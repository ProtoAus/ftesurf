/*
  P1100 (TAS plan 6.1, Lex's decisions of 29 Oct): a legal-start session. `tas start <zone>` places
  the player standing still at a start zone's own destination (SV_ZoneMove -> SV_ZoneDest, where
  `!r` puts a player) and pauses: tick 0. Each TAS step taken in the box is logged (the `in` row's
  sources: .movement, input_angles, the three mover bits) until the step that starts the clock
  (startat). A back to a tick before the start re-places the player and replays the log through
  the input tape -- the placement is canonical (p1100-canon1) and replays are exact, so no second
  rewind ring. After the start the running-phase TAS (ring, recorder, projects) is unchanged.

  Valid while: in the box, nothing re-placed the player since this session's own placement
  (taslg_moved, counted by SV_TASCancel, a respawn and setpos); after the start, the run is the
  recording this session started (rec_rec_serial). Anything else ends the session with a line
  saying so. Each row also keeps the body's state before its move; a replay compares it, so a
  world that moved (a door, another player) ends the session instead of landing elsewhere.
*/
#define TASLG_MAX 4096           // ticks before the start a session holds (61 s at 15 ms)
#define TASLG_STRIDE 13          // TAS_INPUT_STRIDE inputs, then origin and velocity before the move
float *taslg_buf[FS_MAXPLAYERS + 1];

float(entity e) SV_TASLegalValid =
{
	if (!e.taslg_on) return FALSE;
	if (e.run_t_state == TS_ARMED) return !e.taslg_startat && e.taslg_moved == e.taslg_mark;
	if (e.run_t_state == TS_RUNNING) return e.taslg_startat > 0 && e.rec_rec_serial == e.taslg_serial;
	return FALSE;
};

void(entity e, string why) SV_TASLegalEnd =
{
	if (!e.taslg_on) return;
	e.taslg_on = 0; e.taslg_target = -1;
	sprint(e, PRINT_HIGH, sprintf("tas: legal start session ended: %s\n", why));
};

// Places e at its session's start zone without counting it as a foreign move; TRUE if armed there.
float(entity e) SV_TASLegalPlace =
{
	local entity was;
	e.taslg_placing = 1;
	was = self; self = e;
	SV_ZoneMove(e.taslg_zone);
	self = was;
	e.taslg_placing = 0;
	if (e.run_t_state != TS_ARMED) return FALSE;
	SV_TASMark(e);
	e.run_tas_mode = TRUE;
	e.run_tas_seen = e.run_tas_done;
	e.run_tas_paused = TRUE;
	// A tape is bound to a recording serial above 0; a connection that never recorded has 0.
	if (e.rec_rec_serial <= 0) e.rec_rec_serial = SV_RecNextSerial();
	e.taslg_mark = e.taslg_moved;
	e.taslg_n = 0; e.taslg_startat = 0; e.taslg_serial = 0; e.taslg_wait = 0;
	return TRUE;
};

void(entity e, float z) SV_TASLegalStart =
{
	local float s, ok;
	if (e.run_tas_ready != 1 || !e.run_tas_rwcap || !checkbuiltin(tas_tape))
	{
		sprint(e, PRINT_HIGH, "tas: a legal start needs the P1055 engine, Source 15ms clock and native checkpoints\n");
		return;
	}
	if (!zone_loaded) SV_ZoneFrame();
	// Nested: || does not short-circuit here, and zone_type[z] out of range is a fatal VM error.
	ok = (z >= 0 && z < zone_count && z == floor(z));
	if (ok) ok = (zone_type[z] == ZONE_START || zone_type[z] == ZONE_STAGE);
	if (!ok)
	{
		sprint(e, PRINT_HIGH, "tas start <zone>: the number of a start or stage zone (zone_list names them)\n");
		return;
	}
	if (!SV_TASCanPause(e)) return;
	s = num_for_edict(e);
	if (!taslg_buf[s]) taslg_buf[s] = (float*)memalloc(TASLG_MAX * TASLG_STRIDE * 4);
	if (!taslg_buf[s]) { sprint(e, PRINT_HIGH, "tas: out of memory for a legal start\n"); return; }
	e.run_t_wantstage1 = FALSE;     // as the zone_goto arm: a standing `!s 1` does not survive a placement
	e.taslg_on = 1; e.taslg_zone = z; e.taslg_len = 0; e.taslg_target = -1;
	if (!SV_TASLegalPlace(e))
	{
		e.taslg_on = 0;
		sprint(e, PRINT_HIGH, "tas: that zone did not arm a run; no legal start\n");
		return;
	}
	sprint(e, PRINT_HIGH, sprintf("tas: legal start at zone %.0f (track %.0f): tick 0, standing at its start; paused\n",
		z, zone_track[z]));
};

