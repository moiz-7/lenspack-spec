#!/usr/bin/env python3
#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""LensPack validator — checks a bare .cube file, a .lenspack folder or a .lenspack zip
against SPEC.md.

Usage:
    python3 validate_lenspack.py <Look.cube | Pack.lenspack/ | Pack.lenspack (zip)> [--json]

Exit code 0 = valid; 1 = invalid; 2 = valid but needs a newer reader (unknown `required`
feature or a `lenspack` version above 4). Every limit is read from conformance/limits.json,
the same file the app's parity test reads, so the two cannot drift silently.

Problems carry stable codes (`path.unsafe`, `budget.packPixels`, ...). The conformance
cases assert codes, never message wording.
"""
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIMITS_PATH = os.path.join(HERE, os.pardir, "conformance", "limits.json")


def load_limits(path=LIMITS_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Report:
    def __init__(self):
        self.problems = []     # (code, message)
        self.warnings = []     # (code, message)
        self.needs_newer = []  # (code, message)
        self.id = None
        self.version = None
        self.legacy = True

    def problem(self, code, msg):
        self.problems.append((code, msg))

    def warn(self, code, msg):
        self.warnings.append((code, msg))

    def newer(self, code, msg):
        self.needs_newer.append((code, msg))

    @property
    def result(self):
        if self.needs_newer:
            return "needs-newer"
        return "invalid" if self.problems else "valid"

    def codes(self):
        return sorted({c for c, _ in self.problems + self.needs_newer})

    def to_json(self):
        return {
            "result": self.result,
            "id": self.id,
            "version": self.version,
            "legacy": self.legacy,
            "problems": [{"code": c, "message": m} for c, m in self.problems],
            "needsNewer": [{"code": c, "message": m} for c, m in self.needs_newer],
            "warnings": [{"code": c, "message": m} for c, m in self.warnings],
        }


# ---------------------------------------------------------------------------------------
# Paths

def path_is_lexically_safe(rel, max_components):
    """The spec's path rule, without touching the file system."""
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel:
        return False
    if rel.startswith("/") or rel.startswith("~"):
        return False
    parts = rel.split("/")
    if len(parts) > max_components:
        return False
    return all(p not in ("", ".", "..") for p in parts)


def resolve(folder, rel, limits):
    """Join `rel` to `folder` under the path rule. None when unsafe (traversal, absolute,
    too deep, a symlink anywhere on the way, or a result outside the folder)."""
    if not path_is_lexically_safe(rel, limits["paths"]["maxComponents"]):
        return None
    root = os.path.realpath(folder)
    current = root
    for part in rel.split("/"):
        current = os.path.join(current, part)
        if os.path.islink(current):
            return None
    if not (os.path.realpath(current) + os.sep).startswith(root + os.sep):
        return None
    return current


# ---------------------------------------------------------------------------------------
# Assets

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def png_size(path):
    """(width, height) from the PNG IHDR — no imaging library needed. None if not a PNG."""
    with open(path, "rb") as f:
        header = f.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def check_cube(path, limits, report):
    """Structural cube check. Returns the LUT size, or None (with a problem recorded)."""
    lut = limits["lut"]
    if os.path.getsize(path) > lut["maxFileBytes"]:
        report.problem("lut.invalid", f"cube exceeds {lut['maxFileBytes']} bytes")
        return None
    size, rows = 0, 0
    try:
        text = open(path, encoding="utf-8", errors="strict").read()
    except UnicodeDecodeError:
        report.problem("lut.invalid", "cube is not UTF-8 text")
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "TITLE", "DOMAIN_MIN", "DOMAIN_MAX")):
            continue
        if line.startswith("LUT_1D_SIZE"):
            report.problem("lut.invalid", "1D LUTs are not supported")
            return None
        if line.startswith("LUT_3D_SIZE"):
            try:
                size = int(line.split()[1])
            except (IndexError, ValueError):
                report.problem("lut.invalid", "malformed LUT_3D_SIZE line")
                return None
            if not (lut["minSize"] <= size <= lut["maxSize"]):
                report.problem("lut.invalid", f"LUT_3D_SIZE {size} outside {lut['minSize']}…{lut['maxSize']}")
                return None
            continue
        parts = line.split()
        try:
            values = [float(p) for p in parts]
        except ValueError:
            report.problem("lut.invalid", f"non-numeric data row: {line!r}")
            return None
        if len(values) != 3 or any(v != v or v in (float("inf"), float("-inf")) for v in values):
            report.problem("lut.invalid", f"bad data row: {line!r}")
            return None
        rows += 1
    if size == 0:
        report.problem("lut.invalid", "missing LUT_3D_SIZE")
        return None
    if rows != size ** 3:
        report.problem("lut.invalid", f"expected {size ** 3} rows for size {size}, found {rows}")
        return None
    return size


