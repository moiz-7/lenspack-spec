# Publishing `lenspack-spec`

**Status: published.** The repo is live at <https://github.com/moiz-7/lenspack-spec> and the app's
index URL returns 200:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  https://raw.githubusercontent.com/moiz-7/lenspack-spec/main/index.json
```

This document is about **maintaining** it: the gallery, the signing keys, the pip package, the
Action, namespaces and hosting. The original first-publish notes are at the bottom.

**Three things only the owner can do**, each with steps below:

1. [Generate the index-signing keys](#index-signing-one-time-setup) and pin the public halves.
2. [Register the PyPI trusted publisher](#the-pip-package-lenspack) for `lenspack`.
3. [Point a domain at GitHub Pages](#hosting-our-own-domain-on-github-pages-later), when wanted.

---

## Repository layout — read this before moving files

`lenspack-spec/` is a **standalone repository** that also lives inside the Lens working tree at
`Lens/lenspack-spec/`, so the Python validator stays next to the Swift loader it mirrors. The
Lens repo **gitignores** `lenspack-spec/` and does not track it; commit and push from this
folder only.

> ⚠️ **Corrected 2026-08.** A nested `.git` inside a folder the parent repo tracks turns into a
> gitlink on the next `git add -A` and silently drops the files from the parent. If you set this
> up fresh: untrack it in the parent first (`git rm -r --cached lenspack-spec` + `.gitignore`).

| Path | What it is |
|---|---|
| `SPEC.md` | The format: normative text and maths |
| `conformance/limits.json` | Every limit and enumeration; both validators read it |
| `conformance/cases/` | Valid and invalid packs with the result every reader must give (`tools/gen_conformance.py`) |
| `conformance/goldens/` | Reference numbers for colour and effect maths (`tools/gen_goldens.py` from `lenspack/reference.py`) |
| `lenspack/` | The pip package: validator, packer, Ed25519 verifier, CLI |
| `validator/validate_lenspack.py` | The same validator, runnable from a checkout |
| `packs/` | The gallery's packs, as folders (`tools/gen_catalogue.py` drew the starter set) |
| `dist/`, `index.json` | Built by `tools/build_index.py`; never edited by hand |
| `index.json.sig`, `index-keys.json` | The index signature (written by CI) and the public keys |
| `catalogue.json` | Curation: `featured` packs and the `baseURL` archives are served from |
| `namespaces.json` | Which GitHub logins may publish under which `@author` |

## Making a change

```bash
cd /Users/moizsaeed/Documents/Developer/Lens/lenspack-spec
python3 -m pytest -q tests              # conformance, goldens, signing, namespaces, CLI
git add <paths> && git commit -m "..." && git push
```

**Limits live in one file: `conformance/limits.json`.** To change a limit or add vocabulary:

1. Edit `conformance/limits.json` (and `schema/lenspack-4.schema.json` if the shape changes), and
   write the rule and its maths into `SPEC.md`. A vocabulary addition needs both — §12 of the spec
   says what will never be added.
2. Add cases to `tools/gen_conformance.py` (valid and invalid, with the codes), run it; if maths
   changed, extend `lenspack/reference.py` and run `tools/gen_goldens.py`. Then `pytest`.
3. Commit and push here, then **vendor into the app**: copy `conformance/` (cases, goldens and
   limits) over `Lens/LensTests/Conformance/conformance.bundle/` and write this repo's commit sha
   into `Lens/LensTests/Conformance/VERSION`. The app's `LensPackConformanceTests` runs every case
   through `LensPackValidator`, and its colour and effect tests read the goldens; they fail until
   the app matches.

## Adding a look to the in-app gallery

- **A full pack:** a v4 folder at `packs/<author>.<slug>.lenspack/` (manifest with `id`, semver
  `version` and `license`), then `python3 tools/build_index.py`. It validates the pack, writes a
  reproducible zip to `dist/`, regenerates `index.json` and raises its `sequence`.
- **A bare cube:** put the `.cube` in `examples/`, add a version-1 style entry to `index.json`,
  then run `tools/build_index.py` to fill in the rest.
- **Featured:** add the pack's id to `catalogue.json` → `featured`.
- **Creators** open a pull request. CI checks the pack validates and that its `@author`
  namespace belongs to the PR's author (`namespaces.json`); a new creator claims a free namespace
  for their own login in the same PR. `@lens`, `@lenspack-spec`, `@local` and `@conformance` are
  reserved. Review is for taste and rights: original, honestly described, no trademarks.

On merge, CI signs the new index (below). The app picks it up on the next gallery open.

**The starter catalogue** (`tools/gen_catalogue.py`, needs Pillow) draws every image in code and
computes every cube; it is CC0. The four `@lens/…` face looks are also bundled in the app: after
changing one, copy its `packs/lens.<slug>.lenspack/` folder over
`Lens/Lens/Resources/BundledLooks.bundle/lens.<slug>.lenspack/` and bump its `version`.

## Index signing: one-time setup

The gallery index is signed with Ed25519 (SPEC §10.1). Two keys:

| Key | Id | Lives | Used |
|---|---|---|---|
| Signing key K1 | `2026-sign` | password manager **and** the GitHub Environment secret | by CI on every merge |
| Rotation key K2 | `2026-rotate` | password manager **and** an offline encrypted backup | only to revoke K1 |

**No one but the owner ever sees either private key** — not an agent, not a collaborator, not a
log. The repository holds public keys only; `.gitignore` excludes `*.pem` and CI fails if a PEM
private-key header appears anywhere (`tools/scan_secrets.py`).

### 1. Generate the keys (on your Mac, inside an encrypted disk image)

macOS's LibreSSL may lack Ed25519 raw output, so use OpenSSL 3 from Homebrew.

```bash
# An encrypted, throwaway working volume (asks for a password; use a long one).
hdiutil create -size 20m -fs APFS -encryption AES-256 -volname LensKeys ~/LensKeys.dmg
hdiutil attach ~/LensKeys.dmg
cd /Volumes/LensKeys

