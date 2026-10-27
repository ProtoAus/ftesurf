// Home owns the lobby overview; other tabs keep their whole content area.
float mh_req, mh_sent, mh_next, mh_state, mh_source, mh_stale;
float mh_times, mh_wr, mh_wrc, mh_maps, mh_native;
float mh_wos_done, mh_all_done, mh_total, mh_tiers_wos, mh_tiers_all, mh_buffers_ready;
float mh_lcols, mh_lrows, mh_lheight, mh_lshown, mh_tcols, mh_trows, mh_tshown;
float mh_lbottom, mh_tbottom, mh_progress_top;
float mh_thumb_width, mh_thumb_height, mh_friends_height, mh_chat_height;
float mh_spdone, mh_sptotal, mh_spknown, mh_epdone, mh_eptotal, mh_epknown;
vector mh_canvas, mh_lsize, mh_ssize;
vector mh_header_pos, mh_header_size;
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
	local float i, n, tier, slot;
	// Stable slots: tiers1..8, Unrated, then any higher catalogue tiers.
	bufstr_set(target, 8, "");
	tiers = json_find_object_child(node, "tiers");
	// MENU min's tail is varargs: convert the integer JSON length first.
	n = json_get_length(tiers);
	n = min(16, n);
	for (i = 0; i < n; i = i + 1)
	{
		row = json_get_child_at_index(tiers, i);
		tier = json_get_float(json_find_object_child(row, "tier"));
		if (tier < 1 || tier > 16) continue;
		slot = tier <= 8 ? tier - 1 : tier;
		bufstr_set(target, slot, sprintf("%g %g %g", tier,
			json_get_float(json_find_object_child(row, "done")), json_get_float(json_find_object_child(row, "of"))));
	}
	row = json_find_object_child(node, "unrated");
	if (row) bufstr_set(target, 8, sprintf("0 %g %g", json_get_float(json_find_object_child(row, "done")), json_get_float(json_find_object_child(row, "of"))));
};

void() MH_Failed =
{
	mh_stale = TRUE;
	if (mh_state != 2) mh_state = 3;
};

