/*
  P1088: `tas optimize <ticks> <left|right>` -- the first bounded optimizer (TAS plan Stage 4b).

  From the paused head H it searches one number, a constant yaw rate (degrees a tick) turned
  from your current view while strafing that way at 450, for the highest horizontal exit speed
  at H + ticks. A grid over 0..topt_rmax, then golden-section around its best; every candidate
  is a TAS back to H and an input tape, so it is the real mover on the real map. It ends with
  the best one played, paused at H + ticks. No global optimum is claimed.

  P1092 (Lex's per-ramp goals): `board` also searches the yaw offset taken on the first tick
  (the boarding angle, -30..30 degrees toward the strafe side), and `flick [k]` a second, faster
  rate over the last k ticks (default 4) for the launch. One 1-D search per number, each holding
  the others at the best found so far (rate, board, rate again; then flick), so the result is
  never below P1088's own search, which runs first and unchanged.

  P1097 (`time`): the score is how many stages past the start's the run reached (run_t_seg), then
  how early it crossed the last (run_t_split; both set by SV_TimerSplit and restored by a back --
  run_st_tick moves when the box is left), then exit speed. Checkpoints are not scored: a back
  does not restore run_t_cpn. A candidate that finishes ends the run, and the search with it.
*/

#define TOPT_GRID  9            // grid points over a search's range
#define TOPT_GOLD  10           // golden-section steps in best +- one grid step
#define TOPT_G     0.618034
#define TOPT_YMAX  30           // P1092: boarding offset range, degrees either way
#define TOPT_FMAX  45           // P1092: flick rate top, degrees a tick

.float topt_on, topt_head, topt_n, topt_dir, topt_yaw0, topt_pitch0;
.float topt_stage;              // 1 go back to the head and stage the tape, 2 the tape is running
.float topt_phase;              // 1 grid, 2 golden, 3 the best, played last
.float topt_k, topt_cand, topt_evals, topt_bestr, topt_bestv, topt_next;
.float topt_lo, topt_hi, topt_a, topt_b, topt_fa, topt_fb, topt_which, topt_iter;
.float topt_backed, topt_wait;  // a back sent and not yet seen to land; when a refused tape gives up
.float topt_rmax;               // the range's top: twice the air-strafe turn asin(30 / speed)
.float topt_mode;               // P1092: 1 board, 2 flick
.float topt_fk;                 // P1092: flick length in ticks (0 without flick)
.float topt_besty, topt_bestf;  // P1092: the best's boarding offset and flick rate (-1: no flick)
.float topt_srch;               // P1092: which 1-D search of SV_TASOptParam's list is running
.float topt_obj, topt_seg0;     // P1097: 1 = time; run_t_seg at the start
.float topt_pn;                 // P1443: the candidate's rollout: ticks that count (-2 none)
.float topt_pcut;               // P1443: why it counts fewer: 1 an entity QC acts on, 2 the engine stopped
.vector topt_po, topt_pv;       // P1443: its last tick's origin and velocity
.float topt_rchk, topt_rshort, topt_rbado, topt_rbadv;  // P1443: landings checked, cut at an entity, worst gaps
.float topt_rstop;              // P1443: rollouts the engine stopped (a tick its plain case does not cover)
.float topt_rref, topt_rwhy;    // P1443: rollouts refused, and the last refusal's code (SV_TASRollout)
.float topt_rexact;             // P1443: landings bit-equal to the prediction (origin and velocity)
.float topt_fast;               // P1443: candidates scored by tas_rollout; only the best plays as a tape
.float topt_energy, topt_z0;    // P1443: score energy (the speed it is worth at the start height), start z
float *topt_rows;               // P1443: rollout buffers, TAS_TAPE_MAX rows, allocated once
float *topt_out;

