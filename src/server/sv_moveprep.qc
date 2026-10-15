/*
 * Inert movement POLICY descriptors, not native snapshots or permission to
 * predict. No production caller. Timer/recorder/placement remain authoritative.
 * Use Alloc/Free; output owns its identity strings. Reuse clears old output.
 * A READY answer describes this call only: no content/connection epoch or
 * persistent cache is supplied here. See tools/p678moveprep.md, p680zoneprep.md
 * and p682rewindprep.md.
 */
#define MP_READY 1
#define MP_MISSING 2
#define MP_STALE 3
#define MP_REFUSED 4
#define MP_UNSUPPORTED 5
#define MP_LOAD 1
#define MP_RELEASE 2
#define MP_ZONE 3
#define MP_RESET 4
#define MP_REWIND 5
#define MP_DEST_ZONE 1
#define MP_DEST_SAVE 2
#define MP_KEEP 0
#define MP_SET 1
#define MP_CLEAR 2

// Every field in pmsourcestate_t; tests check this table against protocol.h.
#define MP_SRC_surfacefriction 1i
#define MP_SRC_ducktime 2i
#define MP_SRC_ducking 4i
#define MP_SRC_ducked 8i
#define MP_SRC_msec_carry 16i
#define MP_SRC_oldbuttons 32i
#define MP_SRC_stamina 64i
#define MP_SRC_rampoff 128i
#define MP_SRC_boardcount 256i
#define MP_SRC_rampcontact 512i
#define MP_SRC_srcladder 1024i
#define MP_SRC_srcladdernormal 2048i
#define MP_SRC_portaloffset 4096i
#define MP_SRC_ALL 8191i

typedef struct
{
	float version, kind;
	entity subject;
	string map, owner, zone_hash;
	float block, id, seq, ticks;
	float zone, destination_source, destination_fallback;
	float ring_base, ring_serial; // call-local rewind source, NOT a reuse/connection epoch
	vector origin, velocity, angles, release_velocity;
	float origin_policy, velocity_policy, angle_policy, mode_policy;
	float ground_policy, carrier_policy, gravity_policy, jump_policy;
	float mode, forceduck, forceduck_policy, held;
	int source_preserve, source_clear, source_replace;
} moveprep_t;

void(moveprep_t *out) SV_MovePrepClear =
{
	if (!out)
		return;
	if (strcmp(out->map, "")) strunzone(out->map);
	if (strcmp(out->owner, "")) strunzone(out->owner);
	if (strcmp(out->zone_hash, "")) strunzone(out->zone_hash);
	memfill8(out, 0i, sizeof(moveprep_t));
};

moveprep_t *() SV_MovePrepAlloc =
{
	local moveprep_t *out;
	out = memalloc(sizeof(moveprep_t));
	memfill8(out, 0i, sizeof(moveprep_t));
	return out;
};

void(moveprep_t *out) SV_MovePrepFree =
{
	if (!out) return;
	SV_MovePrepClear(out);
	memfree(out);
};

// stof alone accepts junk as zero. Validate the complete bounded numeric token.
float(string s) MP_Number =
{
	local float i, n, digits;
	local string c;
	n = strlen(s);
	if (n < 1 || n > 48) return FALSE;
	i = 0;
	c = substring(s, i, 1);
	if (!strcmp(c, "+") || !strcmp(c, "-")) i += 1;
	digits = 0;
	while (i < n)
	{
		c = substring(s, i, 1);
		if (strstrofs("0123456789", c) < 0) break;
		digits += 1; i += 1;
	}
	if (!strcmp(substring(s, i, 1), "."))
	{
		i += 1;
		while (i < n)
		{
			c = substring(s, i, 1);
			if (strstrofs("0123456789", c) < 0) break;
			digits += 1; i += 1;
		}
	}
	if (!digits) return FALSE;
	c = substring(s, i, 1);
	if (!strcmp(c, "e") || !strcmp(c, "E"))
	{
		i += 1; digits = 0;
		c = substring(s, i, 1);
		if (!strcmp(c, "+") || !strcmp(c, "-")) i += 1;
		while (i < n)
		{
			c = substring(s, i, 1);
			if (strstrofs("0123456789", c) < 0) break;
			digits += 1; i += 1;
		}
		if (!digits) return FALSE;
	}
	if (i != n) return FALSE;
	return (stof(s) > -10000000 && stof(s) < 10000000);
};

