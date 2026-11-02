// P1084: hud_player's Stats page in the main menu -- client/cl_profile.qc's
// breakdown, tier lists, per-map rows and player search, hosted as cl_avatar.qc
// hosts them, on the menu's own player handle (MH_Me) and board transport.
// P1198: every player click in the menu opens it (MStats_Player); the old public
// profile dialog is gone, and its inventory grid is the page's Inventory window.
#define MS_TWOSIDED 1024        // CSQC's DRAWFLAG_TWOSIDED, for the crown's polygons
string ms_pf_other;             // a player picked from the search; "" is me
float  ms_pf_zoned;
float  ms_back;                 // P1198: the screen a player click came from
float  ms_inv;                  // the Inventory window is up
string ms_bmap, ms_bstyle;     // P1198: the board a row click left, reopened on Back
float  ms_btab, ms_btrack, ms_bleg;

void(string who) MStats_SetOther =
{
	if (ms_pf_zoned) strunzone(ms_pf_other);
	ms_pf_other = ""; ms_pf_zoned = FALSE;
	ms_inv = FALSE;
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
	ms_back = SCREEN_MAIN;
	if (ms_bmap != "") { strunzone(ms_bmap); ms_bmap = ""; }
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

// P1198: a player's name or picture anywhere in the menu.  `who` is an 8-hex mark
// or 12-hex handle (Profile_IsWho refuses anything else on the page).
void(string who) MStats_Player =
{
	local float back, board;
	back = menu_screen;
	board = (back == SCREEN_CREATE && Mlb_IsOpen());
	if (!menu_active) m_open();
	MStats_Open();
	MStats_SetOther(who);
	if (back == SCREEN_CHAT || back == SCREEN_STORY || back == SCREEN_CREATE) ms_back = back;
	if (board)
	{
		ms_bmap = strzone(mlb_map);
		if (ms_bstyle != "") strunzone(ms_bstyle);
		ms_btab = mlb_tab;
		ms_bstyle = strzone(mlb_style);
		ms_btrack = mlb_track; ms_bleg = mlb_leg;
	}
};

void() MStats_Close =
{
	Profile_Reset();
	sui_text_unfocus();
	ms_inv = FALSE;
	menu_screen = ms_back;
	ms_back = SCREEN_MAIN;
	if (ms_bmap == "") return;
	Mlb_Reopen(ms_bmap, ms_btab, ms_btrack, ms_bleg, ms_bstyle);
	strunzone(ms_bmap); ms_bmap = "";
};

float() MStats_InvOpen = { return ms_inv && menu_screen == SCREEN_STATS; };
void() MStats_InvClose = { ms_inv = FALSE; };
void() MStats_InvToggle = { if (menu_screen == SCREEN_STATS) ms_inv = !ms_inv; };

// A row's map, handed to the menu's own leaderboard (CSQC's goes to the scoreboard).
void() MStats_Board =
{
	// Profile_BoardPick has already refused any map name outside [A-Za-z0-9_-].
	if (tokenize(cvar_string("ui_board_request")) < 4) return;
	menu_screen = SCREEN_CREATE;
	ui_create_open();
	Mlb_Open(argv(0), stof(argv(2)));
};

// P1198: the read-only grid of CSQC's Inv_Panel (cl_inventory.qc), from the profile
// reply the page already holds: pf_inventory (owned aura, owned crown, crown colour)
// when the server listed the items, else pf_cosmetics (what is equipped).
void(vector size, string nm) MStats_InvDraw =
{
	local float cell, gap, i, j, x, owned, on, w, h;
	local vector p, at, colour, a, b, c;
	local string id, note;
	_action_elements_index = 0;     // the page under it takes no clicks
	sui_fill('0 0 0', size, '0 0 0', 0.6, 0);
	w = min(420, size_x - 32);
	gap = 8;
	cell = floor((w - 32 - gap * 3) / 4);
	h = 64 + cell * 4 + gap * 3 + 56;
	p = [floor((size_x - w) * 0.5), floor((size_y - h) * 0.5)];
	sui_style_panel(p, [w, h], 12, 1);
	sui_push_frame(p, [w, h]);
	sui_text('16 14 0', SZ_HEAD, "Inventory", COL_ACCENT, 1, 0);
	sui_text('16 40 0', SZ_LABEL, ui_fit_text(nm, w - 120, SZ_LABEL), COL_DIM, 1, 0);
	if (ui_button("ms_inv_close", [w - 84, 12], [68, 28], "Back")) ms_inv = FALSE;
	for (i = 0; i < 16; i = i + 1)
	{
		at = [16 + (i % 4) * (cell + gap), 64 + floor(i / 4) * (cell + gap)];
		owned = pf_inventory_known ? (i == 0 ? pf_inventory_x : (i == 1 ? pf_inventory_y : 0))
		                           : (i == 0 ? pf_cosmetics_y : (i == 1 ? pf_cosmetics_z : 0));
		on = i == 0 ? pf_cosmetics_y : (i == 1 ? pf_cosmetics_z : 0);
		sui_roundbox(at, [cell, cell], 6, (owned && on) ? SUI_THEME_SELECTED : SUI_THEME_WELL, 1);
		if (!owned || pf_state != PFS_OK) continue;
		colour = i == 0 ? '0.4 0.83 1' : sui_inventory_colour(pf_inventory_known ? pf_inventory_z : pf_cosmetics_z - 1);
		if (i == 0)
		{
			sui_roundbox(at + [cell * 0.28, cell * 0.18], [cell * 0.44, cell * 0.55], cell * 0.18, colour, 0.85);
			sui_roundbox(at + [cell * 0.34, cell * 0.24], [cell * 0.32, cell * 0.43], cell * 0.12, SUI_THEME_WELL, 1);
		}
		else
		{
			sui_fill(at + [cell * 0.18, cell * 0.46], [cell * 0.64, cell * 0.28], colour * 0.85, 1, 0);
			for (j = 0; j < 3; j = j + 1)
			{
				x = 0.28 + j * 0.22;
				a = at + [cell * (x - 0.1), cell * 0.5];
				b = at + [cell * x, cell * 0.18];
				c = at + [cell * (x + 0.1), cell * 0.5];
				sui_transform_point(a); sui_transform_point(b); sui_transform_point(c);
				R_BeginPolygon("", MS_TWOSIDED, TRUE);
				R_PolygonVertex(a, '0 0 0', colour * 0.85, 1);
				R_PolygonVertex(b, '0 0 0', colour, 1);
				R_PolygonVertex(c, '0 0 0', colour * 0.85, 1);
				R_EndPolygon();
			}
		}
		sui_text(at + [4, cell - 14], '10 10 0', on ? "ON" : "OWNED", colour, 1, 0);
		id = sprintf("ms_inv%g", i);
		sui_action_element(at, [cell, cell], id, sui_noop);
		sui_tooltip_for(id, strcat(i == 0 ? "Ice aura" : "Paper party crown", on ? ": equipped" : ": owned"), 2);
	}
	note = (pf_state != PFS_OK) ? "Loading..." : (pf_inventory_known ? "Owned items (read-only)" : "Owned items unavailable; equipped items only");
	sui_text([16, h - 36], SZ_LABEL, ui_fit_text(note, w - 32, SZ_LABEL), COL_DIM, 1, 0);
	sui_pop_frame();
};

void(vector size) MStats_Draw =
{
	local float me, pad, pic, ttl, tsz, hint, fw, fh, x, y, y0, cx, room;
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
	room = size_x - x - fw - pad * 2;
	sui_text([x, pad + 2], [ttl, ttl], ui_fit_text(nm, room, [ttl, ttl]), COL_TEXT, 1, 0);
	y = pad + ttl + 8;
	s = me ? ((acct_cl_is == 2) ? "Steam account linked" : "Not linked to Steam") : "";
	if (pf_state == PFS_OK)
	{
		s = strcat(s, me ? "   " : "", Profile_TierTag(pf_src));
		if (Profile_Age(pf_last) != "")
			s = strcat(s, "   last time ", Profile_Age(pf_last), (Profile_Age(pf_last) == "today") ? "" : " ago");
	}
	// P1198: the chips first, so the line gives way to them.
	cx = x + room - ceil(hint * 7);
	if (who != "")
	if (Profile_Chip("ms_inventory", [cx, y - 2], [ceil(hint * 7), ceil(hint * 1.9)], "Inventory", hint, ms_inv))
		ms_inv = !ms_inv;
	if (!me)
	{
		cx = cx - ceil(hint * 8) - 6;
		if (Profile_Chip("ms_backme", [cx, y - 2], [ceil(hint * 8), ceil(hint * 1.9)], "Back to me", hint, FALSE))
			MStats_SetOther("");
	}
	sui_text([x, y + 2], [hint, hint], ui_fit_text(s, cx - x - hint, [hint, hint]), COL_DIM, 1, 0);
	Profile_Field("pf_qa", [size_x - pad - fw, pad], [fw, fh], tsz);
	sui_fill([pad, pad + pic + 12], [size_x - pad * 2, 1], SUI_THEME_EDGE, 1, 0);

	y0 = pad + pic + 24;
	if (who == "")
		sui_text([pad, y0 + hint], [tsz, tsz], "Link your Steam account on a lobby to have a World of Surf profile here.",
		         COL_DIM, 1, 0);
	else
		Profile_DrawStats([pad, y0], [size_x - pad * 2, size_y - pad - y0], ttl, tsz, hint);
	// The search's list LAST: over everything, and the element sui answers for.
	if (!ms_inv)
		Profile_Drop([size_x - pad - max(fw, tsz * 18), pad + fh + 4], max(fw, tsz * 18), tsz, hint);
	else
		MStats_InvDraw(size, nm);
	sui_pop_frame();

	if (ms_inv) return;
	if (Profile_BoardNavigate()) { MStats_Board(); return; }
	pick = Profile_TakePick();
	if (pick != "") MStats_SetOther(pick);
};

// `ui_stats [open [who]|close|inv]`: the page, and what it is showing.
void() MStats_Probe =
{
	print(sprintf("ui_stats: screen %g who %s state %g name %s runs %g source %g\n", menu_screen == SCREEN_STATS,
	              (ms_pf_other == "") ? strcat("me:", MH_Me()) : ms_pf_other, pf_state, pf_name, pf_n, pf_cs));
	print(sprintf("ui_stats: kind %g rows-kind %g rows-source %g rows %g/%g waiting %g first %s\n",
	              pf_cm, pf_rf_cm, pf_rf_cs, pf_rn, pf_total, pf_rows_wait,
	              pf_rn ? bufstr_get(pf_bmap, 0) : "--"));
	print(sprintf("ui_stats: inventory window %g known %g owned %g/%g equipped %g/%g\n",
	              ms_inv, pf_inventory_known, pf_inventory_x, pf_inventory_y, pf_cosmetics_y, pf_cosmetics_z > 0));
	print(sprintf("ui_stats: back %g board %s\n", ms_back, (ms_bmap != "") ? ms_bmap : "--"));
};
