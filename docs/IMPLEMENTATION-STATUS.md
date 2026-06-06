# Implementation Status — LockedIn YouTube Filter List

**Resume guide for a fresh Claude Code session.** Last updated mid-execution (Tasks 1–7 of 15 done).

## TL;DR
- We are executing the plan `docs/superpowers/plans/2026-06-06-lockedin-youtube-filter.md` using **subagent-driven development** (one implementer subagent + one reviewer subagent per task, sonnet model).
- All implementation happens on branch **`implement-filter-list`** in a **git worktree**.
- **Tasks 1–7 are committed. NEXT = Task 8 (`build.py`).**
- One verification is owed before/at Task 8 — see "OPEN verification owed" below.

## Where everything lives
- **Main checkout:** `/Users/danlithio/Github/yt-all-distract-list` (branch `main`). Has the spec + plan committed. ALSO has **untracked** pre-existing files: `pyproject.toml`, `main.py`, `README.md`, `CLAUDE.md`, `previous-plan.md`, `.python-version`, `.claude/`. These predate this work (they were never committed).
- **Worktree (do work here):** `/Users/danlithio/.config/superpowers/worktrees/yt-all-distract-list/implement-filter-list` — branch `implement-filter-list`, based on `main@f83ab0c`.
  - `~/.config/superpowers` was added to the session's allowed dirs (`claude --add-dir ~/.config/superpowers`) so tools can read/write the worktree. If a new session can't access it, re-add it (or relocate the worktree inside the repo — see "Alternative" below).
- **Spec:** `docs/superpowers/specs/2026-06-06-lockedin-youtube-filter-design.md` (in both main and worktree).
- **Plan:** `docs/superpowers/plans/2026-06-06-lockedin-youtube-filter.md` (in both). The plan contains the full verbatim code for every task — relay it to implementers.

## Commits on `implement-filter-list` (oldest → newest)
- `b29c4cf` Task 1 scaffold (`pyproject.toml`, `.gitignore`, `uv.lock`, `lockedin_filters/__init__.py`)
- `e55a597` Task 2 `docs/compatibility-notes.md`
- `c718e2a` Task 3 `lockedin_filters/textrules.py` + `tests/test_textrules.py`
- `928caeb` Task 4 `extract.py` constants + `normalize_selector` + tests
- `077b71c` Task 5 `extract.py` harvest functions + tests
- `2d25b20` Task 6 `extract.py` `extract_selectors` + tests
- `de54f6b` Task 7 `data/supplement.txt` + `tests/test_supplement.py`

## Task status
| Task | Status |
|------|--------|
| 1 Scaffold | DONE + reviewed (SPEC PASS / QUALITY APPROVED) |
| 2 Compat verification | DONE (single-list design confirmed; see caveat below) |
| 3 textrules.py | DONE + reviewed (PASS / APPROVED) |
| 4 extract normalize | DONE |
| 5 extract harvest | DONE (committed `077b71c`; a harness pause happened *after* the commit — work is sound) |
| 6 extract orchestration | DONE — full `extract.py` reviewed (SPEC PASS / QUALITY APPROVED) |
| 7 supplement seed | DONE — its test currently ERRORS with `ModuleNotFoundError: lockedin_filters.build` — **this is EXPECTED**; it goes green after Task 8 |
| 8 build.py | **NEXT — not started** |
| 9 lint.py | not started |
| 10 generate + commit dist | not started (clones upstream `KartikHalkunde/LockedIn-YT`) |
| 11 validate.yml | not started |
| 12 sync.yml | not started |
| 13 README.md | not started |
| 14 DEVELOPMENT.md | not started |
| 15 LICENSE + final verify | not started |
| final review + finish | not started |

## Current test state
From the worktree: `uv run --directory . pytest -q` (or `cd` in and `uv run pytest -q`):
- `test_textrules.py` 3 pass, `test_extract.py` 12 pass.
- `test_supplement.py` ERRORS (imports `lockedin_filters.build`, created in Task 8). Expected. All green after Task 8.

## OPEN verification owed (DO THIS FIRST when resuming)
The Task 7 implementer reported "63 curated rules," but the plan's Task 7 supplement has **~46** rule lines. Verify `data/supplement.txt` matches the plan's Task 7 block **exactly** (no rules added/dropped/edited) — it is the authoritative floor that the lint floor-invariant depends on. Check:
```
grep -c '^youtube\.com' data/supplement.txt     # expect ~46
grep '^youtube\.com' data/supplement.txt          # diff this set against the plan's Task 7 list
```
If it deviates, correct it to match the plan exactly, then re-commit.

