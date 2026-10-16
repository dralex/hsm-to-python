#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The checks of the machine: its events and its structure
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
import sys

import testenv  # pylint: disable=unused-import
import gencode  # pylint: disable=wrong-import-position
import hsmcheck  # pylint: disable=wrong-import-position

MODEL_DIR = 'model'
GRAPHS_DIR = 'graphs'
GRAPHML = '.graphml'


def findings(path):
    """The findings of the machine checks as `severity element line rule` lines."""
    return ''.join('{} {} {} {}\n'.format(f.severity, f.element or '-', f.line or '-', f.rule)
                   for f in hsmcheck.model_findings(gencode.CodeGenerator(path)))


def check_planted(regen):
    """The diagrams with planted faults give their expected findings."""
    failed = 0
    for name in sorted(n[:-len(GRAPHML)] for n in os.listdir(MODEL_DIR) if n.endswith(GRAPHML)):
        output = findings(os.path.join(MODEL_DIR, name + GRAPHML))
        expected_path = os.path.join(MODEL_DIR, name + '.txt')
        if regen:
            with open(expected_path, 'w', encoding='utf-8') as f:
                f.write(output)
            print('SAVE {}'.format(name))
            continue
        with open(expected_path, encoding='utf-8') as f:
            expected = f.read()
        if output != expected:
            print('FAIL {}: required="{}" output="{}"'.format(name, expected, output))
            failed += 1
        else:
            print('ok   {}'.format(name))
    return failed


def check_clean():
    """The working diagrams give no findings."""
    failed = 0
    for name in sorted(n for n in os.listdir(GRAPHS_DIR) if n.endswith(GRAPHML)):
        try:
            output = findings(os.path.join(GRAPHS_DIR, name))
        except gencode.ConvertorError:
            continue                # a diagram the tests expect refused
        if output:
            print('FAIL clean {}:\n{}'.format(name, output))
            failed += 1
    if not failed:
        print('ok   clean diagrams')
    return failed


def main():
    failed = check_planted('--regen' in sys.argv) + check_clean()
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
