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


"""Dump info used in bash completions for chaintool."""


__all__ = ["main"]


import sys

from chaintool import item_io
from chaintool import virtual_tools


def update_placeholders_collections(
    key, value, consistent_values_dict, other_set
):
    """Memo-ize whether a placeholder has a single value in a set of commands.

    This function is called repeatedly by :func:`dump_placeholders` to build
    a picture of which placeholders are set to only one specific value in a
    set of commands; such placeholder names and values will be populated in
    ``consistent_values_dict``. If a placeholder is not set to any value, or
    if it appears multiple times and is set to different values, it will be
    treated differently; such placeholder names will be populated in
    ``other_set``.

    So: examine the ``key`` and ``value`` for a placeholder to process,
    examine the existing items in``consistent_values_dict`` and ``other_set``,
    and update the dict and/or set accordingly.

    :param key:                    the name of the placeholder to process
    :type key:                     str
    :param value:                  the value for the placeholder to process
    :type value:                   str
    :param consistent_values_dict: dict of placeholders that have a consistent
                                   value (value keyed by placeholder name);
                                   to modify
    :type consistent_values_dict:  dict[str, str | [str, str]]
    :param other_set:              set of names of placeholders that have
                                   either no value or multiple values; to
                                   modify
    :type other_set:               set[str]

    """
    if key in other_set:
        return
    if value is None:
        if key in consistent_values_dict:
            del consistent_values_dict[key]
        other_set.add(key)
        return
    if key not in consistent_values_dict:
        consistent_values_dict[key] = value
        return
    if consistent_values_dict[key] != value:
        del consistent_values_dict[key]
        other_set.add(key)


def dump_placeholders(commands, is_run):  # pylint: disable=too-many-branches
    """Do a "raw" printing of placeholders used in a list of commands.

    Used internally for bash autocompletion purposes.

    Iterate through the ``commands``. Run their placeholders and toggle-type
    placeholders through :func:`update_placeholders_collections` to build
    placeholder info for printing.

    Then iterate through the collections and print the placeholder info in a
    form useful for doing a command-line autocompletion given the first few
    characters of the placeholder name.

    - If a placeholder has a consistent value, we want to include the value
      setting in the autocompletion, so it can be observed and edited.
    - If a toggle has a consistent value, we want to include the value setting
      only if ``is_run`` is false, since it's not legal to change that value
      at runtime.
    - If a toggle has an inconsistent value, still print an "=" character if
      ``is_run`` is false, since some value must be provided in that case.

    :param commands: names of commands to process
    :type commands:  list[str]
    :param is_run:   whether this is for an intended "run" op (as opposed to
                     "vals")
    :type is_run:    bool

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    placeholders_with_consistent_value = dict()
    other_placeholders_set = set()
    toggles_with_consistent_value = dict()
    other_toggles_set = set()
    env_values = dict()
    for cmd in commands:
        try:
            cmd_dict = item_io.read_cmd(cmd)
        except FileNotFoundError:
            continue
        for key, value in cmd_dict["args"].items():
            if key in env_values:
                # Treat this as unset because this value cannot be entered
                # on the commandline to the same effect... it will not be
                # interpreted for placeholder substitution as a run arg.
                value = None
                cmd_dict["args"][key] = value
            update_placeholders_collections(
                key,
                value,
                placeholders_with_consistent_value,
                other_placeholders_set,
            )
        for key, value in cmd_dict["toggle_args"].items():
            update_placeholders_collections(
                key,
                value,
                toggles_with_consistent_value,
                other_toggles_set,
            )
        if is_run:
            virtual_tools.update_env(cmd_dict["cmdline"], env_values)
    for key, value in placeholders_with_consistent_value.items():
        print("{}={}".format(key, value))
    for key in other_placeholders_set:
        print("{}".format(key))
    if is_run:
        for key in toggles_with_consistent_value:
            print(key)
        for key in other_toggles_set:
            print(key)
    else:
        for key, value in toggles_with_consistent_value.items():
            print("{}={}:{}".format(key, value[0], value[1]))
        for key in other_toggles_set:
            print("{}=".format(key))
    return 0


def main(args):
    """Dump commands, sequences, or placeholders for bash completion support.

    The args are expected to be in one of the following arrangements:

    - cmd: list all command names
    - seq: list all sequence names
    - run: dump placeholders for all commands, in "run" format
    - vals: dump placeholders for all commands, in "vals" format
    - run cmd <command_name>: dump placeholders for command <command_name>,
      in "run" format
    - vals cmd <command_name>: dump placeholders for command <command_name>,
      in "vals" format
    - run seq <sequence_name>: dump placeholders for the commands in sequence
      <sequence_name>, in "run" format
    - vals seq <sequence_name>: dump placeholders for the commands in sequence
      <sequence_name>, in "vals" format

    So if the first arg is "cmd" or "seq", print that list and exit.

    Otherwise, form the appropriate list of command names and delegate to
    :func:`dump_placeholders`.

    Note that this is an internally-used utility so we don't do extra
    validation on the command-line args. Also for the purposes of this
    code, some transient inconsistencies are fine if we happen to race with
    command or sequence edit/create/delete, so no locking is done.

    :param args: command-line arguments
    :type args:  list[str]

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    if args[0] == "cmd":
        commands = item_io.cmd_names()
        print("\n".join(commands))
        return 0
    if args[0] == "seq":
        sequences = item_io.seq_names()
        print("\n".join(sequences))
        return 0
    is_run = args[0] == "run"
    if len(args) == 1:
        commands = item_io.cmd_names()
    elif args[1] == "cmd":
        commands = [args[2]]
    else:
        seq = args[2]
        seq_dict = item_io.read_seq(seq)
        commands = seq_dict["commands"]
    return dump_placeholders(commands, is_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
