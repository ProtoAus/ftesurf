# P1433 -- env_steam drawn and switched; env_spark and env_fire inputs on the effect-state wire

ftesurf-b8, 9 Nov 2026 (entgap-20261108, look-only group). Root C:\FTESurf-worktrees\xhair-20261108-b8
(tools/p1433arms.sh, tools/stm1.cfg, stm2.cfg, fir1.cfg, spk1.cfg, rigs/bm-st*, bm-fi1-*, bm-sp1-*).

## What

- env_steam / env_steamjet (927 on 95 maps) were never drawn. cl_emit.qc's EK_STEAM: a jet on the smokestack
  look path (steamjet.cpp / c_steamjet.cpp): Rate a second along the entity's forward (env_steamjet: its left),
  +-SpreadSpeed along right and up, life JetLength / Speed, particle_smokegrenade, alpha sin(pi t) x renderamt,
  size FLerp(StartSize, EndSize, age in seconds) as Source has it, a random roll at +-RollSpeed. Lit once at load
  by the world light at the jet's middle (times rendercolor, or plus it with SF_EMISSIVE), quantised to quarter
  steps so jets in similar light share a look (STK_MAX 16). Type 1 (heat wave) is not drawn. Switched with the
  smokestacks (vbsp_emit_stack). InitialState defaults off as in the FGD.
- A named env_steam, env_spark or env_fire that starts off is now kept, stopped (em_stop), instead of skipped;
  an unnamed one is skipped as before.
- ENTWIRE_FXSTATE2 classes 5 (steam: TurnOn, TurnOff, Toggle), 6 (spark: StartSpark, StopSpark, ToggleSpark,
  SparkOnce = one burst and the think stops, EnvSpark.cpp) and 7 (fire: StartFire unless Disabled, Extinguish,
  ExtinguishTemporary, Disable, Enable; Extinguish's fade time is not drawn). Emit_FxNet matches kind, lump origin
  (a fire's draw origin may have dropped to the floor) and name crc; dispatched from cl_body.qc; states that
  arrive before the load are re-applied after it. The server keeps a named one's edict (SV_FxKeep); env_steam's
  InitialState reaches the edict through ED_ParseUnknownEpair (the key's case varies).

## Measured (client fteqw64 patch-1424)

(pending a quiet machine)

## Side finding

- C:\FTEQuake's install has no particles/ftesurf.cfg (its particles folder holds one file), so a client run from
  it draws no shared effects (sparks, fire orbs, dust); the arms copy C:\FTESurf's set into the client home.

## Left

- Extinguish's fade, Source's spark sound and glow (SF_SPARK_GLOW), the steam heat wave, env_firesource.
