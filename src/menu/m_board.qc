/*
  m_board.qc -- ROADMAP 9: the selected map's leaderboard over the create
  screen, read from the directory's /api/board without connecting anywhere.

  Tabs KSF / Momentum / FTESurf (tiers ksf, momentum, ranked), main track,
  clean runs, MLB_PAGE rows a request and the next page as the list reaches its
  end, up to MLB_MAXROW.  Ids come from Lob_NextReq and replies through
  m_lobby.qc's one URI_Get_Callback (Mlb_Reply); an id abandoned by a tab
  switch, a close or the deadline is dropped and said so.  mlb_map and the four
  strbufs exist only while the panel is open.

  Compiled after m_main.qc (it draws with ui_button, ui_chip, ui_fit_text);
  m_main.qc calls in through the Mlb_* prototypes beside its SCREEN_* defines.
  Every request and reply prints a `board:` line; ui_board_test drives it.
*/

#define MLB_PAGE      100     // rows a request asks for; surfd caps at 200
#define MLB_MAXROW    1000    // rows held; the list stops there
#define MLB_AHEAD     10      // ask for the next page this many rows before the end
#define MLB_DEADLINE  10      // s; the engine's HTTP client has no timeout of its own
#define MLB_DROPS     8       // abandoned ids remembered, so a late reply is reported
#define MLB_ROW_H     24
#define MLB_RANK_R    52      // the rank column's right edge, in a row
#define MLB_NAME_X    68

#define MLB_T_KSF     0
#define MLB_T_MOM     1
#define MLB_T_OURS    2
#define MLB_NTABS     3

#define MLBS_IDLE     0
#define MLBS_FETCH    1       // the first page is out
#define MLBS_OK       2
#define MLBS_FAIL     3       // mlb_code says why (Mlb_Why)
#define MLBS_OFF      4       // the online terms are not accepted: nothing asked
#define MLBS_NODIR    5       // lobby_dir is empty

// Not in sh_json.qc: the menu is its one caller and csprogs is at its global
// limit.  Registered for this VM beside json_parse (pr_menu.c:2561, upstream
// dd03b69609), and the shipped exe carries the name.
int(int node) json_get_integer = #0:json_get_integer;
int(string value) Mlb_Stoi = #0:stoi;
string(int value) Mlb_Itos = #0:itos;

// A typed int: a bare 86400 makes `int / 86400` a float divide (DIV_IF).
const int MLB_DAYSECS = 86400;

float  mlb_open;
float mlb_track, mlb_leg, mlb_browsing;
string mlb_style, mlb_source;
string mlb_map;               // strzoned while open
float  mlb_tab, mlb_lasttab;
float  mlb_state, mlb_code;   // mlb_code: HTTP status, or Mlb_Why's own (<= 0, 900s)
float  mlb_req, mlb_sent;     // the first page in flight; 0 none
float  mlb_mreq, mlb_msent, mlb_mlim;  // a later page in flight, and its limit
float  mlb_mfail, mlb_mcode;  // a later page failed: the list's last row says why
float mlb_kreq, mlb_kdead, mlb_kafter;
string mlb_kstate;
float  mlb_n, mlb_more;       // rows held; the last page came back full
float  mlb_known, mlb_cksf, mlb_cmom, mlb_cours;   // `counts`, once a reply gave them
float  mlb_tzoff;             // s east of UTC when the panel opened
vector mlb_scroll;
float  mlb_going, mlb_goto;   // ui_board_test's scroll, held until the rows exist
float  mlb_offset;           // first held row's offset, including a profile seek
string mlb_focuswho;
int    mlb_focusms;          // exact milliseconds, never float32 display time
float  mlb_focusrank, mlb_focus; // picked identity/time, never display name
float  mlb_drop[MLB_DROPS];
float  mlb_dropi;
strbuf mlb_brank;
strbuf mlb_bname;
strbuf mlb_btime;
strbuf mlb_bdate;
strbuf mlb_bwho;               // Patch 789: the row's picture mark, "" none
float  mlb_anyav;               // some row has one: every name moves over

string(float t) Mlb_Tier =
{
	if (!strcmp(mlb_source, "all")) return "combined";
	if (t == MLB_T_KSF) return "ksf";
	if (t == MLB_T_MOM) return "momentum";
	return "ranked";
};

string(float t) Mlb_TabName =
{
	if (t == MLB_T_KSF) return "KSF";
	if (t == MLB_T_MOM) return "Momentum";
	return "WOS";
};

float(float t) Mlb_TabCount =
{
	if (t == MLB_T_KSF) return mlb_cksf;
	if (t == MLB_T_MOM) return mlb_cmom;
	return mlb_cours;
};

float() Mlb_BoardCount =
{
	if (!strcmp(mlb_source, "all")) return mlb_cksf + mlb_cmom + mlb_cours;
	return Mlb_TabCount(mlb_tab);
};

// "KSF  26", "FTESurf  none", or the bare name until a reply has counted.
string(float t) Mlb_TabLabel =
{
	local float c;

	if (!mlb_known)
		return Mlb_TabName(t);
	c = Mlb_TabCount(t);
	if (c <= 0)
		return strcat(Mlb_TabName(t), "  ", SUI_ESC_MUTED, "none");
	return sprintf("%s  %g", Mlb_TabName(t), c);
};

// -1 when the word names no tab.
float(string s) Mlb_TabOf =
{
	if (s == "ksf")      return MLB_T_KSF;
	if (s == "momentum") return MLB_T_MOM;
	if (s == "ranked" || s == "ftesurf") return MLB_T_OURS;
	return -1;
};

string() Mlb_Source =
{
	if (!strcmp(mlb_source, "all")) return "All games: World of Surf, Momentum Mod, KSF";
	if (mlb_tab == MLB_T_KSF) return "KSF (ksf.surf), Counter-Strike: Source -- times only";
	if (mlb_tab == MLB_T_MOM) return "Momentum Mod's own leaderboard, imported";
	return "ranked runs on World of Surf's public lobbies";
};

string() Mlb_EmptyLine =
{
	if (mlb_tab == MLB_T_KSF) return sprintf("KSF has no times on %s", mlb_map);
	if (mlb_tab == MLB_T_MOM) return sprintf("Momentum Mod has no times on %s", mlb_map);
	return sprintf("Nobody has set a time on %s on a World of Surf lobby yet", mlb_map);
};

/*
  One sentence per failure.  Beyond HTTP's: 0 is a transfer that ended with no
  status and no body, -1 a body that is not JSON, -2 no answer by
  MLB_DEADLINE, -3 uri_get refused to start, -4 / -5 a next page not asked
  for (terms, lobby_dir); 900-905 are the engine's own (http/iweb.h).
*/
string(float code) Mlb_Why =
{
	if (code == -5) return "lobby_dir is empty";
	if (code == -4) return "online play is off";
	if (code == -3) return "this build refused to send the request";
	if (code == -2) return sprintf("the leaderboard did not answer within %g s", MLB_DEADLINE);
	if (code == -1) return "the leaderboard sent something this build cannot read";
	if (code == 0)  return "could not reach the leaderboard";
	if (code == 429) return "the leaderboard is busy (too many requests) -- retry in a minute";
	if (code == 404) return "this leaderboard has no board service (404)";
	if (code == 900) return "could not reach the leaderboard: its name did not resolve";
	if (code == 901 || code == 902) return "could not reach the leaderboard: no connection";
	if (code == 903) return "the leaderboard hung up before answering";
	if (code == 904 || code == 905) return "could not reach the leaderboard: its certificate was refused";
	return sprintf("the leaderboard answered %g", code);
};

