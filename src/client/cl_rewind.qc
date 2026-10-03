/*
===========================================================================
  cl_rewind.qc -- rewind along your own run.  Patch 477.

  Lex: "hit a rewind button that lets them slide back on the run like the demo
  display and allow continuing from any point/tick with the same velocity and
  angles.  Count the player down when they want to resume and allow placing
  save states during the rewind".

  The line is the live trail's (cl_trail.qc).  The body is pinned by the
  replay's own pin, `rec_watch 1`: the clock freezes, so the .view sidecar takes
  no frames while the camera rides the cursor (Rec_ViewFrame skips TF_FROZEN).
  Resume and save both go through `sl_saveat`, which saves from the SERVER's
  record of the run.  Resume adds `go`: the server leaves the pin, loads that
  save and holds it in the same call, and the countdown is the hold, released
  at zero.  A rewound continuation is practice until a velocity-zeroing reset
  -- sv_saveloc.qc, REWIND.
===========================================================================
*/

#define RW_COUNT    3           // seconds counted before the hold lets go
#define RW_CAMBACK  150         // chase camera: units behind the cursor
#define RW_CAMUP    48          // ...and above it
#define RW_RATE0    30          // samples a second a held scrub key moves at first
#define RW_RATEMAX  600         // ...and after RW_ACCEL seconds held
#define RW_ACCEL    2.0
#define RW_ASK      2           // seconds a clean run's second press has
#define RW_LOST     5           // seconds a go may go unanswered before the mode gives up
#define RW_KEPT     7900        // run ticks back the server keeps: RW_CAP x RW_EVERY, less a margin

float  rw_on;                   // the mode is up: browsing, sent or counting
float  rw_i;                    // cursor: a point index in the live trail slot
float  rw_dir;                  // scrub key held: -1, +1 or 0
float  rw_dirat;                // cltime it went down
float  rw_last;                 // cltime of the last Rewind_Frame
float  rw_ack;                  // a go in flight: the sl_ count that covers it; 0 = none
float  rw_seq;                  // STAT_FS_SLSEQ when it went
float  rw_sentat;               // cltime it went
float  rw_cd;                   // cltime the countdown ends; 0 = not counting
float  rw_askat;                // cltime a clean run's first press asked; 0 = none

void() Rewind_RegisterCvars =
{
	registercommand("rewind");
};

// The key bound to `rewind` (default.cfg), else "rewind".
string() Rewind_Key =
{
	local string k;
	local float sp;

	k = findkeysforcommandex("rewind");
	sp = strstrofs(k, " ", 0);
	if (sp > 0)
		k = substring(k, 0, sp);
	if (k == "")
		return "rewind";
	return strtoupper(k);
};

void() Rewind_Cursor =
{
	local float n, b;

	n = ln_n[tr_live];
	if (rw_i > n - 1)
		rw_i = n - 1;
	if (rw_i < 0)
		rw_i = 0;
	b = tr_live * LN_CAP + floor(rw_i);
	tr_cur_t = ln_t[b];
	tr_cur_p = ln_pos[b];
};

// The cursor is further back than the server's ring reaches, so a save or a
// resume there will be refused.  The line keeps more than the ring does.
float() Rewind_Old =
{
	local float n;

	n = ln_n[tr_live];
	if (n < 1 || tr_tick <= 0)
		return FALSE;
	return (ln_t[tr_live * LN_CAP + n - 1] - tr_cur_t) / tr_tick > RW_KEPT;
};

