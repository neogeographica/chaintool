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

"""Top-level logic for "seq" operations.

Called from cli module. Handles locking and shortcuts/completions; delegates
to sequence_impl_* modules for most of the work.

Note that most locks acquired here are released only when the program exits.
Operations are meant to be invoked one per program instance, using the CLI.

"""


__all__ = [
    "cli_list",
    "cli_set",
    "cli_edit",
    "cli_print",
    "cli_del",
    "cli_run",
    "cli_vals",
]


import atexit
import copy
import os
import tempfile

from colorama import Fore

from . import command_impl_core
from . import command_impl_op
from . import command_impl_print
from . import completions
from . import locks
from . import sequence_impl_core
from . import sequence_impl_op
from . import shared
from . import shortcuts


def undefined_cmds(cmds, ignore_undefined_cmds):
    """Return which commands don't exist, if ``ignore_undefined_cmds``.

    Utility used by :func:`cli_set` and :func:`cli_edit`.

    If ``ignore_undefined_cmds`` is ``True``, just return emptylist. Otherwise
    acquire the cmd inventory readlock and compare the incoming ``cmds`` list
    to the list of all currently defined commands. Return the list of the
    elements of cmds that are not the names of currently defined commands.

    :param cmds:                  list of command names to check
    :type cmds:                   list[str]
    :param ignore_undefined_cmds: if True, always return emptylist
    :type ignore_undefined_cmds:  bool

    :returns: list of names from cmds that will be treated as errors
    :rtype:   list[str]

    """
    if ignore_undefined_cmds:
        return []
    locks.inventory_lock("cmd", locks.LockType.READ)
    return list(set(cmds) - set(command_impl_core.all_names()))


def req_stdout_flags(cmds):
    """Determine which commands need to have their stdout captured.

    Examine the given commands. For any command that uses the ``prev_stdout``
    placeholder, mark that the previous command needs to have its stdout
    captured. Return a list of booleans the same length as the list of
    commands, each element indicating whether the corresponding command needs
    to be captured.

    :param cmds: list of command names to check
    :type cmds:  list[str]

    :returns: list of flags indicating which cmd outputs need to be captured.
    :rtype:   list[bool]

    """
    flags = []
    for cmd in cmds[1:]:
        try:
            cmd_dict = command_impl_core.read_dict(cmd)
            uses_prev_stdout = "prev_stdout" in cmd_dict["args"]
        except FileNotFoundError:
            uses_prev_stdout = False
        flags.append(uses_prev_stdout)
    flags.append(False)
    return flags


def cli_list(column):
    """Print the list of current sequence names.

    No locking needed. Just read a directory list and print it.

    :param column: if True, print as one sequence name per line
    :type column:  bool

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    print()
    sequence_names = sequence_impl_core.all_names()
    if sequence_names:
        if column:
            print("\n".join(sequence_names))
        else:
            print(" ".join(sequence_names))
        print()
    return 0


def cli_set(seq, cmds, ignore_undefined_cmds, overwrite, print_after_set):
    """Create or update a sequence to consist of the given list of commands.

    Acquire the seq inventory and item writelocks. If we're creating a new
    sequence, also acquire the cmd inventory readlock and check to see whether
    a command of this same name already exists (reject if so).

    Delegate to :func:`.sequence_impl_op.define` to create/update the sequence.

    Finally: if we successfully created a new sequence, set up its shortcut
    (:func:`.shortcuts.create_seq_shortcut`) and autocompletion behavior
    (:func:`.completions.create_completion`).

    :param seq:                   name of sequence to create/update
    :type seq:                    str
    :param cmds:                  list of command names to form the sequence
    :type cmds:                   list[str]
    :param ignore_undefined_cmds: if True, don't validate that commands exist
    :type ignore_undefined_cmds:  bool
    :param overwrite:             whether to allow if sequence already exists
    :type overwrite:              bool
    :param print_after_set:       whether to automatically trigger "print"
                                  operation at the end
    :type print_after_set:        bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.item_lock("seq", seq, locks.LockType.WRITE)
    creating = False
    if not sequence_impl_core.exists(seq):
        creating = True
        locks.inventory_lock("cmd", locks.LockType.READ)
        if command_impl_core.exists(seq):
            print()
            shared.errprint(
                "Sequence '{}' cannot be created because a command exists with"
                " the same name.".format(seq)
            )
            print()
            return 1
    status = sequence_impl_op.define(
        seq,
        cmds,
        undefined_cmds(cmds, ignore_undefined_cmds),
        overwrite,
        print_after_set,
        False,
    )
    if creating and not status:
        shortcuts.create_seq_shortcut(seq)
        completions.create_completion(seq)
    return status


