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
No native/evidence retiming or widened oracle. P560 now distinguishes sampled
request, pending and correlated selected native clock/delta in the viewer;
practice remains explicitly untimed. Four delayed warm/fresh-cold six-cut
matrices and real repeated-position/tie/window controls pass. This presentation
delivery does not close general alignment or camera/UX feel acceptance.
Native-event tooling after P542 additionally checks
engine-driven keep/zero-velocity teleport volumes on actual map ground, a
genuine six-second running stop and a fixed cursor over elapsed wall time.
Complete 30/100/300 FPS camera-state scans, nine compiled controls and 39
counterfactual checks pass. Synthetic-volume coverage is not authored BSP
teleport coverage; saved images alias despite distinct camera state. Camera
pixels/feel and the broader reported event/compare acceptance remain open;
numeric traces do not settle them.

### 12.4 Contact labels at the actual surface event

P608 stamps a ramp leave at the ride's last real contact instead of where the
0.08 s hold ran out; the held classifier and the board are unchanged. P611
pairs the live line's samples with the command frame the server's stats
describe, which removes its marks' lag behind a ping (measured at 30 to 1000
fps and at both tick rates, on one ramp). An interpolated crossing, a ride
whose bit flickers before its end, and displacement/prop ramps remain.

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

**Measurement tooling, not implementation.** `tools/OFFRAMP_CONTACT.md` documents
live stage traces and a separate buffered immutable-input replay control. The
latter compares clean/OFF/ON/repeated native results and offline static brush
candidates without per-tick logging. It reports raw gaps, not authenticated
winning geometry or physical exits; no-match geometry abstains. A third private
seam now snapshots return-bound winning BIH provenance with nested/physent,
triangle, equal-fraction, overwrite and unsupported-path controls. Runtime leaf
identity is not a Source brush-lump ID. An optional whole-brush snapshot now
copies actual loaded side planes/bounds at the win, with exact plane membership,
finite/cap/pose/callback abstention and immutable payload repeat controls. Side
gap diagnostics alone are not a collision/support oracle. The optional hull
layer copies actual accepted-contact and tick-end hull/posture instead of
assuming the previous contact's hull. The separate authored motion command
now drives six real static-brush edge/input/jump/seam controls plus open and
ceiling-blocked duck/unduck cycles. Full native queries agree with a bounded
joint convex/AABB oracle; fixture-only/no-oracle/OFF/ON/repeat body parity and
winning snapshot bindings ACT. A ninth real capsule ramp/departure case binds
native tick/contact/winner snapshots and path-sensitive capsule-vs-box queries;
it explicitly ABSTAINS from independent capsule geometry/support rather than
substituting an AABB oracle. A tenth translated/yaw world-brush actor binds
native instance/accepted-hull snapshots and rotation-sensitive real queries,
retaining transformed geometry ABSTAIN and exact original-nine parity.
A matched non-world-physent/removed-entity pair now ACTS a real physent-1 brush
winner, native hit/miss/world-only removal queries, and physically different
removed trajectory. Actual winner/model/whole-brush/hull snapshots bind while
entity geometry/support remains ABSTAIN; joint AABB query checks include only
active untransformed fixture brushes. Exact original-ten parity remains required.
A matched embedded BIH_MODEL/removed-parent pair now ACTS a native depth-1 child
brush winner and physically different removed trajectory, with same-pose native
removal controls and active-child-only joint AABB identity-fixture query checks.
Child/root/model/whole-brush/hull snapshots bind; embedded geometry/support stays
ABSTAIN. Exact original-twelve parity remains required. Embedded here means a
nested collision model, not a player starting solid: actual-body checks stay strict.
A matched actual BIH_TRIANGLE/removed-triangle pair now ACTS a native kind-2
world winner, hit/miss/same-pose removal queries and different removed movement.
Origin/leaf/model/actual hull/identity instance bind with an empty brush payload;
authored vertex/index rows are wiring, not copied accepted geometry. Triangle
geometry/support remains ABSTAIN. A separate `tools/offramp_triangle.py` now
checks retained native standing-AABB queries against an independent finite
triangle/four-unit-back-slab SAT interval, not the recorded plane/fraction.
Hit/miss/removal and native bias checks pass, including mirrored fraction faults
that otherwise preserve five-arm parity. These are authored-wiring query checks,
NOT copied accepted triangle support or general native triangle semantics.
A separate `offramp_tricopy` seam now copies actual native winning indexes/xyz,
return-bound before later probes/source changes. Native competition/ownership
controls and fourteen independent copied-geometry sweep checks pass; original
world-triangle-unresolved categories and general support ABSTAIN are unchanged.
Native axial/broadphase/back/corner/bevel semantics and real-map topology are
not inferred from the face-only actor. Separate setup-only `offramp_trislab`
queries ACT native back-slab NON-equivalence to ideal prism SAT; native miss is
not unconditional geometric clear. Separate `offramp_tribev` queries ACT one
copied-winning front-edge bevel's geometric entry/bias and bevel-OFF ghosts,
with face/solid/removal/repeat controls and exact twenty-case/copy/slab parity.
These are NOT new PM trajectories or general support/physical-exit/marker proof.
A real bevel-winning PM actor, general corner/tie/transform/capsule/entity/native
semantics and real-map topology remain open. An open-air
duck/release and matched no-duck falling pair now ACT native instant hull/origin/timer transitions,
+8.5-unit crouch shift/reversal and matching landing, with actual tick/hull binding
and current-hull joint AABB fixture queries. Original sixteen full case/winner
objects remain exact. This does not cover airborne winning collisions or general
posture. A grounded ascending-ramp approach and matched removed-ramp walker now
ACT native cached-firsttrace reuse, with winning whole brush/plane/actual hull,
prior-grounded-body/requested-sweep binding and actual/local/removed joint AABB
queries. Original eighteen full case/winner objects remain exact. This is NOT a
general engine collision-cache or physical-support solver. General non-world/
entity/embedded map wiring, nested transforms and geometry, real-map triangle/
displacement/prop geometry, general airborne/blocked/sliding posture, general
cached variants and explicit recovery/portal paths,
full capsule/transform geometry and general-map coverage remain unverified. These sampled fixture controls do not establish
continuous physical exit time or close classifier, FPS/tick-rate, held/render,
LOD or human acceptance above.

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

