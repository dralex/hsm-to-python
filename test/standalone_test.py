#!/usr/bin/python3
# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The generated program: the Python code of the machine, run without the
# diagram files and without the CyberiadaML module
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

import testenv  # pylint: disable=unused-import
import gencode  # pylint: disable=wrong-import-position

GRAPHS_DIR = 'graphs'
# an init script and a submachine state; a submachine state of another document
DIAGRAMS = ('vacuum', 'external')
# a block failing on its second line
FAILING = '''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <data key="gFormat">Cyberiada-GraphML-1.0</data>
  <key id="gFormat" for="graphml" attr.name="format" attr.type="string"/>
  <key id="dName" for="graph" attr.name="name" attr.type="string"/>
  <key id="dName" for="node" attr.name="name" attr.type="string"/>
  <key id="dStateMachine" for="graph" attr.name="stateMachine" attr.type="string"/>
  <key id="dNote" for="node" attr.name="note" attr.type="string"/>
  <key id="dVertex" for="node" attr.name="vertex" attr.type="string"/>
  <key id="dData" for="node" attr.name="data" attr.type="string"/>
  <graph id="G" edgedefault="directed">
    <data key="dStateMachine"/>
    <data key="dName">Failing</data>
    <node id="nMeta">
      <data key="dNote">formal</data>
      <data key="dName">CGML_META</data>
      <data key="dData">standardVersion/ 1.0</data>
    </node>
    <node id="init">
      <data key="dVertex">initial</data>
    </node>
    <node id="s">
      <data key="dName">S</data>
      <data key="dData">entry/
count = 0
ratio = 1 / count</data>
    </node>
    <edge id="init-s" source="init" target="s"/>
  </graph>
</graphml>
'''
FAILURE = "machine 'G', state 's', entry, line 2: ZeroDivisionError"


def run_alone(program, directory):
    """Run the program where the CyberiadaML module cannot be imported."""
    blocked = os.path.join(directory, 'blocked')
    os.makedirs(blocked)
    with open(os.path.join(blocked, 'CyberiadaML.py'), 'w', encoding='utf-8') as f:
        f.write("raise ImportError('CyberiadaML is blocked')\n")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([blocked, os.environ['PYTHONPATH']]))
    return subprocess.run([sys.executable, program], cwd=directory, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, env=env,
                          check=False, timeout=60)


def check_program(name):
    """Generate the program from a copy of the diagrams, remove the copy and
    run the program elsewhere, without CyberiadaML."""
    with open(os.path.join(GRAPHS_DIR, name + '.txt'), encoding='utf-8') as f:
        expected = f.read()
    with tempfile.TemporaryDirectory() as target:
        program = os.path.join(target, name + '.py')
        with tempfile.TemporaryDirectory() as source:
            graphs = os.path.join(source, GRAPHS_DIR)
            shutil.copytree(GRAPHS_DIR, graphs)
            gencode.CodeGenerator(os.path.join(graphs, name + '.graphml')).generate_code(program)
        with open(program, encoding='utf-8') as f:
            text = f.read()
        # the path of the diagram stays in the header comment only, no GraphML
        mentions = text.count(source)
        code = 'def ' in text and '<graphml' not in text
        result = run_alone(program, target)
    if result.returncode != 0 or result.stdout != expected or mentions != 1 or not code:
        print('FAIL {}: exit {}, the diagram path {} times, the code {}, output:\n{}{}'.format(
            name, result.returncode, mentions, code, result.stdout, result.stderr))
        return 1
    print('ok   {}'.format(name))
    return 0


def check_failure():
    """An error of the diagram's code names the element and the line of the block."""
    with tempfile.TemporaryDirectory() as directory:
        diagram = os.path.join(directory, 'failing.graphml')
        with open(diagram, 'w', encoding='utf-8') as f:
            f.write(FAILING)
        program = os.path.join(directory, 'failing.py')
        gencode.CodeGenerator(diagram).generate_code(program)
        result = run_alone(program, directory)
    if result.returncode == 0 or FAILURE not in result.stderr:
        print('FAIL failure: exit {}\n{}'.format(result.returncode, result.stderr))
        return 1
    print('ok   failure')
    return 0


def main():
    failed = check_failure()
    for name in DIAGRAMS:
        failed += check_program(name)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
