# P1431 -- env_sprite show/hide and point_spotlight on/off on the effect-state wire

ftesurf-b8, 9 Nov 2026 (entgap-20261108; taken over from ftesurf-3a). Root C:\FTESurf-worktrees\xhair-20261108-b8
(tools/spr2.cfg, tools/spot2.cfg, tools/bmrun.sh, rigs/bm-sv-*, rigs/bm-so-*).

## What

- Before: cl_sprites.qc skipped a named env_sprite without spawnflag 1 and a point_spotlight without
  START_LIGHT_ON at load, and the server removed every one, so no input could show, hide or switch them.
  Library: 241 start-hidden sprites and 755 start-dark spotlights that maps switch on (99 + 369 start-on ones
  they switch off).
- Client: those are kept in the tables, hidden (spr_hide / beam_hide, memalloc'd and cleared every load), with
  a name crc; the sprite draw, the glare trace and the shaft draw skip hidden entries. Sprite_FxNet applies
  ENTWIRE_FXSTATE classes 3 (env_sprite, env_sprite_oriented, env_glow) and 4 (point_spotlight,
  beam_spotlight), matched on origin and name crc; states that arrived before the load are re-applied after it.
- Server: a named one keeps its edict (SV_FxKeep, shared with point_tesla); SV_FxInput takes ShowSprite,
  HideSprite, ToggleSprite / LightOn, LightOff (no outputs: Source's fire none) and Kill (off; the edict stays so
  a late joiner learns it).
- Templates (P1425): a member is hidden on the client (Tpl_ClMember) and matched on class and origin only (a
  copy's name may carry "&0001"); a copy is networked at its spawn in its start state, and a Killed copy's edict
  goes a second later (its member is hidden in the lump anyway). 16 env_sprite members on 3 maps; an
  env_entity_maker copy away from the member's origin does not match (not drawn).
- The wire sends a source's identity (class, origin, name) only on its first send to a client, as
  ENTWIRE_LASERSTATE does: a state change is 4 bytes.

## Measured (client fteqw64 patch-1424)

- bhop_rpg commentary_sprite (named, spawnflags 0: hidden), ShowSprite from three sides 40 units away: 6,630-10,105
  sampled pixels change (the checkpoint sparkle appears); control build 0-230. wiz (start on) HideSprite: 38,143,
  ToggleSprite back: 38,181, first vs last 352; control 1,911 both (unrelated motion).
- surf_orbion: "171 of 173 drawn, 103 of them dark until the map turns them on" (control: 68 drawn). The map
  runs a light show: timers switch rings of spotlights about 100 times a second (4,846 updates in ~50 s, 1,309
  of them repeating a light's state, i.e. switched twice between snapshots). LightOn sp3/sp4: 43,719-63,591
  sampled pixels; control 72. After identity-once: 5,463 updates, none with a zero identity (the client joined
  after the show started, so first sends to a late joiner carry it).
- Rechecked on the final build: surf_y teslas arc (87,622 / 88,528 between frames), bhop_rpg's sprite shows.

## Left

- env_sprite's Color, ColorRedValue/Green/Blue, Alpha inputs; spotlight dynamic lights; beam_spotlight rotation.
- Sprite_FxNet scans the table per update (surf_orbion: ~100 updates x 171 shafts a second).
