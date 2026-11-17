# P1600 delivery -- surfd generation: mapwatch works again, P1580's sweep (17 Nov 2026)

LIVE 17 Nov 2026 03:54-04:04 UTC (guarded successor generation; owner root step 03:28Z; POSTFLIGHT PASS).
- Runtime delta vs the previous generation: new sealed member `tascontent.py` (mapwatch had failed
  `ModuleNotFoundError: tascontent` under every sealed generation since 15 Nov, so the map list was stale), runtime
  `sweep.py` / `test_sweep.py` at main (P1580: the account-key check is live; the receipt address check is skipped
  until main's rcptcheck is installed -- that rides the next generation's Root policy).
- Transition guard profile `tas86-v1` (game main 9742eb5a) admits the 86-file runtime.
- mapwatch.py ships at the LIVE bytes and keeps its `23 */6` schedule. Game main's surfd/mapwatch.py (9143acaf,
  085ab67c, d5dde64a: a 30-minute cadence attempt) must NOT ship: three review rounds showed mapwatch's only back-off
  is the cron interval; Lex's 30-minute new-map scan is ftesurf-29's separate light route (P1601).
- Reviews: four lenses (Root, packet + guard, operator + cron, sweep by ftesurf-a8), three fix rounds on the
  abandoned cadence work, the reduced build, and the independent actual-consumer review (CLEAR).
- Follow-up check: mapwatch's first run under the new generation (06:23 UTC) graded from its own log.
- Next generation: ftesurf-a8's readers (rcptcheck/reccheck/hidcheck) as current in the Root policy, P1601's route,
  and the CURRENT 85->86 profile constants in the operator.
