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

"""Top-level logic for "export" and "import" operations.

Called from cli module. Handles locking and shortcuts/completions; delegates
to command_impl_* and sequence_impl_* modules for most of the work.

Note that most locks acquired here are released only when the program exits.
Operations are meant to be invoked one per program instance, using the CLI.

"""


__all__ = ["cli_export", "cli_import"]


import requests
import yaml  # from pyyaml

from colorama import Fore

from . import current_export_schema_ver

from . import command_impl_op
from . import completions
from . import item_io
from . import sequence_impl_op
from . import locks
from . import shared
from . import shortcuts

from .locks import LockType
from .shared import ItemType


def cli_export(export_file):
    """Export all current commands and sequences to a file.

    Acquire the seq and cmd inventory readlocks, get all sequence and
    command names, and readlock all those items.

    Open the given file and write a YAML doc to it. Commands (from
    :func:`.item_io.read_cmd`) are written to a list value for the "commands"
    property, and sequences (from :func:`.item_io.read_seq`) similarly to the
    "sequences" property. The "schema_version" is also written, to help
    interpret this file if its format changes in the future.

    :param export_file: filepath to write to
    :type export_file:  str

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    export_schema_ver = current_export_schema_ver()
    if export_schema_ver is None:
        print()
        shared.errprint(
            "Internal error: unable to determine export format for this"
            " version of chaintool."
        )
        print()
        return 1
    locks.inventory_lock(ItemType.SEQ, LockType.READ)
    locks.inventory_lock(ItemType.CMD, LockType.READ)
    command_names = item_io.cmd_names()
    sequence_names = item_io.seq_names()
    locks.multi_item_lock(ItemType.CMD, command_names, LockType.READ)
    locks.multi_item_lock(ItemType.SEQ, sequence_names, LockType.READ)
    print()
    export_dict = {
        "schema_version": export_schema_ver,
        "commands": [],
        "sequences": [],
    }
    print(Fore.MAGENTA + "* Exporting commands..." + Fore.RESET)
    print()
    for cmd in command_names:
        try:
            cmd_dict = item_io.read_cmd(cmd)
        except FileNotFoundError:
            print("Failed to read command '{}' ... skipped.".format(cmd))
            print()
            continue
        export_dict["commands"].append(
            {"name": cmd, "cmdline": cmd_dict["cmdline"]}
        )
        print("Command '{}' exported.".format(cmd))
        print()
    print(Fore.MAGENTA + "* Exporting sequences..." + Fore.RESET)
    print()
    for seq in sequence_names:
        try:
            seq_dict = item_io.read_seq(seq)
        except FileNotFoundError:
            print("Failed to read sequence '{}' ... skipped.".format(seq))
            print()
            continue
        export_dict["sequences"].append(
            {"name": seq, "commands": seq_dict["commands"]}
        )
        print("Sequence '{}' exported.".format(seq))
        print()
    export_doc = yaml.dump(export_dict, default_flow_style=False)
    with open(export_file, "w") as outfile:
        outfile.write(export_doc)
    return 0


def cli_import(import_file, overwrite):
    """Import commands and sequences from a filepath or an http/https URL.

    Acquire the seq and cmd inventory writelocks. If ``overwrite`` is
    ``True``, get all sequence and command names, and writelock all those
    items.

    Open the given file or URL and read a YAML doc from it. Commands are read
    from a list value for the "commands" property, and sequences similary from
    the "sequences" property. The ``overwrite`` argument is passed along to
    command and sequence creation (via :func:`.command_impl_op.define` and
    :func:`.sequence_impl_op.define`) to control whether an imported item is
    allowed to replace an existing item of the same name.

    For each successfully created item, also set up its shortcut
    (:func:`.shortcuts.create_seq_shortcut` or
    :func:`.shortcuts.create_cmd_shortcut`) and autocompletion behavior
    (:func:`.completions.create_completion`).

    :param import_file:   filepath or http/https URL to read from
    :type import_file:    str
    :param overwrite:     whether to allow replacing existing items (note this
                          does NOT allow conflict between command name and
                          sequence name)
    :type overwrite:      bool

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    locks.inventory_lock(ItemType.SEQ, LockType.WRITE)
    locks.inventory_lock(ItemType.CMD, LockType.WRITE)
    if overwrite:
        command_names = item_io.cmd_names()
        sequence_names = item_io.seq_names()
        locks.multi_item_lock(ItemType.CMD, command_names, LockType.WRITE)
        locks.multi_item_lock(ItemType.SEQ, sequence_names, LockType.WRITE)
    print()
    if import_file.startswith("https://") or import_file.startswith("http://"):
        with requests.get(import_file) as response:
            import_dict = yaml.safe_load(response.text)
    else:
        with open(import_file, "r") as infile:
            import_dict = yaml.safe_load(infile)
    print(Fore.MAGENTA + "* Importing commands..." + Fore.RESET)
    print()
    for cmd_dict in import_dict["commands"]:
        cmd = cmd_dict["name"]
        if item_io.seq_exists(cmd):
            print(
                "Command '{}' cannot be created because a sequence exists with"
                " the same name.".format(cmd)
            )
            print()
            continue
        status = command_impl_op.define(
            cmd, cmd_dict["cmdline"], overwrite, False, True
        )
        if not status:
            shortcuts.create_cmd_shortcut(cmd)
            completions.create_completion(cmd)
    print(Fore.MAGENTA + "* Importing sequences..." + Fore.RESET)
    print()
    for seq_dict in import_dict["sequences"]:
        seq = seq_dict["name"]
        if item_io.cmd_exists(seq):
            print(
                "Sequence '{}' cannot be created because a command exists with"
                " the same name.".format(seq)
            )
            print()
            continue
        status = sequence_impl_op.define(
            seq, seq_dict["commands"], [], overwrite, False, True
        )
        if not status:
            shortcuts.create_seq_shortcut(seq)
            completions.create_completion(seq)
    return 0
