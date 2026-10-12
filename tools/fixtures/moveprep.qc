// Test-only owned-overlay fixture. No fixture globals/commands in normal progs.
#undef SV_ParseClientCommand
float mpt_checks, mpt_failed;

void(float ok, string name) MPT_Check =
{
	mpt_checks += 1;
	if (!ok)
	{
		mpt_failed += 1;
		bprint(2, strcat("MOVEPREP FAIL ", name, "\n"));
	}
};

void(string org, string vel, string ang, string duck, string extra) MPT_MovementFile =
{
	local filestream f;
	f = fopen(sprintf("data/saves/%s/save001/state.txt", mapname), FILE_WRITE);
	if (f < 0) { MPT_Check(FALSE, "fixture file write acted"); return; }
	fputs(f, sprintf("FTESURF-SAVE 1\nmap %s\nseq 7\nticks 0\n", mapname));
	fputs(f, sprintf("origin %s\nvelocity %s\nangles %s\nduck %s\n", org, vel, ang, duck));
	fputs(f, extra);
	fclose(f);
};

void(string extra) MPT_File =
{
	MPT_MovementFile("11 22 333", "123 234 345", "-12 87", "1", extra);
};

void(moveprep_t *d, string name) MPT_Invalid =
{
	MPT_Check(d->version == 0 && d->kind == 0 && d->subject == world
		&& !strcmp(d->map, "") && !strcmp(d->owner, "") && d->source_preserve == 0i, name);
};

