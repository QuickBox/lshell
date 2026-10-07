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

import re
import sys

# single source of truth: lshell/__init__.py sets __version__ before it imports
# any submodule, so this re-export never hits a partial-init cycle. Keeps the
# `lshell --version` string and the packaged version from ever skewing.
from lshell import __version__

# Required config variable list per user
required_config = ["allowed", "forbidden", "warning_counter"]

def default_configfile(platform=None, exec_prefix=None):
    """Return the default configuration file path.

    On Linux the file is always /etc/lshell.conf, whatever prefix the Python
    interpreter was installed under: a locally compiled interpreter has
    sys.exec_prefix = '/usr/local', but the configuration still lives in /etc.
    On *BSD the file follows the interpreter prefix, which is '/usr/{pkg,local}'
    there, so the default path is '/usr/{pkg,local}/etc/lshell.conf'.
    """
    platform = sys.platform if platform is None else platform
    exec_prefix = sys.exec_prefix if exec_prefix is None else exec_prefix
    if platform.startswith("linux") or exec_prefix == "/usr":
        return "/etc/lshell.conf"
    return exec_prefix + "/etc/lshell.conf"


configfile = default_configfile()

# history file
history_file = ".lhistory"

# help text
usage = (
    """Usage: lshell [OPTIONS]
  --config <file>   : Config file location (default %s)
  --<param> <value> : where <param> is *any* config file parameter
  -h, --help        : Show this help message
  --version         : Show version
"""
    % configfile
)

# Intro Text
intro = """You are in a limited shell.
Type '?' or 'help' to get the list of allowed commands"""
# configuration parameters
configparams = [
    "config=",
    "help",
    "version",
    "quiet=",
    "log=",
    "logpath=",
    "loglevel=",
    "logfilename=",
    "syslogname=",
    "allowed=",
    "forbidden=",
    "sudo_commands=",
    "warning_counter=",
    "aliases=",
    "intro=",
    "prompt=",
    "prompt_short=",
    "timer=",
    "path=",
    "home_path=",
    "env_path=",
    "allowed_cmd_path=",
    "env_vars=",
    "scp=",
    "scp_upload=",
    "scp_download=",
    "sftp=",
    "overssh=",
    "strict=",
    "scpforce=",
    "history_size=",
    "history_file=",
    "path_noexec=",
    "path_noexec_strict=",
    "allowed_shell_escape=",
    "winscp=",
    "disable_exit=",
    "include_dir=",
    "max_processes=",
    "command_timeout=",
]

builtins_list = ["cd", "clear", "exit", "export", "history", "lpath", "lsudo"]

# Standard on-disk locations of the sudo noexec shared object. This is the
# runtime backstop that blocks a whitelisted rich binary (python3, git, an
# editor, ...) from exec()ing a shell: lshell prepends LD_PRELOAD=<this> to
# every non-shell-escape command. Kept here (not inline in set_noexec) so the
# lookup set is single-sourced and overridable in tests.
sudo_noexec_libs = [
    "/lib/sudo_noexec.so",
    "/usr/lib/sudo_noexec.so",
    "/usr/lib/sudo/sudo_noexec.so",
    "/usr/libexec/sudo_noexec.so",
    "/usr/libexec/sudo/sudo_noexec.so",
    "/usr/local/lib/sudo_noexec.so",
    "/usr/local/lib/sudo/sudo_noexec.so",
    "/usr/local/libexec/sudo_noexec.so",
    "/usr/local/libexec/sudo/sudo_noexec.so",
    "/usr/pkg/libexec/sudo_noexec.so",
    "/lib64/sudo_noexec.so",
    "/usr/lib64/sudo/sudo_noexec.so",
]

# Account names that may be substituted for %u in path, env_path and
# allowed_cmd_path. Deliberately narrower than what the OS tolerates: no path
# separator, glob or regex metacharacter, list separator or leading dash.
SAFE_USERNAME_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")

FORBIDDEN_ENVIRON = (
    "LD_AOUT_LIBRARY_PATH",
    "LD_AOUT_PRELOAD",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "LD_ORIGIN_PATH",
    "LD_DEBUG_OUTPUT",
    "LD_PROFILE",
    "GCONV_PATH",
    "HOSTALIASES",
    "LOCALDOMAIN",
    "LOCPATH",
    "MALLOC_TRACE",
    "NLSPATH",
    "RESOLV_HOST_CONF",
    "RES_OPTIONS",
    "TMPDIR",
    "TZDIR",
    "LD_USE_LOAD_BIAS",
    "LD_DEBUG",
    "LD_DYNAMIC_WEAK",
    "LD_SHOW_AUXV",
    "GETCONF_DIR",
    "LD_AUDIT",
    "NIS_PATH",
    "PATH",
)
