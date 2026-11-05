# P1323 - durable historical input recipes

This is one component of `plan-tas-human-workflow.md`, not completion of the
human-first editor. Independently reviewed, qualified and installed BOTH Windows
and all 12 lobbies on 5 November 2026. Owner feel and genuine-device hosted Sign
remain pending. Earlier private receipts used provisional labels P1317, P1319 and P1321. Separate
winter and expected-reset features already claimed those numbers; a full
149-worktree journal/test census establishes P1323. Old receipts keep their
original labels and are not reissued; the reviewed product code is unchanged.

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
  checks below use the P1314 TAS interface. Actual installed primary clients
  retain published P1318; the qualified P1314 dedicated/plugin dependency is
  activated separately, with equivalent server/input source, not relabelled P1318.
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
- Follow-up source review found a remaining full-to-free observer transition:
  the bounded chat observer could insert a previously omitted gameplay repeat
  and make it look fresh. An untreated 9-pass/1-failure control actually reproduces
  that sequence, while release without the repeat stays unclaimed. The recipe
  now observes keyboard scans 1..511 by direct indexing in 2 KiB of VM memory,
  independently of chat's bounded list. Unsupported scans are never acquired;
  a null allocation result does not retry mid-hold (a native allocation error
  can abort CSQC). The combined corrected 19-control
  arm repeats saturation/recovery, proves a genuinely fresh field press still
  acts, and re-runs the ordinary input/name/chat/Windows-stage checks above.
  All 19 pass. This remains synthetic input-chain coverage, not a new claim of
  hardware movement, VM-reload continuity or executed allocation failure.
- A later two-reader pass found native-menu observation gaps and a repeated
  owned key entering a later key-capture panel. The untreated arm has three
  acting setup passes and four predicted failures. An actual owned-window native
  +binding remains held after the old handler eats its release; the correction
  runs the stored -binding. The repeated name key keeps its actual binding and
  a genuinely new key then completes capture instead; its next fresh pair is
  not eaten by a stranded latch. All seven corrected controls pass. Native F
  keys are not acquired. Internally owned releases still stop later QC handlers,
  but the outer entry forwards them to native stored-release processing: CSQC
  can miss an original press. The combined 19-control input/name/occupancy arm
  passes again with that native-return distinction. Window messages are synthetic,
  not physical-device or signing evidence. Native key-path source is unchanged;
  this does not relabel the whole older fixture binary as P1318. The clean
  merged candidate was then checked against the actual published P1318 primary
  client: all seven controls pass again. Both installed primary client hashes
  match the published P1318 receiver proof. Dedicated P1314 source differs from
  P1318 only in an unused client-renderer file; its already-qualified server
  support is a deployment dependency where the dedicated install is still P1312.
- A 10-control source-only arm saves an eight-row historical tail. Its engine
  processes stop. A separate 20-control fresh-process/current-base arm reads that
  saved reference, applies it to an earlier span, actually replays the full head,
  Discards, then Keeps and executes Undo/Redo. The kept rows equal the saved
  source selection, every future row remains identical, and the target base is
  retained instead of importing the expired source base. Wrong count, missing
  recipe and invalid name explicitly refuse without native/body/project change.
- The recorder reader suite completes **949 checks, zero failed**. The retained
  runs-only regression arm used the same 544 input/paired-view byte sets and
  identical per-record findings as its control. Both stored finding sets contain
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

Two fresh independent source/evidence reviews found no blocking issues in the
final native-routing and QC/data-preservation correction.

## Installed receiver provenance — 5 November 2026 UTC

QC source `8ae5dbbb7a0a2ec5e5653f619a00bf6e3412efca` was published before
promotion; this includes the exact published expected-reset and resume guards.
BOTH Windows activated at **12:53:44Z**: six VM/symbol targets and the qualified
P1314 dedicated/five-plugin dependency per install, **24 exact targets** total.
Actual primary P1318 clients stayed unchanged. All current/prior-prev preimages
were retained, every target/.prev pair checked, and **18,483** existing protected
config/data/content files stayed unchanged through the actual installed
client18/server14/plugin14 seven-control receiver check at **13:05:56Z**.

The Pi activated native/server-plugin plus the same QQ pair at **13:58:37Z**.
Before any canonical staging/restart, **8 actual recorder parts and 180 complete
saved-resume payload/metadata files** were individually rehashed ONBOX and OFFBOX.
The short locked boundary rechecked all 13 declared actors/births/FD closure and
the active backend's 156 source files. All 12 lobbies were empty at their restart;
none skipped, no PiForce. Exact targets/.prev and all 12 live native/plugin pairs
passed. **46,856** existing protected files were unchanged at transaction
postflight; the lock was released. At **14:05:25Z**, one player had reconnected.
The backend generation/source did not change. The existing code catalog only
appended this reviewed client hash, retaining every prior byte. No release,
qcbuild bump, general filewriter audit or restoration/expiry waiver is implied.
Earlier failed preservation transactions remain failed; their receipts are not
upgraded by this successful full-preimage delivery.

Owner workflow/feel acceptance and genuine hosted real-device Sign remain
explicitly pending in `lextest.md`. Long-history, variable-command timing,
procedural intent, cold-world replay, sections and constrained route optimization
are not established by these bounded local checks.
