!!ver 130 150
!!permu FOG
!!samps milk=0
!!cvardf r_skyfog=0.5

// Patch 467 -- the visualizer as the map's sky (r_skybox milk; see
// scripts/milk.shader for why a script shader named skybox_milk is enough).
//
// Double stereographic mapping: each hemisphere projects from its own pole,
// so the zenith AND the nadir each sit at the centre of the milk image and the
// horizon lands on one ring (radius K) from both sides -- no seam, and no pole
// pinch.  Surf maps float in open sky, so the lower half matters as much as
// the upper.  One tap per sky pixel; the milk image itself is only rebuilt at
// the sim rate by CSQC (src/client/cl_milk.qc).

#include "sys/defs.h"
#include "sys/fog.h"

varying vec3 pos;

#ifdef VERTEX_SHADER
void main(void)
{
	pos = v_position.xyz;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
#define K 0.44              // horizon ring at uv radius K; milk_skygen.glsl's HOR = 2K
void main(void)
{
	vec3 d = normalize(pos - e_eyepos);
	vec2 uv = 0.5 + K * d.xy / (1.0 + abs(d.z));
	vec3 c = texture2D(s_milk, uv).rgb;

	// A thin haze on the horizon ring hides where the two projections meet.
	float hz = 1.0 - abs(d.z);
	c += vec3(0.05, 0.03, 0.10) * pow(hz, 10.0);

#ifdef FOG
	c = mix(c, w_fogcolour, float(r_skyfog) * w_fogalpha);
#endif
	gl_FragColor = vec4(c, 1.0);
}
#endif
