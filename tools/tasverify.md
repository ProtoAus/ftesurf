# Native legal-start TAS verification

`tasverify.py` is an operator-only Linux/aarch64 replay CLI, not an upload API,
queue or board publisher. Only a future trusted queue may promote its results.
It never submits a human run, and an uploaded recording or receipt is not authority.
See [the TAS plan](plan-tas.md), sections 6.1-6.4.

## Runtime and invocation

Use an agent-owned task root and a minimal fixture under `fixture/sv/ftesurf`.
The operator supplies the approved native server, GL client with the headless
renderer, matching HL2 plugin, QC, map, zones and dependencies. Do not point the
job at a player's install, account state, lobby data or an existing output root.

```sh
python3 -B tools/tasverify.py runtime \
  --fixture "$TASK/fixture" --server "$SERVER" --client "$CLIENT" \
  --plugin "$PLUGIN" --map "$MAP" --gamemode surf \
  --output "$TASK/runtime.json"

python3 -B tools/tasverify.py run \
  --runtime "$TASK/runtime.json" --project "$TASK/candidate.tasp" \
  --out "$TASK/job-unique" --port 27616
```

Generating a manifest does **not** approve a runtime. The queue must later match
its immutable approved profile, not accept an uploader's manifest. Run this CLI
serially; the queue integration must enforce the single shared verification slot.
Its port must be unused and reserved for the job, never a lobby/sweeper port.

The current profile is Source **15 ms** only, using legal-start `.tasp` v3.
Base-save projects are practice only. An incompatible mode/map tick-rate overlay
is held explicitly; it is never silently omitted to obtain a fallback profile.
The runtime includes actual per-map rules, selected-mode rules, entity fixes,
map/model collision sidecars, native `.ent`/`.edo` entity fallbacks, and applicable
absence witnesses. Present dependency bytes and absent dependencies are rechecked
before launch and before PASS. Native VFS lookup ignores case: case aliases or
collisions in relevant dependency names or their parent directories are held,
not silently omitted or resolved differently. Missing/empty optional asset roots
are also case-fenced. Regenerate legacy manifests lacking `case_roots`.

## What PASS establishes

Each job freezes the raw project and runtime, then creates separate fresh VFS roots
for a dedicated server and headless client. Verified executable/plugin copies are
colocated in each private binary directory. Native `-pluginrootonly` confines all
FTE plugin lookups from startup to that directory; a positive native acknowledgement
is required. Ordinary global/root fallbacks and package plugin enumeration are not
used in this opt-in mode. Compiled-in code and platform libraries remain part of
the trusted engine/OS. Actual executable inodes and mapped HL2 plugin images are
checked; a nominated but shadowed plugin is not evidence.
No home directory or existing install is mounted.

The server's developer-log binding joins its actual project reader and canonical
start placement to the admitted revision, start zone/approach and track/leg.
The ordinary player load message is unchanged. A fresh client load acknowledgement
and actual finished timer are required, followed by exactly one closed native TAS
recording from that job. The recording must have matching world/physics identity,
zero start nudge, no restored/held context, the native finish tick count and the
exact consumed project inputs. Mover ticks, not packet ordinals, establish the
consecutive input horizon. Normal world teleports/velocity triggers are allowed;
editor placement and restore transitions are not.

Only rows consumed through the natural finish count. Claimed times, checkpoints,
exit speed and unused project tail do not substitute for the native finish.
Raw-project SHA, canonical revision SHA and recording SHA remain distinct.
`result.json` includes private provenance; it is not suitable for public export.
The CLI returns 0 only for `PASS`; HOLD, REFUSE and internal errors return 2.

## Bounds and cleanup

The existing project parser caps submissions at 96,000 rows. Post-load verification
gets exactly `2 * submitted rows * 0.015` wall seconds; startup has a separate
180-second limit. Every matching wait rechecks its deadline after scanning, and
the final budget check includes evidence assessment and owned cleanup. Result
serialization/printing is outside that measured interval.
Timeout/resource/unsupported cases abstain, not accuse the player.

Each native child has a 768 MiB hard address-space cap, zero core size and a
64 MiB producer-side file limit. Explicit 128 MiB SSQC/CSQC and 64 MiB menu VM
arenas avoid Linux's default 2 GiB virtual reservation. Both peers' game and
console logs are monitored during every replay/startup wait. Dynamic output and file count are
bounded; changed static files cannot evade accounting. Hash-listed staged copies,
including native images, share a 2 GiB aggregate cap.

The opt-in `set vid_headless_sleep 0` removes only the headless renderer's sleep;
normal frame limits remain. Its registered default stays 100 ms for other clients.
SIGTERM/SIGINT only notify the running job; safe checkpoints turn requests into HOLD.
The final cancellation-latch read, after assessment, reaping, retirement and budget
checks, is the standalone CLI's logical decision commit. Signals arriving later,
during result serialization/printing, do not revoke that decision. Any future queue
must independently fence cancellation, lease and status at promotion; private JSON
PASS does not override a cancelled queue job. Handlers never throw into stopping
or reaping, including cancellation during cleanup. Constructor, assessment and
timeout failures also reap the job's own peers. Only verified unchanged static copies are retired.
Generated recordings/logs and unexpected or changed files are retained for review.

## Checks and current limits

`python3 -B tools/test_tasverify.py` exercises admission, recording/input joins,
world transitions, runtime assembly, plugin identity, resource bounds and cleanup.
Agent runs set `TAS_TEST_ROOT` to their owned task root. Linux-only controls must
run on Linux; a Windows skip is not qualification of those paths.

Native delivery qualification additionally needs a fresh real finish, an unfinished
line, wrong start approach, changed live-world target and cancellation. Unit grammar
is not native execution. Current qualification covers one real map with private
fixture zones, not a map corpus or production-board acceptance. Native queue,
Steam-linked admission, daily quotas, TAS publication and public credits remain
separate integration work; none may trust uploader-supplied JSON as a receipt.
