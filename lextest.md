# lextest.md — things waiting on a human

Notes left for Lex. Everything here was either measured and needs a judgement
call, or cannot be measured headlessly at all. Nothing in this file is a bug
report: real defects go in BACKLOG.md, and this is the list of things a machine
could not settle.

Written 2026-09-27 by ftesurf-e0 (the run-line work, Patches 449-453).
Delete an item once you have tried it, or move it to BACKLOG.md if it turns out
to be wrong.

---

## 00. 8 Oct — modern SUI editor preview (Patch 566)

Lex's feedback: the UI looks good; text appears improved but is still only
"OK" against Apple-like quality. Overall appearance is approved. Advanced
font quality is an unbuilt roadmap follow-up with a strict low recurring
rendering budget, not a completed acceptance or permission for costly effects.
Specific input/DPI/lifecycle checks below remain pending.

- With updated server CSQC, try `ui_style 1; hud_edit on`, then compare
  `ui_style 0`. Judge rounded controls, contrast, selected/hover/pressed states
  and actual keyboard/mouse feel; the gameplay HUD should remain familiar.
- Hover the text-effects chip and other descriptions: judge the 0.35 s
  delay, wrapping and edge placement. Hold a mouse button, close/reopen,
  type/chat and alt-tab: no stuck input/cursor or lingering tooltip.
- Judge native-font appearance at your normal resolution/DPI and sizes.
  Modern text snaps to physical bakes instead of stretching glyphs; size
  steps are intentional. Compare future Apple-like clarity/smoothing/weight
  improvements at matched fonts and physical sizes; measured low cost is
  required. Check moving between monitors/virtual UI scales. Current layout
  tests are not advanced font-quality acceptance.

28 isolated runtime checks per UI arm, seven producer/grader tests and the
controlled p498 menu checks pass. Actual OS/device delivery, full CPU/GPU
percentiles and broad renderer/lifecycle acceptance are not claimed. Native
ImGui is not installed by this patch; it is the next roadmap milestone.

## 00. 8 Oct — requested/native rewind clocks (Patch 560)

After reconnect/restart, inspect a fractional cursor: main HUD is display-only,
while the context below the keys names the sampled request. Resume: pending
says waiting, then the held countdown names native time, requested time and
signed difference. The native time must match the main held timer. Practice
resumes remain untimed, not a fabricated native clock. Close/reopen should not
leave an old selected caption. Check readability with your HUD scale/resolution.

Actual draw/timer/native/ack/prefix controls pass at caps 30/100/300 and both
clients with configured latency; compiled untimed/foreign/missing-metadata
branches and repeated-position native ties pass. Strict requested/native clock
equivalence remains red: this caption explains the choice, not a new selection
or evidence clock. Actual-device/untimed camera feel and custom layouts need you.

## 00. 8 Oct — live rewind focus cancellation (Patch 554)

After reconnect/restart, start a run and open rewind. Hold a bare strafe bind
(or an arrow), open chat, console or menu without releasing, then return with
it still held: the cursor should stay fixed, including repeats. Release and
press again: scrolling should start. Also try left+right, lose/restore OS focus,
then release one: the other cancelled hold must not restart on its own. Closing
rewind with a taken key still held must not start movement via its repeats.

Whole-chain synthetic cancellation/return/fresh-press controls pass at
30/100/300 FPS and both installed clients. Actual keyboard/OS-event delivery,
compound/modifier binds and camera feel still need your acceptance. Native
save/resume selection, recorder, personal cfg and Build number are unchanged.

## 00. 8 Oct — live rewind opposing holds (Patch 550)

Live rewind now cancels opposing owned directions, like demo scrolling. After
reconnect/restart, start a run, open rewind and hold your bare strafe binds:
left+right should stop; releasing either should resume the remaining direction.
Try remaps, taps and two keys bound to the same side. Whole-chain synthetic
controls pass at 30/100/300 FPS and both installed clients, but actual keyboard/
OS-focus behavior, compound/modifier binds and camera feel remain unaccepted.
P554 adds chat/menu/console and keyboard-focus cancellation; synthetic
panel-without-release and delivered-release controls pass. Try actual devices.
No native save/resume selection, recorder, personal cfg or Build-number change.

## 00. 8 Oct — fractional demo clock (Patch 549)

The main replay timer and full-demo chrome now share the fractional cursor clock.
Paused sub-tick seeks, backwards seeks, stationary spans, lead-in/finish bounds
and native body pinning pass synthetic draw controls. Try a real native and an
imported demo with taps, held scrolling and playback: timer/chrome should agree
with the visible cursor without creeping while paused. Synthetic legacy missing
velocity retains its old fallback; this is NOT acceptance of unknown-velocity
labels, imported camera continuity, long-demo performance or the whole overhaul.

## 00. 7 Oct — held demo strafe scrolling (Patch 544)

After reconnect/restart, open a native replay and an imported demo:

- Hold your +moveleft/+moveright binds (default A/D): one tick on press, then
  accelerating backward/forward scrolling. Arrows still jump 5 seconds.
- Try remapped keyboard binds, quick taps and releases. Hold both directions:
  demos and live rewind (P550) cancel; releasing one scrolls with the remaining
  key. P554 adds live focus cancellation; actual-device delivery remains to try.
- Open chat/console/menu while held, release and return; close/reopen the demo
  while still holding. No stuck scrolling or movement when leaving the viewer.
- Judge smoothness at your real frame rate, and that clock/speed/energy/camera
  follow the cursor across stops/teleports and imported clips. Primary mouse
  buttons remain replay chrome's. Compound/modifier binds are not implemented.

Synthetic whole-chain controls pass at 30/100/300 FPS; they do not settle actual
keyboard/OS-focus behavior or camera feel. No personal cfg or Build-number bump.

## 00. 7 Oct — low-cost water readability (Patch 543)

Restart the updated client and try the Water menu on `surf_aesthetic`:

- **Budget (no captures):** the body stays visible toward the horizon instead
  of turning into a black baked-cubemap rim. It is still an approximation.
- **Flat sheet:** visible, 70%-alpha material colour; switch Full -> Flat and
  back without restarting the map. Check visibility of the floor/hazards.
- **Cheap reflect:** keeps water colour at grazing angles, including when a
  cube is missing or reflection is disabled. Still has one refraction capture.
- **Dithered:** stronger default coverage (10/16); glass appearance is unchanged.
  Explicit `hl2_dither_force` still overrides coverage, and alpha/force edits
  now rebuild live. Check distance shimmer and readability while surfing.
- **Full reflect:** matched fixed-normal control is pixel-identical to P541.
  Its two extra scene renders remain expensive. Optional capture-size test:
  `r_refractreflect_scale 0.25; flushshaders` (default is 0.5). Judge blur as
  well as FPS; this is not a promise to recover the pre-reflection frame rate.
  Restore your prior scale with the same `flushshaders` command afterwards.

No personal setting, progs, movement or Build-number change.

## 00. 7 Oct — depth-aware live water (Patch 541)

After restarting the updated client, try `surf_aesthetic` with `hl2_water 2`
(your existing preference is retained). Live water now uses real refraction
depth for shallow distortion and material fog, instead of full-screen smearing.
Judge moving-water detail, shoreline clarity and reflection strength against
Momentum; this is not a claim of pixel-identical Source rendering.

- Look across the pool and down near pillars/steps: does it still pull a
  foreground object across the shore or make hazards hard to judge?
- Mode 1 keeps live refraction with cubemap reflection. Mode 4 stays the cheap,
  capture-free approximation; mode 3 remains dither. Those are quality/cost
  choices, not supposed to look identical to mode 2.
- Check your actual frame rate in play. Live modes add a depth attachment to
  their existing refraction pass, not a new scene pass; no universal FPS gain
  is claimed. Dense authored underwater fog is retained, not made transparent.

No personal cfg, swimming, progs, evidence format or Build-number change.

## 00. 7 Oct — low-FPS visual prefix boundary (Patch 542)

A selected visual row must not disappear because its six-decimal clock rounds
above the native cutoff. After reconnect/restart, repeat three warm and three
fresh-client cold cuts at a 30 FPS cap, then at 100/300. Resume close to a visible
sample and check whether the line loses the last row or shows an unexplained
pause. Keep a genuine stop and teleport as controls; neither should disappear.

The native server still chooses the closest position within its rewind window.
A cursor time can differ from that selected native snapshot: this patch fixes
visual boundary loss, not arbitrary requested/native clock equivalence or
moving-camera/contact acceptance. No recording retiming or Build-number bump.

## 00. 7 Oct — rewind camera at stitched breaks (Patch 540)

Raw break/stitch boundaries no longer blend velocity/view across attempts,
and chase direction stays on the current continuous span. Compiled and numeric
controls pass; moving-camera feel still needs you. After reconnect/restart:

- Make three warm and three cold cut/resume attempts, with long failed waits.
  Scrub both ways through each stitch in first-person and chase mode. Does the
  camera still pivot toward an unrelated attempt or show an unexplained pause?
- Keep a genuine recorded stop and a teleport as controls: stop time must stay
  counted, and the teleport must stay explicit rather than smoothed through walls.
- Repeat at low/high frame caps. Two 30-FPS requested/native clock mismatches
  remain in BACKLOG; don't treat this patch as a complete low-FPS resume fix.

No authoritative recording/save retiming, engine change or Build-number bump.

## 00. 7 Oct — swimming and the sidistic palette (Patch 538)

Swimming input/drag and real-recorder wet replay pass machine controls. Judge
feel and visual taste in actual play after restarting the updated client:

- On `surf_sidistic`, does the automatic blue-green hue (150 degrees), twice
  the fog distance and half maximum fog density look pleasant and keep hazards
  readable beyond the starting room? Try `hl2_colour_hue_strength 0.6` for a
  subtler shift, or `hl2_colour_hue 160` for a more cyan tone.
- `hl2_colour_hue 0`, `vbsp_fog_distance 1`, `vbsp_fog_density 1` restore the
  map's authored look. Return to automatic with hue `-999` and fog values `-1`.
  Check another map with these automatic settings: it keeps its original hue.
- Judge underwater visibility with your chosen water-material mode; the orange
  water overlay is gone, but authored material fog can intentionally be dense.
  `r_sourcewater 0` is an appearance control, not a swimming-physics toggle.

Scripted water-lip jump and submerged portal/stair/carrier assurance are in
BACKLOG, not silently included in this acceptance. Personal cfg is untouched.

## 00. 7 Oct — red Impact ERROR art (Patch 534)

The standalone `models/missing_error.md3` has extruded Impact ERROR letters,
fullbright red faces/darker sides and a small additive outline halo. It renders
red with bloom off, and a no-model control draws no red pixels. Judge the style,
not an assumed Source-perfect material. `modelviewer models/missing_error.md3`
or `exec cfg/test/p534missing.cfg` opens a local preview; restart for new assets.

- Is the extrusion/letter spacing/halo the look you wanted, and is the model's
  roughly 75x26x4-unit size sensible for a missing prop? No automatic failed-model
  selector is installed yet, so existing invisible missing props are not fixed.
- The authored 64x64 checker is loaded through `textures/no_texture.png` with
  `gl_load24bit 1`. Judge its sharpness in actual play. Explicit Source VMT pass
  maps can still go black on a missing base texture; that is in BACKLOG, not a
  subjective acceptance item. Your personal cfg has not been changed.

## 00. 7 Oct — budget water and material menu (Patch 523)

Both Windows installs now have the tested native EXE/HL2 plugin and CSQC, with
immediate predecessor `.prev` backups. The default remains Dithered (3). The
menu's Water row adds **Budget (no captures)** (4): animated normals, fog colour
and baked-cubemap reflection, not live reflections or depth-correct fog.
Production transition/menu/archive/startup controls pass. Pi CSQC is deliberately
unchanged pending old-native capability gating (BACKLOG); reconnecting to a lobby
can therefore give you its previous menu. Test locally for now.

- Restart the client, load a local water map and open the Graphics menu. Cycle
  Water through Budget, Flat, Cheap, Full and Dithered. Judge the low-cost look
  during real surfing, including above/below water and approaching the plane.
- Compare full/cheap/budget at your normal resolution. Watch authored normal
  motion and reflections while orbiting; report lost cues or distracting alpha
  artifacts, not an assumed Source-parity verdict. No GPU/portable FPS claim.
- Glass 0 now says Translucent. Starred material rows warn they need rebuilding
  or map load, and retry may cache. The budget label/footer should remain legible
  at your usual HUD/font scale. The full per-row acting audit is still open.
- Keep the default 3 if you prefer it. No owner config, SSQC or menu.dat was
  changed; use your normal explicit save choice if you want to retain 4.

## 00. 6 Oct — private observer panels (Patches 521–522)

The authenticated admin run page now retains per-attempt verifier counts and
shows stored similarity observations. Synthetic signed-in API and actual Node
renderer controls pass; the Pi application is deployed from `bf5153d` (23:42 UTC).
This does not judge browser layout or a new real finish. No badges, rankings or
thresholds changed.

- Log in and open a run detail. Check the counts line is readable inside verifier
  history; old attempts should say unavailable, not measured zero.
- Expand **Stored similarity observations**. A skip must show unavailable metrics,
  not a low score; identity is only same/cross/unknown, with safe skip explanations
  and A/B admin links. No recording filename or identity segment should appear.
- Check the historical/unbound/incomplete-coverage note is clear. The panel is not
  an accusation or a new adjudication button. Real new counts/field calibration
  and full pair coverage have not been claimed.

## 00. 7 Oct — in-game Momentum downloads and comparison graphs (Patch 545)

Machine controls cover queued/ready/missing records, cold delivery, two selected
requests before polls, line loading, watching and replacing queued watch intent.
Graph controls cover full vertical energy, recorded/assumed gravity, stage-start
alignment, gaps, interpolation, selection and clearing; screenshots have been
read. These do not settle physical-mouse feel, curve readability on a real long
run, or the budget with eight long retained paths.

- After picking up the new client progs, open `scores`, choose **imported**, and
  click **Get demo** on a Momentum row we do not hold. The NanoPi's downloader
  runs every five minutes; queued is not downloaded. Unsupported/unavailable
  demos should say so rather than quietly opening something else.
- Tick several **line** boxes, then click **graphs** in the left header (or
  `linegraph`). Move the mouse across either panel: one elapsed-time cursor,
  each selected run's speed and energy below, matching named curve labels.
- Tick graph legend rows off/on; judge overlapping runs, label separation and
  actual mouse accuracy. Close with Escape and make sure ordinary play resumes.
- Replay plus board lines should compare as slots 0..8. Try eight long files:
  loading may build envelopes briefly, but normal movement/HUD must remain usable.
- Energy is relative to each run's first sample, includes vertical speed and
  says **g=800 assumed** for imported/legacy recordings without a physics pin.
  This is not a certification that their original gravity was 800.
