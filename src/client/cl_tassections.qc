// Named checkpoint intervals, not detected ramps or a solver verdict.
float tass_tag, tass_ready, tass_serial, tass_body, tass_request, tass_base, tass_head;
float tass_offset, tass_total, tass_n, tass_ncp, tass_next, tass_chosen;
float tass_start[TAS_SECTION_ROWS], tass_end[TAS_SECTION_ROWS];
string tass_names[TAS_SECTION_ROWS], tass_sha;

void() TASSections_Reset =
{
	local float i;
	tass_tag = tass_tag+1;
	if (tass_tag > 16000000) tass_tag = 1;
	tass_ready = tass_n = tass_total = tass_offset = tass_next = 0;
	tass_chosen = -1;
	if (!tast_marker_name) TASTimeline_MarkerName("section1");
	for (i = 0; i < TAS_SECTION_ROWS; i = i+1)
	{
		if (tass_names[i]) strunzone(tass_names[i]);
		tass_names[i] = "";
	}
	if (tass_sha) strunzone(tass_sha);
	tass_sha = "";
};

float() TASSections_Current =
{
	return (tass_ready && TASTimeline_Current() && tast_v2 && (tast_flags & 2) &&
		tass_body == getstatf(STAT_FS_TIMERTICKS) && tass_serial == tast_serial && tass_body == tast_bodyhead && tass_request == tast_request &&
		tass_base == tast_base && tass_head == tast_head && tass_ncp == tasp_cl_ncp &&
		!strcmp(tass_sha,tasp_cl_sha));
};

void(float offset) TASSections_Request =
{
	if (!TASTimeline_Current() || !tast_v2 || !(tast_flags & 2) || (tast_flags & 4)) return;
	if (offset < 0 || offset > TAS_SECTION_MAX-1 || offset != floor(offset)) return;
	tass_tag = tass_tag+1;
	if (tass_tag > 16000000) tass_tag = 1;
	tass_ready = FALSE; tass_chosen = -1; tass_offset = offset; tass_next = cltime+.5;
	localcmd(sprintf("p1 cmd tas sections2 %.0f %.0f %.0f %.0f %.0f\n",
		offset,tass_tag,tast_serial,tast_bodyhead,tast_request));
};

void() TASSections_Event =
{
	local float tag, serial, body, request, base, head, offset, total, n, ncp, take, good, i;
	local float first, last, previous, c;
	local string rev, name;
	tag = readlong(); serial = readlong(); body = readlong(); request = readlong();
	base = readlong(); head = readlong(); rev = strzone(readstring()); ncp = readbyte();
	offset = readbyte(); total = readbyte(); n = readbyte();
	take = (tag == tass_tag && tasu_open && TASUI_UsesTimeline(tasu_tab) && LT_StatsAreMine() && numclientseats <= 1);
	good = (base >= 0 && body >= base && head >= body && head < 16000000 &&
		total >= 1 && total <= TAS_SECTION_MAX && offset < total && n <= TAS_SECTION_ROWS &&
		n == min(TAS_SECTION_ROWS,total-offset) && ncp < TAS_SECTION_MAX && strlen(rev) == 64);
	for (i = 0; i < strlen(rev); i = i+1)
	{
		c = str2chr(rev,i);
		if (!((c >= 48 && c <= 57) || (c >= 97 && c <= 102))) good = FALSE;
	}
	previous = -1;
	for (i = 0; i < n; i = i+1)
	{
		first = readlong(); last = readlong(); name = readstring();
		if (!(first >= base && last > first && last <= head)) good = FALSE;
		if (i && first != previous) good = FALSE;
		if (!i && !offset && first != base) good = FALSE;
		if (i == n-1 && offset+n == total && last != head) good = FALSE;
		if (strlen(name))
		if (!FS_TASRecipeNameOK(name)) good = FALSE;
		previous = last;
		if (take && i < TAS_SECTION_ROWS)
		{
			tass_start[i] = first; tass_end[i] = last;
			if (tass_names[i]) strunzone(tass_names[i]);
			tass_names[i] = strzone(name);
		}
	}
	if (!take) { strunzone(rev); return; }
	tass_ready = good;
	if (!good) { strunzone(rev); return; }
	if (tass_sha) strunzone(tass_sha);
	tass_sha = rev;
	tass_serial = serial; tass_body = body; tass_request = request;
	tass_base = base; tass_head = head; tass_ncp = ncp;
	tass_offset = offset; tass_total = total; tass_n = n;
	print(sprintf("tas sections: page %.0f rows %.0f total %.0f base %.0f head %.0f current %g\n",
		tass_offset,tass_n,tass_total,tass_base,tass_head,TASSections_Current()));
};

void() TASSections_Pump =
{
	if (tasu_tab != TAS_TAB_SECTIONS || !TASTimeline_Current()) return;
	if (!TASSections_Current() && cltime >= tass_next) TASSections_Request(tass_offset);
};

