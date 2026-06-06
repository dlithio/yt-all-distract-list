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


def render_markdown(annotated: list[dict], diff: dict, *, build_date: str, upstream_sha: str,
                    first_run: bool = False) -> str:
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
    if first_run:
        # No prior candidates snapshot to diff against — listing everything as "new"
        # would be noise, so record a baseline instead.
        out.append(f"_Baseline run — {total} selectors recorded; future runs show only what changed._")
        out.append("")
    else:
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
    # Separate the safe (unguarded) candidates from the guarded ones so a guarded
    # selector is never listed under a "safe to adopt" header.
    safe = [c for c in unblocked if c["guard"] is None]
    guarded = [c for c in unblocked if c["guard"] is not None]
    groups = (
        ("css", "From real hide-CSS (usually safe to adopt)"),
        ("both", "From both hide-CSS and query-anchors"),
        ("string", "From query-anchors only (often over-broad — scope before adding)"),
    )
    for key, title in groups:
        rows = [c for c in safe if _bucket(c["sources"]) == key]
        if not rows:
            continue
        out.append(f"### {title}")
        for c in rows:
            out.append(f"- `{c['selector']}`")
        out.append("")
    if guarded:
        out.append("### ⚠ Guarded — do NOT add without scoping (the lint gate will reject the bare form)")
        for c in guarded:
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
    first_run = not cand_path.exists()
    previous: set[str] = set()
    if not first_run:
        try:
            previous = {c["selector"] for c in json.loads(cand_path.read_text(encoding="utf-8"))}
        except (ValueError, KeyError, TypeError):
            previous = set()
    diff = diff_candidates(current, previous)

    cand_path.parent.mkdir(parents=True, exist_ok=True)
    cand_path.write_text(render_json(annotated), encoding="utf-8")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        render_markdown(annotated, diff, build_date=args.build_date,
                        upstream_sha=args.upstream_sha, first_run=first_run),
        encoding="utf-8",
    )
    print(f"Wrote {args.candidates} and {args.out}: {len(annotated)} harvested, "
          f"{sum(1 for c in annotated if not c['published'])} unblocked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
