// P1329: optional authored settings. These are data, never body/step authority.
#define TASI_DATA 10
#define TASI_STRIDE 11
#define TASI_LIVE_STRIDE 15
#define TASI_LIVE_MAX 4096
#define TASI_RANGES 4096         // bounded canonical metadata parser/writer work

float *tasi_rows[FS_MAXPLAYERS + 1];
float *tasi_live[FS_MAXPLAYERS + 1];
.float tasi_cap, tasi_known, tasi_live_n, tasi_live_serial;
.float tasi_pending, tasi_serial, tasi_gen, tasi_request, tasi_count;
.float tasi_done, tasi_head, tasi_ordinal, tasi_mode, tasi_amount, tasi_follow, tasi_bits;
.vector tasi_moves, tasi_angles;
.float tasi_viewserial, tasi_viewhead, tasi_viewrequest, tasi_eventnext;
float tasi_out[TASI_DATA];
float *tpr_intent;
float tpr_intent_known, tpr_intent_last, tpr_intent_ranges;

void(entity e) SV_TASIReset =
{
	local float s;
	s = SV_TASPSlot(e);
	if (!s) return;
	if (tasi_rows[s]) memfree(tasi_rows[s]);
	tasi_rows[s] = __NULL__;
	e.tasi_cap = e.tasi_known = 0;
};

float(entity e, float count) SV_TASIEnsure =
{
	local float s, cap, i;
	local float *data;

	s = SV_TASPSlot(e);
	if (!s || count < 1 || count > TASP_MAX) return FALSE;
	if (tasi_rows[s] && e.tasi_cap >= count) return TRUE;
	cap = min(TASP_MAX, max(4096, e.tasi_cap));
	while (cap < count) cap = min(TASP_MAX, cap * 2);
	data = (float*)memalloc(cap * TASI_STRIDE * 4);
	if (!data) return FALSE;
	for (i = 0; i < cap; i = i + 1) data[i*TASI_STRIDE] = 0;
	if (tasi_rows[s])
	{
		for (i = 0; i < e.tasi_cap*TASI_STRIDE; i = i + 1) data[i] = tasi_rows[s][i];
		memfree(tasi_rows[s]);
	}
	tasi_rows[s] = data; e.tasi_cap = cap;
	return TRUE;
};

// Read the actual recorder ordinal, never infer it from a logical tick.
// Initial physical play may lack raw warm input: recorder PreThink precedes
// the mover's one-tick increment. Settled authored grants require exact raw input.
float(entity e, float requireNative) SV_TASIOrdinal =
{
	local float i, j, last, ordinal, ok, argc;
	local float *data;
	local string line;

	if (e.rec_rec_buf <= 0 || e.rec_rec_lines <= 0) return 0;
	data = (float*)memalloc(TAS_INPUT_STRIDE * 4);
	if (!data) return 0;
	ok = SV_TASInputRead(e, SV_TimerTicks(e), data, 0);
	ordinal = 0;
	if (ok || !requireNative)
	{
		last = min(e.rec_rec_lines, buf_getsize(e.rec_rec_buf));
		for (i = last - 1; i >= max(0, last - 512); i = i - 1)
		{
			line = bufstr_get(e.rec_rec_buf, i);
			if (substring(line, 0, 3) != "in ") continue;
			argc = tokenize_console(line);
			if (argc != 12) break;
			if (!SV_TASPNum(argv(2), 1, 16777215, TRUE)) break;
			ordinal = fs_tas_number;
			if (!ok)
			{
				if (ordinal + 1 != e.run_movetick) ordinal = 0;
				break;
			}
			for (j = 0; j < 7; j = j + 1)
			{
				if (!FS_TASNumber(argv(j+4))) { ordinal = 0; break; }
				if (j >= 3 && j <= 5) fs_tas_number = FS_TASAngleWord(fs_tas_number);
				if (fs_tas_number != data[j]) { ordinal = 0; break; }
			}
			break;
		}
	}
	memfree(data);
	return ordinal;
};

