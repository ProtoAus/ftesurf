# P1068 — one backdrop and consistent menu glass

## Owner defects and cause

The owner reported a square behind Settings, different backdrop coverage across
menu tabs, opaque menus after loading a map, a top-only highlight and excessive
transparency over the normal Milk scene. These are not inferred fixed by the
0.1.32 release or by the separate live API/native rollout.

Screen functions called `ui_backdrop` after `m_draw` pushed a shell coordinate
frame and substituted its panel-sized `screensize`. They darkened their own
rectangles. `sui_style_glass` was assigned from disconnected-only `MM_Active`,
so hosted/online contexts deliberately used opaque styling.

## Change

- `m_draw` draws the backdrop once in full-screen root coordinates before frames.
- Map-photo fallbacks remain disconnected-only; changing menu tabs cannot replace
  a live world with a selected-map photograph.
- MENU opts into glass in every context; CSQC/HUD's default remains opaque.
- Panels have a complete rounded rim instead of a straight top-only glint.
  Panel tint rises from0.56 to0.72; well/box tint also increases. These are draw
  factors, not a measured final composite opacity or blur/performance claim.

No native binary, movement, recorder, backend schema or account data change.
Native engine commit/tag remain P1066; `ENGINE.txt`'s product patch advances.

## Verification

Existing `build.ps1 -NoDeploy -Jobs8` passes: MENU and server zero warnings,
the same two existing client F333/227 warnings in untouched `cl_viewmodel.qc`.
The installed-control and subject were run with the existing
`test_ui_maps_runtime.Runtime` binary-stdin/log-ack transport. Settings and Maps
were exercised disconnected and on a real hosted `bhop_eazy`; eight native
captures, `client`/`active`/`glass` probes and error-free MENU/CSQC logs passed.
Actual image size was1920x1111 in both arms, not the1280x720 requested by startup
cvars (the existing native window sizing won). No additional resolution claim.
Control reports glass0; subject glass1 in both contexts. The Settings control
shows the large frame-sized square; subject removes that extra rectangle and
preserves a translucent rounded panel over the loaded world.

The stable visual fixture used offline consent and Milk disabled. An initial
transport attempt incorrectly used unsupported menu commands after map load;
its failure/logs are retained, not a product failure/pass. The corrected route
uses the existing native `togglemenu` command. The original attempt's synthetic
online fixture also caused Friends service requests; the final visual fixture
uses offline tier1 and does not claim authenticated API acceptance.

Evidence/source are retained in the session-owned menu task artifacts under
`artifacts/p1068-glass/`, with installed-control program hashes, command logs,
per-rig owner/PID/junction receipts and final `result.json`. Only owned children
were stopped and owned content junctions removed; owner processes/config were
not touched.

## Delivery / human limits

This menu-only delivery must preserve the currently installed native/QW/CS
cohorts and owner settings in both Windows installs. Lobbies never receive
menu.dat. Main-menu default-Milk readability and an actual online game's feel
still need the small owner check in `lextest.md`; no human pass is invented.
Map-record and WOS statistics remain a separate missing live API capability.