def cli_edit(seq, ignore_undefined_cmds, print_after_set):
    """Interactively create or update a sequence.

    Acquire the seq inventory and item writelocks. Read the current sequence
    command list (if it exists).

    If we're creating a new sequence, also acquire the cmd inventory lock and
    check to see whether a command of this same name already exists (reject if
    so). Then create a temporary empty sequence that we can edit.

    Release the inventory locks and let the user interactively edit any
    existing list of cmds. The delegate to :func:`.sequence_impl_op.define` to
    create/update the sequence.

    Finally: if we successfully created a new sequence, set up its shortcut
    (:func:`.shortcuts.create_seq_shortcut`) and autocompletion behavior
    (:func:`.completions.create_completion`).

    :param seq:                   name of sequence to create/update
    :type seq:                    str
    :param ignore_undefined_cmds: if True, don't validate that commands exist
    :type ignore_undefined_cmds:  bool
    :param print_after_set:       whether to automatically trigger "print"
                                  operation at the end
    :type print_after_set:        bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.item_lock("seq", seq, locks.LockType.WRITE)
    locks.inventory_lock("cmd", locks.LockType.READ)
    cleanup_fun = None
    try:
        seq_dict = sequence_impl_core.read_dict(seq)
        old_commands_str = " ".join(seq_dict["commands"])
    except FileNotFoundError:
        if command_impl_core.exists(seq):
            print()
            shared.errprint(
                "Sequence '{}' cannot be created because a command exists with"
                " the same name.".format(seq)
            )
            print()
            return 1
        # We want to release the inventory locks before we go into interactive
        # edit. Creating a temp/empty sequence to edit here makes that safe to
        # do; any concurrent cmd creation will see it when checking for name
        # conflicts.
        old_commands_str = ""
        cleanup_fun = lambda: sequence_impl_op.delete(seq, True)
        atexit.register(cleanup_fun)
        sequence_impl_core.create_temp(seq)
    current_commands = command_impl_core.all_names()
    locks.release_inventory_lock("cmd", locks.LockType.READ)
    locks.release_inventory_lock("seq", locks.LockType.WRITE)
    # We're including the newline in the prompt here, so that if the line gets
    # re-displayed after showing some completion suggestions it will get some
    # separation from the completions list.
    new_commands_str = shared.editline(
        "\ncommands: ", old_commands_str, current_commands
    )
    new_commands = new_commands_str.split()
    status = sequence_impl_op.define(
        seq,
        new_commands,
        undefined_cmds(new_commands, ignore_undefined_cmds),
        True,
        print_after_set,
        False,
    )
    if cleanup_fun:
        if status:
            # Make sure we don't leave the temp/empty sequence laying around
            # in the error case.
            cleanup_fun()
        else:
            shortcuts.create_seq_shortcut(seq)
            completions.create_completion(seq)
        atexit.unregister(cleanup_fun)
    return status


def cli_print(seq):
    """Pretty-print the info for all commands in a sequence.

    Acquire the seq item readlock and cmd inventory readlock. Read the
    sequence's command list. Readlock those commands and delegate to
    :func:`.command_impl_print.print_multi` to pretty-print the info for that
    list of commands.

    :param seq:               name of sequence to print
    :type seq:                str

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.item_lock("seq", seq, locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.READ)
    try:
        seq_dict = sequence_impl_core.read_dict(seq)
    except FileNotFoundError:
        print()
        shared.errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    commands = seq_dict["commands"]
    locks.multi_item_lock("cmd", commands, locks.LockType.READ)
    print()
    return command_impl_print.print_multi(commands, False)


