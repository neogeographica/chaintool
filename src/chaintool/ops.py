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


__all__ = ['handle_cmd_list',
           'handle_cmd_set',
           'handle_cmd_edit',
           'handle_cmd_print',
           'handle_cmd_del',
           'handle_cmd_run',
           'handle_cmd_vals',
           'handle_seq_list',
           'handle_seq_set',
           'handle_seq_edit',
           'handle_seq_print',
           'handle_seq_del',
           'handle_seq_run',
           'handle_seq_vals',
           'handle_print',
           'handle_vals',
           'handle_export',
           'handle_import']


import atexit
import copy
import enum
import os
import re
import readline
import shlex
import string
import subprocess
import sys

import yaml  # from pyyaml

from colorama import Fore

from . import shortcuts
from . import locks
from .constants import DATA_DIR


PLACEHOLDER_DEFAULT_RE = re.compile(r"^([^+][^=]*)=(.*)$")
PLACEHOLDER_TOGGLE_RE = re.compile(r"^(\+[^=]+)=([^:]*):(.*)$")
ALPHANUM_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

CMD_DIR = os.path.join(DATA_DIR, "command")
SEQ_DIR = os.path.join(DATA_DIR, "sequence")

os.makedirs(CMD_DIR, exist_ok=True)
os.makedirs(SEQ_DIR, exist_ok=True)


class PlaceholderArgsPurpose(enum.Enum):
    RUN = 1
    UPDATE = 2


def errprint(msg):
    sys.stderr.write(Fore.RED + msg + Fore.RESET + '\n')


def is_valid_cmdseq_name(n):
    if not n:
        return False
    for c in n:
        if c in string.whitespace:
            return False
    return True


def editline(prompt, oldline):
    def startup_hook():
        readline.insert_text(oldline)
    readline.set_startup_hook(startup_hook)
    # Note that using color codes as part of the prompt will mess up cursor
    # positioning in some edit situations. The solution is probably: put
    # \x01 before any color code and put \x02 after any color code. Haven't
    # tested that though because currently am happy without using colors here.
    newline = input(prompt)
    readline.set_startup_hook()
    return newline


def read_cmd_dict(cmd):
    with open(os.path.join(CMD_DIR, cmd), 'r') as cmd_file:
        cmd_dict = yaml.safe_load(cmd_file)
    return cmd_dict


def write_cmd_doc(cmd, cmd_doc, mode):
    with open(os.path.join(CMD_DIR, cmd), mode) as cmd_file:
        cmd_file.write(cmd_doc)


def read_seq_dict(seq):
    with open(os.path.join(SEQ_DIR, seq), 'r') as seq_file:
        seq_dict = yaml.safe_load(seq_file)
    return seq_dict


def write_seq_doc(seq, seq_doc, mode):
    with open(os.path.join(SEQ_DIR, seq), mode) as seq_file:
        seq_file.write(seq_doc)


def handle_dump_placeholders(commands, is_run):
    placeholders_with_consistent_value = dict()
    other_placeholders_set = set()
    toggles_with_consistent_value = dict()
    other_toggles_set = set()
    for cmd in commands:
        try:
            cmd_dict = read_cmd_dict(cmd)
            for k, v in cmd_dict['args'].items():
                if v is None:
                    other_placeholders_set.add(k)
                else:
                    if k not in other_placeholders_set:
                        if k in placeholders_with_consistent_value:
                            if placeholders_with_consistent_value[k] != v:
                                del placeholders_with_consistent_value[k]
                                other_placeholders_set.add(k)
                        else:
                            placeholders_with_consistent_value[k] = v
            for k, v in cmd_dict['toggle_args'].items():
                if k not in other_toggles_set:
                    if k in toggles_with_consistent_value:
                        if toggles_with_consistent_value[k] != v:
                            del toggles_with_consistent_value[k]
                            other_toggles_set.add(k)
                    else:
                        toggles_with_consistent_value[k] = v
        except FileNotFoundError:
            pass
    for k, v in placeholders_with_consistent_value.items():
        print("{}={}".format(k, v))
    for k in other_placeholders_set:
        print("{}".format(k))
    for k, v in toggles_with_consistent_value.items():
        if is_run:
            print(k)
        else:
            print("{}={}:{}".format(k, v[0], v[1]))
    for k in other_toggles_set:
        if is_run:
            print(k)
        else:
            print("{}=".format(k))
    return 0


