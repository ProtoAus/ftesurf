// The table is a view, not a source of authority. Server binds every GUI edit.
float tast_tag, tast_serial, tast_head, tast_request, tast_first, tast_n, tast_status;
float tast_undo, tast_redo, tast_selected, tast_from, tast_to, tast_field, tast_value;
float tast_next;
float tast_rows[TAS_PAGE_ROWS * 7]; // present, forward, side, up, pitch word, yaw word, buttons

void() TASTimeline_Reset =
{
	tast_tag = tast_tag + 1; // invalidate an in-flight page, including close/map change
	tast_n = tast_undo = tast_redo = 0;
};

float() TASTimeline_Current =
{
	return (tast_n > 0 && !tast_status && getstatf(STAT_FS_TASREQUEST) == tast_request &&
		getstatf(STAT_FS_TASPAUSE) == 1 && getstatf(STAT_FS_TASPENDING) == 0 &&
		LT_StatsAreMine() && numclientseats <= 1);
};

void(float first) TASTimeline_Request =
{
	if (cltime < tast_next) return;
	tast_next = cltime + 0.3;
	if (!LT_StatsAreMine() || numclientseats > 1 || cvar("cl_threadedphysics") ||
		getstatf(STAT_FS_TASINPUT) != 1)
	{
		print("tas timeline: needs own body, one seat, supported input and cl_threadedphysics 0\n");
		return;
	}
	tast_tag = tast_tag + 1;
	if (tast_tag > 16000000) tast_tag = 1;
	tast_n = tast_undo = tast_redo = 0;
	localcmd(sprintf("p1 cmd tas page %.0f %.0f\n", first, tast_tag));
};

void() TASTimeline_ImportValue;

void() TASTimeline_Event =
{
	local float tag, serial, head, request, first, status, n, undo, redo, i, j, present, v, good, take;
	tag = readlong(); serial = readlong(); head = readlong(); request = readlong(); first = readlong();
	status = readbyte(); n = readbyte(); undo = readbyte(); redo = readbyte();
	take = (tag == tast_tag && tasu_open && LT_StatsAreMine() && numclientseats <= 1);
	good = (n <= TAS_PAGE_ROWS && status == 0 && first >= 1 && head >= first &&
		head < 16000000 && first + n - 1 <= head && undo <= 8 && redo <= 8);
	// Always consume the whole message, including a stale or refused answer.
	for (i = 0; i < n; i = i + 1)
	{
		present = readbyte();
		if (present != 0 && present != 1) good = FALSE;
		if (take && i < TAS_PAGE_ROWS) tast_rows[i*7] = present;
		if (present)
		for (j = 1; j <= 6; j = j + 1)
		{
			v = readfloat();
			if (!(v >= -32768 && v <= 32767 && v == floor(v))) good = FALSE;
			if (j == 6)
			if (!(v >= 0 && v <= 7)) good = FALSE;
			if (take && i < TAS_PAGE_ROWS) tast_rows[i*7+j] = v;
		}
	}
	if (!take) return;
	tast_serial = serial; tast_head = head; tast_request = request; tast_first = first;
	tast_n = good ? n : 0; tast_status = status;
	tast_undo = good ? undo : 0; tast_redo = good ? redo : 0;
	tast_selected = first + max(0, tast_n - 1);
	tast_from = tast_to = tast_selected;
	if (!tast_field) tast_field = 2;
	if (good && n > 0) TASTimeline_ImportValue();
	print(sprintf("tas timeline: page %.0f rows %.0f head %.0f serial %.0f request %.0f undo %.0f redo %.0f\n",
		tast_first, tast_n, tast_head, tast_serial, tast_request, tast_undo, tast_redo));
};

float(float tick) TASTimeline_Select =
{
	local float i;
	i = tick - tast_first;
	if (!(i >= 0 && i < tast_n && i == floor(i))) return FALSE;
	if (!tast_rows[i*7]) return FALSE;
	tast_selected = tick;
	return TRUE;
};

void() TASTimeline_ImportValue =
{
	local float b, bit;
	b = (tast_selected - tast_first) * 7;
	if (!(b >= 0 && b < tast_n * 7)) return;
	if (!tast_rows[b]) return;
	if (tast_field <= 3) tast_value = tast_rows[b + tast_field];
	else if (tast_field == 4) tast_value = bound(-89,tast_rows[b+4] * 360 / 65536,89);
	else if (tast_field == 5) tast_value = tast_rows[b+5] * 360 / 65536;
	else
	{
		bit = tast_field == 6 ? 1 : (tast_field == 7 ? 2 : 4);
		tast_value = (tast_rows[b+6] & (int)bit) ? 1 : 0;
	}
};

