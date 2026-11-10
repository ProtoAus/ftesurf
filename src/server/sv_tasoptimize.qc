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
#define TOPT_FOFF  6            // P1449 follow: the view's offset from the velocity, degrees either way
#define TOPT_FFLK  3            // P1449 follow: the flick's added turn, degrees a tick
#define TOPT_FITER 12           // P1449 follow: rollouts to the fixed point (each fixes at least a tick)
#define TOPT_KMAX  16           // P1449 curve: knots at most (a flight's side switches come every 20-30 ticks)
#define TOPT_KDEF  8            // ...by default
#define TOPT_QMAX  120          // P1449 curve: the turn command's range (see SV_TASOptFollow); farsh's rides
                                // reach ~80 (braking turns), the follow optimum on ramp 0 ~130
#define TOPT_CEPOP 20           // P1449 curve: samples a generation
#define TOPT_CEEL  5            // ...the best kept
#define TOPT_CEGEN 30           // ...generations after the seeding grid
#define TOPT_CEMIN 12           // P1449: at least these, then a search ends after TOPT_CESTALL generations without a gain
#define TOPT_CESTALL 8          // over 0.5 (surf_null's searches mostly settled by generation 5-10 and ran 20 more);
                                // a target search only once it has a reach (the pillar stretch's first came at 10-20)
#define TOPT_CEGRID 38          // the seeding grid: 13 constant commands, then 25 two-part ones (q1 then q2,
                                // sides changing included: a flight steers by switching sides)
#define TOPT_FRAMEBUDGET 0.04   // P1449: wall seconds of rollouts per call (a shared server stalls meanwhile)
#define TOPT_EFOLLOW 256        // P1449: tas_rollout row bits (sv_tas_rollout.inc): the engine sets the yaw and
#define TOPT_EPITCHV 512        // side from the velocity each tick (yaw slot = turn command), the pitch too
#define TOPT_DOFF  6            // P1449 curve demo: the yaw correction's range, degrees either way
#define TOPT_DQOFF 30           // ...with the engine following: the command correction's range
#define TOPT_EAIM  1024         // P1449: tas_rollout AIM rows -- a flight steers to the aim point (sv_tas_rollout.inc)
#define TOPT_EWALL 2048         // P1466: tas_rollout reports a wall or ceiling clipped on any tick (out[7] bit 2), rides too
#define TOPT_AIMR  500          // P1449 curve aim: the aim point's offset from the target, units either way (x, y)
#define TOPT_AIMGAIN 10         // ...degrees off the bearing for the hardest speed-keeping turn
#define TOPT_HMAX  768          // P1449: a fast search's horizon (a ramp ride or a flight is ~150 ticks; a link and its lookahead ~600); played
                                // as consecutive TAS_TAPE_MAX tapes

.float topt_on, topt_head, topt_n, topt_dir, topt_yaw0, topt_pitch0;
.float topt_stage;              // 1 go back to the head and stage the tape, 2 the tape is running
.float topt_phase;              // 1 grid, 2 golden, 3 the best, played last
.float topt_k, topt_cand, topt_evals, topt_bestr, topt_bestv, topt_next;
.float topt_lo, topt_hi, topt_a, topt_b, topt_fa, topt_fb, topt_which, topt_iter;
.float topt_backed, topt_wait;  // a back sent and not yet seen to land; when a refused tape gives up
.float topt_rmax;               // the range's top: twice the air-strafe turn asin(30 / speed)
.float topt_mode;               // P1092: 1 board, 2 flick; P1449: 4 zigzag, 8 split
.float topt_bestr2, topt_bests; // P1449 split: the second part's rate (-1 follows the first), where it starts (a fraction)
.float topt_curr2, topt_curs;   // P1449 split: the candidate's
.float topt_bestp, topt_curp;   // P1449: zigzag switch period (ticks): the best so far, the candidate's
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
.float topt_fcut;               // P1443: fast candidates not counted (cut by an entity QC acts on, or stopped)
.vector topt_tgt;               // P1449: the target point (tas target) and its reach radius
.float topt_tgtr, topt_tgton;
.vector topt_tgtn;              // P1449: the face to board there (its plane normal); '0 0 0': any contact or none
.float topt_tgtuse;             // P1449: this search scores by the target (fast with a target set)
float(entity e, string what) SV_TASToolGate;
.float topt_outcome;            // P1449: how the last search ended: 0 running, -1 stopped, 1 played, 2 played to the target
.float as_on, as_stage;        // P1449: a `tas autosurf` chain is running, and its stage (sv_tasautosurf.qc)
void(entity e) SV_TASAutoFrame;
.float topt_candk, topt_candd;  // P1449: the last scored candidate's reach tick and closest distance
.float topt_candw, topt_reachw; // P1449: its wall ticks before the reach (or the scored miss), and the played best's
.float topt_candg;              // P1449: its ground ticks before them (board targets only: a hop's landing is its point)
.float topt_reachk, topt_reachd, topt_reachv;   // P1449: the played best's prediction, the same three
#define TOPT_REACH 100000       // P1449: a reached target scores this + speed/energy at the reach tick
#define TOPT_NEAR  50000        // P1449: a miss scores this - its closest distance
#define TOPT_WEAK  75000        // P1449 `emin`: a reach under the minimum energy scores this + its energy - 3 x the shortfall
                                // (between every reach and every miss; the search treats it as not reached)
#define TOPT_FACEDOT 0.95       // P1449: a contact boards the target's face within ~18 degrees of it: a bent ramp's two faces
                                // sit 11.4 degrees apart (surf_monolith's ramp 2: 0.9797, under the old 0.98); its flat top
                                // (0.72 there) and sides stay out
#define TOPT_WALLPEN 120        // P1449: score lost per tick a wall or ceiling is touched in flight (kind 4): a graze, not a
                                // cut (surf_null board 2: a pillar 18 u off farsh's line cut 400-580 of 638 candidates and
                                // autosurf stuck there after 6 backtracks, 10 Nov); 40 left lines brushing walls 1-18 ticks
#define TOPT_GROUNDPEN 60       // P1449: a board target's score lost per tick on the ground before the reach (surf_null ramp 0's
                                // segments have angled tops, normal z 0.85: a high arrival stood on one; Lex, 10 Nov)
#define TOPT_HOPDIR 20          // P1449: a hop target's score lost per degree off the demo's heading after it
#define TOPT_LOOKW 0.01         // P1449 `look N`: a reach's score per unit of demo route survived after it (a reach scores
                                // sqrt(E + EREF) ~ 5700: 40 u/s at 1800 is ~13; 100 ticks survived ~27 -- at 0.5 survival
                                // swamped energy and boards gave up 50 u/s for it, 9 Nov)
float(entity e, float ran) SV_TASOptTargetScore;
float(entity e, float p) SV_TASOptValue;
.float topt_energy, topt_z0;    // P1443: score energy (the speed it is worth at the start height), start z
float *topt_rows;               // P1443: rollout buffers, TOPT_HMAX rows, allocated once
float *topt_out;
// P1449: the played tape's pitch follows the predicted velocity (Lex: the view looks along the move, up
// or down a ramp). Walk and air flatten the view vectors (pm_source.c PMSrc_WishDir), water and ladders
// do not, so the follow is kept only when a second rollout with it matches the first on every tick.
float topt_pfol[TOPT_HMAX];
float topt_fside[TOPT_HMAX];    // P1449 follow/curve: the side each tick strafes (1 left, -1 right)
float *topt_out0;
.float topt_pfon;               // this candidate's rows use topt_pfol
.float topt_pfoff;              // `fixedpitch`: the view holds the start's pitch
.float topt_play;               // P1449: the ticks the tape plays (a reached target ends it on the reach tick)
.float topt_tat, topt_chunk;    // P1449: ticks of it played so far, and the tape in flight
// P1449 curve: a turn command through topt_kn knots spread over the horizon (SV_TASOptFollow), all
// searched together by a cross-entropy evolution strategy: sample around a mean, keep the best quarter,
// move the mean and spread toward them (a grid of constant commands seeds it).
float topt_kcur[TOPT_KMAX];     // the candidate rolled (at play, the best)
float topt_kbest[TOPT_KMAX];
float topt_kmean[TOPT_KMAX];
float topt_ksig[TOPT_KMAX];
float topt_kpop[TOPT_CEPOP * TOPT_KMAX];
float topt_kval[TOPT_CEPOP];
float topt_kel[TOPT_CEPOP];      // the generation's elite marks
.float topt_kn;                 // knots (0: not a curve)
.float topt_kseedn;             // P1449: `tas seed` knots waiting for the next curve search (0 none)
// P1449 curve demo: a recording's rows (`tas demorows`) the search corrects -- its keys, pitch and jumps kept,
// its yaw plus the curve -- so a human's line is the first candidate and only a better one replaces it.
float topt_drow[TOPT_HMAX * 5];  // fwd, side, pitch, yaw (degrees), buttons
float topt_dq[TOPT_HMAX];         // the row's turn command (SV_TASOptFollow's q) against the velocity before it
float topt_dmap[TOPT_HMAX];       // demo search: the demo row each tick takes its keys from (SV_TASOptDemoMap)
float topt_ride[TOPT_HMAX];       // curve search without a demo: a ride tick's side into its ramp (+1 left, -1 right, 0 none)
// tick i's contact normal facing up: the engine counts a ramp by fabs(nz) (pm_source.c, a displacement's winding can
// face down) and passes the normal as wound (review 8-9)
vector(float i) SV_TASOptFaceUp =
{
	local vector n;
	n = [topt_out[i*13+9], topt_out[i*13+10], topt_out[i*13+11]];
	return (n_z < 0) ? -n : n;
};
// and against the target's face, which the same traces give as wound (review 10)
float(entity e, float i) SV_TASOptFaceDot =
{
	local vector t;
	t = e.topt_tgtn;
	if (t_z < 0) t = -t;
	return SV_TASOptFaceUp(i) * t;
};
.float topt_dn;
float topt_dpos[TOPT_HMAX * 3]; // the rows' origins (each after its tick), for `tube`
.float topt_tube, topt_tubeout; // P1449 `tube R`: candidates stay within R of that path; how many left it
.float topt_wallhit;            // P1449: fast candidates cut at a wall touched in flight (SV_TASOptLimit)
float topt_dlen[TOPT_HMAX];     // the demo path's length from its first row to each row
.float topt_tgtj;               // the row nearest the target (tube searches)
.float topt_hop;                // P1449 `demo hop`: every row holds jump -- pm_autobunny hops a platform
                                // landing; a KSF demo's button rows miss scroll jumps (farsh's surf_null
                                // platform hop at 17.5 s: +284 u/s up, no jump bit) and surf ramps are
                                // too steep to jump from, so holding it costs a ride nothing
.float topt_tubebest, topt_tubebk;  // a candidate's least path still to go (SV_TASOptTubeIn) and its tick
.float topt_tubejend;           // the demo row its last checked tick matched
.float topt_look;               // P1449 `look N`: ticks of the demo's route a reach is scored on surviving
.float topt_emin, topt_weakn;   // P1449 `emin X`: the least energy a reach counts at (internal units; 0 off), weak reaches seen
// P1449 `low W`: where a reach boards against the target point on its face -- along the ramp's run past it (the
// demo's way) and up the face above it, W a unit off the score; before or below it costs nothing (Lex, 10 Nov: board
// a ramp low and early, on its side; boarding far along ramp 6 left less ride to make ramp 7). topt_bal/bup: the
// last scored reach's offsets (along the run, up the face), topt_rbal/rbup the played one's.
.float topt_low, topt_bal, topt_bup, topt_rbal, topt_rbup;
.float topt_edgeok, topt_edgen;     // P1449: edge-bugged reaches allowed (`edgeok`); how many were not counted
.float topt_candeg, topt_reacheg;   // the last scored candidate edge-bugged; the played one did
void(entity e, float bk) SV_TASOptBoardAt =
{
	local vector n, r, s, b, tv;
	local float j;
	n = e.topt_tgtn;
	if (n_z < 0) n = -n;
	r = normalize([n_y, -n_x, 0]);
	tv = [topt_out[bk*13+3], topt_out[bk*13+4], 0];             // the body's way, without a demo
	if (e.topt_tube > 0 && e.topt_dn >= 3)        // tgtj is this search's only with a tube (a stale demo otherwise: review)
	{
		j = bound(1, e.topt_tgtj, e.topt_dn - 2);
		tv = [topt_dpos[j*3+3] - topt_dpos[j*3-3], topt_dpos[j*3+4] - topt_dpos[j*3-2], 0];
	}
	if (tv * r < 0) r = -r;
	s = normalize('0 0 -1' + n_z * n);                          // down the face
	b = [topt_out[bk*13], topt_out[bk*13+1], topt_out[bk*13+2]] - e.topt_tgt;
	e.topt_bal = b * r; e.topt_bup = -(b * s);
};
.float topt_pace;               // P1449 `pace X`: a reach's score lost per tick it takes (energy alone is nearly flat at
                                // speed -- free fall keeps it -- so a longer arc cost nothing: Lex, 10 Nov), in the score's
                                // own units: with `energy` one is ~3-6 u/s of speed at 1800-1000 u/s (review)
// P1449 lookahead warm start: the played best's correction past its reach, tick by tick, for the next
// demo search that starts there -- its first sample after the demo itself (a board 1 whose lookahead
// survived handed board 2 a search that found only 30 of 638 survivors from scratch, 9 Nov)
float topt_wseed[TOPT_HMAX];
.float topt_wseedn, topt_wseedhead;
.float topt_cande, topt_reache; // P1449: a reach's own energy (the score adds lookahead and heading terms)
.float topt_bestce, topt_bestcd; // P1449 review 3: the best's own reach energy and closest distance (the stop line)
.float topt_cegen;              // P1449: a curve search's generations (TOPT_CEGEN, or `gens N`: autosurf's retries)
float topt_kseed[TOPT_KMAX];
.float topt_kgen, topt_kidx;    // generation (-1 the seeding grid) and sample
.float topt_kprev, topt_kstall;  // the best when it last gained, and generations since
.float topt_kd;                 // P1449: the searched vector: the knots, then (aim) the aim offset x, y
.float topt_efol;               // P1449: this server's tas_rollout takes FOLLOW rows (exact, one rollout)
.float topt_ewall;              // P1466: and reports walls clipped on rides (TOPT_EWALL rows)
// P1466: and takes aimlead -- a searched value after the aim's (index topt_kleadj): how far back along the face the
// flight's lead point sits, 0 straight at the aim (board with a snap) to 1, P1449's 0.5 at the middle (Lex, 10 Nov:
// a long launch past geometry goes straight for the ramp's nearest part once clear; taken wide it was lost)
.float topt_elead, topt_kleadj;
float(entity e) SV_TASOptLead = { return bound(0, 0.5 + 0.5 * topt_kcur[e.topt_kleadj] / TOPT_AIMR, 0.9); };   // the engine's cap
.float topt_cestall;            // P1449 `stall N`: generations without a gain that end a search once it reaches
.float topt_kspan;              // P1449: the ticks the knots spread over (aim: the ride, ~0.45 of the horizon)
// The follow, curve and demo buffers live across frames: one search or demo at a time on a server.
.float tdem_on;                 // P1449: a tas demo is playing (below)
entity topt_busy;
float topt_busyt;
float(entity e) SV_TASOptBusy =
{
	if (topt_busy && topt_busy != e && time - topt_busyt < 1)
	{
		sprint(e, PRINT_HIGH, "tas: another player's optimizer or demo is running; try again when it ends\n");
		return TRUE;
	}
	topt_busy = e; topt_busyt = time;
	return FALSE;
};

