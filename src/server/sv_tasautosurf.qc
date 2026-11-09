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
.float as_tube, as_look, as_tries, as_backmax, as_hop, as_finish, as_pace, as_emin;
.float as_backhead, as_backfail;
.float as_startpause, as_laststate;
// `start`: a legal start (tas start <zone>) driven by the native guide (P1308: each tick's best-gain yaw, ground
// friction included) -- as_sg ground ticks of W + strafe key from yaw as_sy, one jump (the start's one hop), then
// guided air strafing (side as_sair) in 2-tick steps until the run starts, where the chain begins.
.float as_szone, as_sg, as_sy, as_sside, as_sair, as_sn;
// `onjump` / `onexit`: armed in the start box while the player prestrafes live; paused at their jump (then guided
// air strafing toward the demo's exit point) or at the exit, the chain takes over (Lex, 10 Nov).
.float as_arm, as_nolegal, as_lastground;
.float as_sn2;                  // ticks steered since the run started (the start clears the box's triggers first)
.float as_sph;                  // the start's ground phase: 0 speed (a left circle), 1 onto the line, 2 around again
.vector as_ex;                  // the demo's position as its run starts (its first sample at t >= 0)
.vector as_exd;                 // and its horizontal heading there: the start steers onto that line
void(entity e, float z) SV_TASLegalStart;    // `tas autosurf startpause`: pause on a run's first tick (TAS on), and the state seen last   // the head at the last rewind request, and requests since it last moved
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
	SV_TASAutoNote(e, 3, (substring(why, 0, 5) == "stuck") ? why : strcat("stopped: ", why));   // a driver waits on stuck/stopped
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

// A tick sooner at this stretch's board is worth what the speed for the rest of the demo's route would gain:
// PM_TICK * (its length left / its time left) / its time left, u/s a tick (surf_null: ~0.6 at board 1, ~1.7
// at board 6), times the `pace` option; "" when off.
string(entity e, float i) SV_TASAutoPace =
{
	local float k, len, tl, x;
	if (e.as_pace <= 0) return "";
	len = 0;
	for (k = as_nrows - 1; k > 0 && as_rows[k*7] > as_wt[i]; k = k - 1)
		len = len + vlen(SV_TASAutoRowO(k) - SV_TASAutoRowO(k - 1));
	tl = max(3, as_rows[(as_nrows - 1) * 7] - as_wt[i]);
	x = bound(0.05, e.as_pace * PM_TICK * (len / tl) / tl, 20);
	return sprintf(" pace %.2f", x);
};

void(entity e, float fwd, float side, float yaw, float bits, float n) SV_TASAutoGuide =
{
	local float argc;
	yaw = yaw - 360 * floor((yaw + 180) / 360);     // the plan takes -360..360 (FS_TASEditValue); a mirror can leave it
	argc = tokenize(sprintf("tas next guide %.0f %.0f 0 %.4f %.0f %.0f 1 0", fwd, side, yaw, bits, n));
	SV_TASPlanCommand(e, argc);
};

// One guided step of the start toward the demo's exit line (a point 300 u past where its run starts, along its
// heading): the strafe side that turns the velocity toward it, alternating once within `tol` degrees so the line
// holds; a side change mirrors the view about the velocity (the guide's own slew would take ~15 ticks to swing
// it). A fixed side circled in the box (rig tpre1, 10 Nov).
// The native guide's best-gain yaw for these keys from the body's velocity (SV_TASGuideYaw, sv_tas_control.h:
// friction first on the ground, the wish at acos((cap - impulse) / speed) off the velocity), so each step starts
// on it: a step's preset came from v_angle, which a TAS pause need not hold, and 3-tick steps topped out at
// 269 u/s where one long guide command reached 290 (rig tstart4). -1000 without a bearing.
float(entity e, float fwd, float side) SV_TASAutoGuideYaw =
{
	local float sp, wish, ctrl, imp, cap, dot, th, ground, surf, off;
	ground = (e.flags & FL_ONGROUND) ? 1 : 0;
	sp = vlen([e.velocity_x, e.velocity_y, 0]);
	if (sp < 1) return -1000;
	wish = min(sqrt(fwd * fwd + side * side), cvar("sv_maxspeed"));
	if (ground)
	{
		ctrl = max(sp, cvar("sv_stopspeed"));
		sp = sp - ctrl * cvar("sv_friction") * PM_TICK;
		if (sp <= 0.0001) return -1000;
	}
	surf = (!ground && e.velocity_z > 0 && e.velocity_z <= 140) ? 0.25 : 1;
	imp = (ground ? cvar("sv_accelerate") : cvar("sv_airaccelerate")) * wish * PM_TICK * surf;
	cap = ground ? wish : min(wish, 30);
	dot = bound(0, cap - imp, sp);
	th = acos(dot / sp) * 180 / M_PI;
	off = fwd ? ((side < 0) ? 45 : -45) : ((side < 0) ? 90 : -90);
	return vectoyaw([e.velocity_x, e.velocity_y, 0]) + ((side < 0) ? th : -th) - off;
};

