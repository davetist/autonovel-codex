# Agent Instructions for Autonovel

This repository is an autonomous novel-generation pipeline. Agents working here should preserve the pipeline's core loop:

```text
modify -> evaluate -> keep/discard -> repeat
```

The goal is not merely to generate text. The goal is to evolve a coherent book through explicit state, tests, evaluation, and reversible commits.

## Golden rules

- Treat `main` as the reusable pipeline branch: code, tests, docs, templates, and generic prompt scaffolding only.
- Treat `book/<slug>` branches as per-book workspaces: seed, foundation files, chapters, generated state, logs, and manuscript artifacts.
- Do not merge a whole book branch into `main` unless explicitly asked. Cherry-pick or recreate only reusable pipeline changes.
- Prefer automated policy and deterministic signals over manual vibes. If a decision can be encoded, encode it with tests.
- Preserve strong work. Do not blindly rerun broad generation when the existing book is good and the problem is localized.
- Keep story revision separate from presentation hygiene. Formatting passes must not rewrite body prose.
- Never commit `.env`, virtual environments, caches, raw credentials, or private API keys.

## Canonical artifact map

Core per-book files:

```text
seed.txt                 premise / story DNA
world.md                 what exists
characters.md            who acts
outline.md               what happens
voice.md                 how the book sounds
canon.md                 hard facts that must remain true
book_profile.md          generated prompt profile for the current book
MYSTERY.md               optional author-only central secret
chapters/ch_*.md         chapter prose
state.json               pipeline progress and propagation debts
results.tsv              evaluation / keep-discard log
edit_logs/reader_panel.json reader-panel signal for revision
briefs/*.md              revision briefs
```

Reusable framework files belong on `main`, including scripts, tests, prompt scaffolding, `README.md`, `PIPELINE.md`, `WORKFLOW.md`, `CRAFT.md`, `ANTI-SLOP.md`, `ANTI-PATTERNS.md`, and this file.

## Pipeline phases

### 1. Foundation

Build the world, characters, outline, voice, and canon from `seed.txt`.

The useful foundation loop is hybrid:

1. If a candidate is structurally weak, regenerate a fresh candidate.
2. If a candidate is close but flawed, repair it surgically from the foundation eval JSON.
3. If it passes threshold, stop iterating and move forward.
4. Reroll a full foundation only when the eval says the premise interpretation, protagonist choice, or world architecture is wrong.

Do not treat foundation retries as pure random rerolls once a good shape exists.

### 2. Drafting

Draft chapters sequentially. Evaluate each chapter. Keep passing chapters and update canon from accepted chapter evals.

If a chapter fails, use the failed eval as repair fuel before gambling on a fresh redraft:

```text
draft_chapter.py N -> evaluate.py --chapter=N
if score passes: append useful eval canon entries -> keep
if score fails: gen_brief.py --eval N -> gen_revision.py N <eval-brief> -> re-evaluate
if eval-guided repair cannot run: fall back to a fresh draft attempt
```

Forward progress matters, but failed attempts should inform the next attempt rather than vanishing.

### 3. Revision

Revision should be feedback-guided, not guesswork.

Default broad loop:

```text
adversarial_edit.py all
-> apply_cuts.py all
-> reader_panel.py
-> panel_triage.py ranking
-> gen_brief.py --combined CH
-> gen_revision.py CH <combined-brief>
-> evaluate pre/post
-> keep/revert
```

Use `panel_triage.py` to parse `reader_panel.json`. Do not manually skim panel prose and guess priorities if the deterministic ranker can do it.

Use `editorial_policy.py` to decide scope:

- weak or signal-poor novel -> broad revision
- strong novel with concentrated panel heat -> surgical revision
- strong novel with no material panel heat -> export
- missing reader panel when revision signal is needed -> broad revision to generate signal

Surgical revision should use combined briefs, not panel-only briefs. Combined briefs keep local panel pain anchored to chapter evals, full-novel evals, adversarial cut data, and voice rules.

Chapter eval is only the first gate for surgical edits. After panel-driven surgery, rerun full eval and, when appropriate, rerun the reader panel. Accept the change only if the targeted heat improves or holds while the full-book score holds or improves. If chapter score rises but panel heat worsens, treat the revision as suspicious.