// P1092: the numbers searched, in order: 1 rate, 2 boarding offset, 3 flick rate; 0 = done.
float(entity e, float i) SV_TASOptParam1 =
{
	if (e.topt_mode & 4)
	{	// P1449 zigzag: rate, period, [aim, rate, period]
		if (i == 0) return 1;
		if (i == 1) return 4;
		if (e.topt_mode & 1) { if (i == 2) return 2; if (i == 3) return 1; if (i == 4) return 4; }
		return 0;
	}
	if (e.topt_mode & 8)
	{	// P1449 split: first rate, second rate, where the second starts, [board, first, second], [flick]
		if (i == 0) return 1;
		if (i == 1) return 5;
		if (i == 2) return 6;
		i = i - 3;
		if (e.topt_mode & 1) { if (i == 0) return 2; if (i == 1) return 1; if (i == 2) return 5; i = i - 3; }
		if (e.topt_mode & 2) { if (i == 0) return 3; }
		return 0;
	}
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
float(entity e, float p) SV_TASOptLo = { if (p == 4) return 2; if (p == 6) return 0.15;
	if ((e.topt_mode & 16) && (p == 1 || p == 5)) return -TOPT_FOFF; return (p == 2) ? -TOPT_YMAX : 0; };
float(entity e, float p) SV_TASOptHi = { if (p == 2) return TOPT_YMAX; if (p == 4) return 40; if (p == 6) return 0.85;
	if (e.topt_mode & 16) { if (p == 3) return TOPT_FFLK; return TOPT_FOFF; }
	if (p == 3) return TOPT_FMAX; return e.topt_rmax; };
float(entity e, float k) SV_TASOptAimFromK;

// P1097: what is scored. Speed, or with `time` segments reached, the tick the last one opened and
// speed / 10: one segment scores below 2^19, where float32 still tells 0.3 u/s apart.
float(entity e) SV_TASOptSegs =
{
	if (e.run_t_seg <= e.topt_seg0) return 0;
	return e.run_t_seg - e.topt_seg0;
};
// P1443: a state's score for speed or energy. P1449: energy scores against a level TOPT_EREF below
// the start (|v|^2 + 2g(z - z0) + TOPT_EREF, square-rooted), so a loss below the start's energy -- a
// hard board -- still ranks instead of clamping to 0; SV_TASOptEnergyShow turns it back into the
// signed speed it is worth at the start height.
#define TOPT_EREF 32000000      // 2 * 800 * 20000: 20000 u of drop before the sum could go negative
float(entity e, vector org, vector vel) SV_TASOptStateScore =
{
	if (e.topt_energy) return sqrt(max(0, vel * vel + 2 * cvar("sv_gravity") * (org_z - e.topt_z0) + TOPT_EREF));
	return vlen([vel_x, vel_y, 0]);
};
float(entity e, float v) SV_TASOptEnergyShow =
{
	if (!e.topt_energy) return v;
	v = v * v - TOPT_EREF;
	return (v < 0) ? -sqrt(-v) : sqrt(v);
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
	if (!e.topt_obj) return sprintf(e.topt_energy ? "energy %.1f u/s" : "%.1f u/s", SV_TASOptEnergyShow(e, v));
	if (!SV_TASOptSegs(e)) return sprintf("no new stage, %.1f u/s", spd);
	return sprintf("stage +%.0f at tick %.0f, %.1f u/s", SV_TASOptSegs(e), e.run_t_split, spd);
};

string(entity e) SV_TASOptExtra =
{
	local string s;
	local float i;
	s = "";
	if (e.topt_mode & 1) s = sprintf(", board %.2f deg", e.topt_besty);
	if (e.topt_kn)
	{
		s = strcat(s, ", curve");
		for (i = 0; i < e.topt_kn; i = i + 1) s = strcat(s, sprintf(" %.2f", topt_kbest[i]));
		if (e.topt_mode & 128) s = strcat(s, sprintf(", aimed %.0f %.0f u off the target in flight", topt_kbest[e.topt_kn], topt_kbest[e.topt_kn + 1]));
		if (e.topt_mode & 256) s = strcat(s, sprintf(" from tick %.0f", SV_TASOptAimFromK(e, topt_kbest[e.topt_kn + 2])));
		if (e.topt_elead) s = strcat(s, sprintf(", lead %.2f", bound(0, 0.5 + 0.5 * topt_kbest[e.topt_kleadj] / TOPT_AIMR, 0.9)));
		s = strcat(s, (e.topt_mode & 64) ? (e.topt_efol ? " (added to the demo's own turn command each tick, from this run's velocity)"
			: " (degrees added to the demo's yaw, + left; knots over the ticks)")
			: " (turn command: + left, 30 most speed, 60 hardest speed-keeping turn; knots over the ticks)");
	}
	else if (e.topt_mode & 16) s = strcat(s, " (follow: the turn is the view's offset from the velocity, degrees)");
	if (e.topt_mode & 4) s = strcat(s, sprintf(", switching sides every %.0f ticks", floor(e.topt_bestp + 0.5)));
	if ((e.topt_mode & 8) && e.topt_bestr2 >= 0)
		s = strcat(s, sprintf(", then %.3f deg/tick from tick %.0f", e.topt_bestr2,
			bound(1, floor(e.topt_bests * e.topt_n + 0.5), e.topt_n - e.topt_fk) + 1));
	else if (e.topt_mode & 8) s = strcat(s, ", one rate throughout");
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
	e.topt_on = 0; e.topt_outcome = -1;
	sprint(e, PRINT_HIGH, sprintf("tas optimize: stopped after %.0f candidates: %s\n", e.topt_evals, why));
	SV_TASOptRollReport(e);
	if (e.topt_bestv >= 0 && e.topt_obj)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best so far turn %.3f deg/tick%s (not applied)\n", e.topt_bestr, SV_TASOptExtra(e)));
	else if (e.topt_bestv >= TOPT_REACH && e.topt_tgtuse)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best so far turn %.3f deg/tick%s reaches the target, %.1f u/s there (not applied)\n",
			e.topt_bestr, SV_TASOptExtra(e), SV_TASOptEnergyShow(e, e.topt_bestce)));
	else if (e.topt_bestv >= TOPT_WEAK && e.topt_tgtuse)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best so far turn %.3f deg/tick%s reaches the target too slowly, %.1f u/s there (not applied)\n",
			e.topt_bestr, SV_TASOptExtra(e), SV_TASOptEnergyShow(e, e.topt_bestce)));
	else if (e.topt_bestv >= 0 && e.topt_tgtuse)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best so far turn %.3f deg/tick%s misses the target by %.1f u (not applied)\n",
			e.topt_bestr, SV_TASOptExtra(e), e.topt_bestcd));
	else if (e.topt_bestv >= 0)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: best so far turn %.3f deg/tick%s, %.1f u/s (not applied)\n", e.topt_bestr,
			SV_TASOptExtra(e), SV_TASOptEnergyShow(e, e.topt_bestv)));
};

// P1449 zigzag: the side row i strafes to (1 the search's side, -1 the other), swapping every topt_curp ticks.
float(entity e, float i) SV_TASOptSide =
{
	local float k;
	if (e.topt_mode & 16) return topt_fside[i] * e.topt_dir;     // P1449 follow/curve: as rolled
	if (!(e.topt_mode & 4)) return 1;
	k = floor(i / max(2, floor(e.topt_curp + 0.5)));
	return (k & 1) ? -1 : 1;
};

// Row i's yaw: yaw0 + board, then turning r a tick, and over the last topt_fk ticks f a tick instead.
// P1449 zigzag: turning r a tick toward the side strafed, so the heading swings and the path holds.
// P1449 follow: each tick's yaw is the velocity's (before that tick) plus a searched offset, a second
// offset from the split, and the flick's added turn -- the human's line: the view on the velocity, its
// turn slowing as the ramp bends the move (a constant rate leaves it behind, and off the velocity the
// 30 u/s air cap adds nothing or brakes). Solved by rollouts to the fixed point: each pass's velocities
// set the next pass's yaws; the last pass's rows are the ones scored and played (topt_fyaw).
float topt_fyaw[TOPT_HMAX];
float topt_fvy[TOPT_HMAX];
float topt_fvs[TOPT_HMAX];      // curve: the horizontal speed before each tick
float topt_wvy[TOPT_HMAX];      // curve: the best line's velocity yaws and speeds, each candidate's first guess
float topt_wvs[TOPT_HMAX];
float topt_byaw[TOPT_HMAX];     // curve: the best candidate's rows as rolled, which the play replays exactly
float topt_bside[TOPT_HMAX];
.float topt_wok;                // topt_wvy/wvs hold a line for this search
.float topt_bok;                // topt_byaw/bside hold the best's rows

float(entity e, float r, float y, float f, float i) SV_TASOptYaw =
{
	local float yaw, m, P, k, rem, sum;
	if (e.topt_mode & 16) return topt_fyaw[i];
	if (e.topt_mode & 4)
	{
		P = max(2, floor(e.topt_curp + 0.5));
		k = floor(i / P); rem = i - k * P + 1;
		sum = ((k & 1) ? P : 0) + ((k & 1) ? -rem : rem);       // the sides' ticks so far, signed
		yaw = e.topt_yaw0 + e.topt_dir * (y + r * sum);
		return yaw - 360 * floor((yaw + 180) / 360);
	}
	m = e.topt_n - e.topt_fk;                           // the flick's first tick
	if (e.topt_mode & 8)
	{	// P1449 split: r up to the split, the second rate to the flick, then the flick
		k = bound(1, floor(e.topt_curs * e.topt_n + 0.5), m);
		sum = r * min(i + 1, k) + e.topt_curr2 * bound(0, i + 1 - k, m - k) + f * max(0, i + 1 - m);
		yaw = e.topt_yaw0 + e.topt_dir * (y + sum);
	}
	else if (i < m || f == r) yaw = e.topt_yaw0 + e.topt_dir * (y + r * (i + 1));
	else yaw = e.topt_yaw0 + e.topt_dir * (y + r * m + f * (i + 1 - m));
	return yaw - 360 * floor((yaw + 180) / 360);        // SV_TASPWord unwraps only one turn
};

// P1443 review 2: per-command QC state already pending at the head acts on the next real ticks with
// nothing near the body -- an OnJump or OnEndTouch edge of a trigger touched (run_tl*, the triggers'
// touch bits), a delayed output with this player as activator (SV_TrigPending 2), the Monolith B4
// latch. A rollout from such a head is not the real move: refuse (-31 latch, -32 edges/delays).
string(entity t) SV_TASOptRename;
float(entity t) SV_TASOptRenameOnly = { return t == world || SV_TASOptRename(t) != ""; };
float(entity e) SV_TASRollPending =
{
	local entity t;
	local float n;
	local int bit;
	if (e.run_mono_phase || e.vsv_on) return -31;
	if (e.vbsp_grav_trig) return -31;   // a persist-0 trigger_gravity's reset is owed (SV_GravityFrame)
	// P1449: a touch edge owed by a trigger that only renames its toucher is not one the rollout loses:
	// SV_TASOptRoll starts its filter name as the rename (SV_TASOptSimStart). surf_monolith's bonus boards
	// its ramps inside such triggers, and every search after the first was refused (9 Nov).
	if (!SV_TASOptRenameOnly(e.run_tl1) || !SV_TASOptRenameOnly(e.run_tl2) || !SV_TASOptRenameOnly(e.run_tl3) || !SV_TASOptRenameOnly(e.run_tl4)
	    || !SV_TASOptRenameOnly(e.run_tl5) || !SV_TASOptRenameOnly(e.run_tl6) || !SV_TASOptRenameOnly(e.run_tl7) || !SV_TASOptRenameOnly(e.run_tl8))
		return -32;
	n = num_for_edict(e) - 1;           // SV_TrigPending's walk, a rename-only trigger excepted
	bit = 0;
	if (n >= 0 && n < 32) bit = (int)1 << (int)n;
	for (t = nextent(world); t; t = nextent(t))
	{
		if (t.enemy == e && t.classname == "vbsp_iodelay") return -32;
		if (t.vbsp_touch_who == e || ((t.vbsp_touch_in | t.vbsp_touch_seen | t.vbsp_touch_out) & bit))
		if (!SV_TASOptRenameOnly(t)) return -32;
	}
	return 0;
};

// P1443: the candidate's rows through tas_rollout into topt_out. Returns the ticks that count and
// sets topt_rollcut (1 an entity QC acts on ended it, 2 the engine stopped), or SV_TASRollout's
// negative refusal; -20 without the builtin or buffers. Callers check SV_TASRollPending first, once
// per head (it walks every edict).
.float topt_rollcut;
.float topt_rollran;            // the last fast candidate's counted ticks (0 with a cut: a start volume)
// P1449 curve: the knots are a TURN COMMAND q. Its sign picks the strafe side (+ left), and the view
// is set from the velocity so the wish direction's dot with it is 30 - |q|: 0 no acceleration (either
// side, so a sign change is smooth), 30 the most speed (the view on the velocity), 60 the hardest turn
// that keeps speed -- the human flight between ramps (farsh, surf_null: four side switches, the view
// ~0.97 deg off the velocity at 1780 u/s). Source's AirAccelerate: addspeed = 30 - v.wishdir.
float(entity e, float r, float f) SV_TASOptFollow =
{
	local float i, it, ran, k, m, ks, off, nv, d, moved, q, sd, ph, vs, pass, ch;
	local vector rn, rl;
	m = e.topt_n - e.topt_fk;
	ks = bound(1, floor(e.topt_curs * e.topt_n + 0.5), m);
	if (e.topt_kn && e.topt_efol)
	{	// the engine applies the command from each tick's own velocity and writes back what it played. Rolled twice
		// when the first roll rides a ramp: then each ride tick's next row strafes into that ramp (q +-30: the view on
		// the velocity, the wish across it on the ramp's side), as a human holds the key in -- with no demo's keys the
		// knots slid a clicked route's ride off ramp 1 into the teleport under it (rig troute1, 10 Nov). Rolled again
		// while the ride grows (4 rolls at most): held in, it rides past where the first roll slid off (review 8)
		for (i = 0; i < e.topt_n; i = i + 1) topt_ride[i] = 0;
		ran = -1;
		for (pass = 0; pass < 4; pass = pass + 1)
		{
		for (i = 0; i < e.topt_n; i = i + 1)
		{
			d = min(i, e.topt_kspan - 1) * (e.topt_kn - 1) / max(1, e.topt_kspan - 1); k = floor(d);   // aim: the knots cover the ride
			q = (k >= e.topt_kn - 1) ? topt_kcur[e.topt_kn - 1] : topt_kcur[k] + (d - k) * (topt_kcur[k + 1] - topt_kcur[k]);
			if (topt_ride[i]) q = 30 * topt_ride[i];
			topt_rows[i*7] = 0; topt_rows[i*7+1] = -450 * e.topt_dir; topt_rows[i*7+2] = 0;
			topt_rows[i*7+3] = SV_TASPWord(e.topt_pitch0); topt_rows[i*7+4] = bound(-TOPT_QMAX, q, TOPT_QMAX);
			topt_rows[i*7+5] = 0; topt_rows[i*7+6] = TOPT_EFOLLOW + (e.topt_pfoff ? 0 : TOPT_EPITCHV) + ((e.topt_mode & 128) ? TOPT_EAIM : 0) + (e.topt_hop ? 1 : 0)
				+ (e.topt_ewall ? TOPT_EWALL : 0);
		}
		SV_NoColPre(e);
		if ((e.topt_mode & 128) && e.topt_tgtn != '0 0 0' && e.topt_elead)
			ran = tas_rollout(e, topt_rows, e.topt_n, topt_out, e.topt_tgt + [topt_kcur[e.topt_kn], topt_kcur[e.topt_kn + 1], 0], TOPT_AIMGAIN, e.topt_tgtn, SV_TASOptLead(e));
		else if ((e.topt_mode & 128) && e.topt_tgtn != '0 0 0')   // aim at a face: arrive along it (sv_tas_rollout.inc)
			ran = tas_rollout(e, topt_rows, e.topt_n, topt_out, e.topt_tgt + [topt_kcur[e.topt_kn], topt_kcur[e.topt_kn + 1], 0], TOPT_AIMGAIN, e.topt_tgtn);
		else if (e.topt_mode & 128)  // aim: the flight steers to the target moved by the last two searched values
			ran = tas_rollout(e, topt_rows, e.topt_n, topt_out, e.topt_tgt + [topt_kcur[e.topt_kn], topt_kcur[e.topt_kn + 1], 0], TOPT_AIMGAIN);
		else
			ran = tas_rollout(e, topt_rows, e.topt_n, topt_out);
		SV_NoColPost(e);
		if (pass >= 3 || ran < 2) break;
		ch = FALSE;
		for (i = 0; i + 1 < ran; i = i + 1)
			if (topt_out[i*13+8] == 1 && !topt_ride[i + 1])
			{	// a world ramp under this tick: the next row strafes into it (the wish against its horizontal normal;
				// the engine passes a displacement's normal as wound, which can face down: pm_source.c fabs(nz))
				rn = SV_TASOptFaceUp(i); rn_z = 0;
				rl = [-topt_out[i*13+4], topt_out[i*13+3], 0];        // left of the velocity
				topt_ride[i + 1] = (rn * rl < 0) ? 1 : -1;
				ch = TRUE;
			}
		if (!ch) break;
		}
		for (i = 0; i < e.topt_n; i = i + 1)
		{	// past the last tick run the rows were not set: they are not played
			k = min(i, max(0, ran - 1)) * 7;
			topt_fyaw[i] = topt_rows[k+4] * 360 / 65536; topt_fside[i] = (topt_rows[k+1] < 0) ? 1 : -1;
			topt_pfol[i] = topt_rows[k+3] * 360 / 65536;
		}
		e.topt_pfon = !e.topt_pfoff;
		return ran;
	}
	nv = atan2(e.velocity_y, e.velocity_x) * DEG_PER_RAD;
	vs = vlen([e.velocity_x, e.velocity_y, 0]);
	if (e.topt_kn && e.topt_phase == 3 && e.topt_bok)
	{	// the play: the best's own rows, one rollout -- what the search scored, exactly
		for (i = 0; i < e.topt_n; i = i + 1)
		{
			topt_fyaw[i] = topt_byaw[i]; topt_fside[i] = topt_bside[i];
			topt_rows[i*7] = 0; topt_rows[i*7+1] = -450 * topt_bside[i]; topt_rows[i*7+2] = 0;
			topt_rows[i*7+3] = SV_TASPWord(e.topt_pfon ? topt_pfol[i] : e.topt_pitch0); topt_rows[i*7+4] = SV_TASPWord(topt_byaw[i]);
			topt_rows[i*7+5] = 0; topt_rows[i*7+6] = 0;
		}
		SV_NoColPre(e);
		ran = tas_rollout(e, topt_rows, e.topt_n, topt_out);
		SV_NoColPost(e);
		return ran;
	}
	for (i = 0; i < e.topt_n; i = i + 1)
	{	// curve: start from the best line so far (neighbours converge in a few passes)
		if (FALSE && e.topt_kn && e.topt_wok) { topt_fvy[i] = topt_wvy[i]; topt_fvs[i] = topt_wvs[i]; }   // off: the passes do not converge on a ramp, so a warm start made the same knots score differently
		else { topt_fvy[i] = nv; topt_fvs[i] = vs; }
	}
	ran = -1;
	for (it = 0; it < TOPT_FITER; it = it + 1)
	{
		for (i = 0; i < e.topt_n; i = i + 1)
		{
			if (e.topt_kn)
			{	// the command on the line through the knots
				d = i * (e.topt_kn - 1) / max(1, e.topt_n - 1); k = floor(d);
				q = (k >= e.topt_kn - 1) ? topt_kcur[e.topt_kn - 1] : topt_kcur[k] + (d - k) * (topt_kcur[k + 1] - topt_kcur[k]);
				sd = (q > 0 || (q == 0 && e.topt_dir > 0)) ? 1 : -1;
				ph = acos(bound(-1, (30 - fabs(q)) / max(1, topt_fvs[i]), 1)) * DEG_PER_RAD;   // wish dir from the velocity
				nv = topt_fvy[i] + sd * (ph - 90);                                              // the view, 90 off the wish dir
			}
			else
			{
				off = ((e.topt_mode & 8) && i >= ks) ? e.topt_curr2 : r;
				if (i >= m) off = off + f * (i + 1 - m);
				sd = e.topt_dir;
				nv = topt_fvy[i] + e.topt_dir * off;
			}
			topt_fside[i] = sd;
			topt_fyaw[i] = nv - 360 * floor((nv + 180) / 360);
			topt_rows[i*7] = 0; topt_rows[i*7+1] = -450 * sd; topt_rows[i*7+2] = 0;
			topt_rows[i*7+3] = SV_TASPWord(e.topt_pfon ? topt_pfol[i] : e.topt_pitch0); topt_rows[i*7+4] = SV_TASPWord(topt_fyaw[i]);
			topt_rows[i*7+5] = 0; topt_rows[i*7+6] = 0;
		}
		SV_NoColPre(e);
		ran = tas_rollout(e, topt_rows, e.topt_n, topt_out);
		SV_NoColPost(e);
		if (ran < 1) return ran;
		moved = 0;
		for (i = 1; i < e.topt_n; i = i + 1)
		{	// tick i turns on the velocity after tick i-1 (past a stop, the last one)
			k = min(i, ran) - 1;
			nv = atan2(topt_out[k*13+4], topt_out[k*13+3]) * DEG_PER_RAD;
			d = nv - topt_fvy[i];
			moved = max(moved, fabs(d - 360 * floor((d + 180) / 360)));
			topt_fvy[i] = nv;
			vs = vlen([topt_out[k*13+3], topt_out[k*13+4], 0]);
			moved = max(moved, fabs(vs - topt_fvs[i]) * 0.01);
			topt_fvs[i] = vs;
		}
		if (moved < 0.0005) return ran;
	}
	return ran;
};