# ---------------------------------------------------------------------------------------
# Manifest

def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def in_range(v, pair):
    return pair[0] <= v <= pair[1]


class PackChecker:
    def __init__(self, folder, limits, report):
        self.folder = folder
        self.limits = limits
        self.r = report
        self.pixels = 0

    # Legacy packs keep v1–v3 behaviour: a broken item is dropped with a warning and the
    # rest of the pack still loads. v4 packs report it as a problem. Path safety and the
    # pack-level budgets are problems in every version.
    def item_issue(self, code, msg):
        if self.r.legacy:
            self.r.warn(code, msg + " — dropped")
        else:
            self.r.problem(code, msg)

    def malformed(self, field, msg):
        self.item_issue("manifest.field", f"{field}: {msg}")

    def image(self, rel, what, animated):
        """Resolve + measure one overlay-class image. Returns pixels or None (issue noted)."""
        ov = self.limits["overlays"]
        path = resolve(self.folder, rel, self.limits)
        if path is None:
            self.r.problem("path.unsafe", f"{what}: unsafe path {rel!r}")
            return None
        if not os.path.isfile(path):
            self.item_issue("asset.missing", f"{what}: file missing {rel!r}")
            return None
        size = png_size(path)
        if size is None:
            self.item_issue("asset.notPNG", f"{what}: {rel!r} is not a PNG")
            return None
        px = size[0] * size[1]
        if px > ov["maxImagePixels"]:
            self.item_issue("budget.imagePixels", f"{what}: {rel!r} is {px} px (max {ov['maxImagePixels']})")
            return None
        if animated and px > ov["maxAnimatedFramePixels"]:
            self.item_issue("budget.framePixels",
                            f"{what}: animated frame {rel!r} is {px} px (max {ov['maxAnimatedFramePixels']})")
            return None
        return px

    def overlay(self, ov, where):
        """Checks one overlay object. Returns the pixels it adds, or None if dropped."""
        L = self.limits["overlays"]
        if not isinstance(ov, dict):
            self.malformed(where, "must be an object")
            return None
        if not isinstance(ov.get("image"), str) or not ov.get("image"):
            self.malformed(where, "'image' is required")
            return None
        anchor = ov.get("anchor")
        if anchor not in L["anchors"]:
            if isinstance(anchor, str):
                self.r.warn("overlay.unknownAnchor", f"{where}: unknown anchor {anchor!r} — skipped")
            else:
                self.malformed(where, "'anchor' is required")
            return None
        for key, rng in (("scale", "scale"), ("offsetX", "offset"), ("offsetY", "offset"),
                         ("fps", "fps"), ("opacity", "opacity"), ("z", "z")):
            if key in ov:
                v = ov[key]
                if not is_number(v) or (key == "z" and not isinstance(v, int)):
                    self.malformed(where, f"{key!r} must be a number")
                    return None
                if not in_range(v, L[rng]):
                    self.r.warn("value.clamped", f"{where}: {key} {v} outside {L[rng]} — clamped")
        if "blend" in ov and ov["blend"] not in L["blends"]:
            self.malformed(where, f"unknown blend {ov['blend']!r}")
            return None
        if "faces" in ov:
            f = ov["faces"]
            ok = (f in L["faces"]) or (isinstance(f, int) and not isinstance(f, bool)
                                       and 1 <= f <= L["maxFaceCount"])
            if not ok:
                self.malformed(where, f"'faces' must be one of {L['faces']} or 1…{L['maxFaceCount']}")
                return None
        frames = ov.get("frames", [])
        if not isinstance(frames, list) or not all(isinstance(x, str) for x in frames):
            self.malformed(where, "'frames' must be a list of file names")
            return None
        names = [ov["image"]] + frames
        if len(names) > L["maxFrames"]:
            if self.r.legacy:
                self.r.warn("budget.frames", f"{where}: {len(names)} frames, only the first {L['maxFrames']} load")
                names = names[:L["maxFrames"]]
            else:
                self.r.problem("budget.frames", f"{where}: {len(names)} frames (max {L['maxFrames']})")
                return None
        animated = len(names) > 1
        total, kept = 0, 0
        for name in names:
            px = self.image(name, where, animated)
            if px is not None:
                total += px
                kept += 1
        return total if kept else None

    def run(self):
        L = self.limits
        manifest_path = resolve(self.folder, "manifest.json", L)
        if manifest_path is None or not os.path.isfile(manifest_path):
            self.r.problem("manifest.missing", "manifest.json missing")
            return
        raw = open(manifest_path, "rb").read()
        try:
            m = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self.r.problem("manifest.json", f"manifest.json is not valid JSON: {e}")
            return
        if not isinstance(m, dict):
            self.r.problem("manifest.json", "manifest.json must be an object")
            return

        # ---- format version and required features, decided first: a newer pack may
        # legitimately use fields this reader would call malformed.
        if "lenspack" in m:
            v = m["lenspack"]
            if not isinstance(v, int) or isinstance(v, bool) or v < 4:
                self.r.problem("manifest.lenspack", f"'lenspack' must be an integer ≥ 4, got {v!r}")
                return
            self.r.legacy = False
            if v > L["lenspack"]:
                self.r.newer("format.newer", f"lenspack {v} is newer than {L['lenspack']}")
                return
        required = m.get("required", [])
        if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
            self.r.problem("manifest.field", "'required' must be a list of strings")
            return
        unknown = [f for f in required if f not in L["features"]]
        if unknown:
            self.r.newer("required.unknown", f"needs features this reader lacks: {unknown}")
            return

        # ---- identity
        if not isinstance(m.get("name"), str) or not m["name"].strip():
            self.r.problem("manifest.name", "'name' is required and must be non-empty")
        if self.r.legacy:
            self.r.id = L["id"]["legacyPrefix"] + sha256_bytes(raw)[:L["id"]["legacyDigestHexChars"]]
            ver = m.get("version")
            self.r.version = ver if isinstance(ver, str) else None
        else:
            pid = m.get("id")
            if not isinstance(pid, str) or not re.match(L["id"]["pattern"], pid):
                self.r.problem("manifest.id", f"'id' must look like @author/slug, got {pid!r}")
            else:
                self.r.id = pid
            ver = m.get("version")
            if not isinstance(ver, str) or not re.match(L["version"]["pattern"], ver):
                self.r.problem("manifest.version", f"'version' must be semver, got {ver!r}")
            else:
                self.r.version = ver
            lic = m.get("license")
            if lic is not None and (not isinstance(lic, str) or len(lic) > L["license"]["maxLength"]
                                    or not re.match(L["license"]["pattern"], lic)):
                self.r.problem("manifest.license", f"'license' must be an SPDX expression, got {lic!r}")
            if "attribution" in m and not isinstance(m["attribution"], str):
                self.r.problem("manifest.field", "'attribution' must be a string")
            loc = m.get("localized", {})
            if not isinstance(loc, dict):
                self.r.problem("manifest.localized", "'localized' must be an object")
            else:
                for tag, entry in loc.items():
                    if not re.match(L["localized"]["pattern"], tag) or not isinstance(entry, dict) \
                            or not all(k in L["localized"]["fields"] and isinstance(v, str)
                                       for k, v in entry.items()):
                        self.r.problem("manifest.localized", f"localized[{tag!r}] is malformed")
            if "thumbnail" in m:
                self.thumbnail(m["thumbnail"])
        if "author" in m and not isinstance(m["author"], str):
            self.malformed("author", "must be a string")

        has_content = False

        # ---- lut
        if "lut" in m:
            lut = m["lut"]
            spec = None
            if isinstance(lut, str):
                spec = {"file": lut, "input": L["lut"]["defaultInput"]}
            elif isinstance(lut, dict) and isinstance(lut.get("file"), str):
                spec = lut
            else:
                self.malformed("lut", "must be a file name or {file, input, output}")
            if spec is not None:
                inp = spec.get("input", L["lut"]["defaultInput"])
                out = spec.get("output")
                if inp not in L["lut"]["inputs"] or (out is not None and out not in L["lut"]["outputs"]):
                    self.r.problem("lut.space", f"unknown lut input/output {inp!r}/{out!r}")
                path = resolve(self.folder, spec["file"], L)
                if path is None:
                    self.r.problem("path.unsafe", f"lut: unsafe path {spec['file']!r}")
                elif not os.path.isfile(path):
                    self.item_issue("asset.missing", f"lut: file missing {spec['file']!r}")
                elif check_cube(path, L, self.r) is not None:
                    has_content = True

        # ---- effects
        effects = m.get("effects", [])
        if not isinstance(effects, list):
            self.malformed("effects", "must be a list")
            effects = []
        if len(effects) > L["effects"]["max"]:
            self.r.problem("budget.effects", f"{len(effects)} effects (max {L['effects']['max']})")
        for i, fx in enumerate(effects):
            where = f"effects[{i}]"
            if not isinstance(fx, dict):
                self.malformed(where, "must be an object")
                continue
            t = fx.get("type")
            if t not in L["effects"]["types"]:
                if isinstance(t, str):
                    self.r.warn("effect.unknownType", f"{where}: unknown type {t!r} — skipped")
                else:
                    self.malformed(where, "'type' is required")
                continue
            inten = fx.get("intensity", 0.5)
            if not is_number(inten):
                self.malformed(where, "'intensity' must be a number")
                continue
            if not (0 <= inten <= 1):
                self.r.warn("value.clamped", f"{where}: intensity {inten} outside 0…1 — clamped")
            params = fx.get("params", {})
            if not isinstance(params, dict) or not all(is_number(v) for v in params.values()):
                self.malformed(where, "'params' must map names to numbers")
                continue
            known = L["effects"]["params"].get(t, {})
            bad = False
            for k, v in params.items():
                if k not in known:
                    self.r.warn("effect.unknownParam", f"{where}: unknown param {k!r} — ignored")
                elif not in_range(v, known[k]):
                    self.item_issue("effect.param", f"{where}: {k} {v} outside {known[k]}")
                    bad = True
            if not bad:
                has_content = True

        # ---- overlays
        overlays = m.get("overlays", [])
        if not isinstance(overlays, list):
            self.malformed("overlays", "must be a list")
            overlays = []
        if len(overlays) > L["overlays"]["max"]:
            self.r.problem("budget.overlays", f"{len(overlays)} overlays (max {L['overlays']['max']})")
        for i, ov in enumerate(overlays):
            px = self.overlay(ov, f"overlays[{i}]")
            if px is not None:
                self.pixels += px
                has_content = True

        # ---- triggers
        triggers = m.get("triggers", [])
        if not isinstance(triggers, list):
            self.malformed("triggers", "must be a list")
            triggers = []
        if len(triggers) > L["triggers"]["max"]:
            self.r.problem("budget.triggers", f"{len(triggers)} triggers (max {L['triggers']['max']})")
        for i, tr in enumerate(triggers):
            where = f"triggers[{i}]"
            if not isinstance(tr, dict):
                self.malformed(where, "must be an object")
                continue
            shape = tr.get("blendshape")
            if shape not in L["triggers"]["blendshapes"]:
                if isinstance(shape, str):
                    self.r.warn("trigger.unknownBlendshape", f"{where}: unknown blendshape {shape!r} — skipped")
                else:
                    self.malformed(where, "'blendshape' is required")
                continue
            if "threshold" in tr and not is_number(tr["threshold"]):
                self.malformed(where, "'threshold' must be a number")
                continue
            px = self.overlay(tr.get("overlay"), f"{where}.overlay")
            if px is not None:
                self.pixels += px
                has_content = True

        # ---- mesh texture
        if "meshTexture" in m:
            mt = m["meshTexture"]
            if not isinstance(mt, str):
                self.malformed("meshTexture", "must be a file name")
            else:
                px = self.image(mt, "meshTexture", animated=False)
                if px is not None:
                    self.pixels += px
                    has_content = True

        # ---- data overlays (v3.1)
        data = m.get("data", [])
        if not isinstance(data, list):
            self.malformed("data", "must be a list")
            data = []
        if len(data) > L["data"]["max"]:
            self.r.problem("budget.data", f"{len(data)} data overlays (max {L['data']['max']})")
        for i, d in enumerate(data):
            where = f"data[{i}]"
            if not isinstance(d, dict):
                self.malformed(where, "must be an object")
                continue
            if d.get("type") not in L["data"]["types"]:
                if isinstance(d.get("type"), str):
                    self.r.warn("data.unknownType", f"{where}: unknown type {d.get('type')!r} — skipped")
                else:
                    self.malformed(where, "'type' is required")
                continue
            if "position" in d and d["position"] not in L["data"]["positions"]:
                self.malformed(where, f"unknown position {d['position']!r}")
                continue
            has_content = True

        # ---- requires (labels only)
        requires = m.get("requires", [])
        if not isinstance(requires, list):
            self.malformed("requires", "must be a list")
            requires = []
        for req in requires:
            if req not in L["requires"]:
                self.r.warn("requires.unknown", f"unknown requirement {req!r} — labelled 'Needs newer Lens'")

        # ---- whole-pack budget
        if self.pixels > L["pack"]["maxOverlayPixels"]:
            self.r.problem("budget.packPixels",
                           f"pack decodes to {self.pixels} overlay pixels (max {L['pack']['maxOverlayPixels']})")

        if not has_content:
            self.r.problem("content.empty", "pack has no usable content")

    def thumbnail(self, rel):
        if not isinstance(rel, str):
            self.r.problem("manifest.field", "'thumbnail' must be a file name")
            return
        path = resolve(self.folder, rel, self.limits)
        if path is None:
            self.r.problem("path.unsafe", f"thumbnail: unsafe path {rel!r}")
            return
        if not os.path.isfile(path):
            self.r.problem("asset.missing", f"thumbnail missing: {rel!r}")
            return
        size = png_size(path)
        if size is None:
            self.r.problem("asset.notPNG", f"thumbnail {rel!r} is not a PNG")
        elif max(size) > self.limits["thumbnail"]["maxEdge"]:
            self.r.problem("thumbnail.size",
                           f"thumbnail is {size[0]}x{size[1]} (max edge {self.limits['thumbnail']['maxEdge']})")