// A guided step for these keys, starting on the guide's yaw (`rest` without a bearing).
void(entity e, float fwd, float side, float bits, float n, float rest) SV_TASAutoStep =
{
	local float yaw;
	yaw = SV_TASAutoGuideYaw(e, fwd, 400 * side);
	if (yaw <= -1000) yaw = rest;
	e.as_sair = side;
	SV_TASAutoGuide(e, fwd, 400 * side, yaw, bits, n);
};

// fside -1 / 1 holds that side (the start's speed circle); from rest the wish starts along `rest`'s yaw.
void(entity e, float fwd, float bits, float n, float tol, float fside, float rest) SV_TASAutoSteer =
{
	local float h, d, side, yaw;
	h = (vlen([e.velocity_x, e.velocity_y, 0]) > 30) ? vectoyaw([e.velocity_x, e.velocity_y, 0]) : rest;
	d = vectoyaw(e.as_ex + e.as_exd * 300 - e.origin) - h;
	d = d - 360 * floor((d + 180) / 360);
	side = (fabs(d) < tol) ? -e.as_sair : ((d > 0) ? -1 : 1);       // + yaw turns left: the left key (-)
	if (fabs(d) > 150) side = e.as_sair;    // the line behind: hold the turn (d's sign flipped each step there and
	                                        // every flip's mirrored view bled speed: 269 u/s, rig tstart3)
	if (fside) side = fside;
	yaw = SV_TASAutoGuideYaw(e, fwd, 400 * side);
	if (yaw <= -1000) yaw = h + ((side < 0) ? -45 : 45) * (fwd ? 1 : 2);    // from rest: wish along the line
	e.as_sair = side;
	SV_TASAutoGuide(e, fwd, 400 * side, yaw, bits, n);
};

// The body overlaps a trigger volume (QC acts on it, so a rollout starting inside is cut at once: surf_null's
// own main_map_startzone has the start box's bounds and every candidate of the first search met it, rig tstart3).
float(entity e) SV_TASAutoTouching =
{
	local entity t;
	for (t = nextent(world); t; t = nextent(t))
		if (t.solid == SOLID_TRIGGER && t != e)
		if (t.absmin_x <= e.absmax_x + 1 && t.absmax_x >= e.absmin_x - 1 && t.absmin_y <= e.absmax_y + 1 && t.absmax_y >= e.absmin_y - 1 &&
		    t.absmin_z <= e.absmax_z + 1 && t.absmax_z >= e.absmin_z - 1)
			return TRUE;
	return FALSE;
};

// Energy against one height for the whole demo (its first sample's): signed sqrt(v.v + 2g dz), so reaches
// compare across stretches and runs (a search's own figure is from where that stretch started).
float(vector v, float z) SV_TASAutoVE =
{
	local float x;
	x = v * v + 2 * cvar("sv_gravity") * (z - as_rows[3]);
	return (x < 0) ? -sqrt(-x) : sqrt(x);
};

// The least energy this stretch's reach counts at: the demo's speed at its board times `emin` (0.9), as
// energy from where the body stands now (the search's own reference); "" when off. A reach well under
// it left the next stretches tried without the speed to make them (Lex, 10 Nov).
string(entity e, float i) SV_TASAutoEmin =
{
	local float k, v2, x;
	if (e.as_emin <= 0) return "";
	for (k = 0; k < as_nrows - 1 && as_rows[k*7] < as_wt[i] - 0.0001; k = k + 1) ;
	v2 = as_rows[k*7+4] * as_rows[k*7+4] + as_rows[k*7+5] * as_rows[k*7+5] + as_rows[k*7+6] * as_rows[k*7+6];
	x = 2 * cvar("sv_gravity") * (as_rows[k*7+3] - e.origin_z) + e.as_emin * e.as_emin * v2;
	x = (x < 0) ? -sqrt(-x) : sqrt(x);
	return sprintf(" emin %.1f", x);
};

