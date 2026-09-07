/*
===========================================================================
  sh_zones.qc -- Momentum Mod timer zones.

  WHERE THE DATA ACTUALLY IS
  --------------------------
  Not in the BSP -- almost.  The zone_* classnames in momentum.fgd
  (zone_timer_start, zone_allowbhop, ...) are authoring entities: Momentum's
  in-game zone editor compiles them out to external JSON, and that JSON is what
  this file reads.

      maps/zones/local/<map>.json      13 files, your own edits, WINS
      maps/zones/online/<map>.json    522 files, the shipped library

  "AND APPEAR IN EXACTLY ZERO SHIPPED MAPS" is what this used to say, and it
  was wrong.  They appear in at least fifteen, as 189 brush entities --
  bhop_arcane alone carries 7 (2 start, 2 end, 4 checkpoint, 1 cancel).  The
  claim came from an offline scan that read raw entity lumps, and the Momentum
  library LZMA-compresses most of them; bhop_futile is a plain VBSP v20 and its
  lump is compressed too, so this is not a newer-map special case.  That same
  flawed scan is why func_bhop spent four builds in the catch-all's non-solid
  list, which is build 37's bug (see sv_entities.qc).

  Nothing downstream moves: the external JSON is still the source of truth for
  zone geometry, and the catch-all makes any zone_* brush that IS in a lump
  non-solid so it cannot become an invisible wall.  What was wrong was the
  confidence, not the design.

  535 of the 1308 installed Momentum maps have zone data.  The rest, and every
  CS:S map, have none -- so "no zones" is the common case and must be silent.

  WHAT A ZONE IS
  --------------
  An EXTRUDED 2D CONVEX POLYGON: an ordered ring of [x,y] points, a `bottom`
  Z and a `height`.  Not an AABB, not a brush index.  Region point counts run
  up to 64 (surf_frost, surf_hourglass, surf_shoria) and about forty maps
  exceed the four points you would assume, so nothing here may assume a quad.

  SCHEMA, as measured across all 535 shipped files
  ------------------------------------------------
    tracks.main                     the run
    tracks.bonuses[]                up to 11 of them
      zones.segments[]              segments[0] is the start stage
        checkpoints[]               checkpoints[0] is that segment's START zone
          regions[]  { points[[x,y]..], bottom, height, teleDestTargetname }
      zones.end.regions[]
    globalRegions.allowBhop[]       FLAT arrays of regions, not {regions:[]}
    globalRegions.cancel[]          `cancel` lives HERE, not under tracks
    globalRegions.overbounce[]      only 3 maps have any

  Region totals across the library: start 1770, end 1901, stage 1452,
  checkpoint 1455, cancel 138, allowBhop 3217, overbounce 5.

  KEYS THIS PARSER STILL IGNORES, and what depends on that.  A segment carries
  `checkpointsRequired`, `checkpointsOrdered` and `limitStartGroundSpeed`; a
  track carries `stagesEndAtStageStarts` and `bhopEnabled`.  None is read.  The
  build 19 checkpoint timing implements `checkpointsOrdered: true` by convention
  -- it only ever counts a gate whose ordinal is higher than the highest reached
  so far -- which is correct for every shipped file I have looked at and is what
  makes a multi-region gate count once.  A map that genuinely wanted unordered
  checkpoints would need the key read here; nothing else has to change.

  WHERE A TELEPORT ACTUALLY GOES
  ------------------------------
  Every start region (1770 of 1770) and every stage region (1452 of 1452) in
  the shipped library declares a destination -- 3241 as `teleDestTargetname`
  naming an info_teleport_destination in the BSP, 56 as an explicit
  `teleDestPos` + `teleDestYaw`.  The FGD calls the key `restart_destination`:
  "the point to which the player should be teleported when restarting a
  stage... placed directly on the ground below this point if possible".

  This file used to read points/bottom/height and stop, so SV_ZoneMove aimed at
  the polygon's centroid at bottom+2 instead.  Measured against the 525 maps
  that have both a zone file and a BSP, 96% of destinations are more than 32
  units away from that -- median 185, p90 417 -- and 126 of 3154 legs put the
  centroid OUTSIDE its own polygon.  A Momentum start zone extends below the
  floor, so on surf_666 the six stage destinations landed 190-286 units inside
  the brushwork, which is what "invisible blocks prevent me being teleported to
  the start of the stages" was.

  CAPS
  ----
  Worst observed map is surf_classics3: 162 regions, 787 points, 11 bonuses --
  63% and 38% of the caps below, and that is re-measured, not inherited.  On a
  cap hit a region is SKIPPED and the load continues.  It used to abort the
  whole load, which is not "refuse rather than truncate" as this comment once
  claimed: regions are added in file order, so main START (load index 0) always
  survived and what actually vanished was main END, then the bonuses, then
  globalRegions -- silently, and in the order most likely to look like the map
  simply has no finish line.

  MEASUREMENT NOTE.  Three figures in the original of this comment were wrong
  because the offline scan behind them read raw entity lumps, and 728 of the
  1308 Momentum maps store theirs LZMA-compressed.  Re-scanned: 34 legacy
  trigger_momentum_timer_* maps (not 17), trigger_momentum_teleport in 12 maps
  (not 239), and the zone_* classnames appear in 15 shipped maps as 189 brush
  entities (not "exactly zero") -- see sv_entities.qc, where they were becoming
  invisible walls.
===========================================================================
*/