// P1092: the numbers searched, in order: 1 rate, 2 boarding offset, 3 flick rate; 0 = done.
float(entity e, float i) SV_TASOptParam1 =
{
	if (i == 0) return 1;
	if (e.topt_mode & 1) { if (i == 1) return 2; if (i == 2) return 1; i = i - 2; }
	if (e.topt_mode & 2) { if (i == 1) return 3; }
	return 0;
};
// P1443: `fast` runs the list twice (rollouts are cheap) and searches each number finer.
float(entity e, float i) SV_TASOptParam =
{
	local float n;
	if (!e.topt_fast) return SV_TASOptParam1(e, i);
	for (n = 0; SV_TASOptParam1(e, n); n = n + 1) ;
	if (i >= n && i < 2 * n) return SV_TASOptParam1(e, i - n);
	return SV_TASOptParam1(e, i);
};
float(entity e) SV_TASOptGrid = { return e.topt_fast ? 33 : TOPT_GRID; };
float(entity e) SV_TASOptGold = { return e.topt_fast ? 24 : TOPT_GOLD; };
float(entity e, float p) SV_TASOptLo = { return (p == 2) ? -TOPT_YMAX : 0; };
float(entity e, float p) SV_TASOptHi = { if (p == 2) return TOPT_YMAX; if (p == 3) return TOPT_FMAX; return e.topt_rmax; };

// P1097: what is scored. Speed, or with `time` segments reached, the tick the last one opened and
// speed / 10: one segment scores below 2^19, where float32 still tells 0.3 u/s apart.
float(entity e) SV_TASOptSegs =
{
	if (e.run_t_seg <= e.topt_seg0) return 0;
	return e.run_t_seg - e.topt_seg0;
};
// P1443: a state's score for speed or energy (energy as the speed it is worth at the start height).
float(entity e, vector org, vector vel) SV_TASOptStateScore =
{
	if (e.topt_energy) return sqrt(max(0, vel * vel + 2 * cvar("sv_gravity") * (org_z - e.topt_z0)));
	return vlen([vel_x, vel_y, 0]);
};
float(entity e) SV_TASOptScore =
{
	local float spd, segs;
	spd = vlen([e.velocity_x, e.velocity_y, 0]);
	if (!e.topt_obj) return SV_TASOptStateScore(e, e.origin, e.velocity);
	segs = SV_TASOptSegs(e);
	spd = min(9990, spd) / 10;
	if (!segs) return spd;
	return segs * 200000 + bound(0, e.topt_head + e.topt_n - e.run_t_split, 128) * 1000 + spd;
};
string(entity e, float v) SV_TASOptDesc =
{
	local float spd;
	spd = vlen([e.velocity_x, e.velocity_y, 0]);
	if (!e.topt_obj) return sprintf(e.topt_energy ? "energy %.1f u/s" : "%.1f u/s", v);
	if (!SV_TASOptSegs(e)) return sprintf("no new stage, %.1f u/s", spd);
	return sprintf("stage +%.0f at tick %.0f, %.1f u/s", SV_TASOptSegs(e), e.run_t_split, spd);
};

string(entity e) SV_TASOptExtra =
{
	local string s;
	s = "";
	if (e.topt_mode & 1) s = sprintf(", board %.2f deg", e.topt_besty);
	if (e.topt_mode & 2) s = strcat(s, (e.topt_bestf < 0) ? ", no flick"
		: sprintf(", flick %.3f deg/tick over the last %.0f ticks", e.topt_bestf, e.topt_fk));
	return s;
};

// P1443: how the rollouts matched the real mover's landings.
void(entity e) SV_TASOptRollReport =
{
	if (!cvar("developer") || (!e.topt_rchk && !e.topt_rshort && !e.topt_rstop && !e.topt_rref)) return;
	sprint(e, PRINT_HIGH, sprintf("tas optimize: rollout check: %.0f landings predicted (%.0f bit-equal), worst %.5f u and %.5f u/s off%s%s%s\n",
		e.topt_rchk, e.topt_rexact, e.topt_rbado, e.topt_rbadv,
		e.topt_rshort ? sprintf("; %.0f cut where QC acts", e.topt_rshort) : "",
		e.topt_rstop ? sprintf("; %.0f stopped by the engine", e.topt_rstop) : "",
		e.topt_rref ? sprintf("; %.0f refused (code %.0f)", e.topt_rref, e.topt_rwhy) : ""));
};

