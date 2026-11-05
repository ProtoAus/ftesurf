// Full captured input lines; execution remains the project's <=128-row chunks.
// A preview is not a saved revision, signature, or an original-packet timing claim.
.float tase_preview, tase_serial, tase_next, tase_originaltime;
.float tase_history, tase_count, tase_cursor;
.string tase_original, tase_name, tase_histname;

void(entity e) SV_TASEditorReset =
{
	if (e.tase_original) strunzone(e.tase_original);
	if (e.tase_name) strunzone(e.tase_name);
	if (e.tase_histname) strunzone(e.tase_histname);
	if (e.tase_history > 0) buf_del(e.tase_history);
	e.tase_original = e.tase_name = e.tase_histname = "";
	e.tase_preview = e.tase_serial = e.tase_next = e.tase_originaltime = 0;
	e.tase_history = e.tase_count = e.tase_cursor = 0;
};

void(entity e) SV_TASEditorClearPreview =
{
	if (e.tase_original) strunzone(e.tase_original);
	if (e.tase_name) strunzone(e.tase_name);
	e.tase_original = e.tase_name = "";
	e.tase_preview = e.tase_originaltime = 0;
};

void(entity e) SV_TASEditorFrame =
{
	if (e.tase_serial)
	if (e.tase_serial != e.rec_rec_serial) { SV_TASEditorReset(e); return; }
};

// Explicit pause owns this disk checkpoint. Ordinary play itself writes no TAS project.
void(entity e) SV_TASEditorCapture =
{
	if (Lobby_Active() || e.rec_rec_stream || !e.rw_playtoken || e.tasp_on) return;
	if (e.run_t_state != TS_RUNNING || !(e.run_t_flags & TF_RECORDING)) return;
	if (!e.run_tas_mode || !e.run_tas_paused || e.tasp_load) return;
	SV_TASProjectSave(e, "", FALSE);
};

float(entity e) SV_TASEditorRows =
{
	local float s, head;
	s = SV_TASPSlot(e);
	if (!s || !e.tasp_on || e.tasp_legal || e.tasp_serial != e.rec_rec_serial) return FALSE;
	if (e.rec_rec_stream || e.tasp_load) return FALSE;
	head = SV_TimerTicks(e);
	if (head > e.tasp_synced)
	{
		if (!SV_TASPHarvest(e, s, head)) return FALSE;
		e.tasp_n = max(e.tasp_n, head - e.tasp_base);
	}
	return (e.tasp_n > 0 && e.tasp_n <= TASP_MAX && tasp_buf[s] != 0);
};

float(entity e) SV_TASEditorSameInputs =
{
	local float s, i;
	s = SV_TASPSlot(e);
	if (!s || !tasp_pbuf[s] || e.tasp_pbase != e.tasp_base || e.tasp_pn != e.tasp_n) return FALSE;
	for (i = 0; i < e.tasp_n * TAS_INPUT_STRIDE; i = i + 1)
		if (tasp_buf[s][i] != tasp_pbuf[s][i]) return FALSE;
	return TRUE;
};

float(entity e, float serial, float head, float request) SV_TASEditorBound =
{
	if (serial != e.rec_rec_serial || head != SV_TimerTicks(e) || request != e.run_tas_req)
	{
		sprint(e, PRINT_HIGH, "tas editor: stale body/line page; refresh before changing anything\n");
		return FALSE;
	}
	if (e.tasp_load || !SV_TASInputReady(e)) return FALSE;
	return TRUE;
};

float(string sha) SV_TASEditorHashOK =
{
	local float i, c;
	if (strlen(sha) != 64) return FALSE;
	for (i = 0; i < 64; i = i + 1)
	{
		c = str2chr(sha, i);
		if (!(c >= 48 && c <= 57) && !(c >= 97 && c <= 102)) return FALSE;
	}
	return TRUE;
};

// Never a client path: only canonical64-hex revision identities from our own reader/writer.
float(entity e, string sha, string stop, float first, float last, float field, float value) SV_TASEditorLoad =
{
	local float s, before;
	local string name, path;
	s = SV_TASPSlot(e);
	if (!s || !SV_TASEditorHashOK(sha) || tasp_name[s] == "") return FALSE;
	name = strzone(tasp_name[s]);
	path = strzone(SV_TASPRevPath(sha, "tasp"));
	before = e.run_tas_req;
	tpr_pathover = path;
	SV_TASProjectLoadChecked(e, name, stop, sha, first, last, field, value);
	tpr_pathover = "";
	strunzone(path); strunzone(name);
	return (e.run_tas_req > before && e.tasp_on && (e.tasp_load || e.tasp_result == 1 || e.tasp_result == 2));
};

