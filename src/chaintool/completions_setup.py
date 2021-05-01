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

"""Handle configuring or disabling the bash completions feature."""


__all__ = ["configure", "probe_config"]


import os
import re
import shlex

from . import completions
from . import shared
from .completions import SHORTCUTS_COMPLETIONS_DIR
from .completions import MAIN_SCRIPT, MAIN_SCRIPT_PATH
from .completions import OMNIBUS_SCRIPT_PATH
from .completions import SOURCESCRIPT_LOCATION, USERDIR_LOCATION


BEGIN_MARK = "# begin bash completions support for chaintool"
END_MARK = "# end bash completions support for chaintool"
SOURCE_RE = re.compile(r"(?m)^.*source " + shlex.quote(OMNIBUS_SCRIPT_PATH))


def default_userdir():
    """Find a suggested user directory for bash-completion script lazy loads.

    Used by :func:`get_userdir_path`.

    Work through the priorities and usage for the BASH_COMPLETION_USER_DIR and
    XDG_DATA_HOME environment variables as understood by the bash-completion
    package. If neither of those are set, fall back to using the default:
    $HOME/.local/share/bash-completion/completions

    Note that we can only interrogate those two variables here if they were
    exported, so this is not a bulletproof recommendation.

    :returns: path for the suggested directory
    :rtype:   str

    """
    if "BASH_COMPLETION_USER_DIR" in os.environ:
        userdir = os.path.join(
            os.environ["BASH_COMPLETION_USER_DIR"], "completions"
        )
    else:
        if "XDG_DATA_HOME" in os.environ:
            homedir = os.environ["XDG_DATA_HOME"]
        else:
            homedir = os.environ["HOME"]
        userdir = os.path.join(
            homedir, ".local", "share", "bash-completion", "completions"
        )
    return userdir


def get_userdir_path():
    """Determine the user directory for bash-completion script lazy loads.

    Present the suggestion from :func:`default_userdir` but allow the user
    to edit/replace that as they see fit. Return the user-provided path.

    :returns: path for the chosen directory
    :rtype:   str

    """
    print(
        "Dynamic loading for bash completions supports a per-user directory,"
        " which this\nprogram will use. The directory path shown below is the"
        " one that should work,\nbut if you know differently then you can"
        " change it."
    )
    print()
    userdir_path = shared.editline("Directory path: ", default_userdir())
    userdir_path = os.path.expanduser(os.path.expandvars(userdir_path))
    print()
    return userdir_path


def enable_dynamic(userdir):
    """Set the "dynamic" completions style that uses lazy script loads.

    Called in a situation where completions are currently unconfigured.

    Set the ``USERDIR_LOCATION`` choicefile to the indicated user dir path. If
    it is ``None``, return.

    Create the selected user dir if necessary. Create a script in that dir
    that will source our main completions script. Also create the script for
    each current shortcut there.

    :param userdir: filepath to user dir for lazy loads, if any
    :type userdir:  str | None

    """
    shared.write_choicefile(USERDIR_LOCATION, userdir)
    if userdir is None:
        return
    os.makedirs(userdir, exist_ok=True)
    userdir_script_path = os.path.join(userdir, MAIN_SCRIPT)
    with open(userdir_script_path, "w") as outstream:
        outstream.write("source {}\n".format(shlex.quote(MAIN_SCRIPT_PATH)))
    for item in os.listdir(SHORTCUTS_COMPLETIONS_DIR):
        completions.create_lazyload(item)
    print("bash completions installed for chaintool and its shortcut scripts.")
    print()


def disable_dynamic(userdir):
    """Unset the "dynamic"-style completions.

    Called in a situation where "dynamic"-style completions are currently
    configured.

    Delete all scripts that we created in the user dir. Clear the
    ``USERDIR_LOCATION`` choicefile.

    :param userdir: filepath of current user dir for lazy loads
    :type userdir:  str

    :returns: whether the disable succeeded; currently always returns True
    :rtype:   bool

    """
    shared.delete_if_exists(os.path.join(userdir, MAIN_SCRIPT))
    for item in os.listdir(SHORTCUTS_COMPLETIONS_DIR):
        completions.delete_lazyload(item)
    shared.write_choicefile(USERDIR_LOCATION, None)
    return True