## 13. Modern SUI + native Dear ImGui — Lex, 8 Oct 2026

**Status: Stage A opt-in HUD-editor sample implemented, isolated/live-tested
and deployed in Patch 566. Patch 570 adds the matched font baseline and corrects
native physical bakes across virtual-screen scaling. P598 supplies the optional
native drawing backend; P600 adds bounded diagnostic input/actions. Native real
panels (B onwards) are NOT migrated. Aesthetic/cost acceptance remains pending.**
Lex wants the current SUI improved, plus native ImGui for rich scoreboards,
graphs, HUD editing and other interactive overlays. Keep the lightweight QC
HUD and the existing interactive panels as fallbacks. This does NOT replace
item 12's cursor, rewind, contact or comparison contracts.

### 13.1 Findings and scope

Inspected local source on 8 Oct: FTESurf `87b2411f7240`, engine
`f05d29419875`, and the separate wrlines reference `6a60d6b205bf`.
The FTESurf tree is shared/dirty, including graph/font work; these refs are
inspection anchors, NOT claims that every observed file belongs to those
commits or that any binary runs that source. Remote main has advanced and has
item 12; choose a freshly inspected clean implementation base before coding.

- `src/sui_sys.qc`: immediate-mode-like action registration, frames, clipping,
  scrolling, keyboard navigation, sliders and text fields already exist.
  `sui_fill`, `sui_subpic`, `sui_border_box` and `sui_text` are useful extension
  sites. Preserve existing calls and interaction IDs.
- `src/shared/sh_font.qc`: shared TrueType faces and per-face baked size
  ladders already exist. `Font_Px` snaps a requested size, but callers must
  account for the renderer's virtual-to-physical conversion. Stage A's modern
  path does that explicitly; the legacy HUD/text interfaces remain unchanged.
- `src/client/cl_hudedit.qc`: `HE_Tip` supplies descriptions, `HE_Chip`
  latches hover text and `HE_DrawTip` draws local tooltips; generalize that
  experience. `HUD_EditClose` explicitly queues
  `cfg_save` when dirty: `cfg_save_auto 0` alone does NOT protect test settings.
- `src/client/cl_scores.qc`: held `+showscores` is a passive peek; MOUSE2 or
  `scores open` pins an interactive board. `-showscores` closes it. Existing
  loading, source tabs, line selection, watch and room actions remain owners
  of the data/actions, regardless of which frontend draws them.
- `src/client/cl_linegraph.qc`: `LineGraph_Prepare/Plot/Draw` already provide
  incremental preparation, nine source slots, 384 display bins, breaks,
  hover values and recorded/assumed gravity labels. Keep these semantics;
  a new renderer is not a second replay reader or energy calculation.
- `src/client/cl_hud.qc`: `UI_CursorClaim/Release` own the mouse through a
  shared bitmask. Panel visibility is separate from cursor ownership.
  `cl_main.qc:CL_InputChain`, `CSQC_InputEvent` and `CSQC_UpdateView` define
  input priority and overlay order; native UI must participate there.
