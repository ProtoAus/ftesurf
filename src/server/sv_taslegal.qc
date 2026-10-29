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
	// A v3 load that fails in the start box has reproduced nothing: it keeps nothing attached.
	if (e.taslg_loading) { e.taslg_loading = 0; SV_TASProjectReset(e); e.tasp_result = 3; SV_TASProjectEvent(e); }
	// A replay in flight stops here, not a packet later from wherever the player now is.
	if (e.taslg_target >= 0 && checkbuiltin(tas_tape)) tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
	e.taslg_on = 0; e.taslg_target = -1; e.taslg_verify = 0;
	sprint(e, PRINT_HIGH, sprintf("tas: legal start session ended: %s\n", why));
};

// Places e at its session's start zone without counting it as a foreign move; TRUE if armed there.
float(entity e) SV_TASLegalPlace =
{
	local entity was;
	e.run_t_wantstage1 = FALSE;     // as the zone_goto arm: a standing `!s 1` does not survive a placement
	e.taslg_placing = 1;
	SV_TpDestReset(e);      // as `!r` (Patch 1050): no SetRemoteDestination entry survives the placement
	was = self; self = e;
	SV_ZoneMove(e.taslg_zone);
	self = was;
	e.taslg_placing = 0;
	if (e.run_t_state != TS_ARMED) return FALSE;
	e.taslg_o0 = e.origin;
	SV_TASMark(e);
	e.run_tas_mode = TRUE;
	e.run_tas_seen = e.run_tas_done;
	e.run_tas_paused = TRUE;
	// Validate and begin need the native input pool, which a fresh map has none of until a step or
	// plan makes one: make it as `tas plan live` would, only when missing (a configured plan survives).
	if (!tas_tape(e, 1, 0, 0, '0 0 0', '0 0 0', 0) && e.run_tas_plancap >= TAS_PLAN_CAP)
		tas_tape(e, TAS_OP_PLANSET, 0, 0, '0 0 0', '0 0 0', 0);
	// A tape is bound to a recording serial above 0; a connection that never recorded has 0.
	if (e.rec_rec_serial <= 0) e.rec_rec_serial = SV_RecNextSerial();
	e.taslg_mark = e.taslg_moved;
	e.taslg_n = 0; e.taslg_startat = 0; e.taslg_serial = 0; e.taslg_wait = 0; e.taslg_verify = 0;
	e.taslg_loading = 0;    // a back or a start during a load's box replay leaves it a plain session
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
		sprint(e, PRINT_HIGH, "tas start <zone>: the number of a start or stage zone (cmd zone_dests lists them)\n");
		return;
	}
	// The stage you are on in a running run is a stage restart (the run goes on), not a start.
	if (SV_TimerWouldRestartSeg(e, z))
	{
		sprint(e, PRINT_HIGH, "tas start: that zone restarts the stage you are on, it does not arm a run; !r first\n");
		return;
	}
	if (!SV_TASCanPause(e)) return;
	s = num_for_edict(e);
	if (s < 1 || s > FS_MAXPLAYERS) { sprint(e, PRINT_HIGH, "tas: no legal start in this player slot\n"); return; }
	if (!taslg_buf[s]) taslg_buf[s] = (float*)memalloc(TASLG_MAX * TASLG_STRIDE * 4);
	if (!taslg_buf[s]) { sprint(e, PRINT_HIGH, "tas: out of memory for a legal start\n"); return; }
	SV_TASProjectReset(e);          // a session's first save is a root; its later saves continue that line
	SV_TASProjectEvent(e);
	e.taslg_on = 1; e.taslg_zone = z; e.taslg_len = 0; e.taslg_target = -1;
	if (!SV_TASLegalPlace(e))
	{
		e.taslg_on = 0;
		sprint(e, PRINT_HIGH, "tas: moved to that zone, but it did not arm a run (a restart in the middle of one?); no legal start\n");
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
	// After a back, the first step's PreThink sees the replay's end state where the log saw it.
	if (e.taslg_verify)
	{
		e.taslg_verify = 0;
		if (taslg_buf[s][b+7] != e.origin_x || taslg_buf[s][b+8] != e.origin_y || taslg_buf[s][b+9] != e.origin_z ||
		    taslg_buf[s][b+10] != e.velocity_x || taslg_buf[s][b+11] != e.velocity_y || taslg_buf[s][b+12] != e.velocity_z)
		{
			SV_TASLegalEnd(e, sprintf("the replay DIVERGED at tick %.0f (something in the start box moved)", e.taslg_n));
			return;
		}
	}
	bt = 0;
	if (e.button2) bt = bt + 1;
	if (e.button4) bt = bt + 2;
	if (e.button8) bt = bt + 4;
	an = [SV_TASPWord(input_angles_x), SV_TASPWord(input_angles_y), SV_TASPWord(input_angles_z)];
	if (e.taslg_target >= 0 && e.taslg_loading)
	{
		// A v3 load: the inputs must be the file's; the states are this replay's, kept for later backs.
		if (taslg_buf[s][b] != e.movement_x || taslg_buf[s][b+1] != e.movement_y || taslg_buf[s][b+2] != e.movement_z ||
		    taslg_buf[s][b+3] != an_x || taslg_buf[s][b+4] != an_y || taslg_buf[s][b+5] != an_z || taslg_buf[s][b+6] != bt)
		{
			SV_TASLegalEnd(e, sprintf("the load did not apply the file's input of tick %.0f", e.taslg_n + 1));
			return;
		}
		taslg_buf[s][b+7] = e.origin_x; taslg_buf[s][b+8] = e.origin_y; taslg_buf[s][b+9] = e.origin_z;
		taslg_buf[s][b+10] = e.velocity_x; taslg_buf[s][b+11] = e.velocity_y; taslg_buf[s][b+12] = e.velocity_z;
	}
	else if (e.taslg_target >= 0)
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

void(entity e) SV_TASLegalLoadRun;
float(entity e, float n) SV_TimerWouldRestartSeg;

// Settled and idle paused frames: the start's tick, and the next replay chunk.
void(entity e) SV_TASLegalFrame =
{
	local float s, count, tx, ok, i, b;
	if (!e.taslg_on) return;
	if (e.run_tas_fault) { SV_TASLegalEnd(e, "a TAS step faulted"); return; }
	// A v3 load's start box ends where the file says the clock started (or, never started, at its head).
	if (e.taslg_loading && e.taslg_target >= 0 && e.taslg_n == e.taslg_target)
	{
		if (e.taslg_moved != e.taslg_mark)
		{
			SV_TASLegalEnd(e, "the player was moved during the load");
			return;
		}
		if (e.tasp_lstartat > 0)
		{
			if (e.run_t_state != TS_RUNNING)
			{
				SV_TASLegalEnd(e, sprintf("the load did not start the clock on tick %.0f as saved", e.tasp_lstartat));
				return;
			}
			e.taslg_startat = e.taslg_n; e.taslg_serial = e.rec_rec_serial; e.taslg_line0 = e.rec_rec_lines;
		}
		else if (e.run_t_state != TS_ARMED)
		{
			SV_TASLegalEnd(e, "the load started the clock, which the saved project never did");
			return;
		}
		e.taslg_target = -1; e.taslg_loading = 0;
		SV_TASLegalLoadRun(e);
		return;
	}
	if (e.taslg_loading && e.taslg_target >= 0 && e.run_t_state == TS_RUNNING)
	{
		if (!e.tasp_lstartat) SV_TASLegalEnd(e, "the load started the clock, which the saved project never did");
		else SV_TASLegalEnd(e, sprintf("the load started the clock on tick %.0f, before the saved %.0f", e.taslg_n, e.tasp_lstartat));
		return;
	}
	// Two steps in one packet: the clock starts at the packet's end, so a replay that stops between
	// them can start it a tick early. That is not the run this start logged.
	if (e.taslg_target >= 0 && e.run_t_state == TS_RUNNING)
	{
		SV_TASLegalEnd(e, "the replay started the clock before its tick (two steps had shared a packet)");
		return;
	}
	if (!e.taslg_startat && e.run_t_state == TS_RUNNING && e.taslg_moved == e.taslg_mark && e.taslg_target < 0)
	{
		e.taslg_startat = e.taslg_n; e.taslg_serial = e.rec_rec_serial; e.taslg_line0 = e.rec_rec_lines;
		sprint(e, PRINT_HIGH, sprintf("tas: the run started on tick %.0f of the legal start\n", e.taslg_startat));
	}
	if (!SV_TASLegalValid(e))
	{
		SV_TASLegalEnd(e, e.run_t_state == TS_ARMED ? "the player was moved, or TAS played or turned off, in the start box"
			: "the run is no longer the one this start began");
		return;
	}
	if (e.taslg_target < 0) return;
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE || e.run_tas_replaystate == TAS_TAPE_STAGING || e.run_tas_pending) return;
	if (e.taslg_n == e.taslg_target)
	{
		// The end state is checked at the next step's PreThink, where the log read it (a push's
		// velocity lands between PostThink and PreThink).
		e.taslg_verify = 1;
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

/*
  P1100 step 3: save a legal-start session as a version 3 project -- a root revision, ticks from
  the placement: the start box's rows from the session's log, then (once the clock started) the
  recorder's `in` rows from run tick 1, harvested as a base-save project's are but with
  tasp_base = -startat so they land at their total tick. One checkpoint: the head.
*/
void(entity e, string name, float force) SV_TASProjectSaveLegal =
{
	local float s, ls, head, pre, running, t, j, run, child, attached, same, prev, prevparent, supa, supb;
	local filestream f;
	local string parent, oname, oparent;
	s = SV_TASPSlot(e); ls = num_for_edict(e);
	if (!s || !SV_TASPLocalOnly(e)) return;
	// The session's line (its load, or its last save): kept through a close or a failed save, as a
	// base-save project's is (P1090); only `tas start`, a load or a base-save save end it.
	child = (e.tasp_legal && tasp_revsha[s] != "");
	attached = (child && e.tasp_on && tasp_name[s] != "");
	if (e.tasp_load) { sprint(e, PRINT_HIGH, "tas project: a load is still running\n"); return; }
	if (!e.run_tas_paused || e.run_tas_pending || e.taslg_target >= 0)
	{
		sprint(e, PRINT_HIGH, "tas project: pause, and let a back finish, before saving a legal start\n");
		return;
	}
	running = (e.run_t_state == TS_RUNNING);
	if (running) SV_RewindTASHead(e);   // the harvest checks the last tick against this ring row
	if (running && SV_ViewTicks(e))
	{
		sprint(e, PRINT_HIGH, "tas project: this run opened a viewing window; a legal start saves none\n");
		return;
	}
	run = running ? SV_TimerTicks(e) : 0;
	pre = running ? e.taslg_startat : e.taslg_n;
	head = pre + run;
	if (head < 1) { sprint(e, PRINT_HIGH, "tas project: take a step before saving\n"); return; }
	if (head > TASP_MAX) { sprint(e, PRINT_HIGH, "tas project: longer than a project holds\n"); return; }
	if (name == "" && attached) name = tasp_name[s];
	if (name == "")
		for (t = 1; t < 1000; t = t + 1)
		{
			name = sprintf("tas%.0f", t);
			if (!SV_TASPExists(name)) break;
		}
	if (SV_TASPExists(name) && !force && !(attached && name == tasp_name[s]))
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: %s already exists; save under a new name, or tas project save %s force\n", name, name));
		return;
	}
	if (attached && name == tasp_name[s] && head < e.tasp_lhead && !force)
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: %s has ticks to %.0f and you are at %.0f; saving would cut them. Save under a new name, or tas project save %s force\n",
			name, e.tasp_lhead, head, name));
		return;
	}
	if (!SV_TASPExists(name) && SV_TASPCount() >= TASP_FILES)
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: %.0f projects on this map is the limit\n", TASP_FILES));
		return;
	}
	if (!SV_TASPIdentityOK(e)) return;
	if (!SV_SaveLocRate(e)) return;
	name = strzone(name);
	// The rows are rebuilt whole; only the line (revsha, and the parent's rows for the supply) carries
	// over. Same name: the next revision; another name: a fork naming it; a closed line: rev 1 of it.
	same = (child && tasp_name[s] != "" && name == tasp_name[s]);
	prev = e.tasp_rev; prevparent = e.tasp_parentrev;
	if (child && tasp_name[s] != "" && !same) parent = strzone(tasp_name[s]);
	else if (same) parent = strzone(tasp_parent[s]);
	else parent = strzone("");
	if (tasp_buf[s]) memfree(tasp_buf[s]);
	if (tasp_cp[s]) memfree(tasp_cp[s]);
	tasp_buf[s] = 0; tasp_cp[s] = 0;
	e.tasp_n = e.tasp_cap = e.tasp_ncp = 0;
	if (tasp_cpnames[s]) strunzone(tasp_cpnames[s]);
	tasp_cpnames[s] = "";
	if (!child && tasp_revsha[s] != "") { strunzone(tasp_revsha[s]); tasp_revsha[s] = ""; }
	e.tasp_on = 0; e.tasp_baseid = 0;   // detached until the write lands (the rows are this save's now)
	if (!SV_TASPEnsure(e, s, head)) { sprint(e, PRINT_HIGH, "tas project: out of memory\n"); strunzone(name); strunzone(parent); SV_TASProjectEvent(e); return; }
	for (t = 0; t < pre; t = t + 1)
		for (j = 0; j < TAS_INPUT_STRIDE; j = j + 1)
			tasp_buf[s][t * TAS_INPUT_STRIDE + j] = taslg_buf[ls][t * TASLG_STRIDE + j];
	e.tasp_n = pre;
	if (running && run > 0)
	{
		// From the start's line, not the ring's tick 0: the ring keeps 60 s (RW_CAP), a run is longer.
		e.tasp_base = -pre; e.tasp_synced = 0;
		SV_TASPAnchorLine(e, e.taslg_line0, FALSE);
		if (!SV_TASPHarvest(e, s, run))
		{
			sprint(e, PRINT_HIGH, sprintf("tas project: cannot save: %s; nothing written\n", tasp_why));
			strunzone(name); strunzone(parent); e.tasp_n = 0; e.tasp_base = 0; SV_TASProjectEvent(e); return;
		}
	}
	e.tasp_base = 0; e.tasp_n = head;
	tasp_cp[s] = (float*)memalloc(TASP_CPMAX * TASP_CPSTRIDE * 4);   // the size `tas cp` assumes
	if (tasp_cp[s])
	{
		tasp_cp[s][0] = head; tasp_cp[s][1] = 0;
		tasp_cp[s][2] = e.origin_x; tasp_cp[s][3] = e.origin_y; tasp_cp[s][4] = e.origin_z;
		tasp_cp[s][5] = e.velocity_x; tasp_cp[s][6] = e.velocity_y; tasp_cp[s][7] = e.velocity_z;
		e.tasp_ncp = 1;
	}
	e.tasp_legal = 1; e.tasp_lzone = e.taslg_zone; e.tasp_lstartat = running ? e.taslg_startat : 0; e.tasp_lo = e.taslg_o0;
	e.tasp_parentrev = same ? prevparent : (parent != "" ? prev : 0);
	e.tasp_rev = same ? prev + 1 : 1;
	supa = e.tasp_supa; supb = e.tasp_supb;
	SV_TASPSupply(e, s, head);   // against the parent's rows (base 0 too), or all of a root's
	oname = tasp_name[s]; oparent = tasp_parent[s];
	tasp_name[s] = name; tasp_parent[s] = parent;
	if (!SV_TASPWrite(e, s, name, parent))
	{
		// The line stays the last revision's (a retry is its child); the project is detached, as after a
		// failed base-save save: a default name forks, the same name needs force.
		sprint(e, PRINT_HIGH, "tas project: cannot write the project file\n");
		strunzone(name); strunzone(parent);
		tasp_name[s] = oname; tasp_parent[s] = oparent;
		e.tasp_rev = prev; e.tasp_parentrev = prevparent; e.tasp_supa = supa; e.tasp_supb = supb;
		SV_TASProjectEvent(e); return;
	}
	if (oname) strunzone(oname);
	if (oparent) strunzone(oparent);
	SV_TASPParentKeep(e, s);
	// Attached for the next save and the panel; the base-save hooks never follow it (tasp_serial).
	e.tasp_on = 1; e.tasp_load = 0; e.tasp_serial = -1; e.tasp_lhead = head;
	e.tasp_filehead = head; e.tasp_result = 0; e.tasp_dev = e.tasp_devtick = 0;
	if (!SV_TASPKeep(SV_TASPPath(name), tasp_revsha[s], FALSE, FALSE))
		sprint(e, PRINT_HIGH, "tas project: could not keep this revision under its hash; Sign will try again\n");
	if (strstrofs(infokey(e, "ip"), "LoopBack", 0) >= 0 && !SV_TASPFileIs(SV_TASPRevPath(tasp_revsha[s], "made")))
	{
		f = fopen(SV_TASPRevPath(tasp_revsha[s], "made"), FILE_WRITE);
		if (f >= 0) { fputs(f, "saved here\n"); fclose(f); }
	}
	e.tasp_made = SV_TASPFileIs(SV_TASPRevPath(tasp_revsha[s], "made"));
	e.tasp_signed = SV_TASPSignedFor(tasp_revsha[s]);
	if (e.tasp_lstartat)
		sprint(e, PRINT_HIGH, sprintf("tas project: saved %s rev %.0f: a legal start at zone %.0f, inputs to tick %.0f, the clock started on tick %.0f\n",
			name, e.tasp_rev, e.tasp_lzone, head, e.tasp_lstartat));
	else
		sprint(e, PRINT_HIGH, sprintf("tas project: saved %s rev %.0f: a legal start at zone %.0f, inputs to tick %.0f, before the clock\n",
			name, e.tasp_rev, e.tasp_lzone, head));
	SV_TASPSupplyNote(e);
	SV_TASProjectEvent(e);
};