def update_values_from_args(values_for_names, togglevalues_for_names, args, unused_args, purpose):
    all_values_keys = list(values_for_names.keys())
    unactivated_toggles = list(togglevalues_for_names.keys())
    for a in args:
        default_match = PLACEHOLDER_DEFAULT_RE.match(a)
        if default_match:
            # Changing a placeholder default is always OK and always handled
            # the same way.
            key = default_match.group(1)
            if key in all_values_keys:
                values_for_names[key] = default_match.group(2)
                if a in unused_args:
                    unused_args.remove(a)
        else:
            # For default-clearing and toggles, we need more smarts.
            toggle_match = PLACEHOLDER_TOGGLE_RE.match(a)
            if purpose == PlaceholderArgsPurpose.RUN:
                if a[0] == '+':
                    if a in togglevalues_for_names:
                        values_for_names[a] = togglevalues_for_names[a][1]
                        if a in unactivated_toggles:
                            unactivated_toggles.remove(a)
                        if a in unused_args:
                            unused_args.remove(a)
                elif toggle_match:
                    errprint(
                        "Can't specify values for 'toggle' style placeholders "
                        "such as '{}' in this operation.".format(toggle_match.group(1)))
                    return False
                else:
                    errprint(
                        "Placeholder '{}' specified in args without a value.".format(a))
                    return False
            else:
                if toggle_match:
                    key = toggle_match.group(1)
                    if key in togglevalues_for_names:
                        togglevalues_for_names[key] = [toggle_match.group(2), toggle_match.group(3)]
                        if a in unused_args:
                            unused_args.remove(a)
                elif a[0] == '+':
                    errprint(
                        "'Toggle' style placeholders such as '{}' require "
                        "accompanying pre/post values in this operation.".format(a))
                    return False
                else:
                    if a in values_for_names:
                        values_for_names[a] = None
                        if a in unused_args:
                            unused_args.remove(a)
    if purpose == PlaceholderArgsPurpose.RUN:
        for key in unactivated_toggles:
            values_for_names[key] = togglevalues_for_names[key][0]
        unspecified = [k for k in all_values_keys if values_for_names[k] is None]
        if unspecified:
            errprint("Not all placeholders in the commandline have been given a value.")
            errprint("Placeholders that still need a value: " + ' '.join(unspecified))
            return False
    return True


def command_with_values(cmd, args, unused_args, purpose):
    try:
        cmd_dict = read_cmd_dict(cmd)
    except FileNotFoundError:
        errprint("Command '{}' does not exist.".format(cmd))
        return None
    values_for_names = cmd_dict['args']
    togglevalues_for_names = cmd_dict['toggle_args']
    if update_values_from_args(values_for_names, togglevalues_for_names, args, unused_args, purpose):
        return cmd_dict
    return None


def process_cmdline(cmdline, handle_placeholder_fun):
    placeholder = ""
    cmdline_format = ""
    prev_undoubled_brace = None
    for c in cmdline:
        c_is_brace = c in ('{', '}')
        if not placeholder:
            if prev_undoubled_brace == '{' and not c_is_brace:
                placeholder = c
            else:
                cmdline_format += c
        else:
            if c == '}' and prev_undoubled_brace != '}':
                cmdline_format += handle_placeholder_fun(placeholder)
                cmdline_format += c
                placeholder = ""
            else:
                placeholder += c
        if c == prev_undoubled_brace:
            prev_undoubled_brace = None
        elif c_is_brace:
            prev_undoubled_brace = c
    return cmdline_format


def update_cmdline(cmd_dict):

    def explode_literal_braces(value):
        return value.replace("{", "{{").replace("}", "}}")

    def handle_placeholder(placeholder):
        toggle_match = PLACEHOLDER_TOGGLE_RE.match(placeholder)
        if toggle_match:
            key = toggle_match.group(1)
            if key not in cmd_dict['toggle_args']:
                # Weird, but we'll handle it.
                return placeholder
            untoggled_value = explode_literal_braces(cmd_dict['toggle_args'][key][0])
            toggled_value = explode_literal_braces(cmd_dict['toggle_args'][key][1])
            return key + "=" + untoggled_value + ":" + toggled_value
        default_match = PLACEHOLDER_DEFAULT_RE.match(placeholder)
        if default_match:
            key = default_match.group(1)
        else:
            key = placeholder
        if key not in cmd_dict['args']:
            # Weird, but we'll handle it.
            return placeholder
        if cmd_dict['args'][key] is None:
            return key
        value = explode_literal_braces(cmd_dict['args'][key])
        return key + "=" + value

    cmd_dict['cmdline'] = process_cmdline(cmd_dict['cmdline'], handle_placeholder)


def handle_cmd_list(column):
    # No locking needed. We just read a directory list and print it.
    print()
    command_names = os.listdir(CMD_DIR)
    if command_names:
        if column:
            print('\n'.join(command_names))
        else:
            print(' '.join(command_names))
        print()
    return 0


