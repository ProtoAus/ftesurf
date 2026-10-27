// P1065: validate local syntax, use the existing active-seat/ticket channel.
float(float argc, float seat) CL_TASInputCommand =
{
	local float first, last, field, value, ticket, query;

	query = !strcmp(argv(1), "inputs");
	if (!query && strcmp(argv(1), "edit") && strcmp(argv(1), "replay")) return FALSE;
	if (getstatf(STAT_FS_TASINPUT) != 1)
	{
		print("tas: input editing requires P1065 native/server support\n");
		return TRUE;
	}
	if (query)
	{
		first = 8;
		if (argc == 3)
		{
			if (!FS_TASNumber(argv(2))) goto bad;
			first = fs_tas_number;
		}
		if (argc < 2 || argc > 3 || first < 1 || first > 16 || floor(first) != first) goto bad;
		localcmd(sprintf("p%g cmd tas inputs %g\n", seat + 1, first));
		return TRUE;
	}
	if (cvar("cl_threadedphysics") || checkextension("FTE_VRINPUTS") || !LT_StatsAreMine())
	{
		print("tas: editing needs your own body, cl_threadedphysics 0 and duration inputs\n");
		return TRUE;
	}
	if (!strcmp(argv(1), "replay"))
	{
		if (argc != 3) goto bad;
	}
	else if (argc != 5 && argc != 6) goto bad;
	if (!FS_TASNumber(argv(2))) goto bad;
	first = fs_tas_number; last = first;
	if (!strcmp(argv(1), "edit"))
	{
		if (argc == 6)
		{
			if (!FS_TASNumber(argv(3))) goto bad;
			last = fs_tas_number;
		}
		field = FS_TASEditField(argv(argc-2));
		if (!FS_TASNumber(argv(argc-1))) goto bad;
		value = fs_tas_number;
		if (!FS_TASEditValue(field, value)) goto bad;
	}
	if (!(first >= 1 && first < 16000000 && floor(first) == first &&
	      last >= first && last < 16000000 && floor(last) == last)) goto bad;
	ticket = max(run_tas_request[seat], getstatf(STAT_FS_TASREQUEST)) + 1;
	if (ticket > 16000000) { print("tas: request budget exhausted; reconnect\n"); return TRUE; }
	run_tas_request[seat] = ticket;
	if (!strcmp(argv(1), "replay"))
		localcmd(sprintf("p%g cmd tas replay %s req %.0f\n", seat + 1, argv(2), ticket));
	else if (argc == 5)
		localcmd(sprintf("p%g cmd tas edit %s %s %s req %.0f\n", seat + 1, argv(2), argv(3), argv(4), ticket));
	else
		localcmd(sprintf("p%g cmd tas edit %s %s %s %s req %.0f\n", seat + 1, argv(2), argv(3), argv(4), argv(5), ticket));
	return TRUE;
:bad
	print("tas: inputs [1..16] | replay first | edit first [last] forward/side/up/pitch/yaw/jump/duck/walk value\n");
	return TRUE;
};
