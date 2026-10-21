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
