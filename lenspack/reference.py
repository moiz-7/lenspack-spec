#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""The reference maths of SPEC §5, §6.1 and §7.4, in plain Python.

This is the arithmetic a renderer is held to, written to be read rather than to be fast: every
function is the formula in the spec, term for term, with no lattice, no GPU and no
approximation beyond floating point. `tools/gen_goldens.py` evaluates it into
`conformance/goldens/`, and the app's tests compare their own renderer against those numbers.

Nothing here is used to *render* a pack; it is a yardstick.
"""
import math

# ---------------------------------------------------------------------------------------------
# Transfer functions (§5.1). Linear light ↔ full-range code values in 0…1.


def srgb_encode(v):
    v = max(0.0, v)
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def srgb_decode(c):
    c = max(0.0, c)
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def bt709_encode(v):
    v = max(0.0, v)
    return 4.5 * v if v < 0.018 else 1.099 * v ** 0.45 - 0.099


def bt709_decode(c):
    c = max(0.0, c)
    return c / 4.5 if c < 0.081 else ((c + 0.099) / 1.099) ** (1 / 0.45)


# Apple Log (Apple, "Apple Log Profile", 2023), on scene-linear reflectance (0.18 = mid grey).
AL_R0 = -0.05641088
AL_RT = 0.01
AL_C = 47.28711236
AL_BETA = 0.00964052
AL_GAMMA = 0.08550479
AL_DELTA = 0.69336945
AL_PT = AL_C * (AL_RT - AL_R0) ** 2


def apple_log_encode(r):
    if r < AL_R0:
        return 0.0
    if r < AL_RT:
        return AL_C * (r - AL_R0) ** 2
    return AL_GAMMA * math.log2(r + AL_BETA) + AL_DELTA


def apple_log_decode(p):
    if p <= 0:
        return AL_R0
    if p < AL_PT:
        return math.sqrt(p / AL_C) + AL_R0
    return 2 ** ((p - AL_DELTA) / AL_GAMMA) - AL_BETA


# BT.2100 HLG, with scene-linear reflectance mapped so that 0.18 lands at 38 % signal (BT.2408).
HLG_A = 0.17883277
HLG_B = 1 - 4 * HLG_A
HLG_C = 0.5 - HLG_A * math.log(4 * HLG_A)
HLG_E18 = 0.38 ** 2 / 3


def hlg_oetf(e):
    e = min(max(e, 0.0), 1.0)
    return math.sqrt(3 * e) if e <= 1 / 12 else HLG_A * math.log(12 * e - HLG_B) + HLG_C


def hlg_inverse_oetf(v):
    v = min(max(v, 0.0), 1.0)
    return v * v / 3 if v <= 0.5 else (math.exp((v - HLG_C) / HLG_A) + HLG_B) / 12


def hlg_encode(r):
    return hlg_oetf(r * HLG_E18 / 0.18)


def hlg_decode(v):
    return hlg_inverse_oetf(v) * 0.18 / HLG_E18


# ---------------------------------------------------------------------------------------------
# Primaries (§5.1). Matrices derived from chromaticities through XYZ, white D65 everywhere.

PRIMARIES = {
    "bt709": ((0.640, 0.330), (0.300, 0.600), (0.150, 0.060)),
    "p3": ((0.680, 0.320), (0.265, 0.690), (0.150, 0.060)),
    "bt2020": ((0.708, 0.292), (0.170, 0.797), (0.131, 0.046)),
}
D65 = (0.3127, 0.3290)


def _xyz(xy):
    x, y = xy
    return (x / y, 1.0, (1 - x - y) / y)


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mat_vec(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def mat_inv(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def rgb_to_xyz(name):
    cols = [_xyz(p) for p in PRIMARIES[name]]
    m = [[cols[j][i] for j in range(3)] for i in range(3)]
    s = mat_vec(mat_inv(m), _xyz(D65))
    return [[m[i][j] * s[j] for j in range(3)] for i in range(3)]


def conversion(src, dst):
    """Linear RGB in `src` primaries → linear RGB in `dst` primaries."""
    if src == dst:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    return mat_mul(mat_inv(rgb_to_xyz(dst)), rgb_to_xyz(src))


# ---------------------------------------------------------------------------------------------
# Encodings (§5.1)

ENCODINGS = {
    "srgb-display": ("bt709", srgb_encode, srgb_decode),
    "rec709-display": ("bt709", bt709_encode, bt709_decode),
    "p3-display": ("p3", srgb_encode, srgb_decode),
    "apple-log": ("bt2020", apple_log_encode, apple_log_decode),
    "hlg": ("bt2020", hlg_encode, hlg_decode),
}


def default_output(inp):
    return inp if inp.endswith("-display") else "rec709-display"


def decode(encoding, rgb):
    """Code values → linear light, in the encoding's own primaries."""
    return [ENCODINGS[encoding][2](c) for c in rgb]


