// The table is a view, not a source of authority. Server binds every GUI edit.
float tast_tag, tast_serial, tast_head, tast_request, tast_first, tast_n, tast_status;
float tast_undo, tast_redo, tast_selected, tast_from, tast_to, tast_field, tast_value;
float tast_next, tast_bodyhead, tast_base, tast_flags, tast_v2;
float tast_originaltime, tast_candidatetime, tast_wantrefresh, tast_refreshat, tast_pick;
float tast_pagepending, tast_pagefirst;
float tast_rows[TAS_PAGE_ROWS * 7]; // present, forward, side, up, pitch word, yaw word, buttons
string tast_recipe_name;
float tast_recipe_caret, tast_recipe_focus;
// P1082 project status, from the server's event 51.
string tasp_cl_name;
float tasp_cl_rev, tasp_cl_base, tasp_cl_head, tasp_cl_load, tasp_cl_stop, tasp_cl_result;
float tasp_cl_dev, tasp_cl_devtick, tasp_cl_ncp, tasp_cl_next, tasp_cl_asked;
// P1090: the current revision's statement fields, and whether it is signed.
string tasp_cl_sha, tasp_cl_parsha, tasp_cl_mapcrc;
float tasp_cl_supa, tasp_cl_supb, tasp_cl_signed, tasp_cl_made, tasp_cl_signdrawn;
vector tasp_cl_signat, tasp_cl_signsz;
// P1090 engine (cl_receipt.c): `<pub> <sig> <code>` over FTESURF-TASREV 1, or "".
string(string sha, string parent, string mapcrc, float from, float to) tasrev_sign = #0:tasrev_sign;

void(float first) TASTimeline_Request;
string(string old) TASProject_Keep = { if (old) strunzone(old); return strzone(readstring()); };
void() TASProject_Event =
{
	local float was;
	tasp_cl_name = TASProject_Keep(tasp_cl_name);
	tasp_cl_rev = readlong(); tasp_cl_base = readlong(); tasp_cl_head = readlong();
	was = tasp_cl_load;
	tasp_cl_load = readbyte(); tasp_cl_stop = readlong(); tasp_cl_result = readbyte();
	if (tasp_cl_load && !was) tr_tasload_at = cltime; // shared downloads load later than their click
	tasp_cl_dev = readfloat(); tasp_cl_devtick = readlong(); tasp_cl_ncp = readbyte();
	tasp_cl_sha = TASProject_Keep(tasp_cl_sha); tasp_cl_parsha = TASProject_Keep(tasp_cl_parsha);
	tasp_cl_mapcrc = TASProject_Keep(tasp_cl_mapcrc);
	tasp_cl_supa = readlong(); tasp_cl_supb = readlong(); tasp_cl_signed = readbyte(); tasp_cl_made = readbyte();
	if (was && !tasp_cl_load && tasu_open && TASUI_UsesTimeline(tasu_tab)) TASTimeline_Request(0);
};

// P1090: called on the press itself (TASUI_Input): the engine signs only while a device's key
// event is being delivered, so a chip's release, a command or a frame cannot sign.
void() TASProject_SignPress =
{
	local string p;
	if (!cl_input_real || tasp_cl_sha == "") return;
	if (!isserver()) { print("tas project: signing needs a game you host\n"); return; }
	if (cltime < tasp_cl_next) { print("tas project: one request at a time; click again\n"); return; }
	if (!tasp_cl_made) { print("tas project: this revision was loaded, not saved here; edit and save to sign your changes\n"); return; }
	if (tasp_cl_supa <= 0)
	{
		print(tasp_cl_supa < 0 ? "tas project: this revision predates signing; edit and save to sign your changes\n"
			: "tas project: this revision changes no inputs of its parent; nothing to sign\n");
		return;
	}
	if (!checkbuiltin(tasrev_sign)) { print("tas project: this game cannot sign revisions (needs the P1090 engine)\n"); return; }
	p = tasrev_sign(tasp_cl_sha, (tasp_cl_parsha != "") ? tasp_cl_parsha : "-", tasp_cl_mapcrc, tasp_cl_supa, tasp_cl_supb);
	if (tokenize(p) != 3) { print("tas project: the game would not sign this revision\n"); return; }
	tasp_cl_next = cltime + 0.5;
	localcmd(sprintf("p1 cmd tas project signed %s %s %.0f %.0f %s %s %s\n", tasp_cl_sha,
		(tasp_cl_parsha != "") ? tasp_cl_parsha : "-", tasp_cl_supa, tasp_cl_supb, argv(2), argv(0), argv(1)));
};