def handle_cmd_set(cmd, cmdline, overwrite, print_after_set):
    locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    locks.item_lock("cmd", cmd, locks.LockType.WRITE)
    creating = False
    if os.path.exists(os.path.join(CMD_DIR, cmd)):
        locks.release_inventory_lock("seq", locks.LockType.READ)
    else:
        creating = True
        # Check whether there's a seq of the same name.
        if os.path.exists(os.path.join(SEQ_DIR, cmd)):
            print()
            errprint(
                "Command '{}' cannot be created because a sequence exists with "
                "the same name.".format(cmd))
            print()
            return 1
    status = handle_cmd_set_internal(cmd, cmdline, overwrite, print_after_set, False)
    if creating and not status:
        shortcuts.write_aliases("cmd", os.listdir(CMD_DIR))
    return status


def handle_cmd_set_internal(cmd, cmdline, overwrite, print_after_set, compact):
    if not compact:
        print()
    if not is_valid_cmdseq_name(cmd):
        errprint("cmdname '{}' contains whitespace, which is not allowed.".format(cmd))
        print()
        return 1
    if not cmdline:
        errprint("cmdline must be nonempty.")
        print()
        return 1
    values_for_names = dict()
    togglevalues_for_names = dict()
    non_alphanum_names = set()
    multi_value_names = set()
    multi_togglevalue_names = set()
    toggles_without_values = set()
    toggle_dup_names = set()

    def collapse_literal_braces(value):
        return value.replace("{{", "{").replace("}}", "}")

    def handle_placeholder(placeholder):
        toggle_match = PLACEHOLDER_TOGGLE_RE.match(placeholder)
        if toggle_match:
            key = toggle_match.group(1)
            untoggled_value = collapse_literal_braces(toggle_match.group(2))
            toggled_value = collapse_literal_braces(toggle_match.group(3))
            value = [untoggled_value, toggled_value]
            if not ALPHANUM_RE.match(key[1:]):
                non_alphanum_names.add(key)
            if key[1:] in values_for_names:
                toggle_dup_names.add(key[1:])
            if key in togglevalues_for_names:
                if togglevalues_for_names[key] != value:
                    multi_togglevalue_names.add(key)
            togglevalues_for_names[key] = value
            return key
        default_match = PLACEHOLDER_DEFAULT_RE.match(placeholder)
        if default_match:
            key = default_match.group(1)
            value = collapse_literal_braces(default_match.group(2))
        else:
            key = placeholder
            value = None
            if key[0] == '+':
                if not ALPHANUM_RE.match(key[1:]):
                    non_alphanum_names.add(key)
                toggles_without_values.add(key)
                return placeholder
        if not ALPHANUM_RE.match(key):
            non_alphanum_names.add(key)
        if "+" + key in togglevalues_for_names:
            toggle_dup_names.add(key)
        if key in values_for_names:
            if values_for_names[key] != value:
                multi_value_names.add(key)
        values_for_names[key] = value
        return key

    cmdline_format = process_cmdline(cmdline, handle_placeholder)
    error = False
    if non_alphanum_names:
        error = True
        errprint("Bad placeholder format: " + ' '.join(non_alphanum_names))
        errprint(
            "Placeholder names must begin with a letter and be composed only "
            "of letters, numbers, and underscores.")
        errprint(
            "(Note that this error can also be triggered by syntax mistakes "
            "when trying to specify placeholder default values or toggle values. "
            "Also, if you need a literal brace character to appear in the "
            "commandline, use a double brace.)")
    if multi_value_names:
        error = True
        errprint(
            "Placeholders occurring multiple times but with different "
            "defaults: " + ' '.join(multi_value_names))
    if multi_togglevalue_names:
        error = True
        errprint(
            "'Toggle' placeholders occurring multiple times but with different "
            "values: " + ' '.join(multi_togglevalue_names))
    if toggles_without_values:
        error = True
        errprint(
            "'Toggle' placeholders specified without values: "
            + ' '.join(toggles_without_values))
    if toggle_dup_names:
        error = True
        errprint(
            "Same placeholder name(s) used for both regular and 'toggle' "
            "placeholders: " + ' '.join(toggle_dup_names))
    if error:
        print()
        return 1
    cmd_doc = yaml.dump(
        {
            'cmdline': cmdline,
            'format': cmdline_format,
            'args': values_for_names,
            'toggle_args': togglevalues_for_names
        },
        default_flow_style=False
    )
    if overwrite:
        mode = 'w'
    else:
        mode = 'x'
    try:
        write_cmd_doc(cmd, cmd_doc, mode)
    except FileExistsError:
        print("Command '{}' already exists... not modified.".format(cmd))
        print()
        return 0
    print("Command '{}' set.".format(cmd))
    print()
    if print_after_set:
        handle_cmd_print_internal(cmd)
    return 0


