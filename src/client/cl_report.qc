/*
===========================================================================
  cl_report.qc -- P1391: the report panel (F3, `report`).

  A subject (typed, or one of the presets), a text body with a hint while it is
  empty, a screenshot taken the moment the panel was asked for, and details the
  player does not have to type (map, place, save cursor, timer, frame rate,
  settings, build). Send POSTs one JSON object to cl_report_url, surfd's
  /api/report (surfd/reports.py), which rate-limits and stores it; the owner reads
  reports on the admin site (/admin/reports).

      report                  toggle (F3)
      report status           state, fields and the screenshot as the panel holds them
      report subject <text>   set the subject     report body <text>   set the text
      report cat <id>         perf render bug map feature other
      report send             what the Send button does

  The fields take printable ASCII only, as the chat's do: the service stores what
  arrives and the admin page shows it.
===========================================================================
*/

#define RP_SUBJ_MAX  80
#define RP_BODY_MAX  4000
#define RP_SHOT_MAX  1468006        // 1.4 MiB: surfd takes 1.5 MiB decoded
#define RP_LINES     96             // wrapped body lines kept
#define RP_KN        8              // keys taken while open (their releases are the panel's)
#define RP_IDLE      0
#define RP_SENDING   1
#define RP_SENT      2
#define UIC_REPORT   8192           // cl_hud.qc's cursor register

string(void *data, int bytes) base64encode = #0:base64encode;   // pr_bgcmd.c; checkbuiltin-gated

float  rpo_open;                     // 0 closed, 1 the screenshot is being taken, 2 drawn
float  rpo_waitn;                    // frames left before the panel draws (the shot reads the backbuffer)
string rpo_shot;                     // gamedir path of this report's screenshot
float  rpo_shotok, rpo_shotuse, rpo_shotat, rpo_flushed;
string rpo_subj, rpo_body;
float  rpo_cat;                      // 0 none, else 1..RP_NCAT
float  rpo_focus;                    // 0 subject, 1 body
float  rpo_caret, rpo_scroll;
float  rpo_state, rpo_req, rpo_nextreq, rpo_closeat;
string rpo_status;
float  rpo_statusat, rpo_statusbad;
vector rpo_ms;
float  rpo_blink;
float  rpo_fps;                      // a running average of the real frame rate, kept while closed too
float  rpo_kd[RP_KN];
// The body as drawn: line starts and lengths into rpo_body, for the width it was wrapped at.
float  rpo_ln_s[RP_LINES], rpo_ln_l[RP_LINES];
float  rpo_ln_n, rpo_wrapw, rpo_wrapfs, rpo_wrapdirty;
vector rpo_bodyp, rpo_bodys, rpo_subjp, rpo_subjs;
float  rpo_lh, rpo_fs;

#define RP_NCAT 6
string(float c) Rp_CatId =
{
	if (c == 1) return "perf";
	if (c == 2) return "render";
	if (c == 3) return "bug";
	if (c == 4) return "map";
	if (c == 5) return "feature";
	if (c == 6) return "other";
	return "";
};
string(float c) Rp_CatLabel =
{
	if (c == 1) return "Poor performance";
	if (c == 2) return "Bad rendering";
	if (c == 3) return "Bug";
	if (c == 4) return "Map or zones";
	if (c == 5) return "Feature request";
	if (c == 6) return "Other";
	return "";
};

string(string s) Rp_Json =
{
	s = strreplace("\\", "\\\\", s);
	s = strreplace("\"", "\\\"", s);
	s = strreplace("\n", "\\n", s);
	s = strreplace("\t", " ", s);
	return strreplace("\r", "", s);
};

// Printable ASCII of a short server-supplied string (names, hostnames can carry Quake glyphs).
string(string s) Rp_Ascii =
{
	local float i, n, c;
	local string o;
	n = min(strlen(s), 128);
	o = "";
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (c >= 128) c = c - 128;  // Quake's high half is the low half drawn another colour
		if (c >= 32 && c <= 126)
			o = strcat(o, chr2str(c));
	}
	return o;
};

string(string k, string v) Rp_KV = { return sprintf("\"%s\":\"%s\"", k, Rp_Json(Rp_Ascii(v))); };

void(string s, float bad) Rp_Status =
{
	if (rpo_status != "") strunzone(rpo_status);
	rpo_status = strzone(s);
	rpo_statusat = cltime;
	rpo_statusbad = bad;
};

void(string s) Rp_SetSubj =
{
	if (rpo_subj != "") strunzone(rpo_subj);
	rpo_subj = strzone(substring(s, 0, RP_SUBJ_MAX));
};

void(string s) Rp_SetBody =
{
	if (rpo_body != "") strunzone(rpo_body);
	rpo_body = strzone(substring(s, 0, RP_BODY_MAX));
	rpo_wrapdirty = TRUE;
};

void() Report_RegisterCvars =
{
	registercommand("report");
	registercvar("cl_report_url", "https://play.proto.bar/api/report");
	rpo_shotuse = TRUE;
};

