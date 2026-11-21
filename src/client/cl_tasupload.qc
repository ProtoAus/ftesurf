/*
  P1696: upload a TAS run from the game to play.proto.bar/tasup (surfd/tasupd.py's game route), the TAS menu's Upload
  tab. Upload asks the service for a code bound to the file's SHA-256; Send, on a real press only, signs
  TASUp_Signed (the code, the purpose and the file) with the linked key -- acct_sign kind -6, as zone publishing signs --
  and posts the proof and the file in one body. The service checks the run as it checks the web form's.
*/
#ifndef TUP_BASE   // a test build only (fteqcc -DTUP_BASE): a server must never choose where a proof goes
#define TUP_BASE "https://play.proto.bar/tasup/"
#endif
#define TUP_MAX 10
#define TUP_BYTES 8388608                           // tasupd.MAX_REC
string tup_p[TUP_MAX], tup_l[TUP_MAX];
float tup_n, tup_at;
string tup_key;                 // the map and its courses the list was made for
float tup_state;                // 0 the list, 1 asking for a code, 2 confirm, 3 sending, 4 answered
float tup_req, tup_until, tup_armed, tup_size;
string tup_path, tup_label, tup_nonce, tup_sha, tup_note;

string(string old, string value) TASUp_Keep =
{
	local string copy;
	copy = strzone(value);
	if (old != "") strunzone(old);
	return copy;
};
// a server's words as one line of plain text
string(string s) TASUp_Clean =
{
	s = strreplace("^", "", strreplace("\n", " ", strreplace("\r", " ", strreplace("\t", " ", s))));
	return (strlen(s) > 240) ? strcat(substring(s, 0, 237), "...") : s;
};
float(string s, float n) TASUp_Hex =
{
	local float i, c;
	if (strlen(s) != n) return FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (!((c >= 48 && c <= 57) || (c >= 97 && c <= 102))) return FALSE;
	}
	return TRUE;
};
// tasupd.game_nonce: what the key signs for this file under the service's code
string(string nonce, string sha) TASUp_Signed =
{
	return substring(strtolower(digest_hex("SHA256", strcat("ftesurf-tasup ", nonce, " ", sha))), 0, 32);
};
string(float track) TASUp_Course = { return (track > 0) ? sprintf("Bonus %g", track) : "Main"; };

void(string p, string l) TASUp_Add =
{
	local float i;
	if (tup_n >= TUP_MAX || !TASJargon_Safe(p)) return;
	for (i = 0; i < tup_n; i = i + 1) if (!strcmp(tup_p[i], p)) return;
	tup_p[tup_n] = strzone(p); tup_l[tup_n] = strzone(l); tup_n = tup_n + 1;
};
// Your finished TAS runs of the map's whole courses (data/runs/<map>/<main|bonus_N>/<ticks>_..._tas.rec, fastest first),
// then a bot's .rec loose in data/ that names this map. Stage legs are not offered: the board takes whole courses.
void(float track) TASUp_Own =
{
	local float h, n, c, k, hd, t;
	local string f, b, dir;
	dir = FS_MovementProfilePath(serverkey("*movementprofile"), FS_RunDir(serverkey("map"), track, 0));
	if (dir == "") return;
	h = search_begin(strcat(dir, "*.rec"), 33, TRUE);
	if (h < 0) return;
	n = search_getsize(h); k = 0;
	for (c = 0; c < n && k < 3 && tup_n < TUP_MAX; c = c + 1)
	{
		f = search_getfilename(h, c);
		b = TASJargon_Base(f);
		if (FS_TagFromName(FS_NameTag(b)) != RT_TAS) continue;
		hd = TASJargon_Head(f);
		if (hd < 0 || !jg_hcok[hd]) continue;
		t = rint(stof(substring(b, 0, strstrofs(b, "_"))) * jg_hctr[hd] * 100) / 100;
		TASUp_Add(f, sprintf("%s  %s  TAS run", TASUp_Course(track), (t >= 60)
			? sprintf("%g:%s%.2f", floor(t / 60), (t - 60 * floor(t / 60) < 10) ? "0" : "", t - 60 * floor(t / 60)) : sprintf("%.2fs", t)));
		k = k + 1;
	}
	search_end(h);
};
void() TASUp_List =
{
	local float i, h, n, hd;
	local string key, f;
	TASJargon_Courses();
	key = sprintf("%s %g", zone_mapname, jg_cn);
	if (key == tup_key && cltime < tup_at) return;
	tup_at = cltime + 3;
	tup_key = TASUp_Keep(tup_key, key);
	for (i = 0; i < tup_n; i = i + 1) { strunzone(tup_p[i]); strunzone(tup_l[i]); }
	tup_n = 0;
	if (!jg_cn) TASUp_Own(0);
	for (i = 0; i < jg_cn; i = i + 1) if (!jg_cl[i]) TASUp_Own(jg_ct[i]);
	h = search_begin("data/*.rec", 33, TRUE);
	if (h < 0) return;
	n = search_getsize(h);
	for (i = 0; i < n && tup_n < TUP_MAX; i = i + 1)
	{
		f = search_getfilename(h, i);
		hd = TASJargon_Head(f);
		if (hd < 0 || !jg_hcok[hd] || jg_hcl[hd] > 0) continue;
		TASUp_Add(f, sprintf("%s  file %s", TASUp_Course(max(0, jg_hct[hd])), TASJargon_Base(f)));
	}
	search_end(h);
};

