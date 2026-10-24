/*
  Patch 854: Story and Event mode.  surfd works the medals out from WOS rows
  (/api/board?story=list|players|player, surfd.py game_story); this screen
  draws the ladder, the trophy count and other players' progress, and Play
  joins a lobby through ui_launch as the map list does.

  "Me" is the handle surfd gives this install's key, asked with the Friends
  proof (m_friends.qc: op list, plus story=1) and kept in data/story_me.txt for
  when the menu cannot sign (in a game, or an engine without friends_sign).
*/
#define STY_LISTS       3
#define STY_TABS        4           // the lists, then players
#define STY_ROW_H       52
#define STY_PROW_H      44
#define STY_SIDE_W      300
#define STY_PROGRESS_RETRIES 6     // pending-only waits: 1, 2, 4, 8, 8, 8 seconds
#define STY_FRESH       60          // seconds a reply is reused
#define STY_WAIT        15          // seconds before an unanswered ask has failed
#define STY_RETRY       5           // P905: first wait before a failed ladder is asked again
#define STY_ME_FILE     "data/story_me.txt"
#define STY_ME_HEAD     "FTESURF-STORYME 1"
#define STY_GOLD        SUI_THEME_WARN
#define STY_SILVER      '0.78 0.80 0.88'
#define STY_BRONZE      SUI_THEME_FOCUS
#define STY_NUM_SZ      '64 64 0'

#define STY_IDLE        0
#define STY_ASK         1
#define STY_OK          2
#define STY_FAIL        3

float sty_ready, sty_tab, sty_plist, sty_n, sty_idxcount;
float sty_rules[STY_LISTS];
float sty_lvmap[STY_LISTS], sty_lvinfo[STY_LISTS], sty_lvtxt[STY_LISTS], sty_lvidx[STY_LISTS];
float sty_chtitle[STY_LISTS], sty_chbar[STY_LISTS], sty_rows[STY_LISTS], sty_prog[STY_LISTS];
float sty_nlv[STY_LISTS], sty_nch[STY_LISTS], sty_nrow[STY_LISTS];
float sty_t[STY_LISTS], sty_open[STY_LISTS], sty_sel[STY_LISTS];
string sty_lid[STY_LISTS], sty_ltitle[STY_LISTS];
vector sty_scr0, sty_scr1, sty_scr2, sty_scr3;
float sty_lrecv;                    // `time` when the ladder arrived: dated levels count from it
float sty_pl, sty_npl, sty_pltotal, sty_plfor;
// One request each: the list, one player's progress, the ranking, the proof.
float sty_lreq, sty_lst, sty_lat;
float sty_preq, sty_pst, sty_pat;
float sty_kreq, sty_kst, sty_kat, sty_kfor;
float sty_mreq, sty_mphase, sty_mat, sty_mnext, sty_notet;
string sty_me, sty_who, sty_whoname, sty_note, sty_lnote;
float sty_changed;
float sty_pending, sty_pretries, sty_pnext, sty_pgeneration;
float sty_preview[STY_LISTS], sty_previewtotal[STY_LISTS];
float sty_previewuntil, sty_previewgeneration, sty_previewscope, sty_previewserial, sty_pack;
#define STY_AWAIT_MAX 32
float sty_await[STY_AWAIT_MAX], sty_awaitcount, sty_awaitoverflow;
float sty_ackseen, sty_ackscope;
string sty_previewwho, sty_revision, sty_prevision;
float sty_previewdrawgeneration;

void() Sty_ClearPreview =
{
	local float L;
	for (L = 0; L < STY_AWAIT_MAX; L = L + 1) sty_await[L] = 0;
	sty_awaitcount = sty_awaitoverflow = 0;
	for (L = 0; L < STY_LISTS; L = L + 1)
	{
		if (sty_preview[L]) buf_del(sty_preview[L]);
		sty_preview[L] = buf_create();
		sty_previewtotal[L] = 0;
	}
	sty_previewuntil = 0;
	if (sty_previewwho != "") strunzone(sty_previewwho);
	sty_previewwho = "";
};
float sty_lfail, sty_lnone;         // P905: failed ladder asks in a row; the board said it has none

// P905: what the story asks and hears is for developer 1 only -- the title screen asks now.
void(string s) Sty_Log = { if (cvar("developer")) print(s); };

// A passing line beside the tabs, gone after 8 s.
void(string s) Sty_Note =
{
	if (strcmp(sty_note, "")) strunzone(sty_note);
	sty_note = strzone(s);
	sty_notet = time;
};

void(string s, __inout string slot) Sty_Set =
{
	if (strcmp(slot, "")) strunzone(slot);
	slot = (s == "") ? "" : strzone(s);
};

float() Sty_Online = { return (cvar("rec_terms") >= FS_TERMS_ONLINE); };

float() Sty_Init =
{
	local float L;
	if (sty_ready)
		return TRUE;
	for (L = 0; L < STY_LISTS; L = L + 1)
	{
		sty_rules[L] = buf_create();
		sty_lvmap[L] = buf_create();
		sty_lvinfo[L] = buf_create();
		sty_lvtxt[L] = buf_create();
		sty_lvidx[L] = buf_create();
		sty_chtitle[L] = buf_create();
		sty_chbar[L] = buf_create();
		sty_rows[L] = buf_create();
		sty_prog[L] = buf_create();
		sty_open[L] = 1;            // chapter 1 is open before anything is known
	}
	sty_pl = buf_create();
	sty_ready = TRUE;
	return TRUE;
};

void() Sty_LoadMe =
{
	local filestream fh;
	local string s;
	registercvar("ui_story_local", "", 0);
	cvar_set("ui_story_local", "");
	fh = fopen(STY_ME_FILE, FILE_READ);
	if (fh < 0) return;
	if (fgets(fh) == STY_ME_HEAD)
	{
		s = fgets(fh);
		if (MF_Hex(s, 12)) Sty_Set(s, sty_me);
		cvar_set("ui_story_local", sty_me);
	}
	fclose(fh);
};

void() Sty_SaveMe =
{
	local filestream fh;
	fh = fopen(STY_ME_FILE, FILE_WRITE);
	if (fh < 0) return;
	fputs(fh, strcat(STY_ME_HEAD, "\n", sty_me, "\n"));
	fclose(fh);
};

// A GET on the board's own address; the request id, or 0.
float(string q) Sty_Get =
{
	local float id;
	local string dir;
	if (!Sty_Online()) return 0;
	dir = cvar_string("lobby_dir");
	if (dir == "") return 0;
	id = Lob_NextReq();
	if (!uri_get(strcat(dir, "/api/board?", q), id)) return 0;
	Sty_Log(sprintf("^5story:^7 asked id %g: %s\n", id, q));
	return id;
};

// P905: a ladder ask that failed; the next waits 5, 10, 20, 40, then 60 s (Sty_RetryIn).
void(string why) Sty_ListFailed =
{
	sty_lreq = 0;
	sty_lst = STY_FAIL;
	sty_lat = time;
	sty_lfail = sty_lfail + 1;
	if (why != "") Sty_Set(why, sty_lnote);
};

float() Sty_RetryIn =
{
	local float d, k;
	d = STY_RETRY;
	for (k = 1; k < sty_lfail && d < 60; k = k + 1)
		d = d * 2;
	return min(d, 60);
};

void() Sty_AskList =
{
	if (sty_lst == STY_ASK) return;
	sty_lreq = Sty_Get("story=list");
	sty_lst = sty_lreq ? STY_ASK : STY_FAIL;
	sty_lat = time;
	if (!sty_lreq) sty_lfail = sty_lfail + 1;
	if (!sty_lreq) Sty_Set(Sty_Online() ? "Could not ask the board for the ladder." :
		"Story needs online play: turn it on in Settings / Privacy.", sty_lnote);
};

void() Sty_Preview;

void() Sty_AskProg =
{
	// P905: never before the ladder -- an answer that lands first matches no list, reads
	// as 0 trophies and chapter 1, and stood until the list's own re-ask (Sty_Reply).
	// Every entrypoint, including UI open/list callbacks, consumes the mailbox
	// before snapshotting GET eligibility; a same-frame event cannot be skipped.
	if (sty_lst == STY_OK) Sty_Preview();
	if (sty_who == "" || sty_pst == STY_ASK || sty_lst != STY_OK) return;
	sty_pgeneration = cvar("ui_story_changed");
	sty_pack = (sty_awaitcount == 0 && !sty_awaitoverflow);
	Sty_Set(sty_revision, sty_prevision);
	sty_preq = Sty_Get(strcat("story=player&who=", sty_who));
	sty_pst = sty_preq ? STY_ASK : STY_FAIL;
	sty_pat = time;
};

