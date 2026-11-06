# P1335: manual sections for the complete local TAS line

Status: implemented and qualified in an isolated real dedicated game; final
review, publication and deployment are pending. This is the manual foundation
of human-plan phase 4, not automatic ramp detection or section solving.

## Use

1. Play the supported local run normally, then `tas pause` and open `tas menu`.
2. Choose **Sections**. Without named markers, the complete retained line is one
   section. The panel pages four intervals at a time and shows the actual paused
   body separately from the retained end.
3. Type a marker name and **Add here**. A marker uses the current supported paused
   body, not a sampled ghost or arbitrary position. Names use 1..32 lowercase
   letters, digits, underscore or hyphen. The base is already the implicit start;
   two named endpoints cannot occupy the same tick.
4. **Go to start/end** uses the existing bound seek/replay. **Inputs** only selects
   that interval's input range and opens Timeline; selection grants no movement.
   Completed body interval [a,b] corresponds to input rows [a+1,b].
5. **Marker** chooses a named endpoint and fills its name draft. Edit the draft
   and press **Rename**, or press **Remove** to merge adjacent intervals. To move
   a boundary, first seek to the desired body, then choose the existing endpoint
   and press **Move here**. Navigation and paging clear endpoint selection, so a
   stale highlight cannot move a different marker.
6. Marker edits automatically save the full retained input line, including later
   inputs while paused earlier. The ordinary Project partial-save refusal stays
   intact; do not use its force option for this workflow. Timeline Undo/Redo uses
   explicit revision replay, including the corresponding end-of-line body; it is
   not a hidden pose change attached to typing a label.

Console equivalents: `tas sections`; `tas sections next` / `previous`;
`tas sections name example`; `tas sections add`; `choose`, `rename`, `remove` or
`move` followed by the section number on the current page. `select`, `start` and
`end` take that same section number. The native body still must meet all normal
local-editor requirements; these are not authority or recovery bypasses.

## Implementation and bounds

Manual checkpoint endpoints delimit sections across the complete retained
project, not the 128-tick native execution window. An endpoint at the retained
head produces no empty trailing section. The existing 48-checkpoint storage cap
and project input cap remain; pages contain at most four rows.

Page data is a view bound to its request tag, record serial, actual body tick,
request, retained extent, revision hash and checkpoint count. Mutations also bind
an existing endpoint's name/tick and the current revision. They require a complete
unchanged local input baseline, retain the original immutable revision, and use
the existing typed temp/read-back/rename writer. New or moved marker poses come
only from the supported live paused body. Future stored checkpoints are retained;
removing the retained-end name keeps its real end snapshot.

A marker child changes checkpoint/name metadata, preserves full raw input and
optional authored settings, and declares no supplied input. Metadata grants no
body, native execution, signing, eligibility or input credit. The ordinary
historical input-save guard and local-v4/portable-v3 sharing distinction remain.
An undo branch may replace only the same writer's known immutable history, not
an unrelated newer named revision. A failed write restores the previous RAM
marker map and keeps the immutable original; the existing writer's retained
complete-stage recovery on final rename errors is unchanged.

The existing single scan-ownership/repeat/release editor handles both name fields
with separate drafts/carets. Tab changes blur focus without clearing held-key
ownership. Native key releases remain forwarded. The original recipe widget and
save path remain available. No native C, movement, evidence format, engine pin,
tag, QC Build, backend API or public admission policy changes.

## Verification

- All three actual QC VMs compile with zero new warnings.
- Acting old dedicated control:14 checks, including supported normal capture,
  five real saved endpoints and explicit refusal of the new page verb.
- Initial new browser:20 checks for complete/no-name intervals, four-row and final
  short pages, exact input selection without a grant, earlier-body navigation
  retaining future intervals, original bytes and explicit stale/invalid refusal.
- Real dedicated metadata workflow:58 checks. Historical add, rename, move and
  remove preserve the complete raw input/settings line; exact parent and no
  supplied input are checked by the existing independent Python parser. Existing
  partial-save protection acts. An owned blocked staging fixture makes the typed
  writer fail, restoring RAM names and preserving saved bytes. The fixture is
  removed and the successful retry acts. Retained-end naming/removal, stale-node
  refusal, explicit Undo/Redo and a branch after undo preserve original/newer
  immutable revisions. No marker action grants a native tick or changes its
  body/request binding; explicit navigation/history replay is separate.
- Actual new widgets:31 checks. Marker field typing, Add/Rename/Remove buttons,
  native held-key handoff between gameplay/Sections/Project, native releases,
  independent recipe field/save, marker-draft retention and fault-free mover.
  The captured panel was inspected for readable controls, bounded rows and no
  clipping; this is not owner appearance/feel acceptance.
- Each actual dedicated pair quits normally with code0. The supplied states are
  isolated fixtures, not proof of arbitrary maps, genuine devices or signatures.
- Mandatory recorder tests:949 checks, zero failures. Required primary runs/parts
  sweep:548 recordings/parts and178 views, existing faulty-entry count remains351
  on unchanged bytes. Ten additional views are actually parsed clean; all726
  inventory members remain unchanged. This is no increase, not a clean corpus. The separate broader legacy kept-save
  prefix denial remains unchanged and unclaimed; no data or ACL was repaired.
- Strict canonical read-back caught a missing internal name-list terminator in
  the first producer. The producer was fixed, not the validator. Reader refusal
  now identifies its line number without relaxing the format.

## Still in scope, not claimed complete

Actual-contact ramp boundary proposals, confidence/manual overrides, constrained
next-ramp best-FOUND solving and the original public TAS submission/board stages
remain unfinished. Local v4 files are still not portable v3 submissions. Owner
camera/input comfort, real-world crouch/ramp feel and genuine-device signing
remain pending human acceptance. A useful local section browser is not the whole
TAS project's completion.
