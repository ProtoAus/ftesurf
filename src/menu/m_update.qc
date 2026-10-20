// FTESurf's updater and launcher share one signed feed, ledger and permission.
// No HTTP before explicit update consent. The server cannot set these engine cvars.
// Menu-only engine capability; intentionally absent from server-supplied CSQC.
// P823: no Updates screen. Play online on the terms turns the permission on
// (ui_tm_answer); the title menu's corner shows the state and turns it off or on.
float(float action) gameupdate = #0;
float(float action) MU_Action =
{
	if (checkbuiltin(gameupdate)) return gameupdate(action);
	print("Updates need the latest engine; start World of Surf through its launcher.\n");
	return FALSE;
};

float mu_checked;
float mu_lastcheck;
float mu_apply_sent;
// The menu identifies its own compiled version, not an unverified install ledger.
#ifndef UI_MENU_VERSION
#define UI_MENU_VERSION "development"
#endif

/*
  P876: patch notes. patchnotes.json sits beside update.json (PATCHNOTES.md, rendered
  by release.ps1) and is asked only under the update permission. The title menu shows
  it while an update is pending, once after one installs (until Close sets
  ui_notes_seen), and from the corner's Patch notes button. mpn_items holds the reply
  as "R<version> <date>", "PP<n> <title>", "B<point>"; mpn_lines the same wrapped to
  the panel, the first character the kind (G gap, Q/C a title's/point's next line).
*/
#define MPN_URL      "https://proto.bar/ftesurf/patchnotes.json"
#define MPN_MAXLEN   262144
#define MPN_MAXREL   12
#define MPN_MAXITEM  2000
#define MPN_MAXLINE  4000
#define MPN_WAIT     15
#define MPN_RETRY    120
#define MPN_ROW      22
#define MPN_INDENT   18
#define MPN_SZ       '16 16 0'

#define MPNS_NONE    0
#define MPNS_ASKED   1
#define MPNS_OK      2
#define MPNS_FAIL    3

strbuf mpn_items, mpn_lines;
float  mpn_state, mpn_req, mpn_sent, mpn_next, mpn_wrapw, mpn_hascur;
float  mpn_open, mpn_closed, mpn_shown;
vector mpn_scroll;
string mpn_forver;
float  mu_foot;                 // where MU_Status's corner ends; the panel starts under it

void() MU_Init =
{
	registercvar("ui_release_version", "", 0);
	registercvar("ui_notes_seen", "", 32);
	mu_checked = FALSE;
	mu_apply_sent = FALSE;
	mu_lastcheck = 0;
	mpn_items = buf_create();
	mpn_lines = buf_create();
};

// The permission, from the terms answer or the corner's button; a new "on" checks at once.
void(float on) MU_Consent =
{
	if (MU_Action(on ? 4 : 5) && on)
		mu_checked = FALSE;
};

float(string st) MU_Pending =
{
	return (!strcmp(st, "available") || !strcmp(st, "downloading") || !strcmp(st, "applying") ||
	        !strcmp(st, "restart") || !strcmp(st, "launcher"));
};

// An update waiting, or the installed release's notes not yet closed.
float(string st) MU_NotesAuto =
{
	local string cur;
	if (MU_Pending(st))
		return TRUE;
	cur = cvar_string("ui_release_version");
	return (cur != "" && strcmp(cur, cvar_string("ui_notes_seen")) != 0);
};

float() MU_NotesShown =
{
	local string st;
	if (menu_screen != SCREEN_MAIN || cvar("update_consent") != 1)
		return FALSE;
	if (mpn_open)
		return TRUE;
	if (mpn_closed || mpn_state != MPNS_OK)
		return FALSE;
	st = cvar_string("update_state");
	if (MU_Pending(st))
		return TRUE;
	return (MU_NotesAuto(st) && mpn_hascur);
};

// Beside the updater's update.json, under its https rule; else the public copy.
string() MU_NotesUrl =
{
	local string m;
	local float n;
	m = cvar_string("update_manifest_url");
	n = strlen(m);
	if (n > 12 && !strcmp(substring(m, n - 12, 12), "/update.json"))
		m = strcat(substring(m, 0, n - 12), "/patchnotes.json");
	else
		m = MPN_URL;
	if (strcmp(substring(m, 0, 8), "https://") && !cvar("update_allow_insecure"))
		return "";
	return m;
};

