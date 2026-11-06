// Full-source, exact-native-base candidate previews. Keep/Discard owns history.
.float tsol_on, tsol_state, tsol_phase, tsol_next, tsol_serial, tsol_id;
.float tsol_first, tsol_last, tsol_head, tsol_target, tsol_stop;
.float tsol_candidate, tsol_best, tsol_bestok, tsol_bestspeed, tsol_besttick;
.float tsol_feasible, tsol_bad, tsol_hit, tsol_speed, tsol_tick, tsol_baseline;
.float tsol_donebase, tsol_request, tsol_seen;
.vector tsol_normal, tsol_point, tsol_velocity;
.float tsol_distance;
.string tsol_sha, tsol_note;
float *tsol_probes[FS_MAXPLAYERS + 1];
float tsol_proben[FS_MAXPLAYERS + 1];

void(entity e) SV_TASSolveEvent =
{
	WriteByte(MSG_MULTICAST,SVC_CGAMEPACKET); WriteByte(MSG_MULTICAST,TAS_EV_SOLVE);
	WriteString(MSG_MULTICAST,e.tsol_sha); WriteLong(MSG_MULTICAST,e.tsol_serial);
	WriteLong(MSG_MULTICAST,e.tsol_id); WriteByte(MSG_MULTICAST,e.tsol_state);
	WriteByte(MSG_MULTICAST,e.tsol_candidate); WriteByte(MSG_MULTICAST,e.tsol_feasible);
	WriteByte(MSG_MULTICAST,e.tsol_bestok ? e.tsol_best+1 : 0);
	WriteFloat(MSG_MULTICAST,e.tsol_bestspeed);
	WriteLong(MSG_MULTICAST,max(0,e.run_tas_done-e.tsol_donebase));
	WriteString(MSG_MULTICAST,e.tsol_note);
	msg_entity = e; multicast(e.origin,MULTICAST_ONE_R);
};

void(entity e, string note) SV_TASSolveNote =
{
	if (e.tsol_note) strunzone(e.tsol_note);
	e.tsol_note = strzone(note);
	SV_TASSolveEvent(e);
};

float(entity e) SV_TASSolveBlocking =
{
	// Failed previews stay unkeepable, but an explicit retained Discard operation
	// must be allowed to finish and clear the preview through the normal editor.
	return (e.tsol_on || (e.tase_preview && !e.tase_operation && e.tsol_state == 3 && !strcmp(e.tsol_sha,e.tase_original)));
};

void(entity e) SV_TASSolveReset =
{
	local float notify, s;
	s = SV_TASPSlot(e);
	if (s)
	{
		if (tsol_probes[s]) memfree(tsol_probes[s]);
		tsol_probes[s] = __NULL__; tsol_proben[s] = 0;
	}
	notify = (e.tsol_state > 0 && e.run_inserver);
	if (e.tsol_sha) strunzone(e.tsol_sha);
	if (e.tsol_note) strunzone(e.tsol_note);
	e.tsol_sha = e.tsol_note = "";
	e.tsol_on = e.tsol_state = e.tsol_phase = 0;
	if (notify) SV_TASSolveEvent(e);
};

void(entity e, string reason) SV_TASSolveCancel =
{
	if (!e.tsol_on) return;
	// Abort only our checked load. Recovery stays in the existing editor preview.
	if (e.tasp_load) SV_TASPAbort(e,reason);
	e.tsol_on = FALSE; e.tsol_state = 3;
	SV_TASSolveNote(e,strcat(reason,"; original/recovery retained, not auto-kept."));
	sprint(e,PRINT_HIGH,sprintf("tas solve: stopped: %s; original retained; use Discard to recover\n",reason));
};

float(entity e, float *rows, float base, float count, float first, float last, float candidate) SV_TASSolveFits =
{
	return (e.tsol_on && e.tsol_serial == e.rec_rec_serial && rows &&
		first == e.tsol_first && last == e.tsol_last && first >= base+1 &&
		last <= base+count && last-first+1 <= TAS_SOLVE_ROWS &&
		candidate >= 0 && candidate < TAS_SOLVE_CANDIDATES && candidate == floor(candidate) &&
		(candidate == e.tsol_candidate || (e.tsol_phase == 2 && candidate == e.tsol_best)));
};

