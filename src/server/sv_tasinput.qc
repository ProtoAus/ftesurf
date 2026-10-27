// P1065: bounded warm input editing. Native owns execution, never QC packet indices.
#define TAS_INPUT_STRIDE 7

float(entity e) SV_TASInputReady =
{
	if (!e.run_tas_incap || !checkbuiltin(tas_input) || !checkbuiltin(tas_tape))
	{
		sprint(e, PRINT_HIGH, "tas: input editing requires P1065 native/server support\n");
		return FALSE;
	}
	if (!e.run_tas_paused || e.run_tas_pending || e.run_t_state != TS_RUNNING ||
	    e.run_tas_replaystate == TAS_TAPE_ACTIVE)
	{
		sprint(e, PRINT_HIGH, "tas: input editing needs a paused running attempt with no queued work\n");
		return FALSE;
	}
	return SV_TASCanPause(e);
};

float(entity e, float tick, float *data, float index) SV_TASInputRead =
{
	local vector meta, moves, angles, bits;
	local float b;

	if (!SV_RewindFindTick(e, tick)) return FALSE;
	if (!SV_RewindWarmReady(e)) return FALSE;
	meta = tas_input(e, rw_native_slot, rw_native_token, 0);
	if (meta_x != 1) return FALSE;
	moves = tas_input(e, rw_native_slot, rw_native_token, 1);
	angles = tas_input(e, rw_native_slot, rw_native_token, 2);
	bits = tas_input(e, rw_native_slot, rw_native_token, 3);
	if (!tas_tape(e, 1, 0, 0, moves, angles, bits_x)) return FALSE;
	b = index * TAS_INPUT_STRIDE;
	data[b] = moves_x; data[b+1] = moves_y; data[b+2] = moves_z;
	data[b+3] = angles_x; data[b+4] = angles_y; data[b+5] = angles_z;
	data[b+6] = bits_x;
	return TRUE;
};

void(entity e, float argc) SV_TASInputs =
{
	local float n, head, tick;
	local float *data;

	n = 8;
	if (argc > 3) return;
	if (argc == 3)
	{
		if (!FS_TASNumber(argv(2))) return;
		n = fs_tas_number;
	}
	if (!(n >= 1 && n <= 16 && floor(n) == n))
	{
		sprint(e, PRINT_HIGH, "tas: inputs count is an integer 1..16\n");
		return;
	}
	if (!SV_TASInputReady(e)) return;
	if (time < e.run_tas_next) return;
	e.run_tas_next = time + 0.2;
	SV_RewindTASHead(e);
	head = SV_TimerTicks(e);
	data = (float*)memalloc(TAS_INPUT_STRIDE * 4);
	if (!data) return;
	for (tick = max(1, head - n + 1); tick <= head; tick = tick + 1)
	{
		if (!SV_TASInputRead(e, tick, data, 0))
		{
			sprint(e, PRINT_HIGH, sprintf("tas input %.0f: unavailable\n", tick));
			continue;
		}
		sprint(e, PRINT_HIGH, sprintf("tas input %.0f: move %g %g %g aim %.5f %.5f bits %.0f\n",
			tick, data[0], data[1], data[2], data[3] * 360 / 65536,
			data[4] * 360 / 65536, data[6]));
	}
	memfree(data);
};

void(float *data, float b, float field, float value) SV_TASInputChange =
{
	local float bit, mask;

	if (field >= 1 && field <= 3) data[b+field-1] = value;
	else if (field == 4 || field == 5) data[b+field-1] = FS_TASAngleWord(value);
	else
	{
		bit = (field == 6) ? 1 : ((field == 7) ? 2 : 4);
		mask = data[b+6];
		if (mask & (int)bit) mask = mask - bit;
		if (value) mask = mask + bit;
		data[b+6] = mask;
	}
};

void(entity e, float slot, float token) SV_TASInputUnpin =
{
	if (!e.rec_wt_hold) return; // a placed/cut failure cannot undo its recorder transaction
	SV_WatchRelease(e);
	e.run_tas_paused = TRUE;
	if (!tas_rewind(e, slot, token, 2))
		sprint(e, PRINT_HIGH, "tas: failed edit; head restore failed, remains paused\n");
	SV_TimerFreezeFrame(e);
};

