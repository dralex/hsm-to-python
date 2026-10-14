# HSM-to-Python Framework

The tool of the Cyberiada project that turns a Hierarchical State Machine
diagram into a Python program. The diagram is stored in the CyberiadaML
GraphML format (or in the legacy yEd dialect) and is executed by the Python
HSM dispatcher: the generated program loads the diagram, runs the
initialization code and the init scripts of the diagram, and drives the
dispatcher with the clock events until the machine finishes. See details
about HSM here: https://platform.kruzhok.org/programming

The code is distributed under the GNU General Public License (version 3).

## Usage

    ./hsm.py diagram.graphml              # generate the program and run it
    ./gencode.py diagram.graphml out.py   # write the program to a file

Both commands take `--main NAME` (the state machine to run when the document
holds several; the first one by default) and `--tick MS` (the period of the
`TIME_TICK` event, 100 ms by default); `hsm.py --keep` leaves the generated
program in place and tells where.

The generated program needs the diagram file at the place it had when it was
generated, the `hsmd` module of the dispatcher and the `CyberiadaML` module.

### The diagram

The action text of the diagram is Python; the names it uses come from the
convention comments of the diagram. A convention comment is a formal
comment named by its key, or an informal comment whose first line is the
key (the form of the yEd diagrams); the key is matched without regard to
case, underscores and a trailing colon:

| Key | Content |
|---|---|
| `Global Initialization` | code run once at the start of the program: imports, variables, functions |
| `Init Scripts` | names of `.py` files beside the diagram, inlined into the program |
| `SM Constructor Arguments` | `name = value` lines, variables with their defaults |
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

### Several state machines

A document may hold several state machines: the first one (or the one named
with `--main`) runs, the others are the machines of its submachine states.
Every machine keeps an initial pseudostate, so a submachine state without
entry points is entered through it.

## Tests

    cd test
    python3 python_hsm_test.py

Each test is a diagram `test/graphs/<name>.graphml` with the expected output
of its program in `<name>.txt`; `HSMException` as the expected output means
the diagram must be refused. `test/run.py <diagram>` runs one diagram and
prints its output. The diagrams are CyberiadaML except `term_node.graphml`,
kept in the yEd dialect. When the dispatcher is not installed, the tests
take it from `../hsm-dispatcher-py` beside this repository.

## Requirements

* python3 (version 3.8+)
* hsm-dispatcher-py - the Python HSM dispatcher (the `hsmd` module)
* libcyberiadamlpp-py - the Python binding of the libcyberiadamlpp library
  (the `CyberiadaML` module) with its libraries
