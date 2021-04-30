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

"""Low-level logic for "cmd" operations related to pretty-printing.

Called from command, sequence, command_impl, and sequence_impl modules.

"""


__all__ = [
    "dump_placeholders",
    "print_one",
    "print_multi",
]


import shlex

from colorama import Fore

from . import command_impl_core
from . import shared
from . import virtual_tools


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

    - If a placeholder has been assigned a constant value from chaintool-env,
      before it is ever used in a command, skip it.
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
    env_constant_values = []
    env_optional_values = dict()
    for cmd in commands:
        try:
            cmd_dict = command_impl_core.read_dict(cmd)
        except FileNotFoundError:
            continue
        for key, value in cmd_dict["args"].items():
            if key in env_constant_values:
                continue
            if key in env_optional_values:
                value = env_optional_values[key]
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
            virtual_tools.update_env(
                cmd_dict["cmdline"],
                env_constant_values,
                env_optional_values,
            )
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


def print_one(cmd):
    """Pretty-print the info for a command.

    Read the command dictionary, and bail out if it does not exist.

    Pretty-print the placeholder info separated into "required values" (no
    default), "optional values", and "toggles".

    :param cmd: name of command to print
    :type cmd:  str

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    try:
        cmd_dict = command_impl_core.read_dict(cmd)
    except FileNotFoundError:
        shared.errprint("Command '{}' does not exist.".format(cmd))
        print()
        return 1
    all_required_placeholders = []
    all_optional_placeholders = []
    for key, value in cmd_dict["args"].items():
        if value is None:
            all_required_placeholders.append(key)
        else:
            all_optional_placeholders.append(key)
    all_toggle_placeholders = list(cmd_dict["toggle_args"].keys())
    print(Fore.MAGENTA + "* commandline format:" + Fore.RESET)
    print(cmd_dict["cmdline"])
    if all_required_placeholders:
        print()
        print(Fore.MAGENTA + "* required values:" + Fore.RESET)
        all_required_placeholders.sort()
        for placeholder in all_required_placeholders:
            print(placeholder)
    if all_optional_placeholders:
        print()
        print(Fore.MAGENTA + "* optional values with default:" + Fore.RESET)
        all_optional_placeholders.sort()
        for placeholder in all_optional_placeholders:
            print(
                "{} = {}".format(
                    placeholder, shlex.quote(cmd_dict["args"][placeholder])
                )
            )
    if all_toggle_placeholders:
        print()
        print(
            Fore.MAGENTA
            + "* toggles with untoggled:toggled values:"
            + Fore.RESET
        )
        all_toggle_placeholders.sort()
        for placeholder in all_toggle_placeholders:
            togglevals = cmd_dict["toggle_args"][placeholder]
            print(
                "{} = {}:{}".format(
                    placeholder,
                    shlex.quote(togglevals[0]),
                    shlex.quote(togglevals[1]),
                )
            )
    print()
    return 0


def init_print_info_collections(  # pylint: disable=too-many-arguments
    commands,
    command_dicts,
    command_dicts_by_cmd,
    commands_by_placeholder,
    placeholders_sets,
    ignore_env,
):
    """Gather info useful to pretty-print multiple commands.

    Iterate through the ``commands``, for each command reading its dictionary
    and using the args info (placeholders+values) to populate the various
    inout collections arguments.

    Populating ``command_dicts``, ``command_dicts_by_cmd``, and
    ``commands_by_placeholder`` is straightforward.

    Deciding which "set" a placeholder name belongs in, to populate
    ``placeholders_sets``, goes according to the following rules:

    - If a placeholder has been assigned a constant value from chaintool-env,
      ignore its appearances in subsequent commands, as its value there is no
      longer user-controllable. (Note that this is not relevant if
      ``ignore_env`` is true.)
    - If a placeholder lacks a default value in some command, put it in the
      "required" set.
    - If a placeholder has some default everywhere it appears -- either
      because of its definition in the commandline or because of the use
      of chaintool-env (if ``ignore_env`` is False) -- put it in the
      "optional" set.
    - Any toggle placeholder goes into the "toggle" set.

    Finally, return a string that lists the command names, with any
    non-existing command highlighted in red.

    :param commands:                list of command names
    :type commands:                 list[str]
    :param command_dicts:           list of command dictionaries, initially
                                    empty; to modify
    :type command_dicts:            list[dict[str, str]]
    :param command_dicts_by_cmd:    dict of command dictionaries, keyed by
                                    command name, initially empty; to modify
    :type command_dicts_by_cmd:     dict[str, dict[str, str]]
    :param commands_by_placeholder: dict keyed by placeholder name where the
                                    value is a list of names of commands where
                                    that placeholder appears, initially empty;
                                    to modify
    :type commands_by_placeholder:  dict[str, dict[str, str]]
    :param placeholders_sets:       dict with keys "required", "optional",
                                    and "toggle", where each value is a set
                                    of placeholders of that type, sets
                                    initially empty; to modify
    :type placeholders_sets:        dict[str, set[str]]
    :param ignore_env:              whether to ignore the effects of
                                    chaintool-env; will be True for
                                    non-sequence prints
    :type ignore_env:               bool

    :returns: pretty-printed string containing command names
    :rtype:   str

    """

    def record_placeholder(cmd, placeholder):
        """Mark that a command uses a placeholder.

        Add the input usage info to the commands_by_placeholder dict.

        :param cmd:         command name
        :type cmd:          str
        :param placeholder: placeholder name used by the command
        :type placeholder:  str

        """
        if placeholder in commands_by_placeholder:
            commands_by_placeholder[placeholder].append(cmd)
        else:
            commands_by_placeholder[placeholder] = [cmd]

    commands_display = ""
    env_constant_values = []
    env_optional_values = dict()
    for cmd in commands:
        try:
            cmd_dict = command_impl_core.read_dict(cmd)
        except FileNotFoundError:
            commands_display += " " + Fore.RED + cmd + Fore.RESET
            continue
        commands_display += " " + cmd
        cmd_dict["name"] = cmd
        command_dicts.append(cmd_dict)
        command_dicts_by_cmd[cmd] = cmd_dict
        for key, value in cmd_dict["args"].items():
            if key in env_constant_values:
                continue
            if key in env_optional_values:
                value = Fore.GREEN + env_optional_values[key] + Fore.RESET
                cmd_dict["args"][key] = value
            record_placeholder(cmd, key)
            if value is None:
                placeholders_sets["required"].add(key)
                placeholders_sets["optional"].discard(key)
            else:
                if key not in placeholders_sets["required"]:
                    placeholders_sets["optional"].add(key)
        for key in cmd_dict["toggle_args"].keys():
            record_placeholder(cmd, key)
            placeholders_sets["toggle"].add(key)
        if not ignore_env:
            virtual_tools.update_env(
                cmd_dict["cmdline"],
                env_constant_values,
                env_optional_values,
            )
    return commands_display[1:]


def print_group_args(group, group_args, build_format_fun):
    """Print the placeholders used in a group of commands.

    For every "arg" (placeholder name) in ``group_args``, iterate through the
    commands in ``group`` invoking ``build_format_fun`` repeatedly. This
    function returns a tuple of: are we done yet (boolean), updated format
    string, and an updated values list to apply to that format string.

    When ``build_format_fun`` returns ``True`` as the first value of that
    return tuple, stop the iteration-over-commands. Print using the
    last-returned format string with the last-returned format values, and then
    move on to processing the next placeholder in ``group_args``.

    Note that the format values returned by ``build_format_fun`` are
    guaranteed to correctly populate the placeholders in the format string
    but may (in fact, will) have additional elements at the end of the list
    for various reasons.

    :param group:            list of command names
    :type group:             list[str]
    :param group_args:       list of placeholders (with values, if any) common
                             to that group of commands
    :type group_args:        list[str]
    :param build_format_fun: func used to gradually build a format string
                             for printing (see above)
    :type build_format_fun:  Callable[
                                 [str, str, str | None, str | None],
                                 tuple[bool, str, list[str | None]]
                             ]

    """
    first_cmd = group[0]
    for arg in group_args:
        done, format_str, format_args = build_format_fun(arg, first_cmd)
        if not done:
            for cmd in group[1:]:
                done, format_str, format_args = build_format_fun(
                    arg, cmd, format_str, format_args
                )
                if done:
                    break
        print(format_str.format(*format_args))


def print_command_groups(cmd_group_args, command_dicts_by_cmd):
    """Print the placeholders used in every group of commands.

    The bulk of this function is really in the definition of the formatter
    function :func:`build_format` passed to :func:`print_group_args`, so see
    the docstring for that.

    Once that function is defined, for each command group pretty-print a
    header and then call :func:`print_group_args`.

    :param cmd_group_args:       list of 2-tuples containing: a list of
                                 commands, and a list of placeholders those
                                 commands have in common
    :type cmd_group_args:        list[tuple[list[str], list[str]]]
    :param command_dicts_by_cmd: dict of command dictionaries, keyed by
                                 command name
    :type command_dicts_by_cmd:  dict[str, dict[str, str]]

    """
    _, firstargs = cmd_group_args[0]
    if firstargs[0][0] == "+":
        args_dict_name = "toggle_args"
        vals_per_arg = 2
        multival_str_suffix = "{}:{} ({})"
        common_format_str = "{} = {}:{}"
    else:
        args_dict_name = "args"
        vals_per_arg = 1
        multival_str_suffix = "{} ({})"
        common_format_str = "{} = {}"

    def build_format(arg, cmd, format_str=None, format_args=None):
        """Iteratively build a format string+values to print placeholder info.

        The general idea is to look up the default value that the given
        placeholder has assigned for the given command, and add on to the
        format string/values the stuff necessary to display that. As this
        function is invoked for all commands that use a given placeholder, the
        complete set of format info is built.

        More specifically:

        If the placeholder is found to lack a default value in any command,
        return a simple set of format info that will only display the
        placeholder name. Also return ``True`` for the are-we-done result. The
        idea is that this placeholder is required to be specified, so even if
        it has default values in some commands, those values don't matter.

        As long as the placeholder has the same default value in all commands
        so far (which should be a common case), a simple set of format info
        is returned that will show the placeholder name and value, not broken
        out per-command. We actually smuggle a "common value so far" element
        at the end of the values list to help track this.

        If this "common value" condition is broken, switch to generating
        format info that will break out the displayed default values
        per-command.

        :param arg:         placeholder name
        :type arg:          str
        :param cmd:         name of a command that uses the placeholder
        :type cmd:          str
        :param format_str:  format string built so far; defaults to None
        :type format_str:   str | None, optional
        :param format_args: list of format values (and whatever else we need
                            to pass between iterations); defaults to None
        :type format_args:  list[str | None] | None, optional

        :returns: tuple of "done yet", format str, and format values
        :rtype:   tuple[bool, str, list[str | None]]

        """
        value = command_dicts_by_cmd[cmd][args_dict_name][arg]
        # Early return if no default value; user will be required to specify.
        if value is None:
            return True, "{}", [arg]
        # Prepare the format values to be added.
        if vals_per_arg == 1:
            args_suffix = [shlex.quote(value), cmd]
        else:
            args_suffix = [shlex.quote(value[0]), shlex.quote(value[1]), cmd]
        # If this is first invocation for this arg, return initial info.
        if format_str is None:
            format_args = [arg] + args_suffix + [value]
            return False, common_format_str, format_args
        # Pop off the "common value so far" being smuggled in the values list.
        actual_format_args, common_value = format_args[:-1], format_args[-1]
        # If value is still common, return the info for that case.
        if value == common_value:
            format_args = actual_format_args + args_suffix + [common_value]
            return False, common_format_str, format_args
        # If this is the first time we're noticing a non-common value,
        # "backfill" the format string to show all prior commands+values.
        if common_value is not None:
            catch_up = (len(actual_format_args) - 1) // (vals_per_arg + 1)
            format_str = "{} = " + ", ".join([multival_str_suffix] * catch_up)
        # Now go ahead and extend the format info for this command+value.
        format_str = ", ".join([format_str, multival_str_suffix])
        format_args = actual_format_args + args_suffix + [None]
        return False, format_str, format_args

    for group, args in cmd_group_args:
        print(Fore.CYAN + "* " + ", ".join(group) + Fore.RESET)
        args.sort()
        print_group_args(group, args, build_format)


def print_placeholders_set(
    placeholders_set, sortfunc, command_dicts_by_cmd, commands_by_placeholder
):
    """Print info for all placeholders of a given type.

    The ``placeholders_set`` input is a set of placeholder names that should
    be displayed in the same block together for pretty-print purposes, e.g.
    "all placeholders that lack a default value".

    The first task here is to group placeholders by the commands where they
    appear. E.g. so we can say that commands x and y both use placeholders
    a, b, and c. Build a list of 2-tuples, where the first element of the
    tuple is a list of commands, and the second element is a list of the
    placeholders used by all of those commands.

    Use the ``sortfunc`` to sort this list in a desirable way (see
    :func:`print_multi` for more details) and then invoke
    :func:`print_command_groups` to pretty-print the list.

    :param placeholders_set:        placeholder names of a given type
    :type placeholders_set:         set[str]
    :param sortfunc:                function used to sort list of tuples
                                    associating command groups with
                                    placeholders
    :type sortfunc:                 Callable[
                                        [tuple[list[str], list[str]]],
                                        int
                                    ]
    :param command_dicts_by_cmd:    dict of command dictionaries, keyed by
                                    command name
    :type command_dicts_by_cmd:     dict[str, dict[str, str]]
    :param commands_by_placeholder: dict keyed by placeholder name where the
                                    value is a list of names of commands where
                                    that placeholder appears, initially empty;
                                    to modify
    :type commands_by_placeholder:  dict[str, dict[str, str]]

    """

    def args_updater(arg, oldargs, update_checker):
        """Utility for doing compact element updates during comprehension.

        Add ``arg`` to the ``oldargs`` list, and add ``True`` to the
        ``update_checker`` list.

        :param arg:            placeholder name to process
        :type arg:             str
        :param oldargs:        current list of placeholder names in element
        :type oldargs:         str
        :param update_checker: list used to track whether this function has
                               been called during the comprehension
        :type update_checker:  list[bool]

        """
        oldargs.append(arg)
        update_checker.append(True)
        return oldargs

    cmd_group_args = []
    for arg in placeholders_set:
        cmd_group = commands_by_placeholder[arg]
        update_checker = []
        # The syntax here is a bit much, but the gist is: if there's already
        # an element in this list with the same command group, add this
        # placeholder to the list of placeholders there, using the
        # args_updater function. For all other elements that don't match the
        # command group, leave them unchanged.
        cmd_group_args = [
            (group, args_updater(arg, group_args, update_checker))
            if group == cmd_group
            else (group, group_args)
            for (group, group_args) in cmd_group_args
        ]
        # If args_updater was not called above, i.e. there was no element
        # with a matching command group, then let's add one.
        if not update_checker:
            newentry = (cmd_group, [arg])
            cmd_group_args.append(newentry)
    cmd_group_args.sort(key=sortfunc, reverse=True)
    print_command_groups(cmd_group_args, command_dicts_by_cmd)


def print_multi(commands, ignore_env):
    """Pretty-print the info for multiple commands.

    Call :func:`init_print_info_collections` to build the info and
    associations that will be used for pretty-printing. At the coarsest
    level, placeholders will be bucketed as "required values", "optional
    values", and "toggles".

    Define a sort function that will be used when arranging placeholders by
    "command group" (commands that use those placeholders)... we want to
    list larger groups first, and among command-groups of the same size, order
    them by how early their first command appears in the list of commands.

    For each of the top-level buckets of placeholder types (if non-empty),
    pretty-print a header and call :func:`print_placeholders_set` to print
    the info for those placeholders.

    :param commands:   names of commands to print
    :type commands:    list[str]
    :param ignore_env: whether to ignore the effects of chaintool-env; will
                       be True for non-sequence prints
    :type ignore_env:  bool

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    num_commands = len(commands)
    command_dicts = []
    command_dicts_by_cmd = dict()
    commands_by_placeholder = dict()
    placeholders_sets = {"required": set(), "optional": set(), "toggle": set()}
    commands_display = init_print_info_collections(
        commands,
        command_dicts,
        command_dicts_by_cmd,
        commands_by_placeholder,
        placeholders_sets,
        ignore_env,
    )

    def cga_sort_keyvalue(cmd_group_args):
        """Sort function for command-groups-with-placeholders.

        First priority: size of group. Second priority: how close is the first
        command in the group to the head of the overall commands list.

        :param cmd_group_args:       list of 2-tuples containing: a list of
                                     commands, and a list of placeholders
                                     those commands have in common
        :type cmd_group_args:        list[tuple[list[str], list[str]]]

        :returns: sort key value
        :rtype:   int

        """
        group = cmd_group_args[0]
        return num_commands * len(group) + (
            num_commands - commands.index(group[0]) - 1
        )

    print(Fore.MAGENTA + "** commands:" + Fore.RESET)
    print(commands_display)
    print()
    print(Fore.MAGENTA + "** commandline formats:" + Fore.RESET)
    for cmd_dict in command_dicts:
        print(Fore.CYAN + "* " + cmd_dict["name"] + Fore.RESET)
        print(cmd_dict["cmdline"])
    if placeholders_sets["required"]:
        print()
        print(Fore.MAGENTA + "** required values:" + Fore.RESET)
        print_placeholders_set(
            placeholders_sets["required"],
            cga_sort_keyvalue,
            command_dicts_by_cmd,
            commands_by_placeholder,
        )
    if placeholders_sets["optional"]:
        print()
        print(Fore.MAGENTA + "** optional values with default:" + Fore.RESET)
        print_placeholders_set(
            placeholders_sets["optional"],
            cga_sort_keyvalue,
            command_dicts_by_cmd,
            commands_by_placeholder,
        )
    if placeholders_sets["toggle"]:
        print()
        print(
            Fore.MAGENTA
            + "** toggles with untoggled:toggled values:"
            + Fore.RESET
        )
        print_placeholders_set(
            placeholders_sets["toggle"],
            cga_sort_keyvalue,
            command_dicts_by_cmd,
            commands_by_placeholder,
        )
    print()
    return 0
