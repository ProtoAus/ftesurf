// FTESurf's updater and launcher share one signed feed, ledger and permission.
// No HTTP before explicit update consent. The server cannot set these engine cvars.
// Menu-only engine capability; intentionally absent from server-supplied CSQC.
// P823: no Updates screen. The terms answer is the permission (Play online on,
// offline off; ui_tm_answer), and the title menu's corner shows the state.
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
	local string st, label, latest, current;
	local float w, right, consent, bw;
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
	else if (strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0) label = "Update ready";
	else if (strcmp(st, "error") == 0) label = "Update check unavailable";
	w = min(320, screensize_x - 32);
	right = screensize_x - 16;
	Font_Set(ui_font_ui);
	MU_StatusLine(right, 16, w, SZ_LABEL, label, COL_ACCENT);
	MU_StatusLine(right, 38, w, '12 12 0', strcat("Your version: ", current), COL_TEXT);
	MU_StatusLine(right, 58, w, '12 12 0', strcat("Latest: ", latest), COL_DIM);
	if (menu_screen != SCREEN_MAIN)
		return;
	// The screen's two deeds that have no other home: finishing an update, and turning
	// updates on for an online player who turned them off before P823.
	if (consent == 1 && clientstate() == 1)
	if (strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0)
	{
		bw = stringwidth("Restart to update", TRUE, SZ_LABEL) + 28;
		if (ui_button("mu_restart", [right - bw, 80], [bw, 28], "Restart to update", TRUE))
			MU_Action(6);
	}
	if (consent != 1 && ms_consent >= FS_TERMS_ONLINE)
	{
		bw = stringwidth("Turn on updates", TRUE, SZ_LABEL) + 28;
		if (ui_button("mu_enable", [right - bw, 80], [bw, 28], "Turn on updates"))
			MU_Consent(TRUE);
	}
};
