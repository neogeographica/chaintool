Placeholders
============

A "placeholder" is a named position in a commandline where a string (the placeholder "value") can be substituted.

This section is a reference for the details of placeholder syntax and usage. It assumes that you have already read the :doc:`overview<overview>` and, hopefully, gone through the first :doc:`example<example>`.

Syntax within Commandlines
--------------------------

A placeholder's expression in a commandline (as defined in a ``cmd set`` or ``cmd edit`` operation) is a token enclosed in curly brackets. It can take one of three forms.

Placeholder without a default value:

.. code-block:: none

   {<placeholder_name>}

Placeholder with a default value:

.. code-block:: none

   {<placeholder_name>=<default_value>}

Or a "Toggle" style placeholder with "off" and "on" values:

.. code-block:: none

   {<toggle_placeholder_name>=<off_value>:<on_value>}

A ``<placeholder_name>`` must start with a letter, which is optionally followed by letters, numbers, and/or underscores.

A ``<toggle_placeholder_name>`` must start with a ``+`` symbol followed by a letter, which is optionally followed by letters, numbers, and/or underscores.

A ``<default_value>`` or an ``<on_value>`` can be anything (including whitespace).

An ``<off_value>`` can be anything except a colon; there's currently no way to express that an ``<off_value>`` must contain a literal colon character.

.. note::

   If you need to include a literal curly-bracket character as part of a ``<default_value>``, ``<off_value>``, or ``<on_value>``, when composing a placeholder token in a commandline, then you must use a double of that character. For example if you need the placeholder ``foo`` to have a default value of ``hey {howdy} ho``, you could express that within a commandline by using the token ``{foo=hey {{howdy}} ho}``.

   That double-curly-bracket maneuver is only required when composing these curly-bracket-enclosed tokens within a commandline. If you are instead specifying the value as part of a ``<placeholder_arg>`` for a ``run`` or ``vals`` operation as described below, the doubling is not needed.

   Finally, note that none of these cases allow/support interpreting a placeholder token nested inside the default value of some other placeholder token. If you need a default value to be based on another placeholder value in some way, using :ref:`chaintool-env<virtual-tools:chaintool-env>` in a sequence can get you the same effect.

Syntax in Vals Operations
-------------------------

As described :ref:`in the overview<overview:command and sequence authoring>`, the ``vals`` operations can be used to modify the values for existing placeholders in commandlines.

Each ``<placeholder_arg>`` in the invocation of a ``vals`` operation can take one of three forms.

Remove any default value a placeholder might have:

.. code-block:: none

   <placeholder_name>

Set a default value for a placeholder:

.. code-block:: none

   <placeholder_name>=<default_value>

Or set the "off" and "on" values for a toggle:

.. code-block:: none

   <toggle_placeholder_name>=<off_value>:<on_value>

You'll note that these formats are pretty much the same as in the commandline tokens described above; they are just missing any curly brackets.

When composing the chaintool invocation for a ``vals`` operation, if you have configured :ref:`bash completions<configuration:completions>` for chaintool, you can use Tab to help autocomplete the available placeholders. The completion for a given placeholder will print the placeholder name followed by the ``=`` symbol, and also the current default value for the placeholder *if* it has a consistent default value in all affected commands. Your cursor will then be placed at the end of that completion so you can edit (or remove) the value as you like.

.. note::

   If you want to remove the default value for a placeholder, make sure to *not* have the ``=`` symbol after the placeholder name. If you have the ``=`` symbol followed by nothing, you are setting the placeholder to a default value of emptystring, which is different than saying it has no default.

For each ``<placeholder_arg>`` in a ``vals`` operation, chaintool will go through all affected commands and update them if they use that placeholder. At the end of the operation, chaintool will also tell you if any specified ``<placeholder_arg>`` was "irrelevant", i.e. its placeholder name was not contained in any of the affected commandlines.

Syntax in Run Operations
------------------------

Finally, as described :ref:`in the overview<overview:command and sequence execution>`, placeholder arguments can also be given to ``run`` operations.

Each ``<placeholder_arg>`` in the invocation of a ``run`` operation can take one of two forms.

Set a runtime value for a placeholder:

.. code-block:: none

   <placeholder_name>=<value>

Or activate a toggle:

.. code-block:: none

   <toggle_placeholder_name>

For each non-toggle ``<placeholder_arg>`` in a ``run`` operation, chaintool will go through all affected commands and substitute in the specified value for that placeholder token, overriding any default value.

