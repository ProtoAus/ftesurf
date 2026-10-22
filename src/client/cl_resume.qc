/* P920: presentation/input for the existing local-player *resume protocol.
   No changes to paused files, recorder clocks or server accept/discard rules. */
string ui_ms_key;
float ui_ms_keyat;
string ui_ms_dismissed;
float ui_ms_answered;
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

void(vector scr) Timer_DrawResumeOffer =
{
	local string k, what, a, s, offermap;
	local float n, ticks, seg, segs, sessions, track, left;
	local float u, fs, small, px, spx, w, h, x, y, row;
	local vector p, col;

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
		u = max(0.5, min(ui_cv_scale, scr_y / 320));
		fs = 14 * u; small = 11 * u;
		Font_Set(ui_font_ui);
		px = Font_Px(fs); spx = Font_Px(small);
		w = min(360 * u, scr_x - 32 * u); h = px * 14.5;
		x = 16 * u; y = max(16 * u, (scr_y - h) * 0.35);
		col = '0.45 0.85 1.00';
		drawfill([x, y, 0], [w, h, 0], '0.025 0.035 0.05', 0.94, 0);
		drawfill([x, y, 0], [3 * u, h, 0], col, 1, 0);
		x = x + 14 * u; row = y + px;
		HUD_Text([x, row, 0], "RESUME PAUSED RUN?", 18 * u, col, 1);
		row = row + px * 1.8;
		offermap = serverkey("map");
		while (strlen(offermap) > 0 && stringwidth(offermap, FALSE, [spx, spx, 0]) > w - 28 * u)
			offermap = substring(offermap, 0, strlen(offermap) - 1);
		HUD_Text([x, row, 0], offermap, small, '0.70 0.75 0.80', 1);
		row = row + px * 1.8;
		HUD_Text([x, row, 0], strcat("Time: ", Time_TickString(ticks, Timer_Tick())), fs, '1 1 1', 1);
		row = row + px * 1.5;
		if (seg >= 0 && segs > 0) s = sprintf("Stage: %g / %g", seg + 1, segs);
		else s = "Run: full map";
		HUD_Text([x, row, 0], s, fs, '0.85 0.88 0.92', 1);
		row = row + px * 1.5;
		if (track > 0) s = sprintf("Bonus %g", track);
		else s = "Main track";
		HUD_Text([x, row, 0], sprintf("%s  -  session %g", s, sessions), small, '0.70 0.75 0.80', 1);
		row = row + px * 2;
		HUD_Text([x, row, 0], "1. Yes", fs, '0.60 1.00 0.75', 1);
		row = row + px * 1.7;
		HUD_Text([x, row, 0], "2. No (not now)", fs, '0.85 0.88 0.92', 1);
		row = row + px * 1.7;
		HUD_Text([x, row, 0], "F2 also resumes.  !resume is available later.", small, '0.60 0.65 0.70', 1);
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