void(entity e, float first, float last, float field, float value, float ticket) SV_TASRecalculate =
{
	local float head, count, i, b, serial, done, moves, prefix, pslot, ptoken;
	local float hslot, htoken, pmark, pgen, tx, ok;
	local float *data;
	local float *m;
	local vector move, angle;

	if (ticket <= e.run_tas_req)
	{
		sprint(e, PRINT_HIGH, "tas: duplicate/stale replay request ignored\n");
		return;
	}
	if (!SV_TASInputReady(e)) return;
	SV_RewindTASHead(e);
	head = SV_TimerTicks(e);
	count = head - first + 1;
	prefix = first - 1;
	if (!(first >= 1 && first <= last && last <= head && count >= 1 && count <= TAS_TAPE_MAX))
	{
		sprint(e, PRINT_HIGH, "tas: edit range must be retained ticks, with at most128 affected tail ticks\n");
		return;
	}
	if (!tas_tape(e, 2, count, 0, '0 0 0', '0 0 0', 0))
	{
		sprint(e, PRINT_HIGH, "tas: replay context/cumulative execution headroom unavailable\n");
		return;
	}
	if (!SV_RewindFindTick(e, head)) return;
	hslot = rw_native_slot; htoken = rw_native_token;
	if (!SV_RewindFindTick(e, prefix))
	{
		sprint(e, PRINT_HIGH, "tas: missing exact prefix; no edit performed\n");
		return;
	}
	if (!SV_RewindWarmReady(e))
	{
		sprint(e, PRINT_HIGH, "tas: exact warm prefix unavailable; no edit performed\n");
		return;
	}
	pslot = rw_native_slot; ptoken = rw_native_token;
	m = rw_slot[num_for_edict(e)];
	pmark = m[rw_statebase+29]; pgen = m[rw_statebase+34];
	serial = e.rec_rec_serial; done = e.run_tas_done; moves = e.run_movetick;
	data = (float*)memalloc(count * TAS_INPUT_STRIDE * 4);
	if (!data) return;
	ok = TRUE;
	for (i = 0; i < count; i = i + 1)
	{
		if (!SV_TASInputRead(e, first + i, data, i)) { ok = FALSE; break; }
		b = i * TAS_INPUT_STRIDE;
		if (field && first + i <= last) SV_TASInputChange(data, b, field, value);
		move = [data[b], data[b+1], data[b+2]];
		angle = [data[b+3], data[b+4], data[b+5]];
		if (!tas_tape(e, 1, 0, 0, move, angle, data[b+6])) { ok = FALSE; break; }
	}
	if (!ok)
	{
		memfree(data);
		sprint(e, PRINT_HIGH, "tas: missing/unsupported exact input or cut lineage; no edit performed\n");
		return;
	}
	if (!SV_SaveLocRate(e)) { memfree(data); return; }
	e.run_tas_req = ticket;
	e.run_tas_rwpin = TRUE;
	SV_WatchHold(e, TRUE);
	if (!e.rec_wt_hold) { e.run_tas_rwpin = FALSE; memfree(data); return; }
	e.rw_pin = TRUE;
	if (!SV_SaveLocCreateAtMode(e, prefix, '0 0 0', FALSE, TRUE, FALSE, 2))
	{
		SV_TASInputUnpin(e, hslot, htoken); memfree(data); return;
	}
	if (!SV_TASGo(e, pslot, ptoken))
	{
		SV_TASInputUnpin(e, hslot, htoken); memfree(data); return;
	}
	ok = (e.rec_rec_serial == serial && e.run_t_state == TS_RUNNING && e.run_t_clock &&
		(e.run_t_flags & TF_RECORDING) && SV_TimerTicks(e) == prefix &&
		e.run_tas_done == done && e.run_movetick == moves && e.run_tas_req == ticket);
	if (ok) ok = SV_RecCutOK(e, pgen, pmark);
	if (!ok)
	{
		memfree(data);
		e.run_tas_fault = 1;
		sprint(e, PRINT_HIGH, "tas: warm restore contract failed; remains paused, replay NOT armed\n");
		return;
	}
	// No native stage survives restore: create/fill/arm only now, in this VM command.
	tx = tas_tape(e, 3, count, 0, '0 0 0', '0 0 0', 0);
	ok = tx > 0;
	for (i = 0; i < count; i = i + 1)
	{
		if (!ok) break;
		b = i * TAS_INPUT_STRIDE;
		move = [data[b], data[b+1], data[b+2]];
		angle = [data[b+3], data[b+4], data[b+5]];
		ok = tas_tape(e, 4, tx, i, move, angle, data[b+6]);
	}
	memfree(data);
	if (ok) ok = tas_tape(e, 5, tx, 0, '0 0 0', '0 0 0', 0);
	if (!ok)
	{
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
		e.run_tas_fault = 1;
		sprint(e, PRINT_HIGH, "tas: replay staging/arm failed; remains paused\n");
		return;
	}
	e.run_tas_replayreq = ticket; e.run_tas_replayhead = head;
	e.run_tas_replayfirst = first; e.run_tas_replaybase = done;
	e.run_tas_replayserial = serial;
	sprint(e, PRINT_HIGH, sprintf("tas: replay request %.0f queued %.0f ticks (%.0f..%.0f), %s %.0f..%.0f\n",
		ticket, count, first, head, FS_TASEditName(field), first, last));
};

