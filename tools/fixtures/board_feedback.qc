// Test-only live-stat and sound seam. Included last, never in shipped CSQC.
float bp_checks, bp_fail, bp_scene, bp_grade;
void(float ok, string name) BP_Check =
{
	bp_checks = bp_checks + 1;
	if (!ok) { bp_fail = bp_fail + 1; print("BOARD FAIL: ", name, "\n"); }
};
void(vector vin) BP_Arrive =
{
	bp_seq = bp_seq + 1;
	bp_vin = vin;
	bp_normal = '0 0.7071068 0.7071068';
	Board_Frame('0 0 100', vin, FALSE);
};
void() BP_Test =
{
	local float i, before;

	bp_active = TRUE;
	bp_quiet = TRUE;
	bp_seq = 100;
	bp_ramp = 0;
	Board_Clear();
	Board_Frame('0 0 100', '1200 0 0', FALSE); // adopt old counter, no sound
	bp_calls = 0;
	BP_Check(board_perfect_streak == 0, "counter resync is not a perfect");
	cvar_set("hud_board_sound", "1");
	cvar_set("hud_board_volume", "0.35");
	BP_Arrive('1200 -50 0');
	BP_Check(board_grade == 0, "real grade of perfect arrival");
	BP_Check(board_perfect_streak == 1 && bp_calls == 1, "first live perfect acted once");
	BP_Check(bp_pitch == 100 && bp_volume == 0.35, "base pitch and volume");
	BP_Check(strcmp(bp_sample, "ftesurf/board_dong.wav") == 0, "dong path");
	Board_Frame('0 0 100', '1200 -50 0', FALSE);
	BP_Check(board_perfect_streak == 1 && bp_calls == 1, "repeated snapshot does not act");
	// Real ground/air edges with no new ramp-board counter: a bhop, not a fail.
	Board_Frame('0 0 100', '1200 0 0', TRUE);
	Board_Frame('0 0 100', '1200 0 300', FALSE);
	Board_Frame('0 0 100', '1200 0 0', TRUE);
	Board_Frame('0 0 100', '1200 0 300', FALSE);
	BP_Check(board_perfect_streak == 1 && bp_calls == 1, "bhops neither reset nor reward");
	BP_Arrive('1200 -50 0');
	BP_Check(board_perfect_streak == 2 && bp_calls == 2, "second live perfect");
	BP_Check(fabs(bp_pitch - 105.9463) < 0.001, "one-semitone rise");
	Board_ResetRun();
	Board_Frame('0 0 100', '1200 0 0', FALSE);
	BP_Check(board_perfect_streak == 2 && bp_calls == 2, "run reset and resync preserve streak");
	BP_Arrive('10 -50 0');
	BP_Check(board_perfect_streak == 2 && bp_calls == 2, "ungraded low-speed contact abstains");
	BP_Arrive('400 -400 0');
	BP_Check(board_grade != 0, "non-perfect arrival really graded");
	BP_Check(board_perfect_streak == 0 && bp_calls == 2, "non-perfect clears without sound");
	BP_Arrive('1200 -50 0');
	BP_Check(board_perfect_streak == 1 && bp_pitch == 100, "next perfect returns to base");
	cvar_set("hud_board_sound", "0");
	before = bp_calls;
	BP_Arrive('1200 -50 0');
	BP_Check(board_perfect_streak == 2 && bp_calls == before, "sound off still tracks streak");
	cvar_set("hud_board_sound", "2");
	cvar_set("hud_board_volume", "2");
	BP_Arrive('1200 -50 0');
	BP_Check(strcmp(bp_sample, "ftesurf/board_bong.wav") == 0 && bp_volume == 1, "bong and clamped volume");
	cvar_set("hud_board_sound", "3");
	cvar_set("hud_board_volume", "0.35");
	BP_Arrive('1200 -50 0');
	BP_Check(strcmp(bp_sample, "ftesurf/board_bell.wav") == 0, "bell path");
	cvar_set("hud_board_volume", "-1");
	before = bp_calls;
	BP_Arrive('1200 -50 0');
	BP_Check(board_perfect_streak == 5 && bp_calls == before, "mute tracks without playback");
	cvar_set("hud_board_volume", "0.35");
	for (i = 0; i < 20; i = i + 1) BP_Arrive('1200 -50 0');
	BP_Check(board_perfect_streak == 13 && bp_pitch == 200, "one octave cap");
	// Exercise the actual replay scanner branch with a failing grade.
	before = bp_calls;
	rec_wt_build = TRUE;
	board_ov_now = cltime;
	board_ov_seq = bp_seq + 1;
	board_ov_bnorm = bp_normal;
	board_ov_bvel = '400 -400 0';
	board_ov_riding = 0;
	Board_Frame('0 0 100', '400 -400 0', FALSE);
	BP_Check(board_grade != 0, "replay scanner really graded failure");
	BP_Check(board_perfect_streak == 13 && bp_calls == before, "replay failure cannot reset or play");
	board_ov_seq = board_ov_seq + 1;
	board_ov_bvel = '1200 -50 0';
	Board_Frame('0 0 100', '1200 -50 0', FALSE);
	BP_Check(board_grade == 0 && bp_calls == before, "replay perfect cannot play");
	rec_wt_build = FALSE;
	Board_Clear();
	BP_Check(board_perfect_streak == 0, "new map clears streak");
	BP_Check(HE_OptCount("board") == 12, "four editor settings exist");
	BP_Check(strcmp(Gfx_Field(HE_OptDef("board", 8), 0, "|"), "hud_board_sound") == 0, "sound picker binding");
	BP_Check(strcmp(Gfx_Field(HE_OptDef("board", 11), 0, "|"), "hud_board_bounce") == 0, "bounce toggle binding");
	bp_active = FALSE;
	bp_quiet = FALSE;
	print(sprintf("BOARD CHECKS: %g checks, %g failures\n", bp_checks, bp_fail));
};
void(vector scr) BP_ScenePrepare =
{
	if (!bp_scene) return;
	// Isolate glyph pixels from animated map dust/model silhouettes.
	drawfill([scr_x * 0.35, scr_y * 0.44, 0], [scr_x * 0.3, scr_y * 0.13, 0], '0 0 0', 1, 0);
	board_time = cltime - 0.1;
	board_now = cltime;
	board_grade = bp_grade;
	board_kept = 99.95;
	board_loss = 0.04;
};
float() BP_Command =
{
	local float i;
	local string cmd;

	cmd = argv(0);
	if (cmd == "board_feedback_test") { BP_Test(); return TRUE; }
	if (cmd == "board_feedback_scene")
	{
		bp_scene = TRUE;
		bp_grade = stof(argv(1));
		return TRUE;
	}
	if (cmd == "board_feedback_editor")
	{
		for (i = 0; i < he_n; i = i + 1)
			if (he_id[i] == "board") ui_he_sel = i;
		return TRUE;
	}
	if (cmd == "board_feedback_audio")
	{
		bp_scene = FALSE;
		bp_active = TRUE;
		bp_quiet = FALSE;
		if (argv(1) == "reset")
		{
			Board_Clear();
			Board_Frame('0 0 100', '1200 0 0', FALSE);
			print(sprintf("BOARD AUDIO START: %g\n", cltime));
		}
		else if (argv(1) == "fail") BP_Arrive('400 -400 0');
		else if (argv(1) == "hop")
		{
			Board_Frame('0 0 100', '1200 0 0', TRUE);
			Board_Frame('0 0 100', '1200 0 300', FALSE);
		}
		else BP_Arrive('1200 -50 0');
		print(sprintf("BOARD AUDIO: %s streak %g time %g\n", argv(1), board_perfect_streak, cltime));
		return TRUE;
	}
	return FALSE;
};
