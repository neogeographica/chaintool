.. role:: py:mod(literal)
.. role:: command(literal)

.. _header_section:

chaintool: a tool to chain tools into toolchains
===============================================================

.. image:: https://img.shields.io/pypi/l/chaintool
   :target: https://www.gnu.org/licenses/gpl-3.0.html
   :alt: license

.. image:: https://img.shields.io/pypi/pyversions/chaintool.svg
   :target: https://www.python.org/
   :alt: supported Python versions

.. image:: http://img.shields.io/pypi/v/chaintool.svg
   :target: https://pypi.python.org/pypi/chaintool
   :alt: current version

.. _blurb_section:

**chaintool** is a utility to manage certain kinds of "toolchain" usecases that require executing a sequence of commandlines.

This is not a replacement for a build system, but rather an alternative to creating one-off scripts for usecases that fit the following characteristics:

- A fixed sequence of command invocations. The sequence may terminate on error, but otherwise the commandlines to invoke are not affected by the output of previous commands.
- The commands accept a large variety of command-line arguments, and many of those are being used. Some of these arguments will very rarely be changed. Some of these might occasionally be changed but should have sensible defaults. Some will be changed frequently, perhaps even from run to run.
- For correct usage, certain arguments across different commands must be supplied with the same value, or with related values (e.g. options that reference the same file basename but with different extensions).

chaintool provides a way to define and manage that sequence of commandlines, and generate a "shortcut" script that will run it. The arguments you care about surfacing will be available as command-line options for this shortcut, and will flow down to generate the correct arguments for the relevant commands in the sequence.

Obviously, you could instead just manually author a script that contains the command invocations. But using chaintool helps you generate a variation on a sequence, or run an existing sequence with different arguments, in a quick and more error-free way. You don't have to dig through any of the arguments you don't currently care about, you don't run the risk of forgetting to edit some commandline as you change occurrences of a common value, you won't break anything with a copy-and-paste error or accidental deletion, and you won't have to remember the specific syntax for options that you need to flip between excluding/including.

If you're using the bash shell, another major benefit from chaintool is that the shortcuts you create will have full autocompletion support, for the options that you have defined and chosen to surface.

chaintool also helps export definitions for these command sequences that are fairly portable. If there are paths or argument values that are specific to a particular OS, or to a particular user's environment, those values can be left as required parameters that an importer must fill in before running the sequence.


.. _prerequisites_section:

Prerequisites
-------------

Python 3.7 or later is required.

There are no other absolute requirements, but there are some prerequisites that are helpful for autocompletion of command-line arguments:

First, the bash shell is required for the autocompletion feature to work at all. Some other shells may be able to make use of bash autocompletions through a compatibility feature (e.g. ``bashcompinit`` in zsh) but that is untested.

Having a *recent* version of bash also helps to avoid a couple of annoying issues:

- If you don't have bash 5 or later, double-quoting a placeholder value on the command line will break autocompletions for all subsequent arguments.
- If you don't have bash 4 or later, the lack of the :command:`compopt` builtin will cause filename completions for directory paths (e.g. when composing the file argument to import/export) to be awkward... you'll get a trailing space instead of a trailing slash. Other quirks are also possible, and in general this code is not often tested with bash versions older than 4.0.

If you need to update bash, the process will be specific to your operating system. macOS is likely to have an extremely old version of bash by default, and an update is definitely recommended in that case; FYI one solution for updating bash on macOS is to `use the homebrew package manager`_. On Linux systems, if you are able to get at least bash 4 from your official OS repositories, that's probably good enough; installing some newer-than-approved version of bash in a Linux system is doable but also potentially a source of future problems.

Finally, version 2.2 or later of the ``bash-completion`` package is a nice-to-have. This package does not enable the basic autocompletion feature -- that's intrinsically part of the bash shell -- but it builds on it. If a recent-enough version of ``bash-completion`` is present, chaintool can use it to allow autocompletions to be enabled immediately for a newly created "shortcut" script, without requiring you to open a new shell.

The process of getting or updating ``bash-completion`` will again be something specific to your system. You can use your package manager to check whether you have ``bash-completion`` installed (and which version). Also if you use :command:`chaintool x completions` to interactively configure the completions feature, it can walk you through a method of checking whether a recent-enough version of ``bash-completion`` is installed and in use by your shell.

.. _use the homebrew package manager: https://itnext.io/upgrading-bash-on-macos-7138bd1066ba


.. _installation_section:

Installation
------------

The latest version of chaintool (hosted at the `Python Package Index`_, PyPI) can be installed via Python's :py:mod:`pip` package manager. For example, if you are installing for Python 3.7, you would invoke pip as follows:

.. code-block:: none

   python3.7 -m pip install chaintool

Similarly, an existing chaintool installation can be updated to the latest version:

.. code-block:: none

   python3.7 -m pip install --upgrade chaintool

An alternative to installing from PyPI is to install chaintool directly from GitHub. For example the following command would install the version of chaintool currently on the main branch:

.. code-block:: none

   python3.7 -m pip install git+https://github.com/neogeographica/chaintool

Note that it's preferable to use an explicit Python-version executable like :command:`python3.7` instead of just :command:`python3`. If you install using :command:`python3` and it is a symbolic link that is later changed to point to some different Python version, chaintool will stop working. (This has to do with how the package-installation process hardcodes Python executable paths into the command scripts that it generates.)

If you later need to uninstall chaintool (with :command:`pip uninstall`) and then re-install it for a newer version of Python, your local data and configuration will be preserved. 

.. _Python Package Index: https://pypi.org/project/chaintool


.. _configuration_section:

Configuration
-------------

Once chaintool has been installed, it can help you configure your shell environment to enable support for shortcuts and autocompletions... in most cases it is able to do this setup automatically for you.

The documentation goes into this in more detail, but running :command:`chaintool x completions` will get you into an interactive process for setting up the autocompletions feature, and :command:`chaintool x shortcuts` is a similar helper for the shortcuts feature.

Depending on your configuration, you may need to start a new shell for these features to be available.

For more details, see the full documentation linked below.

.. _documentation_section:

XXX Eventually need a link here to the relevant readthedocs page.
