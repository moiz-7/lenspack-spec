# LensPack Format Specification (format 4, vocabulary revision 2)

A **LensPack** is a community-authored look for the Lens camera app. A pack is **pure data,
never code**: no scripts, no shaders, no network access, no permissions. The app applies pack
content through its own audited implementation. Each format version widens the manifest's
*vocabulary*, never its *authority*. §12 lists what the vocabulary will never contain.

One pack can carry any combination of:

| Content | Field | Since |
|---|---|---|
| A colour grade (3D LUT), in any of five encodings | `lut` | v1; spaces v4 |
| Film effects (bloom, grain, …) with typed parameters | `effects` | v3; params v4 |
| Face-anchored stickers, optionally animated, with head pose and per-face variants | `overlays` | v2; pose, stage, variants rev 2 |
| Expression triggers | `triggers` | Filter Studio; modes rev 2 |
| Face paint on the face mesh | `facePaint` (`meshTexture` is its shorthand) | rev 2 |
| Skin smoothing (consent-gated, capped), background blur or image, skin protect | `retouch`, `background`, `skinProtect` | rev 2 |
| Live data readouts (elevation, speed; consent-gated) | `data` | v3.1 |
| Identity, versioning, licence, translations, remix provenance, packaging | `lenspack`, `id`, `version`, … `remixOf` | **v4** |

The machine-readable sources of truth sit next to this document:

- `schema/lenspack-4.schema.json`: the manifest structure, for editors and generic tooling;
- `conformance/limits.json`: every limit, enumeration and budget below. Both the reference
  validator and the app's parity test read it, so they cannot drift silently;
- `conformance/cases/`: valid and invalid packs with the result each reader must give;
- `conformance/goldens/`: reference numbers for the colour and effect maths of §5 and §6,
  computed by `lenspack/reference.py`, which every renderer is held to.

Where this text and `limits.json` disagree, `limits.json` wins and this text is a bug.