void(float L) Sty_AskPlayers =
{
	if (L >= sty_n || sty_kst == STY_ASK) return;
	sty_kreq = Sty_Get(strcat("story=players&list=", uri_escape(sty_lid[L])));
	sty_kst = sty_kreq ? STY_ASK : STY_FAIL;
	sty_kat = time;
	sty_kfor = L;
};

// The Friends proof, op list, phase 1: the challenge.
// Asked again 30 s after a failure and 10 min after an answer (a link made
// meanwhile changes it); never while connected, where the engine will not sign.
void() Sty_AskMe =
{
	if (sty_mphase || time < sty_mnext || !Sty_Online()) return;
	if (clientstate() != 1 || !checkbuiltin(friends_sign)) return;  // cannot sign: keep the saved one
	sty_mreq = Lob_NextReq();
	sty_mphase = 1;
	sty_mat = time;
	sty_mnext = time + 30;
	if (!uri_get(sprintf("%s/api/social/menu/challenge?op=list&who=-", MF_SITE), sty_mreq))
		sty_mphase = 0;
};

void(string who) Sty_View =
{
	local float L;
	if (who != "" && !MF_Hex(who, 12)) return;
	if (strcmp(who, sty_who))
	{
		Sty_ClearPreview();
		sty_previewgeneration = cvar("ui_story_changed");
	}
	Sty_Set(who, sty_who);
	Sty_Set("", sty_whoname);
	for (L = 0; L < STY_LISTS; L = L + 1)
	{
		sty_t[L] = 0;
		sty_open[L] = 1;
		buf_del(sty_prog[L]);
		sty_prog[L] = buf_create();
	}
	sty_pst = STY_IDLE;
	sty_pending = sty_pretries = sty_pnext = 0;
	sty_preq = 0;
	Sty_AskProg();
};

// ---------------------------------------------------------------- replies --

void(string body) Sty_ParseList =
{
	local int root, lists, o, chs, lvs, lv, hold, ch, c;
	local float L, n, j, k, m, track, chap, timed, kinds, tb, kb, ks, kg;
	local string info, rev, mk;
	local int win;
	local float dated;

	root = json_parse(body);
	if (!root)
	{
		Sty_ListFailed("The board sent a ladder this game cannot read.");
		return;
	}
	lists = json_find_object_child(root, "lists");
	n = min(json_get_length(lists), STY_LISTS);
	rev = json_get_string(json_find_object_child(root, "rev"));
	if (strcmp(rev, sty_revision)) Sty_ClearPreview();
	Sty_Set(rev, sty_revision);
	for (L = 0; L < n; L = L + 1)
	{
		o = json_get_child_at_index(lists, L);
		Sty_Set(substring(json_get_string(json_find_object_child(o, "id")), 0, 16), sty_lid[L]);
		Sty_Set(substring(json_get_string(json_find_object_child(o, "title")), 0, 64), sty_ltitle[L]);
		buf_del(sty_chtitle[L]); sty_chtitle[L] = buf_create();
		buf_del(sty_chbar[L]); sty_chbar[L] = buf_create();
		buf_del(sty_lvmap[L]); sty_lvmap[L] = buf_create();
		buf_del(sty_lvinfo[L]); sty_lvinfo[L] = buf_create();
		buf_del(sty_lvtxt[L]); sty_lvtxt[L] = buf_create();
		buf_del(sty_rules[L]); sty_rules[L] = buf_create();
		buf_del(sty_lvidx[L]); sty_lvidx[L] = buf_create();
		buf_del(sty_rows[L]); sty_rows[L] = buf_create();
		chs = json_find_object_child(o, "chapters");
		sty_nch[L] = min(json_get_length(chs), 64);
		for (j = 0; j < sty_nch[L]; j = j + 1)
		{
			c = json_get_child_at_index(chs, j);
			bufstr_set(sty_chtitle[L], j, substring(json_get_string(json_find_object_child(c, "title")), 0, 64));
			bufstr_set(sty_chbar[L], j, ftos(json_get_float(json_find_object_child(c, "bar"))));
		}
		lvs = json_find_object_child(o, "levels");
		sty_nlv[L] = min(json_get_length(lvs), 256);
		sty_nrow[L] = 0;
		chap = -1;
		for (k = 0; k < sty_nlv[L]; k = k + 1)
		{
			lv = json_get_child_at_index(lvs, k);
			track = json_get_float(json_find_object_child(lv, "track"));
			timed = json_get_float(json_find_object_child(lv, "timed"));
			hold = json_find_object_child(lv, "hold");
			// A chapter row before the first level of each chapter, empty ones included.
			while (chap < json_get_float(json_find_object_child(lv, "chap")) && chap < sty_nch[L] - 1)
			{
				chap = chap + 1;
				bufstr_set(sty_rows[L], sty_nrow[L], strcat("c ", ftos(chap)));
				sty_nrow[L] = sty_nrow[L] + 1;
			}
			bufstr_set(sty_rows[L], sty_nrow[L], strcat("l ", ftos(k)));
			sty_nrow[L] = sty_nrow[L] + 1;
			bufstr_set(sty_lvmap[L], k, substring(json_get_string(json_find_object_child(lv, "map")), 0, 64));
			// Per medal slot: -1 unset, 0 decided by board rows, 1 coming soon.
			kinds = 0;
			info = "";
			for (m = 0; m < 3; m = m + 1)
				bufstr_set(sty_lvtxt[L], k * 3 + m, "");
			ch = json_find_object_child(lv, "ch");
			tb = json_get_length(ch);
			kb = ks = kg = -1;
			for (m = 0; m < tb && m < 3; m = m + 1)
			{
				c = json_get_child_at_index(ch, m);
				mk = json_get_string(json_find_object_child(c, "m"));
				j = (mk == "b") ? 0 : (mk == "s") ? 1 : (mk == "g") ? 2 : -1;
				if (j < 0) continue;
				bufstr_set(sty_lvtxt[L], k * 3 + j, substring(json_get_string(json_find_object_child(c, "t")), 0, 80));
				bufstr_set(sty_rules[L], k * 3 + j, sprintf("%s %g %g",
				           json_get_string(json_find_object_child(c, "k")),
				           json_get_float(json_find_object_child(c, "v")),
				           json_get_float(json_find_object_child(c, "w"))));
				kinds = (json_get_float(json_find_object_child(c, "live")) == 1) ? 0 : 1;
				if (j == 0) kb = kinds;
				else if (j == 1) ks = kinds;
				else kg = kinds;
			}
			info = sprintf("%g %g %g %g %g %g ", track, json_get_float(json_find_object_child(lv, "chap")), timed,
			               json_get_float(json_get_child_at_index(hold, 0)),
			               json_get_float(json_get_child_at_index(hold, 1)),
			               json_get_float(json_get_child_at_index(hold, 2)));
			// Patch 856: a dated level's seconds until it opens and until it ends.
			win = json_find_object_child(lv, "in");
			dated = json_get_length(win);
			bufstr_set(sty_lvinfo[L], k, strcat(info, sprintf("%g %g %g ", kb, ks, kg),
			           sprintf("%g %d %d %g", dated == 2,
			                   json_get_float(json_get_child_at_index(win, 0)),
			                   json_get_float(json_get_child_at_index(win, 1)),
			                   !strcmp(json_get_string(json_find_object_child(lv, "mode")), "maxfog"))));
		}
		// Chapters after the last level still get their header row.
		while (chap < sty_nch[L] - 1)
		{
			chap = chap + 1;
			bufstr_set(sty_rows[L], sty_nrow[L], strcat("c ", ftos(chap)));
			sty_nrow[L] = sty_nrow[L] + 1;
		}
		if (sty_sel[L] >= sty_nlv[L]) sty_sel[L] = 0;
	}
	sty_n = n;
	sty_lrecv = time;
	if (sty_plist >= n) sty_plist = 0;
	if (sty_tab < STY_LISTS && sty_tab >= n) sty_tab = 0;
	sty_idxcount = -1;
	json_free(root);
	sty_lst = STY_OK;
	sty_lfail = 0;
	sty_lnone = FALSE;
	Sty_Set("", sty_lnote);
	Sty_Log(sprintf("^5story:^7 list rev %s: %g list(s), %g/%g level(s)\n", rev, n, sty_nlv[0], sty_nlv[1]));
};

