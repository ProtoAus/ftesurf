/* Visual travel into an acknowledged held save's OWN loaded picture.
   Never sends a body pose, changes a clock or manufactures a recorder prefix.
   P1384: it starts on the load key's press from what this client already has (SaveLead_Press), so
   it looks the same at any ping; the server's load event binds it or ends it. */
#define SL_LEAD_CAP 512
#define SL_LEAD_LATE 0.1        // P1384: an answer-started travel only this soon after the press
float sl_lead_buf, sl_lead_n, sl_lead_at, sl_lead_from, sl_lead_end, sl_lead_until;
float sl_lead_next, sl_lead_finalfrom, sl_lead_pending, sl_lead_seq, sl_lead_id;
float sl_lead_early;            // P1384: 1 from the press, 2 bound to the server's load, 3 its pose checked
vector sl_lead_target, sl_lead_angles, sl_lead_tail;
float sl_pic_buf, sl_pic_ticks; // P1384: the tail of one save's picture, so a press reads no file
string sl_pic_path;

void() SaveLead_Clear =
{
	if (sl_lead_buf >= 1)
	{
		buf_del(sl_lead_buf);
		localcmd("cmd rec_savepos\n"); // releases only this hold preview's visibility eye
		PVS_Forget();
	}
	sl_lead_buf = sl_lead_n = sl_lead_until = sl_lead_next = sl_lead_pending = sl_lead_early = 0;
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
	if (serverkeyfloat("fs_savelead") < 1) return FALSE;
	if ((getstatf(STAT_FS_TIMERFLAGS) & TF_TAS) || getstatf(STAT_FS_TASPAUSE) || getstatf(STAT_FS_TASPENDING)) return FALSE;
	return (cvar("cl_sl_leadin") > 0 && rec_sl_holding && !rw_on && !rec_wt_on && !Spec_Active());
};


void() SaveLead_NoPath =
{
	SaveLead_Clear();
	if (SaveLead_Ready())
		print("^3save lead-in:^7 no local saved path; using the normal save hold\n");
};

// The last `duration` of src's rows, to its last row, into sl_lead_buf; FALSE when none fit.
// Shorten a very dense window; NEVER decimate away a break/stitch marker.
float(float src, float duration) SaveLead_Copy =
{
	local float n, first, hi, mid, i, t, last;
	local string row;

	n = buf_getsize(src);
	if (n < 2) return FALSE;
	row = bufstr_get(src, n - 1);
	if (!SaveLead_Row(row)) return FALSE;
	sl_lead_end = stof(argv(0));
	sl_lead_tail = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
	// Trail_RawIndex over src: the last row at/before the window's start.
	first = 0;
	hi = n - 1;
	t = sl_lead_end - duration;
	while (first < hi)
	{
		mid = ceil((first + hi) * 0.5);
		if (stof(bufstr_get(src, mid)) <= t) first = mid;
		else hi = mid - 1;
	}
	first = max(first, n - SL_LEAD_CAP);
	sl_lead_buf = buf_create_ex("string", 0);
	if (sl_lead_buf < 1) { sl_lead_buf = 0; return FALSE; }
	last = -1;
	sl_lead_finalfrom = 0;
	for (i = first; i < n; i += 1)
	{
		row = bufstr_get(src, i);
		if (!SaveLead_Row(row)) return FALSE;
		t = stof(argv(0));
		if (t < last) return FALSE;
		last = t;
		if ((stof(argv(7)) & 0x4000000) || stof(argv(8)) || stof(argv(9)))
			sl_lead_finalfrom = t;
		bufstr_set(sl_lead_buf, sl_lead_n, row);
		sl_lead_n += 1;
	}
	sl_lead_from = max(stof(bufstr_get(sl_lead_buf, 0)), sl_lead_end - duration);
	return (sl_lead_end - sl_lead_from >= 0.03);
};

