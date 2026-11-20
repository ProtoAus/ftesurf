/*
===========================================================================
  Patch 1655: GoldSrc (BSP v30) map entities -- ladders, liquids, doors,
  buttons, trains and the target/targetname chain.

  Reached only through the GS_Map() hooks in sv_entities.qc, so a Source map
  runs none of it.  Behaviour follows the Half-Life SDK's dlls (subs, doors,
  buttons, plats, triggers, bmodels, maprules); the file and function each
  part copies is named where it matters.  Sounds, damage and monsters are not
  modelled.
===========================================================================
*/

#define GS_K_LADDER         1
#define GS_K_LIQUID         2
#define GS_K_WALLTOGGLE     3
#define GS_K_DOOR           4
#define GS_K_ROTDOOR        5
#define GS_K_BUTTON         6
#define GS_K_BTARGET        7
#define GS_K_TRAIN          8
#define GS_K_BREAKABLE      9
#define GS_K_MULTIPLE       10
#define GS_K_PUSH           11
#define GS_K_TELEPORT       12
#define GS_K_MANAGER        13
#define GS_K_RELAY          14
#define GS_K_AUTO           15
#define GS_K_MULTISOURCE    16
#define GS_K_CHANGETARGET   17
#define GS_K_ENVGLOBAL      18
#define GS_K_COUNTER        19
#define GS_K_COUNTERSET     20

// USE_TYPE, cbase.h
#define GS_OFF      0
#define GS_ON       1
#define GS_SET      2
#define GS_TOGGLE   3

// spawnflags (doors.h, buttons.cpp, plats.cpp, func_break.h)
#define GS_SF_NOTINDM           2048    // the engine frees these in multiplayer (SF_NOTINDEATHMATCH)
#define GS_SF_DOOR_STARTOPEN    1
#define GS_SF_DOOR_REVERSE      2       // rotating: backwards
#define GS_SF_DOOR_PASSABLE     8
#define GS_SF_DOOR_ONEWAY       16
#define GS_SF_DOOR_TOGGLE       32      // no auto return
#define GS_SF_DOOR_ROTZ         64
#define GS_SF_DOOR_ROTX         128
#define GS_SF_DOOR_USEONLY      256
#define GS_SF_BUTTON_DONTMOVE   1
#define GS_SF_BUTTON_TOGGLE     32
#define GS_SF_BUTTON_TOUCH      256
#define GS_SF_ROTBUTTON_NOTSOLID 1
#define GS_SF_TRAIN_WAIT        1       // also a path_corner's "wait for retrigger"
#define GS_SF_CORNER_TELEPORT   2
#define GS_SF_CORNER_FIREONCE   4
#define GS_SF_TRAIN_PASSABLE    8
#define GS_SF_BREAK_TRIGGERONLY 1
#define GS_SF_BREAK_TOUCH       2
#define GS_SF_BREAK_PRESSURE    4
#define GS_MAT_UNBREAKABLE      7       // matUnbreakableGlass

.float  gs_dead;            // UTIL_Remove'd: freed next frame, skipped by the chain until then
.float  gs_state;           // a mover's TS_*; a multi_manager's running flag
.float  gs_rot;             // the mover turns (gs_pos1/2 and gs_dest are angles)
.float  gs_wait;
.vector gs_pos1, gs_pos2, gs_dest;
.void() gs_done;            // the move's callback
.entity gs_act;             // m_hActivator
.entity gs_corner;          // a train's current path_corner
.string gs_last;            // ...and the name of the one before it
.string gs_list;            // multi_manager: "name\tdelay\n" by delay; multisource: 6-character edict numbers
.float  gs_n;               // entries in gs_list
.float  gs_idx, gs_t0;      // multi_manager: next entry and the start time
.int    gs_bits;            // multisource: which inputs are on
.float  gs_next;            // trigger_multiple: touches before this time are ignored
.float  gs_init;            // game_counter: the count it resets to

float gs_n_ladder, gs_n_liquid, gs_n_door, gs_n_button, gs_n_train, gs_n_trig, gs_n_logic;
float gs_depth;             // nested GS_FireTargets calls
float gs_mm_delay[16];
float gs_mm_used[16];
string gs_mm_name[16];

void(entity t, entity act, entity caller, float ut, float val) GS_Use;

/*
  ---------------------------------------------------------------------------
  subs.cpp: FireTargets, SUB_UseTargets, UTIL_Remove, the global state table.
  ---------------------------------------------------------------------------
*/

void(entity e) GS_Remove =
{
	if (e.gs_dead)
		return;
	e.gs_dead = TRUE;
	e.targetname = "";
	e.solid = SOLID_NOT;
	e.touch = SUB_Null;
	e.velocity = e.avelocity = '0 0 0';
	if (e.modelindex)
		e.effects = e.effects | EF_NODRAW;
	setorigin(e, e.origin);
	e.think = SUB_Remove;
	e.nextthink = ((e.movetype == MOVETYPE_PUSH) ? e.ltime : time) + 0.01;
};

void(string tn, entity act, entity caller, float ut, float val) GS_FireTargets =
{
	local entity t, nx;

	if (tn == "")
		return;
	if (gs_depth >= 48)
	{
		dprint(sprintf("^3goldsrc: target chain deeper than 48 at '%s' -- dropped\n", tn));
		return;
	}
	gs_depth = gs_depth + 1;
	t = find(world, targetname, tn);
	while (t)
	{
		nx = find(t, targetname, tn);
		if (!t.gs_dead)
			GS_Use(t, act, caller, ut, val);
		t = nx;
	}
	gs_depth = gs_depth - 1;
};

void(entity e, entity act, float ut, float val) GS_UseNow =
{
	local entity k, nx;
	local string kt;

	kt = e.gs_killtarget;
	if (kt != "")
	{
		k = find(world, targetname, kt);
		while (k)
		{
			nx = find(k, targetname, kt);
			GS_Remove(k);
			k = nx;
		}
	}
	GS_FireTargets(e.target, act, e, ut, val);
};

void() GS_DelayThink =
{
	GS_UseNow(self, self.gs_act, self.gs_ut, 0);
	remove(self);
};

// CBaseDelay::SUB_UseTargets.  A delayed fire keeps the use type, drops the value, and keeps the
// activator only when it is a player.
void(entity e, entity act, float ut, float val) GS_UseTargets =
{
	local entity d;

	if (e.target == "" && e.gs_killtarget == "")
		return;
	if (e.gs_delay)
	{
		d = spawn();
		d.classname = "gs_delay";
		d.target = e.target;
		d.gs_killtarget = e.gs_killtarget;
		d.gs_ut = ut;
		d.gs_act = (act.classname == "player") ? act : world;
		d.think = GS_DelayThink;
		d.nextthink = time + e.gs_delay;
		return;
	}
	GS_UseNow(e, act, ut, val);
};

float(float ut, float cur) GS_ShouldToggle =
{
	if (ut != GS_TOGGLE && ut != GS_SET)
	{
		if (cur && ut == GS_ON) return FALSE;
		if (!cur && ut == GS_OFF) return FALSE;
	}
	return TRUE;
};

// gGlobalState: one "gs_global" edict a name, gone with the map (a `map` load resets the game's too).
entity(string n) GS_GlobalFind =
{
	local entity g;

	for (g = find(world, classname, "gs_global"); g; g = find(g, classname, "gs_global"))
		if (!strcmp(g.netname, n))
			return g;
	return world;
};

float(string n) GS_GlobalGet =
{
	local entity g;

	g = GS_GlobalFind(n);
	return g ? g.gs_state : 0;      // GLOBAL_OFF when it is not in the table
};

void(string n, float v) GS_GlobalSet =
{
	local entity g;

	g = GS_GlobalFind(n);
	if (!g)
	{
		g = spawn();
		g.classname = "gs_global";
		g.netname = n;
	}
	g.gs_state = v;
};

// CMultiSource::IsTriggered: every input on, and its global state (if it names one) on.
float(entity ms) GS_MultiSourceOn =
{
	local int all;

	all = (ms.gs_n >= 32) ? -1i : (((int)1 << (int)ms.gs_n) - 1i);
	if (ms.gs_bits != all)
		return FALSE;
	if (ms.gs_gstate != "")
	if (GS_GlobalGet(ms.gs_gstate) != 1)
		return FALSE;
	return TRUE;
};

// UTIL_IsMasterTriggered: only a multisource can refuse.
float(string m) GS_MasterOn =
{
	local entity e;

	if (m == "")
		return TRUE;
	e = find(world, targetname, m);
	if (e)
	if (e.gs_kind == GS_K_MULTISOURCE)
		return GS_MultiSourceOn(e);
	return TRUE;
};

// SetMovedir's two specials, as angles makevectors reads: "0 -1 0" is up, "0 -2 0" down.
vector(vector a) GS_DirAngles =
{
	if (a == '0 -1 0') return '-90 0 0';
	if (a == '0 -2 0') return '90 0 0';
	return a;
};

