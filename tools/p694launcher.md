# P694 — animated World of Surf launcher

## Scope / source

Launcher-only presentation, not the full game rename. The signed Surf bootstrap
retains `ftesurf-launcher`, on-disk names, updater metadata, feeds, keys, transport
and install-readiness rules. The Quakers entry point keeps its existing UI.

- Launcher base: `5c60f697c635a8b82affdcd46f51a50aedd3d280`.
- Accepted launcher feature: `64b750799887906be393ba35a5b96f6de45d5855`.
- Product ledger only: engine documentation `2dfe8a4f8fb10180f80144d3893d23d94e975cfc`.
- Native runtime pin/tag remain `195dc58e9054b421dc9c76530a0715df64864183` / `patch-692`.
- QC base: `45077267849ad85b8ea36d67a3ae9c154862e615`; product patch is694,
  no QC Build/public version bump. Generated programs are unchanged.

Task root: `C:/FTESurf-worktrees/woslaunch-20261014T043734Z/` (OWNER.md).
Paired isolated launcher/QC/engine worktrees; no canonical source editing except
an untracked patch reservation, removed after publication. Peer performance
configs/shaders/source/processes, prior handoff recovery work and roots are not
part of this task. No game, native engine or QC build/test process was launched.

## User-facing changes

- Large cyan/violet SURF wordmark beneath WORLD OF, neon sunset/ramp artwork.
- Deterministic light-band sheen, star twinkle, gentle sun glow and moving ocean
  waves at the existing160 ms terminal cadence. No GPU/window/dependency/art fetch.
- The initially proposed tagline is removed everywhere, including CLI help.
- Artwork animates during downloads and on Enter/Y confirmation pages.
  Esc/N/Q/Ctrl-C declines. First-run decline stores update opt-out as before;
  download/launch decline exits without starting a game.
- `--yes` and redirected automation cannot acquire a new prompt. First-run
  permission still requires an interactive terminal or explicit --yes/--offline.
- Main progress is verified FILES; content meters are verified BYTES. Workers
  show live staged bytes. Received speed/ETA is approximate and separate; retries
  cannot manufacture verification, and resumed files count after successful hash
  verification even without network traffic.299/300 stays99%, never rounded100%.
- Raw-key transfer cancellation returns through terminal guards; downloader
  aborts/drains workers and refuses before installation/game launch. Partial
  files remain for the existing guarded rehash/resume policy.
- Early-return sample-only controls: `--ui-preview` plain text, `--ui-demo` live
  animation (interactive terminal, Enter/Esc closes). No lock/recovery/network/
  install/game operations occur in either preview mode.

## Pre-registered acceptance / executed controls

Predictions were recorded before mutation in task `artifacts/PLAN.md`, with the
operator's animation amendment and original finding dispositions in AMENDMENT.md.
The baseline Surf entry point had neither branded renderer nor preview/demo;
source-only baseline is not a before-binary runtime claim.

All Cargo builds use locked, offline dependencies, one job and Windows IDLE
priority, with target/tmp under the owned task root. Logs are bounded artifacts.
Commands include:

```text
rustfmt --edition 2021 src/ftesurf_ui.rs
cargo test --locked --offline -j 1 --lib -- --test-threads=1
cargo build --locked --offline -j 1 --bin ftesurf-launcher
rustfmt --edition 2021 examples/world_of_surf_ui_probe.rs
cargo build --locked --offline -j 1 --example world_of_surf_ui_probe
python -B <task>/artifacts/smoke.py
python -B <task>/artifacts/console-test.py
python -B <task>/artifacts/render-preview.py
```

- Windows Rust library: **41 passed, zero failures, zero warnings**; existing
  signature/disk-policy and acted transport/link/partial-resume guards remain.
- Renderer:46 distinct artwork frames while the actual verified/progress cells
  remain identical; 0/50/100% controls, near-full99% boundaries, all categories,
  compact/tiny/zero dimensions and prompt resizing. Enter/rejection keys and
  release/repeat ignoring are asserted. No tagline in full/compact/prompt frames.
- **Six explicit piped-I/O binary checks:** sample preview before install/network,
  help with demo flag/no tagline, noninteractive demo refusal, undecided consent
  refusal, offline/no-launch, --yes error without a pause. Preview does not create
  the deliberately nonexistent install directory.
- **Six real hidden Windows-console controls:** demo Enter/Esc/Ctrl-C, renderer
  normal stop/Ctrl-C, active guarded slow loopback transfer Ctrl-C. Win32 input
  events/readbacks prove artwork ACT and changes; cooked input/main screen/final
  cursor restore. Controlled exits are0. The transfer made one local GET, staged
  **65,536 bytes**, left an unpromoted partial, and never installed/launched.
  Registered owned PIDs only; consoles were verified hidden and never took focus.
- PNG/GIF previews are rendered terminal cells with SAMPLE DATA labels, not game
  or physical-desktop screenshots. GIF46 frames/160 ms; actual native readback
  separately proves art changes. No fabricated download progress.

Original fresh review of the frozen six-file snapshot blocked on cooked-terminal
Ctrl-C teardown and noted rounded100%. Both are fixed and falsified. Fresh narrow
follow-up of the final seven-path amendment is **OK with notes**, no findings;
review-launcher-02.md. Parent rechecked all seven frozen-source hashes before
commit. LSP returned no recorded diagnostics; that is not Rust build proof.

## Failure history / honest limits

Retained failed logs: missing Stylize/ensure imports in early compiles; smoke
incorrectly expected an offline message despite --no-launch early-return; image
reader initially omitted UTF-8; ConPTY harness attempts inherited wrong handles
or did not capture terminal output. None is hidden or counted as acceptance.
A first hidden-console helper failed to detach its inherited console. Native
cursor API reported visible even while VT alternate artwork was active: direct
hide-command emission and physical cursor visibility are NOT proven. The final
native controls assert final cursor restoration and record the during value.
Expected server disconnect initially surfaced ConnectionAbortedError after a
successful cancellation; the fixture now classifies that expected cancellation
exception explicitly. Earlier failed setup artifacts remain in the task root.

Linux execution, external signal/hard termination, full signed-bootstrap
cancellation, physical console/font/cursor behavior and subjective motion/art
acceptance remain separate. Follow-ups: BACKLOG.md; human artwork: lextest.md.
No native/QC rebuild, canonical or fleet deployment, official archive/feed
publication, bootstrap self-update or full game rename is claimed. An ordinary
content update cannot ship this separately delivered bootstrap; official archive
integration remains a separate release operation.

Unique evidence/preview binary and publication/retirement receipts remain under
the owned task root's artifacts/. Disposable target/tmp and clean source trees
may be retired only after commit/ref and ownership checks; OWNER.md explains any
retention. The final checkpoint separates committed, built, pushed and deployed.
