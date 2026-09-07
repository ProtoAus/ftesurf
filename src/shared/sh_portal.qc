/*
===========================================================================
  sh_portal.qc -- linked_portal_door, the seamless version.  Patch 205.

  Patch 194 made these doors work as TELEPORTS and said in its own header that
  seamless was a bigger patch.  This is that patch, and the reason it had to
  happen is that the teleport was not merely unpolished: it put you inside the
  wall.  A touch trigger fires when your BOX reaches the volume, which for a
  16-deep trigger and a +-16 player is about 32 units in FRONT of the entry
  plane; the mirror sends +32 to -32, i.e. 32 units BEHIND the exit plane,
  which is solid.  Nothing about that is fixable by adjusting the number -- a
  crossing has to be measured at the plane, and only the engine's mover knows
  where the plane was crossed.

  So the doors become SOLID_PORTAL and the engine does the crossing:

    * pmovetst.c's PM_PortalCSG carves the world behind the aperture out of
      every trace, which is what lets you walk through a wall that is still
      there for everything else,
    * pmove.c's PM_PlayerTracePortals follows the crossing, re-traces from the
      far side and only commits if the landing is valid,
    * and both of them call back into THIS FILE through .camera_transform to
      ask "where does this point/direction come out?".

  WHAT THE CONTRACT IS.  camera_transform has three callers and they all agree
  on a shape that is easy to misread:

      self          the portal being crossed
      PARM0         a POINT to transform
      PARM1         angles, informational
      v_forward     )
      v_right       ) three DIRECTIONS to rotate, in place
      v_up          )
      return        the transformed point

  pmove.c:106-114 calls it once with (origin, velocity, move-remainder,
  gravitydir) and again with (origin, and the three rows of the view basis);
  pr_csqc.c:8787-8798 calls it with (vieworg, and the three rows of the view
  basis).  "Transform the point, rotate the three vectors" is correct for all
  three, which is why there is one function here rather than three.

  WHY THE BASIS IS CACHED AT SPAWN.  makevectors WRITES v_forward/v_right/
  v_up -- the very globals the contract passes data in.  Calling it inside the
  transform would destroy the caller's input before it had been read.  The six
  basis vectors and the exit origin are therefore worked out once, at link
  time, and the transform touches no entity but self.  (Which also means these
  doors must not move at runtime.  None in the library does; Source's
  Enable/Disable inputs are a separate matter and are not implemented.)

  THE ROTATION is the ordinary portal one: express the offset in the entry
  door's basis, negate the forward and right components, read it back out in
  the exit door's basis.  Negating two of three axes is a half turn about up,
  not a reflection, so nothing comes out mirrored.  Forward flips because you
  approach the entry from its front and must leave the exit through its front:
  a point at depth +d in front of A becomes depth +d in front of B once the
  exit's own forward is accounted for.

  PITCHED DOORS ARE OUT OF SCOPE, and the limitation is specific rather than
  vague.  109 of the library's 443 doors carry a nonzero pitch (mostly +-90 --
  portals in floors and ceilings).  The rotation above handles them
  geometrically, but pmove.c:110-139 passes pmove.gravitydir through as v_up
  and then applies a 200 u/s minimum-speed clamp when the transformed
  gravitydir has turned more than 45 degrees.  For a pure-yaw pair the
  gravitydir is unchanged and the clamp correctly stays off; for a floor
  portal it fires.  Half gravity is also applied before and after the move
  (pm_source.c), which a yaw rotation preserves exactly and a pitch does not.
  surf_kitsune's eighteen doors are all pure yaw, which is what this patch is
  for.  A pitched one will move you and will not be smooth.
===========================================================================
*/

// The aperture is a plane, so the collision box wants to be as close to one as
// a box can get.  This is not cosmetic: the engine stops the near-side trace
// at the box's face and PM_PortalTransform mirrors THAT point, so a thick box
// puts you that far behind the exit plane -- and PM_PlayerTracePortals then
// refuses the crossing if the landing is still inside the exit's own box
// (pmovetst.c's PM_TestPlayerPosition rejects a position inside a portal).
// The crossing therefore needs a tick's forward movement to exceed twice this
// number: at 0.25 that is half a unit, i.e. about 33 u/s, so a ducked walk
// goes through and only a deliberate crawl does not.  It cannot be zero --
// AddEntityToPmove drops an entity with no size, and a zero-thickness box hull
// encloses nothing.
#define LPD_HALFDEPTH 0.25

// Where the recursed view samples PVS from: the exit doorway's own centre, a
// short step into the room it opens into.  It must not be the transformed EYE,
// which by construction sits just BEHIND the exit plane -- inside the wall the
// door is set into -- and would sample an empty visibility set and hand back a
// black portal.
#define LPD_PVSNUDGE 8

