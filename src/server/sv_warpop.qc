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
		if (op >= WOP_RESET && op <= WOP_TOP)
			if (SV_DevOn())
				dprint(sprintf("warpop: %g dropped, not a decoded command\n", op));
		return;
	}
	if (!wop_live)
	{
		wop_live = TRUE;
		forceinfokey(world, "fs_wop", "1");
	}
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
	if (self.classname != "player" || !self.run_inserver)
		return;
	if (SV_DevOn())
		dprint(sprintf("warpop: %g at command %g\n", op, input_cmd_sequence_hi * 65536 + input_cmd_sequence_lo));

	if (op == WOP_RELEASE)
	{
		SV_SaveLocHold(self, FALSE);
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
void(entity e) SV_WarpOpRows =
{
	local float blk, base, cnt, i;

	e.wop_norg = '0 0 0';
	e.wop_porg = '0 0 0';
	e.wop_forg = '0 0 0';
	e.wop_lorg = '0 0 0';
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
void(entity e) SV_WarpOpPublish =
{
	local float blk, sig, sig2, sig3, moved;

	if (!wop_live)
		return;
	SV_WarpOpRows(e);
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