// Queue callers have already copied their numeric command arguments. This may
// tokenize recorder text; it is deliberately not an early command interceptor.
void(entity e, float count, float ticket) SV_TASIArm =
{
	local float ordinal;

	e.tasi_pending = FALSE;
	if (Lobby_Active() || e.taslg_on || e.tasp_legal || !e.run_tas_paused || e.run_tas_pending) return;
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE) return;
	if (e.run_tas_planmode < TAS_PLAN_MANUAL || e.run_tas_planmode > TAS_PLAN_HOLD) return;
	ordinal = SV_TASIOrdinal(e,FALSE);
	if (!ordinal) return;
	e.tasi_serial = e.rec_rec_serial; e.tasi_gen = e.rec_rec_gen;
	e.tasi_request = ticket; e.tasi_count = count;
	e.tasi_done = e.run_tas_done; e.tasi_head = SV_TimerTicks(e); e.tasi_ordinal = ordinal;
	e.tasi_mode = e.run_tas_planmode; e.tasi_amount = e.run_tas_planamount;
	e.tasi_follow = e.run_tas_pitchfollow; e.tasi_bits = e.run_tas_planbits;
	e.tasi_moves = [e.run_tas_planforward, e.run_tas_planside, 0];
	e.tasi_angles = [FS_TASAngleWord(e.run_tas_planpitch), FS_TASAngleWord(e.run_tas_planyaw), 0];
	e.tasi_pending = TRUE;
};

void(entity e, float tick, float ordinal) SV_TASIHarvest;

void(entity e) SV_TASIBackfill =
{
	local float tick;

	if (!e.tasp_on || e.tasp_load || e.tasp_serial != e.rec_rec_serial) return;
	for (tick = e.tasi_head+1; tick <= min(SV_TimerTicks(e),e.tasp_synced); tick = tick+1)
		SV_TASIHarvest(e,tick,e.tasi_ordinal+tick-e.tasi_head);
};

// An entire settled grant must have executed the unchanged native recipe.
// Clearing a native plan cannot be undone while its queue is pending; the last
// matching native snapshot therefore witnesses continuity, not merely a request.
void(entity e) SV_TASIFlush =
{
	local float s, ordinal, i, b, previous, same;
	local vector meta;
	local float *data;

	if (!e.tasi_pending || e.run_tas_pending || e.run_tas_seen != e.run_tas_done) return;
	e.tasi_pending = FALSE;
	if (!e.run_tas_paused || e.run_tas_fault || e.run_t_state != TS_RUNNING) return;
	if (e.rec_rec_serial != e.tasi_serial || e.rec_rec_gen != e.tasi_gen || e.run_tas_req != e.tasi_request) return;
	if (e.run_tas_done - e.tasi_done != e.tasi_count || SV_TimerTicks(e) - e.tasi_head != e.tasi_count) return;
	ordinal = SV_TASIOrdinal(e,TRUE);
	if (ordinal - e.tasi_ordinal != e.tasi_count) return;
	meta = tas_input(e, rw_native_slot, rw_native_token, 4);
	if (meta_x != e.tasi_mode || meta_y != e.tasi_amount || meta_z != e.tasi_follow) return;
	s = SV_TASPSlot(e);
	if (!s) return;
	if (!tasi_live[s]) tasi_live[s] = (float*)memalloc(TASI_LIVE_MAX * TASI_LIVE_STRIDE * 4);
	if (!tasi_live[s]) return;
	if (e.tasi_live_serial != e.rec_rec_serial)
	{
		e.tasi_live_n = 0; e.tasi_live_serial = e.rec_rec_serial;
	}
	tasi_out[0] = e.tasi_mode; tasi_out[1] = e.tasi_amount; tasi_out[2] = e.tasi_follow;
	tasi_out[3] = e.tasi_moves_x; tasi_out[4] = e.tasi_moves_y; tasi_out[5] = e.tasi_moves_z;
	tasi_out[6] = e.tasi_angles_x; tasi_out[7] = e.tasi_angles_y; tasi_out[8] = e.tasi_angles_z;
	tasi_out[9] = e.tasi_bits;
	data = tasi_live[s]; b = e.tasi_live_n * TASI_LIVE_STRIDE;
	if (e.tasi_live_n > 0)
	{
		previous = b - TASI_LIVE_STRIDE;
		same = (data[previous+2] == e.tasi_ordinal && data[previous+4] == e.tasi_head);
		for (i = 0; i < TASI_DATA; i = i + 1)
			if (data[previous+5+i] != tasi_out[i]) same = FALSE;
		if (same)
		{
			data[previous+2] = ordinal; data[previous+4] = SV_TimerTicks(e);
			SV_TASIBackfill(e);
			return;
		}
	}
	if (e.tasi_live_n >= TASI_LIVE_MAX)
	{
		sprint(e, PRINT_HIGH, "tas intent: recipe history full; new rows remain literal/unknown\n");
		return;
	}
	data[b] = e.rec_rec_serial;
	data[b+1] = e.tasi_ordinal + 1; data[b+2] = ordinal;
	data[b+3] = e.tasi_head + 1; data[b+4] = SV_TimerTicks(e);
	for (i = 0; i < TASI_DATA; i = i + 1) data[b+5+i] = tasi_out[i];
	e.tasi_live_n = e.tasi_live_n + 1;
	SV_TASIBackfill(e);
};

