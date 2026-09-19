/*
===========================================================================
  cl_keys.qc -- what your hands are actually doing, read from the keyboard.

  WHY NOT input_buttons / input_movevalues, WHICH IS WHAT THIS REPLACES.

  Those globals are only ever written inside CSQC_Input_Frame
  (pr_csqc.c:9547-9564, cs_set_input_state), which the engine calls once per
  OUTBOUND COMMAND -- cl_netfps, 66.7 Hz here -- and, when independent physics
  is running, from the physics thread rather than the render thread.  The HUD
  draws per rendered frame, which at 300+ fps is four or five times as often.
  Worse, the buttons inside that command are sampled once per send interval and
  then frozen: CL_AccumlateInput only calls CL_GatherButtons on the first
  accumulate after a clear (`if (!cmd->msec)`, cl_input.c:1771).  So the key
  lights were showing a value resampled at a different rate from the one they
  were drawn at, which is what made them strobe on a held key.

  And +left / +right were unreachable by that route at ANY rate: they have no
  usercmd button bit at all.  They feed CL_AdjustAngles directly
  (cl_input.c:1368-1369) and, with +strafe held, sidemove.  There was nothing
  to read, which is why the two turn bars ended up driven by the mouse instead
  of by the binds -- they were showing the only turn signal available.

  Reading the keyboard fixes both, and is what the HUD's own comment always
  claimed it did: zero latency, because there is no command interval in the way.

  getkeybind(scancode) rather than findkeysforcommand(action):
  findkeysforcommand "only and always returns two values" (cl_defs.qc:1521-1522)
  and cfg/default.cfg binds three separate keys to +duck (CTRL, c, MOUSE1), so
  a two-slot answer would silently drop one.  Asking the other way round has no
  such limit, needs no table to rebuild, and follows a live rebind for free.
===========================================================================
*/

/*
  BUILD 14: the one piece of input state here that is NOT the keyboard's.

  run_prestrafe drops +forward for you on a pre-strafe jump (cl_main.qc), and
  the key block has to say so -- a display that reads the keyboard is precisely
  the display that would keep W lit while the game was not sending it, which is
  worse than not showing it at all.

  Declared here rather than beside the logic that writes it because cl_hud.qc
  compiles before cl_main.qc and a QC global has to exist before the file that
  reads it.  This file is the one about "what is the state of the player's
  input", which this is.
*/
float run_ps_release;            // the game is suppressing +forward right now

/*
  BUILD 40: THE SAVE-LOCK KEY, AND WHY ITS FLAG LIVES HERE TOO.

  cl_saveloc.qc sets this on the key-down edge in CSQC_InputEvent and clears it
  on the key-up, which is a full round trip before STAT_FS_HOLD can answer --
  the press goes out as a client command, the server parks the player, and the
  stat comes back in a snapshot.  For those two or three frames the HUD's stat
  says "not holding" while the velocity behind it has already been replaced by
  the server's zero, and the readouts print a number that describes neither
  state.  The same happens in reverse on the release, for a different reason
  (cl_pred.c's one-frame-stale pmovetype -- see Patch 243).

  So cl_hud.qc has to be able to compare "what the keyboard says" against "what
  the wire says", and cl_progs.src compiles cl_hud.qc BEFORE cl_saveloc.qc.
  A QC global has to exist before the file that reads it, which is the entire
  reason this declaration block is in this file at all.  Written by
  SaveLoc_LoadKey / SaveLoc_Release, read by HUD_UpdateLatch and HUD_DrawDebug.
*/
float rec_sl_holding;            // the load key is down, as of this frame

