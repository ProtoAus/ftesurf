// P1559: acquire this install's completed lobby recordings with the existing
// owner-bound archive transport. Never opens a replay, publishes a run, or
// removes a completed local file. A later visit retries unfinished acquisition.
string ha_map, ha_profile, ha_runfile;
float ha_legs, ha_index, ha_row, ha_offset, ha_more, ha_phase, ha_cycle;
float ha_after, ha_finrec, ha_stagerec, ha_restart, ha_saved, ha_warnat;
int ha_zonegen;

void() History_Warn =
{
	if (!ha_warnat || cltime - ha_warnat > 60)
	{
		print("history: local replay download pending; source is retained on the lobby, retrying later\n");
		ha_warnat = cltime;
	}
};

void() History_Stop =
{
	if (ar_auto)
	{
		if (ar_state >= 2) localcmd(sprintf("cmd archive cancel %d\n", ar_query));
		Archive_ClientCancel(); ar_state = 0; ar_auto = FALSE;
	}
	ha_phase = ha_cycle = ha_restart = 0;
};

void() History_BuildLegs =
{
	local float i, track, leg, maxtrack, segs;
	if (ha_legs > 0) buf_del(ha_legs);
	ha_legs = buf_create_ex("string", 0);
	maxtrack = 0;
	for (i = 0; i < zone_count; i = i + 1)
		maxtrack = max(maxtrack, zone_track[i]);
	for (track = 0; track <= min(64, maxtrack); track = track + 1)
	{
		if (!Zone_TrackExists(track)) continue;
		bufstr_set(ha_legs, buf_getsize(ha_legs), sprintf("%d 0", track));
		segs = Zone_TrackSegs(track);
		if (segs > 1)
		for (leg = 1; leg <= min(128, segs); leg = leg + 1)
			bufstr_set(ha_legs, buf_getsize(ha_legs), sprintf("%d %d", track, leg));
	}
	ha_zonegen = zone_generation;
};

void() History_Request =
{
	local float track, leg;
	tokenize(bufstr_get(ha_legs, ha_index));
	track = stof(argv(0)); leg = stof(argv(1));
	ha_phase = 1;
	ha_after = cltime + 2.1; // retain the server's existing list admission limit
	Archive_ClientList(track, leg, ha_offset, TRUE);
};

void(float status) History_Listed =
{
	if (status == 3)
	{
		ha_phase = 0; ar_auto = FALSE; ha_after = cltime + 2.1;
		return; // retry this exact leg/page, never restart at an empty main
	}
	if (status == 0 || status == 4)
	{
		ha_more = (status == 4);
		ha_row = 0; ha_phase = 2;
		return;
	}
	History_Warn();
	History_Stop(); ha_after = cltime + 30;
};

void(float success) History_Received =
{
	if (success)
	{
		ha_saved = ha_saved + 1;
		return; // continue the same list; no UI or camera side effects
	}
	History_Warn();
	History_Stop(); ha_after = cltime + 30;
};

void() History_Rescan =
{
	ha_restart = TRUE;
	ha_after = 0;
};

void() History_Status =
{
	print(sprintf("history: %d replay(s) downloaded this session; %s; leg %d/%d, page offset %d\n",
		ha_saved, ha_cycle ? "syncing owner archive" : "idle / waiting", ha_index + 1,
		(ha_legs > 0) ? buf_getsize(ha_legs) : 0, ha_offset));
};

void() History_AutoFrame =
{
	local float fh, budget, count;
	local string map, profile, path, leaf;
	map = serverkey("map"); profile = serverkey("*movementprofile");
	if (strcmp(map, ha_map) || strcmp(profile, ha_profile) || ha_zonegen != zone_generation)
	{
		History_Stop();
		if (strcmp(ha_map, "")) strunzone(ha_map);
		if (strcmp(ha_profile, "")) strunzone(ha_profile);
		ha_map = strzone(map); ha_profile = strzone(profile);
		History_BuildLegs(); ha_index = ha_offset = 0; ha_after = cltime + 2;
		ha_finrec = getstatf(STAT_FS_FINREC);
		if (strcmp(ha_runfile, "")) strunzone(ha_runfile);
		ha_runfile = strzone(getstats(STAT_FS_RUNFILE));
		ha_stagerec = getstatf(STAT_FS_STAGEENDREC);
	}
	if (!Rec_ServerIsRemote() || !(getstatf(STAT_FS_LOBBY) & LS_LOBBY)
	    || strcmp(serverkey("fs_runhistory"), "1") || !strcmp(map, "") || zone_count < 1)
	{
		History_Stop();
		return;
	}
	leaf = getstats(STAT_FS_RUNFILE);
	if (ha_finrec != getstatf(STAT_FS_FINREC) || ha_stagerec != getstatf(STAT_FS_STAGEENDREC)
	    || (FS_HistoryLeaf(leaf) && strcmp(leaf, ha_runfile)))
	{
		ha_finrec = getstatf(STAT_FS_FINREC);
		ha_stagerec = getstatf(STAT_FS_STAGEENDREC);
		if (strcmp(ha_runfile, "")) strunzone(ha_runfile);
		ha_runfile = strzone(leaf);
		ha_restart = TRUE; ha_after = min(ha_after, cltime + 1);
	}
	// A foreground archive selection keeps its buffers and transfer. Let the
	// current automatic transfer finish, then yield rather than stealing UI rows.
	if (rec_sb_open || sc_held)
	{
		if (ar_auto && !ar_state) { History_Stop(); ha_after = cltime + 1; }
		return;
	}
	if (ar_state) return;
	if (!ha_cycle)
	{
		if (cltime < ha_after || ha_legs < 1) return;
		if (buf_getsize(ha_legs) < 1) return;
		ha_cycle = TRUE; ha_index = ha_offset = 0; ha_phase = 0; ha_restart = FALSE;
	}
	if (ha_phase == 0)
	{
		if (cltime < ha_after) return;
		History_Request();
		return;
	}
	if (ha_phase != 2) return;
	count = buf_getsize(ar_rows);
	for (budget = 0; budget < 8 && ha_row < count; budget = budget + 1)
	{
		ha_row = ha_row + 1;
		if (!FS_HistoryLeaf(bufstr_get(ar_rows, ha_row - 1))) continue;
		// P1696: a lobby makes no TAS run (its tools are refused there): a tas file offered here would be planted for Upload
		if (FS_TagFromName(FS_NameTag(substring(bufstr_get(ar_rows, ha_row - 1), 0, strlen(bufstr_get(ar_rows, ha_row - 1)) - 4))) == RT_TAS)
			continue;
		path = FS_MovementProfilePath(ar_profile,
			strcat(FS_RunDir(ar_map, ar_track, ar_leg), bufstr_get(ar_rows, ha_row - 1)));
		fh = fopen(path, FILE_READ);
		if (fh >= 0) { fclose(fh); continue; } // preserve existing bytes, even a damaged file
		Archive_ClientGet(ha_row);
		if (ar_state != 2) History_Received(FALSE);
		return;
	}
	if (ha_row < count) return;
	if (ha_more && count > 0)
	{
		ha_offset = ha_offset + count; ha_phase = 0;
		return;
	}
	ar_auto = FALSE; ha_index = ha_index + 1; ha_offset = ha_phase = 0;
	if (ha_index < buf_getsize(ha_legs)) return;
	ha_cycle = FALSE;
	ha_after = cltime + (ha_restart ? 1 : 300);
	ha_restart = FALSE;
};
