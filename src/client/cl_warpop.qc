/*
  Patch 753: `!r`, `!m`, goto_start/goto_spawn and the save-lock load key, predicted.

  Each op rides ONE outgoing usercmd's impulse (WOP_*); the server applies it at
  that command (SV_WarpOpCommand) and CSQC_PredictPlayerPreMove below applies the
  same body at the same command on every replay, so the body moves on the press
  and the server's snapshot agrees with it instead of correcting it.  The body
  comes from the server's own answers published beforehand: STAT_FS_WOPR/WOPM
  (P680's read-only reset destination) and the cursor save's STAT_FS_SLORG/SLANG/
  SLVEL.  A refused or stale op is corrected like any misprediction.

  Only when the server publishes `fs_wop` (it has P675's command context) and the
  engine is running the pre-move hook (P672, cl_predict_qchook); otherwise every
  caller sends the old command.  cl_warpop 0 turns it off.
*/
// P672's pre-move globals (engine pr_csqc.c CSQC_PredictPlayerPreMove).
float predinput_apply;
vector predinput_origin;
vector predinput_velocity;
float predinput_onground;
float predinput_pmtype;
float predinput_forceduck;
float predinput_held;           // Patch 754: the engine predicts through PM_NONE (this server's holds)

#define WOP_PM_NORMAL 0
#define WOP_PM_NONE   5
#define WOP_BODY  1
#define WOP_MODE  2
#define WOP_DUCK  4
#define WOP_HOLD  8
#define WOP_CLEARCARRIER 16

#define WOP_RING 16
float  *wop_seq;                // the command it rode; -1 queued; 0 free
float  *wop_op;
float  *wop_q;                  // queue order while queued
float  *wop_duck;
float  *wop_qt;                 // cltime it was queued, for WarpOp_Frame's expiry
vector *wop_org;
vector *wop_vel;
vector *wop_ang;                // pitch, yaw, 1 = turn the view
float  wop_qn;
float  wop_premove_t;           // cltime the engine last ran the pre-move hook
float  wop_inputt;              // cltime WarpOp_InputFrame last ran (not under cl_threadedphysics)
float  wop_heldmode;            // the mode a predicted load held from; its release returns to it
float  wop_loadseq;             // the last load's command, for the refusal check
float  wop_loadackat;
vector wop_loadvel;
float  wop_relseq;              // the release's command (-1 queued) until the server lets go
float  wop_relat;

// Patch 759: STAT_FS_WOPLEGS parsed -- stage N at N - 1, bonus N at WOP_STAGES + N - 1.
#define WOP_LEGS 46
vector *wop_legorg;
vector *wop_legang;             // pitch, yaw, WOPD_* (WOPD_NONE: no answer)
string wop_legsrc;              // the six strings they were parsed from
// Steps pressed while a load or step is unanswered, in order (WarpOp_Frame).
float  wop_defer[4];
float  wop_defern, wop_defert;

void() WarpOp_RegisterCvars =
{
	registercvar("cl_warpop", "1");
	registercommand("goto_start");
	registercommand("goto_spawn");
};

float() WarpOp_Able =
{
	if (!cvar("cl_warpop") || serverkey("fs_wop") != "1")
		return FALSE;
	if (cltime - wop_premove_t > 0.5 || cltime < wop_premove_t)
		return FALSE;
	if (cltime - wop_inputt > 0.25 || cltime < wop_inputt)
		return FALSE;                   // nothing would carry the op to the server
	if (!LT_StatsAreMine() || Spec_Active() || rec_wt_on || rec_wt_open || rec_gh_on || rw_on)
		return FALSE;
	if (!wop_seq)
	{
		wop_seq  = memalloc(sizeof(float) * WOP_RING);
		wop_op   = memalloc(sizeof(float) * WOP_RING);
		wop_q    = memalloc(sizeof(float) * WOP_RING);
		wop_duck = memalloc(sizeof(float) * WOP_RING);
		wop_qt   = memalloc(sizeof(float) * WOP_RING);
		wop_org  = memalloc(sizeof(vector) * WOP_RING);
		wop_vel  = memalloc(sizeof(vector) * WOP_RING);
		wop_ang  = memalloc(sizeof(vector) * WOP_RING);
	}
	return TRUE;
};

