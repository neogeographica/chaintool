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


__all__ = ['init',
           'exists',
           'all_names',
           'read_dict',
           'write_doc',
           'dump_placeholders',
           'define',
           'delete',
           'run',
           'vals',
           'print_one',
           'print_multi']


import enum
import os
import re
import shlex
import subprocess

import yaml  # from pyyaml

from colorama import Fore

from . import shared
from .constants import DATA_DIR


PLACEHOLDER_DEFAULT_RE = re.compile(r"^([^+][^=]*)=(.*)$")
PLACEHOLDER_TOGGLE_RE = re.compile(r"^(\+[^=]+)=([^:]*):(.*)$")
ALPHANUM_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

CMD_DIR = os.path.join(DATA_DIR, "commands")


def init():
    os.makedirs(CMD_DIR, exist_ok=True)


class PlaceholderArgsPurpose(enum.Enum):
    RUN = 1
    UPDATE = 2


def remove_if_present(element_to_remove, list_in):
    if element_to_remove in list_in:
        list_in.remove(element_to_remove)


def explode_literal_braces(value):
    return value.replace("{", "{{").replace("}", "}}")


def collapse_literal_braces(value):
    return value.replace("{{", "{").replace("}}", "}")


def update_runtime_values_from_args(
        values_for_names,
        togglevalues_for_names,
        all_args,
        unused_args):
    valid_non_toggles = list(values_for_names.keys())
    unactivated_toggles = list(togglevalues_for_names.keys())
    for arg in all_args:
        default_match = PLACEHOLDER_DEFAULT_RE.match(arg)
        if default_match:
            key = default_match.group(1)
            if key in valid_non_toggles:
                values_for_names[key] = default_match.group(2)
                remove_if_present(arg, unused_args)
        else:
            toggle_match = PLACEHOLDER_TOGGLE_RE.match(arg)
            if arg[0] == '+':
                if arg in togglevalues_for_names:
                    values_for_names[arg] = togglevalues_for_names[arg][1]
                    remove_if_present(arg, unactivated_toggles)
                    remove_if_present(arg, unused_args)
            elif toggle_match:
                shared.errprint(
                    "Can't specify values for 'toggle' style placeholders "
                    "such as '{}' in this operation.".format(toggle_match.group(1)))
                return False
            else:
                shared.errprint(
                    "Placeholder '{}' specified in args without a value.".format(arg))
                return False
    for key in unactivated_toggles:
        values_for_names[key] = togglevalues_for_names[key][0]
    unspecified = [k for k in valid_non_toggles if values_for_names[k] is None]
    if unspecified:
        shared.errprint("Not all placeholders in the commandline have been given a value.")
        shared.errprint("Placeholders that still need a value: " + ' '.join(unspecified))
        return False
    return True


def update_default_values_from_args(
        values_for_names,
        togglevalues_for_names,
        all_args,
        unused_args):
    valid_non_toggles = list(values_for_names.keys())
    for arg in all_args:
        default_match = PLACEHOLDER_DEFAULT_RE.match(arg)
        if default_match:
            key = default_match.group(1)
            if key in valid_non_toggles:
                values_for_names[key] = default_match.group(2)
                remove_if_present(arg, unused_args)
        else:
            toggle_match = PLACEHOLDER_TOGGLE_RE.match(arg)
            if toggle_match:
                key = toggle_match.group(1)
                if key in togglevalues_for_names:
                    togglevalues_for_names[key] = [toggle_match.group(2), toggle_match.group(3)]
                    remove_if_present(arg, unused_args)
            elif arg[0] == '+':
                shared.errprint(
                    "'Toggle' style placeholders such as '{}' require "
                    "accompanying pre/post values in this operation.".format(arg))
                return False
            else:
                if arg in values_for_names:
                    values_for_names[arg] = None
                    remove_if_present(arg, unused_args)
    return True


def command_with_values(cmd, all_args, unused_args, purpose):
    try:
        cmd_dict = read_dict(cmd)
    except FileNotFoundError:
        shared.errprint("Command '{}' does not exist.".format(cmd))
        return None
    values_for_names = cmd_dict['args']
    togglevalues_for_names = cmd_dict['toggle_args']
    if purpose == PlaceholderArgsPurpose.RUN:
        update_success = update_runtime_values_from_args(
            values_for_names, togglevalues_for_names, all_args, unused_args)
    else:
        update_success = update_default_values_from_args(
            values_for_names, togglevalues_for_names, all_args, unused_args)
    if update_success:
        return cmd_dict
    return None


