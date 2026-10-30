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

### P1139 Gravity carry status through stock takeoff
- Carried gravity effects keep their run status through more ordinary ground jumps. Jump height, movement and normal map-authored effects are unchanged.

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
