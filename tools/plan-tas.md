# TAS projects, editable lines and contribution history

Requested by Lex, 26 October 2026. This extends [the styles/TAS outline](plan-styles-tas.md).
This is a staged implementation plan, not a claim that the editor or signed saves exist.

## Goal and acceptance

Let players slow movement, step exact physics ticks, branch and edit input timelines,
compare recalculated lines, optimize selected sections and collaborate with visible credit.
Keep human, segmented, assisted and sandbox results honest. Physics validity, trusted
capture and contributor identity are different claims and must stay different in the UI.

A successful final TAS completion is replayed from the legal start using the normal
movement rules. Its finish and time come from that simulation, not submitted positions,
client time, a saved finish state or previously recorded downstream events.

## What already exists

- P954 per-player host_timescale 0.1..1: command-duration pacing, unchanged physics tick,
  existing transport/thread/prediction guards, persistent practice eligibility.
- Save-lock, rewind, branch/prefix restoration and input recordings.
- Native movement replay and trigger/zone verification hooks. These are foundations,
  not a completed arbitrary-input editor or a guarantee about every dynamic world.
- Linked accounts and signing keys. Save directories alone do not authenticate authorship.

## Independent dimensions

- Assistance: live human / TAS-assisted / unrestricted sandbox.
- Assembly: one attempt / segmented, with the existing category's allowed holds/resumes.
- Contributors: solo / collaborative.
- Evidence: service-observed capture / signed self-attestation / unknown import, with
  physics verification recorded separately.

A saved revision inherits the restrictions of the input ancestry it actually retains.
Turning controls off, changing names, sharing or loading into another session cannot
make assisted material human. Unknown history is never silently treated as clean.
A new independent human attempt may start at the normal legal start after an actual
input-drain boundary; merely restoring speed is not that boundary.

The official tools can preserve those rules, not prove all human input was unaided.
Valid physics, a server timestamp or a player signature cannot prove manual play.

## Stage 1: explicit TAS practice sessions (P1052, first implementation)

Implemented and installed locally; [verification and deployment status](p1052-tas.md).
Public fleet/backend promotion remains blocked by its guarded runtime handoff.

- Console tas on, tas off, tas status and tas speed 0.1..1, retaining the existing
  host_timescale interface and per-seat routing.
- A dedicated TF_TAS ancestry marker, distinct from the active control switch.
  Reserve bit22; bits20/21 remain available to the earlier directional-style plan.
- Enabling TAS marks practice before any assisted command. The marker is monotone
  through a map connection, native observe/join, ordinary saves, rewind and exact retry.
  A complete TAS save file loaded by another player marks their session too.
  The old position-only share/mirror protocols cannot carry ancestry: stage 1
  refuses TAS gifts and omits TAS mirroring in either direction rather than
  silently stripping the marker. Existing incomplete-list protection blocks
  deletions on such lists. Full ancestry-preserving transfer is a later stage.
- off restores normal speed, not human eligibility. A new map/actual fresh connection
  resets session controls; loading TAS material raises the marker again.
- Existing local practice storage remains the retention path. TAS is displayed as TAS,
  never entered on human/segmented boards. No TAS leaderboard admission yet.
- Reader checks require the practice/cheat safety envelope; backend independently
  refuses the TAS marker even if those companion bits are absent.

Falsifiers: clean control remains unchanged; normal segmented control still classified
segmented; TAS with both run_class settings remains excluded; off, a clean save load,
observe/join and retry cannot downgrade retained material; fresh independent connection
is not permanently poisoned. Build must add no warnings and corpus faults must not rise.
This stage does not provide cryptographic authorship, stepping, editing or optimization.

## Stage 2: authoritative pause and tick advance

Implemented in P1055: `tas pause`, `tas play`, `tas step [1..128]` and actual
native completion counters on the supported Source15ms movement driver. Exact
commands, acting controls and static/shared-world limits are recorded in
[p1055-tas-step.md](p1055-tas-step.md). Matching native/qw/cs payloads are installed
and socket-tested in both Windows installs. Public guarded-fleet promotion and
broader human acceptance remain pending. Owner has confirmed the existing stop/forward
functionality; this is not a measured precision or full jump/duck/latency acceptance.
This does not complete the later editor stages.