// SetMovedir for a mover: the unit direction, without the cosine dust of a right angle (a door
// facing "90 0 0" would otherwise drift a few millionths sideways).
vector(vector a) GS_MoveDir =
{
	local vector d;

	makevectors(GS_DirAngles(a));
	d = v_forward;
	if (fabs(d_x) < 0.0001) d_x = 0;
	if (fabs(d_y) < 0.0001) d_y = 0;
	if (fabs(d_z) < 0.0001) d_z = 0;
	return normalize(d);
};

// A message with no titles.txt entry draws with the HUD's built-in parameters (hud message.cpp).
void(entity t) GS_MessageInit =
{
	if (t.message == "")
		return;
	t.channel = 4;
	t.vbsp_gt_x = -1;
	t.vbsp_gt_y = 0.7;
	t.vbsp_gt_fx = 2;
	t.color = '100 100 100';
	t.color2 = '240 110 0';
	t.fadein = 0.01;
	t.fadeout = 1.5;
	t.holdtime = 5;
	t.fxtime = 0.25;
};

/*
  ---------------------------------------------------------------------------
  Contents volumes.  A GoldSrc brush entity that is not solid takes its
  contents from "skin" (the engine's SV_LinkContents; a ladder is -16).  Here
  that is SOLID_BSP with the skin kept: sv_user.c AddEntityToPmove and
  cl_ents.c CL_SetSolidEntities both turn it into a non-blocking physent with
  that contents mask, so the server's mover and the client's prediction agree.
  ---------------------------------------------------------------------------
*/
void(float s) GS_SpawnContents =
{
	setmodel(self, self.model);
	self.angles = '0 0 0';
	self.movetype = MOVETYPE_NONE;
	self.solid = SOLID_BSP;
	self.skin = s;
	if (s == CONTENT_LADDER)
	{
		self.effects = self.effects | EF_NODRAW;    // CLadder: renderamt 0
		self.gs_kind = GS_K_LADDER;
		gs_n_ladder = gs_n_ladder + 1;
	}
	else
	{
		self.gs_kind = GS_K_LIQUID;
		gs_n_liquid = gs_n_liquid + 1;
		vbsp_water_n = vbsp_water_n + 1;
	}
};

// 0 when the skin is not a contents this game predicts.  The six currents (-9..-14) are water:
// the client's physent switch has no case for them and would predict a wall.
float(float s) GS_ContentsSkin =
{
	if (s == CONTENT_WATER || s == -4 || s == -5 || s == CONTENT_LADDER)
		return s;
	if (s <= -9 && s >= -14)
		return CONTENT_WATER;
	return 0;
};

/*
  ---------------------------------------------------------------------------
  CBaseToggle::LinearMove / AngularMove.  MOVETYPE_PUSH thinks on .ltime.
  ---------------------------------------------------------------------------
*/
void() GS_MoveDone;

void(entity e, vector dest, float spd, void() done) GS_Move =
{
	local vector d;
	local float t;
	local entity o;

	e.gs_dest = dest;
	e.gs_done = done;
	d = dest - (e.gs_rot ? e.angles : e.origin);
	if (d == '0 0 0' || spd <= 0)
	{
		o = self; self = e; GS_MoveDone(); self = o;
		return;
	}
	t = vlen(d) / spd;
	e.think = GS_MoveDone;
	e.nextthink = e.ltime + t;
	if (e.gs_rot)
		e.avelocity = d * (1 / t);
	else
		e.velocity = d * (1 / t);
};

void() GS_MoveDone =
{
	local void() fn;

	if (self.gs_rot)
	{
		self.angles = self.gs_dest;
		self.avelocity = '0 0 0';
		setorigin(self, self.origin);
	}
	else
	{
		if (vlen(self.gs_dest - self.origin) > 0.03125)
		{
			GS_Move(self, self.gs_dest, 100, self.gs_done);    // LinearMoveDone's retry
			return;
		}
		self.velocity = '0 0 0';
		setorigin(self, self.gs_dest);
	}
	self.nextthink = -1;
	fn = self.gs_done;
	if (fn)
		fn();
};

// CBaseToggle::AxisDir, in angle space: yaw unless a flag picks roll or pitch.
vector() GS_AxisDir =
{
	local vector d;

	if (self.spawnflags & GS_SF_DOOR_ROTZ) d = '0 0 1';
	else if (self.spawnflags & GS_SF_DOOR_ROTX) d = '1 0 0';
	else d = '0 1 0';
	if (self.spawnflags & GS_SF_DOOR_REVERSE) d = d * -1;
	return d;
};

// pos2 of a door or button: along movedir by the brush's own extent less the lip.  setmodel's
// bounds carry the loader's one-unit spread each side (gl_model.c), as the game's do: hence -2.
vector(vector md, float thelip) GS_Travel =
{
	local float d;

	d = fabs(md_x * (self.size_x - 2)) + fabs(md_y * (self.size_y - 2)) + fabs(md_z * (self.size_z - 2)) - thelip;
	return self.origin + md * d;
};

/*
  ---------------------------------------------------------------------------
  doors.cpp: func_door, func_door_rotating.
  ---------------------------------------------------------------------------
*/
void() GS_DoorHitTop;
void() GS_DoorHitBottom;
void() GS_DoorTouch;

void() GS_DoorGoUp =
{
	local float sign;
	local vector v, f;

	self.gs_state = TS_GOING_UP;
	if (self.gs_kind != GS_K_ROTDOOR)
	{
		GS_Move(self, self.gs_pos2, self.speed, GS_DoorHitTop);
		return;
	}
	// a yaw door swings away from whoever opened it unless it is one-way
	sign = 1;
	if (self.gs_act)
	if (!(self.spawnflags & GS_SF_DOOR_ONEWAY))
	if (self.movedir_y)
	{
		v = self.gs_act.origin - self.origin;
		makevectors(self.gs_act.angles);
		f = (self.gs_act.origin + v_forward * 10) - self.origin;
		if (v_x * f_y - v_y * f_x < 0)
			sign = -1;
	}
	GS_Move(self, self.gs_pos2 * sign, self.speed, GS_DoorHitTop);
};

void() GS_DoorGoDown =
{
	self.gs_state = TS_GOING_DOWN;
	GS_Move(self, self.gs_pos1, self.speed, GS_DoorHitBottom);
};

void() GS_DoorHitTop =
{
	self.gs_state = TS_AT_TOP;
	if (self.spawnflags & GS_SF_DOOR_TOGGLE)
	{
		if (!(self.spawnflags & GS_SF_DOOR_USEONLY))
			self.touch = GS_DoorTouch;
	}
	else
	{
		// wait -1 (or any negative) never comes due: the door stays open
		self.think = GS_DoorGoDown;
		self.nextthink = (self.gs_wait < 0) ? -1 : self.ltime + self.gs_wait;
	}
	// netname is the close target; a start-open door's "top" is its closed end
	if (self.netname != "")
	if (self.spawnflags & GS_SF_DOOR_STARTOPEN)
		GS_FireTargets(self.netname, self.gs_act, self, GS_TOGGLE, 0);
	GS_UseTargets(self, self.gs_act, GS_TOGGLE, 0);
};

void() GS_DoorHitBottom =
{
	self.gs_state = TS_AT_BOTTOM;
	self.touch = (self.spawnflags & GS_SF_DOOR_USEONLY) ? SUB_Null : GS_DoorTouch;
	GS_UseTargets(self, self.gs_act, GS_TOGGLE, 0);
	if (self.netname != "")
	if (!(self.spawnflags & GS_SF_DOOR_STARTOPEN))
		GS_FireTargets(self.netname, self.gs_act, self, GS_TOGGLE, 0);
};

float() GS_DoorActivate =
{
	if (!GS_MasterOn(self.gs_master))
		return FALSE;
	if ((self.spawnflags & GS_SF_DOOR_TOGGLE) && self.gs_state == TS_AT_TOP)
		GS_DoorGoDown();
	else
		GS_DoorGoUp();
	return TRUE;
};

// A door something targets opens only for that; the rest open for a player's touch.
void() GS_DoorTouch =
{
	if (other.classname != "player")
		return;
	if (self.targetname != "")
		return;
	self.gs_act = other;
	if (GS_DoorActivate())
		self.touch = SUB_Null;      // until the cycle is done
};

// CBaseDoor::Blocked: a door that comes back by itself reverses; one that never does keeps pushing.
void() GS_DoorBlocked =
{
	if (self.gs_wait < 0)
		return;
	if (self.gs_state == TS_GOING_DOWN)
		GS_DoorGoUp();
	else if (self.gs_state == TS_GOING_UP)
		GS_DoorGoDown();
};

void(entity t, entity act) GS_DoorUse =
{
	local entity o;

	if (t.gs_state != TS_AT_BOTTOM)
	if (!((t.spawnflags & GS_SF_DOOR_TOGGLE) && t.gs_state == TS_AT_TOP))
		return;
	t.gs_act = act;
	o = self; self = t; GS_DoorActivate(); self = o;
};