// P1449 `demo aim late`: the tick the aim takes over -- 0.6 of the horizon (the demo's board is near 0.8:
// the driver gives it 1.25x + 10) moved +-50 ticks by the searched value, so the demo's own strafes fly
// the flight and the aim only the approach onto the face (the whole-flight aim gave up their gain).
// With a tube the demo's own row nearest the target is known: 0.75 of it, so a lookahead's longer
// horizon does not move the aim (0.75 * (0.8 n - 8) ~ 0.6 n without one).
// With a tube, 0.4 to 1.0 of the way to the target's row (0.75 +- 0.05 before: surf_null ramp 6 -> 7, the
// aim could not begin the long left arc until after farsh's right tap, and a faster line overshot ramp 7).
float(entity e, float k) SV_TASOptAimFromK =
{
	if (e.topt_tube > 0 && e.topt_tgtj > 0) return rint(e.topt_tgtj * (0.7 + 0.3 * bound(-1, k / TOPT_AIMR, 1)));
	return rint(0.6 * e.topt_n + k * 0.1);
};
float(entity e) SV_TASOptAimFrom = { return SV_TASOptAimFromK(e, topt_kcur[e.topt_kn + 2]); };

// P1449: topt_dmap from a rollout of `ran` ticks: tick i takes the keys of the demo row after the one
// nearest where tick i starts (the pointer only moves on, as `tube`'s); past the rollout, one row a tick.
// TRUE if some tick's row moved more than 2 from the clock's (closer, the second roll changes little and
// costs a whole rollout). By the clock, a line faster than the demo's kept its strafe side past the ramp's end
// and ducked late under a ceiling (surf_null ramps 6 and 7, Lex 10 Nov).
float(entity e, float ran) SV_TASOptDemoMap =
{
	local float i, j, m, d, d2, ch;
	local vector p;
	j = 0; ch = FALSE;
	for (i = 1; i < e.topt_n; i = i + 1)
	{
		if (i - 1 < ran)
		{
			p = [topt_out[(i-1)*13], topt_out[(i-1)*13+1], topt_out[(i-1)*13+2]];
			d = vlen(p - [topt_dpos[j*3], topt_dpos[j*3+1], topt_dpos[j*3+2]]);
			while (j + 1 < e.topt_dn)
			{
				d2 = vlen(p - [topt_dpos[j*3+3], topt_dpos[j*3+4], topt_dpos[j*3+5]]);
				if (d2 > d) break;
				d = d2; j = j + 1;
			}
			m = min(j + 1, e.topt_dn - 1);
		}
		else
			m = min(topt_dmap[i-1] + 1, e.topt_dn - 1);
		if (fabs(m - topt_dmap[i]) > 2) ch = TRUE;
		topt_dmap[i] = m;
	}
	return ch;
};

// P1449 `kex T`: a demo curve's knots spent where the launch is made -- 60% of them from the stretch's start to tick T
// (the demo's leaving its ramp and a little after: autosurf's `rideknots`), the rest to the target's row, past it
// the last holds. Spread evenly over the horizon (lookahead included) a ride had 3-4 knots of 12, ~50 ticks apart:
// too coarse for a deeper dip or a flick in a ride's last ticks (Lex, 10 Nov).
.float topt_kex, topt_kend;
float(entity e, float i) SV_TASOptKnotD =
{
	local float ka;
	if (e.topt_kex <= 0) return min(i, e.topt_kspan - 1) * (e.topt_kn - 1) / max(1, e.topt_kspan - 1);
	ka = rint(0.6 * (e.topt_kn - 1));
	if (i <= e.topt_kex) return i * ka / e.topt_kex;
	return ka + (min(i, e.topt_kend) - e.topt_kex) * (e.topt_kn - 1 - ka) / max(1, e.topt_kend - e.topt_kex);
};
// and knot j's own tick (the warm seed puts each knot back where SV_TASOptKnotD has it: review 12)
float(entity e, float j) SV_TASOptKnotTick =
{
	local float ka;
	if (e.topt_kex <= 0) return rint(j * (e.topt_kspan - 1) / max(1, e.topt_kn - 1));
	ka = rint(0.6 * (e.topt_kn - 1));
	if (j <= ka) return rint(j * e.topt_kex / ka);
	return rint(e.topt_kex + (j - ka) * (e.topt_kend - e.topt_kex) / max(1, e.topt_kn - 1 - ka));
};

float(entity e) SV_TASOptDemoRoll =
{
	local float i, d, k, off, j, ran, a, pass;
	if (e.topt_efol)
	{	// the demo's own command each tick plus the curve, applied by the engine from the body's velocity:
		// its technique (side switches included) on this run's state, so drift does not compound. Rolled
		// twice: by the clock, then with each tick's keys from where that roll put it (SV_TASOptDemoMap)
		for (i = 0; i < e.topt_n; i = i + 1) topt_dmap[i] = min(i, e.topt_dn - 1);
		ran = -1;
		for (pass = 0; pass < 2; pass = pass + 1)
		{
		for (i = 0; i < e.topt_n; i = i + 1)
		{
			d = SV_TASOptKnotD(e, i); k = floor(d);
			off = (k >= e.topt_kn - 1) ? topt_kcur[e.topt_kn - 1] : topt_kcur[k] + (d - k) * (topt_kcur[k + 1] - topt_kcur[k]);
			j = topt_dmap[i];
			topt_rows[i*7] = topt_drow[j*5]; topt_rows[i*7+1] = topt_drow[j*5+1]; topt_rows[i*7+2] = 0;
			topt_rows[i*7+3] = SV_TASPWord(topt_drow[j*5+2]);
			// the correction changes how hard the demo's side is used, never which side (an added constant
			// flipped its right-hand flight strafes left: Lex, 9 Nov)
			topt_rows[i*7+4] = (topt_dq[j] == 0) ? 0 : ((topt_dq[j] > 0) ? 1 : -1) * bound(0, fabs(topt_dq[j]) + off, TOPT_QMAX);
			topt_rows[i*7+5] = 0;
			// this row aims: only where the demo holds a side key (before the engine's aim takes over, airk < 3,
			// FOLLOW strafes a 0 command at side 0 as 450 left -- review)
			a = ((e.topt_mode & 128) && (!(e.topt_mode & 256) || i >= SV_TASOptAimFrom(e)) && topt_dq[j]);
			topt_rows[i*7+6] = (e.topt_hop ? (topt_drow[j*5+4] | 1) : topt_drow[j*5+4]) + (e.topt_pfoff ? 0 : TOPT_EPITCHV)
				+ ((topt_dq[j] || a) ? TOPT_EFOLLOW : 0) + (a ? TOPT_EAIM : 0) + (e.topt_ewall ? TOPT_EWALL : 0);
			if (!topt_dq[j] && !a)
			{	// no side key held: FOLLOW would strafe (the engine reads side 0 as 450 left) -- the demo's own view (review)
				topt_rows[i*7+1] = 0;
				topt_rows[i*7+4] = SV_TASPWord(topt_drow[j*5+3]);     // off is a command correction here, not degrees
			}
		}
		SV_NoColPre(e);
		if ((e.topt_mode & 128) && e.topt_tgtn != '0 0 0' && e.topt_elead)
			ran = tas_rollout(e, topt_rows, e.topt_n, topt_out, e.topt_tgt + [topt_kcur[e.topt_kn], topt_kcur[e.topt_kn + 1], 0], TOPT_AIMGAIN, e.topt_tgtn, SV_TASOptLead(e));
		else if ((e.topt_mode & 128) && e.topt_tgtn != '0 0 0')   // demo aim at a face: arrive along it
			ran = tas_rollout(e, topt_rows, e.topt_n, topt_out, e.topt_tgt + [topt_kcur[e.topt_kn], topt_kcur[e.topt_kn + 1], 0], TOPT_AIMGAIN, e.topt_tgtn);
		else if (e.topt_mode & 128)  // demo aim: its ride, then the flight steers to the moved target
			ran = tas_rollout(e, topt_rows, e.topt_n, topt_out, e.topt_tgt + [topt_kcur[e.topt_kn], topt_kcur[e.topt_kn + 1], 0], TOPT_AIMGAIN);
		else
			ran = tas_rollout(e, topt_rows, e.topt_n, topt_out);
		SV_NoColPost(e);
		if (ran < 1 || pass > 0 || !SV_TASOptDemoMap(e, ran)) break;
		}
		return ran;
	}
	for (i = 0; i < e.topt_n; i = i + 1)
	{
		d = i * (e.topt_kn - 1) / max(1, e.topt_n - 1); k = floor(d);
		off = (k >= e.topt_kn - 1) ? topt_kcur[e.topt_kn - 1] : topt_kcur[k] + (d - k) * (topt_kcur[k + 1] - topt_kcur[k]);
		j = min(i, e.topt_dn - 1) * 5;
		topt_rows[i*7] = topt_drow[j]; topt_rows[i*7+1] = topt_drow[j+1]; topt_rows[i*7+2] = 0;
		topt_rows[i*7+3] = SV_TASPWord(topt_drow[j+2]);
		off = topt_drow[j+3] + off;
		topt_rows[i*7+4] = SV_TASPWord(off - 360 * floor((off + 180) / 360));
		topt_rows[i*7+5] = 0; topt_rows[i*7+6] = topt_drow[j+4];
	}
	SV_NoColPre(e);
	ran = tas_rollout(e, topt_rows, e.topt_n, topt_out);
	SV_NoColPost(e);
	return ran;
};

// P1449: map sequencing a rollout can follow (surf_monolith's bonus): a trigger whose every output
// renames its toucher (!activator AddOutput targetname X) gives the name it leaves; else "".
float topt_renamenow;            // the last SV_TASOptRename's output fires on touch, not on leaving
string(entity t) SV_TASOptRename =
{
	local entity o;
	local string nm;
	nm = ""; topt_renamenow = FALSE;
	for (o = t.vbsp_io_out; o; o = o.vbsp_io_next)
	{
		if (o.vbsp_io_target != "!activator" || strcasecmp(o.vbsp_io_input, "AddOutput")
		    || substring(o.vbsp_io_param, 0, 11) != "targetname ") return "";
		if (o.vbsp_io_delay > 0) return "";             // a delayed rename: not one to model
		if (o.vbsp_io_name == "onstarttouch" || o.vbsp_io_name == "ontrigger" || o.vbsp_io_name == "onstarttouchall") topt_renamenow = TRUE;
		else if (o.vbsp_io_name != "onendtouch" && o.vbsp_io_name != "onendtouchall") return "";
		nm = substring(o.vbsp_io_param, 11, -1);
	}
	return nm;
};

// P1449: does a volume QC acts on end a rollout? Not a teleport whose filter refuses the toucher under the
// name the rollout has given it so far, and not a rename trigger (its filter passing, the name changes:
// topt_simname). Monolith's 447 teleports send back whoever skipped a ramp; read as fatal, every route
// through them was cut (9 Nov). Overlapping volumes report only one a tick (SV_TASRolloutActor): a
// second, unfiltered one under a passed one would be missed -- the played tape's check would say so.
// A rename lands on leaving (OnEndTouch), and a filtered teleport usually sits inside its rename volume
// (monolith's ramp 1: *130 renames filter_name_2 -> _3, *131 sends back all but _2): the rename waits in
// topt_simpend until a tick touches no volume at all.
string topt_simname, topt_simpend;
float(entity e, entity t) SV_TASOptVolumeEnds =
{
	local string keep, nm;
	local float pass;
	keep = e.targetname; e.targetname = topt_simname;
	pass = SV_PassesFilter(t, e);
	e.targetname = keep;
	// a velocity or progress filter reads the paused body, not this tick: only a name filter's refusal passes
	if (t.classname == "trigger_teleport" && t.filtername != "" && !pass && t.ui_filter.classname == "filter_activator_name") return FALSE;
	if (t.classname == "trigger_multiple" && t.vbsp_io_out)
	{
		nm = SV_TASOptRename(t);
		if (nm != "")
		{
			if (pass && topt_renamenow) topt_simname = nm;      // OnStartTouch / OnTrigger: now
			else if (pass) topt_simpend = nm;                   // OnEndTouch: on leaving
			return FALSE;
		}
	}
	return TRUE;
};

// The filter name a rollout starts with (the body's), and the rename a trigger it is still touching will
// give it on leaving, pending (its own filter passing) -- SV_TASRollPending let the search start there.
void(entity e) SV_TASOptSimStart =
{
	local entity t;
	local string keep;
	local int bit;
	local float n;
	topt_simname = e.targetname; topt_simpend = "";
	n = num_for_edict(e) - 1;
	bit = 0;
	if (n >= 0 && n < 32) bit = (int)1 << (int)n;
	for (t = nextent(world); t; t = nextent(t))
		if (t.classname == "trigger_multiple" && t.vbsp_io_out)
		if (t.vbsp_touch_who == e || ((t.vbsp_touch_in | t.vbsp_touch_seen | t.vbsp_touch_out) & bit))
		if (SV_TASOptRename(t) != "" && !topt_renamenow)      // an OnStartTouch rename already happened
		{
			keep = e.targetname; e.targetname = topt_simname;
			if (SV_PassesFilter(t, e)) topt_simpend = SV_TASOptRename(t);
			e.targetname = keep;
		}
};

float(entity e, float r, float y, float f) SV_TASOptRoll =
{
	local float i, ran, a;
	e.topt_rollcut = 0;
	if (!checkbuiltin(tas_rollout)) return -20;
	if (!topt_rows) topt_rows = (float*)memalloc(TOPT_HMAX * 7 * 4);
	if (!topt_out) topt_out = (float*)memalloc(TOPT_HMAX * 13 * 4);
	if (!topt_rows || !topt_out) return -20;
	e.topt_curp = SV_TASOptValue(e, 4); e.topt_curr2 = SV_TASOptValue(e, 5); e.topt_curs = SV_TASOptValue(e, 6);
	if (e.topt_mode & 64)
		ran = SV_TASOptDemoRoll(e);
	else if (e.topt_mode & 16)
		ran = SV_TASOptFollow(e, r, f);
	else
	{
		for (i = 0; i < e.topt_n; i = i + 1)
		{
			topt_rows[i*7] = 0; topt_rows[i*7+1] = -450 * e.topt_dir * SV_TASOptSide(e, i); topt_rows[i*7+2] = 0;
			topt_rows[i*7+3] = SV_TASPWord(e.topt_pfon ? topt_pfol[i] : e.topt_pitch0); topt_rows[i*7+4] = SV_TASPWord(SV_TASOptYaw(e, r, y, f, i));
			topt_rows[i*7+5] = 0; topt_rows[i*7+6] = 0;
		}
		SV_NoColPre(e);         // P1193's barrier is lent out around a real move; around a rollout too
		ran = tas_rollout(e, topt_rows, e.topt_n, topt_out);
		SV_NoColPost(e);
	}
	if (ran >= 0 && ran < e.topt_n) e.topt_rollcut = 2;
	SV_TASOptSimStart(e);
	for (i = 0; i < ran; i = i + 1)
	{
		a = topt_out[i*13 + 12];
		if (!a && topt_simpend != "") { topt_simname = topt_simpend; topt_simpend = ""; }   // out of every volume
		if (a && !SV_TASOptVolumeEnds(e, edict_num(fabs(a)))) a = 0;
		if (a)
		{	// QC acts on it (a touch, a carrier, a volume) where the rollout cannot: the prediction ends
			// after this tick, or before it when it is the volume the body started in (negative)
			if ((cvar("developer") >= 2 && (!e.topt_fast || e.topt_evals < 64)) || (cvar("developer") && !e.topt_fast && !e.topt_rshort))
				sprint(e, PRINT_HIGH, sprintf("tas optimize: rollout meets %s %s tick %.0f of %.0f\n",
					edict_num(fabs(a)).classname, (a < 0) ? "before" : "at", i + 1, e.topt_n));
			e.topt_rollcut = 1;
			return (a < 0) ? i : i + 1;
		}
	}
	return ran;
};

// The same rows before the tape plays; SV_TASOptFrame checks the tape's landing against the
// prediction's last tick (topt_pn -2: no rollout, else ticks that count, or the refusal).
// P1449: the best's correction (its knots as SV_TASOptDemoRoll spreads them) from the tick after its reach
// to the horizon, for a search that starts at the reach (SV_TASOptCurveNext).
void(entity e) SV_TASOptWarmKeep =
{
	local float i, d, k;
	e.topt_wseedn = 0;
	for (i = e.topt_reachk; i < e.topt_n; i = i + 1)
	{
		d = SV_TASOptKnotD(e, i); k = floor(d);
		topt_wseed[e.topt_wseedn] = (k >= e.topt_kn - 1) ? topt_kbest[e.topt_kn - 1] : topt_kbest[k] + (d - k) * (topt_kbest[k + 1] - topt_kbest[k]);
		e.topt_wseedn = e.topt_wseedn + 1;
	}
	e.topt_wseedhead = e.topt_head + e.topt_reachk;
};