def encode(encoding, rgb):
    return [ENCODINGS[encoding][1](v) for v in rgb]


def convert(rgb, src_encoding, dst_encoding):
    """Code values in one encoding → code values in another (no clamping of the result)."""
    lin = decode(src_encoding, rgb)
    lin = mat_vec(conversion(ENCODINGS[src_encoding][0], ENCODINGS[dst_encoding][0]), lin)
    return encode(dst_encoding, lin)


# ---------------------------------------------------------------------------------------------
# Cubes


def parse_cube(text):
    size, rows = 0, []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "TITLE", "DOMAIN_MIN", "DOMAIN_MAX")):
            continue
        if line.startswith("LUT_3D_SIZE"):
            size = int(line.split()[1])
            continue
        rows.append([float(x) for x in line.split()])
    assert len(rows) == size ** 3
    return size, rows


def cube_text(size, fn, title):
    """Sample fn(r, g, b) → (r, g, b) on a size³ lattice, red fastest, 6 decimals."""
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {size}"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                out = fn(r / (size - 1), g / (size - 1), b / (size - 1))
                lines.append(" ".join(f"{min(max(v, 0.0), 1.0):.6f}" for v in out))
    return "\n".join(lines) + "\n"


def trilinear(size, rows, rgb):
    """The interpolation every GPU sampler and Core Image colour cube performs."""
    base, frac = [], []
    for v in rgb:
        x = min(max(v, 0.0), 1.0) * (size - 1)
        i = min(int(x), size - 2)
        base.append(i)
        frac.append(x - i)
    out = [0.0, 0.0, 0.0]
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                w = (frac[0] if dx else 1 - frac[0]) * (frac[1] if dy else 1 - frac[1]) \
                    * (frac[2] if dz else 1 - frac[2])
                row = rows[((base[2] + dz) * size + base[1] + dy) * size + base[0] + dx]
                for c in range(3):
                    out[c] += w * row[c]
    return out


def lattice_encoding(inp, out):
    """K in §5.2."""
    return "p3-display" if "p3-display" in (inp, out) else "srgb-display"


def apply_on_display(cube, inp, out, rgb):
    """§5.2 on display-referred values, exactly (no composed lattice): `rgb` is in the lattice
    encoding K; the result is in K, clamped."""
    size, rows = cube
    k = lattice_encoding(inp, out)
    y = trilinear(size, rows, convert(rgb, k, inp))
    return [min(max(v, 0.0), 1.0) for v in convert(y, out, k)]


def recording_output_encoding(out):
    return "rec709-display" if out == "rec709-display" else "srgb-display"


def apply_on_footage(cube, inp, out, footage, code):
    """§5.2 on camera footage in the `footage` encoding (apple-log or hlg) → the recording's
    display encoding."""
    size, rows = cube
    x = code if footage == inp else convert(code, footage, inp)
    y = trilinear(size, rows, x)
    return [min(max(v, 0.0), 1.0) for v in convert(y, out, recording_output_encoding(out))]


# ---------------------------------------------------------------------------------------------
# CIE Lab and ΔE2000 (for reporting differences)


