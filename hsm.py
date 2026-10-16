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
import signal
import subprocess
import sys
import tempfile

import gencode
import hsmcheck
import hsmplugin

EXIT_PARSER = 1
EXIT_GENERATOR = 2
EXIT_UNEXPECTED = 3
EXIT_TIMEOUT = 4


def install_plugin():
    """The --install-editor-plugin [DIR] command."""
    index = sys.argv.index('--install-editor-plugin')
    target = sys.argv[index + 1] if index + 1 < len(sys.argv) else None
    try:
        folder = hsmplugin.install(target or None)
    except hsmplugin.PluginError as e:
        sys.stderr.write('{}\n'.format(e))
        return EXIT_GENERATOR
    print('installed the editor plugin {} to\n  {}\nit runs {}; restart the editor'.format(
        hsmplugin.PLUGIN_ID, folder, sys.executable))
    return 0


def run_program(command, timeout):
    """Run the program until it ends, the timeout (subprocess.TimeoutExpired) or a SIGTERM
    to the runner, which the editor's Cancel sends to the runner only."""
    with subprocess.Popen(command) as process:
        previous = signal.signal(signal.SIGTERM, lambda signum, frame: process.terminate())
        try:
            return process.wait(timeout=timeout or None)
        except BaseException:
            # the with waits for it
            process.kill()
            raise
        finally:
            signal.signal(signal.SIGTERM, previous)


def run():
    if '--install-editor-plugin' in sys.argv:
        return install_plugin()
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
    parser.add_argument('--install-editor-plugin', metavar='DIR', nargs='?', const='',
                        help='copy the editor plugin into the plugin folder of the editor '
                             '(or into DIR) and exit')
    args = parser.parse_args()
    try:
        generator = gencode.CodeGenerator(args.graph, main=args.main, tick_len=args.tick)
    except gencode.ParserError as e:
        sys.stderr.write('Graph parsing error: {}\n'.format(e))
        return EXIT_PARSER
    if args.check:
        if hsmcheck.report(generator):
            return EXIT_PARSER
    else:
        hsmcheck.warn(generator)
    with tempfile.NamedTemporaryFile(prefix='hsm-', suffix='.py', delete=False) as program:
        path = program.name
    # unbuffered: the output reaches a pipe line by line and survives a kill
    command = [sys.executable, '-u', path]
    for pair in args.set:
        command += ['--set', pair]
    if args.settings:
        command += ['--settings', args.settings]
    try:
        generator.generate_code(path)
        if args.keep:
            sys.stderr.write('The program is kept in {}\n'.format(path))
        return run_program(command, args.timeout)
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
