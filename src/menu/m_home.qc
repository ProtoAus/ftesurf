// Home owns the lobby overview; other tabs keep their whole content area.
float mh_req, mh_sent, mh_next, mh_state, mh_source;
float mh_times, mh_wr, mh_wrc, mh_maps, mh_native;
float mh_wos_done, mh_all_done, mh_total, mh_tiers_wos, mh_tiers_all, mh_buffers_ready;
vector mh_lscroll, mh_tscroll;
string mh_who;

string() MH_Me =
{
	if (MF_Hex(sty_me, 12)) return sty_me;
	return "";
};

void(vector screensize) MC_Draw =
{
	local vector size, pos;
	size = [min(1040, screensize_x - 32), min(680, screensize_y - 32)];
	pos = [floor((screensize_x - size_x) * 0.5), floor((screensize_y - size_y) * 0.5)];
	MC_Panel(pos, size, FALSE);
};

void(int node, float target) MH_ReadTiers =
{
	local int tiers, row;
	local float i, n;
	tiers = json_find_object_child(node, "tiers");
	n = min(16, json_get_length(tiers));
	for (i = 0; i < n; i = i + 1)
	{
		row = json_get_child_at_index(tiers, i);
		bufstr_set(target, i, sprintf("%g %g %g", json_get_float(json_find_object_child(row, "tier")),
			json_get_float(json_find_object_child(row, "done")), json_get_float(json_find_object_child(row, "of"))));
	}
	row = json_find_object_child(node, "unrated");
	if (row) bufstr_set(target, n, sprintf("0 %g %g", json_get_float(json_find_object_child(row, "done")), json_get_float(json_find_object_child(row, "of"))));
};

float(float reqid, float code, string body) MH_Reply =
{
	local int root, c, wos;
	if (!mh_req || reqid != mh_req) return FALSE;
	mh_req = 0;
	mh_next = time + 60;
	if (code || strlen(body) > 131072)
	{
		mh_state = 3;
		return TRUE;
	}
	root = json_parse(body);
	if (!root) { mh_state = 3; return TRUE; }
	if (strcmp(json_get_string(json_find_object_child(root, "who")), mh_who))
	{
		json_free(root); mh_state = 3; return TRUE;
	}
	if (mh_buffers_ready) { buf_del(mh_tiers_wos); buf_del(mh_tiers_all); }
	mh_tiers_wos = buf_create(); mh_tiers_all = buf_create();
	mh_buffers_ready = TRUE;
	c = json_find_object_child(root, "completion");
	mh_all_done = json_get_float(json_find_object_child(c, "done"));
	mh_total = json_get_float(json_find_object_child(c, "of"));
	MH_ReadTiers(c, mh_tiers_all);
	c = json_find_object_child(root, "completion_wos");
	mh_native = (json_get_length(c) > 0);
	if (!mh_native) mh_source = 1;
	mh_wos_done = json_get_float(json_find_object_child(c, "done"));
	MH_ReadTiers(c, mh_tiers_wos);
	wos = json_find_object_child(root, "wos");
	mh_times = json_get_float(json_find_object_child(wos, "n"));
	mh_maps = json_get_float(json_find_object_child(wos, "maps"));
	mh_wr = json_get_float(json_find_object_child(wos, "wr"));
	mh_wrc = json_get_float(json_find_object_child(wos, "wrc"));
	mh_state = 2;
	json_free(root);
	return TRUE;
};

void() MH_Poll =
{
	local string who;
	if (mh_req)
	if (time - mh_sent > 12) { mh_req = 0; mh_state = 3; mh_next = time + 30; }
	if (!menu_active || menu_screen != SCREEN_MAIN || !MF_Online()) return;
	Lob_Poll();
	Sty_Prefetch();
	who = MH_Me();
	if (who == "") return;
	if (strcmp(who, mh_who))
	{
		strunzone(mh_who); mh_who = strzone(who);
		mh_req = mh_state = mh_next = 0;
	}
	if (strcmp(who, sty_who)) Sty_View(who);
	Sty_Poll();
	if (mh_req || time < mh_next) return;
	mh_req = Lob_NextReq(); mh_sent = time;
	mh_state = 1;
	if (!uri_get(sprintf("%s/api/board?player=%s&limit=1", MF_SITE, who), mh_req))
	{
		mh_req = 0; mh_state = 3; mh_next = time + 30;
	}
};

