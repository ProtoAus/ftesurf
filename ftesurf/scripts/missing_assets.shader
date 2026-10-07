// Impact ERROR mesh: opaque red faces, darker extrusion, small additive halo.
// Vertex UVs select constant palette texels; this works with GPU alias drawing
// without relying on rgbgen const being uploaded as an alias color array.
// No lighting, Source plugin, dynamic light or post-process bloom required.
missing_error_face
{
	cull none
	nomipmaps
	{
		program default2d
		clampmap gfx/env/missing_error_palette.png
		rgbgen identity
		depthwrite
	}
}
missing_error_side
{
	cull none
	nomipmaps
	{
		program default2d
		clampmap gfx/env/missing_error_palette.png
		rgbgen identity
		depthwrite
	}
}
missing_error_halo
{
	sort additive
	cull none
	nomipmaps
	{
		program default2d
		clampmap gfx/env/missing_error_palette.png
		rgbgen identity
		blendfunc add
	}
}