#define ZONE_MAX          256
#define ZONE_MAX_POINTS  2048

#define ZONE_START        0
#define ZONE_END          1
#define ZONE_STAGE        2
#define ZONE_CHECKPOINT   3
#define ZONE_CANCEL       4
#define ZONE_BHOP         5
#define ZONE_OVERBOUNCE   6
#define ZONE_TYPES        7

#define ZSRC_NONE         0
#define ZSRC_LOCAL        1
#define ZSRC_ONLINE       2
#define ZSRC_BSP          3

// Structure-of-arrays rather than entities: the renderer walks all of them
// every frame and the timer's broad phase will too, so locality matters more
// than tidiness.  ~30 KB per module.
float  zone_type[ZONE_MAX];
float  zone_track[ZONE_MAX];        // 0 = main, 1.. = bonus number
float  zone_seg[ZONE_MAX];          // segment index within the track
/*
  The checkpoint's ORDINAL within its track, 1-based; 0 for everything that is
  not a checkpoint.  Build 19.

  Until this the parser typed a region from its position and then threw the
  position away, storing only the segment -- so on a linear map every checkpoint
  came out as segment 0 and nothing downstream could tell them apart.  That is
  why the .rec has been writing `cp 0 <ticks>` for every gate on every linear map
  since checkpoints were first recorded, and why there was no index a per-
  checkpoint best could be stored under.

  NUMBERED ACROSS THE WHOLE TRACK, not restarted per segment.  checkpoints[]
  restarts at 1 inside every segment, so a per-segment ordinal would collide on a
  staged map -- stage 2's first checkpoint would share a number with stage 1's,
  and the "only ever go forwards" rule that dedupes multi-region gates would
  throw the second one away.  A track-wide counter is also the right key for
  run_pb_cp, which is keyed on the track for the same reason run_pb_split is.
*/
float  zone_cp[ZONE_MAX];
float  zone_first[ZONE_MAX];        // index into zone_pt
float  zone_npts[ZONE_MAX];
float  zone_bottom[ZONE_MAX];
float  zone_top[ZONE_MAX];
vector zone_centre[ZONE_MAX];       // precomputed, for distance culling
float  zone_radius[ZONE_MAX];
vector zone_zmins[ZONE_MAX];
vector zone_zmaxs[ZONE_MAX];

/*
  Where `!m` / `!s N` / `!b N` / `!r` should put you for this region.

  Per REGION, not per leg: surf_ace's bonus 1 and surf_lullaby's main track each
  have two start regions with different destinations, so one slot per zone row
  is the correct granularity and a shared one would be wrong on those maps.

  zone_td_name is strzone'd on the way in and released in Zone_Clear.  That is
  belt and braces rather than a requirement: PR_JSON_Linearise allocates each
  string VALUE as a tempstring independent of the node block json_free releases,
  and QC globals are a GC root (PR_QCGC_Mark scans the addressable hunk), so the
  bare assignment would survive.  strzone is documented as redundant under
  FTE_QC_PERSISTENTTEMPSTRINGS and strunzone as a no-op, so the pair costs
  nothing and stops this depending on a guarantee three layers down.

  (json node NAMES are a different matter -- those ARE memcpy'd into the block
  json_free hands back, so nothing may be built on json_get_name.)
*/
#define ZTD_NONE  0
#define ZTD_POS   1                 // explicit teleDestPos + teleDestYaw
#define ZTD_NAME  2                 // an info_teleport_destination to find()

float  zone_td_kind[ZONE_MAX];
vector zone_td_pos[ZONE_MAX];
float  zone_td_yaw[ZONE_MAX];
string zone_td_name[ZONE_MAX];

vector zone_pt[ZONE_MAX_POINTS];    // x,y used; z always 0

float  zone_count;
float  zone_ptcount;
float  zone_source;                 // ZSRC_*
string zone_mapname;                // what the tables were built for
float  zone_overflow;               // hit a cap on this map

