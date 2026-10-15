/* Download cache only: complete timer shape, bounded body, verified write,
 * then a reversible rename. Never remove the installed predecessor first. */
float(string oldpath, string newpath) frename = #0:frename;
float(string path) fremove = #0:fremove;

float(string map) ZoneFile_Map =
{
	local float i;
	if (strlen(map) < 1 || strlen(map) > 64) return FALSE;
	for (i = 0; i < strlen(map); i = i + 1)
		if (strstrofs("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-", substring(map, i, 1), 0) < 0)
			return FALSE;
	return TRUE;
};

// Same bounds as sh_zones tables; the menu deliberately does not load them.
#define ZFILE_MAX_REGIONS 256
#define ZFILE_MAX_POINTS 2048
// Native json_type enum: string0, number1, object2, array3, true4, false5, null6.
int(int node) ZoneFile_Type = #0:json_get_value_type;
float zfile_regions, zfile_points, zfile_nodes;
int zfile_node[17];
int zfile_next[17];

float(int root) ZoneFile_Tree =
{
	local int node, kind, depth, i, n;
	local float v;
	depth = 0i; zfile_node[0i] = root; zfile_next[0i] = 0i;
	while (depth >= 0i)
	{
		node = zfile_node[depth]; kind = ZoneFile_Type(node);
		if (zfile_next[depth] == 0i)
		{
			zfile_nodes = zfile_nodes + 1;
			if (zfile_nodes > 50000) return FALSE;
			if (kind == 1i)
			{
				v = json_get_float(node);
				if (!(v >= -1000000000000000000000000000000.0 && v <= 1000000000000000000000000000000.0)) return FALSE;
			}
		}
		if (kind != 2i && kind != 3i) { depth = depth - 1i; continue; }
		i = zfile_next[depth]; n = json_get_length(node);
		if (i >= n) { depth = depth - 1i; continue; }
		if (depth >= 16i) return FALSE;
		zfile_next[depth] = i + 1i;
		zfile_node[depth + 1i] = json_get_child_at_index(node, i);
		depth = depth + 1i; zfile_next[depth] = 0i;
	}
	return TRUE;
};

float(int node) ZoneFile_Number =
{
	local float v;
	if (ZoneFile_Type(node) != 1i) return FALSE;
	v = json_get_float(node);
	return (v >= -10000000 && v <= 10000000);
};

float(int regions) ZoneFile_Regions =
{
	local int r, points, pair, bottom, height, i, j, n, count;
	local float x, y, firstx, firsty, prevx, prevy, area;
	if (ZoneFile_Type(regions) != 3i) return FALSE;
	n = json_get_length(regions);
	if (n < 1i || n > 128i) return FALSE;
	for (i = 0i; i < n; i = i + 1i)
	{
		r = json_get_child_at_index(regions, i);
		if (ZoneFile_Type(r) != 2i) return FALSE;
		zfile_regions = zfile_regions + 1;
		if (zfile_regions > ZFILE_MAX_REGIONS) return FALSE;
		bottom = json_find_object_child(r, "bottom"); height = json_find_object_child(r, "height");
		if (!ZoneFile_Number(bottom) || !ZoneFile_Number(height)) return FALSE;
		if (json_get_float(height) <= 0) return FALSE;
		points = json_find_object_child(r, "points");
		if (ZoneFile_Type(points) != 3i) return FALSE;
		count = json_get_length(points);
		if (count < 3i || count > 128i) return FALSE;
		zfile_points = zfile_points + (float)count;
		if (zfile_points > ZFILE_MAX_POINTS) return FALSE;
		area = firstx = firsty = prevx = prevy = 0;
		for (j = 0i; j < count; j = j + 1i)
		{
			pair = json_get_child_at_index(points, j);
			if (ZoneFile_Type(pair) != 3i || json_get_length(pair) != 2i) return FALSE;
			if (!ZoneFile_Number(json_get_child_at_index(pair, 0i)) || !ZoneFile_Number(json_get_child_at_index(pair, 1i))) return FALSE;
			x = json_get_float(json_get_child_at_index(pair, 0i)); y = json_get_float(json_get_child_at_index(pair, 1i));
			if (j == 0i) { firstx = x; firsty = y; }
			else area = area + prevx * y - x * prevy;
			prevx = x; prevy = y;
		}
		area = area + prevx * firsty - firstx * prevy;
		if (fabs(area) < 0.000001) return FALSE;
	}
	return TRUE;
};

