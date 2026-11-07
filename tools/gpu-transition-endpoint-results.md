# Boreas transition endpoint experiment — rejected

7 Nov 2026. This is a negative experiment, NOT a product patch or a speedup.
The experimental shader was never installed in either Windows install.

## Question and acting control

The sampled Boreas terrain uses `vmt/transition` with SEAMLESS, BLENDMOD and
BUMP2. The shader samples both base layers and, when active, both normal layers.
Could exact shaped blend endpoints 0/1 avoid fetching the unused layer?

The default-off prototype used explicit texture gradients before the varying
endpoint branch. Unsupported renderers and MASKLT cutouts retained the original
path. All blend, lighting, reflection and fog math remained in place for normal
rendering. A separate temporary heatmap was attribution instrumentation ONLY;
it bypassed normal shading/fog and was never a shipping client capability.

The native heatmap positively acted on the terrain. At the fixed 1920x1200 pose,
498,616 pixels were pure green (second layer only), 5,559 pure blue (first layer
only), and 652,721 pure red (interior blend). These are screen-space counts, NOT
an exact fragment-opportunity percentage: supersampling, overlays and other
materials also contribute. This was not a dead-branch benchmark.

## Frozen comparison

- Original engine: `76876c82061be6a66840d61f4b6f16c239ebd31b`, annotated
  `patch-1358`, with the unmodified original HL2 shader DLL.
- Both cohorts used the SAME full-build native client, SHA256
  `36e22f63f8030e0c6cc76d6478d37e419c9a44be6de87da0e82d8abcb62b488e`.
  Only the shader-containing HL2 DLL differed. Live prototype value 0 was NOT
  substituted for the original shader: it has an extra branch/register footprint.
- Existing cached Boreas replay, seek 0.25, speed 1, two 12-second windows per
  native application; route/assets/programs and normal prop lighting prewarmed.
- Order: original A, prototype A, prototype B, original B. Four measured windows
  per cohort, 48 seconds each. No whole-map, other-map or first-load claim.
- 1920x1200, `r_renderscale 2`, 64 sprite sky rays, `hl2_water 0`, unlimited FPS
  in measured windows. No render-scale, anisotropy, visibility or quality reduction.
  QC profiling and in-window file logging were off; shared native admission
  retained its 4096 MiB / 60-second quiet guard. No competing game was present.

## Native results

FPS values are the native frame-time dump's reciprocal tail means, not a
percentile-FPS approximation. Each row is a separate 12-second capture.

| Cohort | Window | Average FPS | 1% low FPS | 0.1% low FPS |
|---|---|---:|---:|---:|
| Original A | first | 452 | 269 | 232 |
| Original A | repeat | 450 | 248 | 177 |
| Prototype A | first | 359 | 232 | 204 |
| Prototype A | repeat | 358 | 229 | 197 |
| Prototype B | first | 358 | 228 | 204 |
| Prototype B | repeat | 358 | 230 | 199 |
| Original B | first | 452 | 269 | 222 |
| Original B | repeat | 448 | 265 | 218 |

The prototype loses about 20–21% average throughput and has worse 1% lows in
all these comparisons. The 0.1% tails overlap; do not claim a consistent change
from those few worst frames. Returning to the original recovers throughput,
including after the prototype applications, so the regression survives reversal.

End-of-window budget snapshots, NOT whole-clip averages:

| GPU group | Original | Prototype |
|---|---:|---:|
| World | 0.75–0.76 ms | 1.56–1.58 ms |
| 3D sky | 0.20–0.22 ms | 0.23–0.24 ms |
| Transparent/effects | 1.85–1.87 ms | 1.65–1.67 ms |

The world pass becomes substantially more expensive. Extra gradient/control-flow
and shader-resource costs are not free, even where a source-level texture fetch
can be skipped. Register pressure, divergence, texture/LOD behavior and driver
instruction selection were NOT individually profiled; do not invent their shares.
The original's transparent/effects cost is also substantial at this route position,
but this bucket alone does not identify foliage, glass, sprites or another cause.

## Image check and limits

The successful original B and both prototype captures have the same paused
replay time 0.250 and native rendered pose `12745 -11672 14614 58 71 0`.

- Static terrain ROI x1300..1899, y600..899: 180,000 pixels, 99.96% exactly equal;
  every remaining difference is at most one 8-bit channel level.
- Upper-left terrain ROI x0..499, y120..229: 55,000 pixels, 99.989% exactly equal;
  remaining differences at most one channel level.
- Prototype A and B are exactly equal in both static ROIs.
- Full-frame HUD/animated differences are not a material-quality verdict.

The images were inspected. These samples are near-matching, NOT bit-identical,
whole-route shimmer/LOD acceptance or owner manual approval. No further visual
qualification was needed to reject the measured performance regression.

## Preserved reader failure

Original A's native application completed both measured windows, but the old
reader then failed: it expected an invented `r_frametime:` header and demanded
half a second of progress from only three initial frame traces. Native output
actually says `frametime over 12.0 s, ... frames`.

Both original raw files were retained before any subsequent native launch. Their
12-second timing data are accepted narrowly: 5,418/5,399 real frames, no excluded
focus-idle intervals, positive initial replay clocks and eight distinct actual
render-camera slow-frame positions in each. The failed application receipt was
NOT turned into a complete pipeline/image pass. No direct end clock or final
screenshot was captured for original A.

The existing collector was corrected to the real producer format. It now captures
three paused end traces AFTER the metric dumps, before condump, checks the end
clock against seek+duration, and requires actual rendered camera motion. The other
six timing windows and final images passed those checks. The fully successful
original B versus both prototype applications independently confirms the loss.

## Disposition

**Reject the candidate.** A globally enabled optimization that regresses an acting
required map is not releasable; a favorable result on another map would not repair
that failure. No Demise/Garden gain or universal shader conclusion is claimed.

The uniquely retained experimental source, generated header, patch, native DLLs,
raw logs and images remain in the owned workstream archive. Only the verified
owned shader/generated-header edits were restored to inspected engine 1358; its
owned build output and runtime subject DLL were also returned to the original.
Canonical/peer source and installed game files were not restored or overwritten.
No product patch, engine tag, Build, release, VM deployment or Pi restart was made.

Further GPU work needs a new material-qualified hypothesis, with particular
attention to actual transparent/effects attribution rather than assuming fewer
GLSL texture calls must be faster. See BACKLOG.md for the remaining falsifier.
