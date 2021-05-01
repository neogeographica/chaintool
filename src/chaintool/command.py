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

"""Top-level logic for "cmd" operations.

Called from cli module. Handles locking and shortcuts/completions; delegates
to command_impl_* modules for most of the work.

Note that most locks acquired here are released only when the program exits.
Operations are meant to be invoked one per program instance, using the CLI.

"""


__all__ = [
    "cli_list",
    "cli_set",
    "cli_edit",
    "cli_print",
    "cli_print_all",
    "cli_del",
    "cli_run",
    "cli_vals",
    "cli_vals_all",
]


import atexit
import copy

from colorama import Fore

from . import command_impl_core
from . import command_impl_op
from . import command_impl_print
from . import completions
from . import sequence_impl
from . import shared
from . import shortcuts
from . import locks


def cli_list(column):
    """Print the list of current command names.

    No locking needed. Just read a directory list and print it.

    :param column: if True, print as one command name per line
    :type column:  bool

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    print()
    command_names = command_impl_core.all_names()
    if command_names:
        if column:
            print("\n".join(command_names))
        else:
            print(" ".join(command_names))
        print()
    return 0


def cli_set(cmd, cmdline, overwrite, print_after_set):
    """Create or update a command to consist of the given commandline.

    Acquire the seq inventory readlock, the cmd inventory writelock, and
    the cmd item writelock. If we're creating a new command, check to see
    whether a sequence of this same name already exists (reject if so).

    Delegate to :func:`.command_impl_op.define` to create/update the command.

    Finally: if we successfully created a new command, set up its shortcut
    (:func:`.shortcuts.create_cmd_shortcut`) and autocompletion behavior
    (:func:`.completions.create_completion`).

    :param cmd:             name of command to create/update
    :type cmd:              str
    :param cmdline:         commandline
    :type cmdline:          str
    :param overwrite:       whether to allow if command already exists
    :type overwrite:        bool
    :param print_after_set: whether to automatically trigger "print" operation
                            at the end
    :type print_after_set:  bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    locks.item_lock("cmd", cmd, locks.LockType.WRITE)
    creating = False
    if not command_impl_core.exists(cmd):
        creating = True
        if sequence_impl.exists(cmd):
            print()
            shared.errprint(
                "Command '{}' cannot be created because a sequence exists with"
                " the same name.".format(cmd)
            )
            print()
            return 1
    status = command_impl_op.define(
        cmd, cmdline, overwrite, print_after_set, False
    )
    if creating and not status:
        shortcuts.create_cmd_shortcut(cmd)
        completions.create_completion(cmd)
    return status