/*
  BUILD 24: THE REPLAY OVERRIDE, and it lives here for the same reason
  run_ps_release does -- cl_hud.qc and cl_timer.qc read it and cl_watch.qc
  writes it, and cl_watch.qc has to compile LAST because it draws with
  Zone_Line out of cl_zones.qc.  A QC global has to exist before the file that
  reads it, so the declarations come here and nothing else does.

  WHY AN OVERRIDE BLOCK RATHER THAN FAKING THE STATS.  There is no builtin to
  write a stat clientside -- getstatf reads the server's table and nothing in
  CSQC can put a value into it -- so a replay cannot pretend to be the server.
  The alternative was a second copy of the HUD that draws from the file, which
  is the thing that rots: the live panel would gain a column and the replayed
  one would not, and nobody would notice for a build or two.

  So the HUD keeps ONE draw path and gains one question at the top: am I being
  told what to draw, or am I reading it?  Everything below that line is
  untouched, which is why HUD_DrawSpeed and HUD_Key needed no change at all --
  they were already written to take their values as arguments.

  rec_wt_on is the only gate.  It is FALSE for every frame that is not a replay,
  so the cost when nobody is watching is one float test per panel.
*/
float  rec_wt_on;                // a replay is being drawn this frame
vector rec_wt_org;               // FEET, not the eye -- see HUD_Draw
vector rec_wt_vel;
vector rec_wt_gnorm;             // v4: the plane under you, ramp or ground
float  rec_wt_onground;
float  rec_wt_ducked;            // PMF_DUCKED, from the .rec flags column
float  rec_wt_keys;              // the FSI_* mask, from the .view
float  rec_wt_psrel;             // FSI_PSREL split out of it, for KEY_RELEASED
float  rec_wt_ticks;             // the run clock, in ticks
float  rec_wt_state;             // TS_*
float  rec_wt_flags;             // TF_*
float  rec_wt_pb;                // the leg's PB in ticks, or 0
float  rec_wt_track;
float  rec_wt_seg;
float  rec_wt_segs;
float  rec_wt_tickrate;          // the .rec's own `tickrate` header key

/*
  .rec v4 -- what closed build 23's refusal.

  The strafe bar and the board panel were not drawn during a replay because the
  file did not carry a ramp contact or a pre-clip velocity, and deriving one from
  the ground flag would have produced a bar indistinguishable from a measured
  one.  v4 records both.  These four are what the panels read instead of the
  stats they cannot be given.

  rec_wt_v4 is the honest half of it: a v3 file (your surf_aesthetic run, and every
  recording anyone has on disk today) has none of this, and the three panels go
  back to refusing rather than drawing a plausible zero.  One flag, checked once.
*/
/*
  The bottom edge of the playback chrome, in pixels, or 0 when it is not up.

  The timer panel is centred at hud_timer_y 0.035 and the chrome sits across the
  top of the screen, so on any window they overlap -- the run clock and the
  "stage 5/6" line were drawn straight through the scrub bar.  Timer_DrawPanel
  moves down by whatever this says rather than by a constant, because the panel's
  height is now derived from the font and a constant would be wrong again at the
  next hud_scale.  Published by the thing that knows, read by the thing that has
  to avoid it -- the same shape as ui_strafe_bottom, which the board panel
  already stacks under for the same reason.
*/
float  rec_wt_chromebot;

float  rec_wt_v4;                // this recording carries the v4 columns
float  rec_wt_rc;                // run_rampcontact -- flags bit 16
vector rec_wt_wish;              // horizontal wishdir, rebuilt from the usercmd
float  rec_wt_rate;              // playback speed, so the turn rate is per RUN
                                // second rather than per wall second at 4x
float  rec_wt_time;              // the playback position in the .rec's own `t`
                                // domain -- the HUD's frame clock while a replay
                                // is up; see board_now in HUD_Draw

// Patch 383, the pose stream: written by cl_body.qc, read by cl_netmon.qc
// (which compiles before it).  Free-running totals, zeroed per map.
float  spc_hideslot;             // slot+1 of the body NOT to draw this frame, 0 none (spectate writes it)
float  pb_rx_total;              // pose samples received
float  pb_tk_total;              // sum of their tick gaps
float  pb_bf_total;              // body-frames evaluated
float  pb_late_total;            // ...that ran past the newest sample
float  pb_nbodies;               // stream bodies holding a sample, last frame

