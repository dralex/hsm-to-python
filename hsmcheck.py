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

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import gencode
import hsmd

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
    findings = [Finding(ERROR, 'syntax-error', block.where, block.element, error.lineno,
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
