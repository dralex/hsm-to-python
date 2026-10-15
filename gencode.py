#!/usr/bin/python3
# -----------------------------------------------------------------------------
#  HSM-to-Python conversion tool
#
#  The generator: a Python program that runs the diagram on the HSM dispatcher
#
#  Copyright (C) 2025-2026 Alexey Fedoseev <aleksey@fedoseev.net>
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

import argparse
import ast
import os
import re
import sys

import hsmd_reader

VERSION = '2.0'
TICK_LEN = 100                          # the period of TIME_TICK, ms

# the convention comments: the key is the name of a formal comment or the
# first line of an informal one, normalised by normalize()
SECTION_INIT = 'global initialization'
SECTION_SCRIPTS = 'init scripts'
SECTION_ARGUMENTS = 'arguments'
SECTION_LOOP = 'loop'
SYNONYMS = {'sm constructor arguments': SECTION_ARGUMENTS}
SECTIONS = (SECTION_INIT, SECTION_SCRIPTS, SECTION_ARGUMENTS, SECTION_LOOP)
TITLES = {SECTION_INIT: 'Global initialization', SECTION_SCRIPTS: 'Init scripts',
          SECTION_ARGUMENTS: 'Arguments', SECTION_LOOP: 'Loop'}

SCRIPT_EXTENSION = '.py'
INDENT = ' ' * 4
STANDARD_TYPES = ('Timer', 'Log')       # the component types of the dispatcher

LINT_HEADER = '''import ast  # pylint: disable=unused-import
import sys  # pylint: disable=unused-import
import time  # pylint: disable=unused-import

import hsmd


def DISPATCH(name, **parameters):
    """Post an event from the text of the diagram."""
    dispatcher.post(name, **parameters)
'''

HEADER = '''import ast
import sys
import time

import hsmd


def DISPATCH(event, **parameters):
    """Post an event from the text of the diagram."""
    dispatcher.post(event, **parameters)


def _set_arguments(defaults):
    """The declared arguments with the values of --set name=value and
    --settings FILE from the command line."""
    values = dict(defaults)
    pairs = []
    args = sys.argv[1:]
    while args:
        option, args = args[0], args[1:]
        if option in ('-h', '--help'):
            print('usage: {} [--set NAME=VALUE]... [--settings FILE]'.format(sys.argv[0]))
            print('the arguments of the diagram and their defaults:')
            for name, value in defaults.items():
                print('  {} = {!r}'.format(name, value))
            sys.exit(0)
        if option.startswith('--set='):
            pairs.append(option[len('--set='):])
        elif option == '--set' and args:
            pairs.append(args[0])
            args = args[1:]
        elif option == '--settings' and args:
            with open(args[0], encoding='utf-8') as settings:
                pairs.extend(line for line in settings.read().split('\\n')
                             if line.strip() and not line.lstrip().startswith('#'))
            args = args[1:]
        else:
            sys.exit('unknown argument {!r}; see --help'.format(option))
    for pair in pairs:
        name, separator, text = pair.partition('=')
        name, text = name.strip(), text.strip()
        if not separator or name not in defaults:
            sys.exit('{!r} is not an argument of the diagram'.format(name or pair))
        try:
            value = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            value = text
        if isinstance(defaults[name], str):
            value = text if not isinstance(value, str) else value
        elif type(value) is not type(defaults[name]):
            sys.exit('the argument {} takes a {}, not {!r}'.format(
                name, type(defaults[name]).__name__, text))
        values[name] = value
    return values
'''

FOOTER = '''
# The diagram: the states, the transitions and their code
DOCUMENTS = {{
{documents}}}

dispatcher = hsmd.Dispatcher(DIAGRAM, machines=[MAIN], namespace=globals(),
                             documents=DOCUMENTS)


def main():
    dispatcher.start()
    dispatcher.post('INIT')
    dispatcher.run()
    period = TICK_LEN / 1000.0
    start = time.monotonic()
    next_tick = start + period
    next_second = start + 1.0
    while not dispatcher.finished():
{loop}        now = time.monotonic()
        if now >= next_tick:
            dispatcher.post('TIME_TICK')
            while next_tick <= now:
                next_tick += period
        if now >= next_second:
            dispatcher.post('TIME_TICK_1S')
            while next_second <= now:
                next_second += 1.0
        dispatcher.tick()
        time.sleep(period)
    return 0


if __name__ == '__main__':
    sys.exit(main())
'''


