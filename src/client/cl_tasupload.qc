/*
  P1696: upload a TAS run from the game to play.proto.bar/tasup (surfd/tasupd.py's game route), the TAS menu's Upload
  tab. Upload asks the service for a code bound to the file's SHA-256; Send, on a real press only, signs
  TASUp_Signed (the code, the purpose and the file) with the linked key -- acct_sign kind -6, as zone publishing signs --
  and posts the proof and the file in one body. The service checks the run as it checks the web form's.
  The list is the local game's own word (SV_TASUpList: runs it finished, by their SHA-256, kept in data/tasproj/ where
  client code cannot write), so a file a server's csprogs put in data/runs/ is never offered as yours (attack review 2).
  A bot's .rec goes through the web form.
*/
#ifndef TUP_BASE   // a test build only (fteqcc -DTUP_BASE): a server must never choose where a proof goes
#define TUP_BASE "https://play.proto.bar/tasup/"
#endif
#define TUP_MAX 10
#define TUP_BYTES 8388608                           // tasupd.MAX_REC
string tup_p[TUP_MAX], tup_l[TUP_MAX], tup_s[TUP_MAX];   // path, label, the SHA-256 the game saved it with
string tupe_p[TUP_MAX], tupe_s[TUP_MAX];                  // the list arriving (TASUp_ListEvent)
float tup_n, tup_at, tupe_n;
string tup_key;                 // the map the list was asked for
float tup_state;                // 0 the list, 1 asking for a code, 2 confirm, 3 sending, 4 answered
float tup_req, tup_until, tup_armed, tup_size;
float tup_pend, tup_pendt;       // `tas upload N` waiting for the list (row N-1, or -2: `tas upload`, to print it) until tup_pendt
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

