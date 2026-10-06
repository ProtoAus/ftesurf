/* Patch 502: visual replay prefix for a practice save. The .rec remains
   client-owned and is never submitted as authoritative run evidence. */
void() Trail_ReplayClear =
{
	if (tr_rep_raw >= 1)
		buf_del(tr_rep_raw);
	tr_rep_raw = 0;
};

// Opaque correlation, not a command count: raw cmd and localcmd can be
// delivered in the opposite order. This ticket cannot grant run authority.
string(string c) Trail_Command =
{
	if (strcmp(c, "sl_save") && strstrofs(c, "sl_saveat ", 0) != 0 &&
	    strstrofs(c, "sl_saveview ", 0) != 0 && strstrofs(c, "sl_goview ", 0) != 0)
		return c;
	if (!tr_ticket)
		tr_ticket = max(getstatf(STAT_FS_SLTRAILTAG), getstatf(STAT_FS_SLSAVEACK));
	tr_ticket = (tr_ticket < 16000000) ? tr_ticket + 1 : 1;
	tr_saveack = tr_ticket;
	if (strstrofs(c, "sl_saveat ", 0) == 0)
	if (!strcmp(substring(c, strlen(c) - 3, 3), " go"))
	{
		tr_timedgo_ack = tr_ticket;
		tr_go_visual_t = tr_cur_t;
	}
	if (tr_rep_raw >= 1)
	{
		tr_rep_ack = tr_ticket;
		tr_rep_go = (strstrofs(c, "sl_goview ", 0) == 0);
	}
	return strcat(c, " ", sprintf("%d", tr_ticket));
};

void() Trail_RewindPrefix =
{
	local float i, n;
	local string s;
	Trail_ReplayClear();
	tr_rep_raw = buf_create_ex("string", 0);
	if (tr_rep_raw < 1 || tr_raw < 1)
		return;
	tr_rep_tick = tr_tick;
	tr_rep_end = tr_cur_t;
	n = buf_getsize(tr_raw);
	for (i = 0; i < n; i = i + 1)
	{
		s = bufstr_get(tr_raw, i);
		if (stof(s) > tr_rep_end)
			break;
		bufstr_set(tr_rep_raw, i, s);
	}
};

void() Trail_ReplayPrefix =
{
	local float i, n, t, fl, brk, stitch, bits, pitch, yaw;
	local vector o, v, nrm, wsh;
	local string s;
	Trail_ReplayClear();
	tr_rep_raw = buf_create_ex("string", 0);
	if (tr_rep_raw < 1)
		return;
	tr_rep_tick = rec_wt_tickrate;
	tr_rep_end = rec_wt_time;
	brk = stitch = 0;
	for (i = rec_wt_rec0; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		if (!Watch_IsSample(s))
		{
			bits = Watch_RecordBits(s);
			if (bits & WTR_FORCE) brk = TRUE;
			if (bits & WTR_STITCH) stitch = TRUE;
			continue;
		}
		tokenize(s);
		t = stof(argv(WT_C_T));
		if (t > rec_wt_time)
			break;
		if (t < 0)
			continue;
		o = [stof(argv(WT_C_ORG)), stof(argv(WT_C_ORG+1)), stof(argv(WT_C_ORG+2))];
		v = [stof(argv(WT_C_VEL)), stof(argv(WT_C_VEL+1)), stof(argv(WT_C_VEL+2))];
		fl = stof(argv(WT_C_FLAGS));
		pitch = stof(argv(WT_C_PITCH));
		yaw = stof(argv(WT_C_YAW));
		nrm = rec_wt_v4 ? [stof(argv(WT_C_NORM)), stof(argv(WT_C_NORM+1)), stof(argv(WT_C_NORM+2))] : '0 0 0';
		wsh = Watch_WishOf(yaw, stof(argv(WT_C_MOVE)), stof(argv(WT_C_MOVE+1)));
		n = buf_getsize(tr_rep_raw);
		if (n >= LN_CAP * 4)
			break;
		bufstr_set(tr_rep_raw, n, Trail_RawSample(o, v, fl, t, brk, stitch,
		                                       [yaw, nrm_z, wsh * nrm], pitch));
		brk = stitch = 0;
	}
};
