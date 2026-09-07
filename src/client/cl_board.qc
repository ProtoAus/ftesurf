/*
===========================================================================
  cl_board.qc -- grading the moment you land on a ramp.

  A "board" is the transition from air onto a surf ramp.  What it costs you
  is decided in a single tick, by one call to ClipVelocity, and the whole of
  this file is arithmetic on the two things that tick knew: the plane, and
  the velocity going in.  Both arrive from the engine (Patch 131) rather
  than being inferred here -- which is worth saying plainly, because the
  tool this is modelled on could not do that and its author spent a lot of
  effort on the workaround.

  WHY NOT MEASURE THE LOSS DIRECTLY.  The obvious implementation is
  |v_before| - |v_after|.  wrlines shipped exactly that, measured it over
  27,508 boards, and threw it away: the per-tick background motion of a
  surfer (7-12 u/s from gravity and air acceleration) is LARGER than the
  thing being measured (4-23 u/s), so the subtraction is mostly noise.  The
  projected form below has no such problem, because ClipVelocity at
  overbounce 1 is an orthogonal projection and its cost is exactly the
  component it removes.  Do not be tempted back to the subtraction.
===========================================================================
*/

// --- what the last board cost -----------------------------------------------
float  board_time;          // cltime it happened; 0 = nothing yet this map
float  board_seq;           // last run_boardcount we acted on
float  board_speedin;       // 3D speed going in
float  board_speedin_h;     // horizontal speed going in -- the "contact" readout
float  board_kept;          // 0..100, the "how perfect" number
float  board_losspct;       // 0..1
float  board_loss;          // u/s, 3D
float  board_lossh;         // u/s, horizontal only
float  board_losse;         // world units of height -- REPORTED, so gated
/*
  Build 39.  The same quantity as board_losse and computed by the same helper,
  but taken for EVERY board the engine counted rather than only for the ones
  worth grading, because the segment column has to account for all of them.
  See Board_StepE, and the boundary block in Board_Frame that spends it.
*/
float  board_stepe;
vector board_dv;            // the signed XYZ you lost
float  board_approach;      // degrees off the normal; 90 = perfect
float  board_grade;         // 0 perfect .. 4 terrible
float  board_rampdeg;       // how steep the ramp was

// --- leaving ----------------------------------------------------------------
float  board_riding;        // last frame's run_rampcontact
float  leave_time;          // cltime we came off a ramp
float  leave_speed;         // horizontal speed at that instant

/*
===========================================================================
  WHAT YOU GAINED, PER RAMP AND PER AIR TIME.

  A different question from board_* above.  That grades ONE TICK -- the clip
  on entry -- and says what it cost.  This grades the whole SEGMENT between
  two transitions and says what you made.

  THE MEASUREMENT IS ENERGY, and that is the only reason the number means
  anything.  E = z + v^2/2g, and gravity is CONSERVATIVE: it moves energy
  between the two terms and never changes the total.  So dE across a segment
  is exactly what air acceleration put in, minus what the ramp bit off, with
  gravity's contribution algebraically zero.  A pure freefall reads +0.  A
  ramp handing back the height you paid for reads +0.  Only your hands move
  this number, which is what "the strafe gain you made" has to mean.

  The obvious alternative -- speed out minus speed in -- reads +203 on a ramp
  where you strafed nothing at all, because most of it is gravity.  It answers
  a question nobody asked.

  Reported as u/s rather than as a height, by asking what that much energy is
  worth AT THE SPEED YOU ARE LEAVING WITH:

      gain = sqrt(v^2 + 2*g*dE) - v

  which is the honest conversion: the same dE is worth less the faster you are
  already going, exactly as the speedometer would show it.

  WHERE THE BOARD IS CHARGED (build 19).  The boundary between an air time and
  the ramp it ends on is taken from the PRE-clip velocity, so the ramp pays for
  the board and the air row is what your hands did in the air and nothing else.
  Before this it was sampled post-clip and the air row ate the whole cost, which
  made a perfect strafe into a bad board read as a bad air time.  See the essay
  at the segment edge in Board_Frame.
===========================================================================
*/
#define SEG_NONE   0
#define SEG_AIR    1
#define SEG_RAMP   2
/*
  BUILD 25 -- THE TOUCHDOWN IS ITS OWN ROW.

  "When you touch down on a ramp you usually don't have a perfect angle, so a bit
  of energy is lost -- split the ramp row into two, one of them just the touch
  down moment, one tick of energy loss, separated from the gain or loss from
  surfing the actual ramp."

  Build 19 moved that cost off the AIR row and onto the RAMP row, and was right
  to: the boundary is taken from the PRE-clip velocity, so a perfect strafe into
  a bad board stopped reading as a bad air time.  But it landed the whole cost on
  the ramp, where it is indistinguishable from the ride -- a ramp row of -12 is
  either a bad landing you could have fixed or a bad line down the face, and
  those are two different things to practise.

  SPLITTING IT IS ONE VALUE MOVED.  Build 19 used the pre-clip energy TWICE, to
  close the air segment and to open the ramp segment.  Now the air still closes
  at the pre-clip value, the ramp opens at the POST-clip one, and the difference
  between them becomes a row of its own.  The three sum to exactly what the two
  summed to, so build 20's accounting invariant -- the rows add up to the run's
  airborne-plus-riding energy -- is untouched, and the number is
  -(v.n)^2 / 2g, which is what Board_Compute already publishes as board_losse and
  the `cost` readout under the strafe bar already draws.  The row and the panel
  agree by construction rather than by coincidence.

  ITS DURATION IS ONE TICK, because that is literally what it is: one call to
  ClipVelocity, inside one physics tick.  It has no percentage -- seq_pct is for
  air rows, where "how much of the available gain did you take" has a closed-form
  denominator, and one tick of clipping has no such thing.
*/
#define SEG_BOARD  3

// Shorter than this is a bounce, not a ride.  One tick is 0.015s.
#define SEG_MINTIME   0.10

// An origin step this large between two rendered frames is a TELEPORT, and a
// teleport moves z by thousands of units -- dE would report it as the best
// strafe of your life.  3000 u/s at 20fps is 150 units, so this cannot fire on
// honest movement.
#define SEG_JUMPDIST  512

/*
===========================================================================
  BUILD 24 -- THE SEGMENT MACHINE, RUN OVER A FILE.

  Build 23's replay drew no strafe bar, no board panel and no segment column, and
  said on screen that it would not: the three are decided by STAT_FS_RAMPCONTACT
  and the PRE-CLIP STAT_FS_BOARDVEL, and the .rec carried neither.  That was an
  honest refusal to guess, and the answer to it is to RECORD the two rather than
  to derive them -- .rec v4 does, and the reader is then only missing a way to
  feed this file from something other than the live stats.

  Three globals do that, and there is deliberately no fourth.

  board_now  is the frame clock.  Live it is cltime; during a build pass it is
             the recording's own run clock, so a segment's duration is the
             duration it HAD rather than the wall time the load pass took.

  rec_wt_build says the values below are the truth this call rather than the
             stats.  Set only inside Watch_BuildSeq, which runs once at load,
             brackets itself in a snapshot of the live list and restores it
             afterwards -- so the replay cannot destroy the column belonging to
             the run you were actually doing when you opened it.  That is the
             build 11 dead-load-key lesson applied before it can bite: two state
             machines, one set of state, and whichever finished last winning.

  board_ov_* are those values.  They are ordinary globals rather than a call
             into cl_watch.qc because this file compiles FIRST and cannot see it.

  WHY A BUILD PASS AND NOT A LIVE REPLAY.  This machine is an accumulator: a row
  is the difference between two moments, and a scrub runs the clock backwards.
  Re-running it from t0 on every frame of a scrub-bar drag would be six thousand
  iterations a frame.  Run once at load it is six thousand iterations once, and a
  seek becomes what Watch_Splits already is -- a count into a table.
===========================================================================
*/
float  board_now;
float  rec_wt_build;
float  board_ov_now;        // the recording's run clock at this sample, seconds
float  board_ov_seq;        // the board counter as of this sample
float  board_ov_riding;     // run_rampcontact, the v4 flags bit
vector board_ov_bnorm;      // the latched arrival plane of the board just taken
vector board_ov_bvel;       // and its pre-clip velocity

// Defined in cl_watch.qc, which compiles much later.  Seq_Push calls it so the
// build pass can capture a row at the instant it is pushed -- the ring SCROLLS
// at SEQ_MAX and the merge rewrites the last row in place, so watching the ring
// from outside cannot tell a scroll from a merge.  `merged` says which happened.
void(float merged) Watch_SeqRow;

/*
  Build 30.  Defined in cl_hud.qc, which compiles after this file -- same
  arrangement as Watch_SeqRow above and for the same reason: the state belongs
  to the file that owns it, and the file that KNOWS a teleport happened is this
  one.

  cl_hud.qc holds three caches that outlive a save-lock load and have to be
  dropped with the segment state Board_Warped drops: the held ramp plane
  (ui_ramp_norm / ui_ramp_time), the low-passed ideal that was computed from it,
  and the energy-rate ring.  Board_ResetContact calls both, so there is one
  answer to "a load happened" rather than two that can drift.
*/
void() HUD_ClearRampHold;
void() HUD_ClearEnergyHistory;

/*
===========================================================================
  BUILD 25 -- "AM I ON A RAMP", ONCE, WITH THE ENGINE'S OWN GATE.

  THE STAT DROPS OUT MID-RIDE, and that is not a bug in the stat.
  PMSrc_Tick clears rampcontact AND rampnormal at the top of every tick
  (pm_source.c:2665-2666) and PMSrc_TryPlayerMove re-derives them only on a tick
  whose trace actually hits the ramp (:1131-1156).  A tick that clears its whole
  move sets neither.  So on some ramps the flag really does alternate 1/0 at
  66.7 Hz -- which at 300 fps is four or five frames of one answer and four or
  five of the other, and is exactly the reported "flickers between two values".

  THE ENGINE ALREADY KNOWS A SHORT GAP IS THE SAME RIDE.  PMSRC_BOARD_AIRGATE is
  0.08s (pm_source.c:1148): a gap shorter than that does not count as a new
  board, which is why boardcount is not inflating into the thousands over one
  ride.  QC had no such rule, so every dropout flipped the segment machine
  RAMP -> AIR -> RAMP, spent a carry and a merge repair on nothing, and re-fired
  the leaving edge -- which is what puts `leaving 1240` back on screen in the
  middle of a ramp you are still on.

  So the hold is the ENGINE'S NUMBER, not an invented hysteresis.  If 0.08 turns
  out to be too short for a real ride, the measurement says so and the constant
  moves; what it must not be is a value chosen because it looked about right.

  ONE ANSWER FOR BOTH READERS.  Board_Frame's segment kind and HUD_RampNormal's
  regime were reading the same stat separately, and HUD_RampNormal already held
  its PLANE for 0.25s while nothing held the CONTACT -- so the two could disagree
  about whether you were on a ramp at all.  They cannot now.

  IDEMPOTENT WITHIN A FRAME, which is what lets both call it.  Board_Frame runs
  first in HUD_Draw and HUD_RampNormal later, both with the same board_now: a
  second call with the same clock re-reaches the same branch and returns the same
  answer.  During a REPLAY Board_Frame does not run at all (the column comes from
  a prebuilt table) and HUD_RampNormal is the only caller, which is why the hold
  cannot live inside Board_Frame.

  A BUILD PASS LEAVES THE LATCH ON THE RECORDING'S CLOCK, and that self-heals
  rather than needing a bracket: cltime is far away from a 0..82s run clock in
  both directions, so the next live frame either fails `now >= lastc` or exceeds
  the gap, and the hold expires immediately.
===========================================================================
*/
#define RAMP_GAP 0.08           // PMSRC_BOARD_AIRGATE, pm_source.c:172

float  ramp_on;                 // the held answer
float  ramp_lastc;              // board_now of the last RAW contact
float  ramp_raw;                // this frame's raw stat, for the debug readout
float  ramp_drops;              // gaps bridged since the last real ride ended

/*
  The same count, CUMULATIVE, and it exists to make the fix falsifiable.

  ramp_drops is per-ride and is the live readout.  This one is never reset except
  by a map change, which makes it the thing a REPLAY can report: the build pass
  runs this whole machine over a file, so `replay status` on a recording says how
  many contact gaps the hold bridged across the entire run.

  That matters because the obvious test does not actually test anything.  Two
  fixtures that differ only in whether the ramp bit drops out produce the same
  number of column rows either way -- with the hold because the ride is never
  split, and WITHOUT it because every fragment is under SEG_MINTIME and the carry
  and the merge put it back together anyway.  Identical output, opposite reasons.
  This counter is the only thing that separates them.
*/
float  ramp_bridged;