Provide pause, play, step-one and bounded step-N. Grant movement on the trusted mover,
not by asking the client to send a chosen duration. Reuse fixed-tick Source movement and
count actual executed ticks. Preserve partial-tick carry and all movement state. Other
players and global world/audio clocks must not accidentally pause with one player.

Define input sampling while paused (hold movement/buttons, edit view/input explicitly),
coexistence with save-lock, spectate, ghost, rewind and threaded input, and acknowledgement
of a completed step. A queued/repeated network command must not consume another step.

Control: known moving body/count at play; pause leaves both unchanged; one accepted step
advances exactly one mover tick and its expected state at several render/net rates.
Static-world support first if full independent world snapshots are not available; dynamic
movers, delayed IO, physics props and shared effects need explicit limits, never false parity.
Changes to recorder/mover semantics require the private evidence-contract review gates.

## Stage 2b: exact retained-tick rewind (P1061)

Implemented: `tas back [1..128]` restores an exact retained movement tick and stays
paused. The paused TAS rewind cursor navigates integer ticks rather than line-sample
indices. Native Source jump/duck/carry state is restored in addition to the existing
body/timer/recorder-prefix path; transport/completion/request counters stay monotone.
Each granted single-step and the pause head can be restored; unknown/missing ticks
refuse, never fall back to a nearby pose. [Scope and checks](p1061-tas-rewind.md).

This is bounded live-session movement history, not a saved project format. Live
packets can cover intermediate ticks without QC prefixes, which remain unavailable.
Moving-carrier capture is unsupported, the shared world/rules stay current, and no
all-map or cross-rules parity is claimed. Recorded geometry is only a cursor preview.
It does NOT edit inputs, preserve abandoned futures as undo/redo branches, replay
arbitrary edited inputs, export a TAS movie or provide signed collaboration/boards.
Actual installation and owner feel are separate from source/test implementation.

## Stage 2c: bounded input editing and affected-tail recalculation (P1065)

Implemented console core: `tas inputs [N]`, `tas replay FIRST`, and `tas edit FIRST
[LAST] FIELD VALUE`. A paused running attempt can change movement, aim or
jump/duck/walk buttons on an inclusive slice, then recalculate every affected
stored input through the old head, at most128 ticks. Exact warm prefix/input and
headroom checks happen before restore; native storage is armed only after the
verified go. Native successful executions consume the queue, opposing live input
cannot substitute, and terminal cancellation cannot resume old tape. Assistance
stays TAS. [Scope and acting controls](p1065-tas-inputs.md).

This supplies the execution/input-edit core, not all of Stage3. It intentionally
has no persisted/imported project format, abandoned-future undo/redo branches,
visual timeline, comparison overlay or arbitrary world-state editing. Current
rules/shared world and missing-history refusal remain explicit. Source/runtime
verification, Windows installation and human feel are separate states.

## Stage 2d: next-input workshop and directional AIR help (P1074)

Implemented local authoring core: `tas menu` chooses manual upcoming movement,
view and held jump/duck/walk, then advances1 or up to128 actual movement ticks.
Auto left/right recomputes a direction-constrained, quantized observed-air yaw
per granted tick; unsupported/contact/near-cap/custom divergent-cap states use
the configured preset. It is not a collision-aware or global route optimizer.
Paused physical mouse look locks by default with deliberate unlock/Use view.
The complete GUI draft is bound on every Advance, with native authoritative
idempotence preserving unchanged assist carry across acknowledgements. Executed
heads settle after remaining packet callbacks, including bhop teleport.
[Commands, domain, checks and actual delivery state](p1074-tas-workshop.md).

This is a next-command window, not a visual editor for retained tick ranges or
Stage3 project revisions. Shared world/time, current rules and unavailable warm
history remain limits. Project persistence, comparison/interval optimization,
cryptographic contribution and TAS-board admission remain planned. Public lobby
editing policy and guarded backend/native promotion are not implied by local
implementation; owner rendered/feel acceptance is in lextest.md.

## Stage 3: project revisions and a basic input timeline

Status 28 Oct: P1077 (timeline, undo/redo) and P1082 (projects: tools/p1082-tas-projects.md)
deliver the local part; P1085 made cold reloads exact (func_bhop dwell on mover ticks, not
server time; the sub-tick carry was ruled out). Not yet: a portable format without a base
save, and a branch browser UI.

