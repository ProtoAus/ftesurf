# TAS uploads and bring-your-own bot — plan (20 Nov 2026)

## Lex's decision, 20 Nov 2026

> "I don't mind if the anti-cheat can't work 100% it's ok, as long as the run makes
> sense physics wise, it's fine."

This widens the 28 Oct rule (TAS boards admit only server re-simulated runs, no offline
TAS): a TAS record made anywhere — our TAS tools, someone's own bot, a fork such as
Rounin's — can be uploaded, and goes on the TAS board when its physics checks out.
TAS stays off the human and segmented boards; nothing here changes their admission.

## Verdict ladder for an uploaded `.rec`

| Verdict | How | Board |
|---|---|---|
| EXACT (not built) | native recording with `in` rows: `pm_verify` (sweep.py) re-simulates it in our engine and the zones finish it | "re-simulated" badge |
| PLAUSIBLE | `tools/tasplaus.py` PASS: every tick within the measured movement bounds, start/checkpoints/finish visited | upload board (tasupd), "physics checked" |
| HOLD | tasplaus HOLD | owner review queue (`tasupd.py list`), shown to its uploader only |
| FAIL | cannot be a run (no samples, clock backwards, past sv_maxvelocity, samples stop before the finish) | refused with the reason |

tasplaus status (commit b7fab6e2): 117/117 honest KSF/Momentum replays PASS; 12 checks
each proven by a cheat test (speed edits, deleted ticks, teleports into the end, clock
edits, low gravity, start outside the zone, early finish claims). Not yet known to it:
collision (a wall clip at legal speed passes), map push/booster volumes (HOLD), stage
legs (HOLD). Before it gates a public board it gets the independent review that
evidence code requires (CLAUDE.md).

## Bring your own bot (what already works)

- **Any tool, any fork**: the upload takes a `.rec`, so whatever produced it — a fork of
  this public repo, an external optimiser, a hand-made input list — is judged by the
  same physics. A fork that changes movement gets PLAUSIBLE at best, never EXACT.
- **Your inputs, our physics**: `tas demo <file> [rows [from]]` plays a recording's
  input rows (moves, pitch, yaw, with a `ksfbuttons` line before each) as TAS tapes in
  a local game (sv_tasoptimize.qc, P1449). An external program can write that file;
  the game plays it under the real mover and records a native run that can reach EXACT.
- **Tweak Jargon**: every search weight is a `tas_jargon_w_*` cvar (Tuning tab, P1572).
  A preset is a `.cfg` of those lines that people share and `exec`.
- **Analysis**: `tools/runcompare.py REF.rec RUN.rec ...` splits runs at the reference's
  ramp boards, gives the loss per split, the sum of best splits and per-ramp board/leave
  numbers. First use: surf_sandtrap2 bonus 4 (WR 7.827, human-proven splits ≈ 7.765).

## Built: P1640 upload service (tasupd)

`surfd/tasupd.py` at `https://play.proto.bar/tasup/`: an isolated service like tasrevd (own
store under `/srv/nvme/ftesurf-ops/tasupd-state`, read-only surfd `accounts`, no surfd schema or
generation change, 127.0.0.1:8093; 8091 is the twitch bot).

- **Who**: Steam OpenID sign-in on the page; the SteamID must have a World of Surf account (signed
  in once at `/board/link`, which states that names are shown) and no ban (Lex, 20 Nov: Steam-linked
  only). Bans and names are read live (5-minute cache); a ban hides that player's rows.
- **What**: a FTESURF-REC, 8 MB max, tickrate/movetickrate 0.015, map and track from its header,
  read by tasplaus's own header reader (a key given twice or a line break other than `\n`/`\r\n`
  is refused). KSF/Momentum imports (`foreign` and the other import keys, `mom-`/`ksf-` run ids)
  refused; stage legs (`leg`/`startseg`) refused (whole courses only); the header must end within
  64 KB and the samples must be plain ASCII. The same file twice is refused. Another player's motion
  is HELD for the owner with "the motion of run N (another player's)", never shown (two bots on one
  course may converge, so it is not refused as an accusation): rounded motion, or velocities on the
  tick grid (samples at their nearest tick, so moving every time by part of a tick does not hide it)
  against the course's uploads within 10% of the length -- at most 3 per other account, shown ones
  first, 60 in all; +-8 ticks, 2 u/s + 1% on 95% of the upload's sampled ticks -- or the path itself (each step between samples within the same
  tolerance, positions only: velocities edited on their own or a constant offset do not hide it), so
  a reprint, a new header, dropped samples or a lightly edited copy is refused as theirs; so is
  anything the owner removed (that one is refused). A copy re-flown with deliberate small changes (a physically consistent
  wiggle of a few units) is not caught: remove it by id. Your own runs may be
  uploaded again (a re-export, an improvement).
