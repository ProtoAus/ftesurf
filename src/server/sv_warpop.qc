/*
  Patch 753: warp ops -- `!r`, `!m` and the save-lock load key, applied at ONE
  usercmd so the client can predict them (cl_warpop.qc).

  The op is the command's impulse (WOP_*).  A stringcmd lands between packets, at
  whichever command the reliable channel delivered it before, so the client cannot
  know which of its replayed commands to move; an impulse is part of the command
  and arrives with QW's redundant copies.  SV_WarpOpCommand runs first in
  PlayerPreThink, which is where a stringcmd sent just before this command would
  have run, and calls exactly what that stringcmd calls: the timer, recorder and
  run class are unchanged.  The stringcmds keep working for every older client.

  P675's command context says whether this call is a decoded command (and which);
  a repeat of lastcmd carries the same impulse and must not act twice.  A server
  engine without P675 never publishes `fs_wop`, so no client sends ops to it.
*/
// The P675 command context globals (input_cmd_*) are declared at the top of sv_entities.qc.

.float wop_lo, wop_hi;           // the last op's command
.float wop_ack;                  // Patch 759: the same, one number (STAT_FS_WOPACK)
.string wop_cur;                 // P1238: STAT_FS_WOPCUR, zoned (SV_WarpOpCur)
.string wop_chain;               // P1342: optional exact-C-bound extra rows, zoned
.float  wop_csig, wop_ct;        // ...a cheap signature of what it carries, and when it was last built
float  wop_live;                 // fs_wop published

.vector wop_rorg, wop_rang;      // STAT_FS_WOPR/RANG: where `!r` would put you
.vector wop_morg, wop_mang;      // STAT_FS_WOPM/MANG: `!m`
.float  wop_sig, wop_sig2, wop_sig3, wop_pubt;
moveprep_t *wop_mp;

// Mark edits bypass the ordinary leg/save signatures. Drop the old answer
// and force the next normal publication to resolve the new mark precedence.
void(entity e) SV_WarpOpResetChanged =
{
	e.wop_rorg = e.wop_rang = '0 0 0';
	e.wop_pubt = time - 2;
};

// Patch 759: STAT_FS_WOPROW, the rows sl_next/prev/first/last would load.
.vector wop_norg, wop_nang, wop_nvel;
.vector wop_porg, wop_pang, wop_pvel;
.vector wop_forg, wop_fang, wop_fvel;
.vector wop_lorg, wop_lang, wop_lvel;
// STAT_FS_WOPLEGS: `!s N` / `!b N`.
.string wop_legs0, wop_legs1, wop_legs2, wop_legs3, wop_legs4, wop_legs5;
.float  wop_legzoned;            // bit k: wop_legs<k> is a strzone this module owns
.float  wop_legt, wop_legdue;
.float  wop_leggot;              // the wop_leggen this player's table was built on
string  wop_legcrc;              // the zone set wop_nstage/wop_nbonus were counted on
float   wop_legcount, wop_nstage, wop_nbonus, wop_leggen;

