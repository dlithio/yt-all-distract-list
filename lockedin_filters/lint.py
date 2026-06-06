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
