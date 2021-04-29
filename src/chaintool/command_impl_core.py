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

"""Utilities called by various modules to read/write command files."""


__all__ = [
    "init",
    "exists",
    "all_names",
    "read_dict",
    "write_dict",
    "create_temp",
]


import os

import yaml  # from pyyaml

from .shared import DATA_DIR


CMD_DIR = os.path.join(DATA_DIR, "commands")


def init():
    """Initialize module at load time.

    Called from ``__init__`` when package is loaded. Creates the commands
    directory, inside the data appdir, if necessary.

    """
    os.makedirs(CMD_DIR, exist_ok=True)


def exists(cmd):
    """Test whether the given command already exists.

    Return whether a file of name ``cmd`` exists in the commands directory.

    :param cmd: name of command to check
    :type cmd:  str

    :returns: whether the given command exists
    :rtype:   bool

    """
    return os.path.exists(os.path.join(CMD_DIR, cmd))


def all_names():
    """Get the names of all current commands.

    Return the filenames in the commands directory.

    :returns: current command names
    :rtype:   list[str]

    """
    return os.listdir(CMD_DIR)


def read_dict(cmd):
    """Fetch the contents of a command as a dictionary.

    From the commands directory, load the YAML for the named command. Return
    its properties as a dictionary.

    :param cmd: name of command to read
    :type cmd:  str

    :raises: FileNotFoundError if the command does not exist

    :returns: dictionary of command properties/values
    :rtype:   dict[str, str]

    """
    with open(os.path.join(CMD_DIR, cmd), "r") as cmd_file:
        cmd_dict = yaml.safe_load(cmd_file)
    return cmd_dict


def write_dict(cmd, cmd_dict, mode):
    """Write the contents of a command as a dictionary.

    Dump the command dictionary into a YAML document and write it into the
    commands directory.

    :param cmd:      name of command to write
    :type cmd:       str
    :param cmd_dict: dictionary of command properties/values
    :type cmd_dict:  dict[str, str]
    :param mode:     mode used in the open-to-write
    :type mode:      "w" | "x"

    :raises: FileExistsError if mode is "x" and the command exists

    """
    cmd_doc = yaml.dump(cmd_dict, default_flow_style=False)
    with open(os.path.join(CMD_DIR, cmd), mode) as cmd_file:
        cmd_file.write(cmd_doc)


def create_temp(cmd):
    """Create an empty command used to "reserve the name" during edit-create.

    If the command is being created by interactive edit, an empty-valued
    temporary YAML document is first created via this function, so that the
    inventory lock doesn't need to be held during the edit.

    :param cmd: name of command to make a temp document for
    :type cmd:  str

    """
    cmd_dict = {
        "cmdline": "",
        "format": "",
        "args": dict(),
        "args_modifiers": dict(),
        "toggle_args": dict(),
    }
    write_dict(cmd, cmd_dict, "w")
