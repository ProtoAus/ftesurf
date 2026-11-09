# P1452 — Windows input observation and restart safety

## Delivered scope

The native client distinguishes successful keyboard observation from enumeration.
Existing observation can start before an opt-in grab; a refused mode replacement
retains the last known binding and its serviceable buffer/device cohort. The input
owner acknowledges exclusion across the complete teardown/rebuild transaction.
Late or reentrant reads cannot resurrect a bare buffer and bypass initialization.
Ordinary keyboard removal does not pause mouse reads or double-translate a key.

Known registration mode is separate from effective observation availability.
Exclusion abandons pending pairing without counting it and publishes interrupted
coverage through existing availability/change fields, including stop/start changes
coalesced between journal samples. The unchanged reader withholds whole-journal
legacy totals whenever that interruption is recorded.

No new capture/privacy field, input blocking, threshold, ranking, detector
promotion or human-input attestation. The channel is for balanced internal
operations, not sender authentication. A raw/legacy pair split across resumption
can still produce a partial processing-time uncorrelated decision; queued-message
grace and genuine-HID calibration remain pending. These counts are not
false-positive-free proof of physical origin or automation.

## Source and verification

- Native `patch-1452`, commit `0ec891507bd3e9fcdd3823f1b60870381dbf1e69`,
  published to engine main. It includes published P1451/P1453/P1454; the late
  P1452 claim does not lower cumulative feature patch1454 or change QC Build89.
- Final normal `build.ps1 -Engine -Full -Jobs 8 -NoDeploy` passed on the clean
  frozen source. Stamp: `git-8591-patch-1452-0-g0ec891507` (not dirty).
  Same frozen compiler/dependency cohort, 1,041 dependency files rehashed;
  contemporary control: 76 existing warnings, subject: 76, **zero new warnings**
  and zero errors. Initial dependency/compiler/setup failures remain retained,
  not retrospectively relabeled successes.
- Literal production lifecycle/Read/pairing and producer controls retain acting
  make/break identity, ownership, refusal, allocation and mouse positives.
  Rejected draft / unsafe cleanup / null-only / coverage-preimage negatives fail
  15 / 8 / 4 / 16 assertions; corrected and real registration-success arms pass.
  Refusal, enumeration, allocation and raw delivery dependencies are modeled,
  not physical-HID qualification. Fresh independent source/evidence reviews
  clear the explicitly bounded correction.
- Source-bound producer records reach the actual unchanged reader: sampled and
  coalesced interruptions are partial, unlike discriminating false whole-count
  and whole-zero preimages. Six envelopes parse without faults.
- Final actual isolated NoMap clients, queried `vid_winthread 0` and `1`: all six
  journals parse without faults. Quiet has legacy count zero; posted input has
  six privacy-hidden `x` events and two uncorrelated decisions. Restart keeps
  twelve posted `x` events, emits interruption, and has **no whole legacy total**
  in either mode. There are no `+` gameplay records. These are not gameplay,
  genuine-HID, latency or detector-accuracy tests.
- Existing recorder/reader regressions remain 949 / HID 314; the pinned 767-file
  same-buffer corpus has no new fault. No reader/evidence-schema change here.

## Windows deployment

Client EXEs only installed to both documented destinations, using the existing
`build.ps1` Deploy function and `.prev` preservation. Exact preceding EXEs and
previous `.prev` files are also retained in private rollback evidence. Process
preflight refusals made no install changes; no owner/foreign process was stopped.

- `C:\FTESurf\ftesurf64.exe`
- `C:\FTEQuake\fteqw64.exe`
- Qualified and both destination SHA-256:
  `b72fc3930875457d263033c49dfd58cb69fcf78bf1f1823ea3f8d505b2bd4200`
- Installed and actual installed-path verification completed 2026-11-09
  **10:46:56 UTC**: both destination executables launched as owned isolated-data
  clients and exited zero; six additional actual journals parse without faults.
  Both retain acting posted-count and restart-partial behavior. Destination and
  `.prev` hashes were rechecked afterward; hash equality is not the sole proof.

No server, plugin, progs, config or player-data files were promoted. Header changes
are client-local input enums, not a plugin/server ABI change. No public release
was made. Physical keyboard/play acceptance in `lextest.md` remains pending.

## Independent backend lane

`tools/backend-pending.md` queues P1447 viewer and P1448 Fetch together for the
NEXT guarded backend update, including their Python/web/cron cohort and optional-
table rollback/CURRENT-data checks. All four paired prerequisite test groups
passed. The next closure adds Fetch's worker to the fixed admission profile;
that profile extension/staging/activation is not implied by this native delivery.
The healthy admitted P1434 backend was not replayed, rolled back or replaced.
Native-only deployment does not promote the held game-side P1447/P1448 progs.