> **Version history.** Earlier drafts jumped from v3 to "v5" for the Filter Studio fields.
> Those fields are now ordinary features of the format, and the first versioned format is
> **4**. There is no v5. Format 4 then grew by **vocabulary revisions** (§4.1): revision 2
> (2026-10) adds face looks. "Format 5" stays reserved for a genuinely breaking change.

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
| Variants per overlay (revision 2) | ≤ 7 (plus `image`) |
| Face-paint frames (`image` + `frames`, revision 2) | ≤ 8 |
| Pixels per overlay-class image (overlay frames and variants, trigger frames, `meshTexture`, a static `facePaint`, a `background` image) | ≤ 4,000,000 |
| Pixels per frame of an **animated** overlay or face paint (more than one frame) | ≤ 1,000,000 |
| **Decoded overlay pixels per pack** (sum over every overlay frame and variant, trigger frame, `meshTexture`, `facePaint` frame and `background` image reference) | ≤ 32,000,000 |
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
  "overlays": [{"image": "crown.png", "anchor": "head", "scale": 1.3, "opacity": 0.9, "pose": "full"}],
  "skinProtect": 0.6,
  "remixOf": {"id": "@friend/crown", "version": "1.0.0"}
}
```

| Field | Type | Rule |
|---|---|---|
| `lenspack` | integer | **Required** in v4, exactly `4`. A higher integer means a newer format: the reader shows the pack as *Needs a newer Lens*. A non-integer, or an integer below 4, is invalid. |
| `id` | string | **Required.** `@author/slug`, lowercase letters, digits and `-` (author ≤ 39, slug ≤ 64 characters). Stable across versions; it is the pack's identity. |
| `version` | string | **Required.** Semantic version (`1.2.0`, `2.0.0-beta.1`). Used to detect updates and refuse downgrades. |
| `name` | string | **Required**, non-empty. The look's display name. |
| `author`, `summary` | string | Optional, shown in the gallery. |
| `license` | string | An SPDX licence expression (`CC-BY-4.0`, `MIT OR Apache-2.0`). Optional in a manifest; **required for gallery listing**. It also decides what a remix may do (§4.3). |
| `attribution` | string | Optional credit line shown with the pack. |
| `thumbnail` | path | Optional PNG, ≤ 512 px on its longer edge, rendered on a neutral reference image. |
| `localized` | object | Optional. Keys are BCP 47 language tags (`fr`, `pt-BR`); values may carry `name` and `summary`. A reader shows the entry that best matches the person's preferred languages (exact tag, then language alone), else the untranslated fields. Translations are display text only: the look's identity is `id`. |
| `minLens` | string | Optional, informational: the oldest Lens release the author tested. |
| `required` | [string] | Optional. Features the pack cannot be rendered without (§4.1). |
| `requires` | [string] | Optional hardware labels (§8.5). Labels only, never a gate. |
| `remixOf` | object | Revision 2, optional, informational: `{"id": "@author/slug", "version": "1.0.0"}` of the pack this one was remixed from (`id` may be a `legacy:` id). Malformed is `manifest.remixOf`. |
| `lut`, `effects`, `overlays`, `triggers`, `facePaint`, `meshTexture`, `retouch`, `background`, `skinProtect`, `data` | | Content, §5–§8. |

A pack must contain at least one usable item of content. `skinProtect` alone is not content:
it modifies a grade.

### 4.1 Required features, revisions and forward compatibility

`required` lists the features the look depends on. The known feature names are:

- revision 1: `lut`, `lutInput`, `effects`, `effectParams`, `overlays`, `overlayOpacity`,
  `overlayBlend`, `overlayZ`, `overlayFaces`, `data`, `meshTexture`, `triggers`;
- revision 2: `overlayPose`, `overlayStage`, `overlayBehind`, `overlayVariants`, `faceAnchors`,
  `overlayBlendExtended`, `triggerModes`, `triggerShapes2`, `facePaint`, `retouch`,
  `background`, `skinProtect`.

- If any listed feature is unknown to the reader, **or** known but not implemented by it, the
  reader does not load the pack and shows *Needs a newer Lens*, keeping the reason. It never
  renders a degraded version of a look whose author said a feature was essential.
- Content the author did **not** list stays forward-compatible: unknown effect types, unknown
  anchors, unknown blendshapes and unknown data types are dropped individually with a warning.
  Unknown top-level fields are ignored.
- A **malformed known field** (wrong type, an enumeration value outside the list, a `params`
  value outside its range) is a reported problem in v4 packs, not a silent drop.

**Revisions.** `limits.json` carries `"revision"`. A revision is additive and never breaks an
older reader:

- a new **field** is ignored by an older reader, and the pack degrades (the table in §7 says
  how);
- a new **value of an existing strict field** would make an older reader call the pack
  *invalid*. So a pack that uses one **must** list the matching feature in `required`
  (`limits.json` → `overlays.blendsRequiring`), and an older reader then says *Needs a newer
  Lens* instead. A pack that uses one without listing it has the problem **`required.missing`**
  (a warning that drops the overlay, in a legacy pack). In revision 2 the only such values are
  the blends `overlay` and `softLight` (feature `overlayBlendExtended`), in `overlays` and in
  trigger overlays.

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
- revision-2 fields (`facePaint`, `retouch`, `background`, `skinProtect`, `remixOf`, and the
  overlay fields `pose`, `stage`, `behindPerson`, `variants`, and trigger `mode`) are format-4
  vocabulary: a legacy pack that carries them has them **ignored**, with the warning
  `legacy.ignored`;
- path rules and budgets apply in full: they are safety rules, not format rules.

A v4 reader must render a legacy pack exactly as a v3 reader did.

### 4.3 Remixing and licences

A reader that lets a person remix a look writes a new pack with `remixOf` naming the source and
carries the source's face content verbatim. What the new pack may then do follows the source's
`license`:

| Source licence | Remix |
|---|---|
| `CC0-1.0`, `CC-BY-*` (not `-SA`, not `-ND`), `MIT`, `Apache-2.0` (or an `OR` expression containing one) | Allowed, shareable; attribution carried over |
| `CC-BY-SA-*` | Allowed, shareable, and the remix **must** use the same licence |
| any `-ND` licence, any other licence, or none | A **private** remix only: it may be kept on the device, never shared |

`@local/…` ids are what a reader writes for a pack made on the device; they are never listed in
the gallery (§10.3).

## 5. Colour: `lut`

```json
"lut": "warm.cube"
"lut": {"file": "log-to-709.cube", "input": "apple-log", "output": "rec709-display"}
```

- `file` (required): an Adobe/Resolve `.cube`, `LUT_3D_SIZE N` with **2 ≤ N ≤ 65**, exactly N³
  finite `r g b` rows, file ≤ 8 MB. `TITLE`, `DOMAIN_MIN`, `DOMAIN_MAX` and `#` comments are
  allowed. 1D LUTs are not supported.