- `hud_linegraph 0` hides the passive panel; `hud_linegraph_labels 0` hides world
  labels without unloading your chosen paths. Judge whether the default panel
  size/placement is comfortable while surfing.

## 00. 6 Oct — surf_tensor2 model brightness (Patches 508–509)

The first saved window-wall camera no longer has its directional light amplified
by the minimum. The second camera now rejects direct lights behind world walls
instead of accepting every light in the PVS. Machine controls retain visible
lights, prove blocked contributions are zero and keep adjacent world geometry
unchanged. This is not a claim of exact Source rendering: large unbaked models
still use one sample/two slots; the engine's HL2_MODEL_LIGHTING.md explains why.
The HL2 DLL is deployed to both Windows installs (6 Oct, 15:29 UTC), and cold
launches of both installed clients passed the controls. EXEs/progs are unchanged.

- Restart the client to pick up the new HL2 DLL; no owner game was terminated.
- Revisit your two saved cameras and judge the default picture.
- `hl2_lt_min 0` versus `16` should make a modest dark-base change, not multiply
  the lit wall. No worldlight-toggle crutch is needed anymore.
- `hl2_lt_occlusion 0` versus `1` is the old PVS-only/new world-wall control.
  Leave `hl2_lt_worldlight 1`: bounce-only is not the reference.
- If comparing with Momentum/CS:S, use the same BSP build, camera and exposure.
  Judge the whole architectural model, not an assumed func_brush lightmap.

## 00. 6 Oct — rewind/save-lock trail continuity

Machine controls cover timed rewind/recording, retained warm prefixes, replay
saves and replacement, cold pictures, countdown and key release. Buffered and
streamed dedicated arms each pass 42 checks; this does not judge the rendered
path or camera feel. The development progs are deployed to the primary
Windows install, a separate FTESurf mod folder in the second install (Quakers
unchanged), and all 12 Pi lobbies. Reload/reconnect to pick up the new progs.

- Save/load or rewind/continue on a real surf/bhop run: the earlier path should
  remain, the abandoned tail disappear, and the timer continue as **segmented**
  rather than silently restarting as practice.
- Rewind again into the retained warm prefix. Check duck/stand first-person
  eye height and pitch, then the optional chase view. Look for a long joining
  edge or a path that no longer follows the played route.
- Save a replay point and load it: practice, with the correct picture and
  position. Replace one replay with another without closing it. During the
  countdown, try save/load; then hold/release and repress TAB.
- Cold restarts restore pictures, not historical server timer snapshots:
  rewind remains limited to retained authoritative history. P539's isolated
  buffered/streamed controls now pass three cuts AFTER the load, with counted
  long failed waits, native held body/clock and resumed recording. On a real
  route, judge this repeated-cut case too; a machine pass does not judge camera
  jolts, visual pauses or label readability.

## 00. 5 Oct -- the website, KSF's styles, the demo grab (start here)

### surf_voyager flies to the end -- 0.1.23 and the lobbies (5 Oct, night)

The hands-off flight now finishes in **1:06.270, the same 4418 ticks as your own
Momentum run of it.** Every tick of the first 11.6 seconds matches your recording
to the hundredth of a unit, the first ramp seam included; after a V trough at
11.6 s it drifts by a few units and still lands on your tick.

