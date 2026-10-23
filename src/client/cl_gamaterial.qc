/* Mounted Source material -> surface profile -> left/right footstep WAVs.
 * Bounded, cached, render/audio-only. Loaded lazily; refresh owns invalidation. */
#define GM_PROPS 256i
#define GM_SOUNDS 256i
#define GM_MATS 32i
#define GM_FIELDS 7i
string *gm_props;
string *gm_sounds;
string *gm_mats;
int gm_propn, gm_soundn, gm_matn, gm_cursor, gm_reads, gm_hits;
float gm_loaded, gm_css, gm_contactface, gm_contactmodel;
entity gm_contactent;
int gm_surfacescans;
// Existing named FTE search APIs; keep scoped file reads out of generated defs.
string(searchhandle handle, float num) GM_SearchPackage = #0:search_getpackagename;
filestream(searchhandle handle, float num) GM_SearchOpen = #0:search_fopen;
string gm_lasttex, gm_lastprop, gm_lastsource;
// Existing EXT_CSQC trace output; unlike trace_ent it also names world hull hits.
string trace_surfacename;

void(string *table, int at, string value) GM_Put =
{
	if (strcmp(table[at], "")) strunzone(table[at]);
	table[at] = strcmp(value, "") ? strzone(value) : "";
};

void() GM_Clear =
{
	local int i;
	if (gm_props)
	{
		for (i = 0i; i < GM_PROPS * 4i; i += 1i)
			if (strcmp(gm_props[i], "")) strunzone(gm_props[i]);
		memfree(gm_props);
	}
	if (gm_sounds)
	{
		for (i = 0i; i < GM_SOUNDS * 5i; i += 1i)
			if (strcmp(gm_sounds[i], "")) strunzone(gm_sounds[i]);
		memfree(gm_sounds);
	}
	if (gm_mats)
	{
		for (i = 0i; i < GM_MATS * GM_FIELDS; i += 1i)
			if (strcmp(gm_mats[i], "")) strunzone(gm_mats[i]);
		memfree(gm_mats);
	}
	gm_props = 0; gm_sounds = 0; gm_mats = 0;
	gm_propn = 0i; gm_soundn = 0i; gm_matn = 0i; gm_cursor = 0i;
	gm_reads = 0i; gm_hits = 0i; gm_loaded = FALSE; gm_css = FALSE;
	gm_contactface = -1; gm_contactmodel = 0; gm_contactent = world;
	gm_surfacescans = 0i;
	gm_lasttex = ""; gm_lastprop = ""; gm_lastsource = "";
};

string(string path) GM_Path =
{
	path = strtolower(strreplace("\\", "/", path));
	if (strlen(path) > 200 || strstrofs(path, "..", 0) >= 0 || strstrofs(path, ":", 0) >= 0) return "";
	if (!strcmp(substring(path, 0, 1), "/")) return "";
	return path;
};

int(string name, float create) GM_PropSlot =
{
	local int i;
	for (i = 0i; i < gm_propn; i += 1i)
		if (!strcmp(gm_props[i * 4i], name)) return i;
	if (!create || gm_propn >= GM_PROPS || !strcmp(name, "")) return -1i;
	i = gm_propn; gm_propn += 1i;
	GM_Put(gm_props, i * 4i, name);
	return i;
};

int(string name, float create) GM_SoundSlot =
{
	local int i;
	for (i = 0i; i < gm_soundn; i += 1i)
		if (!strcmp(gm_sounds[i * 5i], name)) return i;
	if (!create || gm_soundn >= GM_SOUNDS || !strcmp(name, "")) return -1i;
	i = gm_soundn; gm_soundn += 1i;
	GM_Put(gm_sounds, i * 5i, name);
	return i;
};

string(string path) GM_Wave =
{
	while (strstrofs("*#@)><^", substring(path, 0, 1), 0) >= 0 && strlen(path) > 0)
		path = substring(path, 1, -1);
	path = GM_Path(path);
	if (!strcmp(substring(path, 0, 6), "sound/")) path = substring(path, 6, -1);
	return path;
};