float(vector v) MP_Vector =
{
	return (v_x > -10000000 && v_x < 10000000 && v_y > -10000000 && v_y < 10000000
		&& v_z > -10000000 && v_z < 10000000);
};

// No allocation, scanning, root mutation, cursor movement or messaging.
float(entity e, float id, float seq) MP_Row =
{
	local float blk, base, i, r, slot;
	if (e == world) return -MP_REFUSED;
	slot = num_for_edict(e);
	if (slot < 1 || slot > FS_SLCLIENTS || strcmp(e.classname, "player")) return -MP_REFUSED;
	if (!SV_SaveLocAllowed(e, TRUE)) return -MP_REFUSED;
	blk = SL_Blk(e);
	if (blk < 0 || blk > FS_SLCLIENTS) return -MP_REFUSED;
	if (!SL_Fresh(e, blk)) return -MP_STALE;
	if (!rec_sl_org || !rec_sl_vel || !rec_sl_pit || !rec_sl_yaw || !rec_sl_duck
		|| !rec_sl_id || !rec_sl_seq || !rec_sl_tick) return -MP_STALE;
	if (!(id >= 1 && id <= FS_MAXSAVES && id == floor(id))) return -MP_REFUSED;
	if (!(seq >= 0 && seq < 16777216 && seq == floor(seq))) return -MP_REFUSED;
	if (!(rec_sl_nb[blk] >= 0 && rec_sl_nb[blk] <= SL_Cap(blk)
		&& rec_sl_nb[blk] == floor(rec_sl_nb[blk]))) return -MP_STALE;
	base = SL_Base(blk);
	for (i = 0; i < rec_sl_nb[blk]; i += 1)
	{
		r = base + i;
		if (rec_sl_id[r] != id) continue;
		if (rec_sl_seq[r] != seq) return -MP_STALE;
		return r;
	}
	return -MP_MISSING;
};

void(entity e, float r, float kind, moveprep_t *out) MP_Identity =
{
	out->subject = e;
	out->map = strzone(mapname);
	out->owner = strzone(infokey(e, "guid"));
	out->block = SL_Blk(e);
	out->id = rec_sl_id[r]; out->seq = rec_sl_seq[r]; out->ticks = rec_sl_tick[r];
	out->kind = kind;
	out->source_preserve = MP_SRC_ALL;
	// The zero policies are explicit KEEP for all unsupported native history,
	// gravity and jump_held/jump_msec/waterjumptime, not invented restore values.
};

