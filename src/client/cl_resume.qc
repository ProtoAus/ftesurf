/* P920: presentation/input for the existing local-player *resume protocol.
   No changes to paused files, recorder clocks or server accept/discard rules. */
string ui_ms_key;
float ui_ms_keyat;
string ui_ms_dismissed;
float ui_ms_answered, ui_ms_answerat, ui_ms_refused;
float ui_ms_key1, ui_ms_key2, ui_ms_keyf2;
float ui_ms_hold, ui_ms_holdseq, ui_ms_holdseen, ui_ms_ignorecount;
vector ui_ms_holdang;

string() Timer_ResumeKey =
{
	local string k;
	k = getplayerkeyvalue(player_localnum, "*resume");
	if (strcmp(k, ui_ms_key))
	{
		if (ui_ms_key != "") strunzone(ui_ms_key);
		ui_ms_key = (k != "") ? strzone(k) : "";
		ui_ms_keyat = cltime;
		ui_ms_answered = FALSE;
		ui_ms_refused = FALSE;
		if (ui_ms_dismissed != "") strunzone(ui_ms_dismissed);
		ui_ms_dismissed = "";
	}
	return ui_ms_key;
};

float() Timer_ResumeOffered =
{
	local string k;
	k = Timer_ResumeKey();
	if (Spec_Active() || rec_wt_on) return FALSE;
	if (strcmp(substring(k, 0, 2), "O ")) return FALSE;
	// Still offered 2.5 s after a Yes: the server refused (the reason is in
	// chat), so the offer comes back for another try instead of vanishing.
	if (ui_ms_answered && cltime - ui_ms_answerat > 2.5)
	{
		ui_ms_answered = FALSE;
		ui_ms_refused = TRUE;
	}
	if (ui_ms_answered) return FALSE;
	return strcmp(k, ui_ms_dismissed) != 0;
};

// Higher modal panels keep their keys. Own releases survive a reply which hides
// the offer between press and release. No means "not now", never ms_discard.
float(float typ, float scan) Timer_ResumeInputKey =
{
	local float yes;
	if (typ == IE_KEYUP)
	{
		if (scan == 49 && ui_ms_key1) { ui_ms_key1 = FALSE; return TRUE; }
		if (scan == 50 && ui_ms_key2) { ui_ms_key2 = FALSE; return TRUE; }
		if (scan == K_F2 && ui_ms_keyf2) { ui_ms_keyf2 = FALSE; return TRUE; }
		return FALSE;
	}
	if (typ != IE_KEYDOWN) return FALSE;
	if (scan == 49 && ui_ms_key1) return TRUE;
	if (scan == 50 && ui_ms_key2) return TRUE;
	if (scan == K_F2 && ui_ms_keyf2) return TRUE;
	if (!Timer_ResumeOffered()) return FALSE;
	if (scan != 49 && scan != 50 && scan != K_F2) return FALSE;
	yes = (scan == 49 || scan == K_F2);
	if (scan == 49) ui_ms_key1 = TRUE;
	if (scan == 50) ui_ms_key2 = TRUE;
	if (scan == K_F2) ui_ms_keyf2 = TRUE;
	if (yes)
	{
		ui_ms_answered = TRUE;
		ui_ms_answerat = cltime;
		localcmd("cmd ms_resume\n");
	}
	else
	{
		if (ui_ms_dismissed != "") strunzone(ui_ms_dismissed);
		ui_ms_dismissed = strzone(ui_ms_key);
	}
	return TRUE;
};

void() Timer_ResumeBlur = { ui_ms_key1 = ui_ms_key2 = ui_ms_keyf2 = FALSE; };

// VF_ANGLES alone accumulates a hidden mouse turn and snaps at GO. As with the
// save lock, restore VF_CL_VIEWANGLES at render rate AND outgoing input rate.
// A resume event owns the newly restored angle even if the old C key lingers.
float() Timer_ResumeLockAngles =
{
	local float seq, op, counting;
	seq = getstatf(STAT_FS_SLSEQ);
	if (!ui_ms_holdseen)
	{
		ui_ms_holdseen = TRUE;
		ui_ms_holdseq = seq;
	}
	else if (seq != ui_ms_holdseq)
	{
		ui_ms_holdseq = seq;
		op = FS_SlopOp(getstatf(STAT_FS_SLOP));
		if (op == SLOP_RESUME) ui_ms_ignorecount = TRUE;
	}
	counting = !strcmp(substring(Timer_ResumeKey(), 0, 2), "C ");
	if (!counting)
	{
		ui_ms_hold = FALSE;
		ui_ms_ignorecount = FALSE;
		return FALSE;
	}
	if (Spec_Active() || rec_wt_on || ui_ms_ignorecount)
	{
		ui_ms_hold = FALSE;
		return FALSE;
	}
	if (!ui_ms_hold)
	{
		ui_ms_holdang = getproperty(VF_CL_VIEWANGLES);
		ui_ms_hold = TRUE;
	}
	setproperty(VF_CL_VIEWANGLES, ui_ms_holdang);
	return TRUE;
};

float() Timer_ResumeInputFrame =
{
	if (!Timer_ResumeLockAngles()) return FALSE;
	input_angles = ui_ms_holdang;
	input_movevalues = '0 0 0';
	input_buttons = 0;
	return TRUE;                // leave msec alone so server count-in advances
};

