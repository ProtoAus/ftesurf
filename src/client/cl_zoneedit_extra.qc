/* Patch 671: geometry, window controls, and local map settings. */

float(vector a, vector b, vector c) ZoneEdit_Cross =
{
	return (b_x - a_x) * (c_y - a_y) - (b_y - a_y) * (c_x - a_x);
};

float(vector a, vector b, vector c) ZoneEdit_OnEdge =
{
	if (fabs(ZoneEdit_Cross(a, b, c)) > 0.01) return FALSE;
	return (c_x >= min(a_x, b_x) && c_x <= max(a_x, b_x)
		&& c_y >= min(a_y, b_y) && c_y <= max(a_y, b_y));
};

float(vector a, vector b, vector c, vector d) ZoneEdit_EdgeCross =
{
	local float x, y, z, w;
	x = ZoneEdit_Cross(a, b, c); y = ZoneEdit_Cross(a, b, d);
	z = ZoneEdit_Cross(c, d, a); w = ZoneEdit_Cross(c, d, b);
	if ((x > 0 && y < 0) || (x < 0 && y > 0))
	if ((z > 0 && w < 0) || (z < 0 && w > 0)) return TRUE;
	return (ZoneEdit_OnEdge(a, b, c) || ZoneEdit_OnEdge(a, b, d)
		|| ZoneEdit_OnEdge(c, d, a) || ZoneEdit_OnEdge(c, d, b));
};

float() ZoneEdit_PolygonValid =
{
	local float i, j, k, l, area;
	local vector a, b, c, d;
	area = 0;
	if (ze_np < 3) return FALSE;
	for (i = 0; i < ze_np; i = i + 1)
	{
		k = (i + 1) % ze_np;
		a = ze_pts[i]; b = ze_pts[k];
		if (vlen(a - b) < 0.01) return FALSE;
		area = area + a_x * b_y - b_x * a_y;
		// Adjacent edges may meet at their shared point, not double back.
		c = ze_pts[(i + 2) % ze_np];
		if (ZoneEdit_OnEdge(a, b, c) || ZoneEdit_OnEdge(b, c, a)) return FALSE;
		for (j = i + 1; j < ze_np; j = j + 1)
		{
			l = (j + 1) % ze_np;
			if (j == k || l == i) continue;
			c = ze_pts[j]; d = ze_pts[l];
			if (ZoneEdit_EdgeCross(a, b, c, d)) return FALSE;
		}
	}
	return fabs(area) >= 1;
};

vector(vector p) ZoneEdit_EdgeSnap =
{
	local float z, i, first, n, t, dist, best, limit, corner;
	local vector a, b, d, q, out;
	best = 999999; corner = FALSE; out = p;
	limit = max(4, ze_grid * 0.5);
	// Existing zone vertices and projected XY edges, preserving the traced Z.
	for (z = 0; z < zone_count; z = z + 1)
	{
		first = zone_first[z]; n = zone_npts[z];
		for (i = 0; i < n; i = i + 1)
		{
			a = zone_pt[first + i]; b = zone_pt[first + ((i + 1) % n)];
			if (fabs(p_z - zone_bottom[z]) > limit) continue;
			a_z = p_z; b_z = p_z;
			dist = vlen(p - a);
			if (dist <= limit)
			if (!corner || dist < best) { corner = TRUE; best = dist; out = a; }
			if (corner) continue;
			d = b - a;
			if (d * d > 0)
			{
				t = bound(0, ((p - a) * d) / (d * d), 1);
				q = a + t * d; dist = vlen(p - q);
				if (dist < best && dist <= limit) { best = dist; out = q; }
			}
		}
	}
	return out;
};

void() ZoneEdit_PolygonClose =
{
	local float i;
	local vector p;
	if (!ZoneEdit_PolygonValid())
	{
		ZoneEdit_Note("Need a simple outline: 3+ points, no crossed edges");
		return;
	}
	ze_a = ze_pts[0]; ze_b = ze_a;
	for (i = 1; i < ze_np; i = i + 1)
	{
		p = ze_pts[i];
		ze_a = [min(ze_a_x, p_x), min(ze_a_y, p_y), ze_a_z];
		ze_b = [max(ze_b_x, p_x), max(ze_b_y, p_y), ze_a_z];
	}
	ze_h = ZoneEdit_Height(ze_a_z + 128);
	ui_ze_state = ZE_H;
	ze_close = FALSE;
	ZoneEdit_Note("Look up to pull the height, click to keep it");
};