string(float t) Zone_TypeName =
{
	if (t == ZONE_START)      return "start";
	if (t == ZONE_END)        return "end";
	if (t == ZONE_STAGE)      return "stage";
	if (t == ZONE_CHECKPOINT) return "checkpoint";
	if (t == ZONE_CANCEL)     return "cancel";
	if (t == ZONE_BHOP)       return "bhop";
	if (t == ZONE_OVERBOUNCE) return "overbounce";
	return "?";
};

string(float s) Zone_SourceName =
{
	if (s == ZSRC_LOCAL)  return "maps/zones/local";
	if (s == ZSRC_ONLINE) return "maps/zones/online";
	if (s == ZSRC_BSP)    return "bsp entities";
	return "none";
};

/*
  HOW MANY SEGMENTS A TRACK HAS, and there is now exactly ONE speller of it.

  THE END ZONE'S SEGMENT INDEX **IS** THE SEGMENT COUNT.  Zone_AddTrack sets it
  to nseg after walking the stages, so a 5-stage track's stage zones carry 1..4
  and its end zone carries 5.  A track with no end zone reads 1 -- linear -- which
  is the safe answer for a map that cannot be timed anyway.

  MOVED HERE IN BUILD 24, AND THE MOVE WAS A BUG FIX.  SV_TrackSegs had this
  right and was the only thing that did; build 24's replay reader and its
  leaderboard both wrote `max(zone_seg) + 1` independently, which counts the END
  zone as a segment of its own.  On surf_aesthetic that is 6 against the server's
  5, so the replay's panel read "stage 1/6" beside a live panel reading "stage
  1/5", and the leaderboard grew a `stage_5` leg that no run can ever be written
  into -- a row that looks exactly like a real one until you click it.

  Two independent reimplementations of one rule, both wrong the same way, inside
  one build.  That is what a shared speller is for; see FS_RunPath, which exists
  for the identical reason.
*/
float(float track) Zone_TrackSegs =
{
	local float z, n;

	n = 1;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_type[z] == ZONE_END)
		if (zone_track[z] == track)
		{
			n = zone_seg[z];
			if (n < 1)
				n = 1;
			return n;
		}
	return n;
};

// Does this track exist at all?  A gap in the track numbering is legal in the
// zone format, so "how many segments" and "is there anything here" are two
// questions and the leaderboard needs both -- a track with no zones must not
// produce a leg row.
float(float track) Zone_TrackExists =
{
	local float z;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == track)
			return TRUE;
	return FALSE;
};

void() Zone_Clear =
{
	local float z;

	// Release the destination names before the count goes, or they leak a
	// zoned string per region per map change.
	for (z = 0; z < zone_count; z = z + 1)
	{
		if (zone_td_name[z] != "")
			strunzone(zone_td_name[z]);
		zone_td_name[z] = "";
		zone_td_kind[z] = ZTD_NONE;
	}

	zone_count = 0;
	zone_ptcount = 0;
	zone_source = ZSRC_NONE;
	zone_overflow = FALSE;
};

/*
  Finish a region: derive the bounds, centre and radius the renderer and the
  eventual timer both want, so neither has to walk the points again.
*/
void(float z) Zone_Finish =
{
	local float i, n, first;
	local vector mn, mx, p;

	first = zone_first[z];
	n = zone_npts[z];
	if (n < 1)
		return;

	p = zone_pt[first];
	mn = [p_x, p_y, zone_bottom[z]];
	mx = [p_x, p_y, zone_top[z]];

	for (i = 1; i < n; i = i + 1)
	{
		p = zone_pt[first + i];
		if (p_x < mn_x) mn_x = p_x;
		if (p_y < mn_y) mn_y = p_y;
		if (p_x > mx_x) mx_x = p_x;
		if (p_y > mx_y) mx_y = p_y;
	}

	zone_zmins[z] = mn;
	zone_zmaxs[z] = mx;
	zone_centre[z] = (mn + mx) * 0.5;
	zone_radius[z] = vlen(mx - mn) * 0.5;
};

