# P1430 -- point_tesla, env_beam random arcs, the generic effect-state wire

ftesurf-b8, 8 Nov 2026 (entgap-20261108, look-only group). Root C:\FTESurf-worktrees\xhair-20261108-b8
(tools/tsy.cfg, tools/bmrun.sh, rigs/bm-ts-*).

## What

- cl_fx.qc (new): arc sources from the lump -- point_tesla (1,123 on 132 maps; 1,107 named, nearly all start
  off and are driven by TurnOn/DoSpark) and env_beam with no LightningEnd (RandomArea from itself, RandomPoint
  from its LightningStart). A spark follows FX_Tesla: beamcount beams, two thirds at even yaws from a random
  offset with a random pitch, the rest random, each traced to the radius (up to four tries for a hit), ending
  8 units short. An arc is FX_SEGS segments re-jittered every frame (amplitude 16 for a tesla, NoiseAmplitude
  for a beam), additive, fading over its life, tapering to one unit (m_flEndWidth 1).
- ENTWIRE_FXSTATE (sh_defs.qc): class, origin, name crc, on, event count, fresh -- read in cl_body.qc as
  ENTWIRE_PSYSSTATE2's events are (on first sight only a fresh event fires). sv_entities.qc: point_tesla's
  edict (named ones only; m_bOn is a field so the stash keeps it), SV_FxInput (TurnOn/TurnOff/DoSpark), SV_FxSend.
  The other look-only effects will add classes to this wire.
- env_beam arcs switch on the laser wire: Laser_Net forwards to Fx_LaserNet.
- Sprite_Draw no longer returns early when a map has arcs but no sprites or beams (surf_y drew nothing until
  that); states that reach the client before its load are re-applied after it (they all arrived first).
- vbsp_fx_debug 1 prints the wire, each spark and the arcs drawn a second.

## Measured (client fteqw64 patch-1424, surf_y: 21 teslas, all switched on by the map at start)

- From 60 units above the nearest tesla: consecutive frames differ by 59,538-148,704 sampled pixels (the arcs,
  re-jittered); the control build's frames by 0 (271 = the chat line). The picture: blue jagged arcs fanning
  from the tesla to the walls, the map's red and green ones beside it.
- "arcs: 21 point_tesla, 0 env_beam with no end point, 0 declined". env_beam arcs share the renderer and the
  laser wire; not separately put on screen here.

## Left

- A tesla's sound (m_SoundName), its hit glow and sparks (FX_Tesla's "only spark and glow if we hit"), parented
  teslas (56, declined), template members (P1425: skip them in the walk once it lands).
