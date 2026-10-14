# P699 — KSF demand, styles, zones and replay investigation

## Scope

- Queue **Fetch +100 KSF** for the selected canonical map/track/leg/style from
  the TAB board, Create Server leaderboard and website. This is not the existing
  pagination button, which only reads rows already held here.
- FW (mode0/clean), SW, HSW and BW remain independent ladders. Game selectors
  now expose the styles already stored by the importer; non-forward styles force
  KSF. The website labels Forward explicitly and resets style when leaving KSF.
- Count valid embedded legacy brush start/stop timers in service map coverage;
  the menu says **zones not listed**, rather than asserting all missing JSONs
  mean untimed maps. No personal zones, fabricated JSON or unsafe donations.
- Investigate the supplied replay URLs; provide a bounded offline inspector,
  **not** a playback/conversion or native-verification claim.

Native code/pin/tag, QC Build number, owner preferences, movements and evidence
semantics are unchanged. No release/feed/version publication.

## Before/subject and falsifiers

Owned root: `C:/FTESurf-worktrees/ksf-zones-20261014T0810Z/`, with OWNER.md and
artifacts. QC started at ac450bd (P698), incorporated only published unrelated
launcher-test commits through 6050b3f. Paired engine docs start at 394fecbd0.
Canonical dirty source/engine trees were not edited or built for deployment.
Predictions were recorded in artifacts/PLAN.md before implementation.

Windows controls:

- `python surfd/test_ksftopup.py`: eight controls (including proxy, whole-worker recovery and cached-metadata bootstrap). No queued demand makes
  no requests; explicit demand files 120 -> 220 -> 247/exhausted. Duplicate
  requests do not multiply targets. A cut after fetch/before filing resumes the
  durable cursor. GET does not enqueue, POST does; 50ms lock refusal, global
  cap and remote refusal retain requests. Fast SW cannot appear on Forward.
  Linked `_ksf` map demand resolves to the base; bonus4 fetches zone34, mode2,
  without changing main/Forward rows. Embedded zone controls require both real
  brush models and invalidate cached answers after BSP replacement.
- Existing `test_ksfimport`, `test_board`, `test_web`, `test_join`, `test_surfd`,
  `test_accounts`, `test_variants`, `test_zonefit`, `test_mappool`, `test_mapwatch`
  pass. Schema-head/race tests were consciously moved to additive schema17.
- `python tools/test_ksfreplay_info.py`: v2/v3 positive controls; truncation,
  wrong headers/sizes, invalid bookmarks and NaN frames reject.
- Build from src with pwsh7:
  `$env:PATH="C:\FTESurf\src;"+$env:PATH; ./build.ps1 -Jobs 8 -NoDeploy`.
  Canonical compiler only, owned outputs, zero warnings in all three VMs.
- `python tools/ksftopup_smoke.py --qc-artifacts <NoDeploy dir> --output-dir
  <owned>/artifacts/ui-N`: real dedicated socket + loopback service. Both game
  boards actually GET clean/sw/hsw/bw and POST selected SW/HSW. Durable queue
  keys are checked. HTTP202 is not FTE's normalized 200/0; the acted test caught
  and fixes false failure acknowledgements. No public service or owner account.
- `python tools/ksftopup_web_smoke.py --output-dir <owned>/artifacts/browser-N`:
  actual headless Chrome controls exercise all four styles, source reset and
  SW/HSW POST queues. Synthetic faster styles stay out of Forward. Browser
  waits for rendered source state, not only a changed fragment. Early harness
  attempts retained: malformed cfg URL/argument order, callback202, virtual-time
  timing and incorrect `<main>` result target were not called passing evidence.
  Final acting controls use real-time CDP and a fresh owned browser profile.
- Parent inspected Forward, SW, menu HSW and browser HSW screenshots. Notify
  text is disabled in the final cfg so developer logs do not obscure the UI.

## Live source findings

Census at 07:53Z on 2026-10-14 found all **759 held approved Momentum maps**
had zones. Of **320 held beta/extra maps**, 199 lacked an indexed zone file.
An online-only scan found 198 beta BSPs missing JSON, with three containing
embedded Momentum timer start+stop brushes. LOCAL vs online is significant.
Extra/beta BSP download membership alone does not prove zone publication.
Existing mapwatch approved-zone fetching and measured compatibility donations
remain the authority; arbitrary beta zones cannot be invented by renaming files.

The supplied `/replays/<map>/<file>.rec` links return HTML viewer pages. The
viewer points at `/api/replays/<filename>?game=66t` for CSS. All **12 supplied
files** were downloaded with three-second request spacing and decoded using the
public `gokz/js/replayviewer.js` layout: **3 v3, 9 v2; 1,715,160 bytes total;
1,772–4,087 frames**. Public samples/report are retained under the owned root,
not committed. The inspector validates the full frame stream, not only a magic
number or the first coordinate. No private data or native recordings involved.

They contain pose/angles, buttons, velocity, extensions and zone touch bookmarks.
They are not Source `.dem`, nor FTESurf's text `.rec`. The earlier importer
comment asserting the source had no usable replays was false and is corrected.
Header ticks/file frames include pre/post-roll; timer interval, exact map build,
player/leg/style association, teleports and viewer comparison must be proven
before converting/filing them. BACKLOG records those falsifiers. KSF replay_id
remains zero; no native Watch/line or VERIFIED badge is advertised by this patch.

## Queue operating contract

POST existing `/api/board` or `/board/api/map` with `ksfmore=1`, `map`, `track`,
`leg`, `style`. The public site's nginx adds POST only at exact `/ftesurf/board/api/map`;
other board routes stay GET-only. No caller-supplied URL/player/file. Known KSF leg only, including
an empty selected style on that leg. A first page for an unfiled leg may be
bootstrapped from the importer's bounded, exact-name public metadata cache on a
map already holding KSF records. Stages require isLinear=false, bonus/stage
counts and track/leg combinations must match; no HTTP-side network lookup.
This matters for the supplied prosurf/monolith bonus4 links, whose main records
were present but bonus records had not yet been filed. Ten requests/minute/IP plus 64 active keys,
100 source rows/request, 10,000-row per-board ceiling. Active keys coalesce.
Exhausted boards can be retried after 24 hours. Alias resolution uses the same
provenance-based variant_base as imported boards.

Only the ordinary `ksfimport.py --watch --go` worker fetches: at most three
selected boards and five pages each per tick, under its existing total budget,
delay, lock, cache, .refused park and owed-row recovery. A request is acknowledged
only after durable row filing succeeds. Partial requests rotate to the queue's
back. 'Exhausted' means KSF returned a short terminal page, not that the website
has reached the end of its current cached rows. User refresh shows filed rows;
fetching is deliberately asynchronous, not an unbounded web scrape.

## Delivery

Source verification complete. Clean-commit deployment, NanoPi staged tests and
live hashes/behaviour are separate gates; record their result here after they act.
The native engine and QC Build number must not move for this task.

The first live worker exposed a missing integration arm: topup_step supplied a
three-cell key where watch's common filing seam needs four cells including rows.
The fetched cache/owed marker survived; no queue was acknowledged and no rows
were lost. Fix the tuple contract and leave failed fetches out of successful
refresh/strike-clearing lists. An exact old-function control now fails at that
seam; the subject drives real --watch --go through a forced filing failure,
retains the request/owed marker, then recovers and acknowledges after filing.
Direct topup_step and HTTP/UI tests alone had not covered that seam.
