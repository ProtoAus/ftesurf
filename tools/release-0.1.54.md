# World of Surf 0.1.54 delivery

Published 21 Nov 2026, completing at **01:32 UTC** (12:32 local; worldofsurf-9e, renamed a5 after the desktop restart)
from the Linux PC, one sealed candidate, no rebuild. Lex: "yes" to "shall I cut 0.1.54?" (with P1695). It supersedes
worldofsurf-e3's sealed release0154-e3 candidate (main 9ccec5dc, old engine), which e3 agreed not to publish.
Page: <https://proto.bar/ftesurf>.

- Version **0.1.54** (`0.1.54+b89.p1695`), QC build 89. Frozen QC `b7c5dd59` = main at the cut (branch
  `release-0.1.54b` in release0154b-9e; tag `v0.1.54`). 26 patch entries, P1640 to P1695 (everything under `## next`).
- Progs: qwprogs `8a16f052`, csprogs `42970496` (appended to tasrevd codes.txt, backup .pre0154-20261121T013404Z),
  menu `59be3f77`.
- Engine **c7f7135e1** (patch 1695), the first new engine since 0.1.52's db8de41f0: it carries the engine halves of
  P1646, P1669-P1670, P1682, P1683, P1686, P1687, P1691 and P1695. Windows cross-built in the root's engine worktree
  (clean release/, TLS check 0 plain-address uses, warning set identical to 0.1.52's); Linux built in the Debian 11
  rootfs (BUILDINFO gates all PASS); both stamp `git-8960-patch-1691-20-gc7f7135e1`.
- Launchers unchanged: Windows `WOS-Launcher-0.1.54.exe` = the published MSVC bootstrap (source 8de1339, reused through
  `-WindowsLauncherRoot`), Linux 0.1.7 (Quakers-Launcher 13e7327). The feed's launcher entries and the Linux ImGui
  plugin's `files_ext` entry are as in 0.1.53.
- Prepared `f94757091ae75aaaa8ea9e4573345e136fa3a9a321d428805dfb3754b233f866`; receipt `aa72a7f9`; live feed `1ec0d586`
  (prev 0.1.53 `0844d27a`); 1292 objects. Overrides: none. `-MaxTotalMB 130`: the first prepare stopped at the 128 MB
  ceiling with a 128.3 MB stage, the whole growth over 0.1.53 being P1695's six sky faces (386 KB) and ~60 KB of progs
  and engine; nothing had been sealed.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.54.7z` | 79,364,613 | `6427f232939fa5c11f7d305a93ac5cb9f694389bbfe8ff2bfc81c4793db3a864` |
| `ftesurf-0.1.54-linux-x86_64.tar.xz` | 79,820,984 | `44e989bfe9ae70249137267e71c6b4e59dcee4b25c571018da73bfc971001b45` |
| `WOS-Launcher-0.1.54.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.54-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (26 patches); preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1292 objects;
  `-VerifyFull` rc 0 (both archives, launchers and all 1292 objects round-tripped; page and feed served byte for byte);
  release_smoke linux64 1386 / win64 1385 managed files rehashed from the live feed.
- Wine smoke of the Windows stage: rc 0, engine c7f7135e1, Source and GoldSrc screenshots, eye 64 then 28.
- Linux game smoke of the Linux stage: 5/5. Its GoldSrc check was updated for P1687 (the eye follows the GoldSrc
  profile, 28 under the default AG modes, instead of the map's 17 and its "is a Counter-Strike map" line); the updated
  check fails 0.1.53's saved smoke log (eye 17) and passes this stage.

## Scope and limits

Automated checks only; owner check pending (lextest.md). Lobbies: worldofsurf-42 (was e3) deploys the matching lobby
qwprogs/csprogs after its gen1674 surfd generation. During the cut Lex's desktop compositor aborted (12:13 local, a
wlroots assertion as swayidle's idle lock started hyprlock); the build machine stayed up and no release step was
affected. Root `FTESurf-worktrees/release0154b-9e` keeps qc/dist, artifacts and inputs until the next release.
