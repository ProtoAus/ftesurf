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
