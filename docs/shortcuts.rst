Shortcuts
=========

chaintool's "shortcuts" support is a feature meant to cut down on the amount of typing necessary to run commands and sequences. Instead of typing ``chaintool cmd run foo`` you can just type ``foo``; instead of ``chaintool seq run bar`` just type ``bar``.

.. note::

   If you're using shortcuts, this means that you have an additional consideration when naming a command or sequence: don't give them the same name as an existing program or shell builtin. For example if you're working in Linux and you name a sequence ``ls``, you're going to be causing yourself some future confusion!

Any additional ``run`` arguments (e.g. those for setting placeholder values) can be given to a shortcut. In fact, if you have :ref:`bash completions<configuration:completions>` configured for chaintool, the Tab-completion behavior for a shortcut invocation is exactly the same as it would be for the "real" chaintool invocation for running that command or sequence.

Shortcuts become enabled when you have the necessary directory included in your :envvar:`PATH` environment variable. If you use ``chaintool x info`` to see the directories used by chaintool, the "Directory used to store command/sequence data, shortcuts, and other scripts" is the relevant one here; the scripts that implement shortcuts will be in the "shortcuts" subdirectory of that.

You could manually add that "shortcuts" directory to your :envvar:`PATH`, but it is usually better to let chaintool do it for you. If you use ``chaintool x shortcuts`` to handle :ref:`shortcuts configuration<configuration:shortcuts>`, chaintool will be able to keep track of that configuration. ``chaintool x info`` will then show you which shell startup script contains that :envvar:`PATH` modification, and ``chaintool x shortcuts`` can be used again if necessary to automatically remove that change.
