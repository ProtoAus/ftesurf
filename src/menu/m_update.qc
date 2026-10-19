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

void() MU_Init =
{
	registercvar("ui_release_version", "", 0);
	mu_checked = FALSE;
	mu_apply_sent = FALSE;
	mu_lastcheck = 0;
};

// The permission, from the terms answer or the corner's button; a new "on" checks at once.
void(float on) MU_Consent =
{
	if (MU_Action(on ? 4 : 5) && on)
		mu_checked = FALSE;
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
		if (ui_button("mu_restart", [x - bw, y], [bw, 28], word, TRUE))
			MU_Action(6);
	}
	else if (strcmp(st, "error") == 0)
	{
		bw = stringwidth("Check again", TRUE, SZ_LABEL) + 28;
		if (ui_button("mu_check", [x - bw, y], [bw, 28], "Check again"))
			MU_Action(1);
	}
};
