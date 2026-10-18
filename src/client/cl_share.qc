/*
===========================================================================
  cl_share.qc -- Patch 777: paint and saves for the player you look at.

  `share` (F) picks the player nearest your crosshair and opens a card:
  1 paint together (both see both, live), 2 send my paint (this map's saved
  layout, else what is up), 3 send my selected save.  The other player gets
  a card of their own and answers F3 / F4 (`share yes` / `share no`); the
  server (sv_share.qc) moves nothing until they do.

      share [yes|no|stop [slot]|status]
      share paint|layout|save <slot>     the card's three rows, by slot

  The server's half arrives as stuffcmds (share_ask, share_cancel, share_link,
  share_send: numbers only) and the discs as SVC_CGAMEPACKET, CSQC_Parse_Event.
===========================================================================
*/
#define SH_LIVE    1
#define SH_LAYOUT  2
#define SH_SAVE    3
#define SH_EV_DISC  1      // live, or a live share's first dump: the sender's
#define SH_EV_END   2
#define SH_EV_LDISC 3      // a layout you took: yours now
#define SH_EV_LINK  4      // painting together with a slot began or ended
#define SH_EV_GOT   5      // events the server has had from you
#define SH_SLOTS   32
#define SH_LIVEPS  60       // live discs a second, at most
/*
  The reliable channel carries about one 1428-byte packet a round trip, and what
  queues past that is cleared with an "overflow" (net_chan.c), taking any other
  command with it.  So no more than SH_TXWIN events (~1 KB) go out that the server
  has not confirmed (SH_EV_GOT), whatever the ping: pacing by the scoreboard's ping
  still overflowed once at +300 ms (review rounds 1-2).  A stream is also paced to the
  receiver's ping, so the server's window for them (sv_share.qc SH_RXWIN) seldom fills.
*/
#define SH_TXWIN   20
#define SH_RXDISCS 26       // relayed discs a receiver takes a round trip (~700 bytes)
#define SH_MAXPS   250      // streamed discs a second, at most: the server drops past 300
#define SH_ACKN    32       // you acknowledge every so many events, or half a second
#define SH_SMAX    8192     // discs one stream carries
#define SH_CARD    10       // seconds the share card stays up

float sh_pick;              // `share` was pressed: Share_Frame looks for whom
float sh_to, sh_toend;      // the share card: slot + 1, and until when
float sh_ton;               // ...the paint row's count when it opened
float sh_from, sh_fkind, sh_fn, sh_fend;    // an offer to us: slot + 1, kind, count, until
float sh_link[SH_SLOTS];
float sh_nlink;
float sh_rx[SH_SLOTS];      // discs received from each slot this map
float *sh_buf;              // the stream going out, PD_N a disc
float sh_bn, sh_bi, sh_bto, sh_bkind;
float sh_bid;               // ...the layout offer it answers
float sh_q[8], sh_qid[8];   // streams waiting: (slot + 1) * 10 + kind, and the offer
float sh_qn;
float sh_sent, sh_got, sh_gott;     // events sent; the server's count of them; when the window last moved
float sh_lost;              // events written off by a stalled window (the server never counts them)
float sh_ltok, sh_ltokt, sh_rtok, sh_rtokt;     // live discs; discs the stream's receiver has room for
float sh_rxtot, sh_rxack, sh_ackt;  // events the server wrote you; the count you acknowledged
float sh_fid;               // the offer the card shows (sv_share.qc sh_id)
float sh_rxs[SH_SLOTS];     // discs from each slot since its last end marker
string sh_note;
float sh_noteend;
float sh_kmine;             // keys a card took: their repeats stay the card's

void() Share_RegisterCvars =
{
	registercommand("share");
	registercommand("share_ask");
	registercommand("share_cancel");
	registercommand("share_send");
	registercvar("share_offers", "1", CVAR_ARCHIVE);    // 0: every offer is declined unseen
};

string(float slot) Share_Name =
{
	local string n;

	n = getplayerkeyvalue(slot, "name");
	return (n == "") ? sprintf("player %g", slot + 1) : n;
};

void(string s) Share_Note =
{
	if (sh_note)
		strunzone(sh_note);
	sh_note = strzone(s);
	sh_noteend = cltime + 3;
	print(strcat("share: ", s, "\n"));
};

