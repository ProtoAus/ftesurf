# Lex's third list of 25 Oct 2026: delivery (P1004-P1011)

Task root C:\FTESurf-worktrees\lexlist27-20261025T0530Z (owner ftesurf-7e). Arms in controls/,
outputs in artifacts/. Pre-batch control: FTESurf 2efede49 built in qc-control.

| Lex asked | Patch | State |
|---|---|---|
| resume view lock moves for a frame | P1004 | live; keys proved the pin holds through the count-in; the mouse needs a real hand |
| F1 on the results card gives the mouse | P1005 | live |
| rewind past the stage start on surf_kitsune | P1006 | live: whole run on full-track runs; server half an hour (slow rows) |
| 3 s countdown on the (rewind) resume | P1006 | live: his saved 0 was P784's one-day default; migrated to 3 |
| energy reports "E Line" | P1007 | live: the HUD's zero per sample |
| friends on the hud_player page in a private lobby | P1009 | menu list loads in any game now (engine); the in-game tab points to it -- a game cannot be handed the list safely (BACKLOG) |
| main-menu lobby chat in game | P1010 | live on linked lobbies ([everyone], team-chat key, TAB); menu chat screen reads in a game |
| "Armed" on the timer; re-arm at rest below 289 | P1008 | live |
| noclip, return, re-arm: continue untainted? | P1008 | answered: the attempt re-arms at rest (cheats off); a full run's noclip stays on it |
| styles auto-detected; KSF backwards demos? | P1011 | timer names the style; filing by style planned (tools/plan-styles-tas.md); 108 KSF bw replays imported |
| TAS category; can segmented/TAS be spoofed | -- | plan and answer in tools/plan-styles-tas.md |
| "check chat" though chat does not show | -- | his hud_chat is 0 (Chat panel off in hud_edit); not changed for him |
| "still checking" in the side window; drop F2 text and key; no "view locked" | P1004 | live |

Reviews: three lenses (predicate, evidence, attacker) on 2efede49..540ffde9; round 1 removed the
P1009 cvar bridge (it leaked the friends list to any server, and could not reach the menu) and the
menu chat's relay send (a server could take the text); rounds 2 and 3 integrity-only, round 3 clean.

## Deployed 25 Oct 2026 (UTC)

- 09:30:48Z surfd generation 906bfd78 (branch backend-gen-p1010 = 806d1484 + P1010 social.py), root
  /srv/nvme/agent-work/p1010-backend-20261025T0915Z; P996 root CLOSED and drained, stubs/run.sh/
  cron rebound (backups *.pre-906bfd78-*), momrequests.service moved. Health/lobbies/board 200.
- ~09:33Z both installs: ftesurf64.exe / fteqw64.exe c416c542 (git-7850-patch-1015-1-g96a77421f,
  .prev 5b8e3de0); hl2 plugin and fteqwsv64 unchanged.
- ~09:33Z build.ps1 -Pi from FTESurf cdd11471 (clean worktree): 12 lobbies and C:\FTEQuake,
  qwprogs 117c0942, csprogs 5c61096f, menu 069ec469; C:\FTESurf\ftesurf by hand, .prev kept.
- Lobby smoke 27520: served csprogs 5c61096f, board drew, no QC error.