void(float rot) GS_SpawnDoor =
{
	local vector md, sw;

	setmodel(self, self.model);
	self.skin = 0;
	self.movetype = MOVETYPE_PUSH;
	self.solid = (self.spawnflags & GS_SF_DOOR_PASSABLE) ? SOLID_NOT : SOLID_BSP;
	if (!self.speed)
		self.speed = 100;
	self.gs_wait = self.wait;
	self.gs_rot = rot;
	if (rot)
	{
		self.movedir = GS_AxisDir();
		self.gs_pos1 = self.angles;
		self.gs_pos2 = self.angles + self.movedir * self.distance;
		self.gs_kind = GS_K_ROTDOOR;
	}
	else
	{
		md = GS_MoveDir(self.angles);
		self.angles = '0 0 0';
		self.movedir = md;
		self.gs_pos1 = self.origin;
		self.gs_pos2 = GS_Travel(md, SV_Key2(self.lip, self.Lip));
		self.gs_kind = GS_K_DOOR;
	}
	if (self.spawnflags & GS_SF_DOOR_STARTOPEN)
	{
		sw = self.gs_pos2;
		self.gs_pos2 = self.gs_pos1;
		self.gs_pos1 = sw;
		if (rot)
		{
			self.angles = sw;
			self.movedir = self.movedir * -1;
		}
		else
			setorigin(self, sw);
	}
	setorigin(self, self.origin);
	self.gs_state = TS_AT_BOTTOM;
	self.touch = (self.spawnflags & GS_SF_DOOR_USEONLY) ? SUB_Null : GS_DoorTouch;
	self.blocked = GS_DoorBlocked;
	gs_n_door = gs_n_door + 1;
};

/*
  ---------------------------------------------------------------------------
  buttons.cpp: func_button, func_rot_button, button_target.
  ---------------------------------------------------------------------------
*/
void() GS_ButtonTouch;
void() GS_ButtonBackHome;

void() GS_ButtonReturn =
{
	self.gs_state = TS_GOING_DOWN;
	GS_Move(self, self.gs_pos1, self.speed, GS_ButtonBackHome);
	self.frame = 0;
};

// TriggerAndWait: where a pressed button fires its target.
void() GS_ButtonTrigger =
{
	if (!GS_MasterOn(self.gs_master))
		return;
	self.gs_state = TS_AT_TOP;
	if (self.gs_wait == -1 || (self.spawnflags & GS_SF_BUTTON_TOGGLE))
		self.touch = (self.spawnflags & GS_SF_BUTTON_TOUCH) ? GS_ButtonTouch : SUB_Null;
	else
	{
		self.think = GS_ButtonReturn;
		self.nextthink = self.ltime + self.gs_wait;
	}
	self.frame = 1;
	GS_UseTargets(self, self.gs_act, GS_TOGGLE, 0);
};

void() GS_ButtonBackHome =
{
	local entity t, nx;

	self.gs_state = TS_AT_BOTTOM;
	if (self.spawnflags & GS_SF_BUTTON_TOGGLE)
		GS_UseTargets(self, self.gs_act, GS_TOGGLE, 0);
	// a multisource it targets hears the release as well
	if (self.target != "")
	{
		t = find(world, targetname, self.target);
		while (t)
		{
			nx = find(t, targetname, self.target);
			if (t.gs_kind == GS_K_MULTISOURCE)
			if (!t.gs_dead)
				GS_Use(t, self.gs_act, self, GS_TOGGLE, 0);
			t = nx;
		}
	}
	self.touch = (self.spawnflags & GS_SF_BUTTON_TOUCH) ? GS_ButtonTouch : SUB_Null;
};

void() GS_ButtonActivate =
{
	if (!GS_MasterOn(self.gs_master))
		return;
	self.gs_state = TS_GOING_UP;
	GS_Move(self, self.gs_pos2, self.speed, GS_ButtonTrigger);
};

void(entity t, entity act) GS_ButtonUse =
{
	local entity o;

	if (t.spawnflags & GS_SF_BUTTON_TOUCH)
		return;                     // a touch button has no use function
	if (t.gs_state == TS_GOING_UP || t.gs_state == TS_GOING_DOWN)
		return;
	t.gs_act = act;
	o = self;
	self = t;
	if (t.gs_state == TS_AT_TOP)
	{
		if (t.gs_wait != -1)
		if (t.spawnflags & GS_SF_BUTTON_TOGGLE)
			GS_ButtonReturn();
	}
	else
		GS_ButtonActivate();
	self = o;
};

void() GS_ButtonTouch =
{
	local float stay;

	if (other.classname != "player")
		return;
	stay = (self.gs_wait == -1);
	if (self.gs_state == TS_GOING_UP || self.gs_state == TS_GOING_DOWN)
		return;
	if (self.gs_state == TS_AT_TOP)
	if (stay || !(self.spawnflags & GS_SF_BUTTON_TOGGLE))
		return;
	self.gs_act = other;
	if (!GS_MasterOn(self.gs_master))
		return;
	self.touch = SUB_Null;
	if (self.gs_state == TS_AT_TOP)
	{
		GS_UseTargets(self, self.gs_act, GS_TOGGLE, 0);
		GS_ButtonReturn();
	}
	else
		GS_ButtonActivate();
};

void(float rot) GS_SpawnButton =
{
	local vector md;

	setmodel(self, self.model);
	self.skin = 0;
	self.movetype = MOVETYPE_PUSH;
	self.solid = SOLID_BSP;
	if (!self.speed)
		self.speed = 40;
	self.gs_wait = self.wait ? self.wait : 1;
	self.gs_rot = rot;
	if (rot)
	{
		if (self.spawnflags & GS_SF_ROTBUTTON_NOTSOLID)
			self.solid = SOLID_NOT;
		self.movedir = GS_AxisDir();
		self.gs_pos1 = self.angles;
		self.gs_pos2 = self.angles + self.movedir * self.distance;
	}
	else
	{
		md = GS_MoveDir(self.angles);
		self.angles = '0 0 0';
		self.movedir = md;
		self.gs_pos1 = self.origin;
		self.gs_pos2 = GS_Travel(md, SV_Key2(self.lip, self.Lip) ? SV_Key2(self.lip, self.Lip) : 4);
		if (vlen(self.gs_pos2 - self.gs_pos1) < 1 || (self.spawnflags & GS_SF_BUTTON_DONTMOVE))
			self.gs_pos2 = self.gs_pos1;
	}
	setorigin(self, self.origin);
	self.gs_state = TS_AT_BOTTOM;
	self.touch = (self.spawnflags & GS_SF_BUTTON_TOUCH) ? GS_ButtonTouch : SUB_Null;
	self.gs_kind = GS_K_BUTTON;
	gs_n_button = gs_n_button + 1;
};

// CButtonTarget: a brush whose frame is its state; each change fires on or off.
void(entity t, entity act, float ut) GS_ButtonTargetUse =
{
	if (!GS_ShouldToggle(ut, t.frame))
		return;
	t.frame = 1 - t.frame;
	GS_UseTargets(t, act, t.frame ? GS_ON : GS_OFF, 0);
};

/*
  ---------------------------------------------------------------------------
  plats.cpp: func_train and its path_corners.
  ---------------------------------------------------------------------------
*/
void() GS_TrainNext;

// The train's box centre rides the corners.
vector(entity tr, entity corner) GS_TrainSpot =
{
	return corner.origin - (tr.mins + tr.maxs) * 0.5;
};

void() GS_TrainWait =
{
	local entity c;

	c = self.gs_corner;
	if (c.message != "")
	{
		GS_FireTargets(c.message, self, self, GS_TOGGLE, 0);
		if (c.spawnflags & GS_SF_CORNER_FIREONCE)
			c.message = "";
	}
	if ((c.spawnflags & GS_SF_TRAIN_WAIT) || (self.spawnflags & GS_SF_TRAIN_WAIT))
	{
		self.spawnflags = self.spawnflags | GS_SF_TRAIN_WAIT;
		self.nextthink = 0;
		return;
	}
	if (self.gs_wait != 0)
	{
		self.think = GS_TrainNext;
		self.nextthink = (self.gs_wait < 0) ? -1 : self.ltime + self.gs_wait;
	}
	else
		GS_TrainNext();
};

void() GS_TrainNext =
{
	local entity c;
	local float hops;

	// A ring of teleport corners with no wait would never return (the game recurses there too).
	for (hops = 0; hops < 64; hops = hops + 1)
	{
		if (self.target == "")
			return;
		c = find(world, targetname, self.target);
		if (!c)
			return;
		self.gs_last = self.target;
		self.target = c.target;
		self.gs_wait = c.wait;
		if (self.gs_corner)
		if (self.gs_corner.speed)
			self.speed = self.gs_corner.speed;
		self.gs_corner = c;
		if (!(c.spawnflags & GS_SF_CORNER_TELEPORT))
		{
			GS_Move(self, GS_TrainSpot(self, c), self.speed, GS_TrainWait);
			return;
		}
		setorigin(self, GS_TrainSpot(self, c));
		// GS_TrainWait, unrolled so a teleport chain is a loop
		if (c.message != "")
		{
			GS_FireTargets(c.message, self, self, GS_TOGGLE, 0);
			if (c.spawnflags & GS_SF_CORNER_FIREONCE)
				c.message = "";
		}
		if ((c.spawnflags & GS_SF_TRAIN_WAIT) || (self.spawnflags & GS_SF_TRAIN_WAIT))
		{
			self.spawnflags = self.spawnflags | GS_SF_TRAIN_WAIT;
			self.nextthink = 0;
			return;
		}
		if (self.gs_wait != 0)
		{
			self.think = GS_TrainNext;
			self.nextthink = (self.gs_wait < 0) ? -1 : self.ltime + self.gs_wait;
			return;
		}
	}
	dprint(sprintf("^3goldsrc: func_train %s stopped in a teleport loop\n", self.targetname));
};