- Engine `plugins/plugin.h` and `engine/client/cl_plugin.inc`: the published
  `plug2dfuncs_t` has images/quads/text/lines and menu focus, but not the full
  indexed-triangle/scissor submission API needed by an ImGui renderer.
  Image upload exists, but its alpha convention also needs verification.
- Engine `engine/common/plugin.c`: `MenuEvent`, `UpdateVideo`, shutdown and
  Sbar hooks exist. `ExportInterface` accepts named, known interfaces, NOT
  arbitrary new ones without engine work. In `pr_csqc.c:PF_R_RenderScene`,
  `Plug_SBar` is conditional on engine-HUD drawing; FTESurf sets
  `VF_DRAWENGINESBAR` to 0. A standalone `SbarOverlay` is not the integration.
- wrlines uses an ImGui context, restrained rounding, font-size selection,
  tables and custom graph drawing. Adapt style/presentation as useful; do
  NOT bring over its injector, DX11 Present hook or Momentum memory access.

**Non-goals for the first deliveries.** No movement, recording, evidence,
rewind mathematics, board/download protocol or stored run-format changes.
No wholesale HUD/main-menu rewrite, fullscreen blur, docking, separate OS
windows, web UI or arbitrary native function/pointer calls from QC.

### 13.2 Architecture and compatibility

**Preferred prototype: a native C++ UI plugin plus a small engine host.**
Keep Dear ImGui and its FTE backend together, with a versioned C ABI at the
engine boundary. If plugin registration/lifecycle makes this substantially
less maintainable, decide explicitly on a compiled-in optional module at
Gate B; do not create two production backends.

1. Add a separately versioned 2D mesh interface: texture handles, vertices,
   colours, UVs, indices, clipping and bounded batch submission. Do not grow
   the existing exact-size `2D` ABI and silently break older plugins. Use
   FTE's renderer abstraction, not raw DX11/GL hooks. Flush pending QC 2D
   work at the boundary and restore clipping, blend, colour and other state.
   Handle physical framebuffer vs virtual UI coordinates, clip origins,
   premultiplied vs straight alpha, index limits and vertex offsets.
2. Add a known native-UI service registration and narrowly scoped, named QC
   builtins in the engine's CSQC/MQC builtin tables. QC remains the owner of
   panel state, cvars, data selection and game actions. Native code handles
   widgets/layout and drawing; the engine host handles validation/lifecycle.
   Do not use direct VM-pointer access or invent a gameplay command channel.
3. Start with capability/status, begin/end panel, text, button, checkbox,
   tooltip and bounded table-row primitives. Design the real calls after a
   widget/bridge benchmark, not a speculative wrapper for every ImGui API.
   Copy transient strings; validate buffer lengths, counts and handles.
   Graphs use bounded batches/cached data, not one QC call per raw point.
4. Check availability with nested `checkbuiltin`/capability tests: QC logical
   operators do not short-circuit. Missing module, old engine, unsupported
   renderer, failed atlas or incompatible ABI selects the existing panel.
   Backend preference and actual active backend are separate status fields.
5. Preserve `UIC_SCORES`, `UIC_HUDEDIT` and `UIC_LINEGRAPH` for their panels,
   regardless of frontend. Do not allocate a second claim for each renderer.
   Preserve the passive-board/active-board distinction. ImGui capture flags
   inform routing within the active panel; they are NOT authority to take
   the cursor or to intercept the entire input chain.
6. Route engine mouse/key/Unicode events through the existing input owners.
   Opening-frame capture, repeats, press/release ownership, bound minus
   commands and focus loss need explicit handling; a previous-frame
   `WantCaptureKeyboard` flag alone cannot settle them. Keep chat, replay,
   rewind, console/menu and editor priorities; do not feed/consume one click
   twice through SUI and ImGui. Release stale native input on close/reset.
7. Use stable row/element IDs, not display names or sorted row positions.
   Resolve queued actions against the same identity/generation after drawing;
   a refresh must not redirect a click to another run. Convert engine colour
   escapes deliberately, treat strings as text rather than format strings,
   and handle UTF-8, duplicate names, long names and missing glyphs.
8. One native frame per active frontend/VM, not one per panel. Start with CSQC;
   add MQC after its menu/input lifecycle passes. Keep contexts/state distinct
   across VMs. Closed native panels skip NewFrame, widget building and mesh
   submission. Bound caches/allocator growth; keep optional diagnostics quiet.
9. In the prototype disable ImGui's implicit ini/log writes. Later window
   persistence must use an explicit game-filesystem location, never a bare
   `imgui.ini` in CWD or the owner's cfg. HUD layout stays in existing cvars.