void(string body) Sty_ParseProg =
{
	local int root, lists, o, lv, x;
	local float L, n, i, k, cnt;
	local string id;

	root = json_parse(body);
	if (!root) { sty_pst = STY_FAIL; return; }
	if (strcmp(json_get_string(json_find_object_child(root, "who")), sty_who))
	{
		json_free(root);
		sty_pst = STY_FAIL;         // an answer about somebody not shown
		return;
	}
	Sty_Set(substring(json_get_string(json_find_object_child(root, "name")), 0, 64), sty_whoname);
	lists = json_find_object_child(root, "lists");
	n = json_get_length(lists);
	for (i = 0; i < n; i = i + 1)
	{
		o = json_get_child_at_index(lists, i);
		id = json_get_string(json_find_object_child(o, "id"));
		for (L = 0; L < sty_n; L = L + 1)
			if (!strcmp(id, sty_lid[L])) break;
		if (L >= sty_n) continue;
		sty_t[L] = json_get_float(json_find_object_child(o, "t"));
		sty_open[L] = max(1, json_get_float(json_find_object_child(o, "open")));
		buf_del(sty_prog[L]);
		sty_prog[L] = buf_create();
		lv = json_find_object_child(o, "lv");
		cnt = json_get_length(lv);
		for (k = 0; k < cnt; k = k + 1)
		{
			x = json_get_child_at_index(lv, k);
			bufstr_set(sty_prog[L], json_get_float(json_get_child_at_index(x, 0)),
			           sprintf("%g %g", json_get_float(json_get_child_at_index(x, 1)),
			                   json_get_float(json_get_child_at_index(x, 2))));
		}
	}
	sty_pending = json_get_float(json_find_object_child(root, "pending"));
	sty_pnext = 0;
	if (sty_pending)
	{
		if (sty_pretries < STY_PROGRESS_RETRIES)
		{
			sty_pnext = time + min(8, pow(2, sty_pretries));
			sty_pretries = sty_pretries + 1;
		}
	}
	else
	{
		sty_pretries = 0;
		if (sty_pgeneration == cvar("ui_story_changed") && sty_pack
		    && !strcmp(sty_prevision, sty_revision)
		    && !strcmp(json_get_string(json_find_object_child(root, "rev")), sty_revision))
		{
			Sty_ClearPreview();
			sty_previewgeneration = sty_pgeneration;
		}
	}
	json_free(root);
	sty_pst = STY_OK;
	Sty_Log(sprintf("^5story:^7 progress of %s: %g / %g trophies, chapter %g / %g\n",
	              sty_who, sty_t[0], sty_t[1], sty_open[0], sty_open[1]));
};

void(string body) Sty_ParsePlayers =
{
	local int root, arr, o;
	local float n, i;
	local string av;

	root = json_parse(body);
	if (!root) { sty_kst = STY_FAIL; return; }
	arr = json_find_object_child(root, "players");
	n = min(json_get_length(arr), 100);
	buf_del(sty_pl);
	sty_pl = buf_create();
	for (i = 0; i < n; i = i + 1)
	{
		o = json_get_child_at_index(arr, i);
		av = json_get_string(json_find_object_child(o, "av"));
		if (!MF_Hex(av, 8)) av = "-";
		bufstr_set(sty_pl, i, strcat(sprintf("%s %g %g %g %g %g %s ",
			json_get_string(json_find_object_child(o, "who")),
			json_get_float(json_find_object_child(o, "t")), json_get_float(json_find_object_child(o, "open")),
			json_get_float(json_find_object_child(o, "g")), json_get_float(json_find_object_child(o, "s")),
			json_get_float(json_find_object_child(o, "b")), av),
			"\"", uri_escape(substring(json_get_string(json_find_object_child(o, "name")), 0, 64)), "\""));
	}
	sty_npl = n;
	sty_plfor = sty_kfor;
	sty_pltotal = json_get_float(json_find_object_child(root, "total"));
	json_free(root);
	sty_kst = STY_OK;
	Sty_Log(sprintf("^5story:^7 %g of %g player(s) on %s\n", n, sty_pltotal, sty_lid[sty_kfor]));
};

void(string body) Sty_MeReply =
{
	local int root;
	local string nonce, expires, ticket, proof, pub, sig, who;
	local float viewing;

	root = json_parse(body);
	if (!root) { sty_mphase = 0; return; }
	if (json_get_float(json_find_object_child(root, "ok")) != 1)
	{
		Sty_Log(sprintf("^5story:^7 who-am-I refused: %s\n", json_get_string(json_find_object_child(root, "error"))));
		sty_mphase = 0;
		json_free(root);
		return;
	}
	if (sty_mphase == 1)
	{
		nonce = json_get_string(json_find_object_child(root, "nonce"));
		expires = json_get_string(json_find_object_child(root, "expires"));
		ticket = json_get_string(json_find_object_child(root, "ticket"));
		json_free(root);
		proof = "";
		if (clientstate() == 1)
		if (MF_Hex(nonce, 32) && MF_Hex(ticket, 64) && strlen(expires) == 10)
			proof = friends_sign(nonce, "list", "-");
		if (tokenize(proof) != 2) { sty_mphase = 0; return; }
		pub = argv(0); sig = argv(1);
		if (!MF_Hex(pub, 64) || !MF_Hex(sig, 128)) { sty_mphase = 0; return; }
		sty_mreq = Lob_NextReq();
		sty_mphase = 2;
		sty_mat = time;
		if (!uri_get(strcat(MF_SITE, "/api/social/menu"), sty_mreq, "application/x-www-form-urlencoded",
		             sprintf("op=list&who=-&story=1&nonce=%s&expires=%s&ticket=%s&pub=%s&sig=%s",
		                     nonce, expires, ticket, pub, sig)))
			sty_mphase = 0;
		return;
	}
	who = json_get_string(json_find_object_child(root, "who"));
	json_free(root);
	sty_mphase = 0;
	sty_mnext = time + 600;
	if (who == "")
	{
		Sty_Log("^5story:^7 this install has no WOS runs on the board yet\n");
		Sty_Note("Finish a run on a lobby and your medals start here.");
		return;
	}
	if (!MF_Hex(who, 12)) return;
	Sty_Log(sprintf("^5story:^7 this install plays as %s\n", who));
	Sty_Note("");
	if (strcmp(who, sty_me))
	{
		viewing = (sty_who != "" && strcmp(sty_who, sty_me));
		if (sty_me == "" && !viewing && sty_previewuntil > 0)
		{
			// Bind a connection-local preview when this install first resolves.
			Sty_Set(who, sty_previewwho);
			Sty_Set(who, sty_me);
			Sty_Set(who, sty_who);
			sty_pst = STY_IDLE;
			Sty_AskProg();
		}
		else
		{
			Sty_ClearPreview();
			Sty_Set(who, sty_me);
			if (!viewing) Sty_View(sty_me);
		}
		cvar_set("ui_story_local", sty_me);
		Sty_SaveMe();
	}
};

float(float reqid, float code, string body) Sty_Reply =
{
	if (!reqid) return FALSE;
	if (reqid == sty_mreq && sty_mphase)
	{
		if (code) { Sty_Log(sprintf("^5story:^7 who-am-I returned %g\n", code)); sty_mphase = 0; }
		else Sty_MeReply(body);
		return TRUE;
	}
	if (reqid == sty_lreq)
	{
		sty_lreq = 0;
		sty_lat = time;
		if (code)
		{
			Sty_ListFailed("");
			sty_lnone = (code == 404);      // no list at all: not asked again until STORY is opened
			Sty_Log(sprintf("^5story:^7 list returned %g\n", code));
			if (code < 0)
				Sty_Set("Could not reach the board. Try again shortly.", sty_lnote);
			else
				Sty_Set(code == 404 ? "The board has no story list yet." :
					sprintf("The board did not answer (%g). Try again shortly.", code), sty_lnote);
		}
		else
		{
			Sty_ParseList(body);
			if (sty_who != "") { sty_pst = STY_IDLE; Sty_AskProg(); }
		}
		return TRUE;
	}
	if (reqid == sty_preq)
	{
		sty_preq = 0;
		sty_pat = time;
		if (code) sty_pst = STY_FAIL;
		else Sty_ParseProg(body);
		return TRUE;
	}
	if (reqid == sty_kreq)
	{
		sty_kreq = 0;
		sty_kat = time;
		if (code) sty_kst = STY_FAIL;
		else Sty_ParsePlayers(body);
		return TRUE;
	}
	return FALSE;
};

// Only pending player progress retries quickly; list/roster keep their own timers.
void() Sty_RetryProgress =
{
	if (!Sty_Online()) return;
	if (sty_pnext > 0 && time >= sty_pnext && sty_pst != STY_ASK)
	{
		sty_pnext = 0;
		Sty_AskProg();
	}
};

