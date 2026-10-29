# P1119 claim — tasrevd upgrade path (install_tasrevd.py upgrade mode)

Owner: Claude Code session ftesurf-8b (TAS task, root C:\FTESurf-private\worktrees\tas-20261026T162432z-pi).
UTC 2026-10-29T10:40Z. Max seen: P1118 (pi.dev session01a1861d).
Scope: tools/install_tasrevd.py gains a dry-run-default upgrade of the live TAS revision service
(new release dir beside the old one, exact old unit/snippet, unit swap, restart, probe, restore on
failure) and a test; then the release that lets tasrevd accept P1110's version 3 projects (Lex's sudo).
Root installer: one independent review before Lex runs it.
