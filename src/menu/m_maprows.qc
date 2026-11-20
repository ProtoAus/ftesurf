/*
  P1658: the map finder as a compact list -- one text line a map, no picture and no record
  cells, so no per-row board request.  screen_create keeps the list, the row's element and its
  click; this draws the line and its one action, under the card view's ids (cs_play<i>,
  cs_dl<i>, cs_bmom<i>/cs_bcss<i>).  Saved in ui_maps_list; the card view stays the default.
  Not the idle ui_maps_large: it is archived, and a config can still hold the 0 that P731's
  "Thumbs: compact" button set -- which would turn this list on unasked.
*/
#define MROW_H      26
#define MROW_ACT_W  92
#define MROW_SZ     '16 16 0'
#define MROW_SM     '12 12 0'
#define MSW_W       46
#define MSW_H       18

// ui_create_open: read every time the screen opens, beside its registration.
void() Mrow_Open =
{
	registercvar("ui_maps_list", "0", 32);
	ms_dense = (cvar("ui_maps_list") != 0);
};

/*
  Cards | List, at the right end of the list's heading; pos is that end.  -> the row height to
  draw with, given the card view's.  A switch keeps the top row the top row.
*/
float(vector pos, float rh) Mrow_Switch =
{
	local float k, hov, top;
	local string id, lbl;
	local vector p;

	for (k = 0; k < 2; k = k + 1)
	{
		p = [pos_x - (2 - k) * MSW_W - (1 - k) * 2, pos_y - 1];
		id = k ? "cs_viewlist" : "cs_viewcards";
		lbl = k ? "List" : "Cards";
		sui_action_element(p, [MSW_W, MSW_H], id, sui_noop);
		hov = sui_is_hovered(id);
		sui_roundbox(p, [MSW_W, MSW_H], 5, (k == ms_dense) ? COL_ACCENT : (hov ? COL_ROW_HOVER : COL_ROW), 1);
		sui_text([p_x + (MSW_W - stringwidth(lbl, TRUE, MROW_SM)) * 0.5, p_y + 3], MROW_SM, lbl,
		         (k == ms_dense) ? SUI_THEME_WELL : COL_DIM, 1, 0);
		sui_tooltip_for(id, k ? "A compact list: one line a map, no pictures or record times."
		                      : "Cards: a picture and your times for each map.", 2);
		if (sui_is_released(id))
		if (k != ms_dense)
		{
			top = floor(ms_scroll_y / max(1, ui_cs_rowheight));
			ms_dense = k;
			ms_scroll_y = top * (ms_dense ? MROW_H : rh);
			localcmd(sprintf("seta ui_maps_list %g\n", ms_dense));      // ui_modes_set's reason
		}
	}
	return ms_dense ? MROW_H : rh;
};

// Before the list view: sui scrolls it one item a wheel notch, which is one card (106 px);
// a notch of the compact list is three rows (78 px) -- these are the other two.
void() Mrow_Wheel =
{
	local float char, scan;
	if (sui_hover_index("cs_list") < 0)
		return;
	char = scan = 0;
	sui_reread_input();
	while (sui_get_input(char, scan))
	{
		if (scan == K_MWHEELUP) ms_scroll_y = ms_scroll_y - 2 * MROW_H;
		if (scan == K_MWHEELDOWN) ms_scroll_y = ms_scroll_y + 2 * MROW_H;
	}
};

