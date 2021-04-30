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

"""Low-level logic for "seq" operations.

Called from sequence, command, and xfer modules. Does the bulk of the work
for reading/writing/modifying sequence definitions.

"""


__all__ = [
    "init",
    "exists",
    "all_names",
    "read_dict",
    "write_dict",
    "create_temp",
    "define",
    "delete",
]


import os

import yaml  # from pyyaml

from . import command_impl_print
from . import shared
from .shared import DATA_DIR


SEQ_DIR = os.path.join(DATA_DIR, "sequences")


def init():
    """Initialize module at load time.

    Called from ``__init__`` when package is loaded. Creates the sequences
    directory, inside the data appdir, if necessary.

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


def define(  # pylint: disable=too-many-arguments
    seq, cmds, undefined_cmds, overwrite, print_after_set, compact
):
    """Create or update a sequence to consist of the given commands.

    Do some initial validation of ``seq`` and ``cmds`` to check that they are
    non-empty and consist of legal characters.

    If ``undefined_cmds`` is non-empty, print an error and bail out. (This
    list was already generated for us by the caller to avoid the need for
    inventory lock acquisition in this module).

    Store the commands list in the sequence dictionary.

    Finally, if ``print_after_set`` is ``True``, pretty-print the sequence that
    we just created/updated.

    :param seq:             name of sequence to create/update
    :type seq:              str
    :param cmds:            names of commands to make up the sequence
    :type cmds:             list[str]
    :param undefined_cmds:  names of commands specified for the sequence that
                            do not exist (if not-exist is an error condition)
    :type undefined_cmds:   list[str]
    :param overwrite:       whether to allow if sequence already exists
    :type overwrite:        bool
    :param print_after_set: whether to automatically trigger "print" operation
                            at the end
    :type print_after_set:  bool
    :param compact:         whether to reduce the use of newlines (used when
                            caller is processing many sequences)
    :type compact:          bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    if not compact:
        print()
    if not shared.is_valid_name(seq):
        shared.errprint(
            "seqname '{}' contains whitespace, which is not allowed.".format(
                seq
            )
        )
        print()
        return 1
    if not cmds:
        shared.errprint("At least one cmdname is required.")
        print()
        return 1
    for cmd_name in cmds:
        if not shared.is_valid_name(cmd_name):
            shared.errprint(
                "cmdname '{}' contains whitespace, which is not allowed."
                .format(cmd_name)
            )
            print()
            return 1
    if undefined_cmds:
        shared.errprint("Nonexistent command(s): " + " ".join(undefined_cmds))
        print()
        return 1
    if overwrite:
        mode = "w"
    else:
        mode = "x"
    try:
        write_dict(seq, {"commands": cmds}, mode)
    except FileExistsError:
        print("Sequence '{}' already exists... not modified.".format(seq))
        print()
        return 0
    print("Sequence '{}' set.".format(seq))
    print()
    if print_after_set:
        command_impl_print.print_multi(cmds, False)
    return 0


def delete(seq, is_not_found_ok):
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
    try:
        os.remove(os.path.join(SEQ_DIR, seq))
    except FileNotFoundError:
        if not is_not_found_ok:
            raise
