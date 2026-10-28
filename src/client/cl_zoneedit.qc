/*
===========================================================================
  Patch 671 extends this editor: mouse/cursor switching, title dragging, XYZ
  snapping, simple polygon outlines, and six local map settings. Steam roles
  and publishing are separate: no identity or rights inferred from names.

  Patch 669: THE ZONE EDITOR, part one -- make and move zones in the game.

  The owner, 12 Oct 2026: Momentum's zone editor lets you "noclip around using
  your mouse on the world to place the corners ... it usually snaps to 16 unit
  grid, or the actual world geometry, you lay the floor and then pull it
  upwards for height", and about 870 KSF-only maps have no zones at all.

  WHAT IT EDITS is this client's own zone table (sh_zones.qc), the one
  cl_zones.qc draws.  Nothing is sent anywhere.  `Save` writes Momentum's zone
  JSON as maps/zones/local/<map>.json, which QC's fopen puts under
  ftesurf/data/ (cl_zonedl.qc's note) and which both VMs already read FIRST:
  so on your own hosted game the next map load times with it, and on somebody
  else's server it only changes what YOU are shown.  A hosted game posts no
  times (sv_lobby.qc, "Ranked = official servers only"), and a lobby's zones
  are its own files: no route from here to the board.  Getting a file to the
  lobbies is part two and is not in this file.

  TWO MODES, as Momentum has them.  The PANEL holds the mouse: tracks, the
  zones of one in course order, add / re-place / delete, grid and snap, save.
  PLACING gives the mouse back: you fly (V is noclip) and aim with the
  crosshair; MOUSE1 sets the first floor corner, then the opposite one, then
  you look up to pull the height and click again.  MOUSE2 steps back, the
  wheel changes the grid, ESC returns to the panel.  A new zone is an
  axis-aligned box; a zone that came from a file keeps whatever ring it has.

  THE TYPE OF A CHECKPOINT REGION IS ITS POSITION IN THE FILE (Zone_AddTrack),
  so the table is renumbered after every change: stages 1..n with no gap, the
  end one past the last, checkpoint ordinals 1.. across the track in course
  order.  A new stage goes after the last one and a new checkpoint at the end
  of the selected zone's segment.

  NOT HERE YET (BACKLOG): rings that are not boxes, moving one corner, a
  zone's order in its track, map settings such as the speed cap, cancel and
  bhop regions (they are listed and can be deleted, not made).
===========================================================================
*/

#define UIC_ZONEEDIT 256            // cl_hud.qc's cursor register: the next free bit

#define ZE_OFF    0
#define ZE_PANEL  1                 // the mouse is the panel's
#define ZE_A      2                 // placing: the first floor corner
#define ZE_B      3                 // the opposite corner
#define ZE_H      4                 // the height
#define ZE_P      5                 // polygon outline
#define ZE_MAXPTS 64

#define ZEB_M1    1
#define ZEB_M2    2
#define ZEB_WUP   4
#define ZEB_WDN   8
#define ZEB_ENTER 16

#define ZE_REACH  16384             // how far the aim is traced
#define ZE_MINH   16                // a zone is at least this tall
#define ZE_MAXH   16384             // and at most this

// The Dusk look's own colours (sh_ui.qc); the box being placed has one of its own.
#define ZEC_PANEL SUI_THEME_PANEL
#define ZEC_LINE  SUI_THEME_EDGE
#define ZEC_TEXT  SUI_THEME_TEXT
#define ZEC_DIM   SUI_THEME_DIM
#define ZEC_HOT   SUI_THEME_HOVER
#define ZEC_SEL   SUI_THEME_ACCENT
#define ZEC_WARN  SUI_THEME_WARN
#define ZEC_NEW   '1.00 0.95 0.35'

float  ui_ze_state;                 // ZE_*
float  ze_track;                    // the track the panel shows: 0 main, 1.. a bonus
float  ze_sel;                      // the selected zone, -1 none
float  ze_dirty;                    // changed since the last save or load
float  ze_saved_ok;                 // P815: the last ZoneEdit_Save put its file in place
string ze_saved_sha;                // P815: sha256 of the bytes that save wrote (cl_zonepublish.qc)
string ze_map;                      // the map the edits belong to
float  ze_grid;                     // snap, units
float  ze_snap;                     // 1 the grid, 0 the surface as hit
float  ze_mouse_seen;
vector ze_mouse;
vector ze_panel_p, ze_panel_s;
float  ze_scroll;

// The zone being placed.
float  ze_ntype, ze_nseg, ze_ncp;   // what it will be
float  ze_replace;                  // the zone it replaces, -1 a new one
vector ze_a, ze_b;                  // the floor's two corners (z of ze_a is the floor)
float  ze_h;                        // its height while it is pulled
vector ze_hit;                      // where the aim meets the world, snapped
float  ze_hitok;
float  ze_hitz;                     // ...and its height as hit, before the snap
float  ze_floor;                    // the first corner's: where a new start's spawn stands
float  ze_rsig;                     // the table when a re-place began (count and points)
float  ze_real_t;                   // cltime of the last MOUSE1 release a DEVICE made in the panel
float  ze_click, ze_back;           // asked for by the input handler, done in the draw pass
string ze_press;                    // `zone_edit press <id>`: that element counts as clicked once
void(float real) ZonePub_Begin;
void() ZonePub_Pump;
float(float scan) ZonePub_Key;
void(vector scr) ZonePub_Draw;
string ze_note;                     // one line for the panel's foot
float  ze_note_t;
float  ze_saved_n;                  // zones in the last file written (the status line)

float ze_cursor, ze_drag, ze_positioned;
vector ze_drag_offset, ze_window;
float ze_poly, ze_np, ze_edges, ze_close;
vector *ze_pts;
float ze_lastrow, ze_lastclick;
float ze_settings, ze_field, ze_caret, ze_mode;
string ze_text;
float ze_values[MAPSET_COUNT];
float ze_cap_open;                  // P841: the Speed cap the panel opened with
float *ze_field_keys;

float() ZoneEdit_PolygonValid;
void() ZoneEdit_PolygonClick;
void() ZoneEdit_PolygonClose;
void() ZoneEdit_PolygonGhost;
vector(vector p) ZoneEdit_EdgeSnap;
float(float top) ZoneEdit_Height;
vector(float z) ZoneEdit_Interior;
float() ZoneEdit_AddPolygon;
void() ZoneEdit_SnapSelected;
void(float z) ZoneEdit_RowClick;
void() ZoneEdit_ToggleMouse;
void() ZoneEdit_SettingsOpen;
void(float i) ZoneEdit_SettingEdit;
void() ZoneEdit_SettingApply;
void(float evtype, float scan, float char) ZoneEdit_FieldKey;
float(float c) ZoneEdit_Paste;
void() ZoneEdit_SettingsSave;
void(vector p, float w, float y, float rowh, float tsz) ZoneEdit_SettingsDraw;
void(float mode) ZoneEdit_SettingMode;
void() ZoneEdit_ResetSpawn;
void(vector p) ZoneEdit_DragStart;

void(string s) ZoneEdit_Note =
{
	if (ze_note != "")
		strunzone(ze_note);
	ze_note = strzone(s);
	ze_note_t = cltime;
	print(sprintf("^5zone_edit^7: %s\n", s));
};

string(float z) ZoneEdit_Label =
{
	local float t;

	t = zone_type[z];
	if (t == ZONE_START)      return "start";
	if (t == ZONE_END)        return "end";
	if (t == ZONE_STAGE)      return sprintf("stage %g", zone_seg[z] + 1);
	if (t == ZONE_CHECKPOINT) return sprintf("checkpoint %g", zone_cp[z]);
	return Zone_TypeName(t);
};

/*
===========================================================================
  The table, kept in the shape the file gives it
===========================================================================
*/

// A zone's place in its track's course: its segment, then start or stage before
// the checkpoints in it, then the checkpoint's ordinal.
float(float z) ZoneEdit_Order =
{
	local float t;

	t = zone_type[z];
	if (t == ZONE_END)
		return 900000;
	if (t == ZONE_CHECKPOINT)
		return zone_seg[z] * 1000 + 1 + zone_cp[z];
	return zone_seg[z] * 1000;
};

/*
  Stages 1..n with no gap, the end one past the last, checkpoints 1.. along the
  course.  Regions of one checkpoint share an ordinal and keep sharing it.  A
  checkpoint whose stage went falls back into the stage before.

  Worked out into ze_tmp and ze_st FROM THE OLD NUMBERS and only then written
  back.  The first cut renumbered in place, marking a moved row with a negative
  segment, and its second stage's pass then read those marks as "before every
  stage": with two stages or more every checkpoint from the first stage on
  landed in stage 1 (found by the review; the arm's course had one stage).
*/
#define ZE_STAGES 64
float ze_tmp[ZONE_MAX];             // a row's new segment, then a checkpoint's sort weight
float ze_st[ZE_STAGES];             // the track's old stage segments, ascending, no repeats

void(float track) ZoneEdit_RenumberTrack =
{
	local float z, i, n, lo, last, c, top;

	// A stage with no segment (a legacy BSP trigger without its `stage` key) cannot be
	// segment 0, which is the start's: it goes after the last stage there is.
	top = 0;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == track)
		if (zone_seg[z] > top)
			top = zone_seg[z];
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == track)
		if (zone_type[z] == ZONE_STAGE)
		if (zone_seg[z] < 1)
			zone_seg[z] = top + 1;

	// The stages' old segments in order.
	n = 0;
	last = 0;
	while (n < ZE_STAGES)
	{
		lo = 0;
		for (z = 0; z < zone_count; z = z + 1)
			if (zone_track[z] == track)
			if (zone_type[z] == ZONE_STAGE)
			if (zone_seg[z] > last)
			if (!lo || zone_seg[z] < lo)
				lo = zone_seg[z];
		if (!lo)
			break;
		ze_st[n] = lo;
		n = n + 1;
		last = lo;
	}

	// A row's new segment: how many stages start at or before its old one.
	for (z = 0; z < zone_count; z = z + 1)
	{
		ze_tmp[z] = 0;
		if (zone_track[z] != track)
			continue;
		if (zone_type[z] == ZONE_END)
			ze_tmp[z] = n + 1;
		else if (zone_type[z] == ZONE_STAGE || zone_type[z] == ZONE_CHECKPOINT)
		{
			c = 0;
			for (i = 0; i < n; i = i + 1)
				if (ze_st[i] <= zone_seg[z])
					c = i + 1;
			ze_tmp[z] = c;
		}
	}
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == track)
		if (zone_type[z] <= ZONE_CHECKPOINT)
			zone_seg[z] = ze_tmp[z];

	// Checkpoints: by new segment, then the ordinal they had (a half is "after that one").
	for (z = 0; z < zone_count; z = z + 1)
	{
		ze_tmp[z] = -1;
		if (zone_track[z] == track)
		if (zone_type[z] == ZONE_CHECKPOINT)
			ze_tmp[z] = zone_seg[z] * 10000 + max(0, zone_cp[z]);
	}
	c = 0;
	last = -1;
	while (1)
	{
		lo = -1;
		for (z = 0; z < zone_count; z = z + 1)
			if (ze_tmp[z] > last)
			if (lo < 0 || ze_tmp[z] < lo)
				lo = ze_tmp[z];
		if (lo < 0)
			break;
		c = c + 1;
		for (z = 0; z < zone_count; z = z + 1)
			if (ze_tmp[z] == lo)
				zone_cp[z] = c;
		last = lo;
	}
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == track)
		if (zone_type[z] != ZONE_CHECKPOINT)
		if (zone_type[z] <= ZONE_END || zone_type[z] == ZONE_STAGE)
			zone_cp[z] = 0;
};