/*
  Trail_Frame, on every load event. pic: 1 Trail_Load put this save's picture in tr_raw, 0 tr_raw
  is the retained failed line (a start reset), -1 no picture.
  P1384: while this hold's load is unanswered an event is an earlier load's and is left alone; the
  press's own answer binds the press travel (the folder it was read from) or, when that travel has
  run already, starts no second one. Any other start is late against the press (rec_sl_leadt0, the
  load's or a held step's) and skipped past SL_LEAD_LATE: a round trip late, it jumped the view from
  the save back up the path.
*/
void(float seq, float id, float pic) SaveLead_Begin =
{
	local float mine;

	if (rec_sl_leadans && !SaveLoc_LoadAnswered()) return;
	mine = rec_sl_leadans;
	rec_sl_leadans = FALSE;
	if (mine && sl_lead_early == 1 && sl_lead_buf >= 1 && id == sl_lead_id)
	{
		sl_lead_seq = seq;
		sl_lead_early = 2;
		PVS_Forget();           // the hold exists now: SV_SaveLeadEyeCmd took no earlier eye
		return;
	}
	SaveLead_Clear();
	if (mine && rec_sl_leadhad) return;
	if (!pic) return;
	if (pic < 0) { SaveLead_NoPath(); return; }
	if (!SaveLead_Ready()) return;
	if (cltime - rec_sl_leadt0 > SL_LEAD_LATE) return;
	if (tr_raw < 1 || buf_getsize(tr_raw) < 2) { SaveLead_NoPath(); return; }
	// Copy NOW: later HOLD/endpoint stats must never retry against mutable tr_raw.
	if (!SaveLead_Copy(tr_raw, bound(0, cvar("cl_sl_leadin"), 2))) { SaveLead_Clear(); return; }
	sl_lead_seq = seq;
	sl_lead_id = id;
	sl_lead_pending = cltime + 1; // bounded wait for independently delivered stats
	sl_lead_next = 1;
};

void() SaveLead_Forget =
{
	if (sl_pic_buf >= 1) buf_del(sl_pic_buf);
	sl_pic_buf = 0;
	if (sl_pic_path != "") strunzone(sl_pic_path);
	sl_pic_path = "";
};

// P1384: Trail_Save's picture as written (rows 0..last of raw), so the next press reads no file.
void(float id, float ticks, float raw, float last) SaveLead_Remember =
{
	local float i;

	SaveLead_Forget();
	if (last < 0) return;
	sl_pic_buf = buf_create_ex("string", 0);
	if (sl_pic_buf < 1) { sl_pic_buf = 0; return; }
	for (i = max(0, last - SL_LEAD_CAP + 1); i <= last; i += 1)
		bufstr_set(sl_pic_buf, buf_getsize(sl_pic_buf), bufstr_get(raw, i));
	sl_pic_path = strzone(Trail_SavePath(id));
	sl_pic_ticks = ticks;
};

// P1384: the last SL_LEAD_CAP rows of save id's picture at ticks: Trail_Load's header test, then its
// rows to the first past the save's clock or the first bad row.
float(float id, float ticks) SaveLead_Cache =
{
	local float f, n, tick, timed, endt, ring, i, k;
	local int sz;
	local string p, s;

	p = Trail_SavePath(id);
	if (sl_pic_buf >= 1 && sl_pic_ticks == ticks && !strcmp(p, sl_pic_path))
		return TRUE;
	SaveLead_Forget();
	f = fopen(p, FILE_READ);
	if (f < 0) return FALSE;
	n = tokenize(fgets(f));
	tick = stof(argv(2));
	timed = (n >= 5) ? stof(argv(4)) : (stof(argv(3)) > 0);
	if (strcmp(argv(0), "FTESURF-TRAIL") || stof(argv(1)) != 1 || tick <= 0 || stof(argv(3)) != ticks)
	{
		fclose(f);
		return FALSE;
	}
	endt = Trail_RawClock(timed ? ticks * tick : 99999999);
	// Only the last 96 KiB (~770 rows; SL_LEAD_CAP needs 512): the whole of a 5.7 MB picture was
	// 80 ms on the press (bench1). Trail_Save writes no row past the save's clock, nor a bad one.
	sz = fsize(f);
	if (sz > 98304i)
	{
		fseek(f, sz - 98304i);
		fgets(f);               // the rest of a cut row
	}
	ring = buf_create_ex("string", 0);
	if (ring < 1) { fclose(f); return FALSE; }
	n = 0;
	for (i = 0; i < LN_CAP * 4; i += 1)
	{
		s = fgets(f);
		if (!strcmp(s, "")) break;
		k = tokenize(s);
		if ((k != 14 && k != 15) || stof(argv(0)) > endt) break;
		bufstr_set(ring, n - floor(n / SL_LEAD_CAP) * SL_LEAD_CAP, s);
		n += 1;
	}
	fclose(f);
	sl_pic_buf = buf_create_ex("string", 0);
	if (sl_pic_buf < 1) { sl_pic_buf = 0; buf_del(ring); return FALSE; }
	for (i = max(0, n - SL_LEAD_CAP); i < n; i += 1)
		bufstr_set(sl_pic_buf, buf_getsize(sl_pic_buf), bufstr_get(ring, i - floor(i / SL_LEAD_CAP) * SL_LEAD_CAP));
	buf_del(ring);
	sl_pic_path = strzone(p);
	sl_pic_ticks = ticks;
	return TRUE;
};