// Read into local scratch. Strict movement keys only; unrelated state is never
// restored here. Unknown keys remain additive. Rewound rows use rwvel, matching
// ReadLight/Place (state.txt's velocity is zero for the paused rewind body).
float(string path, float r) MP_FileMatches =
{
	local filestream f;
	local string line, key;
	local float n, lines, j, got, bit, seq, ticks, pit, yaw, duck, dem, rewound;
	local vector org, vel, rwvel;
	local float good;

	f = fopen(path, FILE_READ);
	if (f < 0) return MP_MISSING;
	got = 0; lines = 0; good = TRUE;
	seq = ticks = pit = yaw = duck = dem = rewound = 0;
	org = vel = rwvel = '0 0 0';
	while (strcmp((line = fgets(f)), ""))
	{
		lines += 1;
		if (lines > 8192 || strlen(line) > 1023) { good = FALSE; break; }
		n = tokenize(line);
		if (!n) continue;
		key = argv(0); bit = 0;
		if (!strcmp(key, "FTESURF-SAVE")) bit = 1;
		if (!strcmp(key, "map")) bit = 2;
		if (!strcmp(key, "seq")) bit = 4;
		if (!strcmp(key, "ticks")) bit = 8;
		if (!strcmp(key, "origin")) bit = 16;
		if (!strcmp(key, "velocity")) bit = 32;
		if (!strcmp(key, "angles")) bit = 64;
		if (!strcmp(key, "duck")) bit = 128;
		if (!strcmp(key, "demoted")) bit = 256;
		if (!strcmp(key, "rewound")) bit = 512;
		if (!strcmp(key, "rwvel")) bit = 1024;
		if (!bit) continue;
		if (got & bit) { good = FALSE; break; }
		got = got | bit;
		if (bit == 2)
		{
			if (n != 2 || strcmp(argv(1), mapname)) { good = FALSE; break; }
			continue;
		}
		if (bit == 16 || bit == 32 || bit == 1024) j = 4;
		else if (bit == 64) j = 3;
		else j = 2;
		if (n != j) { good = FALSE; break; }
		for (j = 1; j < n; j += 1)
			if (!MP_Number(argv(j))) good = FALSE;
		if (!good) break;
		if (bit == 1) { if (stof(argv(1)) != SL_STATE_VERSION) good = FALSE; }
		if (bit == 4) seq = stof(argv(1));
		if (bit == 8) ticks = stof(argv(1));
		if (bit == 16) org = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
		if (bit == 32) vel = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
		if (bit == 64) { pit = stof(argv(1)); yaw = stof(argv(2)); }
		if (bit == 128) duck = stof(argv(1));
		if (bit == 256) dem = TRUE; // existing reader treats presence as demotion
		if (bit == 512) rewound = stof(argv(1));
		if (bit == 1024) rwvel = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
	}
	fclose(f);
	if (!good || (got & 255) != 255) return MP_REFUSED;
	if (!SV_SaveOriginSane(org)) return MP_REFUSED;
	if (!(duck == 0 || duck == 1)) return MP_REFUSED;
	if (!(rewound == 0 || rewound == 1)) return MP_REFUSED;
	if (!(ticks >= 0 && ticks == floor(ticks))) return MP_REFUSED;
	if (rewound)
	{
		if (!(got & 1024)) return MP_REFUSED;
		vel = rwvel;
	}
	if (dem) ticks = SL_DEMOTED;
	if (seq != rec_sl_seq[r] || ticks != rec_sl_tick[r]) return MP_STALE;
	if (org != rec_sl_org[r] || vel != rec_sl_vel[r]) return MP_STALE;
	if (pit != rec_sl_pit[r] || yaw != rec_sl_yaw[r] || duck != rec_sl_duck[r]) return MP_STALE;
	return MP_READY;
};

float(entity e, float id, float seq, moveprep_t *out) SV_MovePrepLoad =
{
	local float r, status;
	local string root;
	SV_MovePrepClear(out);
	if (!out) return MP_REFUSED;
	r = MP_Row(e, id, seq);
	if (r < 0) return -r;
	// Mode transitions out of spectate/replay/ghost are not modeled in this slice.
	if (e.run_pmhold || e.rec_wt_hold || e.rec_gh_on || e.run_ms_phase
		|| SL_Sweeper(SL_Blk(e))) return MP_UNSUPPORTED;
	root = sprintf("data/saves/%s", mapname);
	if (SL_Blk(e) > 0)
		root = sprintf("data/saves/%s/@%s", mapname, SV_SaveSanitise(infokey(e, "guid")));
	status = MP_FileMatches(sprintf("%s/save%s/state.txt", root, SL_NN(id)), r);
	if (status != MP_READY) return status;
	MP_Identity(e, r, MP_LOAD, out);
	out->origin = rec_sl_org[r]; out->origin_policy = MP_SET;
	out->velocity = rec_sl_vel[r]; out->velocity_policy = MP_SET;
	out->release_velocity = rec_sl_vel[r];
	out->angles = [rec_sl_pit[r], rec_sl_yaw[r], 0]; out->angle_policy = MP_SET;
	out->forceduck = rec_sl_duck[r] ? FD_DUCK : FD_STAND;
	out->forceduck_policy = MP_SET;
	out->ground_policy = MP_CLEAR; out->carrier_policy = MP_CLEAR;
	out->source_clear = MP_SRC_ducktime | MP_SRC_ducking;
	out->source_replace = MP_SRC_ducked;
	out->source_preserve = MP_SRC_ALL - out->source_clear - out->source_replace;
	out->held = (e.rec_sl_hold != 0);
	if (out->held) out->velocity = '0 0 0';
	out->version = 1;
	return MP_READY;
};