def handle_cmd_edit(cmd, print_after_set):
    locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    locks.item_lock("cmd", cmd, locks.LockType.WRITE)
    cleanup_placeholder_fun = None
    try:
        cmd_dict = read_cmd_dict(cmd)
        old_cmdline = cmd_dict['cmdline']
    except FileNotFoundError:
        # Check whether there's a seq of the same name.
        if os.path.exists(os.path.join(SEQ_DIR, cmd)):
            print()
            errprint(
                "Command '{}' cannot be created because a sequence exists with "
                "the same name.".format(cmd))
            print()
            return 1
        # We want to release the inventory locks before we go into interactive
        # edit. Let's create a placeholder command to edit here, so that any
        # concurrent seq creation will see it when checking for name conflicts.
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
        cleanup_placeholder_fun = lambda: os.remove(os.path.join(CMD_DIR, cmd))
        atexit.register(cleanup_placeholder_fun)
        write_cmd_doc(cmd, cmd_doc, 'w')
    locks.release_inventory_lock("cmd", locks.LockType.WRITE)
    locks.release_inventory_lock("seq", locks.LockType.READ)
    print()
    new_cmdline = editline('commandline: ', old_cmdline)
    status = handle_cmd_set_internal(cmd, new_cmdline, True, print_after_set, False)
    if cleanup_placeholder_fun:
        if status:
            cleanup_placeholder_fun()
        else:
            shortcuts.write_aliases("cmd", os.listdir(CMD_DIR))
        atexit.unregister(cleanup_placeholder_fun)
    return status


def handle_cmd_print(cmd, dump_placeholders):
    # No locking needed. We read a cmd yaml file and format/print it. If
    # the file is being deleted right now that's fine, either we get in
    # before the delete or after.
    if dump_placeholders is not None:
        return handle_dump_placeholders([cmd], dump_placeholders == "run")
    print()
    return handle_cmd_print_internal(cmd)


def handle_cmd_print_internal(cmd):
    try:
        cmd_dict = read_cmd_dict(cmd)
    except FileNotFoundError:
        errprint("Command '{}' does not exist.".format(cmd))
        print()
        return 1
    all_required_placeholders = []
    all_optional_placeholders = []
    for k, v in cmd_dict['args'].items():
        if v is None:
            all_required_placeholders.append(k)
        else:
            all_optional_placeholders.append(k)
    all_toggle_placeholders = list(cmd_dict['toggle_args'].keys())
    print(Fore.MAGENTA + "* commandline format:" + Fore.RESET)
    print(cmd_dict['cmdline'])
    if all_required_placeholders:
        print()
        print(Fore.MAGENTA + "* required values:" + Fore.RESET)
        all_required_placeholders.sort()
        for p in all_required_placeholders:
            print(p)
    if all_optional_placeholders:
        print()
        print(Fore.MAGENTA + "* optional values with default:" + Fore.RESET)
        all_optional_placeholders.sort()
        for p in all_optional_placeholders:
            print("{} = {}".format(p, shlex.quote(cmd_dict['args'][p])))
    if all_toggle_placeholders:
        print()
        print(Fore.MAGENTA + "* toggles with untoggled:toggled values:" + Fore.RESET)
        all_toggle_placeholders.sort()
        for p in all_toggle_placeholders:
            togglevals = cmd_dict['toggle_args'][p]
            print("{} = {}:{}".format(p, shlex.quote(togglevals[0]), shlex.quote(togglevals[1])))
    print()
    return 0


def handle_cmd_del(delcmds, ignore_seq_usage):
    if not ignore_seq_usage:
        locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    locks.multi_item_lock("cmd", delcmds, locks.LockType.WRITE)
    print()
    if not ignore_seq_usage:
        error = False
        sequence_names = os.listdir(SEQ_DIR)
        seq_dicts = []
        for seq in sequence_names:
            try:
                seq_dict = read_seq_dict(seq)
                seq_dict['name'] = seq
                seq_dicts.append(seq_dict)
            except FileNotFoundError:
                pass
        for cmd in delcmds:
            for seq_dict in seq_dicts:
                if cmd in seq_dict['commands']:
                    error = True
                    errprint("Command {} is used by sequence {}.".format(cmd, seq_dict['name']))
        if error:
            print()
            return 1
    any_deleted = False
    for cmd in delcmds:
        try:
            os.remove(os.path.join(CMD_DIR, cmd))
            print("Command '{}' deleted.".format(cmd))
            any_deleted = True
        except FileNotFoundError:
            print("Command '{}' does not exist.".format(cmd))
    print()
    if any_deleted:
        shortcuts.write_aliases("cmd", os.listdir(CMD_DIR))
    return 0


