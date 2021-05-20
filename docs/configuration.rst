*************
Configuration
*************

Once chaintool is installed, a bit of initial configuration can help you get the best user experience. The :command:`chaintool x` command group ("x" for "extended functionality") is used for this setup.

You can always come back and do this later, if you'd rather first check out the :doc:`User Guide<user-guide>` for an overview and some examples!


Shortcuts
=========

What are Shortcuts?
-------------------

When you created a "command" or "sequence" with chaintool, a "shortcut" script with the same name will automatically be created as well. That shortcut can then be used to run the associated command or sequence. So for example if you have created a sequence ``foo``, you *could* execute it by entering this at your shell prompt:

.. code-block:: none

   chaintool seq run foo

But if you have shortcuts properly configured, you could alternately just run it like this:

.. code-block:: none

   foo

Setup
-----

"Configuring shortcuts" means making sure that a necessary directory is part of your :envvar:`PATH` environment variable. This isn't rocket science, but chaintool still provides a little automated assistance to set up (or tear down) this modification of :envvar:`PATH`.

To get into this configuration assistant, after you have installed chaintool invoke this command:

.. code-block:: none

   chaintool x shortcuts

This will start an interactive process for managing the shortcuts configuration.

First, if you have previously used this command to insert a :envvar:`PATH` modification into one of your shell startup scripts, it will ask whether you want to keep that configuration; if you do want to keep it, then that's the end of the process.

On the other hand, if you don't have the :envvar:`PATH` modification (or if you chose to remove it), chaintool will ask if you want to insert the :envvar:`PATH` modification into a startup script. You can enter the filepath of the script you wish to modify. If your login shell is bash, chaintool will suggest using :file:`.bashrc` in your home directory, but in any case you can enter what you want here. chaintool trusts you to pick the correct startup script for your situation.

.. note::

   Your selected startup script must be a file that already exists.

FYI chaintool will add lines to the selected script file in the following form:

.. code-block:: bash

   # begin PATH modification for chaintool shortcut scripts
   export PATH=$PATH:/home/bob/.local/share/chaintool/shortcuts
   # end PATH modification for chaintool shortcut scripts

(The actual directory added to :envvar:`PATH` will vary depending on your OS and your home directory path.)

If you leave these lines intact, you can later use :command:`chaintool x shortcuts` to automatically remove them.

Once your shell startup script has been modified, you will need to start a new shell to get the benefit of this new :envvar:`PATH`. From then on, any new command or sequence creation will result in a new shortcut that is immediately available for use.


Completions
===========

.. note::

   If you're not using the bash shell, this section is probably not relevant for you. Some other shells may be able to make use of bash autocompletions through a compatibility feature (e.g. ``bashcompinit`` in zsh) but that is untested.

What are Completions?
---------------------

The bash shell provides nice facilities for "autocompletion" of command-line arguments: type the first few letters of some argument on the command line, then press Tab and the rest of the argument will appear. Or if there are multiple possible arguments that could follow from those initial letters, you will be shown the list of possibilities.

In chaintool's case, this autocompletion is especially handy because many of the possible arguments are generated from the content of the commands and sequences you create. If you're new to chaintool, this won't mean much to you yet... just trust that chaintool can accept a lot of arguments in a lot of forms, so autocompletion is a real quality-of-life feature.

Correct completion for command-line arguments is of course very context-dependent; it is driven by the semantics of the program being invoked and by other arguments that may have already been typed. So bash needs application-specific help in order to perform this trick. The task of "configuring completions" for chaintool means providing the code (in the form of bash functions) that bash will use to do autocompletion for chaintool and for any chaintool shortcut script.

General Configuration
---------------------

Before getting into chaintool-specific setup though, you may want to tweak the overall behavior of autocompletion. One common modification is to have the following line in your :file:`~/.inputrc` file (creating that file if necessary):

.. code-block:: none

   set show-all-if-ambiguous on

This will change the behavior when there are multiple completion possibilities based on what you've typed so far. Normally in that case the first press of the Tab key would just cause a beep, and you would need to press Tab again to see the possible completions. If you make the above change however, the possible completions will be shown (without a beep) the first time you press Tab.

Completions "Style"
-------------------

When it comes to the chaintool-specific setup, an interactive configuration process is available (similar to the shortcuts setup). Unfortunately there's one bit of information that chaintool can't reliably detect on its own, so you'll need to figure it out. The question is this: is your shell currently using the ``bash-completion`` package, version 2.2 or later? 

