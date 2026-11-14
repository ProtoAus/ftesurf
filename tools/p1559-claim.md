# P1559 claim (ftesurf-16, 15 Nov 2026)

Lex's bug/feature paste of 15 Nov (Mark's and nodsnot's lists). P1559 is the client-visual batch:
- replay/rewind/save-lead cameras keep P916's roof clearance (cl_lines.qc Line_ClipEye; cl_watch.qc,
  cl_rewind.qc, cl_savelead.qc);
- surf_legends fog thinned like surf_sidistic (cl_fog.qc);
- hl2 plugin: surf_beyond/beyond2 renders (scaled-prop cull radius, emissive model UVs, black LDR
  cubemaps fall back to .hdr.vtf, emissive drawn over an opaque base) -- engine plugins/hl2.
Later numbers in this session (claimed separately): zones (!r floor, own-track END, KSF named triggers),
map entity fixes (surf_1day, surf_forbidden_tomb, surf_network2008_final), surf_tendies booster prediction.
Shared docs: PATCHNOTES.md, BACKLOG.md, AGENT_NOTES.md, lextest.md, ENGINE.txt, engine ENGINE_PATCHES.md.
Task root C:/FTESurf-worktrees/lexlist-20261115-16.
