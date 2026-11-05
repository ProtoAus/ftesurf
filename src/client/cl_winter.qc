// P1302: static CC0 holiday props and bounded GPU mist, on explicit per-map manifests.
// Mist is an impostor, not volumetric simulation. No per-frame particles, traces,
// light queries, readbacks, depth captures or allocations. See tools/winter-assets.md.
#define WI_PROPS 16
#define WI_MIST 16
#define WI_VISIBLE_MIST 4
#define WI_AREA_BUDGET 0.12
entity wi_props[WI_PROPS], wi_mist[WI_MIST];
float wi_nprop, wi_nmist, wi_drawprop, wi_drawmist, wi_area;
string wi_map;
float wi_colin, wi_snowsteps;
entity wi_grass, wi_caps;
.float wi_radius;

float() Winter_ThemeActive =
{
	return (wi_colin && cvar("r_colin_winter") != 0);
};

string(string texture, float step) Winter_Footstep =
{
	local float pick;
	if (!Winter_ThemeActive() || wi_snowsteps <= 0) return "";
	if (strstrofs(strtolower(texture), "grass", 0) < 0) return "";
	if (wi_snowsteps == 6)
	{
		pick = 1 + 2 * floor(random() * 3) + (step & 1);
		return sprintf("player/footsteps/snow%g.wav", pick); // mounted CS:S
	}
	return sprintf("player/footsteps/snow/snow_%02.0f.wav", 1 + floor(random() * 12)); // Momentum fallback
};

vector() Weather_SnowTint;
.vector wi_source;

string(float kind) Winter_Model =
{
	if (kind == 1) return "models/christmas/snowman.iqm";
	if (kind == 2) return "models/christmas/snowman-hat.iqm";
	if (kind == 3) return "models/christmas/tree-decorated-snow.iqm";
	if (kind == 4) return "models/christmas/tree-snow-a.iqm";
	if (kind == 5) return "models/christmas/present-a-cube.iqm";
	if (kind == 6) return "models/christmas/present-b-rectangle.iqm";
	return "";
};

void() Winter_Init =
{
	registercvar("r_winter_props", "1", CVAR_ARCHIVE);
	registercvar("r_colin_winter", "1", CVAR_ARCHIVE); // authored single-map theme; no global cvar writes
	registercvar("r_mist", "0", CVAR_ARCHIVE); // opt-in until the moving-view budget is qualified
	registercommand("winter_info");
};

void() Winter_Clear =
{
	local float i;
	for (i = 0; i < WI_PROPS; i = i + 1)
	{
		if (wi_props[i])
		if (!strcmp(wi_props[i].classname, "winter_prop")) remove(wi_props[i]);
		wi_props[i] = world;
	}
	for (i = 0; i < WI_MIST; i = i + 1)
	{
		if (wi_mist[i])
		if (!strcmp(wi_mist[i].classname, "winter_mist")) remove(wi_mist[i]);
		wi_mist[i] = world;
	}
	if (wi_grass)
		if (!strcmp(wi_grass.classname, "winter_surface")) remove(wi_grass);
	if (wi_caps)
		if (!strcmp(wi_caps.classname, "winter_surface")) remove(wi_caps);
	wi_grass = wi_caps = world; wi_colin = wi_snowsteps = 0;
	wi_nprop = wi_nmist = wi_drawprop = wi_drawmist = wi_area = 0;
};

float(vector v) Winter_Finite =
{
	return (fabs(v_x) <= 262144 && fabs(v_y) <= 262144 && fabs(v_z) <= 262144);
};

entity(string group, string path, float zbase, float zrange) Winter_Surface =
{
	local entity e;
	local string grassflag, definition, albedo;
	if (strcmp(wi_map, "surf_colin_blaster_69000")) return world;
	if (strcmp(group, "grass") && strcmp(group, "caps")) return world;
	if (strcmp(path, sprintf("models/gibs/winterweather/%s-%s-lit.iqm", wi_map, group))) return world;
	if (!(fabs(zbase) <= 262144 && zrange >= 1 && zrange <= 524288)) return world;
	if (!Snow_Exists(path) || !Snow_Exists("glsl/ftesurf_snowcover_v3.glsl")) return world;
	grassflag = !strcmp(group, "grass") ? "#GRASS=1" : "";
	albedo = !strcmp(group, "grass") ? "materials/nature/snowfloor001a.vtf" : "materials/nature/snowfloor003a.vtf";
	definition = sprintf("{\ncull none\ndepthpush -2\nsort decal\n{\nprogram ftesurf_snowcover_v3#ZBASE=%.3f#ZRANGE=%.3f%s\nclampmap $nosrgb:$nearest:gfx/snowmask/%s.png\nmap %s\nrgbgen vertex\n}\n}\n", zbase, zrange, grassflag, wi_map, albedo);
	e = spawn(); e.classname = "winter_surface";
	// IQM precache registers its material. Never let its missing-name fallback win
	// the shader cache before the definition: use a distinct runtime name FIRST.
	e.forceshader = shaderforname(strcat("ftesurf_colin_snow_v3_", group), definition);
	precache_model(path); setmodel(e, path);
	e.effects = EF_NOSHADOW; e.colormod = '1 1 1'; e.scale = e.alpha = 1; // baked actual map light
	return e;
};