// Where the file puts a zone: the tracks in order, each in course order, then the regions
// that belong to no track.  Under 2^24, so a float holds it exactly.
float(float z) ZoneEdit_Key =
{
	if (zone_type[z] > ZONE_CHECKPOINT)
		return 14000000 + zone_type[z];
	return zone_track[z] * 1000000 + ZoneEdit_Order(z);
};

void(float i, float j) ZoneEdit_Swap =
{
	local float f;
	local vector v;
	local string s;

	f = zone_type[i];    zone_type[i]    = zone_type[j];    zone_type[j]    = f;
	f = zone_track[i];   zone_track[i]   = zone_track[j];   zone_track[j]   = f;
	f = zone_seg[i];     zone_seg[i]     = zone_seg[j];     zone_seg[j]     = f;
	f = zone_cp[i];      zone_cp[i]      = zone_cp[j];      zone_cp[j]      = f;
	f = zone_first[i];   zone_first[i]   = zone_first[j];   zone_first[j]   = f;
	f = zone_npts[i];    zone_npts[i]    = zone_npts[j];    zone_npts[j]    = f;
	f = zone_bottom[i];  zone_bottom[i]  = zone_bottom[j];  zone_bottom[j]  = f;
	f = zone_top[i];     zone_top[i]     = zone_top[j];     zone_top[j]     = f;
	f = zone_td_kind[i]; zone_td_kind[i] = zone_td_kind[j]; zone_td_kind[j] = f;
	f = zone_td_yaw[i];  zone_td_yaw[i]  = zone_td_yaw[j];  zone_td_yaw[j]  = f;
	v = zone_td_pos[i];  zone_td_pos[i]  = zone_td_pos[j];  zone_td_pos[j]  = v;
	s = zone_td_name[i]; zone_td_name[i] = zone_td_name[j]; zone_td_name[j] = s;
};

/*
  After any change: the numbering, the FILE'S ORDER, each zone's bounds, the hash.
  The order matters because the hash walks the table: a course built out of order would
  hash one way on screen and another once it had been through a file.  An insertion sort,
  so regions of one checkpoint keep the order they had, and a table that came from a file
  does not move at all.
*/
void() ZoneEdit_Touch =
{
	local float z, t, top, j;

	top = 0;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] > top)
			top = zone_track[z];
	for (t = 0; t <= top; t = t + 1)
		ZoneEdit_RenumberTrack(t);
	for (z = 1; z < zone_count; z = z + 1)
		for (j = z; j > 0; j = j - 1)
		{
			if (ZoneEdit_Key(j - 1) <= ZoneEdit_Key(j))
				break;
			ZoneEdit_Swap(j - 1, j);
			if (ze_sel == j)
				ze_sel = j - 1;
			else if (ze_sel == j - 1)
				ze_sel = j;
		}
	for (z = 0; z < zone_count; z = z + 1)
		Zone_Finish(z);
	Zone_Hash();
	ze_dirty = TRUE;
};

void(float z) ZoneEdit_Remove =
{
	local float i, f, n;

	if (z < 0 || z >= zone_count)
		return;
	f = zone_first[z];
	n = zone_npts[z];
	for (i = f; i + n < zone_ptcount; i = i + 1)
		zone_pt[i] = zone_pt[i + n];
	zone_ptcount = zone_ptcount - n;
	if (zone_td_name[z] != "")
		strunzone(zone_td_name[z]);
	for (i = z; i + 1 < zone_count; i = i + 1)
	{
		zone_type[i]    = zone_type[i + 1];
		zone_track[i]   = zone_track[i + 1];
		zone_seg[i]     = zone_seg[i + 1];
		zone_cp[i]      = zone_cp[i + 1];
		zone_first[i]   = zone_first[i + 1];
		zone_npts[i]    = zone_npts[i + 1];
		zone_bottom[i]  = zone_bottom[i + 1];
		zone_top[i]     = zone_top[i + 1];
		zone_td_kind[i] = zone_td_kind[i + 1];
		zone_td_pos[i]  = zone_td_pos[i + 1];
		zone_td_yaw[i]  = zone_td_yaw[i + 1];
		zone_td_name[i] = zone_td_name[i + 1];
	}
	zone_count = zone_count - 1;
	zone_td_name[zone_count] = "";
	zone_td_kind[zone_count] = ZTD_NONE;
	for (i = 0; i < zone_count; i = i + 1)
		if (zone_first[i] > f)
			zone_first[i] = zone_first[i] - n;
};

// A box from two opposite floor corners.  Returns its index, -1 when the table is full.
float(float type, float track, float seg, float cpn, vector a, vector b, float bottom, float top) ZoneEdit_AddBox =
{
	local float z;
	local vector mn, mx;

	if (zone_count >= ZONE_MAX || zone_ptcount + 4 > ZONE_MAX_POINTS)
		return -1;
	mn = [min(a_x, b_x), min(a_y, b_y), 0];
	mx = [max(a_x, b_x), max(a_y, b_y), 0];
	z = zone_count;
	zone_type[z]    = type;
	zone_track[z]   = track;
	zone_seg[z]     = seg;
	zone_cp[z]      = cpn;
	zone_first[z]   = zone_ptcount;
	zone_npts[z]    = 4;
	zone_bottom[z]  = bottom;
	zone_top[z]     = top;
	zone_td_kind[z] = ZTD_NONE;
	zone_td_pos[z]  = '0 0 0';
	zone_td_yaw[z]  = 0;
	zone_td_name[z] = "";
	zone_pt[zone_ptcount + 0] = [mn_x, mn_y, 0];
	zone_pt[zone_ptcount + 1] = [mx_x, mn_y, 0];
	zone_pt[zone_ptcount + 2] = [mx_x, mx_y, 0];
	zone_pt[zone_ptcount + 3] = [mn_x, mx_y, 0];
	zone_ptcount = zone_ptcount + 4;
	zone_count = zone_count + 1;
	Zone_Finish(z);
	return z;
};

// Where `!r` puts you for a start or a stage: the middle of its floor, facing `yaw`.
void(float z, float yaw) ZoneEdit_DestCentre =
{
	local float i, n;
	local vector c;

	n = zone_npts[z];
	c = '0 0 0';
	for (i = 0; i < n; i = i + 1)
		c = c + zone_pt[zone_first[z] + i];
	c = c * (1 / max(1, n));
	if (!Zone_XYInRing(z, c_x, c_y)) c = ZoneEdit_Interior(z);
	if (zone_td_name[z] != "")
		strunzone(zone_td_name[z]);
	zone_td_name[z] = "";
	zone_td_kind[z] = ZTD_POS;
	zone_td_pos[z]  = [c_x, c_y, zone_bottom[z]];
	zone_td_yaw[z]  = yaw;
};

float(float track, float type) ZoneEdit_Has =
{
	local float z;

	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == track)
		if (zone_type[z] == type)
			return TRUE;
	return FALSE;
};

/*
===========================================================================
  tables -> JSON, the shape Zone_LoadJson reads back
===========================================================================
*/
// Nine significant digits bring a float back exactly; three decimals did not (a top that
// is bottom + height moved by 0.001 on its way through a file, which the hash prints).
string(float v) ZoneEdit_Num =
{
	if (v == rint(v))
		return sprintf("%.0f", v);
	return sprintf("%.9g", v);
};

void(filestream f, float z) ZoneEdit_WriteRegion =
{
	local float i, n, first;
	local vector p;
	local string nm;

	first = zone_first[z];
	n = zone_npts[z];
	fputs(f, "{\"points\":[");
	for (i = 0; i < n; i = i + 1)
	{
		p = zone_pt[first + i];
		fputs(f, sprintf("%s[%s,%s]", i ? "," : "", ZoneEdit_Num(p_x), ZoneEdit_Num(p_y)));
	}
	fputs(f, sprintf("],\"bottom\":%s,\"height\":%s", ZoneEdit_Num(zone_bottom[z]),
	                 ZoneEdit_Num(zone_top[z] - zone_bottom[z])));
	if (zone_td_kind[z] == ZTD_POS)
	{
		p = zone_td_pos[z];
		fputs(f, sprintf(",\"teleDestPos\":[%s,%s,%s],\"teleDestYaw\":%s", ZoneEdit_Num(p_x),
		                 ZoneEdit_Num(p_y), ZoneEdit_Num(p_z), ZoneEdit_Num(zone_td_yaw[z])));
	}
	else if (zone_td_kind[z] == ZTD_NAME)
	{
		// A targetname from the BSP: the two characters a JSON string cannot hold bare.
		nm = strreplace("\\", "\\\\", zone_td_name[z]);
		nm = strreplace("\"", "\\\"", nm);
		fputs(f, sprintf(",\"teleDestTargetname\":\"%s\"", nm));
	}
	fputs(f, "}");
};

// Every region that matches, comma separated; seg or cpn -1 is "any".
float(filestream f, float type, float track, float seg, float cpn) ZoneEdit_WriteRegions =
{
	local float z, n;

	n = 0;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_type[z] == type)
		if (zone_track[z] == track)
		if (seg < 0 || zone_seg[z] == seg)
		if (cpn < 0 || zone_cp[z] == cpn)
		{
			if (n)
				fputs(f, ",");
			ZoneEdit_WriteRegion(f, z);
			n = n + 1;
		}
	return n;
};

void(filestream f, float track) ZoneEdit_WriteTrack =
{
	local float z, nseg, si, c, last;

	nseg = 1;       // segments[0] is always there: it holds the start
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == track)
		if (zone_type[z] == ZONE_STAGE || zone_type[z] == ZONE_CHECKPOINT)
		if (zone_seg[z] + 1 > nseg)
			nseg = zone_seg[z] + 1;
	fputs(f, "{\"zones\":{\"segments\":[");
	for (si = 0; si < nseg; si = si + 1)
	{
		// checkpoints[0] is the segment's own start: the start zone, or a stage.
		fputs(f, si ? ",{\"checkpoints\":[{\"regions\":[" : "{\"checkpoints\":[{\"regions\":[");
		ZoneEdit_WriteRegions(f, si ? ZONE_STAGE : ZONE_START, track, si, -1);
		fputs(f, "]}");
		last = 0;
		while (1)
		{
			c = 0;
			for (z = 0; z < zone_count; z = z + 1)
				if (zone_track[z] == track)
				if (zone_type[z] == ZONE_CHECKPOINT)
				if (zone_seg[z] == si)
				if (zone_cp[z] > last)
				if (!c || zone_cp[z] < c)
					c = zone_cp[z];
			if (!c)
				break;
			fputs(f, ",{\"regions\":[");
			ZoneEdit_WriteRegions(f, ZONE_CHECKPOINT, track, si, c);
			fputs(f, "]}");
			last = c;
		}
		fputs(f, "]}");
	}
	fputs(f, "],\"end\":{\"regions\":[");
	ZoneEdit_WriteRegions(f, ZONE_END, track, -1, -1);
	fputs(f, "]}}}");
};