void(float row) TASSections_Select =
{
	if (!TASSections_Current() || row < 0 || row >= tass_n || row != floor(row)) return;
	tast_from = tass_start[row]+1; tast_to = tass_end[row]; tast_pick = tast_from;
	TASUI_SelectTab(TAS_TAB_TIMELINE);
	// SelectTab's latest-page request coalesces into the actual selected section.
	TASTimeline_Request(tast_from);
};

void(float row, float at_end) TASSections_Seek =
{
	if (!TASSections_Current() || row < 0 || row >= tass_n || row != floor(row) || (tast_flags & 4)) return;
	TASTimeline_Action("seek2",at_end ? tass_end[row] : tass_start[row]);
};

float(float row) TASSections_Named =
{
	if (row < 0 || row >= tass_n || row != floor(row)) return FALSE;
	return strlen(tass_names[row]) > 0;
};

void(float row) TASSections_Choose =
{
	if (!TASSections_Current()) return;
	if (!TASSections_Named(row))
	{
		tass_chosen = -1;
		print("tas sections: unnamed end; Go to end, then Add here to name its actual body\n"); return;
	}
	TASTimeline_NameBlur(); tass_chosen = row;
	TASTimeline_MarkerName(tass_names[row]);
};

void(float op, float row) TASSections_Mark =
{
	local float tick;
	local string action, old, replacement, command;
	if (!TASSections_Current() || (tast_flags & 4)) { print("tas sections: Refresh a supported paused local line first\n"); return; }
	if (op < 1 || op > 4 || op != floor(op)) return;
	old = replacement = "_"; tick = tass_body;
	if (op != 1)
	{
		if (!TASSections_Named(row)) { print("tas sections: choose a named endpoint with Marker first\n"); return; }
		old = tass_names[row]; tick = tass_end[row];
	}
	if (op == 1 || op == 2)
	{
		if (!FS_TASRecipeNameOK(tast_marker_name)) { print("tas sections: choose a 1..32 character a-z 0-9 _ - marker name\n"); return; }
		replacement = tast_marker_name;
	}
	action = op == 1 ? "add" : (op == 2 ? "rename" : (op == 3 ? "remove" : "move"));
	command = sprintf("p1 cmd tas marker2 %s %s %s %.0f %s ",action,old,replacement,tick,tass_sha);
	localcmd(strcat(command,sprintf("%.0f %.0f %.0f\n",tass_serial,tass_body,tass_request)));
	TASTimeline_NameBlur(); TASSections_Reset();
	tast_n = 0; tast_wantrefresh = cltime+.6;
};

void(vector at, float width, float tsz, float hint, float row) TASSections_Draw =
{
	local float i;
	local vector chip;
	local string label;
	chip = [(width-12)/3,row,0];
	if (Profile_Chip("tass_refresh",at,chip,"Refresh",tsz,FALSE)) { TASSections_Reset(); TASTimeline_Request(0); }
	if (tass_offset > 0)
	if (Profile_Chip("tass_previous",at+[(width+6)/3,0,0],chip,"Previous",tsz,FALSE)) TASSections_Request(max(0,tass_offset-TAS_SECTION_ROWS));
	if (TASSections_Current())
	if (tass_offset+tass_n < tass_total)
	if (Profile_Chip("tass_next",at+[(width+6)*2/3,0,0],chip,"Next",tsz,FALSE)) TASSections_Request(tass_offset+TAS_SECTION_ROWS);
	at_y = at_y+row+hint;
	sui_text(at,[hint,hint],"Manual checkpoint sections; not detected ramp contact.",SUI_THEME_DIM,1,0);
	at_y = at_y+hint*1.8;
	if (!TASSections_Current())
	{
		sui_text(at,[hint,hint],"Pause a complete local captured line, then Refresh.",SUI_THEME_MUTED,1,0);
		return;
	}
	sui_text(at,[hint,hint],sprintf("Sections %.0f..%.0f of %.0f | body %.0f, retained to %.0f",
		tass_offset+1,tass_offset+tass_n,tass_total,tass_body,tass_head),SUI_THEME_TEXT,1,0);
	at_y = at_y+hint*2;
	TASTimeline_NameField(at,width,tsz,row,TRUE); at_y = at_y+row+hint;
	chip = [(width-18)/4,row,0];
	if (Profile_Chip("tass_add",at,chip,"Add here",hint,FALSE)) TASSections_Mark(1,-1);
	if (Profile_Chip("tass_rename",at+[(width+6)/4,0,0],chip,"Rename",hint,FALSE)) TASSections_Mark(2,tass_chosen);
	if (Profile_Chip("tass_remove",at+[(width+6)*2/4,0,0],chip,"Remove",hint,FALSE)) TASSections_Mark(3,tass_chosen);
	if (Profile_Chip("tass_move",at+[(width+6)*3/4,0,0],chip,"Move here",hint,FALSE)) TASSections_Mark(4,tass_chosen);
	at_y = at_y+row+hint;
	if (TASSections_Named(tass_chosen)) label = sprintf("Selected %s at %.0f | Add/Move uses paused body %.0f",tass_names[tass_chosen],tass_end[tass_chosen],tass_body);
	else label = "Choose Marker in a row to rename, remove or move its endpoint.";
	sui_text(at,[hint,hint],label,SUI_THEME_DIM,1,0); at_y = at_y+hint*1.8;
	for (i = 0; i < tass_n; i = i+1)
	{
		label = sprintf("%.0f: body %.0f -> %.0f | %s",tass_offset+i+1,tass_start[i],tass_end[i],
			strlen(tass_names[i]) ? strcat("to ",tass_names[i]) : "to retained end");
		sui_text(at,[hint,hint],label,SUI_THEME_TEXT,1,0); at_y = at_y+hint*1.8;
		if (Profile_Chip(sprintf("tass_select%g",i),at,chip,"Inputs",hint,FALSE)) TASSections_Select(i);
		if (Profile_Chip(sprintf("tass_start%g",i),at+[(width+6)/4,0,0],chip,"Go to start",hint,FALSE)) TASSections_Seek(i,FALSE);
		if (Profile_Chip(sprintf("tass_end%g",i),at+[(width+6)*2/4,0,0],chip,"Go to end",hint,FALSE)) TASSections_Seek(i,TRUE);
		if (Profile_Chip(sprintf("tass_marker%g",i),at+[(width+6)*3/4,0,0],chip,"Marker",hint,tass_chosen==i)) TASSections_Choose(i);
		at_y = at_y+row+hint;
	}
	sui_text(at,[hint,hint],"Marker edits auto-save ALL retained inputs; Undo/Redo replay revisions.",SUI_THEME_MUTED,1,0);
};

