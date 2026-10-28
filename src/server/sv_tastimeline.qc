// Retained inputs only: revisions never contain authority or native handles.
#define TAS_HISTORY_MAX 8
#define TAS_HISTORY_TAPE (TAS_TAPE_MAX * TAS_INPUT_STRIDE)
#define TAS_HISTORY_STRIDE (2 + 2 * TAS_HISTORY_TAPE)
float *tas_history[FS_MAXPLAYERS + 1];
float tas_history_n[FS_MAXPLAYERS + 1], tas_history_cursor[FS_MAXPLAYERS + 1];
float tas_history_req[FS_MAXPLAYERS + 1], tas_history_serial[FS_MAXPLAYERS + 1];
float tas_history_head[FS_MAXPLAYERS + 1];
string tas_history_branch[FS_MAXPLAYERS + 1];
float tas_history_op, tas_replay_armed;
.float run_tas_pagenext, run_tas_historyready;

void(entity e, float first, float last, float field, float value, float ticket, float *source) SV_TASRecalculate;

void(entity e) SV_TASHistoryReset =
{
	local float s;
	s = num_for_edict(e);
	if (s < 1 || s > FS_MAXPLAYERS) return;
	if (tas_history[s]) memfree(tas_history[s]);
	if (tas_history_branch[s]) strunzone(tas_history_branch[s]);
	tas_history[s] = 0;
	tas_history_branch[s] = "";
	tas_history_n[s] = tas_history_cursor[s] = 0;
	tas_history_req[s] = tas_history_serial[s] = tas_history_head[s] = 0;
	e.run_tas_pagenext = e.run_tas_historyready = 0;
};

float(entity e) SV_TASHistoryAttached =
{
	local float s;
	s = num_for_edict(e);
	return (e.run_tas_historyready && tas_history_n[s] > 0 && tas_history_req[s] == e.run_tas_req &&
		tas_history_serial[s] == e.rec_rec_serial && tas_history_head[s] == SV_TimerTicks(e) &&
		!strcmp(tas_history_branch[s], e.rec_rec_branch));
};

// Only after ARM. Failed validation/staging must not consume a revision.
void(entity e, float first, float count, float field, float attached, float *before, float *after) SV_TASHistoryCommit =
{
	local float s, i, b, n;
	local float *h;
	s = num_for_edict(e);
	if (!tas_history_op)
	{
		if (!attached || !field) tas_history_n[s] = tas_history_cursor[s] = 0;
		if (!field) return; // an unchanged explicit replay detaches edit history
		if (!tas_history[s]) tas_history[s] = (float*)memalloc(TAS_HISTORY_MAX * TAS_HISTORY_STRIDE * 4);
		h = tas_history[s];
		if (!h)
		{
			tas_history_n[s] = tas_history_cursor[s] = 0;
			sprint(e, PRINT_HIGH, "tas: edit armed, but history allocation unavailable\n");
			return;
		}
		n = tas_history_cursor[s];
		if (n == TAS_HISTORY_MAX)
		{
			for (i = 0; i < (TAS_HISTORY_MAX - 1) * TAS_HISTORY_STRIDE; i = i + 1)
				h[i] = h[i + TAS_HISTORY_STRIDE];
			n = n - 1;
		}
		b = n * TAS_HISTORY_STRIDE;
		h[b] = first; h[b + 1] = count;
		for (i = 0; i < count * TAS_INPUT_STRIDE; i = i + 1)
		{
			h[b + 2 + i] = before[i];
			h[b + 2 + TAS_HISTORY_TAPE + i] = after[i];
		}
		tas_history_n[s] = tas_history_cursor[s] = n + 1; // a new edit discards redo
	}
	tas_history_req[s] = e.run_tas_req;
	tas_history_serial[s] = e.rec_rec_serial;
	tas_history_head[s] = e.run_tas_replayhead;
	if (tas_history_branch[s]) strunzone(tas_history_branch[s]);
	tas_history_branch[s] = strzone(e.rec_rec_branch);
};

// A GUI transaction names the exact server view it displayed, never just a row.
float(entity e, float arg) SV_TASTimelineBound =
{
	local float serial, head, request;
	if (!FS_TASNumber(argv(arg))) return FALSE;
	serial = fs_tas_number;
	if (!FS_TASNumber(argv(arg + 1))) return FALSE;
	head = fs_tas_number;
	if (!FS_TASNumber(argv(arg + 2))) return FALSE;
	request = fs_tas_number;
	return (serial == e.rec_rec_serial && head == SV_TimerTicks(e) && request == e.run_tas_req);
};

