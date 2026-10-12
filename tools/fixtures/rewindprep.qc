// Dedicated test-only overlay. Never compile into install/fleet progs.
#undef SV_ParseClientCommand
float rpt_checks, rpt_failed;

void(float ok, string name) RPT_Check =
{
	rpt_checks += 1;
	if (!ok)
	{
		rpt_failed += 1;
		bprint(2, strcat("REWINDPREP FAIL ", name, "\n"));
	}
};

void(moveprep_t *d, string name) RPT_Invalid =
{
	RPT_Check(d->version == 0 && d->kind == 0 && d->subject == world
		&& !strcmp(d->map, "") && !strcmp(d->owner, "") && d->ring_serial == 0
		&& d->ring_base == 0 && d->origin == '0 0 0' && d->release_velocity == '0 0 0'
		&& d->source_preserve == 0i, name);
};

void(entity e) RPT_Run =
{
	local moveprep_t *d;
	local entity snap;
	local float *original;
	local float *m;
	local int *bits;
	local float slot, i, b, actualbase, actualn, actualhead, actuallast, tick, savedtick;
	local float blk, scan, slotscan, ns, stamp, oldtick;
	local string root, owner;
	local vector org, vel, ang, near;

	rpt_checks = rpt_failed = 0;
	slot = num_for_edict(e); blk = SL_Blk(e);
	RPT_Check(e.run_inserver && e.run_t_state == TS_RUNNING && (e.run_t_flags & TF_RECORDING)
		&& e.rec_rec_lines > 0 && e.rw_n >= 3 && rw_slot[slot], "real walked recording and warm ring actor");
	if (!(e.run_t_flags & TF_RECORDING) || e.rw_n < 3 || !rw_slot[slot])
	{
		bprint(2, "REWINDPREP SETUP FAILED\n"); return;
	}
	RPT_Check(rec_sl_nb[blk] == 0 && SL_Fresh(e, blk), "fresh empty isolated save block actor");
	MP_TestOriginalCommand(sprintf("rec_watch 1 rw 7 %d %d %d", e.run_t_state, SV_TimerTicks(e), e.rec_sl_slseq));
	RPT_Check(e.rw_pin && e.rec_wt_hold && e.rec_wt_pin == 7 && e.movetype == MOVETYPE_NONE,
		"production dispatcher pin actor");
	d = SV_MovePrepAlloc(); snap = spawn(); copyentity(e, snap); snap.classname = "rewindprep-snapshot";
	original = rw_slot[slot]; actualn = e.rw_n; actualhead = e.rw_head; actuallast = e.rw_last;
	actualbase = ((e.rw_head - 1 + RW_CAP) % RW_CAP) * RW_STRIDE;
	tick = original[actualbase];
	root = strzone(sl_root); scan = rec_sl_scanlob[blk]; ns = rec_sl_ns[blk]; stamp = rec_sl_usedstamp;
	m = memalloc(sizeof(float) * RW_CAP * RW_STRIDE);
	memfill8(m, 0i, sizeof(float) * RW_CAP * RW_STRIDE);
	rw_slot[slot] = m;
	e.rw_n = 3; e.rw_head = 3; e.rw_last = 120;
	run_t_tick = 0.015;
	for (i = 0; i < 3; i += 1)
	{
		b = i * RW_STRIDE;
		m[b] = 80 + i * 20; m[b+1] = i * 100; m[b+2] = 22; m[b+3] = 333;
		m[b+4] = 123.45678; m[b+5] = -234.56789; m[b+6] = 0.00016;
		m[b+7] = -12.34567; m[b+8] = 87.65432; m[b+9] = 1;
		SV_RewindStateSample(e, b);
	}
	rw_statebase = 987; rw_t = 765; rw_o = '1 2 3'; rw_v = '4 5 6'; rw_pit = 44; rw_yaw = 55; rw_dk = 2;
	RPT_Check(SV_RewindSelectRead(e, 110, '0 0 0', FALSE) == RW_STRIDE, "latest past not closest future");
	RPT_Check(SV_RewindSelectRead(e, 120, '0 0 0', FALSE) == 2 * RW_STRIDE, "exact no near selection");
	RPT_Check(SV_RewindSelectRead(e, 50, '0 0 0', FALSE) == -1, "before first sample missing");
	RPT_Check(SV_RewindSelectRead(e, 154, '0 0 0', FALSE) == -1, "past window missing not clamped");
	near = '0 22 333';
	RPT_Check(SV_RewindSelectRead(e, 110, near, TRUE) == 0, "spatial window winner beats nearer tick");
	m[RW_STRIDE+1] = 0;
	RPT_Check(SV_RewindSelectRead(e, 110, near, TRUE) == RW_STRIDE, "equal space chooses nearest tick");
	m[2*RW_STRIDE+1] = 0;
	RPT_Check(SV_RewindSelectRead(e, 110, near, TRUE) == 2 * RW_STRIDE, "equal space tick tie newest");
	m[RW_STRIDE+1] = 100; m[2*RW_STRIDE+1] = 200;
	RPT_Check(rw_statebase == 987 && rw_t == 765 && rw_o == '1 2 3' && rw_v == '4 5 6'
		&& rw_pit == 44 && rw_yaw == 55 && rw_dk == 2, "read selector no publication");
	run_t_tick = 0;
	RPT_Check(SV_RewindSelectRead(e, 153, '0 0 0', FALSE) == 2 * RW_STRIDE
		&& SV_RewindSelectRead(e, 154, '0 0 0', FALSE) == -1, "legacy fallback 33 tick window");
	run_t_tick = 0.015;
	RPT_Check(SV_MovePrepRewind(e, 110, near, TRUE, TRUE, d) == MP_READY && d->kind == MP_REWIND
		&& d->version == 1 && d->subject == e && d->ring_base == 0 && d->ring_serial == e.rec_rec_serial
		&& d->ticks == 80 && d->id == 0 && d->seq == 0 && d->block == blk, "warm descriptor identity actor no reservation");
	RPT_Check(d->origin == '0 22 333' && d->angles == '-12.3457 87.6543 0'
		&& d->release_velocity == '123.4568 -234.5679 0.0002', "four decimal body normalization");
	RPT_Check(d->velocity == '0 0 0' && d->held && d->mode == MOVETYPE_NONE
		&& d->mode_policy == MP_SET && d->forceduck == FD_DUCK && d->forceduck_policy == MP_SET,
		"held velocity mode duck policies");
	RPT_Check(d->origin_policy == MP_SET && d->angle_policy == MP_SET && d->velocity_policy == MP_SET
		&& d->ground_policy == MP_CLEAR && d->carrier_policy == MP_CLEAR, "rewind placement policies");
	RPT_Check(d->source_clear == 6i && d->source_replace == 8i && d->source_preserve == MP_SRC_ALL - 14i
		&& d->gravity_policy == MP_KEEP && d->jump_policy == MP_KEEP, "complete Source carried policies");
	RPT_Check(e.origin == snap.origin && e.velocity == snap.velocity && e.angles == snap.angles
		&& e.v_angle == snap.v_angle && e.movetype == snap.movetype && e.flags == snap.flags
		&& e.groundentity == snap.groundentity && e.run_forceduck == snap.run_forceduck
		&& e.run_basevel == snap.run_basevel && e.run_basevel_armed == snap.run_basevel_armed, "no body mutation");
	RPT_Check(e.run_t_ticks == snap.run_t_ticks && e.run_t_state == snap.run_t_state && e.run_t_flags == snap.run_t_flags
		&& e.run_movetick == snap.run_movetick && e.rec_rec_lines == snap.rec_rec_lines && e.rec_rec_serial == snap.rec_rec_serial
		&& e.rec_rec_gen == snap.rec_rec_gen && e.rec_rec_fh == snap.rec_rec_fh && e.rec_rec_buf == snap.rec_rec_buf
		&& e.rw_pin == snap.rw_pin && e.rec_wt_hold == snap.rec_wt_hold && e.rec_sl_hold == snap.rec_sl_hold,
		"no timer recorder attachment pin mutation");
	RPT_Check(rec_sl_nb[blk] == 0 && rec_sl_ns[blk] == ns && rec_sl_usedstamp == stamp
		&& rec_sl_scanlob[blk] == scan && !strcmp(sl_root, root) && e.rec_sl_index == snap.rec_sl_index
		&& e.rw_head == 3 && e.rw_n == 3 && e.rw_last == 120 && rw_slot[slot] == m
		&& m[0] == 80 && m[RW_STRIDE] == 100 && m[2*RW_STRIDE] == 120
		&& m[4] == 123.45678 && m[33] == e.rec_rec_serial && m[29] == e.rec_rec_lines
		&& rw_statebase == 987 && rw_t == 765 && rw_o == '1 2 3', "no ring list cursor root stamp publication mutation");
	RPT_Check(SV_RewindFind(e, 110, near, TRUE) && rw_statebase == 0 && rw_t == 80
		&& rw_o == d->origin && rw_v == '123.45678 -234.56789 0.00016', "live Find publication parity actor");
	// Corrupted bounds must not be read; cold pointer must never be allocated.
	e.rw_n = RW_CAP + 1;
	RPT_Check(SV_RewindSelectRead(e, 100, near, TRUE) == -2 && SV_MovePrepRewind(e, 100, near, TRUE, TRUE, d) == MP_STALE, "oversized count bounded");
	RPT_Invalid(d, "bad count invalidates READY");
	e.rw_n = -1;
	RPT_Check(SV_RewindSelectRead(e, 100, near, TRUE) == -2, "negative count bounded");
	e.rw_n = 2.5;
	RPT_Check(SV_RewindSelectRead(e, 100, near, TRUE) == -2, "fractional count bounded");
	e.rw_n = 3; e.rw_head = RW_CAP;
	RPT_Check(SV_RewindSelectRead(e, 100, near, TRUE) == -2, "upper head bounded");
	e.rw_head = -1;
	RPT_Check(SV_RewindSelectRead(e, 100, near, TRUE) == -2, "negative head bounded");
	e.rw_head = 1.5;
	RPT_Check(SV_RewindSelectRead(e, 100, near, TRUE) == -2, "fractional head bounded");
	e.rw_head = 3; savedtick = m[0]; m[0] = 0.5;
	RPT_Check(SV_RewindSelectRead(e, 100, near, TRUE) == -2, "fractional stored tick bounded"); m[0] = savedtick;
	rw_slot[slot] = (float *)0i; e.rw_n = 0;
	RPT_Check(SV_RewindSelectRead(e, 100, near, TRUE) == -1 && SV_MovePrepRewind(e, 100, near, TRUE, TRUE, d) == MP_MISSING
		&& !rw_slot[slot] && e.rw_n == 0 && e.rw_head == 3, "cold ring missing no allocation");
	RPT_Invalid(d, "cold clears identity");
	e.rw_n = 3;
	RPT_Check(SV_RewindSelectRead(e, 100, near, TRUE) == -1 && !rw_slot[slot], "nonempty missing pointer no allocation");
	rw_slot[slot] = m;
	// Wrap at both ends, including the complete cap. The ring search stays bounded.
	memcpy(m + (RW_CAP - 1) * RW_STRIDE, m, sizeof(float) * RW_STRIDE);
	memcpy(m, m + 2 * RW_STRIDE, sizeof(float) * RW_STRIDE);
	m[(RW_CAP-1)*RW_STRIDE] = 100; e.rw_n = 2; e.rw_head = 1;
	RPT_Check(SV_RewindSelectRead(e, 110, near, TRUE) == (RW_CAP-1)*RW_STRIDE, "wrapped physical row selection");
	RPT_Check(SV_MovePrepRewind(e, 110, near, TRUE, TRUE, d) == MP_READY && d->ring_base == (RW_CAP-1)*RW_STRIDE, "wrapped descriptor identity");
	for (i = 0; i < RW_CAP; i += 1) m[i*RW_STRIDE] = i * 2;
	e.rw_n = RW_CAP; e.rw_head = 0;
	RPT_Check(SV_RewindSelectRead(e, 7998, '0 0 0', FALSE) == (RW_CAP-1)*RW_STRIDE, "complete cap search actor");
	RPT_Check(SV_RewindSelectRead(e, 0, '0 0 0', FALSE) == 0, "complete cap oldest actor");
	// Restore live source before policy/refusal probes and the real go funnel.
	rw_slot[slot] = original; e.rw_n = actualn; e.rw_head = actualhead; e.rw_last = actuallast;
	memfree(m); m = original; b = actualbase; near = [m[b+1], m[b+2], m[b+3]];
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_READY
		&& !strcmp(d->map, mapname) && !strcmp(d->owner, infokey(e, "guid")), "actual captured warm descriptor identity actor");
	// Attribution is read without a scan or publishing the private owner value.
	owner = rec_sl_owner[slot]; slotscan = rec_sl_scanlob[slot]; cvar_set("lobby_enable", "1");
	rec_sl_scanlob[slot] = 1; rec_sl_owner[slot] = "p682-not-the-owner";
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE
		&& !strcmp(rec_sl_owner[slot], "p682-not-the-owner"), "attributed block mismatch no rescan");
	rec_sl_owner[slot] = owner; rec_sl_scanlob[slot] = slotscan; cvar_set("lobby_enable", "0");
	rec_sl_nb[blk] = 1; rec_sl_id[SL_Base(blk)] = 0;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE, "malformed existing row id stale");
	rec_sl_id[SL_Base(blk)] = 1; rec_sl_seq[SL_Base(blk)] = -1;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE, "malformed existing row seq stale");
	rec_sl_seq[SL_Base(blk)] = 0;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_READY && d->id == 0 && d->seq == 0,
		"valid nonempty list no reservation"); rec_sl_nb[blk] = 0;
	// IEEE NaN/infinity must be refused, not turn off ordered validation.
	bits = (int *)m; oldtick = m[b+4]; bits[b+4] = 0x7fc00000i;
	RPT_Check(SV_MovePrepRewind(e, m[b+4], near, TRUE, TRUE, d) == MP_REFUSED
		&& SV_RewindSelectRead(e, m[b+4], near, TRUE) == -2, "NaN request domain");
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED, "NaN selected velocity");
	bits[b+4] = 0x7f800000i;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED, "infinite selected velocity");
	m[b+4] = oldtick;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, FALSE, d) == MP_UNSUPPORTED, "pure save has no movement claim"); RPT_Invalid(d, "unsupported invalidates READY");
	RPT_Check(SV_MovePrepRewind(e, -1, near, TRUE, TRUE, d) == MP_REFUSED, "negative request refused");
	RPT_Check(SV_MovePrepRewind(e, tick + 0.5, near, TRUE, TRUE, d) == MP_REFUSED, "fractional request refused");
	RPT_Check(SV_MovePrepRewind(e, 16777216, near, TRUE, TRUE, d) == MP_REFUSED, "inexact request refused");
	RPT_Check(SV_MovePrepRewind(e, tick, near, 2, TRUE, d) == MP_REFUSED, "near flag domain");
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, 2, d) == MP_REFUSED, "go flag domain");
	RPT_Check(SV_MovePrepRewind(e, tick, '70000 0 0', TRUE, TRUE, d) == MP_REFUSED, "unsafe near domain");
	RPT_Check(SV_MovePrepRewind(e, 100, '70000 0 0', FALSE, TRUE, d) != MP_REFUSED, "unused near does not gate");
	e.run_inserver = FALSE; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED, "unspawned slot refused"); e.run_inserver = TRUE;
	e.rw_pin = 0; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED, "unowned pin refused"); e.rw_pin = 1;
	e.rec_wt_hold = 0; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED, "released watch refused"); e.rec_wt_hold = 1;
	e.rec_wt_pin = -7; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED, "terminal pin refused");
	e.rec_wt_pin = 7.5; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED, "fractional pin refused"); e.rec_wt_pin = 7;
	e.rec_sl_tok = 0; e.rec_sl_tokt = time;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED
		&& e.rec_sl_tok == 0 && e.rec_sl_tokt == time, "rate refusal without bucket mutation");
	// Two same-time acting refusals expose the general + go double charge.
	e.rec_sl_tok = 2; SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d);
	e.rec_sl_tok = 1;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED
		&& e.rec_sl_tok == 1 && e.rec_sl_tokt == time, "one token pre-dispatch go refused without charge");
	RPT_Invalid(d, "one token clears READY");
	MP_TestOriginalCommand(sprintf("sl_saveat %d %.4f %.4f %.4f go", tick, near_x, near_y, near_z));
	RPT_Check(e.rec_sl_tok == 0 && rec_sl_nb[blk] == 0 && rec_sl_ns[blk] == ns && e.rw_pin
		&& e.rec_wt_hold && !e.rec_sl_hold && e.origin == snap.origin
		&& e.rec_rec_serial == snap.rec_rec_serial && e.rec_rec_gen == snap.rec_rec_gen,
		"one token authoritative go refusal actor");
	e.rec_sl_tok = 2; SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d);
	e.rec_sl_tok = 1.99999988; e.rec_sl_tokt = time;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED
		&& e.rec_sl_tok < 2 && e.rec_sl_tok > 1 && e.rec_sl_tokt == time,
		"just below two tokens go refused without charge");
	RPT_Invalid(d, "below two tokens clears READY");
	MP_TestOriginalCommand(sprintf("sl_saveat %d %.4f %.4f %.4f go", tick, near_x, near_y, near_z));
	RPT_Check(e.rec_sl_tok < 1 && e.rec_sl_tok > 0 && rec_sl_nb[blk] == 0 && rec_sl_ns[blk] == ns
		&& e.rw_pin && e.rec_wt_hold && !e.rec_sl_hold && e.origin == snap.origin
		&& e.rec_rec_serial == snap.rec_rec_serial && e.rec_rec_gen == snap.rec_rec_gen,
		"below two tokens authoritative go refusal actor");
	e.rec_sl_tok = snap.rec_sl_tok; e.rec_sl_tokt = snap.rec_sl_tokt;
	e.rec_wt_holdmove = MOVETYPE_NOCLIP; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "non walk release unsupported"); e.rec_wt_holdmove = 0;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_READY, "zero stored mode means walk"); e.rec_wt_holdmove = snap.rec_wt_holdmove;
	e.movetype = MOVETYPE_NOCLIP; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "pin mode mismatch unsupported"); e.movetype = MOVETYPE_NONE;
	e.rec_sl_hold = 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED, "save hold conflict"); e.rec_sl_hold = 0;
	e.run_pmhold = 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "spectate hold conflict"); e.run_pmhold = 0;
	e.run_sp_phase = 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "spectate transition conflict"); e.run_sp_phase = 0;
	e.run_ms_phase = 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "resume transition conflict"); e.run_ms_phase = 0;
	e.rec_gh_on = 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "ghost conflict"); e.rec_gh_on = 0;
	e.rw_goid = 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "previous go replacement abstains"); e.rw_goid = 0;
	e.rw_goseq = 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "orphan go seq abstains"); e.rw_goseq = 0;
	rec_sl_scanlob[blk] = 0; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE && rec_sl_scanlob[blk] == 0, "unscanned block no scan"); rec_sl_scanlob[blk] = scan;
	e.rec_sl_delall = 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED && e.rec_sl_delall == 1, "active sweep no cancellation"); e.rec_sl_delall = 0;
	rec_sl_nb[blk] = SL_Cap(blk); RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED && rec_sl_nb[blk] == SL_Cap(blk), "full block no delete reuse");
	rec_sl_nb[blk] = SL_Cap(blk)+1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE, "oversized save count");
	rec_sl_nb[blk] = 0.5; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE, "fractional save count"); rec_sl_nb[blk] = 0;
	rec_sl_ns[blk] = 16777215; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE, "sequence increment must remain exact"); rec_sl_ns[blk] = ns;
	e.rec_rec_serial += 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE, "old attachment abstains"); e.rec_rec_serial = snap.rec_rec_serial;
	e.rec_rec_gen += 1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE, "forked prefix abstains no chain walk"); e.rec_rec_gen = snap.rec_rec_gen;
	e.run_t_state = TS_IDLE; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "old completed run abstains"); e.run_t_state = TS_RUNNING;
	e.run_t_flags = e.run_t_flags - (e.run_t_flags & TF_RECORDING); RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_UNSUPPORTED, "ended recorder abstains"); e.run_t_flags = snap.run_t_flags;
	oldtick = m[b+29]; m[b+29] = e.rec_rec_lines+1; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_STALE, "future prefix mark stale"); m[b+29] = oldtick;
	oldtick = m[b+9]; m[b+9] = 2; RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_REFUSED, "invalid completed duck"); m[b+9] = oldtick;
	oldtick = m[b+1]; m[b+1] = 70000; RPT_Check(SV_MovePrepRewind(e, tick, '0 0 0', FALSE, TRUE, d) == MP_REFUSED, "unsafe selected body"); m[b+1] = oldtick;
	RPT_Check(SV_MovePrepRewind(world, tick, near, TRUE, TRUE, d) == MP_REFUSED, "world refused"); RPT_Invalid(d, "world clears payload");
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, (moveprep_t *)0i) == MP_REFUSED, "null output refused");
	// Actual save-write/read/load/hold dispatch, not applying a descriptor.
	e.rec_sl_tok = 2; e.rec_sl_tokt = time;
	RPT_Check(SV_MovePrepRewind(e, tick, near, TRUE, TRUE, d) == MP_READY
		&& e.rec_sl_tok == 2 && e.rec_sl_tokt == time, "exactly two tokens READY without charge before legacy go");
	org = d->origin; vel = d->release_velocity; ang = d->angles;
	MP_TestOriginalCommand(sprintf("sl_saveat %d %.4f %.4f %.4f go", tick, near_x, near_y, near_z));
	RPT_Check(e.rec_sl_tok == 0 && e.rec_sl_tokt == time, "exactly two tokens authoritative double charge actor");
	RPT_Check(FS_SlopOp(e.rec_sl_slop) == SLOP_LOADED && e.rec_sl_hold && rec_sl_nb[blk] == 1
		&& e.rw_goid > 0 && !e.rw_pin && !e.rec_wt_hold, "legacy write read load hold go actor");
	RPT_Check(e.origin == org && e.v_angle == ang && e.angles == ang && e.run_forceduck == d->forceduck
		&& !(e.flags & FL_ONGROUND) && e.run_basevel == '0 0 0' && !e.run_basevel_armed,
		"actual go normalized placement parity");
	RPT_Check(e.velocity == d->velocity && e.movetype == d->mode && e.rec_sl_holdvel == vel,
		"actual go held release velocity parity");
	RPT_Check(rec_sl_vel[SL_Base(blk)] == vel && e.rec_rec_serial == d->ring_serial
		&& e.run_t_ticks == d->ticks && e.run_t_state == TS_RUNNING && (e.run_t_flags & TF_RECORDING),
		"actual warm restore serial clock actor");
	SV_SaveLocRelease(e);
	RPT_Check(e.velocity == vel && e.movetype == MOVETYPE_WALK && !e.rec_sl_hold, "actual go release parity actor");
	SV_MovePrepFree(d); remove(snap); strunzone(root);
	bprint(2, sprintf("REWINDPREP COMPLETE checks=%g failed=%g\n", rpt_checks, rpt_failed));
};

void(string cmd) SV_ParseClientCommand =
{
	if (!strcmp(cmd, "rewindprep_test")) { RPT_Run(self); return; }
	MP_TestOriginalCommand(cmd);
};
