#
#  Limited command Shell (lshell)
#
#  Copyright (C) 2008-2013 Ignace Mouzannar (ghantoos) <ghantoos@ghantoos.org>
#
#  This file is part of lshell
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import re
import os
import glob
import fnmatch

# import lshell specifics
from lshell import utils

# Precompiled patterns for the command-parsing hot path. check_secure and
# check_path run on EVERY command entered, so the static regexes they use are
# compiled once at import instead of on every call. Behaviour is identical to
# the previous inline re.* calls (same pattern strings); this only removes the
# per-call cache lookups. Patterns that depend on per-user conf (the allowed /
# denied path regexes) stay dynamic below and are intentionally NOT hoisted.
_PATH_SEP_RE = re.compile(r"\ |;|\||&")
_QUOTE_EDGE_RE = re.compile(r'^["\'`]|["\'`]$')
_DOLLAR_WRAP_RE = re.compile(r"^\$[\(\{]|[\)\}]$")
_VARGLOB_RE = re.compile(r"\$|\*|\?")
_QUOTE_ANY_RE = re.compile("\"|'")
_CURLY_VAR_RE = re.compile(r"\$\{(\w+)\}")
_DOLLAR_VAR_RE = re.compile(r"\$(\w+)")
_DQUOTE_RE = re.compile(r"[^=]\"(.+)\"")
_SQUOTE_RE = re.compile(r"[^=]\'(.+)\'")
_CTRL_RE = re.compile(r"[\x01-\x1F\x7F]")
_DOLLARPAREN_RE = re.compile(r"\$\([^)]+[)]")
_BACKTICK_RE = re.compile(r"\`[^`]+[`]")
_CURLYBRACE_RE = re.compile(r"\$\{[^}]+[}]")
_ASSIGNOP_RE = re.compile(r"=|\+|\?|\-")
# the '&' / '|' "single but not doubled" guards, built with the original
# per-item expression so behaviour is byte-for-byte identical.
_AMP_PIPE_RE = {c: re.compile("[^\%s]\%s[^\%s]" % (c, c, c)) for c in ("&", "|")}

# path components that carry a glob metacharacter; used to spot wildcard
# patterns a shell would expand to a parent-directory traversal.
_GLOB_META_RE = re.compile(r"[*?\[]")


def canonicalize_traversal_globs(item):
    """Rewrite wildcard path components that the executing shell resolves to a
    parent-directory ("..") traversal into a literal "..".

    The command is ultimately run through /bin/sh, whose glob matches "." and
    ".." with dot-leading wildcard patterns -- ".*.", ".?" and ".*" all expand
    to "..". Python's glob never matches "." or "..", so such a token would
    otherwise survive as a literal and os.path.realpath from the home directory
    would hide the escape, allowing a forbidden path the shell would actually
    reach. A component is treated as this kind of traversal when it begins with
    a literal period, contains a glob metacharacter, and its pattern matches
    "..". Rewriting to ".." lets realpath collapse the escape so the allowed /
    denied check evaluates the true destination -- validation then matches what
    the shell will run.
    """
    parts = item.split(os.sep)
    changed = False
    for idx, part in enumerate(parts):
        if (
            part.startswith(".")
            and _GLOB_META_RE.search(part)
            and fnmatch.fnmatch("..", part)
        ):
            parts[idx] = ".."
            changed = True
    return os.sep.join(parts) if changed else item


def warn_count(messagetype, command, conf, strict=None, ssh=None):
    """Update the warning_counter, log and display a warning to the user"""

    log = conf["logpath"]
    if not ssh:
        if strict:
            conf["warning_counter"] -= 1
            if conf["warning_counter"] < 0:
                log.critical('*** forbidden %s -> "%s"' % (messagetype, command))
                log.critical("*** Kicked out")
                sys.exit(1)
            else:
                log.critical('*** forbidden %s -> "%s"' % (messagetype, command))
                sys.stderr.write(
                    "*** You have %s warning(s) left,"
                    " before getting kicked out.\n" % conf["warning_counter"]
                )
                log.error("*** User warned, counter: %s" % conf["warning_counter"])
                sys.stderr.write("This incident has been reported.\n")
        else:
            if not conf["quiet"]:
                log.critical("*** forbidden %s: %s" % (messagetype, command))

    # if you are here, means that you did something wrong. Return 1.
    return 1, conf