- **Record backstop**: tasplaus cannot see walls, so an upload that reaches the best known time on its
  course (surfd's clean record in a trusted tier: ranked, momentum or ksf -- not community, banned or
  `tas`-styled rows -- or the best upload shown) is held for the owner, ties included, and so is the
  first upload on a course with no time at all. A run held for physics carries the same note, so an
  approval knows it makes a record. Rounin's run will be held: approve it and later slower uploads
  show by themselves. A TAS author whose every upload is a new record hits the 10-held cap: approve
  or reject to free it. Your own shown motion uploaded again skips the hold only at the same or a slower
  finish: the same samples may claim any finish the end-zone slack allows (review 5: a slow decoy came
  back as the record).
- **Verdicts**: tasplaus PASS -> shown ("physics checked"); HOLD -> held, its uploader sees the
  reasons; FAIL -> refused with the reasons, not kept. At most 40 reasons are kept per run. A held
  run the owner approves is labelled "owner approved", not "physics checked". Review-1 (P1640)
  tasplaus rules, all HOLD: samples off whole ticks, under 2 decimals, ground speed-squared gain
  over 2AW-A^2, a jump not from the ground, contact-tick travel the velocity does not explain, an
  air turn past v'.(v'-v) <= 30|v'-v|, a finish claimed more than a hull early, a teleport that is
  not back to the ridden stage's start or gains speed, a start over 480 u/s (3D), or a moving
  opening on a course with no start limit. Review 2: friction on ground ticks, jumps only after
  a sample that is not rising, unexplained travel summed per second, sharp turns that keep speed
  (air control cannot, a wall would take speed) on air and contact ticks, the clock starting high
  in the start box; walls, steps, slopes and shortest-form numbers no longer hold. The speed cap
  is the larger of the zone file's and `cfg/maps/map_<map>.cfg`'s sv_maxvelocity (past it: HOLD).
  Review 3: landings on a down-slope (the slope fix) and jumps straight after a rising landing pass;
  an arc's top reaching vz 0 by gravity alone is no landing; duck sums reset on jump ticks; steps of 2+
  ticks count with off-tick ones and their turns are checked; the precision is the coarser of positions
  and velocities. Honest corpus (117 sandtrap2 b4 replays): all PASS; across 301 honest files no
  verdict changed in either round. Review 4: hops off an up-slope (the engine lands at the next
  tick's start, jumping from vz up to 140), %g-printed deep maps, and a slope landing inside a lost
  packet pass; jump ticks are held to air control (|v'|^2 <= |v|^2 + 900); at most one lost packet
  after the start, and it may hide ~2 ticks (~0.03 s). Review 5: precision is read from the samples
  checked only (one coarse sample past the finish had widened every bound) and trailing zeros are not
  significant; the end zone allows a tick of travel for a file whose samples stop before its finish (our
  recorder's last sample is the tick before; 53 false "never reaches end" gone, no new reason across 276
  honest files); a jump inside a lost packet gets its ground ticks' allowance; 2+ lost packets after the
  start still hold, now saying so plainly. Review 6: a number other than plain decimal or exponent form
  (`3_4_8.4`, `nan`, Unicode digits: Python reads them, other readers do not) FAILs the file; precision is
  per pair, from its two samples; the end-zone allowance covers the ticks the samples stop short (up to 2);
  a lost packet on the ground allows a step or slope's rise; a jump inside one gets its ground ticks'
  friction; header integers are ASCII digits only. Review 7: the body must leave the start zone within 2.5
  ticks of t=0 (or 8 u at its speed; honest max 1.73 ticks) -- a clock relabelled to start early holds; a file
  that shows %g output gets each number's %g rounding (z -14942 is 0.05 coarse); the energy test's height term
  reads z's precision alone; the per-second drift limit is 6 u (honest PASS max 0.33); at most 100000 samples.
  Review 8: beside the median, the clock's trimmed mean (largest 2 + 1% dropped) must stay <= 1.002 and at most
  2 + 1% of moving steps may cover over 1.15x their speed x time (a clock compressed on a minority of ticks);
  in free flight a ratio over 1 is first discounted by |vb|/|mean| (slow perfect strafing); an air wall hit gets
  the contact allowance in the drift test. Review 9: the clock tests also run in 3D (a velocity tilted toward
  horizontal on ramp ticks had kept the horizontal ratio at 1.000) and the |vb|/|mean| discount applies on every
  tick, contact included (short courses that gain speed on a ramp); exponent-form numbers count their real
  decimals (numpy's %.18e is full precision).
- **Board**: `/tasup/board?map=&track=` best per player; `/tasup/run/<id>` reasons and numbers;
  `/tasup/run/<id>.rec` the file (shown runs only); JSON under `/tasup/api/`.
- **Caps**: 30 uploads per account a day (refusals count), 1000 uploads / 1 GiB of kept runs for
  everyone, 10 held per account, 4 GiB store, 120 reads (GET and HEAD) and 10 sign-ins a minute per
  address (IPv6 by /64), 30 Steam confirmations a minute for everyone and 2 at once, 8 form parts,
  one checker at a time (a 6 MB / 88k-sample file: 1.5 s, 75 MB on the Pi; unit MemoryMax 512M, no
  swap; at most 200 reasons listed by the checker), `.rec` downloads 32 MiB a minute per address and
  128 MiB for everyone, nginx `limit_rate 1m`.
- **Owner review** (as proto on the Pi):
  `python3 /opt/ftesurf-tasupd/<commit>/tasupd.py --store /srv/nvme/ftesurf-ops/tasupd-state/tasup.sqlite3 list`
  then `show ID`, `approve ID [--note ...]`, `reject ID [--note ...]`, `remove ID`, `unblock ID`. A rejected run
  shows its note to its uploader; a removed one is gone for everyone (its file is deleted), and
  its motion stays refused as a duplicate -- except to an uploader who owns that motion (below). A rejected run uploaded again by
  its uploader is held with a note; `approve` also undoes a reject. Review 6: whether a removed run refuses
  you depends on whether you own that motion (a shown or held run of yours with it), not on upload order;
  your rejected motion is caught by the copy match too. `unblock ID` turns a removed run back into a hold
  for its motion (the real author's upload then waits as "another player's"); it cannot be approved itself
  (its file is gone). `reject`/`unblock` without `--note` keep the note; `approve` clears a reject's note.
  Review 7: only a SHOWN run of the motion counts as owning it (a held copy does not); another account's
  rejected run no longer holds the owner of that motion; an identical file is refused with how to re-upload.
  Review 8: a held run of yours counts against copies made after it (the author's first, held upload is not
  refused once a later copier is removed); your own duplicate names your run; 10 candidates per other account.
- **Known gap**: a human's public replay with its import markers stripped is real motion and
  passes; tasupd does not yet compare uploads with surfd's public replays (BACKLOG). Remove it by id.
- **Known gap** (review 6): another player's run re-timed as a whole by ~0.1% (times / f, velocities x f)
  is not seen as a copy -- sub-tick samples drift across tick boundaries -- so it can show a tick ahead of
  theirs below the record (at the record the backstop holds it). Remove it by id; BACKLOG has the fix.
- **Load**: at most two uploads are checked at once (a third gets 503 at once), one per account, so pages
  and sign-in keep two of gunicorn's four threads; each candidate's motion is read one at a time by id; the
  copy check stops after 20 s and holds the run for the owner; copies are matched up to 16 ticks apart.

Install: `tools/install_tasupd.py`, root, dry run by default (install_tasrevd.py's shape). Root takes
the installer out of git as proto into a root-owned file, checks its sha256, and runs that with
`python3 -I` (it refuses to be anything but the commit's own). The commit's own files go into a
root-owned release under /opt/ftesurf-tasupd, its connection-limit zones into
/etc/nginx/conf.d/ftesurf-tasupd-zones.conf, state dir as proto, systemd unit, loopback probe,
then ONE `include snippets/ftesurf-tasupd.conf;` after surfd's include in play.proto.bar's site
(exact predecessor hash required, backup in /etc/nginx), `nginx -t`, reload, public probe; nginx is
put back and the unit disabled if any step fails (Ctrl-C and hangup are held from the unit on). Both
probes read `/tasup/api/health`, which reads the store and surfd's accounts as the sandboxed service
does (a closed WAL surfd.db with no `-wal` is read immutable, as r2gateway does). `--upgrade-from
<installed commit>` for later releases; it runs the new release's `init` (additive schema steps) first.

INSTALLED 21 Nov 2026 00:10Z (Lex's root run): release /opt/ftesurf-tasupd/a8efd378, unit
`ftesurf-tasupd` on 127.0.0.1:8093, store /srv/nvme/ftesurf-ops/tasupd-state. Checked live: health ok,
the page, Steam sign-in redirect, an unsigned upload refused (401), `/tasup/api/board`.

## Still to build

1. In-game "Upload to TAS board" after a TAS finish, and a TAS-uploads tab on the web/menu boards
   reading `/tasup/api/board` (surfd's board.js rides a guarded generation; tasupd's page works now).
2. EXACT: native recordings with `in` rows re-simulated by pm_verify (sweep.py), shown with a
   "re-simulated" badge.
3. tasplaus: map push volumes from the entity lump; stage legs (both HOLD today).
4. Optional: a short public "make your own bot" page describing the `tas demo` row format.

Lex, 20 Nov: Steam-linked uploaders only (answered the open question above).