Version a canonical project format. Store map/zone/ruleset identities, full checkpoints,
immutable input chunks, parent revisions, assistance metadata and explicit origin trust.
Keep project assets separate from player data and ordinary run receipts. Bound untrusted
imports and reject malformed/nonfinite/out-of-range values before simulation.

Edit forward/side/up movement, view angles, jump/duck and action timing. Invalidate cached
states from the first changed input and re-simulate forward. Never reuse old teleports,
trigger outputs or finish events as instructions after an edit. Cache only exact matching
prefix/map/ruleset/world identities. Expose branch, undo/redo, named checkpoints and diff.

Control: unedited replay reproduces its source. One changed input demonstrably changes
the trajectory; reverting reproduces the original. Changed maps/rules/world invalidate caches.

## Stage 4: line comparison and optimization

P1074 supplies the bounded directional observed-air starting point above, not
this stage's route/time/interval optimization or comparison workflow.

Status 28 Oct: P1087 keeps the line a TAS go cut off as a pink comparison line with a ghost
on your clock and a time/speed delta at your place (Lex chose ghost + deltas first). P1088 is
the first optimizer: one constant turn rate for exit speed over up to 128 ticks (Lex's goals
were total time, exit speed, immediate speed, and per ramp: constant strafe rate, boarding
angle, end-of-ramp flick). P1092 (29 Oct) adds the boarding angle (`board`, a start-yaw
offset) and the flick (`flick [k]`, a faster rate over the last k ticks) as further 1-D
searches after P1088's. P1097 adds `time`: the next segment soonest within the tape, then
speed. BACKLOG "TAS optimizer (P1088, P1092)" holds the rest.

Overlay original/edited ghosts and trajectories; show speed, time delta, collisions and
invalid sections. A requested path is a solver target, not permission to set body state.
Arbitrary position/velocity/world edits belong to sandbox and cannot become valid TAS.

Add read-only ideal-strafe hints, then opt-in bounded interval optimization. Separate
immediate speed, exit-speed and total-time objectives. Keep original branch, selected
constraints, optimizer/version and resulting input delta. No global-fastest guarantee.
Manual acceptance: owner checks timeline feel, ghosts, colours and preview controls.

## Stage 5: signed collaborative saves

Use standard content hashes and existing account-backed signing infrastructure, with a
new versioned/domain-separated project protocol; do not reuse unrelated account proofs.
A signed revision binds canonical content, retained parents, input interval, map/ruleset,
assistance/origin metadata and the signing public identity. Server receipts additionally
bind what the service actually observed; offline player signatures are self-attestation.

Keep private keys local/protected; never copy them into saves. Support rotation, recovery,
revocation policy and historic key bindings without rewriting old signed revisions.
Sharing copies revisions and signatures, not keys. Original content remains immutable;
replacements create children. Validate the whole retained ancestry before trusting credit.

Show current input authorship separately from edit/derivation history: Alice opening,
Bob continuation, Charlie optimizer revision. Editing an early input can alter later
geometry without rewriting who supplied the later inputs. Unsigned legacy/imported saves
stay explicitly unattributed/untrusted; names/GUID folders are not proof. Shared/stolen
keys identify an account controller, not a biological person. Independent identical routes
are not automatically evidence of copying or ownership.

Falsifiers: untouched shared revision verifies; altered input/parent/identity/trust metadata
fails; truncated/missing/unknown ancestry cannot acquire trusted origin; key lifecycle and
account display changes preserve only the claims actually supported.

## Stage 6: TAS verification and separate boards

Use an isolated bounded server verifier to simulate final inputs from the legal start,
including required trigger/world behavior. Derive time and finish from the simulation.
Bind results to exact content and rule versions. No client-supplied states/timing or absent
ancestry can earn human/segmented admission. Offline/self-attested TAS can have a policy
of its own without pretending it was service-observed or human-played.

Add explicit TAS board/filter/replay/export and contributor display only after this path
is qualified. Keep existing human and segmented admission unchanged. Resource caps,
retryable infrastructure errors, retained source inputs and content-bound verdicts follow
the existing service conventions. Deploy the coupled readers/program/backend set only
from inspected commits, with destination hashes and live category controls recorded.

## Delivery order and open decisions

Stage 1 is a safe local practice foundation, not ranked TAS delivery. Stage 2 then supplies
the core hands-on tool. Project format and the final verifier should be designed together
before widening imports or enabling public TAS submissions. Signed collaboration follows
the immutable project format rather than signing today's mutable save directory.

