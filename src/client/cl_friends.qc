/* Account friends, supplied privately by the proven lobby connection.
   Separate staging store: a paced list update replaces the visible list only
   at friend_end. No installation-local friendship file or public HTTP reader. */
#define FR_MAX 128
#define FR_FIELDS 8
float fr_buf, fr_stage, fr_ready, fr_n, fr_sn, fr_loading;
float fr_activity_capable, fr_menu_at;
vector fr_scroll;
string fr_notice, fr_msgpick, fr_profpick, fr_snapshot_hash;
float fr_joinuntil, fr_rowh, fr_wheel;
// P788: the "added you" toast, once per account (fr_seen, data/friends_toasted.txt).
string fr_seen, fr_tw, fr_tn;
float fr_tend, fr_tsent, fr_tshown, fr_tlast;
float fr_tsheld;                // cl_main.qc copies sc_held (declared after this file)
void() Av_Close;
void(string who) Av_OpenAt;

float(string who) Friends_MarkSafe =
{
	local float i;
	if (strlen(who) != FS_WHO_IDLEN && strlen(who) != 12) return FALSE;
	for (i = 0; i < strlen(who); i = i + 1)
		if (strstrofs("0123456789abcdef", substring(who, i, 1), 0) < 0) return FALSE;
	return TRUE;
};

float(string who) Friends_Find =
{
	local float i;
	who = substring(who, 0, FS_WHO_IDLEN);
	for (i = 0; i < fr_n; i = i + 1)
		if (!strcmp(bufstr_get(fr_buf, i * FR_FIELDS), who)) return i;
	return -1;
};

float(string who) Friends_Relation =
{
	local float i;
	i = Friends_Find(who);
	if (i < 0) return 0;
	return stof(bufstr_get(fr_buf, i * FR_FIELDS + 1));
};

float(string who) Friends_ProfileSlot =
{
	local float i;
	if (strlen(who) != FS_WHO_IDLEN)
	if (pf_state != PFS_OK || !pf_av || strcmp(who, pf_handle)) return -1;
	who = substring(who, 0, FS_WHO_IDLEN);
	if (!Friends_MarkSafe(who)) return -1;
	for (i = 0; i < 64; i = i + 1)
		if (!strcmp(getplayerkeyvalue(i, "*ahash"), who)) return i;
	return -1;
};

string(string who) Friends_ProfileTarget =
{
	// A just-linked player needs no board history/profile HTTP response.
	if (pf_state == PFS_OK) return pf_handle; // service refuses profiles with no Steam account
	if (Friends_ProfileSlot(who) >= 0) return substring(who, 0, FS_WHO_IDLEN);
	if (strlen(who) == FS_WHO_IDLEN && Friends_Find(who) >= 0) return who;
	return "";
};

void(string op, string who) Friends_Action =
{
	if (!Friends_MarkSafe(who)) return;
	localcmd(sprintf("cmd friend %s %s\n", op, who));
	if (op == "join") fr_joinuntil = cltime + 15;
};

// P788: an add is one-way (relation 1 mine, 2 theirs) until the other adds back.
string(string who) Friends_AddLabel =
{
	local float r;
	r = Friends_Relation(who);
	if (r == 3) return "Friends";
	if (r == 2) return "Add back";
	if (r == 1) return "Added";
	return "Add friend";
};

void(string who) Friends_Add =
{
	local float r;
	r = Friends_Relation(who);
	if (!r || r == 2) Friends_Action("add", who);
};

void() Friends_SeenLoad =
{
	local float f;
	local string l;
	if (fr_seen != "") strunzone(fr_seen);
	fr_seen = "";
	f = fopen("data/friends_toasted.txt", FILE_READ);
	if (f < 0) return;
	// Friends_SeenAdd keeps the newest 300, so this reads it all.
	for (l = fgets(f); l; l = fgets(f))
		if (Friends_MarkSafe(l) && strlen(fr_seen) < 400 * 13)
			fr_seen = strcat(fr_seen, " ", l);
	fclose(f);
	if (fr_seen != "") fr_seen = strzone(fr_seen);
};

