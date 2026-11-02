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
	ze_zkind = 0;
	// Existing zone vertices and projected XY edges, preserving the traced Z.
	for (z = 0; z < zone_count; z = z + 1)
	{
		if (ze_dragging && z == ze_dz) continue;    // P1203: not the zone being dragged
		first = zone_first[z]; n = zone_npts[z];
		for (i = 0; i < n; i = i + 1)
		{
			a = zone_pt[first + i]; b = zone_pt[first + ((i + 1) % n)];
			if (fabs(p_z - zone_bottom[z]) > limit) continue;
			a_z = p_z; b_z = p_z;
			dist = vlen(p - a);
			if (dist <= limit)
			if (!corner || dist < best)
			{
				corner = TRUE; best = dist; out = a;
				ze_zkind = 1; ze_zat = [a_x, a_y, zone_bottom[z]];
			}
			if (corner) continue;
			d = b - a;
			if (d * d > 0)
			{
				t = bound(0, ((p - a) * d) / (d * d), 1);
				q = a + t * d; dist = vlen(p - q);
				if (dist < best && dist <= limit)
				{
					best = dist; out = q;
					ze_zkind = 2; ze_zat = [q_x, q_y, zone_bottom[z]];
				}
			}
		}
	}
	return out;
};

/*
  P1197: snapping to the map's own corners and edges (Lex, 2 Nov: the angled start of
  surf_sinsane_ez has corners no grid step reaches).  The map surface under the aim is read with
  the getsurface builtins; a corner within ZE_SNAPPX of the crosshair on screen wins -- its own
  or an existing zone's, whichever is nearer -- else the nearest edge point.  XY are the
  surface's exactly (with the grid on, an edge point keeps the grid along the edge); Z keeps
  ZoneEdit_SnapV's floor-down rule.  Review 1: splits the compiler cut into one flat floor (BSP
  nodes, lightmap chops) are not corners or edges, a candidate must be near the aim in the world
  too (at a shallow pitch 14 px covers hundreds of units), and searches are rate-limited.
*/
// How far from the crosshair a world point is drawn, in screen units (ze_pxtan: ZoneEdit_AimFrom).
float(vector eye, vector fwd, vector p) ZoneEdit_PxOff =
{
	local vector w;
	local float along;

	w = p - eye;
	along = w * fwd;
	if (along < 1) return 999999;
	return ze_pxtan * vlen(w - fwd * along) / along;
};

// Surface s is under the aim: its nearest point is the aim, and its mesh is filled (an unbuilt
// VBSP mesh is all origin, and the triangle clip hands every point back unchanged).
float(float s, vector raw) ZoneEdit_SurfUnder =
{
	if (getsurfacenumpoints(world, s) < 3) return FALSE;
	if (getsurfacepoint(world, s, 0) == getsurfacepoint(world, s, 1)) return FALSE;
	return vlen(getsurfaceclippedpoint(world, s, raw) - raw) < 1;
};

// The world surface under the aim, -1 none.  getsurfacenearpoint walks every world triangle
// (cl_paint.qc): it is asked again only when the aim leaves the last answer, and at most every
// 50 ms (an aim at a prop or a clip brush has no face under it, every frame).
float(vector raw) ZoneEdit_WorldSurf =
{
	local float s;

	if (!checkbuiltin(getsurfacenearpoint) || !checkbuiltin(getsurfacenumtriangles))
		return -1;
	if (ze_wsurf >= 0 && ZoneEdit_SurfUnder(ze_wsurf, raw))
		return ze_wsurf;
	ze_wsurf = -1;
	if (cltime >= ze_wask_t && cltime < ze_wask_t + 0.05)
		return -1;
	ze_wask_t = cltime;
	ze_wasks = ze_wasks + 1;
	s = getsurfacenearpoint(world, raw);
	if (s >= 0 && ZoneEdit_SurfUnder(s, raw))
		ze_wsurf = s;
	return ze_wsurf;
};

// The face's own flat floor goes on at p: a short trace through p, from the face's side, lands
// on that plane at p.  A wall, a ledge or another slope there makes p a real corner or edge.
float(vector p, vector nm) ZoneEdit_FlatOn =
{
	traceline(p + nm * 4, p - nm * 4, MOVE_NOMONSTERS, world);
	return (!trace_startsolid && trace_fraction < 1 && trace_plane_normal * nm > 0.999 &&
	        fabs(trace_fraction - 0.5) < 0.01);
};

// A corner the compiler made by splitting one flat floor has that floor on every side.
float(vector v, vector nm) ZoneEdit_RealCorner =
{
	local vector t1, t2;

	t1 = (fabs(nm_z) < 0.9) ? '0 0 1' : '1 0 0';
	t1 = normalize(crossproduct(nm, t1));
	t2 = crossproduct(nm, t1);
	return !(ZoneEdit_FlatOn(v + (t1 + t2) * 2, nm) && ZoneEdit_FlatOn(v + (t1 - t2) * 2, nm) &&
	         ZoneEdit_FlatOn(v - (t1 + t2) * 2, nm) && ZoneEdit_FlatOn(v - (t1 - t2) * 2, nm));
};

