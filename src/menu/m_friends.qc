// Connected: CSQC's completed private snapshot. Disconnected: read-only proofs
// to one fixed HTTPS service. No lobby capability, key seed or address in cvars.
#define MF_SITE "https://play.proto.bar"
string(string nonce, string op, string who) friends_sign = #0:friends_sign;
float mf_epoch, mf_seen, mf_count, mf_mode, mf_rows;
float mf_req, mf_wire, mf_phase, mf_at, mf_next;
string mf_op, mf_target, mf_note, mf_pick;
vector mf_scroll;

float(string s, float n) MF_Hex =
{
	local float i;
	if (strlen(s) != n) return FALSE;
	for (i = 0; i < n; i = i + 1)
		if (strstrofs("0123456789abcdef", substring(s, i, 1), 0) < 0) return FALSE;
	return TRUE;
};
float(string who) MF_WhoSafe = { return MF_Hex(who, FS_WHO_IDLEN); };
float() MF_Count = { return mf_count; };

void(string s) MF_Note =
{
	if (strcmp(mf_note, "")) strunzone(mf_note);
	mf_note = strzone(s);
};

void() MF_PressClear =
{
	// Replacing a snapshot must not retarget an in-progress press.
	if (sui_hold_index("mf_list") >= 0)
	{
		_hold_action_count = _click_action_count = _release_action_count = 0;
		_holding_click = FALSE;
	}
};

void() MF_Cancel =
{
	mf_req = mf_phase = 0;
	if (strcmp(mf_op, "")) strunzone(mf_op);
	if (strcmp(mf_target, "")) strunzone(mf_target);
	mf_op = mf_target = "";
};

void(string why) MF_Fail =
{
	MF_Cancel();
	MF_PressClear();
	mf_count = -1;
	mf_next = time + 10;
	MF_Note(why);
};

float() MF_Online = { return (cvar("rec_terms") >= FS_TERMS_ONLINE); };
float() MF_Active =
{
	if (!menu_active || menu_screen != SCREEN_CREATE) return FALSE;
	if (!cvar("ui_maps_friends") || !MF_Online()) return FALSE;
	// MENU clientstate follows NetQuake: 1 disconnected, 2 connected/trying.
	return (clientstate() == 1);
};

void(string op, string who) MF_Ask =
{
	// App timeout/cancel does not cancel the engine's HTTP worker. Wait for
	// its callback before replacing it, even across hide/reopen/clicks.
	if (mf_wire) return;
	MF_Cancel();
	mf_op = strzone(op);
	mf_target = strzone(who);
	mf_req = Lob_NextReq();
	mf_phase = 1;
	mf_at = time;
	mf_wire = mf_req;
	if (!uri_get(sprintf("%s/api/social/menu/challenge?op=%s&who=%s", MF_SITE, op, who), mf_req))
	{
		mf_wire = 0;
		MF_Fail("Friends service unavailable. Your friends are not necessarily offline.");
	}
};

void() MF_Init =
{
	registercvar("ui_friends_count", "-1", 0);
	registercvar("ui_friends_epoch", "0", 0);
	mf_count = mf_epoch = mf_mode = -1;
	mf_rows = buf_create();
};

void(float visible) MF_Poll =
{
	local float mode, epoch;
	mode = clientstate();
	if (mode != mf_mode)
	{
		MF_Cancel();
		MF_PressClear();
		mf_count = mf_epoch = -1;
		mf_next = 0;
		mf_mode = mode;
		MF_Note("");
	}
	if (mode == 2)
	{
		epoch = cvar("ui_friends_epoch");
		if (epoch != mf_epoch)
		{
			mf_epoch = epoch;
			mf_seen = time;
			mf_count = bound(-1, cvar("ui_friends_count"), 128);
			MF_PressClear();
		}
		if (time < mf_seen || time - mf_seen > 16) mf_count = -1;
		return;
	}
	if (mode != 1 || !visible || !MF_Online())
	{
		MF_Cancel();
		mf_count = -1;
		mf_next = 0;
		return;
	}
	if (!checkbuiltin(friends_sign))
	{
		mf_count = -1;
		MF_Note("Update World of Surf to use Friends before joining a map.");
		return;
	}
	if (time < mf_seen || time - mf_seen > 16) mf_count = -1;
	if (mf_req)
	{
		if (time < mf_at || time - mf_at > 8)
			MF_Fail("Friends request timed out. This does not mean your friends are offline.");
		return;
	}
	if (mf_wire) return;
	if (time >= mf_next)
	if (!ui_join_busy())
		MF_Ask("list", "-");
};

