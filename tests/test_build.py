# tests/test_build.py
from lockedin_filters.build import (
    selector_of, canonical_selector, emit_rule, collect_rules,
    render, finalize, load_supplement_selectors,
)


def test_selector_of_parses_markers():
    assert selector_of("youtube.com##ytd-comments") == "ytd-comments"
    assert selector_of("youtube.com###related") == "#related"
    assert selector_of("youtube.com#?#ytd-x:contains(Shorts)") == "ytd-x:contains(Shorts)"
    assert selector_of("! a comment") is None
    # allowlist/exception markers are not hide rules -> not parsed
    assert selector_of("youtube.com#@#ytd-comments") is None


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
