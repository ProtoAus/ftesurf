/* PRIVATE com_bih.c include. Copy already accepted native dereferences at WIN.
 * No xyz/index/model pointers survive. Native tri has no vertex-array count:
 * this is NOT an independent pointer/index bounds validator. NEVER ship.
 */
void OfframpTriCopy_Snapshot(struct offramp_origin_s *r, const struct bihdata_s *info, int plane_tag, qboolean box)
{
	struct offramp_tricopy_s copy;
	vec3_t a, b, normal;
	float area;
	int i, j;

	memset(&r->triangle, 0, sizeof(r->triangle));
	if (!info)
		return;
	r->triangle.status = 2;
	if (!info->tri.xyz || !info->tri.indexes)
		return;
	memset(&copy, 0, sizeof(copy));
	for (i = 0; i < 3; i++)
	{
		copy.indexes[i] = info->tri.indexes[i];
		for (j = 0; j < 3; j++)
		{
			float value = info->tri.xyz[info->tri.indexes[i]][j];
			if (!isfinite(value))
				return;
			copy.vertices[i][j] = value;
		}
	}
	VectorSubtract(copy.vertices[0], copy.vertices[1], a);
	VectorSubtract(copy.vertices[2], copy.vertices[1], b);
	CrossProduct(a, b, normal);
	area = DotProduct(normal, normal);
	if (!isfinite(area) || area <= 0)
		return;
	copy.status = 1;
	copy.plane_tag = plane_tag;
	copy.bevels = box && pm_trisoup_bevels.ival;
	copy.back_slab = 4; /* installer guards BOTH native slab expressions */
	r->triangle = copy;
}

static unsigned int offramp_tricopy_count, offramp_tricopy_complete, offramp_tricopy_invalid;
void OfframpTriCopy_Begin(void)
{
	offramp_tricopy_count = offramp_tricopy_complete = offramp_tricopy_invalid = 0;
	Con_Printf("OFFRAMPTRICOPY_BEGIN 1 3\n");
	Con_Printf("OFFRAMPTRICOPY_SOURCE %s\n", OFFRAMP_TRICOPY_SOURCE_SHA256);
}
void OfframpTriCopy_Dump(unsigned int ordinal, unsigned int tick, const struct offramp_origin_s *r)
{
	const struct offramp_tricopy_s *s = &r->triangle;
	offramp_tricopy_count++;
	offramp_tricopy_complete += s->status == 1;
	offramp_tricopy_invalid += s->status == 2;
	Con_Printf("OFFRAMPTRICOPY_CONTACT %u %u %i %i %i %.9g %u %u %u %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g\n",
		ordinal, tick, s->status, s->plane_tag, s->bevels, s->back_slab,
		s->indexes[0], s->indexes[1], s->indexes[2],
		s->vertices[0][0], s->vertices[0][1], s->vertices[0][2],
		s->vertices[1][0], s->vertices[1][1], s->vertices[1][2],
		s->vertices[2][0], s->vertices[2][1], s->vertices[2][2]);
}
void OfframpTriCopy_End(void)
{
	Con_Printf("OFFRAMPTRICOPY_END %u %u %u\n", offramp_tricopy_count, offramp_tricopy_complete, offramp_tricopy_invalid);
}
