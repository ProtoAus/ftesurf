# P1448 -- Fetch: a leg or a player from KSF and Momentum, on demand (ftesurf-3a, 9 Nov 2026)

Lex: "a fetch button on the leaderboard, so if you wanted the leaderboard for a map / bonus that doesn't have it, it
will search Momentum mod / KSF for new results. It would also refresh that leg. Also ... for a player profile to get
all of their records." and "also fetch the KSF demos for the leg ... if there is one, grab it."

## What it does

- TAB board, menu board and the site's map page: "Fetch" (was "Fetch KSF", KSF filter only) on the KSF, Momentum and
  All filters, empty boards included. One POST (`/api/board?fetch=1`, the site's `/board/api/map?fetch=1`) queues the
  leg with whichever of KSF and Momentum lists it, and says what each answered.
  - KSF: the existing `ksftopup` queue; a leg KSF's cached catalogue lists is askable with no KSF row here (was:
    only maps already holding one). Page 1 is asked again once per press (older than 10 min): the leg is refreshed.
    The leg's demos download first (ksfgrab orders legs pressed in the last day ahead of viewed maps).
  - Momentum: new `momtopup` queue (surfd/fetchq.py), spent first each momwatch tick (4 requests a tick) through
    `momfetch --board`, page 1 again once per press, then deeper.
- Profiles (game and site): "Fetch" re-queues the player's KSF and Momentum walks (after an hour, was a day) and
  makes the KSF walk a full one (stage and bonus PBs, past a view's page limit) -- the walk a press or a profile
  open started, marked by `fetchq.profilefetch` (its `asked`), 8 live non-account marks at most.
- Tables are optional (CREATE IF NOT EXISTS), not a schema bump; every reader treats a missing one as empty.

## Bounds (seven review rounds; the abuse lens counted these)

- HTTP only queues. 4 presses a minute per caller, shared with the old ksfmore route. Maps this server does not host
  are refused (404). KSF spends no more than before (its 10 a tick); Momentum adds at most 4 a tick (823 a day).
- Jobs move to the back before asking; a KSF board strike() set aside finishes instead of being asked; a Momentum
  board refusing 3 times in a row is retired for a day; holed boards finish (depth = rows or deepest rank); a job that
  gains nothing on a tail page is done; exhausted boards refresh after an hour without deepening.
- Momentum profile walks: 32 for accounts (first), 8 for others; one unasked for an hour ranks with accounts.
- Ports: KSF's half asks KSF's own name (the map, its base, or the base's port, by KSF's catalogue).
- Old servers: the clients send ksfmore=1 beside fetch=1, so a client that ships first still queues the KSF half
  on a pre-P1448 surfd (whose reply the client reads as KSF's); the site's buttons are served by surfd itself.
- Accepted residuals: an account viewed, then signed in mid-walk, then pressed, walks fully once more; a walk that
  ran while an account was banned keeps view limits after an unban until FORCE_TTL; momfetch exits 1 for host-wide and board refusals alike, so 3 refused tries an hour apart can
  retire a healthy board for a day (a press after it works); a base with two ports reaches the first; a press racing
  another for the last full-walk slot can start one view-limited walk (at most 20 requests); queues are global, so
  many callers can keep them full (429 "busy").

## Verification

- surfd suites under a socket guard (no network): all 107 files; the 6 that fail (test_admin, test_momindex,
  test_ranked, test_receipt_angle_reasons, test_schema_compat, test_verdict_recording_sha) fail identically on main
  192beb7f. test_fetchq 16 (new); 35 mutants over seven review rounds, each killed by its test.
- QC: three VMs 0 warnings (fteqcc 73f9a1a4). board.js parses (node --check).
- Not yet: a live press (needs the surfd generation), a populated in-game click, screenshots of the chips.