/*
  P1100 step 3: load a version 3 project. Place at its start zone (the body must land on the file's
  baseat), replay the start box from the file's rows through the step that starts the clock, then
  hand the rest to the project driver in run ticks (tasp_base = -startat puts run tick r at row
  startat + r). The tpr_* globals hold the file read by SV_TASProjectLoad.
*/
void(entity e, string name, string cpname) SV_TASLegalLoad =
{
	local float s, ls, z, ok, t, j, pre, bad;
	s = SV_TASPSlot(e); ls = num_for_edict(e);
	if (!e.run_tas_rwcap)
	{
		sprint(e, PRINT_HIGH, "tas project: a legal start needs native checkpoints; nothing changed\n");
		SV_TASPReadFree(); return;
	}
	if (cpname != "")
	{
		sprint(e, PRINT_HIGH, "tas project: a legal start loads to its head (no named checkpoints yet); nothing changed\n");
		SV_TASPReadFree(); return;
	}
	z = tpr_zone;
	if (!zone_loaded) SV_ZoneFrame();
	ok = (z >= 0 && z < zone_count && z == floor(z));
	if (ok) ok = (zone_type[z] == ZONE_START || zone_type[z] == ZONE_STAGE);
	if (!ok || ls < 1 || ls > FS_MAXPLAYERS)
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: %s starts at zone %.0f, which is not a start zone here; nothing changed\n", name, z));
		SV_TASPReadFree(); return;
	}
	if (SV_TimerWouldRestartSeg(e, z))
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: %s starts at zone %.0f, the stage you are on in this run; !r first; nothing changed\n", name, z));
		SV_TASPReadFree(); return;
	}
	pre = tpr_startat ? tpr_startat : tpr_n;
	if (pre > TASLG_MAX)
	{
		sprint(e, PRINT_HIGH, "tas project: its start box is longer than a session holds; nothing changed\n");
		SV_TASPReadFree(); return;
	}
	if (!SV_TASCanPause(e)) { SV_TASPReadFree(); return; }
	if (!SV_SaveLocRate(e)) { SV_TASPReadFree(); return; }
	if (!taslg_buf[ls]) taslg_buf[ls] = (float*)memalloc(TASLG_MAX * TASLG_STRIDE * 4);
	if (!taslg_buf[ls]) { sprint(e, PRINT_HIGH, "tas project: out of memory\n"); SV_TASPReadFree(); return; }
	SV_TASHistoryReset(e);
	SV_TASProjectReset(e);
	e.taslg_on = 1; e.taslg_zone = z; e.taslg_len = 0; e.taslg_target = -1; e.taslg_loading = 0;
	if (!SV_TASLegalPlace(e))
	{
		e.taslg_on = 0;
		sprint(e, PRINT_HIGH, "tas project: its start zone did not arm a run; not replaying\n");
		SV_TASPReadFree(); return;
	}
	if (e.origin != tpr_bo)
	{
		SV_TASLegalEnd(e, "the start zone does not place the body where this project began (the zones changed?)");
		SV_TASPReadFree(); return;
	}
	bad = SV_TASPValidate(e, tpr_buf, tpr_n);
	if (bad)
	{
		SV_TASLegalEnd(e, sprintf("input row %.0f of the project is refused by the engine", bad));
		SV_TASPReadFree(); return;
	}
	for (t = 0; t < pre; t = t + 1)
		for (j = 0; j < TAS_INPUT_STRIDE; j = j + 1)
			taslg_buf[ls][t * TASLG_STRIDE + j] = tpr_buf[t * TAS_INPUT_STRIDE + j];
	e.taslg_len = pre;
	// The project, attached once the run part starts (SV_TASLegalLoadRun).
	tasp_buf[s] = tpr_buf; tasp_cp[s] = tpr_cp; tpr_buf = 0; tpr_cp = 0;
	tasp_name[s] = strzone(name);
	tasp_hash[s] = tpr_hash; tasp_parent[s] = tpr_parent; tasp_cpnames[s] = tpr_cpnames;
	tpr_hash = tpr_parent = tpr_cpnames = "";
	tasp_revsha[s] = strzone(tpr_h);
	if (tpr_revsha != "" && tpr_revsha != tasp_revsha[s])
		sprint(e, PRINT_HIGH, "tas project: this file was changed after it was saved (its revsha does not match)\n");
	tasp_parsha[s] = tpr_parsha; tpr_parsha = "";
	e.tasp_supa = tpr_supa; e.tasp_supb = tpr_supb;
	e.tasp_signed = SV_TASPSignedFor(tasp_revsha[s]);
	e.tasp_made = SV_TASPFileIs(SV_TASPRevPath(tasp_revsha[s], "made"));
	e.tasp_n = tpr_n; e.tasp_cap = tpr_size; e.tasp_ncp = tpr_ncp; e.tasp_rev = tpr_rev;
	e.tasp_base = 0; e.tasp_legal = 1; e.tasp_lzone = z; e.tasp_lstartat = tpr_startat; e.tasp_lo = tpr_bo;
	e.tasp_on = 0; e.tasp_load = 0; e.tasp_parentrev = tpr_parentrev; e.tasp_baseid = 0; e.tasp_lhead = tpr_n;
	SV_TASPReadFree();
	SV_TASPParentKeep(e, s);
	SV_TASPKeep(SV_TASPPath(name), tasp_revsha[s], FALSE, FALSE);
	if (e.run_tas_req < 16000000) e.run_tas_req = e.run_tas_req + 1;  // stale timeline pages refuse
	e.taslg_loading = 1; e.taslg_target = pre;
	e.tasp_load = 1; e.tasp_stop = pre; e.tasp_filehead = tpr_n;
	sprint(e, PRINT_HIGH, sprintf("tas project: loading %s rev %.0f: placed at zone %.0f, replaying the start box to tick %.0f\n",
		name, e.tasp_rev, z, pre));
	SV_TASProjectEvent(e);
};

