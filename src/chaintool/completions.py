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


__all__ = ['init']

# XXX These individual functions need to:
# - create or delete the script that: sources the helper (if necessary) and
#   invokes complete -F
# - update the omnibus script for all cmds/seqs (non-lazy-load support)
# - if configured for lazy load (via marker file), symlink into that dir

# __all__ = ['init',
#            'create_cmd_completion',
#            'delete_cmd_completion',
#            'create_seq_completion',
#            'delete_seq_completion']


import importlib.resources
import os

from .constants import DATA_DIR


COMPLETIONS_DIR = os.path.join(DATA_DIR, "completions")

os.makedirs(COMPLETIONS_DIR, exist_ok=True)


def init():
    main_script = importlib.resources.read_text(__package__, "chaintool_completion")
    helper_script = importlib.resources.read_text(__package__, "chaintool_run_op_common_completion")
    main_script_out = os.path.join(COMPLETIONS_DIR, "chaintool")
    helper_script_out = os.path.join(COMPLETIONS_DIR, "chaintool_run_op_common")
    with open(main_script_out, 'w') as outstream:
        outstream.write(main_script)
    with open(helper_script_out, 'w') as outstream:
        outstream.write(helper_script)
