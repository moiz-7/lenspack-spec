# LensPack Format Specification (v1–v3)

A **LensPack** is a community-authored look for the Lens camera app. Packs are **pure data —
never code**: no scripts, no shaders, no network access, no permissions. The app applies pack
content through its own audited implementation; each spec version widens the manifest's
*vocabulary*, never its *authority*.

## Two forms

1. **Bare cube** — a single `MyLook.cube` file. The look is named after the file.
2. **Pack folder** — `MyLook.lenspack/` containing `manifest.json` plus the assets it names.

Install location: **Files → Lens → LensPacks** (`Documents/LensPacks/`). Deleting the file
removes the look — the file system is the source of truth. Loading is silent: an invalid pack
is skipped and logged, never an alert.

## manifest.json

```json
{
  "name": "Party Crown",            // required, non-empty
  "author": "@you",                 // optional, shown as attribution
  "version": "1.0",                 // optional, informational
  "lut": "warm.cube",               // optional since v2 — color cube file in the folder
  "effects": [ ... ],               // optional, v3 — recipe nodes (see below)
  "overlays": [ ... ]               // optional, v2 — face-anchored images (see below)
}
```

A pack must contain at least one of `lut`, `effects`, `overlays`.
**Forward compatibility:** unknown effect types and unknown overlay anchors are *dropped
individually*, never fatal — author against a newer spec and older apps degrade gracefully.
Pipeline order in the app is fixed: **cube → effects → overlays**.

## v1 — Color cube (`lut`)

Adobe/Resolve `.cube` text format:
- `LUT_3D_SIZE N` with **2 ≤ N ≤ 65**; exactly N³ `r g b` float rows.
- `TITLE`, `DOMAIN_MIN`, `DOMAIN_MAX`, `#` comments allowed (ignored).
- 1D LUTs (`LUT_1D_SIZE`) are not supported.
- File ≤ **8 MB**.

## v2 — Face-anchored overlays (`overlays`)

```json
{ "image": "crown.png", "anchor": "forehead", "scale": 1.3, "offsetX": 0, "offsetY": 0.1 }
```

- `image` (required): PNG with alpha inside the pack folder, ≤ **4 megapixels**.
- `anchor` (required): `forehead` | `eyes` | `nose` | `mouth` | `chin`.
- `scale` (default 1.0): overlay width as a multiple of the detected face width, clamped 0.1–3.
- `offsetX`/`offsetY` (default 0): offsets in face-widths/heights (x right, y up), clamped ±1.
- `frames` (v2.2, default `[]`): additional PNG file names cycled after `image` (frame 0) —
  an animated overlay. Capped at 24 frames total; each frame ≤ 4 megapixels.
- `fps` (v2.2, default 8): animation rate, clamped 1–30 by the app.

The app anchors overlays to detected face landmarks (pupil-exact eyes, lip centroid, contour
chin; forehead extrapolated along the face axis) and rotates them to the head tilt. Every
face in frame gets the overlay.

## v3 — Recipe effects (`effects`)

```json
{ "type": "bloom", "intensity": 0.4 }
```

- `type` (required): `bloom` | `halation` | `grain` | `vignette` | `saturation` | `contrast` | `temperature` | `fade` | `sharpen` (v3.1).
- `intensity` (default 0.5): normalized **0–1**, clamped by the app.
  For the bipolar nodes — `saturation`, `contrast`, `temperature` — **0.5 is neutral**
  (saturation 0→greyscale, 1→2×; contrast maps to 0.75–1.25; temperature maps to 3500K–9500K).
- Effects apply in the order listed. The app guarantees the image extent never changes.

## v5 — Filter Studio (`meshTexture`, `triggers`, `requires`)

Rendered in the app's ARKit **Filter Studio** (TrueDepth devices): a tracked face mesh +
52 expression blendshapes at 60 fps.

- `meshTexture` (optional): PNG in ARKit face-mesh **UV space** (≤ 4 MP) — face paint that
  follows the skin. Regular `overlays` also render in 3D there (anchored planes that turn
  with the head).
- `triggers` (optional): expression-triggered overlays:
  ```json
  {"blendshape": "mouthOpen", "threshold": 0.6,
   "overlay": {"image": "fire.png", "anchor": "mouth", "scale": 2.0}}
  ```
  `blendshape`: `mouthOpen` | `smile` | `browsUp` | `blink`. `threshold` (default 0.5) is the
  0–1 expression coefficient at which the overlay appears (hysteresis applied). Unknown
  blendshape names drop lossily.
- `requires` (optional): hardware the pack is designed for — `"depth"`, `"faceTracking"`.
  **Labels only**: the app installs and runs the pack regardless, degrading gracefully, but
  every surface shows what a device can't unlock. Unknown strings read as unmet.

## Integrity (marketplace distribution)

Packs listed in the curated `index.json` carry a lowercase-hex **SHA-256** of the file; the
app verifies size → checksum → structural parse before install, over HTTPS only.
(Signature-chain verification is a planned index v2 field: `signature`, Ed25519 over the
file digest — reserved, not yet enforced.)

## Validation

Run the validator before publishing:

```
python3 validator/validate_lenspack.py "examples/Sunset Fade.cube"
python3 validator/validate_lenspack.py examples/party-crown.lenspack
```
