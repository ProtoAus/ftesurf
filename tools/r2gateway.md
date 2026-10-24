# R2 download cutover without a public bucket

`r2gateway.py` is a small read-only WSGI service, separate from surfd. The
existing map and zone URLs hand off to a short-lived **302 to R2's S3 HTTPS
endpoint**. Data travels directly from R2 to the client, not through the Pi.
A custom Cloudflare hostname/control-plane token is not required. This is not
Cloudflare edge caching; a custom cacheable public hostname is a separate step.
No QC, engine, lobby config, board backend, recording or evidence changes.

## Safety contract

- Only public map BSPs, zone JSON and (at the WSGI seam) mapshot JPEGs are
  allowlisted. The nginx template switches only the already-public map/zone
  routes. It does not add picture routes or touch board prefixes/authentication.
- A row must be present and verified in the r2mirror database, match the
  configured source/root/group and exact immutable hash-derived key, and still
  match the source's device/inode/size/mtime/ctime observation. New/replaced,
  missing, queued, corrupt or unreadable rows use the current local file.
  This is a selection-time stat check, not a lock against concurrent source
  replacement after selection. No content hash is computed per request.
- A signed HEAD checks R2 reachability at most once per worker/15 seconds.
  Failed checks retry after2s. While a check is in flight the other requests take the last answer (P981: they used disk, so a game asking during the menu's mapshot burst got the 1 MB/s copy); only a gateway that has never checked uses disk. P981 also routes the game's gzip-accepting, non-Range map requests to verified <sha>.bsp.gz companions (r2gzip.py, gzip_state).
  R2 outages within the successful15s observation window can still fail an
  already-redirected request. This cannot recall a302 already sent. Connected
  engine netchan fallback remains available; retry after the window uses disk.
- nginx intercepts409, gateway failures and timeouts and serves the original
  local map/zone at the existing1MiB/s cap. Missing files remain404; no directory
  listings. Source maps/JSON are never removed. Redirects are `no-store` and
  signatures expire after300s; GET and HEAD have distinct valid signatures.
- The service only opens its explicit mirror database read-only. It never
  imports surfd or its environment, migrates a database, exposes a listing,
  signs arbitrary caller keys, forwards queries, or publishes native recordings,
  identities, receipts, private evidence, avatars or account data. Upstream
  access logging is disabled: never publish signatures or credential configs.

## Preparation and one-time privileged install

Read AGENTS.md and the workspace/Pi-operations notes first. Use a NEW owned task
root and inspected source commit. This process is not a release driver.

1. Complete `r2mirror.py` upload/full-readback verification. Configure an ongoing
   uploader; keep its private configuration and state available. If it stops,
   new or changed content still falls back locally, but is not offloaded until
   verification resumes. Gateway restart must not modify that uploader.
2. Create an operator-owned permanent runtime directory under
   `/srv/nvme/ftesurf-ops/r2gateway-<unique>` with OWNER.md first. Do not retire a
   mirror scratch directory while any active config still references it.
3. Copy only committed `r2gateway.py` and `r2gateway-install.py` into the runtime.
   Render `r2gateway.service` to `ftesurf-r2gateway.service` using that directory
   and a free high loopback port. Render `r2gateway.nginx` to
   `ftesurf-maps.conf`, substituting the same port. Inspect the current installed
   snippet and roots before doing so; paths in this template describe the
   existing NanoPi deployment, not arbitrary installations.
4. Write private `gateway.json` mode600, for example:

   ```json
   {"state":"/owned/mirror/state.sqlite","rclone_config":"/owned/private/rclone.conf",
    "remote":"task:YOUR-PUBLIC-BUCKET","groups":{
      "maps":"/srv/nvme/ftesurf-server/game/momentum/maps",
      "zones":"/srv/nvme/ftesurf-site/zones"}}
   ```

   This uses an R2 S3 rclone section (`endpoint`, `access_key_id`,
   `secret_access_key`), not a Cloudflare control-plane bearer token.
5. Write private `bundle.json` with `runtime`, `nginx_before_sha256`, `port`,
   `probe_path` (an actually current `/ftesurf/maps/<name>.bsp`), and `files`:
   raw SHA256 values for exactly `r2gateway.py`, `gateway.json`,
   `ftesurf-r2gateway.service`, `ftesurf-maps.conf`. Pin the installer hash too
   in your private provenance. `--bundle ...` alone is a read-only check.
6. The operator runs one elevated command:

   ```
   sudo python3 /absolute/runtime/r2gateway-install.py --bundle /absolute/runtime/bundle.json --apply
   ```

   The installer refuses predecessor drift, existing service units, tampering
   and backup collisions. It preserves an exclusive timestamped nginx backup,
   starts only its new unit, proves a real loopback302, tests/reloads nginx and
   enables its unit. Failure restores only its own exact snippet bytes and
   stops only its own unit; a concurrent replacement is retained for inspection.
   A failed install may retain a disabled unit: inspect, do not blindly rerun.
   It never changes sudoers, bypasses a backend transition fence, installs
   packages or stops/restarts a game/server process. gunicorn/nginx must already
   be installed. Successful install is not public-client postflight evidence.
7. Check old public URLs return302/no-store, follow to a correct full R2 body,
   and test a fresh engine client. Check local fallback and board/lobby health.
   Keep timestamped receipt, code/config hashes and the original snippet.

## Verification

All output roots must be NEW and below an OWNER.md ancestor. The first suite is
offline; the installer suite mocks every privileged operation on Linux. The
last explicitly uses real R2 and installed gunicorn/nginx on private loopback
ports, making owned copies of only the smallest verified map and zone. It stops
only its own Popen handles, preserving the test records.

```
python tools/test_r2gateway.py --out /owned/artifacts/unit
python3 tools/test_r2gateway_install.py --out /owned/artifacts/install
python3 tools/test_r2gateway_nginx.py --mirror-config /owned/private/config.json --state /owned/state.sqlite --out /owned/artifacts/nginx
```

The live falsifier proves full-body SHA256, signed HEAD, byte ranges, both map
URL layouts, zone routing, current replaced/unmirrored local files,404 listings,
and origin fallback after killing only its own synthetic gateway. Separate
fresh Windows client arms must actually request the map: a404 control leaves
no map/tmp and reaches failed; a302 to real R2 must reach ok and match the full
map SHA. Do not infer client support from curl alone.

## Rollback / limits

If immediate R2 bypass is needed, stop this gateway unit; nginx then serves
maps/zones from disk. To restore the previous deployment, first compare the
installed snippet with the recorded new hash, restore the recorded original
backup, `nginx -t`, then reload nginx. Do not restore over a peer edit. Keep
original source/data and uploader state; never use destructive rclone sync or
remote deletion. A stopped gateway produces an expected upstream-failure log
until nginx is restored; it is a safe short-term bypass, not the final config.

This does **not** migrate replay API responses/demos, alter the native privacy
boundary, speed up an already cached client file, or turn off the existing
origin transfer cap. Private-bucket signatures are time-limited bearer access
to an individual already-public asset, not bucket-listing credentials. R2
control-plane/domain setup and game-engine auto-retry after a failed already
issued redirect are not claimed.
