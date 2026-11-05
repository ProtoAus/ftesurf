# P1329: historical controls for the local TAS line

## Problem

Literal replay correctly reproduced the captured input but left the controller
showing the latest draft. Requested guide yaw is also different from the guide's
effective input yaw: copying the latter back into an unchanged new step silently
changed the requested route.

## Change

Local full-line projects can carry optional, hash-bound authored settings. At a
paused completed tick, Controls restores that tick's known movement, held bits,
mode, turn amount, requested aim and vertical-follow choice. A new GUI step
inherits these settings until the user changes them. A deliberate local look
change supplies the new aim; this does not move the paused body. Apply-only
changes remain a draft rather than relabelling an already executed tick.

This uses the completed tick T, consistent with native warm back/seek. A Timeline
row T+1 is the next input, not the same label. Merely selecting another row does
not import its procedural settings; seek to its body to restore known controls.

### Format and bounds

The existing base-project format gains version 4. Versions 1/2/3 remain readable;
version 3 legal-start projects and literal input templates retain their existing
format and do not invent missing procedural intent. Unimplemented version 5 is
refused, not advertised as legal-start settings support.

Optional ranges occur after checkpoints and before input rows:

```text
intent first last mode amount follow forward side up pitchword yawword rollword bits
```

Ticks are inclusive, increasing, non-overlapping and inside the captured line.
Omitted ticks are explicitly unknown. Each range has exactly ten setting values:
mode 1..5, finite float32 amount 0..4, follow 0/1, integral forward/side -450..450,
zero up/roll, signed angle words (pitch -16202..16202, yaw -32768..32767), and held
bits 0..7. There are at most 4096 ranges and the existing 96000-input cap remains.
An excessive-range save fails without replacing the previous revision. Canonical
float32 exponent notation is accepted for turn amount only; other console-number
grammars are unchanged. Saved numeric zero has one spelling, including when a
valid console argument originally supplied negative zero.

The ranges participate in the existing revision hash. Supply, changed-row credit
and contribution checks still count actual input rows, not metadata changes.
Settings are input-only declarations: they are not a body, snapshot token,
signature, eligibility decision, native grant or verified generator evidence.
File-loaded settings are labelled Saved. Live authored settings are retained only
after the current native grant settles consistently; incomplete or stale work
cannot manufacture a known recipe. The packet describes only the current local
body context. No signature is generated automatically.

Preview preserves the original file; Discard/Keep/Undo/Redo replay the respective
metadata with the line. Re-authored settings make the working revision dirty even
if its seven raw input values do not change. Raw edits and template pastes clear
settings only where input values actually differ; no-op rows retain their known
settings. Literal-gap lookup uses bounded binary search over ordered native
ordinal spans, not a full history scan per input. Quiet panel refreshes have a
separate bounded gate and cannot overwrite a pending grant's vertical-follow
choice. Metadata arrival does not reset the local-view anchor established at the
body/stat acknowledgement. Legacy movement stays explicitly selected: a view-only
Follow click cannot silently convert it to gain GUIDE. Settled intent is flushed
before save serialization and before editor row/dirty comparisons, after command
arguments are owned. A closed workshop must not depend on polling or a post-save
event to make its final grant durable. The revision service uses the matching v4
reader and validates every declared-supply format against its known parent's
actual rows, including v4. Metadata remains hash-bound but earns no input credit;
base-save and legal-start timelines remain different domains. Reader/service
support must be installed before clients emit v4 uploads. Normal in-game sharing
still requires an exact legal-start v3 header before uploading statements/body;
local v4 files cannot enter that path, so local-editor rollout is independent of
the API upgrade. Do not remove this guard or call v4 portable. The isolated installer
also ships both profile modules now imported by accounts; its actual temporary
release import check prevents depending on the surrounding checkout. Native
body/authority gates, movement, recorder formats and QC Build number are
unchanged; no native C, pin or tag change belongs to P1329.

## Verification

- All three QC VMs compile with zero warnings.
- Socketed real dedicated-server scenario: 43 workflow assertions, including
  normal unassisted physical play, pause, two different eight-tick authored spans,
  actual backward/forward literal replay and restored controls/body readback.
- Preview leaves original bytes unchanged; Discard restores them; Keep creates a
  new valid hash; an edited literal tick is unknown while its neighbour remains
  known; Undo/Redo restore the corresponding settings and immutable original.
- The real Controls Step1 widget grants exactly one native mover tick and keeps
  the stored requested aim. Explicit local look changes retarget the next step
  without themselves granting movement. Tiny canonical amounts round-trip through
  both client/server parsers; invalid/noncanonical amounts grant no work.
- Eleven native/Python parser pairs: current game-written v4, legacy v2, 4096-range
  positive, 4097-range refusal, 96000-input positive, malformed settings/ranges and
  unsupported-version refusals. Accepted native revision hashes equal the twin.
  The combined scenario has 65 assertions. Probe files are created only in the
  owned fixture and removed with a matching-byte guard; filesystem hash refresh,
  not a server restart, makes externally written probes visible.
