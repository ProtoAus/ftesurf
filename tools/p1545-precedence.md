# P1545 -- the 13 assignments that kept only their first operand

Owner: ftesurf-e7 (Claude Code), 14 Nov 2026. Task root C:/FTESurf-worktrees/precedence-20261114 (OWNER.md).
Lex (14 Nov): tackle the 12 sites P1544's scan put in BACKLOG.

## The trap

fteqcc keeps id's table (flag_cpriority off): `=` and `?:` priority 6, `&&` and `||` 7. So `x = a && b`
compiles as `(x = a) && b` and x holds `a`. An asm probe (`-Fwasm`, fteqcc 1f2efd06) confirmed it
(`STORE_F ga, g1; AND_F ga, gb, temp`), and also: a local initialiser (`float d = a && b;`) and a ternary
branch are whole expressions; `a || b && c` is `(a || b) && c` (equal priority, left to right);
`!a == b` is `!(a == b)` but warns F304, and the build is at 0 warnings.

## Scan

precscan2.py (task root): statements split on `; { }` across lines, comments and strings stripped, a
top-level `&&`/`||` right of the first top-level `=`; for-header increments and initialisers excluded.
Before: 13 sites (P1544's 12 + src/milk_sys.qc:187, at the src root P1544's scan did not cover). After: 0.
mixscan.py: one `&&` then `||` mix in all of src (sv_tasoptimize.qc:2748, `A && B || C`, the same in
either table); no `a || b && c`; no compound assignment (`|=`, `+=` ...) with a top-level `&&`/`||`.

## The sites (old value -> new)