void() ZoneEdit_PolygonClick =
{
	local vector p;
	local float i;
	if (!ze_hitok) return;
	p = ze_hit;
	if (ze_np > 0)
	{
		p_z = ze_a_z;
		if (ze_np >= 3)
		if (vlen(p - ze_pts[0]) <= max(4, ze_grid * 0.5))
		{
			ZoneEdit_PolygonClose();
			return;
		}
		for (i = 0; i < ze_np; i = i + 1)
			if (vlen(p - ze_pts[i]) < 0.01) { ZoneEdit_Note("Already a corner"); return; }
	}
	else { ze_a = p; ze_floor = ze_hitz; }
	if (ze_np >= ZE_MAXPTS) { ZoneEdit_Note("64 corners is the limit; press Enter to close"); return; }
	ze_pts[ze_np] = p; ze_np = ze_np + 1;
};

// Absolute top-Z is on the grid, even after switching from Surface to Grid.
float(float top) ZoneEdit_Height =
{
	local float g, low, high;
	low = ze_a_z + ZE_MINH; high = ze_a_z + ZE_MAXH;
	if (!ze_snap) return bound(low, top, high) - ze_a_z;
	g = max(1, ze_grid);
	low = ceil(low / g) * g; high = floor(high / g) * g;
	return bound(low, rint(top / g) * g, high) - ze_a_z;
};

vector(float z) ZoneEdit_Interior =
{
	local float i, first, n;
	local vector p, a, b, c;
	first = zone_first[z]; n = zone_npts[z];
	p = '0 0 0';
	for (i = 0; i < n; i = i + 1) p = p + zone_pt[first + i];
	p = p / n;
	if (Zone_XYInRing(z, p_x, p_y)) return p;
	// Every simple ring has an ear. Test consecutive triangle centroids rather
	// than giving a concave zone a spawn in its bounding-box cut-out.
	for (i = 0; i < n; i = i + 1)
	{
		a = zone_pt[first + i]; b = zone_pt[first + ((i + 1) % n)];
		c = zone_pt[first + ((i + 2) % n)]; p = (a + b + c) / 3;
		if (Zone_XYInRing(z, p_x, p_y)) return p;
	}
	return zone_pt[first];
};

void() ZoneEdit_SnapSelected =
{
	local float i, first, n, g, bottom, top;
	local vector p;
	if (ze_sel < 0 || ze_sel >= zone_count) return;
	g = max(1, ze_grid); first = zone_first[ze_sel]; n = zone_npts[ze_sel];
	bottom = floor(zone_bottom[ze_sel] / g) * g;
	top = max(bottom + max(g, ZE_MINH), ceil(zone_top[ze_sel] / g) * g);
	if (!ze_pts) ze_pts = memalloc(sizeof(vector) * ZE_MAXPTS);
	if (n > ZE_MAXPTS) { ZoneEdit_Note("Ring has more than 64 points; leave it intact"); return; }
	ze_np = n;
	for (i = 0; i < n; i = i + 1)
	{
		p = zone_pt[first + i];
		p_x = rint(p_x / g) * g; p_y = rint(p_y / g) * g; p_z = bottom;
		ze_pts[i] = p;
	}
	if (!ZoneEdit_PolygonValid()) { ZoneEdit_Note("Grid would collapse/cross this ring; unchanged"); return; }
	for (i = 0; i < n; i = i + 1)
	{
		p = ze_pts[i]; p_z = 0; zone_pt[first + i] = p;
	}
	zone_bottom[ze_sel] = bottom; zone_top[ze_sel] = top;
	ZoneEdit_Touch();
	ZoneEdit_Note("Snapped X, Y, floor Z and top Z");
};