// The whole table to `path` (under data/, where QC writes).  FALSE: it could not be opened.
float(string path) ZoneEdit_WriteFile =
{
	local filestream f;
	local float t, top, z;

	f = fopen(path, FILE_WRITE);
	if (f < 0)
		return FALSE;
	top = 0;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] > top)
			top = zone_track[z];
	fputs(f, "{\"formatVersion\":1,");
	if (zone_maxvel > 0)            // P841: the map's speed cap, which a published file carries
		fputs(f, sprintf("\"maxVelocity\":%s,", ZoneEdit_Num(zone_maxvel)));
	fputs(f, "\"tracks\":{\"main\":");
	ZoneEdit_WriteTrack(f, 0);
	fputs(f, ",\"bonuses\":[");
	for (t = 1; t <= top; t = t + 1)
	{
		if (t > 1)
			fputs(f, ",");
		ZoneEdit_WriteTrack(f, t);      // a bonus number with nothing in it keeps its place
	}
	fputs(f, "]},\"globalRegions\":{\"cancel\":[");
	ZoneEdit_WriteRegions(f, ZONE_CANCEL, 0, -1, -1);
	fputs(f, "],\"allowBhop\":[");
	ZoneEdit_WriteRegions(f, ZONE_BHOP, 0, -1, -1);
	fputs(f, "],\"overbounce\":[");
	ZoneEdit_WriteRegions(f, ZONE_OVERBOUNCE, 0, -1, -1);
	fputs(f, "]}}\n");
	fclose(f);
	return TRUE;
};

/*
  WHO MAY WRITE A FILE.  Every `zone_edit` word is a console command, and a server can
  type a console command for a player (cl_main.qc, Patch 617): a host could have made
  zones on a joining client and saved them, and that client would then have drawn them on
  that map everywhere and timed its own games with them (the review).  So a file is
  written or removed only when this client IS the server (the netchan's own address,
  cl_replay.qc's test turned round: anything it cannot read is NOT ours), or when a
  device has just clicked in the panel (cl_input_real, which no command can set).
*/
float() ZoneEdit_Hosting =
{
	// P815: anchored, with a local server and no demo: an ICE connect name can contain
	// "QLoopBack", and a demo's "ip" is its file name.
	if (!isserver() || isdemo())
		return FALSE;
	return strstrofs(serverkey("ip"), "QLoopBack", 0) == 0;
};

// P815: Zone_SyncServer must not swap the table out from under an editor.
float() ZoneEdit_Busy = { return (ui_ze_state != ZE_OFF || ze_dirty); };

float() ZoneEdit_MayWrite =
{
	if (ZoneEdit_Hosting())
		return TRUE;
	if (zone_cmd_taint) return FALSE;  // P1081: a steered real click must not write or remove a file
	if (ze_real_t > 0)
	if (cltime - ze_real_t < 1)
		return TRUE;
	return FALSE;
};

/*
  Save.  The table is written BESIDE the file's name, read back, and replaces the old
  file only if it reads back as what is on screen: the same count and the same crc.  (The
  first cut removed the old file first and looked afterwards.)  An unchanged table is not
  written: one press would pin the map to this machine's copy for nothing.
*/
void(float force) ZoneEdit_Save =
{
	local string path, part, was;
	local filestream f;
	local float n, ok, mv;

	ze_saved_ok = FALSE;
	if (ze_map == "" || ze_map != zone_mapname)
	{
		ZoneEdit_Note("no map to save zones for");
		return;
	}
	if (!zone_count)
	{
		// A file that yields no zones is refused by the loader, and the next source is read:
		// an empty save would bring the old zones back, not remove them.
		ZoneEdit_Note("nothing to save: there are no zones (an empty file would be ignored)");
		return;
	}
	// P1081: no file on disk may come from edits a server could have typed for us, or from a
	// table that came from this server's map or packages (zone_base_untrusted).
	if ((zone_cmd_taint || zone_base_untrusted) && !ZoneEdit_Hosting())
	{
		ZoneEdit_Note(zone_cmd_taint
		              ? "NOT SAVED: a command or synthetic input changed these zones on this server; Reload, then edit with the panel"
		              : "NOT SAVED: these zones came from this server's map or packages; edit them in a game you host");
		return;
	}
	if (!ZoneEdit_MayWrite())
	{
		ZoneEdit_Note("on someone else's server, save with a click on the panel's save button");
		return;
	}
	if (!ze_dirty)
	if (!force)
	{
		ZoneEdit_Note("nothing has changed since these zones were read");
		return;
	}
	ZoneEdit_Touch();
	path = strcat("maps/zones/local/", ze_map, ".json");
	part = strcat(path, ".part");
	if (!ZoneEdit_WriteFile(part))
	{
		ZoneEdit_Note(sprintf("could not write %s", part));
		return;
	}
	n = zone_count;
	mv = zone_maxvel;
	was = strzone(zone_crc);
	ok = Zone_LoadJson(part, ZSRC_LOCAL);
	if (ok)
		Zone_Hash();
	if (!ok || zone_count != n || zone_crc != was || zone_maxvel != mv)
	{
		// Not what was on screen: the old file stays as it is.
		fremove(part);
		strunzone(was);
		if (!ok)
		{
			// Nothing came back, and the loader may have emptied the table: what the
			// map had before is read again.  The edits are lost, and that is said.
			zone_mapname = "";
			Zone_LoadForMap();
			ze_dirty = FALSE;
			ze_sel = -1;
			ZoneEdit_Note("NOT SAVED: the file did not read back; the zones are as they were on disk");
		}
		else
		{
			ze_dirty = TRUE;
			ze_sel = -1;
			ZoneEdit_Note("NOT SAVED: the file read back differently; what is on screen now is what it read as");
		}
		return;
	}
	strunzone(was);
	if (ze_saved_sha != "") strunzone(ze_saved_sha);
	ze_saved_sha = strzone(strtolower(digest_hex("SHA256", Zone_ReadFile(part))));
	// Windows will not rename over a file (cl_zonedl.qc): clear the target first.  Only a
	// copy under data/ can be removed from here; a shipped file is simply read after ours.
	f = fopen(path, FILE_READ);
	if (f >= 0)
	{
		fclose(f);
		fremove(path);
	}
	if (frename(part, path) != 0)
	{
		fremove(part);
		ze_dirty = TRUE;
		ZoneEdit_Note(sprintf("NOT SAVED: could not put the file at data/%s", path));
		return;
	}
	ze_saved_n = zone_count;
	ze_dirty = FALSE;
	ze_saved_ok = TRUE;
	zone_own = TRUE;                // P815: now our own edit; Zone_SyncServer must leave it
	zone_sync_wait = FALSE;
	ze_sel = -1;
	ZoneEdit_Note(sprintf("saved %g zones to data/%s (crc %s)%s", zone_count, path, zone_crc,
	                      zone_maxvel > 0 ? sprintf(", speed cap %g", zone_maxvel) : ""));
};

// The way back from a save: this machine's own copy goes, and the map's zones are read
// again from wherever they come next (a release's file, Momentum's, the BSP).
void() ZoneEdit_Forget =
{
	local string path;

	if (ze_map == "" || ze_map != zone_mapname)
		return;
	if (!ZoneEdit_MayWrite())
	{
		ZoneEdit_Note("on someone else's server, use the panel's own button for this");
		return;
	}
	path = strcat("maps/zones/local/", ze_map, ".json");
	fremove(path);
	zone_mapname = "";
	Zone_LoadForMap();
	ze_dirty = FALSE;
	ze_sel = -1;
	ZoneEdit_Note(sprintf("this machine's own file is gone: %g zones now, from %s", zone_count,
	                      Zone_SourceName(zone_source)));
};

/*
===========================================================================
  Placing
===========================================================================
*/
vector(vector v) ZoneEdit_SnapV =
{
	local float g;

	if (!ze_snap)
		return v;
	g = max(1, ze_grid);
	// The floor goes DOWN to the grid, never up: a zone whose bottom is above the floor
	// is one the feet are never in, and the server arms a start on the feet.
	return [rint(v_x / g) * g, rint(v_y / g) * g, floor(v_z / g) * g];
};

// Where the crosshair meets the world.  The world model only: a CSQC trace falls
// through brush entities (cl_soundscape.qc), so aim at solid map, not at a door.
void() ZoneEdit_Aim =
{
	local vector eye;

	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	traceline(eye, eye + v_forward * ZE_REACH, MOVE_NOMONSTERS, world);
	ze_hitok = (trace_fraction < 1 && !trace_startsolid);
	ze_hitz = trace_endpos_z;
	ze_hit = ZoneEdit_SnapV(trace_endpos);
	if (ze_edges && ze_hitok) ze_hit = ZoneEdit_EdgeSnap(ze_hit);
	if (!ze_snap)
		ze_hit_z = ze_hit_z - 1;        // the surface as hit: a hair under it, for the same reason
};

// The height the view is pulling: where the aim passes nearest the vertical through the
// second corner.  Looking level across the floor gives the least, looking up gives more.
float() ZoneEdit_Pull =
{
	local vector eye, d, w;
	local float a, b, c, e, den, t;

	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	d = v_forward;
	// Closest approach of the ray eye + s d to the line ze_b + t up.
	w = eye - [ze_b_x, ze_b_y, ze_a_z];
	a = d * d;
	b = d_z;
	c = 1;
	e = w_z;
	den = a * c - b * b;
	if (den < 0.0001)
		return ze_h;                    // looking straight up or down: keep what it was
	t = (a * e - b * (d * w)) / den;
	return ZoneEdit_Height(ze_a_z + t);
};

// What else has the mouse, "" nothing: the inspector's list (cl_entview.qc), and any
// claim in the cursor register that is not ours.  Two sui brackets in one frame and the
// later one owns every click, so this editor does not share the screen with any of them.
string() ZoneEdit_Blocker =
{
	local float others;

	if (ui_he_open)   return "the layout editor";
	if (rec_sb_open)  return "the leaderboard";
	if (rec_wt_open)  return "a replay";
	if (ui_rs_cursor) return "the results card";
	if (ui_ev_cursor) return "the entity inspector";
	// Subtraction, not &~ (UI_CursorRelease's reason).  The open chat (P821) is no panel:
	// it draws no sui bracket and takes every event while it is up.
	others = UI_CursorHeld() - (UI_CursorHeld() & UIC_ZONEEDIT);
	others = others - (others & UIC_CHAT);
	if (others)
		return sprintf("the panel holding the mouse (cursor claims %g)", others);
	return "";
};

void() ZoneEdit_ToPanel =
{
	local string why;

	ze_click = ze_back = ze_close = FALSE;
	ze_cursor = TRUE;
	ui_ze_state = ZE_PANEL;
	why = ZoneEdit_Blocker();
	if (why != "")
	{
		ui_ze_state = ZE_OFF;
		print(sprintf("^3zone_edit^7: close %s first%s\n", why,
		              ze_dirty ? " (your unsaved zones are still on screen)" : ""));
		return;
	}
	ze_mouse_seen = cl_ptr_real_ok = FALSE;     // P1081: a new cursor; the old place is stale
	sui_reset_actions();
	activate_mouse_cursor();
	UI_CursorClaim(UIC_ZONEEDIT);
};