/*
  The drop count is per GAP, not per frame.

  Counting inside the hold branch would count rendered frames -- at 300 fps a
  one-tick gap is four or five of them -- and the number that answers "is the
  stat alternating" is how many times it went away, not how long the answer took
  to draw.  So it is the falling edge of the raw stat while the hold is live,
  which is one per gap however the frame rate lands on it.
*/
float  ramp_rawlast;

float(float raw, float now) Board_RampHold =
{
	/*
	  Counted on the gap's TRAILING edge, not its leading one.

	  A falling edge only says the stat went away; whether the ride survived it is
	  not known until the contact comes back inside the window.  Counting the fall
	  would count gaps the hold REFUSED to bridge as though it had bridged them --
	  which is precisely the number the fix must not be allowed to inflate.  So:
	  contact returning while the hold is still up is one bridged gap, exactly.
	*/
	if (raw)
	if (!ramp_rawlast)
	if (ramp_on)
	{
		ramp_drops   = ramp_drops + 1;
		ramp_bridged = ramp_bridged + 1;
	}
	ramp_rawlast = raw;
	ramp_raw     = raw;

	if (raw)
	{
		ramp_lastc = now;
		ramp_on    = TRUE;
		return TRUE;
	}

	// Nested, not `&&`: this file's rule.  No array read here, but the next
	// person to add a term will not know that.
	if (ramp_on)
	if (ramp_lastc > 0)
	if (now >= ramp_lastc)
	if (now - ramp_lastc <= RAMP_GAP)
		return TRUE;

	// The ride is genuinely over; the next one counts its own gaps.
	if (ramp_on)
		ramp_drops = 0;
	ramp_on = FALSE;
	return FALSE;
};

float  seg_kind;            // the segment currently open
float  seg_e0;              // energy when it opened
float  seg_t0;              // the frame clock when it opened
float  seg_valid;           // cleared by a teleport; a voided segment says nothing
vector seg_org;             // last frame's origin, for that guard

/*
  The touchdown that opened the ramp segment currently running.  Build 25.

  HELD RATHER THAN PUSHED AT THE BOUNDARY, and that is the whole of making this
  safe.  Build 20's merge repairs a column that a REFUSED segment has broken: a
  few ticks of lost ramp contact around a bend leave two air rows adjacent with
  nothing between them, and the merge joins them back into the one thing they
  were.  A board row pushed the instant the ramp opened would sit BETWEEN those
  two air rows and stop them merging, and the column would fill with junk rows
  for landings that never happened.

  So the cost waits for the ramp it belongs to.  If that ramp becomes a row, the
  board goes in immediately before it -- which is also the right order, since it
  happened first.  If the ramp is refused for being under SEG_MINTIME, the board
  goes into the carry along with it and the two air rows merge exactly as they do
  today.

  seg_bd_v is the POST-clip speed at the moment of the board, and it has to be
  carried rather than taken at the push: Seq_Push converts dE to u/s at the speed
  you are leaving with, and the speed you leave the RAMP with is not the speed
  you had when the board took its bite.  That is the same mismatch build 19's
  essay is about, one row further down.
*/
float  seg_bd_pend;         // a touchdown is waiting for its ramp to close
float  seg_bd_de;           // its energy, negative
float  seg_bd_v;            // the post-clip speed it happened at

/*
  BUILD 34 -- THE OPEN SEGMENT, PUBLISHED WHILE IT IS STILL OPEN.

      "when you board, present the board energy display on the energy loss/gain
       display as soon as you make contact and it's recorded, for some reason it
       waits for you to leave the ramp"

  It did, and the essay above is why: the touchdown's row is HELD in seg_bd_pend
  until Board_SegmentEnd knows the ramp became a real row, because a board row
  pushed at the boundary would sit between two air rows and stop them merging.
  That reasoning is still right and the ring is still not touched early.

  What was missing is that the numbers were never the problem.  seg_bd_de is
  final on the contact frame (see the SEG_BOARD split in Board_Frame) and the
  ramp's running total is one subtraction away on every frame after it.  So the
  column draws a PROVISIONAL pair from these three, outside the ring, and they
  are replaced by the identical committed rows when the segment closes.

  Spelled HERE rather than in cl_hud.qc on purpose: this is Board_SegmentEnd's
  own arithmetic, and two spellings of one measurement is exactly what the
  hud_seq_units essay in default.cfg argues against.  If the live row and the
  committed row ever disagree, that is a bug in one of two lines rather than a
  question about which file was right.

  Zero when there is nothing open, so a reader needs no second flag.
*/
float  seg_live_kind;       // SEG_* of the open segment, 0 = nothing open
float  seg_live_de;         // its energy so far, carry included
float  seg_live_dur;        // and its duration so far, likewise
float  seg_live_gain;       // the same dE as u/s, for hud_seq_units 0
float  seg_live_bdgain;     // and the held touchdown's, at the speed IT took

/*
  BUILD 18 -- the best this segment could have done, integrated frame by frame.

  Air only.  An air segment's percentage is the honest question "how much of the
  gain that was available to you did you take", and it is answerable in closed
  form because the optimum in free air is a fixed angle: with `a` the accelspeed
  applied and `c = dot(v, wishdir)`,

      2g dE = 2ac + a^2

  (sh_strafe.qc:96-115) which is maximised at c = 0 -- wishdir exactly
  perpendicular to velocity, because AirMove flattens forward and right before
  building wishdir, so the answer is always 90 degrees and never depends on where
  you are pointing now.  So the ceiling per tick is a^2 / 2g, and `a` is
  Strafe_AirGain, which already exists.

  THE CEILING ASSUMES A STRAFE KEY IS HELD, deliberately.  Using the wishspeed
  you actually had would make an airtime with no keys pressed divide by zero and
  read 100% -- "you took all of the nothing that was available".  The question
  being asked is what you could have got, and that presumes you strafed.

  seg_lastt rather than a fixed tick because this integrates per RENDERED frame:
  the client does not run physics and its frame rate is not the tick rate.
*/
float  seg_emax;            // units of height, accumulated
float  seg_lastt;           // cltime of the previous frame

float  gain_kind;           // the finished segment on screen; SEG_NONE = nothing
float  gain_speed;          // u/s, signed
float  gain_de;             // the SAME segment in energy -- build 20, see hud_seq_units
float  gain_dur;            // seconds it lasted
float  gain_time;           // cltime it finished, for the fade

/*
  BUILD 20 -- THE CARRY, and it fixes an accounting bug older than this build.

  Board_SegmentEnd refuses a segment shorter than SEG_MINTIME, and Board_Frame
  refuses one a teleport crossed.  But the transition block advances seg_e0
  UNCONDITIONALLY, so a refused segment's energy landed in neither the row before
  it nor the row after: it was simply gone from the column's sum.

  In u/s that was invisible -- nobody adds up a column of speeds.  Build 20 puts
  energy in that column, and an energy column that does not add up is worse than
  a speed column that never claimed to.  So a segment too short to be a row of
  its own DEPOSITS itself here and the next real row absorbs it.

  A teleported segment is dropped rather than carried, and that is not the same
  decision: its dE is the distance the engine moved you, not anything your hands
  did.  Carrying a 3000-unit height change into the next row would make the
  column fiction in a new and more confident way.
*/
float  seg_carry_de;
float  seg_carry_dur;
float  seg_carry_emax;

/*
  "Something real happened between these two rows, do not sew them together."

  The merge below joins two same-kind rows when what came between them was an
  ARTIFACT -- a bounce off a lip, a one-frame contact break around a bend, a
  sub-threshold blip.  It must not join them across a genuine ground phase or a
  teleport, because those are events the column is entitled to keep separate.
  Set where such an event is noticed, consumed by the next push.
*/
float  seq_break;

/*
===========================================================================
  THE SEQUENCE.  The same measurement, kept instead of thrown away.

  gain_* above is ONE segment -- the last one to close -- and it fades after a
  few seconds.  That answers "how was that ramp".  It cannot answer "how did
  this run go", which is a different question and the one you ask after you
  finish: the launch off the start, then every ramp and every air time in
  order, each with what your hands put into it and how long it lasted.

  So the segments are appended to a ring as they close and drawn as a column by
  the crosshair.  Nothing new is measured -- Board_SegmentEnd already computes
  all of it -- and the ring costs one write per segment.

  THE ROWS ARE NOT ALL THE SAME KIND, and the colour says which:

    the launch   -- the first segment of the run, start zone to first contact
    on a ramp    -- what the ramp gave back
    in the air   -- what you made between two ramps

  It is cleared by a NEW RUN, not by finishing one, so it is still there while
  you walk back to look at it.
===========================================================================
*/
#define SEQ_MAX   24
#define SEQ_FADE  1.0           // seconds the old list takes to go, once a run starts

float  seq_kind[SEQ_MAX];
float  seq_gain[SEQ_MAX];
float  seq_dur[SEQ_MAX];
float  seq_launch[SEQ_MAX];     // TRUE on the one row that is the launch
float  seq_pct[SEQ_MAX];        // % of the available gain taken; -1 = not measured

/*
  BUILD 20 -- the two columns a row needs to be MERGEABLE, and to be honest.

  seq_de is the raw energy delta in world units of height, signed and
  UNCLAMPED.  seq_gain is what that was worth in u/s at the speed you left with,
  which is what the row used to be and still is under hud_seq_units 0.  Both,
  not one: the u/s figure cannot be turned back into energy without the closing
  speed, which was a local and is gone, and the energy figure cannot be turned
  into u/s without it either.

  seq_emax is that row's own ceiling, and storing it is what makes a merge
  correct rather than approximate: a duration-weighted average of two
  percentages is NOT the percentage of the sums once either dE is negative, so
  the merged figure has to be recomputed from the summed numerator and the
  summed denominator.  That is also why seq_de is stored unclamped -- the
  `if (pct < 0) pct = 0` below is a display decision, and a display decision
  must not be baked into the arithmetic that later rows are built from.
*/
float  seq_de[SEQ_MAX];
float  seq_emax[SEQ_MAX];

float  seq_n;
float  seq_fadeat;              // cltime the clearing run started; 0 = not fading
float  seq_laststate;
float  seq_haslaunch;           // the launch row has been claimed for this run

// hud_seq_merge / hud_seq_units / hud_seq_board, read once a frame at the top of
// Board_Frame rather than per row -- cl_board.qc compiles before cl_hud.qc, so
// the globals live here and the registercvar calls stay with the other hud_* ones
// there.
float  seq_merge;
float  seq_units;
float  seq_board;

// What the last push produced, so Board_SegmentEnd can drive the single-line
// readout without computing the physics a second time.  On a merge these are
// the MERGED figures, which is the right answer: if a blip split one ride, what
// the ride was worth is the whole of it.
float  seq_lastgain;
float  seq_lastde;

#define BOARD_PERFECT   0
#define BOARD_GOOD      1
#define BOARD_OKAY      2
#define BOARD_BAD       3
#define BOARD_TERRIBLE  4

string(float g) Board_GradeName =
{
	if (g == BOARD_PERFECT) return "perfect";
	if (g == BOARD_GOOD)    return "good";
	if (g == BOARD_OKAY)    return "okay";
	if (g == BOARD_BAD)     return "bad";
	return "terrible";
};

vector(float g) Board_GradeColor =
{
	if (g == BOARD_PERFECT) return '0.30 1.00 0.45';
	if (g == BOARD_GOOD)    return '0.60 0.95 0.35';
	if (g == BOARD_OKAY)    return '1.00 0.85 0.25';
	if (g == BOARD_BAD)     return '1.00 0.55 0.20';
	return '1.00 0.30 0.30';
};

/*
  The grade table.

  BOTH conditions must hold, and the loss ceiling is relaxed by
  sqrt(speedIn/1500) above 1500 u/s.  That relaxation is a grading
  convention, not physics -- the underlying lossPct is speed-independent --
  and it exists because at 3000 u/s a half-percent bite is a much harder
  thing to achieve than it is at 800.

  85 degrees already implies 0.38% loss and 80 implies 1.52%, so the pair is
  very nearly one constraint; it is kept as two for noise tolerance.
*/
float(float losspct, float approach, float speedin) Board_Grade =
{
	local float f;

	f = sqrt(speedin / 1500);
	if (f < 1)
		f = 1;

	if (losspct <= 0.005 * f && approach >= 85) return BOARD_PERFECT;
	if (losspct <= 0.015 * f && approach >= 80) return BOARD_GOOD;
	if (losspct <= 0.030 * f && approach >= 75) return BOARD_OKAY;
	if (losspct <= 0.050 * f && approach >= 60) return BOARD_BAD;
	return BOARD_TERRIBLE;
};