def cli_del(delseqs):
    """Delete one or more sequences.

    Acquire the seq inventory writelock, and item writelocks on the sequences
    to delete. Delete each sequence (via :func:`.sequence_impl_op.delete`),
    and tear down its shortcut (:func:`.shortcuts.delete_seq_shortcut`) and
    autocompletion behavior (:func:`.completions.delete_completion`).

    :param delseqs: names of sequences to delete
    :type delseqs:  list[str]

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.multi_item_lock("seq", delseqs, locks.LockType.WRITE)
    print()
    for seq in delseqs:
        try:
            sequence_impl_op.delete(seq, False)
        except FileNotFoundError:
            print("Sequence '{}' does not exist.".format(seq))
            continue
        print("Sequence '{}' deleted.".format(seq))
        shortcuts.delete_seq_shortcut(seq)
        completions.delete_completion(seq)
    print()
    return 0


def cli_run(seq, quiet, args, ignore_errors, skip_cmdnames):
    """Run a sequence.

    Acquire the seq item readlock and cmd inventory readlock. Read the
    sequence's command list, then acquire readlocks on those commands and
    release the cmd inventory readlock.

    Do a pre-pass through the commands to see which ones want to consume
    the stdout of the previous command; we'll use that info to correctly
    populate ``stdout_requested`` in the reserved-placeholders context
    passed to each command execution.

    Create a temporary directory using a context manager. While the temp
    directory exists, grab its name for the value of the "tempdir" reserved
    placeholder, and delegate to :func:`.command_impl_op.run` to execute each
    command in the list that is not a member of ``skip_cmdnames``. If a
    command returns an error status and ignore_errors is false, bail out.

    In the success case, finally print a warning if any of the given
    placeholder args were irrelevant for all the executed commands.

    Note that ``args`` may be modified during the process of running commands.

    :param seq:           name of sequence to run
    :type seq:            str
    :param quiet:         whether to print only the command output
    :type quiet:          bool
    :param args:          placeholder arguments for this run; to modify
    :type args:           list[str]
    :param ignore_errors: if True, a command error does not stop the run
    :type ignore_errors:  bool
    :param skip_cmdnames: list of command names to not execute
    :type skip_cmdnames:  list[str]

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.item_lock("seq", seq, locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.READ)
    if not quiet:
        print()
    try:
        seq_dict = sequence_impl_core.read_dict(seq)
    except FileNotFoundError:
        shared.errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    cmd_list = seq_dict["commands"]
    locks.multi_item_lock("cmd", cmd_list, locks.LockType.READ)
    locks.release_inventory_lock("cmd", locks.LockType.READ)
    unused_args = copy.deepcopy(args)
    rsv_ctx = command_impl_op.ReservedPlaceholdersCtx()
    req_stdout = req_stdout_flags(cmd_list)
    with tempfile.TemporaryDirectory() as tmpdirname:
        rsv_ctx.tempdir = tmpdirname + os.sep
        for index, cmd in enumerate(cmd_list):
            if skip_cmdnames and cmd in skip_cmdnames:
                print(
                    Fore.MAGENTA
                    + "* SKIPPING command '{}'".format(cmd)
                    + Fore.RESET
                )
                if not quiet:
                    print()
                rsv_ctx.stdout = None
                continue
            rsv_ctx.stdout_requested = req_stdout[index]
            if not quiet:
                print(
                    Fore.MAGENTA
                    + "* running command '{}':".format(cmd)
                    + Fore.RESET
                )
            status = command_impl_op.run(
                cmd, quiet, args, unused_args, rsv_ctx
            )
            if status and not ignore_errors:
                return status
    if unused_args:
        print(
            shared.MSG_WARN_PREFIX
            + " the following args don't apply to any commandline in this"
            " sequence:",
            " ".join(unused_args),
        )
        print()
    return 0


def cli_vals(seq, args, print_after_set):
    """Update placeholder values for all commands in a sequence.

    Acquire the seq item writelock and cmd inventory readlock. Read the
    sequence's command list, then acquire writelocks on those commands and
    release the cmd inventory readlock.

    Delegate to :func:`.command_impl_op.vals` to update each command in the
    list. If any change results from this, and ``print_after_set`` is
    ``True``, then pretty-print the new sequence.

    Finally, print a warning if any of the given placeholder args were
    irrelevant for all of the sequence's commands.

    :param seq:             name of sequence to process
    :type seq:              str
    :param args:            new placeholder value settings
    :type args:             list[str]
    :param print_after_set: whether to automatically trigger "print" operation
                            if any change results
    :type print_after_set:  bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.item_lock("seq", seq, locks.LockType.WRITE)
    locks.inventory_lock("cmd", locks.LockType.READ)
    try:
        seq_dict = sequence_impl_core.read_dict(seq)
    except FileNotFoundError:
        print()
        shared.errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    cmd_list = seq_dict["commands"]
    locks.multi_item_lock("cmd", cmd_list, locks.LockType.WRITE)
    locks.release_inventory_lock("cmd", locks.LockType.READ)
    print()
    unused_args = copy.deepcopy(args)
    print(Fore.MAGENTA + "* updating all commands in sequence" + Fore.RESET)
    print()
    error = False
    any_change = False
    for cmd in cmd_list:
        status = command_impl_op.vals(cmd, args, unused_args, False, True)
        if status:
            error = True
        else:
            any_change = True
    if any_change:
        print("Sequence '{}' updated.".format(seq))
        print()
        if print_after_set:
            command_impl_print.print_multi(cmd_list, False)
    if unused_args:
        print(
            shared.MSG_WARN_PREFIX
            + " the following args don't apply to any commandline in this"
            " sequence:",
            " ".join(unused_args),
        )
        print()
    if error:
        return 1
    return 0
