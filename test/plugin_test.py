#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The editor plugin, run through the batch mode of CyberiadaPro
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

import json
import os
import shutil
import subprocess
import sys
import tempfile

from testenv import REPOSITORY
import hsmplugin  # pylint: disable=wrong-import-position

PLUGIN = 'hsm-to-python'


def editor():
    """The editor binary: CYBERIADA_PRO, PATH, or the sibling build."""
    candidates = [os.environ.get('CYBERIADA_PRO'), shutil.which('CyberiadaPro'),
                  os.path.join(REPOSITORY, '..', 'CyberiadaHSM-Editor', 'build',
                               'CyberiadaPro')]
    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def batch(binary, *args):
    # a private profile: the run neither reads nor writes the user's settings
    with tempfile.TemporaryDirectory() as profile:
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen',
                   XDG_CONFIG_HOME=os.path.join(profile, 'config'),
                   XDG_DATA_HOME=os.path.join(profile, 'data'))
        result = subprocess.run([binary, '--batch'] + list(args), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True, env=env,
                                cwd=REPOSITORY, check=False, timeout=120)
    return result.returncode, result.stdout


def installer():
    """The copy of the plugin into a folder: pinned to this Python, replaced
    on a second install, a foreign folder refused."""
    failed = 0
    with tempfile.TemporaryDirectory() as directory:
        folder = hsmplugin.install(directory)
        with open(os.path.join(folder, hsmplugin.DESCRIPTOR), encoding='utf-8') as f:
            descriptor = json.load(f)
        pinned = ('interpreter' not in descriptor and
                  all(a['argv'][0] == sys.executable for a in descriptor['actions']))
        translated = os.path.isfile(os.path.join(folder, 'i18n', 'ru.json'))
        if folder != os.path.join(directory, PLUGIN) or not pinned or not translated:
            print('FAIL install: {} {}'.format(folder, descriptor.get('actions')))
            failed += 1
        elif hsmplugin.install(directory) != folder:
            print('FAIL install twice')
            failed += 1
        else:
            print('ok   install')
        foreign = os.path.join(directory, 'other')
        os.makedirs(os.path.join(foreign, PLUGIN))
        try:
            hsmplugin.install(foreign)
        except hsmplugin.PluginError:
            print('ok   foreign folder refused')
        else:
            print('FAIL foreign folder accepted')
            failed += 1
    return failed


def translation():
    """The Russian texts: every key is a text of the descriptor, every text is
    translated (the editor shows them by the interface language)."""
    with open(os.path.join(REPOSITORY, 'editor-plugin', 'plugin.json'), encoding='utf-8') as f:
        descriptor = json.load(f)
    with open(os.path.join(REPOSITORY, 'editor-plugin', 'i18n', 'ru.json'), encoding='utf-8') as f:
        ru = json.load(f)
    texts = {descriptor['name'], descriptor.get('description', '')}
    for item in descriptor.get('parameters', []) + descriptor['actions']:
        texts.update([item.get('label', ''), item.get('description', '')])
        texts.update(item.get('choices', []))
    texts.discard('')
    stale = sorted(set(ru) - texts)
    missing = sorted(texts - set(ru))
    if stale or missing:
        print('FAIL translation: stale {} missing {}'.format(stale, missing))
        return 1
    print('ok   translation')
    return 0


def main():
    failed = installer() + translation()
    binary = editor()
    if binary is None:
        print('skipped the editor part: no CyberiadaPro binary')
        return 1 if failed else 0
    print('editor: {}'.format(os.path.realpath(binary)))
    code, out = batch(binary, '--plugin-path', '.', '--list-plugins')
    if code != 0 or PLUGIN not in out or 'enabled' not in out:
        print('FAIL list: exit {}\n{}'.format(code, out))
        failed += 1
    else:
        print('ok   list')
    # the actions save the document after filling its platform language: copies,
    # with the Python files the diagrams import
    with tempfile.TemporaryDirectory() as directory:
        for folder in ('graphs', 'lint', 'runner'):
            shutil.copytree(os.path.join(REPOSITORY, 'test', folder), os.path.join(directory, folder))
        vacuum = os.path.join(directory, 'graphs', 'vacuum.graphml')
        bad = os.path.join(directory, 'lint', 'bad.graphml')
        code, out = batch(binary, vacuum, '--plugin-path', '.',
                          '--run-plugin', PLUGIN + ':check', '--dump-plugin')
        if code != 0 or 'undefined' in out:
            print('FAIL check vacuum: exit {}\n{}'.format(code, out))
            failed += 1
        else:
            print('ok   check vacuum')
        with open(vacuum, encoding='utf-8') as f:
            saved = f.read()
        if 'meta: set platformLanguage Python' not in out or 'platformLanguage/ Python' not in saved:
            print('FAIL platform language (an editor older than the declared '
                  'metainformation of the actions, EDIT-PLUG-34?): {}'.format(out))
            failed += 1
        else:
            print('ok   platform language')
        code, out = batch(binary, bad, '--plugin-path', '.',
                          '--run-plugin', PLUGIN + ':check', '--dump-plugin')
        if code != 0 or 'syntax-error' not in out or 'count: 0' in out:
            print('FAIL check bad: exit {}\n{}'.format(code, out))
            failed += 1
        else:
            print('ok   check bad')
        program_dir = os.path.join(directory, 'program')
        code, out = batch(binary, vacuum, '--plugin-path', '.',
                          '--run-plugin', PLUGIN + ':generate', '--plugin-param',
                          'dir=' + program_dir, '--dump-plugin')
        program = os.path.join(program_dir, 'vacuum.py')
        if code != 0 or not os.path.isfile(program):
            print('FAIL generate: exit {}\n{}'.format(code, out))
            failed += 1
        else:
            print('ok   generate')
        # the output of an endless program comes, its time limit is no failure
        forever = os.path.join(directory, 'runner', 'forever.graphml')
        code, out = batch(binary, forever, '--plugin-path', '.',
                          '--run-plugin', PLUGIN + ':run', '--plugin-param', 'timeout=3',
                          '--dump-plugin')
        if code != 0 or 'state: done' not in out or '  RUNNING' not in out or '  TICK' not in out:
            print('FAIL run: exit {}\n{}'.format(code, out))
            failed += 1
        else:
            print('ok   run')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
