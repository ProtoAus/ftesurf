// P963: explicit main-menu lobby/DM screen. No text/proof cache on disk or cvars.
#define MC_MSG_H 96
float mc_rows, mc_view, mc_friends;
float mc_count, mc_height, mc_cursor;
vector mc_scroll, mc_friend_scroll;
float mc_visible, mc_req, mc_wire, mc_phase, mc_at, mc_next, mc_seen;
string mc_peer, mc_peer_name, mc_me, mc_draft, mc_note;
string mc_op, mc_target, mc_sent;

void(__inout string dst, string src) MC_Keep =
{
	if (dst) strunzone(dst);
	dst = strzone(src);
};

void() MC_Init =
{
	mc_rows = mc_view = mc_friends = -1;
	MC_Keep(mc_peer, "-");
	MC_Keep(mc_peer_name, "Public lobby");
};

void() MC_Open =
{
	m_open();
	sui_text_unfocus();
	menu_screen = SCREEN_CHAT;
};

// P1010: in a game too.  Reading is a read anywhere; a send in a lobby is refused:
// the engine signs none there, and handing the text to the connected server would
// give it to whichever server that is (review: a server can fake the relay's cvar).
float() MC_Active =
{
	return (menu_active && (menu_screen == SCREEN_CHAT || menu_screen == SCREEN_MAIN) && clientstate() >= 1 && MF_Online());
};

float() MC_Relayed = { return (clientstate() == 2 && serverkey("board") != "local"); };

string(string text) MC_Plain = { return strreplace("^", "^^", text); };

void() MC_Rebuild =
{
	local float i, follow;
	local string row;
	follow = (mc_scroll_y >= max(0, mc_count * MC_MSG_H - mc_height) - 8);
	if (mc_view >= 0) buf_del(mc_view);
	mc_view = buf_create();
	mc_count = 0;
	if (mc_rows < 0) return;
	for (i = 0; i < buf_getsize(mc_rows); i = i + 1)
	{
		row = bufstr_get(mc_rows, i);
		if (tokenize(row) != 4) continue;
		if (strcmp(argv(0), mc_peer)) continue;
		bufstr_set(mc_view, mc_count, row);
		mc_count = mc_count + 1;
	}
	if (follow) mc_scroll_y = 999999;
};

void(string who, string name) MC_Select =
{
	if (mc_wire) return;
	MC_Keep(mc_peer, who);
	MC_Keep(mc_peer_name, name);
	MC_Keep(mc_draft, "");
	mc_cursor = 0;
	mc_scroll_y = 999999;
	MC_Rebuild();
};

void() MC_Clear =
{
	if (mc_rows >= 0) buf_del(mc_rows);
	if (mc_view >= 0) buf_del(mc_view);
	if (mc_friends >= 0) buf_del(mc_friends);
	mc_rows = mc_view = mc_friends = -1;
	mc_count = mc_seen = mc_cursor = 0;
	MC_Keep(mc_me, "");
	MC_Keep(mc_draft, "");
	MC_Keep(mc_sent, "");
	MC_Keep(mc_peer, "-");
	MC_Keep(mc_peer_name, "Public lobby");
};

void(string why) MC_Fail =
{
	mc_req = mc_phase = 0;
	mc_next = time + 15;
	MC_Keep(mc_note, why);
};

void(string op, string target) MC_Request =
{
	if (!MC_Active() || mc_wire) return;
	MC_Keep(mc_op, op);
	MC_Keep(mc_target, target);
	mc_req = Lob_NextReq();
	mc_wire = mc_req;
	mc_phase = 1;
	mc_at = time;
	mc_next = time + 8;
	if (!uri_get(strcat(MF_SITE, "/api/social/menu/challenge?op=", op, "&who=", uri_escape(target)), mc_req))
	{
		mc_wire = 0;
		MC_Fail("Chat service unavailable.");
	}
};

void() MC_Send =
{
	if (!MC_Active() || mc_wire || !strlen(mc_draft)) return;
	if (strlen(mc_draft) > 320)
	{
		MC_Keep(mc_note, "Use 1-160 characters on one line.");
		return;
	}
	if (MC_Relayed())
	{
		MC_Keep(mc_note, "In a lobby, talk to everyone from the game's chat: the team-chat key, or TAB in a chat line.");
		return;
	}
	MC_Keep(mc_sent, mc_draft);
	MC_Keep(mc_note, "Sending...");
	MC_Request("message", strcat(mc_peer, ":", strtolower(digest_hex("SHA256", mc_sent))));
};