// Only a fresh backend check can choose a destination. A name prompt resumes
// with a NEW proof, not a retained address or mutable directory row number.
void() MF_ResumeJoin =
{
	if (!MF_Active() || ui_join_busy()) return;
	if (!MF_WhoSafe(mf_pick)) return;
	if (mf_wire)
	{
		MF_Note("Finishing a previous Friends request. Try Join again shortly.");
		return;
	}
	MF_Note("Checking your friend's lobby...");
	MF_Ask("join", mf_pick);
};

void(string who) MF_Join =
{
	if (!MF_Active() || ui_join_busy()) return;
	if (!MF_WhoSafe(who)) return;
	if (strcmp(mf_pick, "")) strunzone(mf_pick);
	mf_pick = strzone(who);
	if (ui_name_gate(3, 0)) return;
	MF_ResumeJoin();
};

float(float reqid, float code, string body) MF_Reply =
{
	local int root, arr, o;
	local float n, i, rel, online, stage;
	local string nonce, expires, ticket, proof, pub, sig, form, who, addr, map, why;
	if (!mf_wire || reqid != mf_wire) return FALSE;
	mf_wire = 0;
	if (!mf_req || reqid != mf_req) return TRUE;
	mf_req = 0;
	if (!MF_Active()) { MF_Cancel(); return TRUE; }
	if (code || strlen(body) > 131072)
	{
		MF_Fail("Friends service unavailable. Your friends are not necessarily offline.");
		return TRUE;
	}
	root = json_parse(body);
	if (!root) { MF_Fail("Friends sent an invalid reply."); return TRUE; }
	if (json_get_float(json_find_object_child(root, "ok")) != 1)
	{
		why = json_get_string(json_find_object_child(root, "error"));
		if (!strcmp(why, "")) why = "Friends unavailable. Try again shortly.";
		MF_Fail(substring(why, 0, 240));
		json_free(root);
		return TRUE;
	}
	if (mf_phase == 1)
	{
		nonce = json_get_string(json_find_object_child(root, "nonce"));
		expires = json_get_string(json_find_object_child(root, "expires"));
		ticket = json_get_string(json_find_object_child(root, "ticket"));
		if (!MF_Hex(nonce, 32) || !MF_Hex(ticket, 64) || strlen(expires) != 10)
		{
			MF_Fail("Friends sent an invalid challenge.");
			json_free(root);
			return TRUE;
		}
		for (i = 0; i < 10; i = i + 1)
			if (strstrofs("0123456789", substring(expires, i, 1), 0) < 0) break;
		if (i != 10) { MF_Fail("Friends sent an invalid challenge."); json_free(root); return TRUE; }
		// The builtin is optional on older engines. No key/nonce ever reaches
		// localcmd, logs, public cvars or a service selected by lobby_dir.
		proof = "";
		if (checkbuiltin(friends_sign)) proof = friends_sign(nonce, mf_op, mf_target);
		if (tokenize(proof) != 2)
		{
			MF_Fail("Friends identity unavailable. Update the game or check this install's signing key.");
			json_free(root);
			return TRUE;
		}
		pub = argv(0); sig = argv(1);
		if (!MF_Hex(pub, 64) || !MF_Hex(sig, 128))
		{
			MF_Fail("Friends identity unavailable."); json_free(root); return TRUE;
		}
		form = sprintf("op=%s&who=%s&nonce=%s&expires=%s&ticket=%s&pub=%s&sig=%s", mf_op, mf_target, nonce, expires, ticket, pub, sig);
		mf_req = Lob_NextReq();
		mf_phase = 2;
		mf_at = time;
		mf_wire = mf_req;
		if (!uri_get(strcat(MF_SITE, "/api/social/menu"), mf_req, "application/x-www-form-urlencoded", form))
		{
			mf_wire = 0;
			MF_Fail("Friends service unavailable.");
		}
		json_free(root);
		return TRUE;
	}
	if (!strcmp(mf_op, "join"))
	{
		addr = json_get_string(json_find_object_child(root, "addr"));
		map = json_get_string(json_find_object_child(root, "map"));
		if (!ui_addr_ok(addr) || !ui_host_allowed(addr))
			MF_Fail("Friends refused an untrusted lobby address.");
		else if (ui_join_busy())
			MF_Fail("A map is already being joined.");
		else
		{
			MF_Cancel();
			mf_next = time + 5;
			MF_Note("Joining your friend...");
			ui_join_cancel();
			if (!ui_prejoin(addr, map))
			{
				localcmd(sprintf("connect %S\n", addr));
				ms_query_stale = TRUE;
				m_close();
			}
		}
		json_free(root);
		return TRUE;
	}
	arr = json_find_object_child(root, "friends");
	n = json_get_length(arr);
	if (!arr || n < 0 || n > 128)
	{
		MF_Fail("Friends sent an invalid list."); json_free(root); return TRUE;
	}
	stage = buf_create();
	for (i = 0; i < n; i = i + 1)
	{
		o = json_get_child_at_index(arr, i);
		who = json_get_string(json_find_object_child(o, "who"));
		rel = json_get_float(json_find_object_child(o, "relation"));
		if (!MF_WhoSafe(who) || rel < 1 || rel > 4 || rel != floor(rel)) break;
		online = (rel == 3 && json_get_float(json_find_object_child(o, "online")) == 1);
		bufstr_set(stage, i, sprintf("%s %g %g \"%s\" \"%s\" \"%s\"", who, rel, online,
			uri_escape(substring(json_get_string(json_find_object_child(o, "name")), 0, 64)),
			uri_escape(substring(json_get_string(json_find_object_child(o, "server")), 0, 128)),
			uri_escape(substring(json_get_string(json_find_object_child(o, "map")), 0, 64))));
	}
	if (i != n)
	{
		buf_del(stage);
		MF_Fail("Friends sent an invalid list.");
	}
	else
	{
		MF_PressClear();
		buf_del(mf_rows);
		mf_rows = stage;
		mf_count = n;
		mf_seen = time;
		mf_next = time + 5;
		MF_Cancel();
		MF_Note("");
	}
	json_free(root);
	return TRUE;
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
	{
		cvar_set("ui_maps_friends", "0");
		MF_Cancel();
	}
	if (!MF_Online())
		ui_para('16 60 0', size_x - 32, SZ_LABEL, 20,
		        "Friends needs online features enabled in Settings / Privacy.", COL_DIM, TRUE);
	else if (mf_count < 0)
	{
		status = mf_note;
		if (!strcmp(status, "")) status = mf_req ? "Loading your friends..." : "Friends unavailable. Link Steam on an account-enabled lobby once, then you can see friends here without loading a map. An unavailable list does not mean your friends are offline.";
		ui_para('16 60 0', size_x - 32, SZ_LABEL, 20, status, COL_DIM, TRUE);
	}
	else if (!mf_count)
		ui_para('16 60 0', size_x - 32, SZ_LABEL, 20,
		        "No friends yet. In a lobby, add someone from TAB > Players.", COL_DIM, TRUE);
	else
	{
		status = strcmp(mf_note, "") ? mf_note : "Private lobby presence";
		sui_text('16 52 0', '12 12 0', ui_fit_text(status, size_x - 32, '12 12 0'), COL_DIM, 1, 0);
		sui_list_view_begin("mf_list", '12 76 0', [size_x - 24, size_y - 88], [size_x - 38, 102], mf_count, mf_scroll, [0, 8]);
		rp = '0 0 0';
		for (i = sui_list_item(rp); i > -1; i = sui_list_item(rp))
		{
			if (clientstate() == 2)
				at = tokenize(cvar_string(strcat("ui_friend_", ftos(i))));
			else
				at = tokenize(bufstr_get(mf_rows, i));
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
			if (rel == 4) status = "Blocked";
			if (online) status = server;
			sui_text(rp + '10 32 0', '12 12 0', ui_fit_text(status, size_x - 60, '12 12 0'), online ? SUI_THEME_GOOD : COL_DIM, 1, 0);
			if (online)
			{
				sui_text(rp + '10 54 0', '12 12 0', ui_fit_text(map, size_x - 144, '12 12 0'), COL_DIM, 1, 0);
				if (ui_button(id, rp + [size_x - 122, 54], [74, 28], "Join"))
				if (!ui_join_busy())
				if (MF_WhoSafe(who))
				{
					if (clientstate() == 2)
						localcmd(sprintf("friends_menu_join %s\n", who));
					else
						MF_Join(who);
				}
			}
		}
		sui_list_view_end();
	}
	sui_pop_frame();
};
