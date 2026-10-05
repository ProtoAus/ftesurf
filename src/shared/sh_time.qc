/*
===========================================================================
  sh_time.qc -- run times, formatted.

  Twelve lines in a file of their own because BOTH VMs print them and they
  must agree to the millisecond: the server says your time in chat, the HUD
  draws it, and the .rec header carries the tick count both were derived
  from.  Two copies of this would eventually disagree by a rounding rule and
  the bug would look like the timer being wrong.

  TICKS, NOT SECONDS, is the interface.  Momentum's leaderboard times are
  integer tick counts (m_iEndTick - m_iStartTick) and every comparison this
  game makes -- against a personal best, between two splits -- is exact in
  ticks and only approximate in seconds.  The tick RATE is a parameter rather
  than a constant because the two VMs read it from different places
  (cvar("pm_ticrate") on the server, serverkeyfloat on the client) and
  because pm_ticrate is settable.

  AND IT IS AN INTEGER INTERFACE UNDERNEATH, because a float32 millisecond
  count is not a number you can format: `ticks * tickrate * 1000` in one
  float32 chain is 1-3 ms off on most values past 4,096,003 ms (68 minutes)
  -- 9,149,677 of the 16,777,216 below 2^24, modelled case for case in
  tools/p496time.py.  Time_TickMs is the exact product, Time_MsString the one
  formatter, and Time_TickString the pair.  Everything that already holds
  milliseconds calls Time_MsString directly rather than pretending they are
  ticks of a 0.001 s rate, which is what the float32 chain was worst at.
===========================================================================
*/

/*
  Whole milliseconds, exactly, from a tick count and a seconds-per-tick rate.

  The product is taken as a COMPENSATED PAIR (Dekker's two-product: 4097 =
  2^12+1 splits a 24-bit mantissa in half), so `p + err` IS the real product
  of the two float32 inputs rather than a 6e-8-relative approximation of it.
  Only the sub-second remainder is then scaled -- under 1000, where a float32
  is good to 6e-5 ms, so the whole path is exact to well inside the digit it
  prints.  Residual, measured: 6 of 463,116 modelled cases differ by 1 ms
  from float64, all of them an exact half-millisecond tie at 233 hours, where
  the rate the caller passed is itself 50 ms uncertain.

  Clamped at 2147483 s (24 days), where sec * 1000 would wrap the int, and at
  1e15 ticks, where the 4097 split would overflow.  Neither is reachable from
  a run; both are reachable from a corrupt header, and a wrapped int prints as
  a negative time.  (And fteqcc takes no exponent in a literal, hence the
  1000000000000000 below.)

  EVERY INTEGER LITERAL IN BOTH FUNCTIONS CARRIES AN `i` SUFFIX, and that is
  not decoration.  A QC literal is a FLOAT unless it is suffixed, so `sec *
  1000` promotes the product to float32 and the assignment stores a quantised
  value back into the int: measured in both VMs, `2144999 * 1000 + 952` gives
  2144999936 with bare literals and 2144999952 with `1000i`/`952i` -- this
  function's whole point, undone above 2^24, with NO compiler warning.  The
  only thing that said anything was `%i` in a sprintf refusing a float (F324).
*/
int(float ticks, float tickrate) Time_TickMs =
{
	local float u, v, p, err, c, uh, ul, vh, vl, r;
	local int sec, ms, neg;

	if (tickrate <= 0)
		tickrate = PM_TICK;

	neg = (ticks < 0);
	u = neg ? -ticks : ticks;
	v = tickrate;

	p = u * v;
	if (p >= 2147483 || u >= 1000000000000000)
		return neg ? -2147483000i : 2147483000i;

	c = 4097 * u;   uh = c - (c - u);   ul = u - uh;
	c = 4097 * v;   vh = c - (c - v);   vl = v - vh;
	err = ((uh * vh - p) + uh * vl + ul * vh) + ul * vl;

	sec = (int)p;                       // truncates toward zero; p >= 0
	r = p - (float)sec;                 // exact while sec < 2^24 (194 days)
	ms = (int)floor((r + err) * 1000 + 0.5);
	if (ms >= 1000i)
	{
		ms = ms - 1000i;
		sec = sec + 1i;
	}
	else if (ms < 0i)                   // err under a whole second of p
	{
		ms = ms + 1000i;
		sec = sec - 1i;
	}

	ms = ms + sec * 1000i;
	return neg ? -ms : ms;
};

