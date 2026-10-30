// Home and the browsers share one persistent Friends/chat column.
float mh_req, mh_sent, mh_next, mh_state, mh_source, mh_stale;
float mh_source_picked;         // P1084: the player chose a source this session
float mh_times, mh_wr, mh_wrc, mh_maps, mh_native;
float mh_wos_done, mh_all_done, mh_total, mh_tiers_wos, mh_tiers_all, mh_buffers_ready;
// P1122: per kind (0 all, 1 surf, 2 bhop, as cl_profile's pf_cm); the tier tables hold MH_TSLOTS
// slots a kind. mh_mode is the kind on show; mh_modes_has, the reply carried the kinds.
#define MH_TSLOTS 17
float mh_mode, mh_modes_has;
var float mh_mode_slide = 2;         // P1130: All's initial knob position, not Surf's
float mh_kwos[3], mh_kall[3], mh_kof[3], mh_ktimes[3], mh_kwr[3], mh_kwrc[3];
float mh_lcols, mh_lrows, mh_lheight, mh_lshown, mh_tcols, mh_trows, mh_tshown;
float mh_lbottom, mh_tbottom, mh_progress_top;
float mh_thumb_width, mh_thumb_height, mh_friends_height, mh_chat_height;
float mh_spdone, mh_sptotal, mh_spknown, mh_epdone, mh_eptotal, mh_epknown;
vector mh_canvas, mh_lsize, mh_ssize;
vector mh_header_pos, mh_header_size;
vector mh_content_size, mh_sidebar_pos, mh_sidebar_size;
string mh_who;

// Bounded to the visible large cards; dense directories keep atlas thumbnails.
#define MH_SHOT_MAX 16
float mh_shots, mh_shot_keys, mh_shots_ready, mh_roster_rows;
float mh_shot_seen[MH_SHOT_MAX], mh_shot_remotev[MH_SHOT_MAX];
float mh_shot_ready, mh_shot_remote, mh_shot_local, mh_shot_pixels;
float mh_shot_shaderid, mh_shot_decodew, mh_shot_decodeh;

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

void(int node, float target, float base) MH_ReadTiers =
{
	local int tiers, row;
	local float i, n, tier, slot, rest;
	// Stable slots: tiers1..8, Unrated, then any higher catalogue tiers; `base` is the kind's first.
	bufstr_set(target, base + 8, "");
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
		bufstr_set(target, base + slot, sprintf("%g %g %g", tier,
			json_get_float(json_find_object_child(row, "done")), json_get_float(json_find_object_child(row, "of"))));
	}
	// P1122: the service sends `untiered` (a count), not an object: finished = done - the tiers'
	// done, as cl_profile's page reads it. It was "-- / --" here.
	if (json_find_object_child(node, "untiered"))
	{
		rest = json_get_float(json_find_object_child(node, "done"));
		for (i = 0; i < n; i = i + 1)
			rest = rest - json_get_float(json_find_object_child(json_get_child_at_index(tiers, i), "done"));
		bufstr_set(target, base + 8, sprintf("0 %g %g", max(0, rest),
			json_get_float(json_find_object_child(node, "untiered"))));
	}
	row = json_find_object_child(node, "unrated");
	if (row) bufstr_set(target, base + 8, sprintf("0 %g %g", json_get_float(json_find_object_child(row, "done")), json_get_float(json_find_object_child(row, "of"))));
};

// P1122: a completion object's surf and bhop tables into kinds 1 and 2, and every kind's
// done (and, from Everything's, of) figures; kind 0 is the object itself.
void(int c, float target, float isall) MH_ReadKinds =
{
	local int modes, m;
	local float k;
	if (isall) mh_kall[0] = json_get_float(json_find_object_child(c, "done"));
	else mh_kwos[0] = json_get_float(json_find_object_child(c, "done"));
	if (isall) mh_kof[0] = json_get_float(json_find_object_child(c, "of"));
	modes = json_find_object_child(c, "modes");
	if (isall) mh_modes_has = (json_get_length(modes) > 0);
	for (k = 1; k < 3; k = k + 1)
	{
		m = json_find_object_child(modes, (k == 1) ? "surf" : "bhop");
		MH_ReadTiers(m, target, k * MH_TSLOTS);
		if (isall) mh_kall[k] = json_get_float(json_find_object_child(m, "done"));
		else mh_kwos[k] = json_get_float(json_find_object_child(m, "done"));
		if (isall) mh_kof[k] = json_get_float(json_find_object_child(m, "of"));
	}
};

