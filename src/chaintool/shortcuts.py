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


# XXX going to change all this...


__all__ = ['write_aliases',
           'write_all_aliases']


import os
import shlex
import sys

from .constants import DATA_DIR


ALIASES_FILE = os.path.join(DATA_DIR, "aliases")


def write_alias_for_item(outstream, chaintool_path, item_type, item_name):
    alias_str = "{} {} run {}".format(
        shlex.quote(chaintool_path), item_type, item_name)
    outstream.write("alias {}={}\n".format(
        item_name, shlex.quote(alias_str)))
    outstream.write(
        "type _chaintool_op_alias > /dev/null 2>&1 && "
        "complete -F _chaintool_op_alias {}\n".format(item_name))


def write_aliases(item_type, item_names, nag=True):
    cmd_aliases_file = ALIASES_FILE + "-cmd"
    seq_aliases_file = ALIASES_FILE + "-seq"
    if not os.path.exists(ALIASES_FILE):
        with open(ALIASES_FILE, 'w') as main_file:
            main_file.write("export CHAINTOOL_ALIASES_NO_NAG=1\n")
            main_file.write("[[ -f {0} ]] && source {0}\n".format(
                shlex.quote(cmd_aliases_file)))
            main_file.write("[[ -f {0} ]] && source {0}\n".format(
                shlex.quote(seq_aliases_file)))
    chaintool_path = os.path.abspath(sys.argv[0])
    if item_type == "cmd":
        outfile = cmd_aliases_file
    else:
        outfile = seq_aliases_file
    with open(outfile, 'w') as outstream:
        for name in item_names:
            write_alias_for_item(outstream, chaintool_path, item_type, name)
    if nag and "CHAINTOOL_ALIASES_NO_NAG" not in os.environ:
        print(
            "chaintool aliases updated. You can make these aliases available "
            "by putting the\nfollowing line into your .bashrc file:")
        print("  source " + shlex.quote(ALIASES_FILE))
        print()
        if "CHAINTOOL_BASH_COMPLETIONS" not in os.environ:
            print(
                "If you want bash completion support, the chaintool-bash-"
                "completion file must be\nsourced BEFORE that aliases file.")
            print()
        print(
            "If you'd rather not worry about any of this and instead just "
            "want to disable\nthis message, you can do so with:")
        print("  export CHAINTOOL_ALIASES_NO_NAG=1")
        print()


def write_all_aliases(cmd_item_names, seq_item_names):
    write_aliases("cmd", cmd_item_names, False)
    write_aliases("seq", seq_item_names, True)
