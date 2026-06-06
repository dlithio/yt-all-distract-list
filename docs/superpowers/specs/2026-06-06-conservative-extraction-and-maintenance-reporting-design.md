# Design: Conservative Extraction + Maintenance Reporting

**Date:** 2026-06-06
**Status:** Approved design, pending written-spec review.
**Builds on:** the LockedIn YouTube filter list on `main` (`lockedin_filters/`, `data/supplement.txt`, `dist/lockedin-youtube.txt`, `.github/workflows/`).

## Problem

The published list still over-blocks. The extractor harvests selectors from two places in the upstream LockedIn-YT extension:

1. **Real hide-CSS** — selectors inside injected `display:none {…}` blocks. Genuine, well-scoped hide intent.
2. **`querySelector`/`closest` string literals** — selectors the extension uses as *anchors* for JavaScript page-context logic, NOT as global hide intents.

`harvest_string_selectors` promotes string anchors into global hide rules, producing bare container nukes (`ytd-two-column-browse-results-renderer`, `ytd-rich-grid-renderer`, `ytm-feed`, `ytd-shelf-renderer`, `ytd-playlist-panel-renderer`, the guide/sidebar, …). Because container hiding cascades, these blank entire pages. Observed breakage (pre-existing, not introduced by the earlier targeted fix):

- Search: never-ending refresh loop, no results.
- Playlist pages: play button shows, video list blank.
- Channel pages: every tab blank (Live/Videos/Playlists).

**Empirical finding that drives this design:** every well-scoped good rule (the `[page-subtype="search"] …:has([href^="/shorts/"])` Shorts-in-search cleanup, scoped home rules, safe-bare distractions like end screens/thumbnails/Shorts shelves) comes from the **hide-CSS** path. The page-blanking nukes come **only** from the string-anchor path. The 27 bare selectors derived from hide-CSS are all safe (player end-screen/autoplay controls, thumbnails, Shorts) — none blank search/channels/playlists.

## Goals

- **Stop publishing the string-anchor harvest.** Publish only hide-CSS-derived selectors plus the curated `supplement.txt`. This un-blanks search, channels, and playlists by construction.
- **Migrate the genuinely-wanted hides** (that previously came only from the string harvest) into `supplement.txt`, scoped so they never blank visible pages.
- **Add daily maintenance observability** so the user can easily keep `supplement.txt` current: a committed catalog of every selector the extension exposes that the list does NOT block ("candidates"), plus a day-over-day change summary of what the extension added/removed.

## Non-goals

- No change to the dual-emit, version-stamping, `finalize` churn-avoidance, or the lint floor/explosion/protected checks (beyond reuse).
- Not trying to perfectly classify every candidate; the report surfaces them with best-effort risk hints for human decision.

## Visibility contract (the bar)

**Visible / usable:** search (no refresh loop; video/channel/playlist results show), channel pages (all tabs incl. Live), playlist pages, the watch video + transcript, the protected "Ask" button.

**Hidden:** home feed, subscriptions feed, Shorts everywhere (shelves/reels/nav entry/in-search), comments, watch-page recommendations + up-next + autoplay + in-player end screens, ads/promos, the desktop left sidebar + mobile bottom nav bar, thumbnails (blanked site-wide; titles/links remain).

---

## Component A — Conservative extraction + supplement curation

### A1. `extract.py` refactor: separate cleaning from policy

Split `normalize_selector` into two reusable pieces so both the publish path and the report can use them:

- `clean_selector(raw: str) -> str | None` — the cleaning currently inside `normalize_selector`: strip CSS comments, the `html[data-lockedin-*]` ancestor, `:not([data-lockedin-*])`/`[data-lockedin-*]` guards, collapse whitespace; return `None` if the result is empty, a bare/truncated token (`ytd-`, trailing `-`, a lone `YT_TOKENS` member), a non-YouTube selector (no `YT_TOKENS`), or a known non-selector JS identifier (the event-name strings `yt-navigate-finish`, `yt-page-data-updated`, `yt-page-type-changed`). Returns a usable normalized YouTube selector otherwise.
- `guard_reason(sel: str) -> str | None` — policy: returns `"over_broad"` if `sel in OVER_BROAD_SHELLS`, `"search_surface"` if `sel in SEARCH_SURFACES`, `"content_renderer"` if `sel in CONTENT_RENDERERS`, `"protected"` if any `PROTECTED_SUBSTRINGS` member is a substring of `sel`, else `None`.
- `normalize_selector(raw)` becomes: `s = clean_selector(raw); return None if (s is None or guard_reason(s)) else s` — identical external behavior to today (all existing `normalize_selector` tests still pass).

Move the event-name strings out of the `OVER_BROAD` frozenset into `clean_selector`'s junk rejection, and rename the remaining shell set to `OVER_BROAD_SHELLS` (matching lint) so `OVER_BROAD_SHELLS` holds only real-but-over-broad page shells. `CONTENT_RENDERERS`, `SEARCH_SURFACES`, `PROTECTED_SUBSTRINGS` are unchanged in membership.

### A2. `extract.py`: publish hide-CSS only