void(float z) ZoneEdit_Goto =
{
	if (z < 0 || z >= zone_count) return;
	Zone_Hash();
	localcmd(sprintf("cmd zone_edit_goto %g %s\n", z, zone_crc));
	ZoneEdit_Note("Teleport requested; save/reload first if zones were edited");
};

void(float z) ZoneEdit_RowClick =
{
	ze_sel = z;
	if (ze_lastrow == z && cltime - ze_lastclick <= 0.35)
	{
		ze_lastrow = -1; ze_lastclick = -999;
		ZoneEdit_Goto(z);
	}
	else { ze_lastrow = z; ze_lastclick = cltime; }
};

void() ZoneEdit_ToggleMouse =
{
	ze_cursor = !ze_cursor;
	ze_drag = FALSE;
	sui_reset_actions();
	if (ze_cursor)
	{
		ze_mouse_seen = FALSE;
		activate_mouse_cursor();
		UI_CursorClaim(UIC_ZONEEDIT);
		if (ze_field >= 0) sui_field_focus("ze_value");
	}
	else
	{
		UI_CursorRelease(UIC_ZONEEDIT);
		if (sui_text_has_focus("ze_value")) sui_text_unfocus();
	}
	ZoneEdit_Note(ze_cursor ? "Mouse: window (Mouse2 to look)" : "Mouse: look (Mouse2 for window)");
};

void() ZoneEdit_ResetSpawn =
{
	local vector p;
	if (ze_sel < 0 || ze_sel >= zone_count) return;
	if (zone_type[ze_sel] != ZONE_START && zone_type[ze_sel] != ZONE_STAGE) return;
	if (zone_td_name[ze_sel] != "") strunzone(zone_td_name[ze_sel]);
	zone_td_name[ze_sel] = "";
	zone_td_kind[ze_sel] = ZTD_NONE;
	zone_td_pos[ze_sel] = '0 0 0'; zone_td_yaw[ze_sel] = 0;
	// The server's NONE fallback is the bounds centre. Concave rings can put
	// that outside: retain an explicit safe zone-derived floor point instead.
	p = zone_centre[ze_sel]; p_z = zone_bottom[ze_sel] + 2;
	if (!Zone_PointInside(ze_sel, p))
	{
		p = ZoneEdit_Interior(ze_sel);
		zone_td_kind[ze_sel] = ZTD_POS; zone_td_pos[ze_sel] = p;
	}
	ZoneEdit_Touch();
	ZoneEdit_Note(sprintf("%s: spawn reset to the zone's default", ZoneEdit_Label(ze_sel)));
};

void(float mode) ZoneEdit_SettingMode =
{
	if (!ze_settings || (mode != 1 && mode != 2)) return;
	ze_field = -1; sui_text_unfocus();
	ze_mode = mode; ze_values[2] = mode == 2 ? 1000 : 150;
	ZoneEdit_Note(mode == 2 ? "Bhop staged: 100 Hz / air accel 1000; save & reload" : "Surf staged: 66.67 Hz / air accel 150; save & reload");
};

void() ZoneEdit_SettingsOpen =
{
	local float i, fh, n, bytes;
	local string line;
	for (i = 0; i < MAPSET_COUNT; i = i + 1) ze_values[i] = cvar(MapSet_Name(i));
	ze_mode = cvar("pm_ticrate") < 0.012 ? 2 : 1;
	bytes = 0; fh = fopen(MapSet_Path(ze_map), FILE_READ);
	if (fh >= 0)
	{
		while ((line = fgets(fh)))
		{
			bytes = bytes + strlen(line);
			if (bytes > 4096) break;
			n = tokenize(line);
			if (n != 2) continue;
			if (strcmp(argv(0), "gamemode") == 0)
			if (strcmp(argv(1), "1") == 0 || strcmp(argv(1), "2") == 0) ze_mode = stof(argv(1));
			for (i = 0; i < MAPSET_COUNT; i = i + 1)
				if (strcmp(argv(0), MapSet_Name(i)) == 0)
				if (MapSet_Valid(i, stof(argv(1)))) ze_values[i] = stof(argv(1));
		}
		fclose(fh);
	}
	ze_settings = TRUE; ze_field = -1;
	ze_cap_open = ze_values[0];
	if (sui_text_has_focus("ze_value")) sui_text_unfocus();
};

