/*
  P1418: crash reports, the sending half.  m_crash.qc writes data/crash/report_<utc>.txt after a session that
  ended in Sys_Error.  On a server that says it takes them (serverinfo fs_crashrep, sv_crash.qc) and that this
  PC does not host, the newest report not in data/crash/sent.txt is offered in a side box, once per report
  (offered.txt, written when the box is first drawn).  F6 alone sends it, one chunk per ack; a server can
  stuffcmd any console command, so `crash_send` only opens the box.  ui_crash_report 0: no box.
*/
#define CR_CHUNK     800
#define CR_MAXCHUNKS 40         // a report is at most 122 lines of 200 bytes
#define CR_BOX       30         // seconds the offer stays up

string cr_stem;                 // the report on offer (zoned); "" = none
float  cr_box_end;              // the box is up until this; -1 = offered on an earlier launch
float  cr_drawn;                // drawn since it opened
float  cr_join_t;
var float cr_send = -1;         // strbuf of chunks being sent; -1 = idle
float  cr_send_i, cr_send_n;
float  cr_send_wait, cr_send_t; // waiting for the ack of chunk cr_send_i - 1, sent at
float  cr_sent_ok;              // 1 stored, -1 refused or failed, 0 neither

// stem listed in data/crash/<list>.txt
float(string list, string stem) CR_Listed =
{
	local float fh;
	local string ln;
	fh = fopen(strcat("data/crash/", list, ".txt"), FILE_READ);
	if (fh < 0)
		return FALSE;
	for (ln = fgets(fh); ln; ln = fgets(fh))
		if (ln == stem)
		{
			fclose(fh);
			return TRUE;
		}
	fclose(fh);
	return FALSE;
};

void(string list, string stem) CR_List =
{
	local float fh;
	fh = fopen(strcat("data/crash/", list, ".txt"), FILE_APPEND);
	if (fh >= 0)
	{
		fputs(fh, strcat(stem, "\n"));
		fclose(fh);
	}
};

void() CR_Init =
{
	local searchhandle h;
	local float i, n;
	local string s, best;

	registercommand("crash_ack");
	registercommand("crash_send");
	cr_join_t = cltime;
	cr_box_end = 0;
	if (cr_stem != "")
		strunzone(cr_stem);
	cr_stem = "";
	h = search_begin("data/crash/report_*.txt", FALSE, TRUE);
	if (h < 0)
		return;
	best = "";
	n = search_getsize(h);
	for (i = 0; i < n; i = i + 1)
	{
		s = search_getfilename(h, i);
		s = substring(s, strlen("data/crash/"), strlen(s) - strlen("data/crash/") - 4);
		if (strcmp(s, best) > 0)        // the names carry the time: the greatest is the newest
		if (!CR_Listed("sent", s))
			best = s;
	}
	search_end(h);
	if (best != "")
		cr_stem = strzone(best);
};

// A server that takes them, not this PC's own game, and the player has not opted out.
float() CR_Here =
{
	if (cr_stem == "" || !cvar("ui_crash_report") || PE_Local())
		return FALSE;
	return serverkey("fs_crashrep") == "1";
};

void() CR_SendStop =
{
	if (cr_send >= 0)
		buf_del(cr_send);
	cr_send = -1;
	cr_send_wait = FALSE;
};

void() CR_Frame =
{
	if (cr_send >= 0)
	if (cr_send_wait)
	if (cltime > cr_send_t + 10)
	{	// as prederror's: a lobby without the channel never answers
		print("crash: the lobby did not answer; the report was not sent\n");
		cr_sent_ok = -1;
		CR_SendStop();
	}
	if (cr_box_end || !CR_Here())
		return;
	if (cltime < cr_join_t + 8)
		return;                         // after the join's own noise
	if (CR_Listed("offered", cr_stem))
	{
		cr_box_end = -1;                // asked once already: `crash_send` still opens it
		return;
	}
	cr_box_end = cltime + CR_BOX;
	cr_drawn = FALSE;
	cr_sent_ok = 0;
};

float() CR_Pack =
{
	local float fh, rows;
	local string ln, cur;
	CR_SendStop();
	fh = fopen(strcat("data/crash/", cr_stem, ".txt"), FILE_READ);
	if (fh < 0)
		return FALSE;
	cr_send = buf_create();
	bufstr_add(cr_send, "begin", TRUE);        // chunk 0, rewritten below
	cur = "";
	rows = 0;
	for (ln = fgets(fh); ln; ln = fgets(fh))
	{
		ln = substring(ln, 0, 200);
		if (strlen(cur) + strlen(ln) + 1 > CR_CHUNK)
		{
			bufstr_add(cr_send, cur, TRUE);
			cur = "";
		}
		cur = strcat(cur, ln, "\n");
		rows = rows + 1;
	}
	fclose(fh);
	if (cur != "")
		bufstr_add(cr_send, cur, TRUE);
	cr_send_n = buf_getsize(cr_send);
	if (rows == 0 || cr_send_n > CR_MAXCHUNKS + 1)
	{
		CR_SendStop();
		return FALSE;
	}
	bufstr_set(cr_send, 0, sprintf("begin %s %.0f", cr_stem, cr_send_n - 1));
	return TRUE;
};

