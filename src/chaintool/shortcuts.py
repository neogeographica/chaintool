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

"""Create/delete "shortcut" scripts for commands and sequences."""


__all__ = ['init',
           'create_cmd_shortcut',
           'delete_cmd_shortcut',
           'create_seq_shortcut',
           'delete_seq_shortcut']


import os
import shlex

from . import shared

from .shared import DATA_DIR
from .shared import LOCATIONS_DIR


SHORTCUTS_DIR = os.path.join(DATA_DIR, "shortcuts")
PATHSCRIPT_LOCATION = os.path.join(
    LOCATIONS_DIR,
    "shortcuts_path_setting_script")


def init():
    os.makedirs(SHORTCUTS_DIR, exist_ok=True)


# Snippet from Jonathon Reinhart to add executable perm where read perm
# exists. Does nothing on Windows of course.
def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2
    os.chmod(path, mode)


def create_shortcut(item_type, item_name):
    shortcut_path = os.path.join(SHORTCUTS_DIR, item_name)
    if "CHAINTOOL_SHORTCUT_SHELL" in os.environ:
        shortcut_shell = shlex.quote(os.environ["CHAINTOOL_SHORTCUT_SHELL"])
    elif "SHELL" in os.environ:
        shortcut_shell = shlex.quote(os.environ["SHELL"])
    else:
        shortcut_shell = "/usr/bin/env sh"
    hashbang = "#!" + shortcut_shell + "\n"
    with open(shortcut_path, 'w') as outstream:
        outstream.write(hashbang)
        outstream.write(
            "if [ \"$1\" = \"--cmdgroup\" ]; "
            "then echo {}; exit 0; fi\n".format(item_type))
        outstream.write(
            "if [ \"$CHAINTOOL_SHORTCUT_PYTHON\" = \"\" ]\n")
        outstream.write(
            "then\n")
        outstream.write(
            "  chaintool {} run {} \"$@\"\n".format(item_type, item_name))
        outstream.write(
            "else\n")
        outstream.write(
            "  \"$CHAINTOOL_SHORTCUT_PYTHON\" -m chaintool "
            "{} run {} \"$@\"\n".format(item_type, item_name))
        outstream.write(
            "fi\n")
    make_executable(shortcut_path)


def create_cmd_shortcut(cmd_name):
    create_shortcut("cmd", cmd_name)


def delete_cmd_shortcut(cmd_name):
    shared.delete_if_exists(os.path.join(SHORTCUTS_DIR, cmd_name))


def create_seq_shortcut(seq_name):
    create_shortcut("seq", seq_name)


def delete_seq_shortcut(seq_name):
    shared.delete_if_exists(os.path.join(SHORTCUTS_DIR, seq_name))