void() Share_WorldLoaded =
{
	local float i;

	for (i = 0; i < SH_SLOTS; i = i + 1)
	{
		sh_link[i] = 0;
		sh_rx[i] = 0;
		sh_rxs[i] = 0;
	}
	sh_nlink = sh_to = sh_from = sh_pick = 0;
	sh_bto = sh_qn = 0;
	sh_sent = sh_got = sh_lost = sh_rxtot = sh_rxack = 0;
};

vector(vector col, float size, float alpha) Share_Pack =
{
	return [rint(bound(0, col_x, 1) * 255) * 65536 + rint(bound(0, col_y, 1) * 255) * 256
	        + rint(bound(0, col_z, 1) * 255), rint(size), alpha];
};

// What `send my paint` would send: the saved layout, else what is up.
float() Share_PaintCount =
{
	local float n;

	n = Paint_LayoutCount();
	if (n >= 0)
		return n;
	return Paint_Count() + Paint_Waiting();
};

// `id` is the layout offer a stream answers (0 for a live share's dump).
void(float slot, float kind, float id) Share_Queue =
{
	local float i, v;

	v = (slot + 1) * 10 + kind;
	if (sh_bto == slot + 1 && sh_bkind == kind && sh_bid == id)
		return;
	for (i = 0; i < sh_qn; i = i + 1)
		if (sh_q[i] == v && sh_qid[i] == id)
			return;
	if (sh_qn < 8)
	{
		sh_q[sh_qn] = v;
		sh_qid[sh_qn] = id;
		sh_qn = sh_qn + 1;
	}
};

void() Share_StreamNext =
{
	local float v, i, kind;

	sh_bto = 0;
	if (!sh_qn)
		return;
	v = sh_q[0];
	sh_bid = sh_qid[0];
	for (i = 1; i < sh_qn; i = i + 1)
	{
		sh_q[i - 1] = sh_q[i];
		sh_qid[i - 1] = sh_qid[i];
	}
	sh_qn = sh_qn - 1;
	kind = v - 10 * floor(v / 10);
	if (!sh_buf)
		sh_buf = memalloc(SH_SMAX * PD_N * 4);
	sh_bn = Paint_Copy(sh_buf, SH_SMAX, kind == SH_LAYOUT, kind == SH_LIVE);
	if (kind == SH_LIVE && !sh_bn)
	{
		Share_StreamNext();         // nothing up yet: no dump, and no "0 marks" line
		return;
	}
	sh_bi = 0;
	sh_bto = floor(v / 10);
	sh_bkind = kind;
	sh_rtok = 0;
	sh_rtokt = cltime;
	if (kind == SH_LAYOUT)
		Share_Note(sprintf("sending %g marks to %s", sh_bn, Share_Name(sh_bto - 1)));
};

// A slot's round trip, from the scoreboard's ping.
float(float slot) Share_Rtt = { return max(0.04, stof(getplayerkeyvalue(slot, "ping")) / 1000 + 0.02); };

/*
  Room for one more event in the window, which counts from the moment it was
  last empty or moved.  One full for 5 s (events lost to some other overflow) is
  written off: the server will never count those, so they stay out of the sum.
*/
float() Share_TxRoom =
{
	local float out;

	out = sh_sent - sh_lost - sh_got;
	if (out <= 0)
		sh_gott = cltime;
	if (out < SH_TXWIN)
		return TRUE;
	if (cltime - sh_gott > 5)
	{
		sh_lost = sh_sent - sh_got;
		sh_gott = cltime;
		return TRUE;
	}
	return FALSE;
};

