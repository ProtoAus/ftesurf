# P1566 gfx panel, P1567 shared saves with their run -- delivery (15 Nov 2026, ftesurf-16)

Lex, 15 Nov: "convert my gfx_menu to a proper click and drag menu with clickable options ... previous and
next buttons, with readout of the option currently selected, maybe tooltips telling you the console command",
and for shared saves: "the player will have 'With help' status, and the whole segment made by someone else is
tagged as them, maybe a coloured display on the timeline of the demo ... Always send it with a run."
Task root C:\FTESurf-worktrees\lexlist2-20261115-16 (notes/ keeps the arm outputs and screenshots).

## What shipped

- P1566 (cab114b6, review 1 497fde6c): gfx_menu is a draggable window: six tabs, < value > per row with the
  value's list one click away, dots for fastest -> fullest, inert reasons, tooltips with the console command,
  Reload map / Close; UIC_GFX 16384; opens over a replay; digits no longer taken, Esc closes. Prop light row
  0 1 2 (the default 2 was unreachable).
- P1567 (fded0539; reviews b9f53563, 173d819b, 90a1bc15, f7edd6a1): `share save` copies the sender's state
  and run into the receiver's list (SV_SaveLocGift) with its own runid (gift date-time + receiver slot letter,
  same length); loading it sets TF_HELPED (bit 20) and writes `takeover <ticks> <name>`; FS_RunKindName "with
  help"; the lobby holds TF_HELPED runs from surfd until `lobby_helped 1`; SLOP_GIFT keeps the receiver's
  client sidecars out of the slot; the replay draws other players' spans with their names and the title names
  the last runner; reccheck learns `takeover`.

## Verified

- Build: 0 warnings in all three VMs at every step.
- tools/test_reccheck.py: 957 checks, 0 failed (case_takeover added).
- tools/p1567share.py (two clients + server, surf_dune, lobby saves): 20/20 on the delivered build (subject17);
  the control on the pre-P1567 build fails the gift checks (position-only row, class "segmented", flags 129).
- gfx panel in a conbridge rig: tabs, < >, the value list, drag (hud_gfx_x/y saved), tooltips, replay overlay,
  knife-panel refusal, Reload map, click-through past an open list, Tab board passes clicks on (screenshots in
  notes/shots).
- Reviews: P1566 one round (fixed); P1567 four rounds (control flow, evidence, cheater; then the fixes) --
  round 4 found no defect in the code.

## Delivery

- main f7edd6a1. Both installs (C:\FTESurf and C:\FTEQuake): qwprogs `b0d8b93c`, csprogs `cfde4c59`, menu
  `7833995c` (.prev `56f3a9ee` / `3ee01d54` = P1564's); lobby csprogs seeded as csprogsvers `6733132b`.
- build.ps1 -Pi at f7edd6a1: nobody on; 12 lobbies restarted, live qwprogs `b0d8b93c` / csprogs `cfde4c59`
  (previous pair kept as .prev), all 12 active, 0 QC errors since spawn (server1-12.log). tasrevd codes.txt
  140 -> 141 (.pre1567).
- tools/pi_lobby_smoke.py against 27510 (C:\FTESurf client, pinned csprogs): served cfde4c59, board drew, no QC
  error, screenshot -- PASS.

## Limits

- No "With help" board online yet: surfd needs a `helped` community style (80ca3c1e's TAS board is the
  pattern), then its guarded activation (owner authorization), then `lobby_helped 1` on the lobbies. Until then
  helped finishes are kept on the lobby and not posted; stages run wholly after a takeover still post.
- The sender's Segments list, run line and replay camera angles do not travel (BACKLOG, with the review
  leftovers). Owner checks: lextest.md "P1566 graphics panel / P1567 shared saves with their run".