// One stretch: the demo's rows from where it left off, the target, the search.
void(entity e) SV_TASAutoLink =
{
	local float i, h, argc, r;
	local vector o, n;
	local string ps, ls, cl;
	i = e.as_i;
	as_ws[i] = SV_TimerTicks(e); as_wp[i] = e.as_tprev;
	h = min(TOPT_HMAX, max(16, rint(1.25 * (as_wt[i] - e.as_tprev) / PM_TICK) + 10 + e.as_look));
	argc = tokenize(sprintf("tas demorows %s %.4f", e.as_file, e.as_tprev + PM_TICK));    // a row's input produced it
	e.topt_dn = 0;
	SV_TASDemoRowsCommand(e, argc);
	if (e.topt_dn < 16) { SV_TASAutoStop(e, "the demo's rows for this stretch did not load"); return; }   // not the last stretch's (review)
	h = min(h, e.topt_dn);
	o = [as_wo[i*3], as_wo[i*3+1], as_wo[i*3+2]]; n = [as_wn[i*3], as_wn[i*3+1], as_wn[i*3+2]];
	r = (as_wk[i] == 2) ? 50 : ((as_wk[i] == 3) ? 400 : 800);
	if (n == '0 0 0') argc = tokenize(sprintf("tas target %.1f %.1f %.1f %.0f", o_x, o_y, o_z, r));
	else argc = tokenize(sprintf("tas target %.1f %.1f %.1f %.0f %.4f %.4f %.4f", o_x, o_y, o_z, r, n_x, n_y, n_z));
	e.topt_tgton = 0;
	SV_TASTargetCommand(e, argc);
	if (!e.topt_tgton) { SV_TASAutoStop(e, "this stretch's target was refused"); return; }
	ps = strcat(SV_TASAutoPace(e, i), SV_TASAutoEmin(e, i));   // not inside the sprintf's argument list (a call there clobbers the args set)
	ls = (e.as_look > 0) ? sprintf(" look %.0f", e.as_look) : "";
	cl = sprintf("tas optimize %.0f left curve 12 demo aim late tube %.0f%s%s%s energy fast", h, e.as_tube, e.as_hop ? " hop" : "", ls, ps);
	if (cvar("developer")) sprint(e, PRINT_HIGH, strcat("tas autosurf: ", cl, "\n"));
	argc = tokenize(cl);
	SV_TASOptCommand(e, argc);
	if (!e.topt_on) e.topt_outcome = -1;        // refused: a failed try
	e.as_stage = 2;
	SV_TASAutoNote(e, 1, sprintf("stretch %.0f of %.0f (%s at demo t=%.2f), try %.0f", i + 1, as_n,
		(as_wk[i] == 1) ? "board" : ((as_wk[i] == 2) ? "hop" : "finish"), as_wt[i], e.as_try + 1));
};