- `input` (feature `lutInput`): the encoding the cube expects: `srgb-display` (default),
  `rec709-display`, `p3-display`, `apple-log`, `hlg`. The reader converts the image into this
  encoding before the lookup, so a look authored for Log footage is never applied to a JPEG as
  if it were Log, and the reverse.
- `output`: the encoding the cube produces: `srgb-display`, `rec709-display` or `p3-display`.
  Defaults to `input` for display inputs and to `rec709-display` for `apple-log` and `hlg`.

### 5.1 The encodings

Every encoding is a set of primaries (white D65 throughout) plus a transfer function between
linear light and code values in 0…1 (full range).

| Encoding | Primaries | Transfer (linear → code) |
|---|---|---|
| `srgb-display` | BT.709 | IEC 61966-2-1: `12.92·L` for L ≤ 0.0031308, else `1.055·L^(1/2.4) − 0.055` |
| `rec709-display` | BT.709 | BT.709: `4.5·L` for L < 0.018, else `1.099·L^0.45 − 0.099` |
| `p3-display` | Display P3 | the sRGB transfer |
| `apple-log` | BT.2020 | Apple Log (Apple, *Apple Log Profile*, 2023), on scene-linear reflectance R (0.18 = mid grey): `0` for R < R₀; `c·(R − R₀)²` for R₀ ≤ R < Rₜ; `γ·log₂(R + β) + δ` otherwise, with R₀ = −0.05641088, Rₜ = 0.01, c = 47.28711236, β = 0.00964052, γ = 0.08550479, δ = 0.69336945 |
| `hlg` | BT.2020 | BT.2100 HLG OETF on E = R · E₁₈ / 0.18, E clamped to 0…1, where E₁₈ = 0.38² / 3 (BT.2408: an 18 % grey card at 38 % signal): `√(3E)` for E ≤ 1/12, else `a·ln(12E − b) + c` with a = 0.17883277, b = 1 − 4a, c = 0.5 − a·ln(4a) |

Primary conversions are the 3×3 matrices derived from the chromaticities (BT.709: R 0.640 0.330,
G 0.300 0.600, B 0.150 0.060; Display P3: R 0.680 0.320, G 0.265 0.690, B 0.150 0.060; BT.2020:
R 0.708 0.292, G 0.170 0.797, B 0.131 0.046; D65 0.3127 0.3290) through XYZ, with no chromatic
adaptation (every white is D65). `apple-log` and `hlg` are BT.2020 encodings, so an Apple Log
cube is always handed BT.2020 values.

### 5.2 How a reader applies a cube

**On display-referred pictures** (photos, the viewfinder, footage recorded in a display
encoding) the reader folds everything into one composed lattice. Its encoding **K** is
`p3-display` when the cube's input or output is `p3-display`, otherwise `srgb-display`; for
each lattice point `k`:

1. decode `k` from K to linear light;
2. convert primaries from K's to the input's;
3. encode into `input`. For `apple-log` and `hlg` the display-linear value is treated as
   scene-linear reflectance (0.18 ↔ 0.18);
4. look the result up in the pack cube, trilinearly, clamped to 0…1;
5. decode with `output`, convert primaries to K's;
6. encode into K and clamp to 0…1.

