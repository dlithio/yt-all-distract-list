# LockedIn YouTube — Self-Updating Maximalist Distraction Filter List

**Date:** 2026-06-06
**Status:** Approved design (pre-implementation)
**Repo:** `dlithio/yt-all-distract-list` (this repo)

---

## 1. Goal (north star)

Produce a **maximal YouTube-distraction cosmetic filter list**, published as a single `.txt`
file at a stable raw URL, that **uBlock Origin** (Firefox/Chromium desktop) and **AdGuard for
iOS** subscribe to. The list **auto-updates daily** with effectively zero manual intervention,
staying in sync with YouTube's changing DOM by tracking the **LockedIn-YT** browser extension as
its upstream selector source.

**Subscribe URL (source of truth):**
`https://raw.githubusercontent.com/dlithio/yt-all-distract-list/main/dist/lockedin-youtube.txt`

Clients auto-refresh because the list header declares `! Expires: 1 day`.

---

## 2. Locked-in decisions

These were settled during brainstorming and are not open for re-litigation during implementation:

| # | Decision | Value |
|---|----------|-------|
| 1 | **Blocking lean** | **Aggressive / over-block.** Hide everything even mildly distracting; accept occasional over-hiding and roll back when noticed. |
| 2 | **Rule source** | **LockedIn-YT extension only** (`KartikHalkunde/LockedIn-YT`, MIT, default branch `main`). No external community lists. |
| 3 | **Publish flow** | **Direct commit to `main`** after a passing lint/sanity gate. Zero manual clicks. Gate failure → skip publishing, fail loudly. |
| 4 | **Generation strategy** | **Extraction + curated supplement.** Auto-extracted upstream rules ∪ a hand-maintained supplement; deduped and merged into the published list. |
| 5 | **Seed of the supplement** | The user's existing hand-crafted list (Section 11 below) is the authoritative base. Extraction is **strictly additive** on top of it. |
| 6 | **Repo / owner** | This repo, owner `dlithio`. |
| 7 | **Desktop extension** | User is **switching away** from the desktop extension; the list is the primary tool. Non-reproducible behaviors documented as "not available." |
| 8 | **List count** | **Single combined list** for both engines (pending a quick syntax re-verification as the first implementation step). |
| 9 | **Security** | Trust upstream content, but **never execute upstream code** — pure text parsing only; least-privilege CI; no third-party runtime deps. |

---

## 3. Core invariant (the heart of the project)

> **The published list always blocks at least everything the curated supplement blocks.**
> Extraction can only ever *add* rules on top of the supplement — never remove or weaken them.

The user's hand-crafted list is the floor. The LockedIn-YT extraction exists to **keep that floor
updated and to add the things the user missed** (and to track YouTube DOM changes over time). The
lint gate enforces `published ⊇ supplement`, so a broken upstream parse can never drop the user's
rules — at worst it adds nothing.

---

## 4. Architecture & components

A small uv-managed Python package (`src/lockedin_filters/`), **stdlib-only at runtime**, plus two
GitHub Actions workflows.

### 4.1 `extract.py` — the extractor

Harvests hide-selectors from the upstream extension source and converts them to filter rules.

**Generic about upstream layout** (per the requirement "filenames could change or be added to"):

1. Read the upstream `manifest.json` and resolve `content_scripts[].js` to discover which files
   carry blocking logic.
2. **Fallback:** if the manifest can't be found/parsed, glob **all** `**/*.js` under the clone.
3. The over-broad guard (below) is the backstop that keeps non-content files (e.g. the extension's
   own settings-popup UI) from polluting the YouTube ruleset.

**Harvest** the three forms of blocking logic found in the upstream source:
- (a) **CSS inside JS template literals** assigned to `style.textContent` — split on `}`, take the
  selector list before each `{`, and **classify the declaration**: *hide*
  (`display:none`, `visibility:hidden`, `opacity:0`, `max-height:0`) vs. *restore/other* — **skip
  restore blocks** (`visibility:visible`, `display:block/flex`, `opacity:1`, `pointer-events:auto`,
  `max-height:none`, `filter:none`).
- (b) **Selector-ish string literals** passed to `querySelectorAll` / toggle helpers, matched by a
  YouTube heuristic (contains `ytd-`, `ytm-`, `tp-yt-`, `yt-`, leading `.ytp-`, a known id like
  `#secondary #related #comments #chat #movie_player`, `[overlay-style`, or `:has(`).
- (c) The central **`SELECTORS` dict** (desktop + mobile) — regex the string values.