// A slot not queued and not still being replayed; -1 when the ring is busy.
float() WarpOp_Slot =
{
	local float i;

	for (i = 0; i < WOP_RING; i = i + 1)
		// Not one the replay can still reach from an older baseline (UPDATE_BACKUP).
		if (wop_seq[i] == 0 || (wop_seq[i] > 0 && wop_seq[i] + 64 <= servercommandframe))
			return i;
	return -1;
};

float(float op, vector org, vector vel, vector ang, float duck) WarpOp_Queue =
{
	local float i;

	i = WarpOp_Slot();
	if (i < 0)
		return FALSE;
	wop_qn = wop_qn + 1;
	wop_seq[i]  = -1;
	wop_q[i]    = wop_qn;
	wop_op[i]   = op;
	wop_org[i]  = org;
	wop_vel[i]  = vel;
	wop_ang[i]  = ang;
	wop_duck[i] = duck;
	wop_qt[i]   = cltime;
	return TRUE;
};

// CSQC_Input_Frame (it tokenizes): STAT_FS_WOPLEGS into the leg arrays when it changes.
void() WarpOp_Legs =
{
	local float k, i, c, n, slot;
	local string all, w;

	all = "";
	for (k = 0; k < WOPLEG_CHUNKS; k = k + 1)
		all = strcat(all, getstats(STAT_FS_WOPLEGS + k), "|");
	if (!strcmp(all, wop_legsrc))
		return;
	if (wop_legsrc != "")
		strunzone(wop_legsrc);
	wop_legsrc = strzone(all);
	if (!wop_legorg)
	{
		wop_legorg = memalloc(sizeof(vector) * WOP_LEGS);
		wop_legang = memalloc(sizeof(vector) * WOP_LEGS);
	}
	for (i = 0; i < WOP_LEGS; i = i + 1)
		wop_legang[i] = '0 0 0';
	for (k = 0; k < WOPLEG_CHUNKS; k = k + 1)
	{
		c = tokenize(getstats(STAT_FS_WOPLEGS + k));
		for (i = 0; i + 7 < c; i = i + 8)
		{
			w = argv(i);
			n = stof(argv(i + 1));
			slot = -1;
			if (w == "s" && n >= 1 && n <= WOP_STAGES)
				slot = n - 1;
			if (w == "b" && n >= 1 && n <= WOP_BONUSES)
				slot = WOP_STAGES + n - 1;
			if (slot < 0)
				continue;
			wop_legorg[slot] = [stof(argv(i + 2)), stof(argv(i + 3)), stof(argv(i + 4))];
			wop_legang[slot] = [stof(argv(i + 5)), stof(argv(i + 6)), stof(argv(i + 7))];
		}
	}
};

// `!r`, `!m`, `!s N`, `!b N` (WOP_RESET, WOP_SPAWN, WOP_STAGE1 + N - 1,
// WOP_BONUS1 + N - 1).  FALSE: send the old command instead.
float(float op) WarpOp_Reset =
{
	local vector org, ang;
	local float i;

	if (!WarpOp_Able() || rec_sl_holding || Trail_RequestBusy())
		return FALSE;
	SaveLoc_Resync();
	if (rec_sl_sent != getstatf(STAT_FS_SLACK))
		return FALSE;                   // an sl_ command in flight would land after the op
	if (op == WOP_SPAWN)
	{
		org = [getstatf(STAT_FS_WOPM), getstatf(STAT_FS_WOPM + 1), getstatf(STAT_FS_WOPM + 2)];
		ang = [getstatf(STAT_FS_WOPMANG), getstatf(STAT_FS_WOPMANG + 1), getstatf(STAT_FS_WOPMANG + 2)];
	}
	else if (op == WOP_RESET)
	{
		org = [getstatf(STAT_FS_WOPR), getstatf(STAT_FS_WOPR + 1), getstatf(STAT_FS_WOPR + 2)];
		ang = [getstatf(STAT_FS_WOPRANG), getstatf(STAT_FS_WOPRANG + 1), getstatf(STAT_FS_WOPRANG + 2)];
	}
	else
	{
		if (!wop_legang)
			return FALSE;
		i = (op >= WOP_BONUS1) ? WOP_STAGES + op - WOP_BONUS1 : op - WOP_STAGE1;
		org = wop_legorg[i];
		ang = wop_legang[i];
	}
	if (ang_z != WOPD_KEEP && ang_z != WOPD_ANG)
		return FALSE;
	ang_z = (ang_z == WOPD_ANG);
	return WarpOp_Queue(op, org, '0 0 0', ang, 0);
};