// P1449 (developer 2): the played prediction's ticks to data/topt_dump.txt, appended -- origin,
// velocity, contact kind and normal -- for lining a link up against its demo offline.
void(entity e, float ran) SV_TASOptDump =
{
	local float fh, i;
	fh = fopen("topt_dump.txt", FILE_APPEND);
	if (fh < 0) return;
	fputs(fh, sprintf("link %.0f %.0f %.0f\n", e.topt_head, ran, e.topt_n));
	for (i = 0; i < ran; i = i + 1)
	{	// two writes: sprintf takes 8 arguments at most
		fputs(fh, sprintf("%.0f %.2f %.2f %.2f %.2f %.2f %.2f", e.topt_head + i + 1,
			topt_out[i*13], topt_out[i*13+1], topt_out[i*13+2], topt_out[i*13+3], topt_out[i*13+4], topt_out[i*13+5]));
		fputs(fh, sprintf(" %.0f %.4f %.4f %.4f\n", topt_out[i*13+8], topt_out[i*13+9], topt_out[i*13+10], topt_out[i*13+11]));
	}
	fclose(fh);
};

void(entity e, float ran) SV_TASOptMissWhy;
void(entity e, float r, float y, float f) SV_TASOptPredict =
{
	local float ran, i, ran2, cut, ok, p;
	local vector v;
	e.topt_pn = -2;
	e.topt_pfon = 0;
	e.topt_play = e.topt_n;
	p = e.topt_pitch0;
	if (!checkbuiltin(tas_rollout)) return;
	ran = SV_TASRollPending(e);
	if (!ran) ran = SV_TASOptRoll(e, r, y, f);
	if (ran >= 1 && !e.topt_pfoff && !(e.topt_kn && e.topt_efol) && !(e.topt_mode & 64))
	{
		if (!topt_out0) topt_out0 = (float*)memalloc(TOPT_HMAX * 13 * 4);
		ok = (topt_out0 != 0);
		for (i = 0; i < e.topt_n && ok; i = i + 1)
		{	// the velocity at the end of tick i; past a cut the last one holds
			if (i < ran)
			{
				v = [topt_out[i*13+3], topt_out[i*13+4], topt_out[i*13+5]];
				p = bound(-85, atan2(-v_z, vlen([v_x, v_y, 0])) * DEG_PER_RAD, 85);
			}
			topt_pfol[i] = p;
		}
		for (i = 0; i < ran * 13 && ok; i = i + 1) topt_out0[i] = topt_out[i];
		cut = e.topt_rollcut;
		if (ok)
		{
			e.topt_pfon = 1;
			ran2 = SV_TASOptRoll(e, r, y, f);
			ok = (ran2 == ran && e.topt_rollcut == cut);
			for (i = 0; i < ran && ok; i = i + 1)
				ok = (topt_out[i*13] == topt_out0[i*13] && topt_out[i*13+1] == topt_out0[i*13+1] && topt_out[i*13+2] == topt_out0[i*13+2]
					&& topt_out[i*13+3] == topt_out0[i*13+3] && topt_out[i*13+4] == topt_out0[i*13+4] && topt_out[i*13+5] == topt_out0[i*13+5]);
			if (!ok)
			{	// the pitch reached the move (water, a ladder, or a rounding): the start's pitch, as searched
				e.topt_pfon = 0;
				ran = SV_TASOptRoll(e, r, y, f);
				if (cvar("developer")) sprint(e, PRINT_HIGH, "tas optimize: the view pitch changed the move here; it holds the start's\n");
			}
		}
	}
	e.topt_pn = (ran == -20) ? -2 : ran;
	e.topt_pcut = e.topt_rollcut;
	if (ran >= 0 && e.topt_tgtuse)
	{
		e.topt_reachv = SV_TASOptTargetScore(e, ran);
		e.topt_reachk = e.topt_candk; e.topt_reachd = e.topt_candd; e.topt_reache = e.topt_cande; e.topt_reachw = e.topt_candw;
		e.topt_rbal = e.topt_bal; e.topt_rbup = e.topt_bup; e.topt_reacheg = e.topt_candeg;
		if (e.topt_phase == 3 && e.topt_look > 0 && e.topt_kn && (e.topt_mode & 64) && e.topt_reachv >= TOPT_REACH)
			SV_TASOptWarmKeep(e);
		if (e.topt_phase == 3 && e.topt_reachv < TOPT_WEAK && cvar("developer"))
			SV_TASOptMissWhy(e, ran);
	}
	if (ran >= 1 && cvar("developer") >= 2) SV_TASOptDump(e, ran);
	if (ran >= 1)
	{
		i = (ran - 1) * 13;
		e.topt_po = [topt_out[i], topt_out[i+1], topt_out[i+2]];
		e.topt_pv = [topt_out[i+3], topt_out[i+4], topt_out[i+5]];
	}
};

// P1449 developer: what the played miss did -- its closest tick and where and why it was cut (ramp 6 of surf_null:
// every candidate within 150-220 u of the board point and none boarding, 10 Nov)
.float topt_limwhy;
float(entity e, float ran) SV_TASOptLimit;
void(entity e, float ran) SV_TASOptMissWhy =
{
	local float k, c, i;
	if (ran < 1) { sprint(e, PRINT_HIGH, "tas optimize: miss: no ticks run\n"); return; }
	k = bound(0, e.topt_reachk - 1, ran - 1) * 13;       // reachk counts ticks (TargetScore's bk + 1: review 9)
	sprint(e, PRINT_HIGH, strcat(sprintf("tas optimize: miss: target %v r %.0f n %v; ", e.topt_tgt, e.topt_tgtr, e.topt_tgtn),
		sprintf("closest tick %.0f at %v vel %v contact %.0f n %v\n", k / 13 + 1, [topt_out[k], topt_out[k+1], topt_out[k+2]],
		[topt_out[k+3], topt_out[k+4], topt_out[k+5]], topt_out[k+8], [topt_out[k+9], topt_out[k+10], topt_out[k+11]])));
	c = SV_TASOptLimit(e, (e.topt_rollcut == 1) ? ran - 1 : ran);
	if (c >= 0)
	{
		i = c * 13;
		sprint(e, PRINT_HIGH, sprintf("tas optimize: miss: cut at tick %.0f (%s) at %v vel %v contact %.0f, %.0f u from the target\n", c + 1,
			(e.topt_limwhy == 1) ? "left the tube" : "limit", [topt_out[i], topt_out[i+1], topt_out[i+2]], [topt_out[i+3], topt_out[i+4], topt_out[i+5]],
			topt_out[i+8], vlen([topt_out[i], topt_out[i+1], topt_out[i+2]] - e.topt_tgt)));
	}
	else sprint(e, PRINT_HIGH, sprintf("tas optimize: miss: not cut; %.0f ticks run, cut code %.0f\n", ran, e.topt_rollcut));
	for (i = 0; i < ran; i = i + 1)
		if (topt_out[i*13+8] == 1 && vlen([topt_out[i*13], topt_out[i*13+1], topt_out[i*13+2]] - e.topt_tgt) < 2 * e.topt_tgtr)
		{	// the first ride near the target: the face it met against the one asked for
			sprint(e, PRINT_HIGH, sprintf("tas optimize: miss: first ride near it at tick %.0f, %.0f u off, face %v (dot %.3f)\n", i + 1,
				vlen([topt_out[i*13], topt_out[i*13+1], topt_out[i*13+2]] - e.topt_tgt), SV_TASOptFaceUp(i), SV_TASOptFaceDot(e, i)));
			i = ran;
		}
};

// P1449: the first of `ran` ticks a fast candidate may not have, or -1; why in topt_limwhy.
// 1 (`tube R`): farther than R from the demo's path. The first tick matches the nearest of the first 64
// rows, later ticks search forward from the last match, so a faster line may run ahead of the demo's
// clock (rows ~27 u apart at 1800 u/s: point distance, not segment). Past the last row it is free.
float(entity e, float ran) SV_TASOptTubeIn;
float(entity e, float ran) SV_TASOptLimit =
{
	local float tube;
	e.topt_limwhy = 0;
	tube = (e.topt_tube > 0 && e.topt_dn >= 1) ? SV_TASOptTubeIn(e, ran) : -1;
	if (tube >= 0) { e.topt_limwhy = 1; return tube; }
	return -1;
};

// P1449: ticks of the first n a wall or ceiling is touched in flight (tas_rollout's contact kind 4; an
// engine without it never says so): TOPT_WALLPEN each. A brush 20 u from farsh's line took 10 u/s off
// a flight that scored nothing for it (9 Nov); cutting there instead left board 2 unreachable (10 Nov).
// A wall or ceiling clipped on tick i: in flight (kind 4), or anywhere when the engine reports it (P1466: a ride
// rubbing a side wall said nothing before, and Lex saw the bot rub walls and lose speed, 10 Nov).
float(float i) SV_TASOptWallAt =
{
	if (topt_out[i*13+8] == 4)
	if (!topt_out[i*13+6])
		return TRUE;
	return (topt_out[i*13+7] & 2) ? TRUE : FALSE;
};
// P1449: an edge bug on tick i: a fall (under -250 u/s) whose vertical speed jumps 200 or more toward zero on a
// surface that is not a ramp, and no jump (under 100 after), the body falling again two ticks on (Lex, 10 Nov: after
// ramp 9 the bot made ramp 10 off an edge that removed its fall -- a line that should not count). `edgeok` allows it.
float(float i, float ran) SV_TASOptEdgeAt =
{
	local float vz0, vz1;
	if (i < 1 || i + 2 >= ran) return FALSE;
	vz0 = topt_out[i*13-8]; vz1 = topt_out[i*13+5];
	if (vz0 >= -250 || vz1 < vz0 + 200 || vz1 >= 100) return FALSE;
	// a ramp's clip takes the fall into it: boarding, not an edge -- a curved or seamed ramp's two planes (3) or a
	// brush entity's (2) too (review)
	if (topt_out[i*13+8] >= 1 && topt_out[i*13+8] <= 3) return FALSE;
	if (topt_out[i*13+32]) return FALSE;                // still on the ground two ticks on: a landing
	return topt_out[i*13+31] <= vz1;                    // an edge clipped again two ticks on leaves the same vz
};
float(float n) SV_TASOptWallTicks =
{
	local float i, w;
	w = 0;
	for (i = 0; i < n; i = i + 1)
		if (SV_TASOptWallAt(i)) w = w + 1;
	return w;
};

// Also keeps topt_tubebest: the least, over the ticks it checks, of the demo path still to go to the
// target's row plus the distance off the path -- progress a miss scores by, where the straight
// distance to a far target says nothing (a ride heading away from the next board, every candidate
// cut on it the same distance short: board 4, 9 Nov).
float(entity e, float ran) SV_TASOptTubeIn =
{
	local float i, j, d, d2, onr, iex, dex, allow;
	local vector p;
	j = 0; onr = 0; iex = -1; dex = 0;
	e.topt_tubebest = 1000000; e.topt_tubebk = -1; e.topt_tubejend = 0;
	if (ran < 1) return -1;
	p = [topt_out[0], topt_out[1], topt_out[2]];
	d = vlen(p - [topt_dpos[0], topt_dpos[1], topt_dpos[2]]);
	for (i = 1; i < min(64, e.topt_dn); i = i + 1)
	{
		d2 = vlen(p - [topt_dpos[i*3], topt_dpos[i*3+1], topt_dpos[i*3+2]]);
		if (d2 < d) { d = d2; j = i; }
	}
	for (i = 0; i < ran; i = i + 1)
	{
		p = [topt_out[i*13], topt_out[i*13+1], topt_out[i*13+2]];
		d = vlen(p - [topt_dpos[j*3], topt_dpos[j*3+1], topt_dpos[j*3+2]]);
		while (j + 1 < e.topt_dn)
		{
			d2 = vlen(p - [topt_dpos[j*3+3], topt_dpos[j*3+4], topt_dpos[j*3+5]]);
			if (d2 > d) break;
			d = d2; j = j + 1;
		}
		// the approach (within the target's radius and a tube of it, at least twice the tube) is the target's to
		// judge: a faster line than the demo's comes in wide of it (surf_null board 6: all 639 candidates cut 76-290 u
		// short, 10 Nov); within twice the tube only, a ride on ramp 10's own face 763 u from the board point (inside
		// its 800) was cut on the way in, and the best played to its closest tick (Lex saw it make the ramp: tcomb1)
		// nor a ramp ride, which the ramp steers (a board 346 u off the demo's left the next stretch cut 31 ticks in);
		// and a flight from a ride starts as wide as the ride left it, narrowing to the tube by the target's row (a
		// ramp-1 board at farsh's speed but elsewhere left every ramp-2 candidate cut at the ride's end, tstart11)
		if (topt_out[i*13+8] == 1) onr = 1;
		else if (onr) { onr = 0; iex = i; dex = d; }
		allow = e.topt_tube;
		if (iex >= 0 && dex > allow) allow = allow + (dex - allow) * max(0, 1 - (i - iex) / max(1, e.topt_tgtj - iex));
		if (d > allow && !(e.topt_tgtuse && vlen(p - e.topt_tgt) < max(2 * e.topt_tube, e.topt_tgtr + e.topt_tube)) && topt_out[i*13+8] != 1) return i;
		e.topt_tubejend = j;
		d2 = max(0, topt_dlen[e.topt_tgtj] - topt_dlen[j]) + d;
		if (d2 < e.topt_tubebest) { e.topt_tubebest = d2; e.topt_tubebk = i; }
		if (j + 1 >= e.topt_dn) return -1;
	}
	return -1;
};

// P1449 review: a band's score from its value (energy less penalties, possibly negative): base + x above K, and
// below it squashed into (base, base + K) as K*K / (2K - x) -- monotonic, so penalties still rank, never across a
// band's floor. K 1500: squashed into (base, base + 1) every reach past ~-254 tied at 100000.0 in float32 (review 2).
#define TOPT_BANDK 1500
float(float base, float x) SV_TASOptBand = { return base + ((x >= TOPT_BANDK) ? x : TOPT_BANDK * TOPT_BANDK / (2 * TOPT_BANDK - x)); };