void(entity e, string why) SV_TASOptStop =
{
	if (!e.topt_on) return;
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING)
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
	e.topt_on = 0;
	sprint(e, PRINT_HIGH, sprintf("tas optimize: stopped after %.0f candidates: %s\n", e.topt_evals, why));
	SV_TASOptRollReport(e);
	if (e.topt_bestv >= 0 && e.topt_obj)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best so far turn %.3f deg/tick%s (not applied)\n", e.topt_bestr, SV_TASOptExtra(e)));
	else if (e.topt_bestv >= 0)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best so far turn %.3f deg/tick%s, %.1f u/s (not applied)\n", e.topt_bestr,
			SV_TASOptExtra(e), e.topt_bestv));
};

// Row i's yaw: yaw0 + board, then turning r a tick, and over the last topt_fk ticks f a tick instead.
float(entity e, float r, float y, float f, float i) SV_TASOptYaw =
{
	local float yaw, m;
	m = e.topt_n - e.topt_fk;
	if (i < m || f == r) yaw = e.topt_yaw0 + e.topt_dir * (y + r * (i + 1));
	else yaw = e.topt_yaw0 + e.topt_dir * (y + r * m + f * (i + 1 - m));
	return yaw - 360 * floor((yaw + 180) / 360);        // SV_TASPWord unwraps only one turn
};

// P1443: an entity a rollout names that per-command QC leaves the body's movement alone for: the
// timer's zone volumes (the timer reads them; nothing pushes, limits or teleports).
float(entity t) SV_TASRollHarmless =
{
	return substring(t.classname, 0, 23) == "trigger_momentum_timer_";
};

// P1443: the candidate's rows through tas_rollout into topt_out. Returns the ticks that count and
// sets topt_pcut (1 an entity QC acts on ended it, 2 the engine stopped), or SV_TASRollout's
// negative refusal; -20 without the builtin or buffers.
.float topt_rollcut;
float(entity e, float r, float y, float f) SV_TASOptRoll =
{
	local float i, ran;
	e.topt_rollcut = 0;
	if (!checkbuiltin(tas_rollout)) return -20;
	if (!topt_rows) topt_rows = (float*)memalloc(TAS_TAPE_MAX * 7 * 4);
	if (!topt_out) topt_out = (float*)memalloc(TAS_TAPE_MAX * 13 * 4);
	if (!topt_rows || !topt_out) return -20;
	for (i = 0; i < e.topt_n; i = i + 1)
	{
		topt_rows[i*7] = 0; topt_rows[i*7+1] = -450 * e.topt_dir; topt_rows[i*7+2] = 0;
		topt_rows[i*7+3] = SV_TASPWord(e.topt_pitch0); topt_rows[i*7+4] = SV_TASPWord(SV_TASOptYaw(e, r, y, f, i));
		topt_rows[i*7+5] = 0; topt_rows[i*7+6] = 0;
	}
	ran = tas_rollout(e, topt_rows, e.topt_n, topt_out);
	if (ran >= 0 && ran < e.topt_n) e.topt_rollcut = 2;
	for (i = 0; i < ran; i = i + 1)
		if (topt_out[i*13 + 12] && !SV_TASRollHarmless(edict_num(topt_out[i*13 + 12])))
		{	// QC acts on it (a touch, a carrier, a volume) where the rollout cannot: ends with this tick
			if (cvar("developer") >= 2 || (cvar("developer") && !e.topt_fast && !e.topt_rshort))
				sprint(e, PRINT_HIGH, sprintf("tas optimize: rollout meets %s at tick %.0f of %.0f\n",
					edict_num(topt_out[i*13 + 12]).classname, i + 1, e.topt_n));
			e.topt_rollcut = 1;
			return i + 1;
		}
	return ran;
};