// Only facts known at completion may assert local tasks. Global first/rank/via
// stay unknown until authority; their decorative HTTP toast is not a task payload.
float(string rule, float leg, float ms, float fails, float mask, float top, float prevms) Sty_LocalTask =
{
	local string kind;
	local float v, w;
	if (tokenize(rule) < 3) return FALSE;
	kind = argv(0); v = stof(argv(1)); w = stof(argv(2));
	if (!strcmp(kind, "reach")) return (leg == 0 || (leg > 0 && leg >= v - 1));
	if (!strcmp(kind, "stage")) return (leg == v && ms < w);
	if (leg != 0) return FALSE;
	if (!strcmp(kind, "finish")) return TRUE;
	if (!strcmp(kind, "time")) return (ms < v);
	if (!strcmp(kind, "nofail")) return (fails == 0);
	if (!strcmp(kind, "speed")) return (top >= v);
	if (!strcmp(kind, "improve")) return (prevms > 0 && ms * 100 <= prevms * (100 - v));
	if (mask < 0) return FALSE;
	if (!strcmp(kind, "wonly")) return !(mask & 14);
	if (!strcmp(kind, "nojump")) return !(mask & 16);
	if (!strcmp(kind, "sw")) return !(mask & 12);
	if (!strcmp(kind, "hsw")) return !(mask & 1024);
	return FALSE;
};

void() Sty_Preview =
{
	local string event, map;
	local float generation, track, leg, ms, fails, mask, top, serial;
	local float L, i, m, medal, prior, held, prevms, dated, opens, closes, changed, slot;
	generation = cvar("ui_story_changed");
	if (sty_previewuntil > 0)
	if (!Sty_Online() || gettime(0) >= sty_previewuntil
	    || sty_previewscope != cvar("ui_story_scope")
	    || strcmp(sty_previewwho, sty_me) || strcmp(sty_who, sty_me)) Sty_ClearPreview();
	if (generation == sty_previewgeneration || sty_lst != STY_OK) return;
	if (!Sty_Online()) return;
	sty_previewgeneration = generation;
	// Empty/empty is the local connection's unresolved self, not another profile.
	if (strcmp(sty_who, sty_me)) return;
	if (strcmp(cvar_string("ui_story_preview_who"), sty_me)) return;
	if (cvar("ui_story_preview_until") <= gettime(0)) return;
	event = cvar_string("ui_story_preview");
	if (tokenizebyseparator(event, "|") != 2) return;
	event = argv(0);
	if (tokenize(event) != 8) return;
	serial = stof(argv(0)); track = stof(argv(1)); leg = stof(argv(2)); ms = stof(argv(3));
	fails = stof(argv(5)); mask = stof(argv(6)); top = stof(argv(7));
	if (serial < 1 || ms < 1) return;
	// Keep map stable while the rule evaluator tokenizes individual challenges.
	tokenizebyseparator(cvar_string("ui_story_preview"), "|");
	map = strzone(argv(1));
	changed = FALSE;
	for (L = 0; L < sty_n; L = L + 1)
	for (i = 0; i < sty_nlv[L]; i = i + 1)
	{
		if (strcmp(map, bufstr_get(sty_lvmap[L], i))) continue;
		tokenize(bufstr_get(sty_lvinfo[L], i));
		if (track != stof(argv(0)) || !stof(argv(2))) continue;
		dated = stof(argv(9)); opens = stof(argv(10)); closes = stof(argv(11));
		if (dated)
		if (time - sty_lrecv < opens || time - sty_lrecv >= closes) continue;
		prevms = 0; held = 0;
		if (tokenize(bufstr_get(sty_prog[L], i)) >= 2)
		{
			held = stof(argv(0)); prevms = stof(argv(1));
		}
		medal = held;
		if (sty_preview[L]) medal = max(medal, stof(bufstr_get(sty_preview[L], i)));
		prior = medal;
		for (m = 0; m < 3; m = m + 1)
			if (Sty_LocalTask(bufstr_get(sty_rules[L], i * 3 + m), leg, ms, fails, mask, top, prevms)) medal = max(medal, m + 1);
		if (medal <= prior) continue;
		changed = TRUE;
		if (!sty_preview[L]) sty_preview[L] = buf_create();
		bufstr_set(sty_preview[L], i, ftos(medal));
		// Highest medal per level is its points; update every matching list/level.
		sty_previewtotal[L] = max(sty_t[L], sty_previewtotal[L]) + medal - prior;
		Sty_Log(sprintf("story: local provisional list %g level %g medal %g total %g at %g\n", L, i + 1, medal, sty_previewtotal[L], gettime(0)));
	}
	strunzone(map);
	if (!changed) return; // unrelated stages neither confirm nor clear prior tasks
	slot = -1;
	for (i = 0; i < STY_AWAIT_MAX; i = i + 1)
		if (sty_await[i] == 0 && slot < 0) slot = i;
	if (slot < 0) sty_awaitoverflow = TRUE; // conservative until expiry, never pretend acked
	else
	{
		sty_await[slot] = serial;
		sty_awaitcount = sty_awaitcount + 1;
	}
	sty_previewserial = serial;
	sty_previewscope = cvar("ui_story_scope");
	Sty_Set(sty_me, sty_previewwho);
	sty_previewuntil = cvar("ui_story_preview_until");
};

float(float L) Sty_Total = { return max(sty_t[L], sty_previewtotal[L]); };
float(float L) Sty_OpenChapter =
{
	local float j, opened;
	opened = sty_open[L];
	if (!sty_previewuntil) return opened;
	for (j = 1; j < sty_nch[L]; j = j + 1)
		if (Sty_Total(L) >= stof(bufstr_get(sty_chbar[L], j))) opened = max(opened, j + 1);
	return opened;
};

void() Sty_Refresh;

void() Sty_AckProgress =
{
	local float i, ack;
	if (sty_ackscope != cvar("ui_story_scope"))
	{
		sty_ackscope = cvar("ui_story_scope");
		sty_ackseen = 0;
	}
	ack = cvar("ui_story_ack");
	if (ack == sty_ackseen) return;
	sty_ackseen = ack;
	if (ack <= 0) return;
	for (i = 0; i < STY_AWAIT_MAX; i = i + 1)
	if (sty_await[i] == ack)
	{
		sty_await[i] = 0;
		sty_awaitcount = sty_awaitcount - 1;
	}
	if (sty_previewuntil > 0 && sty_awaitcount == 0 && !sty_awaitoverflow) Sty_Refresh();
};

// Answers that never came, and refreshes while the screen is up.
void() Sty_Poll =
{
	Sty_Preview();
	Sty_AckProgress();
	if (sty_changed != cvar("ui_story_changed")) Sty_Refresh();
	Sty_RetryProgress();
	if (sty_lst == STY_ASK && time - sty_lat > STY_WAIT)
		Sty_ListFailed("The board did not answer. Try again shortly.");
	if (sty_pst == STY_ASK && time - sty_pat > STY_WAIT) { sty_preq = 0; sty_pst = STY_FAIL; }
	if (sty_kst == STY_ASK && time - sty_kat > STY_WAIT) { sty_kreq = 0; sty_kst = STY_FAIL; }
	if (sty_mphase && time - sty_mat > STY_WAIT) sty_mphase = 0;
	Sty_AskMe();
	// P905: a failed ladder backs off from STY_RETRY instead of waiting STY_FRESH; a 404 waits for STORY.
	if (sty_lst != STY_ASK && !(sty_lst == STY_FAIL && sty_lnone))
	if (time - sty_lat > ((sty_lst == STY_FAIL) ? Sty_RetryIn() : STY_FRESH))
		Sty_AskList();
	if (sty_lst == STY_OK && sty_pst != STY_ASK && sty_who != "" && time - sty_pat > STY_FRESH)
		Sty_AskProg();
	if (sty_tab == STY_TABS - 1 && sty_kst != STY_ASK && (sty_kfor != sty_plist || time - sty_kat > STY_FRESH))
		Sty_AskPlayers(sty_plist);
};

// P905 (Lex: "sometimes it doesn't load on first click"): the ladder, the saved "me" and
// its progress are asked from the title screen once online play is allowed, so the first
// STORY click finds them; three tries at most, on Sty_RetryIn's waits, none after a 404.
float sty_pref, sty_opened;

void() Sty_Refresh =
{
	sty_changed = cvar("ui_story_changed");
	sty_preq = 0;
	sty_pst = STY_IDLE;
	sty_pending = sty_pretries = sty_pnext = 0;
	sty_pat = -STY_FRESH;
	sty_kat = -STY_FRESH;
	if (sty_me == "") sty_mnext = 0;
	Sty_AskProg();
};
void() Sty_Prefetch =
{
	if (!Sty_Online() || !Sty_Init())
		return;
	Sty_Preview();
	Sty_AckProgress();
	if (sty_changed != cvar("ui_story_changed")) Sty_Refresh();
	Sty_RetryProgress();
	if (sty_lst == STY_OK && sty_pst == STY_IDLE) Sty_AskProg();
	if (sty_lst == STY_ASK && time - sty_lat > STY_WAIT)
		Sty_ListFailed("");
	if (sty_lst == STY_OK || sty_lst == STY_ASK || sty_lnone || sty_pref >= 3)
		return;
	if (sty_lst == STY_FAIL && time - sty_lat < Sty_RetryIn())
		return;
	sty_pref = sty_pref + 1;
	if (sty_me == "") Sty_LoadMe();
	if (sty_who == "" && sty_me != "") Sty_View(sty_me);
	Sty_AskList();
	Sty_AskMe();
	Sty_Log(sprintf("^5story:^7 prefetch %g from the title screen\n", sty_pref));
};

