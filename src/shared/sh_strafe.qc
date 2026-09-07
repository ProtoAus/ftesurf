/*
===========================================================================
  sh_strafe.qc -- the surf maths: energy, and what optimal strafing is.

  Ported from wrlines' wr_stress.h, which is a dependency-free header of
  plain floats precisely so it can be checked and reused.  Every constant
  below is quoted from its derivation there; where a number was measured
  rather than derived, the measurement is named.

  Nothing here touches engine state.  Give it numbers, get numbers back --
  which is what makes it testable, and what lets both VMs share it.
===========================================================================
*/

// DEG_PER_RAD moved to sh_defs.qc in build 25 -- the SERVER needs it now, for
// the ramp-plane report, and sh_strafe.qc is client-only (cl_progs.src:10).

/*
  ENERGY, and why it is a height.

      E = z + |v|^2 / (2g)

  Divide the usual 1/2 m v^2 + m g h through by m and by g and both terms
  become world units, so E is the height you would reach if every unit of
  speed were traded for altitude.  That makes it directly comparable with
  the map: a surfer at 3000 u/s on the floor and one standing still 5600
  units up have the same energy, and they do, because either can become the
  other.

  It uses the FULL 3D speed.  The horizontal readout beside it is 2D, and
  they are deliberately different numbers -- horizontal is what you are
  making progress with, energy is what you have left to spend.
*/
float(vector org, vector vel, float gravity) Strafe_Energy =
{
	if (gravity < 1)
		gravity = 1;
	return org_z + ((vel * vel) / (2 * gravity));   // vector*vector is dot
};

/*
  Energy written back as a speed: the horizontal speed this much energy is
  worth if you spent all of it.  Easier to read than a height when what you
  are comparing is speeds.

  E_rel goes NEGATIVE on a descending map -- for everyone, correctly, since
  you finish below where you started -- so this sign-carries rather than
  clamping.  Across 51 surf_demise records E_rel at the finish correlates
  with run time at -0.976, which is the whole argument for putting it on
  screen.
*/
float(float erel, float gravity) Strafe_EquivSpeed =
{
	if (gravity < 1)
		gravity = 1;
	if (erel < 0)
		return -sqrt(-2 * gravity * erel);
	return sqrt(2 * gravity * erel);
};

/*
  The speed added to velocity along wishdir in one tick of AirAccelerate:

      accelspeed = accel * wishspeed * frametime * surfacefriction
      capped at  (wishspeed capped at) the air cap, 30

  This is NOT the formula the popular strafe-analyzer uses -- that one has
  `tick * 30 * sv_airaccelerate`, which puts the air cap where sv_maxspeed
  belongs.  The two agree at surf settings by coincidence, because both
  saturate at 30, and disagree everywhere else.
*/
float(float airaccel, float wishspeed, float tick, float friction, float aircap) Strafe_AirGain =
{
	local float g;
	g = airaccel * wishspeed * tick * friction;
	if (g > aircap)
		g = aircap;
	return g;
};

/*
  Does the wishspeed cap actually bind?

  When it does not, the gain is accelspeed regardless of where you point,
  and the turn rate then says nothing about how well you are strafing --
  it is pinned by the acceleration instead.  At surf settings this is
  150 * 250 * 0.015 = 562.5 against 30, nowhere near the boundary
  (crossover is about sv_airaccelerate 32), but a server running a low
  airaccelerate would otherwise be graded as if it were the player.
*/
float(float airaccel, float maxspeed, float tick, float friction, float aircap) Strafe_CapBinds =
{
	return (airaccel * maxspeed * tick * friction) >= aircap;
};

