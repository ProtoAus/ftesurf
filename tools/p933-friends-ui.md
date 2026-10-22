# P933 — browser Friends, profile preview, double-click select-all

## Prediction / control

The old VM must ACT on the name field but not select the whole text after two
close clicks. The subject must select all, keep the selection through release,
and replace it with one typed character. Two clicks separated by 500ms must
remain normal. With ui_maps_friends explicitly zero, opening Play must leave it
zero in the control and turn it on in the subject. A two-row saved-name fixture
must actually load; offline permission remains off and no clipboard is touched.

Backend controls must show Stage 3 changing to Bonus 5 and changing the snapshot
hash. Omitted fields, cache loss, changed lobby map, expired/absent sessions,
unaccepted adds and blocked relations must never invent current activity.
Invalid labels must be rejected and a failed SQL poll must not publish a sample.

## Implementation

- Compact 64px/two-line cards with picture-centered name and location, offline
  alpha .45, live green map/activity. Flag 2 is last-seen, NOT online flag 1;
  stale/offline rows do not expose a join target.
- Name opens a public profile preview inside the same menu: picture, name,
  public-time/map/first-place figures and first six result rows. Uses the existing
  fixed-origin /api/board?player= endpoint and exact integer-ms builtin. No new
  external URL/browser command and no private account capability.
- The location alone asks the existing signed/lobby join path; the backend still
  checks fresh presence, account policy and compatibility. No direct connect from
  cached display data.
- Opening the browser reveals Friends and asks the connected lobby to refresh;
  disconnected mode schedules its existing signed read-only list request.
- Activity is an optional seventh transport field. Old six-field snapshots still
  work. Server labels come from run_t_track/run_t_seg, or spectator state.
  `friend_begin 1` advertises refresh/activity support. The menu sends the new
  explicit refresh action only after that capability, pinned to the completed
  snapshot's epoch. Old CSQC increments its snapshot epoch but cannot carry a
  newer server's capability across reconnect. An older fleet server continues
  its normal five-second updates without a bad-action error.
- Activity is bounded volatile process state, keyed by the existing session
  digest. It requires SQL-seen and map identity to match and never substitutes for
  SQL's online/relationship decision. A worker without the sample leaves activity
  empty until its next valid poll. No DB migration, recorder/evidence semantics,
  consent, signing or generic chat permission changes. Memory cap 16,384 samples.
- Shared SUI selects all on a second click within 400ms/6 UI pixels, keeps it
  through release, and preserves normal click/drag/shift behavior.

## Verified

- Three-VM NoDeploy build: zero warnings; final outputs under
  rig/build-nodeploy-3f24c759de0b4937851dd07ec906cf73.
- `python -m unittest test_social`: 44 tests pass (5.646s), including the controls
  above and all existing private-list/DM/proof/relationship tests.
- Existing `test_ksfprofile`: 16 tests passed during inspection. A proposed DB
  column was discarded in favor of volatile presence; the DB schema and that test
  file are unchanged from the parent commit.
- Native `tools/p933ui_smoke.py`: old control ('surfer',6,-1), subject
  ('surfer',6,0), replacement ('z',1,-1), slow clicks ('surfer',6,-1). Browser
  Friends setting control 0 vs subject 1; both read the two-row fixture.
- Final new-profile/seventh-field VM reran the subject successfully. Offline
  screenshot inspected: browser shows the Friends side panel and the correct
  online-features-off message, not fabricated live friends.
- Python LSP: no diagnostics recorded. QC authority is fteqcc/runtime, not LSP.

Integration: current origin added P931 weapons and P932 linked KSF playback.
P933 was rebased without production-code conflicts. Recompiled all three VMs at
zero warnings, reran 44 social and 45 Story tests against that integrated source.
The peer's source identity/unverified playback boundaries and native gates remain.
The NanoPi producer/native qualification gate still applies; client UI does not
justify deploying an unqualified mainline producer. Local and fleet states are
tracked independently.

Patch-number coordination: the original unpublished feature/evidence was called
P931. Another session published P931 weapons and P932 map-port playback before
our push. Both rejected pushes were preserved, our unpublished feature was
renumbered P933 after fetching/scanning max932, and it is integrated rather than
force-pushed. Earlier p931-named local evidence remains unchanged.

Two initial UI setup failures never reached a field: Terms correctly replaced
forced Name because the rig omitted the existing consent-file fixture. Compared
with p655text, supplied that isolated fixture, then the control acted. Failed
logs are retained in the owned task root. The failed eight-substitution sprintf
build is likewise not counted as successful verification; final rows have seven
substitutions and all builds end at zero warnings.

## Limits / delivery

Real-account card/picture/profile/join appearance and live cross-client stage
refresh are PENDING owner acceptance in lextest.md, not implied by the offline
screenshot. At narrow widths below the existing 1180px sidebar threshold the
existing responsive fallback still applies. Picture resolution is unchanged by
this patch. Menu-wide chat/DM and game-running disconnected presence are not
implemented here. Publication, dual-install deployment and backend/fleet cutover
must each be recorded separately with actual hashes/UTC; this report is not a
claim that they have happened.
