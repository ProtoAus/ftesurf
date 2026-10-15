/* Account friends, supplied privately by the proven lobby connection.
   Separate staging store: a paced list update replaces the visible list only
   at friend_end. No installation-local friendship file or public HTTP reader. */
#define FR_MAX 128
#define FR_FIELDS 6
float fr_buf, fr_stage, fr_ready, fr_n, fr_sn, fr_loading;
vector fr_scroll;
string fr_notice, fr_msgpick, fr_profpick;
float fr_joinuntil, fr_rowh, fr_wheel;
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

string(string who) Friends_AddLabel =
{
	local float r;
	r = Friends_Relation(who);
	if (r == 3) return "Friends";
	if (r == 2) return "Accept";
	if (r == 1) return "Requested";
	return "Add friend";
};

void(string who) Friends_Add =
{
	local float r;
	r = Friends_Relation(who);
	if (!r) Friends_Action("add", who);
	if (r == 2) Friends_Action("accept", who);
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
	local float y, rowh, i, at, rel, online, x, bw, w;
	local vector lp;
	local string who, nm, s;

	if (getplayerkeyvalue(player_localnum, "*ahash") == "")
	{
		sui_text(p + [0, hint], [tsz, tsz], "Link Steam on an account-enabled lobby to use Friends", SUI_THEME_DIM, 1, 0);
		return;
	}
	sui_text(p, [hint, hint], "Steam friends on every linked install. Messages appear privately in chat.", SUI_THEME_MUTED, 1, 0);
	y = p_y + hint * 2;
	s = fr_notice;
	if (!fr_ready) s = "Loading friends...";
	if (s != "") sui_text([p_x, y], [hint, hint], Chat_Fit(s, sz_x, hint), SUI_THEME_ACCENT, 1, 0);
	y = y + hint * 2;
	if (fr_ready && !fr_n)
		sui_text([p_x, y], [tsz, tsz], "No friends yet. Open a player's profile to add them.", SUI_THEME_DIM, 1, 0);
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
		nm = bufstr_get(fr_buf, at + 3);
		sui_roundbox(lp + '0 1 0', [w, rowh - 3], hint * 0.5, SUI_THEME_WELL, 0.8);
		if (!SteamPic_Draw(lp + [hint * 0.5, hint * 0.5], tsz * 2, who, 1))
			sui_roundbox(lp + [hint * 0.5, hint * 0.5], [tsz * 2, tsz * 2], hint * 0.5, SUI_THEME_CHIP, 1);
		x = lp_x + tsz * 2 + hint;
		if (Profile_Chip(strcat("fr_profile", who), [x, lp_y + 2], [w - tsz * 2 - hint, tsz * 1.5],
		                 Chat_Fit(nm, w - tsz * 3, tsz), tsz, FALSE))
		{
			if (fr_profpick != "") strunzone(fr_profpick);
			fr_profpick = strzone(who);
		}
		s = "Offline";
		if (rel == 1) s = "Friend request sent";
		if (rel == 2) s = "Wants to be your friend";
		if (rel == 3 && online)
			s = strcat(bufstr_get(fr_buf, at + 5), "  /  ", bufstr_get(fr_buf, at + 4));
		sui_text([x, lp_y + tsz * 1.65], [hint, hint], Chat_Fit(s, w - tsz * 3, hint),
		         online ? SUI_THEME_GOOD : SUI_THEME_MUTED, 1, 0);
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
			if (Profile_Chip(strcat("fr_accept", who), [x, y], [bw, hint * 1.9], "Accept", hint, FALSE))
				Friends_Action("accept", who);
			x = x + bw + 4;
		}
		if (Profile_Chip(strcat("fr_del", who), [x, y], [bw, hint * 1.9],
		                 rel == 2 ? "Decline" : (rel == 1 ? "Cancel" : "Remove"), hint, FALSE))
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

void() Friends_Register =
{
	fr_buf = buf_create();
	fr_stage = buf_create();
	registercommand("friend_clear");
	registercommand("friend_begin");
	registercommand("friend_row");
	registercommand("friend_end");
	registercommand("friend_pm");
	registercommand("friend_note");
	registercommand("friend_join");
	registercommand("friends_status");
};

float(string cmd) Friends_ConsoleCommand =
{
	local string c, nm, s;
	local float n, tmp, slot, muted;

	n = tokenize(cmd);
	c = argv(0);
	if (c == "friend_clear")
	{
		fr_n = 0; fr_sn = 0; fr_ready = FALSE; fr_loading = FALSE;
		return TRUE;
	}
	if (c == "friend_begin") { fr_sn = 0; fr_loading = TRUE; return TRUE; }
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
		}
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
		print(sprintf("friends: scroll %.1f wheel %g\n", fr_scroll_y, fr_wheel));
		return TRUE;
	}
	return FALSE;
};
