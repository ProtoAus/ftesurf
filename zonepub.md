# Admin zone uploads, published on acceptance

## What is implemented (P729, P815)

The editor's **Publish saved** button (its own device click; since P1081
`zone_edit publish` may open the same dialog, but only a click on its button sends) reads this install's OWN saved JSON whole
(`data/maps/zones/local/`, not the loose shipped copy), refuses unless those
bytes hash to the table on screen, and opens a dialog with map, zone count and
crc (P822). Its Publish -- the mouse press itself, or Enter -- submits them with
a distinct zone-upload proof from the native key-event signer; the dialog is
cancelled whenever the panel stops showing it. Old engines fail with an update
message.

**Publication is automatic since P815** (Lex, 19 Oct: "I want it to work
automagically"; existing times are KEPT). This replaces the 12 Oct "upload is
not publication / reviewed activation" decision. An accepted upload from a zone
admin is queued (`publications`, zonepub_publish.py) and written, once no lobby
has had the map loaded for 10 minutes with the lobbies heard throughout, to
the lobbies' `game/ftesurf/maps/zones/local/<map>.json` and the site's
`ftesurf-site/zones/<map>.json` (what clients fetch and the R2 mirror copies;
the R2 gateway serves the Pi's copy until the mirror has verified the new one).
Why wait: `retry` reloads the map, so a lobby on it would re-zone a run in
progress, and the sweeper verifies a finished run against the files as they
are then -- the same rule mapwatch.py keeps. The service hears the lobbies
every minute (zonepub_wsgi.py) and publishes what has become quiet; a newer
upload of the same map supersedes a pending one; 20 publishes per account an
hour. Each write is a same-directory temporary and one rename after the row
holding the replaced bytes is committed; a failed second write puts the first
back (`failed`), a failed put-back is `partial` for an operator.

What it does not protect: saves carry no zonecrc, so a save from before a
publish loads into the new zones (as a segmented run, which pm_verify refuses
for its load anyway); a parked Multi-Session run on the map is dropped at its
resume ("the zones changed"); a later re-check of a run set under the old
zones is REFUSE, as after any zone change.

`zonepub.py --store <store> rollback --map <m> [--id <n>] --publish-dir <lobbies> --publish-dir <site>`
(as proto, never root) puts back what publish n (default the newest live one)
replaced, if the files are still what the last publish or rollback left, and
only while the map is quiet (`--anyway` overrides). `apply` runs a tick by hand.

What a client shows: the server publishes serverinfo `zonecrc` (sv_zones.qc).
A client whose table differs, and is not its own saved edit, fetches the map's
file from our origin (cl_zonedl.qc `ZDL_SOURCE`; a server can `set`
`cl_download_zonesrc`, so its value only switches the fetch off with ""), at
most once a minute per map, and switches to whichever copy it holds (dl,
curated, shipped, online) whose crc equals the server's -- never mid-run or
while the zone editor is open or unsaved (cl_zones.qc `Zone_SyncServer`). An
own edit is a loose `data/maps/zones/local` file (`whichpack` ""), never one in
a pack. Load order on the client, and on a server the map picker started (its
Play sets `sv_zones_curated 1`): own edit, the menu's curated refresh, the
shipped library, Momentum's online set, then (client only) dl/. Every other
server -- the lobbies and sweep.py's verifier alike, so they read one table --
keeps the old order, maps/zones/local then online then the BSP. A picker game
now times with a curated copy over the shipped one (91 of 642 maps differ
between the two on 19 Oct; the curated copy is what the site serves). Not
closed: `maps/zones/local/<map>.json` resolves `data/` first through every mount
(QC_FixFileName), a map's own pack included, on lobbies as before P815 (BACKLOG).

P1081: publishing also works from one of OUR lobbies (not any server). A server's map,
packages and commands could stand in for the admin's table, so:
- The service decides "ours": the challenge carries the client's own netchan address
  (`serverkey("ip")`, which the server cannot set) or `host`; zonepub.py `official()`
  accepts only a lobby cfg's `sv_port` at our public name (`SURFD_PUBLIC_HOST`) or one of
  its global addresses. Loopback, private, link-local and unspecified addresses are the
  client's own network and are refused (the client already sends them as "unknown"); a name
  a client sends is never looked up, only our own, cached five minutes; the rate limit runs
  first. Only our csprogs signs, and only a nonce it asked for, so a third party cannot
  borrow it.
- Off-host the client (`ZonePub_Offhost`) refuses a table any input without a device
  touched (`zone_cmd_taint`: every `zone_edit` word but publish/upload/edgeprobe/status,
  and every `!cl_input_real` event reaching the editor -- chat_mouse, hud_edit key/click/
  type), one whose base came from the map's BSP or a package (`zone_base_untrusted`), and
  a saved file that is not loose in our own folder (`whichpack(path, 2) == "ftesurf"`;
  not found fails closed). Such a table cannot be saved, or its file removed, off-host.
  A load from files clears the taint.
- A real press counts where the device put the pointer (`cl_ptr_real`, recorded in
  CSQC_InputEvent before any panel takes the move; lost focus, a new editor cursor and
  mouse-look forget it), never where a synthetic event moved it, and on a confirm page only
  after a real move once the page armed. A page is unarmed until drawn; buttons that move
  under a resting pointer (hud_scale) arm again.
- A command may OPEN the dialog (`zone_edit publish`) but never saves: the saved file must
  already be the table, read back over it and compared as Save checks its `.part`. A
  dialog a command opened takes a click only; every confirm arms 0.6 s after its page
  appears; Send still refuses a command. "Reload now" sits at the far left, warning
  colours, away from Cancel (which keeps P815's place).

A proof names the csprogs that signed it; in publishing mode the service accepts only a
deployed `csprogs.dat` that also carries P815's upload flow (zonepub.py `PUBLISH_MARKER`),
because the P729 client signs the same kind and posts the same body from any server. The
installer takes `--game` as `csprogs.dat` files only, never a `.prev`.

**Reload now (P1081).** The challenge also returns `nonce_now`, bound to the same map and
bytes; one challenge is one publish whichever nonce is signed. An upload signed with it
(and a csprogs carrying `NOW_MARKER`) queues `force`; zonepub_publish.py's docstring has
the steps. In short:
- Targets are our lobbies on or assigned to the map: a lobby cfg `sv_port` at
  `SURFD_PUBLIC_HOST` (how surfd writes a trusted lobby) or a literal address of this
  machine. If any lobby there is not ours, it holds (`hold` says why); an empty target set
  counts only when no lobby is on the map.
- Warn (`say`, acked by a `status` reply -- weak: the lobby answered, not that a player read
  it; all must answer or it retries; unanswered for 15 min: `expired`, nothing installed).
- After 60 s, two sweep completions newer than the stamp at the grace's end (sweeps cannot
  overlap, so the second started after it) and nothing owed; re-warn if over 5 minutes old;
  a lobby that arrived since is warned and waited for; pending an hour: `expired`.
- Write (or find the bytes live), stamped after `put()`, then one round per tick:
  `changelevel` each target until its `status` shows a load after the write. A try is spent
  only on a changelevel sent; 5 tries or 30 minutes leave `live-partial` (`noop-partial`)
  with the ports in `partial` -- rollback treats it as live, and `zonepub.py reload --map M`
  re-arms it (`status --map M` shows the newest rows). A crash between the write and the
  reload recovers as live and the reload still runs.
- rcon goes through rcon.py (its socket now connected, so only the lobby can answer) and a
  budget shared by zonepub's processes (`rcon-budget.json`, 3 packets per port per 30 s,
  stamped inside its lock; admin.py keeps 8; the engine blocks for 24 h past 15). rcon also
  shares the engine's 20 packets/s connectionless budget with public status queries, so a
  flood can delay the warning -- which then expires cleanly rather than writing.
Password and public name: `SURFD_RCON_PASSWORD`, `SURFD_PUBLIC_HOST` in
/srv/nvme/surfd/surfd.env; ports: /srv/nvme/ftesurf-server/game/ftesurf/cfg/lobby. Never past
an owed verdict; evidence posted after the warning and not yet indexed meets the new zones.
`init` adds the P1081 columns to an older store; the P815 release still runs on it.

Installed 2026-10-19T04:05Z by the owner, release d9bf33b4
(`/srv/nvme/ftesurf-ops/zonepub/<commit>`, state `/srv/nvme/ftesurf-ops/zonepub-state`); the
role is granted. Two first `--apply` runs failed safe and taught the preflight: the release
directory holds only FILES, which must import alone (accounts.py imports steam), and nginx loads
`sites-enabled/play.proto.bar.conf`, a regular file on the Pi (it carries the R2 gateway's
include), not a link to sites-available. A failed run leaves the unit and snippet (root) and the
state directory: a rerun refuses until they are removed.

Refusals answer 200 with `ok:0`, `error` and `status` (P826): the game's HTTP client keeps no
body for any other status, so a 403's reason never reached the player. A new release goes in
with `install_zonepub.py --upgrade --source <checkout> --commit <sha> [--apply]`: it requires
the installed unit, state and snippet, writes `zonepub/<sha>`, runs the idempotent `init`, and
rewrites only the unit's WorkingDirectory, SURFD_TOOLS and ZONEPUB_SOURCE; it probes loopback
and public HTTPS and on any failure puts the old unit back and the old release serving.

Not checked: that the uploader's BSP is the build the lobbies load (zones are
by map name). A wrong-build upload is visible at once in the game; roll it back.

