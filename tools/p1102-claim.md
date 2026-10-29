# P1102 claim -- ftesurf-aa (Claude Code), 2026-10-28T23:05Z

Engine: the data/map* tables are read only from the game directory's own loose files, not from
downloaded or server packages; data/ downloads refused; stamp readers agree. Files: engine/common/fs.c,
engine/common/pr_bgcmd.c, engine/client/cl_parse.c, src/menu/m_mapmedia.qc.
