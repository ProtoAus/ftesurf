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
===========================================================================
*/
string(float ticks, float tickrate) Time_TickString =
{
	local float s, m, h, ms, neg;

	if (tickrate <= 0)
		tickrate = PM_TICK;

	neg = (ticks < 0);
	if (neg)
		ticks = -ticks;

	// Round to the millisecond FIRST and derive the rest from the integer, so
	// 59.9996 s reads 1:00.000 rather than 0:60.000.
	ms = floor(ticks * tickrate * 1000 + 0.5);

	h  = floor(ms / 3600000);   ms = ms - h * 3600000;
	m  = floor(ms / 60000);     ms = ms - m * 60000;
	s  = floor(ms / 1000);      ms = ms - s * 1000;

	if (h > 0)
		return sprintf("%s%g:%02g:%02g.%03g", neg ? "-" : "", h, m, s, ms);
	return sprintf("%s%g:%02g.%03g", neg ? "-" : "", m, s, ms);
};

// The +/- form used for a split against a personal best.  Always signed --
// "0.000" with no sign in front of it reads as an absolute time.
string(float ticks, float tickrate) Time_DeltaString =
{
	if (ticks >= 0)
		return strcat("+", Time_TickString(ticks, tickrate));
	return Time_TickString(ticks, tickrate);
};