// Patch 385, spectate: written by cl_spectate.qc's Spec_Frame, read by cl_hud,
// cl_timer, cl_ghost and cl_players, which compile before it.
float  spc_stat;                 // STAT_FS_SPEC as last latched: 0 off, n>0 entnum n, <0 countdown
float  spc_cam;                  // the camera is spectate's this frame
float  spc_hud;                  // the HUD draws the watched player from the spc_h* below
vector spc_hvel, spc_hfeet;
float  spc_hongr, spc_hducked, spc_hkeys;
float  spc_hrun;                 // Body_Run answered: a SPEC sample has arrived
float  spc_htstate, spc_hticks, spc_htrack, spc_htflags;
float  spc_want;                 // entnum asked for, 0 none
float  spc_leaving;              // cltime of a `rec_spec 0` the stat has not answered, 0 none

// Asking, leaving, watching or counting down -- or a stat not latched yet (a raw
// `cmd rec_spec`, a new VM): spectate owns the input and the aim stays put.
float() Spec_Active =
{
	if (spc_stat || spc_want || spc_leaving)
		return TRUE;
	return getstatf(STAT_FS_SPEC) != 0;
};

/*
===========================================================================
  BUILD 43 -- TELLING THE SERVER WHERE A DETACHED CAMERA IS.

  Both of this game's detached cameras -- the replay's and the ghost's -- are
  two setproperty calls over the refdef, and the server is told about neither.
  For MOVEMENT that is the whole point and stays true.  For VISIBILITY it was a
  bug: the server computes which entities to send from the client's own edict,
  so a camera that flies away from a pinned body is sent the entity set the BODY
  can see.  On surf_fiellu that is measurably nothing -- forty-one brush
  entities and every prop, absent until the server stops culling.  The essay and
  the numbers are at SV_ViewEyeAt in sv_saveloc.qc; the receiving end is
  `rec_watchpos` in sv_player.qc.

  HERE RATHER THAN IN EITHER CALLER, for the reason this file's two declaration
  blocks exist at all: cl_ghost.qc and cl_watch.qc both need it and cl_ghost.qc
  compiles first, so it cannot live in cl_watch.qc and must not be written twice.

  THE THROTTLE IS THE WHOLE OF THE DESIGN.  PVS granularity is a visleaf, so
  this wants to be roughly right rather than exact, and a stringcmd per rendered
  frame to say the camera moved forty units would be absurd at 300 fps.  So:
  send when it has moved far enough to plausibly have changed leaf, never more
  often than PVS_MINDT, and once every PVS_MAXDT regardless so the first frame
  after a pause or a scrub is not left describing where the camera used to be.

  128 units is chosen against the map, not the frame rate: it is a third of the
  smallest room worth being wrong about, and at a surf run's 2000 u/s it works
  out to about fifteen sends a second -- which is under the tick rate, on a
  listen server, for a training tool with one player.
===========================================================================
*/
#define PVS_MOVED   128
#define PVS_MINDT   0.05
#define PVS_MAXDT   0.5

vector ui_pvs_last;             // where the server was last told the camera was
float  ui_pvs_at;               // cltime of that telling; 0 = never

void() PVS_Forget =
{
	ui_pvs_last = '0 0 0';
	ui_pvs_at   = 0;
};

void(vector org) PVS_Publish =
{
	local float dt;

	dt = cltime - ui_pvs_at;

	if (ui_pvs_at != 0)
	{
		if (dt < PVS_MINDT)
			return;
		if (dt < PVS_MAXDT)
		if (vlen(org - ui_pvs_last) < PVS_MOVED)
			return;
	}

	ui_pvs_last = org;
	ui_pvs_at   = cltime;

	// %g and not %.2f: a PVS lookup cannot tell the difference and the shorter
	// string is the one that goes over the wire fifteen times a second.
	localcmd(sprintf("cmd rec_watchpos %g %g %g\n", org_x, org_y, org_z));
};

