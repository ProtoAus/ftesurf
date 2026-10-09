/* PRIVATE setup-only native winning-triangle copy controls, NOT motion/support. */
static void OfframpTriCopy_Check(int *n, int *failed, const char *label, qboolean ok)
{
	(*n)++;
	if (!ok)
		(*failed)++;
	Con_Printf("OFFRAMPTRICOPY_CHECK %i %s %i\n", *n, label, ok ? 1 : 0);
}
static qboolean OfframpTriCopy_Hybrid(model_t *model, int hull, const framestate_t *frame, const vec3_t axis[3], const vec3_t start, const vec3_t end, const vec3_t mins, const vec3_t maxs, qboolean capsule, unsigned int contents, trace_t *out)
{
	return BIH_Trace(model, hull, frame, axis, start, end, mins, maxs, capsule, contents, out);
}
void OfframpTriCopy_Selftest(model_t *world)
{
#if defined(Q2BSPS) || defined(Q3BSPS)
	static playermove_t oldpm;
	struct bihnode_s *nodes = world->cnodes, original[2], childnode;
	struct bihtransform_s transform;
	struct bihdata_s invalid;
	struct bihproberec_s savedprobe;
	struct offramp_origin_s r, saved;
	model_t child = *world;
	vecV_t xyz[6] = {{2,10,-10}, {2,-10,10}, {2,-10,-10}, {6,10,-10}, {6,-10,10}, {6,-10,-10}};
	index_t nearidx[3] = {0,1,2}, faridx[3] = {3,4,5}, badidx[3] = {0,0,0};
	trace_t hit, validation;
	vec3_t start = {0,-2,-2}, end = {10,-2,-2}, zero = {0,0,0}, clear = {1,-2,-2}, inside = {2,-2,-2};
	float value;
	int i, n = 0, failed = 0;

	BIH_ProbeSave(&savedprobe);
	oldpm = pmove;
	original[0] = nodes[1];
	original[1] = nodes[2];
	memset(&transform, 0, sizeof(transform));
	for (i = 0; i < 3; i++)
		transform.axis[i][i] = 1;
	nodes[1].type = nodes[2].type = BIH_TRIANGLE;
	nodes[1].data.tri.xyz = nodes[2].data.tri.xyz = xyz;
	nodes[1].data.tri.indexes = nearidx;
	nodes[2].data.tri.indexes = faridx;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = saved = OfframpOrigin_Read(&hit);
	OfframpTriCopy_Check(&n, &failed, "whole-winning-triangle", hit.fraction < .3f && r.kind == 2 && r.leaf == 1 && r.triangle.status == 1 && r.triangle.indexes[0] == 0 && r.triangle.indexes[2] == 2 && r.triangle.vertices[0][0] == 2 && r.triangle.back_slab == 4 && !r.triangle.bevels && !r.shape.status);
	nearidx[0] = 2;
	OfframpTriCopy_Check(&n, &failed, "indexes-mutation-preserves-copy", saved.triangle.indexes[0] == 0 && nearidx[0] == 2);
	nearidx[0] = 0;
	value = xyz[0][0];
	xyz[0][0] += 7;
	OfframpTriCopy_Check(&n, &failed, "vertices-mutation-preserves-copy", saved.triangle.vertices[0][0] == value && saved.triangle.vertices[0][0] != xyz[0][0]);
	xyz[0][0] = value;
	OfframpTriCopy_Check(&n, &failed, "different-output-address-abstains", hit.fraction < 1 && OfframpOrigin_Read(&validation).triangle.status == 0);
	nodes[1].data.tri.indexes = faridx;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &validation);
	r = OfframpOrigin_Read(&validation);
	OfframpTriCopy_Check(&n, &failed, "later-same-kind-probe-preserves-copy", validation.fraction > .5f && validation.fraction < .7f && r.triangle.vertices[0][0] == 6 && r.triangle.indexes[0] == 3 && saved.triangle.vertices[0][0] == 2 && saved.triangle.indexes[0] == 0);
	nodes[2].data.tri.indexes = nearidx;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpTriCopy_Check(&n, &failed, "nearer-same-kind-replaces-copy", hit.fraction < .3f && r.leaf == 2 && r.triangle.vertices[0][0] == 2 && r.triangle.indexes[0] == 0);
	nodes[1].data.tri.indexes = nearidx;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpTriCopy_Check(&n, &failed, "triangle-equal-fraction-replaces", hit.fraction < .3f && r.leaf == 2 && r.triangle.status == 1);
	nodes[1] = original[0];
	nodes[2].data.tri.indexes = faridx;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpTriCopy_Check(&n, &failed, "brush-winner-clears-triangle", hit.fraction < .3f && r.kind == 1 && r.shape.status == 1 && r.triangle.status == 0 && r.triangle.vertices[0][0] == 0);
	r = saved;
	OfframpTriCopy_Snapshot(&r, NULL, 0, false);
	OfframpTriCopy_Check(&n, &failed, "null-source-clears-copy", r.triangle.status == 0 && r.triangle.indexes[2] == 0 && r.triangle.back_slab == 0);
	invalid = nodes[2].data;
	invalid.tri.xyz = NULL;
	OfframpTriCopy_Snapshot(&r, &invalid, 0, false);
	OfframpTriCopy_Check(&n, &failed, "null-xyz-invalid-not-partial", r.triangle.status == 2 && r.triangle.indexes[0] == 0 && r.triangle.vertices[0][0] == 0 && r.triangle.back_slab == 0);
	invalid.tri.xyz = xyz;
	invalid.tri.indexes = NULL;
	OfframpTriCopy_Snapshot(&r, &invalid, 0, false);
	OfframpTriCopy_Check(&n, &failed, "null-indexes-invalid-not-partial", r.triangle.status == 2 && r.triangle.indexes[0] == 0 && r.triangle.vertices[0][0] == 0);
	invalid.tri.indexes = badidx;
	OfframpTriCopy_Snapshot(&r, &invalid, 0, false);
	OfframpTriCopy_Check(&n, &failed, "degenerate-source-invalid-not-partial", r.triangle.status == 2 && r.triangle.indexes[0] == 0 && r.triangle.vertices[0][0] == 0);

	nodes[1].type = BIH_TRIANGLE;
	nodes[1].data.tri.xyz = xyz;
	nodes[1].data.tri.indexes = nearidx;
	childnode = nodes[2];
	child.cnodes = &childnode;
	nodes[2].type = BIH_MODEL;
	nodes[2].data.mesh.model = &child;
	nodes[2].data.mesh.tr = &transform;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpTriCopy_Check(&n, &failed, "losing-nested-triangle-copy", hit.fraction < .3f && r.model == world && r.leaf == 1 && r.depth == 0 && r.triangle.vertices[0][0] == 2);
	nodes[1].data.tri.indexes = faridx;
	childnode.data.tri.indexes = nearidx;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, end, zero, zero, false, MASK_PLAYERSOLID, &hit);
	r = OfframpOrigin_Read(&hit);
	OfframpTriCopy_Check(&n, &failed, "winning-nested-local-triangle-copy", hit.fraction < .3f && r.model == &child && r.leaf == 0 && r.rootleaf == 2 && r.depth == 1 && r.triangle.vertices[0][0] == 2);
	nodes[1].data.tri.indexes = nearidx;
	nodes[2] = childnode;
	nodes[2].data.tri.indexes = faridx;
	childnode.data.tri.indexes = faridx;
	memset(&pmove, 0, sizeof(pmove));
	pmove.numphysent = 2;
	pmove.skipent = -1;
	pmove.physents[0].model = world;
	pmove.physents[1].model = &child;
	pmove.physents[0].scale = pmove.physents[1].scale = 1;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	r = offramp_origin_pm;
	OfframpTriCopy_Check(&n, &failed, "losing-physent-triangle-copy", hit.fraction < .3f && hit.entnum == 0 && r.model == world && r.triangle.vertices[0][0] == 2 && r.native_bih);
	pmove.physents[0].origin[0] = 4;
	childnode.data.tri.indexes = nearidx;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	r = offramp_origin_pm;
	OfframpTriCopy_Check(&n, &failed, "winning-physent-triangle-copy", hit.fraction < .3f && hit.entnum == 1 && r.model == &child && r.depth == 0 && r.triangle.vertices[0][0] == 2);
	pmove.physents[0].origin[0] = -1;
	childnode.data.tri.indexes = faridx;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	r = offramp_origin_pm;
	OfframpTriCopy_Check(&n, &failed, "translated-triangle-copy-metadata", hit.fraction < .2f && hit.entnum == 0 && r.triangle.vertices[0][0] == 2 && r.instance_origin[0] == -1);
	pmove.physents[0].origin[0] = 0;
	pmove.capsule = true;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	r = offramp_origin_pm;
	OfframpTriCopy_Check(&n, &failed, "capsule-triangle-copy-metadata", hit.fraction < .3f && hit.entnum == 0 && r.capsule && r.triangle.status == 1);
	pmove.capsule = false;
	world->funcs.NativeTrace = OfframpTriCopy_Hybrid;
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	r = offramp_origin_pm;
	OfframpTriCopy_Check(&n, &failed, "hybrid-triangle-copy-not-direct-bih", hit.fraction < .3f && hit.entnum == 0 && r.triangle.status == 1 && !r.native_bih);
	world->funcs.NativeTrace = BIH_Trace;
	pmove.numphysent = 3;
	pmove.physents[2].isportal = true;
	pmove.physents[2].scale = 1;
	VectorSet(pmove.physents[2].origin, 100, 0, 0);
	VectorSet(pmove.physents[2].mins, -1, -1, -1);
	VectorSet(pmove.physents[2].maxs, 1, 1, 1);
	hit = PM_PlayerTrace(start, end, MASK_PLAYERSOLID);
	OfframpTriCopy_Check(&n, &failed, "portal-clears-triangle-copy", hit.fraction < .3f && hit.entnum == 0 && offramp_origin_pm.kind == 0 && offramp_origin_pm.triangle.status == 0);
	pmove.numphysent = 2;
	offramp_origin_active = false;
	OfframpTriCopy_Check(&n, &failed, "disabled-read-clears-copy", OfframpOrigin_Read(&hit).triangle.status == 0);
	offramp_origin_active = true;
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, inside, inside, zero, zero, false, MASK_PLAYERSOLID, &hit);
	OfframpTriCopy_Check(&n, &failed, "solid-return-clears-copy", hit.startsolid && OfframpOrigin_Read(&hit).triangle.status == 0);
	BIH_Trace(world, 0, NULLFRAMESTATE, NULL, start, clear, zero, zero, false, MASK_PLAYERSOLID, &hit);
	OfframpTriCopy_Check(&n, &failed, "nohit-return-clears-copy", hit.fraction == 1 && OfframpOrigin_Read(&hit).triangle.status == 0);

	nodes[1] = original[0];
	nodes[2] = original[1];
	pmove = oldpm;
	BIH_ProbeRestore(&savedprobe);
	offramp_origin_out = NULL;
	offramp_origin_pm = OfframpOrigin_Unknown();
	Con_Printf("OFFRAMPTRICOPY_SELFTEST %i %i\n", n, failed);
#else
	Con_Printf("OFFRAMPTRICOPY_SELFTEST 0 1\n");
#endif
}