// Once a map: F3 opens it unless the player has bound F3 to something.
void() Report_Init =
{
	if (getkeybind(K_F3) == "")
		localcmd("bind f3 report\n");
};

/*
===========================================================================
  The details sent with every report.
===========================================================================
*/
string() Report_Meta =
{
	local string m, tst, n, cv;
	local float st, i, k;
	local vector o, a, v;

	o = pmove_org;
	a = input_angles;
	v = pmove_vel;
	st = getstatf(STAT_FS_TIMERSTATE);
	tst = "idle";
	if (st == TS_ARMED) tst = "in the start";
	else if (st == TS_RUNNING) tst = "running";
	else if (st == TS_FINISHED) tst = "finished";
	m = strcat("{", Rp_KV("map", serverkey("map")), ",", Rp_KV("server", PE_Local() ? "local game" : serverkey("hostname")));
	m = strcat(m, ",", Rp_KV("addr", PE_Local() ? "" : serverkey("ip")));
	m = strcat(m, ",", Rp_KV("origin", sprintf("%.1f %.1f %.1f", o_x, o_y, o_z)));
	m = strcat(m, ",", Rp_KV("angles", sprintf("%.1f %.1f", a_x, a_y)));
	m = strcat(m, ",", Rp_KV("velocity", sprintf("%.0f %.0f %.0f (%.0f u/s)", v_x, v_y, v_z, vlen([v_x, v_y, 0]))));
	m = strcat(m, ",", Rp_KV("timer", sprintf("%s, track %g stage %g, %.3f s", tst, getstatf(STAT_FS_TIMERTRACK),
	                                         getstatf(STAT_FS_TIMERSEG) + 1,
	                                         getstatf(STAT_FS_TIMERTICKS) * serverkeyfloat("pm_ticrate"))));
	m = strcat(m, ",", Rp_KV("save", sprintf("%g of %g (folder %g, ticks %g)", getstatf(STAT_FS_SAVEINDEX),
	                                        getstatf(STAT_FS_SAVECOUNT), getstatf(STAT_FS_SLCURID),
	                                        getstatf(STAT_FS_SAVETICKS))));
	m = strcat(m, ",", Rp_KV("fps", sprintf("%.0f", rpo_fps)));
	m = strcat(m, ",", Rp_KV("ping", sprintf("%s ms, loss %s%%", getplayerkeyvalue(player_localnum, "ping"),
	                                        getplayerkeyvalue(player_localnum, "pl"))));
	m = strcat(m, ",", Rp_KV("player", getplayerkeyvalue(player_localnum, "name")));
	m = strcat(m, ",", Rp_KV("ahash", getplayerkeyvalue(player_localnum, "*ahash")));
	m = strcat(m, ",", Rp_KV("build", sprintf("%s (engine %s)", cvar_string("update_version"),
	                                         getplayerkeyvalue(player_localnum, "*ver"))));
	m = strcat(m, ",", Rp_KV("csprogs", serverkey("*csprogs")));
	m = strcat(m, ",", Rp_KV("screen", sprintf("%gx%g fullscreen %g", cvar("vid_width"), cvar("vid_height"),
	                                          cvar("vid_fullscreen"))));
	m = strcat(m, ",", Rp_KV("utc", strftime(FALSE, "%Y-%m-%d %H:%M:%S")));
	// The settings people change to fix (or that cause) what they report.
	cv = "vid_renderer vid_vsync cl_maxfps r_renderscale vid_multisample r_reflectmultisample hl2_water "
	     "gl_texture_anisotropic_filtering gl_picmip r_bloom r_capturerate milk_quality r_christmas "
	     "hud_trail cl_netfps rate cl_sl_leadin";
	n = "";
	k = tokenize(cv);
	for (i = 0; i < k; i = i + 1)
		n = strcat(n, (i ? " " : ""), argv(i), "=", cvar_string(argv(i)));
	m = strcat(m, ",", sprintf("\"settings\":\"%s\"", Rp_Json(n)), "}");     // cvar values: ASCII, longer than Rp_Ascii keeps
	return m;
};

/*
===========================================================================
  Open, close, send.
===========================================================================
*/
float(float scanx, float down) Rp_Took =
{
	local float i, f;
	f = -1;
	for (i = 0; i < RP_KN; i = i + 1)
	{
		if (scanx && rpo_kd[i] == scanx)
		{
			if (!down) rpo_kd[i] = 0;
			return TRUE;
		}
		if (!rpo_kd[i]) f = i;
	}
	if (down && scanx && f >= 0)
		rpo_kd[f] = scanx;
	return FALSE;
};

void() Report_Close =
{
	local float i;
	if (!rpo_open)
		return;
	rpo_open = 0;
	for (i = 0; i < RP_KN; i = i + 1)
		rpo_kd[i] = 0;
	sui_tooltip_reset();
	sui_reset_actions();
	UI_CursorRelease(UIC_REPORT);
};