float() Rewind_Open =
{
	if (rw_on)
		return FALSE;
	if (!tr_on || ln_n[tr_live] < 2)
	{
		print("^3rewind:^7 no run to rewind -- start one first\n");
		return FALSE;
	}
	if (rec_wt_open || rec_gh_on || Spec_Active() || rec_sl_holding)
	{
		print("^3rewind:^7 not while a replay, ghost, spectate or load is up\n");
		return FALSE;
	}
	// The pin stops the clock, which makes a clean run practice (SV_TimerFreeze):
	// Patch 391's refusal of a mid-run load, with a second press as the way through.
	if (SaveLoc_RunLocked() && !(rw_askat && cltime - rw_askat < RW_ASK))
	{
		rw_askat = cltime;
		print(sprintf("^3rewind:^7 %s again to rewind -- this clean run becomes practice\n",
		              Rewind_Key()));
		return FALSE;
	}
	rw_askat = 0;
	rw_on  = TRUE;
	rw_ack = rw_cd = rw_dir = 0;
	rw_last = cltime;
	rw_i = ln_n[tr_live] - 1;       // the head: where you are now
	tr_cur_on = TRUE;
	Rewind_Cursor();
	PVS_Forget();
	localcmd("cmd rec_watch 1\n");
	return TRUE;
};

// Back to the body with nothing loaded: the pin and the clock let go and the
// run carries on, as practice if it was on the clock.  The pin zeroed the
// velocity (SV_WatchHold), as closing a replay does.
void() Rewind_Close =
{
	if (!rw_on || rw_ack || rw_cd)
		return;
	rw_on  = FALSE;
	rw_dir = 0;
	tr_cur_on = FALSE;
	localcmd("cmd rec_watch 0\n");
};

// Out of the mode whatever the server did: neither command does anything to a
// body that is not pinned or held.
void() Rewind_Abandon =
{
	localcmd("cmd rec_watch 0\n");
	if (rec_sl_holding)
		SaveLoc_Release();          // which sends sl_holdoff itself
	else
		SaveLoc_Cmd("sl_holdoff");
	rw_on = rw_ack = rw_cd = rw_dir = 0;
	tr_cur_on = FALSE;
};

// The cursor as `<ticks> <x> <y> <z>`.  The position picks which of the
// server's samples near that tick was meant -- the tick stat lags the drawn
// position by a round trip -- and is never where the body is put.
string() Rewind_At =
{
	local float tk;

	tk = (tr_tick > 0) ? rint(tr_cur_t / tr_tick) : 0;
	return sprintf("%g %g %g %g", tk, tr_cur_p_x, tr_cur_p_y, tr_cur_p_z);
};

void() Rewind_Save =
{
	SaveLoc_Cmd(strcat("sl_saveat ", Rewind_At()));
};

// One command; Rewind_Frame reads what came of it from the load event.
void() Rewind_Go =
{
	rw_seq = getstatf(STAT_FS_SLSEQ);
	SaveLoc_Cmd(strcat("sl_saveat ", Rewind_At(), " go"));
	rw_ack = rec_sl_sent;
	rw_sentat = cltime;
	rw_dir = 0;
};

/*
  The go's answer.  The server ran it once STAT_FS_SLACK covers it, and it
  loaded iff the newest save/load event since is a load -- the save's own event
  is overwritten in the same frame, so a save that loaded nothing ends on
  SLOP_SAVED.  Refused: still pinned, so still browsing, and the server's line
  says why.  Loaded: SaveLoc_LoadKey's latches without its predicted camera,
  and the hold is the countdown.
*/
void() Rewind_Answer =
{
	if (getstatf(STAT_FS_SLACK) < rw_ack)
	{
		if (cltime - rw_sentat > RW_LOST)
			Rewind_Abandon();       // the count restarted under it: an observe or a rejoin
		return;
	}
	if (getstatf(STAT_FS_SLSEQ) == rw_seq || FS_SlopOp(getstatf(STAT_FS_SLOP)) != SLOP_LOADED)
	{
		rw_ack = 0;
		return;
	}
	rec_sl_holdack   = rw_ack;
	rec_sl_holdackat = 0;
	rec_sl_holding   = TRUE;
	rec_sl_holdkey   = 0;
	rec_sl_holdseen  = cltime;
	rec_sl_holdrep   = FALSE;
	rw_ack = 0;
	tr_cur_on = FALSE;
	rw_cd  = cltime + RW_COUNT;
};

