/*
  Patch 753: `!r`, `!m`, goto_start and the save-lock load key, predicted
  (goto_spawn was `!m` until Patch 845 made it the map's spawn; goto_start was `!r`
  until Patch 848 gave that to `reset`).

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

#define WOP_RING 64                 // a slot is held 64 commands past its answer: room for a held key
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
float  *wop_blind;              // Patch 759: WOPB_* -- sent unpredicted
float  wop_slot;                // the slot WarpOp_Queue just filled
vector wop_tgorg, wop_tgang, wop_tgvel;   // WarpOp_Row's answer: origin, pitch/yaw/duck, speed
float  wop_tok, wop_tokt;       // SV_SaveLocRate's bucket, mirrored

void() WarpOp_RegisterCvars =
{
	registercvar("cl_warpop", "1");
	registercommand("goto_start");
	registercommand("reset");
	registercommand("goto_spawn");
	registercommand("startmark");
	registercommand("mom_start_mark_set");
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
		wop_blind = memalloc(sizeof(float) * WOP_RING);
	}
	return TRUE;
};

#define WOPB_BLIND   1              // wop_blind: sent unpredicted; the server's answer moves it
#define WOPB_REFUSED 2              // ...and SV_SaveLocRate will refuse it: no move at all

// Patch 759: an op the server has not answered -- STAT_FS_WOPACK (which arrives
// with the rows the op moved) has not reached its command, and it was queued
// under a second ago (by then the server dropped it).
float(float i) WarpOp_Unanswered =
{
	if (wop_seq[i] == -1)
		return TRUE;
	if (wop_seq[i] <= 0 || wop_seq[i] <= getstatf(STAT_FS_WOPACK))
		return FALSE;
	return (cltime - wop_qt[i] < 1 && cltime >= wop_qt[i]);
};

// A slot not queued, answered and not still being replayed; -1 when the ring is busy.
float() WarpOp_Slot =
{
	local float i;

	for (i = 0; i < WOP_RING; i = i + 1)
		// Not one the replay can still reach from an older baseline (UPDATE_BACKUP).
		if (wop_seq[i] == 0 || (wop_seq[i] > 0 && wop_seq[i] + 64 <= servercommandframe))
		if (!WarpOp_Unanswered(i))
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
	wop_blind[i] = FALSE;
	wop_slot = i;
	return TRUE;
};

#define WOPP_LIST      1            // a load or step: the cursor stats are from before it
#define WOPP_MOVE      2            // anything but a release: `!r`'s leg may move under it
#define WOPP_BLINDLOAD 3            // a blind load: its row's speed is not known here

// An unanswered op of the kind asked about.
float(float what) WarpOp_Pending =
{
	local float i, op;

	if (!wop_seq)
		return FALSE;
	for (i = 0; i < WOP_RING; i = i + 1)
	{
		if (!WarpOp_Unanswered(i))
			continue;
		op = wop_op[i];
		if (what == WOPP_MOVE && op != WOP_RELEASE)
			return TRUE;
		if (what == WOPP_LIST && (op == WOP_LOAD || (op >= WOP_NEXT && op <= WOP_LAST)))
			return TRUE;
		if (what == WOPP_BLINDLOAD && op == WOP_LOAD && wop_blind[i] == WOPB_BLIND)
			return TRUE;
	}
	return FALSE;
};

// SV_SaveLocStep/First/Last's cursor arithmetic.
float(float op, float idx, float cnt) WarpOp_StepIdx =
{
	if (op == WOP_NEXT)
		return (idx < cnt) ? idx + 1 : 1;
	if (op == WOP_PREV)
		return (idx > 1) ? idx - 1 : cnt;
	if (op == WOP_FIRST)
		return 1;
	if (op == WOP_LAST)
		return cnt;
	return idx;                         // WOP_LOAD: the cursor row
};

/*
  The row a load or step lands on, after every load and step still unanswered,
  into wop_tgorg/tgang/tgvel (zero when FALSE).  FALSE when it is not one the
  server published for this cursor (the row itself, next, prev, first or last),
  or follows a blind load (whose hold the replay does not have): send it blind.
*/
float(float op) WarpOp_Row =
{
	local float cnt, i0, idx, i, j, bq, b;

	wop_tgorg = '0 0 0';
	wop_tgang = '0 0 0';
	wop_tgvel = '0 0 0';
	cnt = getstatf(STAT_FS_SAVECOUNT);
	i0 = getstatf(STAT_FS_SAVEINDEX);
	if (cnt < 1 || i0 < 1 || i0 > cnt)
		return FALSE;
	idx = i0;
	bq = 0;
	while (TRUE)
	{
		j = -1;
		for (i = 0; i < WOP_RING; i = i + 1)
			if (wop_op[i] == WOP_LOAD || (wop_op[i] >= WOP_NEXT && wop_op[i] <= WOP_LAST))
			if (wop_q[i] > bq && WarpOp_Unanswered(i))
			{
				if (j < 0)
					j = i;
				else if (wop_q[i] < wop_q[j])
					j = i;
			}
		if (j < 0)
			break;
		bq = wop_q[j];
		if (wop_blind[j] == WOPB_REFUSED)
			continue;                       // the server keeps its cursor
		if (wop_blind[j] == WOPB_BLIND && wop_op[j] == WOP_LOAD)
			return FALSE;
		idx = WarpOp_StepIdx(wop_op[j], idx, cnt);
	}
	idx = WarpOp_StepIdx(op, idx, cnt);
	if (idx == i0)
	{
		wop_tgorg = [getstatf(STAT_FS_SLORG), getstatf(STAT_FS_SLORG + 1), getstatf(STAT_FS_SLORG + 2)];
		wop_tgang = [getstatf(STAT_FS_SLANG), getstatf(STAT_FS_SLANG + 1), getstatf(STAT_FS_SLANG + 2)];
		wop_tgvel = [getstatf(STAT_FS_SLVEL), getstatf(STAT_FS_SLVEL + 1), getstatf(STAT_FS_SLVEL + 2)];
		return (wop_tgorg != '0 0 0');
	}
	if (idx == WarpOp_StepIdx(WOP_NEXT, i0, cnt))
		b = 0;
	else if (idx == WarpOp_StepIdx(WOP_PREV, i0, cnt))
		b = 1;
	else if (idx == 1)
		b = 2;
	else if (idx == cnt)
		b = 3;
	else
		return FALSE;
	b = STAT_FS_WOPROW + WOPROW_STRIDE * b;
	wop_tgorg = [getstatf(b), getstatf(b + 1), getstatf(b + 2)];
	wop_tgang = [getstatf(b + 3), getstatf(b + 4), getstatf(b + 5)];
	wop_tgvel = [getstatf(b + 6), getstatf(b + 7), getstatf(b + 8)];
	return (wop_tgorg != '0 0 0');
};

