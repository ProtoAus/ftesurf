# TAS revision service (tasrevd, P1091)

TAS plan 5.3 and 5.4: the place a TAS project revision and its author statements are kept,
and where public credit for TAS inputs is computed. An isolated service beside surfd, like
zonepub: its own store, read-only use of surfd's `accounts`/`keylinks`, no surfd schema change.

## What it takes and gives

| Route | Body / answer |
|---|---|
| `POST /api/tasrev/statement` | `{"line": "tasrev 1 sha parent mapcrc first last code pub sig"}`, the game's rev/<sha>.<id>.tasrev line. Verified on its own; registering it at signing time fixes that key's first-seen time for the revision. |
| `POST /api/tasrev/revision` | a .tasp exactly as the game wrote it (version 1 or 2, its revsha its hash); kept once by hash with its first-seen time. |
| `GET /api/tasrev/rev/<sha>` | the revision, its statements (each checked against the content, released code or not, the account it belongs to) and its credit. |
| `GET /api/tasrev/rev/<sha>/file` | the body, for a client to open. |
| `GET /api/tasrev/map/<map>` | the map's revisions, newest first (200). |

Refusals answer 200 with `ok: 0` (the game's HTTP client keeps no body otherwise). A peer may
upload 400 items a day; the store holds at most 2 GB of revisions.

## Credit

Per tick, never per signed span:
- a tick's row goes to the EARLIEST revision of the known chain that holds that row at that
  tick (a revert credits whoever first supplied it);
- through the first statement about that revision that verifies against its content, spans the
  tick and names a released csprogs (`codes.txt`, one sha256 a line, appended at each release
  or deploy: statements are signed offline and arrive later);
- to the first account its key was seen linked to at or after the statement arrived (an
  append-only `keyseen` history; surfd's keylinks is overwritten on relink). A later relink does
  not move it; a key linked after its statement arrived is credited once it is seen.

Answers: a steamid, `unsigned`, `unattributed` (unlinked key or unreleased code), or
`unknown-ancestry` (the run of equal rows reaches a parent this service has not seen: nobody's
until that parent is uploaded).

## Install (owner, root)

`tools/install_tasrevd.py --source <clean checkout> --commit <sha> --expected-nginx-sha256 <hash
of /etc/nginx/sites-enabled/play.proto.bar.conf> --code <csprogs sha256> [--code ...]` is a dry run;
`sudo ... --apply` installs /srv/nvme/ftesurf-ops/tasrevd/<sha>, state in tasrevd-state, the unit
ftesurf-tasrevd.service on 127.0.0.1:8089 and the nginx location /api/tasrev/. It never touches
surfd, zonepub or a lobby, and refuses to overwrite anything already there.

Tests: `python surfd/test_tasrevd.py` (chains, reverts, unknown ancestry, late and moved links,
unreleased code, refusals, first-seen times).
