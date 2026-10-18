/*
===========================================================================
  sv_share.qc -- Patch 777: paint and saves handed from one player to another.

  The client asks (`cmd share offer <slot> <kind> <n>`), the other player
  answers (`cmd share answer 1|0 <id>`), and only then does anything move:

      1 live    both see each other's paint from now on, and what each has up
      2 layout  the sender's client streams its paint to the receiver once
      3 save    the sender's selected save becomes a practice row in the
                receiver's list (SV_SaveLocCreateAt's replay-point shape: idle
                timer, no run, velocity under `rwvel`)

  Discs arrive as sendevent ("pd" live, "pl" streamed, "ple" a stream's end;
  a streamed target is slot + 100 for a layout) and go out as SVC_CGAMEPACKET
  to that one client (cl_share.qc's CSQC_Parse_Event).  Every number is the
  server's own re-encoding of a checked float, so nothing a sender writes
  reaches a console.

  A disc goes to the receiver reliably, and a client takes about one 1400-byte
  packet a round trip while the backlog behind it is 16 x 1200 bytes; past
  that the engine drops the client (sv_nchan.c MAX_BACK_BUFFERS).  So each
  receiver gets SH_RXBYTES a round trip of relayed discs and the rest are
  dropped and counted, whoever sends them (review round 1).
===========================================================================
*/
#define SH_LIVE    1
#define SH_LAYOUT  2
#define SH_SAVE    3
#define SH_EV_DISC  1       // live, or a live share's first dump: the sender's
#define SH_EV_END   2
#define SH_EV_LDISC 3       // a layout the receiver took: theirs now
#define SH_WAIT    20       // seconds an offer stands
#define SH_RATE    300      // discs a second, per sender
#define SH_BURST   600
#define SH_DISCB   23       // a relayed disc's bytes
#define SH_RXBYTES 700      // relayed bytes a receiver takes a round trip
#define SH_RXCAP   2400
#define SH_MC_ONE  10       // MULTICAST_ONE_R_NOSPECS (q2game.h): not to whoever spectates the receiver
#define SH_ENDB    7        // an end marker's bytes
#define SH_LAYMAX  8192     // discs a layout may carry (cl_share.qc SH_SMAX)

.float sh_from;             // an offer to this player: the sender's slot + 1
.float sh_kind, sh_n, sh_until, sh_id;
.vector sh_so, sh_sv;       // the offered save, taken when it was offered
.float sh_sp, sh_sy, sh_sd;
.float sh_offerat;          // this player's last offer, for the rate
.float sh_tok, sh_tokt;     // discs this player may send
.float sh_rb, sh_rbt;       // relayed bytes this player may take
.float sh_relayed, sh_dropped, sh_rdropped;
.float sh_lastfrom, sh_lastend;     // the last offer to this player that went unanswered or was declined
float *sh_link;             // [a * FS_MAXPLAYERS + b]: live paint between two slots
float *sh_send;             // [a * FS_MAXPLAYERS + b]: until when a may stream a layout to b
float *sh_left;             // ...and how many discs b said yes to
float sh_seq;

float(entity e) Share_Slot = { return num_for_edict(e) - 1; };

entity(float slot) Share_Player =
{
	local entity e;

	if (slot < 0 || slot >= FS_MAXPLAYERS || slot != floor(slot))
		return world;
	e = edict_num(slot + 1);
	if (e.classname != "player" || clienttype(e) != CLIENTTYPE_REAL)
		return world;
	return e;
};

void() Share_Alloc =
{
	if (sh_link)
		return;
	sh_link = memalloc(sizeof(float) * FS_MAXPLAYERS * FS_MAXPLAYERS);
	sh_send = memalloc(sizeof(float) * FS_MAXPLAYERS * FS_MAXPLAYERS);
	sh_left = memalloc(sizeof(float) * FS_MAXPLAYERS * FS_MAXPLAYERS);
};

