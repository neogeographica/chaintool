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
for creating/modifying/deleting sequence definitions.

"""


__all__ = [
    "define",
]


from . import command_impl_print
from . import item_io
from . import shared


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
        item_io.write_seq(seq, {"commands": cmds}, mode)
    except FileExistsError:
        print("Sequence '{}' already exists... not modified.".format(seq))
        print()
        return 0
    print("Sequence '{}' set.".format(seq))
    print()
    if print_after_set:
        command_impl_print.print_multi(cmds, False)
    return 0
