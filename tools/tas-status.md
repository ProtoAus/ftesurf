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
| Observed local sections | Passive native contact maps, complete exact-source face browsing and retained-line start/end navigation | Both Windows/all12 lobbies deployed6November; static profile and owner acceptance limits; [P1350](p1350-tas-contacts.md) |
| Experimental local section search | Bounded nine-candidate selected-input to later-face/arrival-region search, full-future preview and exact Original recovery | Both Windows/all12 lobbies deployed6November; best found only, no measured speed improvement or owner acceptance; [P1355](p1355-tas-solve.md) |
| Server replay foundation | Operator-only bounded legal-start verifier | Qualified 15 ms fixture profile, not public admission; [runner contract](tasverify.md) |
| Canonical-content foundation | Native VFS source inventory, epoch/lease and binding checks | Components, not complete production source qualification; [source contract](tas-native-source.md) |

P1329's qualified program bytes are installed in **both Windows copies and all
12 lobbies**. Destination/predecessor hashes, current native/config preservation,
complete recorder/resume preimages and new lobby epochs were checked. An
installed-byte dedicated-socket smoke also passed. The original rollout-caller
SSH timeout is retained; the on-box activation succeeded and was reconciled
read-only, without repeating swaps/restarts. See the qualification for scope.
This is deployment evidence, not owner usability or genuine-device signing.

### Manual sections and native observations published and deployed

[P1336](p1336-tas-sections.md) adds a full-retained-line Sections tab with manual
endpoint naming, input-range selection and bound start/end navigation. Add,
rename, move-to-current-body and remove save the complete raw/settings line even
while paused earlier. Original revisions, no-input-supply semantics and the
ordinary partial-save guard remain. A conservative cumulative byte budget now
refuses oversized synchronous marker saves intact; storage/browser limits remain
unchanged. Actual old48000-row control18 exhausts the VM AFTER read/load/browser
baseline; corrected22 safely refuses, stays responsive and saves a short edit on
that same server. Corrected metadata58 and16synthetic budget-helper checks pass;
earlier widgets31/panel inspection remain separate evidence. Two final independent
whole-feature reviews cleared the corrected code. P1336 is published and its
BOTH-Windows install/runtime check passed; P1350 now also carries those reviewed
manual sections to all12 lobbies. Owner acceptance remains separate. Provisional P1335 was renumbered before
publication without a runtime source change.

[P1350](p1350-tas-contacts.md) now adds passive native world-ramp observations,
complete source-bound maps and a separate Observed contacts browser. An actual
static BSP ramp, earlier navigation/metadata-only retag, native helper suite and
changed-input preview/Discard restoration are isolated-qualified. Old native
absence is explicit; unsupported/gap/no-ramp states are not guessed air. Final
clean tagged-source Windows FULL/three-VM and ARM1608/0 builds, two independent
whole-feature source reviews and current real-client cache acceptance are complete:
old open-control37/37 acts and production65/65 passes with original/counters exact.
Both Windows installs and all12 lobbies are deployed; downloaded-client smoke
and owner two-ramp acceptance remain pending. This is an observation foundation,
not best-found section solving.

The API reader upgrade is reviewed/tested/published but still needs the owner's
root-authenticated standalone TAS-service upgrade. This does **not** block local
editing: normal in-game sharing explicitly accepts only legal-start v3 projects,
not local v4 base files. Keep that guard. The upgrade does not itself make v4
projects portable, enable public verification or grant input credit from settings.
The existing v3 sharing path and its newly registered shipped client remain usable.

Earlier dated stage paragraphs in the original plan keep their historical scope.
A statement that a later stage was then unbuilt is not today's overall status.
Source, qualification, deployment and human acceptance are separate evidence.

### Experimental bounded local solver — P1355

Actual22production helpers and37real dedicated-socket goal/cancel/recovery checks
pass: fair baseline, all9 native candidates, complete future, real GUI Cancel,
stale job isolation and exact Original input/settings recovery. Independent review
fixes also prove optimizer exclusion and restored preview status after reopening. Baseline was best;
no invented improvement or input credit. All3VMs compile0warnings. This is initial
bounded-search qualification, not full two-ramp acceptance. Published runtime
c489d56a is installed BOTH Windows22:02Z/all12lobbies22:14Z6November, with exact
hashes, current native/config/backend preservation and full recorder/resume
preimages checked. Details and limits remain in [qualification](p1355-tas-solve.md).

## Still unfinished

1. **Human-plan phase 4 delivery/acceptance.** P1350's native contact proposals,
   full-source browser and metadata/preview invalidation are implemented and
   isolated-qualified; tagged builds, both final reviews and current real-client
   checks pass and BOTH Windows/all12 lobbies are deployed. Finish the bounded
   downloaded-client smoke and owner acceptance described above.
   Keep manual boundaries explicit and static-world scope honest. Real moving/
   unsupported scenes and owner comfort are not supplied by helper tests.
2. **Human-plan phase 5: useful constrained section/next-ramp solving.** P1355's
   initial bounded local face/arrival-region search is now installed, not merely
   an endpoint optimizer.22helper/37native checks qualify its scoped goal,
   full-future/cancel/recovery behavior. A useful familiar two-ramp result, changed
   winner/history, long selection, natural finish and broader real ramp/air
   comparisons remain unverified. Baseline was best in the actual control; no
   measured speed improvement or global-optimum claim. Tune the next change from
   the small owner pilot instead of another broad proof-framework campaign.
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

P1336/P1350 sections and the initial P1355 search are installed. Next obtain the
small familiar two-ramp owner check in lextest.md and a concrete ground-prestrafe
reproduction; use observed gaps to continue the
[human-first plan](plan-tas-human-workflow.md), preserving the delivered
play/pause/full-captured-line/settings loop. Clean-cache downloaded-client smoke
and the explicit long-selection/changed-winner/finish cases remain unverified.
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
