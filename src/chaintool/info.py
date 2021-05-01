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

"""Dump info about current configuration."""


__all__ = ["dump"]


from . import completions_setup
from . import shared
from . import shortcuts_setup


def dump():
    """Print current appdirs and shortcuts/completions configuration.

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    print()
    if not shortcuts_setup.probe_config(False):
        print("Shortcuts are not enabled.")
        print()
    if not completions_setup.probe_config(False):
        print("bash completions are not enabled.")
        print()
    print("Directory used to store shortcuts/completions configuration:")
    print("  " + shared.CONFIG_DIR)
    print("Directory used to store command and sequence data:")
    print("  " + shared.DATA_DIR)
    print("Directory used to store temporary locks:")
    print("  " + shared.CACHE_DIR)
    print()
    return 0