/*
  Point-in-zone.

  THE RINGS ARE NOT ALL CONVEX, and this used to assume they were.

  The original of this test accepted a point that was on the same side of
  every edge, whichever side that turned out to be -- a winding test, correct
  for a convex ring and correct for the 8152 four-point quads that are most of
  the library.  It is wrong for the rest: measured across all 522 shipped zone
  files, 1029 of 10130 regions (10.2%), on 287 maps, are NON-CONVEX.  They are
  mostly chevrons and arrows -- surf_doodles' start is a seven-point arrow --
  drawn that way in Momentum's zone editor to point down the route.

  On one of those, a winding test returns true only inside the polygon's
  KERNEL (the intersection of all its edge half-planes), which for an arrow is
  a sliver and can be empty.  So the affected zones were quietly much smaller
  than they were drawn, and on the worst of them unreachable.  It was
  invisible until something asked the question often enough to notice: the
  renderer only draws the ring and never tests a point against it.

  Replaced with the standard crossing-number test (PNPOLY), which is correct
  for convex and concave rings alike, needs no winding convention, and costs
  the same one pass over the edges.

  Not used by the renderer.  It is here because it is the timer's whole
  broad-phase-plus-narrow-phase and belongs with the data it reads.
*/
float(float z, vector p) Zone_PointInside =
{
	local float i, n, first, inside, xint;
	local vector a, b, mn, mx;

	if (z < 0 || z >= zone_count)
		return FALSE;

	if (p_z < zone_bottom[z] || p_z > zone_top[z])
		return FALSE;

	/*
	  AABB FIRST, and it is not a micro-optimisation.

	  The timer asks this question for every zone on every tick for every
	  player, and a region may carry 64 points (surf_frost, surf_hourglass,
	  surf_shoria).  256 zones x 64 edges x 6 arithmetic ops is 98k operations
	  a tick; the reject below turns almost all of it into four compares.

	  It cannot change the answer: zone_zmins/zmaxs ARE the ring's own x/y
	  bounds (Zone_Finish walks the same points to build them), so a point
	  outside the box is outside every edge test too.
	*/
	mn = zone_zmins[z];
	mx = zone_zmaxs[z];
	if (p_x < mn_x || p_x > mx_x || p_y < mn_y || p_y > mx_y)
		return FALSE;

	first = zone_first[z];
	n = zone_npts[z];
	if (n < 3)
		return FALSE;

	/*
	  Cast a ray in -x from p and count edge crossings; odd means inside.

	  The `(a_y > p_y) != (b_y > p_y)` guard does two jobs: it selects only the
	  edges the ray can cross, and it guarantees b_y != a_y, so the division
	  below cannot be by zero.  A horizontal edge is never selected, which is
	  what makes the test well defined on the axis-aligned quads that are most
	  of this data.
	*/
	inside = FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		a = zone_pt[first + i];
		b = zone_pt[first + ((i + 1) % n)];

		if ((a_y > p_y) != (b_y > p_y))
		{
			xint = a_x + (p_y - a_y) * (b_x - a_x) / (b_y - a_y);
			if (p_x < xint)
				inside = !inside;
		}
	}
	return inside;
};

/*
  Did the segment a..b pass through zone z at any point?

  A POINT TEST PER TICK IS NOT ENOUGH, and the shipped data says so.  Measured
  across all 522 zone files: of 6772 regions, **101 have a dimension under 32
  units and several are one unit thick** -- surf_void's is a 3456x3456 plane
  1 unit tall, surf_sheepy's is 2880x1280x1, and surf_simpsons2 has one 16
  units wide.  Those are trigger PLANES; you are meant to fall through them.

  At 66.67 Hz a player falling at 800 u/s moves 12 units a tick and a surfer
  at 2000 covers 30, so a one-unit plane is missed nine times in ten.  The
  split never fires, the run keeps its old segment, and `!r` then sends you
  back to the last leg you actually touched -- which is the start of the map.

  Sampling along the segment cannot fix that: no step small enough to catch a
  one-unit plane is affordable, and any step at all is a lie about a plane
  thinner than it.  So this is EXACT instead:

    1. clip the 3D segment to the zone's [bottom, top] slab,
    2. if either clipped end is inside the ring, it passed through,
    3. otherwise ask whether the 2D segment crosses any ring edge.

  Step 3 is a plain segment-segment orientation test, which is right for a
  concave ring as well as a convex one -- the same reason Zone_PointInside is
  a crossing-number test now.  Cost is four cross products per edge against
  PNPOLY's one division, on rings that are four points 80% of the time.
*/
float(float z, vector a, vector b) Zone_SegmentInside =
{
	local float i, n, first, dz, ta, tb, t0, t1, tmp;
	local float d1, d2, d3, d4;
	local vector p, q, e0, e1, mn, mx;

	if (z < 0 || z >= zone_count)
		return FALSE;

	n = zone_npts[z];
	if (n < 3)
		return FALSE;

	/* --- clip to the height slab ------------------------------------- */
	t0 = 0;
	t1 = 1;
	dz = b_z - a_z;
	if (dz == 0)
	{
		if (a_z < zone_bottom[z] || a_z > zone_top[z])
			return FALSE;
	}
	else
	{
		ta = (zone_bottom[z] - a_z) / dz;
		tb = (zone_top[z]    - a_z) / dz;
		if (ta > tb) { tmp = ta; ta = tb; tb = tmp; }
		if (ta > t0) t0 = ta;
		if (tb < t1) t1 = tb;
		if (t0 > t1)
			return FALSE;
	}

	p = a + (b - a) * t0;
	q = a + (b - a) * t1;

	/* --- reject on the ring's own x/y bounds -------------------------- */
	mn = zone_zmins[z];
	mx = zone_zmaxs[z];
	if (p_x < mn_x) { if (q_x < mn_x) return FALSE; }
	if (p_x > mx_x) { if (q_x > mx_x) return FALSE; }
	if (p_y < mn_y) { if (q_y < mn_y) return FALSE; }
	if (p_y > mx_y) { if (q_y > mx_y) return FALSE; }

	/* --- an end inside the ring is the common case -------------------- */
	if (Zone_PointInside(z, p))
		return TRUE;
	if (Zone_PointInside(z, q))
		return TRUE;

	/* --- otherwise: does it cross an edge? ---------------------------- */
	first = zone_first[z];
	for (i = 0; i < n; i = i + 1)
	{
		e0 = zone_pt[first + i];
		e1 = zone_pt[first + ((i + 1) % n)];

		d1 = (q_x - p_x)   * (e0_y - p_y)  - (q_y - p_y)   * (e0_x - p_x);
		d2 = (q_x - p_x)   * (e1_y - p_y)  - (q_y - p_y)   * (e1_x - p_x);
		d3 = (e1_x - e0_x) * (p_y - e0_y)  - (e1_y - e0_y) * (p_x - e0_x);
		d4 = (e1_x - e0_x) * (q_y - e0_y)  - (e1_y - e0_y) * (q_x - e0_x);

		if ((d1 > 0) != (d2 > 0))
			if ((d3 > 0) != (d4 > 0))
				return TRUE;
	}
	return FALSE;
};

