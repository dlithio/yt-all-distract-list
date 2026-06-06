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


def test_normalize_rejects_protected_mobile_panels():
    # AdGuard iOS targets m.youtube.com; the mobile ytm- twins of the
    # engagement/transcript side panel must be protected too (spec: best-effort ytm-*).
    assert normalize_selector("ytm-engagement-panel-section-list-renderer") is None
    assert normalize_selector("ytm-transcript-segment-list-renderer") is None


def test_normalize_rejects_over_broad_shells():
    # App/page/nav shells wrap the player + protected panels; harvested from the
    # extension's querySelector() detection probes, never hide-intents.
    for shell in ("ytd-app", "ytm-app", "ytd-browse", "ytm-browse",
                  "ytd-watch-flexy", "ytm-watch", "ytd-page-manager"):
        assert normalize_selector(shell) is None
    # ...but a scoped descendant of the same container is still allowed.
    assert normalize_selector('ytd-browse[page-subtype="home"] #primary') == \
        'ytd-browse[page-subtype="home"] #primary'


def test_normalize_protects_bare_search_surfaces_but_allows_scoped():
    # Search must stay usable: bare search containers are never hidden...
    for surface in ("ytd-search", "ytm-search", "ytd-searchbox",
                    "ytd-two-column-search-results-renderer"):
        assert normalize_selector(surface) is None
    # ...but rules that strip distractions *inside* search are still allowed.
    assert normalize_selector("ytd-search ytd-shelf-renderer") == "ytd-search ytd-shelf-renderer"
    assert normalize_selector("ytm-search ytm-shelf-renderer") == "ytm-search ytm-shelf-renderer"


def test_normalize_rejects_bare_and_truncated_tokens():
    assert normalize_selector("ytd-") is None
    assert normalize_selector("yt-") is None
    assert normalize_selector("ytm-") is None


def test_normalize_rejects_js_event_name_strings():
    assert normalize_selector("yt-navigate-finish") is None
    assert normalize_selector("yt-page-data-updated") is None


def test_harvest_css_blocks_strips_leading_comment():
    js = ('x.textContent = `/* Hide Shorts tab in sidebar */ '
          'ytd-guide-entry-renderer:has(a[href="/shorts"]) { display:none !important; }`;')
    blocks = harvest_css_blocks(js)
    assert len(blocks) == 1
    sel_part, _decl = blocks[0]
    assert "/*" not in sel_part and "*/" not in sel_part
    assert normalize_selector(sel_part) == 'ytd-guide-entry-renderer:has(a[href="/shorts"])'


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
