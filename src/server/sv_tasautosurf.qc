/*
  P1449: `tas autosurf` -- the rig's chain driver (tools/p1449_chain3.py) inside the game. From a paused
  TAS moment on a demo's route, the demo's ramp boards and platform hops become targets, and each
  stretch is a `tas optimize ... curve demo aim late tube` search played to its reach. A stretch that
  fails its tries sends the chain back to search the one before again (a different state there may let
  it through). One autosurf a server: its arrays are global, and it holds the optimizer's busy guard
  through its searches (SV_TASOptBusy).

    tas autosurf <demo.rec> [tube R] [look N] [tries N] [backs N] [nohop] [join] [rideknots] [polish] [low] [finish]
    tas autosurf stop | status
*/
#define TAS_ASMAX   64          // waypoints at most
#define TAS_ASROWS  16384       // demo samples at most (4 minutes at 66.7 a second)

.float as_i, as_try, as_backs, as_tprev, as_wait, as_goal;    // as_stage beside as_on (sv_tasoptimize.qc)
.float as_tube, as_look, as_tries, as_backmax, as_hop, as_finish, as_pace, as_emin;
// `join`: a platform hop sequence is no stretch of its own -- the next board's search hops it (every row holds jump),
// so the first hop's flight can set up the second's turn (Lex, 10 Nov: wider off the first platform, a better right
// turn, lower on surf_null's fifth ramp)
.float as_join;
// `rideknots`: a stretch that starts on a ride passes its search `kex`, the demo's leaving that ride + 15 ticks: most
// of the curve's knots go to the dip and the launch (Lex, 10 Nov: how low to dip, a flick at a ride's end)
.float as_rideknots;
// `polish`: min-max each stretch before going on (Lex, 10 Nov: a human redoes a ramp until the energy is there) --
// every try but the last needs 99% of the demo's speed at the board and searches its longest, ending only after 20
// generations without a gain; the last takes the usual minimum, so a stretch that can't be polished is still made.
// A clicked route has no demo speed: there polish only searches longer. Polish also weighs time a quarter as much
// (pace): the full runs stuck at surf_null's ramp 10 (Lex's count) arriving 345 u under farsh's line at his speed,
// 3.4% short of his energy -- energy is what makes a map (Lex), the time a stretch takes much less.
.float as_polish;
// `low`: a board stretch's search pays 0.25 a unit boarded past the demo's board point along the ramp's run, above it
// up the face or more than 100 u below it, half that more than 100 u before it (optimize `low`; Lex, 10 Nov: where
// farsh boards -- ramp 11's tip, ramp 10's top for the height its flight needs)
.float as_low;
// `apex`: a flight of 1 s or more from a ride to the next board is two stretches, split at farsh's peak -- the launch for
// its energy there, then the flight alone with every knot in the air; a bad board retries from the peak (Lex, 10 Nov:
// a perfectly fine launch, then a bad airtime to the board)
.float as_apex;
// `air`: the route's points ('0 0 0' faces -- `tas route here`, a player's) as aim points in the demo's plan, at the time
// its route passes nearest each, the stretch to one passing within TAS_AIRR (Lex, 10 Nov: the peaks `apex` took from the
// demo were poor -- let a human pick where the bot should be in the sky, e.g. high into the window corner after ramp 6)
.float as_air;
.float as_wide;                 // P1476: the searches' flights weave wider (`wide`)
.float as_redo;                 // a redo's stretch + 1: its first link checks the run is the one that reached it
.float as_spots;                // `spots`: each board tries TAS_SPOTS places on its ramp, each with the stretch after it
.float as_swi, as_swk, as_swph; // the stretch being swept, its spot, 1 searching it / 2 the stretch after (0: none)
#define TAS_AIRR 200       // 120 with a 95% floor: tchain14's best passed 186 u off farsh's peak, the reaches braked to 76%
#define TAS_AIRMIN 0.85    // ...the floor there: a hint where to fly, the board after it keeps the usual one
.float as_backhead, as_backfail;   // the head at the last rewind request, and requests since it last moved
.float as_failat, as_failn;            // the stretch that last failed its tries, and how many times in a row
.float as_failmax;              // the furthest stretch that failed its tries this chain (the stop names it: review 9)
.float as_startpause, as_laststate;    // `tas autosurf startpause`: pause on a run's first tick (TAS on), and the state seen last
// `start`: a legal start (tas start <zone>) driven by the native guide (P1308: each tick's best-gain yaw, ground
// friction included): a speed circle, the demo's exit line captured, one jump (the start's one hop), guided air
// strafing out of the box, then the chain. as_sg caps the ground ticks; as_sair is the strafe side held last.
.float as_szone, as_sg, as_sy, as_sside, as_sair, as_sn;
// `onjump` / `onexit`: armed in the start box while the player prestrafes live; paused at their jump (then guided
// air strafing toward the demo's exit point) or at the exit, the chain takes over (Lex, 10 Nov).
.float as_arm, as_nolegal, as_lastground;
.float as_sn2;                  // ticks steered since the run started (the start clears the box's triggers first)
.float as_sph;                  // the start's ground phase: 0 speed (a left circle), 1 onto the line, 2 around again
.float as_sdrop;                // ticks of the spawn's drop (as_sn2 is the out-of-box phase's own: review 2)
.vector as_runo;                // where the run started (the start box's edge): the start steers 48 u past it before planning
.vector as_ex;                  // the demo's position as its run starts (its first sample at t >= 0)
.vector as_exd;                 // and its horizontal heading there: the start steers onto that line
void(entity e, float z) SV_TASLegalStart;
.string as_file;
.float as_route;                // the chain is the player's clicked route (tas route), not a demo's plan
// P1449: a route clicked in the world (the Optimizer tab's "Add at crosshair"): points and the face to board there
// ('0 0 1' a bhop floor, '0 0 0' a point); `tas autosurf route` surfs it with no demo (Lex, 10 Nov: point and click).
float rt_n;
float rt_o[TAS_ASMAX * 3], rt_nn[TAS_ASMAX * 3];
float as_n;                     // waypoints
// A backtrack's stretch must beat the reach that led to the failure (speed at farsh's board height, +0.25%): the
// full run re-took ramp 5 at 2810-2838 eleven times and failed ramp 6 from each (rigs/tnullfull4, 10 Nov)
float as_rbs[TAS_ASMAX], as_need[TAS_ASMAX];
float as_lowx[TAS_ASMAX];       // a board stretch's `low` weight in 0.25s, doubled by each backtrack its handover caused (0: as_low)
float as_leadmin[TAS_ASMAX];    // a board stretch's least lead, raised by each try that overshot its point (Lex: ramp 9 to 10)
float as_rfs[TAS_ASMAX];        // farsh's energy at each stretch's board (as_rf when it was reached)
float as_wt[TAS_ASMAX];         // the demo's time there
float as_wo[TAS_ASMAX * 3];     // its origin
float as_wn[TAS_ASMAX * 3];     // the face to board ('0 0 1' a hop: a jump there; '0 0 0' any contact)
float as_wk[TAS_ASMAX];         // 1 board, 2 hop, 3 finish, 4 a flight's peak (`apex`)
float as_wr[TAS_ASMAX];         // a peak's radius
float as_wl[TAS_ASMAX];         // a board's ride: the demo time of its last sample off free fall (0: none known)
float as_ws[TAS_ASMAX];         // the head tick its stretch started at
float as_wp[TAS_ASMAX];         // the demo time its stretch started from
// A stretch's start state (origin, velocity) this attempt, and the one it last failed all its tries from with no bar,
// with that search's low weight (as_fsl -1: none). From the same state a search replays the line the search memory kept
// there and fails the same way: tchain9 (10 Nov) failed stretch 12 three times from one 3034 u/s state.
float as_sso[TAS_ASMAX * 6], as_fso[TAS_ASMAX * 6], as_fsl[TAS_ASMAX];
float *as_rows;                 // the demo's samples: t x y z vx vy vz
float as_nrows;

