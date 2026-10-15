# -----------------------------------------------------------------------------
# The HSM-to-Python testing infrastructure
#
# The modules under test: the working copies before the installed packages
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

"""Imported first by every test: this repository, then the dispatcher beside
it, go before the installed packages, for the tests and for the programs and
the plugins they start."""

import os
import sys

REPOSITORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISPATCHER = os.path.join(os.path.dirname(REPOSITORY), 'hsm-dispatcher-py')

PATHS = [REPOSITORY] + ([DISPATCHER] if os.path.isdir(DISPATCHER) else [])
sys.path[:0] = PATHS
os.environ['PYTHONPATH'] = os.pathsep.join(
    PATHS + [p for p in os.environ.get('PYTHONPATH', '').split(os.pathsep) if p])