float(float reqid, float code, string body) MH_Reply =
{
	local int root, c, wos;
	if (!mh_req || reqid != mh_req) return FALSE;
	mh_req = 0;
	mh_next = time + 60;
	if (code || strlen(body) > 131072) { MH_Failed(); return TRUE; }
	root = json_parse(body);
	if (!root) { MH_Failed(); return TRUE; }
	if (strcmp(json_get_string(json_find_object_child(root, "who")), mh_who))
	{
		json_free(root); MH_Failed(); return TRUE;
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
	mh_state = 2; mh_stale = FALSE;
	json_free(root);
	return TRUE;
};

void() MH_Poll =
{
	local string who;
	if (mh_req)
	if (time - mh_sent > 12) { mh_req = 0; MH_Failed(); mh_next = time + 30; }
	if (!menu_active || menu_screen != SCREEN_MAIN || !MF_Online()) return;
	Lob_Poll();
	Sty_Prefetch();
	who = MH_Me();
	if (who == "") return;
	if (strcmp(who, mh_who))
	{
		strunzone(mh_who); mh_who = strzone(who);
		mh_req = mh_state = mh_next = mh_stale = 0;
	}
	if (strcmp(who, sty_who)) Sty_View(who);
	Sty_Poll();
	if (mh_req || time < mh_next) return;
	mh_req = Sty_Get(sprintf("player=%s&limit=1", who));
	mh_sent = time;
	if (mh_state != 2) mh_state = 1;
	if (!mh_req) { MH_Failed(); mh_next = time + 30; }
};

vector(vector screensize) MH_ShellSize =
{
	return [min(1660, screensize_x - 24), min(988, screensize_y - 24)];
};

vector(vector screensize) MH_ShellOrigin =
{
	local vector size;
	size = MH_ShellSize(screensize);
	return [floor((screensize_x - size_x) * 0.5), floor((screensize_y - size_y) * 0.5)];
};

void(vector screensize) MH_Tabs =
{
	local float x, i, target, on;
	local string id, label;
	local vector pos;
	pos = MH_ShellOrigin(screensize);
	screensize = MH_ShellSize(screensize);
	mh_header_pos = pos; mh_header_size = [screensize_x, 56];
	sui_style_panel(pos, [screensize_x, 56], 12, 1);
	sui_push_frame(pos, [screensize_x, 56]);
	sui_text('16 16 0', SZ_HEAD, screensize_x >= 1040 ? "WORLD OF SURF" : "WOS", COL_ACCENT, 1, 0);
	x = screensize_x >= 1040 ? 208 : 80;
	for (i = 0; i < 6; i = i + 1)
	{
		label = i == 0 ? "Lobbies" : (i == 1 ? "Maps" : (i == 2 ? "Story Mode" : (i == 3 ? "Event Mode" : (i == 4 ? "Settings" : "Music"))));
		target = i == 0 ? SCREEN_MAIN : (i == 1 ? SCREEN_CREATE : (i <= 3 ? SCREEN_STORY : (i == 4 ? SCREEN_SETTINGS : SCREEN_MUSIC)));
		on = (menu_screen == target);
		if (i == 4 && menu_screen == SCREEN_VISUALS) on = TRUE;
		if (i == 2 || i == 3) on = (menu_screen == SCREEN_STORY && sty_tab == i - 2);
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
	if (menu_screen == SCREEN_MAIN) MU_HomeHint([x + 8, 10], screensize_x - x - 100);
	if (x + 66 < screensize_x)
	if (ui_button("home_quit", [screensize_x - 74, 12], '58 30 0', "quit")) localcmd("quit\n");
	sui_pop_frame();
};

// Fit the complete directory, never a virtualized window into it.
vector(float width, float available, float count) MH_LobbyGrid =
{
	local float cols, rows, h, minimum;
	count = max(1, count);
	minimum = count <= 16 ? 54 : 34;
	cols = min(count, max(1, min(3, floor((width - 26) / (width < 720 ? 190 : 230)))));
	rows = ceil(count / cols);
	if (rows * minimum > available - 56)
		cols = min(count, max(cols, ceil(count / max(1, floor((available - 56) / minimum)))));
	rows = ceil(count / cols);
	h = max(18, floor((available - 50) / rows) - 6);
	return [cols, rows, h];
};

void(vector p, vector size) MH_Lobbies =
{
	local vector lp, cell, picture;
	local float li, cw, row, page, tile, gr, gc, tx, thumb, countw;
	local string id, s;
	mh_lsize = size; mh_lshown = mh_lbottom = 0;
	mh_thumb_width = mh_thumb_height = 0;
	sui_style_panel(p, size, 12, 1);
	sui_push_frame(p, size);
	sui_text('16 12 0', SZ_HEAD, sprintf("Public lobbies  %g", Lob_Count()), COL_ACCENT, 1, 0);
	if (Lob_Blocked())
	{
		if (ui_button("home_terms", '16 48 0', [size_x - 32, 34], "Online is off - click to choose your terms")) menu_screen = SCREEN_TERMS;
	}
	else if (!Lob_Count())
		sui_text('16 54 0', SZ_LABEL, "Waiting for the lobby directory...", COL_DIM, 1, 0);
	else
	{
		cw = floor((size_x - 32 - 6 * (mh_lcols - 1)) / mh_lcols);
		for (li = 0; li < Lob_Count(); li = li + 1)
		{
			gr = floor(li / mh_lcols); gc = li - gr * mh_lcols;
			lp = [16 + gc * (cw + 6), 44 + gr * (mh_lheight + 6)]; cell = [cw, mh_lheight];
			id = strcat("home_lob", ftos(li));
			sui_action_element(lp, cell, id, sui_noop);
			sui_roundbox(lp, cell, 7, sui_is_hovered(id) ? COL_ROW_HOVER : COL_ROW, 0.95);
			tx = 8;
			thumb = (mh_lheight >= 42 && cw >= 140);
			if (thumb)
			{
				row = Lob_Row(li);
				if (row == -2) { row = ui_map_index(Lob_Map(li)); Lob_SetRow(li, row); }
				page = tile = -1;
				if (row >= 0)
				if (tokenize(bufstr_get(ms_meta, row)) > MT_UUID)
				{
					if (argv(MT_PAGE) != "-") page = stof(argv(MT_PAGE));
					if (argv(MT_CELL) != "-") tile = stof(argv(MT_CELL));
				}
				picture = '0 0 0';
				picture_y = min(mh_lheight - 12, floor(min(192, cw * 0.46) * 9 / 16));
				picture_x = floor(picture_y * 16 / 9);
				ui_thumb(lp + [6, floor((mh_lheight - picture_y) * 0.5)], picture, page, tile);
				tx = picture_x + 16;
				mh_thumb_width = picture_x; mh_thumb_height = picture_y;
			}
			s = sprintf("%g/%g", Lob_Players(li), Lob_Max(li));
			countw = min(cw - 16, stringwidth(s, TRUE, '12 12 0'));
			if (cw < 90) { s = ""; countw = 0; }
			if (thumb)
			{
				sui_text(lp + [tx, 24], '12 12 0', s, Lob_Players(li) ? SUI_THEME_GOOD : COL_DIM, 1, 0);
				sui_text(lp + [tx, 6], '12 12 0', ui_fit_text(Lob_Title(li), cw - tx - 8, '12 12 0'), COL_TEXT, 1, 0);
			}
			else
			{
				sui_text(lp + [cw - countw - 7, mh_lheight < 34 ? 2 : 5], '12 12 0', s, Lob_Players(li) ? SUI_THEME_GOOD : COL_DIM, 1, 0);
				s = (cw < 150 || mh_lheight < 28) ? sprintf("#%g", li + 1) : Lob_Title(li);
				sui_text(lp + [tx, mh_lheight < 34 ? 2 : 5], '12 12 0', ui_fit_text(s, cw - tx - countw - 6, '12 12 0'), COL_TEXT, 1, 0);
			}
			if (mh_lheight >= 28 && cw >= 90)
				sui_text(lp + [tx, mh_lheight - (thumb ? 16 : 14)], '12 12 0', ui_fit_text(Lob_Map(li), cw - tx - 8, '12 12 0'), COL_DIM, 1, 0);
			mh_lshown = mh_lshown + 1;
			mh_lbottom = max(mh_lbottom, lp_y + cell_y);
			if (sui_is_released(id)) ui_connect(li);
		}
	}
	sui_pop_frame();
};

void(vector p, vector size, string label, string value) MH_Figure =
{
	local vector textsize;
	textsize = size_y < 44 ? '16 16 0' : '24 24 0';
	sui_roundbox(p, size, 8, SUI_THEME_WELL, 0.85);
	sui_text(p + '8 3 0', '12 12 0', ui_fit_text(label, size_x - 16, '12 12 0'), COL_DIM, 1, 0);
	sui_text(p + [8, size_y - textsize_y - 3], textsize, ui_fit_text(value, size_x - 16, textsize), COL_TEXT, 1, 0);
};

void(vector p, vector size, float L) MH_Progress =
{
	local float i, count, known, total;
	local string s;
	known = FALSE; count = total = 0;
	if (sty_pst == STY_OK && !strcmp(sty_who, sty_me) && sty_me != "" && sty_n > L)
	{
		known = TRUE; total = sty_nlv[L];
		for (i = 0; i < total; i = i + 1)
		if (tokenize(bufstr_get(sty_prog[L], i)) >= 2)
		if (stof(argv(0)) > 0) count = count + 1;
	}
	if (L == 0) { mh_spdone = count; mh_sptotal = total; mh_spknown = known; }
	else { mh_epdone = count; mh_eptotal = total; mh_epknown = known; }
	sui_roundbox(p, size, 8, SUI_THEME_WELL, 0.85);
	s = known ? sprintf("%g / %g levels", count, total) : "-- / -- levels";
	sui_text(p + '8 5 0', '12 12 0', L ? "Event Mode" : "Story Mode", COL_ACCENT, 1, 0);
	sui_text(p + [8, size_y - 16], '12 12 0', s, COL_TEXT, 1, 0);
	if (size_x > 240)
	{
		sui_roundbox(p + [126, size_y - 17], [size_x - 138, 5], 2, SUI_THEME_PANEL, 1);
		if (known && count > 0)
		if (total > 0) sui_roundbox(p + [126, size_y - 17], [(size_x - 138) * min(1, count / total), 5], 2, SUI_THEME_GOOD, 1);
	}
};

void(vector p, vector size) MH_Stats =
{
	local float target, i, tier, done, total, known, n, rows, cols, cw, th, gy, compact, fy, fh, cy, ph, gr, gc, countw, barw;
	local vector rp, ts;
	local string s, label, value, note;
	mh_ssize = size; mh_tshown = mh_tbottom = 0;
	compact = (size_y < 320);
	fy = compact ? 36 : 44; fh = compact ? 36 : 54;
	cy = fy + fh + 8;
	gy = cy + (compact ? 22 : 28) + 8;
	ph = compact ? 36 : 54;
	mh_progress_top = size_y - ph - 10;
	sui_style_panel(p, size, 12, 1);
	sui_push_frame(p, size);
	sui_text('16 10 0', compact ? '20 20 0' : SZ_HEAD, "Your stats", COL_ACCENT, 1, 0);
	note = "";
	if (!MF_Online()) note = "Online stats off";
	else if (mh_stale) note = mh_state == 2 ? "Refresh failed - previous values" : "Stats unavailable";
	else if (mh_state == 1 || mh_req) note = "Updating...";
	else if (MH_Me() == "") note = "Link or finish a WOS run";
	else if (!mh_native) note = "WOS service update pending";
	sui_text([180, 14], '12 12 0', ui_fit_text(note, size_x - 196, '12 12 0'), COL_DIM, 1, 0);
	cw = floor((size_x - 32 - 18) / 4);
	for (i = 0; i < 4; i = i + 1)
	{
		label = i == 0 ? "WOS times" : (i == 1 ? "WOS WRs" : (i == 2 ? (mh_source ? "Completed (all)" : "Completed (WOS)") : "Contested WRs"));
		value = "--";
		if (mh_state == 2)
		{
			if (i == 2 && mh_source) value = ftos(mh_all_done);
			else if (mh_native) value = ftos(i == 0 ? mh_times : (i == 1 ? mh_wr : (i == 2 ? mh_wos_done : mh_wrc)));
		}
		MH_Figure([16 + i * (cw + 6), fy], [cw, fh], label, value);
	}
	if (mh_native)
	if (ui_button("home_stats_wos", [16, cy], [64, compact ? 22 : 28], mh_source ? "WOS" : "[WOS]")) mh_source = 0;
	if (ui_button("home_stats_all", [86, cy], [116, compact ? 22 : 28], mh_source ? "[Everything]" : "Everything"))
		if (mh_state == 2) mh_source = 1;
	s = mh_state == 2 ? sprintf("%g / %g maps", mh_source ? mh_all_done : mh_wos_done, mh_total) : "-- / -- maps";
	sui_text([212, cy + 6], '12 12 0', ui_fit_text(s, size_x - 228, '12 12 0'), COL_DIM, 1, 0);
	target = mh_source ? mh_tiers_all : mh_tiers_wos;
	n = 9;
	if (mh_buffers_ready) n = max(n, min(17, buf_getsize(target)));
	cols = 2;
	if (ceil(n / cols) * 18 > mh_progress_top - gy - 6) cols = 3;
	rows = ceil(n / cols);
	cw = floor((size_x - 32 - 8 * (cols - 1)) / cols);
	th = min(72, max(16, floor((mh_progress_top - gy - 6) / rows)));
	mh_tcols = cols; mh_trows = rows;
	for (i = 0; i < n; i = i + 1)
	{
		gr = floor(i / cols); gc = i - gr * cols;
		rp = [16 + gc * (cw + 8), gy + gr * th]; ts = [cw, th - 3];
		tier = i < 8 ? i + 1 : (i == 8 ? 0 : i);
		known = FALSE; done = total = 0;
		if (mh_state == 2 && mh_buffers_ready)
		if (i < buf_getsize(target))
		if (tokenize(bufstr_get(target, i)) == 3)
		{
			tier = stof(argv(0)); done = stof(argv(1)); total = stof(argv(2)); known = TRUE;
		}
		label = tier ? sprintf("Tier %g", tier) : "Unrated";
		s = known ? sprintf("%g / %g", done, total) : "-- / --";
		if (th >= 30)
		{
			sui_roundbox(rp, ts, 6, SUI_THEME_WELL, 0.7);
			sui_text(rp + '8 6 0', '12 12 0', label, COL_DIM, 1, 0);
			countw = stringwidth(s, TRUE, '12 12 0');
			sui_text(rp + [cw - countw - 8, 6], '12 12 0', s, COL_TEXT, 1, 0);
			rp = rp + [8, ts_y - 9]; barw = cw - 16;
		}
		else
		{
			sui_text(rp + '0 2 0', '12 12 0', label, COL_DIM, 1, 0);
			countw = stringwidth(s, TRUE, '12 12 0');
			sui_text(rp + [cw - countw, 2], '12 12 0', s, COL_TEXT, 1, 0);
			rp = rp + '54 6 0'; barw = max(8, cw - countw - 64);
		}
		sui_roundbox(rp, [barw, 4], 2, SUI_THEME_PANEL, 1);
		if (known && done > 0)
		if (total > 0) sui_roundbox(rp, [max(2, barw * min(1, done / total)), 4], 2, SUI_THEME_GOOD, 1);
		mh_tshown = mh_tshown + 1;
		mh_tbottom = max(mh_tbottom, gy + gr * th + ts_y);
	}
	cw = floor((size_x - 40) * 0.5);
	MH_Progress([16, mh_progress_top], [cw, ph], 0);
	MH_Progress([24 + cw, mh_progress_top], [cw, ph], 1);
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
	local vector size, p, grid;
	local float right, left, lh, fh, sh, count;
	size = screensize;
	p = '0 0 0';
	mh_canvas = size;
	right = min(400, max(260, floor(size_x * 0.28))); left = size_x - right - 12;
	count = Lob_Count(); if (count < 1) count = 12;
	sh = min(252, max(210, floor(size_y * 0.27)));
	lh = size_y - sh - 12;
	grid = MH_LobbyGrid(left, lh, count);
	mh_lcols = grid_x; mh_lrows = grid_y; mh_lheight = grid_z;
	fh = floor((size_y - 12) * 0.58);
	mh_friends_height = fh; mh_chat_height = size_y - fh - 12;
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
	else if (MFP_IsOpen()) MFP_Draw(p + [left + 12, 0], [right, fh]);
	else MF_Draw(p + [left + 12, 0], [right, fh]);
	MC_Panel(p + [left + 12, fh + 12], [right, size_y - fh - 12], TRUE);
};

void() MH_Probe =
{
	local float i, wos, all;
	wos = all = 0;
	if (mh_buffers_ready)
	for (i = 0; i < 9; i = i + 1)
	{
		if (bufstr_get(mh_tiers_wos, i) != "") wos = wos + 1;
		if (bufstr_get(mh_tiers_all, i) != "") all = all + 1;
	}
	print(sprintf("home: tierdata wos %g all %g\n", wos, all));
	print(sprintf("home: header %g,%g %gx%g body-top %g\n", mh_header_pos_x, mh_header_pos_y, mh_header_size_x, mh_header_size_y, mh_header_pos_y + 68));
	print(sprintf("home: progress story %g/%g known %g event %g/%g known %g\n", mh_spdone, mh_sptotal, mh_spknown, mh_epdone, mh_eptotal, mh_epknown));
	print(sprintf("home: canvas %gx%g lobby %g/%g cols %g rows %g cell %g\n", mh_canvas_x, mh_canvas_y, mh_lshown, Lob_Count(), mh_lcols, mh_lrows, mh_lheight));
	print(sprintf("home: lobby bottom %g <= %g tiers %g cols %g rows %g bottom %g <= progress %g\n", mh_lbottom, mh_lsize_y, mh_tshown, mh_tcols, mh_trows, mh_tbottom, mh_progress_top));
	print(sprintf("home: stats %gx%g state %g source %g native %g stale %g\n", mh_ssize_x, mh_ssize_y, mh_state, mh_source, mh_native, mh_stale));
	print(sprintf("home: thumb %gx%g friends %g chat %g lobby height %g\n", mh_thumb_width, mh_thumb_height, mh_friends_height, mh_chat_height, mh_lsize_y));
};