The lattice is 65³ whenever the cube's input or output is not `srgb-display`. A cube with
`input` and `output` both `srgb-display` (every legacy cube) is applied exactly as written, with
no composition: such a look is bit-identical to its v3 rendering.

**On camera footage in a log or HLG encoding** (a recording):

- when the cube's `input` **equals** the footage's encoding (an `apple-log` cube on Apple Log
  footage, an `hlg` cube on HLG footage), the cube is applied **directly to the camera's code
  values**, with no decode. Its output is the recording's output; this is how a show LUT works
  in a grading application, and a reader's file must match one within ΔE2000 2;
- otherwise the footage is decoded to scene-linear (§5.1), converted to the input's primaries,
  encoded into `input`, and looked up.

Either way the cube's output becomes the recording's display encoding: `rec709-display` code
values when the cube's output is `rec709-display`, else `srgb-display` code values in BT.709
primaries. Per-pixel effects (§6) then apply to display values.

**Pipeline order** is fixed (§8.6 has the full list with face content): background → retouch →
`scene`-stage overlays and face paint → **colour** (the cube, then the per-pixel effects, with
skin protect) → spatial effects → `top`-stage overlays → data.

## 6. Film effects: `effects`

```json
{"type": "grain", "intensity": 0.3, "params": {"size": 0.0015, "roughness": 0.6, "chroma": 0.2}}
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
Per-pixel nodes (`saturation`, `contrast`, `temperature`, `fade`) apply first, in the order
listed, as part of the colour stage; spatial nodes then apply in the order listed. No node
changes the image extent. The node names `splitTone`, `curve` and `hsl` are reserved for a later
revision; today's readers skip them.

### 6.1 The maths of the params

Every formula works on display-encoded values E in 0…1 unless it says linear. A node without
params is exactly what it was in v3; a param only refines its own node.

- **`grain.chroma` = c.** Let n_L be the grain field and n_R, n_G, n_B three further,
  independent fields of the same generator. Channel X receives
  `n_X' = (1 − c)·n_L + c·n_X`. At c = 0 every channel gets the same noise (monochrome grain);
  at c = 1 the channels are independent. The inter-channel correlation is therefore
  `(1 − c)² / ((1 − c)² + c²)`.
- **`bloom.threshold` = t.** Highlights `h = clamp((E − t) / (1 − t), 0, 1)` per channel,
  Gaussian-blurred with σ = `radius` × short edge into B, then screened at the intensity i:
  `E' = 1 − (1 − E)·(1 − i·B)`. Without `threshold`, bloom is the v3 node.
- **`halation.threshold` = t.** As bloom, with the blurred highlights tinted (×1.15, ×0.85,
  ×0.70) and screened at 0.6·i.
- **`vignette.feather` = f** (with `midpoint` m, default 0.5). With r the distance from the
  image centre divided by the half-diagonal, `v(r) = 1 − i·smoothstep(m, m + f·(1 − m) + 0.0001, r)`,
  multiplied into E. A vignette without `feather` is the v3 node (`midpoint` alone sets its
  radius, as before).
- **`temperature.kelvinShift` = s, `temperature.tint` = τ.** The target white is the Planckian
  white of `T = clamp(3500 + 6000·i + s, 1000, 15000)` K (so i = 0.5 with no params is neutral),
  offset along the isotherm (the unit normal to the Planckian locus in CIE 1960 uv, pointing
  away from green) by `0.02·τ`. Planckian uv is Krystek's rational approximation. The node is
  a Bradford adaptation from the Planckian white at 6500 K to that target, applied to **linear**
  BT.709 values, with the white's luminance kept. Being per pixel, it belongs in the cube.

`conformance/goldens/` holds the expected numbers for each of these, and for §5's encodings and
compositions, computed by `lenspack/reference.py`. A renderer is conformant when it matches them
within ΔE2000 1 (colour) or the tolerance stated in the golden file (statistics).

## 7. Overlays: `overlays`

