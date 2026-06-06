# Design: Protect Shared Content Renderers (fix blank search results)

**Date:** 2026-06-06
**Status:** Approved approach (Option 1 of brainstorm), pending written-spec review.
**Builds on:** the LockedIn YouTube filter list already on `main` (`lockedin_filters/`, `data/supplement.txt`, `dist/lockedin-youtube.txt`).

## Problem

The published list (`dist/lockedin-youtube.txt`) blanks the YouTube **search results page**. The user's hard requirement is that search must remain usable (see video/channel/playlist results) while everything else stays aggressively hidden (home feed, subscriptions, Shorts, recommendations, comments, nav chrome, thumbnails).

## Root cause

`lockedin_filters/extract.py` harvests selectors from the upstream LockedIn-YT extension via two paths:

1. **CSS hide-blocks** — selectors inside injected `display:none {…}` rules. These reflect genuine "hide globally" intent. *None of the search-breakers come from here.*
2. **String literals** — selectors passed to `querySelector`/`closest`/`querySelectorAll`. The extension uses these as **anchors** for JavaScript page-context logic (e.g. "on the home page, hide this"), **not** as global hide intents.

`harvest_string_selectors` promotes *any* selector-shaped string literal into a global element-hide rule, discarding the extension's page-context. The result: **bare** (unscoped) result-card / container components that YouTube reuses across pages get hidden everywhere, including under search. Empirically, every search-breaker is a *bare, string-only* selector:

`ytd-video-renderer`, `ytd-item-section-renderer`, `ytd-channel-renderer`, `ytd-playlist-renderer`, `ytd-grid-video-renderer`, `yt-lockup-view-model`, `ytd-continuation-item-renderer`, and the mobile twins `ytm-item-section-renderer`, `ytm-video-with-context-renderer`, `ytm-grid-video-renderer`.

A static filter list cannot re-enable an element on one page after hiding it globally (uBO/AdGuard iOS lack reliable ancestor-scoped exceptions), so the fix must prevent these from becoming global rules in the first place.

## Key mechanism: container hiding cascades

Hiding a *container* hides everything inside it, regardless of the children's own rules. The published list already hides the page containers that wrap home and subscriptions:

- Desktop home: `ytd-browse[page-subtype="home"] #primary`
- Desktop browse/subscriptions: `ytd-two-column-browse-results-renderer`
- Mobile home: `ytm-feed`

Search results live under a **different** container (`ytd-two-column-search-results-renderer` / `ytm-search`) that the list does **not** hide.

Therefore: if we stop emitting the *bare* result-card rules, those cards remain hidden on home/subscriptions (their ancestor container is hidden) but become visible on search (its container is not). No per-page logic is needed.

## The fix (Option 1: protect content renderers)

### 1. `extract.py` — new exact-match guard `CONTENT_RENDERERS`

A curated frozenset of the result cards / containers YouTube reuses on the search page:

```
ytd-video-renderer
ytd-item-section-renderer
ytd-grid-video-renderer
ytd-channel-renderer
ytd-playlist-renderer
ytd-playlist-video-renderer
yt-lockup-view-model
ytd-continuation-item-renderer
ytm-item-section-renderer
ytm-video-with-context-renderer
ytm-grid-video-renderer
```

`normalize_selector` returns `None` when the cleaned selector's **exact** value is in `CONTENT_RENDERERS` (same mechanism as the existing `OVER_BROAD` and `SEARCH_SURFACES` exact-match guards). Because the match is exact, **scoped** uses still pass — e.g. `ytd-search ytd-video-renderer:has([href^="/shorts/"])` and `[page-subtype="search"] ytd-video-renderer:has([href^="/shorts/"])` continue to strip Shorts inside search.

### 2. `lint.py` — publish-gate backstop

Mirror `CONTENT_RENDERERS` into `lint.py` and flag any rule whose exact selector is in the set: `"targets shared content renderer (would hide search results): <line>"`. This makes the gate catch a regression (from a future sync or a hand-edited supplement) that would re-blank search, consistent with the existing `OVER_BROAD_SHELLS` / `SEARCH_SURFACES` backstops.

