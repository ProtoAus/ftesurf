# Patch 1604 claim (Claude Code worldofsurf-0e, 18 Nov 2026)

Content skew for static props: P1581's `propmiss` lists entity props whose model file the lobby lacks, but solid
STATIC props get their collision from the hl2 plugin and were not covered. The plugin publishes the solid static
props whose model file the server could not find; the lobby adds them to `propmiss`, so pm_verify's "may be content
skew" hint names them too. Measured first (lobby logs, 12 lobbies): 531 map/model pairs on 55 maps over the logs'
life, mostly before the Pi had HL2 content; still current on surf_1969 (TF2 props). Engine plugins/hl2/mod_vbsp.c,
FTESurf src/server (propmiss), the .rec grammar block. Root FTESurf-worktrees/sprpmiss-20261118-0e.