// The menu's status (cl_tasoptui.qc): state (0 idle, 1 running, 2 finished, 3 stopped), stretch, of,
// try, backtracks, a line of text, then a reach's record (stretch or -1, its speed at farsh's board height and
// his: the tab's progress strip) -- set as_rk/as_rb/as_rf just before.
var float as_rk = -1;
float as_rb, as_rf;
void(entity e, float state, string note) SV_TASAutoNote =
{
	sprint(e, PRINT_HIGH, strcat("tas autosurf: ", note, "\n"));
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET); WriteByte(MSG_MULTICAST, TAS_EV_AUTOSURF);
	WriteByte(MSG_MULTICAST, state); WriteShort(MSG_MULTICAST, e.as_i); WriteShort(MSG_MULTICAST, as_n);
	WriteByte(MSG_MULTICAST, e.as_try); WriteByte(MSG_MULTICAST, e.as_backs); WriteString(MSG_MULTICAST, note);
	WriteShort(MSG_MULTICAST, as_rk); WriteShort(MSG_MULTICAST, bound(-30000, rint(as_rb), 30000)); WriteShort(MSG_MULTICAST, bound(0, rint(as_rf), 30000));
	msg_entity = e; multicast(e.origin, MULTICAST_ONE_R);
	as_rk = -1;
};

void(entity e, string why) SV_TASAutoStop =
{
	if (!e.as_on) return;
	e.as_on = 0; e.as_swph = 0;
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
string(float k) SV_TASAutoKind =
{
	if (k == 1) return "board";
	if (k == 2) return "hop";
	if (k == 4) return "peak";
	if (k == 5) return "air point";
	return "finish";
};

// a `plan` preview parses the chain's option words too; it puts the running chain's back after (review: redo after a
// preview ran with the defaults, 0 backtracks)
#define TAS_SPOTS 5
float as_swo[TAS_SPOTS * 3], as_swv[TAS_SPOTS], as_sws[TAS_SPOTS], as_swe[TAS_SPOTS];  // spots: place, on the face, score, energy
float as_swd[TAS_ASMAX];        // a swept board's kept spot + 1 (0: not swept)
float as_swp[TAS_ASMAX * 3];    // its place
float as_optsave[20];
void(entity e) SV_TASAutoOptSave =
{
	as_optsave[0] = e.as_tube; as_optsave[1] = e.as_look; as_optsave[2] = e.as_tries; as_optsave[3] = e.as_backmax;
	as_optsave[4] = e.as_hop; as_optsave[5] = e.as_finish; as_optsave[6] = e.as_pace; as_optsave[7] = e.as_emin;
	as_optsave[8] = e.as_join; as_optsave[9] = e.as_rideknots; as_optsave[10] = e.as_polish; as_optsave[11] = e.as_low;
	as_optsave[12] = e.as_apex; as_optsave[13] = e.as_air; as_optsave[14] = e.as_wide; as_optsave[15] = e.as_szone;
	as_optsave[16] = e.as_sg; as_optsave[17] = e.as_sy; as_optsave[18] = e.as_sside; as_optsave[19] = e.as_spots;
};
void(entity e) SV_TASAutoOptRestore =
{
	e.as_tube = as_optsave[0]; e.as_look = as_optsave[1]; e.as_tries = as_optsave[2]; e.as_backmax = as_optsave[3];
	e.as_hop = as_optsave[4]; e.as_finish = as_optsave[5]; e.as_pace = as_optsave[6]; e.as_emin = as_optsave[7];
	e.as_join = as_optsave[8]; e.as_rideknots = as_optsave[9]; e.as_polish = as_optsave[10]; e.as_low = as_optsave[11];
	e.as_apex = as_optsave[12]; e.as_air = as_optsave[13]; e.as_wide = as_optsave[14]; e.as_szone = as_optsave[15];
	e.as_sg = as_optsave[16]; e.as_sy = as_optsave[17]; e.as_sside = as_optsave[18]; e.as_spots = as_optsave[19];
};

void(entity e, float s) SV_TASAutoAir =
{
	local float k, j, jb, d, best, m, i;
	local vector p;
	for (k = 0; k < rt_n && as_n < TAS_ASMAX; k = k + 1)
	{
		if (rt_nn[k*3] || rt_nn[k*3+1] || rt_nn[k*3+2]) continue;
		p = [rt_o[k*3], rt_o[k*3+1], rt_o[k*3+2]];
		best = 1000000; jb = -1;
		for (j = s + 1; j < as_nrows; j = j + 1)
		{
			d = vlen(SV_TASAutoRowO(j) - p);
			if (d < best) { best = d; jb = j; }
		}
		if (jb < 0 || best > 1500)
		{
			sprint(e, PRINT_HIGH, sprintf("tas autosurf: air point %.0f is %.0f u from the demo's route ahead: not used\n", k + 1, best));
			continue;
		}
		for (m = 0; m < as_n && as_wt[m] <= as_rows[jb*7]; m = m + 1) ;
		for (i = as_n; i > m; i = i - 1)
		{
			as_wt[i] = as_wt[i - 1]; as_wk[i] = as_wk[i - 1]; as_wr[i] = as_wr[i - 1]; as_wl[i] = as_wl[i - 1];
			for (j = 0; j < 3; j = j + 1) { as_wo[i*3 + j] = as_wo[i*3 - 3 + j]; as_wn[i*3 + j] = as_wn[i*3 - 3 + j]; }
		}
		as_wt[m] = as_rows[jb*7]; as_wk[m] = 5; as_wr[m] = TAS_AIRR; as_wl[m] = 0;
		as_wo[m*3] = p_x; as_wo[m*3+1] = p_y; as_wo[m*3+2] = p_z; as_wn[m*3] = as_wn[m*3+1] = as_wn[m*3+2] = 0;
		as_n = as_n + 1;
	}
};

// The player's moves of the guide run's points (Jargon's editor, cl_jargon.qc): by the demo time of the point moved, applied
// to every plan of that demo -- a plan is remade at the start box's exit and by each `plan`, and the points moved stay
float jg_ovt[TAS_ASMAX], jg_ovo[TAS_ASMAX * 3];
float jg_ovn;
string jg_ovpath;               // the demo they were made on (another demo's plan clears them)
void() SV_TASAutoMoved =
{
	local float i, j;
	for (i = 0; i < as_n; i = i + 1)
		if (as_wk[i] == 1 || as_wk[i] == 2)
			for (j = 0; j < jg_ovn; j = j + 1)
				if (fabs(as_wt[i] - jg_ovt[j]) < 0.01)
				{
					as_wo[i*3] = jg_ovo[j*3]; as_wo[i*3+1] = jg_ovo[j*3+1]; as_wo[i*3+2] = jg_ovo[j*3+2];
				}
};

// from < 0: from the sample nearest the body; else from that sample (the preview's: the start box's exit)
float(entity e, float from) SV_TASAutoPlan =
{
	local float i, s, d, best, st, lastleave, gdt, j, pk;
	local vector n;
	best = 1000000; s = -1;
	if (from >= 0) { s = from; best = 0; }
	else
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
			// a ride of 0.3 s or more: entered falling, or rising onto a surf face (surf_null's ramp past the ceiling
			// after ramp 6 is entered rising; skipped, one stretch ran ramp 6 to ramp 7 -- 8 s, past a search's cap)
			n = '0 0 0';
			if (as_rows[i*7-7] - as_rows[st*7] >= 0.3 - 0.0001 && as_rows[st*7+6] >= -100 && st > s + 2) n = SV_TASAutoFace(e, st);
			if (as_rows[i*7-7] - as_rows[st*7] >= 0.3 - 0.0001 && (as_rows[st*7+6] < -100 || n != '0 0 0'))
			{
				pk = as_n;
				if (e.as_hop && !e.as_join)
					for (j = max(lastleave, s) + 1; j < st - 3; j = j + 1)
						if (as_rows[j*7-1] < -100 && as_rows[j*7+6] > -1 && fabs(as_rows[j*7+3] - as_rows[j*7-4]) < 40)
						if (as_rows[j*7+6] > 150 || as_rows[j*7+13] > 150 || as_rows[j*7+20] > 150)
							SV_TASAutoAdd(2, j, '0 0 1');
				if (e.as_apex && as_n == pk && st > s + 2 && lastleave > s && as_rows[st*7] - as_rows[lastleave*7] >= 1 - 0.0001)
					for (j = lastleave + 1; j < st; j = j + 1)
						if (as_rows[j*7-1] > 0 && as_rows[j*7+6] <= 0)
						{	// the peak: rising to falling, clear of the ride and the board
							if (as_rows[j*7] - as_rows[lastleave*7] >= 0.4 - 0.0001 && as_rows[st*7] - as_rows[j*7] >= 0.4 - 0.0001)
							{
								SV_TASAutoAdd(4, j, '0 0 0');
								as_wr[as_n - 1] = min(500, 0.5 * vlen(SV_TASAutoRowO(j) - SV_TASAutoRowO(lastleave)));
							}
							j = st;
						}
				if (st > s + 2)
				{
					j = as_n;
					SV_TASAutoAdd(1, st, SV_TASAutoFace(e, st));
					if (as_n > j) as_wl[j] = as_rows[i*7-7];
				}
				lastleave = i - 1;
			}
			st = -1;
		}
	}
	if (e.as_finish) SV_TASAutoAdd(3, as_nrows - 1, '0 0 0');
	if (e.as_air) SV_TASAutoAir(e, s);
	SV_TASAutoMoved();
	if (cvar("developer"))
		for (i = 0; i < as_n; i = i + 1)
			sprint(e, PRINT_HIGH, sprintf("tas autosurf: stretch %.0f: %s at demo t=%.3f %v, face %v\n", i + 1,
				SV_TASAutoKind(as_wk[i]), as_wt[i],
				[as_wo[i*3], as_wo[i*3+1], as_wo[i*3+2]], [as_wn[i*3], as_wn[i*3+1], as_wn[i*3+2]]));
	return s;
};

