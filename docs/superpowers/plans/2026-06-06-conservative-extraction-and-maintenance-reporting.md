# Conservative Extraction + Maintenance Reporting — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the published filter list from blanking search/channels/playlists by publishing only the extension's real hide-CSS selectors (plus the curated supplement), and add a daily maintenance report cataloguing every selector the extension exposes that the list does not block, with day-over-day change tracking.

**Architecture:** Phase A refactors `extract.py` to separate cleaning (`clean_selector`) from publish policy (`guard_reason`), makes `extract_selectors` publish CSS-hide-derived selectors only, and migrates the genuinely-wanted hides into `data/supplement.txt` (scoped). Phase B adds `report.py` which reuses the harvesters to emit `data/candidates.json` + `data/MAINTENANCE.md`, wired into the daily `sync.yml`.

**Tech Stack:** Python 3.12 stdlib only, `uv` for all execution, `pytest`, `ruff`. Upstream extension cloned at `upstream/` (git-ignored).

**Spec:** `docs/superpowers/specs/2026-06-06-conservative-extraction-and-maintenance-reporting-design.md`

**Preconditions for the executor:**
- Work in the provided git worktree on the feature branch (the controller creates it). Confirm `git status` is clean before starting.
- `upstream/` must exist (git-ignored clone). If absent: `git clone --depth 1 https://github.com/KartikHalkunde/LockedIn-YT.git upstream`
- Use `uv` for everything (`uv run pytest`, `uv run ruff`, `uv run python …`). Never bare python/pytest.
- Append this trailer to every commit message: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Task 1: `extract.py` — split cleaning from policy (behavior-preserving)

**Files:**
- Modify: `lockedin_filters/extract.py` (the `OVER_BROAD` frozenset at lines 27-33; `normalize_selector` at lines 86-108)
- Test: `tests/test_extract.py` (add tests), `tests/test_lint.py` (update drift-guard)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_extract.py` (after the existing imports/tests, e.g. at the end of the file):

```python
from lockedin_filters.extract import clean_selector, guard_reason


def test_clean_selector_keeps_policy_selectors_but_drops_junk():
    # cleaning does NOT apply hide/keep policy — over-broad/guarded selectors survive cleaning
    assert clean_selector("ytd-app") == "ytd-app"
    assert clean_selector("ytd-video-renderer") == "ytd-video-renderer"
    # junk / non-selectors are dropped
    assert clean_selector("yt-navigate-finish") is None      # JS event name
    assert clean_selector("ytd-") is None                    # truncated token
    assert clean_selector("yt-") is None                     # bare token
    assert clean_selector("div") is None                     # non-YouTube
    assert clean_selector("   ") is None                     # empty
    # cleaning still strips lockedin guards + comments
    assert clean_selector('html[data-lockedin-x] ytd-comments:not([data-lockedin-hidden])') == "ytd-comments"


def test_guard_reason_labels_each_policy_set():
    assert guard_reason("ytd-app") == "over_broad"
    assert guard_reason("ytd-search") == "search_surface"
    assert guard_reason("ytd-video-renderer") == "content_renderer"
    assert guard_reason("#movie_player") == "protected"
    assert guard_reason("ytd-comments") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_extract.py::test_clean_selector_keeps_policy_selectors_but_drops_junk tests/test_extract.py::test_guard_reason_labels_each_policy_set -v`
Expected: FAIL — `cannot import name 'clean_selector'` / `'guard_reason'`.

- [ ] **Step 3: Rename the shell set and add a junk-identifier set**

In `lockedin_filters/extract.py`, replace the `OVER_BROAD` block (lines 20-33) with:

```python
# Over-broad page/app/nav shells that contain the player, the protected side panels,
# and/or core navigation. Harvested from the extension's detection probes
# (`document.querySelector('ytd-app')` etc.), never from hide-intents — hiding any of
# these would blank the whole app, break navigation, or take the video down with it.
# Matched against the *exact* normalized selector, so scoped descendants like
# `ytd-browse[page-subtype="home"] #primary` are unaffected.
OVER_BROAD_SHELLS = frozenset({
    "ytd-app", "ytm-app",
    "ytd-browse", "ytm-browse",
    "ytd-watch-flexy", "ytm-watch",
    "ytd-page-manager",
})

