# TAS revision service (tasrevd, P1091)

TAS plan 5.3 and 5.4: the place a TAS project revision and its author statements are kept,
and where public credit for TAS inputs is computed. An isolated service beside surfd, like
zonepub: its own store (WAL), read-only use of surfd's `accounts`/`keylinks`, no surfd schema
change, the game's own reader and verifier (tools/tasrev.py).

## What it takes and gives

| Route | Body / answer |
|---|---|
| `POST /api/tasrev/statement` | JSON `{"line": "tasrev 1 sha parent mapcrc first last code pub sig"}` (a rev/<sha>.<id>.tasrev line). Verified on arrival; the key's account is read THEN and kept with it. |
| `POST /api/tasrev/revision` | a .tasp exactly as the game wrote it, `Content-Type: text/x-tasrev` (a cross-site form cannot send it); its revsha must be its hash, and a child's supply must be exact against a known parent of its kind (P1110: a legal start, version 3, counts ticks from its start-zone placement, versions 1-2 from a base save; one never names the other). Kept once by hash with its first-seen time. |
| `GET /api/tasrev/rev/<sha>` | the revision, its statements (no keys: the account, ticks, times, released code or not, arrived before the revision or not), its credit as `[first, last, who]` ranges, and `pending` while its credit waits in the queue. |
| `GET /api/tasrev/rev/<sha>/file` | the body, for a client to open. Lines outside the hash (saved, revision, origin, parent name) are the first uploader's. |
| `GET /api/tasrev/map/<map>?before=<seq>` | the map's revisions, newest first by arrival, 100 a page, with `signers`: how many linked accounts have a qualifying statement about it (the first one is credited). |

