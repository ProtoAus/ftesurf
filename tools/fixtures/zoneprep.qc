// Test-only dedicated overlay. Synthetic zones never reach a normal build.
float zpt_checks, zpt_failed;

void(float ok, string name) ZPT_Check =
{
	zpt_checks += 1;
	if (!ok)
	{
		zpt_failed += 1;
		bprint(2, strcat("ZONEPREP FAIL ", name, "\n"));
	}
};

void(moveprep_t *d, string name) ZPT_Invalid =
{
	ZPT_Check(d->version == 0 && d->kind == 0 && d->subject == world
		&& !strcmp(d->map, "") && !strcmp(d->owner, "") && !strcmp(d->zone_hash, "")
		&& d->source_preserve == 0i && d->destination_source == 0, name);
};

void(entity e) ZPT_Run =
{
	local moveprep_t *d;
	local entity snap, target, obstacle;
	local vector ground, org, expected, hull;
	local float yaw, pit, haveyaw, fallback, status, i, row, blk;
	local string root, hash;

	zpt_checks = zpt_failed = 0;
	cvar_set("lobby_enable", "0"); cvar_set("run_zone_hull", "1"); cvar_set("run_zone_hull_live", "0");
	SV_SaveLocRelease(e); SV_TimerVoid(e, "zoneprep fixture");
	ground = SV_ZoneDestRead(e, 0, yaw, haveyaw, fallback);
	tracebox(ground + '0 0 8', PM_HULL_MINS, PM_HULL_MAXS, ground - '0 0 128', FALSE, e);
	ground = trace_endpos;
	tracebox(ground + '0 0 1', PM_HULL_MINS, PM_HULL_MAXS, ground + '0 0 1', FALSE, e);
	ZPT_Check(!trace_startsolid && !trace_allsolid, "real standing floor actor");
	Zone_Clear();
	for (i = 0; i < 8; i += 1)
	{
		Zone_AddBox(ground - '64 64 8', ground + '64 64 256', ZONE_START, 0);
		zone_td_kind[i] = ZTD_POS; zone_td_pos[i] = ground + '0 0 32'; zone_td_yaw[i] = i * 23;
	}
	zone_type[1] = ZONE_STAGE; zone_seg[1] = 1;
	zone_track[2] = 1;
	zone_td_kind[3] = ZTD_NONE;
	target = spawn(); target.targetname = "zoneprep-target";
	target.origin = ground + '0 0 16'; target.angles = '47 0 0';
	zone_td_kind[4] = ZTD_NAME; zone_td_name[4] = strzone("zoneprep-target");
	zone_td_kind[5] = ZTD_NAME; zone_td_name[5] = strzone("zoneprep-missing");
	zone_td_pos[6] = '50000 50000 50000';
	zone_type[7] = ZONE_END; zone_seg[7] = 2;
	zone_loaded = TRUE; Zone_Hash();
	d = SV_MovePrepAlloc();
	e.run_leg_track = 0; e.run_leg_seg = 0; e.run_leg_zone = 0;
	e.run_pmhold = 0; e.run_sp_phase = 0; e.rec_wt_hold = 0; e.rec_gh_on = 0; e.run_ms_phase = 0;
	e.rec_sl_hold = 0; e.movetype = MOVETYPE_WALK;
	e.velocity = '321 432 543'; e.v_angle = '41 42 0'; e.angles = e.v_angle;
	e.run_forceduck = FD_DUCK; e.flags = e.flags | FL_ONGROUND; e.groundentity = target;
	e.run_basevel = '7 8 9'; e.run_basevel_armed = 1;
	SV_SaveLocAlloc(); rec_sl_scanlob[0] = 1; rec_sl_nb[0] = 0;
	snap = spawn(); copyentity(e, snap); root = strzone(sl_root); hash = strzone(zone_crc);
	expected = SV_ZoneDestRead(e, 0, yaw, haveyaw, fallback);
	status = SV_MovePrepReset(e, "!m", 0, d);
	ZPT_Check(status == MP_READY && d->version == 1 && d->kind == MP_RESET
		&& d->subject == e && d->zone == 0 && !strcmp(d->zone_hash, zone_crc), "map reset READY acted");
	ZPT_Check(d->origin == expected && d->origin_policy == MP_SET && d->destination_source == MP_DEST_ZONE, "canonical ground snap not centre");
	ZPT_Check(d->velocity == '0 0 0' && d->velocity_policy == MP_SET, "reset zero velocity");
	ZPT_Check(d->angles == '0 0 0' && d->angle_policy == MP_SET, "zero yaw is an answer");
	ZPT_Check(d->carrier_policy == MP_CLEAR && d->ground_policy == MP_KEEP
		&& d->mode_policy == MP_KEEP && d->forceduck_policy == MP_KEEP, "reset carried body policies");
	ZPT_Check(d->source_preserve == MP_SRC_ALL && d->source_clear == 0i && d->source_replace == 0i
		&& d->gravity_policy == MP_KEEP && d->jump_policy == MP_KEEP, "reset complete Source history policies");
	ZPT_Check(e.origin == snap.origin && e.velocity == snap.velocity && e.v_angle == snap.v_angle
		&& e.angles == snap.angles && e.flags == snap.flags && e.groundentity == snap.groundentity
		&& e.movetype == snap.movetype && e.run_forceduck == snap.run_forceduck
		&& e.run_basevel == snap.run_basevel && e.run_basevel_armed == snap.run_basevel_armed, "no body mutation");
	ZPT_Check(e.run_t_ticks == snap.run_t_ticks && e.run_t_state == snap.run_t_state
		&& e.run_t_flags == snap.run_t_flags && e.rec_rec_serial == snap.rec_rec_serial
		&& e.run_t_wantstage1 == snap.run_t_wantstage1 && e.rec_sl_hold == snap.rec_sl_hold
		&& rec_sl_nb[0] == 0 && rec_sl_scanlob[0] == 1 && !strcmp(sl_root, root)
		&& !strcmp(zone_crc, hash) && zone_td_kind[0] == ZTD_POS, "no timer recorder scan root table mutation");
	SV_ZoneChatCommand("!m", 0);
	ZPT_Check(e.origin == d->origin && e.velocity == d->velocity && e.v_angle == d->angles
		&& e.flags == snap.flags && e.groundentity == target && e.run_forceduck == FD_DUCK
		&& e.run_basevel == '0 0 0' && !e.run_basevel_armed, "existing map reset parity acted");
	ZPT_Check(SV_MovePrepReset(e, "!s", 2, d) == MP_READY && d->zone == 1 && d->angles == '0 23 0', "stage request selection");
	SV_ZoneChatCommand("!s", 2);
	ZPT_Check(e.origin == d->origin && e.v_angle == d->angles && e.run_leg_zone == 1, "existing stage reset parity acted");
	ZPT_Check(SV_MovePrepReset(e, "!b", 1, d) == MP_READY && d->zone == 2 && d->angles == '0 46 0', "bonus request selection");
	SV_ZoneChatCommand("!b", 1);
	ZPT_Check(e.origin == d->origin && e.v_angle == d->angles && e.run_leg_zone == 2, "existing bonus reset parity acted");
	e.run_leg_zone = 3; e.run_leg_track = 0; e.run_leg_seg = 0;
	e.v_angle = '44 55 0'; e.angles = e.v_angle;
	org = zone_centre[3]; expected = [org_x, org_y, zone_bottom[3] + 2];
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_READY && d->zone == 3
		&& d->angle_policy == MP_KEEP && d->origin == expected, "latched duplicate leg and box keep aim");
	SV_ZoneChatCommand("!r", 0);
	ZPT_Check(e.origin == d->origin && e.v_angle == '44 55 0', "existing latched box parity acted");
	e.run_leg_zone = -1; e.run_leg_track = 1; e.run_leg_seg = 0;
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_READY && d->zone == 2, "invalid latch derives current leg");
	ZPT_Check(SV_MovePrepReset(e, "!s", 0, d) == MP_READY && d->zone == 0, "missing stage means stage one");
	ZPT_Check(SV_MovePrepZone(e, 4, FALSE, 0, 0, d) == MP_READY && d->angles == '0 0 0'
		&& d->angle_policy == MP_SET, "named target zero yaw ignores authored pitch");
	SV_ZoneGotoAng(4, 0, 0, FALSE);
	ZPT_Check(e.origin == d->origin && e.v_angle == d->angles, "existing named target parity acted");
	ZPT_Check(SV_MovePrepZone(e, 5, FALSE, 0, 0, d) == MP_READY && d->destination_fallback == ZDEST_MISSING
		&& d->angle_policy == MP_KEEP && zone_td_kind[5] == ZTD_NAME, "missing target read does not cache mutation");
	SV_ZoneGotoAng(5, 0, 0, FALSE);
	ZPT_Check(e.origin == d->origin && zone_td_kind[5] == ZTD_NONE, "existing missing target cache parity acted");
	ZPT_Check(SV_MovePrepZone(e, 6, FALSE, 0, 0, d) == MP_READY && d->destination_fallback == ZDEST_VOID
		&& d->origin == '50000 50000 50001', "void destination uses raw point lift");
	SV_ZoneGotoAng(6, 0, 0, FALSE);
	ZPT_Check(e.origin == d->origin && e.velocity == '0 0 0', "existing void fallback parity acted");
	ZPT_Check(SV_MovePrepZone(e, 3, TRUE, 89, -31, d) == MP_READY && d->angles == '-31 89 0'
		&& d->angle_policy == MP_SET, "explicit goto angles override box keep");
	SV_ZoneGotoAng(3, 89, -31, TRUE);
	ZPT_Check(e.origin == d->origin && e.v_angle == d->angles, "existing explicit goto parity acted");
	ZPT_Check(SV_MovePrepZone(e, 7, FALSE, 0, 0, d) == MP_READY && d->zone == 7, "goto end zone supported without timer claim");
	obstacle = spawn(); obstacle.solid = SOLID_BBOX; obstacle.movetype = MOVETYPE_NONE;
	setsize(obstacle, '-64 -64 -2048', '64 64 2048'); setorigin(obstacle, ground + '0 0 200');
	zone_td_pos[7] = obstacle.origin;
	tracebox(zone_td_pos[7], PM_HULL_MINS, PM_HULL_MAXS, zone_td_pos[7], FALSE, e);
	ZPT_Check(trace_startsolid, "solid destination actor");
	ZPT_Check(SV_MovePrepZone(e, 7, FALSE, 0, 0, d) == MP_READY && d->destination_fallback == ZDEST_SOLID
		&& d->origin == zone_td_pos[7] + '0 0 1', "solid fallback uses raw point lift");
	SV_ZoneGotoAng(7, 0, 0, FALSE);
	ZPT_Check(e.origin == d->origin, "existing solid fallback parity acted");
	remove(obstacle); zone_td_pos[7] = ground;
	// The start save contributes origin/aim ONLY, not speed or completed duck.
	rec_sl_nb[0] = 2; rec_sl_ns[0] = 9;
	for (i = 0; i < 2; i += 1)
	{
		rec_sl_id[i] = i + 1; rec_sl_seq[i] = i + 7; rec_sl_tick[i] = 0;
		rec_sl_org[i] = ground + [i * 8, 0, 24]; rec_sl_vel[i] = '123 234 345';
		rec_sl_yaw[i] = 87 + i; rec_sl_pit[i] = -12 - i; rec_sl_duck[i] = 1;
	}
	e.run_leg_zone = 0; e.run_leg_track = 0; e.run_leg_seg = 0; e.run_t_state = TS_IDLE;
	ZPT_Check(SV_SaveLocPickInZoneRead(e, 0, org, yaw, pit, row) && row == 1, "start save selector newest row acted");
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_READY && d->destination_source == MP_DEST_SAVE
		&& d->id == 2 && d->seq == 8 && d->origin == org && d->angles == [pit, yaw, 0]
		&& d->velocity == '0 0 0' && d->forceduck_policy == MP_KEEP, "save backed restart payload no prespeed");
	SV_ZoneChatCommand("!r", 0);
	ZPT_Check(e.origin == d->origin && e.velocity == d->velocity && e.v_angle == d->angles
		&& e.run_forceduck == FD_DUCK, "existing save backed restart parity acted");
	rec_sl_scanlob[0] = 0;
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_STALE && rec_sl_scanlob[0] == 0, "unscanned preference explicit stale no scan");
	ZPT_Invalid(d, "stale clears previous READY");
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_READY && d->destination_source == MP_DEST_ZONE, "map reset has no save scan dependency");
	rec_sl_scanlob[0] = 1; rec_sl_tick[1] = 3;
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_READY && d->id == 1, "timed save not a start preference");
	rec_sl_tick[1] = 0; rec_sl_pit[1] = 170;
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_READY && d->angles == '90 88 0', "start save pitch clamped");
	rec_sl_pit[1] = -13;
	// A selected row may fail only AFTER its downward snap. Zone fallback must
	// discard the row's pitch as well as its origin, not leak save aim into it.
	hull = SV_RunHullMaxs(e);
	zone_bottom[0] = ground_z + 8;
	if (run_t_hullocc) zone_bottom[0] += hull_z;
	zone_top[0] = ground_z + 200;
	ZPT_Check(!SV_SaveLocPickInZoneRead(e, 0, org, yaw, pit, row) && row == 1 && pit == -13,
		"selected save post snap refusal actor");
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_READY && d->destination_source == MP_DEST_ZONE
		&& d->angles == '0 0 0', "refused save fallback discards saved pitch");
	SV_ZoneChatCommand("!r", 0);
	ZPT_Check(e.origin == d->origin && e.v_angle == d->angles && e.v_angle == '0 0 0',
		"existing post snap fallback parity acted");
	zone_bottom[0] = ground_z - 8; zone_top[0] = ground_z + 256;
	// Native same-stage query must ACT before checking the bypass.
	e.run_leg_zone = 1; e.run_t_state = TS_RUNNING; e.run_t_track = 0;
	e.run_t_seg = 1; e.run_t_startseg = 0;
	ZPT_Check(SV_TimerWouldRestartSeg(e, 1), "ranked same stage restart query acted");
	rec_sl_scanlob[0] = 0;
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_READY && d->destination_source == MP_DEST_ZONE
		&& d->angles == '0 23 0' && e.run_t_state == TS_RUNNING, "same stage restart bypasses stale save preference");
	e.run_t_state = TS_IDLE; rec_sl_scanlob[0] = 1;
	e.rec_sl_hold = 1; e.rec_sl_holdrow = 1; e.rec_sl_holdmove = MOVETYPE_WALK; e.movetype = MOVETYPE_NONE;
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_READY && d->mode_policy == MP_SET
		&& d->mode == MOVETYPE_WALK && d->velocity == '0 0 0' && !d->held, "held reset prepares release then zero velocity");
	SV_ZoneChatCommand("!m", 0);
	ZPT_Check(!e.rec_sl_hold && e.movetype == d->mode && e.velocity == d->velocity && e.origin == d->origin, "existing held reset parity acted");
	e.movetype = MOVETYPE_NOCLIP;
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_READY && d->mode_policy == MP_KEEP, "noclip reset preserves mode");
	e.movetype = MOVETYPE_WALK; e.run_ms_phase = 1;
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_UNSUPPORTED, "resume unsupported");
	ZPT_Invalid(d, "unsupported clears prior READY");
	e.run_ms_phase = 0; e.rec_wt_hold = 1;
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_UNSUPPORTED, "watch transition unsupported");
	e.rec_wt_hold = 0; e.run_sp_phase = 1;
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_UNSUPPORTED, "spectate transition unsupported");
	e.run_sp_phase = 0; e.rec_gh_on = 1;
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_UNSUPPORTED, "ghost transition unsupported");
	e.rec_gh_on = 0; zone_loaded = FALSE;
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_STALE && !zone_loaded, "zone unavailable no deferred load");
	zone_loaded = TRUE;
	zone_td_kind[0] = 0.5;
	ZPT_Check(SV_MovePrepZone(e, 0, FALSE, 0, 0, d) == MP_UNSUPPORTED, "fractional destination kind refused");
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_UNSUPPORTED, "reset invalid destination kind refused");
	zone_td_kind[0] = ZTD_POS; zone_count = 8.5;
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, d) == MP_STALE, "invalid zone table bound stale");
	zone_count = 8; e.run_leg_zone = 0; rec_sl_nb[0] = SL_Cap(0) + 1;
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_STALE, "invalid save table bound stale");
	rec_sl_nb[0] = 2;
	ZPT_Check(SV_MovePrepReset(e, "!s", 99, d) == MP_MISSING, "missing stage");
	ZPT_Check(SV_MovePrepReset(e, "unknown", 0, d) == MP_REFUSED, "unknown reset request");
	ZPT_Check(SV_MovePrepReset(e, "!s", 1.5, d) == MP_REFUSED, "fractional stage refused");
	ZPT_Check(SV_MovePrepZone(e, -1, FALSE, 0, 0, d) == MP_MISSING, "zone lower bound");
	ZPT_Check(SV_MovePrepZone(e, zone_count, FALSE, 0, 0, d) == MP_MISSING, "zone upper bound");
	ZPT_Check(SV_MovePrepZone(e, 0.5, FALSE, 0, 0, d) == MP_MISSING, "fractional zone refused");
	ZPT_Check(SV_MovePrepZone(e, 0, 2, 0, 0, d) == MP_REFUSED, "angle override domain");
	ZPT_Check(SV_MovePrepZone(e, 0, TRUE, 10000000, 0, d) == MP_REFUSED, "bad explicit yaw");
	zone_td_pos[0] = '70000 0 0';
	ZPT_Check(SV_MovePrepZone(e, 0, FALSE, 0, 0, d) == MP_REFUSED, "unsafe resolved origin refused");
	ZPT_Invalid(d, "refused clears identity");
	zone_td_pos[0] = ground;
	ZPT_Check(SV_MovePrepReset(world, "!m", 0, d) == MP_REFUSED, "world not a subject");
	ZPT_Check(SV_MovePrepReset(e, "!m", 0, (moveprep_t *)0i) == MP_REFUSED, "null output refused");
	// A disabled lobby preference falls back exactly as the live quiet gate does.
	cvar_set("lobby_enable", "1"); cvar_set("lobby_nosaveloc", "1");
	blk = SL_Blk(e); rec_sl_scanlob[blk] = 0;
	e.run_leg_zone = 0;
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_READY && d->destination_source == MP_DEST_ZONE
		&& rec_sl_scanlob[blk] == 0, "disabled lobby saves bypass stale preference");
	cvar_set("lobby_nosaveloc", "0"); rec_sl_scanlob[blk] = 2;
	if (strcmp(rec_sl_owner[blk], "")) strunzone(rec_sl_owner[blk]);
	rec_sl_owner[blk] = strzone("other-fixture-owner"); rec_sl_nb[blk] = 0;
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_STALE, "lobby owner change no rescan");
	strunzone(rec_sl_owner[blk]); rec_sl_owner[blk] = strzone(infokey(e, "guid"));
	ZPT_Check(SV_MovePrepReset(e, "!r", 0, d) == MP_READY && d->destination_source == MP_DEST_ZONE, "fresh empty owner block ready");
	cvar_set("lobby_enable", "0");
	SV_MovePrepFree(d); remove(snap); remove(target); strunzone(root); strunzone(hash);
	bprint(2, sprintf("ZONEPREP COMPLETE checks=%g failed=%g\n", zpt_checks, zpt_failed));
};
