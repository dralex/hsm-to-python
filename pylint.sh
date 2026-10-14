#!/bin/bash

FILES="hsm.py gencode.py hsmcheck.py hsmplugin.py test/python_hsm_test.py test/run.py test/arguments_test.py test/plugin_test.py"
pylint --disable=I1101,C0301,W0703 $FILES
