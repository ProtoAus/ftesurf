// Synthetic fitness only: actual CEM functions run in the standalone qclib VM.
float failures, checks;
void(float ok, string msg) check =
{
	checks = checks + 1;
	if (!ok) { puts("FAIL "); puts(msg); puts("\n"); failures = failures + 1; }
};
void(float a, float b, string msg) near = { check(fabs(a - b) < 0.0001, msg); };
void(float a, float b, string msg) same = { check(a == b, msg); };
void() rng = { topt_r1 = 123; topt_r2 = 456; topt_r3 = 789; };
float saved[320], r1, r2, r3;
void() main =
{
	local entity e;
	local float i, j, pass, v, w, spread;
	e = spawn(); e.topt_kd = 16; e.topt_kn = 12; e.topt_elead = 1; e.topt_kleadj = 15;
	e.topt_dir = 1; e.topt_cegen = 100;
	// Acting pristine control: the old grid inherits a stale best; an invalid generation picks five elites.
	for (j = 0; j < 16; j = j + 1) { topt_kbest[j] = 947 + j; topt_kmean[j] = 99; topt_ksig[j] = 40; }
	e.topt_bestv = -1; e.topt_kgen = -1; e.topt_kidx = 0; rng();
	for (i = 0; i < TOPT_CEGRID; i = i + 1) { BaselineNext(e); BaselineResult(e, -1); }
	near(topt_kmean[0], 947, "pristine stale-best control acts");
	for (i = 0; i < 20; i = i + 1)
	{
		for (j = 0; j < 16; j = j + 1) { topt_kcur[j] = 0; topt_kpop[i * 16 + j] = 0; }
		BaselineResult(e, -1);
	}
	w = 0; for (i = 0; i < 20; i = i + 1) w = w + topt_kel[i];
	near(w, 5, "pristine invalid-elite control acts");
	check(topt_ksig[0] < 40, "pristine invalid spread collapse acts");
	puts("PASS pristine stale-best and invalid-elite controls\n");
	// Distinct stale patterns must be neutralized before otherwise identical invalid searches.
	for (pass = 0; pass < 2; pass = pass + 1)
	{
		for (j = 0; j < 16; j = j + 1) { topt_kbest[j] = (pass ? -731 : 947) + j; topt_kmean[j] = 99; topt_ksig[j] = 1; }
		SV_TASOptCurveReset(e);
		for (j = 0; j < 16; j = j + 1)
		{
			near(topt_kbest[j], 0, "reset best"); near(topt_kmean[j], 0, "reset mean");
			near(topt_ksig[j], j < 12 ? 40 : 200, "reset spread");
		}
		e.topt_bestv = -1; e.topt_kgen = -1; e.topt_kidx = 0; rng();
		for (i = 0; i < TOPT_CEGRID; i = i + 1) { SV_TASOptCurveNext(e); SV_TASOptCurveResult(e, -1); }
		for (i = 0; i < 20; i = i + 1) { SV_TASOptCurveNext(e); SV_TASOptCurveResult(e, -1); }
		for (j = 0; j < 16; j = j + 1)
		{
			near(topt_kbest[j], 0, "invalid best"); near(topt_kmean[j], 0, "invalid mean");
			near(topt_ksig[j], j < 12 ? 40 : 200, "invalid spread");
		}
		for (i = 0; i < 20; i = i + 1) near(topt_kel[i], 0, "no arbitrary invalid elites");
	}
	puts("PASS reset and all-invalid grid/generation\n");
	// Valid top five are 15..19, mean=17, variance=2: unchanged adaptation math must act.
	SV_TASOptCurveReset(e); e.topt_kgen = 0; e.topt_kidx = 0; e.topt_bestv = -1;
	for (i = 0; i < 20; i = i + 1)
	{
		for (j = 0; j < 16; j = j + 1) { topt_kcur[j] = i; topt_kpop[i * 16 + j] = i; }
		SV_TASOptCurveResult(e, i);
	}
	for (i = 0; i < 20; i = i + 1) near(topt_kel[i], i >= 15, "ranked elites");
	near(topt_kmean[0], 11.9, "ranked mean math"); near(topt_ksig[0], 0.7 * sqrt(2) + 12, "ranked spread math");
	near(topt_kbest[15], 19, "valid best lead");
	SV_TASOptCurveReset(e); e.topt_kgen = 0; e.topt_kidx = 0; e.topt_bestv = -1;
	for (i = 0; i < 20; i = i + 1)
	{
		for (j = 0; j < 16; j = j + 1) { topt_kcur[j] = i; topt_kpop[i * 16 + j] = i; }
		v = -1; if (i == 7) v = 0; if (i == 18) v = 1; SV_TASOptCurveResult(e, v);
	}
	for (i = 0; i < 20; i = i + 1) near(topt_kel[i], (i == 7 || i == 18), "mixed elite excludes cuts, includes zero");
	near(topt_kmean[0], 8.75, "mixed mean");
	puts("PASS valid ranked math and mixed zero/cuts\n");
	// Penalized trajectories may have legitimate negative fitness: only -1 means invalid.
	SV_TASOptCurveReset(e); e.topt_kgen = 0; e.topt_kidx = 0; e.topt_bestv = -1;
	for (i = 0; i < 20; i = i + 1)
	{
		for (j = 0; j < 16; j = j + 1) { topt_kcur[j] = i; topt_kpop[i * 16 + j] = i; }
		SV_TASOptCurveResult(e, i - 100);
	}
	for (i = 0; i < 20; i = i + 1) near(topt_kel[i], i >= 15, "all-negative valid elites");
	near(topt_kmean[0], 11.9, "all-negative valid mean");
	SV_TASOptCurveReset(e); e.topt_kgen = 0; e.topt_kidx = 0; e.topt_bestv = -1;
	for (i = 0; i < 20; i = i + 1)
	{
		for (j = 0; j < 16; j = j + 1) { topt_kcur[j] = i; topt_kpop[i * 16 + j] = i; }
		v = -1; if (i == 7) v = -500; if (i == 18) v = -200; SV_TASOptCurveResult(e, v);
	}
	for (i = 0; i < 20; i = i + 1) near(topt_kel[i], (i == 7 || i == 18), "negative valid elites exclude higher sentinel");
	near(topt_kmean[0], 8.75, "negative mixed mean");
	puts("PASS legitimate negative fitness, including mixed invalid sentinels\n");
	// Generic and guide-following samplers, heavy tails off/on: production samples and RNG match pristine.
	for (pass = 0; pass < 4; pass = pass + 1)
	{
		e.topt_mode = (pass >= 2) ? 64 : 0; e.topt_efol = (pass >= 2); e.topt_freeq = (pass & 1);
		e.topt_kgen = 2; SV_TASOptCurveReset(e);
		for (j = 0; j < 16; j = j + 1) { topt_kmean[j] = j; topt_ksig[j] = j < 12 ? 12 : 75; }
		rng();
		for (i = 0; i < 20; i = i + 1)
		{
			e.topt_kidx = i; BaselineNext(e);
			for (j = 0; j < 16; j = j + 1) saved[i * 16 + j] = topt_kcur[j];
		}
		r1 = topt_r1; r2 = topt_r2; r3 = topt_r3; rng();
		for (i = 0; i < 20; i = i + 1)
		{
			e.topt_kidx = i; SV_TASOptCurveNext(e);
			for (j = 0; j < 16; j = j + 1)
			{
				same(topt_kcur[j], saved[i * 16 + j], "pristine sampler all20");
				spread = (j >= 12) ? TOPT_AIMR : ((pass >= 2) ? TOPT_DQOFF : TOPT_QMAX);
				if (e.topt_freeq && j < 12) spread = min(TOPT_QENGINE, 6 * spread);
				check(fabs(topt_kcur[j]) <= spread, "bounds");
				topt_bat_kcur[i * 16 + j] = topt_kcur[j];
			}
		}
		same(topt_r1, r1, "sampler RNG1"); same(topt_r2, r2, "sampler RNG2"); same(topt_r3, r3, "sampler RNG3");
		held = 1;
		for (i = 0; i < 20; i = i + 1)
		{
			e.topt_kidx = i; SV_TASOptCurveNext(e);
			for (j = 0; j < 16; j = j + 1) same(topt_kcur[j], topt_bat_kcur[i * 16 + j], "held sample");
		}
		same(topt_r1, r1, "held RNG1"); same(topt_r2, r2, "held RNG2"); same(topt_r3, r3, "held RNG3"); held = 0;
	}
	puts("PASS pristine all20, kd16 lead, generic/demo, freeq off/on and held retrieval\n");
	// KnotTick=j here: partition/eligibility only, not physical event timing.
	for (pass = 0; pass < 13; pass = pass + 1)
	{
		e.topt_mode = 64; e.topt_efol = 1; e.topt_kn = 12; e.topt_kd = 16;
		e.topt_kgen = -1; e.topt_kidx = 14; e.topt_flick = 21;
		e.topt_catch = 0; e.topt_tgtj = 11; e.topt_kex = 0; w = 9;
		if (pass == 1) { e.topt_flick = 0; e.topt_catch = 3; w = 8; }
		if (pass == 2) { e.topt_flick = 12; e.topt_catch = 3; w = 6; }
		if (pass == 3) { e.topt_flick = 13; w = 1; }
		if (pass == 4) { e.topt_flick = 50; w = 6; }
		if (pass == 5) { e.topt_flick = 0; w = 6; }
		if (pass == 6) { e.topt_flick = 0; e.topt_catch = 12; w = 6; }
		if (pass == 7) { e.topt_mode = 0; w = 6; }
		if (pass == 8) { e.topt_efol = 0; w = 6; }
		if (pass == 9) { e.topt_kn = 11; e.topt_flick = 0; w = 5.5; }
		if (pass == 10) { e.topt_flick = 0; e.topt_kex = 8; w = 8; }
		if (pass == 11) { e.topt_flick = 0; e.topt_kex = 50; w = 6; }
		if (pass == 12) { e.topt_flick = 0; e.topt_kex = 1; w = 1; }
		v = -90;
		if (e.topt_mode & 64) v = v * (e.topt_efol ? TOPT_DQOFF : TOPT_DOFF) / 120;
		if (pass == 0)
		{
			BaselineNext(e);
			near(topt_kcur[6], v * 0.5, "acting pristine midpoint at knot6");
			near(topt_kcur[8], v * 0.5, "acting pristine midpoint at knot8");
		}
		rng(); SV_TASOptCurveNext(e);
		for (j = 0; j < e.topt_kn; j = j + 1)
			near(topt_kcur[j], (j < w) ? v : v * 0.5, "event grid partition and exact fallback");
		same(topt_r1, 123, "grid unchanged RNG1");
		same(topt_r2, 456, "grid unchanged RNG2");
		same(topt_r3, 789, "grid unchanged RNG3");
	}
	puts("PASS acting launch/catch partitions and all eligibility fallbacks (synthetic KnotTick)\n");
	if (!failures) { puts("PASS CEM checks="); puts(ftos(checks)); puts("\n"); }
};
