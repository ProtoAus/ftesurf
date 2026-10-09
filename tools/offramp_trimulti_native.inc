/* PRIVATE separately enveloped native PM multi-patch actors. NEVER ship.
 * Only initial seeds author pmove; all later states come from PM_PlayerMove.
 * One ramp plane family, 0.8x+0.6z=const; every vertex is an exact float.
 * Queries follow commands; fixed numeric copies dump after capture ends.
 */
#define OFFRAMP_TRIMULTI_STEPS 32
#define OFFRAMP_TRIMULTI_CASES 5
void OfframpTriMulti_DumpLeaves(model_t *mod, int actor);
static void OfframpTriMulti_f(void)
{
	static playermove_t saved;
	static model_t world, empty;
	static struct bihleaf_s leaves[4], none;
	static vecV_t xyz[8];
	static index_t indexes[4][3] = {{0,1,2}, {0,2,3}, {4,5,6}, {4,6,7}};
	/* P1 is y 0..y1, P2 is y y2..256 lowered by drop; live counts the leaves handed to BIH_Build. */
	static const struct { const char *label; float y1, y2, drop; int authored, live; vec3_t vel; } actors[OFFRAMP_TRIMULTI_CASES] = {
		{"seam-handoff", 64, 64, 0, 4, 4, {0, 400, 0}},
		{"narrow-gap", 64, 80, 0, 4, 4, {0, 400, 0}},
		{"wide-gap-recontact", 64, 114, 2, 4, 4, {0, 400, 0}},
		{"removed-neighbour-exit", 64, 114, 2, 4, 2, {0, 400, 0}},
		{"vertical-lift", 256, 256, 0, 2, 2, {40, 400, 30}},
	};
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
	} rows[OFFRAMP_TRIMULTI_STEPS];
	static const char *queries[3] = {"stationary", "down2", "untriangled"};
	movevars_t savedvars = movevars;
	float savedfloats[5] = {pms_frametime, pms_forwardmove, pms_sidemove, pms_upmove, pms_maxspeed};
	vec3_t savedvectors[5], start, end;
	int savedflags[7] = {pms_warned_hullfloor, pms_surfed, pms_portalcrossed, pms_haveportals, pms_anyslide, pms_slidecontact, pms_slidetick};
	int savedclip = bih_sourceclip;
	float savedrotated = pm_rotatedboxhulls.value, savedbevels = pm_trisoup_bevels.value;
	int c, i, j, k, q, capture = atoi(Cmd_Argv(1)), oracle = atoi(Cmd_Argv(2));
	trace_t trace;
#ifdef OFFRAMP_MOTION_CAPTURE
	float savedcapture = offrampbuf_replay.value;
	struct offramp_origin_s savednative = offramp_origin_native, savedpm = offramp_origin_pm;
	const trace_t *savedout = offramp_origin_out;
	qboolean savedactive = offramp_origin_active;
	if (offrampbuf_active) { Con_Printf("OFFRAMPTRIMULTI_REFUSE active-capture\n"); return; }
#else
	if (capture) { Con_Printf("OFFRAMPTRIMULTI_REFUSE fixture-only-build\n"); return; }
