# 0.1.30 - Source polish and the updates since 0.1.29

Released **0.1.30+b89.p945** on23Oct2026; publication completed14:14:40UTC.
Built14:05:26UTC. Requested by the owner after "Close enough!" presentation
acceptance. Build remains89. No overrides. No game was killed or lobby restarted.

## Frozen inputs

- QC6c932b03f942ae257e13a4c1c60038c2efa32622, clean inspected public source.
  Includes the Source weapon/Foley/FOV/motion changes and all37unreleased player
  patch entries through P948, including the peer's Fog/Autumnal/Kvas work.
- Native9e73ae1c8ade050af424182b05ae259371a1eefc, tagpatch-945, exact stamp
  git-7745-patch-945-0-g9e73ae1c8. Reused the just-qualified Windows cohort;
  both installed copies match. No unnecessary native rebuild or source edit.
- Linux built at that same native pin in the existing Bullseye builder;10/10
  production gates pass. Engine GLIBC2.29; combined bootstrap floor2.30, measured
  and acted on the2.31baseline. The documentary QC patch is948; the receipt's
  native patch945 describes the compiled engine, not omitted QC features.
- Launcher public646c8d1, unchanged source since the previous release. Native
  Windows and baseline Linux Cargo builds at2jobs; no compiler warnings.
- Explicit generated inputs only: particles/atlases/icons/local zone library,
  mapmeta/mapdeps/mapparticles/mapdl. Mapdeps equals qualified P9474da8d2c1.
  mapwr regenerated read-only:1169maps.682input hashes retained in task artifacts.
  No canonical dirty config, peer uncommitted source or player data shipped.

## Preparation / exact promotion

One successful `-Bump patch -DryRun`: all3VMs0warnings, dirty/stale/native-skew
and asset-policy gates pass. Both archives exactly match verified stages; signed
feed1703managed rows/761objects. Preview did not change source VERSION.

Trusted prepared candidate SHA256:
a2636ec181494dd4d95589b69ec6ae65c63fca1b7a9fc355464fe54af005565f
Trusted local receipt SHA256:
4f5e51aca9efbe63e052410a58dfd82282cbb8f083ba14ddb5d2629ff1bab687

Prepared-only dry-run revalidated761objects without a compiler/packer/signing.
Published that exact candidate with VerifyFull: both archive full round-trip
hashes match, both standalone launchers match, every761referenced object verifies,
the page is byte-exact, and the real signed predecessor was checked under the
publication lock. One player online: normal512kthrottle, no force/restart.

- Windows40.9MB SHA256:
  1fbad5261d20fbb8cf00fbabe6595635134ced29adbcbbd56c26b1a10b5f18a5
- Linux40.8MB SHA256:
  ff0ceb1f7c8ee7f26dd5b96f002a9e8a4b946d122bff6c0a4eeb62ca11fd4fdf
- Signed live feed SHA256:
  6a22ed11fedda18769a9b3abdeef6ac1fa203da467cd77e802442b61061d283d

## Public acceptance / limits

Default canonical HTTPS smoke passed using the actual newly downloaded launchers
in fresh owned synthetic installs: Windows851and Linux850non-overridden managed
files rehashed,3settings/data/edited-zone sentinels preserved on EACH. Neither
launcher started a game. Existing players use the normal signed update feed.
This is delivery/update integrity acceptance, not performance, every-map visual
acceptance or a claim of exact CSS shader/weapon parity. Human overall Source
presentation acceptance is recorded separately in lextest.md.

Tooling fixes: normalize one non-ASCII title and narrowly explain11licensed
Steam-mounted script/model names; they must not be bundled. New removal/neighbor
controls pass. Two inherited optional literal-census assertions are stale6/3vs8/4;
left untouched and not credited as a complete test-suite pass. Actual mandatory
release gates all pass; no policy, signature or missing-owned-asset bypass.

## Retention

Owned root C:/FTESurf-worktrees/source-polish-20261022T0746Z retains the full
sealed candidate graph, hashes, preparation/publication logs and public-smoke
proof/headers/feed/downloaded launchers/licenses/provenance/synthetic sentinels.
Only exact rehashed signed smoke payloads retired; no real player data touched.
New clean engine-release/launcher-release build copies retired after source/known
ignored-output checks; the shared registry link was unlinked first. Linux baseline
outputs retained separately. Owned WSL idle hold stopped by exact argv identity.
No task process, maintenance gate or shared fixture remains active. Local receipts
may contain machine paths and were NOT uploaded. Source metadata records the
release after acceptance; the published candidate was not rebuilt or relabelled.
