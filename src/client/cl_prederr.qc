/*
  Patch 1195: prederror reports.  The engine's snap-back meter (cl_prederror, Patch 335) bumps
  cl_prederror_count; a line of cl_prederr_report units or more starts a report.  1.5 s later the
  engine dumps its comparison ring (prederr_dump) and this file writes the context beside it, both
  in data/prederr/.  Then a side box offers to send them to the lobby, which stores them with its
  own header (sv_prederr.qc).  The upload rides sendevent, one chunk per server ack.
  Timers are cltime: `time` stops with the server.
*/
#define PE_RING      96
#define PE_CHUNK     800
#define PE_MAXCHUNKS 400

var float pe_ring = -1;           // strbuf, circular: "time seq what" context lines
float  pe_ring_n;               // lines ever added; slot = n % PE_RING
float  pe_ok;                   // the engine has prederr_dump
float  pe_count;                // last cl_prederror_count seen
float  pe_due;                  // when the pending report is written; 0 = none pending
float  pe_err, pe_errseq;       // worst line of the pending report
float  pe_cool;                 // no new report before this
string pe_name;                 // the last report written (file stem), zoned
float  pe_box_end;              // the side box is up until this
float  pe_box_err;
var float pe_send = -1;           // strbuf of chunks being sent; -1 = idle
float  pe_send_i, pe_send_n;    // next chunk, chunk count (chunk 0 is the begin line)
float  pe_send_wait, pe_send_t; // waiting for the ack of chunk pe_send_i - 1, sent at
float  pe_sent_ok;              // 1 stored, -1 failed, 0 neither
float  pe_tseq[TG_MAX];         // last seq a mirror trigger fired, for enter-only notes
float  pe_name_err, pe_name_seq; // the last report written: its worst line
float  pe_box_pending;          // a report written during an upload gets its box after it

void() PE_RegisterCvars =
{
	registercvar("cl_prederr_report", "32", CVAR_ARCHIVE);   // units; 0 = no reports
	registercvar("cl_prederr_ask", "1", CVAR_ARCHIVE);       // 0 = keep them locally, never ask
	registercommand("prederr_ack");
	registercommand("prederr_send");
	pe_ok = checkcommand("prederr_dump") == 1;
	pe_count = cvar("cl_prederror_count");
};

void(string s) PE_Note =
{
	if (pe_ring < 0)
		pe_ring = buf_create();
	bufstr_set(pe_ring, pe_ring_n - floor(pe_ring_n / PE_RING) * PE_RING,
	           sprintf("%.3f %.0f %s", time, clientcommandframe, strreplace("\r", " ", strreplace("\n", " | ", s))));
	pe_ring_n = pe_ring_n + 1;
};

// Enter-only: a continuous push fires every command, and a replay repeats old seqs.
void(float i, float seq) PE_TrigFired =
{
	if (i < 0 || i >= TG_MAX)
		return;
	if (seq <= pe_tseq[i])
		return;
	if (seq > pe_tseq[i] + 1)
		PE_Note(sprintf("trig #%g %s kind %g fired at seq %.0f", i, tg_ent[i].model, tg_kind[i], seq));
	pe_tseq[i] = seq;
};

void() PE_MapReset =
{
	local float i;
	for (i = 0; i < TG_MAX; i = i + 1)
		pe_tseq[i] = 0;
	PE_Note(sprintf("map %s", mapname));
};