// P1122: figs.wos by kind (any, surf, bhop); without them kind 0 keeps the top-level `wos`.
void(int f) MH_ReadFigs =
{
	local int k;
	local float i;
	mh_ktimes[0] = mh_times; mh_kwr[0] = mh_wr; mh_kwrc[0] = mh_wrc;
	mh_ktimes[1] = mh_ktimes[2] = mh_kwr[1] = mh_kwr[2] = mh_kwrc[1] = mh_kwrc[2] = 0;
	if (!f) return;
	for (i = 0; i < 3; i = i + 1)
	{
		k = json_find_object_child(f, (i == 0) ? "any" : ((i == 1) ? "surf" : "bhop"));
		if (!k) continue;
		mh_ktimes[i] = json_get_float(json_find_object_child(k, "n"));
		mh_kwr[i] = json_get_float(json_find_object_child(k, "wr"));
		mh_kwrc[i] = json_get_float(json_find_object_child(k, "wrc"));
	}
};

// P1122: a kind's tier slots in use (at least the nine fixed ones), from `target`.
float(float target, float k) MH_TierCount =
{
	local float i, n;
	n = 9;
	if (!mh_buffers_ready) return n;
	for (i = 9; i < MH_TSLOTS; i = i + 1)
		if (bufstr_get(target, k * MH_TSLOTS + i) != "")
			n = i + 1;
	return n;
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
	MH_ReadTiers(c, mh_tiers_all, 0);
	MH_ReadKinds(c, mh_tiers_all, TRUE);
	c = json_find_object_child(root, "completion_wos");
	mh_native = (json_get_length(c) > 0);
	// P1084: World of Surf unless the player picked Everything; a reply without
	// WOS figures (an older service) can only show Everything.
	if (!mh_native) mh_source = 1;
	else if (!mh_source_picked) mh_source = 0;
	mh_wos_done = json_get_float(json_find_object_child(c, "done"));
	MH_ReadTiers(c, mh_tiers_wos, 0);
	MH_ReadKinds(c, mh_tiers_wos, FALSE);
	wos = json_find_object_child(root, "wos");
	mh_times = json_get_float(json_find_object_child(wos, "n"));
	mh_maps = json_get_float(json_find_object_child(wos, "maps"));
	mh_wr = json_get_float(json_find_object_child(wos, "wr"));
	mh_wrc = json_get_float(json_find_object_child(wos, "wrc"));
	MH_ReadFigs(json_find_object_child(json_find_object_child(root, "figs"), "wos"));
	if (!mh_modes_has) mh_mode = 0;
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
	return [min(1660, screensize_x - 24), min(972, screensize_y - 56)];
};

vector(vector screensize) MH_ShellOrigin =
{
	local vector size;
	size = MH_ShellSize(screensize);
	return [floor((screensize_x - size_x) * 0.5), 44 + floor((screensize_y - 56 - size_y) * 0.5)];
};

