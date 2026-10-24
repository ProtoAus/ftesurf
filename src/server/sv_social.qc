/* Steam friends: capability stays on the lobby, never in userinfo/client logs.
   Full-node presence snapshot every five seconds; reliable private stuffcmds.
   Compile before sv_account: it calls Set/Clear only after a proven reply. */
.string social_token, social_hash, social_ack, social_retire;
.float social_here, social_req, social_reqtime, social_last;
.float social_buf, social_buffered, social_sendrow, social_sendtime;
.float social_refresh, social_retry, social_delay;
float social_poll, social_polltime, social_next;
float() Account_On;
float() Account_NextId;
void(entity e) Account_Hello;
float(entity e) Account_Busy;

void(entity e) Social_Clear =
{
	if (e.social_token != "") strunzone(e.social_token);
	if (e.social_hash != "") strunzone(e.social_hash);
	if (e.social_ack != "") strunzone(e.social_ack);
	if (e.social_retire != "") strunzone(e.social_retire);
	e.social_retire = "";
	e.social_refresh = FALSE;
	e.social_retry = e.social_delay = 0;
	if (e.social_buffered) buf_del(e.social_buf);
	e.social_buffered = FALSE;
	e.social_token = "";
	e.social_hash = "";
	e.social_here = FALSE;
	e.social_req = 0;
	e.social_last = 0;
	e.social_ack = "";
	forceinfokey(e, "*ahash", "");
};

void(entity e, string token, string who) Social_Set =
{
	Social_Clear(e);
	if (!SV_RecIsHex(token, 64) || !SV_RecIsHex(who, FS_WHO_IDLEN)) return;
	e.social_token = strzone(token);
	e.social_here = TRUE;
	forceinfokey(e, "*ahash", who);
	stuffcmd(e, "friend_clear\n");
	social_next = 0;
};

string() Social_Form =
{
	return sprintf("key=%s&node=%s", uri_escape(cvar_string("lobby_master_key")),
	               uri_escape(sprintf("p%g", cvar("sv_port"))));
};

void() Social_Drain =
{
	local entity e;
	local float i, n;
	e = findfloat(world, social_here, TRUE);
	while (e)
	{
		if (e.social_buffered && time >= e.social_sendtime)
		{
			e.social_sendtime = time + 0.1;
			n = buf_getsize(e.social_buf);
			for (i = 0; i < 4 && e.social_sendrow < n; i = i + 1)
			{
				stuffcmd(e, bufstr_get(e.social_buf, e.social_sendrow));
				e.social_sendrow = e.social_sendrow + 1;
			}
			if (e.social_sendrow >= n)
			{
				buf_del(e.social_buf);
				e.social_buffered = FALSE;
			}
		}
		e = findfloat(e, social_here, TRUE);
	}
};

string(entity e) Social_Activity =
{
	if (e.run_sp_phase == 2) return "Spectating";
	if (e.run_t_segs <= 0) return "";
	if (e.run_t_track > 0)
		return sprintf("Bonus %g", bound(1, e.run_t_track, 999));
	return sprintf("Stage %g", bound(1, e.run_t_seg + 1, 999));
};

string(string token, string hash, string ack, string activity) Social_RosterRow =
{
	// uri_escape has an 8192-byte output limit. Encode each bounded row,
	// never the complete 64-player snapshot (which exceeds that limit).
	return uri_escape(sprintf("{\"token\":\"%s\",\"hash\":\"%s\",\"ack\":%s,\"activity\":\"%s\"}",
	                         token, hash, ack != "" ? ack : "0", activity));
};

void() Social_Frame =
{
	local entity e;
	local string roster, r;
	local float n;

	if (!Account_On()) return;
	Social_Drain();
	if (social_poll && time - social_polltime < 15) return;
	if (time < social_next) return;
	social_next = time + 5;
	roster = "%5B";
	n = 0;
	e = findfloat(world, social_here, TRUE);
	while (e)
	{
		if (n < 64)
		{
			r = Social_RosterRow(e.social_token, e.social_hash, e.social_ack, Social_Activity(e));
			roster = strcat(roster, n ? "%2C" : "", r);
			n = n + 1;
		}
		e = findfloat(e, social_here, TRUE);
	}
	// Even an empty roster retires the last disconnect's presence.
	roster = strcat(roster, "%5D");
	social_poll = Account_NextId();
	social_polltime = time;
	if (!uri_post(strcat(cvar_string("lobby_master"), "/api/social/poll"), social_poll,
	              "application/x-www-form-urlencoded", strcat(Social_Form(), "&roster=", roster)))
		social_poll = 0;
};