void() Sty_Open =
{
	if (!Sty_Init()) return;
	// First entry reuses P905's prefetch; returning from play never reuses progress.
	if (((sty_opened || clientstate() == 2) && menu_screen != SCREEN_STORY)
	    || sty_changed != cvar("ui_story_changed")) Sty_Refresh();
	sty_opened = TRUE;
	if (ms_count == 0)
		ui_create_open();           // the map rows Play and the thumbnails come from
	if (sty_me == "") Sty_LoadMe();
	// Older than 10 s is asked again now; an ask in flight is left to land.
	if (sty_lst != STY_ASK && time - sty_lat > 10) { sty_lat = -STY_FRESH; sty_lnone = FALSE; }
	if (sty_pst != STY_ASK && time - sty_pat > 10) sty_pat = -STY_FRESH;
	if (sty_kst != STY_ASK && time - sty_kat > 10) sty_kat = -STY_FRESH;
	if (sty_who == "" && sty_me != "") Sty_View(sty_me);
	menu_screen = SCREEN_STORY;
};

void() Sty_Esc =
{
	if (ui_join_busy())
	{
		ui_status_cancel();
		return;
	}
	menu_screen = SCREEN_MAIN;
};

// Counts are lobby occupants on maps in this ladder, not medal holders.
float(float L, string map) Sty_LivePlayers =
{
	local float i, k, found, total;
	if (!Sty_Online() || !Lob_Fresh()) return -1;
	total = 0;
	for (i = 0; i < Lob_Count(); i = i + 1)
	{
		if (!Lob_Live(i)) continue;
		found = FALSE;
		for (k = 0; k < sty_nlv[L]; k = k + 1)
			if (!strcasecmp(Lob_Map(i), bufstr_get(sty_lvmap[L], k))) found = TRUE;
		if (map != "" && strcasecmp(map, Lob_Map(i))) found = FALSE;
		if (found) total = total + max(0, Lob_Players(i));
	}
	return total;
};

string(float n) Sty_Population =
{
	if (n < 0) return "Players live: unavailable";
	if (n == 0) return "";
	return sprintf("%g %s live", n, n == 1 ? "player" : "players");
};

// ---------------------------------------------------------------- drawing --

float(float L, float i) Sty_Medal =
{
	local float official;
	official = 0;
	if (tokenize(bufstr_get(sty_prog[L], i)) >= 2) official = stof(argv(0));
	if (sty_preview[L]) return max(official, stof(bufstr_get(sty_preview[L], i)));
	return official;
};

float(float L, float i) Sty_Ms =
{
	if (tokenize(bufstr_get(sty_prog[L], i)) < 2) return 0;
	return stof(argv(1));
};

// The level's row in the map list, cached until the list reloads.
float(float L, float i) Sty_MapRow =
{
	local string s;
	local float r;
	if (sty_idxcount != ms_count)
	{
		for (r = 0; r < STY_LISTS; r = r + 1)
		{
			buf_del(sty_lvidx[r]);
			sty_lvidx[r] = buf_create();
		}
		sty_idxcount = ms_count;
	}
	s = bufstr_get(sty_lvidx[L], i);
	if (s != "")
	{
		r = stof(s);
		// A reload can move rows without changing ms_count (a download lands).
		if (r < 0 || !strcasecmp(bufstr_get(ms_name, r), bufstr_get(sty_lvmap[L], i)))
			return r;
	}
	r = ui_map_index(bufstr_get(sty_lvmap[L], i));
	bufstr_set(sty_lvidx[L], i, ftos(r));
	return r;
};

void(vector pos, vector size, float row) Sty_Thumb =
{
	local float page, cell;
	page = cell = -1;
	if (row >= 0)
	if (tokenize(bufstr_get(ms_meta, row)) > MT_UUID)
	{
		page = (argv(MT_PAGE) == "-") ? -1 : stof(argv(MT_PAGE));
		cell = (argv(MT_CELL) == "-") ? -1 : stof(argv(MT_CELL));
	}
	ui_thumb(pos, size, page, cell);
};

vector(float m) Sty_MedalCol =
{
	if (m == 2) return STY_GOLD;
	if (m == 1) return STY_SILVER;
	return STY_BRONZE;
};

// One medal: filled when held, a ring when open, a dot when the file sets none.
void(vector pos, float m, float state, float a) Sty_Pip =
{
	if (state < 0)
	{
		sui_roundbox(pos + '5 5 0', '4 4 0', 2, COL_DIM, 0.35 * a);
		return;
	}
	if (state > 0)
	{
		sui_roundbox(pos, '14 14 0', 7, Sty_MedalCol(m), a);
		return;
	}
	sui_roundbox(pos, '14 14 0', 7, COL_BORDER, 0.9 * a);
	sui_roundbox(pos + '2 2 0', '10 10 0', 5, SUI_THEME_WELL, a);
};

float(vector v, float m) Sty_K =
{
	if (m == 0) return v_x;
	if (m == 1) return v_y;
	return v_z;
};

// The level's medal slots, -1 unset, as read from its info line.
vector(float L, float i) Sty_Kinds =
{
	if (tokenize(bufstr_get(sty_lvinfo[L], i)) < 9) return '-1 -1 -1';
	return [stof(argv(6)), stof(argv(7)), stof(argv(8))];
};

string(float s) Sty_Span =
{
	if (s >= 86400) return sprintf("%gd %gh", floor(s / 86400), floor((s % 86400) / 3600));
	if (s >= 3600) return sprintf("%gh %gm", floor(s / 3600), floor((s % 3600) / 60));
	return sprintf("%gm", max(1, ceil(s / 60)));
};

// Patch 856: a dated level's state -- "" undated, else opens in / ends in / ended.
string(float L, float i) Sty_When =
{
	local float gone;
	if (tokenize(bufstr_get(sty_lvinfo[L], i)) < 12) return "";
	if (stof(argv(9)) != 1) return "";
	gone = time - sty_lrecv;
	if (stof(argv(10)) - gone > 0) return strcat("opens in ", Sty_Span(stof(argv(10)) - gone));
	if (stof(argv(11)) - gone > 0) return strcat("ends in ", Sty_Span(stof(argv(11)) - gone));
	return "ended";
};

void(vector pos, float w) Sty_Hero =
{
	local float L, t, nx, bar, frac, g, s, b, i, p, x;
	local string line, togo;

	L = min(sty_tab, STY_LISTS - 1);
	t = Sty_Total(L);
	g = s = b = 0;
	for (i = 0; i < sty_nlv[L]; i = i + 1)
	{
		p = Sty_Medal(L, i);
		if (p == 3) g = g + 1;
		else if (p == 2) s = s + 1;
		else if (p == 1) b = b + 1;
	}
	Font_Set(ui_font_display);
	sui_text(pos, STY_NUM_SZ, ftos(t), STY_GOLD, 1, 0);
	x = stringwidth(ftos(t), TRUE, STY_NUM_SZ) + 14;
	sui_text([pos_x + x, pos_y + 8], SZ_HEAD, "TROPHIES", COL_DIM, 1, 0);
	Font_Set(ui_font_ui);
	sui_text([pos_x + x, pos_y + 38], SZ_LABEL, sty_ltitle[L], COL_DIM, 0.8, 0);
	x = x + 150;

	nx = Sty_OpenChapter(L);                  // 0-based index of the next chapter
	if (sty_nch[L] == 0)
		line = sty_lst == STY_ASK ? "Loading the ladder..." : "";
	else if (nx >= sty_nch[L])
		line = "Every chapter is open";
	else
	{
		bar = stof(bufstr_get(sty_chbar[L], nx));
		line = sprintf("Chapter %g opens at %g trophies", nx + 1, bar);
		togo = sprintf("%g to go", max(0, bar - t));
		sui_text([pos_x + w - stringwidth(togo, TRUE, SZ_LABEL), pos_y + 6], SZ_LABEL, togo, COL_DIM, 1, 0);
	}
	sui_text([pos_x + x, pos_y + 6], SZ_LABEL, line, COL_TEXT, 1, 0);
	frac = (sty_nch[L] > 0) ? 1 : 0;
	if (nx < sty_nch[L])
	{
		bar = stof(bufstr_get(sty_chbar[L], nx));
		frac = bar > 0 ? bound(0, t / bar, 1) : 1;
	}
	sui_roundbox([pos_x + x, pos_y + 30], [w - x, 10], 5, COL_ROW, 1);
	if (frac > 0)
		sui_roundbox([pos_x + x, pos_y + 30], [max(10, (w - x) * frac), 10], 5, STY_GOLD, 0.9);
	Sty_Pip([pos_x + x, pos_y + 50], 2, 1, 1);
	sui_text([pos_x + x + 20, pos_y + 49], SZ_LABEL, sprintf("%g gold", g), COL_DIM, 1, 0);
	Sty_Pip([pos_x + x + 100, pos_y + 50], 1, 1, 1);
	sui_text([pos_x + x + 120, pos_y + 49], SZ_LABEL, sprintf("%g silver", s), COL_DIM, 1, 0);
	Sty_Pip([pos_x + x + 210, pos_y + 50], 0, 1, 1);
	sui_text([pos_x + x + 230, pos_y + 49], SZ_LABEL, sprintf("%g bronze", b), COL_DIM, 1, 0);
	if (sty_nch[L])
		sui_text([pos_x + x + 330, pos_y + 49], SZ_LABEL,
		         sprintf("chapter %g of %g", min(Sty_OpenChapter(L), sty_nch[L]), sty_nch[L]), COL_DIM, 1, 0);
};

