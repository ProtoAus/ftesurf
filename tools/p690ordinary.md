# P690 ordinary stationary cadence/service gate — bounded native pass

**One fixed-station ordinary-path gate passes; no broad performance or default2
promotion.** The quiet capture below passes unchanged exact-pixel and20% timing
limits. Earlier failed captures remain excluded. The supported
[Q1 cache-preservation gate](p690cache.md) remains complete and separate.

## Detector and reproduction

`p690ordinary.py` reads a capture directory; it never launches games, stages
binaries, writes installs, changes defaults or deploys. Python3.10+, Pillow and
NumPy are required. Bundle pins and postdraw parsing reuse `p690cache.py`.

```text
python -B tools/test_p690ordinary.py --output <fresh-owned-root>/detector-tests
python -B -O tools/test_p690ordinary.py --output <fresh-owned-root>/detector-tests-O
python -B tools/p690ordinary.py <owned-capture-directory>
```

The test output directory must be fresh and operator-owned. Eleven test methods
produce74 acted rejection receipts and6 synthetic positive/CLI receipts, passing
under normal and optimized Python. Synthetic receipts are NOT native performance
proof. The CLI exits1 on incomplete/failed evidence, including under Python `-O`.
The native driver is a retained, one-station operator script, not a public launcher.

The frozen gate requires:
- Exact retained P688 and delivered merged P689+P690 client/server/plugin pins,
  diagnostic draw-only probe, and P688-return. Probe timing never contributes.
- OpenGL960x720; cache0; modes1/2; fixed Kitsune body/eye/aim and zero velocity;
  explicit FOV/render-scale/vsync/finish/frame-cap/pacing/material/PVS readbacks.
  Quiet schema2 additionally requires actual registered HUD/input/prediction/HDR
  settings and unique BEGIN/END-or-footer primary records with hash-bound successful
  completion waits inside conservative send/read bounds. The wait's timestamped
  completion line must exactly match its primary; witness paths cannot be reused.
  Schema1 remains readable for historical evidence; it cannot satisfy the stronger
  schema2 protocol.
  `vid_wait` is an alias: the actual readback is **vid_vsync**, not vid_wait.
- Six independent groups per production arm/mode/metric. Cadence has a complete
  128-swap ring, with conservative command bounds proving successive rings do
  not overlap. Cost has one complete100-frame report, current r_speeds2 (never3),
  positive world/transparent draw quantities, and a changed closed-block numeric
  fingerprint. RSpeedShow resets accumulated values after each100-frame sample;
  distinct chronological snapshots therefore cannot reuse the same block.
- Exact full-frame before/after PNG repeat; default parity; diagnostic/production
  binding; P688 pixel return; mode2 sorter acting in >1000 pixels. **No mask.**
- Merged cadence and observer-adjusted refresh medians <=1.20 times BOTH controls,
  with P688 initial/return within20%, separately in each mode. Every group/range
  is reported; no outlier trimming or population-level statistical inference.
- Native slowdown control sys_framepacing4/cap20: >3x cadence AND refresh cost,
  >20000us pacing bucket, and explicit mode2/cap100/pacing2 cadence/pixel return.
  Control timings are excluded from ordinary acceptance. Stops must be rc0;
  original native/config/player/content/install inventories must be restored.

Path/hash/stamp/state/actor/image/missing-ring/stale-block/nonfinite/draw/regression/
return/restoration failures have acted offline rejection controls. Receipt hashes
bind files, not a cryptographically attested execution: this remains local trusted
capture evidence, with empirical probe/production image binding rather than
production postdraw counters.

## Production sampler scope (both pinned engines)

A diff between P68873322dff and mergeda8e705787 is empty for the six sampler files
below. No diagnostic build or timing instrumentation was added for this lane.

- `client/cl_screen.c:36–90,98–224`: r_speeds_dump requests a one-shot report;
  RSpeedShow holds the previous **100 rendered-frame average**, not a fresh
  single-frame measurement. Draw quantities exclude its own table, but timing
  includes the table's work. Published adjusted service cost subtracts the
  `r_speeds overhead` bucket from `Total refresh`; this does not eliminate all
  observer effects or reveal the cost of an otherwise observer-free execution.
- `client/render.h:943–970`: RSpeedEnd uses Sys_DoubleTime and microseconds.
  r_speeds>=3 injects GPU synchronisation around buckets. Accepted samples require2.
