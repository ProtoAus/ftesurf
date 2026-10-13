# P690 supported-Q1 cache preservation — bounded native controls

This is a tooling/evidence continuation, **not a renderer patch or deployment**.
Default `r_blendsort 1` stays unchanged. Source temporal-cache support is still
absent at delivered engine `a8e705787`; selecting cache1 on VBSP is not action.
See [p690blendplanes.md](p690blendplanes.md) for the product/source contract.

## Reproduce the offline controls

Requires Python 3.10+, NumPy and Pillow. Output paths must be fresh, owned scratch
paths following AGENTS.md; these tools never stage a game, start a process, build,
deploy, modify owner data, or create an implicit temporary worktree.

```sh
python -B tools/p690cache.py fixtures --output <owned-root>/fixtures
python -B tools/test_p690cache.py --output <owned-root>/grader-tests
python -B -O tools/test_p690cache.py --output <owned-root>/grader-tests-O
python -B tools/p690cache.py grade --evidence <retained-native-dir> --result <new-result.json>
```

`fixtures` emits two asset-free BSP29 maps and one shader. It refuses an existing
output directory. Do not install these into owner data. Both maps are deliberately
uncollidable: native capture needs explicit noclip, not just setpos. Opaque red
extends beyond nearer blue as a visible lost-geometry sentinel; blue must win
at the overlap. Alpha uses the original narrow red strip with red/blue alpha0.5.

`grade` requires complete schema1 `capture.json`, the exact three generated
fixture hashes, pinned seven-file P688/merged/diagnostic native input/staging
hashes, observed full runtime version, actual map identity, server body/aim/zero
velocity,96 RGB720x960 SHA-bound PNGs and diagnostic main-view postdraw samples.
Screenshot paths must stay inside the evidence directory. A manifest is a local
capture receipt, **not a signed attestation against a hostile evidence author**.
Raw logs/input/restoration receipts must remain alongside it for independent
review. Missing/malformed/modified evidence fails; result files are not overwritten.

The checker imposes exact fullframe repeats with **no HUD mask or tolerance**.
Every opaque image, both modes, every cache state and all four binaries must
match. Authored red/blue counts and centre-blue depth consequence must act.
Alpha is deliberately **not** required to match across cache paths: cached
index-only VBO batches are coarse and cannot enter per-face plane refinement.
Cache1 preserves P688; ordinary cache0 mode2 must visibly act and satisfy authored
red-over-blue versus blue-over-red centre values. Return0 must recover its own
initial image. Diagnostic/merged pixels must match before binding actors to
production visuals. Legacy mode1 A/A-return instability gets a distinct
`UNSTABLE_LEGACY_NOT_ACCEPTED` result; the CLI exits nonzero for an incomplete
alpha matrix even if opaque independently passes.

`test_p690cache.py` uses **synthetic** pictures/receipts solely to falsify the
checker. Seven test methods exercise positive, deterministic fixture/no-overwrite,
legacy-incomplete and33 acted rejection controls: frozen/mixed/wrong-world/
wrong-view actors, ineffective settings, no runtime/version or wrong/staged
binary, missing/duplicate rows, unrestored fixtures, changed/path-escaping PNGs,
empty/incorrect opaque depth/lost geometry, failed return, diagnostic mismatch,
unstable repeats and a sorter that never acts. CLI controls also exercise
successful/legacy-incomplete/refused/malformed evidence, no-overwrite and report
creation/absence under `-O`. Normal and `-O` both pass; runtime acceptance gates
use explicit errors, not Python assertions.

## Retained native matrix — 2026-10-13

Owned root: `C:/FTESurf-worktrees/mapvisual-01a13061/`.
Evidence: `artifacts/supported-cache-20261013/native-04/`.
Exact retained driver: `artifacts/supported-cache-20261013/native_capture.py`.
It is task-root-specific and intentionally not a general install manager.
It stages only an already-owned isolated `subject/`, guards live processes and
port27620, backs up all eight native files, exclusively installs absent-before
fixtures, uses conbridge's config/data guards, and refuses restoration if an
owned stop fails. It never launches or kills an owner/peer process. Input hash
pins are in `p690cache.py`; those are retained output bytes, not a claim of a new
clean build. No compiler, plugin, QC or product rebuild was part of this matrix.

Four arms: clean P688 `73322dff5`, delivered integrated production `a8e705787`,
its diagnostic-only client, then the **same P688 native bundle** again. The
probe is the previously retained post-BE_DrawWorld client with full stamp
`git-690-a8e705787fad1b60661da5e8dd43c9138cc69b1b-mv11-cacheprobe` and SHA-256
`e6c8b0fbf6fbfc54defc9298169c0f878603ca2adfe538e2547bd678cb3344bb`.
Only that client's bytes differ from its production bundle; it is not installed.

