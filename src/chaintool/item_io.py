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

"""Utilities called by various modules to read/write command/sequence files."""


__all__ = [
    "init",
    "cmd_exists",
    "seq_exists",
    "cmd_names",
    "seq_names",
    "read_cmd",
    "read_seq",
    "write_cmd",
    "write_seq",
    "delete_cmd",
    "delete_seq",
]


import os

import yaml  # from pyyaml

from .shared import DATA_DIR
from .shared import ItemType


ITEM_DIR = {
    ItemType.CMD: os.path.join(DATA_DIR, "commands"),
    ItemType.SEQ: os.path.join(DATA_DIR, "sequences"),
}


def init(_prev_version, _cur_version):
    """Initialize module.

    Called when chaintool runs. Creates the commands and sequences directories,
    inside the data appdir, if necessary.

    :param _prev_version: version string of previous chaintool run; not used
    :type _prev_version:  str
    :param _cur_version:  version string of current chaintool run; not used
    :type _cur_version:   str

    """
    os.makedirs(ITEM_DIR[ItemType.CMD], exist_ok=True)
    os.makedirs(ITEM_DIR[ItemType.SEQ], exist_ok=True)


def item_exists(item_type, item_name):
    """Test whether the given command/sequence already exists.

    Return whether a file of name ``item_name`` exists in the relevvant
    directory.

    :param item_type: whether this is for commands or sequences
    :type item_type:  shared.ItemType
    :param item_name: name of item to check
    :type item_name:  str

    :returns: whether the given item exists
    :rtype:   bool

    """
    return os.path.exists(os.path.join(ITEM_DIR[item_type], item_name))


def item_names(item_type):
    """Get the names of all current commands/sequences.

    Return the filenames in the relevant directory.

    :param item_type: whether this is for commands or sequences
    :type item_type:  shared.ItemType

    :returns: current item names
    :rtype:   list[str]

    """
    return os.listdir(ITEM_DIR[item_type])


def read_item(item_type, item_name):
    """Fetch the contents of a command/sequence as a dictionary.

    From the relevant directory, load the YAML for the named item. Return
    its properties as a dictionary.

    :param item_type: whether this is for commands or sequences
    :type item_type:  shared.ItemType
    :param item_name: name of item to read
    :type item_name:  str

    :raises: FileNotFoundError if the item does not exist

    :returns: dictionary of item properties/values
    :rtype:   dict[str, str]

    """
    with open(os.path.join(ITEM_DIR[item_type], item_name), "r") as item_file:
        item_dict = yaml.safe_load(item_file)
    return item_dict


def write_item(item_type, item_name, item_dict, mode):
    """Write the contents of a command/sequence as a dictionary.

    Dump the item dictionary into a YAML document and write it into the
    relevant directory.

    :param item_type: whether this is for commands or sequences
    :type item_type:  shared.ItemType
    :param item_name: name of item to write
    :type item_name:  str
    :param item_dict: dictionary of item properties/values
    :type item_dict:  dict[str, str]
    :param mode:      mode used in the open-to-write
    :type mode:       "w" | "x"

    :raises: FileExistsError if mode is "x" and the item exists

    """
    item_doc = yaml.dump(item_dict, default_flow_style=False)
    with open(os.path.join(ITEM_DIR[item_type], item_name), mode) as item_file:
        item_file.write(item_doc)


def delete_item(item_type, item_name, is_not_found_ok):
    """Delete a command/sequence.

    Delete the file of name ``item_name`` in the relevant directory.

    If that file does not exist, and ``is_not_found_ok`` is ``False``, then
    raise a ``FileNotFoundError`` exception.

    :param item_type:       whether this is for commands or sequences
    :type item_type:        shared.ItemType
    :param item_name:       name of item to delete
    :type item_name:        str
    :param is_not_found_ok: whether to silently accept already-deleted case
    :type is_not_found_ok:  bool

    :raises: FileNotFoundError if the item does not exist and
             is_not_found_ok is False

    """
    try:
        os.remove(os.path.join(ITEM_DIR[item_type], item_name))
    except FileNotFoundError:
        if not is_not_found_ok:
            raise