// CFuncTrain::Use: a waiting train moves on; a moving one stops and will retry its last corner.
void(entity t) GS_TrainUse =
{
	local entity o;

	if (t.spawnflags & GS_SF_TRAIN_WAIT)
	{
		t.spawnflags = t.spawnflags - GS_SF_TRAIN_WAIT;
		o = self; self = t; GS_TrainNext(); self = o;
		return;
	}
	t.spawnflags = t.spawnflags | GS_SF_TRAIN_WAIT;
	if (t.gs_corner)
		t.target = t.gs_corner.targetname;
	t.nextthink = 0;
	t.velocity = '0 0 0';
};

// CFuncTrain::Activate: onto the first corner; an unnamed train then starts by itself.
void(entity t) GS_TrainActivate =
{
	local entity c;

	if (t.target == "")
		return;
	c = find(world, targetname, t.target);
	if (!c)
		return;
	t.target = c.target;
	t.gs_corner = c;
	setorigin(t, GS_TrainSpot(t, c));
	if (t.targetname == "")
	{
		t.think = GS_TrainNext;
		t.nextthink = t.ltime + 0.1;
	}
	else
		t.spawnflags = t.spawnflags | GS_SF_TRAIN_WAIT;
};

void() GS_SpawnTrain =
{
	setmodel(self, self.model);
	self.skin = 0;
	self.movetype = MOVETYPE_PUSH;
	self.solid = (self.spawnflags & GS_SF_TRAIN_PASSABLE) ? SOLID_NOT : SOLID_BSP;
	if (!self.speed)
		self.speed = 100;
	self.gs_kind = GS_K_TRAIN;
	gs_n_train = gs_n_train + 1;
};

/*
  ---------------------------------------------------------------------------
  bmodels.cpp, func_break.cpp: func_wall_toggle, func_breakable.
  ---------------------------------------------------------------------------
*/
void(entity t, float ut) GS_WallToggleUse =
{
	local float on;

	on = (t.solid != SOLID_NOT);
	if (!GS_ShouldToggle(ut, on))
		return;
	if (on)
	{
		t.solid = SOLID_NOT;
		t.effects = t.effects | EF_NODRAW;
	}
	else
	{
		t.solid = SOLID_BSP;
		t.effects = t.effects - (t.effects & EF_NODRAW);
		SV_BrushRenderState(t);     // a rendermode that hides it still does
	}
	setorigin(t, t.origin);
};

// CBreakable::Die: targets fire, then the brush goes.  Held on a lobby as a Source break is.
void(entity t, entity act) GS_Break =
{
	if (t.gs_dead || !t.vbsp_brk || !vbsp_mapedit_ok)
		return;
	if (t.gs_mat == GS_MAT_UNBREAKABLE)
		return;
	t.vbsp_brk = 0;
	t.gs_kind = 0;
	GS_UseTargets(t, world, GS_TOGGLE, 0);
	GS_Remove(t);
};

void() GS_BreakDie = { GS_Break(self, self.gs_act); };

// BreakTouch: "touch" breaks when run into at a hundredth of the speed as damage; "pressure" when stood on.
void() GS_BreakTouch =
{
	if (other.classname != "player")
		return;
	if (self.spawnflags & GS_SF_BREAK_TOUCH)
	if (vlen(other.velocity) * 0.01 >= self.health)
	{
		GS_Break(self, other);
		return;
	}
	if (self.spawnflags & GS_SF_BREAK_PRESSURE)
	if (other.absmin_z >= self.absmax_z - 3)
	{
		self.touch = SUB_Null;
		self.gs_act = other;
		self.think = GS_BreakDie;
		self.nextthink = self.ltime + (self.gs_delay ? self.gs_delay : 0.1);
	}
};

/*
  ---------------------------------------------------------------------------
  triggers.cpp: trigger_multiple / trigger_once, and the keys of the two
  triggers whose touch is the shared one (teleport, push).
  ---------------------------------------------------------------------------
*/
void() GS_MultiTouch =
{
	if (other.classname != "player")
		return;
	if (self.gs_next > time)
		return;
	if (!GS_MasterOn(self.gs_master))
		return;
	GS_UseTargets(self, other, GS_TOGGLE, 0);
	if (self.message != "")
		SV_MapTextTo(self, other);
	if (self.gs_wait > 0)
		self.gs_next = time + self.gs_wait;
	else
		GS_Remove(self);
};

void(float once) GS_SpawnMultiple =
{
	self.angles = '0 0 0';
	SV_BindInvisibleBrush();
	self.movetype = MOVETYPE_NONE;
	self.solid = (self.spawnflags & 2) ? SOLID_NOT : SOLID_BSPTRIGGER;     // 2: no clients
	self.gs_wait = once ? -1 : (self.wait ? self.wait : 0.2);
	self.touch = GS_MultiTouch;
	GS_MessageInit(self);
	self.gs_kind = GS_K_MULTIPLE;
	gs_n_trig = gs_n_trig + 1;
};

void() GS_TeleTouch =
{
	if (!GS_MasterOn(self.gs_master))
		return;
	trigger_teleport_touch();
};

// CTriggerTeleport: the destination's angles, and no velocity (the shared touch's VelocityMode 1).
// Of its spawnflags only 2, "no clients", concerns a player.
void() GS_SpawnTeleport =
{
	self.spawnflags = self.spawnflags & 2;
	self.VelocityMode = 1;
	self.velocitymode = 0;
	self.angles = '0 0 0';
	trigger_teleport();
	if (wasfreed(self))
		return;
	if (self.gs_master != "")
		self.touch = GS_TeleTouch;
	self.gs_kind = GS_K_TELEPORT;
	gs_n_trig = gs_n_trig + 1;
};

// CTriggerPush: direction from "angles", 1 is once-only, 2 starts off, and a use toggles it.
void() GS_SpawnPush =
{
	local float sf;

	sf = self.spawnflags;
	self.spawnflags = SF_TRIGGER_ALLOW_CLIENTS | ((sf & 1) ? SF_PUSH_ONCE : 0);
	self.StartDisabled = (sf & 2) ? 1 : 0;
	self.startdisabled = 0;
	self.pushdir = GS_DirAngles(self.angles);
	self.angles = '0 0 0';
	trigger_push();
	if (wasfreed(self))
		return;
	self.gs_kind = GS_K_PUSH;
	gs_n_trig = gs_n_trig + 1;
};

/*
  ---------------------------------------------------------------------------
  The point entities of the chain.
  ---------------------------------------------------------------------------
*/
void() GS_ManagerThink =
{
	local string s, nm;
	local float p, pt, pn, t, i;

	s = self.gs_list;
	t = time - self.gs_t0;
	p = 0;
	for (i = 0; i < self.gs_n; i = i + 1)
	{
		pt = strstrofs(s, "\t", p);
		pn = strstrofs(s, "\n", p);
		if (i >= self.gs_idx)
		{
			if (stof(substring(s, pt + 1, pn - pt - 1)) > t)
			{
				self.nextthink = self.gs_t0 + stof(substring(s, pt + 1, pn - pt - 1));
				return;
			}
			nm = substring(s, p, pt - p);
			self.gs_idx = i + 1;
			GS_FireTargets(nm, self.gs_act, self, GS_TOGGLE, 0);
			if (self.gs_dead)
				return;
		}
		p = pn + 1;
	}
	// every target has fired: a clone goes, the original takes uses again
	if (self.gs_state == 2)
		remove(self);
	else
		self.gs_state = 0;
};

// CMultiManager::ManagerUse.  Uses are ignored while it runs; "multithreaded" (1) runs a copy instead.
void(entity t, entity act) GS_ManagerUse =
{
	local entity m;

	m = t;
	if (t.spawnflags & 1)
	{
		m = spawn();
		m.classname = t.classname;
		m.targetname = t.targetname;
		m.gs_kind = GS_K_MANAGER;
		m.gs_list = t.gs_list;
		m.gs_n = t.gs_n;
		m.gs_state = 2;
	}
	else
	{
		if (t.gs_state)
			return;
		t.gs_state = 1;
	}
	m.gs_act = act;
	m.gs_idx = 0;
	m.gs_t0 = time;
	m.think = GS_ManagerThink;
	m.nextthink = time;
};