void(entity e, string op, string who, string text) Social_Action =
{
	local string form;

	if (!e.social_here)
	{
		stuffcmd(e, sprintf("friend_note %s\n", uri_escape("Link Steam on this lobby first")));
		return;
	}
	if (e.social_req && time - e.social_reqtime < 15)
	{
		stuffcmd(e, sprintf("friend_note %s\n", uri_escape("Previous action is pending; wait and try again")));
		return;
	}
	if (time < e.social_last)
	{
		stuffcmd(e, sprintf("friend_note %s\n", uri_escape("Wait a second, then resend")));
		return;
	}
	e.social_last = time + 1;
	if (!strcmp(op, "refresh"))
	{
		social_next = 0;
		return;
	}
	if (!SV_RecIsHex(who, FS_WHO_IDLEN) && !SV_RecIsHex(who, 12)) return;
	if (op != "add" && op != "accept" && op != "remove" && op != "message" && op != "join"
	    && op != "block" && op != "unblock") return;
	if (strlen(text) > 960) return; // percent-encoded UTF8, still bounded upstream
	form = strcat(Social_Form(), "&game=1&token=", e.social_token, "&op=", op, "&who=", who);
	if (op == "message") form = strcat(form, "&text=", uri_escape(uri_unescape(text)));
	e.social_req = Account_NextId();
	e.social_reqtime = time;
	if (!uri_post(strcat(cvar_string("lobby_master"), "/api/social/action"), e.social_req,
	              "application/x-www-form-urlencoded", form))
	{
		e.social_req = 0;
		stuffcmd(e, sprintf("friend_note %s\n", uri_escape("Friends unavailable; try again")));
	}
};

float(float reqid, float code, string body) Social_Reply =
{
	local int root, rows, row, friends, f, messages, m;
	local float i, j, n, ok;
	local entity e;
	local string token, hash, note, addr;

	if (reqid != social_poll)
	{
		e = findfloat(world, social_req, reqid);
		if (!e) return FALSE;
		e.social_req = 0;
		root = json_parse(body);
		ok = json_get_float(json_find_object_child(root, "ok"));
		note = json_get_string(json_find_object_child(root, ok ? "note" : "error"));
		if (note == "") note = "Friends unavailable; try again";
		stuffcmd(e, sprintf("friend_note %s\n", uri_escape(note)));
		addr = json_get_string(json_find_object_child(root, "addr"));
		if (!code && ok && addr != "")
			stuffcmd(e, sprintf("friend_join %s\n", uri_escape(addr)));
		if (root) json_free(root);
		social_next = 0;
		return TRUE;
	}
	social_poll = 0;
	root = json_parse(body);
	if (code || !json_get_float(json_find_object_child(root, "ok")))
	{
		if (root) json_free(root);
		return TRUE;
	}
	rows = json_find_object_child(root, "players");
	n = min(64, json_get_length(rows));
	for (i = 0; i < n; i = i + 1)
	{
		row = json_get_child_at_index(rows, i);
		token = json_get_string(json_find_object_child(row, "token"));
		e = find(world, social_token, token);
		if (!e) continue; // disconnect/slot recycle/changed proof
		if (json_get_float(json_find_object_child(row, "invalid")))
		{
			Social_Clear(e);
			e.social_retire = strzone(token);
			stuffcmd(e, "friend_clear\n");
			e.social_refresh = TRUE;
			e.social_retry = time;
			stuffcmd(e, sprintf("friend_note %s\n", uri_escape("Refreshing Steam for Friends; retrying automatically")));
			continue;
		}
		hash = json_get_string(json_find_object_child(row, "hash"));
		friends = json_find_object_child(row, "friends");
		if (friends)
		{
			if (e.social_buffered) buf_del(e.social_buf);
			e.social_buf = buf_create();
			e.social_buffered = TRUE;
			e.social_sendrow = 0;
			bufstr_add(e.social_buf, "friend_begin 1\n", TRUE);
			for (j = 0; j < min(128, json_get_length(friends)); j = j + 1)
			{
				f = json_get_child_at_index(friends, j);
				// All variable text is percent encoded; never an executable argument.
				bufstr_add(e.social_buf, strcat(sprintf("friend_row %s %g %g \"%s\" \"%s\" \"%s\" \"%s\"",
				         json_get_string(json_find_object_child(f, "who")),
				         json_get_float(json_find_object_child(f, "relation")),
				         json_get_float(json_find_object_child(f, "online")),
				         uri_escape(json_get_string(json_find_object_child(f, "name"))),
				         uri_escape(substring(json_get_string(json_find_object_child(f, "server")), 0, 80)),
				         uri_escape(substring(json_get_string(json_find_object_child(f, "map")), 0, 64)),
				         uri_escape(substring(json_get_string(json_find_object_child(f, "activity")), 0, 24))),
				         sprintf(" %g\n", json_get_float(json_find_object_child(f, "menu_online")) == 1)), TRUE);
			}
			bufstr_add(e.social_buf, sprintf("friend_end %s\n", hash), TRUE);
		}
		else if (!e.social_buffered && strlen(hash) == 64)
		{
			// Successful unchanged poll: renew only this completed snapshot.
			if (!strcmp(hash, e.social_hash)) stuffcmd(e, sprintf("friend_end %s\n", hash));
		}
		if (e.social_hash != "") strunzone(e.social_hash);
		e.social_hash = strzone(hash);
		messages = json_find_object_child(row, "messages");
		for (j = 0; j < min(2, json_get_length(messages)); j = j + 1)
		{
			m = json_get_child_at_index(messages, j);
			note = json_get_string(json_find_object_child(m, "id"));
			if (!strcmp(note, e.social_ack)) continue;
			stuffcmd(e, sprintf("friend_pm %s %s %s\n",
			         json_get_string(json_find_object_child(m, "who")),
			         uri_escape(json_get_string(json_find_object_child(m, "name"))),
			         uri_escape(json_get_string(json_find_object_child(m, "text")))));
			if (e.social_ack != "") strunzone(e.social_ack);
			e.social_ack = strzone(note);
		}
	}
	json_free(root);
	return TRUE;
};