// The same rows before the tape plays; SV_TASOptFrame checks the tape's landing against the
// prediction's last tick (topt_pn -2: no rollout, else ticks that count, or the refusal).
void(entity e, float r, float y, float f) SV_TASOptPredict =
{
	local float ran, i;
	ran = SV_TASOptRoll(e, r, y, f);
	e.topt_pn = (ran == -20) ? -2 : ran;
	e.topt_pcut = e.topt_rollcut;
	if (ran >= 1)
	{
		i = (ran - 1) * 13;
		e.topt_po = [topt_out[i], topt_out[i+1], topt_out[i+2]];
		e.topt_pv = [topt_out[i+3], topt_out[i+4], topt_out[i+5]];
	}
};

// P1443 `fast`: a candidate's score from its rollout. -1 when an entity QC acts on (a reset, a
// push) or an engine stop ends it early -- the tape would not land where the rollout says --
// and -2 when it cannot run.
float(entity e, float r, float y, float f) SV_TASOptRollScore =
{
	local float ran, i;
	ran = SV_TASOptRoll(e, r, y, f);
	if (ran < 0) return -2;
	if (ran < e.topt_n) return -1;
	i = (ran - 1) * 13;
	return SV_TASOptStateScore(e, [topt_out[i], topt_out[i+1], topt_out[i+2]], [topt_out[i+3], topt_out[i+4], topt_out[i+5]]);
};

// The candidate's inputs onto the native tape (SV_TASOptYaw's yaws, strafing to the turn's side).
float(entity e, float r, float y, float f) SV_TASOptTape =
{
	local float i, tx, ok;
	if (!tas_tape(e, 2, e.topt_n, 0, '0 0 0', '0 0 0', 0)) return FALSE;
	tx = tas_tape(e, 3, e.topt_n, 0, '0 0 0', '0 0 0', 0);
	ok = tx > 0;
	for (i = 0; i < e.topt_n && ok; i = i + 1)
		ok = tas_tape(e, 4, tx, i, [0, -450 * e.topt_dir, 0],
			[SV_TASPWord(e.topt_pitch0), SV_TASPWord(SV_TASOptYaw(e, r, y, f, i)), 0], 0);
	if (ok) ok = tas_tape(e, 5, tx, 0, '0 0 0', '0 0 0', 0);
	if (!ok)
	{
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
		return FALSE;
	}
	e.run_tas_replayserial = e.rec_rec_serial;  // SV_TASReplayFrame cancels any other serial's
	return TRUE;
};

// The candidate's three numbers: the searched one is topt_cand, the others the best so far.
float(entity e, float p) SV_TASOptValue =
{
	local float q;
	q = SV_TASOptParam(e, e.topt_srch);
	if (e.topt_phase != 3 && q == p) return e.topt_cand;
	if (p == 2) return e.topt_besty;
	if (p == 3) return (e.topt_bestf < 0) ? SV_TASOptValue(e, 1) : e.topt_bestf;   // no flick yet: the rate goes on
	return e.topt_bestr;
};

// The next golden-section point, or the next search (or the final run) once the steps are spent.
void(entity e) SV_TASOptGolden =
{
	local float p;
	if (e.topt_iter >= SV_TASOptGold(e))
	{
		e.topt_srch = e.topt_srch + 1;
		p = SV_TASOptParam(e, e.topt_srch);
		if (!p) { e.topt_phase = 3; e.topt_cand = e.topt_bestr; return; }
		e.topt_phase = 1; e.topt_k = 0; e.topt_iter = 0; e.topt_which = 0;
		e.topt_cand = SV_TASOptLo(e, p);
		return;
	}
	e.topt_iter = e.topt_iter + 1;
	if (e.topt_fa >= e.topt_fb)
	{
		e.topt_hi = e.topt_b; e.topt_b = e.topt_a; e.topt_fb = e.topt_fa;
		e.topt_a = e.topt_hi - TOPT_G * (e.topt_hi - e.topt_lo);
		e.topt_which = 1; e.topt_cand = e.topt_a;
	}
	else
	{
		e.topt_lo = e.topt_a; e.topt_a = e.topt_b; e.topt_fa = e.topt_fb;
		e.topt_b = e.topt_lo + TOPT_G * (e.topt_hi - e.topt_lo);
		e.topt_which = 2; e.topt_cand = e.topt_b;
	}
};