/*
  BUILD 39 -- THE COST OF A CLIP, AS A HEIGHT, AND THE ONLY DEFINITION OF IT.

  A clip does not move you, so its dE is purely kinetic; ClipVelocity at
  overbounce 1 is an orthogonal projection, so it removes exactly the
  into-the-plane component and |v|^2 - |v'|^2 is exactly (v.n)^2.  That makes
  this closed form EXACT rather than approximate -- there is no better answer to
  compare it against.

  Pulled out of Board_Compute in build 39 for two reasons that turned out to be
  the same reason.  Board_Compute only runs for boards past the 100/25 grading
  thresholds, so below them board_losse described the PREVIOUS board while the
  segment column described this one.  And the column was not using this number
  at all: it took the difference of two energy samples instead, and those two
  samples are half a tick of gravity apart.  See the boundary block in
  Board_Frame.

  Orientation does not matter here and is not performed: the dot is squared.
*/
float(vector vin, vector n) Board_StepE =
{
	local float gravity, into;

	if (n == '0 0 0')
		return 0;

	gravity = serverkeyfloat("sv_gravity");
	if (gravity < 1) gravity = 800;

	into = vin * n;                     // vector*vector is dot
	return (into * into) / (2 * gravity);
};

/*
  Board_Compute -- the whole of it.

  ORIENTATION FIRST.  A BSP plane's normal faces whichever way the brush was
  built, so it may point along the velocity or against it.  Flip it so that
  v . n <= 0 -- "the normal points back at the player" -- and after that
  every sign below is correct in all three components.  Skipping this gives
  a confidently wrong answer, not a slightly wrong one.
*/
void(vector vin, vector n) Board_Compute =
{
	local float speed, rawdot, dot, sina, into, k;
	local float bx, by, ax, ay, before, after, diffsq;
	local vector no;

	speed = vlen(vin);
	if (speed < 0.001)
		return;

	rawdot = (vin * n) / speed;
	no = (rawdot > 0) ? -n : n;         // now vin . no <= 0
	dot = fabs(rawdot);
	if (dot > 1) dot = 1;

	sina = 1 - dot * dot;
	sina = (sina > 0) ? sqrt(sina) : 0;

	into = dot * speed;                 // |v.n|: the speed the clip destroys

	// lossPct is 1 - sinA.  Written as dot^2/(1+sinA) -- the same number by
	// (1-s)(1+s) = 1-s^2 = dot^2 -- because at a near-perfect board sinA is
	// within a rounding error of 1 and the direct subtraction cancels away
	// most of its significant figures.
	board_losspct = (dot * dot) / (1 + sina);
	board_loss    = speed * board_losspct;
	board_kept    = sina * 100;
	board_approach = acos(dot) * DEG_PER_RAD;   // 90 = parallel to the face

	// The signed XYZ, which is what "how much velocity did I lose" means to
	// a player.  dv = -(v.n)n, and z is usually POSITIVE: a ramp takes speed
	// and gives back height.
	board_dv = into * no;

	// Horizontal loss.  On a shallow ramp most of the bite is vertical, so
	// this is much smaller than the 3D figure -- it is not that figure
	// scaled.  Computed as (a^2-b^2)/(a+b) for the same cancellation reason.
	k  = into;
	bx = vin_x;              by = vin_y;
	ax = vin_x + k * no_x;   ay = vin_y + k * no_y;
	before = sqrt(bx*bx + by*by);
	after  = sqrt(ax*ax + ay*ay);
	diffsq = (bx*bx + by*by) - (ax*ax + ay*ay);
	board_lossh = (before + after > 0.001) ? (diffsq / (before + after)) : 0;

	// The same cost as a height, so it can be compared against the energy
	// readout directly.  Build 39: through Board_StepE, which is now also what
	// the segment column spends -- so the two numbers are the same number and
	// not merely two derivations that ought to agree.
	board_losse = Board_StepE(vin, n);

	board_speedin   = speed;
	board_speedin_h = before;
	board_rampdeg   = acos(fabs(no_z)) * DEG_PER_RAD;
	board_grade     = Board_Grade(board_losspct, board_approach, speed);
	board_time      = board_now;
};

/*
  Close the open segment, and decide whether it is worth saying.

  THE TWO EDGES ASKED FOR, and no others:
    - a RAMP ending, however it ends (into air, or by landing) -> report it
    - an AIR time ending BECAUSE A RAMP BEGAN                  -> report it
  Air ending by landing on the ground is not reported: every jump and every
  step off a kerb is an air time, and reporting those would bury the two that
  matter.
*/
void() Seq_Clear =
{
	seq_n = 0;
	seq_fadeat = 0;
	seq_haslaunch = FALSE;

	// The carry belongs to the list it was going to be spent on.  Build 20.
	seg_carry_de = seg_carry_dur = seg_carry_emax = 0;
	seq_break = FALSE;
};

/*
===========================================================================
  BUILD 20 -- THE LIST COMES BACK WITH THE SAVE.

  "When the player loads their lock with the timer and all, can you also
  restore the last boarding/air energy values on the left side of the screen?"

  THE RECORDER'S MARK DOES NOT TRANSFER, and that is the first thing to get
  right.  Rec_ViewLoaded rewinds its sidecar with `rec_rp_lines = mark`, which is
  legal because that buffer is APPEND-ONLY -- a mark is a truncation and the
  lines past it are unreachable.  This ring is neither: it scrolls at SEQ_MAX,
  so after a scroll row 0 is not the row it was, and the merge above rewrites
  the LAST row in place.  A remembered length would restore the wrong rows.

  So it is a full copy, and one snapshot rather than one per slot: per-slot
  would be 33 x 24 x 7 floats where the recorder affords per-slot because its
  mark is a single float.  Keyed by id, so save/try/load and save/try/save/load
  -- every ordering anyone actually does -- are exact, and a load of some OTHER
  slot falls through to the file rather than restoring the wrong list.

  The IO half lives in cl_replay.qc: this file compiles FIRST, so it has none of
  the file builtins or the map-name helper, and cl_replay.qc already owns the
  slot paths and the STAT_FS_SLSEQ edge detector these hook into.
===========================================================================
*/
float  seq_mk_id;               // which slot the snapshot belongs to; -1 = none
float  seq_mk_n;
float  seq_mk_haslaunch;
float  seq_mk_kind[SEQ_MAX];
float  seq_mk_gain[SEQ_MAX];
float  seq_mk_de[SEQ_MAX];
float  seq_mk_emax[SEQ_MAX];
float  seq_mk_dur[SEQ_MAX];
float  seq_mk_pct[SEQ_MAX];
float  seq_mk_launch[SEQ_MAX];

/*
===========================================================================
  BUILD 25 -- AND THE SEGMENT YOU ARE IN THE MIDDLE OF.

  Build 20 restored the finished ROWS and deliberately threw away the OPEN one:
  Seq_Read called Board_Warped unconditionally, which is "I did not travel here,
  I was put here" and kills the segment so its pre-teleport e0 cannot be reported
  as something your hands did.

  That is right for every other warp and WRONG for a save-lock load, which is the
  one teleport that puts you back exactly where the open measurement was taken.
  The reported symptom is precise: save mid-flight, load, touch down on a ramp,
  and the air row reports the energy since the LOAD rather than since you left
  the last ramp -- so the number you loaded the save to look at is the one thing
  the load destroys.  Everything around it is already restored verbatim: the run
  clock, the splits, the checkpoint latches, the recorder's own line count.

  FIVE FIELDS, AND ONE OF THEM IS NOT WHAT YOU WOULD STORE FIRST.  seg_t0 is a
  frame clock, and a frame clock means nothing on the other side of a map restart
  -- `retry` rebuilds the whole VM and cltime starts again from zero.  So the
  DURATION SO FAR goes on disk and the reader re-bases it against its own clock.
  Same reason the .rec's stage slicer rewrites timestamps rather than storing a
  tbase: a number that is only meaningful next to a clock nobody kept is worse
  than one that is visibly wrong.

  seg_org is NOT stored, and cannot usefully be: the 512-unit teleport guard in
  Board_Frame would fire on the very frame of the restore, because a load moved
  you further than 512 units and that is exactly what the guard is for.  A
  restore is the one case where being moved is expected, so the guard is
  suspended instead -- see ui_rs_armed, which build 26 rewrote after measuring
  that build 25's one-frame version of it was not long enough.
===========================================================================
*/
// Defined beside Board_Clear, which is where it belongs thematically; promised
// here because Seq_Unmark and Seq_Read both call it, and both are above it.
void() Board_Warped;

float  seq_mk_ok;               // the snapshot carries an open segment
float  seq_mk_skind;
float  seq_mk_se0;
float  seq_mk_semax;
float  seq_mk_sdur;
float  seq_mk_svalid;

// And the touchdown that opened it, if the ramp has not closed yet.  Saving
// halfway down a ramp is an ordinary thing to do and the board row belongs to
// that ride; without these the save would restore the ride and lose its landing.
float  seq_mk_bdpend;
float  seq_mk_bdde;
float  seq_mk_bdv;

/*
===========================================================================
  A RESTORE IS IN FLIGHT.  Build 26, and it replaces build 25's seg_reseed.

  Both the segment machine and the energy anchor re-base themselves when the
  position moves more than SEG_JUMPDIST in a frame, because that is a teleport
  and a teleport's height change is not something your hands did.  A restore is
  the one teleport where it IS -- you are being put back where the measurement
  was taken -- so both guards have to be told to sit this one out.

  BUILD 25 TOLD THEM ONCE AND THAT IS NOT ENOUGH.  seg_reseed was a one-shot,
  consumed by the next call whether or not the teleport had actually arrived, on
  the assumption that the save event and the new origin land in the same frame.
  They do not have to.  Measured, loading a save from ~580 units away:

      save002   open 1 1056.3063 5.5572 0.1521 1      <- valid 1
      save003   open 1 1056.3063 6.6126 0.3339 0      <- valid 0, after a load

  The e0 came back and the segment was then voided anyway, because the exemption
  had been spent on a quiet frame before the position step arrived.  The energy
  anchor failed the same way in the same test and by the same one frame.

  SO THE EXEMPTION IS HELD UNTIL WE ARRIVE, rather than counted down.  A restore
  arms it with WHERE IT LANDS -- the origin the save was taken at, which travels
  in seq.txt beside the anchor -- and both guards skip while it is armed.  The
  disarm happens at the END of Board_Frame, after both have read it, on the first
  frame the position is actually within reach of that destination.

  A pre-build-26 file carries no destination, so nothing arms and the load
  behaves as build 25 did.  That is stated rather than papered over: those files
  are development scratch, and inventing a destination for them would be
  inventing the very number this exists to stop guessing at.
===========================================================================
*/
float  ui_rs_armed;             // a restore's teleport has not landed yet
vector ui_rs_dest;              // where it will land

/*
===========================================================================
  BUILD 26 -- THE ENERGY ANCHOR, WHICH THE SAME TELEPORT ALSO DESTROYED.

  Momentum's energy reference is "the height reachable above your LAST JUMP
  POSITION", so the `e` by the crosshair is measured from the ground you last
  jumped off.  HUD_UpdateJumpRef tracks that, and re-bases it whenever you move
  more than SEG_JUMPDIST in a frame:

      if (!ui_jump_have || vlen(org - ui_jump_lastorg) > SEG_JUMPDIST)
          ui_jump_z = org_z;

  which is right for a run-voiding teleport -- one moves z by thousands and
  would otherwise read as the jump of a lifetime -- and wrong for the one
  teleport that puts you back where the measurement was taken.  A save-lock load
  is almost always further than 512 units from where you pressed the key, so the
  reference became the height you landed at and `e` read about zero.  That is
  "loading a save-lock completely forgets your energy anchor, making it useless",
  exactly, and it is the same sentence as the open segment above with a different
  noun in it.

  WHY THESE LIVE IN THIS FILE.  They were declared in cl_hud.qc, which
  cl_progs.src compiles AFTER this one, so the writer could not see them.  They
  belong here anyway: this file owns SEG_JUMPDIST and the identical 512-unit
  rule, and cl_hud.qc's own declaration comment already said so -- "teleport
  guard, same 512-unit rule as cl_board.qc".  Same move build 25 made for
  DEG_PER_RAD, and for the same reason: one speller, in the VM that needs it
  first.  cl_hud.qc keeps a pointer comment and every reader there is unchanged.
===========================================================================
*/
float  ui_jump_z;           // z of the ground we last jumped from
float  ui_jump_have;        // FALSE until we have seen ground at all
float  ui_ground_z;         // last z seen while standing; the jump latches THIS,
                            // not the origin one frame later, which is already
                            // four units up at 268 u/s and 66 Hz
float  ui_was_onground;
vector ui_jump_lastorg;     // the teleport guard's previous position

