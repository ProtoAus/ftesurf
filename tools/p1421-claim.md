P1421 claimed by ftesurf-b8 (Claude Code), 8 Nov 2026: engine keeps the last 64 console lines in a fixed
in-memory ring (no disk, no per-line cost) and Log_Fatal writes them, scrubbed (typed commands and lines with
password/key=/token/secret dropped), into data/crash/error.txt at a Sys_Error -- P1418's crash report is built
from that instead of an always-on console log (P1418 review 1: an always-on log is readable by any server's
CSQC and costs a disk write per line). Root C:\FTESurf-worktrees\xhair-20261108-b8.
