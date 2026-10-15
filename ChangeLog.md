# hsm-to-python project changelog

## Version 2.0.0 (unreleased)

Changed:
- the generated program runs the diagram on the HSM dispatcher
  (`hsm-dispatcher-py`) instead of a generated pysm class: the program
  carries the diagram and the documents its submachine states reference
  (`DOCUMENTS`) and runs without the files, the path of the diagram is a
  comment; the standard semantics apply (hierarchy, history, deferred and
  propagated events, submachine states, several machines);
- the test diagrams are CyberiadaML, except the yEd `term_node`; the
  former `not-implemented` cases `if_else` and `value_signals` run;
- the `SM Constructor Arguments` comment (synonym `Arguments`) declares the
  arguments of the program; `--set NAME=VALUE`, `--settings FILE` and
  `--help` set and show them.

Added:
- the runner `hsm-run` and the generator `hsm-gencode` as commands, the
  check `hsm-check` of the Python code of a diagram with pylint or pyflakes
  over the lint view (`hsm-gencode --lint`);
- the events with parameters (`DISPATCH('NAME', x=1)`, `event.x`), the
  components declared in the diagram and defined in the init scripts;
- the `vacuum` example of the whole language;
- the guide to the comments of a diagram (`docs/COMMENTS.md`) and the
  `formal_comments` test of the formal form;
- the `embedding` test (a program runs without the diagram files) and the
  `external` test diagram (a machine of another document);
- the tests take this repository, the dispatcher beside it and the sibling
  editor build before the installed packages (`test/testenv.py`);
- the plugin of the Cyberiada State Machine Editor (check, generate, run)
  and `hsm-run --install-editor-plugin`;
- the pip installation and the Debian package.

Removed:
- the dependency on `pysm`; `DISPATCH_VALUE` and `DISPATCH_SM`.

## Version 1.0

The generator of pysm classes from yEd diagrams.
