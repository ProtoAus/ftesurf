/*
===========================================================================
  cl_main.qc -- CSQC entry points.

  This CSQC does NOT predict.  Movement is engine-side, so we let FTE's own
  prediction (cl_pred.c:971-1358) run and CSQC only renders the scene and
  the HUD.  Defining CSQC_Input_Frame with a custom pmove here would fight
  the engine, not help it.
===========================================================================
*/

float vbsp_uv_reported;   // one-shot latch for the ui_bootcheck diagnostic

/*
===========================================================================
  Skybox fallback -- DELETED IN BUILD 27, and the deletion is the point.

  The rule is unchanged and still needed: a Source map names its sky in
  worldspawn's `skyname`, and some carry no such key at all.  Measured on
  surf_colin_blaster_69000 -- no skyname, sky faces textured
  TOOLS/TOOLSSKYBOX2D, and the only sky asset in its own 80-entry pakfile is a
  flat 256x256 tool texture.  Censused: 1074 of the 1084 installed cstrike maps
  declare a skyname and 10 do not.

  What was here read the entity lump from CSQC and, when the key was absent,
  wrote the name into `r_skybox`.  That worked, and it was wrong in a way that
  only showed up when something else wanted the same cvar:

    r_skybox is the USER'S override -- gl_warp.c calls it "the user's
    preference" and it beats everything, including a map that names its own sky.
    Borrowing it as a fallback slot meant the fallback and the override were the
    same variable, so the QC had to CLEAR it on every map that did name a sky
    (the branch that used to be here) -- which quietly threw away any r_skybox
    the player had set, on the next map load, forever.

  Engine patch 211 puts the rule where the answer already is.  R_SetSky knows
  the map named nothing -- that is literally `!*sky` in its own body -- so
  `r_skybox_default` fills the hole THERE, ordered below r_skybox so an explicit
  override still wins and above nothing else.  One rule, one variable, no
  clearing branch, and `sky` now reports which of the three is in force.

  This function's per-frame call in CSQC_UpdateView went with it, as did
  vbsp_sky_default; cfg/default.cfg sets r_skybox_default instead.
===========================================================================
*/

/*
  Patch 207.  The engine's own answer to "when is the entity lump readable".

  cl_defs.qc:396 has always declared this -- "Called after model+sound precaches
  have been executed.  Gives a chance for the qc to read the entity lump from
  the bsp" -- and nothing in FTESurf defined it, so every lump reader here grew
  its own lazy serverkey("map") compare instead.  That works right up until
  serverkey changes BEFORE the lump does, and then it reads the old map and
  latches the new map's name: 116 phantom portal apertures on surf_demise, at
  90 ms a frame.

  Only the portals are moved here.  The sky and zone loaders carry the same
  latent bug and the same fix would suit them, but they are not what this patch
  is about and changing them unmeasured would be worse than leaving them.
*/
/*
===========================================================================
  BUILD 47 -- cl_netfps MUST EQUAL 1/pm_ticrate, AND NOTHING RESTORED IT.

  THE DEFECT.  cl_pred.c takes the RAW cvar for the interpolation back-date:

      float netfps = cl_netfps.value;
      ...
      simtime = realtime - (1.0/netfps);

  while the usercmd SEND interval is snapped to a whole number of ticks by
  cl_netfps_snap (Patch 252).  With cl_netfps 100 against pm_ticrate 0.015 the
  send interval snaps to 15 ms but the back-date stays 10 ms, so prediction
  aims five milliseconds out of step with the commands it is replaying.  The
  extrapolated partial command's msec sawtooths across that gap every cycle and
  crosses the whole-tick boundary, which lands the predicted state a whole tick
  ahead on some rendered frames and not others.

  That is what "the speedometer reads 0-4 at 1000 fps but is fine at 60" is:
  pmove_vel really is alternating between two states.  Sixty fps hides it
  because a 16.7 ms frame period always crosses the 15 ms tick.

  NOTE WHAT THIS IS *NOT*.  cfg/netfix.cfg blames the COMMAND INTERVAL -- 10 ms
  commands into a 15 ms mover, the 101101 stall, "117 of 351 usercmds moved the
  player ZERO units".  Patch 252 fixed that and netfix.cfg predates it.  The
  rule it states is still right; its mechanism is not.  The file has been
  corrected rather than left to look measured.

  WHY THE 100 IS THERE AT ALL.  cfg/mode_bhop.cfg is right to set cl_netfps 100
  -- it also sets pm_ticrate to 0.01, so on a bhop map all of it matches.  But
  cl_netfps is a CLIENT cvar with CVAR_ARCHIVE and the mode overlay is applied
  server-side, so loading one bhop map writes 100 into ftesurf.cfg, and the
  saved config runs AFTER default.fmf's forced 66.6667.  Surf has no
  mode_surf.cfg to set it back.  Nothing ever restored it.

  WHY HERE AND NOT A STUFFCMD FROM THE SERVER.  Two reasons.  The client owns
  the client cvar, so it can COMPARE and stay silent when the setting is already
  right -- a server stuff would rewrite it on every map load whether or not
  anything was wrong.  And the ordering works: netfix.cfg records that a value
  set from a +exec config is overwritten by ftesurf.cfg loading afterwards, and
  this hook runs long after both.

  Symmetric on purpose.  A bhop map publishes pm_ticrate 0.01 and this sets 100
  straight back; the rule is "match the tick", not "prefer surf".
===========================================================================
*/
void() Net_MatchTicrate =
{
	local float tick, want, have;

	tick = serverkeyfloat("pm_ticrate");
	if (tick <= 0)
		return;                     // no Source mover published; not our business

	want = 1 / tick;
	have = cvar("cl_netfps");

	// A tenth of a command per second is the same setting.  66.6667 and 1/0.015
	// are not equal in single precision and an exact compare would re-print,
	// and re-archive, on every single map load.
	if (fabs(have - want) < 0.1)
		return;

	cvar_set("cl_netfps", sprintf("%g", want));
	print(sprintf("^3net:^7 cl_netfps %g -> %g, to match pm_ticrate %g\n",
	              have, want, tick));
};

void() CSQC_WorldLoaded =
{
	// BUILD 61: the per-map render layer at the bottom of this function.
	local string rmap, rname;
	local float  rf;

	Portal_LoadFromWorld();

	// The sprite entities, read from the same lump and for the same reason the
	// portals are read here rather than from a lazy compare in UpdateView: this
	// hook is the engine's own "the entity lump is now readable" point, and the
	// compare bets on an ordering that does not always hold (see Patch 207 in
	// CSQC_UpdateView below).  Sprite_Draw keeps the compare as a safety net.
	Sprite_LoadFromWorld();

	// Source fog, out of the same lump and here for the same reason.  194 maps
	// carry an env_fog_controller and 169 a sky_camera, and NONE of the 1337 put
	// fog keys on worldspawn -- which is the only place the engine's own fog
	// parser looks -- so until this ran, every fogged map drew flat.  cl_fog.qc.
	Fog_LoadFromWorld();

	// Build 49.  The volumetric and emissive entities, out of the same lump and
	// here for the same reason -- func_dustmotes alone is 4999 instances across
	// 464 maps and had never drawn anything.  cl_emit.qc.
	Emit_LoadFromWorld();

	/*
	  Patch 278.  The lobby avatars' own particle effects.

	  Its own file and its own exec rather than an append to
	  particles/ftesurf.cfg, so the generated per-colour blocks stay separate
	  from the hand-written map-entity ones.  tools/mkavatarfx.py writes it from
	  the palette in sv_lobby.qc, so the trail colour and the body colour cannot
	  disagree.

	  IMMEDIATELY AFTER Emit_LoadFromWorld, which is deliberate rather than
	  arbitrary: that call is what execs particles/ftesurf.cfg, so this line
	  inherits an exec point already known to be correct.  All three of Patch
	  272's rules are satisfied by being exactly here -- it is after
	  Renderer_Start, so the blocks are not discarded in silence; it runs again
	  on every map load, so it survives the r_particledesc callback the engine
	  forces there through the cvar's alias; and localcmd from CSQC runs at
	  RESTRICT_INSECURE, so P_SetModified returns early and f_modified_particles
	  stays clear.

	  Not latched to run once, for the same reason Emit_LoadForMap is not: a
	  vid_restart calls PScript_Shutdown and frees the whole part_type table.
	  Re-parsing an effect that already exists is idempotent.
	*/
	localcmd("exec particles/ftesurf_avatar.cfg\n");

	// Build 30.  The ghost's stand-in models, said out loud once per map for the
	// reason cl_portal.qc:261-266 gives -- setmodel would load them anyway, and
	// fteqcc warns about a model it cannot see precached.  This hook is where
	// precaches belong ("called after model+sound precaches have been
	// executed"), and it is the one place a stray load cannot cost a frame
	// mid-run.
	Ghost_Precache();

	// Patch 270.  Resolves the lobby avatar model indices for THIS map -- a
	// modelindex means nothing on the next one, which is also why the engine
	// zeroes its delta counters per map (cl_main.c, CL_ClearState).  Here
	// rather than lazily because this hook is defined as "called after model
	// and sound precaches have been executed", which is exactly the
	// precondition modelnameforindex needs.
	NM_WorldLoaded();

	// Build 47.  Last, because it wants the serverinfo the map load published.
	Net_MatchTicrate();

	/*
	  BUILD 61 -- cfg/render_<mapname>.cfg, THE PER-MAP CLIENT RENDER LAYER.

	  Asked for directly: "vbsp_glare_interval 0.025 is fine for most maps, but I
	  sort of want vbsp_glare_interval 0.2 on tensor2 because of the fps savings."
	  Measured at the start box of surf_tensor2 (`!s 1`), that is worth +82%:
	  328.5 fps at 0.025 against 597.4 at 0.2, four interleaved pairs, every
	  delta positive.  So the preference is real and it needs somewhere to live.

	  WHY NOT cfg/map_<mapname>.cfg, WHICH ALREADY EXISTS.  That file is the
	  SERVER's ruleset layer (Patch 267, SV_LoadMapRuleset in sv_phys.c) and
	  putting a rendering preference in it would be wrong three ways: it is
	  applied in SV_SpawnServer, so on a dedicated lobby it would set the
	  SERVER's copy of a cvar only the client reads; every line it applies is
	  counted in pms_numover and named in the `movement` report beside
	  sv_maxvelocity, so a framerate preference would pollute the audit trail of
	  what physics a run was set under; and it resolves names with Cvar_FindVar,
	  which on the first map of a session runs before the CSQC progs have
	  registered anything -- so it would warn `no cvar named` and be ignored,
	  then silently start working on the second map.  Those are three different
	  trust and lifetime boundaries and this is the client's side of all of them.

	  WHY TWO FILES AND NOT ONE.  A bare per-map exec is STICKY: set 0.2 on
	  tensor2, load anything else, and the cvar is still 0.2 with nothing to put
	  it back.  That is exactly how mode_bhop.cfg's cl_netfps 100 ended up on
	  every surf map.  So the baseline is exec'd first and the per-map file
	  second -- same ordering rule the server layer uses, and for the same
	  reason: the general case is the family, the map file is the specific case
	  and wins.  Both in one localcmd so nothing can interleave between them.

	  SILENT WHEN ABSENT, LOUD WHEN IT FIRES.  Roughly none of the 1310 maps
	  will have one of these, so a missing file must not print -- the same
	  contract Emit_LoadForMap keeps for particles/<map>.cfg and Zone_LoadForMap
	  for its json.  But a file that DOES change your settings must say so, or a
	  per-map override becomes an unexplained framerate difference between two
	  maps.  fopen rather than letting exec fail, because exec's own failure
	  message is the thing being avoided.

	  LAST IN THE HOOK deliberately: everything above has finished loading the
	  map's own data, so this layer can override any of it and nothing it sets
	  can be clobbered by a later loader.
	*/
	rmap = serverkey("map");
	if (rmap != "")
	{
		rname = sprintf("cfg/render_%s.cfg", rmap);
		rf = fopen(rname, FILE_READ);
		if (rf >= 0)
		{
			fclose(rf);
			localcmd(sprintf("exec cfg/render_default.cfg\nexec %s\n", rname));
			print(sprintf("render: per-map layer %s applied over cfg/render_default.cfg\n",
			              rname));
		}
		else
		{
			/*
			  No map file, but the BASELINE still has to run -- otherwise an
			  override applied on the previous map is never undone, which is the
			  stickiness this whole arrangement exists to prevent.  Silent: this
			  is the case for essentially every map.
			*/
			localcmd("exec cfg/render_default.cfg\n");
		}
	}
};

