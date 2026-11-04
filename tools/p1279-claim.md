# P1279 claim

ftesurf-ac, 20261104, Lex (4 Nov): a replay (demo) reads its energy zero from the start zone of the segment it begins at
(the header's track/startseg, or a stage window's segment), not "from jump", when hud_energy_ref is start zones.
State: live: both installs (csprogs ac10e21b), lobbies deploy/p1280-hands (cs 5266984f).
