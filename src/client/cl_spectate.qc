/*
===========================================================================
  cl_spectate.qc -- watching another player.  Patch 385.

  The server holds your body and owns the countdown (Patches 380/382:
  `cmd rec_spec <entnum>`, STAT_FS_SPEC, sv_saveloc.qc SV_Spec*).  This file is
  the camera, the keys and the HUD override; the watched body comes from the
  pose stream (cl_body.qc, Body_Pose).  The stat is the authority: the camera
  follows it, never the request.

  EVIDENCE: nothing here writes VF_CL_VIEWANGLES or input_angles.  The camera has
  its own angles, integrated from the raw counts of IE_MOUSEDELTA (swallowed, so
  CL_AdjustAngles never sees them), and turn keys are swallowed -- the body's aim
  cannot move in the window, and the way back needs no restore.  The .hid gets
  `spec 1|0` notes; the .view needs nothing (TF_FROZEN stops its sampling).

      spectate <name>|#slot        watch (a room-list row click does the same)
      spectate off|next|prev       ESC, MOUSE1, MOUSE2 while watching
      spectate mode first|third|free   SPACE cycles them
      spectate status              spectate look <dx> <dy> is in cl_main.qc
      spec_trace <frames>          one `spt` line per frame (Spec_Trace)
===========================================================================
*/

#define SPM_FIRST   0
#define SPM_THIRD   1
#define SPM_FREE    2

#define SPB_M1      1           // spc_kheld: presses spectate took (auto-repeat, the paired up)
#define SPB_M2      2
#define SPB_SPC     4

#define SPEC_WAIT   2           // s an unanswered request (or leave) stays pending
#define SPEC_HALF   0.12        // s, third person: ease-out half-life
#define SPEC_HIDE   24          // third person: nearer than this hides the target

float  spc_mode;                // SPM_*; kept for the map
float  spc_wantat;              // spc_want, spc_leaving, Spec_Active: cl_keys.qc
float  spc_kheld;
float  spc_lastt;
vector spc_camorg;              // the camera, all modes (first person tracks the eye)
vector spc_camang;              // third/free: the mouse's angles
float  spc_dcur;                // third person: drawn distance
float  spc_clr;                 // third person: the drawn camera's box reaches the pivot clean
float  spc_allow;               // third person: the distance the map allows this frame
vector spc_move;                // the usercmd, captured before it is zeroed (freecam)
float  spc_btn;
vector spc_tfeet, spc_tang;     // the watched body's last pose
float  spc_teye, spc_tbp;
float  spc_eyeclaim;            // freecam has claimed the server's PVS eye
float  spc_goat;                // cltime the countdown ended
float  spc_nlook;               // mouse events integrated
float  spc_trn;                 // spec_trace frames left
string spc_flash;
float  spc_flashat;

void() Spec_RegisterCvars =
{
	registercommand("spectate");
	registercommand("spec_trace");
	registercvar("spec_dist", "110", CVAR_ARCHIVE);     // third person, units
	registercvar("spec_notrace", "0");                  // harness control: no pull-in
};

void(string s) Spec_Flash =
{
	if (spc_flash != "")
		strunzone(spc_flash);
	spc_flash = strzone(s);
	spc_flashat = cltime;
	print(strcat("^3spectate:^7 ", s, "\n"));
};

string(float m) Spec_ModeName =
{
	if (m == SPM_THIRD) return "third person";
	if (m == SPM_FREE)  return "free camera";
	return "first person";
};

// The watched body's pose into spc_t*; your own eye until it has one.
void(float slot) Spec_Pose =
{
	local vector o, a, v;
	local float e, bp;

	o = '0 0 0';  a = '0 0 0';  v = '0 0 0';  e = 0;
	bp = Body_Pose(slot, o, a, e, v);
	if (!bp)
	{
		if (spc_tbp)
			return;                 // keep the last pose it had
		o = rec_gh_bodyfeet;
		a = getproperty(VF_CL_VIEWANGLES);
		e = getstatf(STAT_VIEWHEIGHT);
	}
	spc_tfeet = o;
	spc_tang  = [a_x, a_y, 0];
	spc_teye  = e;
	spc_tbp   = bp;
	spc_hvel  = (bp & BP_VEL) ? v : '0 0 0';
};

