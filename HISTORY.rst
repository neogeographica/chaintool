Changelog
---------

- **0.3.0** (2021-??-??)

  - Use a separate lightweight module for bash completions support; might make
    bash completions slightly speedier.
  - Support filepath completions for placeholder values.
  - Handle updating the format of stored config/data across chaintool version
    upgrades. Also add format-versioning to exported data.
  - Support import-from-URL.
  - Support tab-completion of command names during "seq edit".
  - Make chaintool-del succeed even if file is already gone.
  - Simplification of chaintool-env: only conditional assignment is now
    supported in the env ops. The "=" assignment operator now does conditional
    assignment.
  - More work on Sphinx docs, and hosting them at "Read the Docs".

- **0.2.0** (2021-04-30)

  - New "chaintool x info" command to dump configuration info.
  - More work on readme files and Sphinx docs.
  - Code refactoring, reformatting, docstrings, linting, minor bugfixes, etc.

- **0.1.1** (2021-04-22)

  - Some metadata fixes.

- **0.1.0** (2021-04-22)

  - Initial build and upload to PyPI.
