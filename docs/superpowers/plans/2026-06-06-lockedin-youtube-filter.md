# LockedIn YouTube Filter List — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-updating, maximalist YouTube-distraction cosmetic filter list that uBlock Origin (desktop) and AdGuard for iOS subscribe to, regenerated daily from the LockedIn-YT extension source.

**Architecture:** A small stdlib-only Python package (`lockedin_filters/`) with three responsibilities — `extract` (harvest hide-selectors from upstream JS), `build` (merge the curated `data/supplement.txt` with extracted rules, dual-emit text rules for both engines, write `dist/lockedin-youtube.txt`), and `lint` (the publish gate). A daily GitHub Action clones upstream, rebuilds, runs the lint gate, and commits straight to `main` only when both the gate passes and the rule set actually changed.

**Tech Stack:** Python 3.12+, `uv`, stdlib only at runtime (`re`, `json`, `pathlib`, `argparse`), `pytest` + `ruff` (dev), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-06-06-lockedin-youtube-filter-design.md`

**Layout note (refinement of spec §5):** the package lives at the repo root (`lockedin_filters/`, not `src/lockedin_filters/`) so `uv run python -m lockedin_filters.build` works with zero packaging/build-backend config (running `python -m` from the repo root puts the root on `sys.path`). `pytest` is pointed at the root via `pythonpath = ["."]`.

---

## File structure

| Path | Responsibility |
|------|----------------|
| `pyproject.toml` | uv project: dev deps (pytest, ruff), pytest pythonpath, ruff config |
| `.gitignore` | ignore venv, caches, the transient `upstream/` clone |
| `lockedin_filters/__init__.py` | package marker |
| `lockedin_filters/textrules.py` | uBO `:has-text` ⇄ AdGuard `:contains` conversion + quote stripping |
| `lockedin_filters/extract.py` | harvest + normalize hide-selectors from upstream JS |
| `lockedin_filters/build.py` | compose `dist/lockedin-youtube.txt`; supplement parsing; version stamping |
| `lockedin_filters/lint.py` | the publish gate (validity, protected elements, floor, explosion) |
| `data/supplement.txt` | curated authoritative rule floor (seeded from the user's list) |
| `dist/lockedin-youtube.txt` | THE published list (generated, committed) |
| `data/upstream-selectors.snapshot.json` | last-seen extracted selectors (for diff visibility) |
| `tests/test_textrules.py` | unit tests for text-rule conversion |
| `tests/test_extract.py` | unit tests for harvesting/normalization |
| `tests/test_supplement.py` | sanity test that every supplement line parses |
| `tests/test_build.py` | unit tests for compose/dual-emit/version stamping |
| `tests/test_lint.py` | unit tests for every gate check |
| `.github/workflows/validate.yml` | PR/push: lint + pytest |
| `.github/workflows/sync.yml` | daily: clone upstream → build → lint gate → commit |
| `README.md` | end-user subscribe instructions + limitations |
| `docs/DEVELOPMENT.md` | dev README incl. the verbatim text-rule engineering note |
| `LICENSE` | MIT |

---

## Task 1: Project scaffold & tooling

**Files:**
- Modify: `pyproject.toml`
- Create: `.gitignore`, `lockedin_filters/__init__.py`
- Delete: `main.py`

- [ ] **Step 1: Replace `pyproject.toml` with the project config**

```toml
[project]
name = "yt-all-distract-list"
version = "0.1.0"
description = "Self-updating maximalist YouTube distraction filter list for uBlock Origin and AdGuard"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
upstream/
```

- [ ] **Step 3: Create the package marker `lockedin_filters/__init__.py`**

```python
"""LockedIn YouTube filter-list generator."""
```

- [ ] **Step 4: Delete the scaffold `main.py`**

Run: `rm main.py`

- [ ] **Step 5: Sync the environment (creates `uv.lock`)**

Run: `uv sync`
Expected: creates `.venv` and `uv.lock`, installs pytest + ruff.

- [ ] **Step 6: Verify pytest runs (no tests yet)**

Run: `uv run pytest -q`
Expected: exits 0 with "no tests ran" (exit code may be 5 = "no tests collected"; that's fine at this stage).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore uv.lock lockedin_filters/__init__.py
git rm main.py
git commit -m "chore: scaffold uv project and package skeleton"
```

---

## Task 2: Verify single-list cross-engine compatibility (research gate)

This is the spec's first open item (§14.1). No code — confirm the assumptions before building on them. Record findings so they aren't lost.

**Files:**
- Create: `docs/compatibility-notes.md`

- [ ] **Step 1: Run web searches to confirm current behavior**

Use the WebSearch tool for each of:
- `AdGuard iOS :has() support Safari content blocker version`
- `AdGuard SafariConverterLib :has-text rule silently dropped iOS`
- `uBlock Origin :has-text procedural cosmetic filter syntax`
- `AdGuard #?# :contains extended css iOS Advanced Protection`
- `filter list invalid rule dropped per engine uBO AdGuard`

Confirm: (a) `:has()` works in both engines (AdGuard iOS ≈ v4.4.6+ / Safari 16.4+); (b) AdGuard iOS needs `#?#…:contains(…)` (not `##…:has-text`) and the "Advanced Protection" module; (c) each engine silently drops lines it can't parse, so one combined list is safe; (d) `youtube.com##` matches `www.` and `m.` subdomains in both engines.

- [ ] **Step 2: Write `docs/compatibility-notes.md` with the findings**

Record each claim above with a one-line verdict (confirmed / changed) and the source URL. If anything has materially changed (e.g. single list no longer viable), STOP and raise it with the user before continuing — do not proceed on a stale assumption.

- [ ] **Step 3: Commit**

```bash
git add docs/compatibility-notes.md
git commit -m "docs: record cross-engine filter compatibility verification"
```

---

## Task 3: `textrules.py` — cross-engine text-rule conversion

