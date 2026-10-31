# Steam-linked activity and Local TAS records (source checkpoint)

## Status

This branch is **not deployed or owner-playtested**. It does not modify Steam's
own library playtime. Activity appears on the FTESurf profile linked to Steam.
The current scope is connected, Steam-linked FTESurf lobbies, including native
QW spectators. Offline games, menus, time in other games, and historical activity
are not backfilled. Do not describe this as total Steam/offline playtime.

## Counters

- **Game playtime:** real connected seconds across linked lobbies/maps, including
  spectating. The server samples `gettime()`, not the movement or run clock.
  Slow motion does not reduce this counter. Backwards clock steps and single
  frame gaps of at least 60 seconds are not counted as observed playing time.
- **Map time:** the same seconds grouped by map.
- **Attempts:** counters keyed by map, track, and leg. Track 0 is main; tracks
  1–11 are bonuses. Leg 0 is a whole-track attempt; legs 1–23 are stages.
  A full-track start counts its track and (on a staged track) opening stage;
  stage-only starts count only their stage. A forward stage crossing starts that
  stage once, even if the timer later rebases on leaving its box. Re-entering a
  failed stage box and departing starts another stage attempt. Merely arming a
  timer does not count. Checkpoints, save placement and rewind cursor movement
  are not attempts. Save/load and rewind cannot restore/decrement these counters.

Snapshots are cumulative for a random per-connection/map stream. The backend
pins a stream to the authenticated node, Steam account and map. Each numeric
counter merges by maximum independently, so repeats and out-of-order snapshots
do not add twice. Reconnects and installations sum into the same Steam account.
No client-supplied SteamID, userinfo hash, or display name grants ownership.
Counters are informational only: no ranking, verification or eligibility reader
uses these tables.

The server posts about every 30 seconds under the existing proven social
capability. Disconnect tails use a bounded 64-entry detached retry queue, not a
recycled player entity. A transient error can retry while the same map VM lives.
This is **not a durable offline spool**: process/map shutdown, queue exhaustion,
or revoked account proof can lose an unacknowledged tail. Relinking never credits
the previous account's counters to the new one. Revocation is not bypassed to
recover an old tail. These limitations need resolution before claiming lossless
playtime accounting.

## Backend/profile contract

Schema 25 adds `play_sessions` (idempotency watermarks), `play_maps` (seconds)
and `play_attempts` (per-leg counters). Migration does not rewrite account/run
rows. Do not prune session watermarks independently of their totals; replaying
an old stream after deleting its watermark would count it twice.

`POST /api/social/playstats` uses form fields:

- `key`, `node`: existing lobby authentication;
- `token`: an existing proven, non-revoked social capability for this node;
- `stream`: 32 lowercase hexadecimal characters;
- `map`: bounded lowercase map name;
- `seconds`: cumulative integral seconds, 0–16777215;
- `attempts`: comma-separated `track:leg:count` counters, at most 288 distinct
  keys and 8000 characters. Counts are positive exact QC integers.

All updates occur in one SQLite write transaction. The response is `{ok: 1}`
or an ordinary error; it never returns capabilities or raw SteamIDs.

`GET /api/board?player=<handle>` includes
`playtime: {seconds, scope: "linked_lobbies"}`. Adding `&on=<map>` includes
`map_seconds` and sorted `attempts: [{track, leg, n}]`. Activity-only accounts
can be found before their first completed run. The in-game map profile has
**Times / Attempts** tabs. The ordinary web player JSON also exposes playtime;
no new web activity panel is included here.

## Local PB and TAS files

Earlier PB improvements are retained rather than pruned by `rec_runs_keep` or
replaced by the next lobby improvement. Clean summaries (`lobby.pb`) still hold
only the current clean best. This cannot recover files deleted by older builds.

`RT_TAS` / `<ticks>[_<who>]_tas.rec` archives completed tool-assisted or
host_timescale runs locally, instead of overwriting `cheat.rec`. These files
retain `TF_PRACTICE|TF_CHEAT`; explicit TAS controls retain `TF_TAS` as well.
**The category and explicit-tool ancestry are distinct:** slowmo does not gain
the stronger explicit-TAS connection latch just by being saved and reloaded.
The Local **TAS** chip and `board filter tas` select these records plus historical
records carrying `TF_TAS`. None becomes a clean/segmented-ranked submission.

Header-only remote explicit-TAS improvements use `RT_TAS_LOBBY` and
`<ticks>_taslobby.rec`. They have no movement replay; Watch/line actions are
disabled just as for ordinary lobby summaries. Keeping their namespace separate
prevents them from shadowing a playable `_tas.rec` during `replay tas`.
Remote slowmo-only no-rec finishes do not yet publish an unambiguous category
marker, so mirroring those finishes is a remaining gap. Also, a slowmo-only save
loaded after a validated clean reset or on a fresh normal-speed connection
retains practice/cheat exclusion but loses the slowmo category: it finishes into
`cheat.rec`, not the TAS archive. Preserving category provenance across those
save/rewind boundaries needs a separate additive marker (not the strong explicit
TAS latch), with all capture/copy/restore/file paths covered. These are real
feature gaps: the full requested TAS workflow is NOT complete. Do not relabel
every cheated finish as TAS or weaken clean-return safety to work around them.

## Rewind and save-load posture

The current base already retains a recorded prefix when continuing from rewind
or saving a rewind point; no prefix fabrication is added here. Full-line
acceptance for repeated rewind → save → load → finish still needs a real client
run on this branch.

The paired engine branch resets only the old duck-button latch when restoring
standing, on both the authoritative `run_forceduck` path and predicted
`PM_ApplyPreInput` path. Jump and other buttons are preserved. This fixes the
held-before/pressed-after grounded transition counterexample in an extracted
native harness. It is **not proof of the reported airborne clearance symptom**;
that needs a dedicated-socket held/released comparison of server hull, origin,
camera and final clearance through the real save-lock lifecycle.

## Retained evidence

Task root: `C:/FTESurf-worktrees/playstats-01a192ea/`.
- QC base `f9d1ad842a9c511a03396e7d1286b6fd454c34e0`.
- Engine base `c36bc6b06684e42cc1c513c966e526a796cf392f`.
- `artifacts/` contains compiler, backend, recording-reader, corpus and native
  positive/negative-control logs. Tests do not establish deployed/in-game status.
