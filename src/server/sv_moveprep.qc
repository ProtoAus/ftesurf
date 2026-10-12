/*
 * Inert movement POLICY descriptors, not native snapshots or permission to
 * predict. No production caller. Timer/recorder/placement remain in saveloc.
 * Use Alloc/Free; output owns its identity strings. Reuse clears old output.
 * A READY answer describes this call only: no content/connection epoch or
 * persistent cache is supplied here. See tools/p677moveprep.md.
 */
#define MP_READY 1
#define MP_MISSING 2
#define MP_STALE 3
#define MP_REFUSED 4
#define MP_UNSUPPORTED 5
#define MP_LOAD 1
#define MP_RELEASE 2
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
#define MP_SRC_ALL 4095i

typedef struct
{
	float version, kind;
	entity subject;
	string map, owner;
	float block, id, seq, ticks;
	vector origin, velocity, angles, release_velocity;
	float origin_policy, velocity_policy, angle_policy, mode_policy;
	float ground_policy, carrier_policy, gravity_policy, jump_policy;
	float mode, forceduck, held;
	int source_preserve, source_clear, source_replace;
} moveprep_t;

void(moveprep_t *out) SV_MovePrepClear =
{
	if (!out)
		return;
	if (strcmp(out->map, "")) strunzone(out->map);
	if (strcmp(out->owner, "")) strunzone(out->owner);
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
	out->ground_policy = MP_CLEAR; out->carrier_policy = MP_CLEAR;
	out->source_clear = MP_SRC_ducktime | MP_SRC_ducking;
	out->source_replace = MP_SRC_ducked;
	out->source_preserve = MP_SRC_ALL - out->source_clear - out->source_replace;
	out->held = (e.rec_sl_hold != 0);
	if (out->held) out->velocity = '0 0 0';
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