- **What changed:** the engine traces brushes the way Source does (the 1/32-unit
  epsilon, and Source's "never touched" marker where Quake 2 used -1), plus
  current Momentum's slide-bug rule. It is on by default (`pm_fixrampbugs 2`), so
  it applies to every map, and the randomized start is off on voyager only.
  Displacements and props keep their old test for now (BACKLOG says why).
- **Live:** release 0.1.23 (Windows and Linux), and all 12 lobbies run the new
  engine, cfg and progs.
- **Try:** surf_voyager on a lobby -- `!m`, walk back into the wall, let go. Then
  a few maps you know well, for anything that feels different on ramps.
- **Old recordings still verify.** A run made now pins the new physics version;
  an old server binary refuses it rather than calling it a mismatch.

**Your call:** times set before tonight ran the old rules and rank beside the new
ones. With no players yet the easy answer is to wipe or mark the old ones; say
which.

**One question:** type `mom_mv_bumpcount` in Momentum's console and tell me the
number. We use 8 (Momentum 0.8.7's); the new build's default is not readable
from its files.

**Also from tonight:** the bots' work was reviewed. The journal-check fixes and
the surfd fixes are merged and live; their Patch 444 was held back (it would
cancel an honest run in a rare case -- BACKLOG), and Patch 455 is rebased but
not finished (BACKLOG: finish round 11 or cut it down, your call). The board's
database backups now take 8.9 GB on the Pi's disk (89% full); pruning them is
`surfd-deploy.ps1 -KeepDbBackups N`, your call.

### Your player-page report (5 Oct, afternoon) -- fixed and live

- **"Could not load the board (HTTP 504)" on KSF and Momentum profiles.** The
  web server gives the board 5 seconds. The list of all 57,475 players was
  rebuilt inside a visitor's request every 5 minutes (16 s), and a big profile
  ran one query over every board the player is on (52.8 s for Ellipsis). The
  list is now rebuilt in the background and kept on disk; profiles load in
  1.8 s (Ellipsis, 2,575 times), 0.6 s (levi) and 0.5 s (you).
- **The Momentum profile link went to Momentum's 404.** Their profile pages
  want Momentum's own user number, which we do not have, so the link is now
  **Steam profile**, like Momentum's own site does. KSF players get **KSF
  profile**, which opens their ksf.surf page, and every imported row has a
  **KSF** or **MOM** button that opens that map's board on their site. I
  opened them: levi's KSF page, surf_borderlands' KSF records (levi 4th,
  1:30.569, the same as our row), surf_boreas on Momentum.
- **Stage times came first.** A profile now lists Main, then Bonuses, then
  Stages, with a heading over each; "Show more" loads the rest.
- **surf_chaos_fix "is not installed on the servers" -- not true.** It is
  installed and has zones, in the game's own `maps/zones/local` folder (66
  maps), which the game reads first and the website did not read at all. It
  does now: those 66 maps show as playable, and surf_chaos_fix's page has no
  note.

To try: Leaderboard -> Players -> levi, Ellipsis, yourself. One limit: KSF's
map page opens on Forward, so for a Sideways row pick the style there.

### What happened (5 Oct, while the Qwen bots worked on the anti-cheat)

- **The website is new and live: <https://proto.bar/ftesurf/>.** Black, big
  type, few words. The hero is your own ranked surf_utopia run (1:03.240) drawn
  from its recording, coloured by speed the way the game colours a line,
  turning slowly. There is a new **Anti-Cheat page**
  (<https://proto.bar/ftesurf/anticheat.html>): what a ranked run goes through
  and why that is fair, and nothing about how anything is detected. The
  leaderboard has the same header and look. Republished for 0.1.22 with
  `src/release/sitepage.ps1`, so no new release was needed; the old page is
  backed up in my scratchpad and is one `ln -sfn` away if you want it back.
- **A bug that has been refusing runs since 28 Sep: fixed.** The board's row
  caps (200k main, 1M stage) counted the imported Momentum rows, so from the
  28-30 Sep backfill on, every player's FIRST time on a board was refused with
  "run limit reached". It happened at least once: a lobby's run at 12:33 UTC on
  4 Oct. The caps now count only rows the servers sent (42 main, 131 stage).
  If you finished a map for the first time since 28 Sep and it is not on the
  board, that is why -- it has to be run again.
- **Your question: could the Pi download Momentum demos it does not have? It
  could not.** Every board row named its demo and nothing fetched one. Now
  `momgrab.py` does, from cron: the top 10 of every board, maps people open
  first, a few demos every 5 minutes, each checked against its own name, kept
  for good, converted with the same rules as the 5,260 re-imported runs, and
  linked to its row so "Watch" appears. A demo recorded on a different build of
  the map than the one installed is refused (its line would be drawn on the
  wrong geometry) -- and that is common for old records: the first one I tried,
  surf_nebula's WR, is on a build we do not have.
- **KSF past the first page, and its styles.** `ksfimport.py --watch` runs from
  cron every 5 minutes, 10 requests at a time: first KSF's whole map list
  (~100 requests), then the next unseen page of every board, shallowest first,
  so everything deepens evenly. Maps somebody opens on the website, or scrolls
  to the end of in game, go first. **All four styles** -- Forward (our Clean),
  Sideways, Half-Sideways, Backwards -- are boards of their own, with their
  stages and bonuses. Stages and bonuses for Forward were already there
  (25,579 stage and 12,376 bonus times). At ~2,900 requests a day it takes
  weeks to fill, which is what you asked for. If KSF ever says no, it stops
  for 6 hours, then 12, 24, 48.

### Things to try

1. The website on your phone and your PC: the hero, the Download section, the
   Anti-Cheat page. Does it read like what you wanted?
2. Leaderboard -> any KSF map (try surf_utopia_njv) -> Imported: Sideways,
   Half-Sideways and Backwards tabs appear once the crawl has reached that map
   (opening it moves it to the front).
3. Leaderboard -> a Momentum map you know -> the top rows: "Watch" appears on
   more of them over the next days.
4. In a week, on the Pi: `tail logs/ksfwatch.log logs/momgrab.log` in
   /srv/nvme/surfd -- steady lines, no "parked".

### Decisions only you can make

- The site: the copy, the stats strip (1,300+ maps / 66.67 tick / 12 lobbies /
  free), and the two in-game pictures -- they are crops of test captures with
  the debug text cut out. A clean screenshot session on your PC would beat
  them; I did not run the game while the bots' test arms were using it.
- The Anti-Cheat page ends with "Found a hole? Message the developer on
  Discord" and links the Discord channel. Is that where you want reports?
- KSF's 100-tick boards (`css100t`): their own tier, or leave them out?
- A per-row "Get demo" button (any rank, on demand) -- worth building?
- The game's own leaderboard has no picker for KSF's styles yet (website only).
- Speeds: KSF ~2,900 requests a day, demos ~1,700 a day. Faster or slower?

### Where I stopped (5 Oct)

Everything below is live and was read back, not assumed.

- **The board server:** `cf6cd12` deployed 04:07 UTC (all 53 files hash-match
  the commit, `/health` ok, 12 lobbies). The caps read "not full" on the live
  database; `/api/board` serves `style=hsw`.
- **On the Pi beside it:** momreplay/momimport/momreimport in the game's
  `tools/` (hashes checked), `zstandard` 0.25.0 for the cron user, and two
  crontab lines -- `ksfimport.py --watch` at :01/:06/..., `momgrab.py` at
  :03/:08/... (old crontab in `data/crontab.bak-20261005-*`).
- **First ticks:** the KSF crawl is still listing KSF's maps (620 so far,
  6,010 boards queued); the demo grab took 12 demos in its first two ticks,
  all filed and linked -- e.g. Morgan Freefarm's 3rd place on surf_fiellu
  bonus 1 is watchable now.
- **The site:** republished 0.1.22, every file served byte for byte.
- **Reviews:** the KSF crawl went through two rounds (the second found ways to
  lose rows -- fixed), the cap fix one (clean), the demo grab one (seven
  findings -- fixed); every fix has a test that a broken copy fails. What they
  found and I did not fix is in BACKLOG.md, "The KSF crawl, the demo grab and
  the site".
- **A collision you should know about:** the Qwen bots deployed the board
  server at 03:48 and 04:03 UTC while I deployed at 03:54. My 03:54 deploy
  left their newest work out on purpose (it was not live when I checked at
  03:42) and so rolled it back for nine minutes, until their 04:03 deploy put
  it back. Nothing was lost; the live server now has both. Running two
  deployers at once wants one of us to wait for the other.
- **Not built:** the in-game style picker, a per-row "Get demo" button, KSF's
  100-tick boards, fresh screenshots for the site.

---

## 0. Welcome back -- start here (rewritten 2026-10-04)

### What happened while you were away (3-4 Oct)

- **The rewind (Patch 477) and the ghost fix (478) are live on the lobbies**
  (4 Oct, 14:46). The rewind went through 27 review rounds and the ghost fix 12
  (three independent reviewers a round, each with a test arm and a "mutant"
  build per fix to prove the arm can fail). On 4 Oct you agreed to stop rounds
  once they find nothing that could rank an unearned run, corrupt a recording
  or harm the server; small input quirks now go to BACKLOG.md instead.
- **The timer and the speedometer have the drop shadow** (`hud_font_outline 2`,
  "text shadow" in hud_edit, the default) -- the clock, the speed, its energy
  line and the banner's big numbers. Bebas gets the shadow only, no outline.
- **A paused run of yours may be gone, and I deleted 38 empty folders (both
  3 Oct).** A test for Patch 478 used `data/resume/surf_dune` and consumed the
  paused surf_dune run parked there (0:42.945, written around 23-27 Sep --
  most likely an older test's, but I cannot tell, so assume it may have been
  yours). It cannot be recovered. The same test's cleanup removed 38 empty
  folders under `ftesurf/data`; they were recreated from the list it printed.
  The tests now park and restore the folders they use.
- **Your map-screen requests are live** (4 Oct, 15:40; ROADMAP.md has what is
  left):
  - a strip under the map list shows a download or a connect as it happens,
    with a cancel for the connect (cancelling a download needs engine work),
    and the 3D menu's PLAY station charges while one runs;
  - a **leaderboard** button on the selected map: KSF / Momentum / FTESurf
    tabs, rank, name, time and date, more as you scroll;
  - maps with full data (picture, tier, zones, records) sort first;
  - thickness for the replay, board and your-run lines (hud_edit, Run lines);
  - the line's numbers are in Bebas and say what they are ("701 u/s  E -28");
    `hud_lines_names 0` gives the bare numbers back.
- **KSF maps have pictures, and KSF's tier is kept.** 472 KSF maps had no
  picture; KSF's own now fill them (fetched once, by hand, 1.5 s apart). All
  929 KSF maps are in mapmeta.txt, and a row shows KSF's tier under
  Momentum's chip ("KSF 2", small and dim). The tier filter and the sort still
  use one tier (Momentum's, else KSF's).
- **Your music now drives the visuals.** OpenAL mixes outside the engine, so
  the shaders had nothing to hear. default.cfg now uses the engine's own mixer
  (`s_al_disable 1`, not saved in your cfg) -- just restart the game.
- **Names like Chriis™ and FløppyWrist** drew as `™` or a box on the
  boards: the engine's JSON reader misreads `\u` escapes (an upstream bug), so
  surfd now sends names as UTF-8 -- live, nothing to update. Thai and emoji
  still draw as boxes: the UI font has no glyphs for them.
- **0.1.21 is out** (https://dl.proto.bar/ftesurf/ftesurf-0.1.21.7z, 38.3 MB)
  with everything above and the rewind and ghost fix -- the same engine files
  as 0.1.20, so Patch 468 (touchpad) is still held out for your call.
- **Imported Momentum runs are rebuilt from their own demos (ROADMAP 3)** --
  live on the boards since 4 Oct, 20:31. 5,260 of the 5,281 runs were rewritten
  from the `.mtv` each came from: the player's real view angles, velocity,
  ground, duck and jump, and keys from the demo (the move the game recorded, or
  the buttons where it did not record one). The old files had positions only,
  so the mouse pad drew the velocity turning, the key display stayed dark, and
  a mid-air crouch made a fake speed spike. Stage runs no longer read one stage
  late. The other 21 keep their old body (20 have no demo here, 1 the decoder
  refuses). Four review rounds; the last one's three findings were fixed or
  logged. Still wrong, in BACKLOG.md: a key held on a ladder can read "no key"
  (210 ticks in 2 files), and some A+D overlaps need a closer look. A demo has no
  ramp contact at all, so "colour by contact" still reads air on these runs.
- **The map list says which games a map needs (ROADMAP 6).** A row reads
  "needs TF2 CS:GO": red where this PC lacks the game, plain where it has it.
  It comes from a fresh `data/mapdeps.txt` (560 needs over 419 maps: CS:GO,
  TF2, Portal 2, Portal and Momentum's mount folder) and a new engine call
  (Patch 480). The engine 0.1.21 and 0.1.22 ship cannot answer, so there the
  names draw dim; this PC's engine can. The filter chip is not built yet.
- **Engine Patch 481: a server can no longer make your game load or unload
  content.** Six `fs_` commands (fs_load, fs_useaddons and four more) ran when a
  server sent them, so a server could mount a folder of your PC into the game
  or add a Steam library. Now only your own console and configs can run them.
  Pushed and in this PC's engine; players get it only with an engine release
  (see the decisions below). I keep the notes on what else a server can make
  the engine do in your private repo, not in public files.
- **The Momentum import was locking the database every 7 minutes**, and a run
  submitted in that window would have been refused and lost. Its link step
  scanned 2.35 million rows inside its write lock (6 s, past surfd's 5 s
  timeout); since 20:31 it reads first and writes only what it finds. In the
  40 minutes before, 4 of 6 ticks locked the lobbies out (9 errors); the 8
  ticks after (to 21:21) had none. The board write itself is still one transaction, and
  a much bigger tick could still pass 5 s (BACKLOG).
- **The Momentum demos have been scanned (ROADMAP 11), a first pass.** All
  7,177 on this PC (2,218 players, 499 maps; 2,714 of them the WR set) went
  through it: none was worth a look, and 1,322 were too short to measure. What
  it looks for, what it cannot see yet and the per-demo report are in your
  private repo (`FTESurf-private/momscan` and the plan's "Momentum demo scan"),
  not here.
- **0.1.22 is out** (https://dl.proto.bar/ftesurf/ftesurf-0.1.22.7z, 38.3 MB,
  4 Oct evening) with the `needs` line and the replay Segments column fix. The
  467 engine again, so players see the `needs` names dim until an engine
  release.

### Things to try

1. **Rewind (Patch 477) -- live.** During or after a run, press **BACKSPACE**.
   You freeze and the camera follows a cursor on your run's line:
   - **LEFT / RIGHT** scrub (hold to speed up; the mouse wheel jumps 10 points),
   - **ENTER** resume there: 3-2-1, then you carry on with the speed and the
     view you had at that moment,
   - **S** save a state there (it joins your save list as a normal save),
   - **ESC** back. On a run that is on the clock it reads "ESC resume where you
     were": you go on from there with your speed, after the same countdown, and
     the run's clock ends there. If the server refuses the resume (saves off,
     a full list) you stop where you were instead.
   On any run that is on the clock the first BACKSPACE only warns -- every way
   out of a rewind ends that run, so it says so -- and a second press within
   2 s opens it. A resume faster than a walk or a jump is practice until `!r`
   (or until you come to rest in the start box); slower, the next start
   counts. The server keeps the last two minutes of a run. After a resume,
   BACKSPACE opens at the point you last resumed from. `!r`, `!s`, `zone_goto`
   or `setpos` while rewinding a timed run takes you there and ends the frozen
   run; `retry` ends it too. While the rewind is up the save-lock keys and
   commands wait ("the save-lock waits for the rewind") -- S is the rewind's
   save -- and a key the rewind took stays its own until you let go of it.
   Movement keys held through the countdown are handed back when it ends.
   **Try:** a fast ramp, rewind two seconds, ENTER -- does the speed and the
   direction feel identical to the moment you picked? Is 3 s the right
   countdown? Is BACKSPACE a good key (it is free in default.cfg)?
2. **The drop shadow** on the timer and speed (above): too heavy, too light, or
   right? The offset is 6% of the text size (3-4 px at the defaults).
3. **The map screen.** Create server, pick a map, press **leaderboard**:
   surf_kitsune's Momentum tab has 12,624 times. Then start a map you do not
   have and watch the strip under the list. Do the KSF-only maps' pictures
   look right? Is "full data first" the order you wanted?
4. **Your Volcano tracks** from the in-game music player: do the menu's
   shaders pulse with them now?
5. **A Momentum replay.** On surf_4am, leaderboard > Momentum tab, watch a run.
   Do the key display and the mouse pad look like a player's hands now? (The Pi
   and this PC both hold the new files.)
6. **The `needs` line** on a map row: bhop_stref_amazon reads "needs CS:GO
   Portal 2 MOM mount". Is red-when-missing the right signal, and do you want
   the filter chip ("only maps I can draw fully")?

### Decisions only you can make

- **Should a stage handover be hop-checked?** (BACKLOG, "A finished stage
  run's next box is policed only for a body whose point arrives after the
  finish".) When you finish a stage by entering the next stage's box, the next
  stage starts as you leave it. If you arrive slowly through a side, the start
  is hop-checked as before; if you fly, drop or teleport in, it is not (so a
  player could stop in the box and bhop a chain, then start the stage clean).
  Checking every handover closes that, but tags an honest land-and-hop on
  teleport-staged maps, and every chained stage on a bhop map played
  off-lobby, with a tag only `!r` clears. I left it as it was before.
- **`noclip` works on the lobbies** for every player (BACKLOG, top of Ranking
  integrity): the mod's command handler takes it before the engine's cheat
  gate. Runs are marked when you noclip, but it also lifts the replay pin's
  freeze. Patch 479 would hand it to the engine's gate (off on the lobbies,
  on in single-player). Say if you want it.
- **An engine release?** Three engine patches are waiting: 468 (the touchpad,
  held for you since 3 Oct), 480 (the map list's "do I have this game") and 481
  (a server cannot load or unload content). 0.1.21 and 0.1.22 reuse the 467
  engine, so players see the `needs` names dim. Say which of the three ship,
  and I will cut one.
- **The engine security follow-up is paused, at your request (4 Oct, night).**
  Nothing changed in the engine beyond Patch 481. What is left to look at is in
  your private repo (`ENGINE_SECURITY.md`); pick it up there if and when you
  want it, or leave it.

### Where I stopped (4 Oct, night)

- Everything is committed and pushed. 0.1.22 is the current release, and the
  lobbies run the same progs as this PC's build (checked by hash after the
  release): nothing that ships has changed since, so no new release was cut.
- Next steps are in BACKLOG.md:
  - batch the Momentum import's board write before widening its backfill;
  - fix the client's replay cache before any second rewrite of the Momentum
    files;
  - ramp contact for imported runs;
  - the two key cases the re-import still gets wrong;
  - a rejected Momentum recording stays linked;
  - the demo scan's next signal (method in the private plan).
- **The four ROADMAP questions** (end of ROADMAP.md): may the Pi
  fetch more KSF ranks or Momentum demos when a player asks; how a second
  build of a map (Momentum vs CS:S) is stored and offered; and which screen
  showed you 25 KSF places.

### Found and not fixed yet

- **Three tracks cannot be finished: their END is their START** (pre-existing,
  zone data). `surf_ethereal` bonus 1 and `surf_quirky` bonus 9 have an END
  region identical to the START, `surf_flyin_fortress` main one 0.011 u
  shorter. Driven on 4 Oct on surf_ethereal b1: walking out of the start and
  back reads "run cancelled (back in the start)" and re-arms -- no time can
  ever be set there. The fix is in the zone files (move each END to where the
  track really ends) -- your call, since it means deciding where they end.
- **A modified client can steer its ghost** (the server trusts the client to
  send empty moves while ghosting). Since 478 that cannot start a clean run;
  the fix is in the engine (BACKLOG).
- **`surf_aquaflow` crashes this PC** when launched headless (BACKLOG).
- **surfd has run outside systemd since 27 Sep**: `surfd.service` is stopped
  and a `run.sh` instance serves (same DB, same logs). Harmless, but after a
  reboot the unit is what comes back. AGENTS.md's deploy recipe now reloads
  through the pidfile.

---

## 0a. From 3 Oct -- still to try

### What happened while you were away

- **Your PC did not crash.** Windows Update restarted it at 06:59 on 29 Sep and
  that killed the two Claude sessions you were driving remotely. Nothing was
  lost: their unfinished work was saved to a branch (`wip/0929-sessions`) and
  then finished -- see below. To stop it happening again, pause Windows Update
  before you travel.
- **The laptop's work is now on this PC and on the lobbies:** the milk
  visualizer (467), the touchpad fix (468), and the board/replay/save fixes
  469-473. This PC's engine was rebuilt with 467 and 468.
- **0.1.20 is released (3 Oct, 23:21)** -- https://proto.bar/ftesurf. Your milk
  menu reaches players for the first time (the 3D worlds, panels, the visualizer
  sky), with everything else since 0.1.19 and 276 fresher map bests in the
  browser. As you chose: the touchpad fix (468) is held out, there is no menu
  music, and the rewind is not in it -- it reaches players from the lobbies
  when its review comes back clean. The archive was downloaded back and its
  hashes match the receipt; its progs are byte-identical to the lobbies'.
  Everything is pushed, including the unmerged `p444wip`, `p455fix` and
  `wip/0929-sessions` branches, which now exist on GitHub as well as here.
- **`run_rearmhop` is finally 0 on the lobbies.** It was meant to be since
  27 Sep (Patch 445), but the Pi's `default.cfg` was never copied, so the old
  "stand still in the start and the hop tag lifts" rule stayed live. It is the
  repo's file now. A fluffed start now costs a `!r`. No message of the day tells
  players that yet -- your call whether to add one.

### Things to try (all live on the lobbies unless it says otherwise)

1. **Your own run's line (Patch 475).** Start a run on any zoned map. A line
   follows you with the same marks as a replay line. Fail or `!r`: it stays.
   Start the next run: the old one fades out over 2 s. Settings are in
   `hud_edit` -> Run lines (the last three rows). Tell me if it is too busy on
   by default, or if the fade is the wrong length.
2. **The in-game board scrolls past 64 (Patch 474).** Open the scoreboard,
   switch to the imported tab on `surf_utopia` (15,866 times), and scroll down:
   it loads 100 more each time you get near the bottom, up to 1,000. It should
   never blank or jump while loading. Past 1,000, the website has the rest.
3. **The website loads more as you scroll** (proto.bar/ftesurf/board/), with no
   200 cap -- the "Show more" button is still there as a fallback.
4. **KSF stage and bonus boards -- live on the website.** The first fill (03:12
   UTC, 3 Oct) died at 03:17 on a single 30-second KSF timeout after 171 map
   lookups -- a reply that never came was an unhandled error. Fixed (`ksfimport`
   now stops on "no answer" the way it stops on a refusal; commit 6088943, with
   a test that fails without it) and restarted at 05:02. It ran 2,385 requests
   and then KSF closed a connection without answering, so it stopped -- politely
   this time. It fetched 45,000 records over 288 maps and wrote 44,965 (it keeps
   a faster time already there); the database now holds **25,579 KSF stage rows
   (158 maps) and 12,376 bonus rows** -- try `surf_1day` stage 2 on the
   website's KSF tab. 1,771 deeper pages (ranks past
   ~40) are still wanted: the same command fetches them from where it stopped
   -- `cd /srv/nvme/surfd && python3 ksfimport.py --from-maps --depth 100 --max
   7000 --delay 1.0 --go` -- whenever you choose to run it. Never automatic.
### Decisions only you can make

- **The touchpad fix (468) and ranked runs** (3 Oct: held out of 0.1.20 -- still
  open for a later release). It lets a laptop touchpad turn the
  view, which it could not before. The catch, from Fable's own notes: the
  server cannot tell touchpad movement from mouse movement in a run's
  recording, and that weakens the injection check for anyone with a precision
  touchpad. It is in no release yet. My suggestion: keep it out of ranked runs
  until the run records the touchpad count. Your call.
- **A message of the day for the restart rule** (above).
- **The menu music doesn't ship** in releases yet -- ~100 MB of WAV needs
  converting to OGG (section 8). 3 Oct: not in 0.1.20; listen to the generated
  tracks first, and they can ride the next release.
- **Patch 444 sits unmerged on `p444wip`** (26 Sep, another session's): the save
  writer confirms its prefix file exists before reporting a line count
  (BACKLOG "`reclines` IS NOT EVIDENCE..."). Evidence code, so it needs a review
  round before it merges -- say if you want it taken through.

### Decisions only you can make (rewind)

- **ESC on a timed run** resumes where you were and ends the run's clock,
  rather than unfreezing the same run. Unfreezing would leave a pause the
  angle check cannot see (AGENTS.md's held-run fault) and convict the practice
  run's evidence. If you want the unfreeze back, that fault needs fixing first
  (a `pause` record at the thaw -- in BACKLOG).
- **Loading a moving save with the timer idle now asks for `!r` before a timed
  start** when it carries more than a walk or a jump could (horizontal over
  sv_maxspeed, vertical over the jump), and says so ("save: it carries speed
  -- !r before a timed run"). Two reviewers found that a save taken right after
  a rewind kept the speed and shed the tag. Saves taken in the box, after a
  finish or mid-run are tagged only when they are that fast AND the attempt
  was already hopped -- on bhop maps nothing would otherwise forgive honest
  save practice (BACKLOG, with the hole that leaves open). Coming to rest in
  the start box clears the tag, and so does loading a save that stands still.
- **Patch 455 is not merged.** Its ten review rounds sit on the local branch
  `p455fix` (worktree C:/tmp/p455fix), but AGENTS.md describes its "latency
  bound" as if live. It was another session's work, so whether to finish and
  merge it or retire it is yours -- BACKLOG "PATCH 455 IS NOT MERGED".
- **Each resume replaces your previous resume's save row**, so practice does
  not fill the list. S saves are kept, and a resume row you load again is kept.

### Fixed along the way (worth knowing)

- **A leaderboard hole older than this patch:** typing `cmd rec_watch 1` during
  a run, then `kill`, left the clock's freeze request behind -- the next clean
  run's clock stopped while you kept moving, and `cmd rec_watch 0` later
  ranked the shortened time. Respawn and the Multi-Session paths now release
  the pin, and a run that starts frozen is practice. Graded by
  `tools/p477rewind.py` R11 (fails without the fix: clock stuck at 0.015).
- **The same pin kept speed a map paid it.** A body frozen by the replay viewer
  still touches triggers, and a repeating booster (`OnTrigger` basevelocity,
  20 in the library) paid it once per firing with no friction -- kept when the
  replay closed. The pin now holds the body at rest every tick. Graded by R19
  on surf_embrace.

### Found and not fixed yet

- **`surf_aquaflow` crashes this PC** when launched headless, on both the new
  and the old engine. Try it windowed when you are home; if it crashes for you
  too, it is in BACKLOG ("surf_aquaflow CRASHES THIS PC HEADLESS").

---

## 1. The run line, and whether the defaults are right

All of this is live on the fleet now, so it works on a lobby as well as on a
local replay. Open any recording (`replay <path>`, or a board row's replay
button) and look at the line.

**What you should see without touching anything:** chevrons on the path — `V`
where the run touched ground or a ramp, a single chevron where it left one, a
double chevron where you actually hopped, two grey bars where a segmented run
loaded a save — with speed and energy beside each one.

Two defaults were my choice and are worth disagreeing with if they read badly:

- `hud_lines_marks 1` and `hud_lines_nums 1`. You asked for both on. On a bhop
  line this is a LOT of chevrons: `bhop_monster_jam` main has 438 landings and
  330 jumps in one run. If that reads as clutter rather than information,
  `hud_lines_nums 0` first, and tell me — the defaults are one line to change.
- `hud_lines_size 4` and `hud_lines_gap 40`. The mark size and the least
  spacing between two marks, in pixels. Tuned by eye at one resolution on one
  monitor, which is exactly the kind of thing that is wrong somewhere else.

**Worth trying deliberately:**

| Try | What it should do |
|---|---|
| `hud_lines_win 6` then `hud_lines_winf 2` | show only 6 s of run behind you and 2 s ahead, instead of the whole line. This is the "follow the run, not the room" mode and it is OFF by default |
| `hud_watch_path_color 2` | ground amber, ramp cyan, air pale |
| `hud_watch_path_color 3` | energy gained or lost, green to red, against the most air strafing can physically add |
| `hud_watch_path_color 4` | air control: green where your turn rate matched the target for that moment, red where it did not, **grey where there is no answer** |
| `hud_lines_nums 2` | numbers at the peaks too (where vertical speed turns over). Dense on a bhop run |
| `c` (hud_edit) → "Run lines" | all 21 settings with tooltips, no console needed |

**The one to look at hardest is `hud_watch_path_color 4`.** It is the strafe
bar's own grade, computed per sample — so the line and the bar should never
disagree about one moment. If you find a stretch where the line says green and
the bar says otherwise while you sit on that frame, that is a real finding and
I want it.

## 2. Things a headless test cannot do (from ftesurf-a1's Patches 454/455)

These are the other session's work, not mine. The list SHRANK while you were
away, and the reason is worth a line: the first version of this section said the
refusal "has never once been exercised", and that turned out to be wrong. It had
been firing on every run of the existing test all along — silently, because that
branch printed nothing. A branch with no voice looks exactly like a branch with
no traffic. It prints its reason now, and a script covers most of what this
section used to ask you for.

**2a. Finish fast on a real track.** This item has shrunk twice while you were
away and what is left is genuinely yours.

A script now drives all of it but one: `cfg/test/p455hold.cfg` earns the tag,
crosses the line, freezes the body mid-flight and watches the gate refuse for
each reason in turn — not grounded, held, still settling — before it finally
lets the tag die. It even drives the too-fast refusal, but by moving the CAP
down under a body doing 260 rather than by making the body go faster. That
proves the branch works. It does NOT prove a player can reach it in play, and
that difference is the whole reason this item survives: the fixture's runs are
nine ticks long on a bhop map and cross at 244-260 u/s, so nothing headless has
ever crossed a real finish line above the cap. That wants a human, on a track
whose END sits within 64 units of its own START:

- `surf_bikini_bottom` **b1** — a bonus, one leg, 16 u gap. Far less track to
  cover.
- `surf_summer` **main** — eleven segments, 64 u gap.

(ftesurf-a1 measured the leg counts and gaps and deliberately did NOT guess
which is the easier run — a wrong "easier" sends you to the harder map.)

What to watch for, and the ORDER matters: finish fast with a hopped start
tagged, and at the moment of the finish the forgiveness should NOT be taken —
the tag stays up. Then coast to a stop. Once you are standing still it SHOULD be
taken, and you should see a `start re-armed` line. WHICH line depends on the
build, so check both before reporting it missing:

- live today (Patch 454): `start re-armed -- the hopped start died with that run`
- after 455 ships: `start re-armed -- the hopped start was forgiven once you settled`

The wording changed deliberately — "came to rest" was an overclaim on a gate
that admits a grounded body at 259 u/s under a 260 cap.

So a tag that dies a few seconds after you stop is correct, not a bug. The defect
to report is the tag dying while you are still moving fast, because that is the
one that hands the next run a clean slate with the speed still on it.

**2a-note. Two holes were found in that gate while you were away**, both by
ftesurf-a1's reviewers, both fixed before anything shipped: a jump pad's
vertical carrier could clear the tag and then launch you (1259 outputs carry a
vertical component, out of 2029 across 297 of 1316 shipped maps — measured by
`tools/census/basevel.py`, after the first figure quoted here turned out not to
reproduce), and a pad whose impulse arrives four to six
packets after you step off it could do the same with the speed in neither field
the gate was reading. I reviewed that gate and said the first one was covered.
It was not — I had confused two similarly-named fields — so if you want one
thing to poke at on a real map, a jump pad near a finish is it.

**2a-coming. What changes when Patch 455 ships, and one part will look like a
bug.** NOT LIVE YET — the fleet runs the older gate — so this is here to be read
before you meet it, not to be tested today. ftesurf-a1's constants as of its
round 8:

| | |
|---|---|
| wait | 0.25 s of the body reading clear before the tag dies |
| observations | 8 of them inside that wait, one per move packet received |
| gap | 0.1 s — a longer gap between two observations restarts the wait |

**The gap is the one you will notice.** A client sending fewer than about ten
packets a second can never finish the wait, so the hopped-start tag STAYS UP and
your next runs record as practice until you press `!r`. That is deliberate:
without the gap the wait can be banked — send seven clear packets, stop, and
both limits sit pre-paid indefinitely — which makes the whole thing decoration.
But on a bad connection it is indistinguishable from the tag being stuck. `!r`
is the escape, with the known caveat that `!r` with jump held re-tags you within
a tick or two (that one is in BACKLOG).

Two smaller differences from the gate you have now: the message wording changes
(see 2a above), and it arrives about a quarter second after you stop rather than
instantly — invisible next to coasting to a halt, but not nothing.

**2b. Four tracks may be impossible to set a time on.** `agtricks` main,
`surf_flyin_fortress` main, `surf_ethereal` b1 and `surf_quirky` b9 each have an
END region overlapping their own segment-0 START. Read but not run: re-entering
the START while running should re-arm and cancel, so no time can ever be set.
ftesurf-a1 has taken this one and is driving `agtricks` itself — if you happen
to load one of those maps, whether a time can be set at all is the question.

## 2c. Prop collision — FIXED in four patches, and the risky part needs your eyes

You asked for this to be accurate to Source and 100% consistent between client and
server. It is now, on every path I could find, and all four are verified headlessly
(`tools/p458prop.py`, `p458phy.py`, `p460lock.py`, `p461box.py` — all green). What a
machine cannot tell you is whether the maps still PLAY, and two of the four change
what a map feels like. **THIS IS LIVE ON ALL 12 LOBBIES as of 2026-09-28** — you
said not to be scared of restarting them, so engine Patches 458 and 460 and the
mod-side 459/461 went out together and every lobby restarted with nobody on. The
prop-collision changes below are what a lobby now does, not a plan.

**The one to check first, because it is the biggest change in the set.** Source
collides a prop against its `.phy` hull or against nothing at all; it never uses the
visible mesh. Static props already followed that rule; the props this mod spawns did
not, and fell back to the render mesh. They now follow it too, and on some maps that
is a lot of props:

| map | solid props before | after |
|---|---|---|
| `surf_spacemonkeys` | 177 | **0** |
| `surf_420` | 104 | **0** |
| `surf_bikini_bottom` | 269 | 91 |
| `surf_dune` | 176 | 145 |
| `ahop_coast` | 269 | 269 (unchanged) |

On `surf_spacemonkeys` all 177 were one model, `models/que/monkeys3_detail1.mdl`,
which ships no `.phy` — so in Source those props are not solid either, and the map was
built and played that way. That is the argument for the change. But if a route on one
of those maps depended on standing on or surfing off one of them, it will not work any
more, and that is exactly the kind of thing only playing it shows. `hl2_propcollision_nophy 1`
restores the old render-mesh collision if you need to compare, and needs `sv_cheats 1`
now (see below).

**The rubber-band should be gone.** `surf_spacemonkeys`, `surf_angelinaaa`,
`surf_diet_mountain_dew` had the most scaled props; the client used to predict against
a prop 1.3750 where the server moved you against 1.4000, so you were stopped a unit or
two short of a surface you could see and then released. Prop scale is now on the 1/16
grid the wire can carry, so all four readers agree. `cl_nopred 1` is still the
discriminator if you think you see one.

**`surf_lax`** is worth a look on its own: its 144 railings used to reach the client as
8x8 posts while the server kept a 138-unit fence. They now trace their real `.phy` on
both sides. If those railings feel different, that is why.

**The menu row.** `c` -> Graphics, page 4: "Prop collide" and "Disp collide" now read
`needs sv_cheats` and do nothing while you are connected. That is deliberate — a client
that turns prop collision off predicts a world the server is not running. With
`sv_cheats 1` they work as before.

**One caveat I could not remove, and it is worth knowing.** The lock does not engage on
a listen server with ONE player slot: the engine allows cheats unconditionally there
(`cl_main.c:3253`), so testing the lock solo will show it not locking. That is correct
behaviour, not a hole — it is your own server. A lobby runs 32 slots and locks.

## 2d. Props you walk straight through are probably CORRECT

Still true, and now more so, because the rule above extends it. A prop whose model
ships no `.phy` is non-solid because Source does not collide with it either — that was
**34,514 of 110,959 solid props across 380 maps** before this change, and after it the
props this mod spawns are counted the same way. So "this prop has no collision" is
usually the intended answer, and on the maps in the table above it is now the answer a
lot more often.

The inconsistency I flagged last time is GONE: a model used as a `prop_dynamic` no
longer collides against its visible mesh while the same model as a `prop_static` is
walk-through. Both paths now ask the same question.

Each map prints its own numbers at `developer 1`, on one line, so you can check any map
yourself without me:

```
props: 534 spawned (200 solid, 486 scaled), 29 requantised, 3 non-solid (no .phy), 144 bbox->phy
```

## 2e. Momentum's zones now reach 66 maps that had no clock at all

You asked for Momentum's zones to be copied over, applied to the CS:S and `_ksf`
builds, and made editable. **All three are done and the fleet has them** as of
2026-09-28: 66 donated zone files are on all 12 lobbies and verified loading there
(`zones(sv): 6 on surf_utopia_njv (maps/zones/local) crc 4260ad9c`, the same crc
the local arm measured), and 609 files — 543 mirrors plus the 66 — are in
`maps/zones/local/` on this disk for you to edit.

**The mirrors are LOCAL ONLY, deliberately.** They are byte copies, so they change
nothing; their whole point is that you can edit them. When you edit one and want it
live, it is one `scp` to
`proto@192.168.1.102:/srv/nvme/ftesurf-server/game/ftesurf/maps/zones/local/`.
Pushing all 543 would have added risk for no behaviour change.

**If you break one while editing, it costs you the edit and not the map.** A zone
file that parses but yields no zones used to wipe the table, report success and
block the fallback — so the map went silently untimeable. It now says `loaded no
zones -- ignoring it and trying the next source` and falls back to Momentum's copy.

**What changed.** The zone loader keys on the bare map name and does not alias, so
`surf_aircontrol_ksf` had no start, no end and no timer while `surf_aircontrol.json`
sat installed one directory away. `tools/zoneinstall.py` writes the donor's file as
`maps/zones/local/<target>.json`, which is all it takes — no QC, no engine. 66 maps
went from untimeable to timed.

**The list is `ftesurf/maps/zones/manifest.txt`**, and `python tools/zoneinstall.py
--verify` prints it with a note for any file you have since edited (it will never
overwrite one of yours).

**What only playing them will tell you.** A zone is an absolute world polygon, so a
donated file is only right if the two builds share a coordinate frame. I measured
that (`tools/census/zonefit.py`: start/end polygons inside the target's world, and
the two worldspawn mins agreeing) and 61 of the 66 were clean on every check. Load a
few and see whether the start and finish boxes are where the map clearly wants them.

**Five maps I refused, and they are worth a second opinion because a false refusal
costs you a map.** These share a stem with their donor and measured as different
maps, so they still have no zones:

| map | why |
|---|---|
| `surf_derpis_ksf` | world mins 15,344 units from `surf_derpis` |
| `surf_sequoia_fix` | world mins differ by 2,368 |
| `surf_ravine_csgo` | world mins differ by 320 |
| `bhop_eazy_v2` | 5 start/end regions fall outside the target's world |
| `surf_lullaby_ksf` | same, 5 regions |

`surf_ravine_csgo` at 320 units is the one I would look at first — that is small
enough to be a re-origin rather than a different map, and if the layout is really the
same it could be donated with an offset. The other four look decisive.

**Four that work but whose restart is approximate.** `bhop_arcane_v1`,
`surf_cinnamon_fix`, `surf_medley_fix` and `surf_minuet_ksf` name an
`info_teleport_destination` their build does not carry, so `!r` falls back to the
start polygon's floor centroid instead of the authored spot (`sv_zones.qc:340`, and
it prints the missing name at `developer 1`). The map times correctly; the respawn
point may just be a bit off. On about 4% of the library that centroid is outside its
own polygon, so if one of these four drops you somewhere silly, that is why and it is
fixable by hand-editing the file.

**`surf_kitsune_mom` is the interesting one.** `surf_kitsune` is the map
`tools/mapsync.py` uses as its worked example of one name shipping at two builds, and
it now has a donated zone file under the `_mom` name. If any map is going to show a
difference between builds, it is that one.

**The other 543 maps are NOT copied, and that is deliberate.** Mirroring every map's
own zones into the editable folder is what you asked for and it is written and
verified — but it only becomes safe once the fleet runs engine Patch 463. Before that
patch, moving a byte-identical zone table from `online/` to `local/` made `pm_verify`
refuse every existing recording of that map, because the pin compared the directory
name. Measured, not guessed: on a pre-463 build all five of the existing arm's
recordings refused with the crc and the rule identical on both sides. So the mirror
is one `build.ps1 -Pi` behind, and that restarts all 12 lobbies, which is your call.

**One thing to decide.** `ftesurf/` is gitignored, so your edits to those 66 files
are not in git. If you want them versioned, say so and I will add a negation rule for
`maps/zones/local/` — worth doing before you spend an evening tuning a start box.

## 2f. The strafe trainer (Patch 462) — nobody has ever used it

`hud_trainer 1`. Off by default. Written 2026-09-28 by ftesurf-a1.

**It is live on all 12 lobbies as of 2026-09-28**, so you can try it on a real
server and not only on this PC -- which is worth doing, because the two are
genuinely different paths: the speed it grades against is the SERVER's, arriving
in a snapshot, and on a lobby that snapshot has your actual ping on it. It was
verified in both configurations before it shipped, but only by a config driving
known inputs, never by a hand.

**This is the item on this page that most needs you**, because every other thing
here was at least driven by a human once. This was driven entirely by a config:
`+right` turns at exactly `cl_yawspeed`, which is what let an arm author a known
turn rate and a known key/flick offset. No hand has touched it. It is measured
but not *used*, and those are different claims.

**What it is.** The last jump, broken into individual strafes. A timeline where
left strafes sit above the line and right below, a white tick where your mouse
actually reversed, a per-tick trace of your turn rate against the ideal, and a
row per strafe with a grade and the key/flick offset in milliseconds. One named
fault per jump, ranked worst-first.

**The number that is new** is the sync column: `+45` means the key swap landed
45 ms AFTER the flick (late, red), `-60` means it led the flick (early, amber),
`0` is green. On the timeline it is the horizontal gap between a band's edge and
its white tick, so you can see it rather than read it.

**What I would like you to disagree with, because these were my choices:**

| Thing | Why it might be wrong |
|---|---|
| `hud_trainer_x 0.28 / _y 0.27` | placed off screenshots to clear the speedometer and the Segments column at `hud_scale 2` on a 2560x1494 buffer. Another scale or aspect may collide. `c` (hud_edit) -> "Strafe trainer" drags it |
| the S/A/B/C/D/E letters | boundaries are `Strafe_Quality`'s own shape (0.96 is the +-20% band, 0.84 is +-40%), not taste — but whether an "A" *feels* like an A on a real strafe is a human question |
| `hud_trainer_rows 6` | six rows plus the timeline may be too much to read mid-jump. `hud_trainer_rows 0` is timeline-only and the box shrinks to match |
| `hud_trainer_trace 1` | the per-tick graph. Turn it off if it reads as noise |
| the coach line | one sentence, worst fault first: "key fights your turn", then "mouse N% too fast/slow", then "keys N ms late/early". If it keeps telling you something unhelpful, that ranking is one function (`Trn_Coach`) |

**The one to look at hardest.** The trainer and the strafe bar grade the same
quantity through the same `Strafe_Quality`, so a strafe the bar called good must
not come out a D here. If you find a jump where the bar sat green and the
trainer rows say otherwise, that is a real finding and I want it — they are
supposed to be incapable of disagreeing.

**Known limits, stated up front so they do not read as bugs:**

- **Flat air only.** On a ramp the ideal turn rate is a different function of the
  plane normal (between 1.8x and 6x away), and that normal is not available at
  the cadence this samples at. Ramp ticks count toward a strafe's *duration* but
  not its *grade*, and the coach line says "on a ramp — the bar grades that". So
  on a surf map the trainer is for the airtime between ramps, and on a bhop map
  it is for everything. It was built for your bhop description.
- **The panel lags by your ping.** Speed comes from the server's own velocity
  stat rather than from prediction, deliberately — prediction jitters by a whole
  tick and a per-tick speed change is one tick tall. Live steering is the strafe
  bar's job; this is the review.
- **"+N u/s" in the header is not the grade.** It is two velocity samples either
  end of the airtime, so a ramp or a booster is in it as much as your hands are.
  The grade beside it is the part that is only about your hands.
- **Both strafe keys held reads the same as neither.** The usercmd carries right
  minus left, so it is one zero and the trainer does not guess — the strafe just
  ends and the timeline shows a gap.

**If it looks wrong**, `developer 1; log_developer 1` makes it print a line per
strafe carrying every number behind the display (`trainer: R dur 345ms graded
345ms q 0.926 rate 480.0 ideal 412.1 sync +0ms wrong 0ms v 260->294`), which is
what `cfg/test/p462trn.cfg` grades. Send me that alongside what you saw.

## 2g. The segment percentage, and the air rows are yellow now (Patch 464)

Two things changed in the Segments column, one cosmetic and one arithmetic.

**The colour.** Jump / Bhop / Air rows are lemon yellow now instead of the mint
green, because you did not like the teal. The one real constraint was that the
percentage at the right of the SAME row is drawn in `HUD_QualityColor`, whose
65-85% step is an amber -- a gold air row would have matched its own figure -- so
the yellow is pushed bright and pure (`1.00 0.98 0.40`) to stay clear of it, and
clear of the launch row's pale green on the red channel. **Tell me if it fights
with the percentage anyway at your HUD scale**, because that is the thing I chose
by eye rather than measured, and it is one number to change.

**The percentage.** You were right that over 100% was impossible and the calc was
off, and you were right about where: *"anchor each energy on the previous hop...
you can only gain so much per hop."*

What I could establish without a hand on the game, and what I could not:

*Established.* The per-hop maths was already correct. A tick-accurate simulator of
the engine's own air movement, driving a PERFECT strafe, reads 100.0% through the
old code -- so build 89's anchoring (launch point on one side, jump energy on the
other) telescopes exactly, and the tickrate was already handled. That part was
never broken.

*Established.* Over-100% was real and common -- 217 distinct rows in your 463
saved `seq.txt` files, worst 8800%, and the median **Jump** row was 125%. Walking
300 `.rec` files tick by tick found the cause: 17021 air ticks move the energy
further than air strafing physically can. 8755 of those are jump impulses inside
an air run, because `pm_autobunny` re-jumps on the same tick it lands so the
client never sees a hop touch down and `hud_seq_hopbreak` -- which exists to split
the column per hop -- had never once fired. The other 7504 are boosters, push
triggers and teleports, the largest at 13407 units of height in 0.45 s.

*Established, and it killed my first theory.* The recorder's RAMP bit appears on
**none** of those ticks, so the ramp was never the cause. I had told you it was
and asked you to choose on that basis; the tick-walk said otherwise, so I built
what the data supported instead. Grading ramp rows is still worth doing and is in
BACKLOG.md as its own job -- it would give you a number where you currently get a
dash -- but it would not have moved a single over-100% row.

*The fix.* Any rise the flat-air ceiling cannot explain is added to the ceiling,
against a running high-water mark. Both sides of the fraction then contain the
booster or the unseen hop, so it is neutral, the row reads as the quality of the
strafing either side of it, and `seq_de` still holds the true energy so the column
still sums to the run. My first cut of this compared one frame at a time and was
WRONG -- it credited gains and never gave anything back on losses, so a perfect
strafe read 48.8%; the simulator caught that, not me reading it.

*What it measures.* Across perfect, sloppy, autobunny and boosted flights at two
tickrates and two frame rates: zero rows over 100%, and the sloppy rows are
byte-identical to what build 89 printed (78.9% and 69.9%). That last part is the
one I most wanted -- the new term must not be a way to earn credit for strafing
badly, and it is not.

**It is live on all 12 lobbies as of 2026-09-28**, so try it on a real server as
well as here. The two are different paths: the energy a row is built from arrives
in a snapshot with your actual ping on it, and the frame-vs-tick slack the new
rule leans on is exactly the thing a network makes messier. Verified after the
deploy by reading the host rather than the deploy script's own line -- both progs
hashes match the local build and all 12 units restarted inside twelve seconds.

One bookkeeping note for whoever next checks the release: re-measured when
0.1.15 was cut, and the drop's SERVER progs are byte-identical to the pair on the
lobbies again -- csprogs ae498503, qwprogs 8f74c5f9. menu.dat differs, and should:
it is the client menu and a dedicated server never loads it. Re-hash rather than
re-quoting this line -- it has now been wrong once in each direction.

**NOT established: no human has used any of this.** Everything above is a
simulator and a corpus of files. What I would like you to look at:

1. Does a good bhop chain read near 100% now, per hop, rather than one merged row
   with a silly number? That is the whole change.
2. Does a bad hop still read low? If a sloppy chain reads 100% the rule is being
   used as credit and I want to know immediately.
3. On a map with a booster, the boosted row should read about your strafing
   quality rather than 400%. It will still not be very informative on a row that
   is mostly booster -- there is little strafing in it to grade.
4. Any row still over 100%. There is one known way left (a purely HORIZONTAL push
   spread thin enough to hide under one tick of ceiling per frame) and it is in
   BACKLOG.md; a screenshot would tell me whether it happens in practice.

## 2h. Momentum and KSF runs are LIVE — six things need your eyes

The board went from **172 rows on 36 maps** to **85,768 on 608**: every surf
and bhop leaderboard Momentum publishes (main, every stage, every bonus, top
25 each), plus 5,281 of your own demos converted so they are watchable, plus
511 KSF times. 4,791 rows can be watched; the rest are times, which is what a
leaderboard mostly is.

Everything below is a judgement call I made for you and could not settle by
measuring.

**a) The blue tint reads as lavender, not as a glow, and I am not sure it is
enough.** `hud_watch_path_foreign 0.55` pulls an imported line's colour toward
blue. It composes with `hud_watch_path_color` rather than replacing it, which is
the part I am confident about — a Momentum line can still be read for speed or
contact AND say where it came from. But blending red toward blue makes mud
rather than light, and against `surf_4am`'s orange it is subtle. Compare
`screenshots/momline_a5_tinted.png` with `_untinted.png`: the difference is
clear side by side and less obvious in motion. Try `hud_watch_path_foreign 0.8`.
If it still reads as "slightly odd colour" rather than "someone else's line", a
real glow is a wider or additive draw pass, not a hue blend, and it wants its
own patch — say the word.

**b) The replay camera is pointed by a number nobody recorded.** Momentum demos
contain NO view angles at all — not missing, not lossy, absent — so the camera
follows the direction of travel instead. On a surf line that is close to what a
player looks at; through a teleport or a slow section it will not be. You asked
for it to look as smooth as possible, and this is the part that decides that.
Watch `replay data/momentum/surf_ruse/main/0018126_doobie-1acfa76f_run.rec` and
tell me whether it feels like watching a run or like a camera on rails. (No
`.view` sidecar is written for these, deliberately: that file is mouse evidence
and a derived angle filed there would be a measurement that never happened.)