void(float evtype, float scan, float char) ZoneEdit_FieldKey =
{
	local string was;
	was = ze_text;
	sui_text_event(evtype, scan, char, "ze_value", ze_text, ze_caret);
	ze_text = strzone(substring(ze_text, 0, 16));
	ze_caret = min(ze_caret, strlen(ze_text));
	if (was != "") strunzone(was);
};

// Reuse P667's engine-approved paste delivery; only the active field takes it.
// This edits text, never a bind/cvar/file and never a physical-input save proof.
float(float c) ZoneEdit_Paste =
{
	if (c < 32 || c > 126) return FALSE;
	if (!ui_ze_state || !ze_cursor || !ze_settings || ze_field < 0) return FALSE;
	if (!sui_text_has_focus("ze_value") || ZoneEdit_Blocker() != "") return FALSE;
	ZoneEdit_FieldKey(IE_KEYDOWN, 0, c);
	return TRUE;
};

void(float i) ZoneEdit_SettingEdit =
{
	ze_field = i;
	if (ze_text != "") strunzone(ze_text);
	ze_text = strzone(ZoneEdit_Num(ze_values[i])); ze_caret = strlen(ze_text);
	sui_field_focus("ze_value");
};

void() ZoneEdit_SettingApply =
{
	local float v;
	if (ze_field < 0) return;
	v = stof(ze_text);
	if (!MapSet_Number(ze_text) || !MapSet_Valid(ze_field, v))
	{
		ZoneEdit_Note(sprintf("Enter a number from %g to %g", MapSet_Min(ze_field), MapSet_Max(ze_field)));
		return;
	}
	ze_values[ze_field] = v; ze_field = -1; sui_text_unfocus();
	ZoneEdit_Note("Value staged; Save settings applies on your next map load");
};

void() ZoneEdit_SettingsSave =
{
	local float fh, i, ok;
	local string path, part, backup, line;
	if (!ZoneEdit_MayWrite()) { ZoneEdit_Note("Remote command refused: use the panel button"); return; }
	if (ze_map == "" || strcmp(ze_map, zone_mapname) != 0) return;
	if (ze_field >= 0) { ZoneEdit_SettingApply(); if (ze_field >= 0) return; }
	for (i = 0; i < MAPSET_COUNT; i = i + 1)
		if (!MapSet_Valid(i, ze_values[i])) { ZoneEdit_Note("Invalid value; settings not saved"); return; }
	path = MapSet_Path(ze_map); part = strcat(path, ".new");
	fh = fopen(part, FILE_WRITE);
	if (fh < 0) { ZoneEdit_Note("Could not write map settings"); return; }
	fputs(fh, sprintf("gamemode %g\n", ze_mode));
	for (i = 0; i < MAPSET_COUNT; i = i + 1)
		fputs(fh, sprintf("%s %.9g\n", MapSet_Name(i), ze_values[i]));
	fclose(fh);
	fh = fopen(part, FILE_READ);
	if (fh < 0) { ZoneEdit_Note("Could not read back settings; old file kept"); return; }
	line = fgets(fh);
	ok = (tokenize(line) == 2 && strcmp(argv(0), "gamemode") == 0 && stof(argv(1)) == ze_mode);
	for (i = 0; i < MAPSET_COUNT; i = i + 1)
	{
		line = fgets(fh);
		if (tokenize(line) != 2 || strcmp(argv(0), MapSet_Name(i)) != 0 || stof(argv(1)) != ze_values[i]) ok = FALSE;
	}
	if (fgets(fh)) ok = FALSE;
	fclose(fh);
	if (!ok) { fremove(part); ZoneEdit_Note("Settings readback failed; old file kept"); return; }
	backup = strcat(path, ".prev");
	fh = fopen(path, FILE_READ);
	if (fh >= 0)
	{
		fclose(fh);
		fremove(backup);
		if (frename(path, backup) != 0)
		{ fremove(part); ZoneEdit_Note("Could not back up settings; old file kept"); return; }
	}
	if (frename(part, path) != 0)
	{
		if (fh >= 0)
			if (frename(backup, path) != 0)
			{ ZoneEdit_Note("Settings restore failed: previous file is in .prev"); return; }
		fremove(part); ZoneEdit_Note("Settings rename failed; previous settings restored"); return;
	}
	print(sprintf("zone_edit: settings saved %s maxvelocity %g\n", MapSet_Path(ze_map), ze_values[0]));
	// P841: the speed cap is the zone file's maxVelocity too, so Publish carries it -- only a
	// value edited in this panel: the field opens on the local cvar or an old settings file.
	if (zone_count > 0)
	if (ze_values[0] != ze_cap_open)
	if (ze_values[0] != zone_maxvel)
	{
		zone_maxvel = ze_values[0];
		ze_dirty = TRUE;
	}
	if (zone_count > 0)             // with no zones yet the edit stays pending for the next save
		ze_cap_open = ze_values[0];
	if (ze_dirty && zone_maxvel == ze_values[0])
		ZoneEdit_Note(sprintf("Saved locally; speed cap %g reaches lobbies with the zones: Save zones, then Publish saved", zone_maxvel));
	else
		ZoneEdit_Note("Saved locally; reload the hosted map to apply");
};

