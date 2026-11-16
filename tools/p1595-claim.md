# P1595 claim (ftesurf-64, 17 Nov 2026)

Players: "we're missing ahop_coast". surfd's pool rule (mapmanifest.pool_policy, P727) enables only `surf_`
and zoned `bhop_` names, so since P1496 put Momentum's other native bhop maps in the directory's map list they
arrive disabled and the Maps picker hides them -- ahop_coast and 77 others (kz_, df_, deathrun_, hl_, ...),
even for players who have the file. Fix: a zoned map Momentum files as surf or bhop is in the pool whatever
its name. surfd (mapmanifest/surfd) + tests; Pi surfd deploy. Root C:\FTESurf-worktrees\lexlist-pool-20261117-64.