void(vector rp, vector rs, float L, float j, float hot) Sty_ChapterRow =
{
	local float bar, got, off, i, locked, m, p;
	local string title, meta;
	local vector k;

	bar = stof(bufstr_get(sty_chbar[L], j));
	locked = (j >= Sty_OpenChapter(L));
	got = off = 0;
	for (i = 0; i < sty_nlv[L]; i = i + 1)
	{
		if (tokenize(bufstr_get(sty_lvinfo[L], i)) < 9) continue;
		if (stof(argv(1)) != j) continue;
		if (stof(argv(2)) != 1) continue;       // untimed: nothing to offer yet
		k = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
		p = 0;
		for (m = 0; m < 3; m = m + 1)
			if (Sty_K(k, m) == 0) p = m + 1;
		off = off + p;
		got = got + Sty_Medal(L, i);
	}
	title = bufstr_get(sty_chtitle[L], j);
	Font_Set(ui_font_display);
	sui_text([rp_x + 8, rp_y + 20], SZ_HEAD, sprintf("CHAPTER %g", j + 1), locked ? COL_DIM : COL_ACCENT, 1, 0);
	m = stringwidth(sprintf("CHAPTER %g", j + 1), TRUE, SZ_HEAD);
	Font_Set(ui_font_ui);
	if (title != "")
		sui_text([rp_x + 20 + m, rp_y + 25], SZ_LABEL, title, COL_DIM, 1, 0);
	if (locked)
		meta = sprintf("^9LOCKED^7  opens at %g trophies, %g to go", bar, max(0, bar - Sty_Total(L)));
	else
		meta = sprintf("%g of %g trophies", got, off);
	sui_text([rp_x + rs_x - 12 - stringwidth(meta, TRUE, SZ_LABEL), rp_y + 25], SZ_LABEL, meta,
	         locked ? COL_DIM : COL_TEXT, 1, 0);
	sui_fill([rp_x + 8, rp_y + rs_y - 3], [rs_x - 16, 1], COL_BORDER, 0.6, 0);
};

void(vector rp, vector rs, float L, float i, float on, float hot) Sty_LevelRow =
{
	local float track, chap, timed, locked, row, a, med, ms, m, nx, tw;
	local string map, sub, tm, when;
	local vector kinds;

	map = bufstr_get(sty_lvmap[L], i);
	when = Sty_When(L, i);
	tokenize(bufstr_get(sty_lvinfo[L], i));
	track = stof(argv(0));
	chap = stof(argv(1));
	timed = stof(argv(2));
	kinds = Sty_Kinds(L, i);
	locked = (chap >= Sty_OpenChapter(L));
	a = locked ? 0.35 : 1;
	med = Sty_Medal(L, i);
	ms = Sty_Ms(L, i);

	if (on || hot)
		sui_roundbox(rp + '1 1 0', rs - '2 2 0', 7, on ? COL_ROW_SEL : COL_ROW_HOVER, 1);
	Font_Set(ui_font_display);
	sui_text([rp_x + 40 - stringwidth(ftos(i + 1), TRUE, SZ_HEAD), rp_y + 14], SZ_HEAD,
	         ftos(i + 1), COL_DIM, a, 0);
	Font_Set(ui_font_ui);
	nx = rp_x + 52;
	if (map == "")
	{
		sui_fill([nx, rp_y + 4], [78, 44], COL_ROW, 0.6, 0);
		sui_text([nx + 92, rp_y + 17], SZ_ROW, "Coming soon", COL_DIM, 0.7, 0);
		return;
	}
	row = Sty_MapRow(L, i);
	Sty_Thumb([nx, rp_y + 4], [78, 44], row);
	if (locked)
		sui_fill([nx, rp_y + 4], [78, 44], SUI_THEME_WELL, 0.6, 0);
	tw = rs_x - (nx - rp_x) - 92 - 80 - 110;
	sui_text([nx + 92, rp_y + 7], SZ_ROW, ui_fit_text(map, tw, SZ_ROW),
	         ((on || hot) && !locked) ? COL_ACCENT : COL_TEXT, a, 0);
	sub = Sty_Population(Sty_LivePlayers(L, map));
	if (track)
		sub = strcat(sub, sub == "" ? "" : "  ", sprintf("bonus %g", track));
	if (when != "")
		sub = strcat(sub, sub == "" ? "" : "  ", "^xfc3", when, "^7");
	if (!timed)
		sub = strcat(sub, sub == "" ? "" : "  ", "^9no zones yet^7");
	else if (locked)
		sub = strcat(sub, sub == "" ? "" : "  ", "locked");
	else
	{
		// The first medal above the one held that the file sets.
		for (m = med; m < 3; m = m + 1)
			if (Sty_K(kinds, m) >= 0) break;
		if (m >= 3)
			tm = "all medals";
		else
			tm = strcat("next: ", bufstr_get(sty_lvtxt[L], i * 3 + m),
			            Sty_K(kinds, m) > 0 ? " (coming soon)" : "");
		sub = strcat(sub, sub == "" ? "" : "  ", tm);
	}
	sui_text([nx + 92, rp_y + 29], SZ_LABEL, ui_fit_text(sub, tw, SZ_LABEL), COL_DIM, a, 0);
	for (m = 0; m < 3; m = m + 1)
		Sty_Pip([rp_x + rs_x - 190 + m * 20, rp_y + 19], m, Sty_K(kinds, m) < 0 ? -1 : (med >= m + 1) ? 1 : 0, a);
	Font_Set(ui_font_mono);
	tm = ms > 0 ? Time_MsString((int)ms) : "--";
	sui_text([rp_x + rs_x - 12 - stringwidth(tm, TRUE, SZ_ROW), rp_y + 18], SZ_ROW, tm,
	         ms > 0 ? COL_TEXT : COL_DIM, ms > 0 ? a : 0.5 * a, 0);
	Font_Set(ui_font_ui);
};

float(float L, float i) Sty_Locked =
{
	if (tokenize(bufstr_get(sty_lvinfo[L], i)) < 9) return TRUE;
	return (stof(argv(1)) >= Sty_OpenChapter(L));
};

void(float L, float i) Sty_Play =
{
	local float row, eventmax;
	local string map;
	map = bufstr_get(sty_lvmap[L], i);
	row = Sty_MapRow(L, i);
	if (map == "") return;
	if (row < 0)
	{
		Sty_Note(sprintf("%s is not on this game's map list yet.", map));
		return;
	}
	ms_selected = row;
	ui_plain_only = TRUE;
	if (ui_selected_name() == "")
	{
		ui_plain_only = FALSE;
		Sty_Note(sprintf("%s is switched off on the server.", map));
		return;
	}
	if (!ui_online_opt())
		Sty_Note("Online play is off: medals come only from lobby runs.");
	print(sprintf("^5story:^7 play %s (level %g of %s)\n", map, i + 1, sty_lid[L]));
	eventmax = FALSE;
	if (tokenize(bufstr_get(sty_lvinfo[L], i)) >= 13)
		eventmax = (stof(argv(12)) == 1);
	ui_launch_mode(eventmax);     // reads the name at once (ui_launch_mode's first line)
	ui_plain_only = FALSE;
};

