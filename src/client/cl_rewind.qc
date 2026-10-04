/*
===========================================================================
  cl_rewind.qc -- rewind along your own run.  Patch 477.

  Lex: "hit a rewind button that lets them slide back on the run like the demo
  display and allow continuing from any point/tick with the same velocity and
  angles.  Count the player down when they want to resume and allow placing
  save states during the rewind".

  The line is the live trail's (cl_trail.qc).  The body is pinned by the
  replay's own pin, `rec_watch 1`, which stops the clock (making a running run
  practice), so the .view sidecar takes no frames while the camera rides the
  cursor (Rec_ViewFrame skips TF_FROZEN).  Resume and save both go through
  `sl_saveat`, which saves from the SERVER's record of the run.  Resume adds
  `go`: the server leaves the pin, loads that save and holds it in the same
  call, and the countdown is the hold, released at zero.  A rewound
  continuation is practice when it carries more than a walk or a jump could
  -- sv_saveloc.qc, SV_SaveLoadTag.  ESC on a run that is on the clock is a resume at the
  head: you go on from where you were with your speed (refused, you stop
  there), and the run's clock ends either way (the pin made it practice).  A
  thaw would carry the run past a freeze the .rec never records -- AGENTS.md,
  the held-run fault.
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
#define RW_KEYS     6           // the keys rw_kst tracks, Rewind_KeyIx's order

float  rw_on;                   // the mode is up: browsing, sent or counting
float  rw_st0;                  // STAT_FS_TIMERSTATE when it opened
float  rw_seen;                 // the last STAT_FS_SLSEQ it saw while browsing
float  rw_headi, rw_headt;      // the head when it opened: the leave's resume point
vector rw_headp;
float  rw_i;                    // cursor: a point index in the live trail slot
float  rw_dir;                  // scrub key held: -1, +1 or 0
float  rw_dirat;                // cltime it went down
float  rw_last;                 // cltime of the last Rewind_Frame
float  rw_ack;                  // a go in flight: the sl_ count that covers it; 0 = none
float  rw_seq;                  // STAT_FS_SLSEQ when it went
float  rw_sentat;               // cltime it went
float  rw_goi;                  // ...and the cursor it went from
float  rw_leave;                // it is the way out of a run on the clock (Rewind_Leave)
float  rw_cd;                   // cltime the countdown ends; 0 = not counting
float  rw_askat;                // cltime a clean run's first press asked; 0 = none
float  rw_askgen;               // ...on this line (tr_gen): a new run is asked about afresh
float  rw_resi;                 // the last resume's cursor, -1 none...
float  rw_resgen;               // ...on this line (tr_gen: the two slots alternate)...
float  rw_resn;                 // ...with this many samples, so the same unchanged line
float  rw_atres;                // opened there
float  rw_kst[RW_KEYS];         // 1 this mode took the press, 2 it was down before the mode opened
float  rw_kdown[RW_KEYS];       // down as CSQC_InputEvent saw it, whoever took the press (Rewind_Track)
#define RW_SWN      8
float  rw_sw[RW_SWN];           // other keys this mode swallowed, still held: theirs until let go (round 21)
float  rw_krep;                 // ...and the event in hand repeats one already down
float  rw_pinseen;              // this open's pin seen (STAT_FS_PIN lands a round trip later)
float  rw_serial;               // this open's number, sent with its pin and published back as STAT_FS_PIN
float  rw_openat;               // cltime of the open: a pin unseen RW_LOST after it is gone (round 19)

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

// Round 27: a bind the browsing gate zeroes until the release (CSQC_Input_Frame
// clears movement and buttons, not the view's angles).
float(string b) Rewind_MoveBind =
{
	if (b == "+forward" || b == "+back" || b == "+moveleft" || b == "+moveright")
		return TRUE;
	if (b == "+jump" || b == "+duck" || b == "+moveup" || b == "+movedown")
		return TRUE;
	return FALSE;
};

float(float scan) Rewind_KeyIx =
{
	if (scan == 's')            return 0;
	if (scan == K_ENTER)        return 1;
	if (scan == K_KP_ENTER)     return 2;
	if (scan == K_LEFTARROW)    return 3;
	if (scan == K_RIGHTARROW)   return 4;
	if (scan == K_ESCAPE)       return 5;
	return -1;
};

// Review round 17: every key event, from the top of CSQC_InputEvent, ahead of
// the whole chain.  A press an earlier handler took (the chat draft's ENTER or
// ESC) still marks its key down, so its auto-repeat is not a press here; a
// release one swallowed still lets go (Rewind_Frame).  The engine hands CSQC
// the up of every down it offered, whatever has focus (keys.c).
// Round 21: a key outside the table the mode swallowed (a digit, `z`, a
// save-lock bind) stays swallowed until its release, also once the mode has
// closed -- its auto-repeat reached the save-lock keys as presses (4 deleted
// at the rate limit while held).  Scancode 0 is a free slot, never a key here:
// a real key reports 0 too (the ISO `<>` key, a dead key), and its release
// cleared the whole table (round 22).
float(float scanx) Rewind_SwHas =
{
	local float i;

	if (!scanx)
		return FALSE;
	for (i = 0; i < RW_SWN; i = i + 1)
		if (rw_sw[i] == scanx)
			return TRUE;
	return FALSE;
};

void(float scanx) Rewind_SwSet =
{
	local float i;

	if (Rewind_SwHas(scanx))
		return;
	for (i = 0; i < RW_SWN; i = i + 1)
		if (!rw_sw[i])
		{
			rw_sw[i] = scanx;
			return;
		}
};

void(float scanx) Rewind_SwClear =
{
	local float i;

	if (!scanx)
		return;
	for (i = 0; i < RW_SWN; i = i + 1)
		if (rw_sw[i] == scanx)
			rw_sw[i] = 0;
};

void() Rewind_SwReset =
{
	local float i;

	for (i = 0; i < RW_SWN; i = i + 1)
		rw_sw[i] = 0;
};

void(float evtype, float scanx) Rewind_Track =
{
	local float k;

	rw_krep = FALSE;
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP)
		return;
	if (evtype == IE_KEYUP)         // round 22: whoever takes it -- the chat draft took it
		Rewind_SwClear(scanx);      // and the next press of that key was swallowed
	k = Rewind_KeyIx(scanx);
	if (k < 0)
		return;
	if (evtype == IE_KEYDOWN)
	{
		rw_krep = rw_kdown[k];
		rw_kdown[k] = TRUE;
	}
	else
		rw_kdown[k] = FALSE;
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
	return ((ln_t[tr_live * LN_CAP + n - 1] - tr_cur_t) / tr_tick) > RW_KEPT;
};

float() Rewind_Open =
{
	local float k;

	if (rw_on)
		return FALSE;
	if (!cvar("hud_trail"))
	{
		print("^3rewind:^7 it rewinds your run's line, and hud_trail is off "
		      "(hud_edit, Run lines)\n");
		return FALSE;
	}
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
	// Every way out of a rewind ends the run on the clock (a resume loads an idle
	// row, a refusal voids), so any running run asks first -- Patch 391's refusal
	// of a mid-run load, with a second press as the way through (round 6).
	if (getstatf(STAT_FS_TIMERSTATE) == TS_RUNNING)
	if (!rw_askat || (cltime - rw_askat) >= RW_ASK || rw_askgen != tr_gen)
	{
		rw_askat = cltime;
		rw_askgen = tr_gen;
		print(sprintf("^3rewind:^7 %s again to rewind -- the run on the clock ends here\n",
		              Rewind_Key()));
		return FALSE;
	}
	rw_askat = 0;
	rw_on  = TRUE;
	rw_st0 = getstatf(STAT_FS_TIMERSTATE);
	rw_seen = getstatf(STAT_FS_SLSEQ);
	rw_ack = rw_cd = rw_dir = rw_leave = rw_pinseen = 0;
	rw_openat = cltime;
	rw_serial = rw_serial + 1;
	rw_last = cltime;
	for (k = 0; k < RW_KEYS; k = k + 1)     // held into the open: its repeats are not presses
		rw_kst[k] = rw_kdown[k] ? 2 : 0;
	// No reset of the swallowed-key table here (round 23): each entry goes with
	// its own release (Rewind_Track), and one still held stays swallowed.
	rw_i = ln_n[tr_live] - 1;       // the head: where the run is now...
	rw_headi = rw_i;
	rw_headt = ln_t[tr_live * LN_CAP + rw_i];
	rw_headp = ln_pos[tr_live * LN_CAP + rw_i];
	rw_atres = FALSE;
	if (rw_resi >= 0)               // ...unless that line is the one last resumed from
	if (tr_gen == rw_resgen)
	if (tr_nsamp == rw_resn)
	if (rw_resi < ln_n[tr_live])
	{
		rw_i = rw_resi;
		rw_atres = TRUE;
	}
	tr_cur_on = TRUE;
	Rewind_Cursor();
	PVS_Forget();
	// rw: a warp under it ends the frozen run (SV_RewindWarped); the serial
	// comes back as STAT_FS_PIN while this open's pin is held; the state and the
	// ticks seen now let the server leave alone a run that started since (rounds
	// 12-13).
	// %d, not %g: %g keeps six digits, and a run past 10^6 ticks (4 h) rounded up
	// read as a newer run and was refused (round 14).  SLSEQ: a save or load
	// landing in the round trip changes the run too.
	localcmd(sprintf("cmd rec_watch 1 rw %d %d %d %d\n", rw_serial, rw_st0,
	                 getstatf(STAT_FS_TIMERTICKS), getstatf(STAT_FS_SLSEQ)));
	return TRUE;
};

// Back to the body with nothing loaded: the pin lets go, and a run still on
// the clock under it ENDS (`void`, SV_WatchVoid) -- a refused resume, or a run
// that began just as the mode opened -- rather than thawing past a freeze the
// .rec never records.  The pin zeroed the velocity (SV_WatchHold), as closing
// a replay does.  sl_holdoff too: a go whose answer was misread as a refusal
// must not leave its hold behind.
void() Rewind_Close =
{
	if (!rw_on || rw_ack || rw_cd)
		return;
	rw_on  = FALSE;
	rw_dir = 0;
	tr_cur_on = FALSE;
	localcmd("cmd rec_watch 0 void\n");
	SaveLoc_Cmd("sl_holdoff");
};

// Out of the mode whatever the server did: neither command does anything to a
// body that is not pinned or held.
void() Rewind_Abandon =
{
	localcmd("cmd rec_watch 0 void\n");
	if (rec_sl_holding)
		SaveLoc_Release();          // which sends sl_holdoff itself
	else
		SaveLoc_Cmd("sl_holdoff");
	rw_on = rw_ack = rw_cd = rw_dir = rw_leave = 0;
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

// One command; Rewind_Answer reads what came of it from the load event.
void() Rewind_Go =
{
	rw_seq = getstatf(STAT_FS_SLSEQ);
	rw_goi = floor(rw_i);
	SaveLoc_Cmd(strcat("sl_saveat ", Rewind_At(), " go"));
	rw_ack = rec_sl_sent;
	rw_sentat = cltime;
	rw_dir = 0;
};

// ESC, `rewind` while open, or the line going away.  A run that was and still
// is on the clock resumes at the head stored at the open (see the header) --
// not gated on TF_FROZEN, which lags the pin by a round trip (review round 4).
// A refused resume ends the run (Rewind_Close).
void() Rewind_Leave =
{
	if (getstatf(STAT_FS_TIMERSTATE) != TS_RUNNING || rw_st0 != TS_RUNNING)
	{
		Rewind_Close();
		return;
	}
	rw_i = rw_headi;
	tr_cur_t = rw_headt;
	tr_cur_p = rw_headp;
	rw_leave = TRUE;
	Rewind_Go();
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
		if ((cltime - rw_sentat) > RW_LOST)
			Rewind_Abandon();       // the count restarted under it: an observe or a rejoin
		return;
	}
	if (getstatf(STAT_FS_SLSEQ) == rw_seq || FS_SlopOp(getstatf(STAT_FS_SLOP)) != SLOP_LOADED)
	{
		rw_ack = 0;
		if (rw_leave)
		{
			rw_leave = FALSE;
			Rewind_Close();
		}
		return;
	}
	rec_sl_holdack   = rw_ack;
	rec_sl_holdackat = 0;
	rec_sl_holding   = TRUE;
	rec_sl_holdkey   = 0;
	rec_sl_holdseen  = cltime;
	rec_sl_holdrep   = FALSE;
	rw_resi    = rw_goi;
	rw_resgen  = tr_gen;
	rw_resn    = tr_nsamp;
	rw_ack = 0;
	tr_cur_on = FALSE;
	rw_cd  = cltime + RW_COUNT;
};

// Every frame, with the other per-frame readers.
// A go in flight or the countdown: a replay opened now would miss the handover.
float() Rewind_Busy =
{
	return rw_ack || rw_cd;
};

// Watch_Open, just before its own pin: browsing, the rewind gives its pin up in
// the same frame, so no key it would still read can release the replay's
// (review round 11).  Its run on the clock ends, as every way out does.
void() Rewind_HandOver =
{
	if (!rw_on)
		return;
	localcmd("cmd rec_watch 0 void\n");
	SaveLoc_Cmd("sl_holdoff");      // as Rewind_Close: a go misread as refused (round 12)
	rw_on = rw_dir = 0;
	tr_cur_on = FALSE;
};

void() Rewind_Frame =
{
	local float dt, rate, k;

	// Round 17: a release an earlier handler swallowed (the chat draft's) still
	// lets go, so a scrub stops and the key's next press is a press -- closed
	// too (round 20), as Rewind_AfterTook reads rw_kst then.
	for (k = 0; k < RW_KEYS; k = k + 1)
		if (rw_kst[k])
		if (!rw_kdown[k])
			rw_kst[k] = 0;
	if (!rw_on)
		return;
	dt = cltime - rw_last;
	rw_last = cltime;
	if (rw_dir < 0)
	if (!rw_kdown[3])
		rw_dir = 0;
	if (rw_dir > 0)
	if (!rw_kdown[4])
		rw_dir = 0;
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
	// Loaded under the mode (2-6 are refused under the pin; `sl_replay` with
	// sv_cheats is not): what is on screen is not where the body is (review
	// round 2).  Our own S save is a SAVED event.  A warp is SV_RewindWarped's
	// and the state check's below.
	if (getstatf(STAT_FS_SLSEQ) != rw_seen)
	{
		rw_seen = getstatf(STAT_FS_SLSEQ);
		if (FS_SlopOp(getstatf(STAT_FS_SLOP)) == SLOP_LOADED)
		{
			Rewind_Close();
			return;
		}
	}
	if (getstatf(STAT_FS_TIMERSTATE) != rw_st0)
	{
		Rewind_Close();
		return;
	}
	// The server let go of the pin unasked (a respawn, a lobby flip, a typed
	// `rec_watch 0`): the body is free under the camera (review round 9).  The
	// stat is this open's own serial, so a pin or release still in flight from
	// an earlier open is never mistaken for it (rounds 10-11); a refusal and a
	// release both publish -serial, so one inside a snapshot is seen (14-16).
	k = getstatf(STAT_FS_PIN);
	if (k == rw_serial)
		rw_pinseen = TRUE;
	else if (rw_pinseen || k == -rw_serial)
	{
		Rewind_Close();
		return;
	}
	// Round 19: and one that never showed -- an `observe` inside the round trip
	// clears the edict, so the stat goes straight to 0, neither branch above.
	if (!rw_pinseen)
	if ((cltime - rw_openat) > RW_LOST)
	{
		Rewind_Close();
		return;
	}
	if (!tr_on || !tr_cur_on)
	{
		Rewind_Leave();             // the line went: hud_trail 0
		return;
	}
	// The line started over: a run began under the pin with no state change
	// seen -- a warp out of a start box restarts it within one packet.  The
	// head stored at the open is the old run's: resume nothing (round 7).
	if (ln_n[tr_live] < 2)
	{
		Rewind_Close();
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
	if (n < 2)                      // round 16: the line restarted under a go in flight
		return;
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
		if (rw_askat)
		if ((cltime - rw_askat) < RW_ASK)
		if (rw_askgen == tr_gen)
			HUD_TextC([scr_x * 0.5, scr_y * 0.12, 0],
			          sprintf("%s again to rewind -- the run on the clock ends here",
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
	if (rw_atres)
		HUD_TextC([scr_x * 0.5, scr_y * 0.12 + 56 * ui_cv_scale, 0],
		          "where you last resumed -- what you did since is not on this line",
		          11 * ui_cv_scale, '0.8 0.8 0.8', 0.85);
	if (rw_ack)
		s = "...";
	else if (Rewind_Old())
		s = "LEFT/RIGHT scrub   too far back: the server keeps the last two minutes";
	else
		s = "LEFT/RIGHT scrub   ENTER resume here   S save here";
	s = strcat(s, (rw_st0 == TS_RUNNING) ? "   ESC resume where you were" : "   ESC back");
	HUD_TextC([scr_x * 0.5, scr_y * 0.88, 0], s, 12 * ui_cv_scale, '0.8 0.8 0.8', 0.85);
};

/*
  In CL_InputChain beside the replay's.  The mouse is swallowed while browsing
  (the view rides the cursor).  A key this mode acts on acts on its first
  press only -- the engine hands CSQC every repeat -- and its release is taken
  only if its press was; a key that was down before the mode opened keeps its
  release for its bind.  Everything else falls through.
*/
float(float evtype, float scanx, float chary, float devid) Rewind_InputEvent =
{
	local float k, st, slk;

	if (!rw_on)
		return FALSE;
	if (evtype == IE_MOUSEDELTA || evtype == IE_MOUSEABS)
		return !rw_cd;
	// A key bound to `rewind` stays the toggle, whatever this table would make
	// of it; its repeats never reach the bind (the engine filters them).
	if (getkeybind(scanx) == "rewind")
		return FALSE;
	k = Rewind_KeyIx(scanx);
	if (evtype == IE_KEYUP)
	{
		if (k < 0)
		{
			Rewind_SwClear(scanx);
			return FALSE;
		}
		st = rw_kst[k];
		rw_kst[k] = 0;
		if (st == 1)
		if (k == 3 || k == 4)
			rw_dir = 0;
		// A `+` bind's release always reaches it: one held into the mode that
		// was not seen going down would otherwise stick (round 3).
		if (substring(getkeybind(scanx), 0, 1) == "+")
			return FALSE;
		return st == 1;
	}
	if (evtype != IE_KEYDOWN)
		return FALSE;
	if (k >= 0)
	if (rw_kst[k] || rw_krep)
		return TRUE;                // a repeat, a key held from before, or one another handler took
	// The save-lock keys (cl_saveloc.qc, by scancode) and any other key bound to
	// a save-lock or saveloc command do nothing in the mode: browsing or with a
	// go in flight a load moves the body from under the cursor and its event
	// reads as the go's answer; in the countdown a load took the hold over and
	// a delete let it go (round 19).  A vote gets the digits it takes, nothing
	// else (round 20).  S, ENTER and the arrows stay this mode's whatever they
	// are bound to -- but in the countdown, where they only wait to be held for
	// the release, a saveloc bind on one is swallowed too (round 20).
	// Round 21: browsing, the wheel is the cursor's whatever it is bound to (a
	// Momentum nav bind is a saveloc one, which the block below would swallow).
	if (!rw_cd)
	if (!rw_ack)
	if (scanx == K_MWHEELDOWN || scanx == K_MWHEELUP)
	{
		rw_i = rw_i + ((scanx == K_MWHEELDOWN) ? -10 : 10);
		Rewind_Cursor();
		return TRUE;
	}
	slk = (strstrofs(getkeybind(scanx), "sl_", 0) >= 0 || strstrofs(getkeybind(scanx), "saveloc", 0) >= 0);
	if (k < 0)
	if ((scanx >= '0' && scanx <= '9') || scanx == 'z' || slk)
	{
		if (Vote_Takes(scanx))
			return FALSE;
		if (!Rewind_SwHas(scanx))   // round 24: said once a press, not in silence
			print("^3rewind:^7 the save-lock waits for the rewind\n");
		Rewind_SwSet(scanx);
		return TRUE;
	}
	if (rw_cd)
	if (slk)
	if (k >= 0)
	{
		rw_kst[k] = 1;
		print("^3rewind:^7 the save-lock waits for the rewind\n");
		return TRUE;
	}
	if (rw_cd)
	{
		if (scanx == K_ESCAPE)      // go now rather than wait
		{
			rw_kst[k] = 1;
			rw_cd = cltime;
			return TRUE;
		}
		// Round 18: ENTER again would reach `bind enter say` and open the chat
		// draft, which swallows the releases of the keys held for the release.
		// A `+` bind on it still passes, as a held key.
		if (k == 1 || k == 2)
		if (substring(getkeybind(scanx), 0, 1) != "+")
		{
			rw_kst[k] = 1;
			return TRUE;
		}
		return FALSE;               // the keys the release will find held
	}
	// Rounds 26-27: with a go in flight a movement bind on S or an arrow passes,
	// as in the countdown -- the release hands back what is held.  A view turn
	// or a save-lock bind would act now (a refused go leaves the view turning, a
	// stored -sl_hold lets go of a later hold), so it is swallowed as before.
	if (rw_ack)
	if (k == 0 || k == 3 || k == 4)
	if (Rewind_MoveBind(getkeybind(scanx)))
		return FALSE;
	if (k >= 0)
		rw_kst[k] = 1;
	if (rw_ack)                     // a go in flight: one round trip
		return k >= 0;
	if (k == 3 || k == 4)
	{
		rw_dirat = cltime;
		rw_dir = (k == 3) ? -1 : 1;
		rw_i = rw_i + rw_dir;
		Rewind_Cursor();
		return TRUE;
	}
	if (k == 1 || k == 2)
	{
		Rewind_Go();
		return TRUE;
	}
	if (k == 0)
	{
		Rewind_Save();
		return TRUE;
	}
	if (k == 5)
	{
		Rewind_Leave();
		return TRUE;
	}
	return FALSE;
};

