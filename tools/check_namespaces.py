#!/usr/bin/env python3
#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""CI gate for pull requests: the author owns the namespace of every pack they add or change.

    python3 tools/check_namespaces.py --author <github login> --base <base commit>

Rules (SPEC §10.3):
  * a pack under packs/ belongs to the namespace of its manifest `id` (`@author/slug`);
  * the PR author must be listed for that namespace in namespaces.json **as it is on the base
    branch** — or claim it in this PR, if it was free and is not reserved;
  * a PR may add namespace entries only for its own author, and may not change or remove an
    existing entry or the reserved/maintainers lists, unless the author is a maintainer;
  * `@local` (packs made on a device) is never published.
Identity checks beyond the GitHub login: never.
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], check=True, capture_output=True, text=True).stdout


def load_at(ref, path):
    try:
        return json.loads(git("show", f"{ref}:{path}"))
    except subprocess.CalledProcessError:
        return None


def changed_pack_folders(base):
    names = git("diff", "--name-only", f"{base}...HEAD").splitlines()
    folders = set()
    for name in names:
        parts = name.split("/")
        if len(parts) >= 2 and parts[0] == "packs" and parts[1].endswith(".lenspack"):
            folders.add(parts[1])
    return sorted(folders)


def check(author, base_doc, head_doc, packs):
    """packs: [(folder name, manifest dict or None if deleted)]. Returns a list of problems."""
    problems = []
    base_doc = base_doc or {"maintainers": [], "reserved": [], "namespaces": {}}
    maintainers = set(base_doc.get("maintainers", []))
    reserved = set(base_doc.get("reserved", []))
    base_ns = base_doc.get("namespaces", {})
    head_ns = head_doc.get("namespaces", {})
    is_maintainer = author in maintainers

    if not is_maintainer:
        for key in ("maintainers", "reserved"):
            if head_doc.get(key) != base_doc.get(key):
                problems.append(f"namespaces.json: only a maintainer may change {key!r}")
        for ns, owners in base_ns.items():
            if head_ns.get(ns) != owners:
                problems.append(f"namespaces.json: only a maintainer may change {ns}")
        for ns, owners in head_ns.items():
            if ns in base_ns:
                continue
            if ns in reserved:
                problems.append(f"namespaces.json: {ns} is reserved")
            elif owners != [author]:
                problems.append(f"namespaces.json: a new namespace may only be claimed for yourself ({ns} → {owners})")

    for folder, manifest in packs:
        if manifest is None:
            ns = "@" + folder.split(".", 1)[0]
        else:
            pid = manifest.get("id", "")
            ns = pid.split("/", 1)[0] if pid.startswith("@") else ""
        if ns == "@local":
            problems.append(f"{folder}: @local packs are made on a device and are never published")
            continue
        owners = base_ns.get(ns) or (head_ns.get(ns) if ns not in base_ns and ns not in reserved else None)
        if not owners or author not in owners:
            problems.append(f"{folder}: {author} does not own {ns or 'its namespace'}")
    return problems


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--author", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args(argv[1:])
    base_doc = load_at(args.base, "namespaces.json")
    head_doc = json.load(open(os.path.join(ROOT, "namespaces.json"), encoding="utf-8"))
    packs = []
    for folder in changed_pack_folders(args.base):
        path = os.path.join(ROOT, "packs", folder, "manifest.json")
        packs.append((folder, json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None))
    problems = check(args.author, base_doc, head_doc, packs)
    for p in problems:
        print("NAMESPACE " + p)
    if not problems:
        print(f"namespaces ok for {args.author} ({len(packs)} pack folder(s) changed)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
