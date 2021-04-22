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

"""Handle configuring or disabling the bash completions feature."""


__all__ = ['configure']


import os
import re
import shlex

from . import completions
from . import shared
from .completions import SHORTCUTS_COMPLETIONS_DIR
from .completions import MAIN_SCRIPT, MAIN_SCRIPT_PATH
from .completions import OMNIBUS_SCRIPT_PATH
from .completions import SOURCESCRIPT_LOCATION, USERDIR_LOCATION


BEGIN_MARK = "# begin bash completions support for chaintool"
END_MARK = "# end bash completions support for chaintool"
SOURCE_RE = re.compile(r"(?m)^.*source " + shlex.quote(OMNIBUS_SCRIPT_PATH))


def default_userdir():
    # Note that these var checks only work if the vars are exported.
    if "BASH_COMPLETION_USER_DIR" in os.environ:
        userdir = os.path.join(
            os.environ["BASH_COMPLETION_USER_DIR"],
            "completions")
    else:
        if "XDG_DATA_HOME" in os.environ:
            homedir = os.environ["XDG_DATA_HOME"]
        else:
            homedir = os.environ["HOME"]
        userdir = os.path.join(
            homedir,
            ".local",
            "share",
            "bash-completion",
            "completions")
    return userdir


def get_userdir_path():
    print(
        "Dynamic loading for bash completions supports a per-user directory, "
        "which this\nprogram will use. The directory path shown below is the "
        "one that should work,\nbut if you know differently then you can "
        "change it.")
    print()
    userdir_path = shared.editline("Directory path: ", default_userdir())
    userdir_path = os.path.expanduser(
        os.path.expandvars(userdir_path))
    print()
    return userdir_path


def enable_dynamic(userdir):
    shared.write_choicefile(USERDIR_LOCATION, userdir)
    if userdir is None:
        return
    os.makedirs(userdir, exist_ok=True)
    userdir_script_path = os.path.join(userdir, MAIN_SCRIPT)
    with open(userdir_script_path, 'w') as outstream:
        outstream.write(
            "source {}\n".format(shlex.quote(MAIN_SCRIPT_PATH)))
    for item in os.listdir(SHORTCUTS_COMPLETIONS_DIR):
        completions.create_lazyload(item)
    print("bash completions installed for chaintool and its shortcut scripts.")
    print()


def disable_dynamic(userdir):
    shared.delete_if_exists(os.path.join(userdir, MAIN_SCRIPT))
    for item in os.listdir(SHORTCUTS_COMPLETIONS_DIR):
        completions.delete_lazyload(item)
    shared.write_choicefile(USERDIR_LOCATION, None)
    return True


def check_dynamic(userdir):
    if not os.path.exists(userdir):
        shared.write_choicefile(USERDIR_LOCATION, None)
        print(
            "Dynamic completion loading was previously configured using the "
            "following\ndirectory, but that directory no longer exists:\n  "
            + userdir)
        print()
        return False
    if not os.path.exists(os.path.join(userdir, MAIN_SCRIPT)):
        shared.write_choicefile(USERDIR_LOCATION, None)
        print(
            "Dynamic completion loading was previously configured using the "
            "following\ndirectory, but that seems to no longer be true:\n  "
            + userdir)
        print()
        return False
    return True


def enable_oldstyle(startup_script_path):
    shared.write_choicefile(SOURCESCRIPT_LOCATION, startup_script_path)
    if startup_script_path is None:
        return
    with open(startup_script_path, 'a') as outstream:
        outstream.write(BEGIN_MARK + "\n")
        outstream.write(
            "source {}\n".format(shlex.quote(OMNIBUS_SCRIPT_PATH)))
        outstream.write(END_MARK + "\n")
    print(
        "bash completions installed for chaintool and its shortcut scripts. "
        "Note that\nbecause these are not dynamically loaded, a new shell is "
        "required in order\nfor any changes to take effect (including this "
        "initial installation).")
    print()


