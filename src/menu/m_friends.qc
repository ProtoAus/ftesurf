// Connected: CSQC's completed snapshot. Disconnected: Friends/presence proofs
// to one fixed HTTPS service. No lobby capability, key seed or address in cvars.
#define MF_SITE "https://play.proto.bar"
string(string nonce, string op, string who) friends_sign = #0:friends_sign;
float(string src, string dst) frename = #0:frename;
float mf_epoch, mf_seen, mf_seenmode, mf_count, mf_mode, mf_rows, mf_boot;
float mf_req, mf_wire, mf_phase, mf_at, mf_next, mf_siglen, mf_sigcrc;
float mf_presence_req, mf_presence_wire, mf_presence_phase, mf_presence_at, mf_presence_next;
string mf_op, mf_target, mf_note, mf_pick;
vector mf_scroll;

// Patch 781: the last list, names and relations only (no `who`, no presence),
// shown as "Saved list" until a fresh one replaces it.
#define MF_FILE  "data/friends_menu.txt"
#define MF_TMP   "data/friends_menu.tmp"
#define MF_HEAD  "FTESURF-FRIENDS 1"

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

// clientstate and the list's source together: a local game -> lobby connect keeps
// clientstate 2 but changes who supplies the list (P975 review).
float() MF_Mode = { return clientstate() * 2 + MF_Direct(); };

// Rows held are this mode's and under 16 s old. P731: older is unavailable, not offline.
float() MF_Fresh =
{
	if (mf_seen <= 0 || mf_seenmode != MF_Mode()) return FALSE;
	return (time >= mf_seen && time - mf_seen <= 16);
};

string(float s) MF_Ago =
{
	s = max(0, floor(s));
	if (s < 60) return sprintf("%g s", s);
	if (s < 3600) return sprintf("%g min", floor(s / 60));
	return sprintf("%g h", floor(s / 3600));
};

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

// Held rows stay up; the header says why they are not fresh.
void(string why) MF_Fail =
{
	MF_Cancel();
	MF_PressClear();
	mf_next = time + 10;
	mf_boot = TRUE;
	MF_Note(why);
};

float() MF_Online = { return (cvar("rec_terms") >= FS_TERMS_ONLINE); };

// The menu asks the Friends service itself: disconnected, or in a game with no
// account service behind it (a private local game, board "local"), where CSQC
// never gets a list to publish. MENU clientstate: 1 disconnected, 2 connected.
// Patch 992: and in an online lobby whose relay has published nothing (-1: not
// Steam-linked there, no proof, master unreachable) for MF_RELAY_WAIT -- a working
// relay publishes in ~5 s, and every map change resets it to -1. The first snapshot
// takes over, except under a direct join in flight, whose answer would be dropped.
// The list op writes no presence (social.py menu_read), so friends still see the lobby.
#define MF_RELAY_WAIT 8
float mf_relaygone;     // when the relay's count was first seen at -1; 0 while it publishes
float() MF_Direct =
{
	local float c;
	c = clientstate();
	if (c == 1) return TRUE;
	if (c != 2) return FALSE;
	if (serverkey("board") == "local") return TRUE;
	if (mf_req)
	if (!strcmp(mf_op, "join"))
	if (mf_mode == clientstate() * 2 + 1)
		return TRUE;
	if (cvar("ui_friends_count") >= 0)
	{
		mf_relaygone = 0;
		return FALSE;
	}
	if (!mf_relaygone || time < mf_relaygone)
		mf_relaygone = time;
	return (time - mf_relaygone > MF_RELAY_WAIT);
};

string() MF_ProbeNote = { return sprintf("req=%g wire=%g note=%S", mf_req, mf_wire, mf_note); };

