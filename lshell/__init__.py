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
"""
Limited Shell (lshell)

This module provides functionality for the Limited Shell (lshell) application.
It allows you to restrict the environment of users and configure allowed commands.
"""
__version__ = "0.9.20"
import os
import sys

# import lshell specifics
from lshell.shellcmd import ShellCmd, LshellTimeOut
from lshell.checkconfig import CheckConfig


def main():
    """main function"""
    # set SHELL and get LSHELL_ARGS env variables
    os.environ["SHELL"] = os.path.realpath(sys.argv[0])
    if "LSHELL_ARGS" in os.environ:
        args = sys.argv[1:] + eval(os.environ["LSHELL_ARGS"])
    else:
        args = sys.argv[1:]

    userconf = CheckConfig(args).returnconf()

    try:
        cli = ShellCmd(userconf, args)
        cli.cmdloop()

    except (KeyboardInterrupt, EOFError):
        sys.stdout.write("\nExited on user request\n")
        sys.exit(0)
    except LshellTimeOut:
        userconf["logpath"].error("Timer expired")
        sys.stdout.write("\nTime is up.\n")


if __name__ == "__main__":
    main()
