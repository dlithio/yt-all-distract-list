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
