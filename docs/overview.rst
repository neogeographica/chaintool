Overview
========

The :doc:`introduction<index>` to these docs described chaintool usecases in broad terms, but it didn't go into specifics. This overview will get more concrete about the common chaintool concepts, terminology, and actions. For clarity, we'll use very simple (and sometimes contrived) examples... but don't worry, a :doc:`more interesting example<example>` is queued up next.

Commands and Sequences
----------------------

The core objects that chaintool works with are "commands" and "sequences". A command is a name associated with a commandline; a sequence is a name associated with a list of command names.

So for example we could have a command named ``foo`` that consists of this commandline:

.. code-block:: none

   echo "hi!"

And a command named ``bar`` that consists of this commandline:

.. code-block:: none

   echo "ho!"

If we were to run the ``foo`` command through chaintool, we would see the following output, showing us both the commandline as well as any output printed by its execution:

   | :cyan:`echo "hi!"`
   |
   | :mono:`hi!`

Now let's say that we also have a sequence ``doit`` that consists of these command names:

.. code-block:: none

   foo bar

If we were to run the ``doit`` sequence through chaintool, we would see this output:

   | :magenta:`* running command 'foo':`
   |
   | :cyan:`echo "hi!"`
   |
   | :mono:`hi!`
   |
   | :magenta:`* running command 'bar':`
   |
   | :cyan:`echo "ho!"`
   |
   | :mono:`ho!`

So far, not too confusing, but also not too exciting.

Placeholders
------------

The key ingredient for making these commands/sequences more interesting is the "placeholder". Managing common variations in commandlines is a primary function of chaintool, and placeholders are the mechanism for expressing and choosing among those variations. So, it's time to introduce the placeholder concept. (Details about syntax and usage will come later.)

The basic placeholder is simply a name enclosed in curly brackets. This kind of placeholder is used to substitute arbitrary strings into a commandline.

For example, let's say that the commandline for ``foo`` was the following:

.. code-block:: none

   echo "{message}"

In this example, ``message`` is the name of the placeholder. When the ``foo`` command is run, a string value must be supplied for the ``message`` placeholder, and it will take the place of that entire placeholder token (including the curly brackets) in the command line. So if ``message`` is assigned a value of ``yo!``, the commandline will be executed as ``echo "yo!"``.

A placeholder can also have a default value, for example:

.. code-block:: none

   echo "{message=hi!}"

In this case, if a value is not supplied for ``message`` at runtime, then the string ``hi!`` will be used to replace that entire placeholder token.

A different kind of placeholder, a "toggle", is used to choose between two possible string substitutions. For example, if we only needed to choose between two possible messages ``hello!`` and ``goodbye!``, we could express that as follows:

.. code-block:: none

   echo "{+seeya=hello!:goodbye!}"

That example defines a toggle named ``+seeya`` (the leading ``+`` symbol marks it as a toggle). Normally the commandline will be executed as ``echo "hello!"``, but the ``+seeya`` toggle can be used to change it to ``echo "goodbye!"``.

The full section on :doc:`placeholders<placeholders>` will go into detail about placeholder syntax and usage.

Invoking chaintool
------------------

Let's now talk about the general syntax of running the :command:`chaintool` executable. Broadly speaking a chaintool invocation will look like this:

.. code-block:: none

   chaintool <commandgroup> <operation> [flag flag ...] [argument argument ...]

The "commandgroup" identifies a group of related tasks, while the "operation" is a specific task. In some cases a commandgroup only has one task, so there is no operation; in those cases the invocation would look like this:

.. code-block:: none

   chaintool <commandgroup> [flag flag ...] [argument argument ...]

The optional flags are specific to the chosen commandgroup/operation and can be specified in single-hyphen single-letter form (e.g. ``-i``) or double-hyphen full-word form (e.g. ``--ignore-errors``). To finish out the commandline, the commandgroup/operation may have one or more required positional arguments and may support additional optional positional arguments.

For example, the following invocation would create one of the variations on the ``foo`` command that was mentioned in the previous subsection:

.. code-block:: none

   chaintool cmd set foo 'echo "{message=hi!}"'

In that example, the commandgroup is ``cmd``, the operation is ``set``, and there are two required positional arguments: the name of the command, and the associated commandline. The ``set`` operation also happens to support a ``-q`` or ``--quiet`` flag which suppresses the printing of command info after the operation finishes, so we could have used that like so:

