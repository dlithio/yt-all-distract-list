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
