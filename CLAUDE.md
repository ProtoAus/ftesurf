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

- A FILTER THAT DECIDES WHICH OF YOUR FAILURES TO SHOW YOU is part of the test.
  Patch 453 shipped at three warnings instead of one because the build output
  was grepped for `warning:`, and fteqcc spells some of them `warning Q302:`,
  with no colon. Count every line matching the word, case-insensitively, rather
  than a format you assumed. `build.ps1` itself is fine — it uses a bare
  substring — so this was a hand-rolled check going wrong beside a correct one.
  THE SAME DAY, THE SAME SHAPE, IN THE OTHER DIRECTION: a `%.0f` dprint reading
  "260 u/s ... cap 260" was quoted as "it passes on an exact boundary equality",
  which the line cannot say — it bounds the value to [259.5, 260.0] and nothing
  more, and the argument built on top of it was about a margin of thousandths.
  A printed number's PRECISION bounds the claim you may make from it; read the
  format specifier before you quote the value.
- A FAILED SEARCH IS NOT A PROOF, AND SAYING SO OUT LOUD IS NOT ENOUGH. Patch
  455's gate added a carrier to its horizontal test and left the vertical one
  reading bare `.velocity_z`. I went looking for the jump-pad case that gap
  implies, did not manage to build one, found a comment that appeared to explain
  why, and reported it as covered — in the same message that said I had gone
  looking and failed. The author then wrote four sentences of comment crediting
  the reasoning, and the hole was real: the comment I quoted was about
  `run_basevelocity`, the engine's read-and-clear window, and the gate reads
  `run_basevel`, the mod's latched carrier, which deliberately does NOT drain its
  Z. Two fields, similar names, adjacent in the same declaration block, opposite
  lifetimes. "I could not build it" and "it cannot be built" are different
  findings and only one of them licenses a comment; when the difference matters,
  trace the FIELD rather than the nearest essay that mentions it.
  AND THE SEARCH ITSELF CAN BE THE THING THAT LIED. `git log -S` takes a LITERAL
  string, not a regex, so `-S 'sc = floor(sc \* 16)'` searches for a backslash and
  finds nothing. That empty output was read as "this line is in no commit" while
  the line was plainly in the working file, and the contradiction went unexamined
  for a whole message -- a peer had to point out that the commit it was really in
  was theirs. `-G` is the regex form. When a search comes back empty on something
  you can SEE, suspect the search before the conclusion.
- IDENTICAL SCREENSHOTS CAN BE THE HARNESS STALLING, NOT THE SUBJECT FREEZING.
  Patch 467's first station tour gave four frames of the same cube, and "the sim
  is frozen" was one step from a rewrite of the render path. The log's own
  timestamps said otherwise: each PNG write blocked the main thread ~2 s, so the
  camera had not moved when the shots were taken. Two shots of ONE station 6 s
  apart, diffed (61% of the lattice changed), plus the sim's own tick counter
  printed beside them, settled it in one run. Suspect the measuring before the
  measured, and make the subject print its clock.
- AN A/B THAT MOVES THE CAMERA MEASURES THE CAMERA. The sky's cost was first read
  as 136.8 against 168.1 fps -- an "on" shot at pitch -25 beside an "off" shot at
  pitch -60. The matched pair was 150.6 against 168.1. When the cost scales with
  what is on screen, the view is part of the control.
- WHEN A NUMBER THAT WAS RIGHT GOES WRONG, DIFF BEFORE YOU THEORISE. The milk
  harness printed `audio live 0` in every world for an hour; the explanations
  tried were the window's focus (`s_inactive 1` was added and changed nothing)
  and the new tracks. The cause
  was in the diff: removing a two-line debug print by line count had taken the
  `Milk_Audio();` under it too, so nothing had fed the visuals since. A delete by
  count is an edit you have not read -- read it.
- SKIPPING WORK IS NOT REMOVING IT. On this Intel GPU the monolith ran 40 fps
  with its object groups skipped by a runtime switch and 72 with them (and their
  material code) compiled out -- most likely the shader's size setting the
  register budget for every pixel. A switch that branches round a feature
  measures the branch, not the feature.
- BEFORE "FIXING" A USER'S SETTINGS FILE, ESTABLISH WHO WROTE IT. `ftesurf.cfg`
  gained `milk_panels "0"` mid-session and it looked like a harness leak. The
  harness was tested (it does not save) and the file held the user's own music
  volume and frame cap, not the harness's -- so it was the user's session, and
  the edit already made to it was reverted from a backup.
