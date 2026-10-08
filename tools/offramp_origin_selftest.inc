/* PRIVATE setup-only authored collider controls, before replay rows begin.
 * Runs the real BIH and physent merge. Not a geometric-exit/motion fixture.
 */
static void OfframpOrigin_Check(int *n, int *failed, const char *label, qboolean ok)
{
	(*n)++;
	if (!ok)
		(*failed)++;
	Con_Printf("OFFRAMPORIGIN_CHECK %i %s %i\n", *n, label, ok ? 1 : 0);
}
static qboolean OfframpOrigin_Unstamped(model_t *model, int hull, const framestate_t *frame, const vec3_t axis[3], const vec3_t start, const vec3_t end, const vec3_t mins, const vec3_t maxs, qboolean capsule, unsigned int contents, trace_t *out)
{
	qboolean result = BIH_Trace(model, hull, frame, axis, start, end, mins, maxs, capsule, contents, out);
	offramp_origin_out = NULL; /* simulate a nonparticipating NativeTrace */
	return result;
}
void OfframpOrigin_Selftest(void)
{
#if defined(Q2BSPS) || defined(Q3BSPS)
	static playermove_t savedpm;
	model_t world, child;
	struct bihnode_s nodes[3], childnode;
	struct bihtransform_s transform;
	q2cbrush_t brush[2];
	q2cbrushside_t sides[2][6];
	mplane_t planes[2][6];
	q2mapsurface_t surface;
	struct bihproberec_s savedprobe;
	struct offramp_origin_s witness;
	trace_t hit, validation;
	vec3_t start = {0,0,0}, end = {10,0,0}, zero = {0,0,0};
	vec3_t inside = {3,0,0}, clearend = {1,0,0};
	vecV_t triangle[3] = {{2,10,-10}, {2,-10,10}, {2,-10,-10}};
	index_t indexes[3] = {0,1,2};
	int b, i, n = 0, failed = 0;
	int savedsourceclip = bih_sourceclip;

	BIH_ProbeSave(&savedprobe);
	savedpm = pmove;
	memset(&world, 0, sizeof(world));
	memset(&child, 0, sizeof(child));
	memset(nodes, 0, sizeof(nodes));
	memset(&childnode, 0, sizeof(childnode));
	memset(&transform, 0, sizeof(transform));
	memset(brush, 0, sizeof(brush));
	memset(sides, 0, sizeof(sides));
	memset(planes, 0, sizeof(planes));
	memset(&surface, 0, sizeof(surface));
	for (b = 0; b < 2; b++)
	{
		brush[b].contents = FTECONTENTS_SOLID;
		brush[b].numsides = 6;
		brush[b].brushside = sides[b];
		VectorSet(brush[b].absmins, 2+4*b, -10, -10);
		VectorSet(brush[b].absmaxs, 4+4*b, 10, 10);
		for (i = 0; i < 6; i++)
		{
			int axis = i/2;
			planes[b][i].normal[axis] = (i & 1) ? -1 : 1;
			planes[b][i].dist = (i & 1) ? -brush[b].absmins[axis] : brush[b].absmaxs[axis];
			sides[b][i].plane = &planes[b][i];
			sides[b][i].surface = &surface;
		}
		nodes[b+1].type = BIH_BRUSH;
		nodes[b+1].data.brush = &brush[b];
		nodes[b+1].data.contents = FTECONTENTS_SOLID;
	}
	nodes[0].type = BIH_GROUP;
	nodes[0].group.firstchild = 1;
	nodes[0].group.numchildren = 2;
	world.cnodes = nodes;
	world.funcs.NativeTrace = BIH_Trace;
	world.loadstate = MLS_LOADED;
	VectorSet(world.mins, -100, -100, -100);
	VectorSet(world.maxs, 100, 100, 100);
	Q_strncpyz(world.name, "origin-selftest-world", sizeof(world.name));
	child = world;
	child.cnodes = &childnode;
	Q_strncpyz(child.name, "origin-selftest-child", sizeof(child.name));
	childnode = nodes[2];
	for (i = 0; i < 3; i++)
		transform.axis[i][i] = 1;

	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	witness = OfframpOrigin_Read(&hit);
	OfframpOrigin_Check(&n, &failed, "leaf-competition", witness.kind == 1 && witness.leaf == 1 && witness.depth == 0 && hit.fraction < .3f);
	nodes[2].data.brush = &brush[0];
	bih_sourceclip = 0;
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	OfframpOrigin_Check(&n, &failed, "legacy-equal-fraction-replaces", OfframpOrigin_Read(&hit).leaf == 2);
	bih_sourceclip = 1;
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	OfframpOrigin_Check(&n, &failed, "source-equal-fraction-keeps-first", OfframpOrigin_Read(&hit).leaf == 1);
	bih_sourceclip = savedsourceclip;
	nodes[1].type = BIH_TRIANGLE;
	nodes[1].data.tri.xyz = triangle;
	nodes[1].data.tri.indexes = indexes;
	nodes[2].data.brush = &brush[1];
	start[1] = start[2] = end[1] = end[2] = -2;
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	witness = OfframpOrigin_Read(&hit);
	OfframpOrigin_Check(&n, &failed, "triangle-witness", witness.kind == 2 && witness.leaf == 1 && hit.fraction < .3f);
	start[1] = start[2] = end[1] = end[2] = 0;
	nodes[1].type = BIH_BRUSH;
	nodes[1].data.brush = &brush[0];
	nodes[2].type = BIH_MODEL;
	nodes[2].data.mesh.model = &child;
	nodes[2].data.mesh.tr = &transform;
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	witness = OfframpOrigin_Read(&hit);
	OfframpOrigin_Check(&n, &failed, "losing-nested-model", witness.model == &world && witness.leaf == 1 && witness.depth == 0);
	childnode.data.brush = &brush[0];
	nodes[1].data.brush = &brush[1];
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	witness = OfframpOrigin_Read(&hit);
	OfframpOrigin_Check(&n, &failed, "winning-nested-model", witness.model == &child && witness.leaf == 0 && witness.rootleaf == 2 && witness.depth == 1);
	child.funcs.NativeTrace = OfframpOrigin_Unstamped;
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	OfframpOrigin_Check(&n, &failed, "unstamped-nested-result", OfframpOrigin_Read(&hit).kind == 0);
	child.funcs.NativeTrace = BIH_Trace;
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, clearend, zero, zero, false, MASK_PLAYERSOLID, &hit);
	OfframpOrigin_Check(&n, &failed, "nohit-clears-witness", hit.fraction == 1 && OfframpOrigin_Read(&hit).kind == 0);
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, inside, inside, zero, zero, false, MASK_PLAYERSOLID, &hit);
	OfframpOrigin_Check(&n, &failed, "solid-abstains", hit.startsolid && OfframpOrigin_Read(&hit).kind == 0);
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	witness = OfframpOrigin_Read(&hit);
	OfframpOrigin_Check(&n, &failed, "different-output-address", witness.kind == 1 && OfframpOrigin_Read(&validation).kind == 0);
	BIH_Trace(&world, 0, NULLFRAMESTATE, NULL, start, clearend, zero, zero, false, MASK_PLAYERSOLID, &validation);
	OfframpOrigin_Check(&n, &failed, "later-probe-preserves-copy", witness.kind == 1 && witness.model == &child && OfframpOrigin_Read(&validation).kind == 0);

	memset(&pmove, 0, sizeof(pmove));
	pmove.numphysent = 2;
	pmove.skipent = -1;
	pmove.physents[0].model = &world;
	pmove.physents[1].model = &child;
	pmove.physents[0].scale = pmove.physents[1].scale = 1;
	childnode.data.brush = &brush[1];
	nodes[1].data.brush = &brush[0];
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	OfframpOrigin_Check(&n, &failed, "losing-physent-preserves-winner", hit.entnum == 0 && offramp_origin_pm.model == &world && offramp_origin_pm.leaf == 1);
	pmove.numphysent = 3;
	pmove.physents[2].isportal = true;
	pmove.physents[2].scale = 1;
	VectorSet(pmove.physents[2].origin, 100, 0, 0);
	VectorSet(pmove.physents[2].mins, -1, -1, -1);
	VectorSet(pmove.physents[2].maxs, 1, 1, 1);
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	OfframpOrigin_Check(&n, &failed, "portal-physent-abstains", hit.entnum == 0 && offramp_origin_pm.kind == 0);
	pmove.numphysent = 2;
	pmove.physents[0].origin[0] = 4;
	childnode.data.brush = &brush[0];
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	OfframpOrigin_Check(&n, &failed, "winning-physent-replaces-winner", hit.entnum == 1 && offramp_origin_pm.model == &child && offramp_origin_pm.depth == 0);
	child.funcs.NativeTrace = OfframpOrigin_Unstamped;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	OfframpOrigin_Check(&n, &failed, "unstamped-physent-abstains", hit.entnum == 1 && offramp_origin_pm.kind == 0);
	offramp_origin_active = false;
	OfframpOrigin_Check(&n, &failed, "disabled-read-abstains", OfframpOrigin_Read(&hit).kind == 0);
	offramp_origin_active = true;
	pmove = savedpm;
	BIH_ProbeRestore(&savedprobe);
	offramp_origin_out = NULL;
	offramp_origin_pm = OfframpOrigin_Unknown();
	Con_Printf("OFFRAMPORIGIN_SELFTEST %i %i\n", n, failed);
#else
	Con_Printf("OFFRAMPORIGIN_SELFTEST 0 1\n");
#endif
}