#endif
	if (Cmd_Argc() != 3 || capture < 0 || capture > 1 || oracle < 0 || oracle > 1 ||
		strcmp(Cmd_Argv(1), capture ? "1" : "0") || strcmp(Cmd_Argv(2), oracle ? "1" : "0") ||
		pm_dispprobe.ival || pm_ladderprobe.ival)
	{ Con_Printf("OFFRAMPTRIMULTI_REFUSE arguments-or-debug-probe\n"); return; }
	saved = pmove;
	OfframpBevPM_ProbeSave();
	VectorCopy(pms_forward, savedvectors[0]); VectorCopy(pms_right, savedvectors[1]); VectorCopy(pms_up, savedvectors[2]);
	VectorCopy(pms_standmins, savedvectors[3]); VectorCopy(pms_standmaxs, savedvectors[4]);
	Cvar_SetValue(&pm_rotatedboxhulls, 1);
	Cvar_SetValue(&pm_trisoup_bevels, 1);
	OfframpMotion_Profile();
	Con_Printf("OFFRAMPTRIMULTI_BEGIN 2 %i %i %i %i\nOFFRAMPTRIMULTI_SOURCE %s %s %s\n", capture, oracle,
		OFFRAMP_TRIMULTI_CASES, OFFRAMP_TRIMULTI_STEPS,
		OFFRAMP_TRIMULTI_SOURCE_SHA256, OFFRAMP_MOTION_SOURCE_SHA256, OFFRAMP_MOTION_ENGINE_COMMIT);
	for (c = 0; c < OFFRAMP_TRIMULTI_CASES; c++)
	{
		memset(&world, 0, sizeof(world)); memset(&empty, 0, sizeof(empty));
		memset(leaves, 0, sizeof(leaves)); memset(&none, 0, sizeof(none)); memset(xyz, 0, sizeof(xyz));
		world.loadstate = MLS_LOADED;
		Q_strncpyz(world.name, "maps/authored_offramp_trimulti.bsp", sizeof(world.name));
		VectorSet(world.mins, -16, -16, -512); VectorSet(world.maxs, 272, 272, 64);
		empty = world;
		BIH_Build(&empty, &none, 0); empty.numnodes = 1; /* builder owns one empty group */
		VectorSet(xyz[0], 0, 0, 0); VectorSet(xyz[1], 0, actors[c].y1, 0);
		VectorSet(xyz[2], 192, actors[c].y1, -256); VectorSet(xyz[3], 192, 0, -256);
		VectorSet(xyz[4], 0, actors[c].y2, -actors[c].drop); VectorSet(xyz[5], 0, 256, -actors[c].drop);
		VectorSet(xyz[6], 192, 256, -256-actors[c].drop); VectorSet(xyz[7], 192, actors[c].y2, -256-actors[c].drop);
		Con_Printf("OFFRAMPTRIMULTI_CASE %i %s %i %i %i\n", c, actors[c].label, OFFRAMP_TRIMULTI_STEPS, actors[c].authored, actors[c].live);
		for (j = 0; j < actors[c].authored; j++)
		{
			leaves[j].type = BIH_TRIANGLE; leaves[j].data.contents = FTECONTENTS_SOLID;
			leaves[j].data.tri.xyz = xyz; leaves[j].data.tri.indexes = indexes[j];
			VectorCopy(xyz[indexes[j][0]], leaves[j].mins); VectorCopy(xyz[indexes[j][0]], leaves[j].maxs);
			for (k = 1; k < 3; k++)
				for (q = 0; q < 3; q++)
				{
					float v = xyz[indexes[j][k]][q];
					if (v < leaves[j].mins[q]) leaves[j].mins[q] = v;
					if (v > leaves[j].maxs[q]) leaves[j].maxs[q] = v;
				}
			Con_Printf("OFFRAMPTRIMULTI_FIXTURE %i %i %u %u %u %i", c, j, (unsigned int)indexes[j][0],
				(unsigned int)indexes[j][1], (unsigned int)indexes[j][2], j < actors[c].live);
			for (k = 0; k < 3; k++)
				Con_Printf(" %.9g %.9g %.9g", (double)xyz[indexes[j][k]][0], (double)xyz[indexes[j][k]][1], (double)xyz[indexes[j][k]][2]);
			Con_Printf("\n");
		}
		/* The builder may reorder leaves[]; the native copy below is what it built. */
		BIH_Build(&world, leaves, actors[c].live); world.numnodes = 1;
		OfframpTriMulti_DumpLeaves(&world, c);
		memset(&pmove, 0, sizeof(pmove)); memset(rows, 0, sizeof(rows));
		pmove.pm_type = PM_NORMAL; pmove.numphysent = 1; pmove.physents[0].model = &world;
		pmove.physents[0].scale = 1; pmove.skipent = -1; pmove.surfacefriction = 1; pmove.rampoff = 1;
		VectorSet(pmove.player_mins, -16, -16, 0); VectorSet(pmove.player_maxs, 16, 16, 62);
		VectorSet(pmove.origin, 46, 24, -39.5f); VectorCopy(actors[c].vel, pmove.velocity);
		Con_Printf("OFFRAMPTRIMULTI_SEED %i %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g\n", c,
			(double)pmove.origin[0], (double)pmove.origin[1], (double)pmove.origin[2],
			(double)pmove.velocity[0], (double)pmove.velocity[1], (double)pmove.velocity[2],
			(double)pmove.player_mins[0], (double)pmove.player_mins[1], (double)pmove.player_mins[2],
			(double)pmove.player_maxs[0], (double)pmove.player_maxs[1], (double)pmove.player_maxs[2]);
#ifdef OFFRAMP_MOTION_CAPTURE
		Cvar_SetValue(&offrampbuf_replay, capture);
		PMSrc_OfframpBegin(0, true);
#endif
#ifdef OFFRAMP_TRIPATH_SOURCE_SHA256
		OfframpPath_Begin(c, capture);
#endif
		for (i = 0; i < OFFRAMP_TRIMULTI_STEPS; i++)
		{
			pmove.cmd.msec = 15;
#ifdef OFFRAMP_MOTION_CAPTURE
			PMSrc_OfframpRow(i, i+1, i);
#endif
#ifdef OFFRAMP_TRIPATH_SOURCE_SHA256
			offramp_path_tick = i;
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
#ifdef OFFRAMP_TRIPATH_SOURCE_SHA256
		OfframpPath_End();
#endif
		for (i = 0; i < OFFRAMP_TRIMULTI_STEPS; i++)
		{
			Con_Printf("OFFRAMPTRIMULTI_TICK %i %i 15 0 0 0 %u %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i %.9g %i %i %i\n",
				c, i, rows[i].ticks, (double)rows[i].rate, (double)rows[i].ramp, (double)rows[i].ground,
				(double)rows[i].pos[0], (double)rows[i].pos[1], (double)rows[i].pos[2],
				(double)rows[i].vel[0], (double)rows[i].vel[1], (double)rows[i].vel[2],
				(double)rows[i].mins[0], (double)rows[i].mins[1], (double)rows[i].mins[2],
				(double)rows[i].maxs[0], (double)rows[i].maxs[1], (double)rows[i].maxs[2],
				rows[i].ducked, rows[i].ducking, (double)rows[i].ducktime, rows[i].capsule, rows[i].pmtype, rows[i].oldbuttons);
			if (!oracle) continue;
			for (q = 0; q < 3; q++)
				Con_Printf("OFFRAMPTRIMULTI_QUERY %i %i %s %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i %i %.9g %.9g %.9g %.9g %u\n", c, i, queries[q],
					(double)rows[i].q[q].start[0], (double)rows[i].q[q].start[1], (double)rows[i].q[q].start[2],
					(double)rows[i].q[q].end[0], (double)rows[i].q[q].end[1], (double)rows[i].q[q].end[2],
					(double)rows[i].q[q].fraction, (double)rows[i].q[q].truefraction,
					rows[i].q[q].startsolid ? 1 : 0, rows[i].q[q].allsolid ? 1 : 0, rows[i].q[q].ent,
					(double)rows[i].q[q].normal[0], (double)rows[i].q[q].normal[1], (double)rows[i].q[q].normal[2],
					(double)rows[i].q[q].dist, rows[i].q[q].contents);
		}
		Con_Printf("OFFRAMPTRIMULTI_CASE_END %i %i\n", c, OFFRAMP_TRIMULTI_STEPS);
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
	Con_Printf("OFFRAMPTRIMULTI_END %i\n", OFFRAMP_TRIMULTI_CASES);
}