void() Winter_Load =
{
	local filestream f;
	local string line, mname, model, path;
	local float n, kind, radius, i, ok, traces, yaw;
	local vector pos, colour, source;
	local entity e;

	Winter_Clear();
	mname = serverkey("map");
	if (strcmp(wi_map, "")) strunzone(wi_map);
	wi_map = strzone(mname);
	// Only a basename, not a server-supplied path or a model name from the manifest.
	if (!mname || strlen(mname) > 64) return;
	for (i = 0; i < strlen(mname); i = i + 1)
	{
		n = str2chr(mname, i);
		if (!(n >= 48 && n <= 57) && !(n >= 65 && n <= 90) && !(n >= 97 && n <= 122) && n != 95 && n != 45) return;
	}
	f = fopen(sprintf("gfx/winter/%s.txt", mname), FILE_READ);
	if (f < 0) return;
	line = fgets(f);
	n = tokenize(line);
	ok = FALSE;
	if (n == 3)
	if (!strcmp(argv(0), "winter") && !strcmp(argv(1), "1") && !strcmp(argv(2), mname)) ok = TRUE;
	if (!ok) { fclose(f); return; }
	wi_colin = !strcmp(mname, "surf_colin_blaster_69000");
	// Missing media must not opt older clients into unclipped automatic snow.
	if (wi_colin)
		if (!Snow_Exists(sprintf("gfx/snowmask/%s.png", mname)) || !Snow_Exists(sprintf("gfx/snowmask/%s.txt", mname))) wi_colin = FALSE;
	if (wi_colin)
	{
		for (i = 1; i <= 6; i = i + 1)
		{
			path = sprintf("player/footsteps/snow%g.wav", i);
			if (Snow_Exists(strcat("sound/", path))) wi_snowsteps = wi_snowsteps + 1;
		}
		if (wi_snowsteps == 6)
		{
			for (i = 1; i <= 6; i = i + 1) precache_sound(sprintf("player/footsteps/snow%g.wav", i));
		}
		else
		{
			wi_snowsteps = 0;
			for (i = 1; i <= 12; i = i + 1)
			{
				path = sprintf("player/footsteps/snow/snow_%02.0f.wav", i);
				if (Snow_Exists(strcat("sound/", path))) wi_snowsteps = wi_snowsteps + 1;
			}
			if (wi_snowsteps == 12)
			{
				for (i = 1; i <= 12; i = i + 1) precache_sound(sprintf("player/footsteps/snow/snow_%02.0f.wav", i));
			}
			else wi_snowsteps = 0;
		}
	}
	// Fixed record AND trace caps bound bad local files. Missing assets skip, never error-art.
	traces = 0;
	for (i = 0; i < 128; i = i + 1)
	{
		if (traces >= WI_PROPS + WI_MIST) break;
		line = fgets(f);
		if (!line) break;
		n = tokenize(line);
		if (n < 1) continue;
		if (!strcmp(argv(0), "surface") && n == 5)
		{
			if (!strcmp(argv(1), "grass") && !wi_grass)
				wi_grass = Winter_Surface(argv(1), argv(2), stof(argv(3)), stof(argv(4)));
			if (!strcmp(argv(1), "caps") && !wi_caps)
				wi_caps = Winter_Surface(argv(1), argv(2), stof(argv(3)), stof(argv(4)));
		}
		else if (!strcmp(argv(0), "prop") && n == 7 && wi_nprop < WI_PROPS)
		{
			kind = stof(argv(1));
			model = Winter_Model(kind);
			pos = [stof(argv(2)), stof(argv(3)), stof(argv(4))];
			radius = stof(argv(6));
			yaw = stof(argv(5));
			if (!strcmp(model, "") || !Winter_Finite(pos)) continue;
			if (!(radius >= 0.25 && radius <= 2) || !(yaw >= -360 && yaw <= 360)) continue;
			if (!Snow_Exists(model)) continue;
			// Once at map load. Reject steep surf faces and missing/inside-solid floors.
			traces = traces + 1;
			traceline(pos + '0 0 64', pos - '0 0 320', TRUE, world);
			if (trace_startsolid || trace_fraction == 1 || trace_plane_normal_z < 0.9) continue;
			e = spawn();
			e.classname = "winter_prop";
			e.origin = trace_endpos + '0 0 0.25';
			e.angles = [0, yaw, 0];
			e.scale = radius;
			e.alpha = 1;
			e.colormod = '1 1 1';
			e.effects = EF_NOSHADOW;
			precache_model(model);
			setmodel(e, model);
			wi_props[wi_nprop] = e;
			wi_nprop = wi_nprop + 1;
		}
		else if (!strcmp(argv(0), "mist") && n == 11 && wi_nmist < WI_MIST)
		{
			pos = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
			radius = stof(argv(4));
			colour = [stof(argv(5)), stof(argv(6)), stof(argv(7))];
			source = [stof(argv(8)), stof(argv(9)), stof(argv(10))];
			if (!Winter_Finite(pos) || !Winter_Finite(source) || !Winter_Finite(colour)) continue;
			colour = [bound(0.1, colour_x, 1), bound(0.1, colour_y, 1), bound(0.1, colour_z, 1)];
			if (!(radius >= 24 && radius <= 64)) continue;
			if (!Snow_Exists("models/christmas/mist.iqm")) continue;
			e = spawn();
			e.classname = "winter_mist";
			e.wi_source = source;
			// Once: do not put the wisp's centre through a wall from its authored light.
			traces = traces + 1;
			traceline(source, pos, TRUE, world);
			if (trace_startsolid || trace_fraction < 1) { remove(e); continue; }
			e.origin = pos;
			e.scale = e.wi_radius = radius;
			e.colormod = colour;
			e.alpha = 1;
			e.effects = EF_NOSHADOW;
			precache_model("models/christmas/mist.iqm");
			setmodel(e, "models/christmas/mist.iqm");
			wi_mist[wi_nmist] = e;
			wi_nmist = wi_nmist + 1;
		}
	}
	fclose(f);
	// Load/compile the tiny material at map setup, not on the first mid-run toggle.
	if (wi_nmist > 0) shaderforname("ftesurf_mist");
	print(sprintf("winter: %s, %g props, %g mist fields, %g setup traces (4 visible, area budget 0.12)\n", wi_map, wi_nprop, wi_nmist, traces));
};

