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

"""Implementation of commands that run internally to chaintool.

Implements chaintool-copy, chaintool-del, and chaintool-env "virtual tools"
that run in Python code here rather than in a subprocess shell on the OS.

"""


__all__ = ["copytool", "deltool", "envtool", "dispatch", "update_env"]


import re
import shlex
import shutil

from . import shared


ENV_OP_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*)=(.*)$")


def env_op_parse(env_op):
    """Parse a chaintool-env argument into a tuple.

    Return ``None`` if the ``env_op`` argument is not in the correct format.
    Otherwise return a 2-tuple containing the destination placeholder name and
    the value to apply.

    :param env_op: an argument to chaintool-env
    :type env_op:  str

    :returns: parse results
    :rtype:   tuple[str, str] | None

    """
    match = ENV_OP_RE.match(env_op)
    if match is None:
        shared.errprint("Bad chaintool-env argument format.")
        return None
    dst_name = match.group(1)
    src_value = match.group(2)
    return (dst_name, src_value)


def copytool(copy_args, _run_args):
    """Implement chaintool-copy for platform-independent file copy.

    Bail out with error if ``copy_args`` has other than 2 elements.

    Otherwise, treat first element as copy source and second element as
    copy dest. Delegate to shutil.copy2 to do the copy. If copy2 raises any
    exception, return an error.

    :param copy_args: arguments to chaintool-copy
    :type copy_args:  list[str]
    :param _run_args: arguments to "seq/cmd run", not used in this function
    :type _run_args:  list[str]

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    if len(copy_args) != 2:
        shared.errprint(
            "chaintool-copy takes two arguments: sourcepath and destpath"
        )
        return 1
    try:
        shutil.copy2(copy_args[0], copy_args[1])
    except Exception as copy_exception:  # pylint: disable=broad-except
        print(repr(copy_exception))
        return 1
    print('copied "{}" to "{}"'.format(copy_args[0], copy_args[1]))
    return 0


def deltool(del_args, _run_args):
    """Implement chaintool-del for platform-independent file delete.

    Bail out with error if ``del_args`` has other than 1 element.

    Otherwise, treat that element as the filepath to delete. Delegate to
    :func:`.shared.delete_if_exists` to do the delete. If that raises any
    exception, return an error.

    :param del_args:  arguments to chaintool-del
    :type del_args:   list[str]
    :param _run_args: arguments to "seq/cmd run", not used in this function
    :type _run_args:  list[str]

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    if len(del_args) != 1:
        shared.errprint("chaintool-del takes one argument: filepath")
        return 1
    try:
        shared.delete_if_exists(del_args[0])
    except Exception as del_exception:  # pylint: disable=broad-except
        print(repr(del_exception))
        return 1
    print('deleted "{}"'.format(del_args[0]))
    return 0


def envtool(env_args, run_args):
    """Implement chaintool-env to modify runtime placeholder values.

    Parse the given chaintool-env arguments (in ``env_args``) to get a list of
    environment ops. Bail out with error if any are invalid.

    Iterate through the list of ops. Since the ``run_args`` will be applied
    sequentially for subsequent commands, it is sufficient just to add the
    var assignment generated by each op as a new element at the end of
    ``run_args``.

    :param env_args:  arguments to chaintool-env
    :type env_args:   list[str]
    :param run_args:  arguments to "seq/cmd run"; to modify
    :type run_args:   list[str]

    :returns: exit status code (0 for success, nonzero for error)
    :rtype:   int

    """
    ops = [env_op_parse(arg) for arg in env_args]
    if None in ops:
        return 1
    for env_op in ops:
        (dst_name, src_value) = env_op
        dst_currently_set = False
        for arg in run_args:
            if arg[0] == "+":
                continue
            name = arg.partition("=")[0]
            if name == dst_name:
                dst_currently_set = True
                break
        if dst_currently_set:
            print("{} already has value; not modifying".format(dst_name))
            continue
        new_arg = "=".join([dst_name, src_value])
        print(new_arg)
        run_args.append(new_arg)
    return 0


VTOOL_DISPATCH = {
    "chaintool-copy": copytool,
    "chaintool-del": deltool,
    "chaintool-env": envtool,
}


def dispatch(cmdline, run_args):
    """Run a "virtual tool" for a commandline, if appropriate.

    If the first word of the given commandline is not a key in
    :const:`VTOOL_DISPATCH`, return ``None``.

    Otherwise pass the remaining words from that commandline, as well as any
    runtime-specified placeholder args, to the virtual tool function selected
    by that first word.

    :param cmdline:   commandline for the command to run
    :type cmdline:    str
    :param run_args:  arguments to "seq/cmd run"; to modify
    :type run_args:   list[str]

    :returns: exit status code, or None if no virtual tool
    :rtype:   int | None

    """
    tokens = shlex.split(cmdline)
    if tokens[0] not in VTOOL_DISPATCH:
        return None
    return VTOOL_DISPATCH[tokens[0]](tokens[1:], run_args)


def update_env(cmdline, env_values):
    """Get the optional placeholder values set by a commandline.

    This utility function is invoked during printing placedholder info for
    commands in a sequence; it determines whether a command affects how
    placeholder values will be shown for subsequent commands in the sequence.

    Only the "chaintool-env" command can affect subsequent commands in this
    way, so return immediately if the first ``cmdline`` word doesn't match
    that. Also return if there is any error parsing the remaining words of a
    "chaintool-env" command into a list of environment ops.

    Iterate through the list of ops and add each op's placeholder name/value
    to the ``env_values`` dict.

    :param cmdline:    commandline for the command to examine
    :type cmdline:     str
    :param env_values: dict of optional placeholder values, keyed by
                       placeholder name; to modify
    :type env_values:  dict[str, str]

    """
    tokens = shlex.split(cmdline)
    if tokens[0] != "chaintool-env":
        return
    env_args = tokens[1:]
    ops = [env_op_parse(arg) for arg in env_args]
    if None in ops:
        return
    for env_op in ops:
        (dst_name, src_value) = env_op
        env_values[dst_name] = src_value
