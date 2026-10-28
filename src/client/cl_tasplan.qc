// Included after cl_main's active-seat request counters; GUI uses this channel too.
float(float argc, float seat) CL_TASPlanCommand =
{
	local float count, ticket, next;
	local string line;
	if (!strcmp(argv(1), "timeline")) return TASTimeline_ConsoleCommand(argc,seat);
	if (!strcmp(argv(1), "menu"))
	{
		if (argc == 2) TASUI_Toggle(seat);
		else if (argc == 3 && !strcmp(argv(2), "status"))
		{
			print(sprintf("tas menu: open %g claims %g frames %g draft %s native %g\n", tasu_open, UI_CursorHeld(), tasu_frames, FS_TASPlanName(tasu_mode), getstatf(STAT_FS_TASPLANCAP)));
			print(sprintf("tas menu draft: f%g s%g pitch%.13f yaw%.13f bits%g\n",
				tasu_forward, tasu_side, tasu_pitch, tasu_yaw, tasu_bits));
		}
		else print("tas: menu | menu status\n");
		return TRUE;
	}
	if (!strcmp(argv(1), "mouse"))
	{
		if (!cvar_type("cl_tas_mouselock")) print("tas: mouse lock needs the updated client engine\n");
		else if (argc == 2) TASUI_Mouse();
		else if (argc == 3 && !strcmp(argv(2), "on")) cvar_set("cl_tas_mouselock", "1");
		else if (argc == 3 && !strcmp(argv(2), "off")) cvar_set("cl_tas_mouselock", "0");
		else if (argc == 3 && !strcmp(argv(2), "status")) print(sprintf("tas: paused mouse lock %g (own body only)\n", cvar("cl_tas_mouselock")));
		else print("tas: mouse [on/off/status]\n");
		return TRUE;
	}
	next = !strcmp(argv(1), "next");
	if (!next && strcmp(argv(1), "plan")) return FALSE;
	if ((!next && argc != 8) || (next && argc != 9) || !FS_TASPlanRead(argc)) goto bad;
	if (getstatf(STAT_FS_TASPLANCAP) < TAS_PLAN_CAP)
	{
		print("tas: next-input authoring needs the updated native engine/server\n");
		return TRUE;
	}
	if (cvar("cl_threadedphysics") || checkextension("FTE_VRINPUTS") || !LT_StatsAreMine())
	{
		print("tas: next input needs your own body, cl_threadedphysics 0 and duration inputs\n");
		return TRUE;
	}
	count = ticket = 0;
	if (next)
	{
		if (!FS_TASNumber(argv(8))) goto bad;
		count = fs_tas_number;
		if (!(count >= 1 && count <= TAS_TAPE_MAX && floor(count) == count)) goto bad;
		ticket = max(run_tas_request[seat], getstatf(STAT_FS_TASREQUEST)) + 1;
		if (ticket > 16000000) { print("tas: request budget exhausted; reconnect\n"); return TRUE; }
		run_tas_request[seat] = ticket;
	}
	// Preserve validated angle tokens: decimal shortening can flip a yaw word.
	line = sprintf("p%g cmd tas %s %s %g %g %s %s", seat + 1, argv(1), FS_TASPlanName(fs_tasp_mode),
		fs_tasp_move_x, fs_tasp_move_y, argv(5), argv(6));
	line = strcat(line, sprintf(" %g", fs_tasp_bits));
	if (next) line = strcat(line, sprintf(" %g %.0f", count, ticket));
	localcmd(strcat(line, "\n"));
	return TRUE;
:bad
	print("tas: menu | mouse [on/off/status] | plan mode forward side pitch yaw bits | next mode forward side pitch yaw bits count; mode=live/manual/left/right, bits=jump1+duck2+walk4\n");
	return TRUE;
};