void(entity e) MPT_Run =
{
	local moveprep_t *d;
	local moveprep_t *other;
	local entity snap;
	local float status, i, r, blk, base;
	local string root;
	local filestream f;

	mpt_checks = mpt_failed = 0;
	cvar_set("lobby_enable", "0");
	SV_SaveLocRelease(e);
	SV_SaveLocAlloc();
	rec_sl_nb[0] = 2; rec_sl_ns[0] = 9; rec_sl_scanlob[0] = 1;
	for (i = 0; i < 2; i += 1)
	{
		rec_sl_id[i] = i + 1; rec_sl_seq[i] = i + 7; rec_sl_tick[i] = 0;
		rec_sl_org[i] = '11 22 333'; rec_sl_vel[i] = '123 234 345';
		rec_sl_pit[i] = -12; rec_sl_yaw[i] = 87; rec_sl_duck[i] = 1;
	}
	e.rec_sl_index = 2; // deliberately NOT the requested save
	e.rec_sl_hold = 0; e.run_pmhold = 0; e.rec_wt_hold = 0; e.rec_gh_on = 0;
	e.run_ms_phase = 0; e.movetype = MOVETYPE_WALK;
	e.run_basevel = '7 8 9'; e.run_basevel_armed = 1;
	root = strzone(sl_root);
	snap = spawn(); copyentity(e, snap);
	d = SV_MovePrepAlloc(); other = SV_MovePrepAlloc();
	MPT_File("");
	status = SV_MovePrepLoad(e, 1, 7, d);
	MPT_Check(status == MP_READY && d->version == 1 && d->kind == MP_LOAD, "load READY acted");
	MPT_Check(d->origin == '11 22 333' && d->velocity == '123 234 345'
		&& d->angles == '-12 87 0' && d->forceduck == FD_DUCK, "load payload");
	MPT_Check(d->origin_policy == MP_SET && d->velocity_policy == MP_SET
		&& d->angle_policy == MP_SET && d->mode_policy == MP_KEEP
		&& d->ground_policy == MP_CLEAR && d->carrier_policy == MP_CLEAR, "load body policies");
	MPT_Check(d->source_preserve == (MP_SRC_ALL - 14i) && d->source_clear == 6i
		&& d->source_replace == 8i && d->gravity_policy == MP_KEEP && d->jump_policy == MP_KEEP, "complete Source policies");
	MPT_Check(d->subject == e && d->block == 0 && d->id == 1 && d->seq == 7
		&& !strcmp(d->map, mapname), "identity not cursor");
	MPT_Check(e.origin == snap.origin && e.velocity == snap.velocity && e.angles == snap.angles
		&& e.v_angle == snap.v_angle && e.movetype == snap.movetype && e.flags == snap.flags
		&& e.run_forceduck == snap.run_forceduck && e.run_basevel == snap.run_basevel
		&& e.run_basevel_armed == snap.run_basevel_armed, "no body mutation");
	MPT_Check(e.run_t_ticks == snap.run_t_ticks && e.run_t_state == snap.run_t_state
		&& e.run_t_flags == snap.run_t_flags && e.rec_rec_serial == snap.rec_rec_serial
		&& e.run_movetick == snap.run_movetick && e.rec_sl_index == snap.rec_sl_index
		&& e.rec_sl_hold == snap.rec_sl_hold && rec_sl_ns[0] == 9 && rec_sl_nb[0] == 2
		&& !strcmp(sl_root, root), "no timer recorder list root mutation");
	status = SV_MovePrepLoad(e, 1, 7, other);
	MPT_Check(status == MP_READY && d->velocity == other->velocity && d != other, "caller owned outputs");
	// Weak-validation control must fail HERE, proving the stale-content detector acted.
	rec_sl_vel[0] = '124 234 345';
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "velocity changed independently");
	MPT_Invalid(d, "stale invalidates previous READY");
	rec_sl_vel[0] = '123 234 345';
	rec_sl_pit[0] = -13;
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "pitch changed independently");
	rec_sl_pit[0] = -12; rec_sl_yaw[0] = 88;
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "yaw changed independently");
	rec_sl_yaw[0] = 87; rec_sl_duck[0] = 0;
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "duck changed independently");
	rec_sl_duck[0] = 1; rec_sl_org[0] = '12 22 333';
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "origin changed independently");
	rec_sl_org[0] = '11 22 333'; rec_sl_tick[0] = 1;
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "ticks changed independently");
	rec_sl_tick[0] = 0;
	MPT_Check(SV_MovePrepLoad(e, 1, 6, d) == MP_STALE, "id reuse seq stale");
	MPT_Check(SV_MovePrepLoad(e, 3, 7, d) == MP_MISSING, "missing stable id");
	MPT_Check(SV_MovePrepLoad(e, 1.5, 7, d) == MP_REFUSED, "fractional id");
	MPT_Check(SV_MovePrepLoad(e, 1, 16777216, d) == MP_REFUSED, "inexact seq unsupported");
	rec_sl_scanlob[0] = 0;
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "unscanned block no rescan");
	rec_sl_scanlob[0] = 1;
	e.run_ms_phase = 1;
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_UNSUPPORTED, "resume mode unsupported");
	e.run_ms_phase = 0;
	MPT_MovementFile("11 22 333", "124 234 345", "-12 87", "1", "");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "disk velocity changed independently");
	MPT_MovementFile("11 22 333", "123 234 345", "-13 87", "1", "");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "disk pitch changed independently");
	MPT_MovementFile("11 22 333", "123 234 345", "-12 88", "1", "");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "disk yaw changed independently");
	MPT_MovementFile("11 22 333", "123 234 345", "-12 87", "0", "");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "disk duck changed independently");
	MPT_MovementFile("12 22 333", "123 234 345", "-12 87", "1", "");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "disk origin changed independently");
	MPT_MovementFile("11 22 333", "junk 234 345", "-12 87", "1", "");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "junk velocity not zero");
	MPT_MovementFile("nan 22 333", "123 234 345", "-12 87", "1", "");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "nonfinite file origin");
	MPT_MovementFile("11 22 333", "123 234 345", "-12 87", "2", "");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "invalid duck domain");
	MPT_MovementFile("11 22 333", "123 234 345", "-12 87", "", "");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "torn missing duck");
	MPT_File("future_additive_key 1\n");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_READY, "additive unknown key");
	MPT_File(sprintf("extra %1100s\n", ""));
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "oversized line bounded");
	MPT_File("");
	f = fopen(sprintf("data/saves/%s/save001/state.txt", mapname), FILE_APPEND);
	MPT_Check(f >= 0, "line bound fixture acted");
	if (f >= 0)
	{
		for (i = 0; i < 8193; i += 1) fputs(f, "extra 0\n");
		fclose(f);
	}
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "oversized file bounded");
	MPT_File("velocity 999 0 0\n");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "duplicate movement key");
	MPT_File("seq junk\n");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "duplicate junk key");
	MPT_File("rewound 1\n");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "rewound missing rwvel");
	MPT_File("rewound 1\nrwvel 456 567 678\n"); rec_sl_vel[0] = '456 567 678';
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_READY && d->release_velocity == '456 567 678', "rewound rwvel policy");
	rec_sl_vel[0] = '123 234 345'; rec_sl_tick[0] = SL_DEMOTED;
	MPT_File("demoted 1\n");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_READY && d->ticks == SL_DEMOTED, "demoted movement only");
	rec_sl_tick[0] = 0; MPT_File("");
	// Compaction must not change identity or use the cursor's old row index.
	for (i = 0; i < 2; i += 1)
	{
		r = 1 - i; rec_sl_id[i] = r + 1; rec_sl_seq[i] = r + 7;
	}
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_READY && d->id == 1, "stable id after compaction");
	e.rec_sl_hold = 1; e.rec_sl_holdrow = 1; e.rec_sl_holdmove = MOVETYPE_WALK;
	e.movetype = MOVETYPE_NONE; e.velocity = '0 0 0';
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_READY && d->held == 1
		&& d->velocity == '0 0 0' && d->release_velocity == '123 234 345', "held load live versus release velocity");
	e.v_angle = '44 55 0'; e.angles = '44 55 0';
	MPT_Check(SV_MovePrepRelease(e, 1, 7, d) == MP_READY && d->kind == MP_RELEASE
		&& d->source_preserve == MP_SRC_ALL && d->source_clear == 0i && d->source_replace == 0i
		&& d->origin_policy == MP_KEEP && d->angle_policy == MP_KEEP && d->forceduck == 0
		&& d->ground_policy == MP_KEEP && d->carrier_policy == MP_KEEP, "release keeps aim and complete native history");
	MPT_Check(d->mode == MOVETYPE_WALK && d->mode_policy == MP_SET && d->velocity == '123 234 345', "release payload");
	e.rec_sl_holdrow = -1;
	MPT_Check(SV_MovePrepRelease(e, 1, 7, d) == MP_STALE, "release lower bound");
	e.rec_sl_holdrow = 2;
	MPT_Check(SV_MovePrepRelease(e, 1, 7, d) == MP_STALE, "release upper bound");
	e.rec_sl_holdrow = 0;
	MPT_Check(SV_MovePrepRelease(e, 1, 7, d) == MP_STALE, "release target not cursor");
	e.rec_sl_holdrow = 1; e.rec_sl_holdmove = 0;
	MPT_Check(SV_MovePrepRelease(e, 1, 7, d) == MP_READY && d->mode == MOVETYPE_WALK, "release zero mode fallback");
	e.rec_sl_holdmove = MOVETYPE_NOCLIP;
	MPT_Check(SV_MovePrepRelease(e, 1, 7, d) == MP_UNSUPPORTED, "release non-walk unsupported");
	e.rec_sl_holdmove = MOVETYPE_WALK;
	fremove(sprintf("data/saves/%s/save001/state.txt", mapname));
	MPT_Check(SV_MovePrepRelease(e, 1, 7, d) == MP_READY, "release has no new disk dependency");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, other) == MP_MISSING, "missing file load refuses");
	MPT_Invalid(other, "missing invalidates old output");
	// Actual release funnel, NOT descriptor application, checks existing parity.
	SV_MovePrepRelease(e, 1, 7, d);
	SV_SaveLocRelease(e);
	MPT_Check(e.velocity == d->velocity && e.movetype == d->mode && !e.rec_sl_hold
		&& e.v_angle == '44 55 0' && e.run_basevel == '7 8 9', "existing release parity acted");
	MPT_File("");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_READY, "fresh load before old placement");
	SV_SaveLocLoad(e, 2);
	MPT_Check(e.origin == d->origin && e.velocity == d->velocity && e.v_angle == d->angles
		&& e.run_forceduck == d->forceduck && !(e.flags & FL_ONGROUND)
		&& e.run_basevel == '0 0 0' && !e.run_basevel_armed, "existing load parity acted");
	SV_SaveLocHold(e, TRUE);
	MPT_Check(e.rec_sl_hold && e.velocity == '0 0 0' && e.movetype == MOVETYPE_NONE, "existing hold acted");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_READY && d->held, "prepare existing held load");
	SV_SaveLocLoad(e, 2);
	MPT_Check(e.velocity == d->velocity && e.rec_sl_holdvel == d->release_velocity
		&& e.rec_sl_hold && e.movetype == MOVETYPE_NONE, "existing held-load parity acted");
	SV_SaveLocRelease(e);
	MPT_Check(MP_Number("-1.25e+2") && MP_Number(".5") && !MP_Number("nan")
		&& !MP_Number("infinity") && !MP_Number("junk") && !MP_Number("1x")
		&& !MP_Number("1e") && !MP_Number("1e99"), "numeric token control");
	MPT_Check(SV_MovePrepLoad(world, 1, 7, d) == MP_REFUSED, "world refused");
	MPT_Invalid(d, "world invalidates output");
	// Attribution must ACT; infokey guid is an engine field, not settable userinfo.
	MPT_Check(strcmp(infokey(e, "guid"), "") != 0, "engine attribution present");
	cvar_set("lobby_enable", "1"); cvar_set("lobby_nosaveloc", "1");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_REFUSED, "disabled lobby saves");
	cvar_set("lobby_nosaveloc", "0");
	blk = SL_Blk(e); base = SL_Base(blk);
	rec_sl_scanlob[blk] = 2; rec_sl_nb[blk] = 1;
	if (strcmp(rec_sl_owner[blk], "")) strunzone(rec_sl_owner[blk]);
	rec_sl_owner[blk] = strzone("other-fixture-player");
	MPT_Check(SV_MovePrepLoad(e, 1, 7, d) == MP_STALE, "owner changed without rescan");
	strunzone(rec_sl_owner[blk]); rec_sl_owner[blk] = strzone(infokey(e, "guid"));
	rec_sl_id[base] = 1; rec_sl_seq[base] = 7; rec_sl_tick[base] = 0;
	rec_sl_vel[base] = '0 0 0';
	e.rec_sl_hold = 1; e.rec_sl_holdrow = base - 1; e.rec_sl_holdmove = MOVETYPE_WALK;
	MPT_Check(SV_MovePrepRelease(e, 1, 7, d) == MP_STALE, "cross-block release lower bound");
	e.rec_sl_holdrow = base;
	MPT_Check(SV_MovePrepRelease(e, 1, 7, d) == MP_READY && d->velocity == '0 0 0', "own-block zero speed release");
	e.rec_sl_hold = 0; rec_sl_nb[blk] = 0;
	strunzone(rec_sl_owner[blk]); rec_sl_owner[blk] = "";
	MPT_Check(!strcmp(infokey(snap, "guid"), "") && SV_MovePrepLoad(snap, 1, 7, d) == MP_REFUSED, "unattributed nonclient refused");
	cvar_set("lobby_enable", "0");
	SV_MovePrepFree(d); SV_MovePrepFree(other);
	remove(snap); strunzone(root);
	bprint(2, sprintf("MOVEPREP COMPLETE checks=%g failed=%g\n", mpt_checks, mpt_failed));
};

void(string cmd) SV_ParseClientCommand =
{
	if (!strcmp(cmd, "moveprep_test")) { MPT_Run(self); return; }
	MP_TestOriginalCommand(cmd);
};
