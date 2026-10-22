# P932 - KSF Watch on configured Momentum map versions

## Problem and boundary

The board already shared imported times across explicit map-port families, but
hid their recording IDs. Watch then refused differing map names, and simply
relaxing admission would still stop playback on the next frame. A downloaded
recording also lived under its actual source map, while a second lookup used the
board's map and fetched it again.

This is observational playback, not a claim that two BSPs, physics or recorded
runs are identical. Only configured families are allowed; suffix resemblance is
not permission. The recording retains its actual source header/hash and imported,
unknown-build, not-native-verified status. Native and Momentum playback fences,
verification eligibility and replay-serving bounds are unchanged.

## Implementation

- `cl_mapports.qc` accepts a bounded family from a successfully parsed board, or
  explicit `of` links from the same persisted map list/freshness choice used by
  the menu. Endpoints/root must be unique and the root unlinked. Unknown names,
  malformed/chained/duplicate relationships and oversized input fail closed.
- The original KSF loader and normalized Watch admission use the same policy.
  The explicit original-file source binding is still required. Existing binary
  layout, finite-value, marker, size/frame, style and bonus limits are unchanged.
- Watch keeps the source map separately from the approved loaded-map lifetime.
  Playback advances on that loaded map and stops after a map change. Non-KSF
  recordings retain their existing source-map lifetime behavior.
- The board exposes existing scoped recording IDs, KSF-only actual row maps and
  family metadata only for tiers containing KSF. Watch/board lines share the
  actual-source cache hint, preserving the existing stage-parent leg-zero hint.

## Verification

Supported `src/build.ps1 -Jobs 8 -NoDeploy`: server, client and menu compile with
zero warnings. Final source includes the independently reviewed correction to
the raw loader's earlier exact-map gate and its declaration ordering.

`tools/p928ksfports_smoke.py` reuses the existing retained-overlay/dedicated-socket
harness. Three actual-client actors provide 25 acted cases:

- Linked subject: 10 cases. The genuine retained Leacon Chateau-fix recording
  opens on Momentum Chateau and advances **10.0000 -> 11.0865**. Its original
  KSF binary advances **10.0000 -> 11.0538**. Source-map and unverified labels
  remain. An explicitly counterfactual exact-header recording advances too.
- Legacy control: 9 cases using the actual deployed P922 client program. Linked
  original/normalized inputs refuse, while the exact-header counterfactual
  advances. This proves the controls acted rather than merely showing silence.
- Unrelated, suffix-only, missing source/binding and raw-unrelated/missing cases
  finish closed with cursor released. Native map mismatch keeps its old warning
  and frame-time stop; it is not claimed as an admission-time rejection. A real
  loaded-map change clears the allowed recording.
- JSON/network/cache subject: 6 cases with deliberately empty owned map lists.
  The same linked input refuses before board-family metadata arrives; after an
  accepted fixture board it and the original binary advance. A real local HTTP
  download publishes byte-identical input under `surf_chateau_fix`; repeating
  the row fetch uses that cache, with exactly one replay GET overall.

The retained linked screenshot was inspected: course/rendered playback, clock,
source `surf_chateau_fix (linked build)` and imported/not-verified labels are
visible while the loaded map is `surf_chateau`. This is not owner feel acceptance.

Backend `test_ksfgrab.py` and `test_variants.py` pass. The optional
`SURFD_BASELINE_MODULE` variants contrast uses the same tiny fixture and synthetic
response clock: six native-only responses (three maps, ranked/community) are
byte-identical, while an old-masked/new-exposed KSF replay control acts.
`test_reccheck.py` and `test_ksfreplay_info.py` pass.

Native reader and held-metadata parser bytes are unchanged. A fixed-input
old/new sweep of 419 REC and 136 VIEW reports exactly the same 283 faulting
reports/284 diagnostics, with zero differing fault lists. The earlier captured
405 REC/120 VIEW corpus is a different dataset: a first absolute-count comparison
correctly failed and was preserved, not used to exclude or reclassify new files.
No native faults were repaired or hidden by this playback change.

## Evidence limits and delivery

Initial test transport used the reserved P925 number; concurrently published
P926/P927 were integrated before the P928 proof build. Published P929-P931 then
advanced while those tests ran; final product metadata is P932. The only later
production-path overlap adds the committed weapon module declaration after the
replay modules; the six functional policy/cache/backend file hashes are unchanged.
Old P925/P928 artifacts and this transport file retain their original names/times. The first completed subject actor was regraded, not rerun,
after fixing a harness assumption: successful `Watch_Status` prints owner/clock,
whereas the explicit open/on tuple exists only in its closed branch. An initial
online fixture decoding error stopped before any actor; explicit UTF-8 fixed it.
Two independent source reviews plus a fresh raw-finding resolution review pass.

No separate frame-only counterfactual binary was needed: advancing playback with
source and loaded map still distinct directly falsifies the former frame fence.
This is not an exhaustive every-map/style/stage/bonus runtime matrix. Those paths
share the policy; their existing decoder/cut logic was not changed. KSF top-up's
separate exact-source queue bug remains tracked in BACKLOG.md, not claimed fixed.

At this feature verification checkpoint, publication and development deployment
are still pending. Windows must retain newer committed native/other feature
work; Pi deployment must not accidentally ship the unrelated unqualified P923
native producer. No release, Build-number bump, native binary, engine pin/tag,
BSP identity or evidence-policy change is part of P932. Human-only confirmation
is tracked in lextest.md.