## How to resume (subagent-driven development)
For each remaining task (8→15): dispatch ONE implementer subagent, then ONE reviewer subagent, fix-loop until clean, then continue. Do not pause between tasks. Then a final overall review, then `superpowers:finishing-a-development-branch`.

**Reusable implementer context block** (put before the verbatim task text from the plan):
> You are implementing one task of a larger plan. Zero prior context.
> PROJECT: "LockedIn YouTube" — self-updating maximalist YouTube-distraction filter list for uBlock Origin (desktop) + AdGuard iOS. A stdlib-only Python package `lockedin_filters/` extracts hide-selectors from the LockedIn-YT extension, merges them with the curated `data/supplement.txt`, dual-emits text rules for both engines, and writes `dist/lockedin-youtube.txt`; a daily GitHub Action clones upstream, rebuilds, lint-gates, commits to main.
> WORKSPACE: do ALL work in the worktree `/Users/danlithio/.config/superpowers/worktrees/yt-all-distract-list/implement-filter-list` (cd there first). Use `uv` for EVERYTHING (`uv run pytest`, never bare python/pytest). Append to commit messages: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
> JOB: follow the TDD steps in order (failing test → see it fail → implement with the EXACT code → see it pass → commit). Paste real output. Self-review vs spec. Ask before guessing.
> REPORT: end with DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED + actual output + commit SHA + deviations.

**Reviewer subagent:** read-only; STAGE 1 spec-compliance (gate) then STAGE 2 code-quality; report SPEC PASS/FAIL + QUALITY APPROVED/CHANGES.

## Decisions & gotchas (carry forward)
- **Declined** reviewer suggestion to broaden extract.py protection to all `.html5-*`: it would wrongly stop extracting `.html5-endscreen` (a desired hide). Keep the explicit player list (`#movie_player`, `.html5-video-player`, `.html5-main-video`, `video.video-stream`).
- Task 1 was adapted: `pyproject.toml` CREATE (not replace); no `main.py` to delete (absent in worktree).
- **Task 13 (README) MUST add a caveat the plan text omits:** AdGuard iOS "Advanced Protection" (required for the `#?#:contains` text rules) needs **AdGuard Premium + iOS 15+**. Only the handful of text-matching rules are affected; the rest works for free users. Source: Task 2 → `docs/compatibility-notes.md`.
- Task 8/9 function contract (keep signatures identical to the plan): `build.py` exports `selector_of`, `canonical_selector`, `emit_rule`, `collect_rules`, `render`, `finalize`, `load_supplement_selectors`, `build`, `main`; `lint.py` imports `selector_of`, `canonical_selector`, `load_supplement_selectors` from build and uses `textrules`. `lint` has `references_ask` for the protected "Ask" button, `MAX_RULES` ceiling, supplement-floor check.
- Task 10 clones `https://github.com/KartikHalkunde/LockedIn-YT.git` into `upstream/` (gitignored), runs build + lint. It may surface an over-broad/malformed extracted selector that trips the lint gate — the plan anticipates tightening `YT_TOKENS`/`PROTECTED` and rebuilding. The user's lean is AGGRESSIVE/over-block with rollback tolerance.

## Finishing (after Task 15 + final review)
Use `superpowers:finishing-a-development-branch`. **Merge gotcha:** the main checkout has UNTRACKED `pyproject.toml`/`main.py`/`README.md` that will block checking out the branch's committed versions ("untracked working tree files would be overwritten"). Before merging: remove the obsolete untracked scaffold in main (`main.py`, the old empty `README.md`, the old `pyproject.toml`) but **preserve `CLAUDE.md`** (user's project instructions — consider committing it). Reconcile deliberately.

## Alternative if the external worktree becomes inaccessible
The branch + all commits live in the shared `.git` of the main repo. If `~/.config/superpowers` access can't be restored, relocate the worktree inside the repo:
```
git -C /Users/danlithio/Github/yt-all-distract-list worktree remove --force ~/.config/superpowers/worktrees/yt-all-distract-list/implement-filter-list
git -C /Users/danlithio/Github/yt-all-distract-list worktree add .worktrees/implement-filter-list implement-filter-list
```
(Then work in `/Users/danlithio/Github/yt-all-distract-list/.worktrees/implement-filter-list`. Add `.worktrees/` to ignore handling so it isn't committed.)
