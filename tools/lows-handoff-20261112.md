# Handoff: 0.1%-low hunt (lows2), 12 Nov 2026 -- from ftesurf-18 (Claude Code) to the SOL bot

Lex's ask (11 Nov): "find the worst offenders of 0.1% lows and fix them, to ensure the fps is completely as flat as
possible", then "fix the slowdowns and stutters in the maps we already have", "continue on the fixes, or do the survey
if nothing to do". Task root: `C:\FTESurf-worktrees\lows2-20261107-opus` (engine worktree `engine\`, FTESurf worktree
`qc\`, scripts `artifacts\`, rig game dir `runtime\game`). Earlier report: tools/p1481-survey3.md. Read CLAUDE.md,
AGENTS.md and AGENT_NOTES.md first; the rules there (review, measure every fix, commit-review-fix) all applied here.

## Delivered (all live: 12 lobbies + both Windows installs unless noted)

| Patch | What | Measured |
|---|---|---|
| P1488 | engine gettime(2) + QC 1 ms/frame trace budget for glare + sky test | fairy warm 0.1% 86 -> 125 |
| P1489 | CSQC map loaders run in WorldLoaded, behind the loading screen | fairy post-spawn frame 547 -> 108 ms (profiled) |
| P1490 | engine: r_blendsort 2 memo for uncertifiable failing sorts (installs only) | paused fairy spot 4.34 -> 3.80 ms |
| P1497 | QC: sprite/beam sky test backs off while a verdict holds (vbsp_sprite_skyhold 128) | fairy CSQC -0.22 ms; ~30% staler in-view verdicts (chosen) |
| P1499 | QC: mouse pad fast path | 0 px diff, CSQC -0.05 ms |
| P1501 | engine+hl2 plugin: static props load behind the loading screen (installs) | fairy late compiles 4 -> 0, orgrimmar 2 -> 0 |
| P1504 | QC: glare asks the budget every 16 visits and before corner rays | glare past 1.2 ms 2% -> 1% of frames |

Live now (12 Nov ~00:40): installs exe 5be0c6a5 (pi.dev's patch-1505, contains all of the above) + hl2 plugin d21e12b2;
lobbies + installs cs 267e9b9b / qw ffc0f7e9. tasrevd codes.txt lists every csprogs above (124 lines, .pre1504).

## Survey 5 (live builds, quiet machine, 2 passes a map: first play + warm, players' default effects, r_blendsort 2)

Results: `artifacts\survey5-results.tsv` (cols: map, board, p1 avg/1%/0.1%/max ms/stutters, p2 same, log, exe, plugin,
cs), dumps `artifacts\survey5\<map>-p<n>.txt` (r_frametime_dump with r_spikes' slowest frames). 57 of 60 maps done.

**Not done: surf_whiteout, surf_zae, surf_zoomathon.** At handoff a run_survey3 python (pid 13124, launched from this
session) waits at `artifacts\HOLD`, which ftesurf-16's watcher (`jargon-courses-1111a\tmp\peerhold.sh`) removes when
its Jargon batch ends (Lex asked that batch to run first; many hours). If that process is gone (session ended,
memory reaper), rerun from `artifacts\`:
`LOWS2_BIN=bin_live LOWS2_NEED_MIB=3000 LOWS2_SURVEY_RES=$PWD/survey5-results.tsv LOWS2_SURVEY_DIR=survey5 python -B run_survey3.py survey5-rest.txt`
(it skips maps already in the TSV). First refresh `runtime\game\bin_live` and the rig's `ftesurf\*.dat/.lno` from
C:\FTEQuake if the installs moved, and take the rig per "Rig etiquette" below.

Warm 0.1% ranking (fps): fairy 129, kitsune_css 174, bossfight 196, pantheon 196, joutsenlaulu 209, hourglass 236,
nuclear 239, mesa_revo 240, jumble 267, colony 272 ... the rest 280+ and flat (<= ~20 stutters).

## Open leads, best first (evidence in BACKLOG "Survey 5 stutter maps after P1504" and "First-play leftovers")

1. **surf_kitsune_css (174, 739 warm stutters over 2.8 ms):** CSQC spikes 2.4-5 ms in the first seconds of the warm
   pass (QC UpdateView, HUD) plus windowed present stalls (3.5-6.3 ms "swap/present" -- rig contention, ignore).
   Next: per-builtin attribution (recipe below) to name the QC.
2. **surf_pantheon (196, few stutters):** heavy throughout; slowest frames opaque draws 1.6-1.9 ms (CPU) + CSQC
   1.5-1.9 + hl2 props 0.5 at replay ~2-7 s. Renderer per-draw cost; profile before choosing.
3. **surf_fairy (129):** (a) sprite system CSQC with players' default sprites/glows ~0.94 ms/frame avg (Sprite_Draw:
   glare 0.40 mostly rays, sky 0.20, 38k QC ops a frame looping 460 sprites); the glare's fade loop over every glow
   runs outside the trace budget. An engine-side sprite loop would be the big lever. (b) r_blendsort 2 (Lex's, players
   default 1): sorts fail often in motion; failing sorts ~0.3-0.4 ms vs 0.03 ms. DO NOT loosen P1490's exact-face-set
   memo key: measured, many face-set-rejected sorts then SUCCEED (271 ok vs 11 fail in one window). Any-hit traces
   for glare rays: rejected on reading (BIH already front-to-back with hit pruning).
4. **surf_bossfight (196):** GPU-bound at the brickhouse start (Transparent & effects 4.6 of 6.2 ms; r_drawentities 3
   -> 0.12 ms): ~300 translucent window/blind props ({pi_window.vmt is $translucent + $alphatest -- Source draws it
   translucent too). Opaque rendering is not pixel-identical (8% of texels pass the cutoff partially;
   artifacts\vtfalpha.py). Content cost unless Lex accepts a look change.
5. **surf_joutsenlaulu (209):** broad tail; its two spikes were system stalls attributed to trivial QC. No code lead.
6. Small: the sun glare's material registers on first sight (one late compile per env_sun map). Load time: fairy's
   first frame after the loading screen ~2 s (shader reload 1.1 s, P1364 prop light 0.6 s) -- loading, not lows.

## Tools (artifacts\)

- `run_survey3.py` (survey; env LOWS2_BIN, LOWS2_EXTRA per-arm cvars appended after the base cfg, e.g.
  `LOWS2_EXTRA="r_spikes 2"`), `survey_swap.py <csprogs|live> <maps>` (same on a scratch csprogs, restored after).
- `probe_static.py <maps> <map> <replay s>` paused-view A/B: PS_BIN, PS_VARIANTS="exec a.cfg|exec b.cfg" (cfgs in
  runtime\game\ftesurf, each setting EVERY toggled cvar), PS_TRACEV=1 for r_blendtrace. GPU-by-pass table in the log.
- `abq.py` in-motion unprofiled r_budget A/B (AQ_CSPROGS swap, AQ_SPRITES, AQ_CENSUS/AQ_SKYC). `profqc.py` profile_csqc
  (ranks; inflates small calls). `blendq.py` BLENDSTATS counters. `glareq.py` glare clock. `latecompile.py` late
  shader compiles with a given warm list + launch cfg (lexcfg.cfg = render-only copy of Lex's cfg -- never exec his
  raw ftesurf.cfg in the rig: vid_fullscreen 1). `spawn2.py` load time + post-spawn frames (scr_loadtimes).
- Diag engine branches on origin: `diag-blendmotion` (BLENDSTATS + per-builtin r_spikes 2 + named r_blendtrace),
  `diag-latecompile` (LATECOMPILE/LATESHADER). Build into a `runtime\game\bin_<name>` with the live plugin + server.
  Per-builtin attribution recipe: diag-blendmotion exe in a bin, then run_survey3/survey_swap with
  `LOWS2_EXTRA="r_spikes 2"`; each slow frame then lists "qc builtins" and "qc self".

## Rig etiquette (cost us time this session)

- Shared lock = DIRECTORY `C:\FTESurf-worktrees\rig.lock` (owner.txt). ftesurf-16's batch yields if you touch
  `C:\FTESurf-worktrees\jargon-courses-1111a\HOLD` (it stops after its current run, <= 25 min); remove it after.
  Peers yield via `artifacts\HOLD`. Message ftesurf-16 before and after (SendMessage).
- LOWS2_TANDEM=1 = beside a peer: memory-only gate, NO timing claims, and it does not serialize your OWN runs
  either -- chain your runs in one script.
- Claude Code's memory reaper kills idle background shells: afterwards clear a stale rig.lock whose pid is gone, stop
  orphaned bin_* clients (`python -c "import rig; rig.stop()"`), remove any peer HOLD the script would have removed.
- No builds while a survey or a peer benchmark measures (CPU contention). Timing only on a quiet machine.

## Delivery checklist (QC and engine), with this session's traps

- QC: check the installs' and lobbies' live hashes against the newest delivery record and `git log <live src>..HEAD
  -- src/` for others' undelivered code; `build.ps1 -Pi` from the qc worktree; deliver C:\FTESurf with a
  deliver_qc_pNNNN.py (artifacts\deliver_qc_p1504.py: live-hash guard, .prev + archive, owner-file hashes); APPEND THE
  csprogs sha256 to `proto@192.168.1.102:/srv/nvme/ftesurf-ops/tasrevd-state/codes.txt` (cp -p .preNNNN first;
  build.ps1 -Pi does not); smoke the csprogs on the last release exe (runtime\game\bin_rel0144).
- Engine: annotated tag patch-NNNN; full build from the tag (`build.ps1 -Engine -Full -NoDeploy -FteRoot <engine>`);
  one stamp `git-<count+29>-patch-NNNN-0-g...`; `tools/check_tls_refptr.py release/m_mgw64 release/sv_mingw64`;
  deliver exe (+ hl2 plugin) with artifacts\deliver_p1501.py (pi.dev leaves *.prev READ-ONLY -- keep it, put the
  predecessor in *.preNNNN).
- Records: PATCHNOTES "## next" (points <= 250 chars; dot-source ConvertFrom-PatchNotes from releaselib.ps1 and
  parse the file), ENGINE.txt line (+ pin for engine patches), lextest.md, BACKLOG, tools/pNNNN-claim.md
  "Delivered" line. Claim numbers after fetching both repos (tools/pNNNN-claim.md on origin/main).