void(vector screensize) MH_Tabs =
{
	local float x, i, target, on;
	local string id, label;
	sui_fill('0 0 0', [screensize_x, 56], SUI_THEME_PANEL, 0.98, 0);
	sui_text('20 20 0', SZ_HEAD, screensize_x >= 1040 ? "WORLD OF SURF" : "WOS", COL_ACCENT, 1, 0);
	x = screensize_x >= 1040 ? 220 : 84;
	for (i = 0; i < 6; i = i + 1)
	{
		label = i == 0 ? "Lobbies" : (i == 1 ? "Maps" : (i == 2 ? "Story Mode" : (i == 3 ? "Event Mode" : (i == 4 ? "Settings" : "Music"))));
		target = i == 0 ? SCREEN_MAIN : (i == 1 ? SCREEN_CREATE : (i <= 3 ? SCREEN_STORY : (i == 4 ? SCREEN_SETTINGS : SCREEN_MUSIC)));
		on = (menu_screen == target);
		if (i == 4 && menu_screen == SCREEN_VISUALS) on = TRUE;
		if (i == 2 || i == 3) on = (menu_screen == SCREEN_STORY && sty_tab == i - 2);
		// Stable IDs for the shared navigation strip.
		id = i == 0 ? "home_tab0" : (i == 1 ? "home_tab1" : (i == 2 ? "home_tab2" : (i == 3 ? "home_tab3" : (i == 4 ? "home_tab4" : "home_tab5"))));
		x = x + ui_chip([x, 12], id, label, on) + CHIP_GAP;
		if (sui_is_released(id))
		{
			sui_text_unfocus();
			if (i == 1) { menu_screen = target; ui_create_open(); cvar_set("ui_maps_friends", "0"); }
			else if (i == 2 || i == 3) { Sty_Open(); sty_tab = i - 2; }
			else if (i == 5) { menu_screen = target; MM_MusicScan(); }
			else menu_screen = target;
		}
	}
	if (x + 66 < screensize_x)
	if (ui_button("home_quit", [screensize_x - 74, 12], '58 30 0', "quit")) localcmd("quit\n");
};

void(vector p, vector size) MH_Lobbies =
{
	local vector rp, lp, cell;
	local float i, j, li, cols, cw, row, page, tile, rows;
	local string id, s;
	sui_style_panel(p, size, 12, 1);
	sui_push_frame(p, size);
	sui_text('16 14 0', SZ_HEAD, "Public lobbies", COL_ACCENT, 1, 0);
	if (Lob_Blocked())
	{
		if (ui_button("home_terms", '16 50 0', [size_x - 32, 36], "Online is off - click to choose your terms")) menu_screen = SCREEN_TERMS;
	}
	else if (!Lob_Count())
		sui_text('16 56 0', SZ_LABEL, "Waiting for the lobby directory...", COL_DIM, 1, 0);
	else
	{
		cols = size_x >= 620 ? 2 : 1;
		cw = floor((size_x - 40) / cols);
		rows = ceil(Lob_Count() / cols);
		sui_list_view_begin("home_lobbies", '12 44 0', [size_x - 24, size_y - 56], [size_x - 38, 56], rows, mh_lscroll, [0, 4]);
		rp = '0 0 0';
		for (i = sui_list_item(rp); i > -1; i = sui_list_item(rp))
		for (j = 0; j < cols; j = j + 1)
		{
			li = i * cols + j;
			if (li >= Lob_Count()) continue;
			lp = rp + [j * (cw + 8), 0]; cell = [cw, 50];
			id = strcat("home_lob", ftos(li));
			sui_action_element(lp, cell, id, sui_noop);
			sui_roundbox(lp, cell, 8, sui_is_hovered(id) ? COL_ROW_HOVER : COL_ROW, 0.9);
			row = Lob_Row(li);
			if (row == -2) { row = ui_map_index(Lob_Map(li)); Lob_SetRow(li, row); }
			page = tile = -1;
			if (row >= 0)
			if (tokenize(bufstr_get(ms_meta, row)) > MT_UUID)
			{
				if (argv(MT_PAGE) != "-") page = stof(argv(MT_PAGE));
				if (argv(MT_CELL) != "-") tile = stof(argv(MT_CELL));
			}
			ui_thumb(lp + '3 3 0', '78 44 0', page, tile);
			s = sprintf("%g / %g", Lob_Players(li), Lob_Max(li));
			sui_text(lp + '90 6 0', SZ_LABEL, ui_fit_text(Lob_Title(li), cw - 100, SZ_LABEL), COL_TEXT, 1, 0);
			sui_text(lp + '90 29 0', '12 12 0', ui_fit_text(Lob_Map(li), cw - 148, '12 12 0'), COL_DIM, 1, 0);
			sui_text(lp + [cw - 54, 29], '12 12 0', s, SUI_THEME_GOOD, 1, 0);
			if (sui_is_released(id)) ui_connect(li);
		}
		sui_list_view_end();
	}
	sui_pop_frame();
};

