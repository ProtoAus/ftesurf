# ROADMAP.md — maps, demos, run lines and rewind

Lex's requests of 4 Oct 2026, read against the code as it stands (three surveys
of the menu, the line and replay code, and the KSF/Momentum/Pi data paths), with
what to build, in what order, and what needs a decision. Work happens on branch
`feat-maps-demos`; Patches 477 (rewind) and 478 (ghost) ship first.

Each item: **Today** (what the code does, with pointers), **Build**, **Unknowns**
(measure before promising), **Size**.

**Status, 4 Oct night** (merged into main and live):
- done: 2, 10, 1 without the engine's download cancel, 9;
- 7: both tiers kept end to end, a mapmeta row for every KSF map, KSF's
  pictures (`tools/ksfshots.py`, run once by hand), and a row draws KSF's tier
  under Momentum's ("KSF 2"); the tier chips and the sort still use one;
- 3: done except ramp contact. `tools/momreimport.py` rewrote 5,260 of the
  5,281 imported runs from their own demos (angles, velocity, ground, duck,
  jump, keys and moves; stages numbered as ours), live on the Pi since 4 Oct
  09:31 UTC. A .mtv records no ramp contact (BACKLOG: infer it), and two key
  cases are still wrong (BACKLOG, "Two cases the re-import's keys still get
  wrong"). 20 runs have no demo here and 1 the decoder refuses;
- 6: a row names the games it needs ("needs TF2 CS:GO"), red where this PC lacks
  one, from `data/mapdeps.txt` (rebuilt 4 Oct: 560 needs, 419 maps) and engine
  Patch 480's `fs_addonstate`. An engine without 480 (0.1.21's) draws the names
  dim. The filter chip is not built;
- 11: a first scan ran over the 7,177 Momentum demos on Lex's PC (4 Oct): none
  was worth a look, 1,322 too short to measure. Method, limits and the report
  are in the private repo;
- not started: 8.

**5 Oct** (Lex answered decisions 1 and 2: fill KSF over time; fetch the
demos we do not have):
- 4: `surfd/momgrab.py` on the Pi's crontab fetches the demos of every
  board's top 10, maps people view first, and files them watchable. Automatic
  only -- the per-row "Get demo" button is not built (BACKLOG).
- 5: `surfd/ksfimport.py --watch` on the Pi's crontab pages every KSF board to
  its end, a few requests a tick, maps people view first; KSF's four styles
  (Forward, Sideways, Half-Sideways, Backwards) are boards of their own, and
  the website tabs them. Stages and bonuses were already imported. The game's
  board has no style picker yet (BACKLOG).

---

## 1. Download and connect status under the map list

**Today.**
- A download starts in `ui_dl_start` (src/menu/m_main.qc:4986) through the
  engine's `downloadmap` builtin; progress is polled every frame from
  `serverkey("dlstate")` by `Dl_Tick` (m_main.qc:5023) into the `dl_*` globals.
  The only display is a 6 px bar in the map's own row (m_main.qc:5915-5928) --
  no percent, size or time left, nothing once the row scrolls away. There is no
  cancel: the engine's `curl --cancel` prints "not implemented"
  (engine client/cl_main.c:5321). One download at a time.
- Choosing a map runs `ui_launch` -> `Lob_JoinAsk` (`/api/join`) ->
  `Lob_JoinPoll` (8 s for an answer, up to 20 s for the lobby to switch) ->
  `ui_prejoin` (download first if missing) -> `connect`; any failure falls back
  to a local `map`. All of it reports to the console only, and ESC on the map
  screen does not cancel it (`ui_join_cancel` runs only from `m_close`).

**Build.**
- A status strip under the map list (the footer between start and back), one
  line per phase, each with **Cancel**: "Downloading surf_x -- 42% · 18.3 of
  43.5 MB · 2.1 MB/s · 12 s left", "Finding a lobby…", "Switching lobby 3 to
  surf_x…", "Waiting for surf_x on lobby 3 (12 s)", "Downloading surf_x before
  joining…", "Starting a local server…", and the failures ("lobby busy --
  playing locally", "download failed"). A small toast keeps it visible on other
  screens.
