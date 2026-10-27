#!/usr/bin/env python3
#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""CI gate: fails if any tracked file contains a PEM private-key header or is a key file.

    python3 tools/scan_secrets.py

The signing keys live in a password manager and a GitHub Environment secret, never here
(PUBLISHING.md). This makes "never" checkable.
"""
import re
import subprocess
import sys

HEADER = re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
KEY_SUFFIXES = (".pem", ".key", ".p8", ".p12")


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True).stdout
    return [p for p in out.decode().split("\0") if p]


def main():
    bad = []
    for path in tracked_files():
        if path.lower().endswith(KEY_SUFFIXES):
            bad.append(f"{path}: key file")
            continue
        try:
            data = open(path, "rb").read()
        except OSError:
            continue
        if HEADER.search(data):
            bad.append(f"{path}: PEM private-key header")
    if bad:
        print("private key material in the repository:\n  " + "\n  ".join(bad))
        return 1
    print("no private key material tracked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