The ``bash-completion`` package does not enable the basic autocompletion feature -- that's intrinsically part of the bash shell -- but it builds on it. If a recent-enough version of ``bash-completion`` is present, chaintool can use it to allow autocompletions to be enabled immediately for a newly created shortcut script, without requiring you to open a new shell.

You can determine your ``bash-completion`` situation by entering this at your bash shell prompt:

.. code-block:: bash

   type __load_completion >/dev/null 2>&1 && echo yep

If you see "yep" printed, then you do in fact currently have ``bash-completion`` active, and it's version 2.2 or later. If this is the case, you can configure "dynamic" completions in the process described below. Otherwise, you must use "old style" completions.

Setup
-----

To get into this configuration assistant, invoke this command:

.. code-block:: none

   chaintool x completions

This will start an interactive process for managing the completions configuration.

First, if you have previously used this command to set up completions, it will ask whether you want to keep that configuration; if you do want to keep it, then that's the end of the process.

On the other hand, if you don't have completions set up (or if you chose to remove the previous configuration), chaintool will ask if you want to set up "dynamic" or "old style" completions now.

Dynamic
^^^^^^^

Choosing "dynamic" completions will work if you determined (as per above) that you are currently using a recent version of the ``bash-completion`` package.

If you choose "dynamic" completions, then you must identify a directory where ``bash-completion`` will look to find user-specific completion scripts. If you haven't done any special work to explicitly set this directory to an unusual location, then you should just accept the directory that chaintool suggests.

If however you have changed the value of the :envvar:`BASH_COMPLETION_USER_DIR` or :envvar:`XDG_DATA_HOME` environment variables, then the usual default directory will not be correct. If you have *exported* the values of those variables, so that chaintool can see them, chaintool can still suggest the correct directory. If not, you may need to modify the suggestion. Presumably if you have intentionally made such changes then you will know what the correct directory is.

Once you have selected this directory, autocompletions will immediately be supported for the main :command:`chaintool` executable and any shortcuts you create, without the need to start a new shell.

.. note::

   If you attempted to do autocompletions for chaintool *before* running :command:`chaintool x completions`, then ``bash-completion`` may have installed a default completions handler for chaintool. This will prevent the "real" completion support from kicking in. In that case you do need to start a new shell once, after you have done the :command:`chaintool x completions` process.

Old Style
^^^^^^^^^

Choosing "old style" completions will always work, but has drawbacks described in detail at the end of this subsection.

If you choose "old style" completions, then you must choose a startup script to modify. chaintool will suggest using :file:`.bashrc` in your home directory, but in any case you can enter what you want here. chaintool trusts you to pick the correct startup script for your situation.

.. note::

   Your selected startup script must be a file that already exists.

FYI chaintool will add lines to the selected script file in the following form:

.. code-block:: bash

   # begin bash completions support for chaintool
   source /home/bob/.local/share/chaintool/completions/omnibus
   # end bash completions support for chaintool

(The actual filepath sourced will vary depending on your OS and your home directory path.)

If you leave these lines intact, you can later use :command:`chaintool x completions` to automatically remove them.

Once you have configured "old style" completions, you will need to start a new shell to get autocompletion support for the main :command:`chaintool` executable. Also, after any new shortcut creation you must start a new shell for that shortcut to gain autocompletion support.

Current Config and Paths
========================

If you just want to see a dump of chaintool's current configuration, invoke:

.. code-block:: none

   chaintool x info

The output of this command will depend on whether (and how) you have configured shortcuts and completions, and which OS you are using, but here's a sample output:

   | :mono:`Command and sequence names should currently be available to run as`
   | :mono:`shortcuts, because the shortcuts directory is already in your PATH through`
   | :mono:`a setting in this file:`
   |   :mono:`/home/bob/.bashrc`
   |
   | :mono:`You currently have dynamic completions enabled, using this directory:`
   |   :mono:`/home/bob/.local/share/bash-completion/completions`
   |
   | :mono:`Directory used to store configuration for shortcuts and completions:`
   |   :mono:`/home/bob/.config/chaintool`
   | :mono:`Directory used to store command/sequence data, shortcuts, and other scripts:`
   |   :mono:`/home/bob/.local/share/chaintool`
   | :mono:`Directory used to store temporary locks:`
   |   :mono:`/home/bob/.cache/chaintool`

The three "app directory" paths shown at the end of this output are normally not of any concern to someone using chaintool, but they're displayed in the interest of full disclosure of chaintool's footprint in your home directory. Also note that the contents of those app directories are intentionally *not* cleared out when chaintool is uninstalled, as they may be used again later if/when chaintool is reinstalled. If you care to completely erase chaintool's configuration and data from your system, then (currently) you would need to manually remove those directories.