For each toggle ``<placeholder_arg>`` in a ``run`` operation, chaintool will go through all affected commands and substitute the "on" value for that toggle placeholder token.

Any remaining non-toggle placeholder tokens that have a default value will be replaced with that default value. Any remaining placeholder tokens for unactivated toggles will be replaced with their "off" value.

Now we have the actual commandline(s) to run! If any commandline still has a placeholder left in it -- i.e. a non-toggle placeholder token that does *not* have a default value and did *not* get a value from a runtime ``<placeholder_arg>`` -- then that commandline will fail with an error status. Otherwise the commandline is executed.

At the end of the operation, chaintool will also tell you if any specified ``<placeholder_arg>`` was "irrelevant", i.e. its placeholder name was not contained in any of the affected commandlines.

Modifiers
---------

Normally a placeholder token in a commandline will be replaced with the verbatim value for that placeholder. But for non-toggle placeholders, you can optionally indicate that the value will be changed by some common filepath manipulation(s). These manipulations are called "modifiers" and can be repeatedly prepended to the placeholder name using a slash.

.. note::

   Modifiers can only be used within the curly-bracket tokens in the commandlines. You can't specify modifiers in arguments for ``run`` or ``vals``. The arguments for ``run`` and ``vals`` are saying what a value *is*; modifiers are saying something about how to *change* a value once chaintool knows what it is. 

A placeholder with one modifier would be in this form:

.. code-block:: none

   {<modifier>/<placeholder_name>}

A placeholder with two modifiers, in this form:

.. code-block:: none

   {<modifier>/<modifier>/<placeholder_name>}

and etc. There is no limit enforced on the number of modifiers that can be prepended, but in practice you won't need many.

It's also fine for a modified placeholder to have a default value, e.g.:

.. code-block:: none

   {<modifier>/<modifier>/<placeholder_name>=<default_value>}

Modifiers will always be applied to the value before it's substituted into the commandline, whether that value comes from the default or from a ``run`` argument. Modifiers are applied in order starting with the rightmost one (closest to the placeholder name) and then working leftward.

The available modifiers are:

- ``dirname`` : This modifier removes the final directory separator character (if it exists) and everything after it. It is the equivalent of ``os.path.dirname`` in Python.
- ``basename`` : This modifier removes the final directory separator character (if it exists) and everything before it. It is the equivalent of ``os.path.basename`` in Python.
- ``stem`` : This modifier removes the rightmost file extension (if any), as long as it is after the final directory separator character (if it exists).

So let's look at a concrete example. Let's say this is part of your commandline:

   | :mono:`--inputfile "{inputfile}" --outputfile "{stem/inputfile}.out"`

If the ``inputfile`` value is given at runtime as ``/home/bob/foo.txt``, this portion of the commandline would end up looking like:

   | :mono:`--inputfile "/home/bob/foo.txt" --outputfile "/home/bob/foo.out"`

You could also have a default specified for ``inputfile`` -- with the constraint that multiple instances of a placeholder within a single commandline must have the same default. So the above commandline snippet could instead be:

   | :mono:`--inputfile "{inputfile=default.txt}" --outputfile "{stem/inputfile=default.txt}.out"`

This would give the same resulting commandline portion as above if you explicitly specified ``inputfile`` as ``/home/bob/foo.txt`` at runtime. However if you fail to specify ``inputfile`` at runtime, the commandline portion would then look like:

   | :mono:`--inputfile "default.txt" --outputfile "default.out"`

Finally, if you wanted the output file to be written to the "/tmp" directory, you could also change our example snippet to do that. Using multiple modifiers you can strip the directory from the filepath, giving you a filename that you can append to "/tmp/":

   | :mono:`--inputfile "{inputfile=default.txt}" --outputfile "/tmp/{basename/stem/inputfile=default.txt}.out"`

If we supply that ``/home/bob/foo.txt`` value for ``inputfile`` at runtime, the resulting commandline portion would be:

   | :mono:`--inputfile "/home/bob/foo.txt" --outputfile "/tmp/foo.out"`

Interpreting Print Output
-------------------------

The ``print`` operations allow you to pretty-print information about one or more commands; you can also optionally get this output after operations that create or modify a command or sequence. This print output shows you the names of the commands involved (if more than one), the commandlines, and information about the placeholders in those commandlines.