def cli_edit(cmd, print_after_set):
    """Interactively create or update a command.

    Acquire the seq inventory readlock, the cmd inventory writelock, and
    the cmd item writelock. Read the current command's commandline (if it
    exists).

    If we're creating a new command, check to see whether a sequence of this
    same name already exists (reject if so). Then create a temporary empty
    command that we can edit.

    Release the inventory locks and let the user interactively edit any
    existing commandline. The delegate to :func:`.command_impl_op.define` to
    create/update the command.

    Finally: if we successfully created a new command, set up its shortcut
    (:func:`.shortcuts.create_cmd_shortcut`) and autocompletion behavior
    (:func:`.completions.create_completion`).

    :param cmd:             name of command to create/update
    :type cmd:              str
    :param print_after_set: whether to automatically trigger "print" operation
                            at the end
    :type print_after_set:  bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    locks.item_lock("cmd", cmd, locks.LockType.WRITE)
    cleanup_fun = None
    try:
        cmd_dict = command_impl_core.read_dict(cmd)
        old_cmdline = cmd_dict["cmdline"]
    except FileNotFoundError:
        # Check whether there's a seq of the same name.
        if sequence_impl.exists(cmd):
            print()
            shared.errprint(
                "Command '{}' cannot be created because a sequence exists with"
                " the same name.".format(cmd)
            )
            print()
            return 1
        # We want to release the inventory locks before we go into interactive
        # edit. Creating a temp/empty command to edit here makes that safe to
        # do; any concurrent seq creation will see it when checking for name
        # conflicts.
        old_cmdline = ""
        cleanup_fun = lambda: command_impl_op.delete(cmd, True)
        atexit.register(cleanup_fun)
        command_impl_core.create_temp(cmd)
    locks.release_inventory_lock("cmd", locks.LockType.WRITE)
    locks.release_inventory_lock("seq", locks.LockType.READ)
    print()
    new_cmdline = shared.editline("commandline: ", old_cmdline)
    status = command_impl_op.define(
        cmd, new_cmdline, True, print_after_set, False
    )
    if cleanup_fun:
        if status:
            # Make sure we don't leave the temp/empty command laying around
            # in the error case.
            cleanup_fun()
        else:
            shortcuts.create_cmd_shortcut(cmd)
            completions.create_completion(cmd)
        atexit.unregister(cleanup_fun)
    return status


def cli_print(cmd, dump_placeholders):
    """Pretty-print the info for a command.

    If ``dump_placeholders`` is not ``None``, delegate to
    :func:`.command_impl_print.dump_placeholders`. (This is not a user-facing
    option; it is used for generating argument completions.)

    Otherwise delegate to :func:`.command_impl_print.print_one`.

    :param cmd:               name of command to print
    :type cmd:                str
    :param dump_placeholders: whether to print in a "rawer" format, and
                              without locking (used internally)
    :type dump_placeholders:  "run" | "vals" | None

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    # No locking needed. We read a cmd yaml file and format/print it. If
    # the file is being deleted right now that's fine, either we get in
    # before the delete or after.
    if dump_placeholders is not None:
        return command_impl_print.dump_placeholders(
            [cmd], dump_placeholders == "run"
        )
    print()
    return command_impl_print.print_one(cmd)


