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

"""Constants shared by the package's modules."""


__all__ = ['CACHE_DIR',
           'CONFIG_DIR',
           'DATA_DIR',
           'MSG_WARN_PREFIX']


import appdirs

from colorama import Fore


APP_NAME = "chaintool"
APP_AUTHOR = "Joel Baxter"
CACHE_DIR = appdirs.user_cache_dir(APP_NAME, APP_AUTHOR)
CONFIG_DIR = appdirs.user_config_dir(APP_NAME, APP_AUTHOR)
DATA_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)

MSG_WARN_PREFIX = Fore.YELLOW + "Warning:" + Fore.RESET