void(vector p, float tsz, string text, vector col) ZoneEdit_Text =
{
	sui_text(p, [tsz, tsz], text, col, 1, 0);
};

void(vector p, float w, float y, float rowh, float tsz) ZoneEdit_SettingsDraw =
{
	local float i;
	local vector fp;
	local string id, tip;
	ZoneEdit_Text([p_x + 8, y + 4], tsz, "MAP PROPERTIES  /  reload the hosted map to apply", ZEC_DIM);
	y = y + rowh * 1.4;
	if (ZoneEdit_Button([p_x + 8, y], [w * 0.48 - 8, rowh], "ze_mode_surf", "Surf", tsz, ze_mode == 1 ? ZEC_SEL : ZEC_TEXT)) ZoneEdit_SettingMode(1);
	if (ZoneEdit_Button([p_x + w * 0.5, y], [w * 0.48 - 8, rowh], "ze_mode_bhop", "Bhop", tsz, ze_mode == 2 ? ZEC_SEL : ZEC_TEXT)) ZoneEdit_SettingMode(2);
	y = y + rowh;
	ZoneEdit_Text([p_x + 8, y + 4], tsz, ze_mode == 2 ? "100 Hz  /  preset air accel 1000" : "66.67 Hz  /  preset air accel 150", ZEC_DIM);
	y = y + rowh * 1.4;
	for (i = 0; i < MAPSET_COUNT; i = i + 1)
	{
		id = sprintf("ze_ms%g", i);
		tip = ZoneEdit_Tip(id);
		sui_action_element([p_x + 8, y], [w * 0.56 - 8, rowh - 3], sprintf("ze_msl%g", i), sui_noop);
		if (ze_cursor) sui_tooltip_for(sprintf("ze_msl%g", i), tip, ui_cv_scale);
		ZoneEdit_Text([p_x + 8, y + 6], tsz, MapSet_Label(i), ZEC_TEXT);
		if (ZoneEdit_Button([p_x + w * 0.56, y], [w * 0.40, rowh - 3], id,
			ftos(ze_values[i]), tsz, ze_field == i ? ZEC_SEL : ZEC_TEXT)) ZoneEdit_SettingEdit(i);
		y = y + rowh;
	}
	if (ze_field >= 0)
	{
		fp = [p_x + 8, y, 0];
		sui_style_box(fp, [w * 0.66, rowh - 3, 0], 4, SUI_THEME_WELL, SUI_THEME_EDGE_HI, 1);
		sui_text_metrics(tsz * 0.5, [tsz, tsz]);
		sui_text_input("ze_value", fp, [w * 0.66, rowh - 3, 0], ze_text, ze_caret);
		if (ze_cursor) sui_tooltip_for("ze_value", ZoneEdit_Tip(sprintf("ze_ms%g", ze_field)), ui_cv_scale);
		ZoneEdit_Text(fp + [tsz * 0.5, 5, 0], tsz, ze_text, ZEC_TEXT);
		if (sui_text_has_focus("ze_value"))
			drawfill(fp + [tsz * 0.5 + stringwidth(substring(ze_text, 0, ze_caret), TRUE, [tsz, tsz]), 4, 0],
				[1, tsz + 2, 0], ZEC_SEL, 1, 0);
		if (ZoneEdit_Button([p_x + w * 0.70, y], [w * 0.26, rowh - 3], "ze_msapply", "Apply", tsz, ZEC_TEXT)) ZoneEdit_SettingApply();
	}
	y = y + rowh;
	if (ZoneEdit_Button([p_x + 8, y], [w * 0.48 - 8, rowh - 3], "ze_mssave", "Save settings", tsz, ZEC_TEXT)) ZoneEdit_SettingsSave();
	if (ZoneEdit_Button([p_x + w * 0.5, y], [w * 0.48 - 8, rowh - 3], "ze_msback", "Back to zones", tsz, ZEC_TEXT))
	{ ze_settings = FALSE; ze_field = -1; sui_text_unfocus(); }
	y = y + rowh;
	ZoneEdit_Text([p_x + 8, y + 4], tsz, "Defaults: ground movement stays map-authored", ZEC_DIM);
	y = y + rowh;
	ZoneEdit_Text([p_x + 8, y + 4], tsz, "Lobbies: the speed cap only, with Save zones + Publish", ZEC_DIM);
};