// After SV_TASDemoFrame (SV_TASOptFrame): the next step of the chain once no search is running.
void(entity e) SV_TASAutoFrame =
{
	local float head, i, best, d, t, s, along, lat, herr, ee, ph;
	local vector u, cr, cl, nn;
	// The TAS timeline (rewinds, edits, every tool here) begins with the running attempt, so a start box's
	// prestrafe and jump stay the player's: paused on the first running tick, autosurf takes the fall to the
	// first ramp from there (Lex, 10 Nov).
	if (e.as_startpause && e.run_tas_mode && !e.run_tas_paused && e.run_t_state == TS_RUNNING && e.as_laststate != TS_RUNNING)
		if (SV_TASPauseNow(e)) sprint(e, PRINT_HIGH, sprintf("tas autosurf: paused on the run's first tick (%.0f); press Autosurf\n", SV_TimerTicks(e)));
	e.as_laststate = e.run_t_state;
	if (e.as_on && e.as_stage == 20)
	{	// armed: the player's own prestrafe; take over at the jump (as_arm 2) or the exit (1)
		if (e.run_t_state == TS_RUNNING)
		{
			if (e.run_tas_paused || SV_TASPauseNow(e)) { e.as_stage = 12; return; }
			SV_TASAutoStop(e, "could not pause where the run started"); return;
		}
		if (e.as_arm == 2 && e.run_t_state == TS_ARMED && !e.run_tas_paused && e.as_lastground && !(e.flags & FL_ONGROUND) && e.velocity_z > 100)
			if (SV_TASPauseNow(e))
			{
				e.as_stage = 12; e.as_sn = 0;
				SV_TASAutoNote(e, 1, sprintf("took over at your jump: %.0f u/s", vlen([e.velocity_x, e.velocity_y, 0])));
			}
		e.as_lastground = (e.flags & FL_ONGROUND) ? 1 : 0;
		return;
	}
	if (e.as_on && e.as_stage >= 10)
	{	// the start: a step at a time, each once the last has landed
		if (e.run_tas_pending || e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING) return;
		if (!e.run_tas_paused || (!e.taslg_on && !e.as_nolegal)) { SV_TASAutoStop(e, "the start ended (TAS play, a move, a respawn)"); return; }
		if (e.as_stage == 10 && e.run_t_state != TS_RUNNING)
		{	// the prestrafe, 3 ticks a step; the jump once at speed and lined up within reach of the box's edge
			d = vlen([e.as_ex_x - e.origin_x, e.as_ex_y - e.origin_y, 0]);
			t = vlen([e.velocity_x, e.velocity_y, 0]);
			best = vectoyaw(e.as_ex + e.as_exd * 300 - e.origin) - vectoyaw([e.velocity_x, e.velocity_y, 0]);
			best = fabs(best - 360 * floor((best + 180) / 360));
			// Time in the box is free: land (surf_null's start drops 160 u from a clip cage), build the speed on a left
			// circle from across the line (the guide's circle at the 289 ceiling is ~116 u across), then capture the
			// demo's exit line as a runway: on until a full-speed turn's circle meets it tangentially 260+ u short of
			// the exit, that turn, then the line with a lateral trim; jump on it 130-220 u short (the jump's 218 u
			// arc clears the edge). Past that unaligned: back to 450+ u and again. Modelled offline first
			// (startsim4.py: every start heading 240-330 deg jumped at 289 u/s within 31 u of the line); a pursuit-only
			// version circled the same loop 227 u off the line for 900 ticks (rig tstart7).
			if (!(e.flags & FL_ONGROUND)) { SV_TASAutoGuide(e, 0, 0, e.v_angle_y, 0, 2); return; }
			nn = [-e.as_exd_y, e.as_exd_x, 0];
			along = -((e.origin_x - e.as_ex_x) * e.as_exd_x + (e.origin_y - e.as_ex_y) * e.as_exd_y);
			lat = (e.origin_x - e.as_ex_x) * nn_x + (e.origin_y - e.as_ex_y) * nn_y;
			i = (t > 1) ? vectoyaw([e.velocity_x, e.velocity_y, 0]) : vectoyaw(e.as_exd) + 100;
			herr = vectoyaw(e.as_exd) - i; herr = herr - 360 * floor((herr + 180) / 360);
			ph = e.as_sph;
			if (cvar("developer") && !(e.as_sn % 30))
				sprint(e, PRINT_HIGH, strcat(sprintf("tas autosurf: start %.0f ph %.0f at %v %.0f u/s, ", e.as_sn, ph, e.origin, t),
					sprintf("%.0f u short of the exit, %.0f u off the line, %.0f deg off it, side %.0f\n", along, lat, herr, e.as_sair)));
			if (ph == 0 && t >= 283) ph = 1;
			if ((ph >= 1 && ph != 4 && fabs(lat) < 100 && fabs(herr) < 10 && along >= 130 && along <= 220) || along < 60 || e.as_sn >= e.as_sg)
			{
				SV_TASAutoStep(e, 400, e.as_sair, 1, 1, e.v_angle_y);         // the start's one jump
				SV_TASAutoNote(e, 1, sprintf("start: jumped at %.0f u/s, %.0f u short of the demo's exit, %.0f u and %.0f deg off its line", t, along, lat, herr));
				e.as_stage = 12; e.as_sn = 0;
				return;
			}
			if (ph >= 1 && ph <= 3 && along < 130) ph = 4;
			if (ph == 4 && along > 450) ph = 1;
			if (ph == 0) d = -1;
			else if (ph == 4)
			{	// back toward the box's back: a point 520 u short of the exit on the line
				ee = vectoyaw(e.as_ex - e.as_exd * 520 - e.origin) - i; ee = ee - 360 * floor((ee + 180) / 360);
				d = (fabs(ee) > 150) ? e.as_sair : ((ee > 3) ? -1 : ((ee < -3) ? 1 : -e.as_sair));
			}
			else if (ph == 2) { d = e.as_sair; if (fabs(herr) < 6) ph = 3; }
			else if (ph == 3)
			{
				ee = herr + bound(-20, -lat * 0.3, 20); ee = ee - 360 * floor((ee + 180) / 360);
				d = (ee > 3) ? -1 : ((ee < -3) ? 1 : e.as_sair);	// a side change past 3 deg only, a tick a step:
				e.as_sph = ph;										// the 3-tick alternation lost speed (247, tstart8)
				SV_TASAutoStep(e, 400, d, 0, 1, vectoyaw(e.as_exd) - 90);
				e.as_sn = e.as_sn + 1;
				return;
			}
			else
			{	// the runway capture: a right turn's circle (centre right of the velocity) meets the line when its
				// centre is R right of it, a left turn's when R left; R ~116 at the 289 ceiling
				u = normalize([e.velocity_x, e.velocity_y, 0]);
				cr = e.origin + 116 * [u_y, -u_x, 0]; cl = e.origin + 116 * [-u_y, u_x, 0];
				if (fabs(herr) < 100 && fabs((cr_x - e.as_ex_x) * nn_x + (cr_y - e.as_ex_y) * nn_y + 116) < 15 &&
				    fabs(-((cr_x + 116 * nn_x - e.as_ex_x) * e.as_exd_x + (cr_y + 116 * nn_y - e.as_ex_y) * e.as_exd_y) - 430) <= 170)
					{ d = 1; ph = 2; }
				else if (fabs(herr) < 100 && fabs((cl_x - e.as_ex_x) * nn_x + (cl_y - e.as_ex_y) * nn_y - 116) < 15 &&
				    fabs(-((cl_x - 116 * nn_x - e.as_ex_x) * e.as_exd_x + (cl_y - 116 * nn_y - e.as_ex_y) * e.as_exd_y) - 430) <= 170)
					{ d = -1; ph = 2; }	// a tangent point 260-600 u short: deeper, the turn met the back wall (tstart8: 213 u/s)
				else if (fabs(herr) > 100) d = e.as_sair;                  // facing away: come round
				else
				{	// pursue a point 250 u ahead on the line
					ee = vectoyaw(e.as_ex - e.as_exd * (along - 250) - e.origin) - i; ee = ee - 360 * floor((ee + 180) / 360);
					d = (ee > 3) ? -1 : ((ee < -3) ? 1 : -e.as_sair);
				}
			}
			e.as_sph = ph;
			SV_TASAutoStep(e, 400, d, 0, 3, vectoyaw(e.as_exd) - 90);      // from rest: across the line (startsim4: 240-330 deg)
			e.as_sn = e.as_sn + 3;
		}
		else if (e.run_t_state == TS_RUNNING && e.as_sn2 < 30 && (e.as_sn2 < 4 || SV_TASAutoTouching(e)))
		{	// out of the box: on until clear of its volumes (at least 4 ticks, at most 30)
			SV_TASAutoSteer(e, (e.flags & FL_ONGROUND) ? 400 : 0, 0, 2, 3, 0, vectoyaw(e.as_exd)); e.as_sn2 = e.as_sn2 + 2;
		}
		else if (e.run_t_state == TS_RUNNING)
		{
			s = SV_TASAutoPlan(e);
			if (s < 0 || as_n < 1) { SV_TASAutoStop(e, "out of the start box off the demo's route (not within 400 u)"); return; }
			e.as_stage = 1; e.as_i = 0; e.as_try = 0; e.as_backs = 0; e.as_tprev = as_rows[s*7];
			sprint(e, PRINT_HIGH, sprintf("tas autosurf: out of the start box at %.0f u/s (tick %.0f); %.0f stretches ahead\n",
				vlen([e.velocity_x, e.velocity_y, 0]), SV_TimerTicks(e), as_n));
		}
		else if (e.as_sn >= 240) SV_TASAutoStop(e, "the start never left the box (240 air ticks)");
		else { SV_TASAutoSteer(e, 0, 0, 2, 3, 0, vectoyaw(e.as_exd)); e.as_sn = e.as_sn + 2; }    // in the air in the box
		return;
	}
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
			for (i = 0; i < as_nrows - 1 && as_rows[i*7] < as_wt[e.as_i] - 0.0001; i = i + 1) ;
			// speed at farsh's board height (the energy carried there) against his own: vE near 0 magnified the gap
			d = e.velocity * e.velocity + 2 * cvar("sv_gravity") * (e.origin_z - as_rows[i*7+3]);
			sprint(e, PRINT_HIGH, sprintf("tas autosurf: stretch %.0f reached: %.0f u/s at farsh's board height, farsh %.0f\n", e.as_i + 1,
				(d < 0) ? -sqrt(-d) : sqrt(d), vlen([as_rows[i*7+4], as_rows[i*7+5], as_rows[i*7+6]])));
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
	local float i, s, n, st, flip, arm;
	local string w, path;
	if (argc == 3 && argv(2) == "stop") { if (e.as_on) SV_TASAutoStop(e, "stopped"); else sprint(e, PRINT_HIGH, "tas autosurf: not running\n"); return; }
	if (argc == 3 && argv(2) == "startpause")
	{
		e.as_startpause = !e.as_startpause; e.as_laststate = e.run_t_state;
		sprint(e, PRINT_HIGH, e.as_startpause ? "tas autosurf: startpause on -- a TAS run pauses on its first tick out of the start box\n"
			: "tas autosurf: startpause off\n");
		SV_TASAutoNote(e, e.as_on ? 1 : 0, e.as_startpause ? "startpause on" : "startpause off");
		return;
	}
	if (argc == 3 && argv(2) == "status")
	{
		if (e.as_on) SV_TASAutoNote(e, 1, sprintf("stretch %.0f of %.0f, try %.0f, %.0f backtracks", e.as_i + 1, as_n, e.as_try + 1, e.as_backs));
		else SV_TASAutoNote(e, 0, "idle");
		return;
	}
	path = argv(2);
	if (argc < 3 || path == "" || strstrofs(path, "..") >= 0)
	{
		sprint(e, PRINT_HIGH, "tas autosurf <demo.rec> [tube R] [look N] [tries N] [backs N] [pace X] [emin F] [nohop] [finish] [start [zone N] [sg N] [sy Y] [sright] [sflip] | onjump | onexit] | stop | status | startpause\n");
		return;
	}
	if (e.as_on || e.topt_on || e.tdem_on) { sprint(e, PRINT_HIGH, "tas autosurf: a search, demo or autosurf is running\n"); return; }
	if (!SV_TASDemoPathOK(path)) { sprint(e, PRINT_HIGH, "tas autosurf: a .rec under data/ or cfg/ksfreplays/\n"); return; }
	if (SV_TASOptBusy(e)) return;
	st = 0; flip = 0; arm = 0; e.as_szone = 0; e.as_sg = 900; e.as_sy = 0; e.as_sside = -1;
	e.as_tube = 300; e.as_look = 100; e.as_tries = 2; e.as_backmax = 6; e.as_hop = 1; e.as_finish = 0; e.as_pace = 1; e.as_emin = 0.9;
	for (i = 3; i < argc; i = i + 1)
	{
		w = argv(i); n = FS_TASNumber(argv(i + 1)) ? stof(argv(i + 1)) : -1;    // not a number: refused below, not 0 (review)
		if (w == "tube" && n >= 50 && n <= 2000) { e.as_tube = n; i = i + 1; }
		else if (w == "look" && n >= 0 && n <= 400) { e.as_look = rint(n); i = i + 1; }
		else if (w == "tries" && n >= 1 && n <= 10) { e.as_tries = rint(n); i = i + 1; }
		else if (w == "backs" && n >= 0 && n <= 50) { e.as_backmax = rint(n); i = i + 1; }
		else if (w == "pace" && n >= 0 && n <= 10) { e.as_pace = n; i = i + 1; }    // 0: energy alone
		else if (w == "emin" && n >= 0 && n <= 1.2) { e.as_emin = n; i = i + 1; }   // 0: any speed counts
		else if (w == "nohop") e.as_hop = 0;
		else if (w == "start") st = 1;
		else if (w == "zone" && n >= 0 && n < 64 && n == floor(n)) { e.as_szone = n; i = i + 1; }
		else if (w == "sg" && n >= 6 && n <= 2000 && n == floor(n)) { e.as_sg = n; i = i + 1; }   // the most ground ticks before the jump
		else if (w == "sy" && FS_TASNumber(argv(i + 1)) && fabs(stof(argv(i + 1))) <= 360) { e.as_sy = stof(argv(i + 1)); i = i + 1; }
		else if (w == "sright") e.as_sside = 1;
		else if (w == "sflip") flip = 1;
		else if (w == "onjump") arm = 2;
		else if (w == "onexit") arm = 1;
		else if (w == "finish") e.as_finish = 1;
		else { sprint(e, PRINT_HIGH, sprintf("tas autosurf: unknown option '%s'\n", w)); return; }
	}
	// `start` begins in the start box, before the running attempt the tools need (it is a legal start's own path)
	if (st || arm) { if (Lobby_Active() || !e.run_tas_rwcap) { SV_TASToolGate(e, "autosurf"); return; } }
	else if (!SV_TASToolGate(e, "autosurf")) return;
	e.as_sair = flip ? -e.as_sside : e.as_sside;
	path = strzone(path);                       // argv is clobbered by the reads and searches below
	as_nrows = SV_TASAutoRead(path);
	if (as_nrows < 0)
	{
		sprint(e, PRINT_HIGH, (as_nrows == -2) ? "tas autosurf: that demo is another map's\n" : sprintf("tas autosurf: cannot read %s\n", path));
		strunzone(path); return;
	}
	e.as_nolegal = 0; e.as_arm = 0;
	for (i = 0; i < as_nrows - 1 && as_rows[i*7] < 0; i = i + 1) ;
	e.as_ex = SV_TASAutoRowO(i);
	e.as_exd = normalize([as_rows[i*7+4], as_rows[i*7+5], 0]);
	if (e.as_exd == '0 0 0') e.as_exd = '1 0 0';
	if (arm)
	{
		if (e.run_t_state != TS_ARMED) { sprint(e, PRINT_HIGH, "tas autosurf: onjump / onexit wait in the start box (stand in it, TAS on)\n"); strunzone(path); return; }
		if (e.as_file != "") strunzone(e.as_file);
		e.as_file = path;
		e.as_on = 1; e.as_stage = 20; e.as_arm = arm; e.as_nolegal = 1; e.as_backs = 0; e.as_sair = -1; e.as_sn2 = 0;
		e.as_lastground = (e.flags & FL_ONGROUND) ? 1 : 0;
		SV_TASAutoNote(e, 1, (arm == 2) ? "armed: prestrafe and jump -- I take over at your jump" : "armed: prestrafe out of the box -- I take over at its edge");
		return;
	}
	if (st)
	{
		SV_TASLegalStart(e, e.as_szone);
		if (!e.taslg_on) { strunzone(path); return; }
		if (e.as_file != "") strunzone(e.as_file);
		e.as_file = path;
		e.as_on = 1; e.as_stage = 10; e.as_backs = 0; e.as_sn = 0; e.as_sn2 = 0; e.as_sair = -1; e.as_sph = 0;
		SV_TASAutoNote(e, 1, "start: prestrafe toward the demo's exit line, then one jump");
		return;
	}
	s = SV_TASAutoPlan(e);
	if (s < 0) { sprint(e, PRINT_HIGH, "tas autosurf: the body is not within 400 u of the demo's route; pause on it\n"); strunzone(path); return; }
	if (as_n < 1) { sprint(e, PRINT_HIGH, "tas autosurf: no ramp, hop or finish ahead on the demo from here\n"); strunzone(path); return; }
	if (e.as_file != "") strunzone(e.as_file);
	e.as_file = path;
	e.as_on = 1; e.as_stage = 1; e.as_i = 0; e.as_try = 0; e.as_backs = 0; e.as_tprev = as_rows[s*7];
	SV_TASAutoNote(e, 1, sprintf("%.0f stretches ahead from demo t=%.2f (%.0f u off its route)", as_n, as_rows[s*7], vlen(SV_TASAutoRowO(s) - e.origin)));
};