float(entity e) SV_TASEditorFreeze =
{
	local float s, head;
	if (e.tase_preview) { sprint(e, PRINT_HIGH, "tas editor: Keep or Discard this preview first\n"); return FALSE; }
	head = SV_TimerTicks(e);
	if (e.tasp_on && head < e.tasp_base + e.tasp_n)
	{
		sprint(e, PRINT_HIGH, "tas editor: replay the captured line to its head before creating a new preview\n");
		return FALSE;
	}
	SV_TASProjectSave(e, "", FALSE);
	s = SV_TASPSlot(e);
	if (!s || !e.tasp_on || e.tasp_legal || e.tasp_serial != e.rec_rec_serial ||
		e.tasp_filehead != head || e.tasp_synced != head || e.tasp_native_token <= 0) return FALSE;
	if (!e.tasp_saveok || !SV_TASEditorHashOK(tasp_revsha[s])) return FALSE;
	return SV_TASPKeep(SV_TASPPath(tasp_name[s]), tasp_revsha[s], FALSE, FALSE);
};

void(entity e, float first, float last, float field, float value) SV_TASEditorPreview =
{
	local float s, elapsed;
	local string sha, name;
	if (!SV_TASEditorRows(e)) return;
	if (first < e.tasp_base + 1 || last < first || last > e.tasp_base + e.tasp_n)
	{
		sprint(e, PRINT_HIGH, "tas editor: range outside the captured line; original retained\n"); return;
	}
	if (!SV_TASEditorFreeze(e)) return;
	s = SV_TASPSlot(e);
	sha = strzone(tasp_revsha[s]); name = strzone(tasp_name[s]);
	elapsed = SV_TimerElapsed(e);
	if (SV_TASEditorLoad(e, sha, "", first, last, field, value))
	{
		SV_TASEditorClearPreview(e);
		e.tase_original = sha; e.tase_name = name;
		e.tase_preview = 1; e.tase_serial = e.rec_rec_serial;
		e.tase_originaltime = elapsed;
		sprint(e, PRINT_HIGH, "tas editor: PREVIEW only; original revision retained. Keep or Discard after replay\n");
	}
	else { strunzone(sha); strunzone(name); }
};

void(entity e) SV_TASEditorKeep =
{
	local float s, i;
	local string before, after;
	if (!e.tase_preview || !SV_TASEditorRows(e)) return;
	if (SV_TimerTicks(e) != e.tasp_base + e.tasp_n || e.tasp_load)
	{
		sprint(e, PRINT_HIGH, "tas editor: preview did not finish; original retained, Discard remains available\n"); return;
	}
	s = SV_TASPSlot(e);
	if (strcmp(tasp_name[s], e.tase_name)) return;
	before = strzone(e.tase_original);
	SV_TASProjectSave(e, "", FALSE);
	if (!e.tasp_saveok || !e.tasp_on || !strcmp(tasp_revsha[s], before)) { strunzone(before); return; }
	after = strzone(tasp_revsha[s]);
	if (strcmp(e.tase_histname, tasp_name[s]))
	{
		if (e.tase_history > 0) buf_del(e.tase_history);
		e.tase_history = e.tase_count = e.tase_cursor = 0;
		if (e.tase_histname) strunzone(e.tase_histname);
		e.tase_histname = strzone(tasp_name[s]);
	}
	if (e.tase_history <= 0) e.tase_history = buf_create_ex("string", 0);
	if (e.tase_history > 0)
	{
		if (e.tase_cursor == 8)
		{
			for (i = 0; i < 14; i = i + 1)
				bufstr_set(e.tase_history, i, bufstr_get(e.tase_history, i+2));
			e.tase_cursor = 7;
		}
		bufstr_set(e.tase_history, e.tase_cursor * 2, before);
		bufstr_set(e.tase_history, e.tase_cursor * 2 + 1, after);
		e.tase_cursor = e.tase_cursor + 1; e.tase_count = e.tase_cursor;
	}
	strunzone(before); strunzone(after);
	SV_TASEditorClearPreview(e);
	sprint(e, PRINT_HIGH, "tas editor: KEPT as a child revision; original remains immutable under its hash\n");
};

