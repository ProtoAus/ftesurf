/* Visual travel into an acknowledged held save's OWN loaded picture.
   Never sends a body pose, changes a clock or manufactures a recorder prefix. */
#define SL_LEAD_CAP 512
float sl_lead_buf, sl_lead_n, sl_lead_at, sl_lead_from, sl_lead_end, sl_lead_until;
float sl_lead_next, sl_lead_finalfrom, sl_lead_pending, sl_lead_seq, sl_lead_id;
vector sl_lead_target, sl_lead_angles, sl_lead_tail;

void() SaveLead_Clear =
{
	if (sl_lead_buf >= 1)
	{
		buf_del(sl_lead_buf);
		localcmd("cmd rec_savepos\n"); // releases only this hold preview's visibility eye
		PVS_Forget();
	}
	sl_lead_buf = sl_lead_n = sl_lead_until = sl_lead_next = sl_lead_pending = 0;
	sl_lead_applied = FALSE;
};

float() SaveLead_Done =
{
	if (sl_lead_buf < 1) return TRUE;
	if (sl_lead_pending) return (cltime >= sl_lead_pending);
	return (cltime >= sl_lead_until);
};

// Negative means the travel clock has not started; never invent an ACK ETA.
float() SaveLead_Remaining =
{
	if (sl_lead_buf < 1) return 0;
	if (sl_lead_pending) return -1;
	return max(0, sl_lead_until - cltime);
};

// A finite visual row, not evidence and not a movement instruction.
float(string row) SaveLead_Row =
{
	local float n, i;
	n = tokenize(row);
	if (n != 14 && n != 15) return FALSE;
	for (i = 0; i < n; i += 1)
		if (!Watch_OwnViewNumber(argv(i), 100000000)) return FALSE;
	return (stof(argv(0)) >= 0);
};

float() SaveLead_Ready =
{
	if (numclientseats != 1 || !LT_StatsAreMine()) return FALSE;
	if (serverkeyfloat("fs_savelead") != 1) return FALSE;
	if ((getstatf(STAT_FS_TIMERFLAGS) & TF_TAS) || getstatf(STAT_FS_TASPAUSE) || getstatf(STAT_FS_TASPENDING)) return FALSE;
	return (cvar("cl_sl_leadin") > 0 && rec_sl_holding && !rw_on && !rec_wt_on && !Spec_Active());
};

void() SaveLead_NoPath =
{
	SaveLead_Clear();
	if (SaveLead_Ready())
		print("^3save lead-in:^7 no local saved path; using the normal save hold\n");
};

// Copy NOW: later HOLD/endpoint stats must never retry against mutable tr_raw.
void(float seq, float id) SaveLead_Begin =
{
	local float duration, n, first, i, t, last;
	local string row;

	SaveLead_Clear();
	duration = bound(0, cvar("cl_sl_leadin"), 2);
	if (!SaveLead_Ready()) return;
	if (tr_raw < 1) { SaveLead_NoPath(); return; }
	n = buf_getsize(tr_raw);
	if (n < 2) { SaveLead_NoPath(); return; }
	row = bufstr_get(tr_raw, n - 1);
	if (!SaveLead_Row(row)) return;
	sl_lead_end = stof(argv(0));
	sl_lead_tail = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
	// Shorten a very dense window; NEVER decimate away a break/stitch marker.
	first = max(max(0, Trail_RawIndex(sl_lead_end - duration)), n - SL_LEAD_CAP);
	sl_lead_buf = buf_create_ex("string", 0);
	if (sl_lead_buf < 1) { sl_lead_buf = 0; return; }
	last = -1;
	sl_lead_finalfrom = 0;
	for (i = first; i < n; i += 1)
	{
		row = bufstr_get(tr_raw, i);
		if (!SaveLead_Row(row)) { SaveLead_Clear(); return; }
		t = stof(argv(0));
		if (t < last) { SaveLead_Clear(); return; }
		last = t;
		if ((stof(argv(7)) & 0x4000000) || stof(argv(8)) || stof(argv(9)))
			sl_lead_finalfrom = t;
		bufstr_set(sl_lead_buf, sl_lead_n, row);
		sl_lead_n += 1;
	}
	sl_lead_from = max(stof(bufstr_get(sl_lead_buf, 0)), sl_lead_end - duration);
	if (sl_lead_end - sl_lead_from < 0.03) { SaveLead_Clear(); return; }
	sl_lead_seq = seq;
	sl_lead_id = id;
	sl_lead_pending = cltime + 1; // bounded wait for independently delivered stats
	sl_lead_next = 1;
};

