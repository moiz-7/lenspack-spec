#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""The reference maths against published numbers, and the committed goldens against it."""
import json
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from lenspack import reference as ref  # noqa: E402
import gen_goldens  # noqa: E402

GOLDENS = os.path.join(ROOT, "conformance", "goldens")


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def test_transfer_round_trips():
    for name, (_, enc, dec) in ref.ENCODINGS.items():
        for v in (0.0, 0.002, 0.01, 0.18, 0.5, 0.9, 1.0):
            assert close(dec(enc(v)), v, 1e-9), (name, v)


def test_apple_log_is_continuous_and_puts_grey_where_apple_says():
    lo = ref.AL_C * (ref.AL_RT - ref.AL_R0) ** 2
    hi = ref.AL_GAMMA * __import__("math").log2(ref.AL_RT + ref.AL_BETA) + ref.AL_DELTA
    assert close(lo, hi, 1e-6)
    assert close(ref.apple_log_encode(0.18), 0.4883, 1e-4)


def test_hlg_grey_card_at_38_percent():
    assert close(ref.hlg_encode(0.18), 0.38, 1e-12)
    assert close(ref.hlg_oetf(1.0), 1.0, 1e-6)


def test_primaries_match_bt2087():
    m = ref.conversion("bt709", "bt2020")
    want = [[0.6274, 0.3293, 0.0433], [0.0691, 0.9195, 0.0114], [0.0164, 0.0880, 0.8956]]
    for i in range(3):
        for j in range(3):
            assert close(m[i][j], want[i][j], 1e-4)


@pytest.mark.parametrize("l1,l2,want", [
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
])
def test_delta_e2000_sharma_vectors(l1, l2, want):
    assert close(ref.delta_e2000(l1, l2), want, 1e-4)


def test_temperature_is_neutral_at_half_and_warm_below():
    assert all(close(v, 0.5, 1e-9) for v in ref.temperature([0.5, 0.5, 0.5], 0.5))
    r, g, b = ref.temperature([0.5, 0.5, 0.5], 0.0)
    assert r > g > b
    r, g, b = ref.temperature([0.5, 0.5, 0.5], 0.5, 0, 0.5)
    assert g < r and g < b, "positive tint is magenta"


def test_blends_match_their_definitions():
    assert ref.blend("multiply", 0.5, 0.5, 1) == 0.25
    assert ref.blend("screen", 0.5, 0.5, 1) == 0.75
    assert ref.blend("add", 0.8, 0.5, 1) == 1.0
    assert close(ref.blend("overlay", 0.25, 0.5, 1), 0.25)
    assert close(ref.blend("softLight", 0.5, 0.5, 1), 0.5)
    assert ref.blend("normal", 0.2, 0.9, 0) == 0.2


def test_composed_65_lattice_meets_the_tolerance():
    """§5.2: a 65³ composed lattice, trilinearly sampled, stays within ΔE2000 1 of the exact
    pipeline — the tolerance the goldens give renderers is achievable."""
    cases = json.load(open(os.path.join(GOLDENS, "lut-spaces.json"), encoding="utf-8"))
    case = next(c for c in cases["cases"] if c["cube"] == "applelog-to-709" and c["on"] == "display")
    info = cases["cubes"]["applelog-to-709"]
    cube = ref.parse_cube(open(os.path.join(GOLDENS, info["file"]), encoding="utf-8").read())
    n = 65

    class Lattice(dict):
        """Only the cells the samples touch are composed: same numbers, a fraction of the time."""
        def __missing__(self, i):
            r, g, b = i % n, (i // n) % n, i // (n * n)
            self[i] = ref.apply_on_display(cube, info["input"], info["output"],
                                           [r / (n - 1), g / (n - 1), b / (n - 1)])
            return self[i]
    lattice = Lattice()
    worst = 0.0
    for sample, want in zip(case["samples"], case["expected"]):
        got = ref.trilinear(n, lattice, sample)
        worst = max(worst, ref.delta_e2000(ref.lab(got, "srgb-display"), ref.lab(want, "srgb-display")))
    assert worst < cases["toleranceDE2000"], worst


def test_goldens_are_current():
    """Recomputed from the reference, numerically (not byte-for-byte: libm may differ in the
    last bit across machines)."""
    fresh = gen_goldens.build()
    for name, text in fresh.items():
        path = os.path.join(GOLDENS, name)
        committed = open(path, encoding="utf-8").read()
        if name.endswith(".cube"):
            a, b = ref.parse_cube(text), ref.parse_cube(committed)
            assert a[0] == b[0]
            assert all(close(x, y, 2e-6) for ra, rb in zip(a[1], b[1]) for x, y in zip(ra, rb)), name
        else:
            assert numbers(json.loads(text)) == pytest.approx(numbers(json.loads(committed)), abs=2e-6), name


def numbers(obj):
    if isinstance(obj, dict):
        return [x for k in sorted(obj) for x in numbers(obj[k])]
    if isinstance(obj, list):
        return [x for v in obj for x in numbers(v)]
    if isinstance(obj, bool) or not isinstance(obj, (int, float)):
        return []
    return [float(obj)]