// Back to the server's steering (sv_saveloc.qc SV_SpecEyeSteer).
void() Spec_EyeRelease =
{
	if (spc_eyeclaim)
		localcmd("cmd rec_watchpos\n");
	spc_eyeclaim = FALSE;
	PVS_Forget();
};

void(float m) Spec_SetMode =
{
	if (m == spc_mode)
		return;
	if (spc_mode == SPM_FREE)
		Spec_EyeRelease();
	if (spc_stat > 0)
	{
		// Out of first person the mouse starts from the target's view, so nothing
		// jumps; third glides out from the eye.  third -> free keeps the camera.
		if (spc_mode == SPM_FIRST)
			spc_camang = [bound(-80, spc_tang_x, 80), spc_tang_y, 0];
		if (m == SPM_THIRD)
			spc_dcur = 0;
	}
	spc_mode = m;
};

void(float dx, float dy) Spec_Look =
{
	local float s, lim;
	local vector ps, vs;

	spc_nlook = spc_nlook + 1;
	if (spc_mode == SPM_FIRST)
		return;
	// IN_MoveMouse's terms (in_generic.c: yaw -= m_yaw * x, pitch += m_pitch * y,
	// each times sensitivity, r_xflip after); m_filter and m_accel are not copied.
	// CSQC_MouseMove hands over virtual pixels (pr_csqc.c:9359): back to counts.
	ps = getproperty(VF_SCREENPSIZE);
	vs = getproperty(VF_SCREENVSIZE);
	if (vs_x > 0)
	if (vs_y > 0)
	{
		dx = dx * ps_x / vs_x;
		dy = dy * ps_y / vs_y;
	}
	s = cvar("sensitivity");
	if (cvar("leftisright"))            // r_xflip's console name (renderer.c:609)
		dx = -dx;
	lim = (spc_mode == SPM_THIRD) ? 80 : 89;
	spc_camang_y = Ghost_NormAngle(spc_camang_y - dx * s * cvar("m_yaw"));
	spc_camang_x = bound(-lim, spc_camang_x + dy * s * cvar("m_pitch"), lim);
};

// A bare "-left" clears both key slots (cl_input.c KeyUp_Scan, k < 0) and the
// physical up is then ignored: a turn held into the window by any route -- the
// menu's Keys_Clear, a console +left, a raw `cmd rec_spec` -- stops here.  Every
// frame of the window (Spec_Edges).  Not -mlook: with lookspring it drifts the pitch.
void() Spec_TurnRelease =
{
	localcmd("-left\n-right\n-lookup\n-lookdown\n-klook\n-rollleft\n-rollright\n");
};

// What a key may run while spectating: the free camera's movement, chat, the
// board, the menus and votes, and the default binds that end the window on the
// server (noclip: "move"; `say !r`: "retry").  Anything else -- an alias, +klook,
// a roll, force_centerview -- could turn the held aim, so its press is swallowed.
#define SPEC_CMDS " +forward +back +moveleft +moveright +moveup +movedown +speed +jump +duck +attack +attack2 +use +showscores +voip toggleconsole say say_team messagemode messagemode2 togglemenu hud_edit gfx_menu saveloc_menu vote spectate ghost noclip screenshot quit fullscreen_toggle vid_toggle "

// One command: its first word, to a space or a tab, quotes stripped.
float(string c) Spec_CmdAllowed =
{
	local float i, n;
	local string ch;

	c = strtrim(c);
	n = strlen(c);
	for (i = 0; i < n; i = i + 1)
	{
		ch = substring(c, i, 1);
		if (ch == " " || ch == "\t")
			break;
	}
	c = strreplace("\"", "", substring(c, 0, i));
	if (c == "")
		return TRUE;
	return (strstrofs(SPEC_CMDS, strcat(" ", c, " "), 0) >= 0);
};

