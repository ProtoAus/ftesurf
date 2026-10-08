/* PRIVATE com_bih.c include. No model/plane pointers are retained in shape
 * data: copy at the winning leaf, NEVER query the model again at dump.
 */
void OfframpShape_Snapshot(struct offramp_origin_s *r, const struct q2cbrush_s *brush)
{
	int i;
	memset(&r->shape, 0, sizeof(r->shape));
	if (!brush)
		return;
	r->shape.numsides = brush->numsides;
	if (brush->numsides < 4 || !brush->brushside)
	{
		r->shape.status = 3;
		return;
	}
	VectorCopy(brush->absmins, r->shape.mins);
	VectorCopy(brush->absmaxs, r->shape.maxs);
	if (brush->numsides > OFFRAMP_SHAPE_CAP)
	{
		r->shape.status = 2;
		return; /* NEVER expose a partial plane list as a complete shape */
	}
	for (i = 0; i < brush->numsides; i++)
	{
		const mplane_t *plane = brush->brushside[i].plane;
		if (!plane)
		{
			memset(r->shape.planes, 0, sizeof(r->shape.planes));
			r->shape.status = 3;
			return;
		}
		VectorCopy(plane->normal, r->shape.planes[i]);
		r->shape.planes[i][3] = plane->dist;
	}
	r->shape.status = 1;
}

/* Everything below runs AFTER capture, except Begin's setup-only header.
 * The dictionary points ONLY into immutable COPIED private capture entries,
 * never at source brush/model storage. Payload IDs are NOT collider IDs.
 */
static unsigned int offramp_shape_dumped, offramp_shape_complete, offramp_shape_capped, offramp_shape_count;
static const struct offramp_shape_s *offramp_shape_dictionary[OFFRAMP_SHAPE_DICT_CAP];
void OfframpShape_Begin(void)
{
	offramp_shape_dumped = offramp_shape_complete = offramp_shape_capped = offramp_shape_count = 0;
	Con_Printf("OFFRAMPGEOM_BEGIN 2 %i %i\n", OFFRAMP_SHAPE_CAP, OFFRAMP_SHAPE_DICT_CAP);
}
void OfframpShape_Dump(unsigned int ordinal, unsigned int tick, const struct offramp_origin_s *r)
{
	unsigned int id;
	int i;
	for (id = 0; id < offramp_shape_count; id++)
		if (!memcmp(offramp_shape_dictionary[id], &r->shape, sizeof(r->shape)))
			break;
	if (id == offramp_shape_count)
	{
		if (offramp_shape_count == OFFRAMP_SHAPE_DICT_CAP)
		{
			Con_Printf("OFFRAMPGEOM_ABORT shape-table-cap\n");
			return;
		}
		offramp_shape_dictionary[offramp_shape_count++] = &r->shape;
		Con_Printf("OFFRAMPGEOM_SHAPE %u %i %i %.9g %.9g %.9g %.9g %.9g %.9g\n",
			id+1, r->shape.status, r->shape.numsides, r->shape.mins[0], r->shape.mins[1],
			r->shape.mins[2], r->shape.maxs[0], r->shape.maxs[1], r->shape.maxs[2]);
		if (r->shape.status == 1)
			for (i = 0; i < r->shape.numsides; i++)
				Con_Printf("OFFRAMPGEOM_PLANE %u %i %.9g %.9g %.9g %.9g\n", id+1, i,
					r->shape.planes[i][0], r->shape.planes[i][1], r->shape.planes[i][2], r->shape.planes[i][3]);
	}
	offramp_shape_dumped++;
	offramp_shape_complete += (r->shape.status == 1);
	offramp_shape_capped += (r->shape.status == 2);
	Con_Printf("OFFRAMPGEOM_CONTACT %u %u %u %i %i %i %u %.9g %.9g %.9g %.9g %.9g %.9g %.9g %i %i\n",
		ordinal, tick, id+1, r->leaf, r->rootleaf, r->depth, r->contents,
		r->instance_origin[0], r->instance_origin[1], r->instance_origin[2],
		r->instance_angles[0], r->instance_angles[1], r->instance_angles[2], r->instance_scale, r->capsule, r->native_bih);
}
void OfframpShape_End(void)
{
	Con_Printf("OFFRAMPGEOM_END %u %u %u %u\n", offramp_shape_dumped, offramp_shape_complete, offramp_shape_capped, offramp_shape_count);
}
