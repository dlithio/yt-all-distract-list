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

# Over-broad page/app/nav shells that contain the player, the protected side panels,
# and/or core navigation. Harvested from the extension's detection probes
# (`document.querySelector('ytd-app')` etc.), never from hide-intents — hiding any of
# these would blank the whole app, break navigation, or take the video down with it.
# Also includes JS event-name strings that look selector-ish but match no element.
# Matched against the *exact* normalized selector, so scoped descendants like
# `ytd-browse[page-subtype="home"] #primary` are unaffected.
OVER_BROAD = frozenset({
    "ytd-app", "ytm-app",
    "ytd-browse", "ytm-browse",
    "ytd-watch-flexy", "ytm-watch",
    "ytd-page-manager",
    "yt-navigate-finish", "yt-page-data-updated", "yt-page-type-changed",
})

# Search must stay usable (explicit user requirement). These are the *bare* search
# box / results-page containers — hiding any of them whole would take search down.
# Matched against the EXACT normalized selector, so SCOPED rules that strip
# distractions *inside* search (e.g. `ytd-search ytd-shelf-renderer`,
# `[page-subtype="search"] ytd-reel-shelf-renderer`) are intentionally still allowed.
SEARCH_SURFACES = frozenset({
    "ytd-search", "ytm-search",
    "ytd-searchbox", "ytm-searchbox",
    "ytd-two-column-search-results-renderer",
})

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
    "ytm-engagement-panel-section-list-renderer", "ytm-transcript-segment-list-renderer",
)

_ANCESTOR = re.compile(r"html\[data-lockedin-[^\]]*\]\s*")
_NOT_GUARD = re.compile(r":not\(\[data-lockedin-[^\]]*\]\)")
_ATTR_GUARD = re.compile(r"\[data-lockedin-[^\]]*\]")
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_WS = re.compile(r"\s+")


def normalize_selector(selector: str) -> str | None:
    """Clean one harvested selector. Return the normalized selector, or None if it
    should be skipped (protected, over-broad, malformed, or empty)."""
    sel = selector.strip()
    sel = _CSS_COMMENT.sub(" ", sel)
    sel = _ANCESTOR.sub("", sel)
    sel = _NOT_GUARD.sub("", sel)
    sel = _ATTR_GUARD.sub("", sel)
    sel = _WS.sub(" ", sel).strip()
    if not sel:
        return None
    # Reject bare/truncated token fragments like `ytd-` or a lone `yt-` that slipped
    # in from a `tagName.startsWith('ytd-')` probe — these are not real elements.
    if sel in YT_TOKENS or sel.endswith("-"):
        return None
    if sel in OVER_BROAD or sel in SEARCH_SURFACES or sel in CONTENT_RENDERERS:
        return None
    low = sel.lower()
    if any(p.lower() in low for p in PROTECTED_SUBSTRINGS):
        return None
    if not any(tok in sel for tok in YT_TOKENS):
        return None
    return sel


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
        # Drop CSS comments first so their text (which can contain commas) never leaks
        # into the captured selector list.
        literal = _CSS_COMMENT.sub(" ", literal)
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
