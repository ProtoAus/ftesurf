// FTESurf's updater and launcher share one signed feed, ledger and permission.
// No HTTP before explicit update consent. The server cannot set these engine cvars.
// Menu-only engine capability; intentionally absent from server-supplied CSQC.
// P823: no Updates screen. Play online on the terms turns the permission on
// (ui_tm_answer); F2's Updates page shows the state and turns it off or on (P902).
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
float mu_live;                  // gameupdate answered: this is FTESurf's updater (QKU_MenuAction)
// The menu identifies its own compiled version, not an unverified install ledger.
#ifndef UI_MENU_VERSION
#define UI_MENU_VERSION "development"
#endif

/*
  P876: patch notes. patchnotes.json sits beside update.json (PATCHNOTES.md, rendered
  by release.ps1) and is asked only where the updater itself would ask (MU_NotesCan).
  P902 (Lex): no panel or buttons on the title screen any more -- the notes, the
  updater's state and switch, the input journal and the terms are all in F2
  (screen_journal), and the notes are asked only while F2 is up. mpn_items holds the
  reply as "R<version> <date>", "PP<n> <title>", "B<point>"; mpn_lines the same wrapped
  to the column, the first character the kind (G gap, Q/C a title's/point's next line).
*/
#define MPN_MAXLEN   262144
#define MPN_MAXREL   12
#define MPN_MAXITEM  2000
#define MPN_MAXLINE  4000
#define MPN_WAIT     15
#define MPN_RETRY    600         // the updater's own re-check interval
#define MPN_ROW      22
#define MPN_INDENT   18
#define MPN_SZ       '16 16 0'

#define MPNS_NONE    0
#define MPNS_ASKED   1
#define MPNS_OK      2
#define MPNS_FAIL    3

strbuf mpn_items, mpn_lines, mpn_releases;
float  mpn_state, mpn_req, mpn_sent, mpn_next, mpn_wrapw, mpn_hascur, mpn_selected;
vector mpn_scroll, mpn_versions_scroll;
string mpn_forver, mpn_askver; // update_version at the last good reply / the ask in flight

void() MU_Init =
{
	registercvar("ui_release_version", "", 0);
	mu_checked = FALSE;
	mu_apply_sent = FALSE;
	mu_lastcheck = 0;
	mpn_items = buf_create();
	mpn_lines = buf_create();
	mpn_releases = buf_create();
};

// The permission, from the terms answer or F2's Updates page; a new "on" checks at once.
void(float on) MU_Consent =
{
	if (MU_Action(on ? 4 : 5) && on)
		mu_checked = FALSE;
};

string() MU_NotesUrl;

// Where the updater itself would ask: FTESurf's, on, and allowed.
float() MU_NotesCan =
{
	if (!mu_live || !cvar("update_enabled") || cvar("update_consent") != 1)
		return FALSE;
	return (MU_NotesUrl() != "");
};

// Beside the updater's update.json, under its https rule; "" when the feed is not one.
string() MU_NotesUrl =
{
	local string m;
	local float n;
	m = cvar_string("update_manifest_url");
	n = strlen(m);
	if (n <= 12 || strcmp(substring(m, n - 12, 12), "/update.json"))
		return "";
	m = strcat(substring(m, 0, n - 12), "/patchnotes.json");
	if (strcmp(substring(m, 0, 8), "https://") && !cvar("update_allow_insecure"))
		return "";
	return m;
};