// Called only for a real newly harvested recorder row. Rewritten literals lose
// old intent unless this exact native source ordinal belongs to a proven grant.
void(entity e, float tick, float ordinal) SV_TASIHarvest =
{
	local float s, i, j, b, target, known;

	s = SV_TASPSlot(e);
	if (!s || e.taslg_on || e.tasp_legal || tick <= e.tasp_base || tick > e.tasp_base + TASP_MAX) return;
	target = (tick - e.tasp_base - 1) * TASI_STRIDE;
	b = 0; known = FALSE;
	if (e.tasi_live_serial == e.rec_rec_serial && tasi_live[s])
	for (i = e.tasi_live_n - 1; i >= 0; i = i - 1)
	{
		b = i * TASI_LIVE_STRIDE;
		if (ordinal > tasi_live[s][b+2]) break;
		if (ordinal < tasi_live[s][b+1]) continue;
		if (tasi_live[s][b] != e.rec_rec_serial) break;
		if (tick - tasi_live[s][b+3] != ordinal - tasi_live[s][b+1]) break;
		known = TRUE; break;
	}
	if (!known)
	{
		if (tick - e.tasp_base <= e.tasi_cap)
		if (tasi_rows[s])
		if (tasi_rows[s][target] > 0)
		{
			tasi_rows[s][target] = 0; e.tasi_known = e.tasi_known - 1;
		}
		return;
	}
	if (!SV_TASIEnsure(e, tick - e.tasp_base)) return;
	if (!tasi_rows[s][target]) e.tasi_known = e.tasi_known + 1;
	for (j = 0; j < TASI_DATA; j = j + 1) tasi_rows[s][target+j] = tasi_live[s][b+5+j];
	tasi_rows[s][target+TASI_DATA] = 2; // locally observed recipe, still no authority
};

// The existing local-project packet carries this optional presentation tail.
// No native controls are configured and no grant is issued when it is read.
void(entity e) SV_TASIWire =
{
	local float s, tick, b, i, known;

	s = SV_TASPSlot(e); tick = SV_TimerTicks(e);
	b = 0; known = FALSE;
	if (s && e.tasp_on && !e.tasp_load && e.tasp_serial == e.rec_rec_serial)
	if (!e.tasp_legal && tick > e.tasp_base && tick <= e.tasp_synced && tick - e.tasp_base <= e.tasi_cap)
	if (tasi_rows[s])
	{
		b = (tick - e.tasp_base - 1) * TASI_STRIDE;
		if (tasi_rows[s][b] > 0) known = tasi_rows[s][b+TASI_DATA];
	}
	if (e.tasi_viewserial != e.rec_rec_serial || e.tasi_viewhead != tick || e.tasi_viewrequest != e.run_tas_req)
	{
		e.tasi_viewserial = e.rec_rec_serial; e.tasi_viewhead = tick; e.tasi_viewrequest = e.run_tas_req;
		if (known) e.run_tas_pitchfollow = tasi_rows[s][b+2];
	}
	WriteLong(MSG_MULTICAST, e.rec_rec_serial); WriteLong(MSG_MULTICAST, tick);
	WriteLong(MSG_MULTICAST, e.run_tas_req); WriteByte(MSG_MULTICAST, known);
	if (known)
	for (i = 0; i < TASI_DATA; i = i + 1) WriteFloat(MSG_MULTICAST, tasi_rows[s][b+i]);
};

float(float version) SV_TASVersionLegal = { return (version == TASP_LEGAL); };
float(float version) SV_TASVersionIntent = { return (version == 4); };

void() SV_TASIReadFree =
{
	if (tpr_intent) memfree(tpr_intent);
	tpr_intent = __NULL__; tpr_intent_known = tpr_intent_last = tpr_intent_ranges = 0;
};