void(vector eye, vector fwd, vector raw) ZoneEdit_Snap =
{
	local float s, n, i, d, bv, be, kv, ke, reach;
	local vector v, w, q, pv, pe, zp, nm, mid, ev, ew, gp;

	bv = be = ZE_SNAPPX * ui_cv_scale;
	kv = ke = ZES_NONE;
	pv = pe = ev = ew = mid = '0 0 0';
	reach = max(32, vlen(raw - eye) * 0.2);
	gp = [ze_hit_x, ze_hit_y, raw_z];   // the grid's point, at the aim's height
	s = ZoneEdit_WorldSurf(raw);
	n = (s >= 0) ? getsurfacenumpoints(world, s) : 0;
	if (n && getsurfacenumtriangles(world, s) != n - 2)
		n = 0;                          // not a ring: a displacement's grid is not corners
	for (i = 0; i < n; i = i + 1)
	{
		v = getsurfacepoint(world, s, i);
		w = getsurfacepoint(world, s, (i + 1) % n);
		mid = mid + v * (1 / n);
		if (vlen(v - raw) <= reach)
		{
			d = ZoneEdit_PxOff(eye, fwd, v);
			if (d < bv) { bv = d; pv = v; kv = ZES_MAPV; }
		}
		q = w - v;
		if (q * q > 0) q = v + bound(0, ((raw - v) * q) / (q * q), 1) * q;
		else q = v;
		if (vlen(q - raw) <= reach)
		{
			d = ZoneEdit_PxOff(eye, fwd, q);
			if (d < be) { be = d; pe = q; ke = ZES_MAPE; ev = v; ew = w; }
		}
	}
	if (n)
	{
		nm = normalize(getsurfacenormal(world, s));
		if (kv && !ZoneEdit_RealCorner(pv, nm)) kv = ZES_NONE;
		if (ke)
		{
			q = normalize(crossproduct(ew - ev, nm));
			if (q * (mid - pe) > 0) q = -q;
			if (ZoneEdit_FlatOn(pe + q * 2, nm)) ke = ZES_NONE;
			else if (ze_snap)
			{
				// The grid along the edge: the grid point's foot on it.
				q = ew - ev;
				pe = ev + bound(0, ((gp - ev) * q) / (q * q), 1) * q;
			}
		}
	}
	// An existing zone's corner or edge, by its own world-unit reach; nearer on screen wins.
	zp = ZoneEdit_EdgeSnap(ze_hit);
	if (ze_zkind)
	{
		d = ZoneEdit_PxOff(eye, fwd, ze_zat);
		if (ze_zkind == 1 && (!kv || d < bv)) { bv = d; pv = ze_zat; kv = ZES_ZONEV; }
		if (ze_zkind == 2 && (!ke || d < be)) { be = d; pe = ze_zat; ke = ZES_ZONEE; }
	}
	if (kv) { ze_skind = kv; q = pv; }
	else if (ke) { ze_skind = ke; q = pe; }
	else return;
	ze_sat = q;
	if (ze_skind >= ZES_ZONEV)
	{
		ze_hit = zp;                    // the zone's XY, the aim's floor (ZoneEdit_EdgeSnap)
		return;
	}
	ze_hitz = q_z;
	d = max(1, ze_grid);
	ze_hit = [q_x, q_y, ze_snap ? floor(q_z / d) * d : q_z];
};

string(float k) ZoneEdit_SnapName =
{
	if (k == ZES_MAPV) return "map corner";
	if (k == ZES_MAPE) return "map edge";
	if (k == ZES_ZONEV) return "zone corner";
	if (k == ZES_ZONEE) return "zone edge";
	return ze_snap ? sprintf("grid %g", ze_grid) : "surface";
};

vector(float k) ZoneEdit_SnapCol =
{
	if (k == ZES_MAPV) return '0.35 1 0.45';
	if (k == ZES_MAPE) return '0.35 0.85 1';
	if (k == ZES_ZONEV || k == ZES_ZONEE) return '1 1 1';
	return ZEC_NEW;
};

// The map surface the snap reads, outlined a hair off it, its corners ticked.
void(vector eye) ZoneEdit_SnapDraw3D =
{
	local float n, i, t;
	local vector nm, v, w;

	if (!ze_edges || ze_wsurf < 0) return;
	n = getsurfacenumpoints(world, ze_wsurf);
	if (getsurfacenumtriangles(world, ze_wsurf) != n - 2) return;
	nm = normalize(getsurfacenormal(world, ze_wsurf));
	for (i = 0; i < n; i = i + 1)
	{
		v = getsurfacepoint(world, ze_wsurf, i) + nm * 0.5;
		w = getsurfacepoint(world, ze_wsurf, (i + 1) % n) + nm * 0.5;
		Zone_Line(v, w, ZoneEdit_SnapCol(ZES_MAPE), 0.45);
		t = max(3, vlen(v - eye) * 0.01);
		Zone_Line(v, v + nm * t, ZoneEdit_SnapCol(ZES_MAPV), 0.9);
	}
};

// A square round the snapped point on screen, so a corner far off still shows where it is.
void(float rsz) ZoneEdit_SnapMark2D =
{
	local vector eye, sp, col;
	local float r, t;

	if (!ze_skind) return;
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	if (v_forward * (ze_sat - eye) < 8) return;
	sp = project(ze_sat);
	sp_z = 0;
	col = ZoneEdit_SnapCol(ze_skind);
	r = max(4, rsz * 0.8);
	t = max(1, rint(rsz / 8));
	drawfill(sp + [-r, -r], [r * 2, t], col, 1, 0);
	drawfill(sp + [-r, r - t], [r * 2, t], col, 1, 0);
	drawfill(sp + [-r, -r], [t, r * 2], col, 1, 0);
	drawfill(sp + [r - t, -r], [t, r * 2], col, 1, 0);
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
	local float i, first;
	local vector lo, hi, p;
	if (z < 0 || z >= zone_count) return;
	Zone_Hash();
	if (strcmp(serverkey("fs_zegoto"), "1") || zone_npts[z] <= 0)
	{
		localcmd(sprintf("cmd zone_edit_goto %g %s\n", z, zone_crc));   // an older server refuses five words
		ZoneEdit_Note(ze_dirty ? "Teleport requested; save/reload first if zones were edited" : "Teleport requested");
		return;
	}
	// P1223: the zone as drawn, the middle of its outline's box on its floor (SV_ZoneGotoAng's place
	// for a zone with no destination). A server whose table matches the crc uses its own zone z.
	first = zone_first[z];
	lo = zone_pt[first];
	hi = lo;
	for (i = 1; i < zone_npts[z]; i = i + 1)
	{
		p = zone_pt[first + i];
		lo_x = min(lo_x, p_x); lo_y = min(lo_y, p_y);
		hi_x = max(hi_x, p_x); hi_y = max(hi_y, p_y);
	}
	localcmd(sprintf("cmd zone_edit_goto %g %s %.1f %.1f %.1f\n", z, (zone_crc != "") ? zone_crc : "-",
	                 (lo_x + hi_x) * 0.5, (lo_y + hi_y) * 0.5, zone_bottom[z] + 2));
	ZoneEdit_Note("Teleport requested");
};