- BEFORE CHANGING WHAT A SETTING COSTS, READ WHAT THE OWNER HAS IT ON.
  "High is for a fast machine" made `milk_quality 3` raymarch every tick; the
  owner's `ftesurf.cfg` had chosen high on this laptop, where that took the
  monolith from 55 to 17-24 fps. Caught by measuring before commit. The fast
  machine got its own step (`4`, ultra) instead.
- A HARNESS ON THE OWNER'S LAPTOP SHARES IT WITH THE OWNER. A perf arm asked for
  MAIN printed `station 1` -- a real click had opened PLAY mid-measure -- with
  `[focus] window is foreground` beside it. Grep each run's log for focus lines
  before quoting its number.
- Build and verify before saying something is done: `./build.ps1` to 0 warnings,
  then the relevant falsifier (`tools/test_reccheck.py`, a `cfg/test/` arm, or a
  headless run whose log you actually read).
- Then commit that feature and push it — see the source-control rule in
  AGENTS.md. Verified work that is still only on this disk is not finished.
- IF YOU COMPUTE BY HAND A FIGURE THE TOOL ALREADY PRINTS, RECONCILE THEM BEFORE
  BELIEVING EITHER. On 2026-09-28 `maproster.py` printed "5 maps have more than
  one published build" and a hand `awk` beside it listed 31, because the awk read
  `$10` (`avail`) where the column was `$11` (`builds`) -- so it printed the
  KSF-fetchable set under a heading about contested builds, and every row in it
  was real. A wrong INDEX over the right data reads exactly like a result. The
  same session produced the mirror image from a peer: a sweep for "is this build
  anywhere on disk" that searched two of the three roots, got the right answer,
  and would have printed the same sentence either way. One read a complete set at
  the wrong offset, the other an incomplete set correctly; both had the tool's own
  summary sitting beside them, disagreeing, unread. Neither is caught by looking
  harder at the output -- only by noticing there are two numbers for one question.
- AND A SAMPLE THAT IS THIN READS EXACTLY LIKE ONE THAT IS STRONG. The same tool
  reported `surf_slobs` as a build nobody plays, from ONE demo; against 19
  attestations it is the most-played build. The finding was not wrong about its
  evidence, it was wrong about how much evidence that was. Where a verdict rests
  on a count, CARRY THE COUNT -- a later corpus raising it should read as new
  evidence, not as the earlier answer having been a lie.
- Prefer measuring to reasoning. This codebase has a long history of the right
  answer and the wrong answer being the same bytes; when a claim can be checked
  against a real file or a live run, check it. THAT INCLUDES CLAIMS ABOUT WHAT
  IS DEPLOYED: a note in this repo saying a file was never copied up is not
  evidence. On 2026-09-21 four of them had been live for three hours and the
  receipt step was failing on every cron tick. Look at the host.
- An arm that passes because its condition never occurred proves nothing. Show
  it discriminates: two cuts of `p418race.cfg` measured nothing (wrong forcing
  knob, then the window closed early) before it reproduced anything. The
  cheapest proof of a fix is the same arm against a build with the fix compiled
  out.
- **AND READ THE ARM'S OWN NUMBERS BEFORE BELIEVING ITS VERDICT.** Four arms in
  one session printed a green line while measuring nothing: a `+set` of a plain
  QC global (reads 0, so the handled path never ran), a scratch dir outside the
  gamedir (`fopen` returns -1 with no error line), stringcmds sent before the
  server spawned the client (dropped from both logs), and a `sl_hold` with an
  empty cursor (returns without a word). Each one produced output that looked
  like a result. The rule that catches all four: **the subject must print its own
  action** — a dprint, a latch carrying its authored number, or a state line that
  can only exist if the gesture landed — and the driver must grade THAT, not the
  downstream consequence.
  AND A COUNTER OF INTENT IS NOT EVIDENCE OF INK. Patch 451's labels reported
  thirteen drawn, printed each one's text and screen position, and passed a
  grader that checked those strings against the file — while nothing was on
  screen at all, because text issued inside a stream of deferred polygon batches
  never flushes. Every number was the subject's own, and every one described
  what it MEANT to draw. When the output is pixels, something has to look at the
  pixels.
