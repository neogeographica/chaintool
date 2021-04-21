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

Implements chaintool-move, chaintool-del, and chaintool-env "virtual tools"
that run in Python code here rather than in a subprocess shell on the OS.

"""


__all__ = ['copytool',
           'deltool',
           'envtool',
           'dispatch',
           'update_env']


import os
import re
import shlex
import shutil

from . import shared


ENV_OP_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*)(\??=)(.*)$")


def env_op_parse(env_op):
    match = ENV_OP_RE.match(env_op)
    if match is None:
        shared.errprint("Bad chaintool-env argument format.")
        return None
    dst_name = match.group(1)
    only_if_dst_unset = (match.group(2)[0] == '?')
    src_value = match.group(3)
    return (dst_name, only_if_dst_unset, src_value)


def copytool(copy_args, _):
    if len(copy_args) != 2:
        shared.errprint(
            "chaintool-copy takes two arguments: sourcepath and destpath")
        return 1
    try:
        shutil.copy2(copy_args[0], copy_args[1])
        print("copied \"{}\" to \"{}\"".format(copy_args[0], copy_args[1]))
        return 0
    except Exception as move_exception:  # pylint: disable=broad-except
        print(repr(move_exception))
    return 1


def deltool(del_args, _):
    if len(del_args) != 1:
        shared.errprint(
            "chaintool-del takes one argument: filepath")
        return 1
    try:
        os.remove(del_args[0])
        print("deleted \"{}\"".format(del_args[0]))
        return 0
    except Exception as del_exception:  # pylint: disable=broad-except
        print(repr(del_exception))
    return 1


def envtool(env_args, run_args):
    ops = [env_op_parse(arg) for arg in env_args]
    if None in ops:
        return 1
    for env_op in ops:
        (dst_name, only_if_dst_unset, src_value) = env_op
        dst_arg_index = None
        for index, arg in enumerate(run_args):
            if arg[0] == '+':
                continue
            name = arg.partition('=')[0]
            if name == dst_name:
                dst_arg_index = index
            # Can't bail out early on finding arg, just in case it was
            # specified multiple times in the run_args... last one counts.
        if only_if_dst_unset and dst_arg_index is not None:
            print("{} already has value; not modifying".format(dst_name))
            continue
        new_arg = '='.join([dst_name, src_value])
        print(new_arg)
        if dst_arg_index is None:
            run_args.append(new_arg)
        else:
            run_args[dst_arg_index] = new_arg
    return 0


VTOOL_DISPATCH = {
    "chaintool-copy": copytool,
    "chaintool-del": deltool,
    "chaintool-env": envtool
}


def dispatch(cmdline, args):
    tokens = shlex.split(cmdline)
    if tokens[0] not in VTOOL_DISPATCH:
        return None
    return VTOOL_DISPATCH[tokens[0]](tokens[1:], args)


def update_env(cmdline, env_constant_values, env_optional_values):
    tokens = shlex.split(cmdline)
    if tokens[0] != "chaintool-env":
        return
    env_args = tokens[1:]
    ops = [env_op_parse(arg) for arg in env_args]
    if None in ops:
        return
    for env_op in ops:
        (dst_name, only_if_dst_unset, src_value) = env_op
        if only_if_dst_unset:
            env_optional_values[dst_name] = src_value
        else:
            env_constant_values.append(dst_name)