void(entity e, float *rows, float base, float first, float last, float candidate) SV_TASSolvePaste =
{
	local float tick, row, oldyaw, previous, emitted, yaw, bits;
	// Delta transforms reference ORIGINAL adjacent yaw words, not compounded deltas.
	row = (first-base-1)*TAS_INPUT_STRIDE;
	previous = first > base+1 ? rows[row-TAS_INPUT_STRIDE+4] : rows[row+4];
	emitted = previous;
	for (tick = first; tick <= last; tick = tick+1)
	{
		row = (tick-base-1)*TAS_INPUT_STRIDE; oldyaw = rows[row+4];
		yaw = FS_TASSolveYaw(previous,oldyaw,emitted,candidate);
		bits = FS_TASSolveButtons(rows[row+6],candidate);
		if (yaw != oldyaw || bits != rows[row+6])
		{
			rows[row+4] = yaw; rows[row+6] = bits;
			SV_TASIInvalidate(e,tick,tick);
		}
		previous = oldyaw; emitted = yaw;
	}
};

// Called only for a settled authored contact sample, never an unexecuted row.
void(entity e, float tick, float kind, vector normal, float distance, vector point) SV_TASSolveObserve =
{
	local vector flat;
	local float s;
	if (!e.tsol_on || e.tsol_phase == 0 || e.rec_rec_serial != e.tsol_serial) return;
	if (tick < e.tsol_first || tick > e.tsol_stop || tick <= e.tsol_seen) return;
	if (tick != e.tsol_seen+1) e.tsol_bad = TRUE;
	e.tsol_seen = tick;
	if (kind >= 2) { e.tsol_bad = TRUE; return; }
	if (kind != 1) return;
	if (!e.tsol_candidate && e.tsol_phase == 1)
	{
		// The baseline learns its goal point at target, but must not discard an
		// earlier eligible sample that an unchanged later candidate could score.
		if (FS_TASSolveWindow(tick,e.tsol_target))
		{
			s = SV_TASPSlot(e);
			if (!s) { e.tsol_bad = TRUE; return; }
			if (!tsol_probes[s] || tsol_proben[s] >= TAS_SOLVE_PROBES) { e.tsol_bad = TRUE; return; }
			FS_TASSolveProbe(tsol_probes[s],tsol_proben[s],tick,normal,distance,point,e.velocity);
			tsol_proben[s] = tsol_proben[s]+1;
		}
		if (tick == e.tsol_target)
		{
			if (vlen(normal-e.tsol_normal) > .002 || fabs(distance-e.tsol_distance) > .01) return;
			e.tsol_point = point; e.tsol_velocity = e.velocity; e.tsol_baseline = TRUE;
		}
		return;
	}
	if (!e.tsol_baseline || !FS_TASSolveWindow(tick,e.tsol_target)) return;
	if (!FS_TASSolveContact(normal,distance,point,e.tsol_normal,e.tsol_distance,e.tsol_point,e.velocity,e.tsol_velocity)) return;
	flat = e.velocity; flat_z = 0;
	if (!e.tsol_hit)
	{
		e.tsol_hit = TRUE; e.tsol_speed = vlen(flat); e.tsol_tick = tick;
	}
};

void(entity e) SV_TASSolveStartRun =
{
	local float request, candidate;
	local string path, stop;
	request = e.run_tas_req;
	candidate = e.tsol_phase == 2 ? e.tsol_best : e.tsol_candidate;
	e.tsol_hit = e.tsol_bad = e.tsol_speed = e.tsol_tick = 0;
	e.tsol_seen = e.tsol_first-1;
	path = strzone(SV_TASPRevPath(e.tsol_sha,"tasp"));
	stop = strzone(sprintf("@%.0f",e.tsol_phase == 2 ? e.tsol_head : e.tsol_stop));
	tpr_pathover = path;
	SV_TASProjectLoadChecked(e,e.tase_name,stop,e.tsol_sha,e.tsol_first,e.tsol_last,TAS_SOLVE_FIELD,candidate);
	tpr_pathover = ""; strunzone(stop); strunzone(path);
	if (e.run_tas_req != request+1 || !e.tasp_load)
	{
		SV_TASSolveCancel(e,"Exact-source/native load refused"); return;
	}
	e.tsol_request = e.run_tas_req;
	SV_TASSolveNote(e,e.tsol_phase == 2 ? "Replaying best found through the full retained future; Keep still locked." :
		sprintf("Testing candidate %.0f/%.0f against the selected face/arrival region.",e.tsol_candidate+1,TAS_SOLVE_CANDIDATES));
};