/*
  The ONE formatter: m:ss.mmm with minutes unbounded, h:mm:ss.mmm once there
  is an hour.  Integer throughout, so the split is exact at 10 hours as well
  as at 10 seconds -- a float32 ms count is quantised past 2^24 (4 h 39 m),
  which is where the runs that need this live.
*/
string(int ms) Time_MsString =
{
	local int h, m, s, neg;

	neg = 0i;
	if (ms < 0i)
	{
		neg = 1i;
		ms = -ms;
	}

	h  = ms / 3600000i;   ms = ms - h * 3600000i;
	m  = ms / 60000i;     ms = ms - m * 60000i;
	s  = ms / 1000i;      ms = ms - s * 1000i;

	if (h > 0i)
		return sprintf("%s%g:%02g:%02g.%03g", neg ? "-" : "",
		               (float)h, (float)m, (float)s, (float)ms);
	return sprintf("%s%g:%02g.%03g", neg ? "-" : "",
	               (float)m, (float)s, (float)ms);
};

string(float ticks, float tickrate) Time_TickString =
{
	return Time_MsString(Time_TickMs(ticks, tickrate));
};

// The +/- form used for a split against a personal best.  Always signed --
// "0.000" with no sign in front of it reads as an absolute time.
string(float ticks, float tickrate) Time_DeltaString =
{
	if (ticks >= 0)
		return strcat("+", Time_TickString(ticks, tickrate));
	return Time_TickString(ticks, tickrate);
};

// A countdown in whole seconds, rounded up so 0:00 means now: "m:ss" or "h:mm:ss".
string(float secs) Time_Clock =
{
	local float h, m, s;

	s = ceil(max(0, secs));
	h = floor(s / 3600);    s = s - h * 3600;
	m = floor(s / 60);      s = s - m * 60;
	if (h > 0)
		return sprintf("%g:%02g:%02g", h, m, s);
	return sprintf("%g:%02g", m, s);
};

/*
  `timefmt` -- the harness handle for the three functions above, and the only
  way to grade them: one line per case, the integer ms beside the string it
  formats to.  The client registers it (CSQC_Init) and the server reaches it
  through sv_player.qc's `cmd` chain, so one listen-server arm covers BOTH
  VMs' copies of this file and tags say which printed (tools/p496time.py).

  %.9g on both numbers because nine significant digits is what round-trips a
  float32, and %i on the ms because %g would print 8.38861e+08 and %.0f would
  print a float32's quantisation of it rather than the int.  %.0f on the
  ticks is no better: it prints 0.5 as "0" and loses the case.
*/
void(string tag, float ticks, float rate) Time_Print =
{
	print(sprintf("tf %s %.9g %.9g %i %s\n", tag, ticks, rate,
	              Time_TickMs(ticks, rate), Time_TickString(ticks, rate)));
};

float(string tag) Time_ConsoleCommand =
{
	local string a;
	local float i, n;

	a = argv(1);
	if (a == "sweep")
	{
		n = stof(argv(3));
		for (i = 0; i < n; i = i + 1)
			Time_Print(tag, i * stof(argv(4)), stof(argv(2)));
		return TRUE;
	}
	if (a == "")
	{
		print("timefmt <ticks> <rate> | timefmt sweep <rate> <n> <step>\n");
		return TRUE;
	}
	Time_Print(tag, stof(a), stof(argv(2)));
	return TRUE;
};
