/* PRIVATE diagnostic header: installed only in an isolated engine worktree.
 * No ABI changes to trace_t/model_t/plugin tables. Internal pointers never
 * serialize as identities. Single-threaded pm_recsim scope, not live capture.
 */
#ifndef OFFRAMP_ORIGIN_PRIVATE_H
#define OFFRAMP_ORIGIN_PRIVATE_H
#include "quakedef.h"
struct offramp_origin_s
{
	int kind, leaf, rootleaf, depth;
	unsigned int contents;
	model_t *model;
};
extern qboolean offramp_origin_active;
extern struct offramp_origin_s offramp_origin_native, offramp_origin_pm;
extern const trace_t *offramp_origin_out;
void OfframpOrigin_Selftest(void);

static inline struct offramp_origin_s OfframpOrigin_Unknown(void)
{
	struct offramp_origin_s r;
	memset(&r, 0, sizeof(r));
	r.leaf = r.rootleaf = -1;
	return r;
}
static inline struct offramp_origin_s OfframpOrigin_Read(const trace_t *out)
{
	if (offramp_origin_active && offramp_origin_out == out)
		return offramp_origin_native;
	return OfframpOrigin_Unknown();
}
static inline void OfframpOrigin_Publish(const trace_t *out, struct offramp_origin_s r)
{
	if (offramp_origin_active)
	{
		offramp_origin_native = r;
		offramp_origin_out = out;
	}
}
#endif