void() ZoneEdit_ToPlacing =
{
	UI_CursorRelease(UIC_ZONEEDIT);
	ze_click = ze_back = ze_close = FALSE;
	ze_cursor = FALSE;
	ze_drag = FALSE;
	ze_np = 0;
	if (!ze_pts) ze_pts = memalloc(sizeof(vector) * ZE_MAXPTS);
	ui_ze_state = ze_poly ? ZE_P : ZE_A;
};

// The panel's "+ start" and its fellows: what the new zone will be, then off to place it.
void(float type) ZoneEdit_Begin =
{
	local float z, s, c;

	if (zone_count >= ZONE_MAX || zone_ptcount + 4 > ZONE_MAX_POINTS)
	{
		ZoneEdit_Note(sprintf("the table is full (%g zones, %g points)", zone_count, zone_ptcount));
		return;
	}
	if (type == ZONE_START || type == ZONE_END)
	if (ZoneEdit_Has(ze_track, type))
	{
		ZoneEdit_Note(sprintf("this track has %s: select it and re-place it, or delete it first",
		                      (type == ZONE_START) ? "a start" : "an end"));
		return;
	}
	ze_replace = -1;
	ze_ntype = type;
	ze_nseg = 0;
	ze_ncp = 0;
	// The last segment the track has: a new stage is the one after it.
	s = 0;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == ze_track)
		if (zone_type[z] == ZONE_STAGE)
		if (zone_seg[z] > s)
			s = zone_seg[z];
	if (type == ZONE_STAGE)
		ze_nseg = s + 1;
	if (type == ZONE_END)
		ze_nseg = s + 1;
	if (type == ZONE_CHECKPOINT)
	{
		// In the selected zone's segment, after the checkpoints that segment has; with
		// nothing selected, in the last one.  A half is "after ordinal c": renumbered at once.
		ze_nseg = s;
		if (ze_sel >= 0 && ze_sel < zone_count)
		if (zone_track[ze_sel] == ze_track)
		if (zone_type[ze_sel] != ZONE_END)
			ze_nseg = zone_seg[ze_sel];
		c = 0;
		for (z = 0; z < zone_count; z = z + 1)
			if (zone_track[z] == ze_track)
			if (zone_type[z] == ZONE_CHECKPOINT)
			if (zone_seg[z] <= ze_nseg)
			if (zone_cp[z] > c)
				c = zone_cp[z];
		ze_ncp = c + 0.5;
	}
	ZoneEdit_ToPlacing();
};

void(float z) ZoneEdit_BeginReplace =
{
	if (z < 0 || z >= zone_count)
		return;
	ze_replace = z;
	ze_rsig = zone_count * 4096 + zone_ptcount;
	if (zone_npts[z] != 4) ze_poly = TRUE;
	ze_ntype = zone_type[z];
	ze_nseg = zone_seg[z];
	ze_ncp = zone_cp[z];
	ZoneEdit_ToPlacing();
};

// The third click: the box joins the table.
void() ZoneEdit_Commit =
{
	local float z, kind, yaw, track;
	local vector pos, ang;
	local string nm;

	ze_h = ZoneEdit_Height(ze_a_z + ze_h);
	if (ze_poly)
	{
		if (!ZoneEdit_PolygonValid()) { ZoneEdit_Note("Invalid outline; unchanged"); return; }
		if (zone_ptcount + ze_np > ZONE_MAX_POINTS) { ZoneEdit_Note("Point table full; unchanged"); return; }
	}
	ang = getproperty(VF_ANGLES);
	track = ze_track;
	kind = ZTD_NONE;
	pos = '0 0 0';
	yaw = 0;
	nm = "";
	if (ze_replace >= 0)
	if (ze_replace >= zone_count || ze_rsig != zone_count * 4096 + zone_ptcount)
	{
		// The table is not the one the re-place began on (a reload, a zone download
		// landing): row ze_replace is somebody else now.
		ze_replace = -1;
		ZoneEdit_Note("the zones changed while you were placing: nothing was replaced");
		ZoneEdit_ToPanel();
		return;
	}
	if (ze_replace >= 0)
	{
		// The zone keeps what it was and where it sends you; only its box changes.
		track = zone_track[ze_replace];
		kind = zone_td_kind[ze_replace];
		pos = zone_td_pos[ze_replace];
		yaw = zone_td_yaw[ze_replace];
		if (zone_td_name[ze_replace] != "")
			nm = strzone(zone_td_name[ze_replace]);
		ZoneEdit_Remove(ze_replace);
	}
	if (ze_poly) z = ZoneEdit_AddPolygon();
	else z = ZoneEdit_AddBox(ze_ntype, track, ze_nseg, ze_ncp, ze_a, ze_b, ze_a_z, ze_a_z + ze_h);
	if (z >= 0) zone_track[z] = track;
	if (z < 0)
	{
		if (nm != "")
			strunzone(nm);
		ze_replace = -1;
		ZoneEdit_Touch();               // a removed row left the others' bounds stale
		ZoneEdit_Note("the table is full");
		ZoneEdit_ToPanel();
		return;
	}
	if (ze_replace >= 0)
	{
		zone_td_kind[z] = kind;
		zone_td_pos[z] = pos;
		zone_td_yaw[z] = yaw;
		zone_td_name[z] = nm;
	}
	else if (ze_ntype == ZONE_START || ze_ntype == ZONE_STAGE)
	{
		ZoneEdit_DestCentre(z, rint(ang_y));
		// On the floor as it was hit: the bottom may be a grid step under it, and a
		// spawn inside the floor is one the server has to dig out.
		pos = zone_td_pos[z];
		pos_z = max(pos_z, ze_floor + 1);
		zone_td_pos[z] = pos;
	}
	ze_sel = z;                     // before the sort: it follows the row
	ZoneEdit_Touch();
	ZoneEdit_Note(sprintf("%s %s: %g x %g, %g tall", (ze_replace >= 0) ? "re-placed" : "added",
	                      ZoneEdit_Label(ze_sel), fabs(ze_b_x - ze_a_x), fabs(ze_b_y - ze_a_y), ze_h));
	ze_replace = -1;
	ZoneEdit_ToPanel();
};

// One MOUSE1 while placing, taken in the draw pass where the aim is this frame's.
void() ZoneEdit_Click =
{
	if (ui_ze_state == ZE_P) ZoneEdit_PolygonClick();
	else if (ui_ze_state == ZE_A)
	{
		if (!ze_hitok)
			return;
		ze_a = ze_hit;
		ze_b = ze_hit;
		ze_floor = ze_hitz;
		ze_h = ZoneEdit_Height(ze_a_z + max(ZE_MINH, ze_grid * 4));
		ui_ze_state = ZE_B;
	}
	else if (ui_ze_state == ZE_B)
	{
		if (!ze_hitok)
			return;
		if (ze_hit_x == ze_a_x || ze_hit_y == ze_a_y)
		{
			ZoneEdit_Note("the second corner is in line with the first: the floor needs a width and a depth");
			return;
		}
		ze_b = [ze_hit_x, ze_hit_y, ze_a_z];
		ui_ze_state = ZE_H;
	}
	else if (ui_ze_state == ZE_H)
		ZoneEdit_Commit();
};

// MOUSE2: one step back, and out to the panel from the first.
void() ZoneEdit_Back =
{
	if (ui_ze_state == ZE_P)
	{
		if (ze_np > 0) ze_np = ze_np - 1;
		else { ze_replace = -1; ZoneEdit_ToPanel(); }
	}
	else if (ui_ze_state == ZE_H)
		ui_ze_state = ze_poly ? ZE_P : ZE_B;
	else if (ui_ze_state == ZE_B)
		ui_ze_state = ZE_A;
	else if (ui_ze_state == ZE_A)
	{
		ze_replace = -1;
		ZoneEdit_ToPanel();
	}
};

/*
===========================================================================
  Drawing
===========================================================================
*/
void(vector a, vector b, float bottom, float top, vector col, float alpha) ZoneEdit_DrawBox =
{
	local vector p0, p1, p2, p3, up;

	p0 = [min(a_x, b_x), min(a_y, b_y), bottom];
	p1 = [max(a_x, b_x), min(a_y, b_y), bottom];
	p2 = [max(a_x, b_x), max(a_y, b_y), bottom];
	p3 = [min(a_x, b_x), max(a_y, b_y), bottom];
	up = [0, 0, top - bottom];
	Zone_Line(p0, p1, col, alpha);
	Zone_Line(p1, p2, col, alpha);
	Zone_Line(p2, p3, col, alpha);
	Zone_Line(p3, p0, col, alpha);
	if (top > bottom)
	{
		Zone_Line(p0 + up, p1 + up, col, alpha);
		Zone_Line(p1 + up, p2 + up, col, alpha);
		Zone_Line(p2 + up, p3 + up, col, alpha);
		Zone_Line(p3 + up, p0 + up, col, alpha);
		Zone_Line(p0, p0 + up, col, alpha);
		Zone_Line(p1, p1 + up, col, alpha);
		Zone_Line(p2, p2 + up, col, alpha);
		Zone_Line(p3, p3 + up, col, alpha);
	}
};

// In the world pass, after Zone_Draw (cl_main.qc): the whole table whatever zone_draw
// says, the selected zone, and the box being placed.  The aim is taken HERE, in the
// frame it is drawn in, and a click the input handler asked for is answered here.
void() ZoneEdit_Draw3D =
{
	local float z, g;
	local vector eye, c;

	if (!ui_ze_state)
		return;
	if (ze_map != zone_mapname || serverkey("map") != ze_map)
	{
		// The map changed under the editor: the table is the new map's.
		UI_CursorRelease(UIC_ZONEEDIT);
		ze_cursor = ze_drag = FALSE;
		ui_ze_state = ZE_OFF;
		if (ze_dirty)
			print("^3zone_edit^7: the map changed; the unsaved zones are gone\n");
		ze_dirty = FALSE;
		return;
	}
	// Every zone, whatever zone_draw, its type switches and its distance say (Zone_Draw may
	// have drawn some already: a second pass over a line changes nothing you can see).
	eye = getproperty(VF_ORIGIN);
	for (z = 0; z < zone_count; z = z + 1)
		Zone_DrawOne(z, (z == ze_sel) ? '1 1 1' : zone_cv_typecol[zone_type[z]], 1, eye);
	if (ui_ze_state < ZE_A)
		return;

	if (ZoneEdit_Blocker() != "")
	{
		ze_click = ze_back = FALSE;     // another panel is up: its clicks are its own
		return;
	}
	if (ze_cursor)
	{
		if (ze_poly) ZoneEdit_PolygonGhost();
		return;
	}
	ZoneEdit_Aim();
	if (ui_ze_state == ZE_H)
		ze_h = ZoneEdit_Height(ze_a_z + ZoneEdit_Pull());
	if (ze_back)
	{
		ze_back = FALSE;
		ZoneEdit_Back();
	}
	if (ze_close && ui_ze_state == ZE_P) { ze_close = FALSE; ZoneEdit_PolygonClose(); }
	if (ze_click)
	{
		ze_click = FALSE;
		ZoneEdit_Click();
	}
	if (ui_ze_state < ZE_A)
		return;

	if (ze_poly) { ZoneEdit_PolygonGhost(); return; }
	// The aim: a small cross on the floor at the snapped point.
	if (ze_hitok && ui_ze_state != ZE_H)
	{
		g = max(4, ze_grid * 0.5);
		c = [ze_hit_x, ze_hit_y, ze_hitz + 0.5];
		Zone_Line(c - [g, 0, 0], c + [g, 0, 0], ZEC_NEW, 1);
		Zone_Line(c - [0, g, 0], c + [0, g, 0], ZEC_NEW, 1);
		Zone_Line(c, c + [0, 0, g * 2], ZEC_NEW, 1);
	}
	if (ui_ze_state == ZE_B)
	{
		if (ze_hitok)
			ZoneEdit_DrawBox(ze_a, ze_hit, ze_floor + 0.5, ze_floor + 0.5, ZEC_NEW, 1);
	}
	else if (ui_ze_state == ZE_H)
	{
		ZoneEdit_DrawBox(ze_a, ze_b, ze_a_z, ze_a_z + ze_h, ZEC_NEW, 1);
		// And its outline on the floor itself: the bottom may be a grid step under it.
		ZoneEdit_DrawBox(ze_a, ze_b, ze_floor + 0.5, ze_floor + 0.5, ZEC_NEW, 1);
	}
};

