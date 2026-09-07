/*
===========================================================================
  GHOST -- look around the map without moving, while your body keeps surfing.
  Build 30.

      ghost              detach / re-attach
      ghost status       where the body is, where the camera is, what is armed
      ghost speed <n>    fly speed, same as the ghost_speed cvar; 0 = noclip's

  WHAT IT IS, AND WHAT IT IS NOT.

  The camera detaches.  The BODY DOES NOT STOP.  It keeps running real physics
  from the velocity it had when you left it -- gravity, friction, ramp clipping,
  pushers and map teleports all keep working on it -- so ghosting mid-ride means
  coming back to a body that has gone wherever a body with no hands goes.  That
  is the feature, not a limitation of it: a mode that froze you would be `replay`,
  which already exists and is a server-side pin.

  WHY THE BODY KEEPS MOVING AT ALL, which is the part that needed checking
  rather than assuming.  This mod does not define SV_RunClientCommand, so its
  clients are `isindependant` (sv_user.c:8507) and sv_phys.c:2531-2565 skips
  them entirely -- a player advances once per RECEIVED USERCMD and never
  otherwise.  So a ghost cannot simply stop sending: it has to keep sending, with
  the inputs emptied.  That is the exact opposite of what a replay does
  (cl_main.qc's CSQC_Input_Frame returns early and sends nothing), and it is why
  this is a handful of lines in the input frame rather than a server mode.

  THE CAMERA IS NOT AN ENTITY.  It is two setproperty calls over the refdef,
  the same mechanism Watch_Camera uses for a replay.  Nothing is spawned, nothing
  is solid, nothing has a touch function -- so "the ghost cannot trigger
  anything" is true by construction rather than by a list of things that were
  remembered to be disabled.  What still has to be suppressed is the BODY, which
  is a real player at a real origin: see the gate in SV_TimerFrame.

  ANGLES, AND WHY THIS IS THE INVERSE OF THE SAVE-LOCK VIEW LOCK.  The essay at
  cl_saveloc.qc:146-153 names the three angle sources and picks VF_CL_VIEWANGLES,
  because a save-lock hold wants the camera AND the usercmd frozen together.  A
  ghost wants them split: the mouse must turn the camera freely (so
  VF_CL_VIEWANGLES is left alone) while the body's aim must not move (so
  input_angles alone is pinned, which pr_csqc.c:4051-4055 writes into cmd->angles
  and nowhere else).  Getting this backwards gives you either a camera that
  cannot look around or a body that keeps aiming where you are looking.

  THE SPLIT HAS A THIRD SIDE, and build 30 missed it: the SERVER can force an
  angle too.  A teleport that snaps you to its destination's yaw arrives as an
  svc_setangle, and the client obeys one by writing the exact value the camera
  is flown with -- so the body being teleported threw the camera.  The forced
  angle belongs to the body's half of the split, and Ghost_SetAngles is where it
  is put there instead.

  THE SERVER STAT IS THE AUTHORITY, not the console command.  rec_gh_on is read
  from STAT_FS_GHOST every frame rather than latched locally when you type
  `ghost`.  One tick of a listen server is 15 ms and nobody can see it, and it
  buys the property that matters: the picture can never disagree with the server
  about whether the zone tests are live.  A client that detached optimistically
  would have a window -- small, but real -- in which it was flying around while
  the server still thought the body's crossings counted.
===========================================================================
*/

float  rec_gh_on;                // mirror of STAT_FS_GHOST -- the authority
float  rec_gh_want;              // what we last asked the server for
vector rec_gh_bodyorg;           // the body's EYE this frame, before the override
vector rec_gh_bodyfeet;          // and its feet, which is what the model sits on
vector rec_gh_bodyang;           // the aim the body is pinned at
vector rec_gh_camorg;            // where the camera has flown to
vector rec_gh_move;              // input_movevalues, captured before it is zeroed
float  rec_gh_buttons;           // input_buttons, same
float  rec_gh_lastt;             // cltime of the previous ghost frame
entity rec_gh_body;              // the drawn stand-in, spawned once
float  rec_gh_angsnaps;          // forced view angles absorbed this map

// Quake's jump button.  BTN_DUCK (8) is already named in sh_defs.qc, beside the
// note that FTE fills it from +button4; there is no name for this one there
// because nothing else in the mod has needed to read it.
#define GH_BTN_JUMP 2