def handle_cmd_run(cmd, args):
    # Arguably there's no locking needed here. But in the seq run case we
    # do keep cmds locked until the run is over, so it's good to be consistent.
    # Also it's not too surprising that we would block deleting a cmd while
    # it is running.
    locks.item_lock("cmd", cmd, locks.LockType.READ)
    unused_args = copy.deepcopy(args)
    status = handle_cmd_run_internal(cmd, args, unused_args)
    if unused_args:
        print(
            Fore.YELLOW
            + "Warning:"
            + Fore.RESET
            + " the following args don't apply to this commandline:",
            ' '.join(unused_args))
        print()
    return status


def handle_cmd_run_internal(cmd, args, unused_args):
    print()
    cmd_dict = command_with_values(cmd, args, unused_args, PlaceholderArgsPurpose.RUN)
    if cmd_dict is None:
        print()
        return 1
    cmdline = cmd_dict['format'].format(**cmd_dict['args'])
    print(Fore.CYAN + cmdline + Fore.RESET)
    print()
    status = subprocess.call(cmdline, shell=True)
    print()
    return status


def handle_cmd_vals(cmd, args, print_after_set):
    locks.item_lock("cmd", cmd, locks.LockType.WRITE)
    unused_args = copy.deepcopy(args)
    status = handle_cmd_vals_internal(cmd, args, unused_args, print_after_set, False)
    if status:
        return status
    if unused_args:
        print(
            Fore.YELLOW
            + "Warning:"
            + Fore.RESET
            + " the following args don't apply to this commandline:",
            ' '.join(unused_args))
        print()
    return 0


def handle_cmd_vals_internal(cmd, args, unused_args, print_after_set, compact):
    if not compact:
        print()
    cmd_dict = command_with_values(cmd, args, unused_args, PlaceholderArgsPurpose.UPDATE)
    if cmd_dict is None:
        return 1
    update_cmdline(cmd_dict)
    cmd_doc = yaml.dump(
        cmd_dict,
        default_flow_style=False
    )
    write_cmd_doc(cmd, cmd_doc, 'w')
    print("Command '{}' updated.".format(cmd))
    print()
    if print_after_set:
        handle_cmd_print_internal(cmd)
    return 0


def handle_seq_list(column):
    # No locking needed. We just read a directory list and print it.
    print()
    sequence_names = os.listdir(SEQ_DIR)
    if sequence_names:
        if column:
            print('\n'.join(sequence_names))
        else:
            print(' '.join(sequence_names))
        print()
    return 0


def handle_seq_set(seq, cmds, ignore_missing_cmds, overwrite, print_after_set):
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.item_lock("seq", seq, locks.LockType.WRITE)
    creating = False
    if not os.path.exists(os.path.join(SEQ_DIR, seq)):
        creating = True
        # Check whether there's a cmd of the same name.
        locks.inventory_lock("cmd", locks.LockType.READ)
        if os.path.exists(os.path.join(CMD_DIR, seq)):
            print()
            errprint(
                "Sequence '{}' cannot be created because a command exists with "
                "the same name.".format(seq))
            print()
            return 1
    # If ignore_missing_cmds is true then we will need the cmd inventory lock
    # to check that out, whether or not we acquired it above. That lock will
    # be (re)acquired later inside handle_seq_set_internal. That lock is done
    # late because in the edit case we don't want to hold it while the
    # interactive edit is going on.
    status = handle_seq_set_internal(seq, cmds, ignore_missing_cmds, overwrite, print_after_set, False)
    if creating and not status:
        shortcuts.write_aliases("seq", os.listdir(SEQ_DIR))
    return status


def handle_seq_set_internal(seq, cmds, ignore_missing_cmds, overwrite, print_after_set, compact):
    if not compact:
        print()
    if not is_valid_cmdseq_name(seq):
        errprint("seqname '{}' contains whitespace, which is not allowed.".format(seq))
        print()
        return 1
    if not cmds:
        errprint("At least one cmdname is required.")
        print()
        return 1
    for c in cmds:
        if not is_valid_cmdseq_name(c):
            errprint("cmdname '{}' contains whitespace, which is not allowed.".format(c))
            print()
            return 1
    if not ignore_missing_cmds:
        locks.inventory_lock("cmd", locks.LockType.READ)
        command_names = os.listdir(CMD_DIR)
        invalid_cmds = set(cmds) - set(command_names)
        if invalid_cmds:
            errprint("Nonexistent command(s): " + ' '.join(invalid_cmds))
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
        write_seq_doc(seq, seq_doc, mode)
    except FileExistsError:
        print("Sequence '{}' already exists... not modified.".format(seq))
        print()
        return 0
    print("Sequence '{}' set.".format(seq))
    print()
    if print_after_set:
        handle_multi_cmd_print_internal(cmds)
    return 0