// A button: its box, its word, and whether it was clicked this frame.
// A click on element `id`: the mouse's, or `zone_edit press <id>` (an arm has no mouse).
float(string id) ZoneEdit_Clicked =
{
	if (!ze_cursor && ze_press == "") return FALSE;
	if (ze_press != "")
	if (ze_press == id)
	{
		strunzone(ze_press);
		ze_press = "";
		return (strcmp(id, "ze_upload") != 0);  // P815: a command never stands in for Publish's click
	}
	return sui_is_clicked(id);
};

// Control IDs also serve the shared HUD-editor hover probe.
string(string id) ZoneEdit_Tip =
{
	if (id == "ze_as") return "Place this track's start zone. The timer arms here and starts when you leave. Each track has one start; select it and Re-place to move it.";
	if (id == "ze_ag") return "Place the next stage start in this track. Stages divide the course into timed segments and are numbered in order.";
	if (id == "ze_ac") return "Place a checkpoint in the selected zone's segment, or the last segment if none is selected. Checkpoints record progress without starting a new stage.";
	if (id == "ze_ae") return "Place this track's finish zone. Entering it ends the run. Each track has one end; select it and Re-place to move it.";
	if (id == "ze_rp") return "Select a zone, then redraw its floor and height. Its track, type and course position stay the same. Right-click steps back; Esc returns to the panel.";
	if (id == "ze_sp") return "For a selected start or stage, use your current position and facing as its restart spawn. Stand at a safe point inside the zone first.";
	if (id == "ze_resetspawn") return "For a selected start or stage, remove its custom spawn and use the zone's default floor point. Concave zones keep a safe point inside the outline.";
	if (id == "ze_dl") return "Remove the selected zone from your edits. Stages and checkpoints are renumbered. Nothing is written to disk until Save zones.";
	if (id == "ze_shape") return "Choose Box or Polygon for new and re-placed zones. A box uses two opposite floor corners; a polygon uses an outline closed with Enter or a click on its first corner. Both have a flat floor and vertical height.";
	if (id == "ze_edges") return "Snap placement near existing zone corners and edges on the same floor. Corners take priority. This does not snap to the map's brush edges.";
	if (id == "ze_xyz") return "Round the selected zone's outline and vertical bounds to the chosen grid. Works in the panel; an invalid or collapsed outline is refused.";
	if (id == "ze_gs") return "Use the world surface as hit instead of rounding placement to the grid. This is a snapping option, not the Surf gamemode. Click again to restore grid snapping.";
	if (id == "ze_sv") return "Save the zones to this map's local JSON file on your machine. Reload the map to use them for timing in your hosted game. This does not upload zones or change a lobby's timing or times.";
	if (id == "ze_upload") return "Publish this map's SAVED local zones, and their speed cap, to the lobbies. Requires a linked zone-admin Steam account; a dialog asks before anything is sent. Lobbies time with them from their next map load; existing times stay.";
	if (id == "ze_rl") return "Discard unsaved zone edits and read this map's zones again. Your saved local file takes priority; use Discard local file to stop using that override.";
	if (id == "ze_fg") return "Delete this map's saved local zone override and reload the underlying zones. Unsaved zone edits are lost too. Map properties are separate and are not removed.";
	if (id == "ze_settings") return "Edit local Surf/Bhop presets, speed cap, gravity and air acceleration for this map. Save settings and reload the hosted map to apply them. The speed cap also goes in the zone file, so Publish sends it to the lobbies; the rest stay local.";
	if (id == "ze_look") return "Give the mouse back to aiming and flying without closing the editor. Mouse2 returns the cursor to this window; V toggles noclip.";
	if (id == "ze_cl") return "Close the editor without saving. Unsaved zone edits stay in memory until the map changes; reopen the editor to continue or save them.";
	if (id == "ze_mode_surf") return "Stage Surf mode: 66.67 Hz physics and air acceleration 150. Keeps your chosen speed cap and gravity. Save settings and reload your hosted map to apply.";
	if (id == "ze_mode_bhop") return "Stage Bhop mode: 100 Hz physics and air acceleration 1000. Keeps your chosen speed cap and gravity. Save settings and reload your hosted map to apply.";
	if (id == "ze_ms0") return "Speed cap: limits movement velocity, not ordinary walking speed. Higher values allow faster surfing or bhopping. Enter 1 to 100000; Apply stages the value, Save settings and map reload make it active locally. It is also the zone file's maxVelocity: Save zones and Publish saved to set it on the lobbies.";
	if (id == "ze_ms1") return "Gravity: downward acceleration in map units per second squared. Lower values give longer, higher jumps. Enter 1 to 10000; this map's saved setting applies only after a hosted map reload.";
	if (id == "ze_ms2") return "Air acceleration: how strongly movement input changes your velocity while airborne. Surf presets 150; Bhop presets 1000. Enter 0 to 10000; save and reload the hosted map to apply.";
	if (id == "ze_msapply") return "Validate the number and stage it in this properties panel. Enter does the same. This does not save to disk or change the active physics yet.";
	if (id == "ze_mssave") return "Save this map's mode and three numeric properties locally, including the active text field. Requires a hosted map reload to apply. A changed speed cap is also staged in the zones; nothing is uploaded until Publish saved.";
	if (id == "ze_msback") return "Return to the zone tools without saving properties. Use Save settings first: reopening properties reads the saved values, not your unsaved changes.";
	if (id == "ze_t0") return "Show the main course. Tracks have separate starts, stages, checkpoints and finishes.";
	if (substring(id, 0, 4) == "ze_t") return "Show a bonus course. A +b tab is the next unused bonus track; select it and add zones to build that course.";
	if (substring(id, 0, 4) == "ze_z") return "Select this zone to re-place, delete or snap it. Double-click teleports to it only when your zone table matches the server's. The row shows outline points and bottom/top heights.";
	if (substring(id, 0, 4) == "ze_g") return "Enable grid snapping at this spacing in map units. Affects placement and Snap selected XYZ. The mouse wheel also changes the grid while placing.";
	return "";
};

float(vector p, vector s, string id, string word, float tsz, vector col) ZoneEdit_Button =
{
	local float w;

	sui_action_element(p, s, id, sui_noop);
	sui_style_box(p, s, 4, sui_is_hovered(id) ? SUI_THEME_HOVER
	                : ((col == ZEC_SEL) ? SUI_THEME_SELECTED : SUI_THEME_CHIP),
	              (col == ZEC_SEL) ? SUI_THEME_EDGE_HI : SUI_THEME_EDGE, 1);
	w = stringwidth(word, TRUE, [tsz, tsz]);
	sui_text(p + [max(4, (s_x - w) * 0.5), (s_y - tsz) * 0.5], [tsz, tsz], word, col, 1, 0);
	if (ze_cursor) sui_tooltip_for(id, ZoneEdit_Tip(id), ui_cv_scale);
	return ZoneEdit_Clicked(id);
};