void(entity e) SV_TASEditorDiscard =
{
	local string sha;
	if (!e.tase_preview) return;
	sha = strzone(e.tase_original);
	if (SV_TASEditorLoad(e, sha, "", 0, 0, 0, 0))
	{
		SV_TASEditorClearPreview(e);
		sprint(e, PRINT_HIGH, "tas editor: DISCARDED; replaying the unchanged original revision\n");
	}
	strunzone(sha);
};

void(entity e, float redo) SV_TASEditorHistory =
{
	local float s, i;
	local string sha, expected;
	if (e.tase_preview) { sprint(e, PRINT_HIGH, "tas editor: Keep or Discard first\n"); return; }
	if (e.tase_history <= 0 || (!redo && e.tase_cursor < 1) || (redo && e.tase_cursor >= e.tase_count)) return;
	s = SV_TASPSlot(e);
	if (!s || strcmp(tasp_name[s], e.tase_histname)) return;
	i = (redo ? e.tase_cursor : e.tase_cursor - 1) * 2;
	expected = bufstr_get(e.tase_history, i + (redo ? 0 : 1));
	if (strcmp(expected, tasp_revsha[s])) { sprint(e, PRINT_HIGH, "tas editor: history detached; nothing moved\n"); return; }
	sha = strzone(bufstr_get(e.tase_history, i + (redo ? 1 : 0)));
	if (SV_TASEditorLoad(e, sha, "", 0, 0, 0, 0))
	{
		e.tase_cursor = e.tase_cursor + (redo ? 1 : -1);
		sprint(e, PRINT_HIGH, redo ? "tas editor: REDO replaying retained revision\n" : "tas editor: UNDO replaying retained revision\n");
	}
	strunzone(sha);
};

void(entity e, float first, float tag) SV_TASEditorPage =
{
	local float s, body, base, head, count, status, flags, i, b, ok;
	local float originaltime, candidatetime;
	local float *data;
	s = SV_TASPSlot(e);
	if (!s || Lobby_Active() || time < e.run_tas_pagenext) return;
	e.run_tas_pagenext = time + 0.15;
	body = SV_TimerTicks(e); base = max(0, body - TAS_TAPE_MAX); head = body;
	status = flags = originaltime = candidatetime = 0;
	ok = SV_TASEditorRows(e);
	if (ok) { base = e.tasp_base; head = base + e.tasp_n; flags = 1; }
	if (!SV_TASInputReady(e) || head <= base) status = 1;
	if (e.tasp_native_token > 0)
	if (checkbuiltin(tas_rewind))
	if (tas_rewind(e, e.tasp_native_slot, e.tasp_native_token, 1) == 1) flags = flags | 2;
	if (e.tase_preview)
	{
		flags = flags | 4;
		if (!e.tasp_load && body == head)
		{
			flags = flags | 8;
			originaltime = e.tase_originaltime; candidatetime = SV_TimerElapsed(e);
		}
	}
	if (!first) first = max(base + 1, head - TAS_PAGE_ROWS + 1);
	first = bound(base + 1, first, max(base + 1, head));
	count = max(0, min(TAS_PAGE_ROWS, head - first + 1));
	if (status) count = 0;
	data = (float*)memalloc(TAS_INPUT_STRIDE * 4);
	if (!data) return;
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET); WriteByte(MSG_MULTICAST, TAS_EV_PAGE2);
	WriteLong(MSG_MULTICAST, tag); WriteLong(MSG_MULTICAST, e.rec_rec_serial);
	WriteLong(MSG_MULTICAST, body); WriteLong(MSG_MULTICAST, e.run_tas_req); WriteLong(MSG_MULTICAST, first);
	WriteLong(MSG_MULTICAST, base); WriteLong(MSG_MULTICAST, head);
	WriteByte(MSG_MULTICAST, status); WriteByte(MSG_MULTICAST, count);
	WriteByte(MSG_MULTICAST, e.tase_cursor); WriteByte(MSG_MULTICAST, e.tase_count - e.tase_cursor);
	WriteByte(MSG_MULTICAST, flags); WriteFloat(MSG_MULTICAST, originaltime); WriteFloat(MSG_MULTICAST, candidatetime);
	for (i = 0; i < count; i = i + 1)
	{
		if (ok)
		{
			b = (first + i - base - 1) * TAS_INPUT_STRIDE;
			WriteByte(MSG_MULTICAST, 1);
			WriteFloat(MSG_MULTICAST, tasp_buf[s][b]); WriteFloat(MSG_MULTICAST, tasp_buf[s][b+1]);
			WriteFloat(MSG_MULTICAST, tasp_buf[s][b+2]); WriteFloat(MSG_MULTICAST, tasp_buf[s][b+3]);
			WriteFloat(MSG_MULTICAST, tasp_buf[s][b+4]); WriteFloat(MSG_MULTICAST, tasp_buf[s][b+6]);
		}
		else
		{
			ok = SV_TASInputRead(e, first + i, data, 0);
			WriteByte(MSG_MULTICAST, ok);
			if (ok)
			{
				WriteFloat(MSG_MULTICAST, data[0]); WriteFloat(MSG_MULTICAST, data[1]);
				WriteFloat(MSG_MULTICAST, data[2]); WriteFloat(MSG_MULTICAST, data[3]);
				WriteFloat(MSG_MULTICAST, data[4]); WriteFloat(MSG_MULTICAST, data[6]);
			}
			ok = FALSE;
		}
	}
	msg_entity = e; multicast('0 0 0', MULTICAST_ONE_R);
	memfree(data);
};