// Newest 300 kept: an account toasted that long ago may toast again.
void(string who) Friends_SeenAdd =
{
	local float f, n, i;
	local string s;
	s = strcat(fr_seen, " ", who);
	n = tokenize(s);
	if (n > 300) s = "";
	if (n > 300)
		for (i = n - 300; i < n; i = i + 1) s = strcat(s, " ", argv(i));
	if (fr_seen != "") strunzone(fr_seen);
	fr_seen = strzone(s);
	f = fopen("data/friends_toasted.txt", FILE_WRITE);
	if (f < 0) return;
	n = tokenize(fr_seen);
	for (i = 0; i < n; i = i + 1) fputs(f, strcat(argv(i), "\n"));
	fclose(f);
};

// The first incoming add not toasted yet, at most one up at a time.  Its 12 s
// and the seen mark start when it is first drawn (not under the menu).
void() Friends_ToastPick =
{
	local float i;
	local string who;
	if (fr_tw != "" || !fr_ready) return;
	for (i = 0; i < fr_n; i = i + 1)
	{
		if (stof(bufstr_get(fr_buf, i * FR_FIELDS + 1)) != 2) continue;
		who = bufstr_get(fr_buf, i * FR_FIELDS);
		if (!Friends_MarkSafe(who)) continue;
		if (strstrofs(strcat(fr_seen, " "), strcat(" ", who, " "), 0) >= 0) continue;
		if (Chat_Silenced(bufstr_get(fr_buf, i * FR_FIELDS + 3))) continue;
		fr_tw = strzone(who);
		fr_tn = strzone(bufstr_get(fr_buf, i * FR_FIELDS + 3));
		fr_tsent = fr_tshown = FALSE;
		return;
	}
};

void() Friends_ToastClear =
{
	if (fr_tw != "") strunzone(fr_tw);
	if (fr_tn != "") strunzone(fr_tn);
	fr_tw = fr_tn = "";
};

// Not over the board or the profile card.
float() Friends_ToastCovered =
{
	return (rec_sb_open || fr_tsheld || (UI_CursorHeld() & UIC_AVATAR));
};

float(float scanx) Friends_ToastKey =
{
	if (scanx != K_F2 || fr_tw == "" || !fr_tshown || fr_tsent || cltime >= fr_tend) return FALSE;
	if (Friends_ToastCovered() || Friends_Relation(fr_tw) != 2) return FALSE;
	Friends_Action("add", fr_tw);
	fr_tsent = TRUE;
	fr_tend = cltime + 1.5;
	return TRUE;
};

void(vector scr) Friends_DrawToast =
{
	local vector p;
	local float sc, w, h, hh, lsz, pic, y, dt;
	local string t;

	dt = bound(0, cltime - fr_tlast, 1);      // real time since the last draw
	fr_tlast = cltime;
	if (fr_tw == "") return;
	// Gone, or added back some other way: nothing left to answer.
	if ((fr_tshown && cltime >= fr_tend) || (!fr_tsent && Friends_Relation(fr_tw) != 2))
	{
		Friends_ToastClear();
		Friends_ToastPick();
		return;
	}
	if (Friends_ToastCovered())
	{
		if (fr_tshown) fr_tend = fr_tend + dt;    // paused under it
		return;
	}
	if (!fr_tshown)
	{
		fr_tshown = TRUE;
		fr_tend = cltime + 12;
		Friends_SeenAdd(fr_tw);
	}
	sc = ui_cv_scale;
	Font_Set(ui_font_ui);
	lsz = Font_Px(8 * sc);
	h = 14 * sc;
	hh = 15 * sc;
	pic = 2 * hh;
	t = Chat_Fit(fr_tn, 120 * sc, lsz);
	w = max(150 * sc, stringwidth(t, TRUE, [lsz, lsz]) + pic + 40 * sc);
	p = [scr_x - w - 8 * sc, scr_y * 0.3, 0];
	_sui_round_draw(p, [w, 3 * sc + pic + 2 * sc + h + 3 * sc, 0], 5 * sc, SUI_THEME_PANEL, 0.9);
	y = p_y + 3 * sc;
	if (!SteamPic_Draw([p_x + 6 * sc, y], pic, fr_tw, 1))
		_sui_round_draw([p_x + 6 * sc, y, 0], [pic, pic, 0], 4 * sc, SUI_THEME_CHIP, 1);
	HUD_Text([p_x + pic + 12 * sc, y + (hh - lsz) * 0.5], t, lsz, SUI_THEME_TEXT, 1);
	HUD_TextR([p_x + w - 6 * sc, y + (hh - lsz) * 0.5], sprintf("%gs", ceil(max(0, fr_tend - cltime))),
	          lsz, SUI_THEME_WARN, 1);
	HUD_Text([p_x + pic + 12 * sc, y + hh + (hh - lsz) * 0.5],
	         fr_tsent ? "adding them back..." : "added you as a friend", lsz, SUI_THEME_DIM, 1);
	y = y + pic + 2 * sc;
	KeyMenu_Row([p_x, y], w, h, "F2", "Add back", fr_tsent ? KM_INERT : KM_HOT, lsz, sc);
	Font_Reset();
};