- Cancelling a join: ESC/Cancel calls `ui_join_cancel` and clears the held
  join (`pj_*`). Menu QC only.
- Cancelling a download: an engine patch that aborts the disconnected HTTP
  download (the Patch 465 path, client/cl_parse.c:2013-2032 -- close the
  handle, delete the .tmp) and a way for the menu to ask for it.
- The menu's shader: drive `MM_Camera` (src/menu/m_milk.qc:790-801) from
  `dl_pct` and the join phase -- the PLAY station's world charging with
  progress (zoom, decay, hue), a flash on completion, a stall pulse on an error.
  The `M_EVENT.z` uniform slot (src/milk_sys.qc:370) is free to carry it.
- Optional: a menu loading screen (`m_drawloading`, looked up at
  client/pr_menu.c:3495 and not defined today) so the status survives the
  map load.

**Size.** Medium in QC; the engine cancel is small.

## 2. Line thickness

**Today.** One cvar, `hud_watch_path_px` (pixels, default 1), sets every line
at once (src/client/cl_lines.qc:1213 -> `ln_wpx`), and hud_edit has no row
for it (src/client/cl_hudedit.qc:620-678, "Run lines" rows 0-24).

**Build.** Three thicknesses, one per kind of line: the replay you are
watching (slot 0, `Watch_Path2D`), the leaderboard runs you tick on to show
while you play (slots 1-8, `Scores_LinesDraw` in cl_scores.qc), and your own
live run line (slots 9-10, cl_trail.qc). `Line_Draw` takes a per-slot width
instead of the single `ln_wpx`. Three hud_edit rows under Run lines -- thin /
normal / thick / heavy. Client only.

**Size.** Small.

## 3. Momentum demos: real buttons and mouse, accurate marks and labels

**Today.** Momentum's replay files (`.mtv`) are never parsed in this repo. An
outside extractor wrote positions only, and `tools/momimport.py` derives pitch
and yaw from the direction of travel, takes velocity as a central difference of
positions, and writes zeros for keys, flags and moves -- in all 16.6 million
imported samples. So:
- the mouse pad (`MPad_Frame`, cl_mouse.qc) draws the velocity turning, not
  the player's hand;
- a mid-air crouch moves the origin 8.5 u, which the central difference turns
  into a +-283 u/s vertical spike and a 5-45 degree pitch jab -- 44,593
  two-sample spikes in the corpus, 95% of them an 8-9 u step;
- touching a ramp bends the velocity within a tick, so yaw and pitch jump there;
- the key display stays dark, there are no touchdown/take-off/jump marks,
  "colour by contact" is all grey, and the labels read the spiky velocity;
- stage imports read one stage late: momimport writes `startseg = leg`
  (momimport.py:297) where FTESurf writes `leg - 1`.

**Build.**
1. `tools/momreplay.py`: a parser for Momentum's replay format written from
   Momentum's open game source (header, then per tick: eye angles, position,
   view offset, buttons), checked against real files (the header's hash is
   the map build).
