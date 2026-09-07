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
void() CSQC_WorldLoaded =
{
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

	// Build 30.  The ghost's stand-in models, said out loud once per map for the
	// reason cl_portal.qc:261-266 gives -- setmodel would load them anyway, and
	// fteqcc warns about a model it cannot see precached.  This hook is where
	// precaches belong ("called after model+sound precaches have been
	// executed"), and it is the one place a stray load cannot cost a frame
	// mid-run.
	Ghost_Precache();
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
	HUD_EditRegisterCvars();

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
	// Draw distance in units, 0 = unlimited.  A sprite is culled on its centre
	// less its own radius, so a large glow stays visible past the line.
	registercvar("vbsp_sprite_dist", "0");
	// One-frame dump of the material table and the cull result; clears itself,
	// same idiom as zone_debug.
	registercvar("vbsp_sprite_debug", "0");

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
float(float evtype, float scanx, float chary, float devid) CSQC_InputEvent =
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

	if (rec_sb_open)
		if (Scores_InputEvent(evtype, scanx, chary, devid))
			return TRUE;

	if (rec_wt_open)
		if (Watch_InputEvent(evtype, scanx, chary, devid))
			return TRUE;

	if (evtype == IE_KEYDOWN)
	{
		Keys_Edge(scanx, TRUE);
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
		HUD_Draw(scr);

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

		// Both read stats only, so they are drawn from here rather than from
		// HUD_Draw: neither is part of the strafe/board layout chain and
		// neither wants hud_* to switch it off.
		Timer_Draw(scr);
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

	// zone_goto is deliberately NOT registered here: it has to move the
	// player, so it belongs to SSQC, which parses the same zone file with the
	// same code and therefore numbers the zones identically.  Leaving it
	// unregistered lets the console forward it to the server.
	return Zone_ConsoleCommand(cmd);
};