def process_cmdline(cmdline, handle_placeholder_fun):
    placeholder = ""
    cmdline_format = ""
    prev_undoubled_brace = None
    for char in cmdline:
        char_is_brace = char in ('{', '}')
        if not placeholder:
            if prev_undoubled_brace == '{' and not char_is_brace:
                placeholder = char
            else:
                cmdline_format += char
        else:
            if char == '}' and prev_undoubled_brace != '}':
                cmdline_format += handle_placeholder_fun(placeholder)
                cmdline_format += char
                placeholder = ""
            else:
                placeholder += char
        if char == prev_undoubled_brace:
            prev_undoubled_brace = None
        elif char_is_brace:
            prev_undoubled_brace = char
    return cmdline_format


def handle_update_placeholder(placeholder, args_dict, toggle_args_dict):
    toggle_match = PLACEHOLDER_TOGGLE_RE.match(placeholder)
    if toggle_match:
        key = toggle_match.group(1)
        if key not in toggle_args_dict:
            # Weird, but we'll handle it.
            return placeholder
        untoggled_value = explode_literal_braces(toggle_args_dict[key][0])
        toggled_value = explode_literal_braces(toggle_args_dict[key][1])
        return key + "=" + untoggled_value + ":" + toggled_value
    default_match = PLACEHOLDER_DEFAULT_RE.match(placeholder)
    if default_match:
        key = default_match.group(1)
    else:
        key = placeholder
    if key not in args_dict:
        # Weird, but we'll handle it.
        return placeholder
    if args_dict[key] is None:
        return key
    value = explode_literal_braces(args_dict[key])
    return key + "=" + value


def update_cmdline(cmd_dict):

    def handle_update_placeholder_wrapper(placeholder):
        return handle_update_placeholder(
            placeholder, cmd_dict['args'], cmd_dict['toggle_args'])

    cmd_dict['cmdline'] = process_cmdline(
        cmd_dict['cmdline'],
        handle_update_placeholder_wrapper
    )


def exists(cmd):
    return os.path.exists(os.path.join(CMD_DIR, cmd))


def all_names():
    return os.listdir(CMD_DIR)


def read_dict(cmd):
    with open(os.path.join(CMD_DIR, cmd), 'r') as cmd_file:
        cmd_dict = yaml.safe_load(cmd_file)
    return cmd_dict


def write_doc(cmd, cmd_doc, mode):
    with open(os.path.join(CMD_DIR, cmd), mode) as cmd_file:
        cmd_file.write(cmd_doc)


def update_placeholders_collections(k, v, consistent_values_dict, other_set):
    if k in other_set:
        return
    if v is None:
        other_set.add(k)
        return
    if k not in consistent_values_dict:
        consistent_values_dict[k] = v
        return
    if consistent_values_dict[k] != v:
        del consistent_values_dict[k]
        other_set.add(k)


def dump_placeholders(commands, is_run):
    placeholders_with_consistent_value = dict()
    other_placeholders_set = set()
    toggles_with_consistent_value = dict()
    other_toggles_set = set()
    for cmd in commands:
        try:
            cmd_dict = read_dict(cmd)
            for k, v in cmd_dict['args'].items():
                update_placeholders_collections(
                    k,
                    v,
                    placeholders_with_consistent_value,
                    other_placeholders_set)
            for k, v in cmd_dict['toggle_args'].items():
                update_placeholders_collections(
                    k,
                    v,
                    toggles_with_consistent_value,
                    other_toggles_set)
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


def print_errors(error_sets):
    error = False
    if error_sets["non_alphanum_names"]:
        error = True
        shared.errprint(
            "Bad placeholder format: " + ' '.join(error_sets["non_alphanum_names"]))
        shared.errprint(
            "Placeholder names must begin with a letter and be composed only "
            "of letters, numbers, and underscores.")
        shared.errprint(
            "(Note that this error can also be triggered by syntax mistakes "
            "when trying to specify placeholder default values or toggle values. "
            "Also, if you need a literal brace character to appear in the "
            "commandline, use a double brace.)")
    if error_sets["multi_value_names"]:
        error = True
        shared.errprint(
            "Placeholders occurring multiple times but with different "
            "defaults: " + ' '.join(error_sets["multi_value_names"]))
    if error_sets["multi_togglevalue_names"]:
        error = True
        shared.errprint(
            "'Toggle' placeholders occurring multiple times but with different "
            "values: " + ' '.join(error_sets["multi_togglevalue_names"]))
    if error_sets["toggles_without_values"]:
        error = True
        shared.errprint(
            "'Toggle' placeholders specified without values: "
            + ' '.join(error_sets["toggles_without_values"]))
    if error_sets["toggle_dup_names"]:
        error = True
        shared.errprint(
            "Same placeholder name(s) used for both regular and 'toggle' "
            "placeholders: " + ' '.join(error_sets["toggle_dup_names"]))
    return error