// P1449: topt_out's counted ticks against the target. The reach is the first tick within the radius
// that, when the target names a face, also touches that face (a world-ramp contact whose normal is
// within TOPT_FACEDOT of it: landing on the ramp's flat top beside the point is not boarding it); a
// floor normal ('0 0 1') asks for a hop there instead -- a tick that jumps (vz up > 200 u/s), since
// pm_autobunny jumps on the grounded tick itself (a platform's far end, not the first touch). The
// link ends there (what follows does not count, a reset after it included); reached scores
// TOPT_REACH + the speed/energy there, a miss TOPT_NEAR - its closest distance, and a miss the
// prediction could not follow to the end (cut) -1.
float(entity e, float ran) SV_TASOptTargetScore =
{
	local float i, d, best, bk, hit, lim, tx, dh, eg;
	best = 1000000; bk = -1; hit = FALSE; e.topt_candeg = 0;
	lim = (e.topt_rollcut == 1) ? ran - 1 : ran;        // the tick QC acts on is not one the prediction holds
	tx = SV_TASOptLimit(e, lim);
	if (tx >= 0) lim = tx;                              // a wall touched or the tube left: a cut there
	for (i = 0; i < lim; i = i + 1)
	{
		d = vlen([topt_out[i*13], topt_out[i*13+1], topt_out[i*13+2]] - e.topt_tgt);
		if (d <= e.topt_tgtr)
		if (e.topt_tgtn == '0 0 0' ||
		    (e.topt_tgtn_z >= 0.99 && topt_out[i*13+5] - ((i > 0) ? topt_out[i*13-8] : e.velocity_z) > 200) ||
		    (topt_out[i*13+8] == 1 && SV_TASOptFaceDot(e, i) >= TOPT_FACEDOT))
		{
			best = d; bk = i; hit = TRUE;
			break;
		}
		if (d < best) { best = d; bk = i; }
	}
	if (hit && e.topt_tgtn_z >= 0.99)
	{	// a hop: the link goes on past the jump until the hull stands (farsh ducks over a platform's lip
		// and the next search could not start inside the duck transition: rollouts refuse it, -6)
		for (bk = bk + 2; bk < lim - 1 && (topt_out[bk*13+7] & 1); bk = bk + 1) ;     // bit 1 ducked (bit 2: P1466's wall)
		bk = min(bk, lim - 1);
	}
	if (!hit && e.topt_tube > 0 && e.topt_tubebk >= 0) { best = e.topt_tubebest; bk = e.topt_tubebk; }   // a miss: route progress
	e.topt_candk = bk + 1; e.topt_candd = best;
	e.topt_candw = SV_TASOptWallTicks(bk + 1);
	if (e.topt_candw) e.topt_wallhit = e.topt_wallhit + 1;
	e.topt_candg = 0;
	if (e.topt_tgtn != '0 0 0' && e.topt_tgtn_z < 0.99)
		for (i = 1; i <= bk && i < lim; i = i + 1)
			if (topt_out[i*13+6])
			{	// a hop's landing on the way is no ground: the next tick leaves rising (review 11; nested: || reads both)
				if (i + 1 >= ran) e.topt_candg = e.topt_candg + 1;
				else if (topt_out[i*13+18] - topt_out[i*13+5] <= 200) e.topt_candg = e.topt_candg + 1;
			}
	if (hit)
	{	// review: penalties rank within a band, never across it -- a reach stays above every weak reach, a weak
		// reach above every miss (60 wall or ground ticks used to sink a reach below TOPT_REACH: autosurf then
		// retried a stretch it had made)
		i = bk * 13;
		e.topt_cande = SV_TASOptStateScore(e, [topt_out[i], topt_out[i+1], topt_out[i+2]], [topt_out[i+3], topt_out[i+4], topt_out[i+5]]);
		d = e.topt_cande - TOPT_WALLPEN * e.topt_candw - TOPT_GROUNDPEN * e.topt_candg;
		if (!e.topt_edgeok)
			for (eg = 1; eg <= bk; eg = eg + 1)          // its own counter: i is the reach's offset below (review)
				if (SV_TASOptEdgeAt(eg, ran))
				{
					e.topt_edgen = e.topt_edgen + 1; e.topt_candeg = 1;
					return SV_TASOptBand(TOPT_WEAK, d - 3000);
				}
		if (e.topt_emin > 0 && e.topt_cande < e.topt_emin)
		{	// reached well under the demo's speed there: the stretches after it would not make it (Lex, 10 Nov)
			e.topt_weakn = e.topt_weakn + 1;
			return SV_TASOptBand(TOPT_WEAK, d - 3 * (e.topt_emin - e.topt_cande));
		}
		d = d - e.topt_pace * (bk + 1);
		e.topt_bal = e.topt_bup = 0;
		if ((e.topt_tgtn_x || e.topt_tgtn_y) && e.topt_tgtn_z < 0.99)      // a face, not a hop's floor (as the hop tests)
		{
			SV_TASOptBoardAt(e, bk);
			// past or above the point: W a unit; before or below it, half that beyond 200 u (Lex: boarded way too low on
			// ramp 7, the rest was next to impossible -- a little lower and earlier than farsh is free)
			d = d - e.topt_low * (max(0, e.topt_bal) + max(0, e.topt_bup) + 0.5 * (max(0, -e.topt_bal - 200) + max(0, -e.topt_bup - 200)));
		}
		if (e.topt_tgtn_z >= 0.99 && e.topt_tube > 0 && e.topt_tgtj + 4 < e.topt_dn)
		{	// a hop keeps its horizontal velocity for the next flight: off the demo's heading after its own
			// hop costs TOPT_HOPDIR a degree (10 deg at the surf_null platform hop was 200 u at ramp 4)
			dh = vectoyaw([topt_dpos[e.topt_tgtj*3+12] - topt_dpos[e.topt_tgtj*3+3], topt_dpos[e.topt_tgtj*3+13] - topt_dpos[e.topt_tgtj*3+4], 0])
				- vectoyaw([topt_out[i+3], topt_out[i+4], 0]);
			d = d - TOPT_HOPDIR * fabs(dh - 360 * floor((dh + 180) / 360));
		}
		if (e.topt_look > 0 && e.topt_tube > 0)
		{	// lookahead: the route this candidate goes on along past the reach before a volume QC acts on
			// or the tube ends it (SV_TASOptLimit's scan of the whole rollout), up to `look` ticks
			// of the demo's -- a board whose energy wins and whose next stretch dies loses to one that
			// carries on (surf_null: a fast board 2 cut inside ramp 3's curve; a steep ramp 4 launch)
			dh = topt_dlen[min(e.topt_tgtj + e.topt_look, e.topt_dn - 1)] - topt_dlen[e.topt_tgtj];
			d = d + TOPT_LOOKW * bound(0, topt_dlen[e.topt_tubejend] - topt_dlen[e.topt_tgtj], dh);
			// and its walls: once a wall stopped cutting, a launch whose next 1.4 s ended against the side of the
			// next bhop platform still "survived" the route (surf_null's second platform pair, 10 Nov)
			for (i = bk + 1; i < lim && i <= bk + e.topt_look; i = i + 1)
				if (SV_TASOptWallAt(i)) d = d - TOPT_WALLPEN;
		}
		return SV_TASOptBand(TOPT_REACH, d);
	}
	// P1449: a cut miss still says how near it got (half credit) so a curve search has a slope; its play
	// stops on the closest tick, before the cut. A miss adds its energy there (u/s for u): scored on
	// distance alone, misses traded air-strafe gain for steering and came in low (board 2, 9 Nov).
	if (tx >= 0 && e.topt_limwhy == 1) e.topt_tubeout = e.topt_tubeout + 1;
	if (best >= TOPT_NEAR) return -1;
	i = bk * 13;
	d = TOPT_NEAR - best + SV_TASOptStateScore(e, [topt_out[i], topt_out[i+1], topt_out[i+2]], [topt_out[i+3], topt_out[i+4], topt_out[i+5]])
		- TOPT_WALLPEN * e.topt_candw - TOPT_GROUNDPEN * e.topt_candg;
	return (ran < e.topt_n || e.topt_rollcut == 1 || tx >= 0) ? d * 0.5 : d;
};

// P1443: what an engine refusal (SV_TASRollout's code) means to the player.
string(float why) SV_TASRollWhy =
{
	if (why == -4) return "a movement limit, slide volume or forced duck is in effect here";
	if (why == -6) return "water, a ladder or a duck transition: rollouts cover plain air and ground moves";
	if (why == -7) return "gravity is not the map's default here (rollouts do not follow bank-gravity accounting)";
	if (why == -9) return "a push or conveyor carrier is armed, or the body stands on a moving entity";
	if (why == -3) return "the body is not TAS-paused here (or a movement hold is on)";
	return sprintf("the engine refused the rollout (code %.0f)", why);
};

// P1443 `fast`: a candidate's score from its rollout. -1 when an entity QC acts on (a reset, a
// push) or an engine stop ends it early -- the tape would not land where the rollout says --
// and -2 when it cannot run.
float(entity e, float r, float y, float f) SV_TASOptRollScore =
{
	local float ran, i;
	ran = SV_TASOptRoll(e, r, y, f);
	e.topt_rollran = ran;
	if (ran < 0) { e.topt_rwhy = ran; return -2; }
	if (e.topt_tgtuse) return SV_TASOptTargetScore(e, ran);
	if (ran < e.topt_n || e.topt_rollcut == 1) return -1;   // incl. an entity named on the last tick
	if (SV_TASOptLimit(e, ran) >= 0) { e.topt_tubeout = e.topt_tubeout + 1; return -1; }
	e.topt_candw = SV_TASOptWallTicks(ran);
	if (e.topt_candw) e.topt_wallhit = e.topt_wallhit + 1;
	i = (ran - 1) * 13;
	return SV_TASOptStateScore(e, [topt_out[i], topt_out[i+1], topt_out[i+2]], [topt_out[i+3], topt_out[i+4], topt_out[i+5]])
		- TOPT_WALLPEN * e.topt_candw;
};