/*
  +speed -- bit 7, pmove.h's BUTTON_SPEED.  The same bit PMSrc_NoClipMove reads
  to double noclip's fly speed (pm_source.c:2626).

  It only ARRIVES if in_speedbutton is set, because bit 7 is also +button8 and
  the engine will not fold the two together without being told to
  (cl_input.c:1317).  cfg/default.cfg sets it and has to: pm_walkspeed is the
  Source walk key and needs the same bit, so a build where this is clear has no
  walk key either.  Ghost inherits that dependency rather than adding one.

  Note what the key MEANS either side of the detach, because it is not the same
  thing and that is deliberate in the engine as well: on the body +speed WALKS
  you (pm_walkspeed 0.52), and in noclip it SPRINTS you.  Ghost is the noclip
  half.  Nothing leaks across -- Ghost_InputFrame zeroes input_buttons before
  the usercmd is sent, so the body never sees the key at all while you are out.
*/
#define GH_BTN_SPEED 128

void() Ghost_RegisterCvars =
{
	registercommand("ghost");

	/*
	  FLY SPEED, and 0 means "whatever noclip does".

	  BUILD 30 SHIPPED A FLAT 900 AND AN ESSAY EXPLAINING WHY THERE WAS NO
	  MODIFIER KEY.  Both were wrong the same way.  A ghost is a noclip you can
	  leave your body behind in, and "how fast does it fly" was settled in the
	  engine long before this file existed: PMSrc_NoClipMove flies at
	  pm_noclipspeed * sv_maxspeed and doubles it while +speed is held
	  (pm_source.c:2624-2628).  With FTESurf's numbers that is 4 * 260 = 1040
	  u/s, 2080 held.  900 was a number picked in this file and nowhere else, so
	  the two ways of crossing a map felt different for no reason anybody could
	  have found from either end.

	  0 tracks the server's pair, so it follows a map or a server that changes
	  them.  A positive ghost_speed overrides outright and `ghost speed 0` puts
	  it back on the leash; the +speed doubling applies to both, because the
	  engine doubles its FACTOR rather than its base and an override is a base.
	*/
	registercvar("ghost_speed", "0");

	// The stand-in's translucency.  It is YOUR body and you are looking at it
	// from outside, so it wants to read as present rather than solid.
	registercvar("ghost_body",  "1");
	registercvar("ghost_alpha", "0.55");
};

/*
  The body's model, swapped on the duck state.

  Two files rather than one scaled model, because the hulls are two different
  SHAPES and not two sizes of one: 32x32x72 standing, 32x32x54 ducked, same
  footprint.  A uniform .scale -- which is the only scale a CSQC entity has --
  would take the width down with the height and draw a body narrower than the
  one you actually collide with.  tools/mkplayermodel.py cuts both from one
  description so they cannot drift.
*/
string() Ghost_Model =
{
	if (getstatf(STAT_FS_PMFLAGS) & PMF_DUCKED)
		return "models/player_duck.iqm";
	return "models/player.iqm";
};

/*
  Said out loud for the reason cl_portal.qc:261-266 gives: setmodel would load
  it anyway, and a model the code depends on should be named where the map loads
  rather than discovered mid-run.

  THIS HUNG THE CLIENT AT MAP LOAD UNTIL THE MODEL'S MATERIAL WAS RENAMED, and
  the trail is worth keeping because the symptom pointed at the wrong thing.

  The hand-made model this replaces carried the material name "player".  That is
  also the name of QUAKE'S OWN PLAYER SKIN, so it does not resolve to the .tga
  sitting beside the model -- it goes to FTE's shader for player.mdl, which asks
  for player_norm, player_pants and player_shirt, none of which exist here, and
  each of which is then searched for across every wad and replacement path in
  12 searchpaths and ~86,000 indexed files.  Doing that from CSQC_WorldLoaded
  froze the client: on surf_kitsune, twice, the log reached `portal doors: 18
  linked` (the line immediately before this call), rendered one more frame and
  stopped -- responding, no CPU, no error, no QC fault.

  Two experiments settled it, in this order:

      precache on, material "player"          hung at map load, twice
      precache OFF, material "player"         ran to completion -- so it was
                                              this call, not the model
      precache on, material "models/player"   ran to completion, and the four
                                              "did not resolve from any wad or
                                              replacement" lines went with it

  So the fix is in tools/mkplayermodel.py, not here: a material containing '/'
  is taken verbatim rather than being resolved against the shader scripts and
  the wads, so "models/player" finds models/player.tga directly.  See the essay
  beside MATERIAL there.

  The moral, since the first diagnosis in this comment was wrong for an hour:
  "precache_model hangs in CSQC_WorldLoaded" was the obvious reading of the
  bisect and it was not the cause.  The call was only ever the thing that made a
  bad NAME expensive at a bad moment.
*/
void() Ghost_Precache =
{
	precache_model("models/player.iqm");
	precache_model("models/player_duck.iqm");
};

