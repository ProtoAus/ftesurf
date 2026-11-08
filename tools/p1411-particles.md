# P1411 -- library particle bakes, the index loader, PS_MAX

ftesurf-b8, 8 Nov 2026. Root C:\FTESurf-worktrees\xhair-20261108-b8 (bakes in pbake/gd, arms in rigs/pz*).

## What changed (main b92bf3ed)

- `Emit_PsysLoad` read at most 4096 lines of data/mapparticles.txt, ONE file for every map. With the library
  baked (122 maps, 6094 lines) the 31 maps past that line loaded nothing: surf_sirena's bake created 0 of 426
  emitters on the old build, 426 on the new. Bound 65536; past it, and past PS_MAX, a console line says so.
- PS_MAX 64 -> 512 (surf_sidelines 351 rows; 28 maps had more than 64). The ps_* tables are memalloc'd: as
  globals, 256 hit "Too many globals" (the def table; P1412's -Fomitarraydefs has since lifted that).
  strzone names in memalloc memory: precedent since P940/P1239 on released engines (the GC scans the blocks).
- `trail` rows capped at PS_MAX per map (each walks ps_n: a crafted index could pass qclib's runaway limit).
- pcf.py: "emit noise" emitters baked at (max(min,0)+max)/2 (63 systems; bhop_rpg 0 -> 21).
- sourceassets: BSP pak lump cap 1 GiB (kz_bhop_badg3s 440 MB); per-asset MAX_FILE unchanged.
- prederr_replay: default client C:\FTEQuake\fteqw64.exe, and it prints the client's hash. That install's
  ftesurf64.exe is a stale patch-1306 build; replays before this ran it.

Arms (build 888be4f1 / c83793a1): sidelines 230 systems + 121 links = 351; crafted index (zenith + 600 rows)
"96 psys rows past PS_MAX 512; dropped", 512 kept; aberrant 128 created, zenith 120. Review: one reviewer,
no defects; its two notes fixed (dropped-row lines, trail bound).

## Delivery

- LIVE 8 Nov ~15:23 local: 12 lobbies (nobody on) qw 63fa2880 (unchanged) + cs 3a379a1b, fteqcc 73f9a1a4;
  both installs the same (.prev = 63fa2880 / fa957ba9, .pre1411); csprogsvers a6e54096.dat on the Pi and both
  installs; codes.txt 95 -> 96 (.pre1411). 0 QC errors in the 12 lobby logs.
- Bakes installed 8 Nov ~16:10 local in C:\FTESurf\ftesurf only (118 new cfgs, 4 unchanged; index 6094 lines,
  2.5 MB of cfgs); backup of the old index in the root's backup/. The next release carries them; not C:\FTEQuake.

## Open

- Frame cost, measured (client 824d41cc, bhop_aberrant spawn, r_budget 3, matched): 0.97 ms a frame without
  the bake, 1.41 ms with it (~4500 particles): particles 0.19, Emit_Frame 0.09, transparent draws 0.07.
  timerefresh reads ~100 vs ~6000 fps and its first pass takes 83 s -- on the 5 Nov build too, so it is no
  recent patch -- but play shows no stall (the dump schedule ran to the second), so it is timerefresh only.
- One-shot effects: 1020 rate-0 systems, 820 used by no entity; 200 used on 29 maps (~150 fired by map logic,
  ~33 once at start, ~19 never-dying sprites). Needs an EVENT on the wire (a start counter on a new ENTWIRE
  type): Patch 1028 sends on/off state only, and a second Start on a running system must fire again.
- surf_map_h / surf_map_njv: two pak entries 4 bytes off their headers (packing-tool bug); not baked.
- surf_sirena's 500 systems are start_active 0 and unnamed: invisible in Source as here.
