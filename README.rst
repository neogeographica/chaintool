.. _header_section:

chaintool: a tool to chain tools into toolchains
===============================================================

.. image:: http://img.shields.io/pypi/v/chaintool.svg
    :target: https://pypi.python.org/pypi/chaintool
    :alt: current version

.. image:: https://img.shields.io/pypi/pyversions/chaintool.svg
    :target: https://www.python.org/
    :alt: supported Python versions

.. _blurb_section:

**chaintool** is a GPLv3_-licensed tool to manage certain kinds of "toolchain" usecases that require executing a sequence of commandlines.

This is not a replacement for a build system, but rather an alternative to creating one-off scripts for usecases that fit the following characteristics:

- A fixed sequence of command invocations. The sequence may terminate on error, but otherwise the commandlines to invoke are not affected by the output of previous commands.
- The commands accept a large variety of command-line arguments, and many of those are being used. Some of these arguments will very rarely be changed. Some of these might occasionally be changed but should have sensible defaults. Some will be changed frequently, perhaps even from run to run.
- For correct usage, certain arguments across different commands must be supplied with the same value, or with related values (e.g. options that reference the same file basename but with different extensions).

chaintool provides a way to define and manage that sequence of commandlines, and generate a "shortcut" script that will run it. The arguments you care about surfacing will be available as command-line options for this shortcut, and will flow down to generate the correct arguments for the relevant commands in the sequence.

Obviously, you could instead just manually author a script that contains the command invocations. But using chaintool helps you generate a variation on a sequence, or run an existing sequence with different arguments, in a quick and more error-free way. You don't have to dig through any of the arguments you don't currently care about, you don't run the risk of forgetting to edit some commandline as you change occurrences of a common value, you won't break anything with a copy-and-paste error or accidental deletion, and you won't have to remember the specific syntax for options that you need to flip between excluding/including.

If you're using the bash shell, another major benefit from chaintool is that the shortcuts you create will have full autocompletion support, for the options that you have defined and chosen to surface.

chaintool also helps export definitions for these command sequences that are fairly portable. If there are paths or argument values that are specific to a particular OS, or to a particular user's environment, those values can be left as required parameters that an importer must fill in before running the sequence.

.. _GPLv3: http://www.gnu.org/copyleft/gpl.html


.. _prerequisites_section:

Prerequisites
-------------

Python 3.7 or later is required.

There are no other absolute requirements, but there are some prerequisites that are helpful for autocompletion of command-line arguments:

First, the bash shell is required for the autocompletion feature to work at all. Some other shells may be able to make use of bash autocompletions through a compatibility feature (e.g. ``bashcompinit`` in zsh) but that is untested.

Having a *recent* version of bash also helps to avoid a couple of annoying issues:

- If you don't have bash 5 or later, double-quoting a placeholder value on the command line will break autocompletions for all subsequent arguments.
- If you don't have bash 4 or later, the lack of the "compopt" builtin will cause filename completions for directory paths (e.g. when composing the file argument to import/export) to be awkward... you'll get a trailing space instead of a trailing slash.

If you need to update bash, the process will be specific to your platform and package manager. FYI macOS is likely to have an extremely old version of bash by default; for updating bash on macOS, one approach is to `use the homebrew package manager`_.

Finally, the ``bash-completion`` package (version 2.2 or later) is a nice-to-have. This package does not enable the basic autocompletion feature -- that's intrinsically part of the bash shell -- but it builds on it. If that package is present, chaintool can use it to allow autocompletions to be enabled immediately for a newly created "shortcut" script, without requiring you to open a new shell.

You can use your package manager to check whether you have bash-completion installed (and which version). Also if you use "chaintool x completions" to interactively configure the completions feature, it can walk you through a method of checking whether a recent-enough version of the bash-completion package is installed and in use by your shell.

.. _use the homebrew package manager: https://itnext.io/upgrading-bash-on-macos-7138bd1066ba

.. _installation_section:

Installation
------------

The latest version of chaintool (hosted at the `Python Package Index`_, PyPI) can be installed via Python's ``pip`` package manager:

.. code-block:: none

    python3 -m pip install chaintool

Similarly, an existing chaintool installation can be updated to the latest version:

.. code-block:: none

    python3 -m pip install --upgrade chaintool

An alternative to installing from PyPI is to install chaintool directly from GitHub. For example the following command would install the version of chaintool currently on the main branch:

.. code-block:: none

    python3 -m pip install git+https://github.com/neogeographica/chaintool

.. _Python Package Index: https://pypi.org/project/chaintool

.. _configuration_section:

Configuration
-------------

Once chaintool has been installed, it can help you configure your shell environment to enable support for shortcuts and autocompletions... in most cases it is able to do this setup automatically for you.

The documentation goes into this in more detail, but running "chaintool x completions" will get you into an interactive process for setting up the autocompletions feature, and "chaintool x shortcuts" is a similar helper for the shortcuts feature.

Depending on your configuration, you may need to start a new shell for these features to be available.

.. _documentation_section:

Documentation
-------------

XXX Eventually need a link here to the relevant readthedocs page.