void(float visible) MC_Poll =
{
	if (!visible || !MC_Active())
	{
		if (mc_visible) MC_Clear();
		mc_visible = 0;
		// Keep the wire tombstone until its callback; never stack timed-out requests.
		mc_req = mc_phase = 0;
		return;
	}
	if (!mc_visible)
	{
		MC_Clear();
		mc_visible = 1;
		mc_next = 0;
		MC_Keep(mc_note, "Connecting to chat...");
	}
	if (mc_req)
	{
		if (time < mc_at || time - mc_at > 8)
			MC_Fail("No confirmation. Check chat before sending again.");
		return;
	}
	if (mc_wire || time < mc_next) return;
	MC_Request("chat", "-");
};

// Patch 1000: remember and send this install's mark (see m_init); a mark is 8 hex.
void(string mark, float boot) MC_SelfMark =
{
	if (!MF_Hex(mark, 8)) return;
	if (!boot)
	if (!strcmp(mark, cvar_string("cl_self_mark")))
		return;
	cvar_set("cl_self_mark", mark);
	localcmd(sprintf("setinfo _smark %s\n", mark));
};

float(int root) MC_Snapshot =
{
	local int arr, row;
	local float n, i, pass, stage, friends, j;
	local string who, peer, name, text, me;
	me = json_get_string(json_find_object_child(root, "me"));
	if (!MF_Hex(me, 8)) return FALSE;
	MC_SelfMark(me, FALSE);
	if (strcmp(me, mc_me))
	{
		MC_Clear();
		MC_Keep(mc_me, me);
	}
	stage = buf_create();
	j = 0;
	for (pass = 0; pass < 2; pass = pass + 1)
	{
		arr = json_find_object_child(root, pass ? "messages" : "room");
		n = json_get_length(arr);
		if (!arr || n < 0 || n > 32) { buf_del(stage); return FALSE; }
		for (i = 0; i < n; i = i + 1)
		{
			row = json_get_child_at_index(arr, i);
			who = json_get_string(json_find_object_child(row, "who"));
			peer = pass ? json_get_string(json_find_object_child(row, "peer")) : "-";
			name = json_get_string(json_find_object_child(row, "name"));
			text = json_get_string(json_find_object_child(row, "text"));
			if (!MF_Hex(who, 8) || strlen(name) > 192 || !strlen(text) || strlen(text) > 320) continue;
			if (pass) if (!MF_Hex(peer, 8)) continue;
			if (!strlen(name)) name = "Player";
			bufstr_set(stage, j, strcat(peer, " ", who, " ", uri_escape(name), " ", uri_escape(text)));
			j = j + 1;
		}
	}
	arr = json_find_object_child(root, "friends");
	n = json_get_length(arr);
	if (!arr || n < 0 || n > 128) { buf_del(stage); return FALSE; }
	friends = buf_create();
	j = 0;
	for (i = 0; i < n; i = i + 1)
	{
		row = json_get_child_at_index(arr, i);
		who = json_get_string(json_find_object_child(row, "who"));
		name = json_get_string(json_find_object_child(row, "name"));
		if (!MF_Hex(who, 8) || !strlen(name) || strlen(name) > 192) continue;
		if (json_get_float(json_find_object_child(row, "relation")) != 3) continue;
		bufstr_set(friends, j, strcat(who, " ", uri_escape(name)));
		j = j + 1;
	}
	if (mc_rows >= 0) buf_del(mc_rows);
	if (mc_friends >= 0) buf_del(mc_friends);
	mc_rows = stage;
	mc_friends = friends;
	mc_seen = time;
	MC_Rebuild();
	return TRUE;
};

