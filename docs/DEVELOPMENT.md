# Development

## Setup

```bash
uv sync                 # create the venv, install dev deps (pytest, ruff)
uv run pytest -q        # run tests
uv run ruff check .     # lint the Python
```

## Mental model

- `data/supplement.txt` is the **authoritative floor** — a hand-curated list of rules
  written in uBlock Origin desktop style. The published list always contains every rule
  in it (`lint.py` enforces `published ⊇ supplement`).
- `lockedin_filters/extract.py` harvests hide-selectors from a clone of the LockedIn-YT
  extension and **adds** them on top. Extraction is strictly additive.
- `lockedin_filters/build.py` merges the two, auto-generates AdGuard twins for text
  rules, sorts/de-dupes, stamps the version, and writes `dist/lockedin-youtube.txt`.
- `lockedin_filters/lint.py` is the publish gate.

## Regenerate locally

```bash
git clone --depth 1 https://github.com/KartikHalkunde/LockedIn-YT.git upstream
BUILD_DATE=$(date -u +%Y.%m.%d) uv run python -m lockedin_filters.build --upstream upstream
uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt
```

## Adding a rule by hand

Add it to `data/supplement.txt` in uBO style (`youtube.com##selector`, or
`youtube.com##selector:has-text(Text)` for text matching — do **not** hand-write the
`#?#` twin; `build.py` generates it). Then rebuild and lint.

## CI

- `validate.yml` (push/PR): runs the linter and pytest.
- `sync.yml` (daily cron + manual dispatch): clones upstream, rebuilds, runs the lint
  gate, and commits to `main` **only if the gate passes and the rule set changed**. A
  gate failure aborts the job and publishes nothing; the previous list keeps serving.

Trigger a manual run from the Actions tab → **sync** → **Run workflow**.

## "YouTube broke something" runbook

1. Identify the new element/selector on the page.
2. Add a rule to `data/supplement.txt`.
3. `uv run python -m lockedin_filters.lint dist/lockedin-youtube.txt` (after a rebuild).
4. Commit & push — `validate.yml` gates it; the next sync republishes.

## Why we compile text rules (uBO `:has-text` → AdGuard `:contains`)

`build.py` emits an explicit AdGuard `#?#...:contains(...)` twin (with quotes stripped)
for every uBO `##...:has-text(...)` rule. The rationale, from an external engineering
review:

> Your agent is being a **very sharp engineer** here. While their explanation of *why*
> it happens is slightly off on a minor technical detail, their solution (`build.py`
> auto-emitting the AdGuard twins) is **absolutely necessary and highly recommended**
> for a seamless cross-platform setup.
>
> ### 1. Where the Agent is Slightly Wrong (The Nuance)
> The agent claims that `:has-text()` is a "uBO-only text rule." That is not strictly
> true. AdGuard's core engine actually recognizes `:has-text()` as an official, native
> alias for its own `:contains()` selector for compatibility reasons. If you were running
> AdGuard on a desktop browser, it would parse `:has-text()` just fine.
>
> ### 2. Where the Agent is 100% Right (The iOS Catch)
> The real issue isn't the keyword `:has-text()`; it's the **iOS Safari architecture**.
> Because Apple forces ad blockers to use native Safari Content Blocking APIs, AdGuard
> iOS has to run all incoming rules through an open-source compiler it built called
> **`SafariConverterLib`**.
> - When `SafariConverterLib` looks at your list, it sees the standard uBlock element
>   hiding prefix (`##`).
> - It tries to compile those rules into a native iOS Safari JSON array.
> - Because Safari's native engine is completely blind to advanced text-matching logic,
>   the compiler gets confused by the combination of `##` and `:has-text()`.
>
> Unless a rule explicitly uses AdGuard's procedural selector prefix (**`#?#`**), the iOS
> app will frequently misclassify the rule, fail to hand it off to the Advanced
> Protection JavaScript engine, and **silently drop it**.
>
> ### 3. The Hidden "Quotation Mark" Trap
> There is another massive headache this script avoids. In uBlock Origin, both of these
> are valid:
> - `youtube.com##span:has-text(Shorts)`
> - `youtube.com##span:has-text("Shorts")` *(with quotes)*
>
> However, AdGuard's parser completely chokes if there are quotation marks inside a
> text-matching selector. If you or an upstream list you pull from ever accidentally
> includes quotes, AdGuard iOS will break. By forcing `build.py` to strip the rule down
> and cleanly re-emit it as an explicit AdGuard procedural rule
> (`youtube.com#?#span:contains(Shorts)`), your script completely bypasses the fragile
> iOS compiler wrapper.
>
> ### The Verdict
> **Yes, let the agent build this feature.** It elegantly solves the "Write Once, Run
> Everywhere" problem. Your source file (`supplement.txt`) stays clean, human-readable,
> and formatted in the standard desktop style you are used to. Meanwhile, the script
> ensures that the actual published file contains the bulletproof syntax required to
> force AdGuard iOS's JavaScript engine into action.
