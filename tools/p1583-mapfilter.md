# P1583 -- map picker: the bhop family under Bhop; zones found where the game reads them

Owner: ftesurf-06 (Claude Code), 16 Nov 2026. Task root C:/FTESurf-worktrees/savelock-audit-20261116 (OWNER.md).

## Report

Lex (16 Nov), relaying a player: "would be nice to have coast in all bhop related modes like in mommy mod". Lex:
new bhop modes are coming (HL2 movement, HL1/AG movement); let people see any bhop map in any of them, filtered to
their own category by default, with an option to show other categories.

## Found

- The picker is P1160's Surf/Bhop switch: a map is listed when its category (Momentum's gamemode, else its name
  prefix: m_main.qc ui_cat_load) is the switch's. Momentum files ahop_coast as bhop (mapmeta mode 2), so it is under
  Bhop; the other 27 ahop_ maps (mode 9, HL2 movement) and climb/kz (modes 5/6) were never listed.
- "Zoned" (P1111: without zones a map waits behind Show all) probed only maps/zones/local and online, while
  Zone_Load (cl_zones.qc) also reads curated/ and dl/ -- where cl_zonedl.qc puts zones fetched from the server, under
  data/. On the owner's install 585 names are zoned only there; 70 are not covered by the download list's own zoned
  column, 53 of them bhop by mapmeta (34 bhop, 19 bhop-hl1, mostly kz_bhop_*): hidden from Bhop though zoned.
- Movement: the server picks a map's mode (sv_phys.c SV_ApplyGamemodeModes) and loads cfg/lobby/mode_<mode>.cfg,
  else mode_<category>.cfg. Only mode_bhop.cfg exists, so bhop-hl1 maps play bhop, but ahop_ and kz_ maps play the
  base (surf) settings until their mode's ruleset exists. Not changed here.
- Downloads offer surf/bhop only (maproster.py, mapscan.py, m_lobby.qc Mdl_Row, surfd mapmanifest.py): an ahop or
  kz map a player does not have cannot be fetched from the menu. Not changed here.

## Change (menu only)

- Under Bhop, two chips beside the switch: "+ ahop" and "+ kz/climb" (`ui_maps_also`, archived, default 0 = the
  switch's own category). Not offered under Surf; rj/sj/df/conc stay out (P1160).
- The zone probe reads every folder Zone_Load reads, plain and under data/.
- Bootcheck: Bhop alone, then both chips (must list more), the screenshot with the chips lit; the zone probe's own
  count of rows zoned only in curated/ or dl/.

## Measured

See "Bootcheck" below (filled from the run).
