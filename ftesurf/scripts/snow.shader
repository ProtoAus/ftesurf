// FTESurf P1286: the snow event's flakes (models/christmas/flakes.iqm names this material; a surface whose
// material resolves to no shader is dropped before .forceshader is read). No sky mask here: cl_snow.qc
// gives a map with a baked mask its own copy (ftesurf_snow/<map>) through .forceshader.
ftesurf_snow
{
	sort additive
	cull disable
	nomipmaps
	nopicmip
	{
		program ftesurf_snow
		map $blackimage
		blendfunc blend
		rgbgen const 1 1 1
	}
}
