# P1336: manual sections for the complete local TAS line

Status: implemented, isolated-qualified and cleared by two final independent
whole-feature reviews. Publication/deployment are pending. Qualification used
provisional P1335; the feature was renumbered before publication to avoid an
existing reservation, with no runtime source change. This is the manual
foundation of human-plan phase 4, not automatic ramp detection or section solving.

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
request, retained extent, revision hash and checkpoint count. Refresh asks for the
authoritative project metadata first, including unsaved legacy checkpoint edits. Mutations also bind
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
complete-stage recovery on final rename errors is unchanged. A successful marker
write synchronizes its emitted local parent name and recomputes made/signed
indicators for the new hash before publishing it, not from the parent revision.

The existing single scan-ownership/repeat/release editor handles both name fields
with separate drafts/carets. Tab changes blur focus without clearing held-key
ownership. Native key releases remain forwarded. The original recipe widget and
save path remain available. No native C, movement, evidence format, engine pin,
tag, QC Build, backend API or public admission policy changes.

### Synchronous save limit

The 96000-input storage/browser limit is unchanged, but a marker edit is not an
unbounded bulk rewrite. A marker transaction preflights the named and immutable
file sizes and reserves two projected child reads. Every nested strict read then
charges its actual opened-stream bytes against a conservative 1440000-byte
cumulative allowance, including authored settings and long tokens. Extra branch
or repair reads consume the same allowance; stage/child reserve is rechecked
before RAM checkpoint staging. Zero remaining never disables the limiter.
Ordinary non-marker reading is unchanged, and every marker exit clears the scope.

An oversized edit explicitly refuses with the original retained; it does not
truncate the line or raise the VM limit. Unsaved input/settings changes must be
saved or reverted first, so Freeze cannot insert an implicit save into the
transaction. This intentionally means some long, otherwise readable projects
cannot yet have their marker metadata rewritten synchronously. Bounded staged
bulk editing is not claimed complete.

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
- Independent whole-feature review found three consistency bugs, corrected before
  rollout. An actual old-code control24 reproduces Refresh stuck after an unsaved
  checkpoint and loss of the marker-emitted local parent on a following ordinary
  save. Corrected dedicated subject24 recovers with ordinary Refresh and keeps
  the exact parent pair, full raw/settings rows, immutable original and paused
  body/grant counters. Both normal dedicated pairs quit with code0.
- Literal production success-tail VM checks: five relevant old assertions fail
  while an unchanged hash/head invariant passes; all six corrected assertions
  pass. Explicitly synthetic helper results verify parent-name/event ordering and
  per-child made/signed flags in both directions. No made/signature file is
  fabricated, no genuine-device signing is claimed. These minimal VM fixtures
  complete function checks but require stopping only their own spawned processes
  after the quit deadline during later map setup (exit1), not a normal game pass.
  Actual dedicated workflow acceptance comes from the separate normal pairs.
- A further whole-feature review found the repeated-read VM-budget risk. An
  actual old-code control18 first strictly reads, natively loads a real captured
  checkpoint and browses a 48000-row local authored plan; its marker command then
  causes a recorded VM runaway and only its owned test server exits1. The plan's
  future is explicitly authored, not captured/device evidence; no fake future
  pose or signature is supplied. Corrected actual22 safely refuses before named/
  immutable bytes, RAM names or body/grants change, remains responsive, then
  accepts a short marker on the SAME live server. Normal exit0 both processes.
  Corrected metadata58 rerun covers typed failure/rollback and own history branch.
- Sixteen literal production budget-helper checks pass with synthetic file sizes:
  exact/over boundary, optional branch, different named/original size, missing
  original, settings bytes, negative size, zero remaining and default scope-off.
  This is helper evidence only; its own minimal fixture is stopped after the
  later map-setup quit deadline, not a normal world/device acceptance claim.
- Earlier full dedicated pairs and corrected22/58 quit normally with code0; the
  explicit old runaway control is the exception above. Supplied states do not
  prove arbitrary maps, genuine devices/signatures. Two final independent
  whole-feature reviews of the corrected qualified code report no findings;
  publication/deployment remain pending.
- Mandatory recorder tests:949 checks, zero failures. Required primary runs/parts
  sweep:548 recordings/parts and178 views, existing faulty-entry count remains351
  on unchanged bytes. Ten additional views are actually parsed clean; all726
  inventory members remain unchanged. This is no increase, not a clean corpus.
  The separate broader legacy kept-save prefix denial remains unchanged and
  unclaimed; no data or ACL was repaired.
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
