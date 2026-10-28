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
| `GET /api/tasrev/rev/<sha>` | the revision, its statements (no keys: the account, ticks, times, released code or not, arrived before the revision or not), its credit as `[first, last, who]` ranges, and `pending` while its credit waits in the queue. |
| `GET /api/tasrev/rev/<sha>/file` | the body, for a client to open. Lines outside the hash (saved, revision, origin, parent name) are the first uploader's. |
| `GET /api/tasrev/map/<map>?before=<seq>` | the map's revisions, newest first by arrival, 100 a page, with `signers`: how many linked accounts have a qualifying statement about it (the first one is credited). |

Refusals answer 200 with `ok: 0` (the game's HTTP client keeps no body otherwise); 503 means
"cannot tell right now, try again" (the account list or the released-code list unreadable, or
the store busy), never a verdict. Budgets, counted before any work (a refused attempt counts):
a peer 200 uploads and 64 MB a day, everyone 5000 and 1 GB; a peer 60 reads a minute (a large
credit counts one more for each 32 KB it sends); 2 GB of revisions, 200000 statements, 32 a
revision from unlinked keys, 4 a key a revision. Two uploads parse, and two credits resolve, at
once; resolved credit is cached as text within 16 MB. The unit runs with MemoryMax=384M,
CPUQuota=50%, Nice=10.

## Credit

Every arrival takes the next number of one sequence; "before" and "earliest" mean by that number.

Credit is stored per revision as ranges naming the revision that supplied each row. A tick whose
row equals the parent's takes the parent's supplier. A changed tick takes the supplier of the
nearest ancestor holding the same row there (a revert credits whoever first supplied it); the
search visits only ancestors that changed that tick (up to 4096 ancestors, 1M rows compared). If
none holds it the tick is this revision's own, except at or before the parent's base (never a
child's). A revision with the same map, base and rows as an earlier one takes that one's credit
unless the earlier one descends from it. Where the service cannot see -- an unseen parent or
ancestor, a cut search, an earlier copy whose chain has a gap -- or the credit would be circular
(a copy of a revision derived from it), the answer is `unknown-ancestry`. An arrival queues every
descendant, and a revision whose credit changes queues its descendants and later copies; each
POST works through the queue for half a second (`tasrevd.py --store ... recompute` empties it,
`rebuild` recomputes every revision).

A supplier revision's ticks go to the first statement about it that names its fields, spans the
tick, names a released csprogs and ARRIVED BEFORE THE REVISION ITSELF; others are skipped. The
account is the one its key was linked to when the statement arrived (unlinked or banned then:
`unattributed`); later links and relinks never move it. So a player links before signing, and a
client registers its statement before it shares the revision. Answers: a steamid, `unsigned`,
`unattributed`, or `unknown-ancestry`.

Open (BACKLOG): rows shifted to other ticks, and a near copy (one row changed, saved as a new
root), are not recognised as the same work -- the copy rule catches exact copies only; a revision
shared privately before its statement is registered can be raced; a child uploaded before its
parent is not supply-checked (only its own signer can lose ticks by a wrong supply).

## Install and released codes

`tools/install_tasrevd.py --source <clean checkout> --commit <sha> --expected-nginx-sha256 <hash
of /etc/nginx/sites-enabled/play.proto.bar.conf> --code <csprogs sha256> [--code ...]` is a dry run;
`sudo ... --apply` installs /srv/nvme/ftesurf-ops/tasrevd/<sha>, state in tasrevd-state (owned by
proto), the unit ftesurf-tasrevd.service on 127.0.0.1:8089 and the nginx location /api/tasrev/.
It never touches surfd, zonepub or a lobby, and refuses to overwrite anything already there.
Each release or lobby deploy appends its csprogs sha256 to tasrevd-state/codes.txt (as proto,
no root): statements name the code that signed them and arrive later.

Tests: `python surfd/test_tasrevd.py`.
