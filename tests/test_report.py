from lockedin_filters.report import (
    harvest_candidates, annotate, diff_candidates, published_selectors,
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
