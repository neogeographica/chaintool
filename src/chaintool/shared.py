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


__all__ = ['errprint',
           'is_valid_name',
           'editline']


import readline
import sys
import string

from colorama import Fore


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
