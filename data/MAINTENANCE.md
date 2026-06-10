# Maintenance Report

- Generated: 2026.06.10
- Upstream commit: f0fb3df39f77c0d2e5797cf5d649d72a4cccc9cf
- Harvested: 304 | published: 168 | in supplement: 17 | unblocked candidates: 136

## Changes since last run

_No new selectors._

_No removed selectors._

## Unblocked candidates

Selectors the extension references that your list does NOT block. Add the ones you want to `data/supplement.txt`. ⚠ marks over-broad/protected selectors — scope them before adding or they may blank a page.

### From query-anchors only (often over-broad — scope before adding)
- `#secondary #items`
- `#secondary ytd-playlist-panel-renderer`
- `#secondary-inner`
- `.button-container ytd-button-renderer`
- `.ytm-autonav-toggle-button-container button`
- `.ytp-autonav-endscreen`
- `.ytp-autonav-endscreen-countdown`
- `.ytp-autonav-endscreen-upnext-button`
- `.ytp-autonav-endscreen-upnext-container`
- `.ytp-autonav-toggle-button-container button`
- `.ytp-ce-channel`
- `.ytp-ce-covering-overlay`
- `.ytp-ce-element-show`
- `.ytp-ce-playlist`
- `.ytp-ce-shadow`
- `.ytp-ce-size-1280`
- `.ytp-ce-size-853`
- `.ytp-ce-video`
- `.ytp-ce-website`
- `.ytp-endscreen-content`
- `.ytp-endscreen-next`
- `.ytp-endscreen-previous`
- `.ytp-show-tiles`
- `.ytp-suggestion-set`
- `.ytp-time-duration`
- `.ytp-upnext`
- `.ytp-upnext-container`
- `grid-shelf-view-model`
- `more-from-yt-spacer`
- `yt-badge-view-model`
- `yt-chip-cloud-chip-renderer`
- `ytd-backstage-post-thread-renderer`
- `ytd-brand-video-singleton-renderer`
- `ytd-browse[page-subtype="home"]`
- `ytd-chips-shelf-with-video-shelf-renderer`
- `ytd-comments#comments`
- `ytd-comments-entry-point-header-renderer`
- `ytd-compact-autoplay-renderer`
- `ytd-compact-movie-renderer`
- `ytd-compact-radio-renderer`
- `ytd-compact-video-renderer`
- `ytd-compact-video-renderer[is-shorts]`
- `ytd-expanded-shelf-contents-renderer`
- `ytd-guide-entry-renderer`
- `ytd-guide-entry-renderer #endpoint[title="Home"]`
- `ytd-guide-entry-renderer #endpoint[title="Shorts"]`
- `ytd-guide-entry-renderer a[href="/"]`
- `ytd-guide-entry-renderer a[href="/home"]`
- `ytd-guide-entry-renderer a[href="/shorts"]`
- `ytd-guide-entry-renderer a[href^="/shorts"]`
- `ytd-guide-entry-renderer a[title="Home"]`
- `ytd-guide-entry-renderer a[title="Shorts"]`
- `ytd-guide-entry-renderer:has(#endpoint[href^="/@"])`
- `ytd-guide-entry-renderer:has(#endpoint[href^="/c/"])`
- `ytd-guide-entry-renderer:has(#endpoint[href^="/channel/"])`
- `ytd-guide-section-renderer`
- `ytd-guide-section-renderer:has(a#endpoint[href^="/feed/subscriptions"])`
- `ytd-horizontal-card-list-renderer`
- `ytd-item-section-renderer > #contents`
- `ytd-logo`
- `ytd-mini-guide-entry-renderer`
- `ytd-mini-guide-entry-renderer #endpoint[title="Home"]`
- `ytd-mini-guide-entry-renderer #endpoint[title="Shorts"]`
- `ytd-mini-guide-entry-renderer a[href="/"]`
- `ytd-mini-guide-entry-renderer a[href="/home"]`
- `ytd-mini-guide-entry-renderer a[href="/shorts"]`
- `ytd-mini-guide-entry-renderer a[href^="/shorts"]`
- `ytd-mini-guide-entry-renderer a[title="Home"]`
- `ytd-mini-guide-entry-renderer a[title="Shorts"]`
- `ytd-playlist-panel-renderer`
- `ytd-playlist-panel-view-model`
- `ytd-rich-grid-renderer`
- `ytd-rich-grid-row`
- `ytd-rich-item-renderer`
- `ytd-rich-item-renderer:has(ytd-backstage-post-thread-renderer)`
- `ytd-rich-item-renderer:has(ytd-post-renderer)`
- `ytd-rich-item-renderer[is-post]`
- `ytd-rich-item-renderer[is-shelf-item]`
- `ytd-rich-item-renderer[lockup]`
- `ytd-rich-section-renderer`
- `ytd-rich-section-renderer:has(ytd-rich-item-renderer[is-post])`
- `ytd-rich-shelf-renderer`
- `ytd-rich-shelf-renderer[has-expansion-button][restrict-contents-overflow]`
- `ytd-shelf-renderer`
- `ytd-thumbnail-overlay-time-status-renderer[overlay-style="SHORTS"]`
- `ytd-two-column-browse-results-renderer`
- `ytd-two-column-browse-results-renderer #primary`
- `ytd-watch-next-secondary-results-renderer`
- `ytm-backstage-post-renderer`
- `ytm-comment-thread-renderer`
- `ytm-comments-entry-point-header-renderer`
- `ytm-compact-autoplay-renderer`
- `ytm-compact-video-renderer`
- `ytm-feed`
- `ytm-horizontal-card-list-renderer`
- `ytm-item-section-renderer:has(ytm-backstage-post-renderer)`
- `ytm-item-section-renderer:has(ytm-post-renderer)`
- `ytm-item-section-renderer[section-identifier="related-items"]`
- `ytm-pivot-bar-item-renderer`
- `ytm-pivot-bar-item-renderer a[href="/shorts"]`
- `ytm-pivot-bar-renderer a[title="Shorts"]`
- `ytm-playlist-panel-renderer`
- `ytm-post-renderer`
- `ytm-reel-item-renderer`
- `ytm-rich-grid-renderer`
- `ytm-rich-item-renderer`
- `ytm-rich-item-renderer:has(ytm-post-renderer)`
- `ytm-rich-shelf-renderer`
- `ytm-shelf-renderer`
- `ytm-structured-description-content-renderer`