float(float a, float b) Share_Linked =
{
	if (!sh_link)
		return FALSE;
	return sh_link[a * FS_MAXPLAYERS + b];
};

float(float a, float b) Share_MaySend =
{
	if (!sh_send)
		return FALSE;
	return time < sh_send[a * FS_MAXPLAYERS + b] && sh_left[a * FS_MAXPLAYERS + b] > 0;
};

void(entity a, entity b, float on) Share_SetLink =
{
	local float sa, sb;

	Share_Alloc();
	sa = Share_Slot(a);
	sb = Share_Slot(b);
	if (sh_link[sa * FS_MAXPLAYERS + sb] == on)
		return;
	sh_link[sa * FS_MAXPLAYERS + sb] = on;
	sh_link[sb * FS_MAXPLAYERS + sa] = on;
	if (clienttype(a) == CLIENTTYPE_REAL)
		stuffcmd(a, sprintf("share_link %g %g\n", sb, on));
	if (clienttype(b) == CLIENTTYPE_REAL)
		stuffcmd(b, sprintf("share_link %g %g\n", sa, on));
};

// The offer to `t` is gone: answered, withdrawn or out of time.
void(entity t) Share_Drop =
{
	t.sh_from = 0;
	stuffcmd(t, "share_cancel\n");
};

void(entity e, float slot, float kind, float n) Share_Offer =
{
	local entity t;
	local float blk, row;

	t = Share_Player(slot);
	if (t == world || t == e)
	{
		sprint(e, PRINT_HIGH, "^3share:^7 nobody there to share with\n");
		return;
	}
	if (time < e.sh_offerat + 2)
	{
		sprint(e, PRINT_HIGH, "^3share:^7 wait a moment before asking again\n");
		return;
	}
	if (t.sh_from && time < t.sh_until)
	{
		sprint(e, PRINT_HIGH, sprintf("^3share:^7 %s has an offer up; ask again in a moment\n", t.netname));
		return;
	}
	// After a no or no answer, the same sender waits: one player cannot keep a card up.
	if (t.sh_lastfrom == Share_Slot(e) + 1 && time < t.sh_lastend + 10)
	{
		sprint(e, PRINT_HIGH, sprintf("^3share:^7 give %s a few seconds\n", t.netname));
		return;
	}
	if (!(n >= 0))
		n = 0;                      // NaN
	if (kind == SH_LIVE && Share_Linked(Share_Slot(e), slot))
	{
		sprint(e, PRINT_HIGH, sprintf("^3share:^7 already sharing paint with %s\n", t.netname));
		return;
	}
	if (kind == SH_SAVE)
	{
		blk = SL_Blk(e);
		if (!rec_sl_org || e.rec_sl_index < 1 || e.rec_sl_index > rec_sl_nb[blk])
		{
			sprint(e, PRINT_HIGH, "^3share:^7 select a save first\n");
			return;
		}
		row = SL_Base(blk) + e.rec_sl_index - 1;
		t.sh_so = rec_sl_org[row];
		t.sh_sv = rec_sl_vel[row];
		t.sh_sp = rec_sl_pit[row];
		t.sh_sy = rec_sl_yaw[row];
		t.sh_sd = rec_sl_duck[row];
		n = floor(vlen([t.sh_sv_x, t.sh_sv_y, 0]));
	}
	else if (kind != SH_LIVE && kind != SH_LAYOUT)
		return;
	e.sh_offerat = time;
	sh_seq = sh_seq + 1;
	t.sh_from = Share_Slot(e) + 1;
	t.sh_kind = kind;
	t.sh_n = bound(0, floor(n), 999999);
	t.sh_until = time + SH_WAIT;
	t.sh_id = sh_seq;
	stuffcmd(t, sprintf("share_ask %g %g %g %g %g\n", Share_Slot(e), kind, t.sh_n, SH_WAIT, sh_seq));
	sprint(e, PRINT_HIGH, sprintf("^7share: asked %s\n", t.netname));
};