void() SV_WarpOpCommand =
{
	local float op;
	local vector was;

	// THIS command's impulse (SV_SetSSQCInputs), not .impulse: the engine writes
	// that from a command it does not run (paused, before the spawn) and leaves it.
	op = input_impulse;
	if (input_cmd_kind != 1 && input_cmd_kind != 2)
	{
		if ((op >= WOP_RESET && op <= WOP_TOP) || op == WOP_SAVE)
			if (SV_DevOn())
				dprint(sprintf("warpop: %g dropped, not a decoded command\n", op));
		return;
	}
	if (!wop_live)
	{
		wop_live = TRUE;
		forceinfokey(world, "fs_wop", "1");
		forceinfokey(world, "fs_wopsave", "1");     // P1547
	}
	if (op != WOP_SAVE)
	if (op < WOP_RESET || op > WOP_TOP)
		return;
	if (input_cmd_sequence_hi < self.wop_hi)
		return;
	if (input_cmd_sequence_hi == self.wop_hi && input_cmd_sequence_lo <= self.wop_lo)
		return;
	self.wop_hi = input_cmd_sequence_hi;
	self.wop_lo = input_cmd_sequence_lo;
	// Patch 759: STAT_FS_WOPACK, sent with the rows this op moves, run or refused.
	self.wop_ack = input_cmd_sequence_hi * 65536 + input_cmd_sequence_lo;
	if (op == WOP_SAVE)
	{
		// P1547: sl_save's preamble (SV_ParseClientCommand) under this command's ticket, before anything
		// can refuse it: a terminal answer even then. No STAT_FS_SLACK count: no stringcmd was sent.
		self.rec_sl_answer_tag = FS_SaveOpTag(self.wop_ack);
		self.rec_sl_answer_op = SLOP_NONE;
		self.rec_sl_answer_tick = -1;
	}
	if (self.classname != "player" || !self.run_inserver)
		return;
	if (SV_DevOn())
		dprint(sprintf("warpop: %g at command %g\n", op, input_cmd_sequence_hi * 65536 + input_cmd_sequence_lo));

	if (op == WOP_RELEASE)
	{
		SV_SaveLocHold(self, FALSE);
		return;
	}
	if (op == WOP_SAVE)
	{
		if (!SV_SaveLocRate(self))
			return;
		self.rec_sl_requesttag = self.rec_sl_answer_tag;
		self.rec_sl_auto = FALSE;
		SV_SaveLocCreate(self);
		self.rec_sl_requesttag = 0;     // later untagged events must not answer under it
		return;
	}
	if (op == WOP_LOAD)
	{
		// sl_load's charge and ticket (SV_ParseClientCommand); sl_hold is free.
		if (!SV_SaveLocRate(self))
			return;
		self.rec_sl_requesttag = 0;
		self.rec_sl_auto = FALSE;       // Patch 1021: see the steps below
		SV_SaveLocLoad(self, self.rec_sl_index);
		SV_SaveLocHold(self, TRUE);
		return;
	}
	if (op >= WOP_NEXT && op <= WOP_LAST)
	{
		// Patch 759: the stringcmds' charge and ticket, then what they call.
		if (!SV_SaveLocRate(self))
			return;
		self.rec_sl_requesttag = 0;
		// Patch 1021: the player's own command, as the sl_ stringcmds are (sv_player.qc).
		// Left set, SV_SaveLocSync put the cursor back on the newest row after every step,
		// so 3 and 4 loaded the rows either side of it and the menu read N/N on both.
		self.rec_sl_auto = FALSE;
		if (op == WOP_NEXT)
			SV_SaveLocStep(self, 1);
		else if (op == WOP_PREV)
			SV_SaveLocStep(self, -1);
		else if (op == WOP_FIRST)
			SV_SaveLocFirst(self);
		else
			SV_SaveLocLast(self);
		return;
	}
	was = self.origin;
	if (op >= WOP_BONUS1)
		SV_ZoneChatCommand("!b", op - WOP_BONUS1 + 1);
	else if (op >= WOP_STAGE1)
		SV_ZoneChatCommand("!s", op - WOP_STAGE1 + 1);
	else
		SV_ZoneChatCommand((op == WOP_SPAWN) ? "!m" : "!r", 0);
	SV_RewindWarped(self, was);     // Patch 477, as the chat path does
};

// One reset word's answer in wop_dorg/wop_dang; WOPD_NONE when the live path
// could refuse or differ.
vector wop_dorg, wop_dang;
void(entity e, string word, float n) SV_WarpOpDest =
{
	wop_dorg = '0 0 0';
	wop_dang = '0 0 0';
	if (SV_MovePrepReset(e, word, n, wop_mp) != MP_READY)
		return;
	wop_dorg = wop_mp->origin;
	wop_dang = wop_mp->angles;
	wop_dang_z = (wop_mp->angle_policy == MP_SET) ? WOPD_ANG : WOPD_KEEP;
};

