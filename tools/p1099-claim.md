# P1099 claim -- ftesurf-aa (Claude Code), 2026-10-28T20:10Z

Menu + Pi: the menu fetches mapmeta.txt and mapdeps.txt from play.proto.bar/ftesurf/media/ once a
session and draws a map's small JPEG from there when no local atlas page holds its cell.
src/menu/m_mapmedia.qc (new), m_main.qc, m_lobby.qc, m_progs.src; publish step in
tools/mapmedia_refresh.py; an nginx snippet for Lex to install.