void(float z) ZoneEdit_RowClick =
{
	if (ze_dim >= 0 && z != ze_sel) { ze_dim = -1; sui_text_unfocus(); }   // P1184: the field was for that zone
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
	if (ze_dragging) ZoneEdit_DragCancel();     // P1203: the panel's buttons can change the table
	ze_cursor = !ze_cursor;
	ze_drag = FALSE;
	sui_reset_actions();
	if (ze_cursor)
	{
		ze_mouse_seen = cl_ptr_real_ok = FALSE;  // P1081: a new cursor; the old place is stale
		activate_mouse_cursor();
		UI_CursorClaim(UIC_ZONEEDIT);
		if (ze_field >= 0 || ze_dim >= 0) sui_field_focus("ze_value");
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
	ze_settings = TRUE; ze_field = ze_dim = -1; ze_history = FALSE;
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
	if (!ui_ze_state || !ZoneEdit_FieldOpen()) return FALSE;
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

/*
  P1184: the selected zone's bounds as six numbers (x min/max, y min/max, bottom, top), each
  typed or nudged with the wheel, for corners the crosshair cannot reach (Lex, 2 Nov). An x or y
  face moves by stretching the outline along that axis from the opposite face, so a box's face
  moves exactly and a polygon keeps its shape's proportions.
*/
string(float face) ZoneEdit_DimName =
{
	if (face == 0) return "x min";
	if (face == 1) return "x max";
	if (face == 2) return "y min";
	if (face == 3) return "y max";
	if (face == 4) return "bottom";
	return "top";
};

float(float z, float face) ZoneEdit_DimGet =
{
	local float i, first, n, v, x;
	local vector p;
	if (face == 4) return zone_bottom[z];
	if (face == 5) return zone_top[z];
	first = zone_first[z]; n = zone_npts[z];
	p = zone_pt[first];
	v = (face < 2) ? p_x : p_y;
	for (i = 1; i < n; i = i + 1)
	{
		p = zone_pt[first + i];
		x = (face < 2) ? p_x : p_y;
		if (face == 0 || face == 2) v = min(v, x);
		else v = max(v, x);
	}
	return v;
};

// A plain decimal, a leading minus allowed (MapSet_Number takes none).
float(string s) ZoneEdit_DimNumber =
{
	local float i, c, digits, dot;
	digits = dot = 0;
	if (s == "" || strlen(s) > 16) return FALSE;
	for (i = 0; i < strlen(s); i = i + 1)
	{
		c = str2chr(s, i);
		if (c == '-' && i == 0) continue;
		if (c == '.') { if (dot) return FALSE; dot = TRUE; continue; }
		if (c < '0' || c > '9') return FALSE;
		digits = digits + 1;
	}
	return digits > 0;
};

// Set one face of the selected zone; TRUE when it changed.
float(float face, float v) ZoneEdit_DimSet =
{
	local float z, i, first, n, lo, hi, nlo, nhi, k, x;
	local vector p;
	z = ze_sel;
	if (z < 0 || z >= zone_count || face < 0 || face > 5) return FALSE;
	if (fabs(v) > 1000000) { ZoneEdit_Note("Keep coordinates within 1000000"); return FALSE; }
	if (v == ZoneEdit_DimGet(z, face)) { ZoneEdit_Note(sprintf("%s unchanged", ZoneEdit_DimName(face))); return TRUE; }
	if (face == 4 || face == 5)
	{
		nlo = (face == 4) ? v : zone_bottom[z];
		nhi = (face == 5) ? v : zone_top[z];
		if (nhi - nlo < ZE_MINH || nhi - nlo > ZE_MAXH)
		{
			ZoneEdit_Note(sprintf("Height must stay %g to %g units", ZE_MINH, ZE_MAXH)); return FALSE;
		}
		zone_bottom[z] = nlo; zone_top[z] = nhi;
	}
	else
	{
		lo = ZoneEdit_DimGet(z, (face < 2) ? 0 : 2);
		hi = ZoneEdit_DimGet(z, (face < 2) ? 1 : 3);
		nlo = (face == 0 || face == 2) ? v : lo;
		nhi = (face == 1 || face == 3) ? v : hi;
		if (nhi - nlo < 1 || hi - lo <= 0) { ZoneEdit_Note("A zone must stay at least 1 unit wide"); return FALSE; }
		k = (nhi - nlo) / (hi - lo);
		first = zone_first[z]; n = zone_npts[z];
		for (i = 0; i < n; i = i + 1)
		{
			p = zone_pt[first + i];
			x = (face < 2) ? p_x : p_y;
			x = nlo + (x - lo) * k;
			if (face < 2) p_x = x; else p_y = x;
			zone_pt[first + i] = p;
		}
	}
	ZoneEdit_Touch();
	if (zone_td_kind[ze_sel] == ZTD_POS && !Zone_PointInside(ze_sel, zone_td_pos[ze_sel] + '0 0 2'))
		ZoneEdit_Note(sprintf("%s %s %s; its custom spawn is now outside: Set spawn again",
		                      ZoneEdit_Label(ze_sel), ZoneEdit_DimName(face), ZoneEdit_Num(v)));
	else
		ZoneEdit_Note(sprintf("%s %s %s (not saved)", ZoneEdit_Label(ze_sel), ZoneEdit_DimName(face), ZoneEdit_Num(v)));
	return TRUE;
};

void(float face) ZoneEdit_DimEdit =
{
	if (ze_sel < 0 || ze_sel >= zone_count || ui_ze_state != ZE_PANEL) return;
	ze_dim = face;
	if (ze_text != "") strunzone(ze_text);
	ze_text = strzone(ZoneEdit_Num(ZoneEdit_DimGet(ze_sel, face))); ze_caret = strlen(ze_text);
	sui_field_focus("ze_value");
};

void() ZoneEdit_DimApply =
{
	if (ze_dim < 0) return;
	if (!ZoneEdit_DimNumber(ze_text)) { ZoneEdit_Note("Enter a number, e.g. -1024 or 96.5"); return; }
	if (ZoneEdit_DimSet(ze_dim, stof(ze_text))) { ze_dim = -1; sui_text_unfocus(); }
};

// The wheel over a value: one grid step (1 unit with Surface snapping), up adds.
void(float face, float dir) ZoneEdit_DimNudge =
{
	local float step;
	if (ze_sel < 0 || ze_sel >= zone_count || ui_ze_state != ZE_PANEL) return;
	step = ze_snap ? max(1, ze_grid) : 1;
	ZoneEdit_DimSet(face, ZoneEdit_DimGet(ze_sel, face) + dir * step);
};

// Inspector rows for the selected zone: its size, then six values (or the open field). Returns y.
float(vector p, float w, float y, float rowh, float tsz) ZoneEdit_DimsDraw =
{
	local float face, cw, z, a, pad;
	local vector cp, fp;
	local string id;
	pad = 8 * ui_cv_scale;              // the panel's own margin
	z = ze_sel;
	a = (z >= 0 && z < zone_count);
	ze_dim_hover = -1;
	if (!a)
	{
		if (ze_dim >= 0) { ze_dim = -1; sui_text_unfocus(); }
		ZoneEdit_Text([p_x + pad, y + 4], tsz, "SIZE  /  select a zone to see and type its faces", ZEC_DIM);
		return y + rowh * 2;
	}
	if (ze_dim >= 0)
	{
		ZoneEdit_Text([p_x + pad, y + 4], tsz, sprintf("type %s, Enter applies, Esc cancels", ZoneEdit_DimName(ze_dim)), ZEC_DIM);
		y = y + rowh;
		fp = [p_x + pad, y, 0];
		sui_style_box(fp, [w * 0.62, rowh - 3, 0], 4, SUI_THEME_WELL, SUI_THEME_EDGE_HI, 1);
		sui_text_metrics(tsz * 0.5, [tsz, tsz]);
		sui_text_input("ze_value", fp, [w * 0.62, rowh - 3, 0], ze_text, ze_caret);
		ZoneEdit_Text(fp + [tsz * 0.5, 5, 0], tsz, ze_text, ZEC_TEXT);
		if (sui_text_has_focus("ze_value"))
			drawfill(fp + [tsz * 0.5 + stringwidth(substring(ze_text, 0, ze_caret), TRUE, [tsz, tsz]), 4, 0],
				[1, tsz + 2, 0], ZEC_SEL, 1, 0);
		if (ZoneEdit_Button([p_x + w * 0.66, y], [w * 0.30, rowh - 3], "ze_dimapply", "Apply", tsz, ZEC_TEXT)) ZoneEdit_DimApply();
		return y + rowh;
	}
	ZoneEdit_Text([p_x + pad, y + 4], tsz, sprintf("SIZE %s x %s x %s  /  x min, x max, y min, y max, bottom, top",
		ZoneEdit_Num(ZoneEdit_DimGet(z, 1) - ZoneEdit_DimGet(z, 0)),
		ZoneEdit_Num(ZoneEdit_DimGet(z, 3) - ZoneEdit_DimGet(z, 2)),
		ZoneEdit_Num(zone_top[z] - zone_bottom[z])), ZEC_DIM);
	y = y + rowh;
	cw = (w - pad * 2 - 20) / 6;
	for (face = 0; face < 6; face = face + 1)
	{
		id = sprintf("ze_d%g", face);
		cp = [p_x + pad + (cw + 4) * face, y, 0];
		if (ZoneEdit_Button(cp, [cw, rowh - 3], id, ZoneEdit_Num(ZoneEdit_DimGet(z, face)), tsz, ZEC_TEXT))
			ZoneEdit_DimEdit(face);
		if (sui_is_hovered(id)) ze_dim_hover = face;
	}
	return y + rowh;
};

/*
  P1203: handles (Lex, 2 Nov: "highlight and grab vertex points with your mouse, and then drag it
  around in 3d ... same with grabbing edges and faces").  A zone is a flat ring pulled up, so a
  corner or edge moves in XY and the top and bottom faces move the whole ceiling or floor.  The
  crosshair picks the handle, as placing does: a corner within ZE_SNAPPX on screen, else an edge,
  else the face the aim passes through.  A dragged point goes where Edge snap puts the aim
  (ZoneEdit_Snap) and otherwise to the aim on its own level's plane, on the grid; an edge moves by
  the grab point's offset, a side face along its outward normal, top and bottom by the height the
  aim passes nearest.  A move that would cross the outline keeps the last good one.
*/
// The point of segment a-b nearest the aim's line.
vector(vector eye, vector fwd, vector a, vector b) ZoneEdit_RayNear =
{
	local vector u, w;
	local float uu, uf, uw, fw, den;

	u = b - a; w = a - eye;
	uu = u * u; uf = u * fwd; uw = u * w; fw = fwd * w;
	den = uu - uf * uf;
	if (uu < 0.0001 || den < 0.0001) return a;
	return a + u * bound(0, (uf * fw - uw) / den, 1);
};

// The height where the aim passes nearest the vertical through x y (ZoneEdit_Pull's geometry).
float(vector eye, vector fwd, float x, float y, float keep) ZoneEdit_VertNear =
{
	local vector w;
	local float den;

	w = eye - [x, y, 0];
	den = 1 - fwd_z * fwd_z;
	if (den < 0.0001) return keep;
	return (w_z - fwd_z * (fwd * w)) / den;
};

// Where the aim crosses the level z, or FALSE (behind the eye, or looking along it).
float(vector eye, vector fwd, float z) ZoneEdit_AtLevel =
{
	local float t;

	if (fabs(fwd_z) < 0.0001) return FALSE;
	t = (z - eye_z) / fwd_z;
	if (t <= 0) return FALSE;
	ze_grab_at = eye + fwd * t;
	return TRUE;
};

// The outward normal of ring edge i of the zone as the drag found it, in XY (either winding).
vector(float i) ZoneEdit_SideOut =
{
	local float k, n, area;
	local vector a, b, nm;

	n = ze_onp;
	area = 0;
	for (k = 0; k < n; k = k + 1)
	{
		a = ze_orig[k]; b = ze_orig[(k + 1) % n];
		area = area + a_x * b_y - b_x * a_y;
	}
	a = ze_orig[i]; b = ze_orig[(i + 1) % n];
	nm = normalize([b_y - a_y, a_x - b_x, 0]);
	return (area >= 0) ? nm : -nm;      // counter-clockwise: the right of each edge is outside
};

// The nearest face of zone z the aim passes through: its distance, or ZE_REACH. Sets ze_pk/ze_pi.
float(vector eye, vector fwd, float z) ZoneEdit_FaceHit =
{
	local float i, n, first, best, d, s, lev, zz;
	local vector a, b, nm, q, u;

	first = zone_first[z]; n = zone_npts[z];
	best = ZE_REACH; ze_pk = ZEH_NONE;
	for (i = 0; i < n; i = i + 1)
	{
		a = zone_pt[first + i]; b = zone_pt[first + ((i + 1) % n)];
		nm = normalize([b_y - a_y, a_x - b_x, 0]);
		d = fwd * nm;
		if (fabs(d) < 0.0001) continue;
		d = ([a_x, a_y, eye_z] - eye) * nm / d;
		if (d <= 0 || d >= best) continue;
		q = eye + fwd * d;
		u = b - a; s = ((q - a) * u) / (u * u);
		if (s < 0 || s > 1 || q_z < zone_bottom[z] || q_z > zone_top[z]) continue;
		best = d; ze_pk = ZEH_SIDE; ze_pi = i; ze_pat = q;
	}
	for (lev = 0; lev < 2; lev = lev + 1)
	{
		zz = lev ? zone_top[z] : zone_bottom[z];
		if (!ZoneEdit_AtLevel(eye, fwd, zz)) continue;
		d = vlen(ze_grab_at - eye);
		if (d >= best) continue;
		if (!Zone_PointInside(z, [ze_grab_at_x, ze_grab_at_y, (zone_bottom[z] + zone_top[z]) * 0.5])) continue;
		best = d; ze_pk = lev ? ZEH_TOP : ZEH_BOT; ze_pi = 0; ze_pat = ze_grab_at;
	}
	return best;
};

// The handle of the selected zone under the aim.
void() ZoneEdit_Hover =
{
	local float z, i, n, first, lev, d, best, zz;
	local vector a, b, q;

	ze_hk = ZEH_NONE;
	z = ze_sel;
	if (z < 0 || z >= zone_count) return;
	first = zone_first[z]; n = zone_npts[z];
	best = ZE_SNAPPX * ui_cv_scale;
	for (i = 0; i < n; i = i + 1)
		for (lev = 0; lev < 2; lev = lev + 1)
		{
			a = zone_pt[first + i];
			a_z = lev ? zone_top[z] : zone_bottom[z];
			d = ZoneEdit_PxOff(ze_eye, ze_fwd, a);
			if (d < best) { best = d; ze_hk = ZEH_VERT; ze_hi = i; ze_hl = lev; ze_grab = a; }
		}
	if (ze_hk) return;
	for (i = 0; i < n; i = i + 1)
	{
		a = zone_pt[first + i]; b = zone_pt[first + ((i + 1) % n)];
		for (lev = 0; lev < 3; lev = lev + 1)
		{
			if (lev < 2)
			{
				zz = lev ? zone_top[z] : zone_bottom[z];
				q = ZoneEdit_RayNear(ze_eye, ze_fwd, [a_x, a_y, zz], [b_x, b_y, zz]);
			}
			else
				q = ZoneEdit_RayNear(ze_eye, ze_fwd, [a_x, a_y, zone_bottom[z]], [a_x, a_y, zone_top[z]]);
			d = ZoneEdit_PxOff(ze_eye, ze_fwd, q);
			if (d >= best) continue;
			best = d; ze_hi = i; ze_grab = q;
			if (lev < 2) { ze_hk = ZEH_EDGE; ze_hl = lev; }
			else { ze_hk = ZEH_VERT; ze_hl = 2; }
		}
	}
	if (ze_hk) return;
	if (ZoneEdit_FaceHit(ze_eye, ze_fwd, z) < ZE_REACH)
	{
		ze_hk = ze_pk; ze_hi = ze_pi; ze_hl = 0; ze_grab = ze_pat;
	}
};

string() ZoneEdit_HandleName =
{
	if (ze_hk == ZEH_VERT) return sprintf("corner %g%s", ze_hi + 1, (ze_hl == 2) ? "" : (ze_hl ? " (top)" : " (bottom)"));
	if (ze_hk == ZEH_EDGE) return sprintf("edge %g-%g %s", ze_hi + 1, (ze_hi + 1) % zone_npts[ze_sel] + 1, ze_hl ? "top" : "bottom");
	if (ze_hk == ZEH_SIDE) return sprintf("side %g-%g", ze_hi + 1, (ze_hi + 1) % zone_npts[ze_sel] + 1);
	if (ze_hk == ZEH_TOP) return sprintf("top  z %.1f", zone_top[ze_sel]);
	if (ze_hk == ZEH_BOT) return sprintf("bottom  z %.1f", zone_bottom[ze_sel]);
	return "";
};

string() ZoneEdit_EditLine =
{
	if (!ze_hk) return "aim at a corner, edge or face of the white zone; Mouse1 on another zone selects it";
	if (!ze_dragging) return sprintf("%s  -  hold Mouse1 to drag", ZoneEdit_HandleName());
	if (ze_dragbad) return sprintf("%s: refused, the outline would not stay simple", ZoneEdit_HandleName());
	return sprintf("dragging %s", ZoneEdit_HandleName());
};

void() ZoneEdit_EditBegin =
{
	if (ze_sel < 0 || ze_sel >= zone_count) { ZoneEdit_Note("Select a zone first"); return; }
	if (zone_npts[ze_sel] > ZE_MAXPTS)
	{
		ZoneEdit_Note(sprintf("%g corners: only zones of up to %g can be edited here", zone_npts[ze_sel], ZE_MAXPTS));
		return;
	}
	if (!ze_orig) ze_orig = memalloc(sizeof(vector) * ZE_MAXPTS);
	ZoneEdit_ToPlacing();
	ui_ze_state = ZE_E;
	ze_hk = ZEH_NONE;
	ze_dragging = ze_drop = FALSE;
	ZoneEdit_Note("Aim at a corner, edge or face; hold Mouse1 to drag it");
};

// The table is still the one the drag began on (a zone_reload, say, replaces it). Nested ifs:
// QC evaluates both sides of &&, and zone_npts[-1] takes the VM down.
float() ZoneEdit_DragSame =
{
	if (ze_dz < 0 || ze_dz >= zone_count) return FALSE;
	if (zone_npts[ze_dz] != ze_onp || zone_first[ze_dz] != ze_dfirst) return FALSE;
	return (zone_count == ze_dcount && zone_ptcount == ze_dpts && zone_crc == ze_dcrc);
};

// The zone as it was when the drag began.
void() ZoneEdit_DragRestore =
{
	local float i;

	for (i = 0; i < ze_onp; i = i + 1)
		zone_pt[ze_dfirst + i] = ze_orig[i];
	zone_bottom[ze_dz] = ze_obot; zone_top[ze_dz] = ze_otop;
	Zone_Finish(ze_dz);
};

void() ZoneEdit_DragEnd =
{
	ze_dragging = ze_drop = ze_dragbad = FALSE;
	if (ze_dcrc != "") strunzone(ze_dcrc);
	ze_dcrc = "";
};

void() ZoneEdit_DragCancel =
{
	if (!ze_dragging) return;
	if (ZoneEdit_DragSame())
	{
		ZoneEdit_DragRestore();
		ZoneEdit_Note("Drag cancelled; the zone is as it was");
	}
	else
		ZoneEdit_Note("The zone table changed under the drag; it was let go");
	ZoneEdit_DragEnd();
};

void() ZoneEdit_GrabStart =
{
	local float i;

	if (zone_npts[ze_sel] > ZE_MAXPTS) { ZoneEdit_Note("That zone has too many corners to edit here"); return; }
	ze_dz = ze_sel;
	ze_onp = zone_npts[ze_dz];
	ze_dfirst = zone_first[ze_dz];
	ze_dcount = zone_count; ze_dpts = zone_ptcount;
	if (ze_dcrc != "") strunzone(ze_dcrc);
	ze_dcrc = strzone(zone_crc);
	for (i = 0; i < ze_onp; i = i + 1)
		ze_orig[i] = zone_pt[ze_dfirst + i];
	ze_obot = zone_bottom[ze_dz]; ze_otop = zone_top[ze_dz];
	ze_dragging = TRUE; ze_dragbad = FALSE;
};

// One frame of a drag: the candidate goes through ze_pts (ZoneEdit_PolygonValid's scratch).
void() ZoneEdit_DragStep =
{
	local float z, i, n, g, snapped, lev, d, nb, nt;
	local vector to, dv, nm;

	if (!ZoneEdit_DragSame()) { ZoneEdit_DragCancel(); return; }
	z = ze_dz; n = ze_onp;
	g = max(1, ze_grid);
	// Edge snap's point is the world's: a corner or edge on one level takes it only near that level
	// (a top corner aimed past the zone would jump to the floor's XY far beyond it); a vertical edge
	// or side, within the zone's height; the bottom face, a snap within 64 of the grab's vertical
	// (the floor under the zone is its target, not a ledge across the room).
	if (ze_hk == ZEH_SIDE || (ze_hk == ZEH_VERT && ze_hl == 2)) lev = (ze_sat_z > ze_obot - 48 && ze_sat_z < ze_otop + 48);
	else if (ze_hk == ZEH_VERT || ze_hk == ZEH_EDGE) lev = (fabs(ze_sat_z - ze_grab_z) < 48);
	else lev = (vlen([ze_sat_x - ze_grab_x, ze_sat_y - ze_grab_y, 0]) < 64);
	snapped = (ze_edges && ze_hitok && ze_skind != ZES_NONE && lev);
	for (i = 0; i < n; i = i + 1)
		ze_pts[i] = ze_orig[i];
	nb = ze_obot; nt = ze_otop;
	if (ze_hk == ZEH_TOP || ze_hk == ZEH_BOT)
	{
		d = ZoneEdit_VertNear(ze_eye, ze_fwd, ze_grab_x, ze_grab_y, ze_grab_z);
		if (ze_hk == ZEH_BOT && snapped && ze_skind <= ZES_MAPE) d = ze_hit_z;      // the floor's own height
		else if (ze_snap) d = (ze_hk == ZEH_BOT) ? floor(d / g) * g : rint(d / g) * g;
		if (ze_hk == ZEH_TOP) nt = bound(nb + ZE_MINH, d, nb + ZE_MAXH);
		else nb = bound(nt - ZE_MAXH, d, nt - ZE_MINH);
	}
	else
	{
		// Where the grab point goes: Edge snap's point, else the aim on the grab point's level.
		if (snapped) to = [ze_sat_x, ze_sat_y, ze_grab_z];
		else if (ze_hk == ZEH_VERT && ze_hl == 2 && ze_hitok && ze_raw_z > ze_obot - 48 && ze_raw_z < ze_otop + 48)
			to = [ze_raw_x, ze_raw_y, ze_grab_z];  // a corner's vertical edge goes where the aim meets the world, as placing
		else if (ZoneEdit_AtLevel(ze_eye, ze_fwd, ze_grab_z))
			to = ze_grab_at;
		else if (ze_hk == ZEH_SIDE && ze_hitok && ze_raw_z > ze_obot - 48 && ze_raw_z < ze_otop + 48)
			to = [ze_raw_x, ze_raw_y, ze_grab_z];  // a side taken above the eye, aimed at the floor
		else
			return;
		dv = to - ze_grab; dv_z = 0;
		if (ze_hk == ZEH_VERT)
		{
			if (!snapped && ze_snap) to = [rint(to_x / g) * g, rint(to_y / g) * g, 0];
			ze_pts[ze_hi] = [to_x, to_y, 0];
		}
		else if (ze_hk == ZEH_EDGE)
		{
			if (!snapped && ze_snap) dv = [rint(dv_x / g) * g, rint(dv_y / g) * g, 0];
			ze_pts[ze_hi] = ze_orig[ze_hi] + dv;
			ze_pts[(ze_hi + 1) % n] = ze_orig[(ze_hi + 1) % n] + dv;
		}
		else if (ze_hk == ZEH_SIDE)
		{
			nm = ZoneEdit_SideOut(ze_hi);
			d = dv * nm;
			if (!snapped && ze_snap) d = rint(d / g) * g;
			ze_pts[ze_hi] = ze_orig[ze_hi] + nm * d;
			ze_pts[(ze_hi + 1) % n] = ze_orig[(ze_hi + 1) % n] + nm * d;
		}
	}
	ze_np = n;
	ze_dragbad = !ZoneEdit_PolygonValid();
	ze_np = 0;
	if (ze_dragbad) return;
	for (i = 0; i < n; i = i + 1)
	{
		dv = ze_pts[i]; dv_z = 0;
		zone_pt[ze_dfirst + i] = dv;
	}
	zone_bottom[z] = nb; zone_top[z] = nt;
	Zone_Finish(z);
};

void() ZoneEdit_DragDrop =
{
	local float i, same, first;

	ze_drop = FALSE;
	if (!ze_dragging) return;
	if (!ZoneEdit_DragSame()) { ZoneEdit_DragCancel(); return; }
	ZoneEdit_DragEnd();
	first = ze_dfirst;
	same = (zone_bottom[ze_dz] == ze_obot && zone_top[ze_dz] == ze_otop);
	for (i = 0; same && i < ze_onp; i = i + 1)
		if (zone_pt[first + i] != ze_orig[i]) same = FALSE;
	if (same) { ZoneEdit_Note(sprintf("%s unchanged", ZoneEdit_HandleName())); return; }
	ZoneEdit_Touch();
	if (zone_td_kind[ze_sel] == ZTD_POS && !Zone_PointInside(ze_sel, zone_td_pos[ze_sel] + '0 0 2'))
		ZoneEdit_Note(sprintf("%s moved; its custom spawn is now outside: Set spawn again", ZoneEdit_Label(ze_sel)));
	else
		ZoneEdit_Note(sprintf("%s: moved %s (not saved)", ZoneEdit_Label(ze_sel), ZoneEdit_HandleName()));
};

// A click on nothing of the selected zone selects the zone the aim passes through.
void() ZoneEdit_EditPick =
{
	local float z, d, best, pick;

	best = ZE_REACH; pick = -1;
	for (z = 0; z < zone_count; z = z + 1)
	{
		d = ZoneEdit_FaceHit(ze_eye, ze_fwd, z);
		if (d < best) { best = d; pick = z; }
	}
	if (pick < 0 || pick == ze_sel) return;
	if (zone_npts[pick] > ZE_MAXPTS) { ZoneEdit_Note("That zone has too many corners to edit here"); return; }
	ze_sel = pick;
	ZoneEdit_Note(sprintf("selected %s", ZoneEdit_Label(pick)));
};

// The edit state's draw pass, after ZoneEdit_Aim: clicks, the drag, then the handles.
void() ZoneEdit_EditFrame =
{
	local float z, n, first;
	local vector a, b;

	z = ze_sel;
	if (z < 0 || z >= zone_count) { ZoneEdit_ToPanel(); return; }
	if (ze_back)
	{
		ze_back = FALSE;
		if (ze_dragging) ZoneEdit_DragCancel();
		else { ZoneEdit_ToPanel(); return; }
	}
	if (ze_click)
	{
		ze_click = FALSE;
		if (!ze_dragging)
		{
			ZoneEdit_Hover();
			if (ze_hk) ZoneEdit_GrabStart();
			else ZoneEdit_EditPick();
			if (ze_dragging) ZoneEdit_Aim();    // the snap now leaves this zone out
		}
	}
	if (ze_dragging) ZoneEdit_DragStep();
	else ZoneEdit_Hover();
	if (ze_drop) ZoneEdit_DragDrop();
	z = ze_sel;                         // a drop renumbers the table (ZoneEdit_Touch)

	// The lit side face, filled in the world; corners, edges and rings are ZoneEdit_Handles2D's.
	if (ze_hk == ZEH_SIDE && ze_hi < zone_npts[z])
	{
		first = zone_first[z]; n = zone_npts[z];
		a = zone_pt[first + ze_hi]; b = zone_pt[first + ((ze_hi + 1) % n)];
		Zone_Face([a_x, a_y, zone_bottom[z]], [b_x, b_y, zone_bottom[z]], [a_x, a_y, zone_top[z]],
		          [b_x, b_y, zone_top[z]], ZoneEdit_HandleCol(), 0.25);
	}
	if (ze_dragging && ze_skind) ZoneEdit_SnapDraw3D(ze_eye);
};

vector() ZoneEdit_HandleCol =
{
	if (!ze_dragging) return '1 0.6 0.15';     // lit
	return ze_dragbad ? ZEC_WARN : '0.35 1 0.45';
};

/*
  The handles on screen, in the HUD pass: a zone's bottom sits at or under the floor, so lines in
  the world would be hidden where they matter (the ftesurf_zone_xray shader did not show through
  in the arm's screenshots).  Filled squares only (drawfill), no polygon batch: see cl_plot.qc's
  ORDER note.
*/
// Segment a-b clipped to the screen (Liang-Barsky): FALSE when none of it is on it.
vector ze_clip_a, ze_clip_b;
float(vector a, vector b) ZoneEdit_ClipScreen =
{
	local vector vs, d;
	local float t0, t1, k, p, q, e;

	vs = getproperty(VF_SCREENVSIZE);
	d = b - a; t0 = 0; t1 = 1;
	for (k = 0; k < 4; k = k + 1)
	{
		if (k == 0) { p = -d_x; q = a_x; }
		else if (k == 1) { p = d_x; q = vs_x - a_x; }
		else if (k == 2) { p = -d_y; q = a_y; }
		else { p = d_y; q = vs_y - a_y; }
		if (p == 0) { if (q < 0) return FALSE; continue; }
		e = q / p;
		if (p < 0) { if (e > t1) return FALSE; if (e > t0) t0 = e; }
		else { if (e < t0) return FALSE; if (e < t1) t1 = e; }
	}
	ze_clip_a = a + d * t0; ze_clip_b = a + d * t1;
	return TRUE;
};

// A world segment as dots on screen, clipped to the near side of the eye.
void(vector a, vector b, vector eye, vector fwd, vector col, float s) ZoneEdit_Dots =
{
	local float da, db, k, len, step;
	local vector pa, pb, dir;

	da = (a - eye) * fwd - 8; db = (b - eye) * fwd - 8;
	if (da < 0 && db < 0) return;
	if (da < 0) a = a + (b - a) * (da / (da - db));
	else if (db < 0) b = b + (a - b) * (db / (db - da));
	pa = project(a); pb = project(b); pa_z = pb_z = 0;
	if (!ZoneEdit_ClipScreen(pa, pb)) return;
	pa = ze_clip_a; pb = ze_clip_b;
	len = vlen(pb - pa);
	step = s * 2;
	dir = (len > 0) ? normalize(pb - pa) : '0 0 0';
	for (k = 0; k <= len; k = k + step)
		drawfill(pa + dir * k - [s, s] * 0.5, [s, s], col, 1, 0);
};

void(vector p, vector eye, vector fwd, vector col, float r, float fill) ZoneEdit_Square =
{
	local float t;
	local vector sp;

	if ((p - eye) * fwd < 8) return;
	sp = project(p); sp_z = 0;
	if (fill) { drawfill(sp - [r, r], [r * 2, r * 2], col, 0.85, 0); return; }
	t = max(1, rint(r / 3));
	drawfill(sp + [-r, -r], [r * 2, t], col, 1, 0);
	drawfill(sp + [-r, r - t], [r * 2, t], col, 1, 0);
	drawfill(sp + [-r, -r], [t, r * 2], col, 1, 0);
	drawfill(sp + [r - t, -r], [t, r * 2], col, 1, 0);
};

void(float rsz) ZoneEdit_Handles2D =
{
	local float z, i, n, first, s, lev, zz;
	local vector eye, fwd, a, b, col;

	z = ze_sel;
	if (ui_ze_state != ZE_E || ze_cursor || z < 0 || z >= zone_count) return;
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES)); fwd = v_forward;
	first = zone_first[z]; n = zone_npts[z];
	s = max(2, rint(rsz / 4));
	for (i = 0; i < n; i = i + 1)
	{
		a = zone_pt[first + i];
		b = zone_pt[first + ((i + 1) % n)];
		ZoneEdit_Dots([a_x, a_y, zone_bottom[z]], [b_x, b_y, zone_bottom[z]], eye, fwd, ZEC_DIM, max(1, s * 0.5));
		ZoneEdit_Square([a_x, a_y, zone_bottom[z]], eye, fwd, ZEC_TEXT, s * 1.5, FALSE);
		ZoneEdit_Square([a_x, a_y, zone_top[z]], eye, fwd, ZEC_DIM, s * 1.5, FALSE);
	}
	if (!ze_hk || ze_hi >= n) return;
	col = ZoneEdit_HandleCol();
	a = zone_pt[first + ze_hi]; b = zone_pt[first + ((ze_hi + 1) % n)];
	if (ze_hk == ZEH_VERT)
	{
		if (ze_hl != 1) ZoneEdit_Square([a_x, a_y, zone_bottom[z]], eye, fwd, col, s * 2.5, TRUE);
		if (ze_hl != 0) ZoneEdit_Square([a_x, a_y, zone_top[z]], eye, fwd, col, s * 2.5, TRUE);
		if (ze_hl == 2) ZoneEdit_Dots([a_x, a_y, zone_bottom[z]], [a_x, a_y, zone_top[z]], eye, fwd, col, s);
	}
	else if (ze_hk == ZEH_EDGE)
	{
		zz = ze_hl ? zone_top[z] : zone_bottom[z];
		ZoneEdit_Dots([a_x, a_y, zz], [b_x, b_y, zz], eye, fwd, col, s);
	}
	else if (ze_hk == ZEH_SIDE)
	{
		for (lev = 0; lev < 2; lev = lev + 1)
		{
			zz = lev ? zone_top[z] : zone_bottom[z];
			ZoneEdit_Dots([a_x, a_y, zz], [b_x, b_y, zz], eye, fwd, col, s);
		}
		ZoneEdit_Dots([a_x, a_y, zone_bottom[z]], [a_x, a_y, zone_top[z]], eye, fwd, col, s);
		ZoneEdit_Dots([b_x, b_y, zone_bottom[z]], [b_x, b_y, zone_top[z]], eye, fwd, col, s);
	}
	else
	{
		zz = (ze_hk == ZEH_TOP) ? zone_top[z] : zone_bottom[z];
		for (i = 0; i < n; i = i + 1)
		{
			a = zone_pt[first + i]; b = zone_pt[first + ((i + 1) % n)];
			ZoneEdit_Dots([a_x, a_y, zz], [b_x, b_y, zz], eye, fwd, col, s);
		}
	}
};
