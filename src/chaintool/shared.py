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

"""Constants and utility functions shared by the package's modules."""


__all__ = [
    "CACHE_DIR",
    "CONFIG_DIR",
    "DATA_DIR",
    "LOCATIONS_DIR",
    "MSG_WARN_PREFIX",
    "init",
    "errprint",
    "is_valid_name",
    "editline",
    "check_shell",
    "delete_if_exists",
    "read_choicefile",
    "write_choicefile",
    "get_startup_script_path",
    "remove_script_additions",
]


import os
import readline
import shutil
import sys
import string

import appdirs

from colorama import Fore


APP_NAME = "chaintool"
APP_AUTHOR = "Joel Baxter"
CACHE_DIR = appdirs.user_cache_dir(APP_NAME, APP_AUTHOR)
CONFIG_DIR = appdirs.user_config_dir(APP_NAME, APP_AUTHOR)
DATA_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
LOCATIONS_DIR = os.path.join(CONFIG_DIR, "locations")

MSG_WARN_PREFIX = Fore.YELLOW + "Warning:" + Fore.RESET


def init():
    """Initialize module at load time.

    Called from ``__init__`` when package is loaded. Creates the locations
    directory, inside the config appdir, if necessary.

    """
    os.makedirs(LOCATIONS_DIR, exist_ok=True)


def errprint(msg):
    """Print an error message.

    Print ``msg`` to stderr, in red.

    :param msg: error message
    :type msg:  str

    """
    sys.stderr.write(Fore.RED + msg + Fore.RESET + "\n")


def is_valid_name(name):
    """Check that the given string is valid as a cmd or seq name.

    Return ``False`` if name is emptystring or contains whitespace.

    :param name: name to check
    :type name:  str

    :returns: whether the name is valid
    :rtype:   bool

    """
    if not name:
        return False
    for char in name:
        if char in string.whitespace:
            return False
    return True


def editline(prompt, oldline):
    """Interactively edit a string.

    Print the ``prompt`` and the old/default string value (``oldline``), and
    allow the user to readline-edit that string value. When the user presses
    enter, return that edited value.

    :param prompt:  prompt to print before the editable string
    :type prompt:   str
    :param oldline: original value to present for editing
    :type oldline:  str

    :returns: user-edited new version of the string
    :rtype:   str

    """

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


def check_shell():
    """Attempt to determine the user's login shell.

    The first bool in the returned tuple simply indicates whether the SHELL
    environment variable is set. The second bool is true only if SHELL is set
    to a string that ends in "/bash".

    :returns: a tuple of: whether there is a SHELL, and whether it is bash
    :rtype:   tuple[bool, bool]

    """
    is_shell = "SHELL" in os.environ
    is_bash_login_shell = False
    if is_shell:
        is_bash_login_shell = os.environ["SHELL"].endswith("/bash")
    return is_shell, is_bash_login_shell


def delete_if_exists(filepath):
    """Delete a file, silently succeeding if it is already gone.

    Delegate to os.remove and swallow any FileNotFoundError exception.

    :param filepath: file to delete
    :type filepath:  str

    """
    try:
        os.remove(filepath)
    except FileNotFoundError:
        pass


def read_choicefile(choicefile_path):
    """Return the file contents (choice string), if the file exists.

    Return a string containing the contents of the given file, or ``None``
    if that file does not exist.

    :param choicefile_path: file to read
    :type choicefile_path:  str

    :returns: file contents if it exists
    :rtype:   str | None

    """
    if not os.path.exists(choicefile_path):
        return None
    with open(choicefile_path, "r") as instream:
        return instream.read()


def write_choicefile(choicefile_path, choice):
    """Write the choice string to the file, or delete the file if no choice.

    Write the given ``choice`` string to the given file, or delete that file
    (via :func:`delete_if_exists`) if ``choice`` is ``None``.

    :param choicefile_path: file to write/delete
    :type choicefile_path:  str
    :param choice:          file contents if any
    :type choice:           str | None

    """
    if choice is None:
        delete_if_exists(choicefile_path)
        return
    with open(choicefile_path, "w") as outstream:
        outstream.write(choice)


def default_startup_script():
    """Return a reasonable default value for a shell startup script path.

    If :func:`check_shell` thinks that this user has a bash login shell,
    return the path to a .bashrc file in the user's home directory. Otherwise,
    return emptystring.

    :returns: suggested startup script path (may be emptystring)
    :rtype:   str

    """
    _, is_bash_login_shell = check_shell()
    if is_bash_login_shell:
        return os.path.expanduser(
            os.path.expandvars(os.path.join("~", ".bashrc"))
        )
    return ""


def get_startup_script_path():
    """Interactively get a shell startup script path from the user

    Starting with a suggested value from :func:`default_startup_script`, ask
    the user to enter/edit the path. Return what the user provides, or
    ``None`` if that filepath does not exist.

    :returns: startup script pathm, if valid
    :rtype:   str | None

    """
    startup_script_path = editline(
        "Path to your shell startup script: ", default_startup_script()
    )
    startup_script_path = os.path.expanduser(
        os.path.expandvars(startup_script_path)
    )
    print()
    if not os.path.exists(startup_script_path):
        print("File does not exist.")
        print()
        return None
    return startup_script_path


def remove_script_additions(script_path, begin_mark, end_mark, expected_lines):
    """Strip lines delineated by comment markers from a script file.

    Open the given script file and look for the marker comments. See if
    removing lines from the beginning marker to the end marker would result
    in the expected number of lines removed. If so: make a backup copy of the
    script file, write back the updated script file with lines removed, and
    return ``True``.

    Otherwise leave the script file unmodified and return ``False``.

    :param script_path:    path to the scriptfile to edit
    :type script_path:     str
    :param begin_mark:     comment line marking start of section-to-remove
    :type begin_mark:      str
    :param end_mark:       comment line marking end of section-to-remove
    :type end_mark:        str
    :param expected_lines: number of lines that should be removed, including
                           the marker comments
    :type expected_lines:  int

    :returns: whether lines were removed from the script file
    :rtype:   bool

    """
    try:
        with open(script_path, "r") as instream:
            script_lines = instream.readlines()
    except FileNotFoundError:
        print("That file no longer exists.")
        print()
        return True
    new_script_lines = []
    to_remove = []
    removing = False
    for line in script_lines:
        if begin_mark in line:
            removing = True
            to_remove.append(line)
        elif end_mark in line:
            removing = False
            to_remove.append(line)
        elif not removing:
            new_script_lines.append(line)
        else:
            to_remove.append(line)
    if len(to_remove) != expected_lines:
        print(
            "It doesn't look like this program can safely auto-remove the"
            " configuration\nfrom that file. If you want to use this program"
            " to help put the configuration\nin some other file, first you"
            " will need to manually remove it from this\ncurrent location."
        )
        print()
        return False
    backup_path = script_path + ".bak"
    shutil.copy2(script_path, backup_path)
    with open(script_path, "w") as outstream:
        outstream.writelines(new_script_lines)
    shutil.copystat(backup_path, script_path)
    print(
        "Current configuration has been removed. The previous version of the"
        " file has\nbeen saved at:\n  "
        + backup_path
    )
    print()
    return True
