#!/bin/bash

FILES="hsm.py gencode.py"
pylint --disable=I1101,C0301,W0703 $FILES


