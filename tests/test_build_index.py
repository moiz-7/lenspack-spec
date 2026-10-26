#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_index  # noqa: E402

V1_FIELDS = {"name", "author", "summary", "fileName", "url", "sha256"}


def test_zip_is_deterministic():
    folder = os.path.join(ROOT, "packs", "lenspack-spec.party-crown.lenspack")
    assert build_index.deterministic_zip(folder) == build_index.deterministic_zip(folder)


def test_index_is_current_and_v1_compatible():
    assert build_index.main(["build_index.py", "--check"]) == 0
    index = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
    for entry in index["packs"]:
        assert V1_FIELDS <= set(entry), entry
        assert "/" not in entry["fileName"]
        # Version-1 app builds install exactly the .cube entries.
        assert entry["fileName"].endswith(".cube") == (entry["kind"] == "cube")
