#!/bin/bash

FILES="hsm.py gencode.py hsmcheck.py hsmplugin.py test/python_hsm_test.py test/run.py test/testenv.py test/arguments_test.py test/standalone_test.py test/model_test.py test/plugin_test.py test/session_test.py"
pylint --disable=I1101,C0301,W0703 $FILES
