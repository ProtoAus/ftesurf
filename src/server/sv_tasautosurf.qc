/*
  P1449: `tas autosurf` -- the rig's chain driver (tools/p1449_chain3.py) inside the game. From a paused
  TAS moment on a demo's route, the demo's ramp boards and platform hops become targets, and each
  stretch is a `tas optimize ... curve demo aim late tube` search played to its reach. A stretch that
  fails its tries sends the chain back to search the one before again (a different state there may let
  it through). One autosurf a server: its arrays are global, and it holds the optimizer's busy guard
  through its searches (SV_TASOptBusy).

    tas autosurf <demo.rec> [tube R] [look N] [tries N] [backs N] [nohop] [finish]
    tas autosurf stop | status
*/
#define TAS_ASMAX   64          // waypoints at most
#define TAS_ASROWS  16384       // demo samples at most (4 minutes at 66.7 a second)

.float as_stage, as_i, as_try, as_backs, as_tprev, as_wait, as_goal;
.float as_tube, as_look, as_tries, as_backmax, as_hop, as_finish;
.float as_backhead, as_backfail;   // the head at the last rewind request, and requests since it last moved
.string as_file;
float as_n;                     // waypoints
float as_wt[TAS_ASMAX];         // the demo's time there
float as_wo[TAS_ASMAX * 3];     // its origin
float as_wn[TAS_ASMAX * 3];     // the face to board ('0 0 1' a hop: a jump there; '0 0 0' any contact)
float as_wk[TAS_ASMAX];         // 1 board, 2 hop, 3 finish
float as_ws[TAS_ASMAX];         // the head tick its stretch started at
float as_wp[TAS_ASMAX];         // the demo time its stretch started from
float *as_rows;                 // the demo's samples: t x y z vx vy vz
float as_nrows;

// The menu's status (cl_tasoptui.qc): state (0 idle, 1 running, 2 finished, 3 stopped), stretch, of,
// try, backtracks, and a line of text.
void(entity e, float state, string note) SV_TASAutoNote =
{
	sprint(e, PRINT_HIGH, strcat("tas autosurf: ", note, "\n"));
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET); WriteByte(MSG_MULTICAST, TAS_EV_AUTOSURF);
	WriteByte(MSG_MULTICAST, state); WriteShort(MSG_MULTICAST, e.as_i); WriteShort(MSG_MULTICAST, as_n);
	WriteByte(MSG_MULTICAST, e.as_try); WriteByte(MSG_MULTICAST, e.as_backs); WriteString(MSG_MULTICAST, note);
	msg_entity = e; multicast(e.origin, MULTICAST_ONE_R);
};

void(entity e, string why) SV_TASAutoStop =
{
	if (!e.as_on) return;
	e.as_on = 0;
	if (e.topt_on) SV_TASOptStop(e, "autosurf stopped");
	SV_TASAutoNote(e, 3, why);
};

vector(float i) SV_TASAutoRowO = { return [as_rows[i*7+1], as_rows[i*7+2], as_rows[i*7+3]]; };

// The demo's samples into as_rows; -1 if it cannot be read, -2 if it is another map's.
float(string path) SV_TASAutoRead =
{
	local float fh, c, blank, n, lines;
	local string line;
	lines = 0;
	if (!as_rows) as_rows = (float*)memalloc(TAS_ASROWS * 7 * 4);
	if (!as_rows) return -1;
	fh = fopen(path, FILE_READ);
	if (fh < 0) return -1;
	n = 0; blank = 0;
	while (n < TAS_ASROWS && blank < 64 && lines < TAS_DEMOLINES * 2)
	{
		line = fgets(fh); lines = lines + 1;
		if (line == "") { blank = blank + 1; continue; }
		blank = 0;
		c = tokenize(line);
		if (argv(0) == "map" && c >= 2 && strcasecmp(argv(1), mapname)) { fclose(fh); return -2; }
		if (c < 7 || !FS_TASNumber(argv(0))) continue;
		as_rows[n*7] = stof(argv(0));
		as_rows[n*7+1] = stof(argv(1)); as_rows[n*7+2] = stof(argv(2)); as_rows[n*7+3] = stof(argv(3));
		as_rows[n*7+4] = stof(argv(4)); as_rows[n*7+5] = stof(argv(5)); as_rows[n*7+6] = stof(argv(6));
		n = n + 1;
	}
	fclose(fh);
	return n;
};

void(float kind, float i, vector n) SV_TASAutoAdd =
{
	if (as_n >= TAS_ASMAX) return;
	as_wt[as_n] = as_rows[i*7]; as_wk[as_n] = kind;
	as_wo[as_n*3] = as_rows[i*7+1]; as_wo[as_n*3+1] = as_rows[i*7+2]; as_wo[as_n*3+2] = as_rows[i*7+3];
	as_wn[as_n*3] = n_x; as_wn[as_n*3+1] = n_y; as_wn[as_n*3+2] = n_z;
	as_n = as_n + 1;
};