/*
  THE OPTIMUM ITSELF.

  Per tick, with wishspeed capped at ws and c = dot(v, wishdir):

      2g dE = 2ac + a^2 = 2(ws-c)c + (ws-c)^2 = ws^2 - c^2

  which is maximised at c = 0 -- wishdir exactly PERPENDICULAR to velocity,
  in the horizontal plane, because AirMove zeroes the z of forward and right
  before building wishdir.  So the answer to "what angle" is always 90
  degrees, and it is not worth displaying.

  What IS worth displaying is the view rate that HOLDS that perpendicularity
  as you speed up, which is the angle the velocity itself turns through:

      theta_per_tick = atan2(gain, speed)

  Divided by the tick, that is degrees per second.  It FALLS as you go
  faster -- the same 30 units a tick buys a smaller and smaller angle --
  which is why it is about 115 deg/s at 1000 u/s and 44 at 2600.
*/
float(float speed, float gain, float tick) Strafe_IdealTurn =
{
	if (speed < 1)
		speed = 1;
	if (tick < 0.0001)
		tick = 0.015;
	return (atan2(gain, speed) * DEG_PER_RAD) / tick;
};

/*
  What a PERFECT air turn is worth, as a speed change per tick.

  The ground has had this since Patch 135 (Strafe_GroundBest below) and the air
  did not, so the readout under the bar appeared only while standing -- which is
  the one place a surfer is not.

  It falls straight out of the optimum above.  At c = 0 the applied
  acceleration is the whole of `gain` and it is PERPENDICULAR to the velocity,
  so the new speed is the hypotenuse:

      best = sqrt(|v|^2 + gain^2) - |v|

  Horizontal, like the ground figure, because AirMove zeroes the z of forward
  and right before building wishdir -- nothing here touches the vertical.

  It SHRINKS with speed, and that is the honest shape rather than a defect:
  30 u/s across your path is worth +0.45 at 1000 u/s and +0.17 at 2600.  There
  is no friction term and no zero crossing, so unlike the ground number this one
  is always positive.
*/
float(float speed, float gain) Strafe_AirBest =
{
	if (speed < 1)
		speed = 1;
	return sqrt(speed * speed + gain * gain) - speed;
};

/*
===========================================================================
  THE GROUND, WHICH IS NOT THE SAME PROBLEM AT ALL.

  Everything above rests on the air cap binding.  AirAccelerate measures
  addspeed against a wishspeed CLAMPED to 30, so the applied acceleration is
  `30 - c` and

      d|v|^2 = 2(30-c)c + (30-c)^2 = 900 - c^2      maximised at c = 0

  On the ground there is no cap.  Accelerate (pm_source.c:448-468) applies
  `min(A, wishspeed - c)` with

      A = accel * tick * wishspeed * surfacefriction = 18.75 at CS:S settings

  a CONSTANT, not a budget.  So

      d|v|^2 = 2*A*c + A^2         while c < wishspeed - A   (rising in c)
             = wishspeed^2 - c^2   past it                   (falling in c)

  and the maximum is on the boundary, at c = wishspeed - A -- wishdir nearly
  ALONG the velocity, not across it.  Below that speed the boundary is out of
  reach and the answer is c = |v|: point straight ahead and stop turning.

  This is not a refinement of the air formula, it is its opposite, and using
  the air answer on the ground gives advice that is actively wrong: at 250 u/s
  perpendicular turns a gain of +3.47 u/s into a loss of -14.25.  Checked
  against the real Friction/Accelerate pair in pm_selftest (Patch 135), which
  is where the reference numbers live.

  Friction runs BEFORE Accelerate every tick and is a pure shrink along the
  velocity -- it changes the speed these formulas are evaluated at and rotates
  nothing, which is why it appears as a separate step rather than inside them.
===========================================================================
*/
float(float speed, float fric, float stopspeed, float tick) Strafe_AfterFriction =
{
	local float ctrl, drop;

	if (speed <= 0)
		return 0;

	// Source: the drop uses stopspeed as a floor on the control speed, so
	// walking pace decelerates at a fixed rate rather than proportionally.
	ctrl = (speed < stopspeed) ? stopspeed : speed;
	drop = ctrl * fric * tick;
	if (drop >= speed)
		return 0;
	return speed - drop;
};