/*
===========================================================================
  zone_selftest -- the two geometry tests, against answers worked out by hand.

  These are the only two functions in the game whose correctness cannot be
  seen on screen: a zone that is quietly the wrong shape looks exactly like a
  zone you did not quite reach, and a thin plane that is quietly never
  triggered looks exactly like a map with no split.  Both of those shipped,
  and both were found by accident.

  So they get pinned the way the movement maths is (pm_selftest): synthetic
  rings with known answers, run on demand, on a table appended past the real
  one and truncated away again.

  The cases are chosen to fail on the code that shipped before them --
  an L-shape's notch is INSIDE under the old convex winding test, and a
  one-unit plane straddled by a fifteen-unit fall is MISSED by a point test.
===========================================================================
*/
float zt_ok, zt_fail;

void(string what, float got, float want) Zone_Check =
{
	if ((got != 0) == (want != 0))
	{
		zt_ok = zt_ok + 1;
		print(sprintf("  ^2ok  ^7%-52s %s\n", what, want ? "inside" : "outside"));
	}
	else
	{
		zt_fail = zt_fail + 1;
		print(sprintf("  ^1FAIL^7 %-52s got %s, want %s\n", what,
		              got ? "inside" : "outside", want ? "inside" : "outside"));
	}
};

// Append a ring from a flat "x y x y ..." string.  Only the self-test builds
// zones this way; the loaders have their own paths.
float(string pts, float bottom, float height) Zone_AddRing =
{
	local float z, n, i;

	n = tokenize(pts);
	z = zone_count;

	zone_type[z]   = ZONE_START;
	zone_track[z]  = 0;
	zone_seg[z]    = 0;
	zone_first[z]  = zone_ptcount;
	zone_npts[z]   = n / 2;
	zone_bottom[z] = bottom;
	zone_top[z]    = bottom + height;
	zone_td_kind[z] = ZTD_NONE;
	zone_td_name[z] = "";

	for (i = 0; i < n; i = i + 2)
	{
		zone_pt[zone_ptcount] = [stof(argv(i)), stof(argv(i + 1)), 0];
		zone_ptcount = zone_ptcount + 1;
	}

	zone_count = zone_count + 1;
	Zone_Finish(z);
	return z;
};

