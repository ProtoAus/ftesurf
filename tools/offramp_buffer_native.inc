/* Private-build diagnostic only. Included by pm_source.c through the installer.
 * Never add this to the product build. No printf, allocation, cvar lookup or
 * extra collision trace in the capture path. Dumps run after capture stops.
 * Trace planes may be recovery planes; neither entnum nor trace brush_id is a
 * global/authenticated BSP brush identity. Ordinals are local to one replay.
 */
#define OFFRAMPBUF_CAP 32768
static cvar_t offrampbuf_replay = CVAR("pm_offramp_replay", "0");
struct offrampbuf_tick_s
{
	unsigned int ordinal;
	int row, packet, mt, contact, ground;
	float rate;
	vec3_t origin, velocity, normal;
};
struct offrampbuf_contact_s
{
	unsigned int ordinal, tick;
	int bump, entnum, recovered, startsolid, allsolid;
	float fraction, dist;
	vec3_t normal, start, end, mins, maxs;
};
static struct offrampbuf_tick_s offrampbuf_ticks[OFFRAMPBUF_CAP];
static struct offrampbuf_contact_s offrampbuf_contacts[OFFRAMPBUF_CAP];
static unsigned int offrampbuf_nt, offrampbuf_nc, offrampbuf_dropped;
static qboolean offrampbuf_active;
static int offrampbuf_row, offrampbuf_packet, offrampbuf_mt;
static vec3_t offrampbuf_start, offrampbuf_end;

void PMSrc_OfframpBegin (int mode, qboolean exact)
{
	offrampbuf_active = !mode && exact && offrampbuf_replay.ival;
	if (offrampbuf_active)
	{
		offrampbuf_nt = offrampbuf_nc = offrampbuf_dropped = 0;
		offrampbuf_row = -1;
		Con_Printf("OFFRAMPBUF_BEGIN 1 %u\n", OFFRAMPBUF_CAP);
	}
}

void PMSrc_OfframpRow (int row, int packet, int mt)
{
	if (!offrampbuf_active)
		return;
	offrampbuf_row = row;
	offrampbuf_packet = packet;
	offrampbuf_mt = mt;
}

static void PMSrc_OfframpSweep (vec3_t start, vec3_t end)
{
	if (!offrampbuf_active)
		return;
	VectorCopy(start, offrampbuf_start);
	VectorCopy(end, offrampbuf_end);
}

static void PMSrc_OfframpContact (trace_t *trace, int bump, qboolean recovered)
{
	struct offrampbuf_contact_s *r;
	if (!offrampbuf_active)
		return;
	if (offrampbuf_nc == OFFRAMPBUF_CAP)
	{
		offrampbuf_dropped++;
		return;
	}
	r = &offrampbuf_contacts[offrampbuf_nc];
	r->ordinal = offrampbuf_nc++;
	r->tick = offrampbuf_nt;
	r->bump = bump;
	r->entnum = trace->entnum;
	r->fraction = trace->fraction;
	r->dist = trace->plane.dist;
	r->recovered = recovered;
	r->startsolid = trace->startsolid;
	r->allsolid = trace->allsolid;
	VectorCopy(trace->plane.normal, r->normal);
	VectorCopy(offrampbuf_start, r->start);
	VectorCopy(offrampbuf_end, r->end);
	VectorCopy(pmove.player_mins, r->mins);
	VectorCopy(pmove.player_maxs, r->maxs);
}

static void PMSrc_OfframpTick (void)
{
	struct offrampbuf_tick_s *r;
	if (!offrampbuf_active)
		return;
	if (offrampbuf_nt == OFFRAMPBUF_CAP)
	{
		offrampbuf_dropped++;
		return;
	}
	r = &offrampbuf_ticks[offrampbuf_nt];
	r->ordinal = offrampbuf_nt++;
	r->row = offrampbuf_row;
	r->packet = offrampbuf_packet;
	r->mt = ++offrampbuf_mt;
	r->rate = pms_frametime;
	r->contact = pmove.rampcontact;
	r->ground = pmove.onground;
	VectorCopy(pmove.origin, r->origin);
	VectorCopy(pmove.velocity, r->velocity);
	VectorCopy(pmove.rampnormal, r->normal);
}

void PMSrc_OfframpEnd (void)
{
	unsigned int i;
	if (!offrampbuf_active)
		return;
	offrampbuf_active = false;
	for (i = 0; i < offrampbuf_nt; i++)
	{
		const struct offrampbuf_tick_s *r = &offrampbuf_ticks[i];
		Con_Printf("OFFRAMPBUF_TICK %u %i %i %i %.9g %i %i %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g\n",
			r->ordinal, r->row, r->packet, r->mt, r->rate, r->contact, r->ground,
			r->origin[0], r->origin[1], r->origin[2], r->velocity[0], r->velocity[1], r->velocity[2],
			r->normal[0], r->normal[1], r->normal[2]);
	}
	for (i = 0; i < offrampbuf_nc; i++)
	{
		const struct offrampbuf_contact_s *r = &offrampbuf_contacts[i];
		Con_Printf("OFFRAMPBUF_CONTACT %u %u %i %i %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i %i\n",
			r->ordinal, r->tick, r->bump, r->entnum, r->fraction, r->dist,
			r->normal[0], r->normal[1], r->normal[2], r->start[0], r->start[1], r->start[2],
			r->end[0], r->end[1], r->end[2], r->mins[0], r->mins[1], r->mins[2],
			r->maxs[0], r->maxs[1], r->maxs[2], r->recovered, r->startsolid, r->allsolid);
	}
	Con_Printf("OFFRAMPBUF_END %u %u %u\n", offrampbuf_nt, offrampbuf_nc, offrampbuf_dropped);
}
