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

// A typed int: a bare 86400 makes `int / 86400` a float divide (DIV_IF).
const int MLB_DAYSECS = 86400;

float  mlb_open;
string mlb_map;               // strzoned while open
float  mlb_tab, mlb_lasttab;
float  mlb_state, mlb_code;   // mlb_code: HTTP status, or Mlb_Why's own (<= 0, 900s)
float  mlb_req, mlb_sent;     // the first page in flight; 0 none
float  mlb_mreq, mlb_msent, mlb_mlim;  // a later page in flight, and its limit
float  mlb_mfail, mlb_mcode;  // a later page failed: the list's last row says why
float  mlb_n, mlb_more;       // rows held; the last page came back full
float  mlb_known, mlb_cksf, mlb_cmom, mlb_cours;   // `counts`, once a reply gave them
float  mlb_tzoff;             // s east of UTC when the panel opened
vector mlb_scroll;
float  mlb_going, mlb_goto;   // ui_board_test's scroll, held until the rows exist
float  mlb_drop[MLB_DROPS];
float  mlb_dropi;
strbuf mlb_brank;
strbuf mlb_bname;
strbuf mlb_btime;
strbuf mlb_bdate;

string(float t) Mlb_Tier =
{
	if (t == MLB_T_KSF) return "ksf";
	if (t == MLB_T_MOM) return "momentum";
	return "ranked";
};

string(float t) Mlb_TabName =
{
	if (t == MLB_T_KSF) return "KSF";
	if (t == MLB_T_MOM) return "Momentum";
	return "FTESurf";
};

float(float t) Mlb_TabCount =
{
	if (t == MLB_T_KSF) return mlb_cksf;
	if (t == MLB_T_MOM) return mlb_cmom;
	return mlb_cours;
};

// "KSF  26", "FTESurf  none", or the bare name until a reply has counted.
string(float t) Mlb_TabLabel =
{
	local float c;

	if (!mlb_known)
		return Mlb_TabName(t);
	c = Mlb_TabCount(t);
	if (c <= 0)
		return strcat(Mlb_TabName(t), "  ^9none");
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
	if (mlb_tab == MLB_T_KSF) return "KSF (ksf.surf), Counter-Strike: Source -- times only";
	if (mlb_tab == MLB_T_MOM) return "Momentum Mod's own leaderboard, imported";
	return "ranked runs on FTESurf's public lobbies";
};

