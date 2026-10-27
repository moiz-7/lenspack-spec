#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Reproducible `.lenspack` archives (SPEC §1): the same folder always gives the same bytes."""
import hashlib
import io
import os
import zipfile

from . import validator

FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def deterministic_zip(folder):
    """Zip `folder`'s contents: entries sorted by path, a fixed 1980-01-01 timestamp, Unix mode
    0644, deflate level 9, no extra fields. Refuses symlinks and anything the path rule refuses;
    skips dot-files."""
    limits = validator.load_limits()
    files = []
    for base, dirs, names in os.walk(folder):
        dirs.sort()
        for name in names:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, folder).replace(os.sep, "/")
            if name.startswith("."):
                continue
            if os.path.islink(full) or not validator.path_is_lexically_safe(rel, limits["paths"]["maxComponents"]):
                raise ValueError(f"refusing to pack {rel!r}")
            files.append(rel)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for rel in sorted(files):
            info = zipfile.ZipInfo(rel, date_time=FIXED_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(folder, *rel.split("/")), "rb") as f:
                zf.writestr(info, f.read(), compresslevel=9)
    return buf.getvalue()


def digest(data):
    """(sha256 hex, size) — the two numbers a gallery index entry pins."""
    return hashlib.sha256(data).hexdigest(), len(data)