// Once while something would show it, again when the feed names a new version.
void(string st) MU_NotesAsk =
{
	local string url;
	if (mpn_req)
	{
		if (time - mpn_sent > MPN_WAIT)
		{
			mpn_req = 0;
			if (mpn_state != MPNS_OK) mpn_state = MPNS_FAIL;
			print("^5notes:^7 no answer in 15 s\n");
		}
		return;
	}
	if (!mpn_open && !MU_NotesAuto(st))
		return;
	if (mpn_state == MPNS_OK && !strcmp(mpn_forver, cvar_string("update_version")))
		return;
	if (time < mpn_next)
		return;
	url = MU_NotesUrl();
	if (url == "")
		return;
	if (mpn_forver != "") strunzone(mpn_forver);
	mpn_forver = strzone(cvar_string("update_version"));
	mpn_next = time + MPN_RETRY;
	mpn_sent = time;
	mpn_req = Lob_NextReq();
	if (!uri_get(url, mpn_req))
	{
		mpn_req = 0;
		if (mpn_state != MPNS_OK) mpn_state = MPNS_FAIL;
		return;
	}
	if (mpn_state != MPNS_OK) mpn_state = MPNS_ASKED;
	print(sprintf("^5notes:^7 asking %s (id %g)\n", url, mpn_req));
};

// One line of plain text from the reply: no colour codes, at most n characters.
string(int node, float n) MU_NotesText =
{
	return strreplace("\n", " ", strreplace("^", "", substring(json_get_string(node), 0, n)));
};

string(string d) MU_NotesDate =
{
	if (tokenizebyseparator(d, "-") != 3)
		return d;
	return sprintf("%g %s %s", stof(argv(2)),
	               substring("JanFebMarAprMayJunJulAugSepOctNovDec", (bound(1, stof(argv(1)), 12) - 1) * 3, 3), argv(0));
};

// From URI_Get_Callback.  TRUE when the id was this request's.
float(float reqid, float code, string body) MU_NotesReply =
{
	local int root, rels, rel, pats, pat, pts;
	local float i, j, k, nr, np, nk, len;
	local string v;

	if (!mpn_req)
		return FALSE;
	if (reqid != mpn_req)
		return FALSE;
	mpn_req = 0;
	len = strlen(body);
	root = 0;
	if (!code && len > 0 && len <= MPN_MAXLEN)
		root = json_parse(body);
	if (root)
	if (json_get_float(json_find_object_child(root, "format")) != 1)
	{
		json_free(root);
		root = 0;
	}
	if (!root)
	{
		if (mpn_state != MPNS_OK) mpn_state = MPNS_FAIL;
		print(sprintf("^5notes:^7 not loaded (answer %g, %g bytes)\n", code, len));
		return TRUE;
	}
	buf_del(mpn_items);
	mpn_items = buf_create();
	mpn_hascur = FALSE;
	rels = json_find_object_child(root, "releases");
	nr = json_get_length(rels);
	if (nr > MPN_MAXREL)
		nr = MPN_MAXREL;
	for (i = 0; i < nr; i++)
	{
		rel = json_get_child_at_index(rels, i);
		v = MU_NotesText(json_find_object_child(rel, "version"), 16);
		if (!strcmp(v, cvar_string("ui_release_version")))
			mpn_hascur = TRUE;
		bufstr_add(mpn_items, strcat("R", v, " ", MU_NotesDate(MU_NotesText(json_find_object_child(rel, "date"), 10))), TRUE);
		pats = json_find_object_child(rel, "patches");
		np = json_get_length(pats);
		for (j = 0; j < np && buf_getsize(mpn_items) < MPN_MAXITEM; j++)
		{
			pat = json_get_child_at_index(pats, j);
			bufstr_add(mpn_items, sprintf("PP%g %s", json_get_float(json_find_object_child(pat, "patch")),
			                              MU_NotesText(json_find_object_child(pat, "title"), 80)), TRUE);
			pts = json_find_object_child(pat, "points");
			nk = json_get_length(pts);
			for (k = 0; k < nk && buf_getsize(mpn_items) < MPN_MAXITEM; k++)
				bufstr_add(mpn_items, strcat("B", MU_NotesText(json_get_child_at_index(pts, k), 250)), TRUE);
		}
	}
	json_free(root);
	mpn_state = MPNS_OK;
	mpn_wrapw = 0;
	print(sprintf("^5notes:^7 %g releases, %g items; installed %s listed %g\n", nr, buf_getsize(mpn_items),
	              cvar_string("ui_release_version"), mpn_hascur));
	return TRUE;
};

