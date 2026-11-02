Patch 1209 claimed by ftesurf-e2 (Claude Code), 2026-11-02T09:39Z, at Lex's request (2 Nov): rename the
launcher to WOS-Launcher(.exe) everywhere (Lex chose the full rename). Launcher bin name; engine qkupdate.c
handoff prefers WOS-Launcher and falls back to ftesurf-launcher (installs keep their old copy: the launcher is
not feed-managed); release.ps1, bootstrap.ps1, linux-bootstrap.sh, linux-pack.sh, page template, ftesurf.bat/.sh,
updatefeed.py, tests. Reaches players with the next release.
Root: C:\FTESurf-worktrees\launcherver-20261102T0923Z
