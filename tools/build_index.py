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

Index additions (SPEC §10): `sequence` rises by one whenever any entry changes (rollback
protection for the signed index), `featured` comes from catalogue.json, `faces` says whether a
pack has face content, and `localized` copies the manifest's translations. catalogue.json also
holds `baseURL`, the host the archives are served from (the repository's raw URL until the
gallery moves to its own domain). index.json.sig is written by tools/sign_index.py in CI.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, ROOT)
from lenspack import packing  # noqa: E402
from lenspack import validator  # noqa: E402

PACKS = os.path.join(ROOT, "packs")
DIST = os.path.join(ROOT, "dist")
INDEX = os.path.join(ROOT, "index.json")
CATALOGUE = os.path.join(ROOT, "catalogue.json")
FACE_FIELDS = ("overlays", "triggers", "facePaint", "meshTexture", "retouch", "background")


def catalogue():
    with open(CATALOGUE, encoding="utf-8") as f:
        return json.load(f)


def quote(path):
    from urllib.parse import quote as q
    return catalogue()["baseURL"] + q(path)


def deterministic_zip(folder):
    """Zip `folder` reproducibly (lenspack.packing). Refuses symlinks and unsafe paths."""
    try:
        return packing.deterministic_zip(folder)
    except ValueError as e:
        raise SystemExit(str(e))


def build():
    """Returns {dist file name: bytes} and the index dict."""
    outputs = {}
    entries = []

    existing = json.load(open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {"packs": []}
    featured = set(catalogue().get("featured", []))
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
            if manifest["id"].startswith("@local/"):
                raise SystemExit(f"{name}: @local packs are made on a device and are never published")
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
            if manifest["id"] in featured:
                entry["featured"] = True
            if any(k in manifest for k in FACE_FIELDS):
                entry["faces"] = True
            if manifest.get("localized"):
                entry["localized"] = manifest["localized"]
            entries.append(entry)

    unknown = featured - {e.get("id") for e in entries}
    if unknown:
        raise SystemExit(f"catalogue.json features packs that are not in packs/: {sorted(unknown)}")
    # The sequence rises exactly when the listing changes, so a rebuild of an unchanged gallery
    # is byte-identical and `--check` stays meaningful.
    previous = existing.get("sequence", 0)
    unchanged = existing.get("packs") == entries
    index = {"version": 2, "sequence": previous if unchanged and previous else previous + 1, "packs": entries}
    # Revocations are honoured only in an index signed by the rotation key (SPEC §10.1).
    revoke = catalogue().get("revokeKeyIds", [])
    if revoke:
        index["revokeKeyIds"] = revoke
        if existing.get("revokeKeyIds") != revoke and unchanged and previous:
            index["sequence"] = previous + 1
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