// `id` is the offer the card showed: a press that crosses a newer offer answers nothing.
void(entity t, float yes, float id) Share_Answer =
{
	local entity e;
	local float kind, ok;

	if (!t.sh_from || id != t.sh_id)
	{
		sprint(t, PRINT_HIGH, "^3share:^7 that offer is gone\n");
		return;
	}
	e = Share_Player(t.sh_from - 1);
	kind = t.sh_kind;
	Share_Drop(t);
	if (e == world)
	{
		sprint(t, PRINT_HIGH, "^3share:^7 they have left\n");
		return;
	}
	if (time > t.sh_until)
	{
		sprint(t, PRINT_HIGH, "^3share:^7 that offer ran out\n");
		return;
	}
	if (!yes)
	{
		t.sh_lastfrom = Share_Slot(e) + 1;
		t.sh_lastend = time;
		sprint(e, PRINT_HIGH, sprintf("^7share: %s said no\n", t.netname));
		return;
	}
	if (kind == SH_LIVE)
	{
		Share_SetLink(e, t, 1);
		sprint(e, PRINT_HIGH, sprintf("^7share: painting with %s\n", t.netname));
		sprint(t, PRINT_HIGH, sprintf("^7share: painting with %s\n", e.netname));
	}
	else if (kind == SH_LAYOUT)
	{
		// Until the end marker; a slow link may take minutes for a big layout.
		Share_Alloc();
		sh_send[Share_Slot(e) * FS_MAXPLAYERS + Share_Slot(t)] = time + 600;
		sh_left[Share_Slot(e) * FS_MAXPLAYERS + Share_Slot(t)] = min(t.sh_n, SH_LAYMAX);
		stuffcmd(e, sprintf("share_send %g\n", Share_Slot(t)));
	}
	else if (kind == SH_SAVE)
	{
		// The replay-point row (sl_saveview): a practice placement with no run behind it.
		rw_o = t.sh_so;
		rw_v = t.sh_sv;
		rw_pit = t.sh_sp;
		rw_yaw = t.sh_sy;
		rw_dk = t.sh_sd;
		rw_t = 0;
		t.rec_sl_requesttag = 0;    // the gift answers no save ticket of the receiver's (review)
		sl_sharefrom = e.netname;
		ok = SV_SaveLocCreateAt(t, 0, '0 0 0', FALSE, FALSE, TRUE);
		sl_sharefrom = "";
		sprint(e, PRINT_HIGH, ok ? sprintf("^7share: %s has your save\n", t.netname)
		                         : sprintf("^3share:^7 %s could not take the save\n", t.netname));
	}
};

void(entity e, float slot) Share_Stop =
{
	local entity t;
	local float i;

	for (i = 0; i < FS_MAXPLAYERS; i = i + 1)
	{
		if (slot >= 0 && i != slot)
			continue;
		if (sh_send)
			sh_send[i * FS_MAXPLAYERS + Share_Slot(e)] = 0;     // a layout coming to you ends too
		if (!Share_Linked(Share_Slot(e), i))
			continue;
		t = edict_num(i + 1);
		Share_SetLink(e, t, 0);
		sprint(e, PRINT_HIGH, sprintf("^7share: stopped painting with %s\n", t.netname));
		if (clienttype(t) == CLIENTTYPE_REAL)
			sprint(t, PRINT_HIGH, sprintf("^7share: %s stopped painting with you\n", e.netname));
	}
};