Refusals answer 200 with `ok: 0` (the game's HTTP client keeps no body otherwise); 503 means
"cannot tell right now, try again" (the account list or the released-code list unreadable, or
the store busy), never a verdict. Budgets, counted before any work (an attempt of the right size
and type counts even when refused): a peer 200 uploads and 64 MB a day -- the bytes a revision
keeps (its rows and credit too) count, not just what was sent -- and everyone 50000 and 1 GB; a
peer 60 reads a minute (a large credit counts one more for each 32 KB it sends); 2 GB stored, 200000
statements from unlinked keys, 32 a revision from unlinked keys, 4 a key a revision. A statement
whose revision has not arrived within 7 days is dropped. Two uploads parse, and two credits resolve, at
once; resolved credit is cached as text within 16 MB. The unit runs with MemoryMax=384M,
CPUQuota=50%, Nice=10.

## Game client (P1140)

Host the map locally and open the TAS menu's **Shared** tab. Accept the online
terms before browsing. Save a **legal-start v3** project; link the signing key to
your account and physically press **Sign before Share** if you want linked credit.
Sharing requires explicit public-upload confirmation. It uploads project metadata
(including saved date and local project metadata) and existing public-key
statements, never a private signing key. It does not sign automatically.

Console equivalents:

- `tas project share yes` publishes the current saved legal-start revision.
- `tas project share yes <hash>` publishes an explicitly chosen retained v3
  revision on this map, even without an attached project. A successful child
  upload prints its parent hash; share still-private retained ancestors the same
  way for complete history. Nothing is recursively made public without asking.
- `tas shared refresh`, `tas shared select <zero-based-row>`, `tas shared status`
  and `tas shared open` browse the current map and open the selected revision.
- `tas project open <hash> [new-name]` downloads and validates a v3 project for
  this map, then uses the ordinary local TAS loader. It is not a human run import.

Downloads check size, strict project syntax, map/profile identity and the requested
canonical hash before installing under a new name. Existing final, staged and
`.new`/`.new2` recovery paths are protected, including unreadable files and loose
files added after startup. Failed final rename retains the closed download stage.
Do not edit the same paths from another process during the import transaction;
this is not an atomic multi-writer or power-loss durability protocol. Base-save
v1/v2 projects need their author's private base and are refused by this portable
game workflow before starting an upload or staging an incoming body.

The credit view is informational (at most 4096 ranges / 1 MiB detail). A larger
or unavailable credit view does not silently remove the validated revision's
Open action. Attribution is the service's first-seen contract below, not a
physics verdict, verified time, or proof of human input. Late signing/linking
cannot retrospectively claim already-seen contributions. An already-sent statement
can remain at the service if a later body upload fails.

Transport uses `https://play.proto.bar/api/tasrev`. The `tas_directory` test
override accepts only `http://127.0.0.1:<port>/api/tasrev`, decimal port 1..65535;
other values fall back to the fixed public service. `tas shared status` reports
the resolved endpoint without issuing a request. Native fixture signatures and
synthetic credit-boundary DTOs are not real-account/physical-key or human UI
acceptance; see lextest.md. Source publication and actual deployment are separate.

## Credit

Every arrival takes the next number of one sequence; "before" and "earliest" mean by that number.

Credit is stored per revision as ranges naming the revision that supplied each row. A tick whose
row equals the parent's takes the parent's supplier. A changed tick takes the supplier of the
nearest ancestor holding the same row there (a revert credits whoever first supplied it); the
search visits only ancestors that changed that tick (up to 4096 ancestors, 1M rows compared). If
none holds it the tick is this revision's own, except at or before the parent's base (never a
child's). A revision with the same map, base and rows as an earlier one takes the earliest such
one's credit unless that one descends from it. Where the service cannot see -- an unseen parent or
ancestor, a cut search, an earlier copy whose chain has a gap, a parent or ancestor of the other
kind (it arrived after its child) -- or the credit would be circular (a copy of a revision derived
from it), the answer is `unknown-ancestry`. The copy rule does not look at the kind or the start
zone, and it is exact: only the same block of rows at the same ticks matches, so a legal start's
run re-encoded as a base save from its start (rows shifted by `startat`) is not caught (BACKLOG). An arrival, and a
revision whose credit or changes move, queue every revision that may read it -- descendants, the
later copies of each, and those copies' descendants, at most 20000 -- and nothing else does, so the
queue settles; each POST works through it for half a second, and a waiting revision reads
`pending` (`tasrevd.py --store ... recompute` empties it, `rebuild` recomputes every revision).

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

An upgrade (P1119): `--source <checkout> --commit <sha> --upgrade-from <installed sha>` is a dry
run; under sudo with `--apply` it writes the commit's own files (git objects, not the working
tree) to /opt/ftesurf-tasrevd/<sha> (every directory above it root's alone: /srv/nvme/ftesurf-ops
is proto's), points the unit at it and restarts, with Ctrl-C and hangup ignored until the new
source answers locally and publicly; the outcome is also written to that directory's UPGRADE.txt.
As root it runs git and the import check as proto (git with the checkout as a command-line
safe.directory, without sudo's SUDO_*). It
refuses unless the unit and the nginx snippet are byte for byte what this installer wrote for the
installed release, with no drop-ins or pending reload. If the new release does not serve, the old
unit is put back, restarted and probed, and the error says whether the old release serves again.
State, codes.txt and nginx are not touched. Limits: rows the new code wrote before a rollback stay;
an upgrade runs no schema change (a release that needs one needs its own step); a failed upgrade
keeps its directory, which must be removed before a retry; a downgrade or a change of unit settings
is not an upgrade; a fresh first install still writes under /srv/nvme/ftesurf-ops/tasrevd (proto's
parent). Tests:
`python3 tools/test_install_tasrevd.py` (Linux). The signal test installs known handlers
before the switch, so it also detects a missing signal hold when the suite itself runs under
`nohup` (where SIGINT/SIGHUP may already be ignored). On the Pi as proto, the final suite
passed all 20 tests and rejected all 23 retained installer mutations. These are temporary-tree
and modelled-systemd checks, not proof that an owner has applied the live upgrade.

Live upgrade: Lex applied `71989410041492504ee88c4bbe85e7cea43ecc09` on 30 Oct 2026
(service start 05:34:23 UTC; postflight 05:40:28 UTC). All six deployed files match that
commit, the exact unit and actual master/worker cwd point at its root-owned release,
and both loopback and the public API report that source. The installed parser accepts
the retained canonical v3 fixture and rejects a malformed input row. Existing owner-only
state passes a read-only SQLite quick_check; no pre-upgrade row-identity snapshot was
captured, so this is health/path verification, not a historical row-equality claim.
The original `5352dbae5f160a8575e4d0ec7239ecc7e86b4154` release is retained for rollback;
`UPGRADE.txt` in the new release records the successful transaction. No game/lobby swap.

Tests: `python surfd/test_tasrevd.py`.