// Split as the command buffer does (cmd.c:620-655): at ; or a newline outside quotes.
float(string b) Spec_BindAllowed =
{
	local float i, n, q, from;
	local string ch;

	b = strtolower(b);
	n = strlen(b);
	q = FALSE;
	from = 0;
	for (i = 0; i < n; i = i + 1)
	{
		ch = substring(b, i, 1);
		if (ch == "\"")
			q = !q;
		else if (!q)
		if (ch == ";" || ch == "\n")
		{
			if (!Spec_CmdAllowed(substring(b, from, i - from)))
				return FALSE;
			from = i + 1;
		}
	}
	return Spec_CmdAllowed(substring(b, from, n - from));
};

// Every release, after the chain: one a panel took (the board, a draft) must
// still clear the press it pairs, or the next click reads as a repeat.
void(float scan) Spec_KeyUp =
{
	if (scan == K_MOUSE1)
		spc_kheld = spc_kheld - (spc_kheld & SPB_M1);
	else if (scan == K_MOUSE2)
		spc_kheld = spc_kheld - (spc_kheld & SPB_M2);
	else if (scan == K_SPACE)
		spc_kheld = spc_kheld - (spc_kheld & SPB_SPC);
};

// A local refusal prints and returns FALSE; the server's arrives as
// `spectate _refused` after its own sprint.
float(float slot) Spec_Request =
{
	local vector o, a, v;
	local float e, bp;
	local string nm;

	if (serverkeyfloat("fs_spec") != 1)
	{
		Spec_Flash("this server does not offer it");
		return FALSE;
	}
	if (slot == player_localnum)
	{
		Spec_Flash("you cannot watch yourself");
		return FALSE;
	}
	nm = "";
	if (slot >= 0 && slot < PL_MAXSLOT)
		nm = getplayerkeyvalue(slot, "name");
	if (nm == "")
	{
		Spec_Flash("nobody in that slot");
		return FALSE;
	}
	o = '0 0 0';  a = '0 0 0';  v = '0 0 0';  e = 0;
	bp = Body_Pose(slot, o, a, e, v);
	if (!(bp & BP_LIVE))
	{
		Spec_Flash(strcat(nm, "^7 has no body to watch"));
		return FALSE;
	}
	if (!spc_stat)
	{
		if (rec_wt_open)
		{
			Spec_Flash("close the replay first");
			return FALSE;
		}
		if (rec_sl_holding)
		{
			Spec_Flash("let go of the save-lock key first");
			return FALSE;
		}
		if (rec_gh_on || rec_gh_want)
		{
			Spec_Flash("leave ghost first");
			return FALSE;
		}
		// The input thread skips CSQC_MouseMove (in_generic.c:2495) and
		// CSQC_Input_Frame (cl_input.c:2863): the mouse would turn the held aim and
		// the usercmds would keep their time.  Spec_Frame also holds it off.
		if (cvar("cl_threadedphysics"))
		{
			Spec_Flash("not with cl_threadedphysics on");
			return FALSE;
		}
		// Its bind would keep turning the held body's aim (critic #11).
		if (Keys_TurnHeld())
		{
			Spec_Flash("let go of the turn key first");
			return FALSE;
		}
	}
	if (!Spec_Active())
	{
		spc_kheld = 0;                  // nothing held now was taken here
		Spec_TurnRelease();
	}
	spc_want    = slot + 1;
	spc_wantat  = cltime;
	spc_leaving = 0;                // after a pending leave, the server takes this back to held
	localcmd(sprintf("cmd rec_spec %g\n", slot + 1));
	return TRUE;
};

