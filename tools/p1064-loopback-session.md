# P1064 — desktop visuals while Windows has muted the game

## Problem / fix

The owner reported source1/support1/active1/available1,27416packets,RMS0 while
playing a video. Normal-sound installed client capture remained0 while the same
binary with nosound and standalone output capture were nonzero. A read-only
probe of the owned game PID found volume0/mute1. This narrowed the fault; those
observations alone did not prove the fix.

`VISLB_Open` passed NULL AudioSessionGuid, joining that process's muted rendering
session. Create a fresh capture GUID for Initialize; failures use the existing
close/retry. No render volume/mute override, source opt-in change, microphone,
raw audio, endpoint identity output, evidence/schema change or backend action.
Engine commit/tag: d561b74085c5ee72c9e228d45c8f3c9e9c8b0b31 / patch-1064.

## Acted control and subject

Owned task root C:/FTESurf-worktrees/menu-20261026T1632Z. Native base75abc46df;
QC d3c27821. Predictions were recorded in PLAN-audio-loopback.md before editing.
Existing helper's wrong PCM function name and one shell escaping syntax error
are preserved as infrastructure failures, not product evidence.

- Small Windows-only public test: engine/tools/test_snd_vis_session.c. It mutes
  ONLY its own silent render session. External default-output playback supplies
  positive input. Exit77 = NOT MEASURED when positive input is absent.
- Same public test compiled -Wall -Wextra -Werror against the original production
  header: baseline.005385, independent.009939, old capture67packets/RMS0, exit1.
  Fixed production header: baseline.006796, independent.011199, new capture
  67packets/RMS.006104, exit0. Rendering stays volume0/mute1 in both arms.
- Earlier paired production-header control likewise old66/0 versus new67/.006300;
  positive independent input and unchanged muted rendering were both observed.
- Existing test_snd_vis_loopback.c: PCM/downmix/finite/reset/bounded-silent-ring,
  analyzer/silence/spectrum, Windows capture+close/reset and non-Windows fallback
  pass; both variants compile -Wall -Wextra -Werror.
- Existing build.ps1 -Engine -Full -NoDeploy -Jobs8 with explicit owned FteRoot
  passes client, dedicated and all matched plugins. The first log has79
  warning-containing lines in untouched sources/QC; changed header/test compile
  warning-free under Werror. No unrelated warning repairs. A generated shader
  header differed only in its generator-path comment; restore ONLY that verified
  owned comment change, not shader code or anyone else's files.
- Real normal-sound candidate92882bae59cd: source1 active1 RMS.007916;
  source0 active0 RMS0; source1 reopens active1 RMS.004507. Its two own-PID audio
  sessions were unmuted, so the explicitly muted arm is the production-header
  test, not that native client observation. No owner audio session was changed.
- clangd's cached standalone-header C++/Windows SDK mode reports old lpVtbl errors;
  public C test diagnostics are clean and actual GCC/full-build results above
  are authoritative. No LSP-only build claim.

## Reproduce the focused test

From the engine checkout with the UCRT64 compiler on PATH:

    gcc -std=c99 -O2 -Wall -Wextra -Werror tools/test_snd_vis_session.c -lole32 -luuid -lm -o <owned-output>/session-test.exe
    <owned-output>/session-test.exe

Play desktop audio on the default endpoint. Do not record raw audio or change
other apps' volumes. PRODUCTION_HEADER may select the immutable old header for
the failing control; keep its sibling snd_vis_pcm.h. No input/exit77 must not be
reported as a pass. The test's process exits after its capture/render cleanup.

## Delivery / limits

Native/plugin-only dual Windows delivery completed2026-10-27T11:13:10Z using
the exact inspected build.ps1 Deploy function, without its QC phase. All10
native/plugin destination hashes match the clean d561b7408 build; prior hashes
match retained .prev files. Both client binaries SHA256
17f7ec606877e8c19bedd75546f16faa2f9652b5eb332cf45a137ccbc7aa9e01.

Post-swap own-PID checks completed11:14:27Z. Primary game rendering remained
volume0/mute1 while its independent capture session was volume1/mute0:
active349packets/RMS.016101; source0 closes/RMS0; source1 reopens/RMS.008843.
This is an actual installed native muted-render pass, not just the C helper.
Secondary unmuted rendering:355/.013662, source0/RMS0, reopen/.017234. Only owned
test processes were stopped; original rendering mute/volume stayed unchanged.
Receipt: artifacts/p1064-native/install-receipt.json; numbers/read-only session
probes: artifacts/audio-loopback-control/native-postswap-result.json.

Existing menu/gameplay progs, owner ftesurf.cfg/addon mounts and qcbuild stay
unchanged (hash readback). No surfd, backend gate, NanoPi, release or other
session's processes are touched. Numeric capture/source lifecycle is verified;
the owner subsequently replied "it works!" to the actual backdrop/audio check.
That human confirmation is recorded in lextest.md, not broadened to unrelated
UI/API cases. P1064 was then included in release0.1.32 (tools/release032.md).
