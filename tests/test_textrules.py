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
