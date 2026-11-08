# P1432: templated env_sprite drawn per copy (9 Nov 2026, ftesurf-3a)

From ftesurf-b8's P1431 note: SV_LateStash frees an edict inside its spawn function, so CheckSpawn freed its
P1425 template capture and SV_TplBuild never took it. Templated look-only effects stayed drawn from the lump,
where the template held them, and were never copied.

## Library (tools/census, all 2204 maps, members of a removing or keeping point_template)

- No server-only stashed class (filters, point_teleport, game_text, env_hudhint/fade/shake, model-less
  "tool" triggers) is a template member anywhere.
- Client-drawn members: env_sprite 23 on 7 maps, info_particle_system 13 on 10, point_spotlight 1
  (kz_bhop_yonkoma, in a template with movers), env_explosion 51 on 2 (all parented; P1435 declines them).
  Most are spawned by an env_entity_maker, so at another pose: bhop_crash_egypt's "CHECKPOINT" letters at the
  player for 5 s per checkpoint, bhop_exodus's pictures shown at a touch trigger, bhop_badges2 / bhop_lego
  weapon pickups.

## Change

- Server: CheckSpawn keeps the capture of an entity SV_LateStash set aside (by stash line, tpl_lrec /
  tpl_lio); SV_LateSpawnAll gives it to the re-created edict, so SV_TplBuild can take it.
- A copy of an env_sprite / env_sprite_oriented / env_glow member is a networked entity
  (ENTWIRE_TPLFX = 11, through SV_FxSend): the member's lump origin and name crc, its own pose, once; then
  its on state. ShowSprite / HideSprite / ToggleSprite reach it through SV_FxInput; Kill removes it.
- Client: Sprite_LoadForMap keeps a member's Sprite_Add arguments (Tpl_ClCopied) and does not draw a removed
  member (Tpl_ClMember); Sprite_TplNet adds an entry per copy (a removed copy's entry is reused), Sprite_TplGone
  hides and frees it on CSQC_Ent_Remove. A reload (vbsp_sprites, a new map) places the live copies again.
  Under developer, Sprite_TplNet prints each outcome ("tplfx: ...").
- SV_TplTakes leaves info_particle_system, env_laser, env_beam, point_tesla and the spotlights out, as
  before: the client has no per-copy instance of them.

Limits: a copy is matched to its member by lump origin and name; two members with both equal would draw
the first's look (none in the library). More than 64 template sprites on a map: the rest are not copied,
and the load prints it (the library's most is 10). Each copy arrives twice on the frame it spawns (two
identity sends); the second places it again into the same entry, so nothing is drawn twice.

## Review

Round 1 (one reviewer, code only), fixed in the second commit:
- A parented sprite was taken by the server and not by the client: the stash keeps no parentname. 7
  members in the library. Only an unparented sprite now keeps its capture through the stash.
- A spawnflag-1 template's copies were not drawn: the client kept keys only for removed members. Now
  Tpl_ClCopied (keeping templates too).
- Tpl_ClLoad latched an empty list if the lump was unreadable at CSQC_WorldLoaded.
- Filters and other stashed classes could become members: kept out, as before.
- A copy got no occluder skip; a member-table overflow was silent.

Round 2 (a fresh reviewer, the fix commit): no defects; the server's and the client's membership agree for
wildcards, two templates naming one sprite, parented and unnamed sprites; cl_triggers.qc unchanged. Its
library scan: 16 unparented sprite members now copied (bhop_crash_egypt 10, bhop_exodus 3, bhop_exodus_fix
3), 7 parented ones as before. The load line's count, which a keeping template would have doubled, fixed.

## Measured (bhop_crash_egypt, artifacts/p1425arm.py, private homedir, rig.lock)

- The first arm's camera (-32 -824 98) was outside the map ("VOID VIEW", cluster -1): no copy and no lump
  sprite can show from there, so its screenshots said nothing. The server side was right in it: 10 copies
  at the maker (x -112..32, y -608) and at the player for ForceSpawnAtEntityOrigin, gone after the map's
  Kill at 5 s.
- Client, developer prints: each copy matched its member and took entries 18-27; ShowSprite set them on;
  "10 of 28 passed the cull"; after the Kill 0 drawn. A copy spawned at the player facing yaw -90 was placed
  turned with the player (x 80, y -110..-254).
- Pixels from inside the map (-8 -680 98, pitch 30), P1432 against control (main be16132a), changed pixels
  against the frame before:
  - P1432: ShowSprite on the members 4.3k (background animation; the server took them out); after the maker,
    the copies 89.3k, 32 units left of the lump row as placed.
  - Control: ShowSprite draws the lump letters, 89.2k; the maker makes no copy, 2.7k.
  - P1432 show / hide / toggle: shown 87.5k; hidden back to 4.2k (4.1k after the Kill); ToggleSprite set
    them on again (its screenshot landed after the map's 5 s Kill).
- Cost: a copy is an ordinary sprite entry; placing one is one Sprite_Add and one occluder scan.

## Delivery

- LIVE 9 Nov ~10:20 local (23:14Z 8 Nov): 12 lobbies (build.ps1 -Pi from main 7845b087; nobody on; warned;
  0 QC errors in server1-12.log) qw 418199d4 + cs d24ffb5c; both installs the same (.prev 75759883 /
  a4460fd9, menu 997553ed, same source as 8904d61a); csprogsvers fc263735 on the Pi and both installs;
  codes.txt 107 -> 108 (.pre1432). C:\FTESurf fast-forwarded to 7845b087.

Left: info_particle_system members (13 on 10 maps) need a per-copy instance in cl_emit.qc; point_spotlight (1).
