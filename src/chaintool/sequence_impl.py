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

Called from sequence, command, command_impl, and xfer modules. Does the
bulk of the work for reading/writing/modifying sequence definitions.

"""


__all__ = ['init',
           'exists',
           'all_names',
           'read_dict',
           'create_temp',
           'define',
           'delete']


import os

import yaml  # from pyyaml

from . import command_impl
from . import shared
from .shared import DATA_DIR


SEQ_DIR = os.path.join(DATA_DIR, "sequences")


def init():
    os.makedirs(SEQ_DIR, exist_ok=True)


def exists(seq):
    return os.path.exists(os.path.join(SEQ_DIR, seq))


def all_names():
    return os.listdir(SEQ_DIR)


def read_dict(seq):
    with open(os.path.join(SEQ_DIR, seq), 'r') as seq_file:
        seq_dict = yaml.safe_load(seq_file)
    return seq_dict


def write_doc(seq, seq_doc, mode):
    with open(os.path.join(SEQ_DIR, seq), mode) as seq_file:
        seq_file.write(seq_doc)


def create_temp(seq):
    seq_doc = yaml.dump(
        {
            'commands': []
        },
        default_flow_style=False
    )
    write_doc(seq, seq_doc, 'w')


def define(  # pylint: disable=too-many-arguments
        seq,
        cmds,
        undefined_cmds,
        overwrite,
        print_after_set,
        compact):
    if not compact:
        print()
    if not shared.is_valid_name(seq):
        shared.errprint(
            "seqname '{}' contains whitespace, "
            "which is not allowed.".format(seq))
        print()
        return 1
    if not cmds:
        shared.errprint("At least one cmdname is required.")
        print()
        return 1
    for cmd_name in cmds:
        if not shared.is_valid_name(cmd_name):
            shared.errprint(
                "cmdname '{}' contains whitespace, "
                "which is not allowed.".format(cmd_name))
            print()
            return 1
    if undefined_cmds:
        shared.errprint("Nonexistent command(s): " + ' '.join(undefined_cmds))
        print()
        return 1
    seq_doc = yaml.dump(
        {
            'commands': cmds
        },
        default_flow_style=False
    )
    if overwrite:
        mode = 'w'
    else:
        mode = 'x'
    try:
        write_doc(seq, seq_doc, mode)
    except FileExistsError:
        print("Sequence '{}' already exists... not modified.".format(seq))
        print()
        return 0
    print("Sequence '{}' set.".format(seq))
    print()
    if print_after_set:
        command_impl.print_multi(cmds)
    return 0


def delete(seq, is_not_found_ok):
    try:
        os.remove(os.path.join(SEQ_DIR, seq))
    except FileNotFoundError:
        if not is_not_found_ok:
            raise