```json
{"image": "crown.png", "anchor": "head", "scale": 1.3, "offsetY": 0.1,
 "frames": ["crown2.png"], "fps": 8, "opacity": 0.9, "blend": "screen", "z": 1, "faces": "all",
 "pose": "full", "stage": "top"}
```

| Field | Default | Rule | An older reader |
|---|---|---|---|
| `image` | required | PNG with alpha (§2, §3). Frame 0. | |
| `anchor` | required | `forehead` \| `eyes` \| `nose` \| `mouth` \| `chin`; revision 2 adds `leftEye` \| `rightEye` \| `leftCheek` \| `rightCheek` \| `head` \| `face` (feature `faceAnchors`). | Drops the overlay |
| `scale` | 1.0 | Overlay width as a multiple of the face width, clamped 0.1–3. | |
| `offsetX`, `offsetY` | 0 | Offsets (x right, y up), clamped ±1. v4: both in face **widths**. Legacy: `offsetY` in face heights. | |
| `frames` | `[]` | More PNGs cycled after `image`: an animated overlay. ≤ 24 frames in total; each ≤ 1 MP. | |
| `fps` | 8 | Animation rate, clamped 1–30. | |
| `opacity` | 1 | 0–1 (feature `overlayOpacity`). | |
| `blend` | `normal` | `normal` \| `multiply` \| `screen` \| `add` (feature `overlayBlend`); revision 2 adds `overlay` \| `softLight`, which **must** be announced with `overlayBlendExtended` (§4.1). | Needs a newer Lens |
| `z` | 0 | Integer −100…100; higher draws on top (feature `overlayZ`). | |
| `faces` | `all` | `all`, `largest`, or an integer 1–8: that many faces, largest first (feature `overlayFaces`). | |
| `pose` | `roll` | Revision 2 (feature `overlayPose`): `roll` \| `full` \| `screen`. | Renders roll |
| `stage` | `top` | Revision 2 (feature `overlayStage`): `top` \| `scene`. `scene` draws under the grade and grain, so it reads as part of the photograph. | Renders on top |
| `behindPerson` | false | Revision 2 (feature `overlayBehind`): drawn, then the person (the person matte) is composited back over it. | Renders in front |
| `variants` | — | Revision 2 (feature `overlayVariants`): 1–7 more PNG paths; face slot k gets `([image] + variants)[k mod n]`. Never combined with `frames`. Every variant counts in the pack budget. | Everyone gets `image` |

### 7.1 Faces, order and the face width

- The **face width** is 2.3 × the inter-pupil distance when both pupils are known, otherwise the
  face's bounding-box width. It is the unit of `scale`, of offsets and of every spatial face
  parameter.
- **`faces`** selects faces by size rank. A reader must not let two faces of similar size swap
  rank from frame to frame (the app requires a 15 % area difference held for 0.3 s).
- **Slots.** A face keeps the slot it was given when it appeared (the smallest free index) for
  as long as it is tracked; `variants` are chosen by slot, so a person keeps their sticker.
- **Order.** Layers draw sorted by (stage, `z`, position in the manifest), stably;
  at equal `z`, `overlays` come before `triggers`.

### 7.2 Anchors

2D anchors are landmark points in the upright, unmirrored frame: `eyes` the pupils' midpoint,
`nose` the nose tip, `mouth` the lip centroid, `chin` the lowest contour point, `forehead` the
eyes' midpoint pushed 0.9 × (eyes − mouth) up the face axis. Revision 2:

- `leftEye`, `rightEye`: the subject's left and right pupils;
- `leftCheek`, `rightCheek`: midway between that eye's centre and the same-side mouth corner,
  pushed 0.15 face widths outward (away from the face axis);
- `head`: the forehead + 0.45 face widths along the face axis;
- `face`: the midpoint of the eye–mouth axis.

### 7.3 Pose