// One charge of SV_SaveLocRate's bucket; FALSE when the server would refuse.
float() WarpOp_Charge =
{
	if (cltime < wop_tokt)
		wop_tokt = cltime;
	wop_tok = min(SL_TOKRATE, wop_tok + (cltime - wop_tokt) * SL_TOKRATE);
	wop_tokt = cltime;
	if (wop_tok < 1)
		return FALSE;
	wop_tok = wop_tok - 1;
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
	local float i, blind;

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
	// Patch 759: any op still unanswered can move the leg or restore the run state
	// `!r`'s published destination was read from: sent in order, unpredicted.
	blind = (op == WOP_RESET && WarpOp_Pending(WOPP_MOVE));
	if (blind)
		ang_z = 0;
	if (!WarpOp_Queue(op, org, '0 0 0', ang, 0))
		return FALSE;
	if (blind)
		wop_blind[wop_slot] = WOPB_BLIND;
	return TRUE;
};

// The load key's sl_load + sl_hold.  Same gates as SaveLoc_PredictLoad's camera.
float() WarpOp_Load =
{
	local float relpending, blind, charged;

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
	// Patch 759: after any load or step still unanswered.  Sent in order either
	// way; unpredicted (blind) when its row is not published or the server's
	// bucket would refuse it, and the server's answer corrects it as before.
	blind = WarpOp_Row(WOP_LOAD) ? 0 : WOPB_BLIND;
	charged = WarpOp_Charge();
	if (!charged)
		blind = WOPB_REFUSED;
	if (!WarpOp_Queue(WOP_LOAD, wop_tgorg, wop_tgvel, [wop_tgang_x, wop_tgang_y, !blind], wop_tgang_z))
	{
		if (charged)
			wop_tok = wop_tok + 1;      // the stringcmd sent instead charges it
		return FALSE;
	}
	wop_blind[wop_slot] = blind;
	wop_loadvel = wop_tgvel;
	wop_loadseq = -1;
	wop_loadackat = 0;
	if (!blind)
	{
		// The hold's view lock keeps the save's aim from the first frame.
		rec_sl_holdang = [wop_tgang_x, wop_tgang_y, 0];
		rec_sl_holdang_ok = TRUE;
	}
	return TRUE;
};