// The screenshot is the screen as it is now, so it is taken before the panel draws.
void() Report_Open =
{
	local string dir, pre, q, nm;
	local float i;

	if (rpo_open)
		return;
	if (UI_CursorHeld())
	{
		print("^3report^7: another panel has the mouse -- close it first\n");
		return;
	}
	pre = cvar_string("scr_sshot_prefix");
	dir = "";
	for (i = strlen(pre) - 1; i >= 0; i = i - 1)
		if (str2chr(pre, i) == '/')
		{
			dir = substring(pre, 0, i + 1);
			break;
		}
	nm = sprintf("report_%s", strftime(FALSE, "%Y%m%d_%H%M%S"));
	q = cvar_string("scr_sshot_compression");
	// 60 keeps a 1440p frame near 300 KB; the player's own setting comes straight back.
	localcmd(sprintf("scr_sshot_compression 60\nscreenshot %s.jpg\nscr_sshot_compression \"%s\"\n", nm, q));
	if (rpo_shot != "") strunzone(rpo_shot);
	rpo_shot = strzone(sprintf("%s%s.jpg", dir, nm));
	rpo_shotok = rpo_flushed = FALSE;
	rpo_shotat = cltime;
	rpo_open = 1;
	rpo_waitn = 2;
	rpo_focus = (rpo_subj == "") ? 0 : 1;
	rpo_caret = (rpo_focus ? strlen(rpo_body) : strlen(rpo_subj));
	if (rpo_state == RP_SENT) rpo_state = RP_IDLE;
	rpo_wrapdirty = TRUE;
	sui_reset_actions();
	UI_CursorClaim(UIC_REPORT);
};

// The JPEG as base64, or "" (none, too big, unreadable: the report still goes).
string() Rp_ShotB64 =
{
	local float f, n;
	local string b;
	local void *buf;

	if (!checkbuiltin(base64encode))
		return "";
	f = fopen(rpo_shot, FILE_READ);
	if (f < 0)
		return "";
	n = fsize(f);
	if (n < 4 || n > RP_SHOT_MAX)
	{
		fclose(f);
		if (n > RP_SHOT_MAX) Rp_Status("the screenshot is too big to send; the report goes without it", TRUE);
		return "";
	}
	buf = memalloc(n);
	n = fread(f, buf, n);
	fclose(f);
	b = base64encode(buf, n);
	memfree(buf);
	return b;
};

void() Report_Send =
{
	local string s, env, shot;

	if (rpo_state == RP_SENDING)
		return;
	s = strtrim(rpo_subj);
	if (s == "")
	{
		Rp_Status("give it a subject: type one or pick one above", TRUE);
		rpo_focus = 0;
		rpo_caret = strlen(rpo_subj);
		return;
	}
	shot = (rpo_shotuse && rpo_shotok) ? Rp_ShotB64() : "";
	env = strcat("{\"v\":1,\"subject\":\"", Rp_Json(s), "\",\"category\":\"", Rp_CatId(rpo_cat), "\",\"body\":\"");
	env = strcat(env, Rp_Json(rpo_body), "\",\"meta\":", Report_Meta(), ",\"shot\":\"");
	env = strcat(env, shot, "\"}");
	// A map change restarts this VM's counter; a late reply must not land on a new report.
	if (rpo_nextreq < 7300000) rpo_nextreq = 7300000 + floor(random() * 80000);
	rpo_nextreq = rpo_nextreq + 1;
	rpo_req = rpo_nextreq;
	if (!uri_post(cvar_string("cl_report_url"), rpo_req, "application/json", env))
	{
		Rp_Status("the report service could not be reached; your report is still here", TRUE);
		return;
	}
	rpo_state = RP_SENDING;
	Rp_Status(shot != "" ? sprintf("sending (screenshot %.0f KB)...", strlen(shot) * 0.75 / 1024) : "sending...", FALSE);
	print(sprintf("^5report^7: sent %g bytes to %s\n", strlen(env), cvar_string("cl_report_url")));
};

// URI_Get_Callback (cl_online.qc). TRUE when the reply is this panel's.
float(float reqid, float code, string body) Report_Reply =
{
	local float a, b;
	local string err;

	if (!rpo_req || reqid != rpo_req)
		return FALSE;
	rpo_req = 0;
	rpo_state = RP_IDLE;
	// The engine hands a 200 over as 0 (DP compatibility, pr_bgcmd.c); a failed transfer is 0 with
	// no body, so the service's own "ok" is the test.
	if ((code == 0 || code == 200) && (strstrofs(body, "\"ok\":true") >= 0 || strstrofs(body, "\"ok\": true") >= 0))
	{
		rpo_state = RP_SENT;
		Rp_Status("sent -- thank you!", FALSE);
		Rp_SetSubj("");
		Rp_SetBody("");
		rpo_cat = 0;
		rpo_caret = 0;
		rpo_closeat = cltime + 1.5;
		print("^5report^7: received by the service\n");
		return TRUE;
	}
	err = "";
	a = strstrofs(body, "\"error\":\"");
	if (a >= 0)
	{
		b = strstrofs(body, "\"", a + 9);
		if (b > a + 9) err = Rp_Ascii(substring(body, a + 9, min(b - a - 9, 100)));
	}
	if (err == "")
		err = code ? sprintf("the service answered %g", code) : "the report service could not be reached";
	Rp_Status(strcat(err, "; your report is still here"), TRUE);
	print(sprintf("^3report^7: not sent (%g): %s\n", code, err));
	return TRUE;
};