**Files:**
- Create: `lockedin_filters/textrules.py`
- Test: `tests/test_textrules.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_textrules.py
from lockedin_filters.textrules import (
    has_text, has_contains, to_contains, to_has_text,
)


def test_has_text_and_has_contains_detect_markers():
    assert has_text("ytd-x:has-text(Shorts)")
    assert not has_text("ytd-x")
    assert has_contains("ytd-x:contains(Shorts)")
    assert not has_contains("ytd-x:has-text(Shorts)")


def test_to_contains_converts_and_strips_quotes():
    assert to_contains("ytd-x:has-text(Shorts)") == "ytd-x:contains(Shorts)"
    assert to_contains('ytd-x:has-text("Shorts")') == "ytd-x:contains(Shorts)"
    assert to_contains("ytd-x:has-text('Shorts')") == "ytd-x:contains(Shorts)"


def test_to_has_text_converts_and_strips_quotes():
    assert to_has_text("ytd-x:contains(views)") == "ytd-x:has-text(views)"
    assert to_has_text('ytd-x:contains("views")') == "ytd-x:has-text(views)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_textrules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lockedin_filters.textrules'`

- [ ] **Step 3: Write the implementation**

```python
# lockedin_filters/textrules.py
"""Convert between uBlock Origin :has-text(...) and AdGuard :contains(...) text rules.

AdGuard for iOS compiles rules through SafariConverterLib; a `##` element-hide rule
that uses :has-text() is misclassified and silently dropped, so cross-engine lists
must emit an explicit `#?#...:contains(...)` procedural twin. AdGuard also chokes on
quotation marks inside the text argument, so the twin must be quote-free.
"""
from __future__ import annotations

import re

_HAS_TEXT = re.compile(r":has-text\((.*?)\)")
_CONTAINS = re.compile(r":contains\((.*?)\)")


def has_text(selector: str) -> bool:
    return ":has-text(" in selector


def has_contains(selector: str) -> bool:
    return ":contains(" in selector


def _strip_quotes(arg: str) -> str:
    arg = arg.strip()
    if len(arg) >= 2 and arg[0] == arg[-1] and arg[0] in "\"'":
        arg = arg[1:-1]
    return arg


def to_contains(selector: str) -> str:
    """uBO :has-text(X) -> AdGuard :contains(X), with surrounding quotes stripped."""
    return _HAS_TEXT.sub(lambda m: f":contains({_strip_quotes(m.group(1))})", selector)


def to_has_text(selector: str) -> str:
    """AdGuard :contains(X) -> uBO :has-text(X), with surrounding quotes stripped."""
    return _CONTAINS.sub(lambda m: f":has-text({_strip_quotes(m.group(1))})", selector)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_textrules.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add lockedin_filters/textrules.py tests/test_textrules.py
git commit -m "feat: add cross-engine text-rule conversion helpers"
```

---

## Task 4: `extract.py` — constants and `normalize_selector`

**Files:**
- Create: `lockedin_filters/extract.py`
- Test: `tests/test_extract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract.py
from lockedin_filters.extract import normalize_selector


def test_normalize_accepts_youtube_component():
    assert normalize_selector("ytd-reel-shelf-renderer") == "ytd-reel-shelf-renderer"


def test_normalize_strips_lockedin_guards():
    raw = 'html[data-lockedin-shorts="true"] ytd-reel-shelf-renderer:not([data-lockedin-hidden])'
    assert normalize_selector(raw) == "ytd-reel-shelf-renderer"


def test_normalize_collapses_whitespace():
    assert normalize_selector("ytd-browse   #primary") == "ytd-browse #primary"


def test_normalize_rejects_protected_player():
    assert normalize_selector("#movie_player") is None
    assert normalize_selector("video.video-stream") is None


def test_normalize_rejects_protected_transcript_panel():
    assert normalize_selector("ytd-transcript-segment-list-renderer") is None


def test_normalize_rejects_over_broad_generic():
    assert normalize_selector("img") is None
    assert normalize_selector("#primary") is None
    assert normalize_selector("span") is None


def test_normalize_keeps_view_model_components():
    assert normalize_selector("like-button-view-model") == "like-button-view-model"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extract.py -v`
Expected: FAIL with `ImportError`/`ModuleNotFoundError` for `lockedin_filters.extract`

- [ ] **Step 3: Write the implementation (constants + normalize)**

```python
# lockedin_filters/extract.py
"""Harvest hide-selectors from the LockedIn-YT extension source and normalize them
into youtube.com cosmetic-filter selectors.