// One candidate measured: v at H + n. Chooses what runs next.
void(entity e, float v) SV_TASOptResult =
{
	local float step, p, lo, hi, best;
	e.topt_evals = e.topt_evals + 1;
	if (e.topt_phase == 3)
	{
		e.topt_on = 0;
		if (e.topt_obj)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: best %s turn %.3f deg/tick over %.0f ticks: %s (%.0f candidates); paused at %.0f\n",
				(e.topt_dir > 0) ? "left" : "right", e.topt_bestr, e.topt_n, SV_TASOptDesc(e, v), e.topt_evals, SV_TimerTicks(e)));
		else
			sprint(e, PRINT_HIGH, sprintf("tas optimize: best %s turn %.3f deg/tick over %.0f ticks: %s %.1f u/s (%.0f candidates); paused at %.0f\n",
				(e.topt_dir > 0) ? "left" : "right", e.topt_bestr, e.topt_n, e.topt_energy ? "energy" : "exit", v, e.topt_evals, SV_TimerTicks(e)));
		if (e.topt_mode)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: with%s\n", substring(SV_TASOptExtra(e), 1, -1)));
		SV_TASOptRollReport(e);
		if (e.topt_obj && fabs(v - e.topt_bestv) > 0.35)   // the score's speed step at one stage is 0.31 u/s
			sprint(e, PRINT_HIGH, "tas optimize: the replay differs from the search: the world moved between them\n");
		else if (!e.topt_obj && fabs(v - e.topt_bestv) > 0.05)  // a moving world can differ between two plays
			sprint(e, PRINT_HIGH, sprintf("tas optimize: replayed %.1f u/s, searched %.1f: the world moved between them\n", v, e.topt_bestv));
		if (e.topt_bestr >= e.topt_rmax - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: that is the top of the range searched; a sharper turn may be faster\n");
		if ((e.topt_mode & 1) && fabs(e.topt_besty) >= TOPT_YMAX - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: the board is at the end of its range; a wider one may be faster\n");
		if ((e.topt_mode & 2) && e.topt_bestf >= TOPT_FMAX - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: the flick is at the top of its range\n");
		return;
	}
	p = SV_TASOptParam(e, e.topt_srch);
	if (e.topt_fast && cvar("developer") < 2) {}
	else if (e.topt_mode || e.topt_obj) sprint(e, PRINT_HIGH, sprintf("tas optimize: %.0f  %s %.3f -> %s\n", e.topt_evals,
		(p == 2) ? "board" : ((p == 3) ? "flick" : "turn"), e.topt_cand, SV_TASOptDesc(e, v)));
	else sprint(e, PRINT_HIGH, sprintf("tas optimize: %.0f  turn %.3f deg/tick -> %.1f u/s\n", e.topt_evals, e.topt_cand, v));
	if (v > e.topt_bestv)
	{
		e.topt_bestv = v;
		if (p == 2) e.topt_besty = e.topt_cand; else if (p == 3) e.topt_bestf = e.topt_cand; else e.topt_bestr = e.topt_cand;
	}
	lo = SV_TASOptLo(e, p); hi = SV_TASOptHi(e, p);
	if (e.topt_phase == 1)
	{
		e.topt_k = e.topt_k + 1;
		step = (hi - lo) / (SV_TASOptGrid(e) - 1);
		if (e.topt_k < SV_TASOptGrid(e)) { e.topt_cand = lo + e.topt_k * step; return; }
		e.topt_phase = 2;
		best = max(lo, (p == 2) ? e.topt_besty : ((p == 3) ? SV_TASOptValue(e, 3) : e.topt_bestr));
		e.topt_lo = max(lo, best - step); e.topt_hi = min(hi, best + step);
		e.topt_a = e.topt_hi - TOPT_G * (e.topt_hi - e.topt_lo);
		e.topt_b = e.topt_lo + TOPT_G * (e.topt_hi - e.topt_lo);
		e.topt_which = 3; e.topt_cand = e.topt_a;
		return;
	}
	if (e.topt_which == 3) { e.topt_fa = v; e.topt_which = 4; e.topt_cand = e.topt_b; return; }
	if (e.topt_which == 4 || e.topt_which == 2) e.topt_fb = v;
	else e.topt_fa = v;
	SV_TASOptGolden(e);
};

// After SV_TASProjectFrame: one step of the search a frame.
void(entity e) SV_TASOptFrame =
{
	local float head, k, v;
	if (!e.topt_on) return;
	if (!e.run_tas_paused || e.run_t_state != TS_RUNNING) { SV_TASOptStop(e, "TAS play/off, or the run ended"); return; }
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_pending) return;
	head = SV_TimerTicks(e);
	if (e.topt_stage == 2)
	{
		if (e.run_tas_replaystate != TAS_TAPE_DONE || head != e.topt_head + e.topt_n)
		{
			SV_TASOptStop(e, "the input tape did not land on its tick");
			return;
		}
		e.topt_stage = 1;
		if (e.topt_pn == e.topt_n)
		{	// P1443: the real mover's landing against the rollout's last tick
			e.topt_rchk = e.topt_rchk + 1;
			e.topt_rbado = max(e.topt_rbado, vlen(e.origin - e.topt_po));
			e.topt_rbadv = max(e.topt_rbadv, vlen(e.velocity - e.topt_pv));
			if (e.origin == e.topt_po && e.velocity == e.topt_pv)
				e.topt_rexact = e.topt_rexact + 1;
			if (cvar("developer"))
				sprint(e, PRINT_HIGH, sprintf("tas optimize: rollout %.0f off by %.5f u, %.5f u/s\n", e.topt_evals + 1,
					vlen(e.origin - e.topt_po), vlen(e.velocity - e.topt_pv)));
		}
		else if (e.topt_pn >= 0 && e.topt_pcut == 1)
			e.topt_rshort = e.topt_rshort + 1;
		else if (e.topt_pn >= 0)
			e.topt_rstop = e.topt_rstop + 1;
		else if (e.topt_pn != -2)
		{
			e.topt_rref = e.topt_rref + 1;
			e.topt_rwhy = e.topt_pn;
		}
		SV_TASOptResult(e, SV_TASOptScore(e));
		return;
	}
	if (time < e.topt_next) return;
	e.topt_next = time + 0.05;
	if (head != e.topt_head)
	{
		if (head < e.topt_head) { SV_TASOptStop(e, "the head went back before the start"); return; }
		if (e.topt_backed) { SV_TASOptStop(e, "TAS back to the start tick was refused"); return; }
		e.topt_backed = 1;
		SV_TASBack(e, head - e.topt_head, e.run_tas_req + 1);
		return;
	}
	e.topt_backed = 0;
	if (e.topt_fast && e.topt_phase != 3)
	{	// P1443: up to ~4000 rollout ticks a frame, at the head; the best is played below once found
		for (k = 0; k < max(1, floor(4000 / e.topt_n)) && e.topt_on && e.topt_phase != 3; k = k + 1)
		{
			v = SV_TASOptRollScore(e, SV_TASOptValue(e, 1), SV_TASOptValue(e, 2), SV_TASOptValue(e, 3));
			if (v == -2) { SV_TASOptStop(e, "the engine refused the rollout (needs a plain air or ground start)"); return; }
			SV_TASOptResult(e, v);
		}
		return;
	}
	SV_TASOptPredict(e, SV_TASOptValue(e, 1), SV_TASOptValue(e, 2), SV_TASOptValue(e, 3));
	// The back's holds release over a frame or two: a refused tape waits up to a second.
	if (!SV_TASOptTape(e, SV_TASOptValue(e, 1), SV_TASOptValue(e, 2), SV_TASOptValue(e, 3)))
	{
		if (!e.topt_wait) e.topt_wait = time + 1;
		if (time > e.topt_wait) SV_TASOptStop(e, "the engine refused the input tape");
		return;
	}
	e.topt_wait = 0;
	e.topt_stage = 2;
};

