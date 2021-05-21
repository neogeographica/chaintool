Virtual Tools
=============

Normally a chaintool command's commandline represents a commandline that will be executed by the OS. However in some cases it instead expresses an action that chaintool itself should do. There are three of these "virtual tools" available. To use a virtual tool, the first word in the commandline must be the virtual tool, and subsequent words in the commandline will be arguments for that tool.

chaintool-copy
--------------

The `chaintool-copy` virtual tool lets you copy a file to a new location in an OS-independent syntax. The form is:

.. code-block:: none

   chaintool-copy <sourcepath> <destpath>

Using `chaintool-copy` is equivalent to using ``shutil.copy2`` in Python to copy the file at ``<sourcepath>`` to the new location ``<destpath>``.

chaintool-del
-------------

The `chaintool-del` virtual tool lets you delete a file in an OS-independent syntax. The form is:

.. code-block:: none

   chaintool-del <filepath>

Using `chaintool-del` is equivalent to using ``os.remove`` in Python to delete the file at ``<filepath>``, with one difference: if the file does not exist, the command is still considered to have succeeded.

chaintool-env
-------------

The `chaintool-env` virtual tool is used to set placeholder values. It is useful in a sequence where you need a placeholder's value to be based on another placeholder's value in some way. The form is:

.. code-block:: none

   chaintool-env <env_op> [<env_op> ...]

The ``<env_op>`` arguments will be applied in order when the command executes, affecting placeholder values for subsequent commands in the sequence. Each ``<env_op>`` is of the form:

   <placeholder_name>=<value_source>

This indicates that a value should be assigned to the placeholder ``<placeholder_name>`` *only if* that placeholder has no value when that ``<env_op>`` is evaluated. This assignment is treated the same as a runtime value assignment, i.e. it will override any default values for that placeholder that are baked into the subsequent commands.

The main reason such an assignment is useful, and the reason that the RHS of that expression is called ``<value_source>`` and not just ``<value>``, is that placeholder substitution will be performed on that RHS.

As an example, consider this ``chaintool-env`` commandline taken from the :doc:`final example<complex-example>` in these docs:

.. code-block:: none

   chaintool-env dstbase="{basename/stem/map}"

This has one ``<env_op>``. In plain language, that op says: if ``dstbase`` does not already have a value, set its value to a modified form of the ``map`` placeholder's value. (This modification involves stripping the directory and file extension.)

So if you specify a value for ``dstbase`` when running the sequence containing this command, then this op has no effect. But if you don't specify a value for ``dstbase`` in the ``run`` args, then this op will take effect, and the ``dstbase`` placeholder will get a value derived from ``map``. E.g. if ``map`` is ``/home/bob/foo.map`` then ``dstbase`` will be set to ``foo``. The value for the ``dstbase`` placeholder is then used in subsequent commands in the sequence.

When you pretty-print a sequence, the assumption is that the print output is most useful when you are considering running the sequence. So the print output for a sequence will take into account the effects of ``chaintool-env``. Every ``<env_op>`` is considered to be setting a new default value -- the ``<value_source>`` from the op -- for all the following commands that use that placeholder. That default will be shown in green text to indicate that it will be evaluated for placeholder substitution.

In the example sequence that uses the above ``chaintool-env`` command, there are two following commands ``q3copy`` and ``q3launch`` that make use of ``dstbase``. So the ``seq print`` output includes the following in the "optional values" section:

   | :cyan:`* q3copy, q3launch`
   | :mono:`dstbase = '`:green:`{basename/stem/map}`:mono:`'`