/*
  This board's "--" for a row with no time, and sh_time.qc's Time_MsString for
  everything else.  It used to hold its own integer split, written to dodge the
  float32 chain Time_TickString(ms, 0.001) ran; Patch 496 moved that split into
  sh_time.qc, so there is one formatter again and this keeps only the row rule.
*/
string(int ms) Mlb_MsString =
{
	if (ms <= 0)
		return "--";
	return Time_MsString(ms);
};

// Seconds east of UTC now, from the two clocks strftime can read.
float() Mlb_TzOff =
{
	local string l, u;
	local float d, off;

	l = strftime(TRUE, "%Y-%m-%d %H:%M");
	u = strftime(FALSE, "%Y-%m-%d %H:%M");
	off = (stof(substring(l, 11, 2)) - stof(substring(u, 11, 2))) * 3600
	    + (stof(substring(l, 14, 2)) - stof(substring(u, 14, 2))) * 60;
	d = strcmp(substring(l, 0, 10), substring(u, 0, 10));
	if (d > 0)
		off = off + 86400;
	else if (d < 0)
		off = off - 86400;
	return off;
};

/*
  `when` as a local yyyy-mm-dd, at the offset taken on open.  Split into days
  as integers: a float32 unix time sits on a 128 s grid.  Days to a date is
  Hinnant's civil_from_days, exact in float32 for every day to 2106 (modelled
  against Python's calendar: no misses).
*/
string(int w) Mlb_Date =
{
	local int o, d;
	local float z, era, doe, yoe, y, doy, mp, dd, m;

	if (w <= 0)
		return "--";
	o = mlb_tzoff;
	d = (w + o) / MLB_DAYSECS;
	z = d;
	z = z + 719468;
	era = floor(z / 146097);
	doe = z - era * 146097;
	yoe = floor((doe - floor(doe / 1460) + floor(doe / 36524) - floor(doe / 146096)) / 365);
	y = yoe + era * 400;
	doy = doe - (365 * yoe + floor(yoe / 4) - floor(yoe / 100));
	mp = floor((5 * doy + 2) / 153);
	dd = doy - floor((153 * mp + 2) / 5) + 1;
	if (mp < 10)
		m = mp + 3;
	else
		m = mp - 9;
	if (m <= 2)
		y = y + 1;
	return sprintf("%g-%02g-%02g", y, m, dd);
};

// Stop wanting a reply, and remember its id so its arrival is reported.
void(float id) Mlb_Abandon =
{
	if (!id)
		return;
	mlb_drop[mlb_dropi] = id;
	mlb_dropi = mlb_dropi + 1;
	if (mlb_dropi >= MLB_DROPS)
		mlb_dropi = 0;
};

/*
  Patch 781: FIRST PAGES BY QUERY, so a switch back to a tab draws at once, and
  the panel's other tabs asked one at a time once the first page is up.  Only
  the plain first page (no offset, no picked time) is kept; MLB_CFRESH s.
*/
#define MLB_CN      12
#define MLB_CFRESH  60
float  mlb_ckey, mlb_cbody;     // strbufs, by slot
float  mlb_ct[MLB_CN];          // time stored; 0 free
float  mlb_preq, mlb_psent, mlb_pt;
string mlb_pkey;

string(float t) Mlb_CKey =
{
	return sprintf("%s %g %g %s %s", strtolower(mlb_map), mlb_track, mlb_leg, Mlb_Tier(t), mlb_style);
};

float(string key) Mlb_CFind =
{
	local float i;

	if (!mlb_ckey)
		return -1;
	for (i = 0; i < MLB_CN; i = i + 1)
		if (mlb_ct[i])
		if (!strcmp(bufstr_get(mlb_ckey, i), key))
			return i;
	return -1;
};

void(string key, string body) Mlb_CPut =
{
	local float i, j;

	if (!mlb_ckey)
	{
		mlb_ckey = buf_create();
		mlb_cbody = buf_create();
	}
	i = Mlb_CFind(key);
	if (i < 0)
	{
		i = 0;
		for (j = 1; j < MLB_CN; j = j + 1)
			if (mlb_ct[i])
			if (!mlb_ct[j] || mlb_ct[j] < mlb_ct[i])
				i = j;
	}
	bufstr_set(mlb_ckey, i, key);
	bufstr_set(mlb_cbody, i, body);
	mlb_ct[i] = time;
};

void(float id, float code, string body, float append) Mlb_Page;

// The panel shows a plain first page: the cache may answer it.
float() Mlb_CPlain =
{
	return (!mlb_offset && mlb_focuswho == "" && mlb_source == "");
};

// Empty the list.  The strbufs are bounded by mlb_n, not by their size.
void() Mlb_ClearRows =
{
	Mlb_Abandon(mlb_req);
	Mlb_Abandon(mlb_mreq);
	Mlb_Abandon(mlb_kreq);
	mlb_req = mlb_mreq = mlb_kreq = 0;
	strunzone(mlb_kstate); mlb_kstate = "";
	mlb_n = mlb_more = 0;
	mlb_mfail = mlb_mcode = 0;
	mlb_state = MLBS_IDLE;
	mlb_code = 0;
	mlb_scroll = '0 0 0';
	mlb_focus = -1;
	mlb_going = FALSE;
};