- A CONTROL BUILD IS NOT `git checkout` WHEN THE TREE ALREADY HAS THE PATCH. If
  the working tree holds five commits of work, checking a file out reverts one
  patch, not the batch, and the "control" still contains the other four. Build it
  from a `git worktree` at the pre-batch commit with `-NoDeploy`, copy its .dat
  in, and prove which build ran by hash (`tools/p439smoke.py`'s cfg header has
  the recipe, including the hash that showed the worktree really was pre-patch).
- A DRIVER'S CLEANUP IS PART OF THE ARM. Two leaks survived a green run because
  the cleanup was written from an assumption instead of a listing: a save the run
  wrote into the SERVER's save root (not the scratch `cl_saveroot`), and an
  `except OSError: pass` that hid a removal which never happened. List the tree
  after the run, and never swallow an error in cleanup.
- A CHECK THAT CANNOT MEASURE MUST SAY SO, AND NEEDS A THIRD VERDICT TO SAY IT
  IN. Patch 421's angle check had two -- the files match, or the sidecar is not
  this recording's -- so every way of failing to MEASURE came out as the same
  maximum-severity accusation a forgery gets: a ping past the search window, a
  tick epoch the join could not follow, a clock that stepped mid-run. Three
  false faults on honest runs, all one shape, all found by reviewers and none
  by the suite. The fix is never a better threshold, it is the third answer.
  Before shipping a check, ask what it says when it cannot see, and make sure
  that is not "guilty". ABSENCE IS THE SAME TRAP: Patch 422's first cut read
  "no receipt" as "unsigned", and on the day the receipt step failed for three
  hours that would have flagged every signer. A missing record is evidence
  only once something shows the reader got that far (the receipts watermark).
  Patch 424 hit it twice more: a file hash that could not be taken read as
  "a different file" and lapsed a reject, and a migrate that could not see a
  file marked the row unbound for good.
- AND A WHOLE CORPUS CAN BE THE ARM THAT CANNOT FAIL. 339 .rec/.view pairs
  agreed about angles and not one of them measured anything: every v9 fixture
  drives its route with setpos and noclip, so the camera never turns. Before
  trusting agreement at scale, ask what the files VARY in -- if it is not the
  dimension under test, the sample size is decoration. Same shape one level
  down: an arm for "the tool is not installed" passed while proving nothing,
  because an earlier case in the same process had already imported it and
  sys.modules served the import. Make the condition, do not just point at it.
  AND A SAMPLE IS A CORPUS TOO. Patch 453's arm read every 16th point and passed
  a build with the yaw-wrap handling deleted, because the fixture crosses 180
  degrees six times in 5321 samples and a sparse dump never landed on one; at
  stride 1 it fails with exactly six wrong points. Ask what fraction of the
  samples the term under test can even appear in.
- AND WHEN AN ARM FALSIFIES YOUR PREDICTION, ask whether the ARM was sound
  before you write the conclusion. Patch 419's said "two servers, same second,
  same offset"; they differed, and the first draft concluded the attack did not
  exist. A reviewer checked the premise instead and found the seeds really were
  shared -- what the arm had not controlled was draw POSITION. Name the
  uncontrolled variable, and the verdict is "not demonstrated", not "safe".
- Report what the measurement said, including when it contradicts what you
  predicted. A falsified prediction is a result, not a setback.
- Changes to the recorder, the verifier or anything that writes evidence get an
  independent review (reviewers who see the code, not your conclusion) before
  deploy. Patch 375 passed every harness arm and still had five real defects,
  two of which corrupted recordings.
  Two or three reviewers, each given a DIFFERENT lens — predicate and control
  flow, consequences for recorded evidence, what a cheater gains — and never your
  reasoning. That shape found four real defects in Patch 412, two of which made
  the patch worse than no patch. Dozens of agents is not more rigour, it is the
  same finding many times over; the lenses do the work, not the count.
  Re-review after a redesign: the version that shipped is not the version they
  read. A FIX IS A CHANGE and gets its own round -- Patch 418 took four, and
  round 2's length clamp covered one of the two exits that read that length,
  turning a sign-extension bug into a one-packet server hang. Stop when a round
  finds nothing, not when you are tired of rounds.
  Review a CLEAN tree, AND HOLD IT STILL WHILE THEY READ: one round's headline
  finding was a 4 MiB -> 8 KB cap left in the working copy to measure something
  else, and in Patch 421 two reviewers had the verifier rewritten under them
  mid-read, so their line numbers were stale and one had to redo the work.
  Commit, then review, then fix -- not all three at once. To keep working while
  they read, fix in a `git worktree` on a side branch and fast-forward after.