// A board's face: a real BSP plane in the surf band (the normal the demo's moves imply mixes the strafe
// in). First the hull dropped from the demo one and two samples into the ride, lying on the face; then
// swept along its last move into the ramp -- nearly parallel to the face at a board, that sweep met the
// ramp's edge instead (surf_null's ramp 1: misses 19 u from the board point, 10 Nov). '0 0 0' if none.
vector(entity e, float b) SV_TASAutoFace =
{
	local vector p, q, n;
	local float k;
	for (k = 1; k <= 2; k = k + 1)
	{
		if (b + k >= as_nrows) continue;
		q = SV_TASAutoRowO(b + k);
		tracebox(q + '0 0 2', PM_HULL_MINS, PM_HULL_MAXS, q - '0 0 48', MOVE_NOMONSTERS, e);
		n = trace_plane_normal;
		if (trace_fraction < 1 && !trace_startsolid && fabs(n_z) >= 0.1 && fabs(n_z) <= 0.72) return n;
	}
	for (k = 0; k < 2; k = k + 1)
	{
		if (b + k < 1 || b + k >= as_nrows) continue;
		p = SV_TASAutoRowO(b + k - 1); q = SV_TASAutoRowO(b + k);
		tracebox(p, PM_HULL_MINS, PM_HULL_MAXS, q + (q - p) * 2, MOVE_NOMONSTERS, e);
		n = trace_plane_normal;
		if (trace_fraction < 1 && fabs(n_z) >= 0.1 && fabs(n_z) <= 0.72) return n;
	}
	return '0 0 0';
};

// The route from the sample nearest the body: each ride's board (samples off free fall for 0.3 s or
// more, entered falling), each platform hop between rides (a landing whose next samples rise), and with
// `finish` the demo's last sample. Returns the start sample, or -1 when the body is not on the route.
float(entity e) SV_TASAutoPlan =
{
	local float i, s, d, best, st, lastleave, gdt, j;
	best = 1000000; s = -1;
	for (i = 0; i < as_nrows; i = i + 1)
	{
		d = vlen(SV_TASAutoRowO(i) - e.origin);
		if (d < best) { best = d; s = i; }
	}
	if (s < 0 || best > 400) return -1;
	as_n = 0; st = -1; lastleave = s; gdt = cvar("sv_gravity") * PM_TICK;
	for (i = s + 1; i < as_nrows; i = i + 1)
	{
		d = fabs(as_rows[i*7+6] - as_rows[i*7-1] + gdt) > 1.5;      // vz off free fall
		if (d && st < 0) st = i;
		if (!d && st >= 0)
		{
			if (as_rows[i*7-7] - as_rows[st*7] >= 0.3 - 0.0001 && as_rows[st*7+6] < -100)
			{
				if (e.as_hop)
					for (j = max(lastleave, s) + 1; j < st - 3; j = j + 1)
						if (as_rows[j*7-1] < -100 && as_rows[j*7+6] > -1 && fabs(as_rows[j*7+3] - as_rows[j*7-4]) < 40)
						if (as_rows[j*7+6] > 150 || as_rows[j*7+13] > 150 || as_rows[j*7+20] > 150)
							SV_TASAutoAdd(2, j, '0 0 1');
				if (st > s + 2) SV_TASAutoAdd(1, st, SV_TASAutoFace(e, st));
				lastleave = i - 1;
			}
			st = -1;
		}
	}
	if (e.as_finish) SV_TASAutoAdd(3, as_nrows - 1, '0 0 0');
	if (cvar("developer"))
		for (i = 0; i < as_n; i = i + 1)
			sprint(e, PRINT_HIGH, sprintf("tas autosurf: stretch %.0f: %s at demo t=%.3f %v, face %v\n", i + 1,
				(as_wk[i] == 1) ? "board" : ((as_wk[i] == 2) ? "hop" : "finish"), as_wt[i],
				[as_wo[i*3], as_wo[i*3+1], as_wo[i*3+2]], [as_wn[i*3], as_wn[i*3+1], as_wn[i*3+2]]));
	return s;
};