// P1443: `cmd tas rollbench <ticks> <count>` (developer): count rollouts of a strafing turn from the
// paused body, timed on the wall clock -- what a search can afford.
void(entity e, float argc) SV_TASRollBench =
{
	local float n, c, i, k, ran, total, t0, t1;
	local float *rows;
	local float *out;
	n = stof(argv(2)); c = stof(argv(3));
	if (!cvar("developer") || !checkbuiltin(tas_rollout) || argc != 4 ||
		!(n >= 1 && n <= 2048 && n == floor(n)) || !(c >= 1 && c <= 20000 && c == floor(c)) || n * c > 1000000)
	{
		sprint(e, PRINT_HIGH, "tas rollbench <ticks 1..2048> <count 1..20000>, ticks x count <= 1000000 (developer 1, an engine with tas_rollout)\n");
		return;
	}
	rows = (float*)memalloc(n * 7 * 4);
	out = (float*)memalloc(n * 13 * 4);
	if (!rows || !out) { if (rows) memfree(rows); if (out) memfree(out); return; }
	for (i = 0; i < n; i = i + 1)
	{
		rows[i*7] = 0; rows[i*7+1] = 450; rows[i*7+2] = 0;
		rows[i*7+3] = SV_TASPWord(e.v_angle_x);
		rows[i*7+4] = SV_TASPWord(e.v_angle_y - 360 * floor((e.v_angle_y - 0.5 * (i + 1) + 180) / 360) - 0.5 * (i + 1));
		rows[i*7+5] = 0; rows[i*7+6] = 0;
	}
	total = 0; ran = 0;
	t0 = gettime(1);
	for (k = 0; k < c; k = k + 1)
	{
		ran = tas_rollout(e, rows, n, out);
		if (ran < 0) break;
		total = total + ran;
	}
	t1 = gettime(1);
	memfree(rows); memfree(out);
	if (ran < 0) { sprint(e, PRINT_HIGH, sprintf("tas rollbench: refused (code %.0f)\n", ran)); return; }
	sprint(e, PRINT_HIGH, sprintf("tas rollbench: %.0f rollouts of %.0f ticks (%.0f ticks) in %.3f s: %.0f rollouts/s, %.0f ticks/s\n",
		c, n, total, t1 - t0, c / max(0.001, t1 - t0), total / max(0.001, t1 - t0)));
};

