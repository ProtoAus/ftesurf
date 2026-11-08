# P1417 + P1421 + P1418 -- crash guard, the engine's crash record, crash reports

ftesurf-b8, 8 Nov 2026. Root C:\FTESurf-worktrees\xhair-20261108-b8 (engine worktree eng/, arms in tools/).

## Why

MetalGio (8 Nov): "BZ_Malloc: Failed on allocation of 18446744071578836992 bytes" on every story-mode map switch
while downloading. That is 0xFFFFFFFF80FFE000: FS_LoadMallocGroupFile held a 64-bit file length in an int, so a
length of 0x80FFDFFF reached BZ_Malloc sign-extended. tools/guardarm.py reproduces the dialog exactly with a
dedicated server loading a sparse 0x80FFDFFF-byte map. No map in the library (largest 518 MB) or the download
catalogue (343 MB) is near 2 GB, so his length came from a broken archive or VPK entry.

## What shipped

- P1417 (engine, patch-1417): both loaders refuse a length past 2 GB with "<file>: reports N bytes; not
  loaded"; VPK entry sizes unsigned; Log_Fatal writes Sys_Error's text to data/crash/error.txt.
- P1421 (engine, patch-1421): Con_Log keeps the last 64 console lines in a fixed array; Log_Fatal adds the
  engine version and those lines, without typed commands or lines naming a password, key=, token or secret.
  tools/tailarm2.py (fault injection: the guard compiled out) shows the record: error, engine, 17 lines, no
  secret line. A dedicated server's missing map leaves none (SV_Error shuts the filesystem down first).
- P1418 (QC): the menu copies error.txt into data/crash/report_<utc>.txt at m_init; on a server with
  serverinfo fs_crashrep the client offers it once (offered.txt when first drawn); F6 alone sends it;
  crash_send only opens the box; ui_crash_report 0 offers nothing; the lobby stores it in data/crash/ under its
  own header. tools/p1418arm2.py: a stuffcmd'd crash_send twice stores nothing; F6 (a window message) stores
  it; no second offer; a later crash_send finds nothing.

## Review

- P1418 review 1 (of the first design) refused an always-on console log: a server's CSQC can read it, and it
  costs a file write per printed line (AGENT_NOTES: 4-6 ms). It also found the crash_send consent bypass (two
  in one stuffcmd), a missing send timeout, and an offer used up while hidden. All four changed the design:
  P1421's in-memory tail replaced the log, F6 is the only send, a 10 s timeout, offered-on-draw.
- Review 2 (of the redesign): the three findings fixed; four low ones, three fixed -- fs_crashrep only on a
  lobby (cvar lobby_enable), so a player's own game joined by address takes none; a sent report is overwritten
  with "sent <utc>"; the lobby stores each client line under "| " (chat could say "== end"). Left: a final ack
  that lands after the 10 s timeout leaves the report unlisted in sent.txt (it can be sent again).
  tools/p1418arm2.py as a lobby: as above, plus the "| " lines and the "sent" stub; as a plain server
  (nolobby): no offer, F6 does nothing, crash_send says "reports go to a lobby that takes them".
- Known and left: a server can stuffcmd ui_crash_report back to 1 (QC cannot register a server-proof cvar);
  a server's own CSQC can read data/ files anyway, so the consent box guards the honest path, not a hostile
  server.

## Delivery

(see the commit that records it)