def check_dynamic(userdir):
    """Check the validity of a "dynamic"-style completions configuration.

    Called in a situation where "dynamic"-style completions are currently
    configured.

    If the user dir does not exist or does not contain the file that sources
    our main completions script, clear the ``USERDIR_LOCATION`` choicefile and
    return ``False``. Otherwise return ``True``.

    :param userdir: filepath of current user dir for lazy loads
    :type userdir:  str

    :returns: whether the user dir selection is valid
    :rtype:   bool

    """
    if not os.path.exists(userdir):
        shared.write_choicefile(USERDIR_LOCATION, None)
        print(
            "Dynamic completion loading was previously configured using the"
            " following\ndirectory, but that directory no longer exists:\n  "
            + userdir
        )
        print()
        return False
    if not os.path.exists(os.path.join(userdir, MAIN_SCRIPT)):
        shared.write_choicefile(USERDIR_LOCATION, None)
        print(
            "Dynamic completion loading was previously configured using the"
            " following\ndirectory, but that seems to no longer be true:\n  "
            + userdir
        )
        print()
        return False
    return True


def enable_oldstyle(startup_script_path):
    """Set the old completions style that loads scripts at shell startup.

    Called in a situation where completions are currently unconfigured.

    Set the ``SOURCESCRIPT_LOCATION`` choicefile to the indicated path. If it
    is ``None``, return.

    Write the command that sources our completions scripts into the selected
    script, surrounded by marker comments so that we can later detect/remove
    it.

    :param startup_script_path: filepath of script to modify, if any
    :type startup_script_path:  str | None

    """
    shared.write_choicefile(SOURCESCRIPT_LOCATION, startup_script_path)
    if startup_script_path is None:
        return
    with open(startup_script_path, "a") as outstream:
        outstream.write(BEGIN_MARK + "\n")
        outstream.write("source {}\n".format(shlex.quote(OMNIBUS_SCRIPT_PATH)))
        outstream.write(END_MARK + "\n")
    print(
        "bash completions installed for chaintool and its shortcut scripts."
        " Note that\nbecause these are not dynamically loaded, a new shell is"
        " required in order\nfor any changes to take effect (including this"
        " initial installation)."
    )
    print()


def disable_oldstyle(startup_script_path):
    """Unset the old-style completions.

    Called in a situation where old-style completions are currently configured.

    Use :func:`.shared.remove_script_additions`, and if that succeeds, clear
    the ``SOURCESCRIPT_LOCATION`` choicefile. Finally return whether the
    disable succeeded.

    :param startup_script_path: filepath of currently modified script
    :type startup_script_path:  str

    :returns: whether the disable succeeded
    :rtype:   bool

    """
    unconfigured = shared.remove_script_additions(
        startup_script_path, BEGIN_MARK, END_MARK, 3
    )
    if unconfigured:
        shared.write_choicefile(SOURCESCRIPT_LOCATION, None)
    return unconfigured


def check_oldstyle(startup_script_path):
    """Check the validity of an old-style completions configuration.

    Called in a situation where old-style completions are currently configured.

    If the indicated script does not exist or does not contain the command
    that sources our completions scripts, clear the ``SOURCESCRIPT_LOCATION``
    choicefile and return ``False``. Otherwise return ``True``.

    :param startup_script_path: filepath of currently modified script
    :type startup_script_path:  str

    :returns: whether the script exists and has our modification
    :rtype:   bool

    """
    if not os.path.exists(startup_script_path):
        shared.write_choicefile(SOURCESCRIPT_LOCATION, None)
        print(
            "Old-style completion loading was previously configured using the"
            " following\nfile, but that file no longer exists:\n  "
            + startup_script_path
        )
        print()
        return False
    with open(startup_script_path, "r") as instream:
        startup_script = instream.read()
    if SOURCE_RE.search(startup_script) is None:
        shared.write_choicefile(SOURCESCRIPT_LOCATION, None)
        print(
            "Old-style completion loading was previously configured using the"
            " following\file, but that seems to no longer be true:\n  "
            + startup_script_path
        )
        print()
        return False
    return True


