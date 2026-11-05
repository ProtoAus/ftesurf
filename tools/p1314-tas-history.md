# P1314 - captured local input-line editing

## Component, not completion of the full project

This adds the play/pause/captured-input/preview/keep-or-discard foundation to the
human-first TAS workflow. The whole project in plan-tas-human-workflow.md remains
in progress: durable historical recipes, contact-aware sections, the constrained
next-ramp optimizer and broader end-to-end acceptance are NOT supplied by the
legacy 32-tick exit-speed search.

Ordinary capture retains one exact native state per eligible local recording
without granting movement, changing its input or marking the attempt TAS. Explicit
Pause establishes assistance. The supported buffered recording supplies the full
captured input line; browsing and the separate current-body cursor do not shrink
that line to a native 128-tick execution chunk. The existing project driver still
executes bounded chunks.

The editor binds actions to the recording, actual current body and request. A
file-hash-bound, same-session native base is probed before historical placement.
The explicitly selected immutable saved pair supplies its recorder prefix; a
stale live-ring prefix mark is not treated as authority after a cut, nor are the
existing rewind prefix checks weakened. Preview preserves its frozen original;
Keep writes a child, Discard restores it, and eight hash-bound undo/redo pairs
retain revisions. The advanced project/checkpoint/sign/legacy solver tools have
their own Project tab; Shared retains its existing tab index.

Cold or expired native state, unsupported recording/context, remote authority
and shared-world changes must not be represented as an exact native seek.
Initial capture is buffered REC13/14 only, not REC15 or streamed REC14. Shared
world state is not rewound. Human input whose authoring recipe was not retained
is labelled recorded input/recipe unknown, not inferred from the current draft.

## Evidence so far - explicit limits

A matched predecessor-source Windows dedicated localhost fixture passed thirty
actual checks: ordinary Forward starts an unassisted recording, explicit Pause
marks TAS without synthetic grants, an unchanged full native replay matches all
stored body/velocity checkpoints, and the original file bytes remain exact. A
first-input yaw change actually changes the native trajectory; Discard, Keep,
Undo and Redo act on real rows and preserve the immutable original. Seeking to
body tick zero retains the full future extent; Replay head executes it; Play
leaves no queued synthetic work and does not clear TAS ancestry. Actual GUI
screenshots were read. All three QC VMs compiled with zero warnings.

The tested short fixture is NOT proof of long history, warm-ring expiry, cold
restoration, all recipes, arbitrary worlds, numerical timing or fleet deployment.
Long straight-ahead fixture attempts restarted; attempted gravity overrides did
not change the recorded profile. An unsupported camera command and a completion-
page/navigation race were preserved as failures, not promoted to passes. Client
page requests now coalesce under the existing rate limit instead of dropping a
navigation click. A side-input edit that changed commands but not trajectory is
not used as the physics actuation proof; the yaw edit supplies that control.

These receipts predate integration of the published P1310/P1312 observer-only
commits. Owned source bytes were restored exactly after fast-forwarding those
commits, but their old binary is NOT a build of the integrated source. Fresh full
native/QC build, source/evidence reviews, reader/corpus preservation and exact-
source delivery are pending. This document makes no deployed/current-build or
full-project completion claim. QC Build 89 remains unchanged.
