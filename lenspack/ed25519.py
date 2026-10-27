#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Ed25519 signature verification (RFC 8032 §5.1.7), in pure Python.

Verification handles no secret, so it needs neither constant time nor a native library: this is
what `lenspack verify-index` runs, and it lets the CLI install with no dependencies at all.
Signing is deliberately NOT here. Signing touches the private key, and the only code that does
that is `tools/sign_index.py`, through the audited, constant-time `cryptography` package, in CI.

`sign_for_tests` exists for the test suite's own throwaway keys (generated in memory, never
written anywhere) and is not constant time. Do not use it for a real key.
"""
import hashlib

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = -121665 * pow(121666, P - 2, P) % P
I = pow(2, (P - 1) // 4, P)


def _inv(x):
    return pow(x, P - 2, P)


def _recover_x(y, sign):
    if y >= P:
        return None
    x2 = (y * y - 1) * _inv(D * y * y + 1) % P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * I % P
    if (x * x - x2) % P != 0:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


_GY = 4 * _inv(5) % P
_GX = _recover_x(_GY, 0)
G = (_GX, _GY, 1, _GX * _GY % P)
IDENTITY = (0, 1, 1, 0)


def _add(p, q):
    a = (p[1] - p[0]) * (q[1] - q[0]) % P
    b = (p[1] + p[0]) * (q[1] + q[0]) % P
    c = 2 * p[3] * q[3] * D % P
    d = 2 * p[2] * q[2] % P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _mul(s, p):
    q = IDENTITY
    while s > 0:
        if s & 1:
            q = _add(q, p)
        p = _add(p, p)
        s >>= 1
    return q


def _equal(p, q):
    return (p[0] * q[2] - q[0] * p[2]) % P == 0 and (p[1] * q[2] - q[1] * p[2]) % P == 0


def _compress(p):
    zinv = _inv(p[2])
    x, y = p[0] * zinv % P, p[1] * zinv % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % P)


def _sha512_int(*parts):
    return int.from_bytes(hashlib.sha512(b"".join(parts)).digest(), "little")


def verify(public_key, message, signature):
    """True iff `signature` (64 bytes) is a valid Ed25519 signature of `message` by
    `public_key` (32 bytes). Never raises on malformed input."""
    if len(public_key) != 32 or len(signature) != 64:
        return False
    a = _decompress(public_key)
    if a is None:
        return False
    r_bytes = signature[:32]
    r = _decompress(r_bytes)
    if r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= L:
        return False
    h = _sha512_int(r_bytes, public_key, message) % L
    return _equal(_mul(s, G), _add(r, _mul(h, a)))


def _expand(seed):
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key_for_tests(seed):
    a, _ = _expand(seed)
    return _compress(_mul(a, G))


def sign_for_tests(seed, message):
    """RFC 8032 §5.1.6. Not constant time: for the test suite's throwaway keys only."""
    a, prefix = _expand(seed)
    public = _compress(_mul(a, G))
    r = _sha512_int(prefix, message) % L
    r_point = _compress(_mul(r, G))
    h = _sha512_int(r_point, public, message) % L
    s = (r + h * a) % L
    return r_point + int.to_bytes(s, 32, "little")
