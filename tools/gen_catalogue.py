#!/usr/bin/env python3
#
# Copyright (c) 2026 Bubble Labs.
# Licensed under the Apache License, Version 2.0. See LICENSE-TOOLING.md.
#
"""Generates the starter catalogue in packs/: every PNG drawn here in code, every cube computed.

    python3 tools/gen_catalogue.py          # rewrite packs/ for the looks below (needs Pillow)
    python3 tools/build_index.py            # then rebuild dist/ and index.json

Nothing in these packs is traced, sampled or derived from anyone else's art or LUTs, and nothing
depicts a trademarked character: crowns, sparkles, glasses, a halo, a moustache, blush and
confetti are drawn from circles, polygons and gradients below, and the grades are small
original formulas. The packs are dedicated to the public domain (CC0-1.0) except where a look
says otherwise.

The four `@lens/…` face looks are also built into the Lens app (Resources/BundledLooks.bundle),
so the face catalogue is never empty on a fresh install; the app's copies are these folders.

Pillow is a dependency of this generator only. The validator, the CLI and CI need nothing.
"""
import json
import math
import os
import shutil
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, ROOT)
from lenspack import reference as ref  # noqa: E402

PACKS = os.path.join(ROOT, "packs")
SS = 4  # supersampling for every drawing


# ---------------------------------------------------------------------------------------------
# Drawing helpers


def canvas(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def finish(img, w, h):
    return img.resize((w, h), Image.LANCZOS)


def vertical_gradient(w, h, top, bottom):
    g = Image.new("RGBA", (w, h))
    px = g.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(round(top[i] + (bottom[i] - top[i]) * t)) for i in range(4))
        for x in range(w):
            px[x, y] = c
    return g


def fill_with(shape_mask, fill):
    """`fill` (an RGBA image) where `shape_mask` (L) is set."""
    out = Image.new("RGBA", fill.size, (0, 0, 0, 0))
    out.paste(fill, (0, 0), shape_mask)
    return out


def glow(img, radius, strength=1.0):
    blurred = img.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        a = blurred.getchannel("A").point(lambda v: min(255, int(v * strength)))
        blurred.putalpha(a)
    return Image.alpha_composite(blurred, img)


# ---------------------------------------------------------------------------------------------
# The art


def crown():
    w, h = 640, 320
    W, H = w * SS, h * SS
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    base, top = H * 0.86, H * 0.18
    pts = [(W * 0.08, base), (W * 0.08, H * 0.42), (W * 0.27, H * 0.58), (W * 0.5, top),
           (W * 0.73, H * 0.58), (W * 0.92, H * 0.42), (W * 0.92, base)]
    d.polygon(pts, fill=255)
    for (x, y) in [(W * 0.08, H * 0.40), (W * 0.5, top - H * 0.02), (W * 0.92, H * 0.40)]:
        r = H * 0.075
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    gold = vertical_gradient(W, H, (255, 226, 140, 255), (196, 132, 40, 255))
    art = fill_with(mask, gold)
    d2 = ImageDraw.Draw(art)
    # A band and three gems.
    d2.rectangle([W * 0.08, H * 0.72, W * 0.92, H * 0.86], fill=(176, 112, 30, 255))
    for i, x in enumerate((0.3, 0.5, 0.7)):
        r = H * 0.045
        cx, cy = W * x, H * 0.79
        colour = [(214, 64, 86, 255), (60, 140, 200, 255), (214, 64, 86, 255)][i]
        d2.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour)
        d2.ellipse([cx - r * 0.35, cy - r * 0.55, cx + r * 0.05, cy - r * 0.15], fill=(255, 255, 255, 170))
    # A thin highlight down the left of each spire.
    d2.line([(W * 0.12, H * 0.66), (W * 0.27, H * 0.62)], fill=(255, 245, 210, 200), width=SS * 3)
    d2.line([(W * 0.46, H * 0.30), (W * 0.5, H * 0.22)], fill=(255, 245, 210, 200), width=SS * 3)
    return finish(glow(art, SS * 6, 0.35), w, h)