void(float apilevel, string enginename, float engineversion) CSQC_Init =
{
	Font_Init();
	HUD_RegisterCvars();
	Zone_RegisterCvars();
	Timer_RegisterCvars();
	SaveLoc_RegisterCvars();
	Gfx_RegisterCvars();
	Watch_RegisterCvars();
	Scores_RegisterCvars();
	Ghost_RegisterCvars();
	Results_RegisterCvars();        // build 48
	/*
	  Build 49.  This one also takes every particleeffectnum handle, ONCE, and
	  that has to happen here rather than per map: the effect names are what
	  auto-load particles/ftesurf.cfg, the load is queued through the command
	  buffer, and asking at map load would leave the FIRST map particle-free
	  while the buffer drains.  See the essay above Emit_Precache.
	*/
	Emit_RegisterCvars();
	HUD_EditRegisterCvars();
	NM_RegisterCvars();             // Patch 270, the lobby network monitor
	Ev_Register();                  // build 54, the trigger/entity inspector

	// Not a cvar registration: this VM is new, and a strbuf handle carried over
	// from the last map would alias a live buffer.  See Rec_ViewInit.
	Rec_ViewInit();

	// (vbsp_sky_default was registered here.  Build 27 replaced it with the
	//  engine's r_skybox_default -- see the essay at the top of this file.)

	/*
	  Decals.

	  vbsp_decal_size is a half-width in world units, and it is a guess -- an
	  honest one, but a guess.  Source takes a decal's size from its material
	  ($decalscale against the texture's own dimensions), and FTE's VMT parser
	  does not surface either to QC, so there is nothing to read.  32 (a
	  64-unit square) matches the common 64x64 decal texture at scale 1.
	  If they come out obviously wrong on a map, this is the knob.
	*/
	// CVAR_ARCHIVE since build 33: this is a gfx_menu row (page 2), and every
	// row of that menu was being thrown away on quit.  See the seta essay on
	// Gfx_Cycle in cl_gfx.qc for the whole story.
	registercvar("vbsp_decals", "1", CVAR_ARCHIVE);
	registercvar("vbsp_decal_size", "32");

	/*
	  info_overlay -- the decals Source bakes into LUMP_OVERLAYS rather than
	  writing as entities.  230 maps carry them and none has ever drawn one.
	  See the essay above Overlay_Place in cl_decals.qc for what the builtin can
	  and cannot express; these three cvars are the three thresholds it names.
	*/
	registercvar("vbsp_overlays", "1", CVAR_ARCHIVE);
	// Projection depth, in units.  Independent of the overlay's own size on
	// purpose: the clip box is always at least as deep as the decal is tall, so
	// this is what actually decides how far the decal bleeds onto neighbouring
	// parallel geometry (everything past depth/2 fades to zero alpha).
	registercvar("vbsp_overlay_depth", "16");
	// How far a quad may deviate from a rectangle, relative to its own size,
	// and still be drawn as its bounding box.  0.1 keeps 97.9% of the library;
	// the remainder are visibly-sheared parallelograms a rectangle cannot fake.
	registercvar("vbsp_overlay_shear", "0.1");

	/*
	  The sprite entities -- env_sprite and friends, plus the point_spotlight
	  light shafts.  See cl_sprites.qc for what each class is and for the two
	  that are counted and declined.

	  TWO SWITCHES rather than one, because the two halves are different
	  purchases.  The billboards are 11232 small quads that mostly cost fill;
	  the shafts are 23677 large additive ones and are by far the more likely
	  thing to want gone -- they are the biggest class in the family and they
	  cover a lot of screen.  Both CVAR_ARCHIVE, both gfx_menu rows.
	*/
	registercvar("vbsp_sprites", "1", CVAR_ARCHIVE);
	registercvar("vbsp_spotlights", "1", CVAR_ARCHIVE);
	/*
	  BUILD 54 -- env_lightglow, the third switch and the newest class.

	  Reported as "some of the light glow sprites on the flat white brush models
	  acting as light are actually horizontally stretched in Source, looks like a
	  lens flare almost, can you find that value?"  The value is
	  HorizontalGlowSize / VerticalGlowSize, and this is the class that carries
	  it: surf_tensor2 has 166 of them and 165 read 65 wide by 35 tall.

	  ITS OWN SWITCH rather than sharing vbsp_sprites, for the reason the two
	  above are split: this is 3393 NEW quads across 137 maps that have never
	  drawn anything, and they are view-space flares drawn over the world.  If
	  they turn out to be too much on some map, the answer needs to be "turn off
	  the flares" and not "turn off every billboard in the map".  ARCHIVE, like
	  its two neighbours, because it is a look preference.

	  It is also the A/B: the flares are additive and sit on top of the
	  env_sprite glows that were already there, so "is that halo the new thing or
	  the old thing" has no answer from a screenshot without a switch.
	*/
	registercvar("vbsp_lightglow", "1", CVAR_ARCHIVE);
	/*
	  BUILD 55 -- how a sprite faces you.  2 = read $spriteorientation out of each
	  material (the default), 1 = force vp_parallel, 0 = force parallel_upright.

	  Reported as "the light sprites don't always face the camera, they stay
	  'locked' from underneath and stand upright in the Z".  They did: every
	  non-oriented sprite was drawn parallel_upright, which is Source's fallback
	  for a SILENT material (spritemodel.cpp:311) and not what the materials
	  actually say -- 177 of the library's 213 sprite materials ask for
	  vp_parallel, including sprites/light_glow03 which is what tensor2 uses.

	  The two forcing arms are here because this is a look you have to judge by
	  eye, and flipping one cvar at a fixed vantage is the only way to compare the
	  two without a rebuild.  NOT archived: the read-it-from-the-material answer is
	  the correct one and a forced value should not survive a restart.
	*/
	registercvar("vbsp_sprite_orient", "2");
	// Draw distance in units, 0 = unlimited.  A sprite is culled on its centre
	// less its own radius, so a large glow stays visible past the line.
	registercvar("vbsp_sprite_dist", "0");
	// One-frame dump of the material table and the cull result; clears itself,
	// same idiom as zone_debug.
	registercvar("vbsp_sprite_debug", "0");

	/*
	  BUILD 52 -- LIGHT GLARES.  Reported as "the light sprites simply rotate
	  towards the camera and get cut by the world geometry", and both halves are
	  the same mistake: an additive glow is a LENS effect, so it belongs over the
	  world with its visibility decided by a trace, not by the depth buffer.
	  Sprite_Glare in cl_sprites.qc does what Source's CGlowOverlay does; the
	  essay above it cites the file and line for every constant here.

	  ARCHIVE on the switch, because it is a look preference and someone may
	  prefer the old clipped sprites. The other two are tuning, not preference.

	  traces: a traceline per glow per frame is not free at 429 glares on
	  surf_tensor2, so they are traced round-robin and the fade hides the
	  staleness. 0 freezes the traces entirely, which is the A/B for "is the
	  trace the cost".  See the BUILD 59 note below for the value.

	  decay 0.05 is Source's cl_sun_decay_rate exactly (glow_overlay.cpp:59): a
	  50ms fade either way, framerate-independent because it steps by frametime.
	*/
	registercvar("vbsp_glare", "1", CVAR_ARCHIVE);
	/*
	  BUILD 59: 8 -> 40, because BUILD 58 CHANGED WHAT THIS COUNTS AND LEFT THE
	  VALUE ALONE.

	  Reported as "the update rate of the sprites ... is really quite slow? like
	  up to 1 sec on tensor2.  When they go behind a wall they keep shining, and
	  when revealed they take a bit to render."

	  Build 58 replaced Sprite_Glare's yes/no answer with a 5-ray sample (Source's
	  proxy, c_pixel_visibility.cpp:83-91) and made this budget count RAYS rather
	  than GLARES.  The unit changed; the number did not:

	      build 57, 1 ray:   8 glares/frame -> 429/8  =  54 frames per sweep
	      build 58, 5 rays:  2 glares/frame -> 429/2  = 215 frames per sweep

	  -- 4x slower, and at ~200fps that is the reported ~1s.  Between sweeps a
	  glare keeps its LAST answer, which is exactly "keeps shining behind a wall,
	  takes a beat to come back".  The 50ms ramp was sized to hide a 54-frame
	  sweep and cannot hide a 215-frame one.

	  40 restores build 57's sweep rate EXACTLY (40/5 = 8 glares/frame) while
	  keeping the better 5-ray fraction.  It is not new tuning; it is the old
	  number converted into the new unit, which is what build 58 should have done.
	  The build-58 comment in Sprite_Glare predicted this verbatim -- "If glares
	  lag when you spin, raise the budget rather than lowering the rays" -- and
	  writing that down instead of changing the default is the whole mistake.

	  NOT ARCHIVED, deliberately, and that is load-bearing here: CVAR_ARCHIVE
	  would have pinned 8 into every existing ftesurf.cfg, so the fix would reach
	  new installs only and the person who reported it would still see the bug.

	  KNOWN LIMITATION, stated rather than discovered later: the budget is FIXED,
	  so sweep time scales with the map.  429 glares on tensor2 and a dozen on a
	  quiet map get the same budget -- roughly a 30x spread in staleness across
	  the library.  A target INTERVAL would be steadier than a target ray count.
	  Not done here: this is a regression repair, and that is a redesign.
	*/
	registercvar("vbsp_glare_traces", "40");
	registercvar("vbsp_glare_decay", "0.05");
	/*
	  BUILD 59 -- THE VIEW CULL, and it is a MARGIN rather than a boolean.

	  Sprite_Glare's round-robin used to walk every glare on the map including the
	  ones behind you: 429 on surf_tensor2.  Measured cost of a ray is 27.1us
	  (from Lex's own fps at three budgets: 555-600 at traces 8, 360-420 at 40,
	  200-220 at 120 -- a straight line).

	  WHAT IT ACTUALLY BUYS, corrected in build 60 and worth reading before
	  touching it, because the first answer written here was wrong.  It buys no
	  framerate -- the budget is in RAYS and is saturated either way, measured
	  383.4 fps cull-off against 399.0/412.5 cull-on.  It buys LATENCY: a culled
	  glare is a visit that costs no rays and still advances the cursor, so the
	  sweep goes from 53.6 frames to a MEASURED 11.2 and 10.8 (frames counted
	  between cursor wraps, two arms).  The build 59 census divided by glares
	  TRACED instead of VISITED and therefore reported this 4.8x as "54 -> 50
	  frames"; I passed that on to Lex as "the cull bought almost nothing".  It
	  was the denominator, not the cull.

	  And "roughly 50 are ever on screen" -- also written here -- was wrong: 302
	  of the 429 are inside the frustum and only 6 draw, because the other 296
	  are occluded.  The cull pays on the ones BEHIND the eye.

	  0     disables the cull -- the build-58 behaviour, and the A/B for "is the
	        cull what changed".
	  1.0   the exact circumscribed cone.
	  1.25  default: 25% slack on the tangent, so turning has margin before a
	        glare needs its first trace.

	  The cone is built from `fov` assuming a SQUARE screen, which makes it wider
	  than any real widescreen frustum -- deliberately, because a cone that is
	  too generous wastes a few rays and a cone that is too tight drops a glare
	  that is on screen.  See the essay in Sprite_Glare.
	*/
	registercvar("vbsp_glare_cull", "1.25");

	/*
	  BUILD 58 -- HOW MANY RAYS MAKE UP ONE GLARE'S ANSWER.

	  Source does not ask "is the centre of the lamp visible": it rasterises a
	  small proxy quad and multiplies the glow by pixels/pixelsPossible, a
	  FRACTION. Ours answered 1 or 0, so a flare Source draws at 0.2 we drew at
	  full or not at all -- measured at Lex's own vantage the flares alone lifted
	  the frame by +17.30 mean luma against a zero noise floor.

	  5 fires the centre plus the four corners of Source's own proxy; 1 restores
	  builds 52-57 exactly. Only those two values; see Sprite_Glare for why the
	  budget below counts RAYS, so the per-frame traceline cost is unchanged.
	*/
	registercvar("vbsp_glare_rays", "5");

	/*
	  BUILD 60 -- FIVE RAYS ONLY WHERE FIVE RAYS CAN CHANGE THE ANSWER.

	  Build 59 measured the cost of the budget Lex needed for responsiveness:
	  vbsp_glare_traces 8 gave 555-600fps, 40 gave 360-420, 120 gave 200-220 --
	  a straight line at 27.1us per ray.  The frustum cull tried first removed
	  only 7% of them, because the census shows 302 of surf_tensor2's 429 glares
	  are genuinely in the frustum and 296 of those are HIDDEN, which is a thing
	  only a trace can find out.

	  So the saving is in the 296: each fires five rays to learn what its first
	  ray already said.  This is the limit on how many consecutive centre-only
	  confirmations a hidden glare may take before it owes a full five-ray
	  re-check -- a MARGIN, not a boolean, so that 0 restores build 59 exactly
	  and there is only one way to spell "off".  8 costs (8*1 + 5)/9 = 1.44 rays
	  per hidden glare.

	  The bound on the error is geometric, not hopeful: the four corners sit
	  GlowProxySize (4.0 units on these glows) from the centre aim point, so a
	  wrong cheap answer needs an occluder silhouette within 4 units, where the
	  true answer is 1/5 or 2/5.  A glare becoming VISIBLE is never missed --
	  its centre ray comes back clear and the shortcut declines.  The full essay
	  is in Sprite_Glare.

	  MEASURED, surf_tensor2 at Lex's vantage, sweep counted in frames between
	  cursor wraps rather than derived: 11.2 frames without it, 3.7 with it, and
	  9.8 at a ray budget of 12 -- i.e. build 59's responsiveness for 30% of the
	  rays, which is ~580-630 fps against ~400.  fps at the SAME budget is
	  unchanged (298.1/323.4 on vs 318.9 off, against a same-setting spread of
	  25), and the frame is pixel-identical on vs off at two vantages.  The
	  whole gain is latency; none of it is frame cost.
	*/
	registercvar("vbsp_glare_adaptive", "8");

	/*
	  BUILD 61 -- SPEND RAYS TO A DEADLINE, NOT TO A QUOTA PER FRAME.

	  Build 60's own numbers are the argument.  vbsp_glare_traces is rays per
	  FRAME, so what it delivers -- the age of a glare's occlusion answer -- is
	  a different quantity on every map:

	      surf_tensor2, 429 glares, 40 rays    3.7 frames = 9.3 ms at 397 fps
	      a 12-glare map, 40 rays              the cursor wraps ~3x per FRAME

	  The second case is pure waste: two of those three passes re-ask a question
	  that has not had time to change, at 27.1 us a ray.  The first case is the
	  opposite -- 9.3 ms is far finer than any eye needs, and the rays buying
	  that precision are the ones Lex is paying ~200 fps for.

	  So this cvar is the interval in SECONDS, and it is the age bound directly:
	  every glare gets re-answered at least this often, whatever the map holds
	  and whatever the framerate is.  vbsp_glare_traces stays as the CEILING, so
	  a pathological map misses the deadline instead of dropping a frame, and
	  the census names which of the two limits stopped the loop.

	  DEFAULT 0, WHICH IS OFF, and that is deliberate rather than timid.  Lex
	  chose vbsp_glare_traces 40 explicitly after measuring three values of it,
	  and a default that silently overrode that choice would be me deciding his
	  framerate/latency trade for him.  0 is build 60 exactly.

	  MEASURED, surf_tensor2 at Lex's vantage, three runs -- b61int (mechanism
	  and picture), b61fps (four interleaved pairs) and b61curve (the curve).
	  Staleness is computed from the census's own two counters and needs no
	  framerate reading at all: the quota IS spr_n * frametime / interval, so
	  frametime = quota * interval / 429 and staleness = sweep * frametime.

	      interval   rays/frame   staleness   fps     vs adjacent control
	        0 (off)    40-44         9.5 ms   354.6        --
	        0.015      20           15.9 ms   489.4       +43%
	        0.025       7-12        26.8 ms   574.9       +62%
	        0.05         1.5        42.6 ms   586.5       +55%
	        0.10         2         110   ms   674.8       +71%

	  Every arm met its deadline to within 15% and none was stopped by the ray
	  ceiling.  THIS IS THE FIRST CHANGE IN THE SERIES THAT MOVES FRAMERATE: the
	  view cull and the adaptive rays both could not, because the budget was in
	  rays and saturated either way, and the one time I claimed otherwise I was
	  reading a broken census.  Here the four interleaved pairs of b61fps read
	  +227, +262, +289 and +252 fps, all the same sign.

	  AND THE PICTURE DOES NOT CHANGE.  Eight of b61curve's nine settled arms --
	  every interval from 0.025 to 0.1 plus four interval-0 controls -- are
	  BYTE-IDENTICAL in the centre region, 0 of 28 pairs differing.  The 0.015
	  arm differs by 0.118% of pixels, a quarter of the 0.43-0.62% same-setting
	  floor measured at this vantage in the other two runs.

	  THE ROW THAT MATTERS IS 0.025, and it is a match to a number Lex already
	  accepted rather than a number I picked: build 59 at vbsp_glare_traces 40
	  delivered 27.7 ms of staleness and he approved it explicitly.  0.025 gives
	  26.8 ms -- the same responsiveness -- at ~575 fps against build 60's ~355.
	  Build 60's own 9.5 ms is finer than anything reported as a problem and is
	  being paid for at 40 rays a frame.

	  WHAT IS STILL UNVERIFIED, and it is the only thing that decides the row:
	  whether a given staleness is VISIBLE WHILE TURNING.  A static camera
	  converges -- 296 of the 302 glares in frame are occluded and stay occluded
	  -- so the pixel-identity above is guaranteed by construction and says
	  nothing about a spin.  No cfg can pan the view smoothly (setpos jumps), so
	  that one is Lex's to feel.

	  DEFAULT 0.025 ON LEX'S INSTRUCTION: "0.025 is fine for most maps".  It was
	  0 (inert) for one build while the trade was his to judge.

	  AND THE CURVE ABOVE DOES NOT GENERALISE ACROSS A MAP, which I only found
	  because he said "test on !s 1".  At surf_tensor2's START BOX the census
	  reads `glare 415 in frame, 411 hidden` against 302/296 at the vantage the
	  curve was measured at -- almost nothing is CULLABLE there, so a visit costs
	  ~1.05 rays instead of ~0.35 and the quota no longer fits under the ray
	  ceiling.  Measured at `!s 1`:

	      interval 0      40 rays   sweep 11.5 frames   28.5 ms   269-337 fps
	      0.025           40 rays   sweep 12.2 frames   30.2 ms   328.5 fps
	      0.2            ~2  rays   sweep 141  frames  197   ms   597.4 fps

	  0.025 IS INERT THERE.  It asked for 40-49 visits, the 40-ray ceiling
	  covered 28-45 of them, and `stopped by THE RAY CEILING (interval not met)`
	  fired on 7 of 9 samples -- so the sweep is 12 frames either way and the
	  interval is not being honoured.  That is the census field earning its
	  keep: without it this arm would read as "0.025 mysteriously does nothing
	  here" instead of "the budget cannot afford what you asked for".

	  So the per-map layer at the bottom of CSQC_WorldLoaded is not a
	  convenience -- the right interval genuinely differs by map, and by more
	  than a factor of eight on this one.  cfg/render_surf_tensor2.cfg.
	*/
	registercvar("vbsp_glare_interval", "0.025");

	/*
	  BUILD 58 -- THE SOURCE DIMMING TERMS, one switch over all of them.

	  Reported as "a big square of translucent color, the texture has been
	  reduced to flatness". It was neither the texture nor the size: the sprites
	  are 2304-unit billboards because Source draws them that way, and the square
	  is the faint tail of a correct glow texture made visible by too much gain.
	  What was missing is everything Source dims a glow sprite BY --
	  renderamt applied twice, an inverse-square distance fade, and a fractional
	  rather than binary occlusion.

	  ONE cvar for the lot, and NOT archived: this is a correctness switch, so
	  the fixed path is the one that should survive a restart. It exists so the
	  A/B is a runtime toggle inside one process, because the pixel noise floor
	  is per-run -- see the trap file. Set it to 0 to see what was reported.
	*/
	registercvar("vbsp_sprite_source", "1");

	/*
	  BUILD 58 -- THE FLARE INTENSITY, and why it is a knob rather than a fix.

	  The env_lightglow port is faithful: measured term by term against Source at
	  Lex's own vantage it reads dist 2895, fade 0.921, glare 1.000, half 65x35 at
	  a 100-unit basis, col 0.678 0.804 0.886 -- every factor is what
	  glow_overlay.cpp and c_lightglow.cpp specify, and the 66-degree quad is
	  CalcBasis's own geometry. It still does not look like his Momentum
	  reference, where no such shape appears.

	  The difference that survives scrutiny is not in this code: Momentum forces
	  mat_hdr_level 2 and dynamic tonemapping with auto-exposure clamped to
	  0.5-2.0 (cdll_client_int.cpp:917-929), which scales every additive
	  contribution down, and we apply no tonemap at all. So a term that is
	  correct here is composited into a frame that is not.

	  1.0 is Source's own arithmetic and stays the default; this exists so the
	  difference can be dialled rather than argued about, and so a value chosen
	  by eye is one number in one place instead of a fudge buried in the draw.
	  ARCHIVE: it is a look preference, like its three neighbours above.
	*/
	registercvar("vbsp_lightglow_scale", "1", CVAR_ARCHIVE);

	/*
	  BUILD 53 -- what that trace is allowed to hit.

	  Reported as "brush entities do not block the sprites from rendering when
	  they should", which is precisely the limitation build 52 shipped with and
	  wrote down: a CSQC traceline runs against csqc_world, and the server's
	  func_* brush entities are not in it. The client now builds its own
	  invisible copies at map load, and this picks which ones.

	      0  worldspawn and static props only -- build 52's behaviour
	      1  ...plus SOLID brush entities. Source's own rule for the glow it
	         traces: glow_overlay.cpp:236-237 traces with CONTENTS_SOLID
	      2  ...plus the drawn-but-not-solid ones: func_illusionary (21,231
	         across the library) and every func_brush declaring "solidity 1".
	         Closer to what Source ACTUALLY does for a world glow, which is a
	         hardware pixel query (glow_overlay.cpp:247-250) and therefore sees
	         anything that draws.

	  2 IS THE DEFAULT, and the map that prompted this is why. 1 looks like the
	  conservative choice and on surf_tensor2 it is the useless one: 145 of the
	  map's 160 func_brush declare "solidity 1", so mode 1 keeps 16 of 622 brush
	  entities and the first measured run showed it changing nothing at all --
	  232 of 240 glares hidden with the occluders in, and 232 of 240 with them
	  out. The spawn portals themselves are in the 145: the combine shield is a
	  func_brush with solidity 1. A mapper uses that for detail geometry you can
	  walk through and cannot see through, which is precisely the thing a glow
	  should be hidden behind.

	  The cost of being wrong at 2 is a glare hidden behind something you can
	  see through -- a glass pane, a grate. 1 is there for anyone who would
	  rather have that than the reverse, and 0 restores build 52 exactly.

	  It also fixes point_spotlight, which traced against the same empty world
	  and shot its beam through every door on the map.

	  WHAT IT COSTS, MEASURED IN BUILD 60 -- this is where the price of a glare
	  ray goes.  Lex's fps against the ray budget gave 27.1us per ray, roughly
	  30x what a BSP trace against a world model should cost, and the suspect was
	  always these entities: every ray is tested against worldspawn PLUS all 161
	  of them, with no spatial index in front.  A one-process A/B at his vantage,
	  40 rays a frame, mode 2 / mode 0 / mode 2:

	      444.9 fps   529.6 fps   451.5 fps     (same-setting spread 6.6)

	  +18% of the whole frame, or 0.36ms over 40 rays = ~9us of the 27.1us per
	  ray, ~56ns per occluder per ray.  So the occluders are a third of the ray
	  price and the world trace is the other two thirds.

	  NOT A REASON TO SET 0.  The same run shows 185 traces stopped by an
	  occluder over a load sweep, so they do block glares -- just not any at that
	  particular vantage, where `299 hidden` is identical with and without them
	  because worldspawn hides the same ones.  A faster arm that draws the wrong
	  thing is not an improvement.  Build 60's adaptive rays are the mitigation
	  that does not cost correctness: at the 12-ray budget they make viable, the
	  whole occluder cost falls to ~0.11ms.
	*/
	registercvar("vbsp_glare_brush", "2", CVAR_ARCHIVE);

	// The map's 3D skybox (sky_camera).  On by default because 43 maps look
	// wrong without it, but it is a second full scene render, so it is the
	// first thing to turn off when measuring frame cost on one of them.
	// CVAR_ARCHIVE since build 33, same reason as vbsp_decals above.
	registercvar("vbsp_skyroom", "1", CVAR_ARCHIVE);

	/*
	  The map's own fog (env_fog_controller, and sky_camera's for the 3D skybox).
	  On by default because ~201 maps were authored with it and render flat
	  without it.  Toggleable because fog is a visibility handicap in a timed
	  game and some players will not want it -- it is a client graphics option
	  like the rest of this family and has NO effect on whether a run ranks.
	  CVAR_ARCHIVE, same reason as vbsp_skyroom above.
	*/
	registercvar("vbsp_fog", "1", CVAR_ARCHIVE);

	// Pre-strafe jump releases +forward for you.  See PreStrafe_InputFrame.
	registercvar("run_prestrafe", "1");
	registercvar("run_prestrafe_time", "0.25");

	/*
	  `retry` keeps your position, angle and run across the map restart.

	  Registered on BOTH sides, deliberately: the client tests it before writing
	  its sidecar and returns FALSE to the engine, which then does the plain
	  map_restart of Patch 167 -- so 0 is the previous build exactly, and the
	  server's own copy refuses the command if it somehow arrives anyway.
	*/
	registercvar("rec_retry", "1");

	// Engine sbar off -- we draw our own HUD and nothing else.
	cvar_set("cl_sbar", "0");
	cvar_set("scr_sbaralpha", "0");

	print("FTESurf CSQC loaded\n");
};

