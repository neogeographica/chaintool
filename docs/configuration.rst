Configuration
=================================

Once chaintool is installed, a bit of initial configuration can help you get the best user experience.


Completions
---------------------------------------------------------------

XXX TBD


Shortcuts
---------------------------------------------------------------

XXX TBD


Forcing the Python Version
---------------------------------------------------------------

XXX May delete this whole section. Cf. issue #26 and installation.txt.

.. note::

   This subsection covers some advanced configuration that most users can ignore.

As mentioned in the :doc:`prerequisites <prereqs>`, Python 3.7 or later is required to use chaintool. The chaintool installation process checks that you are installing it into the packages for a valid Python version, and any time chaintool is used, it will run using the Python executable that was originally used to install it. So you can almost certainly skip the rest of this page!

However:

Sometimes system changes can break the assumption of "the install-time Python is the correct runtime Python to use". (E.g. maybe you installed using :command:`python3` which is a symlink that has now been changed to point at some other version.) If for some reason you need to be explicit about the version of Python that chaintool was installed for & is compatible with, then you can.

For starters, you can run chaintool itself explicitly with a particular Python version by using :command:`python -m`, e.g.:

.. code-block:: none

    python3.9 -m chaintool <arguments>

However this does require more typing and will prevent chaintool bash completions from triggering. To get around those issues you can create a wrapper script named :command:`chaintool`, and place it earlier in your :envvar:`PATH` than the "real" :command:`chaintool` command. That wrapper script's contents would look something like this:

.. code-block:: bash

    #!/usr/bin/env bash
    "$CHAINTOOL_PYTHON" -m chaintool "$@"

where :envvar:`CHAINTOOL_PYTHON` is an environment variable that you have exported in some startup script (e.g. :file:`~/.bashrc`) to identify the Python executable to use for chaintool.

The :envvar:`CHAINTOOL_PYTHON` var, if set, is also used by shortcut scripts and by bash completion code.