// Every frame, with the other per-frame readers.
void() Rewind_Frame =
{
	local float dt, rate;

	if (!rw_on)
		return;
	dt = cltime - rw_last;
	rw_last = cltime;
	if (rw_ack)
	{
		Rewind_Answer();
		return;
	}
	if (rw_cd)
	{
		// Let go early (Esc, or SaveLoc_Idle with the console up), or the hold's
		// deadman saw no hold: either way the load is over.
		if (!rec_sl_holding || cltime >= rw_cd)
			Rewind_Abandon();       // sl_holdoff: the server hands back the save's velocity
		return;
	}
	if (!tr_on || ln_n[tr_live] < 2 || !tr_cur_on)
	{
		Rewind_Close();             // the line went: a map change, or hud_trail 0
		return;
	}
	if (rw_dir)
	{
		rate = RW_RATE0 + (RW_RATEMAX - RW_RATE0) * min(1, (cltime - rw_dirat) / RW_ACCEL);
		rw_i = rw_i + rw_dir * rate * dt;
	}
	Rewind_Cursor();
};

// CSQC_UpdateView, beside the replay's camera.  A chase view behind the cursor,
// along the line's own direction there, stopped short of walls.
void() Rewind_Camera =
{
	local float n, b, j0, j1;
	local vector d, a, cam;

	if (!rw_on || rw_cd)
		return;
	n = ln_n[tr_live];
	b = tr_live * LN_CAP;
	j0 = max(0, floor(rw_i) - 3);
	j1 = min(n - 1, floor(rw_i) + 3);
	d = ln_pos[b + j1] - ln_pos[b + j0];
	d_z = 0;
	if (vlen(d) < 1)
		d = '1 0 0';
	a = vectoangles(d);
	makevectors([0, a_y, 0]);
	cam = tr_cur_p - v_forward * RW_CAMBACK + '0 0 1' * RW_CAMUP;
	traceline(tr_cur_p + '0 0 16', cam, MOVE_NOMONSTERS, world);
	cam = trace_endpos + trace_plane_normal * 4;
	setproperty(VF_ORIGIN, cam);
	setproperty(VF_ANGLES, [12, a_y, 0]);
	PVS_Publish(cam);
};

void(vector scr) Rewind_Draw =
{
	local float tk;
	local string s;

	if (!rw_on)
	{
		if (rw_askat && cltime - rw_askat < RW_ASK)
			HUD_TextC([scr_x * 0.5, scr_y * 0.12, 0],
			          sprintf("%s again to rewind -- this clean run becomes practice",
			                  Rewind_Key()),
			          14 * ui_cv_scale, '1 0.8 0.3', 0.95);
		return;
	}
	Font_Set(ui_font_display);
	if (rw_cd)
	{
		HUD_TextC([scr_x * 0.5, scr_y * 0.36, 0], ftos(ceil(rw_cd - cltime)),
		          48 * ui_cv_scale, '0.45 0.85 1', 0.95);
		Font_Reset();
		return;
	}
	HUD_TextC([scr_x * 0.5, scr_y * 0.12, 0], "REWIND", 28 * ui_cv_scale,
	          '0.45 0.85 1', 0.95);
	Font_Reset();
	tk = (tr_tick > 0) ? rint(tr_cur_t / tr_tick) : 0;
	s = sprintf("%s   %g u/s", Time_TickString(tk, tr_tick),
	            floor(ln_spd[tr_live * LN_CAP + floor(rw_i)]));
	HUD_TextC([scr_x * 0.5, scr_y * 0.12 + 36 * ui_cv_scale, 0], s,
	          16 * ui_cv_scale, '1 1 1', 0.95);
	if (rw_ack)
		s = "...";
	else if (Rewind_Old())
		s = "LEFT/RIGHT scrub   too far back: the server keeps the last two minutes   ESC back";
	else
		s = "LEFT/RIGHT scrub   ENTER resume here   S save here   ESC back";
	HUD_TextC([scr_x * 0.5, scr_y * 0.88, 0], s, 12 * ui_cv_scale, '0.8 0.8 0.8', 0.85);
};