void() CSQC_Shutdown = { };

/*
  Forced view angles from the server -- svc_setangle, its relative form, and
  svcfte_setangledelta.  Build 32.

  Delegated whole, because the ghost is the only thing in this mod with an
  opinion about them: while the camera is detached, a teleport's angle snap
  belongs to the BODY and not to the camera the mouse is flying.  Returning
  FALSE is the engine's own behaviour unchanged, and that is what every frame
  that is not ghosting gets -- spawns, ordinary teleports, `zone_goto`, all of
  it.  The reasoning, and why this hook rather than a branch inside
  trigger_teleport_touch, is on Ghost_SetAngles.
*/
float(vector newang, float isdelta) CSQC_Parse_SetAngles =
{
	return Ghost_SetAngles(newang, isdelta);
};

/*
  The hook for rewriting input_* before the engine builds the usercmd.

  It was empty until build 12 -- the strafe trainer reads input rather than
  writing it, and everything else wants the engine's own input verbatim.  The
  one thing that does write here is the save-lock view freeze, and it has to be
  here rather than in the HUD: this runs once per usercmd, so a client drawing
  faster than the tick rate would otherwise still send moved angles on the ticks
  between two rendered frames.
*/
/*
  BUILD 13b -- the pre-strafe jump lets go of W for you.

  Asked for as "release +forward on +jump when you're walking on the ground,
  but not if you're just bhopping around".  Those two are the same key press
  and the same button bit; the only thing that separates them is HOW LONG YOU
  HAVE BEEN ON THE GROUND.  A pre-strafe is a walk -- a second or two of
  W+A building speed before the launch.  A bhop touches down for one or two
  ticks and leaves again, and pm_autobunny re-jumps on the tick you land, so
  the ground phase is nearer 15 ms than 250.  run_prestrafe_time is that line,
  and 0.25 s is comfortably above any landing and below any deliberate walk.

  The release then LATCHES, because the point is the whole flight, not the
  frame you jumped on: you air-strafe with A or D and the mouse, and W held
  through it is exactly the input that stops it working.  It ends on whichever
  comes first --

    * you let go of W yourself, so tapping it again mid-air still works;
    * you land, so the next hop keeps its forward and bhopping is untouched.

  The landing test needs the airborne flag as well, because on the frame the
  jump is pressed you are still standing on the ground and would otherwise
  clear the latch you just set.

  Only positive forward is suppressed; +back is never touched.
*/
float run_ps_ground;             // cltime we last touched down, 0 = airborne
float run_ps_jumpheld;           // jump was down on the previous input frame
float run_ps_left;               // ...and we have actually left the ground since
//run_ps_release ("suppressing +forward right now") is declared in cl_keys.qc:
//the key block draws it and cl_hud.qc compiles before this file.

