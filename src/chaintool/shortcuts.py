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

"""Create/delete "shortcut" scripts for commands and sequences.

These scripts allow doing a command or sequence run operation with less
typing. They are placed in a directory that can be added to the user's PATH.

"""


__all__ = [
    "init",
    "create_cmd_shortcut",
    "delete_cmd_shortcut",
    "create_seq_shortcut",
    "delete_seq_shortcut",
]


import os
import shlex

from . import shared

from .shared import DATA_DIR
from .shared import LOCATIONS_DIR


SHORTCUTS_DIR = os.path.join(DATA_DIR, "shortcuts")
PATHSCRIPT_LOCATION = os.path.join(
    LOCATIONS_DIR, "shortcuts_path_setting_script"
)


def init():
    """Initialize module at load time.

    Called from ``__init__`` when package is loaded. Creates the shortcuts
    directory, inside the data appdir, if necessary.

    """
    os.makedirs(SHORTCUTS_DIR, exist_ok=True)


def make_executable(path):
    """Add executable permissions to a file.

    Add execute permissions where read permissions exist. (Does nothing on
    Windows.)

    :param path: filepath to make executable
    :type path:  str

    """
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2
    os.chmod(path, mode)


def create_shortcut(item_type, item_name):
    """Common code for creating a shortcut script.

    Create a script in the shortcuts dir with the same name as the command
    or sequence, and make it executable.

    This script will invoke chaintool to run the command or sequence, using
    either the system default version of Python 3 or the version specified by
    the CHAINTOOL_SHORTCUT_PYTHON environment variable, and passing along any
    command-line arguments.

    The script also has its own "--cmdgroup" option which can be invoked by
    the bash completion code (probably never by a human user). This just
    returns whether the script is for a cmd or seq. The bash completion code
    uses this info to help generate the appropriate completions.

    :param item_type: whether this is for commands or sequences
    :type item_type:  "cmd" | "seq"
    :param item_name: name of the command or sequence to make a shortcut for
    :type item_name:  str

    """
    shortcut_path = os.path.join(SHORTCUTS_DIR, item_name)
    # Shell-to-use for running this script doesn't really matter, but let
    # the user force it if they wish.
    if "CHAINTOOL_SHORTCUT_SHELL" in os.environ:
        shortcut_shell = shlex.quote(os.environ["CHAINTOOL_SHORTCUT_SHELL"])
    elif "SHELL" in os.environ:
        shortcut_shell = shlex.quote(os.environ["SHELL"])
    else:
        shortcut_shell = "/usr/bin/env sh"
    hashbang = "#!" + shortcut_shell + "\n"
    with open(shortcut_path, "w") as outstream:
        outstream.write(hashbang)
        outstream.write(
            'if [ "$1" = "--cmdgroup" ]; then echo {}; exit 0; fi\n'.format(
                item_type
            )
        )
        # Also let the user force the version of Python to use.
        outstream.write('if [ "$CHAINTOOL_SHORTCUT_PYTHON" = "" ]\n')
        outstream.write("then\n")
        outstream.write(
            '  chaintool {} run {} "$@"\n'.format(item_type, item_name)
        )
        outstream.write("else\n")
        outstream.write(
            '  "$CHAINTOOL_SHORTCUT_PYTHON" -m chaintool '
            '{} run {} "$@"\n'.format(item_type, item_name)
        )
        outstream.write("fi\n")
    make_executable(shortcut_path)


def create_cmd_shortcut(cmd_name):
    """Create a shortcut script for a command.

    Delegate to :func:`create_shortcut` with the "cmd" type and the given
    name.

    :param cmd_name: name of the command to make a shortcut for
    :type cmd_name:  str

    """
    create_shortcut("cmd", cmd_name)


def delete_cmd_shortcut(cmd_name):
    """Delete a shortcut script for a command.

    Remove the file with the given name in the shortcuts directory.

    :param cmd_name: name of the command to delete a shortcut for
    :type cmd_name:  str

    """
    shared.delete_if_exists(os.path.join(SHORTCUTS_DIR, cmd_name))


def create_seq_shortcut(seq_name):
    """Create a shortcut script for a sequence.

    Delegate to :func:`create_shortcut` with the "seq" type and the given
    name.

    :param seq_name: name of the sequence to make a shortcut for
    :type seq_name:  str

    """
    create_shortcut("seq", seq_name)


def delete_seq_shortcut(seq_name):
    """Delete a shortcut script for a sequence.

    Remove the file with the given name in the shortcuts directory.

    :param seq_name: name of the sequence to delete a shortcut for
    :type seq_name:  str

    """
    shared.delete_if_exists(os.path.join(SHORTCUTS_DIR, seq_name))
