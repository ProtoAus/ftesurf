// FTESurf P1286: the snow event's falling snow. One entity on the eye draws models/snow/flakes.iqm
// (tools/snowflakes.py); glsl/ftesurf_snow.glsl moves every flake, so the CPU cost is this entity.
// r_snow 0 off, 1 on the event's maps (r_snow_maps), 2 on every map. A map with a sky mask
// (tools/snowmask.py: gfx/snowmask/<map>.txt + gfx/snowmask/<map>.png, P1293) keeps the flakes out
// from under its roofs; r_snow_indoor 1 ignores the mask (snow everywhere, e.g. a map with no sky).
// r_snow_debug 1 colours each flake by the mask height it read and hides none.

float() Winter_ThemeActive; // later winter module: cached, map-specific opt-out
entity snow_ent;
string snow_map;
string snow_shader;         // "" while the map has no mask
string snow_maskz;          // the mask's "z0 zrange 1" for the shader
float  snow_maskon;         // what r_snow_maskz says now: -1 unknown, 0 off, 1 on
float  snow_have;           // 0 unknown, 1 the flake model is installed, -1 not (an older install on a lobby)

void() Snow_Init =
{
	registercvar("r_snow", "1", CVAR_ARCHIVE);
	registercvar("r_snow_maps", "surf_christmas surf_christmas2 surf_christmas3 surf_frost surf_bluewinter surf_iceworld");
	registercvar("r_snow_indoor", "0");
	registercvar("r_snow_range", "1024");           // half the box's width; the box is half as tall
	registercvar("r_snow_speed", "70");
	registercvar("r_snow_size", "3");
	registercvar("r_snow_density", "1");            // the share of the 64000 flakes drawn
	registercvar("r_snow_alpha", "0.85");
	registercvar("r_snow_sway", "18");
	registercvar("r_snow_wind", "6 4 0");
	registercvar("r_snow_colour", "0.95 0.97 1");
	registercvar("r_snow_maskxy", "0 0 0");         // x0 y0 cell, set here per map, read by the shader
	registercvar("r_snow_maskz", "0 0 0");
	registercvar("r_snow_debug", "0");
	snow_maskon = -1;
};

// list holds word as a whole word
float(string list, string word) Snow_InList =
{
	return strstrofs(strcat(" ", list, " "), strcat(" ", word, " ")) >= 0;
};

float(string path) Snow_Exists =
{
	local float fh;
	fh = fopen(path, FILE_READ);
	if (fh < 0)
		return FALSE;
	fclose(fh);
	return TRUE;
};

// The map's own copy of scripts/snow.shader's block, its mask bound. Again after a renderer restart.
void() Snow_MakeShader =
{
	shaderforname(snow_shader, sprintf("{\nsort additive\ncull disable\nnomipmaps\nnopicmip\n{\nprogram ftesurf_snow\nclampmap $nosrgb:$nearest:gfx/snowmask/%s.png\nblendfunc blend\nrgbgen const 1 1 1\n}\n}\n", snow_map));
};

void() Snow_Load =
{
	local float fh, n;
	local string line;

	if (snow_map != "")
		strunzone(snow_map);
	snow_map = strzone(serverkey("map"));
	if (snow_shader != "")
		strunzone(snow_shader);
	snow_shader = "";
	snow_maskon = -1;
	// "snowmask 1 <map> x0 y0 cell width height z0 zrange"; no PNG, no mask (a missing image reads as roofs)
	fh = fopen(sprintf("gfx/snowmask/%s.txt", snow_map), FILE_READ);
	if (fh >= 0)
	{
		line = fgets(fh);
		fclose(fh);
		n = tokenize(line);
		if (n >= 10 && argv(0) == "snowmask" && stof(argv(1)) == 1 && Snow_Exists(sprintf("gfx/snowmask/%s.png", snow_map)))
		{
			cvar_set("r_snow_maskxy", sprintf("%s %s %s", argv(3), argv(4), argv(5)));
			if (snow_maskz != "")
				strunzone(snow_maskz);
			snow_maskz = strzone(sprintf("%s %s 1", argv(8), argv(9)));
			snow_shader = strzone(sprintf("ftesurf_snow/%s", snow_map));
			Snow_MakeShader();
		}
	}
	print(sprintf("snow: %s, mask %s\n", snow_map, (snow_shader != "") ? "yes" : "none"));
};

// CSQC_RendererRestarted: vid_restart frees every shader, so the handle in .forceshader names another.
void() Snow_Lost =
{
	if (snow_shader != "")
		Snow_MakeShader();
	snow_maskon = -1;
};

// Before renderscene, beside RampWear_Frame. Added here, after the move: addentities has already run
// (cl_main.qc), and an entity it drew would carry last frame's eye.
void() Snow_Frame =
{
	local float want, mask;

	if (serverkey("map") != snow_map)
		Snow_Load();
	want = cvar("r_snow");
	want = ((want >= 2) || (want >= 1 && Snow_InList(cvar_string("r_snow_maps"), snow_map)) || Winter_ThemeActive());   // = binds tighter than ||
	if (!want)
		return;
	if (!snow_have)
	{
		snow_have = Snow_Exists("models/snow/flakes.iqm") ? 1 : -1;
		if (snow_have < 0)
			print("snow: models/snow/flakes.iqm is not installed; no snow\n");
	}
	if (snow_have < 0)
		return;
	if (!snow_ent)
	{
		precache_model("models/snow/flakes.iqm");
		snow_ent = spawn();
		snow_ent.classname = "snow";
		setmodel(snow_ent, "models/snow/flakes.iqm");
		snow_ent.effects = EF_NOSHADOW;
	}
	mask = (snow_shader != "" && !cvar("r_snow_indoor"));
	if (mask != snow_maskon)
	{
		snow_maskon = mask;
		cvar_set("r_snow_maskz", mask ? snow_maskz : "0 0 0");
		snow_ent.forceshader = mask ? shaderforname(snow_shader) : 0;
	}
	setorigin(snow_ent, getproperty(VF_ORIGIN));
	addentity(snow_ent);
};