float(float reqid, float code, string body) MC_Reply =
{
	local int root;
	local float i;
	local string nonce, expires, ticket, proof, pub, sig, form, why;
	if (!mc_wire || reqid != mc_wire) return FALSE;
	mc_wire = 0;
	if (!mc_req || reqid != mc_req) return TRUE;
	mc_req = 0;
	if (!MC_Active()) return TRUE;
	if (code || strlen(body) > 131072) { MC_Fail("Chat service unavailable."); return TRUE; }
	root = json_parse(body);
	if (!root) { MC_Fail("Invalid chat reply."); return TRUE; }
	if (json_get_float(json_find_object_child(root, "ok")) != 1)
	{
		why = json_get_string(json_find_object_child(root, "error"));
		if (!strlen(why)) why = "Chat unavailable. Check that the game is up to date.";
		MC_Fail(substring(why, 0, 240));
		json_free(root);
		return TRUE;
	}
	if (mc_phase == 1)
	{
		nonce = json_get_string(json_find_object_child(root, "nonce"));
		expires = json_get_string(json_find_object_child(root, "expires"));
		ticket = json_get_string(json_find_object_child(root, "ticket"));
		if (!MF_Hex(nonce, 32) || !MF_Hex(ticket, 64) || strlen(expires) != 10)
		{
			MC_Fail("Invalid chat challenge."); json_free(root); return TRUE;
		}
		for (i = 0; i < 10; i = i + 1)
			if (strstrofs("0123456789", substring(expires, i, 1), 0) < 0) break;
		if (i != 10) { MC_Fail("Invalid chat challenge."); json_free(root); return TRUE; }
		proof = "";
		if (checkbuiltin(friends_sign)) proof = friends_sign(nonce, mc_op, mc_target);
		if (tokenize(proof) != 2)
		{
			MC_Fail("Update the native game client to use main-menu chat."); json_free(root); return TRUE;
		}
		pub = argv(0); sig = argv(1);
		if (!MF_Hex(pub, 64) || !MF_Hex(sig, 128))
		{
			MC_Fail("Chat identity unavailable."); json_free(root); return TRUE;
		}
		form = sprintf("op=%s&who=%s&nonce=%s&expires=%s&ticket=%s&pub=%s&sig=%s",
		               mc_op, uri_escape(mc_target), nonce, expires, ticket, pub, sig);
		if (!strcmp(mc_op, "message")) form = strcat(form, "&text=", uri_escape(mc_sent));
		mc_req = Lob_NextReq();
		mc_wire = mc_req;
		mc_phase = 2;
		mc_at = time;
		if (!uri_get(strcat(MF_SITE, "/api/social/menu"), mc_req, "application/x-www-form-urlencoded", form))
		{
			mc_wire = 0;
			MC_Fail("Chat request failed. Check chat before sending again.");
		}
	}
	else if (!strcmp(mc_op, "message"))
	{
		if (!strcmp(mc_draft, mc_sent)) { MC_Keep(mc_draft, ""); mc_cursor = 0; }
		MC_Keep(mc_sent, "");
		MC_Keep(mc_note, "Message sent.");
		mc_scroll_y = 999999;
		mc_phase = mc_next = 0;
	}
	else
	{
		if (!MC_Snapshot(root)) MC_Fail("Invalid chat snapshot.");
		else { MC_Keep(mc_note, "Recent messages expire after two minutes; not saved."); mc_next = time + 8; }
		mc_phase = 0;
	}
	json_free(root);
	return TRUE;
};