// Round 21: up -- browsing, a go in flight or counting down (SaveLoc_Console).
float() Rewind_Holds =
{
	return rw_on;
};

// Round 26: the keys the phase takes, for the chat draft to yield -- all six
// browsing or with a go in flight; counting down, ENTER and ESC (S and the
// arrows wait there for the release, so a chat bind on one is the draft's).
float(float scan) Rewind_Owns =
{
	local float k;

	if (!rw_on)
		return FALSE;
	// Round 27: browsing, the wheel is the cursor's whatever it is bound to.
	if (!rw_cd)
	if (!rw_ack)
	if (scan == K_MWHEELDOWN || scan == K_MWHEELUP)
		return TRUE;
	k = Rewind_KeyIx(scan);
	if (k < 0)
		return FALSE;
	if (rw_cd)
	{
		if (k == 1 || k == 2 || k == 5)
			return TRUE;
		return FALSE;
	}
	return TRUE;
};

// Round 19: a key the mode took is its until let go, also once the mode has
// closed under it -- ESC closing a rewind, or ESC's go-now -- whose auto-repeat
// reached the engine's own ESC, the menu, over a body just released.
float(float evtype, float scanx) Rewind_AfterTook =
{
	local float k;

	if (rw_on)
		return FALSE;
	if (Rewind_SwHas(scanx))        // round 21: a swallowed digit's repeats stay swallowed
	{
		if (evtype == IE_KEYUP)
		{
			Rewind_SwClear(scanx);
			return FALSE;
		}
		return evtype == IE_KEYDOWN;
	}
	k = Rewind_KeyIx(scanx);
	if (k < 0)
		return FALSE;
	if (rw_kst[k] != 1)
		return FALSE;
	if (evtype == IE_KEYDOWN)
	if (rw_krep)
		return TRUE;
	if (evtype == IE_KEYUP)         // a release swallowed elsewhere: Rewind_Frame
		rw_kst[k] = 0;
	return FALSE;
};