/*
  Draw the body you left behind.

  addentity() rather than a .drawmask and addentities(): the entity is wanted on
  exactly the frames this is called from and on no others, and a drawmask is a
  second piece of state that can be left set.  With addentity there is no state
  to leave set -- not calling it IS not drawing it.

  YAW ONLY.  player.iqm's nose is on +X, which is FTE's forward, so a bare yaw
  points it correctly with no fixup (verified: there is no angle correction
  anywhere in this tree, and the model's own vertices put the apex at +23.255).
  Pitch is deliberately dropped: FTE pitch-scales alias models on the player
  path, and a body that leans back as you look up is not what a stand-in is for.
*/
void() Ghost_DrawBody =
{
	if (!cvar("ghost_body"))
		return;

	if (!rec_gh_body)
		rec_gh_body = spawn();

	setmodel(rec_gh_body, Ghost_Model());
	setorigin(rec_gh_body, rec_gh_bodyfeet);

	rec_gh_body.angles = [0, rec_gh_bodyang_y, 0];
	rec_gh_body.alpha  = cvar("ghost_alpha");
	rec_gh_body.colormod = '1 1 1';

	addentity(rec_gh_body);
};

/*
  Once per outgoing usercmd, from CSQC_Input_Frame.

  The capture has to happen BEFORE the zeroing, and that is the whole trick for
  the flight controls: input_movevalues is what the ENGINE built out of whatever
  the player has bound, already resolved through cl_forwardspeed and friends.
  Reading it beats walking the key table, because it needs no second opinion
  about which keys mean forward -- a rebind, a controller, anything the engine
  can turn into a move, this sees.

  msec is untouched, which is the line that makes the body keep simulating.  A
  usercmd with no movement and no buttons is still a usercmd, and the server
  advances the player once per one of those.
*/
void() Ghost_InputFrame =
{
	rec_gh_move    = input_movevalues;
	rec_gh_buttons = input_buttons;

	input_movevalues = '0 0 0';
	input_buttons    = 0;

	// The body's aim, frozen where you left it.  NOT VF_CL_VIEWANGLES: the
	// camera has to keep turning.  See the header.
	input_angles = rec_gh_bodyang;
};

/*
  What noclip would do here, unless ghost_speed overrides it.  See the essay
  beside the cvar.

  serverkeyfloat rather than cvar(), for the reason cl_hud.qc:1598 and
  cl_board.qc:1629 already read sv_maxspeed that way: these are the SERVER's
  numbers, and reading the local cvar only happens to work because the listen
  server is in this process.  pm_noclipspeed is CVAR_SERVERINFO in the engine
  (sv_phys.c:101) precisely so that a client can see it.

  The fallbacks are the engine's own defaults, not guesses: PM_RUN_SPEED is
  sh_defs.qc's copy of sv_maxspeed and 4 is pm_noclipspeed's default.
*/
float() Ghost_SpeedBase =
{
	local float sp, ms, nc;

	sp = cvar("ghost_speed");
	if (sp > 0)
		return sp;

	ms = serverkeyfloat("sv_maxspeed");     if (ms <= 0) ms = PM_RUN_SPEED;
	nc = serverkeyfloat("pm_noclipspeed");  if (nc <= 0) nc = 4;
	return ms * nc;
};

