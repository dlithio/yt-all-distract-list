# Content-Renderer Search-Results Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the published filter list from blanking the YouTube search results page, while keeping all other aggressive hiding, by protecting shared content/result renderers from being hidden in their bare global form.

**Architecture:** Add an exact-match `CONTENT_RENDERERS` guard (the result cards/containers YouTube reuses on search) to `extract.py` so `normalize_selector` drops their bare form (scoped uses still pass), and mirror it into `lint.py` as a publish-gate backstop. Then regenerate the published artifacts and verify. This mirrors the existing `OVER_BROAD`/`SEARCH_SURFACES` exact-match guards. Home/subscriptions stay hidden because their *containers* are still hidden and container-hiding cascades to children; search survives because its container is not hidden.

**Tech Stack:** Python 3.12 stdlib only, `uv` for all execution, `pytest`, `ruff`. Upstream extension cloned at `upstream/` (git-ignored).

**Spec:** `docs/superpowers/specs/2026-06-06-search-content-renderer-protection-design.md`

**Preconditions for the executor:**
- Work in the repo root `/Users/danlithio/Github/yt-all-distract-list` on branch `main` (no worktree needed; this is a small fix on an already-merged codebase). Confirm `git status` is clean before starting.
- `upstream/` must exist (git-ignored clone). If absent, run: `git clone --depth 1 https://github.com/KartikHalkunde/LockedIn-YT.git upstream`
- Use `uv` for everything (`uv run pytest`, `uv run ruff`, `uv run python …`). Never bare python/pytest.
- Append this trailer to every commit message: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Task 1: `extract.py` — `CONTENT_RENDERERS` source guard

**Files:**
- Modify: `lockedin_filters/extract.py` (add a frozenset after the `SEARCH_SURFACES` block at lines 40-44; extend the guard check at line 86)
- Test: `tests/test_extract.py` (add two tests after `test_normalize_protects_bare_search_surfaces_but_allows_scoped` at line 50)

- [ ] **Step 1: Write the failing tests**

Add these two test functions to `tests/test_extract.py` immediately after the existing `test_normalize_protects_bare_search_surfaces_but_allows_scoped` function (it ends just before `def test_normalize_rejects_bare_and_truncated_tokens`):

```python
def test_normalize_protects_bare_content_renderers():
    # Result cards / containers YouTube reuses on the search page must never become
    # bare global hides (they would blank search results).
    for r in ("ytd-video-renderer", "ytd-item-section-renderer", "ytd-grid-video-renderer",
              "ytd-channel-renderer", "ytd-playlist-renderer", "ytd-playlist-video-renderer",
              "yt-lockup-view-model", "ytd-continuation-item-renderer",
              "ytm-item-section-renderer", "ytm-video-with-context-renderer",
              "ytm-grid-video-renderer"):
        assert normalize_selector(r) is None


def test_normalize_allows_scoped_content_renderers():
    # Scoped uses carry page context and stay allowed — e.g. stripping Shorts inside search.
    assert normalize_selector('ytd-search ytd-video-renderer:has([href^="/shorts/"])') == \
        'ytd-search ytd-video-renderer:has([href^="/shorts/"])'
    assert normalize_selector('[page-subtype="search"] ytd-video-renderer:has([href^="/shorts/"])') == \
        '[page-subtype="search"] ytd-video-renderer:has([href^="/shorts/"])'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_extract.py::test_normalize_protects_bare_content_renderers tests/test_extract.py::test_normalize_allows_scoped_content_renderers -v`
Expected: FAIL — `test_normalize_protects_bare_content_renderers` fails because the bare renderers currently normalize to themselves (not `None`). (The scoped test may already pass — that is fine; it guards against over-matching.)

- [ ] **Step 3: Add the `CONTENT_RENDERERS` frozenset**

In `lockedin_filters/extract.py`, the `SEARCH_SURFACES` block currently is (lines 40-44):

```python
SEARCH_SURFACES = frozenset({
    "ytd-search", "ytm-search",
    "ytd-searchbox", "ytm-searchbox",
    "ytd-two-column-search-results-renderer",
})
```

Insert the following immediately AFTER that closing `})` (i.e. between the `SEARCH_SURFACES` block and the `# Declarations that mean "hide"` comment):

