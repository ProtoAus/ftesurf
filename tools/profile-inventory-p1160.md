# P1160 profile inventory and cosmetics

## Implemented

- A floating 4x4 inventory beside `hud_player`, using the existing profile scale
  and input handling. Only owned items can be selected; clicks request an
  authoritative server update rather than trusting local UI state.
- Steam-account ownership, equipment and hat colour persist across reconnects
  and installations. The starter catalog is the light-blue ice outline and a
  paper party hat; the hat receives one persistent random colour.
- Other clients and profile previews draw selected cosmetics. Public state is
  presentation only; the private inventory snapshot does not expose capabilities.
- Linked, non-banned accounts automatically have the cosmetic Tester badge.
  Zoner and Developer badges have separate colours and grant NO editing/admin
  permissions. The authenticated operator accounts page can grant/revoke items
  and badges. Equipment uses ownership checks and a bounded revision comparison.
- Maps has one Surf/Bhop switch. Saved invalid/combined/old masks resolve to a
  valid single selection; there is no selectable All/Other mode.

## Source isolation

| Purpose | Inspected/published commit |
|---|---|
| Main implementation | `3cc2855aba607248bb7584bd3bf62fe8fca96c1d` |
| Fleet QC backport | `84a8ff1a925f3ebda8f681c76387279ac6670472` |
| Fleet backend backport | `da053e69520930578abd4ede985b6f9cde944a78` |
| Schema25 old-endpoint rollback | `a1b8380031bda85a1892f590a1f627e4eed558c9` |
| Engine patch documentation only | `b599bcb0b3d18fb0eb186ce812e4aad3a1376962` |

The deployed VMs are based on installed P1151 VM source `8c857577`, not the
pending P1154 VM work on main. Every owned QC source path was compared; the
player-file difference from main is exactly those excluded P1154 hunks.
No native image or plugin was built or shipped for this feature.

The backend package starts from inspected live `03693b98`, not newer main KSF
code. Its complete 82-file cohort differs in seven existing files plus the new
inventory module; three of those existing changes are schema fixture literals.
The compatibility cohort changes only the schema/migration module, its board
fixture expectation and the inert inventory module. Both pin the unchanged
external converter closure.

## Actually deployed

QC destination/hash/rollback observations: **2026-10-31 22:26 UTC**.

- Both `C:\FTESurf` and `C:\FTEQuake`: all three progs and their LNOs match.
- All 12 NanoPi lobbies: matching `qwprogs.dat` and `csprogs.dat`, healthy units
  and directory rows; all 12 respond to UDP status queries.
- The normal Pi invocation refused when a player joined during compilation.
  The pre-approved `-PiForce` invocation then restarted the 12 lobbies with one
  player present. Previous programs are retained in `.prev` and task preimages.
- Three Windows native executables and the existing primary owner config hash
  remained unchanged. The secondary install had no `ftesurf.cfg`; it was not
  manufactured or copied from the owner's install.
- Both Windows CSQC caches have the exact new program. No active download
  temporaries were deleted. NanoPi client-cache seeding is not required for
  serving `csprogs.dat`; no cache permissions were changed.

| Program | SHA256 |
|---|---|
| qwprogs.dat | `051557d568fce88a252ad1f960598990c6d90570b8160cfe4ddf4c526fa503db` |
| csprogs.dat | `cba6fdc6359bf8bf0a6ab381636e1d85cc43b9262ecd9a4661487c2f5b9ffdd9` |
| menu.dat | `6c9f9034ea348ead9874e5224b144751d39fd03d56bebca1d595aafe7bf2d938` |

**Backend activated 2026-11-01 00:33:44 UTC.** After the owner installed the
protected startup configuration, the unchanged predecessor was closed and its
foreground leases drained. The prepared primary cohort is OPEN at schema25;
the predecessor and schema25-compatible rollback remain CLOSED. The actual
systemd master owns the production listener and uses the frozen primary source.
Its invocation-bound filesystem preflight passed: both runtime trees and five
control pins are read-only; mutable state/data/log roots remain writable.
The four scheduled routes and the restarted Momentum request worker use the
new guarded generation. No native image or unrelated main-branch source shipped.

A private consistent pre-migration backup is retained. At the drained acceptance
boundary all pre-existing table counts and schema definitions matched, as did
full account/link/viewmodel-table digests. Only the two inventory tables and the
schema version were added; no old player-data snapshot was restored.

At 00:34 UTC starter items were initialized for all 13 eligible linked accounts.
Markbeaton54 received Zoner, and the owner's explicitly supplied Steam profile
received Developer; both also have Tester. Readback verified the persisted
items/badges and the live profile API's public cosmetic fields. Unauthenticated
inventory POSTs are rejected, private inventory fields are not in profile
responses, and all 12 lobby directory rows continue to refresh.

## Verification and limits

- Nine signed-account inventory tests pass, covering persistent starter grants,
  two-install behaviour, equipment revisions, eligibility, bounded values and
  authenticated/CSRF-protected operator changes. Existing accounts, social,
  board and join suites pass; eight cold/future-schema checks pass.
- Public POSIX schema25 fence controls pass. The actual full 82-file cohorts
  also pass missing-inventory, changed-inventory and opposite-schema controls.
  Each real CLOSED Gunicorn candidate uses a FRESH fixture DB, owns the measured
  listener, reaches schema25, and is externally accepted OPEN then drained CLOSED.
  Primary inventory GET is 405 (registered POST route); compatibility is 404.
  These are fixture results, NOT production migration or namespace evidence.
- Native real-socket subject/observer checks show OFF/ON cosmetics, the floating
  grid and badge presentation. The mock backend receives five nonempty opt-in
  roster rows and two genuine equip posts; revision5/both-equipped reaches private
  CSQC state. Mock capabilities are not an authentication proof; authentication
  is the separate signed-account suite above.
- All QC programs compile with zero NEW warnings. The two existing viewmodel
  F333 argument227 warnings remain baseline warnings, not silently fixed here.
- The actual menu filter gives Surf1/4 then Bhop1/4. A consent screen covered the
  automated menu view: those counts are not a visual or mouse-click pass.
- The ice effect is an FTE-compatible depth-tested shell, not the supplied
  through-wall JFA pipeline. The owner confirmed the right-hand grid and item
  toggles work, but rejected the aura as a line stroke rather than the requested
  soft fade. That visual failure is a follow-up, not accepted appearance. Other
  avatars/reconnect/badges/Maps checks remain explicit in `lextest.md`. No
  wall-visibility or numerical performance acceptance is claimed.

Never reopen schema24 code against a migrated schema25 database, drop tables,
restore a stale player-data snapshot, or weaken the guard to make rollback pass.
Use the qualified schema25-compatible old-endpoint cohort. Operator activation,
rollback and private identity selection are retained in the local checkpoint;
private raw output/identities do not belong in this public record.
