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

"""Utilities called by various modules to read/write sequence files."""


__all__ = [
    "SEQ_DIR",
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


SEQ_DIR = os.path.join(DATA_DIR, "sequences")


def init(_prev_version, _cur_version):
    """Initialize module at load time.

    Called from :mod:`.__init__` when package is loaded. Creates the sequences
    directory, inside the data appdir, if necessary.

    :param _prev_version: version string of previous chaintool run; not used
    :type _prev_version:  str
    :param _cur_version:  version string of current chaintool run; not used
    :type _cur_version:   str

    """
    os.makedirs(SEQ_DIR, exist_ok=True)


def exists(seq):
    """Test whether the given sequence already exists.

    Return whether a file of name ``seq`` exists in the sequences directory.

    :param seq: name of sequence to check
    :type seq:  str

    :returns: whether the given sequence exists
    :rtype:   bool

    """
    return os.path.exists(os.path.join(SEQ_DIR, seq))


def all_names():
    """Get the names of all current sequences.

    Return the filenames in the sequences directory.

    :returns: current sequence names
    :rtype:   list[str]

    """
    return os.listdir(SEQ_DIR)


def read_dict(seq):
    """Fetch the contents of a sequence as a dictionary.

    From the sequences directory, load the YAML for the named sequence.
    Return its properties as a dictionary.

    :param seq: name of sequence to read
    :type seq:  str

    :raises: FileNotFoundError if the sequence does not exist

    :returns: dictionary of sequence properties/values
    :rtype:   dict[str, str]

    """
    with open(os.path.join(SEQ_DIR, seq), "r") as seq_file:
        seq_dict = yaml.safe_load(seq_file)
    return seq_dict


def write_dict(seq, seq_dict, mode):
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
    seq_doc = yaml.dump(seq_dict, default_flow_style=False)
    with open(os.path.join(SEQ_DIR, seq), mode) as seq_file:
        seq_file.write(seq_doc)


def create_temp(seq):
    """Create an empty sequence used to "reserve the name" during edit-create.

    If the sequence is being created by interactive edit, an empty-valued
    temporary YAML document is first created via this function, so that the
    inventory lock doesn't need to be held during the edit.

    :param seq: name of sequence to make a temp document for
    :type seq:  str

    """
    write_dict(seq, {"commands": []}, "w")
