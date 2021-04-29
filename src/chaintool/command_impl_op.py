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

"""Low-level logic for "cmd" operations (other than pretty-printing).

Called from command, sequence, sequence_impl, and xfer modules. Does the
bulk of the work for reading/writing/modifying command definitions.

"""


__all__ = [
    "define",
    "delete",
    "run",
    "vals",
]


import os
import re
import subprocess

from colorama import Fore

from . import command_impl_core
from . import command_impl_print
from . import shared
from . import virtual_tools
from .command_impl_core import CMD_DIR


PLACEHOLDER_RE = re.compile(r"^((?:[^/+=]+/)*)([^+][^=]*)(?:=(.*))?$")
PLACEHOLDER_TOGGLE_RE = re.compile(r"^(\+[^=]+)=([^:]*):(.*)$")
ALPHANUM_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


def remove_if_present(element_to_remove, list_to_modify):
    """Remove item from list if it is a member.

    Utility function used in various spots in this module for an easy
    one-line list-removal operation.

    :param element_to_remove: element to remove from list
    :param list_to_modify:    input list; to modify
    :type list_to_modify:     list[Any]

    """
    if element_to_remove in list_to_modify:
        list_to_modify.remove(element_to_remove)


def explode_literal_braces(value):
    """Return the given string with each curly brace duplicated.

    :param value: input string
    :type value:  str

    :returns: input string with every left/right curly brace replaced by two
              braces of that type
    :rtype:   str

    """
    return value.replace("{", "{{").replace("}", "}}")


def collapse_literal_braces(value):
    """Return the given string with each duplicate curly brace halved.

    :param value: input string
    :type value:  str

    :returns: input string with every duplicate left/right curly brace changed
              to a single brace of that type
    :rtype:   str

    """
    return value.replace("{{", "{").replace("}}", "}")


def stem_modifier(filepath):
    """Strip the final extension, if any, from the given filepath.

    Take the input ``filepath`` string and remove the final "." character and
    all following characters, if any such character exists in the string
    after the final directory separator.

    :param filepath: input filepath
    :type filepath:  str

    :returns: input filepath with extension stripped
    :rtype:   str

    """
    dotpos = filepath.rfind(".")
    if dotpos == -1:
        return filepath
    slashpos = filepath.rfind(os.sep)
    if slashpos > dotpos:
        return filepath
    return filepath[:dotpos]


MODIFIERS_DISPATCH = {
    "dirname": os.path.dirname,
    "basename": os.path.basename,
    "stem": stem_modifier,
}


def valid_modifiers(modifiers):
    """Check whether all of the given modifiers are valid.

    Return ``True`` if and only if every element of the input ``modifiers``
    list is a key in the ``MODIFIERS_DISPATCH`` constant dictionary.

    :param modifiers: modifiers to check
    :type modifiers:  list[str]

    :returns: whether all modifiers in the given list are valid
    :rtype:   bool

    """
    for mod in modifiers:
        if mod not in MODIFIERS_DISPATCH:
            return False
    return True


def populated_modified_values(values_for_names, modifiers_for_names):
    """Update the values dictionary with the requested modified values.

    Iterate through the items of ``modifiers_for_names``. For each modifier
    list associated with a given name: look up the value for that placeholder
    in ``values_for_names``, apply the modifier list to that value to generate
    a new modified value, and store that new value back into
    ``values_for_names`` keyed by the placeholder name with the appropriate
    modifiers prefix added.

    For example let's say placeholder ``"myfile"`` has a value of
    ``"foo/bar.txt"`` in the ``values_for_names`` dict. If we look up
    ``"myfile"`` in the ``modifiers_for_names`` dict and get both the modifier
    list ``["dirname"]`` and also the modifier list ``["basename", "stem"]``,
    then we will do both of the following assignments:

    .. code-block:: python

        values_for_names["dirname/myfile"]="foo"
        values_for_names["basename/stem/myfile"]="bar"

    :param values_for_names:    dict of placeholder values, keyed by
                                placeholder name; to modify
    :type values_for_names:     dict[str, str]
    :param modifiers_for_names: dict of lists of modifier-lists, keyed by
                                placedholder name
    :type modifiers_for_names:  dict[str, list[list[str]]]

    :returns: whether all modifiers in the given list are valid
    :rtype:   bool

    """
    for name, modlist_list in modifiers_for_names.items():
        if name in values_for_names:
            for modlist in modlist_list:
                mod_value = values_for_names[name]
                modifiers_prefix = "/".join(modlist) + "/"
                for modifier in reversed(modlist):
                    mod_value = MODIFIERS_DISPATCH[modifier](mod_value)
                values_for_names[modifiers_prefix + name] = mod_value