void(entity e) Share_Disconnect =
{
	local entity p;
	local float me, i;

	me = Share_Slot(e);
	Share_Stop(e, -1);
	e.sh_from = e.sh_lastfrom = 0;
	e.sh_offerat = 0;
	if (sh_send)
	for (i = 0; i < FS_MAXPLAYERS; i = i + 1)
	{
		sh_send[me * FS_MAXPLAYERS + i] = 0;
		sh_send[i * FS_MAXPLAYERS + me] = 0;
		sh_left[me * FS_MAXPLAYERS + i] = 0;
		sh_left[i * FS_MAXPLAYERS + me] = 0;
	}
	p = find(world, classname, "player");
	while (p)
	{
		if (p.sh_from == me + 1)
		if (clienttype(p) == CLIENTTYPE_REAL)
			Share_Drop(p);
		if (p.sh_lastfrom == me + 1)
			p.sh_lastfrom = 0;      // whoever takes the slot next starts clean
		p = find(p, classname, "player");
	}
};

// Offers nobody answered: the card has gone on the receiver's side already.
void() Share_Frame =
{
	local entity p, e;

	p = find(world, classname, "player");
	while (p)
	{
		if (p.sh_from)
		if (time > p.sh_until)
		{
			e = Share_Player(p.sh_from - 1);
			p.sh_lastfrom = p.sh_from;
			p.sh_lastend = time;
			p.sh_from = 0;
			if (e != world)
				sprint(e, PRINT_HIGH, sprintf("^7share: %s did not answer\n", p.netname));
		}
		p = find(p, classname, "player");
	}
};

void(entity e, float cmdargc) Share_Command =
{
	local string v;

	v = argv(1);
	if (v == "offer" && cmdargc >= 4)
		Share_Offer(e, stof(argv(2)), stof(argv(3)), stof(argv(4)));
	else if (v == "answer")
		Share_Answer(e, stof(argv(2)) != 0, stof(argv(3)));
	else if (v == "stop")
		Share_Stop(e, (cmdargc >= 3) ? stof(argv(2)) : -1);
	else if (v == "status")
		sprint(e, PRINT_HIGH, sprintf("share: relayed %g, dropped %g, dropped for you %g, offer from %g kind %g\n",
		                              e.sh_relayed, e.sh_dropped, e.sh_rdropped, e.sh_from - 1, e.sh_kind));
};

/*
  One disc, checked.  `c` is the client's packing: x = 0xRRGGBB, y = size,
  z = alpha.  The sender's rate is a token bucket: past it the disc is dropped
  and counted, not queued.
*/
float(entity e, vector o, vector n, vector c) Share_Admit =
{
	if (!SV_SaveOriginSane(o))
		return FALSE;
	if (!(vlen(n) > 0.9 && vlen(n) < 1.1))
		return FALSE;
	if (!(c_x >= 0 && c_x <= 16777215 && c_y >= 1 && c_y <= 256 && c_z >= 0.04 && c_z <= 1))
		return FALSE;
	e.sh_tok = min(SH_BURST, e.sh_tok + (time - e.sh_tokt) * SH_RATE);
	e.sh_tokt = time;
	if (e.sh_tok < 1)
	{
		e.sh_dropped = e.sh_dropped + 1;
		return FALSE;
	}
	e.sh_tok = e.sh_tok - 1;
	return TRUE;
};

void(entity e, entity t, float ev, vector o, vector n, vector c) Share_Write =
{
	local float rgb, rtt;

	// The receiver's room: SH_RXBYTES a round trip of their ping.
	rtt = max(0.04, stof(infokey(t, "ping")) / 1000 + 0.02);
	t.sh_rb = min(SH_RXCAP, t.sh_rb + (time - t.sh_rbt) * SH_RXBYTES / rtt);
	t.sh_rbt = time;
	if (t.sh_rb < SH_DISCB)
	{
		e.sh_dropped = e.sh_dropped + 1;
		t.sh_rdropped = t.sh_rdropped + 1;
		return;
	}
	t.sh_rb = t.sh_rb - SH_DISCB;
	n = normalize(n);
	rgb = floor(c_x);
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, ev);
	WriteByte(MSG_MULTICAST, Share_Slot(e));
	WriteFloat(MSG_MULTICAST, o_x);
	WriteFloat(MSG_MULTICAST, o_y);
	WriteFloat(MSG_MULTICAST, o_z);
	WriteChar(MSG_MULTICAST, rint(n_x * 127));
	WriteChar(MSG_MULTICAST, rint(n_y * 127));
	WriteChar(MSG_MULTICAST, rint(n_z * 127));
	WriteByte(MSG_MULTICAST, floor(rgb / 65536));
	WriteByte(MSG_MULTICAST, floor(rgb / 256) & 255);
	WriteByte(MSG_MULTICAST, rgb & 255);
	WriteByte(MSG_MULTICAST, min(255, floor(c_y)));
	WriteByte(MSG_MULTICAST, rint(c_z * 255));
	msg_entity = t;
	multicast('0 0 0', SH_MC_ONE);
	e.sh_relayed = e.sh_relayed + 1;
};

