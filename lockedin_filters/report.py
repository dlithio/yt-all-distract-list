"""Generate the maintenance report: a catalog of every selector the upstream extension
references that the published list does NOT block, plus a day-over-day change summary.

Observability only — never gates publishing. Pure stdlib.
"""
from __future__ import annotations

from pathlib import Path

from . import extract
from .build import canonical_selector, selector_of

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
