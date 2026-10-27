#!/usr/bin/env python3
#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""The reference validator, run from a checkout without installing anything:

    python3 validator/validate_lenspack.py <Look.cube | Pack.lenspack/ | Pack.lenspack (zip)> [--json]

The code lives in the `lenspack` package (`lenspack/validator.py`), which `pip install lenspack`
installs as the `lenspack` command. This file keeps the documented path working.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from lenspack.validator import *  # noqa: E402,F401,F403
from lenspack.validator import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv))
