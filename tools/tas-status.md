# TAS project: current status and continuation

Status reconciled 4 November 2026. Start with [the full plan](plan-tas.md);
this page summarizes delivery rather than replacing the original acceptance criteria.
There is no single honest completion percentage: a useful local editor exists,
but its public ranked-submission path is not qualified.

**Owner feedback, 4 Nov:** the existing editor is too low-level for practical
surf-line authoring. Directional movement, air assistance and stepping were
useful, but this is NOT human usability acceptance. The requested redesign is
[planned here](plan-tas-human-workflow.md); it is not implemented or deployed.
Lex subsequently approved that design direction and added crouched strafing and
optional vertical look following travel, independent of the main yaw control.
This is plan approval only; crouch movement and camera feel remain to validate.

## Implemented

| Area | Delivered scope | Important limit / reference |
|---|---|---|
| Practice controls | Slow motion, explicit TAS ancestry, pause/play and exact bounded tick advance | Assisted material stays out of human boards; P1052/P1055 |
| Rewind and input editing | Retained-tick rewind, range edits and affected-tail replay | Warm/history and current-world limits; P1061/P1065 |
| Workshop and timeline | Next-input UI, directional air assist, retained input table, undo/redo | Not a full arbitrary-world editor; P1074/P1077 |
| Projects | Saved revisions, named checkpoints, diff, legal-start portable v3 projects | Base-save and portable projects are distinct; P1082/P1089/P1110 |
| Comparison and optimization | Comparison ghost/deltas; bounded turn-rate, boarding-angle, flick and next-segment-time searches | No arbitrary route/collision-aware or globally fastest solver; P1087/P1088/P1092/P1097 |
| Collaboration | Content hashes, signed revisions, contributor history, explicit share/browse/open | Signing is authorship evidence, not a verified finish; P1090/P1091/P1140 |
| Native clock/cold loading | Bounded 10 ms and 15 ms authoring, plus fresh-session project admission | Not full all-map/world qualification; [P1154](p1154-tas-clocks.md), [P1161](tas-cold-p1161.md) |
| Editor reopen | Keeps the last workshop tab, without keeping stale timeline authority | Client-only; [P1298](p1298-tas-reopen.md) |
| Server replay foundation | Operator-only bounded legal-start verifier | Qualified 15 ms fixture profile, not public admission; [runner contract](tasverify.md) |
| Canonical-content foundation | Native VFS source inventory, epoch/lease and binding checks | Components, not complete production source qualification; [source contract](tas-native-source.md) |

Earlier stage paragraphs in the full plan retain their dated scope limits; a
statement that a later stage was then unbuilt is not today's overall status.
Exact historical source and deployment receipts remain in the linked patch notes.
A code/test result is not proof of the current owner client or live fleet.

## Still unfinished

1. **Stage 6.3: public submission and verified TAS board writer.** The approved
   runtime registry must be backed by protected canonical sources, complete
   effective map/zone/dependency identities, alias/writer controls and real-map
   replay qualification. Queue work already exists on a held development branch;
   recover and compare that work with current main rather than inventing a second
   queue. It is not a deployed public-submission service.
2. **Stage 6.4: public TAS board/filter and contributor presentation.** Enable only
   after service-derived finish/time and TAS-only admission are qualified. Human
   and segmented admission must remain unchanged.
3. **Human-first editor, now the owner's local priority.** Normal play/pause and
   earlier-line recalculation, arrow-layout independent movement/turn controls,
   fine gain-relative turn rate, whole-run tick browsing and per-tick recipe
   restoration are requested work, including actual crouch/duck-transition handling
   and optional Follow travel pitch with manual override. Ground prestrafe and
   later ramp/airtime navigation/constrained optimization need distinct models
   and validation.
   [The redesign plan](plan-tas-human-workflow.md) includes capability limits for
   other runs; it does not pretend a position-only import contains exact inputs.
   Dynamic-world, streamed-history and general-route limits remain explicit;
   bounded existing features do not imply this work is done.
4. **Owner acceptance.** Lex tried the workshop and requested substantial usability
   changes; useful individual controls are recorded in [lextest.md](../lextest.md),
   not a whole-editor pass. Camera/input details, signing/account workflow and
   broader real-map cases remain unconfirmed. Reported ~275 versus expected ~289
   ground speed is an owner observation, not a measured regression/maximum.

## Resume here

Follow [the human-first plan](plan-tas-human-workflow.md) for the next local
editor work: small owner layout/ramp check, controller/recipe-state slice, then
the complete normal-play/full-history edit loop. A rearranged128-tick demo is
not completion of that workflow. Public source/queue work stays separate and
preserved; it is not a dependency for improving the controller.

When returning to 6.3, inspect today's source/service/mount state, not the old
failed-setup assumptions. Recheck capabilities at the real boundary; capability
availability alone is not source qualification. Preserve the held queue, original
failures and source history. Public acceptance stays disabled until qualified.

The EXISTING editor remains accessible through `tas menu`, `tas timeline`,
`tas project ...` and `tas shared`; it remains assisted practice, not ranked TAS.
The new screen, gain multiplier and full-history workflow are not there yet.