Roles are server-side, deny-by-default and revocable. A confirmed display name or
Steam identity is not a role grant. A banned/unlinked/non-admin account is denied.
No admin secret/SSH key is shipped in QC, and a client cvar cannot grant access.

## Isolated service

`surfd/zonepub.py` uses a separate SQLite store for roles, short-lived challenges
and drafts. It reads the existing account/key-link database read-only through
the established account role resolver. Proofs are bound to the intended host,
zone-upload purpose, approved CSQC identity, map and exact frozen bytes. Bounds
cover request size, polygons/table capacity, challenge lifetime, pending counts,
proof attempts and draft capacity. Failure does not touch the live account schema,
zone files or leaderboard; only an accepted admin upload writes the publish
directories. There is no public draft list/read route.

Use the dedicated loopback WSGI service and exact `/api/zones/` HTTPS proxy route,
not Flask's development server for production. `zonepub_wsgi.py` trusts forwarding
only from the local proxy. Keep its store/service provenance private.

`tools/install_zonepub.py` is a **new-service-only, dry-run-first** owner helper.
It requires a clean inspected source commit, exact nginx predecessor hash, the
existing account DB, and the actual deployed `csprogs.dat` file(s). It refuses an
existing service/store/route/occupied port. It installs an independent restricted
unit and proxy snippet, verifies nginx before reload, and has a bounded rollback
on failure. P815: the unit may write only its store and the publish directories
(`--publish-dir`, default the lobbies' and the site's zone folders, which must be
real directories owned by proto). Read-only account schema checks reject the historical empty DB sibling
(the real default is `surfd/data/surfd.db`). Before exposing the route it verifies
the new master's origin/lifetime/socket and exact source header over loopback;
public HTTPS must then return the same source. It never restarts or migrates the main surfd service. Root permission
is required only for `--apply`; granting a service role is a separate decision.