/*
  Fly the camera.  Called from CSQC_UpdateView, after clearscene() -- which is
  what makes getproperty(VF_ORIGIN) the engine's own predicted eye for the body
  rather than last frame's override.
*/
void() Ghost_Frame =
{
	local float now, dt, sp, fwd, side, back, f, s, u, eye;
	local vector ang, wish;

	now = cltime;
	dt  = now - rec_gh_lastt;
	if (dt < 0 || dt > 0.5)         // first frame, or a hitch
		dt = 0;
	rec_gh_lastt = now;

	/*
	  THE STAT, EVERY FRAME.  A rising edge here is where the detach actually
	  happens -- not where `ghost` was typed -- so the camera and the aim pin are
	  seeded from the frame the server agreed on.
	*/
	if (getstatf(STAT_FS_GHOST))
	{
		if (!rec_gh_on)
		{
			rec_gh_on     = TRUE;
			rec_gh_camorg = getproperty(VF_ORIGIN);
			rec_gh_bodyang = getproperty(VF_CL_VIEWANGLES);
			rec_gh_move    = '0 0 0';
			rec_gh_buttons = 0;
		}
	}
	else if (rec_gh_on)
	{
		rec_gh_on = FALSE;

		/*
		  Coming back, the view goes to the body's aim rather than to wherever
		  the camera happened to be pointing.  Without this you re-attach looking
		  at the sky you were just admiring, which reads as the game having
		  spun you round.
		*/
		setproperty(VF_CL_VIEWANGLES, rec_gh_bodyang);
	}

	// The body's own position is wanted whether or not we are ghosting: the HUD
	// reads it (see HUD_Draw) and it is what the stand-in is drawn at.
	rec_gh_bodyorg = getproperty(VF_ORIGIN);
	eye = getstatf(STAT_VIEWHEIGHT);
	rec_gh_bodyfeet = rec_gh_bodyorg - [0, 0, eye];

	if (!rec_gh_on)
		return;

	/*
	  Direction from the CAMERA's angles, magnitude from the captured usercmd.

	  Normalised as a whole rather than per axis, so that diagonal flight is not
	  1.41x faster than straight and so the speed does not depend on what
	  cl_forwardspeed happens to be -- only its sign and relative size are used.

	  EACH AXIS BY ITS OWN CVAR, though, because "relative size" is the one thing
	  this does read: cl_sidespeed and cl_backspeed are separate settings and a
	  config where they differ would otherwise fly its diagonals off-axis.  All
	  three are 450 in cfg/default.cfg, so this changes nothing today and stops
	  being silently wrong for anyone who moves one.
	*/
	fwd  = cvar("cl_forwardspeed"); if (fwd  < 1) fwd  = 450;
	side = cvar("cl_sidespeed");    if (side < 1) side = fwd;
	back = cvar("cl_backspeed");    if (back < 1) back = fwd;

	f = rec_gh_move_x / ((rec_gh_move_x < 0) ? back : fwd);
	s = rec_gh_move_y / side;

	u = 0;
	if (rec_gh_buttons & GH_BTN_JUMP) u = u + 1;
	if (rec_gh_buttons & BTN_DUCK)    u = u - 1;

	ang = getproperty(VF_CL_VIEWANGLES);
	makevectors(ang);

	wish = v_forward * f + v_right * s + '0 0 1' * u;
	if (vlen(wish) > 0.001)
		wish = normalize(wish);

	/*
	  +speed doubles it, which is what PMSrc_NoClipMove does with the same bit.
	  Applied to the resolved speed rather than to the noclip factor alone, so
	  that an explicit ghost_speed keeps its modifier instead of quietly losing
	  it -- the engine's Patch 171 note makes the same argument about staying
	  independent of whatever else is scaling the number.
	*/
	sp = Ghost_SpeedBase();
	if (rec_gh_buttons & GH_BTN_SPEED)
		sp = sp * 2;

	rec_gh_camorg = rec_gh_camorg + wish * sp * dt;

	// The detach itself.  VF_ANGLES is deliberately NOT set: the engine already
	// filled it from viewangles, which the mouse is still driving.
	setproperty(VF_ORIGIN, rec_gh_camorg);

	/*
	  BUILD 43: and tell the server where it went, so the entities it sends are
	  the ones around the CAMERA and not the ones around the body it left behind.
	  Milder here than in a replay -- the body is still moving, so the stale PVS
	  at least drifts with it, which is why the report came from the replay and
	  not from this -- but it is the same defect and it is two lines.  Throttled;
	  see PVS_Publish in cl_keys.qc.
	*/
	PVS_Publish(rec_gh_camorg);

	Ghost_DrawBody();
};

