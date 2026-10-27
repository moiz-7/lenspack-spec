#!/usr/bin/env python3
#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Regenerates conformance/cases/ from the table below.

    python3 tools/gen_conformance.py

The cases are committed; this script exists so they are reproducible and reviewable as
code. Every case is a pack folder plus an entry in cases/expect.json:

    {"<valid|invalid>/<case>.lenspack": {"result": "valid|invalid|needs-newer",
                                         "codes": ["path.unsafe", ...]}}

`codes` lists problem (or needs-newer) codes that must appear; a reader may report more.
Symlink cases are not stored here (git and resource copying both mangle symlinks); each
implementation's own test suite builds them at test time.
"""
import json
import os
import shutil
import struct
import zlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "conformance", "cases")


def png(width, height):
    """A solid transparent RGBA PNG. Compresses to almost nothing at any size, so the
    budget cases can claim megapixels without bloating the repo."""
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(width * 4) for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def cube(size=2):
    lines = ["TITLE \"conformance\"", f"LUT_3D_SIZE {size}"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                d = size - 1
                lines.append(f"{r / d:.6f} {g / d:.6f} {b / d:.6f}")
    return ("\n".join(lines) + "\n").encode()


SMALL = png(64, 64)
V4 = {"lenspack": 4, "id": "@conformance/case", "version": "1.0.0", "name": "Case"}


def v4(**fields):
    m = dict(V4)
    m.update(fields)
    return m


def ov(image="a.png", **extra):
    d = {"image": image, "anchor": "forehead"}
    d.update(extra)
    return d


CASES = {
    # ---------------------------------------------------------------- legacy (v1–v3, v5)
    "valid/legacy-v1-lut": ({"name": "Legacy LUT", "author": "@x", "version": "1.0", "lut": "look.cube"},
                            {"look.cube": cube()}, "valid", []),
    "valid/legacy-v2-overlay": ({"name": "Crown", "overlays": [ov(scale=1.3, offsetY=0.1)]},
                                {"a.png": SMALL}, "valid", []),
    "valid/legacy-v2-animated": ({"name": "Sparkle", "overlays": [ov(frames=["b.png", "c.png"], fps=12)]},
                                 {"a.png": SMALL, "b.png": SMALL, "c.png": SMALL}, "valid", []),
    "valid/legacy-v3-effects": ({"name": "Film", "effects": [{"type": "bloom", "intensity": 0.4},
                                                            {"type": "grain"},
                                                            {"type": "teleport", "intensity": 1}]},
                                {}, "valid", []),
    "valid/legacy-v31-data": ({"name": "Ski Day", "effects": [{"type": "fade", "intensity": 0.3}],
                               "data": [{"type": "elevation"}, {"type": "speed", "position": "bottomRight"}]},
                              {}, "valid", []),
    "valid/legacy-v5-filter-studio": ({"name": "Face Paint", "meshTexture": "paint.png",
                                       "triggers": [{"blendshape": "mouthOpen", "threshold": 0.6,
                                                     "overlay": ov("fire.png", anchor="mouth")}],
                                       "requires": ["faceTracking"]},
                                      {"paint.png": SMALL, "fire.png": SMALL}, "valid", []),
    "valid/legacy-missing-overlay-dropped": ({"name": "Half", "lut": "look.cube", "overlays": [ov("gone.png")]},
                                             {"look.cube": cube()}, "valid", []),
    "valid/legacy-numeric-version": ({"name": "Old", "version": 1.0, "lut": "look.cube"},
                                     {"look.cube": cube()}, "valid", []),
    # ---------------------------------------------------------------- v4
    "valid/v4-full": (v4(id="@conformance/full", version="1.2.0-beta.1", license="CC-BY-4.0",
                         attribution="Photo grain scanned by @x", thumbnail="thumb.png",
                         localized={"fr": {"name": "Complet", "summary": "Tout"}},
                         required=["lut", "effects"],
                         lut={"file": "look.cube", "input": "apple-log", "output": "rec709-display"},
                         effects=[{"type": "grain", "intensity": 0.3,
                                   "params": {"size": 0.002, "roughness": 0.5, "chroma": 0.1}},
                                  {"type": "temperature", "params": {"kelvinShift": 400, "tint": -0.1}}],
                         overlays=[ov(opacity=0.8, blend="screen", z=2, faces="largest")],
                         data=[{"type": "speed"}]),
                      {"look.cube": cube(), "thumb.png": png(512, 512), "a.png": SMALL}, "valid", []),
    "valid/v4-string-lut": (v4(lut="look.cube"), {"look.cube": cube()}, "valid", []),
    "valid/v4-subdirectory": (v4(overlays=[ov("stickers/a.png", faces=2)]),
                              {"stickers/a.png": SMALL}, "valid", []),
    "valid/v4-budget-at-limit": (v4(overlays=[ov(f"o{i}.png") for i in range(8)]),
                                 {f"o{i}.png": png(2000, 2000) for i in range(8)}, "valid", []),
    "valid/v4-unknown-effect-skipped": (v4(effects=[{"type": "bloom"}, {"type": "splitTone"}]),
                                        {}, "valid", []),
    # ---------------------------------------------------------------- invalid: paths
    "invalid/path-traversal": ({"name": "Escape", "lut": "../outside.cube"}, {}, "invalid", ["path.unsafe"]),
    "invalid/path-absolute": ({"name": "Abs", "overlays": [ov("/etc/hosts")]}, {}, "invalid", ["path.unsafe"]),
    "invalid/path-too-deep": (v4(overlays=[ov("a/b/c.png")]), {"a/b/c.png": SMALL}, "invalid", ["path.unsafe"]),
    "invalid/path-dotdot-inside": (v4(overlays=[ov("stickers/../a.png")]), {"a.png": SMALL},
                                   "invalid", ["path.unsafe"]),
    "invalid/path-backslash": (v4(thumbnail="..\\thumb.png"), {}, "invalid", ["path.unsafe"]),
    # ---------------------------------------------------------------- invalid: budgets
    "invalid/budget-overlay-count": (v4(overlays=[ov() for _ in range(9)]), {"a.png": SMALL},
                                     "invalid", ["budget.overlays"]),
    "invalid/budget-pack-pixels": (v4(overlays=[ov(f"o{i}.png") for i in range(8)],
                                      triggers=[{"blendshape": "smile", "overlay": ov("t.png")}]),
                                   dict({f"o{i}.png": png(2000, 2000) for i in range(8)}, **{"t.png": png(2000, 2000)}),
                                   "invalid", ["budget.packPixels"]),
    "invalid/budget-legacy-pack-pixels": ({"name": "Heavy", "overlays": [ov(f"o{i}.png") for i in range(8)],
                                           "meshTexture": "m.png"},
                                          dict({f"o{i}.png": png(2000, 2000) for i in range(8)}, **{"m.png": png(1000, 1000)}),
                                          "invalid", ["budget.packPixels"]),
    "invalid/budget-animated-frame": (v4(overlays=[ov(frames=["b.png"])]),
                                      {"a.png": png(1100, 1000), "b.png": png(1100, 1000)},
                                      "invalid", ["budget.framePixels"]),
    "invalid/budget-image-pixels": (v4(overlays=[ov()]), {"a.png": png(2001, 2000)},
                                    "invalid", ["budget.imagePixels"]),
    "invalid/budget-frames": (v4(overlays=[ov(frames=["a.png"] * 24)]), {"a.png": png(8, 8)},
                              "invalid", ["budget.frames"]),
    "invalid/budget-effects": (v4(effects=[{"type": "fade"}] * 17), {}, "invalid", ["budget.effects"]),
    "invalid/budget-triggers": (v4(triggers=[{"blendshape": "blink", "overlay": ov()}] * 9), {"a.png": SMALL},
                                "invalid", ["budget.triggers"]),
    "invalid/budget-data": (v4(data=[{"type": "speed"}] * 5), {}, "invalid", ["budget.data"]),
    "invalid/trigger-image-too-large": (v4(triggers=[{"blendshape": "smile", "overlay": ov()}]),
                                        {"a.png": png(2500, 2000)}, "invalid", ["budget.imagePixels"]),
    # ---------------------------------------------------------------- invalid: manifest
    "invalid/v4-missing-id": ({"lenspack": 4, "version": "1.0.0", "name": "No Id",
                               "effects": [{"type": "fade"}]}, {}, "invalid", ["manifest.id"]),
    "invalid/v4-bad-id": (v4(id="Sunset Fade", effects=[{"type": "fade"}]), {}, "invalid", ["manifest.id"]),
    "invalid/v4-bad-version": (v4(version="1.0", effects=[{"type": "fade"}]), {}, "invalid", ["manifest.version"]),
    "invalid/v4-bad-license": (v4(license="MIT; rm -rf", effects=[{"type": "fade"}]), {}, "invalid",
                               ["manifest.license"]),
    "invalid/v4-bad-localized": (v4(localized={"French": {"name": "x"}}, effects=[{"type": "fade"}]), {},
                                 "invalid", ["manifest.localized"]),
    "invalid/v4-malformed-effect": (v4(effects=[{"type": "bloom", "intensity": "high"}]), {}, "invalid",
                                    ["manifest.field"]),
    "invalid/v4-malformed-overlay": (v4(overlays=[ov(blend="dodge")]), {"a.png": SMALL}, "invalid",
                                     ["manifest.field"]),
    "invalid/v4-param-out-of-range": (v4(effects=[{"type": "grain", "params": {"size": 0.5}}]), {}, "invalid",
                                      ["effect.param"]),
    "invalid/v4-missing-asset": (v4(overlays=[ov("gone.png")]), {}, "invalid", ["asset.missing"]),
    "invalid/v4-not-png": (v4(overlays=[ov("a.jpg")]), {"a.jpg": b"\xff\xd8\xff\xe0not a png"}, "invalid",
                           ["asset.notPNG"]),
    "invalid/v4-thumbnail-too-large": (v4(thumbnail="t.png", effects=[{"type": "fade"}]), {"t.png": png(600, 600)},
                                       "invalid", ["thumbnail.size"]),
    "invalid/v4-bad-lut-input": (v4(lut={"file": "look.cube", "input": "rec2020"}), {"look.cube": cube()},
                                 "invalid", ["lut.space"]),
    "invalid/lenspack-string": ({"lenspack": "4", "name": "Str", "effects": [{"type": "fade"}]}, {}, "invalid",
                                ["manifest.lenspack"]),
    "invalid/bad-cube": ({"name": "Broken", "lut": "look.cube"}, {"look.cube": b"LUT_3D_SIZE 2\n0 0 0\n"},
                         "invalid", ["lut.invalid"]),
    "invalid/empty": ({"name": "Nothing"}, {}, "invalid", ["content.empty"]),
    "invalid/no-name": ({"effects": [{"type": "fade"}]}, {}, "invalid", ["manifest.name"]),
    "invalid/bad-json": (None, {"manifest.json": b"{\"name\": "}, "invalid", ["manifest.json"]),
    "invalid/no-manifest": (None, {"look.cube": cube()}, "invalid", ["manifest.missing"]),
    # ---------------------------------------------------------------- revision 2 (valid)
    "valid/v4-rev2-pose-stage": (v4(required=["overlays", "overlayPose", "overlayStage", "overlayBehind"],
                                    overlays=[ov(pose="full", stage="scene", behindPerson=True),
                                              ov(anchor="eyes", pose="screen", stage="top"),
                                              ov(anchor="chin", pose="roll", behindPerson=False)]),
                                 {"a.png": SMALL}, "valid", []),
    "valid/v4-rev2-variants": (v4(required=["overlayVariants"],
                                  overlays=[ov(variants=["b.png", "c.png"], faces=3)]),
                               {"a.png": SMALL, "b.png": SMALL, "c.png": SMALL}, "valid", []),
    "valid/v4-rev2-anchors": (v4(required=["faceAnchors"],
                                 overlays=[ov(anchor=a) for a in ("leftEye", "rightEye", "leftCheek",
                                                                   "rightCheek", "head", "face")]),
                              {"a.png": SMALL}, "valid", []),
    "valid/v4-rev2-blend-extended": (v4(required=["overlayBlendExtended"],
                                        overlays=[ov(blend="overlay"), ov(blend="softLight", opacity=0.5)],
                                        triggers=[{"blendshape": "smile", "overlay": ov(blend="softLight")}]),
                                     {"a.png": SMALL}, "valid", []),
    "valid/v4-rev2-triggers": (v4(required=["triggerModes", "triggerShapes2"],
                                  triggers=[{"blendshape": "wink", "mode": "toggle", "overlay": ov()},
                                            {"blendshape": "kiss", "mode": "once", "overlay": ov(anchor="mouth")},
                                            {"blendshape": "tongueOut", "overlay": ov(anchor="mouth")},
                                            {"blendshape": "cheekPuff", "mode": "while", "overlay": ov()}]),
                               {"a.png": SMALL}, "valid", []),
    "valid/v4-rev2-face-paint": (v4(required=["facePaint"],
                                    facePaint={"image": "paint.png", "opacity": 0.8, "blend": "multiply",
                                               "faces": "largest"}),
                                 {"paint.png": png(2000, 2000)}, "valid", []),
    "valid/v4-rev2-face-paint-animated": (v4(facePaint={"image": "p0.png", "frames": [f"p{i}.png" for i in range(1, 8)],
                                                        "fps": 12, "blend": "softLight"}),
                                          {f"p{i}.png": png(1000, 1000) for i in range(8)}, "valid", []),
    "valid/v4-rev2-retouch": (v4(required=["retouch"], retouch={"skinSmoothing": 0.6, "slimFace": 1}),
                              {}, "valid", []),
    "valid/v4-rev2-background-blur": (v4(required=["background"], background={"mode": "blur", "amount": 0.4}),
                                      {}, "valid", []),
    "valid/v4-rev2-background-image": (v4(background={"mode": "image", "image": "bg.png", "fit": "fit"},
                                          overlays=[ov()]),
                                       {"bg.png": png(2000, 2000), "a.png": SMALL}, "valid", []),
    "valid/v4-rev2-skin-protect": (v4(required=["skinProtect"], skinProtect=0.7, lut="look.cube"),
                                   {"look.cube": cube()}, "valid", []),
    "valid/v4-rev2-remix-of": (v4(remixOf={"id": "@someone/golden-crown", "version": "1.2.0"},
                                  effects=[{"type": "fade"}]), {}, "valid", []),
    "valid/legacy-rev2-fields-ignored": ({"name": "Old Paint", "lut": "look.cube", "facePaint": {"image": "x.png"},
                                          "retouch": {"skinSmoothing": 9}, "skinProtect": "lots",
                                          "overlays": [ov(pose="sideways", variants=[])]},
                                         {"look.cube": cube(), "a.png": SMALL}, "valid", []),
    # ---------------------------------------------------------------- revision 2 (invalid)
    "invalid/required-missing-blend": (v4(overlays=[ov(blend="overlay")]), {"a.png": SMALL},
                                       "invalid", ["required.missing"]),
    "invalid/required-missing-trigger-blend": (v4(triggers=[{"blendshape": "blink", "overlay": ov(blend="softLight")}]),
                                               {"a.png": SMALL}, "invalid", ["required.missing"]),
    "invalid/v4-bad-pose": (v4(overlays=[ov(pose="tilted")]), {"a.png": SMALL}, "invalid", ["manifest.field"]),
    "invalid/v4-bad-stage": (v4(overlays=[ov(stage="under")]), {"a.png": SMALL}, "invalid", ["manifest.field"]),
    "invalid/v4-bad-behind-person": (v4(overlays=[ov(behindPerson="yes")]), {"a.png": SMALL}, "invalid",
                                     ["manifest.field"]),
    "invalid/v4-bad-trigger-mode": (v4(triggers=[{"blendshape": "smile", "mode": "always", "overlay": ov()}]),
                                    {"a.png": SMALL}, "invalid", ["manifest.field"]),
    "invalid/v4-variants-with-frames": (v4(overlays=[ov(frames=["b.png"], variants=["c.png"])]),
                                        {"a.png": SMALL, "b.png": SMALL, "c.png": SMALL}, "invalid",
                                        ["manifest.field"]),
    "invalid/v4-variants-empty": (v4(overlays=[ov(variants=[])]), {"a.png": SMALL}, "invalid", ["manifest.field"]),
    "invalid/budget-variants": (v4(overlays=[ov(variants=["a.png"] * 8)]), {"a.png": SMALL}, "invalid",
                                ["budget.variants"]),
    "invalid/budget-variant-pixels": (v4(overlays=[ov(f"o{i}.png", variants=[f"v{i}.png"]) for i in range(5)]),
                                      dict({f"o{i}.png": png(2000, 2000) for i in range(5)},
                                           **{f"v{i}.png": png(2000, 2000) for i in range(5)}),
                                      "invalid", ["budget.packPixels"]),
    "invalid/budget-face-paint-frames": (v4(facePaint={"image": "p.png", "frames": ["p.png"] * 8}), {"p.png": SMALL},
                                         "invalid", ["budget.frames"]),
    "invalid/budget-face-paint-frame-pixels": (v4(facePaint={"image": "p.png", "frames": ["q.png"]}),
                                               {"p.png": png(1001, 1000), "q.png": SMALL}, "invalid",
                                               ["budget.framePixels"]),
    "invalid/v4-face-paint-bad-blend": (v4(facePaint={"image": "p.png", "blend": "add"}), {"p.png": SMALL},
                                        "invalid", ["manifest.field"]),
    "invalid/v4-face-paint-and-mesh": (v4(facePaint={"image": "p.png"}, meshTexture="p.png"), {"p.png": SMALL},
                                       "invalid", ["manifest.field"]),
    "invalid/v4-retouch-over-cap": (v4(retouch={"skinSmoothing": 0.7}), {}, "invalid", ["value.range"]),
    "invalid/v4-retouch-missing-amount": (v4(retouch={"slimFace": 1}, effects=[{"type": "fade"}]), {}, "invalid",
                                          ["manifest.field"]),
    "invalid/v4-background-bad-mode": (v4(background={"mode": "sky"}), {}, "invalid", ["manifest.field"]),
    "invalid/v4-background-amount-range": (v4(background={"mode": "blur", "amount": 1.5}), {}, "invalid",
                                           ["value.range"]),
    "invalid/v4-background-bad-fit": (v4(background={"mode": "image", "image": "bg.png", "fit": "stretch"}),
                                      {"bg.png": SMALL}, "invalid", ["manifest.field"]),
    "invalid/v4-background-image-missing": (v4(background={"mode": "image", "image": "bg.png"}), {}, "invalid",
                                            ["asset.missing"]),
    "invalid/budget-background-pixels": (v4(background={"mode": "image", "image": "bg.png"}), {"bg.png": png(2001, 2000)},
                                         "invalid", ["budget.imagePixels"]),
    "invalid/v4-skin-protect-range": (v4(skinProtect=2, lut="look.cube"), {"look.cube": cube()}, "invalid",
                                      ["value.range"]),
    "invalid/v4-bad-remix-of": (v4(remixOf={"id": "golden crown"}, effects=[{"type": "fade"}]), {}, "invalid",
                                ["manifest.remixOf"]),
    # ---------------------------------------------------------------- needs a newer reader
    "invalid/needs-newer-format": ({"lenspack": 5, "id": "@x/y", "version": "1.0.0", "name": "Future",
                                    "hologram": {"x": 1}}, {}, "needs-newer", ["format.newer"]),
    "invalid/needs-newer-feature": (v4(required=["effects", "teleport"], effects=[{"type": "fade"}]), {},
                                    "needs-newer", ["required.unknown"]),
}


def main():
    if os.path.isdir(ROOT):
        shutil.rmtree(ROOT)
    expect = {}
    for key, (manifest, files, result, codes) in sorted(CASES.items()):
        folder = os.path.join(ROOT, key + ".lenspack")
        os.makedirs(folder)
        if manifest is not None:
            with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, sort_keys=True)
                f.write("\n")
        for rel, data in files.items():
            dest = os.path.join(folder, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
        expect[key + ".lenspack"] = {"result": result, "codes": codes}
    with open(os.path.join(ROOT, "expect.json"), "w", encoding="utf-8") as f:
        json.dump(expect, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {len(expect)} cases")


if __name__ == "__main__":
    main()