void(vector p, vector size) MH_Stats =
{
	local float target, i, tier, done, total, L, count, y;
	local vector rp;
	local string s;
	sui_style_panel(p, size, 12, 1);
	sui_push_frame(p, size);
	sui_text('16 14 0', SZ_HEAD, "Your WOS stats", COL_ACCENT, 1, 0);
	if (mh_state != 2)
	{
		s = mh_state == 1 ? "Loading your stats..." : "Your stats are unavailable right now.";
		if (MH_Me() == "") s = "Finish a WOS run to start your stats. Your linked imports count in Everything.";
		if (!MF_Online()) s = "Online stats are off under your current terms.";
		ui_para('16 52 0', size_x - 32, SZ_LABEL, 20, s, COL_DIM, TRUE);
	}
	else
	{
		if (mh_native)
			s = sprintf("%g times   %g maps with times   %g WRs (%g contested)", mh_times, mh_maps, mh_wr, mh_wrc);
		else s = "WOS-only stats await a leaderboard service update.";
		sui_text('16 50 0', SZ_LABEL, ui_fit_text(s, size_x - 32, SZ_LABEL), COL_TEXT, 1, 0);
		y = 80;
		if (mh_native)
		if (ui_button("home_stats_wos", [16, y], '72 28 0', mh_source == 0 ? "[WOS]" : "WOS")) mh_source = 0;
		if (ui_button("home_stats_all", [96, y], '126 28 0', mh_source == 1 ? "[Everything]" : "Everything")) mh_source = 1;
		s = sprintf("%g / %g maps completed", mh_source ? mh_all_done : mh_wos_done, mh_total);
		sui_text([232, y + 8], '12 12 0', ui_fit_text(s, size_x - 248, '12 12 0'), COL_DIM, 1, 0);
		target = mh_source ? mh_tiers_all : mh_tiers_wos;
		if (mh_buffers_ready)
		{
			sui_list_view_begin("home_tiers", '16 120 0', [size_x - 32, max(24, size_y - 204)], [size_x - 46, 26], buf_getsize(target), mh_tscroll, [0, 4]);
			rp = '0 0 0';
			for (i = sui_list_item(rp); i > -1; i = sui_list_item(rp))
			{
				if (tokenize(bufstr_get(target, i)) != 3) continue;
				tier = stof(argv(0)); done = stof(argv(1)); total = stof(argv(2));
				sui_text(rp, SZ_LABEL, tier ? sprintf("Tier %g", tier) : "Unrated", COL_DIM, 1, 0);
				sui_roundbox(rp + '84 4 0', [max(12, size_x - 208), 8], 4, SUI_THEME_WELL, 1);
				if (done > 0 && total > 0) sui_roundbox(rp + '84 4 0', [max(4, (size_x - 208) * min(1, done / total)), 8], 4, SUI_THEME_GOOD, 1);
				sui_text(rp + [size_x - 112, 0], SZ_LABEL, sprintf("%g / %g", done, total), COL_TEXT, 1, 0);
			}
			sui_list_view_end();
		}
	}
	for (L = 0; L < 2; L = L + 1)
	{
		s = "progress unavailable";
		if (sty_pst == STY_OK && !strcmp(sty_who, sty_me) && sty_me != "" && sty_n > L)
		{
			count = 0;
			for (i = 0; i < sty_nlv[L]; i = i + 1)
			if (tokenize(bufstr_get(sty_prog[L], i)) >= 2)
			if (stof(argv(0)) > 0) count = count + 1;
			s = sprintf("%g / %g levels completed", count, sty_nlv[L]);
		}
		sui_text([16, size_y - 62 + L * 26], SZ_LABEL, strcat(L ? "Event Mode: " : "Story Mode: ", s), COL_DIM, 1, 0);
	}
	sui_pop_frame();
};