/*
  A FORCED VIEW ANGLE ARRIVED WHILE THE CAMERA IS DETACHED.  Build 32.

  THE BUG: touch a trigger_teleport while ghosting and the CAMERA spun, from
  wherever in the map you had flown it to.  Everything about that snap is
  correct except who it happened to.  A teleport whose destination is a yaw
  marker aims you at it -- trigger_teleport_touch writes .v_angle and sets
  .fixangle, and the essay at sv_entities.qc:769 records how much work it took
  to make that fire at all -- and the engine turns fixangle into an svc_setangle
  the client obeys by overwriting cl.playerview.viewangles.  The ghost camera IS
  cl.playerview.viewangles.  The mouse drives it and nothing else does, because
  Ghost_Frame deliberately leaves VF_CL_VIEWANGLES alone; see the header.  So
  the body's teleport threw the camera.

  THE FIX IS NOT TO SUPPRESS THE SNAP.  It is to deliver it to the thing it was
  addressed to.  Ghost already splits the two angle sources -- camera on
  VF_CL_VIEWANGLES, body on input_angles -- and rec_gh_bodyang is the body's
  half, the value Ghost_InputFrame pins the usercmd to and the value the camera
  is handed back on re-attach.  Land the forced angle there and the camera never
  moves, the body's aim follows the map, and you come back facing the way the
  teleport meant you to face.  That is more than "make it not so": the map's
  intent survives the ghost instead of being thrown away along with the spin.

  It also settles itself on the server without a second mechanism.  The next
  usercmd carries the new rec_gh_bodyang, .v_angle is derived from it, and the
  server and the client agree again one tick later -- which is why there is no
  matching branch in trigger_teleport_touch.  Suppressing it there would have
  been the same one-line effect and would have thrown the aim away.

  CSQC_Parse_SetAngles IS THE ONE PLACE THEY ALL ARRIVE, which is the other
  reason not to patch the teleport: svc_setangle in both its snap and its
  relative form, svcfte_setangledelta, and the fixangle carried inside the
  player's own delta all funnel through it (cl_parse.c:7604, :7898, :7934,
  :9888, :9900).  A true return suppresses both the viewangles write and the
  frame's fixangles latch; a false return is the engine's behaviour to the
  letter, which is what every frame that is not ghosting gets, including every
  spawn and every ordinary teleport.

  `isdelta` IS LOAD-BEARING, AND THE FIRST VERSION OF THIS FUNCTION SAID IT WAS
  NOT.  The comment it replaced argued that every form hands us an absolute
  angle because the delta forms have "already added themselves to viewangles
  before the call".  Both halves are true and the conclusion drawn from them is
  wrong, in a way only ghosting can expose: they add themselves to VIEWANGLES,
  and while the camera is detached viewangles is the CAMERA.  The server
  computed that delta against the BODY's aim.  Adding it to the camera's
  produces an angle that belongs to neither.

  The b32a run measured it rather than reasoning about it.  Asking a detached
  body for yaw 315 with a body at 44 and a camera at -160 put the aim at -250,
  which is -160 + (315 - 44): the delta, correct, applied to the wrong
  reference.  Absolute would have given -45.  So the delta is recovered by
  subtracting the reference the engine used and re-applied to the one it was
  meant for, and only the non-delta forms are taken verbatim.

  The hook exists because this mod's csprogs is its own.  pr_csqc.c:235 clears
  it outright -- "too evil" -- under csqc_nogameaccess, which is the untrusted
  downloaded-CSQC path and not ours.
*/
float(float a) Ghost_NormAngle =
{
	// -> [-180, 180].  Deltas accumulate across a run of teleports and the two
	// aim rows are read side by side; neither wants a yaw that has wound up.
	return a - 360 * rint(a / 360);
};

vector(vector ang) Ghost_NormAngles =
{
	return [Ghost_NormAngle(ang_x), Ghost_NormAngle(ang_y), Ghost_NormAngle(ang_z)];
};

float(vector newang, float isdelta) Ghost_SetAngles =
{
	local vector d;

	if (!rec_gh_on)
		return FALSE;

	if (isdelta)
	{
		d = newang - getproperty(VF_CL_VIEWANGLES);
		rec_gh_bodyang = Ghost_NormAngles(rec_gh_bodyang + d);
	}
	else
		rec_gh_bodyang = Ghost_NormAngles(newang);

	rec_gh_angsnaps = rec_gh_angsnaps + 1;
	return TRUE;
};

/*
  Ask the server.  One verb with an argument, following rec_watch rather than the
  sl_hold/sl_holdoff pair -- sv_player.qc:414-429 argues the distinction, and a
  ghost is on the `rec_watch` side of it: a mode held for minutes, whose two edges
  are typed seconds apart, and which wants `cmd rec_ghost 0` to exist as a way out
  if a client ever fails to send its own.
*/
void(float on) Ghost_Request =
{
	rec_gh_want = on ? TRUE : FALSE;
	localcmd(sprintf("cmd rec_ghost %g\n", rec_gh_want));
};