**Normalize** each harvested selector:
- trim; collapse internal whitespace/newlines.
- strip `html[data-lockedin-...]` ancestor prefixes.
- remove `:not([data-lockedin-...])` and bare `[data-lockedin-*]` guards.
- **protected-selectors skip** (see 4.5) — never emit a rule for the player, transcript panel,
  extension scaffolding, or the **"Ask" button** (the AI button near like/dislike).
- **over-broad guard:** the normalized selector must contain ≥1 real YouTube token
  (`ytd-`, `ytm-`, `tp-yt-`, `yt-`, `.ytp-`, a `*-view-model` web-component name, or a known YT id);
  otherwise skip + log. Prevents `img`, `span`, `#primary`, `#contents`, bare `video`, and the
  extension's own UI selectors from becoming global hide rules.

**Output:** a normalized set of selectors (the build step prefixes/compiles them).

### 4.2 `data/supplement.txt` — the curated base (authoritative)

Hand-maintained filter rules in standard uBO desktop syntax. Seeded with the user's existing list
(Section 11). This file is:
- the **floor** the published list must always meet (invariant in Section 3),
- the **instant manual lever** when YouTube breaks something (edit it, push, CI republishes),
- the home for rules extraction can't see (player-API-driven behavior, text-match upsell rules,
  best-effort mobile `ytm-*`, belt-and-suspenders end-screens).

It is written in clean, human-readable **desktop style** (single `:has-text(...)` form, no need to
hand-write AdGuard twins — `build.py` generates those).

### 4.3 `build.py` — compose the published file

1. Run extraction over the upstream clone.
2. Parse `supplement.txt` into individual rules.
3. **Union** extracted ∪ supplement; **dedupe** (by normalized selector + marker).
4. **Cross-engine text-rule compilation** (Section 4.4).
5. Deterministic sort (stable grouping/ordering so diffs are meaningful).
6. Prepend the metadata header, stamping `! Version:` with the build date (env-provided for
   determinism).
7. Write `dist/lockedin-youtube.txt`.

**Quiet days don't commit:** before writing, compare the new rule body (ignoring the `! Version:`
line) to the currently-published file. If identical, change nothing — so git history is one commit
per *real* change, not one per day.

### 4.4 Cross-engine text-rule compilation (the dual-emit + quote-strip rule)

Text-matching rules need engine-specific syntax. For **every** text rule in the merged set,
`build.py` emits **both** forms:
- uBlock Origin: `youtube.com##<selector>:has-text(<text>)`
- AdGuard:       `youtube.com#?#<selector>:contains(<text>)`

When emitting the AdGuard twin, **strip surrounding quotation marks** from the text argument
(`:has-text("Shorts")` → `:contains(Shorts)`).

**Why (corrected rationale — see also DEVELOPMENT.md):** the issue is *not* that `:has-text()` is
uBO-only — AdGuard's desktop engine accepts it as an alias. The real problem is **AdGuard for iOS's
`SafariConverterLib`** compiler: when it sees the element-hide prefix `##` combined with
`:has-text()`, it cannot map the rule to a native Safari content-blocking entry, misclassifies it,
and **silently drops it** rather than routing it to the Advanced Protection JS engine. Emitting an
explicit `#?#…:contains(…)` procedural rule forces iOS to use its JS engine. Separately, AdGuard's
parser **chokes on quotation marks inside text args**, so the twin must be quote-free.

Each engine keeps the line it understands and silently discards the other, so both forms can live
in one list. (On AdGuard iOS the `#?#` text rules require the **Advanced Protection** module
enabled — documented for the end user.)

### 4.5 `lint.py` — the safety gate

Exit nonzero (→ CI does **not** publish) on any of:
- a non-comment line that is not a valid `youtube.com##` / `youtube.com#?#` rule;
- unbalanced brackets/parens;
- `:contains(` appearing in a `##` line, or `:has-text(` in a `#?#` line;
- **quotation marks inside any `#?#…:contains(…)` line** (the AdGuard trap);
- duplicate rules;
- missing/malformed metadata header;
- **playback protection** — any rule targeting the video player (`#movie_player`,
  `.html5-video-player`, `.html5-main-video`, `video.video-stream`);
- **protected-element violation** — any rule targeting the transcript/description side panel or the
  **"Ask" button** near like/dislike (exact selector to be confirmed on-device — see Section 14);
- **supplement-floor violation** — the published list does not contain every supplement rule
  (enforces the Section 3 invariant);