// The snapshot's copy, beside the other seq_mk_* fields it travels with.
// seq_mk_aorg is WHERE THE SAVE WAS TAKEN, which is what arms ui_rs_dest above:
// the save's own origin is by definition where its load puts you back.
float  seq_mk_ajz;
float  seq_mk_agz;
float  seq_mk_aong;
float  seq_mk_ahave;
vector seq_mk_aorg;

/*
  Put an open segment back, from either path.

  board_now is already this frame's -- Board_Frame sets it before calling
  Seq_Frame, which is what reaches here -- so the rebase lands on the clock the
  next dt will be measured against.
*/
void(float kind, float e0, float emax, float dur, float valid) Seq_OpenRestore =
{
	seg_kind  = kind;
	seg_e0    = e0;
	seg_emax  = emax;
	seg_t0    = board_now - dur;
	seg_valid = valid;
	seg_lastt = board_now;
};

/*
  Put the energy anchor back, from either path -- and arm the in-flight guard.

  One function for the warm and the cold restore for the same reason Seq_Load
  exists beside the snapshot copy: four fields and an arming, written twice, is
  five chances to leave one behind -- and the one that would be left behind is
  the arming, whose absence makes the whole restore silently do nothing one frame
  later.

  IT ARMS FOR THE SEGMENT MACHINE TOO, and that is why this is the only arming
  site.  Seq_OpenRestore used to set its own one-shot; both restores happen in
  the same breath on both paths, and one flag armed once with one destination
  cannot get out of step with itself the way two could.
*/
void(float jz, float gz, float ong, float have, vector dest) Seq_AnchorRestore =
{
	ui_jump_z       = jz;
	ui_ground_z     = gz;
	ui_was_onground = ong;
	ui_jump_have    = have;

	ui_rs_dest  = dest;
	ui_rs_armed = TRUE;
};

void(float id) Seq_Mark =
{
	local float i;

	seq_mk_id        = id;
	seq_mk_n         = seq_n;
	seq_mk_haslaunch = seq_haslaunch;

	seq_mk_ok    = (seg_kind != SEG_NONE);
	seq_mk_skind = seg_kind;
	seq_mk_se0   = seg_e0;
	seq_mk_semax = seg_emax;
	seq_mk_sdur  = board_now - seg_t0;
	seq_mk_svalid = seg_valid;

	seq_mk_bdpend = seg_bd_pend;
	seq_mk_bdde   = seg_bd_de;
	seq_mk_bdv    = seg_bd_v;

	// The energy anchor.  Unconditional -- unlike the open segment there is no
	// "there isn't one" state to guard: ui_jump_have FALSE is itself the answer
	// and restoring it is how a save taken before the first ground contact comes
	// back saying so rather than claiming a reference at z = 0.
	seq_mk_ajz   = ui_jump_z;
	seq_mk_agz   = ui_ground_z;
	seq_mk_aong  = ui_was_onground;
	seq_mk_ahave = ui_jump_have;

	/*
	  And where this save IS, which is where loading it will put you back.

	  ui_jump_lastorg rather than a fresh read of the origin, deliberately: it is
	  the position HUD_UpdateJumpRef saw this frame, i.e. the same feet position
	  the anchor above was decided against, so the two cannot describe different
	  moments.  Board_Frame's org would be the same value one call later; this one
	  is the value the guard itself will compare against on the way back.
	*/
	seq_mk_aorg  = ui_jump_lastorg;

	for (i = 0; i < seq_n; i = i + 1)
	{
		seq_mk_kind[i]   = seq_kind[i];
		seq_mk_gain[i]   = seq_gain[i];
		seq_mk_de[i]     = seq_de[i];
		seq_mk_emax[i]   = seq_emax[i];
		seq_mk_dur[i]    = seq_dur[i];
		seq_mk_pct[i]    = seq_pct[i];
		seq_mk_launch[i] = seq_launch[i];
	}
};

/*
  Put the list back where that save left it.  Returns FALSE if the snapshot is
  not this slot's, which is the caller's cue to try the file.

  seq_laststate is consumed rather than left, and that is load-bearing.  Seq_Frame
  runs LATER in the same frame (this is driven from CSQC_UpdateView, the HUD draws
  after it) and would see the timer go ARMED -> RUNNING as a NEW RUN, start the
  one-second fade and take the list straight back off the screen.  A load is not
  a new run, it is the same run continued, so the edge is genuinely not there.
*/
float(float id) Seq_Unmark =
{
	local float i;

	if (seq_mk_id != id)
		return FALSE;

	seq_n         = seq_mk_n;
	seq_haslaunch = seq_mk_haslaunch;
	seq_fadeat    = 0;

	for (i = 0; i < seq_mk_n; i = i + 1)
	{
		seq_kind[i]   = seq_mk_kind[i];
		seq_gain[i]   = seq_mk_gain[i];
		seq_de[i]     = seq_mk_de[i];
		seq_emax[i]   = seq_mk_emax[i];
		seq_dur[i]    = seq_mk_dur[i];
		seq_pct[i]    = seq_mk_pct[i];
		seq_launch[i] = seq_mk_launch[i];
	}

	// Build 25.  The open segment, if that save had one -- and Board_Warped
	// otherwise, because a save taken while standing on the floor genuinely has
	// nothing open and the segment that IS open here belongs somewhere else.
	if (seq_mk_ok)
	{
		Seq_OpenRestore(seq_mk_skind, seq_mk_se0, seq_mk_semax,
		                seq_mk_sdur, seq_mk_svalid);
		// After the restore, which does not touch these -- and Board_Warped in
		// the else branch clears them, which is what the else branch means.
		seg_bd_pend = seq_mk_bdpend;
		seg_bd_de   = seq_mk_bdde;
		seg_bd_v    = seq_mk_bdv;
	}
	else
		Board_Warped();

	/*
	  Build 26.  The energy anchor, and it is OUTSIDE the seq_mk_ok branch.

	  The open segment and the anchor answer different questions and a save can
	  legitimately have one without the other: standing on the start block there
	  is no open segment and there IS an anchor -- the block you are about to jump
	  off, which is the whole reference the run will be measured against.  Putting
	  this inside the branch above would have restored the anchor only for saves
	  taken in mid-air, which is the half that needs it least.
	*/
	Seq_AnchorRestore(seq_mk_ajz, seq_mk_agz, seq_mk_aong, seq_mk_ahave,
	                  seq_mk_aorg);

	seq_laststate = getstatf(STAT_FS_TIMERSTATE);
	return TRUE;
};

/*
  Append one row from a file.  Cold path only -- the warm one copies wholesale.

  The launch flag is NOT stored on disk: it is "the first air row", recomputed
  here, which keeps the row a field shorter and removes a way for the file to
  disagree with itself.
*/
void(float kind, float de, float emax, float dur, float pct, float gain) Seq_Load =
{
	if (seq_n >= SEQ_MAX)
		return;

	seq_kind[seq_n]   = kind;
	seq_de[seq_n]     = de;
	seq_emax[seq_n]   = emax;
	seq_dur[seq_n]    = dur;
	seq_pct[seq_n]    = pct;
	seq_gain[seq_n]   = gain;
	seq_launch[seq_n] = (!seq_haslaunch && kind == SEG_AIR);
	if (seq_launch[seq_n])
		seq_haslaunch = TRUE;
	seq_n = seq_n + 1;
};

/*
  pr_dumpplatform emits no prototype for builtin 652, so it is named rather than
  numbered -- exactly as cl_replay.qc has to declare it.
*/
float(string fname) fremove = #0:fremove;

/*
  The list's file, beside the save's own run.rec and run.view.

  serverkey("map") and NOT the `mapname` global: in CSQC that reads
  "maps/surf_666.bsp", which is the build 17 trap that wrote every sidecar to
  data/runs/maps/surf_666.bsp_... for three builds without anyone noticing.
*/
// Build 25: the slot name comes from FS_SaveSlotName now.  It was spelled here,
// in Rec_SavePath and in SL_NN -- three copies of one directory name that four
// files have to land in, across two VMs.  See the essay in sh_defs.qc.
string(float id) Seq_Path =
{
	return sprintf("data/saves/%s/save%s/seq.txt",
	               serverkey("map"), FS_SaveSlotName(id));
};

/*
  A save was taken: snapshot it, and put it on disk.

  Both, for the reason Rec_ViewSaved gives about its own pair -- the snapshot is
  this session's fast path and the file is the only thing that survives a map
  restart, which is what `retry` and a later session both are.

  THE fremove IS NOT TIDINESS.  A save taken with an empty list must not leave
  the PREVIOUS save's file at this path to be paired with the fresh state.txt
  the server is about to write: a segment list from the wrong attempt is worse
  than none, because it looks like it worked.

  The grammar is the additive one this project uses everywhere -- one key per
  line, any order, unknown keys skipped -- so a later build can add a column and
  an older build still reads the file.  `launch` is deliberately not a column:
  it is "the first air row" and is recomputed, which keeps the sprintf inside
  the eight-parameter varargs cap with a slot to spare.
*/
void(float id) Seq_Write =
{
	local float fh, i;

	if (id < FS_RETRY_SLOT || id > FS_MAXSAVES)
		return;

	Seq_Mark(id);
	fremove(Seq_Path(id));

	/*
	  BUILD 26: THERE IS NO LONGER A "NOTHING TO WRITE" CASE, and the guard that
	  used to be here had to go with it.

	  Build 25 wrote the file when there were rows OR an open segment, on the
	  argument that an open segment is worth a file on its own -- saving on the
	  way up your first ramp has no finished rows and that is when the open one
	  matters most.  Both halves are still true and both are now beaten by a third
	  thing: the ENERGY ANCHOR is unconditional.  A save taken standing on the
	  start block has no rows and nothing open, and it has the one reference the
	  whole run will be measured against.  Refusing to write that save's file is
	  refusing to save the thing it was taken for.

	  The consequence, stated because it is a real change: loading a save that had
	  no rows now CLEARS the list, where before it left a stale one.  That is the
	  correct answer -- the file says zero rows and it is this slot's file -- and
	  the "leave it alone" policy in the header above was always about the case
	  where there is no file at all, which a retry from an older build is.
	*/
	fh = fopen(Seq_Path(id), FILE_WRITE);
	if (fh < 0)
	{
		dprint(sprintf("seq: cannot write %s\n", Seq_Path(id)));
		return;
	}

	dprint(sprintf("seq: save %g -- %g row(s) -> %s\n", id, seq_n, Seq_Path(id)));

	fputs(fh, "FTESURF-SEQ 1\n");
	fputs(fh, sprintf("n %g\n", seq_n));
	for (i = 0; i < seq_n; i = i + 1)
		fputs(fh, sprintf("row %g %.4f %.4f %.4f %.2f %.4f\n",
		                  seq_kind[i], seq_de[i], seq_emax[i],
		                  seq_dur[i], seq_pct[i], seq_gain[i]));

	/*
	  Build 25.  The segment still open at the save, as a DURATION rather than a
	  t0 -- see the Seq_Mark essay for why a frame clock does not survive a retry.

	  Additive, and the version deliberately stays at 1: the grammar's own rule is
	  one key per line, any order, unknown keys skipped, which the `.rec` header
	  and state.txt both follow.  Nothing warns on an unknown seq key the way
	  reccheck.py does for the .rec -- the reason VIEW went to 2 in build 22 -- and
	  an older build reading this file simply keeps build 24's behaviour, which is
	  to have no open segment.  Degrading to the previous build is the best a
	  forward-compatibility story gets.
	*/
	if (seq_mk_ok)
		fputs(fh, sprintf("open %g %.4f %.4f %.4f %g\n",
		                  seq_mk_skind, seq_mk_se0, seq_mk_semax,
		                  seq_mk_sdur, seq_mk_svalid ? 1 : 0));

	/*
	  A LINE OF ITS OWN rather than two more fields on `open`, and the reason is
	  the eight-parameter varargs cap: `open` is already a format plus five, and
	  two more would sit exactly on the limit with nothing left for the next
	  person.  fteqcc is silent when that cap is exceeded, which is the worst
	  possible failure mode for a file format.  Two short lines cost nothing and
	  the grammar was designed for exactly this.
	*/
	if (seq_mk_bdpend)
		fputs(fh, sprintf("board %.4f %.4f\n", seq_mk_bdde, seq_mk_bdv));

	/*
	  Build 26.  The energy anchor -- see the essay beside ui_jump_z.

	  UNCONDITIONAL, unlike `open` and `board`.  There is no "no anchor" state to
	  omit the line for: ui_jump_have FALSE is itself a fact about this save (the
	  ground had never been seen) and a file that omitted the line would be
	  indistinguishable from a build-25 file, which restores nothing.  Writing it
	  always is what makes the reader's `if (!gotanchor)` mean "an older build
	  wrote this" rather than "one of two things".

	  Version stays FTESURF-SEQ 1, on the grammar's own rule: one key per line,
	  any order, unknown keys skipped.  A build-25 reader meets `anchor`, skips
	  it, and keeps build 25's behaviour -- which is the behaviour this fixes, so
	  degrading to it is exactly right.
	*/
	fputs(fh, sprintf("anchor %.4f %.4f %g %g\n",
	                  seq_mk_ajz, seq_mk_agz,
	                  seq_mk_aong ? 1 : 0, seq_mk_ahave ? 1 : 0));

	/*
	  A LINE OF ITS OWN, for the reason `board` above has one: `anchor` is already
	  a format plus four, and three more would put it two past the eight-parameter
	  varargs cap that fteqcc exceeds SILENTLY.  The grammar was designed for this
	  and two short lines cost nothing.

	  This is where the load will put you back, and it is what lets the 512-unit
	  guards tell a restore's teleport from any other one -- see ui_rs_dest.  A
	  file without it is a pre-build-26 file and loads as build 25 did.
	*/
	fputs(fh, sprintf("anchorpos %.3f %.3f %.3f\n",
	                  seq_mk_aorg_x, seq_mk_aorg_y, seq_mk_aorg_z));

	fclose(fh);
};