def handle_seq_edit(seq, ignore_missing_cmds, print_after_set):
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.item_lock("seq", seq, locks.LockType.WRITE)
    cleanup_placeholder_fun = None
    try:
        seq_dict = read_seq_dict(seq)
        old_commands_str = ' '.join(seq_dict['commands'])
    except FileNotFoundError:
        # Check whether there's a cmd of the same name.
        locks.inventory_lock("cmd", locks.LockType.READ)
        if os.path.exists(os.path.join(CMD_DIR, seq)):
            print()
            errprint(
                "Sequence '{}' cannot be created because a command exists with "
                "the same name.".format(seq))
            print()
            return 1
        # We want to release the inventory locks before we go into interactive
        # edit. Let's create a placeholder sequence to edit here, so that any
        # concurrent cmd creation will see it when checking for name conflicts.
        seq_doc = yaml.dump(
            {
                'commands': []
            },
            default_flow_style=False
        )
        old_commands_str = ""
        cleanup_placeholder_fun = lambda: os.remove(os.path.join(SEQ_DIR, seq))
        atexit.register(cleanup_placeholder_fun)
        write_seq_doc(seq, seq_doc, 'w')
        locks.release_inventory_lock("cmd", locks.LockType.READ)
    locks.release_inventory_lock("seq", locks.LockType.WRITE)
    print()
    new_commands_str = editline('commands: ', old_commands_str)
    new_commands = new_commands_str.split()
    # If ignore_missing_cmds is true then we will need the cmd-type lock to
    # check that out later; but we'll acquire that inside
    # handle_seq_set_internal. That lock is done late because in the edit case
    # we don't want to hold it while the interactive edit is going on.
    status = handle_seq_set_internal(seq, new_commands, ignore_missing_cmds, True, print_after_set, False)
    if cleanup_placeholder_fun:
        if status:
            cleanup_placeholder_fun()
        else:
            shortcuts.write_aliases("seq", os.listdir(SEQ_DIR))
        atexit.unregister(cleanup_placeholder_fun)
    return status


def handle_multi_cmd_print_internal(commands):
    command_dicts = []
    command_dicts_by_cmd = dict()
    all_required_placeholders_set = set()
    all_optional_placeholders_set = set()
    all_toggle_placeholders_set = set()
    commands_by_placeholder = dict()
    commands_display = ""
    for cmd in commands:
        try:
            cmd_dict = read_cmd_dict(cmd)
            commands_display += " " + cmd
            cmd_dict['name'] = cmd
            command_dicts.append(cmd_dict)
            command_dicts_by_cmd[cmd] = cmd_dict

            def record_placeholder(p):
                if p in commands_by_placeholder:
                    commands_by_placeholder[p].append(cmd)
                else:
                    commands_by_placeholder[p] = [cmd]

            for k, v in cmd_dict['args'].items():
                record_placeholder(k)
                if v is None:
                    all_required_placeholders_set.add(k)
                else:
                    all_optional_placeholders_set.add(k)
            for k in cmd_dict['toggle_args'].keys():
                record_placeholder(k)
                all_toggle_placeholders_set.add(k)
        except FileNotFoundError:
            commands_display += " " + Fore.RED + cmd + Fore.RESET
    print(Fore.MAGENTA + "** commands:" + Fore.RESET)
    print(commands_display)
    print()
    print(Fore.MAGENTA + "** commandline formats:" + Fore.RESET)
    for d in command_dicts:
        print(Fore.CYAN + "* " + d['name'] + Fore.RESET)
        print(d['cmdline'])
    # This sort function aims to list bigger command-groups first; and among
    # command-groups of the same size, order them by how early their first
    # command appears in the sequence.
    num_commands = len(commands)

    def cga_sort_keyvalue(cga):
        group = cga[0]
        return (
            num_commands
            * len(group)
            + (num_commands - commands.index(group[0]) - 1)
        )

    def print_command_groups(argset):
        cmd_group_args = []
        for a in argset:
            cmd_group = commands_by_placeholder[a]
            update_checker = []

            def args_updater(oldargs):
                oldargs.append(a)
                update_checker.append(True)
                return oldargs

            cmd_group_args = [
                (group, args_updater(args)) if group == cmd_group else (group, args)
                for (group, args) in cmd_group_args]
            if not update_checker:
                newentry = (cmd_group, [a])
                cmd_group_args.append(newentry)
        cmd_group_args.sort(key=cga_sort_keyvalue, reverse=True)
        for group, args in cmd_group_args:
            print(Fore.CYAN + "* " + ', '.join(group) + Fore.RESET)
            args.sort()
            first_cmd = group[0]
            for a in args:
                format_str = "{} = "
                format_args = [a]
                args_dict = None
                if a in command_dicts_by_cmd[first_cmd]['args']:
                    if command_dicts_by_cmd[first_cmd]['args'][a] is not None:
                        args_dict = 'args'
                        common_format_str = "{} = {}"
                else:
                    args_dict = 'toggle_args'
                    common_format_str = "{} = {}:{}"
                if args_dict is not None:
                    has_common_value = True
                    first_value = command_dicts_by_cmd[first_cmd][args_dict][a]

                    def format_parts(v, c):
                        if args_dict == 'args':
                            return ("{} ({})", [shlex.quote(v), c])
                        v0 = shlex.quote(v[0])
                        v1 = shlex.quote(v[1])
                        return ("{}:{} ({})", [v0, v1, c])
                    (format_suffix, added_args) = format_parts(first_value, first_cmd)
                    format_str += format_suffix
                    format_args += added_args
                    for cmd in group[1:]:
                        this_value = command_dicts_by_cmd[cmd][args_dict][a]
                        if this_value is None:
                            has_common_value = False
                            format_str = "{}"
                            format_args = [a]
                            break
                        (format_suffix, added_args) = format_parts(this_value, cmd)
                        format_str += ", " + format_suffix
                        format_args += added_args
                        if this_value != first_value:
                            has_common_value = False
                    if has_common_value:
                        format_str = common_format_str

                print(format_str.format(*format_args))

    if all_required_placeholders_set:
        print()
        print(Fore.MAGENTA + "** required values:" + Fore.RESET)
        print_command_groups(all_required_placeholders_set)
    if all_optional_placeholders_set:
        print()
        print(Fore.MAGENTA + "** optional values with default:" + Fore.RESET)
        print_command_groups(all_optional_placeholders_set)
    if all_toggle_placeholders_set:
        print()
        print(Fore.MAGENTA + "** toggles with untoggled:toggled values:" + Fore.RESET)
        print_command_groups(all_toggle_placeholders_set)
    print()
    return 0


