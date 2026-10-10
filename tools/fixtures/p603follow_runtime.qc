//Disposable finite-body/own-row seam. No HTTP or Online_FindMine acceptance.
void(string mode) P603_Board =
{
	local float f;
	local string body, line, path;
	Online_FreeQuery();
	ob_q_map = strzone(serverkey("map"));
	ob_q_tier = strzone(Scores_TierOf());
	ob_q_style = strzone(Scores_StyleOf());
	ob_q_track = rec_sb_legtrack[rec_sb_leg];
	ob_q_leg = rec_sb_legnum[rec_sb_leg];
	ob_q_zoned = TRUE;
	ob_q_gen = ob_gen;
	path = "cfg/test/p603board.json";
	if (!strcmp(mode, "empty")) path = "cfg/test/p603empty.json";
	if (!strcmp(mode, "wrongleg")) path = "cfg/test/p603wrongleg.json";
	if (!strcmp(mode, "wrongstyle")) path = "cfg/test/p603wrongstyle.json";
	f = fopen(path, FILE_READ);
	if (f < 0) { print("P603 FOLLOW ERROR missing board\n"); return; }
	body = "";
	for (line = fgets(f); line; line = fgets(f)) body = strcat(body, line);
	fclose(f);
	Online_Parse(body);
	//The parser/storage is real; own identity is an explicit test-only input.
	ob_mine = -1;
	if (!strcmp(mode, "mine") || !strcmp(mode, "stale")) ob_mine = 7;
	if (!strcmp(mode, "stale"))
	{
		ob_state = OBS_FETCH;
		ob_sent = cltime;
		ob_q_gen = ob_gen - 1;
	}
};

void(string label) P603_FollowProbe =
{
	local float selected, first, last, i, n;
	local string standing;
	selected = first = last = -1;
	standing = "";
	if (scn_cells != __NULL__)
	{
		n = (scn_count - 5) / 9;
		standing = bufstr_get(scn_labels, 4);
		if (n > 0)
		{
			first = stof(bufstr_get(scn_labels, 5));
			last = stof(bufstr_get(scn_labels, 5 + (n - 1) * 9));
		}
		if (scn_cells[19])
			for (i = 0; i < n; i = i + 1)
				if (scn_cells[17] == scn_tokens[i]) selected = scn_page + i;
	}
	print(sprintf("P603 FOLLOW %s seek=%g wait=%g finished=%g outside=%g mine=%g online=%g\n",
		label, rec_sb_seek, rec_sb_finwait, Scores_FinishedOnline(), Scores_StandingOutside(), ob_mine, ob_n));
	print(sprintf("P603 META %s page=%g selected=%g first=%g last=%g count=%g painted=%g\n",
		label, scn_page, selected, first, last, scn_count, scn_painted));
	print(sprintf("P603 STANDING %s: %s\n", label, standing));
	print(sprintf("P603 SCROLL %s local=%g online=%g watch=%g\n",
		label, rec_sb_scroll_y, rec_sb_oscroll_y, rec_wt_open));
};

float(string cmd) P603_FollowCommand =
{
	local string op;
	if (strcmp(argv(0), "p603follow")) return FALSE;
	op = argv(1);
	if (!strcmp(op, "probe")) P603_FollowProbe(argv(2));
	else if (!strcmp(op, "board")) P603_Board(argv(2));
	else if (!strcmp(op, "wait")) rec_sb_finwait = TRUE;
	else if (!strcmp(op, "answer")) Scores_NoteAnswer(TRUE, 99, 3150);
	else if (!strcmp(op, "wrongleg")) { rec_sb_finleg = 1; rec_sb_seek = TRUE; }
	else if (!strcmp(op, "rightleg")) rec_sb_finleg = 0;
	else if (!strcmp(op, "wrongstyle")) rec_sb_finflags = TF_SEGMENT;
	else if (!strcmp(op, "rightstyle")) rec_sb_finflags = 0;
	else print("P603 FOLLOW ERROR unknown command\n");
	return TRUE;
};