void() TASTimeline_Apply =
{
	local string line;
	if (!TASTimeline_Current() || !FS_TASEditValue(tast_field, tast_value))
	{
		print("tas timeline: refresh the paused head before editing\n");
		return;
	}
	line = sprintf("p1 cmd tas slice %.0f %.0f %s %.13f", tast_from, tast_to,
		FS_TASEditName(tast_field), tast_value);
	localcmd(strcat(line, sprintf(" %.0f %.0f %.0f\n", tast_serial, tast_head, tast_request)));
	tast_n = 0; // disable a second click before a server acknowledgement
};

void(float redo) TASTimeline_History =
{
	if (!TASTimeline_Current()) return;
	if ((!redo && tast_undo < 1) || (redo && tast_redo < 1)) return;
	localcmd(sprintf("p1 cmd tas %s %.0f %.0f %.0f\n", redo ? "redo" : "undo",
		tast_serial, tast_head, tast_request));
	tast_n = 0;
};

void(float value) TASTimeline_Value =
{
	if (tast_field <= 3) value = rint(value);
	if (FS_TASEditValue(tast_field,value)) tast_value = value;
};

void(vector at, float width, float tsz, float hint, float row) TASTimeline_Draw =
{
	local float i, b, tick, current;
	local vector chip, range;
	local string label;
	current = TASTimeline_Current(); chip = [(width-18)/4,row,0];
	if (Profile_Chip("tast_prev",at,chip,"< 8",tsz,FALSE)) TASTimeline_Request(max(1,tast_first-8));
	if (Profile_Chip("tast_next",at+[(width+6)/4,0,0],chip,"8 >",tsz,FALSE)) TASTimeline_Request(tast_first+8);
	if (Profile_Chip("tast_latest",at+[(width+6)/2,0,0],chip,"Latest",tsz,FALSE)) TASTimeline_Request(0);
	if (Profile_Chip("tast_refresh",at+[(width+6)*3/4,0,0],chip,"Refresh",tsz,FALSE)) TASTimeline_Request(tast_first);
	at_y = at_y + row + hint;
	sui_text(at,[hint,hint],"Tick | Forward / Side / Up | Pitch / Yaw | Jump Duck Walk",SUI_THEME_DIM,1,0);
	at_y = at_y + hint*1.6;
	for (i = 0; i < tast_n; i = i + 1)
	{
		b = i*7; tick = tast_first+i;
		if (!tast_rows[b]) label = sprintf("%.0f | unavailable",tick);
		else
		{
			label = sprintf("%.0f | %g / %g / %g | %.3f / %.3f",tick,
				tast_rows[b+1],tast_rows[b+2],tast_rows[b+3],
				tast_rows[b+4]*360/65536,tast_rows[b+5]*360/65536);
			label = strcat(label,sprintf(" | %g %g %g",(tast_rows[b+6] & 1)?1:0,
				(tast_rows[b+6] & 2)?1:0,(tast_rows[b+6] & 4)?1:0));
		}
		if (Profile_Chip(sprintf("tast_row%g",i),at,[width,row,0],label,hint,tick==tast_selected))
		if (TASTimeline_Select(tick)) TASTimeline_ImportValue();
		at_y = at_y + row + 2;
	}
	if (!tast_n)
	{
		sui_text(at,[hint,hint],"Pause a running attempt, then Refresh.",SUI_THEME_ACCENT,1,0);
		at_y = at_y + row;
	}
	at_y = at_y + hint;
	sui_text(at,[hint,hint],sprintf("Selected %.0f | range %.0f..%.0f | head %.0f",tast_selected,tast_from,tast_to,tast_head),SUI_THEME_DIM,1,0);
	at_y = at_y + hint*1.6; chip = [(width-12)/3,row,0];
	if (Profile_Chip("tast_single",at,chip,"Single",tsz,FALSE)) tast_from = tast_to = tast_selected;
	if (Profile_Chip("tast_from",at+[(width+6)/3,0,0],chip,"From here",tsz,FALSE)) tast_from = min(tast_selected,tast_to);
	if (Profile_Chip("tast_to",at+[(width+6)*2/3,0,0],chip,"To here",tsz,FALSE)) tast_to = max(tast_selected,tast_from);
	at_y = at_y + row + hint;
	if (Profile_Chip("tast_field",at,[tsz*9,row,0],FS_TASEditName(tast_field),tsz,TRUE))
	{
		tast_field = tast_field % 8 + 1; TASTimeline_ImportValue();
	}
	if (tast_field <= 3) range = [min(-450,tast_value),max(450,tast_value),max(450,tast_value)-min(-450,tast_value)];
	else if (tast_field == 4) range = '-89 89 1780';
	else range = '-360 360 7200';
	if (tast_field <= 5) WPU_Slider("tast_value","Value",at+[tsz*10,0,0],width-tsz*10,tast_value,range,TASTimeline_Value,tsz);
	else if (Profile_Chip("tast_bits",at+[tsz*10,0,0],chip,tast_value ? "Held" : "Released",tsz,tast_value)) tast_value = !tast_value;
	at_y = at_y + row + hint;
	if (Profile_Chip("tast_apply",at,chip,"Recalculate",tsz,current)) TASTimeline_Apply();
	if (Profile_Chip("tast_undo",at+[(width+6)/3,0,0],chip,sprintf("Undo (%.0f)",tast_undo),tsz,current && tast_undo>0)) TASTimeline_History(FALSE);
	if (Profile_Chip("tast_redo",at+[(width+6)*2/3,0,0],chip,sprintf("Redo (%.0f)",tast_redo),tsz,current && tast_redo>0)) TASTimeline_History(TRUE);
	at_y = at_y + row + hint;
	sui_text(at,[hint,hint],current ? "Warm input history only; shared world is NOT rewound." :
		"Refresh after execution. Eight revisions; not a saved project.",SUI_THEME_MUTED,1,0);
};