// `text` word-wrapped to w px onto mpn_lines: the first line as kind, the rest as more.
void(string kind, string more, string text, float w) MU_NotesWrapOne =
{
	local float n, i;
	local string line, next;
	n = tokenizebyseparator(text, " ");
	line = "";
	for (i = 0; i < n; i++)
	{
		next = (line == "") ? argv(i) : strcat(line, " ", argv(i));
		if (line != "")
		if (stringwidth(next, TRUE, MPN_SZ) > w)
		{
			bufstr_add(mpn_lines, strcat(kind, line), TRUE);
			kind = more;
			next = argv(i);
		}
		line = next;
	}
	if (line != "")
		bufstr_add(mpn_lines, strcat(kind, line), TRUE);
};

void(float w) MU_NotesWrap =
{
	local float i, n;
	local string it, k;
	buf_del(mpn_lines);
	mpn_lines = buf_create();
	mpn_wrapw = w;
	n = buf_getsize(mpn_items);
	for (i = 0; i < n && buf_getsize(mpn_lines) < MPN_MAXLINE; i++)
	{
		it = bufstr_get(mpn_items, i);
		k = substring(it, 0, 1);
		if (!strcmp(k, "R"))
		{
			if (i) bufstr_add(mpn_lines, "G", TRUE);
			bufstr_add(mpn_lines, it, TRUE);
		}
		else if (!strcmp(k, "P"))
			MU_NotesWrapOne("P", "Q", substring(it, 1, -1), w);
		else
			MU_NotesWrapOne("B", "C", substring(it, 1, -1), w - MPN_INDENT);
	}
};

// "0.1.29" as one number, for NEW and INSTALLED; 0 when it is not a version.
float(string v) MU_VerNum =
{
	if (tokenizebyseparator(v, ".") != 3)
		return 0;
	return stof(argv(0)) * 1000000 + stof(argv(1)) * 1000 + stof(argv(2));
};

void() MU_NotesClose =
{
	local string cur;
	mpn_open = FALSE;
	mpn_closed = TRUE;
	cur = cvar_string("ui_release_version");
	if (cur != "")
		MM_Seta("ui_notes_seen", cur);
};

// The panel down the right, under the corner; MPN_ROW rows in a list view.
void(vector screensize) MU_Notes =
{
	local vector pos, rp;
	local float w, h, i, bw, cur, vn, sp;
	local string ln, k, t, title, tag, st;

	mpn_shown = MU_NotesShown();
	if (!mpn_shown)
		return;
	Font_Set(ui_font_ui);
	w = min(440, floor(screensize_x * 0.34));
	pos = [screensize_x - 16 - w, mu_foot + 12];
	h = screensize_y - pos_y - 24;
	if (w < 260 || h < 180)
		return;
	sui_style_box(pos, [w, h], 9, SUI_THEME_WELL, SUI_THEME_EDGE, 0.94);

	st = cvar_string("update_state");
	cur = MU_VerNum(cvar_string("ui_release_version"));
	if (MU_Pending(st) && cvar_string("update_version") != "")
		title = strcat("Update ", cvar_string("update_version"));
	else if (MU_NotesAuto(st) && mpn_hascur)
		title = strcat("What's new in ", cvar_string("ui_release_version"));
	else
		title = "Patch notes";
	bw = stringwidth("Close", TRUE, SZ_LABEL) + 28;
	if (ui_button("mpn_close", [pos_x + w - 10 - bw, pos_y + 9], [bw, 28], "Close"))
	{
		MU_NotesClose();
		return;
	}
	sui_text([pos_x + 16, pos_y + 14], '20 20 0', ui_fit_text(title, w - bw - 40, '20 20 0'), COL_ACCENT, 1, 0);
	sui_fill([pos_x + 1, pos_y + 46], [w - 2, 1], SUI_THEME_EDGE, 1, 0);

	if (mpn_state != MPNS_OK)
	{
		sui_text([pos_x + 16, pos_y + 60], MPN_SZ, (mpn_state == MPNS_FAIL) ? "The patch notes could not be loaded." : "Loading the patch notes...", COL_DIM, 1, 0);
		return;
	}
	if (mpn_wrapw != w - 48)
		MU_NotesWrap(w - 48);
	sui_list_view_begin("mpn_list", [pos_x + 16, pos_y + 54], [w - 22, h - 62], [w - 32, MPN_ROW],
	                    buf_getsize(mpn_lines), mpn_scroll, [0, 10]);
	rp = '0 0 0';
	for (i = sui_list_item(rp); i > -1; i = sui_list_item(rp))
	{
		ln = bufstr_get(mpn_lines, i);
		k = substring(ln, 0, 1);
		t = substring(ln, 1, -1);
		if (!strcmp(k, "R"))
		{
			sp = strstrofs(t, " ", 0);
			vn = MU_VerNum(substring(t, 0, sp));
			sui_text(rp + '0 1 0', '20 20 0', substring(t, 0, sp), COL_TEXT, 1, 0);
			sui_text(rp + [stringwidth(substring(t, 0, sp), TRUE, '20 20 0') + 10, 7], '12 12 0', substring(t, sp + 1, -1), COL_DIM, 1, 0);
			tag = "";
			if (cur > 0 && vn > cur) tag = "NEW";
			else if (cur > 0 && vn == cur) tag = "INSTALLED";
			if (tag != "")
				sui_text(rp + [w - 48 - stringwidth(tag, TRUE, '12 12 0'), 7], '12 12 0', tag, (vn > cur) ? COL_ACCENT : COL_DIM, 1, 0);
		}
		else if (!strcmp(k, "P"))
		{
			if (i > 0)
			if (strcmp(substring(bufstr_get(mpn_lines, i - 1), 0, 1), "R"))
				sui_fill(rp + '0 1 0', [w - 48, 1], SUI_THEME_EDGE, 0.6, 0);
			sp = strstrofs(t, " ", 0);
			sui_text(rp + '0 6 0', '12 12 0', substring(t, 0, sp), COL_DIM, 1, 0);
			sui_text(rp + [stringwidth(substring(t, 0, sp), TRUE, '12 12 0') + 6, 3], MPN_SZ, substring(t, sp + 1, -1), COL_ACCENT, 1, 0);
		}
		else if (!strcmp(k, "Q"))
			sui_text(rp + '0 3 0', MPN_SZ, t, COL_ACCENT, 1, 0);
		else if (!strcmp(k, "B") || !strcmp(k, "C"))
		{
			if (!strcmp(k, "B"))
				sui_fill(rp + '3 10 0', '6 2 0', COL_ACCENT, 0.9, 0);
			sui_text(rp + [MPN_INDENT, 3], MPN_SZ, t, COL_TEXT, 0.9, 0);
		}
	}
	sui_list_view_end();
};