class ConvertorError(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return self.msg


class ParserError(ConvertorError):
    pass


class GeneratorError(ConvertorError):
    pass


def normalize(key):
    """The key of a convention comment: case, underscores and the trailing
    colon do not matter."""
    key = ' '.join(key.strip().rstrip(':').lower().replace('_', ' ').split())
    return SYNONYMS.get(key, key)


def identifier(text):
    return re.sub(r'\W', '_', text)


def text_literal(text):
    """The text as a readable triple-quoted literal: only the backslashes,
    the carriage returns and the quotes that would close it are escaped."""
    chars = []
    quotes = 0                          # the unescaped quotes in a row
    for index, char in enumerate(text):
        if char == '\\':
            char = '\\\\'
        elif char == '\r':
            char = '\\r'
        elif char == "'" and (quotes == 2 or index == len(text) - 1):
            char = "\\'"
        quotes = quotes + 1 if char == "'" else 0
        chars.append(char)
    return "'''" + ''.join(chars) + "'''"


class Block:
    """A piece of the diagram's Python in the lint module: the text, where
    it is from, the element and the module line of its first line."""

    def __init__(self, text, where, element, kind, guard=False):
        self.text = text
        self.where = where
        self.element = element
        self.kind = kind
        self.guard = guard
        self.line = 0

    def place(self, line):
        """The place of a module line inside the block, or None."""
        if self.line and line >= self.line:
            return line - self.line + 1
        return None


def assigned_names(tree):
    """The names a module-level text binds when it runs in one namespace:
    the targets of the assignments at any depth outside the functions and
    the classes, the definitions, the imports and the global statements."""
    names = set()

    def targets(node):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for element in node.elts:
                targets(element)
        elif isinstance(node, ast.Starred):
            targets(node.value)

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(child.name)
                continue
            if isinstance(child, ast.Lambda):
                continue
            if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for target in getattr(child, 'targets', None) or [child.target]:
                    targets(target)
            elif isinstance(child, (ast.For, ast.AsyncFor)):
                targets(child.target)
            elif isinstance(child, ast.withitem) and child.optional_vars is not None:
                targets(child.optional_vars)
            elif isinstance(child, ast.NamedExpr):
                targets(child.target)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                for alias in child.names:
                    names.add((alias.asname or alias.name).split('.')[0])
            elif isinstance(child, ast.Global):
                names.update(child.names)
            visit(child)

    visit(tree)
    return names


class CodeGenerator:

    def __init__(self, graph_file, main=None, tick_len=TICK_LEN):
        self.graph_file = graph_file
        self.tick_len = tick_len
        try:
            self.machines = hsmd_reader.load(graph_file)
            # the program carries the diagram and the documents it references
            self.documents = hsmd_reader.read_documents(graph_file)
        except hsmd_reader.DocumentError as e:
            raise ParserError(str(e)) from e
        self.machine = self.__select(self.machines, main)
        # the convention comments belong to the program: every machine's count
        self.sections = {}
        for machine in self.machines:
            for name, body in machine.comments:
                self.__section(name, body.split('\n'))
            for body in machine.informal:
                lines = body.split('\n')
                self.__section(lines[0], lines[1:])
        self.arguments = self.__arguments()

    def __select(self, machines, main):
        if main is None:
            return machines[0]
        for machine in machines:
            if main in (machine.id, machine.name):
                return machine
        raise ParserError("The graph {} has no state machine '{}'".format(
            self.graph_file, main))

    def __section(self, key, lines):
        key = normalize(key)
        if key not in SECTIONS:
            return
        while lines and not lines[0].strip():
            lines = lines[1:]
        while lines and not lines[-1].strip():
            lines = lines[:-1]
        self.sections.setdefault(key, []).extend(line.rstrip() for line in lines)

    def __lines(self, key):
        return self.sections.get(key, [])

    def __arguments(self):
        """The declared arguments: name -> the default value, a literal."""
        declared = {}
        for line in self.__lines(SECTION_ARGUMENTS):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            name, separator, text = line.partition('=')
            name = name.strip()
            if not separator or not name.isidentifier():
                raise GeneratorError("Bad argument line '{}'".format(line))
            try:
                declared[name] = ast.literal_eval(text.strip())
            except (ValueError, SyntaxError):
                raise GeneratorError("The default of the argument {} is not a literal: {}"
                                     .format(name, text.strip())) from None
        return declared

    def __scripts(self):
        """The init scripts: (name, text) in the order of the comment."""
        path = os.path.dirname(os.path.abspath(self.graph_file))
        scripts = []
        for line in self.__lines(SECTION_SCRIPTS):
            name = line.strip()
            if not name.endswith(SCRIPT_EXTENSION):
                continue
            filename = os.path.join(path, name)
            if not os.path.isfile(filename):
                raise GeneratorError('Cannot open the imported Python file {}'.format(filename))
            with open(filename, encoding='utf-8') as script:
                scripts.append((name, script.read().rstrip('\n')))
        return scripts

    # ------------------------------------------------------------------------
    # the program

    def __preamble(self, lint=False):
        """The common part of the program and of the lint module, as lines."""
        lines = ['# The {} of the state machine {!r}'.format(
            'lint view' if lint else 'program', self.machine.name),
                 '# from {}'.format(os.path.abspath(self.graph_file)),
                 '# Generated by HSM-to-Python version {}{}'.format(
                     VERSION, '; not for running' if lint else ''), '']
        lines += (LINT_HEADER if lint else HEADER).split('\n')
        lines += ['DIAGRAM = {!r}  # the name of the diagram in DOCUMENTS'.format(
                      next(iter(self.documents))),
                  'MAIN = {!r}'.format(self.machine.id),
                  'TICK_LEN = {}                 # the period of TIME_TICK, ms'.format(
                      self.tick_len)]
        lines += ['', '# Arguments:']
        if lint:
            lines += ['{} = {!r}'.format(k, v) for k, v in self.arguments.items()]
        else:
            lines += ['_ARGUMENTS = {!r}'.format(self.arguments),
                      'globals().update(_set_arguments(_ARGUMENTS))']
        return lines

    def __sections(self, lines, mark):
        """Append the initialization sections to the lines; mark(title,
        line) notes the module line a section starts after."""
        init = self.__lines(SECTION_INIT)
        if init:
            lines += ['', '# {}:'.format(TITLES[SECTION_INIT])]
            mark(TITLES[SECTION_INIT], len(lines))
            lines += init
        for name, text in self.__scripts():
            lines += ['', '# {}: {}'.format(TITLES[SECTION_SCRIPTS], name)]
            mark('{} {}'.format(TITLES[SECTION_SCRIPTS], name), len(lines))
            lines += text.split('\n')

    def generate_code(self, target=None):
        """Write the program to the file, or to the standard output."""
        lines = self.__preamble()
        self.__sections(lines, lambda title, index: None)
        loop = ''.join(INDENT * 2 + line + '\n' if line.strip() else '\n'
                       for line in self.__lines(SECTION_LOOP))
        text = '\n'.join(lines) + '\n' + FOOTER.format(loop=loop,
                                                       documents=self.__documents())
        self.__write(target, text)

    def __documents(self):
        """The entries of DOCUMENTS: the texts as readable literals."""
        entries = ''
        for name, text in self.documents.items():
            literal = text_literal(text)
            if ast.literal_eval(literal) != text:
                raise GeneratorError('Cannot embed the document {}'.format(name))
            entries += '{}{!r}: {},\n'.format(INDENT, name, literal)
        return entries

    @staticmethod
    def __write(target, text):
        if target is None:
            sys.stdout.write(text)
            return
        with open(target, 'w', encoding='utf-8') as f:
            f.write(text)

    # ------------------------------------------------------------------------
    # the lint module

    def blocks(self):
        """The Python pieces of the diagram: the blocks of every machine,
        the inlined copies excluded."""
        result = []
        for machine in self.machines:
            for vertex in machine.vertices.values():
                if hsmd_reader.INLINE_SEPARATOR in vertex.id:
                    continue
                for kind, group in (('entry', vertex.entry), ('exit', vertex.exit)):
                    for index, block in enumerate(group):
                        where = "{}, {} '{}', {}".format(machine.where(), vertex.kind,
                                                          vertex.id, kind)
                        if len(group) > 1:
                            where += ' {}'.format(index + 1)
                        result.append(Block(block.text, where, vertex.id, kind))
                for number, reaction in enumerate(vertex.reactions):
                    where = reaction.where
                    kind = 'internal_{}'.format(number + 1) if reaction.target is None else ''
                    # an internal transition is a part of its state for the editor
                    element = vertex.id if reaction.target is None else reaction.id
                    if reaction.guard and not reaction.is_else():
                        result.append(Block(reaction.guard, where + ', guard', element,
                                            kind + '_guard' if kind else 'guard', guard=True))
                    if reaction.behavior.strip():
                        result.append(Block(reaction.behavior, where, element,
                                            kind or 'action'))
        return result

    def lint_module(self):
        """The diagram's code as one module for a linter: the text, the
        blocks with their first lines, and the syntax errors found."""
        sections = []
        lines = self.__preamble(lint=True)
        self.__sections(lines, lambda title, index: sections.append((title, index)))
        lines += ['', 'dispatcher = hsmd.Dispatcher.__new__(hsmd.Dispatcher)',
                  "event = hsmd.Event('')", '', '# The components:']
        for declaration in self.machine.components:
            ctype = declaration.type
            if ctype in STANDARD_TYPES:
                ctype = 'hsmd.' + ctype
            lines.append('{} = {}({!r}, None)'.format(declaration.id, ctype, declaration.id))
        # the names the program defines, so a block's new global gets a definition
        defined = set(self.arguments) | {'dispatcher', 'event', 'DISPATCH', 'DIAGRAM',
                                         'MAIN', 'TICK_LEN', 'hsmd', 'sys', 'time', 'ast'}
        defined |= {d.id for d in self.machine.components}
        for text in [self.__lines(SECTION_INIT)] + [s.split('\n') for _, s in self.__scripts()]:
            try:
                defined |= assigned_names(ast.parse('\n'.join(text)))
            except SyntaxError:
                pass
        blocks = self.blocks()
        errors = []
        bodies = []
        created = {}
        for block in blocks:
            if block.guard:
                code, names = '({})'.format(' '.join(block.text.split('\n'))), set()
                try:
                    ast.parse(code, mode='eval')
                except SyntaxError as e:
                    errors.append((block, e))
                    code = 'None'
                body = ['return ' + code]
            else:
                try:
                    names = assigned_names(ast.parse(block.text))
                except SyntaxError as e:
                    errors.append((block, e))
                    names = set()
                    body = ['pass  # a syntax error, see the findings']
                else:
                    body = block.text.split('\n') or ['pass']
            for name in sorted(names - defined):
                created.setdefault(name, block.where)
            bodies.append((block, sorted(names), body))
        if created:
            lines += ['', '# The names the blocks create:']
            lines += ['{} = None  # {}'.format(name, where)
                      for name, where in sorted(created.items())]
        used = set()
        for block, names, body in bodies:
            name = identifier('_{}_{}'.format(block.element, block.kind))
            while name in used:
                name += '_'
            used.add(name)
            lines += ['', '', 'def {}():'.format(name), INDENT + '# ' + block.where]
            if names:
                lines.append(INDENT + 'global ' + ', '.join(names))
            block.line = len(lines) + 1
            lines += [INDENT + line if line.strip() else '' for line in body]
        return '\n'.join(lines) + '\n', blocks, sections, errors

    def generate_lint(self, target=None):
        text = self.lint_module()[0]
        self.__write(target, text)


def arguments(description):
    """The command line shared by the generator, the runner and the check."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('graph', help='the diagram (CyberiadaML or yEd GraphML)')
    parser.add_argument('--main', metavar='NAME',
                        help='the state machine to run (default: the first one)')
    parser.add_argument('--tick', metavar='MS', type=int, default=TICK_LEN,
                        help='the period of the TIME_TICK event, ms (default: {})'.format(
                            TICK_LEN))
    return parser


def run():
    parser = arguments('Generate the Python program of a state machine diagram.')
    parser.add_argument('output', nargs='?', help='the program file (default: stdout)')
    parser.add_argument('--lint', action='store_true',
                        help='write the lint view of the diagram instead of the program')
    parser.add_argument('--check', action='store_true',
                        help='check the code of the diagram first, refuse it with errors')
    args = parser.parse_args()
    try:
        generator = CodeGenerator(args.graph, main=args.main, tick_len=args.tick)
        if args.check:
            import hsmcheck  # pylint: disable=import-outside-toplevel
            if hsmcheck.report(generator):
                return 1
        if args.lint:
            generator.generate_lint(args.output)
        else:
            generator.generate_code(args.output)
    except ParserError as e:
        sys.stderr.write('Graph parsing error: {}\n'.format(e))
        return 1
    except GeneratorError as e:
        sys.stderr.write('Code generating error: {}\n'.format(e))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(run())
