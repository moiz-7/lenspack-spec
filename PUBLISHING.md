# Publishing `lenspack-spec`

The app's Community Looks gallery reads `index.json` from this repository. Until it's
published, the remote fetch 404s — the gallery still works (it ships bundled content since
R20), it just can't offer anything beyond the built-in look.

Run these **from your machine**, in order. Nothing here is destructive; the only outward-
facing step is the final `push`.

## 1. One-time: install the GitHub CLI (optional but easiest)

```bash
brew install gh && gh auth login
```

If you'd rather not use `gh`, create an empty repo named `lenspack-spec` in the GitHub web
UI (no README, no .gitignore — this folder already has content) and skip to step 3.

## 2. Make it its own repository

`lenspack-spec/` is currently tracked inside the Lens repo. It should be standalone so
outside contributors can clone the format without the app source.

```bash
cd /Users/moizsaeed/Documents/Developer/Lens/lenspack-spec
git init -b main
git add -A
git commit -m "LensPack format spec v1-v5, validator, and starter packs"
```

## 3. Create the remote and push

With `gh` (creates the repo and pushes in one step):

```bash
gh repo create lenspack-spec --public --source=. --remote=origin --push
```

Without `gh` (after creating the empty repo in the web UI):

```bash
git remote add origin https://github.com/<your-username>/lenspack-spec.git
git push -u origin main
```

## 4. Point the app at it

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

## 5. Decide what the Lens repo does with this folder

Two reasonable options — pick one deliberately:

- **Keep the copy** (simplest): `lenspack-spec/` stays committed in the Lens repo as a
  vendored reference, and the published repo is the canonical one. Risk: they drift.
- **Remove it from the Lens repo** once published, and add a note pointing at the URL:
  ```bash
  cd /Users/moizsaeed/Documents/Developer/Lens
  git rm -r --cached lenspack-spec && echo "lenspack-spec/" >> .gitignore
  git commit -m "Move lenspack-spec to its own repository"
  ```
  Risk: the validator is no longer next to the app it mirrors, so version skew is easier
  to miss. **Recommendation: keep the copy** until the format stops changing, because the
  validator and the app's loader must stay in lockstep and they currently change together.

## 6. Growing it beyond one look

The gallery is only interesting with content. The cheapest path to a real catalogue:

1. Make 4–6 looks yourself with a real grading tool, validate each, add them to
   `examples/` and `index.json` (the validator prints the `sha256` each entry needs).
2. Open the repo to PRs with a short contribution rule in the README — the curation bar is
   already written there (original, tasteful, honestly described, no trademarks).
3. Only then consider recruiting outside creators. A store with one item reads as
   abandoned; a store with a dozen reads as early.