/*
===========================================================================
  Editing.
===========================================================================
*/
string() Rp_Field = { return rpo_focus ? rpo_body : rpo_subj; };

void(string s) Rp_FieldSet =
{
	if (rpo_focus) Rp_SetBody(s);
	else Rp_SetSubj(s);
};

void(string ins) Rp_Insert =
{
	local string f;
	local float room;
	f = Rp_Field();
	room = (rpo_focus ? RP_BODY_MAX : RP_SUBJ_MAX) - strlen(f);
	if (room <= 0)
		return;
	ins = substring(ins, 0, room);
	rpo_caret = bound(0, rpo_caret, strlen(f));
	Rp_FieldSet(strcat(substring(f, 0, rpo_caret), ins, substring(f, rpo_caret, -1)));
	rpo_caret = rpo_caret + strlen(ins);
};

// The body's lines for width rpo_wrapw: paragraphs at \n, words at spaces.
void(float s, float l) Rp_AddLine =
{
	if (rpo_ln_n >= RP_LINES)
		return;
	rpo_ln_s[rpo_ln_n] = s;
	rpo_ln_l[rpo_ln_n] = l;
	rpo_ln_n = rpo_ln_n + 1;
};

void() Rp_Wrap =
{
	local float n, ps, pe, ls, le, ws, we;

	rpo_wrapdirty = FALSE;
	rpo_ln_n = 0;
	n = strlen(rpo_body);
	for (ps = 0; ps <= n && rpo_ln_n < RP_LINES; ps = pe + 1)
	{
		pe = strstrofs(rpo_body, "\n", ps);
		if (pe < 0) pe = n;
		ls = le = ws = ps;
		while (ws < pe)
		{
			we = strstrofs(rpo_body, " ", ws);
			if (we < 0 || we > pe) we = pe;
			if (le > ls && KC_TextW(substring(rpo_body, ls, we - ls), rpo_wrapfs) > rpo_wrapw)
			{
				Rp_AddLine(ls, le - ls);
				ls = le + 1;
			}
			le = we;
			ws = we + 1;
		}
		Rp_AddLine(ls, pe - ls);
	}
};

// The wrapped line holding caret c (the last one that reaches it).
float(float c) Rp_LineOf =
{
	local float i;
	for (i = rpo_ln_n - 1; i > 0; i = i - 1)
		if (rpo_ln_s[i] <= c)
			return i;
	return 0;
};

// The caret on line i nearest x pixels in.
float(float i, float x) Rp_ColAt =
{
	local float k, best, bd, d;
	local string t;
	t = substring(rpo_body, rpo_ln_s[i], rpo_ln_l[i]);
	best = 0;
	bd = 99999;
	for (k = 0; k <= rpo_ln_l[i]; k = k + 1)
	{
		d = fabs(KC_TextW(substring(t, 0, k), rpo_wrapfs) - x);
		if (d < bd) { bd = d; best = k; }
	}
	return rpo_ln_s[i] + best;
};

void(float scanx, float chary) Rp_Key =
{
	local float n, ctrl, l, x, i;
	local string f;

	f = Rp_Field();
	n = strlen(f);
	rpo_caret = bound(0, rpo_caret, n);
	ctrl = (ui_kmods & 48);
	rpo_blink = cltime;
	if (rpo_wrapdirty)
		Rp_Wrap();

	if (scanx == K_TAB)
	{
		rpo_focus = !rpo_focus;
		rpo_caret = strlen(Rp_Field());
		return;
	}
	if (scanx == K_ENTER || scanx == K_KP_ENTER)
	{
		if (ctrl) { Report_Send(); return; }
		if (!rpo_focus) { rpo_focus = 1; rpo_caret = strlen(rpo_body); return; }
		Rp_Insert("\n");
		return;
	}
	if (ctrl && (chary == 22 || scanx == 'v'))
	{
		sui_paste_ask();
		return;
	}
	if (scanx == K_BACKSPACE)
	{
		if (rpo_caret <= 0) return;
		l = rpo_caret - 1;
		if (ctrl)
		{
			while (l > 0 && str2chr(f, l - 1) == ' ') l = l - 1;
			while (l > 0 && str2chr(f, l - 1) != ' ' && str2chr(f, l - 1) != 10) l = l - 1;
		}
		Rp_FieldSet(strcat(substring(f, 0, l), substring(f, rpo_caret, -1)));
		rpo_caret = l;
		return;
	}
	if (scanx == K_DEL)
	{
		if (rpo_caret < n)
			Rp_FieldSet(strcat(substring(f, 0, rpo_caret), substring(f, rpo_caret + 1, -1)));
		return;
	}
	if (scanx == K_LEFTARROW) { rpo_caret = max(0, rpo_caret - 1); return; }
	if (scanx == K_RIGHTARROW) { rpo_caret = min(n, rpo_caret + 1); return; }
	if (scanx == K_HOME || scanx == K_END)
	{
		if (!rpo_focus || ctrl) { rpo_caret = (scanx == K_HOME) ? 0 : n; return; }
		i = Rp_LineOf(rpo_caret);
		rpo_caret = rpo_ln_s[i] + ((scanx == K_HOME) ? 0 : rpo_ln_l[i]);
		return;
	}
	if ((scanx == K_UPARROW || scanx == K_DOWNARROW) && rpo_focus)
	{
		i = Rp_LineOf(rpo_caret);
		x = KC_TextW(substring(rpo_body, rpo_ln_s[i], rpo_caret - rpo_ln_s[i]), rpo_wrapfs);
		i = i + ((scanx == K_UPARROW) ? -1 : 1);
		if (i >= 0 && i < rpo_ln_n)
			rpo_caret = Rp_ColAt(i, x);
		return;
	}
	if (chary >= 32 && chary <= 126 && !ctrl)
		Rp_Insert(chr2str(chary));
};

