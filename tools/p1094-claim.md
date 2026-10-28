# P1094 claim -- ftesurf-aa (Claude Code), 2026-10-28T17:45Z

A map Download pressed while this client hosts a local game waits for the game to end instead of
failing (the engine refuses downloads while sv.state is up). The pre-join path disconnects first.
Files: src/menu/m_main.qc (ui_dl_start, Dl_Tick, ui_dl_cancel, ui_prejoin_need, the list row).
