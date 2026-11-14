# P1561 claim (ftesurf-16, 15 Nov 2026)

Lex's 15 Nov list, zones: `!r`/zone_goto floor snap traced from a unit up (surf_mesa, mesa_revo,
ahop_coast fell to a lower floor); the runner's own track's END outranks another track's in the shared
zone scan and the replay mirror (surf_reytx bonus 2 through the hoop never finished; 25 maps overlap END
boxes); spawn yaws accept a drifted auto spawn (16 u) and several destinations sharing a yaw (surf_beyond
s5, surf_beyond2 s1/s3/s5). Files: src/server/sv_zones.qc, sv_timer.qc (SV_ZoneScan + callers),
sv_resume.qc, sv_saveloc.qc, src/client/cl_watch.qc. Verifier code: independent review before deploy.
Root C:/FTESurf-worktrees/lexlist-20261115-16.