### 4. Export

Export is for final presentation and packaging after story revision is done.

Before typesetting, run chapter-title normalization as layout hygiene, not prose revision:

```bash
uv run python normalize_chapter_titles.py          # dry-run inventory
uv run python normalize_chapter_titles.py --check  # guard
uv run python normalize_chapter_titles.py --write  # final cleanup when ready
```

The normalizer should derive chapter numbers from filenames and titles from `outline.md` when available. If a chapter starts with body prose, a heading may be prepended, but the original prose line must remain in the body.

Inspect generated `typeset/chapters_content.tex` for sane chapter headings before trusting final output.

## Current-book prompt profile and contamination control

Reusable prompt scaffolding must not contain story-specific DNA from any previous book.

After foundation is accepted or repaired, generate a current-book profile:

```bash
uv run python gen_book_profile.py
```

`book_profile.md` should be derived only from the current book's foundation:

```text
seed.txt
world.md
characters.md
outline.md
voice.md
canon.md
```

Runtime generators should load the current `book_profile.md` plus current foundation docs. They should not hardcode old titles, protagonist names, sensory systems, disabilities, family structures, metaphor wells, chapter-ending patterns, or genre assumptions.

If contamination is discovered after drafting starts:

1. Stop generation.
2. Preserve the current state with a tag or external snapshot before destructive cleanup.
3. Add regression tests that fail on source-book tokens in reusable prompt/runtime files.
4. Scan both code and generated prose.
5. If committed chapters are heavily contaminated, prefer resetting to a clean pre-drafting commit over patching line-by-line.
6. Move reusable contamination fixes to `main`, then merge `main` back into the book branch.
7. Keep the branch shape simple: `main` plus the active `book/<slug>` branch, unless another branch is explicitly needed.

## Verification

After code, pipeline, prompt-scaffolding, or policy changes, run:

```bash
uv run python -m unittest discover -v
uv run python -m py_compile *.py typeset/*.py
git diff --check
```

If the change touches export or title normalization, also run:

```bash
uv run python normalize_chapter_titles.py --check
```

For docs-only changes, `git diff --check` is the minimum, but prefer the full verification suite before merging into `main` when practical.

## Git hygiene

Use small, truthful commits.

Suggested commit prefixes:

```text
book:       seed or manuscript-specific intent
foundation: foundation docs or repair
profile:    book profile regeneration
canon:      canon synchronization
draft:      chapter drafting progress
revision:   revision logic or manuscript fixes
export:     export and formatting hygiene
docs:       documentation only
test:       tests only
fix:        bug fix
```

When moving reusable work from a book branch to `main`:

1. Inspect the diff and commit graph.
2. Commit the reusable change on the book branch if it was developed there.
3. Switch to `main`, pull, and cherry-pick only the reusable commit(s).
4. Validate on `main`.
5. Push `main`.
6. Return to the book branch and merge `main` back in.
7. Validate again.
8. Confirm `main..book/<slug>` contains only manuscript/state artifacts, not divergent reusable code.

## Common commands

Run the full pipeline:

```bash
uv run python run_pipeline.py --from-scratch
```

Run by phase:

```bash
uv run python run_pipeline.py --phase foundation
uv run python run_pipeline.py --phase drafting
uv run python run_pipeline.py --phase revision --max-cycles 5
uv run python run_pipeline.py --phase export
```

Useful manual tools:

```bash
uv run python seed.py --riff "<idea>"
uv run python evaluate.py --phase=foundation
uv run python evaluate.py --chapter=5
uv run python evaluate.py --full
uv run python adversarial_edit.py all
uv run python apply_cuts.py all --types OVER-EXPLAIN REDUNDANT
uv run python reader_panel.py
uv run python gen_brief.py --auto
uv run python gen_brief.py --combined 5
uv run python gen_revision.py 5 briefs/ch05_combined.md
```

## Operating taste

The pipeline should reduce supervision, not create new babysitting rituals. When a repeated editorial choice appears, prefer a tested policy module over a note that future humans or agents must remember.

Preserve the book's intent, not just its files. Keep the "why" of major choices in durable project docs or commit messages when it affects future decisions.