def update_runtime_values_from_args(
    values_for_names,
    modifiers_for_names,
    togglevalues_for_names,
    all_args,
    unused_args,
):
    """Update the values dictionary as determined by "run" placeholder args.

    Iterate through the given args and process them by the following rules:

    - If a toggle with values, reject with error.
    - If a bare toggle name, update ``values_for_names`` to have the "on"
      value for that toggle name. Also remove this arg from ``unused_args``.
    - If a placeholder with modifiers, reject with error.
    - If a placeholder without a value specified, reject with error.
    - If a placeholder with a value, update ``values_for_names`` to have that
      value for that placeholder. Also remove this arg from ``unused_args``.

    After that loop, update ``values_for_names`` to have the "off" value for
    any toggles in this command that were not found in those args.

    If any remaining placeholders have neither a default value nor a value
    provided by the args-processing loop above, return an error.

    Finally call :func:`populated_modified_values` to make sure we have the
    necessary modified versions of values available for substitution.

    :param values_for_names:       dict of placeholder values, keyed by
                                   placeholder name; to modify
    :type values_for_names:        dict[str, str]
    :param modifiers_for_names:    dict of lists of modifier-lists, keyed by
                                   placedholder name
    :type modifiers_for_names:     dict[str, list[list[str]]]
    :param togglevalues_for_names: dict of toggle off/on values, keyed by
                                   placeholder name
    :type togglevalues_for_names:  dict[str, [str, str]]
    :param all_args:               placeholder arguments
    :type all_args:                list[str]
    :param unused_args:            placeholder arguments unused by any
                                   command in current sequence; to modify
    :type unused_args:             list[str]

    :returns: whether the modifications are all valid
    :rtype:   bool

    """
    valid_non_toggles = list(values_for_names.keys())
    unactivated_toggles = list(togglevalues_for_names.keys())
    for arg in all_args:
        toggle_match = PLACEHOLDER_TOGGLE_RE.match(arg)
        if toggle_match:
            shared.errprint(
                "Can't specify values for 'toggle' style placeholders such as"
                " '{}' in this operation.".format(toggle_match.group(1))
            )
            return False
        if arg[0] == "+":
            if arg in togglevalues_for_names:
                values_for_names[arg] = togglevalues_for_names[arg][1]
                remove_if_present(arg, unactivated_toggles)
                remove_if_present(arg, unused_args)
            continue
        nontoggle_match = PLACEHOLDER_RE.match(arg)
        if nontoggle_match is None:
            continue
        modifiers_prefix = nontoggle_match.group(1)
        key = nontoggle_match.group(2)
        value = nontoggle_match.group(3)
        if modifiers_prefix:
            shared.errprint(
                "Can't specify modifiers (such as '{}') for placeholders in"
                " this operation.".format(modifiers_prefix)
            )
            return False
        if value is None:
            shared.errprint(
                "Placeholder '{}' specified in args without a value.".format(
                    key
                )
            )
            return False
        if key in valid_non_toggles:
            values_for_names[key] = value
            remove_if_present(arg, unused_args)
    for key in unactivated_toggles:
        values_for_names[key] = togglevalues_for_names[key][0]
    unspecified = [k for k in valid_non_toggles if values_for_names[k] is None]
    if unspecified:
        shared.errprint(
            "Not all placeholders in the commandline have been given a value."
        )
        shared.errprint(
            "Placeholders that still need a value: " + " ".join(unspecified)
        )
        return False
    populated_modified_values(values_for_names, modifiers_for_names)
    return True