// The candidate's inputs onto the native tape (SV_TASOptYaw's yaws, strafing to the turn's side).
float(entity e, float r, float y, float f) SV_TASOptTape =
{
	local float i, tx, ok, c, at;
	if ((e.topt_mode & 80) && e.topt_pn < 1) return FALSE;     // follow/demo play only the rows their prediction rolled
	at = e.topt_tat;
	c = min(TAS_TAPE_MAX, e.topt_play - at);                  // P1449: a long horizon plays in tapes
	if (c < 1) return FALSE;
	if (!tas_tape(e, 2, c, 0, '0 0 0', '0 0 0', 0)) return FALSE;
	tx = tas_tape(e, 3, c, 0, '0 0 0', '0 0 0', 0);
	ok = tx > 0;
	e.topt_curp = SV_TASOptValue(e, 4); e.topt_curr2 = SV_TASOptValue(e, 5); e.topt_curs = SV_TASOptValue(e, 6);
	for (i = 0; i < c && ok; i = i + 1)
		if (e.topt_mode & 64)       // curve demo: topt_rows as the prediction rolled them (no rollout since)
			ok = tas_tape(e, 4, tx, i, [topt_rows[(at+i)*7], topt_rows[(at+i)*7+1], 0],
				[topt_rows[(at+i)*7+3], topt_rows[(at+i)*7+4], 0], topt_rows[(at+i)*7+6]);
		else
			ok = tas_tape(e, 4, tx, i, [0, -450 * e.topt_dir * SV_TASOptSide(e, at + i), 0],
				[SV_TASPWord(e.topt_pfon ? topt_pfol[at + i] : e.topt_pitch0), SV_TASPWord(SV_TASOptYaw(e, r, y, f, at + i)), 0], 0);
	e.topt_chunk = c;
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
	if (p == 4) return e.topt_bestp;
	if (p == 6) return e.topt_bests;
	if (p == 5) return (e.topt_bestr2 < 0) ? SV_TASOptValue(e, 1) : e.topt_bestr2;  // no second rate yet: the first goes on
	if (p == 3) return (e.topt_bestf < 0) ? ((e.topt_mode & 16) ? 0 : SV_TASOptValue(e, (e.topt_mode & 8) ? 5 : 1)) : e.topt_bestf;   // no flick yet: the rate goes on (follow: none added)
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
		e.topt_outcome = (e.topt_tgtuse && e.topt_reachv >= TOPT_REACH) ? 2 : 1;
		if (e.topt_obj)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: best %s turn %.3f deg/tick over %.0f ticks: %s (%.0f candidates); paused at %.0f\n",
				(e.topt_dir > 0) ? "left" : "right", e.topt_bestr, e.topt_n, SV_TASOptDesc(e, v), e.topt_evals, SV_TimerTicks(e)));
		else
			sprint(e, PRINT_HIGH, sprintf("tas optimize: best %s turn %.3f deg/tick over %.0f ticks: %s %.1f u/s (%.0f candidates); paused at %.0f\n",
				(e.topt_dir > 0) ? "left" : "right", e.topt_bestr, e.topt_n, e.topt_energy ? "energy" : "exit", SV_TASOptEnergyShow(e, v), e.topt_evals, SV_TimerTicks(e)));
		if (e.topt_mode)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: with%s\n", substring(SV_TASOptExtra(e), 1, -1)));
		if (e.topt_fast && e.topt_fcut)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: %.0f of %.0f candidates met something QC acts on (or stopped early) and were not counted\n",
				e.topt_fcut, e.topt_evals - 1));
		SV_TASOptRollReport(e);
		if (e.topt_tube > 0)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: %.0f candidates left the tube (%.0f u round the demo's path) and scored as cut there\n",
				e.topt_tubeout, e.topt_tube));
		if (e.topt_wallhit)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: %.0f candidates touched a wall%s (%.0f a tick off their score)\n", e.topt_wallhit,
				e.topt_ewall ? "" : " in flight", TOPT_WALLPEN));
		if (e.topt_tgtuse && e.topt_reachw)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: the played line touches a wall on %.0f ticks before %s\n", e.topt_reachw,
				(e.topt_reachv >= TOPT_REACH) ? "the reach" : "its closest tick"));
		if (e.topt_tgtuse)
		{	// P1449: the search scored the reach, the line above the end of the tape
			if (e.topt_reachv >= TOPT_REACH)
			{
				if (cvar("developer") && (e.topt_tgtn_x || e.topt_tgtn_y) && e.topt_tgtn_z < 0.99)
					sprint(e, PRINT_HIGH, sprintf("tas optimize: boarded %.0f u along the run and %.0f u up the face from the target point\n",
						e.topt_rbal, e.topt_rbup));
				sprint(e, PRINT_HIGH, sprintf("tas optimize: target reached at tick %.0f of %.0f (%.1f u from it), %s %.1f u/s there\n",
					e.topt_reachk, e.topt_n, e.topt_reachd, e.topt_energy ? "energy" : "speed", SV_TASOptEnergyShow(e, e.topt_reache)));
			}
			else if (e.topt_reachv >= TOPT_WEAK && e.topt_reacheg)      // the played line's own (review)
				sprint(e, PRINT_HIGH, sprintf("tas optimize: target reached only through an edge bug (a fall stopped on an edge, not a ramp): not counted (%.0f such reaches)\n",
					e.topt_edgen));
			else if (e.topt_reachv >= TOPT_WEAK)
				sprint(e, PRINT_HIGH, sprintf("tas optimize: target reached but too slow: energy %.1f u/s at tick %.0f, under the minimum %.1f (%.0f such reaches)\n",
					SV_TASOptEnergyShow(e, e.topt_reache), e.topt_reachk, SV_TASOptEnergyShow(e, e.topt_emin), e.topt_weakn));
			else
				sprint(e, PRINT_HIGH, sprintf("tas optimize: target not reached: closest %.1f u at tick %.0f of %.0f\n",
					e.topt_reachd, e.topt_reachk, e.topt_n));
			if (fabs(e.topt_reachv - e.topt_bestv) > 0.05)
				sprint(e, PRINT_HIGH, "tas optimize: the played best's rollout differs from the search: the world moved between them\n");
			if (e.topt_pn == e.topt_play && e.topt_pcut != 1 && (e.origin != e.topt_po || e.velocity != e.topt_pv))
				sprint(e, PRINT_HIGH, sprintf("tas optimize: the real move ended %.2f u and %.2f u/s from its prediction: the reach is not certain\n",
					vlen(e.origin - e.topt_po), vlen(e.velocity - e.topt_pv)));
		}
		else if (e.topt_obj && fabs(v - e.topt_bestv) > 0.35)   // the score's speed step at one stage is 0.31 u/s
			sprint(e, PRINT_HIGH, "tas optimize: the replay differs from the search: the world moved between them\n");
		else if (!e.topt_obj && fabs(v - e.topt_bestv) > 0.05)  // a moving world can differ between two plays
				sprint(e, PRINT_HIGH, sprintf("tas optimize: replayed %.1f u/s, searched %.1f: the world moved between them\n",
					SV_TASOptEnergyShow(e, v), SV_TASOptEnergyShow(e, e.topt_bestv)));
		if (e.topt_bestr >= e.topt_rmax - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: that is the top of the range searched; a sharper turn may be faster\n");
		if ((e.topt_mode & 1) && fabs(e.topt_besty) >= TOPT_YMAX - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: the board is at the end of its range; a wider one may be faster\n");
		if ((e.topt_mode & 2) && e.topt_bestf >= TOPT_FMAX - 0.01)
			sprint(e, PRINT_HIGH, "tas optimize: the flick is at the top of its range\n");
		return;
	}
	p = SV_TASOptParam(e, e.topt_srch);
	if (e.topt_fast && (cvar("developer") < 2 || e.topt_evals > 64)) {}
	else if (e.topt_mode || e.topt_obj) sprint(e, PRINT_HIGH, sprintf("tas optimize: %.0f  %s %.3f -> %s\n", e.topt_evals,
		(p == 2) ? "board" : ((p == 3) ? "flick" : ((p == 4) ? "period" : ((p == 5) ? "turn 2" : ((p == 6) ? "split" : "turn")))),
		e.topt_cand, SV_TASOptDesc(e, v)));
	else sprint(e, PRINT_HIGH, sprintf("tas optimize: %.0f  turn %.3f deg/tick -> %.1f u/s\n", e.topt_evals, e.topt_cand, v));
	if (v > e.topt_bestv)
	{
		e.topt_bestv = v; e.topt_bestce = e.topt_cande; e.topt_bestcd = e.topt_candd;
		if (p == 2) e.topt_besty = e.topt_cand; else if (p == 3) e.topt_bestf = e.topt_cand;
		else if (p == 4) e.topt_bestp = e.topt_cand; else if (p == 5) e.topt_bestr2 = e.topt_cand;
		else if (p == 6) e.topt_bests = e.topt_cand; else e.topt_bestr = e.topt_cand;
	}
	lo = SV_TASOptLo(e, p); hi = SV_TASOptHi(e, p);
	if (e.topt_phase == 1)
	{
		e.topt_k = e.topt_k + 1;
		step = (hi - lo) / (SV_TASOptGrid(e) - 1);
		if (e.topt_k < SV_TASOptGrid(e)) { e.topt_cand = lo + e.topt_k * step; return; }
		e.topt_phase = 2;
		best = max(lo, (p == 2) ? e.topt_besty : ((p == 4) ? e.topt_bestp : ((p == 6) ? e.topt_bests
			: ((p == 5) ? ((e.topt_bestr2 < 0) ? e.topt_bestr : e.topt_bestr2)
			: ((p == 3) ? SV_TASOptValue(e, 3) : e.topt_bestr)))));
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

// P1449: candidate paths to their own player's view (TAS_EV_OPTVIZ; cl_tasoptviz.qc): the body now and up to
// 63 points of topt_out's counted ticks; kind 0 a new search (the body, the target), 1 a miss, 2 a reach,
// 3 a cut, 5 a new best, 4 the one played. Reliable, so RATE-LIMITED: a best and a sampled candidate are
// kept (topt_vb/vc) and SV_TASOptVizFlush sends one message every 0.25 s -- sending every improvement
// overflowed the client's reliable backbuffers early in a search and the server dropped it
// (MAX_BACK_BUFFERS, 9 Nov). Points after the first go as shorts: 4-unit steps from it.
.float topt_vizt, topt_vbn, topt_vcn, topt_vckind;
float topt_vp[576];             // three paths of 64 points (x y z): 0 the best waiting, 1 a candidate, 2 scratch
                                // (32 left 600 u chords on a lookahead link: the line cut inside its curves)
float(entity e, float ran, float w) SV_TASOptVizSample =
{
	local float st, k, n, t, b;
	if (ran < 1) return 0;
	st = max(1, ceil(ran / 63));
	n = 1 + ceil(ran / st);
	b = w * 192;
	topt_vp[b] = e.origin_x; topt_vp[b+1] = e.origin_y; topt_vp[b+2] = e.origin_z;
	for (k = 1; k < n; k = k + 1)
	{
		t = (min(k * st, ran) - 1) * 13;
		topt_vp[b+k*3] = topt_out[t]; topt_vp[b+k*3+1] = topt_out[t+1]; topt_vp[b+k*3+2] = topt_out[t+2];
	}
	return n;
};

void(entity e, float kind, float n, float w) SV_TASOptVizWrite =
{
	local float k, b;
	b = w * 192;
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET); WriteByte(MSG_MULTICAST, TAS_EV_OPTVIZ);
	WriteByte(MSG_MULTICAST, kind); WriteByte(MSG_MULTICAST, n);
	if (n >= 1) { WriteFloat(MSG_MULTICAST, topt_vp[b]); WriteFloat(MSG_MULTICAST, topt_vp[b+1]); WriteFloat(MSG_MULTICAST, topt_vp[b+2]); }
	for (k = 1; k < n; k = k + 1)
	{
		WriteShort(MSG_MULTICAST, bound(-32767, rint((topt_vp[b+k*3] - topt_vp[b]) / 4), 32767));
		WriteShort(MSG_MULTICAST, bound(-32767, rint((topt_vp[b+k*3+1] - topt_vp[b+1]) / 4), 32767));
		WriteShort(MSG_MULTICAST, bound(-32767, rint((topt_vp[b+k*3+2] - topt_vp[b+2]) / 4), 32767));
	}
	msg_entity = e; multicast(e.origin, MULTICAST_ONE_R);     // reliable: unreliable ones never arrived (a paused client's datagram)
	if (cvar("developer") >= 2) print(sprintf("tas_viz: sent kind %.0f, %.0f points at %.3f\n", kind, n, time));
};

// kind 0 (start) and 4 (played) go now; 5 and 1-3 are kept for the flush
void(entity e, float kind, float ran) SV_TASOptVizSend =
{
	local float n;
	if (kind == 0)
	{
		topt_vp[384] = e.origin_x; topt_vp[385] = e.origin_y; topt_vp[386] = e.origin_z;
		topt_vp[387] = e.topt_tgt_x; topt_vp[388] = e.topt_tgt_y; topt_vp[389] = e.topt_tgt_z;
		SV_TASOptVizWrite(e, 0, e.topt_tgtuse ? 2 : 1, 2);
		e.topt_vbn = e.topt_vcn = 0;
		return;
	}
	if (kind == 4) { n = SV_TASOptVizSample(e, ran, 2); if (n) SV_TASOptVizWrite(e, 4, n, 2); return; }
	if (kind == 5) { e.topt_vbn = SV_TASOptVizSample(e, ran, 0); return; }
	if (!e.topt_vcn) { e.topt_vcn = SV_TASOptVizSample(e, ran, 1); e.topt_vckind = kind; }
};

void(entity e) SV_TASOptVizFlush =
{
	if (time < e.topt_vizt) return;
	if (e.topt_vbn) { SV_TASOptVizWrite(e, 5, e.topt_vbn, 0); e.topt_vbn = 0; e.topt_vizt = time + 0.25; return; }
	if (e.topt_vcn) { SV_TASOptVizWrite(e, e.topt_vckind, e.topt_vcn, 1); e.topt_vcn = 0; e.topt_vizt = time + 0.25; }
};

// P1449: `tas seed q1 .. qk` -- a curve's knots for the next curve search with k knots to start from (a
// demo's line, so the search improves a human's run); `tas seed clear`.
void(entity e, float argc) SV_TASSeedCommand =
{
	local float i;
	if (argc == 3 && argv(2) == "clear") { e.topt_kseedn = 0; sprint(e, PRINT_HIGH, "tas seed: cleared\n"); return; }
	if (argc < 5 || argc > 2 + TOPT_KMAX)
	{
		sprint(e, PRINT_HIGH, sprintf("tas seed <q1> .. <qk> (3..%.0f knots, each -%.0f..%.0f) | clear\n", TOPT_KMAX, TOPT_QMAX, TOPT_QMAX));
		return;
	}
	if (!SV_TASToolGate(e, "seed")) return;
	if (e.topt_on) { sprint(e, PRINT_HIGH, "tas seed: the optimizer is running\n"); return; }
	for (i = 2; i < argc; i = i + 1)
		if (!FS_TASNumber(argv(i))) { sprint(e, PRINT_HIGH, "tas seed: numbers only\n"); return; }
	for (i = 2; i < argc; i = i + 1) topt_kseed[i - 2] = bound(-TOPT_QMAX, stof(argv(i)), TOPT_QMAX);
	e.topt_kseedn = argc - 2;
	sprint(e, PRINT_HIGH, sprintf("tas seed: %.0f knots kept for the next `curve %.0f` search\n", e.topt_kseedn, e.topt_kseedn));
};

// P1449 review: the demo, search and autosurf tools are local practice. Refused on a lobby server (any
// player could pause there: a search takes 40 ms of every server frame, and file reads stall it), and
// only from a paused running TAS attempt (SV_TASInputReady says why not).
float(entity e, string what) SV_TASToolGate =
{
	if (Lobby_Active()) { sprint(e, PRINT_HIGH, strcat("tas ", what, ": a local practice tool; not on lobby servers\n")); return FALSE; }
	if (!e.run_tas_rwcap || !SV_TASInputReady(e)) return FALSE;
	return TRUE;
};
// Demo files a tool may read: .rec under data/ (a bare name is data/'s) or cfg/ksfreplays/ -- not the
// lobby cfgs or maps the engine's read path would otherwise reach (review). Lines read a call are capped.
#define TAS_DEMOLINES 40000
float(string p) SV_TASDemoPathOK =
{
	local float i, c;
	if (p == "" || strstrofs(p, "..") >= 0) return FALSE;
	for (i = 0; i < strlen(p); i = i + 1)
	{	// letters, digits, _ - . / only: no space (re-tokenized by autosurf), no \\ or :
		c = str2chr(p, i);
		if (!((c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c == 95 || c == 45 || c == 46 || c == 47)) return FALSE;
	}
	if (strlen(p) < 5 || strtolower(substring(p, strlen(p) - 4, 4)) != ".rec") return FALSE;
	return strstrofs(p, "/") < 0 || substring(p, 0, 5) == "data/" || substring(p, 0, 15) == "cfg/ksfreplays/";
};

// P1449: a KSF import's move column as a command: some imports store only its direction (-1..1: the
// surf_monolith and surf_prosurf runs; surf_null's carry +-400) -- a 1 u sidemove strafes nothing.
float(float m) SV_TASDemoMove =
{
	if (m && fabs(m) <= 1) m = m * 450;
	return bound(-450, rint(m), 450);
};

// P1449: `tas demorows <file> <from>` -- up to TOPT_HMAX rows of a recording from time `from` (KSF import
// columns, ksfbuttons lines: jump 2 -> 1, duck 4 -> 2) for `curve k demo` to correct. Stand where the
// recording is at `from` (the chain driver places the body there first).
void(entity e, float argc) SV_TASDemoRowsCommand =
{
	local string path, line;
	local float fh, from, n, c, kb, blank, yaw, pvx, pvy, sd, x, wy, lines;
	path = argv(2); from = stof(argv(3));
	if (argc != 4 || !SV_TASDemoPathOK(path) || !FS_TASNumber(argv(3)))
	{
		sprint(e, PRINT_HIGH, "tas demorows <file.rec> <from>: a recording's rows from time `from` for `tas optimize ... curve k demo` (under data/ or cfg/ksfreplays/)\n");
		return;
	}
	if (e.topt_on || e.tdem_on) { sprint(e, PRINT_HIGH, "tas demorows: the optimizer or a demo is running\n"); return; }
	if (!SV_TASToolGate(e, "demorows")) return;
	if (SV_TASOptBusy(e)) return;
	fh = fopen(path, FILE_READ);
	if (fh < 0) { sprint(e, PRINT_HIGH, sprintf("tas demorows: cannot open %s\n", path)); return; }
	n = 0; kb = 0; blank = 0; pvx = pvy = 0; lines = 0;
	while (n < TOPT_HMAX && blank < 64 && lines < TAS_DEMOLINES)
	{
		line = fgets(fh); lines = lines + 1;
		if (line == "") { blank = blank + 1; continue; }
		blank = 0;
		c = tokenize(line);
		if (argv(0) == "ksfbuttons" && c >= 3) { kb = stof(argv(2)); continue; }
		if (c < 14 || !FS_TASNumber(argv(0))) continue;
		if (stof(argv(0)) < from - 0.0001) { pvx = stof(argv(4)); pvy = stof(argv(5)); continue; }
		yaw = stof(argv(8));
		// the command this row's keys and view gave against the velocity before it: a row's input is the
		// one that produced it (surfledger.py's per-tick books close that way; the other reading does not)
		sd = stof(argv(12));
		wy = (yaw + ((sd < 0) ? 90 : -90)) / DEG_PER_RAD;        // Source: negative sidemove is left
		x = pvx * cos(wy) + pvy * sin(wy);
		topt_dq[n] = (sd == 0) ? 0 : bound(-TOPT_QMAX, ((sd < 0) ? 1 : -1) * (30 - x), TOPT_QMAX);
		pvx = stof(argv(4)); pvy = stof(argv(5));
		topt_dpos[n*3] = stof(argv(1)); topt_dpos[n*3+1] = stof(argv(2)); topt_dpos[n*3+2] = stof(argv(3));
		topt_dlen[n] = n ? topt_dlen[n-1] + vlen([topt_dpos[n*3] - topt_dpos[n*3-3], topt_dpos[n*3+1] - topt_dpos[n*3-2], topt_dpos[n*3+2] - topt_dpos[n*3-1]]) : 0;
		topt_drow[n*5] = SV_TASDemoMove(stof(argv(11)));
		topt_drow[n*5+1] = SV_TASDemoMove(stof(argv(12)));
		topt_drow[n*5+2] = bound(-89, stof(argv(7)), 89);
		topt_drow[n*5+3] = yaw - 360 * floor((yaw + 180) / 360);
		topt_drow[n*5+4] = ((kb & 2) ? 1 : 0) | ((kb & 4) ? 2 : 0);
		n = n + 1;
	}
	fclose(fh);
	e.topt_dn = n;
	sprint(e, PRINT_HIGH, sprintf("tas demorows: %.0f rows from %s at %.4f\n", n, path, from));   // not argv: the loop tokenized
};

// P1449: does this server's tas_rollout take FOLLOW rows? An engine without them refuses the bits (-10).
// P1449 probes: 1 the engine does it, 0 it does not (-10: unknown row bits, or ran without writing the
// row back), else the rollout's refusal here (SV_TASRollWhy) -- a state, not the engine (a probe at a
// hop's jump tick read as "needs an engine", 9 Nov).
.float topt_probe;              // the last probe's rollout return
float(entity e) SV_TASOptEngineFollows =
{
	local float r;
	if (!topt_rows) topt_rows = (float*)memalloc(TOPT_HMAX * 7 * 4);
	if (!topt_out) topt_out = (float*)memalloc(TOPT_HMAX * 13 * 4);
	if (!topt_rows || !topt_out) return FALSE;
	topt_rows[0] = 0; topt_rows[1] = -450; topt_rows[2] = 0; topt_rows[3] = 0; topt_rows[4] = 30; topt_rows[5] = 0;
	topt_rows[6] = TOPT_EFOLLOW + TOPT_EPITCHV;
	SV_NoColPre(e);
	r = tas_rollout(e, topt_rows, 1, topt_out);
	SV_NoColPost(e);
	e.topt_probe = r;
	if (r < 0 && r != -10) return r;
	return r >= 1 && topt_rows[6] == 0;         // ran it, and wrote the row back
};

// P1466: does this server's tas_rollout report walls on any tick? (An older one refuses the row bit: -10.)
float(entity e) SV_TASOptEngineWalls =
{
	local float r;
	if (SV_TASOptEngineFollows(e) != 1) return FALSE;
	topt_rows[0] = 0; topt_rows[1] = -450; topt_rows[2] = 0; topt_rows[3] = 0; topt_rows[4] = 30; topt_rows[5] = 0;
	topt_rows[6] = TOPT_EFOLLOW + TOPT_EWALL;
	SV_NoColPre(e);
	r = tas_rollout(e, topt_rows, 1, topt_out);
	SV_NoColPost(e);
	return r >= 1 && topt_rows[6] == 0;
};

// P1466: does it take aimlead? (An older one refuses eight arguments: -1.)
float(entity e) SV_TASOptEngineLeads =
{
	local float r;
	topt_rows[0] = 0; topt_rows[1] = -450; topt_rows[2] = 0; topt_rows[3] = 0; topt_rows[4] = 30; topt_rows[5] = 0;
	topt_rows[6] = TOPT_EFOLLOW + TOPT_EAIM;
	SV_NoColPre(e);
	r = tas_rollout(e, topt_rows, 1, topt_out, e.origin + '1000 0 0', TOPT_AIMGAIN, '0 0.766 0.643', 0.25);
	SV_NoColPost(e);
	return r >= 1 && topt_rows[6] == 0;
};

// P1449: does this server's tas_rollout take an aim point and AIM rows? (An older one refuses six arguments.)
float(entity e) SV_TASOptEngineAims =
{
	local float r;
	r = SV_TASOptEngineFollows(e);
	if (r != 1) return r;
	topt_rows[0] = 0; topt_rows[1] = -450; topt_rows[2] = 0; topt_rows[3] = 0; topt_rows[4] = 30; topt_rows[5] = 0;
	topt_rows[6] = TOPT_EFOLLOW + TOPT_EAIM;
	SV_NoColPre(e);
	r = tas_rollout(e, topt_rows, 1, topt_out, e.origin + '1000 0 0', TOPT_AIMGAIN);
	SV_NoColPost(e);
	e.topt_probe = r;
	if (r < 0 && r != -10) return r;
	return r >= 1 && topt_rows[6] == 0;
};

// P1449 curve: the next sample into topt_kcur.
void(entity e) SV_TASOptCurveNext =
{
	local float j, u, g, c;
	if (e.topt_kgen < 0)
	{
		for (j = e.topt_kn; j < e.topt_kd; j = j + 1) topt_kcur[j] = 0;    // aim: the grid aims at the target
		// aim late: the grid tries four starts (0.7, 0.4, 0.55, 0.85 of the way): a line faster than the demo's must
		// begin a max-rate air turn earlier, and spread 200 round 0.7 almost never sampled 0.4 (surf_null ramp 6 -> 7:
		// farsh turns 94 deg at 43 deg/s, the air cap's rate; at 2800 u/s that arc is ~490 u wider)
		if ((e.topt_mode & 256) && e.topt_kidx > 1) topt_kcur[e.topt_kn + 2] = (e.topt_kidx & 2) ? ((e.topt_kidx & 1) ? 250 : -250) : ((e.topt_kidx & 1) ? -500 : 0);
		if (e.topt_elead && e.topt_kidx > 1 && (e.topt_kidx & 4)) topt_kcur[e.topt_kleadj] = -TOPT_AIMR;    // straight at it (lead 0)
		if (e.topt_kidx == 0 && (e.topt_mode & 64))
		{	// the demo itself
			for (j = 0; j < e.topt_kn; j = j + 1) topt_kcur[j] = 0;
			return;
		}
		if (e.topt_kidx == 1 && (e.topt_mode & 64) && e.topt_wseedn > 0 && e.topt_wseedhead == e.topt_head)
		{	// the last search's lookahead from here (SV_TASOptWarmKeep), each knot at its own tick
			for (j = 0; j < e.topt_kn; j = j + 1)
			{
				u = SV_TASOptKnotTick(e, j);
				topt_kcur[j] = topt_wseed[min(u, e.topt_wseedn - 1)];
			}
			return;
		}
		if (e.topt_kidx == 0 && e.topt_kseedn == e.topt_kn)
		{	// a seed (a demo's own line, `tas seed`): the first sample, so the search starts no worse
			for (j = 0; j < e.topt_kn; j = j + 1) topt_kcur[j] = topt_kseed[j];
			return;
		}
		if (e.topt_kidx < 13)
		{
			u = (e.topt_mode & 64) ? (e.topt_efol ? TOPT_DQOFF : TOPT_DOFF) : TOPT_QMAX;
			c = e.topt_dir * (-u + e.topt_kidx * (2 * u) / 12);     // both sides
			for (j = 0; j < e.topt_kn; j = j + 1) topt_kcur[j] = c;
		}
		else
		{
			u = e.topt_kidx - 13;                                   // 5 x 5: q1, q2 in -90..90
			c = -90 + 45 * floor(u / 5); g = -90 + 45 * (u - 5 * floor(u / 5));
			if (e.topt_mode & 64) { u = e.topt_efol ? TOPT_DQOFF : TOPT_DOFF; c = c * u / 120; g = g * u / 120; }
			for (j = 0; j < e.topt_kn; j = j + 1) topt_kcur[j] = (j < e.topt_kn / 2) ? c : g;
		}
		return;
	}
	for (j = 0; j < e.topt_kd; j = j + 1)
	{
		if (e.topt_kidx == 0) g = 0;            // the mean itself, once a generation
		else
		{
			// near-normal, unit variance, from four uniforms: log (#532) is precache_vwep_model on this server
			u = random() + random() + random() + random();
			g = (u - 2) * 1.7320508;
		}
		u = (j >= e.topt_kn) ? TOPT_AIMR : ((e.topt_mode & 64) ? (e.topt_efol ? TOPT_DQOFF : TOPT_DOFF) : TOPT_QMAX);
		topt_kcur[j] = bound(-u, topt_kmean[j] + topt_ksig[j] * g, u);
		topt_kpop[e.topt_kidx * TOPT_KMAX + j] = topt_kcur[j];
	}
};

// P1449 curve: one sample scored (v: SV_TASOptRollScore's); the next generation, or the play.
void(entity e, float v) SV_TASOptCurveResult =
{
	local float j, i, n, m, s, w, pick, bv;
	local string st;
	e.topt_evals = e.topt_evals + 1;
	if (v > e.topt_bestv)
	{
		e.topt_bestv = v; e.topt_bestce = e.topt_cande; e.topt_bestcd = e.topt_candd;
		for (j = 0; j < e.topt_kd; j = j + 1) topt_kbest[j] = topt_kcur[j];
		for (j = 0; j < e.topt_n; j = j + 1)
		{
			topt_byaw[j] = topt_fyaw[j]; topt_bside[j] = topt_fside[j];
			topt_wvy[j] = topt_fvy[j]; topt_wvs[j] = topt_fvs[j];
		}
		e.topt_bok = e.topt_wok = 1;
	}
	if (e.topt_kgen < 0)
	{
		if (e.topt_kidx == 0 && cvar("developer") >= 2)
			sprint(e, PRINT_HIGH, sprintf("tas optimize: the first candidate (%s) scores %.1f, closest %.0f u at tick %.0f; %s\n",
				(e.topt_mode & 64) ? "the demo itself" : "the seed or the lowest constant", v, e.topt_candd, e.topt_candk,
				sprintf("ran %.0f, QC cut %.0f, limit %.0f (1 tube)", e.topt_rollran, e.topt_rollcut, e.topt_limwhy)));
		e.topt_kidx = e.topt_kidx + 1;
		if (e.topt_kidx < TOPT_CEGRID) return;
		for (j = 0; j < e.topt_kd; j = j + 1)
		{
			topt_kmean[j] = topt_kbest[j];
			topt_ksig[j] = (j >= e.topt_kn) ? 200 : ((e.topt_mode & 64) ? (e.topt_efol ? 8 : 2) : 40);
		}
		e.topt_kgen = 0; e.topt_kidx = 0;
		return;
	}
	topt_kval[e.topt_kidx] = v;
	e.topt_kidx = e.topt_kidx + 1;
	if (e.topt_kidx < TOPT_CEPOP) return;
	if (cvar("developer") >= 2)
	{	// the generation: its best, cuts and reaches, the mean and spread it was drawn from
		bv = -2; w = 0; n = 0;
		for (i = 0; i < TOPT_CEPOP; i = i + 1)
		{
			bv = max(bv, topt_kval[i]);
			if (topt_kval[i] == -1) w = w + 1;
			if (topt_kval[i] >= TOPT_REACH) n = n + 1;
		}
		st = "";
		for (j = 0; j < e.topt_kn; j = j + 1) st = strcat(st, sprintf(" %.0f/%.0f", topt_kmean[j], topt_ksig[j]));
		sprint(e, PRINT_HIGH, sprintf("tas optimize: gen %.0f best %.0f, %.0f cut, %.0f reached; mean/spread%s\n", e.topt_kgen, bv, w, n, st));
	}
	// the best TOPT_CEEL samples (a cut scores -1), marked in topt_kel; the mean and spread move to them
	for (i = 0; i < TOPT_CEPOP; i = i + 1) topt_kel[i] = 0;
	for (n = 0; n < TOPT_CEEL; n = n + 1)
	{
		pick = -1; bv = -1000000000;
		for (i = 0; i < TOPT_CEPOP; i = i + 1)
			if (!topt_kel[i] && topt_kval[i] > bv) { bv = topt_kval[i]; pick = i; }
		if (pick >= 0) topt_kel[pick] = 1;
	}
	for (j = 0; j < e.topt_kd; j = j + 1)
	{
		m = 0; w = 0;
		for (i = 0; i < TOPT_CEPOP; i = i + 1) if (topt_kel[i]) { m = m + topt_kpop[i * TOPT_KMAX + j]; w = w + 1; }
		if (!w) continue;
		m = m / w;
		s = 0;
		for (i = 0; i < TOPT_CEPOP; i = i + 1)
			if (topt_kel[i]) s = s + (topt_kpop[i * TOPT_KMAX + j] - m) * (topt_kpop[i * TOPT_KMAX + j] - m);
		topt_kmean[j] = 0.7 * m + 0.3 * topt_kmean[j];
		// spread floors: with every candidate cut, a board-2 search collapsed onto one near miss by
		// generation 10 (0.01 / 2 u floors) and never tried the 80 u sideways it needed (9 Nov)
		if (j >= e.topt_kn) topt_ksig[j] = bound(25, 0.7 * sqrt(s / w) + 0.3 * topt_ksig[j], 400);
		else topt_ksig[j] = bound((e.topt_mode & 64) ? (e.topt_efol ? 1.5 : 0.1) : 0.2, 0.7 * sqrt(s / w) + 0.3 * topt_ksig[j], (e.topt_mode & 64) ? (e.topt_efol ? 16 : 4) : 60);
	}
	e.topt_kgen = e.topt_kgen + 1; e.topt_kidx = 0;
	if (e.topt_kgen == 1 || e.topt_bestv > e.topt_kprev + 0.5) { e.topt_kprev = e.topt_bestv; e.topt_kstall = 0; }
	else e.topt_kstall = e.topt_kstall + 1;
	if (cvar("developer"))
		sprint(e, PRINT_HIGH, sprintf("tas optimize: curve generation %.0f, best %.1f, %.0f candidates, %.1f s\n", e.topt_kgen, SV_TASOptEnergyShow(e, e.topt_bestv), e.topt_evals, gettime(1)));
	if (e.topt_kgen >= e.topt_cegen || (e.topt_kgen >= TOPT_CEMIN && e.topt_kstall >= e.topt_cestall && (!e.topt_tgtuse || e.topt_bestv >= TOPT_REACH)))
	{
		for (j = 0; j < e.topt_kd; j = j + 1) topt_kcur[j] = topt_kbest[j];
		e.topt_phase = 3;
	}
};

void(entity e) SV_TASDemoFrame;
// After SV_TASProjectFrame: one step of the search a frame.
float topt_frtime, topt_frstart;  // the server frame the search budget counts in, and its wall-clock start
void(entity e) SV_TASOptFrame =
{
	local float head, k, v, t0v;
	SV_TASDemoFrame(e);             // P1449
	SV_TASAutoFrame(e);             // P1449: an autosurf's next stretch, between its searches
	if (e.topt_on || e.tdem_on || e.as_on) topt_busyt = time;   // the chain holds the guard across its rewinds, armed too (it owns as_rows)
	if (!e.topt_on) return;
	if (!e.run_tas_paused || e.run_t_state != TS_RUNNING) { SV_TASOptStop(e, "TAS play/off, or the run ended"); return; }
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_pending) return;
	head = SV_TimerTicks(e);
	if (e.topt_stage == 2)
	{
		if (e.run_tas_replaystate != TAS_TAPE_DONE || head != e.topt_head + e.topt_tat + e.topt_chunk)
		{
			SV_TASOptStop(e, "the input tape did not land on its tick");
			return;
		}
		e.topt_tat = e.topt_tat + e.topt_chunk;
		if (e.topt_tat < e.topt_play) { e.topt_stage = 4; return; }    // P1449: the next tape of a long horizon
		e.topt_stage = 1;
		if (e.topt_pn == e.topt_play && e.topt_pcut != 1)
		{	// P1443: the real mover's landing against the rollout's last tick (a cut on the last tick is not one)
			e.topt_rchk = e.topt_rchk + 1;
			e.topt_rbado = max(e.topt_rbado, vlen(e.origin - e.topt_po));
			e.topt_rbadv = max(e.topt_rbadv, vlen(e.velocity - e.topt_pv));
			if (e.origin == e.topt_po && e.velocity == e.topt_pv)
				e.topt_rexact = e.topt_rexact + 1;
			if (cvar("developer"))
				sprint(e, PRINT_HIGH, sprintf("tas optimize: rollout %.0f off by %.5f u, %.5f u/s\n", e.topt_evals + 1,
					vlen(e.origin - e.topt_po), vlen(e.velocity - e.topt_pv)));
		}
		else if (e.topt_pn >= 0 && e.topt_pcut == 1)	// incl. a cut on the last tick
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
	if (e.topt_stage == 4)
	{	// P1449: no prediction between tapes: the rows are the ones already predicted
		if (!SV_TASOptTape(e, SV_TASOptValue(e, 1), SV_TASOptValue(e, 2), SV_TASOptValue(e, 3)))
		{
			if (!e.topt_wait) e.topt_wait = time + 1;
			if (time > e.topt_wait) SV_TASOptStop(e, "the engine refused the next input tape");
			return;
		}
		e.topt_wait = 0;
		e.topt_stage = 2;
		return;
	}
	// the back/tape pacing; a fast search rolling at the head is paced by its own wall-time budget below
	if (time < e.topt_next && !(e.topt_fast && e.topt_phase != 3 && head == e.topt_head)) return;
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
		if (time == topt_frtime && gettime(1) - topt_frstart > TOPT_FRAMEBUDGET) return;   // the frame's spent: not even the walk below
		v = SV_TASRollPending(e);
		if (v)
		{
			SV_TASOptStop(e, e.vbsp_grav_trig ? "the body is inside a trigger_gravity volume that resets gravity on leaving; step out of it first"
				: ((v == -31) ? "QC owes this body a velocity change on its next move (a script write or a pad latch); step a few ticks and retry"
				: "a trigger edge or delayed output is pending at this tick; step a few ticks and retry"));
			return;
		}
		// The budget is the server FRAME's, not the call's: a call comes with each client packet (~100 a
		// second), and 40 ms a call kept one frame running for a whole search -- the clock stood still, the
		// rate-limited drawing sent one best line, and everything else on the server waited (9 Nov).
		// A frame is marked by the server's clock changing (gettime(0) is realtime, gettime(1) another clock:
		// their difference measures nothing), its start by gettime(1) at its first call.
		if (time != topt_frtime) { topt_frtime = time; topt_frstart = gettime(1); }
		if (gettime(1) - topt_frstart > TOPT_FRAMEBUDGET) return;
		for (k = 0; k < 256 && (k == 0 || gettime(1) - topt_frstart < TOPT_FRAMEBUDGET) && e.topt_on && e.topt_phase != 3; k = k + 1)
		{	// P1449: ~40 ms of rollouts a call, not a tick count (a follow candidate rolls up to 12 times to
			// its fixed point; calls come with the client's packets, a few a second from an unfocused window)
			if (e.topt_kn) SV_TASOptCurveNext(e);
			v = SV_TASOptRollScore(e, SV_TASOptValue(e, 1), SV_TASOptValue(e, 2), SV_TASOptValue(e, 3));
			if (v == -1 && e.topt_rollcut == 1 && !e.topt_rollran)
			{	// cut before tick 1: the volume the body starts in, whatever the inputs
				SV_TASOptStop(e, sprintf("the body starts inside a trigger volume QC acts on (%s, filter '%s', named '%s' here); step out of it first",
					edict_num(fabs(topt_out[12])).classname, edict_num(fabs(topt_out[12])).filtername, topt_simname));
				return;
			}
			if (v == -1) e.topt_fcut = e.topt_fcut + 1;
			if (v == -2)
			{
				SV_TASOptStop(e, SV_TASRollWhy(e.topt_rwhy));
				return;
			}
			t0v = e.topt_bestv;
			if (e.topt_kn) SV_TASOptCurveResult(e, v);
			else SV_TASOptResult(e, v);
			if (e.topt_bestv > t0v) SV_TASOptVizSend(e, 5, e.topt_rollran);     // P1449: topt_out is still this one's
			else SV_TASOptVizSend(e, (v >= TOPT_REACH) ? 2 : ((v == -1) ? 3 : 1), e.topt_rollran);
		}
		SV_TASOptVizFlush(e);
		if (e.topt_on && e.topt_phase == 3 && e.topt_bestv < 0)
			SV_TASOptStop(e, sprintf("all %.0f candidates met a trigger, touch or carrier QC acts on (or stopped early): nothing to play", e.topt_evals));
		return;
	}
	SV_TASOptPredict(e, SV_TASOptValue(e, 1), SV_TASOptValue(e, 2), SV_TASOptValue(e, 3));
	if (e.topt_phase == 3 && e.topt_tgtuse && e.topt_reachv >= 0 && e.topt_reachk >= 1 && e.topt_reachk <= e.topt_pn)
	{	// P1449: a reached target ends the link, so the best plays to the reach tick and no further (past
		// it a fail trigger could end the run under the search); a miss to its closest tick. The rows
		// before it do not change
		k = (e.topt_reachk - 1) * 13;
		e.topt_po = [topt_out[k], topt_out[k+1], topt_out[k+2]];
		e.topt_pv = [topt_out[k+3], topt_out[k+4], topt_out[k+5]];
		e.topt_play = e.topt_pn = e.topt_reachk; e.topt_pcut = 0;
	}
	if (e.topt_fast && e.topt_pn >= 1 && e.topt_play > e.topt_pn) e.topt_play = e.topt_pn;    // an engine stop: its later rows were never written back
	if (e.topt_phase == 3 && e.topt_fast && e.topt_pn >= 1 && e.topt_tat == 0) SV_TASOptVizSend(e, 4, e.topt_play);
	e.topt_tat = 0;
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

// P1449: tas target <x> <y> <z> [radius 8..4096, default 64] [nx ny nz] | clear | show -- a point (a face
// target's radius may span the ramp: a faster arrival boards further along it)
// `tas optimize ... fast` steers to (a boarding spot on the next ramp); with a face normal the reach
// must board that face, not just pass near the point.
void(entity e, float argc) SV_TASTargetCommand =
{
	local vector p, n;
	local float r, i;
	if (argc == 3 && argv(2) == "clear")
	{
		e.topt_tgton = 0;
		sprint(e, PRINT_HIGH, "tas target: cleared\n");
		return;
	}
	if (argc == 2 || (argc == 3 && argv(2) == "show"))
	{
		if (e.topt_tgton) sprint(e, PRINT_HIGH, sprintf("tas target: %s within %.0f u%s\n", vtos(e.topt_tgt), e.topt_tgtr,
			(e.topt_tgtn == '0 0 0') ? "" : ((e.topt_tgtn_z >= 0.99) ? ", a hop there" : strcat(", boarding face ", vtos(e.topt_tgtn)))));
		else sprint(e, PRINT_HIGH, "tas target: none\n");
		return;
	}
	r = 64;
	for (i = 2; i < argc; i = i + 1)
		if (!FS_TASNumber(argv(i)) || fabs(fs_tas_number) > 65536) argc = 0;
	if (argc == 6 || argc == 9) r = stof(argv(5));
	n = '0 0 0';
	if (argc == 9) n = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
	if ((argc != 5 && argc != 6 && argc != 9) || r < 8 || r > 4096 || (argc == 9 && fabs(vlen(n) - 1) > 0.02))
	{
		sprint(e, PRINT_HIGH, "tas target <x> <y> <z> [radius 8..4096 [nx ny nz: the face to board; 0 0 1: a hop there]] | clear | show\n");
		return;
	}
	p = [stof(argv(2)), stof(argv(3)), stof(argv(4))];
	if (n_z < 0) n = -n;
	if (n != '0 0 0') n = normalize(n);     // within 0.02 of unit was taken: hop and face tests read it exactly (review)
	e.topt_tgt = p; e.topt_tgtr = r; e.topt_tgton = 1; e.topt_tgtn = n;
	sprint(e, PRINT_HIGH, sprintf("tas target: %s within %.0f u%s; tas optimize ... fast steers to it\n", vtos(p), r,
		(n == '0 0 0') ? "" : ((n_z >= 0.99) ? ", a hop there" : strcat(", boarding face ", vtos(n)))));
};

// P1449: tas demo <file> [rows [from]] -- a recording's inputs from its first row (or the first at time
// `from` or later), played as TAS tapes from the
// paused head (TAS_TAPE_MAX rows a tape): a KSF import's sample rows (moves, pitch, yaw) with the
// ksfbuttons line before each (CS:S jump 2 -> TAS 1, duck 4 -> TAS 2). The body should stand where the
// recording starts (setpos); then the TAS continues from a human's start, prestrafe and jump included.
.float tdem_left, tdem_stage, tdem_head, tdem_n, tdem_wait, tdem_done, tdem_loaded, tdem_blank, tdem_from;
float tdem_fh;
float tdem_kb;                  // the ksfbuttons value of the row that follows
float tdem_buf[768];            // TAS_TAPE_MAX rows of fwd, side, pitch, yaw, bits, spare

void(entity e, string why) SV_TASDemoStop =
{
	if (!e.tdem_on) return;
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING)
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
	e.tdem_on = 0;
	if (tdem_fh >= 0) fclose(tdem_fh);
	tdem_fh = -1;
	sprint(e, PRINT_HIGH, sprintf("tas demo: %s after %.0f rows; paused at tick %.0f\n", why, e.tdem_done, SV_TimerTicks(e)));
};

// Up to TAS_TAPE_MAX rows into tdem_buf; 0 at the end of the file (a long run of empty reads: fgets
// gives "" for a blank line and for the end alike).
float(entity e) SV_TASDemoRead =
{
	local string line;
	local float n, c, yaw, lines;
	n = 0; lines = 0;
	while (n < TAS_TAPE_MAX && n < e.tdem_left && e.tdem_blank < 64 && lines < TAS_DEMOLINES)
	{
		line = fgets(tdem_fh); lines = lines + 1;
		if (line == "") { e.tdem_blank = e.tdem_blank + 1; continue; }
		e.tdem_blank = 0;
		c = tokenize(line);
		if (argv(0) == "ksfbuttons" && c >= 3) { tdem_kb = stof(argv(2)); continue; }
		if (c < 14 || !FS_TASNumber(argv(0))) continue;
		if (stof(argv(0)) < e.tdem_from - 0.0001) continue;
		yaw = stof(argv(8));
		tdem_buf[n*6] = SV_TASDemoMove(stof(argv(11)));
		tdem_buf[n*6+1] = SV_TASDemoMove(stof(argv(12)));
		tdem_buf[n*6+2] = bound(-89, stof(argv(7)), 89);
		tdem_buf[n*6+3] = yaw - 360 * floor((yaw + 180) / 360);
		tdem_buf[n*6+4] = (((float)tdem_kb & 2) ? 1 : 0) | (((float)tdem_kb & 4) ? 2 : 0);
		n = n + 1;
	}
	return n;
};

float(entity e) SV_TASDemoTape =
{
	local float i, tx, ok;
	if (!tas_tape(e, 2, e.tdem_n, 0, '0 0 0', '0 0 0', 0)) return FALSE;
	tx = tas_tape(e, 3, e.tdem_n, 0, '0 0 0', '0 0 0', 0);
	ok = tx > 0;
	for (i = 0; i < e.tdem_n && ok; i = i + 1)
		ok = tas_tape(e, 4, tx, i, [tdem_buf[i*6], tdem_buf[i*6+1], 0],
			[SV_TASPWord(tdem_buf[i*6+2]), SV_TASPWord(tdem_buf[i*6+3]), 0], tdem_buf[i*6+4]);
	if (ok) ok = tas_tape(e, 5, tx, 0, '0 0 0', '0 0 0', 0);
	if (!ok)
	{
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
		return FALSE;
	}
	e.run_tas_replayserial = e.rec_rec_serial;
	return TRUE;
};

// From SV_TASOptFrame (idle paused frames): one tape at a time, its landing checked on the mover's own
// tick count (a demo from the start box crosses the zone, where the run's clock restarts).
void(entity e) SV_TASDemoFrame =
{
	if (!e.tdem_on) return;
	if (!e.run_tas_paused) { SV_TASDemoStop(e, "stopped (TAS play/off)"); return; }
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_pending) return;
	if (e.tdem_stage == 2)
	{
		if (e.run_tas_replaystate != TAS_TAPE_DONE || e.run_movetick != e.tdem_head + e.tdem_n)
		{
			SV_TASDemoStop(e, "stopped: a tape did not land on its tick");
			return;
		}
		e.tdem_done = e.tdem_done + e.tdem_n;
		e.tdem_left = e.tdem_left - e.tdem_n;
		e.tdem_stage = 1; e.tdem_loaded = 0;
	}
	if (e.tdem_left <= 0) { SV_TASDemoStop(e, "done"); return; }
	if (!e.tdem_loaded)
	{
		e.tdem_n = SV_TASDemoRead(e);
		if (e.tdem_n <= 0) { SV_TASDemoStop(e, "done (end of the recording)"); return; }
		e.tdem_loaded = 1;
	}
	if (!SV_TASDemoTape(e))
	{	// a back's holds release over a frame or two
		if (!e.tdem_wait) e.tdem_wait = time + 1;
		if (time > e.tdem_wait) SV_TASDemoStop(e, "stopped: the engine refused the input tape");
		return;
	}
	e.tdem_wait = 0;
	e.tdem_head = e.run_movetick;
	e.tdem_stage = 2;
};

