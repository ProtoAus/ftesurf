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

## Stage 3: project revisions and a basic input timeline

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