// A tick sooner at this stretch's board is worth what the speed for the rest of the demo's route would gain:
// PM_TICK * (its length left / its time left) / its time left, u/s a tick (surf_null: ~0.6 at board 1, ~1.7
// at board 6), times the `pace` option; "" when off. Passed as is into the energy score's units (one ~3-6 u/s),
// so it weighs ~3x the derivation: the runs that made surf_null's stretches used it so (review).
string(entity e, float i) SV_TASAutoPace =
{
	local float k, len, tl, x;
	if (e.as_pace <= 0) return "";
	len = 0;
	for (k = as_nrows - 1; k > 0 && as_rows[k*7] > as_wt[i]; k = k - 1)
		len = len + vlen(SV_TASAutoRowO(k) - SV_TASAutoRowO(k - 1));
	tl = max(3, as_rows[(as_nrows - 1) * 7] - as_wt[i]);
	x = bound(0.05, e.as_pace * PM_TICK * (len / tl) / tl * (e.as_polish ? 0.25 : 1), 20);
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

// The least energy this stretch's reach counts at: the demo's speed at its board times `emin` (0.95; 0.9 let the
// full run board ramps 2-3 at 94-96% and stick two stretches on), as
// energy from where the body stands now (the search's own reference); "" when off. A reach well under
// it left the next stretches tried without the speed to make them (Lex, 10 Nov).
string(entity e, float i) SV_TASAutoEmin =
{
	local float k, v2, x, f;
	f = e.as_emin;
	if (e.as_polish && e.as_try < e.as_tries - 1) f = max(f, 0.99);      // polish: the last try takes the usual minimum
	if (as_wk[i] == 5) f = min(f, TAS_AIRMIN);
	if (f <= 0 && as_need[i] <= 0) return "";
	for (k = 0; k < as_nrows - 1 && as_rows[k*7] < as_wt[i] - 0.0001; k = k + 1) ;
	v2 = as_rows[k*7+4] * as_rows[k*7+4] + as_rows[k*7+5] * as_rows[k*7+5] + as_rows[k*7+6] * as_rows[k*7+6];
	x = 2 * cvar("sv_gravity") * (as_rows[k*7+3] - e.origin_z) + max(max(0, f) * max(0, f) * v2, as_need[i] * as_need[i]);
	x = (x < 0) ? -sqrt(-x) : sqrt(x);
	return sprintf(" emin %.1f", x);
};

// tas route add <x y z> <nx ny nz> | set <k> <x y z> <nx ny nz> | del <k> | undo | clear | show -- the clicked route
// `tas autosurf route` surfs (set and del: the Optimizer tab's drag editor, cl_tasoptviz.qc).
void(entity e, float argc) SV_TASRouteCommand =
{
	local float i, ad;
	if (Lobby_Active()) { sprint(e, PRINT_HIGH, "tas route: a local practice tool; not on lobby servers\n"); return; }
	// every outcome below sends the count; only a taken add's note carries its point, which is what the tab draws
	// (a pending marker of its own was confirmed by unrelated counts: review 6)
	ad = 0;
	if (e.as_on && e.as_route) sprint(e, PRINT_HIGH, "tas route: autosurf is surfing it; stop it first\n");
	else if (argc == 9 && argv(2) == "add")
	{
		for (i = 3; i < 9; i = i + 1) if (!FS_TASNumber(argv(i)) || fabs(stof(argv(i))) > 65536) i = 100;
		if (i >= 100) sprint(e, PRINT_HIGH, "tas route add <x y z> <nx ny nz>\n");
		else if (rt_n >= TAS_ASMAX) sprint(e, PRINT_HIGH, sprintf("tas route: %.0f points at most\n", TAS_ASMAX));
		else
		{
			i = vlen([stof(argv(6)), stof(argv(7)), stof(argv(8))]);
			if (i > 0.01 && fabs(i - 1) > 0.02) sprint(e, PRINT_HIGH, "tas route add: the normal is a unit vector, or 0 0 0 for a point\n");
			else
			{
				rt_o[rt_n*3] = stof(argv(3)); rt_o[rt_n*3+1] = stof(argv(4)); rt_o[rt_n*3+2] = stof(argv(5));
				if (i <= 0.01) rt_nn[rt_n*3] = rt_nn[rt_n*3+1] = rt_nn[rt_n*3+2] = 0;    // near zero: a point (review 2)
				else { rt_nn[rt_n*3] = stof(argv(6)); rt_nn[rt_n*3+1] = stof(argv(7)); rt_nn[rt_n*3+2] = stof(argv(8)); }
				rt_n = rt_n + 1; ad = 1;
			}
		}
	}
	else if (argc == 10 && argv(2) == "set")
	{	// a point dragged: its place and the face it boards (the face is the editor's, kept from the click)
		ad = stof(argv(3));
		for (i = 3; i < 10; i = i + 1) if (!FS_TASNumber(argv(i)) || fabs(stof(argv(i))) > 65536) i = 100;
		if (i >= 100 || ad < 1 || ad > rt_n || ad != floor(ad)) { sprint(e, PRINT_HIGH, "tas route set <k> <x y z> <nx ny nz>\n"); return; }
		i = vlen([stof(argv(7)), stof(argv(8)), stof(argv(9))]);
		if (i > 0.01 && fabs(i - 1) > 0.02) { sprint(e, PRINT_HIGH, "tas route set: the normal is a unit vector, or 0 0 0 for a point\n"); return; }
		rt_o[ad*3-3] = stof(argv(4)); rt_o[ad*3-2] = stof(argv(5)); rt_o[ad*3-1] = stof(argv(6));
		if (i <= 0.01) rt_nn[ad*3-3] = rt_nn[ad*3-2] = rt_nn[ad*3-1] = 0;
		else { rt_nn[ad*3-3] = stof(argv(7)); rt_nn[ad*3-2] = stof(argv(8)); rt_nn[ad*3-1] = stof(argv(9)); }
		SV_TASAutoNote(e, e.as_on ? 1 : 0, strcat(sprintf("your route: %.0f points, set %.0f ", rt_n, ad),
			sprintf("%.1f %.1f %.1f %.4f %.4f %.4f", rt_o[ad*3-3], rt_o[ad*3-2], rt_o[ad*3-1], rt_nn[ad*3-3], rt_nn[ad*3-2], rt_nn[ad*3-1])));
		return;
	}
	else if (argc == 4 && argv(2) == "del")
	{
		ad = stof(argv(3));
		if (ad < 1 || ad > rt_n || ad != floor(ad)) { sprint(e, PRINT_HIGH, "tas route del <k>\n"); return; }
		for (i = ad * 3 - 3; i < rt_n * 3 - 3; i = i + 1) { rt_o[i] = rt_o[i + 3]; rt_nn[i] = rt_nn[i + 3]; }
		rt_n = rt_n - 1;
		SV_TASAutoNote(e, e.as_on ? 1 : 0, sprintf("your route: %.0f points, removed %.0f", rt_n, ad));
		return;
	}
	else if (argc == 3 && argv(2) == "here")
	{	// an air point where the body is (noclip there): autosurf's `air` aims a demo's stretch through it
		if (rt_n >= TAS_ASMAX) sprint(e, PRINT_HIGH, sprintf("tas route: %.0f points at most\n", TAS_ASMAX));
		else
		{
			rt_o[rt_n*3] = e.origin_x; rt_o[rt_n*3+1] = e.origin_y; rt_o[rt_n*3+2] = e.origin_z;
			rt_nn[rt_n*3] = rt_nn[rt_n*3+1] = rt_nn[rt_n*3+2] = 0;
			rt_n = rt_n + 1; ad = 1;
		}
	}
	else if (argc == 3 && argv(2) == "undo") { if (rt_n > 0) rt_n = rt_n - 1; }
	else if (argc == 3 && argv(2) == "clear") rt_n = 0;
	else if (argc == 3 && argv(2) == "show")
		for (i = 0; i < rt_n; i = i + 1)
			sprint(e, PRINT_HIGH, sprintf("tas route %.0f: %v, %v\n", i + 1, [rt_o[i*3], rt_o[i*3+1], rt_o[i*3+2]], [rt_nn[i*3], rt_nn[i*3+1], rt_nn[i*3+2]]));
	else { sprint(e, PRINT_HIGH, "tas route add <x y z> <nx ny nz> | here | set <k> <x y z> <nx ny nz> | del <k> | undo | clear | show\n"); return; }
	if (ad)
		SV_TASAutoNote(e, e.as_on ? 1 : 0, strcat(sprintf("your route: %.0f points, added ", rt_n),
			sprintf("%.1f %.1f %.1f %.4f %.4f %.4f", rt_o[rt_n*3-3], rt_o[rt_n*3-2], rt_o[rt_n*3-1], rt_nn[rt_n*3-3], rt_nn[rt_n*3-2], rt_nn[rt_n*3-1])));
	else SV_TASAutoNote(e, e.as_on ? 1 : 0, sprintf("your route: %.0f points", rt_n));
};

// One stretch: the demo's rows from where it left off, the target, the search.
// Lex, 10 Nov: a board stays on the guide's spot (its aim moves +-30 u); try places around it on the ramp, and judge each
// by the stretch after it -- the energy a board keeps or loses shows on the next ramp. Spots: the guide's, 160 u back
// along the ramp's edge, 160 u on, 96 u up the face, the top-back corner; each kept at the guide's height off the face.
string(float k) SV_TASAutoSpotName =
{
	if (k == 1) return "further back"; if (k == 2) return "further along"; if (k == 3) return "higher";
	if (k == 4) return "higher and back"; return "the guide's";
};
void(entity e, float i) SV_TASAutoSpots =
{
	local vector o, n, v, ed, up, p;
	local float k, r, d0, f;
	o = [as_wo[i*3], as_wo[i*3+1], as_wo[i*3+2]]; n = [as_wn[i*3], as_wn[i*3+1], as_wn[i*3+2]];
	if (n_z < 0) n = -n;
	for (r = 0; r < as_nrows - 1 && as_rows[r*7] < as_wt[i] - 0.0001; r = r + 1) ;
	v = [as_rows[r*7+4], as_rows[r*7+5], as_rows[r*7+6]];
	ed = normalize([n_y, -n_x, 0]);         // the edge: n x up
	if (ed * v < 0) ed = -ed;               // the way the guide went
	up = normalize('0 0 1' - n_z * n);
	traceline(o, o - n * 128, MOVE_NOMONSTERS, e);
	d0 = (trace_fraction < 1 && !trace_startsolid) ? 128 * trace_fraction : -1;
	for (k = 0; k < TAS_SPOTS; k = k + 1)
	{
		as_sws[k] = -1000000; as_swe[k] = 0; as_swv[k] = (k == 0); p = o;
		for (f = 1; f >= 0.5 && k > 0 && !as_swv[k]; f = f - 0.5)
		{	// on the same face, or half as far; else not tried
			p = o + f * (((k == 1 || k == 4) ? -160 : ((k == 2) ? 160 : 0)) * ed + ((k >= 3) ? 96 : 0) * up);
			traceline(p + n * 64, p - n * 192, MOVE_NOMONSTERS, e);
			if (d0 >= 0 && trace_fraction < 1 && !trace_startsolid && fabs(trace_plane_normal * n) >= 0.95)
				{ p = trace_endpos + n * d0; as_swv[k] = 1; }
		}
		as_swo[k*3] = p_x; as_swo[k*3+1] = p_y; as_swo[k*3+2] = p_z;
	}
};
// the speed at the guide's board height for stretch i (as the reached note gives it)
float(entity e, float i) SV_TASAutoEnergyAt =
{
	local float r, d;
	for (r = 0; r < as_nrows - 1 && as_rows[r*7] < as_wt[i] - 0.0001; r = r + 1) ;
	d = e.velocity * e.velocity + 2 * cvar("sv_gravity") * (e.origin_z - as_rows[r*7+3]);
	return (d < 0) ? -sqrt(-d) : sqrt(d);
};
// the next spot, or the best one kept; either way back to the swept stretch's start
void(entity e) SV_TASAutoSpotNext =
{
	local float k, b, i;
	i = e.as_swi;
	for (k = e.as_swk + 1; k < TAS_SPOTS; k = k + 1) if (as_swv[k]) break;     // not k < N && as_swv[k]: no short-circuit
	if (k < TAS_SPOTS) { e.as_swk = k; e.as_swph = 1; }
	else
	{
		b = 0;
		for (k = 1; k < TAS_SPOTS; k = k + 1) if (as_swv[k] && as_sws[k] > as_sws[b]) b = k;
		as_swd[i] = b + 1; as_swp[i*3] = as_swo[b*3]; as_swp[i*3+1] = as_swo[b*3+1]; as_swp[i*3+2] = as_swo[b*3+2];
		e.as_swph = 0;
		if (as_sws[b] >= 100000)
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f: boarding %s kept, the next ramp at %.0f u/s (the guide's spot: %s)", i + 1,
				(b == 0) ? "on the guide's spot" : SV_TASAutoSpotName(b), as_sws[b] - 100000,
				(as_sws[0] >= 100000) ? sprintf("%.0f", as_sws[0] - 100000) : "missed it"));
		else SV_TASAutoNote(e, 1, sprintf("stretch %.0f: no spot made the next ramp; boarding %s kept", i + 1,
			(b == 0) ? "on the guide's spot" : SV_TASAutoSpotName(b)));
	}
	e.as_i = i; e.as_try = 0; e.as_tprev = as_wp[i]; e.as_goal = as_ws[i]; e.as_stage = 3;
};
// a search ended inside a sweep: TRUE when the sweep took the outcome (the chain's own handling skipped)
float(entity e) SV_TASAutoSweep =
{
	local float k;
	k = e.as_swk;
	if (e.as_swph == 1 && e.as_i == e.as_swi)
	{
		if (e.topt_outcome == 2) { as_swe[k] = SV_TASAutoEnergyAt(e, e.as_i); as_sws[k] = as_swe[k]; e.as_swph = 2; return FALSE; }
		SV_TASAutoNote(e, 1, sprintf("stretch %.0f, boarding %s: missed the ramp", e.as_i + 1, SV_TASAutoSpotName(k)));
		SV_TASAutoSpotNext(e);
		return TRUE;
	}
	if (e.as_swph == 2 && e.as_i == e.as_swi + 1)
	{
		if (e.topt_outcome == 2)
		{
			as_sws[k] = 100000 + SV_TASAutoEnergyAt(e, e.as_i);
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f, boarding %s: %.0f u/s there, the next ramp at %.0f", e.as_swi + 1,
				SV_TASAutoSpotName(k), as_swe[k], as_sws[k] - 100000));
		}
		else SV_TASAutoNote(e, 1, sprintf("stretch %.0f, boarding %s: %.0f u/s there, then missed the next ramp", e.as_swi + 1,
			SV_TASAutoSpotName(k), as_swe[k]));
		SV_TASAutoSpotNext(e);
		return TRUE;
	}
	e.as_swph = 0;      // a backtrack left the sweep: the chain goes on without it
	return FALSE;
};
// a stretch whose point the player moved keeps the player's spot
float(float i) SV_TASAutoIsMoved =
{
	local float j;
	for (j = 0; j < jg_ovn; j = j + 1) if (fabs(as_wt[i] - jg_ovt[j]) < 0.01) return TRUE;
	return FALSE;
};

