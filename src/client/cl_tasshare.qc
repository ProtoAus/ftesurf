// P1140: shared TAS projects are distinct from run rows and verification verdicts.
string tsb_map, tsb_sha, tsb_note;
float tsb_req, tsb_at, tsb_kind, tsb_have, tsb_detail, tsb_selected, tsb_before, tsb_offset, tsb_creditoffset, tsb_confirm;
int tsb_root, tsb_info;

string(string old, string value) TASShare_Keep =
{
	local string copy;
	copy = strzone(value);
	if (strcmp(old,"")) strunzone(old);
	return copy;
};
float(string s) TASShare_Hex =
{
	local float i, c;
	if (strlen(s) != 64) return FALSE;
	for (i = 0; i < 64; i = i + 1)
	{
		c = str2chr(s,i);
		if (!((c >= 48 && c <= 57) || (c >= 97 && c <= 102))) return FALSE;
	}
	return TRUE;
};
float() TASShare_Allowed =
{
	if (ui_consent_ver < FS_TERMS_ONLINE)
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
	{
		print("tas shared: accept the online terms first\n"); return FALSE;
	}
	return TRUE;
};
string() TASShare_URL =
{
	return TASDirectory_Endpoint(cvar_string("tas_directory"));
};
void() TASShare_Reset =
{
	tsb_req = tsb_selected = tsb_confirm = 0;
	if (tsb_have) json_free(tsb_root);
	if (tsb_detail) json_free(tsb_info);
	tsb_have = tsb_detail = FALSE;
	tsb_map = TASShare_Keep(tsb_map,""); tsb_sha = TASShare_Keep(tsb_sha,"");
	tsb_note = TASShare_Keep(tsb_note,"");
};