brew install openssl@3            # once
O=$(brew --prefix openssl@3)/bin/openssl
$O genpkey -algorithm ed25519 -out index-sign-2026.pem
$O genpkey -algorithm ed25519 -out index-rotate-2026.pem

# The two PUBLIC keys, raw 32 bytes, base64 — these are what get pinned:
$O pkey -in index-sign-2026.pem   -pubout -outform DER | tail -c 32 | base64   # "2026-sign"
$O pkey -in index-rotate-2026.pem -pubout -outform DER | tail -c 32 | base64   # "2026-rotate"
```

### 2. Store the private keys

- **K1 (`index-sign-2026.pem`):** save the file's full text (including the BEGIN/END lines) in
  your password manager. Then in GitHub: *Settings → Environments → New environment* `release`;
  under *Deployment branches* choose *Selected branches* → `main`; under *Required reviewers* add
  yourself; under *Environment secrets* add `LENSPACK_INDEX_SIGNING_KEY` with the file's full
  text as the value.
- **K2 (`index-rotate-2026.pem`):** save it in your password manager, and copy it to an encrypted
  USB stick kept somewhere safe. It **never** goes into GitHub, CI or either repository.
- Then delete both files and the disk image:
  ```bash
  cd ~ && hdiutil detach /Volumes/LensKeys && rm -P ~/LensKeys.dmg
  ```

### 3. Pin the public keys (both repos, one commit each)

- Here, in `index-keys.json`:
  ```json
  {"keys": [
    {"id": "2026-sign",   "role": "signing",  "publicKey": "<base64 from step 1>"},
    {"id": "2026-rotate", "role": "rotation", "publicKey": "<base64 from step 1>"}
  ]}
  ```
- In the app, `Lens/Lens/FilmLooks/IndexSignature.swift` → `pinnedKeys`:
  ```swift
  static let pinnedKeys: [PinnedKey] = [
      PinnedKey(id: "2026-sign", publicKey: "<base64>", role: .signing),
      PinnedKey(id: "2026-rotate", publicKey: "<base64>", role: .rotation),
  ]
  ```
  From that build on, the gallery refuses an unsigned or tampered index and shows bundled looks
  only. (While `pinnedKeys` is empty it accepts the unsigned index, logs it, and says "Index
  signing not yet set up" in DEBUG builds.)

### 4. First signature

Push the `index-keys.json` commit. The `sign-index` workflow (*Actions → sign-index → Run
workflow* if it doesn't start on its own) waits for your approval in the `release` environment,
signs `index.json`, checks the signature against `index-keys.json`, and commits `index.json.sig`.
Check it locally:

```bash
python3 -m lenspack verify-index index.json --keys index-keys.json --strict
```

If `main` is branch-protected, allow GitHub Actions to push `index.json.sig` (a ruleset bypass
for the `github-actions` app), or the signing commit will be refused.

### Afterwards

- Every merge that changes `index.json` is signed automatically (after your approval).
- **Rollback protection:** `build_index.py` raises `sequence` with every change; the app refuses
  an index whose sequence is lower than one it already accepted.
- **If K1 leaks:** generate K3 the same way. Add `"2026-sign"` to `catalogue.json` →
  `revokeKeyIds` and run `tools/build_index.py`. Sign that index with **K2**, locally, from the
  USB copy inside an encrypted disk image as in step 1:
  ```bash
  pip install cryptography
  LENSPACK_INDEX_SIGNING_KEY="$(cat index-rotate-2026.pem)" python3 tools/sign_index.py --key-id 2026-rotate
  ```
  then delete the file again, and commit `index.json` with its `index.json.sig` (skip the
  workflow for this one commit, or it re-signs with K1). Replace the `release` secret with K3,
  pin K3 in both repos and ship an app update. Apps that saw the revocation never trust K1 again.

## The pip package (`lenspack`)

`pip install lenspack` gives `lenspack validate | pack | hash | verify-index`, with no
dependencies. It is published by `.github/workflows/publish-pypi.yml` through **PyPI trusted
publishing** (GitHub's OIDC token; no API token exists anywhere). One-time owner setup:

1. On <https://pypi.org>, *Your account → Publishing → Add a new pending publisher*: project
   `lenspack`, owner `moiz-7`, repository `lenspack-spec`, workflow `publish-pypi.yml`,
   environment `pypi`.
2. In GitHub, create the environment `pypi` (optionally with yourself as required reviewer).

To release: bump `version` in `pyproject.toml` and `lenspack/__init__.py`, commit, then
`git tag v1.0.0 && git push origin v1.0.0`. The workflow checks the tag matches the version,
runs the tests, builds and publishes.

## The GitHub Action (`moiz-7/lenspack-spec@v1`)

`action.yml` installs this repository's `lenspack` package from the action's own checkout and
validates the paths it is given. Creators use:

```yaml
- uses: moiz-7/lenspack-spec@v1
  with:
    path: "looks/*.lenspack"
