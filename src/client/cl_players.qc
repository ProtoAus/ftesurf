/* Players occupies the scoreboard's table, never a second/sidebar SUI panel.
   Slot gaps are real; list-view scroll reaches every player. P770: the row is
   the Spectate target and its buttons sit on top of it (SUI's topmost element
   is the last added); only pinned-board clicks act. */
#define PL_MAXSLOT 64
#define PL_BMAX 64
float pl_specpick, pl_rows, pl_bid, pl_bn, pl_req, pl_sent, pl_wait, pl_bgen;
float pl_rowh, pl_wheel;
float pl_bticks[PL_BMAX];
string pl_bmap, pl_profilepick;
vector pl_scroll;

void(string id, float ticks) Players_Note =
{
	local float i;
	if (id == "" || ticks <= 0) return;
	for (i = 0; i < pl_bn; i = i + 1)
		if (!strcmp(bufstr_get(pl_bid, i), id)) break;
	if (i < pl_bn) pl_bticks[i] = min(pl_bticks[i], ticks);
	else if (pl_bn < PL_BMAX)
	{
		bufstr_set(pl_bid, pl_bn, id);
		pl_bticks[pl_bn] = ticks;
		pl_bn = pl_bn + 1;
	}
};
void() Players_AbsorbBoard =
{
	local float i;
	if (!Online_Describes(0, 0, OB_TIER, "clean")) return;
	for (i = 0; i < ob_n; i = i + 1)
		Players_Note(FS_GuidId(bufstr_get(ob_bplayer, i)), ob_ticks[i]);
};
float(float reqid, float code, string body) Players_BoardReply =
{
	local float root, rows, row, i;
	if (!pl_req || reqid != pl_req) return FALSE;
	pl_req = 0;
	root = 0;
	if (!code) root = json_parse(body);
	if (root)
	{
		if (!strcasecmp(json_get_string(json_find_object_child(root, "map")), serverkey("map")))
		{
			rows = json_find_object_child(root, "rows");
			for (i = 0; i < min(OB_PAGE, json_get_length(rows)); i = i + 1)
			{
				row = json_get_child_at_index(rows, i);
				Players_Note(FS_GuidId(json_get_string(json_find_object_child(row, "player"))),
				             json_get_float(json_find_object_child(row, "ticks")));
			}
		}
		json_free(root);
	}
	else { pl_bgen = -1; pl_wait = cltime + OB_RETRY_SECS; }
	return TRUE;
};
float(string who) Players_Best =
{
	local float i;
	for (i = 0; i < pl_bn; i = i + 1)
		if (!strcmp(bufstr_get(pl_bid, i), who)) return pl_bticks[i];
	return 0;
};
void(float slot, string nm) Pl_VoiceToggle =
{
	// Engine's numeric selector is USERID, not slot or '#slot'.
	localcmd(sprintf("cl_voip_%s %.0f\n", stof(getplayerkeyvalue(slot, "vignored")) ? "unmute" : "mute",
	                 stof(getplayerkeyvalue(slot, "userid"))));
};
// Block: the saved chat silence by name, and for a Steam account the service's
// block (no friendship, adds or private messages). Voice is Mute's alone.
void(string nm, string ahash, float on) Pl_BlockToggle =
{
	if (Chat_Silenced(nm) == on) Chat_SilenceToggle(nm);
	if (ahash != "")
	if ((Friends_Relation(ahash) == 4) == on)
		Friends_Action(on ? "unblock" : "block", ahash);
};
// The widest of a button's labels, padded: every row's buttons line up.
float(string a, string b, string c, float sz) Pl_ButtonW =
{
	return ceil(max(stringwidth(a, TRUE, [sz, sz]), max(stringwidth(b, TRUE, [sz, sz]),
	            stringwidth(c, TRUE, [sz, sz]))) + sz * 2);
};
float(float evtype, float scanx) Players_Wheel =
{
	local float bit, d;
	if (scanx != K_MWHEELUP && scanx != K_MWHEELDOWN) return FALSE;
	bit = scanx == K_MWHEELUP ? 1 : 2;
	if (evtype == IE_KEYUP)
	{
		if (!(pl_wheel & bit)) return FALSE;
		pl_wheel = pl_wheel - bit;
		return TRUE;
	}
	_sui_mouse_move(_cursor_position, FALSE);
	if (sui_hover_index("pl_list") < 0) return FALSE;
	d = max(1, pl_rowh) * 3;
	if (scanx == K_MWHEELUP) d = 0 - d;
	pl_scroll_y = max(0, pl_scroll_y + d);
	pl_wheel = pl_wheel | bit;
	return TRUE;
};