// tas project ... / tas cp ...: forwarded word for word; names are a-z 0-9 _ -.
float(float argc, float seat) TASProject_ConsoleCommand =
{
	local float i, j, c;
	local string line, w;
	line = sprintf("p%g cmd tas", seat + 1);
	for (i = 1; i < argc; i = i + 1)
	{
		w = argv(i);
		for (j = 0; j < strlen(w); j = j + 1)
		{
			c = str2chr(w, j);
			if (!((c >= 97 && c <= 122) || (c >= 48 && c <= 57) || c == 95 || c == 45))
			{
				print("tas project: save [name] [force] | load name [checkpoint] | list | diff a b | status | close; tas cp add/del name | list\n");
				return TRUE;
			}
		}
		line = strcat(line, " ", w);
	}
	if (!strcmp(argv(1),"project") && (!strcmp(argv(2),"share") || !strcmp(argv(2),"open")))
		return TASShare_ConsoleCommand(argc,seat);
	if (argv(1) == "project" && argv(2) == "load")
		tr_tasload_at = cltime;     // P1087: its load is another run's line (Trail_TASGo)
	localcmd(strcat(line, "\n"));
	return TRUE;
};

void() TASTimeline_Reset =
{
	tast_tag = tast_tag + 1; // invalidate an in-flight page, including close/map change
	tast_n = tast_undo = tast_redo = tast_flags = tast_v2 = tast_wantrefresh = tast_pick = 0;
	tast_pagepending = tast_pagefirst = 0;
	tasp_cl_asked = FALSE;  // ask for project status on the next open
	tast_recipe_focus = FALSE;
};

float() TASTimeline_Current =
{
	return (tast_n > 0 && !tast_status && getstatf(STAT_FS_TASREQUEST) == tast_request &&
		getstatf(STAT_FS_TASPAUSE) == 1 && getstatf(STAT_FS_TASPENDING) == 0 &&
		LT_StatsAreMine() && numclientseats <= 1);
};

void(string name) TASTimeline_RecipeName =
{
	local string copy;
	copy = strzone(name);
	if (tast_recipe_name) strunzone(tast_recipe_name);
	tast_recipe_name = copy; tast_recipe_caret = strlen(copy);
};

float(float evtype, float scanx, float chary) TASTimeline_RecipeInput =
{
	if (!tasu_open || tasu_tab != TAS_TAB_PROJECT) { tast_recipe_focus = FALSE; return FALSE; }
	if (!tast_recipe_focus) return FALSE;
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN)
		if (!sui_is_hovered("tastr_name")) tast_recipe_focus = FALSE;
		return FALSE;
	}
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP) return FALSE;
	if (scanx == K_ESCAPE || scanx == K_ENTER || scanx == K_KP_ENTER)
	{
		if (evtype == IE_KEYDOWN) tast_recipe_focus = FALSE;
		return TRUE;
	}
	if (chary >= 65 && chary <= 90) chary = chary+32;
	if (chary >= 32 && chary != 127)
	if (!((chary >= 97 && chary <= 122) || (chary >= 48 && chary <= 57) || chary == 95 || chary == 45))
		return TRUE;
	sui_text_event(evtype,scanx,chary,"tastr_name",tast_recipe_name,tast_recipe_caret);
	if (strlen(tast_recipe_name) > 32)
	{
		TASTimeline_RecipeName(substring(tast_recipe_name,0,32));
		tast_recipe_caret = min(tast_recipe_caret,32);
	}
	return TRUE;
};