void() Zone_SelfTest =
{
	local float savecount, saveptcount;
	local float sq, plane, ell;

	savecount   = zone_count;
	saveptcount = zone_ptcount;
	zt_ok = zt_fail = 0;

	if (zone_count + 3 > ZONE_MAX || zone_ptcount + 16 > ZONE_MAX_POINTS)
	{
		print("^1zone_selftest: no room in the tables on this map\n");
		return;
	}

	print("zone_selftest\n");

	/* ---- a plain 64-unit box, 0..64 tall ------------------------------ */
	sq = Zone_AddRing("0 0  64 0  64 64  0 64", 0, 64);

	Zone_Check("box: centre",                 Zone_PointInside(sq, '32 32 32'), TRUE);
	Zone_Check("box: outside in x",           Zone_PointInside(sq, '100 32 32'), FALSE);
	Zone_Check("box: above the top",          Zone_PointInside(sq, '32 32 100'), FALSE);
	Zone_Check("box: below the bottom",       Zone_PointInside(sq, '32 32 -1'), FALSE);
	Zone_Check("box: swept straight through", Zone_SegmentInside(sq, '32 32 -100', '32 32 200'), TRUE);
	Zone_Check("box: swept across",           Zone_SegmentInside(sq, '200 32 32', '-200 32 32'), TRUE);
	Zone_Check("box: swept alongside",        Zone_SegmentInside(sq, '32 200 32', '32 100 32'), FALSE);
	Zone_Check("box: swept over the top",     Zone_SegmentInside(sq, '-200 32 100', '200 32 100'), FALSE);

	/* ---- a ONE UNIT plane, which is what the point test fell through --- */
	plane = Zone_AddRing("0 0  1024 0  1024 1024  0 1024", 0, 1);

	Zone_Check("plane: a point inside its one unit",
	           Zone_PointInside(plane, '512 512 0.5'), TRUE);
	Zone_Check("plane: a point just under it",
	           Zone_PointInside(plane, '512 512 -7'), FALSE);
	/*
	  The case the whole swept test exists for.  A player falling at 1000 u/s
	  covers 15 units in a 66.67 Hz tick; this is one such tick, straddling the
	  plane and ending below it.  The point test sees only the far end.
	*/
	Zone_Check("plane: a 15-unit fall straddling it -- POINT test",
	           Zone_PointInside(plane, '512 512 -7'), FALSE);
	Zone_Check("plane: a 15-unit fall straddling it -- SWEPT test",
	           Zone_SegmentInside(plane, '512 512 8', '512 512 -7'), TRUE);
	Zone_Check("plane: a fall that stops above it",
	           Zone_SegmentInside(plane, '512 512 40', '512 512 25'), FALSE);
	Zone_Check("plane: a fall beside it",
	           Zone_SegmentInside(plane, '2000 512 8', '2000 512 -7'), FALSE);

	/* ---- a CONCAVE L, which the old winding test got wrong ------------- */
	ell = Zone_AddRing("0 0  64 0  64 32  32 32  32 64  0 64", 0, 64);

	Zone_Check("L: in the foot",              Zone_PointInside(ell, '48 16 32'), TRUE);
	Zone_Check("L: in the upright",           Zone_PointInside(ell, '16 48 32'), TRUE);
	Zone_Check("L: in the corner",            Zone_PointInside(ell, '16 16 32'), TRUE);
	/*
	  THE NOTCH.  A convex winding test answers "inside" here -- it is on the
	  same side of every edge -- which is exactly how 1029 of the library's
	  10130 regions were quietly the wrong shape.
	*/
	Zone_Check("L: in the NOTCH (convex test says inside)",
	           Zone_PointInside(ell, '48 48 32'), FALSE);
	Zone_Check("L: swept through the foot, both ends outside",
	           Zone_SegmentInside(ell, '-10 16 32', '74 16 32'), TRUE);
	Zone_Check("L: swept across the notch only",
	           Zone_SegmentInside(ell, '48 48 32', '48 80 32'), FALSE);
	Zone_Check("L: swept from the notch into the foot",
	           Zone_SegmentInside(ell, '48 48 32', '48 20 32'), TRUE);
	Zone_Check("L: swept above the slab entirely",
	           Zone_SegmentInside(ell, '16 16 100', '16 16 80'), FALSE);

	zone_count   = savecount;
	zone_ptcount = saveptcount;

	if (zt_fail)
		print(sprintf("^1%g of %g checks FAILED\n", zt_fail, zt_ok + zt_fail));
	else
		print(sprintf("^2all %g checks passed\n", zt_ok));
};

/*
===========================================================================
  JSON -> tables
===========================================================================
*/

