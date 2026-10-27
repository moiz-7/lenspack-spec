#!/usr/bin/env python3
#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Regenerates conformance/goldens/ from lenspack/reference.py.

    python3 tools/gen_goldens.py           # rewrite the goldens
    python3 tools/gen_goldens.py --check   # CI: fail if they are stale

The goldens are the numbers every renderer is held to (SPEC §5, §6.1, §7.4): transfer
functions, primary conversions, LUT-space compositions on display pictures and on Log/HLG
footage, the effect params, and the blend modes. Inputs are fixed grids, so the files only
change when the maths does.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, ROOT)
from lenspack import reference as ref  # noqa: E402

OUT = os.path.join(ROOT, "conformance", "goldens")


def r6(v):
    return round(v, 6)


def rows(vectors):
    return [[r6(x) for x in v] for v in vectors]


def grid(values):
    return [[r, g, b] for b in values for g in values for r in values]


# ---- test cubes: simple, smooth, original transforms (not anyone's camera LUT)

def tone(x):
    """A gentle shoulder that keeps 0.18 near 0.18 and rolls highlights off."""
    x = max(0.0, x)
    return 1.25 * x / (x + 0.25) if x < 4 else 1.25 * 4 / 4.25


def log_to_709(decoder):
    to709 = ref.conversion("bt2020", "bt709")

    def fn(r, g, b):
        lin = ref.mat_vec(to709, [decoder(r), decoder(g), decoder(b)])
        return [ref.bt709_encode(min(1.0, tone(v) * 0.6)) for v in lin]
    return fn


def p3_warm(r, g, b):
    return [min(1.0, r * 1.05 + 0.01), g * 0.99 + 0.005, b * 0.9]


CUBES = {
    "applelog-to-709": ("apple-log", "rec709-display", 17, log_to_709(ref.apple_log_decode)),
    "hlg-to-709": ("hlg", "rec709-display", 17, log_to_709(ref.hlg_decode)),
    "p3-warm": ("p3-display", "p3-display", 17, p3_warm),
}


def build():
    files = {}
    cubes = {}
    for name, (inp, out, size, fn) in CUBES.items():
        text = ref.cube_text(size, fn, name)
        files[f"{name}.cube"] = text
        cubes[name] = {"file": f"{name}.cube", "input": inp, "output": out}

    # ---- encodings and primaries
    lin_points = [0.0, 0.001, 0.0031308, 0.01, 0.018, 0.05, 0.18, 0.5, 0.9, 1.0]
    encodings = {}
    for name in ref.ENCODINGS:
        pts = lin_points + ([2.0, 4.0] if name in ("apple-log", "hlg") else [])
        enc = ref.ENCODINGS[name][1]
        encodings[name] = {"primaries": ref.ENCODINGS[name][0],
                           "linear": pts, "code": [r6(enc(v)) for v in pts]}
    primaries = {f"{a}->{b}": rows(ref.conversion(a, b))
                 for a in ("bt709", "p3", "bt2020") for b in ("bt709", "p3", "bt2020") if a != b}

    # ---- LUT spaces
    display_samples = grid([0.05, 0.3, 0.55, 0.8, 0.95]) + [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0.18, 0.18, 0.18]]
    footage_samples = grid([0.1, 0.3, 0.5, 0.7, 0.9])
    cases = []
    for name, (inp, out, size, _) in CUBES.items():
        cube = ref.parse_cube(files[f"{name}.cube"])
        k = ref.lattice_encoding(inp, out)
        cases.append({"cube": name, "on": "display", "encoding": k, "samples": rows(display_samples),
                      "expected": rows(ref.apply_on_display(cube, inp, out, s) for s in display_samples),
                      "expectedEncoding": k})
        if inp in ("apple-log", "hlg"):
            for footage in ("apple-log", "hlg"):
                cases.append({"cube": name, "on": "footage", "encoding": footage,
                              "samples": rows(footage_samples),
                              "expected": rows(ref.apply_on_footage(cube, inp, out, footage, s)
                                               for s in footage_samples),
                              "expectedEncoding": ref.recording_output_encoding(out)})
    lut_spaces = {"toleranceDE2000": 1.0, "cubes": cubes, "cases": cases}

    # ---- effect params
    temp_cases = []
    for (i, shift, tint) in [(0.5, 0, 0), (0.0, 0, 0), (1.0, 0, 0), (0.5, 1200, 0), (0.5, -1500, 0),
                             (0.5, 0, 0.5), (0.5, 0, -0.5), (0.3, 800, 0.25)]:
        samples = [[0.5, 0.5, 0.5], [0.8, 0.6, 0.5], [0.2, 0.4, 0.7], [0.9, 0.9, 0.9], [0.1, 0.1, 0.1]]
        temp_cases.append({"intensity": i, "kelvinShift": shift, "tint": tint,
                           "linearMatrix": rows(ref.temperature_matrix(i, shift, tint)),
                           "samples": samples,
                           "expected": rows(ref.temperature(s, i, shift, tint) for s in samples)})
    radii = [round(0.05 * n, 2) for n in range(21)]
    vignette = [{"intensity": i, "midpoint": m, "feather": f, "r": radii,
                 "factor": [r6(ref.vignette_factor(r, i, m, f)) for r in radii]}
                for (i, m, f) in [(1.0, 0.5, 0.5), (0.6, 0.3, 1.0), (0.8, 0.7, 0.2), (0.4, 0.0, 0.0)]]
    bloom = [{"intensity": i, "threshold": t, "e": [0.1, 0.5, 0.8, 0.9, 1.0],
              "expected": [r6(ref.threshold_bloom_uniform(e, i, t)) for e in [0.1, 0.5, 0.8, 0.9, 1.0]]}
             for (i, t) in [(0.5, 0.7), (1.0, 0.5), (0.3, 0.9)]]
    chroma = [{"chroma": c, "correlation": r6(ref.grain_correlation(c))} for c in (0, 0.25, 0.5, 0.75, 1)]
    effects = {"toleranceDE2000": 1.0, "temperature": temp_cases,
               "vignette": {"tolerance": 0.01, "cases": vignette},
               "bloomThreshold": {"tolerance": 0.01, "cases": bloom},
               "grainChroma": {"tolerance": 0.1, "cases": chroma}}

    # ---- blends
    values = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]
    blends = {"tolerance": 1e-6, "cases": []}
    for mode in ("normal", "multiply", "screen", "add", "overlay", "softLight"):
        for alpha in (1.0, 0.5):
            blends["cases"].append({"blend": mode, "alpha": alpha, "cb": values, "cs": values,
                                    "co": [[r6(ref.blend(mode, cb, cs, alpha)) for cs in values] for cb in values]})

    def dump(obj):
        return json.dumps(obj, indent=1, sort_keys=True) + "\n"
    files["encodings.json"] = dump({"encodings": encodings, "primaries": primaries})
    files["lut-spaces.json"] = dump(lut_spaces)
    files["effects.json"] = dump(effects)
    files["blends.json"] = dump(blends)
    return files


def main(argv):
    files = build()
    if "--check" in argv:
        stale = [n for n, text in files.items()
                 if not os.path.exists(os.path.join(OUT, n)) or open(os.path.join(OUT, n)).read() != text]
        if stale:
            print("stale goldens: " + ", ".join(stale) + " — run python3 tools/gen_goldens.py")
            return 1
        print("goldens are up to date")
        return 0
    os.makedirs(OUT, exist_ok=True)
    for name, text in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(text)
    print(f"wrote {len(files)} golden files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