- `roll`: the layer rotates with the head's roll (every earlier reader's behaviour).
- `screen`: the layer stays upright.
- `full`: the layer is a plane in head space centred at the anchor's 3D position, rotated by
  R = R_roll·R_yaw·R_pitch and projected with weak perspective `p′ = p.xy / (1 − k·p.z)`,
  k = 0.15 per face width. The head-space origin is placed so that the `face` anchor projects
  onto the 2D `face` anchor. A reader with a measured face mesh uses the true camera projection
  instead. Anchor positions in head space, in face widths (x toward the subject's left, y up,
  z toward the camera):

  | Anchor | x | y | z |
  |---|---|---|---|
  | forehead | 0 | 0.393 | 0.393 |
  | eyes | 0 | 0.157 | 0.429 |
  | nose | 0 | −0.036 | 0.571 |
  | mouth | 0 | −0.271 | 0.464 |
  | chin | 0 | −0.464 | 0.321 |
  | leftEye / rightEye | ±0.217 | 0.157 | 0.400 |
  | leftCheek / rightCheek | ±0.300 | −0.100 | 0.360 |
  | head | 0 | 0.843 | 0.300 |
  | face | 0 | −0.057 | 0.446 |

  Pose angles: roll positive counter-clockwise, yaw positive when the nose turns toward image
  right, pitch positive when the nose turns up.

### 7.4 Blending

Blending happens on **display-encoded** values with premultiplied alpha, using the W3C
*Compositing and Blending Level 1* formulas, with the layer's alpha αs = image alpha ×
`opacity`: `Co = (1 − αs)·Cb + αs·B(Cb, Cs)`, where

- `normal`: B = Cs; `multiply`: B = Cb·Cs; `screen`: B = Cb + Cs − Cb·Cs;
- `overlay`: B = HardLight(Cs, Cb), i.e. `2·Cb·Cs` for Cb ≤ 0.5, else `screen(Cs, 2·Cb − 1)`;
- `softLight`: `Cb − (1 − 2Cs)·Cb·(1 − Cb)` for Cs ≤ 0.5, else `Cb + (2Cs − 1)·(D(Cb) − Cb)`,
  with D(Cb) = `((16Cb − 12)·Cb + 4)·Cb` for Cb ≤ 0.25, else `√Cb`;
- `add`: `Co = min(1, Cb + αs·Cs)`.

## 8. Face paint, triggers, retouch, background, skin protect, data

### 8.1 Face paint: `facePaint` (revision 2)

```json
"facePaint": {"image": "paint.png", "frames": ["paint2.png"], "fps": 8, "opacity": 0.9,
              "blend": "softLight", "faces": "all"}
```

An image in the ARKit face-mesh **UV space**, drawn on a tracked face mesh. `frames` animates
it (≤ 8 frames in total, each ≤ 1 MP when animated; a static image ≤ 4 MP). `blend` is one of
`normal` \| `multiply` \| `screen` \| `overlay` \| `softLight`; `opacity`, `fps` and `faces`
follow §7. `meshTexture: "paint.png"` (feature `meshTexture`) is the static shorthand for
`facePaint: {"image": "paint.png"}`; a pack gives one or the other, never both. Face paint needs
a face mesh, which today means the selfie camera; elsewhere a reader says so instead of drawing
it.

### 8.2 Triggers: `triggers`

```json
{"blendshape": "mouthOpen", "threshold": 0.6, "mode": "while",
 "overlay": {"image": "fire.png", "anchor": "mouth", "scale": 2.0}}
```