- Follow-up literal-production-function checks in the real QC VM: seven acting
  baseline failures become passes for pending Follow in both directions,
  metadata-only baseline retention, mixed raw/template no-op preservation, legacy
  Follow ownership and a local turn between stat acknowledgement and metadata.
  A 30000-input literal gap before 4096 authored ranges triggers the old VM's
  actual runaway limit; binary lookup completes and retains all ranges. Native
  negative-zero emission is canonicalized. These nine focused checks use
  synthetic state/stat/view sources, not genuine body/grant/device acceptance;
  the minimal fixture's owned-process stops are not normal gameplay-exit passes.
  The full 65-assertion dedicated workflow also passes on the corrected build;
  both of its actual game processes quit normally with code0.
- Closed-workshop real dedicated control/subject:21 checks each. The old code
  loses the last settled HOLD declaration on direct save/native reload and on
  metadata-only freeze/seek; an explicit pre-save event acts as a positive
  control. The subject retains both declarations, reloads the actual native file,
  preserves all seven raw values and earns no input supply. Neither run opens
  the workshop; both real client/server pairs quit normally with code0.
- Revision service suite:37 tests pass, including v4 metadata-only inherited
  credit and identical input digests, hash tampering refusal, exact/wide/missing
  supply declarations, legacy-parent transitions, late ancestry and legal/base
  separation. Three known-parent supply cases act as failures before the service
  format gate is extended. API size/storage/rate budgets are unchanged; the local
  96000-input cap is not a promise that every file fits the existing upload budget.
- On the NanoPi, the same37service tests and21installer tests pass. An actual
  isolated-release import fails with the previous six-file installer, then passes
  with both accounts profile dependencies included. The upgrade targets only the
  TAS service: main-backend/lobby/nginx configuration and TAS state/code-list
  paths are unchanged. These are unit/import checks, not live-upgrade evidence.
- Existing Python revision-chain, supply, legacy and new optional-metadata tests
  pass, including metadata-only hash changes with no input-row credit.
- Mandatory recorder tests: 949 checks, zero failures. The primary install's
  runs/parts sweep contains 548 recordings/parts and 716 entries with paired views:
  existing faulty-entry count stays 351 against the identical baseline reader,
  with input bytes unchanged during comparison. This is no-increase evidence,
  not a clean-corpus claim. The secondary install has no run corpus. A broader
  default sweep of legacy kept-save prefixes is blocked by an unchanged access
  denial; its permissions/data were not altered and that sweep is not claimed.

## Deployment — 5 November 2026 UTC

The final publication programs are byte-identical to the qualified mover/parser
builds. Compiler/runtime inputs did not change in service-only commit e69806b0;
paired engine79dafa90 changes documentation only, not native code/pins/tags.

- BOTH Windows: all six progs/symbol files per install and their `.prev` hashes
  match the exact transaction;24current/prior-prev code preimages retained,
  23native/config hashes unchanged. New CSQC caches seeded with the existing tool;
  no pending downloads removed. An installed-byte real dedicated-socket smoke
  passes7checks; its owned client/server both quit normally code0.
- ALL12lobbies: progs-only QW5e8cd6d1 / CS1ca3a29c,12new native/plugin epochs
  checked; native images/configuration/backend generation unchanged. All8actual
  recorder parts and180complete resume payload/state members captured and each
  rehashed ONBOX/OFFBOX before staging/restarts. Actual locked JIT FD/actor checks
  passed. Postflight preserves all47525old protected paths, zero changed/missing.
- The outer SSH caller timed out after240s; original on-box prepare/activation
  receipts completed successfully. Read-only reconciliation verified those same
  12new actors, destination/predecessor hashes and released lock. No swaps or
  restarts repeated; the failed caller transport remains a failed transport.
- The shipped CSQC hash was append-registered in the existing TAS code catalogue,
  preserving every prior byte/code, without a service restart.
- The standalone API reader upgrade is reviewed/tested/published but NOT deployed:
  the existing account needs owner sudo authentication. Its old v3 service remains
  compatible with the unchanged portable-v3 game path. Native/config/data/shader
  files are not promotion targets. No full Windows-data-hash claim is made; the
  separately recorded unreadable old kept-save prefix remains untouched.

## Remaining limits

These checks and delivery are not owner feel acceptance, genuine-device Sign,
cold/shared-world replay qualification, arbitrary command timing or a completed
section/next-ramp solver. Human acceptance remains pending in lextest.md. Local
v4 settings do not confer portability, body authority or public-board eligibility.
The earlier unpublished reservation 1325 was replaced by the fresh 1329 claim;
original evidence retains its original labels and timestamps.