void(vector pos, vector size, float L) Sty_Side =
{
	local float i, track, chap, timed, locked, med, ms, m, y, hb, hs, hg, hv, k;
	local string map, st, txt;
	local vector kinds, col;

	sui_style_box(pos, size, 9, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	i = sty_sel[L];
	if (i >= sty_nlv[L]) return;
	map = bufstr_get(sty_lvmap[L], i);
	y = pos_y + 12;
	if (map == "")
	{
		sui_fill([pos_x + 12, y], [size_x - 24, (size_x - 24) * 9 / 16], COL_ROW, 0.6, 0);
		y = y + (size_x - 24) * 9 / 16 + 12;
		sui_text([pos_x + 12, y], SZ_HEAD, "Coming soon", COL_DIM, 1, 0);
		return;
	}
	tokenize(bufstr_get(sty_lvinfo[L], i));
	track = stof(argv(0)); chap = stof(argv(1)); timed = stof(argv(2));
	hb = stof(argv(3)); hs = stof(argv(4)); hg = stof(argv(5));
	kinds = Sty_Kinds(L, i);
	locked = (chap >= Sty_OpenChapter(L));
	med = Sty_Medal(L, i);
	ms = Sty_Ms(L, i);
	Sty_Thumb([pos_x + 12, y], [size_x - 24, floor((size_x - 24) * 9 / 16)], Sty_MapRow(L, i));
	y = y + floor((size_x - 24) * 9 / 16) + 10;
	sui_text([pos_x + 12, y], SZ_ROW, ui_fit_text(track ? sprintf("%s  bonus %g", map, track) : map,
	         size_x - 24, SZ_ROW), COL_TEXT, 1, 0);
	y = y + 22;
	txt = Sty_When(L, i);
	sui_text([pos_x + 12, y], SZ_LABEL, sprintf("Level %g, chapter %g%s", i + 1, chap + 1,
	         txt == "" ? "" : strcat(", ", txt)), COL_DIM, 1, 0);
	y = y + 20;
	txt = Sty_Population(Sty_LivePlayers(L, map));
	if (txt != "")
	{
		sui_text([pos_x + 12, y], SZ_LABEL, txt, COL_DIM, 1, 0);
		y = y + 24;
	}
	for (m = 0; m < 3; m = m + 1)
	{
		txt = bufstr_get(sty_lvtxt[L], i * 3 + m);
		hv = (m == 0) ? hb : (m == 1) ? hs : hg;
		col = COL_DIM;
		k = Sty_K(kinds, m);
		if (k < 0) { txt = "Not set yet"; st = ""; }
		else if (med >= m + 1) { st = "Done"; col = SUI_THEME_GOOD; }
		else if (k > 0) { st = "Coming soon"; col = SUI_THEME_ACCENT2; }
		else st = sprintf("%g have it", hv);
		Sty_Pip([pos_x + 12, y + 1], m, k < 0 ? -1 : (med >= m + 1) ? 1 : 0, 1);
		sui_text([pos_x + 34, y], SZ_LABEL, ui_fit_text(txt, size_x - 46 - stringwidth(st, TRUE, SZ_LABEL) - 8,
		         SZ_LABEL), k < 0 ? COL_DIM : COL_TEXT, 1, 0);
		sui_text([pos_x + size_x - 12 - stringwidth(st, TRUE, SZ_LABEL), y], SZ_LABEL, st, col, 1, 0);
		y = y + 26;
	}
	y = y + 6;
	sui_roundbox([pos_x + 12, y], [size_x - 24, 40], 7, COL_ROW, 1);
	sui_text([pos_x + 22, y + 12], SZ_LABEL, strcmp(sty_who, sty_me) ? "Their best" : "Your best", COL_DIM, 1, 0);
	Font_Set(ui_font_mono);
	st = ms > 0 ? Time_MsString((int)ms) : "--";
	sui_text([pos_x + size_x - 22 - stringwidth(st, TRUE, SZ_ROW), y + 12], SZ_ROW, st, COL_TEXT, 1, 0);
	Font_Set(ui_font_ui);
	y = y + 52;
	if (!timed)
		y = y + ui_para([pos_x + 12, y], size_x - 24, SZ_LABEL, 20,
		                "No zones on the server yet, so no time can be set here.", SUI_THEME_WARN, TRUE);
	else if (locked)
		y = y + ui_para([pos_x + 12, y], size_x - 24, SZ_LABEL, 20,
		                sprintf("Opens at %g trophies.", stof(bufstr_get(sty_chbar[L], chap))), SUI_THEME_WARN, TRUE);
	else if (track)
		y = y + ui_para([pos_x + 12, y], size_x - 24, SZ_LABEL, 20,
		                sprintf("In the lobby, type !b %g to go to bonus %g.", track, track), COL_DIM, TRUE);
};

void(vector pos, vector size) Sty_Players =
{
	local float idx, n, t, open, g, s, b, x;
	local string who, av, nm, rid, col;
	local vector rp, rs;

	sui_style_box(pos, size, 9, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	// Another chip's ranking is not shown under this one while it loads (P856).
	if (sty_npl == 0 || sty_plfor != sty_plist)
	{
		sui_text(pos + '12 12 0', SZ_ROW, sty_kst == STY_ASK ? "Loading players..." :
		         sty_kst == STY_FAIL ? "The board did not answer. Try again shortly." :
		         "Nobody has a trophy here yet. Be the first.", COL_DIM, 1, 0);
		return;
	}
	sui_list_view_begin("sty_plist", pos + '1 1 0', size - '2 2 0', [size_x - 16, STY_PROW_H],
	                    sty_npl, sty_scr2, [0, 10]);
	rp = '0 0 0';
	for (idx = sui_list_item(rp); idx > -1; idx = sui_list_item(rp))
	{
		n = tokenize(bufstr_get(sty_pl, idx));
		if (n < 8) continue;
		who = argv(0); t = stof(argv(1)); open = stof(argv(2));
		g = stof(argv(3)); s = stof(argv(4)); b = stof(argv(5)); av = argv(6);
		nm = uri_unescape(argv(7));
		rs = [size_x - 16, STY_PROW_H];
		rid = strcat("sty_p", ftos(idx));
		sui_action_element(rp, rs, rid, sui_noop);
		if (sui_is_hovered(rid) || !strcmp(who, sty_who))
			sui_roundbox(rp + '1 1 0', rs - '2 2 0', 7, !strcmp(who, sty_who) ? COL_ROW_SEL : COL_ROW_HOVER, 1);
		if (sui_is_released(rid))
		{
			Sty_View(who);
			sty_tab = sty_plist;
		}
		Font_Set(ui_font_display);
		sui_text([rp_x + 36 - stringwidth(ftos(idx + 1), TRUE, SZ_HEAD), rp_y + 10], SZ_HEAD,
		         ftos(idx + 1), idx < 3 ? Sty_MedalCol(2 - idx) : COL_DIM, 1, 0);
		Font_Set(ui_font_ui);
		x = rp_x + 48;
		if (av != "-")
			MP_Draw([x, rp_y + 6], 32, av, 1);
		else
			sui_roundbox([x, rp_y + 6], '32 32 0', 6, COL_ROW, 1);
		col = !strcmp(who, sty_me) ? " ^2(you)" : "";
		sui_text([x + 44, rp_y + 13], SZ_ROW, strcat(ui_fit_text(nm, rs_x - 460, SZ_ROW), col), COL_TEXT, 1, 0);
		Font_Set(ui_font_display);
		sui_text([rp_x + rs_x - 400, rp_y + 10], SZ_HEAD, ftos(t), STY_GOLD, 1, 0);
		Font_Set(ui_font_ui);
		sui_text([rp_x + rs_x - 330, rp_y + 15], SZ_LABEL, sprintf("chapter %g", open), COL_DIM, 1, 0);
		Sty_Pip([rp_x + rs_x - 210, rp_y + 15], 2, 1, 1);
		sui_text([rp_x + rs_x - 190, rp_y + 14], SZ_LABEL, ftos(g), COL_TEXT, 1, 0);
		Sty_Pip([rp_x + rs_x - 150, rp_y + 15], 1, 1, 1);
		sui_text([rp_x + rs_x - 130, rp_y + 14], SZ_LABEL, ftos(s), COL_TEXT, 1, 0);
		Sty_Pip([rp_x + rs_x - 90, rp_y + 15], 0, 1, 1);
		sui_text([rp_x + rs_x - 70, rp_y + 14], SZ_LABEL, ftos(b), COL_TEXT, 1, 0);
	}
	sui_list_view_end();
};

void(vector screensize) screen_story =
{
	local vector size, pos, ls, rp, rs;
	local float L, side, y, by, idx, n, k, on, hot, x, w;
	local string rid, msg;

	Lob_Poll();
	Sty_Poll();
	if (sty_previewuntil > 0 && sty_previewdrawgeneration != sty_previewgeneration)
	{
		sty_previewdrawgeneration = sty_previewgeneration;
		Sty_Log(sprintf("story: preview draw generation %g at %g\n", sty_previewgeneration, gettime(0)));
	}
	size = [min(screensize_x - 32, 1100), min(screensize_y - 32, 808)];
	pos = [floor((screensize_x - size_x) * 0.5), floor((screensize_y - size_y) * 0.5)];
	sui_style_panel(pos, size, 12, 1);
	sui_text([pos_x + 16, pos_y + 12], SZ_HEAD, "story", COL_ACCENT, 1, 0);
	sui_push_frame(pos, size);

	// Tabs: the lists the board sent, then Players.
	x = 16;
	for (k = 0; k < STY_TABS; k = k + 1)
	{
		if (k < STY_LISTS && k >= sty_n) continue;
		rid = strcat("sty_tab", ftos(k));
		x = x + ui_chip([x, 48], rid, k < STY_LISTS ? sty_ltitle[k] : "Players", sty_tab == k) + 8;
		if (sui_is_released(rid)) sty_tab = k;
	}
	if (sty_tab == STY_TABS - 1)
	{
		x = x + 24;
		for (k = 0; k < sty_n; k = k + 1)
		{
			rid = strcat("sty_rank", ftos(k));
			x = x + ui_chip([x, 48], rid, strcat("rank by ", sty_ltitle[k]), sty_plist == k) + 8;
			if (sui_is_released(rid)) sty_plist = k;
		}
	}
	// Whose ladder is shown, and the way back to your own.
	if (sty_who != "" && strcmp(sty_who, sty_me))
	{
		msg = strcat("viewing ^7", sty_whoname == "" ? "a player" : sty_whoname);
		w = stringwidth(msg, TRUE, SZ_LABEL);
		if (ui_button("sty_mine", [size_x - 16 - 120, 46], [120, 30], sty_me != "" ? "My story" : "Close"))
			Sty_View(sty_me);
		sui_text([size_x - 16 - 120 - 16 - w, 53], SZ_LABEL, msg, SUI_THEME_ACCENT2, 1, 0);
	}
	else if (sty_previewuntil > 0)
		sui_text([size_x - 300, 53], SZ_LABEL, "Provisional progress - confirming...", SUI_THEME_WARN, 1, 0);
	else if (sty_note != "" && time - sty_notet < 8)
		sui_text([size_x - 16 - stringwidth(sty_note, TRUE, SZ_LABEL), 53], SZ_LABEL, sty_note, COL_DIM, 1, 0);
	else if (sty_me == "" && sty_mphase == 0)
		sui_text([size_x - 16 - stringwidth("Finish a run on a lobby and your medals start here.", TRUE, SZ_LABEL), 53],
		         SZ_LABEL, "Finish a run on a lobby and your medals start here.", COL_DIM, 1, 0);

	y = 92;
	by = size_y - 46;
	if (sty_tab == STY_TABS - 1)
	{
		Sty_Players([16, y], [size_x - 32, by - y - 12]);
	}
	else
	{
		L = sty_tab;
		Sty_Hero([16, y], size_x - 32);
		y = y + 88;
		side = (size_x >= 900) ? STY_SIDE_W : 0;
		ls = [size_x - 32 - (side ? side + 12 : 0), by - y - 12];
		sui_style_box([16, y], ls, 9, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
		if (sty_nrow[L] == 0)
			sui_text([28, y + 12], SZ_ROW, sty_lnote != "" ? sty_lnote :
			         (sty_lst == STY_ASK ? "Loading the ladder..." : "No ladder yet."), COL_DIM, 1, 0);
		else
		{
			if (L == 0)
				sui_list_view_begin("sty_list0", [17, y + 1], ls - '2 2 0', [ls_x - 16, STY_ROW_H],
				                    sty_nrow[L], sty_scr0, [0, 10]);
			else if (L == 1)
				sui_list_view_begin("sty_list1", [17, y + 1], ls - '2 2 0', [ls_x - 16, STY_ROW_H],
				                    sty_nrow[L], sty_scr1, [0, 10]);
			else
				sui_list_view_begin("sty_list2", [17, y + 1], ls - '2 2 0', [ls_x - 16, STY_ROW_H],
				                    sty_nrow[L], sty_scr3, [0, 10]);
			rp = '0 0 0';
			for (idx = sui_list_item(rp); idx > -1; idx = sui_list_item(rp))
			{
				rs = [ls_x - 16, STY_ROW_H];
				n = tokenize(bufstr_get(sty_rows[L], idx));
				k = stof(argv(1));
				if (argv(0) == "c")
				{
					Sty_ChapterRow(rp, rs, L, k, FALSE);
					continue;
				}
				rid = strcat("sty_r", ftos(L), "_", ftos(k));
				sui_action_element(rp, rs, rid, sui_noop);
				on = (k == sty_sel[L]);
				hot = sui_is_hovered(rid);
				if (sui_is_released(rid))
					sty_sel[L] = k;
				Sty_LevelRow(rp, rs, L, k, on, hot);
			}
			sui_list_view_end();
		}
		if (side)
			Sty_Side([size_x - 16 - side, y], [side, ls_y], L);
	}

	if (sty_tab < sty_n)
	{
		msg = Sty_Population(Sty_LivePlayers(sty_tab, ""));
		if (msg != "")
			sui_text([180, 18], SZ_LABEL, strcat(msg, " on this ladder's maps"), COL_DIM, 1, 0);
	}

	// The foot: back, the join strip, and Play for the selected level.
	if (ui_button("sty_back", [16, by], [100, 30], "back"))
		Sty_Esc();
	if (sty_tab < STY_LISTS && sty_n > sty_tab)
	{
		L = sty_tab;
		k = sty_sel[L];
		msg = (k < sty_nlv[L]) ? bufstr_get(sty_lvmap[L], k) : "";
		if (ui_join_busy())
			msg = "";
		if (msg != "" && !Sty_Locked(L, k) && (sty_who == "" || !strcmp(sty_who, sty_me)))
		if (ui_button("sty_play", [size_x - 16 - 160, by], [160, 30], "Play level", TRUE))
			Sty_Play(L, k);
	}
	ui_status_strip([140, by], size_x - 16 - 160 - 24 - 140);
	sui_pop_frame();
};

// `ui_story` opens the screen; `tab N`, `view <handle>`, `sel N` drive it and
// `probe` prints what it holds -- the harness's handles, and a player's too.
void(string what, string arg) Sty_Command =
{
	local float L, i, med, ms;
	local string map;

	if (what == "probe")
	{
		L = min(sty_tab, STY_LISTS - 1);
		i = sty_sel[L];
		map = (i < sty_nlv[L]) ? bufstr_get(sty_lvmap[L], i) : "";
		med = Sty_Medal(L, i);
		ms = Sty_Ms(L, i);
		print(sprintf("story_probe: tab %g lists %g rows %g/%g me %s who %s name %S\n",
		              sty_tab, sty_n, sty_nrow[0], sty_nrow[1], sty_me == "" ? "-" : sty_me,
		              sty_who == "" ? "-" : sty_who, sty_whoname));
		print(sprintf("story_probe: trophies %g/%g open %g/%g ", Sty_Total(0), Sty_Total(1), Sty_OpenChapter(0), Sty_OpenChapter(1)),
		      sprintf("sel %g map %s medal %g ms %g\n", i, map == "" ? "-" : map, med, ms));
		print(sprintf("story_probe: players %g of %g on %s locked %g\n", sty_npl, sty_pltotal,
		              sty_n ? sty_lid[sty_kfor] : "-", (i < sty_nlv[L]) ? Sty_Locked(L, i) : -1));
		print(sprintf("story_probe: provisional until %g official %g shown %g\n", sty_previewuntil, sty_t[L], Sty_Total(L)));
		print(sprintf("story_probe: local serial %g ack %g identity %S scope %g\n", sty_previewserial, cvar("ui_story_ack"), sty_previewwho, sty_previewscope));
		print(sprintf("story_probe: awaiting %g overflow %g GET-confirmed %g\n", sty_awaitcount, sty_awaitoverflow, sty_pack));
		print(sprintf("story_probe: pending %g retries %g next %g\n", sty_pending, sty_pretries, sty_pnext));
		print(sprintf("story_probe: live map %g ladder %g fresh %g\n", Sty_LivePlayers(L, map), Sty_LivePlayers(L, ""), Lob_Fresh()));
		print(sprintf("story_probe: list %s when %S\n", sty_lid[L], (i < sty_nlv[L]) ? Sty_When(L, i) : ""));
		return;
	}
	Sty_Open();
	m_open();
	if (what == "tab")
		sty_tab = bound(0, stof(arg), STY_TABS - 1);
	else if (what == "view")
		Sty_View(arg);
	else if (what == "sel")
	{
		L = min(sty_tab, STY_LISTS - 1);
		sty_sel[L] = bound(0, stof(arg) - 1, max(0, sty_nlv[L] - 1));
	}
};