- `client/cl_main.c:7535–7612,7755–7765`: mode2 frame-cap waits return before
  SCR_UpdateScreen's Total refresh bracket. Input/protocol work outside that
  bracket and paced idle are NOT included. `REAL frame (refresh+server)` is also
  not the whole host frame; cadence must be measured separately.
- `gl/gl_screen.c:258–289,324–350`: GPU drain/present-grid holds occur only in
  mode4; accepted mode2 has neither. RecordPresent follows VID_SwapBuffers. The
  positive mode4/cap20 arm deliberately moves a large wait into Total refresh.
- `client/sys_win.c:2205–2232,2289–2339`: the128-entry present-return interval ring
  runs in every mode and resets on mode changes. Its average/range/jitter are
  sampled independently from r_speeds. This is **Windows WGL swap-return cadence**,
  not GPU completion, photons/display latency or proof of VRR behavior.
- `client/renderer.c:91–95`: vid_vsync's historical alias is vid_wait.

The cap100 station has headroom; near10ms cadence alone can hide a service-cost
regression. Clocked service buckets can include driver blocking, scheduler
preemption and other observer effects; they are not exclusive CPU or GPU counters.
No moving-camera, frame-tail, fullscreen/vsync, representative/all-map or default2
performance claim is made.

## Quiet native continuation — 2026-10-13, bounded PASS

Owned evidence: `C:/FTESurf-worktrees/mapvisual-01a13061/artifacts/ordinary-quiet-20261013/`.
Protocol frozen before launch in PREDICTIONS.md. Hardware remains RTX2080SUPER,
NVIDIA591.86, Windows GL4.6. No engine/QC/binary/default/deployment changes.

- Source controls: `src/client/cl_hud.qc:728–757` caches hud_timer/mapinfo;
  `cl_mouse.qc:48,333–354` registers hud_mouse and draws the lower-right mouse-pad
  box previously mislabelled a minimap. Actual HUD controls are disabled/read back,
  alongside input0 and prior exact-station prediction settings. HDR is explicitly0.
  Several settings changed together: no causal claim about earlier scene drift.
- Short diagnostic probe: HUD on/off changes16,215 pixels; on/off/on return exact.
  Both HUD-off full-frame repeats have0 changed pixels across two complete cost
  dumps and the r_speeds0/2/0 observer round trip. Mainview ordinary counters
  advance314/315 draws, cached0, exact eye/aim. This is not timing acceptance.
- Full capture ran BLOCKING and serialized: diagnostic/P688/merged/P688-return;
  no parent/subagent tests/builds/corpus/hash/image sweeps overlapped timing.
  Owner/peer processes were not stopped; this is not OS-wide workload isolation.
  All78 primary samples include unique current-send tickets and complete reports,
  with78 hashed completion waits; no archive reconstruction. Six independent
  groups per ordinary arm/mode/metric plus native slowdown/return controls.
- All17 PNGs pass exact full-frame repeats, diagnostic/production binding,
  default1 parity, P688 pixel return and timing-control pixel return. Mode2
  acts at12,065 changed pixels. No masks, trims or widened thresholds.

Median observer-adjusted refresh service (us; six groups each):

| Mode | P688 initial | Merged | P688 return | Merged / initial | Merged / return | Return / initial |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 753.410 | 730.220 | 692.195 | 0.96922 | 1.05493 | 0.91875 |
| 2 | 785.760 | 762.495 | 677.520 | 0.97039 | 1.12542 | 0.86225 |

All four cadence/service comparisons pass the unchanged1.20 subject limit against
BOTH controls and return[.80,1.20]. P688-return service differs by-8.13%/-13.78%:
controls are within the guard, not identical, and the result is NOT a speedup claim.
Ordinary cadence medians are9.9995–10.0015ms; raw group values/ranges/jitter and
observer buckets remain in native-grade-final.json. The cap can hide regressions.

The slowdown ACTS: cadence4.99975x, adjusted refresh65.34284x, paced bucket
48.947–48.987ms/frame; cadence return1.00005x and pixel return exact. Slow groups do
not contribute to ordinary acceptance. Reader CLI passes under normal and `-O`.
All eight owned processes quitrc0; subject native8/config/data/content inventories
hash-restored, installed client hashes unchanged. Evidence/source/predictions/raw
logs/PNGs and original hashes retained; only explicitly verified duplicate backups
may retire. A fresh read-only review and regression/closure results are recorded
in the continuation checkpoint, separately from commit/push state.