def update_default_values_from_args(
    values_for_names, togglevalues_for_names, all_args, unused_args
):
    """Update the values dictionary as determined by "vals" placeholder args.

    Iterate through the given args and process them by the following rules:

    - If a toggle with values, update ``togglevalues_for_names`` to have the
      specified "on" and "off" values for that toggle name. Also remove this
      arg from ``unused_args``.
    - If a bare toggle name, reject with error.
    - If a placeholder with modifiers, reject with error.
    - If a placeholder with or without a value specified, update
      ``values_for_names`` to have the specified value or None (respectively)
      stored for that placeholder. Also remove this arg from ``unused_args``.

    :param values_for_names:       dict of placeholder values, keyed by
                                   placeholder name; to modify
    :type values_for_names:        dict[str, str]
    :param togglevalues_for_names: dict of toggle off/on values, keyed by
                                   placeholder name; to modify
    :type togglevalues_for_names:  dict[str, [str, str]]
    :param all_args:               placeholder arguments
    :type all_args:                list[str]
    :param unused_args:            placeholder arguments unused by any
                                   command in current sequence; to modify
    :type unused_args:             list[str]

    :returns: whether the modifications are all valid
    :rtype:   bool

    """
    valid_non_toggles = list(values_for_names.keys())
    for arg in all_args:
        toggle_match = PLACEHOLDER_TOGGLE_RE.match(arg)
        if toggle_match:
            key = toggle_match.group(1)
            if key in togglevalues_for_names:
                togglevalues_for_names[key] = [
                    toggle_match.group(2),
                    toggle_match.group(3),
                ]
                remove_if_present(arg, unused_args)
            continue
        if arg[0] == "+":
            shared.errprint(
                "'Toggle' style placeholders such as '{}' require accompanying"
                " pre/post values in this operation.".format(arg)
            )
            return False
        nontoggle_match = PLACEHOLDER_RE.match(arg)
        if nontoggle_match is None:
            continue
        modifiers_prefix = nontoggle_match.group(1)
        key = nontoggle_match.group(2)
        value = nontoggle_match.group(3)
        if modifiers_prefix:
            shared.errprint(
                "Can't specify modifiers (such as '{}') for placeholders in"
                " this operation.".format(modifiers_prefix)
            )
            return False
        if key in valid_non_toggles:
            values_for_names[key] = value
            remove_if_present(arg, unused_args)
    return True


def command_with_values(cmd, all_args, unused_args, is_run):
    """Fetch the indicated command dictionary, modified by placeholder args.

    Load the command with :func:`.command_impl_core.read_dict`, returning
    ``None`` if that fails.

    Process the loaded dictionary with either
    :func:`update_runtime_values_from_args` or
    :func:`update_default_values_from_args`, according to the value of
    ``is_run``. (Note that these functions can modify ``unused_args``.)

    If that processing fails, return None; otherwise return the updated
    command dictionary.

    :param cmd:         command to fetch
    :type cmd:          str
    :param all_args:    placeholder arguments
    :type all_args:     list[str]
    :param unused_args: placeholder arguments unused by any command in current
                        sequence; to modify
    :type unused_args:  list[str]
    :param is_run:      whether this is a "run" op (as opposed to "vals")
    :type is_run:       bool

    :returns: the loaded and modified command dictionary, if successful
    :rtype:   dict[str, str] | None

    """
    try:
        cmd_dict = command_impl_core.read_dict(cmd)
    except FileNotFoundError:
        shared.errprint("Command '{}' does not exist.".format(cmd))
        return None
    values_for_names = cmd_dict["args"]
    modifiers_for_names = cmd_dict["args_modifiers"]
    togglevalues_for_names = cmd_dict["toggle_args"]
    if is_run:
        update_success = update_runtime_values_from_args(
            values_for_names,
            modifiers_for_names,
            togglevalues_for_names,
            all_args,
            unused_args,
        )
    else:
        update_success = update_default_values_from_args(
            values_for_names, togglevalues_for_names, all_args, unused_args
        )
    if update_success:
        return cmd_dict
    return None


