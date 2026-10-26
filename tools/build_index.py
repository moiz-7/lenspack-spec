#!/usr/bin/env python3
#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Builds the gallery: one reproducible .lenspack zip per pack folder, then index.json.

    python3 tools/build_index.py           # rebuild dist/ and index.json
    python3 tools/build_index.py --check   # CI: fail if either is stale

Sources:
  * packs/<author>.<slug>.lenspack/  — v4 pack folders (manifest needs id, version, license).
  * examples/*.cube                  — bare cube looks already listed in index.json. Their
                                       entries are kept and get the version-2 fields added.

The zip is deterministic: entries sorted by path, a fixed 1980-01-01 timestamp, Unix mode
0644, deflate level 9, no extra fields. The same folder always produces the same bytes, so
its sha256 is stable across machines and the index only changes when a pack does.

Every entry keeps the version-1 fields (name, author, summary, fileName, url, sha256), so app
builds that read index version 1 keep working: they install .cube entries and skip the rest.
"""
import hashlib
import io
import json
import os
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, os.path.join(ROOT, "validator"))
import validate_lenspack as validator  # noqa: E402

RAW_BASE = "https://raw.githubusercontent.com/moiz-7/lenspack-spec/main/"
PACKS = os.path.join(ROOT, "packs")
DIST = os.path.join(ROOT, "dist")
INDEX = os.path.join(ROOT, "index.json")
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def quote(path):
    from urllib.parse import quote as q
    return RAW_BASE + q(path)


def deterministic_zip(folder):
    """Zip `folder` reproducibly. Refuses symlinks and anything the path rule refuses."""
    limits = validator.load_limits()
    files = []
    for base, dirs, names in os.walk(folder):
        dirs.sort()
        for name in names:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, folder).replace(os.sep, "/")
            if name.startswith("."):
                continue
            if os.path.islink(full) or not validator.path_is_lexically_safe(rel, limits["paths"]["maxComponents"]):
                raise SystemExit(f"refusing to pack {rel!r}")
            files.append(rel)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for rel in sorted(files):
            info = zipfile.ZipInfo(rel, date_time=FIXED_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(folder, *rel.split("/")), "rb") as f:
                zf.writestr(info, f.read(), compresslevel=9)
    return buf.getvalue()


def build():
    """Returns {dist file name: bytes} and the index dict."""
    outputs = {}
    entries = []

    existing = json.load(open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {"packs": []}
    for entry in existing["packs"]:
        if entry.get("kind", "cube") != "cube":
            continue
        path = os.path.join(ROOT, "examples", entry["fileName"])
        data = open(path, "rb").read()
        report = validator.validate(path)
        if report.result != "valid":
            raise SystemExit(f"{entry['fileName']}: {report.to_json()}")
        entry = dict(entry)
        entry.update({
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "kind": "cube",
            "lenspack": 1,
            "id": report.id,
        })
        entry.setdefault("license", "CC-BY-4.0")
        entries.append(entry)

    if os.path.isdir(PACKS):
        for name in sorted(os.listdir(PACKS)):
            folder = os.path.join(PACKS, name)
            if not name.endswith(".lenspack") or not os.path.isdir(folder):
                continue
            report = validator.validate(folder)
            if report.result != "valid" or report.legacy:
                raise SystemExit(f"{name}: gallery packs must be valid v4 packs: {report.to_json()}")
            manifest = json.load(open(os.path.join(folder, "manifest.json"), encoding="utf-8"))
            if "license" not in manifest:
                raise SystemExit(f"{name}: gallery packs need a 'license'")
            expected = manifest["id"][1:].replace("/", ".") + ".lenspack"
            if name != expected:
                raise SystemExit(f"{name}: folder must be named {expected}")
            data = deterministic_zip(folder)
            if len(data) > validator.load_limits()["archive"]["maxArchiveBytes"]:
                raise SystemExit(f"{name}: archive over the size cap")
            outputs[name] = data
            entry = {
                "name": manifest["name"],
                "author": manifest.get("author", manifest["id"].split("/")[0]),
                "summary": manifest.get("summary", ""),
                "fileName": name,
                "url": quote(f"dist/{name}"),
                "sha256": hashlib.sha256(data).hexdigest(),
                "id": manifest["id"],
                "version": manifest["version"],
                "size": len(data),
                "license": manifest["license"],
                "kind": "pack",
                "lenspack": manifest["lenspack"],
            }
            if "requires" in manifest:
                entry["requires"] = manifest["requires"]
            if "thumbnail" in manifest:
                entry["thumbnail"] = quote(f"packs/{name}/{manifest['thumbnail']}")
            entries.append(entry)

    index = {"version": 2, "packs": entries}
    return outputs, index


def render_index(index):
    return json.dumps(index, indent=2, ensure_ascii=True) + "\n"


def main(argv):
    outputs, index = build()
    text = render_index(index)
    if len(text.encode()) > validator.load_limits()["index"]["maxIndexBytes"]:
        raise SystemExit("index.json over the 256 KB cap")
    if "--check" in argv:
        stale = []
        if not os.path.exists(INDEX) or open(INDEX, encoding="utf-8").read() != text:
            stale.append("index.json")
        for name, data in outputs.items():
            path = os.path.join(DIST, name)
            if not os.path.exists(path) or open(path, "rb").read() != data:
                stale.append(f"dist/{name}")
        if stale:
            print("stale: " + ", ".join(stale) + " — run python3 tools/build_index.py")
            return 1
        print("index and dist are up to date")
        return 0
    os.makedirs(DIST, exist_ok=True)
    for name, data in outputs.items():
        with open(os.path.join(DIST, name), "wb") as f:
            f.write(data)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote index.json ({len(index['packs'])} entries) and {len(outputs)} archive(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
