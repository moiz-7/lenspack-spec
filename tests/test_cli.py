#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
import glob
import json
import os
import sys
import zipfile

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)
from lenspack import cli, packing, validator  # noqa: E402

CASES = os.path.join(ROOT, "conformance", "cases")


def test_validate_exit_codes(capsys):
    assert cli.main(["validate", os.path.join(CASES, "valid/v4-full.lenspack")]) == 0
    assert cli.main(["validate", os.path.join(CASES, "invalid/empty.lenspack")]) == 1
    assert cli.main(["validate", os.path.join(CASES, "invalid/needs-newer-feature.lenspack")]) == 2
    # The worst over several: invalid outranks needs-newer.
    assert cli.main(["validate", os.path.join(CASES, "invalid/needs-newer-feature.lenspack"),
                     os.path.join(CASES, "invalid/empty.lenspack")]) == 1


def test_pack_is_reproducible_and_valid(tmp_path, capsys):
    folder = os.path.join(CASES, "valid/v4-rev2-variants.lenspack")
    a, b = tmp_path / "a.lenspack", tmp_path / "b.lenspack"
    assert cli.main(["pack", folder, str(a)]) == 0
    assert cli.main(["pack", folder, str(b)]) == 0
    assert a.read_bytes() == b.read_bytes() == packing.deterministic_zip(folder)
    assert validator.validate(str(a)).result == "valid"
    with zipfile.ZipFile(a) as zf:
        assert [i.date_time for i in zf.infolist()] == [packing.FIXED_TIME] * len(zf.infolist())


def test_pack_refuses_an_invalid_folder(tmp_path):
    assert cli.main(["pack", os.path.join(CASES, "invalid/empty.lenspack"), str(tmp_path / "x")]) == 1


def test_hash(tmp_path, capsys):
    f = tmp_path / "x"
    f.write_bytes(b"abc")
    cli.main(["hash", str(f)])
    out = json.loads(capsys.readouterr().out)
    assert out == {"sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "size": 3}


def test_verify_index_without_keys_is_honest(capsys):
    assert cli.main(["verify-index", os.path.join(ROOT, "index.json"),
                     "--keys", os.path.join(ROOT, "index-keys.json")]) == 0
    assert "UNVERIFIED" in capsys.readouterr().out
    assert cli.main(["verify-index", os.path.join(ROOT, "index.json"),
                     "--keys", os.path.join(ROOT, "index-keys.json"), "--strict"]) == 1


jsonschema = pytest.importorskip("jsonschema")


def test_every_valid_v4_case_matches_the_schema():
    schema = json.load(open(os.path.join(ROOT, "schema", "lenspack-4.schema.json"), encoding="utf-8"))
    for manifest in glob.glob(os.path.join(CASES, "valid", "v4-*", "manifest.json")):
        jsonschema.validate(json.load(open(manifest, encoding="utf-8")), schema)
    for manifest in glob.glob(os.path.join(ROOT, "packs", "*", "manifest.json")):
        jsonschema.validate(json.load(open(manifest, encoding="utf-8")), schema)


def test_index_matches_its_schema():
    schema = json.load(open(os.path.join(ROOT, "schema", "index-2.schema.json"), encoding="utf-8"))
    jsonschema.validate(json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8")), schema)