// Patch 759: row r of the arrays into one of STAT_FS_WOPROW's triples.
vector wop_rowang, wop_rowvel;
vector(float r) SV_WarpOpRow =
{
	wop_rowang = [rec_sl_pit[r], rec_sl_yaw[r], rec_sl_duck[r] ? 1 : 0];
	wop_rowvel = rec_sl_vel[r];
	return rec_sl_org[r];
};

// Every command: the rows SV_SaveLocStep/First/Last would load from this cursor.
// SV_SaveLocSync has just set rec_sl_count and the cursor (0 when saves are off).
vector wop_xorg[4], wop_xang[4], wop_xvel[4]; // scratch for this publish only
void(entity e) SV_WarpOpRows =
{
	local float blk, base, cnt, i, j, delta;

	e.wop_norg = '0 0 0';
	e.wop_porg = '0 0 0';
	e.wop_forg = '0 0 0';
	e.wop_lorg = '0 0 0';
	for (i = 0; i < 4; i = i + 1)
	{
		wop_xorg[i] = '0 0 0';
		wop_xang[i] = '0 0 0';
		wop_xvel[i] = '0 0 0';
	}
	blk = SL_Blk(e);
	cnt = e.rec_sl_count;
	if (!rec_sl_org || cnt < 1 || cnt > rec_sl_nb[blk] || e.rec_sl_index < 1 || e.rec_sl_index > cnt)
		return;
	base = SL_Base(blk);
	i = (e.rec_sl_index < cnt) ? e.rec_sl_index + 1 : 1;
	e.wop_norg = SV_WarpOpRow(base + i - 1);
	e.wop_nang = wop_rowang;
	e.wop_nvel = wop_rowvel;
	i = (e.rec_sl_index > 1) ? e.rec_sl_index - 1 : cnt;
	e.wop_porg = SV_WarpOpRow(base + i - 1);
	e.wop_pang = wop_rowang;
	e.wop_pvel = wop_rowvel;
	e.wop_forg = SV_WarpOpRow(base);
	e.wop_fang = wop_rowang;
	e.wop_fvel = wop_rowvel;
	e.wop_lorg = SV_WarpOpRow(base + cnt - 1);
	e.wop_lang = wop_rowang;
	e.wop_lvel = wop_rowvel;
	for (j = 0; j < 4; j = j + 1)
	{
		delta = ((j < 2) ? 2 : 3) * ((j & 1) ? -1 : 1);
		i = e.rec_sl_index + delta;
		while (i < 1) i = i + cnt;
		while (i > cnt) i = i - cnt;
		wop_xorg[j] = SV_WarpOpRow(base + i - 1);
		wop_xang[j] = wop_rowang;
		wop_xvel[j] = wop_rowvel;
	}
};

void(entity e, .string f, float bit, string s) SV_WarpOpLegSet =
{
	if (!strcmp(e.f, s))
		return;
	if (e.wop_legzoned & bit)
		strunzone(e.f);
	e.wop_legzoned = e.wop_legzoned - (e.wop_legzoned & bit);
	e.f = "";
	if (strlen(s) > 0)
	{
		e.f = strzone(s);
		e.wop_legzoned = e.wop_legzoned | bit;
	}
};

// Chunk k of STAT_FS_WOPLEGS: the legs the map has, each one P680 answers.
string(entity e, float k) SV_WarpOpLegChunk =
{
	local float n, hi;
	local string s, word;

	s = "";
	word = (k < 4) ? "!s" : "!b";
	n = (k < 4) ? 8 * k + 1 : 8 * (k - 4) + 1;
	hi = min(n + 7, (k < 4) ? wop_nstage : wop_nbonus);
	while (n <= hi)
	{
		SV_WarpOpDest(e, word, n);
		if (wop_dang_z != WOPD_NONE)
			s = strcat(s, sprintf("%s %g %.9g %.9g %.9g ", substring(word, 1, 1), n,
			                      wop_dorg_x, wop_dorg_y, wop_dorg_z),
			           sprintf("%.9g %.9g %g ", wop_dang_x, wop_dang_y, wop_dang_z));
		n = n + 1;
	}
	return s;
};