void() MU_Poll =
{
	local string st;
	if (cvar("ui_bootcheck")) return;
	if (ms_consent < FS_TERMS_VERSION) return;
	if (cvar("update_consent") != 1) return;
	st = cvar_string("update_state");
	MU_NotesAsk(st);
	if (!mu_checked)
	{
		mu_checked = TRUE;
		mu_lastcheck = time;
		MU_Action(0);
		return;
	}
	// A long-running session sees new releases when it returns to the title menu.
	if (menu_screen == SCREEN_MAIN && clientstate() == 1)
	if (time - mu_lastcheck > 600)
	if (strcmp(st, "uptodate") == 0 || strcmp(st, "idle") == 0 || strcmp(st, "error") == 0)
	{
		mu_lastcheck = time;
		MU_Action(1);
	}
	if (strcmp(st, "available") != 0) mu_apply_sent = FALSE;
	// Never swap code during a run, join or local listen session.
	if (strcmp(st, "available") == 0 && clientstate() == 1 && !mu_apply_sent)
	if (menu_screen == SCREEN_MAIN)
	{
		mu_apply_sent = TRUE;
		MU_Action(2);
	}
};

void(float right, float y, float width, vector size, string text, vector color) MU_StatusLine =
{
	text = ui_fit_text(text, width, size);
	sui_text([right - stringwidth(text, TRUE, size), y], size, text, color, 1, 0);
};