void(float first) TASTimeline_Request =
{
	if (cltime < tast_next)
	{
		// Coalesce navigation while a completion page is in flight; never drop a click.
		tast_pagepending = 1; tast_pagefirst = first; return;
	}
	tast_pagepending = 0;
	tast_next = cltime + 0.3;
	if (!LT_StatsAreMine() || numclientseats > 1 || cvar("cl_threadedphysics") ||
		getstatf(STAT_FS_TASINPUT) != 1)
	{
		print("tas timeline: needs own body, one seat, supported input and cl_threadedphysics 0\n");
		return;
	}
	tast_tag = tast_tag + 1;
	if (tast_tag > 16000000) tast_tag = 1;
	tast_n = tast_undo = tast_redo = tast_wantrefresh = 0;
	localcmd(sprintf("p1 cmd tas page2 %.0f %.0f\n", first, tast_tag));
};

void() TASTimeline_ImportValue;

void(float extended) TASTimeline_ReadEvent =
{
	local float tag, serial, head, request, first, status, n, undo, redo, i, j, present, v, good, take;
	local float base, linehead, flags, originaltime, candidatetime, keeprange;
	flags = originaltime = candidatetime = 0;
	tag = readlong(); serial = readlong(); head = readlong(); request = readlong(); first = readlong();
	base = max(0, head - TAS_TAPE_MAX); linehead = head;
	if (extended) { base = readlong(); linehead = readlong(); }
	status = readbyte(); n = readbyte(); undo = readbyte(); redo = readbyte();
	if (extended) { flags = readbyte(); originaltime = readfloat(); candidatetime = readfloat(); }
	take = (tag == tast_tag && tasu_open && LT_StatsAreMine() && numclientseats <= 1);
	good = (n <= TAS_PAGE_ROWS && status == 0 && first > base && linehead >= first &&
		base >= 0 && head >= 0 && head < 16000000 && linehead < 16000000 &&
		first + n - 1 <= linehead && undo <= 8 && redo <= 8 && flags <= 63 &&
		originaltime >= 0 && originaltime <= 1000000 && candidatetime >= 0 && candidatetime <= 1000000);
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
	keeprange = (serial == tast_serial && tast_from > base && tast_from <= tast_to && tast_to <= linehead);
	tast_serial = serial; tast_bodyhead = head; tast_head = linehead; tast_base = base;
	tast_v2 = extended; tast_flags = flags;
	tast_originaltime = originaltime; tast_candidatetime = candidatetime;
	tast_request = request; tast_first = first;
	tast_n = good ? n : 0; tast_status = status;
	tast_undo = good ? undo : 0; tast_redo = good ? redo : 0;
	tast_selected = first + max(0, tast_n - 1);
	if (tast_pick >= first && tast_pick < first + tast_n) tast_selected = tast_pick;
	if (!keeprange) tast_from = tast_to = tast_selected;
	if (!tast_field) tast_field = 2;
	if (good && n > 0) TASTimeline_ImportValue();
	print(sprintf("tas timeline: page %.0f rows %.0f head %.0f serial %.0f request %.0f undo %.0f redo %.0f\n",
		tast_first, tast_n, tast_head, tast_serial, tast_request, tast_undo, tast_redo));
};

void() TASTimeline_Event = { TASTimeline_ReadEvent(FALSE); };
void() TASTimeline_Event2 = { TASTimeline_ReadEvent(TRUE); };

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
	if (tast_v2)
	if (!(tast_flags & 2) || (tast_flags & 4))
	{
		print("tas timeline: complete live base required; Keep/Discard an active preview first\n"); return;
	}
	line = sprintf("p1 cmd tas %s %.0f %.0f %s %.13f", tast_v2 ? "preview2" : "slice", tast_from, tast_to,
		FS_TASEditName(tast_field), tast_value);
	localcmd(strcat(line, sprintf(" %.0f %.0f %.0f\n", tast_serial, tast_bodyhead, tast_request)));
	tast_n = 0; // disable a second click before a server acknowledgement
	tast_wantrefresh = 1; tast_refreshat = cltime + 0.6;
};

void(string action, float tick) TASTimeline_Action =
{
	if (!TASTimeline_Current() || !tast_v2 || !(tast_flags & 2)) return;
	if (!strcmp(action, "seek2"))
		localcmd(sprintf("p1 cmd tas seek2 %.0f %.0f %.0f %.0f\n", tick, tast_serial, tast_bodyhead, tast_request));
	else
		localcmd(sprintf("p1 cmd tas %s %.0f %.0f %.0f\n", action, tast_serial, tast_bodyhead, tast_request));
	tast_pick = tast_selected; tast_n = 0;
	tast_wantrefresh = 1; tast_refreshat = cltime + 0.6;
};