def check_toggle_errors(
        key,
        value,
        values_for_names,
        togglevalues_for_names,
        error_sets):
    if not ALPHANUM_RE.match(key[1:]):
        error_sets["non_alphanum_names"].add(key)
    if key[1:] in values_for_names:
        error_sets["toggle_dup_names"].add(key[1:])
    if key is not None:
        if key in togglevalues_for_names:
            if togglevalues_for_names[key] != value:
                error_sets["multi_togglevalue_names"].add(key)
    else:
        error_sets["toggles_without_values"].add(key)


def check_placeholder_errors(
        key,
        value,
        values_for_names,
        togglevalues_for_names,
        error_sets):
    if key[0] == '+':
        check_toggle_errors(
            key, value, values_for_names, togglevalues_for_names, error_sets)
        return
    if not ALPHANUM_RE.match(key):
        error_sets["non_alphanum_names"].add(key)
    if "+" + key in togglevalues_for_names:
        error_sets["toggle_dup_names"].add(key)
    if key in values_for_names:
        if values_for_names[key] != value:
            error_sets["multi_value_names"].add(key)


def handle_set_placeholder(
        placeholder,
        values_for_names,
        togglevalues_for_names,
        error_sets):
    toggle_match = PLACEHOLDER_TOGGLE_RE.match(placeholder)
    if toggle_match:
        key = toggle_match.group(1)
        untoggled_value = collapse_literal_braces(toggle_match.group(2))
        toggled_value = collapse_literal_braces(toggle_match.group(3))
        value = [untoggled_value, toggled_value]
        check_toggle_errors(
            key, value, values_for_names, togglevalues_for_names, error_sets)
        togglevalues_for_names[key] = value
        return key
    default_match = PLACEHOLDER_DEFAULT_RE.match(placeholder)
    if default_match:
        key = default_match.group(1)
        value = collapse_literal_braces(default_match.group(2))
    else:
        key = placeholder
        value = None
    check_placeholder_errors(
        key, value, values_for_names, togglevalues_for_names, error_sets)
    values_for_names[key] = value
    return key


def define(cmd, cmdline, overwrite, print_after_set, compact):
    if not compact:
        print()
    if not shared.is_valid_name(cmd):
        shared.errprint("cmdname '{}' contains whitespace, which is not allowed.".format(cmd))
        print()
        return 1
    if not cmdline:
        shared.errprint("cmdline must be nonempty.")
        print()
        return 1
    values_for_names = dict()
    togglevalues_for_names = dict()
    error_sets = {
        "non_alphanum_names": set(),
        "multi_value_names": set(),
        "multi_togglevalue_names": set(),
        "toggles_without_values": set(),
        "toggle_dup_names": set()
    }

    def handle_set_placeholder_wrapper(placeholder):
        return handle_set_placeholder(
            placeholder, values_for_names, togglevalues_for_names, error_sets)

    cmdline_format = process_cmdline(cmdline, handle_set_placeholder_wrapper)
    if print_errors(error_sets):
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
        write_doc(cmd, cmd_doc, mode)
    except FileExistsError:
        print("Command '{}' already exists... not modified.".format(cmd))
        print()
        return 0
    print("Command '{}' set.".format(cmd))
    print()
    if print_after_set:
        print_one(cmd)
    return 0


def delete(cmd, is_not_found_ok):
    try:
        os.remove(os.path.join(CMD_DIR, cmd))
    except FileNotFoundError:
        if not is_not_found_ok:
            raise


def run(cmd, args, unused_args):
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


def vals(cmd, args, unused_args, print_after_set, compact):
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
    write_doc(cmd, cmd_doc, 'w')
    print("Command '{}' updated.".format(cmd))
    print()
    if print_after_set:
        print_one(cmd)
    return 0


def print_one(cmd):
    try:
        cmd_dict = read_dict(cmd)
    except FileNotFoundError:
        shared.errprint("Command '{}' does not exist.".format(cmd))
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


def init_print_info_collections(
        commands,
        command_dicts,
        command_dicts_by_cmd,
        commands_by_placeholder,
        placeholders_sets):

    def record_placeholder(cmd, placeholder):
        if placeholder in commands_by_placeholder:
            commands_by_placeholder[placeholder].append(cmd)
        else:
            commands_by_placeholder[placeholder] = [cmd]

    commands_display = ""
    for cmd in commands:
        try:
            cmd_dict = read_dict(cmd)
            commands_display += " " + cmd
            cmd_dict['name'] = cmd
            command_dicts.append(cmd_dict)
            command_dicts_by_cmd[cmd] = cmd_dict
            for k, v in cmd_dict['args'].items():
                record_placeholder(cmd, k)
                if v is None:
                    placeholders_sets["required"].add(k)
                else:
                    placeholders_sets["optional"].add(k)
            for k in cmd_dict['toggle_args'].keys():
                record_placeholder(cmd, k)
                placeholders_sets["toggle"].add(k)
        except FileNotFoundError:
            commands_display += " " + Fore.RED + cmd + Fore.RESET
    return commands_display


