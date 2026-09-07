// FTESurf Patch 210 -- the shader for the linked_portal_door aperture.
//
// THE APERTURE NOW PAINTS ITSELF, and that is the whole point of this rewrite.
//
// Patch 207 shipped this material with ZERO PASSES, which was correct for the
// design it belonged to: a SHADER_SORT_PORTAL surface was not drawn at all.  The
// engine rendered the far side of the portal over the WHOLE SCREEN
// (gl_backend.c, GLBE_SubmitMeshesPortals) and then submitted the same batch
// again in BEM_DEPTHONLY as a depth mask, trusting the ordinary world to repaint
// everywhere the doorway was not.  Where that repaint did not happen, the far
// room covered the wall -- and Patch 208's answer, a scissor to the aperture's
// projected BOUNDING RECTANGLE, is the "square box, and not the size of the
// doorway" that is still visible.  A rectangle is the best a scissor can do.
//
// So stop scissoring and stop masking.  `portalfbo` (Patch 210) sets
// SHADER_HASPORTAL, which routes this batch through GLBE_GenerateBatchTextures:
// the far view is rendered into a texture, and the pass below paints that
// texture onto the doorway quad from the ordinary sort list.  Confinement is now
// the POLYGON, per pixel.  The rectangle, the corner leak at a yawed door, and
// the whole repaint race stop being possible rather than being made unlikely.
//
// `portal` STAYS, even though the surface is now drawn like any other opaque
// one.  It is not decoration: SHADER_SORT_PORTAL is what puts this batch in
// front of GLR_PortalBudgetBegin, which is where Patch 206's r_portalmaxviews
// cap and the void gate live, and it is also what makes the shader
// SHADER_NEEDSARRAYS so the vertex data survives to be measured
// (gl_shader.c: "q3-style portals (needed for pvs info)").  Losing it would
// silently restore the unbounded cost that surf_tripportals' 116 doors proved.
// GLBE_SubmitMeshesPortals skips SHADER_HASPORTAL batches in both of its loops,
// so the sort no longer costs a second scene render or a stale depth mask.
//
// portalfboscale 1 is deliberate.  Without it the texture inherits
// r_refractreflect_scale, which defaults to 0.5 -- fine for water, where the
// image is about to be distorted by a normalmap anyway, and visibly soft for a
// doorway you can walk up to and put your face against.  Drop it to 0.5 if a map
// with many simultaneous doors needs the fill rate back; the result stays
// correctly SHAPED either way, only softer.
//
// map $refraction is what sets SHADER_HASREFRACT, and SHADER_HASPORTAL is
// documented in shader.h as requiring that pairing -- the portal branch in
// GLBE_GenerateBatchTextures is reached only through the refract test.  For a
// portal material the engine fills it with the view through the link rather than
// with a refraction; ftesurf_portal.glsl explains why the lookup is screen-space
// and must not be a UV lookup.
//
// cull none because a linked_portal_door is enterable from both faces and the
// .obj loader reverses triangle winding depending on mod_obj_orientation
// (com_mesh.c).  The front face is not a fixed thing, so neither side may be
// discarded.  This is now cheaper than it was: with no depth mask, a door you
// are standing behind can no longer mask anything, which was Patch 206's
// transparent square.  GLR_DrawPortal still refuses to render a view from behind
// the plane, and a refusal here simply means the surface is not drawn.
//
// POLYGONOFFSET IS STILL GONE, AND ITS REMOVAL IS STILL A BUG FIX.  Patch 205
// added it against z-fighting that cannot happen -- a linked_portal_door stands
// in a doorway OPENING, with no coplanar brush to fight.  Bare `polygonoffset`
// resolves to unit -25, factor -0.05 (gl_shader.c), applied in every backend
// mode including BEM_DEPTHONLY, so the mask was written twenty-five depth units
// toward the camera and at a grazing angle that kill volume was far larger than
// the aperture itself.  There is no mask any more, but an opaque surface biased
// toward the viewer would still punch through the door frame.
//
// TO GET THE OLD RENDERER BACK: r_portalfbo 0, then vid_reload.  The cvar is
// read here, at parse time; 0 makes `portalfbo` set SHADER_NODRAW instead, which
// suppresses the pass below and leaves this material behaving exactly like the
// zero-pass Patch 207 one -- recursed in place and masked off, bounded by
// r_portalscissor.  That arm is kept because the two designs fail differently
// and it is the only way to see the original symptom again.

ftesurf_portal
{
	portal
	portalfbo
	portalfboscale 1
	cull none
	{
		program ftesurf_portal
		map $refraction
		depthwrite
	}
}