// a run the local game says it finished (path, sha): offered if it is still there, of this map, a whole course
void(string p, string sha) TASUp_Add =
{
	local float i, hd, t;
	local string b;
	if (tup_n >= TUP_MAX || !TASJargon_Safe(p) || !TASUp_Hex(sha, 64)) return;
	if (substring(p, 0, 10) != "data/runs/" || FS_TagFromName(FS_NameTag(TASJargon_Base(p))) != RT_TAS)   // Base drops .rec
		return;
	for (i = 0; i < tup_n; i = i + 1) if (!strcmp(tup_p[i], p)) return;
	hd = TASJargon_Head(p);
	if (hd < 0) return;            // nested: QC's || reads jg_hcok[-1] too (flow review 2)
	if (!jg_hcok[hd] || jg_hcl[hd] > 0) return;
	b = TASJargon_Base(p);
	t = rint(stof(substring(b, 0, strstrofs(b, "_"))) * jg_hctr[hd] * 100) / 100;
	tup_p[tup_n] = strzone(p); tup_s[tup_n] = strzone(sha);
	tup_l[tup_n] = strzone(sprintf("%s  %s  TAS run", TASUp_Course(max(0, jg_hct[hd])), (t >= 60)
		? sprintf("%g:%s%.2f", floor(t / 60), (t - 60 * floor(t / 60) < 10) ? "0" : "", t - 60 * floor(t / 60)) : sprintf("%.2fs", t)));
	tup_n = tup_n + 1;
};
void() TASUp_Pending;
// SV_TASUpList's events: index, count, then the run's sha and path; the list is replaced once the last arrives
void() TASUp_ListEvent =
{
	local float i, n, k;
	local string sha, path;
	i = readbyte(); n = readbyte();
	sha = path = "";
	if (n) { sha = readstring(); path = readstring(); }
	if (!isserver()) return;        // only the game this process hosts says what it finished
	if (i == 0) { for (k = 0; k < tupe_n; k = k + 1) { strunzone(tupe_p[k]); strunzone(tupe_s[k]); } tupe_n = 0; }
	if (n && i == tupe_n && tupe_n < TUP_MAX) { tupe_p[tupe_n] = strzone(path); tupe_s[tupe_n] = strzone(sha); tupe_n = tupe_n + 1; }
	if (i < n - 1) return;
	for (k = 0; k < tup_n; k = k + 1) { strunzone(tup_p[k]); strunzone(tup_l[k]); strunzone(tup_s[k]); }
	tup_n = 0;
	for (k = 0; k < tupe_n; k = k + 1) TASUp_Add(tupe_p[k], tupe_s[k]);
	if (tup_pendt) TASUp_Pending();         // the console verb, answered by this list (flow review 3: it read the last one)
};
// asks the local game for its list: when the map changes, and every 3 s while the tab is drawn
void() TASUp_List =
{
	local string key;
	if (!isserver()) return;
	key = zone_mapname;
	if (key == tup_key && cltime < tup_at) return;
	tup_at = cltime + 3;
	if (key != tup_key) { tup_key = TASUp_Keep(tup_key, key); }
	localcmd("cmd tas uploads\n");
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
	tup_size = 0;
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
	tup_label = TASUp_Keep(tup_label, tup_l[i]);   // first: a refusal below shows this run's name (flow review 2)
	if (!TASShare_Allowed()) { TASUp_Answer("accept the online terms in the main menu first"); return; }
	if (!isserver()) { TASUp_Answer("upload from a game you host, not while on a server"); return; }
	if (!Zone_LooseOwn(tup_p[i])) { TASUp_Answer("that file is not your game's own copy (a package has it); nothing was sent"); return; }
	body = TASUp_Read(tup_p[i]);
	if (body == "") { TASUp_Answer((tup_size > TUP_BYTES) ? "that file is over 8 MB" : "that file could not be read"); return; }
	tup_sha = TASUp_Keep(tup_sha, strtolower(digest_hex("SHA256", body)));
	if (strcmp(tup_sha, tup_s[i])) { TASUp_Answer("that file is not the run your game saved (it changed since); nothing was sent"); return; }
	tup_path = TASUp_Keep(tup_path, tup_p[i]);
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
	if (!isserver()) { TASUp_Answer("upload from a game you host, not while on a server; nothing was sent"); return; }
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
	if (code == 504 && tup_state == 3)    // nginx gave up waiting (150 s): the check may have finished and kept it
		{ TASUp_Answer("no answer in time: the run may still have arrived -- look at play.proto.bar/tasup before sending it again"); return TRUE; }
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
		if (!isserver())
		{
			ZonePub_Wrap(at, width, tsz, "Upload from a game you host: TAS runs are made there.", SUI_THEME_TEXT, TRUE);
			return;
		}
		TASUp_List();
		if (!tup_n)
		{
			ZonePub_Wrap(at, width, tsz, "No TAS run of this map yet. Finish one with Jargon or Manual TAS and it shows here. "
				"Runs from before this update, and a bot's .rec, go through play.proto.bar/tasup.", SUI_THEME_TEXT, TRUE);
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

// `tas upload` lists, `tas upload N` asks for row N's code and opens the tab (Send is a click), `tas upload status`.
// The list comes from the local game (TASUp_ListEvent): the verb acts when it arrives.
void() TASUp_Pending =
{
	local float i;
	i = tup_pend;
	if (cltime > tup_pendt) { tup_pendt = 0; return; }   // asked too long ago: not a click's answer now (flow review 4)
	tup_pendt = 0;
	if (i == -2)
	{
		print(sprintf("tas upload: %g run(s) of %s\n", tup_n, zone_mapname));
		for (i = 0; i < tup_n; i = i + 1) print(sprintf("tas upload: %g %s (%s)\n", i + 1, tup_l[i], tup_p[i]));
		return;
	}
	if (i != floor(i) || i < 0 || i >= tup_n) { print(sprintf("tas upload: 1..%g\n", tup_n)); return; }
	if (!tasu_open) TASUI_Toggle(0);
	TASUI_SelectTab(TAS_TAB_UPLOAD);
	if (tup_state == 1 || tup_state == 3) { print("tas upload: one is on its way; wait for its answer\n"); return; }
	tup_state = 0; TASUp_Ask(i);
};
void(float argc) TASUp_Verb =
{
	local float i;
	if (argc >= 3 && argv(2) == "status") { print(sprintf("tas upload: state %g %s\n", tup_state, tup_note)); return; }
	i = (argc >= 3) ? stof(argv(2)) - 1 : -2;
	if (argc >= 3)
	if (checkbuiltin(cmdlevel_local))      // nested: QC evaluates both sides of &&
	if (!cmdlevel_local())
	{
		print("tas upload: only from your own console or binds\n");   // review: a server's command opened the tab
		return;
	}
	if (!isserver()) { print("tas upload: in a game you host\n"); return; }
	tup_pend = i; tup_pendt = cltime + 5;
	tup_at = 0; TASUp_List();
};
