#!/bin/bash

FILES="hsm.py gencode.py test/python_hsm_test.py test/run.py"
pylint --disable=I1101,C0301,W0703 $FILES