// One region object: { points:[[x,y]..], bottom, height, ... }
// Returns FALSE only on a cap overflow, which aborts the whole load.
float(int rgn, float type, float track, float seg, float cpn) Zone_AddRegion =
{
	local int pts, pt, tdp;
	local float i, n, z;
	local string nm;

	pts = json_find_object_child(rgn, "points");
	n = json_get_length(pts);
	if (n < 3)
		return TRUE;			// degenerate; skip it, but keep loading

	// SKIP the region, do not abort the load.  See the CAPS note at the top:
	// regions arrive in file order, so aborting kept main START and threw away
	// main END, the bonuses and globalRegions -- silently, and in the worst
	// possible order.  Nothing in the shipped library gets near these caps.
	if (zone_count >= ZONE_MAX || zone_ptcount + n > ZONE_MAX_POINTS)
	{
		zone_overflow = TRUE;
		return TRUE;
	}

	z = zone_count;
	zone_type[z]   = type;
	zone_track[z]  = track;
	zone_seg[z]    = seg;
	zone_cp[z]     = cpn;
	zone_first[z]  = zone_ptcount;
	zone_npts[z]   = n;
	zone_bottom[z] = json_get_float(json_find_object_child(rgn, "bottom"));
	zone_top[z]    = zone_bottom[z] +
	                 json_get_float(json_find_object_child(rgn, "height"));

	/*
	  The declared destination.  teleDestPos wins where both exist -- it is an
	  explicit answer, where the targetname is a reference that may not resolve.

	  Handle 0 is a valid null node (sh_json.qc), so a region carrying neither
	  key walks through this and leaves ZTD_NONE without a single guard.
	*/
	zone_td_kind[z] = ZTD_NONE;
	zone_td_pos[z]  = '0 0 0';
	zone_td_yaw[z]  = 0;
	zone_td_name[z] = "";

	tdp = json_find_object_child(rgn, "teleDestPos");
	if (json_get_length(tdp) >= 3)
	{
		zone_td_pos[z] = [json_get_float(json_get_child_at_index(tdp, 0)),
		                  json_get_float(json_get_child_at_index(tdp, 1)),
		                  json_get_float(json_get_child_at_index(tdp, 2))];
		zone_td_yaw[z]  = json_get_float(json_find_object_child(rgn, "teleDestYaw"));
		zone_td_kind[z] = ZTD_POS;
	}
	else
	{
		nm = json_get_string(json_find_object_child(rgn, "teleDestTargetname"));
		if (nm != "")
		{
			zone_td_name[z] = strzone(nm);
			zone_td_kind[z] = ZTD_NAME;
		}
	}

	for (i = 0; i < n; i = i + 1)
	{
		pt = json_get_child_at_index(pts, i);
		zone_pt[zone_ptcount] =
			[json_get_float(json_get_child_at_index(pt, 0)),
			 json_get_float(json_get_child_at_index(pt, 1)), 0];
		zone_ptcount = zone_ptcount + 1;
	}

	zone_count = zone_count + 1;
	Zone_Finish(z);
	return TRUE;
};

// A bare regions[] array.  Both entry points into the region parser use this:
// checkpoints have {regions:[]}, globalRegions.* ARE the array.
float(int arr, float type, float track, float seg, float cpn) Zone_AddRegionArray =
{
	local float i, n;

	n = json_get_length(arr);
	for (i = 0; i < n; i = i + 1)
		if (!Zone_AddRegion(json_get_child_at_index(arr, i), type, track, seg, cpn))
			return FALSE;
	return TRUE;
};

/*
  One track (main, or a bonus).

  The type of a checkpoint region is positional, not labelled:
    segment 0, checkpoint 0  ->  the START zone
    segment N, checkpoint 0  ->  a STAGE zone
    any other checkpoint     ->  a CHECKPOINT
  and zones.end is its own object hanging off the track, not a segment.

  cpn is that position kept rather than discarded -- see zone_cp[].  It counts
  across the whole track, so it does not restart with ci in each segment.
*/
float(int track, float tracknum) Zone_AddTrack =
{
	local int zones, segs, seg, cps, cp, endz;
	local float si, ci, nseg, ncp, type, cpn;

	zones = json_find_object_child(track, "zones");

	cpn = 0;

	segs = json_find_object_child(zones, "segments");
	nseg = json_get_length(segs);
	for (si = 0; si < nseg; si = si + 1)
	{
		seg = json_get_child_at_index(segs, si);
		cps = json_find_object_child(seg, "checkpoints");
		ncp = json_get_length(cps);

		for (ci = 0; ci < ncp; ci = ci + 1)
		{
			cp = json_get_child_at_index(cps, ci);

			if (ci != 0)          type = ZONE_CHECKPOINT;
			else if (si == 0)     type = ZONE_START;
			else                  type = ZONE_STAGE;

			// Every REGION of one checkpoint shares its ordinal.  surf_utopia's
			// first gate is a mirrored pair -- two rows, one number -- and that
			// is what stops it being counted twice at run time.
			if (type == ZONE_CHECKPOINT)
				cpn = cpn + 1;

			if (!Zone_AddRegionArray(json_find_object_child(cp, "regions"),
			                         type, tracknum, si,
			                         (type == ZONE_CHECKPOINT) ? cpn : 0))
				return FALSE;
		}
	}

	endz = json_find_object_child(zones, "end");
	return Zone_AddRegionArray(json_find_object_child(endz, "regions"),
	                           ZONE_END, tracknum, nseg, 0);
};

