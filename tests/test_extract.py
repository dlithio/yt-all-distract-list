from lockedin_filters.extract import (
    normalize_selector,
    is_hide_block,
    harvest_css_blocks,
    harvest_string_selectors,
    extract_selectors,
)


def test_normalize_accepts_youtube_component():
    assert normalize_selector("ytd-reel-shelf-renderer") == "ytd-reel-shelf-renderer"


def test_normalize_strips_lockedin_guards():
    raw = 'html[data-lockedin-shorts="true"] ytd-reel-shelf-renderer:not([data-lockedin-hidden])'
    assert normalize_selector(raw) == "ytd-reel-shelf-renderer"


def test_normalize_collapses_whitespace():
    assert normalize_selector("ytd-browse   #primary") == "ytd-browse #primary"


def test_normalize_rejects_protected_player():
    assert normalize_selector("#movie_player") is None
    assert normalize_selector("video.video-stream") is None


def test_normalize_rejects_protected_transcript_panel():
    assert normalize_selector("ytd-transcript-segment-list-renderer") is None


def test_normalize_rejects_over_broad_generic():
    assert normalize_selector("img") is None
    assert normalize_selector("#primary") is None
    assert normalize_selector("span") is None


def test_normalize_keeps_view_model_components():
    assert normalize_selector("like-button-view-model") == "like-button-view-model"


def test_is_hide_block_true_for_display_none():
    assert is_hide_block("display:none !important;") is True


def test_is_hide_block_false_for_restore():
    assert is_hide_block("visibility:visible; opacity:1;") is False


def test_harvest_css_blocks_returns_selector_and_decl():
    js = 'el.textContent = `ytd-reel-shelf-renderer, #related { display:none !important; }`;'
    blocks = harvest_css_blocks(js)
    assert ("ytd-reel-shelf-renderer, #related ", " display:none !important; ") in blocks


def test_harvest_string_selectors_picks_yt_like_strings():
    js = "const sel = 'ytd-comments'; const noise = 'hello world'; toggle(\"#related\");"
    found = harvest_string_selectors(js)
    assert "ytd-comments" in found
    assert "#related" in found
    assert "hello world" not in found


def test_extract_selectors_integration(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "index.js").write_text(
        'x.textContent = `ytd-reel-shelf-renderer { display:none !important; }`;\n'
        'y.textContent = `#movie_player { filter:none !important; }`;\n'   # protected -> skipped
        'z.textContent = `.keep { visibility:visible !important; }`;\n'    # restore -> skipped
        "const s = 'ytd-comments'; toggle('img');\n"                       # img -> over-broad skip
    )
    result = extract_selectors(content)
    assert "ytd-reel-shelf-renderer" in result
    assert "ytd-comments" in result
    assert "#movie_player" not in result
    assert ".keep" not in result
    assert "img" not in result
