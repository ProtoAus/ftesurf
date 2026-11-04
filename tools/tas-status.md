# TAS project: current status and continuation

Status reconciled 4 November 2026. Start with [the full plan](plan-tas.md);
this page summarizes delivery rather than replacing the original acceptance criteria.
There is no single honest completion percentage: a useful local editor exists,
but its public ranked-submission path is not qualified.

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
3. **Broader editor/solver work.** Range/invalid-tail presentation, branch browsing,
   longer/general interval and route optimization, dynamic-world coverage and
   streamed-history editing remain separate work; bounded existing features do
   not imply they are done. See the TAS sections of [BACKLOG](../BACKLOG.md).
4. **Owner acceptance.** Timeline feel, camera/input, signing/account workflow and
   broader real-map behavior still need the specific checks in
   [lextest.md](../lextest.md). Do not turn an automated screenshot into an owner
   confirmation.

## Resume here

Continue the canonical-source prerequisite for 6.3 using today's inspected
service/source/mount state. The historical privileged-setup failure is evidence
of that attempt, not proof that the same restriction still applies. Recheck
capabilities before asking for another owner action; capability availability
alone is not source qualification. Keep public acceptance disabled until the
full source-to-native-replay boundary is demonstrated. Preserve the held queue,
its original failures and source history when integrating current main.

In parallel, the local editor remains usable through `tas menu`, `tas timeline`,
`tas project ...` and `tas shared`; it remains assisted practice, not ranked TAS.