// A disc just painted: to everyone painting with this player.
void(vector o, vector n, vector c) CSEv_pd_vvv =
{
	local float me, i;
	local entity t;

	me = Share_Slot(self);
	if (!sh_link || me < 0 || me >= FS_MAXPLAYERS)
		return;
	if (!Share_Admit(self, o, n, c))
		return;
	for (i = 0; i < FS_MAXPLAYERS; i = i + 1)
		if (sh_link[me * FS_MAXPLAYERS + i])
		{
			t = Share_Player(i);
			if (t != world)
				Share_Write(self, t, SH_EV_DISC, o, n, c);
		}
};

/*
  A streamed disc for one player: `to` is their slot for this player's paint so
  far when a live share began, slot + 100 for a layout they said yes to.
*/
void(float to, vector o, vector n, vector c) CSEv_pl_fvvv =
{
	local entity t;
	local float layout;

	layout = (to >= 100);
	if (layout)
		to = to - 100;
	t = Share_Player(to);
	if (t == world)
		return;
	if (layout ? !Share_MaySend(Share_Slot(self), to) : !Share_Linked(Share_Slot(self), to))
		return;
	if (!Share_Admit(self, o, n, c))
		return;
	if (layout)
		sh_left[Share_Slot(self) * FS_MAXPLAYERS + to] = sh_left[Share_Slot(self) * FS_MAXPLAYERS + to] - 1;
	Share_Write(self, t, layout ? SH_EV_LDISC : SH_EV_DISC, o, n, c);
};

void(float to, float count) CSEv_ple_ff =
{
	local entity t;
	local float layout, rtt;

	layout = (to >= 100);
	if (layout)
		to = to - 100;
	t = Share_Player(to);
	if (t == world)
		return;
	// A layout's permission (still running, even if its count is spent) or a live link.
	if (layout ? !(sh_send && time < sh_send[Share_Slot(self) * FS_MAXPLAYERS + to])
	           : !Share_Linked(Share_Slot(self), to))
		return;
	if (layout)
		sh_send[Share_Slot(self) * FS_MAXPLAYERS + to] = 0;
	// Charged like a disc, and to the receiver's room: a flood of these cannot fill
	// their backlog either (review round 1).
	if (!Share_Admit(self, '0 0 0', '0 0 1', '0 1 1'))
		return;
	rtt = max(0.04, stof(infokey(t, "ping")) / 1000 + 0.02);
	t.sh_rb = min(SH_RXCAP, t.sh_rb + (time - t.sh_rbt) * SH_RXBYTES / rtt);
	t.sh_rbt = time;
	if (t.sh_rb < SH_ENDB)
		return;
	t.sh_rb = t.sh_rb - SH_ENDB;
	if (!(count >= 0))
		count = 0;
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, SH_EV_END);
	WriteByte(MSG_MULTICAST, Share_Slot(self));
	WriteLong(MSG_MULTICAST, bound(0, floor(count), 1000000));
	msg_entity = t;
	multicast('0 0 0', SH_MC_ONE);
};