// The row writer/read-back rounds movement to four decimals, even for a warm
// prefix. This is its numerical policy, not a replacement save-state writer.
float(float v) MP_SaveDecimal =
{
	return stof(sprintf("%.4f", v));
};

// P682: successful fresh warm `sl_saveat ... go` ends on a save-lock hold.
// Pure save, cold/forked prefix and previous-go replacement paths abstain.
// READY is BODY POLICY ONLY: no ID/sequence reservation, prefix/copy/file promise,
// prediction permission or future reuse claim. Every check is bounded/read-only.
float(entity e, float t, vector near, float usenear, float go, moveprep_t *out) SV_MovePrepRewind =
{
	local float slot, blk, b, i, r, mode;
	local float *m;
	local vector org, vel, ang;
	SV_MovePrepClear(out);
	if (!out) return MP_REFUSED;
	if (e == world) return MP_REFUSED;
	slot = num_for_edict(e);
	if (slot < 1 || slot > FS_MAXPLAYERS || slot > FS_SLCLIENTS || strcmp(e.classname, "player")) return MP_REFUSED;
	if (!e.run_inserver) return MP_REFUSED;
	if (!(t >= 0 && t < 16777216 && t == floor(t))) return MP_REFUSED;
	if (!(usenear == FALSE || usenear == TRUE) || !(go == FALSE || go == TRUE)) return MP_REFUSED;
	if (usenear)
	if (!SV_SaveOriginSane(near)) return MP_REFUSED;
	if (!go) return MP_UNSUPPORTED; // saving alone does not move a body
	if (e.run_pmhold || e.run_sp_phase || e.rec_gh_on || e.run_ms_phase) return MP_UNSUPPORTED;
	if (e.rec_sl_hold) return MP_REFUSED;
	if (!(e.rw_pin == TRUE && e.rec_wt_hold == TRUE && e.rec_wt_pin > 0
		&& e.rec_wt_pin < 16777216 && e.rec_wt_pin == floor(e.rec_wt_pin))) return MP_REFUSED;
	mode = e.rec_wt_holdmove ? e.rec_wt_holdmove : MOVETYPE_WALK;
	if (mode != MOVETYPE_WALK || e.movetype != MOVETYPE_NONE) return MP_UNSUPPORTED;
	if (!SV_SaveLocAllowed(e, TRUE)) return MP_REFUSED;
	// Pre-dispatch go pays one general sl_* charge plus one go charge. Read
	// both here; do not spend tokens or change the authoritative rate gate.
	if (!(min(SL_TOKRATE, e.rec_sl_tok + (time - e.rec_sl_tokt) * SL_TOKRATE) >= 2)) return MP_REFUSED;
	blk = SL_Blk(e);
	if (!(blk >= 0 && blk <= FS_SLCLIENTS && blk == floor(blk))) return MP_REFUSED;
	if (!SL_Fresh(e, blk)) return MP_STALE;
	if (SL_Sweeper(blk)) return MP_REFUSED;
	if (!rec_sl_org || !rec_sl_vel || !rec_sl_pit || !rec_sl_yaw || !rec_sl_duck
		|| !rec_sl_id || !rec_sl_seq || !rec_sl_tick) return MP_STALE;
	if (!(rec_sl_nb[blk] >= 0 && rec_sl_nb[blk] <= SL_Cap(blk)
		&& rec_sl_nb[blk] == floor(rec_sl_nb[blk]))) return MP_STALE;
	if (!(rec_sl_ns[blk] >= 0 && rec_sl_ns[blk] < 16777215 && rec_sl_ns[blk] == floor(rec_sl_ns[blk]))) return MP_STALE;
	if (rec_sl_nb[blk] == SL_Cap(blk) || e.rw_goid || e.rw_goseq) return MP_UNSUPPORTED;
	for (i = 0; i < rec_sl_nb[blk]; i += 1)
	{
		r = SL_Base(blk) + i;
		if (!(rec_sl_id[r] >= 1 && rec_sl_id[r] <= FS_MAXSAVES && rec_sl_id[r] == floor(rec_sl_id[r]))) return MP_STALE;
		if (!(rec_sl_seq[r] >= 0 && rec_sl_seq[r] < 16777216 && rec_sl_seq[r] == floor(rec_sl_seq[r]))) return MP_STALE;
	}
	b = SV_RewindSelectRead(e, t, near, usenear);
	if (b == -1) return MP_MISSING;
	if (b < 0) return MP_STALE;
	m = rw_slot[slot];
	// No cut-chain walk or prefix read here. A sample from before a cut, an
	// ended recorder or an older attachment is unavailable to this warm slice.
	if (!(m[b+18] >= 0 && m[b+18] < 16777216 && m[b+18] == floor(m[b+18]))) return MP_STALE;
	if (e.run_t_state != TS_RUNNING || !(e.run_t_flags & TF_RECORDING) || !(m[b+18] & TF_RECORDING)) return MP_UNSUPPORTED;
	if (!(e.rec_rec_gen >= 0 && e.rec_rec_gen < 16777216 && e.rec_rec_gen == floor(e.rec_rec_gen))) return MP_STALE;
	if (!(e.rec_rec_serial > 0 && e.rec_rec_serial < 16777216 && e.rec_rec_serial == floor(e.rec_rec_serial))) return MP_STALE;
	if (m[b+33] != e.rec_rec_serial || m[b+34] != e.rec_rec_gen) return MP_STALE;
	if (!(m[b+29] > 0 && m[b+29] <= e.rec_rec_lines && m[b+29] == floor(m[b+29]))) return MP_STALE;
	org = [m[b+1], m[b+2], m[b+3]];
	vel = [m[b+4], m[b+5], m[b+6]];
	ang = [m[b+7], m[b+8], 0];
	if (!SV_SaveOriginSane(org) || !MP_Vector(vel) || !(vlen(vel) <= 32768)
		|| !MP_Vector(ang) || !(fabs(ang_x) <= 360) || !(fabs(ang_y) <= 360)
		|| !(m[b+9] == 0 || m[b+9] == 1)) return MP_REFUSED;
	org = [MP_SaveDecimal(org_x), MP_SaveDecimal(org_y), MP_SaveDecimal(org_z)];
	vel = [MP_SaveDecimal(vel_x), MP_SaveDecimal(vel_y), MP_SaveDecimal(vel_z)];
	ang = [MP_SaveDecimal(ang_x), MP_SaveDecimal(ang_y), 0];
	if (!SV_SaveOriginSane(org)) return MP_REFUSED;
	out->subject = e; out->map = strzone(mapname); out->owner = strzone(infokey(e, "guid"));
	out->kind = MP_REWIND; out->block = blk; out->ticks = m[b];
	out->ring_base = b; out->ring_serial = m[b+33];
	out->origin = org; out->origin_policy = MP_SET;
	out->velocity = '0 0 0'; out->velocity_policy = MP_SET; out->release_velocity = vel;
	out->angles = ang; out->angle_policy = MP_SET;
	out->forceduck = m[b+9] ? FD_DUCK : FD_STAND; out->forceduck_policy = MP_SET;
	out->held = TRUE; out->mode = MOVETYPE_NONE; out->mode_policy = MP_SET;
	out->ground_policy = MP_CLEAR; out->carrier_policy = MP_CLEAR;
	out->source_clear = MP_SRC_ducktime | MP_SRC_ducking; out->source_replace = MP_SRC_ducked;
	out->source_preserve = MP_SRC_ALL - out->source_clear - out->source_replace;
	out->version = 1;
	return MP_READY;
};

