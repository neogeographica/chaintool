Advanced Configuration
======================

.. note::

   This section covers rarely-necessary configuration that most users can ignore.


Forcing the Python Version
--------------------------

As mentioned in the :doc:`prerequisites<prerequisites>`, Python 3.7 or later is required to use chaintool. The chaintool installation process checks that you are installing it into the packages for a valid Python version, and any time chaintool is used, it will run using the Python executable that was originally used to install it. Which should be fine.

However:

That assumption -- "the install-time Python is the correct runtime Python to use" -- can possibly be broken by system changes. E.g. maybe you installed using ``python3`` which is a symlink that has now been changed to point at a different Python version. If for some reason you need to be explicit about the version of Python that chaintool is installed for, then you can do that with some additional setup:

To begin with, modify your shell startup script (e.g. :file:`~/.bashrc`) to export the Python-executable-to-use as the value of the :envvar:`CHAINTOOL_PYTHON` environment variable. For example:

.. code-block:: bash

    export CHAINTOOL_PYTHON=python3.9

Once you've done that, you could run chaintool itself explicitly with a particular Python version like so:

.. code-block:: none

    "$CHAINTOOL_PYTHON" -m chaintool <arguments>

However that does require more typing and will prevent chaintool bash completions from triggering. To get around those issues you can create a wrapper script named ``chaintool``, and place it in a directory that is earlier in your :envvar:`PATH` than the "real" ``chaintool`` command. That wrapper script's contents would look something like this:

.. code-block:: bash

    #!/usr/bin/env bash
    "$CHAINTOOL_PYTHON" -m chaintool "$@"

The :envvar:`CHAINTOOL_PYTHON` variable will also be referenced by shortcut scripts and by bash completion code whenever they need to run chaintool or load chaintool modules for some purpose.
