# P1426 -- env_beam drawn

ftesurf-b8, 8 Nov 2026 (entgap-20261108, the look-only group split with ftesurf-3a). Root
C:\FTESurf-worktrees\xhair-20261108-b8 (tools/bmrun.sh, tools/bm*.cfg, rigs/bm-*).

## What

- cl_lasers.qc takes env_beam as a laser: start = the FIRST entity named LightningStart (BeamUpdateVars),
  target = LightningEnd, no wall trace (CEnvBeam::Strike draws entity to entity). BoltWidth is the width;
  renderamt always scales it (CBeam::Spawn forces kRenderTransTexture). A constant beam keeps its first end;
  life > 0 strikes for life seconds every life + StrikeTime, picking one end per strike.
- sv_entities.qc: env_beam is env_laser's edict (named, not SF_BEAM_STARTON: off), so TurnOn/TurnOff/Toggle
  ride ENTWIRE_LASERSTATE; Laser_Net matches the entity's own origin (las_korg).
- Report: "env_beam: N of M drawn, off, random arcs, declined, noisy drawn straight" (vbsp_ebm_*: vbsp_beam_*
  already counted the spotlight shafts -- fteqcc merged the first cut's duplicate globals without a word).

## Measured (client fteqw64 patch-1421)

- surf_canisius: "12 of 12 drawn"; the beam square over spawn on screen, none on the control build.
- surf_sh: 26 drawn, 13 start off; Jail01_Laser01 strikes after ent_fire TurnOn (frames 3-5 change 2,329-5,264
  sampled pixels, the control ~30).
- Review 1: renderamt ignored on 1,124 beams (too bright), LightningStart took the LAST entity of the name
  (surf_smart's 13 beams 140 units off), striking multi-end beams re-picked every 15 ms, two counter slips,
  an unchecked name table. All fixed; surf_smart before/after the fix: the beams' common point moves to the
  first "beam" entity (screen centre from 330 units east of it).

## Delivery

- LIVE 8 Nov ~21:55 local: 12 lobbies (one player, warned; 0 QC errors) qw 91a462f4 + cs 6f716240; both installs
  the same (.prev e1190bdf / 9d48016d, .pre1426); csprogsvers 8bae174c on the Pi and both installs; codes.txt
  100 -> 101 (.pre1426). The client half is in csprogs, so players have it from the lobbies now.

## Left

- No LightningEnd: random arcs (244 beams) -- with point_tesla's patch. NoiseAmplitude (204) drawn straight;
  SF_BEAM_TAPEROUT (36) untapered; SF_BEAM_RING not drawn.
