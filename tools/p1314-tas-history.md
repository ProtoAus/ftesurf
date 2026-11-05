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
Keep writes a child only after verifying its hash-addressed retention. Eight
undo/redo pairs retain revisions. A no-change freeze reuses its immutable identity,
including at an earlier body cursor; it does not save away the retained future or
insert a hidden parent between history endpoints. A genuinely new captured
baseline explicitly detaches incompatible history, without deleting revisions.

Interrupted execution detaches append/progress, not ownership of the unchanged
native recovery base. Original/target handles survive failed or cancelled replays.
Discard and history cursor changes settle after actual replay completion, not
placement admission; a failed retained operation keeps its exact retry target.
Stopped previews cannot be Kept or labelled complete. Partial seeks have their own
result and claim only visited checkpoints, not full-run reproduction. The preview
hint does not present packet/carry timing differences as route-time improvements.

The advanced project/checkpoint/sign/legacy solver tools have their own Project
tab; Shared retains its existing tab index. Cold or expired native state,
unsupported recording/context, remote authority and shared-world changes must not
be represented as an exact native seek. Initial capture is buffered REC13/14 only,
not REC15 or streamed REC14. Shared world state is not rewound. Human input whose
authoring recipe was not retained is labelled recorded input/recipe unknown, not
inferred from the current draft.

## Evidence so far - explicit limits

Initial predecessor-source short-fixture evidence and its original failures are
retained. The published P1310/P1312 code was then integrated and a fresh FULL
Windows native build at f1fe93dd7d5c7754bb8a148e736cf685075694c2 / patch-1314
succeeded through the existing NoDeploy entrypoint: all three QC VMs zero warnings;
74 pre-existing native warning lines, no new native warnings. The native binary
embeds the tag, and its actual pm_selftest command subsequently acted and reported
all checks passed through the existing guarded/ready console bridge. Unsupported
standalone GUI-PE/console-wrapper attempts are retained, not test passes.

The fresh paired native/QC fixture passed an extended sequence of 91 individual
acting/preservation checks before its final observer combined two rate-gated
commands and missed Pause. Those completed checks include a real archive-create
ACL denial, failed Keep retaining preview/history, exact ACL restoration, retry
of the SAME candidate hash, two successive Undo and Redo operations, Discard
without a hidden identity hop, branching without deleting old revisions, nine
commits bounded to eight pairs, and all eight retained Undo operations. Its
original overall failure receipt remains FAILED; the observer was corrected,
not the failed observation regraded or the passed history cases rerun blindly.

A separate cancellation arm passed 36 checks: the candidate had ACTUALLY consumed
native grants but had not completed; Play aborted it; re-pausing exposed a stopped
preview, Keep refused it, and Discard replayed its unchanged original natively.
The original archive and history counts survived. The first observer's rejected
Keep required a fresh page binding before Discard; that failure is also retained.

The subsequent partial-cursor arm passed 35 checks, including no-edit exact
checkpoint/grant/byte controls, physically different yaw preview, Keep/Discard/
Undo/Redo, explicit partial seek, preview FROM that earlier body cursor without
losing the future, exact Discard, Replay head and resumed TAS ancestry with no
queued work. Actual screenshots were read; the controls fit their panel.
Reader suite: 949 checks, zero failures. Paired current RUNS selector: 544 inputs,
351 fault reports in BOTH published-parent reader and candidate, identical
findings and stable input/sidecar bytes; no increase. Existing faults are not
relabelled clean, and SAVES was not read or repaired by that sweep.

Project integration corrections use named tab constants for entry, drawing and
device-press dispatch. Timeline and Project share the pending-page pump; entering
or reopening Project requests its own current paused-body binding without needing
a Timeline visit. A partial seek also displays any divergence already observed in
its visited prefix, with a distinct result line instead of claiming reproduction.
A fresh socket fixture completed 13 controls, including direct Project entry,
actual Checkpoint creation, throttled close/reopen and another Checkpoint, plus
an empty non-device Sign probe. Its overall receipt remains FAILED because the
new external expected-state fixture was not yet visible to the engine VFS. Two
earlier observer failures (unready widgets and a rate-gated list query) are also
retained, not upgraded to passes. After the existing server fs_flush acknowledged
the new owned test file, a separate 11-control arm passed: deliberate checkpoint
mismatch, stop before full head, partial result with nonzero deviation, explicit
visited-prefix DIVERGED/not-full diagnostic, read actual Project pixels, unchanged
original project bytes. No whole-transaction pass is inferred from partial arms.
The real-device hosted Sign/retained-statement positive check is still pending
with the owner; scripted GUI events and the empty probe do not attest it.

These are short, buffered15ms local fixtures, NOT long/warm-ring/cold/all-recipe/
arbitrary-world/numerical-timing or owner-feel acceptance. Straight-ahead long
fixture attempts restarted; attempted gravity overrides did not change the
recorded profile. No such attempt is a long-history pass. Two initial independent
reviews found the history/recovery/retention/partial-result issues above; corrected
source needs fresh independent review. The subsequently published P1313 retry
policy and native journal are retained; its native change is documentation-only,
so no native code dependency of the qualified f1fe93dd binary changed. The merged
QC still requires a clean build/relevant runtime recheck. Exact-source delivery
and the full remaining project stay in scope. No deployed or full-project
completion claim. QC Build 89 remains unchanged.