def probe_config(ask_to_change):
    """Determine existing completions setup; optionally offer to change.

    If a completions configuration does not exist, or does not check out as
    valid (via :func:`check_dynamic` or :func`check_oldstyle`), then return
    ``False``.

    Then if ``ask_to_change`` is ``False``, immediately return ``True``.

    Otherwise, ask the user if they want to preserve the existing setup. If
    they do, return ``True``. Otherwise use :func:`disable_dynamic` or
    :func:`disable_oldstyle` to attempt removing the current setup, returning
    the boolean inverse or whatever that disable operation returns.

    :param ask_to_change: whether to offer to change a current valid setup
    :type ask_to_change:  bool

    :returns: whether there is an existing setup that has been preserved
    :rtype:   bool

    """
    userdir_choice = shared.read_choicefile(USERDIR_LOCATION)
    script_choice = shared.read_choicefile(SOURCESCRIPT_LOCATION)
    disable_func = lambda: disable_oldstyle(script_choice)
    if userdir_choice is not None:
        disable_func = lambda: disable_dynamic(userdir_choice)
        if not check_dynamic(userdir_choice):
            return False
        print(
            "You currently have dynamic completions enabled, using this"
            " directory:\n  "
            + userdir_choice
        )
    elif script_choice is not None:
        if not check_oldstyle(script_choice):
            return False
        print(
            "You currently have old-style completions enabled, using this"
            " file:\n  "
            + script_choice
        )
    else:
        return False
    print()
    if not ask_to_change:
        return True
    print("Do you want to leave this configuration as-is? ", end="")
    choice = input("[y/n] ")
    print()
    if choice.lower() != "n":
        return True
    return not disable_func()


def early_bailout():
    """Give the user a chance to bail out if bash is not their login shell.

    If :func:`.shared.check_shell` indicates that the user has bash for a
    login shell, return without bothering them here... everyone will be given
    a later chance to abort once the setup options are described.

    Otherwise, for the non-bash-login-shell case, give the user a chance to
    escape the configuration process right now. (Different verbiage if they do
    not have a login shell at all.)

    :returns: whether to abort the configuration process
    :rtype:   bool

    """
    is_shell, is_bash_login_shell = shared.check_shell()
    if is_shell:
        if is_bash_login_shell:
            return False
        print(
            "You don't appear to be using bash as your login shell. bash"
            " completions\nonly work under bash; are you sure you want to"
            " continue? [n/y] ",
            end="",
        )
    else:
        print(
            "It doesn't look like you're running in a shell. bash completions"
            " only work\nin the bash shell; are you sure you want to"
            " continue? ",
            end="",
        )
    choice = input("[n/y] ")
    print()
    if choice.lower() != "y":
        return True
    return False


def choose_method():
    """Let the user choose the style of completions to set up, or none at all.

    Describe the two available methods. Let the user pick whether they want
    completions configured, and if so then by which method.

    :returns: user's setup choice
    :rtype:   "dynamic" | "old-style" | None

    """
    print(
        "There are two ways to configure bash completions for chaintool. The"
        " correct\nchoice depends on whether the bash-completion package is"
        " installed (and\nactive for your environment), and what version it"
        " is. The rundown:"
    )
    print()
    print(
        "  1: If using bash-completion 2.2 or later, bash completions can be"
        " activated\n     for new shortcut commands as soon as they are"
        " created, in the same shell.\n"
    )
    print(
        "  2: Otherwise, bash completions for a newly created shortcut command"
        " will\n     only be available when a new shell is started."
    )
    print()
    print(
        "Unfortunately it's difficult to discover (from within this program)"
        " FOR SURE\nwhether a recent version of bash-completion is installed"
        " AND is active in\nyour environment. If you want to test this"
        " yourself, run the following\ncommand in a new shell:\n"
    )
    print("  type __load_completion >/dev/null 2>&1 && echo yep")
    print()
    print(
        'If you see "yep" printed when running that command, you have '
        "bash-completion\n2.2 or later active."
    )
    print()
    print("Which configuration do you want to enable?")
    print(
        "  0: No bash completions\n  1: Use dynamic completions (requires"
        " bash-completion 2.2 or later)\n  2: Use old-style completions"
        " (doesn't depend on bash-completion package)"
    )
    choice = input("choose [0/1/2] ")
    print()
    if choice == "1":
        return "dynamic"
    if choice == "2":
        return "old-style"
    return None


def configure():
    """Set up or disable bash autocompletions.

    If there is no current bash autocompletions setup for chaintool, let
    the user choose the style of setup to use (if any). For "dynamic"
    completions with lazy script loads, the default for the necessary user
    directory is taken from :func:`get_userdir_path`; for old-style
    completions the default path of script-to-modify is taken from
    :func:`.shared.get_startup_script_path`. (But in either case the user can
    enter the path of their choice to edit/replace the default.)

    On the other hand if bash autocompletions are currently configured, give
    the user the option of undoing that configuration.

    :returns: exit status code; currently always returns 0
    :rtype:   int

    """
    print()
    if probe_config(True):
        return 0
    # If we reach this point, any existing completions setup has been
    # unconfigured.
    if early_bailout():
        return 0
    method = choose_method()
    if method is None:
        return 0
    if method == "dynamic":
        enable_dynamic(get_userdir_path())
    else:
        enable_oldstyle(shared.get_startup_script_path())
    return 0