void(vector screensize) MH_Settings =
{
	local vector size, pos;
	local float v;
	size = [min(780, screensize_x - 32), min(440, screensize_y - 32)];
	pos = [floor((screensize_x - size_x) * 0.5), floor((screensize_y - size_y) * 0.5)];
	ui_backdrop(screensize);
	sui_style_panel(pos, size, 12, 1);
	sui_push_frame(pos, size);
	sui_text('24 22 0', SZ_HEAD, "Settings", COL_ACCENT, 1, 0);
	if (ui_button("home_visuals", '24 66 0', '184 36 0', "Visuals & display")) menu_screen = SCREEN_VISUALS;
	if (ui_button("home_music", '224 66 0', '150 36 0', "Music")) { menu_screen = SCREEN_MUSIC; MM_MusicScan(); }
	if (ui_button("home_privacy", '390 66 0', '250 36 0', "Privacy & online terms")) menu_screen = SCREEN_TERMS;
	v = cvar("sensitivity");
	sui_text('24 134 0', SZ_LABEL, sprintf("Mouse sensitivity: %.2f", v), COL_TEXT, 1, 0);
	if (ui_button("home_sens_down", '320 124 0', '48 32 0', "-")) cvar_set("sensitivity", ftos(max(0.1, v - 0.1)));
	if (ui_button("home_sens_up", '380 124 0', '48 32 0', "+")) cvar_set("sensitivity", ftos(min(100, v + 0.1)));
	v = cvar("volume");
	sui_text('24 182 0', SZ_LABEL, sprintf("Effects volume: %g%%", floor(v * 100 + 0.5)), COL_TEXT, 1, 0);
	if (ui_button("home_vol_down", '320 172 0', '48 32 0', "-")) cvar_set("volume", ftos(max(0, v - 0.05)));
	if (ui_button("home_vol_up", '380 172 0', '48 32 0', "+")) cvar_set("volume", ftos(min(1, v + 0.05)));
	sui_text('24 244 0', SZ_LABEL, "Use the tabs above to return to lobbies, maps or your progress.", COL_DIM, 1, 0);
	sui_pop_frame();
};

void(vector screensize) screen_home =
{
	local vector size, p;
	local float right, left, lh, fh;
	size = [min(1480, screensize_x - 32), min(800, screensize_y - 24)];
	p = [floor((screensize_x - size_x) * 0.5), floor((screensize_y - size_y) * 0.5)];
	right = min(410, floor(size_x * 0.36)); left = size_x - right - 12;
	lh = min(226, floor(size_y * 0.38));
	fh = min(206, floor(size_y * 0.36));
	MH_Lobbies(p, [left, lh]);
	MH_Stats(p + [0, lh + 12], [left, size_y - lh - 12]);
	if (mf_linkstate < 0)
	{
		sui_style_panel(p + [left + 12, 0], [right, fh], 12, 1);
		sui_text(p + [left + 28, 18], SZ_HEAD, "Friends", COL_ACCENT, 1, 0);
		if (ui_button("home_linksteam", p + [left + 28, 58], [right - 32, 38], "Click here to link your Steam"))
		{
			ui_steam_t0 = time; menu_screen = SCREEN_STEAM;
		}
		ui_para(p + [left + 28, 112], right - 32, '12 12 0', 18, "Link once on an account-enabled lobby. You can keep playing without linking.", COL_DIM, TRUE);
	}
	else MF_Draw(p + [left + 12, 0], [right, fh]);
	MC_Panel(p + [left + 12, fh + 12], [right, size_y - fh - 12], TRUE);
};