The placeholder information can potentially be large and complicated, so it is organized and formatted for better clarity. We'll go over some examples here to point out exactly what is going on in that section of the output. FYI this output is taken from the :doc:`more complex chaintool example<complex-example>` near the end of this user guide, although possibly the commands/sequences for that example have been updated since this doc was written.

Single Command
^^^^^^^^^^^^^^

First let's look at printing a single command:

.. code-block:: none

   chaintool cmd print q3light

Here's the output:

   | :magenta:`* commandline format:`
   | :mono:`"{q3map2=q3map2.x86_64}" -v -threads {threads=7} -game quake3 -fs_basepath "{q3basepath}" -fs_game {q3mod=baseq3} -light -samplesize {samplesize=8} -fast -gamma {gamma=2} -compensate {compensate=4} -patchshadows {+super=-samples:-super} {samples=3} -filter -bounce {bounce=8} -bouncegrid {+nophong=-shade:} "{map}"`
   |
   | :magenta:`* required values:`
   | :mono:`map`
   | :mono:`q3basepath`
   |
   | :magenta:`* optional values with default:`
   | :mono:`bounce = 8`
   | :mono:`compensate = 4`
   | :mono:`gamma = 2`
   | :mono:`q3map2 = q3map2.x86_64`
   | :mono:`q3mod = baseq3`
   | :mono:`samples = 3`
   | :mono:`samplesize = 8`
   | :mono:`threads = 7`
   |
   | :magenta:`* toggles with untoggled:toggled values:`
   | :mono:`+nophong = -shade:''`
   | :mono:`+super = -samples:-super`

The three sections describing the placeholders are really just repeating the information available in the displayed commandline format, organized to show the different kinds of placeholders in use. For example, knowing that there are two without defaults (``map`` and ``q3basepath``) is useful because they must either be assigned default values or given runtime values in order for the command to execute.

.. note::

   In these placeholder sections, values will be quoted as they would need to be if you were specifying them in a ``<placeholder_arg>`` for a ``run`` or ``vals`` operation (to protect whitespace or special characters). Emptystrings will also be highlighted with quotes, as for example with the "on" value for the ``+nophong`` toggle above.

Multiple Commands
^^^^^^^^^^^^^^^^^

Now let's print all the commands in a sequence:

.. code-block:: none

   chaintool seq print q3build

Here's the output:

   | :magenta:`** commands:`
   | :mono:`q3bsp q3vis q3light q3set-opt-dest q3copy q3launch`
   |
   | :magenta:`** commandline formats:`
   | :cyan:`* q3bsp`
   | :mono:`"{q3map2=q3map2.x86_64}" -v -threads {threads=7} -game quake3 -fs_basepath "{q3basepath}" -fs_game {q3mod=baseq3} -meta -samplesize {samplesize=8} {+leaktest=:-leaktest} -skyfix "{map}"`
   | :cyan:`* q3vis`
   | :mono:`"{q3map2=q3map2.x86_64}" -v -threads {threads=7} -game quake3 -fs_basepath "{q3basepath}" -fs_game {q3mod=baseq3} -vis -saveprt {+fastvis=:-fast} "{map}"`
   | :cyan:`* q3light`
   | :mono:`"{q3map2=q3map2.x86_64}" -v -threads {threads=7} -game quake3 -fs_basepath "{q3basepath}" -fs_game {q3mod=baseq3} -light -samplesize {samplesize=8} -fast -gamma {gamma=2} -compensate {compensate=4} -patchshadows {+super=-samples:-super} {samples=3} -filter -bounce {bounce=8} -bouncegrid {+nophong=-shade:} "{map}"`
   | :cyan:`* q3set-opt-dest`
   | :mono:`chaintool-env dstbase="{basename/stem/map}"`
   | :cyan:`* q3copy`
   | :mono:`chaintool-copy "{stem/map}.bsp" "{q3basepath}/{q3mod=baseq3}/maps/{dstbase}.bsp"`
   | :cyan:`* q3launch`
   | :mono:`"{q3basepath}/{q3exe=quake3e.x64}" +set sv_pure 0 +set fs_game {q3mod=baseq3} {+lightmap=:+r_lightmap 1} +devmap "{dstbase}"`
   |
   | :magenta:`** required values:`
   | :cyan:`* q3bsp, q3vis, q3light, q3copy, q3launch`
   | :mono:`q3basepath`
   | :cyan:`* q3bsp, q3vis, q3light, q3set-opt-dest, q3copy`
   | :mono:`map`
   |
   | :magenta:`** optional values with default:`
   | :cyan:`* q3bsp, q3vis, q3light, q3copy, q3launch`
   | :mono:`q3mod = baseq3`
   | :cyan:`* q3bsp, q3vis, q3light`
   | :mono:`q3map2 = q3map2.x86_64`
   | :mono:`threads = 7`
   | :cyan:`* q3bsp, q3light`
   | :mono:`samplesize = 8`
   | :cyan:`* q3copy, q3launch`
   | :mono:`dstbase = '`:green:`{basename/stem/map}`:mono:`'`
   | :cyan:`* q3light`
   | :mono:`bounce = 8`
   | :mono:`compensate = 4`
   | :mono:`gamma = 2`
   | :mono:`samples = 3`
   | :cyan:`* q3launch`
   | :mono:`q3exe = quake3e.x64`
   |
   | :magenta:`** toggles with untoggled:toggled values:`
   | :cyan:`* q3bsp`
   | :mono:`+leaktest = '':-leaktest`
   | :cyan:`* q3vis`
   | :mono:`+fastvis = '':-fast`
   | :cyan:`* q3light`
   | :mono:`+nophong = -shade:''`
   | :mono:`+super = -samples:-super`
   | :cyan:`* q3launch`
   | :mono:`+lightmap = '':'+r_lightmap 1'`

