#!/usr/bin/python3
# -----------------------------------------------------------------------------
#  HSM-to-Python conversion tool
#
#  The runner: generates the program of a diagram and runs it
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

import os
import subprocess
import sys
import tempfile

import gencode
import hsmcheck

EXIT_PARSER = 1
EXIT_GENERATOR = 2
EXIT_UNEXPECTED = 3
EXIT_TIMEOUT = 4


def run():
    parser = gencode.arguments('Run a state machine diagram on the HSM dispatcher.')
    parser.add_argument('--set', metavar='NAME=VALUE', action='append', default=[],
                        help='the value of an argument of the diagram')
    parser.add_argument('--settings', metavar='FILE',
                        help='a file of NAME = VALUE lines, the arguments of the diagram')
    parser.add_argument('--timeout', metavar='S', type=float, default=0,
                        help='stop the program after S seconds (default: never)')
    parser.add_argument('--check', action='store_true',
                        help='check the code of the diagram first, refuse it with errors')
    parser.add_argument('--keep', action='store_true', help='keep the generated program')
    args = parser.parse_args()
    try:
        generator = gencode.CodeGenerator(args.graph, main=args.main, tick_len=args.tick)
    except gencode.ParserError as e:
        sys.stderr.write('Graph parsing error: {}\n'.format(e))
        return EXIT_PARSER
    if args.check and hsmcheck.report(generator):
        return EXIT_PARSER
    with tempfile.NamedTemporaryFile(prefix='hsm-', suffix='.py', delete=False) as program:
        path = program.name
    command = [sys.executable, path]
    for pair in args.set:
        command += ['--set', pair]
    if args.settings:
        command += ['--settings', args.settings]
    try:
        generator.generate_code(path)
        if args.keep:
            sys.stderr.write('The program is kept in {}\n'.format(path))
        return subprocess.run(command, check=False,
                              timeout=args.timeout or None).returncode
    except gencode.GeneratorError as e:
        sys.stderr.write('Code generating error: {}\n'.format(e))
        return EXIT_GENERATOR
    except subprocess.TimeoutExpired:
        sys.stderr.write('The program was stopped after {} seconds\n'.format(args.timeout))
        return EXIT_TIMEOUT
    except KeyboardInterrupt:
        return EXIT_UNEXPECTED
    finally:
        if not args.keep:
            os.remove(path)


if __name__ == '__main__':
    sys.exit(run())
