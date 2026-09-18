!!ver 110
!!fixed

// FTESurf Patch 331 -- ordered-dither fill for debug geometry: the hovered
// brush entity's faces and r_showbrushes' hulls.
//
// WHY A DITHER AND NOT A BLEND, again.  The hl2 plugin's water dither
// (plugins/hl2/glsl/vmt/flatdither.glsl, Patch 151) established the argument
// for surfaces; it holds double for a DEBUG overlay.  A blended translucent
// polygon needs a sort position, and these polygons are drawn into the same
// scene as the world they intersect: a trigger face coplanar with a wall, a
// swept hull hanging inside the floor, forty overlapping brush faces from one
// hull.  Blended, every one of those is a sort tie the viewer can see as a
// flash.  An ordered dither is opaque geometry with a discard: no blend, no
// sort, depth written, and the coverage is exactly the alpha the vertex
// colour asked for, in 1/16 steps.
//
// THE COLOUR AND THE COVERAGE ARE THE VERTEX COLOUR.  rgbgen vertex and the
// default alphagen (ALPHA_GEN_VERTEX, gl_shader.c:4202) put both in v_colour,
// so one program serves every caller: the engine's hull walker picks the
// per-contents palette and a 6/16 coverage, the hover highlight picks its own,
// and neither needs a shader permutation or a uniform of its own.  `!!fixed`
// is load-bearing exactly as flatdither's essay says: without it
// GenerateColourMods never runs and v_colour is whatever the previous draw
// left bound.
//
// SCREEN-SPACE BAYER, not surface UV: a dither locked to geometry swims and
// moires as you move; gl_FragCoord stands still on the screen, which is what
// reads as a stipple.  Same 4x4 recursion as flatdither, copied rather than
// shared because the plugin's program samples a base texture and applies fog
// and this one must do neither: a debug fill that fogged itself would fade out
// at exactly the distances you turn it on for, and fogging a see-through
// overlay to the fog colour is a contradiction.
//
// NO FOG, NO LIGHT: includes are limited to sys/defs.h.  The vertex shader is
// ftetransform() and nothing else, so the fill costs one varying and a
// discard, which is the whole budget a per-frame debug view deserves.

#include "sys/defs.h"

varying vec4 vc;

#ifdef VERTEX_SHADER
void main ()
{
	vc = v_colour;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER

// The 2x2 Bayer cell, [[0,2],[3,1]], as arithmetic: GLSL 1.10 does not
// guarantee dynamic array indexing in a fragment shader.
float b2 (float x, float y)
{
	return mod(2.0*x + 3.0*y, 4.0);
}

// The standard 4x4 from the recursion M2n = [[4Mn, 4Mn+2],[4Mn+3, 4Mn+1]],
// returned as a threshold in (0,1).
float bayer4 (vec2 p)
{
	float lo = b2(mod(p.x, 2.0), mod(p.y, 2.0));
	float hi = b2(mod(floor(p.x*0.5), 2.0), mod(floor(p.y*0.5), 2.0));
	return (4.0*lo + hi + 0.5) * (1.0/16.0);
}

void main ()
{
	if (vc.a < bayer4(gl_FragCoord.xy))
		discard;

	gl_FragColor = vec4(vc.rgb, 1.0);
}
#endif