float(float accel, float wishspeed, float tick, float friction) Strafe_GroundGain =
{
	return accel * tick * wishspeed * friction;
};

/*
  cos of the optimal angle between wishdir and velocity, on the ground.
  Returns 1 ("straight ahead") below wishspeed - A, where the optimum is not
  reachable -- and that is a real answer, not a degenerate one.

  `speed` is the POST-FRICTION speed.  Handing it the pre-friction speed is
  wrong by about half a degree at 250 and the difference grows as friction
  does, which is enough to move the displayed turn rate.
*/
float(float speed, float gain, float wishspeed) Strafe_GroundOptCos =
{
	local float c;

	if (speed < 1)
		return 1;
	c = (wishspeed - gain) / speed;
	if (c > 1)  c = 1;
	if (c < -1) c = -1;
	return c;
};

/*
  The view rate that HOLDS the optimal angle, in degrees per second.

  The velocity turns by the angle the applied acceleration adds across it:
  atan2(A*sin, |v| + A*cos).  Unlike the air case this does NOT fall
  monotonically -- it is zero below wishspeed - A, peaks near 400 u/s (about
  146 deg/s) and falls away after, because the optimal angle is itself opening
  up as you speed up.
*/
float(float speed, float gain, float wishspeed, float tick) Strafe_IdealTurnGround =
{
	local float c, s;

	if (speed < 1)
		return 0;
	if (tick < 0.0001)
		tick = 0.015;

	c = Strafe_GroundOptCos(speed, gain, wishspeed);
	s = 1 - c * c;
	s = (s > 0) ? sqrt(s) : 0;

	return (atan2(gain * s, speed + gain * c) * DEG_PER_RAD) / tick;
};

/*
  What a PERFECT ground turn is worth, as a speed change per tick.

  Worth showing because on the ground it goes negative: friction takes
  |v|*friction*tick and acceleration can only ever add A, so past about 270 u/s
  the best available turn still loses speed.  A bar that implies otherwise is
  lying, and "you are bleeding as slowly as possible" is the honest reading.
*/
float(float speed, float gain, float wishspeed, float fric, float stopspeed, float tick) Strafe_GroundBest =
{
	local float vf, c;

	vf = Strafe_AfterFriction(speed, fric, stopspeed, tick);
	c  = Strafe_GroundOptCos(vf, gain, wishspeed) * vf;   // the optimal dot product

	return sqrt(vf * vf + 2 * gain * c + gain * gain) - speed;
};

/*
  THE SAME THING ON A RAMP, WHICH IS NOT THE SAME NUMBER.

  A surf ramp is air movement -- above normal.z 0.7 you are simply standing,
  so on anything steeper AirAccelerate runs exactly as it does in free
  flight.  What changes is that TryPlayerMove then clips the result back
  onto the plane, and the clip turns your velocity too.  With P = I - n n^T
  and G = gravity * tick, one tick is v' = v + g*P(w) - G*P(z), and the
  component that rotates you is

      g(1 - wn^2) + G*nz*wn          wn = dot(wishdir, n)

  wn = 0 gives back g/speed, so the flat formula above is this one on a
  plane you are not touching.

  This is a LARGE correction, not a refinement.  Checked in wrlines against
  a literal AirAccelerate -> gravity -> ClipVelocity tick at nz = 0.6 and
  1000 u/s, ridden across the fall line: wn = +0.8 is 55.2% of the flat
  ideal and wn = -0.8 is 16.8%.  Reusing the flat number on a ramp
  overstates the target by between 1.8x and 6x.

  n MUST point away from the surface, out towards the player.  wn's sign is
  the entire difference between those two rows, so an unoriented normal
  gives a confidently wrong answer rather than a slightly wrong one.

  RETURNS 0 WHEN THE MODEL HAS NO ANSWER, which is a real outcome and not a
  degenerate one.  `rot` is a signed quantity -- the two terms pull opposite
  ways on the into-ramp side -- and it genuinely crosses zero on a shallow
  face (nz ~ 0.3) when wishdir points nearly straight into the ramp.  This
  used to take fabs() of it, which folds the crossing into a V: the target
  dived to zero, err = (turn - ideal)/ideal exploded, and the bar slammed from
  one end to the other for a fraction of a second.  An absolute value is the
  wrong shape for a quantity whose sign means "the ramp is now doing the
  turning instead of you"; 0 is the honest answer, and every caller already
  treats ideal <= 0.001 as "show neutral, do not grade".
*/
float(float speed, float tick, float gain, float gravity, float nz, float wn) Strafe_IdealTurnPlane =
{
	local float bigg, rot;

	if (speed < 1)
		speed = 1;
	if (tick < 0.0001)
		tick = 0.015;
	if (wn < -1) wn = -1;
	if (wn >  1) wn =  1;

	bigg = gravity * tick;
	rot  = gain * (1 - wn * wn) + bigg * nz * wn;
	if (rot <= 0)
		return 0;

	return (atan2(rot, speed) * DEG_PER_RAD) / tick;
};

