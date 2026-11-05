// Configure + grant is one VM transaction. Validate every byte/ticket first.
void(entity e, float argc) SV_TASPlanCommand =
{
	local float next, count, ticket, mode, bits, human, amount, follow;
	local vector moves, angles;

	next = !strcmp(argv(1), "next");
	if (!FS_TASPlanRead(argc)) goto bad;
	mode = fs_tasp_mode; bits = fs_tasp_bits; moves = fs_tasp_move;
	amount = fs_tasp_amount; follow = fs_tasp_follow;
	human = (mode >= TAS_PLAN_GUIDE);
	angles = [FS_TASAngleWord(fs_tasp_angles_x), FS_TASAngleWord(fs_tasp_angles_y), 0];
	count = ticket = 0;
	if (next)
	{
		if (!FS_TASNumber(argv(8))) goto bad;
		count = fs_tas_number;
		ticket = e.run_tas_req + 1;
		if ((!human && argc == 10) || (human && argc == 12))
		{
			if (!FS_TASNumber(argv(human ? 11 : 9))) goto bad;
			ticket = fs_tas_number;
		}
		if (!SV_TASStepReady(e, count, ticket)) return;
	}
	else if (!SV_TASCanPause(e)) return;
	if (!e.run_tas_paused || e.run_tas_pending || e.run_tas_replaystate == TAS_TAPE_STAGING ||
	    e.run_tas_replaystate == TAS_TAPE_ACTIVE)
	{
		sprint(e, PRINT_HIGH, "tas: pause and finish/cancel the current queue before changing controls\n");
		return;
	}
	if (e.run_tas_plancap < (human ? TAS_GUIDE_CAP : TAS_PLAN_CAP))
	{
		sprint(e, PRINT_HIGH, "tas: these controls require the updated native engine/server\n");
		return;
	}
	if (!checkbuiltin(tas_tape)) return;
	if (tas_tape(e, human ? TAS_OP_CONTROLSET : TAS_OP_PLANSET, mode, human ? amount : 0, moves, angles, bits) != 1)
	{
		sprint(e, PRINT_HIGH, "tas: input configuration refused; no steps queued\n");
		return;
	}
	if (human) e.run_tas_pitchfollow = follow;
	if (next) SV_TASQueueSteps(e, count, ticket);
	else sprint(e, PRINT_HIGH, sprintf("tas: %s controls configured; body still paused\n", FS_TASPlanName(mode)));
	return;
:bad
	sprint(e, PRINT_HIGH, "tas: plan mode forward side pitch yaw bits | next mode forward side pitch yaw bits count; guide/hold also take amount follow(0/1) before an optional request ticket\n");
};
