// P1084: hud_player's Stats page in the main menu -- client/cl_profile.qc's
// breakdown, tier lists, per-map rows and player search, hosted as cl_avatar.qc
// hosts them, on the menu's own player handle (MH_Me) and board transport.
string ms_pf_other;             // a player picked from the search; "" is me
float  ms_pf_zoned;

void(string who) MStats_SetOther =
{
	if (ms_pf_zoned) strunzone(ms_pf_other);
	ms_pf_other = ""; ms_pf_zoned = FALSE;
	if (who != "" && who != MH_Me())
	{
		ms_pf_other = strzone(who); ms_pf_zoned = TRUE;
	}
};

void() MStats_Open =
{
	sui_text_unfocus();
	MStats_SetOther("");
	Profile_Reset();
	pf_cm = mh_mode;                // P1122: the kind the home panel showed
	pf_cm_slide = Profile_KindPlace(pf_cm);
	if (mh_source_picked)
	{
		pf_cs = !mh_source;         // home's 0 is World of Surf, the page's 1
		pf_cs_picked = TRUE;
	}
	pf_sw_slide = !pf_cs;           // P1130: opening must not animate from another source
	Profile_Stale(60);
	Profile_TierShow(-2);           // opens on the results, as hud_player does
	// P1130: changing the home switch must also invalidate a cached profile's rows.
	// A different player will be asked by Profile_Show; do not ask for their old rows here.
	if (!strcmp(pf_who, MH_Me()) && pf_rf_ok)
	if (pf_rf_cm != pf_cm || pf_rf_cs != pf_cs) Profile_RowsAsk();
	menu_screen = SCREEN_STATS;
};

void() MStats_Close =
{
	Profile_Reset();
	sui_text_unfocus();
	menu_screen = SCREEN_MAIN;
};

// A row's map, handed to the menu's own leaderboard (CSQC's goes to the scoreboard).
void() MStats_Board =
{
	// Profile_BoardPick has already refused any map name outside [A-Za-z0-9_-].
	if (tokenize(cvar_string("ui_board_request")) < 4) return;
	menu_screen = SCREEN_CREATE;
	ui_create_open();
	Mlb_Open(argv(0), stof(argv(2)));
};

void(vector size) MStats_Draw =
{
	local float me, pad, pic, ttl, tsz, hint, fw, fh, x, y, y0;
	local string who, nm, s, pick;

	me = (ms_pf_other == "");
	who = me ? MH_Me() : ms_pf_other;
	acct_cl_is = (MH_Me() != "") ? 2 : 1;      // the menu knows only "has a player handle"
	Profile_Frame();
	if (who != "") Profile_Show(who);
	pad = 16; pic = 48; ttl = 24; tsz = 16; hint = 12;
	fw = min(320, floor(size_x * 0.4)); fh = 30;
	sui_style_panel('0 0 0', size, 12, 1);
	sui_push_frame('0 0 0', size);

	nm = (pf_state == PFS_OK) ? pf_name : (me ? cvar_string("name") : "");
	Profile_Face([pad, pad], pic, substring(pf_handle, 0, 8), pf_state == PFS_OK && pf_av, nm);
	x = pad * 2 + pic;
	sui_text([x, pad + 2], [ttl, ttl], ui_fit_text(nm, size_x - x - fw - pad * 2, [ttl, ttl]), COL_TEXT, 1, 0);
	y = pad + ttl + 8;
	s = me ? ((acct_cl_is == 2) ? "Steam account linked" : "Not linked to Steam") : "";
	if (pf_state == PFS_OK)
	{
		s = strcat(s, me ? "   " : "", Profile_TierTag(pf_src));
		if (Profile_Age(pf_last) != "")
			s = strcat(s, "   last time ", Profile_Age(pf_last), (Profile_Age(pf_last) == "today") ? "" : " ago");
	}
	sui_text([x, y + 2], [hint, hint], ui_fit_text(s, size_x - x - fw - pad * 2, [hint, hint]), COL_DIM, 1, 0);
	if (!me)
	if (Profile_Chip("ms_backme", [x + min(stringwidth(s, TRUE, [hint, hint]), size_x - x - fw - pad * 2) + hint, y - 2],
	                 [ceil(hint * 8), ceil(hint * 1.9)], "Back to me", hint, FALSE))
		MStats_SetOther("");
	Profile_Field("pf_qa", [size_x - pad - fw, pad], [fw, fh], tsz);
	sui_fill([pad, pad + pic + 12], [size_x - pad * 2, 1], SUI_THEME_EDGE, 1, 0);

	y0 = pad + pic + 24;
	if (who == "")
		sui_text([pad, y0 + hint], [tsz, tsz], "Link your Steam account on a lobby to have a World of Surf profile here.",
		         COL_DIM, 1, 0);
	else
		Profile_DrawStats([pad, y0], [size_x - pad * 2, size_y - pad - y0], ttl, tsz, hint);
	// The search's list LAST: over everything, and the element sui answers for.
	Profile_Drop([size_x - pad - max(fw, tsz * 18), pad + fh + 4], max(fw, tsz * 18), tsz, hint);
	sui_pop_frame();

	if (Profile_BoardNavigate()) { MStats_Board(); return; }
	pick = Profile_TakePick();
	if (pick != "") MStats_SetOther(pick);
};

// `ui_stats [open|close|who]`: the page, and what it is showing.
void() MStats_Probe =
{
	print(sprintf("ui_stats: screen %g who %s state %g name %s runs %g source %g\n", menu_screen == SCREEN_STATS,
	              (ms_pf_other == "") ? strcat("me:", MH_Me()) : ms_pf_other, pf_state, pf_name, pf_n, pf_cs));
	print(sprintf("ui_stats: kind %g rows-kind %g rows-source %g rows %g/%g waiting %g first %s\n",
	              pf_cm, pf_rf_cm, pf_rf_cs, pf_rn, pf_total, pf_rows_wait,
	              pf_rn ? bufstr_get(pf_bmap, 0) : "--"));
};