def lab(rgb, encoding):
    lin = mat_vec(conversion(ENCODINGS[encoding][0], "bt709"), decode(encoding, rgb))
    x, y, z = mat_vec(rgb_to_xyz("bt709"), lin)
    wx, wy, wz = _xyz(D65)

    def f(t):
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29
    fx, fy, fz = f(x / wx), f(y / wy), f(z / wz)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e2000(l1, l2):
    """CIEDE2000 (Sharma, Wu and Dalal's formulation)."""
    L1, a1, b1 = l1
    L2, a2, b2 = l2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    cm = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(cm ** 7 / (cm ** 7 + 25 ** 7)))
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dlp, dcp = L2 - L1, c2p - c1p
    dh = h2p - h1p
    if c1p * c2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dhp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    lm, cmp_ = (L1 + L2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        hm = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hm = (h1p + h2p) / 2
    else:
        hm = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(hm - 30)) + 0.24 * math.cos(math.radians(2 * hm))
         + 0.32 * math.cos(math.radians(3 * hm + 6)) - 0.20 * math.cos(math.radians(4 * hm - 63)))
    dtheta = 30 * math.exp(-(((hm - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cmp_ ** 7 / (cmp_ ** 7 + 25 ** 7))
    sl = 1 + 0.015 * (lm - 50) ** 2 / math.sqrt(20 + (lm - 50) ** 2)
    sc = 1 + 0.045 * cmp_
    sh = 1 + 0.015 * cmp_ * t
    rt = -math.sin(math.radians(2 * dtheta)) * rc
    return math.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dhp / sh) ** 2 + rt * (dcp / sc) * (dhp / sh))


# ---------------------------------------------------------------------------------------------
# Effect params (§6.1)

BRADFORD = [[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]]


def planck_uv(t):
    """Krystek (1985): the Planckian locus in CIE 1960 uv, 1000–15000 K."""
    u = (0.860117757 + 1.54118254e-4 * t + 1.28641212e-7 * t * t) / (1 + 8.42420235e-4 * t + 7.08145163e-7 * t * t)
    v = (0.317398726 + 4.22806245e-5 * t + 4.20481691e-8 * t * t) / (1 - 2.89741816e-5 * t + 1.61456053e-7 * t * t)
    return u, v


def isotherm_normal(t):
    """Unit normal to the locus at t, pointing toward green (the +v side). Central difference
    over ±1 K."""
    u0, v0 = planck_uv(t - 1)
    u1, v1 = planck_uv(t + 1)
    du, dv = u1 - u0, v1 - v0
    n = (-dv, du) if du >= 0 else (dv, -du)
    if n[1] < 0:
        n = (-n[0], -n[1])
    length = math.hypot(*n)
    return n[0] / length, n[1] / length


def white_xyz(t, tint):
    u, v = planck_uv(t)
    if tint:
        nu, nv = isotherm_normal(t)
        # Positive tint is magenta: away from green.
        u, v = u - 0.02 * tint * nu, v - 0.02 * tint * nv
    d = 2 * u - 8 * v + 4
    x, y = 3 * u / d, 2 * v / d
    return [x / y, 1.0, (1 - x - y) / y]


def temperature_target(intensity, kelvin_shift):
    return min(15000.0, max(1000.0, 3500 + 6000 * min(max(intensity, 0.0), 1.0) + kelvin_shift))


def temperature_matrix(intensity, kelvin_shift=0.0, tint=0.0):
    """Linear BT.709 RGB → linear BT.709 RGB: Bradford from the 6500 K Planckian white to the
    target white."""
    src = mat_vec(BRADFORD, white_xyz(6500.0, 0.0))
    dst = mat_vec(BRADFORD, white_xyz(temperature_target(intensity, kelvin_shift), tint))
    scale = [[dst[0] / src[0], 0.0, 0.0], [0.0, dst[1] / src[1], 0.0], [0.0, 0.0, dst[2] / src[2]]]
    adapt = mat_mul(mat_inv(BRADFORD), mat_mul(scale, BRADFORD))
    m = rgb_to_xyz("bt709")
    return mat_mul(mat_inv(m), mat_mul(adapt, m))


def temperature(rgb_display, intensity, kelvin_shift=0.0, tint=0.0):
    lin = [srgb_decode(c) for c in rgb_display]
    out = mat_vec(temperature_matrix(intensity, kelvin_shift, tint), lin)
    return [min(max(srgb_encode(v), 0.0), 1.0) for v in out]


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def vignette_factor(r, intensity, midpoint=0.5, feather=0.0):
    m, f = midpoint, feather
    return 1 - intensity * smoothstep(m, m + f * (1 - m) + 0.001, r)


def threshold_bloom_uniform(e, intensity, threshold):
    """A uniform patch: the blur of a constant is the constant."""
    h = min(max((e - threshold) / (1 - threshold), 0.0), 1.0)
    return 1 - (1 - e) * (1 - intensity * h)


def grain_correlation(chroma):
    a, b = 1 - chroma, chroma
    return a * a / (a * a + b * b)


# ---------------------------------------------------------------------------------------------
# Blends (§7.4), on display-encoded values


def _soft_d(cb):
    return ((16 * cb - 12) * cb + 4) * cb if cb <= 0.25 else math.sqrt(cb)


BLENDS = {
    "normal": lambda cb, cs: cs,
    "multiply": lambda cb, cs: cb * cs,
    "screen": lambda cb, cs: cb + cs - cb * cs,
    "overlay": lambda cb, cs: 2 * cb * cs if cb <= 0.5 else 1 - 2 * (1 - cb) * (1 - cs),
    "softLight": lambda cb, cs: (cb - (1 - 2 * cs) * cb * (1 - cb)) if cs <= 0.5
    else cb + (2 * cs - 1) * (_soft_d(cb) - cb),
}


def blend(mode, cb, cs, alpha):
    """One channel: backdrop cb, source cs (unpremultiplied), source alpha × opacity."""
    if mode == "add":
        return min(1.0, cb + alpha * cs)
    return (1 - alpha) * cb + alpha * BLENDS[mode](cb, cs)
