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


__all__ = ['enable',
           'create_cmd_shortcut',
           'delete_cmd_shortcut',
           'create_seq_shortcut',
           'delete_seq_shortcut']


import os
import re
import shlex

from . import shared

from .constants import DATA_DIR


SHORTCUTS_DIR = os.path.join(DATA_DIR, "shortcuts")
PATH_RE = re.compile(r"(?m)^.*export PATH=.*" + shlex.quote(SHORTCUTS_DIR))

os.makedirs(SHORTCUTS_DIR, exist_ok=True)


# Snippet from Jonathon Reinhart to add executable perm where read perm
# exists. Does nothing on Windows of course.
def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2
    os.chmod(path, mode)


def create_shortcut(item_type, item_name):
    shortcut_path = os.path.join(SHORTCUTS_DIR, item_name)
    # XXX create batch file instead if on Windows?
    sh_hashbang = "#!/usr/bin/env sh\n"
    if "CHAINTOOL_SHORTCUT_SHELL" in os.environ:
        hashbang = "#!" + shlex.quote(os.environ["CHAINTOOL_SHORTCUT_SHELL"]) + "\n"
    elif "SHELL" in os.environ:
        hashbang = "#!" + shlex.quote(os.environ["SHELL"]) + "\n"
    else:
        hashbang = sh_hashbang
    with open(shortcut_path, 'w') as outstream:
        outstream.write(hashbang)
        outstream.write(
            "if [ \"$1\" = \"--cmdgroup\" ]; then echo {}; exit 0; fi\n".format(
                item_type))
        outstream.write(
            "$CHAINTOOL_SHORTCUT_PYTHON chaintool {} run {} \"$@\"\n".format(
                item_type, item_name))
    make_executable(shortcut_path)


def delete_shortcut(item_name):
    try:
        os.remove(os.path.join(SHORTCUTS_DIR, item_name))
    except FileNotFoundError:
        pass


def enable():
    print()
    shortcuts_dir_on_path = False
    if "PATH" in os.environ:
        if SHORTCUTS_DIR in os.environ["PATH"]:
            shortcuts_dir_on_path = True
    if shortcuts_dir_on_path:
        print(
            "The shortcuts directory is already in your PATH. Command and "
            "sequence names\nshould be available to run.")
        print()
        return
    print(
        "For shortcuts, this directory must be in your PATH:\n"
        "    {}".format(SHORTCUTS_DIR))
    print()
    bash_shell = False
    startup_script_path = ""
    if "SHELL" in os.environ:
        bash_shell = os.environ["SHELL"].endswith("/bash")
        print(
            "Modify startup script to insert this PATH setting? [Y/n] ", end='')
        choice_default = 'y'
    else:
        print(
            "It doesn't look like you're running in a shell, so there may not "
            "be an\nappropriate startup script file in which to add this PATH "
            "setting. Is there\na file where you do want the PATH setting to "
            "be inserted? [y/N] ", end='')
        choice_default = 'n'
    choice = input()
    print()
    if not choice:
        choice = choice_default
    if choice.lower() != 'y':
        return
    if bash_shell:
        startup_script_path = os.path.expanduser(os.path.join("~", ".bashrc"))
    startup_script_path = shared.editline(
        "Path to startup script: ",
        startup_script_path)
    startup_script_path = os.path.expanduser(startup_script_path)
    print()
    if not os.path.exists(startup_script_path):
        print("File does not exist.")
        print()
        return
    with open(startup_script_path, 'r') as instream:
        startup_script = instream.read()
    if PATH_RE.search(startup_script):
        print(
            "Script already includes a line to set the PATH appropriately. "
            "Shortcuts\nshould be active next time a shell is started.")
        print()
        return
    with open(startup_script_path, 'a') as outstream:
        outstream.write("\n# for chaintool shortcut scripts:\n")
        outstream.write("export PATH=$PATH:{}\n".format(shlex.quote(SHORTCUTS_DIR)))
    print(
        "File modified. Shortcuts should be active next time a shell is "
        "started.")
    print()
    return


def create_cmd_shortcut(cmd_name):
    create_shortcut("cmd", cmd_name)


def delete_cmd_shortcut(cmd_name):
    delete_shortcut(cmd_name)


def create_seq_shortcut(seq_name):
    create_shortcut("seq", seq_name)


def delete_seq_shortcut(seq_name):
    delete_shortcut(seq_name)