// Also cancels a pending entry: the server takes the two in order.  The lock
// stays on (spc_leaving) until the stat answers.
void() Spec_Leave =
{
	if (!Spec_Active())
	{
		Spec_Flash("not spectating");
		return;
	}
	if (spc_stat < 0)
		return;                         // already counting down
	spc_want    = 0;
	spc_leaving = cltime;
	localcmd("cmd rec_spec 0\n");
};

// The next live player after the current one (or the one asked for), wrapping.
float(float dir) Spec_Step =
{
	local vector o, a, v;
	local float from, i, s, e, bp, me;

	me = player_localnum;
	from = me;
	if (spc_stat > 0)
		from = spc_stat - 1;
	if (spc_want)
		from = spc_want - 1;

	for (i = 1; i < PL_MAXSLOT; i = i + 1)
	{
		s = from + dir * i;
		s = s - PL_MAXSLOT * floor(s / PL_MAXSLOT);
		if (s == me)
			continue;
		if (getplayerkeyvalue(s, "name") == "")
			continue;
		o = '0 0 0';  a = '0 0 0';  v = '0 0 0';  e = 0;
		bp = Body_Pose(s, o, a, e, v);
		if (!(bp & BP_LIVE))
			continue;
		return Spec_Request(s);
	}
	if (spc_stat > 0)
		Spec_Flash("only one player to watch");
	else
		Spec_Flash("nobody to watch");
	return FALSE;
};

// Exact name (colours and case ignored), else a unique prefix.  -1 none, -2 several.
float(string q) Spec_FindName =
{
	local float s, hit, n;
	local string nm;

	q = strtolower(strdecolorize(q));
	if (q == "")
		return -1;
	for (s = 0; s < PL_MAXSLOT; s = s + 1)
	{
		nm = strtolower(strdecolorize(getplayerkeyvalue(s, "name")));
		if (nm != "" && !strcmp(nm, q))
			return s;
	}
	hit = -1;
	n = 0;
	for (s = 0; s < PL_MAXSLOT; s = s + 1)
	{
		nm = strtolower(strdecolorize(getplayerkeyvalue(s, "name")));
		if (nm != "" && !strcmp(substring(nm, 0, strlen(q)), q))
		{
			hit = s;
			n = n + 1;
		}
	}
	if (n > 1)
		return -2;
	return hit;
};

// The window's edges, off the stat.  A nonzero stat on a fresh VM is a rising edge.
void(float st) Spec_Edges =
{
	local float was;

	// Out of the input chain, an up can no longer be paired here.  Not on the
	// rising edge: a press taken while asking is still ours to pair.
	if (!Spec_Active())
		spc_kheld = 0;
	else
		Spec_TurnRelease();

	was = spc_stat;
	if (spc_want)
	if (st == spc_want)
		spc_want = 0;
	if (spc_want)
	if (cltime - spc_wantat > SPEC_WAIT)
	{
		spc_want = 0;
		Spec_Flash("the server did not answer");
	}
	if (spc_leaving)
	if (cltime - spc_leaving > SPEC_WAIT)
		spc_leaving = 0;
	if (st == was)
		return;

	if (!was || !st)
	{
		// The .hid's window marks: annotations, not events (hidcheck.py).  %d:
		// %g rounds past 999999 ticks (the .view's ghost marker, cl_replay.qc).
		localcmd(sprintf("in_journal_note spec %d %d\n", st ? 1 : 0,
		                 getstatf(STAT_FS_TIMERTICKS)));
	}
	if (st > 0)
	if (st != was)
	{
		// On, a new target, or back from the countdown: first person on it, and a
		// third-person camera glides out from its eye.  A free camera stays put.
		spc_tbp = 0;
		Spec_Pose(st - 1);
		if (was <= 0 || spc_mode != SPM_FREE)
			spc_camorg = spc_tfeet + [0, 0, spc_teye];
		if (was <= 0)
			spc_camang = [bound(-80, spc_tang_x, 80), spc_tang_y, 0];
		spc_dcur = 0;
		PVS_Forget();
	}
	if (st <= 0)
	{
		spc_leaving  = 0;
		spc_eyeclaim = FALSE;           // the server took the eye back (countdown, release)
		PVS_Forget();
		if (was < 0)
		if (!st)
			spc_goat = cltime;
	}
	// The yaw jumps between the two views; do not grade that as a turn.
	HUD_ClearTurnHistory();
	spc_stat = st;
};