```sh
python3 tools/install_zonepub.py --source /path/to/clean/source \
  --commit <inspected-sha> --expected-nginx-sha256 <measured-predecessor> \
  --game /path/to/deployed/csprogs.dat
# Owner reviews the dry run, then explicitly reruns with --apply.
```

Do not put real identities in command arguments, public docs, logs or Git. A
private owner-approved identity file is used for the separate role operation:

```sh
python3 surfd/zonepub.py --store /private/path/zones.sqlite3 grant \
  --identity-file /private/path/approved-zone-admin
# Same command with revoke removes future upload permission immediately.
```

Do not infer a grant from a sample, repository owner or earlier identity
confirmation. Until explicit approval, leave the role table empty.

## Review staging (optional, before P815 the only route)

Inspect the private draft and its exact SHA256, target BSP/revision, geometry,
annotations and any settings changes. The staging helper exports the reviewed
raw zone bytes; account-envelope identity fields are not exported, but arbitrary
upstream annotations still require privacy review before publication.

```sh
python3 surfd/zonepub.py --store /private/path/zones.sqlite3 stage \
  --draft <reviewed-draft-id> --reviewed-sha256 <reviewed-zone-sha256> \
  --reviewed-bsp-sha256 <reviewed-bsp-sha256> --bsp /path/to/map.bsp --output /owned/task-root/reviewed-new-dir --times keep
```

The output must be new and under an OWNER.md task root, never web-served scratch.
It contains the geometry and a REVIEW.json binding map, zone hash, BSP hash and
explicit times policy. A changed draft/hash/BSP refuses staging. `hide`/`archive`
refuse because their separate reviewed leaderboard operation is not implemented;
they never silently fall back to keep. No staging mode deletes/relabels times.

Staging writes owned files only; publication is the upload path above.

## Verification

`python tools/test_zonepub_install.py` covers read-only/missing/empty DB checks,
occupied-port refusal and wrong-source/malformed-health controls without root.
`python surfd/test_zonepub.py` exercises actual Ed25519 proof verification, role
and revocation checks, nonce/body binding, bounds/invalid geometry, no account
mutation, and (P815 `Publish`) every directory written, rollback, a failed second
write undone, a symlinked destination refused and non-admins writing nothing.
Run it on the Pi too: the 0644 mode check is skipped where there is no getuid.
The client half is `tools/p815zones.py` (lobby, own edit, hosted). `python tools/test_mapmedia.py` covers inventory pagination,
image validation/regeneration, deleted-thumbnail recovery, XL choice for larger
cells, and append-only atlas preservation. Native runtime checks must additionally
prove a real request, pending/ready image behavior, malformed refresh preservation,
and rejected synthetic versus accepted native confirmation; silence is not a pass.
