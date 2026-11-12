# World of Surf patch notes

<!--
  What each update changes, written for players. The release turns this file into
  patchnotes.json beside update.json (src/release/releaselib.ps1 ConvertFrom-PatchNotes);
  the download page lists it down its right-hand side and the game shows it on F2's
  Patch notes page.

  Every patch a player can see or feel gets an entry under "## next" in the commit
  that lands it. The release names "next" (release.ps1 refuses one without it), and
  the release record commit adds "## <version> <yyyy-mm-dd>" under the patches that
  shipped. The newest 12 releases are published.

  Lines the release reads, starting at column 0, and nothing else:
    "## next" or "## <version> <yyyy-mm-dd>"   newest release first
    "### P<number> <title>"                    highest patch first, title up to 80 characters
    "- <point>"                                one line each, up to 250 characters
  Printable ASCII only and no caret (the game reads it as a colour code). Say what
  changed for the player; no file names, hashes or anti-cheat details.
-->

## next
- Ordinary save-load view prediction waits for that load's reply instead of ending early on an older acknowledgement.

### P1514 Practice-run gravity attribution
- Clear airborne water-jump moves now count proven use of retained gravity toward the existing practice-run policy, without changing movement.

### P1513 Configurable replay-journal upload budgets
- Operators can configure a run-length budget for replay journals; servers without this setting keep their existing upload behavior.

### P1511 Less work sorting intersecting transparent surfaces
- Transparent-surface ordering stops checking a pair once neither side can be proved, keeping the same drawing order and visual effects.

### P1510 Safer background work during maintenance
- Background replay analysis stays accounted for during service maintenance instead of appearing finished while work is still running.

### P1509 Bounded background replay analysis
- Background replay analysis runs separately with resource limits, allowing normal verification to continue after a timed-out check is stopped. Missing results remain unavailable rather than being treated as clean.

### P1508 Keep queued updates when packets fill
- Servers keep queued stats and entity updates pending when an update packet fills or is discarded, rather than silently losing them.

### P1507 Less sprite work on busy maps
- Sprites and light glows skip unnecessary per-frame checks on maps like surf_fairy, keeping their original appearance and drawing order.

### P1504 Steadier frames on maps with many light glows
- Light glows now stay within their per-frame time budget, so the slowest frames on glow-heavy maps like surf_fairy are a little shorter.

### P1501 No stutter when props first come into view
- On Source maps, props (trees, statues, decorations) now finish loading behind the loading screen, so their shaders are ready before you move: no stutter the first time you see them after an update (surf_fairy, bhop_orgrimmar).

### P1483 Jargon finishes more reliably, and repeats what works
- Jargon aims a course's last stretch at actually entering the end. A line that gets near the end but would fall short
  is played as close as it gets, and the finish is tried again with a longer search instead of being given up after
  one go. On surf_tensor2 stage 2 it finished in both test runs, once faster than the replay it learned from.
- The same start and settings now search the same way, so a good result can be repeated; pressing Start again after
  "stuck", or Continue, tries new lines.
- A new Start no longer replaces a saved run that got further.
- New effort options: "Best of 4 lines" in the panel (each ramp's few best boards are tried against the next ramp
  before one is kept), and `turns` for the console (a waypoint halfway through each big air turn).
- Fixed: a server crash in Jargon's search; Jargon stopping a whole run when "trying harder" after backtracks; route
  editor points that moved on screen but changed nothing (planned points are no longer draggable).

### P1502 Selected public map imports
- Public map imports can update a selected set while preserving unrelated map entries and earlier map revisions.

### P1499 Cheaper mouse-pad trail
- The mouse-pad display draws its trail with less work and looks exactly the same.

### P1497 Steadier frames on maps with many sprites and light shafts
- The check that hides sprites and light shafts behind the sky re-checks the ones that have not changed less often, so maps full of them spend less time on it (surf_fairy about 0.25 ms less a frame). `vbsp_sprite_skyhold 16` checks as often as before.

### P1496 Public bhop library imports
- Map acquisition recognizes Momentum's native HL1-bhop category even when the filename does not begin with bhop_. This does not switch the current movement model.
- New map and screenshot publication excludes private or unqualified testing entries, including retained offline catalogues.

### P1495 Remember the equipped knife
- Your linked knife setup can equip again on a new map after it has loaded. Drop keeps it off until you choose a knife again.
- Late setup/content replies no longer override a newer Drop or weapon choice; a newly mounted missing model can retry loading.

### P1494 Ordered save loads and resets
- A reset during a held saveloc load now stays in command order, preventing an older delayed load from taking over again.
- Clearing that hold also clears its local camera preview; recovery from a lost reset cannot release a newer rewind countdown.

### P1493 Local game version in map info
- The map-info title now shows your local game version beside World of Surf.

### P1492 Bhop map entities
- The two glass doors in bhop_bunnyrace now slide open when triggered and close after their authored wait, instead of only changing an internal state.
- Fixed local bhop platforms such as kz_bhop_avantura retaining an old landing count after jumping onto another block.

### P1490 Steadier frames where see-through surfaces overlap
- Where water, glass and other see-through surfaces overlap in a way no draw order can get exactly right, the game no longer retries the full order check every frame, only every fourth. Frames at surf_fairy's worst spot take about a tenth less time.

### P1489 No freeze right after you spawn on a map
- Light glows, sprites, emitters, decals, overlays and portals now load behind the loading screen instead of in the first frames after you spawn, which could freeze for a moment (about 130 ms on surf_fairy).

### P1488 Steadier frames on maps full of light glows
- Light glows and sky checks spend at most about 1 ms a frame testing what they can see, so maps with hundreds of glows stutter far less (surf_fairy's slowest frames about 45% faster, surf_jumble's 38%).

### P1487 Replay ladder climbs
- Ladder climbs and descents are no longer mistaken for standing still by replay idle skipping.

### P1486 Recording statistics keep their measurement state
- Input-recording identity counters publish without racing the physics worker. Never-measured values stay unknown, and the last recording's measurements remain available after it closes; settings callbacks still run outside the recording update's lock.

### P1485 Threaded recording updates keep their callback order
- Ordinary recording updates no longer overlap the physics producer. Relative mouse updates stay grouped across empty paste polls, while actual key/paste callbacks retain their original position and ownership.
- Already-marked synthetic input does not acquire a lock for every call.

### P1484 Recordings finish without disturbing a newer recording
- A finishing recording keeps its own bytes and result through callbacks, so its cleanup cannot discard a newer recording. Aborted closes release their buffers without publishing an unfinished result.

### P1481 Steadier frames while the game tidies its text memory
- The game's text-memory cleanup no longer pauses a frame for a few milliseconds: it copies only what changed since its last pass, and after a replay loads it cleans up in small steps instead of rare big ones.

### P1480 Safer input-recording replacement
- Starting or clearing an input recording now waits for threaded physics to finish its current write before replacing or freeing the recording.

### P1479 Input recordings finish at buffer boundaries
- Input recordings near a buffer-growth boundary now finish normally instead of being incorrectly marked truncated.

### P1478 Jargon: one click for the map, a bonus or a stage, and Continue
- Jargon's panel now lists the map's courses (Main, each stage, each bonus). Pick one and it offers only runs of that course as guides, from leaderboard, KSF and Momentum replays and your own recordings.
- "Surf <course> from its start" does the rest: the right start box, a walk to where the guide stood and its own prestrafe, every ramp, and the run into the end, then says your time. When it gets stuck it tries harder by itself before giving up.
- A stage can be guided by a full run of the map: Jargon cuts that stage out of it.
- The run saves itself as it goes (a new start never replaces a saved run that got further). "Continue" replays the saved run exactly and carries on from where it stopped, with the effort you pick now.
- Long maps say when a route is longer than Jargon plans at once (64 ramps): surf them stage by stage. Long chains also backtrack more sensibly (sloped roofs count as walls, overshot ramps are boarded further back).

## 0.1.44 2026-11-10

### P1477 Water reflections take turns even when you move fast
- Fast moves and turns no longer make a water surface redraw its reflection and refraction in the same frame, and the reflection rate setting (r_capturerate) now goes down to 10.

### P1475 Water reflections stay put while you move
- Between redraws, a water reflection or refraction is now shifted by how far you have moved, using each pixel's own depth, so it no longer slides off the water's edges at lower capture rates. r_captureparallax 0 turns it off.

### P1474 Smoother frames over water: captures take turns
- Water's reflection and refraction are now redrawn on different frames instead of the same one, so a frame that redraws water carries one extra scene instead of two. r_capturestagger 0 brings back the old behaviour.

### P1472 No frame cap below the server's tick rate
- While playing, a cl_maxfps under the server's tick rate (66.67 on surf, 100 on bhop) is raised to it, so every physics tick gets its own input. Uncapped (0), menus and demos are unchanged.

### P1470 r_projection works again
- r_projection 1-6 (fisheye, panini, panoramic, equirectangular and the rest) draw again with anti-aliasing and render scale on, instead of filling the console with errors at a few frames a second.

### P1465 / P1463 / P1457 See-through surfaces sorted faster
- Maps with many overlapping see-through surfaces (surf_fairy) spend much less time ordering them each frame: sorts that cannot succeed are skipped and off-screen faces are left out. The picture is the same.

### P1464 Join message names the map
- When someone joins a lobby, the others now see "<name> joined <map>" instead of "server: <name> joined".

### P1462 Save-load key lets go when you let go
- Releasing the load key now starts you at once. Before, the lead-in held you frozen until a full second after the press, so a quick tap left you stuck for about half a second.
- The run-up still plays while you keep holding the key; letting go cuts straight to the save.

### P1461 Timer zones built from the map: bonuses, stages and zone lines
- On maps whose timer zones come from the map itself (no zone file yet, many KSF _css builds), bonus starts and ends are now bonus zones, not extra main starts and ends, so a bonus run no longer times as a main run.
- Those maps' stage zones are numbered the way zone files number them, and their zone lines now draw where the zones really are; before, they were drawn far away and hidden.

### P1460 Missing textures saved per map
- When textures on a map do not load, the whole list is saved to data/missing/<map>.txt (the console shows only the first 24), so it can be sent in. The file is removed once the map loads complete.

### P1459 Graphics: Post-process switch
- The Graphics menu has a Post-process row. Off draws the scene as rendered: no bloom, map colour grading, FXAA, custom post shader or underwater warp. Your gamma and brightness still apply.

### P1458 Blinding light glows fixed; Light glows switch
- Light glows a map sets to show only up close no longer fill the screen from across the room (surf_beginner2 stage 7).
- The Graphics menu has a Light glows row, so turning Sprites off no longer leaves the lens-flare glows on.

### P1454 No "Not Responding" while a big map loads
- A map whose first load takes several seconds (surf_quarantine with CS:GO content) no longer turns the window grey with "Not Responding" while it loads.

### P1453 Loading screen: named steps, the map's own models and its picture
- Each step names what is loading: "Mounting CS:GO content" (with the wait on screen), "Loading textures: CS:S, HL2, the map", "Loading models (3): dagger".
- Maps with their own models show one as the spinning wireframe: surf_gigapede's dagger and boid, bhop_ceaseless's butterfly, spider and dragon, Patrick on surf_bikini_bottom, and 10 more maps.
- The wireframes face you side on; Settings has "Loading-screen models: side on / from above".
- The map card shows the map's own screenshot instead of the small browser thumbnail.

### P1452 Keyboard input survives an input restart
- Input restarts protect device resources while they are rebuilt; if Windows refuses to stop raw keyboard input, the game keeps the existing device working.

### P1451 No string-cleanup hitch early in each map
- The memory the game code's string cleanup works in is now set up while the map loads, so the first cleanup of each map, usually during your first run, no longer stutters for it.

### P1449 Jargon: a bot that surfs a map from a leaderboard run
- The TAS menu's Jargon tab: pick one of the leaderboard lines you have on as the guide, and Jargon surfs the map ramp by ramp along it, searching each ramp's board and flight. Manual TAS keeps the old tools.
- The route is drawn in the world: ramps as see-through planes, boarding points as handles. Edit closes the panel to fly around and drag them; Esc brings it back. You can also place air points to steer a flight.
- Effort (Quick, Normal, Thorough) sets how hard each ramp is searched. A ramp that keeps failing sends it back to the one before; when it overshoots a ramp, it comes in wider on the next try.
- Strafing in the air: Tight, or Wider so it does not flip left and right every frame. Where it boards: the guide's spot, or try 5 spots on each ramp and keep the one that carries the most speed to the next ramp.
- Restart from the start zone, go from where you are, or redo from any stretch. Watch the search lines live, from your view or an overview camera that follows the line, with a thinking panel.
- These are local practice tools: they are refused on the lobby servers.

### P1447 Website replays play on Strata maps, and load faster
- The website's 3D replay viewer now draws Strata Source maps (and a dozen other maps that failed): every map in the library loads.
- Maps with lots of curved terrain build up to 5x faster in the viewer (ahop_coast 11 s to 2 s).

### P1446 Smaller stutters every 15-20 seconds, on every map
- The game code's string cleanup used to freeze one or two frames every 15-20 seconds while it copied and freed a large block of memory.
- It now keeps that memory between cleanups: the slowest frame it causes went from 7.5-12 ms to 4.5-6.4 ms on surf_nuclear, and the same applies on every map.
- `r_spikes` (see P1444) now also shows what the slow frames did in prediction and network handling, and `r_spikes 2` names the game-code functions behind a slow frame.

### P1448 Fetch: any leg, any player, from KSF and Momentum
- The leaderboard's Fetch button (was Fetch KSF) now asks both KSF and Momentum Mod for the leg you are on, refreshes it, and works on maps and bonuses with no times here yet.
- It is on the KSF, Momentum and All filters, in game, in the menu's leaderboard and on the website. KSF replays for that leg download first.
- Player profiles have a Fetch button too: it asks KSF and Momentum Mod for all of that player's records, stages and bonuses included.
- Everything fetched arrives in the background over a few minutes; press Fetch again for 100 more times.

### P1443 TAS: a much faster optimizer, and an energy goal
- `tas optimize <ticks> <left|right> ... fast` tries hundreds of turns, boards and flicks in a second and plays only the best -- the old search played every try (about two seconds each).
- `energy` scores speed plus height instead of speed alone, for maps where you need every bit of energy to make the end.

## 0.1.43 2026-11-09

### P1444 Find what makes a frame slow: r_spikes
- `r_spikes 1` (with `r_frametime 1`) keeps the slowest frames since `r_frametime_reset`.
- `r_frametime_dump` now lists what each one spent its time on: game code, draw calls, map visibility, the display, the network, late shader compiles, water and glass views.
- For tracking down the stutters behind the 0.1% lows.

### P1440 Model parts and animations maps switch
- Models with swappable parts now show only the part the map picks, as in Source: bhop_crash_egypt's crates are whole boxes until you break them, then shatter frame by frame. Before, every part drew at once.
- Props that maps animate now play it: bhop_crash_egypt's nitro crates jiggle.

### P1442 More shaders prepared while loading, without "Not Responding"
- A map's load may now spend up to 6 seconds (was 2) preparing shaders, so slower PCs finish preparing them during the load instead of stuttering through the first run.
- The window stays responsive meanwhile: Windows no longer marks it "Not Responding" while shaders are prepared.
- A saved setting still on the old 2 seconds moves to 6 once you have this version; a different value you chose is kept.

### P1441 Fewer stutters the first time you play a map
- The game now prepares the shaders of all 60 tested maps while a map loads, instead of the first time each one is drawn.
- The first run on a map, after a new install or a graphics driver update, stutters far less: surf_tendies went from 64 small freezes (up to 71 ms) to 4, and its slowest frames from 58 to 139 fps.
- The first load of each map can take about a second longer on such a PC; later loads are as before.

### P1432 Sprites and particles maps spawn
- Sprites a map spawns when something happens now appear where it spawns them: bhop_crash_egypt's CHECKPOINT letters at each checkpoint, bhop_exodus's pictures. Before, they never showed.
- The same for particle effects: booster puffs on bhop_lego2, bhop_japan, bhop_nature, bhop_rin, bhop_epiphany2 and bhop_angst, and bhop_crash_egypt's TNT and Nitro explosions.

### P1439 Screen overlays and shooters
- Full-screen overlays maps put up (7 maps: oil splats, drug effects, flashes) now show, and shooters that fling props (8 maps: plushies, debris, shell casings) now fire.

### P1438 Text in the world
- Text that maps place in the world now shows (24 maps): signs, credits, tutorial hints, and counters and countdowns that change as the map runs.

### P1437 More consistent save loads
- Save lead-in no longer snaps to the held view when load updates arrive separately. Rewind loads keep their saved trail and view, even if the selected save changes before the load is displayed.

### P1436 Fish swim
- Fish pools now have fish (28 maps, about 1,300 fish): they school, wander round their pool and dart away when you come close.

### P1435 Explosions
- Explosions a map sets off now happen (47 maps): a fireball with smoke, embers and flying sparks, the explosion sound, and a scorch mark where it went off.

### P1433 Steam, sparks and fires maps switch
- Steam jets are drawn (95 maps), and maps can turn them on and off.
- Fires and sparks a map starts, stops or sets off on an event now do so, including fires that burn out.

### P1431 Lights and sprites maps switch
- Sprites and spotlights a map switches on, off or toggles now do so (about 1,000 on 100+ maps): checkpoint sparkles that appear when you reach them, light shows like surf_orbion's rings of spotlights. Ones that start hidden were never drawn before.

### P1430 Electric arcs
- Tesla coils now spark (point_tesla, on 132 maps): jagged electric arcs out to the nearest walls, fired when the map switches them on or sparks them. Beams set to arc at random draw the same way.

### P1428 Look triggers and map minigames
- Triggers that fire when you look at something for a moment now work (21 maps), including their timeouts.
- Map minigames that read your keys (game_ui, 20 maps: bowling, races) now get your movement and attack keys. They do not freeze you in place yet.
- Breakable walls that a map damages through outputs break when their health runs out, and props that change skin through outputs now change.

### P1425 Things maps spawn on an event now appear when they should
- Entities a map spawns from a template (130 maps: checkpoint teleporters, collectibles, buttons) are no longer there from the start; they appear when the map spawns them, as often as it does.
- bhop_4muddz and similar maps: the teleporter you get at a checkpoint works every time instead of only once.
- Map outputs aimed at names ending in * (any name starting with that) now reach their targets (54 maps).

### P1426 Beams between points
- The laser and electric beams maps run between two points now draw (env_beam: about 1,200 on 90 maps), switched on and off by the map; striking beams flash as they do in Source.

### P1422 Faster maps with lots of glows and sprites
- On maps full of glows and sprites (surf_fairy, surf_jumble...) the check that hides sprites behind the sky now does a fixed amount of work per second, and only for sprites you can see: surf_fairy went from about 225 to about 300 fps.
- At 60 fps or below the check works as before. Glares on very wide screens, or with an unusual FOV mode, no longer freeze at the screen edges.

## 0.1.42 2026-11-08

### P1423 Graphics menu: option numbers, Movers and Mover light
- The Source Renderer menu (gfx_menu) shows where each setting sits, like "Full reflect (6/6)": 1 is the fastest option, the last is the fullest. Water, Glass, Prop distance, Tool brushes and Reflection AA now step in that order.
- New Movers row: Off hides the moving decorations (passing trains, swarms, spinning props you cannot touch) for speed; on surf_centipedes about 2.4 to 2.1 ms a frame. Moving things you can hit always show.
- New Mover light row: how often moving props update their light, 1/s (default), 4/s or every frame. Every frame costs a lot on swarm maps; below once a second saves nothing, so that is the lowest.

