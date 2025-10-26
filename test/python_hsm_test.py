#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# Copyright (C) 2023-2025      Alexey Fedoseev <aleksey@fedoseev.net>
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

PROGRAM_PREAMBLE = """import sys
import pysm
sys.path.append('..')
"""

TESTS_DIR = 'graphs'
TEST_PATTERN = re.compile(r'(?P<filebase>[^-]+)(-(?P<number>\d+))?.graphml$')
TEST_GRAPHML_EXT = '.graphml'
TEST_OUTPUT_EXT = '.txt'
TMP_FILE = 'tmp.py'
PYTHON_CMD = 'python3'

sys.path.append('..')

import gencode

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
            g = gencode.CodeGenerator(graphfile, generate_loop=True, allow_empty_trans=True)
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

if __name__ == '__main__':
    verbose = len(sys.argv) > 1 and sys.argv[1] == '-v'
    tests = get_tests()
    run_tests(tests, verbose)
    sys.exit(0)