```

Versioning: every release tag `vX.Y.Z` also moves the major tag, so `@v1` follows compatible
fixes:

```bash
git tag -f v1 v1.0.0 && git push -f origin v1
```

A breaking change to the action's inputs or outputs gets `v2`; `v1` stays where it is.

## Hosting: our own domain on GitHub Pages (later)

Today the app reads `https://raw.githubusercontent.com/moiz-7/lenspack-spec/main/index.json`,
which already sends `ETag` and `Cache-Control`. The app revalidates through the system URL cache
(no code change for a new host). To move to a domain you own:

1. *Settings → Pages*: deploy from branch `main`, folder `/` (root).
2. Add the custom domain (e.g. `looks.example.com`) there; create the DNS `CNAME` record it asks
   for; tick *Enforce HTTPS* once the certificate is issued.
3. Set `catalogue.json` → `baseURL` to `https://looks.example.com/` and run
   `tools/build_index.py` (every archive URL changes, so `sequence` rises and CI re-signs).
4. In the app, set `MarketplaceViewModel.defaultIndexURL` to `https://looks.example.com/index.json`
   and ship it. Keep the raw URL working (don't delete files) until old builds age out.

No analytics, ever: Pages logs are not ours to read, and nothing in the app identifies a user.

## Appendix — first-time publishing (for forks)

`MarketplaceViewModel.defaultIndexURL` in `Lens/Lens/FilmLooks/LensPackMarketplace.swift` points
at this repository; a fork changes it to its own `…/index.json` and verifies the URL returns
`200` before shipping. The parent repo *gitignores* `lenspack-spec/`; the alternative (vendoring
and `git subtree push`) is valid too, but never both.