void(string who, string nm) Friends_Message =
{
	if (!Friends_MarkSafe(who)) return;
	if (fr_msgpick != "") strunzone(fr_msgpick);
	fr_msgpick = strzone(who);
	// The existing chat draft owns text input, escape, clipboard and releases.
	Chat_Private(who, nm);
};

void() Friends_Finish =
{
	if (fr_msgpick != "")
	{
		Av_Close();
		strunzone(fr_msgpick);
		fr_msgpick = "";
	}
	if (fr_profpick != "")
	{
		Av_OpenAt(fr_profpick);
		strunzone(fr_profpick);
		fr_profpick = "";
	}
};

float(float evtype, float scanx) Friends_Wheel =
{
	local float bit, d;
	if (scanx != K_MWHEELUP && scanx != K_MWHEELDOWN) return FALSE;
	bit = scanx == K_MWHEELUP ? 1 : 2;
	if (evtype == IE_KEYUP)
	{
		if (!(fr_wheel & bit)) return FALSE;
		fr_wheel = fr_wheel - bit;
		return TRUE;
	}
	_sui_mouse_move(_cursor_position, FALSE);
	if (sui_hover_index("fr_list") < 0) return FALSE;
	d = max(1, fr_rowh) * 3;
	if (scanx == K_MWHEELUP) d = 0 - d;
	fr_scroll_y = max(0, fr_scroll_y + d);
	fr_wheel = fr_wheel | bit;
	return TRUE;
};

