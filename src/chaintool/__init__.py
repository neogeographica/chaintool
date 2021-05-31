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

"""Initialize the package's modules."""


__all__ = ["init", "current_export_schema_ver"]


import atexit
import sys

import colorama

from packaging.version import Version

from . import completions
from . import item_io
from . import locks
from . import shared
from . import shortcuts


__version__ = "0.3.0.dev0"

INTERNAL_SCHEMA_CHANGE_VERSIONS = ["0.3.0"]
EXPORT_SCHEMA_CHANGE_VERSIONS = ["0.3.0"]


if sys.version_info < (3, 7):
    sys.stderr.write("\nPython version 3.7 or later is required.\n")
    sys.exit(1)


def schema_ver_for_package_ver(query_package_ver_str, schema_change_versions):
    """Return the requested schema version for a chaintool package version.

    This function takes the base of the given package version (e.g. if given
    "0.3.0.dev0" it will work with "0.3.0") and compares it to the
    ``schema_change_versions`` to determine the appropriate schema version
    number used by that version of chaintool.

    :param query_package_ver_str:  package version to calculate schema for
    :type query_package_ver_str:   str
    :param schema_change_versions: package versions at which schema changed
    :type schema_change_versions:  list[str]

    :returns: schema version for the given package version, or None if the
              input version string could not be evaluated
    :rtype:   int | None

    """
    query_package_ver = Version(Version(query_package_ver_str).base_version)
    if query_package_ver >= Version(schema_change_versions[-1]):
        return len(schema_change_versions)
    for prev_schema_ver, package_ver_str in reversed(
        list(enumerate(schema_change_versions))
    ):
        if query_package_ver < Version(package_ver_str):
            return prev_schema_ver
    return None


def internal_schema_ver_for_package_ver(query_package_ver_str):
    """Return the internal schema version for a chaintool package version.

    Delegate to :func:`schema_ver_for_package_ver` using the given
    ``query_package_ver_str`` and the schema-change info from
    :const:`INTERNAL_SCHEMA_CHANGE_VERSIONS`.

    :param query_package_ver_str: package version to calculate schema for
    :type query_package_ver_str:  str

    :returns: internal schema version for the given package version, or None
              if the input version string could not be evaluated
    :rtype:   int | None

    """
    return schema_ver_for_package_ver(
        query_package_ver_str, INTERNAL_SCHEMA_CHANGE_VERSIONS
    )


def init_modules():
    """If schema is changing, check for validity; then init modules.

    Initialize the non-schema-dependent :mod:`colorama`, :mod:`.shared`, and
    :mod:`.locks` modules. Then grab the meta-lock.

    While holding the meta-lock, load the schema version for the current
    stored config/data and compare it to the schema version used by our
    current package. If the stored version is larger, that's bad... a newer
    chaintool that uses a different format has been running, and has changed
    the schema to something we don't understand. In that case, exit with error.

    Otherwise, call the init functions for :mod:`.item_io`, :mod:`.shortcuts`,
    and :mod:`.completions`. Pass them the old and new schema versions in case
    they need to update their stored data formats.

    Finally update the last-stored-version info for schema, the chaintool
    package, and Python (last two are just informative). Release the meta-lock
    and return.

    """
    colorama.init()
    atexit.register(colorama.deinit)
    shared.init()
    locks.init()
    with locks.META_LOCK:
        this_schema_ver = internal_schema_ver_for_package_ver(__version__)
        last_schema_ver = shared.get_last_schema_version()
        last_chaintool_ver = shared.get_last_chaintool_version()
        last_python_ver = shared.get_last_python_version()
        if last_schema_ver > this_schema_ver:
            shared.errprint(
                "\nA more recent version of chaintool ({}) has been run on"
                " this system (using Python version {}). The version of"
                " chaintool you are attempting to run ({}) cannot use the"
                " newer config/data format that is now in place.\n".format(
                    last_chaintool_ver, last_python_ver, __version__
                )
            )
            sys.exit(1)
        item_io.init(last_schema_ver, this_schema_ver)
        shortcuts.init(last_schema_ver, this_schema_ver)
        completions.init(last_schema_ver, this_schema_ver)
        shared.set_last_schema_version(this_schema_ver)
        shared.set_last_chaintool_version(__version__)
        this_python_ver = sys.version
        if " " in this_python_ver:
            this_python_ver = this_python_ver[: this_python_ver.index(" ")]
        shared.set_last_python_version(this_python_ver)


def init():
    """Idempotent initialization of chaintool's files and configurations.

    This function must be called at least once before using chaintool for
    the first time, and after any upgrade to a newer chaintool version. It
    is automatically invoked with every use of the chaintool command; you
    would only need to explicitly invoke it if you are calling functions in
    the chaintool modules from other code.

    """
    init_modules()


def current_export_schema_ver():
    """Return the export schema version understood by this chaintool version.

    Delegate to :func:`schema_ver_for_package_ver` using the current
    chaintool version and the schema-change info from
    :const:`EXPORT_SCHEMA_CHANGE_VERSIONS`.

    :returns: export schema version for the given package version, or None
              if the current chaintool version string could not be evaluated
    :rtype:   int | None

    """
    return schema_ver_for_package_ver(
        __version__, EXPORT_SCHEMA_CHANGE_VERSIONS
    )
