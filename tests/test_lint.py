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


def test_protected_mobile_engagement_panel_flagged():
    text = ("! Title: x\n! Expires: 1 day\n! Version: 1\n!\n"
            "youtube.com##ytm-engagement-panel-section-list-renderer\n")
    assert any("protected element" in e for e in lint_text(text, set()))


def test_supplement_floor_violation_flagged():
    text = "! Title: x\n! Expires: 1 day\n! Version: 1\n!\nyoutube.com##ytd-comments\n"
    errors = lint_text(text, {"ytd-comments", "ytd-missing"})
    assert any("floor violation" in e for e in errors)


def test_explosion_ceiling_flagged():
    rules = "\n".join(f"youtube.com##ytd-x{i}" for i in range(10))
    text = f"! Title: x\n! Expires: 1 day\n! Version: 1\n!\n{rules}\n"
    assert any("exceeds ceiling" in e for e in lint_text(text, set(), max_rules=5))
