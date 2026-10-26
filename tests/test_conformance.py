#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Runs every conformance case through the reference validator, plus the cases that can't
be stored in git (symlinks) and the zip rules."""
import io
import json
import os
import stat
import sys
import zipfile

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, os.path.join(ROOT, "validator"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import validate_lenspack as v  # noqa: E402

CASES = os.path.join(ROOT, "conformance", "cases")
EXPECT = json.load(open(os.path.join(CASES, "expect.json"), encoding="utf-8"))


@pytest.mark.parametrize("case", sorted(EXPECT))
def test_case(case):
    report = v.validate(os.path.join(CASES, case))
    want = EXPECT[case]
    assert report.result == want["result"], report.to_json()
    for code in want["codes"]:
        assert code in report.codes(), report.to_json()


def test_every_case_folder_has_an_expectation():
    on_disk = {f"{group}/{name}" for group in ("valid", "invalid")
               for name in os.listdir(os.path.join(CASES, group))}
    assert on_disk == set(EXPECT)


def test_symlinked_asset_is_unsafe(tmp_path):
    outside = tmp_path / "secret.cube"
    outside.write_bytes(open(os.path.join(CASES, "valid/legacy-v1-lut.lenspack/look.cube"), "rb").read())
    pack = tmp_path / "Link.lenspack"
    pack.mkdir()
    (pack / "manifest.json").write_text(json.dumps({"name": "Link", "lut": "look.cube"}))
    os.symlink(outside, pack / "look.cube")
    report = v.validate(str(pack))
    assert report.result == "invalid" and "path.unsafe" in report.codes()


def zip_of(folder, extra=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, _, files in os.walk(folder):
            for name in sorted(files):
                full = os.path.join(base, name)
                zf.write(full, os.path.relpath(full, folder).replace(os.sep, "/"))
        for info, data in (extra or []):
            zf.writestr(info, data)
    return buf.getvalue()


def test_zip_of_valid_case_is_valid(tmp_path):
    path = tmp_path / "p.lenspack"
    path.write_bytes(zip_of(os.path.join(CASES, "valid/v4-full.lenspack")))
    assert v.validate(str(path)).result == "valid"


@pytest.mark.parametrize("name,code", [("../evil.png", "path.unsafe"), ("/abs.png", "path.unsafe")])
def test_zip_slip(tmp_path, name, code):
    path = tmp_path / "p.lenspack"
    path.write_bytes(zip_of(os.path.join(CASES, "valid/v4-string-lut.lenspack"), [(name, b"x")]))
    assert code in v.validate(str(path)).codes()


def test_zip_symlink_entry(tmp_path):
    info = zipfile.ZipInfo("link.png")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    path = tmp_path / "p.lenspack"
    path.write_bytes(zip_of(os.path.join(CASES, "valid/v4-string-lut.lenspack"), [(info, b"/etc/hosts")]))
    assert "archive.symlink" in v.validate(str(path)).codes()


def test_zip_bomb_ratio(tmp_path):
    info = zipfile.ZipInfo("bomb.png")
    info.compress_type = zipfile.ZIP_DEFLATED
    path = tmp_path / "p.lenspack"
    path.write_bytes(zip_of(os.path.join(CASES, "valid/v4-string-lut.lenspack"), [(info, bytes(4_000_000))]))
    assert "archive.ratio" in v.validate(str(path)).codes()


def test_zip_duplicate_names(tmp_path):
    path = tmp_path / "p.lenspack"
    with pytest.warns(UserWarning):
        data = zip_of(os.path.join(CASES, "valid/v4-string-lut.lenspack"), [("look.cube", b"x")])
    path.write_bytes(data)
    assert "archive.duplicate" in v.validate(str(path)).codes()


def test_zip_too_many_entries(tmp_path):
    extra = [(f"f{i}.txt", b"x") for i in range(64)]
    path = tmp_path / "p.lenspack"
    path.write_bytes(zip_of(os.path.join(CASES, "valid/v4-string-lut.lenspack"), extra))
    assert "archive.entries" in v.validate(str(path)).codes()


def test_examples_still_validate():
    assert v.validate(os.path.join(ROOT, "examples", "party-crown.lenspack")).result == "valid"
    assert v.validate(os.path.join(ROOT, "examples", "Sunset Fade.cube")).result == "valid"