// Patch 759: the newest load or step the server has not answered (its ring slot),
// or -1.  While there is one, the cursor rows on the stats are from before it.
float() WarpOp_ListLast =
{
	local float i, op, best, bq;

	best = -1;
	bq = 0;
	if (!wop_seq)
		return -1;
	for (i = 0; i < WOP_RING; i = i + 1)
	{
		op = wop_op[i];
		if (op == WOP_LOAD || (op >= WOP_NEXT && op <= WOP_LAST))
		if (wop_seq[i] == -1 || wop_seq[i] > servercommandframe)
		if (wop_q[i] > bq)
		{
			best = i;
			bq = wop_q[i];
		}
	}
	return best;
};

// The load key's sl_load + sl_hold.  Same gates as SaveLoc_PredictLoad's camera.
float() WarpOp_Load =
{
	local vector org, ang, a;
	local float relpending, j;

	// A release still in flight is ordered before this load (both ride commands);
	// otherwise a hold the server still reports is not ours to stack on.
	relpending = (wop_relseq != 0);
	wop_relseq = 0;                     // a new hold: the last release's backstop is moot
	if (!WarpOp_Able() || Trail_RequestBusy())
		return FALSE;
	if (getstatf(STAT_FS_HOLD) && !relpending)
		return FALSE;
	SaveLoc_Resync();
	if (rec_sl_sent != getstatf(STAT_FS_SLACK))
		return FALSE;                   // a list command is in flight: the row may be stale
	if (getstatf(STAT_FS_SAVECOUNT) < 1 || getstatf(STAT_FS_SAVEINDEX) < 1)
		return FALSE;
	j = WarpOp_ListLast();
	if (j >= 0)
	{
		// Patch 759: the cursor is the row that load or step put it on.
		org = wop_org[j];
		a = wop_ang[j];
		ang = [a_x, a_y, wop_duck[j]];
		wop_loadvel = wop_vel[j];
	}
	else
	{
		org = [getstatf(STAT_FS_SLORG), getstatf(STAT_FS_SLORG + 1), getstatf(STAT_FS_SLORG + 2)];
		ang = [getstatf(STAT_FS_SLANG), getstatf(STAT_FS_SLANG + 1), getstatf(STAT_FS_SLANG + 2)];
		wop_loadvel = [getstatf(STAT_FS_SLVEL), getstatf(STAT_FS_SLVEL + 1), getstatf(STAT_FS_SLVEL + 2)];
	}
	if (org == '0 0 0')
		return FALSE;
	if (!WarpOp_Queue(WOP_LOAD, org, wop_loadvel, [ang_x, ang_y, 1], ang_z))
		return FALSE;
	wop_loadseq = -1;
	wop_loadackat = 0;
	// The hold's view lock keeps the save's aim from the first frame.
	rec_sl_holdang = [ang_x, ang_y, 0];
	rec_sl_holdang_ok = TRUE;
	return TRUE;
};

string(float op) WarpOp_StepCmd =
{
	if (op == WOP_PREV)
		return "sl_prev";
	if (op == WOP_FIRST)
		return "sl_first";
	if (op == WOP_LAST)
		return "sl_last";
	return "sl_next";
};

