#!/usr/bin/env python3
"""LensPack validator — checks a bare .cube file or a .lenspack folder against SPEC.md.

Usage:
    python3 validate_lenspack.py <path/to/Look.cube | path/to/Pack.lenspack>

Exit code 0 = valid; 1 = invalid (problems printed). Mirrors the app's loader rules exactly:
what passes here loads in Lens; what fails here is silently skipped by the app.
"""
import hashlib
import json
import os
import sys

MAX_CUBE_BYTES = 8 * 1024 * 1024
CUBE_SIZES = range(2, 66)
MAX_OVERLAY_PIXELS = 4_000_000
ANCHORS = {"forehead", "eyes", "nose", "mouth", "chin"}
BLENDSHAPES = {"mouthOpen", "smile", "browsUp", "blink"}
REQUIREMENTS = {"depth", "faceTracking"}
EFFECTS = {"bloom", "halation", "grain", "vignette", "saturation", "contrast", "temperature", "fade", "sharpen"}

problems = []
warnings = []


def check_cube(path):
    if not os.path.isfile(path):
        problems.append(f"cube file missing: {path}")
        return
    if os.path.getsize(path) > MAX_CUBE_BYTES:
        problems.append(f"cube exceeds 8 MB: {path}")
        return
    size, rows = 0, 0
    with open(path, encoding="utf-8", errors="strict") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("#", "TITLE", "DOMAIN_MIN", "DOMAIN_MAX")):
                continue
            if line.startswith("LUT_1D_SIZE"):
                problems.append("1D LUTs are not supported")
                return
            if line.startswith("LUT_3D_SIZE"):
                try:
                    size = int(line.split()[1])
                except (IndexError, ValueError):
                    problems.append("malformed LUT_3D_SIZE line")
                    return
                if size not in CUBE_SIZES:
                    problems.append(f"LUT_3D_SIZE {size} outside 2…65")
                    return
                continue
            parts = line.split()
            if len(parts) != 3:
                problems.append(f"non-RGB data row: {line!r}")
                return
            try:
                [float(p) for p in parts]
            except ValueError:
                problems.append(f"non-numeric data row: {line!r}")
                return
            rows += 1
    if size == 0:
        problems.append("missing LUT_3D_SIZE")
    elif rows != size ** 3:
        problems.append(f"expected {size ** 3} rows for size {size}, found {rows}")
    else:
        print(f"  cube OK: {size}^3, sha256={sha256_of(path)}")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def png_pixels(path):
    """Width×height from the PNG IHDR — no imaging library needed."""
    with open(path, "rb") as f:
        header = f.read(26)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    w = int.from_bytes(header[16:20], "big")
    h = int.from_bytes(header[20:24], "big")
    return w * h


def check_pack(folder):
    manifest_path = os.path.join(folder, "manifest.json")
    if not os.path.isfile(manifest_path):
        problems.append("manifest.json missing")
        return
    try:
        m = json.load(open(manifest_path, encoding="utf-8"))
    except json.JSONDecodeError as e:
        problems.append(f"manifest.json is not valid JSON: {e}")
        return

    if not str(m.get("name", "")).strip():
        problems.append("manifest 'name' is required and must be non-empty")

    has_content = False
    if "lut" in m:
        has_content = True
        check_cube(os.path.join(folder, m["lut"]))

    for i, fx in enumerate(m.get("effects", [])):
        has_content = True
        t = fx.get("type")
        if t not in EFFECTS:
            warnings.append(f"effects[{i}] unknown type {t!r} — will be skipped by the app")
        inten = fx.get("intensity", 0.5)
        if not isinstance(inten, (int, float)) or not (0 <= inten <= 1):
            warnings.append(f"effects[{i}] intensity {inten!r} outside 0…1 — the app clamps it")

    for i, ov in enumerate(m.get("overlays", [])):
        has_content = True
        if ov.get("anchor") not in ANCHORS:
            warnings.append(f"overlays[{i}] unknown anchor {ov.get('anchor')!r} — will be skipped")
        img = ov.get("image")
        if not img:
            problems.append(f"overlays[{i}] 'image' is required")
            continue
        img_path = os.path.join(folder, img)
        if not os.path.isfile(img_path):
            problems.append(f"overlays[{i}] image missing: {img}")
        else:
            px = png_pixels(img_path)
            if px is None:
                problems.append(f"overlays[{i}] {img} is not a valid PNG")
            elif px > MAX_OVERLAY_PIXELS:
                problems.append(f"overlays[{i}] {img} exceeds 4 megapixels ({px}px)")
        frames = ov.get("frames", [])
        if len(frames) > 23:
            warnings.append(f"overlays[{i}] has {len(frames)} extra frames — the app caps at 24 total")
        for fr in frames:
            fr_path = os.path.join(folder, fr)
            if not os.path.isfile(fr_path):
                problems.append(f"overlays[{i}] frame missing: {fr}")
            else:
                fpx = png_pixels(fr_path)
                if fpx is None:
                    problems.append(f"overlays[{i}] frame {fr} is not a valid PNG")
                elif fpx > MAX_OVERLAY_PIXELS:
                    problems.append(f"overlays[{i}] frame {fr} exceeds 4 megapixels")
        fps = ov.get("fps", 8)
        if not isinstance(fps, (int, float)) or not (1 <= fps <= 30):
            warnings.append(f"overlays[{i}] fps {fps!r} outside 1…30 — the app clamps it")

    if "meshTexture" in m:
        has_content = True
        mt_path = os.path.join(folder, m["meshTexture"])
        if not os.path.isfile(mt_path):
            problems.append(f"meshTexture missing: {m['meshTexture']}")
        elif png_pixels(mt_path) is None:
            problems.append(f"meshTexture {m['meshTexture']} is not a valid PNG")

    for i, tr in enumerate(m.get("triggers", [])):
        has_content = True
        if tr.get("blendshape") not in BLENDSHAPES:
            warnings.append(f"triggers[{i}] unknown blendshape {tr.get('blendshape')!r} — will be skipped")
        ov = tr.get("overlay") or {}
        if not ov.get("image"):
            problems.append(f"triggers[{i}] overlay.image is required")
        elif not os.path.isfile(os.path.join(folder, ov["image"])):
            problems.append(f"triggers[{i}] overlay image missing: {ov['image']}")

    for req in m.get("requires", []):
        if req not in REQUIREMENTS:
            warnings.append(f"unknown requirement {req!r} — devices will label it 'Needs newer Lens'")

    if not has_content:
        problems.append("pack has no content: needs at least one of lut / effects / overlays / meshTexture / triggers")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    target = sys.argv[1]
    print(f"validating {target}")
    if target.endswith(".cube"):
        check_cube(target)
    elif target.endswith(".lenspack") and os.path.isdir(target):
        check_pack(target)
    else:
        problems.append("expected a .cube file or a .lenspack folder")

    for w in warnings:
        print(f"  warning: {w}")
    if problems:
        for p in problems:
            print(f"  PROBLEM: {p}")
        print("INVALID")
        sys.exit(1)
    print("VALID")


if __name__ == "__main__":
    main()