/*
  The dwell that makes a jump an INITIAL jump rather than a hop.

  BUILD 19: the server is the authority.  It uses the identical number to decide
  whether your start was hopped (SV_TimerJumpWatch) and publishes it to
  serverinfo, because the two must never disagree -- "the game released my
  +forward but the server called it a hop" is a bug report nobody can answer.
  The local cvar is the fallback for a server that does not publish it, which is
  any build before 19 and any server that is not ours.
*/
float() PreStrafe_Dwell =
{
	local float t;

	t = serverkeyfloat("run_prestrafe_time");
	if (t > 0)
		return t;

	t = cvar("run_prestrafe_time");
	if (t > 0)
		return t;

	return 0.25;
};

void() PreStrafe_InputFrame =
{
	local float onground, jump;

	if (!cvar("run_prestrafe"))
	{
		run_ps_release = FALSE;
		return;
	}

	onground = getstatf(STAT_FS_FLAGS) & FL_ONGROUND;
	jump     = input_buttons & 2;

	if (!onground)
		run_ps_ground = 0;
	else if (!run_ps_ground)
		run_ps_ground = cltime;

	// Rising edge of jump, from a standing start, with W actually held.
	if (jump && !run_ps_jumpheld && input_movevalues_x > 0 &&
	    run_ps_ground && (cltime - run_ps_ground) >= PreStrafe_Dwell())
	{
		run_ps_release = TRUE;
		run_ps_left    = FALSE;
	}
	run_ps_jumpheld = jump;

	if (!run_ps_release)
		return;

	if (!onground)
		run_ps_left = TRUE;
	else if (run_ps_left)
		run_ps_release = FALSE;          // landed: the next hop keeps its W

	if (input_movevalues_x <= 0)
		run_ps_release = FALSE;          // you let go: hand it straight back
	else if (run_ps_release)
		input_movevalues_x = 0;
};