void(vector screensize) MH_Tabs =
{
	local float x, w, total, i, target, on;
	local string id, label;
	local vector pos, textsize;
	pos = MH_ShellOrigin(screensize);
	screensize = MH_ShellSize(screensize);
	mh_header_pos = pos; mh_header_size = [screensize_x, screensize_x < 900 ? 32 : 40];
	textsize = screensize_x < 900 ? '24 24 0' : '32 32 0';
	Font_Set(ui_font_display);
	total = -28;
	for (i = 0; i < 6; i = i + 1)
	{
		label = i == 0 ? "LOBBIES" : (i == 1 ? "MAPS" : (i == 2 ? "STORY" : (i == 3 ? "EVENT" : (i == 4 ? "SETTINGS" : "QUIT"))));
		total = total + stringwidth(label, TRUE, textsize) + 28;
	}
	x = max(4, floor((screensize_x - total) * 0.5));
	sui_push_frame(pos, mh_header_size);
	for (i = 0; i < 6; i = i + 1)
	{
		label = i == 0 ? "LOBBIES" : (i == 1 ? "MAPS" : (i == 2 ? "STORY" : (i == 3 ? "EVENT" : (i == 4 ? "SETTINGS" : "QUIT"))));
		target = i == 0 ? SCREEN_MAIN : (i == 1 ? SCREEN_CREATE : (i <= 3 ? SCREEN_STORY : SCREEN_SETTINGS));
		on = (menu_screen == target);
		if (i == 4 && menu_screen == SCREEN_VISUALS) on = TRUE;
		if (i == 0 && menu_screen == SCREEN_STATS) on = TRUE;       // P1084: opened from the Lobbies home
		if (i == 2 || i == 3) on = (menu_screen == SCREEN_STORY && sty_tab == i - 2);
		if (i == 5) on = FALSE;
		id = i == 5 ? "home_quit" : strcat("home_tab", ftos(i));
		w = stringwidth(label, TRUE, textsize);
		sui_action_element([x - 6, 0], [w + 12, mh_header_size_y], id, sui_noop);
		sui_text([x, floor((mh_header_size_y - textsize_y) * 0.5)], textsize, label, '1 1 1', 1, 0);
		if (on || sui_is_hovered(id)) sui_fill([x, mh_header_size_y - 2], [w, 2], '1 1 1', 1, 0);
		x = x + w + 28;
		if (!sui_is_released(id)) continue;
		sui_text_unfocus();
		if (i == 1) { menu_screen = target; ui_create_open(); }
		else if (i == 2 || i == 3) { Sty_Open(); sty_tab = i - 2; }
		else if (i == 5) { if (!ui_synth()) localcmd("quit\n"); }
		else menu_screen = target;
	}
	sui_pop_frame();
	Font_Set(ui_font_ui);
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

void(float slot) MH_ShotRelease =
{
	local float i, shared;
	local string old;
	old = strzone(bufstr_get(mh_shots, slot));
	bufstr_set(mh_shots, slot, "");
	bufstr_set(mh_shot_keys, slot, "");
	mh_shot_remotev[slot] = FALSE;
	shared = FALSE;
	for (i = 0; i < MH_SHOT_MAX; i = i + 1)
		if (!strcmp(bufstr_get(mh_shots, i), old)) shared = TRUE;
	if (strlen(old) && !shared) free_pic(old);
	strunzone(old);
};

// Native async pictures start from the directory's map name, not a later catalogue.
// Never draw an unready URL: drawpic's missing-texture substitution is visible.
float(float slot, string mapname, float row, vector pos, vector size) MH_Shot =
{
	local string uuid, want, key, frozen, texture;
	local vector ready;
	if (slot >= MH_SHOT_MAX || slot < 0) return FALSE;
	if (!checkbuiltin(drawgetimagesize_async)) return FALSE;
	if (!mh_shots_ready)
	{
		mh_shots = buf_create(); mh_shot_keys = buf_create();
		mh_shots_ready = TRUE;
	}
	mh_shot_seen[slot] = time;
	key = sprintf("%s:%g:%g", mapname, row, ms_consent >= FS_TERMS_ONLINE);
	if (strcmp(bufstr_get(mh_shot_keys, slot), key))
	{
		// Filesystem probes belong on a map/consent change, never each frame.
		key = strzone(key); frozen = strzone(mapname);
		MH_ShotRelease(slot);
		bufstr_set(mh_shot_keys, slot, key);
		strunzone(key);
		want = "";
		if (row >= 0)
		if (tokenize(bufstr_get(ms_meta, row)) > MT_UUID)
		{
			uuid = argv(MT_UUID);
			if (ui_bguuid(uuid))
			{
				want = ui_bgprobe(uuid, "small");
				if (!strlen(want)) want = ui_bgpick(uuid, 384);
			}
		}
		if (!strlen(want))
		if (ms_consent >= FS_TERMS_ONLINE)
		if (Mdl_Made(frozen, MDL_NAMECH, 64))
		{
			texture = strcat("https://proto.bar/ftesurf/board/shot/", strtolower(frozen));
			want = strcat("menulobby/", digest_hex("SHA256", texture));
			// HTTP is an image-map ident, not a cachepic/material filename.
			mh_shot_shaderid = shaderforname(want, sprintf("{\naffine\nnomipmaps\ndiffusemap \"%s\"\nprogram default2d\n{\nmap $diffuse\nblendfunc blend\n}\nsort additive\n}\n", texture));
			mh_shot_remotev[slot] = TRUE;
		}
		bufstr_set(mh_shots, slot, want);
		strunzone(frozen);
	}
	want = bufstr_get(mh_shots, slot);
	if (!strlen(want)) return FALSE;
	ready = drawgetimagesize_async(want);
	mh_shot_decodew = ready_x; mh_shot_decodeh = ready_y;
	if (ready_x < max(256, size_x) || ready_y < max(144, size_y)) return FALSE;
	sui_pic(pos, size, want, '1 1 1', 1, 0);
	mh_shot_ready = mh_shot_ready + 1;
	if (mh_shot_remotev[slot]) mh_shot_remote = mh_shot_remote + 1;
	else mh_shot_local = mh_shot_local + 1;
	if (mh_shot_pixels <= 0 || ready_x < mh_shot_pixels) mh_shot_pixels = ready_x;
	return TRUE;
};

void(vector p, vector size) MH_Lobbies =
{
	local vector lp, cell, picture, titlefont, mapfont;
	local float li, cw, row, page, tile, gr, gc, tx, thumb, countw, texty, grouped;
	local string id, s;
	mh_lsize = size; mh_lshown = mh_lbottom = 0;
	mh_thumb_width = mh_thumb_height = 0;
	mh_shot_ready = mh_shot_remote = mh_shot_local = mh_shot_pixels = 0;
	if (mh_roster_rows != ms_count)
	{
		for (li = 0; li < Lob_Count(); li = li + 1) Lob_SetRow(li, -2);
		mh_roster_rows = ms_count;
	}
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
				if (!MH_Shot(li, Lob_Map(li), row, lp + [6, floor((mh_lheight - picture_y) * 0.5)], picture))
					ui_thumb(lp + [6, floor((mh_lheight - picture_y) * 0.5)], picture, page, tile);
				tx = picture_x + 16;
				mh_thumb_width = picture_x; mh_thumb_height = picture_y;
			}
			s = sprintf("%g/%g", Lob_Players(li), Lob_Max(li));
			countw = min(cw - 16, stringwidth(s, TRUE, '12 12 0'));
			if (cw < 90) { s = ""; countw = 0; }
			grouped = (thumb && mh_lheight >= 74);
			if (grouped)
			{
				// P1084: baked UI rungs only (sh_font.qc FONT_UI_SIZES); 14 px was resampled.
				texty = max(6, floor((mh_lheight - 56) * 0.5));
				titlefont = '16 16 0'; mapfont = '16 16 0';
				sui_text(lp + [tx, texty], titlefont, ui_fit_text(Lob_Title(li), cw - tx - 8, titlefont), COL_ACCENT, 1, 0);
				sui_text(lp + [tx, texty + 20], mapfont, ui_fit_text(Lob_Map(li), cw - tx - 8, mapfont), COL_TEXT, 1, 0);
				sui_text(lp + [tx, texty + 40], '16 16 0', ui_fit_text(strcat(s, " players"), cw - tx - 8, '16 16 0'), Lob_Players(li) ? SUI_THEME_GOOD : COL_DIM, 1, 0);
			}
			else if (thumb)
			{
				texty = max(4, floor((mh_lheight - 32) * 0.5));
				sui_text(lp + [tx, texty], '16 16 0', ui_fit_text(Lob_Title(li), cw - tx - countw - 14, '16 16 0'), COL_TEXT, 1, 0);
				sui_text(lp + [cw - countw - 7, texty + 2], '12 12 0', s, Lob_Players(li) ? SUI_THEME_GOOD : COL_DIM, 1, 0);
				sui_text(lp + [tx, texty + 20], '12 12 0', ui_fit_text(Lob_Map(li), cw - tx - 8, '12 12 0'), COL_DIM, 1, 0);
			}
			else
			{
				sui_text(lp + [cw - countw - 7, mh_lheight < 34 ? 2 : 5], '12 12 0', s, Lob_Players(li) ? SUI_THEME_GOOD : COL_DIM, 1, 0);
				s = (cw < 150 || mh_lheight < 28) ? sprintf("#%g", li + 1) : Lob_Title(li);
				sui_text(lp + [tx, mh_lheight < 34 ? 2 : 5], '12 12 0', ui_fit_text(s, cw - tx - countw - 6, '12 12 0'), COL_TEXT, 1, 0);
			}
			if (!thumb && mh_lheight >= 28 && cw >= 90)
				sui_text(lp + [tx, mh_lheight - 14], '12 12 0', ui_fit_text(Lob_Map(li), cw - tx - 8, '12 12 0'), COL_DIM, 1, 0);
			mh_lshown = mh_lshown + 1;
			mh_lbottom = max(mh_lbottom, lp_y + cell_y);
			if (sui_is_released(id)) ui_connect(li);
		}
	}
	if (mh_shots_ready)
	for (li = 0; li < MH_SHOT_MAX; li = li + 1)
		if (time - mh_shot_seen[li] > 3)
		if (strlen(bufstr_get(mh_shots, li))) MH_ShotRelease(li);
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

