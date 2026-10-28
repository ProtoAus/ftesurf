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

  P1097 (`time`): the score is how many segments past the start's the run reached, then how early
  the last one opened (run_st_tick, set by SV_StageOpen), then exit speed. A candidate that
  finishes ends the run, and the search with it.
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
.float topt_obj, topt_seg0;     // P1097: 1 = time; the segment open at the start

// P1092: the numbers searched, in order: 1 rate, 2 boarding offset, 3 flick rate; 0 = done.
float(entity e, float i) SV_TASOptParam =
{
	if (i == 0) return 1;
	if (e.topt_mode & 1) { if (i == 1) return 2; if (i == 2) return 1; i = i - 2; }
	if (e.topt_mode & 2) { if (i == 1) return 3; }
	return 0;
};
float(entity e, float p) SV_TASOptLo = { return (p == 2) ? -TOPT_YMAX : 0; };
float(entity e, float p) SV_TASOptHi = { if (p == 2) return TOPT_YMAX; if (p == 3) return TOPT_FMAX; return e.topt_rmax; };

// P1097: what is scored. Speed, or with `time` segments reached, the tick the last one opened and
// speed / 10: one segment scores below 2^19, where float32 still tells 0.3 u/s apart.
float(entity e) SV_TASOptSegs =
{
	if (e.run_st_seg < 0 || e.run_st_seg <= e.topt_seg0) return 0;
	return e.run_st_seg - e.topt_seg0;
};
float(entity e) SV_TASOptScore =
{
	local float spd, segs;
	spd = vlen([e.velocity_x, e.velocity_y, 0]);
	if (!e.topt_obj) return spd;
	segs = SV_TASOptSegs(e);
	spd = min(9990, spd) / 10;
	if (!segs) return spd;
	return segs * 200000 + bound(0, e.topt_head + e.topt_n - e.run_st_tick, 128) * 1000 + spd;
};
string(entity e, float v) SV_TASOptDesc =
{
	local float spd;
	spd = vlen([e.velocity_x, e.velocity_y, 0]);
	if (!e.topt_obj) return sprintf("%.1f u/s", v);
	if (!SV_TASOptSegs(e)) return sprintf("no new segment, %.1f u/s", spd);
	return sprintf("segment +%.0f at tick %.0f, %.1f u/s", SV_TASOptSegs(e), e.run_st_tick, spd);
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

void(entity e, string why) SV_TASOptStop =
{
	if (!e.topt_on) return;
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING)
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
	e.topt_on = 0;
	sprint(e, PRINT_HIGH, sprintf("tas optimize: stopped after %.0f candidates: %s\n", e.topt_evals, why));
	if (e.topt_bestv >= 0)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best so far turn %.3f deg/tick%s, %s %.1f (not applied)\n", e.topt_bestr,
			SV_TASOptExtra(e), e.topt_obj ? "score" : "u/s", e.topt_bestv));
};