void() CSQC_Input_Frame =
{
	/*
	  BUILD 24: WATCHING A RECORDING SENDS NOTHING.

	  The server pin (rec_watch, MOVETYPE_NONE) is the real freeze and it is what
	  stops gravity, movers and triggers.  This is the half that does not need a
	  round trip: the moment a replay opens, every usercmd leaving this client is
	  empty, so nothing you press between here and the server acknowledging can
	  move you into a start box or off a ledge.

	  First, and unconditionally, so neither of the two below can put a value
	  back -- PreStrafe_InputFrame reads input_movevalues_x and would otherwise
	  latch its release off a key that is not being sent.
	*/
	if (rec_wt_open)
	{
		input_movevalues = '0 0 0';
		input_buttons    = 0;
		return;
	}

	/*
	  BUILD 30: GHOSTING SENDS AN EMPTY USERCMD, NOT NO USERCMD.

	  Superficially the same as the replay branch above and fundamentally its
	  opposite.  A replay wants the body to STOP, and the real freeze is the
	  server pin -- this is only the half that needs no round trip.  A ghost
	  wants the body to KEEP GOING, and because a client of this mod is
	  `isindependant` (sv_user.c:8507), a player advances once per RECEIVED
	  usercmd and never otherwise.  Sending nothing would freeze the body as
	  surely as the pin does.

	  So the cmd still goes, with the movement and buttons emptied and the angles
	  pinned to the aim you left -- msec untouched, which is the field that makes
	  the server tick the body.  Ghost_InputFrame captures the real values first,
	  because they are the flight controls.

	  ABOVE the other two and returning, for the same reason the replay branch
	  is: PreStrafe_InputFrame reads input_movevalues_x and would latch its
	  release off a key that is no longer being sent, and SaveLoc_InputFrame's
	  angle lock is for a mode ghost refuses to coexist with anyway.
	*/
	if (rec_gh_on)
	{
		Ghost_InputFrame();
		return;
	}

	SaveLoc_InputFrame();
	PreStrafe_InputFrame();
};

/*
  Key state for the HUD's key block, and the save-lock keys.

  THE ORDER MATTERS AND IT IS THIS WAY ROUND ON PURPOSE.  Keys_Edge runs
  FIRST and unconditionally, so the key-light block sees every press even for
  a key the save-lock menu is about to consume -- it is an observer and it
  must not develop holes.  Only then is the press offered to the menu.

  Keys_Edge itself never consumes anything (cl_keys.qc's header explains why:
  a TRUE would light the W box and move nobody).  SaveLoc_Key does, for
  exactly the digits it acted on -- see cl_saveloc.qc.
*/
/*
  BUILD 56 REVIEW -- THE RELEASE GATE, and why it lives out here instead of in
  each panel.

  CSQC_KeyPress marks a key down as soon as CSQC SEES the press, whatever CSQC
  returned for it (pr_csqc.c:9307), so the matching release is handed to CSQC as
  well (:9311).  A panel that swallows that release -- returns TRUE -- makes
  Key_Event return at keys.c:3860-3861, before the stored "-duck"/"-jump" runs at
  :3971-3976.  Hold MOUSE1, tap TAB, let go: the leaderboard ate the up, the
  release never ran, and the player stayed crouched until MOUSE1 was pressed and
  released again in game, with the HUD key block lit the whole time.

  ALL FIVE CURSOR PANELS HAD IT, and a per-panel fix does not survive a HAND-OFF:
  the inspector declining an up it never took, and the results card swallowing
  that same up one line later.  So the pairing is kept ONCE, here -- a bit per
  mouse button whose PRESS the chain consumed, and an up whose bit is clear never
  reaches a panel.  It still reaches Keys_Edge and the save-lock at the end of the
  chain, which are as entitled to the edge as they were to the press; returning
  before them would light the key block for good and latch a save-lock hold.

  THE INVARIANT, which is what makes the panels' own "swallowed, so Keys_Edge
  never sees it" comments true rather than exceptions: Keys_Edge and the save-lock
  see BOTH edges of a button or NEITHER.  A press a panel consumed is hidden from
  them, and its paired up is hidden too, because a panel returning TRUE stops the
  chain before them.  An unpaired up is the mirror: they hold no state for a press
  they never saw, so the gate hands them the edge itself.

  ONE MASK, NOT ONE PER DEVICE.  devid is ignored, so two pointing devices could
  cross bits.  The engine pairs per device; nothing in FTESurf reads devid yet.

  NEVER READ THIS MASK AS "the button is physically held".  It records what the
  CHAIN consumed, not what the hand is doing, and the wheel proves the point: a
  notch is a press and a release back to back in the same batch (in_generic.c
  1214-1215, in_sdl.c:1709-1710), so its bit is set and cleared within one input
  batch and is never "held" for any observable time.
*/
float cl_btn_taken;             // CLB_*: buttons whose press the chain consumed
#define CLB_M1   1
#define CLB_M2   2
#define CLB_M3   4
#define CLB_WUP  8
#define CLB_WDN  16

float(float scanx) CL_ButtonBit =
{
	if (scanx == K_MOUSE1)     return CLB_M1;
	if (scanx == K_MOUSE2)     return CLB_M2;
	// MOUSE3 belongs here too: it is the gesture that TAKES the cursor, so its
	// press is consumed by Ev_PassiveKey or Results_PassiveKey -- and since the
	// build-56 review, by Ev_InputEvent as well, which releases the cursor.
	if (scanx == K_MOUSE3)     return CLB_M3;
	if (scanx == K_MWHEELUP)   return CLB_WUP;
	if (scanx == K_MWHEELDOWN) return CLB_WDN;
	return 0;
};

