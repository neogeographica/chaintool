Example
=======

Setup
-----

Your own chaintool usecases will depend heavily on the specific command-line tools you need to work with, so it's unlikely that a simple example -- runnable by most users -- would cover a task that you personally need to do. However, we can put together an example using some common Python tools that will at least illustrate some basic chaintool behaviors.

This example will involve running Python code checkers, or "linters". To follow along with the example exactly as written, you will need the following environment:

- The Python packages :py:mod:`flake8`, :py:mod:`flake8-bugbear`, and :py:mod:`pylint` must be installed.
- You will need some Python code to run the linters against. (The example below will use chaintool's own sourcecode.)
- You must have configured chaintool shortcuts, by using :ref:`chaintool x shortcuts<configuration:shortcuts>`.
- After the initial configuration of chaintool shortcuts you must have started a new shell, so that you now have the updated :envvar:`PATH` environment variable in your current shell.

Ideally you will also be working in a bash shell, specifically, and you have configured chaintool's bash autocompletions by using :ref:`chaintool x completions<configuration:completions>`.


Defining Commands
-----------------

The first part of this example is to define two commands. These will be used to run the ``flake8`` and ``pylint`` command-line tools with desired options.

You could use ``chaintool cmd set`` to create a command in a single stroke, but that can involve figuring out how to properly quote a commandline so that it registers as a single argument. In most cases it's easier to instead use ``chaintool cmd edit`` so you can type or paste the commandline at an interactive prompt.

Let's call these two commands ``myflake8`` and ``mypylint`` to distinguish them from the "real" ``flake8`` and ``pylint`` programs. To create ``myflake8``, invoke:

.. code-block:: none

   chaintool cmd edit myflake8

This will bring up a ``commandline:`` prompt. Since you are editing a command that doesn't exist yet, the commandline-to-edit is empty. At the prompt, paste the following line:

   | :mono:`flake8 --select C,E,F,W,B{+nolong=,B950:} --ignore W503,E203,E501,E731 {target}`

Broadly speaking, we're trying to capture the options we commonly use with that tool. The curly-bracket-enclosed bits express some common variations on those options; we'll describe the specifics of that mechanism in later sections. For now, after you paste the above commandline at the prompt, just press Enter to complete the command creation. chaintool will then print info about the resulting command:

   | :mono:`Command 'myflake8' set.`
   |
   | :magenta:`* commandline format:`
   | :mono:`flake8 --select C,E,F,W,B{+nolong=,B950:} --ignore W503,E203,E501,E731 {target}`
   |
   | :magenta:`* required values:`
   | :mono:`target`
   |
   | :magenta:`* toggles with untoggled:toggled values:`
   | :mono:`+nolong = ,B950:''`

Now let's create the ``mypylint`` command:

.. code-block:: none

   chaintool cmd edit mypylint

And at the ``commandline:`` prompt, paste this:

   | :mono:`pylint {+dup=-d R0801:} {+nodoc=:-d C0114,C0115,C0116} {+nolong=:-d C0301} {target}`

Again, once you press Enter, chaintool will print info about the resulting command (not shown here).


Running a Command
-----------------

Once a command is defined, you can run it. For example you can run the ``myflake8`` command using ``chaintool cmd run myflake8``. However if you have chaintool shortcuts configured, you can run it with much less typing by just using the ``myflake8`` shortcut command that has been created. Similarly for ``mypylint``.

.. note::

   If you configured "old style" bash completions, remember that after creating a new command or sequence you must start a new shell in order for bash completions to work with your new shortcut.

If we now try just invoking one of our new shortcuts:

.. code-block:: none

   myflake8

Then we will see this output:

   | :red:`Not all placeholders in the commandline have been given a value.`
   | :red:`Placeholders that still need a value: target`

So what's going on there? To understand this behavior, and what we should do to make things work, we need to understand what is going on with the curly-bracket tokens that are present in the commandline.

Each thing enclosed by curly brackets defines a "placeholder". The part before the ``=`` symbol (if any) is the placeholder name. If the placeholder name starts with a ``+`` character then it is a "toggle"; otherwise it is a normal (non-toggle) placeholder.

In the ``myflake8`` commandline that we defined, there are two placeholders: ``target``, and the toggle ``+nolong``.

The definition for the ``+nolong`` toggle specifies values to subsitute into the commandline at that location depending on whether the toggle is "off" or "on". We'll dig into this more in following sections, but for now you can just observe that the value substituted when this toggle is "off" (the part between the ``=`` symbol and the colon) is the string ``,B950``. The value substituted when this toggle is "on" (the part after the colon) is emptystring.

The ``target`` placeholder is not a toggle; it marks a spot where any value might be substituted. In this example, no value is assigned by default (there is no ``=`` symbol after the placeholder name), so the user **must** at runtime supply a value. That's why we got the error above; we didn't specify what the value for ``target`` should be.

.. note::

   When we created the ``myflake8`` command, the nature of this ``target`` placeholder was highlighted by it being placed in the "required values" section of the printed command info.

So we need to specify a value when running the command. In this case we should specify a path to some Python sourcecode that can be evaluated by flake8. If for example the chaintool project's Python sourcecode is at the path :file:`/home/bob/chaintool/src/chaintool`, then this invocation of the ``myflake8`` shortcut will work:

.. code-block:: none

   myflake8 target=/home/bob/chaintool/src/chaintool

Of course if your Python source-to-evaluate is at a different path, specify that path instead. If you have chaintool autocompletions enabled, you can use tab-completion to help fill out the path value. And if your path includes spaces, be sure to quote it, e.g. ``target="/foo/bar/dirname with spaces/subdir"``.

As implied above, it's possible to define a default value for such a placeholder, so that it's not necessary to type out a value for the placeholder at runtime. We'll cover that, and other placeholder-related topics, in more detail below after we have built a sequence of commands that we want to run.


Defining a Sequence
-------------------

If you're going to frequently run a given list of commands, you can create a sequence to capture that list. For this example, let's call the sequence ``lint`` and create it like so:

.. code-block:: none

   chaintool seq edit lint

At the resulting ``commands:`` prompt, paste this:

   | :mono:`myflake8 mypylint`

.. note::

   You can use tab-completion during this edit, to help find and autocomplete available command names.

After you press Enter to create the sequence, chaintool will print info about the sequence. This is very similar to the printed command info we saw previously, except that placeholders common to some set of commands in the sequence will be grouped together. In this case you should see:

   | :mono:`Sequence 'lint' set.`
   |
   | :magenta:`** commands:`
   | :mono:`myflake8 mypylint`
   |
   | :magenta:`** commandline formats:`
   | :cyan:`* myflake8`
   | :mono:`flake8 --select C,E,F,W,B{+nolong=,B950:} --ignore W503,E203,E501,E731 {target}`
   | :cyan:`* mypylint`
   | :mono:`pylint {+dup=-d R0801:} {+nodoc=:-d C0114,C0115,C0116} {+nolong=:-d C0301} {target}`
   |
   | :magenta:`** required values:`
   | :cyan:`* myflake8, mypylint`
   | :mono:`target`
   |
   | :magenta:`** toggles with untoggled:toggled values:`
   | :cyan:`* myflake8, mypylint`
   | :mono:`+nolong = ,B950:'' (myflake8), '':'-d C0301' (mypylint)`
   | :cyan:`* mypylint`
   | :mono:`+dup = '-d R0801':''`
   | :mono:`+nodoc = '':'-d C0114,C0115,C0116'`

This shows us that the required (no-default-value) ``target`` placeholder is common to both commands. The ``+nolong`` toggle is common to both commands but causes different value substitutions in each. The ``+dup`` and ``+nodoc`` toggles only affect the ``mypylint`` command.


Running a Sequence
------------------

Let's run that sequence now. Again assuming that you have chaintool shortcuts configured, the sequence can be invoked with the ``lint`` shortcut command.

.. note::

   If you configured "old style" bash completions, remember that after creating a new command or sequence you must start a new shell in order for bash completions to work with your new shortcut.

So this invocation would process our example code target:

.. code-block:: none

   lint target=/home/bob/chaintool/src/chaintool

Because the ``target`` placeholder appears in both commands, each commandline will get this path value substituted at the location of that placeholder.

Running a sequence will execute all of its commands, sequentially, until it finishes or some command returns an error status. In the case of running this sequence against the chaintool source, both commands should succeed:

   | :magenta:`* running command 'myflake8':`
   |
   | :cyan:`flake8 --select C,E,F,W,B,B950 --ignore W503,E203,E501,E731 /home/bob/chaintool/src/chaintool`
   |
   |
   | :magenta:`* running command 'mypylint':`
   |
   | :cyan:`pylint -d R0801   /home/bob/chaintool/src/chaintool`
   |
   | :mono:`-------------------------------------------------------------------`
   | :mono:`Your code has been rated at 10.00/10 (previous run: 10.00/10, +0.00)`

The cyan line is the commandline being executed, after all value substitutions and toggles have been evaluated. Output from the executed commandline is printed in the normal color; in this case only pylint prints any output.


More Fun With Placeholders
--------------------------

If you're going to be frequently linting the same target, it doesn't make sense to keep typing that path for every run.

There are several ways you could change the commands to set a default value for that placeholder. For example you could use ``chaintool cmd set`` or ``chaintool cmd edit`` to modify each of the commandlines, changing each occurence of ``{target}`` to ``{target=/home/bob/chaintool/src/chaintool}``.

However, ``chaintool cmd set`` and ``chaintool cmd edit`` are more applicable for making structural/syntax changes to a commandline. If you just want to change or remove the default value for a non-toggle placeholder, or change the off/on values for a toggle, then it's easier to use ``chaintool cmd vals``. You can also use ``chaintool seq vals`` to set values for all commands in a sequence, or even ``chaintool vals`` to set values across all currently defined commands.

In this case, let's use ``chaintool seq vals`` to set the same default value for ``target`` in all commands in our ``lint`` sequence:

.. code-block:: none

   chaintool seq vals lint target=/home/bob/chaintool/src/chaintool

Now we can run the ``lint`` shortcut without any runtime arguments at all. If we do want to temporarily point it at some other path, we're still allowed to specify a value for ``target`` at runtime, which will override the default. And of course if we want to permanently change the default we could run ``chaintool seq vals`` again.

How about those toggle placeholders? Those toggles can be "activated" at runtime by putting the toggle name on the commandline. For example, this invocation would activate the ``+dup`` toggle:

.. code-block:: none

   lint +dup

In this sequence, the ``+dup`` toggle only happens to affect the ``mypylint`` command. By activating this toggle, the spot in that commandline that would normally contain ``-d R0801`` is instead populated with emptystring. The effect of this change is to remove the suppression of the "duplicate code" check in pylint; in other words, by specifying ``+dup`` you are asking pylint to do the duplicate-code checks that we normally are not asking it to do. When the command runs, you will see that the executed ``pylint`` commandline now looks like this:

   | :cyan:`pylint    /home/bob/chaintool/src/chaintool`

(With the current chaintool codebase, this will in fact cause pylint to complain about some stuff!)

You can specify as many runtime placeholder arguments (normal or toggle) as you wish. For example we could trigger two toggles:

.. code-block:: none

   lint +dup +nolong

Along with activating the "duplicate code" check, this invocation would **suppress** the "long lines" check. Because ``+nolong`` is present in both of our commandlines, specifying it here will affect both commands; in each case it will apply the necessary syntax to suppress the long-lines check for that command.

If you have bash completions configured, you can get suggestions for available placeholder completions by pressing tab while you are typing your invocation. (If there are multiple possible completions, depending on how your shell is configured you may need to double-tap the tab key.) For example if I were just to type ``lint`` followed by a space and then use tab to get completions, I would see this:

   | :mono:`+dup`
   | :mono:`+nodoc`
   | :mono:`+nolong`
   | :mono:`target=/home/bob/chaintool/src/chaintool`

which tells me that I have three toggles available, plus another normal placeholder that currently has the given default.

So if I do want to suppress the "long lines" checks in the linters, I don't need to remember that this means deleting the B950 selection for flake8 and adding a C0301 suppression for pylint. I can just specify ``+nolong``. If I don't exactly remember what I named that toggle, I can use bash completions to get a hint.

(And FYI for completeness' sake: the ``+nodoc`` toggle suppresses all docstrings checks, if you're evil that way.)

These toggles don't give us access to all the ``flake8`` and ``pylint`` arguments of course; presumably these specific toggles were defined because they represent certain options that were frequently being fiddled with.