| site | old | new | live effect |
|---|---|---|---|
| cl_triggers.qc:1981 probe, :2779/:2888 hit | trace_startsolid | the full test | none: a zero-length trace takes the point tests, which set allsolid only with startsolid and never move fraction (BIH_Trace -> BIH_RecursiveTest for Source submodels, Q1BSP_RecursiveHullCheck's point branch, CM_BoxTrace's position test); TG_Overlaps already returned the full test |
| sv_main.qc:158 vbsp_retrigger | lobby_enable | && lobby_retrigger | none: every lobby runs lobby_retrigger 1 (Pi cfgs read 14 Nov); `lobby_retrigger 0` now works as lobby.cfg documents |
| sv_vote.qc:615 vote_on | lobby_cycle > 0 | && a rotation exists | none: all 12 lobbies have 6-10 maps (Pi); a lobby with fewer than 2 maps now has no vote |
| milk_sys.qc:187 milk_hasvis | snd_getvis exists | && snd_visimage exists | none on current engines (both); an engine with only the first no longer aborts the VM on snd_visimage |
| cl_portal.qc:676 lpd_active | partnered | && startactive && !StartDisabled | the lump-time guess until the door's state arrives (IGNOREPVS, re-applied after the lump): 5 maps have partnered doors that start inactive (surf_tripportals 14, bhop_flything, bhop_greybox, bhop_parallel, bhop_tripportals 1 each; portaldoors.py over 2204 .bsp) |
| cl_zones.qc:638 pvs | zone_pvs | && not zone_xray && editor closed && eye not in solid | normal play unchanged; zones are no longer PVS-culled under zone_xray, in the zone editor, or with the eye in a wall (P1285's intent) |
| cl_entview.qc:2188 onpanel | mouse seen | && pointer over the panel | ent_cursor: a click on the world picks again; the wheel off the panel goes to the game (+jump) again. Dead since 13 Sep |
| m_milk.qc:529 want, :734 orbit | slot / milk_panels | the full tests | only with milk_panels 1 (default 0): the panel lights as the camera arrives and powers down off panel screens; the camera orbits only with a panel |
| sv_tasproject.qc:1017 named | named | && the slot is still that row | only with a full checkpoint list (48): the head slot no longer takes a named row's name |
| sv_entities.qc:12175 vbsp_sp_sky | the parent's own mark | parent's or a member's | none on today's maps (census below); a chain whose rider alone carries the sky mark is now sent whole, so the rider draws |

## Measured

Sky chains, the one site where a map decides whether anything changes. Only P1202's sky marks give a chain
member PVSF_IGNOREPVS when SV_SpResolve runs (follows are prop_* only; trains, FX and portals are not members),
and they need a sky_camera, so the candidates are the maps with a sky_camera and a parented spinner:
skychains.py over the 2204 .bsp in Momentum's maps folder -> 65. Dedicated fteqwsv64 (C:/FTEQuake, 5c98d0ac),
svarm.py, `developer 1`, the spin line now ending "(N drawn by csprogs, M always sent)". Fix qwprogs
bcb6f7c6 against a control (the same tree with only line 12175 unbracketed, e043650a).
- One server for all 65 died at map 17 on the dedicated server's model table (MAX_MOD_KNOWN); batches of
  10 after that. The last control batch was stopped by Claude Code for low memory; rerun on Lex's word
  (same control build, all 9 maps).
- 61 maps print the line (the other 4 have no csprogs chain: three are func_door_rotating roots, one
  movelinear's only child is a trigger). Fix and control print the same line on all 61.
- The counter discriminates as far as counting goes: surf_destruction 6, surf_hourglass(_css) 4,
  surf_happyhug / surf_surreal(_css) 1 always sent -- chains whose root carries the mark itself.
So no map in today's library changes; the fix is for a chain whose rider alone is in the sky.

Not run, by design: the trigger probe is shown identical by the trace code; the portal guess is
overwritten by the door's state (always sent, re-applied after the lump); retrigger and the vote read the
live Pi cfgs (lobby_retrigger 1, every lobby 6-10 maps, lobby_cycle 3600); the menu sites are off by
default (milk_panels 0); zones change only in xray/editor/eye-in-solid. Build: 0 warnings (fteqcc 1f2efd06).

## Review

One round, two reviewers on the commit (7a4db4a9), read not run. Intent lens: all 13 correct, none
missed (its own tokeniser over 216 src files + 34 tools fixtures finds exactly 13 at the parent, 0 after),
no `||`-then-`&&` mix; noted `a && b ? c : d` is `a && (b ? c : d)` (no instances) and that the two
cl_triggers diagnostics still omit `trace_fraction < 1` (text only). Consequences lens: nothing that can
rank a run, touch a recording or harm a server; every operand was already evaluated (no short-circuit),
so no new builtin call, argv clobber or frame cost; TAS revsha differs only in the full-list case and
tasrev.py verifies both forms; sky chains only gain PVSF_IGNOREPVS (csprogs chains, non-solid).
Its one correction is in the table above (point tests, not the sweep's `d1 > 0 && d2 >= d1`).

## Delivery

LIVE 14 Nov 2026 ~00:51Z (11:51 local). Main 35105611 (code ad0f7add = 7a4db4a9 rebased over P1546, which
touches no src; compiler 1f2efd06, 0 warnings).
- 12 lobbies: `build.ps1 -Pi -QuakeDir <missing>` from deploy/p1545-precedence 21167906 = deploy/p1544-savelock
  37f65fe9 (the live P1544 source; P1542/P1543 still not lobby-delivered) + P1545's code. Live hashes checked
  first (37ef9e41 / dd6d6c63). One player (lobby 11) got the warning and countdown; all 12 restarted and
  active, logs clean from SpawnServer. Live qwprogs 0aa19d14 / csprogs 8df4b1bf, .prev = P1544's pair.
- Both Windows installs (C:/FTESurf, C:/FTEQuake): qwprogs bcb6f7c6, csprogs d27da0a6, menu eb072f13 (+ .lno)
  from main's build, .prev = 7040dda7 / 620c4da4 / 1c8bb7c8 (what P1543/P1544 left); csprogsvers seeded
  (8a2d283b). Smoke: 25 s headless local game on C:/FTEQuake, server and CSQC loaded, no errors
  (artifacts/install-smoke.log in the task root).
- tasrevd codes.txt 131 -> 133 (8df4b1bf, d27da0a6; backup codes.txt.pre1545).
