# P1342 — short save chains and coherent hold release

## Problem / change

Only current/neighbor/first/last save rows were published, so two or three rapid
steps could not be predicted. Release reused a previous load speed; independent
HOLDVEL stats could be older than a cursor update. Independent review then found
that even a coherent cursor is NOT proof of the held row: a failed state-file
load advances the cursor while the authoritative hold remains on the old row.

Optional stat207 contains COMPLETE quoted C50, actual-held validity/velocity,
and four extra rows (+2,-2,+3,-3):42outer tokens, hard1400-byte cap. Clients select
that WHOLE snapshot, never combine a newer C with an older D. Old C/numeric
interfaces remain. Extra-only and held-only changes participate in refresh even
when C is unchanged. Existing decimal/float32-finite codec validates EVERY numeric
outer/embedded component; wrong structure, invalid hold flag, junk/NaN/infinity/
overflow or an oversize extension rejects D, retaining legacy rows but no extras.
No truncation/partial-row guess and never a full999-save dump.

Pending non-rate-refused loads/steps use existing virtual-row replay (and can
still be corrected if the server refuses validation). Once answered, release uses
ACTUAL held speed from the same D snapshot, NOT the selected cursor. A C-only
settled hold or missing/unproven held state is BLIND; numeric-only legacy fallback
remains. Rate-refused pending ops do not retarget the hold. Queue-full/backstop,
missing-ring, unknown rows and already-free replay behavior remain.

No native engine/wire type, evidence/run/save format, authoritative load/release
semantics, threshold/quiet-period, raw capture, backend, Build or release change.
Beyond+-3 remains unknown unless an original current/neighbor/first/last covers it.

## Acting verification

Actual dedicated CPU-only QC VM, exact production helpers and explicit synthetic
stat/queue/rate/validation dependencies:
- Metadata31/0: production formatter/decoder, legacy C50, complete D42/cap,
  bidirectional2/3, wrapping/small lists, C/D ordering, extra-only AND held-only
  refresh, no-hold transition, stale list ack, malformed structure and same-shape
  junk/NaN/infinity/overflow/inner numeric/invalid flag refusal.
- Release29/0: full queued step/release/apply, known/unknown/refused/legacy/recovery,
  backstop/ring/full/free controls; production server step and release execute.
  A validation callback explicitly refuses/accepts (NOT full state-file IO):
  cursor advances while old hold persists, then acknowledged release matches
  actual server600 rather than cursor700. Accepted retarget/thaw also act.
- Relative24/0 remains byte-identical helper coverage (P1343), total84/0.

The17 added review checks expose12failures in the ORIGINAL67-check candidate:
metadata31/8 and release29/4 before correction, both0 after; compiler0warnings,
server exit0. Original43 baseline18failures and relative24 baseline7 are retained
historical controls, not added together across different baselines. Original
candidate/reviews/fixtures/failures retained; no regrading or warning waiver.

Both post-fix standard THREE-VM NoDeploy builds have0warnings. Both independent
rechecks closed prior runtime findings; their remaining stale shared D38 comment
was corrected to D42 in both profiles, with exact same-line comment equivalence.
Reader949checks passed on the byte-identical reader (reused, not redated). The final
mandatory primary RUNS sweep, including paired views, remains548files/351fault
results: equal to the actual predeployment baseline, NOT fault-free. The existing
permission-protected optional save fixture was not altered or treated as a pass.
This is helper/state evidence, not full packet/collision/PVS/feel or a historical
report's proven cause. No measured bandwidth/FPS claim.

## Delivered6Nov2026UTC

- BOTH Windows installs verified09:17:07: QW/CS DAT+LNO,8destinations total;
  current/prior-prev preimages retained, new .prev hashes verified, all19340
  non-target paths exact. No native/menu/config/data deployment.
- ALL12Pi lobbies activated09:33:10: paired QW+CS,12new actor epochs and mapped
  native/plugin identity verified,0skipped. All47924protected paths exact,
  native/menu/config/backend unchanged.10-second chat warning/grace preceded
  normal disconnect/restart; every original join capacity verified restored.
- All8recorder parts and183complete resume files captured and independently
  rehashed ON/OFFBOX before staging/restart; all bytes still exact after restart.
  No archive restoration, player-data cleanup or verifier downgrade.
- Cold native served-client/UI smoke completed10:28:42UTC after the owner freed
  RAM:66seconds quiet, minimum5212MiB before launch (4096-MiB gate unchanged).
  Existing pi_lobby_smoke.py used clean frozen c9151699assets and unchanged deployed
  native/plugins/menu; no local CS/cache. Fresh download366ab819.dat hashes EXACTLY
  to Pi CS01815ce0below; client exit0, completion marker, last board cols9/type14,
  no detected QC runtime errors. Screenshot inspected: readable HUD/scoreboard in
  no-zone/no-times empty-state, NOT populated rankings or textured-world acceptance.
  Own copied rig retired after preserving/hash-verifying unique proof; rig lock
  released. No rebuild/deploy/restart. Rapid-save release, packet ordering, native
  collision/PVS/feel and actual human acceptance remain unverified.

Runtime source lineage (public commits, not a rebuild after review):
- Windows published19b83fd8d5888ab4083d2e09a1d24ee90a4e1542, compiled
  38b75a6fa10bb892c529cbafed3e461ea9391f3b. Later changes are one same-line
  protocol comment and a published receipt-only merge; whole src tree equality
  across that merge verified. P1339 atlas work preserved, not downgraded.
- Pi component218721aaa436dd88d8c3f09663e990f91037ac20 on
  deploy/p1343-warp-relative, compiledfb57a3ebe783b48a4f597b322c0a00c9530c24ed;
  only the same-line protocol comment differs. Source-bound admission passed.
- Compiler SHA256c24ede65af01d6c7e20d5d1dbd2190a9295a38fb0e109843f75e52166da22f74.

Program SHA256:
| Profile | Program | SHA256 |
|---|---|---|
| Windows | qwprogs.dat | bd250d057f984eef3bdddb8867715799861be1621d42579189df8a7985bf4e7b |
| Windows | csprogs.dat | feccba214e0b27b2f837722550f6cc31d3a4fa97edd84ab78d06dbee0d3a811f |
| Pi | qwprogs.dat | e7b8a26bc0383c75e12256511c5f2759b28c77d8a4346353d5250c96ccc3046f |
| Pi | csprogs.dat | 01815ce013010293cd7f11c5797cb791d43bf04153573802919bbee34c5f9bf5 |

Small owner check requested, not confirmed: hold a save, step next/previous2or3
quickly and release; compare single-step/first/last recovery if convenient. Record
actual feedback in lextest.md. Do not damage/delete saves for a refusal test.
