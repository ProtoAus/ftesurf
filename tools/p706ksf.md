# P706 — original KSF demos and automatic advertised-demo imports

## Original files in the game

Load the matching map, then:

```text
replay ksf <path/to/original.rec> <map> <bonus: 0=main> <FW|SW|HSW|BW>
```

For example, an original CSS/66t `surf_monolith` bonus-4 file uses
`replay ksf cfg/ksfreplays/original.rec surf_monolith 4 FW`.
No Python/conversion command is needed by the client. `cl_ksf.qc` parses the
original v2/v3 layout into Watch's in-memory imported recording; it does not
write player data or a native run. Existing pause, seek, playback rate, path,
HUD and camera controls apply. Ordinary converted P702 aliases still work.

Map, course and style are explicit: the binary does not supply trustworthy
identity. Main/bonus start exit and finish entry must be unambiguous; no full-file
fallback. Keep lead-in at negative time, include the finish sample, ignore
post-roll for timed duration. Source positions/velocity/angles, raw buttons,
ground when recorded, and recorded analog moves are preserved. Direction keys
follow the emitted six-decimal moves, including cancellation and tiny analogs.
Duck body state and BSP build identity are unknown. No native integrity,
verification, plane, receipt or authority is invented.

Limits: CSS/66t only, main or bonus 1..69, original versions 2/3, 16 MiB and
40,000 source frames. The bounds are checked before the engine's materializing
file builtins. Unsupported, malformed, nonfinite, truncated, oversized or
ambiguous selected courses refuse. Wrong-map/failed open tears down an active
viewer; command syntax errors just show usage and do not replace it. CSS100,
other games, stage cuts and build hash matching are not implemented. Automatic
normalized text uses the converter's independent 200,000 emitted-frame bound.

## Automatic discovery and board Watch

The public records API already puts a `file` field on the few rows with demos.
The existing polite board crawler caches those rows; `surfd/ksfgrab.py` scans
that cache, downloads only validated advertised CSS leaves from the fixed raw
endpoint `/api/replays/<file>?game=66t`, retains original bytes/provenance, and
normalizes a text replay under `SURFD_KSF_RUNS` (default `data/ksfruns`).

Enable on the existing **approved unattended crawler command**:

```sh
python3 ksfimport.py --watch --go --demos --max 10 --delay 3
```

`--demos` is opt-in so an existing cron is not silently changed by copying code.
It reserves at most two requests inside the existing `--max` (eight board + two
demo requests at max10), holds the same crawler lock, sleeps before the first
and each later demo request, rejects redirects, caps each response at 16 MiB,
uses a 30-second socket timeout and a 30-second incremental-body deadline
(plus at most one blocking read), and shares `.refused` host cooldown with the board crawler. Socket, header and
body failures park the host; local codec/disk failures defer only that job.
A 256 MiB free-space reserve protects the archive. Each tick scans at most 32
cached boards; durable intent has at most 256 current jobs, and bounded
seven-day tombstones retire three-strike local failures. This is gradual
backfill, not an unbounded per-map/player probe.

Deploy `ksfgrab.py`, `ksfimport.py`, `surfd.py`, and **both** codec dependencies
`ksfconvert.py`, `ksfreplay_info.py` as one tested set. A Pi flattened surfd
install places the codecs under `surfd/tools/`; a checkout uses root `tools/`.
No network fetch runs in a web handler. Dry runs/no `--demos` do not download.

Only an exact current KSF PB gets the replay ID: map, course, style, player,
official rounded millis/date and an identity containing upstream record ID,
raw double seconds and advertised-file hash. A sub-millisecond faster PB or
replacement/withdrawn file clears the old association. The seed path retains
raw seconds and cannot erase a known unchanged exact binding with rounded-only
metadata. Failed indexing leaves files and pending intent for recovery.

Indexed rows are kind/tier `ksf`, served from the separate normalized root by
`/api/replay/N`; the existing `rep` -> cache -> board Watch/line flow needs no
new wire protocol. Native/ranked/community rows remain unchanged. A base-map
KSF time shown on an incompatible catalogue variant retains its time but has
no Watch, rather than bypassing the exact map guard. Not every time has a demo,
and downloaded imports do not become native verified records.

## Verification

- All three QC programs build with zero new warnings using isolated `-NoDeploy`.
- Twelve original clips (three v3 main `surf_null`, nine v2 bonus-4
  `surf_prosurf`/`surf_monolith`) passed real dedicated runtime controls:
  every source pose trace, endpoint velocity/keys/state, negative lead-in and
  timed end, pause, seek, rendered playback advance, path draw and active
  wrong-map refusal. `tools/p706ksf_smoke.py` uses the original bytes in game,
  the independent existing P702 byte decoder and converter only as controls.
- Sixteen original-loader negative arms include version/header/frame/extension/bookmark
  faults, truncation, nonfinite pose/analog, byte/frame caps, invalid course/style
  and bad numeric syntax. Every arm first opens a real valid viewer to prove
  the subject acted and checks refusal/cursor teardown versus syntax preservation.
- `surfd/test_ksfgrab.py --out <owned-artifacts-dir>`: 17 offline acted tests for
  exact binding, SQLite/API/index idempotence, sub-ms replacement, withdrawal,
  host refusals/body reset/IncompleteRead/stream cap/deadline, seed ordering, real main-budget/lock,
  32-board rotation/256-job cap, obsolete queue progress, interrupted publication,
  local failure retirement, variant Watch suppression and path/kind refusal,
  plus 256-warm/one-cold queue saturation and warm missing-file recovery.
- A real public first-page board returned 17 rows, four advertised demos at
  ranks 1/2/5/16. Exactly one advertised original was fetched/indexed; its retained
  actual bytes then drove an isolated real API/client control: board row `rep`,
  cold download/cache/Watch and warm Watch with no second API replay request.
  Failed URL-setup arms are retained separately; only the quoted-URL final arm
  is passing. No production DB or player files were used by this control.
- Existing surfd/replay/board/ranked/web/KSF import/top-up/variant suites pass.
  Existing converter 9 tests, binary inspector 2 tests, unchanged native reader
  suite pass. Same-byte corpus control: 289 REC, 101 VIEW; 184/4 preexisting
  faults respectively, subject identical and delta zero. The reader source is
  byte-identical; changing corpus totals over time is not a code regression.
- Fresh read-only review identified transport cooldown, legacy seed ordering
  and warm-queue starvation blockers. Acted regressions now cover all three;
  warm readable exact links are excluded before admission and removals persist.
  Final gate receipts must be read
  separately from earlier intermediate passing runs.

Evidence root: `C:/FTESurf-worktrees/ksfnative-20261014T134727Z/artifacts/`.
`CHECKPOINT.md` records exact commit/build/push/deploy/verification states.
No native engine code/pin/tag, QC Build, public release or updater-feed change.

## Delivery state

Candidate implementation and isolated gates only at this document's creation.
Publication, dual Windows installation and NanoPi backend/crawler enablement
require their separate exact-commit/hash/runtime receipts. This paragraph is not
a deployment claim. Do not restart an occupied lobby or the owner's client.
