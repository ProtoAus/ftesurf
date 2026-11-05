# P1311: Boreas/Demise shader warm coverage and frame-time investigation

## Goal and implemented change

Owner's i9-9900K / RTX 2080 SUPER / 16 GiB machine, using cached public main
replays of surf_boreas (39.540 s) and surf_demise (37.140 s). Improve slow frames
without silently reducing rendering quality or changing saved settings.

Add exactly three observed successful lazy-compile records to
`ftesurf/glsl/warmseed.txt`: Boreas water and refract permutations, and Demise's
animated permutation. No native code, settings, quality, movement, evidence,
QC Build, engine pin/tag or public release change. Existing committed weather
seed records are preserved; this patch does not enable or deploy weather code.

## Predictions and controls

- Identical second traversal distinguishes repeatable scene cost from first-use
  work. Each route must open, advance, stop and show the actual map.
- A new learned record is positive evidence of an unseeded successful lazy
  compile. Original fixtures learned two Boreas records and one Demise record.
- Expanded seed, no per-PC warm file, two traversals per map: no additional
  records learned. Screenshots inspected after the timed sections.
- IMPORTANT: no new learned file does NOT prove zero runtime compiles. The
  loader already knows seeded names, so a known permutation deferred by its
  two-second budget, or a program created after its sweep, need not dirty the
  learned list. This is coverage, not an all-shaders-ready guarantee.
- Native seed header/bit layout, complete newline-terminated ASCII records,
  byte/entry bounds, dedup, exact three-record delta and three omission controls
  pass. The tested subject differs from final source only by the five already
  committed weather records, unused on these routes.
- Clean `src/build.ps1 -NoDeploy -Jobs 2` with the qualified c24ede65 compiler:
  all three VMs compile, ZERO warnings. None of these progs is deployed here.

## Measured results and limits

These are the engine's rendered-frame timings, including replay opening and a
short tail after playback, NOT PresentMon measurements or a cold-driver-cache
performance claim. Logging, screenshots, clipboard and condump writes were
outside timed sections. No driver cache purge or shader-source salting.

Expanded-seed fixtures, native source `0591e841f`, current quality:

| Map / traversal | Frames | Average fps | 1% low | 0.1% low | Worst frame |
| --- | ---: | ---: | ---: | ---: | ---: |
| Boreas first | 20,818 | 465 | 201 | 125 | 39.04 ms |
| Boreas repeat | 20,550 | 458 | 210 | 181 | 6.74 ms |
| Demise first | 14,591 | 360 | 198 | 137 | 10.33 ms |
| Demise repeat | 14,502 | 357 | 205 | 151 | 10.29 ms |

Original Boreas source was `7ae5d53b2`; a peer native deployment occurred before
Demise preparation. Later fixtures explicitly pin their executable, HL2 plugin
and content snapshot. Do NOT grade old/new seed performance by crossing these
native cohorts. Baseline Boreas had the same first-use signature: 40.33 ms first,
7.44 ms repeat. Expanded coverage did not cure that first-use graphics hitch.
Its exact cause remains unresolved; capture allocation/draw are candidates,
not a measured diagnosis.

Owner's archived fullscreen/auto-resolution settings override the launch's
windowed 1920x1080 request: screenshot output is actually 1920x1200. All main
arms use `r_renderscale 2`, uncapped fps, idle cap disabled, capture rate 60,
capture half-rate off and shader warm enabled. A Demise scalar1 diagnostic gave
426 average / 248 1% / 184 0.1%, versus scalar2's preceding 352/184/112, but the
scalar2 return drifted to 318/147/102. This is a quality-changing diagnostic with
time drift, not a proven free optimization or a setting applied to the owner.

## Remaining native investigation and actual blocker

The local PROBE ONLY diff times lazy compiles and splits reflection/refraction
setup, clear, recursive draw and restoration. It is NOT deployed or qualified.
The first isolated build found the canonical static dependency cache empty;
the system fallback lacked opus/speex headers. Both failed logs are preserved.
A bounded comparison with the last working pacing cache plus correct UCRT PATH
passes the exact font/opus/speex header preflight. A full rebuilt probe/run then
remained blocked by the unchanged >=4000 MiB available-memory / 60 seconds quiet
rig gate. Waiters held no rig lock; no owner/peer processes were stopped.

Task evidence and owned probe patch:
`C:/FTESurf-worktrees/lows-20261104T2339Z-01a1a8e6/artifacts/`.
Existing replay arm/reader/rig guard were reused; no new benchmark framework.
Private local fixture identities/logs are NOT public export inputs.

## Delivery

Implemented and pushed: mod feature `a326b27c`, integrated without losing the
published P1310 native provenance at `5866339a`; engine journal `d9c0a54ba`.

Installed **only** the committed seed from `5866339a` at
2026-11-05T00:43:51Z into BOTH:
- `C:/FTESurf/ftesurf/glsl/warmseed.txt`
- `C:/FTEQuake/ftesurf/glsl/warmseed.txt`

Both SHA256:
`eeaa4a9b368fd96b7940d98e7f04c887fdc540066b22aa527bbd8d26e387529f`.
Both predecessors were the exact already-published P1309 seed, SHA256
`16035db3e310e61239545306bba9795d30ff03fb3191e90b0e6aaf87510531a3`;
all its weather records remain intact. Exact rollback copies and UTC receipt are
under task `artifacts/seed-preimages/` and `artifacts/seed-delivery.json`.
Fourteen actual executable/plugin/progs/config files hashed unchanged across
the 0.13-second file transaction. The owned rig lock was released immediately.

Destination bytes are verified; isolated route behavior was verified as above.
A fresh actual-install client restart/behavior check remains pending headroom
or owner confirmation. The loader reads its seed once per process, so restart
the client when convenient; a map change in an already-running client need not
reread the file. No process was killed/restarted, and no engine, progs, settings,
backend, lobby or release files were deployed. Native probe remains separate
and must not be shipped. The larger first-use hitch remains open, not fixed.