def process_cmdline(cmdline, handle_placeholder_fun):
    """Modify placeholder tokens in a commandline, using the provided func.

    Walk the commandline looking for tokens enclosed in single curly-braces.
    Pass each such token to the ``handle_placeholder_fun`` and replace it
    with the result of that function. Return the resulting updated
    commandline.

    :param cmdline:                commandline to update
    :type cmdline:                 str
    :param handle_placeholder_fun: function to apply to each placeholder
                                   token in the commandline
    :type handle_placeholder_fun:  Callable[[str], str]

    :returns: the updated commandline
    :rtype:   str

    """
    placeholder = ""
    cmdline_format = ""
    prev_undoubled_brace = None
    for char in cmdline:
        char_is_brace = char in ("{", "}")
        if not placeholder:
            if prev_undoubled_brace == "{" and not char_is_brace:
                placeholder = char
            else:
                cmdline_format += char
        else:
            if char == "}" and prev_undoubled_brace != "}":
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
    """Set/replace the value for an existing placeholder token.

    Note that :func:`update_cmdline` uses a wrapped version of this function
    as the func passed to :func:`process_cmdline` to update an existing
    stored commandline.

    Process the ``placeholder`` input by the following rules:

    - If the placeholder token is for a toggle (with values), modify it so it
    has the desired off/on values according to ``toggle_args_dict``.
    - If the placeholder should not have any default value according to
    ``args_dict``, return the bare placeholder name.
    - If the placeholder should have some default value according to
    ``args_dict``, modify the token so the name is assigned that value.

    Note that if a value happens to contain a curly-brace character, we will
    double that character so that it will eventually be processed correctly
    when Python formats the commandline string.

    Return the modified token. Or unmodified, if no rule applied.

    :param placeholder:      placeholder token to process
    :type placeholder:       str
    :param args_dict:        dict of desired placeholder default values,
                             keyed by placeholder name
    :type args_dict:         dict[str, str]
    :param toggle_args_dict: dict of desired toggle off/on values, keyed by
                             placeholder name
    :type toggle_args_dict:  dict[str, [str, str]]

    :returns: the updated placeholder token for the commandline
    :rtype:   str

    """
    toggle_match = PLACEHOLDER_TOGGLE_RE.match(placeholder)
    if toggle_match:
        key = toggle_match.group(1)
        if key not in toggle_args_dict:
            # Weird, but we'll handle it.
            return placeholder
        untoggled_value = explode_literal_braces(toggle_args_dict[key][0])
        toggled_value = explode_literal_braces(toggle_args_dict[key][1])
        return key + "=" + untoggled_value + ":" + toggled_value
    nontoggle_match = PLACEHOLDER_RE.match(placeholder)
    if nontoggle_match is None:
        # Shouldn't happen if our input vetting was correct.
        modifiers_prefix = ""
        key = placeholder
    else:
        modifiers_prefix = nontoggle_match.group(1)
        key = nontoggle_match.group(2)
    if key not in args_dict:
        # Weird, but we'll handle it.
        return placeholder
    if args_dict[key] is None:
        return modifiers_prefix + key
    value = explode_literal_braces(args_dict[key])
    return modifiers_prefix + key + "=" + value


def update_cmdline(cmd_dict):
    """Make a commandline consistent with (updated) placeholder values.

    Make a wrapper for :func:`handle_update_placeholder` to capture necessary
    command dictionary info about desired placeholder values. This results in
    a function that can update a placeholder token in the commandline. Pass
    the old/outdated commandline and the wrapper function to
    :func:`process_cmdline`; store the resulting updated commandline back into
    the command dictionary.

    :param cmd_dicts: command dictionary; to modify
    :type cmd_dicts:  dict[str, str]

    """

    def handle_update_placeholder_wrapper(placeholder):
        return handle_update_placeholder(
            placeholder, cmd_dict["args"], cmd_dict["toggle_args"]
        )

    cmd_dict["cmdline"] = process_cmdline(
        cmd_dict["cmdline"], handle_update_placeholder_wrapper
    )