// The start box is replayed: finish, or hand the run part to the project driver.
void(entity e) SV_TASLegalLoadRun =
{
	local float s, k, b, d;
	s = SV_TASPSlot(e);
	if (!s) return;
	if (!e.tasp_lstartat || e.tasp_n <= e.tasp_lstartat)
	{
		// Nothing ran after the box: the saved state at its head is the one check.
		d = -1;
		for (k = 0; k < e.tasp_ncp; k = k + 1)
		{
			b = k * TASP_CPSTRIDE;
			if (tasp_cp[s][b] == e.taslg_n)
				d = max(vlen(e.origin - [tasp_cp[s][b+2], tasp_cp[s][b+3], tasp_cp[s][b+4]]),
					vlen(e.velocity - [tasp_cp[s][b+5], tasp_cp[s][b+6], tasp_cp[s][b+7]]));
		}
		e.tasp_on = 1; e.tasp_load = 0; e.tasp_serial = -1; e.tasp_filehead = e.tasp_n;
		e.tasp_dev = max(d, 0); e.tasp_devtick = (d > 0) ? e.taslg_n : 0;
		e.tasp_result = (d < 0) ? 0 : ((d > 0) ? 2 : 1);
		if (d > 0)
			sprint(e, PRINT_HIGH, sprintf("tas project: loaded %s to tick %.0f (%s); DIVERGED from its saved state (%.4f); paused\n",
				tasp_name[s], e.taslg_n, e.tasp_lstartat ? "the clock started on its last tick" : "the start box, before the clock", d));
		else
			sprint(e, PRINT_HIGH, sprintf("tas project: loaded %s to tick %.0f (%s); %s; paused\n",
				tasp_name[s], e.taslg_n, e.tasp_lstartat ? "the clock started on its last tick" : "the start box, before the clock",
				d < 0 ? "no saved state to compare" : "reproduced its saved state exactly"));
		SV_TASProjectEvent(e);
		return;
	}
	// Checkpoints into run ticks, which the driver compares against.
	for (k = 0; k < e.tasp_ncp; k = k + 1)
	{
		b = k * TASP_CPSTRIDE;
		tasp_cp[s][b] = tasp_cp[s][b] - e.tasp_lstartat;
	}
	e.tasp_base = -e.tasp_lstartat;
	e.tasp_stop = e.tasp_n - e.tasp_lstartat;
	e.tasp_on = 1; e.tasp_load = 1; e.tasp_cpi = 0; e.tasp_ccount = 0;
	e.tasp_serial = e.rec_rec_serial; e.tasp_synced = 0; e.tasp_lasthead = 0;
	e.tasp_filehead = e.tasp_stop; e.tasp_cut = e.tasp_stop;
	e.tasp_gen = e.rec_rec_gen; e.tasp_dev = e.tasp_devtick = 0; e.tasp_result = 0;
	SV_RewindTASHead(e);
	SV_TASProjectDrive(e);
};