def sparkle(scale=1.0, turn=0.0):
    w = h = 256
    W, H = w * SS, h * SS
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(art)
    cx, cy = W / 2, H / 2
    pts = []
    for k in range(16):
        ang = turn + k * math.pi / 8
        rad = (W * 0.42 if k % 4 == 0 else W * 0.16 if k % 2 == 0 else W * 0.08) * scale
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.polygon(pts, fill=(255, 250, 225, 255))
    r = W * 0.05 * scale
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))
    for (dx, dy, rr) in [(0.28, -0.22, 0.025), (-0.3, 0.25, 0.02), (0.22, 0.3, 0.015)]:
        x, y, q = cx + W * dx * scale, cy + H * dy * scale, W * rr
        d.ellipse([x - q, y - q, x + q, y + q], fill=(255, 236, 190, 230))
    return finish(glow(art, SS * 8, 0.8), w, h)


def shades():
    w, h = 768, 256
    W, H = w * SS, h * SS
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lens = vertical_gradient(W, H, (40, 70, 80, 235), (110, 70, 60, 215))
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    r = H * 0.40
    centres = [(W * 0.27, H * 0.52), (W * 0.73, H * 0.52)]
    for (x, y) in centres:
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    art = fill_with(mask, lens)
    d2 = ImageDraw.Draw(art)
    rim = (214, 170, 92, 255)
    for (x, y) in centres:
        d2.ellipse([x - r, y - r, x + r, y + r], outline=rim, width=SS * 7)
        # A soft reflection across the top-left of each lens.
        d2.arc([x - r * 0.75, y - r * 0.75, x + r * 0.75, y + r * 0.75], 200, 250,
               fill=(255, 255, 255, 120), width=SS * 6)
    d2.arc([W * 0.42, H * 0.30, W * 0.58, H * 0.60], 200, 340, fill=rim, width=SS * 7)
    d2.line([(W * 0.27 - r, H * 0.45), (W * 0.02, H * 0.38)], fill=rim, width=SS * 7)
    d2.line([(W * 0.73 + r, H * 0.45), (W * 0.98, H * 0.38)], fill=rim, width=SS * 7)
    return finish(art, w, h)


def halo():
    w, h = 768, 256
    W, H = w * SS, h * SS
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(art)
    box = [W * 0.1, H * 0.22, W * 0.9, H * 0.8]
    d.ellipse(box, outline=(255, 226, 170, 255), width=SS * 26)
    inner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(inner).ellipse([b + (SS * 9 if i < 2 else -SS * 9) for i, b in enumerate(box)],
                                  outline=(255, 252, 238, 255), width=SS * 8)
    art = Image.alpha_composite(art, inner)
    return finish(glow(glow(art, SS * 10, 1.0), SS * 26, 0.9), w, h)


def moustache():
    """Two brush strokes: a circle swept along a curve that sweeps up into a curl, thinning as it
    goes."""
    w, h = 512, 192
    W, H = w * SS, h * SS
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    for side in (-1, 1):
        for k in range(301):
            t = k / 300
            x = 0.5 + side * (0.015 + 0.44 * t)
            y = 0.42 + 0.16 * math.sin(math.pi * min(1.0, t * 1.25)) - 0.32 * max(0.0, t - 0.7) ** 1.5 * 3
            r = (0.17 * (1 - t) ** 0.9 + 0.012) * H
            cx, cy = W * x, H * y
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    paper = vertical_gradient(W, H, (86, 58, 40, 255), (44, 28, 20, 255))
    return finish(fill_with(mask.filter(ImageFilter.GaussianBlur(SS * 0.75)), paper), w, h)


def blush():
    w, h = 256, 192
    W, H = w * SS, h * SS
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(art).ellipse([W * 0.15, H * 0.2, W * 0.85, H * 0.8], fill=(232, 120, 132, 200))
    return finish(art.filter(ImageFilter.GaussianBlur(SS * 22)), w, h)


