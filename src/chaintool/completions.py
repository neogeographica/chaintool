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

"""Create/delete bash completions for commands and sequences.

The bash function for the autocompletions of the main "chaintool" utility,
and the "complete" command that associates that function with that utility,
are contained in a "main script" file that is placed in the "completions"
directory under the data appdir.

The bash function for shortcut-script autocompletions is defined in a
"helper script" file in the same "completions" directory.

The "completions/shortcuts" directory contains individual files, one per
shortcut, that contain the "complete" command associating that function with
that shortcut.

An "omnibus" file that sources all of the above files is also placed in the
"completions" directory.

If the user has chosen to do old-style (non-dynamic) completions loading,
then the "omnibus" file can be sourced from their shell startup script. This
will define all the necessary functions and run all necessary "complete"
commands, but only at shell startup time (so changes will not be picked up
until a new shell starts).

For dynamic completions loading, the user must specify a directory from which
completion scripts will be lazy-loaded. A file will be placed there which
sources the "main script" file. A file will also be placed there for each
shortcut; each such file will source the "helper script" if necessary and also
run the "complete" command for that shortcut.

"""


__all__ = [
    "init",
    "create_lazyload",
    "delete_lazyload",
    "create_completion",
    "delete_completion",
]


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
    LOCATIONS_DIR, "completions_script_sourcing_script"
)
USERDIR_LOCATION = os.path.join(LOCATIONS_DIR, "completions_lazy_load_userdir")


def init():
    """Initialize module at load time.

    Called from ``__init__`` when package is loaded. Creates the completions
    directory, inside the data appdir, if necessary. Also creates the
    shortcuts completions directory inside that, if necessary.

    Once those directories are ensured, the "main script" and "helper script"
    files can be extracted from the package resources and placed in the
    completions directory. The "omnibus" file is also created there.

    """
    os.makedirs(COMPLETIONS_DIR, exist_ok=True)
    os.makedirs(SHORTCUTS_COMPLETIONS_DIR, exist_ok=True)
    if not os.path.exists(MAIN_SCRIPT_PATH):
        script = importlib.resources.read_text(
            __package__, "chaintool_completion"
        )
        with open(MAIN_SCRIPT_PATH, "w") as outstream:
            outstream.write(script)
    if not os.path.exists(HELPER_SCRIPT_PATH):
        script = importlib.resources.read_text(
            __package__, "chaintool_run_op_common_completion"
        )
        with open(HELPER_SCRIPT_PATH, "w") as outstream:
            outstream.write(script)
    if not os.path.exists(OMNIBUS_SCRIPT_PATH):
        with open(OMNIBUS_SCRIPT_PATH, "w") as outstream:
            outstream.write(
                "source {}\n".format(shlex.quote(MAIN_SCRIPT_PATH))
            )
            outstream.write(
                "source {}\n".format(shlex.quote(HELPER_SCRIPT_PATH))
            )
            outstream.write(
                "ls {0}/* >/dev/null 2>&1 && for s in {0}/*\n".format(
                    shlex.quote(SHORTCUTS_COMPLETIONS_DIR)
                )
            )
            outstream.write("do\n")
            outstream.write('  source "$s"\n')
            outstream.write("done\n")


def write_complete_invoke(outstream, item_name):
    """Write out the "complete" command for a given shortcut.

    :param outstream: stream to write to
    :type outstream:  TextIO
    :param item_name: shortcut name
    :type item_name:  str

    """
    outstream.write("complete -F _chaintool_run_op {}\n".format(item_name))


def create_static(item_name):
    """Create the per-shortcut file in the "completions/shortcuts" directory.

    While this file will only be used for old-style completions, it is always
    generated when a shortcut is created, so that we can just rely on its
    existence to help track which completions should exist, and to be
    available if/when old-style completions are enabled. As this directory is
    a hidden directory under our control, it doesn't hurt.

    :param item_name: shortcut name
    :type item_name:  str

    """
    shortcut_path = os.path.join(SHORTCUTS_COMPLETIONS_DIR, item_name)
    with open(shortcut_path, "w") as outstream:
        write_complete_invoke(outstream, item_name)


def delete_static(item_name):
    """Delete the per-shortcut file in the "completions/shortcuts" directory.

    :param item_name: shortcut name
    :type item_name:  str

    """
    shortcut_path = os.path.join(SHORTCUTS_COMPLETIONS_DIR, item_name)
    shared.delete_if_exists(shortcut_path)


def write_source_if_needed(outstream, test_func_name, script_path):
    """Write out commands to source a script if it has not been sourced.

    Write a sequence of shell commands that will test whether the given
    bash function exists, and if not, source the given script file.

    :param outstream:      stream to write to
    :type outstream:       TextIO
    :param test_func_name: function name to use for existence check
    :type test_func_name:  str
    :param script_path:    script to source if function does not exist
    :type script_path:     str

    """
    outstream.write("if type {} >/dev/null 2>&1\n".format(test_func_name))
    outstream.write("then\n")
    outstream.write("  true\n")
    outstream.write("else\n")
    outstream.write("  source {}\n".format(shlex.quote(script_path)))
    outstream.write("fi\n")


def create_lazyload(item_name):
    """Create the per-shortcut file in the user dir for lazy-load scripts.

    Called when creating a new shortcut if dynamic completions are enabled.
    Also called when enabling dynamic completions when some shortcuts already
    exist.

    Read the user dir location from the ``USERDIR_LOCATION`` choicefile, and
    create the per-shortcut file there that will: source the "main script" if
    necessary, source the "helper script" if necessary, then invoke the
    "complete" command.

    :param item_name: shortcut name
    :type item_name:  str

    """
    userdir = shared.read_choicefile(USERDIR_LOCATION)
    shortcut_path = os.path.join(userdir, item_name)
    with open(shortcut_path, "w") as outstream:
        write_source_if_needed(outstream, "_chaintool", MAIN_SCRIPT_PATH)
        write_source_if_needed(
            outstream, "_chaintool_run_op", HELPER_SCRIPT_PATH
        )
        write_complete_invoke(outstream, item_name)


def delete_lazyload(item_name):
    """Delete the per-shortcut file in the user dir for lazy-load scripts.

    :param item_name: shortcut name
    :type item_name:  str

    """
    userdir = shared.read_choicefile(USERDIR_LOCATION)
    shortcut_path = os.path.join(userdir, item_name)
    shared.delete_if_exists(shortcut_path)


def create_completion(item_name):
    """Create a completion for a shortcut.

    Invoke :func:`create_static` to create the always-generated file for
    old-style completions. Then, if dynamic completions are enabled, also
    invoke :func:`create_lazyload` to create the file in the user dir for
    lazy-load scripts.

    :param item_name: shortcut name
    :type item_name:  str

    """
    create_static(item_name)
    if os.path.exists(USERDIR_LOCATION):
        create_lazyload(item_name)


def delete_completion(item_name):
    """Delete a completion for a shortcut.

    Invoke :func:`delete_static` to delete the always-generated file for
    old-style completions. Then, if dynamic completions are enabled, also
    invoke :func:`delete_lazyload` to delete the file in the user dir for
    lazy-load scripts.

    :param item_name: shortcut name
    :type item_name:  str

    """
    delete_static(item_name)
    if os.path.exists(USERDIR_LOCATION):
        delete_lazyload(item_name)