float(float evtype, float scanx, float chary, float devid) CL_InputChain =
{
	/*
	  BUILD 24: a replay gets the event FIRST, and before Keys_Edge sees it.

	  That ordering is an exception to the rule below, and it is the one case the
	  rule cannot survive.  MOUSE1 is bound to +duck and MOUSE2 to +jump, so
	  clicking the scrub bar would light the duck box and clicking the close
	  button would light it again -- an observer that "must not develop holes"
	  would be faithfully reporting keys that are not being sent anywhere,
	  because CSQC_Input_Frame is zeroing the usercmd while a replay is up.
	  Keys_Edge is also the wrong thing to feed during a replay in the first
	  place: the key block is being driven from the .view, not from the keyboard.
	*/
	/*
	  STAGE 2: the leaderboard is offered it before the replay is, and for the
	  same reason with one more on top -- it is drawn OVER the playback chrome,
	  so a click that lands on a run row must not also land on the scrub bar
	  behind it.  The front one wins, which is the rule the gfx and save-lock
	  menus already share below.
	*/
	/*
	  BUILD 31: the layout editor is offered the event before any of them.

	  It is the front-most thing drawn and it is modal -- while it is up the
	  mouse is a cursor and MOUSE1 is a grab, not a duck.  Returning TRUE for
	  IE_MOUSEABS is what stops the view turning under the cursor mid-drag; see
	  its own header for the rest.  It refuses to coexist with the two below, so
	  in practice at most one of these three ever answers.
	*/
	if (ui_he_open)
		if (HUD_EditInputEvent(evtype, scanx, chary, devid))
			return TRUE;

	/*
	  BUILD 56: the entity inspector's cursor, behind the editor and in front of
	  the results card -- the reverse of its place in the draw order, which is
	  after Results_Draw and before HUD_EditDraw.  ui_ev_cursor and not
	  ui_ev_open, for the results card's reason: an overlay merely on screen
	  joins nothing.  It refuses to share the screen with the editor above, the
	  three below, or any other cursor claim, and lets go if one appears.
	*/
	if (ui_ev_cursor)
		if (Ev_InputEvent(evtype, scanx, chary, devid))
			return TRUE;

	/*
	  BUILD 48: the results card, and it sits AHEAD of the leaderboard because it
	  is drawn in front of it.  Input order is the reverse of draw order and the
	  two have to be kept in step by hand; see CSQC_UpdateView.

	  ui_rs_cursor AND NOT ui_rs_open, which is the whole design of this panel.
	  It spends most of its life drawn and passive -- it appears unasked the
	  instant you cross the line, while you may already be walking back to run
	  again -- so a card that entered the chain merely by being on screen would
	  eat the first key you pressed after every single finish.  It joins the chain
	  only once you have asked for the cursor.
	*/
	if (ui_rs_cursor)
		if (Results_InputEvent(evtype, scanx, chary, devid))
			return TRUE;

	if (rec_sb_open)
		if (Scores_InputEvent(evtype, scanx, chary, devid))
			return TRUE;

	if (rec_wt_open)
		if (Watch_InputEvent(evtype, scanx, chary, devid))
			return TRUE;

	if (evtype == IE_KEYDOWN)
	{
		Keys_Edge(scanx, TRUE);

		// Build 48: the two gestures that ASK the passive card for the cursor,
		// plus ESC to dismiss it.  Offered before the two menus below because it
		// answers only F1, MOUSE3 and ESC, and only while a card is actually up.
		if (Results_PassiveKey(scanx))
			return TRUE;
		// Build 56: MOUSE3 takes the inspector's cursor while its overlay is up.
		// After the card on purpose -- the card was there first and keeps MOUSE3
		// whenever one is up AND drawn (hud_results); see Ev_PassiveKey.
		if (Ev_PassiveKey(scanx))
			return TRUE;
		/*
		  The gfx menu is offered the press FIRST, and only while it is open --
		  it shares the digit row with the save-lock menu, and the one that is
		  visible is the one that should answer.  Both being open at once is
		  the user's business; the front one wins and the other keeps its keys
		  the moment you close this.
		*/
		if (Gfx_Key(scanx, TRUE))
			return TRUE;
		return SaveLoc_Key(scanx, TRUE);
	}

	/*
	  THE RELEASE HAS TO GO TO BOTH.  It did not, and that was the whole of the
	  "hold 2 and you glitch, flicker and stick" bug: SaveLoc_Key's key-up
	  branch -- the one that sends sl_holdoff -- could never run, because
	  nothing here ever called it with down=FALSE.  The hold latched on the
	  press and never came off, on either side.

	  The failure was self-sealing, which is why it looked like the load key had
	  broken for good rather than like a hold that would not let go: with the
	  client still believing 2 was held, every later press hit SaveLoc_Key's
	  repeat guard and was swallowed.  Deleting the save released the SERVER --
	  the list shrank out from under the hold -- but not the client, so 2 stayed
	  dead until the map changed.

	  The engine was always delivering this.  keys.c:3219-3225 forwards up
	  events from every state, and CSQC_KeyPress only filters out ups for keys
	  CSQC never saw go down (pr_csqc.c:9162-9165).  We were dropping it.
	*/
	if (evtype == IE_KEYUP)
	{
		Keys_Edge(scanx, FALSE);
		return SaveLoc_Key(scanx, FALSE);
	}

	/*
	  BUILD 13b -- the view lock, done properly: the mouse never moves at all.

	  Build 13 pinned the ANGLES, per usercmd and then also per rendered frame,
	  and it still read as a fight -- because it is one.  The engine keeps
	  accumulating deltas into cl.viewangles and we keep writing them back, so
	  every frame is a correction rather than a lock, and anything sampling the
	  angle between the accumulate and the write-back sees the moved value.

	  Consuming the delta stops it at the source.  CSQC_MouseMove is called with
	  the frame's accumulated mouse movement at in_generic.c:812-817, and a true
	  return ZEROES mx/my right there -- before m_filter, before m_accel, before
	  CL_AdjustAngles ever sees them.  Nothing to correct, because nothing moved:
	  "0 movement", which is what was asked for.

	  IE_MOUSEABS as well, for a tablet or a touch device, where the same
	  motion arrives as a position rather than a delta.

	  The angle pin in SaveLoc_LockAngles stays. It is now belt and braces
	  rather than the mechanism -- CSQC_MouseMove is skipped entirely when
	  cl_indepphysics is running its own thread (the !runningindepphys guard on
	  the same line), and a lock that quietly stopped working in one
	  configuration would be worse than a redundant write in all of them.
	*/
	if (evtype == IE_MOUSEDELTA || evtype == IE_MOUSEABS)
		return rec_sl_holding && rec_sl_holdang_ok;

	return FALSE;
};

// The gate in front of the chain above; its essay is up there.
float(float evtype, float scanx, float chary, float devid) CSQC_InputEvent =
{
	local float bit, took;

	// Key events only: in an IE_MOUSEABS, scanx is an X COORDINATE, and 512 of
	// them along it would otherwise read as K_MOUSE1.
	bit = 0;
	if (evtype == IE_KEYDOWN || evtype == IE_KEYUP)
		bit = CL_ButtonBit(scanx);

	if (bit && evtype == IE_KEYUP)
	{
		if (!(cl_btn_taken & bit))
		{
			/*
			  Its press went to the game, so its release must go there too: return
			  FALSE and keys.c runs the stored "-command".  The panels do not see
			  it; the two observers at the end of the chain still do, in the order
			  the chain gives them.
			*/
			Keys_Edge(scanx, FALSE);
			SaveLoc_Key(scanx, FALSE);
			return FALSE;
		}
		// Ours.  Cleared BEFORE the chain runs and unconditionally, so a panel
		// that closed while the button was held cannot leave a bit stuck.
		cl_btn_taken = cl_btn_taken - bit;
	}

	took = CL_InputChain(evtype, scanx, chary, devid);

	// Recorded on the WHOLE chain's answer, not a single handler's, so the
	// passive-key path (MOUSE3 taking a cursor) pairs the same way.
	if (took && bit && evtype == IE_KEYDOWN)
		cl_btn_taken = cl_btn_taken | bit;
	return took;
};