/*
  A save was loaded: put the list back.

  WARM -- the snapshot is this slot's, so copy it.  Free and exact.
  COLD -- a different slot, a map restart, or a later session: read the file.
          This is the ONLY path a `retry` can take, because map_restart destroys
          this VM and every global in it.

  A load with nothing either way leaves the list alone rather than clearing it,
  which is Rec_ViewLoaded's policy verbatim and for the same reason: a list that
  is stale for the first half is better than one that is absent for the second.
  Hence the file is opened BEFORE anything is cleared.
*/
void(float id) Seq_Read =
{
	local float fh, gotopen, gotanchor;
	local float ajz, agz, aong, ahave;
	local vector aorg;
	local string l;

	if (id < FS_RETRY_SLOT || id > FS_MAXSAVES)
		return;

	/*
	  BUILD 25: Board_Warped IS NO LONGER UNCONDITIONAL, and that is the fix.

	  It used to run first, on every path, so the segment you were in the middle
	  of died before either restore could speak.  It is still exactly right for a
	  save that had nothing open, and for a file that does not carry the key -- so
	  it moved to the places that mean "there is nothing to put back" rather than
	  sitting above them all.  Seq_Unmark does its own; this is the cold path's.
	*/
	if (Seq_Unmark(id))
		return;

	fh = fopen(Seq_Path(id), FILE_READ);
	if (fh < 0)
	{
		// No file at all.  The list is left alone (see the header) but the open
		// segment cannot be: whatever it is, it was measured before the teleport.
		Board_Warped();
		return;
	}

	Seq_Clear();
	gotopen   = FALSE;
	gotanchor = FALSE;

	// Seeded because fteqcc cannot see that gotanchor gates every read of them,
	// and it warns rather than trusting the reader -- which is the right way
	// round, since the alternative is a silently uninitialised anchor.
	ajz = agz = aong = ahave = 0;
	aorg = '0 0 0';

	// Only the file may set this on the cold path: a pending touchdown belongs to
	// a ramp segment, and the one that is open right now is not that ramp.
	seg_bd_pend = FALSE;

	l = fgets(fh);
	while (l)
	{
		tokenize(l);
		if (argv(0) == "row")
			Seq_Load(stof(argv(1)), stof(argv(2)), stof(argv(3)),
			         stof(argv(4)), stof(argv(5)), stof(argv(6)));
		else if (argv(0) == "open")
		{
			Seq_OpenRestore(stof(argv(1)), stof(argv(2)), stof(argv(3)),
			                stof(argv(4)), stof(argv(5)));
			gotopen = TRUE;
		}
		else if (argv(0) == "board")
		{
			seg_bd_de   = stof(argv(1));
			seg_bd_v    = stof(argv(2));
			seg_bd_pend = TRUE;
		}
		/*
		  COLLECTED, NOT APPLIED, because the destination is on its own line and
		  the grammar says the keys may come in any order.  Applying `anchor` the
		  moment it is read would arm the in-flight guard with whatever
		  ui_rs_dest happened to hold -- and on the one path that matters, the
		  cold retry, that is a value from a VM that no longer exists.
		*/
		else if (argv(0) == "anchor")
		{
			ajz       = stof(argv(1));
			agz       = stof(argv(2));
			aong      = stof(argv(3));
			ahave     = stof(argv(4));
			gotanchor = TRUE;
		}
		else if (argv(0) == "anchorpos")
			aorg = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
		l = fgets(fh);
	}
	fclose(fh);

	// A build-24 file, or a save taken standing still.  Either way there is no
	// open segment to put back and the live one belongs somewhere else.
	if (!gotopen)
		Board_Warped();

	/*
	  A build-25 file has no `anchor` key, and the honest answer to that is to
	  leave the live reference exactly where it is.

	  There is no better fallback available and inventing one would be worse than
	  the bug: the load has already moved you, so "use where you are now" is the
	  build-25 behaviour this exists to fix, and "use where you were" is a
	  position that belongs to a different place on the map.  Doing nothing means
	  the guard in HUD_UpdateJumpRef re-bases as it always did -- build 25's
	  behaviour, reached deliberately rather than by omission.
	*/
	// AFTER Board_Warped above, which clears the in-flight arming along with
	// everything else a warp invalidates -- so the restore has to be the last
	// word rather than the first.
	if (gotanchor)
		Seq_AnchorRestore(ajz, agz, aong, ahave, aorg);
	else
		dprint(sprintf("seq: save %g has no anchor line -- pre-build-26 file, "
		               "the energy reference will re-base\n", id));

	// See Seq_Unmark: the state edge this load is about to produce is not a new
	// run, and Seq_Frame would otherwise fade the list we just restored.
	seq_laststate = getstatf(STAT_FS_TIMERSTATE);
	Seq_Mark(id);
};

/*
  `retry` -- write the list NOW, before the map restart takes the VM.

  Rec_ViewRetry's essay applies word for word: this runs synchronously inside
  the engine's `retry`, which offers the command to CSQC before it queues
  map_restart, and fclose writes through COM_WriteFile unconditionally.  So the
  bytes are down before the builtin returns and there is no race.
*/
void() Seq_Retry =
{
	Seq_Write(FS_RETRY_SLOT);
};

/*
  FORGET THE SURFACE YOU WERE ON.  Build 30.

  Board_Warped kills the open SEGMENT on a save-lock load, and deliberately
  nothing else.  That left every CONTACT reading alive across the teleport, and
  it is what "the locked position shows surface contact and an energy reading,
  wrong until you touch the ramp again" actually is:

    board_time / board_grade / board_loss / board_speedin_h   the `contact NNN`
      and `cost NN` rows, alive for hud_board_fade -- THREE SECONDS by default;
    leave_time / leave_speed                                  the `leaving NNN`
      row, same three seconds, and a load that lands you off the ramp fires a
      fresh one on the falling edge with whatever speed was current;
    gain_kind / gain_time / gain_de                           the `ramp +NN e`
      row above them;
    ramp_on / ramp_lastc                                      RAMP_GAP of held
      "you are on a ramp", which bridges the load itself;
    ui_ramp_norm / ui_ramp_time (cl_hud.qc)                   RAMPHOLD, 0.25s of
      the PREVIOUS ramp's plane -- and this one is not merely cosmetic, it feeds
      Strafe_IdealTurnPlane, so the strafe bar grades you against a plane you
      are no longer anywhere near;
    ui_ehist_* (cl_hud.qc)                                    hud_strafe_window,
      two seconds of energy samples taken on the other side of the teleport.

  Every one of those was reachable ONLY from a map change, through
  Board_ResetRun / HUD_ClearTurnHistory.  A load is the other event that makes
  them all meaningless, and it never called anything.

  BOARD_SEQ IS SYNCED, NOT ZEROED, and that is the one line here that is not
  obvious.  It is "the last run_boardcount we acted on", the engine's counter is
  monotonic across a load, and zeroing it would make the very next frame see an
  edge and replay the PREVIOUS board -- normal, pre-clip velocity and all -- as
  though you had just landed on it.  Board_ResetRun still zeroes it afterwards,
  because on a map change the edict is fresh and the counter really is 0.
*/
void() Board_ResetContact =
{
	board_seq = getstatf(STAT_FS_BOARDCOUNT);

	board_time = 0;
	board_riding = 0;
	leave_time = leave_speed = 0;

	gain_kind = SEG_NONE;
	gain_time = 0;
	gain_de   = 0;

	ramp_on = ramp_lastc = ramp_raw = ramp_rawlast = ramp_drops = 0;
	ramp_bridged = 0;

	// The touchdown that was waiting for a ramp on the far side of the teleport
	// to close it.  Left alive it attaches to the next ramp instead, reporting a
	// landing that happened somewhere else.
	seg_bd_pend = seg_bd_de = seg_bd_v = 0;

	HUD_ClearRampHold();
	HUD_ClearEnergyHistory();
};

/*
  The save handshake's third listener, and it needs its own counter.

  cl_replay.qc and cl_saveloc.qc each watch STAT_FS_SLSEQ with a latch of their
  own so neither can steal the other's edge; this is the third and follows the
  same rule.  The seeding guard is copied verbatim: a client that joined
  mid-session must not replay events it never saw.

  Called from Seq_Frame, AFTER its state-edge block -- see Seq_Unmark for why
  the order is not a preference.  Seq_Frame in turn runs at the top of
  Board_Frame, before the segment transition, so a load's stale open segment is
  dead before it can close a row from a pre-teleport e0.
*/
float  seq_slseq;

void() Seq_SaveEvents =
{
	local float seq, op, id;

	seq = getstatf(STAT_FS_SLSEQ);
	if (seq == seq_slseq)
		return;

	op = getstatf(STAT_FS_SLOP);
	id = FS_SlopId(op);
	op = FS_SlopOp(op);

	dprint(sprintf("seq: event seq %g op %g id %g (had %g)\n", seq, op, id, seq_slseq));

	// A retry is honoured whatever the counter says: it is the one event whose
	// VM is brand new, so the seeding guard would reject every one of them.
	if (op == SLOP_RETRY)
	{
		Board_ResetContact();
		Seq_Read(FS_RETRY_SLOT);
	}
	else if (seq_slseq != 0 || seq == 1)
	{
		if (op == SLOP_SAVED)
			Seq_Write(id);
		else if (op == SLOP_LOADED)
		{
			/*
			  BEFORE Seq_Read, not after.  Seq_Read restores the open segment and
			  the energy anchor out of the save, and Board_ResetContact must not
			  land on top of that -- it would clear the arming Seq_AnchorRestore
			  just set (see the ordering essay in Board_Warped, which makes the
			  same point about the same one-shot).

			  A SAVE is not cleared: writing one does not move you, so every
			  contact reading is still about the surface you are actually on.
			*/
			Board_ResetContact();
			Seq_Read(id);
		}
	}

	seq_slseq = seq;
};

/*
  Append one closed segment.

  Every valid segment goes in, including an air time that ends by LANDING --
  which the single-line readout below deliberately drops, because every jump and
  every step off a kerb is an air time and reporting each one would bury the two
  that matter.  A column can carry them: in a column they are the shape of the
  run rather than an interruption, and on a surf map a segment that ends on the
  floor is exactly the one you want to see.

  The ring scrolls rather than growing.  A long map closes more segments than
  fit on screen and the recent ones are the ones being read.

  BUILD 20 -- IT ALSO MERGES, and the arithmetic moved in here to allow it.

  "Sometimes you follow a ramp around a bend and get two board reports in a row,
  or two air reports in a row -- join it so it has to be air/ramp/air/ramp."

  The state machine never emitted RAMP->RAMP directly; it cannot, the transition
  is guarded on the kind actually changing.  Adjacency comes from a segment that
  existed and was REFUSED -- a few ticks of lost ramp contact around a bend, a
  one-frame ground touch on a lip, a teleport -- leaving its two neighbours next
  to each other with nothing between them.

  So a merge is a repair, not a rewrite: the two rows really were one thing, and
  the row they become is recomputed from the summed energy rather than averaged
  from the two displays.  The u/s figure is recomputed at the LATEST closing
  speed, which is the honest conversion for a segment that ended there.

  What it must NOT do is sew across something real -- see seq_break.
*/
/*
  What a given dE is worth as SPEED, at the speed you are leaving with.

  Split out in build 34 because the live rows have to convert exactly the way the
  committed rows do: a provisional row that changed its number the instant it was
  committed would be worse than not drawing one.  The reasoning about WHY it is
  the closing speed is at the call site in Seq_Push, where the merge case makes
  it interesting.

  Sign-carried.  The radicand can only go negative if you lost more energy than
  your entire current speed is worth, which is a wall; -v is the true reading
  there ("everything you had").
*/
float(float de, float v, float gravity) Seq_Gain =
{
	local float radicand;
	radicand = v * v + 2 * gravity * de;
	if (radicand > 0)
		return sqrt(radicand) - v;
	return 0 - v;
};