10. Pin a tested Dear ImGui version with its MIT notice. Keep vendor sources
    separate from the adapter. Update engine/plugin build targets together,
    including the explicit `NATIVE_PLUGINS` list, both Windows installs and
    eventual Linux packaging/ship-set checks. A dedicated server must not
    acquire a client UI/C++ runtime dependency. No runtime downloads of code.

**Frontend selection.** Proposed per-panel preferences (names not yet API):
`ui_scores_backend`, `ui_graph_backend`, `ui_hudedit_backend`, with legacy as
prototype default and native opt-in. Apply switches at a closed-panel boundary
or perform an orderly close/reopen; never leave two frontends owning input.
Native failure must release state and reopen the usable legacy equivalent,
not just leave the player with a basic HUD and no interactive controls.

### 13.3 Independent SUI improvements

These help even installations that never load ImGui.

**Typography constraint — Lex, 8 Oct.** Layout scaling is not font-quality
acceptance. Use a glyph bake at the actual physical-pixel height, not a scaled
nearby atlas. Stage A converts the desired height to physical pixels, snaps
against the selected existing font ladder, converts back on both axes and
pixel-aligns text origins. Size changes step between native bakes. A new native
size is possible by rasterizing the TTF again and caching that bake; do not
rebuild atlases every frame or substitute bitmap stretching. Apply the same
net-physical-size rule to ImGui's font/framebuffer scaling. Larger font ranges,
missing-glyph/DPI behaviour and human legibility remain explicit acceptance.

**Font-quality follow-up — Lex, 8 Oct (not implemented).** Lex approves the
new UI's overall appearance and thinks text is improved, but still only
"OK" compared with Apple's text processing. Aim for **Apple-like visual
clarity, smooth edges and consistent weights**, while remaining low-budget
and very fast. This is a visual reference, not a promise to reproduce CoreText
or use Apple's proprietary fonts/implementation.

- First capture a font-quality baseline at matched font file, physical size,
  DPI, foreground/background and renderer. Include small text, punctuation,
  thin/bold strokes and light/dark backgrounds; keep native physical bakes.
- Investigate the current rasterizer's hinting/coverage, alpha and gamma
  handling, atlas filtering/padding and pixel alignment. Prefer correcting
  those paths over adding expensive effects. Do not assume more smoothing
  is automatically clearer; compare actual glyph images and let Lex judge.
- Cache glyph rasterization/atlases and metrics by font/size/render settings.
  No steady-frame rebaking, font-file IO, allocation churn, blur/postprocess
  passes or layout recomputation for unchanged text. Bound cache growth and
  account separately for cold glyphs and DPI/size changes.
- A/B visual quality AND CPU/GPU/frame-time cost against P566 with the same
  workload. Apply section 13.5's pre-registered performance gates, not only
  FPS. Keep the current native-bake path as fallback; reject a quality mode
  whose recurring cost exceeds the agreed budget. Any added sampling/shader
  work must earn its cost with visible improvement and measured timings.
- Carry this policy into native ImGui. Investigate/cache additional native
  bakes when needed, not fractional enlargement of a nearby bitmap. Exact
  platform parity and font-quality/performance acceptance remain unverified.

- Shared colour/spacing/radius/focus tokens, scaled consistently. Candidate
  location: a new shared UI module ordered after fonts in both `.src` files.
  Pass the palette to native UI at setup/change, not by parsing every frame.
- Add rounded panel/button helpers using a small preloaded nine-slice asset
  with antialiased corners. Apply frame transforms once, preserve clipping,
  clamp corners for tiny controls and retain rectangular hit targets.
  Existing `sui_fill` remains unchanged. Asset licensing and release ship-set
  coverage are part of this delivery; no per-frame image-size queries.
- General tooltip registration by stable interaction ID: short hover delay,
  wrapped text, screen-edge clamping and explicit layering above scroll
  clips. Reset on ID change, drag, focus loss and panel close; a tooltip is
  informational, not another input/cursor owner. Generalize the existing
  `HE_Chip`/`HE_DrawTip` mechanism while retaining `HE_Tip`'s descriptions.
- Reusable button/tab/checkbox styles with hover, pressed, disabled and
  keyboard-focus states. Focus cannot rely on colour alone. Keep existing
  callbacks and keyboard navigation; style is not a binding-system rewrite.
- First apply to a small existing settings/HUD-editor area. Retain classic
  style during testing. Later add subtle shadows, icons and popup helpers
  only after measured visual/input tests. No mandatory animation/blur.

### 13.4 Delivery sequence and gates

**A — baseline and SUI sample (small/medium).** Capture the existing board,
HUD editor and graph at fixed settings; record source/binary hashes, fonts,
resolution, renderer and input behaviour. Implement tokens, rounded helpers
and a shared tooltip on one real panel, with a classic/modern comparison.
Gate: visible improvement, identical action IDs/results, no new warnings,
correct clipping/scaling and no idle tooltip work when not shown.