**c) You chose "import untouched, flag only" for the 7.6 % with spiky
velocity — and it costs less than I warned.** 225 of 2,961 files have velocity
that exceeds the demo's own speed ceiling, up to 24x, because the extractor's
point array has gaps and a central difference across one divides a longer
distance by the same two ticks. I expected bright speed spikes on those lines.
Measured: the line's colour range is mean ± 2 sd clamped into min..max, so an
outlier never reaches the colour ramp. `surf_4am`'s worst file has a raw peak of
7,976 u/s against the demo's own 3,130 and the line still colours from 282 to
3,358. So the spike is real, in the data, in the header as `momquality`, and
mostly invisible. It WILL show in the live speedometer at that instant. If you
ever see a replay flash an absurd speed for one frame, that is this and it is
not a bug in the mover.

**d) Is the KSF tier worth keeping at all?** Honest answer: much less than
Momentum. 85,085 Momentum rows across 608 maps, 4,791 of them watchable. KSF gives **times only** — that network publishes no replay anything
here can fetch — and their per-map leaderboard route is one I could not find, so
it imports one player at a time, 25 records each. It is real and it works: on
`surf_garden` the combined board now reads KSF 79.884, Momentum 95.745, ours
152.115. But a row you cannot watch may be worth less to you than a clean board.
Seed it from a file of SteamID64s and see; if it reads as clutter, the tier
drops out without touching anything else.

