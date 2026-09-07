// FTESurf Build 40 -- the x-ray material for the timer-zone overlay.
//
// WHY THIS FILE EXISTS AT ALL.
//
// cl_zones.qc draws every zone edge with R_BeginPolygon(""), and an EMPTY
// shader name resolves to the engine's built-in shader_draw_fill_trans
// (pr_csqc.c:1602-1607, defined at r_2d.c:328-338).  That material has no
// nodepthtest, and Zone_Draw is called before renderscene() precisely so the
// world's depth buffer occludes it -- which is correct, and is the default this
// file does NOT change.  It is only reached when zone_xray is set.
//
// THE ROUTE.  For a 3D polygon the builtin calls
//
//     R_RegisterCustom(NULL, shadername, 0, Shader_PolygonShader, NULL)
//
// and R_LoadShader tries Shader_ParseShader against the loaded .shader scripts
// BEFORE it ever runs that generator (gl_shader.c:8552-8565).  So naming a
// shader here is enough; no engine change, and no new builtin.  portal.shader
// beside this one is the same mechanism applied to a model surface.
//
// WHAT THE BODY IS.  shader_draw_fill_trans, verbatim, plus two keywords:
//
//   nodepthtest   a PASS keyword (Shaderpass_NoDepthTest, gl_shader.c:4763),
//                 which is how shader_contrastup spells the same thing at
//                 r_2d.c:339-351.  Without it there is no x-ray.
//   sort banner   without a sort the batch keeps its ordinary place in the
//                 list, so "no depth test" would only mean "drawn over
//                 whatever happened to be submitted earlier" -- correct for
//                 some walls and not others, which is worse than either.
//                 banner is the sort BEF_FORCENODEPTH itself promotes to
//                 (gl_alias.c:3217), so this matches what the engine would do.
//
// rgbgen/alphagen vertex are NOT optional: R_PolygonVertex carries the zone's
// colour and zone_alpha per vertex and there is no other channel for them.
// Drop either and every zone turns white.
//
// KNOWN AND ACCEPTED: with no depth test, two overlapping zones resolve by
// submission order, i.e. by index in the zone table.  On the maps where a main
// start and a bonus start are byte-identical (sv_zones.qc) that will look like
// z-fighting even though nothing is fighting.  zone_xray 0 is the answer, and
// is the default.

ftesurf_zone_xray
{
	sort banner
	program defaultfill
	{
		nodepthtest
		map $whiteimage
		rgbgen vertex
		alphagen vertex
		blendfunc blend
		maskalpha
	}
}
