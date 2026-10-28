# TAS revision service (tasrevd, P1091)

TAS plan 5.3 and 5.4: the place a TAS project revision and its author statements are kept,
and where public credit for TAS inputs is computed. An isolated service beside surfd, like
zonepub: its own store (WAL), read-only use of surfd's `accounts`/`keylinks`, no surfd schema
change, the game's own reader and verifier (tools/tasrev.py).

## What it takes and gives

| Route | Body / answer |
|---|---|
| `POST /api/tasrev/statement` | JSON `{"line": "tasrev 1 sha parent mapcrc first last code pub sig"}` (a rev/<sha>.<id>.tasrev line). Verified on arrival; the key's account is read THEN and kept with it. |
| `POST /api/tasrev/revision` | a .tasp exactly as the game wrote it, `Content-Type: text/x-tasrev` (a cross-site form cannot send it); its revsha must be its hash, and a child's supply must be exact against a known parent. Kept once by hash with its first-seen time. |
| `GET /api/tasrev/rev/<sha>` | the revision, its statements (no keys: the account, ticks, times, released code or not, registered before the revision or not) and its credit. |
| `GET /api/tasrev/rev/<sha>/file` | the body, for a client to open. Lines outside the hash (saved, revision, origin, parent name) are the first uploader's. |
| `GET /api/tasrev/map/<map>?before=<t>` | the map's revisions, newest first, 100 a page, with how many linked statements came before each. |

Refusals answer 200 with `ok: 0` (the game's HTTP client keeps no body otherwise); 503 means
"cannot tell right now, try again" (the account list or the released-code list unreadable, or
the store busy), never a verdict. Budgets, counted before any work: a peer 200 items and 64 MB a
day, everyone 5000 and 1 GB; 2 GB of revisions, 200000 statements, 32 a revision, 4 a key a
revision. The unit runs with MemoryMax=384M, CPUQuota=50%, Nice=10.

## Credit

Computed once, when a revision arrives, as tick ranges naming the revision that supplied each
row: the nearest ancestor (32 deep) holding the same row at that tick passes on its supplier, so
a revert credits whoever first supplied the row; rows past a parent this service has not seen
belong to nobody yet (`unknown-ancestry`) and the waiting revisions are recomputed when it
arrives; a revision whose base and rows equal an earlier one's (not its own descendant) takes
that one's suppliers.

A supplier revision's ticks go to the first statement about it that names its fields, spans the
tick, names a released csprogs and was registered NO LATER THAN THE REVISION ITSELF; others are
skipped. The account is the one its key was linked to when the statement arrived (unlinked or
banned then: `unattributed`); later links and relinks never move it. So a player links before
signing, and a client registers its statement before it shares the revision. Answers: a steamid,
`unsigned`, `unattributed`, or `unknown-ancestry`.

Open (BACKLOG): rows shifted to other ticks are not recognised as the same work; a revision
shared privately before its statement is registered can be raced.

## Install and released codes

`tools/install_tasrevd.py --source <clean checkout> --commit <sha> --expected-nginx-sha256 <hash
of /etc/nginx/sites-enabled/play.proto.bar.conf> --code <csprogs sha256> [--code ...]` is a dry run;
`sudo ... --apply` installs /srv/nvme/ftesurf-ops/tasrevd/<sha>, state in tasrevd-state (owned by
proto), the unit ftesurf-tasrevd.service on 127.0.0.1:8089 and the nginx location /api/tasrev/.
It never touches surfd, zonepub or a lobby, and refuses to overwrite anything already there.
Each release or lobby deploy appends its csprogs sha256 to tasrevd-state/codes.txt (as proto,
no root): statements name the code that signed them and arrive later.

Tests: `python surfd/test_tasrevd.py`.