// Third person: orbit the pivot on the mouse's angles, pulled in at once by the
// map and eased back out.  "The map" is the client's world: the world model and
// cl_sprites.qc's static occluders (cl_entview.qc:45).  Networked brush entities
// (func_brush, doors) are not in it, so the camera can pass through them.
vector(vector piv, vector cang, float dt) Spec_Orbit =
{
	local float want, allow;
	local vector cam;

	want = max(0, cvar("spec_dist"));
	makevectors(cang);
	allow = want;
	if (!cvar("spec_notrace"))
	{
		tracebox(piv, '-6 -6 -6', '6 6 6', piv - v_forward * want, MOVE_NOMONSTERS, world);
		allow = want * trace_fraction;
		if (trace_fraction < 1)
			allow = max(0, allow - 1);
		if (trace_startsolid)
			allow = 0;
	}
	spc_allow = allow;
	if (allow < spc_dcur)
		spc_dcur = allow;
	else
		spc_dcur = spc_dcur + (allow - spc_dcur) * (1 - pow(0.5, dt / SPEC_HALF));
	cam = piv - v_forward * spc_dcur;

	tracebox(piv, '-6 -6 -6', '6 6 6', cam, MOVE_NOMONSTERS, world);
	spc_clr = (trace_fraction >= 1 && !trace_startsolid);
	return cam;
};

// CSQC_UpdateView, after Body_Frame: the camera, the hidden body, your stand-in
// and the HUD override.  The countdown draws from your own eye.
void() Spec_Frame =
{
	local float st, dt, t, ts, tk, tt, tf;
	local vector piv, cam, cang, aim;

	st = getstatf(STAT_FS_SPEC);
	dt = cltime - spc_lastt;
	if (dt < 0 || dt > 0.5)
		dt = 0;
	spc_lastt = cltime;

	Spec_Edges(st);

	// Turned on mid-window, the input thread would hand the mouse back to the aim
	// (Spec_Request's check).
	if (st)
	if (cvar("cl_threadedphysics"))
	{
		cvar_set("cl_threadedphysics", "0");
		Spec_Flash("cl_threadedphysics is off while spectating");
	}

	spc_cam = FALSE;
	spc_hud = FALSE;
	spc_hideslot = 0;
	spc_clr = -1;
	spc_allow = -1;
	if (st <= 0)
		return;

	t = st - 1;
	Spec_Pose(t);
	piv = spc_tfeet + [0, 0, spc_teye];

	if (spc_mode == SPM_THIRD)
	{
		spc_camang_x = bound(-80, spc_camang_x, 80);
		cang = spc_camang;
		cam  = Spec_Orbit(piv, cang, dt);
		if (spc_dcur < SPEC_HIDE)
			spc_hideslot = t + 1;
	}
	else if (spc_mode == SPM_FREE)
	{
		cang = spc_camang;
		cam  = Ghost_Fly(spc_camorg, cang, spc_move, spc_btn, dt);
		// Claims the eye for 1 s a send (SPEC_EYE_STALE).  Not once ESC has gone:
		// a send landing in the countdown would steer it off your body.
		if (!spc_leaving)
		{
			PVS_Publish(cam);
			spc_eyeclaim = TRUE;
		}
	}
	else
	{
		cam  = piv;
		cang = spc_tang;
		spc_hideslot = t + 1;
	}
	spc_camorg = cam;
	setproperty(VF_ORIGIN, cam);
	setproperty(VF_ANGLES, cang);
	setproperty(VF_DRAWCROSSHAIR, 0);
	spc_cam = TRUE;

	// Your own body, where the hold left it -- unless the stream already draws it.
	if (!Body_Has(player_localnum))
	{
		aim = getproperty(VF_CL_VIEWANGLES);
		Ghost_DrawBodyAt(rec_gh_bodyfeet, aim_y);
	}

	if (!spc_tbp)
		return;
	spc_hud     = TRUE;
	spc_hfeet   = spc_tfeet;
	spc_hongr   = (spc_tbp & BP_ONGROUND) ? TRUE : FALSE;
	spc_hducked = (spc_tbp & BP_DUCKED) ? TRUE : FALSE;
	spc_hkeys   = Body_Keys(t);
	ts = 0;  tk = 0;  tt = 0;  tf = 0;
	spc_hrun    = Body_Run(t, ts, tk, tt, tf);
	spc_htstate = ts;
	spc_hticks  = tk;
	spc_htrack  = tt;
	spc_htflags = tf;
};