void(string note) TASUp_Answer =
{
	tup_state = 4; tup_req = 0;
	tup_note = TASUp_Keep(tup_note, strcat(strtoupper(substring(note, 0, 1)), substring(note, 1, -1)));
	print(sprintf("tas upload: %s\n", note));
};
// the file as it is now, or "" (missing, too big, or a NUL in it)
string(string p) TASUp_Read =
{
	local float fh;
	local string s;
	fh = fopen(p, FILE_READNL);
	if (fh < 0) return "";
	s = fgets(fh);
	fclose(fh);
	tup_size = strlen(s);
	return (tup_size > TUP_BYTES) ? "" : s;
};

// Upload's click: the service's code for this file (a draw-time click is enough; only Send signs)
void(float i) TASUp_Ask =
{
	local string body;
	if (i < 0 || i >= tup_n || tup_state == 1 || tup_state == 3) return;
	if (!TASShare_Allowed()) { TASUp_Answer("accept the online terms in the main menu first"); return; }
	if (Rec_ServerIsRemote()) { TASUp_Answer("upload from a local game, not while on a server"); return; }   // review: a server's plant
	body = TASUp_Read(tup_p[i]);
	if (body == "") { TASUp_Answer((tup_size > TUP_BYTES) ? "that file is over 8 MB" : "that file could not be read"); return; }
	tup_path = TASUp_Keep(tup_path, tup_p[i]);
	tup_label = TASUp_Keep(tup_label, tup_l[i]);
	tup_sha = TASUp_Keep(tup_sha, strtolower(digest_hex("SHA256", body)));
	tup_req = Online_NextReq();
	if (!uri_post(strcat(TUP_BASE, "api/game/challenge"), tup_req, "application/json", sprintf("{\"sha\":\"%s\"}", tup_sha)))
	{
		TASUp_Answer("the upload service could not be reached; nothing was sent"); return;
	}
	tup_state = 1; tup_until = gettime(0) + 20;
	print(sprintf("tas upload: asked for a code for %s (%g bytes)\n", tup_path, tup_size));
};