// Its targets are every key the game has no member for: here, the ones no QC field took (gs_raw).
void() GS_SpawnManager =
{
	local string raw, k, out;
	local float p, pt, pn, n, i, j, best;

	raw = self.gs_raw;
	n = p = 0;
	while (n < 16)
	{
		pn = strstrofs(raw, "\n", p);
		if (pn < 0)
			break;
		pt = strstrofs(raw, "\t", p);
		k = substring(raw, p, pt - p);
		i = strstrofs(k, "#");          // Hammer's "name#2" for a second fire of one target
		if (i >= 0)
			k = substring(k, 0, i);
		gs_mm_name[n] = k;
		gs_mm_delay[n] = stof(substring(raw, pt + 1, pn - pt - 1));
		gs_mm_used[n] = FALSE;
		n = n + 1;
		p = pn + 1;
	}
	out = "";
	for (i = 0; i < n; i = i + 1)
	{
		best = -1;
		for (j = 0; j < n; j = j + 1)
		{
			if (gs_mm_used[j])
				continue;
			if (best < 0)
				best = j;
			else if (gs_mm_delay[j] < gs_mm_delay[best])
				best = j;
		}
		gs_mm_used[best] = TRUE;
		out = strcat(out, gs_mm_name[best], "\t", sprintf("%.9g", gs_mm_delay[best]), "\n");
	}
	self.gs_list = out;
	self.gs_n = n;
	self.gs_kind = GS_K_MANAGER;
};

float(entity m, string nm) GS_ManagerHasTarget =
{
	local string s;
	local float p, pt, pn, i;

	s = m.gs_list;
	p = 0;
	for (i = 0; i < m.gs_n; i = i + 1)
	{
		pt = strstrofs(s, "\t", p);
		pn = strstrofs(s, "\n", p);
		if (!strcmp(substring(s, p, pt - p), nm))
			return TRUE;
		p = pn + 1;
	}
	return FALSE;
};

// CMultiSource::Use: the caller's input flips; a caller that is not an input flips the last one.
void(entity t, entity act, entity caller) GS_MultiSourceUse =
{
	local float i, n;

	n = num_for_edict(caller);
	for (i = 0; i < t.gs_n; i = i + 1)
		if (stof(substring(t.gs_list, i * 6, 6)) == n)
			break;
	if (i >= t.gs_n)
		i = t.gs_n - 1;
	if (i >= 0)
		t.gs_bits = t.gs_bits ^ ((int)1 << (int)i);
	if (GS_MultiSourceOn(t))
		GS_UseTargets(t, world, (t.gs_gstate != "") ? GS_ON : GS_TOGGLE, 0);
};

// CMultiSource::Register: its inputs are whatever targets it, and any multi_manager that lists it.
void(entity ms) GS_MultiSourceRegister =
{
	local entity e;
	local float take;

	ms.gs_list = "";
	ms.gs_n = 0;
	for (e = nextent(world); e; e = nextent(e))
	{
		if (ms.gs_n >= 32)
			break;
		take = FALSE;
		if (e.target != "")
		if (!strcmp(e.target, ms.targetname))
			take = TRUE;
		if (e.gs_kind == GS_K_MANAGER)
		if (GS_ManagerHasTarget(e, ms.targetname))
			take = TRUE;
		if (!take)
			continue;
		ms.gs_list = strcat(ms.gs_list, sprintf("%6g", num_for_edict(e)));
		ms.gs_n = ms.gs_n + 1;
	}
};

void() GS_AutoThink =
{
	if (self.gs_gstate != "")
	if (GS_GlobalGet(self.gs_gstate) != 1)
		return;
	GS_UseTargets(self, self, self.gs_ut, 0);
	if (self.spawnflags & 1)
		remove(self);
};

void(entity t) GS_EnvGlobalUse =
{
	local float old, nw;

	old = GS_GlobalGet(t.gs_gstate);
	if (t.gs_tmode == 0) nw = 0;
	else if (t.gs_tmode == 1) nw = 1;
	else if (t.gs_tmode == 2) nw = 2;
	else nw = (old == 1) ? 0 : ((old == 0) ? 1 : old);
	GS_GlobalSet(t.gs_gstate, nw);
};

void(entity t, entity act, float ut, float val) GS_CounterUse =
{
	if (!GS_MasterOn(t.gs_master))
		return;
	if (ut == GS_ON || ut == GS_TOGGLE) t.frags = t.frags + 1;
	else if (ut == GS_OFF) t.frags = t.frags - 1;
	else t.frags = floor(val);
	if (t.frags != t.health)
		return;
	GS_UseTargets(t, act, GS_TOGGLE, 0);
	if (t.spawnflags & 1)
		GS_Remove(t);
	if (t.spawnflags & 2)
		t.frags = t.gs_init;
};

/*
  ---------------------------------------------------------------------------
  Use: one entity receiving one fire.
  ---------------------------------------------------------------------------
*/
void(entity t, entity act, entity caller, float ut, float val) GS_Use =
{
	local float k;
	local entity e;

	k = t.gs_kind;
	if (!k)
	{
		// re-created after the lump by the shared code, so they carry no kind
		if (t.classname == "game_text")
			SV_MapText(t, act);
		else if (t.classname == "env_fade")
			SV_MapFade(t, act, FALSE);
		else if (t.classname == "env_shake")
			SV_MapShake(t, t.amplitude);
		return;
	}
	if (k == GS_K_RELAY)
	{
		GS_UseTargets(t, t, t.gs_ut, 0);
		if (t.spawnflags & 1)
			GS_Remove(t);
	}
	else if (k == GS_K_MANAGER)
		GS_ManagerUse(t, act);
	else if (k == GS_K_CHANGETARGET)
	{
		e = find(world, targetname, t.target);
		if (e)
			e.target = t.gs_newtarget;
	}
	else if (k == GS_K_COUNTER)
		GS_CounterUse(t, act, ut, val);
	else if (k == GS_K_COUNTERSET)
	{
		if (!GS_MasterOn(t.gs_master))
			return;
		GS_UseTargets(t, act, GS_SET, t.frags);
		if (t.spawnflags & 1)
			GS_Remove(t);
	}
	else if (k == GS_K_ENVGLOBAL)
		GS_EnvGlobalUse(t);
	else if (k == GS_K_MULTISOURCE)
		GS_MultiSourceUse(t, act, caller);
	else if (k == GS_K_WALLTOGGLE)
		GS_WallToggleUse(t, ut);
	else if (k == GS_K_DOOR || k == GS_K_ROTDOOR)
		GS_DoorUse(t, act);
	else if (k == GS_K_BUTTON)
		GS_ButtonUse(t, act);
	else if (k == GS_K_BTARGET)
		GS_ButtonTargetUse(t, act, ut);
	else if (k == GS_K_TRAIN)
		GS_TrainUse(t);
	else if (k == GS_K_BREAKABLE)
		GS_Break(t, act);
	else if (k == GS_K_PUSH)
		SV_IOEnable(t, SV_Key2(t.StartDisabled, t.startdisabled));     // CBaseTrigger::ToggleUse
};

// The game's shot (SV_ShootFrame) as damage: CBaseButton, CButtonTarget and CBreakable::TakeDamage.
void(entity t, entity att, float dmg) GS_Damage =
{
	local entity o;

	if (t.gs_dead)
		return;
	if (t.gs_kind == GS_K_BTARGET)
	{
		GS_ButtonTargetUse(t, att, GS_TOGGLE);
		return;
	}
	if (t.gs_kind == GS_K_BREAKABLE)
	{
		if (t.spawnflags & GS_SF_BREAK_TRIGGERONLY)
			return;
		t.health = t.health - dmg;
		if (t.health <= 0)
			GS_Break(t, att);
		return;
	}
	// a button with health is shot, not used; it answers as a touch button would
	if (t.gs_kind != GS_K_BUTTON || t.health <= 0)
		return;
	if (t.gs_state == TS_GOING_UP || t.gs_state == TS_GOING_DOWN)
		return;
	if (t.gs_state == TS_AT_TOP)
	if (t.gs_wait == -1 || !(t.spawnflags & GS_SF_BUTTON_TOGGLE))
		return;
	t.touch = SUB_Null;
	t.gs_act = att;
	o = self;
	self = t;
	if (t.gs_state == TS_AT_TOP)
		GS_ButtonReturn();
	else
		GS_ButtonActivate();
	self = o;
};

/*
  CBasePlayer::PlayerUse: the usable entity within 64 units that sits deepest in the view cone
  (dot over 0.7 against the nearest point of its box).  No line of sight is asked for.
  A later patch that times runs off the community KZ buttons hooks here: `best` is a func_button
  whose .target is "counter_start" or "counter_off" and pl is the player.
*/
float(entity e) GS_Usable =
{
	if (e.gs_dead)
		return FALSE;
	if (e.gs_kind == GS_K_BUTTON)
		return !(e.spawnflags & GS_SF_BUTTON_TOUCH) && e.health <= 0;
	if (e.gs_kind == GS_K_BTARGET)
		return (e.spawnflags & 1);
	if (e.gs_kind == GS_K_DOOR || e.gs_kind == GS_K_ROTDOOR)
		return (e.spawnflags & GS_SF_DOOR_USEONLY);
	return FALSE;
};

