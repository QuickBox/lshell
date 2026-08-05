#
#    Limited command Shell (lshell)
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

import re
import subprocess
import os
import sys
import signal
import resource
from getpass import getuser

# import lshell specifics
from lshell import variables


def usage():
    """Prints the usage"""
    sys.stderr.write(variables.usage)
    sys.exit(0)


def version():
    """Prints the version"""
    sys.stderr.write("lshell-%s - Limited Shell\n" % variables.__version__)
    sys.exit(0)


def random_string(length):
    """generate a random string"""
    import random
    import string

    randstring = ""
    for char in range(length):
        char = random.choice(string.ascii_letters + string.digits)
        randstring += char

    return randstring


def get_aliases(line, aliases):
    """Replace all configured aliases in the line"""

    for item in list(aliases.keys()):
        escaped_item = re.escape(item)
        reg1 = "(^|;|&&|\|\||\|)\s*%s([ ;&\|]+|$)(.*)" % escaped_item
        reg2 = "(^|;|&&|\|\||\|)\s*%s([ ;&\|]+|$)" % escaped_item

        # in case alias begins with the same command
        # (this is until i find a proper regex solution..)
        aliaskey = random_string(10)

        while re.findall(reg1, line):
            (before, after, rest) = re.findall(reg1, line)[0]
            linesave = line

            line = re.sub(reg2, "%s %s%s" % (before, aliaskey, after), line, 1)

            # if line does not change after sub, exit loop
            if linesave == line:
                break

        # replace the key by the actual alias
        line = line.replace(aliaskey, aliases[item])

    for char in [";"]:
        # remove all remaining double char
        line = line.replace("%s%s" % (char, char), "%s" % char)
    return line


def _make_nproc_preexec(max_processes):
    """Build a preexec_fn (runs in the forked child, before exec) that caps how
    many processes/threads the confined user's real UID may hold, via
    RLIMIT_NPROC. This stops a level-3 user fork-bombing a shared host. It only
    ever LOWERS the ceiling: a non-root process cannot raise a limit above the
    inherited hard value, so the soft target is clamped to the hard limit. The
    cap coexists with the LD_PRELOAD noexec backstop (a textual command prefix,
    applied by the shell at exec) -- they act on different layers.
    """

    def _limit():
        soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
        new_hard = hard
        if hard == resource.RLIM_INFINITY or max_processes < hard:
            new_hard = max_processes
        new_soft = max_processes
        if new_hard != resource.RLIM_INFINITY and new_soft > new_hard:
            new_soft = new_hard
        resource.setrlimit(resource.RLIMIT_NPROC, (new_soft, new_hard))

    return _limit


def _kill_process_group(proc):
    """Terminate the child and every process it spawned. On timeout exec_cmd
    launches the child with start_new_session=True, so it leads its own process
    group; signalling the group (not just proc.pid) means no runaway child is
    leaked. SIGTERM first for a clean exit, SIGKILL as the backstop.
    """
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except OSError:
            return
        try:
            proc.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            continue


def exec_cmd(cmd, conf=None):
    """execute a command, locally catching the signals.

    conf carries two optional runtime-containment controls (both default 0 =
    disabled, so an install that sets neither behaves exactly as before):
      * max_processes   -- RLIMIT_NPROC cap on the child (fork-bomb guard)
      * command_timeout -- seconds after which the child tree is killed
    """
    conf = conf or {}
    try:
        max_processes = int(conf.get("max_processes", 0) or 0)
    except (TypeError, ValueError):
        max_processes = 0
    try:
        command_timeout = int(conf.get("command_timeout", 0) or 0)
    except (TypeError, ValueError):
        command_timeout = 0

    preexec = _make_nproc_preexec(max_processes) if max_processes > 0 else None
    # only start a new session when a timeout is armed, so the whole child tree
    # can be signalled; when disabled the child stays attached to the
    # controlling terminal exactly as before (interactive commands keep working)
    new_session = command_timeout > 0

    proc = None
    try:
        proc = subprocess.Popen(
            [cmd],
            shell=True,
            preexec_fn=preexec,
            start_new_session=new_session,
        )
        if command_timeout > 0:
            try:
                proc.communicate(timeout=command_timeout)
                retcode = proc.returncode
            except subprocess.TimeoutExpired:
                _kill_process_group(proc)
                proc.communicate()
                sys.stderr.write(
                    "*** command exceeded command_timeout (%ss) and was "
                    "terminated\n" % command_timeout
                )
                # 124 is the conventional timeout(1) exit code
                retcode = 124
        else:
            proc.communicate()
            retcode = proc.returncode
    except KeyboardInterrupt:
        # force process to properly terminate (SIGTERM)
        if proc is not None:
            proc.terminate()
            proc.communicate()
        # exit code for user terminated scripts is 130
        retcode = 130

    return retcode


def getpromptbase(conf):
    """get prompt used by the shell"""
    if "prompt" in conf:
        promptbase = conf["prompt"]
        promptbase = promptbase.replace("%u", getuser())
        promptbase = promptbase.replace("%h", os.uname()[1].split(".")[0])
    else:
        promptbase = getuser()

    return promptbase


def updateprompt(path, conf):
    """Set actual prompt to print, updated when changing directories"""

    # get initial promptbase (from configuration)
    promptbase = getpromptbase(conf)

    # update the prompt when directory is changed
    if path == conf["home_path"]:
        prompt = "%s:~$ " % promptbase
    elif conf["prompt_short"] == 1:
        prompt = "%s: %s$ " % (promptbase, path.split("/")[-1])
    elif conf["prompt_short"] == 2:
        prompt = "%s: %s$ " % (promptbase, os.getcwd())
    elif re.findall(conf["home_path"], path):
        prompt = "%s:~%s$ " % (promptbase, path.split(conf["home_path"])[1])
    else:
        prompt = "%s:%s$ " % (promptbase, path)

    return prompt
