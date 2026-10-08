/* PRIVATE primitive/copy controls, inside setup before replay starts.
 * Not authored surf departure, seam, jump or capsule movement fixtures.
 */
static qboolean OfframpShape_Hybrid(model_t *model, int hull, const framestate_t *frame, const vec3_t axis[3], const vec3_t start, const vec3_t end, const vec3_t mins, const vec3_t maxs, qboolean capsule, unsigned int contents, trace_t *out)
{
	return BIH_Trace(model, hull, frame, axis, start, end, mins, maxs, capsule, contents, out);
}
static void OfframpShape_Check(int *n, int *failed, const char *label, qboolean ok)
{
	(*n)++;
	if (!ok)
		(*failed)++;
	Con_Printf("OFFRAMPGEOM_CHECK %i %s %i\n", *n, label, ok ? 1 : 0);
}
void OfframpShape_Selftest(model_t *world, struct q2cbrush_s *brush)
{
#if defined(Q2BSPS) || defined(Q3BSPS)
	static playermove_t oldpm;
	struct bihnode_s *nodes = world->cnodes, original[2], childnode;
	struct bihtransform_s transform;
	q2cbrush_t large = *brush;
	q2cbrushside_t many[OFFRAMP_SHAPE_CAP+1];
	model_t child = *world;
	struct offramp_origin_s r, saved;
	trace_t hit, validation;
	vec3_t start = {0,0,0}, end = {10,0,0}, zero = {0,0,0}, clear = {1,0,0};
	vecV_t triangle[3] = {{2,10,-10}, {2,-10,10}, {2,-10,-10}};
	index_t indexes[3] = {0,1,2};
	float distance;
	int i, matches, n = 0, failed = 0;

	oldpm = pmove;
	original[0] = nodes[1];
	original[1] = nodes[2];
	childnode = nodes[2];
	child.cnodes = &childnode;
	memset(&transform, 0, sizeof(transform));
	for (i = 0; i < 3; i++)
		transform.axis[i][i] = 1;

	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpShape_Check(&n, &failed, "whole-brush-copy", r.shape.status == 1 && r.shape.numsides == 6 && r.shape.mins[0] == 2 && r.shape.maxs[0] == 4 && r.native_bih);
	matches = 0;
	for (i = 0; i < r.shape.numsides && i < OFFRAMP_SHAPE_CAP; i++)
		matches += VectorCompare(r.shape.planes[i], hit.plane.normal) && r.shape.planes[i][3] == hit.plane.dist;
	OfframpShape_Check(&n, &failed, "accepted-plane-membership", matches == 1);
	saved = r;
	distance = brush->brushside[1].plane->dist;
	brush->brushside[1].plane->dist += 10;
	OfframpShape_Check(&n, &failed, "source-mutation-cannot-change-copy", saved.shape.planes[1][3] == distance && saved.shape.planes[1][3] != brush->brushside[1].plane->dist);
	brush->brushside[1].plane->dist = distance;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, clear, zero, zero, false, MASK_PLAYERSOLID, &validation);
	OfframpShape_Check(&n, &failed, "later-probe-preserves-geometry", saved.shape.status == 1 && saved.shape.mins[0] == 2 && OfframpOrigin_Read(&validation).shape.status == 0);

	nodes[2].type = BIH_MODEL;
	nodes[2].data.mesh.model = &child;
	nodes[2].data.mesh.tr = &transform;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpShape_Check(&n, &failed, "losing-nested-shape", r.model == world && r.shape.mins[0] == 2 && r.depth == 0);
	nodes[1].data.brush = original[1].data.brush;
	childnode.data.brush = brush;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpShape_Check(&n, &failed, "winning-nested-local-shape", r.model == &child && r.shape.mins[0] == 2 && r.depth == 1);
	nodes[2].type = BIH_TRIANGLE;
	nodes[2].data.tri.xyz = triangle;
	nodes[2].data.tri.indexes = indexes;
	start[1] = start[2] = end[1] = end[2] = -2;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpShape_Check(&n, &failed, "triangle-clears-brush-data", r.kind == 2 && r.shape.status == 0 && r.shape.numsides == 0 && r.shape.planes[0][3] == 0);
	start[1] = start[2] = end[1] = end[2] = 0;
	nodes[1] = original[0];
	nodes[2] = original[1];

	for (i = 0; i < OFFRAMP_SHAPE_CAP+1; i++)
		many[i] = brush->brushside[i%6];
	large.numsides = OFFRAMP_SHAPE_CAP+1;
	large.brushside = many;
	nodes[1].data.brush = &large;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpShape_Check(&n, &failed, "whole-shape-cap-abstention", r.kind == 1 && r.shape.status == 2 && r.shape.numsides == OFFRAMP_SHAPE_CAP+1 && r.shape.planes[0][3] == 0);
	OfframpShape_Snapshot(&r, NULL);
	OfframpShape_Check(&n, &failed, "null-brush-clears-shape", r.shape.status == 0 && r.shape.numsides == 0 && r.shape.mins[0] == 0);
	large.numsides = 0;
	OfframpShape_Snapshot(&r, &large);
	OfframpShape_Check(&n, &failed, "invalid-side-count-abstains", r.shape.status == 3 && r.shape.numsides == 0);
	nodes[1] = original[0];
	childnode = original[1];

	memset(&pmove, 0, sizeof(pmove));
	pmove.numphysent = 2;
	pmove.skipent = -1;
	pmove.physents[0].model = world;
	pmove.physents[1].model = &child;
	pmove.physents[0].scale = pmove.physents[1].scale = 1;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	OfframpShape_Check(&n, &failed, "losing-physent-shape", hit.entnum == 0 && offramp_origin_pm.shape.mins[0] == 2 && offramp_origin_pm.native_bih);
	pmove.physents[0].origin[0] = -1;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	OfframpShape_Check(&n, &failed, "translated-instance-recorded", hit.entnum == 0 && offramp_origin_pm.shape.mins[0] == 2 && offramp_origin_pm.instance_origin[0] == -1);
	pmove.physents[0].origin[0] = 0;
	pmove.capsule = true;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	OfframpShape_Check(&n, &failed, "capsule-metadata-recorded", hit.entnum == 0 && offramp_origin_pm.capsule && offramp_origin_pm.shape.status == 1);
	pmove.capsule = false;
	world->funcs.NativeTrace = OfframpShape_Hybrid;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	OfframpShape_Check(&n, &failed, "hybrid-callback-not-direct-bih", hit.entnum == 0 && offramp_origin_pm.shape.status == 1 && !offramp_origin_pm.native_bih);
	world->funcs.NativeTrace = BIH_Trace;

	nodes[1] = original[0];
	nodes[2] = original[1];
	pmove = oldpm;
	offramp_origin_out = NULL;
	offramp_origin_pm = OfframpOrigin_Unknown();
	Con_Printf("OFFRAMPGEOM_SELFTEST %i %i\n", n, failed);
#else
	Con_Printf("OFFRAMPGEOM_SELFTEST 0 1\n");
#endif
}
