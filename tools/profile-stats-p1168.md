# P1168 - public inventory, tracked-time readers and board navigation

## Implemented

- Public cosmetics include a bounded owned-item list, not just equipped items.
  Both inventories show saved colours; public views are read-only and distinguish
  OWNED from ON. The old-backend fallback explicitly says it knows only equipment.
- Client and menu profiles display optional tracked total playtime. A global menu
  profile opens from leaderboard, Friends and Story pictures, with Back/escape
  handling; no private signing or equipment command is introduced.
- Main-menu map boards have main/bonus course chips from the existing recorded
  board catalogue. Optional map time and main/bonus attempts are displayed, with
  the selected course's starts. Stage starts do not inflate that sum.
- !time and !time followed by a name privately answer tracked total/map time and
  main/bonus starts. Existing normal say dispatch is reused. Own linked identity,
  online exact-name lookup and unique offline public-name lookup are supported;
  ambiguous/offline-unavailable cases answer honestly. Queries are bounded,
  session-bound and rate-limited; they write no counters.
- A seeked online board can prepend earlier pages and retain a bounded moving
  window. Preserve the viewport across shifts and reset stale hit actions.
  Native Previous can request the preceding page rather than staying disabled.
  Menu near is initial-seek-only, not resent on a later page.

Public API requests accept the existing short8 and canonical12 hex handle forms.
The canonical handle must retain the requested prefix; private Friends identity
and capability rules are NOT widened. Optional playtime requires the explicit
steam_linked_game scope. Missing tracking is not a historical0h claim.

## What this does not implement

Real playtime/attempt collection and persistence belongs to a separate existing
workstream. Its unpublished source has NOT been copied or activated here. The
readers accept profile.playtime.seconds, map_seconds and bounded
attempts[{track,leg,n}] when available; until that producer is published, qualified
and deployed, real totals stay unavailable. Historical sessions were not recorded
and cannot be backfilled as invented hours. ROADMAP.md retains this remaining work.

No schema, grants/equipment writes, native source/pin/tag, mover, evidence grammar,
eligibility, qcbuild or public release changes. New public inventory reads expose
only the cosmetic fields already intended for profile display.

## Verification

- Inventory unittest suite:10 pass, including both owned-but-unequipped items,
  saved colours, revoked/unlinked account behavior and no read-time grants.
- Product three-program NoDeploy builds: zero new warning fingerprints; same two
  pre-existing client F333/setproperty227 warnings, no server/menu warnings.
- Real isolated dedicated socket, native client and controlled HTTP responses:
  public owned2/equipped0; absent-time versus7380s total (2h3m); normal plain say
  !time self8 and offline-name12;3720s map (1h2m),10 main/bonus starts rather than
  the extra99 stage starts;3 deduplicated courses, bonus click, actual picture
  click opening the ready read-only profile. Synthetic identity injection is
  test-only and not proof of real authentication, consent or counter collection.
- Actual Jump to me sought rank1500, then fetched offsets1454/1414 without near;
 160 rows held and inspected image starts1455, above the sought rank. The first
  grader incorrectly assumed page100 rather than the existing40; original failing
  report is preserved, and the corrected check derives the previous offset from
  the acted request/reply. Native-table Previous is compile/source-only so far.
- Inspected course, profile and seeking screenshots. The first menu crown's raw
  polygons missed the SUI frame transform; its detached tips were retained as a
  failed visual control. Corrected screenshot has the entire crown in slot2.
- Existing test_board_navigation.py:7/9 on both inspected baseline and subject;
  identical stale brand-text/PF_CF expectations account for the two failures.
- All owned fixture children stopped; three native-fixture program preimages and
  synthetic consent restored, hashes verified; only the owned synthetic zone was
  retired. No installed game/config/player data changed during these GUI checks.

The bounded runtime receipts and failed controls remain under the uniquely owned
profile-kit-01a19370 task root (historical p1166-ui fixture names). Passed receipts
are reused explicitly only for unchanged native/VM inputs, never re-dated.
These checks are not owner acceptance, performance measurement or live adoption.

## Source and delivery boundaries

The runtime source is an isolated backport on inspected fleet69fdb328 (published
as deploy/profile-crown-1164), not a full current-main rollout. Current published
native/TAS/backend source is preserved in the public integration; it must NOT be
silently activated on the frozen runtime. ENGINE.txt advances only the product
patch; each tree retains its own existing native pin/tag and qcbuild.

At this document's initial commit, deployment is pending. Required next actions:
clean exact-commit product build, publish inspected SHAs, ordinary guarded Pi pair
swap/readback, and inventory.py-only backend promotion on the frozen schema25
cohort. Do not use a whole-main backend deploy to bypass generation/namespace
admission. Keep rollback and record actual hashes/UTC after successful delivery.

Both Windows local VM/native cohorts previously changed without an established
source/owner. They remain protected: no blind overwrite, downgrade or restore.
Content-addressed official-CSQC cache seeding is a separate safe step; local
MENU adoption needs that cohort resolved. menu.dat is never a lobby ship item.
Counter collection and native Previous/manual feel remain separate pending gates.
Human-only checks are in lextest.md. No delivery is implied by the local fixtures.