void(entity e, float argc) SV_TASInputCommand =
{
	local float first, last, field, value, ticket, edit;

	edit = !strcmp(argv(1), "edit");
	ticket = e.run_tas_req + 1;
	if (argc >= 5)
	if (!strcmp(argv(argc-2), "req"))
	{
		if (!FS_TASNumber(argv(argc-1))) goto bad;
		ticket = fs_tas_number; argc = argc - 2;
	}
	if (!(ticket >= 1 && ticket <= 16000000 && floor(ticket) == ticket)) goto bad;
	if ((!edit && argc != 3) || (edit && argc != 5 && argc != 6)) goto bad;
	if (!FS_TASNumber(argv(2))) goto bad;
	first = fs_tas_number;
	last = first; field = value = 0;
	if (edit)
	{
		if (argc == 6)
		{
			if (!FS_TASNumber(argv(3))) goto bad;
			last = fs_tas_number;
		}
		field = FS_TASEditField(argv(argc-2));
		if (!FS_TASNumber(argv(argc-1))) goto bad;
		value = fs_tas_number;
		if (!FS_TASEditValue(field, value)) goto bad;
	}
	if (!(first >= 1 && first < 16000000 && floor(first) == first &&
	      last >= first && last < 16000000 && floor(last) == last)) goto bad;
	SV_TASRecalculate(e, first, last, field, value, ticket);
	return;
:bad
	sprint(e, PRINT_HIGH, "tas: replay first | edit first [last] forward/side/up/pitch/yaw/jump/duck/walk value; plain decimal values only\n");
};

void(entity e, float settled) SV_TASReplayFrame =
{
	local float state, good;

	state = e.run_tas_replaystate;
	if (state == TAS_TAPE_ACTIVE && (e.run_t_state != TS_RUNNING ||
	    !(e.run_t_flags & TF_RECORDING) || e.rec_rec_serial != e.run_tas_replayserial))
	{
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
		state = e.run_tas_replaystate;
	}
	if (!e.run_tas_replayreq || e.run_tas_replaynotice == e.run_tas_replayreq) return;
	if (state == TAS_TAPE_DONE)
	{
		if (!settled) return;
		good = (e.run_t_state == TS_RUNNING && (e.run_t_flags & TF_RECORDING) &&
			e.rec_rec_serial == e.run_tas_replayserial &&
			SV_TimerTicks(e) == e.run_tas_replayhead && e.run_tas_pending == 0 &&
			e.run_tas_done - e.run_tas_replaybase == e.run_tas_replaycount);
		if (good)
			sprint(e, PRINT_HIGH, sprintf("tas: replay request %.0f completed %.0f ticks to %.0f; paused\n",
				e.run_tas_replayreq, e.run_tas_replaycount, SV_TimerTicks(e)));
		else
			sprint(e, PRINT_HIGH, "tas: replay ended without its expected warm head; NOT completed\n");
	}
	else if (state == TAS_TAPE_CANCELLED || state == TAS_TAPE_FAULT)
		sprint(e, PRINT_HIGH, sprintf("tas: replay request %.0f stopped %.0f/%.0f (state %.0f); no tail completion\n",
			e.run_tas_replayreq, e.run_tas_replayat, e.run_tas_replaycount, state));
	else return;
	e.run_tas_replaynotice = e.run_tas_replayreq;
};