Owner decisions before later stages: private-only versus lobby TAS editing; which dynamic
maps are supported initially; preferred optimizer goals; account/key recovery UX; public
credit visibility; offline TAS admission policy. None is needed to mark local TAS practice.

Lex decided 28 Oct: optimizer goals total time, exit speed, immediate speed and per-ramp
(constant rate, boarding angle, end flick) -- P1088 first; signing through the Steam-linked
account (recovery = relink; unlinked players share but stay unattributed); credits public;
TAS boards admit only runs the server re-simulates from the legal start (no offline TAS).

## Stages 5-6: the patch sequence (28 Oct)

What exists (code map 28 Oct): fskey Ed25519 (engine/client/cl_receipt.c) with `FTESURF-<KIND> n`
statements naming their audience in a `server` line; account links `keylinks(pub -> steamid)`
and bans in surfd/accounts.py; zone drafts as the challenge-plus-sha precedent
(surfd/zonepub.py); TF_TAS refused by /api/run; style/tier plumbing; a headless arm64
`pm_verify` that checks a recorded trace (teleports from the file's own rows) -- not a
re-simulation from inputs.

5.1 Canonical revision hash (QC, tools): a project revision's identity is the sha256 of a
canonical form (identity lines, inputs, checkpoints; not the save time or local save id), and
a parent is named by that hash, not name/rev. `tas project hash`; a Python twin for surfd.
DONE as P1089 (28 Oct): a hash chain over the canonical lines; a file counts only if it is
exactly what the writer writes (SV_TASPLineCanon, mirrored by tools/tasrev.py, which may be
stricter, never looser; tools/test_tasrev.py's 31 mutations agree with the game); parentsha
is lineage and part of identity; the real file is never written in place. Four review rounds.
Open for 5.3: an inputs-only digest (base sha + rows) so a copy re-saved as a new root is
seen as the same work; the base covers state.txt only, not run.rec's prefix (6.1 removes it).
5.2 `FTESURF-TASREV 1` (engine client): audience surfd; lines sha, parent, mapcrc, ticks (the
revision's `supply`), code (the CSQC's sha256); fskey under a real key press, loopback games
only, the VM the very csprogs the map served. DONE as P1090 (28 Oct): .tasp version 2 adds a
hashed `supply` (exact diff against the parent's own rows; a root supplies every tick; never a
tick at or before the parent's base); every revision saved or loaded is kept as rev/<sha>.tasp,
statements are write-once rev/<sha>.<id>.tasrev, and only revisions the host saved
(rev/<sha>.made) are signable; CSQC is denied data/tasproj/. tools/tasrev.py: changed_ticks,
--supply, --sig. Five review rounds.
For 5.3/5.4, from those reviews: credit is per row, each tick to the nearest ancestor in a
verified chain whose row matches it (against the parent alone, a truncated parent re-credits a
grandparent's rows and reverts launder credit); priority by the rows themselves, tolerant of a
shift to other ticks (a checkpoint line alone changes the sha); an early commitment only the
signer could make (content + pub, not the bare sha), ideally statement-only registration at
signing time; `code` checked against an append-only list of every released csprogs sha256
(statements are signed offline and uploaded later); the key->account binding from the signer's
own upload or the statement's earliest evidence, not whoever uploads it; the CRC32 map identity
is forgeable (credit only; boards re-simulate); `saved` is not a time and `origin` stays out of
the hash until it has a second value; `.made` is the host's word, not evidence.
5.3 surfd `/api/tasrev`: upload revision + statement; verify the signature and the key's link
AT RECEIPT; store revisions immutable by sha with first-seen time; an append-only key-binding
history (keylinks today is overwritten on relink, deleted on unlink); unknown parents are
stored as "ancestry unknown" and earn no credit for what they would have supplied.
5.4 Public credits: per revision, who supplied which ticks along the signed chain (Alice
0..500, Bob 501..900, Charlie optimizer revision); unsigned or unlinked = unattributed.
5.3 + 5.4 BUILT as P1091 (28 Oct): surfd/tasrevd.py, an isolated service (tasrev.md is its
contract; tools/install_tasrevd.py installs it, root). Four review rounds; the last fixes passed
the round-4 reviewer's fuzzers (800 arrival-order trials against a brute-force reading of the
contract, 300 statement/cache trials). LIVE 29 Oct 00:48Z at https://play.proto.bar/api/tasrev/
(unit ftesurf-tasrevd, source 5352dbae); no game client uses it yet (5.5).
P1119 (30 Oct): the rollback-checked upgrade tool is published. Its final Pi suite passes
20 tests and catches all 23 retained mutations; a clean exact-commit upgrade dry-run passes.
The live root apply still needs the owner's sudo; until then the service remains on 5352dbae
and does not have the version 3 credit parser. This does not block isolated 6.2 research.
5.5 Client: share, browse, open a downloaded revision as a project.

6.1 A project from the legal start (no base save): the run's start zone and spawn, so a
verifier has nothing to trust but the map, the rules and the inputs.
P1100 (29 Oct): steps 1-2 -- TAS starts take no start nudge (`startjit 0 0 0 0`); `tas start
<zone>` opens a legal-start session at the zone's own destination; TAS steps and `tas back` in the
start box and back across the start, by replay from the canonical placement (measured exact). Step
3 is P1110: version 3 projects (`start <zone>`, `baseat` standing still, `startat`, ticks from the
placement), saved from a session and loaded by placing and replaying (the clock must start on
`startat`); a session's saves are one revision line; tasrevd supply-checks a v3 child and never
joins a v3 line to a base save's. BACKLOG "TAS legal start".
6.2 Headless re-simulation WITH the map's own world: a dedicated server drives the tape using
a real headless client (P1095; the bot input path is not equivalent). Triggers and teleports
run live, not copied from rows; output `VERIFY-TAS PASS ticks N finish` or HOLD/REFUSE with why.
Pinned binary/progs/map; only the Pi's result counts (Windows/Pi physents have differed).
Further measured 30 Oct, using the retained P1110 progs and owned bhop_eazy fixture, not the
current live fleet or canonical map zones:
- A Windows-made v3 project cold-loads on the Pi exactly (80 input rows, startat 32). Moving
  startat to 31 is refused; altering its head checkpoint reports divergence at row 80.
- Extend that prefix with forward/jump inputs: the real END region (fixture x400..432)
  finishes the timer at run tick 342 / legal row 374 and closes a fault-free recording.
  All 342 recorded run inputs match the project after startat; changing the first input
  or shifting startat fails that comparison. The remaining 1126 supplied rows are unused:
  verification must allow a natural finish before the supplied head.
- An ordinary project load is NOT a verifier verdict. At that finish its editor driver
  reports `the engine stopped the input tape`, since it expects the entire chunk to end
  while the timer is running. Neither this expected abort nor a successful editor load
  is `VERIFY-TAS PASS`. Still unbuilt: a bounded production runner which binds the admitted
  bytes to the fresh native run/finish and emits its own result, plus the queue/board path.
6.3 surfd `/api/tas/submit` (a signed revision whose re-simulation finishes) -> queue with
per-submission tick caps -> Pi verifier -> a `tas` style written only by the verifier, as
importers write momentum/ksf; /api/run keeps refusing TF_TAS.
6.4 The TAS board tab and contributor credits on it.

Lex's Stage 6 decisions (29 Oct): no start nudge for TAS starts; a legal-start project starts
standing still at its track's or stage's own start-zone destination -- where `!r` puts a player
(SV_ZoneDest: teleDestPos/yaw, else info_teleport_destination, else the zone floor, then the
ground snap), never the map's player spawn -- with its inputs covering the approach in the start
box and the timer starting the normal way; TAS stepping in the start box for those projects, and
a rewind across the start re-arms; one `tas` style per map, track/stage and tick rate, with
tasrevd's contributor credits; the Pi verifies one at a time, at most 96000 ticks a submission,
3 submissions an account a day, and over 2x the tick count in wall time is HELD; Steam-linked
submitters. 6.2 measured (P1095): a headless client replays a project exactly, and a project
saved on Windows reproduced every saved state exactly on the Pi.

Risks to design against: trusting any file row that sets state (warp/ride/state) lets a
forger set teleports or times; server-time world logic makes replays differ (P1085 fixed
func_bhop; others are unaudited); a copied fskey signs as its account until unlinked; anyone
can re-sign someone else's inputs, so credit follows the parent chain and first-seen time;
a verified TAS stream played live is still a human-board cheat that re-simulation cannot see.