// Fully parse numeric words before any project helper tokenizes files.
void(entity e, float argc) SV_TASEditorCommand =
{
	local string action, stop;
	local float first, last, field, value, serial, head, request, i;
	first = last = field = value = 0;
	action = strzone(argv(1));
	if (!strcmp(action, "page2"))
	{
		if (argc != 4 || !FS_TASNumber(argv(2))) goto bad;
		first = fs_tas_number;
		if (!FS_TASNumber(argv(3))) goto bad;
		value = fs_tas_number;
		if (first < 0 || first >= 16000000 || first != floor(first) || value < 1 || value > 16000000 || value != floor(value)) goto bad;
		SV_TASEditorPage(e, first, value); strunzone(action); return;
	}
	if (!strcmp(action, "preview2"))
	{
		if (argc != 9 || !FS_TASNumber(argv(2))) goto bad;
		first = fs_tas_number;
		if (!FS_TASNumber(argv(3))) goto bad;
		last = fs_tas_number; field = FS_TASEditField(argv(4));
		if (!FS_TASNumber(argv(5))) goto bad;
		value = fs_tas_number;
		if (!FS_TASEditValue(field, value) || first < 1 || first != floor(first) || last < first || last != floor(last)) goto bad;
	}
	else if (!strcmp(action, "seek2"))
	{
		if (argc != 6 || !FS_TASNumber(argv(2))) goto bad;
		first = fs_tas_number;
		if (first < 0 || first >= 16000000 || first != floor(first)) goto bad;
	}
	else if (argc != 5) goto bad;
	if (!FS_TASNumber(argv(argc-3))) goto bad;
	serial = fs_tas_number;
	if (!FS_TASNumber(argv(argc-2))) goto bad;
	head = fs_tas_number;
	if (!FS_TASNumber(argv(argc-1))) goto bad;
	request = fs_tas_number;
	if (!SV_TASEditorBound(e, serial, head, request)) { strunzone(action); return; }
	if (time < e.tase_next) { sprint(e, PRINT_HIGH, "tas editor: wait for the previous action\n"); strunzone(action); return; }
	e.tase_next = time + 0.35;
	if (!strcmp(action, "preview2")) SV_TASEditorPreview(e, first, last, field, value);
	else if (!strcmp(action, "keep2")) SV_TASEditorKeep(e);
	else if (!strcmp(action, "discard2")) SV_TASEditorDiscard(e);
	else if (!strcmp(action, "undo2")) SV_TASEditorHistory(e, FALSE);
	else if (!strcmp(action, "redo2")) SV_TASEditorHistory(e, TRUE);
	else if (!strcmp(action, "seek2"))
	{
		i = SV_TASPSlot(e);
		if (i && !e.tase_preview && SV_TASEditorRows(e) && first >= e.tasp_base && first <= e.tasp_base + e.tasp_n)
		{
			if (!SV_TASEditorSameInputs(e))
			{
				if (!SV_TASEditorFreeze(e)) { strunzone(action); return; }
			}
			stop = strzone(sprintf("@%.0f", first));
			SV_TASEditorLoad(e, tasp_revsha[i], stop, 0, 0, 0, 0);
			strunzone(stop);
		}
	}
	else goto bad;
	strunzone(action); return;
:bad
	strunzone(action);
	sprint(e, PRINT_HIGH, "tas editor: invalid typed action; nothing moved\n");
};
