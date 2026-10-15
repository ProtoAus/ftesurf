/* Players occupies the scoreboard's table, never a second/sidebar SUI panel.
   Slot gaps are real; list-view scroll reaches every player. Name/profile and
   Spec/Add/Mute are separate targets; only pinned-board clicks act. */
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

void(vector p, vector sz, float tsz) Players_Draw =
{
	local float i, j, n, rowh, hint, bw, x, y, best, mute;
	local float slots[PL_MAXSLOT];
	local vector lp;
	local string who, nm, s, map;

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
	hint = max(8, Font_Px(tsz * 0.75));
	rowh = ceil(tsz * 3.3);
	pl_rowh = rowh;
	bw = ceil(hint * 7);
	sui_text(p, [hint, hint], sprintf("IN THIS SERVER: %g    Select a name for their profile", n), SUI_THEME_MUTED, 1, 0);
	p_y = p_y + hint * 2; sz_y = sz_y - hint * 2;
	sui_list_view_begin("pl_list", p, sz, [sz_x - tsz, rowh], n, pl_scroll, [0, tsz]);
	lp = '0 0 0';
	for (i = sui_list_item(lp); i > -1; i = sui_list_item(lp))
	{
		j = slots[i];
		nm = getplayerkeyvalue(j, "name");
		who = getplayerkeyvalue(j, "*ahash");
		if (who == "") who = getplayerkeyvalue(j, "*phash");
		sui_roundbox(lp + '0 1 0', [sz_x - tsz, rowh - 3], hint * 0.5,
		             spc_stat == j + 1 ? SUI_THEME_SELECTED : SUI_THEME_WELL, 0.85);
		if (!SteamPic_Draw(lp + [hint * 0.5, hint * 0.5], tsz * 2, who, 1))
			sui_roundbox(lp + [hint * 0.5, hint * 0.5], [tsz * 2, tsz * 2], hint * 0.5, Av_WornRGB(j), 1);
		x = lp_x + tsz * 2 + hint;
		if (Profile_Chip(sprintf("pl_name%g", j), [x, lp_y + 2], [sz_x - tsz * 4, tsz * 1.5],
		                 Chat_Fit(nm, sz_x - tsz * 5, tsz), tsz, j == player_localnum))
		if (rec_sb_open && who != "")
		{
			if (pl_profilepick != "") strunzone(pl_profilepick);
			pl_profilepick = strzone(j == player_localnum ? "me" : who);
		}
		y = lp_y + tsz * 1.8;
		if (j != player_localnum)
		{
			if (Profile_Chip(sprintf("pl_spec%g", j), [x, y], [bw, hint * 1.9], "Spectate", hint, spc_stat == j + 1))
			if (rec_sb_open) pl_specpick = j + 1;
			x = x + bw + 4;
			s = getplayerkeyvalue(j, "*ahash");
			if (s != "")
			{
				if (Profile_Chip(sprintf("pl_add%g", j), [x, y], [bw, hint * 1.9], Friends_AddLabel(s), hint, Friends_Relation(s) == 3))
				if (rec_sb_open) Friends_Add(s);
				x = x + bw + 4;
			}
			mute = Chat_Silenced(nm);
			if (Profile_Chip(sprintf("pl_chat%g", j), [x, y], [bw, hint * 1.9], mute ? "Unmute chat" : "Mute chat", hint, mute))
			if (rec_sb_open) Chat_SilenceToggle(nm);
			x = x + bw + 4;
			mute = stof(getplayerkeyvalue(j, "vignored"));
			if (Profile_Chip(sprintf("pl_voice%g", j), [x, y], [bw, hint * 1.9], mute ? "Unmute voice" : "Mute voice", hint, mute))
			if (rec_sb_open) Pl_VoiceToggle(j, nm);
			x = x + bw + 4;
		}
		best = Players_Best(getplayerkeyvalue(j, "*phash"));
		s = strcat(getplayerkeyvalue(j, "ping"), "ms");
		if (best > 0) s = strcat(s, "  PB ", Time_TickString(best, Timer_Tick()));
		sui_text([x + 4, y + hint * 0.4], [hint, hint], Chat_Fit(s, max(0, lp_x + sz_x - tsz - x - 8), hint), SUI_THEME_DIM, 1, 0);
	}
	sui_list_view_end();
};
void() Players_RegisterCvars = { pl_bid = buf_create(); };
