#!/usr/bin/env python
"""Simple test runner for parameter parsing tests."""

import sys
import subprocess

if __name__ == '__main__':
    # Run pytest on the parameter parsing tests
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/test_parameter_parsing.py', '-v', '-s'],
        cwd='/home/sverzijl/planning_latest'
    )
    sys.exit(result.returncode)