void(vector scr) ZoneEdit_Panel =
{
	local vector p, tp, lp, rs;
	local float w, h, pad, tsz, rsz, rowh, bw, z, n, i, k, best, bo, o, a, top, lastk, cut;
	local string s, id, title, controls;

	ZonePub_Pump();
	if (!ui_ze_state || !ze_cursor)
		if (substring(sui_tip_id, 0, 3) == "ze_") sui_tooltip_reset();
	if (!ui_ze_state)
		return;
	if (ui_ze_state == ZE_PANEL)
	{
		s = ZoneEdit_Blocker();
		if (s != "")
		{
			UI_CursorRelease(UIC_ZONEEDIT);
			ui_ze_state = ZE_OFF;
			if (substring(sui_tip_id, 0, 3) == "ze_") sui_tooltip_reset();
			print(sprintf("^3zone_edit^7: closed -- %s opened%s\n", s,
			              ze_dirty ? "; your unsaved zones are still on screen" : ""));
			return;
		}
	}

	Font_Set(ui_font_ui);
	pad  = 8 * ui_cv_scale;
	tsz  = Font_Px(9 * ui_cv_scale);
	rsz  = Font_Px(8 * ui_cv_scale);
	rowh = rsz + 6 * ui_cv_scale;

	if (ui_ze_state >= ZE_A && !ze_cursor)
	{
		// Placing: the mouse is the game's.  One line of what the next click does.
		if (ui_ze_state == ZE_P)
			s = sprintf("click corners (%g); Enter / first corner closes; Mouse2: back", ze_np);
		else if (ui_ze_state == ZE_A)
			s = "MOUSE1 first floor corner";
		else if (ui_ze_state == ZE_B)
			s = sprintf("MOUSE1 opposite corner  (%g x %g)", fabs(ze_hit_x - ze_a_x), fabs(ze_hit_y - ze_a_y));
		else
			s = sprintf("look up to pull the height (%g), MOUSE1 to finish", ze_h);
		title = sprintf("%s %s  /  %s", (ze_replace >= 0) ? "RE-PLACING" : "PLACING",
			Zone_TypeName(ze_ntype), ze_poly ? "polygon" : "box");
		controls = sprintf("MOUSE2 back  /  wheel grid %g  /  V noclip  /  ESC panel", ze_grid);
		rsz = min(rsz, max(8, scr_x / 80));
		w = max(stringwidth(s, TRUE, [rsz, rsz]), stringwidth(controls, TRUE, [rsz, rsz]));
		w = min(scr_x - pad * 2, max(w, stringwidth(title, TRUE, [rsz, rsz])) + pad * 2);
		h = rsz * 3 + pad * 3;
		if (!ze_hitok && ui_ze_state != ZE_H) h = h + rsz + pad * 0.5;
		p = [(scr_x - w) * 0.5, min(scr_y * 0.72, scr_y - h - pad), 0];
		// Raw SUI chrome, in these draw coordinates: no second input bracket.
		_sui_round_draw(p + '-2 -1 0', [w + 4, h + 4, 0], 7, '0 0 0', 0.22);
		_sui_round_draw(p, [w, h, 0], 6, SUI_THEME_EDGE_HI, 1);
		_sui_round_draw(p + '1 1 0', [w - 2, h - 2, 0], 5, SUI_THEME_CHIP, 1);
		drawstring(p + [pad, pad, 0], title, [rsz, rsz], SUI_THEME_ACCENT, 1, 0);
		drawstring(p + [pad, pad * 1.5 + rsz, 0], s, [rsz, rsz], ZEC_TEXT, 1, 0);
		drawstring(p + [pad, pad * 2 + rsz * 2, 0], controls, [rsz, rsz], ZEC_DIM, 1, 0);
		if (!ze_hitok && ui_ze_state != ZE_H)
			drawstring(p + [pad, pad * 2.5 + rsz * 3, 0], "Aim at the map: nothing solid under the crosshair",
				[rsz, rsz], ZEC_WARN, 1, 0);
		Font_Reset();
		return;
	}

	w = 330 * ui_cv_scale;
	if (w > scr_x * 0.5 - 32 * ui_cv_scale)
		w = scr_x * 0.5 - 32 * ui_cv_scale;
	h = scr_y - 110 * ui_cv_scale;
	if (h < rowh * 14)
		h = min(scr_y - 16, rowh * 14);
	p = [scr_x - w - 16 * ui_cv_scale, 56 * ui_cv_scale, 0];
	if (p_y + h > scr_y - 8)
		p_y = max(8, scr_y - 8 - h);
	if (ze_drag) ze_window = _cursor_position - ze_drag_offset;
	if (ze_positioned) p = ze_window;
	p_x = bound(8, p_x, max(8, scr_x - w - 8));
	p_y = bound(8, p_y, max(8, scr_y - h - 8));
	ze_window = p;
	ze_panel_p = p;
	ze_panel_s = [w, h, 0];

	sui_begin(scr_x, scr_y);
	sui_action_element(p, [w, h], "ze_bg", sui_noop);
	sui_style_panel(p, [w, h], 8, 0.96);
	drawsetcliparea(p_x, p_y, w, h);

	tp = p + [pad, pad];
	sui_text(tp, [tsz, tsz], sprintf("zone editor  -  %s%s", ze_map, ze_dirty ? "  (not saved)" : ""),
	         ze_dirty ? ZEC_WARN : ZEC_TEXT, 1, 0);
	tp_y = tp_y + tsz + pad * 0.5;
	sui_text(tp, [rsz, rsz], sprintf("%g zones, from %s%s", zone_count, Zone_SourceName(zone_source),
	                                (serverkey("board") == "ranked") ? "; this server times with its own" : ""),
	         ZEC_DIM, 1, 0);
	tp_y = tp_y + rsz + pad;
	if (ze_settings)
	{
		ZoneEdit_SettingsDraw(p, w, tp_y, rowh, rsz);
		sui_text([p_x + pad, p_y + h - rowh], [rsz, rsz], ze_note, ZEC_WARN, 1, 0);
		drawresetcliparea(); ZonePub_Draw(scr); sui_end(); Font_Reset(); return;
	}

	// Tracks: main, each bonus there is, and the next one.
	top = 0;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] > top)
			top = zone_track[z];
	if (ze_track > top + 1)
		ze_track = top + 1;
	bw = 34 * ui_cv_scale;
	lp = tp;
	for (i = 0; i <= top + 1 && i <= 12; i = i + 1)
	{
		id = strcat("ze_t", ftos(i));
		s = (i == 0) ? "main" : ((i > top) ? sprintf("+b%g", i) : sprintf("b%g", i));
		if (lp_x + bw > p_x + w - pad)
		{
			lp_x = tp_x;
			lp_y = lp_y + rowh + 2;
		}
		if (ZoneEdit_Button(lp, [bw, rowh], id, s, rsz, (i == ze_track) ? ZEC_SEL : ZEC_TEXT))
		{
			ze_track = i;
			ze_sel = -1;
		}
		lp_x = lp_x + bw + 4;
	}
	tp_y = lp_y + rowh + pad;

	// What can be added to this track.
	bw = (w - pad * 2 - 12) / 4;
	if (ZoneEdit_Button(tp, [bw, rowh], "ze_as", "+ start", rsz, ZoneEdit_Has(ze_track, ZONE_START) ? ZEC_DIM : ZEC_TEXT))
		ZoneEdit_Begin(ZONE_START);
	if (ZoneEdit_Button(tp + [bw + 4, 0], [bw, rowh], "ze_ag", "+ stage", rsz, ZEC_TEXT))
		ZoneEdit_Begin(ZONE_STAGE);
	if (ZoneEdit_Button(tp + [(bw + 4) * 2, 0], [bw, rowh], "ze_ac", "+ checkpt", rsz, ZEC_TEXT))
		ZoneEdit_Begin(ZONE_CHECKPOINT);
	if (ZoneEdit_Button(tp + [(bw + 4) * 3, 0], [bw, rowh], "ze_ae", "+ end", rsz, ZoneEdit_Has(ze_track, ZONE_END) ? ZEC_DIM : ZEC_TEXT))
		ZoneEdit_Begin(ZONE_END);
	tp_y = tp_y + rowh + pad;
	if (!ze_cursor && ui_ze_state >= ZE_A)
	{
		// A button above took the mouse away: this frame's panel ends here.
		drawresetcliparea();
		sui_end();
		Font_Reset();
		return;
	}

	// The track's zones in course order (selection sort by ZoneEdit_Order, drawn as found),
	// then the regions that belong to no track, on the main page.
	n = 0;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == ze_track)
			n = n + 1;
	rs = [w - pad * 2, (p_y + h - pad) - tp_y - rowh * 9.9, 0];
	sui_style_box(tp - '3 3 0', rs + '6 6 0', 5, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	lastk = -1;
	bo = -1;
	cut = 0;
	lp = tp;
	for (i = 0; i < n; i = i + 1)
	{
		// The next zone of the track after (bo, lastk) in (order, index).
		best = -1;
		k = 0;
		for (z = 0; z < zone_count; z = z + 1)
			if (zone_track[z] == ze_track)
			{
				o = ZoneEdit_Order(z);
				if (zone_type[z] > ZONE_CHECKPOINT)
					o = 9500000 + zone_type[z];
				if (o < bo || (o == bo && z <= lastk))
					continue;
				if (best < 0 || o < k)
				{
					best = z;
					k = o;
				}
			}
		if (best < 0)
			break;
		bo = k;
		lastk = best;
		if (i < ze_scroll)
			continue;
		if (lp_y + rowh * 2 > tp_y + rs_y)
		{
			cut = cut + 1;              // the last row is kept for saying so
			continue;
		}
		z = best;
		id = strcat("ze_z", ftos(z));
		sui_action_element(lp, [rs_x, rowh], id, sui_noop);
		if (z == ze_sel)
			sui_style_box(lp, [rs_x, rowh], 3, SUI_THEME_SELECTED, SUI_THEME_EDGE_HI, 1);
		else if (sui_is_hovered(id))
			sui_style_box(lp, [rs_x, rowh], 3, SUI_THEME_HOVER, SUI_THEME_HOVER, 1);
		sui_fill(lp + [3, 3], [3, rowh - 6], zone_cv_typecol[zone_type[z]], 1, 0);
		sui_text(lp + [12, (rowh - rsz) * 0.5], [rsz, rsz], ZoneEdit_Label(z),
		         (z == ze_sel) ? ZEC_SEL : ZEC_TEXT, 1, 0);
		sui_text(lp + [rs_x * 0.45, (rowh - rsz) * 0.5], [rsz, rsz],
		         sprintf("%g pts  z %g..%g%s", zone_npts[z], zone_bottom[z], zone_top[z],
		                 ((zone_type[z] == ZONE_START || zone_type[z] == ZONE_STAGE) && zone_td_kind[z] == ZTD_NONE)
		                   ? "  auto spawn" : ""), ZEC_DIM, 1, 0);
		if (ze_cursor) sui_tooltip_for(id, ZoneEdit_Tip(id), ui_cv_scale);
		if (ZoneEdit_Clicked(id)) ZoneEdit_RowClick(z);
		lp_y = lp_y + rowh;
	}
	if (!n)
		sui_text(lp, [rsz, rsz], "no zones on this track yet", ZEC_DIM, 1, 0);
	else if (cut)
		sui_text([tp_x + rs_x * 0.45, tp_y + rs_y - rowh + (rowh - rsz) * 0.5], [rsz, rsz],
		         sprintf("%g more: the wheel scrolls", cut), ZEC_WARN, 1, 0);
	tp_y = tp_y + rs_y + pad * 0.5;

	// Inspector: selection and spawn actions, separate from construction tools.
	bw = (w - pad * 2 - 12) / 4;
	a = (ze_sel >= 0 && ze_sel < zone_count);
	// `k`: the selection is a start or a stage.  Nested ifs, not a && : QC evaluates both
	// sides, and zone_type[-1] is a bounds failure that takes the whole VM down.
	k = FALSE;
	if (a)
	if (zone_type[ze_sel] == ZONE_START || zone_type[ze_sel] == ZONE_STAGE)
		k = TRUE;
	s = "SELECT A ZONE  /  double-click to teleport";
	if (a) s = strcat("SELECTED  /  ", ZoneEdit_Label(ze_sel));
	if (k) s = strcat(s, zone_td_kind[ze_sel] == ZTD_NONE ? "  /  automatic spawn" : "  /  custom spawn");
	sui_text(tp, [rsz, rsz], s, ZEC_DIM, 1, 0);
	tp_y = tp_y + rowh;
	if (ZoneEdit_Button(tp, [bw, rowh], "ze_rp", "Re-place", rsz, a ? ZEC_TEXT : ZEC_DIM))
	if (a)
		ZoneEdit_BeginReplace(ze_sel);
	if (ZoneEdit_Button(tp + [bw + 4, 0], [bw, rowh], "ze_sp", "Set spawn", rsz, k ? ZEC_TEXT : ZEC_DIM))
	if (k)
	{
		// Where you stand and the way you face is where `!r` will put you.
		if (zone_td_name[ze_sel] != "")
			strunzone(zone_td_name[ze_sel]);
		zone_td_name[ze_sel] = "";
		zone_td_kind[ze_sel] = ZTD_POS;
		zone_td_pos[ze_sel] = pmove_org;
		lp = getproperty(VF_ANGLES);
		zone_td_yaw[ze_sel] = rint(lp_y);
		ZoneEdit_Touch();
		ZoneEdit_Note(sprintf("%s: spawn set where you stand", ZoneEdit_Label(ze_sel)));
	}
	if (ZoneEdit_Button(tp + [(bw + 4) * 2, 0], [bw, rowh], "ze_resetspawn", "Reset spawn", rsz, k ? ZEC_TEXT : ZEC_DIM))
		ZoneEdit_ResetSpawn();
	if (ZoneEdit_Button(tp + [(bw + 4) * 3, 0], [bw, rowh], "ze_dl", "Delete", rsz, a ? SUI_THEME_BAD : ZEC_DIM))
	if (a)
	{
		ZoneEdit_Note(sprintf("deleted %s", ZoneEdit_Label(ze_sel)));
		ZoneEdit_Remove(ze_sel);
		ze_sel = -1;
		ZoneEdit_Touch();
	}
	tp_y = tp_y + rowh + pad;

	// Construction: shape, existing-zone edge snapping, and explicit XYZ snap.
	sui_text(tp, [rsz, rsz], "CONSTRUCTION  /  shape & snapping", ZEC_DIM, 1, 0);
	tp_y = tp_y + rowh;
	bw = (w - pad * 2 - 8) / 3;
	if (ZoneEdit_Button(tp, [bw, rowh], "ze_shape", ze_poly ? "Polygon" : "Box", rsz, ze_poly ? ZEC_SEL : ZEC_TEXT))
	{
		if (ui_ze_state == ZE_PANEL) ze_poly = !ze_poly;
		else ZoneEdit_Note("Finish/cancel this outline before changing shape");
	}
	if (ZoneEdit_Button(tp + [bw + 4, 0], [bw, rowh], "ze_edges", "Edge snap", rsz, ze_edges ? ZEC_SEL : ZEC_TEXT)) ze_edges = !ze_edges;
	if (ZoneEdit_Button(tp + [(bw + 4) * 2, 0], [bw, rowh], "ze_xyz", "Snap selected XYZ", rsz, a ? ZEC_TEXT : ZEC_DIM))
		if (ui_ze_state == ZE_PANEL) ZoneEdit_SnapSelected();
	tp_y = tp_y + rowh + 4;
	bw = (w - pad * 2 - 20) / 6;
	for (i = 0; i < 5; i = i + 1)
	{
		k = (i == 0) ? 1 : ((i == 1) ? 8 : ((i == 2) ? 16 : ((i == 3) ? 32 : 64)));
		if (ZoneEdit_Button(tp + [(bw + 4) * i, 0], [bw, rowh], strcat("ze_g", ftos(k)), ftos(k), rsz,
		                    (ze_grid == k && ze_snap) ? ZEC_SEL : ZEC_TEXT))
		{
			ze_grid = k;
			ze_snap = TRUE;
		}
	}
	if (ZoneEdit_Button(tp + [(bw + 4) * 5, 0], [bw, rowh], "ze_gs", "Surface", rsz, ze_snap ? ZEC_TEXT : ZEC_SEL))
		ze_snap = !ze_snap;
	tp_y = tp_y + rowh + pad;

	// File actions are one group; navigation is a separate footer.
	bw = (w - pad * 2 - 12) / 4;
	if (ZoneEdit_Button(tp, [bw, rowh], "ze_sv", "Save zones", rsz, ze_dirty ? ZEC_SEL : ZEC_DIM))
		ZoneEdit_Save(FALSE);
	if (ZoneEdit_Button(tp + [bw + 4, 0], [bw, rowh], "ze_rl", "Reload zones", rsz, ZEC_TEXT))
	{
		zone_mapname = "";
		Zone_LoadForMap();
		ze_dirty = FALSE;
		ze_sel = -1;
		ZoneEdit_Note(sprintf("reloaded: %g zones from %s", zone_count, Zone_SourceName(zone_source)));
	}
	// "my file": the copy a save left on this machine, and the way back from one.
	if (ZoneEdit_Button(tp + [(bw + 4) * 2, 0], [bw, rowh], "ze_fg", "Discard local file", rsz,
	                    (zone_source == ZSRC_LOCAL) ? ZEC_WARN : ZEC_DIM))
		ZoneEdit_Forget();
	if (ZoneEdit_Button(tp + [(bw + 4) * 3, 0], [bw, rowh], "ze_upload", "Publish saved", rsz, ZEC_TEXT))
		ZonePub_Begin(ze_real_t > 0 && cltime - ze_real_t < 0.25);
	tp_y = tp_y + rowh + 4;
	bw = (w - pad * 2 - 8) / 3;
	if (ZoneEdit_Button(tp, [bw, rowh], "ze_settings", "Map properties", rsz, ZEC_TEXT)) ZoneEdit_SettingsOpen();
	if (ZoneEdit_Button(tp + [bw + 4, 0], [bw, rowh], "ze_look", "Look / fly", rsz, ZEC_TEXT)) ZoneEdit_ToggleMouse();
	if (ZoneEdit_Button(tp + [(bw + 4) * 2, 0], [bw, rowh], "ze_cl", "Close", rsz, ZEC_TEXT))
	{
		UI_CursorRelease(UIC_ZONEEDIT);
		ze_cursor = ze_drag = FALSE;
		ze_field = -1; sui_text_unfocus();
		ui_ze_state = ZE_OFF;
		if (ze_dirty)
			print("^3zone_edit^7: closed with unsaved zones; they stay on screen until the map changes\n");
	}
	tp_y = tp_y + rowh + 4;

	a = 1 - (cltime - ze_note_t) / 6;
	if (ze_note != "" && a > 0)
		sui_text(tp, [rsz, rsz], ze_note, SUI_THEME_GOOD, min(1, a * 3), 0);
	else if (serverkey("board") != "ranked")
		sui_text(tp, [rsz, rsz], "saved zones time your own game after the map is loaded again", ZEC_DIM, 1, 0);
	else
		sui_text(tp, [rsz, rsz], "saved zones change what you see here, not this server's timing", ZEC_DIM, 1, 0);

	drawresetcliparea();
	ZonePub_Draw(scr);
	sui_end();
	Font_Reset();
};