- **explosion check** — rule count cratered toward zero or ballooned far beyond the currently
  published list (catches a broken upstream parse).

> **Terminology note:** the "protected selectors" (player, transcript/description side panel,
> extension scaffolding, and the **"Ask" button** near like/dislike) are the *only* things shielded
> from hiding. **Engagement metrics — likes, dislikes, view count, subscriber count — ARE
> blocked.** They are never protected.

---

## 5. Repository layout

```
yt-all-distract-list/
├── .github/workflows/
│   ├── sync.yml              # daily: clone upstream → build → lint gate → commit to main
│   └── validate.yml          # PR/push: lint + pytest
├── dist/
│   └── lockedin-youtube.txt  # THE published list (generated; subscribe URL points here)
├── data/
│   ├── supplement.txt        # curated authoritative base (seeded from the user's list)
│   └── upstream-selectors.snapshot.json   # last-seen upstream set (for "new since last run" logs)
├── src/lockedin_filters/
│   ├── __init__.py
│   ├── extract.py            # harvest + normalize upstream selectors
│   ├── build.py              # compose dist file (union, dual-emit, sort, stamp)
│   └── lint.py               # the safety gate
├── tests/
│   ├── test_extract.py
│   └── test_lint.py
├── docs/
│   ├── DEVELOPMENT.md        # dev README (env, how extraction works, the text-rule rationale, CI)
│   └── superpowers/specs/    # this spec
├── README.md                 # end-user README (subscribe instructions + limitations)
├── pyproject.toml            # uv-managed; stdlib runtime; dev deps: ruff, pytest
├── uv.lock
├── .gitignore
└── LICENSE                   # MIT, attributing the user + upstream Kartik Halkunde
```

CLIs run via uv, e.g. `uv run python -m lockedin_filters.build` / `... .lint` / `... .extract`.

---

## 6. Data flow

```
upstream JS ──extract──▶ selectors ──∪ supplement──▶ dedupe ──▶ dual-emit text rules
                                                                       │
                                                          sort + metadata header
                                                                       │
                                                          dist/lockedin-youtube.txt
                                                                       │
                                                                 lint gate (pass?)
                                                                       │ yes & changed
                                                            commit to main ──▶ raw URL
                                                                       │
                                                          uBO / AdGuard (refresh: Expires 1 day)
```

---

## 7. CI/CD (GitHub Actions)

### `sync.yml` — daily sync + publish
- **Triggers:** `schedule` (daily cron) + `workflow_dispatch`.
- **Permissions:** `contents: write` only. Actions pinned to versions/SHAs.
- **Steps:**
  1. `actions/checkout`.
  2. `astral-sh/setup-uv`; `uv sync --frozen`.
  3. Shallow-clone upstream: `git clone --depth 1 https://github.com/KartikHalkunde/LockedIn-YT.git upstream` (read-only; **no upstream code is executed**).
  4. `BUILD_DATE=$(date -u +%Y.%m.%d) uv run python -m lockedin_filters.build --upstream upstream`.
  5. `uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt` (the gate).
  6. If the file changed **and** the gate passed → commit `dist/lockedin-youtube.txt` (and the
     snapshot) directly to `main`. If the gate failed → **do not commit**; fail the run so it's
     visible in Actions. The previously-published list keeps serving until the user fixes/rolls back.

### `validate.yml` — quality gate for manual edits
- **Triggers:** `pull_request` + `push`.
- **Steps:** checkout → setup-uv → `uv sync` → `uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt` → `uv run pytest -q`. Protects hand edits to `supplement.txt`.

---

## 8. Error handling & resilience

| Failure | Behavior |
|---------|----------|
| Upstream clone fails | CI fails loudly; nothing published; old list keeps serving. |
| Upstream parse looks wrong (explosion check) | Gate fails; nothing published. |
| A rule would hide the player | Gate fails; nothing published. |
| Malformed line / quotes-in-`:contains` | Gate fails; nothing published. |
| Supplement rule missing from output | Gate fails (floor invariant); nothing published. |
| No real change since last run | No commit (clean history). |

All failures surface in the GitHub Actions tab; the user fixes/rolls back when noticed (matches the
stated "I can always roll back" tolerance).

---

## 9. Security posture

- **No execution of upstream code.** The extractor only reads and text-parses upstream files; it
  never imports, evals, or runs them.
- **Zero third-party runtime dependencies** (stdlib only) → minimal supply-chain surface. Dev-only
  deps (`ruff`, `pytest`) pinned via `uv.lock`.