def print_errors(error_sets):
    """Print error messages based on the contents of ``error_sets``.

    Processing an input commandline has accumulated info about violations into
    a dictionary where each key is an error category, and the value is a set
    of placeholder tokens that triggered that error. Iterate through the items
    in this dictionary and print messages about those violations.

    :param error_sets: accumulated error info
    :type error_sets:  dict[str, set[str]]

    :returns: whether any error was found and printed
    :rtype:   bool

    """
    error = False
    if error_sets["non_alphanum_names"]:
        error = True
        shared.errprint(
            "Bad placeholder format: "
            + " ".join(error_sets["non_alphanum_names"])
        )
        shared.errprint(
            "Placeholder names must begin with a letter and be composed only"
            " of letters, numbers, and underscores."
        )
        shared.errprint(
            "(Note that this error can also be triggered by syntax mistakes"
            " when trying to specify placeholder default values or toggle"
            " values. Also, if you need a literal brace character to appear in"
            " the commandline, use a double brace.)"
        )
    if error_sets["invalid_modifiers"]:
        error = True
        shared.errprint(
            "Invalid modifiers on these placeholders: "
            + " ".join(error_sets["invalid_modifiers"])
        )
        shared.errprint(
            "Each modifier must be one of: "
            + ", ".join(MODIFIERS_DISPATCH.keys())
        )
    if error_sets["multi_value_names"]:
        error = True
        shared.errprint(
            "Placeholders occurring multiple times but with different"
            " defaults: "
            + " ".join(error_sets["multi_value_names"])
        )
    if error_sets["multi_togglevalue_names"]:
        error = True
        shared.errprint(
            "'Toggle' placeholders occurring multiple times but with different"
            " values: "
            + " ".join(error_sets["multi_togglevalue_names"])
        )
    if error_sets["toggles_without_values"]:
        error = True
        shared.errprint(
            "'Toggle' placeholders specified without values: "
            + " ".join(error_sets["toggles_without_values"])
        )
    if error_sets["toggle_dup_names"]:
        error = True
        shared.errprint(
            "Same placeholder name(s) used for both regular and 'toggle'"
            " placeholders: "
            + " ".join(error_sets["toggle_dup_names"])
        )
    return error


def check_toggle_errors(
    key, value, values_for_names, togglevalues_for_names, error_sets
):
    """Check a toggle-placeholder token in an input commandline for errors.

    Use the provided info to check for violations in toggle placeholder
    syntax. Update ``error_sets`` with any discovered violations.

    :param key:                    placeholder name from the token
    :type key:                     str
    :param value:                  value from the token
    :type value:                   str
    :param values_for_names:       dict of placeholder values, keyed by
                                   placeholder name
    :type values_for_names:        dict[str, str]
    :param togglevalues_for_names: dict of toggle off/on values, keyed by
                                   placeholder name
    :type togglevalues_for_names:  dict[str, [str, str]]
    :param error_sets:             accumulated error info; to modify
    :type error_sets:              dict[str, set[str]]

    """
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


def check_placeholder_errors(  # pylint: disable=too-many-arguments
    key, modifiers, value, values_for_names, togglevalues_for_names, error_sets
):
    """Check a placeholder token in an input commandline for errors.

    If the ``key`` begins with "+", delegate to :func:`check_toggle_errors`.
    Otherwise, use the provided info to check for violations in (non-toggle)
    placeholder syntax. Update ``error_sets`` with any discovered violations.

    :param key:                    placeholder name from the token
    :type key:                     str
    :param modifiers:              list of modifiers from the token
    :type modifiers:               list[str]
    :param value:                  value from the token
    :type value:                   str
    :param values_for_names:       dict of placeholder values, keyed by
                                   placeholder name
    :type values_for_names:        dict[str, str]
    :param togglevalues_for_names: dict of toggle off/on values, keyed by
                                   placeholder name
    :type togglevalues_for_names:  dict[str, [str, str]]
    :param error_sets:             accumulated error info; to modify
    :type error_sets:              dict[str, set[str]]

    """
    if key[0] == "+":
        check_toggle_errors(
            key, value, values_for_names, togglevalues_for_names, error_sets
        )
        return
    if not ALPHANUM_RE.match(key):
        error_sets["non_alphanum_names"].add(key)
    if not valid_modifiers(modifiers):
        error_sets["invalid_modifiers"].add(key)
    if "+" + key in togglevalues_for_names:
        error_sets["toggle_dup_names"].add(key)
    if key in values_for_names:
        if values_for_names[key] != value:
            error_sets["multi_value_names"].add(key)