### P1418 Crash reports you can send
- If the game ever closes with an error, the next time you join a lobby a box offers to send the error and the last console lines (typed commands and anything naming a password or key are left out). F6 sends it; nothing is sent without that.
- ui_crash_report 0 turns the offer off.

### P1417 A broken game file no longer closes the game
- A map, model or texture file that claims an impossible size (over 2 GB) is now skipped with a console line naming it, instead of closing the game with a "BZ_Malloc: Failed on allocation" error.

### P1416 Map effects that fire on an event
- Particle effects a map plays when something happens now show: booster and teleport bursts, fireworks, badge pops, and glows a button switches on. About 200 of them on 29 maps, fired when the map starts them, as in Source.

### P1413 Steadier frames with an fps cap
- With an fps cap (cl_maxfps / fps_max), each frame now starts just early enough to be ready and is shown exactly on time, instead of starting on time and being shown whenever it finishes.
- At a 100 fps cap, 99% of frames now land within 0.1-0.4 ms of 10 ms (before, 1-3 ms late was common). Input is read about 3-6 ms before the frame shows, far less than the old swap-holding mode (sys_framepacing 4).
- sys_framepacing 1 brings back the old pacing; uncapped, with vsync on, or on D3D/Vulkan nothing changes.
- The frame-time graph (r_frametime) now times frames when they reach the screen.

### P1410 Clicking the game window no longer presses your mouse bind
- When the game is in the background, the click that brings it to the front now does nothing in the game.
- Before, it also pressed whatever Mouse 1 or Mouse 2 is bound to -- with duck on a mouse button, clicking back into the window mid-run ducked you and could wreck the run.

### P1414 Joining a lobby that is changing map works at high ping
- Asking for a map no lobby is running switches a lobby to it and puts you there. With a slow connection (around 400 ms) the game used to give up and say the server never came live, even though the lobby had switched.
- Now it waits for the switch properly, for up to 45 seconds.

### P1412 Smaller client game code
- The game code a lobby sends you is 3 MB smaller (8.0 MB to 4.9 MB), so joining after an update downloads faster. It runs exactly the same.

### P1411 Map particle effects on 118 more maps
- Maps that come with their own particle effects (glows, embers, waterfalls, rising shapes) now draw them on 122 maps instead of 4. Effects that only fire when something happens (a booster, a button, a teleport) are not drawn yet.

### P1409 Faster see-through surfaces with exact sorting
- With r_blendsort 2 (see-through surfaces sorted back to front), maps with many glass or see-through faces no longer recompute every face's centre each frame: surf_bossfight went from about 280 to about 490 fps. The picture is the same.
- r_blendcache 0 brings back the old way.

### P1408 Five crosshairs
- The crosshair setting (HUD editor) cycles five crosshairs and off: a new green plus, a small white dot and a magenta plus join the first two. Each draws at its own size.

### P1405 Teleports that check your name are predicted
- Many maps rename you as you go (each stage, each bhop block) and send you back with teleports that check that name.
- Falling into a stage's reset now takes you straight to the stage start instead of stopping at a hidden room and jumping a moment later. About 22,000 teleports on 577 maps.

### P1403 Prediction reports carry packet timing
- A prediction report now records when each update from the lobby arrived, so the remaining snaps around saves, loads and resets can be traced. Reports are no longer offered for the first moments after a slow map load.

### P1400 Type your own binds; more actions in the key settings
- The Keyboard tab (K) has a "Your own command" box: type any console command, press Enter, then click keys to put it on them. The keys already running it light up.
- Click a key, then Edit to change what it runs (Enter saves, an empty box clears it, Esc cancels) or Clear to unbind it.
- New actions in both tabs: Report, Surf view, Entity view, Entity inspector, Zone editor, Run graph and Race ghost under Tools; Scores, Chat, Console, Main menu, Patch notes, Screenshot and Fullscreen under Game.
- Esc and your last console key can't be cleared or taken from the panel, so you can't lock yourself out; reset keys puts the console back on its usual key.

### P1402 New defaults: flat water, see-through surf_view
- A new install's water is the flat transparent sheet instead of the dithered one: they cost the same, and the flat one is cleaner to look through. Settings you already chose are kept.
- surf_view and ent_view draw see-through planes with outlines by default. If you never changed the old dithered look, it switches once (the console says so); surf_view_style picks another.

