# hsm-to-python project changelog

## Version 2.0.0 (unreleased)

Changed:
- the generated program is the Python code of the machine run by the HSM
  dispatcher (`hsm-dispatcher-py`) instead of a pysm class: a function for
  the code of every state and transition and an `hsmd.Machine` declaration
  of the structure, so it runs without the diagram files and without
  `CyberiadaML`, the path of the diagram is a comment; the standard
  semantics apply (hierarchy, history, deferred and propagated events,
  submachine states, several machines);
- the test diagrams are CyberiadaML, except the yEd `term_node`; the
  former `not-implemented` cases `if_else` and `value_signals` run;
- the `SM Constructor Arguments` comment (synonym `Arguments`) declares the
  arguments of the program; `--set NAME=VALUE`, `--settings FILE` and
  `--help` set and show them.

Added:
- the time events `TIME_TICK_1M` and `TIME_TICK_1H`; the time events come
  from the dispatcher's `tick()`, only those the diagram uses;
- the names of the generated functions in Latin letters: the Cyrillic
  transliterated, the accents dropped (`russian` test);
- the checks of the machine in `hsm-check`, `hsm-run` and `hsm-gencode`:
  the events nothing posts, the unknown component signals, the posted
  events nothing takes, the unreachable states, the composite states
  without an initial pseudostate, the choices without `else` (`model`
  test);
- the runner `hsm-run` and the generator `hsm-gencode` as commands, the
  check `hsm-check` of the Python code of a diagram with pylint or pyflakes
  over the lint view (`hsm-gencode --lint`);
- the events with parameters (`DISPATCH('NAME', x=1)`, `event.x`), the
  components declared in the diagram and defined in the init scripts;
- the `vacuum` example of the whole language;
- the guide to the comments of a diagram (`docs/COMMENTS.md`) and the
  `formal_comments` test of the formal form;
- the `standalone` test (a program runs without the diagram files and
  without `CyberiadaML`, an error names the element and the line) and the
  `external` (a machine of another document) and `code_layout` test
  diagrams;
- the tests take the modules of this repository before their installed
  copies, and stop on a dispatcher older than the generator needs
  (`test/testenv.py`);
- the plugin of CyberiadaPro, the Cyberiada state machine editor (check,
  generate, run)
  and `hsm-run --install-editor-plugin`;
- the pip installation and the Debian package.

Fixed:
- `hsm-run` runs the program unbuffered: its output reaches a pipe (the
  editor's output tab) line by line and is not lost when the timeout kills
  it; a SIGTERM to `hsm-run` (the editor's Cancel) stops the program too;
  the plugin's run stopped by its time limit is no failure.

Removed:
- the dependency on `pysm`; `DISPATCH_VALUE` and `DISPATCH_SM`.

## Version 1.0

The generator of pysm classes from yEd diagrams.
