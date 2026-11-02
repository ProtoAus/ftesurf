# P1211 claim (ftesurf-ac, 2026-11-02)

Prediction of map gravity writes and delayed player writes: bhop_decimus's OnJump gravity pads
(gravity -2/-1 then 1 after 0.3-1.7 s) and surf_oneiric's delayed SetAbsVelocity (1 s after the
hub teleport). Measure first (lexlist4-20261102/artifacts/p1210probe.py, named before the renumber); touches
src/client/cl_triggers.qc and src/server/sv_entities.qc if a fix follows. Lobby QC.
