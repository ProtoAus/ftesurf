# P1298: reopen the TAS workshop on its previous tab

## Problem and change

Closing the workshop unconditionally selected Next input, so temporarily closing
Timeline or Shared discarded the view even though their underlying session
continued. Closing now remembers only the tab. It still invalidates in-flight
and displayed timeline pages, releases the TAS cursor claim, and resets widget
actions/tooltips. Reopening Timeline makes an ordinary guarded refresh request;
Shared keeps its existing browser state and consent rules. First open still
uses Next input. `tas menu status` also reports the numeric tab (0 Next input,
1 Timeline, 2 Shared).

No native engine, server protocol, movement, recorder, signatures, ancestry,
public admission or board policy changes. Native pin/tag and qcbuild do not move.

## Verified

- Clean isolated source; actual compiler through `src/build.ps1 -NoDeploy`.
  SSQC and MENU: zero warnings. CSQC: the same two existing F333 viewmodel
  warnings in control and subject, no new warnings.
- Real dedicated Windows socket and rendered client, minimal session-owned
  fixture, actual production programs. The control has only the status observer
  added: both Timeline and Shared reset to Next input on reopening. The subject
  retains Timeline, Shared, then Timeline again.
- Both arms pass 14 checks: first-open/default and actual drawn-frame controls,
  explicit-tab commands, close/released-cursor and reopen/drawn-frame checks,
  empty-timeline non-authority, Shared refusal without accepted online terms,
  and no client VM error. All owned processes stopped. Rendered subject screenshot
  inspected: the timeline panel draws after reopening.

These are small UI/session-state controls, not populated-timeline replay,
physical-device feel, real-account or all-map validation. Owner acceptance is
pending in lextest.md. Destination hashes/live rollout are recorded separately;
a successful build is not evidence of deployment.

## Deployment readback — 4 November 2026, 17:47 UTC

Frozen product source `0fbcc76382f0bdc6aa7905d3e8c950c3fa5665d7` was built
from its clean isolated worktree. The resulting programs exactly match the acted
subject. Both Windows installs received the programs with predecessors preserved;
the native images and 13 sampled protected config/install/native files are unchanged.
The ordinary `build.ps1 -Pi -PiForce` path warned for 10 seconds and restarted all
12 lobbies (three players were connected). Backend services and native binaries
were not replaced.

| Program | SHA256 |
|---|---|
| qwprogs.dat | `52b4c337cbfb83a7e65b96cb55cefcedb7eedcb69f36f651e078753ae49e6feb` |
| csprogs.dat | `517849e503c3e12ebc9af811bba0c4bd9ba579822c859734fb4250bf8c3c8f01` |
| menu.dat (Windows only) | `e69b5f249e0fb09f777c3fc8f8a3e72c846d8b27200923f4795d93219ae3af04` |

All 12 active lobbies report the new `78f388a3` CSQC checksum. A fresh client
with no local CSQC downloaded these exact bytes, rendered the board panel and
captured a screenshot without a VM error. This small fixture has no local zone
rows; it is not populated-board validation. The downloaded client then exercised Timeline
close/reopen on a live lobby: the tab and actual drawn frames persist, and the
cursor releases/reclaims correctly. Its owned process stopped. Owner visual/feel
acceptance remains pending; no public TAS admission was enabled.

## Project recovery

The [status map](tas-status.md) reconciles the original plan with P1077-P1172.
In particular, native 10 ms authoring already exists, while public submission
and a verified TAS board remain unfinished. The old setup failure must be
rechecked against the current environment rather than treated as a permanent
permission blocker. No public endpoint is enabled by this UI patch.