void(float vwidth, float vheight, float notmenu) CSQC_UpdateView =
{
	local vector scr;

	scr = [vwidth, vheight];

	// Build 13: the view lock, BEFORE the scene is set up.  Input frames run at
	// cl_netfps and this runs at your framerate, so pinning the angles only in
	// CSQC_Input_Frame let four frames in five render from a moved angle -- the
	// bounce.  See SaveLoc_LockAngles.
	SaveLoc_LockAngles();

	// The angle sidecar, AFTER the lock: what belongs in the file is the angle
	// this frame is actually drawn at, not the one the mouse asked for.  Runs
	// whether or not `notmenu` -- a run does not stop while the console is up,
	// and a gap in the sidecar would read as a camera that teleported.
	Rec_ViewFrame();

	// Same lazy-reload idiom Zone_Draw uses: cheap string compare every frame,
	// work only on an actual map change.
	// (Sky_LoadForMap used to be here.  Build 27 moved the whole rule into the
	//  engine as r_skybox_default -- see the essay at the top of this file.)
	if (serverkey("map") != vbsp_decal_map)
		Decal_LoadForMap();

	// Two edges: the server switching this player's fog controller (54 maps do,
	// 397 times), and the player toggling vbsp_fog.  Both are string/float
	// compares that do nothing on the overwhelming majority of frames.
	Fog_Frame();

	/*
	  Patch 207: the portals do NOT use the idiom above, and this is the one
	  place where that difference is load-bearing.

	  The lazy compare bets that serverkey("map") changes after the entity lump.
	  It changes in either order.  When it leads, the load reads the PREVIOUS
	  map's lump, latches the new map's name and never looks again -- which built
	  116 phantom apertures on surf_demise, a map with no portal doors at all,
	  and took it to 11 fps.  Patch 205 documented this transient as harmless
	  because it had only ever seen the other order.

	  The real answer is the entry point the engine already provides for exactly
	  this question: CSQC_WorldLoaded, called once the precaches are done and
	  "gives a chance for the qc to read the entity lump from the bsp"
	  (cl_defs.qc:396).  FTESurf never defined it.  It does now, below.

	  Portal_Poll stays as a safety net for the paths that do not go through
	  CSQC_WorldLoaded -- demo playback among them -- and does nothing at all
	  once the lump has been read and its signature has settled.
	*/
	Portal_Poll();

	/*
	  BUILD 24: advance the replay before the scene is built.

	  Here rather than beside HUD_Draw because the camera has to be set before
	  clearscene's refdef is filled in, and because the HUD reads the values this
	  produces -- so it runs first whether or not `notmenu` is true.  It leaves
	  rec_wt_on false on every frame that is not a replay, and one float test is
	  the entire cost of that.
	*/
	Watch_Frame();

	clearscene();

	setproperty(VF_DRAWENGINESBAR, 0);
	setproperty(VF_DRAWCROSSHAIR, (rec_wt_on || rec_gh_on) ? 0 : 1);

	// The recorded camera, over the top of whatever the engine put in the
	// refdef.  After clearscene, which resets both properties.
	if (rec_wt_on)
		Watch_Camera();

	/*
	  BUILD 30: the ghost camera, and the body it left behind.

	  Here, and unconditionally, because it does two jobs: it flies the camera
	  when detached, and on EVERY frame it captures where the body actually is.
	  That capture has to happen after clearscene -- which refills the refdef
	  from the engine, so VF_ORIGIN is the predicted eye of the real player --
	  and before any override, which is why it cannot live with the HUD.

	  After Watch_Camera so a replay still wins the refdef outright; the two
	  refuse each other on the server anyway, and this is the belt to that
	  braces.
	*/
	Ghost_Frame();

	/*
	  The map's 3D skybox, if it has one.  See cl_decals.qc for where the
	  sky_camera is read and for what this does and does not reproduce.

	  Set every frame rather than once: clearscene() resets the refdef, and
	  skyroom_enabled is part of it.  222 is VF_SKYROOM_CAMERA (pr_common.h:849);
	  it is a real viewproperty but not one the defs dump declares, hence the
	  bare number and this note.
	*/
	if (vbsp_skyroom_have && cvar("vbsp_skyroom"))
	{
		/*
		  BUILD 13b: Source's parallax, which FTE's skyroom does not have.

		      skybox camera = sky_camera.origin + view.origin / scale

		  See the header comment in cl_decals.qc.  `scale` defaults to 16 --
		  every sky_camera in the library that omits the key means 16, and a
		  zero would divide the map into the sky room.
		*/
		local float sksc;
		local vector skeye;
		sksc = vbsp_skyroom_scale;
		if (sksc <= 0)
			sksc = 16;
		skeye = getproperty(VF_ORIGIN);
		setproperty(VF_SKYROOM_CAMERA, vbsp_skyroom_pos + skeye * (1 / sksc));
	}

	addentities(MASK_ENGINE | MASK_VIEWMODEL);

	// Zones go in BEFORE renderscene: R_BeginPolygon queues into the scene,
	// and the default shader is depth-tested, so this is what makes a zone
	// behind a wall correctly disappear behind it.
	Zone_Draw();

	// The map's sprites, in the same window and for the same reason -- these are
	// world objects, and one behind a wall has to be hidden by it.  Costs one
	// string compare on the frames where there is nothing to draw.
	Sprite_Draw();

	// The replay's path, for exactly the same reason and through exactly the
	// same primitive -- a route that drew over the walls would be unreadable.
	if (rec_wt_on)
		Watch_Path();

	// Build 54.  The entity/trigger inspector's volumes, here for the same
	// reason as the three above -- they are world outlines and a box behind a
	// wall should be behind it.  Its LABELS are 2D and are drawn after
	// renderscene by Ev_Labels; this pass queues them.  Costs one float test on
	// the frames it is off, which is nearly all of them.
	Ev_Draw();

	/*
	  Build 49.  Also before renderscene, but for a different reason than the
	  three above: particles are drawn INSIDE renderscene by the engine's own
	  pass, so emitting after it would land a frame late.  VF_ORIGIN is already
	  final here, which is what the distance cull reads.
	*/
	Emit_Frame();

	renderscene();

	// Headless self-check (see menu/m_main.qc's ui_bootcheck).  Reports the
	// two things that can silently blank the whole HUD: `notmenu` arriving
	// false, and the hud_* cvars reading 0.  Kept in two prints because
	// fteqcc caps varargs at 8 and silently drops the rest.
	if (cvar("ui_bootcheck") >= 3 && !vbsp_uv_reported)
	{
		vbsp_uv_reported = TRUE;
		print(sprintf("^2bootcheck/csqc: notmenu=%g scr=%gx%g scale=%g\n",
		              notmenu, vwidth, vheight, cvar("hud_scale")));
		print(sprintf("^2bootcheck/csqc: speed=%g keys=%g debug=%g  speedpos %g,%g\n",
		              cvar("hud_speed"), cvar("hud_keys"), cvar("hud_debug"),
		              vwidth * cvar("hud_speed_x"), vheight * cvar("hud_speed_y")));
	}

	if (notmenu)
	{
		/*
		  Patch 270.  NM_Frame samples the engine's received-delta counters and
		  closes a one-second window; NM_Draw prints it.  Sampling is OUTSIDE the
		  draw so the window keeps advancing even on frames the panel is off --
		  which matters because the counter is free-running and the alternative
		  is a bogus first reading whenever hud_net is switched on mid-session.
		*/
		NM_Frame();

		HUD_Draw(scr);
		NM_Draw(scr);

		/*
		  BUILD 43: the replay's path AGAIN, and this is not a duplicate.
		  hud_watch_path_mode picks which of the two drawers does the work and
		  the other returns immediately, so exactly one of these two calls ever
		  draws anything.

		  The screen-space one has to be after renderscene, because that is what
		  2D means -- and the cost of being there is that it cannot be occluded
		  by the world, which is the trade the essay at Watch_PathMode spells out.

		  AFTER HUD_Draw, and the reason is mechanical rather than aesthetic.  A
		  2D CSQC polygon is not drawn when it is submitted: R_BeginPolygon sets
		  R2D_Flush and the batch is drawn when some later 2D draw call flushes
		  it (pr_csqc.c:1671-1678, CSQC_PolyFlush's twod branch at :1605-1622).
		  Sitting after the HUD guarantees there is such a call.  Before it there
		  may not be, and rather than reason about which of Timer_Draw's or
		  Watch_Draw's first primitive would do the flushing, this takes the
		  position where the question does not arise.

		  It is still before Timer_Draw and the replay chrome, so the panels you
		  actually read stay on top of the line.
		*/
		if (rec_wt_on)
			Watch_Path2D();

		/*
		  Build 54.  The inspector's labels, and they are here for exactly the
		  reason the block above gives: they are 2D, so they have to be after
		  renderscene, and after HUD_Draw so that a later 2D call is guaranteed to
		  flush the batch.  Their positions were projected in Ev_Draw, before
		  renderscene, while the view matrix was set.
		*/
		Ev_Labels();

		// Both read stats only, so they are drawn from here rather than from
		// HUD_Draw: neither is part of the strafe/board layout chain and
		// neither wants hud_* to switch it off.
		/*
		  BUILD 48.  The latch first, then the toast, and both before the panels
		  that can cover them.

		  Results_Frame owns two edges and draws nothing: the finish, which raises
		  the card, and the stage close, which raises the toast.  It runs here
		  rather than inside either draw function because the card can be switched
		  off with hud_results and a detector you can switch off comes back seeded
		  -- it would then pop a card about a run that ended four minutes ago.

		  The toast is drawn beside the split column it belongs with, and NOT with
		  the card down at the bottom of this list: they are mutually exclusive by
		  construction, so nothing is gained by putting them on the same layer and
		  the toast reads better next to the splits it is about.
		*/
		Results_Frame();

		/*
		  BUILD 57, STAGE T: the lobby time store, and it must run AFTER
		  Results_Frame rather than before it.

		  Both watch the server's finish counter.  The card reads what the run was
		  measured against out of the lobby files on disk -- the server zeroes
		  TIMERPBWAS in a lobby -- and this call is what WRITES this run's file
		  into that folder.  Swapped, every lobby card would report "personal best
		  by 0.000" against the run's own time.  It draws nothing.
		*/
		LT_Frame();

		Timer_Draw(scr);
		Results_DrawToast(scr);
		SaveLoc_Draw(scr);
		Gfx_Draw(scr);
		// Reads two cvars the hl2 plugin writes at map load, and self-limits to
		// the first twenty seconds of a map -- see the essay above it.
		Gfx_DrawMissing(scr);

		// The replay's own chrome, LAST, so the scrub bar and the close button
		// sit over the panels rather than under them.
		Watch_Draw(scr);

		// And the leaderboard over THAT: it is opened from inside a replay to
		// pick the next one, so it has to be the front-most thing on screen and
		// the first thing offered a click.  See CSQC_InputEvent.
		Scores_Draw(scr);

		/*
		  BUILD 48: the results card, over the leaderboard and under the editor.

		  In FRONT of the board because it is raised by an event rather than
		  opened by you, so it must not appear behind something you already had
		  up; BEHIND the editor for the reason the editor gives below about
		  drawing outlines around what it edits.  Its entry in CSQC_InputEvent
		  sits one step ahead of the board's to match, and the two orders have to
		  be kept in step by hand.
		*/
		Results_Draw(scr);

		/*
		  BUILD 56: the entity inspector's panel, over the results card and under
		  the editor.  Its place matters for input, not only for looks: sui has
		  one hit-test list and sui_begin empties it, so the LAST bracket drawn in
		  a frame owns the clicks.  The card draws raw until it takes the cursor,
		  and the inspector refuses to hold the cursor alongside the editor, the
		  board, a replay or a card that has taken it -- so whenever this draws,
		  its bracket is that last one.  Its entry in CSQC_InputEvent sits behind
		  the editor's and ahead of the card's to match.
		*/
		Ev_Panel(scr);

		/*
		  BUILD 31: the layout editor, over everything.

		  It has to be last for two independent reasons.  It draws outlines AROUND
		  the panels it is editing, so anything drawn after it would sit inside a
		  box that claims to contain it; and it consumes the rect registry, which
		  is filled by HUD_Draw, Timer_Draw, SaveLoc_Draw and Gfx_Draw above -- it
		  would be editing last frame's layout from anywhere earlier.

		  It refuses to open while a replay or the scoreboard is up and closes
		  itself if one appears, so the two sui_begin/sui_end brackets on this line
		  can never nest.
		*/
		HUD_EditDraw(scr);

		// The save-lock hold's deadman.  Here rather than inside SaveLoc_Draw
		// because it has to run whether or not the menu is up.
		SaveLoc_HoldFrame();
	}
	else
	{
		// The menu and the console eat key events, so a key held while one of
		// them is up never sends us its release.  Nothing is being drawn from
		// this state right now anyway, so drop it and let the next real press
		// rebuild it -- otherwise you come back to a W box lit by a key you
		// stopped holding two minutes ago.
		Keys_Clear();

		// Same argument, but this one is not cosmetic: a save-lock hold whose
		// release went missing would leave the player pinned.
		SaveLoc_Idle();
	}
};