// Console accessibility also drives the actual table actions in socket checks.
float(float argc, float seat) TASTimeline_ConsoleCommand =
{
	local string action;
	local float tick, i, b, field, value;
	if (seat != 0 || numclientseats > 1) { print("tas timeline: one local seat only\n"); return TRUE; }
	action = argv(2);
	if (argc == 2)
	{
		if (!tasu_open) TASUI_Toggle(0);
		if (tasu_open) { tasu_tab = 1; TASTimeline_Request(0); }
		return TRUE;
	}
	if (argc == 3 && !strcmp(action,"status"))
	{
		print(sprintf("tas timeline view: rows %.0f selected %.0f range %.0f..%.0f field %s value %.13f current %g\n",
			tast_n,tast_selected,tast_from,tast_to,FS_TASEditName(tast_field),tast_value,TASTimeline_Current()));
		for (i = 0; i < tast_n; i = i + 1)
		{
			b = i*7;
			if (tast_rows[b]) print(sprintf("tas timeline row %.0f: move %g %g %g words %.0f %.0f bits %.0f\n",
				tast_first+i,tast_rows[b+1],tast_rows[b+2],tast_rows[b+3],tast_rows[b+4],tast_rows[b+5],tast_rows[b+6]));
			else print(sprintf("tas timeline row %.0f: unavailable\n",tast_first+i));
		}
		return TRUE;
	}
	if (argc == 3)
	{
		if (!strcmp(action,"refresh")) { TASTimeline_Request(tast_first); return TRUE; }
		if (!strcmp(action,"latest")) { TASTimeline_Request(0); return TRUE; }
		if (!strcmp(action,"apply")) { TASTimeline_Apply(); return TRUE; }
		if (!strcmp(action,"undo")) { TASTimeline_History(FALSE); return TRUE; }
		if (!strcmp(action,"redo")) { TASTimeline_History(TRUE); return TRUE; }
		if (!strcmp(action,"single")) { tast_from = tast_to = tast_selected; return TRUE; }
		if (!strcmp(action,"from")) { tast_from = min(tast_selected,tast_to); return TRUE; }
		if (!strcmp(action,"to")) { tast_to = max(tast_selected,tast_from); return TRUE; }
	}
	if (argc == 4 && !strcmp(action,"select"))
	{
		if (!FS_TASNumber(argv(3))) goto bad;
		tick = fs_tas_number;
		if (TASTimeline_Select(tick)) TASTimeline_ImportValue();
		return TRUE;
	}
	if (argc == 5 && !strcmp(action,"field"))
	{
		field = FS_TASEditField(argv(3));
		if (!FS_TASNumber(argv(4))) goto bad;
		value = fs_tas_number;
		if (!FS_TASEditValue(field,value)) goto bad;
		tast_field = field; tast_value = value;
		return TRUE;
	}
:bad
	print("tas timeline: status | refresh/latest | select tick | single/from/to | field name value | apply | undo/redo\n");
	return TRUE;
};