≤ 8. `blendshape`: `mouthOpen` | `smile` | `browsUp` | `blink`; revision 2 adds `wink` | `kiss` |
`tongueOut` | `cheekPuff` (feature `triggerShapes2`; `tongueOut` and `cheekPuff` need a measured
face mesh). Unknown names are dropped. `threshold` (default 0.5) is the 0–1 coefficient at which
the overlay appears, with hysteresis (it leaves at threshold − 0.1). `mode` (revision 2, feature
`triggerModes`): `while` (default: shown while held), `toggle` (each onset flips it), `once`
(each onset plays the overlay's frames once). The trigger's overlay follows every rule in §7,
including the image budgets.

### 8.3 Retouch, background, skin protect (revision 2)

- **`retouch`** (feature `retouch`): `{"skinSmoothing": 0…0.6}`. The algorithm is the reader's,
  but bound by these rules: only inside the skin mask; never moves a pixel; the skin's mean
  colour is preserved within ΔE 1; at 0.6 at least 40 % of fine-texture energy remains.
  Retouching is **never applied without the person's per-pack consent**, and photos and videos
  record "Skin smoothing" in their metadata. Unknown keys are warned about (`retouch.unknownKey`)
  and never implemented. A value outside 0…0.6 is the problem `value.range`.
- **`background`** (feature `background`): `{"mode": "blur", "amount": 0…1}` (σ = amount × 0.03 ×
  short edge, outside the person matte) or `{"mode": "image", "image": "bg.png", "fit": "fill" |
  "fit"}` (PNG ≤ 4 MP, counted in the pack budget; `fill` covers the frame, `fit` letterboxes).
- **`skinProtect`** (feature `skinProtect`): 0…1 (default 0). In display-encoded Rec.709 Y′CbCr,
  the output keeps Y′ from the graded image and takes
  `CbCr = mix(CbCr_graded, CbCr_ungraded, mask × skinProtect)`. The mask is the reader's: a
  feathered face-contour polygon, intersected with the person matte, weighted by a skin-chroma
  likelihood. A grade can therefore never shift skin hue toward or away from any skin tone.

### 8.4 Data readouts: `data`

`data` (feature `data`, v3.1), ≤ 4: live readouts drawn on the image.
```json
{"type": "elevation", "position": "bottomLeft"}
```
`type`: `elevation` | `speed` (unknown types are dropped). `position`: `topLeft` | `topRight` |
`bottomLeft` (default) | `bottomRight`. Readouts are computed on the device from its location
and can be baked into shared photos, so a reader **must** ask for a per-pack opt-in before it
shows them; until then the look renders without them. Nothing about location ever leaves the
device.

### 8.5 Hardware labels: `requires`

`requires`: hardware the pack is designed for, `depth` and `faceTracking`. **Labels only**: the
app installs and runs the pack regardless, degrading gracefully, and shows what a device can't
unlock. Unknown strings read as unmet. (Contrast `required`, §4.1, which gates.)

### 8.6 Pipeline order (normative)

1. `background`
2. `retouch`
3. `scene`-stage overlays and face paint
4. colour: the cube (§5), then the per-pixel effects, with `skinProtect`
5. spatial effects
6. `top`-stage overlays (the default) and triggers
7. `data`

### 8.7 Consent

`data` (location) and `retouch` each need the person's **per-pack** Allow, asked the first time
the look is chosen. The default is deny: the look renders without those parts and says so. A
new version that **adds** a need asks again. Consent can be revoked at any time and takes effect
on the next frame.

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

The in-app gallery reads `index.json` from this repository, only when the person opens it.
Schema: `schema/index-2.schema.json`.

```json
{"version": 2, "sequence": 7, "packs": [{
  "name": "Party Crown", "author": "@lenspack-spec", "summary": "…",
  "fileName": "lenspack-spec.party-crown.lenspack",
  "url": "https://raw.githubusercontent.com/moiz-7/lenspack-spec/main/dist/lenspack-spec.party-crown.lenspack",
  "sha256": "…",
  "id": "@lenspack-spec/party-crown", "version": "1.0.0", "size": 690,
  "license": "CC-BY-4.0", "kind": "pack", "lenspack": 4,
  "thumbnail": "https://…/thumb.png", "featured": true, "faces": true,
  "localized": {"fr": {"name": "Couronne de fête"}}
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
- `featured` (optional): shown in the gallery's Featured row. `faces` (optional): the pack has
  face content, for the Faces section. `localized`: the manifest's translations, copied.
- `sequence` (top level): a positive integer that **increases** with every change to the index.
- `revokeKeyIds` (top level, optional): key ids a reader must stop trusting (§10.1).

`index.json` and `dist/` are generated by `python3 tools/build_index.py` from `packs/` and
`examples/`; CI fails if they are stale.

### 10.1 Signing

The index is signed with **Ed25519**. The detached signature `index.json.sig` sits next to it:

```json
{"v": 1, "keyId": "2026-sign", "sig": "<base64 of the 64-byte signature>"}
```

- The signature is over the **exact bytes** of `index.json`. A reader verifies before it parses.
- A reader pins public keys by id: an online **signing** key and an offline **rotation** key.
  The repository lists the same public keys in `index-keys.json`.
- **Rollback:** a reader stores the highest `sequence` it has accepted and refuses a lower one.
- **Revocation:** an index signed by a **rotation** key may carry `revokeKeyIds`; a reader
  persists them and never again accepts a signature by those keys. (A revocation in an index
  signed by an ordinary signing key is ignored.)
- **Failure:** a missing, malformed or invalid signature, an unknown or revoked key or a lower
  sequence means the remote gallery is not shown: the reader keeps its built-in looks only,
  says it couldn't verify the gallery, and installs nothing from it.
- Because the index and its signature are two fetches, a cache can briefly hand a reader a new
  index with the previous signature. A reader that fails verification retries both once,
  bypassing caches, before it gives up.
- Signing happens in CI on every merge to `main` (`tools/sign_index.py`, the `release`
  environment); the private keys never enter the repository. `PUBLISHING.md` has the procedure.

`checksums.json` inside archives is deliberately **not** part of the format: for gallery
installs the signed index's `sha256` already covers the archive, and for a side-loaded pack a
checksum file gives no authenticity, because whoever altered the pack regenerates it.

### 10.2 Hosting and caching

The index and archives are static files served over HTTPS. Servers should send `ETag` and
`Cache-Control`; readers revalidate with an ordinary HTTP cache. No reader ever sends anything
but a plain GET, and no analytics exist.

### 10.3 Namespaces

`namespaces.json` maps each `@author` to the GitHub logins allowed to publish under it. CI
refuses a pull request that adds or changes a pack in a namespace its author does not own, or
that claims a reserved namespace (`@lens`, `@lenspack-spec`, `@local`, `@conformance`). A new
creator claims a free namespace for their own login in the pull request that adds their first
pack.

## 11. Validation and tools

```
pip install lenspack                       # or: pip install . from a checkout
lenspack validate "examples/Sunset Fade.cube"
lenspack validate examples/party-crown.lenspack
lenspack validate dist/lenspack-spec.party-crown.lenspack --json   # a zip
lenspack pack packs/lenspack-spec.party-crown.lenspack out.lenspack  # reproducible zip
lenspack hash out.lenspack                                         # sha256 and size
lenspack verify-index index.json --sig index.json.sig --keys index-keys.json
```

From a checkout without installing, `python3 validator/validate_lenspack.py <path>` is the same
validator. Exit status: 0 valid, 1 invalid, 2 needs a newer reader. Problems carry stable codes
(`path.unsafe`, `budget.packPixels`, `manifest.id`, `required.missing`, …). The conformance
cases assert codes, not wording; run them with `python3 -m pytest tests`. Regenerate the cases
with `python3 tools/gen_conformance.py` and the goldens with `python3 tools/gen_goldens.py`.

A GitHub Action validates packs in other repositories:

```yaml
- uses: moiz-7/lenspack-spec@v1
  with:
    path: "looks/*.lenspack"
```

## 12. What LensPack will never contain

The vocabulary grows only by spec pull requests that bring their maths and conformance cases.
These are out of scope for good, whatever the request:

- scripting, logic graphs, shaders, code of any kind, network access, storage, or ML models
  inside a pack;
- 3D model formats parsed by a reader (static head accessories, if ever, through the platform's
  own renderer only);
- face or body **reshaping** (liquify, slimming, enlarging), and skin **lightening**;
- beauty applied by default: retouching is opt-in per pack, capped, and labelled in metadata;
- hair or sky segmentation (no live platform API exists, so a preview could not match the
  photograph);
- audio;
- paid packs, accounts, or download analytics.
