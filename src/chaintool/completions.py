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

"""Create/delete bash completions for commands and sequences."""


__all__ = ['init',
           'create_lazyload',
           'delete_lazyload',
           'create_completion',
           'delete_completion']


import importlib.resources
import os
import shlex

from . import shared
from .shared import DATA_DIR
from .shared import LOCATIONS_DIR


COMPLETIONS_DIR = os.path.join(DATA_DIR, "completions")
SHORTCUTS_COMPLETIONS_DIR = os.path.join(COMPLETIONS_DIR, "shortcuts")
MAIN_SCRIPT = "chaintool"
MAIN_SCRIPT_PATH = os.path.join(COMPLETIONS_DIR, MAIN_SCRIPT)
HELPER_SCRIPT_PATH = os.path.join(COMPLETIONS_DIR, "chaintool_run_op_common")
OMNIBUS_SCRIPT_PATH = os.path.join(COMPLETIONS_DIR, "omnibus")
SOURCESCRIPT_LOCATION = os.path.join(
    LOCATIONS_DIR, "completions_script_sourcing_script")
USERDIR_LOCATION = os.path.join(
    LOCATIONS_DIR, "completions_lazy_load_userdir")


def init():
    os.makedirs(COMPLETIONS_DIR, exist_ok=True)
    os.makedirs(SHORTCUTS_COMPLETIONS_DIR, exist_ok=True)
    if not os.path.exists(MAIN_SCRIPT_PATH):
        script = importlib.resources.read_text(
            __package__,
            "chaintool_completion")
        with open(MAIN_SCRIPT_PATH, 'w') as outstream:
            outstream.write(script)
    if not os.path.exists(HELPER_SCRIPT_PATH):
        script = importlib.resources.read_text(
            __package__,
            "chaintool_run_op_common_completion")
        with open(HELPER_SCRIPT_PATH, 'w') as outstream:
            outstream.write(script)
    if not os.path.exists(OMNIBUS_SCRIPT_PATH):
        with open(OMNIBUS_SCRIPT_PATH, 'w') as outstream:
            outstream.write(
                "source {}\n".format(shlex.quote(MAIN_SCRIPT_PATH)))
            outstream.write(
                "source {}\n".format(shlex.quote(HELPER_SCRIPT_PATH)))
            outstream.write(
                "ls {0}/* >/dev/null 2>&1 && for s in {0}/*\n".format(
                    shlex.quote(SHORTCUTS_COMPLETIONS_DIR)))
            outstream.write(
                "do\n")
            outstream.write(
                "  source \"$s\"\n")
            outstream.write(
                "done\n")


def write_complete_invoke(outstream, item_name):
    outstream.write("complete -F _chaintool_run_op {}\n".format(item_name))


def create_static(item_name):
    shortcut_path = os.path.join(SHORTCUTS_COMPLETIONS_DIR, item_name)
    with open(shortcut_path, 'w') as outstream:
        write_complete_invoke(outstream, item_name)


def delete_static(item_name):
    shortcut_path = os.path.join(SHORTCUTS_COMPLETIONS_DIR, item_name)
    shared.delete_if_exists(shortcut_path)


def write_source_if_needed(outstream, test_func_name, script_path):
    outstream.write(
        "if type {} >/dev/null 2>&1\n".format(test_func_name))
    outstream.write(
        "then\n")
    outstream.write(
        "  true\n")
    outstream.write(
        "else\n")
    outstream.write(
        "  source {}\n".format(shlex.quote(script_path)))
    outstream.write(
        "fi\n")


def create_lazyload(item_name):
    userdir = shared.read_choicefile(USERDIR_LOCATION)
    shortcut_path = os.path.join(userdir, item_name)
    with open(shortcut_path, 'w') as outstream:
        write_source_if_needed(
            outstream, "_chaintool", MAIN_SCRIPT_PATH)
        write_source_if_needed(
            outstream, "_chaintool_run_op", HELPER_SCRIPT_PATH)
        write_complete_invoke(outstream, item_name)


def delete_lazyload(item_name):
    userdir = shared.read_choicefile(USERDIR_LOCATION)
    shortcut_path = os.path.join(userdir, item_name)
    shared.delete_if_exists(shortcut_path)


def create_completion(cmd):
    create_static(cmd)
    if os.path.exists(USERDIR_LOCATION):
        create_lazyload(cmd)


def delete_completion(cmd):
    delete_static(cmd)
    if os.path.exists(USERDIR_LOCATION):
        delete_lazyload(cmd)
