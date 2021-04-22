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


__all__ = ['CACHE_DIR',
           'CONFIG_DIR',
           'DATA_DIR',
           'LOCATIONS_DIR',
           'MSG_WARN_PREFIX',
           'init',
           'errprint',
           'is_valid_name',
           'editline',
           'check_shell',
           'delete_if_exists',
           'read_choicefile',
           'write_choicefile',
           'get_startup_script_path',
           'remove_script_additions']


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
    os.makedirs(LOCATIONS_DIR, exist_ok=True)


def errprint(msg):
    sys.stderr.write(Fore.RED + msg + Fore.RESET + '\n')


def is_valid_name(name):
    if not name:
        return False
    for char in name:
        if char in string.whitespace:
            return False
    return True


def editline(prompt, oldline):
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
    is_shell = ("SHELL" in os.environ)
    is_bash_login_shell = False
    if is_shell:
        is_bash_login_shell = os.environ["SHELL"].endswith("/bash")
    return is_shell, is_bash_login_shell


def delete_if_exists(filepath):
    try:
        os.remove(filepath)
    except FileNotFoundError:
        pass


def read_choicefile(choicefile_path):
    if not os.path.exists(choicefile_path):
        return None
    with open(choicefile_path, 'r') as instream:
        return instream.read()


def write_choicefile(choicefile_path, choice):
    if choice is None:
        delete_if_exists(choicefile_path)
        return
    with open(choicefile_path, 'w') as outstream:
        outstream.write(choice)


def default_startup_script():
    _, is_bash_login_shell = check_shell()
    if is_bash_login_shell:
        return os.path.expanduser(
            os.path.expandvars(os.path.join("~", ".bashrc")))
    return ""


def get_startup_script_path():
    startup_script_path = editline(
        "Path to your shell startup script: ",
        default_startup_script())
    startup_script_path = os.path.expanduser(
        os.path.expandvars(startup_script_path))
    print()
    if not os.path.exists(startup_script_path):
        print("File does not exist.")
        print()
        return None
    return startup_script_path


def remove_script_additions(script_path, begin_mark, end_mark, expected_lines):
    try:
        with open(script_path, 'r') as instream:
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
            "It doesn't look like this program can safely auto-remove the "
            "configuration\nfrom that file. If you want to use this program "
            "to help put the configuration\nin some other file, first you "
            "will need to manually remove it from this\ncurrent location.")
        print()
        return False
    backup_path = script_path + ".bak"
    shutil.copy2(script_path, backup_path)
    with open(script_path, 'w') as outstream:
        outstream.writelines(new_script_lines)
    shutil.copystat(backup_path, script_path)
    print(
        "Current configuration has been removed. The previous version of the "
        "file has\nbeen saved at:\n  " + backup_path)
    print()
    return True
