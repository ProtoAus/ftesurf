/*
  Return from slow practice is a NEW attempt, never forgiveness of an old run.
  Normal speed + a supported armed opening box requests a per-seat input fence.
  CSQC consumes its pending command as neutral and keeps sending neutral commands
  until completion. A reliable event identifies that first generated sequence;
  the event itself does NOT clear taint. Old QW recovered/repeated commands run
  before a decoded neutral boundary, at which only this client's complete native
  Source carry is reset. Explicit respawn then discards the old body/attempt and
  restores only validated position/view through the ordinary zone placement.

  One derived request/completion stat, no capture grammar or result override.
  Missing/old/timestamp/thread-bypassing clients cannot complete the fence.
*/
float(entity player) sourcepractice_reset = #0;
.float run_ts_return;              // positive pending identity, negative completed
.float run_ts_return_uid;
.int run_ts_return_attempt;      // same-zone resets replace the admission too
.float run_ts_return_zone;
.float run_ts_return_after;
.float run_ts_return_frame;
.float run_ts_return_seed;          // exact prepared neutral command; stat203
.float run_ts_return_ready;         // native-client epoch reset acknowledged
.float run_ts_return_until;
.float run_ts_return_block;
float run_ts_return_serial;        // exact, never reused in this VM lifetime

void(entity e, float blocked) SV_TimeScaleReturnCancel =
{
	// A pre-fence load already on the wire may park after the client cancelled
	// its release queue. Refusing return must not strand that authoritative hold.
	// This releases assistance only; ancestry remains practice.
	if (e.run_ts_return > 0 && e.rec_sl_hold) SV_SaveLocRelease(e);
	e.run_ts_return = e.run_ts_return_frame = e.run_ts_return_until = 0;
	e.run_ts_return_seed = e.run_ts_return_ready = 0;
	e.run_ts_return_block = blocked;
};

// This is pose selection, NOT proof that an already armed attempt is clean.
float(entity e) SV_TimeScaleReturnZone =
{
	local float z;
	if (e.bank_attempt <= 0i) return -1; // exhausted/unknown admissions cannot alias
	if (!e.run_ts_used || e.run_timescale != 1 || !e.run_inserver || !(e.health > 0))
		return -1;
	if (e.run_tas_used || e.run_tas_mode || e.run_tas_paused || e.run_tas_pending ||
		e.rec_wt_hold || e.rec_sl_hold || e.run_pmhold || e.run_t_viewowner ||
		e.run_ms_phase || SV_MsBusy(e) || SV_CheatsOn())
		return -1;
	z = SV_TimerMarkZone(e);
	if (z < 0) return -1;
	if (!(e.flags & FL_ONGROUND) || (e.pmove_flags & PMF_DUCKED)) return -1;
	tracebox(e.origin, PM_HULL_MINS, PM_HULL_MAXS, e.origin, FALSE, e);
	if (trace_startsolid || trace_allsolid) return -1;
	tracebox(e.origin + '0 0 1', PM_HULL_MINS, PM_HULL_MAXS,
		e.origin - '0 0 2', FALSE, e);
	if (trace_startsolid || trace_allsolid || trace_fraction >= 1 || trace_plane_normal_z < 0.7)
		return -1;
	return z;
};

// Seat routing comes from the native QC-request reader, not a client entity id.
void(float request, float frame) CSEv_tsreturn_ff =
{
	if (!(request > 0 && request <= 16000000 && floor(request) == request)) return;
	if (!(frame > self.run_ts_return_after && frame <= 16000000 && floor(frame) == frame)) return;
	if (self.run_ts_return != request || self.run_ts_return_until < time) return;
	if (self.run_ts_return_uid != stof(infokey(self, "*userid"))) return;
	if (self.run_ts_return_attempt != self.bank_attempt) return;
	if (self.run_ts_return_seed) return;
	if (!self.run_ts_return_frame) self.run_ts_return_frame = frame;
};

// An ACK of the actual prepared command, not merely receipt of a request.
// A modified client can lie about its own prediction; this cannot bypass the
// server's independent neutral/native-reset/new-attempt eligibility boundary.
void(float request, float seed, float frame) CSEv_tsreturnready_fff =
{
	if (!(request > 0 && request <= 16000000 && floor(request) == request)) return;
	if (!(seed > 0 && seed <= 16000000 && floor(seed) == seed)) return;
	if (!(frame > seed && frame <= 16000000 && floor(frame) == frame)) return;
	if (self.run_ts_return != request || self.run_ts_return_seed != seed || self.run_ts_return_until < time) return;
	if (self.run_ts_return_uid != stof(infokey(self, "*userid"))) return;
	if (self.run_ts_return_attempt != self.bank_attempt) return;
	if (!self.run_ts_return_ready) self.run_ts_return_ready = frame;
};

