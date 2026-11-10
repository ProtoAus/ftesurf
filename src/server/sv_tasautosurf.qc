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
.float as_lmused;               // the least lead this stretch's search ran with (the failed-state record compares it)
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
.float as_ri;                   // P1478: the guide's row the start replays next (stage 13), -1 when it steers instead
.vector as_runo;                // where the run started (the start box's edge): the start steers 48 u past it before planning
.vector as_ex;                  // the demo's position as its run starts (its first sample at t >= 0)
.vector as_exd;                 // and its horizontal heading there: the start steers onto that line
void(entity e, float z) SV_TASLegalStart;
.string as_file;
.float as_route;                // the chain is the player's clicked route (tas route), not a demo's plan
// P1478: courses. A KSF bonus replay was offered for the main start and planned from the wrong box; the guide's own
// header says its course, and a stage run from a full-run guide starts at the guide's crossing out of that stage's box.
float as_dtrack, as_dleg;       // the guide's `track` / `leg` header lines (-1: not stated)
float as_r0;                    // the guide's row where the course starts
float as_rmin;                  // the nearest-row search starts here (a full-run guide may pass a stage's place earlier)
.float as_ctrack, as_cleg;      // the chain's course: track (0 main, k bonus k), leg (0 the whole track, k stage k); -1 none
.float as_saved;                // the furthest stretch autosaved for Continue (-1 none)
.float as_esc;                  // P1478: effort steps a stuck course chain has taken by itself (2 at most)
.float as_coastf;              // coasts predicted into a wrong teleport this chain (a reach resets as_try: rig t2chain10 looped)
.float as_cseed;               // P1483: Continues of this course this session (a Continue after "stuck" searched exactly as before: review F)
float as_visit[TAS_ASMAX];      // P1483: searches of each stretch this chain (in the seed)
// a set tas_jargon_seed reproduces a chain exactly (the benchmark); unset, each new chain searches anew
void() SV_TASAutoRunSalt = { topt_runsalt = cvar("tas_jargon_seed") ? 0 : topt_runsalt + 1 - 1000 * floor((topt_runsalt + 1) / 1000); };
float(entity e, float i) SV_TASAutoSeedOf =
{	// under 1e6 (the optimizer's limit): try < 10, backs <= 200, esc <= 2, cseed <= 9, visits mod 13
	return e.as_try + 10 * min(200, e.as_backs) + 2100 * min(2, e.as_esc) + 7000 * min(9, e.as_cseed) + 70000 * (as_visit[i] - 13 * floor(as_visit[i] / 13));
};
// P1483 `beam`: after a stretch reaches, its search's kept candidates (SV_TASOptArcKeep, up to TOPT_ARCN) are each played
// from the stretch's start and judged by a quick search of the stretch after; the best is played again and the chain goes
// on from it -- a board that wins now and leaves the next ramp unmakeable loses (surf_shape bonus 1: stretch 1 boarded
// 350 u off the guide's point and every stretch-2 line died within 3 ticks)
.float as_beam, as_bmi, as_bmk, as_bmph, as_bmn;        // on; the stretch; the candidate under test; 1 play it, 2 the stretch after, 3 the chosen played
float as_bms[TOPT_ARCN];                                // each candidate's next-stretch score
float as_bmd[TAS_ASMAX];                                // a beamed stretch's chosen candidate + 1 (0: not beamed)
float as_bmso[TAS_ASMAX * 3];                           // ...and where it started (a backtrack that moves the start beams it again)
float as_bmkn[TOPT_ARCN * TOPT_KMAX], as_bmv[TOPT_ARCN], as_bme[TOPT_ARCN], as_bmo[TOPT_ARCN * 3];   // the search's kept candidates
float as_bmarcn, as_bmkd, as_bmnn, as_bmmode;
vector as_bmmo, as_bmmv, as_bmtgt;
.float as_bmtry, as_bmrb, as_bmrf;      // the try the stretch reached on (its emin), and its records (review D)
// P1483: what past runs learned about this course with this guide -- each stretch's best played line (its knots) and the
// share of the guide's energy it carried -- in data/jargon/<map>/<leg folder>.prior; a search starts with it among its
// first candidates, so a course run again starts from its best so far (tas_jargon_off 256: none)
float as_prs[TAS_ASMAX], as_prkd[TAS_ASMAX], as_prk[TAS_ASMAX * TOPT_KMAX], as_prt[TAS_ASMAX], as_prw[TAS_ASMAX];
float as_prp[TOPT_KMAX], as_prpkd, as_prpi, as_prpsh;  // the last reach's line, kept as its stretch's prior once the next reaches
// P1483: the older repair rules, each switched off by a bit of tas_jargon_off for the benchmark (P1478 tools/jgbench.py)
float(float b) SV_TASAutoRule = { return !(cvar("tas_jargon_off") & b); };
.float as_fromstart;            // the chain began at the course's start box (a Start or a Continue): only these autosave
.float as_savedold, as_keepsaid; // a saved run of this course that got further (its stretch), and the note that kept it said
.float as_savedoldt;            // ...its last reached waypoint's guide time: plans differ (turn points, options), times do not (review H)
float as_cwt[TAS_ASMAX], as_cnxt;
.float as_finrec;               // run_t_finrec when the chain began: a finish since counts (a stage's hands over to the next arm)
.float as_chead, as_ctprev, as_cnext, as_cof;    // a Continue's load: the run tick, demo time, stretch, of
.vector as_corg;                // ...and where the saved run was
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
float as_hb[TAS_ASMAX];         // a ramp's backtracks for the hops after it falling short (the second goes past it)
float as_fresh[TAS_ASMAX];      // a backtrack's stretch: its next search starts without its remembered line
float as_lost[TAS_ASMAX];       // backtracks sent to a ramp because the energy against the guide's fell there
float as_back[TAS_ASMAX], as_up[TAS_ASMAX];  // a board's point moved back along its ramp and up toward the tip
float as_slack[TAS_ASMAX];      // the tube's slack past a ride's exit, set once a stretch's line left the path early
#define TAS_SLACK 200
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
float as_sso[TAS_ASMAX * 6], as_fso[TAS_ASMAX * 6], as_fsl[TAS_ASMAX], as_fsm[TAS_ASMAX];
float *as_rows;                 // the demo's samples: t x y z vx vy vz
float *as_bin;                  // P1478: each sample's inputs: forward, side, pitch, yaw (columns 11, 12, 7, 8)
float as_nrows;
float as_nraw, as_traw0, as_traw1;      // P1478: the guide as read, before a course cut: rows, first and last time (Continue's check)

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
	e.as_on = 0; e.as_swph = 0; e.as_redo = 0; e.as_bmph = 0;
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
	if (!as_bin) as_bin = (float*)memalloc(TAS_ASROWS * 4 * 4);
	if (!as_rows || !as_bin) return -1;
	fh = fopen(path, FILE_READ);
	if (fh < 0) return -1;
	n = 0; blank = 0; as_dtrack = as_dleg = -1; as_rmin = 0; as_r0 = 0;
	while (n < TAS_ASROWS && blank < 64 && lines < TAS_DEMOLINES * 2)
	{
		line = fgets(fh); lines = lines + 1;
		if (line == "") { blank = blank + 1; continue; }
		blank = 0;
		c = tokenize(line);
		if (argv(0) == "map" && c >= 2 && strcasecmp(argv(1), mapname)) { fclose(fh); return -2; }
		if (!n && c == 2 && argv(0) == "track" && FS_TASNumber(argv(1))) as_dtrack = stof(argv(1));
		if (!n && c == 2 && argv(0) == "leg" && FS_TASNumber(argv(1))) as_dleg = stof(argv(1));
		if (c < 7 || !FS_TASNumber(argv(0))) continue;
		as_rows[n*7] = stof(argv(0));
		as_rows[n*7+1] = stof(argv(1)); as_rows[n*7+2] = stof(argv(2)); as_rows[n*7+3] = stof(argv(3));
		as_rows[n*7+4] = stof(argv(4)); as_rows[n*7+5] = stof(argv(5)); as_rows[n*7+6] = stof(argv(6));
		as_bin[n*4] = as_bin[n*4+1] = as_bin[n*4+2] = as_bin[n*4+3] = 0;
		if (c >= 13)
		{
			as_bin[n*4] = SV_TASDemoMove(stof(argv(11))); as_bin[n*4+1] = SV_TASDemoMove(stof(argv(12)));
			as_bin[n*4+2] = bound(-89, stof(argv(7)), 89); as_bin[n*4+3] = stof(argv(8));
		}
		n = n + 1;
	}
	fclose(fh);
	as_nraw = n; as_traw0 = n ? as_rows[0] : 0; as_traw1 = n ? as_rows[(n - 1) * 7] : 0;
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
float as_optsave[21];
void(entity e) SV_TASAutoOptSave =
{
	as_optsave[0] = e.as_tube; as_optsave[1] = e.as_look; as_optsave[2] = e.as_tries; as_optsave[3] = e.as_backmax;
	as_optsave[4] = e.as_hop; as_optsave[5] = e.as_finish; as_optsave[6] = e.as_pace; as_optsave[7] = e.as_emin;
	as_optsave[8] = e.as_join; as_optsave[9] = e.as_rideknots; as_optsave[10] = e.as_polish; as_optsave[11] = e.as_low;
	as_optsave[12] = e.as_apex; as_optsave[13] = e.as_air; as_optsave[14] = e.as_wide; as_optsave[15] = e.as_szone;
	as_optsave[16] = e.as_sg; as_optsave[17] = e.as_sy; as_optsave[18] = e.as_sside; as_optsave[19] = e.as_spots; as_optsave[20] = e.as_beam;
};
void(entity e) SV_TASAutoOptRestore =
{
	e.as_tube = as_optsave[0]; e.as_look = as_optsave[1]; e.as_tries = as_optsave[2]; e.as_backmax = as_optsave[3];
	e.as_hop = as_optsave[4]; e.as_finish = as_optsave[5]; e.as_pace = as_optsave[6]; e.as_emin = as_optsave[7];
	e.as_join = as_optsave[8]; e.as_rideknots = as_optsave[9]; e.as_polish = as_optsave[10]; e.as_low = as_optsave[11];
	e.as_apex = as_optsave[12]; e.as_air = as_optsave[13]; e.as_wide = as_optsave[14]; e.as_szone = as_optsave[15];
	e.as_sg = as_optsave[16]; e.as_sy = as_optsave[17]; e.as_sside = as_optsave[18]; e.as_spots = as_optsave[19]; e.as_beam = as_optsave[20];
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

// the guide's velocity heading change from row j-1 to j (0 under 200 u/s, where a heading is noise)
float(float j) SV_TASAutoHeadD =
{
	local float d;
	if (vlen([as_rows[j*7+4], as_rows[j*7+5], 0]) < 200 || vlen([as_rows[j*7-3], as_rows[j*7-2], 0]) < 200) return 0;
	d = vectoyaw([as_rows[j*7+4], as_rows[j*7+5], 0]) - vectoyaw([as_rows[j*7-3], as_rows[j*7-2], 0]);
	return d - 360 * floor((d + 180) / 360);
};
// P1483: a flight that turns 90 degrees or more gets an air point where half of its turn is done -- surf_shape bonus 1
// turns 237 degrees in one 1.4 s flight and every line flew straight on, 1522 u past ramp 2; surf_tensor2 stage 5's
// stretch 4 is an S (-73 then +172) whose lines fell into the fail teleport on the first swing (tools/jgturns.py).
// Progress is signed: an S's swing the other way is not half the turn. tas_jargon_off 512: none. Collected here and
// placed after the boards, hops and finish, into free slots only (tools/jgturns.py over 337 guides: 3 more would pass
// TAS_ASMAX, and a turn point must never take a board's place).
float as_tpj[TAS_ASMAX], as_tpn;
float as_rdt[TAS_ASMAX], as_rdk[TAS_ASMAX], as_rdr[TAS_ASMAX], as_rdl[TAS_ASMAX], as_rdo[TAS_ASMAX * 3], as_rdn[TAS_ASMAX * 3], as_rdnn;
void(float back) SV_TASAutoPlanCopy =
{	// a redo's plan before its replan; back: put it back
	local float i, j;
	if (back)
	{
		as_n = as_rdnn;
		for (i = 0; i < as_n; i = i + 1)
		{
			as_wt[i] = as_rdt[i]; as_wk[i] = as_rdk[i]; as_wr[i] = as_rdr[i]; as_wl[i] = as_rdl[i];
			for (j = 0; j < 3; j = j + 1) { as_wo[i*3+j] = as_rdo[i*3+j]; as_wn[i*3+j] = as_rdn[i*3+j]; }
		}
		return;
	}
	as_rdnn = as_n;
	for (i = 0; i < as_n; i = i + 1)
	{
		as_rdt[i] = as_wt[i]; as_rdk[i] = as_wk[i]; as_rdr[i] = as_wr[i]; as_rdl[i] = as_wl[i];
		for (j = 0; j < 3; j = j + 1) { as_rdo[i*3+j] = as_wo[i*3+j]; as_rdn[i*3+j] = as_wn[i*3+j]; }
	}
};
void(float a, float b) SV_TASAutoTurn =
{
	local float j, c, tot;
	if (as_rows[b*7] - as_rows[a*7] < 0.6 - 0.0001) return;
	tot = 0;
	for (j = a + 1; j < b; j = j + 1) tot = tot + SV_TASAutoHeadD(j);     // row b boards: its clip is the ramp's
	if (fabs(tot) < 90) return;
	c = 0;
	for (j = a + 1; j < b; j = j + 1)
	{
		c = c + SV_TASAutoHeadD(j);
		if (c * tot >= 0.5 * tot * tot) break;
	}
	if (j >= b) return;
	if (as_rows[j*7] - as_rows[a*7] < 0.25 - 0.0001 || as_rows[b*7] - as_rows[j*7] < 0.25 - 0.0001) return;     // the board's own turn
	if (as_tpn < TAS_ASMAX) { as_tpj[as_tpn] = j; as_tpn = as_tpn + 1; }
};
void() SV_TASAutoTurnsPlace =
{
	local float k, j, m, i;
	for (k = 0; k < as_tpn && as_n < TAS_ASMAX; k = k + 1)
	{
		j = as_tpj[k];
		for (m = 0; m < as_n && as_wt[m] <= as_rows[j*7]; m = m + 1) ;
		for (i = as_n; i > m; i = i - 1)
		{
			as_wt[i] = as_wt[i - 1]; as_wk[i] = as_wk[i - 1]; as_wr[i] = as_wr[i - 1]; as_wl[i] = as_wl[i - 1];
			as_wo[i*3] = as_wo[i*3 - 3]; as_wo[i*3+1] = as_wo[i*3 - 2]; as_wo[i*3+2] = as_wo[i*3 - 1];
			as_wn[i*3] = as_wn[i*3 - 3]; as_wn[i*3+1] = as_wn[i*3 - 2]; as_wn[i*3+2] = as_wn[i*3 - 1];
		}
		as_wt[m] = as_rows[j*7]; as_wk[m] = 5; as_wr[m] = TAS_AIRR; as_wl[m] = -1;     // -1: a turn point (kind 6 to the client)
		as_wo[m*3] = as_rows[j*7+1]; as_wo[m*3+1] = as_rows[j*7+2]; as_wo[m*3+2] = as_rows[j*7+3];
		as_wn[m*3] = as_wn[m*3+1] = as_wn[m*3+2] = 0;
		as_n = as_n + 1;
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
		for (i = as_rmin; i < as_nrows; i = i + 1)
		{
			d = vlen(SV_TASAutoRowO(i) - e.origin);
			if (d < best) { best = d; s = i; }
		}
	if (s < 0 || best > 400) return -1;
	as_n = 0; st = -1; lastleave = s; gdt = cvar("sv_gravity") * PM_TICK; as_tpn = 0;
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
				if (as_n == pk && st > s + 2 && SV_TASAutoRule(512)) SV_TASAutoTurn(max(lastleave, s), st);   // after any hop or peak: none
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
	SV_TASAutoTurnsPlace();     // after the player's air points: near TAS_ASMAX theirs stay (review H)
	SV_TASAutoMoved();
	if (cvar("developer"))
		for (i = 0; i < as_n; i = i + 1)
			sprint(e, PRINT_HIGH, sprintf("tas autosurf: stretch %.0f: %s at demo t=%.3f %v, face %v\n", i + 1,
				SV_TASAutoKind(as_wk[i]), as_wt[i],
				[as_wo[i*3], as_wo[i*3+1], as_wo[i*3+2]], [as_wn[i*3], as_wn[i*3+1], as_wn[i*3+2]]));
	return s;
};

string(float track, float leg) SV_TASAutoCourseName =
{
	if (track > 0) return (leg > 0) ? sprintf("bonus %g stage %g", track, leg) : sprintf("bonus %g", track);
	return (leg > 0) ? sprintf("stage %g", leg) : "the main course";
};

// the first guide row from `from` whose hull is in zone z (the timer's own hull test), -1 none
float(float z, float from) SV_TASAutoRowIn =
{
	local float i;
	if (z < 0) return -1;
	for (i = max(0, from); i < as_nrows; i = i + 1)
		if (Zone_BoxInside(z, SV_TASAutoRowO(i), PM_HULL_MINS, PM_HULL_MAXS)) return i;
	return -1;
};

// the first guide row from `from` in one of the track's END boxes, -1 none (a KSF demo runs on past its finish)
float(float track, float from) SV_TASAutoEndRow =
{
	local float z, i, best;
	best = -1;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_type[z] == ZONE_END)
		if (zone_track[z] == track)
		{
			i = SV_TASAutoRowIn(z, from);
			if (i >= 0 && (best < 0 || i < best)) best = i;
		}
	return best;
};

// P1478: the chain's course against its guide (track -1: the guide's own). Sets the start zone (as_szone), the guide's
// rows cut to the course (as_r0 .. as_nrows - 1) and the line the start steers onto. A stage of a full-run guide runs
// from its crossing out of that stage's box to its entry into the next; stage 1 starts at the main box (a TAS legal
// start arms a full run there: the v3 project format has no stage-1 flag). FALSE, with a note, when it cannot be.
float(entity e, float track, float leg) SV_TASAutoCourse =
{
	local float z, r, i, j, run0, own;
	own = (track < 0);
	if (own) { track = max(0, as_dtrack); leg = max(0, as_dleg); }
	if (as_dtrack >= 0 && as_dtrack != track)
	{
		SV_TASAutoNote(e, 0, sprintf("that guide run is of %s, not %s: pick one of this course",
			SV_TASAutoCourseName(as_dtrack, max(0, as_dleg)), SV_TASAutoCourseName(track, leg)));
		return FALSE;
	}
	if (as_dleg > 0 && as_dleg != leg)
	{
		SV_TASAutoNote(e, 0, sprintf("that guide run is %s alone, not %s", SV_TASAutoCourseName(track, as_dleg), SV_TASAutoCourseName(track, leg)));
		return FALSE;
	}
	if (!zone_loaded) SV_ZoneFrame();
	z = SV_ZoneFindLeg(track, max(0, leg - 1));
	if (z < 0 && own && zone_count <= 0)
	{	// a map without zones: the plan as before, from the run's first sample (a start says why it cannot)
		for (as_r0 = 0; as_r0 < as_nrows - 1 && as_rows[as_r0*7] < 0; as_r0 = as_r0 + 1) ;
		return TRUE;
	}
	if (z < 0) { SV_TASAutoNote(e, 0, sprintf("this map has no %s", SV_TASAutoCourseName(track, leg))); return FALSE; }
	for (run0 = 0; run0 < as_nrows - 1 && as_rows[run0*7] < 0; run0 = run0 + 1) ;
	r = run0;
	if (as_dleg <= 0 && leg >= 2)
	{
		i = SV_TASAutoRowIn(z, run0);
		if (i < 0) { SV_TASAutoNote(e, 0, sprintf("that guide run never passes %s's box", SV_TASAutoCourseName(track, leg))); return FALSE; }
		for (j = min(i + 1, as_nrows - 1); j < as_nrows - 1 && Zone_BoxInside(z, SV_TASAutoRowO(j), PM_HULL_MINS, PM_HULL_MAXS); j = j + 1) ;
		r = j;
	}
	else if (SV_TASAutoRowIn(z, max(0, run0 - 400)) < 0 || SV_TASAutoRowIn(z, max(0, run0 - 400)) > run0 + 16)
		sprint(e, PRINT_HIGH, sprintf("tas autosurf: the guide run's start is not in %s's box here (its zones differ?)\n", SV_TASAutoCourseName(track, leg)));
	// to its entry into the next stage's box, or the last stage and a whole track to its END box
	j = (leg >= 1) ? SV_ZoneFindLeg(track, leg) : -1;
	i = (j >= 0) ? SV_TASAutoRowIn(j, r + 1) : SV_TASAutoEndRow(track, r + 1);
	if (i > r + 8) as_nrows = i + 1;
	if (as_nrows - r < 8) { SV_TASAutoNote(e, 0, sprintf("the guide run has too little of %s", SV_TASAutoCourseName(track, leg))); return FALSE; }
	as_r0 = r; as_rmin = max(0, r - 64);
	e.as_szone = z;
	e.as_ex = SV_TASAutoRowO(r);
	e.as_exd = normalize([as_rows[r*7+4], as_rows[r*7+5], 0]);
	if (e.as_exd == '0 0 0') e.as_exd = '1 0 0';
	return TRUE;
};

// P1478: the guide's own start -- its last standstill on the ground before the course's first row (-1: none, as a
// full-run guide crossing a stage's box at speed). The start replays its rows from there: surf_tensor2's stage-2 box
// is 270 u from spawn to exit, where the runway capture (450 u and more) jumped 375 u off the line (rig t2chain1).
float(entity e) SV_TASAutoRest =
{
	local float i;
	for (i = as_r0 - 1; i >= 1; i = i - 1)
		if (!as_rows[i*7+4] && !as_rows[i*7+5] && !as_rows[i*7+6] && as_rows[i*7+3] == as_rows[i*7-4])
		{	// in the course's own start box (a full-run guide's spawn before a stage walked out of it: review C)
			if (e.as_szone >= 0 && e.as_szone < zone_count)     // nested: zone arrays at -1 are fatal
			if (Zone_PointInside(e.as_szone, SV_TASAutoRowO(i))) return i;
			return -1;
		}
	return -1;
};

// P1478: Continue. A course chain that began at the start zone (a legal session) saves the run as a legal-start TAS
// project, jg_<leg folder>, each time it reaches its furthest stretch yet, and its place in the chain beside it
// (<name>.jargon); `tas autosurf continue <track> <leg>` loads both.
string(entity e) SV_TASAutoSaveName = { return strcat("jg_", FS_LegDir(e.as_ctrack, e.as_cleg)); };
string(string name) SV_TASAutoSidePath = { return sprintf("data/tasproj/%s/%s.jargon", mapname, name); };
#define TAS_ASNOTES (12 + 4 * TAS_ASMAX)     // lines a notes file can hold (the writer's read-back and the reader agree)

// a notes number: the plain decimal FS_TASNumber reads, or %.9g's own exponent form -- never NaN or an infinity (a
// hand-edited `at nan` reached as_ws[NaN], a fatal bound check: review B)
float(string t) SV_TASAutoNum =
{
	local float x;
	if (FS_TASNumber(t)) return TRUE;
	x = stof(t);
	if (x != x || fabs(x) > 1000000000) return FALSE;
	return !strcmp(t, sprintf("%.9g", x));
};
float(float from, float c) SV_TASAutoNums =
{
	local float i;
	for (i = from; i < c; i = i + 1) if (!SV_TASAutoNum(argv(i))) return FALSE;
	return TRUE;
};
float(float x, float lo, float hi) SV_TASAutoWhole = { return (x == floor(x) && x >= lo && x <= hi); };

// the stretch a saved run of this course had reached, 0 none -- only a run Continue could use: notes that pass, made
// with this guide as it is now (notes it refuses blocked every new autosave for good: review C)
float as_cnx, as_cgn, as_cg0, as_cg1;
string as_cguide;
float(entity e, float track, float leg, float commit) SV_TASAutoNotes;
float(entity e) SV_TASAutoSavedAt =
{
	if (!SV_TASAutoNotes(e, e.as_ctrack, e.as_cleg, 0)) return 0;
	if (strcmp(as_cguide, e.as_file)) return 0;
	if (as_cgn >= 0 && (as_nraw != as_cgn || as_traw0 != as_cg0 || as_traw1 != as_cg1)) return 0;
	return as_cnx;
};

void(entity e, float next) SV_TASAutoSave =
{
	local float head, f, i, ok;
	local string name, path;
	// strictly further only (a re-reach after a backtrack wrote a revision each time: review B); only a chain that began at
	// the course's box, in that box's session (a From-here forked the player's own project into jg_: review B)
	if (e.as_ctrack < 0 || e.as_route || !e.as_fromstart || next - 1 <= e.as_saved || !SV_TASLegalValid(e) || e.run_t_state != TS_RUNNING) return;
	if (next >= as_n && e.as_finish) return;   // the coast decides the last one (saved there, Continue could never retry it: review C)
	if (e.taslg_zone != e.as_szone || e.as_bmph) return;
	if (e.as_saved < 0 && e.as_savedold > 0 && as_wt[next - 1] <= e.as_savedoldt + 0.0001)
	{	// a saved run of this course that got further is the player's Continue: a new Start overwrites it only once it passes
		if (!e.as_keepsaid) SV_TASAutoNote(e, 1, sprintf("a saved run of %s that reached stretch %.0f is kept until this one gets further",
			SV_TASAutoCourseName(e.as_ctrack, e.as_cleg), e.as_savedold));
		e.as_keepsaid = 1;
		return;
	}
	name = SV_TASAutoSaveName(e);
	head = e.taslg_startat + SV_TimerTicks(e);
	SV_TASProjectSaveLegal(e, name, TRUE);
	ok = (e.tasp_on && e.tasp_legal && e.tasp_lhead == head);
	if (ok) ok = !strcmp(tasp_name[SV_TASPSlot(e)], name);
	if (!ok) { SV_TASAutoNote(e, 1, "this run could not be saved for Continue (the line before says why)"); return; }
	path = SV_TASAutoSidePath(name);
	f = fopen(path, FILE_WRITE);
	if (f < 0) { SV_TASAutoNote(e, 1, "the Continue notes could not be written"); return; }
	fputs(f, "jargon 1\n", sprintf("guide %s\n", e.as_file), sprintf("course %g %g\n", e.as_ctrack, e.as_cleg));
	fputs(f, sprintf("gfp %.0f %.9g %.9g\n", as_nraw, as_traw0, as_traw1));
	fputs(f, sprintf("opts %g %g %g %g ", e.as_tube, e.as_look, e.as_tries, e.as_backmax), sprintf("%g %g %.9g %.9g\n", e.as_hop, e.as_finish, e.as_pace, e.as_emin));
	fputs(f, sprintf("opts2 %g %g %g %g ", e.as_join, e.as_rideknots, e.as_polish, e.as_low), sprintf("%g %g %g %g\n", e.as_apex, e.as_air, e.as_wide, e.as_spots));
	fputs(f, sprintf("opts3 %g\n", e.as_beam));
	fputs(f, sprintf("at %.0f %.0f %.0f %.9g %.0f\n", next, as_n, SV_TimerTicks(e), e.as_tprev, e.as_backs));
	fputs(f, sprintf("org %.9g %.9g %.9g\n", e.origin_x, e.origin_y, e.origin_z));
	for (i = 0; i < next; i = i + 1)
	{
		fputs(f, sprintf("s %.0f %.0f %.9g %.9g %.9g\n", i, as_ws[i], as_wp[i], as_rbs[i], as_rfs[i]));
		fputs(f, sprintf("so %.0f %.9g %.9g %.9g\n", i, as_sso[i*6], as_sso[i*6+1], as_sso[i*6+2]));
	}
	for (i = 0; i < as_n; i = i + 1)
	{
		fputs(f, sprintf("w %.0f %.0f %.9g %.9g %.9g %.9g\n", i, as_wk[i], as_wt[i], as_wo[i*3], as_wo[i*3+1], as_wo[i*3+2]));
		fputs(f, sprintf("wn %.0f %.9g %.9g %.9g %.9g %.9g\n", i, as_wn[i*3], as_wn[i*3+1], as_wn[i*3+2], as_wl[i], as_wr[i]));
	}
	fputs(f, "end\n");
	fclose(f);
	// FILE_WRITE fails silently at fclose: read it back
	ok = 0;
	f = fopen(path, FILE_READ);
	if (f >= 0)
	{
		for (i = 0; i < TAS_ASNOTES && ok < 2; i = i + 1)
		{
			tokenize(fgets(f));
			if (!i && argv(0) == "jargon") ok = 1;
			if (ok && argv(0) == "end") ok = 2;
		}
		fclose(f);
	}
	if (ok < 2) { SV_TASAutoNote(e, 1, "the Continue notes did not read back"); return; }
	e.as_saved = next - 1;
	SV_TASAutoNote(e, 1, sprintf("saved for Continue: %s to stretch %.0f of %.0f (as the TAS project %s)", SV_TASAutoCourseName(e.as_ctrack, e.as_cleg), next, as_n, name));
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
	if (as_wk[i] == 3 && e.as_ctrack >= 0) f = 0;   // P1478: a course's end counts at any speed (the score still wants more)
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
			if (fabs((trace_endpos - o) * n + d0) < 2)      // the same plane: not a parallel ramp past the edge (review)
			{
				p = trace_endpos + n * d0;
				traceline(trace_endpos + n, p, MOVE_NOMONSTERS, e);
				if (trace_fraction == 1 && !trace_startsolid) as_swv[k] = 1;
			}
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
// P1483: the beam. Start: after a stretch's own search reached (rank 0 played), keep its candidates and judge them.
float(entity e) SV_TASAutoBeamStart =
{
	local float i, h;
	i = e.as_i;
	if (!e.as_beam || e.as_route || e.as_bmph || i + 1 >= as_n || topt_arcn < 2) return FALSE;
	if (as_bmd[i] && vlen([as_sso[i*6], as_sso[i*6+1], as_sso[i*6+2]] - [as_bmso[i*3], as_bmso[i*3+1], as_bmso[i*3+2]]) < 0.5) return FALSE;
	if (as_wk[i] != 1 && as_wk[i] != 2 && as_wk[i] != 5) return FALSE;
	if (as_wk[i + 1] == 3) return FALSE;     // review E: the finish's quick search would end the course
	for (h = 0; h < TOPT_ARCN * TOPT_KMAX; h = h + 1) as_bmkn[h] = topt_arck[h];
	for (h = 0; h < TOPT_ARCN; h = h + 1) { as_bmv[h] = topt_arcv[h]; as_bme[h] = topt_arce[h]; as_bms[h] = -1000000; }
	for (h = 0; h < TOPT_ARCN * 3; h = h + 1) as_bmo[h] = topt_arco[h];
	as_bmarcn = topt_arcn; as_bmkd = topt_arckd; as_bmmo = topt_arcmo; as_bmmv = topt_arcmv; as_bmtgt = topt_arctgt;
	as_bmnn = topt_arcnn; as_bmmode = topt_arcmode;
	e.as_bmtry = e.as_try;
	e.as_bmi = i; e.as_bmk = 0; e.as_bmn = min(topt_arcn, TOPT_ARCN); e.as_bmph = 2;
	as_bmso[i*3] = as_sso[i*6]; as_bmso[i*3+1] = as_sso[i*6+1]; as_bmso[i*3+2] = as_sso[i*6+2];
	e.as_bmrb = -1000000; e.as_bmrf = 0;    // set by the reached branch's first record below (SV_TASAutoBeamStep)
	SV_TASAutoNote(e, 1, sprintf("stretch %.0f: %.0f different lines reach it; each judged on the stretch after", i + 1, e.as_bmn));
	return TRUE;
};
// the next candidate, or the best one played again
void(entity e) SV_TASAutoBeamNext =
{
	local float i, k, b;
	i = e.as_bmi;
	k = e.as_bmk + 1;
	if (k < e.as_bmn) e.as_bmk = k;
	else
	{
		b = 0;
		for (k = 1; k < e.as_bmn; k = k + 1) if (as_bms[k] > as_bms[b]) b = k;
		as_bmd[i] = b + 1; e.as_bmk = b;
		SV_TASAutoNote(e, 1, sprintf("stretch %.0f: line %.0f of %.0f kept, %s (the search's best: %s)", i + 1, b + 1, e.as_bmn,
			(as_bms[b] >= 100000) ? sprintf("the next ramp at %.0f u/s", as_bms[b] - 100000) : "none made the next ramp",
			(as_bms[0] >= 100000) ? sprintf("%.0f", as_bms[0] - 100000) : "missed it"));
	}
	e.as_bmph = (k < e.as_bmn) ? 1 : 3;
	// the try that kept them (polish's emin differs by try: review D)
	e.as_i = i; e.as_try = e.as_bmtry; e.as_tprev = as_wp[i]; e.as_goal = as_ws[i]; e.as_backhead = -1; e.as_backfail = 0; e.as_stage = 3;
};
// a search ended inside a beam: TRUE when the beam took the outcome (the chain's own handling skipped)
float(entity e) SV_TASAutoBeamStep =
{
	local float i, k;
	i = e.as_bmi; k = e.as_bmk;
	if (e.as_bmph == 1 && e.as_i == i)
	{	// candidate k played: on to the stretch after (the reached branch records it), or judged a miss
		if (e.topt_outcome == 2) { e.as_bmph = 2; return FALSE; }
		as_bms[k] = -1000000; SV_TASAutoBeamNext(e); return TRUE;
	}
	if (e.as_bmph == 2 && e.as_i == i + 1)
	{
		if (!k && e.as_bmrb <= -1000000) { e.as_bmrb = as_rbs[i]; e.as_bmrf = as_rfs[i]; }     // the search's own reach's records
		as_bms[k] = (e.topt_outcome == 2) ? 100000 + SV_TASAutoEnergyAt(e, i + 1) : 50000 - min(49000, e.topt_reachd);
		SV_TASAutoBeamNext(e); return TRUE;
	}
	if (e.as_bmph == 3 && e.as_i == i)
	{	// the chosen line played again: the chain goes on from it
		e.as_bmph = 0;
		if (e.topt_outcome == 2) return FALSE;
		SV_TASAutoNote(e, 1, sprintf("stretch %.0f: the kept line did not play back; the stretch's own handling goes on", i + 1));
		if (e.as_bmrb > -1000000) { as_rbs[i] = e.as_bmrb; as_rfs[i] = e.as_bmrf; }    // not the last candidate's (review D)
		return FALSE;       // as_bmd[i] stays: this start never beams again, so the chain cannot cycle (review D)
	}
	e.as_bmph = 0;      // a backtrack or a stop left the beam: the chain goes on without it
	return FALSE;
};

string(entity e) SV_TASAutoPriorPath = { return sprintf("data/jargon/%s/%s.prior", mapname, FS_LegDir(e.as_ctrack, e.as_cleg)); };
void(entity e) SV_TASAutoPriorLoad =
{
	local float f, k, c, i, j, kd;
	for (i = 0; i < TAS_ASMAX; i = i + 1) as_prs[i] = as_prkd[i] = 0;
	as_prpi = -1;
	if (e.as_ctrack < 0 || e.as_route || !SV_TASAutoRule(256)) return;
	f = fopen(SV_TASAutoPriorPath(e), FILE_READ);
	if (f < 0) return;
	for (k = 0; k < 4 + TAS_ASMAX; k = k + 1)
	{
		c = tokenize(fgets(f));
		if (!k) { if (c != 2 || argv(0) != "jprior" || argv(1) != "1") k = 1000; continue; }
		if (argv(0) == "guide") { if (c != 2 || strcmp(argv(1), e.as_file)) k = 1000; continue; }    // another guide's stretches
		if (argv(0) != "p" || c < 7 || !SV_TASAutoNums(1, c)) continue;
		i = stof(argv(1)); kd = stof(argv(3));
		if (!SV_TASAutoWhole(i, 0, TAS_ASMAX - 1) || !SV_TASAutoWhole(kd, 1, TOPT_KMAX) || c != 6 + kd) continue;
		if (stof(argv(2)) < 0 || stof(argv(2)) > 2) continue;
		for (j = 0; j < kd; j = j + 1) if (fabs(stof(argv(6 + j))) > 1000) j = 1000;
		if (j >= 1000) continue;
		for (j = 0; j < as_n; j = j + 1) if (fabs(as_wt[j] - stof(argv(4))) <= 0.05) if (as_wk[j] == stof(argv(5))) { i = j; j = 1000; }
		if (j < 1000) continue;     // no stretch of this plan is that ramp (review H)
		if (as_prkd[i] > 0 && stof(argv(2)) <= as_prs[i]) continue;    // two entries on one ramp: the better share (review I)
		as_prs[i] = stof(argv(2)); as_prkd[i] = kd; as_prt[i] = stof(argv(4)); as_prw[i] = stof(argv(5));
		for (j = 0; j < kd; j = j + 1) as_prk[i * TOPT_KMAX + j] = stof(argv(6 + j));
	}
	fclose(f);
};
// a stretch's reach: its line held until the stretch after reaches from it
void(entity e, float i) SV_TASAutoPriorPend =
{
	local float j;
	as_prpi = -1;
	if (e.as_ctrack < 0 || e.as_route || e.as_bmph || !SV_TASAutoRule(256) || e.topt_kd < 1 || e.topt_kd > TOPT_KMAX || as_rfs[i] <= 0) return;
	for (j = 0; j < e.topt_kd; j = j + 1) as_prp[j] = topt_kbest[j];
	as_prpkd = e.topt_kd; as_prpi = i; as_prpsh = as_rbs[i] / as_rfs[i];
};
// a held line with more of the guide's energy than its stretch's best so far becomes that stretch's prior
void(entity e, float i) SV_TASAutoPriorKeep =
{
	local float f, j, k, sh;
	if (e.as_ctrack < 0 || e.as_route || e.as_bmph || !SV_TASAutoRule(256) || as_prpi != i) return;
	sh = as_prpsh;
	if (as_prkd[i] > 0 && (fabs(as_prt[i] - as_wt[i]) > 0.05 || as_prw[i] != as_wk[i])) as_prs[i] = 0;   // another plan's ramp
	if (sh <= as_prs[i] + 0.0005 || sh > 2) return;
	as_prs[i] = sh; as_prkd[i] = as_prpkd; as_prt[i] = as_wt[i]; as_prw[i] = as_wk[i];
	for (j = 0; j < as_prpkd; j = j + 1) as_prk[i * TOPT_KMAX + j] = as_prp[j];
	f = fopen(SV_TASAutoPriorPath(e), FILE_WRITE);
	if (f < 0) return;
	fputs(f, "jprior 1\n", sprintf("guide %s\n", e.as_file));
	for (k = 0; k < TAS_ASMAX; k = k + 1)
	{
		if (as_prkd[k] < 1) continue;
		fputs(f, sprintf("p %.0f %.6f %.0f %.9g %.0f", k, as_prs[k], as_prkd[k], as_prt[k], as_prw[k]));
		for (j = 0; j < as_prkd[k]; j = j + 1) fputs(f, sprintf(" %.9g", as_prk[k * TOPT_KMAX + j]));
		fputs(f, "\n");
	}
	fclose(f);
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
	local float i, h, argc, r, q, fz, fz2;
	local vector o, n, cr, cl_v;
	local string ps, ls, cl;
	i = e.as_i;
	e.topt_reachd = 1000000;     // a search that never runs leaves no closest distance (review D)
	if (e.as_redo == i + 1)
	{	// the rewound state must be the one this stretch started from: a restarted run reuses the tick numbers (review)
		e.as_redo = 0;
		if (vlen(e.origin - [as_sso[i*6], as_sso[i*6+1], as_sso[i*6+2]]) > 1)
			{ SV_TASAutoStop(e, "this is not the run that reached that stretch: restart from the start zone"); return; }
	}
	as_ws[i] = SV_TimerTicks(e); as_wp[i] = e.as_tprev;
	as_sso[i*6] = e.origin_x; as_sso[i*6+1] = e.origin_y; as_sso[i*6+2] = e.origin_z;
	as_sso[i*6+3] = e.velocity_x; as_sso[i*6+4] = e.velocity_y; as_sso[i*6+5] = e.velocity_z;
	if (!e.as_route && e.as_try == 0 && as_need[i] <= 0 && as_fsl[i] == as_lowx[i] && as_fsm[i] == as_leadmin[i])
	if (e.origin == [as_fso[i*6], as_fso[i*6+1], as_fso[i*6+2]] && e.velocity == [as_fso[i*6+3], as_fso[i*6+4], as_fso[i*6+5]])
	{	// counted as failed again without a search: the failure handler goes on to the next backtrack
		SV_TASAutoNote(e, 1, sprintf("stretch %.0f starts in the state it failed from before: counted as failed again", i + 1));
		e.topt_outcome = 1; e.topt_lowneed = e.topt_earlycut = e.topt_trigcut = 0; e.topt_over = e.topt_briefn = 0;
		e.as_try = e.as_tries - 1; e.as_stage = 2;
		return;
	}
	o = [as_wo[i*3], as_wo[i*3+1], as_wo[i*3+2]]; n = [as_wn[i*3], as_wn[i*3+1], as_wn[i*3+2]];
	if (e.as_spots && !e.as_beam && !e.as_route && !e.as_swph && !as_swd[i] && as_wk[i] == 1 && i + 1 < as_n && (n_x || n_y) && !SV_TASAutoIsMoved(i))
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
	else if (as_swd[i] > 1 && !SV_TASAutoIsMoved(i)) o = [as_swp[i*3], as_swp[i*3+1], as_swp[i*3+2]];
	if ((as_back[i] > 0 || as_up[i] > 0) && (n_x || n_y))
	{	// back along the ramp's edge (against the guide's way) and up its face, toward the tip
		for (h = 0; h < as_nrows - 1 && as_rows[h*7] < as_wt[i] - 0.0001; h = h + 1) ;
		cr = (n_z < 0) ? -n : n;
		cl_v = normalize([cr_y, -cr_x, 0]);
		if (cl_v * [as_rows[h*7+4], as_rows[h*7+5], as_rows[h*7+6]] < 0) cl_v = -cl_v;
		o = o - as_back[i] * cl_v + as_up[i] * normalize('0 0 1' - cr_z * cr);
	}
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
	r = (as_wk[i] == 2) ? 50 : ((as_wk[i] == 3) ? 400 : ((as_wk[i] == 4 || as_wk[i] == 5) ? as_wr[i] : 800));
	h = min(h, e.topt_dn);
	}
	if (n == '0 0 0') argc = tokenize(sprintf("tas target %.1f %.1f %.1f %.0f", o_x, o_y, o_z, r));
	else argc = tokenize(sprintf("tas target %.1f %.1f %.1f %.0f %.4f %.4f %.4f", o_x, o_y, o_z, r, n_x, n_y, n_z));
	e.topt_tgton = 0;
	SV_TASTargetCommand(e, argc);
	if (!e.topt_tgton) { SV_TASAutoStop(e, "this stretch's target was refused"); return; }
	if (e.as_route)
	{
		as_visit[i] = as_visit[i] + 1;
		cl = sprintf("tas optimize %.0f left curve 12 aim%s gens %.0f%s seed %.0f energy fast", h, (e.as_hop && as_wk[i] == 2) ? " hop" : "",
			e.as_polish ? 90 : min(90, 30 * (1 + e.as_try)), (e.as_polish && e.as_try < e.as_tries - 1) ? " stall 20" : "", SV_TASAutoSeedOf(e, i));
	}
	else
	{
	ps = strcat(SV_TASAutoPace(e, i), SV_TASAutoEmin(e, i));
	ls = (e.as_look > 0) ? sprintf(" look %.0f", e.as_look) : "";
	// a retry searches longer: 30 generations more a try (the pillar stretch's narrow line came in some searches only); a
	// beam's look at the stretch after is a quick one (P1483)
	if (e.as_bmph == 2 && i == e.as_bmi + 1) ps = strcat(ps, " gens 20");
	else ps = strcat(ps, sprintf(" gens %.0f", e.as_polish ? 90 : min(90, 30 * (1 + e.as_try))));
	as_visit[i] = as_visit[i] + 1;
	ps = strcat(ps, sprintf(" seed %.0f", SV_TASAutoSeedOf(e, i)));     // P1483: a retry, an effort step, a Continue, a revisit search anew
	if (e.as_ctrack >= 0)
	{	// a fall lands in the box of the stage the body is in: past stage 1 of a whole-track chain, that stage's (review G)
		fz = e.as_szone;
		if (e.as_cleg == 0 && e.run_t_state == TS_RUNNING && e.run_t_seg >= 1) { fz2 = SV_ZoneFindLeg(e.as_ctrack, e.run_t_seg); if (fz2 >= 0) fz = fz2; }
		if (fz >= 0 && fz < zone_count) ps = strcat(ps, sprintf(" startz %.0f", fz));
		if (fz != e.as_szone && e.as_szone >= 0 && e.as_szone < zone_count) ps = strcat(ps, sprintf(" startz2 %.0f", e.as_szone));
	}
	if (as_wk[i] == 3 && e.as_ctrack >= 0)
	{	// P1483: the course's end box, or its track's END boxes: a reach there (or into the teleport to it) is the finish
		r = (e.as_cleg >= 1) ? SV_ZoneFindLeg(e.as_ctrack, e.as_cleg) : -1;
		ps = strcat(ps, (r >= 0) ? sprintf(" endz %.0f", r) : sprintf(" endtrack %.0f", e.as_ctrack));
	}
	if ((e.as_bmph == 1 || e.as_bmph == 3) && i == e.as_bmi)
	{	// the beam's candidate: the stretch's own search's kept lines put back (the stretch after's search replaced them)
		for (q = 0; q < TOPT_ARCN * TOPT_KMAX; q = q + 1) topt_arck[q] = as_bmkn[q];     // q: h is the horizon here
		for (q = 0; q < TOPT_ARCN; q = q + 1) { topt_arcv[q] = as_bmv[q]; topt_arce[q] = as_bme[q]; }
		for (q = 0; q < TOPT_ARCN * 3; q = q + 1) topt_arco[q] = as_bmo[q];
		topt_arcn = as_bmarcn; topt_arckd = as_bmkd; topt_arcmo = as_bmmo; topt_arcmv = as_bmmv; topt_arctgt = as_bmtgt;
		topt_arcnn = as_bmnn; topt_arcmode = as_bmmode;
		ps = strcat(ps, sprintf(" play %.0f", e.as_bmk));
	}
	if (e.as_polish && e.as_try < e.as_tries - 1) ps = strcat(ps, " stall 20");
	// `low` 0.5 (as_lowx 2): at 0.25 tchain10 boarded ramp 10 557 u under farsh's point; its 0.5 retry boarded 8 u off and faster
	if ((e.as_low || as_lowx[i]) && as_wk[i] == 1) ps = strcat(ps, sprintf(" low %g", 0.25 * max(e.as_low ? 2 : 0, as_lowx[i])));
	if (as_wk[i] == 1 && as_wl[i] > as_wt[i]) ps = strcat(ps, sprintf(" ride %.0f", rint((as_wl[i] - as_wt[i]) / PM_TICK)));
	if (e.as_rideknots && i > 0)
	if (as_wk[i - 1] == 1 && as_wl[i - 1] > e.as_tprev)
		ps = strcat(ps, sprintf(" kex %.0f", min(TOPT_HMAX, rint((as_wl[i - 1] - e.as_tprev) / PM_TICK) + 15)));   // past the cap: refused (review 13)
	if (e.as_wide) ps = strcat(ps, " wide");
	if (as_leadmin[i] > 0 && as_wk[i] == 1) ps = strcat(ps, sprintf(" leadmin %g", as_leadmin[i]));
	if (as_fresh[i]) { ps = strcat(ps, " fresh"); as_fresh[i] = 0; }   // a backtrack's: not the line that led to it
	if (as_slack[i]) ps = strcat(ps, sprintf(" slack %g", as_slack[i]));
	e.as_lmused = as_leadmin[i];
	cl = sprintf("tas optimize %.0f left curve 12 demo aim late tube %.0f%s%s%s energy fast", h, e.as_tube, e.as_hop ? " hop" : "", ls, ps);
	}
	if (cvar("developer")) sprint(e, PRINT_HIGH, strcat("tas autosurf: ", cl, "\n"));
	argc = tokenize(cl);
	e.topt_over = 0; e.topt_trigcut = 0;
	topt_priorn = 0;
	if (!e.as_route && as_prkd[i] > 0 && fabs(as_prt[i] - as_wt[i]) <= 0.05 && as_prw[i] == as_wk[i])     // this ramp's (review F)
	{
		for (q = 0; q < as_prkd[i]; q = q + 1) topt_prior[q] = as_prk[i * TOPT_KMAX + q];
		topt_priorn = as_prkd[i];
	}
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
	e.as_finrec = e.run_t_finrec; e.as_coastf = 0; e.as_bmph = 0; as_prpi = -1;
	for (k = 0; k < TAS_ASMAX; k = k + 1) as_visit[k] = 0;
	SV_TASAutoPriorLoad(e);
	for (k = 0; k < TAS_ASMAX; k = k + 1) as_bmd[k] = 0;
	for (k = 0; k < TAS_ASMAX; k = k + 1) { as_rbs[k] = as_need[k] = as_lowx[k] = as_rfs[k] = as_ws[k] = as_leadmin[k] = as_swd[k] = as_fsm[k] = as_hb[k] = as_fresh[k] = as_slack[k] = as_lost[k] = as_back[k] = as_up[k] = 0; as_fsl[k] = -1; }
	e.as_failmax = -1; e.as_swph = 0; e.as_redo = 0;
};

// P1478: `tas autosurf continue <track> <leg>`: the course's saved run loaded (SV_TASLegalLoad replays it from the
// start zone), then the chain from the stretch it had reached (SV_TASAutoFrame stage 30), its records restored so a
// backtrack can still reach the stretches before.
float as_cov, as_covtries, as_covbacks, as_covflags;   // a Continue's options from the panel (as_cov 0: the saved ones)
// as_cguide, as_cnx, as_cgn/cg0/cg1 (declared above SV_TASAutoSavedAt): the notes' guide, stretch and fingerprint
// A course's notes: commit 0 checks every line (numbers, ranges, indices, counts) and writes nothing; commit 1, run only
// after that passed, writes the chain's state from them. TRUE when the file is whole.
float(entity e, float track, float leg, float commit) SV_TASAutoNotes =
{
	local float f, c, ok, k, bad, i, ns, nw, nx, nof, nso, nwn;
	local string g;
	f = fopen(SV_TASAutoSidePath(SV_TASAutoSaveName(e)), FILE_READ);
	if (f < 0) return FALSE;
	ok = 0; bad = 0; ns = nw = nso = nwn = 0; nx = nof = -1; g = "";
	for (k = 0; k < TAS_ASNOTES && ok < 2 && !bad; k = k + 1)
	{
		c = tokenize(fgets(f));
		if (!k) { if (c != 2 || argv(0) != "jargon" || argv(1) != "1") bad = 1; else ok = 1; continue; }
		if (argv(0) == "end") { ok = 2; continue; }
		if (argv(0) == "guide" && c == 2)
		{
			if (!SV_TASDemoPathOK(argv(1))) bad = 1;
			else { if (as_cguide != "") strunzone(as_cguide); as_cguide = strzone(argv(1)); g = "x"; }
			continue;
		}
		if (!SV_TASAutoNums(1, c)) { bad = 1; continue; }
		if (argv(0) == "course" && c == 3) { if (stof(argv(1)) != track || stof(argv(2)) != leg) bad = 1; }
		else if (argv(0) == "gfp" && c == 4) { as_cgn = stof(argv(1)); as_cg0 = stof(argv(2)); as_cg1 = stof(argv(3)); }
		else if (argv(0) == "opts" && c == 9)
		{	// the command's own ranges (a raw `backs 1e9` never stopped: review B)
			if (stof(argv(1)) < 50 || stof(argv(1)) > 2000 || !SV_TASAutoWhole(stof(argv(2)), 0, 400) || !SV_TASAutoWhole(stof(argv(3)), 1, 10) ||
			    !SV_TASAutoWhole(stof(argv(4)), -1, 200) || !SV_TASAutoWhole(stof(argv(5)), 0, 1) || !SV_TASAutoWhole(stof(argv(6)), 0, 1) ||
			    stof(argv(7)) < 0 || stof(argv(7)) > 10 || stof(argv(8)) < 0 || stof(argv(8)) > 1.2) bad = 1;
			else if (commit)
			{
				e.as_tube = stof(argv(1)); e.as_look = stof(argv(2)); e.as_tries = stof(argv(3)); e.as_backmax = stof(argv(4));
				e.as_hop = stof(argv(5)); e.as_finish = stof(argv(6)); e.as_pace = stof(argv(7)); e.as_emin = stof(argv(8));
			}
		}
		else if (argv(0) == "opts3" && c == 2)
		{
			if (!SV_TASAutoWhole(stof(argv(1)), 0, 1)) bad = 1;
			else if (commit) e.as_beam = stof(argv(1));
		}
		else if (argv(0) == "opts2" && c == 9)
		{
			for (i = 1; i < 9; i = i + 1) if (!SV_TASAutoWhole(stof(argv(i)), 0, 1)) bad = 1;
			if (!bad && commit)
			{
				e.as_join = stof(argv(1)); e.as_rideknots = stof(argv(2)); e.as_polish = stof(argv(3)); e.as_low = stof(argv(4));
				e.as_apex = stof(argv(5)); e.as_air = stof(argv(6)); e.as_wide = stof(argv(7)); e.as_spots = stof(argv(8));
			}
		}
		else if (argv(0) == "at" && c == 6)
		{
			nof = stof(argv(2)); nx = stof(argv(1));
			if (!SV_TASAutoWhole(nof, 1, TAS_ASMAX) || !SV_TASAutoWhole(nx, 1, nof) || !SV_TASAutoWhole(stof(argv(3)), 1, 10000000) ||
			    !SV_TASAutoWhole(stof(argv(5)), 0, 1000)) bad = 1;
			else if (commit) { e.as_cnext = nx; e.as_cof = nof; e.as_chead = stof(argv(3)); e.as_ctprev = stof(argv(4)); }
		}
		else if (argv(0) == "org" && c == 4) { if (commit) e.as_corg = [stof(argv(1)), stof(argv(2)), stof(argv(3))]; }
		else if ((argv(0) == "s" && c == 6) || (argv(0) == "so" && c == 5))
		{
			i = stof(argv(1));
			if (!SV_TASAutoWhole(i, 0, TAS_ASMAX - 1)) bad = 1;
			else if (argv(0) == "s") { ns = ns + 1; if (commit) { as_ws[i] = stof(argv(2)); as_wp[i] = stof(argv(3)); as_rbs[i] = stof(argv(4)); as_rfs[i] = stof(argv(5)); } }
			else { nso = nso + 1; if (commit) { as_sso[i*6] = stof(argv(2)); as_sso[i*6+1] = stof(argv(3)); as_sso[i*6+2] = stof(argv(4)); } }
		}
		else if ((argv(0) == "w" && c == 7) || (argv(0) == "wn" && c == 7))
		{
			i = stof(argv(1));
			if (!SV_TASAutoWhole(i, 0, TAS_ASMAX - 1)) bad = 1;
			else if (argv(0) == "w")
			{
				nw = nw + 1;
				if (!SV_TASAutoWhole(stof(argv(2)), 1, 5)) bad = 1;
				else if (commit) { as_wk[i] = stof(argv(2)); as_wt[i] = stof(argv(3)); as_wo[i*3] = stof(argv(4)); as_wo[i*3+1] = stof(argv(5)); as_wo[i*3+2] = stof(argv(6)); }
				else as_cwt[i] = stof(argv(3));
			}
			else { nwn = nwn + 1; if (commit) { as_wn[i*3] = stof(argv(2)); as_wn[i*3+1] = stof(argv(3)); as_wn[i*3+2] = stof(argv(4)); as_wl[i] = stof(argv(5)); as_wr[i] = stof(argv(6)); } }
		}
	}
	fclose(f);
	if (commit) return TRUE;
	as_cnx = nx; as_cnxt = (nx >= 1 && nx <= TAS_ASMAX) ? as_cwt[max(0, nx - 1)] : 0;
	return (!bad && ok == 2 && g != "" && nx >= 1 && ns == nx && nso == nx && nw == nof && nwn == nof);
};

// P1478: `tas autosurf continue <track> <leg>`: the course's saved run loaded (SV_TASLegalLoad replays it from the start
// zone), then the chain from the stretch it had reached on the saved plan (SV_TASAutoFrame stage 30), every stretch's
// record restored so a backtrack or redo can still reach the ones before.
void(entity e, float track, float leg) SV_TASAutoContinue =
{
	local float ot, ol;
	local string name;
	ot = e.as_ctrack; ol = e.as_cleg;
	e.as_ctrack = track; e.as_cleg = leg;        // the notes' name; put back on every refusal (review A)
	name = SV_TASAutoSaveName(e);
	if (!SV_TASPExists(name))
	{
		SV_TASAutoNote(e, 0, sprintf("nothing saved for %s on this map: surf it from its start first", SV_TASAutoCourseName(track, leg)));
		e.as_ctrack = ot; e.as_cleg = ol; return;
	}
	as_cgn = -1;
	if (!SV_TASAutoNotes(e, track, leg, 0))
	{
		SV_TASAutoNote(e, 0, "the saved run's Jargon notes are missing or not readable: surf the course from its start");
		e.as_ctrack = ot; e.as_cleg = ol; return;
	}
	if (SV_TASAutoRead(as_cguide) < 2 || (as_cgn >= 0 && (as_nraw != as_cgn || as_traw0 != as_cg0 || as_traw1 != as_cg1)))
	{	// the guide as it was at the save, checked before the replay (a vanished one was found only after it: review B)
		SV_TASAutoNote(e, 0, "the saved run's guide is gone or changed since the save: surf the course from its start");
		e.as_ctrack = ot; e.as_cleg = ol; return;
	}
	e.tasp_result = 0;
	SV_TASProjectLoad(e, name, "");
	if (!e.tasp_load && !e.taslg_loading)
	{	// refused (queued TAS work, a pause not allowed): nothing of the stopped chain is touched yet (review C)
		SV_TASAutoNote(e, 0, "the saved run could not be loaded (the line before says why)");
		e.as_ctrack = ot; e.as_cleg = ol; return;
	}
	e.as_backmax = -1;
	SV_TASAutoBacks(e);
	SV_TASAutoNotes(e, track, leg, 1);
	as_n = e.as_cof;
	if (as_cov)
	{	// the panel's effort now; `finish` and `air` stay the save's (they shaped the saved plan: review A)
		if (as_covtries > 0) e.as_tries = as_covtries;
		if (as_covbacks >= 0) e.as_backmax = as_covbacks;
		e.as_rideknots = (as_covflags & 1) ? 1 : 0; e.as_polish = (as_covflags & 2) ? 1 : 0; e.as_low = (as_covflags & 4) ? 1 : 0;
		e.as_wide = (as_covflags & 16) ? 1 : 0; e.as_spots = (as_covflags & 32) ? 1 : 0; e.as_beam = (as_covflags & 128) ? 1 : 0;
	}
	if (e.as_file != "") strunzone(e.as_file);
	e.as_file = strzone(as_cguide);
	e.as_on = 1; e.as_stage = 30; e.as_route = 0; e.as_i = e.as_cnext; e.as_try = 0; e.as_fromstart = 1; e.as_savedold = 0; e.as_keepsaid = 0;
	e.as_cseed = e.as_cseed + 1 - 10 * floor((e.as_cseed + 1) / 10);
	SV_TASAutoNote(e, 1, sprintf("continue: replaying the saved run of %s to stretch %.0f of %.0f", SV_TASAutoCourseName(track, leg), e.as_cnext, e.as_cof));
};

// P1478: the coast into a course's end, predicted first (no keys, 160 ticks, the exact rollout): the tick a teleport into
// the course's end box is met (its finish), -1 for any other teleport met first (surf_tensor2's stage-2 fail teleport:
// the coast lost the run, rigs t2chain3/6), 0 none met or no prediction (the end is a zone box the body coasts into)
float *as_crows;
float *as_cout;                 // fteqcc reads `float *a, *b` with b a float**
float(entity e) SV_TASAutoCoastPredict =
{
	local float i, n, ran, a, k;
	if (!checkbuiltin(tas_rollout)) return 0;
	if (!as_crows) as_crows = (float*)memalloc(160 * 7 * 4);
	if (!as_cout) as_cout = (float*)memalloc(160 * 13 * 4);
	if (!as_crows || !as_cout) return 0;
	n = 160;
	for (i = 0; i < n; i = i + 1)
	{
		as_crows[i*7] = as_crows[i*7+1] = as_crows[i*7+2] = as_crows[i*7+5] = as_crows[i*7+6] = 0;
		as_crows[i*7+3] = SV_TASPWord(e.v_angle_x); as_crows[i*7+4] = SV_TASPWord(e.v_angle_y);
	}
	SV_TASOptSimStart(e);       // review G: else the last search's rollout state
	SV_NoColPre(e);
	ran = tas_rollout(e, as_crows, n, as_cout);
	SV_NoColPost(e);
	if (ran <= 0) return 0;
	k = (e.as_cleg >= 1) ? SV_ZoneFindLeg(e.as_ctrack, e.as_cleg) : -1;      // the course's end, as its finish search had it
	e.topt_endz = k; e.topt_endtrack = (k >= 0) ? -1 : e.as_ctrack;
	for (i = 0; i < ran; i = i + 1)
	{
		a = as_cout[i*13 + 12];
		if (!a) continue;
		k = SV_TASOptEndTele(e, edict_num(fabs(a)));
		if (k == 1) return i + 1;
		if (k == -1) return -1;
		if (strcmp(edict_num(fabs(a)).classname, "trigger_teleport") && strcmp(edict_num(fabs(a)).classname, "trigger_momentum_teleport"))
			return 0;       // another volume: QC acts there, the prediction ends
	}
	return 0;
};

// After SV_TASDemoFrame (SV_TASOptFrame): the next step of the chain once no search is running.
void(entity e) SV_TASAutoFrame =
{
	local float head, i, best, d, t, s, along, lat, herr, ee, ph, argc_pl, rd;
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
	if (e.as_on && e.as_stage == 30)
	{	// P1478: a Continue's load, then the chain from the saved stretch
		if (e.tasp_load || e.taslg_loading || e.run_tas_pending || e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING) return;
		if (e.tasp_result != 1)
		{
			SV_TASAutoStop(e, (e.tasp_result == 2) ? "the saved run did not replay exactly: surf the course from its start"
				: "the saved run's load stopped (the line before says why)");
			return;
		}
		if (e.run_t_state != TS_RUNNING || !e.run_tas_paused || SV_TimerTicks(e) != e.as_chead || vlen(e.origin - e.as_corg) > 0.01)
			{ SV_TASAutoStop(e, "the loaded run is not where Jargon left off: surf the course from its start"); return; }
		as_nrows = SV_TASAutoRead(e.as_file);
		if (as_nrows < 2) { SV_TASAutoStop(e, "the guide run cannot be read"); return; }
		if (!SV_TASAutoCourse(e, e.as_ctrack, e.as_cleg)) { e.as_on = 0; return; }
		as_n = e.as_cof;        // the saved plan (SV_TASAutoNotes), not a new one: air points and options made another
		SV_TASAutoPriorLoad(e);
		e.as_saved = e.as_cnext - 1; e.as_swph = 0; e.as_redo = 0; e.as_failat = -1; e.as_failmax = e.as_cnext - 1;
		e.as_backs = 0; e.as_esc = 0;     // its own budgets: a Continue after "stuck" would otherwise stop at once
		if (e.as_backmax < 0) e.as_backmax = max(6, 2 * as_n);
		if (e.as_cnext >= as_n)
		{
			e.as_on = 0;
			SV_TASAutoNote(e, 2, sprintf("the saved run of %s had reached its last stretch: paused there", SV_TASAutoCourseName(e.as_ctrack, e.as_cleg)));
			return;
		}
		e.as_i = e.as_cnext; e.as_try = 0; e.as_tprev = e.as_ctprev; e.as_stage = 1; e.as_finrec = e.run_t_finrec;
		SV_TASAutoNote(e, 1, sprintf("continuing %s from stretch %.0f of %.0f", SV_TASAutoCourseName(e.as_ctrack, e.as_cleg), e.as_i + 1, as_n));
		return;
	}
	if (e.as_on && e.as_stage >= 10 && e.as_stage < 30)
	{	// the start: a step at a time, each once the last has landed
		if (e.run_tas_pending || e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING) return;
		if (!e.run_tas_paused || (!e.taslg_on && !e.as_nolegal)) { SV_TASAutoStop(e, "the start ended (TAS play, a move, a respawn)"); return; }
		if (e.as_stage == 14)
		{	// to the guide's standstill: walk (slower within 48 u), let friction stop the body short of it, again until
			// within 16 u and still; 900 ticks at most, then the steering start
			if (e.run_t_state == TS_RUNNING) { SV_TASAutoStop(e, "walking to the guide's start left the box"); return; }
			rd = vlen([as_rows[e.as_ri*7+1] - e.origin_x, as_rows[e.as_ri*7+2] - e.origin_y, 0]);
			t = vlen([e.velocity_x, e.velocity_y, 0]);
			if (rd <= 16 && t < 1)
			{
				e.as_stage = 13; e.as_ri = e.as_ri + 1; e.as_sn = 0;
				SV_TASAutoNote(e, 1, sprintf("start: the guide's own prestrafe from where it stood (%.0f u from here)", rd));
				return;
			}
			if (e.as_sn >= 900)
			{
				e.as_ri = -1; e.as_stage = 10; e.as_sn = 0;
				SV_TASAutoNote(e, 1, "start: could not reach where the guide stood; steering instead");
				return;
			}
			best = vectoyaw([as_rows[e.as_ri*7+1] - e.origin_x, as_rows[e.as_ri*7+2] - e.origin_y, 0]);
			best = best - 360 * floor((best + 180) / 360);
			d = (rd <= t / max(1, cvar("sv_friction")) + 12) ? 0 : ((rd < 48) ? 100 : 400);
			argc_pl = tokenize(sprintf("tas next manual %.0f 0 0 %.4f 0 2", d, best));
			SV_TASPlanCommand(e, argc_pl);
			e.as_sn = e.as_sn + 2;
			return;
		}
		if (e.as_stage == 13)
		{	// a guide row a tick, as a manual step (its jump read from the physics: KSF button rows miss scroll jumps),
			// until the clock has started and the body is 4 rows past the guide's first; then the run's own handover below
			if (e.run_t_state == TS_RUNNING && e.as_ri > as_r0 + 4) { e.as_stage = 10; e.as_sn = 1; return; }
			if (e.as_ri >= as_nrows || e.as_ri > as_r0 + 120)
				{ SV_TASAutoStop(e, "the guide's own start did not leave the box from here"); return; }
			i = e.as_ri;
			t = (as_rows[i*7+6] - as_rows[i*7-1] > 150 && fabs(as_rows[i*7-1]) < 1) ? 1 : 0;
			best = as_bin[i*4+3] - 360 * floor((as_bin[i*4+3] + 180) / 360);
			argc_pl = tokenize(sprintf("tas next manual %.0f %.0f %.4f %.4f %.0f 1", as_bin[i*4], as_bin[i*4+1], as_bin[i*4+2], best, t));
			SV_TASPlanCommand(e, argc_pl);
			e.as_ri = e.as_ri + 1;
			return;
		}
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
			if (!e.as_sn && e.as_ri >= 0 && vlen(e.velocity) < 1)
			{	// landed and still: the guide's own prestrafe, from where it stood -- walked there first when that is on this
				// floor (surf_shape's bonus-1 box places the body 13 u from the guide's exit, ~280 u from its standstill)
				rd = vlen([e.origin_x - as_rows[e.as_ri*7+1], e.origin_y - as_rows[e.as_ri*7+2], 0]);
				if (rd <= 64 && fabs(e.origin_z - as_rows[e.as_ri*7+3]) <= 18)
				{
					e.as_stage = 13; e.as_ri = e.as_ri + 1;
					SV_TASAutoNote(e, 1, sprintf("start: the guide's own prestrafe from where it stood (%.0f u from here)", rd));
					return;
				}
				if (rd <= 1500 && fabs(e.origin_z - as_rows[e.as_ri*7+3]) <= 18)
				{
					e.as_stage = 14; e.as_sn = 0;
					SV_TASAutoNote(e, 1, sprintf("start: walking %.0f u to where the guide stood", rd));
					return;
				}
				e.as_ri = -1;
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
	// P1478: a played line crossed the course's end (zones are positions: no rollout sees them). A stage run's finish
	// hands over to the next stage's arm at once (TS_ARMED, rig t2chain2), so the finish record says it; stage 1 is a
	// full run's first stage (a legal start at the main box arms a full run), so its end is the split into stage 2.
	if (e.as_stage == 3) t = -1;
	else if (e.run_tas_paused && e.as_ctrack >= 0 && e.run_t_finrec != e.as_finrec && e.run_t_finleg == e.as_ctrack * 100 + e.as_cleg + 1)
		t = e.run_t_finticks;
	else if (e.run_tas_paused && e.run_t_state == TS_FINISHED) t = e.run_t_ticks;
	else if (e.run_tas_paused && e.as_ctrack >= 0 && e.as_cleg == 1 && e.run_t_state == TS_RUNNING && e.run_t_seg >= 1) t = e.run_t_split;
	else t = -1;
	if (t >= 0)
	{
		e.as_on = 0;
		if (e.as_stage == 2 && e.as_i >= 1 && as_prpi == e.as_i - 1) SV_TASAutoPriorKeep(e, e.as_i - 1);     // review G
		if (as_prpi == as_n - 1) SV_TASAutoPriorKeep(e, as_n - 1);
		SV_TASAutoNote(e, 2, sprintf("finished %s in %s, %.0f backtracks", SV_TASAutoCourseName(max(0, e.as_ctrack), max(0, e.as_cleg)),
			Time_TickString(t, run_t_tick), e.as_backs));
		return;
	}
	if (!e.run_tas_paused || e.run_t_state != TS_RUNNING)
	{
		SV_TASAutoStop(e, (e.as_stage == 31) ? "the route is done, but the run fell short of the end (a fall or a teleport)" : "TAS play/off, or the run ended");
		return;
	}
	if (e.as_stage == 1) { SV_TASAutoLink(e); return; }
	if (e.as_stage == 31)
	{	// no keys, 4 ticks a step, at most 6 s; the finish check above ends it
		if (e.run_tas_pending || e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING) return;
		if (e.as_sn >= 400)
		{
			e.as_on = 0;
			SV_TASAutoNote(e, 2, sprintf("finished the route (%.0f stretches, %.0f backtracks); the run did not reach the end in 6 s", as_n, e.as_backs));
			return;
		}
		if (!e.as_sn && SV_TASAutoCoastPredict(e) < 0)
		{	// the coast would fall into a teleport that is not the end: the last stretch failed, tried again or backtracked
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f: from where it ends, the run would fall into a teleport, not the end: again", as_n));
			e.as_i = as_n - 1; e.as_tprev = as_wp[as_n - 1];    // the reach had moved it to its own end (rig t2chain9: no rows left)
			e.as_coastf = e.as_coastf + 1; e.as_try = min(e.as_tries, e.as_coastf) - 1;     // counted, so the tries run out
			e.topt_outcome = 1; e.topt_lowneed = e.topt_earlycut = e.topt_trigcut = 0; e.topt_over = e.topt_briefn = 0;
			e.as_stage = 2;
			return;
		}
		SV_TASAutoGuide(e, 0, 0, e.v_angle_y, 0, 4);
		e.as_sn = e.as_sn + 4;
		return;
	}
	if (e.as_stage == 2)
	{
		if (e.as_bmph && SV_TASAutoBeamStep(e)) return;
		if (e.as_swph && SV_TASAutoSweep(e)) return;
		if (e.topt_outcome == 2 && !e.as_bmph && !e.as_route && e.as_i > 0 && as_prpi == e.as_i - 1) SV_TASAutoPriorKeep(e, e.as_i - 1);
		if (e.topt_outcome == 2 && !e.as_bmph) SV_TASAutoBeamStart(e);
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
			if (as_prpi == e.as_i - 1 && e.as_i > 0) SV_TASAutoPriorKeep(e, e.as_i - 1);
			SV_TASAutoPriorPend(e, e.as_i);
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f reached: %.0f u/s at the guide's board height, the guide %.0f", e.as_i + 1, as_rb, as_rf));
			}
			e.as_tprev = t; e.as_i = e.as_i + 1; e.as_try = 0;
			SV_TASAutoSave(e, e.as_i);
			if (e.as_i >= as_n && e.as_ctrack >= 0 && e.as_finish)
			{	// P1478: the course's last target is reached within 400 u of its end: the coast, predicted first, does the rest
				e.as_stage = 31; e.as_sn = 0;
				SV_TASAutoNote(e, 1, "the route is done: coasting into the end");
				return;
			}
			if (e.as_i >= as_n)
			{
				e.as_on = 0;
				SV_TASAutoNote(e, 2, sprintf("finished: %.0f stretches, %.0f backtracks", as_n, e.as_backs));
				return;
			}
			e.as_stage = 1;
			return;
		}
		if (!e.as_route && as_wk[e.as_i] == 1 && (e.topt_briefn >= 10 || (e.topt_over > 100 && e.topt_over < 800)) && as_back[e.as_i] < 400 && SV_TASAutoRule(1))     // a near overshoot, not a line flown past the ramp
		{	// it flew past the point, or its boards skimmed off the face at once (ramp 10: 11-59 a search, the guide rode 58
			// ticks): the next try boards further back along the ramp and higher (Lex: "near the tip and far back"). A wider
			// approach (the lead below) cost ~3% and made more of them skim; aiming lower made 41 into 137 (tfull4s6)
			as_back[e.as_i] = min(400, as_back[e.as_i] + bound(64, e.topt_over, 200)); as_up[e.as_i] = min(144, as_up[e.as_i] + 48);
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f %s: the next try boards %.0f u further back and %.0f u higher",
				e.as_i + 1, (e.topt_over > 100) ? sprintf("overshot its ramp by %.0f u", e.topt_over) : sprintf("had %.0f boards skim off the ramp", e.topt_briefn),
				as_back[e.as_i], as_up[e.as_i]));
		}
		else if (!e.as_route && as_wk[e.as_i] == 1 && e.topt_over > 100 && as_leadmin[e.as_i] < 0.8 && SV_TASAutoRule(2))
		{	// it flew past the ramp's point: the next try comes in wider, along the face (a lead of at least 0.5, 0.7, 0.8).
			// A backtrack to an earlier stretch clears the later ones' leads: kept, they climbed to 0.8 on stretches 6-8
			// over a chain's misses and the wide approaches cost the energy the chain was backtracking for (tfull4s2)
			as_leadmin[e.as_i] = min(0.8, max(0.5, as_leadmin[e.as_i] + 0.2));
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f overshot its ramp by %.0f u: the next try comes in wider (lead %g or more)",
				e.as_i + 1, e.topt_over, as_leadmin[e.as_i]));
		}
		if (!e.as_route && e.topt_earlycut && !as_slack[e.as_i] && SV_TASAutoRule(4))
		{	// the played line left the guide's path within 40 ticks: once, the same stretch with slack round a ride's exit
			// (the next board's line can start wide of farsh's) before any backtrack moves the board before it
			as_slack[e.as_i] = TAS_SLACK;
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f left the guide's path %.0f ticks in: again with %.0f u of slack round it",
				e.as_i + 1, e.topt_earlycut, as_slack[e.as_i]));
			e.as_backhead = -1; e.as_backfail = 0; e.as_goal = as_ws[e.as_i]; e.as_stage = 3;
			return;
		}
		e.as_try = e.as_try + 1;
		e.as_backhead = -1; e.as_backfail = 0;
		if (e.as_try < e.as_tries) { e.as_goal = as_ws[e.as_i]; e.as_stage = 3; return; }
		e.as_failmax = max(e.as_failmax, e.as_i);
		if (!e.as_route && as_need[e.as_i] <= 0)
		{
			as_fsl[e.as_i] = as_lowx[e.as_i]; as_fsm[e.as_i] = e.as_lmused;   // a lead raised since is tried, not skipped (review)
			for (i = 0; i < 6; i = i + 1) as_fso[e.as_i*6 + i] = as_sso[e.as_i*6 + i];
		}
		if (as_need[e.as_i] > 0 && e.as_backs < e.as_backmax && !e.as_route && !as_lost[e.as_i] && SV_TASAutoRule(8))
		if (as_rfs[e.as_i] > 0 && as_rbs[e.as_i] < 0.985 * as_rfs[e.as_i])     // short of energy itself (tfull4s5: 99.0% sent it to stretch 3)
		{	// a bar this stretch could not meet: the energy went earlier (not from a stretch this rule sent the chain to:
			// that cascaded 9 -> 7 -> 5 -> 4 in tfull4s4, 16 backtracks with nothing gained -- it goes on without the bar). Back to the ramp where the share of the guide's
			// energy fell most (0.5% or more, twice a ramp at most), needing the guide's there, 3% a time -- the one-or-two
			// back walk spent tfull4c's backtracks on stretches 6-8, which could not make what stretches 4-5 lost
			d = -1; t = 0; ee = 1;
			for (i = 0; i < max(0, e.as_i - 5); i = i + 1)              // the share before the window
				if (as_wk[i] == 1 && as_rbs[i] > 0 && as_rfs[i] > 0) ee = as_rbs[i] / as_rfs[i];
			for (i = max(0, e.as_i - 5); i < e.as_i; i = i + 1)        // the last five: further back than that is a restart
			{
				if (as_wk[i] != 1 || as_rbs[i] <= 0 || as_rfs[i] <= 0) continue;
				s = as_rbs[i] / as_rfs[i];
				if (ee - s > t && as_lost[i] < 2) { t = ee - s; d = i; }
				ee = s;
			}
			if (d >= 0 && t >= 0.005)
			{
				t = e.as_i; as_lost[d] = as_lost[d] + 1;
				e.as_backs = e.as_backs + 1; e.as_i = d; e.as_try = 0;
				for (i = d + 1; i < as_n; i = i + 1) as_need[i] = as_leadmin[i] = as_back[i] = as_up[i] = 0;
				as_need[d] = max(as_rbs[d] * 1.0025, min(as_rfs[d] * 0.995, as_rbs[d] * 1.03)); as_fresh[d] = 1;
				e.as_tprev = as_wp[d]; e.as_goal = as_ws[d]; e.as_stage = 3;
				SV_TASAutoNote(e, 1, sprintf("stretch %.0f could not beat its bar: the energy went at stretch %.0f (%.1f%% of the guide's): backtrack %.0f there, needing %.0f u/s",
					t + 1, d + 1, 100 * as_rbs[d] / as_rfs[d], e.as_backs, as_need[d]));
				return;
			}
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
		if (e.as_backs < e.as_backmax && e.as_i > 0 && e.topt_lowneed > 1 && !e.as_route && SV_TASAutoRule(16))
		{	// a hop's flight came in under its platform: the board feeding the hops again, needing the energy that flight
			// lacked (Lex: min-max a ramp until the energy is high enough; surf_null's second platform 29-41 u under)
			d = e.as_i;
			for (t = e.as_i - 1; t > 0 && as_wk[t] != 1; t = t - 1) ;
			if (as_wk[t] == 1 && as_rbs[t] > 0)
			{
				e.as_backs = e.as_backs + 1; e.as_i = t; e.as_try = 0;
				for (i = t + 1; i < as_n; i = i + 1) as_need[i] = as_leadmin[i] = as_back[i] = as_up[i] = 0;
				as_need[t] = max(as_need[t], as_rbs[t] * min(1.08, e.topt_lowneed)); as_fresh[t] = 1;
				e.as_tprev = as_wp[t]; e.as_goal = as_ws[t]; e.as_stage = 3;
				SV_TASAutoNote(e, 1, sprintf("stretch %.0f came in under its platform: backtrack %.0f to stretch %.0f, needing %.0f u/s (it had %.0f)",
					d + 1, e.as_backs, t + 1, as_need[t], as_rbs[t]));
				return;
			}
		}
		if (e.as_backs < e.as_backmax && e.as_i > 0 && (e.topt_earlycut || e.topt_trigcut) && !e.as_route && SV_TASAutoRule(32))
		if (as_wk[e.as_i - 1] == 1 && as_lowx[e.as_i - 1] < 8)     // nested: && reads both sides, as_wk[-1] on stretch 1 (review)
		{	// it left farsh's path within 40 ticks (TOPT_EARLYCUT): the board before handed over the wrong place, so that board again
			// nearer farsh's point and with no speed bar -- the bar made a retry board lower still (surf_null ramp 9 for 10,
			// 280-333 u under; Lex: the top keeps the height that flight needs)
			e.as_backs = e.as_backs + 1; e.as_i = e.as_i - 1; e.as_try = 0;
			as_lowx[e.as_i] = as_lowx[e.as_i] ? as_lowx[e.as_i] * 2 : (e.as_low ? 4 : 2); as_fresh[e.as_i] = 1;
			for (i = e.as_i; i < as_n; i = i + 1)
			{
				if (e.topt_trigcut <= TOPT_EARLYCUT || i > e.as_i) as_need[i] = 0;    // a late fall keeps the board's speed bar (review F)
				if (i > e.as_i) as_leadmin[i] = as_back[i] = as_up[i] = 0;
			}
			e.as_tprev = as_wp[e.as_i]; e.as_goal = as_ws[e.as_i]; e.as_stage = 3;
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f %s %.0f ticks in, from where the board before put it: backtrack %.0f to stretch %.0f, boarding nearer the guide's point (low %g)",
				e.as_i + 2, e.topt_earlycut ? "left the guide's path" : "fell into a trigger", e.topt_earlycut ? e.topt_earlycut : e.topt_trigcut,
				e.as_backs, e.as_i + 1, 0.25 * as_lowx[e.as_i]));
			return;
		}
		if (e.as_backs < e.as_backmax && e.as_i > 0 && !e.as_route && SV_TASAutoRule(64))
		if (as_wk[e.as_i - 1] == 2)     // nested: as_wk[-1] on stretch 1
		{	// only hops back to the ramp before them: a hop carries what it is handed (one state, one line), so back to that
			// ramp needing the guide's energy there -- surf_null's last flight: from farsh's state the hops carried
			// 3093/3101 and it finished; from the chain's 3059/3064 every line fell short, and one-at-a-time backtracks
			// replayed the hops. A second time for the same ramp goes to the stretch before it.
			for (t = e.as_i - 1; t > 0 && as_wk[t] == 2; t = t - 1) ;
			if (as_wk[t] == 1 && as_rbs[t] > 0)
			{
				d = e.as_i;
				as_hb[t] = as_hb[t] + 1;
				if (as_hb[t] > 1 && t > 0) t = t - 1;
				e.as_backs = e.as_backs + 1; e.as_i = t; e.as_try = 0;
				for (i = t + 1; i < as_n; i = i + 1) as_need[i] = as_leadmin[i] = as_back[i] = as_up[i] = 0;
				as_need[t] = max(as_need[t], as_rbs[t] * 1.0025);
				if (as_rfs[t] > as_need[t]) as_need[t] = min(as_rfs[t], as_rbs[t] * 1.03);  // the guide's, 3% a time at most
				as_fresh[t] = 1;
				e.as_tprev = as_wp[t]; e.as_goal = as_ws[t]; e.as_stage = 3;
				SV_TASAutoNote(e, 1, sprintf("stretch %.0f fell short after the hops: backtrack %.0f to stretch %.0f, needing %.0f u/s (it had %.0f, the guide %.0f)",
					d + 1, e.as_backs, t + 1, as_need[t], as_rbs[t], as_rfs[t]));
				return;
			}
		}
		if (e.as_backs < e.as_backmax && e.as_i > 0)
		{	// back one stretch, then further each second time the same stretch fails again: one back at a time spent
			// 8 backtracks re-doing the stretch before, when the deficit came two or three earlier (full run, 10 Nov)
			if (e.as_failat == e.as_i) e.as_failn = e.as_failn + 1; else { e.as_failat = e.as_i; e.as_failn = 1; }
			e.as_backs = e.as_backs + 1; e.as_i = max(0, e.as_i - 1 - floor((e.as_failn - 1) / 2)); e.as_try = 0; as_fresh[e.as_i] = 1;
			for (i = e.as_i + 1; i < as_n; i = i + 1) as_need[i] = as_leadmin[i] = as_back[i] = as_up[i] = 0;       // reached from a new state: no bar or raised lead of their own
			if (!e.as_route && as_rbs[e.as_i] > 0) as_need[e.as_i] = max(as_need[e.as_i], as_rbs[e.as_i] * 1.0025);
			// under farsh there: toward 99.5% of his energy, 2% at a time -- a retry from one state replays one line, so
			// 0.25% more was never found and the bar was dropped each time (surf_null: 97.9% at the board before the
			// platforms failed the last ramp three times; from farsh's own state the last three stretches took 20 s)
			if (!e.as_route && as_rfs[e.as_i] * 0.995 > as_rbs[e.as_i] && as_rbs[e.as_i] > 0 && SV_TASAutoRule(128))
				as_need[e.as_i] = max(as_need[e.as_i], min(as_rfs[e.as_i] * 0.995, as_rbs[e.as_i] * 1.02));
			e.as_tprev = as_wp[e.as_i]; e.as_goal = as_ws[e.as_i]; e.as_stage = 3;
			SV_TASAutoNote(e, 1, sprintf("stretch %.0f failed its tries: backtrack %.0f to stretch %.0f", e.as_failat + 1, e.as_backs, e.as_i + 1));
			return;
		}
		if (e.as_ctrack >= 0 && e.as_esc < 2 && !e.as_route)
		{	// P1478 (Lex: a lot of automation): a stuck course chain tries harder by itself before it stops -- more tries and
			// ride knots, then polish and boarding spots -- again from two stretches before the furthest failure, its bars,
			// leads and remembered failures cleared there (surf_shape bonus 1 at Quick: stretch 1 had nothing to back up to)
			e.as_esc = e.as_esc + 1; e.as_coastf = 0; e.as_bmph = 0;
			for (i = 0; i < as_n; i = i + 1) as_bmd[i] = 0;
			e.as_tries = max(e.as_tries, 2 + e.as_esc); e.as_rideknots = 1; e.as_low = 1;
			if (e.as_esc >= 2) { e.as_polish = 1; e.as_spots = 1; }
			t = max(0, e.as_failmax - 2);
			for (i = t; i < as_n; i = i + 1)
			{
				as_need[i] = 0; as_fsl[i] = -1; as_swd[i] = 0; as_leadmin[i] = 0; as_hb[i] = 0; as_fresh[i] = 1; as_slack[i] = 0;
				as_lost[i] = 0; as_back[i] = as_up[i] = 0; as_lowx[i] = 0;
				if (i > t) as_ws[i] = 0;
			}
			SV_TASAutoNote(e, 1, sprintf("trying harder at stretch %.0f of %.0f (step %.0f: %.0f tries%s), again from stretch %.0f",
				e.as_failmax + 1, as_n, e.as_esc, e.as_tries, (e.as_esc >= 2) ? ", polish, five boarding spots" : ", ride knots", t + 1));
			e.as_i = t; e.as_try = 0; e.as_backs = 0; e.as_failat = -1; e.as_failmax = t; e.as_swph = 0;
			e.as_tprev = as_wp[t]; e.as_goal = as_ws[t]; e.as_backhead = -1; e.as_backfail = 0; e.as_stage = 3;
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
	local float i, s, n, st, flip, arm, pl, ct, cl, zg, nct, ncl;
	local string w, path;
	if (argc >= 5 && argv(2) == "continue")
	{
		if (Lobby_Active()) { sprint(e, PRINT_HIGH, "tas autosurf: a local practice tool; not on lobby servers\n"); return; }
		if (e.as_on || e.topt_on || e.tdem_on) { SV_TASAutoNote(e, e.as_on ? 1 : 0, "already running: stop it first"); return; }
		ct = stof(argv(3)); cl = stof(argv(4));
		if (!FS_TASNumber(argv(3)) || !FS_TASNumber(argv(4)) || ct < 0 || ct >= ZONE_MAXTRACKS || ct != floor(ct) || cl < 0 || cl > 64 || cl != floor(cl))
			{ sprint(e, PRINT_HIGH, "tas autosurf continue <track> <leg>: 0 main, k bonus k; 0 the whole track, k stage k\n"); return; }
		if (SV_TASOptBusy(e)) return;
		// the panel's effort as it is now (a Continue after "stuck" is a chance to try harder): flags absent are off
		as_cov = (argc > 5); as_covtries = -1; as_covbacks = -1; as_covflags = 0;
		for (i = 5; i < argc; i = i + 1)
		{
			w = argv(i); n = FS_TASNumber(argv(i + 1)) ? stof(argv(i + 1)) : -1;
			if (w == "tries" && n >= 1 && n <= 10) { as_covtries = rint(n); i = i + 1; }
			else if (w == "backs" && n >= 0 && n <= 200) { as_covbacks = rint(n); i = i + 1; }
			else if (w == "rideknots") as_covflags = as_covflags | 1;
			else if (w == "polish") as_covflags = as_covflags | 2;
			else if (w == "low") as_covflags = as_covflags | 4;
			else if (w == "air") as_covflags = as_covflags | 8;
			else if (w == "wide") as_covflags = as_covflags | 16;
			else if (w == "spots") as_covflags = as_covflags | 32;
			else if (w == "finish") as_covflags = as_covflags | 64;
			else if (w == "beam") as_covflags = as_covflags | 128;
			else { sprint(e, PRINT_HIGH, sprintf("tas autosurf continue: unknown option '%s'\n", w)); return; }
		}
		SV_TASAutoContinue(e, ct, cl);
		return;
	}
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
		if (e.as_ctrack >= 0) if (!SV_TASAutoCourse(e, e.as_ctrack, e.as_cleg)) return;
		for (s = 0; s < as_nrows - 1 && as_rows[s*7] < as_wp[0] - 0.0001; s = s + 1) ;
		SV_TASAutoPlanCopy(0);
		SV_TASAutoPlan(e, s);
		if (n >= as_n) { SV_TASAutoPlanCopy(1); SV_TASAutoNote(e, 0, "the route changed: restart from the start zone"); return; }
		for (i = 0; i <= n; i = i + 1) if (fabs(as_wt[i] - as_rdt[i]) > 0.0001 || as_wk[i] != as_rdk[i]) i = 1000;
		if (i >= 1000) { SV_TASAutoPlanCopy(1); SV_TASAutoNote(e, 0, "the route changed: restart from the start zone"); return; }     // review H
		SV_TASAutoPriorLoad(e);     // stretches after n may have moved: priors re-slotted, or a keep erased a moved ramp's (review I)
		for (i = n; i < as_n; i = i + 1)
		{	// from here on a new attempt: no bars, no "failed from this state", no later stretch's start tick
			as_need[i] = 0; as_fsl[i] = -1; as_swd[i] = 0; as_leadmin[i] = 0; as_hb[i] = 0; as_fresh[i] = 0; as_slack[i] = 0; as_lost[i] = 0; as_back[i] = as_up[i] = 0; as_bmd[i] = 0;
			if (i > n) as_ws[i] = 0;
		}
		if (e.as_backmax < 0) e.as_backmax = max(6, 2 * as_n);
		e.as_redo = n + 1; e.as_swph = 0; e.as_finrec = e.run_t_finrec; e.as_esc = 0; e.as_bmph = 0;
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
		sprint(e, PRINT_HIGH, "tas autosurf <demo.rec> [tube R] [look N] [tries N] [backs N] [pace X] [emin F] [nohop] [join] [rideknots] [polish] [low] [finish] [course T L] [start [zone N] [sg N] | onjump | onexit] | continue T L | stop | status | startpause\n");
		return;
	}
	if (e.as_on || e.topt_on || e.tdem_on) { SV_TASAutoNote(e, e.as_on ? 1 : 0, "already running: stop it first"); return; }
	if (path != "route" && !SV_TASDemoPathOK(path)) { sprint(e, PRINT_HIGH, "tas autosurf: a .rec under data/ or cfg/ksfreplays/ (or route)\n"); return; }
	if (SV_TASOptBusy(e)) return;
	SV_TASAutoOptSave(e);
	st = 0; flip = 0; arm = 0; pl = 0; ct = -1; cl = 0; zg = 0; e.as_szone = 0; e.as_sg = 900; e.as_sy = 0; e.as_sside = -1;
	e.as_tube = 300; e.as_look = 100; e.as_tries = 2; e.as_backmax = -1; e.as_hop = 1; e.as_finish = 0; e.as_pace = 1; e.as_emin = 0.95; e.as_join = 0; e.as_rideknots = 0; e.as_polish = 0; e.as_low = 0; e.as_apex = 0; e.as_air = 0; e.as_wide = 0; e.as_spots = 0; e.as_beam = 0;
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
		else if (w == "beam") e.as_beam = 1;            // P1483
		else if (w == "start") st = 1;
		else if (w == "plan") pl = 1;
		else if (w == "zone" && n >= 0 && n < 64 && n == floor(n)) { e.as_szone = n; zg = 1; i = i + 1; }
		else if (w == "course" && n >= 0 && n < ZONE_MAXTRACKS && n == floor(n) && FS_TASNumber(argv(i + 2)))
		{	// P1478: the course picked in the panel (track, leg); the guide must be a run of it
			cl = stof(argv(i + 2));
			if (cl < 0 || cl > 64 || cl != floor(cl)) { sprint(e, PRINT_HIGH, "tas autosurf: course <track> <leg>\n"); SV_TASAutoOptRestore(e); return; }
			ct = n; i = i + 2;
		}
		else if (w == "sg" && n >= 6 && n <= 2000 && n == floor(n)) { e.as_sg = n; i = i + 1; }   // the most ground ticks before the jump
		else if (w == "onjump") arm = 2;
		else if (w == "onexit") arm = 1;
		else if (w == "finish") e.as_finish = 1;
		else { sprint(e, PRINT_HIGH, sprintf("tas autosurf: unknown option '%s'\n", w)); SV_TASAutoOptRestore(e); return; }
	}
	// `start` begins in the start box, before the running attempt the tools need (it is a legal start's own path)
	if (pl) { if (Lobby_Active()) { sprint(e, PRINT_HIGH, "tas autosurf: a local practice tool; not on lobby servers\n"); SV_TASAutoOptRestore(e); return; } }
	else if (st || arm) { if (Lobby_Active() || !e.run_tas_rwcap) { SV_TASToolGate(e, "autosurf"); return; } }
	else if (!pl && !SV_TASToolGate(e, "autosurf")) { SV_TASAutoNote(e, 0, "TAS is not paused in a run here: use Restart from the start zone"); return; }
	if (ct >= 0 && (zg || arm)) { sprint(e, PRINT_HIGH, "tas autosurf: `course` picks the start itself; not with zone, onjump or onexit\n"); SV_TASAutoOptRestore(e); return; }
	if (path == "route")
	{	// the clicked route: no demo, no plan to make; from here (a running attempt, paused)
		if (st || arm) { sprint(e, PRINT_HIGH, "tas autosurf route: from a pause on the route (the start options follow a demo)\n"); return; }
		if (rt_n < 1) { sprint(e, PRINT_HIGH, "tas autosurf route: no points yet -- tas route add, or the tab's Add at crosshair\n"); return; }
		e.as_ctrack = -1; e.as_cleg = 0; e.as_saved = -1; e.as_fromstart = 0;     // no course (review A: an old one finished it at once)
		e.as_cseed = 0; SV_TASAutoRunSalt();
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
		SV_TASAutoOptRestore(e); strunzone(path); return;
	}
	e.as_nolegal = 0; e.as_arm = 0;
	if ((st || arm) && as_nrows < 2) { sprint(e, PRINT_HIGH, "tas autosurf: that demo has no samples to start from\n"); SV_TASAutoOptRestore(e); strunzone(path); return; }
	for (i = 0; i < as_nrows - 1 && as_rows[i*7] < 0; i = i + 1) ;
	e.as_ex = SV_TASAutoRowO(i);
	e.as_exd = normalize([as_rows[i*7+4], as_rows[i*7+5], 0]);
	if (e.as_exd == '0 0 0') e.as_exd = '1 0 0';
	nct = -1; ncl = 0;
	if (!zg && !arm && (st || pl || ct >= 0))
	{	// P1478: a start or preview without `zone`, or a picked course: the course decides the box and the rows. The chain's
		// course is set where it really starts (a refused start left the stopped chain's redo without one: review A)
		if (!SV_TASAutoCourse(e, ct, cl)) { SV_TASAutoOptRestore(e); strunzone(path); return; }
		nct = (ct >= 0) ? ct : max(0, as_dtrack); ncl = (ct >= 0) ? cl : max(0, as_dleg);
		if (zone_count <= 0 && ct < 0) nct = -1;        // a map without zones: no course
		i = as_r0;
	}
	if (arm)
	{
		if (e.run_t_state != TS_ARMED) { sprint(e, PRINT_HIGH, "tas autosurf: onjump / onexit wait in the start box (stand in it, TAS on)\n"); strunzone(path); return; }
		if (e.as_file != "") strunzone(e.as_file);
		e.as_file = path;
		e.as_on = 1; e.as_stage = 20; e.as_arm = arm; e.as_nolegal = 1; e.as_backs = 0; e.as_sair = -1; e.as_sn2 = 0;
		e.as_ctrack = -1; e.as_cleg = 0; e.as_saved = -1; e.as_esc = 0; e.as_fromstart = 0; e.as_cseed = 0;
		SV_TASAutoRunSalt();
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
		e.as_ctrack = nct; e.as_cleg = ncl; e.as_saved = -1; e.as_esc = 0; e.as_keepsaid = 0; e.as_cseed = 0;
		SV_TASAutoRunSalt();
		e.as_ri = (e.as_ctrack >= 0) ? SV_TASAutoRest(e) : -1;      // a `zone` start steers as before
		e.as_fromstart = 1; e.as_savedold = (e.as_ctrack >= 0) ? SV_TASAutoSavedAt(e) : 0; e.as_savedoldt = as_cnxt;
		if (cvar("tas_jargon_fresh"))
			for (i = 0; i < TOPT_MEMN; i = i + 1) { topt_memkey[i*9] = 1000000000; topt_memreach[i] = 0; }
		SV_TASAutoNote(e, 1, (e.as_ctrack >= 0) ? sprintf("start of %s: prestrafe toward the guide's exit line, then one jump", SV_TASAutoCourseName(e.as_ctrack, e.as_cleg))
			: "start: prestrafe toward the demo's exit line, then one jump");
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
				WriteByte(MSG_MULTICAST, (as_wk[n] == 5 && as_wl[n] < 0) ? 6 : as_wk[n]); WriteFloat(MSG_MULTICAST, as_wt[n]);
				WriteFloat(MSG_MULTICAST, as_wo[n*3]); WriteFloat(MSG_MULTICAST, as_wo[n*3+1]); WriteFloat(MSG_MULTICAST, as_wo[n*3+2]);
				WriteShort(MSG_MULTICAST, rint(as_wn[n*3] * 30000)); WriteShort(MSG_MULTICAST, rint(as_wn[n*3+1] * 30000));
				WriteShort(MSG_MULTICAST, rint(as_wn[n*3+2] * 30000));
			}
			msg_entity = e; multicast(e.origin, MULTICAST_ONE_R);
		}
		SV_TASAutoNote(e, 0, (as_n >= TAS_ASMAX) ? sprintf("route: the first %.0f points of a longer course (surf it stage by stage)", as_n)
			: sprintf("route: %.0f points from the guide run", as_n));
		SV_TASAutoOptRestore(e);
		strunzone(path);
		return;
	}
	s = SV_TASAutoPlan(e, -1);
	if (s < 0) { SV_TASAutoNote(e, 0, "you are not on the guide run's route (400 u): restart, or redo from a stretch"); strunzone(path); return; }
	if (as_n < 1) { sprint(e, PRINT_HIGH, "tas autosurf: no ramp, hop or finish ahead on the demo from here\n"); strunzone(path); return; }
	if (e.as_file != "") strunzone(e.as_file);
	e.as_file = path;
	e.as_ctrack = nct; e.as_cleg = ncl; e.as_saved = -1; e.as_esc = 0; e.as_fromstart = 0; e.as_keepsaid = 0; e.as_cseed = 0;
	SV_TASAutoRunSalt();
	e.as_on = 1; e.as_stage = 1; e.as_i = 0; e.as_try = 0; e.as_backs = 0; e.as_tprev = as_rows[s*7]; e.as_failat = -1;
	SV_TASAutoBacks(e);
	SV_TASAutoNote(e, 1, sprintf("%.0f stretches ahead from demo t=%.2f (%.0f u off its route)", as_n, as_rows[s*7], vlen(SV_TASAutoRowO(s) - e.origin)));
};