def handle_set_placeholder(
    placeholder,
    values_for_names,
    modifiers_for_names,
    togglevalues_for_names,
    error_sets,
):
    """Set the value for a placeholder token in input commandline processing.

    Note that :func:`define` uses a wrapped version of this function
    as the func passed to :func:`process_cmdline` to process user input for a
    commandline and generate a resulting format string.

    Process the ``placeholder`` input by the following rules:

    - If the placeholder token is for a toggle (with values), call
      :func:`check_toggle_errors` and store the values in
      ``togglevalues_for_names``.
    - If the placeholder token is for a non-toggle, call
      :func:`check_placeholder_errors` and store the value in
      ``values_for_names`` (storing ``None`` if no value). If there are
      modifiers, add them to the list-of-modifier-lists stored for that
      placeholder name in ``modifiers_for_names``.

    Note that if an input value happens to contain a double-curly-brace, we
    will collapse that to a single brace when storing the value.

    Return the placeholder name as extracted from the token, prefixed with
    any modifiers. Or the unmodified token, if no rule applied.

    :param placeholder:            placeholder token to process
    :type placeholder:             str
    :param values_for_names:       dict of placeholder values, keyed by
                                   placeholder name; to modify
    :type values_for_names:        dict[str, str]
    :param modifiers_for_names:    dict of lists of modifier-lists, keyed by
                                   placedholder name; to modify
    :type modifiers_for_names:     dict[str, list[list[str]]]
    :param togglevalues_for_names: dict of toggle off/on values, keyed by
                                   placeholder name; to modify
    :type togglevalues_for_names:  dict[str, [str, str]]
    :param error_sets:             accumulated error info; to modify
    :type error_sets:              dict[str, set[str]]

    :returns: the replacement token for the commandline
    :rtype:   str

    """
    toggle_match = PLACEHOLDER_TOGGLE_RE.match(placeholder)
    if toggle_match:
        key = toggle_match.group(1)
        untoggled_value = collapse_literal_braces(toggle_match.group(2))
        toggled_value = collapse_literal_braces(toggle_match.group(3))
        value = [untoggled_value, toggled_value]
        check_toggle_errors(
            key, value, values_for_names, togglevalues_for_names, error_sets
        )
        togglevalues_for_names[key] = value
        return key
    nontoggle_match = PLACEHOLDER_RE.match(placeholder)
    if nontoggle_match is None:
        # Placeholder name format error checks will trigger later.
        modifiers_prefix = ""
        key = placeholder
        value = None
    else:
        modifiers_prefix = nontoggle_match.group(1)
        key = nontoggle_match.group(2)
        value = nontoggle_match.group(3)
        if value is not None:
            value = collapse_literal_braces(value)
    modifiers = modifiers_prefix.split("/")[:-1]
    check_placeholder_errors(
        key,
        modifiers,
        value,
        values_for_names,
        togglevalues_for_names,
        error_sets,
    )
    values_for_names[key] = value
    if modifiers:
        if key in modifiers_for_names:
            modifiers_for_names[key].append(modifiers)
        else:
            modifiers_for_names[key] = [modifiers]
    return modifiers_prefix + key