// The legs this zone set has; a new set bumps wop_leggen, which every player's
// table then follows.
void() SV_WarpOpLegCount =
{
	local float n;

	if (!zone_loaded)
		return;
	if (!strcmp(wop_legcrc, zone_crc) && wop_legcount == zone_count)
		return;
	if (wop_legcrc)
		strunzone(wop_legcrc);
	wop_legcrc = strzone(zone_crc);
	wop_legcount = zone_count;
	wop_leggen = wop_leggen + 1;
	wop_nstage = 0;
	wop_nbonus = 0;
	for (n = 1; n <= WOP_STAGES; n = n + 1)
		if (SV_ZoneFindLeg(0, n - 1) >= 0)
			wop_nstage = n;
	for (n = 1; n <= WOP_BONUSES; n = n + 1)
		if (SV_ZoneFindLeg(n, 0) >= 0)
			wop_nbonus = n;
};

void(entity e) SV_WarpOpLegs =
{
	if (!zone_loaded)
		return;
	e.wop_leggot = wop_leggen;
	e.wop_legt = time;
	SV_WarpOpLegSet(e, wop_legs0, 1, SV_WarpOpLegChunk(e, 0));
	SV_WarpOpLegSet(e, wop_legs1, 2, SV_WarpOpLegChunk(e, 1));
	SV_WarpOpLegSet(e, wop_legs2, 4, SV_WarpOpLegChunk(e, 2));
	SV_WarpOpLegSet(e, wop_legs3, 8, SV_WarpOpLegChunk(e, 3));
	SV_WarpOpLegSet(e, wop_legs4, 16, SV_WarpOpLegChunk(e, 4));
	SV_WarpOpLegSet(e, wop_legs5, 32, SV_WarpOpLegChunk(e, 5));
};

/*
  PlayerPostThink.  The destinations are P680's read-only answer for the same
  words, recomputed when anything they read moves (the leg, the run's stage, the
  save list, a hold, the movetype, a pin) and at least once a second; the `!s`/`!b`
  table on the same changes and at least every 5 s.
*/
string(vector o, vector a, vector v) SV_WopCurRow =
{
	return strcat(sprintf("%.9g %.9g %.9g %.9g %.9g %.9g ", o_x, o_y, o_z, a_x, a_y, a_z),
	              sprintf("%.9g %.9g %.9g ", v_x, v_y, v_z));
};

float(vector o, vector a, vector v) SV_WopCurSig =
{
	return o_x * 1.1 + o_y * 1.3 + o_z * 1.7 + a_x * 0.7 + a_y * 0.9 + a_z * 3.1 + v_x * 0.11 + v_y * 0.13 + v_z * 0.17;
};

