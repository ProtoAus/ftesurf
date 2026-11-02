# 0.1.36 — P1197-P1200 as delivered, with saved chat switched on

Published **0.1.36** on 2 Nov 2026 at 07:15Z, at Lex's request (AskUserQuestion "Release 0.1.36 + switch":
P1198-P1200's menu, with P1200's saved chat switched on in surfd at the same time, because 0.1.35's
menu tells players chat is not saved). 4 patch entries; see PATCHNOTES.md `## 0.1.36`.

## What shipped

The DELIVERED set, as for 0.1.35 (tools/release035.md):
- QC = origin/deploy/p1198-menu 3d50226d (= deploy/p1197-zonesnap 7bfe2807 + P1198-P1200 menu), live on
  the 12 lobbies and both installs. Frozen tree: tag v0.1.36 = 7c32702b (release/0136-20261102T0652Z)
  = main 575eb23e's tooling, docs and site with the 14 src files that differ taken from 3d50226d;
  src/build.ps1 and src/release/ stay main's. Stage: qw 6955e756 and cs bddd5081 = live; menu 9b2c6615
  = the installed 8bae5190 but for its version string (0.1.36 vs 0.1.33; the rest is shifted offsets).
- Left out (still under `## next`): P1169, P1161, P1154 and Collectors, as for 0.1.35.
- Engine release-0135 686d42014 unchanged: Windows outputs copied from 2b's release0135 build (exe
  6c86dfb5 = 0.1.35's), Linux drop linux-build-0135 (BUILDINFO gates PASS, glibc 2.29 <= 2.35).
- Launcher 646c8d1 (origin/main). Data: mapmedia_refresh found nothing new; the same 657 zones as
  0.1.35 (sha1 lists identical); 680 allowlisted assets copied from the dev install (populate-assets.py).
- surfd: P1200 generation ac283934 (fix/chat-1200 = 0d72a27c + 4 commits, only social.py in the
  pinned closure) live at /srv/nvme/agent-work/chatsave-1200-57e27fa4 since 07:10:16Z, swapped at
  0 players through 2b's P1189 kit (root/owner/generation seams only; reservation taken and released).
  Fallback: 0d72a27c CLOSED in that root's control/. Checks: empty POST /api/hid 413, data/evidence rw,
  maps=1 equal before/after, no errors, heartbeats flowing.

## Evidence

- Prepared SHA256 `323b52c6037c7e64c3669ffaffa9c7c18f1a2bd59fec0d80d9f88f8d74a25d8a`; receipt
  `b5a96bbfb81962eb27fccb4a334b1bfce607db5e657c5ccfdfd779308d5f207b`.
- Windows `ftesurf-0.1.36.7z` 57.5 MB, sha256 `dc6b7b29f82a22960da04cd972eba47348ab97cdf61369d08bdb0a2ee3d5e64e`.
- Linux `ftesurf-0.1.36-linux-x86_64.tar.xz` 57.5 MB, sha256 `9adbbdd3e69e604dd8f82b73bfdda2933637aebe83247e9205b216842cff763b`.
- One prepare, one -PublishPrepared -DryRun, one -PublishPrepared -VerifyFull -Tag: 790 objects
  round-tripped, both launchers, archives, page and no-cache feed byte for byte.
- release_smoke: fresh default-HTTPS installs, Windows 882 / Linux 881 managed files rehashed, 3
  sentinels each, no game launch.
- The menu's behaviour was measured before the release on owned rigs against a real surfd with
  synthetic data (profiles-20261102/artifacts/p1198arm.py: 25/25; the 0.1.35 menu 4/22).
- Not claimed: in-game play by a real account, Linux desktop acceptance (lextest.md).

## Notes

- Players still on 0.1.35 see "Recent messages expire after two minutes; not saved" until they
  update, while surfd saves; the 0.1.36 menu words its note from the server's `keep`.
- Task root: C:\FTESurf-worktrees\release0136-20261102T0652Z (OWNER.md, artifacts/, qc/dist candidate).