// The row's one action: the card view's states (screen_create's action column), one line high.
void(vector p, float idx, float real, float er, string have) Mrow_Action =
{
	local vector s;
	local string id, mnm, lbl;
	local float hov, busy, mine, wrong;

	s = [MROW_ACT_W, MROW_H - 4];
	if (have == "1")
	{
		id = strcat("cs_play", ftos(idx));
		busy = ui_join_busy();
		sui_action_element(p, s, id, sui_noop);
		hov = busy ? FALSE : sui_is_hovered(id);
		sui_roundbox(p, s, s_y * 0.5, hov ? COL_PLAY : COL_PLAY_HOT, busy ? 0.3 : 1);
		sui_text([p_x + (s_x - stringwidth("Play", TRUE, MROW_SZ)) * 0.5, p_y + 3], MROW_SZ, "Play",
		         hov ? SUI_THEME_WELL : COL_PLAY, busy ? 0.3 : 1, 0);
		if (sui_is_released(id))
		if (!busy)
		{
			ms_selected = real;
			ui_launch();                // the consent and name gates stay in front
		}
		return;
	}
	if (have != "0")
	if (have != "2")
		return;                         // a GoldSrc map that cannot be offered

	mnm = bufstr_get(ms_name, er);
	mine = !strcmp(dl_name, mnm);
	wrong = (have == "2");
	if (mine && dl_afterlocal)
		sui_text([p_x, p_y + 5], MROW_SM, strcat(SUI_ESC_MUTED, "after this game"), COL_DIM, 1, 0);
	else if (mine && dl_state == DL_ACTIVE)
	{
		sui_roundbox([p_x, p_y + 1], [s_x, 5], 2, COL_ROW_HOVER, 1);
		if (dl_pct > 0)
			sui_roundbox([p_x, p_y + 1], [max(5, s_x * bound(0, dl_pct / 100, 1)), 5], 2, COL_ACCENT, 1);
		sui_text([p_x, p_y + 9], MROW_SM, (dl_rate > 0) ? ui_dl_rate(dl_rate) : "...", COL_DIM, 1, 0);
	}
	else if (mine && dl_state == DL_OK)
		sui_text([p_x, p_y + 3], MROW_SZ, strcat(SUI_ESC_GOOD, "installed"), COL_TEXT, 1, 0);
	else if (mine && dl_state == DL_FAIL)
		sui_text([p_x, p_y + 3], MROW_SZ, strcat(SUI_ESC_BAD, "failed"), COL_TEXT, 1, 0);
	else if (dl_state == DL_ACTIVE)
		sui_text([p_x, p_y + 3], MROW_SZ, strcat(SUI_ESC_MUTED, "queued"), COL_DIM, 0.5, 0);
	else
	{
		id = strcat("cs_dl", ftos(idx));
		lbl = wrong ? "Re-get" : "Download";
		sui_action_element(p, s, id, sui_noop);
		hov = sui_is_hovered(id);
		sui_style_box(p, s, 7, hov ? COL_ROW_HOVER : COL_ROW, hov ? COL_ACCENT : SUI_THEME_EDGE, 1);
		sui_text([p_x + (s_x - stringwidth(lbl, TRUE, MROW_SZ)) * 0.5, p_y + 3], MROW_SZ, lbl,
		         hov ? COL_TEXT : COL_ACCENT, 1, 0);
		if (sui_is_released(id))
			ui_dl_start(mnm, wrong);
	}
};