**e) Five wrong records were on the board and I found one of them by eye.**
`surf_utopia`'s #1 read 26.565s against a #2 of 53.565s. That is not a record,
it is a broken extraction — the demo's own header reports a 10,073 u/s peak,
about 3x anything real on surf. Because the API sweep and the demo corpus now
answer for the same boards, they can be checked against each other: 5 of 4,743
demo rows beat Momentum's own #1, including a 0.405s "run" where the real
record is 92.565s. All five are gone. **The check only exists because I looked
at one board by eye** — nothing I had built would have caught them, and I do
not know what else is in there that a different glance would find. If a time
ever looks impossible to you, it probably is, and I would like to hear about it.

**f) THE COMBINED VIEW DOES NOT WORK AT REAL SCALE, and I need you to pick the
fix.** You asked for a separate tier plus a combined view, and the combined view
is built and correct: all tiers, ranked by time. At test scale that read
beautifully -- your 7.125s, your Momentum 7.320s, borobongo's 7.635s, one list.

On the live board it is useless. `surf_utopia` main has 271 imported rows and 2
of ours, and **221 of theirs are faster than your best**, so your row is at rank
222 while the client only ever fetches the first 64. You would scroll a page of
strangers and never find yourself. That is not a bug in the merge; it is the
merge doing exactly what it says on a map where you are not competitive yet.

Three ways out, and it is a question about what "compare" should mean rather
than one I can measure:

  1. **Cap the foreign rows.** Combined shows the top N imported plus ALL of
     ours. You see the best few of theirs and every one of yours. Best for
     "how far off am I", worst if you want to browse their board.
  2. **Always include your own row.** Keep the merge, but pin the local
     player's row into the page wherever it really ranks, with the rank shown.
     Honest about position, needs the client to say who it is -- /api/board
     currently has no idea who is asking.
  3. **Page it.** The board fetches one page of 64 and has no offset; adding
     paging fixes this and every other long board at once, and is the most work.

My instinct is 1 for the combined tab specifically, because the tab exists to
read one against the other, and 3 separately because the ranked board will hit
this too one day. But you are the one who will use it.

**One thing I would like you to look at that is not a judgement call:** the
`why` column on the board. It has been empty by construction since Patch 355 and
now carries `momentum` or `ksf` on exactly the rows that are foreign. If that
column ever shows a word on a ranked row, something is wrong and I want to know.

## 2i. The map roster — two decisions only you can make

There is now one list of every surf and bhop map either catalogue knows about,
pinned to the exact build this install would load: `ftesurf/data/maproster.txt`,
1748 maps, 1280 of them on a local mount and hashed -- which is NOT the number
the Pi serves (1743), nor the number the browser offers. `python tools/maproster.py check
<map>` explains any single row in English. Nothing about it is deployed and it
changes no game behaviour — it is a file on disk and a tool that writes it.

**First decision: `surf_dune` and `surf_fantasy` in `ftesurf/maps/`.**

