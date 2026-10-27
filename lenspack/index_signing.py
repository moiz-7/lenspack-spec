#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Gallery index signature checks (SPEC §10.1), the same decisions the app makes.

The app's `IndexSignature.swift` and this module answer one question the same way, with the
same codes: may a reader that pins `keys`, and has accepted `state` before, accept this
`index.json` with this `index.json.sig`?
"""
import base64
import binascii
import json

from . import ed25519

SIGNATURE_VERSION = 1
ROLES = ("signing", "rotation")


class Rejected(Exception):
    def __init__(self, code, message):
        super().__init__(f"[{code}] {message}")
        self.code = code


def load_keys(path):
    """index-keys.json → {key id: (public key bytes, role)}."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    keys = {}
    for entry in doc.get("keys", []):
        raw = base64.b64decode(entry["publicKey"], validate=True)
        if len(raw) != 32 or entry.get("role") not in ROLES:
            raise ValueError(f"index-keys.json: bad entry {entry.get('id')!r}")
        keys[entry["id"]] = (raw, entry["role"])
    return keys


def parse_signature(sig_bytes):
    try:
        doc = json.loads(sig_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Rejected("signature.malformed", "index.json.sig is not JSON")
    if not isinstance(doc, dict) or doc.get("v") != SIGNATURE_VERSION \
            or not isinstance(doc.get("keyId"), str) or not isinstance(doc.get("sig"), str):
        raise Rejected("signature.malformed", "index.json.sig must be {v: 1, keyId, sig}")
    try:
        sig = base64.b64decode(doc["sig"], validate=True)
    except (binascii.Error, ValueError):
        raise Rejected("signature.malformed", "sig is not base64")
    if len(sig) != 64:
        raise Rejected("signature.malformed", "sig must be 64 bytes")
    return doc["keyId"], sig


def verify(index_bytes, sig_bytes, keys, sequence_seen=0, revoked=()):
    """Accept or raise `Rejected`. Returns (sequence, newly revoked key ids).

    Order: signature shape → key known and not revoked → signature valid over the exact bytes
    → the index parses → sequence present and not lower than `sequence_seen` → revocations
    (honoured only from a rotation key)."""
    if sig_bytes is None:
        raise Rejected("signature.missing", "no index.json.sig")
    key_id, sig = parse_signature(sig_bytes)
    if key_id in revoked:
        raise Rejected("signature.revokedKey", f"key {key_id!r} was revoked")
    if key_id not in keys:
        raise Rejected("signature.unknownKey", f"key {key_id!r} is not pinned")
    public, role = keys[key_id]
    if not ed25519.verify(public, index_bytes, sig):
        raise Rejected("signature.invalid", "the signature does not match index.json")
    try:
        index = json.loads(index_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Rejected("index.malformed", "index.json is not JSON")
    sequence = index.get("sequence") if isinstance(index, dict) else None
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise Rejected("index.sequenceMissing", "a signed index must carry a positive 'sequence'")
    if sequence < sequence_seen:
        raise Rejected("index.rollback", f"sequence {sequence} is below {sequence_seen}, already seen")
    newly_revoked = []
    if role == "rotation":
        ids = index.get("revokeKeyIds", [])
        if isinstance(ids, list):
            newly_revoked = [k for k in ids if isinstance(k, str) and k != key_id]
    return sequence, newly_revoked
