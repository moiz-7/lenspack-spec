#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""The `lenspack` command.

    lenspack validate <path> [<path> ...] [--json]
    lenspack pack <folder> <out.lenspack>
    lenspack hash <file>
    lenspack verify-index <index.json> [--sig <index.json.sig>] [--keys <index-keys.json>] [--strict]

Exit status for `validate`: 0 valid, 1 invalid, 2 needs a newer reader (the worst over all
paths). Everything else: 0 success, 1 failure.
"""
import argparse
import json
import os
import sys

from . import __version__, index_signing, packing, validator


def cmd_validate(args):
    worst = 0
    rank = {"valid": 0, "needs-newer": 2, "invalid": 1}
    for path in args.paths:
        report = validator.validate(path)
        if args.json:
            print(json.dumps(dict(report.to_json(), path=path), indent=2))
        else:
            print(f"validating {path}")
            if report.id:
                print(f"  id: {report.id}" + (f"  version: {report.version}" if report.version else ""))
            for code, msg in report.warnings:
                print(f"  warning [{code}]: {msg}")
            for code, msg in report.needs_newer:
                print(f"  NEEDS NEWER [{code}]: {msg}")
            for code, msg in report.problems:
                print(f"  PROBLEM [{code}]: {msg}")
            print(report.result.upper())
        code = rank[report.result]
        # invalid (1) outranks needs-newer (2): a broken pack is the more urgent answer.
        if code == 1 or (code == 2 and worst == 0):
            worst = code
    return worst


def cmd_pack(args):
    report = validator.validate(args.folder)
    if report.result != "valid":
        print(f"{args.folder}: {report.result} {report.codes()} — not packed", file=sys.stderr)
        return 1
    data = packing.deterministic_zip(args.folder)
    if len(data) > validator.load_limits()["archive"]["maxArchiveBytes"]:
        print("archive over the 25 MB cap", file=sys.stderr)
        return 1
    with open(args.out, "wb") as f:
        f.write(data)
    sha, size = packing.digest(data)
    print(f"{args.out}\n  sha256 {sha}\n  size   {size}")
    return 0


def cmd_hash(args):
    with open(args.file, "rb") as f:
        sha, size = packing.digest(f.read())
    print(json.dumps({"sha256": sha, "size": size}))
    return 0


def cmd_verify_index(args):
    with open(args.index, "rb") as f:
        index_bytes = f.read()
    sig_path = args.sig or args.index + ".sig"
    sig_bytes = open(sig_path, "rb").read() if os.path.exists(sig_path) else None
    keys = index_signing.load_keys(args.keys) if args.keys and os.path.exists(args.keys) else {}
    if not keys:
        print("UNVERIFIED: no public keys are pinned (index-keys.json is empty) — the signature was not checked")
        return 1 if args.strict else 0
    try:
        sequence, revoked = index_signing.verify(index_bytes, sig_bytes, keys)
    except index_signing.Rejected as e:
        print(f"REFUSED {e}")
        return 1
    print(f"VERIFIED sequence {sequence}" + (f", revokes {revoked}" if revoked else ""))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lenspack", description="LensPack reference tooling")
    parser.add_argument("--version", action="version", version=f"lenspack {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate", help="validate .cube files, .lenspack folders and .lenspack zips")
    p.add_argument("paths", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("pack", help="validate a pack folder and write a reproducible .lenspack zip")
    p.add_argument("folder")
    p.add_argument("out")
    p.set_defaults(func=cmd_pack)
    p = sub.add_parser("hash", help="print the sha256 and size an index entry pins")
    p.add_argument("file")
    p.set_defaults(func=cmd_hash)
    p = sub.add_parser("verify-index", help="check index.json against its Ed25519 signature")
    p.add_argument("index")
    p.add_argument("--sig")
    p.add_argument("--keys", default=None)
    p.add_argument("--strict", action="store_true", help="fail when no keys are pinned")
    p.set_defaults(func=cmd_verify_index)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
