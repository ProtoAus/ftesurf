# P1116 claim -- ftesurf-aa (Claude Code), 2026-10-29T10:04Z

Stutter on finishing a map, Lex 29 Oct: measure the after-run input-journal upload (engine/client/cl_receipt.c:
whole-journal read and SHA-256 on the main thread, then a frame-polled POST) and move it off the main
thread; split the menu map table read (m_mapmedia.qc Mmm_TakeMeta) across frames. Evidence path: reviews.
