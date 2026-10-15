# P723 — separate map and leg ratings

## Behavior and sources

The top-right map HUD names **MOM** and **KSF** independently. Missing means `?`,
not tier zero. Momentum public-submission estimates say `(suggested)`; the
scoreboard's compact equivalent has `*` and a `* suggested` header. Main-map
tiers are never donated to stages/bonuses, port aliases or different map names.
The current server-timed stage/bonus gets an additional HUD line when rated.
The scoreboard Track sidebar puts the same sources below each leg's name.

- MOM: installed Momentum Playtest public MSML map caches. Canonical gamemode
  and NORMAL/PRO/TELEPORT style selection matches `tools/mapmeta.py`. Approved
  maps use leaderboard tiers; public testing/content/final approval maps use
  submission suggestions. Private testing/disabled maps are not published.
- Numeric KSF main ratings: the existing `maproster.py` `ksf_roster.csv` snapshot,
  which originates from KSF's map-list spreadsheet. These are not MOM ratings.
- Community KSF bonus ratings: the spreadsheet requested by the owner:
  <https://docs.google.com/spreadsheets/d/1Hft-1XdK7lge5WWqP5hrNsSUJw_Ss2PS-t-c3CTawpQ>.
  Its **letter** tiers are displayed as letters, not made-up numeric equivalents.
  Unit and Strafe columns remain separate (`U:`/`S:` on the compact scoreboard).
  A split rating, such as shibboleth bonus4 X(unit)/S(strafe) in this snapshot,
  retains both. The To be added column is not a rating. `? Tier` stays `?`.

The initial public snapshot has2776 exact map names /5260 rated legs,
4683 MOM leg ratings,929 KSF main ratings and163 distinct community-rated
bonuses (138 Unit +26 Strafe; one bonus appears in both). The installed
Momentum snapshot contains **no non-null stage tiers**; support is implemented
and tested with explicit synthetic stage ratings, not fabricated live values.
Several real main ratings differ, e.g. surf_angst MOM5 / KSF4.

Ratings are metadata by exact map name, NOT proof of an identical BSP build.
No runtime HTTP fetch occurs during HUD drawing. Refresh the shipped snapshot
explicitly when the Momentum cache/roster/community sheet changes:

```powershell
python tools/maptiers.py --ksf-roster C:/FTESurf/ftesurf/data/ksf_roster.csv
python tools/test_maptiers.py
```

`--momentum <gamedir>`, `--bonus-csv <snapshot>` and `--out <path>` support
isolated/offline refreshes. Fetch/parse/conflict/size failure leaves the old
catalogue unchanged. New non-empty sheet layouts or unsupported letter labels
fail rather than guessing. Case folding and the sheet's missing `surf_` prefix
are canonicalized; `_css`, `_v2`, etc. are NOT stripped.

## File, wire and deployment

`ftesurf/maps/tiers.txt` is a tracked, public generated asset, explicitly in the
release ship allowlist. Its grammar is documented in `tools/maptiers.py`.
SSQC scans it once at worldspawn, clears prior ratings, publishes short
`maprating_<track>_<leg>` rows and finally `mapratings=v1:<map>`.
Track0/leg0 is the full main run; track0/legN is stageN; trackN/leg0 is bonusN.
CSQC uses the server's values, never its own catalogue. A different-map marker
is unknown. Old servers get source-aware fallback from maptier/maptiersrc;
KSF and alias/local overrides are not mislabelled MOM.

Do NOT put the whole compact file payload in one serverinfo value. Acting
controls found the supported engine pair omitted it initially: >=64-byte OR
semicolon-containing values become info blobs. Short comma-only row values
and the colon-separated map/version marker are delivered correctly.

Deploy the asset to **both Windows installs and the NanoPi game gamedir** as
well as qwprogs/csprogs. `build.ps1 -Pi` ships only the progs; the asset must be
copied separately before restarting. menu.dat is local only. No native rebuild,
engine pin/tag or qcbuild bump belongs to this QC-only patch.

`scores tiers [track leg]` prints whole-map/current-leg/listed-leg ratings and,
when requested, full and compact representations. Existing `vote fake` HUD
controls accept `ratings <v1;map;...>` or `maptier <N> <source>`; `vote fake off`
restores actual serverinfo. They do not change server state or player data.

## cstrike map search

Confirmed by code AND an acted headless dedicated-socket join:
`fs_addons.default.txt` includes `steam:Counter-Strike Source/cstrike`, and this
owner's `fs_addons.txt` has it enabled. `CL_CheckFile()` asks
`COM_FCheckExists()`, which searches mounted files, before enqueueing downloads.
A client fixture with NO local BSP joined **surf_unrequited**, absent from both
Momentum's maps and this mod's maps. `flocate maps/surf_unrequited.bsp` resolved
inside the real `Counter-Strike Source/cstrike/maps` directory. There was no map
download or new map/temp file in the fixture.

The installed game's Steam library must be discoverable (or use an explicit
absolute gamedir entry / `fs_load`); an owner's existing fs_addons.txt is not
overwritten by defaults. The server must request the exact local filename.
`surf_name.bsp` does not satisfy `surf_name_css.bsp`; a same-name but different
BSP can still fail checksum/build checks. This is content mounting, not a scan
of every arbitrary folder named cstrike or automatic map-name aliasing.

## Verification and honest limits

- `pwsh -NoProfile -Command './build.ps1 -Jobs 8 -NoDeploy'` from clean inspected
  base c672f9c plus this patch: all three VMs compiled, **zero warnings**.
- `python tools/test_maptiers.py`:14 positive/negative importer and ship-entry
  controls. Includes first ratings sharing left-hand note rows, layout change,
  conflicting duplicates, independent mode/style/track selection, private-map
  exclusion, split Unit/Strafe letters and omitted-asset failure.
- `python tools/test_maptiers_runtime.py --output-dir <owned-path> --progs
  <built-dir> --zones <surf_eclipse.json> --bonus-zones <surf_ace.json>
  --css-control surf_unrequited`: actual headless CSQC through a real dedicated
  socket. Differing client/server catalogues prove server authority; independent
  MOM4/KSF6, stage2 suggestion, bonus split, compact labels, unknown stage,
  stale map, old-server fallbacks and clearing on map change pass. Actual
  `say !b 1` warp proves bonus-track HUD stats and sidebar leg table agree.
- Predecessor c672f9c with a TEST-ONLY command observing its unchanged HUD
  formatter acted as `Tier 4`; the same positive dual-source assertion failed.
- Whole-tree shipguard in a fresh source-only worktree cannot run without the
  unrelated installed particle asset directory. The targeted real-literal /
  real-release-entry gate passes and removing this entry produces MISS.
- Existing non-headless owner/peer game remains untouched. Screenshot, physical
  wheel/click hit-testing and normal/small-window appearance were NOT verified
  by the headless controls; see lextest.md. No recorder/evidence semantics,
  physics, backend/schema, identity, network download policy or content files
  were changed.

Disposable test rigs and detailed logs are owned under the task's OWNER.md root;
public source/receipts contain no player identities or raw private output.
Deployment provenance is recorded separately after actual destination checks.