```python

# Content/result renderers YouTube REUSES across pages — including the search results
# page. Their bare (unscoped) form must never become a global hide rule or it blanks
# search. Matched against the EXACT normalized selector, so SCOPED uses (e.g.
# `ytd-search ytd-video-renderer:has([href^="/shorts/"])`) are still allowed. Home and
# subscriptions stay hidden via their page CONTAINERS (ytm-feed,
# ytd-browse[page-subtype="home"] #primary, ytd-two-column-browse-results-renderer) —
# hiding a container cascades to these children regardless of this guard.
CONTENT_RENDERERS = frozenset({
    "ytd-video-renderer", "ytd-item-section-renderer", "ytd-grid-video-renderer",
    "ytd-channel-renderer", "ytd-playlist-renderer", "ytd-playlist-video-renderer",
    "yt-lockup-view-model", "ytd-continuation-item-renderer",
    "ytm-item-section-renderer", "ytm-video-with-context-renderer",
    "ytm-grid-video-renderer",
})
```

- [ ] **Step 4: Extend the guard check in `normalize_selector`**

In `lockedin_filters/extract.py`, find this line (currently line 86):

```python
    if sel in OVER_BROAD or sel in SEARCH_SURFACES:
```

Replace it with:

```python
    if sel in OVER_BROAD or sel in SEARCH_SURFACES or sel in CONTENT_RENDERERS:
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_extract.py -v`
Expected: PASS (all extract tests, including the two new ones).

- [ ] **Step 6: Commit**

```bash
git add lockedin_filters/extract.py tests/test_extract.py
git commit -m "fix: stop hiding shared content renderers (blanks search results)"
```
(Append the Co-Authored-By trailer.)

---

## Task 2: `lint.py` — `CONTENT_RENDERERS` publish-gate backstop

**Files:**
- Modify: `lockedin_filters/lint.py` (add a frozenset after the `SEARCH_SURFACES` block at lines 38-42; add a check after the search-surface check at lines 91-92)
- Test: `tests/test_lint.py` (add one test after `test_bare_search_surface_flagged_but_scoped_search_cleanup_ok` at line 79)

- [ ] **Step 1: Write the failing test**

Add this test function to `tests/test_lint.py` immediately after `test_bare_search_surface_flagged_but_scoped_search_cleanup_ok` (and before `test_allowlist_marker_rejected_as_invalid_prefix`):

```python
def test_bare_content_renderer_flagged_but_scoped_ok():
    bad = "! Title: x\n! Expires: 1 day\n! Version: 1\n!\nyoutube.com##ytd-video-renderer\n"
    assert any("shared content renderer" in e for e in lint_text(bad, set()))
    ok = ("! Title: x\n! Expires: 1 day\n! Version: 1\n!\n"
          'youtube.com##ytd-search ytd-video-renderer:has([href^="/shorts/"])\n')
    assert not any("shared content renderer" in e for e in lint_text(ok, set()))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_lint.py::test_bare_content_renderer_flagged_but_scoped_ok -v`
Expected: FAIL — the bare `ytd-video-renderer` is not yet flagged with `"shared content renderer"`.

- [ ] **Step 3: Add the `CONTENT_RENDERERS` frozenset**

In `lockedin_filters/lint.py`, the `SEARCH_SURFACES` block currently is (lines 37-42):

```python
# Publish-gate backstop for extract.py's SEARCH_SURFACES guard.
SEARCH_SURFACES = frozenset({
    "ytd-search", "ytm-search",
    "ytd-searchbox", "ytm-searchbox",
    "ytd-two-column-search-results-renderer",
})
```

Insert the following immediately AFTER that closing `})` (between it and the `# Only HIDE markers are valid` comment):

```python

# Content/result renderers reused on the search page. Their bare form must never be a
# global hide (it blanks search results). EXACT match, so scoped rules like
# `ytd-search ytd-video-renderer:has(...)` stay allowed. Publish-gate backstop for
# extract.py's CONTENT_RENDERERS guard.
CONTENT_RENDERERS = frozenset({
    "ytd-video-renderer", "ytd-item-section-renderer", "ytd-grid-video-renderer",
    "ytd-channel-renderer", "ytd-playlist-renderer", "ytd-playlist-video-renderer",
    "yt-lockup-view-model", "ytd-continuation-item-renderer",
    "ytm-item-section-renderer", "ytm-video-with-context-renderer",
    "ytm-grid-video-renderer",
})
```

- [ ] **Step 4: Add the gate check in `lint_text`**

In `lockedin_filters/lint.py`, find these lines (currently 91-92):

```python
        if sel in SEARCH_SURFACES:
            errors.append(f"targets protected search surface: {line}")
```

Insert the following immediately after them (same indentation, inside the per-line `for` loop):

```python
        if sel in CONTENT_RENDERERS:
            errors.append(f"targets shared content renderer (would hide search results): {line}")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_lint.py -v`
Expected: PASS (all lint tests, including the new one).

- [ ] **Step 6: Commit**