/*
  THE SAME "what is a perfect turn worth" NUMBER, ON A RAMP.

  One tick on a plane is  v' = v + a*P(w) - G*P(z),  P = I - n n^T,  G = g*tick.
  The gravity term does not depend on where you point, so fold it in first:

      u = v - G*P(z)        still in the plane, since v is
      |v'|^2 = |u|^2 + 2a(u.w) + a^2(1 - wn^2)      wn = dot(w, n)

  with a = min(rate, aircap - dot(v, w)) from AirAccelerate.

  AND THEN IT DOES NOT HAVE A CLOSED FORM, which is the whole reason this
  function is a search and not one line.  In free air the answer is "point
  perpendicular to your velocity", because w is free.  On a ramp it is NOT:
  AirMove zeroes the z of forward and right before building wishdir, so w is
  always HORIZONTAL, and the perpendicular-within-the-plane direction that would
  give wn = 0 is generally not horizontal.  Only one heading on any given ramp
  has wn = 0 -- the horizontal tangent, straight across the slope -- and it is
  the direction perpendicular to your velocity only by coincidence.

  I wrote the closed form first (sqrt(|u|^2 + gain^2) - |v|, the free-air
  hypotenuse with u swapped in) and it is WRONG: it evaluates the objective at a
  heading the player cannot point at, so it reports an unreachable upper bound
  and reports it largest exactly where the ramp is steepest.  A ceiling you
  cannot reach is worse than no ceiling, because you would spend the ride
  wondering what you were doing wrong.

  So: scan the heading.  Coarse pass around the circle to pick the basin, then
  two refinement rounds either side of the winner.  98 evaluations of a dozen
  flops, once per rendered frame.

  THE SCHEDULE IS MEASURED, NOT GUESSED.  Checked against a 200,000-step brute
  force over nz 0.15-0.69, across-slope and down-slope, at 300 to 3000 u/s: the
  worst shortfall anywhere in that sweep is 0.002 u/s, against a readout that
  prints one decimal.  One refinement round of 16 leaves 0.064, which is
  visible.  And the COARSE grid is the part that matters -- 90 coarse steps with
  two rounds of 10 is 112 evaluations and 0.224 u/s worst, twelve percent WORSE
  than 72 for more work, because the optimum sometimes sits next to a coarse
  sample that is not the best one and the refinement then polishes the wrong
  basin.  Do not "improve" these numbers without re-running that sweep.

  GRAVITY IS DELIBERATELY INSIDE THIS NUMBER.  On a ramp gravity is where the
  speed comes from -- that is the entire point of surfing -- so a "best" with it
  removed would read near zero on the fastest part of every map.  This says what
  the next tick can give you, all sources together, if your hand is perfect, and
  it is a 3D figure unlike the flat and ground ones because on a plane the
  acceleration has a vertical component.

  It shares Strafe_IdealTurnPlane's one-lump gravity model.  The real tick
  applies half of G before the clip and half after (PMSrc_StartGravity /
  PMSrc_FinishGravity), so the true answer carries a small residual into the
  plane; the same approximation is already what the target rate above rests on,
  and using two different models for the two halves of one panel would be worse
  than using one imperfect one for both.

  n MUST be oriented out towards the player, as everywhere else in this file.
*/
#define PLANEBEST_COARSE  72        // 5 degrees around the circle
#define PLANEBEST_ROUNDS  2         // refinement rounds after it
#define PLANEBEST_FINE    12        // steps per round, one span either side

