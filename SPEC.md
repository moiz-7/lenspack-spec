# LensPack Format Specification (format 4)

A **LensPack** is a community-authored look for the Lens camera app. A pack is **pure data,
never code**: no scripts, no shaders, no network access, no permissions. The app applies pack
content through its own audited implementation. Each format version widens the manifest's
*vocabulary*, never its *authority*.

One pack can carry any combination of:

| Content | Field | Since |
|---|---|---|
| A colour grade (3D LUT) | `lut` | v1 |
| Face-anchored stickers, optionally animated | `overlays` | v2 |
| Film effects (bloom, grain, …) | `effects` | v3 |
| Live data readouts (elevation, speed) | `data` | v3.1 |
| Face paint on the AR face mesh, expression triggers | `meshTexture`, `triggers` | Filter Studio |
| Identity, versioning, licence, colour spaces, packaging | `lenspack`, `id`, `version`, … | **v4** |

The machine-readable sources of truth sit next to this document:

- `schema/lenspack-4.schema.json`: the manifest structure, for editors and generic tooling;
- `conformance/limits.json`: every limit, enumeration and budget below. Both the reference
  validator and the app's parity test read it, so they cannot drift silently;
- `conformance/cases/`: valid and invalid packs with the result each reader must give.

Where this text and `limits.json` disagree, `limits.json` wins and this text is a bug.

> **Version history.** Earlier drafts jumped from v3 to "v5" for the Filter Studio fields.
> Those fields are now ordinary features of the format, and the first versioned format is
> **4**. There is no v5.

---

## 1. Forms and packaging

1. **Bare cube.** A single `MyLook.cube`. The look is named after the file.
2. **Pack folder.** `MyLook.lenspack/` with `manifest.json` at its root plus the assets it
   names. This is the authoring form and the installed form.
3. **Pack archive.** A `.lenspack` *file* is a **zip** of the pack folder's *contents*
   (`manifest.json` at the archive root, not inside a wrapper folder). This is the form that is
   shared and downloaded.
   - Uniform Type Identifier: `com.bubblelabs.lenspack` (conforms to `public.zip-archive`).
   - MIME type: `application/vnd.lenspack+zip`.
   - Entries are stored (method 0) or deflated (method 8). Nothing else.
   - Gallery archives are built reproducibly by `tools/build_index.py`: sorted entries, a
     fixed 1980-01-01 timestamp, mode 0644, no extra fields.

Install location: **Files → Lens → LensPacks** (`Documents/LensPacks/`). The file system is the
source of truth: delete the file or folder and the look is gone. Loading is silent: a pack
that fails validation is skipped and logged, never an alert.

A v4 pack installed by the app lives at `LensPacks/<author>.<slug>.lenspack/`, derived from its
`id` (`@author/slug`). Installing a pack with the same `id` replaces it; a lower `version` is
refused as a downgrade unless the user asks for it.

## 2. Path rules

Every file name in a manifest is a **path relative to the pack root**, and every reader
enforces the same rule before touching the file system:

- not empty; no NUL; no backslash (`\`);
- not absolute (no leading `/`) and no leading `~`;
- split on `/`, no component is empty, `.` or `..`;
- **at most two components**: a file at the root or in one subdirectory (`stickers/a.png`);
- no component may be a **symlink**, and the resolved file must lie inside the pack folder.

A path that breaks the rule makes the pack **invalid** in every format version, including
legacy packs. Archive entry names follow the same rule (see §9).

## 3. Budgets

Budgets bound what a pack can make the app decode. Exceeding a pack-level budget makes the pack
invalid; there is no partial load.

| Budget | Limit |
|---|---|
| Overlays | ≤ 8 |
| Triggers | ≤ 8 |
| Effects | ≤ 16 |
| Data readouts | ≤ 4 |
| Frames per overlay (frame 0 + `frames`) | ≤ 24 |
| Pixels per overlay-class image (overlay frames, trigger frames, `meshTexture`) | ≤ 4,000,000 |
| Pixels per frame of an **animated** overlay (more than one frame) | ≤ 1,000,000 |
| **Decoded overlay pixels per pack** (sum over every overlay frame, trigger frame and `meshTexture` reference) | ≤ 32,000,000 |
| `.cube` file | ≤ 8 MB, `LUT_3D_SIZE` 2…65 |
| Thumbnail | PNG, ≤ 512 px on its longer edge |
| Archive (§9) | ≤ 25 MB compressed, ≤ 64 MB uncompressed, ≤ 64 entries, ≤ 16 MB per entry, compression ratio ≤ 100:1 |
| Gallery index | ≤ 256 KB |

Overlay-class images must be **PNG**; readers measure them from the PNG header, never by
decoding. In legacy packs, a single image that is missing, not a PNG, or over its per-image
limit drops that frame (and its overlay, if no frame survives) with a warning, as v1–v3
readers did. In v4 packs it is a problem.

## 4. manifest.json (format 4)

```json
{
  "lenspack": 4,
  "id": "@you/golden-crown",
  "version": "1.2.0",
  "name": "Golden Crown",
  "author": "@you",
  "summary": "Warm grade, soft bloom, a crown on every face.",
  "license": "CC-BY-4.0",
  "attribution": "Crown artwork by @friend",
  "thumbnail": "thumb.png",
  "localized": {"fr": {"name": "Couronne dorée", "summary": "…"}},
  "required": ["lut", "overlays"],
  "requires": ["faceTracking"],
  "lut": {"file": "warm.cube", "input": "srgb-display"},
  "effects": [{"type": "bloom", "intensity": 0.4, "params": {"radius": 0.02}}],
  "overlays": [{"image": "crown.png", "anchor": "forehead", "scale": 1.3, "opacity": 0.9}],
  "data": [{"type": "elevation", "position": "bottomLeft"}]
}
```

| Field | Type | Rule |
|---|---|---|
| `lenspack` | integer | **Required** in v4, exactly `4`. A higher integer means a newer format: the reader shows the pack as *Needs a newer Lens*. A non-integer, or an integer below 4, is invalid. |
| `id` | string | **Required.** `@author/slug`, lowercase letters, digits and `-` (author ≤ 39, slug ≤ 64 characters). Stable across versions; it is the pack's identity. |
| `version` | string | **Required.** Semantic version (`1.2.0`, `2.0.0-beta.1`). Used to detect updates and refuse downgrades. |
| `name` | string | **Required**, non-empty. The look's display name. |
| `author`, `summary` | string | Optional, shown in the gallery. |
| `license` | string | An SPDX licence expression (`CC-BY-4.0`, `MIT OR Apache-2.0`). Optional in a manifest; **required for gallery listing**. |
| `attribution` | string | Optional credit line shown with the pack. |
| `thumbnail` | path | Optional PNG, ≤ 512 px on its longer edge, rendered on a neutral reference image. |
| `localized` | object | Optional. Keys are BCP 47 language tags (`fr`, `pt-BR`); values may carry `name` and `summary`. |
| `minLens` | string | Optional, informational: the oldest Lens release the author tested. |
| `required` | [string] | Optional. Features the pack cannot be rendered without (§4.1). |
| `requires` | [string] | Optional hardware labels (§8). Labels only, never a gate. |
| `lut`, `effects`, `overlays`, `data`, `meshTexture`, `triggers` | | Content, §5–§8. |

A pack must contain at least one usable item of content.

### 4.1 Required features and forward compatibility

`required` lists the features the look depends on. The known feature names are:

`lut`, `lutInput`, `effects`, `effectParams`, `overlays`, `overlayOpacity`, `overlayBlend`,
`overlayZ`, `overlayFaces`, `data`, `meshTexture`, `triggers`.

- If any listed feature is unknown to the reader, **or** known but not implemented by it, the
  reader does not load the pack and shows *Needs a newer Lens*, keeping the reason. It never
  renders a degraded version of a look whose author said a feature was essential.
- Content the author did **not** list stays forward-compatible: unknown effect types, unknown
  anchors, unknown blendshapes and unknown data types are dropped individually with a warning.
  Unknown top-level fields are ignored.
- A **malformed known field** (wrong type, an enumeration value outside the list, a `params`
  value outside its range) is a reported problem in v4 packs, not a silent drop.

### 4.2 Legacy packs and migration

A manifest **without** a `lenspack` field is a **legacy pack** and is read with the v1–v3
rules, unchanged:

- `id` is derived as `legacy:` + the first 16 hex digits of the SHA-256 of the
  `manifest.json` bytes (of the `.cube` bytes, for a bare cube);
- `version` is informational and may be any string (or absent, or a number);
- a string `lut` means `{"file": <string>, "input": "srgb-display"}`;
- a broken individual item (a missing image, a malformed overlay) is dropped with a warning;
  the rest of the pack loads;
- overlay `offsetY` stays in face **heights** (v4 measures both offsets in face widths);
- path rules and budgets apply in full: they are safety rules, not format rules.

A v4 reader must render a legacy pack exactly as a v3 reader did.

## 5. Colour: `lut`

```json
"lut": "warm.cube"
"lut": {"file": "log-to-709.cube", "input": "apple-log", "output": "rec709-display"}
```

- `file` (required): an Adobe/Resolve `.cube`, `LUT_3D_SIZE N` with **2 ≤ N ≤ 65**, exactly N³
  finite `r g b` rows, file ≤ 8 MB. `TITLE`, `DOMAIN_MIN`, `DOMAIN_MAX` and `#` comments are
  allowed. 1D LUTs are not supported.
- `input`: the encoding the cube expects: `srgb-display` (default), `rec709-display`,
  `p3-display`, `apple-log`, `hlg`. The reader converts the image into this encoding before the
  lookup, so a look authored for sRGB stills is never applied to Log footage as if it were sRGB.
- `output`: the encoding the cube produces: `srgb-display`, `rec709-display` or `p3-display`.
  Defaults to `input` for display inputs and to `rec709-display` for `apple-log` and `hlg`.

Pipeline order is fixed: **lut → effects → overlays → data**.

## 6. Film effects: `effects`

```json
{"type": "grain", "intensity": 0.3, "params": {"size": 0.0015, "roughness": 0.6}}
```

- `type` (required): `bloom` | `halation` | `grain` | `vignette` | `saturation` | `contrast` |
  `temperature` | `fade` | `sharpen`.
- `intensity` (default 0.5): the headline dial, normalised **0–1** and clamped by the reader.
  For the bipolar nodes (`saturation`, `contrast`, `temperature`) **0.5 is neutral**:
  saturation 0 → greyscale, 1 → 2×; contrast maps to 0.75–1.25; temperature maps to
  3500 K–9500 K.
- `params` (optional, feature `effectParams`): named, typed parameters with units. **Every
  spatial value is a fraction of the image's short edge**, so a look renders the same on a
  1080p preview and a 48 MP photo.

| Node | Param | Unit | Range |
|---|---|---|---|
| grain | `size` | grain diameter, fraction of short edge | 0.0002–0.02 |
| grain | `roughness` | 0 smooth … 1 clumpy | 0–1 |
| grain | `chroma` | 0 monochrome … 1 full colour grain | 0–1 |
| bloom, halation | `radius` | blur radius, fraction of short edge | 0.001–0.1 |
| bloom, halation | `threshold` | luminance where the glow starts | 0–1 |
| vignette | `midpoint` | where falloff begins, fraction of the half-diagonal | 0–1 |
| vignette | `feather` | width of the falloff | 0–1 |
| temperature | `kelvinShift` | white-balance shift, kelvin | −3000…3000 |
| temperature | `tint` | green (−) … magenta (+) | −1…1 |

An unknown param name is ignored with a warning; a known param outside its range is a problem.
Effects apply in the order listed and never change the image extent. The node names
`splitTone`, `curve` and `hsl` are reserved for a later revision; today's readers skip them.

## 7. Overlays: `overlays`

```json
{"image": "crown.png", "anchor": "forehead", "scale": 1.3, "offsetY": 0.1,
 "frames": ["crown2.png"], "fps": 8, "opacity": 0.9, "blend": "screen", "z": 1, "faces": "all"}
```

| Field | Default | Rule |
|---|---|---|
| `image` | required | PNG with alpha (§2, §3). Frame 0. |
| `anchor` | required | `forehead` \| `eyes` \| `nose` \| `mouth` \| `chin`. |
| `scale` | 1.0 | Overlay width as a multiple of the face width, clamped 0.1–3. |
| `offsetX`, `offsetY` | 0 | Offsets (x right, y up), clamped ±1. v4: both in face **widths**. Legacy: `offsetY` in face heights. |
| `frames` | `[]` | More PNGs cycled after `image`: an animated overlay. ≤ 24 frames in total; each ≤ 1 MP. |
| `fps` | 8 | Animation rate, clamped 1–30. |
| `opacity` | 1 | 0–1 (feature `overlayOpacity`). |
| `blend` | `normal` | `normal` \| `multiply` \| `screen` \| `add` (feature `overlayBlend`). |
| `z` | 0 | Integer −100…100; higher draws on top (feature `overlayZ`). |
| `faces` | `all` | `all`, `largest`, or an integer 1–8: that many faces, largest first (feature `overlayFaces`). |

The app anchors overlays to detected face landmarks (pupil-exact eyes, lip centroid, contour
chin; forehead extrapolated along the face axis) and rotates them with the head's roll.

## 8. Filter Studio, data readouts and hardware labels

Rendered in the app's ARKit **Filter Studio** on TrueDepth devices: a tracked face mesh plus
52 expression blendshapes at 60 fps.

- `meshTexture` (feature `meshTexture`): a PNG in ARKit face-mesh **UV space**, ≤ 4 MP, counted
  in the pack pixel budget. Face paint that follows the skin.
- `triggers` (feature `triggers`), ≤ 8:
  ```json
  {"blendshape": "mouthOpen", "threshold": 0.6,
   "overlay": {"image": "fire.png", "anchor": "mouth", "scale": 2.0}}
  ```
  `blendshape`: `mouthOpen` | `smile` | `browsUp` | `blink`; unknown names are dropped.
  `threshold` (default 0.5) is the 0–1 coefficient at which the overlay appears (with
  hysteresis). The trigger's overlay follows every rule in §7, including the image budgets.
- `data` (feature `data`, v3.1), ≤ 4: live readouts drawn on the image.
  ```json
  {"type": "elevation", "position": "bottomLeft"}
  ```
  `type`: `elevation` | `speed` (unknown types are dropped). `position`: `topLeft` |
  `topRight` | `bottomLeft` (default) | `bottomRight`. Readouts are computed on the device from
  its location and can be baked into shared photos, so readers may require a per-pack opt-in
  before showing them. Nothing about location ever leaves the device.
- `requires`: hardware the pack is designed for, `depth` and `faceTracking`. **Labels only**:
  the app installs and runs the pack regardless, degrading gracefully, and shows what a device
  can't unlock. Unknown strings read as unmet. (Contrast `required`, §4.1, which gates.)

## 9. Archives

A reader unpacks a `.lenspack` archive from its **central directory**, and refuses the archive
whole, before writing anything, if any entry:

- has a name that breaks the path rule (§2): "zip-slip";
- is a symlink (Unix mode `S_IFLNK` in the external attributes);
- is encrypted (general-purpose flag bit 0), or uses a method other than store/deflate;
- duplicates another entry's name, compared case-insensitively;
- inflates to more than 16 MB, or to more than 100× its compressed size,

or if the archive has more than 64 entries, more than 64 MB in total, is a Zip64 archive, or is
over 25 MB. While inflating, an entry that produces more bytes than its declared size, or whose
CRC-32 does not match, is refused. The unpacked folder is then validated like any other pack,
staged outside `LensPacks/`, and moved into place with an atomic rename.

## 10. Gallery index (`index.json`, version 2)

The in-app gallery reads `index.json` from this repository, only when the user opens it. Schema:
`schema/index-2.schema.json`.

```json
{"version": 2, "packs": [{
  "name": "Party Crown", "author": "@lenspack-spec", "summary": "…",
  "fileName": "lenspack-spec.party-crown.lenspack",
  "url": "https://raw.githubusercontent.com/moiz-7/lenspack-spec/main/dist/lenspack-spec.party-crown.lenspack",
  "sha256": "…",
  "id": "@lenspack-spec/party-crown", "version": "1.0.0", "size": 690,
  "license": "CC-BY-4.0", "kind": "pack", "lenspack": 4,
  "thumbnail": "https://…/thumb.png"
}]}
```

- Every entry keeps the version-1 fields (`name`, `author`, `summary`, `fileName`, `url`,
  `sha256`). App builds that read version 1 install the `.cube` entries and skip the rest, so
  adding packs never breaks a shipped app.
- `fileName` is a **bare file name**: no `/`, no `\`, no leading `.`, ending in `.cube` or
  `.lenspack`. A reader refuses any other value.
- `kind`: `cube` (a bare `.cube`) or `pack` (a `.lenspack` archive).
- `size`: the exact byte count. Readers stream the download and abort once it exceeds `size`
  (and never accept more than 25 MB for a pack, 8 MB for a cube, or 256 KB for the index).
- `sha256`: lowercase hex of the downloaded bytes, verified before anything is unpacked.
- Index signing (Ed25519, detached `index.json.sig`, a pinned key plus an offline rotation key)
  is planned and not yet enforced.

`index.json` and `dist/` are generated by `python3 tools/build_index.py` from `packs/` and
`examples/`; CI fails if they are stale.

## 11. Validation

```
python3 validator/validate_lenspack.py "examples/Sunset Fade.cube"
python3 validator/validate_lenspack.py examples/party-crown.lenspack
python3 validator/validate_lenspack.py dist/lenspack-spec.party-crown.lenspack   # a zip
python3 validator/validate_lenspack.py some.lenspack --json
```

Exit status: 0 valid, 1 invalid, 2 needs a newer reader. Problems carry stable codes
(`path.unsafe`, `budget.packPixels`, `manifest.id`, …). The conformance cases assert codes, not
wording; run them with `python3 -m pytest tests`. Regenerate the cases with
`python3 tools/gen_conformance.py`.