Because there are six commands in this sequence, it could be even more confusing to try to get a good picture of the available placeholders just by looking at the commandline formats. The three placeholder sections in the output try to help by collating commands that share the same placeholder. So for example the ``q3mod`` placeholder is present in the commandlines for ``q3bsp``, ``q3vis``, ``q3light``, ``q3copy``, and ``q3launch``. chaintool will just list this placeholder once, but it shows that it applies to those five commands.

The command groupings for the placeholders are arranged so that the largest groupings are shown first. Among groupings of the same size, groupings with commands from earlier in the sequence are shown first.

Inconsistent Defaults
^^^^^^^^^^^^^^^^^^^^^

One thing to notice here is that currently the placeholders shared by multiple commands have the same default value(s) in all those commands. Let's change that and see how the output changes. Maybe for some reason we only want to use 5 threads by default for ``q3light``:

.. code-block:: none

   chaintool cmd vals q3light threads=5

Now if we print the ``q3build`` sequence again, the relevant part of the "optional values" section will have changed from this:

   | :cyan:`* q3bsp, q3vis, q3light`
   | :mono:`q3map2 = q3map2.x86_64`
   | :mono:`threads = 7`

to this:

   | :cyan:`* q3bsp, q3vis, q3light`
   | :mono:`q3map2 = q3map2.x86_64`
   | :mono:`threads = 7 (q3bsp), 7 (q3vis), 5 (q3light)`

It still shows that ``threads`` is used by ``q3bsp``, ``q3vis``, and ``q3light``, but since the default value is not the same across all of those commands, it shows what that value is for each command.

Now what if we were to remove the default value for ``threads`` in one of those commands?

.. code-block:: none

   chaintool cmd vals q3vis threads

Since there is now at least one command where this placeholder lacks a value, the sequence cannot be executed without specifying a runtime value for that placeholder. Any default values for that placeholder in other commands are now irrelevant, as they will necessarily get overwritten at runtime. Since the pretty-print output is primarily geared toward "what you need to know when running this command/sequence", the part for ``threads`` will be moved from the "optional values" section to the "required values" section, and just look like this:

   | :cyan:`* q3bsp, q3vis, q3light`
   | :mono:`q3map2 = q3map2.x86_64`
   | :mono:`threads`

.. note::

   When a placeholder's value is set by ``run`` or ``vals``, the same value is applied wherever that placeholder appears in all affected commands. So, it also usually makes sense for a placeholder to have the same *default* value everywhere. If a placeholder is shown as having a different default in some commands, that might be an indication that a different placeholder name should be used in those cases.

"chaintool-env" Effects
^^^^^^^^^^^^^^^^^^^^^^^

The last thing to notice in the example output above is the bit of green text:

   | :mono:`dstbase = '`:green:`{basename/stem/map}`:mono:`'`

This green text can appear in print output for sequences, and it indicates a placeholder value affected by a "chaintool-env" :doc:`virtual tool<virtual-tools>` that is used earlier in the sequence. More details about virtual tools can be found in that full section; the gist to mention here is that the value of some placeholder (here, ``dstbase``) will be based on the runtime value of some other placeholder (here, ``map`` with :ref:`modifiers<placeholders:modifiers>`).