/*
===========================================================================
  Input.  cl_main.qc asks this before the entity inspector.
===========================================================================
*/
// Ownership records the press, not today's bind/mode. Releases survive a
// toggle, close, rebind or map change; releases of earlier game presses pass.
#define ZE_KEYCOUNT 2048
float(float evtype, float scanx, float chary, float devid) ZoneEdit_InputEvent =
{
	local float owned, onpanel, valid;

	valid = (scanx >= 0 && scanx < ZE_KEYCOUNT);
	owned = 0;
	if (ze_field_keys && valid) owned = ze_field_keys[scanx];
	// P1081: chat_mouse, hud_edit key/click/type and zone_edit pointer reach here with no device
	// behind them, and a server can type those commands: the table is no longer the admin's alone.
	if (!cl_input_real)
	if (ui_ze_state || owned)
	if (!ZoneEdit_Hosting())
		zone_cmd_taint = TRUE;
	if (evtype == IE_KEYUP)
	{
		if (!owned) return FALSE;
		ze_field_keys[scanx] = 0;
		if (owned == 4) ZoneEdit_FieldKey(evtype, scanx, chary);
		if (scanx == K_MOUSE1)
		{
			onpanel = (cl_ptr_real_ok && is_2dpoint_in_bbox(cl_ptr_real, ze_panel_p, ze_panel_s));
			if (owned == 1 && ui_ze_state && ze_cursor && !ze_drag)
			{
				if (cl_input_real && onpanel) ze_real_t = cltime;
				sui_input_event(evtype, scanx, chary, devid);
			}
			ze_drag = FALSE;
		}
		return TRUE;
	}
	if (!ui_ze_state) return FALSE;
	if (evtype == IE_MOUSEABS && ze_cursor)
	{
		ze_mouse = [scanx, chary]; ze_mouse_seen = TRUE;
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (evtype != IE_KEYDOWN || !valid) return FALSE;
	if (ZoneEdit_Blocker() != "") return FALSE;
	if (owned && !(owned == 4 && ze_cursor && ze_settings && ze_field >= 0)) return TRUE;
	if (!ze_field_keys)
	{
		ze_field_keys = memalloc(sizeof(float) * ZE_KEYCOUNT);
		memfill8(ze_field_keys, 0i, sizeof(float) * ZE_KEYCOUNT);
	}

	if (ZonePub_Key(scanx))
	{
		ze_field_keys[scanx] = 3;
		return TRUE;
	}

	// Leave +jump binds alone, especially the wheel used to scroll this list.
	// In look-mode placement Mouse2 still goes back; elsewhere it switches mouse.
	if (!owned)
	if (scanx == K_MOUSE2 && (ze_cursor || ui_ze_state < ZE_A))
	{
		ze_field_keys[scanx] = 3;
		ZoneEdit_ToggleMouse();
		return TRUE;
	}
	if (ze_cursor && ze_settings && ze_field >= 0)
	if (scanx != K_MOUSE1 && scanx != K_MOUSE2 && scanx != K_MWHEELUP && scanx != K_MWHEELDOWN)
	{
		ze_field_keys[scanx] = 4;
		if (scanx == K_ESCAPE) { ze_field = -1; sui_text_unfocus(); }
		else if (scanx == K_ENTER || scanx == K_KP_ENTER) ZoneEdit_SettingApply();
		else ZoneEdit_FieldKey(evtype, scanx, chary);
		return TRUE;
	}
	if (scanx == K_ESCAPE)
	{
		ze_field_keys[scanx] = 5;
		if (ze_cursor)
		{
			UI_CursorRelease(UIC_ZONEEDIT); ui_ze_state = ZE_OFF;
			ze_cursor = ze_drag = FALSE; ze_field = -1; sui_text_unfocus();
		}
		else { ze_replace = -1; ZoneEdit_ToPanel(); }
		return TRUE;
	}
	if (ze_cursor)
	{
		// P1081 review: a real press is aimed where the device pointer is. A panel that took the
		// moves (an open chat) leaves ze_mouse behind: resync, and this press does nothing.
		if (cl_input_real && scanx == K_MOUSE1)
		if (!cl_ptr_real_ok || vlen(cl_ptr_real - ze_mouse) > 1)
		{
			if (cl_ptr_real_ok) { ze_mouse = cl_ptr_real; ze_mouse_seen = TRUE; _sui_mouse_move(ze_mouse, FALSE); }
			ze_field_keys[scanx] = 3;   // its release is swallowed too
			ZoneEdit_Note("click again: the pointer had moved behind another panel");
			return TRUE;
		}
		onpanel = (ze_mouse_seen && is_2dpoint_in_bbox(ze_mouse, ze_panel_p, ze_panel_s));
		if (!onpanel) return FALSE;
		if (scanx == K_MOUSE1)
		{
			ze_field_keys[scanx] = 1;
			_sui_mouse_move(ze_mouse, FALSE);
			ZoneEdit_DragStart(ze_panel_p);
			if (!ze_drag) sui_input_event(evtype, scanx, chary, devid);
			return TRUE;
		}
		if (scanx == K_MWHEELUP || scanx == K_MWHEELDOWN)
		{
			ze_field_keys[scanx] = 1;
			if (!ze_settings) ze_scroll = max(0, ze_scroll + ((scanx == K_MWHEELUP) ? -2 : 2));
			return TRUE;
		}
		return FALSE;
	}
	if (ui_ze_state < ZE_A) return FALSE;
	if (scanx == K_ENTER || scanx == K_KP_ENTER)
	{
		if (ui_ze_state != ZE_P) return FALSE;
		ze_field_keys[scanx] = 6; ze_close = TRUE; return TRUE;
	}
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2 || scanx == K_MWHEELUP || scanx == K_MWHEELDOWN)
	{
		ze_field_keys[scanx] = 2;
		if (scanx == K_MOUSE1) ze_click = TRUE;
		else if (scanx == K_MOUSE2) ze_back = TRUE;
		else
		{
			ze_grid = bound(1, ze_grid * ((scanx == K_MWHEELUP) ? 2 : 0.5), 64);
			ze_snap = TRUE;
		}
		return TRUE;
	}
	return FALSE;
};

