# P1162 — delivered to both Windows installs and all 12 Pi lobbies

Native `520ba3ca9` / annotated `patch-1162`, compiled QC `c79ee297`.
Both actual Windows roots and all12 active lobbies now have the scoped noclip
update. Exact current source preserves the already-live P1163 aura and P1164
paper crown; no backend operation or pending TAS activation occurred.
Human slow-flight / physical wheel acceptance is still pending.

## What changed

Two owner reports: noclip judder below host_timescale1 and walk-key/wheel speed
adjustment working privately but not in lobbies. The high-speed flicker was
confirmed noclip-only; normal movement was not widened into the fix.

The code uses the existing slow-practice presentation path with finite fast-flight
bounds, preserves Source noclip velocity outside the walking cap, and sends an
individual bounded native `cl_noclipspeed` userinfo preference instead of changing
the lobby's global `pm_noclipspeed`. Unsupported servers retain the fallback;
nonzero local seats do not mutate the primary local preference. Real placements
reach both native consumers and the default streamed CSQC body/spectator serial.

## Exact installed scope

- Actual Native base: P1158 `793ee161a`; candidate/tag `520ba3ca9`.
- Actual VM base: P1160 backport `84a8ff1a`; compiled final `c79ee297`.
- Same sole owned source pair / `deliver-noclip-1162` branches. Saved full-main
  integrations are retained separately, not activated over the installed scope.
- Nine native runtime files equal the reviewed candidate. Native pm_source.c
  and sv_tas_rewind.inc remain the actual P1158 baseline. No physical mover,
  API epoch, recorder format, practice/ranking policy or qcbuild bump.
- Pi first exposed live CSQC39518177 rather than the published Windows baseline.
  Exact whole-binary control reconstructs published P1163 inventory over84a8ff1a.
  It was preserved in Windows phase2, without replacing user data.
- A concurrent peer then changed live CSQC to9640f764 and all12 service epochs.
  The original READY failed correctly; no original native swap/restart happened.
  After the owner closed the game, exact whole-binary control reproduced9640f764
  using the PUBLIC P1164 `69fdb328a7fea9c10ee22d4e8544e183d97ef4c0`
  cl_inventory.qc over84a8ff1a. Final c79ee297 preserves that exact client file.
  Only inventory changes from the already-qualified noclip5a4c685b source;
  cl_main, all33 pose functions and the Native images remain exact.
- Current CSQC SHA256 b3ef8935baacd70101b51ebe6073d950e564480a609d9c6d176df3d6d7d32267;
  advertised/downloaded cache `32158989.dat`. SSQC54fc2f59, menu6c9f9034.

## Actual acceptance and limits

- Header-required clean all7 Windows build and ARM server+HL2 pair passed with
  exact final Native520 stamps. Official QC build0SS/0menu and the existing2CS
  F333 warnings. Native source/image closure reused, not rebuilt for inventory.
- Exact final Native images on both platforms: native selftest, all60 named
  physical rows equal, declared reconstructed historicalpin2/pin7 controls PASS.
- Actual four-case listen probes: old/disabled path frozen-camera fraction~0.72;
  current preference2/default16 zero frozen fraction; full8320 flight speed;
  normal walking control. No physical mouse-wheel claim from scripted controls.
- Eleven-scenario controlled native-QC-VM stream regression0fail/681 assertions,
  old-source29fail/664 with controls acting; all33 literal functions held. Roles,
  arrivals and clocks are controlled, not real CSQC dispatch/GPU/world physics.
- Final both-Windows28-target receipt PASS. BOTH actual installed EXE/menu/HL2+
  ImGui sets made fresh isolated lobby joins, downloaded the final CSQC, drew
  cols9/type14 boards, captured screenshots and exited0 without QC errors.
- Final Pi exact Native520 executable/plugin mappings and VM hashes PASS on
  all12 fresh service epochs. Exactly one official restart per lobby; no extra
  restart after cold joins. Fresh-epoch server journals have no QC/native errors.
- Actual owner roof/duck/high-speed noclip feel, physical wheel input and other
  players' unchanged speed remain human checks; automated results do not imply
  acceptance. No ranked finish, GPU geometry or backend acceptance is claimed.

## Preservation, including newer saves

Original snapshots, complete data/config archives, failed READY and all earlier
harness/reader failures remain retained. They were not reset or relabelled PASS.
The old local post-cold guard found later settings/cache writes; those actual
bytes were kept. After the owner closed the game, a linked explicit continuation
backed up ALL15818 current Windows protected files;40 changed old entries were
recorded, not restored. Final post-cold guard verifies all15818 unchanged across
installation, plus28 generated outputs and224 configuration files.

Pi's linked continuation first refused three changed closed data/resume files
from the same testing window. Review proved the change set was exactly those
three, with all other old data/config/links and the complete one-part boundary
held. Original refusal/old save generations remain archived. The current resume
state then received a complete separate39037-file on/offbox verified backup.
Native preflight and final under-lock commit verified ALL current closed parts,
not an old subset. Final after/cold guards verify the current protected bytes,
links, part hashes and archive unchanged. No player data/config was restored,
deleted, skipped or written by a deployment helper. Runtime-created new entries
are not a loss of old bytes. The native pair lock critical section was1.13s.

See `lextest.md` for the remaining short owner check. Source/runtime proofs and
private original/current archives stay in the same owned task; no new clone.