# JS identifiers / event names that look selector-ish (they contain a YT token) but
# match no DOM element — pure noise from addEventListener/querystring scans.
_JUNK_IDENTIFIERS = frozenset({
    "yt-navigate-finish", "yt-page-data-updated", "yt-page-type-changed",
})
```

- [ ] **Step 4: Replace `normalize_selector` with `clean_selector` + `guard_reason` + a thin `normalize_selector`**

In `lockedin_filters/extract.py`, replace the whole `normalize_selector` function (lines 86-108) with:

```python
def clean_selector(selector: str) -> str | None:
    """Clean a harvested selector to its normalized form, or None if it is not a usable
    YouTube selector (empty, a junk JS identifier, a bare/truncated token, or non-YT).

    Cleaning ONLY — it applies no hide/keep policy. Use guard_reason() for policy."""
    sel = selector.strip()
    sel = _CSS_COMMENT.sub(" ", sel)
    sel = _ANCESTOR.sub("", sel)
    sel = _NOT_GUARD.sub("", sel)
    sel = _ATTR_GUARD.sub("", sel)
    sel = _WS.sub(" ", sel).strip()
    if not sel:
        return None
    if sel in _JUNK_IDENTIFIERS:
        return None
    # Reject bare/truncated token fragments like `ytd-` or a lone `yt-` that slipped in
    # from a `tagName.startsWith('ytd-')` probe — these are not real elements.
    if sel in YT_TOKENS or sel.endswith("-"):
        return None
    if not any(tok in sel for tok in YT_TOKENS):
        return None
    return sel


def guard_reason(sel: str) -> str | None:
    """Why a cleaned selector must NOT be published as a hide rule, or None if it is safe.

    Returns one of: 'over_broad', 'search_surface', 'content_renderer', 'protected'."""
    if sel in OVER_BROAD_SHELLS:
        return "over_broad"
    if sel in SEARCH_SURFACES:
        return "search_surface"
    if sel in CONTENT_RENDERERS:
        return "content_renderer"
    low = sel.lower()
    if any(p.lower() in low for p in PROTECTED_SUBSTRINGS):
        return "protected"
    return None


def normalize_selector(selector: str) -> str | None:
    """Clean one harvested selector and apply publish policy. Return the normalized
    selector, or None if it should be skipped (junk, over-broad, protected, etc.)."""
    sel = clean_selector(selector)
    if sel is None or guard_reason(sel) is not None:
        return None
    return sel
```

- [ ] **Step 5: Run extract tests to verify they pass**

Run: `uv run pytest tests/test_extract.py -v`
Expected: PASS — the two new tests plus all existing `normalize_selector` tests (behavior is unchanged).

- [ ] **Step 6: Update the lint drift-guard to cover the renamed shell set**

In `tests/test_lint.py`, find `test_lint_guard_sets_mirror_extract` (currently asserts CONTENT_RENDERERS + SEARCH_SURFACES parity). Replace its body's assertions with:

```python
    assert lint.CONTENT_RENDERERS == extract.CONTENT_RENDERERS
    assert lint.SEARCH_SURFACES == extract.SEARCH_SURFACES
    assert lint.OVER_BROAD_SHELLS == extract.OVER_BROAD_SHELLS