// Patch 759: 3/4/5/6 at one command -- SV_SaveLocStep/First/Last on the row the
// server published for this cursor (STAT_FS_WOPROW).  FALSE: send the stringcmd.
float(float op) WarpOp_StepNow =
{
	local float b;
	local vector org, ang, vel;

	if (!WarpOp_Able() || Trail_RequestBusy())
		return FALSE;
	SaveLoc_Resync();
	if (rec_sl_sent != getstatf(STAT_FS_SLACK))
		return FALSE;
	if (WarpOp_ListLast() >= 0)
		return FALSE;
	if (getstatf(STAT_FS_SAVECOUNT) < 1 || getstatf(STAT_FS_SAVEINDEX) < 1)
		return FALSE;
	b = STAT_FS_WOPROW + WOPROW_STRIDE * (op - WOP_NEXT);
	org = [getstatf(b), getstatf(b + 1), getstatf(b + 2)];
	if (org == '0 0 0')
		return FALSE;                   // a server before Patch 759
	ang = [getstatf(b + 3), getstatf(b + 4), getstatf(b + 5)];
	vel = [getstatf(b + 6), getstatf(b + 7), getstatf(b + 8)];
	if (!WarpOp_Queue(op, org, vel, [ang_x, ang_y, 1], ang_z))
		return FALSE;
	if (rec_sl_holding)
	{
		// The hold's view lock and its release speed follow the row.
		rec_sl_holdang = [ang_x, ang_y, 0];
		rec_sl_holdang_ok = TRUE;
		wop_loadvel = vel;
	}
	return TRUE;
};

// A step pressed while another load or step is unanswered waits for it: its row
// is not on the stats until then, and a stringcmd sent now could run first.
float(float op) WarpOp_Step =
{
	if (wop_defern > 0 || WarpOp_ListLast() >= 0)
	{
		if (!WarpOp_Able())
			return FALSE;
		if (wop_defern < 4)
		{
			if (!wop_defern)
				wop_defert = cltime;
			wop_defer[wop_defern] = op;
			wop_defern = wop_defern + 1;
		}
		return TRUE;
	}
	return WarpOp_StepNow(op);
};

// Letting go of a predicted hold.  The speed is the held row's, once the server
// says which row that is (3-6 can move it while held).  FALSE: send sl_holdoff.
float() WarpOp_Release =
{
	local vector v;

	v = wop_loadvel;
	if (getstatf(STAT_FS_HOLD))
	if (WarpOp_ListLast() < 0)
		v = [getstatf(STAT_FS_HOLDVEL), getstatf(STAT_FS_HOLDVEL + 1), getstatf(STAT_FS_HOLDVEL + 2)];
	if (!wop_seq)
		return FALSE;
	if (!WarpOp_Queue(WOP_RELEASE, '0 0 0', v, '0 0 0', 0))
		return FALSE;
	wop_relseq = -1;
	wop_relat = 0;
	return TRUE;
};

/*
  The release's backstop, once its command is acknowledged and the server still
  holds (the command lost to 3+ dropped packets, or trimmed to kind 0).  Not sent
  with the release: a reliable stringcmd runs before its packet's moves, so on a
  fast tap it landed ahead of the load's command and released nothing.
*/
void() WarpOp_Frame =
{
	local float i, op;

	// An op no command has carried in 0.25 s (CSQC_Input_Frame returning early
	// under a replay, spectate, rewind or ghost): send the old command, or for a
	// release nothing a rewind could be holding by now.
	if (wop_seq)
		for (i = 0; i < WOP_RING; i = i + 1)
			if (wop_seq[i] == -1)
			if (cltime - wop_qt[i] > 0.25 || cltime < wop_qt[i])
			{
				op = wop_op[i];
				wop_seq[i] = 0;
				if (op == WOP_RESET)
					localcmd("cmd zone_reset\n");
				else if (op == WOP_SPAWN)
					localcmd("cmd zone_restart\n");
				else if (op >= WOP_BONUS1)
					localcmd(sprintf("cmd say \"!b %g\"\n", op - WOP_BONUS1 + 1));
				else if (op >= WOP_STAGE1)
					localcmd(sprintf("cmd say \"!s %g\"\n", op - WOP_STAGE1 + 1));
				else if (op >= WOP_NEXT)
					SaveLoc_Cmd(WarpOp_StepCmd(op));
				else if (op == WOP_LOAD && rec_sl_wophold)
				{
					rec_sl_wophold = FALSE;
					SaveLoc_Release();
				}
				else if (op == WOP_RELEASE)
				{
					wop_relseq = 0;
					if (!rw_on)
						SaveLoc_Cmd("sl_holdoff");
				}
			}

	// Patch 759: the next waiting step, once nothing ahead of it is unanswered
	// (or after 1 s, as the stringcmd).
	if (wop_defern > 0)
	if (WarpOp_ListLast() < 0 || cltime - wop_defert > 1 || cltime < wop_defert)
	{
		op = wop_defer[0];
		for (i = 1; i < wop_defern; i = i + 1)
			wop_defer[i - 1] = wop_defer[i];
		wop_defern = wop_defern - 1;
		wop_defert = cltime;
		if (WarpOp_ListLast() >= 0)
			SaveLoc_Cmd(WarpOp_StepCmd(op));
		else if (!WarpOp_StepNow(op))
			SaveLoc_Cmd(WarpOp_StepCmd(op));
	}

	if (wop_relseq <= 0 || servercommandframe < wop_relseq)
		return;
	if (!getstatf(STAT_FS_HOLD))
	{
		wop_relseq = 0;
		return;
	}
	if (!wop_relat)
		wop_relat = cltime;
	if (cltime - wop_relat > 0.3)
	{
		wop_relseq = 0;
		SaveLoc_Cmd("sl_holdoff");
	}
};