Your gamedir wins the mount, ahead of both Steam installs. Those two files are
byte-identical to the **CS:S** builds, and they override Momentum's cuts of the
same maps. So anyone playing either one on this install is on geometry no
leaderboard knows: 45 imported runs attest to a different `surf_dune` and 5 to a
different `surf_fantasy`. They are the only two maps out of 1748 whose loaded
build contradicts the evidence — everything else is either confirmed or has no
evidence either way.

Deleting those two files makes the roster clean in one step. I have not touched
them because I cannot tell from here whether they are deliberate fixtures — 
`poop` and `surf_raqbonus3ramp` beside them clearly are, and have no upstream
build at all, so they are unaffected either way. If you put those two there on
purpose, say so and I will record why rather than keep flagging them.

**Second decision: three maps still missing, and whether to spend the bandwidth.**

28 of the 31 KSF maps you did not have are now in your Momentum install.
`surf_tycho2`, `surf_weirdcore` and `surf_yolo` are not: the fetch was stopped
partway through the 29th because the machine ran critically low on memory. That
was not a failure of the download, and re-running picks up exactly those three
(the roster recomputes what is missing from what is on disk). I have not
restarted it on my own because memory may still be tight — tell me when it suits.

Worth knowing what that cost: these are big. `surf_expel` is 335 MB unpacked,
`surf_crank` 216 MB, `surf_starvald` 195 MB. The 28 added roughly 2.5 GB.

**And one thing that is not a decision, just worth your eyes.**

The 28 new maps are CS:S builds sitting in a Momentum mount. That is fine — none
of them exists in the Momentum install, so nothing is shadowed, and I checked
that per file rather than assuming it. But they have never been loaded by this
engine. Pick two or three at random, load them, and see that they come up and are
solid. If a CS:S-built map needs content the Momentum mount does not carry, that
is where it will show, and it will show as missing textures or props you fall
through rather than as an error.

## 2j. Map downloads — 0.1.16, the library is complete, and wrong builds are fixable

### Get 0.1.15 first. 0.1.14 cannot show you this feature at all.

You downloaded a build and there was no Download button. That was not the
feature failing — it was never in a release. Two separate faults:

1. **0.1.14 was built at 13:33 and the map-download work landed 19:41–20:17.**
   Six hours later. The source was pushed; no release contained it.
2. **Rebuilding alone would still have shipped a button-less list.**
   `data/mapdl.txt` is gitignored, and the release ships a *named* list of data
   files that did not include it. Without that file the map list is built purely
   from what is already on your disk, so every row is an installed map and
   **nothing draws a button**. The feature was compiled in, working, invisible.

Both fixed. `https://proto.bar/ftesurf` now serves **0.1.16**. If the button is
missing, check the version before anything else — that is by far the likeliest
cause, and `data/mapdl.txt` should exist in your install with ~1743 lines.

### What you have now

    bhop      131 -> 574 of 574     100%
    surf     1146 -> 1169 of 1174    99.6%
    offerable 1277 -> 1743 of 1748

463 maps were pulled from Momentum's CDN straight onto the Pi, each checked
against the publisher's own sha1 before being installed. The Pi holds 1813 bsp.

**The five that are left are not a backlog — they cannot be got.** Four are KSF
names with no archive behind them and no Momentum record (`surf_disappointed_fix`,
`surf_junglepics_ksf`, `surf_race_final`, `surf_vestige_fix`); the fifth,
`surf_solipsism`, has a Momentum record whose download URL 404s on their side.
Nothing to do about any of them from here.

KSF is finished: 931 Drive archives indexed, not one for a map we lack.

### What to test in game

Launch `ftesurf.bat` from the 0.1.15 install.

1. **The list is much longer** — 1743 maps, the ones the Pi can actually serve.
   The ones you do not have carry a **Download** button on the right with the
   file size under it.
2. **Click one.** The button becomes a progress bar with a live KB/s figure.
   Other rows say `queued`; the engine does one at a time, deliberately.
3. **Press ESC mid-download.** It should keep going and still say `installed`
   when you come back. The tick that notices completion runs outside the menu
   gate on purpose. **This is the bit most likely to be wrong and no human has
   ever done it** — the harness drives `ui_dlmap`, which cannot press ESC.
4. **The row should become a normal map** once it lands, without a restart.

Expect roughly 1 MB/s. That is the cap you asked for, applied on the Pi.

### Do not expect NEW badges on these 463

They will not badge, and that is correct. `NEW` means "a sweep saw this name
appear in the catalogue", not "recently downloadable". These maps have been in
the catalogue all along — what changed is that the Pi can now serve them. A
badge here would mean the opposite of what it says everywhere else.

The six-hourly scan is registered and healthy (last run 18:07, result 0, next
00:07). New Momentum or KSF releases picked up by a future sweep *will* badge.

### What is already proven, so you need not re-check it

- **The Pi serves the right bytes.** `bhop_pandora`, fetched an hour before the
  release, pulled over https at 1,041,220 B/s with a sha1 identical to the Pi's
  copy. Both url layouts resolve; directory listing and `../` traversal 404.
- **An interrupted download cannot corrupt a map.** This was a real bug and you
  would have hit it: a part-way http transfer used to leave a TRUNCATED .bsp
  under the real name, which looks installed, stops the button offering it, and
  mismatches mapcrc — silently demoting every run played on it. Downloads now
  land in a `.tmp` and are renamed only once whole. Same discipline on the Pi
  side: 464 transfers, zero leftovers.
- **Six maps could never have downloaded** — the catalogues lowercase names and
  the Pi does not, and Linux paths are case-sensitive. Now matched by fold.
- **The published archive is the right one.** Re-downloaded from dl.proto.bar
  after publishing: sha256 matches and `mapdl.txt` inside carries 1743 rows.

### The laptop kick, and what 0.1.16 does about it

You loaded surf_666 on a laptop with no CS:S or HL2 and got kicked:

```
Map model file does not match (maps/surf_666.bsp), 0XC6702B74 != 0X77D2E0BD
You have been kicked due to the file maps/surf_666.bsp being modfied
```

and asked whether the map should have downloaded. **It should not have, and it
did not, and that was correct** — you already had a file called
`maps/surf_666.bsp`. Nothing to do with the missing CS:S or HL2.

What was actually wrong: your copy is a **different build** from the server's.
Measured before changing anything —

```
roster surf_666   sha1 cb5343da…   pin=ok, 53 demo attestations
this workstation  cb5343da…
the Pi (server)   cb5343da…        identical, and the pinned build
your laptop       a third thing
```

— so the Pi is serving the right cut and your Momentum install is the odd one
out. The browser had no way to tell you that and no way to replace it, because
it only ever asked *is there a file of that name*.

**0.1.16 asks about the build instead.** A map whose size does not match the
server's now draws **Wrong build** with `re-get <size>` under it instead of a
time. Clicking it downloads the server's build into `ftesurf/maps/`, which wins
the mount — **your Steam install is never touched or deleted**, it is shadowed.
If the re-get fails you keep the old map rather than ending up with none.

**What to do on the laptop:** open the map list, find surf_666, and if it says
Wrong build, click it. Then rejoin. If it does NOT say Wrong build, tell me —
that means the two builds are the same size and different content, which this
check cannot see (below), and I will need a different signal.

**The honest limit.** The check compares file size. A size difference is proof
of a different build; **equal sizes are proof of nothing**, so it under-reports
and will never accuse a correct install. That is deliberately the safe way
round, because the action it offers spends your bandwidth.

**It found your two open questions on its own.** On this workstation the count
comes up 2, and the two are `surf_dune` and `surf_fantasy` — the exact pair 2i
above has been asking you about. That pair was originally found by hash
attestation; this found it by file size, from the other end. Two independent
methods, same two maps, which is the strongest evidence 2i has had. The sizes
are not marginal: surf_dune is 149 MB here against the Pi's 20.7 MB.

### About CS:S and HL2

You do not need either for downloads to work. But your log says neither is
installed (`fs_load: steam game "Counter-Strike Source/cstrike" not
found/installed`), and that will cost you textures on most surf maps. For
surf_666 specifically the engine reported those 38 materials as supplied by no
pack at all, so CS:S would not have fixed those particular ones — but it will
matter broadly. Worth installing when you can.

### One thing I found in your log and have NOT fixed

```
Downloading https://play.proto.bar/play.proto.bar/sp to maps/dlcache/surf_666.bsp...
```

That URL is malformed — `<base>/play.proto.bar/sp`. The sound download two lines
later used the correct shape, so `sv_dlURL` is fine; it is the engine's own
post-kick map-repair path building a bad remote name. Traced as far as
`cl_parse.c:1045-1047`, the `package/` branch, and **not** root-caused. It only
fires once you have already been kicked, so the Wrong build button gets you out
of that situation first. Left open deliberately rather than guessed at.

### Still waiting on you

- **`surf_dune` / `surf_fantasy` from §2i** — unchanged by any of this, and
  still the only two of 1748 whose loaded build contradicts the evidence.

## 2k. The map browser, rebuilt (build 89) — seven changes, four to look at

You asked for six things and then for the Play button. All seven are in and
measured (`python tools/b89browse.py`, PASS). Four of them are lettered below
because they are choices I made rather than facts I found, and you may want
them differently.

**The download button had run out of room.** It was a flat 92 px and
"re-get 149.0 MB" needs 127. The width is now asked of the font rather than
typed: `ui_dl_gutter` measures the widest label and the widest re-get line and
returns 127 on this install. The test FAILS if 92 would have been enough, so
the premise is checked rather than assumed.

**The best known time sits above yours.** New column, from
`data/mapwr.txt`, which `tools/mapwr.py` reads out of the Pi's board. **736 of
1833 listed maps have one** — and 586 of those are Momentum's imported
leaderboard and 150 KSF's, so on nearly every row that number is another
community's world record rather than anything set here. It is labelled `best`
and not `WR` for that reason. The rest of the rows show nothing on that line,
which is honest and is most of them.

- **(n) It is a SNAPSHOT.** Regenerated at release time, not live. Re-running
  `tools/mapwr.py` takes a few seconds. Live would mean a new public endpoint
  and a fetch on a screen that currently works with the Pi switched off; say if
  you want that instead.

**The times moved left** — 20 px of clearance instead of 8 — and both now sit on
the row's own two lines, best above, yours below.

**Tier order.** Tier 1 first, then 2, and everything nothing knows a tier for
at the bottom in one block. Within a tier the order is unchanged (alphabetical).
The old order went backwards 832 times over 2271 rows, which is what it looked
like.

- **(o) A side effect worth knowing.** Maps you do NOT have are appended to the
  list last, and the sort is stable, so within each tier the installed maps come
  first and the downloadable ones follow. A Download button is therefore never
  on the first screen of a tier. I think that is the right way round — the maps
  you can play now lead — but it is a choice, not a consequence of anything.

**The missing tiers were not missing.** 462 maps drew `--` while a real tier for
them sat in `data/mapdl.txt`, which this menu already opens: `maproster.py`
falls back to KSF's roster wherever Momentum has no record, and nothing read it.
They now draw `T3k` — the `k` marks a KSF ranking, the way `?` marks a
suggestion and `~` an inherited one, because KSF's scale and Momentum's are not
the same scale. **469 rows gained a tier. 128 maps have no tier from anywhere**
and still draw `--`; that is the honest answer for them and I have not invented
one.

- **(p) Is `T3k` the right mark?** It is the only two-letter one. If it reads
  badly beside `T3?` and `T3~` I will change it.

**The library switch** is a new `both / momentum / cs:s` strip under the tier
chips, and it filters the download offers as well because those are rows in the
same list.

- **(q) It reads the CATALOGUE now, not the mount, and that changed after you
  reported 30 surf maps in the CS:S list.** It first filtered on which mount
  supplied the file, which is wrong for exactly the maps the switch exists to
  separate: 463 of the offerable maps are in both catalogues, and on a machine
  with no CS:S mount every one Momentum also ships read as Momentum-only. The
  letters `data/mapdl.txt` already carries are now folded in. Here that moved
  cs:s 1027 → 1080, which is deliberately small BECAUSE this box has CS:S
  mounted; your laptop is the case it is for, and it should show something near
  925 rather than 30. **If it still shows ~30, that is the thing to tell me** —
  it would mean the count tracks what is installed rather than what the
  catalogue lists, and I have not proven which of those you were seeing.

**A green Play button** now fills the action column on every row you already
have, which you asked for after seeing it empty. It goes through the same launch
path the start button does, so the terms and name screens still come first.

### What I could not check

The Play button and the whole layout are in
`ftesurf/screenshots/ui_menu_create.png` and I have looked at it. **The Download
and Wrong build buttons are NOT in that shot** — every map on the first screen
is installed — so their width is verified by measurement (127 px against a
111 px string) and not by eye. If a size still looks cut off on your machine,
that is the thing to tell me.

### One defect this turned up, already fixed

Since build 58 every map the browser appended from `data/mapdl.txt` was written
81 rows away from where its name went, because `bufstr_add` appends at the
buffer's physical end and the list's row count is smaller than that. It was
invisible for four builds because the columns it corrupted are all-identical
down the list. Build 89's tier column was the first one with a second opinion to
disagree with — 550 against a possible 469, and 550 − 469 is exactly the 81 rows
the list drops. Nothing to do on your side; noted because it means map sizes and
NEW badges on downloadable rows were wrong before today.

---

## 2l. Joining a lobby now fetches the map -- and one download bug behind it

You were kicked from a public lobby on surf_rookie and asked whether it could
just download the right map when connecting. It does now (0.1.19): clicking a
lobby, or letting the directory pick one, holds the connect, fetches the
server's build into `ftesurf/maps/` and then connects. It never touches your
Steam install -- the file shadows the mount rather than replacing anything.

**The thing worth knowing is why my first test of it failed.** `sv_dlURL` was
EMPTY at runtime on this box. `cfg/default.cfg` sets it to
`https://play.proto.bar`; `ftesurf/ftesurf.cfg` -- the config the engine writes
when it quits -- holds `sv_dlURL ""`, and it is read AFTER default.cfg. The
saved empty value wins, silently, and then every map download fails with **no
message at any layer**. On a box in that state the Download button has never
worked.

Your original report on 0.1.14 was "it had no map download option. It just
failed." I put that down to the release being stale and the data file not
shipping, and both of those were true -- but this may well have been the "it
just failed" half, and I did not find it then. 0.1.19 repairs an empty value on
launch and leaves a mirror you set yourself alone.

- **(r) surf_rookie may or may not be fixed, and one look tells us which.**
  Measured: the Pi's copy and this workstation's are byte-identical -- same
  8,377,611 bytes, same sha1. So your laptop holds a third build. Find
  surf_rookie in the map list:
    * **"Wrong build"** -> click it, rejoin, done. The size differs and the
      check can see it.
    * **"> Play"** -> your copy is a different build of the SAME SIZE, which no
      check in the client can see. Tell me, and I will do the engine patch that
      reads the server's own `//kickfile` message -- it names the exact file --
      and repairs it automatically. I have not started that, because if the
      first case is what you have, it buys nothing.