Pure stdlib. NEVER imports, evals, or executes upstream code — it only reads and
text-parses the files.
"""
from __future__ import annotations

import re
from pathlib import Path

# A normalized selector must contain at least one of these real YouTube tokens,
# otherwise it is too broad (e.g. bare `img`, `span`, `#primary`) or belongs to the
# extension's own settings UI rather than the YouTube page.
YT_TOKENS = (
    "ytd-", "ytm-", "tp-yt-", "yt-", ".ytp-", "-view-model",
    "#movie_player", "#secondary", "#related", "#comments", "#chat",
)

# Declarations that mean "hide" (we want these blocks).
HIDE_DECLS = ("display:none", "visibility:hidden", "opacity:0", "max-height:0")

# Declarations that mean "restore / keep visible" — skip the whole block.
RESTORE_DECLS = (
    "visibility:visible", "display:block", "display:flex", "opacity:1",
    "pointer-events:auto", "max-height:none", "filter:none",
)

# Selectors we must NEVER turn into hide rules (protected elements). The "Ask"
# button is additionally protected via references_ask() in lint.py.
PROTECTED_SUBSTRINGS = (
    "#movie_player", ".html5-video-player", ".html5-main-video", "video.video-stream",
    "data-lockedin-center-watch", "lockedin-feed-placeholder",
    "ytd-engagement-panel-section-list-renderer", "ytd-transcript-segment-list-renderer",
)

_ANCESTOR = re.compile(r"html\[data-lockedin-[^\]]*\]\s*")
_NOT_GUARD = re.compile(r":not\(\[data-lockedin-[^\]]*\]\)")
_ATTR_GUARD = re.compile(r"\[data-lockedin-[^\]]*\]")
_WS = re.compile(r"\s+")


def normalize_selector(selector: str) -> str | None:
    """Clean one harvested selector. Return the normalized selector, or None if it
    should be skipped (protected, over-broad, or empty)."""
    sel = selector.strip()
    sel = _ANCESTOR.sub("", sel)
    sel = _NOT_GUARD.sub("", sel)
    sel = _ATTR_GUARD.sub("", sel)
    sel = _WS.sub(" ", sel).strip()
    if not sel:
        return None
    low = sel.lower()
    if any(p.lower() in low for p in PROTECTED_SUBSTRINGS):
        return None
    if not any(tok in sel for tok in YT_TOKENS):
        return None
    return sel
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extract.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add lockedin_filters/extract.py tests/test_extract.py
git commit -m "feat: add selector normalization with protected/over-broad guards"
```

---

## Task 5: `extract.py` — harvest functions

**Files:**
- Modify: `lockedin_filters/extract.py`
- Test: `tests/test_extract.py`

- [ ] **Step 1: Add failing tests**

```python
# append to tests/test_extract.py
from lockedin_filters.extract import (
    is_hide_block, harvest_css_blocks, harvest_string_selectors,
)


def test_is_hide_block_true_for_display_none():
    assert is_hide_block("display:none !important;") is True


def test_is_hide_block_false_for_restore():
    assert is_hide_block("visibility:visible; opacity:1;") is False


def test_harvest_css_blocks_returns_selector_and_decl():
    js = 'el.textContent = `ytd-reel-shelf-renderer, #related { display:none !important; }`;'
    blocks = harvest_css_blocks(js)
    assert ("ytd-reel-shelf-renderer, #related ", " display:none !important; ") in blocks


def test_harvest_string_selectors_picks_yt_like_strings():
    js = "const sel = 'ytd-comments'; const noise = 'hello world'; toggle(\"#related\");"
    found = harvest_string_selectors(js)
    assert "ytd-comments" in found
    assert "#related" in found
    assert "hello world" not in found
```

- [ ] **Step 2: Run test to verify the new tests fail**

Run: `uv run pytest tests/test_extract.py -v`
Expected: FAIL — `is_hide_block` / `harvest_css_blocks` / `harvest_string_selectors` not defined.

- [ ] **Step 3: Add the harvest functions to `extract.py`**

```python
# append to lockedin_filters/extract.py
_TEMPLATE_LITERAL = re.compile(r"`([^`]*)`", re.DOTALL)
_CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
_STRING_LITERAL = re.compile(r"""(['"])((?:\\.|(?!\1).)*)\1""")


def is_hide_block(declaration: str) -> bool:
    """True if a CSS declaration block hides (and is not a restore/keep-visible block)."""
    d = declaration.replace(" ", "").lower()
    if any(r.replace(" ", "") in d for r in RESTORE_DECLS):
        return False
    return any(h.replace(" ", "") in d for h in HIDE_DECLS)


def harvest_css_blocks(js_text: str) -> list[tuple[str, str]]:
    """Return (selector_list, declaration) pairs found inside JS template literals."""
    blocks: list[tuple[str, str]] = []
    for literal in _TEMPLATE_LITERAL.findall(js_text):
        if "{" not in literal:
            continue
        for sel_part, decl in _CSS_RULE.findall(literal):
            blocks.append((sel_part, decl))
    return blocks


def _looks_like_selector(value: str) -> bool:
    return any(tok in value for tok in YT_TOKENS) or ":has(" in value or "[overlay-style" in value


def harvest_string_selectors(js_text: str) -> list[str]:
    """Return selector-like string/quote literals (covers querySelectorAll args and the
    shared SELECTORS dict)."""
    out: list[str] = []
    for _quote, value in _STRING_LITERAL.findall(js_text):
        if _looks_like_selector(value):
            out.append(value)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extract.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add lockedin_filters/extract.py tests/test_extract.py
git commit -m "feat: harvest selectors from JS template-literal CSS and string literals"
```

---

## Task 6: `extract.py` — `extract_selectors` orchestration

**Files:**
- Modify: `lockedin_filters/extract.py`
- Test: `tests/test_extract.py`

- [ ] **Step 1: Add failing test (uses a temp upstream dir fixture)**

```python
# append to tests/test_extract.py
from lockedin_filters.extract import extract_selectors


def test_extract_selectors_integration(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "index.js").write_text(
        'x.textContent = `ytd-reel-shelf-renderer { display:none !important; }`;\n'
        'y.textContent = `#movie_player { filter:none !important; }`;\n'   # protected -> skipped
        'z.textContent = `.keep { visibility:visible !important; }`;\n'    # restore -> skipped
        "const s = 'ytd-comments'; toggle('img');\n"                       # img -> over-broad skip
    )
    result = extract_selectors(content)
    assert "ytd-reel-shelf-renderer" in result
    assert "ytd-comments" in result
    assert "#movie_player" not in result
    assert ".keep" not in result
    assert "img" not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extract.py::test_extract_selectors_integration -v`
Expected: FAIL — `extract_selectors` not defined.

- [ ] **Step 3: Add `extract_selectors` and `iter_js_files`**

```python
# append to lockedin_filters/extract.py
def iter_js_files(upstream_dir: Path) -> list[Path]:
    """All .js files under the upstream clone, sorted for determinism.

    We scan every .js file (not just manifest content_scripts) so that imported
    modules like shared/selectors.js are covered and the extractor is resilient to
    upstream file renames/additions. The over-broad guard in normalize_selector keeps
    non-YouTube selectors (e.g. the extension's settings popup) out of the result.
    """
    return sorted(upstream_dir.rglob("*.js"))


def extract_selectors(upstream_dir: Path) -> set[str]:
    """Harvest and normalize all hide-selectors from the upstream clone."""
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
        for raw in harvest_string_selectors(text):
            for piece in raw.split(","):
                norm = normalize_selector(piece)
                if norm:
                    selectors.add(norm)
    return selectors
```

- [ ] **Step 4: Run the whole extract test module**

Run: `uv run pytest tests/test_extract.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add lockedin_filters/extract.py tests/test_extract.py
git commit -m "feat: add extract_selectors orchestration over upstream JS files"
```

---

## Task 7: `data/supplement.txt` — the curated seed

**Files:**
- Create: `data/supplement.txt`
- Test: `tests/test_supplement.py`

- [ ] **Step 1: Create `data/supplement.txt`** (the user's authoritative list, line-broken)

```
! ==============================================================================
! YOUTUBE DE-ADDICTION FILTER LIST (Optimized for Desktop & Mobile)
! Source of truth for the curated floor. Written in uBO desktop style;
! build.py auto-generates the AdGuard #?#:contains twins.
! ==============================================================================

! --- 1. CORE FEED & SIDEBAR OVERHAUL ---
youtube.com##ytd-browse[page-subtype="home"] #primary
youtube.com###related

! --- 2. SHORTS REMOVAL ---
youtube.com##ytd-mini-guide-entry-renderer:has(a[title="Shorts"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Shorts"])
youtube.com##ytm-pivot-bar-item-renderer:has-text(Shorts)
youtube.com##ytd-rich-shelf-renderer:has([is-shorts])
youtube.com##ytm-reel-shelf-renderer

! --- 3. "YOU" & "EXPLORE" SECTIONS ---
youtube.com##ytd-guide-section-renderer:has(a[title="Shopping"])
youtube.com##ytd-guide-section-renderer:has(a[title="YouTube Premium"])
youtube.com##ytd-guide-entry-renderer:has(a[title="History"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Playlists"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Watch later"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Liked videos"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Your videos"])
youtube.com##ytd-guide-entry-renderer:has(a[title="Downloads"])
youtube.com##ytd-guide-collapsible-entry-renderer

! --- 4. THUMBNAIL ERADICATION ---
youtube.com##ytd-thumbnail img
youtube.com##ytd-playlist-thumbnail img
youtube.com##.media-item-thumbnail-container img
youtube.com##ytm-thumbnail-element img
youtube.com##ytd-playlist-header-renderer yt-image
youtube.com##ytd-playlist-header-renderer .hero-image-container

! --- 5. PLAYER DISTRACTIONS & END SCREENS ---
youtube.com###mouseover-overlay
youtube.com##ytd-moving-thumbnail-renderer
youtube.com##.ytp-cued-thumbnail-overlay
youtube.com##.player-poster
youtube.com##.ytp-ce-element
youtube.com##.html5-endscreen
youtube.com##.ytp-videowall-still
youtube.com##.ytp-fullscreen-grid

! --- 6. COMMENTS ---
youtube.com##ytd-comments

! --- 7. METRICS & ENGAGEMENT ---
youtube.com##ytd-notification-topbar-button-renderer
youtube.com##.badge-style-type-notification
youtube.com##ytd-guide-entry-renderer #newness-dot
youtube.com##ytd-video-meta-block span.ytd-video-meta-block:first-of-type
youtube.com##ytd-watch-metadata #info-container span:has-text(views)
youtube.com##ytd-watch-metadata #info-container span:has-text(view)
youtube.com##yt-formatted-string#owner-sub-count
youtube.com##yt-formatted-string#subscriber-count
youtube.com##ytd-subscribe-button-renderer
youtube.com##ytd-button-renderer:has-text(Try it free)
youtube.com##ytd-button-renderer:has-text(Premium)
youtube.com##segmented-like-dislike-button-view-model
youtube.com##like-button-view-model
youtube.com##dislike-button-view-model

! --- 8. SEARCH AUTOCOMPLETE ---
youtube.com##.ytSearchboxComponentSuggestionsContainer
```

- [ ] **Step 2: Write a test that every supplement rule line parses**

```python
# tests/test_supplement.py
from pathlib import Path

from lockedin_filters.build import selector_of

SUPPLEMENT = Path("data/supplement.txt")


def test_every_supplement_rule_line_parses():
    bad = []
    for line in SUPPLEMENT.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("!"):
            continue
        if selector_of(s) is None:
            bad.append(s)
    assert bad == [], f"unparseable supplement lines: {bad}"
```

- [ ] **Step 3: Run the test (expected to fail until `build.selector_of` exists)**

Run: `uv run pytest tests/test_supplement.py -v`
Expected: FAIL with `ImportError` (`build.selector_of` is created in Task 8). This is expected — proceed to Task 8, then re-run.

- [ ] **Step 4: Commit the supplement now (test goes green after Task 8)**

```bash
git add data/supplement.txt tests/test_supplement.py
git commit -m "feat: add curated supplement seed (authoritative rule floor)"
```

---

## Task 8: `build.py` — compose the published list

**Files:**
- Create: `lockedin_filters/build.py`
- Test: `tests/test_build.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_build.py
from lockedin_filters.build import (
    selector_of, canonical_selector, emit_rule, collect_rules,
    render, finalize, load_supplement_selectors, build,
)


def test_selector_of_parses_markers():
    assert selector_of("youtube.com##ytd-comments") == "ytd-comments"
    assert selector_of("youtube.com###related") == "#related"
    assert selector_of("youtube.com#?#ytd-x:contains(Shorts)") == "ytd-x:contains(Shorts)"
    assert selector_of("! a comment") is None


def test_canonical_selector_normalizes_contains_to_has_text():
    assert canonical_selector("ytd-x:contains(Shorts)") == "ytd-x:has-text(Shorts)"
    assert canonical_selector("ytd-comments") == "ytd-comments"


def test_emit_rule_plain_is_single_line():
    assert emit_rule("ytd-comments") == ["youtube.com##ytd-comments"]


def test_emit_rule_text_dual_emits_with_quote_strip():
    assert emit_rule('ytd-x:has-text("Shorts")') == [
        'youtube.com##ytd-x:has-text("Shorts")',
        "youtube.com#?#ytd-x:contains(Shorts)",
    ]


def test_collect_rules_merges_supplement_and_extracted_sorted_unique(tmp_path):
    supp = tmp_path / "supplement.txt"
    supp.write_text(
        "! header comment\n"
        "youtube.com##ytd-comments\n"
        "youtube.com##ytm-pivot-bar-item-renderer:has-text(Shorts)\n"
    )
    extracted = {"ytd-comments", "ytd-reel-shelf-renderer"}  # ytd-comments already in supplement
    rules = collect_rules(str(supp), extracted)
    assert rules == sorted(set(rules))                      # sorted + unique
    assert "youtube.com##ytd-comments" in rules
    assert "youtube.com##ytd-reel-shelf-renderer" in rules
    assert "youtube.com#?#ytm-pivot-bar-item-renderer:contains(Shorts)" in rules


def test_render_includes_header_and_version():
    out = render("2026.06.06", ["youtube.com##ytd-comments"])
    assert "! Title:" in out
    assert "! Version: 2026.06.06" in out
    assert "! Expires: 1 day" in out
    assert out.rstrip().endswith("youtube.com##ytd-comments")


def test_finalize_reuses_old_text_when_body_unchanged():
    old = render("2026.06.01", ["youtube.com##ytd-comments"])
    new = render("2026.06.06", ["youtube.com##ytd-comments"])
    assert finalize(new, old) == old            # only version differs -> keep old (no churn)


def test_finalize_uses_new_text_when_body_changed():
    old = render("2026.06.01", ["youtube.com##ytd-comments"])
    new = render("2026.06.06", ["youtube.com##ytd-comments", "youtube.com##ytd-x"])
    assert finalize(new, old) == new


def test_load_supplement_selectors(tmp_path):
    supp = tmp_path / "supplement.txt"
    supp.write_text("! c\nyoutube.com##ytd-comments\nyoutube.com##ytd-x:has-text(Premium)\n")
    sels = load_supplement_selectors(str(supp))
    assert "ytd-comments" in sels
    assert "ytd-x:has-text(Premium)" in sels
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build.py -v`
Expected: FAIL — `lockedin_filters.build` not found.

- [ ] **Step 3: Write `build.py`**

```python
# lockedin_filters/build.py
"""Compose dist/lockedin-youtube.txt from the curated supplement + extracted rules."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date
from pathlib import Path

from . import extract
from .textrules import has_contains, has_text, to_contains, to_has_text

DOMAIN = "youtube.com"
# Matches a cosmetic-filter line and captures the selector after the marker
# (## element-hide, #?# extended-css, #@# allowlist).
_RULE_RE = re.compile(r"^youtube\.com#@?\??#(.+)$")


def selector_of(line: str) -> str | None:
    """Return the selector part of a filter line, or None if the line is not a rule."""
    m = _RULE_RE.match(line.strip())
    return m.group(1).strip() if m else None


def canonical_selector(sel: str) -> str:
    """Map :contains(...) to its :has-text(...) form so engine twins collapse to one key."""
    return to_has_text(sel) if has_contains(sel) else sel


def emit_rule(selector: str) -> list[str]:
    """Render a canonical (uBO-form) selector to published filter line(s)."""
    if has_text(selector):
        return [f"{DOMAIN}##{selector}", f"{DOMAIN}#?#{to_contains(selector)}"]
    return [f"{DOMAIN}##{selector}"]


def _supplement_selectors_in_order(supplement_path: str) -> list[str]:
    sels: list[str] = []
    for line in Path(supplement_path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("!"):
            continue
        sel = selector_of(s)
        if sel is not None:
            sels.append(canonical_selector(sel))
    return sels


def load_supplement_selectors(supplement_path: str) -> set[str]:
    """Canonical selectors present in the supplement (for the lint floor check)."""
    return set(_supplement_selectors_in_order(supplement_path))


def collect_rules(supplement_path: str, extracted: set[str]) -> list[str]:
    """Merge supplement + extracted selectors into a sorted, de-duplicated rule list."""
    selectors: set[str] = set(_supplement_selectors_in_order(supplement_path))
    selectors.update(extracted)
    lines: set[str] = set()
    for sel in selectors:
        lines.update(emit_rule(sel))
    return sorted(lines)


def header(build_date: str) -> str:
    return (
        "! Title: LockedIn YouTube — Maximalist Distraction Filter\n"
        "! Description: Strips YouTube to a focus-only surface: home feed, Shorts, "
        "watch-page recommendations, thumbnails, comments, player end screens, "
        "engagement metrics (likes, views, subscriber count), and guide/navigation "
        "clutter. Derived from the LockedIn-YT extension. Works in uBlock Origin "
        "(desktop) and AdGuard for iOS.\n"
        "! Homepage: https://github.com/dlithio/yt-all-distract-list\n"
        "! Source extension: https://github.com/KartikHalkunde/LockedIn-YT "
        "(MIT, © Kartik Halkunde)\n"
        "! Expires: 1 day\n"
        f"! Version: {build_date}\n"
        "! License: MIT\n"
    )


def render(build_date: str, rules: list[str]) -> str:
    return header(build_date) + "!\n" + "\n".join(rules) + "\n"


def _strip_version(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.startswith("! Version:"))


def finalize(new_text: str, old_text: str | None) -> str:
    """If only the version line differs from the published file, keep the old file so a
    quiet day produces no git diff (and therefore no commit)."""
    if old_text is not None and _strip_version(new_text) == _strip_version(old_text):
        return old_text
    return new_text


def build(supplement_path: str, extracted: set[str], build_date: str,
          old_text: str | None = None) -> str:
    rules = collect_rules(supplement_path, extracted)
    return finalize(render(build_date, rules), old_text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the LockedIn YouTube filter list.")
    parser.add_argument("--upstream", required=True, help="path to the upstream clone")
    parser.add_argument("--supplement", default="data/supplement.txt")
    parser.add_argument("--out", default="dist/lockedin-youtube.txt")
    parser.add_argument("--snapshot", default="data/upstream-selectors.snapshot.json")
    parser.add_argument("--build-date", default=os.environ.get("BUILD_DATE"))
    args = parser.parse_args(argv)

    build_date = args.build_date or date.today().strftime("%Y.%m.%d")
    extracted = extract.extract_selectors(Path(args.upstream))

    snapshot_path = Path(args.snapshot)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(sorted(extracted), indent=2) + "\n", encoding="utf-8")

    out_path = Path(args.out)
    old_text = out_path.read_text(encoding="utf-8") if out_path.exists() else None
    text = build(args.supplement, extracted, build_date, old_text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path} ({len(text.splitlines())} lines).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run build + supplement tests to verify they pass**

Run: `uv run pytest tests/test_build.py tests/test_supplement.py -v`
Expected: PASS (all of test_build.py + the supplement parse test)

- [ ] **Step 5: Commit**

```bash
git add lockedin_filters/build.py tests/test_build.py
git commit -m "feat: compose published list with dual-emit and version stamping"
```

---

## Task 9: `lint.py` — the publish gate

**Files:**
- Create: `lockedin_filters/lint.py`
- Test: `tests/test_lint.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lint.py
from lockedin_filters.lint import lint_text, references_ask

GOOD = (
    "! Title: x\n! Expires: 1 day\n! Version: 2026.06.06\n!\n"
    "youtube.com##ytd-comments\n"
    "youtube.com##ytd-x:has-text(Premium)\n"
    "youtube.com#?#ytd-x:contains(Premium)\n"
    'youtube.com##ytd-guide-entry-renderer:has(a[title="Shorts"])\n'
)
SUPP = {"ytd-comments", "ytd-x:has-text(Premium)"}


def test_good_list_passes():
    assert lint_text(GOOD, SUPP) == []


def test_missing_header_flagged():
    text = "youtube.com##ytd-comments\n"
    errors = lint_text(text, {"ytd-comments"})
    assert any("missing header" in e for e in errors)


def test_invalid_prefix_flagged():
    text = "! Title: x\n! Expires: 1 day\n! Version: 1\n!\nexample.com##ytd-x\n"
    assert any("invalid rule prefix" in e for e in lint_text(text, set()))


def test_contains_in_ubo_line_flagged():
    text = "! Title: x\n! Expires: 1 day\n! Version: 1\n!\nyoutube.com##ytd-x:contains(Premium)\n"
    assert any(":contains in ##" in e for e in lint_text(text, set()))


def test_has_text_in_adguard_line_flagged():
    text = "! Title: x\n! Expires: 1 day\n! Version: 1\n!\nyoutube.com#?#ytd-x:has-text(Premium)\n"
    assert any(":has-text in #?#" in e for e in lint_text(text, set()))


def test_quotes_inside_contains_flagged_but_attribute_quotes_ok():
    bad = '! Title: x\n! Expires: 1 day\n! Version: 1\n!\nyoutube.com#?#ytd-x:contains("Premium")\n'
    assert any("quotes inside :contains" in e for e in lint_text(bad, set()))
    ok = '! Title: x\n! Expires: 1 day\n! Version: 1\n!\nyoutube.com#?#ytd-x[title="Shorts"]\n'
    assert not any("quotes inside :contains" in e for e in lint_text(ok, set()))


def test_duplicate_flagged():
    text = "! Title: x\n! Expires: 1 day\n! Version: 1\n!\nyoutube.com##ytd-x\nyoutube.com##ytd-x\n"
    assert any("duplicate" in e for e in lint_text(text, set()))


def test_protected_player_flagged():
    text = "! Title: x\n! Expires: 1 day\n! Version: 1\n!\nyoutube.com###movie_player\n"
    assert any("protected element" in e for e in lint_text(text, set()))


def test_references_ask_flagged():
    text = ('! Title: x\n! Expires: 1 day\n! Version: 1\n!\n'
            'youtube.com##button[aria-label="Ask"]\n')
    assert any("Ask" in e for e in lint_text(text, set()))
    assert references_ask('button[aria-label="Ask"]')
    assert references_ask("ytd-x:has-text(Ask)")
    assert not references_ask("ytd-comments")


def test_supplement_floor_violation_flagged():
    text = "! Title: x\n! Expires: 1 day\n! Version: 1\n!\nyoutube.com##ytd-comments\n"
    errors = lint_text(text, {"ytd-comments", "ytd-missing"})
    assert any("floor violation" in e for e in errors)


def test_explosion_ceiling_flagged():
    rules = "\n".join(f"youtube.com##ytd-x{i}" for i in range(10))
    text = f"! Title: x\n! Expires: 1 day\n! Version: 1\n!\n{rules}\n"
    assert any("exceeds ceiling" in e for e in lint_text(text, set(), max_rules=5))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_lint.py -v`
Expected: FAIL — `lockedin_filters.lint` not found.

- [ ] **Step 3: Write `lint.py`**

```python
# lockedin_filters/lint.py
"""Validate dist/lockedin-youtube.txt — the publish gate. Nonzero exit => do not publish."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .build import canonical_selector, load_supplement_selectors, selector_of

MAX_RULES = 5000  # explosion ceiling (tunable; see spec §14 — bounds deferred)
REQUIRED_HEADERS = ("! Title:", "! Expires:", "! Version:")

# Elements that must never be hidden. The "Ask" button is handled by references_ask().
PROTECTED = (
    "#movie_player", ".html5-video-player", ".html5-main-video", "video.video-stream",
    "ytd-engagement-panel-section-list-renderer", "ytd-transcript-segment-list-renderer",
)

_VALID_PREFIX = re.compile(r"^youtube\.com#@?\??#")
_CONTAINS_ARG = re.compile(r":contains\((.*?)\)")
_TEXT_OR_ARIA = re.compile(r":has-text\((.*?)\)|:contains\((.*?)\)|\[aria-label[^\]]*\]")


def references_ask(selector: str) -> bool:
    """True if the selector targets something labelled 'Ask' (the protected AI button).

    Best-effort until the exact selector is confirmed on-device (spec §14.3): matches the
    word 'Ask' inside a text pseudo-class or an aria-label attribute."""
    for match in _TEXT_OR_ARIA.finditer(selector):
        if re.search(r"\bask\b", match.group(0), re.IGNORECASE):
            return True
    return False


def lint_text(text: str, supplement_selectors: set[str], max_rules: int = MAX_RULES) -> list[str]:
    errors: list[str] = []
    lines = text.splitlines()

    for required in REQUIRED_HEADERS:
        if not any(line.startswith(required) for line in lines):
            errors.append(f"missing header: {required}")

    rule_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith("!")]
    seen: set[str] = set()
    for line in rule_lines:
        if not _VALID_PREFIX.match(line):
            errors.append(f"invalid rule prefix: {line}")
            continue
        if line.count("(") != line.count(")") or line.count("[") != line.count("]"):
            errors.append(f"unbalanced brackets: {line}")
        if line.startswith("youtube.com##") and ":contains(" in line:
            errors.append(f":contains in ## line: {line}")
        if line.startswith("youtube.com#?#") and ":has-text(" in line:
            errors.append(f":has-text in #?# line: {line}")
        for arg in _CONTAINS_ARG.findall(line):
            if '"' in arg or "'" in arg:
                errors.append(f"quotes inside :contains: {line}")
        sel = selector_of(line) or ""
        low = sel.lower()
        if any(p.lower() in low for p in PROTECTED):
            errors.append(f"targets protected element: {line}")
        if references_ask(sel):
            errors.append(f"targets protected 'Ask' button: {line}")
        if line in seen:
            errors.append(f"duplicate: {line}")
        seen.add(line)

    if len(rule_lines) > max_rules:
        errors.append(f"rule count {len(rule_lines)} exceeds ceiling {max_rules}")

    published = {canonical_selector(selector_of(l)) for l in rule_lines if selector_of(l)}
    for sel in supplement_selectors:
        if canonical_selector(sel) not in published:
            errors.append(f"supplement floor violation, missing: {sel}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint the LockedIn YouTube filter list.")
    parser.add_argument("dist")
    parser.add_argument("--supplement", default="data/supplement.txt")
    args = parser.parse_args(argv)

    text = Path(args.dist).read_text(encoding="utf-8")
    supplement = load_supplement_selectors(args.supplement)
    errors = lint_text(text, supplement)
    for err in errors:
        print(f"LINT ERROR: {err}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} lint error(s).", file=sys.stderr)
        return 1
    print("Lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lint.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Run the full test suite + ruff**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all tests pass; ruff reports no errors.

- [ ] **Step 6: Commit**

```bash
git add lockedin_filters/lint.py tests/test_lint.py
git commit -m "feat: add publish-gate linter (validity, protected, floor, explosion)"
```

---

## Task 10: Generate and commit the initial published list

**Files:**
- Create: `dist/lockedin-youtube.txt`, `data/upstream-selectors.snapshot.json`

- [ ] **Step 1: Clone upstream locally (temp)**

Run: `git clone --depth 1 https://github.com/KartikHalkunde/LockedIn-YT.git upstream`
Expected: `upstream/` directory created (git-ignored).

- [ ] **Step 2: Build the list**

Run: `BUILD_DATE=2026.06.06 uv run python -m lockedin_filters.build --upstream upstream`
Expected: prints `Wrote dist/lockedin-youtube.txt (N lines).`

- [ ] **Step 3: Run the lint gate**

Run: `uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt`
Expected: prints `Lint passed.` (exit 0). If it fails, inspect the reported lines — likely an over-broad extracted rule; tighten `YT_TOKENS`/`PROTECTED` in `extract.py` or add to the protected set, then rebuild.

- [ ] **Step 4: Eyeball the output**

Run: `uv run python -c "print(open('dist/lockedin-youtube.txt').read()[:1500])"`
Expected: metadata header, then `youtube.com##`/`youtube.com#?#` rules including every supplement rule plus extracted additions. Confirm no rule targets `#movie_player` or the video element.

- [ ] **Step 5: Commit the generated artifacts**

```bash
git add dist/lockedin-youtube.txt data/upstream-selectors.snapshot.json
git commit -m "build: generate initial published filter list"
```

---

## Task 11: `validate.yml` — PR/push quality gate

**Files:**
- Create: `.github/workflows/validate.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: validate
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - name: Lint the published list
        run: uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt --supplement data/supplement.txt
      - name: Run tests
        run: uv run pytest -q
```

- [ ] **Step 2: Sanity-check the YAML parses**

Run: `uv run python -c "import sys,ast; print('ok')"` is not enough — instead confirm the file is well-formed YAML using the stdlib-free approach: open it and check indentation visually, then (optional) if a YAML parser is available run `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/validate.yml')); print('yaml ok')"`. If `yaml` isn't installed, skip — GitHub validates the workflow on push.
Expected: `yaml ok` (or skipped). Indentation is two-space, jobs/steps nested correctly.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "ci: add validate workflow (lint + pytest)"
```

---

## Task 12: `sync.yml` — daily build & publish

**Files:**
- Create: `.github/workflows/sync.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: sync
on:
  schedule:
    - cron: "17 6 * * *"
  workflow_dispatch:
permissions:
  contents: write
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - name: Clone upstream (read-only; never executed)
        run: git clone --depth 1 https://github.com/KartikHalkunde/LockedIn-YT.git upstream
      - name: Build the list
        run: |
          BUILD_DATE=$(date -u +%Y.%m.%d) \
            uv run python -m lockedin_filters.build \
              --upstream upstream \
              --supplement data/supplement.txt \
              --out dist/lockedin-youtube.txt \
              --snapshot data/upstream-selectors.snapshot.json
      - name: Lint gate (no publish on failure)
        run: uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt --supplement data/supplement.txt
      - name: Commit if changed
        run: |
          if [[ -n "$(git status --porcelain dist data)" ]]; then
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git add dist/lockedin-youtube.txt data/upstream-selectors.snapshot.json
            git commit -m "chore: daily sync $(date -u +%Y-%m-%d)"
            git push
          else
            echo "No changes since last run."
          fi
```

- [ ] **Step 2: Verify the gate ordering**

Confirm by reading the file: the **Lint gate** step runs *before* **Commit if changed**, so a gate failure aborts the job (and `set -e` default in the run step) before anything is committed. The previously published list keeps serving.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/sync.yml
git commit -m "ci: add daily sync workflow (build -> lint gate -> commit to main)"
```

---

## Task 13: `README.md` — end-user instructions

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# LockedIn YouTube — Maximalist Distraction Filter

A self-updating cosmetic filter list that strips YouTube down to a focus-only surface
(home feed, Shorts, recommendations, thumbnails, comments, end screens, engagement
metrics, and navigation clutter). It is regenerated daily from the
[LockedIn-YT](https://github.com/KartikHalkunde/LockedIn-YT) extension source.

## Subscribe URL

```
https://raw.githubusercontent.com/dlithio/yt-all-distract-list/main/dist/lockedin-youtube.txt
```

The list declares `! Expires: 1 day`, so both engines auto-refresh daily.

## uBlock Origin (desktop)

1. Open the uBO dashboard → **Filter lists**.
2. Scroll to **Import** (bottom), tick it, and paste the subscribe URL.
3. Click **Apply changes**.

## AdGuard for iOS

1. Open AdGuard → **Filters** → **Custom** → **Add custom filter**.
2. Paste the subscribe URL and add it.
3. Enable **Advanced Protection** (required for the `#?#` text-matching rules).
4. Ensure AdGuard's Safari extensions are enabled: iOS **Settings → Safari → Extensions**.
   Requires roughly iOS 16.4+ (for `:has()` support).

## Limitations

A cosmetic filter list cannot change behavior, only hide elements. It does **not**:

- redirect URLs (`/shorts/...` → `/watch`, Home → Subscriptions);
- truly disable autoplay — it hides Shorts entry points and any autoplay/next-up UI it
  can, but a queued next video may still play.

These behaviors are not available in this setup.

## Attribution

Selectors are derived from [KartikHalkunde/LockedIn-YT](https://github.com/KartikHalkunde/LockedIn-YT)
(MIT, © Kartik Halkunde). This project is MIT licensed.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add end-user README with subscribe instructions"
```

---

## Task 14: `docs/DEVELOPMENT.md` — developer guide (with verbatim engineering note)

**Files:**
- Create: `docs/DEVELOPMENT.md`

- [ ] **Step 1: Write `docs/DEVELOPMENT.md`**

````markdown
# Development

## Setup

```bash
uv sync                 # create the venv, install dev deps (pytest, ruff)
uv run pytest -q        # run tests
uv run ruff check .     # lint the Python
```

## Mental model

- `data/supplement.txt` is the **authoritative floor** — a hand-curated list of rules
  written in uBlock Origin desktop style. The published list always contains every rule
  in it (`lint.py` enforces `published ⊇ supplement`).
- `lockedin_filters/extract.py` harvests hide-selectors from a clone of the LockedIn-YT
  extension and **adds** them on top. Extraction is strictly additive.
- `lockedin_filters/build.py` merges the two, auto-generates AdGuard twins for text
  rules, sorts/de-dupes, stamps the version, and writes `dist/lockedin-youtube.txt`.
- `lockedin_filters/lint.py` is the publish gate.

## Regenerate locally

```bash
git clone --depth 1 https://github.com/KartikHalkunde/LockedIn-YT.git upstream
BUILD_DATE=$(date -u +%Y.%m.%d) uv run python -m lockedin_filters.build --upstream upstream
uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt
```

## Adding a rule by hand

Add it to `data/supplement.txt` in uBO style (`youtube.com##selector`, or
`youtube.com##selector:has-text(Text)` for text matching — do **not** hand-write the
`#?#` twin; `build.py` generates it). Then rebuild and lint.

## CI

- `validate.yml` (push/PR): runs the linter and pytest.
- `sync.yml` (daily cron + manual dispatch): clones upstream, rebuilds, runs the lint
  gate, and commits to `main` **only if the gate passes and the rule set changed**. A
  gate failure aborts the job and publishes nothing; the previous list keeps serving.

Trigger a manual run from the Actions tab → **sync** → **Run workflow**.

## "YouTube broke something" runbook

1. Identify the new element/selector on the page.
2. Add a rule to `data/supplement.txt`.
3. `uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt` (after a rebuild).
4. Commit & push — `validate.yml` gates it; the next sync republishes.

## Why we compile text rules (uBO `:has-text` → AdGuard `:contains`)

`build.py` emits an explicit AdGuard `#?#...:contains(...)` twin (with quotes stripped)
for every uBO `##...:has-text(...)` rule. The rationale, from an external engineering
review:

> Your agent is being a **very sharp engineer** here. While their explanation of *why*
> it happens is slightly off on a minor technical detail, their solution (`build.py`
> auto-emitting the AdGuard twins) is **absolutely necessary and highly recommended**
> for a seamless cross-platform setup.
>
> ### 1. Where the Agent is Slightly Wrong (The Nuance)
> The agent claims that `:has-text()` is a "uBO-only text rule." That is not strictly
> true. AdGuard's core engine actually recognizes `:has-text()` as an official, native
> alias for its own `:contains()` selector for compatibility reasons. If you were running
> AdGuard on a desktop browser, it would parse `:has-text()` just fine.
>
> ### 2. Where the Agent is 100% Right (The iOS Catch)
> The real issue isn't the keyword `:has-text()`; it's the **iOS Safari architecture**.
> Because Apple forces ad blockers to use native Safari Content Blocking APIs, AdGuard
> iOS has to run all incoming rules through an open-source compiler it built called
> **`SafariConverterLib`**.
> - When `SafariConverterLib` looks at your list, it sees the standard uBlock element
>   hiding prefix (`##`).
> - It tries to compile those rules into a native iOS Safari JSON array.
> - Because Safari's native engine is completely blind to advanced text-matching logic,
>   the compiler gets confused by the combination of `##` and `:has-text()`.
>
> Unless a rule explicitly uses AdGuard's procedural selector prefix (**`#?#`**), the iOS
> app will frequently misclassify the rule, fail to hand it off to the Advanced
> Protection JavaScript engine, and **silently drop it**.
>
> ### 3. The Hidden "Quotation Mark" Trap
> There is another massive headache this script avoids. In uBlock Origin, both of these
> are valid:
> - `youtube.com##span:has-text(Shorts)`
> - `youtube.com##span:has-text("Shorts")` *(with quotes)*
>
> However, AdGuard's parser completely chokes if there are quotation marks inside a
> text-matching selector. If you or an upstream list you pull from ever accidentally
> includes quotes, AdGuard iOS will break. By forcing `build.py` to strip the rule down
> and cleanly re-emit it as an explicit AdGuard procedural rule
> (`youtube.com#?#span:contains(Shorts)`), your script completely bypasses the fragile
> iOS compiler wrapper.
>
> ### The Verdict
> **Yes, let the agent build this feature.** It elegantly solves the "Write Once, Run
> Everywhere" problem. Your source file (`supplement.txt`) stays clean, human-readable,
> and formatted in the standard desktop style you are used to. Meanwhile, the script
> ensures that the actual published file contains the bulletproof syntax required to
> force AdGuard iOS's JavaScript engine into action.
````

- [ ] **Step 2: Commit**

```bash
git add docs/DEVELOPMENT.md
git commit -m "docs: add developer guide with text-rule compilation rationale"
```

---

## Task 15: `LICENSE`

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Create the MIT license**

```
MIT License

Copyright (c) 2026 dlithio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Final full verification**

Run: `uv run pytest -q && uv run ruff check . && uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt`
Expected: all tests pass, ruff clean, `Lint passed.`

- [ ] **Step 3: Commit**

```bash
git add LICENSE
git commit -m "docs: add MIT license"
```

---

## Post-implementation: deploy checklist (manual, by the user)

These steps need the user's GitHub account and a browser; not part of the automated build.

- [ ] Push the repo to `https://github.com/dlithio/yt-all-distract-list` (public, so the raw URL is reachable).
- [ ] Actions tab → run **sync** via **Run workflow** once to confirm the end-to-end clone→build→gate→commit path works.
- [ ] Subscribe in uBO and AdGuard iOS using the README URL; spot-check YouTube (home feed gone, Shorts gone, recommendations gone, thumbnails blanked, comments gone, **video still plays**, transcript + the "Ask" button still present).
- [ ] Confirm the exact "Ask" button selector on-device (spec §14.3) and tighten `references_ask`/`PROTECTED` if needed.
```