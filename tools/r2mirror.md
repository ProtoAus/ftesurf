# R2 public-asset staging

`r2mirror.py` uploads only allowlisted public map, zone and JPEG groups. It
never deletes source/remote data, changes configs, opens a public bucket,
restarts a service, or declares a CDN cutover. Native/imported recordings,
evidence, database backups and credentials MUST NOT enter its public bucket.

## Layout and safety

Use an owned private task root, outside web-served directories, following
AGENTS.md and Agent workspace lifecycle. Put OWNER.md first. Keep the JSON
config, rclone config, state database and logs owner-only. Credentials belong
in the private rclone file, never CLI values, Git or tool output. A provided
object-scoped S3 token does not imply permission to create buckets, attach a
custom domain, install a Worker or edit DNS/nginx.

The config names source directories (direct children only), not install copies:

```json
{
  "remote": "task:YOUR-PUBLIC-BUCKET",
  "rclone": "/owned/task/bin/rclone",
  "rclone_config": "/owned/task/private/rclone.conf",
  "upload_limit": "3M",
  "groups": {
    "maps": "/actual/map/library",
    "zones": "/actual/client/zone/mirror",
    "mapshots": "/actual/published/mapshots"
  },
  "minimum_files": {"maps": 1, "zones": 1, "mapshots": 1}
}
```

Optional `avatars` accepts only 17-digit JPEG filenames. It does not copy the
entire avatar cache, sidecar text or game-converted formats. Inputs/ancestors
must not be symlinks/reparse points. Partials, subdirectories (including .old),
zero-length files and unapproved filename/extension shapes are excluded.
Register realistic `minimum_files` floors: a missing/emptied source must not
silently become a complete empty mirror. A below-floor scan leaves prior
inventory state unchanged.

Each body is captured from one stable source handle into one owned temporary
file, hashed, uploaded to `objects/<group>/<sha256>.<extension>`, downloaded
again and SHA-256 checked. Source identity/size/timestamps must still match
before readiness is recorded. Old objects stay. ETags are not a substitute for
this whole-body check. Stage disk use is bounded to one asset; no second map
library is created. Only upload traffic is capped; read-back verification is
not subject to that upload cap.

A failed/changed body is excluded from `manifests/public.json`. That manifest
contains only compatibility paths, object keys, SHA-256, sizes and MIME types;
no local source paths. Hash bodies get immutable caching; the changing manifest
gets a short TTL. The manifest's `complete` means the OBSERVED scan is complete,
not an atomic freeze of a growing map library or proof of live client delivery.
Rescan, run a final delta and prove current versions before a cutover.

## Commands

Create the work directory yourself under the task root. Examples contain no
secret values:

```sh
python3 tools/r2mirror.py scan --config /owned/task/config.json --work /owned/task/state
python3 tools/r2mirror.py run --config /owned/task/config.json --work /owned/task/state --group maps --limit 1
python3 tools/r2mirror.py run --config /owned/task/config.json --work /owned/task/state --watch 900
python3 tools/r2mirror.py status --config /owned/task/config.json --work /owned/task/state
python3 tools/r2mirror.py audit --config /owned/task/config.json --work /owned/task/state
python3 tools/test_r2mirror.py
```

Register an owned background process and retain its handles/aggregate log in
OWNER.md. The OS writer lock prevents competing writers and releases on crash.
A resumed scan retries errors and skips already verified unchanged sources.
Audit re-downloads verified bodies; a mismatch removes readiness. There is no
automatic deletion/repair of an allegedly immutable corrupted remote object.
Fix that explicitly only after establishing exact ownership and intended bytes.
Transport output is suppressed; report error classes, not signed URLs/paths.

## Delivery remains a separate deployment

A CDN gateway/edge mapping must translate these existing paths to the verified
content-addressed body, preserving exact case:

- `/ftesurf/maps/<name>.bsp` (connected client)
- `/maps/<name>.bsp` (menu; map to the first path)
- `/ftesurf/maps/zones/local/<name>.json`
- `/board/shot/<name>.jpg` and optionally `/board/avatar/<steamid>.jpg`

Do not make the name-only compatibility URL immutable. Test 404/netchan fallback,
redirect handling, gzip, HEAD/ranges, the largest BSP, cold/warm delivery and
actual fresh clients before changing sv_dlURL/defaults or legacy redirects.
An upload or catalogue `complete` is not evidence of any of those.

Ongoing server map updates need a publication/activation contract and a small
origin fallback for an unmirrored/currently changed version. A periodic mirror
alone does not guarantee that an old name alias matches a newly activated BSP.
Keep original local maps, existing configs and origin routes for rollback.
Do not proxy bulk R2 downloads THROUGH the NanoPi; that keeps the uplink limit.

Replays need a private bucket and their existing authorisation checks before
redirect/Worker delivery. Public manifest staging deliberately has no replay
mode. Adding one is a separate reviewed backend feature, not enabling a generic
recursive sync of game data.
