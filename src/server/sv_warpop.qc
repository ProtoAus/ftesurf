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
float input_cmd_kind;
float input_cmd_sequence_lo;
float input_cmd_sequence_hi;
__used float input_cmd_msec;     // all six or the engine exports none
__used float input_cmd_piece_msec;
__used float input_cmd_offset_msec;

.float wop_lo, wop_hi;           // the last op's command
float  wop_live;                 // fs_wop published

.vector wop_rorg, wop_rang;      // STAT_FS_WOPR/RANG: where `!r` would put you
.vector wop_morg, wop_mang;      // STAT_FS_WOPM/MANG: `!m`
.float  wop_sig, wop_sig2, wop_sig3, wop_pubt;
moveprep_t *wop_mp;

void() SV_WarpOpCommand =
{
	local float op;
	local vector was;

	// THIS command's impulse (SV_SetSSQCInputs), not .impulse: the engine writes
	// that from a command it does not run (paused, before the spawn) and leaves it.
	op = input_impulse;
	if (input_cmd_kind != 1 && input_cmd_kind != 2)
	{
		if (op >= WOP_RESET && op <= WOP_RELEASE)
			dprint(sprintf("warpop: %g dropped, not a decoded command\n", op));
		return;
	}
	if (!wop_live)
	{
		wop_live = TRUE;
		forceinfokey(world, "fs_wop", "1");
	}
	if (op < WOP_RESET || op > WOP_RELEASE)
		return;
	if (input_cmd_sequence_hi < self.wop_hi)
		return;
	if (input_cmd_sequence_hi == self.wop_hi && input_cmd_sequence_lo <= self.wop_lo)
		return;
	self.wop_hi = input_cmd_sequence_hi;
	self.wop_lo = input_cmd_sequence_lo;
	if (self.classname != "player" || !self.run_inserver)
		return;
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
		SV_SaveLocLoad(self, self.rec_sl_index);
		SV_SaveLocHold(self, TRUE);
		return;
	}
	was = self.origin;
	SV_ZoneChatCommand((op == WOP_SPAWN) ? "!m" : "!r", 0);
	SV_RewindWarped(self, was);     // Patch 477, as the chat path does
};

// One reset word's answer in wop_dorg/wop_dang; WOPD_NONE when the live path
// could refuse or differ.
vector wop_dorg, wop_dang;
void(entity e, string word) SV_WarpOpDest =
{
	wop_dorg = '0 0 0';
	wop_dang = '0 0 0';
	if (SV_MovePrepReset(e, word, 0, wop_mp) != MP_READY)
		return;
	wop_dorg = wop_mp->origin;
	wop_dang = wop_mp->angles;
	wop_dang_z = (wop_mp->angle_policy == MP_SET) ? WOPD_ANG : WOPD_KEEP;
};

/*
  PlayerPostThink.  The destinations are P680's read-only answer for the same
  words, recomputed when anything they read moves (the leg, the run's stage, the
  save list, a hold, the movetype, a pin) and at least once a second.
*/
void(entity e) SV_WarpOpPublish =
{
	local float blk, sig, sig2, sig3;

	if (!wop_live)
		return;
	blk = SL_Blk(e);
	sig = e.run_leg_zone + 1024 * (e.run_t_state + 8 * (e.rec_sl_hold + 2 * (e.movetype
	      + 16 * (e.run_pmhold || e.run_sp_phase || e.rec_wt_hold || e.rec_gh_on || e.run_ms_phase))));
	sig2 = rec_sl_nb[blk] + 1024 * rec_sl_ns[blk];
	sig3 = e.run_t_seg + 256 * (e.run_t_track + 256 * e.run_t_startseg);
	if (sig == e.wop_sig && sig2 == e.wop_sig2 && sig3 == e.wop_sig3)
	if (time - e.wop_pubt < 1 && time >= e.wop_pubt)
		return;
	e.wop_sig = sig;
	e.wop_sig2 = sig2;
	e.wop_sig3 = sig3;
	e.wop_pubt = time;
	if (!wop_mp)
		wop_mp = SV_MovePrepAlloc();
	SV_WarpOpDest(e, "!r");
	e.wop_rorg = wop_dorg;
	e.wop_rang = wop_dang;
	SV_WarpOpDest(e, "!m");
	e.wop_morg = wop_dorg;
	e.wop_mang = wop_dang;
};
