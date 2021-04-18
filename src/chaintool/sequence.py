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


__all__ = ['cli_list',
           'cli_set',
           'cli_edit',
           'cli_print',
           'cli_del',
           'cli_run',
           'cli_vals']


import atexit
import copy

import yaml  # from pyyaml

from colorama import Fore

from . import command_impl
from . import completions
from . import constants
from . import sequence_impl
from . import shared
from . import shortcuts
from . import locks


def cli_list(column):
    # No locking needed. We just read a directory list and print it.
    print()
    sequence_names = sequence_impl.all_names()
    if sequence_names:
        if column:
            print('\n'.join(sequence_names))
        else:
            print(' '.join(sequence_names))
        print()
    return 0


def cli_set(seq, cmds, ignore_missing_cmds, overwrite, print_after_set):
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.item_lock("seq", seq, locks.LockType.WRITE)
    creating = False
    if not sequence_impl.exists(seq):
        creating = True
        # Check whether there's a cmd of the same name.
        locks.inventory_lock("cmd", locks.LockType.READ)
        if command_impl.exists(seq):
            print()
            shared.errprint(
                "Sequence '{}' cannot be created because a command exists with "
                "the same name.".format(seq))
            print()
            return 1
    # If ignore_missing_cmds is true then we will need the cmd inventory lock
    # to check that out, whether or not we acquired it above. That lock will
    # be (re)acquired later inside sequence_impl.define. That lock is done
    # late because in the edit case we don't want to hold it while the
    # interactive edit is going on.
    status = sequence_impl.define(seq, cmds, ignore_missing_cmds, overwrite, print_after_set, False)
    if creating and not status:
        shortcuts.create_seq_shortcut(seq)
        completions.create_completion(seq)
    return status


def cli_edit(seq, ignore_missing_cmds, print_after_set):
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.item_lock("seq", seq, locks.LockType.WRITE)
    cleanup_placeholder_fun = None
    try:
        seq_dict = sequence_impl.read_dict(seq)
        old_commands_str = ' '.join(seq_dict['commands'])
    except FileNotFoundError:
        # Check whether there's a cmd of the same name.
        locks.inventory_lock("cmd", locks.LockType.READ)
        if command_impl.exists(seq):
            print()
            shared.errprint(
                "Sequence '{}' cannot be created because a command exists with "
                "the same name.".format(seq))
            print()
            return 1
        # We want to release the inventory locks before we go into interactive
        # edit. Let's create a placeholder sequence to edit here, so that any
        # concurrent cmd creation will see it when checking for name conflicts.
        # XXX Should move this into impl somehow so this module doesn't need
        # to know about doc structure.
        seq_doc = yaml.dump(
            {
                'commands': []
            },
            default_flow_style=False
        )
        old_commands_str = ""
        cleanup_placeholder_fun = lambda: sequence_impl.delete(seq, True)
        atexit.register(cleanup_placeholder_fun)
        sequence_impl.write_doc(seq, seq_doc, 'w')
        locks.release_inventory_lock("cmd", locks.LockType.READ)
    locks.release_inventory_lock("seq", locks.LockType.WRITE)
    print()
    new_commands_str = shared.editline('commands: ', old_commands_str)
    new_commands = new_commands_str.split()
    # If ignore_missing_cmds is true then we will need the cmd-type lock to
    # check that out later; but we'll acquire that inside sequence_impl.define.
    # That lock is done late because in the edit case we don't want to hold it
    # while the interactive edit is going on.
    status = sequence_impl.define(seq, new_commands, ignore_missing_cmds, True, print_after_set, False)
    if cleanup_placeholder_fun:
        if status:
            cleanup_placeholder_fun()
        else:
            shortcuts.create_seq_shortcut(seq)
            completions.create_completion(seq)
        atexit.unregister(cleanup_placeholder_fun)
    return status


def cli_print(seq, dump_placeholders):
    # We're going to skip locking if dump_placeholders is set. That's an
    # internal/hidden flag used only for bash completion, and in the vanishingly
    # small chance that something gets changed/deleted while a bash completion
    # is being calculated, that's fine. Not worth incurring the extra work if
    # someone is hitting TAB a lot on the command line.
    if dump_placeholders is None:
        locks.item_lock("seq", seq, locks.LockType.READ)
        locks.inventory_lock("cmd", locks.LockType.READ)
    try:
        seq_dict = sequence_impl.read_dict(seq)
    except FileNotFoundError:
        if dump_placeholders is None:
            print()
            shared.errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    commands = seq_dict['commands']
    if dump_placeholders is None:
        locks.multi_item_lock("cmd", commands, locks.LockType.READ)
        locks.release_inventory_lock("cmd", locks.LockType.READ)
    if dump_placeholders is not None:
        return command_impl.dump_placeholders(commands, dump_placeholders == "run")
    print()
    return command_impl.print_multi(commands)


def cli_del(delseqs):
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.multi_item_lock("seq", delseqs, locks.LockType.WRITE)
    print()
    for seq in delseqs:
        try:
            sequence_impl.delete(seq, False)
            print("Sequence '{}' deleted.".format(seq))
            shortcuts.delete_seq_shortcut(seq)
            completions.delete_completion(seq)
        except FileNotFoundError:
            print("Sequence '{}' does not exist.".format(seq))
    print()
    return 0


def cli_run(seq, args, ignore_errors, skip_cmdnames):
    locks.item_lock("seq", seq, locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.READ)
    print()
    try:
        seq_dict = sequence_impl.read_dict(seq)
    except FileNotFoundError:
        shared.errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    cmd_list = seq_dict['commands']
    locks.multi_item_lock("cmd", cmd_list, locks.LockType.READ)
    locks.release_inventory_lock("cmd", locks.LockType.READ)
    unused_args = copy.deepcopy(args)
    for cmd in cmd_list:
        if skip_cmdnames and cmd in skip_cmdnames:
            print(Fore.MAGENTA + "* SKIPPING command '{}'".format(cmd) + Fore.RESET)
            print()
            continue
        print(Fore.MAGENTA + "* running command '{}':".format(cmd) + Fore.RESET)
        status = command_impl.run(cmd, args, unused_args)
        if status and not ignore_errors:
            return status
    if unused_args:
        print(
            constants.MSG_WARN_PREFIX
            + " the following args don't apply to any commandline "
            "in this sequence:",
            ' '.join(unused_args))
        print()
    return 0


def cli_vals(seq, args, print_after_set):
    locks.item_lock("seq", seq, locks.LockType.WRITE)
    locks.inventory_lock("cmd", locks.LockType.READ)
    try:
        seq_dict = sequence_impl.read_dict(seq)
    except FileNotFoundError:
        print()
        shared.errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    cmd_list = seq_dict['commands']
    locks.multi_item_lock("cmd", cmd_list, locks.LockType.WRITE)
    locks.release_inventory_lock("cmd", locks.LockType.READ)
    print()
    unused_args = copy.deepcopy(args)
    print(Fore.MAGENTA + "* updating all commands in sequence" + Fore.RESET)
    print()
    error = False
    any_change = False
    for cmd in cmd_list:
        status = command_impl.vals(cmd, args, unused_args, False, True)
        if status:
            error = True
        else:
            any_change = True
    if any_change:
        print("Sequence '{}' updated.".format(seq))
        print()
        if print_after_set:
            command_impl.print_multi(cmd_list)
    if unused_args:
        print(
            constants.MSG_WARN_PREFIX
            + " the following args don't apply to any commandline "
            "in this sequence:",
            ' '.join(unused_args))
        print()
    if error:
        return 1
    return 0