void(entity e, float argc, float redo) SV_TASHistoryCommand =
{
	local float s, b, cursor, first, count;
	local float *source;
	local float *h;
	if (argc != 2 && argc != 5)
	{
		sprint(e, PRINT_HIGH, "tas: undo/redo [serial head request]\n");
		return;
	}
	if (argc == 5)
	if (!SV_TASTimelineBound(e, 2))
	{
		sprint(e, PRINT_HIGH, "tas: stale timeline; refresh before editing\n");
		return;
	}
	s = num_for_edict(e);
	if (!SV_TASHistoryAttached(e) || e.run_tas_replaystate != TAS_TAPE_DONE ||
		e.run_tas_replaynotice != e.run_tas_replayreq)
	{
		sprint(e, PRINT_HIGH, "tas: no completed edit history at this head\n");
		return;
	}
	cursor = tas_history_cursor[s];
	if ((!redo && cursor < 1) || (redo && cursor >= tas_history_n[s]))
	{
		sprint(e, PRINT_HIGH, "tas: no more undo/redo at this head\n");
		return;
	}
	b = (redo ? cursor : cursor - 1) * TAS_HISTORY_STRIDE;
	h = tas_history[s];
	first = h[b]; count = h[b + 1];
	source = h + b + 2 + (redo ? TAS_HISTORY_TAPE : 0);
	tas_history_op = TRUE;
	SV_TASRecalculate(e, first, first + count - 1, 0, 0, e.run_tas_req + 1, source);
	tas_history_op = FALSE;
	if (!tas_replay_armed) return;
	tas_history_cursor[s] = cursor + (redo ? 1 : -1);
	sprint(e, PRINT_HIGH, sprintf("tas: %s armed; revision %.0f of %.0f (completion pending)\n",
		redo ? "redo" : "undo", tas_history_cursor[s], tas_history_n[s]));
};

void(entity e, float argc) SV_TASTimelineSlice =
{
	local float first, last, field, value;
	if (argc != 9)
	{
		sprint(e, PRINT_HIGH, "tas: slice first last field value serial head request\n");
		return;
	}
	if (!SV_TASTimelineBound(e, 6))
	{
		sprint(e, PRINT_HIGH, "tas: stale timeline; refresh before editing\n");
		return;
	}
	if (!FS_TASNumber(argv(2))) goto bad;
	first = fs_tas_number;
	if (!FS_TASNumber(argv(3))) goto bad;
	last = fs_tas_number;
	field = FS_TASEditField(argv(4));
	if (!FS_TASNumber(argv(5))) goto bad;
	value = fs_tas_number;
	if (!(first >= 1 && first < 16000000 && first == floor(first) &&
		last >= first && last < 16000000 && last == floor(last))) goto bad;
	if (!FS_TASEditValue(field, value)) goto bad;
	SV_TASRecalculate(e, first, last, field, value, e.run_tas_req + 1, 0);
	return;
:bad
	sprint(e, PRINT_HIGH, "tas: invalid timeline range/field/value\n");
};

// <=8 rows in one bounded reliable message. No background stream or row handles.
void(entity e, float argc) SV_TASTimelinePage =
{
	local float first, tag, head, n, i, status, s, undo, redo;
	local float *data;
	if (argc != 4) return;
	if (!FS_TASNumber(argv(2))) return;
	first = fs_tas_number;
	if (!(first >= 0 && first <= 16000000 && first == floor(first))) return;
	if (!FS_TASNumber(argv(3))) return;
	tag = fs_tas_number;
	if (!(tag >= 1 && tag <= 16000000 && tag == floor(tag))) return;
	head = SV_TimerTicks(e); status = 0; n = undo = redo = 0;
	if (time < e.run_tas_pagenext) return;
	e.run_tas_pagenext = time + 0.25;
	if (!e.run_tas_paused || e.run_tas_pending || e.run_tas_incap != 1 ||
		e.run_t_state != TS_RUNNING || e.run_tas_replaystate == TAS_TAPE_ACTIVE) status = 1;
	data = (float*)memalloc(TAS_INPUT_STRIDE * 4);
	if (!data) return;
	if (!status)
	{
		SV_RewindTASHead(e);
		if (!first) first = max(1, head - TAS_PAGE_ROWS + 1);
		first = bound(max(1, head - TAS_TAPE_MAX + 1), first, head);
		n = min(TAS_PAGE_ROWS, head - first + 1);
		if (head < 1) n = 0;
	}
	s = num_for_edict(e);
	if (SV_TASHistoryAttached(e))
	if (e.run_tas_replaystate == TAS_TAPE_DONE && e.run_tas_replaynotice == e.run_tas_replayreq)
	{
		undo = tas_history_cursor[s]; redo = tas_history_n[s] - undo;
	}
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, TAS_EV_PAGE);
	WriteLong(MSG_MULTICAST, tag); WriteLong(MSG_MULTICAST, e.rec_rec_serial);
	WriteLong(MSG_MULTICAST, head); WriteLong(MSG_MULTICAST, e.run_tas_req);
	WriteLong(MSG_MULTICAST, first);
	WriteByte(MSG_MULTICAST, status); WriteByte(MSG_MULTICAST, n);
	WriteByte(MSG_MULTICAST, undo); WriteByte(MSG_MULTICAST, redo);
	for (i = 0; i < n; i = i + 1)
	{
		status = SV_TASInputRead(e, first + i, data, 0);
		WriteByte(MSG_MULTICAST, status);
		if (status)
		{
			WriteFloat(MSG_MULTICAST, data[0]);
			WriteFloat(MSG_MULTICAST, data[1]);
			WriteFloat(MSG_MULTICAST, data[2]);
			WriteFloat(MSG_MULTICAST, data[3]);
			WriteFloat(MSG_MULTICAST, data[4]);
			WriteFloat(MSG_MULTICAST, data[6]);
		}
	}
	memfree(data);
	msg_entity = e;
	multicast('0 0 0', SH_MC_ONE);
};
