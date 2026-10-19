# 0.1.28 — the 19 Oct frame-time work and everything since 0.1.27

Released **0.1.28+b89.p836** at 2026-10-19T13:39Z (built 13:33:38Z), requested by Lex ("can you
please combine all of these updates I've made recently and push a update to the game"). Build stays
89. No overrides. Lobbies were not restarted: they already run this QC.

## Sources

- QC `353098d0` (main). Its csprogs `f1f94d56` and qwprogs `90f915b6` are byte-identical to the
  lobbies'; `menu.dat` differs from the installs' in 3 bytes (version string, compile date).
- Engine `39afb825f` (tag `patch-836`) = ENGINE.txt's pin. The receipt's `p836` is that commit's top
  patch-log heading; ENGINE.txt's `patch 838` is a reader-only patch, so preparation reported
  "pin drift 838 vs 836", which is documentary. Native Windows products reused from the `-Full`
  restamp build (`git-7520-patch-836-0-g39afb825f`): exe `ff0f0a2d` (the installs' exe), hl2
  `0939fdff`, imgui `737171e0` (the installs' plugins are 831's builds of the same plugin source);
  gate 3 matched all three against `engine\release`. The Linux drop was built at the same commit with
  the same stamp; all 10 gates pass.
- Launcher `646c8d1`, unchanged since 0.1.26.

## Generated inputs

Copied from `C:\FTESurf` into the fresh worktree (gitignored): `src/fteqcc64.exe` (`7ccb93d1`, the
compiler 0.1.26 and 0.1.27 used), `data/mapdeps|mapmeta|mapparticles|mapdl.txt`, `particles/` (7),
`gfx/mapthumbs` (8), `gfx/thumbnails` (48), `maps/zones/local` (649). `mapwr.txt` regenerated
read-only from the Pi's database: 1,170 rows (0.1.27: 1,167). All 718 hashes are in the root's
`generated-inputs.sha256`.

## What the preparation hit

- Attempt 1 stopped at step 14 (Linux pack): WSL had idled down, and its cold start printed
  "Failed to start the systemd user session for 'root'" ahead of wslpath's answer, which
  `ConvertTo-WslPath` took as the path. Nothing was sealed or uploaded; its log and unsealed .7z are in
  the root's `failed-prep-1/`. Attempt 2 ran with a `sleep` held in the distro and passed. The
  tooling fix (ignore that line) is in BACKLOG; it was not made mid-release because it would change
  the publisher bytes the candidate seals.

## Checks

- 0 warnings in all three QC builds. Gates 1-4 pass, and so do the Linux gates.
- Trusted candidate SHA256 `0c6427c5...a06d1feb`; `-PublishPrepared -DryRun` verified 761 objects.
- Windows `.7z`: 40.8 MB, sha256 `BFCC6CBF...0DC8A551`. Linux `.tar.xz`: 40.7 MB, sha256
  `168C9B3F...1D03855`. Both round-trip after a full download; all 761 signed objects round-trip;
  both standalone launchers match; the page and feed are byte-exact and served no-cache.
- `release_smoke.py`: new launchers installed fresh from public HTTPS. Windows rehashed 851 files and
  Linux 848, and 3 sentinels were kept on each. No game was launched.
- The 0.1.27 launchers, unmodified (hashes checked against their published `.sha256`), installed
  0.1.28 from the live feed (`--yes --no-launch`, exit 0, VERSION.txt 0.1.28). Existing players need no
  new launcher.

## What is in it (patch log 786-838)

Since 0.1.27 (patch 785), from the patch log: P831 instanced props, P832 r_blendsort 2, P836 native
board-line names, P837 run-graph cache, P827 Line_End; P812 big velocity, P813 mover 8, P805 camera
smoother, P818 surf_view colours, P802 portal visibility, P799 glows, P810 proximity fade, P807 volume
brushes, P786-P791 (spectate in triggers, friends, pictures, rot buttons, beams); the chat panel
(P821/P824), rewind saves and fail rewind (P808/P809/P811/P817), first-boot screens (P796/P823),
hud_edit (P798/P806), r_budget_csqc and r_frametime (P800/P801), zone publishing (P815/P822), the
lobby hour (P819), replays (P814/P820), Teleport-to-player (P797), and the readers 792-794/816/828/833/838.
surfd and web patches (825, 826, 829, 830, 834, 835) are server-side and do not ship.

Owned root: `C:\FTESurf-worktrees\release-0128-20261019T132138Z\` (OWNER.md). Retained as evidence.
`launcher/target/ftesurf-linux/cargo-home/registry` may be a link into the shared Cargo registry:
unlink it before removing the root, and never delete it recursively.
