# TAS project: current status and continuation

Status reconciled 6 November 2026 UTC. Start with
[the full plan](plan-tas.md); this page summarizes delivery, not a replacement
for its acceptance criteria. There is no honest single completion percentage:
the local authoring loop is substantially delivered, while contact-aware section
work and the public ranked-submission path remain unfinished.

**Owner feedback, 4 Nov:** the old workshop was too low-level for practical
surf-line authoring. Lex approved the [human-first redesign](plan-tas-human-workflow.md)
and added crouched strafing and optional vertical look following travel. This
was design approval, not whole-editor usability or numeric physics acceptance.
The controller, full captured local-line editing and literal input templates
subsequently shipped; P1329 historical settings are now installed too. Owner
camera/input feel remains pending in [lextest.md](../lextest.md).

## Implemented and delivered

| Area | Delivered scope | Important limit / reference |
|---|---|---|
| Practice controls | Slow motion, explicit TAS ancestry, pause/play and exact bounded tick advance | Assisted material stays out of human boards; P1052/P1055 |
| Rewind and input editing | Retained-tick rewind, range edits and affected-tail replay | Warm/history and current-world limits; P1061/P1065 |
| Workshop and timeline | Next-input UI, directional air assist, retained input table, undo/redo | Not a full arbitrary-world editor; P1074/P1077 |
| Projects | Saved revisions, named checkpoints, diff, legal-start portable v3 projects | Base-save and portable projects remain distinct; P1082/P1089/P1110 |
| Comparison and optimization | Comparison ghost/deltas; bounded turn-rate, boarding-angle, flick and next-segment-time searches | No arbitrary route/collision-aware or globally fastest solver; P1087/P1088/P1092/P1097 |
| Collaboration | Content hashes, signed revisions, contributor history, explicit share/browse/open | Signing is authorship evidence, not a verified finish; P1090/P1091/P1140 |
| Native clock/cold loading | Bounded 10 ms and 15 ms authoring, plus fresh-session project admission | Not full all-map/world qualification; [P1154](p1154-tas-clocks.md), [P1161](tas-cold-p1161.md) |
| Editor reopen | Keeps the last workshop tab, without stale timeline authority | Client-only; [P1298](p1298-tas-reopen.md) |
| Human-first local controller | Normal play → Pause; independent movement, yaw/gain and duck controls; optional Follow travel pitch | Owner feel and broader ramp/ground cases still need acceptance; [human plan](plan-tas-human-workflow.md) |
| Full captured local line | Browse/seek/recalculate retained earlier inputs, preview and recover the original; named literal templates | Captured native-base projects, bounded input capacity; not position-only or arbitrary streamed imports; [P1323](p1323-tas-recipes.md) |
| Historical local settings | Completed-tick movement/turn/duck/Follow settings restore on seek, survive closed-panel save/reload and history operations | Local v4 only; missing/legacy intent stays unknown, not guessed; [P1329](p1329-tas-settings.md) |
| Server replay foundation | Operator-only bounded legal-start verifier | Qualified 15 ms fixture profile, not public admission; [runner contract](tasverify.md) |
| Canonical-content foundation | Native VFS source inventory, epoch/lease and binding checks | Components, not complete production source qualification; [source contract](tas-native-source.md) |

P1329's qualified program bytes are installed in **both Windows copies and all
12 lobbies**. Destination/predecessor hashes, current native/config preservation,
complete recorder/resume preimages and new lobby epochs were checked. An
installed-byte dedicated-socket smoke also passed. The original rollout-caller
SSH timeout is retained; the on-box activation succeeded and was reconciled
read-only, without repeating swaps/restarts. See the qualification for scope.
This is deployment evidence, not owner usability or genuine-device signing.

### Implemented manual sections, pending delivery

[P1335](p1335-tas-sections.md) adds a full-retained-line Sections tab with manual
endpoint naming, input-range selection and bound start/end navigation. Add,
rename, move-to-current-body and remove save the complete raw/settings line even
while paused earlier. Original revisions, no-input-supply semantics and the
ordinary partial-save guard remain. A conservative cumulative byte budget now
refuses oversized synchronous marker saves intact; storage/browser limits remain
unchanged. Actual old48000-row control18 exhausts the VM AFTER read/load/browser
baseline; corrected22 safely refuses, stays responsive and saves a short edit on
that same server. Corrected metadata58 and16synthetic budget-helper checks pass;
earlier widgets31/panel inspection remain separate evidence. Final re-review,
publication and BOTH-Windows/lobby delivery are pending. This is the manual foundation, not contact detection
or best-found solving; P1329 remains the current installed authoring feature.

The API reader upgrade is reviewed/tested/published but still needs the owner's
root-authenticated standalone TAS-service upgrade. This does **not** block local
editing: normal in-game sharing explicitly accepts only legal-start v3 projects,
not local v4 base files. Keep that guard. The upgrade does not itself make v4
projects portable, enable public verification or grant input credit from settings.
The existing v3 sharing path and its newly registered shipped client remain usable.

Earlier dated stage paragraphs in the original plan keep their historical scope.
A statement that a later stage was then unbuilt is not today's overall status.
Source, qualification, deployment and human acceptance are separate evidence.

## Still unfinished

1. **Human-plan phase 4: contact-aware sections.** P1335's manual browser and
   marker workflow is implemented/isolated-qualified, with review/delivery still
   pending above. Actual-contact ramp proposals remain unimplemented. Keep manual
   boundaries explicit; do not label a ramp merely from `FL_ONGROUND`, proximity
   or speed.
2. **Human-plan phase 5: constrained section/next-ramp solving.** Existing bounded
   optimizers are not this feature. Real ramp/air candidates must satisfy contact
   and arrival constraints, reject a fast missed ramp, preserve the original on
   cancel/failure, and label results best **found**, not globally fastest.
3. **Stage 6.3: public submission and verified TAS board writer.** The approved
   runtime registry needs protected canonical sources, complete effective
   map/zone/dependency identities, alias/writer controls and real-map replay
   qualification. Queue work exists on a held development branch; recover and
   compare it with current main rather than inventing another queue. It is not a
   deployed public-submission service.
4. **Stage 6.4: public TAS board/filter and contributor presentation.** Enable
   only after service-derived finish/time and TAS-only admission are qualified.
   Human and segmented admission must remain unchanged.
5. **Owner acceptance.** Camera/input comfort, crouch/ramp feel, signing/account
   workflow and broader real-map cases remain unconfirmed. Reported ~275 versus
   expected ~289 ground speed is an owner observation, not a measured regression
   or maximum. Record actual observations in [lextest.md](../lextest.md).

## Resume here

Finish P1335 manual-section review/delivery, then continue the
[human-first plan](plan-tas-human-workflow.md) with actual-contact proposals and
constrained next-ramp work. Keep the delivered play/pause/full-captured-line/settings loop intact.
A rearranged128-tick demonstration, one passing build or this deployment is not
whole-project completion. Dynamic-world, streamed-history, physical-device and
general-route limits remain explicit.

When returning to 6.3, inspect today's source/service/mount state rather than old
failed-setup assumptions. Recheck capabilities at the actual boundary; capability
availability alone is not source qualification. Preserve the held queue and
original failures/history. Public acceptance stays disabled until qualified.

Use `tas menu` for the controller, `tas timeline` for retained inputs,
`tas project ...` for project operations and `tas shared` for portable projects.
These remain assisted practice tools, not a ranked TAS submission verdict.
