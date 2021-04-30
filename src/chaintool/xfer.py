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
to command_impl_* and sequence_impl modules for most of the work.

Note that most locks acquired here are released only when the program exits.
Operations are meant to be invoked one per program instance, using the CLI.

"""


__all__ = ["cli_export", "cli_import"]


import yaml  # from pyyaml

from colorama import Fore

from . import command_impl_core
from . import command_impl_op
from . import completions
from . import sequence_impl
from . import locks
from . import shortcuts


def cli_export(export_file):
    """Export all current commands and sequences to a file.

    Acquire the seq and cmd inventory readlocks, get all sequence and
    command names, and readlock all those items.

    Open the given file and write a YAML doc to it. Commands (from
    :func:`.command_impl_core.read_dict`) are written to a list value for the
    "commands" property, and sequences (from :func:`.sequence_impl.read_dict`)
    similarly to the "sequences" property.

    :param export_file: filepath to write to
    :type export_file:  str

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    locks.inventory_lock("seq", locks.LockType.READ)
    locks.inventory_lock("cmd", locks.LockType.READ)
    command_names = command_impl_core.all_names()
    sequence_names = sequence_impl.all_names()
    locks.multi_item_lock("cmd", command_names, locks.LockType.READ)
    locks.multi_item_lock("seq", sequence_names, locks.LockType.READ)
    print()
    export_dict = {"commands": [], "sequences": []}
    print(Fore.MAGENTA + "* Exporting commands..." + Fore.RESET)
    print()
    for cmd in command_names:
        try:
            cmd_dict = command_impl_core.read_dict(cmd)
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
            seq_dict = sequence_impl.read_dict(seq)
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
    """Import commands and sequences from a file.

    Acquire the seq and cmd inventory writelocks. If ``overwrite`` is
    ``True``, get all sequence and command names, and writelock all those
    items.

    Open the given file and read a YAML doc from it. Commands are read from a
    list value for the "commands" property, and sequences similary from the
    "sequences" property. The ``overwrite`` argument is passed along to
    command and sequence creation (via :func:`.command_impl_op.define` and
    :func:`.sequence_impl.define`) to control whether an imported item is
    allowed to replace an existing item of the same name.

    For each successfully created item, also set up its shortcut
    (:func:`.shortcuts.create_seq_shortcut` or
    :func:`.shortcuts.create_cmd_shortcut`) and autocompletion behavior
    (:func:`.completions.create_completion`).

    :param import_file:   filepath to read from
    :type import_file:    str
    :param overwrite:     whether to allow replacing existing items
    :type overwrite:      bool

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    locks.inventory_lock("seq", locks.LockType.WRITE)
    locks.inventory_lock("cmd", locks.LockType.WRITE)
    if overwrite:
        command_names = command_impl_core.all_names()
        sequence_names = sequence_impl.all_names()
        locks.multi_item_lock("cmd", command_names, locks.LockType.WRITE)
        locks.multi_item_lock("seq", sequence_names, locks.LockType.WRITE)
    print()
    with open(import_file, "r") as infile:
        import_dict = yaml.safe_load(infile)
    print(Fore.MAGENTA + "* Importing commands..." + Fore.RESET)
    print()
    for cmd_dict in import_dict["commands"]:
        cmd = cmd_dict["name"]
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
        status = sequence_impl.define(
            seq, seq_dict["commands"], [], overwrite, False, True
        )
        if not status:
            shortcuts.create_seq_shortcut(seq)
            completions.create_completion(seq)
    return 0
