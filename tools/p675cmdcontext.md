# Patch 675: exact command identity and scoped SSQC execution context

P672's optional replayed pre-input seam remains **unused by normal client QC**.
P675 adds the exact/native execution identity prerequisite; it does not implement
requests, admission, server-prepared movement descriptors or baseline coverage.
No instant hold release/reset/load/rewind is enabled. Timer, recorder and ranking
remain server-owned. No Build/release/deployment is implied by this patch.

## SSQC contract

Declare **all six optional globals as float scalars** to opt in. They are
read-only metadata inside native Q1 SSQC `PlayerPreThink`, reseeded immediately
before the callback and zeroed immediately afterward. Typed discovery zeroes
valid exports and rejects other types. Incomplete exports are unavailable, not
a partially valid interface. QC writes are not interpreted as operations.

| Global | Meaning |
|---|---|
| `input_cmd_kind` | 0 unavailable, 1 decoded classic QW, 2 FTE timestamp-derived execution |
| `input_cmd_sequence_lo` | exact low 16 bits of the native uint32 command sequence |
| `input_cmd_sequence_hi` | exact high 16 bits |
| `input_cmd_msec` | top-level executed-command duration before native subdivision, unscaled ms |
| `input_cmd_piece_msec` | actual current server piece, unscaled ms |
| `input_cmd_offset_msec` | sum of executed preceding native pieces, unscaled ms |

Kind 1 includes genuinely decoded redundancy recovery (incoming packet sequence
minus two/minus one/current). Gap-filling by repeating `lastcmd` is **not** a new
decoded command: kind 0. Spawn, legacy/non-independent/server-tick calls also
remain kind 0. A native budget guard that shortens a command invalidates the
context. Missing/invalid payloads, invalid kind and nonfinite/out-of-piece
intervals are unavailable; all available fields are zero. Sequence zero itself
is valid when a decoded command wraps: it is not an unavailable sentinel.

Kind 2 identifies the decoded command but its duration is derived from server
execution timestamps/clamping, **not guaranteed original client input length**.
Neither kind is an admission grant, operation ACK, map/connection epoch or
proof that an authoritative baseline contains an operation. Full-QC movement,
Q1QVM, spectator and other non-native-PreThink paths do not provide this scope.
Do not cache it as permission for `StartFrame`, touch, postthink or stringcmd.
Gamespeed/frametime caps are not folded into these raw-millisecond fields.

Server physics is unchanged: commands over 50 ms still use integer truncation
and half/remainder recursion. Thus 51 ms executes 25+26; 50.5 executes 25+25;
100.75 executes a 100 ms subdivided budget. Offsets describe **those actual
pieces**, not the P672 client's fractional-half policy. Logical identity is
useful, but universal server/client piece equivalence is not claimed.

## CSQC contract

P672 optionally reseeds float `predinput_sequence_lo` and
`predinput_sequence_hi` on **every invocation**, including replay/subpieces.
Only float exports are accepted; restricted discovery disables them. The legacy
`CSQC_PredictPlayerPreMove(seat, sequence, seconds, offset_seconds)` signature and
its lossy float sequence argument remain unchanged for compatibility. Metadata
writes neither change the command identity nor survive the next invocation.
Missing words leave the P672 interface usable on both old and new engines.

Each word is exactly representable as a QC float. Compare the pair or use an
explicitly typed integer representation. **Do not recombine into float32** and
reintroduce the alias above 2^24. Connection/map generations and serial ordering
across uint32 wrap remain the future operation protocol's responsibility.

## Falsifiers and evidence

`test_cmdcontext.py --engine E --out ARTIFACTS` compiles real server publisher,
lookup, budget/split prefix, wrappers and scoped PreThink source with native
headers/compile flags from `compile_commands.json`. The remaining VM/mover and
full-QC path are explicit downstream doubles, not live collision/network proof.
Tests cover zero, word crossings, float-precision boundary, high-bit and wrap
identities; integer/fractional subdivision; budget shortening/refusal;
synthetic/legacy unavailability; full-QC bypass; absent/incomplete exports;
nonfinite/invalid timing; typed lookup and post-callback clearing.

`test_predinput.py` still tests P672 replay, held/carrier and atomic rejection;
it additionally asserts exact words on every replay/subpiece, deliberately
dirties them, and checks missing-word compatibility. Normal builds still do
not include either fixture.

Dedicated fixture preparation in an **owned** QC build:

1. Build all three normal progs with `src/build.ps1 -NoDeploy`; use those owned
   outputs, not either running install's source. Build the exact native subject.
2. Copy `sv_progs.src` to a test-only manifest, give it a separate output path,
   insert `../tools/fixtures/cmdcontext_begin.qc` immediately BEFORE
   `server/sv_player.qc`, and append `../tools/fixtures/cmdcontext.qc` at the end.
   Compile with fteqcc in `src/`. Do not use global `-DPlayerPreThink=...`:
   renaming the fixed system defs caused an acting compiler refusal (Q208).
3. `runlines_smoke.py ftesurf/cfg/test/p675cmdcontext.cfg --dedicated --mount
   --client <exact-client> --server <exact-server> --ssqc <fixture.dat>
   --output-dir <existing-owned-artifacts-dir> --port <free-lobby-range-port>
   --server-arg "+set test_cmdcontext 1 +set _pext_vrinputs 0"`.
   Explicit `--server`, `--ssqc` and `--csqc` select/copy fixtures without swaps.
4. Grade retained server/client logs with `test_cmdcontext.py --log SERVER
   --client-log CLIENT --kind 1`. For kind 2, set `_pext_vrinputs 1` on BOTH
   sides before connecting (copy the cfg into owned artifacts for this arm).
   For compatibility, the same fixture on a pre-P675 server must pass `--kind 0`
   while original PreThink/StartFrame and the client act.

Pre-publication acting dedicated results: QW 501 decoded observations, 68 split
observations, 433 complete executed budgets; FTE 182 decoded, 13 split, 169 complete;
old P672 server 600 unavailable callbacks. All include frame-clear controls.
Negative graders reject missing PreThink/frame observations and stale context.
High words/wrap and synthetic routing have native unit/source coverage; a forced
packet-loss/reordering runtime matrix is **not** claimed. Fresh candidate cfgs
failed before client completion, including a retained P672 client control;
the final cfg follows the reread, acting P672 setup rather than counting those
failed logs as evidence. No unrelated renderer/network repair is included.

Full Windows client/dedicated/five-plugin and normal progs builds passed (QC
zero warnings; 48 compiler-warning kinds, no new kinds versus P672). Independent
native source review found no blocker. Recorder suite: 306/306; read-only
270-run corpus: 165 pre-existing faults before and after. These are separate
from operation prediction, Linux/fleet tests, deployment and release.

## Next integration boundary

Prepare complete canonical descriptors tied to map/connection and save/zone/run
identity/generations. Resolve reset's actual server-selected zone/start save;
keep navigation/held load/release and warm/cold rewind semantics explicit for
all carried fields (including native Source state). Add bounded request
admission on a decoded **logical command** rather than an arbitrary stringcmd.
Reconcile against operation-bearing authoritative body baselines, not only the
processed save ACK; only then install a normal CSQC consumer and route every
frontend. Exact words/provenance alone do not close any of those obligations.