float() MF_Active =
{
	if (!menu_active || menu_screen != SCREEN_CREATE) return FALSE;
	if (!cvar("ui_maps_friends") || !MF_Online()) return FALSE;
	return MF_Direct();
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

// Written only when the names or relations changed; Windows rename cannot replace.
void() MF_Save =
{
	local filestream fh;
	local float i;
	local string text;
	text = "";
	for (i = 0; i < mf_count; i = i + 1)
		if (tokenize(bufstr_get(mf_rows, i)) >= 6)
		if (MF_WhoSafe(argv(0)))
			text = strcat(text, argv(1), " \"", argv(3), "\"\n");
	if (strlen(text) == mf_siglen && crc16(FALSE, text) == mf_sigcrc) return;
	fh = fopen(MF_TMP, FILE_WRITE);
	if (fh < 0) return;
	fputs(fh, strcat(MF_HEAD, "\n"));
	fputs(fh, text);
	fclose(fh);
	fremove(MF_FILE);
	if (frename(MF_TMP, MF_FILE) != 0)
	{
		fremove(MF_TMP);
		return;
	}
	mf_siglen = strlen(text);
	mf_sigcrc = crc16(FALSE, text);
};

void() MF_LoadSaved =
{
	local filestream fh;
	local float n, rel;
	local string ln, text;
	fh = fopen(MF_FILE, FILE_READ);
	if (fh < 0) return;
	if (fgets(fh) != MF_HEAD) { fclose(fh); return; }
	n = 0;
	text = "";
	for (ln = fgets(fh); ln != "" && n < 128; ln = fgets(fh))
	{
		if (tokenize(ln) != 2) continue;
		rel = stof(argv(0));
		if (rel < 1 || rel > 4 || rel != floor(rel) || strlen(argv(1)) > 192) continue;
		// `who` "-": no Join and no presence until a fresh list replaces it.
		bufstr_set(mf_rows, n, sprintf("- %g 0 \"%s\" \"\" \"\"", rel, argv(1)));
		text = strcat(text, ftos(rel), " \"", argv(1), "\"\n");
		n = n + 1;
	}
	fclose(fh);
	if (!n) return;
	mf_count = n;
	mf_siglen = strlen(text);
	mf_sigcrc = crc16(FALSE, text);
};

void() MF_Init =
{
	registercvar("ui_friends_count", "-1", 0);
	registercvar("ui_friends_epoch", "0", 0);
	mf_count = mf_epoch = mf_mode = -1;
	mf_rows = buf_create();
	MF_LoadSaved();
};

/*
  A new list replaces the held one.  The server's presence TTL is 16 s and a
  lobby polls every 5 s, so one late poll reads a friend offline for one
  reply: a row online (flag 1) in the last fresh list is carried online once,
  as flag 2, with its old server and map.
*/
void(float stage, float n) MF_Swap =
{
	local float i, j;
	local hashtable was;
	local string who, nm;
	if (mf_seen > 0 && mf_count > 0)
	{
		was = hash_createtab(256, EV_FLOAT);
		for (i = 0; i < mf_count; i = i + 1)
			if (tokenize(bufstr_get(mf_rows, i)) >= 6)
			if (stof(argv(2)) == 1)
				hash_add(was, argv(0), i + 1, HASH_REPLACE | EV_FLOAT);
		for (i = 0; i < n; i = i + 1)
		{
			j = tokenize(bufstr_get(stage, i));
			if (j < 6) continue;
			if (j == 8 && stof(argv(7)) == 1) continue;
			if (stof(argv(1)) != 3 || stof(argv(2)) != 0) continue;
			j = hash_get(was, argv(0), 0, EV_FLOAT);
			if (!j) continue;
			who = argv(0);
			nm = argv(3);
			tokenize(bufstr_get(mf_rows, j - 1));
			bufstr_set(stage, i, sprintf("%s 3 2 \"%s\" \"%s\" \"%s\" \"%s\"", who, nm, argv(4), argv(5), argv(6)));
		}
		hash_destroytab(was);
	}
	MF_PressClear();
	buf_del(mf_rows);
	mf_rows = stage;
	mf_count = n;
	mf_seen = time;
	mf_seenmode = MF_Mode();
	MF_Save();
};

// Connected: CSQC publishes a completed snapshot (~5 s); copy it so rows survive a disconnect.
void() MF_TakeCvars =
{
	local float i, n, k, stage, fields;
	local string row;
	n = cvar("ui_friends_count");
	if (n < 0) return;
	n = min(n, 128);
	stage = buf_create();
	k = 0;
	for (i = 0; i < n; i = i + 1)
	{
		row = cvar_string(strcat("ui_friend_", ftos(i)));
		fields = tokenize(row);
		if (fields != 6 && fields != 7 && fields != 8) continue;
		if (!MF_WhoSafe(argv(0))) continue;
		bufstr_set(stage, k, row);
		k = k + 1;
	}
	MF_Swap(stage, k);
};

// Independent of the visible Friends panel and its list/join request slot.
void() MF_PresencePoll =
{
	if (clientstate() != 1 || !MF_Online())
	{
		mf_presence_req = mf_presence_phase = 0;
		mf_presence_next = time + 10;
		return;
	}
	if (!checkbuiltin(friends_sign)) return;
	if (mf_presence_req)
	{
		if (time < mf_presence_at || time - mf_presence_at > 8)
		{
			mf_presence_req = mf_presence_phase = 0;
			mf_presence_next = time + 30;
		}
		return;
	}
	if (mf_presence_wire || time < mf_presence_next) return;
	mf_presence_req = Lob_NextReq();
	mf_presence_wire = mf_presence_req;
	mf_presence_phase = 1;
	mf_presence_at = time;
	mf_presence_next = time + 10;
	if (!uri_get(strcat(MF_SITE, "/api/social/menu/challenge?op=presence&who=-"), mf_presence_req))
	{
		mf_presence_req = mf_presence_wire = mf_presence_phase = 0;
		mf_presence_next = time + 30;
	}
};

float(float reqid, float code, string body) MF_PresenceReply =
{
	local int root;
	local float phase, i;
	local string nonce, expires, ticket, proof, pub, sig, form;
	if (!mf_presence_wire || reqid != mf_presence_wire) return FALSE;
	mf_presence_wire = 0;
	if (!mf_presence_req || reqid != mf_presence_req) return TRUE;
	phase = mf_presence_phase;
	mf_presence_req = mf_presence_phase = 0;
	mf_presence_next = time + 30;
	if (clientstate() != 1 || !MF_Online() || code || strlen(body) > 4096) return TRUE;
	root = json_parse(body);
	if (!root) return TRUE;
	if (json_get_float(json_find_object_child(root, "ok")) != 1)
	{
		json_free(root);
		return TRUE;
	}
	if (phase == 2)
	{
		mf_presence_next = time + 10;
		json_free(root);
		return TRUE;
	}
	nonce = json_get_string(json_find_object_child(root, "nonce"));
	expires = json_get_string(json_find_object_child(root, "expires"));
	ticket = json_get_string(json_find_object_child(root, "ticket"));
	if (!MF_Hex(nonce, 32) || !MF_Hex(ticket, 64) || strlen(expires) != 10)
	{
		json_free(root);
		return TRUE;
	}
	for (i = 0; i < 10; i = i + 1)
		if (strstrofs("0123456789", substring(expires, i, 1), 0) < 0) break;
	if (i != 10) { json_free(root); return TRUE; }
	proof = "";
	if (checkbuiltin(friends_sign)) proof = friends_sign(nonce, "presence", "-");
	if (tokenize(proof) != 2) { json_free(root); return TRUE; }
	pub = argv(0); sig = argv(1);
	if (!MF_Hex(pub, 64) || !MF_Hex(sig, 128)) { json_free(root); return TRUE; }
	form = sprintf("op=presence&who=-&nonce=%s&expires=%s&ticket=%s&pub=%s&sig=%s", nonce, expires, ticket, pub, sig);
	mf_presence_req = Lob_NextReq();
	mf_presence_wire = mf_presence_req;
	mf_presence_phase = 2;
	mf_presence_at = time;
	if (!uri_get(strcat(MF_SITE, "/api/social/menu"), mf_presence_req, "application/x-www-form-urlencoded", form))
		mf_presence_req = mf_presence_wire = mf_presence_phase = 0;
	json_free(root);
	return TRUE;
};

void(float visible) MF_Poll =
{
	local float mode, epoch;
	MF_PresencePoll();
	mode = MF_Mode();
	if (mode != mf_mode)
	{
		// Rows stay up across a connect or disconnect; MF_Fresh marks them stale.
		MF_Cancel();
		MF_PressClear();
		mf_epoch = -1;
		mf_next = 0;
		mf_mode = mode;
		MF_Note("");
	}
	if (clientstate() == 2 && !MF_Direct())
	{
		epoch = cvar("ui_friends_epoch");
		if (epoch != mf_epoch)
		{
			mf_epoch = epoch;
			MF_TakeCvars();
		}
		return;
	}
	if (!MF_Direct() || !MF_Online())
	{
		MF_Cancel();
		return;
	}
	if (!checkbuiltin(friends_sign))
	{
		if (!strcmp(mf_note, ""))
			MF_Note("Update World of Surf to use Friends before joining a map.");
		return;
	}
	// Patch 781 (Lex): one list at launch with the panel hidden; after that a
	// hidden panel finishes nothing, as P741 had it.
	if (!visible)
	if (mf_boot)
	{
		MF_Cancel();
		return;
	}
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
// Each map-browser opening reveals Friends and requests new presence.
void() MF_Open =
{
	MFP_Close();
	cvar_set("ui_maps_friends", "1");
	mf_next = 0;
	if (MF_Online())
	if (!MF_Direct())
	if (cvar("ui_friends_activity") > 0 && cvar("ui_friends_activity") == cvar("ui_friends_epoch"))
		localcmd("cmd friend refresh -\n");
};

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
	if (MF_PresenceReply(reqid, code, body)) return TRUE;
	if (MFP_Reply(reqid, code, body)) return TRUE;
	if (!mf_wire || reqid != mf_wire) return FALSE;
	mf_wire = 0;
	if (!mf_req || reqid != mf_req) return TRUE;
	mf_req = 0;
	// A join needs the open panel; a list may land hidden (the launch fetch).
	if (!strcmp(mf_op, "join"))
	{
		if (!MF_Active()) { MF_Cancel(); return TRUE; }
	}
	else if (!MF_Online() || !MF_Direct()) { MF_Cancel(); return TRUE; }
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
			ui_eventfog_target("");
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
		bufstr_set(stage, i, strcat(sprintf("%s %g %g \"%s\" \"%s\" \"%s\" \"%s\"", who, rel, online,
			uri_escape(substring(json_get_string(json_find_object_child(o, "name")), 0, 64)),
			uri_escape(substring(json_get_string(json_find_object_child(o, "server")), 0, 128)),
			uri_escape(substring(json_get_string(json_find_object_child(o, "map")), 0, 64)),
			uri_escape(substring(json_get_string(json_find_object_child(o, "activity")), 0, 24))),
			" ", ftos(rel == 3 && json_get_float(json_find_object_child(o, "menu_online")) == 1)));
	}
	if (i != n)
	{
		buf_del(stage);
		MF_Fail("Friends sent an invalid list.");
	}
	else
	{
		MF_Swap(stage, n);
		mf_next = time + 5;
		mf_boot = TRUE;
		MF_Cancel();
		MF_Note("");
	}
	json_free(root);
	return TRUE;
};