// Release is a separate resolver: current holdrow, not cursor or saved angles.
// Existing release is row-based and never rereads the disk. Do not add a file
// dependency to its policy, nor claim this proves future hold/connection epochs.
float(entity e, float id, float seq, moveprep_t *out) SV_MovePrepRelease =
{
	local float r, base, mode;
	SV_MovePrepClear(out);
	if (!out) return MP_REFUSED;
	r = MP_Row(e, id, seq);
	if (r < 0) return -r;
	if (!e.rec_sl_hold) return MP_REFUSED;
	base = SL_Base(SL_Blk(e));
	if (!(e.rec_sl_holdrow >= base && e.rec_sl_holdrow < base + rec_sl_nb[SL_Blk(e)])) return MP_STALE;
	if (e.rec_sl_holdrow != r) return MP_STALE;
	mode = e.rec_sl_holdmove ? e.rec_sl_holdmove : MOVETYPE_WALK;
	if (mode != MOVETYPE_WALK) return MP_UNSUPPORTED;
	if (!MP_Vector(rec_sl_vel[r])) return MP_REFUSED;
	MP_Identity(e, r, MP_RELEASE, out);
	out->velocity = rec_sl_vel[r]; out->velocity_policy = MP_SET;
	out->release_velocity = rec_sl_vel[r];
	out->mode = mode; out->mode_policy = MP_SET;
	out->version = 1;
	return MP_READY;
};