// Block's lit state is rose, not the accent a lit chip wears.
float(string id, vector pos, vector sz, string label, float tsz, float on) Pl_BlockChip =
{
	local float hot;
	if (!on) return Profile_Chip(id, pos, sz, label, tsz, FALSE);
	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	sui_style_box(pos, sz, sz_y * 0.5, SUI_THEME_BAD_BG, hot ? SUI_THEME_BAD : SUI_THEME_BAD_BG, 1);
	sui_text([pos_x + (sz_x - stringwidth(label, TRUE, [tsz, tsz])) * 0.5, pos_y + (sz_y - tsz) * 0.5],
	         [tsz, tsz], label, SUI_THEME_BAD, 1, 0);
	return sui_is_released(id);
};

void(vector p, vector sz, float tsz) Players_Draw =
{
	local float i, j, n, rowh, hint, x, y, by, best, vmute, blocked, rel, me, on, hot, av, bh, rw;
	local float wpro, wadd, wmute, wblk, ax, pbr, pingr, nx, nw;
	local float slots[PL_MAXSLOT];
	local vector lp, c;
	local string who, ahash, nm, s, map, rid;

	map = serverkey("map");
	if (strcmp(pl_bmap, map))
	{
		if (pl_bmap != "") strunzone(pl_bmap);
		pl_bmap = strzone(map);
		pl_bn = 0; pl_wait = 0; pl_bgen = -1;
	}
	if (pl_req && cltime - pl_sent > OB_DEADLINE) { pl_req = 0; pl_bgen = -1; pl_wait = cltime + OB_RETRY_SECS; }
	if (!pl_req && cltime >= pl_wait && pl_bgen != ob_gen && map != "")
	if (cvar_string("lobby_dir") != "")
	if (ui_consent_ver >= FS_TERMS_ONLINE || cvar("rec_terms") >= FS_TERMS_ONLINE)
	{
		pl_req = Online_NextReq(); pl_sent = cltime; pl_bgen = ob_gen;
		if (!uri_get(sprintf("%s/api/board?map=%s&track=0&leg=0&tier=%s&style=clean&limit=%g",
		             cvar_string("lobby_dir"), uri_escape(map), OB_TIER, OB_PAGE), pl_req))
			{ pl_req = 0; pl_bgen = -1; pl_wait = cltime + OB_RETRY_SECS; }
	}
	n = 0;
	for (i = 0; i < PL_MAXSLOT; i = i + 1)
		if (getplayerkeyvalue(i, "name") != "") { slots[n] = i; n = n + 1; }
	pl_rows = n;

	// Columns, right to left: the buttons, PB, ping; the name takes the rest.
	// The small labels stop at 11 px, as the board's do (Scores_Type).
	hint = Font_Px(max(tsz * 0.75, 11));
	rowh = max(ceil(tsz * 2.9), tsz + hint + 14);
	pl_rowh = rowh;
	av = ceil(tsz * 2);
	bh = ceil(hint * 2.1);
	rw = sz_x - tsz;                    // the scrollbar's lane
	wpro = Pl_ButtonW("Profile", "", "", hint);
	wadd = Pl_ButtonW("Add friend", "Requested", "Accept", hint);
	wmute = Pl_ButtonW("Mute", "Unmute", "", hint);
	wblk = Pl_ButtonW("Block", "Unblock", "", hint);
	ax = rw - hint - wpro - wadd - wmute - wblk - 18;
	pbr = ax - hint * 2;
	pingr = pbr - ceil(stringwidth("88:88.888", TRUE, [hint, hint])) - hint * 2;
	nx = hint * 2 + av;
	nw = max(0, pingr - ceil(stringwidth("999 ms", TRUE, [hint, hint])) - hint - nx);

	sui_text([p_x + nx, p_y], [hint, hint], sprintf("IN THIS SERVER: %g", n), SUI_THEME_MUTED, 1, 0);
	sui_text([p_x + pingr - stringwidth("PING", TRUE, [hint, hint]), p_y], [hint, hint], "PING", SUI_THEME_MUTED, 1, 0);
	sui_text([p_x + pbr - stringwidth("PB", TRUE, [hint, hint]), p_y], [hint, hint], "PB", SUI_THEME_MUTED, 1, 0);
	s = "Click a player to spectate";
	sui_text([p_x + rw - hint - stringwidth(s, TRUE, [hint, hint]), p_y], [hint, hint], s, SUI_THEME_MUTED, 1, 0);
	p_y = p_y + hint * 1.8; sz_y = sz_y - hint * 1.8;

	sui_list_view_begin("pl_list", p, sz, [rw, rowh], n, pl_scroll, [0, tsz]);
	lp = '0 0 0';
	for (i = sui_list_item(lp); i > -1; i = sui_list_item(lp))
	{
		j = slots[i];
		nm = getplayerkeyvalue(j, "name");
		ahash = getplayerkeyvalue(j, "*ahash");
		who = ahash;
		if (who == "") who = getplayerkeyvalue(j, "*phash");
		me = (j == player_localnum);
		on = (spc_stat == j + 1);
		rid = sprintf("pl_spec%g", j);
		hot = FALSE;
		if (!me)
		{
			sui_action_element(lp, [rw, rowh - 4], rid, sui_noop);
			hot = (sui_hover_index(rid) >= 0);        // under its buttons too
			if (sui_is_released(rid))
			if (rec_sb_open) pl_specpick = j + 1;
		}
		c = SUI_THEME_WELL;
		if (hot) c = SUI_THEME_HOVER;
		if (on) c = SUI_THEME_SELECTED;
		sui_roundbox(lp, [rw, rowh - 4], hint * 0.6, c, (on || hot) ? 1 : 0.85);
		if (on)
			sui_roundbox(lp + [0, hint * 0.6], [3, rowh - 4 - hint * 1.2], 1.5, SUI_THEME_ACCENT, 1);
		Profile_Face([lp_x + hint, lp_y + floor((rowh - 4 - av) * 0.5)], av, who, who != "", nm);

		// The name, and under it what this player is to you.
		y = lp_y + floor((rowh - 4 - tsz - hint - 3) * 0.5);
		sui_text([lp_x + nx, y], [tsz, tsz], Chat_Fit(nm, nw, tsz), SUI_THEME_TEXT, 1, 0);
		rel = (ahash != "") ? Friends_Relation(ahash) : 0;
		vmute = stof(getplayerkeyvalue(j, "vignored"));
		blocked = (Chat_Silenced(nm) || rel == 4);
		s = "";
		c = SUI_THEME_MUTED;
		if (me) { s = "You"; c = SUI_THEME_ACCENT; }
		else if (on) { s = "Spectating"; c = SUI_THEME_ACCENT; }
		else if (sui_is_hovered(rid)) { s = "Click to spectate"; c = SUI_THEME_ACCENT; }
		else if (blocked) { s = "Blocked"; c = SUI_THEME_BAD; }
		else if (vmute) s = "Voice muted";
		if (s != "")
			sui_text([lp_x + nx, y + tsz + 3], [hint, hint], Chat_Fit(s, nw, hint), c, 1, 0);

		y = lp_y + floor((rowh - 4 - hint) * 0.5);
		s = strcat(getplayerkeyvalue(j, "ping"), " ms");
		sui_text([lp_x + pingr - stringwidth(s, TRUE, [hint, hint]), y], [hint, hint], s, SUI_THEME_DIM, 1, 0);
		best = Players_Best(getplayerkeyvalue(j, "*phash"));
		s = (best > 0) ? Time_TickString(best, Timer_Tick()) : "-";
		sui_text([lp_x + pbr - stringwidth(s, TRUE, [hint, hint]), y], [hint, hint], s,
		         (best > 0) ? SUI_THEME_TEXT : SUI_THEME_MUTED, 1, 0);

		x = lp_x + ax;
		by = lp_y + floor((rowh - 4 - bh) * 0.5);
		if (Profile_Chip(sprintf("pl_name%g", j), [x, by], [wpro, bh], "Profile", hint, FALSE))
		if (rec_sb_open && who != "")
		{
			if (pl_profilepick != "") strunzone(pl_profilepick);
			pl_profilepick = strzone(me ? "me" : who);
		}
		if (me) continue;
		x = x + wpro + 6;
		if (rel == 3)
			sui_text([x + (wadd - stringwidth("Friend", TRUE, [hint, hint])) * 0.5, by + (bh - hint) * 0.5],
			         [hint, hint], "Friend", SUI_THEME_GOOD, 1, 0);
		else if (ahash != "" && rel != 4)
			if (Profile_Chip(sprintf("pl_add%g", j), [x, by], [wadd, bh], Friends_AddLabel(ahash), hint, rel == 1))
			if (rec_sb_open) Friends_Add(ahash);
		x = x + wadd + 6;
		if (Profile_Chip(sprintf("pl_voice%g", j), [x, by], [wmute, bh], vmute ? "Unmute" : "Mute", hint, vmute))
		if (rec_sb_open) Pl_VoiceToggle(j, nm);
		x = x + wmute + 6;
		if (Pl_BlockChip(sprintf("pl_chat%g", j), [x, by], [wblk, bh], blocked ? "Unblock" : "Block", hint, blocked))
		if (rec_sb_open) Pl_BlockToggle(nm, ahash, blocked);
	}
	sui_list_view_end();
};
void() Players_RegisterCvars = { pl_bid = buf_create(); };