void(entity e) SV_TASAutoLink =
{
	local float i, h, argc, r;
	local vector o, n;
	local string ps, ls, cl;
	i = e.as_i;
	if (e.as_redo == i + 1)
	{	// the rewound state must be the one this stretch started from: a restarted run reuses the tick numbers (review)
		e.as_redo = 0;
		if (vlen(e.origin - [as_sso[i*6], as_sso[i*6+1], as_sso[i*6+2]]) > 1)
			{ SV_TASAutoStop(e, "this is not the run that reached that stretch: restart from the start zone"); return; }
	}
	as_ws[i] = SV_TimerTicks(e); as_wp[i] = e.as_tprev;
	as_sso[i*6] = e.origin_x; as_sso[i*6+1] = e.origin_y; as_sso[i*6+2] = e.origin_z;
	as_sso[i*6+3] = e.velocity_x; as_sso[i*6+4] = e.velocity_y; as_sso[i*6+5] = e.velocity_z;
	if (!e.as_route && e.as_try == 0 && as_need[i] <= 0 && as_fsl[i] == as_lowx[i])
	if (e.origin == [as_fso[i*6], as_fso[i*6+1], as_fso[i*6+2]] && e.velocity == [as_fso[i*6+3], as_fso[i*6+4], as_fso[i*6+5]])
	{	// counted as failed again without a search: the failure handler goes on to the next backtrack
		SV_TASAutoNote(e, 1, sprintf("stretch %.0f starts in the state it failed from before: counted as failed again", i + 1));
		e.topt_outcome = 1; e.topt_lowneed = e.topt_earlycut = 0; e.as_try = e.as_tries - 1; e.as_stage = 2;
		return;
	}
	o = [as_wo[i*3], as_wo[i*3+1], as_wo[i*3+2]]; n = [as_wn[i*3], as_wn[i*3+1], as_wn[i*3+2]];
	if (e.as_spots && !e.as_route && !e.as_swph && !as_swd[i] && as_wk[i] == 1 && i + 1 < as_n && (n_x || n_y) && !SV_TASAutoIsMoved(i))
	{
		SV_TASAutoSpots(e, i);
		r = 0;
		for (h = 0; h < TAS_SPOTS; h = h + 1) r = r + as_swv[h];
		if (r > 1)
		{
			e.as_swi = i; e.as_swk = 0; e.as_swph = 1;
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f: trying %.0f boarding spots, each judged on the ramp after it", i + 1, r));
		}
		else as_swd[i] = 1;     // only the guide's spot is on the face
	}
	if (e.as_swph == 1 && e.as_swi == i) o = [as_swo[e.as_swk*3], as_swo[e.as_swk*3+1], as_swo[e.as_swk*3+2]];
	else if (as_swd[i] > 1) o = [as_swp[i*3], as_swp[i*3+1], as_swp[i*3+2]];
	if (e.as_route)
	{	// a clicked point: the horizon from its distance at this speed (1.5x and 40 ticks over), a radius for a click
		h = bound(64, rint(1.5 * vlen(o - e.origin) / max(500, vlen(e.velocity)) / PM_TICK) + 40, TOPT_HMAX);
		r = (as_wk[i] == 2) ? 90 : ((as_wk[i] == 3) ? 200 : 300);
	}
	else
	{
	h = max(16, rint(1.25 * (as_wt[i] - e.as_tprev) / PM_TICK) + 10 + e.as_look);
	if (h > TOPT_HMAX && cvar("developer"))      // the lookahead goes first, then the reach (a joined stretch is long: review 11)
		sprint(e, PRINT_HIGH, sprintf("tas autosurf: this stretch wants %.0f ticks; searched over %.0f\n", h, TOPT_HMAX));
	h = min(TOPT_HMAX, h);
	argc = tokenize(sprintf("tas demorows %s %.4f", e.as_file, e.as_tprev + PM_TICK));    // a row's input produced it
	e.topt_dn = 0;
	SV_TASDemoRowsCommand(e, argc);
	if (e.topt_dn < 16) { SV_TASAutoStop(e, "the demo's rows for this stretch did not load"); return; }   // not the last stretch's (review)
	h = min(h, e.topt_dn);
	r = (as_wk[i] == 2) ? 50 : ((as_wk[i] == 3) ? 400 : ((as_wk[i] == 4 || as_wk[i] == 5) ? as_wr[i] : 800));
	}
	if (n == '0 0 0') argc = tokenize(sprintf("tas target %.1f %.1f %.1f %.0f", o_x, o_y, o_z, r));
	else argc = tokenize(sprintf("tas target %.1f %.1f %.1f %.0f %.4f %.4f %.4f", o_x, o_y, o_z, r, n_x, n_y, n_z));
	e.topt_tgton = 0;
	SV_TASTargetCommand(e, argc);
	if (!e.topt_tgton) { SV_TASAutoStop(e, "this stretch's target was refused"); return; }
	if (e.as_route)
		cl = sprintf("tas optimize %.0f left curve 12 aim%s gens %.0f%s energy fast", h, (e.as_hop && as_wk[i] == 2) ? " hop" : "",
			e.as_polish ? 90 : min(90, 30 * (1 + e.as_try)), (e.as_polish && e.as_try < e.as_tries - 1) ? " stall 20" : "");
	else
	{
	ps = strcat(SV_TASAutoPace(e, i), SV_TASAutoEmin(e, i));
	ls = (e.as_look > 0) ? sprintf(" look %.0f", e.as_look) : "";
	// a retry searches longer: 30 generations more a try (the pillar stretch's narrow line came in some searches only)
	ps = strcat(ps, sprintf(" gens %.0f", e.as_polish ? 90 : min(90, 30 * (1 + e.as_try))));
	if (e.as_polish && e.as_try < e.as_tries - 1) ps = strcat(ps, " stall 20");
	// `low` 0.5 (as_lowx 2): at 0.25 tchain10 boarded ramp 10 557 u under farsh's point; its 0.5 retry boarded 8 u off and faster
	if ((e.as_low || as_lowx[i]) && as_wk[i] == 1) ps = strcat(ps, sprintf(" low %g", 0.25 * max(e.as_low ? 2 : 0, as_lowx[i])));
	if (as_wk[i] == 1 && as_wl[i] > as_wt[i]) ps = strcat(ps, sprintf(" ride %.0f", rint((as_wl[i] - as_wt[i]) / PM_TICK)));
	if (e.as_rideknots && i > 0)
	if (as_wk[i - 1] == 1 && as_wl[i - 1] > e.as_tprev)
		ps = strcat(ps, sprintf(" kex %.0f", min(TOPT_HMAX, rint((as_wl[i - 1] - e.as_tprev) / PM_TICK) + 15)));   // past the cap: refused (review 13)
	if (e.as_wide) ps = strcat(ps, " wide");
	if (as_leadmin[i] > 0 && as_wk[i] == 1) ps = strcat(ps, sprintf(" leadmin %g", as_leadmin[i]));
	cl = sprintf("tas optimize %.0f left curve 12 demo aim late tube %.0f%s%s%s energy fast", h, e.as_tube, e.as_hop ? " hop" : "", ls, ps);
	}
	if (cvar("developer")) sprint(e, PRINT_HIGH, strcat("tas autosurf: ", cl, "\n"));
	argc = tokenize(cl);
	SV_TASOptCommand(e, argc);
	if (!e.topt_on) e.topt_outcome = -1;        // refused: a failed try
	if (e.topt_on && !e.as_route)
	{	// the search panel's reference: the demo's speed and height at this board (the progress strip's measure)
		for (r = 0; r < as_nrows - 1 && as_rows[r*7] < as_wt[i] - 0.0001; r = r + 1) ;
		e.topt_refspeed = vlen([as_rows[r*7+4], as_rows[r*7+5], as_rows[r*7+6]]); e.topt_refz = as_rows[r*7+3];
	}
	e.as_stage = 2;
	if (e.as_route) SV_TASAutoNote(e, 1, sprintf("point %.0f of %.0f (%s), try %.0f", i + 1, as_n,
		(as_wk[i] == 1) ? "ramp" : ((as_wk[i] == 2) ? "bhop" : "point"), e.as_try + 1));
	else SV_TASAutoNote(e, 1, sprintf("stretch %.0f of %.0f (%s at demo t=%.2f), try %.0f%s", i + 1, as_n,
		SV_TASAutoKind(as_wk[i]), as_wt[i], e.as_try + 1,
		(as_need[i] > 0) ? sprintf(", needs %.0f u/s", as_need[i]) : ""));
};

