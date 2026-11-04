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

## Project recovery

The [status map](tas-status.md) reconciles the original plan with P1077-P1172.
In particular, native 10 ms authoring already exists, while public submission
and a verified TAS board remain unfinished. The old setup failure must be
rechecked against the current environment rather than treated as a permanent
permission blocker. No public endpoint is enabled by this UI patch.
