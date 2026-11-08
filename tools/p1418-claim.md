P1418 (with P1417) claimed by ftesurf-b8 (Claude Code), 8 Nov 2026: engine crash guard -- FS_LoadMallocGroupFile and
Image_LoadHiResTextureWorker refuse a file length past 2 GB and name the file instead of passing a
sign-extended size to BZ_Malloc (MetalGio's "BZ_Malloc: Failed on allocation of 18446744071578836992
bytes"); fs_vpk.c builds entry sizes and offsets unsigned; Sys_Error writes its text into the console log
and data/crash/ before the dialog. P1418 (same claimant): crash reports from the log, offered to the
lobby like prediction reports. Root C:\FTESurf-worktrees\xhair-20261108-b8.
