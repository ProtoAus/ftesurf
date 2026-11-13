/*
  Patch 1195: prederror reports.  The engine's snap-back meter (cl_prederror, Patch 335) bumps
  cl_prederror_count; a line of cl_prederr_report units or more starts a report.  1.5 s later the
  engine dumps its comparison ring (prederr_dump) and this file writes the context beside it, both
  in data/prederr/.  Then a side box offers to send them to the lobby, which stores them with its
  own header (sv_prederr.qc).  The upload rides sendevent, one chunk per server ack.
  Timers are cltime: `time` stops with the server.
*/
#define PE_RING      96
#define PE_EXPECT    16
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
float  pe_join_t;               // P1238: cltime of the last map start
float  pe_exp_t[PE_EXPECT], pe_exp_seq[PE_EXPECT];
string pe_exp_reason[PE_EXPECT]; // literal reasons; no zoned strings owned here
float  pe_exp_n, pe_exp_next;    // P1321: bounded history, not just the newest pending reset
string pe_exp_why;              // the reason belonging to the matching request

// P1403: one row per acknowledged snapshot, taken where prediction starts from it (the first command
// after the ack, before its move): when, which command it acknowledged, the newest sent, its state.
#define PE_AKS 512
float  pe_ak_rt[PE_AKS], pe_ak_t[PE_AKS], pe_ak_ack[PE_AKS], pe_ak_sent[PE_AKS], pe_ak_gp[PE_AKS];
vector pe_ak_org[PE_AKS], pe_ak_vel[PE_AKS];
float  pe_ak_n;
var float pe_ak_last = -1;
// P1405: the published name (*tn) per ack row, as a generation into the last 8 names (0 = never renamed),
// so a replay restores the name in effect where it starts (review 2: the header's is 1.5 s after the error).
float  pe_ak_gen[PE_AKS];
float  pe_nm_gen;
string pe_nm_cur;
string pe_nm_name[8];
float  pe_nm_g[8];

// P1404: a report's commands replayed on a rig (tools/prederr_replay.py writes the file); the lobby
// sets the recorded state before command pe_rp_s (pe_state, sv_cheats only), then each command
// carries its row's angles, moves and buttons.
#define PE_RPMAX 1024
float  pe_rp_n, pe_rp_s, pe_rp_on, pe_rp_auto;
float  pe_rp_btn[PE_RPMAX], pe_rp_imp[PE_RPMAX], pe_rp_ms[PE_RPMAX];
vector pe_rp_ang[PE_RPMAX], pe_rp_mv[PE_RPMAX];

void() PE_RegisterCvars =
{
	registercvar("cl_prederr_report", "32", CVAR_ARCHIVE);   // units; 0 = no reports
	registercvar("cl_prederr_ask", "1", CVAR_ARCHIVE);       // 0 = keep them locally, never ask
	registercommand("prederr_ack");
	registercommand("prederr_send");
	registercommand("pe_replay");       // P1404
	registercvar("pe_replay_auto", "");  // P1404: a file to replay once in the map (tools/prederr_replay.py)
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
	if (pe_rp_on)                       // P1404: the replay driver grades the report decision too
		print(sprintf("pe note %.0f: %s\n", clientcommandframe, s));
};