// Send: called from TASUI_Input on a device's press over the button, the one moment the engine signs
void() TASUp_Send =
{
	local string body, p, env;
	if (tup_state != 2 || !cl_input_real) return;
	if (gettime(0) < tup_armed) return;     // no press carried in from the Upload click
	if (Rec_ServerIsRemote()) { TASUp_Answer("upload from a local game, not while on a server; nothing was sent"); return; }
	body = TASUp_Read(tup_path);
	if (body == "" || strcmp(strtolower(digest_hex("SHA256", body)), tup_sha))
	{
		TASUp_Answer("the file changed after Upload: press Upload again; nothing was sent"); return;
	}
	p = acct_sign(TASUp_Signed(tup_nonce, tup_sha), -6);
	if (p == "" || tokenize(p) != 5)
	{
		TASUp_Answer("the game would not sign the upload: it needs a linked Steam account (Settings), the latest engine and a "
			"real click; nothing was sent");
		return;
	}
	// tasupd.GAME_HEAD: the proof is checked before the file is read; then the bytes the code was asked for, raw
	env = strcat("FTESURF-TASUP 1\nnonce ", tup_nonce, "\nsha ", tup_sha, "\npub ", argv(0), "\nsig ", argv(2));
	env = strcat(env, "\ngame ", argv(4), "\n", body);
	tup_req = Online_NextReq();
	if (!uri_post(strcat(TUP_BASE, "upload"), tup_req, "application/x-ftesurf-tasup", env))
	{
		TASUp_Answer("the upload service could not be reached; nothing was sent"); return;
	}
	tup_state = 3; tup_until = gettime(0) + 180;
	print(sprintf("tas upload: sent %s (%g bytes), signed under a real press\n", tup_path, tup_size));
};
void() TASUp_Press =
{
	if (tup_state == 2 && sui_is_hovered("tup_send")) TASUp_Send();
};

float(float reqid, float code, string body) TASUp_Reply =
{
	local int root, rs, it;
	local float ok, i, n, t;
	local string s, why;
	if (!tup_req || reqid != tup_req) return FALSE;
	tup_req = 0;
	if (code) { TASUp_Answer(sprintf("play.proto.bar could not be reached (%g); try again in a minute", code)); return TRUE; }
	root = json_parse(body);
	if (root <= 0i) { TASUp_Answer("play.proto.bar answered something unreadable; try again in a minute"); return TRUE; }
	ok = json_get_float(json_find_object_child(root, "ok"));
	why = TASUp_Clean(json_get_string(json_find_object_child(root, "error")));
	if (tup_state == 1)
	{
		s = json_get_string(json_find_object_child(root, "nonce"));
		if (ok == 1 && TASUp_Hex(s, 32) && !strcmp(json_get_string(json_find_object_child(root, "sha")), tup_sha))
		{
			tup_nonce = TASUp_Keep(tup_nonce, s);
			tup_state = 2; tup_armed = gettime(0) + 0.5;
			print(sprintf("tas upload: ready to send %s: click Send\n", tup_path));
		}
		else TASUp_Answer(strcat("not uploaded: ", (why != "") ? why : "the service did not give a code"));
	}
	else if (tup_state == 3)
	{
		rs = json_find_object_child(root, "reasons");
		s = "";
		n = (json_get_value_type(rs) == 3i) ? min(3, json_get_length(rs)) : 0;
		for (i = 0; i < n; i = i + 1)
		{
			it = json_get_child_at_index(rs, (int)i);
			t = json_get_float(json_find_object_child(it, "t"));
			s = strcat(s, (s != "") ? "; " : "", (json_get_value_type(json_find_object_child(it, "t")) == 1i) ? sprintf("at %.3fs ", t) : "",
				TASUp_Clean(json_get_string(json_find_object_child(it, "what"))));
		}
		if (ok == 1)
		{
			t = json_get_float(json_find_object_child(root, "id"));
			if (json_get_string(json_find_object_child(root, "state")) == "shown")
				TASUp_Answer(sprintf("on the TAS board, physics checked: run %g, %.3fs. play.proto.bar/tasup/run/%g", t,
					json_get_float(json_find_object_child(root, "time")), t));
			else
				TASUp_Answer(sprintf("uploaded, waiting for review: run %g (%s). play.proto.bar/tasup/run/%g", t, s, t));
		}
		else TASUp_Answer(strcat("not uploaded: ", (why != "") ? why : "the service refused it", (s != "") ? strcat(" -- ", s) : ""));
	}
	json_free(root);
	return TRUE;
};

void() TASUp_Pump =
{
	if ((tup_state == 1 || tup_state == 3) && gettime(0) > tup_until)
		TASUp_Answer((tup_state == 1) ? "play.proto.bar did not answer; try again in a minute"
			: "no answer yet: the run may still have arrived -- look at play.proto.bar/tasup before sending it again");
	if (tup_state == 2 && gettime(0) > tup_armed + 590) TASUp_Answer("the confirmation expired: press Upload again");   // tasupd.CHALLENGE_TTL
};

