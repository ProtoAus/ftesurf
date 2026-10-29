# P1101 claim -- ftesurf-aa (Claude Code), 2026-10-28T23:05Z

Engine + menu: rec_terms (the menu's consent mirror) becomes an engine cvar with CVAR_NOTFROMSERVER, as
rec_upload/rec_hid_upload already are, so a server cannot switch consent on; the menu sets it with
localcmd_local. Files: engine client cvar, src/menu/m_main.qc.
