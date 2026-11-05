# P1319 - durable historical input recipes

This is one component of `plan-tas-human-workflow.md`, not completion of the
human-first editor. Implemented and locally exercised; review and deployment are
still pending. P1314's separately frozen artifacts are not silently replaced by
this working source. Earlier private receipts used the provisional label P1317;
the unpublished component was renumbered when the commit-time audit found a
separate winter feature using that number. Those receipts are not renamed or
silently reissued.

## Use

1. Play normally, pause, and open `tas menu`.
2. In Timeline, select the first and last ticks of the desired input span.
3. Open Project, type a recipe name, and choose **Save selected input**.
4. In a supported paused recording with the same map/profile/tick duration,
   select an equally long target span. In Project, enter the saved name and
   choose **Preview named recipe**.
5. Project has **Keep recipe preview** and **Discard recipe preview**. The
   existing Timeline Undo/Redo history also retains kept recipe edits.

Names use 1..32 lowercase letters, digits, `_` or `-`. Typing uppercase folds it
to lowercase. Enter/Escape releases the name field; another Escape closes the
panel. There are at most 64 templates per map. Saving refuses an existing name
or retained unfinished write rather than silently overwriting it. Both the final
and staged names require confirmed absence in the uncached write namespace;
unreadable files, lookup errors or unavailable metadata readers refuse before
freeze/write. Saving assumes no concurrent external writer in that namespace.

The console accessibility equivalent is `tas timeline recipe save <name>` or
`tas timeline recipe apply <name>`, using the current bound Timeline selection.

## Contract and limits

A named recipe retains the actual selected input rows: three movement values,
three angle words and button bits, plus the fixed map-tick duration and row
count. The captured tape does **not** store arbitrary per-usercmd durations;
this feature neither invents them nor claims their reproduction.

The small unsigned `.tasr` reference points to the already retained, hashed
immutable input project and its selected span. The strict existing project reader
checks the source map, zone, movement profile and computed input identity. A
recipe does not depend on the old engine process still having its body in memory.
It does require the retained input revision still to exist.

Saving does not move the body or replace the working input line. Applying copies
only the chosen input rows into a preview of the current full captured line.
All input outside that selection, including the retained future, survives.
Exact row-count and fixed-clock mismatches refuse before placement. Native row
admission is checked before placement too. Keep/Discard and Undo/Redo reuse the
existing immutable-revision transaction.

A template supplies **input only**. It never imports the source project's body,
base, native token, recorder prefix, locally-made state, signature, ranking or
other authority. Execution still uses the **current target run's own supported
warm base**. Loading an input reference saved by an earlier engine process is
not cold-body or shared-world reproduction; the world is not rewound.

Original generating intent stays unknown: recorded W+D/yaw values do not prove
that GUIDE, HOLD or a particular strength produced them. These are literal input
templates, not a completed procedural recipe/section/next-ramp solver. Historical
procedural intent beyond the existing qualified live metadata remains in scope.

## Verification

- All three VMs compile with zero warnings. This feature changes no native C or
  evidence grammar and retains the published base's native requirement/pin. The
  checks below use the P1314 TAS interface; whole-native deployment binding to
  the latest published renderer build is a separate requirement.
- A 14-control same-line arm saves a mixed-key historical selection, changes the
  live draft, actually replays the saved input rather than that draft, and
  executes Discard while preserving original bytes and monotone counters.
- A 16-control GUI arm uses actual Project widgets and synthetic input routed
  through the normal client input chain: edit the name, Escape without closing
  Project, Save/Preview/Discard. The actual captured image was read. This is UI
  functionality, not real-device signing attestation or owner feel acceptance.
- Independent review found release ownership, chat-key priority and unreadable
  staged-file occupancy defects before shipment. The untreated input arm has
  eight passing setup controls and four predicted failures. The corrected
  16-control arm forwards a pre-focus gameplay repeat/release, retains owned A
  and Escape releases after tab/blur, types a name containing the chat-bound T
  without opening chat, and actually saves that exact name. A higher-priority
  chat draft clears name focus. This measures synthetic CSQC-chain replies, not
  hardware-held movement or device signing. The same arm proves a read-denied
  but write-accessible owned Windows stage refuses at the metadata preflight,
  preserving its bytes, native state, body and working file; its exact ACL is
  restored. POSIX-specific overwrite reproduction and concurrent external
  writers are not established by that Windows arm. The guarded metadata helper
  is the existing conservative import interface, not a new file-open fallback.
- A 10-control source-only arm saves an eight-row historical tail. Its engine
  processes stop. A separate 20-control fresh-process/current-base arm reads that
  saved reference, applies it to an earlier span, actually replays the full head,
  Discards, then Keeps and executes Undo/Redo. The kept rows equal the saved
  source selection, every future row remains identical, and the target base is
  retained instead of importing the expired source base. Wrong count, missing
  recipe and invalid name explicitly refuse without native/body/project change.
- The recorder reader suite completes **949 checks, zero failed**. The current
  runs-only corpus has the same 544 input/paired-view byte sets and identical
  per-record findings as the retained control. Both stored finding sets contain
  **352 entries**; the older summary's 351 is not its stored finding total. An
  initial scalar/list-order comparison failed and is retained. Comparing by
  record path confirms zero changed findings; it does not make the corpus clean
  or add SAVES coverage.

Earlier observer and product failures remain failed: wrong expected preview
message; a recipe-padding run incorrectly asked for the separate >128-row
experiment; a test decoder incorrectly assumed an explicit tick column; the
first native validation caller inverted the first-bad-row return contract; an
Undo probe hit the existing action gate; and an overlong ordinary run returned
to its start before saving. A later ownership probe passed its first 12 controls but looked
for the wrong saved name: it rendered an empty field between clearing and typing,
which reinstated the default. Its receipt remains failed; clear/type now uses one
normal input batch. The validation call is corrected, the same actor's
format/gate/setup seams are fixed, and the smaller actually saved source span avoids
turning this feature into a long-run harness campaign. No old receipt is upgraded.

Owner workflow/feel acceptance and genuine hosted real-device Sign remain
explicitly pending in `lextest.md`. Long-history, variable-command timing,
procedural intent, cold-world replay, sections and constrained route optimization
are not established by these bounded local checks.
