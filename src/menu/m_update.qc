// FTESurf's updater and launcher share one signed feed, ledger and permission.
// No HTTP before explicit update consent. The server cannot set these engine cvars.
// Menu-only engine capability; intentionally absent from server-supplied CSQC.
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

void() MU_Poll =
{
	local string st;
	local float consent;
	consent = cvar("update_consent");
	if (cvar("ui_bootcheck")) return;
	if (ms_consent < FS_TERMS_VERSION) return;
	if (consent < 0 && menu_screen == SCREEN_MAIN)
	{
		menu_screen = SCREEN_UPDATE;
		return;
	}
	if (consent != 1) return;
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
	if (menu_screen == SCREEN_MAIN || menu_screen == SCREEN_UPDATE)
	{
		mu_apply_sent = TRUE;
		MU_Action(2);
	}
};

float(string st) MU_Ready =
{
	return (strcmp(st, "available") == 0 || strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0);
};

void(float right, float y, float width, vector size, string text, vector color) MU_StatusLine =
{
	text = ui_fit_text(text, width, size);
	sui_text([right - stringwidth(text, TRUE, size), y], size, text, color, 1, 0);
};

void(vector screensize) MU_Status =
{
	local string st, label, latest, current;
	local float w, right;
	st = cvar_string("update_state");
	current = cvar_string("ui_release_version");
	if (current == "") current = strcat(UI_MENU_VERSION, " (dev)");
	latest = cvar_string("update_version");
	if (latest == "") latest = "not checked";
	label = "Updates";
	if (cvar("update_consent") == 0) label = "Updates off";
	else if (strcmp(st, "checking") == 0) label = "Checking for updates";
	else if (strcmp(st, "uptodate") == 0) label = "Up to date";
	else if (strcmp(st, "downloading") == 0 || strcmp(st, "applying") == 0) label = "Updating...";
	else if (strcmp(st, "available") == 0) label = "Update available";
	else if (strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0) label = "Update ready - restart";
	else if (strcmp(st, "error") == 0) label = "Update check unavailable";
	if (cvar("update_consent") == 1)
	if (MU_Ready(st))
	if (checkbuiltin(localcmd_local))
	if (strcmp(getkeybind(K_F2), "ui_updates") == 0)
		label = strcat(label, "  [F2]");
	w = min(320, screensize_x - 32);
	right = screensize_x - 16;
	Font_Set(ui_font_ui);
	MU_StatusLine(right, 16, w, SZ_LABEL, label, COL_ACCENT);
	MU_StatusLine(right, 38, w, '12 12 0', strcat("Your version: ", current), COL_TEXT);
	MU_StatusLine(right, 58, w, '12 12 0', strcat("Latest: ", latest), COL_DIM);
};

void(vector screensize) MU_Screen =
{
	local float x, y, w, h, consent, frac;
	local string st, title, detail;
	x = floor(screensize_x * 0.5) - 300;
	y = max(36, floor(screensize_y * 0.5) - 210);
	w = 600;
	consent = cvar("update_consent");
	st = cvar_string("update_state");
	ui_backdrop(screensize);
	sui_fill([x, y], [w, 420], COL_PANEL, 0.95, 0);
	sui_border_box([x, y], [w, 420], 1, COL_BORDER, 1, 0);
	sui_text([x + 24, y + 20], SZ_TITLE, "World of Surf updates", COL_TEXT, 1, 0);
	h = ui_para([x + 24, y + 62], w - 48, SZ_LABEL, 19,
		"Optional automatic updates check proto.bar and download from dl.proto.bar. Those services see your IP address. Nothing is uploaded: your settings, recordings, mounted game assets and edited zones stay yours.", COL_DIM, TRUE);
	y = y + 62 + h + 18;
	if (consent != 1)
	{
		sui_text([x + 24, y], SZ_LABEL, "Enable updates once, then just play.", COL_TEXT, 1, 0);
		if (ui_button("mu_enable", [x + 24, y + 42], [250, 36], "Enable automatic updates", TRUE))
		{
			MU_Action(4);
			mu_checked = FALSE;
		}
		if (ui_button("mu_off", [x + 292, y + 42], [240, 36], "Keep updates off"))
		{
			MU_Action(5);
			menu_screen = SCREEN_MAIN;
		}
		return;
	}
	title = "Checking for updates";
	detail = "The launcher checks all game-owned files before starting World of Surf.";
	if (strcmp(st, "uptodate") == 0) title = "You have the latest published update";
	else if (strcmp(st, "available") == 0)
	{
		title = "A content update is ready";
		detail = "Small content updates install automatically at the title menu. Leave the game first; files are never swapped during a run.";
	}
	else if (strcmp(st, "downloading") == 0 || strcmp(st, "applying") == 0)
	{
		title = "Downloading and verifying the update";
		detail = "Keep World of Surf open. A failed download leaves the installed files untouched.";
		frac = 0;
		if (cvar("update_bytes") > 0) frac = bound(0, cvar("update_done_bytes") / cvar("update_bytes"), 1);
		drawfill([x + 24, y + 100], [w - 48, 6], COL_BORDER, 1, 0);
		drawfill([x + 24, y + 100], [(w - 48) * frac, 6], COL_ACCENT, 1, 0);
	}
	else if (strcmp(st, "restart") == 0)
	{
		title = "Update installed - restart to finish";
		detail = "Restart through the launcher to load the new files. Your mounted games and local settings are unchanged.";
	}
	else if (strcmp(st, "launcher") == 0)
	{
		title = "A complete update needs the launcher";
		detail = "Engine and plugin updates are installed together before the game starts. Restart through the launcher; it downloads only changed files.";
	}
	else if (strcmp(st, "error") == 0)
	{
		title = "Update check unavailable";
		detail = cvar_string("update_error");
	}
	if (strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0)
	if (strcmp(cvar_string("update_error"), "") != 0)
		detail = cvar_string("update_error");
	sui_text([x + 24, y], SZ_LABEL, title, COL_TEXT, 1, 0);
	if (strcmp(cvar_string("update_version"), "") != 0)
		sui_text([x + 24, y + 28], SZ_LABEL, sprintf("Published version: %s", cvar_string("update_version")), COL_DIM, 1, 0);
	ui_para([x + 24, y + 58], w - 48, SZ_LABEL, 19, detail, COL_DIM, TRUE);
	if (clientstate() == 1)
	if (strcmp(st, "restart") == 0 || strcmp(st, "launcher") == 0)
	if (ui_button("mu_restart", [x + 24, y + 140], [250, 36], "Restart through launcher", TRUE))
		MU_Action(6);
	if (strcmp(st, "error") == 0 || strcmp(st, "uptodate") == 0 || strcmp(st, "idle") == 0)
	if (ui_button("mu_check", [x + 24, y + 140], [210, 36], "Check now"))
		MU_Action(1);
	if (ui_button("mu_back", [x + 292, y + 140], [160, 36], "Back")) menu_screen = SCREEN_MAIN;
	if (ui_button("mu_disable", [x + 24, y + 188], [210, 30], "Disable automatic updates"))
		MU_Action(5);
};