## Additional-map eligibility follow-up

The published quiet result above remains Kitsune-only. A separate diagnostic
probe of existing Tensor2 and Demise stations found full-frame scene changes
with fixed rendered cameras and advancing uncached draws. Neither qualifies for
this EXACT stationary protocol; no production P688/merged/P688-return timing
was run there. The first Demise attempt is invalid wrong-camera evidence and
remains excluded; its separately preregistered settled-camera retry is valid
but ineligible. See [p690stationprobe.md](p690stationprobe.md) for native pixel
counts, fixed-state/action controls, and the eligibility-only CLI contract.
This does not identify a renderer defect or expand performance/default2 claims.

## Earlier native experiment — 2026-10-13, EXCLUDED

Owned evidence: `C:/FTESurf-worktrees/mapvisual-01a13061/artifacts/ordinary-cost-20261013/`.
No binaries were built or deployed. Installed clients/defaults and peer source/
index/processes were untouched. Hardware: RTX2080SUPER, NVIDIA591.86, Windows GL4.6.

- native-01 completed78 timed groups/17 PNGs and restored, but used implicit
  renderer selection and lacked current per-sample sampler readbacks; EXCLUDED.
- native-02 explicitly selected GL and collected78 groups/17 PNGs, with actual
  mainview postdraw actors and per-sample r_speeds/pacing readbacks. **Strict CLI
  rejects `unstable station repeat` under normal and optimized Python.** Six of
  eight before/after arm/mode pairs differ by1016–3900 full-frame pixels; probe1
  and merged2 happen to repeat exactly. No relaxation converted these into passes.
- The setup also invoked guessed HUD names: timer/mapinfo/mouse-pad remained visible.
  Inspect the actual registered QC HUD controls before a new capture. The changed
  pixels extend into scene geometry, so the HUD alone is NOT established as the
  cause. No product renderer bug or repair follows from this failed control.
- Thirty-four of38 cost replies end before the dump footer: a0.4second console
  read does not prove a complete sampler record. Complete records exist in the
  date-unique retained raw client logs. Diagnostic recovery checks unique exact
  archived headers and byte-identical captured prefixes, retains source/recovered
  hashes and NEVER rewrites capture.json or the primary replies.
- Archive-bound **EXCLUDED diagnostics**: ordinary cadence medians ~10.000–10.010ms.
  Adjusted refresh medians (P688 / merged / P688-return), in us:
  mode1 **723.415 / 722.995 / 995.190**; mode2 **765.670 / 841.635 / 807.785**.
  Mode1 P688 return drifts **37.57%**, exceeding the pre-registered20% control.
  Thus even repairing the PNG/setup/completeness problem cannot certify this run.
- The excluded native slowdown nevertheless ACTS: cadence5.00x and refresh59.11x;
  pacing48.41–48.79ms/frame. Cadence return is1.00095x. This verifies the timing
  channel's responsiveness, not performance acceptance or stable background load.
  Parent detector/corpus work overlapped sampling; a next attempt must serialize
  it and prove quiet A/B/A controls. Do not discard the drift or trim samples.
- All eight owned bridge runtime pairs across both attempts stopped rc0. Eight
  subject native originals per capture and protected fixtures were hash-restored;
  both installed client hashes stayed unchanged. Unique failed/raw/PNG/prediction/
  recovery evidence is retained. Only verified duplicate staging/log copies retire.
- Recorder regression306 checks/0 failures. Canonical273 recordings/91 sidecars
  retain their existing168/5 faulted reports (176 fault messages); reader and
  corpus byte digests match before/after, **zero new faults**. An extra save-tree
  sweep hit a protected fixture and was retained as a setup failure; no save-tree
  repair or clean sweep is claimed, and raw private paths/fault text are not exported.

A later [sprite/world-alpha fixture](p690spritefixture.md) adds one bounded native
production overlap-preservation result without a timing matrix. It does not expand
this fixed-station cost gate or certify arbitrary sprite ordering.

**Remaining falsifiers:** representative additional-map/moving-camera ordinary
cost and tails, native arbitrary model/sprite/weapon/rotated-brush overlaps,
portal/reflection captures, and supported-map cached opaque preservation. The
single quiet station does not close these or promote default2. Keep the failed
matrix excluded and the broader promotion gate open.