// The first page (append FALSE) or the one after the rows held.  TRUE if sent.
float(float append) Mlb_Fetch =
{
	local string dir, url, tier;
	local float off, lim, id;

	if (!mlb_open)
		return FALSE;               // no map, and no buffers for a reply

	// Lob_JoinAsk's consent tier: this GET discloses the address as a join does.
	// A next page refused here fails alone; the rows held stay up.
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
	{
		print("^5board:^7 online play is off -- nothing asked\n");
		if (append)
		{
			mlb_mfail = TRUE;
			mlb_mcode = -4;
		}
		else
			mlb_state = MLBS_OFF;
		return FALSE;
	}
	dir = cvar_string("lobby_dir");
	if (dir == "")
	{
		print("^5board:^7 lobby_dir is empty -- nothing asked\n");
		if (append)
		{
			mlb_mfail = TRUE;
			mlb_mcode = -5;
		}
		else
			mlb_state = MLBS_NODIR;
		return FALSE;
	}

	if (!append)
	if (Mlb_CPlain())
	{
		id = Mlb_CFind(Mlb_CKey(mlb_tab));
		if (id >= 0)
		if (time - mlb_ct[id] < MLB_CFRESH)
		{
			print(sprintf("^5board:^7 %s from the cache, %g s old\n", Mlb_Tier(mlb_tab), rint(time - mlb_ct[id])));
			Mlb_Page(0, 0, bufstr_get(mlb_cbody, id), FALSE);
			return TRUE;
		}
	}

	off = mlb_offset;
	lim = MLB_PAGE;
	if (append)
	{
		off = mlb_offset + mlb_n;
		lim = min(MLB_PAGE, MLB_MAXROW - mlb_n);
	}
	tier = Mlb_Tier(mlb_tab);
	url = strcat(sprintf("%s/api/board?map=%s&track=%g&leg=%g&tier=%s&style=%s",
	              dir, uri_escape(mlb_map), mlb_track, mlb_leg, tier, uri_escape(mlb_style)),
	              sprintf("&limit=%g&offset=%g", lim, off));
	id = Lob_NextReq();
	if (!uri_get(url, id))
	{
		print(sprintf("^5board:^7 uri_get refused id %g (%s offset %g)\n", id, tier, off));
		if (append)
		{
			mlb_mfail = TRUE;
			mlb_mcode = -3;
		}
		else
		{
			mlb_state = MLBS_FAIL;
			mlb_code = -3;
		}
		return FALSE;
	}

	if (append)
	{
		mlb_mreq  = id;
		mlb_msent = time;
		mlb_mlim  = lim;
		mlb_mfail = FALSE;
		mlb_mcode = 0;
	}
	else
	{
		mlb_req   = id;
		mlb_sent  = time;
		mlb_state = MLBS_FETCH;
		mlb_code  = 0;
	}
	print(sprintf("^5board:^7 asked id %g: %s %s offset %g limit %g\n",
	              id, mlb_map, tier, off, lim));
	return TRUE;
};

// The next page, once the list nears its end.  TRUE if one went out.
float() Mlb_More =
{
	if (mlb_state != MLBS_OK || !mlb_more)
		return FALSE;
	if (mlb_mreq || mlb_mfail || mlb_n >= MLB_MAXROW)
		return FALSE;
	return Mlb_Fetch(TRUE);
};

// The retry buttons: a first page that did not land, or the next page.
void() Mlb_Retry =
{
	if (!mlb_open)
		return;
	if (mlb_state != MLBS_OK && mlb_state != MLBS_FETCH)
	{
		Mlb_ClearRows();        // a first page lands only on an empty list
		Mlb_Fetch(FALSE);
	}
	else if (mlb_mfail)
	{
		mlb_mfail = FALSE;
		Mlb_Fetch(TRUE);
	}
};

void(float t) Mlb_SetTab =
{
	if (!mlb_open) return;
	if (t == mlb_tab && mlb_source == "") return;
	strunzone(mlb_source);
	mlb_source = "";
	Mlb_ClearRows();
	mlb_offset = mlb_focusrank = 0;
	mlb_focusms = 0i;
	strunzone(mlb_focuswho); mlb_focuswho = "";
	mlb_tab = mlb_lasttab = t;
	print(sprintf("^5board:^7 tab %s\n", Mlb_Tier(t)));
	Mlb_Fetch(FALSE);
};

string(float i) Mlb_StyleKey = { return FS_BoardStyle(i, FS_BoardSegmented(mlb_style)); };

void(string style) Mlb_SetStyle =
{
	if (strcmp(style, FS_BoardStyle(FS_BoardDirection(style), FS_BoardSegmented(style)))) return;
	if (!strcmp(style, mlb_style)) return;
	Mlb_ClearRows();
	mlb_offset = mlb_focusrank = 0;
	mlb_focusms = 0i;
	strunzone(mlb_focuswho); mlb_focuswho = "";
	strunzone(mlb_style); mlb_style = strzone(style);
	Mlb_Fetch(FALSE);
};

void() Mlb_KsfMore =
{
	local string url;
	if (!mlb_open || cvar("rec_terms") < FS_TERMS_ONLINE) return;
	if (!strcmp(cvar_string("lobby_dir"), "") || !strcmp(mlb_style, "segmented")) return;
	if (time < mlb_kafter) return;
	if (mlb_kreq && time < mlb_kdead) return;
	mlb_kreq = Lob_NextReq(); mlb_kdead = time + MLB_DEADLINE; mlb_kafter = time + 10;
	url = sprintf("%s/api/board?ksfmore=1&map=%s&track=%g&leg=%g&style=%s",
	              cvar_string("lobby_dir"), uri_escape(mlb_map), mlb_track, mlb_leg, uri_escape(mlb_style));
	strunzone(mlb_kstate); mlb_kstate = strzone("asking");
	if (uri_get(url, mlb_kreq, "application/json", "{}")) return;
	mlb_kreq = 0;
	strunzone(mlb_kstate); mlb_kstate = strzone("failed");
};

float() Mlb_IsOpen = { return mlb_open; };

void(string why) Mlb_Close =
{
	if (!mlb_open)
		return;
	Mlb_ClearRows();
	buf_del(mlb_brank);
	buf_del(mlb_bname);
	buf_del(mlb_btime);
	buf_del(mlb_bdate);
	buf_del(mlb_bwho);
	print(sprintf("^5board:^7 closed %s (%s)\n", mlb_map, why));
	strunzone(mlb_style);
	strunzone(mlb_source);
	mlb_source = "";
	strunzone(mlb_map);
	mlb_map = "";
	strunzone(mlb_focuswho); mlb_focuswho = "";
	mlb_offset = mlb_focusrank = 0;
	mlb_focusms = 0i;
	mlb_open = FALSE;
};

// Open on `t`, or on the last tab used when t is -1.  Already open on this map:
// just the tab.
void(string mapname, float t) Mlb_Open =
{
	if (t < 0 || t >= MLB_NTABS)
		t = mlb_browsing ? mlb_lasttab : MLB_T_OURS;
	if (mlb_open)
	{
		if (!strcmp(mapname, mlb_map) && mlb_track == 0 && mlb_leg == 0 && mlb_style == "clean")
		{
			Mlb_SetTab(t);
			return;
		}
		Mlb_Close("another map");
	}

	if (!mlb_browsing)
	{
		mlb_track = mlb_leg = mlb_offset = mlb_focusrank = 0;
		mlb_focusms = 0i;
		strunzone(mlb_focuswho); mlb_focuswho = "";
		mlb_style = strzone("clean");
	}
	mlb_map   = strzone(mapname);
	mlb_brank = buf_create();
	mlb_bname = buf_create();
	mlb_btime = buf_create();
	mlb_bdate = buf_create();
	mlb_bwho  = buf_create();
	mlb_anyav = FALSE;
	mlb_open  = TRUE;
	mlb_tab   = mlb_lasttab = t;
	mlb_known = mlb_cksf = mlb_cmom = mlb_cours = 0;
	mlb_tzoff = Mlb_TzOff();
	Mlb_ClearRows();
	// The screen's hover and the search box's focus go: keys would type under it.
	sui_reset_actions();
	print(sprintf("^5board:^7 opened %s on %s; dates are local, %g min from UTC\n",
	              mlb_map, Mlb_Tier(t), mlb_tzoff / 60));
	Mlb_Fetch(FALSE);
};

