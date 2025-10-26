#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing script
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

sys.path.append('..')
import gencode

PYTHON_CMD = 'python3'
TMP_FILE = 'tmp.py'

def run_script(filename):
    idx = filename.index('.graphml')
    if idx < 0:
        print('Bad graph file name {}'.format(filename))
        sys.exit(1)
    if not os.path.isfile(filename):
        print('Cannot find file {}'.format(filename))
        sys.exit(1)
    try:
        g = gencode.CodeGenerator(filename, generate_loop=True, allow_empty_trans=True)
        g.generate_code(TMP_FILE)
        result = subprocess.run([PYTHON_CMD, TMP_FILE],
                                capture_output=True,
                                text=True,
                                check=True)
        print(result.stdout)
        print('OK')
    except gencode.ConvertorError:
        if output == 'HSMException\n':
            print('OK')
            sys.exit(0)
        print('failed: {}\n\n Program:{}\n'.format(s, TMP_FILE))
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print('Script failed: {}\n\n Program graph:{} Program: {}\n'.format(e.stderr, filename, TMP_FILE))
        sys.exit(1)
    except KeyboardInterrupt as e:
        print('Script failed: {}\n\n Program graph:{} Program: {}\n'.format(e, filename, TMP_FILE))
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 {} <graphml-file>'.format(sys.argv[0]))
        sys.exit(1)
    run_script(sys.argv[1])