// The load's command has been acknowledged and no hold came: it was refused.
float() WarpOp_LoadRefused =
{
	if (wop_loadseq <= 0 || servercommandframe < wop_loadseq)
		return FALSE;
	if (!wop_loadackat)
		wop_loadackat = cltime;
	return (!getstatf(STAT_FS_HOLD) && cltime - wop_loadackat > 0.3);
};

// CSQC_Input_Frame: the oldest queued op rides this command.
void() WarpOp_InputFrame =
{
	local float i, best, bq;
	local vector a;

	// Only where PM_NONE is a hold this module can release (sv_nqplayerphysics is not).
	predinput_held = (cvar("cl_warpop") && serverkey("fs_wop") == "1");
	wop_inputt = cltime;
	if (predinput_held)
		WarpOp_Legs();
	if (!wop_seq)
		return;
	best = -1;
	bq = 0;
	for (i = 0; i < WOP_RING; i = i + 1)
		if (wop_seq[i] == -1)
		if (best < 0 || wop_q[i] < bq)
		{
			best = i;
			bq = wop_q[i];
		}
	if (best < 0)
		return;
	wop_seq[best] = clientcommandframe;
	input_impulse = wop_op[best];
	a = wop_ang[best];
	if (a_z)
	{
		a_z = 0;
		input_angles = a;
		setproperty(VF_CL_VIEWANGLES, a);
	}
	if (wop_op[best] == WOP_LOAD)
		wop_loadseq = clientcommandframe;
	if (wop_op[best] == WOP_RELEASE)
		wop_relseq = clientcommandframe;
	dprint(sprintf("warpop: %g on command %g\n", wop_op[best], clientcommandframe));
};

// The server's body for op `op` (ring slot i), at the first piece of its command.
void(float op, float i) WarpOp_Apply =
{
	if (op == WOP_RESET || op == WOP_SPAWN || op >= WOP_STAGE1)
	{
		// SV_ZoneMoveAt: origin, speed zero, carrier cleared, ground and duck kept.
		predinput_apply = WOP_BODY | WOP_CLEARCARRIER;
		predinput_origin = wop_org[i];
		predinput_velocity = '0 0 0';
		if (predinput_pmtype == WOP_PM_NONE)
		{
			predinput_apply = predinput_apply | WOP_MODE;
			predinput_pmtype = WOP_PM_NORMAL;
		}
	}
	else if (op == WOP_LOAD)
	{
		// SV_SaveLocPlace + SV_SaveLocHold: the save's origin and duck, off the
		// ground, carrier cleared, held still (MOVETYPE_NONE).
		predinput_apply = WOP_BODY | WOP_MODE | WOP_DUCK | WOP_CLEARCARRIER;
		predinput_origin = wop_org[i];
		predinput_velocity = '0 0 0';
		predinput_onground = 0;
		wop_heldmode = predinput_pmtype;    // SV_SaveLocHold's rec_sl_holdmove
		predinput_pmtype = WOP_PM_NONE;
		predinput_forceduck = wop_duck[i] ? 2 : 1;
	}
	else if (op >= WOP_NEXT && op <= WOP_LAST)
	{
		// SV_SaveLocLoad: the row's origin, speed and duck, off the ground,
		// carrier cleared; a hold stays held at speed zero.
		predinput_apply = WOP_BODY | WOP_DUCK | WOP_CLEARCARRIER;
		predinput_origin = wop_org[i];
		predinput_velocity = (predinput_pmtype == WOP_PM_NONE) ? '0 0 0' : wop_vel[i];
		predinput_onground = 0;
		predinput_forceduck = wop_duck[i] ? 2 : 1;
	}
	else if (op == WOP_RELEASE)
	{
		if (predinput_pmtype != WOP_PM_NONE)
			return;                     // nothing held on this replay
		// SV_SaveLocRelease; SV_SaveLocHoldFrame cleared the carrier every packet.
		predinput_apply = WOP_BODY | WOP_MODE | WOP_CLEARCARRIER;
		predinput_velocity = wop_vel[i];
		predinput_pmtype = (wop_heldmode == WOP_PM_NONE) ? WOP_PM_NORMAL : wop_heldmode;
	}
};

