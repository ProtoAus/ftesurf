# Backend generation swap under systemd: P1080 (28 Oct 2026) -- the procedure as run

Lex, 28 Oct: "I need them all complete, do them all". Live backend now: generation
`74e060d79603f4f106f5b1478d0b82af79bab1d3` (FTESurf main at P1080: P1052/P1054/P1062/P1079/P1080
surfd), root `/srv/nvme/agent-work/menu-gen1080-20261028`, fence OPEN since 06:32:43Z, API down at
most 06:32:20-06:32:43. Rollback generation `eab9a4f6` (root `/srv/nvme/agent-work/ac-01a170a1/
backend24/cohorts/recover-current81-from2e8-prerequisites`) is CLOSED and drained; keep it. Scripts:
`C:\FTESurf-worktrees\menu-20261026T1632Z\artifacts\backend-gen\` (build_runtime.py, make_manifest.py,
stage.sh, gen_dropin.py, cutover.sh, postswap_check.py); Pi copies and logs in
`/srv/nvme/agent-work/menu-gen1080-incoming-20261028`.

## What changed since P996

- surfd is a root systemd unit (`surfd.service`, `Restart=on-failure`) with a sandbox drop-in
  (`surfd.service.d/10-guarded-startup.conf`, `ProtectSystem=strict`): RW only for the live
  generation's `state/` and `control/` plus `/srv/nvme/surfd`, 814 read-only pins. A new root's
  guard cannot take its locks there, so each new root needs a new drop-in, and proto's sudo is
  only `start`/`stop surfd.service` and `daemon-reload` (no `restart`): Lex installs it.
  gen_dropin.py keeps every old RW path and pin, so the old generation still starts (rollback).
- eab9a4f6 served through a sealed witness (`bootstrap_wsgi` -> `witness_wsgi`) that pinned the
  lobby native and the game/tools readers; this generation serves plain `surfd:app` under the same
  guard (launch still verifies all 81 runtime hashes). AC (ftesurf-d0) confirmed the witness was
  rollout machinery, not an evidence rule. Order that follows: generation, then readers, then natives.
- The guard's `current81-v1` profile demands exactly its 81 hardcoded files; four live under
  `tools/` in the repo (momfetch, msml, ksfconvert, ksfreplay_info).

## Cutover (cutover.sh)

`systemctl stop` the old unit; `guard candidate` the new fence outside systemd; health; receipt and
`reopen` (the fence goes OPEN); stop the candidate; rebind run.sh; `systemctl start` (the new
generation under systemd); stubs, momrequests, cron; close the old fence. Every failure point puts
the old generation back through systemd (run.sh restored first where it moved).

## Traps met

- SEVEN stubs, not six: the dispatcher's `FILES` include `momgrab.py`, which the `momrequests`
  user service runs. Left on the old fence it held its admission lock and the close timed out
  (60 s). cutover.sh now renders `sorted(d.FILES)`.
- `lobby_dir x; menu_main` in a harness sets the cvar to the whole remainder (unrelated to the Pi,
  same day: it cost the P1080 arm two runs).
- Readers: game/tools/reccheck.py was behind main (P1079); swapped right after the generation under
  the sweep lock, proved with a known-PASS .rec through rcptcheck's import path.
