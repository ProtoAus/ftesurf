# P695 — simpler ASCII wave launcher artwork

## Correction / source

The owner rejected the abstract P694 ramp/sun art as not matching its description
and requested an ASCII wave. That feedback supersedes the earlier art choice.

- Launcher base:64b750799887906be393ba35a5b96f6de45d5855.
- Accepted launcher correction:47871ddbc6324a69a1a4cfd89ea61449a7267464.
- Engine ledger ONLY:65c540fed75a1f891ab7b7e9c1b97f7906f22f58.
- QC base94e0af582415809d2561d01d6915d84294e4bb1b retains the merged peer P693
  native pin4148e72923e617a79bf8ed16474cc49143fb72fc / patch-693. Only product patch
  counter advances to695; native source/pin/tag, QC Build/public version stay put.

Only launcher README.md and src/ftesurf_ui.rs changed: ten-line all-ASCII wave,
white/cyan curl held steady, tilde waterline moving sideways. Remove ramp/sun/stars.
The logo and its existing sheen remain. Pad wave rows to equal width before
centering; individually centered differently sized rows shifted the outline.

Bootstrap/progress/transport/signature/confirmation/guard/probe files were compared
byte-for-byte with P694 and are unchanged. No new dependency, network/art request,
GPU/window, install/launch gate, game rename or real-progress semantics change.
This localized illustration correction has parent source/visual acceptance, not a
new independent-review claim. Original independent control-flow review remains
historical P694 evidence, not proof of the owner's new aesthetic acceptance.

## Controls / evidence

Owned task root:C:/FTESurf-worktrees/asciiwave-20261014T053529Z/. OWNER.md/PLAN.md
precede scratch population. Prior root and old previews are read-only controls.
All builds use locked offline Cargo, jobs1 and IDLE priority with owned target/tmp.
Commands and results in artifacts/validation-02-*.log, smoke-results.json and
console-results.json:

```text
rustfmt --edition 2021 src/ftesurf_ui.rs
cargo test --locked --offline -j 1 --lib -- --test-threads=1
cargo build --locked --offline -j 1 --bin ftesurf-launcher
cargo build --locked --offline -j 1 --example world_of_surf_ui_probe
python -B <task>/artifacts/smoke.py
python -B <task>/artifacts/console-test.py
python -B <task>/artifacts/render-preview.py
```

-42 Rust library tests pass, zero failures/warnings. New all-ASCII/equal-row-width
  and complete80/100-column render assertions ACT; stable curl/moving-water
  contrast plus existing46-frame real-progress-invariance tests pass.
- Six explicit piped binary regressions: sample preview before install/network,
  help/no tagline, noninteractive demo refusal, undecided consent refusal,
  offline/no-launch, --yes error without a pause.
- Six real hidden Windows-console regressions: sample Enter/Esc/Ctrl-C, renderer
  normal stop/Ctrl-C and an acted slow local partial-transfer cancellation. Art
  changes, raw input/main screen/final cursor restore and controlled exit0 pass.
  One loopback GET only, no official feed/game/installation. Only registered own
  PIDs; no source/config/shader/player fixture or process of the performance bot
  was touched. Native cursor-hide/physical/Linux limits from P694 remain unchanged.
- Parent inspected the terminal-cell PNG after equal-width alignment and saved
  wave-before-row-alignment.png as the visual layout control. PNG/GIF are sample
  terminal-cell renders, not a physical desktop/game screenshot or owner approval.

## Safe NEW preview / delivery boundary

Use artifacts/Preview-World-of-Surf.cmd under the NEW task root above (not the old
P694 preview). It runs only --ui-demo with sample data; Enter/Esc closes, no game,
download or install operation. artifacts/world-of-surf-preview.png and
world-of-surf-animation.gif show the simpler wave. The curl is static, waterline
moves; no former sun/stars/ramp/tagline. Personal console/font/readability feedback
is still requested in lextest.md, not inferred from passing unit tests.

Source commits/publication receipts, exact debug-preview/source-archive hashes and
workspace status are in artifacts/CHECKPOINT-ASCII-WAVE.md / preview-manifest.json.
No canonical/fleet binary swap, official archive/release/feed publication, native
engine/game/performance run or full rename. The current launcher source and one
owned Cargo target may be retained through this still-active artwork feedback
iteration to avoid repeated cold builds; OWNER.md explains exact paths/retirement.
Clean QC/engine doc worktrees are disposable after publication. No blanket clean
or peer-root cleanup. Previous source/preview evidence stays untouched.