// P1104: client/cl_profile.qc's switch, compiled later.
float(string id, vector pos, vector sz, string left, string right, float onright, float tsz, float *slide) Profile_Switch;
float(string id, vector pos, vector sz, string a, string b, string c, float on, float tsz, float *slide) Profile_Switch3;
float(float kind) Profile_KindPlace;
float(float place) Profile_PlaceKind;
float mh_sw_slide;

void(vector p, vector size) MH_Stats =
{
	local float target, i, tier, done, total, known, n, rows, cols, cw, th, gy, compact, fy, fh, cy, ph, gr, gc, countw, barw, x, srcw, kindw;
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
	// P1084: the whole panel opens hud_player's Stats page; the switch drawn later wins its clicks.
	sui_action_element('0 0 0', size, "home_stats_open", sui_noop);
	s = "Full stats";
	sui_text([size_x - 16 - stringwidth(s, TRUE, '12 12 0'), 14], '12 12 0', s,
	         sui_is_hovered("home_stats_open") ? COL_ACCENT : COL_DIM, 1, 0);
	sui_text('16 10 0', compact ? '20 20 0' : SZ_HEAD, "Your stats", COL_ACCENT, 1, 0);
	note = "";
	if (!MF_Online()) note = "Online stats off";
	else if (mh_stale) note = mh_state == 2 ? "Refresh failed - previous values" : "Stats unavailable";
	else if (mh_state == 1 || mh_req) note = "Updating...";
	else if (MH_Me() == "") note = "Link or finish a WOS run";
	else if (!mh_native) note = "WOS service update pending";
	sui_text([180, 14], '12 12 0', ui_fit_text(note, size_x - 196 - stringwidth("Full stats", TRUE, '12 12 0') - 12, '12 12 0'), COL_DIM, 1, 0);
	cw = floor((size_x - 32 - 18) / 4);
	for (i = 0; i < 4; i = i + 1)
	{
		label = i == 0 ? "WOS times" : (i == 1 ? "WOS WRs" : (i == 2 ? (mh_source ? "Completed (all)" : "Completed (WOS)") : "Contested WRs"));
		value = "--";
		if (mh_state == 2)
		{
			if (i == 2 && mh_source) value = ftos(mh_kall[mh_mode]);
			else if (mh_native) value = ftos(i == 0 ? mh_ktimes[mh_mode] : (i == 1 ? mh_kwr[mh_mode] : (i == 2 ? mh_kwos[mh_mode] : mh_kwrc[mh_mode])));
		}
		MH_Figure([16 + i * (cw + 6), fy], [cw, fh], label, value);
	}
	// P1104: one switch (it was two bracketed buttons). World of Surf needs the native figures,
	// Everything an answer.
	// P1130: keep both switches inside the card even at narrow virtual viewports.
	srcw = mh_modes_has ? min(220, floor((size_x - 40) * 0.56)) : min(220, size_x - 32);
	kindw = min(168, size_x - 40 - srcw);
	x = 16 + srcw;
	if (Profile_Switch("home_stats_src", [16, cy], [srcw, compact ? 22 : 26], "World of Surf", "Everything",
	                   mh_source, 12, &mh_sw_slide))
	{
		if (mh_source && mh_native) { mh_source = 0; mh_source_picked = TRUE; }
		else if (!mh_source && mh_state == 2) { mh_source = 1; mh_source_picked = TRUE; }
	}
	x = x + 8;
	// P1122 (Lex): Surf / Bhop / All, for every figure and tier row below.
	if (mh_modes_has)
	{
		i = Profile_Switch3("home_stats_kind", [x, cy], [kindw, compact ? 22 : 26], "Surf", "Bhop", "All",
		                    Profile_KindPlace(mh_mode), 12, &mh_mode_slide);
		if (i >= 0) mh_mode = Profile_PlaceKind(i);
		x = x + kindw + 12;
	}
	else
		x = x + 4;
	s = mh_state == 2 ? sprintf("%g / %g maps", mh_source ? mh_kall[mh_mode] : mh_kwos[mh_mode], mh_kof[mh_mode]) : "-- / -- maps";
	if (size_x - x - 16 > 0)
		sui_text([x, cy + 6], '12 12 0', ui_fit_text(s, size_x - x - 16, '12 12 0'), COL_DIM, 1, 0);
	target = mh_source ? mh_tiers_all : mh_tiers_wos;
	n = MH_TierCount(target, mh_mode);
	// P1104: as many columns (up to 4) as it takes for the rows to clear the progress boxes;
	// Tier 9 and 10 were drawn under Story Mode with three.
	cols = 2;
	while (cols < 4 && ceil(n / cols) * 15 > mh_progress_top - gy - 4)
		cols = cols + 1;
	rows = ceil(n / cols);
	cw = floor((size_x - 32 - 8 * (cols - 1)) / cols);
	th = min(72, max(15, floor((mh_progress_top - gy - 4) / rows)));
	mh_tcols = cols; mh_trows = rows;
	for (i = 0; i < n; i = i + 1)
	{
		gr = floor(i / cols); gc = i - gr * cols;
		rp = [16 + gc * (cw + 8), gy + gr * th]; ts = [cw, th - 3];
		tier = i < 8 ? i + 1 : (i == 8 ? 0 : i);
		known = FALSE; done = total = 0;
		if (mh_state == 2 && mh_buffers_ready)
		if (tokenize(bufstr_get(target, mh_mode * MH_TSLOTS + i)) == 3)
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
	if (sui_is_released("home_stats_open")) MStats_Open();
};

void(vector screensize) MH_Settings =
{
	local vector size, pos;
	local float v;
	size = [min(780, screensize_x - 32), min(440, screensize_y - 32)];
	pos = [floor((screensize_x - size_x) * 0.5), floor((screensize_y - size_y) * 0.5)];
	sui_style_panel(pos, size, 12, 1);
	sui_push_frame(pos, size);
	sui_text('24 22 0', SZ_HEAD, "Settings", COL_ACCENT, 1, 0);
	if (ui_button("home_visuals", '24 66 0', '184 36 0', "Visuals & display")) menu_screen = SCREEN_VISUALS;
	if (ui_button("home_privacy", '224 66 0', '250 36 0', "Privacy & online terms")) menu_screen = SCREEN_TERMS;
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

vector(vector size) MH_ContentSize =
{
	return [size_x - min(400, max(260, floor(size_x * 0.28))) - 12, size_y];
};

void(vector screensize) screen_home =
{
	local vector size, p, grid, content;
	local float left, lh, sh, count;
	size = screensize;
	p = '0 0 0';
	mh_canvas = size;
	content = MH_ContentSize(size); left = content_x;
	count = Lob_Count(); if (count < 1) count = 12;
	sh = min(252, max(210, floor(size_y * 0.27)));
	lh = size_y - sh - 12;
	grid = MH_LobbyGrid(left, lh, count);
	mh_lcols = grid_x; mh_lrows = grid_y; mh_lheight = grid_z;
	MH_Lobbies(p, [left, lh]);
	MH_Stats(p + [0, lh + 12], [left, size_y - lh - 12]);
};

void(vector size) MH_Sidebar =
{
	local vector p, content;
	local float left, right, fh;
	p = '0 0 0'; content = MH_ContentSize(size);
	left = content_x; right = size_x - left - 12;
	fh = floor((size_y - 12) * 0.58);
	mh_canvas = size; mh_content_size = content;
	mh_sidebar_pos = [left + 12, 0]; mh_sidebar_size = [right, size_y];
	mh_friends_height = fh; mh_chat_height = size_y - fh - 12;
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
		if (bufstr_get(mh_tiers_wos, mh_mode * MH_TSLOTS + i) != "") wos = wos + 1;
		if (bufstr_get(mh_tiers_all, mh_mode * MH_TSLOTS + i) != "") all = all + 1;
	}
	print(sprintf("home: tierdata wos %g all %g kind %g kinds %g\n", wos, all, mh_mode, mh_modes_has));
	if (mh_buffers_ready)
	for (i = 0; i < 3; i = i + 1)
	{
		print(sprintf("home: kind %g tier1 wos %s all %s", i,
		              bufstr_get(mh_tiers_wos, i * MH_TSLOTS), bufstr_get(mh_tiers_all, i * MH_TSLOTS)));
		print(sprintf(" maps wos %g all %g of %g times %g wr %g\n", mh_kwos[i], mh_kall[i], mh_kof[i],
		              mh_ktimes[i], mh_kwr[i]));
	}
	print(sprintf("browser: screen %g content %gx%g side %g,%g %gx%g\n", menu_screen, mh_content_size_x, mh_content_size_y, mh_sidebar_pos_x, mh_sidebar_pos_y, mh_sidebar_size_x, mh_sidebar_size_y));
	print(sprintf("home: header %g,%g %gx%g body-top %g\n", mh_header_pos_x, mh_header_pos_y, mh_header_size_x, mh_header_size_y, mh_header_pos_y + mh_header_size_y + 12));
	print(sprintf("home: progress story %g/%g known %g event %g/%g known %g\n", mh_spdone, mh_sptotal, mh_spknown, mh_epdone, mh_eptotal, mh_epknown));
	print(sprintf("home: canvas %gx%g lobby %g/%g cols %g rows %g cell %g\n", mh_canvas_x, mh_canvas_y, mh_lshown, Lob_Count(), mh_lcols, mh_lrows, mh_lheight));
	print(sprintf("home: lobby bottom %g <= %g tiers %g cols %g rows %g bottom %g <= progress %g\n", mh_lbottom, mh_lsize_y, mh_tshown, mh_tcols, mh_trows, mh_tbottom, mh_progress_top));
	print(sprintf("home: stats %gx%g state %g source %g native %g stale %g\n", mh_ssize_x, mh_ssize_y, mh_state, mh_source, mh_native, mh_stale));
	print(sprintf("home: thumb %gx%g friends %g chat %g lobby height %g\n", mh_thumb_width, mh_thumb_height, mh_friends_height, mh_chat_height, mh_lsize_y));
	print(sprintf("home: photos ready %g local %g remote %g min-width %g limit %g\n", mh_shot_ready, mh_shot_local, mh_shot_remote, mh_shot_pixels, MH_SHOT_MAX));
	print(sprintf("home: photo gate %g terms %g builtin %g shader %g decoded %gx%g\n", ms_consent, cvar("rec_terms"), checkbuiltin(drawgetimagesize_async), mh_shot_shaderid, mh_shot_decodew, mh_shot_decodeh));
};