// After addentities / final VF_ORIGIN, before renderscene. Native depth testing
// and frustum culling still apply; these conservative CPU caps are additional.
void() Winter_Frame =
{
	local vector eye, d, forward;
	local float i, dist, score, share;
	local entity e;
	if (strcmp(wi_map, serverkey("map"))) Winter_Load();
	wi_drawprop = wi_drawmist = wi_area = 0;
	if (Winter_ThemeActive())
	{
		if (wi_grass) { wi_grass.colormod = Weather_SnowTint(); addentity(wi_grass); }
		if (wi_caps) { wi_caps.colormod = Weather_SnowTint(); addentity(wi_caps); }
	}
	if (!wi_nprop && !wi_nmist) return;
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	forward = v_forward;
	if (cvar("r_winter_props") > 0 || Winter_ThemeActive())
	for (i = 0; i < wi_nprop; i = i + 1)
	{
		e = wi_props[i];
		d = e.origin - eye;
		if (vlen(d) > 2600 || d * forward < -192) continue;
		addentity(e);
		wi_drawprop = wi_drawprop + 1;
	}
	if (cvar("r_mist") <= 0)
		if (!Winter_ThemeActive()) return;
	for (i = 0; i < wi_nmist; i = i + 1)
	{
		if (wi_drawmist >= WI_VISIBLE_MIST) break;
		e = wi_mist[i];
		d = e.origin - eye;
		dist = vlen(d);
		if (dist > 1100 || d * forward < -e.wi_radius) continue;
		// Allocate a continuous projected-size share instead of dropping an
		// entire field at192/277 units. Each of4 fields retains its own share;
		// approaching one cannot abruptly evict the next light's mist.
		score = 4 * (e.wi_radius / max(32, dist)) * (e.wi_radius / max(32, dist));
		share = min(score, WI_AREA_BUDGET / WI_VISIBLE_MIST);
		e.scale = e.wi_radius * sqrt(share / max(0.000001, score));
		e.alpha = 1;
		wi_area = wi_area + share;
		addentity(e);
		wi_drawmist = wi_drawmist + 1;
	}
};

float(string command) Winter_ConsoleCommand =
{
	if (strcmp(command, "winter_info")) return FALSE;
	print(sprintf("winter: %s loaded props %g mist %g; submitted props %g mist %g area %.4f\n", wi_map, wi_nprop, wi_nmist, wi_drawprop, wi_drawmist, wi_area));
	print(sprintf("winter: Colin theme %g grass %g caps %g mounted snow footsteps %g (6 CSS / 12 Momentum); r_colin_winter 0 disables automatic extras\n", Winter_ThemeActive(), wi_grass != world, wi_caps != world, wi_snowsteps));
	return TRUE;
};
