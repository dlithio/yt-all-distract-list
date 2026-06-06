from lockedin_filters.extract import normalize_selector


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