float(float chary) Report_Paste =
{
	if (rpo_open != 2)
		return FALSE;
	Rp_Insert(chr2str(chary));
	return TRUE;
};

float(float evtype, float scanx, float chary, float devid) Report_InputEvent =
{
	if (!rpo_open)
		return FALSE;
	if (evtype == IE_MOUSEABS)
	{
		rpo_ms = [scanx, chary];
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (evtype == IE_KEYUP)
	{
		if (scanx == K_MOUSE1)
			sui_input_event(evtype, scanx, chary, devid);
		return Rp_Took(scanx, FALSE);
	}
	if (evtype != IE_KEYDOWN)
		return FALSE;
	if (getkeybind(scanx) == "toggleconsole")
	{
		Report_Close();                 // the draft stays for the next F3
		return FALSE;
	}
	Rp_Took(scanx, TRUE);
	if (scanx == K_MOUSE1)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (rpo_open != 2)
		return TRUE;
	if (scanx == K_ESCAPE || getkeybind(scanx) == "report")
	{
		Report_Close();
		return TRUE;
	}
	if (scanx == K_MWHEELUP || scanx == K_MWHEELDOWN)
	{
		rpo_scroll = max(0, rpo_scroll + ((scanx == K_MWHEELUP) ? -1 : 1));
		return TRUE;
	}
	Rp_Key(scanx, chary);
	return TRUE;
};

/*
===========================================================================
  Drawing.
===========================================================================
*/
// A field's frame, focused or not; TRUE on the frame it is clicked.
float(string id, vector p, vector s, float on, float sc) Rp_FieldBox =
{
	sui_action_element(p, s, id, sui_noop);
	if (on)
		sui_style_box(p, s, 3 * sc, SUI_THEME_WELL, SUI_THEME_FOCUS, 1);
	else if (sui_is_hovered(id))
		sui_style_box(p, s, 3 * sc, SUI_THEME_WELL, SUI_THEME_EDGE_HI, 1);
	else
		sui_roundbox(p, s, 3 * sc, SUI_THEME_WELL, 1);
	return sui_is_released(id);
};

void(vector p, float fs) Rp_Caret =
{
	if ((cltime - rpo_blink) - floor(cltime - rpo_blink) < 0.65)
		sui_fill(p, [max(1, fs * 0.12), fs * 1.15, 0], SUI_THEME_FOCUS, 1, 0);
};

void(vector p, vector s, float sc) Rp_DrawSubject =
{
	local float fs, pad, x;
	local vector glyph;
	local string t;

	fs = rpo_fs;
	pad = 4 * sc;
	glyph = sui_native_text_size(fs);
	if (Rp_FieldBox("rpo_subj", p, s, rpo_focus == 0, sc))
	{
		rpo_focus = 0;
		rpo_caret = strlen(rpo_subj);
		rpo_blink = cltime;
	}
	drawsetcliparea(p_x + 1, p_y, s_x - 2, s_y);
	if (rpo_subj == "")
		sui_native_text([p_x + pad, p_y + (s_y - glyph_y) * 0.5, 0],
		                "What is it about? Type it, or pick one below", fs, SUI_THEME_MUTED, 0.8);
	else
		sui_native_text([p_x + pad, p_y + (s_y - glyph_y) * 0.5, 0], rpo_subj, fs, SUI_THEME_TEXT, 1);
	if (rpo_focus == 0)
	{
		t = substring(rpo_subj, 0, rpo_caret);
		x = KC_TextW(t, fs);
		Rp_Caret([p_x + pad + x, p_y + (s_y - glyph_y) * 0.5 - fs * 0.05, 0], fs);
	}
	drawresetcliparea();
};

void(vector p, vector s, float sc) Rp_DrawBody =
{
	local float fs, pad, lh, rows, i, ci, y, x;
	local vector glyph;

	fs = rpo_fs;
	pad = 4 * sc;
	lh = rpo_lh;
	glyph = sui_native_text_size(fs);
	if (rpo_wrapw != s_x - pad * 2 || rpo_wrapfs != fs)
	{
		rpo_wrapw = s_x - pad * 2;
		rpo_wrapfs = fs;
		rpo_wrapdirty = TRUE;
	}
	if (rpo_wrapdirty)
		Rp_Wrap();
	rows = max(1, floor((s_y - pad * 2) / lh));
	ci = Rp_LineOf(rpo_caret);
	if (rpo_focus == 1)
	{
		if (ci < rpo_scroll) rpo_scroll = ci;
		if (ci >= rpo_scroll + rows) rpo_scroll = ci - rows + 1;
	}
	rpo_scroll = bound(0, rpo_scroll, max(0, rpo_ln_n - rows));
	rpo_bodyp = p;
	rpo_bodys = s;
	if (Rp_FieldBox("rpo_body", p, s, rpo_focus == 1, sc))
	{
		rpo_focus = 1;
		i = bound(0, rpo_scroll + floor((rpo_ms_y - p_y - pad) / lh), rpo_ln_n - 1);
		rpo_caret = Rp_ColAt(i, rpo_ms_x - p_x - pad);
		rpo_blink = cltime;
	}
	drawsetcliparea(p_x + 1, p_y + 1, s_x - 2, s_y - 2);
	if (rpo_body == "")
	{
		y = p_y + pad;
		sui_native_text([p_x + pad, y, 0], "Be specific. What happened, and what did you expect?", fs, SUI_THEME_MUTED, 0.8);
		sui_native_text([p_x + pad, y + lh, 0], "Where on the map, and does it happen every time?", fs, SUI_THEME_MUTED, 0.8);
		sui_native_text([p_x + pad, y + lh * 2, 0], "How can someone else make it happen? Step by step helps most.", fs, SUI_THEME_MUTED, 0.8);
		sui_native_text([p_x + pad, y + lh * 3.5, 0], "The map, your position, your save, your settings and the", fs, SUI_THEME_MUTED, 0.6);
		sui_native_text([p_x + pad, y + lh * 4.5, 0], "screenshot on the right go with it: no need to type those.", fs, SUI_THEME_MUTED, 0.6);
	}
	for (i = rpo_scroll; i < rpo_ln_n && i < rpo_scroll + rows; i = i + 1)
	{
		y = p_y + pad + (i - rpo_scroll) * lh;
		sui_native_text([p_x + pad, y, 0], substring(rpo_body, rpo_ln_s[i], rpo_ln_l[i]), fs, SUI_THEME_TEXT, 1);
		if (rpo_focus == 1 && i == ci)
		{
			x = KC_TextW(substring(rpo_body, rpo_ln_s[i], rpo_caret - rpo_ln_s[i]), fs);
			Rp_Caret([p_x + pad + x, y - fs * 0.05, 0], fs);
		}
	}
	if (rpo_focus == 1 && rpo_body == "")
		Rp_Caret([p_x + pad, p_y + pad - fs * 0.05, 0], fs);
	drawresetcliparea();
};

void(vector p, vector s, float sc) Rp_DrawShot =
{
	local vector isz, d;
	local float f;

	if (!rpo_shotok && cltime - rpo_shotat < 4)
	{
		f = fopen(rpo_shot, FILE_READ);
		if (f >= 0)
		{
			if (fsize(f) > 0) rpo_shotok = TRUE;
			fclose(f);
		}
		// The engine writes a screenshot without adding it to its file index (cl_screen.c), so
		// neither fopen nor drawpic finds it; fs_flush makes lookups scan until the next map's
		// rehash. Once a report, and only when the shot is not found on its own.
		else if (!rpo_flushed && cltime - rpo_shotat > 0.3)
		{
			rpo_flushed = TRUE;
			localcmd("fs_flush\n");
		}
	}
	sui_roundbox(p, s, 3 * sc, SUI_THEME_WELL, 1);
	if (!rpo_shotok)
	{
		sui_native_text([p_x + 6 * sc, p_y + s_y * 0.45, 0], (cltime - rpo_shotat < 4) ? "taking a screenshot..."
		                : "no screenshot (it could not be taken)", 7 * sc, SUI_THEME_MUTED, 1);
		return;
	}
	isz = drawgetimagesize(rpo_shot);
	if (isz_x < 1 || isz_y < 1)
		isz = [16, 9, 0];
	f = min((s_x - 4) / isz_x, (s_y - 4) / isz_y);
	d = [isz_x * f, isz_y * f, 0];
	drawpic([p_x + (s_x - d_x) * 0.5, p_y + (s_y - d_y) * 0.5, 0], rpo_shot, d, '1 1 1', rpo_shotuse ? 1 : 0.25, 0);
};

void(vector scr) Report_Draw =
{
	local float sc, fit, pad, panw, panh, y, x, colw, rw, bw, i, cw, ch, done, cancel, send;
	local vector p, glyph, shs;
	local string foot;
	local vector footc;

	if (clframetime > 0)
		rpo_fps = rpo_fps ? rpo_fps * 0.97 + (1 / clframetime) * 0.03 : 1 / clframetime;
	if (!rpo_open)
		return;
	if (rpo_open == 1)
	{
		rpo_waitn = rpo_waitn - 1;
		if (rpo_waitn > 0)
			return;
		rpo_open = 2;
	}
	if (rpo_closeat && cltime >= rpo_closeat)
	{
		rpo_closeat = 0;
		Report_Close();
		return;
	}
	if (rec_sb_open || rec_wt_open || (UI_CursorHeld() - (UI_CursorHeld() & UIC_REPORT)))
	{
		Report_Close();
		return;
	}

	sc = ui_cv_scale;
	if (sc <= 0) sc = 2;
	fit = min(scr_x * 0.96 / 440, scr_y * 0.96 / 270);
	if (sc > fit)
		sc = max(1, floor(fit * 2) / 2);
	pad = 8 * sc;
	rpo_fs = 8 * sc;
	rpo_lh = 10 * sc;
	colw = 250 * sc;
	rw = 160 * sc;
	panw = pad * 3 + colw + rw;
	panh = 270 * sc;
	p = [floor((scr_x - panw) * 0.5), floor((scr_y - panh) * 0.5), 0];
	glyph = sui_native_text_size(7 * sc);
	done = cancel = send = FALSE;

	sui_begin(scr_x, scr_y);
	Font_Set(ui_font_ui);
	sui_fill('0 0 0', [scr_x, scr_y, 0], '0 0 0', 0.35, 0);
	sui_action_element(p, [panw, panh, 0], "rpo_panel", sui_noop);
	sui_style_panel(p, [panw, panh, 0], 7 * sc, 1);

	y = p_y + 6 * sc;
	sui_native_text([p_x + pad, y, 0], "Report a problem or an idea", 10 * sc, SUI_THEME_TEXT, 1);
	sui_native_text([p_x + panw - pad - KC_TextW("Esc closes, keeps your text", 7 * sc), y + 2 * sc, 0],
	                "Esc closes, keeps your text", 7 * sc, SUI_THEME_MUTED, 1);
	y = y + 18 * sc;

	// Left: subject, presets, text.
	x = p_x + pad;
	sui_native_text([x, y, 0], "Subject", 7 * sc, SUI_THEME_DIM, 1);
	y = y + glyph_y + 2 * sc;
	rpo_subjp = [x, y, 0];
	rpo_subjs = [colw, 14 * sc, 0];
	Rp_DrawSubject(rpo_subjp, rpo_subjs, sc);
	y = y + 14 * sc + 4 * sc;
	cw = (colw - 2 * 4 * sc) / 3;
	ch = 12 * sc;
	for (i = 1; i <= RP_NCAT; i = i + 1)
	{
		if (KC_Button(sprintf("rpo_cat%g", i), [x + ((i - 1) % 3) * (cw + 4 * sc), y + floor((i - 1) / 3) * (ch + 3 * sc), 0],
		              [cw, ch, 0], Rp_CatLabel(i), (rpo_cat == i) ? SUI_THEME_SELECTED : SUI_THEME_CHIP,
		              (rpo_cat == i) ? SUI_THEME_TEXT : SUI_THEME_DIM, sc))
		{
			// A preset fills an empty subject (or replaces the preset it wrote); typed text stays.
			if (strtrim(rpo_subj) == "" || (rpo_cat && !strcmp(rpo_subj, Rp_CatLabel(rpo_cat))))
				Rp_SetSubj(Rp_CatLabel(i));
			rpo_cat = i;
			rpo_focus = 1;
			rpo_caret = strlen(rpo_body);
		}
	}
	y = y + 2 * (ch + 3 * sc) + 3 * sc;
	sui_native_text([x, y, 0], "What happened", 7 * sc, SUI_THEME_DIM, 1);
	sui_native_text([x + colw - KC_TextW(sprintf("%g / %g", strlen(rpo_body), RP_BODY_MAX), 7 * sc), y, 0],
	                sprintf("%g / %g", strlen(rpo_body), RP_BODY_MAX), 7 * sc, SUI_THEME_MUTED, 1);
	y = y + glyph_y + 2 * sc;
	Rp_DrawBody([x, y, 0], [colw, p_y + panh - pad - 22 * sc - y, 0], sc);

	// Right: the screenshot and what goes with the report.
	x = p_x + pad * 2 + colw;
	y = p_y + 24 * sc;
	sui_native_text([x, y, 0], "Screenshot", 7 * sc, SUI_THEME_DIM, 1);
	y = y + glyph_y + 2 * sc;
	shs = [rw, rw * 9 / 16, 0];
	Rp_DrawShot([x, y, 0], shs, sc);
	y = y + shs_y + 3 * sc;
	if (KC_Button("rpo_shotuse", [x, y, 0], [rw, 12 * sc, 0],
	              rpo_shotuse ? "include the screenshot: yes" : "include the screenshot: no",
	              rpo_shotuse ? SUI_THEME_CHIP : SUI_THEME_WELL, rpo_shotuse ? SUI_THEME_TEXT : SUI_THEME_MUTED, sc))
		rpo_shotuse = !rpo_shotuse;
	y = y + 12 * sc + 8 * sc;
	sui_native_text([x, y, 0], "Also sent", 7 * sc, SUI_THEME_DIM, 1);
	y = y + glyph_y + 2 * sc;
	sui_native_text([x, y, 0], sprintf("map %s", serverkey("map")), 7 * sc, SUI_THEME_MUTED, 1);
	y = y + 9 * sc;
	sui_native_text([x, y, 0], PE_Local() ? "a local game" : Rp_Ascii(substring(serverkey("hostname"), 0, 30)), 7 * sc, SUI_THEME_MUTED, 1);
	y = y + 9 * sc;
	sui_native_text([x, y, 0], sprintf("position %.0f %.0f %.0f", pmove_org_x, pmove_org_y, pmove_org_z), 7 * sc, SUI_THEME_MUTED, 1);
	y = y + 9 * sc;
	sui_native_text([x, y, 0], sprintf("save %g of %g, the timer, %.0f fps", getstatf(STAT_FS_SAVEINDEX),
	                                   getstatf(STAT_FS_SAVECOUNT), rpo_fps), 7 * sc, SUI_THEME_MUTED, 1);
	y = y + 9 * sc;
	sui_native_text([x, y, 0], "graphics settings, game version", 7 * sc, SUI_THEME_MUTED, 1);
	y = y + 9 * sc;
	sui_native_text([x, y, 0], "your name (for questions back)", 7 * sc, SUI_THEME_MUTED, 1);

	// Bottom: what happened last, then the two buttons.
	y = p_y + panh - pad - 14 * sc;
	bw = 64 * sc;
	cancel = KC_Button("rpo_cancel", [p_x + panw - pad - bw * 2 - 6 * sc, y, 0], [bw, 14 * sc, 0], "cancel",
	                   SUI_THEME_CHIP, SUI_THEME_DIM, sc);
	sui_tooltip_for("rpo_cancel", "Close and throw this report away.", sc);
	send = KC_Button("rpo_send", [p_x + panw - pad - bw, y, 0], [bw, 14 * sc, 0],
	                 (rpo_state == RP_SENDING) ? "sending..." : "send", SUI_THEME_SELECTED, SUI_THEME_TEXT, sc);
	sui_tooltip_for("rpo_send", "Ctrl+Enter sends too.", sc);
	if (rpo_status != "" && (cltime - rpo_statusat < 8 || rpo_state == RP_SENDING || rpo_statusbad))
	{
		foot = rpo_status;
		footc = rpo_statusbad ? SUI_THEME_BAD : SUI_THEME_GOOD;
	}
	else
	{
		foot = "Tab moves between the boxes   Enter starts a new line   Ctrl+V pastes";
		footc = SUI_THEME_MUTED;
	}
	sui_native_text([p_x + pad, y + (14 * sc - glyph_y) * 0.5, 0], foot, 7 * sc, footc, 1);

	sui_end();
	Font_Reset();

	if (send)
		Report_Send();
	if (cancel)
	{
		Rp_SetSubj("");
		Rp_SetBody("");
		rpo_cat = 0;
		Report_Close();
	}
};

float() Report_Console =
{
	local string a;
	local float i;

	if (argv(0) != "report")
		return FALSE;
	a = argv(1);
	if (a == "")
	{
		if (rpo_open) Report_Close();
		else Report_Open();
		return TRUE;
	}
	if (a == "subject") { Rp_SetSubj(substring(argv(2), 0, RP_SUBJ_MAX)); return TRUE; }
	if (a == "body") { Rp_SetBody(argv(2)); return TRUE; }
	if (a == "cat")
	{
		for (i = 1; i <= RP_NCAT; i = i + 1)
			if (argv(2) == Rp_CatId(i)) rpo_cat = i;
		return TRUE;
	}
	if (a == "send") { Report_Send(); return TRUE; }
	if (a == "status")
	{
		print(sprintf("report: open %g state %g cat %s shot %s ok %g use %g\n", rpo_open, rpo_state,
		              Rp_CatId(rpo_cat), rpo_shot, rpo_shotok, rpo_shotuse));
		print(sprintf("report: subject [%s] body %g chars, %g lines; status [%s]\n", rpo_subj, strlen(rpo_body),
		              rpo_ln_n, rpo_status));
		return TRUE;
	}
	print("report: report [status|subject <t>|body <t>|cat <id>|send]\n");
	return TRUE;
};