// One atomic, seq/id-bound endpoint. Separate cursor-vector deltas are not coherent.
float(string pose, float held) SaveLead_TryStart =
{
	local float i;

	if (sl_lead_buf < 1 || !sl_lead_pending || !held) return FALSE;
	if (tokenize(pose) != 9) return FALSE;
	if (strcmp(argv(0), "L")) return FALSE;
	for (i = 1; i < 9; i += 1)
		if (!Watch_OwnViewNumber(argv(i), 100000000)) return FALSE;
	if (stof(argv(1)) != sl_lead_seq || stof(argv(2)) != sl_lead_id) return FALSE;
	if (!(stof(argv(8)) == 0 || stof(argv(8)) == 1)) return FALSE;
	sl_lead_target = [stof(argv(3)), stof(argv(4)), stof(argv(5))];
	sl_lead_angles = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
	if (vlen(sl_lead_tail - sl_lead_target) > 128)
	{
		SaveLead_Clear();
		print("^3save lead-in:^7 saved path does not meet this save; using the held position\n");
		return FALSE;
	}
	sl_lead_pending = 0;
	sl_lead_at = cltime;
	sl_lead_until = cltime + sl_lead_end - sl_lead_from;
	PVS_Forget();
	return TRUE;
};

// Called after the real body's capture. Only the rendered eye/aim is replaced.
float() SaveLead_Camera =
{
	local float t, ta, tb, f, brk, vh, savedvh, endmix, duck, aflags, bflags;
	local vector a, b, aa, ab, p, aim, vo;
	local string row;

	sl_lead_applied = FALSE;
	if (sl_lead_buf < 1) return FALSE;
	if (!SaveLead_Ready() || getstatf(STAT_FS_SLSEQ) != sl_lead_seq)
	{
		SaveLead_Clear();
		return FALSE;
	}
	if (sl_lead_pending)
	{
		if (cltime >= sl_lead_pending)
		{
			SaveLead_Clear();
			print("^3save lead-in:^7 travel acknowledgement timed out; using the normal save hold\n");
			return FALSE;
		}
		if (!SaveLead_TryStart(getstats(STAT_FS_SLLEAD), getstatf(STAT_FS_HOLD))) return FALSE;
	}
	if (!getstatf(STAT_FS_HOLD) || cltime >= sl_lead_until)
	{
		SaveLead_Clear();
		return FALSE;
	}
	t = sl_lead_from + max(0, cltime - sl_lead_at);
	while (sl_lead_next < sl_lead_n - 1 && stof(bufstr_get(sl_lead_buf, sl_lead_next)) < t)
		sl_lead_next += 1;
	row = bufstr_get(sl_lead_buf, sl_lead_next - 1);
	if (!SaveLead_Row(row)) { SaveLead_Clear(); return FALSE; }
	ta = stof(argv(0)); a = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
	aa = [stof(argv(13)), stof(argv(10)), 0]; aflags = stof(argv(7));
	row = bufstr_get(sl_lead_buf, sl_lead_next);
	if (!SaveLead_Row(row)) { SaveLead_Clear(); return FALSE; }
	tb = stof(argv(0)); b = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
	ab = [stof(argv(13)), stof(argv(10)), 0]; bflags = stof(argv(7));
	brk = ((bflags & 0x4000000) || stof(argv(8)) || stof(argv(9)));
	f = (tb > ta) ? bound(0, (t - ta) / (tb - ta), 1) : 1;
	if (brk && f < 1) f = 0;
	p = a + (b - a) * f;
	aim = Interp_View(aa, ab, f);
	duck = ((f < 1 ? aflags : bflags) & WT_F_DUCKED);
	// Correct the last network-tick endpoint ONLY after the final discontinuity.
	endmix = 0;
	if (t >= sl_lead_finalfrom)
		endmix = bound(0, (t - (sl_lead_end - 0.08)) / 0.08, 1);
	p += (sl_lead_target - p) * endmix;
	aim = Interp_View(aim, [sl_lead_angles_x, sl_lead_angles_y, 0], endmix);
	vo = duck ? PM_DUCK_VIEW_OFS : PM_VIEW_OFS;
	vh = serverkeyfloat(duck ? "pm_duckviewheight" : "pm_viewheight");
	if (vh <= 0) vh = vo_z;
	vo = sl_lead_angles_z ? PM_DUCK_VIEW_OFS : PM_VIEW_OFS;
	savedvh = serverkeyfloat(sl_lead_angles_z ? "pm_duckviewheight" : "pm_viewheight");
	if (savedvh <= 0) savedvh = vo_z;
	vh += (savedvh - vh) * endmix;
	p += [0, 0, vh];
	setproperty(VF_ORIGIN, p);
	setproperty(VF_ANGLES, [aim_x, aim_y, 0]);
	sl_lead_applied = TRUE; // HUD_Feet keeps the body's pre-override capture
	PVS_PublishCmd(p, "rec_savepos");
	return TRUE;
};
