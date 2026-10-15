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
A differently named/versioned file is not guaranteed to satisfy that request;
a same-name but different BSP can still fail checksum/build checks. This is
content mounting, not a scan of every arbitrary folder named cstrike. The acted
control proves exact-name reuse, not every possible duplicate/alias combination.
The mount confirmation is for the main `C:/FTESurf` install. The separate
`C:/FTEQuake` control install currently has neither addon-list file; its mount
preferences were not silently rewritten while deploying progs/tier metadata.

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
  MOM4/KSF6, stage1/tier2 suggestion, bonus split, compact labels, unknown stage,
  stale map, old-server fallbacks and clearing on map change pass. Actual
  `say !b 1` warp proves bonus-track HUD stats and sidebar leg table agree.
- Predecessor c672f9c with a TEST-ONLY command observing its unchanged HUD
  formatter acted as `Tier 4`; the same positive dual-source assertion failed.
- Whole-tree shipguard in a fresh source-only worktree cannot run without the
  unrelated installed particle asset directory. The targeted real-literal /
  real-release-entry gate passes and removing this entry produces MISS.
- The existing non-headless game was not closed or used as a subject. After it
  exited independently, graphical checks became possible; see the P724
  follow-up below. Physical input and preferred HUD scale remain human-only
  acceptance, not a claim made by the headless controls. No recorder/evidence
  semantics, physics, backend/schema, identity or download policy were changed.

Disposable test rigs and detailed logs are owned under the task's OWNER.md root;
public source/receipts contain no player identities or raw private output.
Deployment provenance is recorded below after actual destination checks.

## P724 — graphical follow-up: fit the complete bonus label

The first1280x720 screenshot exposed a real P723 fault: the complete formatter
text reached the client, but `22 * rec_sb_cw` clipped the sidebar after `KSF U:X`,
hiding `S:S`. The mono row had shrunk below the UI label's12px floor. P724
measures the header, every actual leg name and the SAME compact tier formatter
in their drawn UI-font sizes inside the existing responsive sizing loop. Insets
and the resulting width feed the board's normal column/size calculation.
`scores status` prints `track sidebar <width> label <extent> inset <padding>`.

All3 VMs compiled with0 warnings. The corrected graphical rig passed the full
real-socket controls at1280x720 AND800x600 with complete `MOM 8* KSF U:X S:S`
visible in the bonus sidebar, full bonus text in the HUD, and real UI-chain
clicks selecting the taller stage2 row. Images were opened and inspected.
A further800x600 HUD-editor arm registered the expanded map-info box including
the bonus line, with all bounds inside the window. Width witnesses included
123 >=108+14.4 for stages and128 >=113+14.4 for the split bonus. Normal/small
HUD and board images were inspected; no physical mouse/wheel test is claimed.

Commands: the same runtime script above with `--window-size 1280x720` or
`--window-size 800x600`. The script refuses a graphical launch if an owner/peer
game process exists, excluding only its own dedicated server. Screenshots plus
nonzero drawn column/type metrics and the measured-width grade are required;
headless text alone cannot pass this graphical arm. The initial graphical rig
also failed on client-only cvars sent as bare server commands; the fixture was
corrected to use `set`, and clean repeat arms passed. Those failed controls were
retained, not relabelled as product passes.

## Final delivery — 2026-10-15 UTC

**Product source:** QC `54ea7bcc83d0e0180d0d1c107bc8ced1a787fea6` (P724)
includes the original P723 feature `3088366b163f9a2afb43e08284cd9221dbaffc5a`.
Engine patch-log documentation is `85ef3e3f2f6a9f8adaada1117225ceb2a82f2d40`.
Both exact inspected SHAs were pushed to main; native pins/tags and qcbuild were
not moved. This receipt is a later docs-only commit, not another product patch.

The clean inspected QC worktree was rebuilt with
`pwsh -NoProfile -Command './build.ps1 -Jobs 8 -Pi'` from `src/`.
All3 VMs compiled with0 warnings. Before either fleet swap the official deploy
gate positively found all12 directory rows at0 players. The rating asset was
installed separately before the first swap. The final fleet restart completed
at08:18:54 UTC (all12 services active); both Windows gamedirs were verified
at08:19:13 UTC:

- `C:/FTESurf/ftesurf`
- `C:/FTEQuake/ftesurf`
- `/srv/nvme/ftesurf-server/game/ftesurf` on the NanoPi (progs + asset only;
  menu.dat remains local)

Final SHA256 values, matching BOTH Windows copies and the NanoPi where shipped:

| File | SHA256 |
|---|---|
| qwprogs.dat | `4bc9774c7b3459fd2466286dc3ec5caa0cee4134396d00cbb24d9744a3ed2446` |
| csprogs.dat | `a78f8dd66f92ff5f3caa1655c2e05107f53237f67300e9baaf030d8584213ce2` |
| maps/tiers.txt | `f653a7cccc6f58610a39ab6aab2f94a0ef75e10d8d8039446fd45eae68b4931b` |
| menu.dat (Windows, unchanged) | `44f12fd918278bd160db66f6cfb45b176d56eeb6290e3d28e6365e81e3bbcbd9` |

The deployed progs exactly hash to the bits used for the successful graphical
controls, not merely another compilation of similar source. At08:20:39 UTC,
a bounded read-only check confirmed all12 fresh lobby processes publishing the
current-map marker and EVERY expected catalogue row. A fresh headless client
with NO local CSQC and NO local tier catalogue joined a live lobby, downloaded
the exact final csprogs SHA above and reported actual `MOM tier 1 | KSF tier 1`
for surf_kitsune at08:21:36 UTC. No fake overlay was used in this live check.

Rollback: Pi retains its `.prev` progs pair. Both Windows installs retain
`csprogs.dat.pre-p724-20261015T081913Z`; the P723 predecessor backups remain
as `qwprogs.dat.pre-p723-20261015T075419Z` and
`csprogs.dat.pre-p723-20261015T075419Z`. No original asset existed before P723.
The first explicit `-File -PiGame /srv/...` invocation was refused before any
progs swap because Bash rewrote that argument as a Windows path; the documented
`-Command` invocation with defaults then passed the real fleet gate and swap.
A first minimal fresh-client fixture omitted the standard cfg tree and never
acted; the corrected isolated fixture did. Neither failed arm is counted pass.

**Workspace:** pre-existing canonical branch/ref and dirty instruction/lobby/
engine-log files were NOT switched, stashed, reverted or committed. Source is
on origin/main and in the inspected owned QC worktree, not silently merged into
those stale canonical checkouts. Do not rebuild/deploy their stale HEAD as if
it were this tested source. The owned source/evidence root is
`C:/FTESurf-worktrees/tiers-8bad691a/` (OWNER.md). All25 disposable control/build/
runtime copies were archived, verified byte-for-byte and retired. The current
QC source/current compiled outputs, opened screenshots and unique local evidence
remain. The local-only fixture archive/manifest contain unreviewed logs and must
not be exported as public reports. No owner/peer process was killed; physical
input and preferred visual scale remain acceptance in lextest.md.