// Once per usercmd for the whole window, countdown included (critic #28): no time,
// so the client predicts nothing.  The server's anti-hover still forces moves (held:
// zeroed), and after the release about one round trip of them run as no-input moves
// and are recorded, until a timed usercmd arrives.
void() Spec_InputFrame =
{
	spc_move = input_movevalues;
	spc_btn  = input_buttons;
	input_movevalues = '0 0 0';
	input_buttons    = 0;
	input_timelength = 0;
};

/*
  From CL_InputChain while Spec_Active, behind the draft, the panels and the
  replay, and ahead of Keys_Edge.  No device reaches the aim: the mouse drives
  the camera or nothing, and a stick or a touch is zeroed (a TRUE return,
  in_generic.c:2152/2474).  Asking or leaving: ESC cancels, MOUSE1/MOUSE2/SPACE
  wait (critic #27; `spectate _refused` clears the ask).  Watching: MOUSE1/MOUSE2
  step, SPACE cycles, ESC leaves.  Counting down: ESC only.  Turn keys never reach
  their binds.  Releases pass unless their press was taken here, so a key held
  into the window lets go.
*/
float(float evtype, float scanx, float chary, float devid) Spec_InputEvent =
{
	local float bit, m;

	if (evtype == IE_MOUSEDELTA)
	{
		if (spc_stat > 0)
		if (!spc_leaving)
			Spec_Look(scanx, chary);
		return TRUE;
	}
	if (evtype == IE_MOUSEABS || evtype == IE_JOYAXIS)
		return TRUE;
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP)
		return FALSE;

	bit = 0;
	if (scanx == K_MOUSE1)      bit = SPB_M1;
	else if (scanx == K_MOUSE2) bit = SPB_M2;
	else if (scanx == K_SPACE)  bit = SPB_SPC;

	if (evtype == IE_KEYUP)
	{
		if (bit)
		if (spc_kheld & bit)
		{
			spc_kheld = spc_kheld - bit;
			return TRUE;
		}
		return FALSE;
	}

	if (Keys_TurnAny(scanx))
		return TRUE;
	// An auto-repeat of a press taken here, into the countdown too.
	if (bit)
	if (spc_kheld & bit)
		return TRUE;

	// A second ESC must not open the menu.
	if (spc_stat < 0 || (!spc_stat && getstatf(STAT_FS_SPEC) < 0))
		return (scanx == K_ESCAPE);

	// Asking, leaving, or a hold not latched yet.
	if (!spc_stat || spc_leaving)
	{
		if (scanx == K_ESCAPE)
		{
			if (!spc_leaving)
				Spec_Leave();
			return TRUE;
		}
		if (!bit)
			return FALSE;
		spc_kheld = spc_kheld | bit;
		return TRUE;
	}

	if (scanx == K_ESCAPE)
	{
		Spec_Leave();
		return TRUE;
	}
	if (!bit)
		return FALSE;
	spc_kheld = spc_kheld | bit;
	if (bit == SPB_M1)
		Spec_Step(1);
	else if (bit == SPB_M2)
		Spec_Step(-1);
	else
	{
		m = spc_mode + 1;
		if (m > SPM_FREE)
			m = SPM_FIRST;
		Spec_SetMode(m);
	}
	return TRUE;
};

