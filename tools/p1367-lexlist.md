# P1367 -- Lex's list of 7 Nov 2026

Root C:\FTESurf-worktrees\lexlist-20261107-3a (ftesurf-3a). QC + cfg/maps/map_ahop_coast.cfg; no
native change. Rig: isolated basedir (installed engine + hl2 plugin, install cfg/glsl, no
data/mapmeta.txt, like the Pi), driven by tools/conbridge.py; subject = this branch, control = the
same origin/main base, both built with fteqcc c24ede65, 0 warnings.

## Own replays: the view led the body by the player's ping

Cause: an own online replay pairs the board .rec with the player's staged .view (P814's
Watch_OnlineOwnView). Watch_ViewMap places each .view frame at `cltime - (cltime - ticks*tickrate)`,
and `ticks` is STAT_FS_TIMERTICKS as received -- a round trip after the command it counts. So every
frame lands one RTT early. Local runs (listen server) and the owner (Pi LAN) see 0; before t = 0
the .rec's angles are used, hence "flipped as soon as they leave the start zone".

Measured on the lobby's uploaded .views paired by runid with their server .rec (game/ftesurf/data,
read-only): best shift / mean |yaw| error at no shift -> at best.

| player | shift | error |
|---|---|---|
| Proto, proto (LAN) | 0 ms | 0.1-0.9 deg (unchanged) |
| nodsnot, Yesh M'Lord | 30-75 ms | 2.2-3.5 -> 0.2-0.5 |
| DRAGON, tsbussn, Glacier, linguini15 | 210-240 ms | 6.5-21.5 -> 0.04-0.36 |
| Markbeaton54, Akatosh, borobongo | 315-375 ms | 11-34 -> 0.09-0.74 |
| MetalGio, Bibs | 420-435 ms | 13.7-53.5 -> 0.11-0.63 |

The .rec, the board download (/api/replay) and the .view data themselves are sound: strafe
direction agrees with turn direction ~95% in every file checked, owner's and reporters' alike.

Fix: Watch_ViewLag, own online views only: 64 probe knots, shifts -2 ticks .. 1.2 s, yaw+pitch
error against the .rec's samples; a shift that beats none by 0.5 deg is taken out of every knot
and printed. `replay status` shows it.

Rig, Akatosh surf_ace 0:51.000 (board r41468, his uploaded view as the own cache):
- subject: "your per-frame view was 375 ms ahead of the recording (your ping); aligned (34.2 to
  0.1 degrees over 50 probes)"; `replay trace 500 0.1` vs the .rec: mean 0.08, p95 0.25, max 0.59 deg.
- control: no line; same trace mean 28.75, p95 89.38, max 160.01 deg.
- subject, Proto surf_pools 0:57.075 (LAN): "own online view: lead 0 ms taken out (55 probes)".

## Lobby rows left as "unnamed"

Cause: Lobby_Frame's colour pass walks classname "player", which a departed client's edict keeps.
In the 2 s zombie window forceinfokey lands; SV_ExtractFromUserinfo turns the emptied name into
"unnamed" and the engine sends it to everyone; nothing clears it. Fix: skip slots clienttype() does
not call REAL/BOT. Rig, two clients, B does `disconnect`, A at developer/log_developer 1:
- control: A logs topcolor/bottomcolor/tc/lc/lrgb for the empty slot, then `SETINFO : name=unnamed`;
  server logs 120 `PF_ForceInfoKey: inactive client` in 8 s.
- subject: A logs only the engine's own `*ann=` / `*vm=` clears; server 0.

## ahop_coast (reported as bhop_coast)

Teleport: its filter is filter_activator_name `"!player"`, compared literally with the activator's
targetname, so 23 trigger_teleports, 19 water resets and 34 trigger_multiples never fired. Source
(filters.cpp CFilterName, baseentity.cpp NameMatchesComplex): `!player` is any player, other names
NamesMatch (case-insensitive, `*` ends a prefix). Both server and client (cl_triggers TF_EvalD).
Rig, setpos into C0103_teleport's middle (-13957 4772 -13456): subject lands at the
landmark-relative -895 -15319 -12655.09 (server row); control stays at -13957 4772, falls to -13580.9.
Library census (2206 Momentum maps): "!player" 1 map (ahop_coast); `*` filters 29 maps (ng*, ng0*,
state0*: checkpoint systems); case-only matches 14 maps. Those filters never matched before.

Ruleset: the Pi has no data/mapmeta.txt, so `ahop_` gave mode ahop, which has no file: base ruleset
(Pi server12.log: "ahop_coast is ahop (name), base ruleset"). Momentum indexes it bhop (mode 2).
cfg/maps/map_ahop_coast.cfg carries mode_bhop.cfg's six lines. Rig without mapmeta: "100 Hz tick,
airaccel 1000", client "cl_netfps 66.6667 -> 100". Other maps with the same lobby/install split and
Momentum's missing uphill slope fix: BACKLOG.

## goto

`goto [spawn|start|main|sN|s N|stage N|bN|b N|bonus N]`; bare `goto` is spawn; goto_spawn kept.
Rig on surf_colin_blaster_69000, each answered by the server's own line: s3 "!s -- stage 3", spawn
and bare "goto_spawn: back at the map's spawn", b1/b 2 "!b -- bonus 1/2", main "!m -- start of the
map", start "!r -- stage 1", stage 3 = s3; `goto xyz` prints the usage line.

## surf_ferros materials

Not a game fault: luna_tag_0.mdl's two skins (lunatag2/ELDEN RING/NORMAL AND USABLE/AET001_0{20,78}_A)
are in no pack, no installed VPK (399 read, 1.24 M entries), no loose file and no map pakfile;
the message is right. No reporting channel added: mapdeps already predicts this offline.