// mode0: merge property scalars; mode1: only WAVs for already referenced aliases.
void(float f, float mode) GM_LoadFile =
{
	local int i, n, depth, slot, field, wave, bytes;
	local string line, tok, name, key, value;
	depth = 0i; slot = -1i; field = 0i; wave = 0i; bytes = 0i;
	name = ""; key = "";
	while ((line = fgets(f)))
	{
		bytes += (int)strlen(line);
		if (bytes > 196608i) break;
		n = (int)tokenize_console(line);
		for (i = 0i; i < n; i += 1i)
		{
			tok = argv(i);
			if (!strcmp(tok, "{"))
			{
				depth += 1i; field = 0i;
				if (depth == 1i)
				{
					if (mode)
					{
						slot = GM_SoundSlot(name, FALSE);
						if (slot >= 0i)
						for (wave = 0i; wave < 4i; wave += 1i)
							GM_Put(gm_sounds, slot * 5i + 1i + wave, "");
					}
					else slot = GM_PropSlot(name, TRUE);
					wave = 0i;
				}
				continue;
			}
			if (!strcmp(tok, "}"))
			{
				depth -= 1i; field = 0i;
				if (depth <= 0i) { depth = 0i; slot = -1i; }
				continue;
			}
			if (depth == 0i)
			{
				if (strcmp(name, "")) strunzone(name);
				name = strzone(strtolower(tok));
				continue;
			}
			if (slot < 0i) continue;
			if (mode)
			{
				if (field)
				{
					value = GM_Wave(tok);
					if (wave < 4i && strcmp(value, ""))
					{
						GM_Put(gm_sounds, slot * 5i + 1i + wave, value);
						wave += 1i;
					}
					field = 0i;
				}
				else if (!strcmp(strtolower(tok), "wave")) field = 1i;
			}
			else if (depth == 1i)
			{
				if (field)
				{
					if (!strcmp(key, "base")) GM_Put(gm_props, slot * 4i + 1i, strtolower(tok));
					if (!strcmp(key, "stepleft")) GM_Put(gm_props, slot * 4i + 2i, strtolower(tok));
					if (!strcmp(key, "stepright")) GM_Put(gm_props, slot * 4i + 3i, strtolower(tok));
					field = 0i;
				}
				else
				{
					if (strcmp(key, "")) strunzone(key);
					key = strzone(strtolower(tok)); field = 1i;
				}
			}
		}
	}
	if (strcmp(name, "")) strunzone(name);
	if (strcmp(key, "")) strunzone(key);
	fclose(f);
};

void(string path, float mode) GM_LoadScript =
{
	local float f;
	gm_reads += 1i;
	f = fopen(path, FILE_READ);
	if (f >= 0) GM_LoadFile(f, mode);
};

// CSS foot aliases must not inherit Momentum's different sample set by VFS order.
void() GM_LoadCSS =
{
	local float h, i, n, f;
	local string package;
	if (!checkbuiltin(GM_SearchPackage)) return;
	if (!checkbuiltin(GM_SearchOpen)) return;
	h = search_begin("scripts/game_sounds_physics.txt", 6, TRUE); // full package paths + duplicates; no inactive-package force
	if (h < 0) return;
	n = bound(0, search_getsize(h), 64);
	for (i = 0; i < n; i += 1)
	{
		package = strtolower(GM_SearchPackage(h, i));
		if (strstrofs(package, "cstrike", 0) < 0) continue;
		gm_reads += 1i;
		f = GM_SearchOpen(h, i);
		if (f < 0) continue;
		GM_LoadFile(f, TRUE);
		gm_css = TRUE;
		break;
	}
	search_end(h);
};