// The candidate's inputs onto the native tape: yaw0 + board, then turning r a tick, and over the
// last topt_fk ticks turning f a tick instead.
float(entity e, float r, float y, float f) SV_TASOptTape =
{
	local float i, tx, ok, yaw, m;
	if (!tas_tape(e, 2, e.topt_n, 0, '0 0 0', '0 0 0', 0)) return FALSE;
	tx = tas_tape(e, 3, e.topt_n, 0, '0 0 0', '0 0 0', 0);
	ok = tx > 0;
	m = e.topt_n - e.topt_fk;
	for (i = 0; i < e.topt_n && ok; i = i + 1)
	{
		if (i < m || f == r) yaw = e.topt_yaw0 + e.topt_dir * (y + r * (i + 1));
		else yaw = e.topt_yaw0 + e.topt_dir * (y + r * m + f * (i + 1 - m));
		yaw = yaw - 360 * floor((yaw + 180) / 360);     // SV_TASPWord unwraps only one turn
		ok = tas_tape(e, 4, tx, i, [0, -450 * e.topt_dir, 0],
			[SV_TASPWord(e.topt_pitch0), SV_TASPWord(yaw), 0], 0);
	}
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
	if (e.topt_iter >= TOPT_GOLD)
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
			sprint(e, PRINT_HIGH, sprintf("tas optimize: best %s turn %.3f deg/tick over %.0f ticks: exit %.1f u/s (%.0f candidates); paused at %.0f\n",
				(e.topt_dir > 0) ? "left" : "right", e.topt_bestr, e.topt_n, v, e.topt_evals, SV_TimerTicks(e)));
		if (e.topt_mode)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: with%s\n", substring(SV_TASOptExtra(e), 1, -1)));
		if (fabs(v - e.topt_bestv) > 0.05)  // a moving world can differ between two plays
			sprint(e, PRINT_HIGH, sprintf("tas optimize: replayed %.1f %s, searched %.1f: the world moved between them\n", v,
				e.topt_obj ? "score" : "u/s", e.topt_bestv));
		if (e.topt_bestr >= e.topt_rmax - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: that is the top of the range searched; a sharper turn may be faster\n");
		if ((e.topt_mode & 1) && fabs(e.topt_besty) >= TOPT_YMAX - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: the board is at the end of its range; a wider one may be faster\n");
		if ((e.topt_mode & 2) && e.topt_bestf >= TOPT_FMAX - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: the flick is at the top of its range\n");
		return;
	}
	p = SV_TASOptParam(e, e.topt_srch);
	if (e.topt_mode || e.topt_obj) sprint(e, PRINT_HIGH, sprintf("tas optimize: %.0f  %s %.3f -> %s\n", e.topt_evals,
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
		step = (hi - lo) / (TOPT_GRID - 1);
		if (e.topt_k < TOPT_GRID) { e.topt_cand = lo + e.topt_k * step; return; }
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
	local float head;
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

void(entity e) SV_TASOptReset =
{
	e.topt_on = 0;
};

// tas optimize <ticks> <left|right> [board] [flick [k]] [time]
void(entity e, float argc) SV_TASOptCommand =
{
	local float n, dir, i, mode, fk, searches, obj;
	local string w;
	n = stof(argv(2));
	dir = !strcmp(argv(3), "left") ? 1 : (!strcmp(argv(3), "right") ? -1 : 0);
	mode = 0; fk = 0; obj = 0;
	for (i = 4; i < argc; i = i + 1)
	{
		w = argv(i);
		if (w == "time" && !obj && mode >= 0) obj = 1;
		else if (w == "board" && !(mode & 1)) mode = mode | 1;
		else if (w == "flick" && !(mode & 2)) { mode = mode | 2; fk = 4; }
		else if ((mode & 2) && fk == 4 && argv(i - 1) == "flick" && stof(w) >= 1 && stof(w) <= 32 && stof(w) == floor(stof(w)) && w == ftos(stof(w))) fk = stof(w);
		else { mode = -1; break; }
	}
	if (argc >= 4 && argc <= 8 && n >= 4 && n <= TAS_TAPE_MAX && n == floor(n) && dir && mode >= 0 && fk >= n)
	{
		sprint(e, PRINT_HIGH, sprintf("tas optimize: the flick (%.0f ticks) must be shorter than the run (%.0f ticks)\n", fk, n));
		return;
	}
	if (argc < 4 || argc > 8 || !(n >= 4 && n <= TAS_TAPE_MAX && n == floor(n)) || !dir || mode < 0)
	{
		sprint(e, PRINT_HIGH, "tas optimize <ticks 4..128> <left|right> [board] [flick [ticks 1..32]] [time]: best turn for exit speed, or with time the next segment soonest\n");
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
	e.topt_obj = obj; e.topt_seg0 = e.run_st_seg;
	// Source's air wish speed cap is 30: the speed-holding turn is asin(30 / v) a tick.
	e.topt_rmax = bound(1, 2 * asin(min(1, 30 / max(30, vlen([e.velocity_x, e.velocity_y, 0])))) * 180 / M_PI, 45);
	e.topt_bestf = -1;                  // no flick until its search finds a faster one
	for (searches = 0; SV_TASOptParam(e, searches); searches = searches + 1) ;
	sprint(e, PRINT_HIGH, sprintf("tas optimize: from tick %.0f, %.0f ticks turning %s, 0..%.2f deg/tick, %.0f candidates\n",
		e.topt_head, n, argv(3), e.topt_rmax, searches * (TOPT_GRID + TOPT_GOLD + 2) + 1));
	if (mode)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: %s%s%s\n", (mode & 1) ? "board -30..30 deg" : "", (mode == 3) ? "; " : "",
			(mode & 2) ? sprintf("flick over the last %.0f ticks, 0..%.0f deg/tick", fk, TOPT_FMAX) : ""));
	if (obj)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: scoring segments past %.0f reached, then how soon, then speed\n", e.topt_seg0));
};
