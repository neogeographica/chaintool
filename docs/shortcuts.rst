Shortcuts
=========

Summary
-------

chaintool's "shortcuts" support is a feature meant to cut down on the amount of typing necessary to run commands and sequences. Instead of typing ``chaintool cmd run foo`` you can just type ``foo``; instead of ``chaintool seq run bar`` just type ``bar``.

.. note::

   If you're using shortcuts, this means that you have an additional consideration when naming a command or sequence: don't give them the same name as an existing program or shell builtin. For example if you're working in Linux and you name a sequence ``ls``, you're going to be causing yourself some future confusion!

Any additional ``run`` arguments (e.g. those for setting placeholder values) can be given to a shortcut. In fact, if you have :ref:`bash completions<configuration:completions>` configured for chaintool, the Tab-completion behavior for a shortcut invocation is exactly the same as it would be for the "real" chaintool invocation for running that command or sequence.

Configuration
-------------

Shortcuts become enabled when you have the necessary directory included in your :envvar:`PATH` environment variable. If you use ``chaintool x info`` to see the directories used by chaintool, the "Directory used to store command/sequence data, shortcuts, and other scripts" is the relevant one here; the scripts that implement shortcuts will be in the "shortcuts" subdirectory of that.

You could manually add that "shortcuts" directory to your :envvar:`PATH`, but it is usually better to let chaintool do it for you. If you use ``chaintool x shortcuts`` to handle :ref:`shortcuts configuration<configuration:shortcuts>`, chaintool will be able to keep track of that configuration. ``chaintool x info`` will then show you which shell startup script contains that :envvar:`PATH` modification, and ``chaintool x shortcuts`` can be used again if necessary to automatically remove that change.

Optional Run Flags
------------------

So to recap, a shortcut is a way of executing a ``cmd run`` or ``seq run`` operation. This means that the optional ``-q`` (or ``--quiet``) flag is available. For ``seq run``, the optional ``-i`` (or ``--ignore-errors``) flag is also available.

As mentioned in the :ref:`overview<overview:invoking chaintool>`, you can't intermix optional flags with positional arguments. Since a shortcut already has one positional argument "baked in" (i.e. the command/sequence name), this means that if you want to use these flags you'll have to put them at the very end of any other arguments you may be specifying. (Also as described in the overview, there are reasons that the autocomplete logic can't help with these flags in this case, so you'll have to type them yourself.)

Going back to the example from the overview, maybe you have a command named ``foo`` that you want to run with placeholder argument ``arg=wow``. With a shortcut, you could run it like this:

.. code-block:: none

   foo arg=wow

Now if you want to use the ``-q`` flag, this will work fine:

.. code-block:: none

   foo arg=wow -q

But this form is **not** allowed:

.. code-block:: none

   foo -q arg=wow

A little annoying! Fortunately the need for using run flags is apparently rare, but it's a limitation that would be nice to deal with in future development.
