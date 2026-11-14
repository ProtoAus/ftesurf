# P1564 - TAS boards and completed-run history

## Implemented

- The scoreboard has a separate **TAS** community leaderboard, plus a TAS
  filter on **Local**. TAS never enters ordinary ranked boards, ordinary PBs,
  points or native certification. Whole-run and stage/bonus selection remain
  separate, as do movement profiles.
- Completed ordinary, segmented and TAS recordings receive unique history
  names, including slower completions. PB/last slots remain compatibility
  pointers; replacing one does not remove its retained history copy. History
  copies are excluded from ordinary quota pruning.
- While connected, the client automatically acquires its own completed
  recordings for the current map's published legs through the existing
  authenticated archive protocol. This neither opens a replay nor changes
  optional raw-input sharing. Local history is paged and filterable; header
  indexing is frame-budgeted and drawing uses cached metadata.
- TAS playback uses recorded mover angles from REC, not the live mouse-camera
  VIEW track. This is a replay presentation choice, not native attribution.
- Eligible renderer sidecars use an attachment/run/finish/nonce/map/profile
  binding. A real confirmed final filename is retained before the existing
  signer runs. Missing run IDs, stale attachments and incomplete/cold captures
  are not guessed into complete VIEW files or retrospective signatures.
- Archive header eligibility covers known REC schemas 4-15. Copies retain the
  original bytes, including native headers longer than QC's line-string limit.
  Ownership, path/content seals, sequencing and digest checks remain mandatory.

Default Source recordings are under `ftesurf/data/runs/<map>/<leg>/`;
experimental profiles use
`ftesurf/data/experimental/<profile>/runs/<map>/<leg>/`.
Do not rename/delete player files to exercise the feature.

## Finding the runs

Open the scoreboard and choose **Local**, then **All**, **Segmented** or **TAS**.
The **TAS** tab is the online community board, not another ordinary ranked tier.
Console equivalents include:

```
scores tab local
scores filter tas
scores history next
scores history prev
scores history sync
scores history status
scores tab tas
```

The online TAS tab requires the matching backend generation. An older backend
rejects the unknown TAS style rather than returning an ordinary board.

## Verified

- All three integrated VMs compile with zero warnings, retaining the published
  P1559-P1563 fixes and optional P1565 angle-context changes.
- A real dedicated-socket native fixture completed two ordinary attempts, a
  save-resumed segmented attempt and two actual TAS attempts. All five distinct
  recordings remained on the server; the prior three bodies stayed unchanged.
  Real account proof and automatic owner downloads acted, and client/server
  recording bytes matched. The native headers included a 1,063-byte line.
- The TAS-only completion check requires a finish-specific suffix, not the
  earlier "TAS mode enabled" announcement. The first test's premature TAS
  observations are not credited as completions; its ordinary/segmented and
  camera observations remain separate valid evidence.
- The recorded TAS camera fixture loads the old VIEW cache under the control;
  the candidate explicitly selects REC presentation and loads no VIEW rows.
  This does not claim a human visual pass on the owner's original clip.
- `python tools/test_reccheck.py`: 952 checks, zero failures. A same-byte sweep
  of 578 REC and 184 VIEW files found 365 faults under both the published
  integrated base and this reader: zero new faults, not a fault-free corpus.
- Independent final source/acceptance review found no remaining source blocker.
  These are lifecycle/classification/copying/presentation checks, not physics,
  performance or native-certification measurements. Runtime completion samples
  were REC14; REC15 eligibility is source-verified here.

The backend lane separately passed four focused `surfd/test_tas.py` tests:
ordinary/segmented isolation, no points or per-player/global ranked leakage,
public-web replay gating, native community replay access and submission-key
rejection. Existing `test_web.py`, `test_board.py`, JS syntax and focused TAS
DOM controls pass. The unrelated pre-existing `test_ranked.py` template failure
was preserved, not repaired or called a pass.

## Explicit limits and delivery

- The existing authenticated Archive **8 MiB per-file limit** remains a safety
  boundary. Larger server originals are retained, but are not automatically
  copied to a remote client's local history. Removing the limit without a
  bounded streaming/digest design would permit unbounded QC allocation.
- Cold restoration without a real run ID cannot receive a guessed VIEW pair;
  late confirmation does not invent a signature. No evidence format, input
  ancestry, detector, sharing-consent or certification rule is relaxed.
- Owner visual/menu confirmation is pending in `lextest.md`.
- Source, tests and review are not deployment evidence. The QC delivery receipt
  will identify the inspected commit, both Windows destinations, fleet hashes
  and UTC separately. The backend requires its existing guarded-generation
  procedure; do not copy this source into a serving immutable generation or
  use a generic reload to bypass it. See
  [the generation procedure](surfd-generation-p996.md).

No native build, engine tag/pin change, release or QC Build-number decision is
part of this QC completion. Published peer engine metadata is preserved.