void(entity pl) GS_PlayerUse =
{
	local entity e, best;
	local vector eye, los, half, d;
	local float dot, bestdot;

	makevectors(pl.v_angle);
	eye = pl.origin + pl.view_ofs;
	best = world;
	bestdot = 0.7;
	for (e = nextent(world); e; e = nextent(e))
	{
		if (!e.gs_kind)
			continue;
		if (!GS_Usable(e))
			continue;
		d_x = max(e.absmin_x - pl.origin_x, 0, pl.origin_x - e.absmax_x);
		d_y = max(e.absmin_y - pl.origin_y, 0, pl.origin_y - e.absmax_y);
		d_z = max(e.absmin_z - pl.origin_z, 0, pl.origin_z - e.absmax_z);
		if (vlen(d) > 64)
			continue;
		los = (e.absmin + e.absmax) * 0.5 - eye;
		half = e.size * 0.5;
		los_x = (los_x > half_x) ? los_x - half_x : ((los_x < -half_x) ? los_x + half_x : 0);
		los_y = (los_y > half_y) ? los_y - half_y : ((los_y < -half_y) ? los_y + half_y : 0);
		los_z = (los_z > half_z) ? los_z - half_z : ((los_z < -half_z) ? los_z + half_z : 0);
		dot = normalize(los) * v_forward;
		if (dot > bestdot)
		{
			best = e;
			bestdot = dot;
		}
	}
	if (best)
		GS_Use(best, pl, pl, GS_SET, 1);
};

/*
  ---------------------------------------------------------------------------
  The hooks.
  ---------------------------------------------------------------------------
*/
float(string key, string value) GS_UnknownKey =
{
	local float v;

	if (value == "")
		return TRUE;
	if (key == "x" || key == "y" || key == "effect")
		return FALSE;               // game_text's, which the shared hook keeps
	if (key == "master")        { self.gs_master = strcat(value); return TRUE; }
	if (key == "killtarget")    { self.gs_killtarget = strcat(value); return TRUE; }
	if (key == "globalstate")   { self.gs_gstate = strcat(value); return TRUE; }
	if (key == "m_iszNewTarget"){ self.gs_newtarget = strcat(value); return TRUE; }
	if (key == "delay")         { self.gs_delay = stof(value); return TRUE; }
	if (key == "dmg")           { self.gs_dmg = stof(value); return TRUE; }
	if (key == "triggermode")   { self.gs_tmode = stof(value); return TRUE; }
	if (key == "initialstate")  { self.gs_istate = stof(value); return TRUE; }
	if (key == "material")      { self.gs_mat = stof(value); return TRUE; }
	if (key == "triggerstate")
	{
		v = stof(value);
		self.gs_ut = (v == 0) ? GS_OFF : ((v == 2) ? GS_TOGGLE : GS_ON);
		return TRUE;
	}
	self.gs_raw = strcat(self.gs_raw, key, "\t", value, "\n");
	return TRUE;
};

float() GS_Spawn =
{
	local string cn;
	local float brush, s;

	cn = self.classname;
	if (cn == "worldspawn")
	{
		gs_n_ladder = gs_n_liquid = gs_n_door = gs_n_button = gs_n_train = gs_n_trig = gs_n_logic = 0;
		gs_depth = 0;
		self.gs_raw = "";
		return FALSE;
	}
	if (self.spawnflags & GS_SF_NOTINDM)
	{
		remove(self);
		return TRUE;
	}
	brush = (substring(self.model, 0, 1) == "*");

	if (!brush)
	{
		if (cn == "multi_manager")              GS_SpawnManager();
		else if (cn == "trigger_relay")         self.gs_kind = GS_K_RELAY;
		else if (cn == "trigger_auto")          self.gs_kind = GS_K_AUTO;
		else if (cn == "multisource")           self.gs_kind = GS_K_MULTISOURCE;
		else if (cn == "trigger_changetarget")  self.gs_kind = GS_K_CHANGETARGET;
		else if (cn == "game_counter_set")      self.gs_kind = GS_K_COUNTERSET;
		else if (cn == "game_counter")
		{
			self.gs_init = self.frags;
			self.gs_kind = GS_K_COUNTER;
		}
		else if (cn == "env_global")
		{
			if (self.gs_gstate == "")
			{
				remove(self);
				return TRUE;
			}
			if (self.spawnflags & 1)
			if (!GS_GlobalFind(self.gs_gstate))
				GS_GlobalSet(self.gs_gstate, self.gs_istate);
			self.gs_kind = GS_K_ENVGLOBAL;
		}
		else if (cn == "path_corner")
		{
			// kept for func_train's find(); it does nothing by itself
			self.solid = SOLID_NOT;
			self.gs_raw = "";
			return TRUE;
		}
		else
		{
			self.gs_raw = "";
			return FALSE;
		}
		self.solid = SOLID_NOT;
		self.movetype = MOVETYPE_NONE;
		self.gs_raw = "";
		gs_n_logic = gs_n_logic + 1;
		return TRUE;
	}

	self.gs_raw = "";
	s = GS_ContentsSkin(self.skin);
	if (cn == "func_ladder")
		GS_SpawnContents(CONTENT_LADDER);
	else if (cn == "func_water" || cn == "func_illusionary" ||
	         ((cn == "func_door" || cn == "func_door_rotating") && self.skin != 0))
	{
		// CBaseDoor::Spawn: a door with a skin is "special contents", never solid
		if (s)
			GS_SpawnContents(s);
		else if (cn == "func_illusionary")
		{
			if (self.skin != -1)
				self.skin = 0;      // a skin the client has no case for would predict solid
			return FALSE;           // the shared non-solid list
		}
		else
		{
			setmodel(self, self.model);
			self.skin = 0;
			self.angles = '0 0 0';
			self.movetype = MOVETYPE_NONE;
			self.solid = SOLID_NOT;
		}
	}
	else if (cn == "func_door")             GS_SpawnDoor(FALSE);
	else if (cn == "func_door_rotating")    GS_SpawnDoor(TRUE);
	else if (cn == "func_button")           GS_SpawnButton(FALSE);
	else if (cn == "func_rot_button")       GS_SpawnButton(TRUE);
	else if (cn == "func_train")            GS_SpawnTrain();
	else if (cn == "trigger_multiple")      GS_SpawnMultiple(FALSE);
	else if (cn == "trigger_once")          GS_SpawnMultiple(TRUE);
	else if (cn == "trigger_teleport")      GS_SpawnTeleport();
	else if (cn == "trigger_push")          GS_SpawnPush();
	else if (cn == "button_target")
	{
		self.skin = 0;
		func_wall();
		self.frame = (self.spawnflags & 2) ? 1 : 0;
		self.gs_kind = GS_K_BTARGET;
	}
	else if (cn == "func_wall_toggle")
	{
		self.skin = 0;
		func_wall_toggle();
		self.gs_kind = GS_K_WALLTOGGLE;
	}
	else if (cn == "func_breakable")
	{
		self.skin = 0;
		SV_SpawnBreakable();
		self.gs_kind = GS_K_BREAKABLE;
		if (!(self.spawnflags & GS_SF_BREAK_TRIGGERONLY))
		if (self.spawnflags & (GS_SF_BREAK_TOUCH | GS_SF_BREAK_PRESSURE))
			self.touch = GS_BreakTouch;
	}
	else if (cn == "func_conveyor")
	{
		// CFuncConveyor: direction from "angles"; the shared spawn reads Source's movedir
		self.skin = 0;
		self.movedir = GS_DirAngles(self.angles);
		func_conveyor();
	}
	else if (cn == "func_friction" || cn == "func_monsterclip")
		remove(self);               // a friction trigger and a monsters-only clip: nothing a player meets
	else
	{
		// the shared spawn or catch-all; a solid brush's skin is not contents in this game
		self.skin = 0;
		return FALSE;
	}
	return TRUE;
};

/*
  ---------------------------------------------------------------------------
  The test driver, in check builds only (fteqcc -DGS_TEST; the shipped progs
  have none of it).  `+set gs_test <file>` names a script in the gamedir (data/
  first): one command a line, run from the first frame of a GoldSrc map.  It
  moves a bot client through the server's own command path (SV_RunCmd) or the
  mover alone (`phys`), so an arm needs no game client.  Prints "GSTEST ...".
  ---------------------------------------------------------------------------
*/
#ifdef GS_TEST
void() ClientConnect;
void() PutClientInServer;
__uint(vector pos, optional float worldonly) pointcontentsmask = #0;

entity gs_bot;
filestream gs_tf;
float gs_tsleep, gs_tblank;

void(entity e) GS_TestEnt =
{
	print(sprintf("GSTEST ent #%g %s '%s' %s org %v ang %v", num_for_edict(e), e.classname, e.targetname,
	              e.model, e.origin, e.angles));
	print(sprintf(" vel %v avel %v absmin %v absmax %v\n", e.velocity, e.avelocity, e.absmin, e.absmax));
	print(sprintf("GSTEST     solid %g mt %g fx %g skin %g alpha %g frame %g flags %g\n", e.solid, e.movetype,
	              e.effects, e.skin, e.alpha, e.frame, e.spawnflags));
	print(sprintf("GSTEST     kind %g state %g wait %g frags %g health %g target '%s' think-in %g\n",
	              e.gs_kind, e.gs_state, e.gs_wait, e.frags, e.health, e.target,
	              e.nextthink - ((e.movetype == MOVETYPE_PUSH) ? e.ltime : time)));
};