**A delivery (P566).** Added `src/shared/sh_ui.qc`, shared SUI frame hooks,
a generated/licensed-in-tree nine-slice mask, and an opt-in HUD editor using
`ui_style 1` (`0` stayed default/classic until P607 removed the switch). Modern
text is drawn at native
physical bakes. Tooltips delay (`ui_tooltip_delay`, default 0.35 s), wrap/cache,
clamp to screen edges, and release cached strings on close/hold/focus loss.
Mouse and keyboard focus are independent; -1 means unchanged. The editor
continues using the same action IDs, drag machinery and settings.

QC build: zero warnings. `tools/test_ui_modern.py`: 28 checks per isolated
real-dedicated/client arm, including missing-mask fallback, native font-size
requests, geometry/action parity, dirty-save isolation and zero additional
closed SUI frames/submissions. Tested 1280x720, 1920x1080 and 2560x1440,
HUD scales 0.75/1/2 and virtual-screen scales 1/1.5/2, using both Windows
client binaries. Same-style panel pixel floors were zero; the acted speed-HUD
control stayed pixel-identical. Seven producer/grader tests include absent
probes and font/tooltip/closed-work mutants. Existing p498 menu navigation:
16/16 after fresh-rig offline-consent/chosen-name bootstrap, fixed geometry
and 1.5 s rendered waits; stock fresh-rig failures were fixture prerequisites,
not patched product code. First tests established bounds/actions only; font
requests were corrected after Lex's warning and the revised matrix re-run.

**Deployment (8 Oct UTC).** Source commit `414cd86`, rebuilt/proved in a clean
worktree: CSQC/menu/mask copied to both Windows installs at 02:46, hashes
verified, .prev retained, personal configs and Windows server progs unchanged.
Guarded Pi deployment found all 12 lobbies empty, verified both progs, kept
.prev and restarted all 12. Mask copied/hash-verified separately. At 02:57 an
actual connected-client smoke opened the fleet-delivered editor and reported
79 rounded draws with the asset available. UDP status omitted CSQC fields;
it was not a checksum control. Do not infer automatic asset downloads for
other clients, active owner-VM reload, release verification or font acceptance.

**Operator feedback (8 Oct).** Lex says the UI looks good and text seems
better, but requests the font-quality follow-up above. This accepts the
overall look, not every input/lifecycle case or an Apple-like quality result.

Not closed: actual OS/device feel, broad nested clipping/UTF-8/lifecycle matrix,
full CPU/GPU/percentile budgets or advanced font/DPI acceptance. No graph,
scoreboard, main-menu styling, evidence semantics or native ImGui changed.
Full shipguard is blocked in a bare worktree by pre-existing untracked
`ftesurf/particles`; the new exact asset entry and its missing-entry mutant
are separately tested. This is not release/archive verification.

**B — native plumbing and isolated gallery (large; highest-risk step).**
Bring up one opt-in CSQC test window with text, rounded controls, nested
scrolling, a tooltip and a bounded table. Explicitly submit through the QC
bridge; do not use the disabled Sbar route. Exercise image upload, mixed
QC/native drawing, large index batches and lifecycle before porting panels.
Gate: measured counters prove native execution, backend absence proves the
legacy path, input is returned correctly, and graphics state is restored.
Decide plugin vs compiled-in module here, using actual build/adapter evidence.

**C — scoreboard first (medium after B).** Preserve the existing read/refresh,
source tabs, paging, download/watch/line/room actions and empty/loading/error
states. Build ImGui tables with visible-row processing, tooltips and stable
row identity. Keep hold-to-peek and MOUSE2/pinned interaction exactly usable.
Do not resurrect item 12's removed mixed-list Compare chip.
Gate: row/content/action parity with legacy; scrolling and refreshing cannot
select another run; release/focus controls pass and legacy fallback works.
Current unpublished ranked-table slice: `tools/p603scores.md`, still opt-in and
legacy-covered. Real-source local/HTTP routes, lifecycle, enable/VM teardown,
docked-room exclusion and narrow overflow have synthetic acting controls.
GL/D3D11 act; Vulkan atlas teardown now waits for its fence and passes those
controls. D3D9 device creation/fallback is not parity. Six-row uninstrumented
CPU samples exist; wider stores/endurance/device budgets and human font/input
acceptance remain. Bounded physical13/16/20/24 bakes are now staged on the unchanged
model ABI, with acting size-change authority, atlas stability, physical ink and
prior-score-provider fallback controls. This is not face/Unicode quality, automatic
DPI or shared QC/native typography acceptance. A bounded density continuation now
adds a separate exact-size NativeUIModel/2 (256 widgets); /1 stays at64 and
older engines/providers retain six-row native pages. Current providers budget
24 nine-cell rows plus at most6 metadata widgets, using the existing physical
viewport/clipper and vertical/horizontal scroll. Both-index real ImGui controls,
six GL runtime arms, 32-row real loopback parser/FindMine, identical/reordered/
shrunk replacement authority, first-row scroll reset and reader counterfactuals
act. This does not extend earlier six-row D3D11/Vulkan/cost evidence to /2:
denser-store percentile/allocator/endurance/backend/device budgets remain the
next gate, along with human font/input acceptance and clean publication proof.

