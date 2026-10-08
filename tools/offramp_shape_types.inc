/* PRIVATE fixed-copy geometry types; no plugin/trace/model ABI changes.
 * Installed as a private header only by offramp_shape_smoke.py.
 */
#ifndef OFFRAMP_SHAPE_TYPES_H
#define OFFRAMP_SHAPE_TYPES_H
#define OFFRAMP_SHAPE_CAP 64
#define OFFRAMP_SHAPE_DICT_CAP 32768
struct offramp_shape_s
{
	/* 0 no brush, 1 whole brush, 2 whole-shape cap abstention, 3 invalid source */
	int status, numsides;
	vec3_t mins, maxs;
	float planes[OFFRAMP_SHAPE_CAP][4];
};
struct offramp_origin_s;
struct q2cbrush_s;
void OfframpShape_Snapshot(struct offramp_origin_s *r, const struct q2cbrush_s *brush);
void OfframpShape_Selftest(model_t *world, struct q2cbrush_s *brush);
void OfframpShape_Begin(void);
void OfframpShape_Dump(unsigned int ordinal, unsigned int tick, const struct offramp_origin_s *r);
void OfframpShape_End(void);
#endif
