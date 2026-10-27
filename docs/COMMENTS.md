# The Comments of an HSM-to-Python Diagram

Document version: 0.3 (2026-10-15)

This guide is for the authors of the diagrams run with `hsm-run`, `hsm-gencode` or the
editor plugin. The states and the transitions carry the action text; the comments carry
the rest of the program: the initialization, the init scripts, the arguments and the
loop code. The semantics of the diagram itself is described in the architecture document
of the dispatcher (`hsm-dispatcher-py/docs/ARCHITECTURE.md`).

## Where the comments go

```
 the diagram                                 the generated program
 ─────────────────────────────────           ─────────────────────────────────────────
 its path               ──────────────────▶  the header comment only
                                             imports, DISPATCH(), TICK_LEN
 Arguments              ──────────────────▶  the arguments as globals (--set, --settings)
 Global Initialization  ──────────────────▶  module code, run once
 Init Scripts: a.py b.py ─────────────────▶  a.py, b.py inlined, in this order
 the code of the states
 and the transitions    ──────────────────▶  def Idle_entry(): ...   one function a block
 the states, the transitions ─────────────▶  machine = hsmd.Machine(...)
 CGML_COMPONENT <id>    ──────────────────▶      hsmd.Declaration(...) in the machine
 CGML_META order, propagation ────────────▶      Machine(transition_order=, propagate=)
                                             make_dispatcher(): hsmd.Dispatcher(...)
                                                 the components are built here
                                             _begin(): start, post INIT
 Loop                   ──────────────────▶  _loop(): the loop code
                                             main():
                                                 make_dispatcher(), _begin()
                                                 while the machine is not finished:
                                                     _loop()
                                                     tick(): the time events, the timers
                                                     sleep TICK_LEN
 any other comment      ──▶ not in the program
```

`Arguments`, `Global Initialization`, `Init Scripts` and `Loop` are the convention
comments of hsm-to-python. `CGML_COMPONENT` and `CGML_META` are the formal comments of
the standard (PNST 1044-2025), interpreted by the dispatcher.

## Two forms of a convention comment

| | formal comment | informal comment |
|---|---|---|
| the key | the name of the comment | the first line of the body |
| the content | the whole body | the body after the first line |
| typical source | CyberiadaPro | yEd and the older diagrams |

The same comment in both forms, as it is stored:

```xml
<node id="nInit">
  <data key="dNote">formal</data>
  <data key="dName">Global Initialization</data>
  <data key="dData">debug = print
count = 0</data>
</node>

<node id="nInit">
  <data key="dNote">informal</data>
  <data key="dData">Global Initialization

debug = print
count = 0</data>
</node>
```

The rules of both forms:

* the key ignores case, underscores, extra spaces and a trailing colon:
  `GLOBAL_INITIALIZATION:` is `Global Initialization`;
* the comments of every state machine of the document count, in the document order;
  the same key used twice appends its content, so a long initialization may be split;
* the leading and trailing empty lines of the content are dropped.

The traps:

* **a formal comment without a name is ignored**, even when the first line of its body is
  a key: the key of a formal comment is its name. The editor creates every formal comment
  unnamed (see [In the editor](#in-the-editor));
* **the name of an informal comment is not a key**: the key must be the first line of the
  body;
* a comment placed inside a simple state makes that state composite, and a composite state
  needs an initial pseudostate. Keep the convention comments at the level of the machine
  or inside a composite state.

## The keys

### Arguments

The synonym `SM Constructor Arguments` is kept for the older diagrams. One argument per
line, `name = value`, the value a Python literal; the empty lines and the `#` lines are
skipped:

```
# the room the robot may clean
allowed = 'kitchen'
limit = 3
```

The arguments become globals before any other code runs, so the initialization, the
blocks and the loop use them by name. A line that is not `name = literal` stops the
generation: `The default of the argument limit is not a literal: three`.

The program takes the values from its command line:

```
hsm-run vacuum.graphml --set allowed=hall
hsm-run vacuum.graphml --settings run.txt        # name = value lines, # comments
hsm-gencode vacuum.graphml vacuum.py
python3 vacuum.py --help                         # the arguments and their defaults
```

A name that is not declared is refused. The value must have the type of the default
(`--set limit=x` gives `the argument limit takes a int, not 'x'`); for a string default
the text is taken as it is, quotes are not needed.

### Global Initialization

Python code run once at the module level: imports, variables, functions. It runs after
the arguments and before the init scripts. The names it defines are visible to every
block, guard and the loop.

```
debug = print
iteration = 0

def say(text):
    debug('{}: {}'.format(iteration, text))
```

The init scripts are inlined after this code: a function defined here may call the
names of a script, but the code at the module level here cannot.

### Init Scripts

The names of the Python files to inline into the program, one per line, relative to the
directory of the diagram. A line that does not end with `.py` is skipped; a missing file
stops the generation (`Cannot open the imported Python file ...`).

```
vacuum_battery.py
```

The files are inlined in the listed order, after `Global Initialization`; the generated
program does not need them later. This is the place for the component types: a subclass
of `hsmd.Component` registered under the type name of the declaration.

```python
import hsmd

class Battery(hsmd.Component):
    def __init__(self, ident, dispatcher, **parameters):
        hsmd.Component.__init__(self, ident, dispatcher, **parameters)
        self.threshold = int(parameters.get('threshold', 20))
        ...

hsmd.register('Battery', Battery)
```

### Loop

Python code run on every iteration of the main loop, before the time events, until the
main machine reaches its final state. The iterations are `--tick` milliseconds apart
(100 by default).

```
global iteration
iteration += 1
if iteration in SCRIPT:
    name, parameters = SCRIPT[iteration]
    DISPATCH(name, **parameters)
```

**The loop code is the body of the function `_loop()`, not the module code.** To assign
a global it needs `global name`; without it the assignment makes a local name and the
program fails with `UnboundLocalError`. The code of the states and the transitions does
not need `global`: the generator declares the names it assigns. `DISPATCH()` and `dispatcher` are
available.

## The formal comments of the dispatcher

These comments are a part of the standard. The details are in the dispatcher's
architecture document, sections Components and Standards.

`CGML_COMPONENT <id>` declares a component: an object the action text calls by its
identifier and whose signals are the events `<id>.<SIGNAL>`. The body holds `name/ value`
blocks separated by empty lines; `CGML_COMPONENT battery` of the vacuum cleaner:

```
type/ Battery

threshold/ 20
```

* `type/` - `Timer`, `Log` or a type registered by an init script;
* `priority/` - the priority of the events the component raises (the queue order);
* `shared/ yes` - one component common to every machine of the document;
* any other parameter is passed to the type as a string.

In the text: `battery.drain(7)`, the trigger `battery.LOW propagate/`.

`CGML_META` is the metainformation of the document. The dispatcher reads
`transitionOrder` (`actionFirst` by default: the behaviour of a transition runs before
the exit actions; or `exitFirst`) and `eventPropagation` (`block` by default, or
`propagate`). `platformLanguage/ Python` tells the editor how to highlight the code; the
plugin sets it before a run.

## Other comments

Any other formal comment and any informal comment without a key is not interpreted and
is not a part of the generated program: notes, prompts, settings of other tools. An
application that loads the diagram on the dispatcher reads them with
`dispatcher.comments(machine, formal=True|False|None)`.

## In the editor

The tools are in **Edit > Tools** and on the **Elements** toolbar: **New Comment** (an
informal comment) and **New Formal Comment**. Pick the tool and click the canvas.

```
 Properties                                canvas
 ▾ Element                                 ┌───────────────────────────┐
   Name    [Global Initialization  ]  ───▶ │ Global Initialization     │  the name, bold
 ▾ Comment                                 │ debug = print             │
   Body    [debug = print …   ] [ … ] ───▶ │ iteration = 0             │  the body
   Markup  [                  ]            └───────────────────────────┘
```

* A new formal comment has no name and the body "New formal comment". Set the key in
  **Properties > Element > Name**: an unnamed comment has no title to double-click.
* The body is edited in **Properties > Comment > Body** ("…" opens the multiline
  **Edit text** dialog) or by a double click on the canvas.
* `CGML_META` is not drawn. It is edited in the properties of the document,
  **Document > Metainformation**, and with **Edit > Language**.
* A component is a New Formal Comment named `CGML_COMPONENT <id>`. The components are
  hidden on the canvas unless **View > Component comments** is on; the element tree
  always lists them.
* **Run the diagram...** of the plugin asks for the arguments ("Arguments (name = value
  per line)") on the first run of a document; **Plugins > HSM to Python > Settings...**
  changes them later. They are stored in the settings of the editor, not in the diagram,
  and override the defaults of the `Arguments` comment.

## The code check

`hsm-check` and the plugin's **Check the code** lint the initialization, the init scripts
and the action text of every element. A wrong argument line is reported as an error of
the document. **The loop code is not checked**: its errors appear when the program runs.

## Summary

| key | synonyms | content | runs | `hsm-check` |
|---|---|---|---|---|
| `Arguments` | `SM Constructor Arguments` | `name = literal` lines | first, as globals | the syntax |
| `Global Initialization` | | Python, module level | once, after the arguments | yes |
| `Init Scripts` | | `.py` file names | once, after the initialization | yes |
| `Loop` | | Python, function body (`global`) | every iteration | no |
| `CGML_COMPONENT <id>` | | `name/ value` blocks | built before the start | the calls (pylint) |
| `CGML_META` | | `name/ value` blocks | read at the load | |

`test/graphs/vacuum.graphml` uses every key in the informal form,
`test/graphs/formal_comments.graphml` in the formal form with the traps above.
