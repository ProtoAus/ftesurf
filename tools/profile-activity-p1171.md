# P1171: lobby playtime and main/bonus attempts

## What it counts

An official lobby counts, per connected player, real connected seconds (`gettime`,
spectating included, host_timescale ignored) and main/bonus course starts (leg 0;
stage starts excluded) when all of these hold (`PlayStats_Allowed`):
linked account, the lobby's social capability, an activity binding from the
backend, and the client's online answer `run_t_terms == FS_TERMS_ONLINE` (8).
Offline/unlinked play is not counted; old hours are not invented.

**Consent (Lex, 1 Nov 2026): the existing online answer (8) covers it.** The first
cut raised FS_TERMS_ONLINE to 9. sh_defs.qc is compiled into the csprogs every
lobby serves, so every released menu (answer 8) would have got "TERMS NOT ACCEPTED -
RUNS WILL NOT SUBMIT" and lost ranked uploads, boards and pictures until it
updated and re-accepted. The terms page gains a "Playtime and attempts" paragraph.

## Producer (src/server/sv_playstats.qc)

- One stream per (connection, map): progs reload per map, and `SV_Shutdown`
  flushes first. Losing permission pauses the stream; the same identity resumes
  it; a changed owner (relink) ends it. Players are evaluated once a second.
- Sealed snapshot `data/playstats-server1/p<port>/<who>.<binding>/<stream>.act`
  (header, body, SHA256, `end`; `.new`/`.prev` during the swap), written with
  FS_FILE_WRITESTREAM. First save 10-29 s after a stream begins, then every 30 s.
- POST `/api/social/playstats`; at most 8 in flight; a timeout or backend failure
  holds every send for 30 s. 200 or 400 removes that exact snapshot (hash
  checked); 403 is the player's session and retries.

## Backend (schema 26)

`surfd/playstats.py` is byte-identical to P1162's c83774a7: `play_sessions` holds a
max-merged watermark per (node, stream); `play_maps`/`play_attempts` are its sums;
`play_link_epochs` plus three keylinks triggers rotate the binding on every link
change. The route needs `consent >= 8`, the capability and the current binding.

## Verified

- Windows suites: playstats 9, social 72, inventory 10, accounts, join, board.
- Native arm (actual native520 fixture, real dedicated socket, isolated backend):
  the client's own answer reaches the server as 8, 0, 8; nothing accrues at 0; three
  toggles keep one stream id and one backend row; real seconds under
  host_timescale 4; one main plus one bonus, stages excluded; an outage leaves a
  sealed outbox that replays after a native restart; leaving stops time.
- Pi: fresh-fixture CLOSED candidates (3 negatives), and a private snapshot of the
  live DB migrated by the real primary: 37 existing tables' schema, counts and
  account/link/inventory digests unchanged, 22/22 link generations; fallback starts
  on it; the down step returns it to schema 25 exactly.
- Two independent reviews (producer/control flow; data preservation/abuse); their
  defects are fixed in the review-1 commits, quirks are in BACKLOG.

## Delivery and rollback

Generation 495537a9 (fcc0d20b + this) with fallback cba82980 (fcc0d20b + schema-26
tables only); deploy branches `deploy/profile-activity-{,backend-,fallback-}1171`.
A schema-25 surfd refuses a schema-26 DB, so going back to P1168 itself means
the private down step (drop four tables and three triggers, stamp 25) with surfd
stopped, not restoring the pre-26 backup (which loses every later write).
