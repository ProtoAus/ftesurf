/*
===========================================================================
  sv_share.qc -- Patch 777: paint and saves handed from one player to another.

  The client asks (`cmd share offer <slot> <kind> <n>`), the other player
  answers (`cmd share answer 1|0`), and only then does anything move:

      1 live    both see each other's paint from now on, and what each has up
      2 layout  the sender's client streams its paint to the receiver once
      3 save    the sender's selected save becomes a practice row in the
                receiver's list (SV_SaveLocCreateAt's replay-point shape: idle
                timer, no run, velocity under `rwvel`)

  Discs arrive as sendevent ("pd" live, "pl" streamed, "ple" a stream's end)
  and go out as SVC_CGAMEPACKET to that one client (cl_share.qc's
  CSQC_Parse_Event).  Every number is the server's own re-encoding of a
  checked float, so nothing a sender writes reaches a console.
===========================================================================
*/
#define SH_LIVE    1
#define SH_LAYOUT  2
#define SH_SAVE    3
#define SH_EV_DISC 1
#define SH_EV_END  2
#define SH_WAIT    20       // seconds an offer stands
#define SH_RATE    300      // relayed discs a second, per sender
#define SH_BURST   600

.float sh_from;             // an offer to this player: the sender's slot + 1
.float sh_kind, sh_n, sh_until;
.vector sh_so, sh_sv;       // the offered save, taken when it was offered
.float sh_sp, sh_sy, sh_sd;
.float sh_offerat;          // this player's last offer, for the rate
.float sh_sendto;           // a layout stream this player may send: target slot + 1
.float sh_senduntil;
.float sh_tok, sh_tokt;
.float sh_relayed, sh_dropped;
float *sh_link;             // [a * FS_MAXPLAYERS + b]: live paint between two slots

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

float(float a, float b) Share_Linked =
{
	if (!sh_link)
		return FALSE;
	return sh_link[a * FS_MAXPLAYERS + b];
};

void(entity a, entity b, float on) Share_SetLink =
{
	local float sa, sb;

	if (!sh_link)
		sh_link = memalloc(sizeof(float) * FS_MAXPLAYERS * FS_MAXPLAYERS);
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
	if (t.sh_from && time < t.sh_until && t.sh_from != Share_Slot(e) + 1)
	{
		sprint(e, PRINT_HIGH, sprintf("^3share:^7 %s is answering someone else\n", t.netname));
		return;
	}
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
	t.sh_from = Share_Slot(e) + 1;
	t.sh_kind = kind;
	t.sh_n = bound(0, floor(n), 999999);
	t.sh_until = time + SH_WAIT;
	stuffcmd(t, sprintf("share_ask %g %g %g %g\n", Share_Slot(e), kind, t.sh_n, SH_WAIT));
	sprint(e, PRINT_HIGH, sprintf("^7share: asked %s\n", t.netname));
};

void(entity t, float yes) Share_Answer =
{
	local entity e;
	local float kind, ok;

	if (!t.sh_from)
		return;
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
		e.sh_sendto = Share_Slot(t) + 1;
		e.sh_senduntil = time + 30;
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
	local float me;

	me = Share_Slot(e) + 1;
	Share_Stop(e, -1);
	e.sh_from = e.sh_sendto = 0;
	e.sh_offerat = 0;
	p = find(world, classname, "player");
	while (p)
	{
		if (p.sh_from == me)
		if (clienttype(p) == CLIENTTYPE_REAL)
			Share_Drop(p);
		if (p.sh_sendto == me)
			p.sh_sendto = 0;
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
		Share_Answer(e, stof(argv(2)) != 0);
	else if (v == "stop")
		Share_Stop(e, (cmdargc >= 3) ? stof(argv(2)) : -1);
	else if (v == "status")
		sprint(e, PRINT_HIGH, sprintf("share: relayed %g, dropped %g, offer from %g kind %g, sending to %g\n",
		                              e.sh_relayed, e.sh_dropped, e.sh_from - 1, e.sh_kind, e.sh_sendto - 1));
};

/*
  One disc, checked and re-encoded.  `c` is the client's packing: x = 0xRRGGBB,
  y = size, z = alpha.  The rate is a token bucket: past it the disc is dropped
  and counted, not queued -- the receiver misses a few marks of a fast spray.
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

void(entity e, entity t, vector o, vector n, vector c) Share_Write =
{
	local float rgb;

	rgb = floor(c_x);
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, SH_EV_DISC);
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
	multicast('0 0 0', MULTICAST_ONE_R);
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
				Share_Write(self, t, o, n, c);
		}
};

// A streamed disc for one player: a layout they took, or this player's paint
// so far when a live share began.
void(float to, vector o, vector n, vector c) CSEv_pl_fvvv =
{
	local entity t;

	t = Share_Player(to);
	if (t == world)
		return;
	if (!Share_Linked(Share_Slot(self), to))
	if (!(self.sh_sendto == to + 1 && time < self.sh_senduntil))
		return;
	if (self.sh_sendto == to + 1)
		self.sh_senduntil = max(self.sh_senduntil, time + 10);
	if (Share_Admit(self, o, n, c))
		Share_Write(self, t, o, n, c);
};

void(float to, float count) CSEv_ple_ff =
{
	local entity t;

	t = Share_Player(to);
	if (t == world)
		return;
	if (!Share_Linked(Share_Slot(self), to) && self.sh_sendto != to + 1)
		return;
	if (self.sh_sendto == to + 1)
		self.sh_sendto = 0;
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, SH_EV_END);
	WriteByte(MSG_MULTICAST, Share_Slot(self));
	WriteLong(MSG_MULTICAST, bound(0, floor(count), 1000000));
	msg_entity = t;
	multicast('0 0 0', MULTICAST_ONE_R);
};