// Both phases close their still-practice evidence BEFORE native carry changes.
// Preparation does NOT clear the latch; only a later client-ready boundary can.
float(float z, vector at, vector aim, float wantstage1, float clean) SV_TimeScaleReturnPlace =
{
	local float slot;
	SV_TimerVoid(self, "normal-speed clean restart");
	if (!sourcepractice_reset(self))
	{
		SV_TimeScaleReturnCancel(self, TRUE);
		return FALSE;
	}
	SV_PlayerRespawn();
	slot = num_for_edict(self) - 1;
	if (!(slot >= 0 && slot < FS_MAXPLAYERS))
	{
		SV_TimeScaleReturnCancel(self, TRUE);
		return FALSE;
	}
	if (clean)
	{
		self.run_ts_used = FALSE;
		sv_ts_taint_uid[slot] = 0;
	}
	self.run_t_wantstage1 = wantstage1;
	SV_ZoneMoveAt(z, at, aim_y, aim_x, TRUE, TRUE);
	if (self.bank_attempt <= 0i || self.origin != at || SV_TimerMarkZone(self) != z)
	{
		self.run_ts_used = TRUE;
		SV_TimeScaleRemember(self);
		SV_TimerCheat(self);
		SV_TimeScaleReturnCancel(self, TRUE);
		return FALSE;
	}
	return TRUE;
};

// PlayerPreThink, after command-aligned reset ops and before any moved input.
void() SV_TimeScaleReturnCommand =
{
	local float z, frame, uid, request, wantstage1, clean;
	local vector at, aim;
	z = SV_TimeScaleReturnZone(self);
	if (z < 0)
	{
		if (self.run_ts_return > 0) SV_TimeScaleReturnCancel(self, FALSE);
		self.run_ts_return_block = FALSE;
		return;
	}
	if (!checkbuiltin(sourcepractice_reset))
	{
		if (self.run_ts_return > 0) SV_TimeScaleReturnCancel(self, TRUE);
		return; // old native: keep practice, never strand a revived request
	}
	if (self.run_ts_return > 0 && self.run_ts_return_until < time)
	{
		SV_TimeScaleReturnCancel(self, TRUE);
		sprint(self, PRINT_HIGH, "host_timescale: clean return not confirmed; still practice. Set 1 again to retry.\n");
		return;
	}
	uid = stof(infokey(self, "*userid"));
	if (!(uid > 0)) return;
	if (input_cmd_kind != 1 || input_cmd_offset_msec != 0) return;
	frame = input_cmd_sequence_hi * 65536 + input_cmd_sequence_lo;
	if (!(frame > 0 && frame <= 16000000 && floor(frame) == frame)) return;
	if (self.run_ts_return > 0)
	{
		if (self.run_ts_return_zone != z || self.run_ts_return_uid != uid ||
			self.run_ts_return_attempt != self.bank_attempt)
		{
			SV_TimeScaleReturnCancel(self, FALSE);
			return;
		}
	}
	else
	{
		if (self.run_ts_return_block || run_ts_return_serial >= 16000000) return;
		run_ts_return_serial = run_ts_return_serial + 1;
		self.run_ts_return = run_ts_return_serial;
		self.run_ts_return_uid = uid;
		self.run_ts_return_attempt = self.bank_attempt;
		self.run_ts_return_zone = z;
		self.run_ts_return_after = frame;
		self.run_ts_return_frame = self.run_ts_return_seed = self.run_ts_return_ready = 0;
		self.run_ts_return_until = time + 5;
		return;
	}
	clean = self.run_ts_return_seed > 0;
	if (clean)
	{
		if (!self.run_ts_return_ready || frame < self.run_ts_return_ready) return;
	}
	else if (!self.run_ts_return_frame || frame < self.run_ts_return_frame) return;
	if (input_cmd_msec != 0 || input_cmd_piece_msec != 0 || input_buttons != 0 ||
		input_impulse != 0 || input_movevalues != '0 0 0') return;
	if (SV_TimeScaleReturnZone(self) != z) return;
	at = self.origin;
	aim = self.v_angle;
	wantstage1 = self.run_t_wantstage1;
	request = self.run_ts_return;
	if (!SV_TimeScaleReturnPlace(z, at, aim, wantstage1, clean)) return;
	if (!clean)
	{
		// Native client must reseed AFTER this acknowledged authoritative command,
		// while every later pending command is still neutral. No ACK => practice.
		self.run_ts_return_seed = frame;
		self.run_ts_return_ready = 0;
		self.run_ts_return_attempt = self.bank_attempt;
		self.run_ts_return_until = time + 5;
		return;
	}
	self.run_ts_return = -request;
	self.run_ts_return_frame = self.run_ts_return_until = 0;
	self.run_ts_return_block = FALSE;
	sprint(self, PRINT_HIGH, "host_timescale: normal speed, clean new attempt armed here\n");
};