void(vector screensize) MU_Status =
{
	local string st, label, latest, current, err, word;
	local float w, right, consent, bw, x, y;
	st = cvar_string("update_state");
	consent = cvar("update_consent");
	current = cvar_string("ui_release_version");
	if (current == "") current = strcat(UI_MENU_VERSION, " (dev)");
	latest = cvar_string("update_version");
	if (latest == "") latest = "not checked";
	label = "Updates";
	if (consent != 1) label = "Updates off";
	else if (strcmp(st, "checking") == 0) label = "Checking for updates";
	else if (strcmp(st, "uptodate") == 0) label = "Up to date";
	else if (strcmp(st, "downloading") == 0 || strcmp(st, "applying") == 0) label = "Updating...";
	else if (strcmp(st, "available") == 0) label = "Update available";
	else if (strcmp(st, "restart") == 0) label = "Update ready";
	else if (strcmp(st, "launcher") == 0) label = "Update needs the launcher";
	else if (strcmp(st, "error") == 0) label = "Update check unavailable";
	w = min(320, screensize_x - 32);
	right = screensize_x - 16;
	Font_Set(ui_font_ui);
	MU_StatusLine(right, 16, w, SZ_LABEL, label, COL_ACCENT);
	MU_StatusLine(right, 38, w, '12 12 0', strcat("Your version: ", current), COL_TEXT);
	MU_StatusLine(right, 58, w, '12 12 0', strcat("Latest: ", latest), COL_DIM);
	// The Updates screen's message line: a failed check, restart or launcher handoff says why.
	err = "";
	if (consent == 1)
	if (strcmp(st, "error") == 0 || strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0)
		err = cvar_string("update_error");
	y = 82;
	if (strlen(err))
	{
		// Wrapped when long, as the screen did: the actionable part (a URL, the retry) comes last.
		if (stringwidth(err, TRUE, '12 12 0') <= w)
		{
			MU_StatusLine(right, 78, w, '12 12 0', err, SUI_THEME_WARN);
			y = 100;
		}
		else
			y = 78 + ui_para([right - w, 78], w, '12 12 0', 15, err, SUI_THEME_WARN, TRUE) + 6;
	}
	mu_foot = y + 28;
	if (menu_screen != SCREEN_MAIN)
		return;
	// Right to left: the switch, then what the state asks for. The switch is the old
	// screen's Disable, which earlier terms promised; turning on needs online terms.
	x = right;
	if (consent == 1)
	{
		bw = stringwidth("Turn off updates", TRUE, SZ_LABEL) + 28;
		x = x - bw;
		if (ui_button("mu_disable", [x, y], [bw, 28], "Turn off updates"))
			MU_Consent(FALSE);
		x = x - 8;
	}
	else if (ms_consent >= FS_TERMS_ONLINE)
	{
		bw = stringwidth("Turn on updates", TRUE, SZ_LABEL) + 28;
		x = x - bw;
		if (ui_button("mu_enable", [x, y], [bw, 28], "Turn on updates"))
		{
			if (ui_synth())
				print("menu: updates are turned on by a real click or key, not ui_key/ui_click\n");
			else
				MU_Consent(TRUE);
		}
	}
	if (consent != 1)
		return;
	word = "";
	if (clientstate() == 1)
	if (strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0)
		word = (strcmp(st, "launcher") == 0) ? "Restart through launcher" : "Restart to update";
	if (strlen(word))
	{
		bw = stringwidth(word, TRUE, SZ_LABEL) + 28;
		x = x - bw;
		if (ui_button("mu_restart", [x, y], [bw, 28], word, TRUE))
			MU_Action(6);
		x = x - 8;
	}
	else if (strcmp(st, "error") == 0)
	{
		bw = stringwidth("Check again", TRUE, SZ_LABEL) + 28;
		x = x - bw;
		if (ui_button("mu_check", [x, y], [bw, 28], "Check again"))
			MU_Action(1);
		x = x - 8;
	}
	// P876: the notes again after a Close, or before anything showed them.
	if (!mpn_shown)
	if (MU_NotesUrl() != "")
	{
		bw = stringwidth("Patch notes", TRUE, SZ_LABEL) + 28;
		if (ui_button("mu_notes", [x - bw, y], [bw, 28], "Patch notes"))
		{
			mpn_open = TRUE;
			mpn_closed = FALSE;
			mpn_scroll = '0 0 0';
		}
	}
};

// ui_notes status|open|close|scroll <px>: the harness's handle on the panel.
void(string what) MU_NotesCommand =
{
	if (!strcmp(what, "open"))
	{
		mpn_open = TRUE;
		mpn_closed = FALSE;
	}
	else if (!strcmp(what, "close"))
		MU_NotesClose();
	else if (!strcmp(what, "scroll"))
		mpn_scroll_y = stof(argv(2));
	print(sprintf("ui_notes: state %g shown %g items %g lines %g wrap %g scroll %g\n",
	              mpn_state, mpn_shown, buf_getsize(mpn_items), buf_getsize(mpn_lines), mpn_wrapw, mpn_scroll_y));
	print(sprintf("ui_notes: installed %s listed %g seen %s url %s\n",
	              cvar_string("ui_release_version"), mpn_hascur, cvar_string("ui_notes_seen"), MU_NotesUrl()));
};
