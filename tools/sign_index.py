#!/usr/bin/env python3
#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Signs index.json with the gallery's Ed25519 signing key and writes index.json.sig.

    LENSPACK_INDEX_SIGNING_KEY="$(cat …)" python3 tools/sign_index.py [--key-id 2026-sign]

Runs in CI only, in the `release` GitHub Environment, which holds the key as the secret
`LENSPACK_INDEX_SIGNING_KEY` (PKCS#8 PEM, as `openssl genpkey -algorithm ed25519` writes it).
The key is read from the environment and nowhere else: this script takes no key path, writes the
key nowhere and never prints it. Signing goes through `cryptography` (audited, constant time);
the result is then checked by the independent pure-Python verifier in `lenspack.ed25519`, and
against the public key `index-keys.json` pins for the key id, so a mis-pasted secret fails here
rather than in the app.

The signature is over the exact bytes of index.json (SPEC §10.1). Signed: {"v": 1, "keyId", "sig"}.
"""
import argparse
import base64
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, ROOT)
from lenspack import ed25519, index_signing  # noqa: E402

ENV = "LENSPACK_INDEX_SIGNING_KEY"


def load_private_key(pem_text):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = serialization.load_pem_private_key(pem_text.encode("ascii"), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit(f"{ENV} is not an Ed25519 key")
    return key


def raw_public(key):
    from cryptography.hazmat.primitives import serialization
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def signature_document(key_id, signature):
    return json.dumps({"v": index_signing.SIGNATURE_VERSION, "keyId": key_id,
                       "sig": base64.b64encode(signature).decode("ascii")}) + "\n"


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=os.path.join(ROOT, "index.json"))
    parser.add_argument("--key-id", default="2026-sign")
    parser.add_argument("--keys", default=os.path.join(ROOT, "index-keys.json"))
    args = parser.parse_args(argv[1:])

    pem = os.environ.get(ENV)
    if not pem:
        raise SystemExit(f"{ENV} is not set — signing runs only in the release environment")
    key = load_private_key(pem)
    del pem
    with open(args.index, "rb") as f:
        index_bytes = f.read()
    signature = key.sign(index_bytes)
    public = raw_public(key)
    del key

    if not ed25519.verify(public, index_bytes, signature):
        raise SystemExit("self-check failed: the signature does not verify")
    pinned = index_signing.load_keys(args.keys) if os.path.exists(args.keys) else {}
    if args.key_id in pinned and pinned[args.key_id][0] != public:
        raise SystemExit(f"the key in {ENV} is not the public key pinned as {args.key_id!r} in index-keys.json")
    if args.key_id not in pinned:
        print(f"warning: {args.key_id!r} is not in index-keys.json yet; the app will not trust this signature "
              f"until its public key is pinned there and in IndexSignature.swift")

    with open(args.index + ".sig", "w", encoding="utf-8") as f:
        f.write(signature_document(args.key_id, signature))
    print(f"signed {os.path.relpath(args.index, ROOT)} with {args.key_id} "
          f"(public key {base64.b64encode(public).decode()})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