// P1238: STAT_FS_WOPCUR, rebuilt after the rows.  The sprintfs run only when the signature moves, or
// once a second so a signature that collided cannot leave the string stale for longer.
void(entity e) SV_WarpOpCur =
{
	local string s, chain;
	local vector holdvel;
	local float sig, k, held, blk, base;

	held = FALSE;
	holdvel = '0 0 0';
	if (e.rec_sl_hold)
	if (rec_sl_vel)
	{
		blk = SL_Blk(e);
		base = SL_Base(blk);
		if (e.rec_sl_holdrow >= base && e.rec_sl_holdrow < base + rec_sl_nb[blk])
		{
			held = TRUE;
			holdvel = rec_sl_vel[e.rec_sl_holdrow];
		}
	}
	sig = e.wop_ack + e.rec_sl_index * 4099.5 + e.rec_sl_count * 77.25 + e.rec_sl_ack * 0.37
	      + SV_WopCurSig(e.rec_sl_curorg, e.rec_sl_curang, e.rec_sl_curvel)
	      + 2 * SV_WopCurSig(e.wop_norg, e.wop_nang, e.wop_nvel) + 3 * SV_WopCurSig(e.wop_porg, e.wop_pang, e.wop_pvel)
	      + 5 * SV_WopCurSig(e.wop_forg, e.wop_fang, e.wop_fvel) + 7 * SV_WopCurSig(e.wop_lorg, e.wop_lang, e.wop_lvel);
	sig = sig + held * 31.7 + 23 * SV_WopCurSig('0 0 0', '0 0 0', holdvel);
	for (k = 0; k < 4; k = k + 1)
		sig = sig + (11 + 2 * k) * SV_WopCurSig(wop_xorg[k], wop_xang[k], wop_xvel[k]);
	if (e.wop_cur != "" && sig == e.wop_csig && time - e.wop_ct < 1 && time >= e.wop_ct)
		return;
	e.wop_csig = sig;
	e.wop_ct = time;
	s = strcat(sprintf("C %.0f %g %g %g ", e.wop_ack, e.rec_sl_index, e.rec_sl_count, e.rec_sl_ack),
	           SV_WopCurRow(e.rec_sl_curorg, e.rec_sl_curang, e.rec_sl_curvel),
	           SV_WopCurRow(e.wop_norg, e.wop_nang, e.wop_nvel),
	           SV_WopCurRow(e.wop_porg, e.wop_pang, e.wop_pvel),
	           SV_WopCurRow(e.wop_forg, e.wop_fang, e.wop_fvel),
	           SV_WopCurRow(e.wop_lorg, e.wop_lang, e.wop_lvel));
	if (strcmp(e.wop_cur, s))
	{
		if (e.wop_cur != "") strunzone(e.wop_cur);
		e.wop_cur = strzone(s);
	}
	chain = strcat("D \"", s, sprintf("\" %g %.9g %.9g %.9g ", held, holdvel_x, holdvel_y, holdvel_z));
	for (k = 0; k < 4; k = k + 1)
		chain = strcat(chain, SV_WopCurRow(wop_xorg[k], wop_xang[k], wop_xvel[k]));
	if (strlen(chain) > WOPCHAIN_MAX)
		chain = "";                     // no truncation or partial-row prediction
	if (strcmp(e.wop_chain, chain))
	{
		if (e.wop_chain != "") strunzone(e.wop_chain);
		e.wop_chain = (chain != "") ? strzone(chain) : "";
	}
};

void(entity e) SV_WarpOpPublish =
{
	local float blk, sig, sig2, sig3, moved;

	if (!wop_live)
		return;
	SV_WarpOpRows(e);
	SV_WarpOpCur(e);                // P1238
	blk = SL_Blk(e);
	sig = e.run_leg_zone + 1024 * (e.run_t_state + 8 * (e.rec_sl_hold + 2 * (e.movetype
	      + 16 * (e.run_pmhold || e.run_sp_phase || e.rec_wt_hold || e.rec_gh_on || e.run_ms_phase))));
	sig2 = rec_sl_nb[blk] + 1024 * rec_sl_ns[blk];
	sig3 = e.run_t_seg + 256 * (e.run_t_track + 256 * e.run_t_startseg);
	moved = (sig != e.wop_sig || sig2 != e.wop_sig2 || sig3 != e.wop_sig3);
	if (!moved)
	if (time - e.wop_pubt < 1 && time >= e.wop_pubt)
		return;
	e.wop_sig = sig;
	e.wop_sig2 = sig2;
	e.wop_sig3 = sig3;
	e.wop_pubt = time;
	if (!wop_mp)
		wop_mp = SV_MovePrepAlloc();
	SV_WarpOpDest(e, "!r", 0);
	e.wop_rorg = wop_dorg;
	e.wop_rang = wop_dang;
	SV_WarpOpDest(e, "!m", 0);
	e.wop_morg = wop_dorg;
	e.wop_mang = wop_dang;
	// Up to 46 destinations, each a find and traces: at most once a second even
	// for a client that changes the signature every command.
	SV_WarpOpLegCount();
	if (moved || e.wop_leggot != wop_leggen)
		e.wop_legdue = TRUE;
	if ((e.wop_legdue && time - e.wop_legt >= 1) || time - e.wop_legt >= 5 || time < e.wop_legt)
	{
		e.wop_legdue = FALSE;
		SV_WarpOpLegs(e);
	}
};