/*
  Patch 759: 3/4/5/6 at one command -- SV_SaveLocStep/First/Last.  Every press is
  sent at once, in order; it is predicted when its row (WarpOp_Row) is published
  and the server's bucket has a charge, else blind.  A key's auto-repeat (rep)
  waits for the last step's answer and is dropped rather than sent blind.
  FALSE: send the stringcmd.
*/
float(float op, float rep) WarpOp_Step =
{
	local float blind, charged;

	if (!WarpOp_Able() || Trail_RequestBusy())
		return FALSE;
	SaveLoc_Resync();
	if (rec_sl_sent != getstatf(STAT_FS_SLACK))
		return FALSE;
	if (getstatf(STAT_FS_SAVECOUNT) < 1 || getstatf(STAT_FS_SAVEINDEX) < 1)
		return FALSE;
	if (rep)
	if (WarpOp_Pending(WOPP_LIST))
		return TRUE;
	blind = WarpOp_Row(op) ? 0 : WOPB_BLIND;
	if (rep && blind)
		return TRUE;
	charged = WarpOp_Charge();
	if (!charged)
	{
		if (rep)
			return TRUE;
		blind = WOPB_REFUSED;
	}
	if (!WarpOp_Queue(op, wop_tgorg, wop_tgvel, [wop_tgang_x, wop_tgang_y, !blind], wop_tgang_z))
	{
		if (charged)
			wop_tok = wop_tok + 1;      // the stringcmd sent instead charges it
		return rep;                     // a repeat with the ring full is dropped
	}
	wop_blind[wop_slot] = blind;
	if (!blind)
	if (rec_sl_holding)
	{
		// The hold's view lock and its release speed follow the row.
		rec_sl_holdang = [wop_tgang_x, wop_tgang_y, 0];
		rec_sl_holdang_ok = TRUE;
		wop_loadvel = wop_tgvel;
	}
	return TRUE;
};