```

- [ ] **Step 7: Run the full suite + ruff**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all pass; ruff `All checks passed!`. (If ruff flags the now-unused nothing — there should be none.)

- [ ] **Step 8: Commit**

```bash
git add lockedin_filters/extract.py tests/test_extract.py tests/test_lint.py
git commit -m "refactor: split extract cleaning (clean_selector) from policy (guard_reason)"
```
(Append the Co-Authored-By trailer.)

---

## Task 2: `extract_selectors` publishes hide-CSS only

**Files:**
- Modify: `lockedin_filters/extract.py` (`extract_selectors` at lines 163-180)
- Test: `tests/test_extract.py` (replace `test_extract_selectors_integration` at lines 132-146)

- [ ] **Step 1: Update the integration test to expect CSS-only output**

In `tests/test_extract.py`, replace the entire `test_extract_selectors_integration` function (lines 132-146) with:

```python
def test_extract_selectors_publishes_css_hides_only(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "index.js").write_text(
        'x.textContent = `ytd-reel-shelf-renderer { display:none !important; }`;\n'   # real hide-CSS
        'y.textContent = `#movie_player { filter:none !important; }`;\n'              # protected -> skipped
        'z.textContent = `.keep { visibility:visible !important; }`;\n'              # restore -> skipped
        "const s = 'ytd-comments'; toggle('img');\n"                                 # string anchors -> NOT published
        "document.querySelector('ytd-video-renderer');\n"                            # string anchor -> NOT published
    )
    result = extract_selectors(content)
    assert "ytd-reel-shelf-renderer" in result      # published: from real hide-CSS
    assert "ytd-comments" not in result             # string anchor only -> not published
    assert "ytd-video-renderer" not in result       # string anchor only -> not published
    assert "#movie_player" not in result            # protected
    assert ".keep" not in result                    # restore block
    assert "img" not in result                      # non-YouTube
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_extract.py::test_extract_selectors_publishes_css_hides_only -v`
Expected: FAIL — `ytd-comments` and `ytd-video-renderer` are currently published (the string harvest still runs).

- [ ] **Step 3: Drop the string harvest from `extract_selectors`**

In `lockedin_filters/extract.py`, replace the entire `extract_selectors` function (lines 163-180) with:

```python
def extract_selectors(upstream_dir: Path) -> set[str]:
    """Harvest and normalize hide-selectors from the upstream clone.

    Only selectors from the extension's real CSS hide-blocks (`display:none {…}`) are
    published — these carry genuine, well-scoped hide intent. Selectors that appear only
    as querySelector/closest string ANCHORS are deliberately NOT published (they are
    over-broad and blank whole pages); report.py surfaces them as maintenance candidates.
    """
    selectors: set[str] = set()
    for path in iter_js_files(upstream_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for sel_part, decl in harvest_css_blocks(text):
            if not is_hide_block(decl):
                continue
            for piece in sel_part.split(","):
                norm = normalize_selector(piece)
                if norm:
                    selectors.add(norm)
    return selectors
```

(The `harvest_string_selectors` function stays in the module — report.py uses it.)

- [ ] **Step 4: Run extract tests + full suite + ruff**

Run: `uv run pytest tests/test_extract.py -v && uv run pytest -q && uv run ruff check .`
Expected: all pass; ruff clean. (`harvest_string_selectors` is now unused by `extract_selectors` but still referenced by its own test and, later, report.py — ruff will NOT flag a module-level function as unused.)

- [ ] **Step 5: Commit**

```bash
git add lockedin_filters/extract.py tests/test_extract.py
git commit -m "fix: publish only hide-CSS selectors, not querySelector anchors"
```
(Append the Co-Authored-By trailer.)

---

## Task 3: Migrate wanted hides into `data/supplement.txt`

**Files:**
- Modify: `data/supplement.txt` (append new sections)

- [ ] **Step 1: Append the migrated rules**

Append the following to the END of `data/supplement.txt` (after the existing section 8). Keep all existing rules unchanged.

```
! --- 9. SUBSCRIPTIONS & MOBILE FEEDS (scoped; channels/search/playlists stay visible) ---
youtube.com##ytd-browse[page-subtype="subscriptions"] #primary
youtube.com##ytm-browse[page-subtype="home"] ytm-feed
youtube.com##ytm-browse[page-subtype="subscriptions"] ytm-feed

! --- 10. NAVIGATION CHROME (whole sidebar + mobile bottom bar) ---
youtube.com##ytd-guide-renderer
youtube.com##ytd-mini-guide-renderer
youtube.com##ytm-pivot-bar-renderer

! --- 11. WATCH RECOMMENDATIONS & COMMENTS (mobile) ---
youtube.com##ytm-watch-next-secondary-results-renderer
youtube.com##ytm-comments-section-renderer

! --- 12. ADS & PROMOS ---
youtube.com##ytd-display-ad-renderer
youtube.com##ytd-ad-slot-renderer
youtube.com##ytd-in-feed-ad-layout-renderer
youtube.com##ytd-promoted-sparkles-web-renderer
youtube.com##ytd-primetime-promo-renderer
youtube.com##ytd-statement-banner-renderer
```

- [ ] **Step 2: Verify every supplement line still parses**

Run: `uv run pytest tests/test_supplement.py -q`
Expected: PASS (the supplement parse test runs after build.py exists — it asserts every rule line is parseable).

- [ ] **Step 3: Verify none of the new rules trip a guard (would mean a typo)**

Run:
```bash
uv run python -c "
from lockedin_filters.build import load_supplement_selectors
from lockedin_filters.extract import guard_reason
bad=[(s,guard_reason(s)) for s in load_supplement_selectors('data/supplement.txt') if guard_reason(s)]
print('guarded supplement selectors (expect none):', bad)
"
```
Expected: `guarded supplement selectors (expect none): []`. (If a new rule is guarded, it would be flagged by lint and dropped — fix the rule.)

- [ ] **Step 4: Commit**

```bash
git add data/supplement.txt
git commit -m "feat: migrate subscriptions/nav/recs/ads hides into curated supplement"
```
(Append the Co-Authored-By trailer.)

---

## Task 4: Regenerate the list and verify Phase A

**Files:**
- Modify (regenerated): `dist/lockedin-youtube.txt`, `data/upstream-selectors.snapshot.json`

- [ ] **Step 1: Full suite + ruff green; ensure upstream present**

Run:
```bash
uv run pytest -q && uv run ruff check .
[ -d upstream/.git ] && echo present || git clone --depth 1 https://github.com/KartikHalkunde/LockedIn-YT.git upstream
```
Expected: all pass; `present` or fresh clone.

- [ ] **Step 2: Rebuild + lint gate**

Run:
```bash
BUILD_DATE=2026.06.06 uv run python -m lockedin_filters.build --upstream upstream
uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt --supplement data/supplement.txt
```
Expected: `Wrote dist/lockedin-youtube.txt (N lines).` then `Lint passed.` (exit 0).

- [ ] **Step 3: Verify NO page-blanking bare renderers remain**

Run:
```bash
grep -nE '^youtube\.com##(ytd-two-column-browse-results-renderer|ytd-rich-grid-renderer|ytd-rich-grid-row|ytd-rich-item-renderer|ytd-section-list-renderer|ytd-shelf-renderer|ytd-video-renderer|ytd-item-section-renderer|ytd-channel-renderer|ytd-playlist-renderer|ytd-playlist-panel-renderer|yt-lockup-view-model|ytm-feed|ytm-rich-grid-renderer|ytm-rich-item-renderer|ytm-item-section-renderer|ytm-video-with-context-renderer)$' dist/lockedin-youtube.txt || echo "NONE (good)"
```
Expected: `NONE (good)`. If any line prints, STOP and report.

- [ ] **Step 4: Verify the hidden set IS represented (scoped where needed)**

Run:
```bash
for sel in \
  'ytd-browse[page-subtype="home"] #primary' \
  'ytd-browse[page-subtype="subscriptions"] #primary' \
  '##ytd-guide-renderer' \
  '##ytm-pivot-bar-renderer' \
  '##ytd-comments' \
  '###related' \
  '##ytd-display-ad-renderer' ; do
  grep -qF "$sel" dist/lockedin-youtube.txt && echo "OK  $sel" || echo "MISSING  $sel"
done
```
Expected: all `OK`. If any `MISSING`, STOP and report.

- [ ] **Step 5: Verify scoped search-cleanup survives + floor intact**

Run:
```bash
grep -qF 'ytd-search ytd-video-renderer:has([href^="/shorts/"])' dist/lockedin-youtube.txt && echo "scoped-search OK" || echo "scoped-search MISSING"
uv run python -c "from lockedin_filters.build import load_supplement_selectors, canonical_selector, selector_of; supp=load_supplement_selectors('data/supplement.txt'); pub={canonical_selector(selector_of(l)) for l in open('dist/lockedin-youtube.txt') if selector_of(l)}; print('floor', len(supp), 'MISSING', [s for s in supp if canonical_selector(s) not in pub])"
```
Expected: `scoped-search OK`; `floor <N> MISSING []`.

- [ ] **Step 6: Commit the regenerated artifacts**

Confirm only dist/data changed, then commit:
```bash
git status --porcelain dist data
git add dist/lockedin-youtube.txt data/upstream-selectors.snapshot.json
git commit -m "build: regenerate list (conservative hide-CSS extraction + migrated supplement)"
```
(Append the Co-Authored-By trailer. If `git status` shows no dist/data change, STOP and report — that contradicts the diagnosis.)

---

## Task 5: `report.py` — candidate harvesting core

**Files:**
- Create: `lockedin_filters/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_report.py`:

```python
from lockedin_filters.report import (
    harvest_candidates, annotate, diff_candidates, published_selectors,
)


def _write(tmp_path):
    d = tmp_path / "up"
    (d / "content").mkdir(parents=True)
    (d / "content" / "index.js").write_text(
        'x.textContent = `ytd-reel-shelf-renderer { display:none !important; }`;\n'  # css hide
        "document.querySelector('ytd-video-renderer');\n"                            # string anchor (over-broad)
        "const s = 'ytd-search ytd-shelf-renderer';\n"                               # string anchor (scoped, safe)
    )
    return d


def test_harvest_candidates_tags_source_scoped_and_guard(tmp_path):
    cands = {c["selector"]: c for c in harvest_candidates(_write(tmp_path))}
    assert cands["ytd-reel-shelf-renderer"]["sources"] == ["css"]
    assert cands["ytd-reel-shelf-renderer"]["guard"] is None
    assert cands["ytd-video-renderer"]["sources"] == ["string"]
    assert cands["ytd-video-renderer"]["guard"] == "content_renderer"
    assert cands["ytd-video-renderer"]["scoped"] is False
    assert cands["ytd-search ytd-shelf-renderer"]["scoped"] is True


def test_annotate_sets_published_and_in_supplement():
    cands = [{"selector": "ytd-comments", "sources": ["string"], "scoped": False, "guard": None},
             {"selector": "ytd-x", "sources": ["string"], "scoped": False, "guard": None}]
    out = {c["selector"]: c for c in annotate(cands, published={"ytd-comments"}, supplement={"ytd-comments"})}
    assert out["ytd-comments"]["published"] is True
    assert out["ytd-comments"]["in_supplement"] is True
    assert out["ytd-x"]["published"] is False
    assert out["ytd-x"]["in_supplement"] is False


def test_diff_candidates_reports_added_and_removed():
    d = diff_candidates(current={"a", "b"}, previous={"b", "c"})
    assert d == {"added": ["a"], "removed": ["c"]}


def test_published_selectors_reads_dist(tmp_path):
    dist = tmp_path / "d.txt"
    dist.write_text("! header\nyoutube.com##ytd-comments\nyoutube.com#?#ytd-x:contains(Hi)\n")
    pub = published_selectors(dist)
    assert "ytd-comments" in pub
    assert "ytd-x:has-text(Hi)" in pub   # canonicalized from the #?# twin
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_report.py -v`
Expected: FAIL — `No module named 'lockedin_filters.report'`.

- [ ] **Step 3: Create `lockedin_filters/report.py` core**

Create `lockedin_filters/report.py`:

```python
"""Generate the maintenance report: a catalog of every selector the upstream extension
references that the published list does NOT block, plus a day-over-day change summary.

Observability only — never gates publishing. Pure stdlib.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import extract
from .build import canonical_selector, load_supplement_selectors, selector_of

# A selector is "scoped" if it has structure beyond a single component name.
_SCOPED_CHARS = set(" >[]:(),+~")


def _is_scoped(sel: str) -> bool:
    return any(ch in _SCOPED_CHARS for ch in sel)


def harvest_candidates(upstream_dir: Path) -> list[dict]:
    """Every cleaned YouTube selector the extension references — from BOTH the CSS
    hide-blocks and the querySelector string anchors — annotated with source(s), whether
    it is scoped, and its guard risk (None = safe to publish). Sorted by selector."""
    css: set[str] = set()
    strs: set[str] = set()
    for path in extract.iter_js_files(upstream_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for sel_part, decl in extract.harvest_css_blocks(text):
            if not extract.is_hide_block(decl):
                continue
            for piece in sel_part.split(","):
                s = extract.clean_selector(piece)
                if s:
                    css.add(s)
        for raw in extract.harvest_string_selectors(text):
            for piece in raw.split(","):
                s = extract.clean_selector(piece)
                if s:
                    strs.add(s)
    candidates: list[dict] = []
    for sel in sorted(css | strs):
        sources = []
        if sel in css:
            sources.append("css")
        if sel in strs:
            sources.append("string")
        candidates.append({
            "selector": sel,
            "sources": sources,
            "scoped": _is_scoped(sel),
            "guard": extract.guard_reason(sel),
        })
    return candidates


def annotate(candidates: list[dict], published: set[str], supplement: set[str]) -> list[dict]:
    """Add `published` and `in_supplement` booleans (compared on canonical selector)."""
    pub = {canonical_selector(s) for s in published}
    supp = {canonical_selector(s) for s in supplement}
    out: list[dict] = []
    for c in candidates:
        canon = canonical_selector(c["selector"])
        out.append({**c, "published": canon in pub, "in_supplement": canon in supp})
    return out


def diff_candidates(current: set[str], previous: set[str]) -> dict:
    return {"added": sorted(current - previous), "removed": sorted(previous - current)}


def published_selectors(dist_path: Path) -> set[str]:
    """Canonical-form selectors currently in the published list."""
    out: set[str] = set()
    for line in Path(dist_path).read_text(encoding="utf-8").splitlines():
        sel = selector_of(line)
        if sel:
            out.add(canonical_selector(sel))
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_report.py -v`
Expected: PASS (all four tests).

- [ ] **Step 5: Run full suite + ruff**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all pass; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add lockedin_filters/report.py tests/test_report.py
git commit -m "feat: report core — harvest/annotate/diff selector candidates"
```
(Append the Co-Authored-By trailer.)

---

## Task 6: `report.py` — rendering + CLI

**Files:**
- Modify: `lockedin_filters/report.py` (add rendering + `main`)
- Test: `tests/test_report.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_report.py`:

```python
from lockedin_filters.report import render_json, render_markdown


def _annotated():
    return [
        {"selector": "ytd-reel-shelf-renderer", "sources": ["css"], "scoped": False,
         "guard": None, "published": True, "in_supplement": False},
        {"selector": "ytd-video-renderer", "sources": ["string"], "scoped": False,
         "guard": "content_renderer", "published": False, "in_supplement": False},
        {"selector": "ytd-cool-new-renderer", "sources": ["css"], "scoped": False,
         "guard": None, "published": False, "in_supplement": False},
    ]


def test_render_json_is_valid_sorted_array():
    import json
    data = json.loads(render_json(_annotated()))
    assert isinstance(data, list) and len(data) == 3
    assert data[0]["selector"] == "ytd-reel-shelf-renderer"


def test_render_markdown_has_counts_changes_and_warnings():
    md = render_markdown(_annotated(), {"added": ["ytd-cool-new-renderer"], "removed": []},
                         build_date="2026.06.06", upstream_sha="abc123")
    assert "abc123" in md and "2026.06.06" in md
    assert "ytd-cool-new-renderer" in md            # appears in "changes since last run"
    # unblocked candidates are listed; the over-broad one carries a warning, the safe one does not
    assert "ytd-video-renderer" in md
    assert "⚠" in md                                 # warning marker present for guarded candidate
    assert "ytd-reel-shelf-renderer" not in md.split("## Unblocked")[1]  # published -> not in unblocked list
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_report.py::test_render_json_is_valid_sorted_array tests/test_report.py::test_render_markdown_has_counts_changes_and_warnings -v`
Expected: FAIL — `cannot import name 'render_json'` / `'render_markdown'`.

- [ ] **Step 3: Add rendering + `main` to `report.py`**

Append to `lockedin_filters/report.py`:

```python
_GUARD_NOTE = {
    "over_broad": "⚠ over-broad page shell — scope before adding",
    "search_surface": "⚠ search surface — would break search",
    "content_renderer": "⚠ shared content renderer — would blank search",
    "protected": "⚠ protected element — do not hide",
}


def render_json(annotated: list[dict]) -> str:
    return json.dumps(annotated, indent=2) + "\n"


def _bucket(sources: list[str]) -> str:
    if "css" in sources and "string" in sources:
        return "both"
    return "css" if "css" in sources else "string"


def render_markdown(annotated: list[dict], diff: dict, *, build_date: str, upstream_sha: str) -> str:
    unblocked = [c for c in annotated if not c["published"]]
    total = len(annotated)
    pub = sum(1 for c in annotated if c["published"])
    insupp = sum(1 for c in annotated if c["in_supplement"])
    out: list[str] = []
    out.append("# Maintenance Report")
    out.append("")
    out.append(f"- Generated: {build_date}")
    out.append(f"- Upstream commit: {upstream_sha}")
    out.append(
        f"- Harvested: {total} | published: {pub} | in supplement: {insupp} "
        f"| unblocked candidates: {len(unblocked)}"
    )
    out.append("")
    out.append("## Changes since last run")
    out.append("")
    out.append("**New upstream selectors:**" if diff["added"] else "_No new selectors._")
    for s in diff["added"]:
        out.append(f"- `{s}`")
    out.append("")
    out.append("**Removed upstream selectors:**" if diff["removed"] else "_No removed selectors._")
    for s in diff["removed"]:
        out.append(f"- `{s}`")
    out.append("")
    out.append("## Unblocked candidates")
    out.append("")
    out.append(
        "Selectors the extension references that your list does NOT block. Add the ones "
        "you want to `data/supplement.txt`. ⚠ marks over-broad/protected selectors — scope "
        "them before adding or they may blank a page."
    )
    out.append("")
    groups = (
        ("css", "From real hide-CSS (usually safe to adopt)"),
        ("both", "From both hide-CSS and query-anchors"),
        ("string", "From query-anchors only (often over-broad — scope before adding)"),
    )
    for key, title in groups:
        rows = [c for c in unblocked if _bucket(c["sources"]) == key]
        if not rows:
            continue
        out.append(f"### {title}")
        for c in rows:
            note = _GUARD_NOTE.get(c["guard"], "")
            out.append(f"- `{c['selector']}`" + (f"  {note}" if note else ""))
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the LockedIn YouTube maintenance report.")
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--supplement", default="data/supplement.txt")
    parser.add_argument("--dist", default="dist/lockedin-youtube.txt")
    parser.add_argument("--candidates", default="data/candidates.json")
    parser.add_argument("--out", default="data/MAINTENANCE.md")
    parser.add_argument("--build-date", required=True)
    parser.add_argument("--upstream-sha", default="unknown")
    args = parser.parse_args(argv)

    candidates = harvest_candidates(Path(args.upstream))
    published = published_selectors(Path(args.dist))
    supplement = load_supplement_selectors(args.supplement)
    annotated = annotate(candidates, published, supplement)

    current = {c["selector"] for c in candidates}
    cand_path = Path(args.candidates)
    previous: set[str] = set()
    if cand_path.exists():
        try:
            previous = {c["selector"] for c in json.loads(cand_path.read_text(encoding="utf-8"))}
        except (ValueError, KeyError, TypeError):
            previous = set()
    diff = diff_candidates(current, previous)

    cand_path.parent.mkdir(parents=True, exist_ok=True)
    cand_path.write_text(render_json(annotated), encoding="utf-8")
    Path(args.out).write_text(
        render_markdown(annotated, diff, build_date=args.build_date, upstream_sha=args.upstream_sha),
        encoding="utf-8",
    )
    print(f"Wrote {args.candidates} and {args.out}: {len(annotated)} harvested, "
          f"{sum(1 for c in annotated if not c['published'])} unblocked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_report.py -v`
Expected: PASS (all report tests).

- [ ] **Step 5: Run full suite + ruff**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all pass; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add lockedin_filters/report.py tests/test_report.py
git commit -m "feat: report rendering (json + markdown) and CLI"
```
(Append the Co-Authored-By trailer.)

---

## Task 7: Generate initial report + wire into `sync.yml`

**Files:**
- Create (generated): `data/candidates.json`, `data/MAINTENANCE.md`
- Modify: `.github/workflows/sync.yml` (add a report step + extend the commit `git add`)

- [ ] **Step 1: Generate the initial report artifacts**

Run (upstream must be present from Task 4):
```bash
uv run python -m lockedin_filters.report \
  --upstream upstream --supplement data/supplement.txt \
  --dist dist/lockedin-youtube.txt \
  --candidates data/candidates.json --out data/MAINTENANCE.md \
  --build-date 2026.06.06 --upstream-sha "$(git -C upstream rev-parse HEAD)"
```
Expected: `Wrote data/candidates.json and data/MAINTENANCE.md: <N> harvested, <M> unblocked.`

- [ ] **Step 2: Sanity-check the artifacts**

Run:
```bash
uv run python -c "import json; d=json.load(open('data/candidates.json')); print('candidates', len(d), 'valid json')"
grep -c '^- ' data/MAINTENANCE.md
grep -q '## Unblocked candidates' data/MAINTENANCE.md && echo "md sections OK"
```
Expected: candidates count printed; MAINTENANCE.md has list items and the Unblocked section.

- [ ] **Step 3: Add the report step to `sync.yml`**

In `.github/workflows/sync.yml`, find the `Lint gate (no publish on failure)` step and the `Commit if changed` step. Insert a new step BETWEEN them:

```yaml
      - name: Maintenance report
        run: |
          uv run python -m lockedin_filters.report \
            --upstream upstream --supplement data/supplement.txt \
            --dist dist/lockedin-youtube.txt \
            --candidates data/candidates.json --out data/MAINTENANCE.md \
            --build-date "$(date -u +%Y.%m.%d)" \
            --upstream-sha "$(git -C upstream rev-parse HEAD)"
```

- [ ] **Step 4: Extend the commit step's `git add`**

In `.github/workflows/sync.yml`, in the `Commit if changed` step, change this line:
```
            git add dist/lockedin-youtube.txt data/upstream-selectors.snapshot.json
```
to:
```
            git add dist/lockedin-youtube.txt data/upstream-selectors.snapshot.json data/candidates.json data/MAINTENANCE.md
```

- [ ] **Step 5: Validate the workflow YAML parses**

Run:
```bash
uv run --with pyyaml python -c "import yaml; s=yaml.safe_load(open('.github/workflows/sync.yml')); steps=[x.get('name','<uses>') for x in s['jobs']['sync']['steps']]; print(steps); assert steps.index('Maintenance report') < steps.index('Commit if changed')"
```
Expected: the step list prints and the assertion passes (report runs before commit).

- [ ] **Step 6: Commit**

```bash
git add data/candidates.json data/MAINTENANCE.md .github/workflows/sync.yml
git commit -m "ci: generate maintenance report in daily sync"
```
(Append the Co-Authored-By trailer.)

---

## Self-review notes (author)

- **Spec coverage:** A1 split → Task 1; A2 publish-CSS-only → Task 2; A3 supplement migration → Task 3; A4 lint/drift-guard → Task 1 step 6; regenerate+verify → Task 4. B1 report core → Task 5; B1 rendering+`annotate`/`diff` → Tasks 5–6; B2 artifacts → Tasks 6–7; B3 CLI+sync wiring → Tasks 6–7. Testing/verification → Tasks 4, 5, 6, 7 steps. Manual on-device acceptance (spec #8) is called out as out-of-band.
- **Placeholder scan:** none — every code/command step is concrete.
- **Type/name consistency:** `clean_selector`/`guard_reason`/`normalize_selector` signatures are consistent across Tasks 1, 5; `OVER_BROAD_SHELLS` rename applied in Task 1 and asserted in the drift-guard (Task 1 step 6); `harvest_candidates`/`annotate`/`diff_candidates`/`published_selectors`/`render_json`/`render_markdown`/`main` names match between report.py (Tasks 5–6) and their tests; the report CLI flag names in Task 6 `main` match the invocations in Task 7 steps 1 & 3.
- **Guard reuse:** `guard_reason` labels (`over_broad`/`search_surface`/`content_renderer`/`protected`) are identical in extract.py (Task 1) and the `_GUARD_NOTE` keys (Task 6).
```