**D — graph presentation (medium after B; can follow C independently).**
Use the same retained samples, incremental preparation, bins and source IDs.
Add cleaner axes/legend, hover readout and display selection; defer graph
zoom/pan until the existing behaviour passes. Keep the basic passive graph
on QC initially so an always-visible HUD graph does not activate ImGui.
Gate: numerical/identity parity, real breaks stay unjoined, missing metadata
stays honest, and nine-source graph work stays bounded during loading.

**E — HUD editor inspector (medium/large after C/D).** First port only the
options inspector: controls, descriptions, grouping and tooltips. Keep the
current HUD preview/rectangles, drag/anchor machinery and cvars. Never let a
window move and a HUD element drag act on the same press. Retain reset/save
semantics; undo/presets are separate follow-ups, not necessary for this gate.
Gate: same cvar outcomes and placement, correct scale/hit tests, safe close,
no accidental cfg/ini writes in the isolated rig, and legacy editor fallback.

**F — optional wider adoption.** Consider MQC main-menu/map/board screens,
more replay/practice windows and an explicitly owned line-inspection bubble
only after the earlier gates. Item 12 owns that bubble's point selection and
provenance; ImGui only supplies presentation. Docking and multi-viewport stay
out unless Lex separately asks and their input/performance cost is justified.

### 13.5 Pre-registered tests and falsifiers

Every arm needs an acting control. A blank screenshot, no log line or no
crash does not prove either frontend ran. Add planned diagnostic handles
for active backend, cursor mask, focused ID, action ID/generation, native
frame/submission counts, geometry counts, allocator growth and UI CPU time.
Register harness controls as cvars/commands; do not rely on QC-global `set`.

| Test | Control/subject and failure condition |
|---|---|
| Capability/fallback | Legacy control visibly opens the real panel. Native subject reports an active context/submission and draws it. Missing/disabled module, old engine and unsupported renderer still open the legacy panel, with no unresolved builtin call. |
| SUI styling | Same real control/action in classic and modern styles. Rounded pixels and delayed tooltip must be present; both actions/cvar results must agree. Nested frames, tiny controls and scroll clips must not offset hitboxes. |
| Tooltip geometry | Hover centre and all four screen edges, move IDs, drag and close. Wrapped/clamped tip appears after the declared delay and disappears on each reset, without consuming clicks. |
| Board modes | Hold showscores while walking/mouselooking: passive board, no cursor claim. MOUSE2 pins: native table responds. Release showscores, Escape, console/menu and focus changes must follow existing contracts and leave no orphan claim. |
| Key ownership | Open/close while movement/jump/modifier/mouse keys are held; repeat, rebind, press both directions, lose focus, return and release. Chat/replay/rewind controls act in control arms. No lost minus-command, stuck movement, leaked UI action or revived held scroll. |
| Cursor arbitration | Claim two legitimate owners, release each in both orders. Closing native UI must not steal the other owner's cursor; final release returns mouselook. |
| Table identity | Empty/loading/error/one-row/large-list fixtures, duplicate/long/UTF-8 names, refresh and sort while selecting. Display IDs and resulting replay/line/room actions must match the clicked identity, not its new index. Work scales with visible rows. |
| Scale/fonts | P570's `tools/font_quality.py` gallery proves native pixel invariance at console scales 1/1.5/2, with repeat/reload/unbaked controls (see `tools/font_quality.md`). Broader gate: compare at 1280x720, 1920x1080 and 2560x1440, UI/HUD scale 0.75/1/2 and changed virtual-screen scaling. Text and controls fit, clicks align and corner radii stay sensible. Missing font/rounded asset has a usable fallback; glyph atlas rebuilds do not occur every frame. |
| Drawing state | Draw known QC colour/clip markers before and after native UI, with overlaps and off-screen clips. Compare legacy/control pixels; no tint, alpha halo, scissor leak, changed HUD or incorrect layer. Exercise 16/32-bit index limits/vertex offsets where supported. |
| Graph parity | Same fixture/source selection in both renderers. Check values at first/middle/last/bin boundaries, gaps, teleports, absent velocity/gravity and assumed gravity. Same numeric values/labels; no line crossing a real break or fabricated sample. |
| Editor safety | Isolated cfg fixture: edit position, anchor, size and one option, reset and close/save. Both frontends produce the expected cvars/file changes ONLY in the rig. Dragging a widget cannot move the HUD or vice versa. |
| Lifecycle | Repeated open/close, map change, disconnect/reconnect, CSQC reload, menu restart, resize, fullscreen/alt-tab and renderer restart. Restore fonts/textures correctly, clear stale input/actions, and bound memory after warm-up. Test module absence separately from an initialized-module failure. |
| Closed cost | Same gameplay/HUD control with native disabled vs loaded but all native panels closed. Counters prove zero native frames/submissions and no recurring native allocator growth; repeated timing arms must exclude a repeatable regression beyond the agreed bound. |
| Open cost | Legacy and native show the same rows/graph workload. Prove scrolling/hover/input acted. Report UI CPU, geometry/draw counts, memory and real frame distributions, not only headline FPS. |

