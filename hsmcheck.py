#!/usr/bin/python3
# -----------------------------------------------------------------------------
#  HSM-to-Python conversion tool
#
#  The check of the Python code of a diagram with a lint tool
#
#  Copyright (C) 2026 Alexey Fedoseev <aleksey@fedoseev.net>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see https://www.gnu.org/licenses/
#
#  -----------------------------------------------------------------------------

import ast
import difflib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import hsmd
import hsmd_components
import hsmd_reader

import gencode

ERROR = 'error'
WARNING = 'warning'

PYLINT = 'pylint'
PYFLAKES = 'pyflakes'
COMPILE = 'compile'
# the pylint messages worth a diagram: the errors and the warnings about names
PYLINT_ENABLE = ('E', 'unused-import', 'unused-variable', 'global-variable-undefined',
                 'global-variable-not-assigned', 'redefined-builtin')
PYFLAKES_ERRORS = ('undefined name', 'invalid syntax', 'syntax error')
PYFLAKES_LINE = re.compile(r'^.*?:(\d+):(?:\d+:)?\s*(.*)$')


class Finding:

    def __init__(self, severity, rule, where, element, line, message):
        self.severity = severity
        self.rule = rule
        self.where = where
        self.element = element
        self.line = line
        self.message = message

    def __str__(self):
        place = (self.where or 'document') + (', line {}'.format(self.line) if self.line else '')
        return '{}: {}: {} ({})'.format(self.severity, place, self.message, self.rule)

    def diagnostic(self):
        """The entry of the editor's diagnostics file."""
        entry = {'severity': self.severity, 'rule': self.rule,
                 'message': '{}: {}'.format(self.where, self.message) if self.where
                 else self.message}
        if self.element:
            entry['element'] = self.element
        return entry


# the events a trigger may name without anything posting them
SPECIAL_EVENTS = (hsmd_reader.EVENT_ANY, hsmd_reader.EVENT_UNKNOWN)
SIGNAL_SEPARATOR = '.'
# the calls that post an event: DISPATCH('X'), dispatcher.post('X'), dispatcher.send('X')
POSTING_METHODS = ('post', 'send')
STATE_KINDS = (hsmd_reader.STATE, hsmd_reader.COMPOSITE)
# the rules of the machine checks, before the linter's
MODEL_RULES = ('unknown-event', 'unknown-signal', 'unhandled-event', 'unreachable',
               'no-initial', 'no-else')
CONTAINER_LABELS = {hsmd_reader.CHOICE: 'choice', hsmd_reader.FINAL: 'final',
                    hsmd_reader.TERMINATE: 'terminate'}


# ----------------------------------------------------------------------------
# the machine: its events and its structure

def _machine_code(machine):
    """The code of the run machine, inlined parts included: (where, element, text)."""
    pieces = []
    for vertex in machine.vertices.values():
        for block in vertex.entry + vertex.exit:
            pieces.append((block.where, vertex.id, block.text))
        for reaction in vertex.reactions:
            element = vertex.id if reaction.target is None else reaction.id
            pieces.append((reaction.where, element, reaction.behavior))
    return pieces


def _parse(text):
    try:
        return ast.parse(text)
    except SyntaxError:
        return None              # the syntax is the linter's finding