```bash
git add lockedin_filters/lint.py tests/test_lint.py
git commit -m "fix: lint gate rejects bare content renderers (search-results backstop)"
```
(Append the Co-Authored-By trailer.)

---

## Task 3: Regenerate the published list and verify

**Files:**
- Modify (regenerated): `dist/lockedin-youtube.txt`, `data/upstream-selectors.snapshot.json`

- [ ] **Step 1: Ensure the full suite + ruff are green first**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all tests pass; ruff `All checks passed!`. If not, STOP and report.

- [ ] **Step 2: Ensure upstream is present**

Run: `[ -d upstream/.git ] && echo present || git clone --depth 1 https://github.com/KartikHalkunde/LockedIn-YT.git upstream`
Expected: `present` (or a fresh clone completes).

- [ ] **Step 3: Rebuild the list (pin BUILD_DATE for a deterministic version line)**

Run: `BUILD_DATE=2026.06.06 uv run python -m lockedin_filters.build --upstream upstream`
Expected: prints `Wrote dist/lockedin-youtube.txt (N lines).`

- [ ] **Step 4: Run the lint gate**

Run: `uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt --supplement data/supplement.txt`
Expected: `Lint passed.` (exit 0).

- [ ] **Step 5: Verify the bare content renderers are GONE from dist**

Run:
```bash
grep -nE '^youtube\.com##(ytd-video-renderer|ytd-item-section-renderer|ytd-grid-video-renderer|ytd-channel-renderer|ytd-playlist-renderer|ytd-playlist-video-renderer|yt-lockup-view-model|ytd-continuation-item-renderer|ytm-item-section-renderer|ytm-video-with-context-renderer|ytm-grid-video-renderer)$' dist/lockedin-youtube.txt || echo "NONE (good)"
```
Expected: `NONE (good)`.

- [ ] **Step 6: Verify scoped search-cleanup + supplement floor survive**

Run:
```bash
grep -nF 'ytd-search ytd-video-renderer:has([href^="/shorts/"])' dist/lockedin-youtube.txt
uv run python -c "from lockedin_filters.build import load_supplement_selectors, canonical_selector, selector_of; supp=load_supplement_selectors('data/supplement.txt'); pub={canonical_selector(selector_of(l)) for l in open('dist/lockedin-youtube.txt') if selector_of(l)}; missing=[s for s in supp if canonical_selector(s) not in pub]; print('floor', len(supp), 'MISSING', missing)"
```
Expected: the scoped Shorts-in-search rule is present; `floor 46 MISSING []`.

- [ ] **Step 7: Verify the user's nav/feed hides still present**

Run:
```bash
grep -cE '^youtube\.com##(ytm-pivot-bar-item-renderer|ytd-guide-renderer|ytd-mini-guide-renderer|ytm-feed|ytd-rich-grid-renderer|ytd-two-column-browse-results-renderer|ytd-shelf-renderer)$' dist/lockedin-youtube.txt
```
Expected: `7`.

- [ ] **Step 8: Commit the regenerated artifacts**

First confirm only `dist/` and `data/` changed (no `upstream/`):
```bash
git status --porcelain dist data
```
Then:
```bash
git add dist/lockedin-youtube.txt data/upstream-selectors.snapshot.json
git commit -m "build: regenerate list without bare content-renderer rules"
```
(Append the Co-Authored-By trailer. If `git status` shows no changes to `dist`/`data` — meaning the bare rules were somehow already absent — STOP and report, because that contradicts the diagnosis.)

---

## Self-review notes (author)

- **Spec coverage:** §"The fix" item 1 → Task 1; item 2 → Task 2; §Verification criteria 1-7 → Task 3 steps 1,3,4,5,6,7 (criterion 8 is manual/on-device, called out in the spec and not automatable here). §"Deliberately NOT protected" is satisfied by *omission* — those names are absent from `CONTENT_RENDERERS`, so they stay hidden; the Task 3 step-7 grep confirms representative ones remain.
- **Placeholder scan:** none — every code/command step shows exact content.
- **Type/name consistency:** the `CONTENT_RENDERERS` member list is identical in Task 1, Task 2, and the Task 3 step-5 grep (11 entries: ytd-video-renderer, ytd-item-section-renderer, ytd-grid-video-renderer, ytd-channel-renderer, ytd-playlist-renderer, ytd-playlist-video-renderer, yt-lockup-view-model, ytd-continuation-item-renderer, ytm-item-section-renderer, ytm-video-with-context-renderer, ytm-grid-video-renderer). The error substring `"shared content renderer"` in Task 2 step 4 matches the assertion in Task 2 step 1.