void(float save) TASTimeline_Recipe =
{
	local string line;
	if (!TASTimeline_Current() || !tast_v2 || !(tast_flags & 2) || (tast_flags & 4) || (tast_flags & 16))
	{
		print("tas recipe: refresh a complete paused line and settle the previous edit first\n"); return;
	}
	if (!FS_TASRecipeNameOK(tast_recipe_name))
	{
		print("tas recipe: name uses 1..32 lowercase letters, digits, _ or -\n"); return;
	}
	line = sprintf("p1 cmd tas %s %s %.0f %.0f %.0f %.0f %.0f\n",save ? "recipesave2" : "recipeapply2",
		tast_recipe_name,tast_from,tast_to,tast_serial,tast_bodyhead,tast_request);
	localcmd(line);
	tast_recipe_focus = FALSE; tast_pick = tast_selected; tast_n = 0;
	tast_wantrefresh = 1; tast_refreshat = cltime+0.6;
};

void(float redo) TASTimeline_History =
{
	if (!TASTimeline_Current()) return;
	if ((!redo && tast_undo < 1) || (redo && tast_redo < 1)) return;
	if (tast_v2)
	if (!(tast_flags & 2) || (tast_flags & 4)) return;
	localcmd(sprintf("p1 cmd tas %s %.0f %.0f %.0f\n", tast_v2 ? (redo ? "redo2" : "undo2") : (redo ? "redo" : "undo"),
		tast_serial, tast_bodyhead, tast_request));
	tast_n = 0; tast_wantrefresh = 1; tast_refreshat = cltime + 0.6;
};

void(float value) TASTimeline_Value =
{
	if (tast_field <= 3) value = rint(value);
	if (FS_TASEditValue(tast_field,value)) tast_value = value;
};

// P1087: you against the line the last TAS go cut off (LN_S_TASREF), where you are now:
// time is yours minus its to get here (+ behind), speed yours minus its here.
float tasc_ok, tasc_dt, tasc_ds;
string() TASCompare_Text =
{
	local vector ss;
	tasc_ok = FALSE;
	if (!tr_tasref || Cmp_Off())    // a rewind cursor's clock is not your body's
		return "";
	if (!Cmp_Match(LN_S_TASREF, 0, HUD_Feet()))
		return "Before the edit (pink): not near its route here.";
	ss = HUD_SplitSample();
	tasc_dt = rg_now - cmp_mt;
	tasc_ds = ss_x - cmp_ms;
	tasc_ok = TRUE;
	return sprintf("Before the edit (pink): %s%.3f s here, %s%.0f u/s",
		(tasc_dt >= 0) ? "+" : "", tasc_dt, (tasc_ds >= 0) ? "+" : "", tasc_ds);
};

void(float value) TASTimeline_Goto =
{
	tast_pick = bound(tast_base + 1, rint(value), max(tast_base + 1, tast_head));
	TASTimeline_Request(max(tast_base + 1, tast_pick - 3));
};

// Shared by Timeline and Project; both pages need a current paused-body binding.
void() TASTimeline_Pump =
{
	if (tast_pagepending && cltime >= tast_next) TASTimeline_Request(tast_pagefirst);
	if (tast_wantrefresh && cltime >= tast_refreshat && !tasp_cl_load)
	if (getstatf(STAT_FS_TASPAUSE) == 1 && getstatf(STAT_FS_TASPENDING) == 0)
		TASTimeline_Request(tast_pick > 0 ? max(tast_base + 1, tast_pick - 3) : 0);
};

