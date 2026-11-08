# P1433 -- env_steam drawn and switched; env_spark and env_fire inputs on the effect-state wire

ftesurf-b8, 9 Nov 2026 (entgap-20261108, look-only group). Root C:\FTESurf-worktrees\xhair-20261108-b8
(tools/p1433arms.sh, tools/stm1.cfg, stm2.cfg, fir1.cfg, spk1.cfg, rigs/bm-st*, bm-fi1-*, bm-sp1-*).

## What

- env_steam / env_steamjet (927 on 95 maps) were never drawn. cl_emit.qc's EK_STEAM: a jet on the smokestack
  look path (steamjet.cpp / c_steamjet.cpp): Rate a second along the entity's forward (env_steamjet: its left),
  +-SpreadSpeed along right and up, life JetLength / Speed, particle_smokegrenade, alpha sin(pi t) x renderamt,
  size FLerp(StartSize, EndSize, age in seconds) as Source has it, a random roll at +-RollSpeed. Lit once at load
  by the world light at the jet's middle (times rendercolor, or plus it with SF_EMISSIVE), quantised to quarter
  steps so jets in similar light share a look (STK_MAX 32). Type 1 (heat wave) is not drawn. Switched with the
  smokestacks (vbsp_emit_stack). InitialState defaults off as in the FGD.
- A named env_steam, env_spark or env_fire that starts off is now kept, stopped (em_stop), instead of skipped;
  an unnamed one is skipped as before.
- ENTWIRE_FXSTATE2 classes 5 (steam: TurnOn, TurnOff, Toggle), 6 (spark: StartSpark, StopSpark, ToggleSpark,
  SparkOnce = one burst and the think stops, EnvSpark.cpp) and 7 (fire: StartFire unless Disabled, Extinguish,
  ExtinguishTemporary, Disable, Enable; Extinguish's fade time is not drawn). Emit_FxNet matches kind, lump origin
  (a fire's draw origin may have dropped to the floor) and name crc; dispatched from cl_body.qc; states that
  arrive before the load are re-applied after it. The server keeps a named one's edict (SV_FxKeep); env_steam's
  InitialState reaches the edict through ED_ParseUnknownEpair (the key's case varies).

## Measured (client C:\FTEQuake\fteqw64.exe c61f874b, 9 Nov; 0 QC errors in every run)

Builds: new cs 0227027f (review 1) and 2057bc6f (+ the SparkOnce print), qw 8e17de2e; control = live P1431
cs a90ec502. Pixel diffs every 2nd px; the HUD chat line alone is ~500.

- Steam always on (surf_sluice2, 4 unnamed jets, InitialState 1, tools/stm3.cfg from between them): new q1->q2
  17358 and q3->q4 19160 px, white jets pouring from the ceiling vents; control 759 / 1, no jets.
  (The first cut, stm1.cfg, faced a wall and measured nothing: 701 px of dust motes in both.)
- Steam switched (bhop_rpg st1, a red and a blue jet): TurnOn draws both (q1->q2 48528 px), TurnOff removes them
  (q1->q4 1274, back to the start frame); control 7041 / 1420 with no jets. Wire: 4 class-5 states.
- Fire with fuel (bhop_maya FIRE2, StartDisabled, health 30): StartFire while disabled does nothing (534, the
  HUD line); Enable + StartFire lights it (10687 px); 33 s later it is out (534 vs the start frame); StartFire
  again does nothing (0 px) -- burnt out for good, as SF_FIRE_DIE_PERMANENT.
- Fire switched (surf_vegetables microwave_fire, 3 flames): flames above and beside the box after StartFire,
  none after Extinguish (q1->q4 0 px).
- SparkOnce (bhop_depot spark1): 25 inputs from the arm plus 3 from the map's own logic, 28 "emit: spark once"
  lines, each 27 particles. The sparks themselves were not seen in a screenshot -- see Left.

## Side finding

- C:\FTEQuake's install has no particles/ftesurf.cfg (its particles folder holds one file), so a client run from
  it draws no shared effects (sparks, fire orbs, dust); the arms copy C:\FTESurf's set into the client home.

## Left

- Extinguish's fade, Source's spark sound and glow (SF_SPARK_GLOW), the steam heat wave, env_firesource.
