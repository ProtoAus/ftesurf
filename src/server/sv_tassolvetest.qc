// Pure local diagnostic. No native movement, player metadata or disk writes.
float tsol_testfailed, tsol_testcount;
void(string label, float ok) SV_TASSolveCheck =
{
	tsol_testcount = tsol_testcount+1;
	if (!ok) tsol_testfailed = tsol_testfailed+1;
	print(sprintf("P1351 %s %s\n",ok ? "ok" : "FAIL",label));
};
void() SV_TASSolveSelftest =
{
	local float row[TAS_INPUT_STRIDE];
	local float bits, candidate, ok, i;
	local float *probes;
	local vector score;
	tsol_testfailed = tsol_testcount = 0;
	SV_TASSolveCheck("baseline yaw exact",FS_TASSolveYaw(1234,-5678,1234,0) == -5678);
	SV_TASSolveCheck("gentle first turn",FS_TASSolveYaw(0,1000,0,1) == 980);
	SV_TASSolveCheck("gentle cumulative turn",FS_TASSolveYaw(1000,2000,980,1) == 1960);
	SV_TASSolveCheck("sharp cumulative turn",FS_TASSolveYaw(1000,2000,1020,2) == 2040);
	SV_TASSolveCheck("signed yaw wrap",FS_TASSolveYaw(32760,-32760,32760,4) == -32751);
	SV_TASSolveCheck("posture preserves yaw",FS_TASSolveYaw(1,200,19,5) == 200);
	SV_TASSolveCheck("baseline compact bits exact",FS_TASSolveButtons(5,0) == 5);
	SV_TASSolveCheck("compact duck only bit",FS_TASSolveButtons(5,5) == 7);
	SV_TASSolveCheck("compact stand only bit",FS_TASSolveButtons(7,6) == 5);
	ok = TRUE;
	for (bits = 0; bits <= 7; bits = bits+1)
	for (candidate = 0; candidate < TAS_SOLVE_CANDIDATES; candidate = candidate+1)
	{
		for (i = 0; i < TAS_INPUT_STRIDE; i = i+1) row[i] = 0;
		row[6] = bits;
		if (candidate == 5 || candidate == 7 || candidate == 8) SV_TASInputChange(row,0,7,1);
		else if (candidate == 6) SV_TASInputChange(row,0,7,0);
		if (FS_TASSolveButtons(bits,candidate) != row[6] || FS_TASSolveButtons(bits,candidate) > 7) ok = FALSE;
	}
	SV_TASSolveCheck("all72 compact masks match EXISTING native editor",ok);
	SV_TASSolveCheck("fast missed ramp loses",!FS_TASSolveBetter(FALSE,4000,10,TRUE,1800,20));
	SV_TASSolveCheck("slower feasible beats invalid",FS_TASSolveBetter(TRUE,1800,20,FALSE,4000,10));
	SV_TASSolveCheck("best found speed",FS_TASSolveBetter(TRUE,1900,20,TRUE,1800,20));
	SV_TASSolveCheck("equal speed earlier tie",FS_TASSolveBetter(TRUE,1800,19,TRUE,1800,20));
	SV_TASSolveCheck("late target loses",!FS_TASSolveWindow(109,100));
	SV_TASSolveCheck("inclusive arrival window",FS_TASSolveWindow(108,100));
	SV_TASSolveCheck("actual-region positive",FS_TASSolveContact('.8 0 .6',16,'1 2 3','.8 0 .6',16,'1 2 3','200 0 0','200 0 0'));
	SV_TASSolveCheck("wrong face negative",!FS_TASSolveContact('-.8 0 .6',16,'1 2 3','.8 0 .6',16,'1 2 3','200 0 0','200 0 0'));
	SV_TASSolveCheck("wrong plane negative",!FS_TASSolveContact('.8 0 .6',17,'1 2 3','.8 0 .6',16,'1 2 3','200 0 0','200 0 0'));
	SV_TASSolveCheck("wrong region negative",!FS_TASSolveContact('.8 0 .6',16,'100 2 3','.8 0 .6',16,'1 2 3','200 0 0','200 0 0'));
	SV_TASSolveCheck("wrong travel direction negative",!FS_TASSolveContact('.8 0 .6',16,'1 2 3','.8 0 .6',16,'1 2 3','-200 0 0','200 0 0'));
	// Target-only baseline300/35 would invent improvement for an unchanged
	// candidate scoring400/31. Both must use the same first eligible window.
	probes = memalloc(3*TAS_SOLVE_PROBE_STRIDE*sizeof(float)); ok = FALSE;
	if (probes)
	{
		FS_TASSolveProbe(probes,0,20,'.8 0 .6',16,'20 0 0','1000 0 0');
		FS_TASSolveProbe(probes,1,31,'.8 0 .6',16,'20 0 0','400 0 0');
		FS_TASSolveProbe(probes,2,35,'.8 0 .6',16,'20 0 0','300 0 0');
		score = FS_TASSolveBaseline(probes,3,35,'.8 0 .6',16,'20 0 0','300 0 0');
		ok = (score == '400 31 1');
		score = FS_TASSolveBaseline(probes,TAS_SOLVE_PROBES+1,35,'.8 0 .6',16,'20 0 0','300 0 0');
		if (score_z) ok = FALSE;
		memfree(probes);
	}
	SV_TASSolveCheck("fair baseline earliest eligible window, outside/count guards",ok);
	print(sprintf("P1351 helper result: %.0f checks, %.0f failed; NOT a native/two-ramp acceptance\n",tsol_testcount,tsol_testfailed));
};