void(vector p, vector sz, float tsz, float hint) Friends_Draw =
{
	local float y, rowh, i, at, rel, online, menuonline, x, bw, w;
	local vector lp;
	local string who, nm, s;

	if (getplayerkeyvalue(player_localnum, "*ahash") == "")
	{
		// A private game has no account service: the menu's Play screen lists friends itself.
		if (serverkey("board") == "local")
			s = "Private game: your friends list is in the menu, under Play";
		else
			s = "Link Steam on an account-enabled lobby to use Friends";
		sui_text(p + [0, hint], [tsz, tsz], s, SUI_THEME_DIM, 1, 0);
		return;
	}
	sui_text(p, [hint, hint], "Steam friends on every linked install. Messages appear privately in chat.", SUI_THEME_MUTED, 1, 0);
	y = p_y + hint * 2;
	s = fr_notice;
	if (!fr_ready) s = "Loading friends...";
	if (s != "") sui_text([p_x, y], [hint, hint], Chat_Fit(s, sz_x, hint), SUI_THEME_ACCENT, 1, 0);
	y = y + hint * 2;
	if (fr_ready && !fr_n)
		sui_text([p_x, y], [tsz, tsz], "No friends yet. Add someone from TAB > Players or their profile.", SUI_THEME_DIM, 1, 0);
	rowh = ceil(tsz * 3.7);
	fr_rowh = rowh;
	bw = ceil(hint * 7);
	w = sz_x - tsz;
	sui_list_view_begin("fr_list", [p_x, y], [sz_x, p_y + sz_y - y], [w, rowh], fr_n, fr_scroll, [0, tsz]);
	lp = '0 0 0';
	for (i = sui_list_item(lp); i > -1; i = sui_list_item(lp))
	{
		at = i * FR_FIELDS;
		who = bufstr_get(fr_buf, at);
		rel = stof(bufstr_get(fr_buf, at + 1));
		online = stof(bufstr_get(fr_buf, at + 2));
		menuonline = (rel == 3 && stof(bufstr_get(fr_buf, at + 7)) == 1 && cltime >= fr_menu_at && cltime - fr_menu_at <= 16);
		nm = bufstr_get(fr_buf, at + 3);
		// P788: incoming adds, listed after friends, are drawn faded.
		sui_roundbox(lp + '0 1 0', [w, rowh - 3], hint * 0.5, SUI_THEME_WELL, rel == 2 ? 0.35 : 0.8);
		if (!SteamPic_Draw(lp + [hint * 0.5, hint * 0.5], tsz * 2, who, rel == 2 ? 0.45 : 1))
			sui_roundbox(lp + [hint * 0.5, hint * 0.5], [tsz * 2, tsz * 2], hint * 0.5, SUI_THEME_CHIP,
			             rel == 2 ? 0.45 : 1);
		x = lp_x + tsz * 2 + hint;
		if (Profile_Chip(strcat("fr_profile", who), [x, lp_y + 2], [w - tsz * 2 - hint, tsz * 1.5],
		                 Chat_Fit(nm, w - tsz * 3, tsz), tsz, FALSE))
		{
			if (fr_profpick != "") strunzone(fr_profpick);
			fr_profpick = strzone(who);
		}
		s = "Offline";
		if (rel == 1) s = "Added -- waiting for them to add you back";
		if (rel == 2) s = "Added you -- add them back";
		if (rel == 4) s = "Blocked: cannot add or message you";
		if (rel == 3 && stof(bufstr_get(fr_buf, at + 7)) == 1) s = menuonline ? "Main menu" : "Presence unavailable";
		if (rel == 3 && online)
			s = strcat(bufstr_get(fr_buf, at + 5), "  /  ", bufstr_get(fr_buf, at + 6));
		sui_text([x, lp_y + tsz * 1.65], [hint, hint], Chat_Fit(s, w - tsz * 3, hint),
		         (online || menuonline) ? SUI_THEME_GOOD : (rel == 2 ? SUI_THEME_DIM : SUI_THEME_MUTED), 1, 0);
		y = lp_y + tsz * 2.45;
		if (rel == 3 && online)
		{
			if (Profile_Chip(strcat("fr_join", who), [x, y], [bw, hint * 1.9], "Join", hint, FALSE))
				Friends_Action("join", who);
			x = x + bw + 4;
			if (Profile_Chip(strcat("fr_msg", who), [x, y], [bw, hint * 1.9], "Message", hint, FALSE))
				Friends_Message(who, nm);
			x = x + bw + 4;
		}
		if (rel == 2)
		{
			if (Profile_Chip(strcat("fr_accept", who), [x, y], [bw, hint * 1.9], "Add back", hint, FALSE))
				Friends_Action("add", who);
			x = x + bw + 4;
		}
		if (rel == 4)
		{
			if (Profile_Chip(strcat("fr_unblock", who), [x, y], [bw, hint * 1.9], "Unblock", hint, FALSE))
				Friends_Action("unblock", who);
		}
		else if (Profile_Chip(strcat("fr_del", who), [x, y], [bw, hint * 1.9], "Remove", hint, FALSE))
			Friends_Action("remove", who);
	}
	sui_list_view_end();
};

float(string addr) Friends_AddrSafe =
{
	local float i;
	if (strlen(addr) < 3 || strlen(addr) > 128 || strstrofs(addr, ":", 0) < 0) return FALSE;
	for (i = 0; i < strlen(addr); i = i + 1)
		if (strstrofs("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:[]", substring(addr, i, 1), 0) < 0)
			return FALSE;
	return TRUE;
};

// Optional install-local menu adapter. Keep the account/presence protocol here.
void() Friends_MenuClear;
void() Friends_MenuPublish;
void(string who) Friends_MenuJoin;

void() Friends_Register =
{
	Friends_MenuClear();
	fr_buf = buf_create();
	fr_stage = buf_create();
	Friends_SeenLoad();
	registercommand("friend_clear");
	registercommand("friend_begin");
	registercommand("friend_row");
	registercommand("friend_end");
	registercommand("friend_pm");
	registercommand("friend_note");
	registercommand("friend_join");
	registercommand("friends_status");
	registercommand("friends_menu_join");
	registercommand("friends_menu_add");
};

// Only a successful unchanged poll for the completed snapshot renews it.
float(string hash) Friends_SnapshotFresh =
{
	if (!fr_ready || fr_loading || strlen(hash) != 64) return FALSE;
	if (strcmp(hash, fr_snapshot_hash)) return FALSE;
	fr_menu_at = cltime;
	Friends_MenuPublish();
	return TRUE;
};

