# 0.1.29 — Lex's two lists of 21 Oct and everything since 0.1.28

Released **0.1.29+b89.p900** at 2026-10-21T08:12Z (built 08:08:54Z), requested by Lex ("I want a new update pushed to my game,
however I want some things cleaned up and some settings to be default ... and fix the other bugs I have
please"), held for ftesurf-2a's P893 on his word ("hold on the release ... merge that one too"). Build stays 89.
No overrides. Lobbies were not restarted for it: they already run this QC.

## Sources

- QC `2834ed62` (main). Its csprogs `b8adda1e` and qwprogs `b685ef3a` are byte-identical to the lobbies' and
  both installs'; `menu.dat` (`cf7586d7`) differs from the installs' `c3f9597d` only by the version string.
- Engine `f6dc50075` (tag `patch-900`) = ENGINE.txt's pin: P898/P900/P903 on ftesurf-2a's patch-893.
  Natives from the integration worktree's `-j2` build, restamped after tagging
  (`git-7690-patch-900-0-gf6dc50075`): exe `8109f66d`, hl2 `a31abb5f`, imgui `97e033be` = both installs'
  since 07:53Z; gate 3 matched all three. Linux drop built at the same commit with the same stamp, 10/10 gates.
- Launcher `646c8d1`, unchanged since 0.1.26.

## Generated inputs

Copied from `C:\FTESurf` into the fresh worktree (gitignored): `src/fteqcc64.exe`,
`data/mapdeps|mapmeta|mapparticles|mapdl.txt`, `particles/` (7), `gfx/mapthumbs` (8), `gfx/thumbnails` (48),
`maps/zones/local` (649). `mapwr.txt` regenerated read-only from the Pi's database: 1,167 maps. All 721 hashes
are in the root's `generated-inputs.sha256`.

## What the preparation hit

- The Linux engine build was stopped twice for memory: `build.sh` compiles with `nproc` (16) jobs inside WSL
  while the owner was using the PC. Rebuilt at 2 jobs (`OMP_NUM_THREADS` through `WSLENV`, which `nproc`
  honours) with a free-memory watch; lowest free 2.88 GB. The killed run left
  `refs/heads/ftesurf-selected-build` in `/srv/fteqw-mirror.git`, which `build.sh` refuses; it named this
  commit and the flock was free, so it was deleted with a compare-and-swap `update-ref -d`.
- Both launchers were pre-built at 2 jobs (`CARGO_BUILD_JOBS`; for the Linux bootstrap, whose cargo runs with
  `env -i`, a `jobs = 2` `config.toml` in its own `target\ftesurf-linux\cargo-home`, outside the hashed
  provenance), so the prepare's cargo steps were incremental (P876's earlier 0.1.29 attempt was reaped there).
- WSL was held up with a `sleep` through preparation and smoke (0.1.28's step-14 trap).

## Checks

- 0 warnings in all three QC builds. Gates 1-4 pass, and so do the Linux gates.
- Trusted candidate SHA256 `b8a955ba...282623d4`; `-PublishPrepared -DryRun` verified 760 objects.
- Windows `.7z`: 40.8 MB, sha256 `10E26D25...DB3E6F9E5`. Linux `.tar.xz`: 40.7 MB, sha256
  `8FA3F597...CB17497D7`. Both round-trip after a full download; all 760 signed objects round-trip; both
  standalone launchers match; the page and feed are byte-exact and served no-cache.
- `release_smoke.py`: new launchers installed fresh from public HTTPS. Windows rehashed 850 files and Linux
  849, and 3 sentinels were kept on each. No game was launched.
- The 0.1.28 launchers, unmodified (hashes checked against their published `.sha256`), installed 0.1.29 from
  the live feed (`--yes --no-launch`, exit 0, VERSION.txt 0.1.29). Existing players need no new launcher.
- Before the release: a combined check of the integrated build (defaults and all 23 binds read back,
  bhop_eazy back to front by `r_blendtrace`, server `sv_tickparts 1`) and lobby smokes on 27510 with the new
  client and 0.1.28's exe (served csprogs `b8adda1e`, board drawn, no QC error).

## What is in it (patch log 839-906)

60 patches under `## next`: Lex's second list (P898 new-install defaults, binds, borderless and ALT+ENTER;
P899 newest save; P900 layered glass order; P901 ghost offset in ms; P902 F2 holds updates, notes, journal and
terms; P903 quiet redirect URL; P904 results card; P905 story preload, surf_tendies and surf_affliction),
ftesurf-2a's P892/P893/P897/P906 (zone-tool triggers, one Source tick per part, quiet offline console), the
six-map list P884-P895, and P839-P883 from 19-20 Oct. surfd and web patches do not ship.

Owned root: `C:\FTESurf-worktrees\release-0129-20261021T075803Z\` (OWNER.md). Retained as evidence.
`launcher/target/ftesurf-linux/cargo-home/registry` is a link into the shared Cargo registry: unlink it before
removing the root, and never delete it recursively.