void(entity e) SV_TASSolveFrame =
{
	local float feasible, s;
	local vector score;
	if (!e.tsol_on) return;
	if (e.rec_rec_serial != e.tsol_serial || !e.run_tas_paused || !e.tase_preview ||
		e.run_t_state != TS_RUNNING || !(e.run_t_flags & TF_RECORDING))
	{
		SV_TASSolveCancel(e,"Recording/control context changed"); return;
	}
	if (e.run_tas_done-e.tsol_donebase > TAS_SOLVE_BUDGET)
	{
		SV_TASSolveCancel(e,"Native authored-work budget exhausted"); return;
	}
	if (e.tsol_phase == 0)
	{
		if (time < e.tsol_next) return;
		e.tsol_phase = 1; SV_TASSolveStartRun(e); return;
	}
	if (e.tasp_load || e.run_tas_replaystate == TAS_TAPE_ACTIVE) return;
	if (e.run_tas_req != e.tsol_request || e.tasp_result == 3 ||
		SV_TimerTicks(e) != (e.tsol_phase == 2 ? e.tsol_head : e.tsol_stop))
	{
		SV_TASSolveCancel(e,"Candidate replay did not complete"); return;
	}
	if (!e.tsol_candidate && e.tsol_phase == 1 && e.tsol_baseline)
	{
		s = SV_TASPSlot(e); score = '0 0 0';
		if (s) score = FS_TASSolveBaseline(tsol_probes[s],tsol_proben[s],e.tsol_target,e.tsol_normal,e.tsol_distance,e.tsol_point,e.tsol_velocity);
		e.tsol_hit = score_z; e.tsol_speed = score_x; e.tsol_tick = score_y;
	}
	feasible = (e.tsol_baseline && e.tsol_hit && !e.tsol_bad && e.tsol_seen == e.tsol_stop);
	if (e.tsol_phase == 2)
	{
		if (!feasible) { SV_TASSolveCancel(e,"Best found failed full-future goal replay"); return; }
		e.tsol_on = FALSE; e.tsol_state = 2;
		e.tase_previewrequest = e.run_tas_req;
		SV_TASEditorFrame(e);
		SV_TASSolveNote(e,e.tsol_best ? "Best FOUND full-line preview ready. Keep commits; Discard restores the complete original." :
			"Unchanged baseline is best FOUND; no improvement claimed. Discard finishes without a new input revision.");
		sprint(e,PRINT_HIGH,sprintf("tas solve: best FOUND candidate %.0f, feasible %.0f/%.0f, speed %.6f arrival %.0f; full future retained; Keep or Discard\n",
			e.tsol_best,e.tsol_feasible,TAS_SOLVE_CANDIDATES,e.tsol_bestspeed,e.tsol_besttick));
		SV_TASProjectEvent(e); return;
	}
	if (!e.tsol_candidate && !feasible)
	{
		SV_TASSolveCancel(e,"Unchanged baseline did not reproduce a supported target arrival"); return;
	}
	if (feasible) e.tsol_feasible = e.tsol_feasible+1;
	if (FS_TASSolveBetter(feasible,e.tsol_speed,e.tsol_tick,e.tsol_bestok,e.tsol_bestspeed,e.tsol_besttick))
	{
		e.tsol_best = e.tsol_candidate; e.tsol_bestok = TRUE;
		e.tsol_bestspeed = e.tsol_speed; e.tsol_besttick = e.tsol_tick;
	}
	e.tsol_candidate = e.tsol_candidate+1;
	if (e.tsol_candidate >= TAS_SOLVE_CANDIDATES)
	{
		if (!e.tsol_bestok) { SV_TASSolveCancel(e,"No feasible candidate found"); return; }
		e.tsol_phase = 2; SV_TASSolveStartRun(e); return;
	}
	e.tsol_phase = 0; e.tsol_next = time+.35;
	SV_TASSolveEvent(e);
};