def handle_seq_print(seq, dump_placeholders):
    # We're going to skip locking if dump_placeholders is set. That's an
    # internal/hidden flag used only for bash completion, and in the vanishingly
    # small chance that something gets changed/deleted while a bash completion
    # is being calculated, that's fine. Not worth incurring the extra work if
    # someone is hitting TAB a lot on the command line.
    if dump_placeholders is None:
        locks.item_lock("seq", seq, locks.LockType.READ)
        locks.inventory_lock("cmd", locks.LockType.READ)
    try:
        seq_dict = read_seq_dict(seq)
    except FileNotFoundError:
        if dump_placeholders is None:
            print()
            errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    commands = seq_dict['commands']
    if dump_placeholders is None:
        locks.multi_item_lock("cmd", commands, locks.LockType.READ)
        locks.release_inventory_lock("cmd", locks.LockType.READ)
    if dump_placeholders is not None:
        return handle_dump_placeholders(commands, dump_placeholders == "run")
    print()
    return handle_multi_cmd_print_internal(commands)


def handle_seq_del(delseqs):
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.multi_item_lock("seq", delseqs, locks.LockType.WRITE)
    print()
    any_deleted = False
    for seq in delseqs:
        try:
            os.remove(os.path.join(SEQ_DIR, seq))
            print("Sequence '{}' deleted.".format(seq))
            any_deleted = True
        except FileNotFoundError:
            print("Sequence '{}' does not exist.".format(seq))
    print()
    if any_deleted:
        shortcuts.write_aliases("seq", os.listdir(SEQ_DIR))
    return 0


def handle_seq_run(seq, args, ignore_errors, skip_cmdnames):
    locks.item_lock("seq", seq, locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.READ)
    print()
    try:
        seq_dict = read_seq_dict(seq)
    except FileNotFoundError:
        errprint("Sequence '{}' does not exist.".format(seq))
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
        status = handle_cmd_run_internal(cmd, args, unused_args)
        if status and not ignore_errors:
            return status
    if unused_args:
        print(
            Fore.YELLOW
            + "Warning:"
            + Fore.RESET
            + " the following args don't apply to any commandline "
            "in this sequence:",
            ' '.join(unused_args))
        print()
    return 0