def _posting(node):
    """Whether the call posts an event: DISPATCH(...) or dispatcher.post/send(...)."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == 'DISPATCH'
    return (isinstance(func, ast.Attribute) and func.attr in POSTING_METHODS and
            isinstance(func.value, ast.Name) and func.value.id == 'dispatcher')


def _posted(generator):
    """The events the code posts: [(name, where, element)]; when some name is
    computed, the strings of the code it may come from, else None."""
    posted, computed, strings = [], False, set()
    pieces = _machine_code(generator.machine)
    pieces += [(where, None, text) for where, text in generator.program_code()]
    for where, element, text in pieces:
        tree = _parse(text)
        for node in ast.walk(tree) if tree else ():
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                strings.add(node.value)
            if isinstance(node, ast.Call) and _posting(node) and node.args:
                name = node.args[0]
                if isinstance(name, ast.Constant) and isinstance(name.value, str):
                    posted.append((name.value, where, element))
                else:
                    computed = True
    return posted, strings if computed else None


def _class_signals(node):
    """The signals of a component class of the init code: its `signals`
    literal, else the names of its self.signal('X') calls; None when the
    class may inherit them."""
    for statement in node.body:
        if (isinstance(statement, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == 'signals' for t in statement.targets)):
            try:
                value = ast.literal_eval(statement.value)
            except ValueError:
                return None
            return None if value is None else set(value)
    bases = [b.attr if isinstance(b, ast.Attribute) else getattr(b, 'id', None)
             for b in node.bases]
    if bases != ['Component']:
        return None
    return {call.args[0].value for call in ast.walk(node)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and
            call.func.attr == 'signal' and call.args and
            isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)}


def _script_types(generator):
    """The component types of the init code: type name -> signals (None: unknown)."""
    classes, registered = {}, {}
    for _, text in generator.program_code():
        tree = _parse(text)
        for node in ast.walk(tree) if tree else ():
            if isinstance(node, ast.ClassDef):
                classes[node.name] = node
            elif (isinstance(node, ast.Call) and len(node.args) == 2 and
                  getattr(node.func, 'attr', getattr(node.func, 'id', None)) == 'register' and
                  isinstance(node.args[0], ast.Constant) and isinstance(node.args[1], ast.Name)):
                registered[node.args[0].value] = node.args[1].id
    return {ctype: _class_signals(classes[cls]) if cls in classes else None
            for ctype, cls in registered.items()}


def _signals(generator):
    """The component of the machine -> its type and the signals it declares
    (None: unknown)."""
    scripts = _script_types(generator)
    result = {}
    for declaration in generator.machine.components:
        cls = hsmd_components.find(declaration.type)
        if declaration.type in scripts or cls is None:
            signals = scripts.get(declaration.type)
        else:
            signals = hsmd.describe(cls)['signals']
            signals = None if signals is None else set(signals)
        result[declaration.id] = (declaration.type, signals)
    return result


def _trigger(reaction, element, context):
    """Whether the event of the reaction may occur, and the finding when not."""
    trigger = reaction.trigger
    known, computed, signals, names = context
    if (not trigger or trigger in known or trigger in SPECIAL_EVENTS or
            (computed is not None and trigger in computed)):
        return True, None
    ident, _, signal = trigger.partition(SIGNAL_SEPARATOR)
    if signal and ident in signals:
        ctype, declared = signals[ident]
        if declared is None or signal in declared:
            return True, None
        return False, Finding(ERROR, 'unknown-signal', reaction.where, element, None,
                              "'{}' is not a signal of {} ({})".format(
                                  trigger, ctype, ', '.join(sorted(declared)) or
                                  'it has no signals'))
    if signal and computed is None:
        return False, Finding(ERROR, 'unknown-signal', reaction.where, element, None,
                              "the trigger '{}' names no component of the machine".format(
                                  trigger))
    hint = difflib.get_close_matches(trigger, sorted(names), 1)
    return False, Finding(ERROR if computed is None else WARNING, 'unknown-event',
                          reaction.where, element, None,
                          "the event '{}' is never posted{}".format(
                              trigger, "; did you mean '{}'?".format(hint[0]) if hint else ''))


def _context(generator):
    """The posted events and what a trigger is checked against: the known
    events, the strings a computed name may be, the component signals and the
    names for the hints."""
    posted, computed = _posted(generator)
    signals = _signals(generator)
    known = set(gencode.PROGRAM_EVENTS) | {name for name, _ in hsmd.TIME_EVENTS}
    known |= {name for name, _, _ in posted}
    names = known | {'{}{}{}'.format(ident, SIGNAL_SEPARATOR, signal)
                     for ident, (_, declared) in signals.items() for signal in declared or ()}
    return posted, (known, computed, signals, names)


def _unhandled(posted, triggers):
    if triggers & set(SPECIAL_EVENTS):
        return []
    return [Finding(WARNING, 'unhandled-event', where, element, None,
                    "no transition takes the event '{}'".format(name))
            for name, where, element in posted if name not in triggers]


def events(generator):
    """The triggers nobody posts and the posted events nobody takes; returns
    the findings and the reactions whose events may occur."""
    posted, context = _context(generator)
    findings, possible, triggers = [], set(), set()
    for vertex in generator.machine.vertices.values():
        for reaction in vertex.reactions:
            triggers.add(reaction.trigger)
            element = vertex.id if reaction.target is None else reaction.id
            occurs, finding = _trigger(reaction, element, context)
            if occurs:
                possible.add(reaction)
            if finding is not None:
                findings.append(finding)
    return findings + _unhandled(posted, triggers), possible


def _vertex_where(machine, vertex):
    return "{}, {} '{}'".format(machine.where(), CONTAINER_LABELS.get(vertex.kind, 'state'),
                                vertex.id)


def structure(generator, possible):
    """The vertices no possible transition leads to, the composite states
    entered by default without an initial pseudostate, the choices without
    a way out."""
    machine = generator.machine
    findings = []
    reached = set()
    work = []

    def arrive(vertex):
        for v in [vertex] + vertex.chain()[1:]:
            if v not in reached:
                reached.add(v)
                work.append(v)
        states = [c for c in vertex.children if c.kind not in hsmd_reader.POINT_KINDS]
        if vertex.kind in STATE_KINDS and states:
            if vertex.initial is not None:
                arrive(vertex.initial)
            elif not any(f.element == vertex.id and f.rule == 'no-initial' for f in findings):
                findings.append(Finding(ERROR, 'no-initial', _vertex_where(machine, vertex),
                                        vertex.id, None, 'entered by a transition to the state '
                                        'but has no initial pseudostate'))

    arrive(machine.root.initial)
    while work:
        vertex = work.pop()
        for reaction in vertex.reactions:
            if reaction.target is not None and reaction in possible:
                arrive(reaction.target)
    for vertex in machine.vertices.values():
        if (vertex.kind in STATE_KINDS + tuple(CONTAINER_LABELS) and vertex not in reached
                and (vertex.parent in reached or vertex.parent is machine.root)):
            findings.append(Finding(WARNING, 'unreachable', _vertex_where(machine, vertex),
                                    vertex.id, None, 'no transition leads here'))
        if (vertex.kind == hsmd_reader.CHOICE and vertex.reactions and
                all(r.guard and not r.is_else() for r in vertex.reactions)):
            findings.append(Finding(WARNING, 'no-else', _vertex_where(machine, vertex),
                                    vertex.id, None, 'every way out has a guard and none is '
                                    'else: the choice may find none'))
    return findings


def model_findings(generator):
    """The findings of the events and of the structure of the run machine."""
    findings, possible = events(generator)
    return findings + structure(generator, possible)


def warn(generator):
    """Print the findings of the machine to stderr, the linter left out."""
    for finding in model_findings(generator):
        sys.stderr.write('{}\n'.format(finding))


def linter():
    """The lint tool available: pylint, pyflakes or the plain compilation."""
    for name in (PYLINT, PYFLAKES):
        if _command(name) is not None:
            return name
    return COMPILE


def _command(name):
    """The command of a lint tool: a module of this interpreter, or a program
    in the PATH, which then gets the directory of hsmd to import."""
    if importlib.util.find_spec(name) is not None:
        return [sys.executable, '-m', name]
    program = shutil.which(name)
    return [program] if program else None


def _environment():
    env = dict(os.environ)
    paths = [os.path.dirname(os.path.abspath(hsmd.__file__)),
             os.path.dirname(os.path.abspath(gencode.__file__))]
    env['PYTHONPATH'] = os.pathsep.join(paths + [env['PYTHONPATH']] if env.get('PYTHONPATH')
                                        else paths)
    return env


def _locate(line, blocks, sections):
    """The block or the section a module line belongs to."""
    for block in blocks:
        place = block.place(line)
        if place is not None and block.line <= line < block.line + block.text.count('\n') + 2:
            return block.where, block.element, place
    where = None
    for title, index in sections:
        if line > index:
            where = title
    return where, None, None


def _run(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, check=False, env=_environment())
    return result.stdout


def _pylint(path, blocks, sections):
    output = _run(_command(PYLINT) + ['--output-format=json', '--score=n', '--disable=all',
                                      '--enable=' + ','.join(PYLINT_ENABLE), path])
    try:
        messages = json.loads(output)
    except ValueError:
        return [Finding(ERROR, PYLINT, None, None, None, 'the linter failed: ' + output.strip())]
    findings = []
    for message in messages:
        where, element, line = _locate(message['line'], blocks, sections)
        severity = ERROR if message['type'] in ('error', 'fatal') else WARNING
        findings.append(Finding(severity, message['symbol'], where, element, line,
                                message['message']))
    return findings


def _pyflakes(path, blocks, sections):
    findings = []
    for text in _run(_command(PYFLAKES) + [path]).split('\n'):
        match = PYFLAKES_LINE.match(text)
        if not match:
            continue
        where, element, line = _locate(int(match.group(1)), blocks, sections)
        message = match.group(2)
        severity = ERROR if any(e in message for e in PYFLAKES_ERRORS) else WARNING
        findings.append(Finding(severity, PYFLAKES, where, element, line, message))
    return findings


def check(generator):
    """The findings of the lint tool over the code of the diagram, and the
    name of the tool used."""
    text, blocks, sections, errors = generator.lint_module()
    findings = model_findings(generator)
    findings += [Finding(ERROR, 'syntax-error', block.where, block.element, error.lineno,
                         error.msg) for block, error in errors]
    tool = linter()
    if tool == COMPILE:
        return findings, tool
    with tempfile.NamedTemporaryFile('w', prefix='hsm-lint-', suffix='.py', delete=False,
                                     encoding='utf-8') as module:
        module.write(text)
        path = module.name
    try:
        lint = _pylint if tool == PYLINT else _pyflakes
        findings += lint(path, blocks, sections)
    finally:
        os.remove(path)
    return findings, tool


def report(generator, json_path=None):
    """Print the findings, write the diagnostics file; True when there is
    an error."""
    findings, tool = check(generator)
    if tool == COMPILE:
        sys.stderr.write('neither pylint nor pyflakes is installed: '
                         'only the syntax is checked\n')
    for finding in findings:
        print(finding)
    if json_path is not None:
        with open(json_path, 'w', encoding='utf-8') as out:
            json.dump([f.diagnostic() for f in findings], out, indent=1, ensure_ascii=False)
    return any(f.severity == ERROR for f in findings)


def run():
    parser = gencode.arguments('Check the Python code of a state machine diagram.')
    parser.add_argument('--json', metavar='FILE',
                        help='write the findings as the diagnostics file of the editor')
    args = parser.parse_args()
    try:
        generator = gencode.CodeGenerator(args.graph, main=args.main, tick_len=args.tick)
    except gencode.ConvertorError as e:
        finding = Finding(ERROR, 'document', None, None, None, str(e))
        print(finding)
        if args.json is not None:
            with open(args.json, 'w', encoding='utf-8') as out:
                json.dump([finding.diagnostic()], out, indent=1, ensure_ascii=False)
        return 1
    return 1 if report(generator, args.json) else 0


if __name__ == '__main__':
    sys.exit(run())
