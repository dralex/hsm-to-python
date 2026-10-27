#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The session of the editor: hsm --session answers a scripted editor
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

"""hsm-run --session against a scripted editor: the virtual clock, INIT, a step,
a restart; a dispatcher without the session refused."""

import json
import os
import subprocess
import sys
import tempfile

import testenv  # pylint: disable=unused-import
import hsm  # pylint: disable=wrong-import-position

# prints RUNNING on entry, TICK at every TIME_TICK_1S
DIAGRAM = os.path.join('runner', 'forever.graphml')
WAIT_S = 60
MESSAGES = [
    {'id': 1, 'method': 'initialize', 'params': {'session': 1}},
    {'method': 'control', 'params': {'command': 'step', 'unit': 'event'}},
    {'method': 'control', 'params': {'command': 'restart'}},
    {'id': 2, 'method': 'shutdown'},
]


def session(env=None):
    """The messages the session sends for the script, and its exit code."""
    lines = ''.join(json.dumps(dict(m, jsonrpc='2.0')) + '\n' for m in MESSAGES)
    result = subprocess.run([sys.executable, '-m', 'hsm', DIAGRAM, '--session', '--tick', '100'],
                            input=lines, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=WAIT_S, env=env, check=False)
    return [json.loads(line) for line in result.stdout.splitlines()], result.returncode, result.stderr


def kind(message):
    if 'method' in message:
        return message['method']
    return 'reply {}'.format(message['id'])


def test_session():
    """The program runs on the virtual clock: INIT, a step to the time event,
    a restart that runs the entry again."""
    messages, code, err = session()
    kinds = [kind(m) for m in messages]
    expected = ['log', 'reply 1', 'history', 'state', 'log', 'history', 'state',
                'log', 'history', 'state', 'reply 2']
    if code != 0 or kinds != expected:
        return 'exit {}, {}\n{}'.format(code, kinds, err)
    model = messages[1]['result']
    first, step, again = messages[3]['params'], messages[5]['params'], messages[9]['params']
    checks = [
        (model['kind'], 'driven'), (model['events'], ['TIME_TICK_1S']),
        (messages[0]['params']['text'], 'RUNNING'),
        ((messages[2]['params']['event'], messages[2]['params']['outcome'],
          messages[2]['params']['origin']), ('INIT', 'dropped', 'model')),
        ((first['active'], first['fired']), (['n0'], ['e0'])),
        (messages[4]['params']['text'], 'TICK'),
        ((step['event'], step['time'], step['fired']), ('TIME_TICK_1S', 1.0, ['n0'])),
        (messages[7]['params']['text'], 'RUNNING'),
        ((again['time'], again['fired']), (0.0, ['e0'])),
    ]
    for got, want in checks:
        if got != want:
            return '{!r} instead of {!r}'.format(got, want)
    return None


def test_old_dispatcher():
    """A dispatcher without hsmd_session: the session is refused with the version."""
    with tempfile.TemporaryDirectory() as blocked:
        with open(os.path.join(blocked, 'hsmd_session.py'), 'w', encoding='utf-8') as f:
            f.write("raise ImportError('an older dispatcher')\n")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([blocked, os.environ.get('PYTHONPATH', '')]))
        messages, code, err = session(env)
    if code != hsm.EXIT_GENERATOR or messages or hsm.SESSION_DISPATCHER not in err:
        return 'exit {}, {} {!r}'.format(code, messages, err)
    return None


def main():
    failed = 0
    for name, case in [('session', test_session), ('old dispatcher', test_old_dispatcher)]:
        problem = case()
        if problem:
            print('FAIL {}: {}'.format(name, problem))
            failed += 1
        else:
            print('ok   {}'.format(name))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