/*
===========================================================================
  Commands
===========================================================================
*/
void() ZoneEdit_Open =
{
	if (ui_ze_state)
		return;
	if (serverkey("map") == "" || zone_mapname != serverkey("map"))
	{
		print("^3zone_edit^7: no map loaded\n");
		return;
	}
	if (ze_map != zone_mapname)
	{
		if (ze_map != "")
			strunzone(ze_map);
		ze_map = strzone(zone_mapname);
		ze_dirty = FALSE;
		ze_track = 0;
	}
	ze_sel = -1;
	ze_replace = -1;
	ze_scroll = 0;
	ze_lastrow = -1;
	ze_lastclick = -999;
	ze_settings = FALSE;
	ze_field = -1;
	if (ze_grid < 1)
	{
		ze_grid = 16;
		ze_snap = TRUE;
	}
	ZoneEdit_ToPanel();
	if (ui_ze_state)
		print("^5zone_edit^7: add a zone from the panel, then aim and click; ESC closes\n");
};

void() ZoneEdit_Status =
{
	local float z;
	local vector p;

	print(sprintf("zone_edit: state %g map %s zones %g points %g dirty %g crc %s\n", ui_ze_state,
	              (ze_map != "") ? ze_map : "-", zone_count, zone_ptcount, ze_dirty,
	              (zone_crc != "") ? zone_crc : "-"));
	print(sprintf("zone_edit: cursor %g polygon %g corners %g window %g %g\n", ze_cursor, ze_poly, ze_np, ze_window_x, ze_window_y));
	print(sprintf("zone_edit: first list row %g\n", ze_scroll));
	print(sprintf("zone_edit: track %g sel %g grid %g snap %g source %s\n", ze_track, ze_sel, ze_grid,
	              ze_snap, Zone_SourceName(zone_source)));
	print(sprintf("zone_edit: placing type %g seg %g cp %g a %g %g %g", ze_ntype, ze_nseg, ze_ncp,
	              ze_a_x, ze_a_y, ze_a_z));
	print(sprintf(" b %g %g h %g hit %g %g %g ok %g\n", ze_b_x, ze_b_y, ze_h, ze_hit_x, ze_hit_y,
	              ze_hit_z, ze_hitok));
	// (sprintf takes eight arguments at most: three prints a zone, one line.)
	for (z = 0; z < zone_count; z = z + 1)
	{
		print(sprintf("zone_edit: zone %g %s track %g seg %g cp %g pts %g", z, Zone_TypeName(zone_type[z]),
		              zone_track[z], zone_seg[z], zone_cp[z], zone_npts[z]));
		p = zone_zmins[z];
		print(sprintf(" z %g %g box %g %g", zone_bottom[z], zone_top[z], p_x, p_y));
		p = zone_zmaxs[z];
		print(sprintf(" %g %g", p_x, p_y));
		p = zone_td_pos[z];
		// The destination too: Zone_Hash does not cover it, so only this line can show a save kept it.
		print(sprintf(" td %g %g %g %g %g [%s]\n", zone_td_kind[z], p_x, p_y, p_z, zone_td_yaw[z],
		              zone_td_name[z]));
	}
};

/*
  zone_edit                 open or close
  zone_edit save [force] | forget | status      force: write an unchanged table too
  zone_edit publish         P1081: open the publish dialog (its buttons need a real click)
  zone_edit add <start|end|stage|checkpoint> <track> <x1> <y1> <x2> <y2> <bottom> <height>
  zone_edit del <n> | sel <n> | track <n>
  zone_edit place <start|end|stage|checkpoint>     as the panel's + buttons
  zone_edit click | back                            as MOUSE1 and MOUSE2 while placing
  The last three are how an arm drives the same code the mouse does.
*/
float(string cmd) ZoneEdit_ConsoleCommand =
{
	local float n, t, z;
	local string a;
	local vector zv;

	n = tokenize(cmd);
	if (argv(0) != "zone_edit")
		return FALSE;
	a = argv(1);
	if (n == 1)
	{
		if (ui_ze_state)
		{
			UI_CursorRelease(UIC_ZONEEDIT);
			ze_cursor = ze_drag = FALSE;
			ze_field = -1; sui_text_unfocus();
			ui_ze_state = ZE_OFF;
			print("^5zone_edit^7: off\n");
		}
		else
			ZoneEdit_Open();
		return TRUE;
	}
	if (a == "status")
	{
		ZoneEdit_Status();
		return TRUE;
	}
	if (!ui_ze_state)
	{
		print("^3zone_edit^7: open it first (zone_edit)\n");
		return TRUE;
	}
	// P1081: on a server, any word here may be the server's (see WHO MAY WRITE A FILE).
	if (a != "publish" && a != "upload" && a != "edgeprobe")
	if (!ZoneEdit_Hosting())
		zone_cmd_taint = TRUE;
	t = -1;
	if (argv(2) == "start")           t = ZONE_START;
	else if (argv(2) == "end")        t = ZONE_END;
	else if (argv(2) == "stage")      t = ZONE_STAGE;
	else if (argv(2) == "checkpoint") t = ZONE_CHECKPOINT;
	if (ui_ze_state >= ZE_A)
	if (a != "click" && a != "back" && a != "mouse" && a != "point" && a != "close" && a != "height" && a != "grid")
	{
		print("^3zone_edit^7: finish or cancel the zone being placed first (click, back)\n");
		return TRUE;
	}
	if (a == "save")
		ZoneEdit_Save(argv(2) == "force");
	else if (a == "publish" || a == "upload")
		ZonePub_Begin(FALSE);           // P1081: opens the dialog; only a real press sends
	else if (a == "forget")
		ZoneEdit_Forget();
	else if (a == "track")
	{
		ze_track = bound(0, stof(argv(2)), 12);
		ze_sel = -1;
	}
	else if (a == "sel")
		ze_sel = (stof(argv(2)) >= 0 && stof(argv(2)) < zone_count) ? stof(argv(2)) : -1;
	else if (a == "del")
	{
		z = stof(argv(2));
		if (argv(2) != "" && z >= 0 && z < zone_count)
		{
			ZoneEdit_Remove(z);
			ze_sel = -1;
			ZoneEdit_Touch();
		}
	}
	else if (a == "place" && t >= 0)
	{
		if (ui_ze_state == ZE_PANEL)
			ZoneEdit_Begin(t);
	}
	else if (a == "press" && argv(2) != "")
	{
		// The panel's own branch runs it on its next frame: ze_as + start, ze_ag + stage,
		// ze_ac + checkpoint, ze_ae + end, ze_t<n> a track, ze_z<n> a row, ze_rp re-place,
		// ze_sp spawn here, ze_dl delete, ze_g<n> the grid, ze_gs surface, ze_sv save,
		// ze_rl reload, ze_cl close.
		if (ze_press != "")
			strunzone(ze_press);
		ze_press = strzone(argv(2));
	}
	else if (a == "click")
		ze_click = (ui_ze_state >= ZE_A);
	else if (a == "back")
		ze_back = (ui_ze_state >= ZE_A);
	else if (a == "pasteprobe")
		print(sprintf("zone_edit: synthetic paste took %g\n", ZoneEdit_Paste(stof(argv(2)))));
	else if (a == "edgeprobe")
	{
		zv = ZoneEdit_EdgeSnap([stof(argv(2)), stof(argv(3)), stof(argv(4))]);
		print(sprintf("zone_edit: edge snap %g %g %g\n", zv_x, zv_y, zv_z));
	}
	else if (a == "pointer")
	{
		// Synthetic cursor probe; never marks cl_input_real or authorizes a save.
		ZoneEdit_InputEvent(IE_MOUSEABS, stof(argv(2)), stof(argv(3)), 0);
	}
	else if (a == "mouse") ZoneEdit_ToggleMouse();
	else if (a == "shape") ze_poly = (argv(2) == "polygon");
	else if (a == "point")
	{
		if (ui_ze_state == ZE_P && n == 5)
		{
			ze_hit = [stof(argv(2)), stof(argv(3)), stof(argv(4))];
			ze_hitz = ze_hit_z; ze_hitok = TRUE; ZoneEdit_PolygonClick();
		}
	}
	else if (a == "close") { if (ui_ze_state == ZE_P) ZoneEdit_PolygonClose(); }
	else if (a == "height") { if (ui_ze_state == ZE_H) ze_h = ZoneEdit_Height(ze_a_z + stof(argv(2))); }
	else if (a == "grid") { ze_grid = bound(1, stof(argv(2)), 64); ze_snap = (argv(3) != "surface"); }
	else if (a == "snapxyz") ZoneEdit_SnapSelected();
	else if (a == "row")
	{
		z = stof(argv(2)); if (z >= 0 && z < zone_count) ZoneEdit_RowClick(z);
	}
	else if (a == "settings") ZoneEdit_SettingsOpen();
	else if (a == "mode") ZoneEdit_SettingMode(argv(2) == "bhop" ? 2 : 1);
	else if (a == "resetspawn") ZoneEdit_ResetSpawn();
	else if (a == "setting")
	{
		for (z = 0; z < MAPSET_COUNT; z = z + 1)
			if (strcmp(argv(2), MapSet_Name(z)) == 0)
			{
				ZoneEdit_SettingEdit(z); strunzone(ze_text); ze_text = strzone(argv(3));
				ZoneEdit_SettingApply(); break;
			}
	}
	else if (a == "savesettings") ZoneEdit_SettingsSave();
	else if (a == "add" && t >= 0 && n >= 10)
	{
		ze_track = bound(0, stof(argv(3)), 12);
		if ((t == ZONE_START || t == ZONE_END) && ZoneEdit_Has(ze_track, t))
			print("^3zone_edit^7: that track has one\n");
		else
		{
			// As the panel would number it: ZoneEdit_Begin's choice, without leaving the panel.
			ZoneEdit_Begin(t);
			if (ui_ze_state >= ZE_A)
			{
				ze_a = [stof(argv(4)), stof(argv(5)), stof(argv(8))];
				ze_b = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
				ze_floor = stof(argv(8)) - 1;       // by command the floor is the bottom given
				ze_h = bound(ZE_MINH, stof(argv(9)), ZE_MAXH);
				ZoneEdit_Commit();
			}
		}
	}
	else
		print("zone_edit [save [force]|publish|forget|status|track n|sel n|del n|place type|click|back|press id|"
		      "add type track x1 y1 x2 y2 bottom height]\n");
	return TRUE;
};

void() ZoneEdit_Register =
{
	registercommand("zone_edit");
	ze_field = -1;
	ze_sel = -1;
	ze_replace = -1;
	ze_grid = 16;
	ze_snap = TRUE;
};