.. code-block:: none

   chaintool cmd set -q foo 'echo "{message=hi!}"'

Once that command has been created, we could execute it like so:

.. code-block:: none

   chaintool cmd run foo message=whoa

In that case the first (required) positional argument after ``cmd run`` specifies the command to run, and then we can specify additional arguments to manipulate the command's placeholders.

The subsections below, and the other pages of this user guide, go into more detail about how to use each of the commandgroups and their operations. Two more things should be mentioned at this point:

- chaintool has a multi-level help system to describe the available commandline options. :command:`chaintool -h` will describe all of the commandgroups and (where relevant) list their operations. If a commandgroup has multiple operations, then :command:`chaintool <commandgroup> -h` will show the help for all of its operations, and :command:`chaintool <commandgroup> <operation> -h` will show the help for a single operation. (The :doc:`reference<reference>` section of this user guide replicates that help text.)

- If you have configured :ref:`bash completions<configuration:completions>` for chaintool, you can use Tab to help autocomplete available options on the commandline. This includes the optional positional arguments for placeholder settings; e.g. in the example above typing ``chaintool cmd run foo m`` followed by Tab would autocomplete to ``chaintool cmd run foo message=hi\!``, showing the available placeholder and its current default value, quoted/escaped as necessary, for you to edit.

Command and Sequence Authoring
------------------------------

The ``cmd`` and ``seq`` commandgroups are used to work with commands and sequences, respectively.

You can create or update a command with the ``cmd set`` operation, of the form:

.. code-block:: none

   chaintool cmd set [-q] <cmdname> <cmdline>

``<cmdname>`` is the name of the command to create or update, and can be any sequence of non-whitespace characters. ``<cmdline>`` is the commandline to associate with that name; keep in mind that this is a single argument and so likely will need to be appropriately quoted/escaped to deal with spaces or special characters in it. The optional ``-q`` flag suppresses the pretty-printed command info that would normally happen after the set.

Similarly you can create or update a sequence using ``seq set``:

.. code-block:: none

   chaintool seq set [-f] [-q] <seqname> <cmdname> [<cmdname> ...]

``<seqname>`` is the name of the sequence to create or update. It must be followed by one or more command names to compose the sequence. The optional ``-q`` flag behaves similarly here. The optional ``-f`` (or ``--force``) flag allows you to specify command names that do not currently exist.

While the ``set`` operations can be useful, they can also be tedious if you just want to modify an existing command or sequence. Also, in the case of ``cmd set``, the proper quoting/escaping of the commandline argument can be frustrating to figure out. For those reasons, often you will want to use ``edit`` instead of ``set``:

.. code-block:: none

   chaintool cmd edit [-q] <cmdname>

   chaintool seq edit [-f] [-q] <seqname>

When you invoke an ``edit`` operation, you are presented with a prompt where you can type the commandline or list of command names. No special quoting/escaping required. If you are modifying an existing command or sequence, the existing content will be placed there for you to edit.

.. note::

   During an ``edit`` operation, several familiar editing control-characters are supported, such as Ctrl-A to jump to beginning of line and Ctrl-E to jump to end. And for ``seq edit``, you can use tab-completion on the command names that make up the sequence.

Once you have some commands and/or sequences, you can use ``cmd list`` and ``seq list`` to see their names. You can also pretty-print the info for a command, or for all the commands in a sequence:

.. code-block:: none

   chaintool cmd print <cmdname>

   chaintool seq print <seqname>

Or pretty-print the info for all commands using just :command:`chaintool print`. The placeholder information shown in the output of these ``print`` operations will be covered in more detail in the full section on :doc:`placeholders<placeholders>`.

The final part of the authoring lifecycle is of course deleting stuff. You can use the ``del`` operation to delete multiple commands or sequences:

.. code-block:: none

   chaintool cmd del [-f] <cmdname> [<cmdname> ...]

   chaintool seq del <seqname> [<seqname> ...]

The optional ``-f`` flag for ``cmd del`` allows you to delete commands that are currently being used by some sequence.

XXX general mention of bash completions?

Command and Sequence Execution
------------------------------

XXX run

XXX briefly mention shortcuts, link to full page

XXX general mention of bash completions?

Updating Placeholder Values
---------------------------

XXX vals

XXX general mention of bash completions?