// P680: preparation never loads zones, releases pins or changes a timer.
float(entity e) MP_ZoneContext =
{
	local float slot;
	if (e == world) return MP_REFUSED;
	slot = num_for_edict(e);
	if (slot < 1 || slot > FS_SLCLIENTS || strcmp(e.classname, "player")) return MP_REFUSED;
	if (!zone_loaded) return MP_STALE;
	if (!(zone_count >= 0 && zone_count <= ZONE_MAX && zone_count == floor(zone_count))) return MP_STALE;
	if (e.run_pmhold || e.run_sp_phase || e.rec_wt_hold || e.rec_gh_on || e.run_ms_phase)
		return MP_UNSUPPORTED;
	if (e.rec_sl_hold)
	{
		if (e.rec_sl_holdmove != 0 && e.rec_sl_holdmove != MOVETYPE_WALK) return MP_UNSUPPORTED;
	}
	else if (e.movetype != MOVETYPE_WALK && e.movetype != MOVETYPE_NOCLIP) return MP_UNSUPPORTED;
	return MP_READY;
};

float(entity e, float z, vector org, float yaw, float pit, float haveyaw, moveprep_t *out)
	MP_ZonePolicy =
{
	if (!SV_SaveOriginSane(org) || !MP_Vector([pit, yaw, 0])) return MP_REFUSED;
	out->subject = e; out->map = strzone(mapname);
	out->zone_hash = strzone(zone_crc); // identity hint only, NOT a lifecycle epoch
	out->zone = z; out->destination_source = MP_DEST_ZONE;
	out->origin = org; out->origin_policy = MP_SET;
	out->velocity = '0 0 0'; out->velocity_policy = MP_SET;
	out->carrier_policy = MP_CLEAR;
	// setorigin/TimerWarped do not clear onground; the NEXT move categorizes it.
	out->ground_policy = MP_KEEP; out->source_preserve = MP_SRC_ALL;
	if (haveyaw)
	{
		out->angles = [pit, yaw, 0]; out->angle_policy = MP_SET;
	}
	if (e.rec_sl_hold)
	{
		out->mode = MOVETYPE_WALK; out->mode_policy = MP_SET;
	}
	out->version = 1;
	return MP_READY;
};

