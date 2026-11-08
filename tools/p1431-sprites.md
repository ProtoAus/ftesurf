# P1431 -- env_sprite show/hide and point_spotlight on/off on the effect-state wire

ftesurf-b8, 9 Nov 2026 (entgap-20261108; taken over from ftesurf-3a). Root C:\FTESurf-worktrees\xhair-20261108-b8
(tools/spr2.cfg, tools/spot2.cfg, tools/killw.cfg, tools/tsy.cfg, tools/bmrun.sh, rigs/bm-sv-*, rigs/bm-so-*,
rigs/bm-kw-*, rigs/bm-ts-mix2 with rigs-mix1431).

## What

- Before: cl_sprites.qc skipped a named env_sprite without spawnflag 1 and a point_spotlight without
  START_LIGHT_ON at load, and the server removed every one, so no input could show, hide or switch them.
  Library: 241 start-hidden sprites and 755 start-dark spotlights that maps switch on (99 + 369 start-on ones
  they switch off).
- Client: the named ones are kept in the tables, hidden (spr_hide / beam_hide, memalloc'd, cleared every load),
  with a name crc; the sprite draw, the glare trace and the shaft draw skip hidden entries. An unnamed dark
  spotlight is skipped as before (nothing can turn it on). Sprite_FxNet applies classes 3 (env_sprite,
  env_sprite_oriented, env_glow) and 4 (point_spotlight, beam_spotlight), matched on origin and name crc; states
  that arrived before the load are re-applied after it.
- Server: a named one keeps its edict (SV_FxKeep, shared with point_tesla); SV_FxInput takes ShowSprite,
  HideSprite, ToggleSprite / LightOn, LightOff, and Kill: off for good (later inputs find nothing, as in Source),
  the edict kept so a late joiner learns it.
- ENTWIRE_FXSTATE2 (10): the identity (class, origin, name) only on a source's first send to a client, as
  ENTWIRE_LASERSTATE does -- a state change is 4 bytes. The client still reads P1430's layout under 9 (its
  recordings).
- Templates (P1425): SV_LateStash removes these edicts inside their spawn, so P1425 never captures one as a
  member (CheckSpawn frees the record of a freed edict). A member is drawn from the lump in its start state, as
  before P1431. 16 env_sprite members on 3 maps; none of the other look-only classes.

## Measured (client fteqw64 patch-1424)

- bhop_rpg commentary_sprite (named, spawnflags 0: hidden), ShowSprite from three sides 40 units away: 6,630-10,105
  sampled pixels change (the checkpoint sparkle appears); control build 0-230. wiz (start on) HideSprite 38,143,
  ToggleSprite back 38,181, first vs last 352; control 1,911 both (unrelated motion). Kill then ToggleSprite and
  ShowSprite: 39,332 at the Kill, 1,479 / 1,541 after (the same unrelated motion).
- surf_orbion: "171 of 173 kept, 103 dark" (control: 68 drawn). The map runs a light show: timers switch rings of
  spotlights about 100 times a second (4,846-6,191 updates in ~50 s, about a quarter repeating a light's state,
  i.e. switched twice between snapshots). LightOn sp3/sp4: 43,719-63,591 sampled pixels; control 72. With
  identity-once no update carried a zero identity (the client joined after the show started).
- Mixed rig (live P1430 qwprogs e49f4a34 sending type 9, this csprogs): surf_y teslas arc (56,721 / 93,512). Its
  first run found the reader's `f == 9 || readbyte()` reading a byte on type 9 too (fteqcc runs both sides) and
  the client ending with "CSQC cannot remove world!"; now an explicit branch.
- Final build: surf_y teslas (type 10) 58,523 / 60,315; bhop_rpg sprite 8,925 / 8,949; orbion lit 53,795.

## Review (one round: wire, Source parity, templates, every draw path)

Fixed: template members hidden for good (no copy is ever made) and matched to any named effect at their origin;
Kill undone by a later input; unnamed dark spotlights taking table slots; the layout change in place (now 10).
Wrong in the first record: point_spotlight DOES fire OnLightOn/OnLightOff (point_spotlight.cpp:244, :418).

## Left

- point_spotlight OnLightOn/OnLightOff (12 outputs, surf_awp_sk337_v3): not fired -- the stash drops a stashed
  entity's outputs. env_sprite's Color, ColorRedValue/Green/Blue, Alpha inputs; spotlight dynamic lights;
  beam_spotlight rotation; templated look-only effects copied on ForceSpawn (needs the stash to keep outputs and
  the template capture, P1425's side).
- Sprite_FxNet scans the table per update (surf_orbion: ~100 updates x 171 shafts a second).
