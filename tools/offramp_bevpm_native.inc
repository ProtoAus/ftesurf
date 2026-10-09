/* PRIVATE separately enveloped native PM triangle bevel actors. NEVER ship.
 * Only initial seeds author pmove; all later states come from PM_PlayerMove.
 * Queries follow commands; fixed numeric copies dump after capture ends.
 */
#define OFFRAMP_BEVPM_STEPS 32
void OfframpBevPM_ProbeSave(void);
void OfframpBevPM_ProbeRestore(void);
static void OfframpBevPM_f(void)
{
	static playermove_t saved;
	static model_t world, empty;
	static struct bihleaf_s leaf;
	static vecV_t xyz[3] = {{0,0,0}, {0,256,-256*4.0f/3.0f}, {256,0,-256}};
	static index_t indexes[3] = {0,1,2};
	static struct {
		vec3_t pos, vel, mins, maxs;
		unsigned int ticks;
		float rate, ramp, ground;
		int capsule, pmtype, ducked, ducking, oldbuttons;
		float ducktime;
		struct {
			vec3_t start, end, normal;
			float fraction, truefraction, dist;
			int startsolid, allsolid, ent;
			unsigned int contents;
		} q[3];
	} rows[OFFRAMP_BEVPM_STEPS];
	static const char *labels[3] = {"edge-bevel-departure", "removed-triangle-control", "bevel-disabled-control"};
	static const char *queries[3] = {"stationary", "down2", "untriangled"};
	movevars_t savedvars = movevars;
	float savedfloats[5] = {pms_frametime, pms_forwardmove, pms_sidemove, pms_upmove, pms_maxspeed};
	vec3_t savedvectors[5], start, end;
	int savedflags[7] = {pms_warned_hullfloor, pms_surfed, pms_portalcrossed, pms_haveportals, pms_anyslide, pms_slidecontact, pms_slidetick};
	int savedclip = bih_sourceclip;
	float savedrotated = pm_rotatedboxhulls.value, savedbevels = pm_trisoup_bevels.value;
	int c, i, j, q, capture = atoi(Cmd_Argv(1)), oracle = atoi(Cmd_Argv(2));
	trace_t trace;
#ifdef OFFRAMP_MOTION_CAPTURE
	float savedcapture = offrampbuf_replay.value;
	struct offramp_origin_s savednative = offramp_origin_native, savedpm = offramp_origin_pm;
	const trace_t *savedout = offramp_origin_out;
	qboolean savedactive = offramp_origin_active;
	if (offrampbuf_active) { Con_Printf("OFFRAMPBEVPM_REFUSE active-capture\n"); return; }
#else
	if (capture) { Con_Printf("OFFRAMPBEVPM_REFUSE fixture-only-build\n"); return; }
#endif
	if (Cmd_Argc() != 3 || capture < 0 || capture > 1 || oracle < 0 || oracle > 1 ||
		strcmp(Cmd_Argv(1), capture ? "1" : "0") || strcmp(Cmd_Argv(2), oracle ? "1" : "0") ||
		pm_dispprobe.ival || pm_ladderprobe.ival)
	{ Con_Printf("OFFRAMPBEVPM_REFUSE arguments-or-debug-probe\n"); return; }
	saved = pmove;
	OfframpBevPM_ProbeSave();
	VectorCopy(pms_forward, savedvectors[0]); VectorCopy(pms_right, savedvectors[1]); VectorCopy(pms_up, savedvectors[2]);
	VectorCopy(pms_standmins, savedvectors[3]); VectorCopy(pms_standmaxs, savedvectors[4]);
	Cvar_SetValue(&pm_rotatedboxhulls, 1);
	OfframpMotion_Profile();
	Con_Printf("OFFRAMPBEVPM_BEGIN 1 %i %i 3 32\nOFFRAMPBEVPM_SOURCE %s %s %s\n", capture, oracle,
		OFFRAMP_BEVPM_SOURCE_SHA256, OFFRAMP_MOTION_SOURCE_SHA256, OFFRAMP_MOTION_ENGINE_COMMIT);
	for (c = 0; c < 3; c++)
	{
		memset(&world, 0, sizeof(world)); memset(&empty, 0, sizeof(empty)); memset(&leaf, 0, sizeof(leaf));
		world.loadstate = MLS_LOADED;
		Q_strncpyz(world.name, "maps/authored_offramp_bevpm.bsp", sizeof(world.name));
		VectorSet(world.mins, -16, -16, -512); VectorSet(world.maxs, 272, 272, 64);
		empty = world;
		BIH_Build(&empty, &leaf, 0); empty.numnodes = 1; /* builder owns one empty group */
		leaf.type = BIH_TRIANGLE; leaf.data.contents = FTECONTENTS_SOLID;
		leaf.data.tri.xyz = xyz; leaf.data.tri.indexes = indexes;
		VectorSet(leaf.mins, 0, 0, xyz[1][2]); VectorSet(leaf.maxs, 256, 256, 0);
		BIH_Build(&world, &leaf, c == 1 ? 0 : 1); world.numnodes = 1;
		Cvar_SetValue(&pm_trisoup_bevels, c != 2);
		memset(&pmove, 0, sizeof(pmove)); memset(rows, 0, sizeof(rows));
		pmove.pm_type = PM_NORMAL; pmove.numphysent = 1; pmove.physents[0].model = &world;
		pmove.physents[0].scale = 1; pmove.skipent = -1; pmove.surfacefriction = 1; pmove.rampoff = 1;
		VectorSet(pmove.player_mins, -16, -16, 0); VectorSet(pmove.player_maxs, 16, 16, 62);
		VectorSet(pmove.origin, -8, 64, -32); VectorSet(pmove.velocity, -25, 200, -400);
		Con_Printf("OFFRAMPBEVPM_CASE %i %s 32 %i %i\n", c, labels[c], c != 1, c != 2);
		Con_Printf("OFFRAMPBEVPM_FIXTURE %i 0 1 2", c);
		for (j = 0; j < 3; j++) Con_Printf(" %.9g %.9g %.9g", (double)xyz[j][0], (double)xyz[j][1], (double)xyz[j][2]);
		Con_Printf("\nOFFRAMPBEVPM_SEED %i -8 64 -32 -25 200 -400 -16 -16 0 16 16 62\n", c);
#ifdef OFFRAMP_MOTION_CAPTURE
		Cvar_SetValue(&offrampbuf_replay, capture);
		PMSrc_OfframpBegin(0, true);
#endif
		for (i = 0; i < OFFRAMP_BEVPM_STEPS; i++)
		{
			pmove.cmd.msec = 15;
#ifdef OFFRAMP_MOTION_CAPTURE
			PMSrc_OfframpRow(i, i+1, i);
#endif
			PM_PlayerMove(1);
			VectorCopy(pmove.origin, rows[i].pos); VectorCopy(pmove.velocity, rows[i].vel);
			VectorCopy(pmove.player_mins, rows[i].mins); VectorCopy(pmove.player_maxs, rows[i].maxs);
			rows[i].ticks = pmove.ticksrun; rows[i].rate = pmove.tickused;
			rows[i].ramp = pmove.rampcontact; rows[i].ground = pmove.onground;
			rows[i].capsule = pmove.capsule; rows[i].pmtype = pmove.pm_type;
			rows[i].ducked = pmove.ducked; rows[i].ducking = pmove.ducking;
			rows[i].oldbuttons = pmove.oldbuttons; rows[i].ducktime = pmove.ducktime;
			if (!oracle) continue;
			for (q = 0; q < 3; q++)
			{
				model_t *savedmodel = pmove.physents[0].model;
				VectorCopy(rows[i].pos, start); VectorCopy(start, end);
				if (q) end[2] -= 2;
				if (q == 2) pmove.physents[0].model = &empty;
				trace = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
				pmove.physents[0].model = savedmodel;
				VectorCopy(start, rows[i].q[q].start); VectorCopy(end, rows[i].q[q].end);
				VectorCopy(trace.plane.normal, rows[i].q[q].normal);
				rows[i].q[q].fraction = trace.fraction; rows[i].q[q].truefraction = trace.truefraction;
				rows[i].q[q].dist = trace.plane.dist; rows[i].q[q].startsolid = trace.startsolid;
				rows[i].q[q].allsolid = trace.allsolid; rows[i].q[q].ent = trace.entnum;
				rows[i].q[q].contents = trace.contents;
			}
		}
#ifdef OFFRAMP_MOTION_CAPTURE
		PMSrc_OfframpEnd();
#endif
		for (i = 0; i < OFFRAMP_BEVPM_STEPS; i++)
		{
			Con_Printf("OFFRAMPBEVPM_TICK %i %i 15 0 0 0 %u %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i %.9g %i %i %i\n",
				c, i, rows[i].ticks, (double)rows[i].rate, (double)rows[i].ramp, (double)rows[i].ground,
				(double)rows[i].pos[0], (double)rows[i].pos[1], (double)rows[i].pos[2],
				(double)rows[i].vel[0], (double)rows[i].vel[1], (double)rows[i].vel[2],
				(double)rows[i].mins[0], (double)rows[i].mins[1], (double)rows[i].mins[2],
				(double)rows[i].maxs[0], (double)rows[i].maxs[1], (double)rows[i].maxs[2],
				rows[i].ducked, rows[i].ducking, (double)rows[i].ducktime, rows[i].capsule, rows[i].pmtype, rows[i].oldbuttons);
			if (!oracle) continue;
			for (q = 0; q < 3; q++)
				Con_Printf("OFFRAMPBEVPM_QUERY %i %i %s %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i %i %.9g %.9g %.9g %.9g %u\n", c, i, queries[q],
					(double)rows[i].q[q].start[0], (double)rows[i].q[q].start[1], (double)rows[i].q[q].start[2],
					(double)rows[i].q[q].end[0], (double)rows[i].q[q].end[1], (double)rows[i].q[q].end[2],
					(double)rows[i].q[q].fraction, (double)rows[i].q[q].truefraction,
					rows[i].q[q].startsolid ? 1 : 0, rows[i].q[q].allsolid ? 1 : 0, rows[i].q[q].ent,
					(double)rows[i].q[q].normal[0], (double)rows[i].q[q].normal[1], (double)rows[i].q[q].normal[2],
					(double)rows[i].q[q].dist, rows[i].q[q].contents);
		}
		Con_Printf("OFFRAMPBEVPM_CASE_END %i 32\n", c);
		ZG_FreeGroup(&world.memgroup); ZG_FreeGroup(&empty.memgroup);
	}
#ifdef OFFRAMP_MOTION_CAPTURE
	Cvar_SetValue(&offrampbuf_replay, savedcapture);
	offramp_origin_active = savedactive; offramp_origin_native = savednative;
	offramp_origin_pm = savedpm; offramp_origin_out = savedout;
#endif
	Cvar_SetValue(&pm_rotatedboxhulls, savedrotated); Cvar_SetValue(&pm_trisoup_bevels, savedbevels);
	pmove = saved; movevars = savedvars; bih_sourceclip = savedclip;
	pms_frametime = savedfloats[0]; pms_forwardmove = savedfloats[1]; pms_sidemove = savedfloats[2]; pms_upmove = savedfloats[3]; pms_maxspeed = savedfloats[4];
	VectorCopy(savedvectors[0], pms_forward); VectorCopy(savedvectors[1], pms_right); VectorCopy(savedvectors[2], pms_up);
	VectorCopy(savedvectors[3], pms_standmins); VectorCopy(savedvectors[4], pms_standmaxs);
	pms_warned_hullfloor = savedflags[0]; pms_surfed = savedflags[1]; pms_portalcrossed = savedflags[2]; pms_haveportals = savedflags[3];
	pms_anyslide = savedflags[4]; pms_slidecontact = savedflags[5]; pms_slidetick = savedflags[6];
	OfframpBevPM_ProbeRestore();
	Con_Printf("OFFRAMPBEVPM_END 3\n");
}