float(int track) ZoneFile_Track =
{
	local int zones, segments, segment, cps, cp, i, j, n, count;
	if (ZoneFile_Type(track) != 2i) return FALSE;
	zones = json_find_object_child(track, "zones");
	if (ZoneFile_Type(zones) != 2i) return FALSE;
	if (!ZoneFile_Regions(json_find_object_child(json_find_object_child(zones, "end"), "regions"))) return FALSE;
	segments = json_find_object_child(zones, "segments");
	if (ZoneFile_Type(segments) != 3i) return FALSE;
	n = json_get_length(segments);
	if (n < 1i || n > 128i) return FALSE;
	for (i = 0i; i < n; i = i + 1i)
	{
		segment = json_get_child_at_index(segments, i);
		if (ZoneFile_Type(segment) != 2i) return FALSE;
		cps = json_find_object_child(segment, "checkpoints");
		if (ZoneFile_Type(cps) != 3i) return FALSE;
		count = json_get_length(cps);
		if (count < 1i || count > 128i) return FALSE;
		for (j = 0i; j < count; j = j + 1i)
		{
			cp = json_get_child_at_index(cps, j);
			if (ZoneFile_Type(cp) != 2i) return FALSE;
			if (!ZoneFile_Regions(json_find_object_child(cp, "regions"))) return FALSE;
		}
	}
	return TRUE;
};

float(string body) ZoneFile_Valid =
{
	local int root, tracks, version, bonuses, globalregions, regions, i, n;
	local float ok;
	if (strlen(body) < 16 || strlen(body) > 262144) return FALSE;
	if (!checkbuiltin(ZoneFile_Type)) return FALSE;
	root = json_parse(body);
	if (!root) return FALSE;
	zfile_regions = zfile_points = zfile_nodes = 0;
	tracks = json_find_object_child(root, "tracks"); version = json_find_object_child(root, "formatVersion");
	ok = (ZoneFile_Type(root) == 2i && ZoneFile_Type(tracks) == 2i && ZoneFile_Type(version) == 1i && json_get_float(version) == 1);
	if (ok) ok = ZoneFile_Tree(root);
	if (ok) ok = ZoneFile_Track(json_find_object_child(tracks, "main"));
	bonuses = json_find_object_child(tracks, "bonuses");
	if (ok && ZoneFile_Type(bonuses) != 6i)
	{
		n = json_get_length(bonuses);
		if (ZoneFile_Type(bonuses) != 3i || n > 16i) ok = FALSE;
		for (i = 0i; i < n && ok; i = i + 1i)
			ok = ZoneFile_Track(json_get_child_at_index(bonuses, i));
	}
	globalregions = json_find_object_child(root, "globalRegions");
	if (ok && ZoneFile_Type(globalregions) != 6i)
	{
		if (ZoneFile_Type(globalregions) != 2i) ok = FALSE;
		n = json_get_length(globalregions);
		for (i = 0i; i < n && ok; i = i + 1i)
		{
			regions = json_get_child_at_index(globalregions, i);
			if (ZoneFile_Type(regions) != 3i) ok = FALSE;
			else if (json_get_length(regions) > 0i) ok = ZoneFile_Regions(regions);
		}
	}
	json_free(root);
	return ok;
};

float(string path, string body) ZoneFile_Store =
{
	local string part, prev;
	local float f, had;
	if (!ZoneFile_Valid(body)) return FALSE;
	if (!checkbuiltin(frename)) return FALSE;
	part = strcat(path, ".part"); prev = strcat(path, ".prev");
	f = fopen(part, FILE_WRITE);
	if (f < 0) return FALSE;
	fputs(f, body); fclose(f);
	f = fopen(part, FILE_READ);
	if (f < 0) return FALSE;
	if (fsize(f) != (int)strlen(body))
	{
		fclose(f); fremove(part); return FALSE;
	}
	fclose(f);
	f = fopen(path, FILE_READ); had = (f >= 0);
	if (had)
	{
		fclose(f);
		fremove(prev);
		if (frename(path, prev) != 0) { fremove(part); return FALSE; }
	}
	if (frename(part, path) == 0) return TRUE;
	if (had)
	if (frename(prev, path) != 0)
		print("^1zones: could not restore cache; predecessor remains in .prev\n");
	fremove(part);
	return FALSE;
};