// The banner, and the countdown's digit.  From the HUD pass, after the timer.
void(vector scr) Spec_Draw =
{
	local vector p;
	local float sz, t;
	local string s, nm;

	if (spc_stat < 0 || (spc_goat && cltime - spc_goat < 0.6))
	{
		Font_Set(ui_font_display);
		s = (spc_stat < 0) ? ftos(-spc_stat) : "GO";
		HUD_TextC([scr_x * 0.5, scr_y * 0.36, 0], s, 48 * ui_cv_scale, '0.45 0.85 1', 0.95);
		Font_Reset();
	}
	if (spc_stat <= 0)
		return;

	t  = spc_stat - 1;
	nm = getplayerkeyvalue(t, "name");
	if (strstrofs(nm, "^", 0) < 0)
		nm = strcat("^", Chat_ColourOf(t), nm, "^7");

	Font_Set(ui_font_ui);
	sz = 9 * ui_cv_scale;
	p  = [scr_x * 0.5, scr_y * 0.84, 0];
	HUD_TextC(p, strcat("^5WATCHING^7  ", nm, "^7  ^9", Spec_ModeName(spc_mode)),
	          sz, '1 1 1', 0.95);
	p_y = p_y + Font_Px(sz) + 3 * ui_cv_scale;
	sz = 6.5 * ui_cv_scale;
	HUD_TextC(p, "mouse1 next  -  mouse2 prev  -  space camera  -  esc back",
	          sz, '0.70 0.73 0.78', 0.85);
	p_y = p_y + Font_Px(sz) + 3 * ui_cv_scale;
	if (getstatf(STAT_FS_TIMERSTATE) == TS_RUNNING)
	{
		HUD_TextC(p, sprintf("your run %s paused",
		                     Time_TickString(getstatf(STAT_FS_TIMERTICKS), Timer_Tick())),
		          sz, '0.45 0.85 1', 0.9);
		p_y = p_y + Font_Px(sz) + 3 * ui_cv_scale;
	}
	if (spc_flash != "")
	if (cltime - spc_flashat < 2)
		HUD_TextC(p, spc_flash, sz, '1 0.82 0.2', 0.9);
	Font_Reset();
};

void() Spec_Status =
{
	local vector aim;

	aim = getproperty(VF_CL_VIEWANGLES);
	print(sprintf("spectate: stat %g  mode %s  asking %g  leaving %g  offered %g  keys %g  board %g\n",
	              spc_stat, Spec_ModeName(spc_mode), spc_want, spc_leaving ? 1 : 0,
	              serverkeyfloat("fs_spec"), spc_kheld, rec_sb_open));
	if (spc_stat > 0)
		print(sprintf("  target slot %g (%s^7)  pose bits %g  hud %g run %g\n",
		              spc_stat - 1, getplayerkeyvalue(spc_stat - 1, "name"),
		              spc_tbp, spc_hud, spc_hrun));
	print(sprintf("  camera %v  angles %v  dist %.1f\n", spc_camorg, spc_camang, spc_dcur));
	print(sprintf("  aim %v  body feet %v  looks %g  eye claimed %g\n",
	              aim, rec_gh_bodyfeet, spc_nlook, spc_eyeclaim));
};

