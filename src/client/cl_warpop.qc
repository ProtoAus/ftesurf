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
float predinput_entgravity;     // P1211: preloaded with the server's gravity; WOP_GRAVITY sets this piece's
float predinput_version;        // P1211: 1211+ on an engine that takes WOP_GRAVITY (older ones reject the mask)

#define WOP_PM_NORMAL 0
#define WOP_PM_NONE   5
#define WOP_BODY  1
#define WOP_MODE  2
#define WOP_DUCK  4
#define WOP_HOLD  8
#define WOP_CLEARCARRIER 16
#define WOP_GRAVITY 32                  // P1211: engine PMPI_GRAVITY

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
float  wop_loadpred, wop_loadsteps; // P1384: it was predicted; a step was still unanswered before it
float  wop_loadackat;
vector wop_loadvel;
float  wop_relseq;              // the release's command (-1 queued) until the server lets go
float  wop_rellast, wop_loadlast;   // P1238: the last release and load commands sent (not cleared on an ack)
// P1238: STAT_FS_WOPCUR parsed (WarpOp_Cur); wop_c_ok 0 on a lobby without it (the separate stats then).
float  wop_c_ok, wop_c_ack, wop_c_idx, wop_c_cnt, wop_c_slack;
vector wop_c_org[5], wop_c_ang[5], wop_c_vel[5];   // cursor, next, prev, first, last
string wop_c_src;
float wop_x_ok, wop_x_held;
vector wop_x_holdvel;             // actual held row, which can differ from a refused load's cursor
string wop_x_src, wop_x_cur;
vector wop_x_org[4], wop_x_ang[4], wop_x_vel[4]; // +2,-2,+3,-3 from the same C snapshot
float  wop_relat;
// A reset cancels local camera ownership, not the obligation to free an old hold.
float  wop_resetq, wop_resetseq, wop_resetat, wop_resetheld;

// Patch 759: STAT_FS_WOPLEGS parsed -- stage N at N - 1, bonus N at WOP_STAGES + N - 1.
#define WOP_LEGS 46
vector *wop_legorg;
vector *wop_legang;             // pitch, yaw, WOPD_* (WOPD_NONE: no answer)
string wop_legsrc;              // the six strings they were parsed from
float  *wop_blind;              // Patch 759: WOPB_* -- sent unpredicted
float  *wop_cap;                // P1547: a WOP_SAVE's row has been taken at its command (WarpOp_Apply)
float  wop_pmduck;              // P1547: the last predicted move's hull: 1 ducked, 0 standing, -1 neither
float  wop_saveseq, wop_saveat; // P1547: the carried WOP_SAVE's command, and since when it is acked unanswered
float  wop_saveafter;           // P1547: another op rode a command after it (the backstop then refuses)
float  wop_hst, wop_hs, wop_hd; // P1547: pm_standheight/pm_duckheight, read once a frame
float  wop_slot;                // the slot WarpOp_Queue just filled
vector wop_tgorg, wop_tgang, wop_tgvel;   // WarpOp_Row's answer: origin, pitch/yaw/duck, speed
float  wop_tok, wop_tokt;       // SV_SaveLocRate's bucket, mirrored
string wop_why;                 // Patch 1207: why the last WarpOp_Able/Reset said no (a constant)

void() WarpOp_RegisterCvars =
{
	registercvar("cl_warpop", "1");
	registercommand("goto_start");
	registercommand("reset");
	registercommand("goto_spawn");
	registercommand("goto");
	registercommand("startmark");
	registercommand("mom_start_mark_set");
};

// P1238: the prediction hook ran on this map and within the last frame or two (a slow first frame on
// a map is longer than 0.5 s: outra, starvald), and never more than 2 s ago.
float() WarpOp_HookAlive =
{
	return wop_premove_t > 0 && cltime >= wop_premove_t
	       && cltime - wop_premove_t <= min(2, max(0.5, 2.5 * clframetime));
};

float() WarpOp_Able =
{
	wop_why = "off (cl_warpop 0, or the server has no fs_wop)";
	if (!cvar("cl_warpop") || serverkey("fs_wop") != "1")
		return FALSE;
	// P1238: within a frame or two of the last hook, not 0.5 s of wall time: the first frames on a map
	// can each take longer (outra, starvald: 0.8 and 1.6 s), and the op then went unpredicted.
	wop_why = "no prediction hook in the last frames (this PC hosts the game, or prediction is off)";
	if (!WarpOp_HookAlive())
		return FALSE;
	wop_why = "no input frame to carry it";
	if (cltime - wop_inputt > 0.25 || cltime < wop_inputt)
		return FALSE;                   // nothing would carry the op to the server
	wop_why = "spectating, watching or rewinding";
	if (!LT_StatsAreMine() || Spec_Active() || rec_wt_on || rec_wt_open || rec_gh_on || rw_on)
		return FALSE;
	wop_why = "";
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
		wop_cap   = memalloc(sizeof(float) * WOP_RING);
	}
	return TRUE;
};

#define WOPB_BLIND   1              // wop_blind: sent unpredicted; the server's answer moves it
#define WOPB_REFUSED 2              // ...and SV_SaveLocRate will refuse it: no move at all

