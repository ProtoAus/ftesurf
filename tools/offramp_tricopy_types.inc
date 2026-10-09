/* PRIVATE value-copy only; no trace/model/plugin ABI change. NEVER ship. */
#ifndef OFFRAMP_TRICOPY_TYPES_H
#define OFFRAMP_TRICOPY_TYPES_H
struct offramp_tricopy_s
{
	/* 0 nontriangle/unknown, 1 complete three vertices, 2 invalid source. */
	int status, plane_tag, bevels;
	float back_slab;
	unsigned int indexes[3];
	vec3_t vertices[3];
};
struct offramp_origin_s;
struct bihdata_s;
void OfframpTriCopy_Snapshot(struct offramp_origin_s *r, const struct bihdata_s *info, int plane_tag, qboolean box);
void OfframpTriCopy_Selftest(model_t *world);
void OfframpTriCopy_Begin(void);
void OfframpTriCopy_Dump(unsigned int ordinal, unsigned int tick, const struct offramp_origin_s *r);
void OfframpTriCopy_End(void);
#endif