**Performance policy, not measured claims.** Pre-register exact fixtures,
row counts (candidate 1,000-row table) and graph workload (all nine available
slots), rendering/settings and run duration before implementation testing.
Candidate budgets for Lex to approve: closed-path median active-frame delta
<= 0.05 ms and p99 delta <= 0.10 ms; warmed open-panel UI CPU median <= 0.50 ms
and p99 <= 1.00 ms. Also report whole-frame impact and GPU time if trustworthy
timestamps exist; do not infer GPU cost from CPU or FPS. Record first-open
atlas/upload/loading spikes separately instead of hiding them in warm-up.
If A/A control drift exceeds the closed bound, the result is inconclusive,
not a pass. Investigate or agree a different budget BEFORE rerunning.

Alternate A/B order over at least three warmed runs per arm with a fixed
camera/workload, foreground client, resolution, fonts, vsync/pacing settings
and explicit `cl_idlefps 0`, `cl_maxfps 100`. Record actual effective cvars.
Use UI-specific instrumentation plus `profile_csqc`/`r_speeds_dump` for CPU
attribution. FTE's refresh-only headline omits the listen server; include
server cost and use sampled frame times for percentiles. The cap can conceal
headroom loss: active UI/host work must be measured separately from pacing.
Any additional high-FPS matrix is explicitly specified, not an inherited cap.

### 13.6 Harness, build and delivery safety

- Use an isolated clean worktree and test install/home/config for runtime
  arms; owner content/settings and another session's processes are not test
  fixtures. Account for explicit `cfg_save` as well as automatic saving.
  Fresh log/screenshot names; start configs with `cfg_save_auto 0` and set
  every measured cvar. Launch with WorkingDirectory `C:\FTESurf`.
- A local socket/dedicated server is required for real client-prediction/input
  arms. Use `C:\FTEQuake\fteqwsv64.exe` on a designated test port, not the
  game exe's dedicated mode or the sweep port. After CSQC rebuild seed with
  `python tools/seed_csprogs.py` and restart the test server. For main-menu
  arms issue `menu_restart`; for in-game HUD arms close the builtin menu.
- Build from `src/` with pwsh 7. QC:
  `pwsh -NoProfile -Command "./build.ps1 -Jobs 8"` in an isolated worktree.
  The published script inspected at `21cfeea` has no `-NoDeploy` parameter;
  QC-only builds write into that worktree and do not copy to either install.
  Check the actual script before future use. Engine/interface work adds
  `-Engine -Full` and explicit isolated `-FteRoot` and `-QuakeDir` destinations;
  do not repoint/copy over shared
  engine objects. Regenerate clangd's database after build-flag changes and
  inspect LSP diagnostics, but the compiler/runtime remain the actual gates.
- Reuse relevant existing falsifiers: `tools/p498keys.py` (whole-chain input),
  `tools/p440font.py` (font/scale pixels), `tools/p545graph.py` (graph fixtures)
  and the SUI/editor/cursor fixtures. Inspect each driver's fixture/process
  operations before running it. Add a bounded UI driver with explicit reached,
  acted and graded stages; capture screenshots as well as status/counters.
- Keep .src ordering load-bearing. Regenerate builtin definitions by the
  normal engine/QC procedure; do not hand-edit generated `src/defs/*.qc`.
  Evidence/reader changes are out of scope; if scope expands, stop and apply
  their separate design/contracts/corpus gates first.
- Lex accepts the actual appearance, legibility, tooltip timing and mouse
  feel. Numeric traces and screenshots cannot certify those preferences.
  Record remaining human-only acceptance in `lextest.md` at delivery, not as
  completed work in this proposal.