void(vector at, float width, float tsz, float hint, float row) TASUp_Draw =
{
	local float i;
	local vector chip, half;
	TASUp_Pump();
	at_y = ZonePub_Wrap(at, width, hint, "Send a finished TAS run of this map to the TAS board at play.proto.bar/tasup, as your "
		"Steam account. It is checked against the game's movement physics: runs that check out are listed there with their "
		"file; a new record, or anything the check cannot clear, waits for review.", SUI_THEME_DIM, TRUE) + hint;
	half = [(width - 6) / 2, row, 0];
	if (tup_state == 0)
	{
		TASUp_List();
		if (!tup_n)
		{
			ZonePub_Wrap(at, width, tsz, "No TAS run of this map yet. Finish one with Jargon or Manual TAS (or put a bot's .rec "
				"in data/) and it shows here.", SUI_THEME_TEXT, TRUE);
			return;
		}
		chip = [tsz * 7, row, 0];
		for (i = 0; i < tup_n; i = i + 1)
		{
			sui_text(at + [0, (row - tsz) * 0.5, 0], [tsz, tsz], tup_l[i], SUI_THEME_TEXT, 1, 0);
			if (Profile_Chip(sprintf("tup_go%g", i), at + [width - chip_x, 0, 0], chip, "Upload", tsz, FALSE)) TASUp_Ask(i);
			at_y = at_y + row + 4;
		}
		return;
	}
	sui_text(at, [tsz, tsz], tup_label, SUI_THEME_TEXT, 1, 0); at_y = at_y + row;
	if (tup_state == 1) sui_text(at, [hint, hint], "Asking play.proto.bar for a confirmation...", SUI_THEME_DIM, 1, 0);
	else if (tup_state == 2)
	{
		at_y = ZonePub_Wrap(at, width, hint, sprintf("Send this run (%g KB) to the TAS board as your Steam account? The game signs "
			"it with your linked account when you click Send.", ceil(tup_size / 1024)), SUI_THEME_TEXT, TRUE) + hint;
		Profile_Chip("tup_send", at, half, "Send", tsz, gettime(0) >= tup_armed);   // the press acts (TASUp_Press), not this
		if (Profile_Chip("tup_back", at + [half_x + 6, 0, 0], half, "Back", tsz, FALSE)) { tup_state = 0; tup_req = 0; }
	}
	else if (tup_state == 3) sui_text(at, [hint, hint], "Sending and checking... a long run takes a few seconds.", SUI_THEME_DIM, 1, 0);
	else
	{
		at_y = ZonePub_Wrap(at, width, hint, tup_note, SUI_THEME_TEXT, TRUE) + hint;
		if (Profile_Chip("tup_list", at, half, "Back to the list", tsz, FALSE)) { tup_state = 0; tup_at = 0; }
	}
};

// `tas upload` lists, `tas upload N` asks for row N's code and opens the tab (Send is a click), `tas upload status`
void(float argc) TASUp_Verb =
{
	local float i;
	if (argc >= 3 && argv(2) == "status") { print(sprintf("tas upload: state %g %s\n", tup_state, tup_note)); return; }
	i = (argc >= 3) ? stof(argv(2)) - 1 : -1;     // before the list: reading headers tokenizes
	if (argc >= 3)
	if (checkbuiltin(cmdlevel_local))      // nested: QC evaluates both sides of &&
	if (!cmdlevel_local())
	{
		print("tas upload: only from your own console or binds\n");   // review: a server's command opened the tab
		return;
	}
	tup_at = 0; TASUp_List();
	if (argc >= 3)
	{
		if (i != floor(i) || i < 0 || i >= tup_n) { print(sprintf("tas upload: 1..%g\n", tup_n)); return; }
		if (!tasu_open) TASUI_Toggle(0);
		TASUI_SelectTab(TAS_TAB_UPLOAD);
		tup_state = 0; TASUp_Ask(i);
		return;
	}
	print(sprintf("tas upload: %g run(s) of %s\n", tup_n, zone_mapname));
	for (i = 0; i < tup_n; i = i + 1) print(sprintf("tas upload: %g %s (%s)\n", i + 1, tup_l[i], tup_p[i]));
};