def cmd_exists(cmd):
    """Test whether the given command already exists.

    Return whether a file of name ``cmd`` exists in the commands directory.

    :param cmd: name of command to check
    :type cmd:  str

    :returns: whether the given command exists
    :rtype:   bool

    """
    return item_exists(ItemType.CMD, cmd)


def seq_exists(seq):
    """Test whether the given sequence already exists.

    Return whether a file of name ``seq`` exists in the sequences directory.

    :param seq: name of sequence to check
    :type seq:  str

    :returns: whether the given sequence exists
    :rtype:   bool

    """
    return item_exists(ItemType.SEQ, seq)


def cmd_names():
    """Get the names of all current commands.

    Return the filenames in the commands directory.

    :returns: current command names
    :rtype:   list[str]

    """
    return item_names(ItemType.CMD)


def seq_names():
    """Get the names of all current sequences.

    Return the filenames in the sequences directory.

    :returns: current sequence names
    :rtype:   list[str]

    """
    return item_names(ItemType.SEQ)


def read_cmd(cmd):
    """Fetch the contents of a command as a dictionary.

    From the commands directory, load the YAML for the named command. Return
    its properties as a dictionary.

    :param cmd: name of command to read
    :type cmd:  str

    :raises: FileNotFoundError if the command does not exist

    :returns: dictionary of command properties/values
    :rtype:   dict[str, str]

    """
    return read_item(ItemType.CMD, cmd)


def read_seq(seq):
    """Fetch the contents of a sequence as a dictionary.

    From the sequences directory, load the YAML for the named sequence.
    Return its properties as a dictionary.

    :param seq: name of sequence to read
    :type seq:  str

    :raises: FileNotFoundError if the sequence does not exist

    :returns: dictionary of sequence properties/values
    :rtype:   dict[str, str]

    """
    return read_item(ItemType.SEQ, seq)


def write_cmd(cmd, cmd_dict, mode):
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
    return write_item(ItemType.CMD, cmd, cmd_dict, mode)


def write_seq(seq, seq_dict, mode):
    """Write the contents of a sequence as a dictionary.

    Dump the sequence dictionary into a YAML document and write it into the
    sequences directory.

    :param seq:      name of sequence to write
    :type seq:       str
    :param seq_dict: dictionary of sequence properties/values
    :type seq_dict:  dict[str, str]
    :param mode:     mode used in the open-to-write
    :type mode:      "w" | "x"

    :raises: FileExistsError if mode is "x" and the sequence exists

    """
    return write_item(ItemType.SEQ, seq, seq_dict, mode)


def delete_cmd(cmd, is_not_found_ok):
    """Delete a command.

    Delete the file of name ``cmd`` in the commands directory.

    If that file does not exist, and ``is_not_found_ok`` is ``False``, then
    raise a ``FileNotFoundError`` exception.

    :param cmd:             names of command to delete
    :type cmd:              str
    :param is_not_found_ok: whether to silently accept already-deleted case
    :type is_not_found_ok:  bool

    :raises: FileNotFoundError if the command does not exist and
             is_not_found_ok is False

    """
    return delete_item(ItemType.CMD, cmd, is_not_found_ok)


def delete_seq(seq, is_not_found_ok):
    """Delete a sequence.

    Delete the file of name ``seq`` in the sequences directory.

    If that file does not exist, and ``is_not_found_ok`` is ``False``, then
    raise a ``FileNotFoundError`` exception.

    :param seq:             names of sequence to delete
    :type seq:              str
    :param is_not_found_ok: whether to silently accept already-deleted case
    :type is_not_found_ok:  bool

    :raises: FileNotFoundError if the sequence does not exist and
             is_not_found_ok is False

    """
    return delete_item(ItemType.SEQ, seq, is_not_found_ok)