float(string cmd) CSQC_ConsoleCommand =
{
	tokenize(cmd);

	/*
	  `retry` -- restart the map's entities without losing where you are.

	  THE ENGINE HANDS THIS TO US; we do not register it.  `retry` is an engine
	  command (Patch 167) and Cmd_ExecuteString returns the moment one matches,
	  so cmd beats alias beats cvar beats CSQC -- and registercommand refuses a
	  name that already exists, so trying to claim it here would be a silent
	  no-op rather than a shadow.  CL_Retry_f offers it to us instead, and falls
	  through to a plain map_restart if we return FALSE.

	  Which is exactly what `rec_retry 0` does, and why the cvar is tested before
	  anything is written: returning FALSE gives the pre-build-18 behaviour,
	  byte for byte, from one cvar.

	  The ordering is the whole reason this half is client-side.  The sidecar is
	  written HERE, synchronously, before the server is even told -- the restart
	  destroys this VM and the buffer with it, and the server cannot write a
	  file only the client holds.
	*/
	if (argv(0) == "retry")
	{
		if (!cvar("rec_retry"))
			return FALSE;

		Rec_ViewRetry();

		// Build 20: the segment column is the client's too, and it dies with the
		// same VM for the same reason.  Written here, on the same argument.
		Seq_Retry();

		localcmd("cmd rec_retry\n");
		return TRUE;
	}

	/*
	  Re-anchor the energy readout to where you are standing.

	  Normally the anchor is the floor of the start zone of whichever leg you
	  are on, set the moment you stand in it.  On a map with no zone data
	  there is nothing to anchor to and the readout says so; this is the
	  manual way in.  It is also the way to ask "how much have I gained since
	  HERE", which is a different and sometimes more useful question.
	*/
	if (argv(0) == "ui_anchor")
	{
		local vector org;

		// `ui_anchor clear` is the way back out.  Without it a hand-set anchor
		// outranked everything until the next map load, which was tolerable
		// when the alternative was the zones and is not now that the default
		// reference follows your jumps and is the one that matches Momentum.
		if (argv(1) == "clear" || argv(1) == "auto")
		{
			ui_anchor_manual = FALSE;
			print("energy anchor released -- back to hud_energy_ref\n");
			return TRUE;
		}

		/*
		  Build 30: the anchor is where YOU stand, not where the camera is.

		  `ui_anchor` means "measure energy from here", and while ghosting
		  VF_ORIGIN is the flying camera -- so anchoring from up in the air would
		  silently set the zero to a height nobody was ever at, and every energy
		  reading for the rest of the map would be measured from it.  This is a
		  console command rather than a draw path, so it does not even have the
		  excuse of running before the override: it runs outside CSQC_UpdateView
		  entirely and sees whatever the last frame left in the refdef.
		*/
		if (rec_gh_on)
			ui_anchor_z = rec_gh_bodyfeet_z;
		else
		{
			org = getproperty(VF_ORIGIN);
			ui_anchor_z = org_z - getstatf(STAT_VIEWHEIGHT);
		}
		ui_anchor_manual = TRUE;
		print(sprintf("energy anchored at z = %.0f  (`ui_anchor clear` to release)\n",
		              ui_anchor_z));
		return TRUE;
	}

	if (argv(0) == "saveloc")
	{
		// `saveloc release` is the manual way out of a hold, and it exists
		// because a hold that will not let go is the one failure here you
		// cannot escape by playing.  Both sides are cleared, so it also fixes
		// the client-side latch that used to kill the load key outright.
		if (argv(1) == "release")
		{
			SaveLoc_Release();
			localcmd("cmd sl_holdoff\n");
			print("saveloc: hold released\n");
			return TRUE;
		}

		localcmd("cmd sl_list\n");
		return TRUE;
	}

	if (argv(0) == "saveloc_menu")
	{
		rec_sl_open = !rec_sl_open;
		return TRUE;
	}

	// BUILD 14: the renderer settings, in words (cl_gfx.qc).
	// BUILD 33 gave it arguments -- see Gfx_Console.
	if (argv(0) == "gfx_menu")
		return Gfx_Console();

	if (argv(0) == "timer")
	{
		/*
		  BUILD 48 VERIFICATION: the client's own reading of the five build-48
		  stats and of the two tables built from them, printed BEFORE the server
		  is asked, so a stat that never arrived reads 0 here beside a real number
		  in the server's stage close: line.  ui_sp_class[] is the word each split
		  row will draw its mark from (128|64 = the red !, 128|32 = ~, 0 = never
		  told); the results lines are what the card is drawing.  Local, so it
		  prints immediately and ahead of the queued cmd replies.  No cvar.
		*/
		{
			local float i;
			print(sprintf("cl stats: endrec %g endseg %g endst %g endticks %g pbwas %g\n",
			              getstatf(STAT_FS_STAGEENDREC), getstatf(STAT_FS_STAGEENDSEG),
			              getstatf(STAT_FS_STAGEENDST), getstatf(STAT_FS_STAGEENDTICKS),
			              getstatf(STAT_FS_TIMERPBWAS)));
			print(sprintf("cl splits: n %g over %g pend %g\n",
			              ui_sp_n, ui_sp_over, ui_sp_pendword));
			for (i = 0; i < ui_sp_n; i = i + 1)
				print(sprintf("  row %g: kind %g seg %g ticks %g delta %g class %g\n",
				              i, ui_sp_kind[i], ui_sp_seg[i], ui_sp_ticks[i],
				              ui_sp_delta[i], ui_sp_class[i]));
			print(sprintf("cl results: open %g ticks %g pb %g tag %g rank %g of %g\n",
			              ui_rs_open, ui_rs_ticks, ui_rs_pb, ui_rs_tag,
			              ui_rs_rank, ui_rs_of));
			/*
			  BUILD 57: "leg", not "seg", in both places -- ui_rs_leg IS a leg and
			  ui_rs_toastseg now holds one too (cl_results.qc assigns FS_LegOf).
			  A diagnostic that calls a leg a segment reads a correct stage-1 toast
			  as off by one, which is this tree's own recorded failure mode.
			*/
			print(sprintf("cl results: track %g leg %g startseg %g seen %g  toast leg %g ticks %g word %g\n",
			              ui_rs_track, ui_rs_leg, ui_rs_startseg, ui_rs_seen,
			              ui_rs_toastseg, ui_rs_toastticks, ui_rs_toastword));

			/*
			  BUILD 57, STAGE T VERIFICATION.  `mine` is the gate that decides
			  whether a lobby time may be written to this disk at all, and the two
			  numbers behind it are printed beside its answer because the identity
			  they encode -- on a QW server client N is edict N + 1 -- is the one
			  part of cl_lobbytime.qc read off the engine rather than measured
			  here.  Playing normally, mine must read 1; track another player on a
			  lobby, or play back a demo of one, and it must read 0 while the lobby
			  bits stand and the FIN counters keep moving.  That is the whole test,
			  and it needs no build to run.

			  THE STAT IS THREE BITS (LS_LOBBY 1, LS_NOPB 2, LS_NOREC 4), so they
			  are printed apart as well as raw: `lobby 7` is a real lobby keeping
			  nothing, `lobby 1` is lobby_enable on a server that is still writing
			  its own files -- where this client deliberately keeps nothing -- and 0
			  is not a lobby at all.  Printing only the raw number would have made
			  the middle case look like the first.

			  TWO PRINTS, NOT ONE: fteqcc warns past 8 parameters on a varargs
			  call ("More than 8 parameters on varargs function"), and this tree
			  compiles at zero warnings.  The split is along the seam anyway --
			  what the SERVER says, then who the client thinks it is.
			*/
			print(sprintf("cl lobby: stat %g (lobby %g nopb %g norec %g)\n",
			              getstatf(STAT_FS_LOBBY),
			              !!(getstatf(STAT_FS_LOBBY) & LS_LOBBY),
			              !!(getstatf(STAT_FS_LOBBY) & LS_NOPB),
			              !!(getstatf(STAT_FS_LOBBY) & LS_NOREC)));
			print(sprintf("cl lobby: mine %g (localent %g localnum %g) finrec %g finleg %g\n",
			              LT_StatsAreMine(),
			              player_localentnum, player_localnum,
			              getstatf(STAT_FS_FINREC), getstatf(STAT_FS_FINLEG)));
		}
		localcmd("cmd timer\n");
		return TRUE;
	}

	// Where am I.  Answered by the server, because the answer is the player's
	// own origin and v_angle -- which is exactly what setpos writes back, and is
	// not where the camera is while a replay is playing.
	if (argv(0) == "viewpos")
	{
		localcmd("cmd viewpos\n");
		return TRUE;
	}

	if (Watch_ConsoleCommand(cmd))
		return TRUE;

	// +showscores arrives here as a plain console command -- the engine offers
	// TAB's bind to CSQC before it turns its own scoreboard on (sbar.c:788).
	if (Scores_ConsoleCommand(cmd))
		return TRUE;

	// Build 48.  `results` reopens the last card, which is the only way back to
	// it once it has been dismissed -- and the only way to see one at all with
	// hud_results 0.
	if (Results_ConsoleCommand(cmd))
		return TRUE;

	// Build 49.  `emit_list` -- what the map holds, what is emitting, and why
	// the rest is not.  It also prints the particle handles, because "nothing
	// is drawing" is nearly always either a handle of 0 or a cfg that did not
	// parse, and those two have different fixes.
	if (Emit_ConsoleCommand(cmd))
		return TRUE;

	// Build 30.  Registered on the client and forwarded with `cmd rec_ghost`,
	// which is the same shape `replay` and the save-lock verbs use: the work is
	// on the server, but an UNREGISTERED name never reaches
	// SV_ParseClientCommand -- Cmd_ExecuteString offers it to the SSQC
	// server-command hook instead, where `self` is world.  See cl_zones.qc:98.
	if (Ghost_ConsoleCommand(cmd))
		return TRUE;

	// Build 31.  `hud_edit`, `hud_edit status|reset|save|on|off`.
	if (HUD_EditConsoleCommand(cmd))
		return TRUE;

	// Build 54.  `ent_here`, `ent_view`, `ent_reload` -- the trigger and entity
	// inspector.  ent_here forwards `cmd ent_info` to the server for the half
	// the entity lump cannot answer; see cl_entview.qc.
	if (Ev_ConsoleCommand(cmd))
		return TRUE;

	// zone_goto is deliberately NOT registered here: it has to move the
	// player, so it belongs to SSQC, which parses the same zone file with the
	// same code and therefore numbers the zones identically.  Leaving it
	// unregistered lets the console forward it to the server.
	return Zone_ConsoleCommand(cmd);
};