void(float n, float ms) GS_TestPhys =
{
	local float i;
	local entity o;

	o = self;
	self = gs_bot;
	for (i = 0; i < n; i = i + 1)
	{
		input_timelength = ms * 0.001;
		input_angles = gs_bot.v_angle;
		input_movevalues = gs_bot.movement;
		input_buttons = gs_bot.button2 ? 2 : 0;
		input_impulse = 0;
		runstandardplayerphysics(gs_bot);
	}
	self = o;
};

void(vector p, float pitch, float yaw) GS_TestPlace =
{
	setorigin(gs_bot, p);
	gs_bot.velocity = '0 0 0';
	gs_bot.v_angle = [pitch, yaw, 0];
	gs_bot.angles = [0, yaw, 0];
	gs_bot.flags = gs_bot.flags - (gs_bot.flags & FL_ONGROUND);
};

// Every func_ladder: stand where the hull meets the brush and nothing else (a grid of spots on its
// four sides), press forward against it and report the best rise.  "touch" counts those spots.
void(float pitch) GS_TestLadders =
{
	local entity l;
	local vector p, c, h;
	local float d, yaw, dz, best, touch, n, ok, ntouch, i, k, lat, dist, wasskin;

	n = ok = ntouch = 0;
	for (l = find(world, classname, "func_ladder"); l; l = find(l, classname, "func_ladder"))
	{
		n = n + 1;
		best = -9999;
		touch = 0;
		c = (l.absmin + l.absmax) * 0.5;
		h = (l.absmax - l.absmin) * 0.5;
		for (k = 0; k < 216 && best < 24; k = k + 1)
		{
			d = k & 3;
			i = floor(k / 4) % 6;                           // the hull 0.25 to 7 units into the brush (absmax is a unit out)
			dist = (i == 0) ? 14.75 : ((i == 1) ? 14.5 : ((i == 2) ? 14 : ((i == 3) ? 13 : ((i == 4) ? 11 : 8))));
			lat = (floor(k / 24) % 3) * 0.6 - 0.6;          // along the face: -0.6, 0, 0.6 of the half width
			p = c;
			p_z = c_z + ((floor(k / 72) % 3) * 0.5 - 0.5) * max(0, h_z - 40);
			if (d == 0)      { p_x = l.absmax_x + dist; p_y = c_y + lat * h_y; yaw = 180; }
			else if (d == 1) { p_x = l.absmin_x - dist; p_y = c_y + lat * h_y; yaw = 0; }
			else if (d == 2) { p_y = l.absmax_y + dist; p_x = c_x + lat * h_x; yaw = 270; }
			else             { p_y = l.absmin_y - dist; p_x = c_x + lat * h_x; yaw = 90; }
			tracebox(p, gs_bot.mins, gs_bot.maxs, p, MOVE_NOMONSTERS, gs_bot);
			if (trace_startsolid)
				continue;
			wasskin = l.skin;
			l.skin = 0;                                 // solid: does the hull meet this brush?
			tracebox(p, gs_bot.mins, gs_bot.maxs, p, MOVE_NOMONSTERS, gs_bot);
			l.skin = wasskin;
			if (!trace_startsolid)
				continue;
			touch = touch + 1;
			GS_TestPlace(p, pitch, yaw);
			gs_bot.movement = '400 0 0';
			gs_bot.button2 = 0;
			// the best rise within 0.32 s: past the top the body walks off, into whatever is there
			for (i = 0; i < 20; i = i + 1)
			{
				GS_TestPhys(1, 16);
				dz = gs_bot.origin_z - p_z;
				if (dz > best)
					best = dz;
				if (dz >= 24 || vlen(gs_bot.origin - p) > 200)
					break;
			}
		}
		if (touch) ntouch = ntouch + 1;
		if (best >= 24) ok = ok + 1;
		print(sprintf("GSTEST ladder %s skin %g size %v touch %g rise %.1f\n", l.model, l.skin, l.size, touch, best));
	}
	gs_bot.movement = '0 0 0';
	print(sprintf("GSTEST ladders pitch %g: %g of %g climbed (%g could be touched)\n", pitch, ok, n, ntouch));
};

// Every liquid brush: a spot inside it where the hull fits, the water level the mover reads there,
// and the upward speed holding jump gives (water 100, slime 80, lava 50).
void() GS_TestWaters =
{
	local entity w;
	local vector p, lo, hi;
	local float k, n, ok, lvl, vz, spots;

	n = ok = 0;
	for (w = nextent(world); w; w = nextent(w))
	{
		if (w.gs_kind != GS_K_LIQUID)
			continue;
		n = n + 1;
		lvl = spots = 0;
		vz = -9999;
		lo = w.absmin + '2 2 2';
		hi = w.absmax - '2 2 2';
		for (k = 0; k < 75 && lvl < 2; k = k + 1)
		{
			p_x = lo_x + (hi_x - lo_x) * ((k % 5) + 0.5) * 0.2;
			p_y = lo_y + (hi_y - lo_y) * ((floor(k / 5) % 5) + 0.5) * 0.2;
			p_z = lo_z + (hi_z - lo_z) * (floor(k / 25) + 0.5) / 3;
			tracebox(p, gs_bot.mins, gs_bot.maxs, p, MOVE_NOMONSTERS, gs_bot);
			if (trace_startsolid)
				continue;
			spots = spots + 1;
			GS_TestPlace(p, 0, 0);
			gs_bot.movement = '0 0 0';
			gs_bot.button2 = 1;
			GS_TestPhys(5, 16);
			if (gs_bot.waterlevel > lvl)
			{
				lvl = gs_bot.waterlevel;
				vz = gs_bot.velocity_z;
			}
		}
		if (lvl >= 2) ok = ok + 1;
		print(sprintf("GSTEST water %s %s skin %g size %v spots %g level %g jump-vz %.1f\n", w.classname, w.model,
		              w.skin, w.size, spots, lvl, vz));
	}
	gs_bot.button2 = 0;
	print(sprintf("GSTEST waters: %g of %g swim (level 2 or 3 reached)\n", ok, n));
};

// Every unnamed solid func_door: stand on it (where the hull fits) and see that the touch starts it.
void() GS_TestDoors =
{
	local entity d;
	local vector p;
	local float n, stood, went, i;

	n = stood = went = 0;
	for (d = find(world, classname, "func_door"); d; d = find(d, classname, "func_door"))
	{
		if (d.gs_kind != GS_K_DOOR || d.targetname != "" || d.solid != SOLID_BSP)
			continue;
		if (d.spawnflags & GS_SF_DOOR_USEONLY)
			continue;
		n = n + 1;
		if (d.gs_state != TS_AT_BOTTOM)
			continue;
		p = (d.absmin + d.absmax) * 0.5;
		p_z = d.absmax_z - 1 + 36.5;
		tracebox(p, gs_bot.mins, gs_bot.maxs, p, MOVE_NORMAL, gs_bot);
		if (trace_startsolid)
			continue;
		GS_TestPlace(p, 0, 0);
		gs_bot.movement = '0 0 0';
		for (i = 0; i < 30 && d.gs_state == TS_AT_BOTTOM; i = i + 1)
		{
			GS_TestPhys(1, 16);
			if (gs_bot.flags & FL_ONGROUND)
				break;
		}
		// a shaped door's box centre can be air: only a body that came to rest on this door counts
		if (d.gs_state == TS_AT_BOTTOM)
		if (!(gs_bot.flags & FL_ONGROUND) || gs_bot.groundentity != d)
			continue;
		stood = stood + 1;
		if (d.gs_state == TS_GOING_UP || d.gs_state == TS_AT_TOP)
			went = went + 1;
		else if (stood - went <= 5)
			print(sprintf("GSTEST door-nostart %s size %v body %v on %s %s (ground %g)\n", d.model, d.size,
			              gs_bot.origin - p, gs_bot.groundentity.classname, gs_bot.groundentity.model,
			              (gs_bot.flags & FL_ONGROUND) != 0));
	}
	print(sprintf("GSTEST doors: %g touch doors, stood on %g, %g started\n", n, stood, went));
};

