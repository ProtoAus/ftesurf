// Patch 467 -- the milk visualizer's fixed materials.  The per-pass ones
// (scene, warp, bloom, composite) are built at runtime by src/milk_sys.qc with
// shaderforname, because their names carry the pipeline prefix and the
// ping-pong parity.
//
// THE SKY.  `r_skybox milk` makes R_SetSky (gl_warp.c:133) load gfx/env/milk.png
// -- a 2x1 placeholder whose only job is to exist, because that is the branch
// that registers the shader `skybox_milk` -- and R_LoadShader reads the shader
// scripts BEFORE it falls back to the generated text (gl_shader.c:8710-8723),
// so this definition wins.  The sky surfaces are then submitted with this
// program (R_DrawSkyChain's forcedsky branch, gl_warp.c:612-630).  No engine
// change is involved.  The depthwrite block is the default sky's own.
skybox_milk
{
	sort sky
	surfaceparm nodlight
	surfaceparm sky
	{
		program milk_sky
		if !$unmaskedsky
			depthwrite
		endif
		map $rt:ms_out
	}
}

// Soft additive sprites drawn into the feedback frame (glsl/milk_dot.glsl).
milk_dot
{
	{
		program milk_dot
		blendfunc add
		map $whiteimage
	}
}

milk_bar
{
	{
		program milk_dot#BAR
		blendfunc add
		map $whiteimage
	}
}

// The menu's readability gradient: one quad, alpha per vertex.
milk_shade
{
	{
		program milk_dot#FLAT
		blendfunc blend
		map $whiteimage
	}
}

// The MUSIC screen's analyser.  milk_spec is a render target milk_sys.qc
// configures (and the engine fills), so this is only drawn once it exists.
milk_specview
{
	{
		program milk_specview
		blendfunc blend
		map $rt:milk_spec
	}
}