void(float i, int row) Mlb_Row =
{
	local string s;

	bufstr_set(mlb_brank, i, ftos(json_get_float(json_find_object_child(row, "r"))));
	if (mlb_focuswho != "")
	if (!strcmp(substring(digest_hex("SHA256", json_get_string(json_find_object_child(row, "player"))), 0, strlen(mlb_focuswho)), mlb_focuswho))
	if (json_get_integer(json_find_object_child(row, "ms")) == mlb_focusms)
		mlb_focus = i;
	s = json_get_string(json_find_object_child(row, "name"));
	bufstr_set(mlb_bname, i, (s != "") ? s : "unknown");
	bufstr_set(mlb_btime, i, Mlb_MsString(json_get_integer(json_find_object_child(row, "ms"))));
	bufstr_set(mlb_bdate, i, Mlb_Date(json_get_integer(json_find_object_child(row, "when"))));
	// Patch 789: `av` is surfd saying the player has a picture (cl_online.qc's rule).
	bufstr_set(mlb_bwho, i, json_get_float(json_find_object_child(row, "av"))
	           ? FS_GuidId(json_get_string(json_find_object_child(row, "player"))) : "");
	if (bufstr_get(mlb_bwho, i) != "") mlb_anyav = TRUE;
};

void(string label, float i) Mlb_PrintRow =
{
	print(sprintf("^5board:^7   %s #%s %S %s %s\n", label, bufstr_get(mlb_brank, i),
	              bufstr_get(mlb_bname, i), bufstr_get(mlb_btime, i),
	              bufstr_get(mlb_bdate, i)));
};

void(float id, float code, float append) Mlb_Fail =
{
	if (append)
	{
		mlb_mfail = TRUE;
		mlb_mcode = code;
	}
	else
	{
		mlb_state = MLBS_FAIL;
		mlb_code  = code;
	}
	print(sprintf("^5board:^7 failed id %g (%s): code %g -- %s\n", id,
	              append ? "next page" : "first page", code, Mlb_Why(code)));
};

// One reply to the first page or the next.  Rows land only where they continue
// the list (the reply's own offset); a page that does not is dropped.
void(float id, float code, string body, float append) Mlb_Page =
{
	local int root, rows, cnt;
	local float n, i, off, lim, got, imp, com;
	local string tier;

	if (code)
	{
		Mlb_Fail(id, code, append);
		return;
	}
	// A transfer that failed without a status arrives as 0 with no body.
	if (body == "")
	{
		Mlb_Fail(id, 0, append);
		return;
	}
	root = json_parse(body);
	if (!root)
	{
		Mlb_Fail(id, -1, append);
		return;
	}

	if (strcasecmp(json_get_string(json_find_object_child(root, "map")), mlb_map) ||
	    strcmp(json_get_string(json_find_object_child(root, "tier")), Mlb_Tier(mlb_tab)) ||
	    strcmp(json_get_string(json_find_object_child(root, "style")), mlb_style) ||
	    json_get_float(json_find_object_child(root, "track")) != mlb_track ||
	    json_get_float(json_find_object_child(root, "leg")) != mlb_leg)
	{ json_free(root); Mlb_Fail(id, -1, append); return; }
	cnt = json_find_object_child(root, "counts");
	mlb_cksf  = json_get_float(json_find_object_child(cnt, "ksf"));
	mlb_cmom  = json_get_float(json_find_object_child(cnt, "momentum"));
	mlb_cours = json_get_float(json_find_object_child(cnt, "ranked"));
	imp = json_get_float(json_find_object_child(cnt, "imported"));
	com = json_get_float(json_find_object_child(cnt, "community"));
	mlb_known = TRUE;

	tier = json_get_string(json_find_object_child(root, "tier"));
	off  = json_get_float(json_find_object_child(root, "offset"));
	rows = json_find_object_child(root, "rows");
	got  = json_get_length(rows);
	lim  = append ? mlb_mlim : MLB_PAGE;

	if (off != mlb_offset + mlb_n)
	{
		json_free(root);
		print(sprintf("^5board:^7 reply id %g: %s offset %g, but %g rows are held -- page dropped\n",
		              id, tier, off, mlb_n));
		Mlb_Fail(id, -1, append);
		return;
	}

	n = got;
	if (n > lim)
		n = lim;
	if (n > MLB_MAXROW - mlb_n)
		n = MLB_MAXROW - mlb_n;
	for (i = 0; i < n; i = i + 1)
		Mlb_Row(mlb_n + i, json_get_child_at_index(rows, i));
	json_free(root);

	// A full page: the server may hold more, even at the cap (the tail says so).
	mlb_n = mlb_n + n;
	mlb_more = (n >= lim);
	if (!append)
	{
		mlb_state = MLBS_OK;
		mlb_code  = 0;
		if (mlb_focus >= 0)
		{
			mlb_scroll_y = max(0, mlb_focus - 4) * MLB_ROW_H;
			print(sprintf("^5board:^7 profile time at #%s (%s ms)\n", bufstr_get(mlb_brank, mlb_focus), Mlb_Itos(mlb_focusms)));
		}
		else if (mlb_focuswho != "")
			print("^3board:^7 selected time changed or is no longer on this page; showing nearby ranks\n");
	}

	print(sprintf("^5board:^7 reply id %g: %s offset %g rows %g -- held %g, more %g\n",
	              id, tier, off, got, mlb_n, mlb_more));
	print(sprintf("^5board:^7   counts ksf %g momentum %g ranked %g (imported %g, community %g)\n",
	              mlb_cksf, mlb_cmom, mlb_cours, imp, com));
	if (n > 0)
	{
		Mlb_PrintRow("first", mlb_n - n);
		Mlb_PrintRow("last ", mlb_n - 1);
	}
};

/*
  From m_lobby.qc's URI_Get_Callback, after the join's test and before the
  poll's.  TRUE when the id was one of ours, live or abandoned.
*/
float(float reqid, float code, string body) Mlb_Reply =
{
	local float k;
	local int root;

	if (!reqid)
		return FALSE;
	if (mlb_kreq)
	if (reqid == mlb_kreq)
	{
		mlb_kreq = 0;
		strunzone(mlb_kstate); mlb_kstate = strzone("failed");
		if (code == 0 || code == 202)
		{
			root = json_parse(body);
			if (root >= 0)
			{
				strunzone(mlb_kstate);
				mlb_kstate = strzone(substring(json_get_string(json_find_object_child(root, "state")), 0, 32));
				json_free(root);
			}
		}
		print(sprintf("^5board:^7 KSF top-up %s (code %g); refresh after the background crawl\n", mlb_kstate, code));
		return TRUE;
	}
	if (mlb_req)
	if (reqid == mlb_req)
	{
		mlb_req = 0;
		Mlb_Page(reqid, code, body, FALSE);
		if (!code)
		if (mlb_state == MLBS_OK)
		if (Mlb_CPlain())
			Mlb_CPut(Mlb_CKey(mlb_tab), body);
		return TRUE;
	}
	if (mlb_preq)
	if (reqid == mlb_preq)
	{
		mlb_preq = 0;
		if (!code)
		if (strlen(body) < 1048576)
		{
			root = json_parse(body);
			if (root)
			{
				if (json_find_object_child(root, "rows"))
				if (!strcmp(mlb_pkey, sprintf("%s %g %g %s %s", strtolower(json_get_string(json_find_object_child(root, "map"))),
				    json_get_float(json_find_object_child(root, "track")), json_get_float(json_find_object_child(root, "leg")),
				    json_get_string(json_find_object_child(root, "tier")), json_get_string(json_find_object_child(root, "style")))))
					Mlb_CPut(mlb_pkey, body);
				json_free(root);
			}
		}
		return TRUE;
	}
	if (mlb_mreq)
	if (reqid == mlb_mreq)
	{
		mlb_mreq = 0;
		Mlb_Page(reqid, code, body, TRUE);
		return TRUE;
	}
	for (k = 0; k < MLB_DROPS; k = k + 1)
		if (mlb_drop[k] == reqid)
		{
			mlb_drop[k] = 0;
			print(sprintf("^5board:^7 dropped the reply to id %g (code %g): its tab or panel is gone\n",
			              reqid, code));
			return TRUE;
		}
	return FALSE;
};

