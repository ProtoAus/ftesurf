# Patch 1617: the lobby log flood (Claude Code worldofsurf-58, 19 Nov 2026)

FS_StreamFiles (src/shared/sh_streamfile.qc) asked checkextension("FTESURF_QC_FILESTREAM_HASH") on every call;
Archive_StreamFrame calls it every server frame and the engine prints each yes at developer 1 (pr_cmds.c:7676).
On 19 Nov server10.log's last 6001 lines held 5916 of it; 2.8 KB/s per lobby, 16 GB of server*.log, 59 GB free,
no logrotate entry. Now asked once, kept in one state global. QC only; not yet on the lobbies.

The first cut did not work and compiled at 0 warnings: a flag declared between the builtins and the function was
inside FS_StreamFiles' frame (fteqcc: parm_start 839, locals 4, over the three builtins and the flag), and the VM
restores a frame on return -- watchpoint_ssqc fs_streamfiles_asked showed 1 -> 0 in Archive_StreamFrame after
every call, and the line still printed once a frame. A declared local moves the frame onto it. That cut also had
`ok = a && b && ...`, which QuakeC parses as `(ok = a) && ...`.

tools/qcframes.py fails a progs where a file-scope global sits inside a function's frame; tools/test_qcframes.py
20/0 on synthetic progs (the shape did not reproduce in a small program). Live qwprogs 14f1aa82 / csprogs 9f0ea093:
0. This build: 0. The first cut rebuilt: 1, fs_streamfiles_asked, exit 1.

Measured, local fteqw-sv64 at developer 1 on ahop_coast, 20 s each: live 14f1aa82 printed the line 1242 times,
this build (qwprogs 9e3bc024, csprogs 3da4417a) once; both advertise fs_archive2 1, no QC errors.
Deploy: rides the next lobby qwprogs+csprogs restart. The existing 1-2 GB logs are left for Lex.