// The engine takes [A-Za-z0-9_.-] only; a map name may hold anything else.
string(string s) PE_Safe =
{
	local float i, c;
	local string o;
	o = "";
	for (i = 0; i < strlen(s) && i < 40; i = i + 1)
	{
		c = str2chr(s, i);
		if ((c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c == 45 || c == 46 || c == 95)
			o = strcat(o, chr2str(c));
		else
			o = strcat(o, "_");
	}
	return o;
};

// Patch 1207: CSQC_PredictPlayerPreMove runs on every replayed command.  The engine skips it, and
// every CSQC prediction hook, while this process hosts a server (pr_csqc.c: sv.state != ss_dead).
float() PE_Predicting =
{
	return (cltime - wop_premove_t < 0.5 && cltime >= wop_premove_t);
};

// This PC hosts the game: no warp op or trigger is predicted, so a line is a server move, not a
// misprediction; nor is a report sent to itself.  (P1195 read cvar("sv_running"), which the engine
// does not have: always 0.)
float() PE_Local =
{
	return !strncmp(serverkey("ip"), "QLoopBack", 9);
};

void(string stem) PE_WriteContext =
{
	local float f, i, i0;
	f = fopen(strcat("data/prederr/", stem, "_ctx.txt"), FILE_WRITE);
	if (f < 0)
		return;
	fputs(f, "FTESURF-PREDCTX 1\n");
	fputs(f, sprintf("map %s\nserver %s\nlocal %s\nworst %.2f at seq %.0f\n", serverkey("map"), serverkey("ip"),
	                 strftime(TRUE, "%Y-%m-%d %H:%M:%S"), pe_err, pe_errseq));
	fputs(f, sprintf("cvars cl_netfps %s rate %s cl_maxfps %s cl_prederror %s cl_triggers %s cl_warpop %s\n",
	                 cvar_string("cl_netfps"), cvar_string("rate"), cvar_string("cl_maxfps"),
	                 cvar_string("cl_prederror"), cvar_string("cl_triggers"), cvar_string("cl_warpop")));
	fputs(f, sprintf("ping %s\n", getplayerkeyvalue(player_localnum, "ping")));   // the engine is in the ring's header
	fputs(f, sprintf("csprogs crc %s size %s local %g qchook %s\n", serverkey("*csprogs"),
	                 serverkey("*csprogssize"), PE_Local(), cvar_string("cl_predict_qchook")));   // P1207
	fputs(f, "# context: time seq what (server prints, mirror triggers, gates, warp ops, prederr lines)\n");
	i0 = max(0, pe_ring_n - PE_RING);
	for (i = i0; i < pe_ring_n; i = i + 1)
		fputs(f, strcat(bufstr_get(pe_ring, i - floor(i / PE_RING) * PE_RING), "\n"));
	fclose(f);
};

void() PE_BoxOpen =
{
	pe_box_pending = FALSE;
	pe_box_end = cltime + 20;
	pe_box_err = pe_name_err;
	pe_sent_ok = 0;
};

void() PE_Write =
{
	local string stem;
	stem = strcat(strftime(TRUE, "%Y%m%d_%H%M%S"), "_", PE_Safe(serverkey("map")));
	if (pe_name != "")
		strunzone(pe_name);
	pe_name = strzone(stem);
	localcmd(sprintf("prederr_dump %s.txt\n", stem));
	PE_WriteContext(stem);
	print(sprintf("prederr: report kept in data/prederr/%s.txt (worst %.0f units)\n", stem, pe_err));
	pe_name_err = pe_err;
	pe_name_seq = pe_errseq;
	if (cvar("cl_prederr_ask") && !PE_Local())
	{
		if (pe_send >= 0)
			pe_box_pending = TRUE;
		else
			PE_BoxOpen();
	}
};

void() PE_SendStop =
{
	if (pe_send >= 0)
		buf_del(pe_send);
	pe_send = -1;
	if (pe_box_pending)
		PE_BoxOpen();
};

void() PE_Frame =
{
	local float c, n, e;
	if (!pe_ok)
		return;
	c = cvar("cl_prederror_count");
	if (c != pe_count)
	{
		pe_count = c;
		n = tokenize(cvar_string("cl_prederror_last"));
		e = (n >= 9) ? stof(argv(2)) : 0;
		PE_Note(strcat("prederr ", cvar_string("cl_prederror_last")));
		if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report") && PE_Local())
			PE_Note("not reported: this PC hosts the game, so nothing is predicted");
		else if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report") && cvar("cl_predict_qchook")
		         && !PE_Predicting())
			PE_Note(sprintf("not reported: no prediction hook for %.1f s", cltime - wop_premove_t));
		else if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report"))
		{
			if (!pe_due && cltime >= pe_cool)
			{
				pe_due = cltime + 1.5;     // the commands after it go in the ring too
				pe_err = 0;
			}
			if (pe_due && e > pe_err)
			{
				pe_err = e;
				pe_errseq = stof(argv(1));
			}
		}
	}
	if (pe_due && cltime >= pe_due)
	{
		pe_due = 0;
		pe_cool = cltime + 60;
		PE_Write();
	}
	if (pe_send >= 0 && pe_send_wait && cltime > pe_send_t + 10)
	{
		print("prederr: the server stopped answering; report not sent\n");
		pe_sent_ok = -1;
		PE_SendStop();
	}
};

// The context file, then the ring, in chunks after a begin line.
float(string stem) PE_Pack =
{
	local float f, k, rows;
	local string ln, cur, path;
	if (pe_send >= 0)
		buf_del(pe_send);
	pe_send = buf_create();
	bufstr_add(pe_send, "begin", TRUE);        // chunk 0, rewritten below
	cur = "";
	rows = 0;
	for (k = 0; k < 2; k = k + 1)
	{
		path = (k == 0) ? strcat("data/prederr/", stem, "_ctx.txt") : strcat("data/prederr/", stem, ".txt");
		f = fopen(path, FILE_READ);
		if (f < 0)
			continue;
		cur = strcat(cur, (k == 0) ? "== context\n" : "== ring\n");
		for (ln = fgets(f); ln; ln = fgets(f))
		{
			ln = substring(ln, 0, PE_CHUNK - 64);
			if (strlen(cur) + strlen(ln) + 1 > PE_CHUNK)
			{
				bufstr_add(pe_send, cur, TRUE);
				cur = "";
			}
			cur = strcat(cur, ln, "\n");
			rows = rows + 1;
		}
		fclose(f);
	}
	if (cur != "")
		bufstr_add(pe_send, cur, TRUE);
	pe_send_n = buf_getsize(pe_send);
	if (rows == 0 || pe_send_n > PE_MAXCHUNKS)
	{
		buf_del(pe_send);
		pe_send = -1;
		return FALSE;
	}
	bufstr_set(pe_send, 0, sprintf("begin %s %.0f %.0f %.0f", stem, pe_send_n - 1, pe_name_err, pe_name_seq));
	return TRUE;
};

