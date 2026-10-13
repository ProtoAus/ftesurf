# Viewer HUD and controls — Patch 684

## Change

Playback keeps the user's configured HUD and adds the demo player; it does not
turn the board into a read-only display. Front modals own SUI's single hit list
and release queue. Playback chrome yields its bracket to the board, customizer,
graph or HUD editor, without stopping the recorded clock/camera. The native
board's front-input gate likewise permits the replay's background cursor claim.
This fixes actual line-checkbox and replay-row clicks, not just console twins.

Spectator save keys/binds use the transmitted target pose through the existing
`sl_saveview` snapshot path. They never save the parked body and do not grant a
recorded prefix. Ordinary native rewind still requires the server's own history.
Loads already release the viewer before applying the save. Spectate-to-playback
restores the old spectator pin before taking the replay pin in one server command.
Missing target velocity/pose data still refuses a save rather than inventing it.

Configured engine/custom crosshairs remain visible in viewed runs, and rewind
also draws the normal keys panel. Timer, speed, saves, map information and run
lines/graphs retain their own layouts and cvars. Analytical panels still require
their actual telemetry: another body's missing input/contact plane is not filled
with the parked player's data. No default HUD settings or held-body movement
protection was removed.

The demo player and optional info panel use shared Dusk surfaces, rounded chrome,
semantic colours, UI labels and a stable-width clock. The clock's Play/Pause
control is clickable. Mouse-down re-tests the current hit list so the first click
after opening/reflow is not lost while SUI's pointer is asleep. Existing seek,
speed, idle-skip, stage-cut and keyboard routes remain.

## Acting gate

Run from this checkout, with a new directory under an owned task root:

```text
python -B tools/viewer_ui_smoke.py --output-dir <owned-root>/subject
python -B tools/viewer_ui_smoke.py --output-dir <owned-root>/control --baseline e81efad7948821d3d4df38a1249bc7d0228d0bb9
```

The control is expected to exit nonzero at the new oracle, not during build or
runtime. Both arms compile exact source with identical measurement seams and
run two real clients against an isolated dedicated socket. Only synthetic rows,
poses and save roots are used. No install progs, configs or player data are swapped.
The script terminates only its own peer handle. Retained overlays/sources belong
to the caller and must be retired under the workspace lifecycle contract.

Checks: actual pause click, rewind HUD calls, editor/customizer opened during
playback, front-board gate, actual line/replay clicks, existing native rewind and
demo saves/loads, real peer spectator pose save (not parked body), no timed prefix,
load leaving spectate and exclusive server-pin handoff. Screenshots need inspection;
this tool does not call a returned frame a style approval. Public provenance below
contains summaries only; keep raw runtime logs and save artifacts private.

## Verification and limits

Baseline e81efad reproduces the removed HUD/modal/board/spectator restrictions.
Subject completes the same real socket sequence, with every positive control
acting, zero QC runtime errors and zero compiler warnings. The saved spectator
row matches the stationary target within two units, differs from the parked body
by over 50 units, is untimed (`tick -1`), and leaves spectate on load. A server
probe proves spectator/replay holds are exclusive after the handoff. Reader suite
remains 306/0; no recording grammar, receipt, verifier or movement rule changed.

1920-wide demo, board, spectator, rewind and editor screenshots were inspected.
The existing missing-map-material warning is unrelated and was not repaired by
this UI change. Owner acceptance at other scales, long names, imported recordings
and third/free cameras remains in lextest.md. No new engine binary, native tag,
QC Build-number or release is claimed.

## Development deployment — 2026-10-13

Product commit `ea284a017a17cbab159ee47712523aade4dd8f05`; engine changelog
commit `74bebd2a9842bf1298473e321dc008084f9ff219`. Both exact SHAs pushed to main.
A clean exact-product-commit QC build completed with zero warnings.

At 02:46:44Z both Windows installs received all three programs with six matching
destination hashes and verified `.prev` rollback files. Four protected owner/default
configs hashed unchanged. No native executable/plugin was replaced.

Guarded progs-only Pi deployment found all twelve lobbies empty, verified staged
and live hashes, kept the prior pair and restarted the twelve active units. The
02:49:49Z readback proves twelve active PID/matching UDP-socket actors, current
programs and retained rollback. Health and the fresh directory both list twelve.

| Program | Deployed SHA-256 |
|---|---|
| qwprogs.dat | f427438dff25d08bd4d08428c9b2a4882f7549b00044898f92e9ad165dd639b6 |
| csprogs.dat | 99744087bd1b56f01b5e1aac42e63beaf9edd31d09608556a827eef7afaaf0cc |
| menu.dat (Windows only) | f13f792cb416ff0752ce51c1ac2cd0520e462a0f9a7c314b18caae2492e407c1 |

Each installed Windows engine/menu pair separately joined the live lobby from a
fresh isolated client with no local CSQC. Both downloaded the exact deployed
client hash, drew a cols8/type14 board, captured a screenshot and exited normally
with zero QC/smoke errors. The screenshots were inspected. Owner game processes
were not stopped. Reconnect/map reload is needed for an already-running client
VM to pick up the newly served code; restart is the simplest local refresh.
