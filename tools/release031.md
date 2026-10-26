# 0.1.31 - everything since 0.1.30

Released **0.1.31+b89.p1048** on 26 Oct 2026; publication completed 10:40:40Z (built 10:36:52Z). Requested
by Lex: "bundle up all the new features, make build, deploy, commit, whatever you have to do to make a new
version the downloader/website knows about!" Build stays 89. No overrides. Lobbies were not restarted for
it: the released qwprogs `fa93d213` and csprogs `9b926b67` are byte-identical to both installs' and the
lobbies' (deployed with P1050/P1051 the same hour); menu.dat `513afc7c` differs from the installs'
`d0eb3e8a` only by the version string.

## Frozen inputs

- QC `f7d5fc82` (main), clean inspected source: 92 patch entries under `## next`, P949-P1051, among them
  the bhop_ceaseless lists (P1012-P1033), response contexts on by default (P1036/P1037), Source grass and
  GPU-skinned props (P1038/P1047), fail teleports (P1050) and goto_start (P1051).
- Native `c7dc90bd3` (tag `patch-1047`), exact stamp `git-7899-patch-1047-0-gc7dc90bd3`: the installed
  Windows cohort reused (exe `e28907a1`, hl2 `36cea9c8`, imgui `58841b0b`, identical in both installs),
  copied into the engine worktree's `engine/release`; gate 3 matched all three. ENGINE.txt pins the
  docs-only `c931d98ea` (patch-log entries) on top of it. The receipt's native patch 1048 is the highest
  heading at `c7dc90bd3`; QC patches 1049-1051 need no native change.
- Linux built at `c7dc90bd3` in the Bullseye builder at 2 jobs (OMP_NUM_THREADS through WSLENV): 10/10
  gates, same stamp, GLIBC 2.29; the bootstrap raises the advertised floor to 2.30.
- Launcher `646c8d1`, unchanged since 0.1.26; Windows cargo (CARGO_BUILD_JOBS=2, pre-built) and the Linux
  bootstrap (`jobs = 2` in its cargo-home) at 2 jobs. WSL held up by a `sleep` through prepare and smoke.
- Generated inputs copied from C:\FTESurf (gitignored): the natives, `data/mapdeps|mapmeta|mapparticles|
  mapdl.txt`, `particles/` (8, now with bhop_ceaseless.cfg), `gfx/mapthumbs` (8), `gfx/thumbnails` (the 12
  0.1.30 shipped; SVG sources, 32 px conversions and two scripts beside them were left out),
  `maps/zones/local` (648), fteqcc `c24ede65`. Backup files (`*.pre*`) and `zones/local/.old/` dropped.
  `mapwr.txt` regenerated read-only from the Pi's database: 1,175 lines. 684 input hashes in the root's
  `artifacts/release031-inputs.json`.
- Release tooling `d1e1dcb4`: the preflight refused 98 literals, the knife catalog's CS:GO Legacy knife,
  sleeve and glove models (installed metadata, never bundled) and a `particles/sec` unit string; two narrow
  DENY prefixes and three exact names, each with its reason.

## Preparation / exact promotion

One `-Bump patch -DryRun`: three VMs 0 warnings, gates 1-4 and the Linux gates pass, both archives match
their stages, signed feed 1,717 files / 768 objects. Trusted prepared candidate SHA256
`aca5f7709ded0cea60d749af05edb17fddaf6ad0e6050e9f4886fd17f5c01988`; trusted local receipt SHA256
`49d32673ccf34e4ec4f32889a28dc9547c67864bb7659d0106f9c20fedff504a`. The prepared-only dry run verified 768
objects without a compiler, packer or signing. Published that exact candidate with `-VerifyFull`: both
archives round-trip after a full download, both standalone launchers match, all 768 referenced objects
verify, the page is byte-exact and the served signed feed matches exactly and is no-cache.

- Windows 41.0 MB, SHA256 `A02B556D5C9F4395A719E2F9DFFD1D787EAC36F567C79B9B7E17FB9093C9DF29`
- Linux 40.9 MB, SHA256 `01D8A462A061E60CE6B76148A0E4FE25152142E65E7EC3AC5F761CF6D93FF5E7`

## Public acceptance

- `release_smoke.py`, default HTTPS, the newly downloaded launchers in fresh synthetic installs: Windows
  858 and Linux 857 managed files rehashed, 3 settings/data/edited-zone sentinels preserved on each, no
  game launched.
- 0.1.30's launcher, unmodified (its SHA256 equals the published `.sha256`), installed 0.1.31 from the live
  feed into an empty folder (`--yes --no-launch`, exit 0, VERSION.txt 0.1.31): existing players need no
  new launcher.
- Delivery/update integrity acceptance, not a play test; the patches' own owner checks are in lextest.md.

## Retention

Owned root `C:\FTESurf-worktrees\release-0131-20261026T0921Z\` (OWNER.md): sealed candidate, logs,
inputs, receipts and smoke proof (local receipts name this machine and were not uploaded). The launcher
worktree's `target/ftesurf-linux/cargo-home/registry` links into the shared Cargo registry: unlink it
before removing the root, never delete it recursively.