void() PE_SendNext =
{
	sendevent("pe", "fs", pe_send_i, bufstr_get(pe_send, pe_send_i));
	pe_send_i = pe_send_i + 1;
	pe_send_wait = TRUE;
	pe_send_t = cltime;
	pe_box_end = max(pe_box_end, cltime + 5);   // up for as long as it sends
};

// Only while the box is asking: a server can stuffcmd prederr_send.
void() PE_Send =
{
	if (pe_box_end <= cltime || pe_name == "" || pe_send >= 0 || pe_sent_ok == 1 || PE_Local())
		return;
	if (!PE_Pack(pe_name))
	{
		print("prederr: nothing to send\n");
		pe_sent_ok = -1;
		return;
	}
	pe_send_i = 0;
	pe_sent_ok = 0;
	pe_box_end = max(pe_box_end, cltime + 20);
	PE_SendNext();
};

float(string cmd) PE_ConsoleCommand =
{
	tokenize(cmd);
	if (argv(0) == "prederr_send")
	{
		PE_Send();
		return TRUE;
	}
	if (argv(0) != "prederr_ack")
		return FALSE;
	if (pe_send < 0)
		return TRUE;
	if (argv(1) == "refused")
	{
		print(sprintf("prederr: the lobby did not take the report (%s)\n", argv(2)));
		pe_sent_ok = -1;
		PE_SendStop();
		return TRUE;
	}
	if (stof(argv(1)) != pe_send_i - 1)
		return TRUE;
	pe_send_wait = FALSE;
	if (pe_send_i < pe_send_n)
	{
		PE_SendNext();
		return TRUE;
	}
	pe_sent_ok = 1;
	pe_box_end = cltime + 4;
	print("prederr: report sent, thank you\n");
	PE_SendStop();
	return TRUE;
};

float() PE_BoxUp =
{
	return pe_box_end > cltime && !rec_sb_open;
};

float(float scanx) PE_Key =
{
	if (scanx != K_F6 || !PE_BoxUp() || pe_send >= 0 || pe_sent_ok == 1)
		return FALSE;
	PE_Send();
	return TRUE;
};

void(vector scr) PE_Draw =
{
	local vector p;
	local float sc, w, h, hh, lsz, y;
	local string st;
	if (!PE_BoxUp())
		return;
	sc = ui_cv_scale;
	Font_Set(ui_font_ui);
	lsz = Font_Px(8 * sc);
	h = 14 * sc;
	hh = 15 * sc;                       // P1221: the digit menus' header band and rule (SaveLoc_Draw)
	w = 160 * sc;
	p = [scr_x - w - 8 * sc, scr_y * 0.42, 0];
	_sui_round_draw(p, [w, 3 * sc + hh + 3 * h + 3 * sc, 0], 5 * sc, SUI_THEME_PANEL, 0.90);
	y = p_y + 3 * sc;
	HUD_Text([p_x + 6 * sc, y + (hh - 2 * sc - lsz) * 0.5], "Prediction error", lsz, SUI_THEME_TEXT, 1);
	HUD_TextR([p_x + w - 6 * sc, y + (hh - 2 * sc - lsz) * 0.5], sprintf("%gs", ceil(max(0, pe_box_end - cltime))),
	          lsz, SUI_THEME_WARN, 1);
	drawfill([p_x + 4 * sc, y + hh - 2 * sc, 0], [w - 8 * sc, 1, 0], SUI_THEME_EDGE_HI, 0.7, 0);
	y = y + hh;
	HUD_Text([p_x + 6 * sc, y + (h - lsz) * 0.5], sprintf("%.0f units off", pe_box_err), lsz, SUI_THEME_DIM, 1);
	y = y + h;
	if (pe_sent_ok == 1)
		st = "sent -- thank you";
	else if (pe_sent_ok == -1)
		st = "not sent (see console)";
	else if (pe_send >= 0)
		st = sprintf("sending %g of %g...", pe_send_i, pe_send_n);
	else
		st = "kept the last few seconds";
	HUD_Text([p_x + 6 * sc, y + (h - lsz) * 0.5], st, lsz, SUI_THEME_DIM, 1);
	y = y + h;
	KeyMenu_Row([p_x, y], w, h, "F6", "Send report to the lobby",
	            (pe_send >= 0 || pe_sent_ok == 1) ? KM_INERT : KM_HOT, lsz, sc);
	Font_Reset();
};