def print_command_groups(cmd_group_args, command_dicts_by_cmd):

    def format_parts(v, c):
        if isinstance(v, str):
            return ("{} ({})", [shlex.quote(v), c])
        return ("{}:{} ({})", [shlex.quote(v[0]), shlex.quote(v[1]), c])

    for group, args in cmd_group_args:
        print(Fore.CYAN + "* " + ', '.join(group) + Fore.RESET)
        args.sort()
        first_cmd = group[0]
        for a in args:
            format_str = "{} = "
            format_args = [a]
            args_dict_name = None
            if a in command_dicts_by_cmd[first_cmd]['args']:
                if command_dicts_by_cmd[first_cmd]['args'][a] is not None:
                    args_dict_name = 'args'
                    common_format_str = "{} = {}"
            else:
                args_dict_name = 'toggle_args'
                common_format_str = "{} = {}:{}"
            if args_dict_name is not None:
                has_common_value = True
                first_value = command_dicts_by_cmd[first_cmd][args_dict_name][a]
                (format_suffix, added_args) = format_parts(first_value, first_cmd)
                format_str += format_suffix
                format_args += added_args
                for cmd in group[1:]:
                    this_value = command_dicts_by_cmd[cmd][args_dict_name][a]
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


def print_placeholders_set(
        placeholders_set,
        sortfunc,
        command_dicts_by_cmd,
        commands_by_placeholder):

    def args_updater(arg, oldargs, update_checker):
        oldargs.append(arg)
        update_checker.append(True)
        return oldargs

    cmd_group_args = []
    for arg in placeholders_set:
        cmd_group = commands_by_placeholder[arg]
        update_checker = []
        cmd_group_args = [
            (group, args_updater(arg, group_args, update_checker))
            if group == cmd_group else (group, group_args)
            for (group, group_args) in cmd_group_args]
        if not update_checker:
            newentry = (cmd_group, [arg])
            cmd_group_args.append(newentry)
    cmd_group_args.sort(key=sortfunc, reverse=True)
    print_command_groups(cmd_group_args, command_dicts_by_cmd)


def print_multi(commands):
    num_commands = len(commands)
    command_dicts = []
    command_dicts_by_cmd = dict()
    commands_by_placeholder = dict()
    placeholders_sets = {
        "required": set(),
        "optional": set(),
        "toggle": set()
    }
    commands_display = init_print_info_collections(
        commands,
        command_dicts,
        command_dicts_by_cmd,
        commands_by_placeholder,
        placeholders_sets)

    # This sort function aims to list bigger command-groups first; and among
    # command-groups of the same size, order them by how early their first
    # command appears in the sequence.
    def cga_sort_keyvalue(cmd_group_args):
        group = cmd_group_args[0]
        return (
            num_commands
            * len(group)
            + (num_commands - commands.index(group[0]) - 1)
        )

    print(Fore.MAGENTA + "** commands:" + Fore.RESET)
    print(commands_display)
    print()
    print(Fore.MAGENTA + "** commandline formats:" + Fore.RESET)
    for d in command_dicts:
        print(Fore.CYAN + "* " + d['name'] + Fore.RESET)
        print(d['cmdline'])
    if placeholders_sets["required"]:
        print()
        print(Fore.MAGENTA + "** required values:" + Fore.RESET)
        print_placeholders_set(
            placeholders_sets["required"],
            cga_sort_keyvalue,
            command_dicts_by_cmd,
            commands_by_placeholder)
    if placeholders_sets["optional"]:
        print()
        print(Fore.MAGENTA + "** optional values with default:" + Fore.RESET)
        print_placeholders_set(
            placeholders_sets["optional"],
            cga_sort_keyvalue,
            command_dicts_by_cmd,
            commands_by_placeholder)
    if placeholders_sets["toggle"]:
        print()
        print(Fore.MAGENTA + "** toggles with untoggled:toggled values:" + Fore.RESET)
        print_placeholders_set(
            placeholders_sets["toggle"],
            cga_sort_keyvalue,
            command_dicts_by_cmd,
            commands_by_placeholder)
    print()
    return 0