void(entity e, float argc) SV_TASDemoCommand =
{
	local string path;
	local float rows, from;
	path = argv(2);
	rows = (argc >= 4) ? stof(argv(3)) : 100000;
	from = (argc >= 5) ? stof(argv(4)) : -1000000;
	if (argc < 3 || argc > 5 || !SV_TASDemoPathOK(path) || rows < 1 || rows != floor(rows) ||
	    (argc >= 5 && !FS_TASNumber(argv(4))))
	{
		sprint(e, PRINT_HIGH, "tas demo <file> [rows [from]]: a recording's inputs as TAS tapes, from its first row or time `from` (stand where it is then)\n");
		return;
	}
	if (e.topt_on || e.tdem_on) { sprint(e, PRINT_HIGH, "tas demo: the optimizer or a demo is running\n"); return; }
	if (!SV_TASToolGate(e, "demo")) return;
	if (SV_TASOptBusy(e)) return;
	tdem_fh = fopen(path, FILE_READ);
	if (tdem_fh < 0) { sprint(e, PRINT_HIGH, sprintf("tas demo: cannot open %s\n", path)); return; }
	if (e.run_tas_req < 16000000) e.run_tas_req = e.run_tas_req + 1;   // a tape's request must be >= 1
	tdem_kb = 0;
	e.tdem_on = 1; e.tdem_left = rows; e.tdem_stage = 1; e.tdem_done = 0; e.tdem_loaded = 0;
	e.tdem_wait = 0; e.tdem_blank = 0; e.tdem_from = from;
	sprint(e, PRINT_HIGH, sprintf("tas demo: playing %s from tick %.0f\n", path, SV_TimerTicks(e)));
};

