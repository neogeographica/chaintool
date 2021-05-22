Export/Import
=============

The final chaintool commandgroups let you export your commands and sequences to a single file, or import from such a file.

Export is simple:

.. code-block:: none

   chaintool export <outfile>

This will write the data for all current commands and sequences to a single file located at the path `<outfile>`. If `<outfile>` exists it will be overwritten; if not, it will be created.

Import is used to create commands and sequences using the data from a file previously created by ``chaintool export``. It is (slightly) more complex:

.. code-block:: none

   chaintool import [-o] <infile>

In this case the `<infile>` can be either a filepath or a URL.

The optional ``-o`` flag controls what happens if an imported command or sequence has the same name as an already-existing item of the same type. If ``-o`` is not specified, the imported item is skipped over; if ``-o`` is specified, the imported item is accepted and overwrites the current item.

Note that it's not possible to import a command with the same name as an existing sequence, or vice-versa. In the case of such a conflict the imported item is skipped over.
