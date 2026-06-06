# LockedIn YouTube — Maximalist Distraction Filter

A self-updating cosmetic filter list that strips YouTube down to a focus-only surface
(home feed, Shorts, recommendations, thumbnails, comments, end screens, engagement
metrics, and navigation clutter). It is regenerated daily from the
[LockedIn-YT](https://github.com/KartikHalkunde/LockedIn-YT) extension source.

## Subscribe URL

```
https://raw.githubusercontent.com/dlithio/yt-all-distract-list/main/dist/lockedin-youtube.txt
```

The list declares `! Expires: 1 day`, so both engines auto-refresh daily.

## uBlock Origin (desktop)

1. Open the uBO dashboard → **Filter lists**.
2. Scroll to **Import** (bottom), tick it, and paste the subscribe URL.
3. Click **Apply changes**.

## AdGuard for iOS

1. Open AdGuard → **Filters** → **Custom** → **Add custom filter**.
2. Paste the subscribe URL and add it.
3. Enable **Advanced Protection** if you have an **AdGuard Premium subscription (iOS 15+
   required)**. Advanced Protection is only needed for the handful of `#?#` text-matching
   rules in this list — free-tier users can skip this step.
4. Ensure AdGuard's Safari extensions are enabled: iOS **Settings → Safari → Extensions**.
   Requires roughly iOS 16.4+ (for `:has()` support).

### Free vs Premium

**Free AdGuard iOS users still get nearly all of this list.** Every `##` element-hiding
rule — including those using `:has()` (free since AdGuard iOS v4.4.6 / Safari 16.4) —
works without a subscription. Only the small number of `#?#:contains()` text-content
rules require Premium (Advanced Protection module, iOS 15+). If you are on the free
tier, the vast majority of the filtering still applies.

## Limitations

A cosmetic filter list cannot change behavior, only hide elements. It does **not**:

- redirect URLs (`/shorts/...` → `/watch`, Home → Subscriptions);
- truly disable autoplay — it hides Shorts entry points and any autoplay/next-up UI it
  can, but a queued next video may still play.

These behaviors are not available in this setup.

## Attribution

Selectors are derived from [KartikHalkunde/LockedIn-YT](https://github.com/KartikHalkunde/LockedIn-YT)
(MIT, © Kartik Halkunde). This project is MIT licensed.