void(entity e) SV_TASOptReset =
{
	e.topt_on = 0;
};

// tas optimize <ticks> <left|right> [board] [flick [k]] [time] [energy] [fast]
void(entity e, float argc) SV_TASOptCommand =
{
	local float n, dir, i, mode, fk, searches, obj, fast, energy;
	local string w;
	n = stof(argv(2));
	dir = !strcmp(argv(3), "left") ? 1 : (!strcmp(argv(3), "right") ? -1 : 0);
	mode = 0; fk = 0; obj = 0; fast = 0; energy = 0;
	for (i = 4; i < argc; i = i + 1)
	{
		w = argv(i);
		if (w == "fast" && !fast) fast = 1;
		else if (w == "energy" && !energy) energy = 1;
		else if (w == "time" && !obj && mode >= 0) obj = 1;
		else if (w == "board" && !(mode & 1)) mode = mode | 1;
		else if (w == "flick" && !(mode & 2)) { mode = mode | 2; fk = 4; }
		else if ((mode & 2) && fk == 4 && argv(i - 1) == "flick" && stof(w) >= 1 && stof(w) <= 32 && stof(w) == floor(stof(w)) && w == ftos(stof(w))) fk = stof(w);
		else { mode = -1; break; }
	}
	if ((obj && (fast || energy)) || (fast && !checkbuiltin(tas_rollout)))
	{
		sprint(e, PRINT_HIGH, obj ? "tas optimize: time scores stages, which only the real mover reaches: not with fast or energy\n"
			: "tas optimize: fast needs an engine with tas_rollout\n");
		return;
	}
	if (argc >= 4 && argc <= 10 && n >= 4 && n <= TAS_TAPE_MAX && n == floor(n) && dir && mode >= 0 && fk >= n)
	{
		sprint(e, PRINT_HIGH, sprintf("tas optimize: the flick (%.0f ticks) must be shorter than the run (%.0f ticks)\n", fk, n));
		return;
	}
	if (argc < 4 || argc > 10 || !(n >= 4 && n <= TAS_TAPE_MAX && n == floor(n)) || !dir || mode < 0)
	{
		sprint(e, PRINT_HIGH, "tas optimize <ticks 4..128> <left|right> [board] [flick [ticks 1..32]] [time | energy] [fast]: best turn for exit speed (energy: speed + height), or with time the next segment soonest; fast searches by rollout and plays only the best\n");
		return;
	}
	if (!e.run_tas_rwcap || !SV_TASInputReady(e) || !SV_TASCanPause(e)) return;
	if (e.rec_rec_stream)
	if (e.rec_rec_ver >= 14)
	{
		sprint(e, PRINT_HIGH, "tas optimize: REC14 stream rewind is unsupported here\n");
		return;
	}
	// Every candidate after the first goes back here: refuse now, not one candidate in.
	SV_RewindTASHead(e);
	if (!SV_RewindFindTick(e, SV_TimerTicks(e)))
	{
		sprint(e, PRINT_HIGH, "tas optimize: this tick has no native checkpoint (standing on a moving or brush entity?)\n");
		return;
	}
	if (e.run_tas_req < 16000000) e.run_tas_req = e.run_tas_req + 1;   // a tape's request must be >= 1
	e.topt_on = 1; e.topt_head = SV_TimerTicks(e); e.topt_n = n; e.topt_dir = dir;
	e.topt_yaw0 = e.v_angle_y; e.topt_pitch0 = e.v_angle_x;
	e.topt_stage = 1; e.topt_phase = 1; e.topt_k = 0; e.topt_cand = 0; e.topt_which = 0;
	e.topt_evals = e.topt_iter = 0; e.topt_bestr = 0; e.topt_bestv = -1; e.topt_next = 0;
	e.topt_backed = e.topt_wait = 0;
	e.topt_mode = mode; e.topt_fk = fk; e.topt_srch = 0; e.topt_besty = 0; e.topt_bestf = 0;
	e.topt_obj = obj; e.topt_seg0 = e.run_t_seg;
	e.topt_fast = fast; e.topt_energy = energy; e.topt_z0 = e.origin_z;
	e.topt_pn = -2; e.topt_rchk = e.topt_rshort = e.topt_rbado = e.topt_rbadv = e.topt_rref = e.topt_rwhy = e.topt_rexact = e.topt_rstop = 0;
	// Source's air wish speed cap is 30: the speed-holding turn is asin(30 / v) a tick.
	e.topt_rmax = bound(1, 2 * asin(min(1, 30 / max(30, vlen([e.velocity_x, e.velocity_y, 0])))) * 180 / M_PI, 45);
	e.topt_bestf = -1;                  // no flick until its search finds a faster one
	for (searches = 0; SV_TASOptParam(e, searches); searches = searches + 1) ;
	sprint(e, PRINT_HIGH, sprintf("tas optimize: from tick %.0f, %.0f ticks turning %s, 0..%.2f deg/tick, %.0f candidates%s\n",
		e.topt_head, n, argv(3), e.topt_rmax, searches * (SV_TASOptGrid(e) + SV_TASOptGold(e) + 2) + 1,
		fast ? " by rollout, the best played" : ""));
	if (mode)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: %s%s%s\n", (mode & 1) ? "board -30..30 deg" : "", (mode == 3) ? "; " : "",
			(mode & 2) ? sprintf("flick over the last %.0f ticks, 0..%.0f deg/tick", fk, TOPT_FMAX) : ""));
	if (obj)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: scoring stages reached after stage %.0f, then how soon, then speed\n", e.topt_seg0 + 1));
};
