# lenspack-spec

The open format for **LensPacks** — community-built looks for the Lens camera app.

A LensPack is **pure data, never code**: a color cube, a recipe of vetted effect nodes, and
face-anchored overlay images. The app applies your pack through its own audited pipeline —
the worst a pack can do is look ugly.

## Author a look in 60 seconds
1. Export a `.cube` LUT (2–65 points) from Resolve/Photoshop/anything.
2. AirDrop it to your iPhone → save into **Files → Lens → LensPacks**.
3. It's now a look in every mode, on the Camera Control button, and it survives relaunch.

Want a name/attribution, face stickers, or effect recipes? Make a `.lenspack` folder with a
`manifest.json` — see [SPEC.md](SPEC.md) and [examples/](examples/).

## Validate before publishing
```
python3 validator/validate_lenspack.py "examples/Sunset Fade.cube"
python3 validator/validate_lenspack.py examples/party-crown.lenspack
```
The validator mirrors the app's loader exactly: what passes here, loads there.

## Get listed in the in-app gallery
The app's **Community Looks** gallery reads [`index.json`](index.json) from this repository.
To list your look: open a PR adding your `.cube` under `examples/` (or host it at any HTTPS
URL) plus an index entry with its `sha256` (the validator prints it). Curation favors looks
that are original, tasteful, and honestly described. No trademarks in names.

## Principles (non-negotiable)
- Declarative only — the manifest gains vocabulary over time, never authority.
- Zero user annoyance: silent loading, no watermarks, no phoning home, opt-in discovery.
- The user's file system is the source of truth: delete the file, the look is gone.
