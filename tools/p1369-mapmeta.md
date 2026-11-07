# P1369 -- lobbies get data/mapmeta.txt; every bhop map runs 100 tick, airaccelerate 1000

ftesurf-3a (Claude Code), 7 Nov 2026. Cfg/data only: no QC, engine or Build change.
Owner, answering P1367's open decision: "yea sure, all bhop maps should use the 100tick 1000aa rules tho."

## What changed

- Pi `game/ftesurf/data/mapmeta.txt` = the installs' file (sha1 5e6c978d, 2837 rows). Nothing deploys it
  (build.ps1 -Pi copies progs only; the release ships it to installs), so copy it up by hand after a
  tools/mapmeta.py regeneration.
- `cfg/maps/map_<map>.cfg` with mode_bhop.cfg's six lines for the five bhop_ maps Momentum files
  elsewhere: bhop_badwater, bhop_odyssey (ahop, 9), bhop_nightmare, bhop_ytt_cruma (climb-16, 6),
  bhop_canals (df-vq3, 12). That is 5 of the index's 522 bhop_ rows; none is in a lobby rotation.
- `cfg/maps/map_ahop_coast.cfg` (P1367) removed: mapmeta files ahop_coast as bhop (mode 2).
- A map cfg cannot set the mode (SV_LoadRulesetFile refuses sv_gamemode; the zone-editor mode file is
  refused on dedicated/lobby servers), so the five keep Momentum's gamemode and their timer starts on
  leaving the box (sv_timer.qc run_t_bhopjump), on lobbies and installs alike. Before this the lobbies
  started them on the jump (bhop by name). BACKLOG.

## Mode changes on the Pi's 2256 maps (name prefix -> mapmeta)

Ruleset change, all four in a rotation: agtricks (none), df_cavernish, df_yungstrafe08 (df-cpm),
kz_bkz_goldbhop_v2 (kz) -> bhop; ahop_coast ahop -> bhop (its map cfg already gave the numbers).
Same ruleset, other gamemode key: 6 bhop_ maps -> bhop-hl1 (same category, same timer rule); the five
above; conc_fal, conc_school -> sj; df_ori-dorado -> df-vq3; six kz_ maps and ph_slide_ramp,
slide_kzbr_hasty2 -> climb-16 (base both). 27 maps in all.
Every lobby now publishes maptier/maplinear/mapstages/mapbonuses/maptiersrc as installs do.

## Verification (live, lobby 12, empty; rcon from the Pi)

After copying and rcon `fs_flush` on all 12 lobbies, rcon `map <m>` then `movement`:

    movement: bhop on agtricks, from mapmeta (cfg/lobby/mode_bhop.cfg)          pm_ticrate 0.01, airaccel 1000
    movement: ahop on bhop_badwater, from mapmeta  per-map: map_bhop_badwater.cfg, 6 cvars
    movement: df-vq3 on bhop_canals, from mapmeta  per-map: map_bhop_canals.cfg, 6 cvars  pm_ticrate 0.01, airaccel 1000
    movement: bhop on ahop_coast, from mapmeta (cfg/lobby/mode_bhop.cfg)        (after map_ahop_coast.cfg removed)

serverinfo on ahop_coast: gamemode bhop, maptier 1, maptiersrc rank (mapmeta row `1 1 0 0 ... 2 rank`).
Lobby 12 was left on ahop_coast, its map before the test. An rcon `map`'s own load lines reached neither
server12.log nor the rcon reply; `movement` afterwards is what shows the ruleset.

## Delivery

- Pi, 7 Nov ~11:47-11:55Z: data/mapmeta.txt 5e6c978d, five map cfgs (hashes as committed),
  cfg/lobby/lobby4.cfg comment, map_ahop_coast.cfg removed; no lobby restart (each lobby picks the
  file up at its next map load).
- Installs: the five map cfgs and the ahop_coast removal, after ftesurf-1d's native install (see the
  delivery commit).