// In CL_InputChain beside the replay's.  The mouse is swallowed (the view rides
// the cursor); keys this mode does not use fall through to their binds.
float(float evtype, float scanx, float chary, float devid) Rewind_InputEvent =
{
	if (!rw_on)
		return FALSE;
	if (evtype == IE_MOUSEDELTA || evtype == IE_MOUSEABS)
		return !rw_cd;
	if (evtype == IE_KEYUP)
	{
		if (scanx == K_LEFTARROW || scanx == K_RIGHTARROW)
		{
			rw_dir = 0;
			return TRUE;
		}
		return FALSE;
	}
	if (evtype != IE_KEYDOWN)
		return FALSE;
	if (rw_cd)
	{
		if (scanx == K_ESCAPE)      // go now rather than wait
		{
			rw_cd = cltime;
			return TRUE;
		}
		return FALSE;
	}
	if (rw_ack)                     // a go is in flight: one round trip
		return scanx == K_ESCAPE || scanx == K_ENTER || scanx == K_KP_ENTER || scanx == 's'
		    || scanx == K_LEFTARROW || scanx == K_RIGHTARROW;
	if (scanx == K_LEFTARROW || scanx == K_RIGHTARROW)
	{
		if (!rw_dir)
			rw_dirat = cltime;
		rw_dir = (scanx == K_LEFTARROW) ? -1 : 1;
		rw_i = rw_i + rw_dir;
		Rewind_Cursor();
		return TRUE;
	}
	if (scanx == K_MWHEELDOWN || scanx == K_MWHEELUP)
	{
		rw_i = rw_i + ((scanx == K_MWHEELDOWN) ? -10 : 10);
		Rewind_Cursor();
		return TRUE;
	}
	if (scanx == K_ENTER || scanx == K_KP_ENTER)
	{
		Rewind_Go();
		return TRUE;
	}
	if (scanx == 's')
	{
		Rewind_Save();
		return TRUE;
	}
	if (scanx == K_ESCAPE)
	{
		Rewind_Close();
		return TRUE;
	}
	return FALSE;
};

/*
  `rewind` toggles.  The rest are harness handles a config can drive:
  `rewind go|save|status`, `rewind seek <seconds>` (negative: back from the
  head) and `rewind step <points>`.
*/
float() Rewind_Console =
{
	local string a;
	local float t, busy;

	if (argv(0) != "rewind")
		return FALSE;
	a = argv(1);
	busy = !rw_on || rw_ack || rw_cd;
	if (a == "")
	{
		if (rw_on)
			Rewind_Close();
		else
			Rewind_Open();
	}
	else if (a == "go" && !busy)
		Rewind_Go();
	else if (a == "save" && !busy)
		Rewind_Save();
	else if (a == "seek" && !busy)
	{
		t = stof(argv(2));
		if (t < 0)
			t = ln_t[tr_live * LN_CAP + ln_n[tr_live] - 1] + t;
		rw_i = Line_Find(tr_live, t);
		Rewind_Cursor();
	}
	else if (a == "step" && !busy)
	{
		rw_i = rw_i + stof(argv(2));
		Rewind_Cursor();
	}
	else if (a == "status")
	{
		print(sprintf("rewind: on %g counting %g sent %g  cursor %g of %g  kept %g\n",
		              rw_on, rw_cd ? 1 : 0, rw_ack ? 1 : 0, floor(rw_i), ln_n[tr_live],
		              !Rewind_Old()));
		print(sprintf("rewind: at %s  %s\n", Rewind_At(),
		              Time_TickString(tr_tick > 0 ? rint(tr_cur_t / tr_tick) : 0, tr_tick)));
	}
	return TRUE;
};

// A map change: the line is gone and the server has forgotten the pin.
void() Rewind_Reset =
{
	rw_on = rw_ack = rw_cd = rw_dir = rw_askat = 0;
	tr_cur_on = FALSE;
};
