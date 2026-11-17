# P1593 delivery -- World of Surf names, stage 1 (17 Nov 2026)

Stage 1 = readers that understand both identities; nothing a player sees changes until the stage-3 release.
- Engine main 1e5888f9a = tag patch-1593 (git-8841-patch-1593-0-g1e5888f9a): dual-identity update contract
  (qkupdate.c) + gamedir alias (fs.c, cl_parse.c, cl_demo.c, cl_main.c, sv_main.c). ENGINE_PATCHES Patch 1593.
- Game main 6d94957a..0948133b: tools/updatefeed.py (two identities, strict envelopes and default.fmf, one version
  line), launcher harnesses on allowed arguments, ftesurf.sh/.bat comments, cl_zones.qc accepts worldofsurf.
- Launcher (Quakers-Launcher) main 200af7f: identity marker `.ftesurf-updater/identity`, 2-of-3 .dat fallback,
  argument allowlist, per-identity feed URL `ftesurf/worldofsurf.json`, strict envelopes. Ships with the next release.
- Installed both installs 17 Nov ~10:15 local: client bfd20c21 (C:\FTESurf ftesurf64.exe, C:\FTEQuake fteqw64.exe),
  fteqwsv64 3c8017e6, hl2 11261f8d, ui_imgui a1d1df9e; C:\FTEQuake cod eb14f416, box3d 22cfee24, ode aa571369
  (.prev = P1594's). Local-game check on this exe: p1592seg finish writes `_segmented.rec` (flags 133257).
- Verified before integration: test_update_identity.py 102/102 win64+linux64 (35 mutants each), test_update_tiers,
  launcher 58+7 tests (23 mutants), updatefeed 26 tests (34 mutants); alias rig forward / list / offline download with
  controls. Reviews: contract five rounds, alias two (nothing above Low at the end).
- Lobbies: no change needed (they keep `ftesurf`); cl_zones.qc rides the next lobby QC deploy.

Next: stage 2 (launcher moves `ftesurf/` -> `worldofsurf/` with the marker, journalled), stage 3 (release, new feed,
the legacy feed's last release points at the new launcher; INSTALL text in tools/p1593-claim.md).
- cl_zones.qc reached the lobbies and both installs in P1598's deploy (17 Nov, cs 83467981); both installs' engine is
  now patch-1598 (client 424548fb), which carries patch-1593.

## Stage 2 -- the launcher moves the folder (pushed 17 Nov; ships with the stage-3 release)
- Launcher (Quakers-Launcher) main 200af7f..e1f731d: src/ftesurf_migrate.rs -- when a signed worldofsurf feed exists
  (`ftesurf/worldofsurf.json`, not older than the ledger), ask, stage and verify first, then a journalled move
  (`.ftesurf-updater/migrate.json`: intent + barrier -> legacy exe parked + `ftesurf/`->`worldofsurf/` -> ledger keys
  respelled and the legacy update_manifest_url line dropped -> marker ftesurf->worldofsurf, the only rewrite allowed),
  then the ordinary verified update; finish() deletes parked exes only on a ledger-hash match. Approved envelope staged
  as move-feed.json (sha256 + version in the journal). Never on --wait-for-game; clean-up can finish offline.
- Game main adffcbc4..709f6e61: tools/updatefeed.py refuses a worldofsurf feed whose default.fmf the move refuses (one
  DISABLEHOMEDIR 1, MAINCONFIG ftesurf|worldofsurf); stage-3 notes in tools/p1593-claim.md.
- Verified: 65 lib + 7 bin + 37 integration tests (Windows), 66 + 7 + 32 (Linux); real-binary smoke 15/15; mutants per
  round (26, 34, 55, 61, 17, 12, 6, all killed). Reviews: seven rounds (no High; the last Mediums fixed and re-checked).
  Not done: a production-key run, a real engine against a moved install (stage 3's acceptance).