// P1190: teleport pop-in. The client predicts a teleport at once; the destination's networked
// entities (func_brush ramps, prop_dynamic) waited for a snapshot from the new origin, a command
// interval plus a round trip later. A second PVS origin through .view2, as above, sits at the
// destination of a teleport the player is about to touch, else at this stage's `!r` destination.
// The replay/ghost/spectate eye outranks it. sv_tp_pvs 0 detaches it, 2 keeps teleports only.
.entity tp_eye;
.float  tp_eye_next;
.float  tp_eye_hold;             // until: the eye stays at a crossed teleport's destination
.float  tp_eye_zone;             // on the eye: the !r zone it shows, -1 for a teleport
.entity tp_next;
entity  tp_chain;               // every live trigger_teleport, relinked each second
float   tp_chain_at;

void(entity e) SV_TpEyeDetach =
{
	if (e.tp_eye == world)
		return;
	if (e.view2 == e.tp_eye)
		e.view2 = world;
	remove(e.tp_eye);
	e.tp_eye = world;
};

float(entity t) SV_TpIsTele =
{
	return (t.touch == trigger_teleport_touch || t.touch == trigger_teleport_relative_touch);
};

void() SV_TpChain =
{
	local entity t;

	tp_chain = world;
	for (t = nextent(world); t; t = nextent(t))
		if (SV_TpIsTele(t))
		{
			t.tp_next = tp_chain;
			tp_chain = t;
		}
	tp_chain_at = time + 1;
};