// Called even without menu focus: consume browse data and expire pending replies.
// Once the first page is up: one other tab's first page, asked ahead (Mlb_Poll).
void() Mlb_Ahead =
{
	local float t, i;
	local string url, key;

	if (mlb_preq)
	{
		if (time - mlb_psent > MLB_DEADLINE)
		{
			Mlb_Abandon(mlb_preq);
			mlb_preq = 0;
		}
		return;
	}
	if (mlb_state != MLBS_OK || !Mlb_CPlain() || strcmp(mlb_style, "clean"))
		return;
	if (time < mlb_pt || cvar("rec_terms") < FS_TERMS_ONLINE || cvar_string("lobby_dir") == "")
		return;
	for (t = 0; t < MLB_NTABS; t = t + 1)
	{
		if (t == mlb_tab)
			continue;
		key = Mlb_CKey(t);
		i = Mlb_CFind(key);
		if (i >= 0)
		if (time - mlb_ct[i] < MLB_CFRESH)
			continue;
		url = strcat(sprintf("%s/api/board?map=%s&track=%g&leg=%g&tier=%s&style=%s",
		              cvar_string("lobby_dir"), uri_escape(mlb_map), mlb_track, mlb_leg, Mlb_Tier(t), uri_escape(mlb_style)),
		              sprintf("&limit=%g&offset=0", MLB_PAGE));
		mlb_preq = Lob_NextReq();
		mlb_psent = time;
		mlb_pt = time + 0.4;
		if (mlb_pkey != "") strunzone(mlb_pkey);
		mlb_pkey = strzone(key);
		if (!uri_get(url, mlb_preq))
		{
			mlb_preq = 0;
			mlb_pt = time + 30;
		}
		return;
	}
};

void() Mlb_PollRequest;
void() Mlb_Poll =
{
	local float id;

	Mlb_PollRequest();
	if (mlb_open)
		Mlb_Ahead();

	if (mlb_req)
	if (time - mlb_sent > MLB_DEADLINE)
	{
		id = mlb_req;
		Mlb_Abandon(id);
		mlb_req = 0;
		Mlb_Fail(id, -2, FALSE);
	}
	if (mlb_mreq)
	if (time - mlb_msent > MLB_DEADLINE)
	{
		id = mlb_mreq;
		Mlb_Abandon(id);
		mlb_mreq = 0;
		Mlb_Fail(id, -2, TRUE);
	}
};

// The podium wears the theme's butter, silver and peach.
vector(float r) Mlb_RankCol =
{
	if (r == 1) return SUI_THEME_WARN;
	if (r == 2) return '0.78 0.80 0.88';
	if (r == 3) return SUI_THEME_FOCUS;
	return SUI_THEME_MUTED;
};

void(vector rp, float i, float rw, float tr, float dr, float nw) Mlb_DrawRow =
{
	local float ty;
	local string s;

	if (i == mlb_focus)
		sui_fill(rp, [rw, MLB_ROW_H], SUI_THEME_SELECTED, 0.85, 0);
	else if (i & 1)
		sui_fill(rp, [rw, MLB_ROW_H], COL_ROW, 0.6, 0);
	ty = rp_y + (MLB_ROW_H - SZ_LABEL_H) * 0.5;

	Font_Set(ui_font_mono);
	s = bufstr_get(mlb_brank, i);
	sui_text([rp_x + MLB_RANK_R - stringwidth(s, TRUE, SZ_ROW), ty], SZ_ROW, s,
	         Mlb_RankCol(stof(s)), 1, 0);
	s = bufstr_get(mlb_btime, i);
	sui_text([rp_x + tr - stringwidth(s, TRUE, SZ_ROW), ty], SZ_ROW, s, COL_TEXT, 1, 0);
	s = bufstr_get(mlb_bdate, i);
	sui_text([rp_x + dr - stringwidth(s, TRUE, SZ_ROW), ty], SZ_ROW, s, COL_DIM, 1, 0);
	Font_Set(ui_font_ui);

	s = bufstr_get(mlb_bwho, i);
	if (mlb_anyav)
	{
		if (s != "")
		if (!MP_Draw([rp_x + MLB_NAME_X, rp_y + 2], MLB_ROW_H - 4, s, 1))
			sui_roundbox([rp_x + MLB_NAME_X, rp_y + 2], [MLB_ROW_H - 4, MLB_ROW_H - 4], 4, SUI_THEME_CHIP, 1);
		sui_text([rp_x + MLB_NAME_X + MLB_ROW_H, ty], SZ_ROW,
		         ui_fit_text(bufstr_get(mlb_bname, i), nw - MLB_ROW_H, SZ_ROW), COL_TEXT, 1, 0);
	}
	else
		sui_text([rp_x + MLB_NAME_X, ty], SZ_ROW,
		         ui_fit_text(bufstr_get(mlb_bname, i), nw, SZ_ROW), COL_TEXT, 1, 0);
};

// The row after the last one held: what comes next, or why nothing does.
void(vector rp, float rw) Mlb_DrawTail =
{
	local float ty;
	local vector tp;

	ty = rp_y + (MLB_ROW_H - SZ_LABEL_H) * 0.5;
	tp = [rp_x + MLB_NAME_X, ty];
	if (mlb_mfail)
	{
		sui_text(tp, SZ_ROW,
		         ui_fit_text(strcat("could not load more: ", Mlb_Why(mlb_mcode)),
		                     rw - MLB_NAME_X - 100, SZ_ROW), COL_FAIL, 1, 0);
		if (ui_button("mlb_retry2", [rp_x + rw - 88, rp_y + 1], [80, MLB_ROW_H - 2], "retry"))
			Mlb_Retry();
	}
	else if (mlb_mreq || (mlb_more && mlb_n < MLB_MAXROW))
		sui_text(tp, SZ_ROW, "loading...", COL_DIM, 1, 0);
	else if (mlb_more && Mlb_BoardCount() > mlb_n)
		sui_text(tp, SZ_ROW, sprintf("the first %g of %g -- the list stops there",
		                             mlb_n, Mlb_BoardCount()), COL_DIM, 1, 0);
	else
		sui_text(tp, SZ_ROW, "end of the list", COL_DIM, 1, 0);
};

