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
           'cli_print_all',
           'cli_del',
           'cli_run',
           'cli_vals',
           'cli_vals_all']


import atexit
import copy

import yaml  # from pyyaml

from colorama import Fore

from . import command_impl
from . import constants
from . import sequence_impl
from . import shared
from . import shortcuts
from . import locks


def cli_list(column):
    # No locking needed. We just read a directory list and print it.
    print()
    command_names = command_impl.all_names()
    if command_names:
        if column:
            print('\n'.join(command_names))
        else:
            print(' '.join(command_names))
        print()
    return 0


def cli_set(cmd, cmdline, overwrite, print_after_set):
    locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    locks.item_lock("cmd", cmd, locks.LockType.WRITE)
    creating = False
    if command_impl.exists(cmd):
        locks.release_inventory_lock("seq", locks.LockType.READ)
    else:
        creating = True
        # Check whether there's a seq of the same name.
        if sequence_impl.exists(cmd):
            print()
            shared.errprint(
                "Command '{}' cannot be created because a sequence exists with "
                "the same name.".format(cmd))
            print()
            return 1
    status = command_impl.define(cmd, cmdline, overwrite, print_after_set, False)
    if creating and not status:
        shortcuts.create_cmd_shortcut(cmd)
    return status


def cli_edit(cmd, print_after_set):
    locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    locks.item_lock("cmd", cmd, locks.LockType.WRITE)
    cleanup_placeholder_fun = None
    try:
        cmd_dict = command_impl.read_dict(cmd)
        old_cmdline = cmd_dict['cmdline']
    except FileNotFoundError:
        # Check whether there's a seq of the same name.
        if sequence_impl.exists(cmd):
            print()
            shared.errprint(
                "Command '{}' cannot be created because a sequence exists with "
                "the same name.".format(cmd))
            print()
            return 1
        # We want to release the inventory locks before we go into interactive
        # edit. Let's create a placeholder command to edit here, so that any
        # concurrent seq creation will see it when checking for name conflicts.
        # XXX Should move this into impl somehow so this module doesn't need
        # to know about doc structure.
        cmd_doc = yaml.dump(
            {
                'cmdline': "",
                'format': "",
                'args': dict(),
                'toggle_args': dict()
            },
            default_flow_style=False
        )
        old_cmdline = ""
        cleanup_placeholder_fun = lambda: command_impl.delete(cmd, True)
        atexit.register(cleanup_placeholder_fun)
        command_impl.write_doc(cmd, cmd_doc, 'w')
    locks.release_inventory_lock("cmd", locks.LockType.WRITE)
    locks.release_inventory_lock("seq", locks.LockType.READ)
    print()
    new_cmdline = shared.editline('commandline: ', old_cmdline)
    status = command_impl.define(cmd, new_cmdline, True, print_after_set, False)
    if cleanup_placeholder_fun:
        if status:
            cleanup_placeholder_fun()
        else:
            shortcuts.create_cmd_shortcut(cmd)
        atexit.unregister(cleanup_placeholder_fun)
    return status


def cli_print(cmd, dump_placeholders):
    # No locking needed. We read a cmd yaml file and format/print it. If
    # the file is being deleted right now that's fine, either we get in
    # before the delete or after.
    if dump_placeholders is not None:
        return command_impl.dump_placeholders([cmd], dump_placeholders == "run")
    print()
    return command_impl.print_one(cmd)


def cli_print_all(dump_placeholders):
    if dump_placeholders is None:
        locks.inventory_lock("cmd", locks.LockType.READ)
    command_names = command_impl.all_names()
    if dump_placeholders is None:
        locks.multi_item_lock("cmd", command_names, locks.LockType.READ)
    else:
        return command_impl.dump_placeholders(command_names, dump_placeholders == "run")
    print()
    return command_impl.print_multi(command_names)


def cli_del(delcmds, ignore_seq_usage):
    if not ignore_seq_usage:
        locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    locks.multi_item_lock("cmd", delcmds, locks.LockType.WRITE)
    print()
    if not ignore_seq_usage:
        error = False
        sequence_names = sequence_impl.all_names()
        seq_dicts = []
        for seq in sequence_names:
            try:
                seq_dict = sequence_impl.read_dict(seq)
                seq_dict['name'] = seq
                seq_dicts.append(seq_dict)
            except FileNotFoundError:
                pass
        for cmd in delcmds:
            for seq_dict in seq_dicts:
                if cmd in seq_dict['commands']:
                    error = True
                    shared.errprint("Command {} is used by sequence {}.".format(cmd, seq_dict['name']))
        if error:
            print()
            return 1
    for cmd in delcmds:
        try:
            command_impl.delete(cmd, False)
            print("Command '{}' deleted.".format(cmd))
            shortcuts.delete_cmd_shortcut(cmd)
        except FileNotFoundError:
            print("Command '{}' does not exist.".format(cmd))
    print()
    return 0


def cli_run(cmd, args):
    # Arguably there's no locking needed here. But in the seq run case we
    # do keep cmds locked until the run is over, so it's good to be consistent.
    # Also it's not too surprising that we would block deleting a cmd while
    # it is running.
    locks.item_lock("cmd", cmd, locks.LockType.READ)
    unused_args = copy.deepcopy(args)
    status = command_impl.run(cmd, args, unused_args)
    if unused_args:
        print(
            constants.MSG_WARN_PREFIX
            + " the following args don't apply to this commandline:",
            ' '.join(unused_args))
        print()
    return status


def cli_vals(cmd, args, print_after_set):
    locks.item_lock("cmd", cmd, locks.LockType.WRITE)
    unused_args = copy.deepcopy(args)
    status = command_impl.vals(cmd, args, unused_args, print_after_set, False)
    if status:
        return status
    if unused_args:
        print(
            constants.MSG_WARN_PREFIX
            + " the following args don't apply to this commandline:",
            ' '.join(unused_args))
        print()
    return 0


def cli_vals_all(placeholder_args):
    locks.inventory_lock("cmd", locks.LockType.READ)
    command_names = command_impl.all_names()
    locks.multi_item_lock("cmd", command_names, locks.LockType.WRITE)
    print()
    unused_args = copy.deepcopy(placeholder_args)
    print(Fore.MAGENTA + "* updating all commands" + Fore.RESET)
    print()
    error = False
    for cmd in command_names:
        status = command_impl.vals(cmd, placeholder_args, unused_args, False, True)
        if status:
            error = True
    if unused_args:
        print(
            constants.MSG_WARN_PREFIX
            + " the following args don't apply to any commandline:",
            ' '.join(unused_args))
        print()
    if error:
        return 1
    return 0