void(entity e) SV_TASOptReset =
{
	e.topt_on = 0;
};

// tas optimize <ticks> <left|right> [board] [flick [k]] [time] [energy] [fast]
void(entity e, float argc) SV_TASOptCommand =
{
	local float n, dir, i, mode, fk, searches, obj, fast, energy, fixp, kn, tube, hop, look, pace, emin, gens, kex, stall, low, edgeok;
	local string w;
	n = stof(argv(2));
	dir = !strcmp(argv(3), "left") ? 1 : (!strcmp(argv(3), "right") ? -1 : 0);
	mode = 0; fk = 0; obj = 0; fast = 0; energy = 0; fixp = 0; kn = 0; tube = 0; hop = 0; look = 0; pace = 0; emin = 0; gens = 0; kex = 0; stall = 0; low = 0; edgeok = 0;
	for (i = 4; i < argc; i = i + 1)
	{
		w = argv(i);
		if (w == "fast" && !fast) fast = 1;
		else if (w == "fixedpitch" && !fixp) fixp = 1;     // P1449: the view holds its pitch
		else if (w == "energy" && !energy) energy = 1;
		else if (w == "time" && !obj && mode >= 0) obj = 1;
		else if (w == "board" && !(mode & 17)) mode = mode | 1;
		else if (w == "flick" && !(mode & 38)) { mode = mode | 2; fk = 4; }          // not with zigzag or curve
		else if (w == "curve" && !(mode & 63)) { mode = mode | 48; kn = TOPT_KDEF; } // P1449: follow through knots, alone
		else if ((mode & 32) && kn == TOPT_KDEF && argv(i - 1) == "curve" && stof(w) >= 3 && stof(w) <= TOPT_KMAX && w == ftos(stof(w))) kn = stof(w);
		else if (w == "demo" && (mode & 32) && !(mode & 64)) mode = mode | 64;   // P1449: correct `tas demorows`' line
		else if (w == "aim" && (mode & 32) && !(mode & 128)) mode = mode | 128;  // P1449: flights steer to the target (demo aim: its ride, then this)
		else if (w == "late" && (mode & 192) == 192 && !(mode & 256)) mode = mode | 256;   // demo aim late: the approach only
		else if (w == "tube" && (mode & 64) && !tube) tube = -1;                 // P1449: stay near the demo's path
		else if (w == "hop" && (mode & 32) && !hop) hop = 1;                     // P1449: hold jump (topt_hop); a route's too
		else if (w == "look" && (mode & 64) && !look) look = -1;                 // P1449: score a reach's continuation
		else if (w == "pace" && (mode & 64) && !pace) pace = -1;                 // P1449: score lost a tick to the reach
		else if (w == "low" && (mode & 32) && !low) low = -1;                    // P1449: score lost a unit boarded past/above
		else if (w == "edgeok" && !edgeok) edgeok = 1;                           // P1449: an edge-bugged reach counts
		else if (low == -1 && argv(i - 1) == "low" && FS_TASNumber(w) && stof(w) > 0 && stof(w) <= 10) low = stof(w);
		else if (pace == -1 && argv(i - 1) == "pace" && FS_TASNumber(w) && stof(w) > 0 && stof(w) <= 20) pace = stof(w);
		else if (w == "gens" && (mode & 32) && !gens) gens = -1;                 // P1449: a curve search's generations
		else if (gens == -1 && argv(i - 1) == "gens" && stof(w) >= 4 && stof(w) <= 200 && w == ftos(stof(w))) gens = stof(w);
		else if (w == "stall" && (mode & 32) && !stall) stall = -1;              // P1449: generations without a gain that end it
		else if (stall == -1 && argv(i - 1) == "stall" && stof(w) >= 2 && stof(w) <= 200 && w == ftos(stof(w))) stall = stof(w);
		else if (w == "kex" && (mode & 64) && !kex) kex = -1;                   // P1449: the knots' launch split (SV_TASOptKnotD)
		else if (kex == -1 && argv(i - 1) == "kex" && stof(w) >= 8 && stof(w) <= TOPT_HMAX && w == ftos(stof(w))) kex = stof(w);
		else if (w == "emin" && (mode & 64) && !emin) emin = -1;                 // P1449: the least energy a reach counts at
		else if (emin == -1 && argv(i - 1) == "emin" && FS_TASNumber(w) && fabs(stof(w)) <= 20000)    // shown units (signed)
			emin = sqrt(max(1, stof(w) * fabs(stof(w)) + TOPT_EREF));
		else if (look == -1 && argv(i - 1) == "look" && stof(w) >= 1 && stof(w) <= 400 && w == ftos(stof(w))) look = stof(w);
		else if (tube == -1 && argv(i - 1) == "tube" && stof(w) >= 16 && stof(w) <= 4096 && w == ftos(stof(w))) tube = stof(w);
		else if (w == "zigzag" && !(mode & 30)) mode = mode | 4;    // P1449: not with flick, split or follow
		else if (w == "follow" && !(mode & 21)) mode = mode | 16;   // P1449: the view on the velocity; not with board or zigzag
		else if (w == "split" && !(mode & 44)) mode = mode | 8;     // P1449: a second rate from a searched tick
		else if ((mode & 2) && fk == 4 && argv(i - 1) == "flick" && stof(w) >= 1 && stof(w) <= 32 && stof(w) == floor(stof(w)) && w == ftos(stof(w))) fk = stof(w);
		else { mode = -1; break; }
	}
	if (tube == -1 || look == -1 || pace == -1 || emin == -1 || gens == -1 || kex == -1 || stall == -1 || low == -1 || (look && !tube)) mode = -1;      // look scores route: it needs a tube
	if (mode > 0 && (mode & 128) && (!e.topt_tgton || kn > TOPT_KMAX - ((mode & 256) ? 3 : 2)))
	{
		sprint(e, PRINT_HIGH, sprintf("tas optimize: aim steers to the tas target (set one) and takes up to %.0f knots\n", TOPT_KMAX - ((mode & 256) ? 3 : 2)));
		return;
	}
	if (mode > 0 && (mode & 64) && e.topt_dn < n)
	{
		sprint(e, PRINT_HIGH, sprintf("tas optimize: demo needs %.0f rows from `tas demorows` (%.0f loaded)\n", n, e.topt_dn));
		return;
	}
	if (mode > 0 && (mode & 16) && !fast)
	{
		sprint(e, PRINT_HIGH, "tas optimize: follow is solved by rollouts: add fast\n");
		return;
	}
	if (fast && Lobby_Active()) { sprint(e, PRINT_HIGH, "tas optimize: fast is a local practice tool; not on lobby servers\n"); return; }
	if ((obj && (fast || energy)) || (fast && !checkbuiltin(tas_rollout)))
	{
		sprint(e, PRINT_HIGH, obj ? "tas optimize: time scores stages, which only the real mover reaches: not with fast or energy\n"
			: "tas optimize: fast needs an engine with tas_rollout\n");
		return;
	}
	if (argc >= 4 && argc <= 17 && n >= 4 && n <= (fast ? TOPT_HMAX : TAS_TAPE_MAX) && n == floor(n) && dir && mode >= 0 && fk >= n)
	{
		sprint(e, PRINT_HIGH, sprintf("tas optimize: the flick (%.0f ticks) must be shorter than the run (%.0f ticks)\n", fk, n));
		return;
	}
	if (argc < 4 || argc > 30 || !(n >= 4 && n <= (fast ? TOPT_HMAX : TAS_TAPE_MAX) && n == floor(n)) || !dir || mode < 0)
	{
		sprint(e, PRINT_HIGH, "tas optimize <ticks 4..128, fast 4..768> <left|right> [board | follow | curve [knots 3..16]] [split] [flick [ticks 1..32] | zigzag] [time | energy] [fast] [fixedpitch] [aim] [hop] [gens N] [demo [late (after aim)] [tube R [look N]] [pace X] [emin E] [kex T]] [stall N] [low W] [edgeok] (with curve): best turn for exit speed (energy: speed + height), or with time the next segment soonest; fast searches by rollout and plays only the best\n");
		return;
	}
	if (!e.run_tas_rwcap || !SV_TASInputReady(e) || !SV_TASCanPause(e)) return;
	if (e.tdem_on) { sprint(e, PRINT_HIGH, "tas optimize: a demo is playing\n"); return; }
	if (SV_TASOptBusy(e)) return;
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
	e.topt_tat = e.topt_chunk = 0;      // the last search's played ticks: left over, its successor never sent the played line
	e.topt_outcome = 0;
	e.topt_evals = e.topt_iter = 0; e.topt_bestr = 0; e.topt_bestv = -1; e.topt_next = 0;
	e.topt_backed = e.topt_wait = 0;
	e.topt_mode = mode; e.topt_fk = fk; e.topt_srch = 0; e.topt_besty = 0; e.topt_bestf = 0; e.topt_bestp = 12;
	e.topt_pfoff = fixp; e.topt_pfon = 0;
	e.topt_kn = kn; e.topt_kgen = -1; e.topt_kidx = 0; e.topt_wok = e.topt_bok = 0; e.topt_vizt = 0;   // vizt before the clear below
	e.topt_efol = 0; e.topt_tube = tube; e.topt_tubeout = e.topt_wallhit = 0; e.topt_hop = hop; e.topt_look = look; e.topt_pace = pace; e.topt_emin = emin; e.topt_weakn = 0; e.topt_cegen = gens ? gens : TOPT_CEGEN; e.topt_cestall = stall ? stall : TOPT_CESTALL; e.topt_low = low; e.topt_edgeok = edgeok; e.topt_edgen = 0;
	e.topt_tgtj = 0;
	if (tube)
		for (i = 1; i < e.topt_dn; i = i + 1)
			if (vlen([topt_dpos[i*3], topt_dpos[i*3+1], topt_dpos[i*3+2]] - e.topt_tgt) <
			    vlen([topt_dpos[e.topt_tgtj*3], topt_dpos[e.topt_tgtj*3+1], topt_dpos[e.topt_tgtj*3+2]] - e.topt_tgt)) e.topt_tgtj = i;
	e.topt_ewall = 0;
	if (kn) { i = SV_TASOptEngineFollows(e); if (i == 1) e.topt_efol = 1; }    // demo too: its command in the engine
	if (e.topt_efol) e.topt_ewall = SV_TASOptEngineWalls(e);
	if (kn && i < 0)
	{
		SV_TASOptStop(e, SV_TASRollWhy(i));
		return;
	}
	e.topt_kd = kn + ((mode & 128) ? ((mode & 256) ? 3 : 2) : 0);
	e.topt_kspan = ((mode & 128) && !(mode & 256)) ? max(kn, ceil(0.45 * n)) : n;
	// kex: only with knots enough to split and the target's row well past it (else the even spread)
	e.topt_kex = e.topt_kend = 0;
	if (kex > 0 && kn >= 6 && min(e.topt_tgtj, e.topt_kspan - 1) >= kex + kn) { e.topt_kex = kex; e.topt_kend = min(e.topt_tgtj, e.topt_kspan - 1); }
	else if (kex > 0)       // said, not dropped silently (review 13)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: kex %.0f not used (it needs a tube, 6 knots or more and the target's row %.0f ticks past it): knots spread evenly\n", kex, kn));
	if (mode & 128) i = SV_TASOptEngineAims(e);
	if ((mode & 128) && i < 0)
	{
		SV_TASOptStop(e, SV_TASRollWhy(i));
		return;
	}
	if ((mode & 128) && i != 1)
	{
		SV_TASOptStop(e, "aim needs a server engine whose tas_rollout steers AIM rows (P1449)");
		return;
	}
	e.topt_elead = e.topt_kleadj = 0;
	if ((mode & 128) && (e.topt_tgtn_x || e.topt_tgtn_y) && e.topt_tgtn_z < 0.99 && e.topt_kd < TOPT_KMAX)      // a hop's floor has no lead (review)
	if (SV_TASOptEngineLeads(e))
	{
		e.topt_elead = 1; e.topt_kleadj = e.topt_kd; e.topt_kd = e.topt_kd + 1;
	}
	e.topt_bestr2 = -1; e.topt_bests = 0.5;
	e.topt_obj = obj; e.topt_seg0 = e.run_t_seg;
	e.topt_fast = fast; e.topt_energy = energy; e.topt_z0 = e.origin_z; e.topt_fcut = 0;
	e.topt_tgtuse = (fast && e.topt_tgton); e.topt_reachv = -1;   // bracketed: = binds tighter than && here
	e.topt_reachk = e.topt_reachd = e.topt_reachw = e.topt_reacheg = 0;
	if (fast) SV_TASOptVizSend(e, 0, 0);
	if (e.topt_tgtuse)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: steering to the target %s (within %.0f u), then %s there\n",
			vtos(e.topt_tgt), e.topt_tgtr, energy ? "energy" : "speed"));
	else if (e.topt_tgton)
		sprint(e, PRINT_HIGH, "tas optimize: a target is set but only fast searches steer to it\n");
	e.topt_pn = -2; e.topt_rchk = e.topt_rshort = e.topt_rbado = e.topt_rbadv = e.topt_rref = e.topt_rwhy = e.topt_rexact = e.topt_rstop = 0;
	// Source's air wish speed cap is 30: the speed-holding turn is asin(30 / v) a tick.
	e.topt_rmax = bound(1, 2 * asin(min(1, 30 / max(30, vlen([e.velocity_x, e.velocity_y, 0])))) * 180 / M_PI, 45);
	e.topt_bestf = -1;                  // no flick until its search finds a faster one
	for (searches = 0; SV_TASOptParam(e, searches); searches = searches + 1) ;
	if (kn)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: from tick %.0f, %.0f ticks, starting %s, a turn command through %.0f knots (side and view from the velocity%s): %.0f candidates by rollout, the best played\n",
			e.topt_head, n, argv(3), kn, (mode & 64) ? (tube ? sprintf("; demo, within %.0f u of its path%s", tube, look ? sprintf(", %.0f ticks of it looked ahead", look) : "") : "; demo: degrees added to its yaw") : (e.topt_efol ? ", exact in the engine" : ", approximated in passes: an older server engine"),
			TOPT_CEGRID + e.topt_cegen * TOPT_CEPOP));
	else
	sprint(e, PRINT_HIGH, sprintf("tas optimize: from tick %.0f, %.0f ticks turning %s, 0..%.2f deg/tick, %.0f candidates%s\n",
		e.topt_head, n, argv(3), e.topt_rmax, searches * (SV_TASOptGrid(e) + SV_TASOptGold(e) + 2) + 1,
		fast ? " by rollout, the best played" : ""));
	if (mode)
		sprint(e, PRINT_HIGH, sprintf("tas optimize:%s%s%s%s\n", (mode & 1) ? " board -30..30 deg;" : "",
			(mode & 8) ? " a second rate from a searched tick;" : "", (mode & 4) ? " switching sides every 2..40 ticks;" :
			((mode & 16) ? " the view follows the velocity, offset -6..6 deg;" : ""),
			(mode & 2) ? sprintf(" flick over the last %.0f ticks, 0..%.0f deg/tick", fk, TOPT_FMAX) : ""));
	if (obj)
		sprint(e, PRINT_HIGH, sprintf("tas optimize: scoring stages reached after stage %.0f, then how soon, then speed\n", e.topt_seg0 + 1));
};