void(vector at, float width, float tsz, float hint, float row) TASTimeline_Draw =
{
	local float i, b, tick, current;
	local vector chip, range;
	local string label;
	current = TASTimeline_Current(); chip = [(width-18)/4,row,0];
	if (Profile_Chip("tast_prev",at,chip,"< 8",tsz,FALSE)) TASTimeline_Request(max(tast_base+1,tast_first-8));
	if (Profile_Chip("tast_next",at+[(width+6)/4,0,0],chip,"8 >",tsz,FALSE)) TASTimeline_Request(tast_first+8);
	if (Profile_Chip("tast_latest",at+[(width+6)/2,0,0],chip,"Latest",tsz,FALSE)) TASTimeline_Request(0);
	if (Profile_Chip("tast_refresh",at+[(width+6)*3/4,0,0],chip,"Refresh",tsz,FALSE)) TASTimeline_Request(tast_first);
	at_y = at_y + row + hint;
	if (tast_head > tast_base + 1)
	{
		WPU_Slider("tast_scrub", "Browse tick", at, width, tast_selected,
			[tast_base+1,tast_head,max(1,tast_head-tast_base-1)], TASTimeline_Goto, tsz);
		at_y = at_y + row + hint;
	}
	sui_text(at,[hint,hint],sprintf("Captured %.0f..%.0f | body %.0f | recorded input, recipe unknown",tast_base+1,tast_head,tast_bodyhead),SUI_THEME_DIM,1,0);
	at_y = at_y + hint*1.6;
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
	if (Profile_Chip("tast_from",at+[(width+6)/3,0,0],chip,"From here",tsz,FALSE))
	{ tast_from = tast_selected; tast_to = max(tast_to,tast_from); }
	if (Profile_Chip("tast_to",at+[(width+6)*2/3,0,0],chip,"To here",tsz,FALSE))
	{ tast_to = tast_selected; tast_from = min(tast_from,tast_to); }
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
	if (Profile_Chip("tast_apply",at,chip,tast_v2 ? "Preview line" : "Recalculate",tsz,current && !(tast_flags & 4))) TASTimeline_Apply();
	if (Profile_Chip("tast_undo",at+[(width+6)/3,0,0],chip,sprintf("Undo (%.0f)",tast_undo),tsz,current && tast_undo>0 && !(tast_flags & 4))) TASTimeline_History(FALSE);
	if (Profile_Chip("tast_redo",at+[(width+6)*2/3,0,0],chip,sprintf("Redo (%.0f)",tast_redo),tsz,current && tast_redo>0 && !(tast_flags & 4))) TASTimeline_History(TRUE);
	at_y = at_y + row + hint;
	if (tast_v2)
	{
		chip = [(width-18)/4,row,0];
		if (Profile_Chip("tast_seek",at,chip,"Seek before",tsz,current && !(tast_flags & 4)))
			TASTimeline_Action("seek2",max(tast_base,tast_selected-1));
		if (Profile_Chip("tast_seekhead",at+[(width+6)/4,0,0],chip,"Replay head",tsz,current && !(tast_flags & 4))) TASTimeline_Action("seek2",tast_head);
		if (Profile_Chip("tast_keep",at+[(width+6)/2,0,0],chip,"Keep",tsz,current && (tast_flags & 8))) TASTimeline_Action("keep2",0);
		if (Profile_Chip("tast_discard",at+[(width+6)*3/4,0,0],chip,"Discard",tsz,current && (tast_flags & 4))) TASTimeline_Action("discard2",0);
		at_y = at_y + row + hint; chip = [(width-12)/3,row,0];
		if (tast_flags & 8) label = "Preview complete. Original retained; shared world is not rewound.";
		else if (tast_flags & 16)
		{
			if (tast_flags & 4) label = "Preview stopped/not complete. Original retained: Discard from a supported paused body.";
			else label = "Retained replay stopped. Retry the same Undo/Redo from a supported paused body.";
		}
		else label = "Native tick replay; packet timing can differ. Shared world is not rewound.";
		sui_text(at,[hint,hint],label,SUI_THEME_DIM,1,0); at_y = at_y + hint*1.6;
	}
	label = TASCompare_Text();
	if (label != "") sui_text(at,[hint,hint],label,SUI_THEME_DIM,1,0);
};