### ⚠ Guarded — do NOT add without scoping (the lint gate will reject the bare form)
- `#related ytd-continuation-item-renderer:not(:has(ytd-engagement-panel-section-list-renderer)):not(:has(ytd-transcript-segment-list-renderer))`  ⚠ protected element — do not hide
- `#related ytd-item-section-renderer:not(:has(ytd-engagement-panel-section-list-renderer)):not(:has(ytd-transcript-segment-list-renderer))`  ⚠ protected element — do not hide
- `#secondary #related:not(:has(ytd-engagement-panel-section-list-renderer)):not(:has(ytd-transcript-segment-list-renderer))`  ⚠ protected element — do not hide
- `#secondary ytd-continuation-item-renderer:not(:has(ytd-engagement-panel-section-list-renderer)):not(:has(ytd-transcript-segment-list-renderer))`  ⚠ protected element — do not hide
- `#secondary ytd-item-section-renderer:not(:has(ytd-engagement-panel-section-list-renderer)):not(:has(ytd-transcript-segment-list-renderer))`  ⚠ protected element — do not hide
- `#secondary ytd-watch-next-secondary-results-renderer:not(:has(ytd-engagement-panel-section-list-renderer)):not(:has(ytd-transcript-segment-list-renderer))`  ⚠ protected element — do not hide
- `yt-lockup-view-model`  ⚠ shared content renderer — would blank search
- `ytd-app`  ⚠ over-broad page shell — scope before adding
- `ytd-channel-renderer`  ⚠ shared content renderer — would blank search
- `ytd-continuation-item-renderer`  ⚠ shared content renderer — would blank search
- `ytd-engagement-panel-section-list-renderer`  ⚠ protected element — do not hide
- `ytd-grid-video-renderer`  ⚠ shared content renderer — would blank search
- `ytd-item-section-renderer`  ⚠ shared content renderer — would blank search
- `ytd-playlist-renderer`  ⚠ shared content renderer — would blank search
- `ytd-playlist-video-renderer`  ⚠ shared content renderer — would blank search
- `ytd-transcript-segment-list-renderer`  ⚠ protected element — do not hide
- `ytd-video-renderer`  ⚠ shared content renderer — would blank search
- `ytd-watch-next-secondary-results-renderer ytd-continuation-item-renderer:not(:has(ytd-engagement-panel-section-list-renderer)):not(:has(ytd-transcript-segment-list-renderer))`  ⚠ protected element — do not hide
- `ytd-watch-next-secondary-results-renderer ytd-item-section-renderer:not(:has(ytd-engagement-panel-section-list-renderer)):not(:has(ytd-transcript-segment-list-renderer))`  ⚠ protected element — do not hide
- `ytm-app`  ⚠ over-broad page shell — scope before adding
- `ytm-browse`  ⚠ over-broad page shell — scope before adding
- `ytm-engagement-panel-section-list-renderer`  ⚠ protected element — do not hide
- `ytm-grid-video-renderer`  ⚠ shared content renderer — would blank search
- `ytm-item-section-renderer`  ⚠ shared content renderer — would blank search
- `ytm-video-with-context-renderer`  ⚠ shared content renderer — would blank search
- `ytm-watch`  ⚠ over-broad page shell — scope before adding

