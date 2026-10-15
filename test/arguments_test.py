#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The arguments of a generated program: --set, --settings, --help
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

import os
import subprocess
import sys
import tempfile

import testenv  # pylint: disable=unused-import
import gencode  # pylint: disable=wrong-import-position

DIAGRAM = os.path.join('graphs', 'vacuum.graphml')


def run(program, *args):
    result = subprocess.run([sys.executable, program] + list(args), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, universal_newlines=True, check=False,
                            timeout=60)
    return result.returncode, result.stdout


def main():
    failed = 0
    with tempfile.TemporaryDirectory() as directory:
        program = os.path.join(directory, 'vacuum.py')
        gencode.CodeGenerator(DIAGRAM).generate_code(program)
        settings = os.path.join(directory, 'settings.txt')
        with open(settings, 'w', encoding='utf-8') as f:
            f.write('# the arguments\nallowed = hall\n')
        cases = [
            ('help', ('--help',), 0, ["allowed = 'kitchen'"]),
            ('undeclared', ('--set', 'nosuch=1'), 1, ["'nosuch' is not an argument"]),
            ('unknown option', ('--bogus',), 1, ['unknown argument']),
            ('set', ('--set', 'allowed=hall'), 0,
             ['order refused: kitchen', 'order accepted: hall']),
            ('settings file', ('--settings', settings), 0, ['order accepted: hall']),
        ]
        for name, args, code, expected in cases:
            result, output = run(program, *args)
            missing = [text for text in expected if text not in output]
            if result != code or missing:
                print('FAIL {}: exit {} (expected {}), missing {}'.format(
                    name, result, code, missing))
                failed += 1
            else:
                print('ok   {}'.format(name))
    # a wrong type for an int argument, on a tiny diagram of the lint tests
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
