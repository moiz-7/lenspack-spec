#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Index signature decisions (SPEC §10.1). Every key here is a throwaway made in memory for the
test and discarded with it; no private key exists in this repository."""
import base64
import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)
from lenspack import ed25519, index_signing  # noqa: E402


def keypair():
    seed = os.urandom(32)
    return seed, ed25519.public_key_for_tests(seed)


def index_bytes(sequence=5, **extra):
    return (json.dumps(dict({"version": 2, "sequence": sequence, "packs": []}, **extra), indent=2) + "\n").encode()


def sig_doc(seed, data, key_id="2026-sign"):
    sig = ed25519.sign_for_tests(seed, data)
    return json.dumps({"v": 1, "keyId": key_id, "sig": base64.b64encode(sig).decode()}).encode()


@pytest.fixture
def keys():
    sign_seed, sign_pub = keypair()
    rot_seed, rot_pub = keypair()
    return {"seeds": {"2026-sign": sign_seed, "2026-rotate": rot_seed},
            "pinned": {"2026-sign": (sign_pub, "signing"), "2026-rotate": (rot_pub, "rotation")}}


def test_rfc8032_vector_verifies():
    """RFC 8032 §7.1 test 2 — its public key, message and signature (published, public data)."""
    pk = bytes.fromhex("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c")
    sig = bytes.fromhex("92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
                        "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00")
    assert ed25519.verify(pk, b"\x72", sig)
    assert not ed25519.verify(pk, b"\x73", sig)


def test_valid(keys):
    data = index_bytes()
    assert index_signing.verify(data, sig_doc(keys["seeds"]["2026-sign"], data), keys["pinned"]) == (5, [])


def test_tampered_byte(keys):
    data = index_bytes()
    sig = sig_doc(keys["seeds"]["2026-sign"], data)
    tampered = data.replace(b'"sequence": 5', b'"sequence": 6')
    with pytest.raises(index_signing.Rejected) as e:
        index_signing.verify(tampered, sig, keys["pinned"])
    assert e.value.code == "signature.invalid"


def test_wrong_key(keys):
    data = index_bytes()
    stranger, _ = keypair()
    with pytest.raises(index_signing.Rejected) as e:
        index_signing.verify(data, sig_doc(stranger, data), keys["pinned"])
    assert e.value.code == "signature.invalid"
    with pytest.raises(index_signing.Rejected) as e:
        index_signing.verify(data, sig_doc(stranger, data, key_id="someone"), keys["pinned"])
    assert e.value.code == "signature.unknownKey"


def test_revoked_key(keys):
    data = index_bytes(revokeKeyIds=["2026-sign"])
    seq, revoked = index_signing.verify(data, sig_doc(keys["seeds"]["2026-rotate"], data, key_id="2026-rotate"), keys["pinned"])
    assert revoked == ["2026-sign"]
    later = index_bytes(sequence=9)
    with pytest.raises(index_signing.Rejected) as e:
        index_signing.verify(later, sig_doc(keys["seeds"]["2026-sign"], later), keys["pinned"], revoked=revoked)
    assert e.value.code == "signature.revokedKey"


def test_revocation_needs_the_rotation_key(keys):
    data = index_bytes(revokeKeyIds=["2026-rotate"])
    assert index_signing.verify(data, sig_doc(keys["seeds"]["2026-sign"], data), keys["pinned"]) == (5, [])


def test_lower_sequence(keys):
    data = index_bytes(sequence=3)
    with pytest.raises(index_signing.Rejected) as e:
        index_signing.verify(data, sig_doc(keys["seeds"]["2026-sign"], data), keys["pinned"], sequence_seen=4)
    assert e.value.code == "index.rollback"
    # Equal is fine: the same index fetched again.
    index_signing.verify(data, sig_doc(keys["seeds"]["2026-sign"], data), keys["pinned"], sequence_seen=3)


@pytest.mark.parametrize("sig,code", [(None, "signature.missing"), (b"{}", "signature.malformed"),
                                      (b'{"v":1,"keyId":"2026-sign","sig":"AAAA"}', "signature.malformed"),
                                      (b"not json", "signature.malformed")])
def test_missing_or_malformed(keys, sig, code):
    with pytest.raises(index_signing.Rejected) as e:
        index_signing.verify(index_bytes(), sig, keys["pinned"])
    assert e.value.code == code


def test_signed_index_needs_a_sequence(keys):
    data = json.dumps({"version": 2, "packs": []}).encode()
    with pytest.raises(index_signing.Rejected) as e:
        index_signing.verify(data, sig_doc(keys["seeds"]["2026-sign"], data), keys["pinned"])
    assert e.value.code == "index.sequenceMissing"


def test_committed_key_list_holds_public_keys_only():
    doc = json.load(open(os.path.join(ROOT, "index-keys.json"), encoding="utf-8"))
    for entry in doc["keys"]:
        assert set(entry) <= {"id", "role", "publicKey", "comment"}
        assert len(base64.b64decode(entry["publicKey"])) == 32
    index_signing.load_keys(os.path.join(ROOT, "index-keys.json"))


@pytest.mark.skipif(importlib.util.find_spec("cryptography") is None, reason="cryptography not installed")
def test_sign_index_tool_round_trip(tmp_path, monkeypatch):
    """tools/sign_index.py with a throwaway key held only in the process environment."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import sign_index
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    index = tmp_path / "index.json"
    index.write_bytes(index_bytes())
    keyfile = tmp_path / "keys.json"
    keyfile.write_text(json.dumps({"keys": [{"id": "2026-sign", "role": "signing",
                                             "publicKey": base64.b64encode(public).decode()}]}))
    monkeypatch.setenv(sign_index.ENV, pem)
    assert sign_index.main(["sign_index.py", "--index", str(index), "--keys", str(keyfile)]) == 0
    sig = (tmp_path / "index.json.sig").read_bytes()
    assert index_signing.verify(index.read_bytes(), sig, index_signing.load_keys(str(keyfile)))[0] == 5
