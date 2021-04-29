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

"""Locking system to preserve consistency under simultaneous operations.

Acquire WRITE inventory lock to create or delete item-of-type.
Any inventory lock prevents other create/delete for item-of-type.

Acquire WRITE item lock to create, delete, or modify an item.
Any item lock prevents other create/delete/modify for that item.

This simple R/W lock implementation does not enforce all the guardrails
necessary to prevent deadlock. Because its usage is pretty simple in this
program, we just have to follow conventions to avoid deadlock (knock on
wood). The conventions are:

- lock acquisition order: seq inventory, seq item, cmd inventory, cmd item
- for holding multiple item locks, acquire in sorted item name order (this
  is actually enforced as long as you use multi_item_lock to do it)

Also note that item locks (and in some cases inventory locks) are released
only when the program exits, using an atexit handler. Operations are meant
to be invoked one per program instance, using the CLI.

"""


__all__ = [
    "LockType",
    "init",
    "inventory_lock",
    "release_inventory_lock",
    "item_lock",
    "multi_item_lock",
]


import atexit
import copy
import enum
import glob
import os
import time

import filelock
import psutil

from . import shared
from .shared import CACHE_DIR


LOCKS_DIR = os.path.join(CACHE_DIR, "locks")

META_LOCK = filelock.FileLock(os.path.join(CACHE_DIR, "metalock"))
LOCKS_PREFIX = os.path.join(LOCKS_DIR, "")

MY_PID = str(os.getpid())


class LockType(enum.Enum):
    """Enum used to differentiate readlocks and writelocks."""

    READ = "read"
    WRITE = "write"


def init():
    """Initialize module at load time.

    Called from ``__init__`` when package is loaded. Creates the locks
    directory, inside the cache appdir, if necessary.

    """
    os.makedirs(LOCKS_DIR, exist_ok=True)


def locker_pid(lock_path):
    """Return the PID of the process that created a lock.

    Extract the PID from the suffix of the lockfile, and return it as an int.

    :param lock_path: lockfile
    :type lock_path:  str

    :returns: PID of the lock owner
    :rtype:   int

    """
    return int(lock_path[lock_path.rindex(".") + 1 :])


def remove_dead_locks(lock_paths):
    """Delete lockfiles whose owner process is gone.

    Get the list of PIDs for current active processes. For each of the given
    lockfiles, extract its PID, if the PID is not in the active-PIDs list then
    delete the lockfile.

    :param lock_paths: lockfiles to check
    :type lock_paths:  list[str]

    """
    current_pids = psutil.pids()
    for path in lock_paths:
        if locker_pid(path) not in current_pids:
            shared.delete_if_exists(path)


def lock_internal(lock_type, prefix):
    """Common lock-creation code.

    First determine what existing locks would block the creation of this lock.
    If this lock is a writelock, then any other lockfile with the same prefix
    (scope) will block it. Otherwise it is only blocked by writelocks with the
    same prefix.

    Now loop indefinitly trying to create the lock:

    Holding the ``META_LOCK`` used to protect lockfile modifications, check
    for conflicting locks. If there are conflicting locks we will invoke
    :func:`remove_dead_locks` just in case, then loop back to try again.

    If no conflicting locks, then create this lockfile, and register an atexit
    handle that will delete it when this program exits.

    :param lock_type: whether this is writelock or readlock
    :type lock_type:  LockType.WRITE | LockType.READ
    :param prefix:    the non-type, non-PID portion of the lock name,
                      indicating scope
    :type prefix:     str

    """
    if lock_type == LockType.WRITE:
        conflict_pattern = prefix + ".*"
    else:
        conflict_pattern = ".".join([prefix, LockType.WRITE.value, "*"])
    first_try = True
    while True:
        with META_LOCK:
            conflicting_locks = glob.glob(conflict_pattern)
            conflicting_locks = [
                lck for lck in conflicting_locks if locker_pid(lck) != MY_PID
            ]
            if not conflicting_locks:
                lock_path = ".".join([prefix, lock_type.value, MY_PID])
                atexit.register(shared.delete_if_exists, lock_path)
                with open(lock_path, "w"):
                    pass
                return
            remove_dead_locks(conflicting_locks)
        if not first_try:
            print("waiting on other chaintool process...")
            time.sleep(5)
        else:
            first_try = False


def inventory_lock(item_type, lock_type):
    """Create an inventory lock.

    Delegate to :func:`lock_internal` with a prefix indicating an inventory
    lock for this item type.

    :param item_type: whether this is for commands or sequences
    :type item_type:  "cmd" | "seq"
    :param lock_type: whether this is writelock or readlock
    :type lock_type:  LockType.WRITE | LockType.READ

    """
    prefix = LOCKS_PREFIX + "inventory-" + item_type
    lock_internal(lock_type, prefix)


def release_inventory_lock(item_type, lock_type):
    """Remove an inventory lock.

    Delete the lockfile with matching prefix and lock type, and with a PID
    suffix matching the current process PID.

    :param item_type: whether this is for commands or sequences
    :type item_type:  "cmd" | "seq"
    :param lock_type: whether this is writelock or readlock
    :type lock_type:  LockType.WRITE | LockType.READ

    """
    prefix = LOCKS_PREFIX + "inventory-" + item_type
    lock_path = ".".join([prefix, lock_type.value, MY_PID])
    shared.delete_if_exists(lock_path)


def item_lock(item_type, item_name, lock_type):
    """Create an individual item lock.

    Delegate to :func:`lock_internal` with a prefix indicating an item
    lock for this item type and specific item name.

    :param item_type: whether this is for commands or sequences
    :type item_type:  "cmd" | "seq"
    :param item_name: name of the command or sequence to lock
    :type item_name:  str
    :param lock_type: whether this is writelock or readlock
    :type lock_type:  LockType.WRITE | LockType.READ

    """
    prefix = LOCKS_PREFIX + item_type + "-" + item_name
    lock_internal(lock_type, prefix)


def multi_item_lock(item_type, item_name_list, lock_type):
    """Create multiple item locks.

    Sort the list of item names and then lock each via :func:`item_lock`.

    :param item_type:      whether this is for commands or sequences
    :type item_type:       "cmd" | "seq"
    :param item_name_list: names of the commands or sequences to lock
    :type item_name_list:  list[str]
    :param lock_type:      whether this is writelock or readlock
    :type lock_type:       LockType.WRITE | LockType.READ

    """
    items = copy.deepcopy(item_name_list)
    items.sort()
    for i in items:
        item_lock(item_type, i, lock_type)