// Paced to the window and the receiver's ping, then the end marker it counts by.
// The target code is sv_share.qc's Share_StreamTo: slot, + 64 and the offer for a layout.
void() Share_StreamStep =
{
	local float j, to;

	if (!sh_bto)
	{
		Share_StreamNext();
		if (!sh_bto)
			return;
	}
	// A live share that ended mid-stream: its dump is nobody's now.
	if (sh_bkind == SH_LIVE && !sh_link[sh_bto - 1])
	{
		Share_StreamNext();
		return;
	}
	sh_rtok = min(8, sh_rtok + bound(0, cltime - sh_rtokt, 0.5) * min(SH_MAXPS, SH_RXDISCS / Share_Rtt(sh_bto - 1)));
	sh_rtokt = cltime;
	to = sh_bto - 1;
	if (sh_bkind == SH_LAYOUT)
		to = to + 64 + 128 * (sh_bid % 65536);
	while (sh_rtok >= 1 && sh_bi < sh_bn && Share_TxRoom())
	{
		j = sh_bi * PD_N;
		sendevent("pl", "fvvv", to, Paint_O(sh_buf, j), Paint_N(sh_buf, j),
		          Share_Pack(Paint_C(sh_buf, j), sh_buf[j + 9], sh_buf[j + 10]));
		sh_sent = sh_sent + 1;
		sh_bi = sh_bi + 1;
		sh_rtok = sh_rtok - 1;
	}
	if (sh_bi >= sh_bn && Share_TxRoom())
	{
		sendevent("ple", "ff", to, sh_bn);
		sh_sent = sh_sent + 1;
		Share_StreamNext();
	}
};

// A disc you just painted (Paint_At): to everyone painting with you.
void(vector o, vector n, vector col, float size, float alpha) Share_OnPaint =
{
	if (!sh_nlink)
		return;
	sh_ltok = min(SH_LIVEPS, sh_ltok + (cltime - sh_ltokt) * SH_LIVEPS);
	sh_ltokt = cltime;
	if (sh_ltok < 1 || !Share_TxRoom())
		return;                     // a faster spray than the share carries: some stay yours
	sh_ltok = sh_ltok - 1;
	sendevent("pd", "vvv", o, n, Share_Pack(col, size, alpha));
	sh_sent = sh_sent + 1;
};

/*
  Painting together with a slot began or ended (SH_EV_LINK).  An event, not a
  stuffcmd: it is parsed in order with the discs behind it, where a stuffcmd ran a
  frame later and its drop ate the dump's first discs (review round 2).
*/
void(float slot, float on) Share_SetLinked =
{
	if (slot < 0 || slot >= SH_SLOTS)
		return;
	if (sh_link[slot] != on)
		sh_nlink = sh_nlink + (on ? 1 : -1);
	sh_link[slot] = on;
	if (on)
	{
		Share_Note(sprintf("painting together with %s", Share_Name(slot)));
		Paint_DropFrom(slot + 1);       // their dump brings it again: no copies on a re-link
		sh_rxs[slot] = 0;
		Share_Queue(slot, SH_LIVE, 0);  // what you have up so far
	}
};

void() CSQC_Parse_Event =
{
	local float t, from, cnt;
	local vector o, n, c;
	local float size, alpha;

	t = readbyte();
	if (t == SH_EV_GOT)
	{
		cnt = readlong();
		if (cnt > sh_got)
			sh_gott = cltime;
		sh_got = max(sh_got, cnt);
		return;
	}
	if (t == SH_EV_LINK)
	{
		from = readbyte();
		Share_SetLinked(from, readbyte() != 0);
		return;
	}
	sh_rxtot = sh_rxtot + 1;        // a disc or an end marker: what the server windows
	if (t == SH_EV_DISC || t == SH_EV_LDISC)
	{
		from = readbyte();
		o_x = readfloat();
		o_y = readfloat();
		o_z = readfloat();
		n_x = readchar();
		n_y = readchar();
		n_z = readchar();
		c_x = readbyte();
		c_y = readbyte();
		c_z = readbyte();
		size = readbyte();
		alpha = readbyte() / 255;
		if (from < SH_SLOTS)
		{
			sh_rx[from] = sh_rx[from] + 1;
			sh_rxs[from] = sh_rxs[from] + 1;
		}
		if (n != '0 0 0')
			Paint_Receive(o, normalize(n), c * (1 / 255), size, alpha, (t == SH_EV_LDISC) ? 0 : from + 1);
	}
	else if (t == SH_EV_END)
	{
		from = readbyte();
		cnt = readlong();
		// Only for discs that came: an end marker alone says nothing (review round 1).
		if (from < SH_SLOTS && sh_rxs[from] > 0)
		{
			if (sh_rxs[from] >= cnt)
				Share_Note(sprintf("%s sent you %g marks", Share_Name(from), cnt));
			else
				Share_Note(sprintf("%s sent you %g marks, %g arrived", Share_Name(from), cnt, sh_rxs[from]));
			sh_rxs[from] = 0;
		}
	}
	else
		error(sprintf("CSQC_Parse_Event: unknown event %g\n", t));
};

