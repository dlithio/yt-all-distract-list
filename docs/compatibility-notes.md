# Cross-Engine Filter Compatibility Notes

**Research date:** 2026-06-06
**Status:** No material blocker found — single combined list remains viable.

---

## Summary of verdicts

| Claim | Verdict | Short note |
|---|---|---|
| (a) `:has()` works in both uBO and AdGuard iOS | CONFIRMED | Native since Safari 16.4 / AdGuard iOS v4.4.6 |
| (b) AdGuard iOS needs `#?#…:contains(…)` and Advanced Protection module | CONFIRMED | `##:has-text()` is a synonym but `#?#` is the explicit marker for ExtendedCss routing; Premium required |
| (c) Each engine silently drops lines it cannot parse, so one combined list is safe | CONFIRMED (with nuance) | AdGuard routes unsupported rules to Advanced Protection rather than truly dropping them; practical effect for list authors is the same |
| (d) `youtube.com##` matches `www.` and `m.` subdomains in both engines | CONFIRMED | Both engines apply domain cosmetic rules to all subdomains by default |

---

## Claim (a): `:has()` support in AdGuard iOS and uBlock Origin

**Verdict: CONFIRMED**

AdGuard for iOS v4.4.6 (October 2024) added native `:has()` CSS pseudo-class support, previously limited to paid users via the Advanced Protection module. The `:has()` pseudo-class was introduced in Safari 16.4, allowing selection of elements based on their children or content. This is now available to all AdGuard iOS users (free and paid).

uBlock Origin has supported `:has()` natively via its procedural cosmetic filter engine for several years and also benefits from native browser support where available.

**Sources:**
- https://adguard.com/en/blog/adguard-v4-4-6-for-ios.html
- https://github.com/uBlockOrigin/uBlock-issues/wiki/Procedural-cosmetic-filters

---

## Claim (b): AdGuard iOS needs `#?#…:contains(…)` and Advanced Protection

**Verdict: CONFIRMED**

The `#?#` rule marker in AdGuard syntax explicitly forces the rule to be processed by AdGuard's ExtendedCss engine rather than the native browser CSS engine. SafariConverterLib (the library that converts AdGuard filter rules to Safari content blocking rules) routes rules marked with `#?#` to "advanced blocking rules" — these are interpreted by the Safari Web Extension component called Advanced Protection, not by Safari's native content blocker.

Key details:
- Advanced Protection requires **iOS 15 or later** and an **AdGuard Premium subscription**. Free-tier AdGuard for iOS users will not receive extended CSS filtering.
- `:has-text()` is a recognised synonym for `:contains()` in AdGuard's ExtendedCss library. However, `#?#` is the documented marker that guarantees the rule is routed to ExtendedCss processing; `##` without `#?#` may be treated as a standard CSS cosmetic rule and fail if the pseudo-class is not natively supported.
- A combined list can include both `youtube.com##div:has-text(foo)` (for uBlock Origin) and `youtube.com#?#div:contains(foo)` (for AdGuard iOS) on separate lines; each engine handles what it understands and ignores the rest.

**Sources:**
- https://github.com/AdguardTeam/ExtendedCss/blob/master/README.md (`:has-text()` as synonym; `#?#` marker semantics)
- https://adguard.com/kb/adguard-for-ios/features/advanced-protection/ (iOS 15+ requirement; Premium)
- https://adguard.com/en/blog/adguard-4-3-for-ios.html (Advanced Protection introduction)
- https://github.com/AdguardTeam/SafariConverterLib (advanced rules concept)

---

## Claim (c): Each engine silently drops lines it cannot parse

**Verdict: CONFIRMED (with nuance)**

**uBlock Origin:** Silently ignores rules with unrecognised syntax (invalid URLs, unknown markers, unsupported modifiers). The `#?#` AdGuard marker is not a uBO construct; uBO will not apply those lines.

**AdGuard (SafariConverterLib / iOS):** Does not "drop" unsupported cosmetic rules — instead, rules that cannot be converted to native Safari content blocker JSON are moved to an "advanced rules" text buffer and processed by the Advanced Protection web extension. Truly unsupported rules (e.g. network modifiers with no Safari equivalent such as `$csp`, `$cookie`) are discarded.

The practical implication for a combined list is identical to "silent dropping": uBO applies uBO-syntax lines and ignores AdGuard-syntax lines; AdGuard applies AdGuard-syntax lines and routes extended CSS lines to Advanced Protection. The single-list design is safe.

**Caveat:** uBlock Origin procedural filters (`##:has-text()`) use the `##` marker that AdGuard also recognises. Because AdGuard's ExtendedCss library treats `:has-text()` as a synonym for `:contains()`, AdGuard may correctly route `##div:has-text()` rules to its ExtendedCss engine without needing `#?#`. This reduces the need for duplicate lines, but the `#?#` form remains the explicitly documented and safest approach for AdGuard iOS.

**Sources:**
- https://github.com/AdguardTeam/SafariConverterLib (ConversionResult: safariRulesJSON + advancedRulesText)
- https://github.com/gorhill/uBlock/wiki/Dashboard:-Filter-lists (uBO ignores invalid filter URLs/rules)
- https://adguard.com/kb/general/ad-filtering/create-own-filters/ (invalid rules shorter than 4 chars are ignored)

---

## Claim (d): `youtube.com##` matches `www.` and `m.` subdomains

**Verdict: CONFIRMED**

In both uBlock Origin and AdGuard, a domain-scoped cosmetic filter rule such as `youtube.com##.selector` applies to the specified domain **and all its subdomains**. AdGuard's documentation explicitly confirms: "example.com##.banner will be used on http://example.com/ and http://something.example.com/". This means `youtube.com##` rules cover `www.youtube.com`, `m.youtube.com`, and any other subdomains without additional lines.

To restrict a rule to a specific subdomain only, the filter would need to use the full subdomain (e.g. `www.youtube.com##`) or a negated wildcard.

**Sources:**
- https://adguard.com/kb/general/ad-filtering/create-own-filters/ (subdomain matching confirmation)
- https://github.com/gorhill/ublock/wiki/static-filter-syntax (uBO cosmetic filter domain matching)

---

## Overall conclusion

The single combined `.txt` list design is viable. The key authoring pattern for text-content matching is to emit **two lines per rule** in the filter list:

```
youtube.com##div:has-text(foo)        ! uBlock Origin (procedural)
youtube.com#?#div:contains(foo)       ! AdGuard iOS (Advanced Protection / ExtendedCss)
```

Each engine will apply the line it recognises and silently pass over the other. No material assumption has changed that would invalidate the design.

**One limitation to document for end-users:** AdGuard for iOS users without a **Premium subscription** will not benefit from `#?#:contains()` / Extended CSS rules, because Advanced Protection is a Premium-only feature.