// One TAS step in the box, from PlayerPreThink after the recorder's own `in` row.
void(entity e) SV_TASLegalLog =
{
	local float s, b, bt;
	local vector an;
	if (!e.taslg_on || e.run_t_state != TS_ARMED) return;
	if (!SV_TASLegalValid(e)) { SV_TASLegalEnd(e, "the player was moved, or played live, in the start box"); return; }
	if (!e.run_tas_paused || input_cmd_later) { SV_TASLegalEnd(e, "an input in the start box that was not one TAS step"); return; }
	if (e.taslg_n >= TASLG_MAX) { SV_TASLegalEnd(e, "longer than a start box holds (61 s)"); return; }
	s = num_for_edict(e);
	b = e.taslg_n * TASLG_STRIDE;
	bt = 0;
	if (e.button2) bt = bt + 1;
	if (e.button4) bt = bt + 2;
	if (e.button8) bt = bt + 4;
	an = [SV_TASPWord(input_angles_x), SV_TASPWord(input_angles_y), SV_TASPWord(input_angles_z)];
	if (e.taslg_target >= 0)
	{
		// Replaying the log: the step must be the row it was staged from.
		if (taslg_buf[s][b] != e.movement_x || taslg_buf[s][b+1] != e.movement_y || taslg_buf[s][b+2] != e.movement_z ||
		    taslg_buf[s][b+3] != an_x || taslg_buf[s][b+4] != an_y || taslg_buf[s][b+5] != an_z || taslg_buf[s][b+6] != bt)
		{
			SV_TASLegalEnd(e, sprintf("the replay did not apply the logged input of tick %.0f", e.taslg_n + 1));
			return;
		}
		if (taslg_buf[s][b+7] != e.origin_x || taslg_buf[s][b+8] != e.origin_y || taslg_buf[s][b+9] != e.origin_z ||
		    taslg_buf[s][b+10] != e.velocity_x || taslg_buf[s][b+11] != e.velocity_y || taslg_buf[s][b+12] != e.velocity_z)
		{
			SV_TASLegalEnd(e, sprintf("the replay DIVERGED before tick %.0f (something in the start box moved)", e.taslg_n + 1));
			return;
		}
	}
	else
	{
		taslg_buf[s][b] = e.movement_x; taslg_buf[s][b+1] = e.movement_y; taslg_buf[s][b+2] = e.movement_z;
		taslg_buf[s][b+3] = an_x; taslg_buf[s][b+4] = an_y; taslg_buf[s][b+5] = an_z;
		taslg_buf[s][b+6] = bt;
		taslg_buf[s][b+7] = e.origin_x; taslg_buf[s][b+8] = e.origin_y; taslg_buf[s][b+9] = e.origin_z;
		taslg_buf[s][b+10] = e.velocity_x; taslg_buf[s][b+11] = e.velocity_y; taslg_buf[s][b+12] = e.velocity_z;
		e.taslg_len = e.taslg_n + 1;
	}
	e.taslg_n = e.taslg_n + 1;
};

