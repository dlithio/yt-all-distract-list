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
# Matches a cosmetic-filter line and captures the selector after the marker.
# We only ever produce/consume HIDE rules: `##` (element-hide) and `#?#` (extended-css).
# Allowlist/exception markers (`#@#`/`#@?#`) are deliberately NOT matched — accepting
# them would let an un-hide line be silently re-emitted as a hide rule.
_RULE_RE = re.compile(r"^youtube\.com#\??#(.+)$")


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
    return "\n".join(ln for ln in text.splitlines() if not ln.startswith("! Version:"))


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
