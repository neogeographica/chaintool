#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2021 Joel Baxter
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Compose and run sequences of commandlines with tweakable parameters.

Originally designed for managing the sequences of "compile" commands needed
to transform Quake 1/2/3 .map files into .bsp files.

More description TBD.
"""

import argparse
import atexit
import copy
import enum
import errno
import glob
import os
import re
import readline
import shlex
import string
import subprocess
import sys
import time

# Five nonstandard modules required
import appdirs
import colorama
import filelock
import psutil
import yaml # from pyyaml

from colorama import Fore

# We need at least Python 3.7; current long pole is the ability to require
# a subcommand in the argparse definitions.
if sys.version_info < (3, 7):
    sys.stderr.write("Python version 3.7 or later is required.\n")
    sys.exit(1)

class PlaceholderArgsPurpose(enum.Enum):
    RUN = 1
    UPDATE = 2

class LockType(enum.Enum):
    READ = "read"
    WRITE = "write"

PLACEHOLDER_DEFAULT_RE = re.compile("^([^+][^=]*)=(.*)$")
PLACEHOLDER_TOGGLE_RE = re.compile("^(\+[^=]+)=([^:]*):(.*)$")
ALPHANUM_RE = re.compile("^[a-zA-Z][a-zA-Z0-9_]*$")

APP_NAME = "chaintool"
APP_AUTHOR = "Joel Baxter"
CONFIG_DIR = appdirs.user_config_dir(APP_NAME, APP_AUTHOR)
CMD_DIR = os.path.join(CONFIG_DIR, "command")
SEQ_DIR = os.path.join(CONFIG_DIR, "sequence")
DATA_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
LOCKS_DIR = os.path.join(DATA_DIR, "locks")

ALIASES_FILE = os.path.join(CONFIG_DIR, "aliases")
META_LOCK = filelock.FileLock(os.path.join(DATA_DIR, "metalock"))
LOCKS_PREFIX = os.path.join(LOCKS_DIR, "")

MY_PID = str(os.getpid())


class SubparsersHelpAction(argparse.Action):
    def __init__(self, option_strings, dest, help=None, subparsers=[]):
        self.subparsers = subparsers
        super(SubparsersHelpAction, self).__init__(
            option_strings=option_strings,
            dest=argparse.SUPPRESS,
            default=argparse.SUPPRESS,
            nargs=0,
            help=help)
    def __call__(self, parser, namespace, values, option_string=None):
        cut_prefix = os.path.basename(sys.argv[0]) + ' '
        print()
        for p in self.subparsers:
            desc = p.prog
            if desc.startswith(cut_prefix):
                desc = desc[len(cut_prefix):]
            print(Fore.MAGENTA + "* '{}' help:".format(desc) + Fore.RESET)
            print()
            p.print_help()
            print()
        parser.exit()

def errprint(msg):
    sys.stderr.write(Fore.RED + msg + Fore.RESET + '\n')

def write_alias_for_item(outstream, chaintool_path, item_type, item_name):
    alias_str = "{} {} run {}".format(
        shlex.quote(chaintool_path), item_type, item_name)
    outstream.write("alias {}={}\n".format(
        item_name, shlex.quote(alias_str)))
    outstream.write(
        "type _chaintool_op_alias > /dev/null 2>&1 && "
        "complete -F _chaintool_op_alias {}\n".format(item_name))

def write_aliases(item_type, nag=True):
    cmd_aliases_file = ALIASES_FILE + "-cmd"
    seq_aliases_file = ALIASES_FILE + "-seq"
    if not os.path.exists(ALIASES_FILE):
        with open(ALIASES_FILE, 'w') as main_file:
            main_file.write("export CHAINTOOL_ALIASES_NO_NAG=1\n")
            main_file.write("[[ -f {0} ]] && source {0}\n".format(
                shlex.quote(cmd_aliases_file)))
            main_file.write("[[ -f {0} ]] && source {0}\n".format(
                shlex.quote(seq_aliases_file)))
    chaintool_path = os.path.abspath(sys.argv[0])
    if item_type == "cmd":
        item_names = os.listdir(CMD_DIR)
        outfile = cmd_aliases_file
    else:
        item_names = os.listdir(SEQ_DIR)
        outfile = seq_aliases_file
    with open(outfile, 'w') as outstream:
        for name in item_names:
            write_alias_for_item(outstream, chaintool_path, item_type, name)
    if nag and "CHAINTOOL_ALIASES_NO_NAG" not in os.environ:
        print(
            "chaintool aliases updated. You can make these aliases available by putting the\n"
            "following line into your .bashrc file:")
        print("  source " + shlex.quote(ALIASES_FILE))
        print()
        if "CHAINTOOL_BASH_COMPLETIONS" not in os.environ:
            print(
                "If you want bash completion support, the chaintool-bash-completion file must be\n"
                "sourced BEFORE that aliases file.")
            print()
        print(
            "If you'd rather not worry about any of this and instead just want to disable\n"
            "this message, you can do so with:")
        print("  export CHAINTOOL_ALIASES_NO_NAG=1")
        print()

def write_all_aliases():
    write_aliases("cmd", False)
    write_aliases("seq", True)

def locker_pid(lock_path):
    return int(lock_path[lock_path.rindex('.') + 1:])

def remove_lock(lock_path):
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        pass

def remove_dead_locks(lock_paths):
    current_pids = psutil.pids()
    for path in lock_paths:
        if locker_pid(path) not in current_pids:
            remove_lock(path)

# This simple R/W lock implementation does not enforce all the guardrails
# necessary to prevent deadlock. Because its usage is pretty simple in this
# program, we just have to follow conventions to avoid deadlock (knock on
# wood). The conventions are:
# * lock acquisition order: seq inventory, seq item, cmd inventory, cmd item
# * for holding multiple item locks, acquire in sorted item name order (this
#    is actually enforced as long as you use multi_item_lock to do it)

def lock_internal(lock_type, prefix):
    if lock_type == LockType.WRITE:
        conflict_pattern = prefix + ".*"
    else:
        conflict_pattern = '.'.join([prefix, LockType.WRITE.value, "*"])
    first_try = True
    while True:
        with META_LOCK:
            conflicting_locks = glob.glob(conflict_pattern)
            conflicting_locks = [l for l in conflicting_locks if locker_pid(l) != MY_PID]
            if not conflicting_locks:
                lock_path = '.'.join([prefix, lock_type.value, MY_PID])
                atexit.register(remove_lock, lock_path) 
                with open(lock_path, 'w'):
                    pass
                return
            remove_dead_locks(conflicting_locks)
        if not first_try:
            print("waiting on other chaintool process...")
            time.sleep(5)
        else:
            first_try = False

# Acquire WRITE inventory lock to create or delete item-of-type.
# Other create/delete for item-of-type is prevented during WRITE or READ lock.

def inventory_lock(item_type, lock_type):
    prefix = LOCKS_PREFIX + "inventory-" + item_type
    lock_internal(lock_type, prefix)

def release_inventory_lock(item_type, lock_type):
    prefix = LOCKS_PREFIX + "inventory-" + item_type
    lock_path = '.'.join([prefix, lock_type.value, MY_PID])
    remove_lock(lock_path)

# Acquire WRITE item lock to create, delete,or modify an item.
# Other create/delete/modify for that item is prevented during WRITE or READ lock.

def item_lock(item_type, item_name, lock_type):
    prefix = LOCKS_PREFIX + item_type + "-" + item_name
    lock_internal(lock_type, prefix)

def multi_item_lock(item_type, item_name_list, lock_type):
    items = copy.deepcopy(item_name_list)
    items.sort()
    for i in items:
        item_lock(item_type, i, lock_type)

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

def set_cmd_options(group_subparsers):
    group_parser_cmd = group_subparsers.add_parser(
        "cmd",
        add_help=False,
        help="Work with saved commandlines.",
        description="Work with saved commandlines.")
    cmd_subparsers = group_parser_cmd.add_subparsers(
        title="operations",
        dest="operation",
        required=True)
    cmd_parser_list = cmd_subparsers.add_parser(
        "list",
        help="List current commandline names.",
        description="List current commandline names.")
    cmd_parser_list.add_argument(
        "-c", "--column",
        action="store_true",
        help="Single-column format.")
    cmd_parser_set = cmd_subparsers.add_parser(
        "set",
        help="Create or update a named commandline.",
        description="Create or update a named commandline.")
    cmd_parser_set.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Don't display info about the resulting commandline.")
    cmd_parser_set.add_argument(
        "cmdname")
    cmd_parser_set.add_argument(
        "cmdline",
        help="Entire commandline as one argument (will probably need to be "
        "quoted). This string may include named placeholders in Python style, "
        "e.g. {placeholdername}. Such a placeholder may also include a default "
        "value string e.g. {placeholdername=2}. 'Toggle' style placeholders "
        "can also be specified, of the form {defval:+togglename:newval}. That "
        "example defines a location that will normally be the string 'defval' "
        "but can be toggled to be 'newval' instead.")
    cmd_parser_edit = cmd_subparsers.add_parser(
        "edit",
        help="Interactively edit a new or existing commandline.",
        description="Interactively edit a new or existing commandline.")
    cmd_parser_edit.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Don't display info about the resulting commandline.")
    cmd_parser_edit.add_argument(
        "cmdname")
    cmd_parser_print = cmd_subparsers.add_parser(
        "print",
        help="Display a commandline and its placeholders/defaults.",
        description="Display a commandline and its placeholders/defaults.")
    cmd_parser_print.add_argument(
        "--dump-placeholders",
        choices=["run", "vals"],
        dest="dump_placeholders",
        help=argparse.SUPPRESS)
    cmd_parser_print.add_argument(
        "cmdname")
    cmd_parser_del = cmd_subparsers.add_parser(
        "del",
        help="Delete one or more commandlines.",
        description="Delete one or more commandlines.")
    cmd_parser_del.add_argument(
        "-f", "--force",
        action="store_true",
        help="Allow deletion of commandlines currently used by sequences.")
    cmd_parser_del.add_argument(
        "cmdnames",
        nargs='+',
        metavar="cmdname",
        help="Commandline to delete. Requires that this commandline currently NOT "
        "be used by any sequence, unless the optional --force argument is specified.")
    cmd_parser_run = cmd_subparsers.add_parser(
        "run",
        help="Execute a commandline, optionally setting values for placeholders.",
        description="Execute a commandline, optionally setting values for placeholders.")
    cmd_parser_run.add_argument(
        "cmdname")
    cmd_parser_run.add_argument(
        "placeholder_args",
        nargs='*',
        metavar="placeholder_arg",
        help="Each of these items can either specify a value for a placeholder "
        "(overriding any default) or activate a 'toggle' style placeholder. A "
        "value for a 'normal' placeholder is specified with an argument of the "
        "form placeholdername=value, while a toggle is activated just by "
        "specifying +togglename.")
    cmd_parser_vals = cmd_subparsers.add_parser(
        "vals",
        help="Set/clear values for placeholders in an existing commandline.",
        description="Set/clear values for placeholders in an existing commandline.")
    cmd_parser_vals.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Don't display info about the resulting commandline.")
    cmd_parser_vals.add_argument(
        "cmdname")
    cmd_parser_vals.add_argument(
        "placeholder_args",
        nargs='+',
        metavar="placeholder_arg",
        help="Each of these items updates an existing placeholder specification "
        "in the commandline. An argument of the form placeholdername=value will "
        "set the default value for the given placeholder, while an argument of "
        "the form placeholdername will clear the default value. An argument of "
        "the form defval:+togglename:newval will replace the values for a "
        "'toggle' style placeholder.")
    group_parser_cmd.add_argument(
        "-h", "--help",
        action=SubparsersHelpAction,
        help='show detailed operations help message and exit',
        subparsers=[
            cmd_parser_list,
            cmd_parser_set,
            cmd_parser_edit,
            cmd_parser_print,
            cmd_parser_del,
            cmd_parser_run,
            cmd_parser_vals])
    return group_parser_cmd

def set_seq_options(group_subparsers):
    group_parser_seq = group_subparsers.add_parser(
        "seq",
        add_help=False,
        help="Work with sequences of saved commandlines.",
        description="Work with sequences of saved commandlines.")
    seq_subparsers = group_parser_seq.add_subparsers(
        title="operations",
        dest="operation",
        required=True)
    seq_parser_list = seq_subparsers.add_parser(
        "list",
        help="List current sequence names.",
        description="List current sequence names.")
    seq_parser_list.add_argument(
        "-c", "--column",
        action="store_true",
        help="Single-column format.")
    seq_parser_set = seq_subparsers.add_parser(
        "set",
        help="Create or update a named sequence.",
        description="Create or update a named sequence.")
    seq_parser_set.add_argument(
        "-f", "--force",
        action="store_true",
        help="Allow use of commandline names that are not currently defined.")
    seq_parser_set.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Don't display info about the resulting sequence.")
    seq_parser_set.add_argument(
        "seqname")
    seq_parser_set.add_argument(
        "cmdnames",
        nargs='+',
        metavar="cmdname",
        help="Commandline to use in this sequence. Must currently exist, unless "
        "the optional --force argument is specified. When the sequence is run, "
        "the commandlines will be run in the specified order.")
    seq_parser_edit = seq_subparsers.add_parser(
        "edit",
        help="Interactively edit a new or existing sequence.",
        description="Interactively edit a new or existing sequence.")
    seq_parser_edit.add_argument(
        "-f", "--force",
        action="store_true",
        help="Allow use of commandline names that are not currently defined.")
    seq_parser_edit.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Don't display info about the resulting sequence.")
    seq_parser_edit.add_argument(
        "seqname")
    seq_parser_print = seq_subparsers.add_parser(
        "print",
        help="Display the commandlines for the named sequence, with their "
        "available placeholders.",
        description="Display the commandlines for the named sequence, with their "
        "available placeholders.")
    seq_parser_print.add_argument(
        "--dump-placeholders",
        choices=["run", "vals"],
        dest="dump_placeholders",
        help=argparse.SUPPRESS)
    seq_parser_print.add_argument(
        "seqname")
    seq_parser_del = seq_subparsers.add_parser(
        "del",
        help="Delete one or more sequences.",
        description="Delete one or more sequences.")
    seq_parser_del.add_argument(
        "seqnames",
        nargs='+',
        metavar="seqname",
        help="Sequence to delete.")
    seq_parser_run = seq_subparsers.add_parser(
        "run",
        help="Execute a sequence, optionally setting values for commandlines' "
        "placeholders.",
        description="Execute a sequence, optionally setting values for commandlines' "
        "placeholders.")
    seq_parser_run.add_argument(
        "-i", "--ignore-errors",
        action="store_true",
        dest="ignore_errors",
        help="Continue running the sequence even if a commandline does not exist "
        "or returns an error status.")
    seq_parser_run.add_argument(
        "-s", "--skip",
        action="append",
        metavar="cmdname",
        dest="skip_cmdnames",
        help="Skip running a command, if it is in this sequence. Multiple --skip "
        "usages are allowed, to skip multiple commands.")
    seq_parser_run.add_argument(
        "seqname")
    seq_parser_run.add_argument(
        "placeholder_args",
        nargs='*',
        metavar="placeholder_arg",
        help="Each of these items must be in the same format as used for "
        "'cmd run', and they will be passed along to each commandline in this "
        "sequence when running it. It is OK if a placeholder specified here is "
        "only relevant for some subset of the commandlines.")
    seq_parser_vals = seq_subparsers.add_parser(
        "vals",
        help="Set/clear values for placeholders in a sequence's commandlines.",
        description="Set/clear values for placeholders in a sequence's commandlines.")
    seq_parser_vals.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Don't display info about the resulting sequence.")
    seq_parser_vals.add_argument(
        "seqname")
    seq_parser_vals.add_argument(
        "placeholder_args",
        nargs='+',
        metavar="placeholder_arg",
        help="Each of these items must be in the same format as used for "
        "'cmd vals', and they will be passed along to each commandline in this "
        "sequence. It is OK if a placeholder specified here is only relevant for "
        "some subset of the commandlines.")
    group_parser_seq.add_argument(
        "-h", "--help",
        action=SubparsersHelpAction,
        help='show detailed operations help message and exit',
        subparsers=[
            seq_parser_list,
            seq_parser_set,
            seq_parser_edit,
            seq_parser_print,
            seq_parser_del,
            seq_parser_run,
            seq_parser_vals])
    return group_parser_seq

def set_print_options(group_subparsers):
    group_parser_print = group_subparsers.add_parser(
        "print",
        help="Display placeholders across all commandlines.",
        description="Display placeholders across all commandlines.")
    group_parser_print.add_argument(
        "--dump-placeholders",
        choices=["run", "vals"],
        dest="dump_placeholders",
        help=argparse.SUPPRESS)
    return group_parser_print

def set_vals_options(group_subparsers):
    group_parser_vals = group_subparsers.add_parser(
        "vals",
        help="Update placeholder values across all commandlines.",
        description="Update placeholder values across all commandlines.")
    group_parser_vals.add_argument(
        "placeholder_args",
        nargs='+',
        metavar="placeholder_arg",
        help="Each of these items must be in the same format as used for "
        "'cmd vals', and they will be passed along to each commandline. It is "
        "OK if a placeholder specified here is only relevant for some subset "
        "of the commandlines.")
    return group_parser_vals

def set_export_options(group_subparsers):
    group_parser_export = group_subparsers.add_parser(
        "export",
        help="Store commandline and sequence definitions to a flat file.",
        description="Store commandline and sequence definitions to a flat file.")
    group_parser_export.add_argument(
        "file",
        metavar="outfile")
    return group_parser_export

def set_import_options(group_subparsers):
    group_parser_import = group_subparsers.add_parser(
        "import",
        help="Load commandline and sequence definitions from a flat file.",
        description="Load commandline and sequence definitions from a flat file.")
    group_parser_import.add_argument(
        "-o", "--overwrite",
        action="store_true",
        help="Allow overwriting an existing commandline/sequence with an imported "
        "definition. If this is not specified, any such conflicts will be skipped.")
    group_parser_import.add_argument(
        "file",
        metavar="infile")
    return group_parser_import

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
                if v == None:
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
        unspecified = [k for k in all_values_keys if values_for_names[k] == None]
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
        c_is_brace = (c == '{' or c == '}')
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
        if cmd_dict['args'][key] == None:
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
    inventory_lock("seq", LockType.READ)
    inventory_lock("cmd", LockType.WRITE)
    item_lock("cmd", cmd, LockType.WRITE)
    creating = False
    if os.path.exists(os.path.join(CMD_DIR, cmd)):
        release_inventory_lock("seq", LockType.READ)
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
        write_aliases("cmd")
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
            "'Toggle' placeholders specified without values: " +
            ' '.join(toggles_without_values))
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
    inventory_lock("seq", LockType.READ)
    inventory_lock("cmd", LockType.WRITE)
    item_lock("cmd", cmd, LockType.WRITE)
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
    release_inventory_lock("cmd", LockType.WRITE)
    release_inventory_lock("seq", LockType.READ)
    print()
    new_cmdline = editline('commandline: ', old_cmdline)
    status = handle_cmd_set_internal(cmd, new_cmdline, True, print_after_set, False)
    if cleanup_placeholder_fun:
        if status:
            cleanup_placeholder_fun()
        else:
            write_aliases("cmd")
        atexit.unregister(cleanup_placeholder_fun) 
    return status

def handle_cmd_print(cmd, dump_placeholders):
    # No locking needed. We read a cmd yaml file and format/print it. If
    # the file is being deleted right now that's fine, either we get in
    # before the delete or after.
    if dump_placeholders != None:
        return handle_dump_placeholders([cmd], dump_placeholders=="run")
    print()
    handle_cmd_print_internal(cmd)

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
        if v == None:
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
        inventory_lock("seq", LockType.READ)
    inventory_lock("cmd", LockType.WRITE)
    multi_item_lock("cmd", delcmds, LockType.WRITE)
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
        write_aliases("cmd")
    return 0

def handle_cmd_run(cmd, args):
    # Arguably there's no locking needed here. But in the seq run case we
    # do keep cmds locked until the run is over, so it's good to be consistent.
    # Also it's not too surprising that we would block deleting a cmd while
    # it is running.
    item_lock("cmd", cmd, LockType.READ)
    unused_args = copy.deepcopy(args)
    status = handle_cmd_run_internal(cmd, args, unused_args)
    if unused_args:
        print(
            Fore.YELLOW + "Warning:" + Fore.RESET +
            " the following placeholder args don't apply to this commandline:",
            ' '.join(unused_args))
        print()
    return status

def handle_cmd_run_internal(cmd, args, unused_args):
    print()
    cmd_dict = command_with_values(cmd, args, unused_args, PlaceholderArgsPurpose.RUN)
    if cmd_dict == None:
        print()
        return 1
    cmdline = cmd_dict['format'].format(**cmd_dict['args'])
    print(Fore.CYAN + cmdline + Fore.RESET)
    print()
    status = subprocess.call(cmdline, shell=True)
    print()
    return status

def handle_cmd_vals(cmd, args, print_after_set):
    item_lock("cmd", cmd, LockType.WRITE)
    unused_args = copy.deepcopy(args)
    status = handle_cmd_vals_internal(cmd, args, unused_args, print_after_set, False)
    if status:
        return status
    if unused_args:
        print(
            Fore.YELLOW + "Warning:" + Fore.RESET +
            " the following placeholder args don't apply to this commandline:",
            ' '.join(unused_args))
        print()
    return 0

def handle_cmd_vals_internal(cmd, args, unused_args, print_after_set, compact):
    if not compact:
        print()
    cmd_dict = command_with_values(cmd, args, unused_args, PlaceholderArgsPurpose.UPDATE)
    if cmd_dict == None:
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

def handle_cmd(args):
    if args.operation == "list":
        return handle_cmd_list(args.column)
    if args.operation == "set":
        return handle_cmd_set(args.cmdname, args.cmdline, True, not args.quiet)
    if args.operation == "edit":
        return handle_cmd_edit(args.cmdname, not args.quiet)
    if args.operation == "print":
        return handle_cmd_print(args.cmdname, args.dump_placeholders)
    if args.operation == "del":
        return handle_cmd_del(args.cmdnames, args.force)
    if args.operation == "run":
        return handle_cmd_run(args.cmdname, args.placeholder_args)
    if args.operation == "vals":
        return handle_cmd_vals(args.cmdname, args.placeholder_args, not args.quiet)
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
    inventory_lock("seq", LockType.WRITE)
    item_lock("seq", seq, LockType.WRITE)
    creating = False
    if not os.path.exists(os.path.join(SEQ_DIR, seq)):
        creating = True
        # Check whether there's a cmd of the same name.
        inventory_lock("cmd", LockType.READ)
        if os.path.exists(os.path.join(CMD_DIR, seq)):
            print()
            errprint(
                "Sequence '{}' cannot be created because a command exists with "
                "the same name.".format(cmd))
            print()
            return 1
    # If ignore_missing_cmds is true then we will need the cmd inventory lock
    # to check that out, whether or not we acquired it above. That lock will
    # be (re)acquired later inside handle_seq_set_internal. That lock is done
    # late because in the edit case we don't want to hold it while the
    # interactive edit is going on.
    status = handle_seq_set_internal(seq, cmds, ignore_missing_cmds, overwrite, print_after_set, False)
    if creating and not status:
        write_aliases("seq")
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
        inventory_lock("cmd", LockType.READ)
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
    inventory_lock("seq", LockType.WRITE)
    item_lock("seq", seq, LockType.WRITE)
    cleanup_placeholder_fun = None
    try:
        seq_dict = read_seq_dict(seq)
        old_commands_str = ' '.join(seq_dict['commands'])
    except FileNotFoundError:
        # Check whether there's a cmd of the same name.
        inventory_lock("cmd", LockType.READ)
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
        delete_on_error = True
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
        release_inventory_lock("cmd", LockType.READ)
    release_inventory_lock("seq", LockType.WRITE)
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
            write_aliases("seq")
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
                if v == None:
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
        return num_commands*len(group)+(num_commands-commands.index(group[0])-1)
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
                    if command_dicts_by_cmd[first_cmd]['args'][a] != None:
                        args_dict = 'args'
                        common_format_str = "{} = {}"
                else:
                    args_dict = 'toggle_args'
                    common_format_str = "{} = {}:{}"
                if args_dict != None:
                    has_common_value = True
                    first_value = command_dicts_by_cmd[first_cmd][args_dict][a]
                    def format_parts(v, c):
                        if args_dict == 'args':
                            return ("{} ({})", [shlex.quote(v), c])
                        else:
                            v0 = shlex.quote(v[0])
                            v1 = shlex.quote(v[1])
                            return ("{}:{} ({})", [v0, v1, c])
                    (format_suffix, added_args) = format_parts(first_value, first_cmd)
                    format_str += format_suffix
                    format_args += added_args
                    for cmd in group[1:]:
                        this_value = command_dicts_by_cmd[cmd][args_dict][a]
                        if this_value == None:
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
    if dump_placeholders == None:
        item_lock("seq", seq, LockType.READ)
        inventory_lock("cmd", LockType.READ)
    try:
        seq_dict = read_seq_dict(seq)
    except FileNotFoundError:
        if dump_placeholders == None:
            print()
            errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    commands = seq_dict['commands']
    if dump_placeholders == None:
        multi_item_lock("cmd", commands, LockType.READ)
        release_inventory_lock("cmd", LockType.READ)
    if dump_placeholders != None:
        return handle_dump_placeholders(commands, dump_placeholders=="run")
    print()
    handle_multi_cmd_print_internal(commands)

def handle_seq_del(delseqs):
    inventory_lock("seq", LockType.WRITE)
    multi_item_lock("seq", delseqs, LockType.WRITE)
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
        write_aliases("seq")
    return 0

def handle_seq_run(seq, args, ignore_errors, skip_cmdnames):
    item_lock("seq", seq, LockType.READ)
    inventory_lock("cmd", LockType.READ)
    print()
    try:
        seq_dict = read_seq_dict(seq)
    except FileNotFoundError:
        errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    cmd_list = seq_dict['commands']
    multi_item_lock("cmd", cmd_list, LockType.READ)
    release_inventory_lock("cmd", LockType.READ)
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
            Fore.YELLOW + "Warning:" + Fore.RESET +
            " the following placeholder args don't apply to any commandline:",
            ' '.join(unused_args))
        print()
    return 0

def handle_seq_vals(seq, args, print_after_set):
    item_lock("seq", seq, LockType.WRITE)
    inventory_lock("cmd", LockType.READ)
    try:
        seq_dict = read_seq_dict(seq)
    except FileNotFoundError:
        print()
        errprint("Sequence '{}' does not exist.".format(seq))
        print()
        return 1
    cmd_list = seq_dict['commands']
    multi_item_lock("cmd", cmd_list, LockType.WRITE)
    release_inventory_lock("cmd", LockType.READ)
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
            Fore.YELLOW + "Warning:" + Fore.RESET +
            " the following placeholder args don't apply to any commandline "
            "in this sequence:",
            ' '.join(unused_args))
        print()
    if error:
        return 1
    return 0

def handle_seq(args):
    if args.operation == "list":
        return handle_seq_list(args.column)
    if args.operation == "set":
        return handle_seq_set(args.seqname, args.cmdnames, args.force, True, not args.quiet)
    if args.operation == "edit":
        return handle_seq_edit(args.seqname, args.force, not args.quiet)
    if args.operation == "print":
        return handle_seq_print(args.seqname, args.dump_placeholders)
    if args.operation == "del":
        return handle_seq_del(args.seqnames)
    if args.operation == "run":
        return handle_seq_run(args.seqname, args.placeholder_args, args.ignore_errors, args.skip_cmdnames)
    if args.operation == "vals":
        return handle_seq_vals(args.seqname, args.placeholder_args, not args.quiet)
    return 0

def handle_print(args):
    if args.dump_placeholders == None:
        inventory_lock("cmd", LockType.READ)
    command_names = os.listdir(CMD_DIR)
    if args.dump_placeholders == None:
        multi_item_lock("cmd", command_names, LockType.READ)
    if args.dump_placeholders != None:
        return handle_dump_placeholders(command_names, args.dump_placeholders=="run")
    print()
    return handle_multi_cmd_print_internal(command_names)

def handle_vals(args):
    inventory_lock("cmd", LockType.READ)
    command_names = os.listdir(CMD_DIR)
    multi_item_lock("cmd", command_names, LockType.WRITE)
    print()
    unused_args = copy.deepcopy(args.placeholder_args)
    print(Fore.MAGENTA + "* updating all commands" + Fore.RESET)
    print()
    error = False
    for cmd in command_names:
        status = handle_cmd_vals_internal(cmd, args.placeholder_args, unused_args, False, True)
        if status:
            error = True
    if unused_args:
        print(
            Fore.YELLOW + "Warning:" + Fore.RESET +
            " the following placeholder args don't apply to any commandline:",
            ' '.join(unused_args))
        print()
    if error:
        return 1
    return 0

def handle_export(args):
    inventory_lock("seq", LockType.READ)
    inventory_lock("cmd", LockType.READ)
    command_names = os.listdir(CMD_DIR)
    sequence_names = os.listdir(SEQ_DIR)
    multi_item_lock("cmd", command_names, LockType.READ)
    multi_item_lock("seq", sequence_names, LockType.READ)
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
    with open(args.file, 'w') as export_file:
        export_file.write(export_doc)
    return 0

def handle_import(args):
    inventory_lock("seq", LockType.WRITE)
    inventory_lock("cmd", LockType.WRITE)
    if args.overwrite:
        command_names = os.listdir(CMD_DIR)
        sequence_names = os.listdir(SEQ_DIR)
        multi_item_lock("cmd", command_names, LockType.WRITE)
        multi_item_lock("seq", sequence_names, LockType.WRITE)
    print()
    with open(args.file, 'r') as import_file:
        import_dict = yaml.safe_load(import_file)
    print(Fore.MAGENTA + "* Importing commands..." + Fore.RESET)
    print()
    for cmd_dict in import_dict['commands']:
        handle_cmd_set_internal(cmd_dict['name'], cmd_dict['cmdline'], args.overwrite, False, True)
    print(Fore.MAGENTA + "* Importing sequences..." + Fore.RESET)
    print()
    for seq_dict in import_dict['sequences']:
        handle_seq_set_internal(seq_dict['name'], seq_dict['commands'], True, args.overwrite, False, True)
    write_all_aliases()
    return 0

def main():
    colorama.init()
    atexit.register(lambda: colorama.deinit()) 
    os.makedirs(CMD_DIR, exist_ok=True)
    os.makedirs(SEQ_DIR, exist_ok=True)
    os.makedirs(LOCKS_DIR, exist_ok=True)
    parser = argparse.ArgumentParser(add_help=False)
    group_subparsers = parser.add_subparsers(
        title="command groups",
        dest="commandgroup",
        required=True)
    group_parser_cmd = set_cmd_options(group_subparsers)
    group_parser_seq = set_seq_options(group_subparsers)
    group_parser_print = set_print_options(group_subparsers)
    group_parser_vals = set_vals_options(group_subparsers)
    group_parser_export = set_export_options(group_subparsers)
    group_parser_import = set_import_options(group_subparsers)
    parser.add_argument(
        "-h", "--help",
        action=SubparsersHelpAction,
        help='show detailed help message and exit',
        subparsers=[
            group_parser_cmd,
            group_parser_seq,
            group_parser_print,
            group_parser_vals,
            group_parser_export,
            group_parser_import])
    args = parser.parse_args()
    status = 0
    if args.commandgroup == "cmd":
        status = handle_cmd(args)
    elif args.commandgroup == "seq":
        status = handle_seq(args)
    elif args.commandgroup == "print":
        status = handle_print(args)
    elif args.commandgroup == "vals":
        status = handle_vals(args)
    elif args.commandgroup == "export":
        status = handle_export(args)
    elif args.commandgroup == "import":
        status = handle_import(args)
    return status

if __name__ == "__main__":
    sys.exit(main())