// |v'|^2 for one candidate heading.  Split out because the coarse and fine
// passes must evaluate exactly the same thing.
float(vector vel, vector u, vector n, float rate, float aircap, float ph) Strafe_PlaneTrial =
{
	local vector w;
	local float c, a, wn;

	w = [cos(ph), sin(ph), 0];      // horizontal, as AirMove builds it

	// AirAccelerate: addspeed = cap - dot(v, wishdir), rate-limited.
	c = vel * w;
	a = aircap - c;
	if (a > rate) a = rate;
	if (a <= 0)
		return u * u;               // nothing to add from here

	wn = w * n;
	return (u * u) + 2 * a * (u * w) + a * a * (1 - wn * wn);
};

float(vector vel, float tick, float rate, float aircap, float gravity, vector n) Strafe_PlaneBest =
{
	local vector pz, u;
	local float bigg, speed, best2, s2, ph, dphi, mid, lo, i, r;

	if (tick < 0.0001)
		tick = 0.015;

	speed = vlen(vel);
	if (speed < 1)
		return 0;

	bigg = gravity * tick;

	// P(z): the in-plane part of the up axis.  Gravity pulls along -P(z), which
	// on any ramp you can ride is the down-slope direction.
	pz = '0 0 1' - n * n_z;
	u  = vel - pz * bigg;

	// Pointing nowhere useful is always available, so the search can only
	// improve on it and never has to report a loss it did not have to take.
	best2 = u * u;
	mid   = 0;

	dphi = 6.283185307179586 / PLANEBEST_COARSE;
	for (i = 0; i < PLANEBEST_COARSE; i = i + 1)
	{
		ph = i * dphi;
		s2 = Strafe_PlaneTrial(vel, u, n, rate, aircap, ph);
		if (s2 > best2) { best2 = s2; mid = ph; }
	}

	// Each round narrows to one previous step either side of the best heading
	// so far, so the span shrinks by PLANEBEST_FINE/2 every time.
	for (r = 0; r < PLANEBEST_ROUNDS; r = r + 1)
	{
		lo   = mid - dphi;
		dphi = (2 * dphi) / PLANEBEST_FINE;

		for (i = 0; i <= PLANEBEST_FINE; i = i + 1)
		{
			ph = lo + i * dphi;
			s2 = Strafe_PlaneTrial(vel, u, n, rate, aircap, ph);
			if (s2 > best2) { best2 = s2; mid = ph; }
		}
	}

	return sqrt(best2) - speed;
};

