# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The modules under test: this repository, the installed dispatcher
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

"""Imported first by every test: the modules of this repository go before
their installed copies; the dispatcher is the installed one, or the one beside
this repository when none is installed. The paths hold for the programs and
the plugins the tests start too."""

import importlib.util
import os
import sys

REPOSITORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISPATCHER = os.path.join(os.path.dirname(REPOSITORY), 'hsm-dispatcher-py')
# the dispatcher function the generated programs depend on
DISPATCHER_API = 'read_documents'

PATHS = [REPOSITORY]
if importlib.util.find_spec('hsmd') is None and os.path.isdir(DISPATCHER):
    PATHS.append(DISPATCHER)
sys.path[:0] = PATHS
os.environ['PYTHONPATH'] = os.pathsep.join(
    PATHS + [p for p in os.environ.get('PYTHONPATH', '').split(os.pathsep) if p])

try:
    import hsmd  # pylint: disable=wrong-import-position
except ImportError as error:
    sys.exit('no dispatcher: install hsm-dispatcher-py or put it beside this '
             'repository ({})'.format(error))
if not hasattr(hsmd, DISPATCHER_API):
    sys.exit('the dispatcher {} is older than this generator needs (no {}): install '
             'the current hsm-dispatcher-py'.format(hsmd.__file__, DISPATCHER_API))