- Each implemented milestone gets its own verified product patch; fetch both
  repos and claim max+1 only then. No patch/build bump for this plan. Verify
  and commit only owned changes, prove the commit in a clean tree, then do
  the normal approved dual deployment with destination hashes/provenance.
  Fleet/release deployment needs its full operations/ship-set gates; a native
  client UI does not imply that server progs or the Pi need changes.

**Next step.** Overall Stage A appearance is approved; keep it opt-in while
interaction/lifecycle acceptance remains pending. P570's physical-native font
baseline and guarded dual Windows delivery are complete; quality preference,
cost and device acceptance remain separate. Stage B's first prerequisite is
now repaired by P581: memory images return drawable shader references, with
replacement/restart/release/reload, invalid input/IDs and no-renderer controls.
The P570 zero-handle defect is an acting control, not the current implementation.
P589 (guarded dual-native delivery 2026-10-08T09:09:48Z) adds the separate
exact-size `2DMesh/1` indexed-2D interface and non-repeating plugin-owned RGBA
texture tokens, reclaimed on release, plugin
close and pre-renderer teardown. Physical CPU triangle clipping avoids raw
backend-dependent `BE_Scissor` writes. Its native-only gallery passes offsets,
alpha, both windings, chunks, whole-batch rejection, count budgets, legacy
before/after markers, virtual scales 1/2, renderer restart and plugin reload.
P593 adds the prerequisite explicit MQC/CSQC draw-site dispatch (not Sbar hooks):
copied `NativeUI/1` service ABI, non-reused VM-local owner handles, frame identity,
physical dimensions/inherited clip, synchronous failure fallback and lifecycle
release. The acting mixed QC-before/native/QC-after gallery passes in both VMs,
with independent virtual scales and full CSQC UpdateView; caller state and stale,
foreign, duplicate and outside-draw rejection have real-host controls. Optional
shared QC wrappers are compiled but no actual panel/default/input chain changes.
P594 additionally rejects non-finite final inherited clips before service dispatch;
NaN/Inf/physical-conversion-overflow host controls prove release to fallback.
P598 adds the minimal optional Dear ImGui 1.91.9b command-list service on that
bridge: diagnostic owners only, per-VM embedded-font RGBA atlases, no implicit
ini/log writes and bounded preflighted indexed-mesh batches. The real ImGui text,
rounded control, clipped 1000-row table/tooltip gallery acts at both QC draw sites
with identical physical output across virtual scales; malformed-data/16-/32-bit/
>64K/lifecycle/fallback controls pass. The development build includes the optional
DLL, but no real panel invokes it. Frozen-stamp build and guarded dual Windows
native-only delivery are complete, separately recorded in tools/p598imgui.md;
actual installed paths act and repeated protected-data/config/progs hashes stay
unchanged. Provisional native P595 was reassigned without rewriting the
concurrently published surfd P595-597 or historical tag.
P600 adds exact-size optional NativeUIInput/1 scalar events and generation-tagged
actions without changing NativeUI/1. Interactive diagnostic owners perform real
button/checkbox/text edits; both VM contexts, reset/queue/text bounds, UTF-8 scalar
preservation, fallback and lifecycle controls pass. Synthetic QC event dispatch
proves transport, NOT physical device routing or real-panel cursor/minus safety.
P601 supplies bounded copied widget/model snapshots and stable widget/row/action
identities for diagnostic owners; see tools/p601model.md. Renamed/reordered/deleted
rows, queued/held presses and unpolled actions have acting freshness controls.
P605 publishes the first real panel on that bridge: the ranked scoreboard table,
opt-in behind `ui_native_scores 1` with legacy as default and fallback, on an
additive exact-size `NativeUIModel/2` (256 widgets, 24-row pages). GL, D3D11 and
Vulkan pass the same acting gate on one laptop; D3D9 does not start there. Cost
and open/close endurance are measured against legacy on that machine only (see
`tools/p603scores.md`), which is evidence, not a portable budget. Appearance,
font/DPI and device acceptance are a human's (lextest.md). Switching the default,
or migrating the menu/editor, waits on those and on an approved budget.

P606 takes Stage A's modern style from one panel to every SUI panel a player
meets, and gives it a palette: one token set in `sh_ui.qc` (dark slate, pastel
accents) read by hud_edit, the save-lock and Source-renderer menus, the map
picker, the menu leaderboard and the +showscores board, whose modern layout is
new (`Scores_DrawModern`: same data, row drawers, ids and hand-offs). The native
table's provider wears the same colours. P606 kept `ui_style 0` as the default,
gated pixel-identical; Lex then retired the old look and P607 removed it and
the switch, gated the other way (`tools/test_ui_theme.py`: the new look did not
move). The board now shrinks its type on a small window instead of changing
layout. Next on the native
side, each its own patch because both move the fixed-offset gates: the game's
own font embedded in the provider, and the table's columns in the board's order.

---

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