// Every func_breakable that breaks when run into (spawnflag 2): drop the body onto it from 100 units up,
// which lands at about 400 u/s -- 4 as damage -- so the ones with health over 4 must survive.
void() GS_TestBreaks =
{
	local entity b, nx;
	local vector p;
	local float n, hit, broke, held, i, hp;

	n = hit = broke = held = 0;
	b = find(world, classname, "func_breakable");
	while (b)
	{
		nx = find(b, classname, "func_breakable");
		if (b.gs_kind == GS_K_BREAKABLE && !b.gs_dead)
		if ((b.spawnflags & GS_SF_BREAK_TOUCH) && !(b.spawnflags & GS_SF_BREAK_TRIGGERONLY))
		{
			n = n + 1;
			hp = b.health;
			p = (b.absmin + b.absmax) * 0.5;
			p_z = b.absmax_z - 1 + 36 + 100;
			tracebox(p, gs_bot.mins, gs_bot.maxs, p - '0 0 99', MOVE_NORMAL, gs_bot);
			if (!trace_startsolid && trace_fraction == 1)
			{
				GS_TestPlace(p, 0, 0);
				gs_bot.movement = '0 0 0';
				for (i = 0; i < 40 && !b.gs_dead; i = i + 1)
				{
					GS_TestPhys(1, 16);
					if (gs_bot.flags & FL_ONGROUND)
						break;
				}
				if (b.gs_dead || gs_bot.groundentity == b)
				{
					hit = hit + 1;
					if (b.gs_dead) broke = broke + 1;
					else if (hp > 4 || b.gs_mat == GS_MAT_UNBREAKABLE || !vbsp_mapedit_ok) held = held + 1;
					else print(sprintf("GSTEST break-miss %s health %g mat %g\n", b.model, hp, b.gs_mat));
				}
			}
		}
		b = nx;
	}
	print(sprintf("GSTEST breaks: %g touch breakables, landed on %g, %g broke, %g rightly held\n", n, hit, broke, held));
};

// Fire every targetname once: no gameplay meaning, it runs each entity's use path for the error log.
.float gs_tfired;
void() GS_TestFireAll =
{
	local entity e;
	local float n;
	local string nm;

	n = 0;
	for (e = nextent(world); e; e = nextent(e))
	{
		if (e.targetname == "" || e.gs_dead || e.gs_tfired || e == gs_bot)
			continue;
		if (find(world, targetname, e.targetname) != e)
			continue;
		e.gs_tfired = TRUE;
		nm = e.targetname;
		GS_FireTargets(nm, gs_bot, world, GS_TOGGLE, 0);
		n = n + 1;
	}
	print(sprintf("GSTEST fireall: %g names fired\n", n));
};

void(string c, string a1, string a2, string a3, string a4, string a5) GS_TestCmd =
{
	local entity e, o;
	local vector p;
	local float n;
	local string ln;

	if (c == "bot")
	{
		if (!gs_bot)
		{
			gs_bot = spawnclient();
			if (gs_bot)
			{
				forceinfokey(gs_bot, "name", "gsbot");
				o = self; self = gs_bot; ClientConnect(); PutClientInServer(); self = o;
			}
		}
		print(sprintf("GSTEST bot #%g org %v mins %v maxs %v mt %g\n", num_for_edict(gs_bot), gs_bot.origin,
		              gs_bot.mins, gs_bot.maxs, gs_bot.movetype));
		return;
	}
	if (c == "ent" || c == "entc" || c == "entm")
	{
		n = stof(a2) ? stof(a2) : 8;
		for (e = nextent(world); e && n > 0; e = nextent(e))
		{
			if (c == "ent") { if (strcmp(e.targetname, a1)) continue; }
			else if (c == "entc") { if (strcmp(e.classname, a1)) continue; }
			else if (strcmp(e.model, a1)) continue;
			GS_TestEnt(e);
			n = n - 1;
		}
		return;
	}
	if (c == "fire")
	{
		GS_FireTargets(a1, gs_bot, world, (a2 != "") ? stof(a2) : GS_TOGGLE, 0);
		print(sprintf("GSTEST fire '%s' t %.3f\n", a1, time));
		return;
	}
	if (c == "pc")
	{
		p = [stof(a1), stof(a2), stof(a3)];
		n = -1;
		if (checkbuiltin(pointcontentsmask))
			n = (float)pointcontentsmask(p, FALSE);
		print(sprintf("GSTEST pc %v world %g mask %g\n", p, pointcontents(p), n));
		return;
	}
	if (c == "globals")
	{
		for (e = find(world, classname, "gs_global"); e; e = find(e, classname, "gs_global"))
			print(sprintf("GSTEST global '%s' %g\n", e.netname, e.gs_state));
		return;
	}
	if (c == "states")              // one line: which entities of a class are solid, and their mover state
	{
		ln = "";
		for (e = find(world, classname, a1); e; e = find(e, classname, a1))
		{
			ln = strcat(ln, " ", (e.targetname != "") ? e.targetname : e.model, "=", ftos(e.solid != SOLID_NOT),
			            "/", ftos(e.gs_state));
			if (a2 != "")
				ln = strcat(ln, "@", sprintf("%v", e.origin));
		}
		print(sprintf("GSTEST states %s t %.3f:%s\n", a1, time, ln));
		return;
	}
	if (c == "setskin")
	{
		for (e = find(world, classname, a1); e; e = find(e, classname, a1))
			e.skin = stof(a2);
		return;
	}
	if (c == "velmode")             // control: 0 is what the shared teleport did with these maps before
	{
		for (e = find(world, classname, "trigger_teleport"); e; e = find(e, classname, "trigger_teleport"))
			e.VelocityMode = stof(a1);
		return;
	}
	if (c == "census") { SV_CensusPrint(); return; }
	if (c == "time") { print(sprintf("GSTEST time %.3f %s\n", time, a1)); return; }
	if (!gs_bot)
	{
		print(sprintf("GSTEST %s: no bot\n", c));
		return;
	}
	if (c == "at")          GS_TestPlace([stof(a1), stof(a2), stof(a3)], stof(a4), stof(a5));
	else if (c == "shoot")                          // the shot's damage at every entity of a targetname or model
	{
		for (e = nextent(world); e; e = nextent(e))
			if (!strcmp(e.targetname, a1) || !strcmp(e.model, a1))
				SV_EntityDamage(e, gs_bot, stof(a2));
	}
	else if (c == "move")   { gs_bot.movement = [stof(a1), stof(a2), stof(a3)]; gs_bot.button2 = stof(a4); }
	else if (c == "phys")   GS_TestPhys(stof(a1), stof(a2));
	else if (c == "use")    GS_PlayerUse(gs_bot);
	else if (c == "ladders") GS_TestLadders(stof(a1));
	else if (c == "waters") GS_TestWaters();
	else if (c == "doors")  GS_TestDoors();
	else if (c == "breaks") GS_TestBreaks();
	else if (c == "fireall") GS_TestFireAll();
	else if (c == "pos")
		print(sprintf("GSTEST pos %s t %.3f org %v vel %v ground %g water %g/%g\n", a1, time, gs_bot.origin,
		              gs_bot.velocity, (gs_bot.flags & FL_ONGROUND) != 0, gs_bot.waterlevel, gs_bot.watertype));
	else
		print(sprintf("GSTEST unknown command '%s'\n", c));
};

void() GS_TestThink =
{
	local string ln, c;
	local float n;

	self.nextthink = time + 0.001;
	if (time < gs_tsleep)
		return;
	while (gs_tblank < 64)
	{
		ln = fgets(gs_tf);
		n = tokenize(ln);
		if (!n)
		{
			gs_tblank = gs_tblank + 1;      // a run of blank reads is the end of the file
			continue;
		}
		gs_tblank = 0;
		c = argv(0);
		if (substring(c, 0, 1) == "#")
			continue;
		if (c == "sleep")
		{
			gs_tsleep = time + stof(argv(1));
			return;
		}
		if (c == "quit")
		{
			localcmd("quit\n");
			break;
		}
		GS_TestCmd(c, argv(1), argv(2), argv(3), argv(4), argv(5));
	}
	fclose(gs_tf);
	print("GSTEST end\n");
	remove(self);
};

void() GS_TestStart =
{
	local entity e;

	gs_bot = world;
	gs_tsleep = gs_tblank = 0;
	if (cvar_string("gs_test") == "")
		return;
	gs_tf = fopen(cvar_string("gs_test"), FILE_READ);
	if (gs_tf < 0)
	{
		print(sprintf("GSTEST cannot open '%s'\n", cvar_string("gs_test")));
		return;
	}
	print(sprintf("GSTEST begin %s on %s\n", cvar_string("gs_test"), mapname));
	e = spawn();
	e.classname = "gs_test";
	e.think = GS_TestThink;
	e.nextthink = time + 0.1;
};
#endif

void() GS_MapStart =
{
	local entity e;

	for (e = nextent(world); e; e = nextent(e))
	{
		if (e.gs_kind == GS_K_MULTISOURCE)
			GS_MultiSourceRegister(e);
		else if (e.gs_kind == GS_K_TRAIN)
			GS_TrainActivate(e);
		else if (e.gs_kind == GS_K_AUTO)
		{
			e.think = GS_AutoThink;
			e.nextthink = time + 0.1;
		}
	}
	print(sprintf("goldsrc: %g ladders, %g liquid volumes, %g doors, %g buttons, %g trains, %g triggers, %g logic entities\n",
	              gs_n_ladder, gs_n_liquid, gs_n_door, gs_n_button, gs_n_train, gs_n_trig, gs_n_logic));
#ifdef GS_TEST
	GS_TestStart();
#endif
};