### Deliberately NOT protected (stay hidden — distractions, not search results)

- `ytd-compact-video-renderer`, `ytm-compact-video-renderer` — watch-page recommendations.
- `ytd-rich-item-renderer`, `ytm-rich-item-renderer` — home/subscriptions grid items.
- `*-horizontal-card-list-renderer`, `*-shelf-renderer`, `grid-shelf-view-model`, reel/Shorts lockups — "people also watched"/Shorts shelves, which the curated rules already hide inside search on purpose.

These remain hidden globally; none of them carries the core search **result list**, so search stays usable.

## Components & boundaries

- `extract.py`: owns *what selectors are eligible*. Adds one guard set + one check line in `normalize_selector`. No change to the two harvesters or the orchestration.
- `lint.py`: owns *the publish gate*. Adds one guard set + one check line in `lint_text`. No change to other checks.
- `data/supplement.txt`: unchanged (the curated floor already scopes its search rules correctly).
- `dist/lockedin-youtube.txt`, `data/upstream-selectors.snapshot.json`: regenerated artifacts.

## Testing

TDD, stdlib `pytest` via `uv`:

- `tests/test_extract.py`:
  - bare content renderers (`ytd-video-renderer`, `ytd-item-section-renderer`, `ytm-video-with-context-renderer`, `ytm-item-section-renderer`, `ytd-continuation-item-renderer`) → `normalize_selector` returns `None`.
  - a scoped use survives: `normalize_selector('ytd-search ytd-video-renderer:has([href^="/shorts/"])')` is unchanged (returns the same selector).
- `tests/test_lint.py`:
  - bare `youtube.com##ytd-video-renderer` → flagged with `"shared content renderer"`.
  - scoped `youtube.com##ytd-search ytd-video-renderer:has([href^="/shorts/"])` → not flagged.

## Verification (acceptance criteria)

After regenerating with `BUILD_DATE` pinned and `--upstream upstream`:

1. `uv run pytest -q` all pass; `uv run ruff check .` clean.
2. `uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt --supplement data/supplement.txt` → `Lint passed.`, exit 0.
3. No **bare** content-renderer rule remains in `dist`: grep for `^youtube\.com##(ytd-video-renderer|ytd-item-section-renderer|ytd-grid-video-renderer|ytd-channel-renderer|ytd-playlist-renderer|ytd-playlist-video-renderer|yt-lockup-view-model|ytd-continuation-item-renderer|ytm-item-section-renderer|ytm-video-with-context-renderer|ytm-grid-video-renderer)$` → no matches.
4. Scoped search-cleanup rules still present (e.g. `ytd-search ytd-video-renderer:has([href^="/shorts/"])`).
5. Supplement floor intact: all 46 curated selectors present in `dist`.
6. Nav/feed hides the user wants still present (e.g. `ytm-pivot-bar-item-renderer`, `ytd-guide-renderer`, `ytm-feed`, `ytd-two-column-browse-results-renderer`).
7. Protected elements / player / search-surfaces / Ask button still clean (unchanged from current).
8. **Manual, by the user (cannot be automated here):** after publishing, confirm on-device that the search results page shows video/channel/playlist results on both desktop (uBO) and m.youtube.com (AdGuard iOS), while home/subscriptions/Shorts/recs remain hidden.

## Out of scope / follow-ups

- The systematic "trust CSS, scope strings" rework (brainstorm Option 2) is intentionally deferred. Residual risk of Option 1: if YouTube introduces a brand-new result-card element name, a future sync could re-hide search until that name is added to `CONTENT_RENDERERS`; the lint backstop only catches names already in the set. Acceptable given the daily-sync + rollback tolerance.
- Confirming the exact "Ask" button selector on-device and tightening `references_ask` remains a separate pre-existing follow-up.
