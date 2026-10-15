#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The embedded diagram: a generated program runs without the diagram files
#
# Copyright (C) 2026 Alexey Fedoseev <aleksey@fedoseev.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see https://www.gnu.org/licenses/
# -----------------------------------------------------------------------------

import ast
import os
import shutil
import subprocess
import sys
import tempfile

import testenv  # pylint: disable=unused-import
import gencode  # pylint: disable=wrong-import-position

GRAPHS_DIR = 'graphs'
# an init script and a submachine state; a submachine state of another document
DIAGRAMS = ('vacuum', 'external')
# the texts that could break a triple-quoted literal
LITERALS = ['', "'", "''", "'''", "''''''", "a'", "'a", '\\', "\\'", 'end\\',
            "x'''y'''z", 'a\r\nb', '"""', '\\n is not a newline', 'Привет']


def check_literals():
    """The literals of the generated program give the texts back."""
    bad = [text for text in LITERALS
           if ast.literal_eval(gencode.text_literal(text)) != text]
    if bad:
        print('FAIL literals: {!r}'.format(bad))
        return 1
    print('ok   literals')
    return 0


def check_program(name):
    """Generate the program from a copy of the diagrams, remove the copy and
    run the program elsewhere."""
    with open(os.path.join(GRAPHS_DIR, name + '.txt'), encoding='utf-8') as f:
        expected = f.read()
    with tempfile.TemporaryDirectory() as target:
        program = os.path.join(target, name + '.py')
        with tempfile.TemporaryDirectory() as source:
            graphs = os.path.join(source, GRAPHS_DIR)
            shutil.copytree(GRAPHS_DIR, graphs)
            gencode.CodeGenerator(os.path.join(graphs, name + '.graphml')).generate_code(program)
        with open(program, encoding='utf-8') as f:
            # the path of the diagram stays in the header comment only
            mentions = f.read().count(source)
        result = subprocess.run([sys.executable, program], cwd=target, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, universal_newlines=True,
                                check=False, timeout=60)
    if result.returncode != 0 or result.stdout != expected or mentions != 1:
        print('FAIL {}: exit {}, the diagram path {} times, output:\n{}'.format(
            name, result.returncode, mentions, result.stdout))
        return 1
    print('ok   {}'.format(name))
    return 0


def main():
    failed = check_literals()
    for name in DIAGRAMS:
        failed += check_program(name)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