#define FSK_FWD     0
#define FSK_BACK    1
#define FSK_LEFT    2
#define FSK_RIGHT   3
#define FSK_JUMP    4
#define FSK_DUCK    5
#define FSK_TLEFT   6           // +left
#define FSK_TRIGHT  7           // +right
#define FSK_COUNT   8

// How many keys may be held for one action at once.  Three is already used
// (+duck); four leaves room and costs 32 floats.
#define FSK_SLOTS   4

// Scancodes currently held, per action.  0 means the slot is empty -- key 0 is
// K_UNKNOWN and never arrives as a real press.  A SET rather than a counter on
// purpose: a missed key-up (alt-tab, a menu swallowing the release) leaves a
// counter permanently wrong, while a set is repaired by the next press of the
// same key and cleared wholesale by Keys_Clear.
float ui_kdown[FSK_COUNT * FSK_SLOTS];

float(string bind) Keys_Action =
{
	if (bind == "+forward")   return FSK_FWD;
	if (bind == "+back")      return FSK_BACK;
	if (bind == "+moveleft")  return FSK_LEFT;
	if (bind == "+moveright") return FSK_RIGHT;
	if (bind == "+jump")      return FSK_JUMP;
	if (bind == "+duck")      return FSK_DUCK;
	if (bind == "+left")      return FSK_TLEFT;
	if (bind == "+right")     return FSK_TRIGHT;
	return -1;
};

// Patch 385: keys whose bind turns but has no FSK slot (+lookup/+lookdown, or a
// compound "+left; +forward") -- FSI bit order is FSK order and the .view mask is
// written from it; spectate only needs to know one is held.
float ui_klook[FSK_SLOTS];

// c as a whole command anywhere in the bind: after its start, ';' or a space, and
// before its end, ';' or a space.  No tokenize -- `vote key` still reads argv.
float(string b, string c) Keys_BindHas =
{
	local float at, n, pre, post;

	n = strlen(c);
	at = strstrofs(b, c, 0);
	while (at >= 0)
	{
		pre = TRUE;
		if (at > 0)
			pre = (strstrofs(" ;\t", substring(b, at - 1, 1), 0) >= 0);
		post = TRUE;
		if (at + n < strlen(b))
			post = (strstrofs(" ;\t", substring(b, at + n, 1), 0) >= 0);
		if (pre)
		if (post)
			return TRUE;
		at = strstrofs(b, c, at + 1);
	}
	return FALSE;
};

float(string b) Keys_TurnBind =
{
	if (Keys_BindHas(b, "+left") || Keys_BindHas(b, "+right"))
		return TRUE;
	return (Keys_BindHas(b, "+lookup") || Keys_BindHas(b, "+lookdown"));
};

// #342 with its bindmap and modifier arguments (pr_clcmd.c PF_cl_getkeybind).  A
// plain `bind` fills all eight modifier slots, `bind shift+q` one of them, and
// the engine runs the slot for the modifiers held (keys.c:3824, 4108).
string(float keynum, float bindmap, float modifier) getkeybind_mod = #342;
float ui_kmods;                 // held: L/R shift 1/2, alt 4/8, ctrl 16/32 (the chain's own edges)

void(float scan, float down) Keys_ModEdge =
{
	local float b;

	b = 0;
	if (scan == K_LSHIFT)      b = 1;
	else if (scan == K_RSHIFT) b = 2;
	else if (scan == K_LALT)   b = 4;
	else if (scan == K_RALT)   b = 8;
	else if (scan == K_LCTRL)  b = 16;
	else if (scan == K_RCTRL)  b = 32;
	if (!b)
		return;
	if (down)
		ui_kmods = ui_kmods | b;
	else
		ui_kmods = ui_kmods - (ui_kmods & b);
};