// Once while the Patch notes page is up, again when the feed names a new version.
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
	if (!MU_NotesCan())
		return;
	if (menu_screen != SCREEN_JOURNAL || ui_f2_tab != 0)   // P902: only on F2's Patch notes page
		return;
	if (mpn_state == MPNS_OK && !strcmp(mpn_forver, cvar_string("update_version")))
		return;
	if (time < mpn_next)
		return;
	url = MU_NotesUrl();
	if (url == "")
		return;
	if (mpn_askver != "") strunzone(mpn_askver);
	mpn_askver = (cvar_string("update_version") == "") ? "" : strzone(cvar_string("update_version"));
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
	buf_del(mpn_releases);
	mpn_releases = buf_create();
	mpn_hascur = FALSE;
	mpn_selected = 0;
	mpn_scroll = '0 0 0';
	rels = json_find_object_child(root, "releases");
	nr = json_get_length(rels);
	if (nr > MPN_MAXREL)
		nr = MPN_MAXREL;
	for (i = 0; i < nr; i++)
	{
		rel = json_get_child_at_index(rels, i);
		v = MU_NotesText(json_find_object_child(rel, "version"), 16);
		if (!strcmp(v, cvar_string("ui_release_version")))
		{
			mpn_hascur = TRUE;
			mpn_selected = buf_getsize(mpn_releases);
		}
		bufstr_add(mpn_releases, v, TRUE);
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
	if (mpn_forver != "") strunzone(mpn_forver);
	mpn_forver = (mpn_askver == "") ? "" : strzone(mpn_askver);
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
	local float i, n, release;
	local string it, k;
	buf_del(mpn_lines);
	mpn_lines = buf_create();
	mpn_wrapw = w;
	n = buf_getsize(mpn_items);
	release = -1;
	for (i = 0; i < n && buf_getsize(mpn_lines) < MPN_MAXLINE; i++)
	{
		it = bufstr_get(mpn_items, i);
		k = substring(it, 0, 1);
		if (!strcmp(k, "R")) release = release + 1;
		if (release != mpn_selected) continue;
		if (!strcmp(k, "R"))
			bufstr_add(mpn_lines, it, TRUE);
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

void(float release) MU_NotesSelect =
{
	release = bound(0, release, max(0, buf_getsize(mpn_releases) - 1));
	if (release == mpn_selected) return;
	mpn_selected = release;
	mpn_wrapw = 0;
	mpn_scroll = '0 0 0';
};

// A separate version list leaves only the selected release in the reading pane.
void(vector pos, vector size) MU_NotesAt =
{
	local vector rp;
	local float iw, i, cur, vn, sp, sidebar;
	local string ln, k, t, tag;

	Font_Set(ui_font_ui);
	if (!MU_NotesCan())
	{
		ui_para(pos, size_x, SZ_LABEL, 20, (cvar("update_consent") == 1) ? "This build does not use the update server, so it has no patch notes."
		        : "The patch notes come with the updates: turn them on in the Updates page to see what each one changes.", COL_DIM, TRUE);
		return;
	}
	if (mpn_state != MPNS_OK)
	{
		sui_text(pos, MPN_SZ, (mpn_state == MPNS_FAIL) ? "The patch notes could not be loaded." : "Loading the patch notes...", COL_DIM, 1, 0);
		if (mpn_state == MPNS_FAIL)
		if (ui_button("mpn_retry", pos + '0 28 0', [120, 28], "Try again"))
			mpn_next = 0;
		return;
	}
	cur = MU_VerNum(cvar_string("ui_release_version"));
	sidebar = min(136, size_x * 0.28);
	sui_text(pos, SZ_LABEL, "Version", COL_DIM, 1, 0);
	sui_list_view_begin("mpn_versions", pos + '0 26 0', [sidebar, size_y - 26], [sidebar - 10, 36],
	                    buf_getsize(mpn_releases), mpn_versions_scroll, [0, 4]);
	rp = '0 0 0';
	for (i = sui_list_item(rp); i > -1; i = sui_list_item(rp))
	{
		t = bufstr_get(mpn_releases, i);
		ui_chip(rp, strcat("mpn_version", ftos(i)), t, mpn_selected == i);
		if (sui_is_released(strcat("mpn_version", ftos(i)))) MU_NotesSelect(i);
	}
	sui_list_view_end();
	pos_x = pos_x + sidebar + 12;
	size_x = size_x - sidebar - 12;
	iw = size_x - 16;
	if (mpn_wrapw != iw)
		MU_NotesWrap(iw);
	sui_list_view_begin("mpn_list", pos, size, [size_x - 10, MPN_ROW],
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
				sui_text(rp + [iw - stringwidth(tag, TRUE, '12 12 0'), 7], '12 12 0', tag, (vn > cur) ? COL_ACCENT : COL_DIM, 1, 0);
		}
		else if (!strcmp(k, "P"))
		{
			if (i > 0)
			if (strcmp(substring(bufstr_get(mpn_lines, i - 1), 0, 1), "R"))
				sui_fill(rp + '0 1 0', [iw, 1], SUI_THEME_EDGE, 0.6, 0);
			sp = strstrofs(t, " ", 0);
			if (sp < 0)
				sui_text(rp + '0 3 0', MPN_SZ, t, COL_ACCENT, 1, 0);
			else
			{
				sui_text(rp + '0 6 0', '12 12 0', substring(t, 0, sp), COL_DIM, 1, 0);
				sui_text(rp + [stringwidth(substring(t, 0, sp), TRUE, '12 12 0') + 6, 3], MPN_SZ, substring(t, sp + 1, -1), COL_ACCENT, 1, 0);
			}
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
	if (!mu_checked)
	{
		mu_checked = TRUE;
		mu_lastcheck = time;
		mu_live = MU_Action(0);
		return;
	}
	MU_NotesAsk(st);
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

// P902: the updater's state and its one switch, in F2; returns the y under what it drew.
float(vector pos, float w) MU_StatusAt =
{
	local string st, label, latest, current, err, word, say;
	local float consent, bw, x, y;
	st = cvar_string("update_state");
	consent = cvar("update_consent");
	current = cvar_string("ui_release_version");
	if (current == "") current = strcat(UI_MENU_VERSION, " (dev)");
	latest = (consent == 1) ? cvar_string("update_version") : "";
	if (latest == "") latest = "unknown";
	label = "Updates";
	if (consent != 1) label = "Updates are off";
	else if (strcmp(st, "checking") == 0) label = "Checking for updates";
	else if (strcmp(st, "uptodate") == 0) label = "Up to date";
	else if (strcmp(st, "downloading") == 0 || strcmp(st, "applying") == 0) label = "Updating...";
	else if (strcmp(st, "available") == 0) label = "Update available";
	else if (strcmp(st, "restart") == 0) label = "Update ready";
	else if (strcmp(st, "launcher") == 0) label = "Update needs the launcher";
	else if (strcmp(st, "error") == 0) label = "Update check unavailable";
	Font_Set(ui_font_ui);
	sui_text(pos, SZ_LABEL, label, COL_ACCENT, 1, 0);
	sui_text(pos + '0 28 0', SZ_LABEL, ui_fit_text(strcat("Your version: ", current), w, SZ_LABEL), COL_TEXT, 1, 0);
	sui_text(pos + '0 50 0', SZ_LABEL, ui_fit_text(strcat("Latest: ", latest), w, SZ_LABEL), COL_DIM, 1, 0);
	y = pos_y + 80;
	err = "";
	if (consent == 1)
	if (strcmp(st, "error") == 0 || strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0)
		err = cvar_string("update_error");
	if (strlen(err))
		y = y + ui_para([pos_x, y], w, SZ_LABEL, 20, err, SUI_THEME_WARN, TRUE) + 8;
	if (consent == 1)
		say = "The game checks for updates at the title screen and installs one between games; restart when it says one is ready.";
	else if (ms_consent >= FS_TERMS_ONLINE)
		say = "Updates are off: the game does not check for or install new versions.";
	else
		say = "Updates are off. Turning them on needs the online terms (the Terms page).";
	y = y + ui_para([pos_x, y], w, SZ_LABEL, 20, say, COL_DIM, TRUE) + 14;
	// Left to right: the switch, then what the state asks for. Turning on needs online
	// terms and a real click (earlier terms promised this off switch).
	x = pos_x;
	if (consent == 1)
	{
		bw = stringwidth("Turn off updates", TRUE, SZ_LABEL) + 28;
		if (ui_button("mu_disable", [x, y], [bw, 28], "Turn off updates"))
			MU_Consent(FALSE);
		x = x + bw + 8;
	}
	else if (ms_consent >= FS_TERMS_ONLINE)
	{
		bw = stringwidth("Turn on updates", TRUE, SZ_LABEL) + 28;
		if (ui_button("mu_enable", [x, y], [bw, 28], "Turn on updates"))
		{
			if (ui_synth())
				print("menu: updates are turned on by a real click or key, not ui_key/ui_click\n");
			else
				MU_Consent(TRUE);
		}
		x = x + bw + 8;
	}
	else
		return y;
	if (consent != 1)
		return y + 28;
	word = "";
	if (clientstate() == 1)
	if (strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0)
		word = (strcmp(st, "launcher") == 0) ? "Restart through launcher" : "Restart to update";
	if (strlen(word))
	{
		bw = stringwidth(word, TRUE, SZ_LABEL) + 28;
		if (ui_button("mu_restart", [x, y], [bw, 28], word, TRUE))
			MU_Action(6);
	}
	else if (strcmp(st, "error") == 0)
	{
		bw = stringwidth("Check again", TRUE, SZ_LABEL) + 28;
		if (ui_button("mu_check", [x, y], [bw, 28], "Check again"))
			MU_Action(1);
	}
	return y + 28;
};

// P902: all the title screen keeps of the updater, as text: the two versions (Lex kept
// those from P823's corner), a line naming F2, and one more while an update downloads or
// waits for a restart.
void(vector screensize) MU_Hint =
{
	local string st, msg, current, latest;
	local float w, cur;
	if (ms_consent < FS_TERMS_VERSION)
		return;
	w = min(440, screensize_x - 32);
	current = cvar_string("ui_release_version");
	cur = MU_VerNum(current);
	if (current == "") current = strcat(UI_MENU_VERSION, " (dev)");
	latest = (cvar("update_consent") == 1) ? cvar_string("update_version") : "";  // never cleared by the engine
	Font_Set(ui_font_ui);
	MU_StatusLine(screensize_x - 16, 16, w, '12 12 0', strcat("Your version: ", current), COL_TEXT);
	MU_StatusLine(screensize_x - 16, 34, w, '12 12 0', strcat("Latest: ", (latest == "") ? "unknown" : latest),
	              (cur > 0 && MU_VerNum(latest) > cur) ? COL_ACCENT : COL_DIM);
	MU_StatusLine(screensize_x - 16, 56, w, '12 12 0', "F2   patch notes, updates, input journal, terms", COL_DIM);
	st = cvar_string("update_state");
	msg = "";
	if (cvar("update_consent") == 1)
	{
		if (!strcmp(st, "restart"))
			msg = "Update ready -- restart the game (F2)";
		else if (!strcmp(st, "launcher"))
			msg = "Update ready -- restart through the launcher (F2)";
		else if (!strcmp(st, "downloading") || !strcmp(st, "applying"))
			msg = "Downloading an update";
	}
	if (msg != "")
		MU_StatusLine(screensize_x - 16, 76, w, SZ_LABEL, msg, COL_ACCENT);
};

// ui_notes status|open|close|scroll <px>|select <version>: F2's notes controls.
void(string what) MU_NotesCommand =
{
	local float i;
	if (!strcmp(what, "open"))
	{
		ui_f2_tab = 0;
		menu_screen = SCREEN_JOURNAL;
		m_open();
		if (mpn_state == MPNS_FAIL) mpn_next = 0;
	}
	else if (!strcmp(what, "close"))
	{
		if (menu_screen == SCREEN_JOURNAL)
			menu_screen = SCREEN_MAIN;
	}
	else if (!strcmp(what, "scroll"))
		mpn_scroll_y = stof(argv(2));
	else if (!strcmp(what, "select"))
	{
		for (i = 0; i < buf_getsize(mpn_releases); i++)
			if (!strcmp(bufstr_get(mpn_releases, i), argv(2))) MU_NotesSelect(i);
	}
	print(sprintf("ui_notes: selected %s of %g\n", bufstr_get(mpn_releases, mpn_selected), buf_getsize(mpn_releases)));
	print(sprintf("ui_notes: state %g shown %g items %g lines %g wrap %g scroll %g\n",
	              mpn_state, menu_screen == SCREEN_JOURNAL && ui_f2_tab == 0, buf_getsize(mpn_items), buf_getsize(mpn_lines), mpn_wrapw, mpn_scroll_y));
	print(sprintf("ui_notes: installed %s listed %g url %s\n",
	              cvar_string("ui_release_version"), mpn_hascur, MU_NotesUrl()));
};