def handle_seq_vals(seq, args, print_after_set):
    locks.item_lock("seq", seq, locks.LockType.WRITE)
    locks.inventory_lock("cmd", locks.LockType.READ)
    try:
        seq_dict = read_seq_dict(seq)
    except FileNotFoundError:
        print()
        errprint("Sequence '{}' does not exist.".format(seq))
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
        status = handle_cmd_vals_internal(cmd, args, unused_args, False, True)
        if status:
            error = True
        else:
            any_change = True
    if any_change:
        print("Sequence '{}' updated.".format(seq))
        print()
        if print_after_set:
            handle_multi_cmd_print_internal(cmd_list)
    if unused_args:
        print(
            Fore.YELLOW
            + "Warning:"
            + Fore.RESET
            + " the following args don't apply to any commandline "
            "in this sequence:",
            ' '.join(unused_args))
        print()
    if error:
        return 1
    return 0


def handle_print(dump_placeholders):
    if dump_placeholders is None:
        locks.inventory_lock("cmd", locks.LockType.READ)
    command_names = os.listdir(CMD_DIR)
    if dump_placeholders is None:
        locks.multi_item_lock("cmd", command_names, locks.LockType.READ)
    else:
        return handle_dump_placeholders(command_names, dump_placeholders == "run")
    print()
    return handle_multi_cmd_print_internal(command_names)


def handle_vals(placeholder_args):
    locks.inventory_lock("cmd", locks.LockType.READ)
    command_names = os.listdir(CMD_DIR)
    locks.multi_item_lock("cmd", command_names, locks.LockType.WRITE)
    print()
    unused_args = copy.deepcopy(placeholder_args)
    print(Fore.MAGENTA + "* updating all commands" + Fore.RESET)
    print()
    error = False
    for cmd in command_names:
        status = handle_cmd_vals_internal(cmd, placeholder_args, unused_args, False, True)
        if status:
            error = True
    if unused_args:
        print(
            Fore.YELLOW
            + "Warning:"
            + Fore.RESET
            + " the following args don't apply to any commandline:",
            ' '.join(unused_args))
        print()
    if error:
        return 1
    return 0


def handle_export(export_file):
    locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.READ)
    command_names = os.listdir(CMD_DIR)
    sequence_names = os.listdir(SEQ_DIR)
    locks.multi_item_lock("cmd", command_names, locks.LockType.READ)
    locks.multi_item_lock("seq", sequence_names, locks.LockType.READ)
    print()
    export_dict = {
        'commands': [],
        'sequences': []
    }
    print(Fore.MAGENTA + "* Exporting commands..." + Fore.RESET)
    print()
    for cmd in command_names:
        try:
            cmd_dict = read_cmd_dict(cmd)
            export_dict['commands'].append(
                {
                    'name': cmd,
                    'cmdline': cmd_dict['cmdline']
                }
            )
            print("Command '{}' exported.".format(cmd))
        except FileNotFoundError:
            print("Failed to read command '{}' ... skipped.".format(cmd))
        print()
    print(Fore.MAGENTA + "* Exporting sequences..." + Fore.RESET)
    print()
    for seq in sequence_names:
        try:
            seq_dict = read_seq_dict(seq)
            export_dict['sequences'].append(
                {
                    'name': seq,
                    'commands': seq_dict['commands']
                }
            )
            print("Sequence '{}' exported.".format(seq))
        except FileNotFoundError:
            print("Failed to read sequence '{}' ... skipped.".format(seq))
        print()
    export_doc = yaml.dump(
        export_dict,
        default_flow_style=False
    )
    with open(export_file, 'w') as outfile:
        outfile.write(export_doc)
    return 0


def handle_import(import_file, overwrite):
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    if overwrite:
        command_names = os.listdir(CMD_DIR)
        sequence_names = os.listdir(SEQ_DIR)
        locks.multi_item_lock("cmd", command_names, locks.LockType.WRITE)
        locks.multi_item_lock("seq", sequence_names, locks.LockType.WRITE)
    print()
    with open(import_file, 'r') as infile:
        import_dict = yaml.safe_load(infile)
    print(Fore.MAGENTA + "* Importing commands..." + Fore.RESET)
    print()
    for cmd_dict in import_dict['commands']:
        handle_cmd_set_internal(cmd_dict['name'], cmd_dict['cmdline'], overwrite, False, True)
    print(Fore.MAGENTA + "* Importing sequences..." + Fore.RESET)
    print()
    for seq_dict in import_dict['sequences']:
        handle_seq_set_internal(seq_dict['name'], seq_dict['commands'], True, overwrite, False, True)
    new_command_names = os.listdir(CMD_DIR)
    new_sequence_names = os.listdir(SEQ_DIR)
    shortcuts.write_all_aliases(new_command_names, new_sequence_names)
    return 0
