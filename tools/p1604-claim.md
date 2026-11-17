# Patch 1604 claim (Claude Code worldofsurf-0e, 18 Nov 2026)

Content skew for static props: P1581's `propmiss` lists entity props whose model file the lobby lacks, but solid
STATIC props get their collision from the hl2 plugin and were not covered. The plugin publishes the solid static
props whose model file the server could not find; the lobby adds them to `propmiss`, so pm_verify's "may be content
skew" hint names them too. Measured first (lobby logs, 12 lobbies): 531 map/model pairs on 55 maps over the logs'
life, mostly before the Pi had HL2 content; still current on surf_1969 (TF2 props). Engine plugins/hl2/mod_vbsp.c,
FTESurf src/server (propmiss), the .rec grammar block. Root FTESurf-worktrees/sprpmiss-20261118-0e.

## Status (18 Nov 2026): merged -- engine main fe1ebfa3c (tag patch-1604), FTESurf below. Not deployed.

Engine: the hl2 plugin publishes read-only `hl2_sprpmiss` (PLUG_CVAR_FLAGS now passes CVAR_NOSET). QC: SV_PropStaticMissing
merges it into `propmiss` (case-insensitive keys, checked against entity props without joining their dedup list), and
the header gains `propstatic 0 | 1 <k>`; reccheck knows it. Record and arms: engine ENGINE_PATCHES.md "Patch 1604"
(ahop_coast: 154 static files missing without content, propmiss 215, `propstatic 1 154`; the old engine reads
`propstatic 0`). Reviews: round 1 (two lenses), round 2 on the fixes; stopped under the integrity rule. Deploy: the Pi's
server engine + hl2 plugin rebuild (it runs patch-1568), and the lobby QC with lex-90's step-2 progs (main's QC carries
P1603, whose surfd must go first). What it leaves: BACKLOG "Content skew vs tampering".

## Delivered (18 Nov 2026 21:34-21:41Z): lobby engine patch-1604 + lobby QC 3495dc51 -- tools/p1604-delivery.md
