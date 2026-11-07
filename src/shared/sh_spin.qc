/*
  P1387: Patch 860's decorative motion as pure functions of a mover's clock, shared by the server
  (sv_entities.qc SV_SpRotTheta / SV_SpLinPos, which keep the logic: inputs, outputs, timers) and
  csprogs (cl_spin.qc, which draws a chain that is non-solid throughout from that clock, sent once).
*/
#define SPK_ROT     1           // func_rotating (sv_entities.qc vbsp_sp_kind)
#define SPK_LIN     2           // func_movelinear
#define SPK_FOLLOW  3           // a non-solid prop_* parented to one

float sp_wnow;                  // Sp_Theta's speed at that moment

// func_rotating's angle dt after its clock: ACCDCC's SpinUpMove / SpinDownMove / ReverseMove
// (bmodels.cpp:902-1000) as continuous ramps; a stop at the start orientation clamps at stopat.
float(float th, float w, float wt, float up, float dn, float stopping, float stopat, float dt) Sp_Theta =
{
	local float a, seg, rate;

	dt = max(0, dt);
	if (dn && w * wt < 0)
	{
		seg = fabs(w) / dn;
		if (dt < seg)
		{
			a = (w > 0) ? -dn : dn;
			sp_wnow = w + a * dt;
			return th + w * dt + 0.5 * a * dt * dt;
		}
		th = th + 0.5 * w * seg;
		dt = dt - seg;
		w = 0;
	}
	if (w != wt)
	{
		rate = (fabs(wt) > fabs(w)) ? up : dn;
		if (rate)
		{
			seg = fabs(wt - w) / rate;
			if (dt < seg)
			{
				a = (wt > w) ? rate : -rate;
				sp_wnow = w + a * dt;
				return th + w * dt + 0.5 * a * dt * dt;
			}
			th = th + 0.5 * (w + wt) * seg;
			dt = dt - seg;
		}
		w = wt;
	}
	th = th + w * dt;
	sp_wnow = w;
	if (stopping)
	if ((w > 0 && th >= stopat) || (w < 0 && th <= stopat))
	{
		sp_wnow = 0;
		return stopat;
	}
	return th;
};

// func_movelinear's position 0..1 dt after its clock, held at the goal.
float(float pos, float dir, float speed, float dt, float movedistance, float ideal) Sp_LinPos =
{
	local float p;

	if (!dir)
		return pos;
	p = pos + dir * speed * dt / movedistance;
	if (dir > 0 && p > ideal)
		p = ideal;
	if (dir < 0 && p < ideal)
		p = ideal;
	return p;
};
