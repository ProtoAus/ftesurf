# P1648-P1650 delivery (20 Nov 2026, worldofsurf-ed)

## gen1650 backend (P1650) -- LIVE 10:12:39Z after a HOLD and a reviewed recovery

Packet `FTESurf-private/worktrees/gen1650-20261120-ed` (RUNBOOK, OWNER log, recovery/). Primary `f7243132` (REF
`cee8794f`: four changed files on the gen1635 tour91 guard), fallback `df87d0ed` (= gen1635 code). Lex's owner Root
install 09:02Z; source pin `12cab28a`, reference `4496facd`, independent token `03927586`.

- **HOLD 09:24-09:29Z.** The execute drained and closed gen1635, then `sudo -n systemctl start surfd.service` for the
  fallback qualification outlived the retained operator's 250 s `run()` timeout: the guarded drop-in's ExecStartPre
  chain is 16 filesystem preflights of ~15.5 s each (~252 s; 15 blocks took 238 s at 06:06-06:10Z). recover() refused
  ("unqualified fallback recovery"); all fences CLOSED, cron parked, unit stopped. surfd down 09:24:22-10:12:39Z.
- **Recovery (Lex: "re-run swap, new code").** `recovery/recover1650.py` reloads the same pinned operator, rebuilds its
  state from the failed run's records plus the live host, and runs the same retained sequence with a 900 s start and a
  fresh `fallback-requalification` lifetime. Its read-only `--check` caught a JSON list-vs-tuple mismatch in the drained
  record before it could HOLD a second time. Two independent reviews (sequence, failure) CLEAR. Fallback requalified
  10:01-10:07Z, primary accepted 10:12:39Z.
- **Postflight PASS 10:13Z** (`tools/postflight_recovery.py`: the stock postflight reading recovery/ evidence). Mapwatch
  and mapnew functional runs pending their next schedules.

## Lobbies (P1648/P1649)

10:14:23Z qwprogs `4a72a384` / csprogs `18e26fa6` (main `08f6ee47`) on all 12 (`deploy1648.sh`, backups
`.pre1648-20261120T101329Z`), then worldofsurf-4b's main `4dcc1ec0` build at 10:18:42Z (carries them). Preflight ALL GO.

## Next generation: read this first

The ExecStartPre chain grows by one ~15.5 s block per generation. A future successor must raise the operator's start
timeout (or the owner must prune retired blocks from the drop-in) BEFORE its execute, or it HOLDs the same way.
