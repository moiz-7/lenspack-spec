#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Everything is in pyproject.toml. This file only copies conformance/limits.json — the one
source of every limit — into the built package, so an installed validator reads the same
numbers as the repository's, and the repository never holds a second copy."""
import os
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py

HERE = os.path.dirname(os.path.abspath(__file__))


class BuildWithLimits(build_py):
    def run(self):
        super().run()
        target = os.path.join(self.build_lib, "lenspack", "limits.json")
        shutil.copyfile(os.path.join(HERE, "conformance", "limits.json"), target)


setup(cmdclass={"build_py": BuildWithLimits})