- **(s) Two negative cases matter as much as the positive one.** A join-check
  that holds a join it should not have held is a player who cannot join
  anything. So a map you already have, a map nothing has heard of, a transfer
  already running and a fetch that will not start ALL connect exactly as before.
  Only a fetch that fails on a map we know is wrong refuses, because arriving at
  that kick slowly is worse than arriving at it at once. If a join ever hangs on
  "holding the join", that is the bug to tell me about.

---

## 3. Known limits of the line, so they do not surprise you

These are in BACKLOG.md with the detail; the short version:

- **A hop whose ground contact falls between two network packets has no mark,
  and cannot have one.** Samples arrive 43-65 times a second against a 66.67 Hz
  tick, and a bhop's contact is one tick. The Segments panel misses exactly the
  same hops, which is why the two never disagree — but a chevron count on a bhop
  line is an undercount, not a total.
- **Air control is graded against the settings of the server you are ON**, not
  the one the recording was made on. The strafe bar has the same limitation, so
  they agree with each other; they would be wrong together on a recording from a
  differently-configured server.
- **The mark cap (4096 a run) has never been reached by any test.** The policy
  for exceeding it — drop the peak markers first, then stop and say so — is
  written but unexercised, because the longest recording available produces
  2158. If you ever watch a run and the console says marks were dropped, that
  path has run for the first time and I would like to know what it looked like.

## 4. If something looks wrong, what to send

`replay marks` (the mark table), `replay colours 0 32` (the colour of every
32nd point plus the movement settings it was graded against) and `replay
marktrace 2` (what the next two frames actually drew, including each label's
text and screen position) all print to the console, and `ftesurf/logs/` keeps
them with `log_enable 1`. Any one of those plus the recording is enough to
reproduce a bad line exactly.

## 5. The website, and what I want you to look at

`proto.bar/ftesurf/board/` is live with all of this on it. It reads the real
database, so every number below is one you can click.

- **The map list** now says 766 maps, 740 with times, 4,791 runs to watch. Tier
  chips (T1-T10) filter by Momentum's own difficulty rating; 380 of your 536
  playable maps are rated, the rest say Unrated rather than pretending to be
  tier 0.
- **Any row with a demo has a Watch button.** That opens the run: the path
  coloured by speed, a dot you can play and scrub with the u/s it was carrying
  at that instant, and a speed strip you can click to seek. Pausing puts the
  moment in the address bar, so `#r=5&at=31` shares the exact frame.
- **Player search and profiles.** Click any name. ~5,000 people, times,
  records, top tens, maps finished, and a completion bar per difficulty tier.

### Judgement calls for you (2h continues)

- **(g) DONE -- the profile leads with 35 now.** You chose "show 35, note it's
  mostly uncontested", so the big number is first places and a small grey line
  underneath says how many were against somebody else. Your Momentum profile
  reads 1,629 times / 35 first places / *0 contested* / 17 top tens; ours reads
  128 / 109 / *24 contested* / 43. The word "contested" is mine, not standard
  -- say if you want it to read "0 against others" or "0 head-to-head".
- **(h) DONE -- imported dates are real now.** 81,290 rows backfilled from
  Momentum's own `created`; the board reads 2025-10-07, 2026-06-20 and so on
  instead of one afternoon. Nothing of ours moved (checked row by row against
  the pre-backfill database: 0 ranked/community/ksf rows changed). ~3,795 rows
  sit below the cached top-25 and still show the import date; they are counted,
  not guessed at. Say if you would rather they showed nothing than show a date
  that is ours.
- **(l) DONE, and it found exactly one row.** You chose "tighten the check".
  The allowance is now whichever is *smaller* -- 0.5%, or 20 milliseconds --
  so short runs keep the percentage (18 ms on a 3.7 s record, tighter than the
  floor anyway) and long ones stop getting a quarter of a second of slack.
  Run across all 3,726 cached boards it flags **one** row:

      surf_utopia  main  53.565s vs 53.625s official  -0.060s  z3nE柊

  So it is one bad demo extraction, not a pattern. **Nothing is deleted** --
  removing it needs a flag I have not passed, because wiping a row off a
  public board is not mine to do on my own. Say the word and it is one
  command; the demo file stays on disk either way.
- **(i) The imported tint is 0.45 on the web line** against 0.55 in the game.
  Look at a MOM run and an OURS run side by side and tell me whether the blue
  reads as "different source" or just as "blue".
- **(j) Momentum profiles link out to momentum-mod.org.** Your own guid never
  leaves the server -- the site's player ids are a hash -- but an imported
  player's steamid is published, because their own leaderboard publishes it.
  Say if you would rather it did not.
- **(k) 740 of 766 maps now have times on a public page**, most of them other
  people's. You said yes to this; it is worth seeing at full size before it is
  indexed by anything.

### The admin page, and the prestrafe

- **Your run-review page folds up now.** Verdicts, Receipt, Key and the raw
  recording header are behind dropdowns, but each one still says its state on
  the closed line -- `[PASS] 1 current`, `[FIRST KEY]`, `[UNREADABLE] no file
  on this node` -- and anything flagged opens itself. It also has the same
  moving dot the public page does. Nothing about approving or rejecting a run
  changed; that was checked line by line.
- **(m) The public viewer could not reach the prestrafe and now can.** A
  recording starts about two to four seconds before the timer does, and the
  scrubber used to start at 0:00.000 with that span drawn off the edge. It
  opens at `-0:02.130` on your surf_utopia run, standing still, and the speed
  strip shades the pre-timer part. Tell me if you would rather it opened at
  0:00 and treated the prestrafe as an extra you scrub back into.

---

## 6. Builds 0.1.18 / 0.1.19 — five things you asked for, and one shape

**The current build is 0.1.19** and everything below is in it. I checked that
by downloading the published archive back and listing it, not by trusting the
build log: 12 voice icons, 609 zone files including surf_666, 6 thumbnail
atlases, and zero of the source art or the 1.1 GB of screenshots that must not
ship. Worth re-checking after any release, because a ship-set regression is
completely silent — which is the whole point of this section.

**Four separate complaints turned out to be one shape:** something the game
asks for by name, silently absent, presenting as a broken feature. Three were
files the release list never named (zones, map screenshots, voice icons). The
fourth was ftesurf-a1's: a value saved in your own config quietly overriding
the shipped one, so map downloads could never start. None of them were broken
logic, and none of them printed anything.

### The one sentence version

**Three sets of art and data that the game asks for by name have never been in
a release archive.** Not broken code — the ship list in `release.ps1` simply
never named them. Every install anyone has ever downloaded was missing all
three. They are in now.

### (1) The tabs at the top — fixed, already live

Two separate bugs. `Leaderboard` stayed lit no matter which page you were on,
because which tab is highlighted was written into the HTML once and never
moved. And the download page had **no Players tab at all**, so from there the
player list was unreachable. Both fixed; the lit tab now has a blue underline
so it is obvious.

Nothing to install — refresh `proto.bar/ftesurf`.

### (2) Map screenshots on the site — done, already live

Every map page opens with a picture of the map. 630 of the 740 maps on the
board have one. The other 110 draw nothing at all — no grey box, no broken
image icon, the page just starts at the title.

### (3) surf_666 had no zones — and neither did any other map

You reported this on the laptop. It is much bigger than one map: **no release
has ever contained a single zone file.** I checked all twenty release folders
on disk; every one has zero. So a fresh install could not time or rank *any*
of the 587 downloadable maps we hold zones for, and said "no legs and no
times" on all of them. surf_666's zone file has been sitting in this tree the
whole time.

2.5 MB added — a tenth of what the map thumbnails already cost.

There is also a second half for maps zoned *after* a release: the client asks
our own server for a missing zone file. **You ran the nginx command, so this
is live and proven** — see the end of this section for the round trip.

### (4) The error texture behind the create-server menu

You said the map screenshots "show as error". The comment in our own code
claimed a missing image draws nothing. **It was wrong**, and I only found it
by reading the engine: `drawpic` substitutes the checkerboard `no_texture` and
draws it anyway.

So now every map gets a backdrop, from the thumbnail atlas **we already
ship** — blurred, as you asked, which hides that it started life 128x72. Costs
zero extra download. If a map has a full-size screenshot on your machine
(because you have Momentum installed) you still get the sharp one; the blur is
the fallback.

I verified this by hiding both image sources and looking at the actual
screen — not by reasoning about it. The blur draws, and no error texture.

### (5) The mic and speaker icons — same bug, found because of (4)

You asked for these to be in the build, and checking turned up why they
mattered: `gfx/thumbnails/` has never shipped either. The player list draws
one of these beside **every** name with the same `drawpic` as above — and the
idle state `speaking_off` is always on screen — so a shipped install has been
drawing a small error texture next to every player, permanently.

12 files, 31.5 KB. The `dark/` and `light/` folders beside them are your
source art (SVGs and a PowerShell script) and deliberately do not ship.

### What to actually test on the laptop

1. **Create server screen.** Arrow through maps. Every map should have a
   blurred backdrop. Nothing should ever be a checkerboard.
2. **Player list** (while connected). The mic icon beside each name should be
   a mic, not a checkerboard.
3. **surf_666, or any map you download.** Join it and open the leaderboard.
   It should have legs and times now instead of "no zone file".
4. **The website tabs**, and click a map to see its picture.

### The zone download works — you ran the command, so I could finally test it

Proven end to end, not reasoned about. I parked surf_rookie's zone file *and*
Momentum's own copy of it, so the game genuinely had none, and watched the log
say so and then fix itself:

```
zones: none for surf_rookie
zones: 19 on surf_rookie (maps/zones/dl) crc d1eaee84
```

The second line can only exist if the game asked our server, got the file,
wrote it and re-read it. The `crc d1eaee84` is the same table Momentum's own
copy produces, and the downloaded bytes hash identical to both the server's
copy and the shipped one. The mirror also refuses what it should: no directory
listing, no path traversal, and a map with no zones gets a clean 404.

Two runs before that one measured nothing, and both said so rather than
passing quietly — the first never loaded the map at all, the second was still
reading Momentum's copy.

### What I could not check

- Nothing on a real laptop — every screenshot above is from this desktop.
- **A map you download on joining a lobby.** The zone fetch is proven for a
  map already installed; the join-time case runs the same code but I have not
  driven it.

## 7. The boards are filling in — we had 2.8% of Momentum's times

You asked whether we have the tools to get all the Momentum times, whether we
can build them up slowly, and whether we keep them updated. We had most of the
machinery and one character was throwing away 97% of the data.

### What was wrong

`momfetch.py` built every request with `&skip=0`. So `--take 25` was not a
default, it was a **ceiling** — the tool could not ask for place 26 of anything.

| | |
|---|---|
| times we held | **81,290** |
| times that exist on Momentum | **2,927,709** |
| coverage | **2.8%** |
| boards stopped at exactly 25 places | 2,914 of 3,726 |

Momentum's API pages perfectly well. I checked by hand before changing anything:
ask for `skip=100` and you get ranks 101–200, continuing exactly where the first
page stopped. Nothing had ever asked it to.

### What happens now

The Pi's cron does three jobs every 7 minutes instead of one:

1. **maps people are on** — boards get refreshed if stale *and* deepened if short
2. **maps opened on the website** — opening a map's page on the board queues it,
   and the next tick prepares it
3. **a background crawl** — 15 pages a tick into whichever boards are shallowest

That third one is the "slowly build it out" you asked for. At ~3,000 requests a
day it reaches every place on every board in about **10 days**, unattended.

The website queue is deliberately a *queue* and not a fetch: opening a map page
writes one row in our database, and our cron spends it later on our own
schedule. A visitor never causes a request to Momentum. That matters because
otherwise anyone who found the page could spend our rate limit for us.

### One thing worth your decision

**Nothing we serve can display a rank past 200.** That is our own limit
(`BOARD_LIMIT_MAX`). So of the 2.9M times now being collected, about 450,000 are
reachable by any reader and the other 2.5M are being stored for a feature that
doesn't exist yet — "where would I rank", or searching for a friend's name.

You picked full depth knowing that, which is fine. But it's either worth building
that feature or worth stopping the crawl at 200. Doing neither means paying for
rows nobody can see. It's in BACKLOG.md either way.

### Five faults I hit doing this, four of which only testing found

I mention these because each one looked like success:

- **`--refresh` made a tick pointless.** Refresh re-reads page 1, and page 1
  sorts ahead of every deeper page — so a small budget spent itself re-reading
  ranks 1–25 we already had and gained **zero** rows, while the crawl beside it
  gained 50 from the same budget.
- **Refreshing a board would have truncated it.** Replacing page 1 instead of
  merging looks right, and would have cut every played map's board back to one
  page **every 7 minutes**.
- **A wrong row count would have looped forever.** If Momentum's own total is a
  few high, the crawl asks for a page that doesn't exist, gets nothing, and asks
  again next tick — for good. Proven by planting a false total and watching it
  self-correct.
- **The indexer would have run out of memory.** It re-read all 3,726 files every
  7 minutes and held every row in memory: fine at 84k rows, about **2.3 GB** at
  full depth, on a Pi with 1.0 GB free. It's incremental now.
- **And the incremental check was wrong twice, subtly.** It remembers a
  timestamp, and no decimal version of a file's timestamp survives a round trip —
  one file stayed "changed" forever, both times. It would have looked like it
  worked to anything that didn't demand *zero* files re-read.

### KSF — the route exists, and it isn't an API

> **WRONG, and superseded by section 0 (2026-10-03).** The same session found an
> hour later that KSF *does* have a proper paged JSON API, with stage and bonus
> boards. It is built now; see section 0. The text below is kept as written.

You gave me the `ksf.surf/maps/surf_dragonfall` link. That was the missing piece,
and it explains why two earlier attempts failed: **there is nothing to find in
their API.** The leaderboard is built on their server and baked into the page, so
every records endpoint in their site's code is per-player, and searching it
correctly could never have turned up a per-map one.

The map page URL *is* the route. What it gives:

- **exactly 10 rows**, and no paging at all — asking for more returns the same 10
- **main track only.** Stage and bonus boards are not reachable this way, even
  for a map with four stages and seven bonuses
- the four styles (`fw`/`sw`/`hsw`/`bw`) do work

So it's worth about **7,400 times across ~740 maps**, against the 666 KSF rows we
hold now. I have **not** built it, on purpose: reading that page means parsing
their web framework's internal data format, which will break the next time they
deploy and will break *silently*. That's a maintenance commitment rather than a
patch, so I want you to say yes to it knowingly. Say the word and I'll build it
with an alarm that fails loudly on a format change rather than quietly importing
nothing.