/*
  The player under the crosshair: the streamed lobby body when there is one, the
  engine's entity otherwise.  Nearest the line of sight by angle, within about
  3.5 degrees or a body's width, and not behind a wall.  -1 for nobody.
*/
float() Share_Pick =
{
	local vector eye, fw, c, d;
	local float s, along, perp, sc, best, bs, act;
	local entity b;

	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fw = v_forward;
	bs = -1;
	best = 1;
	for (s = 0; s < maxclients && s < SH_SLOTS; s = s + 1)
	{
		if (s == player_localnum || getplayerkeyvalue(s, "name") == "")
			continue;
		b = Body_Find(s);
		act = getentity(s + 1, GE_ACTIVE);
		c = getentity(s + 1, GE_ORIGIN);
		if (b != world)
			c = b.pb_rorg;
		else if (!act)
			continue;
		c = c + '0 0 36';
		d = c - eye;
		along = d * fw;
		if (along < 16 || along > 8192)
			continue;
		perp = vlen(d - fw * along);
		if (perp > max(36, along * 0.06))
			continue;
		traceline(eye, c, MOVE_NOMONSTERS, world);
		if (trace_fraction < 1 && vlen(trace_endpos - c) > 48)
			continue;
		sc = perp / along;
		if (sc < best)
		{
			best = sc;
			bs = s;
		}
	}
	return bs;
};

void(float slot, float kind) Share_Offer =
{
	local float n;

	n = 0;
	if (kind == SH_LAYOUT)
	{
		n = Share_PaintCount();
		if (n <= 0)
		{
			Share_Note("nothing to send: paint, or load a layout, first");
			return;
		}
	}
	localcmd(sprintf("cmd share offer %g %g %g\n", slot, kind, n));
};

void(float yes) Share_Answer =
{
	if (!sh_from)
		return;
	localcmd(sprintf("cmd share answer %g %g\n", yes ? 1 : 0, sh_fid));
	sh_from = 0;
};

// A row of the share card, by number.
void(float row) Share_Choose =
{
	local float slot;

	slot = sh_to - 1;
	sh_to = 0;
	if (row == 1)
	{
		if (sh_link[slot])
			localcmd(sprintf("cmd share stop %g\n", slot));
		else
			Share_Offer(slot, SH_LIVE);
	}
	else if (row == 2)
		Share_Offer(slot, SH_LAYOUT);
	else if (row == 3)
		Share_Offer(slot, SH_SAVE);
};

// After the camera is final (CSQC_UpdateView): the pick, the stream, the cards' clocks.
void() Share_Frame =
{
	local float s;

	if (sh_pick)
	{
		sh_pick = FALSE;
		s = Share_Pick();
		if (s < 0)
			Share_Note("look at a player to share with them");
		else
		{
			sh_to = s + 1;
			sh_toend = cltime + SH_CARD;
			sh_ton = Share_PaintCount();
		}
	}
	if (sh_to && cltime > sh_toend)
		sh_to = 0;
	if (sh_from && cltime > sh_fend)
		sh_from = 0;
	if (sh_bto || sh_qn)
		Share_StreamStep();
	// The server's window for you moves on these (sv_share.qc SH_RXWIN).
	if (sh_rxtot > sh_rxack)
	if (sh_rxtot - sh_rxack >= SH_ACKN || cltime > sh_ackt + 0.5)
	{
		localcmd(sprintf("cmd share ack %g\n", sh_rxtot));
		sh_rxack = sh_rxtot;
		sh_ackt = cltime;
	}
};

float(float scan) Share_KeyBit =
{
	if (scan == '0') return 0;
	if (scan == '1') return 1;
	if (scan == '2') return 2;
	if (scan == '3') return 3;
	if (scan == K_F3) return 4;
	if (scan == K_F4) return 5;
	if (scan == K_ESCAPE) return 6;
	return -1;
};