// Patch 759: an op the server has not answered -- STAT_FS_WOPACK (which arrives
// with the rows the op moved) has not reached its command, and it was queued
// under a second ago (by then the server dropped it).
float() WarpOp_Ack = { return wop_c_ok ? wop_c_ack : getstatf(STAT_FS_WOPACK); };
float() WarpOp_Idx = { return wop_c_ok ? wop_c_idx : getstatf(STAT_FS_SAVEINDEX); };
float() WarpOp_Cnt = { return wop_c_ok ? wop_c_cnt : getstatf(STAT_FS_SAVECOUNT); };

// CSQC_Input_Frame (it tokenizes): STAT_FS_WOPCUR into the cache when it changes.
// D carries the complete old C snapshot as one quoted token plus four rows.
// Prefer that whole snapshot: independently arriving C must never mix with D.
void() WarpOp_Chain =
{
	local string s;
	local float n, i, b, limit;

	s = getstats(STAT_FS_WOPCHAIN);
	if (!strcmp(s, wop_x_src))
		return;
	if (wop_x_src != "") strunzone(wop_x_src);
	if (wop_x_cur != "") strunzone(wop_x_cur);
	wop_x_src = strzone(s);
	wop_x_cur = "";
	wop_x_ok = FALSE;
	if (strlen(s) > WOPCHAIN_MAX)
		return;
	n = tokenize(s);
	if (n != 42)
		return;
	if (strcmp(argv(0), "D"))
		return;
	limit = stof("3.4028234663852886e38");
	for (i = 2; i < n; i = i + 1)
		if (!Watch_OwnViewNumber(argv(i), limit))
			return;
	wop_x_held = stof(argv(2));
	if (wop_x_held != 0 && wop_x_held != 1)
		return;
	wop_x_holdvel = [stof(argv(3)), stof(argv(4)), stof(argv(5))];
	wop_x_cur = strzone(argv(1));
	for (i = 0; i < 4; i = i + 1)
	{
		b = 6 + i * 9;
		wop_x_org[i] = [stof(argv(b)), stof(argv(b + 1)), stof(argv(b + 2))];
		wop_x_ang[i] = [stof(argv(b + 3)), stof(argv(b + 4)), stof(argv(b + 5))];
		wop_x_vel[i] = [stof(argv(b + 6)), stof(argv(b + 7)), stof(argv(b + 8))];
	}
	if (tokenize(wop_x_cur) != 50)
		return;
	if (strcmp(argv(0), "C"))
		return;
	for (i = 1; i < 50; i = i + 1)
		if (!Watch_OwnViewNumber(argv(i), limit))
			return;
	wop_x_ok = TRUE;
};

void() WarpOp_Cur =
{
	local string s;
	local float r;
	WarpOp_Chain();
	s = wop_x_ok ? wop_x_cur : getstats(STAT_FS_WOPCUR);
	if (!strcmp(s, wop_c_src))
		return;
	if (wop_c_src != "")
		strunzone(wop_c_src);
	wop_c_src = strzone(s);
	wop_c_ok = (tokenize(s) == 50 && argv(0) == "C");
	if (!wop_c_ok)
		return;
	wop_c_ack = stof(argv(1));
	wop_c_idx = stof(argv(2));
	wop_c_cnt = stof(argv(3));
	wop_c_slack = stof(argv(4));
	for (r = 0; r < 5; r = r + 1)
	{
		wop_c_org[r] = [stof(argv(5 + r * 9)), stof(argv(6 + r * 9)), stof(argv(7 + r * 9))];
		wop_c_ang[r] = [stof(argv(8 + r * 9)), stof(argv(9 + r * 9)), stof(argv(10 + r * 9))];
		wop_c_vel[r] = [stof(argv(11 + r * 9)), stof(argv(12 + r * 9)), stof(argv(13 + r * 9))];
	}
};