def check_path(line, conf, completion=None, ssh=None, strict=None):
    """Check if a path is entered in the line. If so, it checks if user
    are allowed to see this path. If user is not allowed, it calls
    warn_count. In case of completion, it only returns 0 or 1.
    """
    allowed_path_re = str(conf["path"][0])
    denied_path_re = str(conf["path"][1][:-1])

    # split line depending on the operators
    line = line.strip()
    line = _PATH_SEP_RE.split(line)

    for item in line:
        # remove potential quotes or back-ticks
        item = _QUOTE_EDGE_RE.sub("", item)

        # remove potential $(), ${}, ``
        item = _DOLLAR_WRAP_RE.sub("", item)

        # if item has been converted to something other than a string
        # or an int, reconvert it to a string
        if type(item) not in ["str", "int"]:
            item = str(item)
        # replace "~" with home path
        item = os.path.expanduser(item)

        # collapse wildcard forms the exec shell would resolve to a ".."
        # traversal (Python glob never matches "." or "..") so the escape is
        # validated, not hidden behind a surviving literal. Run this before the
        # variable/glob branch below so a bracket form such as ".[.]" -- which
        # carries no $ * ? and would otherwise skip that branch -- is still
        # caught, matching what /bin/sh will run.
        item = canonicalize_traversal_globs(item)

        # expand shell variables and wildcards WITHOUT invoking a shell.
        # historically this ran "`which echo` <item>" through shell=True so the
        # shell would expand $VAR and * ? globs, then took the first result.
        # that handed the path checker a command-injection surface: a token
        # like a$(cmd)b (no spaces, so it survives the split above) was executed
        # by the shell before the path was ever validated. expand in-process
        # instead, reproducing shell semantics without any shell:
        #   $VAR / ${VAR} -> environment value, empty when unset (as the shell
        #   does), then glob the pattern for * ? [ ] wildcards.
        if _VARGLOB_RE.findall(item):
            # remove quotes if available
            item = _QUOTE_ANY_RE.sub("", item)
            # expand ${VAR} then $VAR; an unset variable becomes empty so a
            # payload such as "$unset/etc/passwd" still resolves to the real
            # forbidden path and is caught, matching the previous behaviour.
            item = _CURLY_VAR_RE.sub(lambda m: os.environ.get(m.group(1), ""), item)
            item = _DOLLAR_VAR_RE.sub(lambda m: os.environ.get(m.group(1), ""), item)
            # re-canonicalize in case a variable expanded into a traversal glob.
            item = canonicalize_traversal_globs(item)
            # expand wildcards; take the first match sorted (shell parity), else
            # keep the literal pattern (matches shell nullglob-off behaviour).
            globbed = sorted(glob.glob(item))
            if globbed:
                item = globbed[0]

        tomatch = os.path.realpath(item)
        if os.path.isdir(tomatch) and tomatch[-1] != "/":
            tomatch += "/"
        match_allowed = re.findall(allowed_path_re, tomatch)
        if denied_path_re:
            match_denied = re.findall(denied_path_re, tomatch)
        else:
            match_denied = None

        # if path not allowed
        # case path executed: warn, and return 1
        # case completion: return 1
        if not match_allowed or match_denied:
            if not completion:
                ret, conf = warn_count("path", tomatch, conf, strict=strict, ssh=ssh)
            return 1, conf

    if not completion:
        if not re.findall(allowed_path_re, os.getcwd() + "/"):
            ret, conf = warn_count("path", tomatch, conf, strict=strict, ssh=ssh)
            os.chdir(conf["home_path"])
            conf["promptprint"] = utils.updateprompt(os.getcwd(), conf)
            return 1, conf
    return 0, conf