// zone_goto: explicit angles override the destination's yaw exactly as live QC.
float(entity e, float z, float setang, float yaw, float pit, moveprep_t *out) SV_MovePrepZone =
{
	local float status, haveyaw, fallback, unusedyaw;
	local vector org;
	SV_MovePrepClear(out);
	if (!out) return MP_REFUSED;
	status = MP_ZoneContext(e);
	if (status != MP_READY) return status;
	if (!(z >= 0 && z < zone_count && z == floor(z))) return MP_MISSING;
	if (!(setang == 0 || setang == 1)) return MP_REFUSED;
	if (!(zone_td_kind[z] == ZTD_NONE || zone_td_kind[z] == ZTD_POS || zone_td_kind[z] == ZTD_NAME))
		return MP_UNSUPPORTED;
	if (!MP_Vector([pit, yaw, 0])) return MP_REFUSED;
	if (setang)
	{
		org = SV_ZoneDestRead(e, z, unusedyaw, haveyaw, fallback);
		haveyaw = TRUE;
	}
	else
	{
		org = SV_ZoneDestRead(e, z, yaw, haveyaw, fallback);
		pit = 0;
	}
	status = MP_ZonePolicy(e, z, org, yaw, pit, haveyaw, out);
	if (status != MP_READY) return status;
	out->kind = MP_ZONE; out->destination_fallback = fallback;
	return MP_READY;
};

// Chat/zone_reset/restart: freshly scanned cached rows, NOT a new file read.
// A stale list cannot answer whether !r should prefer a save: explicit STALE.
float(entity e, string word, float n, moveprep_t *out) SV_MovePrepReset =
{
	local float status, z, blk, row, yaw, pit, haveyaw, fallback, pick;
	local vector org;
	SV_MovePrepClear(out);
	if (!out) return MP_REFUSED;
	status = MP_ZoneContext(e);
	if (status != MP_READY) return status;
	if (strcmp(word, "!r") && strcmp(word, "!m") && strcmp(word, "!s") && strcmp(word, "!b"))
		return MP_REFUSED;
	if (!(n > -10000000 && n < 10000000 && n == floor(n))) return MP_REFUSED;
	z = SV_ZoneRequestZone(e, word, n);
	if (!(z >= 0 && z < zone_count && z == floor(z))) return MP_MISSING;
	pick = FALSE; row = -1; pit = yaw = fallback = blk = 0; org = '0 0 0';
	if (!strcmp(word, "!r"))
	if (e.run_leg_zone >= 0 && e.run_leg_zone < zone_count)
	if (!SV_TimerWouldRestartSeg(e, z))
	{
		blk = SL_Blk(e);
		// The existing quiet gate is read-only; reuse it without scan/allocation.
		if (SV_SaveLocAllowed(e, TRUE))
		{
			if (!rec_sl_org || !rec_sl_pit || !rec_sl_yaw || !rec_sl_id || !rec_sl_seq || !rec_sl_tick)
				return MP_STALE;
			if (!(rec_sl_nb[blk] >= 0 && rec_sl_nb[blk] <= SL_Cap(blk)
				&& rec_sl_nb[blk] == floor(rec_sl_nb[blk]))) return MP_STALE;
			if (!SL_Fresh(e, blk)) return MP_STALE;
			pick = SV_SaveLocPickInZoneRead(e, z, org, yaw, pit, row);
		}
	}
	if (pick)
		haveyaw = TRUE;
	else
	{
		if (!(zone_td_kind[z] == ZTD_NONE || zone_td_kind[z] == ZTD_POS || zone_td_kind[z] == ZTD_NAME))
			return MP_UNSUPPORTED;
		org = SV_ZoneDestRead(e, z, yaw, haveyaw, fallback);
		pit = 0; // a post-snap refused save must not leak its pitch into fallback
	}
	status = MP_ZonePolicy(e, z, org, yaw, pit, haveyaw, out);
	if (status != MP_READY) return status;
	out->kind = MP_RESET; out->destination_fallback = fallback;
	if (pick)
	{
		out->destination_source = MP_DEST_SAVE; out->block = blk;
		out->id = rec_sl_id[row]; out->seq = rec_sl_seq[row];
		if (blk > 0) out->owner = strzone(infokey(e, "guid"));
	}
	return MP_READY;
};