// Follow the selected game's manifest: Momentum separates footsteps from physics.
void() GM_LoadSounds =
{
	local float f;
	local int i, n, count, bytes;
	local string *files;
	local string line, key, path;
	files = memalloc(sizeof(string) * 16i);
	count = 0i; bytes = 0i;
	gm_reads += 1i;
	f = fopen("scripts/game_sounds_manifest.txt", FILE_READ);
	if (f >= 0)
	{
		while ((line = fgets(f)))
		{
			bytes += (int)strlen(line);
			if (bytes > 32768i) break;
			n = (int)tokenize_console(line);
			for (i = 0i; i + 1i < n; i += 1i)
			{
				key = strtolower(argv(i));
				if (strcmp(key, "precache_file") && strcmp(key, "preload_file")) continue;
				path = GM_Path(argv(i + 1i));
				if (strcmp(substring(path, 0, 8), "scripts/")) continue;
				if (strstrofs(path, "player", 0) < 0 && strstrofs(path, "foot", 0) < 0
				    && strstrofs(path, "physics", 0) < 0 && strstrofs(path, "surface", 0) < 0) continue;
				if (count >= 16i) break;
				files[count] = strzone(path); count += 1i;
			}
		}
		fclose(f);
	}
	if (!count)
	{
		files[0i] = strzone("scripts/game_sounds_player.txt");
		files[1i] = strzone("scripts/game_sounds_physics.txt"); count = 2i;
	}
	for (i = 0i; i < count; i += 1i)
	{
		GM_LoadScript(files[i], TRUE);
		strunzone(files[i]);
	}
	memfree(files);
};

void() GM_Load =
{
	local float f;
	local int i, j, n, count, bytes;
	local string *files;
	local string line, path;
	if (gm_loaded) return;
	gm_loaded = TRUE;
	gm_props = memalloc(sizeof(string) * GM_PROPS * 4i);
	gm_sounds = memalloc(sizeof(string) * GM_SOUNDS * 5i);
	gm_mats = memalloc(sizeof(string) * GM_MATS * GM_FIELDS);
	files = memalloc(sizeof(string) * 16i);
	count = 0i; bytes = 0i;
	gm_reads += 1i;
	f = fopen("scripts/surfaceproperties_manifest.txt", FILE_READ);
	if (f >= 0)
	{
		while ((line = fgets(f)))
		{
			bytes += (int)strlen(line);
			if (bytes > 16384i) break;
			n = (int)tokenize_console(line);
			for (i = 0i; i + 1i < n; i += 1i)
			if (!strcmp(strtolower(argv(i)), "file") && count < 16i)
			{
				path = GM_Path(argv(i + 1i));
				if (!strcmp(substring(path, 0, 8), "scripts/"))
				{
					files[count] = strzone(path); count += 1i;
				}
			}
		}
		fclose(f);
	}
	if (!count)
	{
		files[0i] = strzone("scripts/surfaceproperties.txt");
		files[1i] = strzone("scripts/surfaceproperties_cs.txt"); count = 2i;
	}
	for (i = 0i; i < count; i += 1i)
	{
		GM_LoadScript(files[i], FALSE);
		strunzone(files[i]);
	}
	memfree(files);
	for (i = 0i; i < gm_propn; i += 1i)
	for (j = 2i; j <= 3i; j += 1i)
		GM_SoundSlot(gm_props[i * 4i + j], TRUE);
	GM_LoadSounds();
	GM_LoadCSS();
};

// Returned nonempty property is zoned; recursion follows only safe material paths.
string(string texture, float depth) GM_Property =
{
	local float f;
	local int i, n, want, bytes;
	local string path, line, tok, prop, parent;
	if (depth >= 4) return "";
	path = GM_Path(texture);
	if (!strcmp(path, "")) return "";
	if (strcmp(substring(path, 0, 10), "materials/")) path = strcat("materials/", path);
	if (strcmp(substring(path, -4, 4), ".vmt")) path = strcat(path, ".vmt");
	gm_reads += 1i;
	f = fopen(path, FILE_READ);
	if (f < 0) return "";
	want = 0i; bytes = 0i; prop = ""; parent = "";
	while ((line = fgets(f)))
	{
		bytes += (int)strlen(line);
		if (bytes > 32768i) break;
		n = (int)tokenize_console(line);
		for (i = 0i; i < n; i += 1i)
		{
			tok = argv(i);
			if (!strcmp(tok, "{") || !strcmp(tok, "}")) { want = 0i; continue; }
			if (want == 1i)
			{
				if (strcmp(prop, "")) strunzone(prop);
				prop = strzone(strtolower(tok)); want = 0i;
			}
			else if (want == 2i)
			{
				if (strcmp(parent, "")) strunzone(parent);
				parent = strzone(tok); want = 0i;
			}
			else if (!strcmp(strtolower(tok), "$surfaceprop")) want = 1i;
			else if (!strcmp(strtolower(tok), "include")) want = 2i;
		}
	}
	fclose(f);
	if (!strcmp(prop, "") && strcmp(parent, "")) prop = GM_Property(parent, depth + 1);
	if (strcmp(parent, "")) strunzone(parent);
	return prop;
};