/*
  P1384: the travel on the load key's press, toward org/ang (pitch, yaw, 1 if ducked): the row this
  client predicts the load puts it on. Its picture is the cursor save's (STAT_FS_SLCURID), so a load
  behind a step still unanswered (another row) never comes here. Started on the server's answer, the
  view sat on the save for a round trip and then jumped back up the path (markbeaton54, 8 Nov).
*/
void(vector org, vector ang) SaveLead_Press =
{
	local float id;

	SaveLead_Clear();
	if (serverkeyfloat("fs_savelead") < 2 || !SaveLead_Ready()) return;
	id = getstatf(STAT_FS_SLCURID);
	if (id < 1 || org == '0 0 0') return;
	// The predicted row comes from the cursor string, which can lag the numeric stats a packet.
	if (vlen(org - [getstatf(STAT_FS_SLORG), getstatf(STAT_FS_SLORG + 1), getstatf(STAT_FS_SLORG + 2)]) > 1)
		return;
	if (!SaveLead_Cache(id, getstatf(STAT_FS_SAVETICKS))) return;     // no picture: the plain hold
	if (!SaveLead_Copy(sl_pic_buf, bound(0, cvar("cl_sl_leadin"), 2))) { SaveLead_Clear(); return; }
	if (vlen(sl_lead_tail - org) > 128)
	{
		SaveLead_Clear();
		print("^3save lead-in:^7 saved path does not meet this save; using the held position\n");
		return;
	}
	sl_lead_target = org;
	sl_lead_angles = ang;
	sl_lead_id = id;
	sl_lead_seq = 0;
	sl_lead_early = 1;
	sl_lead_next = 1;
	sl_lead_at = cltime;
	sl_lead_until = cltime + sl_lead_end - sl_lead_from;
	rec_sl_leadhad = TRUE;
};

// P1384: a bound press travel against the server's loaded pose once it lands (a string stat can
// come a packet after SLSEQ). FALSE: the server put the body elsewhere and the travel is gone.
float() SaveLead_Check =
{
	local float i;

	if (tokenize(getstats(STAT_FS_SLLEAD)) != 9 || strcmp(argv(0), "L")) return TRUE;
	for (i = 1; i < 9; i += 1)
		if (!Watch_OwnViewNumber(argv(i), 100000000)) return TRUE;
	if (stof(argv(1)) != sl_lead_seq || stof(argv(2)) != sl_lead_id) return TRUE;
	if (vlen([stof(argv(3)), stof(argv(4)), stof(argv(5))] - sl_lead_target) > 1)
	{
		SaveLead_Clear();
		print("^3save lead-in:^7 the server loaded another place; using the held position\n");
		return FALSE;
	}
	sl_lead_angles = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
	sl_lead_early = 3;
	return TRUE;
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
	// P1384: a press's travel has no seq until the server's load event binds it.
	if (!SaveLead_Ready() || (sl_lead_early != 1 && getstatf(STAT_FS_SLSEQ) != sl_lead_seq))
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
	if (sl_lead_early == 2 && !SaveLead_Check())
		return FALSE;
	if ((sl_lead_early != 1 && !getstatf(STAT_FS_HOLD)) || cltime >= sl_lead_until)
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
	if (sl_lead_early != 1)
		PVS_PublishCmd(p, "rec_savepos");
	return TRUE;
};