/*
  The "30" in the quality formula below, scaled for a plane.

  Redoing the steady-state step with the rotating component above leaves the
  30 carrying two terms: c = (1 - r) * (30 + K), K = G*nz*wn / (1 - wn^2).
  K = 0 is the flat case and gives back 30 exactly.  On an nz = 0.6 ramp K
  is about 16, so the same fractional error costs 2.35x as much quality --
  which is right, because the ramp is doing part of the turning and the part
  you are responsible for is correspondingly more sensitive.

  wn^2 -> 1 is a wall, where no amount of air acceleration rotates anything;
  the guard hands back the flat scale rather than an infinity.

  THE CLAMPS ARE NOT COSMETIC.  K is unbounded as wn^2 -> 1 and is NEGATIVE on
  the into-ramp side, so the old `if (s < 1) s = 1;` turned "this model has
  gone out of range" into "the scale is 1/30th of normal" -- which multiplies
  the grade's falloff by 0.033 and widens the green band from |1-r| < 0.2 to
  |1-r| < 3.1.  In other words the bar went green for turning at four times
  the target.  A scale that has left the geometry has to read as no answer,
  not as a pass, so the band below is tight and the fallback is neutral.
*/
float(float gravity, float tick, float nz, float wn, float aircap) Strafe_CScale =
{
	local float denom, k, s;

	if (tick < 0.0001)
		tick = 0.015;
	if (wn < -1) wn = -1;
	if (wn >  1) wn =  1;

	denom = 1 - wn * wn;
	if (denom < 0.05)
		return aircap;

	k = (gravity * tick) * nz * wn / denom;
	s = aircap + k;

	// Half to four times the flat scale.  Beyond that the steady-state
	// approximation the grade rests on has stopped describing the ride, and
	// falling back to the flat scale grades you as if you were in free air --
	// which is wrong, but wrong by a bounded factor rather than by 30x.
	if (s < aircap * 0.5) s = aircap * 0.5;
	if (s > aircap * 4.0) s = aircap * 4.0;
	return s;
};

/*
  HOW GOOD IS A TURN RATE, on a scale rather than in or out of a band.

  Picking a tolerance would have been an invention, so this comes out of
  AirAccelerate instead.  When the cap binds, a = 30 - c and

      d|v|^2 = 2(30-c)c + (30-c)^2 = 900 - c^2

  In steady state the view turns with the velocity, so with r = w/w*:

      c ~= 30(1 - r)      and      quality = (900 - c^2)/900 = 1 - (1 - r)^2

  Symmetric about r = 1.  Zero at r = 0 (not turning adds nothing) and zero
  again at r = 2, where wishdir has swung far enough to sit behind the
  velocity.  It reproduces the +-20% band it replaced: r in [0.8, 1.2] is
  quality >= 0.96.

  The one approximation is cos(theta) ~= 1, worth (c/|v|)^2 -- 0.09% at
  1000 u/s.  Everything else is exact.

  Returns -1 for "no answer" so a caller can show neutral rather than a bad
  grade.  Callers must ALSO check Strafe_CapBinds; this is handed two rates,
  not the cvars they came from, so it cannot check that itself.
*/
float(float turn, float ideal, float cscale, float aircap) Strafe_Quality =
{
	local float r, m, q;

	if (ideal <= 0.001 || turn < 0)
		return -1;
	if (cscale <= 0.001)
		cscale = aircap;

	// Normalised before squaring: algebraically identical to c^2/900, but this
	// way cscale == aircap makes the factor exactly 1 and the flat result
	// bit-identical, so adopting the plane-aware form moves no existing number.
	r = turn / ideal;
	m = (1 - r) * (cscale / aircap);
	q = 1 - m * m;
	if (q < 0) q = 0;
	if (q > 1) q = 1;
	return q;
};

/*
  The most energy air strafing can physically add, per second:

      P_max = ws^2 / (2 * g * tick) = 900 / (2*800*0.015) = 37.5 units/s

  Independent of speed -- which is what makes dE/dt divided by it a fair
  efficiency at any speed.  This is the denominator of the strafe gauge.
*/
float(float aircap, float gravity, float tick) Strafe_PowerCeiling =
{
	if (gravity < 1)   gravity = 1;
	if (tick < 0.0001) tick = 0.015;
	return (aircap * aircap) / (2 * gravity * tick);
};

/*
  Past this much of the ceiling on the GAIN side it was not the player, it
  was a booster or a teleport.  There is deliberately no matching limit on
  the loss side: losing at 350x the ceiling is a wall, and a wall is worth
  drawing.
*/
#define STRAFE_ETA_NOT_PLAYER   3.0
