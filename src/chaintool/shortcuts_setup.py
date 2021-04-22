# -*- coding: utf-8 -*-
#
# Copyright 2021 Joel Baxter
#
# This file is part of chaintool.
#
# chaintool is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# chaintool is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with chaintool.  If not, see <https://www.gnu.org/licenses/>.

"""Handle setting/unsetting the PATH modification for shortcuts."""


__all__ = ['configure']


import os
import re
import shlex

from . import shared
from .shortcuts import SHORTCUTS_DIR
from .shortcuts import PATHSCRIPT_LOCATION


BEGIN_MARK = "# begin PATH modification for chaintool shortcut scripts"
END_MARK = "# end PATH modification for chaintool shortcut scripts"
PATH_RE = re.compile(r"(?m)^.*export PATH=.*" + shlex.quote(SHORTCUTS_DIR))


def unconfigure(startup_script_path):
    print("Do you want to leave this configuration as-is? ", end='')
    choice = input("[y/n] ")
    print()
    if choice.lower() != 'n':
        return False
    unconfigured = shared.remove_script_additions(
        startup_script_path, BEGIN_MARK, END_MARK, 3)
    if unconfigured:
        shared.write_choicefile(PATHSCRIPT_LOCATION, None)
    return unconfigured


def keep_existing_config():
    already_in_path = (
        "PATH" in os.environ and SHORTCUTS_DIR in os.environ["PATH"])
    location_choice = shared.read_choicefile(PATHSCRIPT_LOCATION)
    if location_choice is None:
        if already_in_path:
            print(
                "Command and sequence names should currently be available to "
                "run as\nshortcuts, because the shortcuts directory is "
                "already in your PATH. There's\nno record of this program "
                "being used to help set that up, so if you want to\nremove "
                "that PATH configuration you'll need to do it manually.")
            print()
            return True
        return False
    if not os.path.exists(location_choice):
        shared.write_choicefile(PATHSCRIPT_LOCATION, None)
        print(
            "The PATH value for shortcuts used to be set in the following "
            "file, but this\nfile no longer exists:\n  " + location_choice)
        print()
        return False
    with open(location_choice, 'r') as instream:
        startup_script = instream.read()
    if not PATH_RE.search(startup_script):
        shared.write_choicefile(PATHSCRIPT_LOCATION, None)
        print(
            "The PATH value for shortcuts used to be set in the following "
            "file, but that\nseems to no longer be true:\n  "
            + location_choice)
        print()
        return False
    if already_in_path:
        print(
            "Command and sequence names should currently be available to run "
            "as\nshortcuts, because the shortcuts directory is already in "
            "your PATH through\na setting in this file:\n  "
            + location_choice)
        print()
        return not unconfigure(location_choice)
    print(
        "The following file already includes a line to set the PATH "
        "appropriately.\nIf it's a valid startup script, then shortcuts "
        "should be active next time a\nshell is started.\n  "
        + location_choice)
    print()
    return not unconfigure(location_choice)


def early_bailout():
    is_shell, _ = shared.check_shell()
    if is_shell:
        print(
            "Modify startup script to insert this PATH setting? ", end='')
        choice_default = 'y'
        choice = input("[y/n] ")
    else:
        print(
            "It doesn't look like you're running in a shell, so there may not "
            "be an\nappropriate startup script file in which to add this PATH "
            "setting. Is there\na file where you do want the PATH setting to "
            "be inserted? ", end='')
        choice_default = 'n'
        choice = input("[n/y] ")
    print()
    if not choice:
        choice = choice_default
    if choice.lower() != 'y':
        return True
    return False


def update_startup_script(startup_script_path):
    shared.write_choicefile(PATHSCRIPT_LOCATION, startup_script_path)
    if startup_script_path is None:
        return
    with open(startup_script_path, 'a') as outstream:
        outstream.write(BEGIN_MARK + "\n")
        outstream.write("export PATH=$PATH:{}\n".format(
            shlex.quote(SHORTCUTS_DIR)))
        outstream.write(END_MARK + "\n")
    print(
        "File modified. Shortcuts should be active next time a shell is "
        "started.")
    print()


def configure():
    print()
    print(
        "For shortcuts access, this directory must be in your PATH:\n"
        "    {}".format(SHORTCUTS_DIR))
    print()
    if keep_existing_config():
        return 0
    if early_bailout():
        return 0
    update_startup_script(shared.get_startup_script_path())
    return 0
