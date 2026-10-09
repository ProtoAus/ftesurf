/* PRIVATE restored front-edge/bevel BIH setup queries, NOT PM support. NEVER ship. */
static void OfframpTriBev_Selftest(void)
{
#if defined(Q2BSPS) || defined(Q3BSPS)
	struct bihnode_s nodes[2];
	model_t world;
	struct bihproberec_s savedprobe;
	struct offramp_origin_s savednative = offramp_origin_native, savedpm = offramp_origin_pm, origin;
	const trace_t *savedout = offramp_origin_out;
	qboolean savedactive = offramp_origin_active;
	int savedclip = bih_sourceclip;
	float savedbevels = pm_trisoup_bevels.value;
	vecV_t xyz[3] = {{0,0,0}, {0,4,-4}, {4,0,-4}};
	index_t indexes[3] = {0,1,2};
	vec3_t mins = {-.5f,-.5f,-.5f}, maxs = {.5f,.5f,.5f};
	static const float endpoints[5][2][3] = {
		{{1,1,2}, {1,1,-2}}, {{-.25f,2,0}, {-.25f,2,-2}},
		{{-.25f,2,-.75f}, {-.25f,2,-.75f}}, {{-.25f,2,-2}, {-.25f,2,-2}}, {{6,6,6}, {6,6,6}}
	};
	struct {
		vec3_t start, end, normal;
		float fraction, truefraction, dist;
		int active, bevels, startsolid, allsolid, kind, leaf, rootleaf, depth, native_bih;
		unsigned int contents;
		struct offramp_tricopy_s copy;
	} rows[30];
	trace_t hit;
	int r, i, mode;

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
	VectorSet(world.mins, -16, -16, -16);
	VectorSet(world.maxs, 16, 16, 16);
	Q_strncpyz(world.name, "tribev-selftest-world", sizeof(world.name));
	bih_sourceclip = 1;
	offramp_origin_active = true;
	for (r = 0; r < 30; r++)
	{
		mode = (r % 15) / 5;
		rows[r].active = mode != 2;
		rows[r].bevels = mode != 1;
		nodes[0].group.numchildren = rows[r].active ? 1 : 0;
		Cvar_SetValue(&pm_trisoup_bevels, rows[r].bevels);
		VectorCopy(endpoints[r%5][0], rows[r].start);
		VectorCopy(endpoints[r%5][1], rows[r].end);
		BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, rows[r].start, rows[r].end,
			mins, maxs, false, MASK_PLAYERSOLID, &hit);
		origin = OfframpOrigin_Read(&hit);
		/* Fixed winning values only; no source/model/index/xyz pointer retained. */
		rows[r].copy = origin.triangle;
		rows[r].kind = origin.kind; rows[r].leaf = origin.leaf;
		rows[r].rootleaf = origin.rootleaf; rows[r].depth = origin.depth;
		rows[r].native_bih = origin.native_bih;
		rows[r].fraction = hit.fraction; rows[r].truefraction = hit.truefraction;
		rows[r].startsolid = hit.startsolid; rows[r].allsolid = hit.allsolid;
		rows[r].contents = hit.contents; rows[r].dist = hit.plane.dist;
		VectorCopy(hit.plane.normal, rows[r].normal);
	}
	/* Restore before dumping; no query/logging added to the mover path. */
	bih_sourceclip = savedclip;
	Cvar_SetValue(&pm_trisoup_bevels, savedbevels);
	BIH_ProbeRestore(&savedprobe);
	offramp_origin_active = savedactive;
	offramp_origin_native = savednative;
	offramp_origin_pm = savedpm;
	offramp_origin_out = savedout;
	Con_Printf("OFFRAMPTRIBEV_BEGIN 1 30\nOFFRAMPTRIBEV_SOURCE %s\n", OFFRAMP_TRIBEV_SOURCE_SHA256);
	Con_Printf("OFFRAMPTRIBEV_FIXTURE %u %u %u", (unsigned)indexes[0], (unsigned)indexes[1], (unsigned)indexes[2]);
	for (i = 0; i < 3; i++) Con_Printf(" %.9g %.9g %.9g", (double)xyz[i][0], (double)xyz[i][1], (double)xyz[i][2]);
	Con_Printf(" %.9g %.9g %.9g %.9g %.9g %.9g\n", (double)mins[0], (double)mins[1], (double)mins[2], (double)maxs[0], (double)maxs[1], (double)maxs[2]);
	for (r = 0; r < 30; r++)
	{
		struct offramp_tricopy_s *copy = &rows[r].copy;
		Con_Printf("OFFRAMPTRIBEV_QUERY %i %i %i %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i %u %.9g %.9g %.9g %.9g %i %i %i %i %i\n",
			r+1, rows[r].active, rows[r].bevels,
			(double)rows[r].start[0], (double)rows[r].start[1], (double)rows[r].start[2],
			(double)rows[r].end[0], (double)rows[r].end[1], (double)rows[r].end[2],
			(double)rows[r].fraction, (double)rows[r].truefraction, rows[r].startsolid ? 1 : 0, rows[r].allsolid ? 1 : 0,
			rows[r].contents, (double)rows[r].normal[0], (double)rows[r].normal[1], (double)rows[r].normal[2],
			(double)rows[r].dist, rows[r].kind, rows[r].leaf, rows[r].rootleaf, rows[r].depth, rows[r].native_bih);
		Con_Printf("OFFRAMPTRIBEV_COPY %i %i %i %i %.9g %u %u %u", r+1, copy->status, copy->plane_tag,
			copy->bevels, (double)copy->back_slab, copy->indexes[0], copy->indexes[1], copy->indexes[2]);
		for (i = 0; i < 3; i++) Con_Printf(" %.9g %.9g %.9g", (double)copy->vertices[i][0], (double)copy->vertices[i][1], (double)copy->vertices[i][2]);
		Con_Printf("\n");
	}
	Con_Printf("OFFRAMPTRIBEV_END 30\n");
#else
	Con_Printf("OFFRAMPTRIBEV_REFUSE no-bih\n");
#endif
}