def define(cmd, cmdline, overwrite, print_after_set, compact):
    """Create or update a command to consist of the given commandline.

    Do some initial validation of ``cmd`` and ``cmdline`` to check that they
    are non-empty and consist of legal characters.

    Make a wrapper for :func:`handle_set_placeholder` to capture the mutable
    containers that we'll be updating. This results in a function that can
    accumulate placeholder and error info while processing the placeholder
    tokens. Pass the input commandline and the wrapper function to
    :func:`process_cmdline` to get the format string for the commandline.

    Call :func:`print_errors` to print about any detected errors, and if there
    are any, bail out with error status.

    Store the input commandline, the generated format string, and the
    accumulated placeholder info in the command dictionary.

    Finally, if ``print_after_set`` is ``True``, pretty-print the command that
    we just created/updated.

    :param cmd:             name of command to create/update
    :type cmd:              str
    :param cmdline:         commandline
    :type cmdline:          str
    :param overwrite:       whether to allow if command already exists
    :type overwrite:        bool
    :param print_after_set: whether to automatically trigger "print" operation
                            at the end
    :type print_after_set:  bool
    :param compact:         whether to reduce the use of newlines (used when
                            caller is processing many commands)
    :type compact:          bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    if not compact:
        print()
    if not shared.is_valid_name(cmd):
        shared.errprint(
            "cmdname '{}' contains whitespace, which is not allowed.".format(
                cmd
            )
        )
        print()
        return 1
    if not cmdline:
        shared.errprint("cmdline must be nonempty.")
        print()
        return 1
    values_for_names = dict()
    modifiers_for_names = dict()
    togglevalues_for_names = dict()
    error_sets = {
        "non_alphanum_names": set(),
        "invalid_modifiers": set(),
        "multi_value_names": set(),
        "multi_togglevalue_names": set(),
        "toggles_without_values": set(),
        "toggle_dup_names": set(),
    }

    def handle_set_placeholder_wrapper(placeholder):
        return handle_set_placeholder(
            placeholder,
            values_for_names,
            modifiers_for_names,
            togglevalues_for_names,
            error_sets,
        )

    cmdline_format = process_cmdline(cmdline, handle_set_placeholder_wrapper)
    if print_errors(error_sets):
        print()
        return 1
    cmd_dict = {
        "cmdline": cmdline,
        "format": cmdline_format,
        "args": values_for_names,
        "args_modifiers": modifiers_for_names,
        "toggle_args": togglevalues_for_names,
    }
    if overwrite:
        mode = "w"
    else:
        mode = "x"
    try:
        command_impl_core.write_dict(cmd, cmd_dict, mode)
    except FileExistsError:
        print("Command '{}' already exists... not modified.".format(cmd))
        print()
        return 0
    print("Command '{}' set.".format(cmd))
    print()
    if print_after_set:
        command_impl_print.print_one(cmd)
    return 0


def delete(cmd, is_not_found_ok):
    """Delete a command.

    Delete the file of name ``cmd`` in the commands directory.

    If that file does not exist, and ``is_not_found_ok`` is ``False``, then
    raise a ``FileNotFoundError`` exception.

    :param cmd:             names of command to delete
    :type cmd:              str
    :param is_not_found_ok: whether to silently accept already-deleted case
    :type is_not_found_ok:  bool

    :raises: FileNotFoundError if the command does not exist and
             is_not_found_ok is False

    """
    try:
        os.remove(os.path.join(CMD_DIR, cmd))
    except FileNotFoundError:
        if not is_not_found_ok:
            raise


def run(cmd, args, unused_args):
    """Run a command.

    Apply the placeholder values from the ``args`` list to the relevant
    values of the command dictionary, and update ``unused_args``, by calling
    :func:`command_with_values`. If that fails, bail out with error status.

    Generate the commandline to execute by using the keys/values from this
    command dictionary with the command's format string. Invoke
    :func:`.virtual_tools.dispatch` to see whether the command is a "virtual
    tool" that should be executed internally (and do so). If so, then return
    the status from the virtual tool. If not, then execute the commandline
    via subprocess.call and return its exit status.

    Note that :func:`.virtual_tools.dispatch` may modify ``args``.

    :param cmd:         name of command to run
    :type cmd:          str
    :param args:        placeholder arguments for this run; to modify
    :type args:         list(str)
    :param unused_args: placeholder arguments unused by any command in current
                        sequence; to modify
    :type unused_args:  list[str]

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    print()
    cmd_dict = command_with_values(cmd, args, unused_args, True)
    if cmd_dict is None:
        print()
        return 1
    cmdline = cmd_dict["format"].format(**cmd_dict["args"])
    print(Fore.CYAN + cmdline + Fore.RESET)
    print()
    vtool_status = virtual_tools.dispatch(cmdline, args)
    if vtool_status is not None:
        print()
        return vtool_status
    status = subprocess.call(cmdline, shell=True)
    print()
    return status


def vals(cmd, args, unused_args, print_after_set, compact):
    """Update placeholder values for a command.

    Apply the placeholder values from the ``args`` list to the relevant
    values of the command dictionary, and update ``unused_args``, by calling
    :func:`command_with_values`. If that fails, bail out with error status.

    Call :func:`update_cmdline` to update the stored commandline to match the
    new placeholder values, and write back the new command dictionary.

    Finally, if ``print_after_set`` is ``True``, pretty-print the command that
    we just updated.

    :param cmd:             name of command to update
    :type cmd:              str
    :param args:            placeholders to update, with values
    :type args:             list(str)
    :param unused_args:     placeholder arguments unused by any command in
                            current sequence; to modify
    :type unused_args:      list[str]
    :param print_after_set: whether to automatically trigger "print" operation
                            at the end
    :type print_after_set:  bool

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    if not compact:
        print()
    cmd_dict = command_with_values(cmd, args, unused_args, False)
    if cmd_dict is None:
        return 1
    update_cmdline(cmd_dict)
    command_impl_core.write_dict(cmd, cmd_dict, "w")
    print("Command '{}' updated.".format(cmd))
    print()
    if print_after_set:
        command_impl_print.print_one(cmd)
    return 0
