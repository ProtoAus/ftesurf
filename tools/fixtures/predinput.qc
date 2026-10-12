// Test-only: append to cl_progs.src in an owned build. Never a product include.
float predinput_apply;
vector predinput_origin;
vector predinput_velocity;
float predinput_onground;
float predinput_pmtype;
float predinput_forceduck;
float pif_seq;
float pif_offset;
vector pif_placed;
float pif_mode;

void(float seat, float seq, float seconds, float offset) CSQC_PredictPlayerPreMove =
{
	float testmode, basetype;
	vector before, beforevel;

	testmode = cvar("test_predinput");
	before = predinput_origin;
	beforevel = predinput_velocity;
	basetype = predinput_pmtype;
	if (testmode == 1)
	{
		if (offset == 0)
		{
			predinput_apply = 1 | 2 | 16;
			predinput_origin = before + '0 0 64';
			predinput_velocity = '1000 0 0';
			predinput_onground = 0;
			predinput_pmtype = 0;
			pif_placed = predinput_origin;
			print(sprintf("PREDINPUT PLACE seq=%g org=%v\n", seq, pif_placed));
		}
	}
	else if (testmode == 2)
	{
		predinput_apply = 2 | 4 | 8 | 16;
		predinput_pmtype = 5;
		predinput_forceduck = 2;
	}
	if ((seq != pif_seq) || (offset != pif_offset) || (testmode != pif_mode))
		print(sprintf("PREDINPUT mode=%g seq=%g dt=%.6f off=%.6f org=%v vel=%v basepm=%g\n",
		              testmode, seq, seconds, offset, before, beforevel, basetype));
	pif_seq = seq;
	pif_offset = offset;
	pif_mode = testmode;
};