void(float kind, float de, float emax, float dur, float v, float gravity) Seq_Push =
{
	local float i, p, merged;

	// A new run is fading the old list out.  The first row of the new run ends
	// that immediately -- fading out under something that is already filling in
	// would read as a glitch, not as a transition.  Before the merge test on
	// purpose: the first row of a run has nothing to merge into.
	if (seq_fadeat > 0)
		Seq_Clear();

	/*
	  NESTED IFS, NOT `&&`, and this one is not stylistic.

	  QuakeC's && is OP_AND and evaluates BOTH sides, so
	  `seq_n > 0 && seq_kind[seq_n - 1] == kind` reads seq_kind[-1] on the first
	  push of every run.  That is a boundcheck failure in the CLIENT VM, which
	  takes the renderer down with it -- and an empty list is the state every
	  single run begins in, so it would fail immediately and always.
	*/
	p = -1;
	if (seq_merge)
	if (kind != SEG_BOARD)          // build 25: each landing is its own, always
	if (seq_merge >= 2 || !seq_break)
	if (seq_n > 0)
	if (seq_kind[seq_n - 1] == kind)
		p = seq_n - 1;

	// Latched BEFORE the else branch, which assigns p a fresh row and would
	// otherwise make `p >= 0` true in both cases.  Build 24's capture hook is the
	// only reader and it needs exactly this distinction.
	merged = (p >= 0);

	if (p >= 0)
	{
		de   = de   + seq_de[p];
		emax = emax + seq_emax[p];
		dur  = dur  + seq_dur[p];
	}
	else
	{
		if (seq_n >= SEQ_MAX)
		{
			// SEVEN arrays now.  Forgetting one here is the easiest bug in this
			// file to write and the hardest to see: the column would keep drawing,
			// with one field a row out of step with the rest.
			for (i = 0; i < SEQ_MAX - 1; i = i + 1)
			{
				seq_kind[i]   = seq_kind[i + 1];
				seq_gain[i]   = seq_gain[i + 1];
				seq_de[i]     = seq_de[i + 1];
				seq_emax[i]   = seq_emax[i + 1];
				seq_dur[i]    = seq_dur[i + 1];
				seq_launch[i] = seq_launch[i + 1];
				seq_pct[i]    = seq_pct[i + 1];
			}
			seq_n = SEQ_MAX - 1;
		}

		p = seq_n;
		seq_n = seq_n + 1;
		seq_launch[p] = (!seq_haslaunch && kind == SEG_AIR);
		if (seq_launch[p])
			seq_haslaunch = TRUE;
	}

	/*
	  The u/s figure, for hud_seq_units 0 and for the single-line readout.

	  What that much energy is worth AT THE SPEED YOU ARE LEAVING WITH, which is
	  the honest conversion: the same dE is worth less the faster you already are,
	  exactly as the speedometer would show it.  On a merge that speed is the
	  LATEST one, because the merged segment is the one that ended there.

	  Sign-carried.  The radicand can only go negative if you lost more energy
	  than your entire current speed is worth, which is a wall; -v is the true
	  reading there ("everything you had").
	*/
	seq_gain[p] = Seq_Gain(de, v, gravity);

	/*
	  The percentage, for AIR rows only.

	  Energy rather than the u/s beside it, and the difference matters: u/s is a
	  nonlinear function of energy, so a speed percentage compresses at the top --
	  at 1500 u/s a sloppy strafe and a clean one both read above 90% and the
	  number stops discriminating exactly where a surfer needs it to.  Energy is
	  what you actually accumulate and it is additive, so 50% really is half as
	  good as 100%.  Under hud_seq_units 1 the row finally says so out loud: the
	  figure to its left is now the numerator of this fraction.

	  RECOMPUTED FROM THE SUMS, never averaged.  A duration-weighted mean of two
	  percentages is not the percentage of the sums once either dE is negative,
	  and an air row that ends by landing is exactly that case.

	  -1 means "not measured" -- a ramp row, or a segment whose ceiling came out
	  at zero -- and is distinct from 0%, which is a real reading.
	*/
	seq_pct[p] = -1;
	if (kind == SEG_AIR)
	if (emax > 0)
	{
		seq_pct[p] = 100 * de / emax;

		/*
		  CLAMPED AT ZERO, and the reason is a measurement artifact rather than a
		  preference.

		  An air segment that ends by LANDING reads a large negative dE -- about
		  -37 units for an ordinary jump -- because the boundary is sampled on the
		  frame the client first sees onground, by which point the engine has
		  already zeroed the vertical velocity that was most of the energy.  The
		  u/s column has always had the same artifact (a jump on flat ground reads
		  -30 u/s); it just becomes -150% here, and "-150% of the available gain"
		  is noise rather than information.

		  Zero is the honest floor for the question being asked: you captured none
		  of what was on offer.  The clamp is on the DISPLAY only -- seq_de keeps
		  the true negative, because a later merge sums it.
		*/
		if (seq_pct[p] < 0)
			seq_pct[p] = 0;
	}

	seq_kind[p] = kind;
	seq_de[p]   = de;
	seq_emax[p] = emax;
	seq_dur[p]  = dur;

	seq_lastgain = seq_gain[p];
	seq_lastde   = seq_de[p];

	// Consumed whether or not it actually blocked a merge: it describes the gap
	// that has just been closed, and that gap is now behind us.
	seq_break = FALSE;

	/*
	  BUILD 24: the build pass takes a copy, HERE, and not by watching the ring.

	  Two things happen in this function that an outside observer cannot tell
	  apart from the ring alone -- a merge rewrites row seq_n-1 in place without
	  changing seq_n, and a scroll shifts every row down and leaves seq_n pinned
	  at SEQ_MAX.  Both look like "seq_n did not move".  Reporting it from inside,
	  where `p >= 0` already distinguishes them, is exact and costs one call per
	  row rather than a comparison per frame.
	*/
	if (rec_wt_build)
		Watch_SeqRow(merged);
};

/*
  Watch the run timer for the edge that clears the list.

  TS_RUNNING arriving from anything else is a new run.  Note this is the START
  of a run and not the end: the point of the list is to still be there when you
  walk back to read it.
*/
void() Seq_Frame =
{
	local float st;

	st = getstatf(STAT_FS_TIMERSTATE);
	if (st != seq_laststate)
	{
		if (st == TS_RUNNING && seq_n > 0)
			seq_fadeat = cltime;
		if (st == TS_RUNNING)
			seq_haslaunch = FALSE;
		seq_laststate = st;
	}

	/*
	  AFTER the block above, not before, and the order is the whole trick.

	  A load restores the saved run's STATE as well as its position, and the
	  server writes both in one tick, so they arrive in one snapshot: loading a
	  running save while armed produces an ARMED -> RUNNING edge on the very frame
	  the load event lands.  The block above reads any such edge as a new run and
	  starts the one-second fade.

	  Running second is what lets the restore win: Seq_Unmark and Seq_Clear both
	  zero seq_fadeat, so the fade that block just armed is cancelled by the thing
	  it was about to erase.  Running first, the block would re-arm it afterwards
	  and the list would be gone a second later, which is worse than never
	  restoring it -- it would look like the restore worked and then broke.
	*/
	Seq_SaveEvents();

	if (seq_fadeat > 0)
		if (cltime - seq_fadeat >= SEQ_FADE)
			Seq_Clear();
};

/*
  Units of height per SECOND that a perfect air strafe could add, right now.

  Per tick the best is a^2 / 2g with a = Strafe_AirGain (see seg_emax); divide by
  the tick to get a rate, because this is integrated over rendered frames.

  At the shipped tuning this is a constant 37.5 -- 150 * 260 * 0.015 = 585, which
  saturates the 30 u/s cap, so a = 30 and 900 / (2 * 800 * 0.015) = 37.5.  It is
  computed rather than written down because none of those four numbers is ours:
  a server with a low sv_airaccelerate falls off the cap and the ceiling drops
  with it, and a percentage measured against the wrong ceiling is worse than no
  percentage at all.  Strafe_PowerCeiling says the same thing for the cap-bound
  case; this goes through Strafe_AirGain so the un-bound case is right too.
*/
float(vector vel, float onground, float gravity) Board_AirCeiling =
{
	local float airaccel, maxspeed, aircap, tick, fric, a;

	tick     = serverkeyfloat("pm_ticrate");       if (tick     <= 0) tick     = PM_TICK;
	airaccel = serverkeyfloat("sv_airaccelerate"); if (airaccel <= 0) airaccel = 150;
	maxspeed = serverkeyfloat("sv_maxspeed");      if (maxspeed <= 0) maxspeed = PM_RUN_SPEED;
	aircap   = serverkeyfloat("pm_maxairspeed");   if (aircap   <= 0) aircap   = 30;

	// The same quartering PMSrc_CategorizePosition applies while airborne and
	// rising slowly -- see the long note in HUD_DrawStrafe.  Inert at the
	// shipped tuning (the cap binds either way) and not inert at a low
	// sv_airaccelerate, which is the case this whole function exists for.
	fric = 1;
	if (!onground && vel_z > 0 && vel_z <= PM_NONJUMP_VEL)
		fric = 0.25;

	a = Strafe_AirGain(airaccel, maxspeed, tick, fric, aircap);
	return (a * a) / (2 * gravity * tick);
};

/*
  Returns TRUE if it produced a row.  Build 20, and the caller needs the answer:
  a segment too short to be a row has to be DEPOSITED into the carry instead of
  discarded, or its energy leaves the column's sum with nothing to say it went.

  It reads the carry but does NOT consume it -- the caller clears it on a
  successful push and grows it otherwise, so `+=` there cannot double-count.
*/
float(float newkind, float e, vector vel, float gravity) Board_SegmentEnd =
{
	local float dur, de, v, emax;

	dur  = (board_now - seg_t0) + seg_carry_dur;
	de   = (e - seg_e0)      + seg_carry_de;
	emax = seg_emax          + seg_carry_emax;

	// Tested against the CARRIED duration, so three consecutive blips add up to
	// a row rather than each vanishing on its own.
	if (dur < SEG_MINTIME)
		return FALSE;

	/*
	  THE ARITHMETIC MOVED INTO Seq_Push.  Build 20, and it had to.

	  A merged row is not the average of two displayed rows, it is the row the
	  two segments would have produced had nothing interrupted them -- so both
	  the u/s conversion and the percentage have to be recomputed from the summed
	  energy, and only Seq_Push can see the row being merged into.  Everything
	  this function used to compute is handed over raw instead; the essays that
	  explain the two conversions went with them.

	  v travels with the energy: Board_Frame hands us the PRE-CLIP velocity at a
	  board, and converting a pre-clip dE at a post-clip speed would be mismatched
	  by exactly the board this build charges to the ramp.
	*/
	v = vlen(vel);

	/*
	  BUILD 25 -- THE TOUCHDOWN GOES IN FIRST, and only now.

	  Held since the ramp opened (see seg_bd_pend), pushed here because this is
	  the first moment we know the ramp became a real row -- everything above this
	  line can still return FALSE, and a board row with no ramp behind it would
	  break the merge it was waiting for.

	  BEFORE the ramp's own push, because it happened first: the column is
	  chronological and reads air / board / ramp down the screen, which is the
	  order the three things occurred in.

	  seg_bd_v, not v: the speed the board took its bite at, not the speed the
	  ride ended with.  emax 0 and one tick of duration -- see SEG_BOARD.
	*/
	if (seg_kind == SEG_RAMP)
	if (seg_bd_pend)
	{
		local float btick;
		btick = serverkeyfloat("pm_ticrate");
		if (btick <= 0) btick = PM_TICK;

		Seq_Push(SEG_BOARD, seg_bd_de, 0, btick, seg_bd_v, gravity);
		seg_bd_pend = FALSE;
	}

	// The COLUMN takes every valid segment, including an air time that ends by
	// landing; the single-line readout below still takes only the two that are
	// worth interrupting you for.  Same number, two different questions.
	Seq_Push(seg_kind, de, emax, dur, v, gravity);

	if (seg_kind == SEG_AIR && newkind != SEG_RAMP)
		return TRUE;

	// seq_last* rather than a second copy of the physics, so a merged ride shows
	// the whole ride here too.
	gain_kind  = seg_kind;
	gain_speed = seq_lastgain;
	gain_de    = seq_lastde;
	gain_dur   = dur;
	gain_time  = board_now;
	return TRUE;
};

