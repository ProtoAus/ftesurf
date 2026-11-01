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
- A real backend HTTP check caught a fabricated catalogue suffix route (404).
  Fixed it to the actual `/board/api/map?map=...` Flask/nginx route (200), and
  tightened the fixture so it rejects the fabricated path. The rerun acted two
  canonical catalogue requests, both200, with no suffix requests; course image
  inspected, children stopped and preimages restored. This supersedes the old
  fixture's insufficient endpoint-contract coverage.
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

Keep the separately published source cohorts distinct:

- Public integration: `fba5b68f629416a19c0a219fb7489cf9451f362f`, including
  the corrected catalogue URL. Existing published native/TAS/backend work is
  preserved here; this is NOT approval for whole-main backend activation.
- Frozen QC: `bfdf69e5a4f0ce1a2c98c010c584efc5567c17ec` on fleet69fdb328,
  published as `deploy/profile-stats-1168`. It retains that older native cohort;
  do not ship it over a newer unbound pair. Pre-URL-fix artifacts are superseded.
- Inventory-only backend: `fcc0d20b6e86c8b3597da7636a7fd9be421dc0a9`,
  `deploy/profile-inventory-readers-1168`, on exact live primary da053e69.
  Its82-file closure changes ONLY inventory.py; prior-primary fallback is the
  exact old82-file closure. Same schema25/inventory82-v1, guard and dispatcher;
  no counter family, schema migration, native activation or DB restoration.

### Delivered: Windows MENU only

At **2026-11-01 05:43:15UTC**, both Windows `menu.dat` + matching LNO were
updated from the clean inspected public integration commit above. Both prior
menus exactly matched a clean published fea6969b control build. That resolves
MENU ownership independently; it does NOT establish the unknown CSQC/SSQC/native
pair's source. The build's existing Deploy/.prev helper was reused narrowly.
Both destination hashes were verified, `.prev` retains the actual predecessor,
and older `.prev` files were preserved in this task's evidence. All captured
CSQC/SSQC/native/plugin/config hashes stayed unchanged; no owner process restarted.

| Both Windows installs | SHA-256 |
|---|---|
| menu.dat | `8a3705aa799622a42fb69b6a75e01f89d04d905a4b6905ad426436e03f468b46` |
| menu.lno | `b607841121e9d01e09933c4d81c1f15b0465255b83c2ff226bedb327252c2116` |

Reload with `menu_restart`. Picture-to-profile navigation, main/bonus chips and
menu earlier-page fetching are installed. Owned-but-unequipped display is now
backed by the live inventory promotion below; real counters remain unavailable.
menu.dat is client-local and is NEVER a lobby ship item.

### Delivered: frozen inventory backend

Owner confirmed protected namespace admission. At **2026-11-01 06:47:08UTC**
primary `fcc0d20b` was activated through the existing CLOSED-candidate/receipt
protocol and reopened OPEN. Exact previous-primary fallback remains CLOSED and
available on the SAME database; original predecessor drained CLOSED. All82 raw
source hashes and every canonical entrypoint were checked, actual process/CWD,
listener and service namespace verified, four cron routes rebound, momrequests
restarted and health200. Schema remains25; all closed-boundary table counts,
existing schema and identity/inventory row digests matched. No old DB restoration,
native/game-program deployment, collector activation or historical backfill.

Independent live verification at **06:54:47UTC** checked seven real public
`/api/board?player=...` profiles: all persisted owned lists matched exactly,
including14 real unequipped items. No grants/equipment changes or fake users were
made for this check. The acted unknown-player control returned404. One linked
account without an existing public board profile also returned404; this update
does not manufacture a public profile for that case. Main-menu owner interaction
acceptance remains pending; run `menu_restart` then reopen the profile.

### Concrete remaining blockers

1. **Newer live/Windows SSQC+CSQC source ownership.** Neither matches the clean
   published fea6969b control or any of32 retained task artifacts. Their current
   pair remains untouched, including all12 lobbies. Obtain the owning commit /
   build receipt or explicit handoff, integrate without losing that work, build
   and validate the exact source, then ordinary paired deploy/readback with
   rollback. This blocks live `!time` and in-game reader/board adoption, not the
   separately source-bound MENU update.
2. **Actual counter collection/persistence remains unimplemented here.** The
   existing owner must publish/hand off the consented linked-game producer and
   required family before it can be integrated, qualified and activated. Reader
   completion is NOT completion of the user's real hours/attempt request. No
   competing or unpublished collector was copied; no historic hours invented.

These are unfinished parts of the same request, not an owner-imposed later pass.
Native-table Previous runtime proof and owner interaction/appearance acceptance
also remain pending. Human-only checks are in lextest.md.