// Every key event, before the chain (observes): a taken key is the card's until it comes up.
void(float evtype, float scan) Share_Track =
{
	local float b;

	if (evtype != IE_KEYUP)
		return;
	b = Share_KeyBit(scan);
	if (b >= 0)
		sh_kmine = sh_kmine - (sh_kmine & bitshift(1, b));
};

// Key-downs, after the vote box: the cards' keys while a card is up.
float(float scan) Share_Key =
{
	local float b, bit;

	b = Share_KeyBit(scan);
	if (b < 0)
		return FALSE;
	bit = bitshift(1, b);
	if (sh_kmine & bit)
		return TRUE;
	if (sh_from && (scan == K_F3 || scan == K_F4))
	{
		Share_Answer(scan == K_F3);
		sh_kmine = sh_kmine | bit;
		return TRUE;
	}
	if (!sh_to || scan == K_F3 || scan == K_F4)
		return FALSE;
	if (scan == '0' || scan == K_ESCAPE)
		sh_to = 0;
	else
		Share_Choose(b);
	sh_kmine = sh_kmine | bit;
	return TRUE;
};

void(vector scr) Share_Draw =
{
	local vector p;
	local float sc, w, h, hh, lsz, ssz, y, slot, idx, cnt, rows;
	local string t, l;

	l = "";
	sc  = ui_cv_scale;
	if (sh_note && cltime < sh_noteend)
	{
		Font_Set(ui_font_ui);
		lsz = Font_Px(8 * sc);
		HUD_Text([(scr_x - stringwidth(sh_note, TRUE, [lsz, lsz])) * 0.5, scr_y * 0.4], sh_note, lsz,
		         SUI_THEME_TEXT, min(1, (sh_noteend - cltime) * 2));
		Font_Reset();
	}
	if (!sh_to && !sh_from)
		return;

	Font_Set(ui_font_ui);
	lsz = Font_Px(8 * sc);
	ssz = Font_Px(6 * sc);
	h   = 14 * sc;
	hh  = 15 * sc;
	w   = 150 * sc;
	if (sh_from)
	{
		slot = sh_from - 1;
		if (sh_fkind == SH_LIVE)
			l = "wants to paint together";
		else if (sh_fkind == SH_LAYOUT)
			l = sprintf("sends you their paint (%g marks)", sh_fn);
		else
			l = sprintf("sends you a save (%g u/s)", sh_fn);
		rows = 2;
		t = Share_Name(slot);
	}
	else
	{
		slot = sh_to - 1;
		rows = 3;
		t = strcat("Share with ", Share_Name(slot));
	}
	w = max(w, stringwidth(t, TRUE, [lsz, lsz]) + 40 * sc);
	p = [(scr_x - w) * 0.5, scr_y * 0.72, 0];       // under the speed readout
	_sui_round_draw(p, [w, 3 * sc + hh + (sh_from ? h : 0) + rows * h + 3 * sc + ssz + 4 * sc, 0], 5 * sc,
	                SUI_THEME_PANEL, 0.9);
	y = p_y + 3 * sc;
	HUD_Text([p_x + 6 * sc, y + (hh - 2 * sc - lsz) * 0.5], t, lsz, SUI_THEME_TEXT, 1);
	HUD_TextR([p_x + w - 6 * sc, y + (hh - 2 * sc - lsz) * 0.5],
	          sprintf("%gs", ceil(max(0, (sh_from ? sh_fend : sh_toend) - cltime))), lsz, SUI_THEME_WARN, 1);
	drawfill([p_x + 4 * sc, y + hh - 2 * sc, 0], [w - 8 * sc, 1, 0], SUI_THEME_EDGE_HI, 0.7, 0);
	y = y + hh;
	if (sh_from)
	{
		HUD_Text([p_x + 6 * sc, y + (h - sc - lsz) * 0.5], l, lsz, SUI_THEME_DIM, 1);
		y = y + h;
		KeyMenu_Row([p_x, y], w, h, "F3", "Accept", KM_HOT, lsz, sc);
		y = y + h;
		KeyMenu_Row([p_x, y], w, h, "F4", "Decline", KM_NORMAL, lsz, sc);
		y = y + h;
		l = "or `share yes` / `share no`";
	}
	else
	{
		KeyMenu_Row([p_x, y], w, h, "1", sh_link[slot] ? "Stop painting together" : "Paint together",
		            KM_NORMAL, lsz, sc);
		y = y + h;
		KeyMenu_Row([p_x, y], w, h, "2", sprintf("Send my paint (%g)", max(0, sh_ton)),
		            sh_ton > 0 ? KM_NORMAL : KM_INERT, lsz, sc);
		y = y + h;
		idx = getstatf(STAT_FS_SAVEINDEX);
		cnt = getstatf(STAT_FS_SAVECOUNT);
		KeyMenu_Row([p_x, y], w, h, "3", idx >= 1 ? sprintf("Send save %g/%g", idx, cnt) : "Send save (none)",
		            idx >= 1 ? KM_NORMAL : KM_INERT, lsz, sc);
		y = y + h;
		l = "0 close";
	}
	y = y + 3 * sc;
	HUD_Text([p_x + 6 * sc, y], l, ssz, SUI_THEME_MUTED, 1);
	Font_Reset();
};