void() CR_SendNext =
{
	sendevent("cr", "fs", cr_send_i, bufstr_get(cr_send, cr_send_i));
	cr_send_i = cr_send_i + 1;
	cr_send_wait = TRUE;
	cr_send_t = cltime;
	cr_box_end = max(cr_box_end, cltime + 5);   // up for as long as it sends
};

float() CR_BoxUp =
{
	return cr_box_end > cltime && !rec_sb_open && !PE_BoxUp();
};

// F6 only, while the box is drawn.
void() CR_Send =
{
	if (!CR_BoxUp() || !CR_Here() || cr_send >= 0 || cr_sent_ok == 1)
		return;
	if (!CR_Pack())
	{
		print("crash: the report could not be read\n");
		cr_sent_ok = -1;
		return;
	}
	cr_send_i = 0;
	cr_sent_ok = 0;
	CR_SendNext();
};

float(string cmd) CR_ConsoleCommand =
{
	local float fh;
	tokenize(cmd);
	if (argv(0) == "crash_send")
	{	// opens the box; F6 sends (a server can stuffcmd this)
		if (cr_stem == "")
			print("crash: no unsent report\n");
		else if (cr_sent_ok == 1)
			print("crash: already sent\n");
		else if (!cvar("ui_crash_report"))
			print("crash: ui_crash_report is 0\n");
		else if (!CR_Here())
			print("crash: reports go to a lobby that takes them\n");
		else
		{
			cr_box_end = max(cr_box_end, cltime + CR_BOX);
			cr_drawn = FALSE;
			if (cr_sent_ok == -1)
				cr_sent_ok = 0;
			print("crash: press F6 to send the report\n");
		}
		return TRUE;
	}
	if (argv(0) != "crash_ack")
		return FALSE;
	if (cr_send < 0)
		return TRUE;
	if (argv(1) == "refused")
	{
		print(sprintf("crash: the lobby did not take the report (%s)\n", argv(2)));
		cr_sent_ok = -1;
		CR_SendStop();
		return TRUE;
	}
	if (stof(argv(1)) != cr_send_i - 1)
		return TRUE;
	cr_send_wait = FALSE;
	if (cr_send_i < cr_send_n)
	{
		CR_SendNext();
		return TRUE;
	}
	cr_sent_ok = 1;
	cr_box_end = cltime + 4;
	CR_List("sent", cr_stem);
	fh = fopen(strcat("data/crash/", cr_stem, ".txt"), FILE_WRITE);
	if (fh >= 0)
	{	// sent: the console lines leave this disk too (a server's CSQC can read data/)
		fputs(fh, sprintf("sent %s\n", strftime(FALSE, "%Y-%m-%d %H:%M:%S")));
		fclose(fh);
	}
	print("crash: report sent, thank you\n");
	CR_SendStop();
	return TRUE;
};

float(float scanx) CR_Key =
{
	if (scanx != K_F6 || !CR_BoxUp() || cr_send >= 0 || cr_sent_ok == 1)
		return FALSE;
	CR_Send();
	return TRUE;
};

void(vector scr) CR_Draw =
{
	local vector p;
	local float sc, w, h, hh, lsz, y;
	local string st;
	if (!CR_BoxUp())
		return;
	if (!cr_drawn)
	{	// seen: offered once, even if not sent
		cr_drawn = TRUE;
		if (!CR_Listed("offered", cr_stem))
			CR_List("offered", cr_stem);
	}
	sc = ui_cv_scale;
	Font_Set(ui_font_ui);
	lsz = Font_Px(8 * sc);
	h = 14 * sc;
	hh = 15 * sc;
	w = 160 * sc;
	p = [scr_x - w - 8 * sc, scr_y * 0.42, 0];
	_sui_round_draw(p, [w, 3 * sc + hh + 3 * h + 3 * sc, 0], 5 * sc, SUI_THEME_PANEL, 0.90);
	y = p_y + 3 * sc;
	HUD_Text([p_x + 6 * sc, y + (hh - 2 * sc - lsz) * 0.5], "Game closed with an error", lsz, SUI_THEME_TEXT, 1);
	HUD_TextR([p_x + w - 6 * sc, y + (hh - 2 * sc - lsz) * 0.5], sprintf("%gs", ceil(max(0, cr_box_end - cltime))),
	          lsz, SUI_THEME_WARN, 1);
	drawfill([p_x + 4 * sc, y + hh - 2 * sc, 0], [w - 8 * sc, 1, 0], SUI_THEME_EDGE_HI, 0.7, 0);
	y = y + hh;
	HUD_Text([p_x + 6 * sc, y + (h - lsz) * 0.5], substring(strcat("to ", serverkey("hostname")), 0, 30),
	         lsz, SUI_THEME_DIM, 1);
	y = y + h;
	if (cr_sent_ok == 1)
		st = "sent -- thank you";
	else if (cr_sent_ok == -1)
		st = "not sent (see console)";
	else if (cr_send >= 0)
		st = sprintf("sending %g of %g...", cr_send_i, cr_send_n);
	else
		st = "the error + last console lines";
	HUD_Text([p_x + 6 * sc, y + (h - lsz) * 0.5], st, lsz, SUI_THEME_DIM, 1);
	y = y + h;
	KeyMenu_Row([p_x, y], w, h, "F6", "Send report to the lobby",
	            (cr_send >= 0 || cr_sent_ok == 1) ? KM_INERT : KM_HOT, lsz, sc);
	Font_Reset();
};