// Everything but a list: off, unset, failed, asking, or a board with no times.
void(vector p, float w) Mlb_DrawBody =
{
	if (mlb_state == MLBS_OFF)
	{
		sui_text(p, SZ_LABEL, "Online play is off", COL_TEXT, 1, 0);
		sui_text(p + '0 24 0', SZ_LABEL,
		         ui_fit_text(strcat(SUI_ESC_MUTED, "leaderboards come from a server, which needs the online terms"),
		                     w, SZ_LABEL), COL_DIM, 1, 0);
		if (ui_button("mlb_terms", p + '0 56 0', [150, 30], "read the terms"))
			menu_screen = SCREEN_TERMS;     // m_draw closes the panel off this screen
	}
	else if (mlb_state == MLBS_NODIR)
	{
		sui_text(p, SZ_LABEL, "No leaderboard server is set", COL_TEXT, 1, 0);
		sui_text(p + '0 24 0', SZ_LABEL,
		         ui_fit_text(strcat(SUI_ESC_MUTED, "lobby_dir is empty -- set it to a directory, e.g. https://play.proto.bar"),
		                     w, SZ_LABEL), COL_DIM, 1, 0);
	}
	else if (mlb_state == MLBS_FAIL)
	{
		sui_text(p, SZ_LABEL, ui_fit_text(Mlb_Why(mlb_code), w, SZ_LABEL), COL_FAIL, 1, 0);
		sui_text(p + '0 24 0', SZ_LABEL,
		         ui_fit_text(strcat(SUI_ESC_MUTED, "asked ", cvar_string("lobby_dir")), w, SZ_LABEL),
		         COL_DIM, 1, 0);
		if (ui_button("mlb_retry", p + '0 56 0', [84, 30], "retry"))
			Mlb_Retry();
	}
	else if (mlb_state == MLBS_OK)
		sui_text(p, SZ_LABEL, ui_fit_text(Mlb_EmptyLine(), w, SZ_LABEL), COL_TEXT, 1, 0);
	else
		sui_text(p, SZ_LABEL, "loading...", COL_DIM, 1, 0);
};

/*
  Over the create screen, from m_draw, which has already struck that screen's
  controls from sui's hit list, so the rows, wheel and keys under the panel are
  dead while it is up.
*/
void(vector screensize) Mlb_Draw =
{
	local vector p, sz, ls, rp;
	local float w, h, x, t, ly, rw, tr, dr, nw, idx, cw, closeit;
	local string s, id;

	if (!mlb_open)
		return;
	Mlb_Poll();

	w  = min(screensize_x - 64, 760);
	h  = min(screensize_y - 64, 680);
	p  = [floor((screensize_x - w) * 0.5), floor((screensize_y - h) * 0.5)];
	sz = [w, h];

	sui_fill('0 0 0', screensize, '0 0 0', 0.6, 0);
	sui_style_panel(p, sz, 12, 1);
	sui_push_frame(p, sz);

	// Closed at the end: the rows below still read the buffers a close frees.
	closeit = FALSE;
	if (ui_button("mlb_close", [w - 100, 12], [84, 30], "close"))
		closeit = TRUE;

	sui_text([16, 14], SZ_HEAD, ui_fit_text(mlb_map, w - 132, SZ_HEAD), COL_ACCENT, 1, 0);
	s = sprintf("%s / %s / %s", !strcmp(mlb_source, "all") ? "All games" : Mlb_TabName(mlb_tab),
	            mlb_track ? sprintf("bonus %g", mlb_track) : "main", FS_BoardStyleName(mlb_style));
	if (mlb_leg) s = strcat(s, sprintf(" / stage %g", mlb_leg));
	sui_text([16, 38], '12 12 0', ui_fit_text(s, w - 32, '12 12 0'), COL_DIM, 1, 0);

	x = 16;
	for (t = 0; t < MLB_NTABS; t = t + 1)
	{
		id = strcat("mlb_tab", ftos(t));
		x = x + ui_chip([x, 56], id, Mlb_TabLabel(t), t == mlb_tab) + CHIP_GAP;
		if (sui_is_released(id))
			Mlb_SetTab(t);
	}

	if (mlb_offset > 0)
	{
		if (ui_button("mlb_earlier", [w - 204, 56], [92, CHIP_H], "earlier")
		    || ui_button("mlb_top", [w - 100, 56], [84, CHIP_H], "top"))
		{
			mlb_offset = sui_is_released("mlb_top") ? 0 : max(0, mlb_offset - MLB_PAGE);
			strunzone(mlb_focuswho); mlb_focuswho = "";
			mlb_focusrank = 0;
			mlb_focusms = 0i;
			Mlb_ClearRows(); Mlb_Fetch(FALSE);
		}
	}

	x = 16;
	ly = 56 + CHIP_H + 8;
	for (t = 0; t < 4; t = t + 1)
	{
		id = strcat("mlb_style", ftos(t));
		s = FS_BoardDirectionName(t);
		cw = ui_chip_w(s);
		if (x + cw > w - 16 && x > 16) { x = 16; ly = ly + CHIP_H + 8; }
		x = x + ui_chip([x, ly], id, s, !strcmp(mlb_style, Mlb_StyleKey(t))) + CHIP_GAP;
		if (sui_is_released(id)) Mlb_SetStyle(Mlb_StyleKey(t));
	}
	x = x + 16;
	// Keep refresh's 84px target and a gap clear; wrap instead of stealing clicks.
	if (x + 150 + 8 > w - 100) { x = 16; ly = ly + CHIP_H + 8; }
	sui_action_element([x, ly], [150, CHIP_H], "mlb_segmented", sui_noop);
	sui_roundbox([x, ly + 2], [36, CHIP_H - 4], (CHIP_H - 4) * 0.5, SUI_THEME_WELL, 1);
	sui_roundbox([x + (FS_BoardSegmented(mlb_style) ? 18 : 2), ly + 4], [CHIP_H - 8, CHIP_H - 8],
	             (CHIP_H - 8) * 0.5, FS_BoardSegmented(mlb_style) ? COL_ACCENT : COL_DIM, 1);
	sui_text([x + 44, ly + 4], SZ_LABEL, "Segmented", COL_TEXT, 1, 0);
	if (sui_is_released("mlb_segmented"))
		Mlb_SetStyle(FS_BoardStyle(FS_BoardDirection(mlb_style), !FS_BoardSegmented(mlb_style)));
	if (ui_button("mlb_refresh", [w - 100, ly], [84, CHIP_H], "refresh"))
	{
		Mlb_ClearRows(); Mlb_Fetch(FALSE);
	}

	// Columns, right-aligned numbers in the mono face: rank, player, time, date.
	ly = ly + CHIP_H + 30;
	ls = [w - 32, h - ly - 44];
	rw = ls_x - 14;
	Font_Set(ui_font_mono);
	dr = rw - 12;
	tr = dr - stringwidth("0000-00-00", TRUE, SZ_ROW) - 28;
	nw = tr - stringwidth("0:00:00.000", TRUE, SZ_ROW) - 24 - MLB_NAME_X;
	Font_Set(ui_font_ui);

	sui_text([17 + MLB_RANK_R - stringwidth("rank", TRUE, SZ_LABEL), ly - 22], SZ_LABEL,
	         "rank", COL_DIM, 1, 0);
	sui_text([17 + MLB_NAME_X, ly - 22], SZ_LABEL, "player", COL_DIM, 1, 0);
	sui_text([17 + tr - stringwidth("time", TRUE, SZ_LABEL), ly - 22], SZ_LABEL,
	         "time", COL_DIM, 1, 0);
	sui_text([17 + dr - stringwidth("date", TRUE, SZ_LABEL), ly - 22], SZ_LABEL,
	         "date", COL_DIM, 1, 0);

	sui_style_box([16, ly], ls, 9, SUI_THEME_WELL, SUI_THEME_EDGE, 1);

	if (mlb_state == MLBS_OK && mlb_n > 0)
	{
		if (mlb_going)
			mlb_scroll_y = mlb_goto * MLB_ROW_H;

		// One row past the rows held: loading, an error, or the end.
		sui_list_view_begin("mlb_list", [17, ly + 1], [ls_x - 2, ls_y - 2],
		                    [rw, MLB_ROW_H], mlb_n + 1, mlb_scroll, [0, 10]);
		rp = '0 0 0';
		for (idx = sui_list_item(rp); idx > -1; idx = sui_list_item(rp))
		{
			if (idx >= mlb_n)
				Mlb_DrawTail(rp, rw);
			else
				Mlb_DrawRow(rp, idx, rw, tr, dr, nw);
		}
		sui_list_view_end();

		if (floor((mlb_scroll_y + ls_y - 2) / MLB_ROW_H) + MLB_AHEAD >= mlb_n)
			Mlb_More();

		// ui_board_test's scroll ends where it was sent, or where the rows run out.
		if (mlb_going)
		if (mlb_scroll_y >= mlb_goto * MLB_ROW_H || mlb_mfail
		    || (!mlb_mreq && (!mlb_more || mlb_n >= MLB_MAXROW)))
		{
			mlb_going = FALSE;
			print(sprintf("^5board:^7 scrolled: top row %g of %g held\n",
			              floor(mlb_scroll_y / MLB_ROW_H), mlb_n));
		}
	}
	else
	{
		Mlb_DrawBody([32, ly + 16], ls_x - 32);
		if (mlb_going)
		if (mlb_state != MLBS_FETCH && mlb_state != MLBS_IDLE)
		{
			mlb_going = FALSE;
			print("^5board:^7 scrolled: no rows to scroll\n");
		}
	}

	sui_text([16, h - 30], SZ_LABEL, ui_fit_text(Mlb_Source(), w - 160, SZ_LABEL),
	         COL_DIM, 1, 0);
	if (mlb_state == MLBS_OK)
	{
		s = sprintf("%g of %g", mlb_n, Mlb_BoardCount());
		sui_text([w - 16 - stringwidth(s, TRUE, SZ_LABEL), h - 30], SZ_LABEL, s, COL_DIM, 1, 0);
	}

	sui_pop_frame();
	if (closeit)
		Mlb_Close("close button");
};