### P1398 Moving things are cheaper to light
- Props that move (surf_centipedes' skull swarms in the sky, things riding tracks, other players) look up the map's light about once a second instead of every frame, and fade smoothly to each new value, so the light never steps.
- surf_centipedes' stage starts went from under 200 fps to 460-920 at the default settings. r_modellight_moverate sets how many times a second; 0 is every frame.

### P1397 Noclip no longer files prediction reports
- Turning noclip on or off in a lobby is no longer counted as a prediction error, so it no longer writes or offers a report.

### P1396 Teleports whose names differ in capitals are predicted
- About 1,000 teleports on 123 maps (surf_delight, surf_tycho, surf_prevail, surf_mesa_mine, surf_kitsune and others) spell their destination with different capitals than the destination itself. The server always took them.
- Your game did not predict them, so each one sent you a moment late with a jump. They are predicted now.
- surf_bossfight's intro drop is decided by the server alone and no longer files prediction reports.

### P1394 Teleports that push you are predicted
- Teleports that also give you a push as you enter (surf_perennial's speed loops, 63 teleports on 31 maps) are predicted again instead of being left to the server, which snapped you to the exit a moment late each time.

### P1386 Water walls and slopes share the view's reflection
- With Full reflect water, walls and slopes of water, water seen from underneath, and water on moving parts of a map now use the same reflection and refraction as the main water you can see, as Source does.
- Before, each drew the whole scene again every frame. bhop_ceaseless looking back at the start: 214 to about 450 fps. surf_affliction's lava channel: 8 to about 600. The picture is the same in nearly every view; r_waterwalls 0 brings back the old way.

### P1392 Keyboard view in the key settings
- The key configuration panel (K) has a Keyboard tab: a whole keyboard and mouse showing what every key does. Pick an action from the list, then click keys to put it on them; right-click a key to clear it. Keys bound to the action you picked light up.

### P1391 Report a problem (F3)
- Press F3 to send a report: pick a subject (Poor performance, Bad rendering, Bug, Map or zones, Feature request, Other) or type your own, say what happened, and send.
- A screenshot of the moment you pressed F3 goes with it, plus the map, your position and save, frame rate, settings and game version, so you don't have to type those. Esc closes it and keeps your text for next time.

### P1390 surf_colony's sky
- The headcrab canisters in surf_colony's sky now fly round their routes instead of hanging still.

### P1388 Trains keep the map's speeds
- Trains and other things that run on tracks speed up and slow down where the map says (surf_christmas2's sky, bhop_collective's screens), instead of keeping one speed the whole way.

### P1387 Spinning scenery moved by your game
- Spinning and sliding scenery (windmills, asteroids, fans and what rides on them) is moved by your game from a clock the lobby sends once, instead of the lobby updating it 20 times a second, so it turns smoothly.

### P1385 Map messages in crisp text
- Messages a map puts on screen (like surf_centipedes' "Press E (+use) in any startzone" line) and its hint boxes are drawn at a real font size on whole pixels, so they are sharp instead of resized and blurry.
- surf_centipedes' moving sky costs your game less each frame.

### P1384 Loading a save is the same at any ping
- With a lead-in set, the run-up into your save now starts the moment you press the load key, and a tap lets you go when the lead-in ends.
- Before, both waited for the server to answer, so on a distant lobby the view sat on the save, jumped back up your path and counted down from less than the lead-in.
- A lead-in of 0 now lets you go on the tap itself, at any ping.
- Loading a save with a long recorded path no longer freezes the game: on the longest saves (about 46,000 points) the freeze was a third of a second, now it is a few hundredths. Your run line comes back a moment after the load instead.

### P1383 Noclip speed on the lobbies
- Shift + mouse wheel while noclipping now changes your flying speed on the lobbies too, not only in a private game. It changes only your own speed.

### P1382 Missing textures: what is not found, and a report
- When a map shows missing (pink and black) textures because a game it takes them from was not found on your PC, the message now names that game (for example Counter-Strike Source or Half-Life 2) instead of saying the map is broken.
- If it is installed on another drive, type fs_steamlibs in the console.
- Once a map, the game tells the lobby which textures were missing and which games were not found, so missing content can be fixed without asking you. No file paths are sent; cl_matreport 0 turns it off.

### P1380 Pixel-art map textures
- Pixel-art signs no longer show slivers of their neighbours at the edges, and stay even rather than jagged when seen from further away (surf_centipedes' title).

### P1378 Things that fly along a track now move
- Things a map sends flying along a track, like surf_centipedes' swarms in the 3D sky, now move. Your game moves them itself, so they cost the lobby nothing.

### P1381 Personal bests survive a mode change
- When a map moves between surf and bhop, your local best and your lobby times on it are compared by time, not by tick count, so a slower run no longer counts as a new best (or a faster one as not).
- Zone editor: clicking the mode that is already selected keeps your custom air acceleration, and a tier you did not change is not sent again.

### P1376 New default picture: your screen's size with anti-aliasing
- The game now draws at your screen's own size with 4x anti-aliasing, and water and glass reflections with 2x, instead of drawing at twice the size and shrinking it. Edges stay smooth for far less work on the graphics card.
- If your settings were still on the old default, they move once to the new one (the console says so). If you had already lowered Render scale for a slower PC, nothing changes.
- The graphics menu's Display page has two new rows, Anti-aliasing and Reflection AA, beside Render scale.

### P1373 Light glows after a teleport
- After a fail or a stage teleport, light glows from where you were no longer show through walls for a moment when you turn towards them. Glows you can see from the new place fade back in within a moment.

### P1375 Save-load countdown
- A small centered millisecond countdown shows the remaining save-load lead-in. Waiting for a server answer says Loading save; keeping the load key held says Release to play once ready.
- Save & load in hud_edit has one Lead-in field in milliseconds, rather than two controls for the same setting. Your existing value is kept.

### P1372 Historical warm saves keep recording
- Newly created saves from a live rewind retain the recorder state needed to keep recording after a warm load. Existing incomplete saves and old cold-rewind duration errors are unchanged.

### P1371 Bhop maps start on the jump; the zone editor sets mode and tiers
- Every map named bhop_ plays as a bhop map: 100 tick, air acceleration 1000 and the timer starting on the jump, including the five that Momentum lists under other modes.
- The zone editor's Map properties can set a map's mode for the lobbies (click Surf or Bhop) and its Momentum and KSF tiers. Save settings, Save zones, then Publish saved; lobbies use them from their next map load.
- The HUD and scoreboard show a tier set in the zone editor.

### P1369 Lobbies use the same map list as your game; every bhop map runs 100 tick
- The lobbies now read each map's Momentum mode, tier and stage count from the same list your installed game uses, so a map plays by the same rules online and offline, and lobbies show the tier.
- agtricks, df_cavernish, df_yungstrafe08 and kz_bkz_goldbhop_v2 run bhop rules on the lobbies now (100 tick, air acceleration 1000, timer starts on the jump), as they already did offline.
- bhop_badwater, bhop_canals, bhop_nightmare, bhop_odyssey and bhop_ytt_cruma run 100 tick and air acceleration 1000 offline too.
- ahop_coast's lobby timer now starts on the jump, as it does offline.

### P1367 Your own replays look the right way, goto, ahop_coast
- Watching your own lobby replay no longer shows the view turning before you do. The camera was ahead of your body by your ping (a third of a second for many players); it now lines up.
- Players who leave a lobby no longer stay behind in the player list as "unnamed".
- New goto command: goto (or goto spawn), goto main, goto start, goto s3, goto b1. goto_spawn still works.
- ahop_coast's teleports, water resets and doors work, and the lobbies run it at Momentum's bhop tick rate and air acceleration.
- Name filters now match the way Source does (any case, trailing *), so checkpoint triggers on about 40 maps such as surf_autosave and bhop_kirous behave as their authors made them.

### P1366 Comparison bars and held-save travel
- Compare speed and energy both at the same elapsed time and at the nearest point on the displayed reference. Centered bars keep the numeric differences visible.
- Travel through the saved path into a held save, then return control at the saved point. Missing local paths safely keep the ordinary hold.
- Keep segmented local bests separate from clean personal bests, so a faster segmented result does not disappear behind a clean-run receipt.

### P1365 Fewer first-play shader stutters
- Shaders that Tensor2, Ceaseless, Boreas, Garden, Demise and similar maps need with full water and glass effects are now prepared while the map loads, instead of the first time you see them.

### P1364 Prop lighting prepared before you play
- Static prop lighting is worked out when a map loads, so new props no longer cause a stutter the first time they come into view. On Ceaseless the first run no longer hitches near the 11 second mark.

### P1363 Faster light glow checks
- Light glows and shafts check the sky far faster on maps with many of them: about 25% higher frame rate on Tensor2, with identical results.

### P1362 Tiny ramp surfaces
- Tiny ramp faces no longer invalidate a whole map's downloaded marks.

### P1361 Background diagnostic scheduling
- Background diagnostics avoid starting new source work once their cooperative time budget is reached. Work already in progress still finishes normally.

### P1360 More optional ramp marks
- Expand replay-baked ramp wear and boarding marks across popular maps and the priority bonus list. Each map has one optional atlas; unavailable recordings and unpainted geometry remain explicit gaps.
- Add verified R2 delivery and smaller compressed text downloads with a local-server fallback. Marks remain opt-in and are not added to game packages.

### P1359 Recording diagnostic version numbers
- Recording diagnostics now withhold similarity metrics for unsupported numeral notation in version numbers.

- Reduce first-traversal static-prop lighting stalls without changing the lighting or visibility quality.
### P1357 Lower client collision-query overhead
- Reduce CPU overhead from light-visibility queries, particularly on Tensor2, without changing light visibility, ray budgets or rendering quality.

### P1355 Experimental local section search
- Select earlier inputs and a later observed ramp face to try nine bounded turn/crouch candidates against its arrival region, then preview the complete retained future. Results are best found, not a global fastest route.
- Progress and Cancel stay tied to your own source and search. Keep waits for complete replay; Discard restores the original full line, settings and future without inventing input credit.

- Fix decorative-brush prediction corrections on the NanoPi lobbies.
- Keep board-run labels visible with board paths hidden, and show boarding energy change beneath the main contact label.
- Snap zone-editor geometry to invisible player-clip faces shown by surf_view, and sharpen teleport destination names.
- Improve point-filtered cutout textures at grazing angles without blurring their close-up pixel detail.
### P1351 Bounded map preparation and honest readiness diagnostics
- Loading briefly waits for known pending resources and remembered shader work, with explicit timeout and failure diagnostics instead of an unbounded wait.
- Developer diagnostics identify shader compilation and image work that happens after loading. This is not a promise that every future resource is already resident.

### P1350 Native contact sections for local TAS lines
- Browse observed ramp faces separately from your manual markers, and jump to their input ranges without losing the rest of your line.
- Keep complete observations across safe marker-only edits; changed previews stay separate and Discard restores the original map. This is not yet an automatic next-ramp solver.
- Validate large saved lines without a second full read in the load command; pending observation pages retry automatically and failed sources stay unbound.

### P1349 Reliable developer compiler results
- Compiler output and requested debug-file failures now stop compilation instead of returning success. An unavailable decompiler reports its missing capability safely.

## 0.1.41 2026-11-06

### P1348 Correct overview state on exit
- Leaving map-only noclip keeps normal dynamic lighting intact, including cached and realtime-lighting policies.
- Hidden weapon bursts, recoil and scope feedback are discarded rather than replayed on exit. Viewmodel preferences and watched profiles still update while hidden.
- The overview only accepts already-loaded structural models; unloaded decorative models cannot slip through the brush exception.
- Zone editing still processes clicks and drag releases at the current aim in the void, without drawing editor world overlays.

### P1347 Fetch KSF boards and gentler replay retries
- Added Fetch KSF buttons to the in-game and map leaderboards for the selected course and direction; available replays follow in the background.
- Made KSF replay fetching gentler: missing files no longer stall the whole importer, and temporary replay-server errors use targeted retries while genuine rate limits remain protected.

### P1345 Smoother noclip overview and accurate frame reports
- Outside-map noclip skips decorative props and effects while keeping the map and structural brushes visible. Normal in-map rendering settings are unchanged.
- Fixed a first-exit rendering stall caused by cosmetic prop lighting returning inside reflections. Recursive reflections now keep the selected map-only policy.
- Frame reports retain long stalls and disclose sampling exclusions. Explicit reports calculate exact raw percentiles and tail averages; live estimates are labelled.

### P1343 Relative teleport parity
- Relative teleports stay invisible pass-through triggers when enabled and preload their destination like ordinary teleports. Prediction reports now distinguish server-only relative snaps without hiding same-destination prediction errors.

### P1342 Smoother short save chains and correct release speed
- Two or three rapid save steps in either direction can now be predicted. Fixed releases using a previous save's velocity; unknown destinations are not guessed.

### P1341 No stale boost after velocity-reset teleports
- Fixed predicted push velocity surviving teleports that reset or redirect velocity. Keep-velocity and landmark teleports still preserve their intended speed, and a later push still works.

### P1340 Developer export and dump safety
- Hardened developer export/dump handling and made failed outputs report failure instead of silently succeeding.

### P1339 Downloadable replay-baked ramp atlases
- Request a map's prebaked wear/scratch atlas with rampwear_download, then enable marks or dirt separately. Larger atlases are verified and cached without increasing the engine's remote-picture limit; both effects still default off.
- Expanded replay inputs for Story/Event ramp baking and moved the unchanged snowflake model alongside the Christmas assets.

### P1337 Safer developer-tool commands
- Hardened developer-tool command handling while keeping normal local developer workflows available.

### P1336 Name and navigate TAS sections
- A new Sections tab splits the complete captured local line at your named markers. Select a section's inputs or replay to its start or end without losing the later line.
- Add, rename, move or remove manual boundaries while paused. Marker edits save the full retained run, even from an earlier body; Undo/Redo keeps the original revisions.
- Marker names have their own text field, with safe held-key handoff to gameplay and the existing recipe editor. These are manual sections, not automatic ramp detection or a fastest-route solver.
- Oversized marker edits stop safely with the full saved line intact instead of exhausting the game server. Long lines can still be browsed; synchronous marker saving has a conservative size limit.

### P1335 Optional Christmas effects and closer ramp dirt
- Added a Christmas effects master switch, off by default, in Display Info and as r_christmas. It gates seasonal weather, snow, ambience and decorations while keeping individual effect settings.
- Ramp marks and dirt are now off by default. Enabled dirt sits much closer to ramps, using depth bias instead of a visibly floating layer; lift adjustments apply live.

### P1334 Clearer unavailable replay comparisons
- Replay review now distinguishes an unsupported recording model from malformed input. Both remain unjudged rather than being shown as a measured zero; saved historical results are left unchanged.

### P1333 Optional current-file check in replay review
- Admin replay review can explicitly check current files while keeping saved historical comparison results unchanged. Unavailable checks are reported separately rather than presented as a match.

### P1332 Snow rendering and snappier lightning
- Fixed black snow on Colin by correcting texture and baked-light bindings. The existing shallow snow caps remain cosmetic and do not change terrain collision.
- Lightning strokes and the dark gaps between them are three times quicker, preserving their brightness and the thunder after each burst.

### P1330 Better prediction timing diagnostics
- Command-tagged timing updates take priority over routine stat changes when space is available. Prediction reports now retain the timing seed and movement-step counts used to make the prediction, with clearer handling of incomplete evidence.

### P1329 Bring back the controls used at an earlier TAS tick
- Seeking a local TAS line now restores its saved movement, jump/duck, turning and vertical-look settings instead of showing the latest draft everywhere. Preview, Discard and Undo/Redo keep the right settings with each line.
- A new step keeps the restored requested aim until you deliberately change your local view. Editing raw inputs marks only the changed ticks as having no saved turning preset; older literal recordings stay honest about missing settings.
- Re-authoring the same key presses keeps your new turning settings through previews. No-op edits retain known settings, and quiet refreshes no longer overwrite a queued vertical-look choice.

### P1327 Textured, lit snow and storm previews
- Colin's snow uses the mounted Source snow textures and baked map lighting instead of a fullbright white layer. Exposed caps gain shallow, uneven depth and visible edge rims; collision is unchanged.
- Snow-covered grass uses mounted Counter-Strike: Source snow footsteps, with Momentum's snow steps as a fallback.
- Weather uses the owner's rain/snow loops and thunder, compressed to small mono64kbps Vorbis files. Choose the ambient loop without changing map precipitation.
- Lightning fires randomized multi-flash bursts before the thunder. Added repeat-preview and storm-interval controls, with no dynamic lights or per-frame lightmap updates.

### P1326 More reliable prediction-report input details
- Fixed command timing, buttons and movement inputs being attributed to the wrong command in some prediction-error reports. This improves diagnostics; it does not change movement.

## 0.1.40 2026-11-05

### P1324 Complete winter downloads
- Fresh installs now include the winter/Santa models, weather audio and map-specific media, with the holiday asset license retained.
- Fixed Colin's baked weather header being rejected, restoring its sky, ice and sheltered-audio setup without changing terrain or roof coverage.

### P1323 Named input templates for local TAS
- Save a named selection of captured input, then preview its keys and view angles onto an equal-length selection in another compatible local attempt. Inputs after the selection stay available; Keep, Discard and Undo/Redo retain the original.
- Templates reuse recorded input, not a saved world or a newly optimized route. Supported current-run replay is still required; ramp sections and the next-ramp solver remain in progress.
- Recipe name typing keeps chat shortcuts in the field and releases movement safely on focus changes. A held name key cannot be rebound by a later key-capture panel. Existing or unreadable unfinished templates are preserved rather than overwritten.

### P1321 Fewer false prediction-error alerts after resets
- Reduced false prediction-error popups when several resets are sent in quick succession over a higher-latency connection. Movement and the underlying diagnostic history are unchanged.

### P1320 Keep paused runs safe during ownership checks
- A paused run stays intact while ownership is unavailable or belongs to another game key. Starting or finishing a fresh run now uses the same discard checks as the manual command, without repeating the warning every frame.

### P1319 Snow-facing and ramp-mark corrections
- Colin's snowy grass and exposed snow caps use the intended white-snow material and outward faces instead of cached purple fallback/undersides. Walking on its snowy grass adds quiet crunches without enabling all game sounds.
- Our installed falling snow replaces new map-native snow emissions while active; disabling it restores the map's snow. Rain and other map effects are unchanged.
- Ramp marks sit 2 units above the ridden surface instead of 0.75, retaining the small constant depth bias. Native surfing acceptance is still pending.

### P1318 Smoother first views
- Fixed an unnecessary first-view lightmap rebuild that could hitch when a new area or water reflection first appeared, without reducing lighting quality.

### P1317 Colin Christmas theme
- surf_colin_blaster_69000 has authored snowy grass and exposed snow caps, distributed snowmen/trees/gifts, falling snow, cosmetic ice, storm sky, light mist and winter audio. Collision and liquid damage are unchanged.
- Its automatic theme can be disabled with the Display Info checkbox or r_colin_winter 0; individual snow/weather/prop options remain separate. Other maps keep their existing defaults.

### P1315 Winter rendering corrections
- Christmas props face outwards, and light mist becomes more visible without abruptly disappearing up close. Close fields shrink smoothly to retain their coverage budget.
- Ramp dirt sits slightly above the surface to reduce flicker while riding and at grazing angles.
- Enabled winter weather adds a persistent moving storm sky and reversible cool map lighting, recovers a late map-name update, and offers an immediate lightning check.

### P1314 Preview edits to a captured local TAS line
- Supported local TAS practice can keep the captured input line visible while seeking earlier, preview a change without replacing its original, then Keep or Discard it and Undo or Redo retained edits.
- Timeline keeps the main editing controls together; project, checkpoint, signing and legacy speed-search tools move to a separate Project tab. Ramp sections and the next-ramp-constrained solver are still in progress.

### P1313 Retry keeps momentum and the right start status
- A fresh retry carrying extra ground speed is shown as practice without changing your saved movement. Falls, upward pushes and continuing a running attempt keep their saved status.

### P1311 More map shaders in the loading warm-up
- Three additional shader variants used in Boreas and Demise join the loading-time warm list, without changing image quality or your saved settings.
- This expands first-visit coverage; it does not remove every first-use hitch or make busy map views cost the same to render.

### P1309 Optional winter weather preview
- An opt-in winter preview adds crossfaded outdoor/sheltered wind, delayed thunder and a short sky-only flash with lightning. It stays off pending moving-view checks.
- Frost and Christmas have provisional static liquid frost layers. Contents, collision, movement and lava damage are unchanged; this does not make liquids safe to walk on.
- Sky lightning is previewed on Frost. Christmas's larger sky mesh is held out by the sizing cap; Bluewinter has no eligible world sky/liquid mesh.
- Winter shader variants join the loading-time warm list rather than deliberately waiting for the first mist puff or storm.

### P1308 Independent TAS surf controls
- TAS practice gets a movement-key pad, independent auto strafe, fine turning, held jump/crouch and optional view-only vertical following. Recent warm ticks restore their control settings; the full captured-run editor is still being built.
- TAS turning preserves fractional/negative yaw instead of repeatedly corrupting its cached heading. Ground and crouched-ground guidance use the real mover rules rather than the old air-only preset.

### P1307 Ramp marks across client updates
- Ramp marks keep their intended brightness when client files update at different times; older shader files retain the previous rendering mode.
- Additional existing replays drive provisional ramp-mark bakes for Frost, Simple and Garden. The much larger Christmas overlay stays staged until its moving-view cost is checked.

### P1304 A permanent Christmas Santa hat
- A small red-and-white Santa hat has its own inventory cell and shares the headwear slot with the party crown; your aura stays independent.
- Linked players present on a trusted lobby during the enabled Christmas event earn the hat permanently. It is not auto-equipped, survives event end, and cannot be claimed from a web or menu visit. Event activation is off until its dates are chosen.

### P1301 Smooth view under a sloping roof
- With your head against a sloping roof the lowered view now follows the roof smoothly instead of stepping down in small jumps many times a second, for example flying fast under a descending ceiling.

### P1302 Holiday props and lightweight mist preview
- Snowmen, snowy decorated trees and gifts are available on provisional Christmas, Frost and Bluewinter layouts. Decorations are visual-only and can be disabled in Display Info.
- Optional light mist uses shader-animated wisps with strict size, range, draw and coverage caps. It defaults off until moving-view performance is qualified; enable Light mist in Display Info to preview it.

### P1297 Segmented runs are not completions
- Your profile's maps finished, completion bars and finished counts leave out maps you have only finished as a segmented run. Segmented times still show on the boards and in your maps with a time.

### P1296 Reflections at 60 per second
- Water and glass reflections are redrawn 60 times a second by default instead of 144, so they cost less GPU time. A saved 144 moves to 60 once; r_capturerate sets another rate.

### P1295 Chat commands typed any way
- Warp commands work however they are typed in chat: !b3, !b 3, /b 3, /b3 and !B3 all go to bonus 3, and !s, !m and !r take the same forms. They stay in your lobby's chat instead of the global room.

### P1300 Ramp scuffs, knife sounds and sky recovery
- Ramp wear has a longer adjustable range, stronger scratches and broad distant scuffs instead of losing the fine detail abruptly. Atlas seam bleeding and grazing-angle depth bias are reduced; smooth ride lines gain a subtle optional polish highlight.
- Knife inspect sounds warm after equip instead of first resolving every new sound during the animation. Sound aliases no longer keep paths from a different weapon package.
- A disabled or unsupported visualizer sky releases its stale override when a map loads, allowing maps without an authored sky to use the default sky again.

### P1299 Gravity carry status through supported jump-height offsets
- Carried gravity effects keep their run status through more supported normalized jumps on maps with a takeoff-height offset. Jump height, movement and normal map-authored effects are unchanged.

### P1298 TAS workshop remembers its tab
- Close and reopen the TAS workshop: it returns to Timeline or Shared instead of always switching to Next input. The timeline still refreshes before old rows can be edited.

### P1161 Fresh TAS project loads
- TAS projects can load and replay in a fresh supported session without first building rewind history. Legal-start rewind keeps working from a fresh start.
- Loading a TAS project while noclipping or held now refuses before changing your body or saved timeline. TAS remains assisted practice.

### P1154 TAS frame advance at 100Hz
- TAS pause, frame advance, retained rewind and input replay can use a selected 10ms Source clock as well as the existing 15ms clock. Default movement timing is unchanged.
- Clock changes stop queued TAS work instead of silently reusing it. Reload the map after changing its clock before starting a new timeline. TAS remains assisted practice.

## 0.1.39 2026-11-04

### P1292 No more 20-30 ms hitches from the game's string cleanup
- The game code's temporary-text cleanup could make a frame wait for it to finish (17-30 ms hitches on surf_demise, surf_boreas and surf_monolith); it never waits now, and runs about six times less often. 0.1% low on those maps: 125-189 to 150-258 fps.

### P1289 Replays: energy after scrubbing back and from replay saves
- Scrubbing a replay backwards measures energy from the zone the run had reached by then, not the last one passed, and a hand-set zero stays put.
- A save made while watching a replay keeps that replay's energy zero when you load it, instead of your own.

### P1283 No more lighting dips at light-heavy spots
- Models (your knife and hands, other players, moving props) no longer re-check every map light each frame: they remember which lights they can see and re-check a few each frame, brightest first.
- Walking through bhop_ceaseless's light-dense area: 1% low 137 to about 380 fps, stutters 175 to almost none. surf_voyager's moving asteroids no longer stutter.
- hl2_lt_vcache 0 turns it off.

### P1284 No hitch when a new part of a map comes into view
- Every map used to rebuild its lighting, unchanged, the first time each surface came into view, because the light setting the server sends just after a load looked different from the one the map was built with.
- On big maps that froze a frame as you surfed into a new area (measured on surf_monolith: up to 34 ms in one frame, about 85 ms over a run; the same rebuilds showed on surf_demise and surf_boreas).
- It no longer does, and the lighting looks exactly the same.

### P1282 Fewer shader stutters on a fresh install
- The game now ships a starter list of the shaders 26 maps need (more to come), so their first play on a new install builds those shaders while the map loads rather than mid-run (surf_boreas on a fresh install: 28 mid-run shader builds gone).

### P1286 Snow
- Snow falls on Christmas and winter maps (surf_christmas 1 to 3, surf_frost, surf_bluewinter, surf_iceworld), only where there is sky above you, at almost no cost to frame rate. `r_snow 0` turns it off, `r_snow 2` brings it to every map.

### P1291 Record lines in chat
- When someone sets a personal best or a record, the chat line no longer starts with a "board" title: the green line says it. In the main menu's chat it now shows the player's picture, as the in-game chat does.

### P1290 Landing sounds as in CS:S
- With game sounds on (cl_game_sfx), a hard landing played Counter-Strike's fall-damage grunt, which CS:S only plays when you take fall damage (so never on surf). It now plays the footstep of the surface you land on, at full volume, as CS:S does.

### P1288 Tinted map surfaces as bright as in CS:S
- Map surfaces tinted by their material ($color) were drawn much darker than CS:S draws them: Source applies that tint in linear light. surf_eternity's stair-room walls are now about twice as bright, close to CS:S.

### P1285 Zone lines only where you can see
- Zone outlines now show only while their part of the map is visible from where you are, as in Momentum, so other stages' and bonuses' zones no longer show through the sky. `zone_pvs 0` shows them all again.

### P1280 CS:GO hands no longer cost frame rate
- The knife, CS:GO arms and sleeve each worked out the map's light at your eye every frame; they now share one look-up, refreshed up to 60 times a second (r_viewmodel_lightrate; 0 = every frame). bhop_ceaseless, hands out, moving: 462 to 628 fps.
- The plain-leather gloves (Specialist, Sporty, Slick, Motorcycle and others) no longer draw almost black.
- r_drawviewmodel 0 hides the knife and the hands, as it does any other view model.

### P1279 Replays measure energy from their start zone
- A replay's energy readout is measured from the start zone of the track or stage it plays, instead of from a jump when the replay begins outside that zone. Closing a replay gives you back your own zero.

### P1281 Faster water and glass at high frame rates
- Water and glass reflections are redrawn about 144 times a second instead of every frame (turned with your view in between, and redrawn at once if you move or turn far).
- At 200-300 fps on surf_eternity's glass that is about 40% more frames; at or below 144 fps nothing changes. r_capturerate sets the rate (0: every frame).

### P1275 Smoother map lighting
- Source maps' lighting is filtered bicubically, as Half-Life 2's 20th anniversary update does: smoother light and shadow gradients where a map's lighting is coarse. No measurable cost; r_lightmap_bicubic 0 turns it off (from the next map).

### P1277 Fewer shader stutters
- A surface drawn a new way for the first time (water seen from a new spot, a lit model, fog) needs a shader built for it.
- When your graphics driver had not kept that shader -- after an update, or once its cache fills -- building it froze a frame mid-run for up to a fifth of a second.
- The game now remembers those shaders and builds them while the next map loads, behind the loading screen (surf_boreas with a cold driver cache, as after an update: 11 mid-run stalls gone).
- It learns as you play: a map's first run can still hitch once at a new shader, and every later load covers it. That load takes up to about half a second longer the first time after an update. `r_glsl_warm 0` turns it off.

### P1278 Worn ramps
- On 23 maps, ramps look used: a film of dirt that riders have wiped clean along the lines people surf, and scratches where they land on a ramp, more and longer the steeper the landing (a landing parallel to the ramp leaves none).
- Built from replays of real runs. r_rampwear 0 turns it off.

### P1276 Smoother reflections
- With MSAA on (vid_multisample), water and glass reflections are anti-aliased too, so reflected edges no longer stair-step (surf_eternity's river and glass floors). It costs about 0.05 ms a frame on a fast graphics card;
- r_reflectmultisample 0 turns it off.

### P1274 surf_santorini's windmills
- Windmill sails no longer hang in the sky on their own. They were sent from places where the map hides their tower, and popped in and out as they turned. Now they show where the rest of the windmill does.

### P1273 Gulls that move
- Decorative props that play an idle animation in Source now play it here too: surf_santorini's gulls flap. Only props nothing collides with animate.

### P1272 Smoother spinning scenery
- Rotating and orbiting scenery, like surf_voyager's asteroids, now moves smoothly instead of stepping.

### P1271 No half-drawn stations on surf_voyager
- On maps built without visibility data (68 of them), parts of the map sealed off from where you are no longer show through the sky, cut off and shrinking as you got closer. Source hides them, and now so do we: surf_voyager's far stations among them.

### P1270 No black squares in space
- Glowing orbs drawn with a multiply effect, like surf_voyager's, no longer show as black squares.

### P1269 No seam on blended floors
- Blended displacement floors were drawn a quarter darker than the flat floor beside them, so a sharp seam showed (surf_starvald's crystal floor). Both now take the same light, as in CS:S.

### P1268 Glass and ice layers in order
- On a model with glass or ice, the see-through layers after the glass now draw over it, as in Source (surf_starvald's start platform).

## 0.1.38 2026-11-03

### P1267 No hitch after you spawn
- A map load ends sooner and the half-second hitch a moment after you spawn on a new map is gone: the game no longer re-reads every material in memory twice per load (bikini_bottom after another map: 1.1 s down to 0.04 s).

### P1266 Lighter movement prediction
- The game no longer redoes a collision check it has just made with exactly the same inputs: movement prediction on surf_voyager does about a fifth less work. Movement itself is unchanged, bit for bit.

### P1265 The map on the loading screen
- The loading screen shows the map you are loading at the bottom left: its picture, its name, and its author, tiers and stages as the map list has them.
- The loading screen's text is a little smaller.

### P1264 Bump mapping on map walls and floors
- Walls and floors with a bump map are lit the way Source lights them, so their cracks, grain and relief show (bhop_ceaseless's rock walls, surf_sedona's sand). Some read a little darker or brighter than before. hl2_rnm 0 turns it off.

### P1263 Particle rings on surf_fantasy
- surf_fantasy's laser rings have their swirling glow back, and the map's other particle systems all load (it lists three particle files; only the first was read).

### P1262 Smooth leaves and fences with MSAA
- With vid_multisample on, the cut-out edges of leaves, fences and grates are smoothed too, about as well as render scale 2, at no measurable cost. r_alphacoverage 0 turns it off.

### P1261 Less CPU work on Source maps
- Source maps no longer re-check every prop and terrain patch against what you can see each frame while you stay in the same part of the map: surf_demise spends about a quarter less time on it.

### P1259 The loading screen keeps moving
- Big Source maps no longer freeze the loading screen while they build their collision, materials and sky: on surf_eternity those were stops of 1.4 s, 0.4 s and 0.4 s.
- Starting a map yourself spends less time placing its entities.

### P1258 The loading screen says what it is doing
- Bottom left: the server it is connecting to and for how long, a download's file, percent, speed and size left, and how far the load has got.
- A join that downloads files (a lobby's update, a missing map) keeps the loading screen up instead of showing a black screen.
- The newest step shows how long it has been running, and the whole load's time sits under "Loading".

### P1257 Sharper depth far away
- The camera's near clip is 2 units instead of 1 (gl_mindist; Source's 3D sky uses 2, its main view 7), so surfaces far away fight each other less. Weapons keep 1. `gl_mindist 1` puts it back.

### P1256 Lasers that switch on and off
- Lasers that maps turn on, off or flash now do it: surf_hyper's ramp lights chase, and secret and stage lasers appear when their trigger fires (315 switches on 33 maps).
- `ent_fire <name> <input> [value]` fires a map input as in Source. It needs sv_cheats 1, and after it every run on that map counts as cheated until the map reloads.

### P1254 Energy on maps without a start zone
- With no start zone (or before you stand in one) the energy readout measures from your last jump and says "from jump", instead of "-- no start zone".
- Standing where you spawned or teleported now reads 0 before your first jump; it used to read the few units you dropped on arrival.

### P1260 MSAA works on Source maps
- vid_multisample 4 (or 8) now smooths the edges of the 3D view. Before, it did nothing on Source maps, because the scene is drawn off-screen first.
- Render scale 1 with MSAA 4 smooths edges like render scale 2 for about half the graphics work. Leaves and fences cut out of textures are not smoothed by MSAA.

### P1253 Momentum Beta map leaderboards
- Leaderboards of the Momentum maps still in Beta testing are now collected too, for the Beta maps the server has.
- When Momentum approves a map and clears its testing runs, the old testing times and replays are cleared here too, so the board shows only runs Momentum still lists. Maps whose testing runs Momentum kept keep them here.

### P1252 Laser beams on Source maps
- Laser beams in Source maps are drawn now: surf_fantasy's blue rings, surf_sky_city's flickering lasers and about 2,000 more on 180 maps.
- Lasers that start switched off, move with a part of the map or have no target are not drawn yet. vbsp_lasers 0 hides them.

### P1251 No more black stripes over fake skies
- The black hatching over far-away fake sky windows (surf_fantasy's last stage) is gone.

### P1250 Water windows and coloured brushes on Source maps
- Water and glass surfaces take the map's lighting instead of glowing flat white: surf_bikini_bottom's windows are a thin layer of water again, and water and lava on about 290 maps look as they do in Source.
- Coloured brushes show their colour, and maps that change a brush's colour now do it (surf_orbion's flashing panels).

### P1249 Prop lighting on older Source maps
- Props on 770 Source maps no longer take their light from the wrong place: surf_pantheon's yellow pillars are marble again.

### P1248 No more snags where prop ramps meet
- Ramps built from props no longer catch you where two pieces meet: the end of surf_sedona's ramp 3 and surf_pantheon's ramps ride through.
- The lobbies have it now. Until your game updates you may see a small correction at those spots on a lobby.

### P1247 Steadier KSF replay downloads
- One broken KSF replay file no longer stops that round of downloads, so the backlog keeps moving.
- Replays the converter could not read are fetched again as soon as the converter is updated, instead of waiting a week.

### P1245 Half-rate reflections (optional)
- New setting r_capturehalfrate 1: water and glass reflections are redrawn every second frame and turned with your view in between. surf_eternity's glass about 40% faster, water maps up to 24%.
- Off (0) unless you set it. When you strafe fast, nearby things in a reflection can trail by a frame.

### P1244 A new loading screen
- Loading a map shows what the game is doing, step by step, in white text: the newest step on top, the earlier ones pushed down and fading.
- A spinning white wireframe keeps you company while it loads: the lobby avatar or a surf ramp, seen from above.
- "Loading" in the bottom right corner, with its dots growing and shrinking.
- The screen keeps moving through most of a load instead of freezing between steps.

### P1243 A warning before a lobby restarts
- When a lobby has to restart for an update while people are playing, everyone on it gets a chat message ten seconds before.

### P1242 Faster Source maps with light shafts and sprites
- The check that hides light shafts and sprites behind a skybox now runs only when you have moved, not every frame. surf_eternity's start room: 190 -> 398 fps; surf_garden while running: 271 -> 352 fps. What is hidden is unchanged.

### P1240 KSF replays and boards, faster
- KSF replays now download four times as fast, so the roughly 46,000 still waiting should arrive in about a week instead of a month.
- Every KSF stage, bonus and style board is fetched once before any board is paged deeper, so boards nobody had fetched yet appear within a few days. Maps players are looking at still go first.

### P1238 Fewer snap-backs, better prediction-error reports
- Teleports on maps that put a second teleport at the arrival point (surf_frey_remake and about 40 others) no longer snap you back about 185 units after you arrive.
- Letting go of a save-lock hold no longer leaves you frozen in place for a moment when a network packet is lost (players far from the server saw large snaps).
- Stepping quickly through your saves at high ping no longer predicts the wrong save.
- The prediction error box no longer appears for things that are not errors: joining a map, Go to spawn, resets the game sends without predicting, ghost or spectate, and teleports only the server can run.
- A report you send now carries the lobby's own record of the moments around it, so causes such as lost packets can be told apart from movement bugs.

### P1239 Lighter HUD
- The HUD's own script work is about an eighth lighter: the rounded movement keys are drawn as one piece each (they look exactly the same), and settings the HUD reads every frame are now read ten times a second.
- A HUD or zone setting changed from the console or a bind now shows within a tenth of a second (instantly while the HUD or zone editor is open).

### P1237 Faster skies on Source maps
- The flat sky on Source maps is drawn whole, as Source draws it, instead of being worked out piece by piece
  every frame: about 8-10% more frames per second where a lot of sky is reflected (surf_eternity's glass),
  with the same picture.
- New setting `r_skyroom_scale`: 0.5 draws a map's 3D sky at half resolution, which at `r_renderscale 2` is
  your screen's own resolution. surf_demise runs about 16% faster at those settings with a slightly softer
  sky; maps with a simple sky gain nothing. It is off (1) unless you set it.

### P1236 Kerned, fuller text
- Letters in the menus, the HUD and chat now sit as their font intends: pairs like AV, To, Ty and P. close up (kerning). Number readouts do not move, because neither font kerns digits.
- Text edges are a little fuller, so light text on dark reads crisper. `r_font_kerning 0` and `r_font_gamma 1` (then `vid_reload`) bring back the old look.
- Carets and selections in chat and name fields sit right against the letters, and a map message's typing effect no longer jumps as letters settle.

### P1230 Ice aura glow, party crown
- The Ice aura is now a soft glow around the player instead of stacked shells that looked like panels, and it is cheaper with many wearers. It never shows through walls.
- The party crown is one piece with a printed band and points, so no half of it draws over the other.

### P1235 Source maps: huge models out of sight, the visualizer sky
- Very large models the map hides from where you stand no longer draw through the sky (surf_remeanian's window frames).
- With the visualizer sky on, scrolling and animated textures no longer flicker as you move (surf_dragonfall's lava panels).

### P1233 Faster water on Source maps
- Water with live reflections (hl2_water 2) draws faster with the same picture: about 22-49% more frames per second at your
  surf_garden and surf_boreas saves.

### P1232 Records from KSF and Momentum
- KSF times and demos are collected again: one bad entry in a player's KSF profile had stopped all KSF collection since 30 October.
- The leaderboards of 349 Momentum maps that had never been fetched are now collected.
- Momentum demos set aside as made on a different version of the map are added once the server holds that version (about 1,400 qualify now).

### P1231 Faster combined leaderboards
- The combined leaderboard opens faster on big maps.

### P1218 Source maps: sky leaks, distance fades and map decals
- Light shafts and sprites behind a skybox wall no longer show through the sky (surf_eternity).
- Panes that fade with distance (surf_sidelines' doorway) fade at the same distance as in CS:S when the game renders above screen resolution.
- Map-painted text and decals sit just off their wall instead of on it, so they can no longer flicker against it.
- Animated screens on models play (surf_eternity's screens behind its glass panels), and models that fade out with distance fade instead of popping (surf_remeanian's end).

### P1217 Mirror floors and water on Source maps
- Mirror surfaces (CS:S reflective glass) now reflect the scene instead of drawing flat white, which fixes surf_eternity's pink rivers and pools.

### P1215 Zone editor shows where reset puts you
- The zone editor draws each start and stage spawn, and the map's own teleport destinations, with their facing.
- A start or stage without a set spawn now resets you onto the map's own teleport destination inside it, facing the way the map does.

### P1229 Faster run submits
- A new time reaches the leaderboard sooner: the server no longer reads every board row before storing a first finish or a new stage time.

### P1228 Your progress loads with the game
- The maps you have finished load when the game starts, so the Maps screen shows Complete! on every one of them as soon as it opens.
- Until they arrive, the Maps filters say "loading your progress...".

### P1227 Load lead-in
- A quick tap of the load key now holds you at the save until the server has placed you there (and at least 100 ms), so the view no longer snaps forward.
- hud_edit has a new Save & load pane to set the lead-in, from none to one second, or typed in milliseconds.

### P1226 Leaderboards refresh themselves
- When anyone on your lobby sets a new time, open leaderboards fetch it again on their own.
- Pressing TAB fetches a board again if it is more than 15 seconds old, and the board says "your run: submitting..." until your own finish is in.

### P1225 Colour and items when you join
- Joining a lobby now loads your items and your colour within about a second, instead of after several.
- The main menu's Stats page asks for your inventory again after you join or leave a server.

### P1224 Text selection
- A selection made by dragging in a text box, such as the map search, stays selected when you let go outside the box.

### P1223 Zone editor teleport
- Double-clicking a zone in the zone editor teleports you to it even before you save. An unsaved zone puts you in its middle, on its floor.

### P1222 Maps without lighting run much faster
- Maps compiled without lighting (surf_leet_xl_beta7z, surf_legends_css, surf_rebel_resistance, surf_ev2 and about 25 more) no longer redraw their lighting every frame: on our test PC surf_leet_xl_beta7z went from about 200 to over 750 fps.

### P1221 Tidier menus and HUD
- Key letters sit centred on their keys in the key hints, the save menu, the Steam link box and the report box.
- The prediction-error report box, the name screen and the keys display use the same rounded style as the rest of the interface.
- Inventory: the hint under the items is larger, and the ON / OWNED tags are clearer.

### P1220 In-game chat
- The chat box no longer puts "to everyone" in front of what you type or shows the Enter/Esc hint. A small tag at its top right says who will get the line.

### P1219 Console crash on a map change
- Fixed a crash when the console was open with a command half typed while the map changed or reloaded.

### P1214 Main menu chat
- Messages in the main menu chat sit close together, each as tall as its text.
- The notes about saving and encryption under the chat are gone.

### P1169 Larger Maps filter text
- Maps: larger, sharper native-pixel filter text, with roomier controls that wrap on smaller windows.

### P1234 Your records when you link Steam
- Signing in with Steam now fetches your KSF and Momentum personal bests, KSF stage and bonus times included, and accounts that play are refreshed regularly, so your records stay up to date.
- Momentum leaderboards nobody is playing are refreshed in rotation, about once a week.
- KSF collection recovers sooner after a timeout, and one failing job no longer holds up the others.

## 0.1.37 2026-11-02

### P1213 Fog on Source maps looks like Source's
- Fog now thickens toward the edges of the screen as it does in CS:S and Momentum, not only straight ahead. On surf_shape the horizon above the dunes is orange haze, as in CS:S, instead of a white band.
- Glowing signs, sky blends, rain and other unlit surfaces fade into the fog like the walls around them, including on maps where they were not fogged at all before.

### P1212 The launcher and game say World of Surf in Windows
- WOS-Launcher.exe and the game now name World of Surf as their publisher and product in Windows (file Properties, SmartScreen, antivirus). They used to name the FTE engine, or nothing.

### P1211 Gravity launchers and delayed speed stops no longer snap
- Maps that change your gravity (bhop_decimus's launch pads and about 200 others) are predicted by your game, so the view no longer jumps when gravity flips or comes back (up to 8 units before). Needs this update's game.
- A map script that stops you a moment after a teleport (surf_oneiric's hub) is predicted too, on every game version.
- The server applies a map's gravity change on your next move, as Momentum does.

### P1210 KSF replays show crouching
- KSF replays now show when the player is crouched, including a crouch the ramp keeps after the key is let go, worked out from how the player moves since KSF does not record it.

### P1209 The launcher is now WOS-Launcher
- The World of Surf launcher is now WOS-Launcher.exe (WOS-Launcher on Linux). Download it again from the site to get it; the launcher you have keeps working.
- The in-game update restart uses WOS-Launcher when it is next to the game, and your old launcher otherwise.

### P1208 The launcher shows your version and the new one
- The launcher says which version you have installed, which version an update brings (for example 0.1.36 -> 0.1.37), and when you are already up to date.

### P1207 No prediction-error box in a game you host
- A game running on your own PC (single player) no longer offers prediction-error reports. Nothing is predicted there, so a teleport or `!r` was being reported as an error.
- When `!r` or another reset cannot be predicted, the report now says why, and it names the game files you were running.

### P1206 Chat: fairer saved history, read on every install
- The saved lobby chat keeps everyone's lines: a few spam accounts can only push out each other's, and a quiet friend's message always shows in your chat.
- A message you have read is read on your account, so a friend's Message count clears on every install, and one you saw in a game counts as read.
- Clicking a name in the menu's lists no longer opens the wrong player when the list updates during the click.

### P1205 Map scripts that set your speed at teleports work
- About 40 maps (surf_centipedes, surf_affliction, surf_skipalot, surf_spaceracer and others) set your speed when a teleport or trigger fires. Those scripts now run, as on Momentum, and your game predicts them, so there is no snap.
- bhop_decimus: its jump triggers that change gravity now work, as on Momentum.

### P1204 surf_sirena's barriers stay open after a save load
- A barrier you opened on surf_sirena stays open when you load a save, rewind or resume from after its trigger. A save from before the trigger still finds it shut.

### P1203 Zone editor: drag corners, edges and faces
- Zone editor: select a zone and press Edit shape, then aim at a corner, edge or face to light it up and hold Mouse1 to drag it. Right-click cancels, Esc returns to the panel.
- Dragged corners snap like placing does: to the grid (the wheel changes it), to the map's corners and edges, and to other zones. Side faces push and pull, top and bottom set the height.

### P1202 3D skies show their moving scenery
- Things placed in a map's 3D sky (props, trains, spinning parts) now show behind the map, as Momentum shows them. surf_shape's sand dunes, surf_centipedes' bird flocks, surf_colony's skyline and surf_destruction's cyclones were missing before.
- Sky props that have an animation now play it: surf_shape's dunes move past.

### P1201 surf_view and ent_view: outlines and see-through planes
- surf_view now outlines every face it shows, so you can tell where one ramp ends and the one behind it starts. ent_view's trigger volumes get the same outlines.
- New setting surf_view_style: 0 dotted (the old look), 1 dotted with outlines (default), 2 see-through planes, 3 see-through planes with outlines. surf_view_fill sets how strong the fill is.

## 0.1.36 2026-11-02

### P1200 Chat is saved, and friends can get your message later
- Main-menu chat and messages to friends are now kept for 30 days, so a friend who was offline sees your message the next time they play.
- You can message a friend who is offline. A friend with new messages shows a count on their Message button and at the top of the chat.

### P1199 Map leaderboards in the menu work like the in-game one
- The map leaderboard opened from the main menu now has All games plus each game, every stage, bonus and bonus stage in a list down the side, and a delta column.
- It loads more times as you scroll; the earlier, top and refresh buttons are gone.

### P1198 Clicking a player opens their Stats page
- Clicking a player's name or picture in the main menu (friends, leaderboards, story ranking, lobby chat) opens the full Stats page for them; Back returns to where you were.
- Friends have a Message button, and the Stats page has an Inventory button that shows a player's items.

### P1197 Zone editor snaps to the map's corners
- Zone editor: Edge snap now snaps to the corners and edges of the map surface under your crosshair, not only to other zones, and it starts switched on.
- A square marks the snapped point, the surface being read is outlined, and the placing hint shows what your next click takes, with its coordinates.

## 0.1.35 2026-11-02

### P1196 No snap when surf_network2008's spawn sends you on
- Teleports that the map switches on and off with timers (surf_network2008's spawn and jail teleports, and others like them) are now predicted, so they no longer snap you back and forth by up to 2000 units.


### P1195 Report a prediction error with one key
- When the game corrects your position by a lot (a "prediction error"), it now keeps a short record of the last few seconds and shows a box on the right. Press F6 to send it to the lobby so we can find the cause.
- Nothing is sent unless you press F6. `cl_prederr_ask 0` keeps the reports on your PC without asking; `cl_prederr_report` sets how big an error has to be (32 units).


### P1193 surf_sirena's barriers open after their trigger
- surf_sirena's invisible barriers now let you through once you have passed the trigger that opens them, as on Momentum, and stay shut for anyone who skipped it.
- An opening lasts for the run that earned it: after a reset, a save load or a resumed run, pass the trigger again.

### P1192 surf_olivia's sky is back over the hub
- On maps with a 3D sky, the whole sky is now drawn behind it, as Momentum does. surf_olivia's start area showed black (with smears) where the sky should be.


### P1191 Missing textures from a game you do not have draw as flat colours
- Walls whose material comes from a game you do not have (surf_utopia without Team Fortress 2) now draw as a flat colour, lit like the rest of the map, as Momentum does, instead of the missing-texture checker.
- A map whose sky comes from a game you do not have now shows the default sky instead of black.


### P1190 Teleports arrive with their ramps already there
- Ramps and props at a teleport's destination, and at your reset point, are now there the moment you arrive instead of appearing a moment later (about one ping online).

### P1189 Newly zoned maps reach the Maps menu within a minute
- When a zoner publishes a map's zones, the Maps menu now shows that map as zoned at its next refresh, within about a minute, instead of up to six minutes later.


### P1188 surf_skyhaven's glass is no longer a missing texture
- surf_skyhaven's glass panes (and rj_tattarrattat's grates) use Momentum's own fallback materials. The game now finds them in your Momentum install instead of drawing the purple checker.


### P1187 One chat for every lobby and the main menu
- With a linked Steam account, what you type in a lobby's chat now reaches every lobby and the main menu chat, tagged with your lobby number. Press TAB (or the team chat key) to talk to this lobby only.
- Lines from other lobbies show their number, like [#4], and lines from the main menu show [menu]. Commands starting with ! stay in your lobby.


### P1186 Enter sends menu chat messages
- In the main menu's chat, Enter (or keypad Enter) now sends your message on the Maps, Story and Stats screens too, not only on the front page.


### P1185 Boosters no longer put your next run in practice
- On maps whose boosters switch themselves off and back on (surf_mesa and many others), riding one, then resetting or loading a save and riding it again, no longer marks the new run as practice.


### P1184 Zone editor: type a zone's exact size
- The zone editor shows the selected zone's size and its six edges (x min/max, y min/max, bottom, top). Click one to type an exact number, or roll the wheel over it to move that edge a grid step.
- `zone_edit face <xmin|xmax|ymin|ymax|bottom|top> <value>` does the same from the console.


### P1183 Two wrong console messages
- Loading a save on a map where you have none says "nothing saved on this map" once instead of twice.
- Shift + mouse wheel noclip speed now works on lobbies; it used to refuse with "first local seat only".


### P1182 The sun hides behind props
- A map's sun glow (env_sun) no longer shines through pillars, statues and other props in front of it (surf_pantheon's columns, for one). Glass still lets it through.


### P1181 Stage resets face the right way
- On maps whose zones were made in the zone editor, !r and !s now face you where the map's own stage teleport faces, instead of wherever the zoner happened to be looking (13 maps, e.g. surf_for_shareholder_value, surf_sirena, surf_midnight).


### P1180 Zone publishing is instant, with a history
- Publish has one button now, and it takes effect at once: the lobbies on that map restart with the new zones straight away (runs in progress there end). A bad zone no longer waits for people to finish.
- The zone editor's new History page lists every published version of the map, who published it and when; click one to load it, then Save and Publish to bring it back.
- The site's Zoning page shows who zoned each map, and a map drops off the list as soon as it is published.


### P1178 Maps list: snug rows, map authors, sharper pictures
- Each map in the Maps list now takes the height of its picture plus a little padding, so more maps fit on screen.
- The map's author is shown after its name in the Maps list, and under the map name in the in-game Map info.
- Map pictures in the list are sharper: they are now stored at the size they are drawn.


### P1177 Your hud_player colours are kept
- The colours, belt, trail and glow you pick in hud_player now stay picked after you restart the game, instead of going back to a random colour.


### P1176 Site: a cleaner front page and a zoning list
- The front page is down to the logo, a rainbow BETA and the downloads; hover BETA for the build details.
- New Zoning page on the site: every KSF map that still needs zones, with its picture, tier, stages, bonuses, plays and mapper. Maps drop off a few minutes after a zoner publishes them.


### P1175 Zone publishing works again
- Zone admins can publish from the zone editor again. Since 1 Nov every upload had answered "Zone uploads unavailable".

## 0.1.34 2026-11-01

### P1174 KSF map pictures and zones
- 17 KSF maps that showed no picture in the map list now have one, among them surf_corrosion, surf_froots2, surf_null and surf_kraken.
- Nine KSF maps can now be timed, with zones from their Momentum versions that start and stop where KSF's timer does: surf_benevolent_refix, surf_beverages_remix, surf_neoteric_retexture, surf_nsz_fix and surf_pyzire_retexture.
- Also surf_devil_css, surf_lore_css and surf_wasteland2_css (restarts fitted to these builds), and surf_fast_css for its main track; its bonuses still need zones.

### P1173 Duck held through a save load
- Holding duck while you load a standing save now crouches you straight away, the same as pressing duck right after the load. Before, you stayed standing until you let go and pressed duck again.

### P1172 Recoverable zone updates
- Zone updates that cannot confirm completion keep their recovery state instead of being reported as safely reverted.

### P1171 Profile playtime and course attempts
- With online play on and Steam linked, official-lobby play records your connected time, map time and main/bonus course starts on your public profile.
- Counters retry without double counting; offline/unlinked play is not uploaded and old unrecorded hours are not invented.

### P1170 Clean lobby disconnects
- Switching or rejoining lobbies and closing the game normally now cleans up the old connection instead of leaving a ghost player until timeout. Weapon Drop still works without disconnecting you.

### P1168 Public inventory and map statistics
- Other players' profile inventories show their owned items, including items they are not wearing. Public inventories are read-only and keep each item's saved colour.
- Profiles show tracked playtime when available. Missing tracking is labelled instead of inventing historical hours.
- The main-menu map leaderboard has main/bonus course buttons, optional map playtime and attempt counts, and clickable player pictures that open a profile.
- Use !time or !time followed by a player name to query tracked total/map hours and main/bonus attempts when the server has that data.
- After Jump to me, scroll upward to fetch earlier ranks instead of getting stuck at the sought page's first row.

### P1164 Paper party crowns
- The party hat is now a cylindrical paper crown with upward-pointing triangular tips instead of a cone. Your existing hat colour and equipped state stay the same, and its inventory icon matches the new shape.

### P1163 Softer ice aura
- The inventory's ice aura now fades outward from your player instead of drawing a hard blue stroke. Equipping the aura and paper hat still works independently.

### P1160 Profile inventory and cosmetics
- Your player profile now has an attached 4x4 inventory. Click an owned item to equip or remove it; selected cosmetics are visible to other players.
- Linked Steam accounts receive a light-blue ice aura and a paper party hat with a persistent, randomly assigned colour.
- Player profiles show colour-coded Tester, Zoner and Developer badges. Badges are cosmetic, not map-editing or administration permissions.
- The Maps menu now uses one Surf/Bhop switch instead of the full gamemode filter strip.

### P1158 Gravity carry status through fatigued jumps
- Carried gravity effects keep their run status through more supported fatigued jumps. Jump height, movement and normal map-authored effects are unchanged.

### P1156 Smoother ducking under roofs in slow practice
- Keep the camera's movement and eye height together while ducking, unducking or clearing a low roof at slow practice speeds. Normal movement and run status are unchanged.

### P1152 Gravity carry status through recovered standing jumps
- Carried gravity effects keep their run status through ordinary standing jumps with fully recovered stamina. Jump height, movement and normal map-authored effects are unchanged.

### P1151 Return from slow practice without reconnecting
- At an eligible start, stand still and restore host_timescale to 1 to arm a fresh clean attempt at the same position. Wait for the server's confirmation before moving.
- If the clean restart cannot be confirmed, normal speed returns but the attempt stays practice. Earlier practice attempts are not turned into ranked runs.

### P1147 Smoother practice speed changes and short resets
- Keep the camera continuous when switching practice speeds or returning to normal speed, and stop blending across short zone resets even when the destination has no angle.
- Movement and the connection's earlier practice status are unchanged.

### P1145 Gravity carry status through normalized crouch jumps
- Carried gravity effects keep their run status through more normalized crouch and duck-transition jumps. Jump height, movement and normal map-authored effects are unchanged.

### P1144 Keep the slow-practice camera fix in newer builds
- Integrate the smoother slow-motion camera with the newer game changes, without changing movement or clearing a connection's earlier practice status.
- Practice classification now covers another supported jump setting; movement is unchanged.
- TAS: Share saved legal-start projects and browse shared revisions and contribution ranges for the current map.
- TAS: Open a shared revision as a new local TAS project without replacing existing projects or recovery files. Shared TAS inputs are never ranked human runs.

### P1141 Gravity carry status through normalized takeoff
- Carried gravity effects keep their run status through more normalized ground jumps. Jump height, movement and normal map-authored effects are unchanged.

### P1139 Gravity carry status through stock takeoff
- Carried gravity effects keep their run status through more ordinary ground jumps. Jump height, movement and normal map-authored effects are unchanged.

### P1138 Smoother slow-practice camera
- Slow-practice camera motion blends completed movement ticks instead of freezing between repeated poses. Normal-speed movement is unchanged.
- host_timescale help now distinguishes restored normal speed from the connection's existing practice status; resetting the attempt does not clear earlier slow-practice use.

### P1136 Airborne gravity carry status with vertical boosts
- Carried gravity effects keep their run status during more airborne vertical boosts. Movement, boost amounts and normal map-authored effects are unchanged.

### P1135 Airborne gravity carry status with horizontal boosts
- Carried gravity effects keep their run status during more airborne horizontal boosts. Movement, boost amounts and normal map-authored effects are unchanged.

### P1134 TAS verification groundwork
- Operator checks can replay legal-start TAS projects in a fresh native server. Ordinary run rankings are unchanged; TAS submission and board integration are still in development.

### P1133 Airborne carry status with jump input
- Run status follows carried gravity effects during more airborne commands. Holding jump in the air no longer suppresses this status; movement and real jumps are unchanged.

## 0.1.33 2026-10-30

### P1131 Earlier airborne gravity carry status
- Run status follows more carried gravity effects during airborne movement. Normal gravity, map-authored behavior and movement are unchanged.

### P1130 Stats and WOS completion
- Full stats refreshes its records when reopened after a home Surf / Bhop / All change. Switches start in the right position and fit narrow home panels.
- Show all stays selected during the same session, but starts off next launch.
- Complete! and completed-first sorting count only your clean main finishes in World of Surf, on that map build. Momentum and KSF times stay visible without marking it complete here.

### P1129 Airborne gravity carry status
- Carried gravity effects keep the right run status when they affect airborne movement. Gravity amounts, retry speed and normal map-authored effects are unchanged.

### P1128 Neutral map speed inputs
- Neutral map speed inputs no longer make a clean run unranked. Real speed effects keep their existing run status and movement.

### P1127 Unchanged map effects keep their status
- Repeated map inputs that leave gravity or a pending boost unchanged no longer make a clean run unranked. Gravity and boost amounts are unchanged.

### P1126 Momentum pad carry status
- Reversal and catapult pads keep the right run status when enabled by an earlier attempt. Their speed, aim and timing are unchanged.

### P1125 Gravity carry status
- Gravity zones keep the right run status through a delayed return to normal gravity. Gravity values and movement are unchanged.

### P1124 Teleport carry status
- Map teleports keep the right run status when enabled by an earlier attempt. Their destinations and movement are unchanged.

### P1123 Speed-pad and conveyor carry
- Speed pads, conveyors and the Monolith booster keep the right run status when an earlier attempt enabled them. Their movement and normal current-run behavior are unchanged.

### P1122 Stats by kind of map
- The stats on the main menu have a Surf / Bhop / All switch; every figure and tier row follows it, and Full stats opens on the same choice.
- On the full stats page the All / Surf / Bhop buttons are one Surf / Bhop / All switch.
- The Unrated row on the main menu counts your finished unrated maps (it showed -- / --).
- The Maps screen's "show all" starts off every time you launch.

### P1121 Speed-effect carry
- Player-origin speed effects carried between attempts keep the right run status. Normal map-authored speeds and movement are unchanged.

### P1120 Boost activation carry
- Using a boost enabled by an earlier attempt marks the new run unranked. Normal map-start and current-run boosts keep their behavior and speed.

### P1118 Reliable save loading
- A refused save load leaves your current position and speed alone. Valid loads still keep their saved speed.

### P1116 Finishing a run no longer stutters
- A lobby's input-journal checks now happen as you play, with sending in the background. Finishing no longer holds up those frames (20 ms and 17 ms measured with a 3 MB journal, more on long runs).
- Connecting to a lobby no longer pauses a frame to prepare its input-journal check.
- The map tables the menu fetches from the Pi at startup load over several frames instead of one (68 ms measured).

### P1110 TAS projects from the start zone
- `tas project save` in a `tas start` session saves a project that begins standing at the start zone, before the timer: everything from the first step is in it.
- `tas project load` of one puts you at that start zone and plays it back exactly, through the timer's start. Saving again after a load, or after more steps, makes the next revision of the same project; a new `tas start` begins a new one.
- Named checkpoints are not available on these projects yet.

### P1114 Map downloads no longer stutter the game
- Downloading a map runs in the background: before, looking up and connecting to the map host could hold up a frame (one measured download held one for 62 ms).

### P1113 KSF maps have their tier on profiles
- Profile tier lists use KSF's tier when Momentum has none, so maps like surf_anubis (tier 8) are listed under their tier instead of Unrated. Completion figures change to match.

### P1112 Stray maps are out of the map list
- 140 maps on no Momentum or KSF list (old beta copies that slipped into the library) no longer show in the map list, lobbies or completion.

### P1111 Maps screen filters
- Clicking "all" again clears every mode, so you can pick one alone.
- With "show all" off, maps without zones or a picture are hidden (a search still finds them).
- The filter group names are easier to read.
- The Library filter goes by catalogue: Momentum shows Momentum Mod's maps and cs:s shows KSF's, whichever folder a file is in.

### P1109 Maps without zones say why
- A map without timer zones now says "no zones", or "no zones: KSF map" for KSF's Counter-Strike: Source maps, whose zones are not public.
- surf_blastpit, surf_shape and surf_simple_v3 have zones and now show it.

### P1108 Profile pictures no longer stutter the game
- Pictures load about twenty times faster and one at a time, so lists full of them no longer hitch.

### P1107 Leaderboards opened at your time scroll up
- A leaderboard opened at one of your times now loads the ranks above it as you scroll up.

### P1106 Stats: map lists, and Surf / Bhop on every figure
- Click "maps" for every map you have a time on, or "maps finished" for the maps you have finished, with a switch to the ones you have not (easiest tier first).
- The All / Surf / Bhop filter now changes times, first places, top tens and maps, and the records list, as the World of Surf switch does.

### P1100 TAS: start from the start zone
- `tas start <zone>` puts you standing at a start or stage zone's own start point (where `!r` puts you) and pauses TAS. `cmd zone_dests` lists the zones and their numbers.
- TAS steps and `tas back` work in the start box, even back across the start, by replaying your inputs from the start point.
- If something in the start box moved since (a door or another player), TAS says DIVERGED and ends the session instead of putting you somewhere new.
- A run you start under TAS no longer gets the random start nudge: TAS lines are planned to the unit. TAS runs still never count on the normal boards.

### P1105 Completed maps stand out
- A map you have finished now fills its whole card with green from the right, with a large Complete! scrolling across it behind the Play button.

### P1104 Stats: every tier, and World of Surf or Everything
- The Stats page shows every tier again (it only drew Tier 1); click one for its maps.
- World of Surf and Everything is now a switch, on the home page and the Stats page, and the times, first places, top tens and maps follow it.
- Click times, first places or top tens on the Stats page for that list of your records.

### P1103 Clearer native run-check explanations
- The native run-check console distinguishes unsupported recordings from incomplete ones. Eligible runs and board decisions are unchanged.

### P1102 Map lists come only from the game's own files
- The map tiers, map list and the list of maps that use other games' content are read only from the game's own folder, never from something a server sent.

### P1101 Online consent stays yours
- A server can no longer change whether you have agreed to play online.

### P1099 New maps between updates
- The map list fetches the latest tiers and the list of maps that use other games' content once a session, so maps added since the last update show their tier and load with their textures.
- A map whose picture is not in this update's thumbnails shows it from the server instead of a blank tile.

### P1098 Map tiers and pictures stay current
- The tiers, thumbnails and extra game content each release ships for its maps are refreshed from Momentum every six hours instead of by hand, so new maps arrive with their tier and picture.

### P1097 TAS: search for the soonest next stage
- Add `time` to `tas optimize` (with or without `board` and `flick`) to search for the turn that reaches the next stage soonest instead of the one with the most exit speed.
- If no try reaches the next stage within the ticks given, the fastest try wins. Checkpoints are not counted.
- The console shows each try's result: the tick it reached the next stage, or that it did not.
- A try that reaches the end zone finishes the run there and ends the search; save a project first if the end is in reach.

### P1096 Prop lighting on maps with out-of-date bakes
- Props whose baked lighting was made for a different model (the map changed after it was lit) now light like unbaked props, as Source does. surf_pantheon's columns are even marble again instead of striped brown, grey and black.

### P1094 Downloading a map during a local game
- Pressing Download while you are playing a map yourself no longer fails: the map downloads as soon as you leave that game, and the row says "after this game".

### P1092 TAS: best boarding angle and launch flick
- `tas optimize <ticks> <left|right> board` also finds the best heading to start the turn from (up to 30 degrees either way), for the angle you board a ramp at.
- `flick [ticks]` adds a faster turn over the last ticks (4 unless you give 1..32), for the launch off the end of a ramp. Use both with `board flick`.
- Each search starts with the plain best turn, so its result is never slower than that; the console says which angle and flick it chose.

### P1090 TAS: sign the inputs you supplied
- Each saved TAS project revision now records which ticks it changed from the revision it came from. A first save covers all of its ticks; a save that changes nothing records none.
- Sign in the TAS panel signs the current revision with your key, saying you supplied those ticks. It signs only on a real click, in a game you host, for a revision you saved; the panel shows the revision, its parent and the ticks first.
- Every revision you save or load is kept under its fingerprint, so a later save never loses an earlier one or its signature.
- Servers you visit can no longer read, list or change your TAS projects.

### P1089 TAS projects get a fingerprint
- Every saved TAS project revision now records a fingerprint of its inputs, and names the revision it came from by that fingerprint. `tas project hash <name>` shows it. This is the groundwork for sharing projects with credit.
- Project files must be exactly as the game wrote them: a hand-edited file is refused, and loading one that was changed after saving warns you.
- A save that could not be read back no longer replaces your last revision.

### P1088 TAS: find the best turn for exit speed
- Best turn left/right in the TAS panel, or `tas optimize <ticks> <left|right>`, tries turn rates from your current view while strafing that way and keeps the one with the most speed at the end.
- TAS plays the winning turn and stays paused there.
- Every try is the real movement on the real map, and the console lists each rate and speed. The search covers one constant turn, not every possible line.

### P1087 TAS: compare against the line you just changed
- When TAS steps back, or the timeline recalculates or undoes, the part of your line it replaced stays on screen as a pink line. A pink ghost runs it on your clock.
- The TAS panel shows how far ahead or behind you are at the same place on that line, and your speed difference there.
- Stepping back in TAS no longer erases your whole trail; it keeps the line up to the tick you went back to.

### P1086 Servers can no longer run commands in your game
- Servers you join can no longer use several old engine paths to run local console commands or change files your game loads at startup.
- Test input, config files, demo names, saved games and a few settings now ignore those server requests. Normal play is unchanged.

### P1085 Bhop blocks time your stay in ticks
- A bhop block now sends you back after a fixed number of ticks on it (7 at 66 tick, 10 at 100 tick) instead of after a tenth of a second of server time, which could vary by a tick with the network.
- Reloading a TAS project on a bhop map now reproduces it exactly. Pausing TAS while standing on a block no longer sends you back on your next step.

### P1084 Stats page in the main menu
- Click Your stats on the Lobbies page to open the same Stats page as the in-game player panel: your figures, tier bars, best runs and player search.
- Stats now show World of Surf by default (the switch was labelled WOS), on the Lobbies page and in the player panel.
- Lobby cards draw their text at the font's own sizes, so the player count is sharp.

### P1083 Ranked runs use the standard move settings
- Move inputs are capped at the standard 450: a raised cl_forwardspeed or cl_sidespeed, or a gamepad stick on top of a held key, no longer goes past it. A run whose moves still exceed it is not ranked, and the finish says why.
- cl_netfps now stays matched to the map's tick for the whole map, not only when it loads.

### P1082 Save TAS projects and reopen them later
- The TAS timeline can save your line as a project and reload it after leaving the map or restarting: it replays every input from a TAS save and says whether it reproduced exactly.
- Name checkpoints, load up to one, fork a project under a new name and compare two projects tick by tick. Local games only for now.
- A TAS run's last stage on the results banner now always reads TAS, never segmented or a clean time.

### P1081 Publish zones from our lobbies, and reload now
- Zone admins can publish their saved zones while on one of our lobbies, not only from a game they host. zone_edit publish opens the same confirmation; a click on its button still sends.
- A new Reload now button warns the players on that map, then reloads its lobbies with the new zones once their runs are verified, usually within 10 minutes. Publish alone still waits until the map is quiet.

### P1080 Sort maps by completion
- The Maps list has a Sort row: tier order, incomplete first or completed first, using your clean main finishes (WOS, Momentum Mod or KSF). Tier order is kept within each group. Without a linked account online it says so and keeps tier order.

### P1079 Keep inherited map effects unranked across run styles
- Inherited effects that make a run unranked now stay practice in segmented and shadow styles too. Normal current-attempt segmented play and map effects keep working.

### P1078 Tiers for newer maps
- surf_midnight and six other maps added since 24 Oct now show their MOM and KSF tiers in game, not just in the map list. Four Momentum maps that left Beta now show their ranked tier instead of a suggestion.

### P1077 Edit retained TAS ticks in a timeline
- The TAS workshop has a tick-table tab: select a retained tick or range, change movement, aim or a held button, then recalculate its suffix. Refresh after completion to inspect the result.
- Undo and redo keep up to eight local input edits at the paused head. New execution or expired exact history can detach revisions; this is not a saved project or a rewind of shared world time.

### P1076 Preserve attempt ownership through recurring timer callbacks
- Recurring timers retain attempt ownership without stopping map effects. Affected clean runs become practice; normal current/world timers and existing segmented/shadow tier rules are unchanged.

### P1075 Complete the server update before finish re-arming
- Finish and reset re-arming now waits for the current server update to complete; normal map effects keep working.

### P1074 Choose upcoming TAS inputs in a workshop
- tas menu opens a next-input window with manual aim, movement, jump/duck/walk and single or multi-tick advance. Auto left/right chooses a fresh observed-air strafe yaw each tick; this is not route search.
- Paused physical mouse look is locked by default. Toggle Mouse free to aim deliberately, then Use view; authored steps and rewind still update the camera. Shared world time keeps running and attempts remain TAS practice.
- Button completion and return effects from an earlier attempt now make the affected attempt practice without interrupting play. Current-attempt and world-origin button effects keep working.
- Receiving a queued effect from an earlier attempt marks the affected attempt as practice without stopping play. Current-attempt and world-origin effects keep working.
- Lobby cards group larger lobby titles, map names and player counts together, with a compact layout for small windows.
- Lobby photos can load at higher resolution as soon as the directory arrives, without waiting for the map catalogue. Offline and unavailable photos keep the local thumbnail fallback.
- Corrupted recording generation or rewind indices now refuse safely rather than rejoining the wrong recording branch. Valid warm rewinds and confirmed cold copies keep working.
- Menus keep their rounded glass in hosted and online games, with a clearer full border and less see-through panels.
- Fixed panel-sized square backdrops and uneven darkening when switching menu tabs over a loaded map.
- Loading a save with malformed recording confirmation now stops safely instead of treating it as an old save. Valid older saves and matching in-memory rewinds keep working.
- TAS replay and tick rewind preserve camera pitch; replay also follows the mover's view through rotated portals.
- TAS refuses unsupported REC14 streamed edits and tick rewind without cancelling or cutting the active recording.
### P1065 Edit TAS tick inputs and recalculate the affected line
- Paused TAS can list captured tick inputs and edit movement, aim, jump, duck or walk for a selected range. Replay recalculates the affected tail and stays paused; unavailable exact history refuses.
- Replays use stored inputs rather than live movement. Play/off cancels safely, shared world time still runs, and the attempt keeps its TAS label. This is a bounded console editor, not a saved-project or timeline GUI.

## 0.1.32 2026-10-27

### P1064 Windows-output visuals work while game audio is muted
- The menu's sound-reactive backdrop can hear desktop playback even when the game is muted in Windows. Your game volume, mute and visualization opt-in stay unchanged.

### P1062 Glass scenes, visible filters and larger map cards
- Menu windows now use tinted glass over the MilkDrop backdrop, with section-specific scenes and crisp text. Milk-off and in-game menus keep their readable fallback.
- Map filters stay visible without a collapse button. Larger cards add a green completion fade and separate your WOS/overall times from WOS/overall world records (main track, clean style); unavailable records stay unknown.
- Map cards request visible records in one small cached batch. Play/Download actions are larger, Quit calls its input guard correctly, and Music is no longer offered in Settings.

### P1061 Rewind TAS one movement tick at a time
- While paused, tas back restores the previous retained movement tick; tas back N goes back N ticks and stays paused. Repeating the same forward input follows the restored movement state.
- The paused TAS rewind cursor now moves in individual ticks, not line samples. Unavailable checkpoints refuse instead of choosing a nearby point; shared world time is not rewound.

### P1060 Lobby history survives downtime
- Lobbies keep their rotation history across long heartbeat gaps; inactive lobbies still disappear from the live list.

### P1059 Shared browser panels and simple navigation
- Friends and lobby chat stay in place while Lobbies, Maps, Story and Event swap the main panel. Switching pages keeps your unsent chat text.
- Navigation returns to bold white text without a backdrop. The compact update note stays at the screen's top-left.
- Maps fills the remaining panel, with large thumbnails and larger native-size names. The old filter, thumbnail-size and Friends switches are removed.
- The Music menu and automatic menu-track playback are removed; Windows-output visualization and its existing local source preference remain.

### P1058 Crisp Home text and a floating header
- Home text uses the font's native baked sizes, with separated stat-card label/value rows.
- The rounded navigation bar floats above the main panels with a clear gap and matching width.
- Development menus keep signed release checks but no longer replace themselves automatically on startup. F2 offers an explicit switch to the published release; release builds retain automatic installation.

### P1057 More room for lobbies and Friends
- Lobbies get most of Home, with substantially larger map thumbnails; stats stay visible in a compact panel below.
- Friends gets more vertical space than chat. Compact chat keeps its message field and status rows separate.

### P1056 Home fits your lobbies and stats
- All lobbies fit in a responsive grid without scrolling. Every tier, summary card and Story/Event progress card stays visible below it.
- The Home layout adapts down to 800x600, with compact lobby cards and tier bars. Version/update information lives in the tab strip instead of overlapping Friends.
- Completion now loads values for every tier; unavailable values stay clearly marked, and an ordinary refresh no longer blanks previously loaded stats.

### P1055 Pause TAS practice and advance one tick at a time
- tas pause freezes your movement; tas step advances one movement tick, or tas step N queues up to 128. tas play resumes your chosen practice speed and tas off returns to normal speed without clearing TAS history.
- Stepping is server-authoritative on the normal Source movement clock. Other players and the shared world keep running; timeline editing, optimization and public TAS boards are still to come.

### P1054 Your home, your records and your completion
- Home puts lobbies above your WOS stats and progress, with friends and public lobby or friend-only chat on the right. Tabs give Maps its own space, alongside Story, Event Mode and Settings.
- Jump to me finds your record in the selected leaderboard without changing its filters. Boards load smaller first pages and keep paging as you scroll.
- Tier completion has WOS and Everything views in-game and on the website. Everything includes Momentum and KSF; both views use the same map totals.

### P1052 Explicit TAS practice sessions
- tas on and tas speed 0.1..1 start assisted practice using the existing slow motion. tas off restores normal speed, not the run's eligibility. TAS saves retain their label; frame advance, editing and public TAS boards are still to come.
- TAS saves stay local for now: sharing and automatic mirroring wait for a format that preserves their history.

## 0.1.31 2026-10-26

### P1051 goto_start goes to the start
- goto_start (M) now takes you to the start of the map, or of the bonus you are on, from anywhere: also after a run was voided or finished, where it often only restarted the stage you were in. Reset (R) still restarts your stage.

### P1050 Fail floors send you back
- On bhop_tealbox, bhop_whitebox, bhop_greenbox, bhop_greybox and bhop_peribox, falling onto a fail floor now sends you back to your last checkpoint instead of leaving you stuck there. Each player's checkpoint is their own on a lobby.

### P1049 Rotated conveyors and see-through pieces match Momentum
- Conveyor belts and walk-through decorations that a mapper turned in the editor now sit and face the way Momentum shows them (deathrun_forest's conveyors, bhop_shust_extension's markers).

### P1048 Rotated wall pieces stay where the mapper put them
- Wall pieces the mapper turned in the editor now sit where Momentum draws them, instead of being drawn and solid somewhere else: bhop_goldsrc2's sparking panel is back on its wall.

### P1047 Much faster maps full of props
- Animated and moveable map props are now drawn by the graphics card and in batches: surf_hourglass's main view went from about 80 to about 400 frames a second here, and other prop-heavy maps gain too.

### P1046 Sparks spark as often as in Momentum
- Sparking map pieces now throw a shower of sparks up to ten times a second, as in Momentum, instead of a few sparks every three seconds.

### P1045 Water and glass with a missing ripple texture stay clear
- Water and glass whose ripple texture is not installed now draw clear instead of smearing the edge of the screen into streaks. surf_hourglass's water also loads its ripples from Team Fortress 2 when you have it installed.

### P1044 Smoke stacks look like Momentum's
- Smoke rising from map smoke stacks now uses each stack's own size, colour, speed and lifetime: bhop_orgrimmar's braziers send up grey smoke columns instead of short white dots.

### P1043 bhop_goldsrc2 crates removed for now
- bhop_goldsrc2's 39 physics crates are removed until physics is supported; without it they hung frozen in mid-air instead of falling and being pushed around.

### P1041 Invisible map props stay invisible
- Props the mapper made invisible or see-through now draw that way, and fade in when the map says so: surf_hourglass's vortex no longer sits on a white square.

### P1040 No prediction warnings from noclip speed changes
- Changing noclip speed with Shift and the mouse wheel while flying no longer prints prediction error lines in the console.

### P1039 Untextured map pieces draw in their colour
- Map pieces with no texture of their own now draw in their flat colour, as in Momentum, instead of a missing-texture checkerboard: surf_bossfight's window frame, lamp and radiator.

### P1038 Grass and other detail sprites
- Maps with grass, flowers and other small detail sprites (bhop_monster_jam, bhop_blacktop, surf_castle and 63 more) now draw them, fading out with distance as in Momentum. hl2_detail 0 turns them off.

### P1037 Maps remember what you did
- Triggers that check what you have done on the map now work as in Momentum: bhop_tealbox no longer holds you on the start pad, and bhop_2shiny2shuckle's stage-2 door stays shut until you have found the flint and iron.

### P1035 Animated signs run at their own speed
- Animated signs and sprites now play at the speed the mapper set, as in Momentum: bhop_goldsrc2's exit signs flicker at 40 frames a second instead of 10. A sprite set to speed 0 holds still.

### P1034 Exit signs, smoke and screens animate
- Sprites made of several frames (exit signs, smoke puffs, sparks, screens) now cycle through them instead of showing only the first frame.

### P1033 Fading map pieces use the mapper's distance
- Map pieces that appear as you get closer (bhop_ceaseless's lattice) now fade in at the distance the mapper set, as in Momentum, instead of all at 2000 units.

### P1030 Glowing signs stay behind walls
- Glowing signs and sprites (bhop_goldsrc2's exit signs) no longer show through the walls in front of them. Light glows and flares still shine through, as in Momentum.

### P1029 Noclip speed on the mouse wheel
- While noclipping, hold Shift and turn the mouse wheel to make noclip faster or slower, in small steps from a quarter of the normal speed to 16 times it.

### P1028 Particle switches work
- bhop_ceaseless's particle switch at the start, and any button or trigger that starts or stops a particle effect, now turns the map's particle effects off and on again. Effects that start switched off wait for their start.

### P1027 Tilted models face the right way
- Models a map tilts forward or back (bhop_ceaseless's hanging spider) now tilt the way they do in Momentum; they were tipped the other way. Only the drawing changed: you collide with them as before.

### P1026 No error for a missing optional sound
- A map sound that is not packed anywhere (bhop_ceaseless's booster sound) no longer prints download errors when you join. Files the game needs still report a failed download.

### P1025 Boost pads match Momentum and stay smooth
- Pads that launch you as you leave or jump off them (bhop_ceaseless) now fire on that tick, as in Momentum, push exactly their set amount and are predicted, so no snap back. A lag spike while standing on one no longer launches you.

### P1023 Smooth reflections on curved walls
- Curved walls built from flat faces (bhop_ceaseless's tunnel) now reflect smoothly, the way the mapper smoothed them, instead of facet by facet.

### P1022 Faster map changes on servers
- Changing maps on a server no longer re-reads every installed game's files twice: bhop_ceaseless to surf_666 took 21 s on the test PC and now takes 11.5 s, about 4.5 s of it the server's own load. scr_loadtimes 5 shows where a load's time goes.

### P1021 Save menu on servers
- On a server, going to the next or previous save right after joining now walks through your saves instead of bouncing between the two either side of the newest one, which both showed the same number.

### P1020 Screen-space water
- New water setting, hl2_water 5: water refracts and reflects from what is already on screen instead of drawing the scene twice more, about halving the frame time near water on bhop_ceaseless. Reflections show only what is on screen.

### P1019 Calmer water from far away
- Source water seen from a distance no longer breaks into speckle and thin horizontal lines; its ripple distortion stays the size it is up close, as in Momentum. hl2_waterrefractfalloff 0 restores the old look.

### P1018 Faster water
- Water in a map's distant 3D sky no longer renders its own reflection and refraction every frame; it uses the ones the main view already made, as in Source. On bhop_ceaseless this cut about a quarter of the frame time where that sky is in view.
- Water reflections and refractions are rendered no larger than 1024 pixels a side, as in Source, which saves time at high render scales (r_watertargetsize).

### P1017 Particles that circle
- Map particles that circle around their emitter now do: bhop_ceaseless's butterflies, the tunnel spiral, the gate lights and the stars all turn as in Momentum.

### P1016 Clearer ent_info
- ent_info no longer calls map particle systems and colour correction "unimplemented": it says the client draws or applies them.

### P1015 No download errors when a map loads
- Loading a Source map no longer tries to download the map itself from a garbled address ("play.proto.bar/play.proto.bar/...") and then report that the server refused it.

### P1014 Window panes fade in
- Fading window panes in Source maps now fade instead of staying solid and vanishing at the last moment, and what is behind them (particles included) shows through while they fade.

### P1013 Source underwater overlays
- Under Source water you now see that water's own underwater overlay, a moving ripple over the whole view. Water that has none in Source shows no warp, as in Momentum, and keeps its underwater fog.

### P1012 Particles: colours, spread and the missing ones
- Map particles change colour over their life as the map's author set them.
- Particles that never appeared on bhop_ceaseless (the start room's floating circles, the butterflies' dots, the tunnel's spiral) are drawn.
- Particles spread over the whole area the map gives them instead of bunching into a square or a column, and the boost strips' particles cover the strips.
- Particles start upright where the map gives them no rotation, so falling drops fall straight instead of at random angles.
- Particle rings the map limits to half a circle are drawn as half rings.
- A particle that starts part-way through its colour change no longer ends past the colour it was fading to.
- surf_boreas' end-room glow is a compact glow again instead of a bright dome.

### P1011 The timer names your style
- The timer says sideways, half-sideways or backwards while you run one of those styles, read from how you face against your travel and which keys you use. Forward says nothing. Runs are not filed by style yet.

### P1010 Main-menu chat in a game
- On a linked lobby, the main menu's public chat shows in your game's chat as [everyone], with records and bests as board lines.
- The team-chat key opens a line to everyone, and TAB in a chat line switches between your lobby and everyone.
- The menu's Lobby chat screen works in a game too (ESC); in a lobby you send from the game's chat.

### P1009 Friends in private games
- In a private game, or a lobby without Friends, the menu's Friends list loads again (ESC, then Play): the game would not vouch for you while you were in any game.
- In a private game the profile's Friends tab points you there.

### P1008 Armed
- The timer says armed when leaving the start box will start a clean run, or not armed and what to do.
- Bunnyhopping in a start box, or noclipping there with cheats then off, re-arms once you stand still on the box's floor below 290 u/s, instead of needing !r.

### P1007 Rewind energy as you saw it
- While rewinding, the energy readout is what your speedometer showed at that moment, not energy from the start of the line ("e line").

### P1006 Rewind the whole run
- On staged maps the rewind reaches back past stage starts to the start of the run; the line still shows only the current stage until you rewind.
- Rewinding more than two minutes back now works, to the nearest second, up to about half an hour back.
- The 3 second countdown after a rewind resume is back if your settings had kept the 0 an update set for a day.

### P1005 Results card leaves F1 alone
- F1 on the results card no longer takes the mouse; there is nothing to click on it.

### P1004 Resume
- While a resumed run counts in, the view is locked: the mouse no longer moves it for a frame before it snaps back.
- F2 no longer answers the resume offer and the card drops its hint; 1, 2 and !resume still work.
- If the leaderboard is still checking your game, the card says it is loading the resume and goes ahead when it can, instead of sending you to chat to retry.
- If the server refuses a resume, the card says why. The countdown no longer says VIEW LOCKED.

### P1003 Authored no-fog materials
- Materials a map marks as no-fog now stay clear on the plain GL rendering path too, including Source wireframe surfaces. An explicit no-fog value of 0 keeps ordinary fog.

### P1002 bhop_ceaseless's speed tunnel, func_lod and particles
- Momentum's AddSpeed, AddHorizontalSpeed and AddVerticalSpeed map inputs work: bhop_ceaseless's speed tunnel under the start pushes you along the way you are moving.
- A trigger whose filter shares its name with a name the map gives players no longer lets everyone through once someone carrying that name touched it first.
- func_lod brushes the map marks not solid are walk-through, as in Momentum, and all func_lod detail fades out at its authored distance.
- bhop_ceaseless's particle effects (boosters, stars, rain, smoke) are drawn.

### P1001 Ramp touchdown numbers from just before the ramp
- The run line's touchdown label on a ramp now shows your speed and energy on the tick before you touched the ramp, not after the ramp's clip took its share.

### P1000 Profiles in private games
- Player profiles now load in a private game: yours from the account this install last linked, and a friend's from the account their game reports, marked as their own claim.

### P999 Smoother launch
- The map list loads about twice as fast when the game starts and when the map catalogue updates: checking maps you do not have no longer searches every folder, and the wrong-build check finishes over the next frames.

### P998 No stutter when a stage completes
- Finishing a stage no longer copies your whole run so far to cut that stage's recording; it is cut from memory. Cleaning up old stage recordings waits a moment, and your client finds the stage in its own recording at once.

### P996 Records and bests in the main menu chat
- The main menu's public chat now shows when someone sets a world record, a personal best or a first finish on the online board, with the time and place.

### P994 No "F1 cursor" on the results card
- The card shown when you finish a map, bonus or stage no longer shows the F1 cursor hint.

### P993 Loading a save in a start zone stays clean
- Loading a save you made standing in a map, bonus or stage start zone no longer marks the run segmented: it arms a clean attempt, as walking in does. A save made while moving still keeps its tag.

### P992 Friends list in a lobby
- The Play screen's Friends list now loads in an online lobby even when the lobby cannot relay it, by asking the Friends service directly.

### P991 Play screen: one Esc, profile times, map links
- In a game, one Esc on the Play screen returns you to the game; on a small window the first Esc still hides the Friends drawer.
- A friend's profile now lists up to 12 times with clear text, where it showed one.
- A friend's map is underlined when you point at it, to show it can be clicked.

### P990 bhop_ceaseless's colours, roof, gates, rain and water
- Cubemaps saved without the old sphere map load: bhop_ceaseless's glowing cracks, gradients, chains, dragon, tree, butterflies and roof crystals have their colour back.
- Unlit signs and labels with a reflection draw it (the start room's text, logos and buttons).
- A model that pokes through a sky brush is no longer cut off by the sky (the faceted roof over the start).
- Props marked never-fade by newer compilers are drawn again (the bridge gates).
- Scrolling rain is small and moving, flowing water animates, the sword floor's ripples move, and the start room's glass floor shimmers gently instead of warping hard.

### P986 New crosshair 3
- Crosshair 3 is now a 42 pixel Counter-Strike: Source style sight, centred on the same pixel as before.

### P997 Reuse the oldest-idle lobby first
- New-map requests now reuse the least-recently-used empty lobby. Simultaneous requests reserve separate vacancies or share the same map without stealing each other's assignment.
- Occupied lobbies are never moved; no server is stopped or player data removed.

### P995 Keep the SDL3 file picker local
- SDL3 file-picker requests now require a trusted local command, matching the DBus picker restriction.

### P989 Clean up failed desktop file-picker requests
- Failed DBus file-picker requests now stop cleanly, validate replies, and release their resources instead of keeping a disconnected request alive.

### P988 Keep the DBus file picker local
- The DBus file picker now accepts only trusted local commands; remote game commands cannot open it.

### P987 Refuse download cache names that do not fit
- Download cache names that are too long are now refused cleanly instead of being used by the package manager.

### P985 Keep retry in place if its saved point cannot be confirmed
- Retry now checks its save point and movement copy before restarting. If either cannot be confirmed, it explains why and keeps the current run in place.

### P984 Momentum zones on more CS:S builds
- 31 CS:S and KSF builds that timed only a main start and end from their own triggers (surf_axiom_css among them) now use the Momentum map's zones, with its stages and bonuses.

### P983 Faster map downloads in the game
- The game reads everything that has arrived each frame instead of one piece, so a map download runs at your connection's speed (about 3x faster at 100 fps).

### P981 Smaller, faster map downloads
- Maps that are not already compressed are now sent gzipped from the map storage (40-60% smaller), and the game unpacks them; this works on every released version.
- Map downloads no longer fall back to the slow 1 MB/s copy on the lobby server when several requests arrive at once.

### P982 r_mirrorworld
- r_mirrorworld 1 mirrors the world left to right and flips mouse, keyboard and gamepad turning and strafing to match, so you play the mirrored map normally. It is the same switch as leftisright.
- Names and markers drawn over the world (ent_view, player names, run lines) now follow the mirrored view.

### P980 Momentum builds for Story and demos
- Story and Event levels always load the level's own (Momentum) build, even where you picked the CS:S build in the map list, so the medal counts.
- A Momentum demo now plays on the CS:S build of its map (the way KSF demos play on Momentum builds), with a note that the geometry may differ.

### P979 bindlist in key order, with a filter
- bindlist lists F2 before F10 (numbers in key names sort as numbers), and bindlist <text> shows only the keys or commands containing that text.

### P978 Reload account settings without overwriting them
- Reload restores your account setup without saving stale local choices over it. New edits made while loading stay local; use Save when you deliberately want to replace the account setup.

### P977 Movement settings under sv_cheats 1 take effect at once
- With sv_cheats 1, sv_accelerate, sv_airaccelerate, sv_friction and sv_stopspeed now change how you move straight away, like sv_gravity always did; before they only applied from the next map.
- sv_cheats 0 lists each movement setting it puts back, with the value it had and the value it returns to.

### P976 KSF tiers for CS:S builds and new KSF maps
- The in-game map info box and scoreboard now show the KSF tier for CS:S builds of Momentum maps, for KSF maps added since the last list, and for Momentum maps KSF rates under another name. Four maps KSF re-tiered show their new tier.

### P975 Friends in a private game
- In a private local game the friends list now loads on the menu Play screen, as it does at the main menu; the in-game Friends tab points you there.

### P974 Stage toast switch and a search you can double-click
- hud_edit: the Splits pane has a Stage toast switch for the pill that shows each stage you finish, top left.
- The map search no longer empties itself on the first click after you play a map: the old search is selected instead, so typing replaces it and a double-click selects it all.

### P973 Resume offers that work
- A paused run the game cannot resume (a practice, stage or bonus run) no longer shows the resume box; chat says it is kept and that !discard drops it.
- When a resume is refused, the reason now shows in chat and the box comes back so you can press 1 again.
- The resume box uses the same left-hand card as the save menu.

### P972 Keep earned re-arming across retry
- Retry preserves a finish or reset's pending re-arm, so coming to rest afterward can clear the old hopped-start tag just as it would without retry. A genuine hopped start still needs its normal reset.

### P971 Keep retry in place when recording preparation fails
- Retry no longer restarts the map if its recording cannot be prepared. If that failure lost the current recording, the attempt is cancelled with an explanation; ordinary retry still works without recording.

### P970 Account-linked workshop and watched-player viewmodels
- Knife workshop settings can sync with your linked Steam account on updated lobbies. Save and Reload controls cover the full cosmetic setup; a late load will not overwrite newer local edits.
- First-person spectating shows the followed player's knife, hands, sleeves, finish, weapon FOV, shooting and inspect animation without replacing your own preferences. A disabled target viewmodel stays hidden.
- Matching updated native client, game code and account service are required. Installed game content is still needed; no game assets or inventory skins are downloaded or bundled.

### P969 Keep in-memory loads when a save copy fails
- Saves check the movement copy on disk and warn if it cannot be confirmed. The current recording remains available for a matching in-memory load instead of being cancelled by that disk failure.

### P968 Check the body before re-arming a hopped start
- Pending finish forgiveness checks carried speed and your current movement cap, and is not granted while frozen or rising. It can still re-arm after the start has settled.

### P967 Match Original and default-T knife textures
- Original and default-T knives now use their own installed Legacy texture instead of a same-named CSS texture. CSS weapons keep their existing materials; an updated native client is required.

### P966 Viewmodel lighting and save-load holds
- Skin and cloth pieces, including FBI Gray sleeves, now respond to local lighting. Neutral Preview glove styling is unchanged.
- Your viewmodel stays visible during save-load holds instead of disappearing until release.

### P965 Restore older saved progress safely
- Older saved states can restore their stage progress without an invalid zone lookup stopping the server. Matching stage-region preferences are preserved.

### P964 Keep stage tracking after retry
- Retrying a saved running attempt now reopens its current stage, including after reconnecting. Loading and retrying retain their existing clean/practice classification.

### P963 Main-menu lobby chat and direct messages
- Open lobby chat beside Play to talk in the shared main-menu room or select a mutual friend for a private conversation. Requires a linked account, online features and matching updated client/service.
- Messages are recent-only and expire after two minutes. Blocks apply, private messages are friend-only, and closing chat clears local drafts and held messages. DMs are not end-to-end encrypted.

### P962 Installed Legacy knife, glove and sleeve workshop
- The knife workshop lists installed Legacy knife shapes, hands/gloves and sleeves/watches, with paged selectors and a draggable shared-theme panel.
- Selecting Legacy content can mount the installed game for this session without changing saved mounts. Missing content keeps your selection; no game assets are downloaded or bundled.
- Legacy viewmodels default to 70-degree FOV without changing world or CSS weapon FOV. Bare arms use matte skin, and template gloves are labelled neutral local previews rather than inventory skins.

### P961 Main-menu Friends presence
- With online features enabled, mutual friends can see that your game is running at the main menu. Joining becomes available after you enter a lobby, not while you are at the menu.
- Healthy unchanged Friends polls keep the displayed presence current; unavailable updates still go stale. Background presence no longer consumes the interactive Friends request budget.

### P958 Saved-run check resilience
- Saved-run checks report damaged numeric data without interrupting checks of other recordings.

### P957 Legacy knife workshop
- Equip mounted CS:GO Legacy Butterfly or M9 knives with butterfly or m9, and play their inspect animation with inspect. Requires installed Legacy content and an updated client; CSS knife remains available with knife_css.
- Type knife_menu for a small local Original/Fade/Web/Marble workshop with pattern seed, scale, rotation, fade amount and wear. These are local cosmetic previews, not Steam inventory or exact CS paint kits.
- If Legacy content is not mounted, selection stays unchanged and the console explains the one-time trusted mount command. No Valve assets are downloaded or bundled.

### P955 Source weapon touch-ups
- Glock single fire no longer kicks the camera; three-round bursts retain their gentle kick.
- Scout secondary attack cycles two zoom levels and back out, with the mounted CSS scope graphic and zoom sound. Firing temporarily unscopes for the bolt, then restores your zoom.
- Saving/loading no longer re-equips your weapon, and noclip keeps it visible. Type drop to put it away.
- Unsilenced guns show a brief mounted CSS muzzle flash at the model's muzzle. Disable it with cl_weapon_muzzleflash 0 if preferred.
- Hard-landings use CSS's damage sounds rather than Half-Life 2's fall-pain sample.

### P954 Practice slow motion
- Type host_timescale 0.5 for half-speed practice, or choose 0.1 through 1. Movement and the timer slow together without changing the physics tick or other players.
- Restoring 1 changes speed, but this connection stays in practice until a new map or reconnect. Slow practice uses server-authoritative movement while active.

- Restore Epiphany's world instead of a black screen, while keeping its intended colour grading.
- Restore Phantasia's glass ramps in both CSS and Momentum versions instead of drawing a missing-texture checkerboard.
- Make `hl2_missing` distinguish unsupported shader classes from missing material files, including later-loaded props.
### P953 Trusted operator file tools
- Local file-output tools now reject untrusted command requests while retaining trusted operator use.

### P949 Boreas mountain
- Boreas no longer has the sky-colored cutout through the foreground mountain near Save 11. The correction is scoped to Boreas; other maps retain their own sky settings.

## 0.1.30 2026-10-23

### P948 Kvas tree crowns
- Kvas no longer cuts off the bonus 4 tree crowns at the sky brush. Per-map render settings now wait for the connected map to be ready, so they work online too; other maps retain the ordinary sky-depth setting.

### P947 Autumnal platform textures
- Autumnal now requests its optional CS:GO Source 1 assets when loading, fixing checkerboard platform tops when that content is installed. No extra game pack is mounted on every startup.

### P946 Glock shot kick
- Glock shots now also give a small, smooth cosmetic view kick, including each bullet of a burst; aim and movement stay unchanged.


### P943 Source weapon controls and varied footsteps
- Hold primary attack for repeated knife slashes; secondary attack stabs. Knife misses whoosh, while harmless player contacts can make an impact sound without damage or pushing.
- The USP starts unsilenced; secondary attack attaches or removes its silencer. Glock secondary switches between single fire and three-round bursts. Scout shots now include the authored bolt sound.
- Equip with `knife`, `usp`, `scout` or `glock`, as well as the existing give commands. USP/Scout shots have smooth, render-only upward camera kick and recovery; aim and movement remain unchanged.
- Footstep samples vary within the material's left/right set, and closely adjacent jump/contact cues merge instead of double-stepping. Default viewmodel FOV is now75; explicit preferences and bindings are preserved.

### P944 Personal Max Fog event
- Playing the Zoomathon Max Fog event now starts a dense personal fog attempt without changing anyone else's view. Type cmd maxfog 0 to restore normal map fog, or cmd maxfog status to inspect the mode.
- Whole-run tracking distinguishes staying in fog from switching it off or enabling it late. Existing gold credit is unchanged while the legacy-credit policy is pending.

### P941 Subtler weapons and authentic floor sounds
- Weapon bob and turning sway are one-fifth as strong by default. Idle animations keep looping, and spawning starts unarmed even if weapon models are enabled; select a weapon when you want one.
- Fix long material names on maps such as Axiom falling back to concrete. When CSS is mounted, its footstep samples take priority over Momentum's versions; quiet walking and crouching stay silent.

### P940 Source-style weapon motion and material footsteps
- Viewmodels rock as you move and gently trail your turns, without moving the camera or aim. The default viewmodel FOV is 70; existing personal FOV choices stay unchanged.
- Footsteps follow mounted material surface properties and left/right sound variants, with safe fallbacks for older maps or missing content. Quiet walking and crouching remain silent.

### P939 Paste without an extra question
- Paste into text fields with Ctrl+V or Shift+Insert without an extra confirmation dialog. As with normal paste, only paste text you intend to share with the connected game's UI.

### P938 Lighter recording checks
- Less repeated work during recording and replay checks; movement and saved-run formats are unchanged.

### P937 Optional movement instrument
- `cl_surf_tone 1` adds a sine tone whose pitch follows your height; `cl_surf_drums 1` adds a kick on A and a snare on D. Both are off by default and typing in chat does not play the drums.
- `cl_surf_audio_volume` controls their shared volume (default 0.15); `motionaudio_info recenter` resets the reference height. Existing movement sounds and music are unchanged.

### P936 Clearer Steam portraits
- Profiles, Friends and boards use 64x64 Steam pictures instead of 32x32, retaining four times as many source pixels. Existing cached pictures and older clients are left intact.
- Browser profile previews can load the picture using the same public profile identity as the website.

### P935 Quieter walking, Source weapon feel and faster saved runs
- Footsteps are silent at 135 u/s or less and while crouched, with speed-scaled volume and reliable hop cues. Foot sounds and weapon models now default off; selecting a supported weapon turns its model on.
- Add mounted weapon draw sounds, better idle/shot presentation, independent viewmodel FOV and natural give aliases. Existing map-target damage gates and no PvP stay unchanged.
- Hands no longer let sprites show through; weapon environment lighting samples your eye position. Large saved recordings load with buffered reads instead of pausing for byte-at-a-time disk reads.

### P934 Bound keys in the console
- Type `bindlist` to print your current bindings in alphabetical order, including modifier overrides and alternate bindmaps. Listing them never changes or executes a bind.

### P933 Friends and textbox selection
- Opening the map browser reveals Friends and asks for fresh presence. Friends use compact two-line cards; offline cards are faded and online map/stage or bonus text is green.
- Click a friend's name for an in-menu public profile preview, or their green location to ask to join their lobby.
- Double-click a textbox to select all its text. Normal clicks, dragging and slow separate clicks still work.

### P932 Watch KSF runs on linked Momentum maps
- KSF demos can play on linked Momentum map versions, including surf_chateau_fix recordings on surf_chateau. Original KSF files and downloaded recordings use the same configured links.
- Pause and seek while watching a linked recording. Changing maps ends playback, and unrelated maps are still refused.
- Linked recordings keep their real source-map name and imported/unverified status. Downloaded recordings can be watched again from cache without another download.

### P931 Bring a knife - or a Glock
- Add mounted CS:S knife, USP, Scout and Glock viewmodels with idle/fire animations and shot sounds. Select with surf_weapon knife, usp, scout or glock; existing save keys stay unchanged.
- Basic attacks use supported map buttons/breakables, retaining the server's shared-damage gates and no PvP. cl_viewweapon hides the model; cl_viewweapon_left swaps hands.

### P930 Updated Story and Events
- Story and Events now follow the updated 100-level lists, including the new maps and bonus challenges. Blank slots keep their level numbers; Momentum builds are used where the roster has one.
- Existing Story medal targets move with their map. New Story maps begin with a bronze finish; later trophy gates retain the existing 65%/70% progression policy.

### P929 Stable lobby names
- Servers are now Open Lobby #1 through Open Lobby #12. Their names no longer promise a map tier or mode that changes when someone chooses a different map.

### P927 Hear your feet and the water
- Add local footsteps, landing impacts, water entry/exit and swimming sounds using your mounted CS:S content. Walking sounds follow body travel, not camera movement; cl_game_sfx controls their volume.

### P926 Rotated teleports turn you at the right place
- Fix rotated map triggers predicting a teleport before the server reaches it, including surf_me save 9. The map's intended view turn now happens with the actual teleport rather than early during the fall.

### P924 Source conveyor belts carry you
- Static conveyor belts now carry you at their authored speed and direction, including parc_colore and classics stage 4. Stepping off keeps the belt momentum.
- Client prediction follows the belt movement instead of repeatedly correcting your position.

### P923 Keep recording attempts separate
- Starting or resuming a recording no longer carries another attempt's bookkeeping into the new recording. Existing recordings keep their original meaning.
- A selected recording that cannot be completed is preserved privately for recovery instead of discarded. This does not create a leaderboard result or change the existing retention period.

### P922 Local filters and a scoreboard that stays open
- Keep the direction and Segmented controls on Local, with a Practice filter. Existing local recordings stay Normal until directional recording is available; filters do not relabel runs.
- Right-click the scoreboard to keep it open after releasing Tab. Another right-click does not dismiss it; Esc closes it, even while searching.
- Story maps with nobody playing no longer show a zero-player label. Positive counts and unavailable-directory status remain distinct.

### P920 A proper paused-run choice
- A paused run now offers a left-side details panel with 1. Yes and 2. No. No means not now: it does not discard the paused run, and F2 still accepts it.
- Your view stays locked during the resume count-in, without banking a hidden look turn before GO.

### P919 Decorative sheets stay walk-through
- Fix a client/server collision mismatch on empty brush volumes, including the illusionary sheet at bhop_goldsrc2 save 2. Decorative illusionaries remain walk-through, without the client trying to stand on them.

### P918 Crisp missing textures
- The missing-texture checker now stays nearest-neighbour crisp without changing filtering on ordinary map textures.

### P917 Steady head clearance
- The ceiling-lowered camera no longer bobs with the mismatch between movement ticks and rendered frames while rising beneath a roof.

### P916 Duck your view under roofs and climb out of water
- Your view lowers when a ceiling would clip through the camera, on the ground or in the air. This does not crouch or shrink your collision box.
- At the water's surface, face a low ledge with room above it for a Source-style upward assist. Jump or swim up to reach the surface; the ledge assist itself needs neither button.

### P915 Disconnected time counts, and clean stages stay watchable
- Resuming a clean whole-main run now counts the entire time disconnected, including overnight, while preserving your physical movement history.
- Every newly completed clean stage attempt is kept under the normal recording limits, even if it is not a PB or you cancel the main run.
- On lobbies, Local can retrieve your newly saved stage recordings once your connection is identified. Choose an attempt to fetch and watch it; this does not award a record.
- Older saves retain their original timing. A slot whose clock cannot be resumed safely is left untouched rather than consumed; removing it remains your choice.

### P914 Your run clock keeps going while you watch
- Spectating another player or watching a recording no longer pauses your own run timer. Your body stays held; the time spent watching is added to the run and current stage without inventing movement.
- Repeated viewing and supported save, rewind and resume paths preserve the accumulated time. Older recordings keep their original timing rather than being reinterpreted.
- Runs containing viewing time are not natively verified yet; ordinary supported runs without it still can be. This patch does not add the time spent disconnected from a server.

### P913 Automatic resume is for clean whole-main runs
- Automatic resume accepts only clean whole-main runs, not practice, segmented, bonus or standalone-stage attempts. Older or ineligible stored slots are left untouched until you explicitly discard them.
- If a stored slot cannot prove that classification, resume will not consume it or move your body. Use !discard to remove it when you choose. Manual saves are unchanged.

### P912 Story tasks update as you finish
- Story and Events now show provisional task progress as soon as you finish, before the upload reply. All locally decidable matches update, not just the medal shown in the toast; confirmation or rejection reconciles the preview with the server.
- First-time players can see a temporary local preview before their profile resolves. It is scoped to their connection and expires if it cannot be confirmed; it never grants an official trophy or record.
- Story's Player/s count uses fresh live map occupancy. Missing or failed data shows unavailable, not a misleading zero. Story still begins loading before you first open it.
- Later Story chapters require progressively more trophies from earlier chapters. Some previously accessible later chapters may lock again until you meet the new requirement; earned progress is not removed.

### P911 Choose your reset point with startmark
- Use startmark or mom_start_mark_set while standing in a run's start box to choose its reset point and view angle. Marks are per player and map; startmark status and startmark clear inspect or remove them.
- Resets and fails use the mark only when returning to that run's first leg. Later legs keep their ordinary reset point, and a blocked mark falls back to the ordinary start.
- Returning to the start after noclip no longer leaves a genuinely fresh stage stuck in practice. Fresh retries keep their attempt/fail counters; this does not clear the enclosing run's practice state or change saved-attempt eligibility.
- Using reset outside the current stage's start now counts another attempt. Resetting inside the box does not inflate the counter, and the count stays updated after you move.
- Clean stage PB recordings survive cancellation of the main run. This is not a new archive of every non-PB stage attempt.

### P910 Open a recording while spectating
- You can open a recorded run while watching another player, then return to your own body and run display. Closing replay quickly no longer lets a delayed spectator update take the view back.
- If you have only just requested spectating and have not entered it yet, wait for entry before opening the recording. A missing recording leaves you spectating.
- This patch does not yet change how viewing time is charged to your run; that timer change is separate work.

### P909 Clearer leaderboard filters
- Loading a map starts the leaderboard on World of Surf records. Choosing a direction no longer switches you to KSF.
- Styles read Normal, Sideways, Half-Sideways and Backwards. Segmented is a separate switch that works with any direction; existing times are not reclassified, and empty categories stay empty.
- The menu board keeps the map name and filter summary readable and wraps its controls in small windows. The manual +100 KSF button is gone; the existing automatic import/download work remains.

### P908 Less of a hitch just after the title screen appears
- Loading the map catalogue no longer checks missing maps twice on current clients. On the test catalogue, the blocking load fell from about 2.07 seconds to 0.85 seconds, with the same maps and download offers. Story and map preloading stay on.

### P907 Choose the patch notes version in F2
- F2's Patch notes page has a version list. Pick a release to read just its changes, starting with your installed version when it is listed. Switching versions does not download the notes again.

## 0.1.29 2026-10-21

### P906 No snap-back on surf_reverie
- On maps whose zone-tool triggers use a Momentum filter this game does not support yet, such as surf_reverie, the game no longer predicts a teleport the server does not make, which pulled you back every frame.

### P905 Story is ready before you open it
- The story ladder and your trophies load while you are on the title screen, so the first STORY click shows them straight away. If the board does not answer, it is asked again after 5 seconds instead of a minute.
- surf_tendies (Tier 1) and surf_affliction (Tier 2) join the story, with placeholder challenges for now.

### P904 The results card in the new look
- The card after a finish now matches the rest of the new interface: rounded panel, the time large with a coloured gain or loss against your PB, and your previous PB under it.
- Local and world placement sit together in one box, and a run without a world rank says why in plain words.
- The splits table shows each split's gain or loss against your PB, and the card is only as tall as its rows and always fits the screen.
- The one-line stage toast (shown when stage banners are off) gets the same look.
- The middle mouse button no longer takes the card's cursor, so it does what it is bound to (paint, with the default binds); F1 still takes it.

### P903 No signed download addresses in the console
- Downloading a map's zones no longer prints the long signed address the download is redirected to.

### P902 A quieter title screen: updates, patch notes and terms move to F2
- The update corner and the patch notes panel are gone from the title screen. F2 holds them instead, one page each: Patch notes, Updates (turn on or off, restart, check again), Input journal and Terms.
- The title screen keeps your version and the latest one in the top right, as text, with a line pointing at F2, and says when an update is ready for a restart.

### P901 Type the ghost's time offset
- The Ghost settings in hud_edit have a new row, Offset in ms: click it, type any offset from -60000 to 60000 ms and press Enter (Esc leaves it as it was). The old quick steps are still there.

### P900 Layered glass draws in the right order
- Windows made of several glass layers, such as bhop_eazy's, no longer break into patches or swap tints when seen at an angle: panes are drawn back to front by which side of each pane you are on.
- Graphics menu: the Glass option "Dithered" now reads "Dithered if textured". Glass without a texture of its own, which is most glass (surf_boreas's ice included), has always drawn as Translucent in that mode.

### P899 The newest save is selected when you load a map
- Loading into a map now selects the last save you made in the save menu, not the first.

### P898 New-install defaults, binds and ALT+ENTER
- A new install starts in borderless fullscreen at 2x render scale, with sensitivity 0.5, fov 95 and no fps counter.
- Console messages no longer stack up over the game (con_notifylines 0). A value you set yourself is now kept between launches.
- The graphics menu has a Render scale setting (1x, 1.5x, 2x): 1x is the first step for a slower graphics card.
- New default binds: q/e and mouse 1/2 turn, mouse 3 paints, t rewinds, p opens the player panel (player_edit). Saved binds are kept.
- ALT+ENTER switches between windowed and borderless fullscreen in the game, the menus and the console, and with ALT still held, ENTER switches back. Your own ALT+ENTER bind wins; in_altenter 0 turns it off.
- Lex's HUD layout is the new default, for new installs and for every HUD setting you never changed; the ones you changed stay yours.
- The keyboard and mouse input displays stay together in the bottom right at every screen size. Dropping the mouse display where it sits beside the keys joins them again.

### P897 Quieter console in your own games
- Debug lines from map triggers, runs, saves and spectating no longer fill the console in your own games, such as surf_boreas's spinning symbols; developer 1 shows them again.

### P893 Zones and triggers checked every tick
- The server checks triggers and zones on every tick, as Source does: sending fewer, longer updates no longer lets you pass through a thin zone or fail plate.

### P892 Triggers from Momentum's zone tool
- 195 triggers that Momentum's zone tool adds to maps now exist on 47 maps: 133 teleports on 30 maps catch falls that went nowhere, and surf_greek's 25 checkpoint no-bhop zones work.
- Zone-tool checkpoint triggers with actions, such as surf_cannonball's, now carry them out (21 on 13 maps).
- Triggers behind a Momentum surface filter this game does not support yet stay off, so surf_reverie does not reset everyone.

### P896 Every KSF recording, three times faster
- KSF recordings now arrive three times faster, including those of older KSF times imported before recordings were linked.
- A broken file on KSF's side no longer holds up everyone else's recordings.

### P895 Refracting waterfalls and glass draw much faster
- Refracting world surfaces, such as surf_pantheon's waterfalls, share one copy of the screen instead of taking one each: at 2x render scale its start went from 124 to about 275 fps.

### P894 Graphics settings switch without a map reload
- Translucent, Overlays and Sprites in the graphics menu now take effect immediately.
- Bump maps, glass, animated textures, dithering, decals, light shafts and model lighting also switch live; the menu still marks the ones not confirmed in testing.

### P890 Map fixes: surf_network2008_final's falls go back to the start
- Maps can carry small fixes the way surf servers patch them. The first sends every fall on surf_network2008_final back to the start, stopped, instead of its round-based jail, and one player can no longer reset everyone else there.

### P886 Ropes draw their own textures
- Ropes and chains with a custom look (string lights, banners, chains, coloured cables) now draw their textures instead of a plain fallback.

### P882 Momentum's no-bhop, key-limit and slide zones
- Zones from Momentum maps that block jumping, crouching, bunny hopping or certain movement keys now work, such as bhop_offstyles' one-key sections and bhop_mom_training_beta.
- A no-bhop zone keeps you on the ground for 0.2 s after each landing.
- Slide zones (bhop_parallel, surf_rogue) make the floor slippery.
- run_momtriggers 0 turns them off with the other Momentum anti-bhop triggers.

### P881 Triggers made of see-through brushes fire
- Teleports and other triggers built from grate or see-through brushes now work: surf_network2008_final's falls no longer leave you standing on the floor under the map.

### P891 KSF stage recordings
- KSF recordings of single stages can be watched from the stage boards, starting with surf_kepler's.
- KSF recordings download again: one broken file on KSF's side had stopped them since 19 October.

### P889 Props from games you do not own collide
- Momentum's stand-in models for TF2, CS:S, CS:GO and Portal 2 load last when the game is not installed, so their props collide as in Momentum.
- surf_nuclear's spawn hub stands on the lobbies again; 16 more maps use these props.

### P888 Prop ramps with collision past their edges
- Large prop ramps no longer grow invisible slopes: 845 prop placements on 72 maps, surf_pantheon's floating ramp among them, collide where they are drawn.

### P887 HDR reflections at the right brightness
- Reflections from HDR cubemaps were drawn several times too dark: surf_demise's first ramp shows its red panels again, and 414 materials on 45 maps brighten.

### P885 Hops after the start zone are yours
- Stand in the start zone, jump out once, and the hops after it count: surf_tendies' booster hop no longer makes the run practice.
- Bunny hopping inside the start zone, or flying through it without stopping, still does.

### P884 Physics boxes that Source leaves passable
- Physics boxes a map marks not solid no longer stop you: 229 on 30 maps, among them surf_lovetunnel's butterfly axles.

### P883 vid_restart and ent_view crashes
- Restarting the renderer in a map (vid_restart, or changing the video mode, fullscreen or window) no longer crashes the game.
- The entity viewer (ent_view) no longer crashes the game after such a restart.

### P876 Patch notes on the site and in the game
- The download page lists what changed in each update down its right-hand side
- The title screen shows what's new when an update is ready, and once after it installs
- Scroll the list with the mouse wheel or drag its bar; Patch notes in the corner opens it again

### P875 Right water textures; animated Momentum textures
- Loose files in a Source game's folder, such as a CS:S mapping pack, no longer override packed game content.
- surf_garden's water now uses the proper HL2 water texture instead of a mapping pack's static one.
- Momentum's own multi-frame textures (VTF 7.6) now load instead of failing, such as animated screens.
- fs_sourceloose 0 restores the old file order.

### P874 Sun glow and ropes
- Maps with an env_sun (247 of them) now draw the sun's glow over the sky, hidden when something blocks it.
- Ropes and cables (181 maps) are drawn as hanging curves between their points; they do not sway or collide.
- Turn either off with Sun or Ropes in the Graphics menu.

### P873 Soundscape triggers
- Maps that switch ambient sound as you walk into an area (trigger_soundscape), or reuse a soundscape elsewhere, now play it there.

### P872 r_frametime shows the last second
- The r_frametime headline is now the last second's fps, matching show_fps; the 30-second average follows it.

### P871 Panel redraw rate
- New Panel redraw setting in hud_edit's Display Info: frame, 240/s, 144/s, 120/s, 60/s or tick.
- The strafe trainer, net, boarding and key hint panels redraw at that rate and are pasted in between.
- With every panel on, this cut the HUD's cost by over a third at 144/s. The default (every frame) is unchanged.
- OpenGL only; other renderers and older game versions draw every frame.

### P870 Map text, hints, fades and shakes
- Map text from game_text, such as stage names and credits, now appears, typed out and faded as in Source.
- Map hints show in a panel, and map screen fades and camera shakes now play.
- Turn them off with Map messages and Map screen effects in hud_edit's Display Info (hud_mapmsg, hud_mapfx).

### P869 Momentum bhop triggers
- Momentum's bhop section triggers now work: onehop, multihop, progress, teleport_progress, reversespeed, userinput and trigger_catapult.
- Landing twice on a onehop, or staying too long on a multihop, sends you back to your last progress point.
- Affects maps such as bhop_mom_training_beta, surf_mom_training, bhop_floodwaters and bhop_lego2.

### P868 Faster water reflections
- Water reflections now show the 2D skybox instead of the 3D sky, and skip entities unless the material asks for them, as in Source.
- On surf_garden this made water views about 15% faster, and more where the 3D sky is above a pond.
- r_waterforcereflectentities 1 puts entities back into every reflection.

### P867 Water that ripples and scrolls
- Animated water such as surf_garden's now ripples and moves instead of standing still, and scrolling water such as surf_boreas's scrolls.
- Water tint, distortion and fog follow Source's water shader more closely.

### P866 Refracting glass and fountains like Source
- With hl2_refract 1, glass warps and tints as in Source: surf_garden's fountain shows the statue through rippling sheets.
- surf_boreas's icicles now look like bright ice with a reflection, not dark see-through panes.
- Refract glass uses its tint, reflection and blur settings, and costs a little less to draw.

### P865 Gravity, team filters, breakables, point teleports
- Gravity volumes (trigger_gravity, on 87 maps) now change your gravity; entering a start zone resets it.
- Team and class filters work, so maps with separate T and CT teleports send you to the right one; point_teleport moves you.
- Breakable walls and glass break when the map says so (not on lobbies, where that would change the map for everyone).
- In your own games, +attack fires a silent shot that presses shootable buttons and breaks breakables.

### P864 No water reflections inside water reflections
- Water seen inside another water's reflection is no longer rendered a second time, as in Source.
- surf_garden's pond stage drew about twice as fast.

### P863 Lighter HUD, same picture
- The HUD does about a third less work each frame, most noticeable with the strafe trainer and every panel on. Nothing on screen changes.

### P862 Smooth stage teleports offline
- In your own games, teleports to the next stage (such as on surf_garden) no longer judder: map triggers are now predicted offline too.
- cl_predict_listen 0 restores the old behaviour.

### P860 Spinning and bobbing decorations
- Decorative spinning and bobbing map pieces now move, like the dagger in surf_gigapede's spawn, and props attached to them follow.
- Only pieces that cannot touch you move, so collision is unchanged. Seen on 282 maps.

### P859 See-through Refract glass
- Refract glass that drew bright white or as an opaque picture is now see-through, with its tint and reflection.
- Fixes surf_spectra's windows, surf_garden's fountain and surf_gigapede's red glass, among hundreds of maps.
- Applies at hl2_refract 0, and at the default 2 for panes with no texture of their own.

### P857 Download page: its own folder
- The launcher installs into the folder it runs from, so the download page now says to give it its own folder (Linux: chmod +x).

### P856 Story challenges, medal toasts, Halloween
- Story levels can now set one-run challenges: no fails, W only, no jumping, sideways or half-sideways, a top speed, a route or a stage time.
- Others ask for the first finish, a rank, or an improvement on your time.
- A toast shows the moment a lobby run earns a medal, and a gold is announced to the lobby.
- Events have dates (opens in, ends in), starting with a Halloween event of 11 maps from 24 Oct to 2 Nov.

### P855 3D viewer: props and HDR maps
- The 3D run viewer now draws props made with Propper, such as surf_null's bhop platforms and arches.
- HDR maps no longer fail to load in Chrome and Edge.

### P854 Story mode
- New STORY menu between PLAY and VISUALS: a ladder of levels where your runs earn bronze, silver or gold.
- Trophies unlock the next chapter; locked levels are greyed out, and Play takes you to the map.
- See other players' ladders in the Players tab; events have a ladder of their own.
- Only World of Surf runs count: Momentum and KSF imports and segmented runs do not.

### P853 Tier completion by Surf or Bhop
- Player profiles on the website and the in-game player card can show tier completion for All, Surf or Bhop maps.
- Opening a tier lists only that kind's maps.

### P852 Launcher-first downloads
- The download page's main buttons are now the launcher; the full package archives are linked below them.
- New downloads no longer include ftesurf.bat or ftesurf_debug.bat; existing installs keep theirs.

### P851 m restarts the run, r resets the stage
- New default keys: m is goto_start (back to the start of the run) and r is reset (back to the start of your stage).
- Restart run, Reset stage and Go to spawn sit together in the key panel; a saved config keeps its own binds.

### P850 Cheaper full water
- With full water (hl2_water 2), water views no longer draw the main view's props as well as their own, or a 3D sky they cannot see.
- In surf_boreas's cave, frame time fell from about 8.9 ms to 4.1 ms.
- r_nestedents 0 and r_skyroomneed 0 restore the old behaviour.

### P848 New reset command; goto_start restarts the run
- New reset command: what goto_start used to do, taking you back to the start of the stage you are on.
- goto_start now takes you to the start of the run when you are past the first stage, cancelling the run.
- The key panel has a Reset stage row, and reset also works while spectating.

### P847 Glows and embers behind glass
- Glow sprites and fire embers behind glass or a grate now draw behind it, not over it, as on surf_dune's braziers.

### P846 Faster, friendlier console
- Typing map names in the console no longer stutters: completion reads a cached map list, about 0.3 ms a key instead of 140.
- Enter on a highlighted cvar types it in so you can give it a value; Tab with nothing highlighted types the first row.
- Clicking a completion row types it, and the console key now closes the console even with text typed.
- The window focus correction message no longer prints on screen.

### P845 goto_spawn goes to the spawn
- goto_spawn now takes you to the map's spawn point, where joining puts you, instead of the start zone. It cancels a running run.

### P844 Glass walls and glowing signs
- Brush entities now use their render mode: bhop_eazy's glass walls are see-through, and additive signs glow without black squares.
- Pieces that Source hides are hidden here too.

### P843 Fire behind glass and grates
- A fire behind glass or a grate now draws behind it instead of in front, as on surf_dune's braziers behind the chains.

### P841 Speed caps from Momentum zone files
- Maps now use the speed cap in their Momentum zone file, such as surf_apollo at 10000 and surf_boreas at 5000 instead of 3500.
- 164 lobby maps change cap; existing times stay on their boards.
- The zone editor saves the speed cap into the zone file, and the publish dialog shows which cap goes with it.
- A Multi-Session saved under a different cap is dropped, saying the speed cap changed.

### P840 Unranked line names the setting; slow-motion runs
- When a lobby run is unranked for its input settings, the line now names the setting, such as "input mode: m_accel is on".
- Runs played in slow motion are now detected and left unranked.

### P839 Faster 3D run viewer
- The 3D run viewer runs about 11-16% faster on prop-heavy maps such as surf_demise.

## 0.1.28 2026-10-19

### P837 Faster HUD run graph
- The HUD run graph's unchanging parts are drawn once and reused, saving about 0.4 ms a frame with eight board lines.

### P831 Much faster prop-heavy maps
- Static props are now sorted and drawn in batches: about 45% more fps at surf_demise's spawn, and 343 to 397 fps on surf_boreas.
- OpenGL only; r_instancing 0 turns it off.

### P825 Watch runs in 3D on the website
- Run pages on the leaderboard have a Watch in 3D link: play a run in your browser in first person, chase, overhead or free camera.
- It shows time, speed and keys, the run line, splits and a speed graph, and races the map's top recorded run.
- Textures come from your own game folder if you pick it; otherwise surfaces are flat colours.

### P823 Simpler first-boot screens; no Updates screen
- The terms and Steam screens now match the other menus, and the separate Updates screen is gone.
- Play online also turns updates on; the title menu corner can turn them off or on again.

### P821 Chat panel with select and copy
- Open chat is now a panel with the chat history: drag to select, double-click a word, and copy with Ctrl+C or right-click.
- The text field has a real cursor and selection, Ctrl word jumps, paste, and Up/Down for your last 20 messages.
- The chat font is one size smaller.

### P820 Hide failed attempts in imported replays
- Momentum and KSF replays now find failed stage attempts, so they can be hidden and skipped.
- One "successful only" chip on the replay bar hides the failed lines and skips those attempts.

### P819 Hour-long lobby maps
- Lobby maps now last an hour, and extend adds an hour.
- The first player into an empty lobby gets a fresh hour on the clock.

### P818 surf_view colours fixed
- surf_view now shows reset and teleport triggers in red, clip brushes in yellow and ramps in blue.
- The yellow wash over whole maps from hidden faces is gone.

### P817 Rewind past a failed attempt stays timed
- On maps that fail you into the start box (surf_dune), saving or resuming on the rewind from before the fail keeps the run timed (segmented).

### P815 Admin zone fixes reach everyone
- Zone changes published by map admins now go out automatically to the lobbies and the website.
- Your game switches to the zones the lobby is timing with, never mid-run.

### P813 Random stops on surf ramps fixed
- Fixed the rare dead stop while surfing, which happened crossing the seam between two curved ramp pieces (seen on surf_colin_blaster_69000).

### P812 Prediction above 4096 u/s
- Speeds over 4096 u/s are now predicted correctly, so fast maps no longer pull you back past that speed.
- The lobbies already have it; your game needs this update.

### P811 Saves shared between lobbies and your game
- Saves made on a lobby and in your own game are now one list: each side copies the other's when you join a lobby map.
- Deleting a save on one side deletes it on the other; your local copy goes to a deleted folder, never removed.
- cl_savesync 0 turns it off.

### P810 Neon fades with distance; more portals
- Neon and other map pieces that Momentum fades by distance from the player now fade here too (surf_tripportals).
- r_portalmaxviews now defaults to 16 (was 2), so more portal doors show what is behind them at once.

### P805 Camera stuck at the wrong height fixed
- Fixed the view staying high above your feet after a long frame over a step down, until you jumped (seen at surf_null's spawn).

### P802 See through portal doors properly
- The server now sends what you can see through a portal door, so surf_tripportals' hub keeps its signs and neon from the start zone.
- Portal doors keep working in noclip and spectate.

### P799 Glows hidden behind ramps; fading windows
- Light glows are now hidden behind props and displacements as in Source, such as surf_jumble's ramps.
- Areaportal windows fade with distance (surf_dragon's black disc is gone), and glows behind glass now show.

### P797 Teleport to a player
- Each player's row on the TAB player list has a Teleport button that puts you just behind them, facing their way.
- Teleporting ends your current run.

### P789 Profile pictures beside names
- Steam pictures now show beside player names in chat, the demo window, the spectator HUD, the Comparison window and completion banners.
- The main menu's friends panel and leaderboard rows show them too.

### P788 Friend adds and the added-you toast
- Adding a friend is now one-way until they add you back; presence and Join work once you are both friends.
- When someone adds you, a toast shows with F2 Add back, and their row sits faded at the bottom of your list.

### P786 Spectate inside a trigger
- You can now go to spectate while standing in a trigger, and your run stays ranked.
- Coming back does not fire the trigger again.