// A chain's start. backs unset: twice the stretches, at least 6 (the full surf_null run spent 10 on its first five of 17)
void(entity e) SV_TASAutoBacks =
{
	local float k;
	if (e.as_backmax < 0) e.as_backmax = max(6, 2 * as_n);
	for (k = 0; k < TAS_ASMAX; k = k + 1) { as_rbs[k] = as_need[k] = as_lowx[k] = as_rfs[k] = as_ws[k] = as_leadmin[k] = as_swd[k] = 0; as_fsl[k] = -1; }
	e.as_failmax = -1; e.as_swph = 0;
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
	if (e.as_on && e.as_stage == 20 && (!e.run_tas_mode || (e.run_t_state != TS_ARMED && e.run_t_state != TS_RUNNING)))
	{	// review: armed through `tas off` it would later pause a live run into TAS
		SV_TASAutoStop(e, "TAS off, or out of the start box, while armed");
		return;
	}
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
			if (!(e.flags & FL_ONGROUND))
			{	// the spawn's drop; bounded (review: a refused step or a box with no floor repeated forever)
				e.as_sdrop = e.as_sdrop + 2;
				if (e.as_sdrop > 300) { SV_TASAutoStop(e, "the start never landed in the box (300 ticks)"); return; }
				SV_TASAutoGuide(e, 0, 0, e.v_angle_y, 0, 2);
				return;
			}
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
				d = (fabs(ee) > 150) ? e.as_sair : ((ee > 4) ? -1 : ((ee < -4) ? 1 : e.as_sair));
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
				    fabs(-((cr_x + 116 * nn_x - e.as_ex_x) * e.as_exd_x + (cr_y + 116 * nn_y - e.as_ex_y) * e.as_exd_y) - 455) <= 195)
					{ d = 1; ph = 2; }
				else if (fabs(herr) < 100 && fabs((cl_x - e.as_ex_x) * nn_x + (cl_y - e.as_ex_y) * nn_y - 116) < 15 &&
				    fabs(-((cl_x - 116 * nn_x - e.as_ex_x) * e.as_exd_x + (cl_y - 116 * nn_y - e.as_ex_y) * e.as_exd_y) - 455) <= 195)
					{ d = -1; ph = 2; }	// a tangent point 260-600 u short: deeper, the turn met the back wall (tstart8: 213 u/s)
				else if (fabs(herr) > 100) d = e.as_sair;                  // facing away: come round
				else
				{	// pursue a point 250 u ahead on the line
					ee = vectoyaw(e.as_ex - e.as_exd * (along - 250) - e.origin) - i; ee = ee - 360 * floor((ee + 180) / 360);
					d = (ee > 4) ? -1 : ((ee < -4) ? 1 : e.as_sair);	// a side change past 4 deg only: each one cost speed
																		// in the game (pursuit fell to 242 u/s, tstart9)
				}
			}
			e.as_sph = ph;
			SV_TASAutoStep(e, 400, d, 0, 3, vectoyaw(e.as_exd) - 90);      // from rest: across the line (startsim4: 240-330 deg)
			e.as_sn = e.as_sn + 3;
		}
		else if (e.run_t_state == TS_RUNNING && e.as_sn2 < 30 && (e.as_sn2 < 4 || SV_TASAutoTouching(e) || vlen(e.origin - e.as_runo) < 48))
		{	// out of the box: on until clear of its volumes and 48 u past where the run started (at least 4 ticks, at most
			// 30) -- the zones are positions, not volumes, and a body paused over the box's edge was put back in the
			// start, cancelling the run mid-search (rig tstart10)
			if (!e.as_sn2) e.as_runo = e.origin;
			SV_TASAutoSteer(e, (e.flags & FL_ONGROUND) ? 400 : 0, 0, 2, 3, 0, vectoyaw(e.as_exd)); e.as_sn2 = e.as_sn2 + 2;
		}
		else if (e.run_t_state == TS_RUNNING)
		{
			s = SV_TASAutoPlan(e, -1);
			if (s < 0 || as_n < 1) { SV_TASAutoStop(e, "out of the start box off the demo's route (not within 400 u)"); return; }
			e.as_stage = 1; e.as_i = 0; e.as_try = 0; e.as_backs = 0; e.as_tprev = as_rows[s*7]; e.as_failat = -1;
			SV_TASAutoBacks(e);
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
		if (e.as_swph && SV_TASAutoSweep(e)) return;
		if (e.topt_outcome == 2)
		{	// reached: the next stretch's demo rows start where the demo came nearest this state
			best = 1000000; t = e.as_tprev;
			for (i = 0; i < as_nrows; i = i + 1)
				if (fabs(as_rows[i*7] - as_wt[e.as_i]) <= 2)
				{
					d = vlen(SV_TASAutoRowO(i) - e.origin);
					if (d < best) { best = d; t = as_rows[i*7]; }
				}
			if (e.as_route)
			{
				as_rk = e.as_i; as_rb = vlen(e.velocity); as_rf = 0;
				SV_TASAutoNote(e, 1, sprintf("point %.0f reached at %.0f u/s", e.as_i + 1, as_rb));
			}
			else
			{
			for (i = 0; i < as_nrows - 1 && as_rows[i*7] < as_wt[e.as_i] - 0.0001; i = i + 1) ;
			// speed at farsh's board height (the energy carried there) against his own: vE near 0 magnified the gap
			d = e.velocity * e.velocity + 2 * cvar("sv_gravity") * (e.origin_z - as_rows[i*7+3]);
			as_rk = e.as_i; as_rb = (d < 0) ? -sqrt(-d) : sqrt(d); as_rf = vlen([as_rows[i*7+4], as_rows[i*7+5], as_rows[i*7+6]]);
			as_rbs[e.as_i] = as_rb; as_rfs[e.as_i] = as_rf;
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f reached: %.0f u/s at the guide's board height, the guide %.0f", e.as_i + 1, as_rb, as_rf));
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
		if (as_wk[e.as_i] == 1 && e.topt_over > 100 && as_leadmin[e.as_i] < 0.8)
		{	// it flew past the ramp's point: the next try comes in wider, along the face (a lead of at least 0.5, 0.7, 0.8)
			as_leadmin[e.as_i] = min(0.8, max(0.5, as_leadmin[e.as_i] + 0.2));
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f overshot its ramp by %.0f u: the next try comes in wider (lead %g or more)",
				e.as_i + 1, e.topt_over, as_leadmin[e.as_i]));
		}
		e.as_try = e.as_try + 1;
		e.as_backhead = -1; e.as_backfail = 0;
		if (e.as_try < e.as_tries) { e.as_goal = as_ws[e.as_i]; e.as_stage = 3; return; }
		e.as_failmax = max(e.as_failmax, e.as_i);
		if (!e.as_route && as_need[e.as_i] <= 0)
		{
			as_fsl[e.as_i] = as_lowx[e.as_i];
			for (i = 0; i < 6; i = i + 1) as_fso[e.as_i*6 + i] = as_sso[e.as_i*6 + i];
		}
		if (as_need[e.as_i] > 0 && e.as_backs < e.as_backmax)
		{	// it could not beat its last reach: again without the bar (the next stretch may need another line at the
			// same speed), a backtrack's worth -- barred stretches cascaded to the first and stopped (review 8)
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f could not beat %.0f u/s: again without the bar (backtrack %.0f)",
				e.as_i + 1, as_need[e.as_i], e.as_backs + 1));
			as_need[e.as_i] = 0; e.as_backs = e.as_backs + 1; e.as_try = 0;
			e.as_goal = as_ws[e.as_i]; e.as_stage = 3;
			return;
		}
		if (e.as_backs < e.as_backmax && e.as_i > 0 && e.topt_lowneed > 1 && !e.as_route)
		{	// a hop's flight came in under its platform: the board feeding the hops again, needing the energy that flight
			// lacked (Lex: min-max a ramp until the energy is high enough; surf_null's second platform 29-41 u under)
			d = e.as_i;
			for (t = e.as_i - 1; t > 0 && as_wk[t] != 1; t = t - 1) ;
			if (as_wk[t] == 1 && as_rbs[t] > 0)
			{
				e.as_backs = e.as_backs + 1; e.as_i = t; e.as_try = 0;
				for (i = t + 1; i < as_n; i = i + 1) as_need[i] = 0;
				as_need[t] = max(as_need[t], as_rbs[t] * min(1.08, e.topt_lowneed));
				e.as_tprev = as_wp[t]; e.as_goal = as_ws[t]; e.as_stage = 3;
				SV_TASAutoNote(e, 1, sprintf("stretch %.0f came in under its platform: backtrack %.0f to stretch %.0f, needing %.0f u/s (it had %.0f)",
					d + 1, e.as_backs, t + 1, as_need[t], as_rbs[t]));
				return;
			}
		}
		if (e.as_backs < e.as_backmax && e.as_i > 0 && e.topt_earlycut && !e.as_route)
		if (as_wk[e.as_i - 1] == 1 && as_lowx[e.as_i - 1] < 8)     // nested: && reads both sides, as_wk[-1] on stretch 1 (review)
		{	// it left farsh's path within 40 ticks (TOPT_EARLYCUT): the board before handed over the wrong place, so that board again
			// nearer farsh's point and with no speed bar -- the bar made a retry board lower still (surf_null ramp 9 for 10,
			// 280-333 u under; Lex: the top keeps the height that flight needs)
			e.as_backs = e.as_backs + 1; e.as_i = e.as_i - 1; e.as_try = 0;
			as_lowx[e.as_i] = as_lowx[e.as_i] ? as_lowx[e.as_i] * 2 : (e.as_low ? 4 : 2);
			for (i = e.as_i; i < as_n; i = i + 1) as_need[i] = 0;
			e.as_tprev = as_wp[e.as_i]; e.as_goal = as_ws[e.as_i]; e.as_stage = 3;
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f left the guide's path %.0f ticks in, from where the board before put it: backtrack %.0f to stretch %.0f, boarding nearer the guide's point (low %g)",
				e.as_i + 2, e.topt_earlycut, e.as_backs, e.as_i + 1, 0.25 * as_lowx[e.as_i]));
			return;
		}
		if (e.as_backs < e.as_backmax && e.as_i > 0)
		{	// back one stretch, then further each second time the same stretch fails again: one back at a time spent
			// 8 backtracks re-doing the stretch before, when the deficit came two or three earlier (full run, 10 Nov)
			if (e.as_failat == e.as_i) e.as_failn = e.as_failn + 1; else { e.as_failat = e.as_i; e.as_failn = 1; }
			e.as_backs = e.as_backs + 1; e.as_i = max(0, e.as_i - 1 - floor((e.as_failn - 1) / 2)); e.as_try = 0;
			for (i = e.as_i + 1; i < as_n; i = i + 1) as_need[i] = 0;       // reached from a new state: no bar of their own
			if (!e.as_route && as_rbs[e.as_i] > 0) as_need[e.as_i] = max(as_need[e.as_i], as_rbs[e.as_i] * 1.0025);
			// under farsh there: toward 99.5% of his energy, 2% at a time -- a retry from one state replays one line, so
			// 0.25% more was never found and the bar was dropped each time (surf_null: 97.9% at the board before the
			// platforms failed the last ramp three times; from farsh's own state the last three stretches took 20 s)
			if (!e.as_route && as_rfs[e.as_i] * 0.995 > as_rbs[e.as_i] && as_rbs[e.as_i] > 0)
				as_need[e.as_i] = max(as_need[e.as_i], min(as_rfs[e.as_i] * 0.995, as_rbs[e.as_i] * 1.02));
			e.as_tprev = as_wp[e.as_i]; e.as_goal = as_ws[e.as_i]; e.as_stage = 3;
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f failed its tries: backtrack %.0f to stretch %.0f", e.as_failat + 1, e.as_backs, e.as_i + 1));
			return;
		}
		if (e.as_failmax > e.as_i)     // the furthest stretch that failed, not only the one the backtracks ended on (review 8-9)
			SV_TASAutoStop(e, sprintf("stuck at stretch %.0f of %.0f after %.0f backtracks (stretch %.0f failed last)",
				e.as_failmax + 1, as_n, e.as_backs, e.as_i + 1));
		else SV_TASAutoStop(e, sprintf("stuck at stretch %.0f of %.0f after %.0f backtracks", e.as_i + 1, as_n, e.as_backs));
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
	local float i, s, n, st, flip, arm, pl;
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
	if ((argc == 7 && argv(2) == "move") || (argc == 3 && argv(2) == "reset") || (argc == 4 && argv(2) == "redo"))
	if (Lobby_Active()) { sprint(e, PRINT_HIGH, "tas autosurf: a local practice tool; not on lobby servers\n"); return; }
	if (argc == 7 && argv(2) == "move")
	{	// a guide run's point moved in the editor: its demo time, where it is now
		for (i = 3; i < 7; i = i + 1) if (!FS_TASNumber(argv(i)) || fabs(stof(argv(i))) > 65536) i = 100;
		if (i >= 100) { sprint(e, PRINT_HIGH, "tas autosurf move <demo time> <x y z>\n"); return; }
		for (n = 0; n < jg_ovn; n = n + 1) if (fabs(jg_ovt[n] - stof(argv(3))) < 0.01) break;     // && reads jg_ovt[64] (review)
		if (n >= TAS_ASMAX) { sprint(e, PRINT_HIGH, "tas autosurf: too many moved points\n"); return; }
		jg_ovt[n] = stof(argv(3)); jg_ovo[n*3] = stof(argv(4)); jg_ovo[n*3+1] = stof(argv(5)); jg_ovo[n*3+2] = stof(argv(6));
		if (n == jg_ovn) jg_ovn = jg_ovn + 1;
		return;
	}
	if (argc == 3 && argv(2) == "reset") { jg_ovn = 0; SV_TASAutoNote(e, 0, "route: back to the guide run's points"); return; }
	if (argc == 4 && argv(2) == "redo")
	{	// Lex, 10 Nov: pick a stretch under the panel's strip and run again from it -- the TAS head rewound to that
		// stretch's start (as a backtrack is), the plan remade from the chain's own start with the moves since applied
		n = stof(argv(3)) - 1;
		if (e.as_on || e.topt_on || e.tdem_on) { SV_TASAutoNote(e, 0, "stop it first, then redo"); return; }
		if (SV_TASOptBusy(e)) return;
		if (e.as_route || e.as_file == "" || n < 0 || n >= TAS_ASMAX || n != floor(n))
			{ SV_TASAutoNote(e, 0, "nothing to redo there: surf a run first"); return; }
		if (as_ws[n] <= 0)      // nested: || reads every operand, as_ws[-1] on `redo 0` (review)
			{ SV_TASAutoNote(e, 0, sprintf("stretch %.0f was not reached in this run: surf it first", n + 1)); return; }
		if (SV_TimerTicks(e) < as_ws[n]) { SV_TASAutoNote(e, 0, "the run is not that far any more: restart it"); return; }
		if (!SV_TASToolGate(e, "autosurf")) { SV_TASAutoNote(e, 0, "TAS is not paused in a run here: restart from the start zone"); return; }
		as_nrows = SV_TASAutoRead(e.as_file);
		if (as_nrows < 2) { SV_TASAutoNote(e, 0, "the guide run's file cannot be read"); return; }
		for (s = 0; s < as_nrows - 1 && as_rows[s*7] < as_wp[0] - 0.0001; s = s + 1) ;
		SV_TASAutoPlan(e, s);
		if (n >= as_n) { SV_TASAutoNote(e, 0, "the route changed: restart from the start zone"); return; }
		for (i = n; i < as_n; i = i + 1)
		{	// from here on a new attempt: no bars, no "failed from this state", no later stretch's start tick
			as_need[i] = 0; as_fsl[i] = -1; as_swd[i] = 0;
			if (i > n) as_ws[i] = 0;
		}
		if (e.as_backmax < 0) e.as_backmax = max(6, 2 * as_n);
		e.as_redo = n + 1; e.as_swph = 0;
		e.as_on = 1; e.as_i = n; e.as_try = 0; e.as_backs = 0; e.as_failat = -1; e.as_failmax = n;
		e.as_tprev = as_wp[n]; e.as_goal = as_ws[n]; e.as_stage = 3;
		SV_TASAutoNote(e, 1, sprintf("redo from stretch %.0f", n + 1));
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
		sprint(e, PRINT_HIGH, "tas autosurf <demo.rec> [tube R] [look N] [tries N] [backs N] [pace X] [emin F] [nohop] [join] [rideknots] [polish] [low] [finish] [start [zone N] [sg N] | onjump | onexit] | stop | status | startpause\n");
		return;
	}
	if (e.as_on || e.topt_on || e.tdem_on) { SV_TASAutoNote(e, e.as_on ? 1 : 0, "already running: stop it first"); return; }
	if (path != "route" && !SV_TASDemoPathOK(path)) { sprint(e, PRINT_HIGH, "tas autosurf: a .rec under data/ or cfg/ksfreplays/ (or route)\n"); return; }
	if (SV_TASOptBusy(e)) return;
	SV_TASAutoOptSave(e);
	st = 0; flip = 0; arm = 0; pl = 0; e.as_szone = 0; e.as_sg = 900; e.as_sy = 0; e.as_sside = -1;
	e.as_tube = 300; e.as_look = 100; e.as_tries = 2; e.as_backmax = -1; e.as_hop = 1; e.as_finish = 0; e.as_pace = 1; e.as_emin = 0.95; e.as_join = 0; e.as_rideknots = 0; e.as_polish = 0; e.as_low = 0; e.as_apex = 0; e.as_air = 0; e.as_wide = 0; e.as_spots = 0;
	for (i = 3; i < argc; i = i + 1)
	{
		w = argv(i); n = FS_TASNumber(argv(i + 1)) ? stof(argv(i + 1)) : -1;    // not a number: refused below, not 0 (review)
		if (w == "tube" && n >= 50 && n <= 2000) { e.as_tube = n; i = i + 1; }
		else if (w == "look" && n >= 0 && n <= 400) { e.as_look = rint(n); i = i + 1; }
		else if (w == "tries" && n >= 1 && n <= 10) { e.as_tries = rint(n); i = i + 1; }
		else if (w == "backs" && n >= 0 && n <= 200) { e.as_backmax = rint(n); i = i + 1; }    // 0: none; unset: auto
		else if (w == "pace" && n >= 0 && n <= 10) { e.as_pace = n; i = i + 1; }    // 0: energy alone
		else if (w == "emin" && n >= 0 && n <= 1.2) { e.as_emin = n; i = i + 1; }   // 0: any speed counts
		else if (w == "nohop") e.as_hop = 0;
		else if (w == "join") e.as_join = 1;
		else if (w == "rideknots") e.as_rideknots = 1;
		else if (w == "polish") e.as_polish = 1;
		else if (w == "low") e.as_low = 1;
		else if (w == "apex") e.as_apex = 1;
		else if (w == "air") e.as_air = 1;
		else if (w == "wide") e.as_wide = 1;
		else if (w == "spots") e.as_spots = 1;
		else if (w == "start") st = 1;
		else if (w == "plan") pl = 1;
		else if (w == "zone" && n >= 0 && n < 64 && n == floor(n)) { e.as_szone = n; i = i + 1; }
		else if (w == "sg" && n >= 6 && n <= 2000 && n == floor(n)) { e.as_sg = n; i = i + 1; }   // the most ground ticks before the jump
		else if (w == "onjump") arm = 2;
		else if (w == "onexit") arm = 1;
		else if (w == "finish") e.as_finish = 1;
		else { sprint(e, PRINT_HIGH, sprintf("tas autosurf: unknown option '%s'\n", w)); return; }
	}
	// `start` begins in the start box, before the running attempt the tools need (it is a legal start's own path)
	if (pl) { if (Lobby_Active()) { sprint(e, PRINT_HIGH, "tas autosurf: a local practice tool; not on lobby servers\n"); return; } }
	else if (st || arm) { if (Lobby_Active() || !e.run_tas_rwcap) { SV_TASToolGate(e, "autosurf"); return; } }
	else if (!pl && !SV_TASToolGate(e, "autosurf")) { SV_TASAutoNote(e, 0, "TAS is not paused in a run here: use Restart from the start zone"); return; }
	if (path == "route")
	{	// the clicked route: no demo, no plan to make; from here (a running attempt, paused)
		if (st || arm) { sprint(e, PRINT_HIGH, "tas autosurf route: from a pause on the route (the start options follow a demo)\n"); return; }
		if (rt_n < 1) { sprint(e, PRINT_HIGH, "tas autosurf route: no points yet -- tas route add, or the tab's Add at crosshair\n"); return; }
		as_nrows = 0; as_n = rt_n;
		for (i = 0; i < rt_n; i = i + 1)
		{
			as_wo[i*3] = rt_o[i*3]; as_wo[i*3+1] = rt_o[i*3+1]; as_wo[i*3+2] = rt_o[i*3+2];
			as_wn[i*3] = rt_nn[i*3]; as_wn[i*3+1] = rt_nn[i*3+1]; as_wn[i*3+2] = rt_nn[i*3+2];
			as_wk[i] = (rt_nn[i*3+2] >= 0.99) ? 2 : ((rt_nn[i*3+2] == 0 && rt_nn[i*3] == 0 && rt_nn[i*3+1] == 0) ? 3 : 1);
			as_wt[i] = 0;
		}
		if (e.as_file != "") strunzone(e.as_file);
		e.as_file = "";
		e.as_route = 1; e.as_on = 1; e.as_stage = 1; e.as_i = 0; e.as_try = 0; e.as_backs = 0; e.as_tprev = 0; e.as_failat = -1;
		SV_TASAutoBacks(e);
		SV_TASAutoNote(e, 1, sprintf("your route: %.0f points ahead", as_n));
		return;
	}
	e.as_route = 0;
	path = strzone(path);                       // argv is clobbered by the reads and searches below
	as_nrows = SV_TASAutoRead(path);
	if (as_nrows < 0)
	{
		sprint(e, PRINT_HIGH, (as_nrows == -2) ? "tas autosurf: that demo is another map's\n" : sprintf("tas autosurf: cannot read %s\n", path));
		strunzone(path); return;
	}
	e.as_nolegal = 0; e.as_arm = 0;
	if ((st || arm) && as_nrows < 2) { sprint(e, PRINT_HIGH, "tas autosurf: that demo has no samples to start from\n"); strunzone(path); return; }
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
		e.as_on = 1; e.as_stage = 10; e.as_backs = 0; e.as_sn = 0; e.as_sn2 = 0; e.as_sdrop = 0; e.as_sair = -1; e.as_sph = 0;
		SV_TASAutoNote(e, 1, "start: prestrafe toward the demo's exit line, then one jump");
		return;
	}
	if (pl)
	{	// the preview: the plan from the start box's exit (i, above), sent to the player's Jargon panel; nothing runs
		if (jg_ovpath != path)
		{
			jg_ovn = 0;
			if (jg_ovpath != "") strunzone(jg_ovpath);
			jg_ovpath = strzone(path);
		}
		SV_TASAutoPlan(e, i);
		for (s = 0; s == 0 || s < as_n; s = s + 40)
		{	// chunks of 40 points (23 bytes each): one message past ~52 overflowed a UDP client's backbuffer (review)
			WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET); WriteByte(MSG_MULTICAST, TAS_EV_JPLAN);
			WriteByte(MSG_MULTICAST, as_n); WriteByte(MSG_MULTICAST, s); WriteByte(MSG_MULTICAST, min(40, as_n - s));
			for (n = s; n < min(as_n, s + 40); n = n + 1)
			{
				WriteByte(MSG_MULTICAST, as_wk[n]); WriteFloat(MSG_MULTICAST, as_wt[n]);
				WriteFloat(MSG_MULTICAST, as_wo[n*3]); WriteFloat(MSG_MULTICAST, as_wo[n*3+1]); WriteFloat(MSG_MULTICAST, as_wo[n*3+2]);
				WriteShort(MSG_MULTICAST, rint(as_wn[n*3] * 30000)); WriteShort(MSG_MULTICAST, rint(as_wn[n*3+1] * 30000));
				WriteShort(MSG_MULTICAST, rint(as_wn[n*3+2] * 30000));
			}
			msg_entity = e; multicast(e.origin, MULTICAST_ONE_R);
		}
		SV_TASAutoNote(e, 0, sprintf("route: %.0f points from the guide run", as_n));
		SV_TASAutoOptRestore(e);
		strunzone(path);
		return;
	}
	s = SV_TASAutoPlan(e, -1);
	if (s < 0) { SV_TASAutoNote(e, 0, "you are not on the guide run's route (400 u): restart, or redo from a stretch"); strunzone(path); return; }
	if (as_n < 1) { sprint(e, PRINT_HIGH, "tas autosurf: no ramp, hop or finish ahead on the demo from here\n"); strunzone(path); return; }
	if (e.as_file != "") strunzone(e.as_file);
	e.as_file = path;
	e.as_on = 1; e.as_stage = 1; e.as_i = 0; e.as_try = 0; e.as_backs = 0; e.as_tprev = as_rows[s*7]; e.as_failat = -1;
	SV_TASAutoBacks(e);
	SV_TASAutoNote(e, 1, sprintf("%.0f stretches ahead from demo t=%.2f (%.0f u off its route)", as_n, as_rows[s*7], vlen(SV_TASAutoRowO(s) - e.origin)));
};
