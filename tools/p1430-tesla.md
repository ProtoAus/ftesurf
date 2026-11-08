# P1430 -- point_tesla, env_beam random arcs, the generic effect-state wire

ftesurf-b8, 8 Nov 2026 (entgap-20261108, look-only group). Root C:\FTESurf-worktrees\xhair-20261108-b8
(tools/tsy.cfg, tools/arcc.cfg, tools/bmrun.sh, rigs/bm-ts-*, rigs/bm-ar-*).

## What

- cl_fx.qc (new): arc sources from the lump -- point_tesla (1,123 on 132 maps; 1,107 named, nearly all start
  off and are driven by TurnOn/DoSpark) and env_beam with no LightningEnd.
  - Tesla spark (fx.cpp FX_Tesla): beamcount beams, two thirds at even yaws with a random pitch, the rest
    random, traced to the radius (four tries), drawn to the hit; one width and life a spark.
  - env_beam (EnvBeam.cpp): RandomArea wall to wall with a clear path between, RandomPoint from its start to a
    wall at least radius/10 away; ten tries, nothing on a miss; constant width. A constant beam (life 0) with
    no end draws nothing, as BeamUpdateVars returns without its end. StrikeTime < 0 restrikes every tick
    (bhop_anomalous: 3 beams, about 100 arcs alive, as Source).
  - An arc: FX_SEGS segments, one shape for its life (FBEAM_ONLYNOISEONCE), noise scaled as DrawSegs does
    (amplitude x max(0.5, length x 0.01 pi) / 8), additive, no fade, a tesla's tapering to one unit.
  - A source more than 6000 units past its radius from the eye does not spark (no traces).
- ENTWIRE_FXSTATE 9 (sh_defs.qc): class, origin, name crc, on, event count, fresh -- read in cl_body.qc as
  ENTWIRE_PSYSSTATE2's events are (first sight fires only a fresh event). sv_entities.qc: point_tesla's edict
  (named ones only; m_bOn is a field so the stash keeps it), SV_FxInput (TurnOn/TurnOff/DoSpark), SV_FxSend.
  A state update keeps the source's own spark schedule unless it just turned on. The other look-only effects
  add classes to this wire.
- env_beam arcs switch on the laser wire (Laser_Net -> Fx_LaserNet).
- Load order traps: Sprite_Draw returned before the arcs on a map with no sprites or beams (fx_n is in its
  test now); every wire state arrives before the client's load, so fx_net AND laser_net entities are re-applied
  after Fx_LoadForMap (Laser_LoadForMap's own re-apply runs before the arc table exists). The lump is walked
  only when Sprite_LoadForMap's walk counted a point_tesla or env_beam.
- vbsp_fx_debug 1 prints the wire, each spark, misses, and once a real second the arcs drawn with CSQC time.

## Measured (client fteqw64 patch-1424)

- surf_y (21 teslas the map switches on), 60 units above the nearest, shots 2.5 s apart: 97,744 and 102,072
  sampled pixels differ; control build 531 and 312 (the chat line). Picture: blue jagged tapering arcs to the
  walls. "arcs: 21 point_tesla, 0 env_beam with no end point, 0 declined".
- bhop_anomalous (3 env_beam RandomPoint, StrikeTime -0.5): from inside the emitter, gold arcs to the walls;
  frames 600 ms apart differ by 6,886-106,866; control 0. From outside they are hidden by the emitter brushes.
- surf_hedron: 9 env_beam arcs find no wall within 256 in ten tries (Source draws nothing there too).
- A false lead worth knowing: two shots 600 ms apart came out identical because PNG writes block the frame
  loop; the realtime debug line showed CSQC time advancing.

## Review (one round, lenses: wire/control flow + SDK fidelity)

Fixed: env_beam arc state lost at load and on a sprite-cvar reload; a fixed 60 s schedule guard (an interval
over 60 s sparked every frame); re-jitter every frame, fade, the 8-unit end gap, per-beam width/life; env_beam
drawing from the origin, drawing on a miss, tapering, drawing a constant no-end beam; Fx_Net resetting the
schedule; the double count on a material failure; the walk on every map; distant sources tracing.

## Delivery

- LIVE 8 Nov ~23:45 local: 12 lobbies (one player on #10, warned; 0 QC errors) qw e49f4a34 + cs a94e4f5a from
  main bbd9fb59; both installs the same (.prev 53744f28 / 190d9980, .pre1430); csprogsvers dfe3bb01 on the Pi
  and both installs; codes.txt 102 -> 103 (.pre1430). The client half is in csprogs: players have it from the
  lobbies now.

## Left

- A tesla's sound (m_SoundName), its hit glow and sparks, m_SourceEntityName, parented teslas (56, declined).
- Templates (P1425): no point_tesla, env_beam or env_laser in the library is a template member (counted);
  env_sprite members (16 on 3 maps) come with the env_sprite follow-up.