void(vector p) ZoneEdit_DragStart =
{
	if (_cursor_position_x < p_x || _cursor_position_x >= p_x + ze_panel_s_x) return;
	if (_cursor_position_y < p_y || _cursor_position_y >= p_y + 24 * ui_cv_scale) return;
	ze_drag = TRUE; ze_positioned = TRUE;
	ze_drag_offset = _cursor_position - p;
};

float() ZoneEdit_AddPolygon =
{
	local float z, i, first;
	local vector p;
	if (zone_count >= ZONE_MAX || zone_ptcount + ze_np > ZONE_MAX_POINTS) return -1;
	z = zone_count; first = zone_ptcount;
	zone_type[z] = ze_ntype; zone_track[z] = ze_track;
	zone_seg[z] = ze_nseg; zone_cp[z] = ze_ncp;
	zone_first[z] = first; zone_npts[z] = ze_np;
	zone_bottom[z] = ze_a_z; zone_top[z] = ze_a_z + ze_h;
	zone_td_kind[z] = ZTD_NONE; zone_td_pos[z] = '0 0 0';
	zone_td_yaw[z] = 0; zone_td_name[z] = "";
	for (i = 0; i < ze_np; i = i + 1)
	{
		p = ze_pts[i]; p_z = 0; zone_pt[first + i] = p;
	}
	zone_count = zone_count + 1; zone_ptcount = zone_ptcount + ze_np;
	Zone_Finish(z);
	return z;
};

void() ZoneEdit_PolygonGhost =
{
	local float i;
	local vector a, b, up;
	up = [0, 0, ze_h];
	for (i = 0; i < ze_np; i = i + 1)
	{
		a = ze_pts[i];
		if (i + 1 < ze_np) b = ze_pts[i + 1];
		else if (ui_ze_state == ZE_H) b = ze_pts[0];
		else b = ze_hit;
		b_z = a_z;
		if (i + 1 < ze_np || ui_ze_state == ZE_H || ze_hitok) Zone_Line(a, b, ZEC_NEW, 1);
		Zone_Line(a - [3, 0, 0], a + [3, 0, 0], ZEC_NEW, 1);
		Zone_Line(a - [0, 3, 0], a + [0, 3, 0], ZEC_NEW, 1);
		if (ui_ze_state == ZE_H)
		{
			Zone_Line(a + up, b + up, ZEC_NEW, 1);
			Zone_Line(a, a + up, ZEC_NEW, 1);
		}
	}
};
