from lockedin_filters.report import (
    harvest_candidates, annotate, diff_candidates, published_selectors,
    render_json, render_markdown,
)


def _write(tmp_path):
    d = tmp_path / "up"
    (d / "content").mkdir(parents=True)
    (d / "content" / "index.js").write_text(
        'x.textContent = `ytd-reel-shelf-renderer { display:none !important; }`;\n'  # css hide
        "document.querySelector('ytd-video-renderer');\n"                            # string anchor (over-broad)
        "const s = 'ytd-search ytd-shelf-renderer';\n"                               # string anchor (scoped, safe)
    )
    return d


def test_harvest_candidates_tags_source_scoped_and_guard(tmp_path):
    cands = {c["selector"]: c for c in harvest_candidates(_write(tmp_path))}
    assert cands["ytd-reel-shelf-renderer"]["sources"] == ["css"]
    assert cands["ytd-reel-shelf-renderer"]["guard"] is None
    assert cands["ytd-video-renderer"]["sources"] == ["string"]
    assert cands["ytd-video-renderer"]["guard"] == "content_renderer"
    assert cands["ytd-video-renderer"]["scoped"] is False
    assert cands["ytd-search ytd-shelf-renderer"]["scoped"] is True


def test_annotate_sets_published_and_in_supplement():
    cands = [{"selector": "ytd-comments", "sources": ["string"], "scoped": False, "guard": None},
             {"selector": "ytd-x", "sources": ["string"], "scoped": False, "guard": None}]
    out = {c["selector"]: c for c in annotate(cands, published={"ytd-comments"}, supplement={"ytd-comments"})}
    assert out["ytd-comments"]["published"] is True
    assert out["ytd-comments"]["in_supplement"] is True
    assert out["ytd-x"]["published"] is False
    assert out["ytd-x"]["in_supplement"] is False


def test_diff_candidates_reports_added_and_removed():
    d = diff_candidates(current={"a", "b"}, previous={"b", "c"})
    assert d == {"added": ["a"], "removed": ["c"]}


def test_published_selectors_reads_dist(tmp_path):
    dist = tmp_path / "d.txt"
    dist.write_text("! header\nyoutube.com##ytd-comments\nyoutube.com#?#ytd-x:contains(Hi)\n")
    pub = published_selectors(dist)
    assert "ytd-comments" in pub
    assert "ytd-x:has-text(Hi)" in pub   # canonicalized from the #?# twin


def test_harvest_candidates_marks_selector_from_both_sources(tmp_path):
    d = tmp_path / "up"
    (d / "content").mkdir(parents=True)
    (d / "content" / "index.js").write_text(
        'a.textContent = `ytd-comments { display:none !important; }`;\n'  # css hide-block
        "document.querySelector('ytd-comments');\n"                       # same selector as a string anchor
    )
    cands = {c["selector"]: c for c in harvest_candidates(d)}
    assert cands["ytd-comments"]["sources"] == ["css", "string"]


def _annotated():
    return [
        {"selector": "ytd-reel-shelf-renderer", "sources": ["css"], "scoped": False,
         "guard": None, "published": True, "in_supplement": False},
        {"selector": "ytd-video-renderer", "sources": ["string"], "scoped": False,
         "guard": "content_renderer", "published": False, "in_supplement": False},
        {"selector": "ytd-cool-new-renderer", "sources": ["css"], "scoped": False,
         "guard": None, "published": False, "in_supplement": False},
    ]


def test_render_json_is_valid_sorted_array():
    import json
    data = json.loads(render_json(_annotated()))
    assert isinstance(data, list) and len(data) == 3
    assert data[0]["selector"] == "ytd-reel-shelf-renderer"


def test_render_markdown_has_counts_changes_and_warnings():
    md = render_markdown(_annotated(), {"added": ["ytd-cool-new-renderer"], "removed": []},
                         build_date="2026.06.06", upstream_sha="abc123")
    assert "abc123" in md and "2026.06.06" in md
    assert "ytd-cool-new-renderer" in md            # appears in "changes since last run"
    assert "ytd-video-renderer" in md               # unblocked candidate listed
    assert "⚠" in md                                 # warning marker for the guarded candidate
    assert "ytd-reel-shelf-renderer" not in md.split("## Unblocked")[1]  # published -> not in unblocked list