/*
  spec_trace <frames>: one line per frame, from CSQC_UpdateView just before
  renderscene, so VF_ORIGIN/VF_ANGLES are what is drawn.  Columns:
    spt cltime stat mode tslot posebits clr dcur want
        cam.xyz cam.pitch cam.yaw
        feet.xyz eye body.pitch body.yaw rtick
        aim.pitch aim.yaw own.xyz hideslot allow
  tslot -1 when the camera is yours; clr and allow -1 outside third person
  (allow: the distance the map allows this frame); rtick is the
  watched body's render clock in ticks (an integer = drawn on a sample), -1 none.
*/
void() Spec_Trace =
{
	local vector c, ca, aim;
	local float t, rt;
	local entity b;

	if (spc_trn <= 0)
		return;
	spc_trn = spc_trn - 1;

	c   = getproperty(VF_ORIGIN);
	ca  = getproperty(VF_ANGLES);
	aim = getproperty(VF_CL_VIEWANGLES);
	t   = spc_cam ? spc_stat - 1 : -1;
	rt  = -1;
	if (t >= 0)
	{
		b = Body_Find(t);
		if (b)
		if (pb_tick > 0)
			rt = b.pb_reval / pb_tick;
	}
	// A QC call takes eight parameters, the format included (AGENTS.md).
	print(strcat(sprintf("spt %.4f %g %g %g %g %g %.2f", cltime, spc_stat, spc_mode, t,
	                     spc_tbp, spc_clr, spc_dcur),
	             sprintf(" %g %.3f %.3f %.3f %.4f %.4f", spc_want, c_x, c_y, c_z, ca_x, ca_y),
	             sprintf(" %.3f %.3f %.3f %.2f %.4f %.4f %.3f", spc_tfeet_x, spc_tfeet_y,
	                     spc_tfeet_z, spc_teye, spc_tang_x, spc_tang_y, rt),
	             sprintf(" %.4f %.4f %.3f %.3f %.3f %g %.2f\n", aim_x, aim_y, rec_gh_bodyorg_x,
	                     rec_gh_bodyorg_y, rec_gh_bodyorg_z, spc_hideslot, spc_allow)));
};

float(string cmd) Spec_ConsoleCommand =
{
	local float s;
	local string a;

	tokenize(cmd);
	if (argv(0) == "spec_trace")
	{
		spc_trn = (argv(1) == "") ? 600 : stof(argv(1));
		print(sprintf("spec_trace: %g frames\n", spc_trn));
		return TRUE;
	}
	if (argv(0) != "spectate")
		return FALSE;

	a = argv(1);
	if (a == "_refused")
	{
		// A leave queued behind a refused entry has nothing left to answer it.
		spc_want = 0;
		if (!spc_stat)
			spc_leaving = 0;
		return TRUE;
	}
	if (a == "status")
	{
		Spec_Status();
		return TRUE;
	}
	if (a == "off")
	{
		Spec_Leave();
		return TRUE;
	}
	if (a == "next" || a == "prev")
	{
		Spec_Step((a == "next") ? 1 : -1);
		return TRUE;
	}
	if (a == "mode")
	{
		a = argv(2);
		if (a == "first")      Spec_SetMode(SPM_FIRST);
		else if (a == "third") Spec_SetMode(SPM_THIRD);
		else if (a == "free")  Spec_SetMode(SPM_FREE);
		else
			print("spectate mode first|third|free\n");
		print(sprintf("spectate: %s\n", Spec_ModeName(spc_mode)));
		return TRUE;
	}
	if (a == "")
	{
		// Bare: leave, or watch the next player.
		if (spc_stat > 0)
			Spec_Leave();
		else
			Spec_Step(1);
		return TRUE;
	}
	if (substring(a, 0, 1) == "#")
	{
		Spec_Request(stof(substring(a, 1, -1)));
		return TRUE;
	}
	s = Spec_FindName(a);
	if (s == -2)
		Spec_Flash(sprintf("\"%s\" matches more than one player", a));
	else if (s < 0)
		Spec_Flash(sprintf("nobody called \"%s\"", a));
	else
		Spec_Request(s);
	return TRUE;
};