Two maps × two sorting modes × cache0/cache1/return0 × two repeats × four arms:
**96 frames**. Measured cvars/prediction/input/HUD are explicit in the retained
driver/raw replies. Body/aim/velocity are checked before each screenshot.
Diagnostic rendered eye is consistently `(0.062,0.062,64.062)`, angles `(0,0,0)`
with the normal FTESurf viewheight; assumed vanilla Quake eye22 was rejected.

Results:

- All48 repeat pairs exactly match. Every one of48 opaque frames is identical
  across modes, builds and cache phases. The authored visible red sentinel has
  **15,276 pixels**, blue **300,736**; overlap centre is `(0,0,255)`. This proves
  a visible depth consequence, not a numerical depth-buffer readback.
- Diagnostic settled cache1 intervals add **470–476 cached draws**, ordinary0.
  Cache0/return intervals add **469–480 ordinary draws**, cached0. Actual world
  identity is `maps/mv12_cache_{opaque,alpha}.bsp`, fromgame0. Counters are after
  real main-view draws, not request/cvar readbacks.
- Diagnostic and delivered merged images match in every phase/mode/map. This
  empirical binding is distinct from production counter instrumentation: the
  production executable has no such postdraw counters.
- Mode1 P688/merged/P688-return images match per cache phase; no legacy instability
  in this matrix. Cached alpha mode2 also preserves P688 exactly. Ordinary mode2
  ACTS in **20,604 pixels**: centre P688 `(127,0,64)`, merged `(64,0,127)`.
  Return0 recovers each arm's initial image. Coarse cached behaviour remains
  separately attributed, not falsely required to equal ordinary alpha ordering.
- Every bridge-owned runtime stops rc0. All eight subject native originals are
  hash-restored, created fixtures/directories restored absent and protected
  subject config/progs/player files unchanged by membership/size/hash/mtime.
  Both canonical installed client hashes are unchanged. No shared process,
  source index, QC data, defaults, fleet, release or installed native swap.

`NATIVE_RESULTS_FINAL.json` is the strict regrade, not a new native run. Capture
receipt SHA-256: `04b251cd9e16b0a147f4b7483f021c476b35486f7bb3103f9f1a0c1a12b674a6`.
Restoration receipt: `000c9b40f4c355745c822e2713958c3f56035bfd9a87269ed25defc85f0caa8b`.
Final strict result SHA-256:
`94208c8d2af1fbf674225e005dec47bf1ba2cb3be71207d990290bd538cf8dff`.
Independent bounded review reconciles receipts, actor intervals and pixel/hash
placements, OK with notes: local receipt trust, no independent production
postdraw counters and no broader promotion claim. The added optimized CLI
controls also pass. Recorder regression306 checks/0 failures;273 canonical
recordings/91 sidecars retain their existing168/5 faults, zero new faults and
unchanged corpus bytes/metadata. Raw private paths/fault text were not exported.

## Failed controls retained, not hidden

`FAILED_SETUP.md` keeps failed file-location/setup assumptions and three excluded
native directories. `native/` omitted noclip and the body fell before any accepted
PNG. `native-02/` rejected a proposed stale-MarkLeaves actor. `native-03/` completed
96 stable pictures but the intended opaque red sentinel was entirely occluded;
that generator does not prove loss detection. Corrected `fixtures-02/` extends
red's exposed edge, leaves alpha bytes unchanged, and is the only accepted opaque
fixture. First generator/grader and third driver are preserved for attribution.
No pixel mask or relaxed threshold converted a failed fixture into a pass.

**Stale MarkLeaves age is not proof of temporal cache use.** In delivered
`common/q1bsp.c:2227–2231`, Q1BSP_MarkLeaves reuses cvis at a fixed same-cluster
camera before reaching q1bsp_marktime at2275. Real cache0 therefore reported
“MarkLeaves last ran14.1 seconds ago” while saying wanted0/inuse0. `r_waterinfo`
can print a false causal explanation (“scene cache is returning before it”).
Here it supplies only Q1 world/effective-setting readback. The postdraw actors
supply reachability. Do not call this pre-existing diagnostic on Source (its
separate crash remains), and do not credit older stale-age-only cache evidence
as direct draw-path proof. Follow-up is in BACKLOG.md.

## Limits

Two authored supported-Q1 maps, one fixed camera and one Windows/OpenGL GPU.
This newly binds exact delivered opaque/coarse-cache preservation; it does not
close representative Q1/Q3/HL coverage, arbitrary model/sprite/weapon/rotated
brush overlaps, portal/reflection captures, hardware tessellation, custom
external projections, broad all-map GPU coverage or ordinary frame-time gates.
It implements no Source temporal cache and makes no default2 promotion claim.
