# Backend changes waiting for the next surfd generation

Lex, 9 Nov 2026: pi.dev folds these into its next guarded backend generation (asked of ftesurf-3a: "pi.dev folds
it in"). Nothing below is live; the game-side buttons are held until it is. Remove an entry once it is activated.

## P1447 web viewer (Strata maps, faster builds) and P1448 Fetch (KSF + Momentum, boards and profiles)

- Source: QC main at or after `00641171`. The surfd delta since `192beb7f` is exactly these two patches:
  `surfd/{fetchq.py (new), surfd.py, ksftopup.py, ksfimport.py, ksfgrab.py, ksfprofile.py, momprofile.py,
  momwatch.py}`, `surfd/web/{board.js, board.html, watch.js}`, tests `surfd/test_{fetchq (new), ksfgrab, ksftopup,
  momprofile}.py`. `tools/momfetch.py` is unchanged.
- Ship the .py set together: `ksftopup.pending` now returns a sixth column that `ksfimport.topup_step` unpacks, and
  `momwatch` imports `fetchq`. The KSF crawl and momwatch cron routes must run this generation's copies.
- Data: no schema bump. `fetchq.ensure` (called from `migrate`) creates two optional tables in one transaction,
  `momtopup` and `profilefetch`; readers treat a missing table as empty, so an older generation ignores them and
  a rollback needs no data step.
- Tests: all 107 `surfd/test_*.py` under a socket guard; the 6 that fail (test_admin, test_momindex, test_ranked,
  test_receipt_angle_reasons, test_schema_compat, test_verdict_recording_sha) fail identically on 192beb7f.
- Records: `tools/p1448-fetch.md` (seven review rounds, residuals, bounds), `tools/p1447-viewer.md`.
- After activation (ftesurf-3a or whoever is free): deploy the QC (lobbies + installs) from main; the clients already
  send `ksfmore=1` beside `fetch=1`, so they are safe on either generation. Live check: one board press and one
  profile press, `momtopup`/`ksftopup` rows queued, a 3D replay on bhop_2006isback.