def check_secure(line, conf, strict=None, ssh=None):
    """This method is used to check the content on the typed command.
    Its purpose is to forbid the user to user to override the lshell
    command restrictions.
    The forbidden characters are placed in the 'forbidden' variable.
    Feel free to update the list. Emptying it would be quite useless..: )

    A warning counter has been added, to kick out of lshell a user if he
    is warned more than X time (X being the 'warning_counter' variable).
    """

    # store original string
    oline = line

    # strip all spaces/tabs
    line = line.strip()

    # init return code
    returncode = 0

    # This logic is kept crudely simple on purpose.
    # At most we might match the same stanza twice
    # (for e.g. "'a'", 'a') but the converse would
    # require detecting single quotation stanzas
    # nested within double quotes and vice versa
    relist = _DQUOTE_RE.findall(line)
    relist2 = _SQUOTE_RE.findall(line)
    relist = relist + relist2
    for item in relist:
        if os.path.exists(item):
            ret_check_path, conf = check_path(item, conf, strict=strict)
            returncode += ret_check_path

    # parse command line for control characters, and warn user
    if _CTRL_RE.findall(oline):
        ret, conf = warn_count("control char", oline, conf, strict=strict, ssh=ssh)
        return ret, conf

    for item in conf["forbidden"]:
        # allow '&&' and '||' even if singles are forbidden
        if item in ["&", "|"]:
            if _AMP_PIPE_RE[item].findall(line):
                ret, conf = warn_count("syntax", oline, conf, strict=strict, ssh=ssh)
                return ret, conf
        else:
            if item in line:
                ret, conf = warn_count("syntax", oline, conf, strict=strict, ssh=ssh)
                return ret, conf

    # check if the line contains $(foo) executions, and check them
    executions = _DOLLARPAREN_RE.findall(line)
    for item in executions:
        # recurse on check_path
        ret_check_path, conf = check_path(item[2:-1].strip(), conf, strict=strict)
        returncode += ret_check_path

        # recurse on check_secure
        ret_check_secure, conf = check_secure(item[2:-1].strip(), conf, strict=strict)
        returncode += ret_check_secure

    # check for executions using back quotes '`'
    executions = _BACKTICK_RE.findall(line)
    for item in executions:
        ret_check_secure, conf = check_secure(item[1:-1].strip(), conf, strict=strict)
        returncode += ret_check_secure

    # check if the line contains ${foo=bar}, and check them
    curly = _CURLYBRACE_RE.findall(line)
    for item in curly:
        # split to get variable only, and remove last character "}"
        if _ASSIGNOP_RE.findall(item):
            variable = _ASSIGNOP_RE.split(item, 1)
        else:
            variable = item
        ret_check_path, conf = check_path(variable[1][:-1], conf, strict=strict)
        returncode += ret_check_path

    # if unknown commands where found, return 1 and don't execute the line
    if returncode > 0:
        return 1, conf
    # in case the $(foo) or `foo` command passed the above tests
    elif line.startswith("$(") or line.startswith("`"):
        return 0, conf

    # in case ';', '|' or '&' are not forbidden, check if in line
    lines = []

    # corrected by Alojzij Blatnik #48
    # test first character
    if line[0] in ["&", "|", ";"]:
        start = 1
    else:
        start = 0

    # split remaining command line
    for i in range(1, len(line)):
        # in case \& or \| or \; don't split it
        if line[i] in ["&", "|", ";"] and line[i - 1] != "\\":
            # if there is more && or || skip it
            if start != i:
                lines.append(line[start:i])
            start = i + 1

    # append remaining command line
    if start != len(line):
        lines.append(line[start : len(line)])

    for separate_line in lines:
        separate_line = " ".join(separate_line.split())
        splitcmd = separate_line.strip().split(" ")
        command = splitcmd[0]
        if len(splitcmd) > 1:
            cmdargs = splitcmd
        else:
            cmdargs = None

        # in case of a sudo command, check in sudo_commands list if allowed
        if command == "sudo":
            if type(cmdargs) == list:
                # allow the -u (user) flag
                if cmdargs[1] == "-u" and cmdargs:
                    sudocmd = cmdargs[3]
                else:
                    sudocmd = cmdargs[1]
                if sudocmd not in conf["sudo_commands"] and cmdargs:
                    ret, conf = warn_count(
                        "sudo command", oline, conf, strict=strict, ssh=ssh
                    )
                    return ret, conf

        # if over SSH, replaced allowed list with the one of overssh
        if ssh:
            conf["allowed"] = conf["overssh"]

        # for all other commands check in allowed list
        if command not in conf["allowed"] and command:
            ret, conf = warn_count("command", command, conf, strict=strict, ssh=ssh)
            return ret, conf
    return 0, conf