float(float i) WarpOp_Unanswered =
{
	if (wop_seq[i] == -1)
		return TRUE;
	if (wop_seq[i] <= 0 || wop_seq[i] <= WarpOp_Ack())
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
#define WOPP_HOLDROW   4            // a pending load/step not known to be rate-refused
#define WOPP_STEP      5            // P1384: a pending step (a load leaves the cursor where it is)
#define WOPP_RESET     6            // an ordered reset will release the preceding hold
#define WOPP_ANY       7            // P1547: any op (Trail_RequestFrame holds stringcmds behind it)

float(float what) WarpOp_Pending;
float() WarpOp_AnyPending = { return WarpOp_Pending(WOPP_ANY); };

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
		// P1547: a save too -- `!r` goes to the newest idle save in the leg's start zone (P415).
		if (what == WOPP_MOVE && op != WOP_RELEASE)
			return TRUE;
		if (what == WOPP_ANY)
			return TRUE;
		if (what == WOPP_RESET && (op == WOP_RESET || op == WOP_SPAWN || op >= WOP_STAGE1))
			return TRUE;
		if (what == WOPP_LIST && (op == WOP_LOAD || (op >= WOP_NEXT && op <= WOP_LAST)))
			return TRUE;
		if (what == WOPP_BLINDLOAD && op == WOP_LOAD && wop_blind[i] == WOPB_BLIND)
			return TRUE;
		if (what == WOPP_STEP && op >= WOP_NEXT && op <= WOP_LAST)
			return TRUE;
		if (what == WOPP_HOLDROW && wop_blind[i] != WOPB_REFUSED)
			if (op == WOP_LOAD || (op >= WOP_NEXT && op <= WOP_LAST))
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

float(float idx, float cnt, float delta) WarpOp_Offset =
{
	local float op;
	op = (delta < 0) ? WOP_PREV : WOP_NEXT;
	if (delta < 0) delta = -delta;
	while (delta > 0)
	{
		idx = WarpOp_StepIdx(op, idx, cnt);
		delta = delta - 1;
	}
	return idx;
};

// P1547: the newest WOP_SAVE the server has not answered, or -1.
float() WarpOp_SaveSlot =
{
	local float i, j;

	j = -1;
	if (!wop_seq)
		return j;
	for (i = 0; i < WOP_RING; i = i + 1)
		if (wop_op[i] == WOP_SAVE && WarpOp_Unanswered(i))
		if (j < 0 || wop_q[i] > wop_q[j])
			j = i;
	return j;
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
	// P1547: behind a save not yet answered the cursor is that save, its row the one this client took at
	// the save's command. A step's row count is not known here; a row not taken yet goes blind.
	j = WarpOp_SaveSlot();
	if (j >= 0)
	{
		if (op != WOP_LOAD || !wop_cap[j])
			return FALSE;
		SaveLoc_Resync();
		if (rec_sl_sent != getstatf(STAT_FS_SLACK))
			return FALSE;
		for (i = 0; i < WOP_RING; i = i + 1)
			if (wop_op[i] >= WOP_NEXT && wop_op[i] <= WOP_LAST)
			if (wop_q[i] > wop_q[j] && WarpOp_Unanswered(i))
				return FALSE;
		wop_tgorg = wop_org[j];
		wop_tgang = wop_ang[j];
		wop_tgang_z = wop_duck[j];
		wop_tgvel = wop_vel[j];
		return TRUE;
	}
	// P1238: string stats follow the numeric ones, so a fresh sl_save's ack (STAT_FS_SLACK) can land a
	// packet before the cursor string that answers it: predict nothing until they agree.
	if (wop_c_ok && wop_c_slack != getstatf(STAT_FS_SLACK))
		return FALSE;
	cnt = WarpOp_Cnt();
	i0 = WarpOp_Idx();
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
	if (idx == i0 && wop_c_ok)
	{
		wop_tgorg = wop_c_org[0];
		wop_tgang = wop_c_ang[0];
		wop_tgvel = wop_c_vel[0];
		return (wop_tgorg != '0 0 0');
	}
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
	{
		if (!wop_c_ok || !wop_x_ok)
			return FALSE;
		for (b = 0; b < 4; b = b + 1)
			if (idx == WarpOp_Offset(i0, cnt, ((b < 2) ? 2 : 3) * ((b & 1) ? -1 : 1)))
			{
				wop_tgorg = wop_x_org[b];
				wop_tgang = wop_x_ang[b];
				wop_tgvel = wop_x_vel[b];
				return (wop_tgorg != '0 0 0');
			}
		return FALSE;
	}
	if (wop_c_ok)
	{
		wop_tgorg = wop_c_org[b + 1];
		wop_tgang = wop_c_ang[b + 1];
		wop_tgvel = wop_c_vel[b + 1];
		return (wop_tgorg != '0 0 0');
	}
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
float(float op) WarpOp_ResetTry =
{
	local vector org, ang;
	local float i, blind, opsave, nodest;

	if (!WarpOp_Able())
		return FALSE;
	wop_why = "a trail request is busy";
	if (Trail_RequestBusy() && !Trail_RequestOpSave())     // P1547: carried after a save on a command
		return FALSE;
	opsave = (WarpOp_SaveSlot() >= 0);
	SaveLoc_Resync();
	wop_why = "a save command is in flight";
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
		wop_why = "no stage table yet";
		if (!wop_legang && !opsave)
			return FALSE;
		i = (op >= WOP_BONUS1) ? WOP_STAGES + op - WOP_BONUS1 : op - WOP_STAGE1;
		org = ang = '0 0 0';
		if (wop_legang)
		{
			org = wop_legorg[i];
			ang = wop_legang[i];
		}
	}
	wop_why = "the server published no destination";
	// P1547: behind a save on a command, unpredicted but on the same ordered stream: the stringcmd
	// could be run before the save (one reliable in flight, a lost packet).
	nodest = (ang_z != WOPD_KEEP && ang_z != WOPD_ANG);
	if (nodest && !opsave)
		return FALSE;
	ang_z = (ang_z == WOPD_ANG);
	// Patch 759: any op still unanswered can move the leg or restore the run state
	// `!r`'s published destination was read from: sent in order, unpredicted.
	blind = (rec_sl_holding || (op == WOP_RESET && WarpOp_Pending(WOPP_MOVE)) || nodest);
	if (blind)
		ang_z = 0;
	wop_why = "the op queue is full";
	if (!WarpOp_Queue(op, org, '0 0 0', ang, 0))
		return FALSE;
	if (blind)
		wop_blind[wop_slot] = WOPB_BLIND;
	// Keep an earlier load and this reset on the same ordered usercmd stream.
	// A reliable fallback can run before that load, putting the hold back again.
	if (rec_sl_holding || getstatf(STAT_FS_HOLD) || wop_resetq || wop_relseq)
	{
		wop_resetq = wop_q[wop_slot];
		wop_resetseq = -1;
		wop_resetat = 0;
	}
	SaveLoc_ResetHold();
	wop_relseq = wop_relat = 0; // the reset now owns the old hold's release obligation
	return TRUE;
};

// Patch 1207: a reset sent unpredicted says why in the prederror context.
float(float op) WarpOp_Reset =
{
	if (WarpOp_ResetTry(op))
		return TRUE;
	PE_Note(sprintf("warpop %g not predicted: %s", op, wop_why));
	PE_Expect("a reset sent unpredicted");     // P1238: every caller sends the plain command next
	wop_strat = cltime;
	return FALSE;
};

// The load key's sl_load + sl_hold.  Same gates as SaveLoc_PredictLoad's camera.
// The new owner, not an earlier reset, now decides when its hold is released.
void() WarpOp_HoldAdopt =
{
	wop_resetq = wop_resetseq = wop_resetat = 0;
};

float() WarpOp_Load =
{
	local float relpending, blind, charged;

	// A release still in flight is ordered before this load (both ride commands);
	// otherwise a hold the server still reports is not ours to stack on.
	relpending = (wop_relseq != 0);
	WarpOp_HoldAdopt(); // a newer load owns any subsequent hold
	wop_relseq = 0;                     // a new hold: the last release's backstop is moot
	wop_loadpred = FALSE;
	if (!WarpOp_Able())
		return FALSE;
	// P1544: SaveLoc_FifoLoad's pair is the queue. P1547: a save on a command is carried before this.
	if (Trail_RequestBusy() && !wop_fifoload && !Trail_RequestOpSave())
		return FALSE;
	// A pending reset also releases the old hold, before this load's command.
	if (getstatf(STAT_FS_HOLD) && !relpending && !WarpOp_Pending(WOPP_RESET))
		return FALSE;
	SaveLoc_Resync();
	if (rec_sl_sent != getstatf(STAT_FS_SLACK))
		return FALSE;                   // a list command is in flight: the row may be stale
	if (WarpOp_SaveSlot() < 0)          // P1547: else that save is the cursor
	if (getstatf(STAT_FS_SAVECOUNT) < 1 || getstatf(STAT_FS_SAVEINDEX) < 1)
		return FALSE;
	// Patch 759: after any load or step still unanswered.  Sent in order either
	// way; unpredicted (blind) when its row is not published or the server's
	// bucket would refuse it, and the server's answer corrects it as before.
	wop_loadsteps = WarpOp_Pending(WOPP_STEP);
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
	wop_loadpred = !blind;
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
  P1547: the live save at one command (SV_WarpOpCommand's WOP_SAVE), so a load pressed before its answer
  rides behind it, predicted from the row taken at the save's command (WarpOp_Apply). Only where the
  server's PlayerPreThink row is the one predicted here: not held (a held save keeps its row's speed),
  nothing blind and no sl_ stringcmd unanswered ahead of it (a reliable can run after a later command).
  FALSE: send sl_save. Its ticket is bound when a command carries it (Trail_OpSaveCarried).
*/
float(float charged) WarpOp_Save =
{
	local float i;

	if (!charged || serverkey("fs_wopsave") != "1" || !WarpOp_Able())
		return FALSE;
	// An impulse escapes a TAS pause and stops a tape or plan (sv_tas.h SV_TASPlan): the stringcmd does not.
	if ((getstatf(STAT_FS_TIMERFLAGS) & TF_TAS) || getstatf(STAT_FS_TASPAUSE) || getstatf(STAT_FS_TASPENDING) ||
	    getstatf(STAT_FS_TASPLANMODE) || getstatf(STAT_FS_TASREPLAY) == TAS_TAPE_ACTIVE ||
	    getstatf(STAT_FS_TASREPLAY) == TAS_TAPE_STAGING)
		return FALSE;
	if (rec_sl_holding || wop_pmduck < 0)
		return FALSE;
	// Held on the server: only with this client's release queued or carried and not yet acked (the
	// backstop's case would save the hold's row speed against a replay that has none).
	if (getstatf(STAT_FS_HOLD))
	if (!(wop_relseq < 0 || (wop_relseq > 0 && servercommandframe < wop_relseq)))
		return FALSE;
	if (cltime - wop_strat < 1 && cltime >= wop_strat)
		return FALSE;                   // a reset's stringcmd in flight could run after this command
	SaveLoc_Resync();
	if (rec_sl_sent != getstatf(STAT_FS_SLACK))
		return FALSE;
	for (i = 0; i < WOP_RING; i = i + 1)
		if (wop_blind[i] == WOPB_BLIND && WarpOp_Unanswered(i))
			return FALSE;
	if (!WarpOp_Queue(WOP_SAVE, '0 0 0', '0 0 0', '0 0 0', 0))
		return FALSE;
	wop_cap[wop_slot] = FALSE;
	wop_opsave = TRUE;
	tr_saveack = -1;
	if (tr_rep_raw >= 1)
	{
		tr_rep_ack = -1;
		tr_rep_go = FALSE;
	}
	return TRUE;
};

// P1547: a WOP_SAVE no command carried in time (WarpOp_Frame): the stringcmd it stood for, on its own ticket.
void() WarpOp_SaveExpired =
{
	SaveLoc_Resync();
	rec_sl_sent = rec_sl_sent + 1;
	localcmd(strcat("cmd ", Trail_Command("sl_save"), "\n"));
	if (tr_req_opsave && tr_req_wait == -1)
	{
		tr_req_wait = tr_saveack;
		tr_req_at = cltime;
	}
	tr_req_opsave = FALSE;
};

// P1547: a carried WOP_SAVE the server acked without answering (its command dropped: 3+ lost packets,
// a shortened command, a pause) is sent again as the stringcmd, so the save and what the FIFO queued
// behind it are not lost; it then saves wherever the server has the body. Not before 0.3 s plus 1.5
// pings (capped at 1 s) past the ack: an answer lost with its packet is sent again about a round trip
// later (sv_ents.c SV_RequeueFrame), and the save it answers did run. Refused once another op rode a
// command after it: that op ran first, and the save would copy where it put the body.
void() WarpOp_SaveFrame =
{
	local float ping;

	if (!tr_req_opsave || tr_req_wait <= 0 || wop_saveseq <= 0)
		return;
	if (servercommandframe < wop_saveseq || getstatf(STAT_FS_SLSAVEACK) == tr_req_wait)
	{
		wop_saveat = 0;
		return;
	}
	if (!wop_saveat || cltime < wop_saveat)
	{
		wop_saveat = cltime;
		tr_req_at = cltime;             // the FIFO's 5 s now counts from the ack, not the press
	}
	ping = bound(0, stof(getplayerkeyvalue(player_localnum, "ping")) / 1000, 1);
	if (cltime - wop_saveat <= 0.3 + 1.5 * ping)
		return;
	wop_saveseq = wop_saveat = 0;
	PE_Expect("a save on a command was not answered");
	if (wop_saveafter)
	{
		print("^3save: lost on the way to the server -- save again\n");
		tr_req_wait = tr_req_opsave = 0;
		Trail_ReplayClear();
		return;
	}
	SaveLoc_Resync();
	rec_sl_sent = rec_sl_sent + 1;
	localcmd(strcat("cmd ", Trail_Command("sl_save"), "\n"));
	tr_req_wait = tr_saveack;
	tr_req_at = cltime;
	tr_req_opsave = FALSE;
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
vector wop_relv;
// The release's speed into wop_relv; TRUE when it is not known here and the release would go blind.
float() WarpOp_RelVel =
{
	local vector v;
	local float blind;

	v = wop_loadvel;
	blind = FALSE;
	// A refused load advances the cursor without retargeting the hold. Only
	// pending non-refused loads/steps may predict a new row; otherwise use the
	// actual held speed in the SAME snapshot, never the cursor or stale HOLDVEL.
	// P1384: a predicted load not yet acknowledged is still the hold, past WarpOp_Unanswered's
	// 1 s too: a 1 s lead-in let go at a round trip over 1 s otherwise went blind. Not after any
	// step in this hold, which may have moved it (an aged or refused one included).
	if (wop_loadpred && !rec_sl_heldstep && !WarpOp_LoadAnswered())
		v = wop_loadvel;
	else if (WarpOp_Pending(WOPP_HOLDROW))
	{
		blind = !WarpOp_Row(WOP_LOAD);
		if (!blind)
			v = wop_tgvel;
	}
	else if (wop_c_ok)
	{
		blind = !(wop_x_ok && wop_x_held && wop_c_slack == getstatf(STAT_FS_SLACK));
		if (!blind)
			v = wop_x_holdvel;
	}
	else if (getstatf(STAT_FS_HOLD))
		v = [getstatf(STAT_FS_HOLDVEL), getstatf(STAT_FS_HOLDVEL + 1), getstatf(STAT_FS_HOLDVEL + 2)];
	wop_relv = v;
	return (blind || WarpOp_Pending(WOPP_BLINDLOAD));   // Patch 759: that load's speed is not known here
};

float() WarpOp_Release =
{
	local float blind;

	if (!wop_seq)
		return FALSE;
	blind = WarpOp_RelVel();
	if (!WarpOp_Queue(WOP_RELEASE, '0 0 0', wop_relv, '0 0 0', 0))
		return FALSE;
	if (blind)
		wop_blind[wop_slot] = WOPB_BLIND;
	wop_relseq = -1;
	wop_relat = 0;
	return TRUE;
};

// P1544: SaveLoc_LeadDone. A release on a command would go blind now (the cursor strings that carry the
// held row trail the numeric answer a packet): the view would stay parked a round trip, then snap.
float() WarpOp_RelBlind =
{
	if (!wop_seq)
		return FALSE;
	return WarpOp_RelVel();
};

// P1544: Watch_OpenIn sent sl_holdoff; a queued release would be carried after the replay, over its pin.
void() WarpOp_DropRelease =
{
	local float i;
	if (!wop_seq)
		return;
	// A load still queued could be carried after the sl_holdoff (the open fails, or closes at once):
	// keep its release behind it (review round 3).
	for (i = 0; i < WOP_RING; i = i + 1)
		if (wop_seq[i] == -1 && wop_op[i] == WOP_LOAD)
			return;
	for (i = 0; i < WOP_RING; i = i + 1)
		if (wop_seq[i] == -1 && wop_op[i] == WOP_RELEASE)
			wop_seq[i] = 0;
	wop_relseq = wop_relat = 0;
};

// A clean return discards queued actions as well as the accumulated usercmd.
// The existing warp/save client queues are connection-global, so clean return
// currently refuses split-screen rather than cancel another seat's actions.
// No localcmd/release fallback here: the server owns authoritative teardown.
void() WarpOp_PracticeReturnCancel =
{
	local float i;
	if (wop_seq)
		for (i = 0; i < WOP_RING; i = i + 1)
			wop_seq[i] = 0;
	wop_qn = wop_loadseq = wop_loadackat = wop_relseq = wop_relat = 0;
	wop_resetq = wop_resetseq = wop_resetat = 0;
	wop_rellast = wop_loadlast = 0;
	wop_heldmode = 0;
	wop_loadvel = '0 0 0';
	if (rec_sl_holdkey)
	{
		rec_sl_refkey = rec_sl_holdkey; // swallow old hold repeats until key-up
		rec_sl_refseen = cltime;
	}
	rec_sl_holding = rec_sl_holdkey = rec_sl_holdrep = rec_sl_holdseen = 0;
	rec_sl_holdang_ok = rec_sl_wophold = rec_sl_pv_on = rec_sl_upwait = rec_sl_pred = 0;   // P1227 review 1
	rec_sl_leadans = rec_sl_leadhad = 0;    // P1384
	rec_sl_holdack = rec_sl_holdackat = 0;
	Trail_RequestReset();          // do not dispatch an old deferred save/load
};

// WOP ACK means dispatched, not reset success; a lost/nondecoded reset has no ACK.
// Wait past its command and let the coherent hold snapshot and numeric stat settle.
void() WarpOp_ResetReleaseFrame =
{
	local float held;
	if (!wop_resetq || wop_resetseq < 0)
		return;
	// A go may create a newer hold before its split load event arrives. Keep
	// recovery on refusal, but never release while that handoff is unresolved.
	if (Rewind_Waiting())
	{
		wop_resetat = 0;
		return;
	}
	if (servercommandframe <= wop_resetseq)
	{
		wop_resetat = 0;
		return;
	}
	held = getstatf(STAT_FS_HOLD) ? 1 : 0;
	if (wop_x_ok)
	if (held != wop_x_held)
	{
		wop_resetat = 0;
		return;
	}
	if (!wop_resetat || held != wop_resetheld || cltime < wop_resetat)
	{
		wop_resetat = cltime;
		wop_resetheld = held;
		return;
	}
	if (cltime - wop_resetat <= 0.3)
		return;
	// Free stats without this reset's ACK can still precede an older load.
	// A delayed holdoff is safe now; a newer load cancels this obligation.
	if (held || WarpOp_Ack() < wop_resetseq)
		SaveLoc_Cmd("sl_holdoff");
	wop_resetq = wop_resetseq = wop_resetat = 0;
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

	if (numclientseats == 1 && LT_StatsAreMine() && getstatf(STAT_FS_TSRETURN) > 0)
	{
		WarpOp_PracticeReturnCancel(); // before the independent stringcmd expiry
		return;
	}

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
				if (wop_resetq && wop_q[j] == wop_resetq)
				{
					// The reliable expiry fallback may also refuse. Older input must
					// finish before a holdoff can safely follow that fallback.
					wop_resetseq = clientcommandframe;
					wop_resetat = 0;
				}
				wop_seq[j] = 0;
				PE_Expect("a reset sent unpredicted");     // P1238
				if (op != WOP_SAVE && op != WOP_LOAD && op != WOP_RELEASE)
					wop_strat = cltime;
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
				else if (op == WOP_SAVE)
					WarpOp_SaveExpired();
			}
		}

	WarpOp_ResetReleaseFrame();
	WarpOp_SaveFrame();
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

// P1384: SaveLoc_LoadKey, right after WarpOp_Load: TRUE when that load was predicted, whose travel
// then starts now from the row it predicted (wop_tgorg/tgang, still WarpOp_Row's answer).
float() WarpOp_LoadLead =
{
	if (!wop_loadpred)
		return FALSE;
	// P1547: behind a save not yet answered the cursor picture is the previous save's: the plain hold.
	if (!wop_loadsteps)
	if (WarpOp_SaveSlot() < 0)
		SaveLead_Press(wop_tgorg, wop_tgang);
	return TRUE;
};

float() WarpOp_LoadPredicted = { return wop_loadpred; };     // P1544: SaveLoc_FifoLoad

// P1544: SaveLoc_Release of a stringcmd hold the server has answered (SaveLoc_StringHoldDone).
float() WarpOp_ReleaseString =
{
	if (!WarpOp_Able())
		return FALSE;
	wop_heldmode = WOP_PM_NONE;     // its movetype is the server's: walk, as SV_SaveLocRelease defaults
	return WarpOp_Release();
};

// P1384: a step not yet answered (SaveLead_Begin starts no travel under it).
float() WarpOp_StepPending = { return WarpOp_Pending(WOPP_STEP); };

// P1227: the load's command has reached the server and been answered (SaveLoc_LeadDone).
float() WarpOp_LoadAnswered =
{
	return (wop_loadseq > 0 && servercommandframe >= wop_loadseq);
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
	{
		WarpOp_Legs();
		WarpOp_Cur();               // P1238
	}
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
	if (wop_resetq && wop_q[best] == wop_resetq)
		wop_resetseq = clientcommandframe;
	input_impulse = wop_op[best];
	a = wop_ang[best];
	if (a_z)
	{
		a_z = 0;
		input_angles = a;
		setproperty(VF_CL_VIEWANGLES, a);
	}
	if (wop_op[best] == WOP_LOAD)
		wop_loadseq = wop_loadlast = clientcommandframe;
	if (wop_op[best] == WOP_RELEASE)
		wop_relseq = wop_rellast = clientcommandframe;
	if (wop_op[best] != WOP_SAVE && wop_saveseq > 0)
		wop_saveafter = TRUE;
	if (wop_op[best] == WOP_SAVE)
	{
		Trail_OpSaveCarried(clientcommandframe);
		wop_saveseq = clientcommandframe;
		wop_saveat = wop_saveafter = 0;
	}
	dprint(sprintf("warpop: %g on command %g\n", wop_op[best], clientcommandframe));
	// P1238: blind, and the cursor stats the prediction read (they can arrive in different packets).
	PE_Note(sprintf("warpop %g on command %g%s ack %g save %g of %g", wop_op[best], clientcommandframe,
	                wop_blind[best] ? " blind" : "", WarpOp_Ack(), WarpOp_Idx(), WarpOp_Cnt()));
	if (wop_blind[best])
		PE_Expect("a warp op sent blind (its destination was not published yet)");
};

// The server's body for op `op` (ring slot i), at the first piece of its command.
// P1547: state.txt's %.4f (SV_SaveWriteState). Not exact: the replay starts from the snapshot's 1/8 u/s
// speed, and the server clamps to maxvelocity before PlayerPreThink, so a release can differ by < 1 u/s.
vector(vector v) WarpOp_Round4 = { return stov(sprintf("'%.4f %.4f %.4f'", v_x, v_y, v_z)); };

void(float op, float i) WarpOp_Apply =
{
	if (op == WOP_SAVE)
	{
		// P1547: SV_SaveWriteState's row at this command's PlayerPreThink, from replays of it unacked
		// (an older baseline's replay follows another frame's last move). The first command a replay
		// runs starts from the server's snapshot, whose duck is its flags stat; any later one from the
		// move before it, which must be one of the two hulls.
		if (wop_cap[i] && wop_seq[i] <= servercommandframe)
			return;
		wop_org[i] = WarpOp_Round4(predinput_origin);
		wop_vel[i] = WarpOp_Round4(predinput_velocity);
		if (wop_seq[i] == servercommandframe + 1)
			wop_duck[i] = ((getstatf(STAT_FS_PMFLAGS) & PMF_DUCKED) != 0);
		else
			wop_duck[i] = wop_pmduck;
		wop_cap[i] = (wop_duck[i] >= 0);
		return;
	}
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

void(float ack) PE_AckSnap;             // P1403, cl_prederr.qc
float pe_pm_seq, pe_pm_off;             // P1403: the last replayed command and piece, for the chain start

// Every replay of every unacknowledged command.
void(float seat, float seq, float seconds, float offset) CSQC_PredictPlayerPreMove =
{
	local float i;

	wop_premove_t = cltime;
	// P1403: a chain starts where the command goes back (TG_ChainStart's test); its base is the snapshot it
	// replays from, so predinput_* is that state (servercommandframe can already name a newer one, review).
	if (!seat)
	{
		if (seq < pe_pm_seq || (seq == pe_pm_seq && offset <= pe_pm_off))
			PE_AckSnap(seq - 1);
		pe_pm_seq = seq;
		pe_pm_off = offset;
	}
	tg_baseseq = seq;                // Patch 1025: cl_triggers.qc's ring check, before any warp
	tg_baseorg = predinput_origin;
	// P1238: the server sends movetype only when it changes (sv_ents.c SVFTE_DeltaCalcBits), so a lost
	// snapshot leaves the release's PM_NONE in the baseline for a round trip.  A save-lock hold is
	// always still (SV_SaveLocHold), so a moving one after this client's release, no load since, is
	// that: read on the chain's first command only (the server's state, not this client's), never
	// under spectate (its hold keeps velocity), and disarmed once a baseline past the release is free.
	if (!seat)
	if (offset == 0)
	if (seq == servercommandframe + 1)
	if (wop_rellast > wop_loadlast && seq > wop_rellast)
	{
		if (predinput_pmtype != WOP_PM_NONE)
			wop_rellast = 0;
		else if (!getstatf(STAT_FS_SPEC) && vlen(predinput_velocity) > 0)
		{
			predinput_apply = predinput_apply | WOP_MODE;
			predinput_pmtype = (wop_heldmode == WOP_PM_NONE) ? WOP_PM_NORMAL : wop_heldmode;
		}
	}
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

	// P1211: the trigger mirror's gravity and delayed velocity rows (cl_triggers.qc TG_PreMove).
	if (seat)
		return;
	TG_PreMove(seq, seconds, offset, predinput_apply & WOP_HOLD, predinput_velocity, predinput_entgravity);
	if (tg_pm_velon)
	{
		predinput_apply = predinput_apply | WOP_BODY;   // origin and ground stay as the engine preloaded them
		predinput_velocity = tg_pm_vel;
	}
	// The client engine must take the flag, and the server's engine apply gravity per command
	// (review: a P1211 csprogs ahead of the lobby engine, or after its rollback).
	if (tg_pm_gravon && predinput_version >= 1211 && tg_grav_srv)
	{
		predinput_apply = predinput_apply | WOP_GRAVITY;
		predinput_entgravity = tg_grav;
	}
};

// cl_triggers.qc's CSQC_PredictPlayerMove: a reset that turns the view registers
// the turn as a predicted snap (Patch 396), so the server's fixangle a round trip
// later is recognized instead of undoing the mouse movement made since.
void(float seat, float seq) WarpOp_PostMove =
{
	local float i, h;
	local vector a;

	if (seat)
		return;
	// P1547: against the hulls the engine builds (pm_standheight/pm_duckheight, cl_main.c; the AG
	// profile publishes its 72/36 there); a hull that is neither predicts no save.
	if (wop_hst != cltime)
	{
		wop_hst = cltime;
		wop_hs = serverkeyfloat("pm_standheight");
		wop_hd = serverkeyfloat("pm_duckheight");
		if (wop_hs <= 0) wop_hs = 62;
		if (wop_hd <= 0) wop_hd = 45;
	}
	h = predmove_maxs_z - predmove_mins_z;
	wop_pmduck = (fabs(h - wop_hd) < 0.5) ? 1 : ((fabs(h - wop_hs) < 0.5) ? 0 : -1);
	if (!wop_seq)
		return;
	for (i = 0; i < WOP_RING; i = i + 1)
		if (wop_seq[i] == seq)
		{
			// P1547: the save's aim is its command's (v_angle at PlayerPreThink), z 0: no turn.
			if (wop_op[i] == WOP_SAVE)
			{
				wop_ang[i] = WarpOp_Round4([predmove_cmdangles_x, predmove_cmdangles_y, 0]);
				return;
			}
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
	text = ChatCmd_Normalize(text);     // FTESurf Patch 1295: "!b3", "/b 3" as the server reads them
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
	// P1547: these go to `say`, a stringcmd that moves the body (WarpOp_Save waits it out).
	if (w == "!r" || w == "!m" || w == "!resume" || w == "!restart")
		wop_strat = cltime;
	if (w != "!s" && w != "!b")
		return FALSE;
	for (i = 0; i < strlen(tail); i = i + 1)
	{
		c = str2chr(tail, i);
		if (c < '0' || c > '9')
		{
			wop_strat = cltime;     // P1547: to `say`
			return FALSE;
		}
	}
	n = max(1, stof(tail));
	if (w == "!s")
	{
		if (n > WOP_STAGES)
		{
			wop_strat = cltime;     // P1547: to `say`
			return FALSE;
		}
		return WarpOp_Reset(WOP_STAGE1 + n - 1);
	}
	if (n > WOP_BONUSES)
	{
		wop_strat = cltime;         // P1547: to `say`
		return FALSE;
	}
	return WarpOp_Reset(WOP_BONUS1 + n - 1);
};

// `goto [spawn|start|main|sN|bN]` (Lex, 7 Nov): one command for the warps. Stages and
// bonuses go through `!s N` / `!b N`, predicted where those are, else sent as that chat line.
float(string w) WarpOp_Goto =
{
	local float n, i, c;
	local string kind;

	// Patch 845: the map's spawn entity, where joining puts you, not `!m`'s start zone.
	// A respawn, so not predicted.
	if (w == "" || w == "spawn")
	{
		PE_Expect("goto_spawn, a respawn");     // P1238
		wop_strat = cltime;                     // P1547
		localcmd("cmd zone_spawn\n");
		return TRUE;
	}
	if (w == "start")
	{
		localcmd("goto_start\n");
		return TRUE;
	}
	if (w == "main" || w == "m")
	{
		if (!WarpOp_Chat("!m"))
			localcmd("cmd say \"!m\"\n");
		return TRUE;
	}
	kind = "";
	if (substring(w, 0, 5) == "stage" || substring(w, 0, 5) == "bonus")
	{
		kind = substring(w, 0, 1);
		w = substring(w, 5, strlen(w) - 5);
	}
	else if (substring(w, 0, 1) == "s" || substring(w, 0, 1) == "b")
	{
		kind = substring(w, 0, 1);
		w = substring(w, 1, strlen(w) - 1);
	}
	n = 0;
	if (kind != "" && w != "")
	{
		n = stof(w);
		for (i = 0; i < strlen(w); i = i + 1)
		{
			c = str2chr(w, i);
			if (c < '0' || c > '9')
				n = 0;
		}
	}
	if (n < 1)
	{
		print("goto: spawn (or just goto), start, main, s<N> for stage N, b<N> for bonus N -- e.g. goto s3, goto b1\n");
		return TRUE;
	}
	if (!WarpOp_Chat(sprintf("!%s %g", kind, n)))
		localcmd(sprintf("cmd say \"!%s %g\"\n", kind, n));
	return TRUE;
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
	// segment, a stage restart: SV_TimerWouldRestartSeg).
	// Patch 1051: goto_start is the start of the track `!r`'s latched leg is on: `!r` itself where that
	// leg is the track's first segment (startmark, save in the box, P415), else `!m` or `!b N`.  It read
	// the timer before, whose segment is 0 whenever it is idle, so it "only reset" to the latched stage.
	if (argv(0) == "reset")
	{
		if (!WarpOp_Reset(WOP_RESET))
			localcmd("cmd zone_reset\n");
		return TRUE;
	}
	if (argv(0) == "goto_start")
	{
		if (!WarpOp_Able())
		{
			PE_Expect("goto_start, not predicted here");     // P1238
			wop_strat = cltime;                             // P1547
			localcmd("cmd zone_start\n");        // spectating, replays: the server decides on your own leg
			return TRUE;
		}
		n = getstatf(STAT_FS_LEGTRACK);         // 0 main, N bonus N
		if (getstatf(STAT_FS_LEGSEG) > 0)
		{
			if (n > 0)
			{
				if (n > WOP_BONUSES)
				{
					wop_strat = cltime;                     // P1547
					localcmd(sprintf("cmd say \"!b %g\"\n", n));
				}
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
	if (argv(0) == "goto_spawn")
		return WarpOp_Goto("spawn");
	// "s 3" and "s3", "stage 3" and "stage3" read alike.
	if (argv(0) == "goto")
		return WarpOp_Goto(strtolower(strcat(argv(1), argv(2))));
	return FALSE;
};