// One stretch: the demo's rows from where it left off, the target, the search.
void(entity e) SV_TASAutoLink =
{
	local float i, h, argc, r;
	local vector o, n;
	i = e.as_i;
	as_ws[i] = SV_TimerTicks(e); as_wp[i] = e.as_tprev;
	h = min(TOPT_HMAX, max(16, rint(1.25 * (as_wt[i] - e.as_tprev) / PM_TICK) + 10 + e.as_look));
	argc = tokenize(sprintf("tas demorows %s %.4f", e.as_file, e.as_tprev + PM_TICK));    // a row's input produced it
	e.topt_dn = 0;
	SV_TASDemoRowsCommand(e, argc);
	if (e.topt_dn < 16) { SV_TASAutoStop(e, "the demo's rows for this stretch did not load"); return; }   // not the last stretch's (review)
	h = min(h, e.topt_dn);
	o = [as_wo[i*3], as_wo[i*3+1], as_wo[i*3+2]]; n = [as_wn[i*3], as_wn[i*3+1], as_wn[i*3+2]];
	// a board within the tube of the demo's: one 346 u off left the next stretch outside its tube at once
	// (surf_null board 1 -> 2, and 5 -> 6: closest 8357 u / 13961 u at ticks 31 / 18, 10 Nov)
	r = (as_wk[i] == 2) ? 50 : ((as_wk[i] == 3) ? 400 : min(800, e.as_tube));
	if (n == '0 0 0') argc = tokenize(sprintf("tas target %.1f %.1f %.1f %.0f", o_x, o_y, o_z, r));
	else argc = tokenize(sprintf("tas target %.1f %.1f %.1f %.0f %.4f %.4f %.4f", o_x, o_y, o_z, r, n_x, n_y, n_z));
	e.topt_tgton = 0;
	SV_TASTargetCommand(e, argc);
	if (!e.topt_tgton) { SV_TASAutoStop(e, "this stretch's target was refused"); return; }
	argc = tokenize(sprintf("tas optimize %.0f left curve 12 demo aim late tube %.0f%s%s energy fast", h, e.as_tube,
		e.as_hop ? " hop" : "", (e.as_look > 0) ? sprintf(" look %.0f", e.as_look) : ""));
	SV_TASOptCommand(e, argc);
	if (!e.topt_on) e.topt_outcome = -1;        // refused: a failed try
	e.as_stage = 2;
	SV_TASAutoNote(e, 1, sprintf("stretch %.0f of %.0f (%s at demo t=%.2f), try %.0f", i + 1, as_n,
		(as_wk[i] == 1) ? "board" : ((as_wk[i] == 2) ? "hop" : "finish"), as_wt[i], e.as_try + 1));
};

// After SV_TASDemoFrame (SV_TASOptFrame): the next step of the chain once no search is running.
void(entity e) SV_TASAutoFrame =
{
	local float head, i, best, d, t;
	if (!e.as_on || e.topt_on || e.tdem_on) return;
	if (!e.run_tas_paused || e.run_t_state != TS_RUNNING) { SV_TASAutoStop(e, "TAS play/off, or the run ended"); return; }
	if (e.as_stage == 1) { SV_TASAutoLink(e); return; }
	if (e.as_stage == 2)
	{
		if (e.topt_outcome == 2)
		{	// reached: the next stretch's demo rows start where the demo came nearest this state
			best = 1000000; t = e.as_tprev;
			for (i = 0; i < as_nrows; i = i + 1)
				if (fabs(as_rows[i*7] - as_wt[e.as_i]) <= 2)
				{
					d = vlen(SV_TASAutoRowO(i) - e.origin);
					if (d < best) { best = d; t = as_rows[i*7]; }
				}
			e.as_tprev = t; e.as_i = e.as_i + 1; e.as_try = 0;
			if (e.as_i >= as_n)
			{
				e.as_on = 0;
				SV_TASAutoNote(e, 2, sprintf("finished: %.0f stretches, %.0f backtracks", as_n, e.as_backs));
				return;
			}
			e.as_stage = 1;
			return;
		}
		e.as_try = e.as_try + 1;
		e.as_backhead = -1; e.as_backfail = 0;
		if (e.as_try < e.as_tries) { e.as_goal = as_ws[e.as_i]; e.as_stage = 3; return; }
		if (e.as_backs < e.as_backmax && e.as_i > 0)
		{
			e.as_backs = e.as_backs + 1; e.as_i = e.as_i - 1; e.as_try = 0;
			e.as_tprev = as_wp[e.as_i]; e.as_goal = as_ws[e.as_i]; e.as_stage = 3;
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f failed its tries: backtrack %.0f to stretch %.0f", e.as_i + 2, e.as_backs, e.as_i + 1));
			return;
		}
		SV_TASAutoStop(e, sprintf("stuck at stretch %.0f of %.0f after %.0f backtracks", e.as_i + 1, as_n, e.as_backs));
		return;
	}
	if (e.as_stage == 3)
	{	// back to the stretch's start, 128 ticks a request
		head = SV_TimerTicks(e);
		if (head == e.as_goal) { e.as_stage = 1; return; }
		if (head < e.as_goal) { SV_TASAutoStop(e, "the head went back past the stretch's start"); return; }
		if (e.run_tas_pending || time < e.as_wait) return;
		// a refused request (no native checkpoint there, a pause not allowed) leaves the head: give up after 20
		// tries rather than asking forever (review)
		if (head == e.as_backhead) e.as_backfail = e.as_backfail + 1; else e.as_backfail = 0;
		if (e.as_backfail > 20) { SV_TASAutoStop(e, sprintf("the rewind to tick %.0f was refused at tick %.0f", e.as_goal, head)); return; }
		e.as_backhead = head;
		SV_TASBack(e, min(128, head - e.as_goal), e.run_tas_req + 1);
		e.as_wait = time + 0.05;
	}
};