def disable_oldstyle(startup_script_path):
    shared.write_choicefile(SOURCESCRIPT_LOCATION, None)
    if startup_script_path is None:
        return True
    return shared.remove_script_additions(
        startup_script_path, BEGIN_MARK, END_MARK, 3)


def check_oldstyle(startup_script_path):
    if not os.path.exists(startup_script_path):
        shared.write_choicefile(SOURCESCRIPT_LOCATION, None)
        print(
            "Old-style completion loading was previously configured using the "
            "following\nfile, but that file no longer exists:\n  "
            + startup_script_path)
        print()
        return False
    with open(startup_script_path, 'r') as instream:
        startup_script = instream.read()
    if SOURCE_RE.search(startup_script) is None:
        shared.write_choicefile(SOURCESCRIPT_LOCATION, None)
        print(
            "Old-style completion loading was previously configured using the "
            "following\file, but that seems to no longer be true:\n  "
            + startup_script_path)
        print()
        return False
    return True


def keep_existing_config():
    dynamic = False
    if os.path.exists(USERDIR_LOCATION):
        dynamic = True
        location_choice = shared.read_choicefile(USERDIR_LOCATION)
        if not check_dynamic(location_choice):
            return False
        print(
            "You currently have dynamic completions enabled, using this "
            "directory:\n  " + location_choice)
    elif os.path.exists(SOURCESCRIPT_LOCATION):
        location_choice = shared.read_choicefile(SOURCESCRIPT_LOCATION)
        if not check_oldstyle(location_choice):
            return False
        print(
            "You currently have old-style completions enabled, using this "
            "file:\n  " + location_choice)
    else:
        return False
    print()
    print("Do you want to leave this configuration as-is? ", end='')
    choice = input("[y/n] ")
    print()
    if choice.lower() != 'n':
        return True
    if dynamic:
        return not disable_dynamic(location_choice)
    return not disable_oldstyle(location_choice)


def early_bailout():
    is_shell, is_bash_login_shell = shared.check_shell()
    if is_shell:
        if is_bash_login_shell:
            return False
        print(
            "You don't appear to be using bash as your login shell. bash "
            "completions\nonly work under bash; are you sure you want to "
            "continue? [n/y] ", end='')
    else:
        print(
            "It doesn't look like you're running in a shell. bash completions "
            "only work\nin the bash shell; are you sure you want to "
            "continue? ", end='')
    choice = input("[n/y] ")
    print()
    if choice.lower() != 'y':
        return True
    return False


def choose_method():
    print(
        "There are two ways to configure bash completions for chaintool. "
        "The correct\nchoice depends on whether the bash-completion package "
        "is installed (and\nactive for your environment), and what version it "
        "is. The rundown:")
    print()
    print(
        "  1: If using bash-completion 2.2 or later, bash completions can "
        "be activated\n     for new shortcut commands as soon as they are "
        "created, in the same shell.\n")
    print(
        "  2: Otherwise, bash completions for a newly created shortcut "
        "command will\n     only be available when a new shell is started.")
    print()
    print(
        "Unfortunately it's difficult to discover (from within this program) "
        "FOR SURE\nwhether a recent version of bash-completion is installed "
        "AND is active in\nyour environment. If you want to test this "
        "yourself, run the following\ncommand in a new shell:\n")
    print(
        "  type __load_completion >/dev/null 2>&1 && echo yep")
    print()
    print(
        "If you see \"yep\" printed when running that command, you have "
        "bash-completion\n2.2 or later active.")
    print()
    print("Which configuration do you want to enable?")
    print(
        "  0: No bash completions\n  1: Use dynamic completions (requires "
        "bash-completion 2.2 or later)\n  2: Use old-style completions "
        "(doesn't depend on bash-completion package)")
    choice = input("choose [0/1/2] ")
    print()
    if choice == "1":
        return "dynamic"
    if choice == "2":
        return "old-style"
    return None


def configure():
    print()
    if keep_existing_config():
        return 0
    if early_bailout():
        return 0
    method = choose_method()
    if method is None:
        return 0
    if method == "dynamic":
        enable_dynamic(get_userdir_path())
    else:
        enable_oldstyle(shared.get_startup_script_path())
    return 0
