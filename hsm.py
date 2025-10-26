#!/usr/bin/python3
# -----------------------------------------------------------------------------
#  HSM-to-Python conversion tool
#
#  The main function
#
#  Copyright (C) 2025 Alexey Fedoseev <aleksey@fedoseev.net>
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

import sys
import traceback

import gencode

def usage():
    print('usage: {} <diagram.graphml> [output.py]'.format(sys.argv[0]))
    sys.exit(1)

if __name__ == '__main__':

    if len(sys.argv) < 2 or len(sys.argv) > 3:
        usage()

    graph = sys.argv[1]

    if len(sys.argv) == 3:
        output = sys.argv[2]
    else:
        output = None

    graph = sys.argv[1]

    try:
        g = gencode.CodeGenerator(graph, generate_loop=True)
        g.generate_code(output)
    except gencode.ParserError as e:
        sys.stderr.write('Graph parsing error: {}\n'.format(e))
        sys.exit(1)
    except gencode.GeneratorError as e:
        sys.stderr.write('Code generating error: {}\n'.format(e))
        sys.exit(2)
    except gencode.ConvertorError as e:
        sys.stderr.write('Strange convertor error: {}\n'.format(e))
        sys.exit(3)
    except Exception as e:
        sys.stderr.write('Unexpected exception: {}\n'.format(e.__class__))
        sys.stderr.write('{}\n'.format(traceback.format_exc()))
        sys.exit(4)

    sys.exit(0)