void() Mlb_Status =
{
	local string st;

	if (!mlb_open)
	{
		print("^5board:^7 closed\n");
		return;
	}
	st = "idle";
	if (mlb_state == MLBS_FETCH)      st = "asking";
	else if (mlb_state == MLBS_OK)    st = "ok";
	else if (mlb_state == MLBS_FAIL)  st = "failed";
	else if (mlb_state == MLBS_OFF)   st = "online play is off";
	else if (mlb_state == MLBS_NODIR) st = "no lobby_dir";
	print(sprintf("^5board:^7 open: %s tab %s style %s, %s (code %g)\n", mlb_map,
	              Mlb_Tier(mlb_tab), mlb_style, st, mlb_code));
	print(sprintf("^5board:^7   offset %g, top #%g, profile requested #%g, selected #%g\n",
	              mlb_offset, mlb_offset + floor(mlb_scroll_y / MLB_ROW_H) + 1, mlb_focusrank,
	              (mlb_focus >= 0) ? stof(bufstr_get(mlb_brank, mlb_focus)) : 0));
	print(sprintf("^5board:^7   held %g of %g, more %g; out: first id %g, next id %g; next failed %g (code %g)\n",
	              mlb_n, Mlb_BoardCount(), mlb_more, mlb_req, mlb_mreq, mlb_mfail, mlb_mcode));
	print(sprintf("^5board:^7   counts known %g: ksf %g momentum %g ranked %g; top row %g\n",
	              mlb_known, mlb_cksf, mlb_cmom, mlb_cours, floor(mlb_scroll_y / MLB_ROW_H)));
	print(sprintf("^5board:^7   pictures: rows have them %g; slots held %g, asked %g, from disk %g, fetched %g\n",
	              mlb_anyav, MP_Held(), mp_asked, mp_disk, mp_got));
	if (mlb_n > 0)
	{
		Mlb_PrintRow("first", 0);
		Mlb_PrintRow("last ", mlb_n - 1);
	}
};

void(float n) Mlb_Scroll =
{
	if (!mlb_open)
	{
		print("^5board:^7 not open\n");
		return;
	}
	mlb_goto  = max(0, floor(n));
	mlb_going = TRUE;
	print(sprintf("^5board:^7 scrolling to row %g (%g held)\n", mlb_goto, mlb_n));
};

