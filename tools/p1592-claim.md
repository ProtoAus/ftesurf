# P1592 claim -- "segmented" replaces "shadow" in run file names (ftesurf-63, 17 Nov 2026)

Lex, 17 Nov: rename the shadow runs and their demos to segmented, now. A shadow run (TF_SHADOW, RT_SHADOW) is a
segmented run resumed from a save with its clock. New files are written `<stamp>_<who>_segmented.rec` (.view/.hid
alike); every reader keeps reading `_shadow` files, which stay on disk under their old name.

Touches: QC writer and readers (sh_defs FS_TagName/FS_TagFromName, cl_watch), the engine's held-recording close
(the expected leaf for tag 3 accepts both words), surfd `_LEAF_OK`, tools/reccheck.py TAGS. The writer switches
only where the engine accepts the new word. The display-only rename (HUD, chat lines, replay info) rides along.