# ---------------------------------------------------------------------------------------
# Zip

def check_zip_entries(zf, limits, report):
    """The safe-unzip rules, applied to the central directory before anything is written."""
    A = limits["archive"]
    infos = zf.infolist()
    if len(infos) > A["maxEntries"]:
        report.problem("archive.entries", f"{len(infos)} entries (max {A['maxEntries']})")
        return False
    seen, total = set(), 0
    for info in infos:
        name = info.filename
        if info.flag_bits & 0x1:
            report.problem("archive.encrypted", f"encrypted entry {name!r}")
            return False
        mode = (info.external_attr >> 16) & 0xFFFF
        if info.create_system == 3 and stat.S_ISLNK(mode):
            report.problem("archive.symlink", f"symlink entry {name!r}")
            return False
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            report.problem("archive.method", f"unsupported compression for {name!r}")
            return False
        check_name = name[:-1] if name.endswith("/") else name
        if not path_is_lexically_safe(check_name, limits["paths"]["maxComponents"]):
            report.problem("path.unsafe", f"unsafe entry name {name!r}")
            return False
        key = name.lower()
        if key in seen:
            report.problem("archive.duplicate", f"duplicate entry {name!r}")
            return False
        seen.add(key)
        if info.file_size > A["maxEntryBytes"]:
            report.problem("archive.entrySize", f"{name!r} is {info.file_size} bytes")
            return False
        if info.file_size > max(info.compress_size, 1) * A["maxCompressionRatio"]:
            report.problem("archive.ratio", f"{name!r} compresses more than {A['maxCompressionRatio']}:1")
            return False
        total += info.file_size
    if total > A["maxUncompressedBytes"]:
        report.problem("archive.totalSize", f"{total} bytes uncompressed")
        return False
    return True