// Read the whole file in one go.  FILE_READNL makes fgets return the entire
// file as a single tempstring (pr_bgcmd.c:2777-2793, 3038-3044) instead of one
// line at a time, so this works on the minified and the pretty-printed files
// alike -- and the shipped library contains both.
string(string path) Zone_ReadFile =
{
	local filestream f;
	local string s;

	f = fopen(path, FILE_READNL);
	if (f < 0)
		return "";

	s = fgets(f);
	fclose(f);
	return s;
};

float(string path, float src) Zone_LoadJson =
{
	local string text;
	local int root, tracks, bonuses, gr;
	local float i, n, ok;

	text = Zone_ReadFile(path);
	if (text == "")
		return FALSE;

	root = json_parse(text);
	if (!root)
	{
		print(sprintf("^1zones: %s is not valid JSON\n", path));
		return FALSE;
	}

	Zone_Clear();
	ok = TRUE;

	tracks = json_find_object_child(root, "tracks");

	// Handle 0 is a safe null node, so a file with no "tracks" walks straight
	// through this without a single guard and simply adds nothing.
	if (ok) ok = Zone_AddTrack(json_find_object_child(tracks, "main"), 0);

	bonuses = json_find_object_child(tracks, "bonuses");
	n = json_get_length(bonuses);
	for (i = 0; i < n && ok; i = i + 1)
		ok = Zone_AddTrack(json_get_child_at_index(bonuses, i), i + 1);

	// globalRegions.* are FLAT region arrays -- no {regions:[]} wrapper.
	gr = json_find_object_child(root, "globalRegions");
	if (ok) ok = Zone_AddRegionArray(json_find_object_child(gr, "cancel"),     ZONE_CANCEL,     0, 0, 0);
	if (ok) ok = Zone_AddRegionArray(json_find_object_child(gr, "allowBhop"),  ZONE_BHOP,       0, 0, 0);
	if (ok) ok = Zone_AddRegionArray(json_find_object_child(gr, "overbounce"), ZONE_OVERBOUNCE, 0, 0, 0);

	json_free(root);

	// Driven off zone_overflow rather than off `ok`, because a cap hit now skips
	// one region and keeps loading -- so `ok` stays TRUE and the warning would
	// never appear.  It has to appear: a silently short zone table is the shape
	// of bug that reads as "this map has no finish line".
	if (zone_overflow)
		print(sprintf("^1zones: %s exceeds the %g zone / %g point cap -- "
		              "%g zones loaded, some regions skipped\n",
		              path, ZONE_MAX, ZONE_MAX_POINTS, zone_count));

	zone_source = src;
	return TRUE;
};

/*
  Legacy maps.

  Seventeen maps carry trigger_momentum_timer_* BRUSH entities in the entity
  lump instead of a zone file, and the two sources provably never coexist --
  so for those this is the only source there is.  A brush trigger's AABB is a
  four-point extruded polygon, which is exactly the shape the tables already
  hold, so this needs no renderer changes at all.

  trigger_momentum_teleport (239 maps) is deliberately NOT read here: it is a
  reset volume, not a timer zone, and belongs with the timer work.
*/
float(string cn) Zone_LegacyType =
{
	if (cn == "trigger_momentum_timer_start")      return ZONE_START;
	if (cn == "trigger_momentum_timer_stop")       return ZONE_END;
	if (cn == "trigger_momentum_timer_stage")      return ZONE_STAGE;
	if (cn == "trigger_momentum_timer_checkpoint") return ZONE_CHECKPOINT;
	return -1;
};

void(vector mn, vector mx, float type, float stage) Zone_AddBox =
{
	local float z;

	if (zone_count >= ZONE_MAX || zone_ptcount + 4 > ZONE_MAX_POINTS)
	{
		zone_overflow = TRUE;
		return;
	}

	z = zone_count;
	zone_type[z]   = type;
	zone_track[z]  = 0;
	zone_seg[z]    = stage;
	/*
	  The legacy brush triggers have no checkpoint ordinal to give: all a
	  trigger_momentum_timer_checkpoint carries is `stage`, and on the 34 maps
	  that use this path (all of them linear) that key IS the gate's number.  So
	  reuse it rather than writing 0, which would make every checkpoint on those
	  maps share an ordinal and collapse them into one under the forward-only
	  rule.  A map that leaves the key unset gets 0 and is simply not timed at
	  its checkpoints, which is what it got before build 19 anyway.
	*/
	zone_cp[z]     = (type == ZONE_CHECKPOINT) ? stage : 0;
	zone_first[z]  = zone_ptcount;
	zone_npts[z]   = 4;
	zone_bottom[z] = mn_z;
	zone_top[z]    = mx_z;

	// A legacy brush trigger declares no destination; SV_ZoneMove falls back to
	// the box floor for these, which is what it always did for everything.
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
};