/*
  One row: name | library tag (or the build switch) | tiers or kind | detail | size | action.
  Everything but the name is dropped as the row narrows.  Odd rows are shaded as the
  leaderboard's are (Mlb_DrawRow).
*/
void(vector rp, vector rs, float idx, float real, float er, float on, float hot) Mrow_Draw =
{
	local float gs, gx, a, x, right, ty, ts, w, namew, mn, stages, bonus, linear, pop, neww;
	local string name, tag, tier, det, size, have, mt, kt, s;

	if (on)
		sui_fill(rp, rs, COL_ROW_SEL, 0.85, 0);
	else if (hot)
		sui_fill(rp, rs, COL_ROW_HOVER, 0.85, 0);
	else if (idx & 1)
		sui_fill(rp, rs, COL_ROW, 0.6, 0);

	gs = Mgs_Row(real);
	gx = Mgs_Gx(real);
	a = gx ? 0.5 : 1;
	have = bufstr_get(ms_have, er);
	ty = rp_y + (MROW_H - 16) * 0.5;
	ts = rp_y + (MROW_H - 12) * 0.5;

	if (gs)
	{
		name = Mgs_Show(real);
		tag = strcat(MGS_ESC, "GoldSrc");
		tier = Mgs_Kind(real);
		det = strcat(gx ? "not available: " : "", Mgs_Note(real));
		size = Mgs_Size(real);
		if (gx)
			sui_tooltip_for(strcat("cs_row", ftos(idx)), MGS_GXTIP, 2);
	}
	else
	{
		name = bufstr_get(ms_name, real);
		tag = ui_srcname(stof(bufstr_get(ms_src, real)));
		mt = bufstr_get(ms_momtier, real);
		kt = bufstr_get(ms_ksftier, real);
		tier = sprintf("MOM %s | KSF %s", stof(mt) > 0 ? strcat("T", mt) : "-", stof(kt) > 0 ? strcat("T", kt) : "-");
		// The card's detail line (screen_create), less what has its own column here.
		mn = tokenize(bufstr_get(ms_meta, real));
		stages = bonus = linear = -1;
		if (mn > MT_UUID)
		{
			linear = strcmp(argv(MT_LINEAR), "-") ? stof(argv(MT_LINEAR)) : -1;
			stages = strcmp(argv(MT_STAGES), "-") ? stof(argv(MT_STAGES)) : -1;
			bonus = strcmp(argv(MT_BONUS), "-") ? stof(argv(MT_BONUS)) : -1;
		}
		det = ui_mode_name(stof(bufstr_get(ms_modev, real)));
		if (stages > 0) det = sprintf("%s%s%g stages", det, (det == "") ? "" : " | ", stages);
		else if (linear == 1) det = strcat(det, (det == "") ? "" : " | ", "linear");
		if (bonus > 0) det = sprintf("%s%s%g bonus", det, (det == "") ? "" : ", ", bonus);
		pop = ui_map_players(er);
		if (pop >= 0) det = sprintf("%s%s%g playing", det, (det == "") ? "" : " | ", pop);
		s = ui_deps_text(real);
		if (strcmp(s, "")) det = strcat(det, (det == "") ? "" : " | ", "needs ", s);
		if (strcmp(bufstr_get(ms_zoned, er), "1"))
			det = strcat(MAP_NOZONE_ESC, "no zones^7", (det == "") ? "" : " | ", det);
		// The list asked once at the screen's start (MCard_DoneWant), not a request a row.
		if (MCard_Done(bufstr_get(ms_name, er)) == 1)
			det = strcat(SUI_ESC_GOOD, "complete^7", (det == "") ? "" : " | ", det);
		size = (have == "1") ? "installed" : ((have == "2") ? strcat(SUI_ESC_WARN, "wrong build")
		                                                    : ui_dl_size(stof(bufstr_get(ms_dlkb, er))));
	}

	// Right to left: the action, then the size.
	right = rp_x + rs_x - 4;
	Mrow_Action([right - MROW_ACT_W, rp_y + 2], idx, real, er, have);
	right = right - MROW_ACT_W - 12;
	if (rs_x >= 420)
	{
		sui_text([right - stringwidth(size, TRUE, MROW_SM), ts], MROW_SM, size, COL_DIM, a, 0);
		right = right - 84;
	}

	// Left to right: the name takes a third, the detail what is left.
	x = rp_x + 8;
	w = right - x;
	namew = (rs_x >= 560) ? bound(150, floor(w * 0.34), 380) : w;
	neww = (!gs && !strcmp(bufstr_get(ms_new, real), "1")) ? stringwidth("NEW", TRUE, MROW_SM) + 6 : 0;
	name = ui_fit_text(name, namew - 8 - neww, MROW_SZ);
	if (neww)
		sui_text([x + stringwidth(name, TRUE, MROW_SZ) + 6, ts], MROW_SM, strcat(SUI_ESC_GOOD, "NEW"), COL_TEXT, 1, 0);
	if (!gs)
	if (strcmp(bufstr_get(ms_zoned, er), "1"))
		name = strcat(MAP_NOZONE_ESC, name);
	sui_text([x, ty], MROW_SZ, name, gx ? COL_DIM : ((on || hot) ? COL_ACCENT : COL_TEXT), a, 0);
	if (rs_x < 560)
		return;
	x = x + namew;
	if (!gs && strcmp(bufstr_get(ms_var, real), ""))
		ui_build_switch([x, rp_y + (MROW_H - 18) * 0.5], real, idx);
	else
		sui_text([x, ts], MROW_SM, tag, COL_DIM, a, 0);
	x = x + 98;
	sui_text([x, ts], MROW_SM, tier, COL_DIM, a, 0);
	x = x + (gs ? 48 : 116);
	if (right - x > 60)
		sui_text([x, ts], MROW_SM, ui_fit_text(det, right - x - 8, MROW_SM), COL_DIM, a, 0);
};
