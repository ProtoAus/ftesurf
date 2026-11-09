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

## Particles (second half, 9 Nov)

Library: 13 templated info_particle_system on 10 maps. 10 are unparented with a bake line and are now copied:
boosters on bhop_lego2, bhop_japan, bhop_nature, bhop_rin, bhop_epiphany2 and bhop_angst (2), bhop_crash_egypt's
TNT and Nitro explosions (8 child systems each). The other 3 stay as before: surf_network_2013's (parented),
surf_spaceship_ksf's two (parented, no bake), bhop_shutdown2's (no bake). None of the 10 has a rope, an orbit
or a never-dying glow, and no two share a name at one origin.

- Server: CheckSpawn keeps the stash capture of an unparented info_particle_system too; SV_TplTakes takes it.
  A copy is ENTWIRE_TPLFX class FX_CLS_PSYS (11): the identity as for sprites, then ENTWIRE_PSYSSTATE2's on,
  start count and fresh flag. Start/Stop reach it through SV_PsysInput (SV_PsysSend hands a copy to
  SV_TplFxSend); Kill removes it. A copy that starts active counts a start, as Source's starts on spawn.
- Wire: the flag byte's TPLFX_V2 bit marks the identity with the copy's instance number (tpl_instof) and a
  three-byte tail for every class; sprite recordings from before it parse as written.
- Client: Emit_LoadForMap's EK_PSYS arm is Emit_PsysAt (same code, map load unchanged), so a copy makes its
  system's emitters at its own pose (Emit_TplNet, ranges in tplr_*). A removed copy's emitters stop and wait;
  the next copy of that member writes over them in place (same member, same emitter count per load). Copy
  emitters carry em_tnc EM_TNC_TPL: lump systems' state messages pass them by. A copy on an edict whose last
  copy's remove was lost (instance number or class changed) frees the old one; an edict that held a copy and
  now carries any other wire frees it (tfx_held). emit_list counts the members drawn per copy.

Limits: a rope or orbit a member starts is not drawn per copy, and a copy places no never-dying glow (it
could not be taken back on Kill); none in the library. More than 32 templated systems per map, or 64 copies
alive at once, are not drawn (developer says so). With two packet losses in a row (a lost remove, then the
reused edict's identity lost) one state message can reach the old copy's emitters until the identity
arrives; a lost remove on the same edict exactly 10000 instances later counts as a duplicate.

Review (one reviewer per round, code only):
- Round 1: the arm's move confirmed identical. Fixed: the tail's length depended on the class, which a
  state-only send to a client that missed the identity could not know (CSQC block desync); a copy that starts
  active never fired; never-dying glows would stack per copy; map systems at a copy's spot switched it; an
  edict reused for the other kind kept the old instance; report counters drifted.
- Round 2: those fixes confirmed. Fixed: a lost remove plus edict reuse kept the old member's emitters
  (instance number added); any other wire on a held edict leaked it; the sprite layout change would have
  broken recordings made since the sprite deploy (TPLFX_V2).
- Round 3: no defects; four packet-loss notes, three closed (identity cleared on a drop, generations reset on
  any first hold -- spr_hide could be written unallocated before the first sprite load -- class change is a
  new copy, the spawn frame's duplicate identity no longer re-adds a sprite). A quick check of that: none.

Measured (bhop_crash_egypt, the letters' vantage -8 -680 98, copies spawned at the player -8 -608 98):
- sound_maker_TNT (Start at 4.1 s, Kill at 6 s): the copy placed 8 emitters at the player, fired one start at
  4.1 s; the explosion changed 348k px (261k-452k across the fix builds) against the frame before; the copy was
  gone after the Kill. Control (main 75b972c9): no copy, a faint puff at the template's own spot (16k px).
- sound_maker_TNT2 (Start in the spawn frame, Stop at 2 s): one start fired, the spawn frame's duplicate
  identity fired none, the Stop arrived; the second copy reused the first's emitter range.
- The control's lump system started by name at its spot drew 143k px: this rig draws the map's bake.
- bhop_lego2, the booster pad's own output (boost_maker ForceSpawnAtEntityOrigin !activator; Start at 0.02 s,
  Kill at 1 s), camera on the spawn looking down: the copy's one emitter at the player drew the green boost
  glows, 150k px, then 2.5k (background) after the Kill; a second boost reused the range, 72k px. Control: no
  copy, 2.5k throughout. (A first pair shot from 600 up was outside the map, VOID VIEW, and measured nothing;
  one post-Kill frame of a TNT run moved 386k px when the window took focus, same brightness: left out.)
- Sprites re-measured on every fix build: shown 87k px, hidden back to background, removed by the map's Kill.

Delivery: LIVE 9 Nov ~11:38 local (00:38Z): 12 lobbies (build.ps1 -Pi from main d079fb0b; nobody on; warned;
0 QC errors in server1-12.log) qw 9cad7952 + cs 72715416; both installs the same (.prev 418199d4 / d24ffb5c,
menu 997553ed unchanged); csprogsvers cbb19469 on the Pi and both installs; codes.txt 108 -> 109
(.pre1432b). C:\FTESurf fast-forwarded to d079fb0b.

Left: point_spotlight (1, kz_bhop_yonkoma, in a template with movers).