void(entity e) SV_TpEyeThink =
{
	local entity t, best, d;
	local vector lo, hi, sw, org, c;
	local float ahead, bd, dd, z, yaw, haveyaw, fallback, have;
	local string tgt;

	if (e.rec_wt_hold || e.rec_gh_on || e.run_sp_phase || e.rec_vw_eye != world
		|| !cvar("sv_tp_pvs"))
	{
		SV_TpEyeDetach(e);
		return;
	}
	if (time < e.tp_eye_next && e.tp_eye_next < time + 1)
		return;                     // 20 Hz with or without an eye (review: unzoned maps)
	e.tp_eye_next = time + 0.05;
	if (time >= tp_chain_at || tp_chain_at > time + 1)
		SV_TpChain();

	// The client runs a round trip ahead of the snapshot that answers it; 400*t^2 is
	// half of sv_gravity 800, for a fall into a fail trigger.
	ahead = bound(0.2, stof(infokey(e, "ping")) * 0.0015 + 0.1, 0.8);
	sw = e.velocity * ahead;
	lo = e.absmin + [min(sw_x, 0), min(sw_y, 0), min(sw_z, 0) - 400 * ahead * ahead];
	hi = e.absmax + [max(sw_x, 0), max(sw_y, 0), max(sw_z, 0)];
	best = world;
	bd = 999999999;
	for (t = tp_chain; t; t = t.tp_next)
	{
		if (wasfreed(t))
			continue;
		if (!SV_TpIsTele(t) || t.solid == SOLID_NOT)
			continue;
		if (SV_Key2(t.StartDisabled, t.startdisabled))
			continue;
		if (t.absmin_x > hi_x || t.absmax_x < lo_x || t.absmin_y > hi_y || t.absmax_y < lo_y
			|| t.absmin_z > hi_z || t.absmax_z < lo_z)
			continue;
		c = [bound(t.absmin_x, e.origin_x, t.absmax_x), bound(t.absmin_y, e.origin_y, t.absmax_y),
		     bound(t.absmin_z, e.origin_z, t.absmax_z)];
		dd = vlen(c - e.origin);
		if (dd < bd)
		{
			bd = dd;
			best = t;
		}
	}

	// A teleport just left the sweep (usually crossed): the eye stays at its destination while
	// `!r`'s stat catches up (up to 1 s stale), or it would flash to the last stage's start.
	// Filters and spawnflags are not tested: a teleport that will not fire costs one PVS.
	if (best == world && time < e.tp_eye_hold && e.tp_eye != world)
		return;
	have = FALSE;
	d = world;
	org = '0 0 0';
	if (best != world)
	{
		if (best.touch == trigger_teleport_relative_touch)
		{
			org = SV_RelTelePoint(best);
			have = TRUE;
		}
		else
		{
			tgt = SV_TpDest(best, e);
			if (tgt != "")          // find("") returns client slot 0 (Patch 881)
				d = find(world, targetname, tgt);
			if (d != world)
			{
				org = d.origin;
				have = TRUE;
			}
		}
		if (have)
			e.tp_eye_hold = time + 1;
	}
	z = -1;
	if (cvar("sv_tp_pvs") == 2)
		z = -4;             // teleports only (the arm's lookahead control)
	else if (!have && e.wop_rorg != '0 0 0')
	{
		org = e.wop_rorg;           // the client's own `!r` prediction target
		have = TRUE;
		z = -3;
	}
	if (!have && z == -1 && zone_count > 0)
	{
		z = SV_ZoneRequestZone(e, "!r", 0);
		if (z >= 0 && z < zone_count)
		if (zone_td_kind[z] == ZTD_NONE || zone_td_kind[z] == ZTD_POS || zone_td_kind[z] == ZTD_NAME)
		{
			org = SV_ZoneDestRead(e, z, yaw, haveyaw, fallback);
			have = TRUE;
		}
	}
	if (!have)
	{
		SV_TpEyeDetach(e);
		return;
	}

	if (e.tp_eye == world)
	{
		// A slot's next client inherits the field cleared, not the entity (Patch 477 round 27).
		e.tp_eye = find(world, classname, "tp_view_eye");
		while (e.tp_eye != world && e.tp_eye.owner != e)
			e.tp_eye = find(e.tp_eye, classname, "tp_view_eye");
	}
	if (e.tp_eye == world)
	{
		e.tp_eye = spawn();
		e.tp_eye.classname = "tp_view_eye";
		e.tp_eye.movetype  = MOVETYPE_NONE;
		e.tp_eye.solid     = SOLID_NOT;
		e.tp_eye.owner     = e;
		setmodel(e.tp_eye, "");
		setsize(e.tp_eye, '0 0 0', '0 0 0');
		e.tp_eye.tp_eye_zone = -2;
	}
	e.view2 = e.tp_eye;
	if (cvar("developer"))
	if (e.tp_eye.enemy != best || e.tp_eye.tp_eye_zone != z || vlen(org + e.view_ofs - e.tp_eye.origin) > 64)
	{
		if (best != world)
			tgt = sprintf("teleport %s -> %s", etos(best), etos(d));
		else if (z == -3)
			tgt = "!r stat";
		else
			tgt = sprintf("!r zone %g", z);
		dprint(sprintf("tp_pvs: %s eye at %v (%s)\n", e.netname, org + e.view_ofs, tgt));
	}
	setorigin(e.tp_eye, org + e.view_ofs);
	e.tp_eye.enemy = best;
	e.tp_eye.tp_eye_zone = z;
};
