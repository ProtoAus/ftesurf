# P936 — 64-pixel Steam portraits

## Scope / preregistered predictions

Inspected base: QC c5d260445c11d9bc9b830b48d72022020cb42331.
Fetched both repositories on 22 Oct 2026; maximum published patch 934,
maximum untracked p-number 935. Claim 936 only.

- Preserve the default 32x32 avatar endpoint and existing JPEG/text assets.
  Add explicit `size=64`, derived from the already-fetched 64px Steam JPEG:
  twice the linear source resolution, four times the source pixels, not an
  upscale of the 32px game copy. No extra Steam requests or data migration.
- New game/menu readers request 64px, validate exact headers/length/hex, and
  use separate 64px disk/texture namespaces. Old clients/caches stay intact.
- Bounds: only sizes 32/64, existing 1024px source-image limit, 64KiB JPEG
  read limit, at most 64 cached 64px responses. No recorder, evidence, physics,
  authentication, visibility, rate-budget or native ABI changes.
- Falsifiers: the unchanged endpoint remains 32px; an explicit 64px request
  returns 64 rows; a lossless 1px source pattern survives at 64px but not
  32px; malformed/oversized/missing pictures and invalid sizes fail closed;
  conditional responses differ between sizes; existing bans/collision guards
  still apply. The old core must fail the new 64px expectation.
- Reuse `surfd/test_ranked.py` and `tools/p640pics.py`: actual native uploaded
  texture dimensions and screenshot quadrants, including renderer restart.
  A no-picture control must actually have no image/ask. These checks do not
  establish subjective portrait quality or performance; owner acceptance is
  recorded separately in lextest.md.

## Verified implementation (not yet deployed)

- Mainline final NoDeploy build `eb24ef8723df4775bf4f3b7b3ce73454`:
  all three VMs, zero warnings. Native engine/pin/tag unchanged.
- `surfd/test_ranked.py`: all passed, including SIX new P936 checks; profile
  12-hex aliases produce the same picture as the 8-hex mark and retain ban and
  linked-mode gates. The default 32px endpoint still rejects the alias.
- `p640pics.py --picture-size 64 --menu-picture`: real game and menu bodies,
  native 64x64 textures and both quadrant screenshots pass. Game texture/ink
  survive renderer restart via an acted reload. Screenshots were inspected.
- Prior P934 clean-build 32px control `d19eb145acec45919649697ab966de6d`
  ACTS and draws both screenshots, but fails exactly the three 64px transport/
  texture expectations. The visible no-picture control passes with no avatar
  request, no texture and no quadrant ink.
- Retained evidence: this task root's `artifacts/p936-{ranked-final,menu,
  control32,none}.log`, screenshots and per-rig stopped-process metadata.
  No real account, subjective appearance, frame-time or network-cost claim.

## Harness failures retained

Implemented, NOT deployed. Initial NoDeploy QC build: all three programs,
zero warnings. `surfd/test_ranked.py`: all passed, including the five new
P936 controls (64px detail, legacy API, conditional identities, bounds and
cache invalidation), plus ban/collision/linked-mode controls for both sizes.

Two native-harness infrastructure failures are preserved, not feature passes:
missing output parent before any fixture, then the old helper's hardcoded
online tier 4 was correctly refused by current tier 8. Stopped that approach,
compared the working P933 isolated consent fixture and current source, and
fixed the caller's mkdir/current-tier fixture plus builtin-menu closure. No
product consent guard was changed; the new synthetic file is ONLY in a fresh
localhost test profile, not the owner's installation. Native proof remains
initially pending. The next arm was stopped by the tool timeout: its WOS-only
source filter hid the imported rows although a 64px warm reply ACTED. Inspected
the screenshot/current source, set the measured source explicitly to all, and
used current warm-disk counter semantics. Both registered processes were absent;
only exact owned junctions were unlinked after target-identity verification.
Subsequent game/menu, 32px and no-picture arms above completed normally. No
product consent/source guard was weakened, and no clipboard/physical input was
used. The failed/timeout arms are not counted as feature passes.

## Delivery

Pending: inspect/commit/push source; build compatible recorder-preserving QC and
backend variants; qualify the immutable backend source/runtime through the
existing guarded transaction; promote backend first, then both Windows installs
and all available empty lobbies; verify hashes and a fresh live client. Do not
ship mainline producer/reader changes to the older fleet.
