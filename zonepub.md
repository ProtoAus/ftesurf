# Saved-zone admin drafts

## What is and is not implemented

The editor's **Upload saved** action freezes the saved local JSON, asks for an
explicit Enter confirmation, and submits it as an authenticated admin draft.
Unsaved edits are not silently saved/uploaded. The native existing key-event
signer supplies a distinct zone-upload proof; a command-generated confirmation
cannot substitute for that event. Old engines fail with an update message.

This deliberately preserves the owner's October 12 decision: **upload is not
publication**. Draft submission changes neither live geometry nor existing
times. Review/activation must consistently update the authoritative site layer,
lobby files and client downloads, with rollback/provenance and an explicit times
choice. That live activation operation remains pending; do not describe a stored
draft or staged file as active. In particular, do not deploy an unreviewed surfd
generation or migrate a sealed production schema to finish this feature.

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
zone files or leaderboard. There is no public draft list/read/activation route.

Use the dedicated loopback WSGI service and exact `/api/zones/` HTTPS proxy route,
not Flask's development server for production. `zonepub_wsgi.py` trusts forwarding
only from the local proxy. Keep its store/service provenance private.

`tools/install_zonepub.py` is a **new-service-only, dry-run-first** owner helper.
It requires a clean inspected source commit, exact nginx predecessor hash, the
existing account DB, and the actual deployed `csprogs.dat` file(s). It refuses an
existing service/store/route/occupied port. It installs an independent restricted
unit and proxy snippet, verifies nginx before reload, and has a bounded rollback
on failure. Read-only account schema checks reject the historical empty DB sibling
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

## Review staging (not activation)

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

Real activation still requires the documented authoritative/fleet operation and
its evidence/ranked-policy checks. Do not reload an in-progress run's timer table.
Verify the public JSON bytes and each destination file, activate only at a safe
map boundary, and record UTC provenance/rollback references. The outstanding
integration is tracked in ROADMAP.md; end-to-end public availability is not proved
by backend unit tests or by a local loopback draft test.

## Verification

`python tools/test_zonepub_install.py` covers read-only/missing/empty DB checks,
occupied-port refusal and wrong-source/malformed-health controls without root.
`python surfd/test_zonepub.py` exercises actual Ed25519 proof verification, role
and revocation checks, nonce/body binding, bounds/invalid geometry, and no live
file/account mutation. `python tools/test_mapmedia.py` covers inventory pagination,
image validation/regeneration, deleted-thumbnail recovery, XL choice for larger
cells, and append-only atlas preservation. Native runtime checks must additionally
prove a real request, pending/ready image behavior, malformed refresh preservation,
and rejected synthetic versus accepted native confirmation; silence is not a pass.