// Back to logged tick `target` (0..len-1, before the start): re-place, then replay rows 1..target.
void(entity e, float target) SV_TASLegalBack =
{
	if (!(target >= 0 && target < e.taslg_len && target == floor(target)))
	{
		sprint(e, PRINT_HIGH, sprintf("tas: a legal back reaches ticks 0..%.0f before the start\n", e.taslg_len - 1));
		return;
	}
	if (!SV_TASLegalPlace(e)) { SV_TASLegalEnd(e, "the start zone did not arm a run again"); return; }
	e.taslg_target = target;
	if (!target)
	{
		e.taslg_target = -1;
		sprint(e, PRINT_HIGH, "tas: back to tick 0, standing at the start; paused\n");
	}
};

// Settled and idle paused frames: the start's tick, and the next replay chunk.
void(entity e) SV_TASLegalFrame =
{
	local float s, count, tx, ok, i, b;
	if (!e.taslg_on) return;
	if (e.run_tas_fault) { SV_TASLegalEnd(e, "a TAS step faulted"); return; }
	// Two steps in one packet: the clock starts at the packet's end, so a replay that stops between
	// them can start it a tick early. That is not the run this start logged.
	if (e.taslg_target >= 0 && e.run_t_state == TS_RUNNING)
	{
		SV_TASLegalEnd(e, "the replay started the clock before its tick (two steps had shared a packet)");
		return;
	}
	if (!e.taslg_startat && e.run_t_state == TS_RUNNING && e.taslg_moved == e.taslg_mark && e.taslg_target < 0)
	{
		e.taslg_startat = e.taslg_n; e.taslg_serial = e.rec_rec_serial;
		sprint(e, PRINT_HIGH, sprintf("tas: the run started on tick %.0f of the legal start\n", e.taslg_startat));
	}
	if (!SV_TASLegalValid(e))
	{
		SV_TASLegalEnd(e, e.run_t_state == TS_ARMED ? "the player was moved in the start box" : "the run is no longer the one this start began");
		return;
	}
	if (e.taslg_target < 0) return;
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING || e.run_tas_pending) return;
	if (e.taslg_n == e.taslg_target)
	{
		// The body after the last replayed step is the state logged before the next one.
		s = num_for_edict(e); b = e.taslg_n * TASLG_STRIDE;
		if (taslg_buf[s][b+7] != e.origin_x || taslg_buf[s][b+8] != e.origin_y || taslg_buf[s][b+9] != e.origin_z ||
		    taslg_buf[s][b+10] != e.velocity_x || taslg_buf[s][b+11] != e.velocity_y || taslg_buf[s][b+12] != e.velocity_z)
		{
			SV_TASLegalEnd(e, sprintf("the replay DIVERGED at tick %.0f (something in the start box moved)", e.taslg_n));
			return;
		}
		e.taslg_target = -1;
		sprint(e, PRINT_HIGH, sprintf("tas: back to tick %.0f of the legal start (before the clock); paused\n", e.taslg_n));
		return;
	}
	if (e.taslg_n > e.taslg_target) { SV_TASLegalEnd(e, "the replay passed its tick"); return; }
	s = num_for_edict(e);
	count = min(TAS_TAPE_MAX, e.taslg_target - e.taslg_n);
	ok = tas_tape(e, 2, count, 0, '0 0 0', '0 0 0', 0);
	tx = ok ? tas_tape(e, 3, count, 0, '0 0 0', '0 0 0', 0) : 0;
	ok = tx > 0;
	for (i = 0; i < count && ok; i = i + 1)
	{
		b = (e.taslg_n + i) * TASLG_STRIDE;
		ok = tas_tape(e, 4, tx, i, [taslg_buf[s][b], taslg_buf[s][b+1], taslg_buf[s][b+2]],
			[taslg_buf[s][b+3], taslg_buf[s][b+4], taslg_buf[s][b+5]], taslg_buf[s][b+6]);
	}
	if (ok) ok = tas_tape(e, 5, tx, 0, '0 0 0', '0 0 0', 0);
	if (!ok)
	{
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
		// A placement's holds release over a frame or two: a refused tape waits up to a second.
		if (!e.taslg_wait) e.taslg_wait = time + 1;
		if (time > e.taslg_wait) SV_TASLegalEnd(e, "the engine refused the replay tape");
		return;
	}
	e.taslg_wait = 0;
	e.run_tas_replayserial = e.rec_rec_serial;
};
