#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The editor plugin, run through the batch mode of CyberiadaEditor
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
import shutil
import subprocess
import sys
import tempfile

PLUGIN = 'hsm-to-python'
REPOSITORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
COMMANDS = ('hsm-check', 'hsm-gencode', 'hsm-run')


def editor():
    """The editor binary: CYBERIADA_EDITOR, PATH, or the sibling build."""
    candidates = [os.environ.get('CYBERIADA_EDITOR'), shutil.which('CyberiadaEditor'),
                  os.path.join(REPOSITORY, '..', 'CyberiadaHSM-Editor', 'build',
                               'CyberiadaEditor')]
    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def batch(binary, *args):
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    result = subprocess.run([binary, '--batch'] + list(args), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, env=env,
                            cwd=REPOSITORY, check=False, timeout=120)
    return result.returncode, result.stdout


def main():
    binary = editor()
    missing = [c for c in COMMANDS if shutil.which(c) is None]
    if binary is None or missing:
        print('skipped: {}'.format('no CyberiadaEditor binary' if binary is None
                                   else 'not in PATH: ' + ' '.join(missing)))
        return 0
    failed = 0
    code, out = batch(binary, '--plugin-path', '.', '--list-plugins')
    if code != 0 or PLUGIN not in out or 'enabled' not in out:
        print('FAIL list: exit {}\n{}'.format(code, out))
        failed += 1
    else:
        print('ok   list')
    code, out = batch(binary, 'test/graphs/vacuum.graphml', '--plugin-path', '.',
                      '--run-plugin', PLUGIN + ':check', '--dump-plugin')
    if code != 0 or 'undefined' in out:
        print('FAIL check vacuum: exit {}\n{}'.format(code, out))
        failed += 1
    else:
        print('ok   check vacuum')
    code, out = batch(binary, 'test/lint/bad.graphml', '--plugin-path', '.',
                      '--run-plugin', PLUGIN + ':check', '--dump-plugin')
    if code != 0 or 'syntax-error' not in out or 'count: 0' in out:
        print('FAIL check bad: exit {}\n{}'.format(code, out))
        failed += 1
    else:
        print('ok   check bad')
    with tempfile.TemporaryDirectory() as directory:
        code, out = batch(binary, 'test/graphs/vacuum.graphml', '--plugin-path', '.',
                          '--run-plugin', PLUGIN + ':generate', '--plugin-param',
                          'dir=' + directory, '--dump-plugin')
        program = os.path.join(directory, 'vacuum.py')
        if code != 0 or not os.path.isfile(program):
            print('FAIL generate: exit {}\n{}'.format(code, out))
            failed += 1
        else:
            print('ok   generate')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