float(float argc, float seat) TASSections_ConsoleCommand =
{
	local string action;
	local float i, row;
	if (seat != 0 || numclientseats > 1) { print("tas sections: one local seat only\n"); return TRUE; }
	action = argv(2);
	if (argc == 2)
	{
		if (!tasu_open) TASUI_Toggle(0);
		if (tasu_open) TASUI_SelectTab(TAS_TAB_SECTIONS);
		return TRUE;
	}
	if (argc == 3 && !strcmp(action,"status"))
	{
		print(sprintf("tas sections view: current %g page %.0f rows %.0f total %.0f base %.0f head %.0f body %.0f\n",
			TASSections_Current(),tass_offset,tass_n,tass_total,tass_base,tass_head,tass_body));
		print(sprintf("tas marker draft: %s caret %.0f focus %g chosen %.0f\n",tast_marker_name,tast_marker_caret,tast_recipe_focus,tass_chosen+tass_offset+1));
		for (i = 0; i < tass_n; i = i+1)
			print(sprintf("tas section %.0f: body %.0f..%.0f inputs %.0f..%.0f name [%s]\n",
				tass_offset+i+1,tass_start[i],tass_end[i],tass_start[i]+1,tass_end[i],tass_names[i]));
		return TRUE;
	}
	if (argc == 3 && !strcmp(action,"refresh")) { TASSections_Reset(); TASTimeline_Request(0); return TRUE; }
	if (argc == 3 && !strcmp(action,"add")) { TASSections_Mark(1,-1); return TRUE; }
	if (argc == 4 && !strcmp(action,"name"))
	{
		if (!FS_TASRecipeNameOK(argv(3))) goto bad;
		TASTimeline_MarkerName(argv(3)); print(strcat("tas marker draft: ",tast_marker_name,"\n")); return TRUE;
	}
	if (argc == 3 && !strcmp(action,"next"))
	{
		if (TASSections_Current() && tass_offset+tass_n < tass_total) TASSections_Request(tass_offset+TAS_SECTION_ROWS);
		return TRUE;
	}
	if (argc == 3 && !strcmp(action,"previous"))
	{
		if (TASSections_Current() && tass_offset > 0) TASSections_Request(max(0,tass_offset-TAS_SECTION_ROWS));
		return TRUE;
	}
	if (argc == 4)
	{
		if (!FS_TASNumber(argv(3))) goto bad;
		row = fs_tas_number-tass_offset-1;
		if (!TASSections_Current() || row < 0 || row >= tass_n || row != floor(row)) goto bad;
		if (!strcmp(action,"choose")) { TASSections_Choose(row); return TRUE; }
		if (!strcmp(action,"rename")) { TASSections_Mark(2,row); return TRUE; }
		if (!strcmp(action,"remove")) { TASSections_Mark(3,row); return TRUE; }
		if (!strcmp(action,"move")) { TASSections_Mark(4,row); return TRUE; }
		if (!strcmp(action,"select")) { TASSections_Select(row); return TRUE; }
		if (!strcmp(action,"start")) { TASSections_Seek(row,FALSE); return TRUE; }
		if (!strcmp(action,"end")) { TASSections_Seek(row,TRUE); return TRUE; }
	}
:bad
	print("tas sections: status | refresh | next/previous | select/start/end/choose section-number-on-page\n");
	print("tas sections: name marker-name | add | rename/remove/move section-number-on-page\n");
	return TRUE;
};
