# World of Surf 0.1.41 — published 6 Nov 2026

Public page: https://proto.bar/ftesurf/

## Exact delivered snapshot

- QC/release source `61c45b1cdb544697a90cc67f408cb876eddfe6e7`,
  branch `release/0.1.41`, annotated public tag `v0.1.41`. Existing QC Build89
  retained, not bumped. All three VMs built with zero warnings; authored client/server/
  shared/menu source bodies match delivered main `2f2f3946`.
- Native source/tag `1355c256a758f01be88280c1bc03d8b81f92709b` / `patch-1348`.
  Windows uses the exact qualified normal product, no probe executable. Linux
  was built from this exact pin in the standard locked Bullseye builder and
  passed every dependency/glibc/RPATH/revision/plugin gate.
- Later main P1349 compiler metadata arrived during preparation. It was NOT
  silently folded into this tested native1348 candidate. Its notes and newer
  engine pin remain pending on main; this release contains the eighteen patches
  explicitly sealed in its own release notes.
- Bootstrap source `1538d9c4866c32282fef1060be8248c0e773b346`, complete source
  fingerprint `f7c51d732e7904048c6583d48d79924a82b87e7d5938db523573ea26bfa111c8`.
  Both locked optimized builds have clean source, full notices and measured
  provenance. Combined Linux minimum glibc is 2.30.

## Immutable publication

| Artifact | Bytes | SHA256 |
|---|---:|---|
| [Windows](https://dl.proto.bar/ftesurf/ftesurf-0.1.41.7z) | 77969969 | `73aaadbb20e45d052e3b479ee95fb9ed3e32193061726e0c5c4aa8cd5f236b38` |
| [Linux x86-64](https://dl.proto.bar/ftesurf/ftesurf-0.1.41-linux-x86_64.tar.xz) | 78025540 | `cc70d2619bc3af60365756555779d657334b9b06f89a23577688d824b7d398c4` |

Prepared candidate SHA256:
`0cac4638aadb25cfc37633a757a61a8bda70b28c774cc4a891807baee4753383`.
Prepared build-receipt SHA256:
`2596dafd3ba16e84ced2e1daa63b4846990d72b965e204c65fc7728302a0082d`.
Public `version.json` omits that receipt's tool/host field, as intended. Its bytes
match the sealed site JSON exactly; SHA256:
`285175afb1aa872380c54c022193c89841ee0f8bc7961fac6307675c3097c783`.
Signed update-feed SHA256:
`39eb63a06f2de3ae65e890af3e9292d6202b24e73e87fd68a2c55047e3b5b262`.
Previous feed:
`9050be03a2bcea9a52d72668344d41d42392f48bf25567f51dfee74678c63e6f`.
No overrides, pruning, QC Build bump or post-preview rebuild.

Both archives were downloaded in full from the public CDN and SHA256 matched.
Both standalone launchers were similarly round-tripped. All914 referenced
update objects were uploaded immutably, downloaded back and verified before the
atomic site/feed promotion. Public page bytes match the prepared page; the
signed public update feed matches exactly and is no-cache.

Default-production-HTTPS launcher acceptance passed for BOTH platforms:
Linux1006 / Windows1007 managed files independently rehashed, three protected
synthetic settings/data/edited-zone sentinels preserved on each. No game was
started. Update permission/opt-out policy is unchanged; the bootstrap itself
remains a separate archive upgrade, not an ordinary managed update file.

## Packaging controls and limits

Early preflight caught the generic authored `models/snow/flakes.iqm` missing from
its nonrecursive allowlist; the exact asset is now declared. The generated mesh
is narrowly ignored as a release input, not used to hide source changes. Asset
seeding used the SHA256-verified PUBLIC0.1.40 archive, never a copied player
install, private data or uncommitted peer config. The gated map-media refresh /
export passed with3282entries,811dependencies and no cell/tier loss. Final ship
policy classified all557literals without a miss. Stages contain1009Windows /
1008Linux files, with no denied path; archive contents match their stages.

First source-clean and Build-number inference refusals happened before sealing.
Their original logs were kept. Existing Build89 was supplied explicitly; the
successful zero-warning VM outputs were reused rather than rebuilt. Exactly one
successful preview was sealed and its exact bytes were published.

Released CSea6720026f7a5ab472310a2e6af6f801fd9fb94413a8110bb71675bf9aa202a3
was admitted before publication, preserving the prior catalog and backend actor;
active lobby programs were not replaced as part of this public release.

Archive/update installation, dependency gates and state checks are NOT a visual,
frame-rate or owner-feel pass. Final in-game void-transition confirmation and
unprofiled timing remain pending; no universal shader/resource readiness or
zero-stutter guarantee is claimed. Earlier normal dual-Windows/all12lobby
rendering deployment is recorded in `p1348-overview-state.md`.