// P1403: CSQC_PredictPlayerPreMove on the chain's first command; predinput_* is the acknowledged state.
void(float ack) PE_AckSnap =
{
	local float k, g;
	local string nm;
	if (ack == pe_ak_last)
		return;
	if (pe_ak_last < 0)
		pe_join_t = cltime;             // the first moments run from the first snapshot (surf_4am: 20 s load)
	pe_ak_last = ack;
	k = pe_ak_n - floor(pe_ak_n / PE_AKS) * PE_AKS;
	pe_ak_rt[k]   = gettime(0);
	pe_ak_t[k]    = time;
	pe_ak_ack[k]  = ack;
	pe_ak_sent[k] = clientcommandframe;
	pe_ak_org[k]  = predinput_origin;
	pe_ak_vel[k]  = predinput_velocity;
	pe_ak_gp[k]   = predinput_onground + 2 * predinput_pmtype;
	nm = getplayerkeyvalue(player_localnum, "*tn");
	if (nm != pe_nm_cur)
	{
		pe_nm_gen = pe_nm_gen + 1;
		g = pe_nm_gen - floor(pe_nm_gen / 8) * 8;
		pe_nm_name[g] = strzone(nm);
		pe_nm_g[g] = pe_nm_gen;
		pe_nm_cur = pe_nm_name[g];
	}
	pe_ak_gen[k]  = pe_nm_gen;
	pe_ak_n = pe_ak_n + 1;
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

// P1321: a second request can precede the first request's delayed correction.
void(float when, float seq, string why) PE_ExpectAt =
{
	pe_exp_t[pe_exp_next] = when;
	pe_exp_seq[pe_exp_next] = seq;
	pe_exp_reason[pe_exp_next] = why;
	pe_exp_next = pe_exp_next + 1;
	if (pe_exp_next >= PE_EXPECT)
		pe_exp_next = 0;
	pe_exp_n = min(pe_exp_n + 1, PE_EXPECT);
};

void() PE_ResetExpected =
{
	pe_exp_n = 0;
	pe_exp_next = 0;
};

// P1238: the client asked the server for a move it does not predict (goto_spawn, a reset sent as a
// plain command); the snap that answers it is that move, not a misprediction.
void(string why) PE_Expect =
{
	PE_ExpectAt(cltime, clientcommandframe, why);
	PE_Note(sprintf("expect at cltime %.3f: %s", cltime, why));
};

// P1397: the lobby's own "noclip ON/OFF" (sv_player.qc) comes with the movement mode it just switched,
// which this client learns only from the server; the snap a command either side of it is that switch.
void(string msg) PE_ServerPrint =
{
	if (msg == "noclip ON\n" || msg == "noclip OFF\n")
	{
		PE_ExpectAt(cltime, servercommandframe - 2, "noclip turned on or off");
		PE_Note(sprintf("expect at cltime %.3f: noclip turned on or off", cltime));
	}
};

void() PE_MapReset =
{
	local float i;
	pe_join_t = cltime;
	pe_rp_on = FALSE;                   // P1404
	pe_ak_last = -1;                    // P1403
	PE_ResetExpected();
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
	return WarpOp_HookAlive();      // P1238: the gate the ops use
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
	local float f, i, i0, k;
	local vector o, v;
	f = fopen(strcat("data/prederr/", stem, "_ctx.txt"), FILE_WRITE);
	if (f < 0)
		return;
	fputs(f, "FTESURF-PREDCTX 1\n");
	fputs(f, sprintf("reporter P1321 fs_wop \"%s\" expected %g of %g\n", serverkey("fs_wop"), pe_exp_n, PE_EXPECT));
	fputs(f, sprintf("map %s\nserver %s\nlocal %s\nworst %.2f at seq %.0f\n", serverkey("map"), serverkey("ip"),
	                 strftime(TRUE, "%Y-%m-%d %H:%M:%S"), pe_err, pe_errseq));
	fputs(f, sprintf("cvars cl_netfps %s rate %s cl_maxfps %s cl_prederror %s cl_triggers %s cl_warpop %s\n",
	                 cvar_string("cl_netfps"), cvar_string("rate"), cvar_string("cl_maxfps"),
	                 cvar_string("cl_prederror"), cvar_string("cl_triggers"), cvar_string("cl_warpop")));
	fputs(f, sprintf("ping %s pl %s\n", getplayerkeyvalue(player_localnum, "ping"),
	                 getplayerkeyvalue(player_localnum, "pl")));   // P1238: packet loss %
	fputs(f, sprintf("activator name \"%s\" fs_tn \"%s\"\n", getplayerkeyvalue(player_localnum, "*tn"),
	                 serverkey("fs_tn")));   // P1405; fs_tn "" = a lobby that does not publish names
	fputs(f, "names 0 \"\"");                // the ack rows' last column: generation -> name
	for (i = 0; i < 8; i = i + 1)
		if (pe_nm_g[i] > 0)
			fputs(f, sprintf(" %g \"%s\"", pe_nm_g[i], pe_nm_name[i]));
	fputs(f, "\n");
	fputs(f, sprintf("csprogs crc %s size %s local %g qchook %s\n", serverkey("*csprogs"),
	                 serverkey("*csprogssize"), PE_Local(), cvar_string("cl_predict_qchook")));   // P1207
	fputs(f, "# context: time seq what (server prints, mirror triggers, gates, warp ops, prederr lines)\n");
	i0 = max(0, pe_ring_n - PE_RING);
	for (i = i0; i < pe_ring_n; i = i + 1)
		fputs(f, strcat(bufstr_get(pe_ring, i - floor(i / PE_RING) * PE_RING), "\n"));
	// P1403. rt: gettime(0) of the frame that first predicted from it; t: CSQC time then.
	fputs(f, "# acks: rt t ack sent org(3) vel(3) ground+2*pmtype namegen\n");
	i0 = max(0, pe_ak_n - PE_AKS);
	for (i = i0; i < pe_ak_n; i = i + 1)
	{
		k = i - floor(i / PE_AKS) * PE_AKS;
		o = pe_ak_org[k];
		v = pe_ak_vel[k];
		fputs(f, strcat(sprintf("%.4f %.3f %.0f %.0f ", pe_ak_rt[k], pe_ak_t[k], pe_ak_ack[k], pe_ak_sent[k]),
		                sprintf("%.3f %.3f %.3f ", o_x, o_y, o_z),          // a replay's start state
		                sprintf("%.3f %.3f %.3f %g %g\n", v_x, v_y, v_z, pe_ak_gp[k], pe_ak_gen[k])));
	}
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

// P1396: the predicted body is at that trigger, as the server's was when it touched (the move's end).
float(vector p, vector b0, vector b1) PE_AtTrigger =
{
	local vector mn, mx;
	mn = tg_pmins;
	mx = tg_pmaxs;
	if (mn == '0 0 0' && mx == '0 0 0')
	{
		mn = '-16 -16 0';
		mx = '16 16 62';
	}
	mn = p + mn - '32 32 32';
	mx = p + mx + '32 32 32';
	return !(mn_x > b1_x || mn_y > b1_y || mn_z > b1_z || mx_x < b0_x || mx_y < b0_y || mx_z < b0_z);
};

// P1238: the server put the body on the destination of a teleport the mirror left to it, and no
// teleport the mirror still predicts lands there (one it missed would land there too). P1396: a
// landmark teleport's landing is measured from the predicted body, which is where the server's was,
// and only at its own trigger: the offset alone matches a predicted teleport fired early (review).
float(vector srv, vector pred) PE_ServerTele =
{
	local float i, j, d, m;
	local vector at, p;
	for (i = 0; i < tg_sod_n; i = i + 1)
	{
		at = tg_sod[i];
		if (tg_sodl[i])
		{
			if (!PE_AtTrigger(pred, tg_sodmin[i], tg_sodmax[i]))
				continue;
			at = at + (pred - tg_sodlm[i]);
		}
		if (vlen(srv - at) >= 2)
			continue;
		for (j = 0; j < tg_n; j = j + 1)
			if (tg_kind[j] == TG_TELE)
			{
				if (tg_ent[j].tg_fname)
					continue;           // P1405: fires only on the published name; a stale one is the server's
				d = TT_Find(tg_target[j]);
				if (d < 0)
					continue;
				p = tt_org[d];
				m = (tg_landmark[j] != "") ? TT_Find(tg_landmark[j]) : -1;
				if (m >= 0)
					p = p + (pred - tt_org[m]);
				if (vlen(p - at) < 2)
					return FALSE;
			}
			else if (tg_kind[j] == TG_RELTELE)
			{
				if (tg_ent[j].tg_fname)
					continue;
				if (vlen(TG_RelTelePoint(j) - at) < 2)
					return FALSE;
			}
		return TRUE;
	}
	return FALSE;
};

// P1321: keep P1238's bounds for EACH request; a newer request must not overwrite an older one.
float(float seq, float now, float ping, float netfps) PE_ExpectedAt =
{
	local float i, slot;
	for (i = 1; i <= pe_exp_n; i = i + 1)
	{
		slot = pe_exp_next - i;
		if (slot < 0)
			slot = slot + PE_EXPECT;
		if (now >= pe_exp_t[slot] && now - pe_exp_t[slot] < 1 + 2 * ping
		    && seq >= pe_exp_seq[slot] - 2 && seq <= pe_exp_seq[slot] + ceil(ping * netfps) + 8)
		{
			pe_exp_why = pe_exp_reason[slot];
			return TRUE;
		}
	}
	return FALSE;
};

float(float seq) PE_Expected =
{
	local float ping;
	ping = min(stof(getplayerkeyvalue(player_localnum, "ping")) / 1000, 1);
	return PE_ExpectedAt(seq, cltime, ping, cvar("cl_netfps"));
};

void(string fn) PE_ReplayStart;

void() PE_Frame =
{
	local float c, n, e, s;
	local vector srv, pred;
	local string rp;
	if (pe_ak_last >= 0 && cltime > pe_join_t + 4 && !pe_rp_on)   // past "the first moments" (3 s)
	{
		rp = cvar_string("pe_replay_auto");
		if (rp != "")
		{
			PE_ReplayStart(rp);
			pe_rp_auto = pe_rp_on;
			cvar_set("pe_replay_auto", "");
		}
	}
	if (!pe_ok)
		return;
	c = cvar("cl_prederror_count");
	if (c != pe_count)
	{
		pe_count = c;
		n = tokenize(cvar_string("cl_prederror_last"));
		e = (n >= 9) ? stof(argv(2)) : 0;
		s = stof(argv(1));             // P1238: kept, the calls below may tokenize
		srv = (n >= 9) ? stov(sprintf("%s %s %s", argv(6), argv(7), argv(8))) : '0 0 0';
		pred = (n >= 9) ? stov(sprintf("%s %s %s", argv(3), argv(4), argv(5))) : '0 0 0';
		PE_Note(strcat("prederr ", cvar_string("cl_prederror_last")));
		if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report") && PE_Local())
			PE_Note("not reported: this PC hosts the game, so nothing is predicted");
		else if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report") && cltime - pe_join_t < 3)
			PE_Note("not reported: the first moments on the map");     // P1238: the spawn's first comparison
		else if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report") && n >= 9 && PE_Expected(s))
			PE_Note(sprintf("not reported: %s, which is not predicted", pe_exp_why));
		else if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report")
		         && (rec_gh_on || Spec_Active() || rec_wt_on || rw_on || taso_state == 1 || getstatf(STAT_FS_TASPAUSE) == 1))
			PE_Note("not reported: ghost, spectating, watching, rewinding, TAS or Jargon (nothing is predicted)");     // P1483: a takeover's pause, on stream
		else if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report") && n >= 9
		         && PE_ServerTele(srv, pred))
			PE_Note("not reported: a teleport only the server runs (its trigger is filtered or gated)");
		else if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report") && cvar("cl_predict_qchook")
		         && !PE_Predicting())
			PE_Note(sprintf("not reported: no prediction hook for %.1f s", cltime - wop_premove_t));
		else if (cvar("cl_prederr_report") > 0 && e >= cvar("cl_prederr_report"))
		{
			if (!pe_due && cltime >= pe_cool)
			{
				pe_due = cltime + 1.5;     // the commands after it go in the ring too
				pe_err = 0;
				if (!PE_Local())
					sendevent("pe_mk", "f", s);   // P1238: the lobby freezes its rows of it
			}
			if (pe_due && e > pe_err)
			{
				pe_err = e;
				pe_errseq = s;
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

// P1404: `pe_replay <file in data/prederr/>`. Line 1 "FTESURF-PEREPLAY 1", line 2 "start <report seq>
// <origin> <velocity>" (the server's state before the first row), then one row per command:
// "<report seq> <msec> <pitch> <yaw> <roll> <fwd> <side> <up> <buttons> <impulse>".
void(string fn) PE_ReplayStart =
{
	local float f, lead, n, hasnm;
	local string ln, nm;
	local vector o, v;
	if (serverkey("*cheats") != "ON")
	{
		print("pe_replay: only on a server with sv_cheats 1\n");
		return;
	}
	f = fopen(strcat("data/prederr/", fn), FILE_READ);
	if (f < 0)
	{
		print(sprintf("pe_replay: cannot open data/prederr/%s\n", fn));
		return;
	}
	ln = fgets(f);
	n = tokenize(fgets(f));
	if (ln != "FTESURF-PEREPLAY 1" || n < 8 || argv(0) != "start")
	{
		fclose(f);
		print("pe_replay: not a replay file\n");
		return;
	}
	o = [stof(argv(2)), stof(argv(3)), stof(argv(4))];
	v = [stof(argv(5)), stof(argv(6)), stof(argv(7))];
	nm = strzone((n >= 9) ? argv(8) : "");   // P1405: the activator name, if the report has one
	hasnm = (n >= 9);                         // "" included: a cleared name is restored too
	pe_rp_n = 0;
	for (ln = fgets(f); ln && pe_rp_n < PE_RPMAX; ln = fgets(f))
	{
		if (tokenize(ln) < 10)
			continue;
		pe_rp_ang[pe_rp_n] = [stof(argv(2)), stof(argv(3)), stof(argv(4))];
		pe_rp_mv[pe_rp_n]  = [stof(argv(5)), stof(argv(6)), stof(argv(7))];
		pe_rp_btn[pe_rp_n] = stof(argv(8));
		pe_rp_ms[pe_rp_n]  = stof(argv(1));
		pe_rp_imp[pe_rp_n] = stof(argv(9));
		pe_rp_n = pe_rp_n + 1;
	}
	fclose(f);
	if (!pe_rp_n)
	{
		strunzone(nm);
		print("pe_replay: no rows\n");
		return;
	}
	// the stringcmd reaches the lobby before that command, a reliable already in flight included
	lead = ceil((0.3 + 2 * stof(getplayerkeyvalue(player_localnum, "ping")) / 1000) * cvar("cl_netfps")) + 2;
	pe_rp_s = clientcommandframe + lead;
	pe_rp_on = TRUE;
	localcmd(strcat(sprintf("cmd pe_state %.0f %.3f %.3f %.3f %.3f %.3f %.3f", pe_rp_s, o_x, o_y, o_z, v_x, v_y, v_z),
	                hasnm ? sprintf(" \"%s\"\n", nm) : "\n"));
	print(sprintf("pe_replay: %g rows, state on command %.0f, name \"%s\"\n", pe_rp_n, pe_rp_s, nm));
	strunzone(nm);
};

// CSQC_Input_Frame, first: idle until the state lands, then the rows. Warp ops (201 up) are left out:
// the client predicts them from its own op state, which a raw impulse would not set.
float() PE_ReplayInputFrame =
{
	local float r;
	if (!pe_rp_on)
		return FALSE;
	if (serverkey("*cheats") != "ON")   // turned off mid-replay
	{
		pe_rp_on = FALSE;
		print("pe_replay: stopped, cheats are off\n");
		return FALSE;
	}
	r = clientcommandframe - pe_rp_s;
	input_movevalues = '0 0 0';
	input_buttons = 0;
	if (r >= pe_rp_n)
	{
		pe_rp_on = FALSE;
		print(sprintf("pe_replay: done at command %.0f\n", clientcommandframe));
		if (pe_rp_auto)                 // the driver's run: its ring, then out
			localcmd("waitms 1500\nprederr_dump replay_ring.txt\nwaitms 800\necho PEREPLAY END\nquit\n");
		return TRUE;
	}
	if (r < 0)
		return TRUE;
	input_angles     = pe_rp_ang[r];
	input_movevalues = pe_rp_mv[r];
	input_buttons    = pe_rp_btn[r];
	// the recorded duration: a rig frame hitch made 50 ms commands (cs_get_input_state reads it back once a
	// command; usercmd msec is a float here, a byte on the wire, and 15/1000*1000 comes back as 15.0)
	if (pe_rp_ms[r] > 0)
		input_timelength = pe_rp_ms[r] / 1000;
	if (pe_rp_imp[r] && pe_rp_imp[r] < 201)
		input_impulse = pe_rp_imp[r];
	return TRUE;
};

float(string cmd) PE_ConsoleCommand =
{
	tokenize(cmd);
	if (argv(0) == "pe_replay")
	{
		PE_ReplayStart(argv(1));
		return TRUE;
	}
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
