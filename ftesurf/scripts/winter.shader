// P1302: namespaced CC0 holiday palette, ordinary lit static models.
models/christmas/holiday
{
	{
		map models/christmas/palette.png
		rgbgen lightingdiffuse
	}
}

ftesurf_mist
{
	sort blend
	cull disable
	{
		program ftesurf_mist
		map $nosrgb:models/christmas/mist-noise.png
		blendfunc blend
		rgbgen entity
		alphagen entity
	}
}
