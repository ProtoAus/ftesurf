# P1600 claim -- surfd generation: tascontent.py sealed, mapwatch every 30 min, P1580 sweep (ftesurf-4a, 17 Nov 2026)

The next guarded surfd generation after db11bd61 (P1592+P1595). Carries: `tascontent.py` as an 86th sealed runtime
member (mapwatch has failed `ModuleNotFoundError: tascontent` since 15 Nov, so the map list is stale), a transition
guard profile `tas86-v1` (fetch85 + tascontent.py) so the guard admits it, mapwatch's canonical cron row at
`23,53 * * * *` (Lex: scan every 30 min), and runtime sweep.py/test_sweep.py at main (P1580; ftesurf-a8 reviews
that lens and later does P1580's activation). Owner root step `sh ~/p1600`.