void(vector at, float width, float tsz, float hint, float row) TASProject_Draw =
{
	local float current;
	local vector chip;
	local string label;
	current = TASTimeline_Current(); chip = [(width-12)/3,row,0];
	// P1082: the project row. The server answers each button in the console too.
	if (!tasp_cl_asked) { tasp_cl_asked = TRUE; localcmd("p1 cmd tas project event\n"); }
	if (tasp_cl_name == "") label = "Project: none. Save project keeps these inputs and a base save on disk.";
	else
	{
		label = sprintf("Project %s rev %.0f | ticks %.0f..%.0f | %.0f checkpoints", tasp_cl_name, tasp_cl_rev,
			tasp_cl_base, tasp_cl_head, tasp_cl_ncp);
	}
	sui_text(at,[hint,hint],label,SUI_THEME_DIM,1,0);
	at_y = at_y + hint*1.6;
	if (tasp_cl_name != "")
	{
		if (tasp_cl_load) label = sprintf("Loading to %.0f", tasp_cl_stop);
		else if (tasp_cl_result == 1) label = "Reproduced every saved checkpoint exactly";
		else if (tasp_cl_result == 2) label = sprintf("DIVERGED at %.0f (max %.4f)", tasp_cl_devtick,tasp_cl_dev);
		else if (tasp_cl_result == 3) label = "Load stopped";
		else if (tasp_cl_result == 4)
		{
			if (tasp_cl_devtick > 0) label = sprintf("Partial seek: visited prefix DIVERGED at %.0f (max %.4f); future retained",tasp_cl_devtick,tasp_cl_dev);
			else label = "Partial seek: only visited checkpoints checked; future retained";
		}
		else label = "Saved";
		sui_text(at,[hint,hint],label,(tasp_cl_result == 2 || (tasp_cl_result == 4 && tasp_cl_devtick > 0)) ? SUI_THEME_ACCENT : SUI_THEME_DIM,1,0);
		at_y = at_y + hint*1.6;
	}
	if (Profile_Chip("tasp_save",at,chip,"Save project",tsz,FALSE) && cltime >= tasp_cl_next)
	{
		tasp_cl_next = cltime + 0.5; localcmd("p1 cmd tas project save\n");
	}
	if (Profile_Chip("tasp_load",at+[(width+6)/3,0,0],chip,"Reload project",tsz,FALSE) && cltime >= tasp_cl_next)
	if (tasp_cl_name != "")
	{
		tasp_cl_next = tr_tasload_at = cltime + 0.5; localcmd(sprintf("p1 cmd tas project load %s\n", tasp_cl_name));
	}
	if (Profile_Chip("tasp_cp",at+[(width+6)*2/3,0,0],chip,"Checkpoint",tsz,FALSE) && cltime >= tasp_cl_next)
	if (current)
	{
		tasp_cl_next = cltime + 0.5; localcmd(sprintf("p1 cmd tas cp add cp%.0f\n", tast_head));
	}
	at_y = at_y + row + hint;
	label = TASCompare_Text();
	if (label != "")
	{
		sui_text(at,[hint,hint],label,(tasc_ok && tasc_dt > 0) ? SUI_THEME_ACCENT : SUI_THEME_DIM,1,0);
		at_y = at_y + hint*1.6;
	}
	// Kept as an advanced legacy tool, NOT the constrained section solver.
	sui_text(at,[hint,hint],"Legacy speed search: no next-ramp constraint, not route-safe.",SUI_THEME_ACCENT,1,0);
	at_y = at_y + hint*1.6;
	if (Profile_Chip("topt_left",at,chip,"Best turn left (32)",tsz,FALSE) && cltime >= tasp_cl_next && current)
	{
		tasp_cl_next = cltime + 0.5; localcmd("p1 cmd tas optimize 32 left\n");
	}
	if (Profile_Chip("topt_right",at+[(width+6)/3,0,0],chip,"Best turn right (32)",tsz,FALSE) && cltime >= tasp_cl_next && current)
	{
		tasp_cl_next = cltime + 0.5; localcmd("p1 cmd tas optimize 32 right\n");
	}
	// P1090: acts on the press (TASProject_SignPress); the chip only draws.
	if (tasp_cl_sha != "")
	{
		if (!isserver()) label = "Sign: host the game";
		else if (!tasp_cl_made) label = "Loaded, not yours";
		else if (tasp_cl_supa <= 0) label = "Nothing to sign";
		else label = sprintf("%s %.0f..%.0f", tasp_cl_signed ? "Signed" : "Sign", tasp_cl_supa, tasp_cl_supb);
		Profile_Chip("tasp_sign",at+[(width+6)*2/3,0,0],chip,label,tsz,tasp_cl_signed);
		tasp_cl_signat = at+[(width+6)*2/3,0,0]; tasp_cl_signsz = chip; tasp_cl_signdrawn = cltime;
	}
	at_y = at_y + row + hint;
	// P1090: what a Sign press attests, parent included, in place of the hint.
	if (tasp_cl_sha != "" && tasp_cl_supa > 0 && tasp_cl_made)
		label = sprintf("Sign attests revision %s %s, ticks %.0f..%.0f", substring(tasp_cl_sha, 0, 8),
			(tasp_cl_parsha != "") ? strcat("over ", substring(tasp_cl_parsha, 0, 8)) : "(a new line)", tasp_cl_supa, tasp_cl_supb);
	else label = current ? "Warm input history; the shared world is NOT rewound." :
		"Refresh after execution. Undo keeps eight edits; a project keeps them on disk.";
	sui_text(at,[hint,hint],label,SUI_THEME_MUTED,1,0);
	at_y = at_y+row+hint;
	sui_text(at,[hint,hint],sprintf("Named input recipe | selected span %.0f..%.0f | fixed map ticks",tast_from,tast_to),SUI_THEME_DIM,1,0);
	at_y = at_y+hint*1.6;
	if (!tast_recipe_name) TASTimeline_RecipeName("line1");
	sui_text_metrics(ceil(row*0.45),[tsz,tsz]);
	sui_text_input("tastr_name",at,[width,row,0],tast_recipe_name,tast_recipe_caret);
	if (sui_is_held("tastr_name") || sui_is_clicked("tastr_name"))
	{
		Profile_Unfocus(); tast_recipe_focus = TRUE; sui_field_focus("tastr_name");
	}
	Profile_FieldLook("tastr_name",at,[width,row,0],tsz,tast_recipe_name,tast_recipe_caret,
		"Recipe name: a-z 0-9 _ -",tast_recipe_focus,row*0.5,ceil(row*0.45));
	at_y = at_y+row+hint; chip = [(width-6)/2,row,0];
	if (Profile_Chip("tastr_save",at,chip,"Save selected input",tsz,current && !(tast_flags & 4))) TASTimeline_Recipe(TRUE);
	if (Profile_Chip("tastr_apply",at+[(width+6)/2,0,0],chip,"Preview named recipe",tsz,current && !(tast_flags & 4))) TASTimeline_Recipe(FALSE);
	at_y = at_y+row+hint;
	if (tast_flags & 4)
	{
		if (Profile_Chip("tastr_keep",at,chip,"Keep recipe preview",tsz,current && (tast_flags & 8))) TASTimeline_Action("keep2",0);
		if (Profile_Chip("tastr_discard",at+[(width+6)/2,0,0],chip,"Discard recipe preview",tsz,current)) TASTimeline_Action("discard2",0);
		at_y = at_y+row+hint;
	}
	sui_text(at,[hint,hint],"Select the span in Timeline. Recipes supply keys, not a body or signing authority.",SUI_THEME_DIM,1,0);
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
		if (tasu_open) TASUI_SelectTab(TAS_TAB_TIMELINE);
		return TRUE;
	}
	if (argc == 3 && !strcmp(action,"status"))
	{
		print(sprintf("tas timeline view: rows %.0f selected %.0f range %.0f..%.0f field %s value %.13f current %g\n",
			tast_n,tast_selected,tast_from,tast_to,FS_TASEditName(tast_field),tast_value,TASTimeline_Current()));
		print(sprintf("tas timeline extent: base %.0f head %.0f body %.0f flags %.0f v2 %.0f undo %.0f redo %.0f\n",
			tast_base,tast_head,tast_bodyhead,tast_flags,tast_v2,tast_undo,tast_redo));
		for (i = 0; i < tast_n; i = i + 1)
		{
			b = i*7;
			if (tast_rows[b]) print(sprintf("tas timeline row %.0f: move %g %g %g words %.0f %.0f bits %.0f\n",
				tast_first+i,tast_rows[b+1],tast_rows[b+2],tast_rows[b+3],tast_rows[b+4],tast_rows[b+5],tast_rows[b+6]));
			else print(sprintf("tas timeline row %.0f: unavailable\n",tast_first+i));
		}
		return TRUE;
	}
	if ((argc == 3 || argc == 4) && !strcmp(action,"sign"))   // P1090, for arms: where a real click must land
	{
		if (argv(3) == "probe" && checkbuiltin(tasrev_sign))   // a command is no press: the engine must refuse
			print(sprintf("tas timeline sign probe: [%s]\n", tasrev_sign(tasp_cl_sha,
				(tasp_cl_parsha != "") ? tasp_cl_parsha : "-", tasp_cl_mapcrc, tasp_cl_supa, tasp_cl_supb)));
		print(sprintf("tas timeline sign: chip %v size %v drawn %.2f ago cursor %v hover %g ",
			tasp_cl_signat, tasp_cl_signsz, cltime - tasp_cl_signdrawn, _cursor_position, sui_is_hovered("tasp_sign")));
		print(sprintf("sha %s supply %.0f..%.0f signed %g engine %g made %g\n", substring(tasp_cl_sha, 0, 8),
			tasp_cl_supa, tasp_cl_supb, tasp_cl_signed, checkbuiltin(tasrev_sign), tasp_cl_made));
		return TRUE;
	}
	if (argc == 5 && !strcmp(action,"recipe"))
	{
		if (!FS_TASRecipeNameOK(argv(4))) goto bad;
		if (strcmp(argv(3),"save") && strcmp(argv(3),"apply")) goto bad;
		b = !strcmp(argv(3),"save");
		TASTimeline_RecipeName(argv(4)); TASTimeline_Recipe(b); return TRUE;
	}
	if (argc == 3)
	{
		if (!strcmp(action,"refresh")) { TASTimeline_Request(tast_first); return TRUE; }
		if (!strcmp(action,"latest")) { TASTimeline_Request(0); return TRUE; }
		if (!strcmp(action,"apply")) { TASTimeline_Apply(); return TRUE; }
		if (!strcmp(action,"keep")) { TASTimeline_Action("keep2",0); return TRUE; }
		if (!strcmp(action,"discard")) { TASTimeline_Action("discard2",0); return TRUE; }
		if (!strcmp(action,"seek")) { TASTimeline_Action("seek2",max(tast_base,tast_selected-1)); return TRUE; }
		if (!strcmp(action,"head")) { TASTimeline_Action("seek2",tast_head); return TRUE; }
		if (!strcmp(action,"undo")) { TASTimeline_History(FALSE); return TRUE; }
		if (!strcmp(action,"redo")) { TASTimeline_History(TRUE); return TRUE; }
		if (!strcmp(action,"single")) { tast_from = tast_to = tast_selected; return TRUE; }
		if (!strcmp(action,"from")) { tast_from = tast_selected; tast_to = max(tast_to,tast_from); return TRUE; }
		if (!strcmp(action,"to")) { tast_to = tast_selected; tast_from = min(tast_from,tast_to); return TRUE; }
		if (!strcmp(action,"compare"))  // P1087, for arms: the line, its ghost and the deltas
		{
			b = LN_B(LN_S_TASREF);
			TASCompare_Text();
			print(sprintf("tas timeline compare: line %g samples %g t %.4f..%.4f now %.4f ", tr_tasref,
				ln_n[LN_S_TASREF], tr_tasref ? ln_t[b + ln_ia[LN_S_TASREF]] : 0, tr_tasref ? ln_t[b + ln_ib[LN_S_TASREF]] : 0, rg_now));
			print(sprintf("ghost %g at %v ok %g dt %.4f ds %.2f ", (rg_n > 0 && rg_slot[0] == LN_S_TASREF),
				rg_pos[0], tasc_ok, tasc_dt, tasc_ds));
			print(sprintf("body %g model %g screen %v\n", rg_ent[0] != world, rg_ent[0] ? rg_ent[0].modelindex : 0,
				project(rg_pos[0] + '0 0 36')));
			return TRUE;
		}
	}
	if (argc == 4 && !strcmp(action,"goto"))
	{
		if (!FS_TASNumber(argv(3))) goto bad;
		tick = fs_tas_number;
		if (tick <= tast_base || tick > tast_head || tick != floor(tick)) goto bad;
		tast_pick = tick;
		TASTimeline_Request(max(tast_base+1,tick-3));
		return TRUE;
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
	print("tas timeline: status | refresh/latest | select tick | single/from/to | field name value | apply | undo/redo | recipe save/apply name\n");
	return TRUE;
};
