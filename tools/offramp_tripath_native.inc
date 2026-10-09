/* PRIVATE bounded TryPlayerMove path snapshots. Diagnostic server NEVER ships.
 * No allocation, printing or new traces while PM runs. Store value copies only.
 * Unsupported paths are flagged, not generalized from these three actors.
 */
#define OFFRAMP_TRIPATH_MAX 512
static qboolean offramp_path_active;
static int offramp_path_case, offramp_path_tick, offramp_path_calls, offramp_path_count, offramp_path_overflow;
static struct {
	int tick, cached, portals, fixramps, sliding, unsupported, blocked;
	float dt, left, total;
	vec3_t pos, vel, mins, maxs, outpos, outvel;
	int capsule, pmtype, ducked, ducking, oldbuttons, ground;
	float ducktime, ramp, outramp;
} offramp_path_callsbuf[32];
static struct {
	int call, bump, route, reason, aux;
	float left, outleft;
	vec3_t pos, fixed, vel, mins, maxs, end, outpos, outvel;
	float ramp, outramp;
	trace_t trace, validation;
} offramp_path_rows[OFFRAMP_TRIPATH_MAX];
static void OfframpPath_Begin(int c, int capture)
{
	offramp_path_case = c; offramp_path_active = capture != 0;
	offramp_path_calls = offramp_path_count = offramp_path_overflow = 0;
	memset(offramp_path_callsbuf, 0, sizeof(offramp_path_callsbuf));
	memset(offramp_path_rows, 0, sizeof(offramp_path_rows));
}
static int OfframpPath_Call(float dt, qboolean cached, qboolean portals, qboolean fixramps)
{
	int n;
	if (!offramp_path_active) return -1;
	n = offramp_path_calls++;
	if (n >= 32) { offramp_path_overflow++; return -1; }
	offramp_path_callsbuf[n].tick = offramp_path_tick;
	offramp_path_callsbuf[n].dt = dt; offramp_path_callsbuf[n].cached = cached;
	offramp_path_callsbuf[n].portals = portals; offramp_path_callsbuf[n].fixramps = fixramps;
	offramp_path_callsbuf[n].sliding = pms_slidetick;
	VectorCopy(pmove.origin, offramp_path_callsbuf[n].pos); VectorCopy(pmove.velocity, offramp_path_callsbuf[n].vel);
	VectorCopy(pmove.player_mins, offramp_path_callsbuf[n].mins); VectorCopy(pmove.player_maxs, offramp_path_callsbuf[n].maxs);
	offramp_path_callsbuf[n].capsule = pmove.capsule; offramp_path_callsbuf[n].pmtype = pmove.pm_type;
	offramp_path_callsbuf[n].ducked = pmove.ducked; offramp_path_callsbuf[n].ducking = pmove.ducking;
	offramp_path_callsbuf[n].oldbuttons = pmove.oldbuttons; offramp_path_callsbuf[n].ducktime = pmove.ducktime;
	offramp_path_callsbuf[n].ground = pmove.onground; offramp_path_callsbuf[n].ramp = pmove.rampcontact;
	return n;
}
static void OfframpPath_Unsupported(int n)
{
	if (n >= 0) offramp_path_callsbuf[n].unsupported++;
}
static int OfframpPath_Attempt(int call, int bump, vec3_t fixed, vec3_t end, float left)
{
	int n;
	if (call < 0) return -1;
	n = offramp_path_count++;
	if (n >= OFFRAMP_TRIPATH_MAX) { offramp_path_overflow++; return -1; }
	offramp_path_rows[n].call = call; offramp_path_rows[n].bump = bump; offramp_path_rows[n].left = left;
	VectorCopy(pmove.origin, offramp_path_rows[n].pos); VectorCopy(fixed, offramp_path_rows[n].fixed);
	VectorCopy(pmove.velocity, offramp_path_rows[n].vel); VectorCopy(end, offramp_path_rows[n].end);
	VectorCopy(pmove.player_mins, offramp_path_rows[n].mins); VectorCopy(pmove.player_maxs, offramp_path_rows[n].maxs);
	offramp_path_rows[n].ramp = pmove.rampcontact;
	return n;
}
static void OfframpPath_Result(int n, trace_t *trace, int route)
{
	if (n < 0) return;
	offramp_path_rows[n].trace = *trace; offramp_path_rows[n].route = route;
}
static void OfframpPath_Validation(int n, trace_t *trace)
{
	if (n < 0) return;
	offramp_path_rows[n].aux++; offramp_path_rows[n].validation = *trace;
}
static void OfframpPath_Outcome(int n, int reason, float left)
{
	if (n < 0) return;
	offramp_path_rows[n].reason = reason; offramp_path_rows[n].outleft = left;
	VectorCopy(pmove.origin, offramp_path_rows[n].outpos); VectorCopy(pmove.velocity, offramp_path_rows[n].outvel);
	offramp_path_rows[n].outramp = pmove.rampcontact;
}
static void OfframpPath_Return(int n, int blocked, float left, float total)
{
	if (n < 0) return;
	offramp_path_callsbuf[n].blocked = blocked; offramp_path_callsbuf[n].left = left; offramp_path_callsbuf[n].total = total;
	VectorCopy(pmove.origin, offramp_path_callsbuf[n].outpos); VectorCopy(pmove.velocity, offramp_path_callsbuf[n].outvel);
	offramp_path_callsbuf[n].outramp = pmove.rampcontact;
}
static void OfframpPath_Vector(vec3_t v)
{
	Con_Printf(" %.9g %.9g %.9g", (double)v[0], (double)v[1], (double)v[2]);
}
static void OfframpPath_Trace(trace_t *t)
{
	Con_Printf(" %.9g %.9g %i %i %i", (double)t->fraction, (double)t->truefraction, t->startsolid?1:0, t->allsolid?1:0, t->entnum);
	OfframpPath_Vector(t->plane.normal);
	Con_Printf(" %.9g %u", (double)t->plane.dist, t->contents);
	OfframpPath_Vector(t->endpos);
}
static void OfframpPath_End(void)
{
	int n;
	if (!offramp_path_active) return;
	offramp_path_active = false;
	Con_Printf("OFFRAMPTRIPATH_BEGIN 1 %i %i %i %i %s\n", offramp_path_case, offramp_path_calls, offramp_path_count, offramp_path_overflow, OFFRAMP_TRIPATH_SOURCE_SHA256);
	for (n = 0; n < offramp_path_calls && n < 32; n++)
	{
		Con_Printf("OFFRAMPTRIPATH_CALL %i %i %.9g %i %i %i %i %i", n, offramp_path_callsbuf[n].tick,
			(double)offramp_path_callsbuf[n].dt, offramp_path_callsbuf[n].cached, offramp_path_callsbuf[n].portals,
			offramp_path_callsbuf[n].fixramps, offramp_path_callsbuf[n].sliding, offramp_path_callsbuf[n].unsupported);
		OfframpPath_Vector(offramp_path_callsbuf[n].pos); OfframpPath_Vector(offramp_path_callsbuf[n].vel);
		OfframpPath_Vector(offramp_path_callsbuf[n].mins); OfframpPath_Vector(offramp_path_callsbuf[n].maxs);
		Con_Printf(" %i %i %i %i %.9g %i %i %.9g\n", offramp_path_callsbuf[n].capsule, offramp_path_callsbuf[n].pmtype,
			offramp_path_callsbuf[n].ducked, offramp_path_callsbuf[n].ducking, (double)offramp_path_callsbuf[n].ducktime,
			offramp_path_callsbuf[n].oldbuttons, offramp_path_callsbuf[n].ground, (double)offramp_path_callsbuf[n].ramp);
	}
	for (n = 0; n < offramp_path_count && n < OFFRAMP_TRIPATH_MAX; n++)
	{
		Con_Printf("OFFRAMPTRIPATH_ATTEMPT %i %i %i %i %.9g", n, offramp_path_rows[n].call, offramp_path_rows[n].bump, offramp_path_rows[n].route, (double)offramp_path_rows[n].left);
		OfframpPath_Vector(offramp_path_rows[n].pos); OfframpPath_Vector(offramp_path_rows[n].fixed);
		OfframpPath_Vector(offramp_path_rows[n].vel); OfframpPath_Vector(offramp_path_rows[n].end);
		OfframpPath_Vector(offramp_path_rows[n].mins); OfframpPath_Vector(offramp_path_rows[n].maxs);
		Con_Printf(" %.9g", (double)offramp_path_rows[n].ramp); OfframpPath_Trace(&offramp_path_rows[n].trace); Con_Printf("\n");
		if (offramp_path_rows[n].aux)
		{
			Con_Printf("OFFRAMPTRIPATH_VALIDATE %i %i", n, offramp_path_rows[n].aux);
			OfframpPath_Vector(offramp_path_rows[n].trace.endpos); OfframpPath_Trace(&offramp_path_rows[n].validation); Con_Printf("\n");
		}
		Con_Printf("OFFRAMPTRIPATH_OUTCOME %i %i %.9g", n, offramp_path_rows[n].reason, (double)offramp_path_rows[n].outleft);
		OfframpPath_Vector(offramp_path_rows[n].outpos); OfframpPath_Vector(offramp_path_rows[n].outvel);
		Con_Printf(" %.9g\n", (double)offramp_path_rows[n].outramp);
	}
	for (n = 0; n < offramp_path_calls && n < 32; n++)
	{
		Con_Printf("OFFRAMPTRIPATH_RETURN %i %i %.9g %.9g", n, offramp_path_callsbuf[n].blocked,
			(double)offramp_path_callsbuf[n].left, (double)offramp_path_callsbuf[n].total);
		OfframpPath_Vector(offramp_path_callsbuf[n].outpos); OfframpPath_Vector(offramp_path_callsbuf[n].outvel);
		Con_Printf(" %.9g\n", (double)offramp_path_callsbuf[n].outramp);
	}
	Con_Printf("OFFRAMPTRIPATH_END %i\n", offramp_path_case);
}
