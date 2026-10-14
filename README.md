# HSM-to-Python Framework

The tool of the Cyberiada project that turns a Hierarchical State Machine
diagram into a Python program. The diagram is stored in the CyberiadaML
GraphML format (or in the legacy yEd dialect) and is executed by the Python
HSM dispatcher: the generated program loads the diagram, runs the
initialization code and the init scripts of the diagram, and drives the
dispatcher with the clock events until the machine finishes. See details
about HSM here: https://platform.kruzhok.org/programming

The code is distributed under the GNU General Public License (version 3).

## Installation

    pip install .

installs the three commands into the active Python environment. The
dispatcher (`hsm-dispatcher-py`, the module `hsmd`) and the `CyberiadaML`
module of `libcyberiadamlpp-py` must be installed there as well; neither is
on a package index, both come from their source trees. The scripts of the
repository run without installation too (`./hsm.py`, `./gencode.py`,
`./hsmcheck.py`) when `hsmd` is importable.

## Usage

    hsm-run diagram.graphml              # generate the program and run it
    hsm-gencode diagram.graphml out.py   # write the program to a file
    hsm-check diagram.graphml            # check the Python code of the diagram

All three take `--main NAME` (the state machine to run when the document
holds several; the first one by default) and `--tick MS` (the period of the
`TIME_TICK` event, 100 ms by default). `hsm-run` also takes `--check`
(refuse a diagram whose code has errors), `--timeout S` (stop the program
after S seconds), `--set NAME=VALUE` and `--settings FILE` (the arguments of
the diagram, see below) and `--keep` (leave the generated program in place
and tell where). `hsm-gencode --check` refuses a diagram with errors, and
`hsm-gencode --lint out.py` writes the lint view instead of the program.

The generated program needs the diagram file at the place it had when it was
generated, the `hsmd` module and the `CyberiadaML` module. It takes `--set`,
`--settings` and `--help` itself.

### The diagram

The action text of the diagram is Python. Every block - `entry/`, `exit/`,
the behaviour of a transition, a guard - runs in the one namespace of the
program, like code at module level: a name assigned in a block is a global
visible to every other block, to the guards and to the loop code, `global x`
is allowed but not needed, and there are no block-local variables. The
names the text sees are the components of the machine by their identifiers,
`event` (the current event: `event.name` and its parameters as attributes),
`DISPATCH`, and everything the convention comments define.

A convention comment is a formal comment named by its key, or an informal
comment whose first line is the key (the form of the yEd diagrams); the key
is matched without regard to case, underscores and a trailing colon, and the
comments of every machine of the document count, in the document order:

| Key | Content |
|---|---|
| `Global Initialization` | code run once at the start of the program: imports, variables, functions |
| `Init Scripts` | names of `.py` files beside the diagram, inlined into the program |
| `Arguments` (or `SM Constructor Arguments`) | `name = value` lines: the arguments of the program with their defaults, Python literals |
| `loop` | code run on every iteration of the loop |

The program posts the events `INIT` (once, after the start), `TIME_TICK`
(every `--tick` milliseconds) and `TIME_TICK_1S` (every second). The text of
the diagram posts its own events with `DISPATCH('NAME', parameter=value)`;
a transition reads the parameters as `event.parameter`:

    WAKEUP [int(event.num) == 22]/
    global foo
    foo = int(event.num)

The names of the events are written in capitals. The rest of the language -
the components, the order of the transitions, the special events, the
submachine states - is the dispatcher's; see its architecture document.

### The arguments

The `Arguments` comment declares what may be changed without editing the
diagram. The program keeps the arguments as globals with the declared
defaults and takes other values from its command line: `--set name=value`
(repeatable) or `--settings FILE` (a file of `name = value` lines, `#`
comments allowed); `hsm-run` passes both on. Only a declared name may be
set, and the value must have the type of the default (`--set limit=5` for
`limit = 3`; a string default takes the text as it is). `--help` of the
program lists the arguments with their defaults.

### Several state machines

A document may hold several state machines: the first one (or the one named
with `--main`) runs, the others are the machines of its submachine states.
Every machine keeps an initial pseudostate, so a submachine state without
entry points is entered through it.

## The code check

`hsm-check` gives the Python of the diagram to a lint tool and maps the
findings back to the elements:

    error: machine 'G', state 'a', entry, line 1: Undefined variable 'debg' (undefined-variable)
    error: machine 'G', transition 'b-fin', line 1: Instance of 'Counter' has no 'ad' member (no-member)
    warning: Global initialization: Unused import os (unused-import)

The tool is `pylint` when it is installed (it infers the component classes
from the init scripts, so a wrong member is found), `pyflakes` otherwise;
without either only the syntax of every block is checked. The tool is taken
from this interpreter or from the `PATH`. The exit code is 1 when there is
an error. `--json FILE` writes the findings in the diagnostics format of the
CyberiadaHSM-Editor plugins.

The check runs on the lint view of the diagram, which `hsm-gencode --lint`
writes: one module with the initialization code, the components and
`event`, and one function per block, named after the element; it is also a
readable listing of the diagram's code. The lint view mirrors the run-time
semantics: a name a block assigns is declared `global` in its function and
defined at module level.

## The editor plugin

`editor-plugin/` holds the plugin for the CyberiadaHSM-Editor (its plugin
interface, level 1): the actions *Check the code* (the findings appear on
the elements), *Generate the program...* (into a chosen directory) and *Run
the diagram...* (the output in the plugin dock, a time limit, the arguments
as `name = value` lines). Install the directory as `hsm-to-python/` into the
editor's plugin folder (see the editor's `docs/PLUGIN-API.md`, Packaging).
The plugin runs the commands `hsm-check`, `hsm-gencode` and `hsm-run`, so
the environment where they are installed must be in the `PATH` of the
editor. To try it from the repository:

    CyberiadaEditor --batch test/graphs/vacuum.graphml --plugin-path . \
        --run-plugin hsm-to-python:check --dump-plugin

## Tests

    cd test
    python3 python_hsm_test.py      # the diagrams, their code check, the lint tests
    python3 arguments_test.py       # --set, --settings, --help of a generated program
    python3 plugin_test.py          # the editor plugin in the batch mode of the editor

Each test is a diagram `test/graphs/<name>.graphml` with the expected output
of its program in `<name>.txt`; `HSMException` as the expected output means
the diagram must be refused. The code of every diagram is checked first.
`test/lint/` holds diagrams with planted faults and their expected findings
(compared when pylint is the linter). `test/run.py <diagram>` runs one
diagram and prints its output. The diagrams are CyberiadaML except
`term_node.graphml`, kept in the yEd dialect. `vacuum.graphml`, a robot
vacuum cleaner, is the full example: two machines with a submachine state,
history, deferred and propagated events, a choice, event parameters, a
component defined in the init script `vacuum_battery.py`, and every
convention comment. The plugin test needs the editor binary
(`CYBERIADA_EDITOR`, the `PATH`, or the sibling build) and the installed
commands; it says when it skips. When the dispatcher is not installed, the
tests take it from `../hsm-dispatcher-py` beside this repository.

## Requirements

* python3 (version 3.8+)
* hsm-dispatcher-py - the Python HSM dispatcher (the `hsmd` module)
* libcyberiadamlpp-py - the Python binding of the libcyberiadamlpp library
  (the `CyberiadaML` module) with its libraries
* pylint or pyflakes - for the code check (optional)