/*
  Board_Frame -- called once per rendered frame from the HUD.

  Two edges, and they are different in kind.  A BOARD is a counter change,
  because a counter cannot be missed however slow the frame rate; LEAVING is
  a level falling, which is safe to sample per frame because coming off a
  ramp is followed by being off it.

  The 100 u/s and 25 u/s gates below are what stop a long ride being graded
  as thousands of perfect landings.  They are not sufficient on their own --
  applying the 25 u/s rule alone (which is what the surf community's server
  plugins do) grades 84% of events perfect, because sustained surfing clips
  every single tick.  The airborne-first gate in the engine is the real
  filter; these two only reject the trivial.
*/
void(vector org, vector vel, float onground) Board_Frame =
{
	local float seq, riding, kind, gravity, e, dt, boarded, eb;
	local vector n, vin, vb;

	/*
	  BUILD 24.  The frame clock, and where this frame's inputs come from.

	  Seq_Frame is SKIPPED during a build pass and that is not an optimisation.
	  It watches STAT_FS_TIMERSTATE for the edge that clears the list -- the live
	  player's timer, which during a load pass is doing whatever the live player
	  is doing and has nothing to do with the file being read.  It also drives the
	  one-second fade off cltime, and a build pass has no wall clock.  The
	  recording's own TS_ARMED -> TS_RUNNING edge is not needed either: the pass
	  starts from a cleared list by construction.
	*/
	if (rec_wt_build)
	{
		board_now = board_ov_now;
		seq    = board_ov_seq;
		riding = board_ov_riding;
	}
	else
	{
		board_now = cltime;
		Seq_Frame();
		seq    = getstatf(STAT_FS_BOARDCOUNT);
		riding = getstatf(STAT_FS_RAMPCONTACT);
	}

	/*
	  BUILD 25 -- through the hold, in BOTH branches.

	  The build pass gets it too, and that is deliberate rather than incidental: a
	  .rec's flags bit 16 is the same per-tick stat with the same per-tick
	  dropouts, so a replayed ride has to be segmented the same way a live one is
	  or the column you scrub to would not match the column you watched.
	*/
	riding = Board_RampHold(riding, board_now);

	// Read once, up here.  The segment boundary at the bottom needs it as well
	// as the energy sample, and a board edge is where those two meet.
	gravity = serverkeyfloat("sv_gravity");
	if (gravity < 1) gravity = 800;

	/*
	  Build 20's two switches, cached per frame rather than read per row.

	  seq_units is not used in this file at all -- HUD_DrawSeq and HUD_DrawBoard
	  read it -- but it is cached HERE because cl_board.qc compiles before
	  cl_hud.qc, so a global that both files touch has to be declared on this side
	  of the line.  The registercvar calls stay with the other hud_* ones over
	  there; only the read crosses, and cvar() is a builtin so no symbol does.
	*/
	seq_merge = cvar("hud_seq_merge");
	seq_units = cvar("hud_seq_units");
	seq_board = cvar("hud_seq_board");

	// Zeroed rather than left to the edge block below, which is the only thing
	// that ever writes them: fteqcc cannot see that `boarded` implies they were
	// written this frame, and the segment boundary reads them under that guard.
	boarded = FALSE;
	n = vin = '0 0 0';

	if (seq != board_seq)
	{
		board_seq = seq;

		// Only read these on the frame the count moved.  At any other time
		// they hold the previous board's values.  During a build pass they come
		// out of the .rec's own `board` record, which is written on exactly the
		// tick the counter moved and carries the same latched pair.
		if (rec_wt_build)
		{
			n   = board_ov_bnorm;
			vin = board_ov_bvel;
		}
		else
		{
			n_x   = getstatf(STAT_FS_BOARDNORM + 0);
			n_y   = getstatf(STAT_FS_BOARDNORM + 1);
			n_z   = getstatf(STAT_FS_BOARDNORM + 2);
			vin_x = getstatf(STAT_FS_BOARDVEL + 0);
			vin_y = getstatf(STAT_FS_BOARDVEL + 1);
			vin_z = getstatf(STAT_FS_BOARDVEL + 2);
		}

		/*
		  NOT GATED BY THE TWO THRESHOLDS BELOW, and that is deliberate.

		  The 100 u/s and 25 u/s gates exist to stop a long ride being GRADED as
		  thousands of perfect landings -- they are about whether a board is
		  worth reporting.  A sub-threshold board still moves energy, and the
		  segment boundary is about accounting rather than about reporting, so
		  it takes every board the engine counted.  All it needs is a plane.
		*/
		if (n != '0 0 0')
		{
			boarded = TRUE;
			// Build 39: taken here, ungated, for the same reason `boarded` is.
			// Board_Compute below may not run, and the boundary still has to be
			// paid for.
			board_stepe = Board_StepE(vin, n);
		}

		if (vlen(vin) >= 100 && fabs(vin * n) >= 25 && n != '0 0 0')
			Board_Compute(vin, n);
	}

	// Leaving: the falling edge of ramp contact.  wrlines has no equivalent
	// of this at all -- its "speedOut" is the analytically clipped speed at
	// the instant of ENTRY, not a measurement of what you left with.  We can
	// measure it honestly because the engine tells us the tick the clipping
	// stopped.
	if (board_riding && !riding)
	{
		// `vel` rather than a second read of STAT_FS_VELOCITY, which is what it
		// already is -- HUD_Draw reads that stat into it.  Byte-identical live,
		// and it makes the build pass work with no override of its own.
		leave_speed = vlen([vel_x, vel_y, 0]);
		leave_time  = board_now;
	}
	board_riding = riding;

	/*
	  The segment tracker.  Three states and they are mutually exclusive:
	  standing beats riding beats falling.  Standing opens no segment at all --
	  a ground segment would just be "you walked", and the ground already has
	  its own readout under the bar.
	*/
	e = Strafe_Energy(org, vel, gravity);

	/*
	  BUILD 26: a restored segment is exempt from the guard UNTIL IT ARRIVES.

	  Seq_OpenRestore hands back a real e0 from a real earlier moment, but its
	  seg_org belongs to nothing -- and a save-lock load has just moved you, very
	  probably by more than SEG_JUMPDIST, which is precisely what the guard exists
	  to catch.  Without the exemption the restore would invalidate itself,
	  silently, and look exactly like not having restored.

	  Build 25 made it a ONE-SHOT consumed here, and that was measurably not
	  enough: loading a save from ~580 units away spent it on a quiet frame before
	  the position step landed, and the segment came back with valid 0.  See
	  ui_rs_armed for the evidence and the rule that replaces it.
	*/
	if (!ui_rs_armed)
	if (seg_kind != SEG_NONE && vlen(org - seg_org) > SEG_JUMPDIST)
		seg_valid = FALSE;
	seg_org = org;

	if (onground)    kind = SEG_NONE;
	else if (riding) kind = SEG_RAMP;
	else             kind = SEG_AIR;

	/*
	  Integrate the ceiling BEFORE the state edge below, so the frame that ends
	  a segment contributes to the segment it is ending rather than to the next
	  one.  dt is clamped: a hitch, an alt-tab or a map load would otherwise add
	  seconds of "available gain" the player was never given a chance at, and
	  the percentage would read as a catastrophic miss for something that was
	  not their input at all.  0.1s is the same clamp Timer_Display uses on the
	  same reasoning.
	*/
	dt = board_now - seg_lastt;
	seg_lastt = board_now;
	if (dt < 0)   dt = 0;
	if (dt > 0.1) dt = 0.1;

	if (seg_kind == SEG_AIR && seg_valid)
		seg_emax = seg_emax + Board_AirCeiling(vel, onground, gravity) * dt;

	if (kind != seg_kind)
	{
		/*
		  THE BOARD IS THE RAMP'S COST, NOT THE AIR TIME'S.  Build 19.

		  `e` above is sampled from the POST-clip velocity: STAT_FS_RAMPCONTACT
		  is set by the engine on the tick that did the clipping, so on the first
		  frame we see `riding` the speed has already been taken.  Closing the air
		  segment at `e` therefore charged the entire board to the air time and
		  handed the ramp an already-reduced number to start from -- so a perfect
		  strafe into a bad board read as a bad AIR row and a bad air %, which is
		  backwards.  What you strafed for and what the board cost you are two
		  different measurements and they belong on two different rows.

		  STAT_FS_BOARDVEL is the PRE-clip velocity, latched by the engine and
		  read above on the same frame.  So the boundary is taken from it, and
		  taken ONCE: it closes the air segment and opens the ramp segment at the
		  same value, which is what keeps the rows summing to the run's total.

		  BUILD 39 -- AND THE PARAGRAPH THAT USED TO BE HERE WAS WRONG.

		  It claimed the step the ramp inherits is `e - eb = -(v.n)^2 / 2g,
		  exactly the number Board_Compute publishes as board_losse ... so the
		  two agree by construction rather than by coincidence.'  They do not
		  agree, and it is not a coincidence either -- it is a systematic error
		  with a closed form, and it is the "one will say I lost -169 e and the
		  other will read -179 e" report.

		  vin and vel are not the two ends of one clip.  The engine latches
		  boardvelocity INSIDE TryPlayerMove (pm_source.c:1151), which is after
		  StartGravity and before FinishGravity; `vel` is the end-of-tick
		  velocity, after FinishGravity.  Half a step of gravity sits between
		  them, unpaired -- unpaired because both energies are evaluated at the
		  SAME origin, so the height that half-step is exchanged with is missing.
		  With G = g*dt = 12 at the shipped tuning:

		      e - eb  =  -(v.n)^2/2g  +  (G^2/4 - G*v'z) / 2g
		              =  -(v.n)^2/2g  +  0.0225 - 0.0075 * v'z

		  v'z is the post-clip vertical speed and on a board it is large and
		  NEGATIVE, so the column's number is systematically less negative than
		  the panel's.  At a hard touchdown around -1330 u/s that is the ten
		  units reported, and it grows with the speed of the landing -- i.e. it
		  is worst exactly where the reading matters most.

		  So the boundary is now taken from Board_StepE, the closed form, which
		  is the same call Board_Compute makes for board_losse.  The telescoping
		  the paragraph above cares about is untouched: the air segment closes at
		  e + stepe, the board step is -stepe, the ramp opens at e, and the pair
		  still sums to e exactly.  The panel and the column now print one
		  number because they are one number.

		  WHICH ONE WAS TRUE: the panel's.  board_losse is a closed form for an
		  orthogonal projection and has no sampling in it at all.

		  vb travels with eb because Board_SegmentEnd converts dE to u/s at the
		  closing speed.  A pre-clip energy delta converted at a post-clip speed
		  is mismatched by the board all over again, in the other direction.

		  NONE -> RAMP is included as well as AIR -> RAMP: sliding onto a ramp
		  off flat ground has no air time to charge, and opening the ramp at the
		  post-clip energy would hide the cost rather than move it.

		  BUILD 25 -- AND NOW eb IS USED ONCE, NOT TWICE.

		  Build 19 opened the ramp at eb as well as closing the air at it, which
		  handed the ramp the board's whole cost as an invisible head start.  With
		  hud_seq_board on, the ramp opens at `e` -- the post-clip energy, which is
		  what the ramp actually starts from -- and the step between them is held
		  as its own row.  See SEG_BOARD.

		  At hud_seq_board 0 this is build 24 byte for byte, which is the
		  bisection rule every behaviour change in this project follows.
		*/
		eb = e;
		vb = vel;
		if (boarded && kind == SEG_RAMP)
		{
			vb = vin;

			// hud_board_exact 0 is build 38 byte for byte, which is the
			// bisection rule every behaviour change in this project follows --
			// and here it is also the only way to see the ten units, since the
			// error lives in the difference between the two.
			if (cvar("hud_board_exact") || !cvar_string("hud_board_exact"))
				eb = e + board_stepe;
			else
				eb = Strafe_Energy(org, vin, gravity);

			if (seq_board)
			{
				seg_bd_de   = e - eb;       // -(v.n)^2 / 2g, exactly, since build 39
				seg_bd_v    = vlen(vel);    // post-clip, see seg_bd_v
				seg_bd_pend = TRUE;
			}
		}

		/*
		  BUILD 20 -- WHERE A REFUSED SEGMENT'S ENERGY GOES.

		  Three outcomes, and they are three because a segment can fail to become
		  a row for two entirely different reasons:

		    teleported   its dE is the distance the ENGINE moved you.  Dropped,
		                 and it takes any waiting carry with it -- depositing a
		                 3000-unit height change into the next row would make the
		                 column fiction in a new and more confident way.  It is
		                 also a real gap, so it may not be merged across.
		    too short    a bounce off a lip, a few ticks of lost ramp contact
		                 around a bend.  It still MOVED energy, so it is carried
		                 into whatever row comes next, and its two neighbours
		                 become adjacent and mergeable.
		    a real row   the carry has been spent; clear it.

		  The deposit adds the RAW values, not the carried ones: Board_SegmentEnd
		  read the carry without consuming it, so a `+` here cannot double-count.

		  The final else is the fourth case and the one that is easy to miss -- a
		  genuine grounded phase, which opens no segment of its own and so passes
		  through here as SEG_NONE.  Long enough to be real, and it breaks the
		  merge chain: two air times either side of standing on the floor are two
		  air times.  seg_t0 is set unconditionally below for SEG_NONE too, so its
		  duration costs no extra timer.
		*/
		if (seg_kind != SEG_NONE)
		{
			if (!seg_valid)
			{
				seg_carry_de = seg_carry_dur = seg_carry_emax = 0;
				seq_break = TRUE;

				// Build 25: a teleported ramp takes its touchdown with it.  Its
				// dE is real, but the row it belonged to is being dropped as
				// fiction and a lone board row would be fiction with it.
				seg_bd_pend = FALSE;
			}
			else if (!Board_SegmentEnd(kind, eb, vb, gravity))
			{
				seg_carry_de   = seg_carry_de   + (eb - seg_e0);
				seg_carry_dur  = seg_carry_dur  + (board_now - seg_t0);
				seg_carry_emax = seg_carry_emax + seg_emax;

				/*
				  BUILD 25 -- THE REFUSED RAMP TAKES ITS TOUCHDOWN INTO THE CARRY.

				  This is the branch that protects build 20's merge.  A few ticks
				  of lost contact around a bend produce a ramp segment too short
				  to be a row; its energy is carried into whatever comes next so
				  the column still sums, and its two air neighbours become
				  adjacent and mergeable.  The board that opened it has to travel
				  the same way -- left pending it would attach itself to the NEXT
				  ramp, reporting one landing's cost against another's ride.

				  No duration is added for it: it is one tick and the carry's
				  duration is what SEG_MINTIME is tested against, so counting it
				  would make three blips reach the threshold slightly sooner for a
				  reason that has nothing to do with how long you were on the ramp.
				*/
				if (seg_bd_pend)
				{
					seg_carry_de = seg_carry_de + seg_bd_de;
					seg_bd_pend  = FALSE;
				}
			}
			else
				seg_carry_de = seg_carry_dur = seg_carry_emax = 0;
		}
		else if (board_now - seg_t0 >= SEG_MINTIME)
			seq_break = TRUE;

		seg_kind  = kind;
		seg_e0    = eb;
		seg_t0    = board_now;
		seg_valid = TRUE;
		seg_emax  = 0;

		/*
		  BUILD 25.  The ramp opens at the POST-clip energy when its touchdown has
		  been split out; eb is still what closed the air segment above.  One
		  assignment, and it is the whole of the split -- everything else is about
		  making sure the held row goes to the right place.
		*/
		if (seg_bd_pend)
		if (kind == SEG_RAMP)
			seg_e0 = e;
	}

	/*
	  BUILD 26: THE RESTORE HAS ARRIVED, so both guards go back on.

	  Disarmed HERE rather than in either guard, and last in the function, for one
	  reason: HUD_UpdateJumpRef reads the same flag earlier in the same frame
	  (cl_hud.qc:2063 against this at :2093).  Whichever read it first would
	  otherwise disarm it for the other, and on the arrival frame BOTH still need
	  the exemption -- that is the frame the position actually jumps.

	  "Arrived" is the same SEG_JUMPDIST the guards use, against the destination
	  the save recorded.  A load that lands within a step of where the save was
	  taken is the normal case and disarms on its first frame; the slow case is a
	  teleport whose new origin takes an extra snapshot to reach us, which is
	  exactly what build 25's one-shot could not survive.
	*/
	if (ui_rs_armed)
	if (vlen(org - ui_rs_dest) <= SEG_JUMPDIST)
		ui_rs_armed = FALSE;

	/*
	  BUILD 34: publish the open segment.  See seg_live_kind.

	  LAST, so it describes the segment this frame ended with rather than the one
	  it started with -- the transition block above may have closed one and opened
	  another, and a reader wants the one that is still running.

	  Byte for byte Board_SegmentEnd's own first two lines.  seg_emax is left out
	  because the percentage it feeds is only meaningful once the segment is
	  finished: an air row's "% of what you could have got" against a ceiling that
	  is still being integrated would read as a miss that has not happened yet.

	  NOT during the replay build pass.  That pass runs this whole function over a
	  .rec to fill the ring, at which point "the open segment" is a position in a
	  file rather than anything on screen, and leaving its last value published
	  would put a phantom row under a replay that has not started.  Watch_SeqApply
	  clears them again on the way into playback, where this does not run at all.
	*/
	seg_live_kind   = 0;
	seg_live_de     = 0;
	seg_live_dur    = 0;
	seg_live_gain   = 0;
	seg_live_bdgain = 0;
	if (!rec_wt_build)
	if (seg_kind != SEG_NONE && seg_valid)
	{
		seg_live_kind = seg_kind;
		seg_live_de   = (e - seg_e0)         + seg_carry_de;
		seg_live_dur  = (board_now - seg_t0) + seg_carry_dur;

		/*
		  Both u/s figures converted HERE, through the same Seq_Gain the committed
		  rows go through, so hud_seq_units 0 cannot show one number live and a
		  different one a moment later.  The ramp converts at the speed it is
		  travelling at now; the touchdown converts at the speed it took its bite
		  at, which is the mismatch build 19's essay is about.
		*/
		seg_live_gain = Seq_Gain(seg_live_de, vlen(vel), gravity);
		if (seg_bd_pend)
			seg_live_bdgain = Seq_Gain(seg_bd_de, seg_bd_v, gravity);
	}
};