// Every replay of every unacknowledged command.
void(float seat, float seq, float seconds, float offset) CSQC_PredictPlayerPreMove =
{
	local float i;

	wop_premove_t = cltime;
	if (!seat)
	if (offset == 0)
	if (wop_seq)
		for (i = 0; i < WOP_RING; i = i + 1)
			if (wop_seq[i] == seq)
			{
				WarpOp_Apply(wop_op[i], i);
				break;
			}
	// The spectate hold runs no ticks and touches nothing (run_pmhold, msec 0);
	// a save-lock hold runs PM_NONE ticks and triggers, so it is not held here.
	if (predinput_pmtype == WOP_PM_NONE)
	if (getstatf(STAT_FS_SPEC))
		predinput_apply = predinput_apply | WOP_HOLD;
};

// cl_triggers.qc's CSQC_PredictPlayerMove: a reset that turns the view registers
// the turn as a predicted snap (Patch 396), so the server's fixangle a round trip
// later is recognized instead of undoing the mouse movement made since.
void(float seat, float seq) WarpOp_PostMove =
{
	local float i;
	local vector a;

	if (seat || !wop_seq)
		return;
	for (i = 0; i < WOP_RING; i = i + 1)
		if (wop_seq[i] == seq)
		{
			a = wop_ang[i];
			if (a_z)
			if (wop_op[i] != WOP_RELEASE)
			if (checkcommand("predangle_dump") == 1)
			{
				predmove_anglesnap = [a_x, a_y, 0];
				predmove_fixangle = 1;
			}
			return;
		}
};

// `say !r` / `!m` / `!s N` / `!b N`, from a bind (CSQC_ChatSay) or the chat box.
float(string text) WarpOp_Chat =
{
	local float sp, n, i, c;
	local string w, tail;

	text = strtrim(text);
	if (substring(text, 0, 1) == "\"" && substring(text, strlen(text) - 1, 1) == "\"")
		text = strtrim(substring(text, 1, strlen(text) - 2));
	if (text == "!r")
		return WarpOp_Reset(WOP_RESET);
	if (text == "!m")
		return WarpOp_Reset(WOP_SPAWN);
	// Patch 759: split as SV_ParseClientCommand does -- the word, then digits only.
	text = strtolower(text);
	sp = strstrofs(text, " ", 0);
	w = text;
	tail = "";
	if (sp >= 0)
	{
		w = substring(text, 0, sp);
		tail = substring(text, sp + 1, strlen(text) - (sp + 1));
	}
	if (w != "!s" && w != "!b")
		return FALSE;
	for (i = 0; i < strlen(tail); i = i + 1)
	{
		c = str2chr(tail, i);
		if (c < '0' || c > '9')
			return FALSE;
	}
	n = max(1, stof(tail));
	if (w == "!s")
	{
		if (n > WOP_STAGES)
			return FALSE;
		return WarpOp_Reset(WOP_STAGE1 + n - 1);
	}
	if (n > WOP_BONUSES)
		return FALSE;
	return WarpOp_Reset(WOP_BONUS1 + n - 1);
};

float() WarpOp_Console =
{
	if (argv(0) == "goto_start")
	{
		if (!WarpOp_Reset(WOP_RESET))
			localcmd("cmd zone_reset\n");
		return TRUE;
	}
	if (argv(0) == "goto_spawn")
	{
		if (!WarpOp_Reset(WOP_SPAWN))
			localcmd("cmd zone_restart\n");
		return TRUE;
	}
	return FALSE;
};
