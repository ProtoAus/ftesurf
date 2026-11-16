# P1595 claim (ftesurf-64, 17 Nov 2026)

Players: "we're missing ahop_coast". surfd's pool rule (mapmanifest.pool_policy, P727) enables only `surf_`
and zoned `bhop_` names, so since P1496 put Momentum's other native bhop maps in the directory's map list they
arrive disabled and the Maps picker hides them -- ahop_coast and 77 others (kz_, df_, deathrun_, hl_, ...),
even for players who have the file. Fix: a zoned map Momentum files as surf or bhop is in the pool whatever
its name. surfd (mapmanifest/surfd) + tests; Pi surfd deploy. Root C:\FTESurf-worktrees\lexlist-pool-20261117-64.

## Live (17 Nov 2026)

surfd generation P1592+P1595 (ftesurf-4a, swap 22:34-22:43Z 16 Nov): /api/board?maps=1 2269 rows, disabled 217 -> 142.
ahop_coast stayed `enabled 0`: an explicit admin row (map_pool enabled=0, 15 Oct 09:53Z, with ahop_rainbow,
ahop_trick_or_treat and agtricks within 4 s; no record says by whom), which outranks the pool rule by design.
tools/p1595_enable.py (the inverse of p1112_disable.py, same UPSERT as admin /api/maps) re-enabled ahop_coast,
ahop_rainbow and agtricks at 22:46Z; backup of every map_pool row before it:
/srv/nvme/agent-work/gamemode-20261117-29/map_pool-before-p1595.json (Pi). Now 140 disabled; ahop_coast and agtricks
list `- 1 1`. ahop_rainbow is not in mapwatch's list (Momentum mode 9, never acquired); ahop_trick_or_treat has no
zones, so the rule keeps it out.