/*
  Fade.  Solid for the first two-thirds of its life, then linear to nothing
  -- wrlines' rule, which reads as "it is still there" rather than as a
  slow dissolve.  At the default hud_board_fade of 3 s that is 2.01 s solid
  and 0.99 s of fade.
*/
float(float when, float life) Board_Alpha =
{
	local float age, fadefrom;

	if (when <= 0 || life <= 0.1)
		return 0;

	/*
	  board_now and not cltime, so a replay fades in RUN seconds.

	  Live the two are the same thing.  During a replay board_now is the
	  recording's own clock, which is what makes the panel hold a board for the
	  three seconds it held it when the run happened rather than for three
	  seconds of wall time -- at 4x that would be three quarters of a second, and
	  at 0.1x the panel would never clear.  It also makes a backwards scrub put
	  the readout back, because `age < 0` is a board that has not happened yet.
	*/
	age = board_now - when;
	if (age < 0 || age >= life)
		return 0;

	fadefrom = life * 0.67;
	if (age <= fadefrom)
		return 1;
	return 1 - ((age - fadefrom) / (life - fadefrom));
};

/*
  BUILD 24: SPLIT OUT OF Board_Clear, and the half that is left behind is why.

  Board_Clear also invalidates the SAVE-LOCK snapshot (seq_mk_id = -1), which is
  right for a map change and wrong for anything else.  Watch_BuildSeq needs a
  clean machine to run the file through and must not, in the process, throw away
  the snapshot a save state took -- that would make a later load of that slot
  fall through to the file with nothing on screen saying why, which is precisely
  the class of silent entanglement build 11 spent a build tracking down.

  So: this is "forget the run", Board_Clear is "forget the map".

  BUILD 30 ADDED A THIRD, Board_ResetContact, and the overlap between them is
  deliberate rather than an oversight waiting to be tidied up.  That one is
  "forget the surface", for a save-lock load, and it is NOT called from here for
  two reasons: it syncs board_seq to the live counter where a map change wants a
  hard 0 (the edict is fresh), and it reaches into cl_hud.qc's energy ring --
  which this function must not do, because Watch_BuildSeq calls it to run a
  recording through the machine and would wipe the live player's history as a
  side effect.  If you add a contact field, add it to BOTH.
*/
void() Board_ResetRun =
{
	// Reachable from HUD_UpdateAnchor, which runs BEFORE Board_Frame has set the
	// frame clock this frame, so seg_lastt below would otherwise be seeded from
	// the previous frame's value -- or from zero on the very first map load,
	// which is the epoch and would make the first dt clamp.
	if (!rec_wt_build)
		board_now = cltime;

	board_time = board_seq = 0;
	leave_time = leave_speed = 0;
	board_riding = 0;

	// Build 25: and the held ramp contact, which is measured against a clock that
	// has just restarted.  It would expire on its own (see Board_RampHold), but a
	// hold left live across a map change is one frame of a ramp that is not there.
	ramp_on = ramp_lastc = ramp_raw = ramp_rawlast = ramp_drops = 0;
	ramp_bridged = 0;

	// And the touchdown waiting for a ramp that is no longer there to close.
	seg_bd_pend = seg_bd_de = seg_bd_v = 0;

	// Build 26: an in-flight restore that a map change or an `ui_anchor clear`
	// has just overtaken.  Its destination is on a map that is not loaded any
	// more, so it can never arrive and would stay armed for the whole session.
	ui_rs_armed = FALSE;

	// A map change or an anchor reset makes the open segment meaningless -- its
	// e0 was measured against different geometry.
	seg_kind  = SEG_NONE;
	seg_valid = FALSE;
	seg_org   = '0 0 0';
	seg_emax  = 0;
	seg_lastt = board_now;  // not 0: a dt measured from the epoch would clamp
	gain_kind = SEG_NONE;
	gain_time = 0;
	gain_de   = 0;

	// The sequence goes too: its rows were measured against geometry that is no
	// longer there.  Cleared outright rather than faded -- a map change is not a
	// transition anyone is watching.  Seq_Clear also empties the carry.
	Seq_Clear();
	seq_laststate = -1;
};

void() Board_Clear =
{
	Board_ResetRun();

	/*
	  And the snapshot, which belongs to the map it was taken on.  -1 rather than
	  0, because 0 is the RETRY slot and a real id -- leaving it at zero would let
	  a stale in-memory list satisfy the warm path of a retry restore that ought
	  to read the file the previous VM wrote.

	  Q106: seeded here rather than in the declaration, because fteqcc folds an
	  initialised global scalar into a constant and then refuses to assign to it.

	  This runs on a map-name change, i.e. from HUD_UpdateAnchor, which HUD_Draw
	  calls BEFORE Board_Frame -- so a retry's restore, which happens inside
	  Board_Frame, is safely after this and is not undone by it.
	*/
	seq_mk_id = -1;
	seq_mk_n  = 0;
};

/*
  "I did not travel here, I was put here" -- the client's half of
  SV_TimerWarped, and named for it because it exists for the same reason.
  Build 20.

  A save-lock load teleports you, and the open segment does not know.  Its e0
  was sampled where you WERE, so the first row after the load would report the
  height difference between two places as something your hands did.

  seg_valid = FALSE ALONE IS NOT ENOUGH, and that is the trap: it makes
  Board_Frame skip the SegmentEnd, but it leaves seg_kind set, so no transition
  fires until the kind happens to change on its own and the segment meanwhile
  runs on carrying the pre-teleport e0.  seg_kind = SEG_NONE is what forces the
  next frame to open a fresh one at the post-load energy.

  seg_org can be zeroed safely: the 512-unit teleport guard reads it only after
  testing seg_kind != SEG_NONE, which is now false.

  The existing guard USUALLY catches a load on its own, because a load usually
  moves you further than 512 units.  Usually is not a mechanism -- a save taken
  two hundred units back is a perfectly ordinary save.
*/
void() Board_Warped =
{
	seg_kind  = SEG_NONE;
	seg_valid = FALSE;
	seg_emax  = 0;
	seg_t0    = cltime;
	seg_org   = '0 0 0';

	/*
	  And any exemption a restore had armed.  Build 25 cleared its one-shot here
	  and build 26 clears the in-flight arming for the same reason: nothing is
	  open to exempt now, and an arming left live would excuse the next real
	  teleport as well.

	  ORDERING, AND IT IS LOAD-BEARING.  Both callers that can restore an anchor
	  in the same breath -- Seq_Unmark's else branch and Seq_Read's !gotopen
	  branch -- call this BEFORE Seq_AnchorRestore, so the arming survives.  Get
	  that backwards and every save with no open segment loads with the anchor
	  restored and then immediately re-based, which looks exactly like not having
	  fixed anything.
	*/
	ui_rs_armed = FALSE;

	// The pending touchdown belonged to the ramp segment this just killed.  Left
	// alive it would attach to the next one, reporting a landing that happened
	// before the teleport against a ride that happened after it.
	seg_bd_pend = FALSE;

	seg_carry_de = seg_carry_dur = seg_carry_emax = 0;

	// And the row after a load may not be sewn onto the row before it: you were
	// somewhere else in between, which is the definition of a real gap.
	seq_break = TRUE;
};
