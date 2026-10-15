#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# Copyright (C) 2023-2026      Alexey Fedoseev <aleksey@fedoseev.net>
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

import sys
import os
import subprocess
import re

import testenv  # pylint: disable=unused-import
import hsmd  # pylint: disable=wrong-import-order
import gencode
import hsmcheck

TESTS_DIR = 'graphs'
TEST_PATTERN = re.compile(r'(?P<filebase>[^-]+)(-(?P<number>\d+))?.graphml$')
TEST_GRAPHML_EXT = '.graphml'
TEST_OUTPUT_EXT = '.txt'
TMP_FILE = 'tmp.py'
PYTHON_CMD = sys.executable

LINT_DIR = 'lint'

def get_tests():
    tests = {}
    
    for filename in os.listdir(TESTS_DIR):
        m = TEST_PATTERN.match(filename)
        if not m:
            continue
        fields = m.groupdict()
        filebase = fields['filebase']
        if filebase not in tests:
            tests[filebase] = []
        n = fields['number']
        if n:
            tests[filebase].append(n)

    return tests

def run_tests(tests, verbose=False):
    for filebase, numbers in tests.items():
        if numbers:
            # multiple diagrams are not supported yet
            continue
        filename = filebase + TEST_GRAPHML_EXT
        graphfile = os.path.join(TESTS_DIR, filename)
        outputfile = os.path.join(TESTS_DIR, filebase + TEST_OUTPUT_EXT)
        if not os.path.isfile(graphfile) or not os.path.isfile(outputfile):
            continue
        output = open(outputfile).read()
        print('Test {}: '.format(filebase), end='')
        try:
            g = gencode.CodeGenerator(graphfile)
            findings, _ = hsmcheck.check(g)
            errors = [str(f) for f in findings if f.severity == hsmcheck.ERROR]
            if errors:
                raise Exception('failed: the code check: ' + '; '.join(errors))
            if verbose:
                for finding in findings:
                    print('\n    ' + str(finding), end='')
            g.generate_code(TMP_FILE)
            result = subprocess.run([PYTHON_CMD, TMP_FILE],
                                    capture_output=True,
                                    text=True,
                                    check=True)
            if result.stdout != output:
                raise Exception('failed: output mismatch, required="{}" output="{}"'.format(output, result.stdout))
            print('OK')
        except gencode.ConvertorError as e:
            if output == 'HSMException\n':
                print('OK')
                continue
            print('failed: {}\n\n Program:{}\n'.format(e, TMP_FILE))
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print('Script failed: {}\n\n Program:{}\n'.format(e.stderr, TMP_FILE))
            sys.exit(1)

def run_lint_tests():
    """The diagrams with planted faults: the findings are compared with the
    expected `severity element line rule` lines when pylint is the linter."""
    if hsmcheck.linter() != hsmcheck.PYLINT:
        print('Lint tests skipped: pylint is not installed')
        return
    for filename in sorted(os.listdir(LINT_DIR)):
        if not filename.endswith(TEST_GRAPHML_EXT):
            continue
        name = filename[:-len(TEST_GRAPHML_EXT)]
        print('Lint test {}: '.format(name), end='')
        with open(os.path.join(LINT_DIR, name + TEST_OUTPUT_EXT), encoding='utf-8') as f:
            expected = f.read()
        findings, _ = hsmcheck.check(gencode.CodeGenerator(os.path.join(LINT_DIR, filename)))
        output = ''.join('{} {} {} {}\n'.format(f.severity, f.element or '-', f.line or '-',
                                                 f.rule) for f in findings)
        if output != expected:
            print('failed: required="{}" output="{}"'.format(expected, output))
            sys.exit(1)
        print('OK')


if __name__ == '__main__':
    verbose = len(sys.argv) > 1 and sys.argv[1] == '-v'
    print('the generator {}, the dispatcher {}'.format(gencode.__file__, hsmd.__file__))
    tests = get_tests()
    run_tests(tests, verbose)
    os.remove(TMP_FILE)
    run_lint_tests()
    sys.exit(0)