Two things in our own notes turned out to be false and are now corrected: we
claimed KSF publishes no replay files anywhere (they list filenames), and that a
KSF run's map build could *never* be checked (they publish the map as a zip, and
a zip can be hashed). Both conclusions still hold — we still can't watch a KSF
run — but they were resting on wrong reasons.

---

## 8. The milk visualizer (Patch 467) -- what only you can judge

Written 2026-09-29 on the laptop. Everything below was built and photographed
headless; none of it has been LOOKED AT by a person moving a mouse, with the
sound on. Run `ftesurf.bat`.

**What you should see without touching anything.** The main menu sits in a dark
3D space: a GameCube-style lattice of glowing cubes turning slowly over a
reflective floor, motes drifting, the tunnel's rings glinting behind it. PLAY /
VISUALS / MUSIC / QUIT on the left in Bebas. Hovering a row slides it right,
lights an accent bar, and leaves a glow that smears away when you move off it.
Changing screen flies the camera: PLAY to the spectrum towers, VISUALS into the
ring tunnel, MUSIC to the orb pool. The first file in `ftesurf/music/` plays.

**Things a headless run could not do -- try these:**

| Try | What it should do, and the question |
|---|---|
| Move the mouse slowly across the main menu | The whole space turns a few degrees after it, eased. Does it feel alive, or seasick? (`MM_Camera`: 16 deg yaw, 8 deg pitch, time constant ~0.3 s) |
| Hover PLAY, then MUSIC | The camera leans toward where each would fly. Noticeable? Too much? |
| Play a track you know well, watch the towers and the orbs | Do the beats land ON the beat? The analysis is aligned to DirectSound's play cursor (measured ~95 ms of mix-ahead removed); the Windows audio engine's own delay (~10-30 ms) is not, so visuals may lead slightly |
| VISUALS: audio reactivity "wild" | You already picked it. Is it too much on a busy track? |
| VISUALS: in-game sky "visualizer", then surf an open map with music on | Epic, or does it hurt reading the ramps? It is OFF by default for that reason |
| MUSIC: "muffle game in menu" on, open the menu mid-run | Game audio should low-pass to ~900 Hz over a quarter second and come back when you close it |
| VISUALS: menu scene high | On this N100 that is ~35 fps in the menu (medium ~145). Your main rig should not notice either |

**Decisions only you can make:**

- **Ship a menu track?** `python tools/mkmenumusic.py` wrote
  `ftesurf/music/ftesurf_dream.wav` (76.8 s ambient loop, generated, no licence
  question) -- but it is 13.5 MB of WAV and not in git or the release. Ship it as
  an OGG, commission a real one, or leave menu music to the player. Taste
  matters more than bytes here: is the generated one any good?
- **Music after the menu closes.** It keeps playing into the map (the sky is
  built to react to it). Stop it on join instead?
- **Defaults:** scene medium, trails full, reactivity normal, sky OFF, menu
  music "auto" (first file in `music/`).

**On your main rig:** pull both repos, `build.ps1 -Engine` (the audio analysis is
engine Patch 467 -- without it the visuals run but ignore the music, and VISUALS
says so), then run. Nothing reaches the lobbies until a `-Pi` deploy.

**Known limits, so they do not surprise you:** OpenGL only (Vulkan/D3D get the
old flat backdrop); the OpenAL output skips the software mixer, so no analysis
there (`s_al_disable 1`); the menu space only runs while you are NOT in a game.

---

## 9. The menu worlds, panels in the world, and six tracks -- what only you can judge

Written 2026-09-30 on the laptop. Built, photographed and measured headless;
nobody has moved a real mouse over it with the sound on. First run
`python tools/mkmusic.py` once (about four minutes): it writes the tracks and the
menu's sound effects, which are generated, not in git.

**Your config says `milk_panels "0"`** -- flat panels. That was written by your
own session at 00:16 (it holds your music volume and frame cap, not the test
harness's), so it was left alone. VISUALS -> Menu panels -> "in the world" is
the new thing.

**The worlds (VISUALS -> Menu world):**

| World | MAIN | PLAY | VISUALS | MUSIC |
|---|---|---|---|---|
| lattice | the cube lattice | tower field | ring tunnel | orb pool |
| monolith | a pier over a 400 m void: bridge, a lone figure in a shaft of light, a forest terrace, a waterfall into the abyss | inside that forest (behind the dialog) | a corridor that does not end | PS2 towers of light cubes over flooded concrete |
| vessel | an artery, red cells tumbling past | darkfield plankton | an iris whose pupil breathes with the bass | leaf cells, chloroplasts streaming |

Changing world dives: the camera plunges on, the scene swaps at the bottom of
the plunge, and "auto" menu music changes to that world's track.

**Try these:**

| Try | What it should do, and the question |
|---|---|
| Hover the menu entries on a panel | The text should be exactly as sharp as before (one texel per pixel at rest). Is it? |
| Move the mouse off the panel, to the right | The camera orbits round the panel; the world swings behind it. Moving back onto the panel settles it exactly. Too much? Too little? (`MM_Camera`: 30 deg per screen of distance) |
| Click VISUALS / MUSIC | The panel you leave collapses like a CRT; the next scans on as you arrive |
| Menu sounds on | Hover ticks, a deep click, whooshes on flights, a boom on a dive. Too loud? |
| Listen to `ftesurf_monolith` | A generated male choir (formant synthesis) in a long room. Does it read as voices, or as a synth? |
| `ftesurf_drive` in a run with the visualizer sky | The one track made for surfing (120 BPM) |

**Decisions only you can make:**

- **Default world.** New installs start in `monolith`. Or `shuffle`?
- **Default panels.** New installs get "in the world"; you have chosen flat.
- **Ship the audio?** Six tracks and five effects, all generated. OGG and a
  release line, or leave them to `mkmusic.py`?

**Measured here (N100, medium, MAIN):** lattice 86 fps, monolith 74, vessel 101
(flat panels: lattice 122). The two new worlds raymarch every other tick. Your
main rig will not notice any of it. (Superseded by section 10's table.)

---

## 10. Calmer beats, a cool grade, the x-ray films -- what only you can judge

Written 2026-09-30 on the laptop, after your notes on section 9. Built,
photographed and measured headless; not yet seen on the 360 Hz PC.

**Reactivity.** The full-screen flash used to fire on every onset the engine
found -- hats included, up to 7 a second on `ftesurf_drive`. Now it, the zoom
punch and the shaders' beat pulse answer only the big hits: a kick well above
the track's average bass, or a snare with body in the mids. Replayed over the
generated tracks (`tools/p468react.py`): 0.4-2 big hits a second where there
were 1.4-7 flashes, and at your setting the average flash is 4-8x weaker and
its peak a third. Your config has
Audio reactivity on **wild**; wild is now what normal used to be, and normal is
a bit over half of that.

| Where | What changed |
|---|---|
| vessel, MUSIC (leaf cells) | The "freakout" was a bug, not taste: the chloroplasts' speed moved with the music, and their position is time x speed, so each change teleported them round their cells. They now stream at a steady pace; only the walls' glow follows the music, and gently |
| vessel, MAIN (artery) | The heartbeat leads; the bass leans on it and big kicks push it |
| vessel, PLAY / VISUALS | Plankton rims no longer flicker on hats; the pupil breathes less |
| monolith | Light shafts swell with the bass, not the mids; corridor rings and panel edges pulse half as hard |
| lattice, in-game sky | Stars, sparkles and rings on the smoothed treble and the big hits, not every hat |

**The corridor (monolith, VISUALS).** You were right, it was not rendering
correctly: rays that ran out of steps down the tunnel were painted with the
open void's daylight haze, a grey wedge at the far end. The tunnel's air is now
its own dark, so it recedes into black, at every quality.

**Colour grade.** VISUALS -> Colour grade -> natural | cool (cool is the
default). Display-side: the image cooled and a little desaturated, colours near
a pure red, green or blue kept and pushed -- the artery goes from orange-red to
crimson, the leaves from yellow-green to deep green, the monolith's concrete
blue. Is it strong enough?

**Your x-rays.** In the vessel: PLAY hangs the side view on a lightbox behind
the plankton, bone lines glowing blue-white on black, a scan line crossing it
every 9 s, and the metal glowing hardest, pulsing on the big hits; in VISUALS
the eye is looking at the front view on a lightbox, and you see it mirrored in
the cornea. They stay on this disk: git-ignored, never in a release (anyone
else gets a dark void there).

**Bells.** `ftesurf_void`'s glass bells are 8 dB down with a softer strike; by
ear it had been the loudest track (-20 dB(A), now -26.4, mid-pack). The
vessel's monitor ping and glass arpeggio are 3 dB down.

**Speed -- the magic sauce is the Menu scene setting.** Your config has it on
high. On this laptop (MAIN, in-world panels, uncapped):

| Menu scene | lattice | monolith | vessel |
|---|---|---|---|
| medium | 144 fps | 84 | 115 |
| high | 38 | 55 | 75 |
| ultra (new) | 38 (high already is) | 17-24 | 32 |

Medium looks nearly the same here and is 1.5-4x faster. Ultra is high's
resolution with the 3D drawn every tick instead of every other: meant for the
360 Hz PC, and the thing to try there. (Numbers on this laptop move ~30% run to
run.)

**Decisions only you can make:**

- Is "wild" now the right amount, or is normal enough?
- Keep the cool grade as the default?
- Ultra on the PC: smoother flights, or no visible difference? Rendering above
  720p is now the speed page's "native" (section 11).
- Your own loud songs, if you have some: do the flashes follow their kicks? The
  beat gates were tuned on the generated tracks only.

---

## 11. Kick streaks, a fractal world, the speed page -- what only you can judge

Written 2026-09-30 on the laptop. Built, photographed and measured headless;
not yet seen on the PC.

**Kick streaks** (VISUALS -> look -> Kick streaks: off | menu | menu + sky).
MilkDrop's waves: on each big hit a line is drawn into the trails and the trails
carry it off -- a kick throws an arc out from the station's landmark (the
echoes are the "rainbow road"), a snare a comet spiralling round it, and a hard
kick now and then the classic waveform line across the screen. Each line is bent
by the music's actual waveform, so at your volume they squiggle with the sound.
White when thrown, colour as they fly. In the lattice, the vessel (a bit
softer) and the new fractal world; not the monolith. "menu + sky" adds them to
the in-game sky, flying from the zenith to the horizon; that choice is the only
way they reach a map. They cost nothing measurable here.

They also go BEHIND models now (your question after the first cut): each
station's streaks fly just behind its centrepiece, so an arc thrown from the
lattice's cube comes out from behind it, and shows through the gaps between the
cubes. What counts as a model: the lattice's cubes, towers and orbs (not the
tunnel or the floor -- they fly over those), the vessel's blood cells,
plankton and eye (not the artery wall), and in the fractal world the fractal
itself, so there they fly in the sky behind the arches and the bulb (not in the
Menger tunnel).

While doing it I found why some of the trails looked green toward the screen
edges: the edge colour fringe had been stripping red and blue out of everything
drawn over the scene. Fixed -- the colours are the real ones now, everywhere.

**The fractal world** (Menu world -> fractal). Four places, each moving slowly
past a resting camera:

| Station | What |
|---|---|
| MAIN | a gothic cathedral (a pseudo-Kleinian fractal), turning slowly round you, sun shafts through the arches |
| PLAY | the same fractal folded taller: a moonlit hall that mirrors into the distance |
| VISUALS | a Mandelbulb against a cold star, the light breaking round its rim |
| MUSIC | down a tunnel of a Menger sponge, drifting; the holes' edges light with the spectrum |

The volumetrics are cheap ones: glow gathered wherever the rays pass close to
the fractal, fog that brightens toward the light, and light shafts -- the
brightest light blurred toward its source, so the arches cut dark lanes through
it. 100-131 fps at medium here, faster than the monolith. Its music is
`ftesurf_void` (no track of its own yet).

**The speed page** (VISUALS -> the Page row at the top -> speed). Menu scene
moved here, beside four new switches, all off by default, all the menu's only
-- a map is never touched:

- Resolution: by quality | native. Native renders the 3D at your screen's own
  resolution, one pixel of it to one pixel of the screen (a first cut still
  scaled it 3% for the edge overscan; fixed). Here: ~20 fps -- this laptop
  cannot. For the PC.
- Upscaler: bilinear | FSR 1. AMD's upscaler instead of the plain stretch:
  crisper edges and lines. Here it costs ~15 ms an update at 2256x1380 (123 ->
  38 fps), so not on this laptop; on a desktop GPU it should be cheap.
- Checkerboard: off | on. The 3D draws half its pixels each time and fills the
  rest from the last frame: 1.5-1.7x faster here, the same picture at rest,
  a little softer while the camera flies.
- Coarse pass: off | on. A small first pass finds how far each block of rays
  can skip; +19% in the fractal, nothing measurable in the other worlds.

The line under them shows the resolution it renders at and the frame rate, so
you can judge each switch as you flip it. `show_fps 1` now shows over the menu
too, top right (the engine's counter was drawn underneath the menu's 3D).

**Decisions only you can make:**

- The streaks: too many, too bright, or right? Want them in the monolith too?
  Behind the models is right, or should some fly in front (the floor, the
  tunnel)?
- The fractal stations: any you would swap out?
- On the PC: native at your setting -- smooth? FSR 1 at high or ultra: worth
  its cost there? Checkerboard: can you see it?

---

## 12. Run-line fades and rewind cursor controls (Patches 532–535)

`hud_edit lines` now includes **Chunk fade** (instant / fast / smooth / slow)
plus **Nearby players**, **Hidden within** and **Opaque beyond**. Defaults:
0.18 seconds for new line chunks; bodies dither away between 128 and 32 units.
Both are client-side visual effects, not run-clock or movement changes.
Patch 533 removes chunk-boundary restarts, shows the newest samples between
bulk rebuilds and replaces the body's 16-level pattern with fine static noise.

- Surf and watch a demo: do the small chunks arrive smoothly, from back to
  front, or is 0.18 seconds too slow? Instant is the comparison.
- Approach another lobby player: does the stippled fade feel unobtrusive while
  retaining their normal colours, or are the distances wrong? Toggle Nearby
  players off for comparison. Ghosts and your own avatar are unchanged.
- Judge on the high-refresh PC too: the automated pixel controls prove coverage
  and colour, not subjective motion quality or every renderer/driver.

**P535 rewind:** the usual clock, speed and energy now follow the visual cursor;
its clock says display-only and energy says `e line` (relative to the recorded
line start, not today's live anchor). No second time/speed line. Try your actual
strafe binds held/released, remapped and overlapped with arrows, then resume or
leave while held. Does the fractional camera feel continuous? Actual resume/save
still selects the original sampled point, not an invented interpolated state.
Normal HUD returns during countdown/after close. Live rewind only; demo held-key
parity, stitched wait-tail faults and the broad event/comparison work remain open.

**P536 board:** the confusing Compare chip is gone. Imported and native tabs
remain separate; refresh still exists. This is not a new live/frame comparator.