`extract_selectors(upstream_dir)` changes to harvest **only** CSS hide-blocks:

```
for path in iter_js_files(upstream_dir):
    text = read(path)
    for sel_part, decl in harvest_css_blocks(text):
        if is_hide_block(decl):
            for piece in sel_part.split(","):
                norm = normalize_selector(piece)
                if norm: selectors.add(norm)
return selectors
```

i.e. the `harvest_string_selectors` loop is removed from `extract_selectors`. The string harvester remains in the module (used by the report). Net effect on the current upstream: published extracted set drops from 278 → ~156, all safe; no page-blanking renderers remain.

### A3. `supplement.txt` migration

Add the genuinely-wanted hides that were previously only string-derived, scoped to protect visible pages. Keep all existing supplement rules. New additions (uBO style; `build.py` auto-emits the AdGuard twins):

**Feeds (home already present; add subscriptions + mobile home):**
```
youtube.com##ytd-browse[page-subtype="subscriptions"] #primary
youtube.com##ytm-browse[page-subtype="home"] ytm-feed
youtube.com##ytm-browse[page-subtype="subscriptions"] ytm-feed
```

**Navigation chrome (whole desktop sidebar + mobile bottom bar):**
```
youtube.com##ytd-guide-renderer
youtube.com##ytd-mini-guide-renderer
youtube.com##ytm-pivot-bar-renderer
```

**Watch recommendations / up-next (desktop `#related` already present; add mobile):**
```
youtube.com##ytm-watch-next-secondary-results-renderer
```

**Comments (desktop `ytd-comments` already present; add mobile):**
```
youtube.com##ytm-comments-section-renderer
```

**Ads / promos:**
```
youtube.com##ytd-display-ad-renderer
youtube.com##ytd-ad-slot-renderer
youtube.com##ytd-in-feed-ad-layout-renderer
youtube.com##ytd-promoted-sparkles-web-renderer
youtube.com##ytd-primetime-promo-renderer
youtube.com##ytd-statement-banner-renderer
```

These are grouped under clearly-labelled `! ---` sections. None are members of `CONTENT_RENDERERS`/`SEARCH_SURFACES`/`OVER_BROAD_SHELLS`/`PROTECTED`, so they pass the lint gate; the nav/ad/recs additions are safe-bare (they are chrome/ads, never search/channel/playlist content); the feed additions are page-scoped.

**Best-effort / verify on-device:** the mobile feed selectors (`ytm-browse[page-subtype=…] ytm-feed`) and the exact ad renderer names are best-effort. If any are wrong on-device, the Component-B report (below) will surface the real selectors as candidates for a quick supplement edit. This is called out, not hidden.

### A4. Guards / lint

`lint.py` keeps its `OVER_BROAD_SHELLS`, `SEARCH_SURFACES`, `CONTENT_RENDERERS`, `references_ask`, floor, and explosion checks unchanged. The `extract`↔`lint` drift-guard test (`test_lint_guard_sets_mirror_extract`) is updated to compare `lint.OVER_BROAD_SHELLS == extract.OVER_BROAD_SHELLS` (post-rename) alongside the existing `CONTENT_RENDERERS`/`SEARCH_SURFACES` parity.

---

## Component B — Daily maintenance report

### B1. `lockedin_filters/report.py`

A new stdlib-only module. Public entry `main(argv)` and a pure core:

- `harvest_candidates(upstream_dir) -> list[Candidate]` where a `Candidate` is a plain dict: `{"selector": str, "sources": ["css"|"string", …], "scoped": bool, "guard": str|None}`. It harvests BOTH paths (CSS hide-blocks and string literals), runs each through `clean_selector` (so junk is excluded but over-broad/guarded selectors are KEPT and annotated), records which source(s) produced it, whether it is scoped (contains a combinator/attribute/pseudo), and its `guard_reason` (the risk hint).
- `annotate(candidates, published: set[str], supplement: set[str]) -> list[Candidate]` — adds `"published": bool` and `"in_supplement": bool` to each candidate (compared on canonical selector), and derives the `unblocked` view (candidates where not `published` — the user's "could-be-blocked" list). `published` is the set of canonical selectors actually in the built `dist` (which already includes the supplement floor); `supplement` drives the `in_supplement` flag.
- `diff_candidates(current: set[str], previous: set[str]) -> {added, removed}` — day-over-day change.
- `render_markdown(...) -> str` and `render_json(...) -> str` — the two artifacts.

### B2. Artifacts (committed daily → git history is the change log)

- `data/candidates.json` — the full catalog: a sorted JSON array of candidate objects (selector + sources + scoped + guard + published/in_supplement flags). Machine-readable; its git diff is the precise change record.
- `data/MAINTENANCE.md` — human-readable, regenerated each run:
  - Header: generation date (from `BUILD_DATE`/passed in — never `Date.now()`), upstream commit SHA (`git -C upstream rev-parse HEAD`, passed in as an arg), and counts (total harvested, published, in-supplement, unblocked).
  - **Changes since last run:** NEW selectors and REMOVED selectors (diff of current candidate selectors vs the previously-committed `data/candidates.json`, read before overwrite). This is the "summary of what the extension changed."
  - **Unblocked candidates, grouped:** by `guard` risk then by source, each line showing the selector and, for guarded ones, a `⚠ over-broad — scope before adding` style hint so the user never pastes a page-blanker into the supplement.

### B3. CLI + wiring

`python -m lockedin_filters.report --upstream upstream --supplement data/supplement.txt --dist dist/lockedin-youtube.txt --candidates data/candidates.json --out data/MAINTENANCE.md --build-date <YYYY.MM.DD> --upstream-sha <sha>` reads the previous `data/candidates.json` (if present) for the diff, then writes both artifacts.

`.github/workflows/sync.yml` gains a step after the lint gate and before commit:
```
- name: Maintenance report
  run: |
    uv run python -m lockedin_filters.report \
      --upstream upstream --supplement data/supplement.txt \
      --dist dist/lockedin-youtube.txt \
      --candidates data/candidates.json --out data/MAINTENANCE.md \
      --build-date "$(date -u +%Y.%m.%d)" --upstream-sha "$(git -C upstream rev-parse HEAD)"
```
and the commit step adds `data/candidates.json data/MAINTENANCE.md` to the `git add`. The report runs **after** the lint gate so a failed gate still publishes nothing (report generation never gates publishing; it is observability only).

`validate.yml` is unchanged (report is not a CI gate).

---

## Data flow

```
upstream/ (cloned) ─┬─ harvest_css_blocks ─ is_hide_block ─ normalize_selector ─┐
                    │                                                            ├─ extract_selectors (PUBLISHED) ─┐
                    │                                                            │                                  ├─ build.py ─ dist/lockedin-youtube.txt
data/supplement.txt ───────────────────────────────────────────────────────────┘ (curated floor) ────────────────┘        │
                    │                                                                                                         └─ lint.py (gate)
                    └─ harvest_css_blocks + harvest_string_selectors ─ clean_selector + guard_reason ─ report.py ─ data/candidates.json + data/MAINTENANCE.md
```

## Testing (TDD, stdlib pytest via uv)

- `extract.py`: `clean_selector` cleans + rejects junk but does NOT drop over-broad/guarded selectors; `guard_reason` returns the right label per set; `normalize_selector` behavior unchanged (existing tests green). `extract_selectors` on a fixture/upstream returns CSS-derived selectors and EXCLUDES string-only renderers (`ytd-video-renderer`, `ytd-two-column-browse-results-renderer`, `ytm-feed`, etc.) while INCLUDING a CSS-derived scoped rule and a safe-bare distraction.
- `report.py`: `harvest_candidates` tags source/scoped/guard correctly on small JS fixtures (one CSS hide-block, one querySelector string with an over-broad renderer); `annotate` sets published/in_supplement and the unblocked view; `diff_candidates` reports added/removed; `render_markdown` includes the changes section and a ⚠ hint for a guarded candidate.
- `lint.py`: drift-guard updated and green; all existing checks pass.
- Supplement parse test still passes for the migrated `supplement.txt`.

## Verification / acceptance

After regenerating with `BUILD_DATE` pinned and `--upstream upstream`:

1. `uv run pytest -q` all pass; `uv run ruff check .` clean.
2. Lint gate passes on the new `dist`.
3. NO page-blanking bare renderers in `dist`: grep finds none of `ytd-two-column-browse-results-renderer`, `ytd-rich-grid-renderer`/`row`/`item-renderer`, `ytd-section-list-renderer`, `ytd-shelf-renderer`, `ytd-video-renderer`, `ytd-item-section-renderer`, `ytd-channel-renderer`, `ytd-playlist-renderer`, `ytd-playlist-panel-renderer`, `yt-lockup-view-model`, `ytm-feed`, `ytm-rich-*`, `ytm-item-section-renderer`, `ytm-video-with-context-renderer` as bare `youtube.com##<name>` rules.
4. Scoped Shorts-in-search rules still present (from the CSS set).
5. Supplement floor intact: every supplement selector present in `dist`.
6. The hidden set is represented: home (`ytd-browse[page-subtype="home"] #primary`), subscriptions (`ytd-browse[page-subtype="subscriptions"] #primary`), sidebar (`ytd-guide-renderer`), mobile bottom bar (`ytm-pivot-bar-renderer`), comments (`ytd-comments`), recs (`#related`), ads present.
7. `data/candidates.json` is valid JSON (sorted) and `data/MAINTENANCE.md` is generated with the counts + changes + grouped-candidates sections; over-broad candidates carry the ⚠ hint.
8. **Manual, by the user (on-device, not automatable here):** after publishing, confirm search/channels (all tabs)/playlists render; home/subs/Shorts/comments/recs/nav are hidden; verify the best-effort mobile feed + ad selectors actually hit (use `data/MAINTENANCE.md` to correct any that don't).

## Out of scope / risks / follow-ups

- Mobile feed scoping and ad renderer names are best-effort; the report exists precisely to make correcting them a one-line supplement edit.
- The report is observability only and never gates publishing.
- The "Ask" button on-device confirmation remains a pre-existing follow-up.