string(string texture) GM_Guess =
{
	texture = strtolower(texture);
	if (strstrofs(texture, "grate", 0) >= 0) return "metalgrate";
	if (strstrofs(texture, "chain", 0) >= 0) return "chainlink";
	if (strstrofs(texture, "vent", 0) >= 0 || strstrofs(texture, "duct", 0) >= 0) return "metalvent";
	if (strstrofs(texture, "metal", 0) >= 0) return "metal";
	if (strstrofs(texture, "wood", 0) >= 0) return "wood";
	if (strstrofs(texture, "glass", 0) >= 0) return "glass";
	if (strstrofs(texture, "tile", 0) >= 0) return "tile";
	if (strstrofs(texture, "grass", 0) >= 0) return "grass";
	if (strstrofs(texture, "gravel", 0) >= 0) return "gravel";
	if (strstrofs(texture, "sand", 0) >= 0) return "sand";
	if (strstrofs(texture, "snow", 0) >= 0) return "snow";
	if (strstrofs(texture, "mud", 0) >= 0) return "mud";
	if (strstrofs(texture, "dirt", 0) >= 0) return "dirt";
	return "concrete";
};

string(string prop, int side, int choice) GM_ProfileWave =
{
	local int p, s, depth;
	local string alias, parent, wave;
	p = GM_PropSlot(prop, FALSE);
	if (p < 0i) p = GM_PropSlot("default", FALSE);
	for (depth = 0i; depth < 8i && p >= 0i; depth += 1i)
	{
		alias = gm_props[p * 4i + 2i + side];
		s = GM_SoundSlot(alias, FALSE);
		if (s >= 0i)
		{
			wave = gm_sounds[s * 5i + 1i + choice];
			if (!strcmp(wave, "")) wave = gm_sounds[s * 5i + 1i];
			if (strcmp(wave, "")) return wave;
		}
		parent = gm_props[p * 4i + 1i];
		if (!strcmp(parent, ""))
		{
			if (!strcmp(gm_props[p * 4i], "default")) break;
			parent = "default";
		}
		p = GM_PropSlot(parent, FALSE);
	}
	return "";
};

int(string texture) GM_Material =
{
	local int i, j, at;
	local string prop, wave, source;
	GM_Load();
	texture = GM_Path(texture);
	for (i = 0i; i < gm_matn; i += 1i)
	if (!strcmp(gm_mats[i * GM_FIELDS], texture)) { gm_hits += 1i; return i; }
	at = gm_cursor; gm_cursor = (gm_cursor + 1i) % GM_MATS;
	if (gm_matn < GM_MATS) gm_matn += 1i;
	if (!strcmp(gm_lasttex, gm_mats[at * GM_FIELDS]))
	{
		gm_lasttex = ""; gm_lastprop = ""; gm_lastsource = "";
	}
	GM_Put(gm_mats, at * GM_FIELDS, texture);
	prop = GM_Property(texture, 0);
	source = "vmt";
	if (!strcmp(prop, "")) { prop = strzone(GM_Guess(texture)); source = "texture-fallback"; }
	GM_Put(gm_mats, at * GM_FIELDS + 1i, prop);
	GM_Put(gm_mats, at * GM_FIELDS + 2i, source);
	for (i = 0i; i < 2i; i += 1i)
	for (j = 0i; j < 2i; j += 1i)
	{
		wave = GM_ProfileWave(prop, i, j);
		if (!GA_Exists(wave)) wave = sprintf("player/footsteps/concrete%g.wav", (float)(1i + i + j * 2i));
		GM_Put(gm_mats, at * GM_FIELDS + 3i + i * 2i + j, wave);
	}
	strunzone(prop);
	return at;
};

