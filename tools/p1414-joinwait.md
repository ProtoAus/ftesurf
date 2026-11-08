# P1414: the join wait at high ping (8 Nov 2026, ftesurf-3a)

Player report via Lex (~400 ms to Australia): asking for a map no lobby runs changes a lobby's map, but
the game says the change was unsuccessful and never connects; asking again connects.

- Cause (src/menu/m_lobby.qc): during LJ_WAIT the menu polled lobbies.json every second and dropped
  any reply whose id was not the newest (Lob_URIReply, `reqid != lb_req`). A fresh HTTPS request at
  400 ms takes ~2 s, so every reply was stale and LJ_WAITCAP (20 s) expired: "the server never came
  live ... playing locally". A retry finds the lobby live and surfd answers "ready".
- surfd log 8 Nov: lobbies came live 11-13 s after the ask; the 186.x (South American) asker arrived
  49 s after, i.e. after a failed wait and a manual retry.
- Fix: one lobbies.json poll in flight (lb_sent, LB_INFLIGHT 10 s); LJ_WAITCAP 45.
- Arm tools/p1414joinwait.py (directory holding replies 1.5 s, switch at 12 s): control (main's
  menu.dat) failed at 21.5 s; fix live at 13.2 s.

Delivery: main 571ad70f; menu.dat 74f7f8c5 in both installs (8 Nov). menu.dat is local to each
client, so players get it with the next release; lobbies need nothing.