def cli_print_all(dump_placeholders):
    """Pretty-print the info for all commands.

    If ``dump_placeholders`` is not ``None``, get the list of all commands
    (without locking) and delegate to
    :func:`.command_impl_print.dump_placeholders`. (This is not a user-facing
    option; it is used for generating argument completions.)

    Otherwise:

    Acquire the cmd inventory readlock and get the list of all commands.
    Readlock those commands and delegate to
    :func:`.command_impl_print.print_multi` to pretty-print the info for that
    list of commands.

    :param dump_placeholders: whether to print in a "rawer" format, and
                              without locking (used internally)
    :type dump_placeholders:  "run" | "vals" | None

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    if dump_placeholders is None:
        locks.inventory_lock("cmd", locks.LockType.READ)
    command_names = command_impl_core.all_names()
    if dump_placeholders is None:
        locks.multi_item_lock("cmd", command_names, locks.LockType.READ)
    else:
        return command_impl_print.dump_placeholders(
            command_names, dump_placeholders == "run"
        )
    print()
    return command_impl_print.print_multi(command_names, True)


def cli_del(delcmds, ignore_seq_usage):
    """Delete one or more commands.

    If ``ignore_seq_usage`` is ``False``, acquire the seq inventory readlock
    and item readlocks on all sequences.

    Acquire the cmd inventory writelock and item writelocks on the commands
    to delete.

    If ``ignore_seq_usage`` is False, check all the given commands to make
    sure that they are not currently contained in any sequence (reject if so).

    Delete each command (via :func:`.command_impl_op.delete`), and tear down
    its shortcut (:func:`.shortcuts.delete_cmd_shortcut`) and autocompletion
    behavior (:func:`.completions.delete_completion`).

    :param delcmds:          names of commands to delete
    :type delcmds:           list[str]
    :param ignore_seq_usage: if True, don't validate that commands are unused
                             by current sequences
    :type ignore_seq_usage:  bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    if not ignore_seq_usage:
        locks.inventory_lock("seq", locks.LockType.READ)
        sequence_names = sequence_impl.all_names()
        locks.multi_item_lock("seq", sequence_names, locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    locks.multi_item_lock("cmd", delcmds, locks.LockType.WRITE)
    print()
    if not ignore_seq_usage:
        error = False
        seq_dicts = []
        for seq in sequence_names:
            try:
                seq_dict = sequence_impl.read_dict(seq)
            except FileNotFoundError:
                continue
            seq_dict["name"] = seq
            seq_dicts.append(seq_dict)
        for cmd in delcmds:
            for seq_dict in seq_dicts:
                if cmd in seq_dict["commands"]:
                    error = True
                    shared.errprint(
                        "Command {} is used by sequence {}.".format(
                            cmd, seq_dict["name"]
                        )
                    )
        if error:
            print()
            return 1
    for cmd in delcmds:
        try:
            command_impl_op.delete(cmd, False)
        except FileNotFoundError:
            print("Command '{}' does not exist.".format(cmd))
            continue
        print("Command '{}' deleted.".format(cmd))
        shortcuts.delete_cmd_shortcut(cmd)
        completions.delete_completion(cmd)
    print()
    return 0


def cli_run(cmd, args):
    """Run a command.

    Acquire the cmd item readlock. Delegate to :func:`.command_impl_op.run` to
    execute the command. Finally, print a warning if any of the given
    placeholder args were irrelevant for this command.

    Note that :func:`.command_impl_op.run` may modify ``args`` (for use with
    subsequent commands in the sequence).

    :param cmd:           name of command to run
    :type cmd:            str
    :param args:          placeholder arguments for this run; to modify
    :type args:           list[str]

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    # Arguably there's no locking needed here. But in the seq run case we
    # do keep cmds locked until the run is over, so it's good to be consistent.
    # Also it's not too surprising that we would block editing or deleting a
    # cmd while it is running.
    locks.item_lock("cmd", cmd, locks.LockType.READ)
    unused_args = copy.deepcopy(args)
    status = command_impl_op.run(cmd, args, unused_args)
    if unused_args:
        print(
            shared.MSG_WARN_PREFIX
            + " the following args don't apply to this commandline:",
            " ".join(unused_args),
        )
        print()
    return status


def cli_vals(cmd, args, print_after_set):
    """Update placeholder values for a command.

    Acquire the cmd item writelock. Delegate to :func:`.command_impl_op.vals`
    to update this command. Finally, print a warning if any of the given
    placeholder args were irrelevant for this command.

    :param cmd:             name of command to update
    :type cmd:              str
    :param args:            new placeholder value settings
    :type args:             list[str]
    :param print_after_set: whether to automatically trigger "print" operation
                            at the end
    :type print_after_set:  bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.item_lock("cmd", cmd, locks.LockType.WRITE)
    unused_args = copy.deepcopy(args)
    status = command_impl_op.vals(
        cmd, args, unused_args, print_after_set, False
    )
    if status:
        return status
    if unused_args:
        print(
            shared.MSG_WARN_PREFIX
            + " the following args don't apply to this commandline:",
            " ".join(unused_args),
        )
        print()
    return 0


def cli_vals_all(placeholder_args):
    """Update placeholder values for all commands.

    Acquire the cmd inventory readlock and get the list of all commands.
    Writelock those commands and delegate to :func:`.command_impl_op.vals`
    to update each command. Finally, print a warning if any of the given
    placeholder args were irrelevant for all commands.

    :param cmd:             name of command to update
    :type cmd:              str
    :param args:            new placeholder value settings
    :type args:             list[str]
    :param print_after_set: whether to automatically trigger "print" operation
                            at the end
    :type print_after_set:  bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    locks.inventory_lock("cmd", locks.LockType.READ)
    command_names = command_impl_core.all_names()
    locks.multi_item_lock("cmd", command_names, locks.LockType.WRITE)
    print()
    unused_args = copy.deepcopy(placeholder_args)
    print(Fore.MAGENTA + "* updating all commands" + Fore.RESET)
    print()
    error = False
    for cmd in command_names:
        status = command_impl_op.vals(
            cmd, placeholder_args, unused_args, False, True
        )
        if status:
            error = True
    if unused_args:
        print(
            shared.MSG_WARN_PREFIX
            + " the following args don't apply to any commandline:",
            " ".join(unused_args),
        )
        print()
    if error:
        return 1
    return 0