void(vector pos, vector size, float embedded) MC_Panel =
{
	local vector rp;
	local float left, right, i, width, board, compact, message_y, field_y, field_h;
	local string who, name, text, id;
	if (!embedded) ui_backdrop(size);
	sui_style_panel(pos, size, 12, 1);
	sui_push_frame(pos, size);
	sui_text('16 18 0', SZ_HEAD, "lobby chat", COL_ACCENT, 1, 0);
	if (embedded)
	{
		if (ui_button("mc_public", [size_x - 116, 12], '100 30 0', "Public lobby"))
			if (!mc_wire) MC_Select("-", "Public lobby");
	}
	else if (ui_button("mc_back", [size_x - 98, 12], '82 30 0', "back"))
	{
		menu_screen = SCREEN_MAIN;
		sui_text_unfocus();
	}
	if (!MF_Online())
	{
		text = "Accept online terms to use chat.";
		ui_para('16 76 0', size_x - 32, SZ_LABEL, 20, text, COL_DIM, TRUE);
		sui_pop_frame();
		return;
	}
	left = min(240, floor(size_x * 0.26));
	right = left + 20;
	if (embedded) right = 16;
	width = size_x - right - 16;
	if (!embedded)
	{
	if (ui_button("mc_room", '12 60 0', [left, 34], "Public lobby"))
		if (!mc_wire) MC_Select("-", "Public lobby");
	sui_text('16 104 0', SZ_LABEL, "Friends / direct messages", COL_DIM, 1, 0);
	if (mc_friends >= 0)
	{
		sui_list_view_begin("mc_friends", '12 130 0', [left, max(36, size_y - 198)], [left - 14, 36], buf_getsize(mc_friends), mc_friend_scroll, [0, 6]);
		rp = '0 0 0';
		for (i = sui_list_item(rp); i > -1; i = sui_list_item(rp))
		{
			if (tokenize(bufstr_get(mc_friends, i)) != 2) continue;
			who = argv(0); name = uri_unescape(argv(1));
			id = strcat("mc_dm_", who);
			if (ui_button(id, rp, [left - 14, 32], ui_fit_text(MC_Plain(name), left - 36, SZ_LABEL)))
				if (!mc_wire) MC_Select(who, name);
		}
		sui_list_view_end();
	}
	}
	compact = (embedded && size_y < 300);
	message_y = compact ? 72 : 96;
	field_y = size_y - (compact ? 84 : 110);
	field_h = compact ? 30 : 34;
	sui_text([right, compact ? 48 : 62], compact ? SZ_LABEL : SZ_HEAD,
		ui_fit_text(MC_Plain(mc_peer_name), width, compact ? SZ_LABEL : SZ_HEAD), COL_TEXT, 1, 0);
	mc_height = max(24, field_y - message_y - 12);
	if (mc_view >= 0 && mc_seen > 0 && time >= mc_seen && time - mc_seen <= 24)
	{
		sui_list_view_begin("mc_messages", [right, message_y], [width, mc_height], [width - 14, MC_MSG_H], mc_count, mc_scroll, [0, 6]);
		rp = '0 0 0';
		for (i = sui_list_item(rp); i > -1; i = sui_list_item(rp))
		{
			if (tokenize(bufstr_get(mc_view, i)) != 4) continue;
			who = argv(1); name = uri_unescape(argv(2)); text = uri_unescape(argv(3));
			board = (argv(0) == "-");               // the public room, not a message
			if (!strcmp(who, mc_me)) name = "You";
			// P996: "* ..." in the room is a board line surfd said for the player (social.announce).
			if (board)
			if (substring(text, 0, 2) == "* ")
			{
				sui_text(rp, SZ_LABEL, "board", COL_DIM, 1, 0);
				ui_para(rp + '0 22 0', width - 20, SZ_LABEL, 18,
				        MC_Plain(strcat(name, " ", substring(text, 2, -1))), SUI_THEME_GOOD, TRUE);
				continue;
			}
			sui_text(rp, SZ_LABEL, ui_fit_text(MC_Plain(name), width - 20, SZ_LABEL), COL_ACCENT, 1, 0);
			ui_para(rp + '0 22 0', width - 20, SZ_LABEL, 18, MC_Plain(text), COL_TEXT, TRUE);
		}
		sui_list_view_end();
		if (!mc_count) sui_text([right, message_y + 8], SZ_LABEL, "No recent messages.", COL_DIM, 1, 0);
	}
	else ui_para([right, message_y + 8], width, SZ_LABEL, 18, "Waiting for a fresh chat snapshot...", COL_DIM, TRUE);
	ui_field("mc_text", [right, field_y], [width - 88, field_h], mc_draft, mc_cursor, "Write a message...");
	if (ui_button("mc_send", [size_x - 96, field_y], [80, field_h], mc_wire ? "wait..." : "send")) MC_Send();
	sui_text([right, size_y - (compact ? 40 : 66)], '12 12 0', ui_fit_text(MC_Plain(mc_note), width, '12 12 0'), COL_DIM, 1, 0);
	sui_text([16, size_y - (compact ? 20 : 32)], '12 12 0', ui_fit_text("Lobby / DMs: not end-to-end encrypted.", size_x - 32, '12 12 0'), COL_DIM, 1, 0);
	sui_pop_frame();
};