// v4 local full-line ranges are part of the revision, not a mutable sidecar.
// A valid saved recipe is declared data, NOT proof of how its inputs arose.
float(float base, float count, float argc) SV_TASIReadRange =
{
	local float first, last, i, j, b, lo, hi, integral;

	if (argc != 13 || count < 1 || tpr_intent_ranges >= TASI_RANGES) return FALSE;
	if (!SV_TASPNum(argv(1), base+1, base+count, TRUE)) return FALSE;
	first = fs_tas_number;
	if (!SV_TASPNum(argv(2), first, base+count, TRUE)) return FALSE;
	last = fs_tas_number;
	if (first <= tpr_intent_last) return FALSE;
	for (i = 0; i < TASI_DATA; i = i + 1)
	{
		lo = -32768; hi = 32767; integral = TRUE;
		if (i == 0) { lo = TAS_PLAN_MANUAL; hi = TAS_PLAN_HOLD; }
		else if (i == 1) { lo = 0; hi = 4; integral = FALSE; }
		else if (i == 2) { lo = 0; hi = 1; }
		else if (i == 3 || i == 4) { lo = -450; hi = 450; }
		else if (i == 5 || i == 8) { lo = 0; hi = 0; }
		else if (i == 6) { lo = -16202; hi = 16202; }
		else if (i == 9) { lo = 0; hi = 7; }
		if (integral)
		{
			if (!SV_TASPNum(argv(i+3), lo, hi, TRUE)) return FALSE;
		}
		else if (!SV_TASPFloat(argv(i+3),lo,hi)) return FALSE;
		tasi_out[i] = fs_tas_number;
	}
	if (!tpr_intent)
	{
		tpr_intent = (float*)memalloc(count * TASI_STRIDE * 4);
		if (!tpr_intent) return FALSE;
		for (i = 0; i < count; i = i + 1) tpr_intent[i*TASI_STRIDE] = 0;
	}
	for (i = first; i <= last; i = i + 1)
	{
		b = (i-base-1) * TASI_STRIDE;
		for (j = 0; j < TASI_DATA; j = j + 1) tpr_intent[b+j] = tasi_out[j];
		tpr_intent[b+TASI_DATA] = 1; // project-supplied, not native-observation evidence
	}
	tpr_intent_known = tpr_intent_known + last-first+1; tpr_intent_last = last;
	tpr_intent_ranges = tpr_intent_ranges + 1;
	return TRUE;
};

void(entity e, float first, float last) SV_TASIInvalidate =
{
	local float s, i, b;

	s = SV_TASPSlot(e);
	if (!s || !tasi_rows[s]) return;
	for (i = max(first, e.tasp_base+1); i <= min(last, e.tasp_base+e.tasi_cap); i = i + 1)
	{
		b = (i-e.tasp_base-1) * TASI_STRIDE;
		if (tasi_rows[s][b] > 0)
		{
			tasi_rows[s][b] = 0; e.tasi_known = e.tasi_known - 1;
		}
	}
};

void(entity e) SV_TASIAdopt =
{
	local float s;

	s = SV_TASPSlot(e);
	SV_TASIReset(e);
	if (!s) return;
	tasi_rows[s] = tpr_intent; tpr_intent = __NULL__;
	e.tasi_cap = e.tasp_n; e.tasi_known = tpr_intent_known;
	tpr_intent_known = tpr_intent_last = 0;
};

float(filestream file, entity e, float s) SV_TASIEmit =
{
	local float i, last, b, next, j, same, ranges;
	local string line;

	if (!tasi_rows[s] || e.tasp_legal) return TRUE;
	ranges = 0;
	for (i = 0; i < min(e.tasp_n,e.tasi_cap); i = i + 1)
	{
		b = i * TASI_STRIDE;
		if (!tasi_rows[s][b]) continue;
		ranges = ranges + 1;
		if (ranges > TASI_RANGES) return FALSE;
		last = i;
		while (last+1 < min(e.tasp_n,e.tasi_cap))
		{
			next = (last+1) * TASI_STRIDE; same = TRUE;
			for (j = 0; j < TASI_DATA; j = j + 1)
				if (tasi_rows[s][b+j] != tasi_rows[s][next+j]) same = FALSE;
			if (!same) break;
			last = last + 1;
		}
		line = sprintf("intent %.0f %.0f %.0f %.9g %.0f %g %g",
			e.tasp_base+i+1,e.tasp_base+last+1,tasi_rows[s][b],tasi_rows[s][b+1],
			tasi_rows[s][b+2],tasi_rows[s][b+3],tasi_rows[s][b+4]);
		fputs(file,strcat(line,sprintf(" %g %.0f %.0f %.0f %.0f\n",tasi_rows[s][b+5],
			tasi_rows[s][b+6],tasi_rows[s][b+7],tasi_rows[s][b+8],tasi_rows[s][b+9])));
		i = last;
	}
	return TRUE;
};
