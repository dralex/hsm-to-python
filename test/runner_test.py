#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The runner into a pipe: the output line by line, the timeout, a SIGTERM
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
import select
import signal
import subprocess
import sys

import testenv  # pylint: disable=unused-import
import hsm  # pylint: disable=wrong-import-position

# prints RUNNING, then TICK every second, until it is stopped
DIAGRAM = os.path.join('runner', 'forever.graphml')
FIRST_LINES = ['RUNNING', 'TICK']
TIMEOUT_S = 3
WAIT_S = 30


def runner(*args):
    # a session of its own: the cleanup reaches a program the runner left behind
    return subprocess.Popen([sys.executable, '-m', 'hsm', DIAGRAM] + list(args),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, start_new_session=True)


def cleanup(process):
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.kill()


def test_timeout():
    """The lines printed before the timeout are kept."""
    process = runner('--timeout', str(TIMEOUT_S))
    try:
        out, err = process.communicate(timeout=WAIT_S)
    finally:
        cleanup(process)
    missing = [line for line in FIRST_LINES if line not in out.splitlines()]
    if process.returncode != hsm.EXIT_TIMEOUT or missing or 'stopped after' not in err:
        return 'exit {}, missing {}, stderr {!r}'.format(process.returncode, missing, err)
    return None


def test_sigterm():
    """The output comes while the program runs; a SIGTERM to the runner stops the
    program too, so the pipe closes."""
    process = runner()
    try:
        # a buffered program would keep its first line until it ends, that is never
        if not select.select([process.stdout], [], [], WAIT_S)[0]:
            return 'no line came while the program ran'
        first = process.stdout.readline().rstrip('\n')
        process.send_signal(signal.SIGTERM)
        try:
            process.communicate(timeout=WAIT_S)
        except subprocess.TimeoutExpired:
            return 'the program outlived the runner'
    finally:
        cleanup(process)
    if first != FIRST_LINES[0]:
        return 'the first line {!r} did not come while the program ran'.format(first)
    return None


def main():
    cases = [('timeout', test_timeout)]
    if os.name == 'posix':
        cases.append(('sigterm', test_sigterm))
    failed = 0
    for name, case in cases:
        problem = case()
        if problem:
            print('FAIL {}: {}'.format(name, problem))
            failed += 1
        else:
            print('ok   {}'.format(name))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