void() Share_Status =
{
	local float i;
	local string s;

	print(sprintf("share: you are slot %g\n", player_localnum));
	s = "";
	for (i = 0; i < SH_SLOTS; i = i + 1)
		if (sh_link[i])
			s = strcat(s, " ", Share_Name(i));
	print(sprintf("share: painting with%s; card %g, offer from %g kind %g n %g\n",
	              s == "" ? " nobody" : s, sh_to - 1, sh_from - 1, sh_fkind, sh_fn));
	s = "";
	for (i = 0; i < SH_SLOTS; i = i + 1)
		if (sh_rx[i])
			s = strcat(s, sprintf(" %g from %s", sh_rx[i], Share_Name(i)));
	print(sprintf("share: received%s; stream to %g kind %g at %g/%g, %g queued\n",
	              s == "" ? " nothing" : s, sh_bto - 1, sh_bkind, sh_bi, sh_bn, sh_qn));
	print(sprintf("share: %g sent, %g confirmed, %g written off; the receiver's round trip %g ms; %g had, %g acknowledged\n",
	              sh_sent, sh_got, sh_lost, sh_bto ? rint(Share_Rtt(sh_bto - 1) * 1000) : -1, sh_rxtot, sh_rxack));
};

float(string cmd) Share_ConsoleCommand =
{
	local string c, v;
	local float slot;

	c = argv(0);
	if (c == "share")
	{
		v = argv(1);
		if (v == "" || v == "pick")
		{
			if (sh_to)
				sh_to = 0;
			else
				sh_pick = TRUE;
		}
		else if (v == "yes" || v == "no")
			Share_Answer(v == "yes");
		else if (v == "stop")
			localcmd(argv(2) == "" ? "cmd share stop\n" : sprintf("cmd share stop %g\n", stof(argv(2))));
		else if (v == "status")
		{
			Share_Status();
			localcmd("cmd share status\n");
		}
		else if (v == "paint" || v == "layout" || v == "save")
			Share_Offer(stof(argv(2)), v == "paint" ? SH_LIVE : (v == "layout" ? SH_LAYOUT : SH_SAVE));
		else
			print("share [yes|no|stop [slot]|status], share paint|layout|save <slot>\n");
		return TRUE;
	}
	// The server's half (sv_share.qc): numbers only.
	if (c == "share_ask")
	{
		if (!cvar("share_offers"))
		{
			localcmd(sprintf("cmd share answer 0 %g\n", stof(argv(5))));
			return TRUE;
		}
		sh_fid = stof(argv(5));
		sh_from = stof(argv(1)) + 1;
		sh_fkind = stof(argv(2));
		sh_fn = stof(argv(3));
		sh_fend = cltime + bound(1, stof(argv(4)), 60);
		return TRUE;
	}
	if (c == "share_cancel")
	{
		sh_from = 0;
		return TRUE;
	}
	if (c == "share_send")
	{
		slot = stof(argv(1));
		if (slot >= 0 && slot < SH_SLOTS && slot == floor(slot))
			Share_Queue(slot, SH_LAYOUT, stof(argv(2)));
		return TRUE;
	}
	return FALSE;
};
