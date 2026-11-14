# P1559-P1563 -- Lex's list of 15 Nov 2026 (ftesurf-16, root C:/FTESurf-worktrees/lexlist-20261115-16)

Source: FTESurf main `5b5ca243` (P1561 `04298f18`, P1559 `31dec364`, P1562 `3335e335`, P1563 `a1595740`, review
fixes through `5b5ca243`, docs `c5d3b751`); ftequakers main `6c7b63b4e`, tag `patch-1559` (P1559 `53116cf6e`,
reviews `b1f2b588c` `cbb4ba87a`, patch log `6c7b63b4e`).

## What each item became

| Report | Outcome |
| --- | --- |
| surf_1day stage 6 booster 1000 vs ~2000 | KSF demos: *125 at 2100, *82 inert. entfix (P1562) |
| Jail teleports stick (surf_forbidden_tomb) | Map round logic enables them map-wide; three outputs removed (P1562) |
| surf_legends fog | Half density, double distance like sidistic (P1559) |
| network2008 start faces the corner | P890's own entfix yaw 135 -> 270 (P1562) |
| surf_tendies booster lag at sv_minping 500 | Predicted (P1563) |
| Late boarding info at ping | Not done: BACKLOG (export the mover's board latch from prediction) |
| surf_beyond dust leaves its brush | In-brush point pool (P1559) |
| Reflective glass not solid / hovering | Solidity 1 = never solid in Source; the platform prop (scale 2) collides at scale 1: BACKLOG |
| custom_particle_003 black | Its spiral is the child systems; children on by default (P1559) |
| Ramp texture tiled tiny | Brush-only 32-unit emissive UV fix applied to model materials (P1559) |
| Logo/models culled early at screen edge | Cull radius x scale in three places (P1559) |
| beyond/beyond2 fails and resets face wrong | Resets fixed (spawn yaw rules, P1561); fails not reproduced as wrong |
| beyond2 floor not reflective | Black LDR cubemaps -> float .hdr.vtf (P1559) |
| beyond2 portal shader | Child psys; refract tiling (texdata 128) left: BACKLOG |
| beyond2 ramps transparent | Emissive drawn over the opaque base (P1559) |
| surf_ace seams leak light | vbsp's crack-free face lists (P1559); owner check |
| Demo head-duck view | Replays/rewind/save lead clip the eye (P1559) |
| surf_reytx b2 hoop never finishes | Own-track covered END ranks first (P1561) |
| KSF auto-zoned maps (interstellar) | Not done: BACKLOG (named-trigger zones, zonecrc impact) |
| Send save with segments/demo line/helper name | ROADMAP with design; decisions owed |
| ahop_coast grass sprites | Wrong sprite sheet mounted first: BACKLOG |
| bhop_coast / surf_mesa(_revo) / ahop_coast !r below the platform | Floor snap from a unit up (P1561); ahop_coast's facing is its zone file's |
| surf_null grate two frames late | TEXTUREFLAGS_NOMIP honoured (DXT); a frame delay was not found |
| surf_leesriize props missing | Not reproduced; scaled-radius culls fixed (P1559); owner check |

## Verification (all on the PC, i9-9900K / RTX 2080 SUPER)

- Rig (conbridge, worktree build against the installed control): see each commit body. Key numbers: surf_mesa
  zone_goto 0 at 10144 (control 9490, falling); beyond2 yaws 0/0/-90 (control 148/158/38); network2008 -90
  (control 135); tendies 4/4 predicted rename + exit boost with no prederr (control 4/4 prederr 20.05 u);
  bhop_tranquility replay eyes 33-63 under ceilings (control never below 47); dust "105 points inside".
- Reviews: P1561 three rounds (control flow, evidence, cheater; final census 28 covered ENDs over 1164 zone
  files, board DB holds no lobby/uploaded run on a covered map+track), P1563 three rounds, P1559 two rounds.
- tools/test_entfix.py's applier over the three maps' real lumps.

## Delivery (UTC 14 Nov 2026 = local 15 Nov)

- ~19:55Z both installs: engine `git-8758-patch-1559-0-g6c7b63b4e` (one stamp; check_tls_refptr 10 symbols, 0
  uses): C:\FTESurf ftesurf64.exe `35d8dbfa` (.prev `796f5019` = P1550), fteplug_hl2 `3b05bfe8`, ui_imgui
  `05e7def8`; C:\FTEQuake fteqw64 `35d8dbfa`, fteqwsv64 `98485cc8`, hl2 `3b05bfe8`, cod `a9ce4709`, box3d
  `907ab9c8`, ode `effb2f77`, ui_imgui `05e7def8` (.prev kept).
- 20:00:51Z Pi cfg/maps under /tmp/surfd-sweep.lock: entfix_surf_1day `dd1a80b5`, entfix_surf_forbidden_tomb
  `d867460e`, entfix_surf_network2008_final `64ddb43c` (old `37100699` kept as .pre1562-20261114T200051Z).
- ~20:01Z build.ps1 -Pi from a clean worktree at 5b5ca243: nobody on, 12 lobbies restarted; qwprogs
  `b8289f17`, csprogs `0b0aa139` (.prev `c3c28ffa` / `aae6269a`); all 12 active, 0 QC errors since spawn.
  tasrevd codes.txt 139 -> 140 (.pre1563).
- Both installs: QC `b8289f17` / `0b0aa139` / menu `91b96cad` (.prev kept), cfg default.cfg `b82050b9`,
  defaultuser.cfg `d1fbfbbe`, the three entfix files; lobby csprogs seeded as csprogsvers `e46e9dc9`.
- 20:05Z tools/pi_lobby_smoke.py (patch-1559 client, pinned expected csprogs) against 27510: served csprogs
  0b0aa139, board drew, no QC error, screenshot -- PASS.

## Limits

- The reytx bonus-2 finish, surf_ace seams, surf_null grate, leesriize props, forbidden_tomb after 420 s and
  1day's stage 6 speed are owner checks (lextest). Players get the engine half with the next release; the
  entfix files and default.cfg likewise ship with it (clients without them mirror their own lump).
- Earlier runs on surf_1day, surf_forbidden_tomb and surf_network2008_final no longer verify (entfile).
- C:\FTESurf is a stale checkout (567 commits behind, others' tracked edits): its cfg files now show as
  modified with main's content; it was not fast-forwarded.
