# P1371 -- bhop maps start on the jump; zone_edit sets a map's mode and its Momentum/KSF tiers

ftesurf-3a (Claude Code), 7-8 Nov 2026. Owner: "bhop maps start on jump ... Can you ensure the zone_edit
can edit this, and the teir of the map for Momentum mod and KSF." Engine (sv_phys.c) + QC.

## What changed

- Engine SV_ApplyGamemodeModes: hosted map settings > sv_gamemode > the first loose zone file with a
  region (SV_ZoneLoad's order; SV_FindZoneFile, shared with the speed cap) naming `"gamemode"` 1 (surf)
  or 2 (bhop), compared as a 32-bit float like QC, anything else warned and ignored > mapmeta, where a
  bhop_ map the index files under a non-bhop category is bhop (src "bhop_ name") > the name. Bhop mode
  starts the timer on the jump (sv_timer.qc run_t_bhopjump reads serverinfo gamemode) and loads
  mode_bhop.cfg, so P1369's five cfg/maps/map_bhop_*.cfg go.
- Zone file keys `gamemode`, `momentumTier`, `ksfTier` (sh_zones.qc Zone_JsonId: integral, in range,
  else 0; gamemode 1..2, tiers 1..10). Not in zone_crc (BACKLOG).
- zone_edit Map properties: Surf/Bhop stay the local mode; a line under them shows the zone file's mode
  (what lobbies run). The zone file's mode changes only on a Surf/Bhop click then Save settings. Two rows,
  Momentum tier and KSF tier (0 = none), staged when edited. Mode and tiers go into the table's zone
  fields even before it has zones; Save zones writes them; Publish carries them (zonepub unchanged: it
  validates known keys and compares whole files). Save settings needs the panel open.
  `zone_edit setting momentumTier|ksfTier N`; `zone_edit status` prints the file's mode, cap, tiers.
- Server: SV_ZoneLoad republishes the main-track tier row from the zone file (MOM source "zone", shown
  by the client like a ranked tier); a warning when the file's mode is not what the server runs.
- `.rec` header (additive): `startrule jump|leave` (the map's rule; jump includes the walk-out fallback)
  and `gamemode <name|->`; grammar block; reccheck HEAD_V9.
- Menu ui_map_tick: a bhop_ map is bhop unless mapmeta says 3 (next release; not installed).

## Verification

Windows rig, server-only (control = installed fteqwsv64 e40415cb + qw db38fe13; subject = P1371):

    bhop_badwater   control: ahop from mapmeta, 66.7 Hz/150     subject: bhop from bhop_ name, 100 Hz/1000
    surf_ace (zone gamemode 2, tiers 7/5)  control: surf, row 0,0,1,rank,1   subject: bhop from zone file, row 0,0,7,zone,5
    bhop_eazy (zone gamemode 1)    control: bhop from mapmeta    subject: surf from zone file, 66.7 Hz
    agtricks (zone gamemode 2.5, later 3)  both bhop from mapmeta; subject warns "not 1 (surf) or 2 (bhop) - ignored"

Client arms (hosted game, subject build): scoreboard "main MOM 7 KSF 5" and HUD "MOM tier 7 | KSF tier 5"
(screenshot); panel screenshot with the tier rows. Round-1 flow: Surf + MOM 3 + KSF 0 -> file
"gamemode":1,"momentumTier":3, no ksfTier; reload: "surf on surf_ace, from zone file", row 0,0,3,zone,1.
rec_stream: agtricks `startrule jump` `gamemode bhop` (0.01), bhop_eazy (zone surf) `startrule leave` (0.015).
Final build (exe 0fc47fd5, qw e9e0a367): savesettings unopened -> "Open Map properties first"; local
gamemode 1 vs zone 2 -> panel note, a save stages nothing (file mode 2, not dirty); clicking the selected
Surf stages it (file mode 1 tiers 3 0); bhop_badwater with 0 zones keeps mode 2 tier 4 in the fields.
tools/p841editor.py 18/18 with an editor-format settings file (gamemode line included).
test_reccheck 949/0. zonepub.validate accepts a saved file. QC 0 warnings (fteqcc c24ede65).

Pi (ARM): branch p1371-arm = engine patch-1353 (the live lobby build, pi.dev 6 Nov) + this sv_phys.c,
764 canonical blobs verified on the Pi, binary 632ceca2 git-8486-patch-1353-1-gee74886df. Gate overlay
/srv/nvme/agent-work/p1371-3a/gate against live 7ae9b650: pm_dettest on bhop_eazy and surf_ace identical
(38 lines); bhop_badwater ahop -> bhop (bhop_ name); surf_ace (test zone file) -> bhop (zone file); agtricks
mode-3 file refused. Sweeper-form pm_verify on live data: surf_wasteland2 0022396 PASS 22396/22396 on both
binaries; surf_shy 0005532 REFUSE "a different zone table" on both (its zones changed since the run).

Runs on the five maps between P1369's delivery (7 Nov ~11:50Z) and this one: 0 (surfd runs table).

## Review

Round 1 (predicates; evidence/cheating): the verifier replays each run's own pmpin/movetickrate, so a
later mode change cannot fail an honest run. Fixed: zone-file mode limited to 1..2; `.rec gamemode`;
startrule wording; menu bhop_ rule; tier/mode staging (values lost with no zones, stale snapshots);
ze_fg tooltip. Round 2 found the redesign staged an untouched guess (the local settings file always has
a gamemode line) and mixed sources; the mode now changes only on a click; float compare. Round 3: no
medium/high; three low quirks left: the no-zones note can win over P841's when every zone was deleted;
tiers compare with the panel's open value (a reload under an open panel can mark dirty for nothing);
re-clicking the selected mode resets the local air accel to its preset (the note says so).