- **Least-privilege CI:** `contents: write` token, pinned actions, shallow read-only upstream clone.

---

## 10. Testing

- `tests/test_extract.py` — normalization on small fixture strings: guard-stripping, restore-block
  skipping, protected-selector skip, over-broad guard rejection, the three harvest forms.
- `tests/test_lint.py` — gate catches: invalid line, wrong text operator per marker, quotes inside
  `:contains`, duplicate, player-protection violation, supplement-floor violation, explosion.
- `tests/` may include a small dual-emit test for `build.py`'s text-rule compilation (incl. quote
  stripping).
- CI runs `pytest` on every push/PR via `validate.yml`.

---

## 11. Seed supplement (`data/supplement.txt`, v1)

The user's existing hand-crafted list, restored to proper line breaks. This is the authoritative
floor; extraction adds on top. `build.py` will auto-generate AdGuard twins for the `:has-text(...)`
rules — do **not** hand-write `#?#` lines here.

```
! ==============================================================================
! YOUTUBE DE-ADDICTION FILTER LIST (Optimized for Desktop & Mobile)
! ==============================================================================

! --- 1. CORE FEED & SIDEBAR OVERHAUL ---
! Hide YouTube Homepage Feed completely
youtube.com##ytd-browse[page-subtype="home"] #primary
! Hide YouTube Sidebar / Up Next Recommendations
youtube.com###related

! --- 2. THE "SHORTS" REMOVAL ---
! Hide Shorts in Mini Guide (collapsed left sidebar)
youtube.com##ytd-mini-guide-entry-renderer:has(a[title="Shorts"])
! Hide Shorts in Main Guide (expanded left sidebar)
youtube.com##ytd-guide-entry-renderer:has(a[title="Shorts"])
! Hide Shorts in Mobile Bottom Navigation Bar
youtube.com##ytm-pivot-bar-item-renderer:has-text(Shorts)
! Hide Shorts shelves/carousels in search results
youtube.com##ytd-rich-shelf-renderer:has([is-shorts])
youtube.com##ytm-reel-shelf-renderer

! --- 3. "YOU" & "EXPLORE" SECTIONS ---
! Hide Explore section (block containing 'Shopping', 'Music', etc.)
youtube.com##ytd-guide-section-renderer:has(a[title="Shopping"])
! Hide 'More from YouTube' section
youtube.com##ytd-guide-section-renderer:has(a[title="YouTube Premium"])
! Hide specific items under 'You' (leaves 'Your channel' untouched)
youtube.com##ytd-guide-entry-renderer:has(a[title="History"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Playlists"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Watch later"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Liked videos"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Your videos"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Downloads"])
! Hide the 'Show more' expander under 'You'
youtube.com##ytd-guide-collapsible-entry-renderer

! --- 4. THUMBNAIL ERADICATION ---
! Hide standard video thumbnails (desktop & mobile)
youtube.com##ytd-thumbnail img
youtube.com##ytd-playlist-thumbnail img
youtube.com##.media-item-thumbnail-container img
youtube.com##ytm-thumbnail-element img
! Hide the giant hero thumbnail on Watch Later / Playlist pages
youtube.com##ytd-playlist-header-renderer yt-image
youtube.com##ytd-playlist-header-renderer .hero-image-container

! --- 5. PLAYER DISTRACTIONS & END SCREENS ---
! Disable video hover/moving previews
youtube.com###mouseover-overlay
youtube.com##ytd-moving-thumbnail-renderer
! Hide splash thumbnail inside player before clicking play
youtube.com##.ytp-cued-thumbnail-overlay
youtube.com##.player-poster
! Hide floating End Cards (videos/channels overlapping the player)
youtube.com##.ytp-ce-element
! Hide full-screen/paused recommendation grids
youtube.com##.html5-endscreen
youtube.com##.ytp-videowall-still
youtube.com##.ytp-fullscreen-grid

! --- 6. COMMENTS ---
! Hide Comments Section
youtube.com##ytd-comments

! --- 7. METRICS & ENGAGEMENT ---
! Hide the Notification Bell
youtube.com##ytd-notification-topbar-button-renderer
! Hide Subscription Badges (red dots/numbers for new videos)
youtube.com##.badge-style-type-notification
youtube.com##ytd-guide-entry-renderer #newness-dot
! Hide View Counts (thumbnails and video player)
youtube.com##ytd-video-meta-block span.ytd-video-meta-block:first-of-type
youtube.com##ytd-watch-metadata #info-container span:has-text(views)
youtube.com##ytd-watch-metadata #info-container span:has-text(view)
! Hide Subscriber Count
youtube.com##yt-formatted-string#owner-sub-count
youtube.com##yt-formatted-string#subscriber-count
! Hide Subscribe and "Try it free" / Premium buttons
youtube.com##ytd-subscribe-button-renderer
youtube.com##ytd-button-renderer:has-text(Try it free)
youtube.com##ytd-button-renderer:has-text(Premium)
! Hide Like / Dislike Buttons
youtube.com##segmented-like-dislike-button-view-model
youtube.com##like-button-view-model
youtube.com##dislike-button-view-model

! --- 8. SEARCH AUTOCOMPLETE ---
! Hide modern web-component search autocomplete dropdown
youtube.com##.ytSearchboxComponentSuggestionsContainer
```

