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
Any inventory lock prevents create/delete for item-of-type.

Acquire WRITE item lock to create, delete, or modify an item.
Any item lock prevents other create/delete/modify for that item.

This simple R/W lock implementation does not enforce all the guardrails
necessary to prevent deadlock. Because its usage is pretty simple in this
program, we just have to follow conventions to avoid deadlock (knock on
wood). The conventions are:
  * lock acquisition order: seq inventory, seq item, cmd inventory, cmd item
  * for holding multiple item locks, acquire in sorted item name order (this
    is actually enforced as long as you use multi_item_lock to do it)

Also note that item locks (and in some cases inventory locks) are released
only when the program exits, using an atexit handler. Operations are meant
to be invoked one per program instance, using the CLI.

"""


__all__ = ['LockType',
           'init',
           'inventory_lock',
           'release_inventory_lock',
           'item_lock',
           'multi_item_lock']


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
    os.makedirs(LOCKS_DIR, exist_ok=True)


def locker_pid(lock_path):
    return int(lock_path[lock_path.rindex('.') + 1:])


def remove_dead_locks(lock_paths):
    current_pids = psutil.pids()
    for path in lock_paths:
        if locker_pid(path) not in current_pids:
            shared.delete_if_exists(path)


def lock_internal(lock_type, prefix):
    if lock_type == LockType.WRITE:
        conflict_pattern = prefix + ".*"
    else:
        conflict_pattern = '.'.join([prefix, LockType.WRITE.value, "*"])
    first_try = True
    while True:
        with META_LOCK:
            conflicting_locks = glob.glob(conflict_pattern)
            conflicting_locks = [
                lck for lck in conflicting_locks
                if locker_pid(lck) != MY_PID]
            if not conflicting_locks:
                lock_path = '.'.join([prefix, lock_type.value, MY_PID])
                atexit.register(shared.delete_if_exists, lock_path)
                with open(lock_path, 'w'):
                    pass
                return
            remove_dead_locks(conflicting_locks)
        if not first_try:
            print("waiting on other chaintool process...")
            time.sleep(5)
        else:
            first_try = False


def inventory_lock(item_type, lock_type):
    prefix = LOCKS_PREFIX + "inventory-" + item_type
    lock_internal(lock_type, prefix)


def release_inventory_lock(item_type, lock_type):
    prefix = LOCKS_PREFIX + "inventory-" + item_type
    lock_path = '.'.join([prefix, lock_type.value, MY_PID])
    shared.delete_if_exists(lock_path)


def item_lock(item_type, item_name, lock_type):
    prefix = LOCKS_PREFIX + item_type + "-" + item_name
    lock_internal(lock_type, prefix)


def multi_item_lock(item_type, item_name_list, lock_type):
    items = copy.deepcopy(item_name_list)
    items.sort()
    for i in items:
        item_lock(item_type, i, lock_type)
