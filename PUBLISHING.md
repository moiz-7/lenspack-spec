# Publishing `lenspack-spec`

**Status: published.** The repo is live at
<https://github.com/moiz-7/lenspack-spec> and the app's index URL returns 200:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  https://raw.githubusercontent.com/moiz-7/lenspack-spec/main/index.json
```

This document is now about **maintaining** it. The original publishing steps are kept at the
bottom for anyone forking the format.

---

## Repository layout — read this before moving files

`lenspack-spec/` is a **standalone repository** that also lives inside the Lens working tree
at `Lens/lenspack-spec/`. That is deliberate: the Python validator must stay next to the
Swift loader it mirrors, because the two encode the same limits and drift silently when
separated.

To make that safe, the Lens repo **gitignores** `lenspack-spec/` and does not track it.

> ⚠️ **Corrected 2026-08.** An earlier version of this file told you to run `git init` inside
> `lenspack-spec/` while those files were still tracked by the Lens repo. That was wrong: a
> nested `.git` inside a tracked folder makes Git convert the folder to a **gitlink** on the
> next `git add -A`, silently dropping the file contents from the parent repo. If you are
> setting this up fresh, untrack it in the parent *first* (`git rm -r --cached lenspack-spec`
> plus a `.gitignore` entry), then initialise here.

## Making a change

Edit here, then commit and push from **this** folder — not from the Lens repo:

```bash
cd /Users/moizsaeed/Documents/Developer/Lens/lenspack-spec
git add -A && git commit -m "..." && git push
```

**Whenever you change a limit, change it in both places.** The validator and the app's loader
must agree, or a pack that validates will fail to load (or worse, load when it shouldn't):

| Concept | Validator | App |
|---|---|---|
| Cube size / file cap | `validator/validate_lenspack.py` (`CUBE_SIZES`, `MAX_CUBE_BYTES`) | `LensPackManager` (`allowedCubeSizes`, `maxCubeFileBytes`) |
| Overlay pixel cap, frame cap, fps range | `MAX_OVERLAY_PIXELS`, frame/fps checks | `maxOverlayPixels`, frame `prefix(23)`, fps clamp |
| Effect nodes | `EFFECTS` | `RecipeEffectSpec.Kind` |
| Anchors / blendshapes / requirements | `ANCHORS`, `BLENDSHAPES`, `REQUIREMENTS` | `FaceOverlaySpec.Anchor`, `BlendshapeTriggerSpec.Shape`, `FilterCapabilities.knownRequirements` |

A parity test that fails when these diverge is the right long-term fix; until it exists, this
table is the checklist.

## Adding a look to the in-app gallery

1. Put the `.cube` in `examples/`.
2. `python3 validator/validate_lenspack.py "examples/Your Look.cube"` — it prints the sha256.
3. Add an entry to `index.json` with that sha256 (the app verifies it before installing).
4. Commit and push. The app picks it up on the next gallery open — no app release needed.

---

## Appendix — first-time publishing (for forks)

### Point the app at it

`MarketplaceViewModel.defaultIndexURL` currently reads:

```
https://raw.githubusercontent.com/moiz-7/lenspack-spec/main/index.json
```

If your GitHub username is **not** `moiz-7`, update that constant in
`Lens/Lens/FilmLooks/LensPackMarketplace.swift` to match. Verify the URL resolves before
shipping:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  https://raw.githubusercontent.com/<your-username>/lenspack-spec/main/index.json
```

`200` means the gallery will now merge remote looks on top of the bundled one.

### Decide what the parent repo does with this folder

**Decided for this project (2026-08):** the parent repo *gitignores* `lenspack-spec/` and
this repo is the only place it is tracked — see "Repository layout" above. The working copy
stays inside the Lens tree so the validator and the app's loader sit side by side.

The alternative (vendoring the files in the parent and publishing via `git subtree push`)
is also valid and keeps a single history, but it cannot coexist with a nested `.git` —
pick one, never both.

### Growing it beyond one look

The gallery is only interesting with content. The cheapest path to a real catalogue:

1. Make 4–6 looks yourself with a real grading tool, validate each, add them to
   `examples/` and `index.json` (the validator prints the `sha256` each entry needs).
2. Open the repo to PRs with a short contribution rule in the README — the curation bar is
   already written there (original, tasteful, honestly described, no trademarks).
3. Only then consider recruiting outside creators. A store with one item reads as
   abandoned; a store with a dozen reads as early.