2. momimport writes the real columns: view angles; the key mask from Source's
   button bits (forward, back, strafes, jump, duck, turn -- the bit layout
   differs from FTESurf's); ducked from the duck button and view offset; the
   jump flag; velocity from position deltas with the duck offset taken out;
   ground and ramp contact inferred (vertical speed and jump presses, or a
   trace when the map is loaded).
3. Re-import the corpus from the `.mtv` files and re-index it on the Pi.
4. Fix the stage off-by-one.
5. The viewer then lights the keys, draws the real mouse, and places marks and
   labels as it does for our own runs.

**Unknowns.** Which `.mtv` versions the corpus holds, and whether every file
carries view offsets and buttons.

**Size.** Large but mechanical once the format is pinned.

## 5. KSF past 25 places

**Today.** Nothing in our boards stops at 25: the in-game board pages to
1,000 rows (cl_online.qc `OB_PAGE`/`OB_MAXROW`), the website pages 50 at a
time, and surfd's `/api/board` takes an offset. KSF's own pages are 20 rows;
the import reached ~40 ranks on most maps (the map path defaults to 100 rows a
board, the player-seeded path takes 25 per player). On the Momentum side
`momfetch.py --take` still defaults to 25 (the Pi's momwatch asks for 100).

**Build.** (a) A deeper import -- `ksfimport.py --from-maps --depth 500`, run
by hand as always. (b) Optionally, when a player scrolls past the KSF rows we
hold, the Pi fetches the next 20-row KSF page for that board on demand
(rate-limited, cached).

**Unknowns.** Which screen showed 25.

**Size.** (a) a command; (b) small-medium.

## 6. Which games a map needs, and which you have

**Today.** `data/mapdeps.txt` (545 `dep <map> steam:<game>` lines, from
`tools/mapdeps.py`, last built 12 Sep) is read only by the engine when a map
loads (`FS_AutoMountForMap`, common/fs.c). The menu knows only which install a
map came from (the MOM/CSS label), and no builtin says which Steam games are
installed or mounted.

**Build.** Rebuild mapdeps.txt over every map (the Pi-only ones too) and ship
it; the menu reads it; a small engine builtin answers per game -- not
installed, installed, mounted (from `FS_Addon_ResolveEx` /
`FS_Addon_IsMounted`). Each row shows the games it needs as badges, lit if you
have them; the detail line names them; a filter chip shows only maps you can
draw fully, or only the ones missing something.

**Size.** Medium, one small engine patch.

## 7. Every KSF and Momentum map, both tiers, every thumbnail

**Today.** Momentum maps, tiers and thumbnails come from the local Momentum
install's cache -- `approved_*.dat` and `submission_*.dat`, so beta and
unlisted submissions are already in (tools/mapmeta.py, tools/msml.py) -- with
images from `cdn.momentum-mod.org/img/<uuid>`. KSF maps come from the KSF
sheet (`data/ksf_roster.csv`) with their tier, but `maproster.txt` keeps one
tier (Momentum's, else KSF's), so the KSF tier is lost downstream: surf_whiteout
is Momentum 2 / KSF 1 and shows 2. Beta maps show unrated on the website.

**Build.**
- Keep `mtier` and `ktier` apart end to end (maproster, mapdl.txt, mapmeta,
  the website) and show both: "T3 · KSF T2".
- A completeness audit: the KSF sheet and Momentum's lists against what we
  list; fetch every missing thumbnail (Momentum's CDN; for KSF-only maps,
  ksf.surf's images if it has them); rebuild the atlases (`tools/mapthumbs.py`)
  and the website's shots.

**Unknowns.** Whether Momentum's public API lists maps the local cache does
not; whether ksf.surf exposes map screenshots.

**Size.** Medium-large, mostly data.

## 8. One row per map, with a Momentum / CS:S toggle

**Today.** Duplicates already merge into one "MOM CSS" row
(m_main.qc:2184-2250), but which BSP loads is decided by the mount order
(`ftesurf/maps` > Momentum > cstrike); the Pi serves one build per name; zones,
boards and the `mapbuild` hash key on the name.

**Build.** Per map, a list of builds with their hashes; a toggle on the row --
"Play: Momentum | CS:S", remembered per map; loading a chosen build needs a
variant path the engine loads under the map's own name (for example
`maps/variants/<name>@css.bsp`), zones per build (KSF's for the CS:S build,
Momentum's for theirs), boards keyed by build (the existing mapbuild hash), and
surfd's `/api/join` and the Pi's map store carrying the build.

**Size.** Large: engine, server, surfd and data.

## 9. Leaderboards on the map screen

**Today.** None in the menu; the in-game board needs a loaded map
(`serverkey("map")`). surfd's `/api/board?map=&tier=ksf|momentum|ranked|imported`
already serves paged rows.

**Build.** A "Leaderboard" button on the selected map opens a panel with KSF /
Momentum / FTESurf tabs -- rank, name, time, date -- loading more as you scroll.
The menu's web replies share one callback (src/menu/m_lobby.qc:885), so they are
told apart by request id.

**Size.** Medium, menu QC only.

## 10. Maps with full data first

**Today.** Sorted by tier only, untiered last, installed before downloadable
(`ui_refilter`, m_main.qc:2446).

**Build.** Rank by completeness first -- thumbnail, tier, zones, records --
then by tier; maps without a thumbnail sink to the bottom and show in full only
while searching or with a "show all" chip.

**Size.** Small.

## 11. Scanning Momentum demos

Once (3) gives real per-tick angles and buttons, Momentum demos can go through
the same input analysis our own runs get, as far as their data allows, and
flag records to look at. How it detects lives in the private anti-cheat plan,
not in this public file.

---

## 12. Run-line and rewind overhaul — Lex, 7 Oct 2026

**Status: incremental delivery; the full overhaul is NOT implemented.** P535
implements the main rewind cursor timer/speed/energy, removes its duplicate
readout, adds fractional visual motion without changing sampled save state, and
adds bind-resolved held strafe scrolling for live rewind. P544 adds bare-bind
held demo scrolling; P550 closes live rewind opposing-key cancellation and
P554 adds live focus cancellation with retained physical ownership.
Compound/modifier binds, full device/focus acceptance,
stitched diagnosis, event browsing, imports and real comparison remain below.
These requests
supersede treating rewind as a separate little time/speed readout. Keep the
reported defects in BACKLOG.md until their falsifiers pass. The chunk reveal
and nearby-player dither fades requested earlier are implemented separately
by Patch 532; they are not proof that this overhaul has shipped.

### 12.1 One cursor state for the main HUD

P535 delivers live-rewind main timer/speed/energy and duplicate-readout removal.
`e line` uses recorded start energy; missing velocity is explicitly unavailable.
P549 aligns the demo main clock and full-demo chrome to the fractional visual
cursor, retaining sampled ticks for events/splits. This bounded display fix does
not complete broader source/HUD, imported-camera or human acceptance.

**Build.** During player-line rewind and demo-line inspection/rewind, the normal
**timer, speed/units and energy displays** show the exact same cursor sample as
the viewed body/line, including fractional interpolation. Remove the duplicate
rewind time/speed readout; retain only useful controls and an unmistakable
"rewinding"/source indication. Timer is cursor run time, not the advancing live
or wall clock. Speed honours the existing units/speed mode. Energy uses the
cursor position and full velocity with the source's gravity/reference; derived
energy history/rate must not combine cursor samples with the stationary live
body or stale history. Leaving rewind restores live HUD state and histories.

**Sites.** `cl_rewind.qc:Rewind_Cursor/Rewind_Draw/Rewind_Camera`,
`cl_trailstate.qc:Trail_CursorState`, `cl_hud.qc:HUD_DrawSpeed/HUD_EnergyRef` and the
clock in `cl_main.qc`. Reuse a shared visual cursor snapshot; do not change the
server's frozen timer/recording or create an alternative evidence clock.

**Acceptance.** At first/middle/last/fractional cursor positions, main clock,
speed and energy agree with the displayed pose and source sample. Hold still:
all cursor readings stay still. Scrub both ways, cancel, resume, countdown and
switch between demo/player lines: no live-HUD leakage or stale energy rate.

### 12.2 Strafe binds also scroll rewind

P535 delivers bare-command binds for live rewind; P544 adds them to demos.
Demo taps move one recorded tick; holds accelerate, opposing left/right cancels,
and same-direction presses remain independent. Physical ownership survives
rebind/close/reopen. Arrows keep 5s jumps; primary mouse buttons remain chrome's.
Private dedicated controls at 30/100/300 prove whole-chain navigation and a
stationary pinned body. P550 makes live rewind cancel opposing owners as well;
either release resumes the remaining side and same-side owners stay independent.
Native selection and save/resume are unchanged. P554 cancels activity, not
press ownership, on chat/menu/console or keyboard-focus loss: return/repeats
stay stopped until release/fresh press. Whole-chain controls pass at
30/100/300 FPS and both installed clients. Compound/modifier binds,
actual-device/OS focus delivery and human smoothness acceptance remain open.

**Build.** `+moveleft` scrolls backward; `+moveright` scrolls forward, alongside
the existing controls. Resolve the player's binds, not literal A/D keys. Held
keys accelerate smoothly; release stops, opposing keys cancel, and a quick tap
allows fine positioning. Browsing must continue to suppress real movement.

**Sites.** `cl_rewind.qc:Rewind_MoveBind/Rewind_InputEvent/Rewind_Frame` and
`CSQC_Input_Frame`. The movement gate already recognises these binds; that is
NOT proof that they currently drive the cursor.

**Acceptance.** Default and remapped keys, simultaneous presses, repeats,
chat/console/menu focus, opening while a strafe is held, focus loss and closing
rewind with a key down leave neither unwanted motion nor a stuck scroll/key.

### 12.3 Smooth stitched rewind, without failed-attempt idle tails

**Reported.** After several rewind cuts, scrolling reaches a stationary,
zero-speed stretch while time continues, then the body jolts forward. Captured
failed-attempt/hold time is a hypothesis, not a confirmed root cause.

**Build.** Reproduce and trace raw cursor samples, publication/trim boundaries,
retained prefix, loaded pose and each stitch's visual time/index mapping. Remove
abandoned tail/hold samples from the browsable stitched continuation if they
are incorrectly retained. Use a consistent continuous visual timeline and
fractional position/velocity/camera interpolation on each continuous span;
acceleration/deceleration should feel smooth in either direction and at several
frame rates. Do not paper over a bad splice by smoothing a teleport, invent
movement through walls, or rewrite authoritative recording/save times. Genuine
recorded stops stay distinguishable from synthetic gaps; real teleports and
incompatible stitches remain explicit discontinuities, never interpolation
across unrelated attempts. This is display/history repair, not evidence retiming.

**Sites.** `cl_rewind.qc:Rewind_Cursor/Rewind_Frame/Rewind_Camera`,
`cl_trailstate.qc` raw history/restore/trim, `cl_trailreplay.qc` replay/rewind
prefixes, and `cl_lines.qc` point/break
indices. Preserve Patch 502's lineage, hold, save acknowledgement and timed-go
contracts.

**Acceptance.** Three or more cut/resume/fail/rewind cycles, warm and cold saved
prefixes, with a deliberately long wait after a failure. No leaked wait, timer
creep at a fixed cursor, zero-speed plateau or unexplained jolt. A genuine pause
and a teleport are positive controls. P502 dedicated warm/cold/held-clock arms
must still pass. Moving-camera feel needs Lex's acceptance, not just a numeric
interpolation test.

2026-10-07 controls: P539 repairs the cold recorder-attachment boundary;
streamed/buffered six-cut native body/clock/prefix/refusal controls pass at 100
FPS. P540 repairs raw break/stitch velocity/view interpolation and chase
camera tangents crossing unrelated spans. Compiled discontinuity controls and
both-camera quarter-point traces pass at caps 30/100/300, preserving genuine
counted stops. Full six-cut controls also pass streamed at 300 FPS. At 30 FPS,
two requested-prefix arms remained red with 45 ms endpoint differences;
the unchanged P539 baseline reproduced both exactly. P542 distinguishes the
0.735 native selection from its incorrectly shortened 0.690 visual prefix:
normalize only the visual cutoff through the raw six-decimal representation.
All six requested/native/prefix controls pass in new buffered 30/100/300 and
streamed 30 matrices, without widening the requested-clock check. The original
forward 45 ms native selection and general requested/native UX remain separate
follow-ups (BACKLOG). A fresh P554-source audit confirms thirty local native/
acknowledged-prefix choices across caps 30/100/300, streamed/buffered30 and the
second installed client. Three warm/three fresh-cold cuts remove deliberately
counted >4s failed waits and exclude held time. A configured/read-back 30ms
packet-delay arm reproduces strict requested-clock red results (+60/+60/+45ms)
while native-ring selection, native held body/clock, exact acknowledged prefix,
hold/release and camera/discontinuity checks pass. This isolates a clock/pose
alignment or presentation contract, not another raw trim boundary failure.
No native/evidence retiming or widened oracle; general UX/feel remain open.
Native-event tooling after P542 additionally checks
engine-driven keep/zero-velocity teleport volumes on actual map ground, a
genuine six-second running stop and a fixed cursor over elapsed wall time.
Complete 30/100/300 FPS camera-state scans, nine compiled controls and 39
counterfactual checks pass. Synthetic-volume coverage is not authored BSP
teleport coverage; saved images alias despite distinct camera state. Camera
pixels/feel and the broader reported event/compare acceptance remain open;
numeric traces do not settle them.

### 12.4 Contact labels at the actual surface event

**Build.** Audit native "off ramp" placement against the mover's actual contact
loss tick and hull/plane, not just proximity of the player's centre to a ramp.
Keep the raw event separate from the held contact used to stabilise HUD/board
classification. `Line_Contact` currently uses `Board_RampHeld`; that can delay a
visual edge, but measurement must establish which delay Lex is seeing. Place
entry/exit labels on the correct adjacent samples (or a justified interpolated
contact crossing), independent of render batching, LOD and frame rate. Do not
"improve detection" by fabricating collision truth from a line's appearance.

**Acceptance.** Slide off a known brush ramp edge; compare actual per-tick raw
contact/normal, held kind and final event time/position. Include ramp-to-air,
ramp-to-ground, curved ramps, displacement/prop ramps, grazing contact and a
teleport. Contact labels stay aligned at several tick/frame rates and LODs.

### 12.5 Momentum demo labels: coverage and honest provenance

**Today.** The re-imported demos now carry much more than positions, but the
existing BACKLOG item "Re-imported Momentum runs read every ramp as free air"
still applies: `.mtv` has no authoritative ramp-contact bit/plane. Do not treat
missing contact as measured free air, and do not call inferred labels exact.

**Build.** Audit native and imported metadata/label availability separately.
Derive reliable timing/velocity/energy labels from available samples, with
correct duck-origin handling, tick cadence, stage windows and source map build.
Evaluate map-matched hull tracing and/or validated velocity/contact inference
for missing surface events against native runs with known contact truth. Mark
inferred or unavailable contact explicitly. Native, imported and board-line
views of the same data must agree; no invented authoritative flag/normal and
no silent corpus rewrite. Re-import/version migration is a separate measured
step if the eventual fix needs stored metadata.

**Acceptance.** Known native ramp/air controls, Momentum ramps/apexes/ducking,
old formats, sparse data and mismatched map builds. Show what is measured,
inferred or unavailable, with identical event times in all viewer modes.

### 12.6 Apex and ramp-bottom speed/energy labels

**Build.** Show **time, speed and energy at vertical-velocity reversals**:
ascending -> descending is the airborne high point; descending -> ascending
is the trough/bottom of ramping. These are height extrema, not necessarily
extrema of speed or total energy. Label the values AT the reversal, interpolate
between the bracketing samples when justified, and debounce near-zero noise
without losing slow genuine reversals. A trough may lie on a ramp or coincide
with a contact transition; it must not disappear just because the current
classifier's reversal branch only runs in `SEG_AIR`. Respect teleports/stitches.

**Today/sites.** `cl_lines.qc:Line_Point/Line_Marks` already has airborne apex/
trough events and a 40 u/s gate; `hud_lines_nums 1` defaults to contacts only,
while 2 adds peaks. Audit those existing behaviours rather than starting a
second classifier or declaring all peak detection absent. Make the requested
labels discoverable and enabled in the delivered normal/demo line experience,
with density/visibility controls.

**Acceptance.** Air apex, ramp trough, reversal at a contact transition, slow
reversal, several near-zero jitter ticks and teleport/stitch controls. Numbers
match the same interpolated time/position/velocity/energy, on native and
Momentum demo lines, without duplicate or arbitrary "peak velocity" labels.

### 12.7 Live nearest-fastest-line pace comparison

**Build.** While running, find the corresponding point on an eligible fast
reference line near the player's route and compare **moment by moment**:
run-time delta (ahead/behind), speed delta and energy delta. Name the reference
player/run and retain a visible cursor on that line. This is spatially aligned
pace coaching, NOT comparison at equal elapsed times and NOT the leaderboard's
current "compare" chip. Establish whether existing split/PB pace code can be
reused; do not claim continuous nearest-line matching is already built.

**Matching contract to implement and measure.** Same map build, track/stage,
route/window and compatible run class; choose the fastest eligible reference,
then match a plausible nearby segment with temporal/order continuity. Spatial
nearness alone must not jump to another lap, crossing, nearby ramp or a future
stage. Keep reference identity stable with bounded search/hysteresis; only
switch at meaningful boundaries or an explicit user choice. Exclude noclip/
invalid/missing data from ranked coaching. Different game's physics may still
be a labelled visual reference, never an unqualified like-for-like result.
Show "no matching reference" rather than a made-up delta when confidence is low.
Time delta means player time minus time the reference reached the matched spot;
positive is behind. Speed units and energy reference/gravity must be consistent
or clearly identified as not comparable. Loading is bounded/asynchronous; no
full-corpus scan or per-frame unbounded point walk.

**Acceptance.** Faster/slower runs on the same route; route divergence, crossings,
stages, teleports, backwards movement, missing demos, unlike builds/physics,
reference changes and reconnects. A known matching run produces near-zero
deltas; an intentionally separated line refuses a match. Measure frame cost.

### 12.8 Mouse inspection and an anchored information bubble

**Build.** Inspect a visible line with the mouse: highlight the selected segment
and anchor a bubble/leader to the exact interpolated point. Show whose line it
is (name/run/source), time, speed/units and energy there; contact/label provenance
when relevant. Use the same point/cursor data as rewind and comparison, not a
separate nearest-sample estimate. Pick screen-space line segments with a bounded
hit radius, depth/visibility checks, sensible priority among overlapping lines
and stable hover. Never pick the imaginary segment across a teleport/stitch or
a culled/off-screen continuation. Let the mouse off the line dismiss the bubble.

**Interaction.** Use explicit inspect/cursor ownership in active play so hover
does not steal mouselook or movement. Decide on the smallest discoverable hold/
mode control during implementation; preserve menu/board/replay/rewind input
ownership and release on every exit/focus change. A bubble is informational,
not an implicit placement/resume request.

**Acceptance.** Own/demo/selected-board lines, crossings, near clip, occluded
segments, off-screen points, dense marks, several resolutions/scales, focus
loss and switching views. Bubble source and numbers match the chosen point,
including fractional time; normal running remains controllable.

### 12.9 Distinct line glow: player blue, demos yellow

**Build.** Give the **player line a blue outer glow** and **demo/reference lines
a yellow outer glow**, with controllable strength/width/colour and an off
setting. Preserve meaningful contact/gain/energy colouring in the core; the
identity cue must not make a scientific colour mode unreadable. Reuse the
existing strip's soft/additive outer band where possible, instead of mandatory
fullscreen bloom or dynamic-light passes. Define selected-board references
consistently with demos, and keep previous/failed attempts distinguishable.

**Acceptance.** Warm/dark/bright maps, several line widths, overlapping sources,
HDR/bloom off and glow off, accessibility/custom colours, and a bounded
multi-line GPU/CPU budget. Lex confirms the blue/yellow identity is obvious.

### 12.10 Noclip/practice sections become faint or dashed

**Build.** On entering noclip, transition the player line to a **faint dashed
style** (or the chosen faint equivalent); return to normal style when valid
movement resumes. Style is attached to the historical samples/spans, not to the
current movement mode applied to the whole old line. Preserve it through
publication, saved pictures, trim/splice, rewind and slot reuse. Inspect exactly
which raw/client/server metadata establishes noclip; do not guess from high
speed, missing ground contact or pause alone. Extend the visual-picture format
if needed with a backward-compatible unknown state, not a recording/evidence
change by accident. Practice markings do not alter server run eligibility.

**Acceptance.** Normal -> noclip -> normal, zero-speed noclip, a legitimate
fast airborne run, warm/cold restored pictures and multiple rewinds. Only the
actual noclip span is dashed/faint; dash spacing remains stable under LOD and
camera movement, and old/unknown files are not falsely marked valid.

### 12.11 Remove the leaderboard "Compare" control

Delivered by P536: chip/mixed-list state removed; imported/native remain separate.
This is not the continuous per-frame comparator in 12.9.

**Today.** `cl_scores.qc:Scores_Draw` draws the `sb_tmix` chip on the imported
board. It mixes native ranked and imported rows (`rec_sb_mixboth`); it is NOT
the live line-by-line comparator requested above.

**Build.** Remove that confusing visible chip/tab as requested. Reset/ignore
stale UI selection that would leave the board in an invisible mixed mode; keep
ordinary source tabs, refresh, line selection and demo viewing working. Do not
remove unrelated backend tiers or the new pace feature merely because they
share the word "compare". No rename-only workaround unless Lex asks for one.

**Acceptance.** Fresh/remembered board state, all source tabs, imported-only
and native-only maps, refresh/reconnect and selecting lines. No Compare chip,
no hidden mixed-board mode, no missing rows or broken watch/line actions.

### Delivery order and completion bar

1. Reproduce stitched rewind/contact/label failures and pin cursor/contact
   truth first (12.3–12.6); retain positive controls for pauses and teleports.
2. Shared cursor -> normal HUD/energy, then strafe-bind scrolling and smooth
   continuous browsing (12.1–12.3), plus Compare-chip removal (12.11).
3. Accurate/native and honestly inferred imported labels, visible reversal
   numbers, blue/yellow glow and historical noclip styling (12.4–12.6,
   12.9–12.10). Shared metadata/provenance before cosmetic smoothing.
4. Bounded live reference matching/pace, then mouse inspection using the same
   cursor/segment machinery (12.7–12.8). Inspect the identity/eligibility data
   and search budget before choosing an automatic-switch policy.

Each delivery needs acting control/subject tests, clean-build verification,
retained logs/screenshots, safe dual deployment and a recorded product patch.
Moving rewind feel, label placement and visual identity also need Lex's manual
acceptance. Do not mark the entire list done because the first visual effect
or existing split timer works.

## Order

- **A -- client, no decisions needed:** 2 (thickness), 10 (sort), 1 without
  the engine cancel (status strip, join cancel, the shader), 9 (leaderboard).
- **B -- data:** 7 (both tiers, the audit, thumbnails), 6 (mapdeps, the menu,
  the engine builtin).
- **C -- Momentum demos:** 3 (parser, re-import, the stage fix), 4 (the Pi
  fetch), 11.
- **D -- engine and server:** 1's download cancel and loading screen, 8 (builds).
- 5 waits on the answer below.
- **E -- current run-line/rewind request:** 12, in its staged delivery order
  above. This is a separate plan, not an extension of the old demo-import status.

## Decisions for Lex

1. ~~**KSF on demand**~~ -- answered 5 Oct: fill it slowly by itself (item 5).
2. ~~**Momentum demos on demand**~~ -- answered 5 Oct: fetch what we do not
   have (item 4).
3. **Builds (8):** how a second build of a map is stored and named, and
   whether the lobbies offer both.
4. **Where you saw 25 KSF places** (which screen).