def validate_zip(path, limits):
    report = Report()
    if os.path.getsize(path) > limits["archive"]["maxArchiveBytes"]:
        report.problem("archive.size", "archive exceeds the size cap")
        return report
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        report.problem("archive.corrupt", "not a zip archive")
        return report
    with zf:
        if not check_zip_entries(zf, limits, report):
            return report
        tmp = tempfile.mkdtemp(prefix="lenspack-")
        try:
            for info in zf.infolist():
                if info.filename.endswith("/"):
                    continue
                dest = os.path.join(tmp, *info.filename.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                data = zf.read(info)  # zipfile verifies the CRC
                if len(data) != info.file_size:
                    report.problem("archive.corrupt", f"{info.filename!r} size mismatch")
                    return report
                with open(dest, "wb") as f:
                    f.write(data)
            return validate_folder(tmp, limits)
        except (zipfile.BadZipFile, OSError) as e:
            report.problem("archive.corrupt", str(e))
            return report
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def validate_folder(folder, limits):
    report = Report()
    PackChecker(folder, limits, report).run()
    return report


def validate_cube(path, limits):
    report = Report()
    with open(path, "rb") as f:
        report.id = limits["id"]["legacyPrefix"] + sha256_bytes(f.read())[:limits["id"]["legacyDigestHexChars"]]
    check_cube(path, limits, report)
    return report


def validate(path, limits=None):
    limits = limits or load_limits()
    if os.path.isdir(path):
        return validate_folder(path, limits)
    if path.lower().endswith(".cube"):
        return validate_cube(path, limits)
    if os.path.isfile(path) and zipfile.is_zipfile(path):
        return validate_zip(path, limits)
    report = Report()
    report.problem("input.unknown", "expected a .cube file, a .lenspack folder or a .lenspack zip")
    return report


def main(argv):
    args = [a for a in argv[1:] if a != "--json"]
    if len(args) != 1:
        print(__doc__)
        return 1
    report = validate(args[0])
    if "--json" in argv:
        print(json.dumps(report.to_json(), indent=2))
    else:
        print(f"validating {args[0]}")
        if report.id:
            print(f"  id: {report.id}" + (f"  version: {report.version}" if report.version else ""))
        for code, msg in report.warnings:
            print(f"  warning [{code}]: {msg}")
        for code, msg in report.needs_newer:
            print(f"  NEEDS NEWER [{code}]: {msg}")
        for code, msg in report.problems:
            print(f"  PROBLEM [{code}]: {msg}")
        print(report.result.upper())
    return {"valid": 0, "invalid": 1, "needs-newer": 2}[report.result]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
