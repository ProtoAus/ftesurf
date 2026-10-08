/* PRIVATE pm_source.c include; fixed-size snapshots, no mover ABI change.
 * Copy at accepted contacts and completed native ticks. Dump AFTER capture.
 * Posture flags describe the observed state, not a guessed collision hull.
 */
struct offramp_hull_s
{
	vec3_t mins, maxs;
	int capsule, pmtype, ducked, ducking, oldbuttons;
	float ducktime, raw_standheight, raw_duckheight;
};
static void OfframpHull_Snapshot(struct offramp_hull_s *r)
{
	VectorCopy(pmove.player_mins, r->mins);
	VectorCopy(pmove.player_maxs, r->maxs);
	r->capsule = pmove.capsule;
	r->pmtype = pmove.pm_type;
	r->ducked = pmove.ducked;
	r->ducking = pmove.ducking;
	r->ducktime = pmove.ducktime;
	r->oldbuttons = pmove.oldbuttons;
	r->raw_standheight = movevars.standheight;
	r->raw_duckheight = movevars.duckheight;
}
static void OfframpHull_Selftest(void);
static void OfframpHull_Begin(void)
{
	OfframpHull_Selftest();
	Con_Printf("OFFRAMPHULL_BEGIN 1 %i\n", OFFRAMPBUF_CAP);
}
static void OfframpHull_Dump(qboolean contact, unsigned int ordinal, unsigned int tick, const struct offramp_hull_s *r)
{
	char binding[64];
	if (contact)
		Q_snprintfz(binding, sizeof(binding), "%u %u", ordinal, tick);
	else
		Q_snprintfz(binding, sizeof(binding), "%u", ordinal);
	Con_Printf("OFFRAMPHULL_%s %s %.9g %.9g %.9g %.9g %.9g %.9g %i %i %i %i %.9g %i %.9g %.9g\n",
		contact ? "CONTACT" : "TICK", binding, r->mins[0], r->mins[1], r->mins[2], r->maxs[0], r->maxs[1], r->maxs[2],
		r->capsule, r->pmtype, r->ducked, r->ducking, r->ducktime, r->oldbuttons,
		r->raw_standheight, r->raw_duckheight);
}