void() Ghost_Status =
{
	print(sprintf("ghost: %s (asked for %s)\n",
	              rec_gh_on ? "^5on^7" : "off",
	              rec_gh_want ? "on" : "off"));
	print(sprintf("  body   %.1f %.1f %.1f  feet, yaw %.1f\n",
	              rec_gh_bodyfeet_x, rec_gh_bodyfeet_y, rec_gh_bodyfeet_z,
	              rec_gh_bodyang_y));
	/*
	  The camera's own aim, beside the body's, because the two being ABLE to
	  disagree is the whole of the angle split and there was no way to see it.
	  A forced angle that lands on the body must leave this row alone; one that
	  escaped into the camera shows up here as the two rows moving together.
	*/
	local vector cang;
	cang = getproperty(VF_CL_VIEWANGLES);
	print(sprintf("  camera %.1f %.1f %.1f  yaw %.1f pitch %.1f  %s\n",
	              rec_gh_camorg_x, rec_gh_camorg_y, rec_gh_camorg_z,
	              cang_y, cang_x,
	              rec_gh_on ? "detached" : "(stale -- attached)"));
	/*
	  The speed row says where the number CAME FROM, not just what it is.  0 vs
	  a positive ghost_speed are two different modes reading the same cvar, and
	  "1040" alone cannot tell you whether the server's pair is being followed
	  or an override happens to agree with it.
	*/
	print(sprintf("  speed %g u/s, %g with +speed  (%s)\n",
	              Ghost_SpeedBase(), Ghost_SpeedBase() * 2,
	              (cvar("ghost_speed") > 0)
	                  ? "ghost_speed override"
	                  : sprintf("noclip: %g x %g",
	                            serverkeyfloat("pm_noclipspeed"),
	                            serverkeyfloat("sv_maxspeed"))));
	print(sprintf("  +speed %s   angles absorbed %g\n",
	              (rec_gh_buttons & GH_BTN_SPEED) ? "^5held^7"
	                                             : (cvar("in_speedbutton") ? "up" : "^1UNREADABLE^7 (in_speedbutton 0)"),
	              rec_gh_angsnaps));
	print(sprintf("  model %s   body %s alpha %g\n",
	              Ghost_Model(),
	              cvar("ghost_body") ? "on" : "off", cvar("ghost_alpha")));
	print(sprintf("  timer %s, flags %g\n",
	              (getstatf(STAT_FS_TIMERSTATE) == TS_RUNNING) ? "running" : "not running",
	              getstatf(STAT_FS_TIMERFLAGS)));
};

float(string cmd) Ghost_ConsoleCommand =
{
	/*
	  tokenize FIRST.  `cmd` is the whole command LINE, not the verb -- so a bare
	  string compare against "ghost" fails the moment anything is typed after it,
	  and argv() without this reads whatever was last tokenized by somebody else.
	  Watch_ConsoleCommand is the model here, and it is the right one to copy:
	  Scores_ConsoleCommand reads argv(0) with no tokenize because +showscores
	  never carries arguments, which is true for it and not for this.
	*/
	tokenize(cmd);

	if (argv(0) != "ghost")
		return FALSE;

	if (argv(1) == "status")
	{
		Ghost_Status();
		return TRUE;
	}

	if (argv(1) == "speed")
	{
		if (argv(2) != "")
		{
			/*
			  localcmd IS DEFERRED -- it appends to the command buffer, which
			  does not run until this function has returned, so printing here
			  would read back the value we are in the middle of replacing and
			  report every change one change late.  Queueing the bare form
			  BEHIND the seta prints from the far side of it instead, in order,
			  through the same dispatch.
			*/
			localcmd(sprintf("seta ghost_speed %s\n", argv(2)));
			localcmd("ghost speed\n");
			return TRUE;
		}

		if (cvar("ghost_speed") > 0)
			print(sprintf("ghost_speed %g u/s (override; 0 follows noclip)\n",
			              cvar("ghost_speed")));
		else
			print(sprintf("ghost_speed 0 -- following noclip: %g u/s (pm_noclipspeed %g x sv_maxspeed %g)\n",
			              Ghost_SpeedBase(),
			              serverkeyfloat("pm_noclipspeed"),
			              serverkeyfloat("sv_maxspeed")));
		return TRUE;
	}

	if (argv(1) == "on")       { Ghost_Request(TRUE);  return TRUE; }
	if (argv(1) == "off")      { Ghost_Request(FALSE); return TRUE; }

	// Bare `ghost` toggles.  Against what we ASKED for rather than against the
	// stat, so a double tap inside one round trip does not send the same edge
	// twice and sit there looking broken.
	Ghost_Request(!rec_gh_want);
	return TRUE;
};
