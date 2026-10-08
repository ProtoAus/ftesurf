/* PRIVATE authored static-brush mover trajectories. NEVER ship this build.
 * Full native collision queries follow each completed PM_PlayerMove command.
 * Numeric rows are copied first and printed only after each case completes.
 */
#include "com_bih.h"
#define OFFRAMP_MOTION_CASES 16
extern cvar_t pm_rotatedboxhulls, pm_trisoup_bevels;
#define OFFRAMP_MOTION_STEPS 192
#define OFFRAMP_MOTION_BRUSHES 2
#define OFFRAMP_MOTION_ORACLES 6
struct offramp_motion_row_s
{
	int caseindex, msec, forward, side, buttons;
	unsigned int ticks;
	float rate, ramp, ground;
	vec3_t pos, vel, mins, maxs;
	int ducked, ducking, capsule, pmtype, oldbuttons;
	float ducktime;
	struct {
		vec3_t start, end, normal;
		float fraction, dist;
		int startsolid, allsolid, ent;
		unsigned int contents;
	} oracle[OFFRAMP_MOTION_ORACLES];
};
static void OfframpMotion_Profile(void)
{
	memset(&movevars, 0, sizeof(movevars));
	movevars.physicsmode = PHYSMODE_SOURCE;
	movevars.coordtype = COORDTYPE_FLOAT_32;
	movevars.ticrate = 0.015f;
	movevars.gravity = 800;
	movevars.entgravity = 1;
	movevars.maxspeed = 250;
	movevars.spectatormaxspeed = 250;
	movevars.maxairspeed = 30;
	movevars.maxvelocity = 3500;
	movevars.accelerate = 5;
	movevars.airaccelerate = 150;
	movevars.wateraccelerate = 10;
	movevars.friction = 4;
	movevars.waterfriction = 1;
	movevars.stopspeed = 75;
	movevars.stepheight = 18;
	movevars.jumpvelocity = 301.9933774f;
	movevars.standablenormal = 0.7f;
	movevars.standheight = 62;
	movevars.duckheight = 45;
	movevars.duckspeed = 0.34f;
	movevars.viewheight = 64;
	movevars.duckviewheight = 47;
	movevars.viewscale = 0.5f;
	movevars.walkspeed = 0.52f;
	movevars.groundtracedist = 2;
	movevars.bumpcount = 8;
	movevars.snaptoground = 1;
	movevars.groundquadrants = 1;
	movevars.fixslopes = 1;
	movevars.fixedges = 1;
	movevars.fixrampbugs = 2;
	movevars.rampretrace = 0.2f;
}
static void OfframpMotion_DumpProfile(void)
{
#define MOTION_PARAM(field) Con_Printf("OFFRAMPMOTION_PARAM %s %.9g\n", #field, (double)movevars.field)
	MOTION_PARAM(physicsmode); MOTION_PARAM(ticrate); MOTION_PARAM(gravity); MOTION_PARAM(entgravity);
	MOTION_PARAM(maxspeed); MOTION_PARAM(spectatormaxspeed); MOTION_PARAM(maxairspeed); MOTION_PARAM(maxvelocity);
	MOTION_PARAM(accelerate); MOTION_PARAM(airaccelerate); MOTION_PARAM(wateraccelerate);
	MOTION_PARAM(friction); MOTION_PARAM(waterfriction); MOTION_PARAM(stopspeed); MOTION_PARAM(stepheight);
	MOTION_PARAM(jumpvelocity); MOTION_PARAM(standablenormal); MOTION_PARAM(standheight); MOTION_PARAM(duckheight);
	MOTION_PARAM(duckspeed); MOTION_PARAM(viewheight); MOTION_PARAM(duckviewheight); MOTION_PARAM(viewscale);
	MOTION_PARAM(walkspeed); MOTION_PARAM(groundtracedist); MOTION_PARAM(bumpcount); MOTION_PARAM(snaptoground);
	MOTION_PARAM(groundquadrants); MOTION_PARAM(fixslopes); MOTION_PARAM(fixedges); MOTION_PARAM(fixrampbugs);
	MOTION_PARAM(rampretrace); MOTION_PARAM(ladders); MOTION_PARAM(slide); MOTION_PARAM(stamina);
	MOTION_PARAM(normalizejump); MOTION_PARAM(jumpaddrise); MOTION_PARAM(jumpzoffset); MOTION_PARAM(autobunny);
	MOTION_PARAM(flags);
#undef MOTION_PARAM
	Con_Printf("OFFRAMPMOTION_PARAM coord_float32 %i\n", movevars.coordtype == COORDTYPE_FLOAT_32);
	Con_Printf("OFFRAMPMOTION_PARAM rotatedboxhulls %i\n", pm_rotatedboxhulls.ival);
	Con_Printf("OFFRAMPMOTION_PARAM trisoup_bevels %i\n", pm_trisoup_bevels.ival);
}
static void OfframpMotion_Query(model_t *model, struct offramp_motion_row_s *row, int q, vec3_t start, vec3_t end)
{
	trace_t trace;
	vec3_t querymaxs, localstart, localend, axis[3];
	const vec3_t *queryaxis = NULL;
	int savedclip = bih_sourceclip;
	VectorCopy(row->maxs, querymaxs);
	if (q == 5) querymaxs[2] = row->mins[2] + movevars.standheight;
	bih_sourceclip = 1;
	VectorCopy(start, localstart); VectorCopy(end, localend);
	if (row->caseindex == 9)
	{
		VectorSubtract(start, pmove.physents[0].origin, localstart);
		VectorSubtract(end, pmove.physents[0].origin, localend);
		if (q != 2)
		{
			AngleVectors(pmove.physents[0].angles, axis[0], axis[1], axis[2]);
			VectorNegate(axis[1], axis[1]); queryaxis = axis;
		}
		/* q2 removes ONLY the local query's rotation, never the mover's. */
	}
	if (row->caseindex >= 10)
	{
		int savedcount = pmove.numphysent;
		model_t *savedmodel = pmove.physents[0].model;
		if (q == 2)
		{
			/* Remove ONLY the extra physent, embedded root or triangle for this query. */
			if (row->caseindex >= 12) pmove.physents[0].model = model;
			else pmove.numphysent = 1;
		}
		trace = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
		pmove.numphysent = savedcount;
		pmove.physents[0].model = savedmodel;
	}
	else
	{
		/* Capsule q2 is a same-pose BOX counterfactual, not actual contact. */
		model->funcs.NativeTrace(model, 0, NULL, queryaxis, localstart, localend, row->mins, querymaxs,
			q == 2 && row->capsule ? false : row->capsule, MASK_PLAYERSOLID, &trace);
	}
	bih_sourceclip = savedclip;
	VectorCopy(start, row->oracle[q].start);
	VectorCopy(end, row->oracle[q].end);
	VectorCopy(trace.plane.normal, row->oracle[q].normal);
	row->oracle[q].fraction = trace.fraction;
	row->oracle[q].dist = trace.plane.dist;
	row->oracle[q].startsolid = trace.startsolid;
	row->oracle[q].allsolid = trace.allsolid;
	row->oracle[q].ent = trace.entnum;
	row->oracle[q].contents = trace.contents;
}
static void OfframpMotion_f(void)
{
	static playermove_t saved;
	static vecV_t triangle[3];
	static index_t triangleindexes[3] = {0, 1, 2};
	static model_t world, single[OFFRAMP_MOTION_BRUSHES];
	static struct bihleaf_s leaves[OFFRAMP_MOTION_BRUSHES];
	static struct bihtransform_s embedded;
	static q2cbrush_t brushes[OFFRAMP_MOTION_BRUSHES];
	static q2cbrushside_t sides[OFFRAMP_MOTION_BRUSHES][7];
	static mplane_t planes[OFFRAMP_MOTION_BRUSHES][7];
	static q2mapsurface_t surface;
	static struct offramp_motion_row_s rows[OFFRAMP_MOTION_STEPS];
	static const char *labels[OFFRAMP_MOTION_CASES] = {
		"interior-ride", "partial-full-side-exit", "convex-side-exit",
		"interior-input-departure", "ground-jump", "overlapping-brush-seam",
		"open-ground-duck-cycle", "ceiling-blocked-unduck", "capsule-ramp-side-departure",
		"translated-yaw-brush-departure", "non-world-physent-departure", "removed-physent-control",
		"embedded-model-departure", "removed-embedded-model-control",
		"triangle-departure", "removed-triangle-control"
	};
	static const char *querylabels[3] = {"stationary", "down2", "projected"};
	movevars_t savedvars = movevars;
	float savedfloats[5] = {pms_frametime, pms_forwardmove, pms_sidemove, pms_upmove, pms_maxspeed};
	vec3_t savedvectors[5];
	int savedflags[7] = {pms_warned_hullfloor, pms_surfed, pms_portalcrossed, pms_haveportals, pms_anyslide, pms_slidecontact, pms_slidetick};
	int savedclip = bih_sourceclip;
	float savedrotatedboxhulls = pm_rotatedboxhulls.value;
	float savedtrisoupbevels = pm_trisoup_bevels.value;
	int capture = atoi(Cmd_Argv(1)), oracle = atoi(Cmd_Argv(2));
	int c, b, i, j, q, nbrush, nsteps;
	vec3_t start, end, projected;
	float minsdot;
#ifdef OFFRAMP_MOTION_CAPTURE
	float savedcapture = offrampbuf_replay.value;
	if (offrampbuf_active)
	{
		Con_Printf("OFFRAMPMOTION_REFUSE active-capture\n");
		return;
	}
#else
	if (capture)
	{
		Con_Printf("OFFRAMPMOTION_REFUSE fixture-only-build\n");
		return;
	}
#endif
	if (Cmd_Argc() != 3 || capture < 0 || capture > 1 || oracle < 0 || oracle > 1 ||
		strcmp(Cmd_Argv(1), capture ? "1" : "0") || strcmp(Cmd_Argv(2), oracle ? "1" : "0"))
	{
		Con_Printf("OFFRAMPMOTION_REFUSE arguments\n");
		return;
	}
	if (pm_dispprobe.ival || pm_ladderprobe.ival)
	{
		Con_Printf("OFFRAMPMOTION_REFUSE active-debug-probe\n");
		return;
	}
	saved = pmove;
	VectorCopy(pms_forward, savedvectors[0]); VectorCopy(pms_right, savedvectors[1]); VectorCopy(pms_up, savedvectors[2]);
	VectorCopy(pms_standmins, savedvectors[3]); VectorCopy(pms_standmaxs, savedvectors[4]);
	Cvar_SetValue(&pm_rotatedboxhulls, 1);
	Cvar_SetValue(&pm_trisoup_bevels, 1);
	OfframpMotion_Profile();
	Con_Printf("OFFRAMPMOTION_BEGIN 7 %i %i %i %i\n", capture, oracle, OFFRAMP_MOTION_CASES, OFFRAMP_MOTION_STEPS);
	Con_Printf("OFFRAMPMOTION_SOURCE %s %s\n", OFFRAMP_MOTION_SOURCE_SHA256, OFFRAMP_MOTION_ENGINE_COMMIT);
	OfframpMotion_DumpProfile();
	memset(&surface, 0, sizeof(surface));
	Q_strncpyz(surface.c.name, "authored-motion", sizeof(surface.c.name));
	for (c = 0; c < OFFRAMP_MOTION_CASES; c++)
	{
		nbrush = c == 5 || c == 7 || c >= 10 ? 2 : 1;
		nsteps = c < 6 || c >= 8 ? 32 : (c == 6 ? 96 : OFFRAMP_MOTION_STEPS);
		memset(&world, 0, sizeof(world)); memset(single, 0, sizeof(single)); memset(leaves, 0, sizeof(leaves));
		memset(brushes, 0, sizeof(brushes)); memset(sides, 0, sizeof(sides)); memset(planes, 0, sizeof(planes));
		world.loadstate = MLS_LOADED;
		Q_strncpyz(world.name, "maps/authored_offramp_motion.bsp", sizeof(world.name));
		VectorSet(world.mins, -256, -256, -512); VectorSet(world.maxs, 256, 256, 512);
		for (b = 0; b < nbrush; b++)
		{
			brushes[b].numsides = c == 2 ? 7 : 6;
			brushes[b].brushside = sides[b]; brushes[b].contents = FTECONTENTS_SOLID;
			VectorSet(brushes[b].absmins, -256, c == 2 ? -256 : (b ? -8 : -64), -512);
			VectorSet(brushes[b].absmaxs, 256, c == 2 ? 256 : (c == 5 ? (b ? 192 : 0) : 64), 512);
			if (c >= 10)
			{
				brushes[b].absmins[1] = b ? -64 : -1024;
				brushes[b].absmaxs[1] = b ? 64 : -896;
			}
			if (c == 6 || c == 7)
			{
				VectorSet(brushes[b].absmins, b ? -32 : -256, b ? -128 : -256, b ? 50 : -512);
				VectorSet(brushes[b].absmaxs, b ? 32 : 256, b ? 128 : 256, b ? 128 : 0);
			}
			for (i = 0; i < brushes[b].numsides; i++)
			{
				sides[b][i].plane = &planes[b][i]; sides[b][i].surface = &surface;
				planes[b][i].type = 3; /* PointContents must use the full signed normal. */
				if (i < 4) { planes[b][i].normal[i/2] = (i&1) ? -1 : 1; planes[b][i].dist = (i&1) ? -brushes[b].absmins[i/2] : brushes[b].absmaxs[i/2]; }
				else if (i == 4) { planes[b][i].normal[2] = -1; planes[b][i].dist = -brushes[b].absmins[2]; }
				else if (i == 5) { planes[b][i].normal[0] = c == 4 || c == 6 || c == 7 ? 0 : 0.8f; planes[b][i].normal[2] = c == 4 || c == 6 || c == 7 ? 1 : 0.6f; if (c == 6 || c == 7) planes[b][i].dist = brushes[b].absmaxs[2]; }
				else { planes[b][i].normal[0] = planes[b][i].normal[1] = 0.7071067811865475f; }
			}
			leaves[b].type = BIH_BRUSH; leaves[b].data.contents = FTECONTENTS_SOLID; leaves[b].data.brush = &brushes[b];
			VectorCopy(brushes[b].absmins, leaves[b].mins); VectorCopy(brushes[b].absmaxs, leaves[b].maxs);
			single[b] = world;
			if (c >= 10)
			{
				VectorCopy(brushes[b].absmins, single[b].mins);
				VectorCopy(brushes[b].absmaxs, single[b].maxs);
				if (b) Q_strncpyz(single[b].name, c >= 12 ? "*authored_offramp_embedded" : "*authored_offramp_entity", sizeof(single[b].name));
			}
			BIH_Build(&single[b], &leaves[b], 1);
			single[b].numnodes = 1;
		}
		if (c >= 14)
		{
			VectorSet(triangle[0], -256, -64, 256*.8f/.6f);
			VectorSet(triangle[1], -256, 64, 256*.8f/.6f);
			VectorSet(triangle[2], 256, 0, -256*.8f/.6f);
			if (c == 14)
			{
				memset(&leaves[0], 0, sizeof(leaves[0]));
				leaves[0].type = BIH_TRIANGLE;
				leaves[0].data.contents = FTECONTENTS_SOLID;
				leaves[0].data.tri.xyz = triangle;
				leaves[0].data.tri.indexes = triangleindexes;
				VectorSet(leaves[0].mins, -256, -64, triangle[2][2]);
				VectorSet(leaves[0].maxs, 256, 64, triangle[0][2]);
			}
		}
		else if (c >= 12)
		{
			memset(&embedded, 0, sizeof(embedded));
			for (i = 0; i < 3; i++) embedded.axis[i][i] = 1;
			if (c == 12)
			{
				memset(&leaves[0], 0, sizeof(leaves[0]));
				leaves[0].type = BIH_MODEL;
				leaves[0].data.contents = FTECONTENTS_SOLID;
				leaves[0].data.mesh.model = &single[1];
				leaves[0].data.mesh.tr = &embedded;
				VectorCopy(single[1].mins, leaves[0].mins);
				VectorCopy(single[1].maxs, leaves[0].maxs);
			}
		}
		BIH_Build(&world, leaves, c >= 10 ? 1 : nbrush);
		world.numnodes = (c >= 10 ? 1 : nbrush)*2-1;
		if (c >= 10)
		{
			VectorCopy(leaves[0].mins, world.mins);
			VectorCopy(leaves[0].maxs, world.maxs);
		}
		memset(&pmove, 0, sizeof(pmove)); memset(rows, 0, sizeof(rows));
		pmove.pm_type = PM_NORMAL; pmove.numphysent = 1; pmove.physents[0].model = &world; pmove.skipent = -1;
		pmove.surfacefriction = 1; pmove.rampoff = 1;
		VectorSet(pmove.player_mins, -16, -16, 0); VectorSet(pmove.player_maxs, 16, 16, 62);
		VectorSet(pmove.origin, c == 2 ? -40 : -100, c == 1 ? 76 : (c == 5 ? -32 : 0), 0);
		pmove.origin[2] = c == 4 || c == 6 || c == 7 ? 0.05f : (12.8f - 0.8f*pmove.origin[0] + 0.05f) / 0.6f;
		VectorSet(pmove.velocity, c == 3 ? 0 : (c == 4 ? 60 : 300), (c == 1 || c == 2 || c == 5 || c == 8 || c >= 10) ? 250 : 0, (c == 3 || c == 4) ? 0 : -400);
		if (c == 6 || c == 7) VectorClear(pmove.velocity);
		if (c == 8)
		{
			/* Native upright capsule offset authors the seed, NOT a support oracle. */
			pmove.capsule = true;
			pmove.origin[2] = (6.4f - 0.8f*pmove.origin[0] + 0.05f) / 0.6f;
		}
		if (c == 9)
		{
			/* Seed support authors the pose, NOT an independent transform oracle. */
			VectorSet(pmove.physents[0].origin, 1000, -300, 100);
			VectorSet(pmove.physents[0].angles, 0, 45, 0);
			pmove.physents[0].scale = 1;
			VectorSet(pmove.origin, 1000-100*sqrtf(.5f), -300-100*sqrtf(.5f),
				100+(16*.8f*sqrtf(2)+80+.05f)/.6f);
			VectorSet(pmove.velocity, 50*sqrtf(.5f), 550*sqrtf(.5f), -400);
		}
		if (c >= 10)
		{
			pmove.numphysent = c == 10 ? 2 : 1;
			pmove.physents[0].scale = 1;
			if (c < 12)
			{
				pmove.physents[1].model = &single[1];
				pmove.physents[1].info = 42;
				pmove.physents[1].scale = 1;
			}
		}
		Con_Printf("OFFRAMPMOTION_CASE %i %s %i %i\n", c, labels[c], nsteps, nbrush);
		for (b = 0; b < nbrush; b++)
		{
			Con_Printf("OFFRAMPMOTION_BRUSH %i %i %i %.9g %.9g %.9g %.9g %.9g %.9g\n", c, b, brushes[b].numsides,
				brushes[b].absmins[0], brushes[b].absmins[1], brushes[b].absmins[2], brushes[b].absmaxs[0], brushes[b].absmaxs[1], brushes[b].absmaxs[2]);
			for (i = 0; i < brushes[b].numsides; i++)
				Con_Printf("OFFRAMPMOTION_PLANE %i %i %i %.9g %.9g %.9g %.9g\n", c, b, i, planes[b][i].normal[0], planes[b][i].normal[1], planes[b][i].normal[2], planes[b][i].dist);
		}
		if (c == 9)
			Con_Printf("OFFRAMPMOTION_INSTANCE %i 0 %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i\n", c,
				pmove.physents[0].origin[0], pmove.physents[0].origin[1], pmove.physents[0].origin[2],
				pmove.physents[0].angles[0], pmove.physents[0].angles[1], pmove.physents[0].angles[2],
				pmove.physents[0].scale, pmove.capsule);
		if (c >= 10)
		{
			Con_Printf("OFFRAMPMOTION_SET %i %i %i\n", c, pmove.numphysent, pmove.skipent);
			for (b = 0; b < (c >= 12 ? 1 : 2); b++)
			{
				physent_t *pe = &pmove.physents[b];
				Con_Printf("OFFRAMPMOTION_PHYSENT %i %i %i %s %i %i\n", c, b, pe->info, pe->model->name, c == 12 || c == 14 ? -1 : b, b < pmove.numphysent);
				Con_Printf("OFFRAMPMOTION_INSTANCE %i %i %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i\n", c, b,
					pe->origin[0], pe->origin[1], pe->origin[2], pe->angles[0], pe->angles[1], pe->angles[2], pe->scale, pmove.capsule);
			}
		}
		if (c >= 14)
			Con_Printf("OFFRAMPMOTION_TRIANGLE %i %i %i %u %u %u %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g\n",
				c, c == 14, c == 14 ? 0 : -1,
				(unsigned int)triangleindexes[0], (unsigned int)triangleindexes[1], (unsigned int)triangleindexes[2],
				triangle[0][0], triangle[0][1], triangle[0][2], triangle[1][0], triangle[1][1], triangle[1][2],
				triangle[2][0], triangle[2][1], triangle[2][2]);
		else if (c >= 12)
			Con_Printf("OFFRAMPMOTION_EMBED %i 0 0 %i %i %s %s %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g\n",
				c, world.numnodes, leaves[0].type == BIH_MODEL, leaves[0].type == BIH_MODEL ? "model" : "brush", single[1].name,
				embedded.origin[0], embedded.origin[1], embedded.origin[2],
				embedded.axis[0][0], embedded.axis[0][1], embedded.axis[0][2],
				embedded.axis[1][0], embedded.axis[1][1], embedded.axis[1][2],
				embedded.axis[2][0], embedded.axis[2][1], embedded.axis[2][2]);
		Con_Printf("OFFRAMPMOTION_SEED %i %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g\n", c,
			pmove.origin[0], pmove.origin[1], pmove.origin[2], pmove.velocity[0], pmove.velocity[1], pmove.velocity[2],
			pmove.player_mins[0], pmove.player_mins[1], pmove.player_mins[2], pmove.player_maxs[0], pmove.player_maxs[1], pmove.player_maxs[2]);
#ifdef OFFRAMP_MOTION_CAPTURE
		Cvar_SetValue(&offrampbuf_replay, capture);
		PMSrc_OfframpBegin(0, true);
#endif
		for (i = 0; i < nsteps; i++)
		{
			struct offramp_motion_row_s *r = &rows[i];
			pmove.cmd.msec = 15; pmove.cmd.forwardmove = c == 6 || c == 7 || (c == 3 && i == 3) ? 250 : 0;
			pmove.cmd.buttons = c == 6 || c == 7 ? (i >= 3 && i <= (c == 6 ? 34 : 44) ? BUTTON_DUCK : 0) : ((c == 4 && i == 3) ? BUTTON_JUMP : 0);
#ifdef OFFRAMP_MOTION_CAPTURE
			PMSrc_OfframpRow(i, i+1, i);
#endif
			PM_PlayerMove(1);
			r->caseindex = c;
			r->msec = pmove.cmd.msec; r->forward = pmove.cmd.forwardmove; r->side = pmove.cmd.sidemove; r->buttons = pmove.cmd.buttons;
			r->ticks = pmove.ticksrun; r->rate = pmove.tickused; r->ramp = pmove.rampcontact; r->ground = pmove.onground;
			VectorCopy(pmove.origin, r->pos); VectorCopy(pmove.velocity, r->vel);
			VectorCopy(pmove.player_mins, r->mins); VectorCopy(pmove.player_maxs, r->maxs);
			r->ducked = pmove.ducked; r->ducking = pmove.ducking; r->ducktime = pmove.ducktime;
			r->capsule = pmove.capsule; r->pmtype = pmove.pm_type; r->oldbuttons = pmove.oldbuttons;
			if (!oracle) continue;
			VectorCopy(r->pos, start); VectorCopy(start, end);
			OfframpMotion_Query(&world, r, 0, start, end);
			end[2] -= 2;
			OfframpMotion_Query(&world, r, 1, start, end);
			if (c >= 8)
			{
				OfframpMotion_Query(c >= 12 ? &single[0] : &world, r, 2, c == 8 ? r->pos : start, c == 8 ? r->pos : end);
				continue;
			}
			minsdot = 0;
			for (j = 0; j < 3; j++) minsdot += planes[0][5].normal[j] * (planes[0][5].normal[j] < 0 ? r->maxs[j] : r->mins[j]);
			VectorCopy(r->pos, projected);
			projected[2] = (planes[0][5].dist - minsdot - planes[0][5].normal[0]*r->pos[0] - planes[0][5].normal[1]*r->pos[1]) / planes[0][5].normal[2];
			VectorCopy(projected, start); VectorCopy(projected, end); start[2] += 2; end[2] -= 2;
			OfframpMotion_Query(&world, r, 2, start, end);
			for (b = 0; b < nbrush; b++) OfframpMotion_Query(&single[b], r, b+3, start, end);
			if (c == 6 || c == 7) OfframpMotion_Query(&world, r, 5, r->pos, r->pos);
		}
#ifdef OFFRAMP_MOTION_CAPTURE
		PMSrc_OfframpEnd();
#endif
		for (i = 0; i < nsteps; i++)
		{
			const struct offramp_motion_row_s *r = &rows[i];
			Con_Printf("OFFRAMPMOTION_TICK %i %i %i %i %i %i %u %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i %.9g %i %i %i\n",
				c, i, r->msec, r->forward, r->side, r->buttons, r->ticks, r->rate, r->ramp, r->ground,
				r->pos[0], r->pos[1], r->pos[2], r->vel[0], r->vel[1], r->vel[2], r->mins[0], r->mins[1], r->mins[2], r->maxs[0], r->maxs[1], r->maxs[2],
				r->ducked, r->ducking, r->ducktime, r->capsule, r->pmtype, r->oldbuttons);
			if (!oracle) continue;
			for (q = 0; q < (c >= 8 ? 3 : nbrush+3+(c == 6 || c == 7)); q++)
			{
				int oq = q == nbrush+3 ? 5 : q;
				Con_Printf("OFFRAMPMOTION_ORACLE %i %i %s %i %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i %i %.9g %.9g %.9g %.9g %u\n", c, i,
					c >= 8 && q == 2 ? (c >= 14 ? "untriangled" : (c >= 12 ? "unembedded" : (c >= 10 ? "worldonly" : (c == 8 ? "box" : "identity")))) : (q == nbrush+3 ? "standing" : querylabels[q < 3 ? q : 2]),
					c >= 10 && q == 2 ? 0 : (q == nbrush+3 || q < 3 ? -1 : q-3),
					r->oracle[oq].start[0], r->oracle[oq].start[1], r->oracle[oq].start[2], r->oracle[oq].end[0], r->oracle[oq].end[1], r->oracle[oq].end[2],
					r->oracle[oq].fraction, r->oracle[oq].startsolid, r->oracle[oq].allsolid, r->oracle[oq].ent,
					r->oracle[oq].normal[0], r->oracle[oq].normal[1], r->oracle[oq].normal[2], r->oracle[oq].dist, r->oracle[oq].contents);
			}
		}
		Con_Printf("OFFRAMPMOTION_CASE_END %i %i\n", c, nsteps);
		ZG_FreeGroup(&world.memgroup);
		for (b = 0; b < nbrush; b++) ZG_FreeGroup(&single[b].memgroup);
	}
#ifdef OFFRAMP_MOTION_CAPTURE
	Cvar_SetValue(&offrampbuf_replay, savedcapture);
#endif
	Cvar_SetValue(&pm_rotatedboxhulls, savedrotatedboxhulls);
	Cvar_SetValue(&pm_trisoup_bevels, savedtrisoupbevels);
	pmove = saved; movevars = savedvars; bih_sourceclip = savedclip;
	pms_frametime = savedfloats[0]; pms_forwardmove = savedfloats[1]; pms_sidemove = savedfloats[2]; pms_upmove = savedfloats[3]; pms_maxspeed = savedfloats[4];
	VectorCopy(savedvectors[0], pms_forward); VectorCopy(savedvectors[1], pms_right); VectorCopy(savedvectors[2], pms_up);
	VectorCopy(savedvectors[3], pms_standmins); VectorCopy(savedvectors[4], pms_standmaxs);
	pms_warned_hullfloor = savedflags[0]; pms_surfed = savedflags[1]; pms_portalcrossed = savedflags[2]; pms_haveportals = savedflags[3];
	pms_anyslide = savedflags[4]; pms_slidecontact = savedflags[5]; pms_slidetick = savedflags[6];
	Con_Printf("OFFRAMPMOTION_END %i\n", OFFRAMP_MOTION_CASES);
}