// The left-hand digit-menu card (SaveLoc_Draw's pieces), beside the save menu
// when that is open.
void(vector scr) Timer_DrawResumeOffer =
{
	local string k, what, a, s, offermap;
	local float n, ticks, seg, segs, sessions, track, left;
	local float sc, lsz, w, h, hh, y, total, mw;
	local vector p;

	if (rec_wt_on) return;
	k = Timer_ResumeKey();
	if (k == "") return;
	n = tokenize(k);
	what = argv(0);
	if (!strcmp(what, "O") && n >= 7)
	{
		if (!Timer_ResumeOffered()) return;
		tokenize(k);
		ticks = stof(argv(1)); seg = stof(argv(2)); segs = stof(argv(3));
		track = stof(argv(4)); sessions = stof(argv(6)) + 1;

		sc  = ui_cv_scale;
		Font_Set(ui_font_ui);
		lsz = Font_Px(8 * sc);
		h   = 14 * sc;
		hh  = 15 * sc;
		w   = 120 * sc;
		total = 3 * sc + hh + 6 * h + 3 * sc;
		if (ui_ms_refused) total = total + h;

		p = [scr_x * cvar("hud_saveloc_x"), scr_y * cvar("hud_saveloc_y"), 0];
		if (rec_sl_open) p_x = p_x + 102 * sc;
		_sui_round_draw(p, [w, total, 0], 5 * sc, SUI_THEME_PANEL, 0.90);

		y = p_y + 3 * sc;
		HUD_Text([p_x + 6 * sc, y + (hh - 2 * sc - lsz) * 0.5], "Resume run", lsz, SUI_THEME_TEXT, 1);
		if (seg >= 0 && segs > 0) s = sprintf("stage %g / %g", seg + 1, segs);
		else s = "full run";
		HUD_TextR([p_x + w - 6 * sc, y + (hh - 2 * sc - lsz) * 0.5], s, lsz, SUI_THEME_WARN, 1);
		drawfill([p_x + 4 * sc, y + hh - 2 * sc, 0], [w - 8 * sc, 1, 0], SUI_THEME_EDGE_HI, 0.7, 0);
		y = y + hh;

		offermap = serverkey("map");
		mw = w - 18 * sc - stringwidth("map", TRUE, [lsz, lsz]);
		while (strlen(offermap) > 0 && stringwidth(offermap, TRUE, [lsz, lsz]) > mw)
			offermap = substring(offermap, 0, strlen(offermap) - 1);
		HUD_Text([p_x + 6 * sc, y + (h - sc - lsz) * 0.5], "map", lsz, SUI_THEME_MUTED, 1);
		HUD_TextR([p_x + w - 6 * sc, y + (h - sc - lsz) * 0.5], offermap, lsz, SUI_THEME_DIM, 1);
		y = y + h;
		HUD_Text([p_x + 6 * sc, y + (h - sc - lsz) * 0.5], "paused at", lsz, SUI_THEME_MUTED, 1);
		HUD_TextR([p_x + w - 6 * sc, y + (h - sc - lsz) * 0.5],
		          Time_TickString(ticks, Timer_Tick()), lsz, SUI_THEME_ACCENT, 1);
		y = y + h;
		if (track > 0) s = sprintf("bonus %g", track);
		else s = "main";
		HUD_Text([p_x + 6 * sc, y + (h - sc - lsz) * 0.5], s, lsz, SUI_THEME_MUTED, 1);
		HUD_TextR([p_x + w - 6 * sc, y + (h - sc - lsz) * 0.5], sprintf("session %g", sessions),
		          lsz, SUI_THEME_DIM, 1);
		y = y + h;
		if (ui_ms_refused)
		{
			_sui_round_draw([p_x + 2 * sc, y, 0], [w - 4 * sc, h - sc, 0], 2.5 * sc, SUI_THEME_BAD_BG, 1);
			HUD_Text([p_x + 6 * sc, y + (h - sc - lsz) * 0.5], "not resumed - see chat", lsz,
			         SUI_THEME_BAD, 1);
			y = y + h;
		}
		KeyMenu_Row([p_x, y], w, h, "1", "Resume", KM_HOT, lsz, sc);       y = y + h;
		KeyMenu_Row([p_x, y], w, h, "2", "Not now", KM_NORMAL, lsz, sc);   y = y + h;
		HUD_Text([p_x + 6 * sc, y + (h - sc - lsz) * 0.5], "F2 or !resume also work", lsz,
		         SUI_THEME_MUTED, 1);
		Font_Reset();
		return;
	}
	a = "";
	if (!strcmp(what, "R") && n >= 2)
		a = sprintf("RESTORING THE RECORDING  %g%%", stof(argv(1)));
	else if (!strcmp(what, "C") && n >= 2)
	{
		left = ceil(stof(argv(1)) - (cltime - ui_ms_keyat));
		a = sprintf("RESUMING IN %g  -  VIEW LOCKED", max(1, left));
	}
	if (a == "") return;
	Font_Set(ui_font_ui);
	p = [scr_x * 0.5, scr_y * 0.30, 0];
	HUD_TextC(p, a, 10 * ui_cv_scale, '0.45 0.85 1.00', 0.95);
	Font_Reset();
};