/*
  `rewind` opens, and while open is ESC.  The rest are harness handles a config
  can drive: `rewind go|save|status`, `rewind seek <seconds>` (negative: back
  from the head) and `rewind step <points>`.
*/
float() Rewind_Console =
{
	local string a;
	local float t, busy, k, kup, oth;

	if (argv(0) != "rewind")
		return FALSE;
	a = argv(1);
	busy = (!rw_on || rw_ack || rw_cd);
	if (a == "")
	{
		if (!rw_on)
			Rewind_Open();
		else if (!busy)
			Rewind_Leave();
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
	else if (a == "key")
	{
		// Harness: a key event as CSQC_InputEvent hands it over -- tracked, then
		// this mode's handler, or not, for `other` (an earlier handler took it).
		// Read first: what the handler runs must not decide what this prints.
		t = stof(argv(2));
		kup = (argv(3) == "up");
		oth = (argv(3) == "other" || argv(4) == "other");
		Rewind_Track(kup ? IE_KEYUP : IE_KEYDOWN, t);
		k = oth ? 0 : Rewind_InputEvent(kup ? IE_KEYUP : IE_KEYDOWN, t, 0, 0);
		print(sprintf("rewind: key %g %s -> %s\n", t, kup ? "up" : "down",
		              oth ? "other" : (k ? "taken" : "passed")));
	}
	else if (a == "status")
	{
		print(sprintf("rewind: on %g counting %g sent %g  cursor %g of %g  kept %g  resume %g\n",
		              rw_on, rw_cd ? 1 : 0, rw_ack ? 1 : 0, floor(rw_i), ln_n[tr_live],
		              !Rewind_Old(), rw_atres));
		print(sprintf("rewind: at %s  %s\n", Rewind_At(),
		              Time_TickString(tr_tick > 0 ? rint(tr_cur_t / tr_tick) : 0, tr_tick)));
		print(sprintf("rewind: pin %g serial %g\n", getstatf(STAT_FS_PIN), rw_serial));
	}
	return TRUE;
};

// A map change: the line is gone and the server has forgotten the pin.
void() Rewind_Reset =
{
	rw_on = rw_ack = rw_cd = rw_dir = rw_askat = rw_leave = rw_atres = 0;
	rw_resi = -1;
	tr_cur_on = FALSE;
	Rewind_SwReset();
};
