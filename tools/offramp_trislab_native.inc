/* PRIVATE full native BIH back-slab queries, NOT PM movement/support. NEVER ship. */
static void OfframpTriSlab_Selftest(void)
{
#if defined(Q2BSPS) || defined(Q3BSPS)
	struct bihnode_s nodes[2];
	model_t world;
	struct bihproberec_s savedprobe;
	struct offramp_origin_s savednative = offramp_origin_native, savedpm = offramp_origin_pm;
	const trace_t *savedout = offramp_origin_out;
	qboolean savedactive = offramp_origin_active;
	int savedclip = bih_sourceclip;
	float savedbevels = pm_trisoup_bevels.value;
	vecV_t xyz[3] = {{-100,-100,0}, {0,100,0}, {100,-100,0}};
	index_t indexes[3] = {0,1,2};
	vec3_t mins = {-.5f,-.5f,-.5f}, maxs = {.5f,.5f,.5f};
	static const float z[6][2] = {{6,-6}, {-6,2}, {-6,-2}, {-2,-2}, {0,0}, {0,0}};
	struct {vec3_t start, end; trace_t hit; struct offramp_origin_s origin;} rows[24];
	int r, i, c, active;

	BIH_ProbeSave(&savedprobe);
	memset(&world, 0, sizeof(world));
	memset(nodes, 0, sizeof(nodes));
	memset(rows, 0, sizeof(rows));
	nodes[0].type = BIH_GROUP;
	nodes[0].group.firstchild = 1;
	nodes[1].type = BIH_TRIANGLE;
	nodes[1].data.contents = FTECONTENTS_SOLID;
	nodes[1].data.tri.xyz = xyz;
	nodes[1].data.tri.indexes = indexes;
	world.cnodes = nodes;
	world.funcs.NativeTrace = BIH_Trace;
	world.loadstate = MLS_LOADED;
	VectorSet(world.mins, -200, -200, -200);
	VectorSet(world.maxs, 200, 200, 200);
	Q_strncpyz(world.name, "trislab-selftest-world", sizeof(world.name));
	bih_sourceclip = 1;
	offramp_origin_active = true;
	Cvar_SetValue(&pm_trisoup_bevels, 1);
	for (r = 0; r < 24; r++)
	{
		c = r % 6;
		active = (r % 12) < 6;
		nodes[0].group.numchildren = active ? 1 : 0;
		VectorSet(rows[r].start, c == 5 ? 150 : 0, 0, z[c][0]);
		VectorSet(rows[r].end, c == 5 ? 150 : 0, 0, z[c][1]);
		BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, rows[r].start, rows[r].end,
			mins, maxs, false, MASK_PLAYERSOLID, &rows[r].hit);
		rows[r].origin = OfframpOrigin_Read(&rows[r].hit);
	}
	/* No query/logging on the mover path. Restore before emitting setup data. */
	bih_sourceclip = savedclip;
	Cvar_SetValue(&pm_trisoup_bevels, savedbevels);
	BIH_ProbeRestore(&savedprobe);
	offramp_origin_active = savedactive;
	offramp_origin_native = savednative;
	offramp_origin_pm = savedpm;
	offramp_origin_out = savedout;
	Con_Printf("OFFRAMPTRISLAB_BEGIN 1 24\nOFFRAMPTRISLAB_SOURCE %s\n", OFFRAMP_TRISLAB_SOURCE_SHA256);
	Con_Printf("OFFRAMPTRISLAB_FIXTURE %u %u %u", (unsigned)indexes[0], (unsigned)indexes[1], (unsigned)indexes[2]);
	for (i = 0; i < 3; i++) Con_Printf(" %.9g %.9g %.9g", (double)xyz[i][0], (double)xyz[i][1], (double)xyz[i][2]);
	Con_Printf(" %.9g %.9g %.9g %.9g %.9g %.9g\n", (double)mins[0], (double)mins[1], (double)mins[2], (double)maxs[0], (double)maxs[1], (double)maxs[2]);
	for (r = 0; r < 24; r++)
	{
		trace_t *h = &rows[r].hit;
		struct offramp_origin_s *o = &rows[r].origin;
		Con_Printf("OFFRAMPTRISLAB_QUERY %i %i %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i %u %.9g %.9g %.9g %.9g %i %i %i %i\n",
			r+1, (r % 12) < 6 ? 1 : 0,
			(double)rows[r].start[0], (double)rows[r].start[1], (double)rows[r].start[2],
			(double)rows[r].end[0], (double)rows[r].end[1], (double)rows[r].end[2],
			(double)h->fraction, (double)h->truefraction, h->startsolid ? 1 : 0, h->allsolid ? 1 : 0,
			h->contents, (double)h->plane.normal[0], (double)h->plane.normal[1], (double)h->plane.normal[2],
			(double)h->plane.dist, o->kind, o->leaf, o->triangle.status, o->triangle.plane_tag);
	}
	Con_Printf("OFFRAMPTRISLAB_END 24\n");
#else
	Con_Printf("OFFRAMPTRISLAB_REFUSE no-bih\n");
#endif
}