---

## 12. Published-list metadata header (`dist/lockedin-youtube.txt`)

```
! Title: LockedIn YouTube — Maximalist Distraction Filter
! Description: Strips YouTube to a focus-only surface: home feed, Shorts, watch-page recommendations, thumbnails, comments, player end screens, engagement metrics (likes, views, subscriber count), and guide/navigation clutter. Derived from the LockedIn-YT extension. Works in uBlock Origin (desktop) and AdGuard for iOS.
! Homepage: https://github.com/dlithio/yt-all-distract-list
! Source extension: https://github.com/KartikHalkunde/LockedIn-YT (MIT, © Kartik Halkunde)
! Expires: 1 day
! Version: <YYYY.MM.DD build date>
! License: MIT
```

---

## 13. Documentation deliverables

**`README.md` (end user):**
- One-paragraph what/why + the subscribe URL.
- **uBlock Origin:** Dashboard → *Filter lists* → *Import* → paste raw URL → *Apply changes*.
- **AdGuard for iOS:** *Filters* → *Custom* → *Add custom filter* → paste raw URL → add; then
  enable **Advanced Protection** (for the `#?#` text rules) and ensure AdGuard's Safari extensions
  are on (iOS *Settings → Safari → Extensions*). Requires ~iOS 16.4+ for `:has()`.
- **Limitations** (user is not running the desktop extension): a cosmetic list cannot redirect URLs
  (`/shorts`→`/watch`, Home→Subscriptions) or truly disable autoplay — the list hides all Shorts
  entry points (and any autoplay / next-up UI surfaced from upstream), but a queued next video can
  still roll. The redirect and true-autoplay-off behaviors are **not available** anywhere in this
  setup.
- Attribution: derived from `KartikHalkunde/LockedIn-YT` (MIT).

**`docs/DEVELOPMENT.md` (developer):**
- Dev env: install uv, `uv sync`; run build/lint/extract locally; `uv run pytest`, `uv run ruff check`.
- Mental model: `supplement.txt` is the authoritative floor; extraction adds on top; the core
  invariant; how to add a rule by hand.
- **"Why we compile text rules" section** — include the external engineering review verbatim
  (SafariConverterLib silent-drop behavior + the quotation-mark trap) so the rationale isn't lost.
- CI: what `sync.yml` / `validate.yml` do; the daily cadence; how to trigger a manual run.
- How to handle a "YouTube broke something" report: add to `supplement.txt` → lint → push.
- License/attribution.

---

## 14. Open items / first implementation steps

1. **Verify single-list cross-engine compatibility** (first task): quick web check that current
   uBO + AdGuard iOS still support `:has()`, the `#?#`/`:contains` procedural path, per-engine
   silent-drop of foreign lines, and the SafariConverterLib behavior described in 4.4. If anything
   has changed, revisit the single-list assumption before building.
2. Confirm the upstream repo (`KartikHalkunde/LockedIn-YT`) still matches the harvest assumptions
   in 4.1 (three blocking forms, `manifest.json` content scripts).
3. **Confirm the exact "Ask" button selector** on-device (the AI button near like/dislike) so the
   protected-element check guards the right element. Until confirmed, protect by best-effort match
   (e.g. an `[aria-label^="Ask" i]` button within the watch actions row).
4. Decide the exact daily cron time (cosmetic).

---

## 15. Out of scope

- URL redirects and true autoplay-off (not possible in a cosmetic filter list).
- External/community filter lists (decision #2 — LockedIn-YT only).
- Auto-merged-PR or Pages/Release publishing (decision #3 — direct commit to main).
- Hiding the video player, transcript panel, or the "Ask" button (protected selectors).
```