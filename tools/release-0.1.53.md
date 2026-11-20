# World of Surf 0.1.53 delivery

Published 20 Nov 2026 (21 Nov local), completing at **15:01 UTC** (worldofsurf-75) from the Linux PC, one sealed candidate, no rebuild.
Lex: "Well do the still open please. fix it all up." -- the open item was the Linux run-graph (ui_imgui) plugin reaching
players. Page: <https://proto.bar/ftesurf>.

- Version **0.1.53** (`0.1.53+b89.p1667`), QC build 89. Frozen QC `8f7908e3` = main at the cut (branch `release-0.1.53`,
  tag `v0.1.53`). One patch entry: P1668 (run graphs on Linux).
- Progs: qwprogs `9879822f`, csprogs `b915c60f` (unchanged from 0.1.52, already in tasrevd codes.txt), menu `7df9755b`.
- Engine unchanged from 0.1.52 (patch-1666/1667 builds reused, as 0.1.50 reused 0.1.49's): FteRoot release0152-75/engine,
  Linux drop db8de41f0 (it always held the plugin; P1654).
- Launchers: Windows `WOS-Launcher-0.1.53.exe` = the published MSVC bootstrap, source 8de1339, reused through the new
  `-WindowsLauncherRoot`; Linux **0.1.7** built in the Debian 11 rootfs from Quakers-Launcher 13e7327 (tag
  wos-launcher-0.1.7), `7add7813`. The feed's "launcher" entry names it, so P1666 engines install it on existing Linux
  installs; the Windows entry is unchanged (no refresh there).
- The signed feed carries `files_ext` = [fteplug_ui_imgui_amd64.so linux64, 1,171,395 bytes, blake2b `04ba7eab`]; it is
  in no "files" entry. Prepared `070e755eb30baa2adab061c823bce5293270391da3e8edec2af0b4a76be59ebb`; receipt
  `93d8084f86d4e859b456b3c73f36170827818a84b0a152ca3006b8b9031f7489`; feed `0844d27a` (prev 0.1.52 `76014d86`); 1286
  objects. Overrides: none.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.53.7z` | 79,082,429 | `1c794748813d0e153bd3595ca588254b12bae56f9b3811c70d9aab6d003282f9` |
| `ftesurf-0.1.53-linux-x86_64.tar.xz` | 79,534,924 | `cf677f3d85e8df7491e6e85143f09b5be46b7008c612a98cabf1ba20bf2c6a46` |
| `WOS-Launcher-0.1.53.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.53-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS; preparation gates 1-4 PASS, Linux gates PASS, "Windows bootstrap source 8de13397d, Linux 13e73277f";
  receipt provenance Windows 8de1339 (so the next release can reuse it again), Linux 13e7327; the sealed feed's plugin
  entry and launcher entries match the staged files; `-PublishPrepared -DryRun` 1286 objects.
- End to end on the candidate's content (release0153-75/tools/p1668arm.py, loopback): a 0.1.52 Linux install's 0.1.6
  launcher updates from the feed and installs no plugin; the engine's check replaces it with 0.1.7; 0.1.7 installs the
  plugin (state.json records it); plug_list shows fteplug_ui_imgui_amd64.so loaded; a second run keeps it verified.
- Linux game smoke and Wine smoke on the stages; `-VerifyFull` rc 0; release_smoke linux64 1380 (now rehashing
  files_ext) / win64 1379.
- Production (tools/p1668prod.py): the same path from the live feed and dl.proto.bar, all pass.

## Scope and limits

Automated checks only; owner check pending (lextest.md). Windows-side launcher changes still need a Windows host or a
gnu cross-build (BACKLOG). Root `FTESurf-worktrees/release0153-75` keeps qc/dist, artifacts and inputs until the next release.