float(string cmd) Friends_ConsoleCommand =
{
	local string c, nm, s;
	local float n, tmp, slot, muted;

	n = tokenize(cmd);
	c = argv(0);
	if (c == "friends_menu_join" && n == 2)
	{
		Friends_MenuJoin(argv(1));
		return TRUE;
	}
	if (c == "friends_menu_add" && n == 2)      // P788: the menu's Add back while connected
	{
		if (Friends_Relation(argv(1)) == 2) Friends_Action("add", argv(1));
		return TRUE;
	}
	if (c == "friend_clear")
	{
		fr_n = 0; fr_sn = 0; fr_ready = FALSE; fr_loading = FALSE;
		Friends_MenuClear();
		return TRUE;
	}
	if (c == "friend_begin")
	{
		fr_sn = 0;
		fr_loading = TRUE;
		fr_activity_capable = (n >= 2 && stof(argv(1)) == 1);
		return TRUE;
	}
	if (c == "friend_row")
	{
		if (fr_loading && fr_sn < FR_MAX && n >= 7)
		{
			bufstr_set(fr_stage, fr_sn * FR_FIELDS, argv(1));
			bufstr_set(fr_stage, fr_sn * FR_FIELDS + 1, argv(2));
			bufstr_set(fr_stage, fr_sn * FR_FIELDS + 2, argv(3));
			bufstr_set(fr_stage, fr_sn * FR_FIELDS + 3, uri_unescape(argv(4)));
			bufstr_set(fr_stage, fr_sn * FR_FIELDS + 4, uri_unescape(argv(5)));
			bufstr_set(fr_stage, fr_sn * FR_FIELDS + 5, uri_unescape(argv(6)));
			bufstr_set(fr_stage, fr_sn * FR_FIELDS + 6, n >= 8 ? uri_unescape(argv(7)) : "");
			bufstr_set(fr_stage, fr_sn * FR_FIELDS + 7, (n >= 9 && stof(argv(8)) == 1) ? "1" : "0");
			fr_sn = fr_sn + 1;
		}
		return TRUE;
	}
	if (c == "friend_end")
	{
		if (fr_loading)
		{
			// SUI retains frame strings during a press. Even stable row IDs
			// can be overwritten by a replacement snapshot: cancel this
			// list's hold, never an unrelated panel's interaction.
			if (sui_hold_index("fr_list") >= 0)
			{
				_hold_action_count = _click_action_count = _release_action_count = 0;
				_holding_click = FALSE;
			}
			tmp = fr_buf; fr_buf = fr_stage; fr_stage = tmp;
			fr_n = fr_sn; fr_ready = TRUE; fr_loading = FALSE;
			if (strlen(fr_snapshot_hash)) strunzone(fr_snapshot_hash);
			fr_snapshot_hash = "";
			if (n == 2 && strlen(argv(1)) == 64) fr_snapshot_hash = strzone(argv(1));
			fr_menu_at = cltime;
			Friends_MenuPublish();
			Friends_ToastPick();
		}
		else if (n == 2) Friends_SnapshotFresh(argv(1));
		return TRUE;
	}
	if (c == "friend_pm" && n >= 4)
	{
		nm = uri_unescape(argv(2));
		s = uri_unescape(argv(3));
		muted = Chat_Silenced(nm);
		slot = Friends_ProfileSlot(argv(1));
		if (slot >= 0)
			if (Chat_Silenced(getplayerkeyvalue(slot, "name"))) muted = TRUE;
		if (!muted)
		{
			s = strcat("^5[PM from ", nm, "^5]^7 ", s);
			if (Friends_MarkSafe(argv(1))) chat_push_mark = argv(1);      // Patch 789
			Chat_Push(s);
			print(strcat(s, "\n")); // local only, never a server/public say
		}
		return TRUE;
	}
	if (c == "friend_note" && n >= 2)
	{
		if (fr_notice != "") strunzone(fr_notice);
		fr_notice = strzone(uri_unescape(argv(1)));
		Chat_Push(strcat("^5Friends:^7 ", fr_notice));
		return TRUE;
	}
	if (c == "friend_join" && n >= 2)
	{
		s = uri_unescape(argv(1));
		if (cltime < fr_joinuntil && Friends_AddrSafe(s)) localcmd(sprintf("connect \"%s\"\n", s));
		fr_joinuntil = 0;
		return TRUE;
	}
	if (c == "friends_status")
	{
		print(sprintf("friends: ready %g rows %g loading %g\n", fr_ready, fr_n, fr_loading));
		print(sprintf("friends: toast \"%s\" %s sent %g left %.1f\n", fr_tn, fr_tw, fr_tsent, max(0, fr_tend - cltime)));
		print(sprintf("friends: scroll %.1f wheel %g\n", fr_scroll_y, fr_wheel));
		return TRUE;
	}
	return FALSE;
};