// P1449 review: a leaving player's tools end with it -- above all a demo's file handle, which the next
// client in the slot would otherwise lose (ED_Clear zeroes tdem_on) until the map changes.
void(entity e) SV_TASToolsDisconnect =
{
	e.as_on = 0;
	if (e.as_file != "") { strunzone(e.as_file); e.as_file = ""; }
	if (e.tdem_on) SV_TASDemoStop(e, "disconnected");
	if (e.topt_on) SV_TASOptStop(e, "disconnected");
	if (topt_busy == e) topt_busy = world;
};

void(entity e, float argc) SV_TASAutoCommand =
{
	local float i, s, n;
	local string w, path;
	if (argc == 3 && argv(2) == "stop") { if (e.as_on) SV_TASAutoStop(e, "stopped"); else sprint(e, PRINT_HIGH, "tas autosurf: not running\n"); return; }
	if (argc == 3 && argv(2) == "status")
	{
		if (e.as_on) SV_TASAutoNote(e, 1, sprintf("stretch %.0f of %.0f, try %.0f, %.0f backtracks", e.as_i + 1, as_n, e.as_try + 1, e.as_backs));
		else SV_TASAutoNote(e, 0, "idle");
		return;
	}
	path = argv(2);
	if (argc < 3 || path == "" || strstrofs(path, "..") >= 0)
	{
		sprint(e, PRINT_HIGH, "tas autosurf <demo.rec> [tube R] [look N] [tries N] [backs N] [nohop] [finish] | stop | status\n");
		return;
	}
	if (e.as_on || e.topt_on || e.tdem_on) { sprint(e, PRINT_HIGH, "tas autosurf: a search, demo or autosurf is running\n"); return; }
	if (!SV_TASDemoPathOK(path)) { sprint(e, PRINT_HIGH, "tas autosurf: a .rec under data/ or cfg/ksfreplays/\n"); return; }
	if (!SV_TASToolGate(e, "autosurf")) return;
	if (SV_TASOptBusy(e)) return;
	e.as_tube = 300; e.as_look = 100; e.as_tries = 2; e.as_backmax = 6; e.as_hop = 1; e.as_finish = 0;
	for (i = 3; i < argc; i = i + 1)
	{
		w = argv(i); n = FS_TASNumber(argv(i + 1)) ? stof(argv(i + 1)) : -1;    // not a number: refused below, not 0 (review)
		if (w == "tube" && n >= 50 && n <= 2000) { e.as_tube = n; i = i + 1; }
		else if (w == "look" && n >= 0 && n <= 400) { e.as_look = rint(n); i = i + 1; }
		else if (w == "tries" && n >= 1 && n <= 10) { e.as_tries = rint(n); i = i + 1; }
		else if (w == "backs" && n >= 0 && n <= 50) { e.as_backmax = rint(n); i = i + 1; }
		else if (w == "nohop") e.as_hop = 0;
		else if (w == "finish") e.as_finish = 1;
		else { sprint(e, PRINT_HIGH, sprintf("tas autosurf: unknown option '%s'\n", w)); return; }
	}
	path = strzone(path);                       // argv is clobbered by the reads and searches below
	as_nrows = SV_TASAutoRead(path);
	if (as_nrows < 0)
	{
		sprint(e, PRINT_HIGH, (as_nrows == -2) ? "tas autosurf: that demo is another map's\n" : sprintf("tas autosurf: cannot read %s\n", path));
		strunzone(path); return;
	}
	s = SV_TASAutoPlan(e);
	if (s < 0) { sprint(e, PRINT_HIGH, "tas autosurf: the body is not within 400 u of the demo's route; pause on it\n"); strunzone(path); return; }
	if (as_n < 1) { sprint(e, PRINT_HIGH, "tas autosurf: no ramp, hop or finish ahead on the demo from here\n"); strunzone(path); return; }
	if (e.as_file != "") strunzone(e.as_file);
	e.as_file = path;
	e.as_on = 1; e.as_stage = 1; e.as_i = 0; e.as_try = 0; e.as_backs = 0; e.as_tprev = as_rows[s*7];
	SV_TASAutoNote(e, 1, sprintf("%.0f stretches ahead from demo t=%.2f (%.0f u off its route)", as_n, as_rows[s*7], vlen(SV_TASAutoRowO(s) - e.origin)));
};