/*
  ui_board_test <map> [ksf|momentum|ranked] [scroll <n>] -- the button's twin:
  the create screen with <map> picked and the panel open on that tab (default
  the last one used), its top row sent to n, loading pages on the way.  On an
  open panel: tab <t>, scroll <n>, retry, esc (the ESC key's step), close.
  Bare: the panel's state.
*/
void() Mlb_TestCommand =
{
	local string a, mapname;
	local float t, sc, k, i;

	a = argv(1);
	if (a == "")
	{
		Mlb_Status();
		return;
	}
	if (a == "close")
	{
		if (!mlb_open)
			print("^5board:^7 not open\n");
		Mlb_Close("ui_board_test");
		return;
	}
	if (a == "esc")
	{
		// The key's step exists only on the create screen (Menu_InputEvent).
		if (menu_screen != SCREEN_CREATE)
		{
			print("^5board:^7 esc: not on the create screen\n");
			return;
		}
		k = ui_create_esc();
		print(sprintf("^5board:^7 esc %s\n", (k == 1) ? "closed the leaderboard" :
		              (k == 2) ? "ended a join" : "left the create screen"));
		return;
	}
	if (a == "ksfmore")
	{
		Mlb_KsfMore();
		return;
	}
	if (a == "style")
	{
		if (mlb_open)
			Mlb_SetStyle(argv(2));
		return;
	}
	if (a == "segmented")
	{
		if (mlb_open)
			Mlb_SetStyle(FS_BoardStyle(FS_BoardDirection(mlb_style), stof(argv(2))));
		return;
	}
	if (a == "retry")
	{
		if (!mlb_open)
			print("^5board:^7 not open\n");
		Mlb_Retry();
		return;
	}
	if (a == "tab")
	{
		t = Mlb_TabOf(argv(2));
		if (t < 0 || !mlb_open)
			print("^5board:^7 ui_board_test tab <ksf|momentum|ranked>, on an open panel\n");
		else
			Mlb_SetTab(t);
		return;
	}
	if (a == "scroll")
	{
		Mlb_Scroll(stof(argv(2)));
		return;
	}

	// <map> [tab] [scroll <n>]: every word read before ui_create_open tokenizes.
	t  = -1;
	sc = -1;
	i  = 2;
	if (Mlb_TabOf(argv(i)) >= 0)
	{
		t = Mlb_TabOf(argv(i));
		i = i + 1;
	}
	if (argv(i) == "scroll")
		sc = stof(argv(i + 1));
	mapname = strzone(a);

	if (!menu_active)
		m_open();
	menu_screen = SCREEN_CREATE;
	ui_create_open();
	ui_refilter();
	k = ui_map_index(mapname);
	if (k >= 0)
		ms_selected = k;
	print(sprintf("^5board:^7 ui_board_test %s: %s\n", mapname, (k >= 0)
	              ? "picked in the list" : "not in this install's list (the board does not need it)"));
	Mlb_Open(mapname, t);
	if (sc >= 0)
		Mlb_Scroll(sc);
	strunzone(mapname);
};

// Untrusted browse data never becomes a console command or launch request.
float(string value, float limit) Mlb_ScopeNumber =
{
	local float i, c;
	if (value == "" || strlen(value) > 3) return FALSE;
	for (i = 0; i < strlen(value); i = i + 1)
	{
		c = str2chr(value, i);
		if (c < 48 || c > 57) return FALSE;
	}
	return stof(value) <= limit;
};
// Canonical decimal digits for the lexical bound check before atoi-based stoi.
string(string value) Mlb_Decimal =
{
	while (strlen(value) > 1 && str2chr(value, 0) == 48)
		value = substring(value, 1, -1);
	return value;
};
float(string value, int limit) Mlb_FocusNumber =
{
	local float i, c;
	local string bound;
	if (value == "" || strlen(value) > 10) return FALSE;
	for (i = 0; i < strlen(value); i = i + 1)
	{
		c = str2chr(value, i);
		if (c < 48 || c > 57) return FALSE;
	}
	// Bound the decimal before stoi: overflow must not wrap into a valid int.
	value = Mlb_Decimal(value);
	bound = Mlb_Itos(limit);
	if (strlen(value) > strlen(bound)) return FALSE;
	if (strlen(value) == strlen(bound))
	if (strcmp(value, bound) > 0) return FALSE;
	return Mlb_Stoi(value) > 0i;
};
float(string map, string source, string track, string leg, string style, string rank, string who, string time_ms) Mlb_Browse =
{
	local float i, c, t, tr, lg, allsource, off, pickedrank;
	local int pickedms;
	local string savedmap, savedstyle, savedwho;
	if (map == "" || strlen(map) > 64) return FALSE;
	for (i = 0; i < strlen(map); i = i + 1)
	{
		c = str2chr(map, i);
		if (!(c >= 48 && c <= 57) && !(c >= 65 && c <= 90) && !(c >= 97 && c <= 122) && c != 95 && c != 45) return FALSE;
	}
	if (strcmp(source, "ranked") && strcmp(source, "momentum") && strcmp(source, "ksf") && strcmp(source, "all")) return FALSE;
	if (strcmp(style, "clean") && strcmp(style, "segmented") && strcmp(style, "sw")
	    && strcmp(style, "hsw") && strcmp(style, "bw")) return FALSE;
	if (!strcmp(style, "sw") || !strcmp(style, "hsw") || !strcmp(style, "bw"))
	if (strcmp(source, "ksf")) return FALSE;
	if (!Mlb_ScopeNumber(track, 64) || !Mlb_ScopeNumber(leg, 256)) return FALSE;
	allsource = !strcmp(source, "all");
	t = allsource ? MLB_T_OURS : Mlb_TabOf(source);
	tr = stof(track); lg = stof(leg);
	off = pickedrank = 0;
	pickedms = 0i;
	if (who != "" || rank != "" || time_ms != "")
	{
		if ((strlen(who) != 8 && strlen(who) != 12) || !Mlb_FocusNumber(rank, 10000000i) || !Mlb_FocusNumber(time_ms, 2147483647i)) return FALSE;
		for (i = 0; i < strlen(who); i = i + 1)
		{
			c = str2chr(who, i);
			if (!(c >= 48 && c <= 57) && !(c >= 97 && c <= 102)) return FALSE;
		}
		pickedrank = stof(rank); pickedms = Mlb_Stoi(Mlb_Decimal(time_ms));
		off = max(0, pickedrank - 6);
	}
	savedmap = strzone(map); savedstyle = strzone(style); savedwho = strzone(who);
	Mlb_Close("browse");
	if (allsource) mlb_source = strzone("all");
	if (!menu_active) m_open();
	menu_screen = SCREEN_CREATE;
	ui_create_open();
	mlb_track = tr; mlb_leg = lg; mlb_style = strzone(savedstyle);
	mlb_offset = off; mlb_focusrank = pickedrank; mlb_focusms = pickedms;
	mlb_focuswho = strzone(savedwho);
	mlb_browsing = TRUE;
	Mlb_Open(savedmap, t);
	mlb_browsing = FALSE;
	strunzone(savedmap); strunzone(savedstyle); strunzone(savedwho);
	return TRUE;
};

void() Mlb_PollRequest =
{
	local string payload;
	local float i, c, valid, n;
	if (cvar_string("ui_board_request") == "") return;
	payload = strzone(cvar_string("ui_board_request"));
	cvar_set("ui_board_request", "");
	if (strlen(payload) > 128)
	{
		strunzone(payload);
		print("board: rejected browse request\n");
		return;
	}
	valid = TRUE;
	for (i = 0; i < strlen(payload); i = i + 1)
	{
		c = str2chr(payload, i);
		if (!(c >= 48 && c <= 57) && !(c >= 65 && c <= 90) && !(c >= 97 && c <= 122) && c != 95 && c != 45 && c != 32) valid = FALSE;
	}
	if (valid)
	{
		n = tokenize(payload);
		if (n == 5 || n == 8)
			valid = Mlb_Browse(argv(0), argv(1), argv(2), argv(3), argv(4), argv(5), argv(6), argv(7));
		else valid = FALSE;
	}
	if (!valid) print("board: rejected browse request\n");
	strunzone(payload);
};

// Trusted manual command shares validation and browse behavior, not token replay.
void() Mlb_Command =
{
	if (argv(6) != "") return;
	Mlb_Browse(argv(1), argv(2), argv(3), argv(4), argv(5) == "" ? "clean" : argv(5), "", "", "");
};