// The bind a press of `scan` runs now (keys.h KEY_MODIFIER_*: shift 1, alt 2, ctrl 4).
string(float scan) Keys_BindNow =
{
	local float m;
	local string b;

	m = 0;
	if (ui_kmods & 3)
		m = m | 1;
	if (ui_kmods & 12)
		m = m | 2;
	if (ui_kmods & 48)
		m = m | 4;
	b = getkeybind_mod(scan, 0, m);
	// An unbound right-hand modifier runs its left-hand twin's bind (keys.c:4118-4131).
	if (b == "")
	{
		if (scan == K_RALT)
			b = getkeybind_mod(K_LALT, 0, m);
		else if (scan == K_RCTRL)
			b = getkeybind_mod(K_LCTRL, 0, m);
		else if (scan == K_RSHIFT)
			b = getkeybind_mod(K_LSHIFT, 0, m);
		else if (scan == K_RWIN)
			b = getkeybind_mod(K_LWIN, 0, m);
	}
	return b;
};

// A turn in ANY modifier slot: ui_kmods misses a modifier the engine holds when
// it went down under the console or before a map change.
float(float scan) Keys_TurnAny =
{
	local float m;

	for (m = 0; m < 8; m = m + 1)
		if (Keys_TurnBind(getkeybind_mod(scan, 0, m)))
			return TRUE;
	return Keys_TurnBind(Keys_BindNow(scan));
};

void() Keys_Clear =
{
	local float i;
	for (i = 0; i < FSK_COUNT * FSK_SLOTS; i = i + 1)
		ui_kdown[i] = 0;
	for (i = 0; i < FSK_SLOTS; i = i + 1)
		ui_klook[i] = 0;
};

void(float scan, float down) Keys_LookEdge =
{
	local float i, free;

	free = -1;
	for (i = 0; i < FSK_SLOTS; i = i + 1)
	{
		if (ui_klook[i] == scan)
		{
			if (!down)
				ui_klook[i] = 0;
			return;
		}
		if (free < 0 && !ui_klook[i])
			free = i;
	}
	if (down && free >= 0)
		ui_klook[free] = scan;
};

float(float act) Keys_Held =
{
	local float i, base;

	if (act < 0)
		return FALSE;
	base = act * FSK_SLOTS;
	for (i = 0; i < FSK_SLOTS; i = i + 1)
		if (ui_kdown[base + i])
			return TRUE;
	return FALSE;
};

// Any key bound to +left/+right/+lookup/+lookdown held, as far as its bind ran.
float() Keys_TurnHeld =
{
	local float i;

	for (i = 0; i < FSK_SLOTS; i = i + 1)
		if (ui_klook[i])
			return TRUE;
	if (Keys_Held(FSK_TLEFT))
		return TRUE;
	return Keys_Held(FSK_TRIGHT);
};

void(float scan, float down) Keys_Edge =
{
	local float act, i, base, free;
	local string b;

	if (scan <= 0)
		return;

	b = getkeybind(scan);
	act = Keys_Action(b);
	if (act < 0)
	{
		if (Keys_TurnBind(b))
			Keys_LookEdge(scan, down);
		return;
	}

	base = act * FSK_SLOTS;
	free = -1;

	for (i = 0; i < FSK_SLOTS; i = i + 1)
	{
		if (ui_kdown[base + i] == scan)
		{
			// Already recorded.  A repeat press is a no-op; a release clears it.
			if (!down)
				ui_kdown[base + i] = 0;
			return;
		}
		if (free < 0 && !ui_kdown[base + i])
			free = i;
	}

	// A release of a key we never saw pressed (held through a menu, say) is
	// nothing to do -- the set already says "not held".
	if (down && free >= 0)
		ui_kdown[base + free] = scan;
};
