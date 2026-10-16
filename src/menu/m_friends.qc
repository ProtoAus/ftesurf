// Read-only view of CSQC's completed, private lobby snapshot. Never an HTTP reader.
float mf_epoch, mf_seen, mf_count;
vector mf_scroll;

float(string who) MF_WhoSafe =
{
	local float i;
	if (strlen(who) != FS_WHO_IDLEN) return FALSE;
	for (i = 0; i < strlen(who); i = i + 1)
		if (strstrofs("0123456789abcdef", substring(who, i, 1), 0) < 0) return FALSE;
	return TRUE;
};

float() MF_Count = { return mf_count; };

void() MF_Init =
{
	registercvar("ui_friends_count", "-1", 0);
	registercvar("ui_friends_epoch", "0", 0);
	mf_count = -1;
	mf_epoch = -1;
};

void() MF_Poll =
{
	local float epoch;
	if (clientstate() != 2)
	{
		mf_count = -1;
		mf_epoch = -1;
		cvar_set("ui_friends_count", "-1");
		return;
	}
	epoch = cvar("ui_friends_epoch");
	if (epoch != mf_epoch)
	{
		mf_epoch = epoch;
		mf_seen = time;
		mf_count = bound(-1, cvar("ui_friends_count"), 128);
		// A snapshot replacement must not retarget an in-progress press.
		if (sui_hold_index("mf_list") >= 0)
		{
			_hold_action_count = _click_action_count = _release_action_count = 0;
			_holding_click = FALSE;
		}
	}
	if (time - mf_seen > 16) mf_count = -1;
};

void(vector pos, vector size) MF_Draw =
{
	local float i, rel, online, at;
	local vector rp;
	local string who, nm, server, map, status, id;
	sui_style_panel(pos, size, 12, 1);
	sui_push_frame(pos, size);
	sui_text('16 12 0', SZ_HEAD, "friends", COL_ACCENT, 1, 0);
	if (ui_button("mf_close", [size_x - 76, 12], [60, 28], "Hide"))
		cvar_set("ui_maps_friends", "0");
	if (clientstate() != 2)
		ui_para('16 60 0', size_x - 32, SZ_LABEL, 20,
		        "Connect to an account-enabled lobby to see your Steam-linked friends and where they are playing. Presence is private; it is not available while disconnected.", COL_DIM, TRUE);
	else if (mf_count < 0)
		ui_para('16 60 0', size_x - 32, SZ_LABEL, 20,
		        "Friends unavailable. Link Steam on an account-enabled lobby. This lobby must support Friends; an unavailable list does not mean your friends are offline.", COL_DIM, TRUE);
	else if (!mf_count)
		ui_para('16 60 0', size_x - 32, SZ_LABEL, 20,
		        "No friends yet. Open a player's profile in the Players tab to add them.", COL_DIM, TRUE);
	else
	{
		sui_text('16 52 0', '12 12 0', "Private lobby presence", COL_DIM, 1, 0);
		sui_list_view_begin("mf_list", '12 76 0', [size_x - 24, size_y - 88], [size_x - 38, 102], mf_count, mf_scroll, [0, 8]);
		rp = '0 0 0';
		for (i = sui_list_item(rp); i > -1; i = sui_list_item(rp))
		{
			at = tokenize(cvar_string(strcat("ui_friend_", ftos(i))));
			if (at != 6) continue;
			who = argv(0);
			rel = stof(argv(1));
			online = (rel == 3 && stof(argv(2)) != 0);
			nm = uri_unescape(argv(3));
			server = uri_unescape(argv(4));
			map = uri_unescape(argv(5));
			id = strcat("mf_join", who);
			sui_style_box(rp, [size_x - 38, 96], 8, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
			sui_text(rp + '10 8 0', SZ_ROW, ui_fit_text(nm, size_x - 60, SZ_ROW), COL_TEXT, 1, 0);
			status = "Offline";
			if (rel == 1) status = "Friend request sent";
			if (rel == 2) status = "Incoming friend request";
			if (online) status = server;
			sui_text(rp + '10 32 0', '12 12 0', ui_fit_text(status, size_x - 60, '12 12 0'), online ? SUI_THEME_GOOD : COL_DIM, 1, 0);
			if (online)
			{
				sui_text(rp + '10 54 0', '12 12 0', ui_fit_text(map, size_x - 144, '12 12 0'), COL_DIM, 1, 0);
				if (ui_button(id, rp + [size_x - 122, 54], [74, 28], "Join"))
				if (!ui_join_busy())
				if (MF_WhoSafe(who))
				{
					// No client address: the authenticated lobby resolves presence again.
					localcmd(sprintf("friends_menu_join %s\n", who));
				}
			}
		}
		sui_list_view_end();
	}
	sui_pop_frame();
};
