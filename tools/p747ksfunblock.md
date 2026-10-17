# P747 — KSF crawler unblock and viewed-map demo priority

## What was wrong (measured 2026-10-17)

No KSF row ever had a replay (`runs` tier ksf with `replay_id>0`: 0 of 429,436;
`data/ksfruns` absent), so the board offered no Watch or line for KSF.

Cause: P715/716 queue a KSF "best records" walk for every Steam player whose
profile is viewed. KSF answers HTTP 500 for a player it does not know
(`ksfimport.NoSuchPlayer`), and `Pacer.get` re-raises that as a host refusal.
The walk stays first in `ksfprofiles` order, so from 2026-10-15T14:31Z every
`--watch` tick made exactly one request, got 500 and parked (6 h, 12 h, 24 h;
next 48 h). Board crawling, top-ups and the P740 `--demos` lane never ran.

Read-only probe from the Pi, 03:40Z, 3 s apart:

| Request | Answer |
|---|---|
| first queued walk, `/api/players/<id>/bestrecords/1` | 500, empty |
| `/api/maps/surf_dragonfall/records/zone/0/1` | 200, 20 rows, 12 with `file` |
| `/api/replays/<file>?game=66t` | 200, 353,092-byte v3 original |
| `/replays/surf_dragonfall/<file>` (site link) | 200 HTML viewer, not the file |

7,124 of 7,743 cached boards advertise at least one demo. 7 of the 19
queued/partial walks were for players with no KSF rows (4 of them native
ranked players).

## Change

- `ksfprofile.step`: a 500 on the profile route ends that walk (`unknown` before
  any page, `limited` after) and stops profile work for the tick. No park; the
  crawl's next request still parks a host that 500s everything. A later view
  re-queues it after TTL. The client shows nothing for `unknown` unless the
  player has KSF rows ("not fully checked yet").
- `ksfgrab`: boards of maps viewed within `WANT_DAYS` (mapwant) are scanned
  first, `SCAN` a tick on their own cursor; their jobs download first; a full
  queue gives one cold unwanted job up per wanted row. The rotation's eviction
  no longer takes a wanted job. Rate unchanged: at most 2 downloads a tick.

## Verified

Profile suite 20 OK, grab suite 48 OK, ksfimport suite 0 failed (Windows,
Python 3.10). The seven new tests fail on the unpatched code; the watch-tick test
reproduces the live symptom (one request, then park).

## Delivery

Not deployed. `ksfprofile.py` and `ksfgrab.py` are among the eight files the
sealed schema20 generation `36697da` pins; the Pi's `/srv/nvme/surfd/ksf*.py`
are dispatch stubs into it. The owner chose to ship this with the next guarded
generation cutover (BACKLOG).

Interim, owner-approved, 2026-10-17T03:56:14Z, under the crawler's own lock with
the guard OPEN: the 7 queued, zero-page walks of players with no KSF rows were
set to `unknown` and the park file removed. Old rows and park file are saved
privately in the owned Pi scratch root. This holds only until somebody views a
non-KSF player's profile again; then the old code parks the crawler again.

## Review and first live result

One independent review (predicate/control flow and host politeness). Fixed: a
swallowed profile 500 counted as an answer and could lift an expired park on a
tick that asked nothing else (`Pacer.unanswered`; new test fails on the prior
commit). Refuted by the Pi's cached pages: KSF answers 200 with an empty list
for a style with no records (8 such pages), so an FW-only player is not ended
`limited`. Kept as designed: limits in BACKLOG.

First tick after the interim, 04:01Z: 8 requests, 6 board pages, 202 rows, no
park; `KSF demos: 2 request(s), 2 linked`. The first linked KSF replays:
surf_004_fix and surf_1024, main FW.

## Why most advertised demos still cannot link (measured 2026-10-17)

Every advertised demo on surf_monolith (91), surf_prosurf (38) and surf_null
(59) matched our row's time and date, yet `current()` refused all of them: each
row had `runid=''` and a `ksf_unbound` marker. The schema20 migration marks
older KSF rows unbound, and only a board page fetched FRESH re-files a record
with its ID and lifts the marker. The crawler re-asks a first page every
`REFRESH_DAYS` (14) and walks deeper ranks again every `REWALK_DAYS` (60), so
until then most maps' demos are not eligible, whatever the demo lane does.

Owner-requested one-off, 05:2xZ, under the crawler lock through the live
admitted code: page 1 of the 32 main/bonus boards of those three maps that
advertise a demo was re-asked (`board_page(top=True)`) and filed as a tick
files it: 411 rows set, 137 demos eligible. Downloads 10 s apart: 19 asked, 14
linked on surf_monolith (main FW 5, HSW 3, SW 1, BW 1; bonus 1 FW 4), 4 refused
by the converter ("public time differs from bookmark interval by over one CSS
tick", all four monolith main styles), then one demo answered HTTP 500 and the
host was parked 6 h as the crawler would. That demo and a board answered 200
minutes later, so the 500 was transient. Script and log: owned Pi scratch.

## Owner's hard bonuses, 06:2x-07:05Z

From Lex's bonus tier sheet (Y/X tiers) plus monolith B4: same method, two
batches (`ksfbonus.py`, `ksfbonus2.py` in the owned Pi scratch). It did not
wait out the 6 h park left by the single transient 500 (`--ignore-park`, at
the owner's request; KSF had answered every request since); a new refusal
would still have parked and stopped. None came.

- Batch 1, 13 cached boards: 88 asked, 80 linked (monolith B4 4, prosurf B4 5,
  gigapede B4/B5/B6 8/6/5, fornax B4 5, kvas B4 6, facility B4 7, sanctuary B3 4,
  assail B4 5, bugs B4 9, hades2 B4 9, cannonball B2 7).
- Batch 2, 8 bonus boards the crawler had not reached (KSF names
  `surf_medley_fix`, `surf_fiellu_ksf`, `surf_sinsane_ksf`): 49 asked, 44 linked
  (exonic B3 4, highlands B4 5, radiant B3/B4 7/4, goliath B4 5, medley_fix B4 5,
  fiellu_ksf B4 7, sinsane_ksf B1 7).
- 17 converter refusals today: 7 "public time differs from bookmark interval
  by over one CSS tick", 10 "course has no initial start-zone entry". Handed
  to ftesurf-89 as P757 with the advertised file names.
- Not fetched: sinsane2 B3/B4, shibboleth B4, mdrn B4, shodan B10, stitched B1
  (the owner's client has no zones for them); not_so_zen B5 (not on KSF);
  pyzire B4 (KSF has only `surf_pyzire_retexture`, absent locally); axiom B4
  (no KSF records).
- Pi total after: 153 KSF rows with a demo across 27 maps, 128 on bonuses.