string(vector org, float step) GM_Sound =
{
	local int at, side, choice;
	local float near;
	local vector p, clipped, ofwd, oright, oup;
	local string texture;
	texture = "";
	traceline(org + '0 0 4', org - '0 0 72', MOVE_NOMONSTERS, world);
	// Collision names are16bytes; render names retain the full cubemap VMT path.
	// FTE's trace id is 1-based; DP_QC_GETSURFACE takes a 0-based index.
	if (trace_fraction < 1)
	if (trace_surface_id > 0i)
	if (checkbuiltin(getsurfacetexture))
		texture = getsurfacetexture(trace_ent, (float)(trace_surface_id - 1i));
	if (!strcmp(texture, ""))
	if (trace_fraction < 1)
	if (checkbuiltin(getsurfacenearpoint))
	if (checkbuiltin(getsurfaceclippedpoint))
	if (checkbuiltin(getsurfacetexture))
	{
		p = trace_endpos - trace_ent.origin;
		ofwd = v_forward; oright = v_right; oup = v_up;
		makevectors(trace_ent.angles);
		p = [p * v_forward, -(p * v_right), p * v_up];
		v_forward = ofwd; v_right = oright; v_up = oup;
		near = -1;
		if (trace_ent == gm_contactent && trace_ent.modelindex == gm_contactmodel && gm_contactface >= 0)
		{
			clipped = getsurfaceclippedpoint(trace_ent, gm_contactface, p);
			// Reuse only while this new contact still lies on the SAME polygon.
			if (vlen(clipped - p) <= 0.125) near = gm_contactface;
		}
		if (near < 0)
		{
			gm_surfacescans += 1i;
			near = getsurfacenearpoint(trace_ent, p);
		}
		if (near >= 0)
		{
			clipped = getsurfaceclippedpoint(trace_ent, near, p);
			// Do not substitute a distant world floor under a prop's collision hull.
			if (vlen(clipped - p) <= 2)
			{
				texture = getsurfacetexture(trace_ent, near);
				gm_contactent = trace_ent; gm_contactmodel = trace_ent.modelindex;
				gm_contactface = near;
			}
		}
	}
	if (!strcmp(texture, ""))
	if (trace_fraction < 1) texture = trace_surfacename;
	at = GM_Material(texture);
	gm_lasttex = gm_mats[at * GM_FIELDS];
	gm_lastprop = gm_mats[at * GM_FIELDS + 1i];
	gm_lastsource = gm_mats[at * GM_FIELDS + 2i];
	side = (int)step % 2i; choice = ((int)step / 2i) % 2i;
	return gm_mats[at * GM_FIELDS + 3i + side * 2i + choice];
};

void() GM_Info =
{
	print(sprintf("gameaudio: material-db profiles %g aliases %g CSS-samples %g surface-scans %g\n", (float)gm_propn, (float)gm_soundn, gm_css, (float)gm_surfacescans));
	print(sprintf("gameaudio: texture '%s' surface '%s' via %s metadata-reads %g cache-hits %g\n",
		gm_lasttex, gm_lastprop, gm_lastsource, (float)gm_reads, (float)gm_hits));
};

void(string texture) GM_Inspect =
{
	local int at;
	at = GM_Material(texture);
	print(sprintf("material: '%s' surface '%s' via %s\n", gm_mats[at * GM_FIELDS],
		gm_mats[at * GM_FIELDS + 1i], gm_mats[at * GM_FIELDS + 2i]));
	print(sprintf("material: left '%s' / '%s' right '%s' / '%s'\n",
		gm_mats[at * GM_FIELDS + 3i], gm_mats[at * GM_FIELDS + 4i],
		gm_mats[at * GM_FIELDS + 5i], gm_mats[at * GM_FIELDS + 6i]));
};
