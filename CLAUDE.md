# CLAUDE.md

Read **AGENTS.md** first — it is the working brief for this repo: layout, build,
run-and-test, the anti-cheat/evidence contract, Pi operations, and the pitfalls
that each cost a real debugging session. CONTRIBUTING.md covers git identity,
line endings and `.src` ordering. Everything below is style only.

## Comments and notes: concise

A comment earns its space by carrying something the code does not show —
a measured number, a file:line, a gotcha, or a decision that was made against an
obvious alternative. Say it once.

It does NOT earn space by:

- restating what the line does;
- meta-commentary — "said out loud because…", "this paragraph exists because…",
  "which is not laziness", "worth one sentence";
- repeating an argument at three call sites. State it where it belongs and point
  at it from the others ("see the grammar block").

Prefer `//` over a `/* */` block when it fits in three lines. Long-form reasoning
belongs in `ENGINE_PATCHES.md` (engine repo), not in source files.

**The existing essays are legacy, not the target.** `cl_hud.qc`, `cl_board.qc`
and `sv_timer.qc` are wall-to-wall multi-paragraph comment blocks from earlier
builds. They are kept (they are paid for, and rewriting them churns diffs for
nothing) but they are NOT the house style to imitate — reading them and matching
their length is how this file came to be needed. New comments are a few lines.

**The one exception is a format contract** — the `.rec` grammar block over
`SV_RecOpen` in `src/server/sv_timer.qc`. That is reference material four
independent readers are written from, so it stays complete. Keep it dense, not
chatty.

## Working style here

- Build and verify before saying something is done: `./build.ps1` to 0 warnings,
  then the relevant falsifier (`tools/test_reccheck.py`, a `cfg/test/` arm, or a
  headless run whose log you actually read).
- Then commit that feature and push it — see the source-control rule in
  AGENTS.md. Verified work that is still only on this disk is not finished.
- Prefer measuring to reasoning. This codebase has a long history of the right
  answer and the wrong answer being the same bytes; when a claim can be checked
  against a real file or a live run, check it.
- Report what the measurement said, including when it contradicts what you
  predicted. A falsified prediction is a result, not a setback.
- Changes to the recorder, the verifier or anything that writes evidence get an
  independent review (reviewers who see the code, not your conclusion) before
  deploy. Patch 375 passed every harness arm and still had five real defects,
  two of which corrupted recordings.
