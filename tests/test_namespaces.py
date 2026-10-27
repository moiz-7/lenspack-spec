#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_namespaces as ns  # noqa: E402

BASE = {"maintainers": ["owner"], "reserved": ["@lens", "@local"],
        "namespaces": {"@lens": ["owner"], "@ana": ["ana"]}}


def head(**extra):
    doc = json.loads(json.dumps(BASE))
    doc["namespaces"].update(extra)
    return doc


def pack(pid):
    return (pid[1:].replace("/", ".") + ".lenspack", {"id": pid})


def test_owner_publishes_in_own_namespace():
    assert ns.check("ana", BASE, head(), [pack("@ana/sunset")]) == []


def test_stranger_cannot_publish_in_someone_elses():
    assert ns.check("bob", BASE, head(), [pack("@ana/sunset")])


def test_new_creator_claims_a_free_namespace_for_themselves():
    assert ns.check("bob", BASE, head(**{"@bob": ["bob"]}), [pack("@bob/first")]) == []
    assert ns.check("bob", BASE, head(**{"@bob": ["bob", "eve"]}), [pack("@bob/first")])


def test_reserved_and_local():
    assert ns.check("bob", BASE, head(**{"@lens": ["bob"]}), [pack("@lens/x")])
    assert ns.check("owner", BASE, head(), [pack("@local/x-1234abcd")])
    assert ns.check("owner", BASE, head(), [pack("@lens/crown")]) == []


def test_only_maintainers_edit_existing_entries():
    changed = head()
    changed["namespaces"]["@ana"] = ["bob"]
    assert ns.check("bob", BASE, changed, [])
    assert ns.check("owner", BASE, changed, []) == []


def test_repository_file_is_well_formed():
    doc = json.load(open(os.path.join(ROOT, "namespaces.json"), encoding="utf-8"))
    for reserved in ("@lens", "@lenspack-spec", "@local", "@conformance"):
        assert reserved in doc["reserved"]
    for owners in doc["namespaces"].values():
        assert owners and all(isinstance(o, str) for o in owners)