void(vector pos, vector size) MF_Draw =
{
	local float i, rel, online, menuonline, at, fresh, alpha, flag, room;
	local vector rp;
	local string who, nm, server, map, status, id, ago, activity;
	if (MFP_IsOpen()) { MFP_Draw(pos, size); return; }
	sui_style_panel(pos, size, 12, 1);
	sui_push_frame(pos, size);
	sui_text('16 12 0', SZ_HEAD, "friends", COL_ACCENT, 1, 0);
	if (ui_button("mf_close", [size_x - 76, 12], [60, 28], "Hide"))
	{
		cvar_set("ui_maps_friends", "0");
		MF_Cancel();
	}
	fresh = MF_Fresh();
	ago = (mf_seen > 0) ? MF_Ago(time - mf_seen) : "";
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
		if (fresh)
			status = strcmp(mf_note, "") ? mf_note : "Private lobby presence";
		else
		{
			status = (mf_seen > 0) ? strcat("Updated ", ago, " ago") : "Saved list";
			if (mf_req)
				status = strcat(status, " -- refreshing");
			else if (strcmp(mf_note, ""))
				status = strcat(status, " -- ", mf_note);
		}
		sui_text('16 52 0', '12 12 0', ui_fit_text(status, size_x - 32, '12 12 0'), COL_DIM, 1, 0);
		sui_list_view_begin("mf_list", '12 76 0', [size_x - 24, size_y - 88], [size_x - 38, 64], mf_count, mf_scroll, [0, 8]);
		rp = '0 0 0';
		for (i = sui_list_item(rp); i > -1; i = sui_list_item(rp))
		{
			at = tokenize(bufstr_get(mf_rows, i));
			if (at != 6 && at != 7 && at != 8) continue;
			who = argv(0);
			rel = stof(argv(1));
			flag = stof(argv(2));
			online = (rel == 3 && flag == 1 && fresh);
			menuonline = (rel == 3 && at == 8 && stof(argv(7)) == 1 && fresh);
			nm = uri_unescape(argv(3));
			server = uri_unescape(argv(4));
			map = uri_unescape(argv(5));
			activity = at >= 7 ? uri_unescape(argv(6)) : "";
			alpha = (online || menuonline) ? 1 : 0.45;
			room = size_x - 114;
			sui_style_box(rp, [size_x - 38, 64], 8, SUI_THEME_WELL, SUI_THEME_EDGE, alpha);
			if (MF_WhoSafe(who))
			if (!MP_Draw(rp + '10 10 0', 44, who, alpha))
				sui_roundbox(rp + '10 10 0', '44 44 0', 8, SUI_THEME_CHIP, alpha);
			id = strcat("mf_profile", who);
			sui_action_element(rp + '64 8 0', [room, 24], id, sui_noop);
			sui_text(rp + '64 12 0', SZ_ROW, ui_fit_text(nm, room, SZ_ROW), COL_TEXT, alpha, 0);
			if (sui_is_released(id) && MF_WhoSafe(who))
			{
				MFP_Open(who, nm);
			}
			status = fresh ? "Offline" : "Checking...";
			if (rel == 1) status = "Added -- waiting for them";
			if (rel == 2) status = "Added you";
			if (rel == 4) status = "Blocked";
			if (menuonline) status = "Main menu";
			if (online)
			{
				status = strcat(ui_fit_text(map, max(16, room - stringwidth(activity, TRUE, '12 12 0') - 8), '12 12 0'), "  ", activity);
				id = strcat("mf_join", who);
				sui_action_element(rp + '64 32 0', [room, 24], id, sui_noop);
				// Patch 991: underline the map under the cursor, so it reads as a link.
				if (sui_is_hovered(id))
					sui_fill(rp + '64 49 0', [min(room, stringwidth(ui_fit_text(map,
					         max(16, room - stringwidth(activity, TRUE, '12 12 0') - 8), '12 12 0'),
					         TRUE, '12 12 0')), 1], SUI_THEME_GOOD, alpha, 0);
				// The location is the join target, never the profile/name row.
				if (sui_is_released(id) && MF_WhoSafe(who))
				if (!ui_join_busy())
				{
					if (!MF_Direct()) localcmd(sprintf("friends_menu_join %s\n", who));
					else MF_Join(who);
				}
			}
			else if (rel == 3 && flag == 2) status = strcat("Last seen: ", map);
			sui_text(rp + '64 36 0', '12 12 0', ui_fit_text(status, room, '12 12 0'), (online || menuonline) ? SUI_THEME_GOOD : COL_DIM, alpha, 0);
			if (rel == 2 && !MF_Direct() && MF_WhoSafe(who))
			if (ui_button(strcat("mf_add", who), rp + [size_x - 126, 32], [78, 24], "Add back"))
				localcmd(sprintf("friends_menu_add %s\n", who));
		}
		sui_list_view_end();
	}
	sui_pop_frame();
};