void(float before, string sha) TASShare_Request =
{
	local string url;
	if (!TASShare_Allowed()) return;
	if (tsb_req && cltime - tsb_at < 12) return;
	tsb_req = tsb_selected = tsb_confirm = 0; tsb_offset = tsb_creditoffset = 0;
	tsb_map = TASShare_Keep(tsb_map,serverkey("map"));
	tsb_note = TASShare_Keep(tsb_note,"Asking the TAS directory...");
	if (!strcmp(tsb_map,"")) { tsb_note = TASShare_Keep(tsb_note,"Join or host a map first."); return; }
	if (tsb_have) json_free(tsb_root);
	if (tsb_detail) json_free(tsb_info);
	tsb_have = tsb_detail = FALSE;
	tsb_kind = (strcmp(sha,"") != 0); tsb_before = before;
	tsb_sha = TASShare_Keep(tsb_sha,sha);
	if (strcmp(sha,"")) url = strcat(TASShare_URL(),"/rev/",sha);
	else url = sprintf("%s/map/%s%s",TASShare_URL(),uri_escape(tsb_map),
		before > 0 ? sprintf("?before=%.0f",before) : "");
	tsb_req = Online_NextReq(); tsb_at = cltime;
	if (!uri_get(url,tsb_req))
	{
		tsb_req = 0; tsb_note = TASShare_Keep(tsb_note,"The request could not start. Refresh to retry.");
	}
};
float(float reqid, float code, string body) TASShare_Reply =
{
	local int root, rows, item, part;
	local float valid, i, n, last;
	if (!tsb_req || reqid != tsb_req) return FALSE;
	tsb_req = 0;
	tsb_note = TASShare_Keep(tsb_note,"The TAS directory returned unavailable or invalid data. Refresh to retry.");
	if (code || strcmp(tsb_map,serverkey("map"))) return TRUE;
	if (strlen(body) > 1048576)
	{
		if (tsb_selected) tsb_note = TASShare_Keep(tsb_note,"Credit history exceeds this view's 1 MiB limit. The selected revision can still be opened as TAS.");
		return TRUE;
	}
	root = json_parse(body);
	if (root <= 0i) return TRUE;
	valid = (json_get_float(json_find_object_child(root,"ok")) == 1);
	if (!tsb_kind)
	{
		rows = json_find_object_child(root,"revisions");
		valid = (valid && !strcmp(json_get_string(json_find_object_child(root,"map")),tsb_map) &&
			json_get_value_type(rows) == 3i && json_get_length(rows) <= 100i);
		n = json_get_length(rows); last = 16777216;
		if (tsb_before) last = tsb_before;
		for (i = 0; i < n && valid; i = i + 1)
		{
			item = json_get_child_at_index(rows,(int)i);
			part = json_find_object_child(item,"seq");
			valid = (TASShare_Hex(json_get_string(json_find_object_child(item,"sha"))) &&
				json_get_value_type(part) == 1i && json_get_float(part) >= 1 && json_get_float(part) < last && floor(json_get_float(part)) == json_get_float(part));
			last = json_get_float(part);
		}
		if (valid) { tsb_root = root; tsb_have = TRUE; }
	}
	else
	{
		item = json_find_object_child(root,"revision");
		rows = json_find_object_child(root,"credit");
		valid = (valid && !strcmp(json_get_string(json_find_object_child(item,"sha")),tsb_sha) &&
			!strcmp(json_get_string(json_find_object_child(item,"map")),tsb_map) && json_get_value_type(rows) == 3i);
		n = json_get_length(rows);
		if (valid && n > 4096)
		{
			json_free(root);
			tsb_note = TASShare_Keep(tsb_note,"Credit history exceeds this view's 4096-range limit. The selected revision can still be opened as TAS.");
			return TRUE;
		}
		last = -1;
		for (i = 0; i < n && valid; i = i + 1)
		{
			part = json_get_child_at_index(rows,(int)i);
			valid = (json_get_value_type(part) == 3i && json_get_length(part) == 3i);
			valid = (valid && json_get_value_type(json_get_child_at_index(part,0i)) == 1i &&
				json_get_value_type(json_get_child_at_index(part,1i)) == 1i &&
				json_get_float(json_get_child_at_index(part,0i)) >= 1 &&
				floor(json_get_float(json_get_child_at_index(part,0i))) == json_get_float(json_get_child_at_index(part,0i)) &&
				floor(json_get_float(json_get_child_at_index(part,1i))) == json_get_float(json_get_child_at_index(part,1i)) &&
				json_get_float(json_get_child_at_index(part,0i)) > last &&
				json_get_float(json_get_child_at_index(part,1i)) >= json_get_float(json_get_child_at_index(part,0i)) &&
				json_get_float(json_get_child_at_index(part,1i)) <= 16777215 &&
				json_get_value_type(json_get_child_at_index(part,2i)) == 0i /* string; 2 is object */);
			last = json_get_float(json_get_child_at_index(part,1i));
		}
		if (valid) { tsb_info = root; tsb_detail = TRUE; }
	}
	if (!valid) { json_free(root); return TRUE; }
	tsb_note = TASShare_Keep(tsb_note,"Public project history; sharing or credit is NOT verification of a TAS time.");
	return TRUE;
};
void(float index) TASShare_Select =
{
	local int rows, item;
	local string sha;
	if (!tsb_have || index < 0 || floor(index) != index) return;
	if (strcmp(tsb_map,serverkey("map"))) { TASShare_Reset(); return; }
	rows = json_find_object_child(tsb_root,"revisions");
	if (index >= json_get_length(rows)) return;
	item = json_get_child_at_index(rows,(int)index);
	sha = strzone(json_get_string(json_find_object_child(item,"sha")));
	TASShare_Request(0,sha);
	// Selection is bound by the validated map list, not by loading every
	// contribution range. Download acceptance remains the strict server reader.
	if (!strcmp(tsb_sha,sha) && !strcmp(tsb_map,serverkey("map"))) tsb_selected = TRUE;
	strunzone(sha);
};
void() TASShare_Open =
{
	if (!TASShare_Allowed() || !TASShare_Hex(tsb_sha) || !tsb_selected) return;
	if (strcmp(tsb_map,serverkey("map"))) { TASShare_Reset(); return; }
	if (!isserver()) { print("tas open: host this map locally first\n"); return; }
	localcmd(sprintf("tas project open %s\n",tsb_sha));
};
void(vector at, float width, float tsz, float hint, float row) TASShare_Draw =
{
	local float i, n;
	local int rows, item;
	local string label, who;
	local vector chip;
	chip = [(width-12)/3,row,0];
	if (Profile_Chip("tsh_refresh",at,chip,"Refresh",tsz,FALSE)) TASShare_Request(0,"");
	if (Profile_Chip("tsh_share",at+[(width+6)/3,0,0],chip,tsb_confirm > cltime ? "Confirm public share" : "Share saved revision",hint,FALSE))
	{
		if (tsb_confirm > cltime) { tsb_confirm = 0; localcmd("tas project share yes\n"); }
		else tsb_confirm = cltime + 8;
	}
	if (Profile_Chip("tsh_open",at+[(width+6)*2/3,0,0],chip,"Open selected as TAS",hint,FALSE)) TASShare_Open();
	at_y = at_y + row + hint;
	label = tsb_note;
	if (tsb_confirm > cltime) label = "PUBLIC: saved project, metadata and existing signatures. Sign first for credit.";
	if (tsb_req && cltime - tsb_at >= 12) label = "Directory timed out. Refresh to retry.";
	sui_text(at,[hint,hint],label,SUI_THEME_DIM,1,0); at_y = at_y + hint*2.5;
	if (tsb_selected)
	{
		sui_text(at,[hint,hint],strcat("Revision ",substring(tsb_sha,0,16)),SUI_THEME_TEXT,1,0); at_y = at_y + row;
		if (!tsb_detail) return;
		label = json_get_float(json_find_object_child(tsb_info,"pending")) ? "Credit is still being resolved." : "Contribution ranges (unknown/unsigned stays uncredited):";
		sui_text(at,[hint,hint],label,SUI_THEME_DIM,1,0); at_y = at_y + row;
		rows = json_find_object_child(tsb_info,"credit"); n = json_get_length(rows);
		for (i = tsb_creditoffset; i < min(n,tsb_creditoffset+10); i = i + 1)
		{
			item = json_get_child_at_index(rows,(int)i);
			who = substring(json_get_string(json_get_child_at_index(item,2i)),0,64);
			who = strreplace("^","",strreplace("\n"," ",strreplace("\r"," ",who)));
			sui_text(at,[hint,hint],sprintf("%.0f..%.0f  %s",json_get_float(json_get_child_at_index(item,0i)),
				json_get_float(json_get_child_at_index(item,1i)),who),SUI_THEME_TEXT,1,0); at_y = at_y + row;
		}
		if (Profile_Chip("tsh_prevcredit",at,chip,"Earlier ranges",hint,FALSE)) tsb_creditoffset = max(0,tsb_creditoffset-10);
		if (Profile_Chip("tsh_nextcredit",at+[(width+6)/3,0,0],chip,"Later ranges",hint,FALSE))
			if (tsb_creditoffset+10 < n) tsb_creditoffset = tsb_creditoffset+10;
		return;
	}
	if (!tsb_have) return;
	rows = json_find_object_child(tsb_root,"revisions"); n = json_get_length(rows);
	if (!n) sui_text(at,[hint,hint],"No shared revisions for this map yet.",SUI_THEME_DIM,1,0);
	for (i = tsb_offset; i < min(n,tsb_offset+10); i = i + 1)
	{
		item = json_get_child_at_index(rows,(int)i);
		label = sprintf("%s  ticks %.0f..%.0f  %.0f linked signers",substring(json_get_string(json_find_object_child(item,"sha")),0,12),
			json_get_float(json_find_object_child(item,"base")),json_get_float(json_find_object_child(item,"head")),
			json_get_float(json_find_object_child(item,"signers")));
		if (Profile_Chip(sprintf("tsh_row%.0f",i),at,[width,row,0],label,hint,FALSE)) { TASShare_Select(i); return; }
		at_y = at_y + row + 2;
	}
	if (Profile_Chip("tsh_prev",at,chip,"Previous rows",hint,FALSE)) tsb_offset = max(0,tsb_offset-10);
	if (Profile_Chip("tsh_next",at+[(width+6)/3,0,0],chip,"More rows",hint,FALSE))
	{
		if (tsb_offset+10 < n) tsb_offset = tsb_offset+10;
		else if (n == 100)
		{
			item = json_get_child_at_index(rows,99i);
			TASShare_Request(json_get_float(json_find_object_child(item,"seq")),"");
		}
	}
};
float(float argc, float seat) TASShare_ConsoleCommand =
{
	local string op, sha, name;
	op = argv(2); sha = argv(3); name = argv(4);
	if (seat || numclientseats > 1) { print("tas shared: one local seat only\n"); return TRUE; }
	if (!strcmp(argv(1),"shared"))
	{
		if (!strcmp(op,"status"))
		{
			print(sprintf("tas shared: map %s list %.0f detail %.0f request %.0f selected %.0f\n",tsb_map,tsb_have,tsb_detail,tsb_req,tsb_selected));
			print("tas shared: endpoint ",TASShare_URL(),"\n"); return TRUE;
		}
		if (!strcmp(op,"select") && argc == 4)
		{
			if (!strcmp(sha,ftos(stof(sha)))) TASShare_Select(stof(sha));
			return TRUE;
		}
		if (!strcmp(op,"open") && argc == 3) { TASShare_Open(); return TRUE; }
		if (argc > 2 && (argc != 3 || strcmp(op,"refresh")))
		{
			print("tas shared [refresh|status|select <row>|open]\n"); return TRUE;
		}
		TASShare_Request(0,"");
		if (!tasu_open) TASUI_Toggle(seat);
		tasu_tab = 2; return TRUE;
	}
	if (!TASShare_Allowed()) return TRUE;
	if (!isserver()) { print("tas share/open: host this game locally first\n"); return TRUE; }
	if (!strcmp(op,"share"))
	{
		if (argc == 4 && !strcmp(sha,"yes")) localcmd("p1 cmd tas project share yes\n");
		else if (argc == 5 && !strcmp(sha,"yes") && TASShare_Hex(name))
			localcmd(sprintf("p1 cmd tas project share yes %s\n",name));
		else print("tas project share yes [retained-hash]: public project metadata and existing signatures; sign first for credit. No private keys.\n");
		return TRUE;
	}
	if (argc < 4 || argc > 5 || !TASShare_Hex(sha)) { print("tas project open <64 lowercase hexadecimal digits> [new-name]\n"); return TRUE; }
	// Project console's ordinary name filter is deliberately retained.
	localcmd(sprintf("p1 cmd tas project open %s%s\n",sha,!strcmp(name,"") ? "" : strcat(" ",name)));
	return TRUE;
};