def confetti(frame):
    w = h = 512
    W, H = w * SS, h * SS
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(art)
    colours = [(242, 92, 84, 255), (247, 192, 66, 255), (88, 178, 154, 255), (96, 140, 222, 255), (230, 230, 240, 255)]
    spread = 0.12 + 0.11 * frame
    for k in range(28):
        ang = k * 2.39996 + frame * 0.15
        dist = spread * (0.45 + 0.55 * ((k * 37) % 11) / 10)
        x, y = W * (0.5 + dist * math.cos(ang)), H * (0.5 + dist * math.sin(ang) + 0.02 * frame * frame)
        s = W * 0.018
        rot = ang * 2 + frame
        quad = [(x + s * math.cos(rot + q * math.pi / 2) * (1.8 if q % 2 else 0.8),
                 y + s * math.sin(rot + q * math.pi / 2) * (1.8 if q % 2 else 0.8)) for q in range(4)]
        d.polygon(quad, fill=colours[k % len(colours)])
    return finish(art, w, h)


# ---------------------------------------------------------------------------------------------
# Grades (original formulas, sampled into cubes)


def clamp01(v):
    return min(1.0, max(0.0, v))


def luma(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def mix(a, b, t):
    return a + (b - a) * t


def s_curve(v, k):
    return clamp01(0.5 + (v - 0.5) * (1 + k) - 4 * k * (v - 0.5) ** 3)


def grade_gold(r, g, b):
    y = luma(r, g, b)
    return [clamp01(s_curve(r, 0.08) * 1.04 + 0.02), clamp01(s_curve(g, 0.08) * 0.99 + 0.01),
            clamp01(mix(s_curve(b, 0.08) * 0.88, y * 0.9, 0.1))]


def grade_lavender(r, g, b):
    return [clamp01(r * 0.97 + 0.03), clamp01(g * 0.95 + 0.025), clamp01(b * 1.0 + 0.05)]


def grade_summer(r, g, b):
    y = luma(r, g, b)
    sat = 1.15
    return [clamp01(y + (r - y) * sat + 0.02), clamp01(y + (g - y) * sat), clamp01(y + (b - y) * sat - 0.02)]


def grade_halo(r, g, b):
    return [clamp01(r * 0.92 + 0.08), clamp01(g * 0.92 + 0.07), clamp01(b * 0.9 + 0.09)]


def grade_paper(r, g, b):
    y = luma(r, g, b)
    return [clamp01(mix(r, y, 0.45) * 0.9 + 0.08), clamp01(mix(g, y, 0.45) * 0.88 + 0.07),
            clamp01(mix(b, y, 0.45) * 0.8 + 0.06)]


def grade_teal(r, g, b):
    y = luma(r, g, b)
    shadow, light = 1 - y, y
    return [clamp01(s_curve(r, 0.12) + 0.06 * light - 0.05 * shadow),
            clamp01(s_curve(g, 0.12) + 0.01 * light + 0.02 * shadow),
            clamp01(s_curve(b, 0.12) - 0.07 * light + 0.07 * shadow)]


def grade_night(r, g, b):
    y = luma(r, g, b)
    return [clamp01(s_curve(r, 0.18) * 1.03 + 0.04 * y), clamp01(s_curve(g, 0.18) * 0.97),
            clamp01(s_curve(b, 0.18) * 0.9 + 0.03 * (1 - y))]


def grade_mono(r, g, b):
    y = s_curve(luma(r, g, b), 0.22)
    return [clamp01(y * 1.01), clamp01(y), clamp01(y * 0.97 + 0.01)]


def grade_log_daylight(r, g, b):
    """Apple Log (BT.2020) → Rec.709: decode, a gentle filmic shoulder, re-encode."""
    to709 = ref.conversion("bt2020", "bt709")
    lin = ref.mat_vec(to709, [ref.apple_log_decode(r), ref.apple_log_decode(g), ref.apple_log_decode(b)])

    def shoulder(x):
        x = max(0.0, x) * 1.6
        return x / (1 + x) * 1.12
    return [clamp01(ref.bt709_encode(clamp01(shoulder(v)))) for v in lin]


def grade_garden(r, g, b):
    """On Display P3 values: lush, slightly cooled greens; warm skin untouched."""
    y = luma(r, g, b)
    green = max(0.0, g - max(r, b))
    return [clamp01(r - 0.04 * green), clamp01(g + 0.08 * green + 0.01), clamp01(b + 0.02 * green + 0.01 * (1 - y))]


def cube(fn, size=17, title="look"):
    return ref.cube_text(size, fn, title)


# ---------------------------------------------------------------------------------------------
# Thumbnails: the look on a neutral reference — a grey studio backdrop and a plain head shape.


def reference_scene(size=256):
    W = size * SS
    img = vertical_gradient(W, W, (170, 170, 168, 255), (92, 92, 90, 255))
    d = ImageDraw.Draw(img)
    d.ellipse([W * 0.12, W * 0.78, W * 0.88, W * 1.35], fill=(120, 124, 132, 255))         # shoulders
    d.rectangle([W * 0.42, W * 0.62, W * 0.58, W * 0.84], fill=(196, 170, 150, 255))        # neck
    d.ellipse([W * 0.3, W * 0.2, W * 0.7, W * 0.7], fill=(208, 182, 160, 255))              # face
    d.ellipse([W * 0.28, W * 0.12, W * 0.72, W * 0.42], fill=(70, 56, 48, 255))             # hair
    d.ellipse([W * 0.32, W * 0.24, W * 0.68, W * 0.5], fill=(208, 182, 160, 255))
    for x in (0.42, 0.58):
        d.ellipse([W * (x - 0.025), W * 0.42, W * (x + 0.025), W * 0.46], fill=(60, 48, 44, 255))
    d.arc([W * 0.44, W * 0.52, W * 0.56, W * 0.6], 20, 160, fill=(150, 90, 84, 255), width=SS * 3)
    return img.resize((size, size), Image.LANCZOS)


# Where each anchor sits on the reference head, as (x, y, face width) in thumbnail fractions.
ANCHOR = {"forehead": (0.5, 0.25), "head": (0.5, 0.13), "eyes": (0.5, 0.44), "mouth": (0.5, 0.56),
          "leftCheek": (0.39, 0.52), "rightCheek": (0.61, 0.52), "face": (0.5, 0.5)}
FACE_WIDTH = 0.4


def thumbnail(look, size=256):
    img = reference_scene(size)
    grade = look.get("grade")
    if grade and not look.get("logInput"):
        px = img.load()
        for y in range(size):
            for x in range(size):
                r, g, b, a = px[x, y]
                out = grade(r / 255, g / 255, b / 255)
                px[x, y] = tuple(int(round(v * 255)) for v in out) + (a,)
    # Triggers are shown fired, so the thumbnail says what the look does.
    for ov in look.get("overlays", []) + [dict(t["overlay"], image=(t["overlay"].get("frames") or [t["overlay"]["image"]])[-1])
                                          for t in look.get("triggers", [])]:
        art = look["art"][ov["image"]]
        width = int(size * FACE_WIDTH * ov.get("scale", 1))
        height = max(1, int(art.height * width / art.width))
        sticker = art.resize((width, height), Image.LANCZOS)
        if "opacity" in ov:
            sticker.putalpha(sticker.getchannel("A").point(lambda v, o=ov["opacity"]: int(v * o)))
        ax, ay = ANCHOR.get(ov["anchor"], (0.5, 0.45))
        ay -= ov.get("offsetY", 0) * FACE_WIDTH
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        layer.paste(sticker, (int(size * ax - width / 2), int(size * ay - height / 2)), sticker)
        if ov.get("behindPerson"):
            # Behind the person: the head is cut out of the layer, as the person matte would.
            mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(mask).ellipse([size * 0.28, size * 0.12, size * 0.72, size * 0.7], fill=255)
            layer.paste((0, 0, 0, 0), (0, 0), mask)
        img = Image.alpha_composite(img, layer)
    return img


# ---------------------------------------------------------------------------------------------
# The catalogue

CC0 = "CC0-1.0"


def looks():
    sparkles = [sparkle(1.0, 0.0), sparkle(0.82, 0.25), sparkle(0.92, 0.5)]
    burst = [confetti(f) for f in range(4)]
    return [
        # ----------------------------------------------------- bundled face looks (@lens)
        dict(id="@lens/gold-leaf-crown", name="Gold Leaf Crown", license=CC0,
             summary="A drawn gold crown, a warm grade and a little glow.",
             localized={"fr": {"name": "Couronne feuille d'or"}, "es": {"name": "Corona de pan de oro"}},
             art={"crown.png": crown()}, grade=grade_gold,
             overlays=[{"image": "crown.png", "anchor": "forehead", "scale": 1.25, "offsetY": 0.12}],
             effects=[{"type": "bloom", "intensity": 0.25}], required=["overlays"]),
        dict(id="@lens/starlit-cheeks", name="Starlit Cheeks", license=CC0,
             summary="Twinkling stars on both cheeks and a soft lavender cast.",
             localized={"fr": {"name": "Joues étoilées"}, "es": {"name": "Mejillas estrelladas"}},
             art={"star1.png": sparkles[0], "star2.png": sparkles[1], "star3.png": sparkles[2]}, grade=grade_lavender,
             overlays=[{"image": "star1.png", "frames": ["star2.png", "star3.png"], "fps": 6, "anchor": "leftCheek",
                        "scale": 0.32, "blend": "screen"},
                       {"image": "star2.png", "frames": ["star3.png", "star1.png"], "fps": 6, "anchor": "rightCheek",
                        "scale": 0.28, "blend": "screen"}],
             effects=[{"type": "grain", "intensity": 0.2, "params": {"size": 0.0012, "roughness": 0.4}}],
             required=["overlays"]),
        dict(id="@lens/round-shades", name="Round Shades", license=CC0,
             summary="Round gold-rimmed sunglasses that turn with your head, on a bright summer grade.",
             localized={"fr": {"name": "Lunettes rondes"}, "es": {"name": "Gafas redondas"}},
             art={"shades.png": shades()}, grade=grade_summer,
             overlays=[{"image": "shades.png", "anchor": "eyes", "scale": 1.05, "pose": "full"}],
             effects=[{"type": "vignette", "intensity": 0.35, "params": {"midpoint": 0.55, "feather": 0.6}}],
             required=["overlays"]),
        dict(id="@lens/soft-halo", name="Soft Halo", license=CC0,
             summary="A glowing ring behind your head, pastel light, skin kept true.",
             localized={"fr": {"name": "Halo doux"}, "es": {"name": "Halo suave"}},
             art={"halo.png": halo()}, grade=grade_halo,
             overlays=[{"image": "halo.png", "anchor": "head", "scale": 1.3, "opacity": 0.9, "blend": "screen",
                        "behindPerson": True}],
             effects=[{"type": "bloom", "intensity": 0.3, "params": {"threshold": 0.7, "radius": 0.02}}],
             skinProtect=0.5, required=["overlays"]),
        # ----------------------------------------------------- gallery face looks
        dict(id="@lenspack-spec/paper-moustache", name="Paper Moustache", license=CC0,
             summary="A cut-paper moustache and a faded, papery grade.",
             localized={"fr": {"name": "Moustache en papier"}},
             art={"moustache.png": moustache()}, grade=grade_paper,
             overlays=[{"image": "moustache.png", "anchor": "mouth", "scale": 0.72, "offsetY": 0.1}],
             effects=[{"type": "grain", "intensity": 0.25}], required=["overlays"]),
        dict(id="@lenspack-spec/rosy-blush", name="Rosy Blush", license=CC0,
             summary="A soft blush on both cheeks — colour, never reshaping.",
             art={"blush.png": blush()}, grade=None,
             overlays=[{"image": "blush.png", "anchor": "leftCheek", "scale": 0.36, "blend": "multiply", "opacity": 0.55},
                       {"image": "blush.png", "anchor": "rightCheek", "scale": 0.36, "blend": "multiply", "opacity": 0.55}],
             effects=[{"type": "fade", "intensity": 0.2}], required=["overlays"]),
        dict(id="@lenspack-spec/confetti-pop", name="Confetti Pop", license=CC0,
             summary="Open your mouth and confetti bursts out, once each time.",
             localized={"fr": {"name": "Pluie de confettis"}},
             art={f"confetti{i}.png": img for i, img in enumerate(burst)}, grade=grade_summer,
             triggers=[{"blendshape": "mouthOpen", "threshold": 0.55, "mode": "once",
                        "overlay": {"image": "confetti0.png", "frames": ["confetti1.png", "confetti2.png", "confetti3.png"],
                                    "fps": 10, "anchor": "mouth", "scale": 2.2}}],
             effects=[{"type": "saturation", "intensity": 0.6}], required=["triggers"]),
        # ----------------------------------------------------- colour and film looks
        dict(id="@lenspack-spec/harbour-teal", name="Harbour Teal", license=CC0,
             summary="Teal shadows, warm highlights, a firm contrast.", grade=grade_teal,
             localized={"fr": {"name": "Port sarcelle"}, "es": {"name": "Puerto turquesa"}},
             effects=[{"type": "grain", "intensity": 0.15, "params": {"size": 0.001, "roughness": 0.5}}],
             required=["lut"]),
        dict(id="@lenspack-spec/paper-matte", name="Paper Matte", license=CC0,
             summary="Lifted blacks, low contrast, fine grain, a touch warm.", grade=None,
             effects=[{"type": "fade", "intensity": 0.55}, {"type": "contrast", "intensity": 0.4},
                      {"type": "temperature", "intensity": 0.5, "params": {"kelvinShift": -350}},
                      {"type": "grain", "intensity": 0.35, "params": {"size": 0.0015, "roughness": 0.6, "chroma": 0.15}}],
             required=["effects"]),
        dict(id="@lenspack-spec/night-market", name="Night Market", license=CC0,
             summary="Warm neon highlights that bloom and halate; deep, clean shadows.", grade=grade_night,
             effects=[{"type": "bloom", "intensity": 0.45, "params": {"threshold": 0.75, "radius": 0.025}},
                      {"type": "halation", "intensity": 0.4, "params": {"threshold": 0.8, "radius": 0.012}}],
             required=["lut"]),
        dict(id="@lenspack-spec/silver-mono", name="Silver Mono", license=CC0,
             summary="Black and white with a silver sheen, fine grain and a feathered vignette.", grade=grade_mono,
             localized={"fr": {"name": "Argent mono"}},
             effects=[{"type": "grain", "intensity": 0.4, "params": {"size": 0.0012, "roughness": 0.55}},
                      {"type": "vignette", "intensity": 0.45, "params": {"midpoint": 0.5, "feather": 0.7}}],
             required=["lut"]),
        dict(id="@lenspack-spec/log-to-daylight", name="Log to Daylight", license=CC0,
             summary="For Apple Log footage: a gentle daylight rendering to Rec.709.", grade=grade_log_daylight,
             logInput=True, lut={"input": "apple-log", "output": "rec709-display"}, size=33,
             required=["lut", "lutInput"]),
        dict(id="@lenspack-spec/garden-p3", name="Garden P3", license=CC0,
             summary="Lush greens graded in Display P3, skin left alone.", grade=grade_garden,
             lut={"input": "p3-display", "output": "p3-display"}, required=["lut", "lutInput"]),
    ]


def write_look(look):
    pid = look["id"]
    folder = os.path.join(PACKS, pid[1:].replace("/", ".") + ".lenspack")
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    author = pid.split("/")[0]
    manifest = {"lenspack": 4, "id": pid, "version": "1.0.0", "name": look["name"], "author": author,
                "summary": look["summary"], "license": look["license"]}
    if look.get("localized"):
        manifest["localized"] = look["localized"]
    if look.get("required"):
        manifest["required"] = look["required"]
    if look.get("overlays") or look.get("triggers"):
        manifest["requires"] = ["faceTracking"]
    if look.get("grade"):
        size = look.get("size", 17)
        with open(os.path.join(folder, "look.cube"), "w", encoding="utf-8") as f:
            f.write(f"# {look['name']} — an original LensPack grade, {look['license']}\n")
            f.write(cube(look["grade"], size=size, title=look["name"]))
        manifest["lut"] = dict({"file": "look.cube"}, **look.get("lut", {}))
    for key in ("effects", "overlays", "triggers", "skinProtect"):
        if key in look:
            manifest[key] = look[key]
    for name, img in look.get("art", {}).items():
        img.save(os.path.join(folder, name), optimize=True)
    thumb = thumbnail(look)
    thumb.convert("RGB").save(os.path.join(folder, "thumb.png"), optimize=True)
    manifest["thumbnail"] = "thumb.png"
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return folder


def main(argv):
    only = set(argv[1:])
    written = [write_look(look) for look in looks() if not only or look["id"] in only]
    print(f"wrote {len(written)} pack(s) to packs/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