/*
  How far in FRONT of the exit plane a crossing comes out, and the difference
  between a portal that works and one that stops you dead in the doorway.

  The mirror is exact: a player stopped `t` in front of the entry plane arrives
  `t` BEHIND the exit plane.  t is small -- the near face of the aperture box
  above, or PM_PortalCSG's own 1/32 -- but it is not zero, and behind the exit
  plane is inside the wall the exit door is set into.

  PM_PortalCSG's back plane (pmovetst.c, planes[1]) is what says whether a
  position inside that wall is nevertheless legal, and it allows exactly 4/32 =
  0.125 units.  At LPD_HALFDEPTH 0.25 the arrival is 0.3 behind: rejected by
  0.175 of a unit.  PM_PlayerTracePortals then refuses the whole crossing,
  PMSrc_TryPlayerMove sees a bump that made no progress and deletes the
  player's velocity, and a surfer arriving at 1200 u/s stops flat against the
  doorway.  That is precisely what the first run of this patch did, and the
  measurement is in ENGINE_PATCHES: y went to -15351.7 against a portal plane
  at -15352 and then never moved again.

  One unit forward puts the arrival in front of the plane instead of behind it,
  with margin against the 1/8 grid PM_PortalTransform rounds to.  It also
  removes a second problem for free: PM_PlayerTracePortals validates the
  landing with PM_TestPlayerPosition, which rejects a position inside a
  portal's own box, so without the nudge a crossing needed enough leftover
  movement in the tick to clear that box -- and a slow walk did not have it.

  Only the returned POINT moves.  Velocities and the three direction vectors
  are rotations and must not be translated; the render camera moves by the same
  unit, which at any distance is less than a pixel.
*/
#define LPD_EXITNUDGE 1

.entity lpd_dst;                    // the partner, for setup and debug only
.vector lpd_fa, lpd_ra, lpd_ua;     // entry basis, cached at link time
.vector lpd_fb, lpd_rb, lpd_ub;     // exit basis
.vector lpd_ob;                     // exit origin
.float  lpd_hw, lpd_hh;             // half width, half height
.float  lpd_ok;                     // linked and usable

/*
  The world-axis extent of an oriented rectangle of hw x hh with a little
  depth: the standard sum of |axis component| x half-extent.  Exact for the
  427 doors at axis-aligned yaws and conservative for the sixteen that are
  not.  setsize wants an AABB and QuakeC entities do not have oriented ones,
  so this is the same compromise PM_PortalCSG and PM_PlayerTrace make on the
  engine side -- stated in all three places rather than assumed once.
*/
vector(vector f, vector r, vector u, float hw, float hh) FS_PortalExtent =
{
	local vector e;
	e_x = fabs(r_x)*hw + fabs(u_x)*hh + fabs(f_x)*LPD_HALFDEPTH;
	e_y = fabs(r_y)*hw + fabs(u_y)*hh + fabs(f_y)*LPD_HALFDEPTH;
	e_z = fabs(r_z)*hw + fabs(u_z)*hh + fabs(f_z)*LPD_HALFDEPTH;
	return e;
};

/*
  Rotate a direction from the entry door's frame into the exit door's.
  Also does the whole job for a POINT, via FS_PortalWarp below, because a
  point warp is this rotation applied to the offset from the entry origin.
*/
vector(entity e, vector d) FS_PortalRotate =
{
	return (0 - (d * e.lpd_fa)) * e.lpd_fb
	     + (0 - (d * e.lpd_ra)) * e.lpd_rb
	     +      (d * e.lpd_ua)  * e.lpd_ub;
};

vector(entity e, vector p) FS_PortalWarp =
{
	return e.lpd_ob + FS_PortalRotate(e, p - e.origin)
	     + e.lpd_fb * LPD_EXITNUDGE;
};

/*
  Cache the pair's geometry.  Called once per door, after every entity in the
  map exists -- spawn order is map order and a door's partner is as likely to
  come after it as before.  Returns FALSE for a pair we cannot use, and the
  caller then leaves the door SOLID_NOT: a SOLID_PORTAL whose camera_transform
  is 0 makes PR_ExecuteProgram fault, so "half set up" is not an option.
*/
float(entity door, entity dst) FS_PortalSetup =
{
	if (!dst || dst == door)
		return FALSE;

	makevectors(door.angles);
	door.lpd_fa = v_forward;
	door.lpd_ra = v_right;
	door.lpd_ua = v_up;

	makevectors(dst.angles);
	door.lpd_fb = v_forward;
	door.lpd_rb = v_right;
	door.lpd_ub = v_up;

	door.lpd_ob  = dst.origin;
	door.lpd_dst = dst;
	door.lpd_ok  = TRUE;
	return TRUE;
};

/*
  .camera_transform.  See the contract in the header.  The three rotations are
  computed into locals before any of them is written back, so the function
  reads its own inputs rather than the half-updated globals.
*/
vector(vector org, vector ang) FS_PortalTransform =
{
	local vector f, r, u;

	/*
	  A door that never linked.  Identity, so a caller that reaches us anyway
	  gets a portal that does nothing instead of a player thrown to the origin.

	  Patch 207 makes it SAY SO.  Returning the point unchanged and leaving
	  v_forward/v_right/v_up alone is a total no-op crossing -- the player walks
	  into the doorway, the engine dutifully transforms them to exactly where
	  they already were, and the symptom is "the portal does nothing at all"
	  with no evidence anywhere that a portal was even involved.  That is the
	  same class of silent failure as the refused carve in Patch 206, and it
	  gets the same treatment.
	*/
	if (!self.lpd_ok)
	{
		dprint("portal: crossing a door that never linked -- no-op\n");
		return org;
	}

	f = FS_PortalRotate(self, v_forward);
	r = FS_PortalRotate(self, v_right);
	u = FS_PortalRotate(self, v_up);

	v_forward = f;
	v_right   = r;
	v_up      = u;

	return FS_PortalWarp(self, org);
};