void(entity e, float argc) SV_TASSolveCommand =
{
	local float first, last, goal, serial, body, request, s, row, target, stop, budget, elapsed;
	local vector normal;
	local float distance;
	local string hash, frozen, name;
	local float *probes;
	probes = __NULL__;
	if (argc != 9) goto bad;
	if (!FS_TASNumber(argv(2))) goto bad; first = fs_tas_number;
	if (!FS_TASNumber(argv(3))) goto bad; last = fs_tas_number;
	if (!FS_TASNumber(argv(4))) goto bad; goal = fs_tas_number;
	hash = strzone(argv(5));
	if (!FS_TASNumber(argv(6))) goto done; serial = fs_tas_number;
	if (!FS_TASNumber(argv(7))) goto done; body = fs_tas_number;
	if (!FS_TASNumber(argv(8))) goto done; request = fs_tas_number;
	if (first != floor(first) || last != floor(last) || goal != floor(goal) || goal < 1 ||
		last < first || first < 1 || last-first+1 > TAS_SOLVE_ROWS || e.tsol_on || e.tsol_id >= 16000000) goto done;
	if (!SV_TASPLocalOnly(e) || !SV_TASEditorBound(e,serial,body,request)) goto done;
	if (!SV_TASEditorRows(e) || e.tase_operation || e.tase_preview) goto done;
	s = SV_TASPSlot(e);
	if (!s || e.tasp_legal || strcmp(hash,tasp_revsha[s])) goto done;
	if (!SV_TASContactSpansBind(e) || goal > e.tasc_boundrows) goto done;
	row = (goal-1)*TASC_SPAN_STRIDE;
	if (tasc_bound[s][row+2] != 1) goto done;
	target = tasc_bound[s][row]+1;
	if (first < e.tasp_base+1 || last > target-1 || last > e.tasp_base+e.tasp_n) goto done;
	stop = min(e.tasp_base+e.tasp_n,target+TAS_SOLVE_SLACK);
	budget = TAS_SOLVE_CANDIDATES*(stop-e.tasp_base)+e.tasp_n;
	if (budget > TAS_SOLVE_BUDGET || e.run_tas_done+budget > 15990000 ||
		e.run_movetick+budget > 15990000 || e.run_tas_req > 15999980) goto done;
	if (time < e.tase_next) goto done;
	if (e.run_tas_contactinfo_x != 1) goto done;
	normal = [tasc_bound[s][row+3],tasc_bound[s][row+4],tasc_bound[s][row+5]];
	distance = tasc_bound[s][row+6];
	probes = memalloc(TAS_SOLVE_PROBES*TAS_SOLVE_PROBE_STRIDE*sizeof(float));
	if (!probes) goto done;
	if (!SV_TASEditorFreeze(e)) goto done;
	// Freeze validates/retains the whole source; Preview owns the recovery strings.
	// Seed them exactly like the ordinary editor, before any load can replace them.
	frozen = strzone(tasp_revsha[s]); name = strzone(tasp_name[s]); elapsed = SV_TimerElapsed(e);
	SV_TASEditorClearPreview(e);
	tsol_probes[s] = probes; probes = __NULL__; tsol_proben[s] = 0;
	e.tase_original = frozen; e.tase_name = name; e.tase_originaltime = elapsed;
	e.tsol_sha = strzone(frozen); e.tsol_serial = e.rec_rec_serial;
	e.tsol_id = e.tsol_id+1; // never reused on reset/cancel of an unexecuted search
	e.tsol_first = first; e.tsol_last = last; e.tsol_head = e.tasp_base+e.tasp_n;
	e.tsol_target = target; e.tsol_stop = stop;
	e.tsol_normal = normal; e.tsol_distance = distance;
	e.tsol_candidate = e.tsol_best = e.tsol_bestok = e.tsol_feasible = e.tsol_baseline = 0;
	e.tsol_bestspeed = e.tsol_besttick = 0; e.tsol_donebase = e.run_tas_done;
	e.tsol_on = TRUE; e.tsol_state = 1; e.tsol_phase = 0; e.tsol_next = time;
	e.tase_preview = 1; e.tase_complete = 0; e.tase_serial = e.rec_rec_serial;
	e.tase_next = time+.35;
	SV_TASSolveNote(e,"Testing unchanged baseline first; no best-found or input change is claimed yet.");
	sprint(e,PRINT_HIGH,sprintf("tas solve: interval %.0f..%.0f target face %.0f arrival %.0f; %.0f candidates, planned native work %.0f; original retained\n",
		first,last,goal,target,TAS_SOLVE_CANDIDATES,budget));
	strunzone(hash); return;
:done
	if (probes) memfree(probes);
	strunzone(hash);
:bad
	sprint(e,PRINT_HIGH,"tas solve: refused: select 1..1024 earlier inputs and a current later observed world face; source/body, native budget and settled preview must match; nothing queued\n");
};
