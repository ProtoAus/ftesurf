# P1438 -- point_worldtext drawn; Enable/Disable/Toggle/SetMessage

ftesurf-b8, 9 Nov 2026 (entgap-20261108, look-only group). Root C:\FTESurf-worktrees\xhair-20261108-b8
(tools/armse.sh, wtx1.cfg, wtx2.cfg, rigs/bm-wt*).

## What

- point_worldtext (560 texts on 24 maps, CS:GO / Momentum) drew nothing. src/client/cl_wtext.qc draws each
  unparented one from the lump: one cell of its font sheet per character, textsize square, advancing 0.6 x
  textsize along the entity's right from its origin at the bottom-left, readable looking along its forward,
  in its color. The sheets (CS:GO's editor/worldtextsheet, Momentum's editor/worldtextsheet_*) are 16 x 16 cells
  of ASCII 32-127 from the top-left (read off the decoded sheets). A font that does not load falls back to
  editor/worldtext, then Momentum's editor/worldtext_roboto-mono. Spawnflag 1 starts it hidden.
- Momentum's renderer is not public (its github "game" repo predates the Playtest engine and has no worldtext);
  the layout is read off the maps: bhop_bowling's "Round" then "1" and "LEVEL" then "1" leave 14-16 units of gap
  at 0.6; Momentum's training maps centre titles over subtitles at 0.45-0.56 and stack them cell on cell with the
  origin at the bottom; bhop_flything's "Runs started" and its four digits run along the right vector.
- A named one keeps its edict (SV_FxKeep) and, from its first input, sends its shown state and whatever SetMessage
  or AddOutput (message, color, textsize) changed on ENTWIRE_WTEXT 12 (SV_WtSend; WT_SET_* say which fields
  follow); Kill hides it for good. The library sends Enable 17, Disable 36, SetMessage 42 and AddOutput 7 to
  them (the reviewer's census; entgap's static scan saw only SetMessage): bhop_flything's run counter,
  bhop_2shiny2shuckle's stage countdown (AddOutput message), bhop_floodwaters' colours. Drawn when inside a
  75-degree cone round the view, within vbsp_sprite_dist and ~400 x textsize. vbsp_worldtext 0 hides them.

## Measured (client C:\FTEQuake\fteqw64.exe c61f874b; 0 QC errors)

- bhop_flything (build cs of build-nodeploy-3228b4bb), tools/wtx1.cfg: "worldtext: 20 of 20 point_worldtext
  drawn". "Runs started" over "0 0 0 0" reads left to right, not mirrored (rigs/bm-wt1-new q1); after
  `ent_fire runcount1 SetMessage 7` and `runcount2 SetMessage 3` the client logs both and the counter reads
  "0 0 3 7" (q2; 2246 px changed, the two digits).
- bhop_bowling (tools/wtx2.cfg, Momentum's Bebas-Neue sheet): "worldtext: 5 of 5"; "ROUND 1" and "LEVEL 1" read as
  the mapper placed them, the separate "1" a space after the word (rigs/bm-wt2-new q1, q2).
- From behind (wt1-new q3) the text is mirrored, as the font material's $nocull draws it. Control (P1433 build):
  no text (644 px between its two shots, the HUD).
- Review-1 build (build-nodeploy-fc2c66b3), bhop_2shiny2shuckle (tools/wtx3.cfg, the map's own lego font): "157 of
  157"; the stage-7 countdown reads "3", `AddOutput "message 2"` makes it "2", `AddOutput "color 255 0 0"` turns
  it red (rigs/bm-wt3-new q1-q3); named texts the map disables at start arrive before the load and are applied
  after it. bhop_flything's counter again "0 0 3 7" on the new wire layout (bm-wt4-new).

## Review

One round. Fixed: AddOutput (message, color, textsize) never reached the client -- 7 in the library, among them
bhop_2shiny2shuckle's countdown, so the wire gained WT_SET_* flags and the fields; no view-cone test and no
vbsp_sprite_dist, so the cost followed the map's glyphs (1436 on bhop_2shiny2shuckle), not what is in view; an
empty SetMessage leaked a zone string (freed now by a flag, as strzone("") compares equal to "").

## Delivery

- LIVE 9 Nov ~05:35 local: 12 lobbies (nobody on; warned; 0 QC errors) qw 145fca3c + cs cb462abf from main
  19849648; both installs the same (.prev 23bcf6b5 / 0fe650c4, .pre1438); csprogsvers b54dc279 on the Pi and both
  installs; codes.txt 105 -> 106 (.pre1438).

## Left

- Parented texts (19) are declined; texts behind walls in the view cone still draw (no PVS test).