// Letting go of a predicted hold.  The speed is the held row's, once the server
// says which row that is (3-6 can move it while held).  FALSE: send sl_holdoff.
float() WarpOp_Release =
{
	local vector v;

	v = wop_loadvel;
	if (getstatf(STAT_FS_HOLD))
	if (!WarpOp_Pending(WOPP_LIST))
		v = [getstatf(STAT_FS_HOLDVEL), getstatf(STAT_FS_HOLDVEL + 1), getstatf(STAT_FS_HOLDVEL + 2)];
	if (!wop_seq)
		return FALSE;
	if (!WarpOp_Queue(WOP_RELEASE, '0 0 0', v, '0 0 0', 0))
		return FALSE;
	if (WarpOp_Pending(WOPP_BLINDLOAD))
		wop_blind[wop_slot] = WOPB_BLIND;   // Patch 759: that load's speed is not known here
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
	local float i, j, op;

	// An op no command has carried in 0.25 s (CSQC_Input_Frame returning early
	// under a replay, spectate, rewind or ghost): send the old command, or for a
	// release nothing a rewind could be holding by now.  Oldest first.
	if (wop_seq)
		while (TRUE)
		{
			j = -1;
			for (i = 0; i < WOP_RING; i = i + 1)
				if (wop_seq[i] == -1)
				if (cltime - wop_qt[i] > 0.25 || cltime < wop_qt[i])
				{
					if (j < 0)
						j = i;
					else if (wop_q[i] < wop_q[j])
						j = i;
				}
			if (j < 0)
				break;
			{
				op = wop_op[j];
				wop_seq[j] = 0;
				if (op == WOP_RESET)
					localcmd("cmd zone_reset\n");
				else if (op == WOP_SPAWN)
					localcmd("cmd zone_restart\n");
				else if (op >= WOP_BONUS1)
					localcmd(sprintf("cmd say \"!b %g\"\n", op - WOP_BONUS1 + 1));
				else if (op >= WOP_STAGE1)
					localcmd(sprintf("cmd say \"!s %g\"\n", op - WOP_STAGE1 + 1));
				// A step is dropped: the replay, rewind or spectate that stopped the
				// commands is a state its load would end.
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
	if (wop_blind[i])
		return;
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
	// Patch 1025: the ground this move starts from, for cl_triggers.qc's OnJump edge.
	tg_pmseq = seq;
	tg_pmground = predinput_onground;
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
	local float n;
	local string action;

	if (!strcmp(argv(0), "startmark") || !strcmp(argv(0), "mom_start_mark_set"))
	{
		action = argv(1);
		if (argv_start_index(2) < 0)
		{
			if (argv_start_index(1) < 0 || !strcmp(action, "set"))
			{
				localcmd("cmd startmark set\n");
				return TRUE;
			}
			if (!strcmp(action, "clear"))
			{
				localcmd("cmd startmark clear\n");
				return TRUE;
			}
			if (!strcmp(action, "status"))
			{
				localcmd("cmd startmark status\n");
				return TRUE;
			}
		}
		print("startmark [set|clear|status]\n");
		return TRUE;
	}

	// Patch 848: reset is `!r`, the start of the leg you are on (mid-run past the leg's first
	// segment, a stage restart: SV_TimerWouldRestartSeg). goto_start is the start of the run:
	// `!r` too, keeping its save in the box (P415) and its latched zone, except there, where it
	// is the track's start, `!m` or `!b N`.
	if (argv(0) == "reset")
	{
		if (!WarpOp_Reset(WOP_RESET))
			localcmd("cmd zone_reset\n");
		return TRUE;
	}
	if (argv(0) == "goto_start")
	{
		if (getstatf(STAT_FS_TIMERSTATE) == TS_RUNNING)
		if (getstatf(STAT_FS_TIMERSEG) > getstatf(STAT_FS_TIMERSTARTSEG))
		{
			n = getstatf(STAT_FS_TIMERTRACK);     // 0 main, N bonus N
			if (n > 0)
			{
				if (n > WOP_BONUSES)
					localcmd(sprintf("cmd say \"!b %g\"\n", n));
				else if (!WarpOp_Reset(WOP_BONUS1 + n - 1))
					localcmd(sprintf("cmd say \"!b %g\"\n", n));
			}
			else if (!WarpOp_Reset(WOP_SPAWN))
				localcmd("cmd zone_restart\n");
			return TRUE;
		}
		if (!WarpOp_Reset(WOP_RESET))
			localcmd("cmd zone_reset\n");
		return TRUE;
	}
	// Patch 845: the map's spawn entity, where joining puts you, not `!m`'s start zone.
	// A respawn, so not predicted.
	if (argv(0) == "goto_spawn")
	{
		localcmd("cmd zone_spawn\n");
		return TRUE;
	}
	return FALSE;
};