string() Mlb_EmptyLine =
{
	if (mlb_tab == MLB_T_KSF) return sprintf("KSF has no times on %s", mlb_map);
	if (mlb_tab == MLB_T_MOM) return sprintf("Momentum Mod has no times on %s", mlb_map);
	return sprintf("Nobody has set a time on %s on an FTESurf lobby yet", mlb_map);
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
  Whole milliseconds as Time_TickString's m:ss.mmm / h:mm:ss.mmm.  Not
  Time_TickString(ms, 0.001): in float32 that is 1-3 ms off on most values from
  4,096,003 ms (68 min) up (BACKLOG), and Momentum boards hold hours-long runs.
*/
string(int ms) Mlb_MsString =
{
	local int h, m, s;

	if (ms <= 0)
		return "--";
	h = ms / 3600000i;  ms = ms - h * 3600000i;
	m = ms / 60000i;    ms = ms - m * 60000i;
	s = ms / 1000i;     ms = ms - s * 1000i;
	if (h > 0)
		return sprintf("%g:%02g:%02g.%03g", (float)h, (float)m, (float)s, (float)ms);
	return sprintf("%g:%02g.%03g", (float)m, (float)s, (float)ms);
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

// Empty the list.  The strbufs are bounded by mlb_n, not by their size.
void() Mlb_ClearRows =
{
	Mlb_Abandon(mlb_req);
	Mlb_Abandon(mlb_mreq);
	mlb_req = mlb_mreq = 0;
	mlb_n = mlb_more = 0;
	mlb_mfail = mlb_mcode = 0;
	mlb_state = MLBS_IDLE;
	mlb_code = 0;
	mlb_scroll = '0 0 0';
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

	off = 0;
	lim = MLB_PAGE;
	if (append)
	{
		off = mlb_n;
		lim = min(MLB_PAGE, MLB_MAXROW - mlb_n);
	}
	tier = Mlb_Tier(mlb_tab);
	url = sprintf("%s/api/board?map=%s&track=0&leg=0&tier=%s&style=clean&limit=%g&offset=%g",
	              dir, uri_escape(mlb_map), tier, lim, off);
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
	if (!mlb_open || t == mlb_tab)
		return;
	Mlb_ClearRows();
	mlb_tab = mlb_lasttab = t;
	print(sprintf("^5board:^7 tab %s\n", Mlb_Tier(t)));
	Mlb_Fetch(FALSE);
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
	print(sprintf("^5board:^7 closed %s (%s)\n", mlb_map, why));
	strunzone(mlb_map);
	mlb_map = "";
	mlb_open = FALSE;
};

// Open on `t`, or on the last tab used when t is -1.  Already open on this map:
// just the tab.
void(string mapname, float t) Mlb_Open =
{
	if (t < 0 || t >= MLB_NTABS)
		t = mlb_lasttab;
	if (mlb_open)
	{
		if (!strcmp(mapname, mlb_map))
		{
			Mlb_SetTab(t);
			return;
		}
		Mlb_Close("another map");
	}

	mlb_map   = strzone(mapname);
	mlb_brank = buf_create();
	mlb_bname = buf_create();
	mlb_btime = buf_create();
	mlb_bdate = buf_create();
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
	s = json_get_string(json_find_object_child(row, "name"));
	bufstr_set(mlb_bname, i, (s != "") ? s : "unknown");
	bufstr_set(mlb_btime, i, Mlb_MsString(json_get_integer(json_find_object_child(row, "ms"))));
	bufstr_set(mlb_bdate, i, Mlb_Date(json_get_integer(json_find_object_child(row, "when"))));
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

	if (off != mlb_n)
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

	if (!reqid)
		return FALSE;
	if (mlb_req)
	if (reqid == mlb_req)
	{
		mlb_req = 0;
		Mlb_Page(reqid, code, body, FALSE);
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

// The deadline nothing under us has.  A late reply is then dropped by id.
void() Mlb_Poll =
{
	local float id;

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

void(vector rp, float i, float rw, float tr, float dr, float nw) Mlb_DrawRow =
{
	local float ty;
	local string s;

	if (i & 1)
		sui_fill(rp, [rw, MLB_ROW_H], COL_ROW, 0.6, 0);
	ty = rp_y + (MLB_ROW_H - SZ_LABEL_H) * 0.5;

	Font_Set(ui_font_mono);
	s = bufstr_get(mlb_brank, i);
	sui_text([rp_x + MLB_RANK_R - stringwidth(s, TRUE, SZ_ROW), ty], SZ_ROW, s, COL_DIM, 1, 0);
	s = bufstr_get(mlb_btime, i);
	sui_text([rp_x + tr - stringwidth(s, TRUE, SZ_ROW), ty], SZ_ROW, s, COL_TEXT, 1, 0);
	s = bufstr_get(mlb_bdate, i);
	sui_text([rp_x + dr - stringwidth(s, TRUE, SZ_ROW), ty], SZ_ROW, s, COL_DIM, 1, 0);
	Font_Set(ui_font_ui);

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
	else if (mlb_more && Mlb_TabCount(mlb_tab) > mlb_n)
		sui_text(tp, SZ_ROW, sprintf("the first %g of %g -- the list stops there",
		                             mlb_n, Mlb_TabCount(mlb_tab)), COL_DIM, 1, 0);
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
		         ui_fit_text("^9leaderboards come from a server, which needs the online terms",
		                     w, SZ_LABEL), COL_DIM, 1, 0);
		if (ui_button("mlb_terms", p + '0 56 0', [150, 30], "read the terms"))
			menu_screen = SCREEN_TERMS;     // m_draw closes the panel off this screen
	}
	else if (mlb_state == MLBS_NODIR)
	{
		sui_text(p, SZ_LABEL, "No leaderboard server is set", COL_TEXT, 1, 0);
		sui_text(p + '0 24 0', SZ_LABEL,
		         ui_fit_text("^9lobby_dir is empty -- set it to a directory, e.g. https://play.proto.bar",
		                     w, SZ_LABEL), COL_DIM, 1, 0);
	}
	else if (mlb_state == MLBS_FAIL)
	{
		sui_text(p, SZ_LABEL, ui_fit_text(Mlb_Why(mlb_code), w, SZ_LABEL), COL_FAIL, 1, 0);
		sui_text(p + '0 24 0', SZ_LABEL,
		         ui_fit_text(strcat("^9asked ", cvar_string("lobby_dir")), w, SZ_LABEL),
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
	sui_fill(p, sz, COL_PANEL, 1, 0);
	sui_border_box(p, sz, 1, COL_BORDER, 1, 0);
	sui_push_frame(p, sz);

	// Closed at the end: the rows below still read the buffers a close frees.
	closeit = FALSE;
	if (ui_button("mlb_close", [w - 100, 12], [84, 30], "close"))
		closeit = TRUE;

	cw = stringwidth("  main track", TRUE, SZ_HEAD);
	s  = ui_fit_text(mlb_map, w - 132 - cw, SZ_HEAD);
	sui_text([16, 14], SZ_HEAD, s, COL_ACCENT, 1, 0);
	sui_text([16 + stringwidth(s, TRUE, SZ_HEAD), 14], SZ_HEAD, "  main track", COL_DIM, 1, 0);

	x = 16;
	for (t = 0; t < MLB_NTABS; t = t + 1)
	{
		id = strcat("mlb_tab", ftos(t));
		x = x + ui_chip([x, 56], id, Mlb_TabLabel(t), t == mlb_tab) + CHIP_GAP;
		if (sui_is_released(id))
			Mlb_SetTab(t);
	}

	// Columns, right-aligned numbers in the mono face: rank, player, time, date.
	ly = 56 + CHIP_H + 30;
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

	sui_fill([16, ly], ls, '0.03 0.03 0.04', 1, 0);
	sui_border_box([16, ly], ls, 1, COL_ACCENT, 1, 0);

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
		s = sprintf("%g of %g", mlb_n, Mlb_TabCount(mlb_tab));
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
	print(sprintf("^5board:^7 open: %s tab %s, %s (code %g)\n", mlb_map,
	              Mlb_Tier(mlb_tab), st, mlb_code));
	print(sprintf("^5board:^7   held %g of %g, more %g; out: first id %g, next id %g; next failed %g (code %g)\n",
	              mlb_n, Mlb_TabCount(mlb_tab), mlb_more, mlb_req, mlb_mreq, mlb_mfail, mlb_mcode));
	print(sprintf("^5board:^7   counts known %g: ksf %g momentum %g ranked %g; top row %g\n",
	              mlb_known, mlb_cksf, mlb_cmom, mlb_cours, floor(mlb_scroll_y / MLB_ROW_H)));
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
	if (a == "retry")
	{
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
