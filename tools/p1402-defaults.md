# P1402 -- flat water for new installs, surf_view planes with edges (8 Nov 2026)

Delivery (8 Nov 22:20Z): build.ps1 -Pi from main 9edf6dfb (no src change since 37fb0a76's live build besides
P1402; fteqcc c24ede65): nobody on any lobby, cs 3dbeb0c1 / qw 0a406f51 (unchanged), all 12 restarted, 0 QC errors.
artifacts/deliver_qc1402.py: C:\FTESurf progs and both installs' default.cfg/defaultuser.cfg, protected files
unchanged (delivery-p1402). tasrevd codes.txt 89 -> 90 (.pre1402); csprogsvers e05a6982 seeded in both installs.

Lex, 8 Nov: "not yet [Full reflect] ... dithered and flat transparent plane performs the same, use flatplane
instead. Can you make the ent_view and surf_view flat transparent planes with wireframe option as default too."

- default.cfg / defaultuser.cfg: `set hl2_water 0`, `set surf_view_style 3` (engine cvars: hl2_water default 3,
  surf_view_style 1, archived). A saved value wins, so water changes for new installs only.
- cl_hudedit.qc HE_MigrateDefaults: r_video_rev 1402 moves a saved surf_view_style 1 (the old default) to 3 once,
  gated on the engine's "Patch 1201" description (P1376's reason: set/seta clear the engine type flag).
- cl_gfx.qc: an archived Budget/Screen-space water an old client cannot draw falls back to Flat sheet, not Dithered.

Verified (lows2 root artifacts/run_defaults1402.py, one boot each, values read from the client console):
fresh (no saved values, no exec of the test copy's fullfx.cfg) hl2_water 0 (default), surf_view_style 3 (default),
r_video_rev 1402; saved 1 + rev 1376 -> 3 with the console line; saved 2 -> 2; saved 1 + rev 1402 -> 1.
QC build 0 warnings (fteqcc c24ede65).

Flat (0) against dithered (3), Lex's settings otherwise, paused 3 s, each twice (artifacts/waterscan flat run):
garden 001 810/818 vs 814/797, garden 005 568/561 vs 550/556, boreas 002 596/599 vs 625/648, boreas 009 557/546 vs
584/566, aesthetic 937/890 vs 910/923, ceaseless 035 624/621 vs 637/590, ceaseless 001 816/773 vs 708/749 fps avg:
the same within about 5%, boreas a little faster dithered.
