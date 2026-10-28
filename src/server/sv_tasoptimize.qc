/*
  P1088: `tas optimize <ticks> <left|right>` -- the first bounded optimizer (TAS plan Stage 4b).

  From the paused head H it searches one number, a constant yaw rate (degrees a tick) turned
  from your current view while strafing that way at 450, for the highest horizontal exit speed
  at H + ticks. A grid over 0..topt_rmax, then golden-section around its best; every candidate
  is a TAS back to H and an input tape, so it is the real mover on the real map. It ends with
  the best one played, paused at H + ticks. No global optimum is claimed.
*/

#define TOPT_GRID  9            // grid points over 0..topt_rmax
#define TOPT_GOLD  10           // golden-section steps in best +- one grid step
#define TOPT_G     0.618034

.float topt_on, topt_head, topt_n, topt_dir, topt_yaw0, topt_pitch0;
.float topt_stage;              // 1 go back to the head and stage the tape, 2 the tape is running
.float topt_phase;              // 1 grid, 2 golden, 3 the best, played last
.float topt_k, topt_cand, topt_evals, topt_bestr, topt_bestv, topt_next;
.float topt_lo, topt_hi, topt_a, topt_b, topt_fa, topt_fb, topt_which, topt_iter;
.float topt_backed, topt_wait;  // a back sent and not yet seen to land; when a refused tape gives up
.float topt_rmax;               // the range's top: twice the air-strafe turn asin(30 / speed)

void(entity e, string why) SV_TASOptStop =
{
	if (!e.topt_on) return;
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING)
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
	e.topt_on = 0;
	sprint(e, PRINT_HIGH, sprintf("tas optimize: stopped after %.0f candidates: %s\n", e.topt_evals, why));
	if (e.topt_bestv >= 0)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best so far turn %.3f deg/tick, %.1f u/s (not applied)\n", e.topt_bestr, e.topt_bestv));
};

// The candidate's inputs onto the native tape: the yaw turns rate*dir each tick.
float(entity e, float r) SV_TASOptTape =
{
	local float i, tx, ok, yaw;
	if (!tas_tape(e, 2, e.topt_n, 0, '0 0 0', '0 0 0', 0)) return FALSE;
	tx = tas_tape(e, 3, e.topt_n, 0, '0 0 0', '0 0 0', 0);
	ok = tx > 0;
	for (i = 0; i < e.topt_n && ok; i = i + 1)
	{
		yaw = e.topt_yaw0 + e.topt_dir * r * (i + 1);
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

// The next golden-section point, or the final run once the steps are spent.
void(entity e) SV_TASOptGolden =
{
	if (e.topt_iter >= TOPT_GOLD)
	{
		e.topt_phase = 3; e.topt_cand = e.topt_bestr;
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
	local float step;
	e.topt_evals = e.topt_evals + 1;
	if (e.topt_phase == 3)
	{
		e.topt_on = 0;
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best %s turn %.3f deg/tick over %.0f ticks: exit %.1f u/s (%.0f candidates); paused at %.0f\n",
			(e.topt_dir > 0) ? "left" : "right", e.topt_bestr, e.topt_n, v, e.topt_evals, SV_TimerTicks(e)));
		if (fabs(v - e.topt_bestv) > 0.05)  // a moving world can differ between two plays
			sprint(e, PRINT_HIGH, sprintf("tas optimize: replayed %.1f u/s, searched %.1f: the world moved between them\n", v, e.topt_bestv));
		if (e.topt_bestr >= e.topt_rmax - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: that is the top of the range searched; a sharper turn may be faster\n");
		return;
	}
	sprint(e, PRINT_HIGH, sprintf("tas optimize: %.0f  turn %.3f deg/tick -> %.1f u/s\n", e.topt_evals, e.topt_cand, v));
	if (v > e.topt_bestv) { e.topt_bestv = v; e.topt_bestr = e.topt_cand; }
	if (e.topt_phase == 1)
	{
		e.topt_k = e.topt_k + 1;
		step = e.topt_rmax / (TOPT_GRID - 1);
		if (e.topt_k < TOPT_GRID) { e.topt_cand = e.topt_k * step; return; }
		e.topt_phase = 2;
		e.topt_lo = max(0, e.topt_bestr - step); e.topt_hi = min(e.topt_rmax, e.topt_bestr + step);
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
		SV_TASOptResult(e, vlen([e.velocity_x, e.velocity_y, 0]));
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
	if (!SV_TASOptTape(e, e.topt_cand))
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

void(entity e, float argc) SV_TASOptCommand =
{
	local float n, dir;
	n = stof(argv(2));
	dir = !strcmp(argv(3), "left") ? 1 : (!strcmp(argv(3), "right") ? -1 : 0);
	if (argc != 4 || !(n >= 4 && n <= TAS_TAPE_MAX && n == floor(n)) || !dir)
	{
		sprint(e, PRINT_HIGH, "tas optimize <ticks 4..128> <left|right>: best constant turn for exit speed\n");
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
	// Source's air wish speed cap is 30: the speed-holding turn is asin(30 / v) a tick.
	e.topt_rmax = bound(1, 2 * asin(min(1, 30 / max(30, vlen([e.velocity_x, e.velocity_y, 0])))) * 180 / M_PI, 45);
	sprint(e, PRINT_HIGH, sprintf("tas optimize: from tick %.0f, %.0f ticks turning %s, 0..%.2f deg/tick, %.0f candidates\n",
		e.topt_head, n, argv(3), e.topt_rmax, TOPT_GRID + TOPT_GOLD + 3));
};
