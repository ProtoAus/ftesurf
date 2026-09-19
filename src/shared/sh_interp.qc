/*
===========================================================================
  sh_interp.qc -- one speller for sampled-motion interpolation.

  The replay viewer (cl_watch.qc) and the body stream (cl_body.qc) both turn
  tick samples into per-frame poses; they must agree, so both call these.
  Pure functions, no globals.  Client-only today (cl_progs.src).
===========================================================================
*/

#define INTERP_SNAP     0       // a teleport between the two samples: do not blend
#define INTERP_LINEAR   1       // velocities disagree with the move (clip, push)
#define INTERP_HERMITE  2       // velocities explain the move: cubic is exact enough

// An angle in [-180, 180).  Moved from cl_watch.qc (build 24's yaw wrap).
float(float a) Interp_Wrap =
{
	return a - floor((a + 180) / 360) * 360;
};

// The signed shortest turn from a to b.
float(float a, float b) Interp_Arc =
{
	return Interp_Wrap(b - a);
};

float(float a, float b, float f) Interp_Angle =
{
	return Interp_Wrap(a + Interp_Arc(a, b) * f);
};

// Pitch and yaw each on the shortest arc, roll 0.  Not a quaternion slerp:
// a pitch-heavy path must not pick up roll.
vector(vector va, vector vb, float f) Interp_View =
{
	return [Interp_Angle(va_x, vb_x, f), Interp_Angle(va_y, vb_y, f), 0];
};

// Source's SimpleSpline (pm_source.c:389), clamped.
float(float x) Interp_Smooth =
{
	if (x <= 0)
		return 0;
	if (x >= 1)
		return 1;
	return x * x * (3 - 2 * x);
};

// Cubic Hermite from p0 to p1 over dt seconds, tangents v*dt, at s in [0,1].
vector(vector p0, vector v0, vector p1, vector v1, float dt, float s) Interp_Hermite =
{
	local float s2, s3;

	s2 = s * s;
	s3 = s2 * s;
	return p0 * (2 * s3 - 3 * s2 + 1)
	     + v0 * (dt * (s3 - 2 * s2 + s))
	     + p1 * (3 * s2 - 2 * s3)
	     + v1 * (dt * (s3 - s2));
};

/*
  Which interpolation a sample pair supports.  r is how far the move misses
  the trapezoid of the two velocities.  SNAP past half the summed speeds plus
  64 u (the smallest real jump in 239 files missed it by 69.8 u); LINEAR past
  1 u + 5% of the move (clip planes, boosters); HERMITE otherwise.
*/
float(vector p0, vector v0, vector p1, vector v1, float dt) Interp_Fit =
{
	local vector d;
	local float r;

	d = p1 - p0;
	r = vlen(d - (v0 + v1) * (0.5 * dt));
	if (r > 0.5 * (vlen(v0) + vlen(v1)) * dt + 64)
		return INTERP_SNAP;
	if (r > 1 + 0.05 * vlen(d))
		return INTERP_LINEAR;
	return INTERP_HERMITE;
};
