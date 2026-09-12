/*
===========================================================================
  sv_entities.qc -- Source (VBSP) map entity support.

  Surf maps are Source maps, so the entity lump is full of Valve classnames.
  Build 1 implements only what a surf map actually needs to be traversable:
  spawn points, teleports, pushes, ladders, and -- crucially -- a catch-all
  that keeps unrecognised BRUSH entities as geometry instead of deleting them.
===========================================================================
*/

/*
  FORWARD DECLARATIONS, because sv_progs.src compiles this file FIRST.

  sv_timer.qc is three files further down the list, so anything of its own that
  this file calls has to be promised here.  The engine resolves by name at
  runtime and does not care which file a function was written in; fteqcc does.
  sv_zones.qc has the same block for the same reason.
*/
void(entity e) SV_TimerWarped;

// Q1CONTENTS_LADDER (bspfile.h:189).  Set on .skin, the engine turns it into
// FTECONTENTS_LADDER in AddLinksToPmove (sv_user.c:7018).
#define CONTENT_LADDER -16

/*
  Patch 280: func_slide.  .skin in -32..-25 tags a SOLID brush as a slide and
  skin + 32 is the flag byte (engine pmove.h PMSLIDE_*).  Same channel as the
  ladder above, but NOT a contents override: the engine traces a slide exactly
  as a skin-0 brush and only pm_source.c reads the byte.
  NEVER worn while SOLID_NOT: sv_ents.c:3643 sends any negative-skin brush as
  ES_SOLID_BSP, so the client would predict a disabled slide as a wall the
  server does not have.  func_slide sets it only when solid and SV_IOEnable
  keeps it in step; vbsp_slide_skin remembers the value between the two.
*/
#define SKIN_SLIDE_BASE    -32
#define SLIDE_STAYON        1
#define SLIDE_ALLOWJUMP     2
#define SLIDE_NOGRAVITY     4

// Source's SF_TRIG_PUSH_ONCE.
#define SF_PUSH_ONCE 128

/*
  SOLID_BSPTRIGGER (pr_common.h:712) is a trigger whose volume is the BSP
  submodel rather than its bounding box: World_TouchAllLinks runs a real
  World_ClipMoveToEntity startsolid test against it (world.c:2040-2044), and
  World_LinkEdict rotates its box like a SOLID_BSP one (world.c:557).  Plain
  SOLID_TRIGGER gets neither, so a trigger brush built at an angle -- which on
  a surf map is most of them -- fires across its whole AABB.
  Not in the shipped MenuQC/SSQC defs dump, so declared here.
*/
#define SOLID_BSPTRIGGER 22

// DP_EF_NODRAW is advertised by the defs but the constant itself is not.
#define EF_NODRAW 16

// Source spawnflags we actually read.
#define SF_TELEPORT_CLIENTS         1       // "[1] Clients/Players", on by default
#define SF_TELEPORT_PRESERVE_ANGLES 32
#define SF_WALLTOGGLE_START_OFF     1       // "[1] Starts Invisible"
#define SF_BRUSH_IGNORE_USE         2

// Build 63.  logic_relay, logicrelay.cpp:24-25.
#define SF_RELAY_REMOVE_ON_FIRE     1       // "[1] Only trigger once"
#define SF_RELAY_FAST_RETRIGGER     2       // "[2] Allow fast retrigger"

// Build 63.  logic_case, logicentities.cpp:2204 (MAX_LOGIC_CASES).
#define MAX_LOGIC_CASES            16

/*
  Build 63, Tier 2.  func_button and func_door STATE -- no geometry moves.

  buttons.h:15-20 and doors.h:26-38.  Note SF_BUTTON_TOGGLE and
  SF_DOOR_NO_AUTO_RETURN are the SAME BIT (32) on their respective classes, and
  SF_BUTTON_LOCKED is the same bit as SF_DOOR_LOCKED (2048), which is already
  #defined further down beside SV_UseFrame -- it is not repeated here.

  SF_BUTTON_DAMAGE (512) is named and deliberately never read; see the OnDamaged
  note in SV_UseFrame for why that one can never work in this game.
*/
#define SF_BUTTON_DONTMOVE          1       // buttons.h:15
#define SF_BUTTON_TOGGLE            32      // buttons.h:17
#define SF_BUTTON_TOUCH             256     // buttons.h:18
#define SF_BUTTON_DAMAGE            512     // buttons.h:19 -- never read, see below
#define SF_BUTTON_USE               1024    // buttons.h:20 "Use Activates"
#define SF_DOOR_NO_AUTO_RETURN      32      // doors.h:26
#define SF_DOOR_PUSE                256     // doors.h:30 "Use Opens"

// Source's TOGGLE_STATE, in Source's order -- buttons.cpp:794-801 lists the
// debug strings {Pressed, Unpressed, Pressing, Unpressing} indexed by
// m_toggle_state, and Spawn sets TS_AT_BOTTOM = "Unpressed" (:397).
#define TS_AT_TOP                   0
#define TS_AT_BOTTOM                1
#define TS_GOING_UP                 2
#define TS_GOING_DOWN               3

// CBaseButton's BUTTON_CODE, buttons.cpp.  PRESS toggles, ACTIVATE only goes
// in, RETURN only comes out; the three are not interchangeable (:201-214).
#define BUTTON_PRESS                1
#define BUTTON_ACTIVATE             2
#define BUTTON_RETURN               3

// Which state machine an entity runs, stamped at spawn.  A float compare in the
// input ladder rather than a classname ladder, and it doubles as "is this a
// mover at all" -- which is what keeps the breakable aliases out (see below).
#define MVK_BUTTON                  1
#define MVK_DOOR                    2

// func_brush "solidity"
#define SOLIDITY_TOGGLE 0       // follows StartDisabled
#define SOLIDITY_NEVER  1
#define SOLIDITY_ALWAYS 2

/*
  Source's "solid" key on a PROP.  Note these are Source's numbers, not
  QuakeC's SOLID_ constants -- see the name-collision note in SV_SpawnProp.
*/
#define SRCSOLID_NONE       0   // "Not Solid"
#define SRCSOLID_BBOX       2   // "Use Bounding Box"
#define SRCSOLID_VPHYSICS   6   // "Use VPhysics" -- the collision mesh

// Source rendermode 10 is "Don't Render".
#define RENDERMODE_NONE     10

// Q1CONTENTS_WATER (bspfile.h:176).  Same forced-contents mechanism as
// CONTENT_LADDER above: World_ClipMoveToEntity turns a negative .skin into
// FTECONTENTS_WATER and then only reports the brush to traces whose
// hitcontentsmask actually asks for water (world.c:1330-1393).  A player move
// does not, so the brush stops blocking and starts being swimmable.
#define CONTENT_WATER -3

void() SUB_Remove = { remove(self); };
void() SUB_Null   = { };

// Source keys read below.  These are the VBSP spellings, case as VBSP writes
// them -- the engine's entity parser is case sensitive for field names.
.float  StartDisabled;
.float  solidity;
.float  VelocityMode;
.float  SetSpeed;
.string landmark;
.float  modelscale;
.float  rendermode;
.float  renderamt;
.vector teleportoffset;

// Patch 194, linked_portal_door.  Every one of the library's 443 instances
// writes width, height, angles, targetname and startactive; 440 of 443 also
// write partnername (the three that do not are in maps that pair by nothing at
// all, and they are reported rather than guessed at).
.string partnername;
.float  width;
.float  height;
.float  startactive;

/*
===========================================================================
  THE OTHER SPELLING.

  The rule in the comment above is right -- ED_ParseEdict looks a key up with
  ED_FindField, which is a plain strcmp (qclib/pr_edict.c:293-303, called from
  :1551), so field names ARE case sensitive.  The spellings were wrong.  Hammer
  writes BOTH cases for most of these keys, and for four of them the case
  declared above is the MINORITY one.  Counted over 300 shipped maps:

      'StartDisabled'      53463     'startdisabled'      1808
      'solid'              13762     'Solid'               430
      'VelocityMode'       10773     'velocitymode'         65
      'Solidity'            7354     'solidity'            901
      'speed'               4608     'Speed'               885
      'UseLandmarkAngles'   3355     'uselandmarkangles'   514
      'SetSpeed'             728     'setspeed'            467

  So .solidity has been catching 11% of the keys that exist, and func_brush's
  entire Solidity branch has effectively never run.  5,986 func_brush in that
  sample say Solidity 1, "Never Solid", and every one of them has been a solid
  wall -- including a 9984 x 9984 x 256 slab on surf_666 and a 576 x 2176 x 256
  one across surf_utopia's start line.  This is not a rare-key nicety; it is the
  single biggest cause of "invisible blocks" in the game.

  Every one of these keys means zero when absent, so reading whichever spelling
  is non-zero is exact rather than a heuristic -- there is no value that both
  spellings could disagree about.

  `solid` is deliberately NOT redeclared: it collides with QuakeC's own .solid
  field, which is the whole trick SV_SpawnProp relies on.  Only its capital
  twin is new.

  To find the next one of these: `developer 1` makes ED_ParseEdict print
  "'%s' is not a field" for every key no QC field matched (pr_edict.c:1559).
===========================================================================
*/
.float  Solidity;
.float  startdisabled;
.float  Solid;
.float  velocitymode;
.float  Speed;
.float  setspeed;

// Whichever spelling the mapper's Hammer happened to write.
float(float a, float b) SV_Key2 = { return a ? a : b; };

/*
  THE THREE KEYS WHERE ABSENT AND ZERO ARE DIFFERENT THINGS.

  Everything above means zero when absent, which is what makes SV_Key2 exact.
  "Use Destination Angles" does not: its FGD default is 1, so a map that never
  wrote it wants the angles SNAPPED, while a map that wrote 0 wants them left
  alone -- and a .float cannot tell those apart.

  It matters.  Counted over all 1,308 shipped maps: 16,829 teleports write the
  key, 13,153 of them saying 1 -- but only 1,189 teleports have a landmark at
  all, so Momentum plainly applies it in BOTH modes.  Meanwhile of the 101
  landmark teleports that write it, 82 say 0, which is the FGD's own landmark
  rule ("angles are left alone") stated explicitly.  Reading these as floats
  would collapse "the mapper said no" into "the mapper said nothing" and get
  3,676 teleports backwards.

  So they are declared as STRINGS -- the entity parser assigns the raw text to a
  .string field -- and SV_KeyTri returns -1 for absent.

  Only the lowercase snapvelocitytodestangles exists in the library (98
  instances); it has no capitalised twin, unlike every key above.
*/
.string UseLandmarkAngles;
.string uselandmarkangles;
.string snapvelocitytodestangles;

// -1 = the map never wrote this key at all.  0 / 1 = it did, and meant it.
float(string a, string b) SV_KeyTri =
{
	if (a != "") return (stof(a) != 0);
	if (b != "") return (stof(b) != 0);
	return -1;
};

// +use lands on button5, NOT buttonuse.  Under QuakeWorld the engine puts
// in_use on cmd.buttons bit 4 (cl_input.c:1284, `(protocol==QW)?4:8`), and
// SSQC reads bit N as .button(N+1) (buttonfields[], pr_cmds.c:195).
// .buttonuse is the NetQuake spelling and stays 0 here forever.
.float button5;

/*
  Classname census, developer-gated.
  Surf maps are third-party CS:S content and the FGD is a poor guide to what
  they actually contain -- it lists hundreds of classes, of which a surf map
  uses a dozen.  This counts what really turns up so the next entity to
  implement is chosen from evidence rather than from the FGD's table of
  contents.  Print it with `ent_census`.
*/
float  ent_census_n;
strbuf ent_census_name;
strbuf ent_census_count;

// Returns TRUE the FIRST time a classname is seen, which is what lets the
// catch-all below warn once per unknown class instead of 903 times.
float(string cn) SV_CensusAdd =
{
	local float i;

	// Recorded unconditionally.  It used to be gated on `developer`, which
	// meant the one question it exists to answer -- "did my new spawn function
	// actually get called, or did this classname fall through to here?" --
	// could only be asked by someone who had already known to set a cvar
	// BEFORE loading the map.  The cost is a few hundred string compares at
	// load; the census only ever holds unique classnames.
	if (ent_census_name <= 0)
	{
		ent_census_name  = buf_create();
		ent_census_count = buf_create();
		ent_census_n = 0;
	}

	for (i = 0; i < ent_census_n; i = i + 1)
		if (bufstr_get(ent_census_name, i) == cn)
		{
			bufstr_set(ent_census_count, i,
			           ftos(stof(bufstr_get(ent_census_count, i)) + 1));
			return FALSE;
		}

	bufstr_add(ent_census_name, cn, TRUE);
	bufstr_add(ent_census_count, "1", TRUE);
	ent_census_n = ent_census_n + 1;
	return TRUE;
};

void() SV_CensusPrint =
{
	local float i;

	if (ent_census_n <= 0)
	{
		print("ent_census: every classname on this map has a spawn function\n");
		return;
	}

	print(sprintf("ent_census: %g unhandled classnames/inputs on %s\n",
	              ent_census_n, mapname));
	for (i = 0; i < ent_census_n; i = i + 1)
		print(sprintf("  %5s  %s\n", bufstr_get(ent_census_count, i),
		              bufstr_get(ent_census_name, i)));
};

/*
===========================================================================
  SOURCE ENTITY I/O -- outputs, inputs, and filters.

  Build 37.  Until this, FTESurf modelled NO entity I/O at all, and two bhop
  maps are unplayable for exactly that reason.  The teleport/push/brush classes
  above are each a faithful copy of one Source entity's behaviour; this is the
  wiring BETWEEN entities, which is how a Source map expresses everything that
  is not a property of a single brush.

  WHAT AN OUTPUT LOOKS LIKE.  Hammer writes one keyvalue per connection:

      "OnEndTouch" "!activator,AddOutput,targetname block2,0,-1"
                    <target>  <input>   <parameter>       <dly> <times>

  `times` of -1 is unlimited.  Targets `!activator` / `!caller` / `!self` are
  resolved when the output fires; anything else is a targetname lookup that may
  match SEVERAL entities, and Source fires the input at every one of them.

  THE DELIMITER IS NOT ALWAYS A COMMA, and this is the trap that would have
  made a half-working implementation look finished.  Newer Source compilers
  switched the separator to 0x1B ESC so a parameter could itself contain a
  comma.  The two maps this build exists for are one of each:

      bhop_futile  (VBSP v20)  38 outputs, every one COMMA-separated
      bhop_arcane  (VBSP v25)  23 outputs, every one ESC-separated

  So the separator is detected per value.  A parser that assumed either one
  would silently mis-parse a whole map into single-token garbage rather than
  fail loudly, and the map would look exactly as broken as it does today.

  WHY THE ENGINE HOOK RATHER THAN DECLARED FIELDS.  `.string OnStartTouch`
  would work for one output and lose the rest: ED_ParseEdict assigns by field
  name, so a field keeps only the LAST key of that name, and futile's triggers
  carry several.  ED_ParseUnknownEpair (pr_cmds.c:487-506, README.md:36) is
  called once per key/value pair with `self` bound to the entity being parsed,
  which is the only way to see all of them.  The hook has existed in this fork
  since it was forked and no QC has ever defined it.

  DEFINING IT ALSO SILENCES 4,033 WARNINGS PER MAP LOAD.  SV_BadField returns
  true whenever the hook exists, and pr_edict.c:1557 reads that return as "this
  key was handled" and skips the `'%s' is not a field` DPrintf.  Under
  `developer 1` that spam was measured at 60.7 s to load a map whose BSP parses
  in 2.6 s; the same map without it is 8.3 s.  This is a side effect and not
  the reason, but it is the reason map loads stop being unusable under
  developer.

  NOTHING IS SPAWNED DURING THE PARSE.  The hook accumulates into a string on
  the entity and SV_EntityIOBuild materialises the outputs afterwards, beside
  SV_RepairTargetCase which already runs there.  Spawning an edict from inside
  the engine's own entity-parse loop would happen to work -- FTE fixes up prog
  references when the edict array is relocated -- but it is not a property to
  lean on when a deferred pass costs nothing and is easier to reason about.
===========================================================================
*/
float  vbsp_io_n;			// outputs materialised on this map
float  vbsp_io_fired;		// inputs actually delivered, for the report
float  vbsp_io_on;		// cvar vbsp_entity_io, latched at map load
string vbsp_io_esc;		// chr2str(27), built once

// func_bhop, and teleports that spawn disabled.  Up here with the other
// per-map counters because SV_EntityReset clears them and it comes first.
float  vbsp_bhop_n, vbsp_bhop_tele_n;
float  vbsp_tele_disabled_n;

/*
  FTESurf Build 63 -- the output-cycle fuse, and what it is actually protecting
  against.

  An output that fires an input that fires an output is the POINT of this layer,
  so a cycle cannot be forbidden structurally; it can only be bounded.  Nothing
  re-enters SV_FireOutput today, which is the only reason this has never
  mattered -- logic_relay is a stub.  The moment Trigger works, `OnTrigger
  <self> Trigger` is one line in Hammer and two relays aimed at each other is
  barely more.

  WHAT AN UNBOUNDED CYCLE COSTS, read out of the engine rather than guessed:

    MAX_STACK_DEPTH is 1024 (qclib/progsint.h:167).  PR_EnterFunction prints
    "stack overflow on call to %s (depth %i)" (pr_exec.c:514-518) and calls
    externs->Abort.  Abort IS SV_Error (server/pr_cmds.c:779), and SV_Error
    (sv_main.c:337-404) sends a final message, unspawns every client, and on a
    dedicated build calls Sys_Error -- THE PROCESS EXITS.

  So the same wiring that drops a map on this desktop drops all five Pi lobbies
  and takes a systemd restart, with every run in progress lost.  SV_FireOutput
  is ~4 QC frames per hop, so two relays pointing at each other reach 1024 in
  well under a millisecond: there is no stutter to notice, the server simply
  vanishes.

  Hence a REFUSAL AND A CENSUS LINE, never an error().  A map with a cycle
  should stay playable and tell you which entity did it.

  Delayed outputs deliberately do not consume depth: SV_IODelayThink re-enters
  through SV_IODeliver on a fresh stack with the counter back at zero, which is
  correct -- a delay IS the break in the cycle.
*/
#define VBSP_IO_MAXDEPTH 32
float  vbsp_io_depth;		// SV_FireOutput nesting right now
float  vbsp_io_depth_max;	// high-water mark, so 32 can stop being a guess
float  vbsp_io_depth_hit;	// fires refused by the fuse, for the report

/*
  Build 63.  TWO ceilings, and the per-entity one is the one that matters.

  I predicted the failure mode wrong the first time, and the correction is
  worth keeping because the wrong guess is the intuitive one.  The reasoning
  was: SV_EntityIOBuild spawns one edict per declared output, pr_maxedicts is
  131072 (engine/server/pr_cmds.c:76), bhop_miku_v2 declares far more than
  that, so ED_Alloc Sys_Errors.  True as far as it goes -- and the map never
  gets near it.

  MEASURED, by loading the map with only VBSP_IO_MAXOUT in place: the log goes
  "FTESurf: worldspawn" then "Server ended", with no error line at all.  That
  is during ED_LoadFromFile -- the ENTITY PARSE -- which is long before
  SV_EntityIOBuild runs on the first frame.  The edict ceiling was never
  reached because the server died before any output edict was spawned.

  What actually kills it is ED_ParseUnknownEpair's accumulator.  Every "On"
  key is appended to self.vbsp_io_raw with strcat, so an entity carrying N
  outputs builds its string in N successive reallocating concatenations -- and
  bhop_miku_v2 has a single logic_relay carrying 170,428 of them, for a 5.9 MB
  string built quadratically.

  SO THE CAP HAS TO BE AT THE APPEND, not at the materialise.

  The number, censused across all 1315 maps: the densest legitimate entity in
  the library is surf_forbidden_tomb4's logic_case at 320 outputs, the median
  map's densest entity carries 4, and EXACTLY ONE map has any entity above
  500.  1024 is therefore 3.2x clear of anything real while stopping miku's
  relay dead at 0.6% of its declared size.

  VBSP_IO_MAXOUT stays as a second, map-wide backstop against a map that
  spreads the same abuse over many entities -- which nothing in the library
  does, but which costs one comparison to refuse.
*/
#define VBSP_IO_MAXRAW 1024		// outputs on ONE entity
#define VBSP_IO_MAXOUT 32768	// outputs on the whole map
float  vbsp_io_over_ent;	// refused by the per-entity ceiling
float  vbsp_io_over_map;	// refused by the map-wide ceiling

// On a SOURCE entity.
.string vbsp_io_raw;		// parse-time accumulator, "key\tvalue\n" repeated
.float  vbsp_io_rawn;		// how many are in it -- see VBSP_IO_MAXRAW
.entity vbsp_io_out;		// head of this entity's output list
.float  vbsp_io_solid;	// .solid as spawned, so Enable can put it BACK
.float  vbsp_slide_skin;	// Patch 280: a func_slide's tag, worn on .skin only while solid

// On an vbsp_output entity.  .owner is the source entity.
.entity vbsp_io_next;
.string vbsp_io_name;		// "onendtouch" -- Patch 256 stores it FOLDED; the
							// original spelling stays in vbsp_io_raw
.string vbsp_io_target;	// "!activator"
.string vbsp_io_input;	// "AddOutput"
.string vbsp_io_param;	// "targetname block2"
.float  vbsp_io_delay;
.float  vbsp_io_times;	// -1 unlimited, 0 exhausted

// Source keys this section reads.  `wait` and `count` are Quake field names
// but neither is declared by the shipped SSQC defs, so both are ours.
.float  wait;
.float  count;
.float  vbsp_io_max;		// math_counter's `max`, see SV_EntityIOBuild
// Build 63, completing CMathCounter.  `min` arrives through
// ED_ParseUnknownEpair beside `max` and for the same reason -- see the hook.
// The two latches are m_bHitMin / m_bHitMax: without them OnHitMin and
// OnHitMax would re-fire on every input that left the value at the limit.
.float  vbsp_io_min;
.float  vbsp_io_hitmin, vbsp_io_hitmax;
.float  startvalue,     StartValue;
.float  vbsp_io_next_ok;	// trigger_multiple's `wait` gate on OnTrigger
.string vbsp_dmgfilter;	// SetDamageFilter's argument, stored and not yet read

/*
  Build 63.  logic_relay's m_bWaitForRefire (logicrelay.cpp:32).

  There is deliberately NO field for the relay's disabled state, and that is
  worth a line because its absence looks like an omission.  CLogicRelay declares
  it as DEFINE_KEYFIELD(m_bDisabled, FIELD_BOOLEAN, "StartDisabled")
  (logicrelay.cpp:33) -- m_bDisabled IS StartDisabled, the same key SV_IOEnable
  already writes in both capitalisations and SV_Key2 already reads.  So Enable
  and Disable need no new code and cannot drift out of step with Toggle.
*/
.float  vbsp_relay_wait;

/*
  Build 63.  logic_case -- SIXTEEN cases in four fields, and no array.

  This is the largest dead output family in the library: 6,258 OnCase01..16
  outputs across 112 maps, none of which could ever have fired, because
  logic_case is a point entity with no spawn function and the catch-all deleted
  it before SV_EntityIOBuild ran.

  The obvious storage -- sixteen Case values plus sixteen output slots per
  entity, as Source has (string_t[16] + COutputEvent[16] + unsigned char[16]) --
  would be a per-entity array, and this tree has a measured finding that fteqcc
  array storage costs about 8x its data in progs size.  It turns out not to be
  needed, for two separate reasons:

  1. PickRandom NEEDS NO STORAGE AT ALL.  CLogicCase::BuildCaseMap
     (logicentities.cpp:2349-2366) selects on m_OnCase[i].NumberOfElements() > 0
     -- cases that have an output WIRED, not cases that have a value set; the
     FGD says the same ("Fires a random OnCase output with at least one
     connection").  That question is already answered by the vbsp_io_out chain,
     so SV_IOCaseWired walks it instead.  And PickRandom is 1,142 of the 1,243
     logic_case input fires, so the dominant path costs nothing.

  2. InValue is 101 fires across 13 maps.  At that volume a linear walk of a
     <=16-record accumulator string per fire is free, so the Case values reuse
     the vbsp_io_raw idiom rather than being parsed into anything.
*/
.string vbsp_case_raw;		// "\tNN\tvalue\n" repeated, from ED_ParseUnknownEpair
.int    vbsp_case_shuf;		// PickRandomShuffle: cases already spent this batch
.float  vbsp_case_last;		// m_nLastShuffleCase, the cross-batch repeat avoid

// Build 63.  logic_branch (CLogicBranch::m_bInValue) and logic_compare
// (CLogicCompare::m_InValue / m_CompareValue).  Both key pairs are declared in
// both capitalisations and read through SV_Key2, per the essay above; both mean
// zero when absent, so neither needs the SV_KeyTri tri-state.
.float  vbsp_branch_val;
.float  vbsp_cmp_in;
.float  vbsp_cmp_cmp;
.float  InitialValue,  initialvalue;
.float  CompareValue,  comparevalue;

/*
  Build 63, Tier 2.  func_button / func_door state.  NOTHING MOVES.

  The rule that decides what may fire, and it is the whole design: FIRE WHAT IS
  TRUE OF THE STATE MACHINE, NEVER WHAT IS A CLAIM ABOUT GEOMETRY.

    OnPressed / OnUseLocked / OnLockedUse   fire -- pure interaction events.
    OnOpen / OnClose                        fire -- they mean "told to open",
                                            and Source fires them at the START
                                            of the move (doors.cpp:1008/1091).
    OnIn / OnOut                            fire -- and this is not emulation:
                                            CBaseButton::Spawn collapses a
                                            SF_BUTTON_DONTMOVE button's travel
                                            to zero (buttons.cpp:406-409) and
                                            LinearMove short-circuits straight
                                            to MoveDone when the destination
                                            equals the origin (subs.cpp:205-210).
                                            A non-moving Source button fires
                                            these through the identical path.
    OnFullyOpen / OnFullyClosed             DO NOT FIRE.  Those are statements
                                            about where the brush is.  Firing
                                            one on a door that has not moved
                                            tells a map the route is open while
                                            a solid wall is still in it -- a
                                            NEW failure mode that frozen-and-
                                            silent does not have.

  That costs the headline number: func_movelinear's 818 OnFullyOpen across 63
  maps stay dead until a real mover exists.  It is the right trade, because
  func_movelinear has no Source configuration in which it does not move, so
  faking its arrival would be fabrication with no C++ to point at.

  .speed, .lip and .wait are the map's own keys; `wait` is already declared
  above for trigger_multiple and is the same key here.
*/
.float  vbsp_mv_kind;		// MVK_*, stamped at spawn.  0 = not a mover.
.float  vbsp_mv_state;		// TS_*, Source's m_toggle_state
.float  vbsp_mv_locked;		// m_bLocked -- SEEDED by the spawnflag, not equal to it
.float  vbsp_mv_stay;		// m_fStayPushed, (wait == -1)
.float  vbsp_mv_wait;		// resolved, with the CODE default not the FGD one
.float  vbsp_mv_travel;		// cached traveltime; Tier 2 and a later mover agree
.float  vbsp_mv_uselocked;	// m_flUseLockedTime, the 0.5s OnUseLocked debounce
.entity vbsp_mv_act;		// m_hActivator -- OnIn/OnOut name it, buttons.cpp:731/762
.float  lip,  Lip;			// both spellings, per SV_Key2

/*
  On a PLAYER: the env_fog_controller SetFogController last put them on, by
  targetname.  Declared here rather than with the timer's fields because
  SV_ApplyInput (this file) is what writes it, and this file is compiled before
  sv_main.qc, which is where it is published as STAT_FS_FOGCTRL.  The client
  holds the actual fog parameters -- only the name travels.
*/
.string run_fogctrl;
.entity vbsp_touch_who;	// synthesised end-touch, see trigger_multiple
.float  vbsp_touch_when;

/*
  PATCH 270, STAGE 2 -- the same state, once per player instead of once.

  vbsp_touch_who tracks exactly ONE toucher, which the essay above
  SV_TriggerEndThink states outright and names as "the first thing that would
  need revisiting for real multiplayer".  This is that revisit.

  Three slot masks on the TRIGGER, one bit per client:

    vbsp_touch_in    confirmed inside as of the last sweep
    vbsp_touch_seen  has touched since the last sweep
    vbsp_once_done   has consumed this trigger_once (lobby_retrigger)

  WHY A MASK AND NOT PER-PAIR STATE.  The correct structure is one record per
  (player, trigger) pair, and QuakeC has nowhere to put one: there are no
  per-entity arrays, and an entity per pair means a spawn/remove on every bhop
  block crossing plus a find() -- which scans EVERY edict, not every match, so
  on a 1122-brush map that is a five-figure per-frame cost.  A mask is two int
  stores per touch and no allocation at all.

  What the mask cannot hold is a per-player TIMESTAMP, which is what the 0.05 s
  end-touch grace was built on.  So the grace is quantised into sweep windows
  instead -- and getting that quantisation wrong is the interesting part.

  THE FIRST VERSION USED ONE WINDOW AND WAS A REGRESSION FOR A SINGLE PLAYER.
  It was argued from the MAXIMUM latency ("0.03-0.06 s against today's
  0.05-0.07 s, no worse") and the maximum is not what 0.05 was chosen for.  The
  essay at SV_TriggerEndThink says why: "too short and one dropped frame fires
  a spurious end-touch mid-platform".  Build 51's test is `time - when > 0.05`
  measured from the LAST touch, so its MINIMUM grace is 0.05 s whatever the
  poll rate.  One window is 0.03 s -- two physics frames on surf, three on
  bhop -- so any 0.030-0.049 s gap fired an OnEndTouch that build 51 would not
  have fired, and then an OnStartTouch on re-contact.  On the seven maps where
  AddOutput targetname IS the progression logic that is a rename mid-crossing.
  It also made the claim that this is "a no-op with one player" false, which
  broke the house rule rather than merely being untidy.

  So a bit must now be absent for TWO consecutive windows.  vbsp_touch_out is
  the intermediate state: seen-absent-once.  That puts the grace at 0.06-0.09 s
  against build 51's 0.05-0.07 s -- LONGER at both ends, deliberately, because
  the two errors are not symmetric.  Ending a touch too late re-fires logic
  that is idempotent on these maps; ending it too early injects an end/start
  pair that is not.  vbsp_mp 0 still restores the timestamp path exactly.

  THE BIT INDEX IS num_for_edict(player) - 1, not run_t_slot.  It has to be,
  twice over: run_t_slot is declared in sv_timer.qc, which compiles after this
  file, and it is capped at FS_MAXPLAYERS and can be -1.  The edict number of a
  client is assigned by the engine, is 1..maxclients, and never changes for the
  life of the connection.  edict_num() turns it back into the entity, which is
  what lets the sweep name an activator it only holds as a bit.

  ABOVE 32 CLIENTS the bit does not exist -- an int is 32 bits -- and those
  players fall back to the shared vbsp_touch_who path, i.e. exactly today's
  behaviour.  That is deliberate rather than a limit worth removing: MAX_CLIENTS
  is 40 so that a spectator, an MVD recorder and an admin have somewhere to sit
  ABOVE the 32 playing slots, and none of those three should be tripping map
  triggers in the first place.
*/
.int    vbsp_touch_in;
.int    vbsp_touch_seen;
.int    vbsp_touch_out;         // absent for one window, not yet ended
.int    vbsp_once_done;

/*
  Which players have already spent the current `wait` window.

  vbsp_io_next_ok alone is a per-TRIGGER cooldown, so on a 32-player map one
  player crossing a trigger_multiple with `wait 1` swallows everybody else's
  OnTrigger for a second.

  THE FIRST ATTEMPT AT THIS WAS AN `.entity vbsp_io_next_who` -- "gate only
  against whoever set it" -- AND IT WAS MUCH WORSE THAN THE BUG IT FIXED.  The
  field was rewritten on every touch, so it could only ever match when the SAME
  player touched twice in a row.  Two players standing in one volume overwrite
  it for each other on every single command, so NEITHER ever matched, both
  passed, and OnTrigger fired twice per tick -- about 200 times a second on a
  bhop map against `wait 1`.  On a trigger driving a math_counter that reaches
  OnHitMax instantly; on the 465 OnTrigger->AddOutput outputs it rewrites
  gravity or targetname at tick rate.  It was written down as a residual
  affecting "two players deliberately taking turns"; it actually needed no
  deliberation at all, only co-occupancy, which is the normal lobby case.

  What works is a consumption mask over the SHARED window: the window is still
  one timer per trigger, but each player may spend it once.  Everyone gets
  their OnTrigger, nobody swallows anyone else's, and the fire rate is bounded
  by how many people are standing there rather than by the tick rate.
*/
.int vbsp_io_gate_seen;

/*
  Per-player func_bhop landing count -- the block's .count, moved onto the
  player.  See SV_BhopFrame.
*/
.entity vbsp_bhop_cntblk;
.float  vbsp_bhop_cnt;

/*
  vbsp_mp -- the master switch for everything in this block.  Latched once per
  frame in StartFrame beside run_bv_debug, for the reason that comment gives.

  0 restores build 51 exactly: one toucher per trigger, one shared `wait` gate,
  one shared landing count.  With a single player on the server the two paths
  are indistinguishable by construction -- one player is one bit -- so this is
  a falsifier for the rewrite rather than a gameplay preference.
*/
float vbsp_mp;

/*
  vbsp_retrigger -- lobby_enable && lobby_retrigger, latched in the same place.

  Kept as its own flag rather than read from sv_lobby.qc because that file
  compiles AFTER this one; the policy is expressed once, in StartFrame, next to
  every other per-frame cvar latch.  Separate from vbsp_mp because re-arming a
  trigger_once is a real change to what a map does, and it is only ever right
  in a lobby -- whereas vbsp_mp is a correctness fix that is a no-op with one
  player.
*/
float vbsp_retrigger;

/*
  Bit for a client's edict, or 0 if it has not got one.

  Returns 0 rather than a bit for anything that is not a live client edict in
  1..32, and every caller treats 0 as "use the shared path".  Written once so
  the two callers cannot disagree about the bound.
*/
int(entity p) SV_TouchBit =
{
	local float n;

	if (!vbsp_mp)
		return 0;
	n = num_for_edict(p) - 1;
	if (n < 0 || n >= 32)
		return 0;
	return (int)1 << (int)n;
};

/*
  Give a departing client's bit back, everywhere.

  THE BIT IS A SLOT, NOT A PERSON, and that is the hole this closes.  The essay
  above says the edict number "never changes for the life of the connection",
  which is true and is not enough: vbsp_once_done OUTLIVES the connection.
  Under vbsp_retrigger a consumed trigger_once is deliberately not removed, so
  the bit on the trigger is the only record that it was used -- and the engine
  hands the lowest free client slot to the next person who connects
  (sv_main.c:2516-2522), which is the same edict, which is the same bit.

  Left uncleared, a joining player silently inherits every trigger_once the
  previous occupant of their slot had consumed: no OnTrigger, no OnStartTouch,
  no OnEndTouch, nothing printed, for the rest of the map.  On the 841 library
  trigger_onces that wire an output that is the map's progression logic simply
  absent for them.  It is the exact harm lobby_retrigger exists to prevent,
  reintroduced one connection later.

  THE THREE SWEEP MASKS ARE DELIBERATELY LEFT ALONE, and an earlier version of
  this cleared them.  Clearing looks tidier and is wrong twice over.  It DROPS
  the OnEndTouch and OnEndTouchAll the departure should produce -- and on the
  seven maps where end-touch is the progression logic those events are map
  state, not player state, so losing them leaves the map wedged.  And it is
  inconsistent with the path beside it: build 51 holds the departing player in
  .vbsp_touch_who and its sweep fires the map's OnEndTouch at them, because a
  client edict is never freed -- ClientDisconnect leaves the slot allocated, so
  the entity reference stays valid and the activator is the player who left.
  Leaving the bits set makes the mask path do exactly the same thing, and the
  sweep clears them two windows later of its own accord.

  Aliasing is not a risk on that path: a slot passes through cs_zombie before
  it is free (sv_main.c:666-670), which is seconds, against a 0.06 s sweep.
  vbsp_once_done has no sweep at all, which is the whole point.

  NOT gated on vbsp_mp, and the bit is computed here rather than through
  SV_TouchBit: the bits may have been set while it was 1 and it is latched at
  map load, so a release that only runs in one mode leaks in the other.

  One walk of the edict table per disconnect -- the same shape as the four
  map-init walks already in this file, on an event that happens far less often.
*/
void(entity p) SV_TouchForget =
{
	local entity e;
	local float  n;
	local int    keep;

	n = num_for_edict(p) - 1;
	if (n < 0 || n >= 32)
		return;
	keep = ~((int)1 << (int)n);

	for (e = nextent(world); e; e = nextent(e))
	{
		e.vbsp_once_done    = e.vbsp_once_done    & keep;
		e.vbsp_io_gate_seen = e.vbsp_io_gate_seen & keep;
	}
};

// On a PLAYER.  ModifySpeed's multiplier, applied in PlayerPreThink; and the
// func_bhop dwell state, driven from PlayerPostThink.  Declared here because
// sv_entities.qc is the first file in sv_progs.src and sv_player.qc reads them.
.float  run_speedmod;
.entity vbsp_bhop_on;
.float  vbsp_bhop_since;
// Ground state as it stood BEFORE this command's move, stamped by PlayerPreThink
// and read by SV_TriggerIOTouch after it -- which is how OnJump can tell a jump
// from walking off a ledge on the exact command it happens.
.float  run_wasground;

/*
  On a PLAYER.  Source's basevelocity, and the field engine Patch 240 reads.

  The engine copies it into pmove.basevelocity at the TOP of the next movement
  command -- immediately after PMSrc_LoadState -- and ZEROES IT AS IT READS, so
  it is a one-command carrier that cannot latch no matter what QC does with it.
  pm_source.c then adds it before the move and subtracts it after (and, for Z,
  spends it through StartGravity as an acceleration), which is Source's own
  add/move/subtract sandwich.

  Declaring it is the entire opt-in.  The engine looks the field up by name and
  caches the miss, so an engine with Patch 240 running a mod without this line
  does nothing at all -- which is how `quakers`, sharing this tree, is unaffected.

  Declared up here rather than beside trigger_push because SV_IOAddOutput reads
  it 1600 lines earlier, and fteqcc wants the field before its first use.
*/
.vector run_basevelocity;

/*
===========================================================================
  PATCH 249 -- THE OTHER HALF OF BASEVELOCITY, and why the boosters did not boost.

  Patch 240 wired the carrier and stopped one step short.  What it built is
  Source's `m_vecBaseVelocity` and the add/move/subtract sandwich around it.
  What it did not build is `CPlayerMove::CheckMovingGround`
  (player_command.cpp:97-127), which is where a carrier turns into speed you
  keep -- and without it a booster pad delivers about 1.5% of its number.

  SOURCE HAS A FLAG, AND THE FLAG IS THE WHOLE MECHANISM.  Every tick, before
  the move, Source runs:

      if ( !( player->GetFlags() & FL_BASEVELOCITY ) )
      {
          player->ApplyAbsVelocityImpulse( (1.0 + (frametime * 0.5)) * player->GetBaseVelocity() );
          player->SetBaseVelocity( vec3_origin );
      }
      player->RemoveFlag( FL_BASEVELOCITY );

  So basevelocity is not consumed by being ridden.  It is CASHED OUT into real
  velocity on the first tick that nothing re-armed it -- and the flag, cleared
  unconditionally on the line after, is what "nothing re-armed it" means.

  THE TWO WRITERS DIFFER IN EXACTLY ONE BIT, and that bit is the entire bug:

    trigger_push  sets basevelocity AND the flag (triggers.cpp:2270-2271).  So
                  while you stand in the volume the cash-out never fires; you
                  ride the carrier, keep full strafe control, and collect the
                  horizontal part as real velocity on the tick AFTER you leave.

    AddOutput     sets basevelocity through KeyValue and does NOT touch the
                  flag (baseentity.cpp:7440 -> saverestore_gamedll.cpp:80).  So
                  the very next tick cashes it out in full.

  `AddOutput basevelocity 0 0 650` is therefore a 654.875 u/s launch, not the
  9.75 u/s that Patch 240's note claimed -- and that note is corrected where it
  stands.  The claim came from reading StartGravity's

      velocity[2] += basevelocity[2] * frametime;   basevelocity[2] = 0;

  in isolation and concluding Z was an acceleration.  It IS an acceleration --
  for a carrier that a conveyor or a trigger_push re-arms every tick.  For an
  AddOutput write the cash-out at the top of the tick has already emptied
  basevelocity before StartGravity ever looks at it, because CheckMovingGround
  runs at player_command.cpp:472 and ProcessMovement not until :515.

  HOW BIG THIS IS.  2004 `AddOutput basevelocity` outputs across 298 of the
  1310 maps, carried by OnEndTouch (776), OnStartTouch (613) and OnJump (579).
  Every one of them has been delivering a rounding error.  bhop_futile's six
  pads were never the story; they were the six we happened to be looking at.

  THE MODEL, IN QC.  QC owns the authoritative vector and the flag; the engine
  field stays exactly what Patch 240 made it, a one-command hand-off:

    .run_basevel        m_vecBaseVelocity   -- survives across commands
    .run_basevel_armed  FL_BASEVELOCITY     -- set by a touch, cleared every command
    .run_basevelocity   the engine's read-and-clear window for THIS command

  SV_BaseVelocityFrame is CheckMovingGround and runs from PlayerPreThink, which
  is the same slot: before the move, before the engine reads the field, after
  last command's touches.  SV_BaseVelocityPost mirrors the one thing pm_source
  does to the vector that QC cannot see -- StartGravity spends Z and zeroes it,
  and our held copy has to be zeroed with it or the same Z is spent again next
  command and then cashed out on top.

  No engine change.  Patch 240's field, read and cleared where it always was.
===========================================================================
*/
.vector run_basevel;
.float  run_basevel_armed;

// TICK_INTERVAL, for the (1.0 + frametime * 0.5) fudge in the cash-out --
// Source's own "add in half of the previous frame of velocity first".  It is
// worth 0.75% at a 15 ms tick, which is not why it is here; it is here because
// a number copied without its constant is a number nobody can check later.
float run_bv_tick;

// Reported by SV_EntityReport: how many AddOutput writes landed, and how many
// of them turned into speed.  They should be equal on a map whose pads all
// fire while you are on them; a large gap means something is re-arming the
// carrier every command and the cash-out never fires.
float run_bv_set_n, run_bv_paid_n;

// `run_bv_debug 1` prints every cash-out.  A plain cvar read per command per
// player would be silly, so it is latched by SV_UpdateMovementServerInfo
// alongside the movement vars it already refreshes.
float run_bv_debug;

void(entity pl) SV_BaseVelocityFrame =
{
	if (!pl.run_basevel_armed && pl.run_basevel != '0 0 0')
	{
		local vector was;

		was = pl.velocity;
		pl.velocity = pl.velocity + (1 + run_bv_tick * 0.5) * pl.run_basevel;
		run_bv_paid_n = run_bv_paid_n + 1;

		// The one line that makes this patch checkable from a log: what was
		// held, and what it was worth.  A pad authored `basevelocity 0 0 650`
		// must print 650 here and move the speed by 654.9 -- if it prints 9.8
		// the cash-out is not running and the carrier is being drained by
		// StartGravity instead, which is precisely the bug this patch fixes.
		// sprintf tops out at eight varargs, so this reports DELTAS rather than
		// before/after pairs -- which is the number being checked anyway.
		if (run_bv_debug)
			// "paid" counts every cash-out, push volumes included; "AddOutput"
			// counts only pad writes, so paid > AddOutput means a trigger_push.
			print(sprintf("basevel: paid #%g [AddOutput %g] %s -> speed %.1f (h %+.1f, v %+.1f)\n",
			              run_bv_paid_n, run_bv_set_n, vtos(pl.run_basevel),
			              vlen([pl.velocity_x, pl.velocity_y, 0]),
			              vlen([pl.velocity_x, pl.velocity_y, 0]) - vlen([was_x, was_y, 0]),
			              pl.velocity_z - was_z));

		pl.run_basevel = '0 0 0';
	}

	// RemoveFlag, and it is UNCONDITIONAL in Source (player_command.cpp:126).
	// That single line is what makes the accumulate in trigger_push_touch a
	// sum across volumes OVERLAPPING IN ONE COMMAND rather than a per-command
	// accumulation from one volume.  Drop it and a push compounds forever.
	pl.run_basevel_armed = FALSE;

	// Hand this command's carrier to the engine.  It reads and zeroes this
	// field itself (sv_user.c:7994-7999); .run_basevel is ours and persists.
	pl.run_basevelocity = pl.run_basevel;

	/*
	  AND SPEND Z HERE, on the value just handed over -- not after the move.

	  PMSrc_StartGravity will add basevelocity[2] * frametime into velocity and
	  zero it, inside `pmove`, where QC cannot watch it happen.  The obvious
	  place to mirror that is PlayerPostThink, and the obvious place is wrong
	  TWICE, both times because the touch loop runs between the move and
	  PostThink:

	    - An `AddOutput basevelocity 0 0 500` written by a touch on THIS command
	      would be zeroed by a post-move drain before the next command's
	      cash-out ever saw it.  A vertical boost would vanish entirely -- which
	      it did, and this is the bug that turned up in bv02.
	    - A trigger_push re-arming on THIS command writes a fresh carrier with a
	      fresh Z.  Source's StartGravity drained the PREVIOUS tick's value; a
	      post-move drain would eat the new one a tick early.

	  Draining it here is exactly Source's ordering: the value pmove is about to
	  be given is the value whose Z pmove is about to spend.  Anything a touch
	  writes afterwards is next command's carrier and keeps its Z.
	*/
	pl.run_basevel_z = 0;
};

void(entity src, string name, entity act) SV_FireOutput;

//Patch 256: logic_timer is defined near the other I/O endpoints at the bottom
//of the file, but SV_IOEnable has to re-arm one and SV_ApplyInput has to
//recognise one, and both are up here.  Fields and prototypes, no behaviour.
.float RefireTime;
.float UseRandomTime;
.float LowerRandomBound;
.float UpperRandomBound;
float(entity t) SV_TimerInterval;
void() SV_TimerThink;

/*
  Build 63.  The oscillator, SF_TIMER_UPDOWN (logicentities.cpp:195).

  An "Oscillator" timer alternates OnTimerHigh and OnTimerLow instead of firing
  OnTimer at all.  11 and 12 outputs respectively -- small, but they are the
  only reason those two names appear in the library, and a map that sets the
  flag fired NOTHING before this, because SV_TimerThink only ever knew OnTimer.

  SV_TimerFire is prototyped here rather than inlined at the two call sites for
  a reason worth keeping: SV_ApplyInput's FireTimer branch and SV_TimerThink
  must not be able to disagree about WHICH of the three outputs a given timer
  fires.  One function, two callers.
*/
#define SF_TIMER_UPDOWN 1
.float vbsp_timer_updown;		// CTimerEntity::m_bUpDownState
void(entity t) SV_TimerFire;

/*
  Build 63, Tier 2.  Button and door state -- prototypes only, same arrangement
  and same reason as the timer block above.

  The bodies cannot live up here: they read .speed, .lip and .wait, and .speed
  is not declared until much further down (beside trigger_push).  But
  SV_ApplyInput and SV_UseFrame both drive them and both compile long before
  that.  So: names here, behaviour beside SV_SpawnDoor.
*/
void(entity t, float on)               SV_MoverLock;
void(entity t, entity act, float code) SV_ButtonPress;
void(entity t, entity act)             SV_ButtonUse;
void(entity t, entity act)             SV_DoorUse;
void(entity t, entity act)             SV_DoorOpen;
void(entity t, entity act)             SV_DoorClose;
void(entity t, entity act)             SV_MoverOnUseLocked;

/*
  ED_PARSEUNKNOWNEPAIR -- called by the engine for every key with no field.

  Deliberately does almost nothing.  It runs for EVERY unmatched key on every
  entity -- 4,033 times on bhop_arcane -- so the first line is the cheap
  rejection, and everything expensive happens later in SV_EntityIOBuild.

  `max` is captured by name because QuakeC cannot declare a field called `max`:
  the identifier is already a builtin, and `.float max;` does not compile.  The
  hook is the only way to read that key at all, which is a neat demonstration
  of what it is for -- see the math_counter note below.
*/
void(string key, string value) ED_ParseUnknownEpair =
{
	if (value == "")
		return;

	if (substring(key, 0, 2) == "On")
	{
		/*
		  Build 63.  The per-entity ceiling -- see VBSP_IO_MAXRAW for why this
		  is here and not at the materialise, and for the census that sets 1024.

		  Counted rather than measured with strlen: this runs for every output
		  key on every entity of every map, and a strlen of a string that is
		  being built by repeated strcat is exactly the cost being avoided.
		*/
		if (self.vbsp_io_rawn >= VBSP_IO_MAXRAW)
		{
			vbsp_io_over_ent = vbsp_io_over_ent + 1;
			return;
		}
		self.vbsp_io_rawn = self.vbsp_io_rawn + 1;

		// A newline cannot occur inside a VBSP keyvalue (the lump is
		// line-structured and the parser would have split there), and neither
		// can a tab, so both are safe record separators.
		self.vbsp_io_raw = strcat(self.vbsp_io_raw, key, "\t", value, "\n");
		return;
	}

	if (key == "max" || key == "Max")
	{
		self.vbsp_io_max = stof(value);
		return;
	}

	// Build 63.  `min` is here for exactly the reason `max` is, and it is worth
	// stating so nobody "tidies" either into the field block: both are fteqcc
	// intrinsics -- min is builtin #94 and max #95 (defs/sv_defs.qc:978/981) --
	// so neither `.float min;` nor `.float max;` compiles at all.
	if (key == "min" || key == "Min")
	{
		self.vbsp_io_min = stof(value);
		return;
	}

	/*
	  Build 63.  logic_case's Case01..Case16.

	  These do not start with "On", so until now this hook dropped every one of
	  them -- which was invisible, because the class had no spawn function
	  either and the entity was deleted before anything could have read them.

	  strlen FIRST, and that ordering is the point rather than fussiness: this
	  function runs for EVERY unmatched key on EVERY entity -- thousands of
	  times on a dense map -- and substring() allocates a temporary each call
	  while strlen allocates nothing.  The length test also keeps a longer key
	  beginning "Case" from being mistaken for one of the sixteen.

	  Both capitalisations, for the reason the SV_Key2 essay gives at length.
	  Stored in its OWN accumulator rather than vbsp_io_raw, so SV_EntityIOBuild
	  never hands a non-output to the output parser or to the "nothing fires
	  this" check.
	*/
	if (strlen(key) == 6)
	if (substring(key, 0, 4) == "Case" || substring(key, 0, 4) == "case")
	{
		// Same record separators as vbsp_io_raw, and safe for the same reason:
		// a VBSP keyvalue is line-structured, so it can hold neither a tab nor
		// a newline.
		self.vbsp_case_raw = strcat(self.vbsp_case_raw, "\t",
		                            substring(key, 4, -1), "\t", value, "\n");
	}
};

/*
  Resolve a targetname, tolerating letter case.

  Source's entity I/O is case-insensitive and mappers rely on it without
  knowing they do -- the whole of Patch 191 is that fact costing 1,168 dead
  teleports.  Patch 191 repairs `.target` and `.landmark` at load; the strings
  in an OUTPUT are not fields and never passed through it, so the same
  tolerance is applied here at lookup time.

  Only the FIRST lookup falls back to the case-insensitive scan; continuing a
  chain from a non-world start is an exact find().  An output whose target
  matches several entities differing only in case is a map that is already
  ambiguous in Source, and guessing further would be inventing behaviour.
*/
entity(string want, entity from) SV_FindByName =
{
	local entity d;

	if (want == "")
		return world;

	d = find(from, targetname, want);
	if (d)
		return d;
	if (from != world)
		return world;			// chain exhausted, not a failed first lookup

	for (d = nextent(world); d; d = nextent(d))
		if (d.targetname != "" && !strcasecmp(d.targetname, want))
			return d;
	return world;
};

/*
  FILTERS, and the key-name overload that is a genuine trap.

  On a FILTER entity, `filtername` is the name the filter matches.  On a
  TRIGGER, `filtername` is the targetname OF the filter.  Both maps here use
  both senses of the same key, so reading it as one thing gets the other
  backwards.

  MISSING AND UNIMPLEMENTED FILTERS BOTH PASS.  Source's CBaseFilter lookup
  returns NULL for a name that resolves to nothing and PassesFilter then
  returns true, so failing open is the faithful behaviour and not a shortcut --
  and both cases are live here:

      bhop_futile  6 trigger_multiple reference `boosterqwd`, which is not an
                   entity in the map at all.
      bhop_arcane  12 trigger_teleport and 4 trigger_setspeed reference
                   `filter_standing`, which IS in the map -- as a
                   filter_momentum_surface_collision, a class this build does
                   not implement.

  Failing CLOSED on the second case would kill twelve of arcane's teleports
  while fixing its blocks, which is the sort of trade that turns one bug report
  into two.  The unimplemented class is censused instead.
*/
.string filtername;
.float  Negated;
/*
  BUILD 51: AND THE LOWERCASE SPELLING, which every other dual-cased key in this
  file already had and this one did not.

  ED_ParseEdict matches keys CASE-SENSITIVELY against QC field names, which is
  why SV_Key2 exists at :141 and why Solidity/startdisabled/Solid/velocitymode/
  Speed/setspeed are all declared in pairs above.  `Negated` was the one filter
  key read raw, so a mapper whose Hammer wrote `negated` got the field left at 0
  and the test un-inverted -- the filter then passed exactly the activators it
  was authored to block.

  Censused rather than assumed: 90 filter entities in the 1310-map library write
  the key lowercase, and 26 of those are truthy.  Five of the 26 are
  filter_activator_name -- bhop_2shiny2shuckle, bhop_floodwaters, surf_agony and
  surf_dune -- which is the one filter class this build implements, so those five
  are inverted TODAY.  The other 21 are filter_activator_context and
  filter_multi, neither implemented yet; declaring the pair now means whichever
  build adds them inherits the fix instead of the bug.
*/
.float  negated;
.entity ui_filter;
.float  vbsp_filterdone;

/*
  FTESurf Patch 256 splits the PREDICATE out of SV_PassesFilter, because the
  two callers ask opposite questions of the same test.

  SV_PassesFilter is the TRIGGER's question -- "I carry a filtername, does this
  activator get through?" -- and it owns the name lookup and the cache.
  SV_FilterPasses is the FILTER's own question -- "does this activator pass
  ME?" -- which is what Source's CBaseFilter::PassesFilter is (filters.cpp:46-50),
  and it is what the TestActivator input needs.  Same test, no duplicate.
*/
/*
===========================================================================
  BUILD 51 -- filter_multi, the biggest hole in the filter system.

  320 of them across 50 maps, and 2847 TRIGGERS point at one.  Every one of
  those triggers has been failing open since the filter system was written,
  which on the badges family is not a cosmetic loss: 252 of bhop_badges_mini's
  reset teleports are gated on a filter_multi, so they fire on first touch and
  end the run.  Same shape as the pre-build-37 bhop_futile bug, in a different
  filter class.  Worst maps: kz_bhop_benchmark 415 triggers, bhop_pharma 403,
  bhop_badges2 371, kz_bhop_badg3s 367, kz_bhop_yonkoma 357, bhop_lego 278,
  bhop_badges_mini 252.

  IT IS WORTH IMPLEMENTING BECAUSE ITS CHILDREN ARE.  Of the 901 sub-filter
  references, 778 (86%) resolve to filter_activator_name -- the one class this
  build already evaluates.  The rest are filter_activator_class 56, a nested
  filter_multi 42, filter_activator_context 13, filter_momentum_collectibles 8,
  and single figures of four more.

  FAIL-OPEN COMPOSES, which is what makes this safe.  An unimplemented child
  returns TRUE from the recursion below, exactly as it does when a trigger
  points at it directly.  Under OR that passes the parent, under AND it simply
  does not block -- both are the fail-open direction, so adding filter_multi
  cannot make an unimplemented class start rejecting players.

  filtertype: 1 is OR (280 of 319), 0 is AND (39).  The FGD's wording is
  "0: AND (all filters must pass) / 1: OR (any filter must pass)".  Only 319 of
  the 320 write it at all; the missing one gets Source's default of 0 = AND.

  EIGHT SUB-FILTERS, not five.  Hammer's own dialog offers five and 305 of the
  320 use two or fewer, but two instances in the library carry Filter06..08 and
  stopping at five would evaluate those two incorrectly rather than visibly.
  Both spellings of every one: 13 instances write `filter01`, 11 write
  `negated`, and ED_ParseEdict is case-sensitive.
===========================================================================
*/
.string Filter01; .string Filter02; .string Filter03; .string Filter04;
.string Filter05; .string Filter06; .string Filter07; .string Filter08;
.string filter01; .string filter02; .string filter03; .string filter04;
.string filter05; .string filter06; .string filter07; .string filter08;
.float  filtertype;

// SV_Key2 is for floats; the same idea for the dual-cased string keys.
string(string a, string b) SV_KeyS2 = { return (a != "") ? a : b; };

string(entity f, float i) SV_MultiSub =
{
	if (i == 1) return SV_KeyS2(f.Filter01, f.filter01);
	if (i == 2) return SV_KeyS2(f.Filter02, f.filter02);
	if (i == 3) return SV_KeyS2(f.Filter03, f.filter03);
	if (i == 4) return SV_KeyS2(f.Filter04, f.filter04);
	if (i == 5) return SV_KeyS2(f.Filter05, f.filter05);
	if (i == 6) return SV_KeyS2(f.Filter06, f.filter06);
	if (i == 7) return SV_KeyS2(f.Filter07, f.filter07);
	return SV_KeyS2(f.Filter08, f.filter08);
};

// Forward-declared for the recursion: 42 sub-filter references in the library
// are themselves a filter_multi.
float(entity f, entity act, float depth) SV_FilterPassesD;

float(entity f, entity act, float depth) SV_FilterPassesD =
{
	local float pass, i, n, isor, sub;
	local string nm;
	local entity c;

	if (!f)
		return TRUE;						// no such filter -- Source passes

	if (f.classname == "filter_activator_name")
	{
		pass = (act.targetname == f.filtername);
		if (SV_Key2(f.Negated, f.negated))
			pass = !pass;
		return pass;
	}

	if (f.classname == "filter_multi")
	{
		/*
		  A cycle in the graph would recurse forever, and nothing in a BSP
		  stops a mapper pointing two filter_multis at each other.  Four is
		  past the deepest chain the library actually contains and cheap
		  enough that the guard costs nothing to be generous with.
		*/
		if (depth > 4)
			return TRUE;

		isor = f.filtertype;
		n = 0;
		// AND starts true and is cleared by a failure; OR starts false and is
		// set by a success.  Source's CFilterMultiple does exactly this.
		pass = !isor;

		for (i = 1; i <= 8; i = i + 1)
		{
			nm = SV_MultiSub(f, i);
			if (nm == "")
				continue;
			n = n + 1;
			c = SV_FindByName(nm, world);
			sub = SV_FilterPassesD(c, act, depth + 1);
			if (isor)
			{
				if (sub)
					pass = TRUE;
			}
			else if (!sub)
				pass = FALSE;
		}

		/*
		  A filter_multi naming nothing.  One instance in the library has zero
		  sub-filters, and an empty OR would otherwise evaluate to FALSE and
		  block every activator -- a filter that blocks everything is never what
		  an empty one means, and it is the wrong direction to guess in.
		*/
		if (!n)
			return TRUE;

		if (SV_Key2(f.Negated, f.negated))
			pass = !pass;
		return pass;
	}

	return TRUE;							// censused by the caller -- fail open
};

float(entity f, entity act) SV_FilterPasses =
{
	return SV_FilterPassesD(f, act, 0);
};

float(entity trig, entity act) SV_PassesFilter =
{
	local entity f;

	if (trig.filtername == "")
		return TRUE;

	// vbsp_entity_io gates the map's WIRING, and a filter is wiring: it is the
	// half of the mechanism that reads the name, and AddOutput is the half that
	// writes it.  Gating only one of the two would leave the switch in a state
	// neither build has ever been in -- names never written, but still tested --
	// which is a worse thing to bisect against than either end.
	if (!vbsp_io_on)
		return TRUE;

	// Resolved once and cached.  It cannot be resolved at spawn time: spawn
	// functions run DURING the entity parse, so a filter declared later in the
	// lump does not exist yet -- futile's filters follow their triggers.
	if (!trig.vbsp_filterdone)
	{
		trig.ui_filter = SV_FindByName(trig.filtername, world);
		trig.vbsp_filterdone = TRUE;

		// Build 51 adds filter_multi to the implemented set, so it must come out
		// of the "not implemented" report as well -- a census that still names a
		// class this file now evaluates is worse than no census.
		if (trig.ui_filter)
		if (trig.ui_filter.classname != "filter_activator_name")
		if (trig.ui_filter.classname != "filter_multi")
			if (SV_CensusAdd(strcat("filter ", trig.ui_filter.classname)))
				dprint(sprintf("^3filter: %s is not implemented -- '%s' passes "
				               "everything\n", trig.ui_filter.classname,
				               trig.filtername));
	}

	f = trig.ui_filter;
	return SV_FilterPasses(f, act);
};

void() filter_activator_name =
{
	// A point entity holding two strings.  Nothing to draw, nothing to touch;
	// it exists only to be found by name.
	self.solid = SOLID_NOT;
	self.movetype = MOVETYPE_NONE;
};

/*
  Build 51.  Without this the entity is a point entity with no '*' model, so
  SV_OnEntityNoSpawnFunction removes it -- and a removed filter is exactly the
  fail-open that SV_FilterPassesD is written to replace.  The predicate above
  can only run if the entity is still there to be found by name.
*/
void() filter_multi =
{
	self.solid = SOLID_NOT;
	self.movetype = MOVETYPE_NONE;
};

/*
  INPUTS.

  The set below is what these two maps actually use, plus the Enable/Disable
  family, which is worth having for its own sake: StartDisabled has been a
  one-way door on every class that reads it, because nothing could ever turn
  one back on.

  An unrecognised input is CENSUSED rather than dropped in silence, through the
  same machinery `ent_census` already prints.  The next missing input is then
  one console line instead of another play session.
*/
/*
  Trim.  Not cosmetic: surf_kitsune CLEARS the player's name with
  `AddOutput "targetname  "` -- the key, a space, and then nothing but spaces.
  Split naively that assigns a name of " " rather than "", and a one-space
  targetname is a name: it is not equal to "", so it would survive every
  emptiness test in this file and could still be matched by a filter.

  32 rather than ' ' because a single-quoted literal in QuakeC is vector
  syntax, and ' ' is an empty vector rather than the space character.
*/
string(string s) SV_IOTrim =
{
	local float a, b;

	a = 0;
	b = strlen(s);
	while (a < b && str2chr(s, a) <= 32)
		a = a + 1;
	while (b > a && str2chr(s, b - 1) <= 32)
		b = b - 1;
	return substring(s, a, b - a);
};

void(entity t, string param) SV_IOAddOutput =
{
	local string k, v;
	local float  sp;

	sp = strstrofs(param, " ", 0);
	if (sp < 0)
		return;
	k = SV_IOTrim(substring(param, 0, sp));
	v = SV_IOTrim(substring(param, sp + 1, -1));

	/*
	  CASE.  Source matches a keyvalue name with `stricmp`
	  (saverestore_gamedll.cpp:46), so `basevelocity`, `Basevelocity` and
	  `BaseVelocity` are the same key.  This compared with `==` and was
	  therefore reading only the first spelling.

	  It is not a hypothetical: of the library's 2004 AddOutput-basevelocity
	  outputs, 1835 say `basevelocity`, 164 say `Basevelocity` and 5 say
	  `BaseVelocity` -- 8.4% missed, and missed WHOLE MAPS, because a mapper
	  picks one spelling and uses it everywhere.  surf_breach, surf_strike and
	  surf_inferno are capital-B throughout and lost every boost on the map.
	*/
	k = strtolower(k);

	/*
	  `targetname` is the one that matters, and it is the whole of bhop_futile.

	  The map renames the PLAYER as they progress -- block1, block2, ... -- and
	  each platform's reset teleport carries a filter that passes only for the
	  NEXT block's name.  That is its anti-backtrack: standing on block 1 while
	  named nothing fails the filter and you are left alone; coming back to it
	  after reaching block 2 passes, and you are sent to the start.  33 of
	  futile's 38 outputs are this one input.
	*/
	if (k == "targetname")
	{
		t.targetname = v;
		return;
	}

	/*
	  FTESurf Patch 256.  `gravity` -- 2239 outputs across 208 of the 1310 maps,
	  three times the next unimplemented key, and the field was already wired
	  end to end and never once written.

	  It is a MULTIPLIER on sv_gravity, not absolute units.  Source:
	  baseentity.cpp DEFINE_KEYFIELD( m_flGravity, FIELD_FLOAT, "gravity" ) ->
	  gamemovement.cpp:3110-3117 `ent_gravity = player->GetGravity(); if
	  (ent_gravity == 0.0f) ent_gravity = 1.0f; velocity.z -= ent_gravity *
	  GetCurrentGravity() * frametime`.  FTE's `.gravity` is the same quantity
	  with the same guard -- progdefs.h calls it "Multiplier applied in addition
	  to sv_gravity", pm_source.c does the identical zero-means-one test -- and
	  the engine already networks it (svc_entgravity), already ships
	  STAT_MOVEVARS_ENTGRAVITY, and already feeds it back into movevars for
	  client prediction.  So this is one assignment, not a feature.

	  ALWAYS !activator IN PRACTICE: all 2239 outputs target !activator, carried
	  by OnStartTouch 1009 / OnEndTouch 735 / OnTrigger 465 / OnJump 21 /
	  OnEndTouchAll 4, and the owner is a trigger_multiple on 2138 of them.

	  1441 of the writes are exactly `1` -- the restore -- across 207 maps, and
	  797 are something else across 138.  So 70 maps only ever write 1 and have
	  been accidentally correct all along; surf_4am is one of them, which is why
	  its warning was cosmetic.  Values in use: 1, -1 (64 maps), -0.5, 40, 0.5,
	  -2, -3, -0.75, 0.25, 0.0001, 0.000001.  Negative works -- only exact zero
	  is special-cased on either side -- so `gravity -1` really is inverted
	  gravity, which is what those 64 maps are asking for.

	  `gravity 40` (217 outputs / 10 maps) is the one I cannot read the intent
	  of: as a multiplier that is 40x, which is enormous but not absurd for a
	  kill-floor.  Taking Source's semantics literally is the defensible choice
	  and it is what happens here; it is written down so the next person who
	  finds a map that falls through the world has somewhere to start.

	  SV_PutClientInServer resets this.  A multiplier written by a map and left
	  on the player is the same class of bug as .run_speedmod, and 0.25 carried
	  into the next map is moon gravity that no cvar explains.
	*/
	if (k == "gravity")
	{
		t.gravity = stof(v);
		return;
	}

	/*
	  `basevelocity` -- 2004 outputs across 298 of the 1310 maps, and the reason
	  engine Patch 240 exists.  A pad is typically a trigger_multiple carrying

	      OnJump  !activator,AddOutput,basevelocity 0 0 1140,0,-1

	  so the target is the PLAYER, not the trigger -- AddOutput has always been
	  able to write to !activator, this is just the first input that wants to.

	  THE PARAGRAPH THAT USED TO BE HERE WAS WRONG, and it is worth saying how
	  rather than just deleting it.  It read StartGravity's

	      velocity[2] += basevelocity[2] * frametime;   basevelocity[2] = 0;

	  concluded that Z is an acceleration, and therefore that `0 0 1140` is
	  worth about 17 u/s at a 15 ms tick -- "the pads therefore boost, but
	  barely, and they would do exactly the same in Source".  They would not.
	  StartGravity never sees an AddOutput write: CheckMovingGround cashes the
	  whole vector out into velocity at the top of the same tick, because this
	  path does not set FL_BASEVELOCITY.  The full essay is at .run_basevel.

	  So this is a LAUNCH, and `0 0 1140` means 1148.5 u/s.

	  IT IS A SET OF ALL THREE COMPONENTS, never an add: Source's
	  UTIL_StringToVector (util_shared.cpp:916-946) parses up to three floats
	  and ZERO-FILLS the ones it did not reach.  `basevelocity 0 0 650` clears
	  X and Y as a side effect, and 14 outputs in the library write fewer than
	  three components -- "basevelocity 450", "basevelocity 500 0", and one
	  un-substituted Hammer instance parameter, "Basevelocity boostAmountY
	  1100".  Those are not errors to reject; Source zero-fills them, so
	  "basevelocity 450" is a 450 u/s push along +X.  Counted, because a
	  sideways launch from a value that reads like a height is exactly the kind
	  of thing someone will later report as a bug in this code.
	*/
	if (k == "basevelocity")
	{
		// Not stov, for the reason cl_decals.qc:227 gives: the value is a bare
		// "x y z" and tokenize says exactly what it parsed.  Safe here even
		// though tokenize writes one global buffer -- the record list was
		// tokenised at BUILD time into fields (SV_EntityIOBuild) and nothing
		// upstream of this call is holding argv at fire time.
		local float nv;
		nv = tokenize(v);
		if (nv >= 3)
			t.run_basevel = [stof(argv(0)), stof(argv(1)), stof(argv(2))];
		else if (nv == 2)
			t.run_basevel = [stof(argv(0)), stof(argv(1)), 0];
		else if (nv == 1)
			t.run_basevel = [stof(argv(0)), 0, 0];
		else
			return;

		if (nv < 3)
			if (SV_CensusAdd("AddOutput basevelocity (short)"))
				dprint(sprintf("^3entity I/O: 'basevelocity %s' has %g of 3 "
				               "components; zero-filled, as Source does\n", v, nv));

		run_bv_set_n = run_bv_set_n + 1;
		if (run_bv_debug)
			print(sprintf("basevel: SET %s on %s (write %g)\n",
			              vtos(t.run_basevel), t.classname, run_bv_set_n));
		return;
	}

	if (SV_CensusAdd(strcat("AddOutput ", k)))
		dprint(sprintf("^3entity I/O: AddOutput '%s' is not implemented\n", k));
};

void(entity t, float on) SV_IOEnable =
{
	if (!on)
	{
		// Remember what it was before the first Disable, so Enable can restore
		// a trigger as SOLID_BSPTRIGGER rather than flattening it to SOLID_BSP.
		if (t.solid != SOLID_NOT && !t.vbsp_io_solid)
			t.vbsp_io_solid = t.solid;
		t.solid = SOLID_NOT;
		t.effects = t.effects | EF_NODRAW;
		// Patch 280: a non-solid slide must not wear the tag (see SKIN_SLIDE_BASE).
		if (t.vbsp_slide_skin)
			t.skin = 0;
	}
	else
	{
		if (t.model != "" && substring(t.model, 0, 1) == "*")
			t.solid = t.vbsp_io_solid ? t.vbsp_io_solid : SOLID_BSP;
		t.effects = t.effects - (t.effects & EF_NODRAW);
		if (t.vbsp_slide_skin && t.solid != SOLID_NOT)
			t.skin = t.vbsp_slide_skin;
	}

	// Both spellings are read everywhere else through SV_Key2, so both are
	// written here; leaving the other one set would re-disable on the next read.
	t.StartDisabled = t.startdisabled = !on;

	/*
	  Patch 256.  A logic_timer stops its own think when it finds itself
	  disabled, so Enable has to start it again -- otherwise Disable is
	  permanent and the 220 maps that toggle a timer get one shot at it.
	  Narrowed to the classname on purpose: several classes here carry thinks
	  with their own scheduling (SV_TriggerEndThink's 0.02 dwell, the door
	  movers) and a blanket re-arm would trample them.
	*/
	if (on && t.classname == "logic_timer")
		t.nextthink = time + SV_TimerInterval(t);
};

/*
  `Command` is remote code execution by map, so it is allow-listed.

  A map that can run console commands can set sv_airaccelerate, and this game's
  leaderboard is a physics claim.  That is not hypothetical: bhop_futile's
  logic_auto fires `server,Command,sv_airaccelerate 150` at map spawn.

  Blocking it costs futile NOTHING, and that is checkable rather than hoped
  for -- cfg/mode_bhop.cfg already sets sv_airaccelerate 1000 for every bhop
  map, and Patch 170's movement lock reverts any live write to a locked cvar
  anyway.  So the map's own line was already being undone twice over; this just
  makes the refusal deliberate and visible instead of incidental.

  bhop_arcane's six Commands are all `say Secret N Found` and all run.
*/
void(string cmd) SV_IOCommand =
{
	local string w;
	local float  sp;

	sp = strstrofs(cmd, " ", 0);
	w = (sp < 0) ? cmd : substring(cmd, 0, sp);

	if (w == "say" || w == "echo" || w == "print")
	{
		localcmd(strcat(cmd, "\n"));
		return;
	}

	if (SV_CensusAdd(strcat("blocked command ", w)))
		dprint(sprintf("^3entity I/O: refused map command '%s' -- only say/echo/"
		               "print are allowed\n", cmd));
};

void(entity t, entity act, float v) SV_IOModifySpeed =
{
	local entity p;

	// Source applies this to the ACTIVATOR (CPlayerSpeedMod sets the touching
	// player's lagged-movement value), not to the player_speedmod itself.
	p = (act.classname == "player") ? act : t;
	if (p.classname != "player")
		return;
	if (v <= 0)
		v = 1;
	p.run_speedmod = v;
};

/*
  math_counter, for arcane's five secrets.

  Cosmetic -- OnHitMax is wired to `say All secrets found!` -- but it is the
  only thing on either map that exercises a DELAYED output (the say has a
  delay of 1), and a counter that fires an output is the smallest complete
  test of the layer feeding itself.

  `max` reaches this through ED_ParseUnknownEpair, because `.float max;` does
  not compile -- see the hook's own note.

  BUILD 63 COMPLETES IT, and this is the one change in the build with a real
  regression surface, so the size of it is written down rather than discovered.

  Source's CMathCounter::UpdateOutValue (logicentities.cpp:1728-1779) gates the
  whole limit block on (min != 0 || max != 0), latches BOTH edges in
  m_bHitMin/m_bHitMax, fires OnHitMin at the bottom, and -- the part that is new
  behaviour -- CLAMPS the value into range afterwards.

  The edge latch and the old `wasbelow` agree on every counter with max > 0 and
  min 0, which is every counter that could reach the old code, so that half is a
  superset rather than a change.  THE CLAMP IS NOT.  Censused across all 1315
  maps: of 546 math_counters in the library, 505 across 112 maps write a
  non-zero `max` (only 43 across 12 write a non-zero `min`).  Every one of those
  505 could previously run past its maximum and now sticks there.  That is
  Source's behaviour and it is why a counter has a maximum at all -- but it is
  the reason this went in its own commit, and the reason it wants a real
  before/after on bhop_arcane and surf_ny_platinum rather than a smoke test.

  NOT fired: OutValue, OnChangedFromMin and OnChangedFromMax.  OutValue is a
  COutputFloat whose entire purpose is carrying the value, and this layer has no
  parameter pass-through -- see the note at `getvalue` in SV_ApplyInput.
*/
void(entity t, float v, float fire) SV_IOCounter =
{
	if (t.vbsp_io_min == 0 && t.vbsp_io_max == 0)
	{
		// No limits declared: nothing to latch and nothing to clamp against.
		t.count = v;
		return;
	}

	if (fire)
	{
		if (v >= t.vbsp_io_max)
		{
			if (!t.vbsp_io_hitmax)
			{
				t.vbsp_io_hitmax = TRUE;
				SV_FireOutput(t, "OnHitMax", world);
			}
		}
		else
			t.vbsp_io_hitmax = FALSE;

		if (v <= t.vbsp_io_min)
		{
			if (!t.vbsp_io_hitmin)
			{
				t.vbsp_io_hitmin = TRUE;
				SV_FireOutput(t, "OnHitMin", world);
			}
		}
		else
			t.vbsp_io_hitmin = FALSE;
	}

	// SetValueNoFire clamps too -- it suppresses the outputs, not the limits
	// (InputSetValueNoFire, logicentities.cpp:1673).
	t.count = bound(t.vbsp_io_min, v, t.vbsp_io_max);
};

/*
  Does this entity declare an output by this (folded) name, with fires left?

  Source asks exactly this question in two places and both matter later:
  CLogicCase::BuildCaseMap tests m_OnCase[i].NumberOfElements() > 0 to decide
  which cases PickRandom may choose (logicentities.cpp:2349-2366), and
  CLogicRelay::Activate tests m_OnSpawn the same way to decide whether a
  once-only relay consumes itself at map spawn (logicrelay.cpp:55-62).  Neither
  is an optimisation; in both the answer CHANGES BEHAVIOUR.

  `name` must already be folded -- vbsp_io_name is stored that way by
  SV_EntityIOBuild, so callers pass a lowercase literal and no strtolower
  happens per output.
*/
float(entity e, string name) SV_IOHasOutput =
{
	local entity o;

	for (o = e.vbsp_io_out; o; o = o.vbsp_io_next)
		if (o.vbsp_io_name == name)
		if (o.vbsp_io_times != 0)			// -1 unlimited, 0 exhausted
			return TRUE;
	return FALSE;
};

/*
===========================================================================
  THE KNOWN-OUTPUT LIST, lifted out of SV_EntityIOBuild.

  The essay that used to sit around the literal chain down there applies to this
  function verbatim, and it is why the chain moved rather than merely grew:

      "THIS LIST IS HAND-MAINTAINED AND NOTHING TIES IT TO THE FIRE SITES.
       Adding a SV_FireOutput call without adding its name here makes the check
       cry wolf; adding a name here without a fire site makes it lie the other
       way and is worse, because the silence then reads as 'implemented'."

  That remains exactly true.  What changed is that the chain was eight lines of
  `&&`-joined `!=` tests, and the work this build starts roughly doubles the
  name count -- logic_case alone contributes sixteen.  A forty-term boolean is
  not something anyone can check against the fire sites by eye, and checking it
  by eye is the ONLY thing keeping it honest.  So it became a readable function
  with one name per line and a comment naming each fire site.

  ONE CORRECTION TO THE OLD ESSAY while moving it.  It claimed "there are as
  many names here as there are SV_FireOutput call sites in this file, and that
  correspondence is the only thing keeping it honest."  That was already not
  true: 19 names against 23 call sites, because OnStartTouch fires from three
  sites, OnEndTouch from three and OnTimer from two.  The invariant that is
  actually checkable, and the one to hold to, is the weaker pair:

      every name below has AT LEAST ONE SV_FireOutput call site, and
      every SV_FireOutput call site's name appears below.

===========================================================================
*/
float(string lk) SV_IOOutputKnown =
{
	// Build 37.
	if (lk == "onmapspawn")   return TRUE;	// SV_EntityIOBuild, logic_auto
	if (lk == "onnewgame")    return TRUE;	// SV_EntityIOBuild, logic_auto
	if (lk == "onstarttouch") return TRUE;	// SV_TriggerIOTouch (x2 paths)
	if (lk == "onendtouch")   return TRUE;	// SV_TriggerEndThink (x3 paths)
	if (lk == "ontrigger")    return TRUE;	// trigger_multiple_touch
	if (lk == "onpressed")    return TRUE;	// SV_UseFrame
	if (lk == "onhitmax")     return TRUE;	// SV_IOCounter
	if (lk == "onactivate")   return TRUE;	// SV_BhopTeleport
	if (lk == "onusefinished")return TRUE;	// SV_UseFrame
	if (lk == "onlandinglimitreached") return TRUE;	// SV_BhopFrame
	if (lk == "onjump")       return TRUE;	// SV_TriggerIOTouch
	if (lk == "onland")       return TRUE;	// SV_TriggerIOTouch -- build 51

	// Patch 256.
	if (lk == "onstarttouchall") return TRUE;	// SV_TriggerIOTouch
	if (lk == "onendtouchall")   return TRUE;	// SV_TriggerEndThink
	if (lk == "onlockeduse")     return TRUE;	// SV_UseFrame
	if (lk == "onpass")          return TRUE;	// TestActivator, SV_ApplyInput
	if (lk == "onfail")          return TRUE;	// TestActivator, SV_ApplyInput
	if (lk == "ontimer")         return TRUE;	// SV_TimerThink, and FireTimer

	// Build 63.
	if (lk == "onspawn")      return TRUE;	// SV_EntityIOBuild, logic_relay
	if (lk == "ondefault")    return TRUE;	// SV_IOCaseValue
	if (lk == "ontrue")       return TRUE;	// SV_IOBranch
	if (lk == "onfalse")      return TRUE;	// SV_IOBranch
	if (lk == "onequalto")    return TRUE;	// SV_IOCompare
	if (lk == "onnotequalto") return TRUE;	// SV_IOCompare
	if (lk == "ongreaterthan")return TRUE;	// SV_IOCompare
	if (lk == "onlessthan")   return TRUE;	// SV_IOCompare
	if (lk == "onhitmin")     return TRUE;	// SV_IOCounter
	if (lk == "ongetvalue")   return TRUE;	// SV_ApplyInput, getvalue
	if (lk == "ontimerhigh")  return TRUE;	// SV_TimerFire, oscillator
	if (lk == "ontimerlow")   return TRUE;	// SV_TimerFire, oscillator
	if (lk == "ontouching")   return TRUE;	// SV_ApplyInput, touchtest
	if (lk == "onnottouching")return TRUE;	// SV_ApplyInput, touchtest
	if (lk == "onuser1")      return TRUE;	// SV_ApplyInput, fireuser1
	if (lk == "onuser2")      return TRUE;	// SV_ApplyInput, fireuser2
	if (lk == "onuser3")      return TRUE;	// SV_ApplyInput, fireuser3
	if (lk == "onuser4")      return TRUE;	// SV_ApplyInput, fireuser4

	/*
	  Build 63, Tier 2.  Button and door STATE.

	  DELIBERATELY ABSENT, and this is the half of the list that needs saying
	  out loud rather than being inferred from what is here:

	    onfullyopen / onfullyclosed  are claims about where a brush IS, and
	      nothing in this build moves one.  func_movelinear's 818 OnFullyOpen
	      across 63 maps stay censused, correctly.
	    ondamaged / onbreak          have no possible fire site in a game with
	      no damage system -- see the essay in SV_UseFrame.
	*/
	if (lk == "onin")         return TRUE;	// SV_ButtonAtTop
	if (lk == "onout")        return TRUE;	// SV_ButtonHome
	if (lk == "onuselocked")  return TRUE;	// SV_MoverOnUseLocked
	if (lk == "onopen")       return TRUE;	// SV_DoorOpen
	if (lk == "onclose")      return TRUE;	// SV_DoorClose

	/*
	  logic_case's sixteen, as one prefix test rather than sixteen literals --
	  which is most of why this function exists at all.

	  The length and range tests are not decoration: without them "oncasexx" or
	  "oncase99" would be accepted as known and silently lose their warning,
	  and SV_IOCaseName only ever produces oncase01..oncase16.
	*/
	if (strlen(lk) == 8)
	if (substring(lk, 0, 6) == "oncase")
	if (stof(substring(lk, 6, 2)) >= 1)
	if (stof(substring(lk, 6, 2)) <= MAX_LOGIC_CASES)
		return TRUE;						// SV_IOCasePick / SV_IOCaseValue

	return FALSE;
};

/*
===========================================================================
  logic_relay -- Build 63, and it is the largest unimplemented input in the
  library that is not cosmetic.

  2,506 Trigger inputs across 120 maps aim at one, and until now the class was
  a spawn stub with a comment saying so (see logic_relay below).  A relay is a
  pass-through: whatever fires its Trigger makes it fire OnTrigger, which is
  what lets a map fan one event out to several targets, or put a delay in the
  middle, or gate a chain behind an Enable.

  CLogicRelay, logicrelay.cpp.
===========================================================================
*/
void() SV_RelayRefireThink =
{
	self.vbsp_relay_wait = FALSE;
	self.nextthink = 0;
};

void(entity t, entity act) SV_IORelayTrigger =
{
	local entity o;
	local float  maxdelay;

	// m_bDisabled, which is StartDisabled -- see the field note.
	if (SV_Key2(t.StartDisabled, t.startdisabled))
		return;
	if (t.vbsp_relay_wait)
		return;

	/*
	  THE FLAG IS SET BEFORE THE FIRE, AND SOURCE SETS IT AFTER.

	  That is not a transcription slip; it is the one place this layer's
	  architecture differs from Source's, and the difference is load-bearing.

	  CLogicRelay::InputTrigger (logicrelay.cpp:136-158) calls
	  m_OnTrigger.FireOutput() and THEN sets m_bWaitForRefire.  That ordering is
	  safe there only because FireOutput does not deliver anything -- it queues
	  into g_EventQueue, which is serviced later, by which time the flag is
	  already true.

	  SV_FireOutput delivers a zero-delay output INLINE, on this stack.  Keeping
	  Source's order would mean a relay wired `OnTrigger <self> Trigger`
	  re-entered here with the flag still clear, and 120 maps carry a relay --
	  each one line in Hammer away from a QC stack overflow, which on a lobby
	  is not a dead map but a dead server process (see VBSP_IO_MAXDEPTH).

	  For every wiring that is NOT a cycle this is observationally identical to
	  Source, because the flag can only be read again from inside the fire.
	*/
	if (t.spawnflags & SF_RELAY_REMOVE_ON_FIRE)
	{
		/*
		  "Only trigger once".  Source calls UTIL_Remove (logicrelay.cpp:145).
		  Latching Disabled instead is observationally the same -- a disabled
		  relay forwards nothing -- and avoids remove()ing an entity from
		  inside SV_FireOutput's own walk of that entity's output chain, which
		  is the one thing the capture-nx dance up there cannot survive.  It
		  also keeps the entity findable, so ent_info and ent_census still show
		  what the map declared.
		*/
		SV_IOEnable(t, FALSE);
	}
	else if (!(t.spawnflags & SF_RELAY_FAST_RETRIGGER))
	{
		/*
		  The lockout runs until the last output has been sent --
		  m_OnTrigger.GetMaxDelay() + 0.001 (logicrelay.cpp:152).  Walked rather
		  than cached in a field: Trigger is fired 2,506 times in the whole
		  library and a relay carries a handful of outputs, so the walk is free,
		  and AddOutput can extend a chain after any cache would have been built.
		*/
		maxdelay = 0;
		for (o = t.vbsp_io_out; o; o = o.vbsp_io_next)
			if (o.vbsp_io_name == "ontrigger")
			if (o.vbsp_io_delay > maxdelay)
				maxdelay = o.vbsp_io_delay;

		t.vbsp_relay_wait = TRUE;
		t.think     = SV_RelayRefireThink;
		t.nextthink = time + maxdelay + 0.001;
	}

	SV_FireOutput(t, "OnTrigger", act);
};

/*
  CancelPending -- 244 fires across 13 maps.

  Source's g_EventQueue.CancelEvents(this) is CALLER-keyed (eventqueue.h:25/82),
  and CLogicRelay::InputCancelPending (logicrelay.cpp:106-112) also clears the
  refire wait.  Our pending deliveries are the vbsp_iodelay edicts SV_FireOutput
  spawns, whose .owner is the OUTPUT and whose output's .owner is the source --
  so "fired by t" is exactly d.owner.owner == t.
*/
void(entity t) SV_IOCancelPending =
{
	local entity d, nx;

	for (d = find(world, classname, "vbsp_iodelay"); d; d = nx)
	{
		nx = find(d, classname, "vbsp_iodelay");	// captured BEFORE the remove
		if (d.owner)
		if (d.owner.owner == t)
			remove(d);
	}
	t.vbsp_relay_wait = FALSE;
};

/*
===========================================================================
  logic_case -- Build 63, and the single largest dead output family in the
  library: 6,258 OnCase01..OnCase16 outputs across 112 maps.

  CLogicCase, logicentities.cpp:2204-2430.  See the field block for why none of
  this needs a per-entity array.
===========================================================================
*/
// "oncase07".  Built rather than sprintf'd with a %02g, because the zero pad on
// a %g conversion is not a thing to rely on across fteqcc versions and
// vbsp_io_name is compared as a plain folded string.
string(float idx) SV_IOCaseName =
{
	return strcat("oncase", (idx < 10) ? "0" : "", ftos(idx));
};

/*
  One bit per case, 1..16 -> bits 0..15.  This is CLogicCase's m_uchShuffleCaseMap
  and its nNumCases in ONE int field instead of two 16-byte arrays.
*/
int(entity t) SV_IOCaseWired =
{
	local int   m;
	local float i;

	m = 0;
	for (i = 1; i <= MAX_LOGIC_CASES; i = i + 1)
		if (SV_IOHasOutput(t, SV_IOCaseName(i)))
			m = m | (1 << (i - 1));
	return m;
};

void(entity t, entity act, float shuffle) SV_IOCasePick =
{
	local int   wired, avail;
	local float i, n, pick;

	wired = SV_IOCaseWired(t);
	if (!wired)
		return;						// nothing wired: Source picks nothing either

	avail = wired;
	if (shuffle)
	{
		/*
		  PickRandomShuffle, logicentities.cpp:2396-2430.  Spend each wired case
		  once before any repeats; when the batch empties, refill -- and on the
		  refill avoid repeating the case that ended the last batch, so a
		  shuffle cannot hand out the same case twice across the seam.  That is
		  Source's m_nLastShuffleCase, expressed as one bit clear rather than an
		  array swap.
		*/
		avail = wired & ~t.vbsp_case_shuf;
		if (!avail)
		{
			t.vbsp_case_shuf = 0;
			avail = wired;
			if (t.vbsp_case_last >= 1)
			if (avail & ~(1 << (t.vbsp_case_last - 1)))	// unless it is the only one
				avail = avail & ~(1 << (t.vbsp_case_last - 1));
		}
	}

	// Uniform over the set bits, without an array to index.
	n = 0;
	for (i = 0; i < MAX_LOGIC_CASES; i = i + 1)
		if (avail & (1 << i))
			n = n + 1;
	if (!n)
		return;

	pick = floor(random() * n);
	if (pick >= n)
		pick = n - 1;				// random() may return exactly 1.0
	for (i = 0; i < MAX_LOGIC_CASES; i = i + 1)
		if (avail & (1 << i))
		{
			if (!pick)
				break;
			pick = pick - 1;
		}

	if (shuffle)
	{
		t.vbsp_case_shuf = t.vbsp_case_shuf | (1 << i);
		t.vbsp_case_last = i + 1;
	}
	SV_FireOutput(t, SV_IOCaseName(i + 1), act);
};

void(entity t, string want, entity act) SV_IOCaseValue =
{
	local string rec, idx, val;
	local float  p0, pn, ptab, hit;

	hit = FALSE;
	p0  = 0;
	while (1)
	{
		pn = strstrofs(t.vbsp_case_raw, "\n", p0);
		if (pn < 0)
			break;
		rec = substring(t.vbsp_case_raw, p0 + 1, pn - p0 - 1);	// skip the lead \t
		p0  = pn + 1;

		ptab = strstrofs(rec, "\t", 0);
		if (ptab < 0)
			continue;
		idx = substring(rec, 0, ptab);
		val = substring(rec, ptab + 1, -1);

		/*
		  Source matches with Matcher_Match (logicentities.cpp:2330), a
		  case-insensitive compare that ALSO honours '*' wildcards.

		  THE WILDCARD IS NOT IMPLEMENTED, AND THAT IS MEASURED RATHER THAN
		  OVERLOOKED: across all 1315 maps, not one Case value in the library
		  contains a '*'.  If one ever does it falls to OnDefault, which is the
		  safe direction.

		  Numbers are compared as numbers as well as as strings, so that "1" and
		  "1.0" agree -- which is what a mapper wiring a math_counter into a
		  logic_case means.  Guarded so that stof()'s 0-for-junk does not make
		  every non-numeric value match every other one.
		*/
		if (!strcasecmp(val, want) ||
		    (val != "" && want != "" && stof(val) == stof(want) &&
		     (stof(val) != 0 || val == "0" || want == "0")))
		{
			SV_FireOutput(t, SV_IOCaseName(stof(idx)), act);
			hit = TRUE;
			// MultipleCasesAllowed defaults off, so Source stops at the first
			// match (logicentities.cpp:2334-2339).
			break;
		}
	}

	if (!hit)
		SV_FireOutput(t, "OnDefault", act);
};

/*
===========================================================================
  logic_branch and logic_compare -- Build 63.

  A branch stores one boolean and, when TESTED, says which way it points:
  OnTrue 562 outputs, OnFalse 149, across 20 maps.  A compare stores two floats
  and says how they relate: OnEqualTo 96, OnGreaterThan 78, OnLessThan 70,
  OnNotEqualTo 8, across 20 maps.  Neither class had a spawn function before
  this build, so the catch-all deleted both and every one of those outputs
  resolved to nothing.

  The distinction that matters in both classes, and the reason each has two
  near-identical inputs: SetValue STORES WITHOUT TESTING and SetValueTest stores
  and then tests (CLogicBranch::InputSetValue at logicentities.cpp:2723 vs
  InputSetValueTest; CLogicCompare::InputSetValue at :2538 vs
  InputSetValueCompare).  A map uses the silent one to arrange state and the
  testing one to act on it, so collapsing them would fire outputs at moments the
  map deliberately kept quiet.
===========================================================================
*/
void(entity t, float nv, float fire, entity act) SV_IOBranch =
{
	t.vbsp_branch_val = nv ? TRUE : FALSE;
	if (!fire)
		return;
	if (t.vbsp_branch_val)
		SV_FireOutput(t, "OnTrue",  act);
	else
		SV_FireOutput(t, "OnFalse", act);
};

void(entity t, entity act) SV_IOCompare =
{
	// CLogicCompare::DoCompare, logicentities.cpp:2585-2613.  Equal wins
	// outright; otherwise exactly one of greater/less fires, and OnNotEqualTo
	// fires ALONGSIDE it rather than instead of it -- which is why this is not
	// an if/else chain all the way down.
	if (t.vbsp_cmp_in == t.vbsp_cmp_cmp)
	{
		SV_FireOutput(t, "OnEqualTo", act);
		return;
	}

	SV_FireOutput(t, "OnNotEqualTo", act);
	if (t.vbsp_cmp_in > t.vbsp_cmp_cmp)
		SV_FireOutput(t, "OnGreaterThan", act);
	else
		SV_FireOutput(t, "OnLessThan", act);
};

void(entity t, entity o, entity act) SV_ApplyInput =
{
	local string in, pm;

	in = o.vbsp_io_input;
	pm = o.vbsp_io_param;
	vbsp_io_fired = vbsp_io_fired + 1;

	/*
	  Input names are case-insensitive in Source: AcceptInput compares with
	  `stricmp` against the datadesc's externalName (baseentity.cpp:3887).
	  Three outputs in the library spell it `AddOutPut`, and one of them is a
	  basevelocity boost.  Matching on the canonical spellings below after a
	  fold costs one string per delivery and cannot mis-match, because no two
	  Source inputs differ only by case.
	*/
	in = strtolower(in);

	if (in == "addoutput")      { SV_IOAddOutput(t, pm);                return; }
	if (in == "kill")           { remove(t);                            return; }
	if (in == "enable")         { SV_IOEnable(t, TRUE);                 return; }
	if (in == "disable")        { SV_IOEnable(t, FALSE);                return; }
	/*
	  TOGGLE, AND THE TWO DIFFERENT THINGS IT MEANS.

	  This line has meant one thing since build 37 -- flip a brush entity's
	  solidity -- and it is the most-declared input in the library, so the
	  existing expression is NOT touched: it stays, unchanged, as the
	  fall-through, and the new meaning is added above it by classname.

	  THE HEADLINE NUMBER IS A TRAP AND IT IS WORTH SPENDING A PARAGRAPH ON,
	  because it argues the opposite of what it looks like.  A census of all
	  1315 maps counts 401,491 declared Toggles -- but 401,072 of those are ONE
	  map, bhop_miku_v2, whose single logic_relay drives a song's worth of
	  func_wall_toggle animation, and which cannot load at all (see
	  VBSP_IO_MAXOUT).  Take it out and the real figure is 419 across 65 maps,
	  of which 201 still target func_wall_toggle, where today's line is exactly
	  right.  Only 68 reach a logic_relay, on 3 maps.

	  WHY THE CLASSNAME ARM CANNOT REGRESS ANYTHING, said exactly.

	  SV_SpawnIOPoint spawns every logic point entity SOLID_NOT with no model,
	  and nothing ever changes that, so for all of them `t.solid == SOLID_NOT`
	  is PERMANENTLY TRUE and today's line already resolves to
	  SV_IOEnable(t, TRUE) every single time.  Walk what that does to a modelless
	  point entity: the solid restore is gated on the model starting with '*' so
	  .solid is untouched; the EF_NODRAW clear is a no-op on something with
	  nothing to draw; and all it actually writes is StartDisabled = 0.

	  So Toggle on a point entity has been an unconditional ENABLE since build
	  37 -- never a toggle.  For logic_relay that write was observable by
	  nothing at all, because the class read StartDisabled nowhere.

	  logic_timer is the one real behaviour change, and it is a bug fix:
	  SV_TimerThink DOES read StartDisabled, so Toggle could start a timer and
	  never stop one, against CTimerEntity::Toggle (logicentities.cpp:351-361)
	  which flips.  Censused before shipping rather than argued about: ONE fire,
	  on ONE map (surf_era), in the whole library.
	*/
	if (in == "toggle")
	{
		if (t.classname == "logic_relay" || t.classname == "logic_timer")
		{
			SV_IOEnable(t, !SV_Key2(t.StartDisabled, t.startdisabled));
			return;
		}
		// A branch's Toggle flips its stored boolean WITHOUT testing it --
		// CLogicBranch::InputToggle, the silent twin of ToggleTest.  26 fires
		// across 5 maps, none of which could reach this before build 63.
		if (t.classname == "logic_branch")
		{
			SV_IOBranch(t, !t.vbsp_branch_val, FALSE, act);
			return;
		}
		SV_IOEnable(t, t.solid == SOLID_NOT);
		return;
	}
	if (in == "command")        { SV_IOCommand(pm);                     return; }
	if (in == "modifyspeed")    { SV_IOModifySpeed(t, act, stof(pm));   return; }
	if (in == "setdamagefilter"){ t.vbsp_dmgfilter = pm;                  return; }
	if (in == "add")            { SV_IOCounter(t, t.count + stof(pm), TRUE);  return; }
	/*
	  SETVALUE IS THE SECOND COLLISION, and unlike Toggle nobody had it on a
	  list -- it surfaced only from reading the FGD against this ladder.  Three
	  classes declare the name and mean three different things: math_counter
	  sets its counter (and has owned this line since build 37), logic_branch
	  sets its boolean WITHOUT testing it (logicentities.cpp:2723), logic_compare
	  stores its input value without comparing (:2538).

	  Same dispatch as Toggle, and safe for the same reason plus a stronger one:
	  neither logic_branch nor logic_compare exists as an edict before this
	  build, so the new arms are unreachable on every map that works today.

	  The lesson, worth more than the fix: a new input name has to be grepped
	  against this whole ladder, not checked against the names someone flagged.
	*/
	if (in == "setvalue")
	{
		if (t.classname == "logic_branch")
			{ SV_IOBranch(t, stof(pm) != 0, FALSE, act); return; }
		if (t.classname == "logic_compare")
			{ t.vbsp_cmp_in = stof(pm);                  return; }
		SV_IOCounter(t, stof(pm), TRUE);
		return;
	}
	if (in == "setvaluenofire") { SV_IOCounter(t, stof(pm), FALSE);     return; }

	// Build 63.  The rest of CMathCounter.  Divide's count is not a typo: one
	// output, on one map, implemented because the divide-by-zero guard
	// (logicentities.cpp:1615-1638) is the whole of what it needs.
	if (in == "subtract") { SV_IOCounter(t, t.count - stof(pm), TRUE);  return; }
	if (in == "multiply") { SV_IOCounter(t, t.count * stof(pm), TRUE);  return; }
	if (in == "divide")
	{
		// Source logs a level-design error and re-runs the update with the value
		// UNCHANGED -- which still evaluates the edges, so it is not a no-op.
		if (stof(pm) != 0) SV_IOCounter(t, t.count / stof(pm), TRUE);
		else               SV_IOCounter(t, t.count,            TRUE);
		return;
	}
	if (in == "getvalue")
	{
		/*
		  71 fires / 5 maps, 39 OnGetValue outputs.  KNOWN GAP, stated here
		  rather than left to look finished: Source's m_OnGetValue is a
		  COutputFloat and InputGetValue (logicentities.cpp:1708-1712) SETS it,
		  i.e. the counter's value is substituted into any output whose own
		  parameter field is blank.  This layer has no parameter pass-through --
		  an output carries only what the map wrote -- so this fires at the right
		  moment with the wrong (usually empty) parameter.

		  Firing it is still strictly better than not: a map that uses
		  GetValue purely as a "now" signal works, and one that needs the number
		  is no worse off than when nothing fired at all.  Threading an override
		  through SV_FireOutput/SV_IODeliver/SV_ApplyInput is the next piece of
		  work and it is bigger than this line looks.
		*/
		SV_FireOutput(t, "OnGetValue", act);
		return;
	}
	if (in == "sethitmax")
	{
		t.vbsp_io_max = stof(pm);
		if (t.vbsp_io_max < t.vbsp_io_min)
			t.vbsp_io_min = t.vbsp_io_max;		// logicentities.cpp:1559
		SV_IOCounter(t, t.count, TRUE);
		return;
	}
	if (in == "sethitmin")
	{
		t.vbsp_io_min = stof(pm);
		if (t.vbsp_io_max < t.vbsp_io_min)
			t.vbsp_io_max = t.vbsp_io_min;		// logicentities.cpp:1569
		SV_IOCounter(t, t.count, TRUE);
		return;
	}
	if (in == "turnoff")        { t.effects = t.effects | EF_NODRAW;    return; }
	if (in == "turnon")         { t.effects = t.effects - (t.effects & EF_NODRAW); return; }

	// Build 63.  logic_relay -- 2,506 Trigger fires across 120 maps, the most
	// common unimplemented input in the library that is not cosmetic.
	if (in == "trigger")        { SV_IORelayTrigger(t, act);            return; }
	if (in == "cancelpending")  { SV_IOCancelPending(t);                return; }

	// Build 63.  logic_case -- 6,258 OnCaseNN outputs across 112 maps, the
	// largest dead output family in the library.  PickRandom is 1,142 of the
	// 1,243 fires; InValue is 101.
	if (in == "invalue")           { SV_IOCaseValue(t, pm, act);        return; }
	if (in == "pickrandom")        { SV_IOCasePick(t, act, FALSE);      return; }
	if (in == "pickrandomshuffle") { SV_IOCasePick(t, act, TRUE);       return; }

	// Build 63.  logic_branch -- OnTrue 562 / OnFalse 149 across 20 maps.
	// `setvalue` is up with the counter group because it collides there; these
	// three are unambiguous.  Test re-fires the CURRENT value without changing
	// it (CLogicBranch::InputTest).
	if (in == "setvaluetest") { SV_IOBranch(t, stof(pm) != 0,       TRUE, act); return; }
	if (in == "toggletest")   { SV_IOBranch(t, !t.vbsp_branch_val,  TRUE, act); return; }
	if (in == "test")         { SV_IOBranch(t, t.vbsp_branch_val,   TRUE, act); return; }

	// Build 63.  logic_compare -- OnEqualTo 96 / OnGreaterThan 78 /
	// OnLessThan 70 / OnNotEqualTo 8 across 20 maps.  Note SetCompareValue
	// stores silently while SetValueCompare tests: the asymmetry is Source's.
	if (in == "setvaluecompare") { t.vbsp_cmp_in  = stof(pm); SV_IOCompare(t, act); return; }
	if (in == "setcomparevalue") { t.vbsp_cmp_cmp = stof(pm);                       return; }
	if (in == "compare")         { SV_IOCompare(t, act);                           return; }

	/*
	  Build 63.  FireUser1..4 -- and the thing to notice is that this is NOT a
	  classname.  It is CBaseEntity (baseentity.cpp:6655-6670), so it works on
	  anything, which is exactly what makes it useful: a map forwards a message
	  through !activator to a target the sender knows nothing about.  278
	  FireUser1 fires across 25 maps against 523 OnUser1 outputs, so most of
	  those outputs hang off entities told to fire by something else entirely.

	  It is also this build's easiest accidental cycle -- `OnUser1 !self
	  FireUser1` is one line in Hammer, on ANY classname -- which is the other
	  half of why VBSP_IO_MAXDEPTH is not optional.
	*/
	/*
	  Build 63, Tier 2.  Button and door STATE inputs.

	  Gated on vbsp_mv_kind rather than on classname: it is one float compare
	  instead of a ladder of string compares in a function that runs on every
	  delivery, it is the same test that keeps the breakable aliases out (see
	  SV_SpawnBreakable), and an input aimed at something that is not a mover
	  falls through to the census rather than doing something surprising --
	  which is the rule the firetimer block above already follows.

	  `Use` is NOT here, and that is a measured decision rather than an
	  oversight: 1,154 of its 1,408 fires across 129 maps target
	  game_player_equip, Source's weapon handout, which this game has no use
	  for.  Only 3 fires in the whole library reach anything else.  It stays
	  censused.
	*/
	if (t.vbsp_mv_kind)
	{
		if (in == "lock")     { SV_MoverLock(t, TRUE);                    return; }
		if (in == "unlock")   { SV_MoverLock(t, FALSE);                   return; }

		if (t.vbsp_mv_kind == MVK_BUTTON)
		{
			if (in == "press")    { SV_ButtonPress(t, act, BUTTON_PRESS);    return; }
			if (in == "pressin")  { SV_ButtonPress(t, act, BUTTON_ACTIVATE); return; }
			if (in == "pressout") { SV_ButtonPress(t, act, BUTTON_RETURN);   return; }
		}
		if (t.vbsp_mv_kind == MVK_DOOR)
		{
			if (in == "open")  { SV_DoorOpen(t, act);  return; }
			if (in == "close") { SV_DoorClose(t, act); return; }
		}
	}

	if (in == "fireuser1") { SV_FireOutput(t, "OnUser1", act); return; }
	if (in == "fireuser2") { SV_FireOutput(t, "OnUser2", act); return; }
	if (in == "fireuser3") { SV_FireOutput(t, "OnUser3", act); return; }
	if (in == "fireuser4") { SV_FireOutput(t, "OnUser4", act); return; }

	/*
	  FTESurf Patch 256.  TestActivator -- and this is the input that makes
	  OnPass possible, which is not where anyone looks for it.

	  `nothing fires 'OnPass'` reads like a missing fire site inside the filter
	  test, and it is not: Source's CBaseFilter::PassesFilter (filters.cpp:46-50)
	  is a PURE PREDICATE that fires nothing at all.  m_OnPass and m_OnFail are
	  fired only from the two explicit input handlers --

	      CBaseFilter::InputTestActivator (filters.cpp:69-79)
	          if (PassesFilter(pCaller, pActivator)) m_OnPass.FireOutput(...);
	          else                                   m_OnFail.FireOutput(...);

	  -- declared at filters.cpp:28-29.  So a filter is inert until something
	  ASKS it, and asking is what we could not do.

	  742 TestActivator inputs exist across 20 maps and about 661 of them target
	  a filter that declares OnPass; it is the 27th most common input name in the
	  library.  surf_solace alone sends 394.

	  SCOPE, said plainly so the headline number is not misread later: the
	  library has 1543 OnPass outputs, but 968 of them belong to path_track and
	  74+32+23+13+8 more to filter classes we fail open on.  This closes the
	  425 on filter_activator_name.  path_track's are a func_tracktrain mechanic
	  that does not exist here at all and this is not a step towards it.

	  `t` is the filter (the output's target), `act` the activator being tested,
	  which is the same pairing Source passes as (pCaller, pActivator).
	*/
	/*
	  Patch 256: logic_timer's own inputs (logicentities.cpp, CTimerEntity).
	  FireTimer fires now and restarts the interval; ResetTimer restarts it
	  without firing; RefireTime changes it.  All three are no-ops on anything
	  that is not a timer, which is why they test the think rather than the
	  classname -- a map that aims FireTimer at the wrong entity should do
	  nothing rather than something surprising.
	*/
	if (in == "firetimer")
	{
		/*
		  Build 63 routes this through SV_TimerFire so an oscillator's FireTimer
		  fires the same output its own think would, and adopts Source's
		  disabled gate: CTimerEntity::FireTimer (logicentities.cpp:366-370)
		  is `if (!m_iDisabled)`, and this branch was not.

		  That gate can only change behaviour on a map that Disables a timer and
		  then sends it FireTimer, so it was censused rather than argued about:
		  across all 1315 maps, FireTimer is 20 fires on 12 maps, Disable-at-a-
		  timer is 217 on 74, and only THREE maps do both -- surf_ethereal,
		  surf_liberation and bhop_angst.  Those three are where to look if a
		  one-shot stops working.
		*/
		if (t.think == SV_TimerThink)
		if (!SV_Key2(t.StartDisabled, t.startdisabled))
		{
			SV_TimerFire(t);
			t.nextthink = time + SV_TimerInterval(t);
		}
		return;
	}
	if (in == "resettimer")
	{
		if (t.think == SV_TimerThink) t.nextthink = time + SV_TimerInterval(t);
		return;
	}
	if (in == "refiretime")
	{
		t.RefireTime = stof(pm);
		if (t.think == SV_TimerThink) t.nextthink = time + SV_TimerInterval(t);
		return;
	}

	if (in == "testactivator")
	{
		if (SV_FilterPasses(t, act)) SV_FireOutput(t, "OnPass", act);
		else                         SV_FireOutput(t, "OnFail", act);
		return;
	}

	/*
	  Build 63.  TouchTest, put here rather than with the logic entities because
	  it is the exact structural mirror of TestActivator above -- and the essay
	  there is the one a reader will already have in view.

	  Same shape, same reason: CBaseTrigger's m_OnTouching and m_OnNotTouching
	  (triggers.cpp:119-120) are fired ONLY from InputTouchTest (:150-153 ->
	  TouchTest, :241-252).  A trigger is inert until something ASKS it, and
	  asking is what we could not do.  74 OnTouching and 11 OnNotTouching
	  outputs across 32 maps.

	  Our equivalent of Source's m_hTouchingEntities is Patch 270's per-player
	  masks plus the legacy single-toucher.  ONE FIDELITY GAP, stated because it
	  is not visible from here: those masks are swept on a 0.03s think with a
	  two-window absence test (see SV_TriggerEndThink), so a player who left
	  less than ~0.09s ago still reads as inside, where Source's set is exact.
	  On 32 maps that is the right trade.

	  Source passes the trigger as both caller and activator here, so the fire
	  names `t` rather than `act`.
	*/
	if (in == "touchtest")
	{
		if (SV_Key2(t.StartDisabled, t.startdisabled))
			return;						// a disabled trigger touches nothing
		if (t.vbsp_touch_in || t.vbsp_touch_seen || t.vbsp_touch_who)
			SV_FireOutput(t, "OnTouching",    t);
		else
			SV_FireOutput(t, "OnNotTouching", t);
		return;
	}

	/*
	  SetFogController -- the map moving THIS player onto a different
	  env_fog_controller.  Source fires it at !activator from a trigger's
	  OnStartTouch with the controller's targetname as the parameter, and by the
	  time we are here SV_ApplyInput has already resolved !activator to the
	  player edict and put that name in `pm`.  It was the single most common
	  unimplemented input in the library: 54 maps fire it 397 times.

	  The server does not need the controller entity at all -- it is a point
	  entity with no model, so it is removed at spawn like every other one, and
	  the CLIENT holds the parameters from its own read of the entity lump.  All
	  that crosses the wire is the name, on a per-player string stat.

	  Deliberately NOT a stuffcmd("fog ..."): that runs at RESTRICT_SERVER, which
	  makes the engine latch cl.fog_locked, and from then on the player's own
	  vbsp_fog toggle is refused -- silently.  See STAT_FS_FOGCTRL in sh_defs.qc.
	*/
	if (in == "setfogcontroller")
	{
		if (t.classname == "player")
			t.run_fogctrl = pm;
		return;
	}

	// Cosmetic and deliberately no-ops: honouring them would mean a render
	// pipeline these entities do not have.  Named rather than censused so the
	// census keeps meaning "nobody has looked at this".
	if (in == "color" || in == "alpha")
		return;

	// Censused under the MAP'S spelling, not the folded one -- the census is
	// read by someone about to go looking for the name in the FGD.
	vbsp_io_fired = vbsp_io_fired - 1;
	if (SV_CensusAdd(strcat("input ", o.vbsp_io_input)))
		dprint(sprintf("^3entity I/O: input '%s' is not implemented (fired at "
		               "%s)\n", o.vbsp_io_input, t.classname));
};

void(entity o, entity act) SV_IODeliver =
{
	local entity t;
	local string tn;

	tn = o.vbsp_io_target;

	if (tn == "!activator" || tn == "!caller" || tn == "!player")
	{
		if (act)
			SV_ApplyInput(act, o, act);
		return;
	}
	if (tn == "!self")
	{
		if (o.owner)
			SV_ApplyInput(o.owner, o, act);
		return;
	}
	if (tn == "")
		return;

	t = SV_FindByName(tn, world);
	if (!t)
	{
		/*
		  A target that resolves to nothing.  For `Command` that is normal and
		  not an error: futile aims at `server`, which is Source's console sink
		  rather than an entity, and arcane aims at `servercommand`, a
		  point_servercommand this build removes on sight.  Both mean the same
		  thing, so both land in the allow-list.
		*/
		if (strtolower(o.vbsp_io_input) == "command")
			SV_IOCommand(o.vbsp_io_param);
		return;
	}

	// Source fires an input at EVERY entity carrying the targetname.
	while (t)
	{
		SV_ApplyInput(t, o, act);
		t = SV_FindByName(tn, t);
	}
};

// A delayed output.  Two entity references and a think; removed before it
// delivers, so a delivery that removes things cannot leave this behind.
void() SV_IODelayThink =
{
	local entity o, a;

	o = self.owner;
	a = self.enemy;
	remove(self);
	if (o)
		SV_IODeliver(o, a);
};

void(entity src, string name, entity act) SV_FireOutput =
{
	local entity o, nx, d;

	name = strtolower(name);	//Patch 256 -- see the fold note in the loop

	/*
	  Build 63.  The fuse.  See the essay beside VBSP_IO_MAXDEPTH for why a
	  refusal rather than an error, and what the engine does if this is absent.

	  Bracketing works here without restructuring because this function has
	  exactly ONE exit path: the loop below contains `continue` but no `return`,
	  so the decrement at the tail cannot be skipped.  Check that before adding
	  an early return to this function -- a fuse that leaks is worse than no
	  fuse, because it bricks the map's I/O after enough unrelated fires rather
	  than failing loudly.
	*/
	if (vbsp_io_depth >= VBSP_IO_MAXDEPTH)
	{
		vbsp_io_depth_hit = vbsp_io_depth_hit + 1;
		if (SV_CensusAdd(strcat("output cycle ", name)))
			dprint(sprintf("^1entity I/O: '%s' on %s exceeded %g nested fires -- "
			               "this map has an output cycle; refusing to recurse\n",
			               name, src.classname, VBSP_IO_MAXDEPTH));
		return;
	}
	vbsp_io_depth = vbsp_io_depth + 1;
	if (vbsp_io_depth > vbsp_io_depth_max)
		vbsp_io_depth_max = vbsp_io_depth;

	for (o = src.vbsp_io_out; o; o = nx)
	{
		// Captured first: an input may remove entities, and `Kill` on the
		// source would otherwise leave this walking a freed chain.
		nx = o.vbsp_io_next;

		/*
		  FTESurf Patch 256.  Output names fold too.  Source resolves an output
		  name through the same datadesc lookup as everything else, which is
		  stricmp (saverestore_gamedll.cpp:46) -- the argument SV_ApplyInput
		  already makes for INPUT names one function up.  vbsp_io_name is stored
		  folded by SV_EntityIOBuild, so this is a comparison against a folded
		  literal and costs one strtolower per call, not per output.

		  Small but total where it bites: surf_paranoid_enigma writes
		  `Onstarttouch` on five teleports and every one of them was dead.
		*/
		if (o.vbsp_io_name != name)
			continue;
		if (o.vbsp_io_times == 0)
			continue;					// -1 is unlimited; 0 is exhausted

		/*
		  Build 63.  THE DECREMENT MOVED ABOVE THE DELIVERY, and it is a real bug
		  fix rather than tidying.

		  It used to sit after the SV_IODeliver below.  For a ZERO-DELAY output
		  that delivery is inline, on this stack, and it can re-enter
		  SV_FireOutput on this same source and walk this same chain -- with
		  vbsp_io_times not yet decremented.  So a relay wired `OnTrigger <self>
		  Trigger` and declared `times 1`, which is exactly what a mapper writes
		  to BOUND it, recursed without limit anyway: the one guard the map
		  author was given did not work.

		  Latent until now only because logic_relay was a stub and nothing
		  re-entered.  Decrementing first makes the count mean what the map says
		  it means, and it is what lets the fuse above stay a backstop rather
		  than the only thing standing between a map and SV_Error.

		  Order against the delay path is unchanged: a delayed output is spent
		  when it is SCHEDULED, which is what Source does too -- the event is in
		  the queue and cancelling it is CancelPending's job, not a refire
		  count's.
		*/
		if (o.vbsp_io_times > 0)
			o.vbsp_io_times = o.vbsp_io_times - 1;

		if (o.vbsp_io_delay > 0)
		{
			d = spawn();
			d.classname = "vbsp_iodelay";
			d.owner = o;
			d.enemy = act;
			d.think = SV_IODelayThink;
			d.nextthink = time + o.vbsp_io_delay;
		}
		else
			SV_IODeliver(o, act);
	}

	vbsp_io_depth = vbsp_io_depth - 1;
};

/*
===========================================================================
  END TOUCH, which QuakeC does not have.

  Source's CBaseTrigger fires OnStartTouch when you enter and OnEndTouch when
  you LEAVE.  QuakeC has one .touch, called every tick you are inside, and
  nothing at all for leaving.

  bhop_futile needs the one QuakeC lacks: 27 of its 33 renames are on
  OnEndTouch, because you become "block2" by LEAVING block 1.

  So end-touch is synthesised.  The touch stamps the toucher and the time, and
  a think a few ticks later notices the stamp has gone stale and fires
  OnEndTouch.  The grace matters in both directions -- too short and one
  dropped frame fires a spurious end-touch mid-platform, too long and a fast
  player is renamed after they have already landed on the next block.  0.05 s
  is five ticks at bhop's 100 Hz and three at surf's 66.7, and .touch is called
  on every one of them.

  IT COSTS NOTHING ON A TRIGGER WITH NO OUTPUTS, which is all but a handful in
  a 1,308-map library: the first line returns before any state is written and
  no think is ever armed.  That is what keeps this off the hot path of the
  4,940 trigger_push and 17,000-odd trigger_teleport entities that wire
  nothing.

  ONE TOUCHER AT A TIME, deliberately.  Per-player-per-trigger state would need
  an array this codebase has no home for, and every map here is played by one
  player; a second player entering the same trigger takes over the stamp rather
  than corrupting it.  Stated rather than hidden, because it is the first thing
  that would need revisiting for real multiplayer.
===========================================================================
*/
void() SV_TriggerEndThink =
{
	local entity a;
	local int    gone, bit, absent;
	local float  i;

	/*
	  PATCH 270, STAGE 2 -- the per-player sweep, ahead of the legacy path
	  because on a lobby it is the only one that runs.

	  "Left" is defined as absent for one whole sweep window rather than by a
	  timestamp, for the reason given at the field declarations: a mask has
	  nowhere to put 32 timestamps.  gone = was-inside AND not-seen-since.

	  OnEndTouchAll fires ONLY when the trigger empties, which is Source's
	  actual rule (CBaseTrigger::EndTouch sweeps m_hTouchingEntities at
	  triggers.cpp:449-475 and fires m_OnEndTouchAll only when nothing is left).
	  The one-toucher code fired it after every OnEndTouch because with one
	  toucher those are the same event; with several they are not, and only 10
	  of the 555 OnEndTouchAll owners declare both outputs, so this is a visible
	  change on ten entities and a correction on all of them.
	*/
	if (self.vbsp_touch_in || self.vbsp_touch_seen)
	{
		/*
		  Two windows, not one -- see the essay at the field declarations for
		  the regression the one-window version was.

		    absent  did not touch during the window just ended
		    out     was absent for the PREVIOUS window too
		    gone    absent for both, so >= 2 sweeps ~ 0.06 s: end it
		*/
		absent = self.vbsp_touch_in & ~self.vbsp_touch_seen;
		gone   = absent & self.vbsp_touch_out;
		self.vbsp_touch_out = absent & ~gone;
		a = world;

		if (gone)
		{
			for (i = 0; i < 32; i = i + 1)
			{
				bit = (int)1 << (int)i;
				if (!(gone & bit))
					continue;
				// +1: the mask is edict-number-minus-one, see SV_TouchBit.
				a = edict_num(i + 1);
				SV_FireOutput(self, "OnEndTouch", a);
			}
		}

		/*
		  A bit that is absent but not yet `gone` STAYS in vbsp_touch_in, and
		  that is what restores the other half of build 51's behaviour: a
		  player who re-touches inside the grace is still recorded as inside,
		  so the entry test in SV_TriggerIOTouch does not fire a second
		  OnStartTouch at them.  It is exactly what vbsp_touch_who staying set
		  used to do.
		*/
		self.vbsp_touch_in   = (self.vbsp_touch_in | self.vbsp_touch_seen) & ~gone;
		self.vbsp_touch_seen = 0;

		// Emptied on this sweep.  `a` is the last player out, which is the
		// activator Source passes for the same reason.
		if (gone && !self.vbsp_touch_in)
			SV_FireOutput(self, "OnEndTouchAll", a);
	}

	if (self.vbsp_touch_who && time - self.vbsp_touch_when > 0.05)
	{
		a = self.vbsp_touch_who;
		self.vbsp_touch_who = world;
		SV_FireOutput(self, "OnEndTouch", a);
		/*
		  FTESurf Patch 256.  OnEndTouchAll, and it is one line BECAUSE of the
		  one-toucher design documented above rather than in spite of it.

		  Source keeps m_hTouchingEntities and fires m_OnEndTouchAll from
		  CBaseTrigger::EndTouch (triggers.cpp:481) only once the sweep at
		  :449-475 finds no other toucher left.  We track exactly one toucher,
		  so "the last one left" and "the one left" are the same event and the
		  correct place to fire it is right here, immediately after OnEndTouch.

		  555 outputs across 40 maps, and it is not a duplicate of OnEndTouch:
		  only 10 of the 555 owning entities declare BOTH, so on 545 of them
		  this is the map's ONLY leave notification and firing OnEndTouch
		  instead would have been wrong rather than merely redundant.
		  Concentrated -- surf_funhouse_v1 alone has 202.
		*/
		SV_FireOutput(self, "OnEndTouchAll", a);
	}

	/*
	  Only think while somebody is inside.  A map with 1122 brush entities
	  cannot afford a per-frame think on every trigger that ever fired.

	  TWO RATES, and the split is so that vbsp_mp 0 is build 51 to the frame.
	  0.03 is the window the per-player grace is quantised in; 0.02 is what the
	  legacy timestamp path has always polled at.  When only the legacy state is
	  live it keeps its own number, so the control arm of the A/B is not a
	  slightly different thing.  With both live -- which needs more than 32
	  clients, or vbsp_mp flipped mid-map -- the masks win, and the legacy
	  path's `> 0.05` test is unchanged either way.
	*/
	if (self.vbsp_touch_in || self.vbsp_touch_seen)
		self.nextthink = time + 0.03;
	else if (self.vbsp_touch_who)
		self.nextthink = time + 0.02;
	else
		self.nextthink = 0;
};

void(entity trig, entity act) SV_TriggerIOTouch =
{
	local int bit;

	if (!trig.vbsp_io_out)
		return;

	bit = SV_TouchBit(act);
	if (bit)
	{
		/*
		  PATCH 270, STAGE 2.  Entry is "not currently recorded inside, by
		  either half of the sweep state" -- `in` is last sweep's answer and
		  `seen` is this window's, and a player who has already touched this
		  window is in `seen` but not yet in `in`.  Testing only `in` would
		  re-fire OnStartTouch on every frame until the next sweep.
		*/
		if (!((trig.vbsp_touch_in | trig.vbsp_touch_seen) & bit))
		{
			/*
			  OnStartTouchAll fires only on the FIRST entrant, which is the
			  same correction Patch 270 made on the exit side and it has to be
			  made on both or the pair stops bracketing.  Source's rule
			  (CBaseTrigger::StartTouch, triggers.cpp:422) is that
			  m_OnStartTouchAll fires when m_hTouchingEntities goes from empty
			  to one; with a single toucher "the first" and "every" were the
			  same event, which is why the one-toucher code fired it
			  unconditionally.  116 entities declare it.
			*/
			SV_FireOutput(trig, "OnStartTouch", act);
			if (!(trig.vbsp_touch_in | trig.vbsp_touch_seen))
				SV_FireOutput(trig, "OnStartTouchAll", act);
		}
		trig.vbsp_touch_seen = trig.vbsp_touch_seen | bit;
	}
	else
	{
		// vbsp_mp 0, or a client above the 32nd slot.  Build 51 exactly.
		if (trig.vbsp_touch_who != act)
		{
			trig.vbsp_touch_who = act;
			SV_FireOutput(trig, "OnStartTouch", act);
			SV_FireOutput(trig, "OnStartTouchAll", act);
		}
		trig.vbsp_touch_when = time;
	}

	/*
	  OnJump -- fired when the player jumps while inside the trigger.  Build 37's
	  static output check reported this as the one output nothing fires, and it
	  is bhop_futile's six booster pads: a trigger_multiple with

	      OnJump  !activator,AddOutput,basevelocity 0 0 <650..1140>,0,-1

	  THE DETECTION IS PRE-MOVE STATE COMPARED WITH POST-MOVE STATE, and the
	  ordering is what makes it exact rather than a command late.  Within one
	  SV_RunCmd the engine runs PlayerPreThink, then the move, then this touch
	  loop, then PlayerPostThink.  PlayerPreThink stamps run_wasground from the
	  flags as they stood BEFORE the move; here, after it, a player who was on
	  the ground, is not now, and is moving up has jumped on this very command.

	  Leaving the ground by walking off a ledge fails the velocity test, and
	  being launched by something else fails the wasground test on every command
	  after the first, so this does not fire continuously while airborne.
	*/
	if ((act.run_wasground) && !(act.flags & FL_ONGROUND) && act.velocity_z > 0)
	{
		if (run_bv_debug)
			print(sprintf("basevel: OnJump from %s vz %.0f\n", trig.model, act.velocity_z));
		SV_FireOutput(trig, "OnJump", act);
	}

	/*
	  BUILD 51: OnLand, which is OnJump read backwards and shares its whole
	  mechanism -- was airborne before the move, is grounded after it.

	  2302 outputs across 7 maps, every one of them on a trigger_multiple:
	  bhop_pharma 1206, bhop_badges_mini 789, bhop_orgrimmar 204, surf_rez 72,
	  bhop_bowling 26, bhop_ragequit 3, bhop_aberrant 2.  What they do is almost
	  entirely renaming the player so the next trigger in the chain sees a
	  different targetname -- AddOutput targetname activator 723,
	  AddOutput targetname default 636, RemoveContext _mom_leftground 758 -- so
	  on those maps this output IS the progression logic, not decoration.

	  NO VELOCITY TEST, unlike OnJump.  Its jump test needs velocity_z > 0 to
	  tell a jump from walking off a ledge, because both leave the ground.
	  Landing has no such twin: there is only one way to acquire FL_ONGROUND.

	  THE EDGE IT CANNOT DISTINGUISH is a frame where the mover drops and
	  regains the flag without the player ever having been airborne -- stepping
	  up, or a moving surface pulling away and catching up.  run_wasground is
	  stamped PRE-move and the flag is read POST-move, so a step-up that clears
	  and restores the flag inside a single move is invisible here and does not
	  fire; only a move that BEGINS airborne can.  The residual risk is a
	  platform that genuinely un-grounds you for one whole command, which on
	  these seven maps re-runs an idempotent rename.
	*/
	if (!(act.run_wasground) && (act.flags & FL_ONGROUND))
		SV_FireOutput(trig, "OnLand", act);

	if (trig.nextthink <= 0)
	{
		trig.think = SV_TriggerEndThink;
		trig.nextthink = time + 0.02;
	}
};

/*
  +USE, so that a func_button is a button.

  `.float button5` has been declared in this file since build 1, with an essay
  about which usercmd bit +use lands on under QuakeWorld, and NOTHING HAS EVER
  READ IT.  Until entity I/O existed there was nothing for a press to do.

  surf_kitsune is why it is here now rather than later, and it is a regression
  this build would otherwise have introduced: its `SecretTeleporter` carries
  StartDisabled 1 and is switched on by a func_button's
  `OnPressed SecretTeleporter Enable` (and off again three seconds later).
  Before this build FTESurf ignored StartDisabled on a teleport, so the secret
  was permanently ON -- wrong, but reachable.  Honouring StartDisabled without
  honouring the button would have made it permanently OFF, which is wrong in
  the harder direction: a secret nobody can reach and no message to say why.

  80 units is Source's PLAYER_USE_RADIUS.  The trace is from the EYE along
  .v_angle, which is where the player is actually looking -- .angles on a
  player is the model's orientation and has the pitch scaled to a third (see
  the .v_angle essay in trigger_teleport_touch).
*/
#define PM_USE_RANGE 80

//FTESurf Patch 256.  doors.h:33.  Declared here rather than beside
//SF_DOOR_NONSOLID_TO_PLAYER because SV_UseFrame is compiled before SV_SpawnDoor
//and QC resolves defines in file order.
#define SF_DOOR_LOCKED 2048

.float vbsp_lastuse;

void(entity pl) SV_UseFrame =
{
	local vector src;
	local entity t;

	if (!pl.button5)
	{
		pl.vbsp_lastuse = FALSE;
		return;
	}
	if (pl.vbsp_lastuse)
		return;						// held down; a press is an edge, not a state
	pl.vbsp_lastuse = TRUE;

	if (!vbsp_io_on)
		return;

	makevectors(pl.v_angle);
	src = pl.origin + pl.view_ofs;
	traceline(src, src + v_forward * PM_USE_RANGE, FALSE, pl);

	t = trace_ent;
	if (!t || t == world)
		return;
	if (!t.vbsp_io_out)
		return;						// nothing wired to it; not a button

	/*
	  FTESurf Patch 256.  OnLockedUse -- a locked door telling the map that
	  somebody tried it.

	  Source, CBaseDoor::Use (doors.cpp:759-762):

	      if (bAllowUse) {
	          if (m_bLocked) { m_OnLockedUse.FireOutput(pActivator, pCaller); ... }
	          else DoorActivate();
	      }

	  m_bLocked comes from SF_DOOR_LOCKED (2048) at spawn (doors.cpp:290-292),
	  and bAllowUse is true whenever the door is at the bottom, i.e. closed
	  (doors.cpp:747/753) -- which is the state SV_SpawnDoor freezes every door
	  in, so the guard is satisfied by construction here.  prop_door_rotating
	  has the identical output on CBasePropDoor (props.cpp:3539).

	  All 23 in the library carry SF_DOOR_LOCKED at spawn, so we do not need
	  the Lock/Unlock inputs to fire it correctly for any of them.  6 maps;
	  surf_centipedes has 12, surf_bossfight 3.

	  BUILD 63 ENDS THAT, and the paragraph above is left standing because it
	  says exactly what stopped being true.  Lock and Unlock now exist, so
	  "they all carry the spawnflag at spawn" is no longer the same statement as
	  "they are locked": InputUnlock clears m_bLocked and leaves the spawnflag
	  set forever (doors.cpp:882-885).  Reading spawnflags here would report an
	  unlocked door as locked from the first Unlock onward.  The test below is
	  now vbsp_mv_locked, which SV_SpawnDoor seeds from the flag and
	  SV_MoverLock maintains.

	  Two more things this function got wrong, both surfaced by Tier 2:

	  THE SF_DOOR_PUSE GATE.  CBaseDoor::Use refuses a player activator outright
	  unless spawnflag 256 is set (doors.cpp:731-735), BEFORE it even computes
	  bAllowUse -- so we were firing at doors Source would not have looked at.
	  Its FGD default is OFF, which made honouring it look like it might silence
	  real maps, so it was censused rather than guessed: of the 20 doors in the
	  library declaring OnLockedUse, NINETEEN already set bit 256.  Honouring it
	  costs exactly one door, on one map.

	  AND OnPressed WAS FIRED AT ANYTHING WITH OUTPUTS -- doors, triggers,
	  logic_relays -- because the old body's only test was `trace_ent has a
	  vbsp_io_out chain`.  A button's press is now routed through
	  SV_ButtonUse so the toggle / stay-pushed / already-moving guards apply and
	  OnIn and OnOut follow it; a door's through SV_DoorUse.  Everything else
	  keeps the old behaviour, because for a func_brush or a trigger wired to
	  OnPressed that behaviour is all there is.

	  WHAT STILL CANNOT WORK, so the census keeps meaning "nobody has looked at
	  this": OnDamaged.  It is func_button's second largest dead output -- 1,187
	  outputs across 32 maps -- and Source fires it from CBaseButton::OnTakeDamage
	  (buttons.cpp:309) under the "Damage activates" spawnflag.  This game has
	  no damage system and no weapons: sv_player.qc sets takedamage DAMAGE_NO on
	  the player and nothing anywhere calls T_Damage.  There is no honest fire
	  site, so `ondamaged` is deliberately NOT in SV_IOOutputKnown -- adding a
	  name there without a fire site is the failure that essay calls the worse
	  one, because silence then reads as "implemented".  func_breakable's
	  OnBreak (276) is dead for the same reason.

	  FOUR OF THE 23 ARE UNREACHABLE and that is worth saying rather than
	  discovering later: they also carry the passable spawnflags, so SV_SpawnDoor
	  makes them SOLID_NOT and this traceline goes straight through them.  They
	  stay silent until doors get a touch path (Source fires the same output
	  from DoorTouch, doors.cpp:654, under SF_DOOR_PTOUCH).

	  Fired BEFORE OnPressed and returning, because in Source a locked door does
	  not activate -- firing both would report a press that never happened.
	*/
	if (t.vbsp_mv_kind == MVK_DOOR)
	{
		SV_DoorUse(t, pl);
		return;
	}
	if (t.vbsp_mv_kind == MVK_BUTTON)
	{
		if (!(t.spawnflags & SF_BUTTON_USE))
			return;					// buttons.cpp:422-429 SetUse(NULL) without it
		SV_ButtonUse(t, pl);
		return;
	}

	/*
	  prop_door_rotating keeps the old spawnflag path: it has the identical
	  output on CBasePropDoor (props.cpp:3539) but is a MODEL entity here, not a
	  brush, so it never went through SV_SpawnDoor and has no vbsp_mv_kind.
	*/
	if (t.classname == "prop_door_rotating")
	if (t.spawnflags & SF_DOOR_LOCKED)
	{
		SV_FireOutput(t, "OnLockedUse", pl);
		return;
	}

	SV_FireOutput(t, "OnPressed", pl);
	SV_FireOutput(t, "OnUseFinished", pl);
};

/*
  Materialise every captured output into an vbsp_output entity.

  Runs from StartFrame's first-frame-after-worldspawn hook, next to
  SV_RepairTargetCase, for the reason that hook exists at all: StartFrame is
  called BEFORE the map's entities exist, so anything earlier walks an empty
  world.

  The records are walked with strstrofs rather than tokenised, because the
  VALUE has to be tokenised too and tokenizebyseparator writes one global
  buffer -- a nested call would clobber the record list mid-loop.  That is the
  kind of bug that produces a partial parse and no error.
*/
void() SV_EntityIOBuild =
{
	local entity e, o, tail;
	local string rec, k, v, sep, lk;
	local float  p0, pn, ptab, ntok;

	// Latched, not read per touch: SV_PassesFilter runs on every trigger touch
	// of every frame, and a cvar lookup there would be the only cost this layer
	// imposes on the 1,300 maps that wire nothing.
	vbsp_io_on = cvar("vbsp_entity_io");
	if (!vbsp_io_on)
		return;

	vbsp_io_esc = chr2str(27);

	for (e = nextent(world); e; e = nextent(e))
	{
		if (e.vbsp_io_raw == "")
			continue;

		tail = world;
		p0 = 0;
		while (1)
		{
			pn = strstrofs(e.vbsp_io_raw, "\n", p0);
			if (pn < 0)
				break;
			rec = substring(e.vbsp_io_raw, p0, pn - p0);
			p0 = pn + 1;

			ptab = strstrofs(rec, "\t", 0);
			if (ptab < 0)
				continue;
			k = substring(rec, 0, ptab);
			v = substring(rec, ptab + 1, -1);

			// Per value, not per map -- see the header.  ESC wins when present
			// because a comma is legal INSIDE an ESC-separated parameter.
			sep = ",";
			if (strstrofs(v, vbsp_io_esc, 0) >= 0)
				sep = vbsp_io_esc;

			ntok = tokenizebyseparator(v, sep);
			if (ntok < 2)
				continue;				// no input name: nothing to fire

			/*
			  Build 63.  THE CEILING, and it exists because one map in the
			  library kills the server without it.

			  This loop spawns ONE EDICT PER DECLARED OUTPUT.  pr_maxedicts
			  defaults to 131072 (engine/server/pr_cmds.c:76) and nothing in
			  this game raises it; past that ED_Alloc calls Sys_Error
			  ("no free edicts"), which is fatal and says nothing about why.

			  bhop_miku_v2 is a music-sync map: 468 entities, and 416,366 of its
			  416,464 outputs hang off ONE logic_relay driving a whole song of
			  func_wall_toggle animation.  That is 3.2x the edict ceiling, so
			  the map cannot load at all -- and could not before this build
			  either.  This does not make it play; it makes it load, and makes
			  it say what it dropped instead of dying.

			  It is a 167x outlier and the number below is chosen against the
			  rest of the library rather than against it: the next densest map
			  is surf_forbidden_tomb4 at 2,494 outputs, and the MEDIAN map wires
			  14.  32768 is therefore ~13x headroom over every other map in
			  1315 while staying a quarter of the edict budget, leaving room for
			  the vbsp_iodelay edicts SV_FireOutput spawns at runtime.
			*/
			if (vbsp_io_n >= VBSP_IO_MAXOUT)
			{
				vbsp_io_over_map = vbsp_io_over_map + 1;
				if (SV_CensusAdd("output table full"))
					dprint(sprintf("^1entity I/O: more than %g outputs on this map "
					               "-- refusing the rest.  The map is playable but "
					               "incomplete; see VBSP_IO_MAXOUT.\n",
					               VBSP_IO_MAXOUT));
				continue;
			}

			o = spawn();
			o.classname    = "vbsp_output";
			o.owner        = e;
			o.vbsp_io_name   = strtolower(k);	//Patch 256: folded, see SV_FireOutput
			o.vbsp_io_target = argv(0);
			o.vbsp_io_input  = argv(1);
			o.vbsp_io_param  = (ntok > 2) ? argv(2) : "";
			o.vbsp_io_delay  = (ntok > 3) ? stof(argv(3)) : 0;
			o.vbsp_io_times  = (ntok > 4) ? stof(argv(4)) : -1;

			// Appended, not pushed: Source fires an entity's outputs in the
			// order the map declares them, and two AddOutputs writing the same
			// key in the wrong order is a different map.
			if (tail)
				tail.vbsp_io_next = o;
			else
				e.vbsp_io_out = o;
			tail = o;
			vbsp_io_n = vbsp_io_n + 1;

			/*
			  SAY WHICH OUTPUTS HAVE NO FIRING POINT.  This is a STATIC check
			  against the list of names anything in this file actually fires,
			  and it is the honest half of "reusable layer": an output we parse
			  perfectly and never fire is invisible otherwise, and looks from
			  the outside exactly like one we got wrong.

			  bhop_futile has six OnJump (a Momentum output fired when the
			  player jumps inside the trigger, wired to a basevelocity boost).

			  THIS COMMENT USED TO SAY "FTE's Source pmove has no basevelocity
			  concept at all".  THAT WAS WRONG, and it is corrected rather than
			  quietly deleted because it was quoted onward into ENGINE_PATCHES.md
			  and into the trigger_push essay below.  pm_source.c reads
			  pmove.basevelocity in ELEVEN places -- the Z half-step in
			  PMSrc_StartGravity and the add/subtract sandwiches around WalkMove
			  and AirMove.  What was missing was a WRITER: the only one in the
			  engine was Half-Life-specific, so for this game the field was
			  permanently zero.  Engine Patch 240 adds one via .run_basevelocity,
			  and this file now fires OnJump and honours AddOutput basevelocity.
			*/
			/*
			  FTESurf Patch 256 added the second row: OnStartTouchAll and
			  OnEndTouchAll (SV_TriggerIOTouch / SV_TriggerEndThink),
			  OnLockedUse (SV_UseFrame), OnPass and OnFail (the TestActivator
			  input in SV_ApplyInput), OnTimer (logic_timer).

			  Build 63 moved the list itself up to SV_IOOutputKnown, where its
			  hand-maintained-ness is written out at length and each name names
			  its fire site.  The warning below is unchanged.
			*/
			lk = strtolower(k);
			if (!SV_IOOutputKnown(lk))
				if (SV_CensusAdd(strcat("output ", lk)))
					dprint(sprintf("^3entity I/O: nothing fires '%s' -- %s's "
					               "outputs on it are parsed and never run\n",
					               k, e.classname));
		}

		e.vbsp_io_raw = "";				// the blob has done its job
	}

	/*
	  logic_auto's OnMapSpawn, now that every output on the map exists.

	  This is the last thing the pass does, and it has to be: an OnMapSpawn
	  output may target an entity whose OWN outputs have not been built yet,
	  and firing mid-build would deliver into a half-wired map.

	  The entities are left in place rather than removed on fire (Source's
	  spawnflag 1).  They are inert point entities from here on, and keeping
	  them means `ent_census` and a find() still see what the map declared.
	*/
	for (e = find(world, classname, "logic_auto"); e;
	     e = find(e, classname, "logic_auto"))
	{
		SV_FireOutput(e, "OnMapSpawn", world);
		SV_FireOutput(e, "OnNewGame", world);
	}

	/*
	  Build 63.  logic_relay's OnSpawn, in the same place and for the same
	  reason -- every output on the map has to exist before any of them fires.

	  Source kicks a think at +0.01 from CLogicRelay::Activate and ONLY if
	  m_OnSpawn has connections (logicrelay.cpp:55-62); the think fires OnSpawn
	  and then removes the relay under SF_REMOVE_ON_FIRE (:70-81).  The
	  "has connections" test is not an optimisation -- it decides whether a
	  once-only relay consumes itself at map spawn, so a relay with no OnSpawn
	  must stay armed for a later Trigger.  Hence SV_IOHasOutput.

	  AFTER the logic_auto loop.  Source leaves the relative order unspecified,
	  and a relay is far more often the TARGET of a logic_auto than the reverse,
	  so a map that disables a relay from OnMapSpawn gets the ordering it plainly
	  intended.  44 OnSpawn outputs in the library.
	*/
	for (e = find(world, classname, "logic_relay"); e;
	     e = find(e, classname, "logic_relay"))
	{
		if (!SV_IOHasOutput(e, "onspawn"))
			continue;
		SV_FireOutput(e, "OnSpawn", e);
		if (e.spawnflags & SF_RELAY_REMOVE_ON_FIRE)
			SV_IOEnable(e, FALSE);
	}
};

/*
===========================================================================
  Spawn points
===========================================================================
*/
// Source places info_player_* origins at the player's FEET, which is also
// where CS:S puts the player origin -- so no offset conversion is needed.
// CBasePlayer::Spawn nudges up by 1 unit; PutClientInServer does the same.
void() info_player_start                = { };
void() info_player_deathmatch           = { };
void() info_player_terrorist            = { };
void() info_player_counterterrorist     = { };
void() info_player_teamspawn            = { };
void() info_player_logo                 = { remove(self); };
void() info_teleport_destination        = { };
void() info_target                      = { };
void() info_landmark                    = { };

/*
  info_overlay is not in any map's entity lump -- the VBSP plugin SYNTHESISES
  one per record in LUMP_OVERLAYS (45) and appends it to the entity string, so
  that CSQC's decal walk can read the map's baked decals (see Overlay_Place in
  cl_decals.qc).  It is a client-side drawing instruction and nothing more.

  It needs a spawn function here purely so it does not reach
  SV_OnEntityNoSpawnFunction, which would count it in ent_census as an
  unimplemented class -- a census row for something we deliberately handle
  elsewhere is worse than no row, because it makes the census lie about what is
  still missing.  Removing self is the whole body: the server has no use for it,
  and on surf_theme there are 604 of them.  They cost nothing even so --
  ED_Alloc relaxes its reuse rule while sv.time < 2 (pr_edict.c), so entities
  spawned and removed during map load all recycle the same edict slot.
*/
void() info_overlay                     = { remove(self); };

/*
  The sprite entities, Patch 248.  Same deal as info_overlay above and for the
  same reason: they are drawn entirely by CSQC, which reads them out of the
  entity lump itself (cl_sprites.qc), so the server has nothing to do with them
  beyond not reporting them as missing.

      env_sprite            10947 across 276 maps
      point_spotlight       23666 across 413 maps   the light shafts
      env_sprite_oriented     284 across   8 maps
      beam_spotlight           11 across   2 maps
      env_glow                  1                   env_sprite's older name

  DELIBERATELY NOT STUBBED, so they keep showing up in ent_census as the
  unimplemented classes they are:

      env_spritetrail        2773 across 132 maps   a ribbon through its
                                                    parent's motion, and 95.1%
                                                    of them are parented to a
                                                    brush entity that rotates
      env_lightglow          3393 across 137 maps   a view-space flare drawn at
                                                    a fixed 100 units from the
                                                    camera, not a world quad

  A stub for either would make the census claim they are handled.  The census's
  whole job is to be the honest statement of what is still missing, so the two
  that are missing stay in it.
*/
void() env_sprite                       = { remove(self); };
void() env_sprite_oriented              = { remove(self); };
void() env_glow                         = { remove(self); };
void() point_spotlight                  = { remove(self); };
void() beam_spotlight                   = { remove(self); };

/*
  Build 49.  The two POINT classes cl_emit.qc draws, stubbed under exactly the
  rule above: CSQC reads them out of the lump itself, so the only thing the
  server owes them is to stop ent_census reporting them as missing.

      env_fire   13633 across 211 maps   the largest instance count in the
                                         library after env_sprite
      env_spark    452 across  67 maps

  Without these they were reaching SV_OnEntityNoSpawnFunction and being removed
  by its "point entity with no * model" rule -- the right OUTCOME, by an
  accident of the catch-all rather than by a decision, and censused as unhandled
  the whole time.

  THE FIVE BRUSH CLASSES cl_emit.qc also draws -- func_dustmotes,
  func_dustcloud, func_smokevolume, env_bubbles and env_embers -- get NO stub
  and must not get one.  They are already handled deliberately, in the
  non-solid list at the bottom of this file, which is where they have to stay:
  a stub here would remove them, and removing them would drop the submodel that
  IS the volume CSQC spawns particles inside.  Their census rows are honest for
  a different reason -- that list is a decision, not a fallthrough.

  env_firesource is deliberately absent from both this block and cl_emit.qc.
  It carries fireradius and firedamage and no visual keys whatever; Source
  draws nothing for it either, and it stays in the census as the genuinely
  unimplemented gameplay entity it is.
*/
void() env_fire                         = { remove(self); };
void() env_spark                        = { remove(self); };

/*
  Build 51 adds a third, under the same rule.

      env_smokestack   2443 across 52 maps   worst: surf_anubis and
                                             surf_anubis_ksf at 498 each,
                                             surf_anoobis 381, surf_saturday 224

  It is a point jet, so like the two above it was already being removed by
  SV_OnEntityNoSpawnFunction and censused as missing the whole time.  The
  difference is that this one was missing VISIBLY: it is most of the library's
  torch flames, and the report that found it was a player asking why only some
  of surf_anubis' fires light.
*/
void() env_smokestack                   = { remove(self); };

/*
===========================================================================
  Props.

  Census over all 1308 maps: prop_dynamic 28178 (37.0% of maps),
  prop_dynamic_override 10902 (13.6%), prop_physics 1304 (6.7%),
  prop_physics_multiplayer 743 (4.5%), prop_physics_override 231 (1.6%),
  plus small numbers of prop_ragdoll / prop_door_rotating.  41358 in all.

  Every one of them was being DELETED before this: they are point entities,
  so the catch-all's "no '*' model, nothing to preserve" arm removed them.
  Whole map decorations -- and on some maps whole ramps -- were simply absent.

  STATIC, as asked: MOVETYPE_NONE, and no rigid body anywhere.  That last part
  is not merely by omission.  SOLID_PHYSICS_TRIMESH sounds like it hands the
  entity to Bullet/ODE, and it does not: both backends early-out on
  `movetype != MOVETYPE_PHYSICS` (com_phys_box3d.c:254, com_phys_ode.c:1458),
  so the constant selects a COLLISION SHAPE and nothing more.  That is exactly
  what we want -- Source's mesh, none of Source's physics.

  prop_static is deliberately absent: VBSP moves it out of the entity lump
  into the `sprp` game lump, the engine loads it there
  (VBSP_LoadStaticProps, mod_vbsp.c:2439) and already makes it solid.  A
  census confirms it -- zero prop_static entities in 1308 maps.  Same for
  prop_detail, which lives in its own lump and is decorative clutter.
===========================================================================
*/

/*
  SV_SpawnProp -- shared body for every prop_* classname.

  `defsolid` is the Source collision mode to assume when the map wrote no
  "solid" key.  It has to be per-class, and the reason is a QuakeC limitation
  worth stating plainly: an ABSENT key and an explicit "0" both leave .solid
  reading 0, and QC cannot tell them apart.  So the default is chosen from
  what each class actually does in the wild:

    prop_dynamic / _override   write "solid" 99.98% of the time (13098 of them
                               write exactly 0 = Not Solid).  Absent -> none.
    prop_physics*              OMIT it 96.2% of the time, and Source's default
                               for a physics prop is VPhysics.  Absent -> mesh.

  That is right for 41357 of the 41358 props in the library; the single
  prop_physics that explicitly asks for Not Solid becomes solid, which is a
  better failure than 1254 physics props turning into ghosts.
*/
/*
  Spawn tallies.

  Two ordering traps here, both of which produced a confidently wrong "props:
  0 spawned" before they were found.

  1. StartFrame RUNS BEFORE THE MAP'S ENTITIES EXIST.  Verified from the log:
     the report printed at line 27 and worldspawn only reached line 30.  So
     "report once, on the first frame we ever see" latches onto a frame from
     before the map was built and never fires again.  worldspawn is the right
     re-arm point instead -- it is the FIRST entity in the lump, so everything
     counted below spawns strictly after it.

  2. These globals SURVIVE A MAP CHANGE.  Without an explicit reset the counts
     would accumulate across every map loaded in a session, which is the kind
     of number that looks plausible and is wrong.
*/
float vbsp_prop_n, vbsp_prop_solid_n, vbsp_prop_scaled_n, vbsp_prop_dropped_n;
// Build 34: props whose bounds came back empty from setmodel.  Should be 0 now
// that worldspawn sets sv_gameplayfix_setmodelsize_qw; a non-zero count means
// either that cvar_set stopped working or the model genuinely failed to load,
// and both look identical on screen (a prop you walk through) without it.
float vbsp_prop_nobox_n;
float vbsp_water_n, vbsp_reltele_n;
float vbsp_need_report;

// Areaportals -- see func_areaportal, far below.  Declared up here with the
// other per-map counters because SV_EntityReset/SV_EntityReport come before
// the spawn function does and QC has no forward declaration for a global.
float  vbsp_portal_n;
entity vbsp_portal_first;

// Patch 191, below.  Same reason it lives up here as the areaportal pair.
float vbsp_targetfix_n;

// Patch 194, linked_portal_door.  Likewise: SV_EntityReset clears these and
// SV_EntityReport prints them, and both come before the spawn function.
float vbsp_lpd_n, vbsp_lpd_unpaired;
entity vbsp_lpd_reporter;	// Patch 207: deferred count, see linked_portal_door_report

void() SV_EntityReset =
{
	vbsp_prop_n = vbsp_prop_solid_n = vbsp_prop_scaled_n = vbsp_prop_dropped_n = 0;
	vbsp_prop_nobox_n = 0;
	vbsp_water_n = vbsp_reltele_n = 0;
	vbsp_need_report = TRUE;

	// Both of these survive a map change, and vbsp_portal_first would survive it
	// holding an edict from the LAST map -- which SV_OpenAllPortals would then
	// walk.  Same trap the prop counters carry a note about above.
	vbsp_portal_n = 0;
	vbsp_portal_first = world;
	vbsp_targetfix_n = 0;
	vbsp_lpd_n = vbsp_lpd_unpaired = 0;
	vbsp_lpd_reporter = world;	// Patch 207: SV_EntityReset clears this too

	// Build 37.  Same trap as every counter above: these are globals and they
	// would otherwise accumulate across every map loaded in a session.
	vbsp_io_n = vbsp_io_fired = 0;

	/*
	  Build 63.  vbsp_io_depth in particular MUST be cleared here, and it is the
	  one in this function whose absence would not look like a counter bug.  It
	  is a bracketing counter: a map change that landed while a chain was part
	  way through -- a delayed output delivering into a changelevel, say --
	  would leave the NEXT map starting at a non-zero depth, and a map that
	  starts at or above the ceiling has its entity I/O silently dead from the
	  first frame with no warning that says so.
	*/
	vbsp_io_depth = vbsp_io_depth_max = vbsp_io_depth_hit = 0;
	vbsp_io_over_ent = vbsp_io_over_map = 0;
	vbsp_bhop_n = vbsp_bhop_tele_n = 0;
	vbsp_tele_disabled_n = 0;

	// The census buffers outlive the map too.  Drop them and let SV_CensusAdd
	// recreate them lazily, rather than reporting the last map's classnames.
	if (ent_census_name > 0)
	{
		buf_del(ent_census_name);
		buf_del(ent_census_count);
	}
	ent_census_name = ent_census_count = 0;
	ent_census_n = 0;
};

/*
===========================================================================
  Patch 191 -- 1,168 teleports that pointed at nothing but a letter case.

  find() is strcmp (pr_bgcmd.c:1728).  Source's entity I/O is case-insensitive,
  and mappers rely on that without knowing they do, so a trigger_teleport whose
  `target` is "Red" never finds the info_teleport_destination named "red" and
  silently does nothing but print to the developer console.

  surf_kitsune is the map that surfaced it and it is not a near miss: 28 of its
  44 teleports fail this way -- Red/red, yellow/YELLOW, white/WHITE,
  Orange1/orange1, Teal1/teal1 -- so most of the map cannot be completed.
  Counted across all 2,394 BSPs in the library: 1,184 mismatched target
  references in 145 maps, 1,168 of them trigger_teleport.  Worst are
  surf_tycho 74, surf_prevail 52, surf_mesa_mine 48, surf_delight 41, then
  surf_santorini3 / surf_kitsune / surf_happyhug at 28 each.

  WHY REWRITE THE KEY INSTEAD OF FIXING THE LOOKUP.  Two reasons.

  The lookup is not in one place.  trigger_teleport resolves `target` and
  `landmark`, and func_tanktrain, path_track, point_viewcontrol and
  func_tracktrain resolve `target` too -- the survey found mismatches on all of
  them.  Repairing the KEY fixes every consumer, including ones nobody has
  written yet, and leaves the touch path as a single find() with no added
  runtime cost.

  And it is deliberately not an engine change.  Making the find() builtin
  case-insensitive would change behaviour for every mod that uses it, to fix a
  problem that belongs to one game's entity format.

  EXACT MATCHES ARE NEVER TOUCHED.  The exact find() is tried first and wins, so
  a map where two destinations differ only in case keeps whichever one it
  resolves to today.  The scan only runs for references that already resolve to
  nothing, which is why it costs nothing on the 2,249 maps that are fine.

  Runs from StartFrame's first-frame-after-worldspawn hook for the reason the
  comment above SV_EntityReport gives: StartFrame is called before the map's
  entities exist, so doing this any earlier would walk an empty world.
===========================================================================
*/
// "" when the reference is empty, already resolves, or matches nothing even
// ignoring case -- i.e. when there is nothing to repair.  Otherwise the
// destination's own spelling.
string(string want) SV_TargetCaseFix =
{
	local entity d;

	if (want == "")
		return "";
	if (find(world, targetname, want) != world)
		return "";			// resolves exactly; leave it alone

	for (d = nextent(world); d; d = nextent(d))
	{
		if (d.targetname == "")
			continue;
		if (!strcasecmp(d.targetname, want))
			return d.targetname;
	}
	return "";				// genuinely points at nothing; not ours to invent
};

void() SV_RepairTargetCase =
{
	local entity e;
	local string fix;

	for (e = nextent(world); e; e = nextent(e))
	{
		fix = SV_TargetCaseFix(e.target);
		if (fix != "")
		{
			e.target = fix;
			vbsp_targetfix_n = vbsp_targetfix_n + 1;
		}
		fix = SV_TargetCaseFix(e.landmark);
		if (fix != "")
		{
			e.landmark = fix;
			vbsp_targetfix_n = vbsp_targetfix_n + 1;
		}
	}
};

void() SV_EntityReport =
{
	// Printed even when the count is zero.  "props: 0" and no line at all mean
	// two very different things -- a map with no props, versus spawn functions
	// that are never being reached -- and silence cannot tell them apart.
	print(sprintf("props: %g spawned (%g solid, %g scaled)",
	              vbsp_prop_n, vbsp_prop_solid_n, vbsp_prop_scaled_n));
	if (vbsp_prop_dropped_n)
		print(sprintf(", %g dropped (no model)", vbsp_prop_dropped_n));
	// Build 34.  Printed ONLY when non-zero, because zero is the expected state
	// and a line that always says "0 with no bounds" would be read past.  A
	// non-zero here means props are ghosts -- see worldspawn's setmodelsize_qw.
	if (vbsp_prop_nobox_n)
		print(sprintf(", ^1%g with NO BOUNDS^7", vbsp_prop_nobox_n));
	print("\n");

	if (vbsp_water_n)
		print(sprintf("water: %g brush(es) as CONTENT_WATER\n", vbsp_water_n));
	if (vbsp_reltele_n)
		print(sprintf("relative teleports: %g\n", vbsp_reltele_n));

	// Patch 191.  Printed because a silent repair is one nobody can check, and
	// because a map reporting a large number here is a map whose author was
	// relying on Source's case-insensitive entity I/O throughout -- worth
	// knowing before blaming anything else that misbehaves on it.
	if (vbsp_targetfix_n)
		print(sprintf("target case: %g reference(s) repaired\n", vbsp_targetfix_n));

	// Printed whenever the map has any, because "the far half of the map is
	// missing" and "this map has areaportals" are the same sentence -- see
	// func_areaportal.
	if (vbsp_portal_n)
		print(sprintf("areaportals: %g opened\n", vbsp_portal_n));

	/*
	  Patch 207: the portal-door count is NOT printed here any more, because
	  from here it could only ever print zero.

	  This report runs from StartFrame, and in FTESurf StartFrame runs before
	  worldspawn and therefore long before `time + 0.1` -- which is when
	  linked_portal_door_link resolves the pairs and increments vbsp_lpd_n.  So
	  the line that was meant to say "eighteen doors linked" said "no portal
	  doors on this map", on every map that has them, for two patches.  It is
	  reported from the deferred reporter instead (linked_portal_door_report),
	  which fires after every link has had its chance.
	*/
	/*
	  Build 37.  Printed whenever the map wires anything, because "this map has
	  entity I/O" is the single most useful thing to know before blaming
	  anything else on it -- and because a map whose outputs failed to parse
	  reports 0 here rather than reporting nothing, which is the difference
	  between "no wiring" and "the wiring was dropped".
	*/
	if (vbsp_io_n)
		print(sprintf("entity I/O: %g output(s) wired\n", vbsp_io_n));

	/*
	  Build 63.  In red, unconditional, and it NAMES THE MAP.

	  print rather than dprint, and the map name spelled out, because the
	  failure this reports is one that will otherwise be described to you
	  second-hand and wrongly: a map that silently drops 400,000 outputs gets
	  reported as "the func_wall_toggles don't work on miku", and nobody
	  connects that to a cap they cannot see.  A silent discard and a clean run
	  produce identical evidence; the counter is the only thing that separates
	  them.
	*/
	/*
	  Reported SEPARATELY, because the two ceilings fail for different reasons
	  and pointing at the wrong one sends the next reader to the wrong place.
	  The first build-63 run proved that on itself: it printed "declares more
	  than 32768 outputs" for bhop_miku_v2, when the map-wide ceiling had never
	  been reached at all -- 4194 wired is well under it -- and every one of the
	  412,270 refusals came from the per-entity cap.
	*/
	if (vbsp_io_over_ent)
		print(sprintf("^1entity I/O: %s has an entity declaring more than %g "
		              "outputs -- %g REFUSED and will never fire.  The map is "
		              "playable but its wiring is incomplete.^7\n",
		              mapname, VBSP_IO_MAXRAW, vbsp_io_over_ent));
	if (vbsp_io_over_map)
		print(sprintf("^1entity I/O: %s declares more than %g outputs in total "
		              "-- %g REFUSED and will never fire.^7\n",
		              mapname, VBSP_IO_MAXOUT, vbsp_io_over_map));

	if (vbsp_bhop_n)
		print(sprintf("func_bhop: %g solid platform(s)\n", vbsp_bhop_n));

	// Only when non-zero, because zero is the expected state.  A map reporting
	// a large number here has teleports that are inert until something enables
	// them, and if that something is an output we do not fire, this is the line
	// that says so before the map reads as broken.
	if (vbsp_tele_disabled_n)
		print(sprintf("teleports: %g spawned DISABLED\n", vbsp_tele_disabled_n));

	print(sprintf("ent_census: %g unhandled classnames/inputs (`ent_census` to list)\n",
	              ent_census_n));
};

/*
===========================================================================
  `ent_io` -- Build 63.  Did any of the wiring RUN?

  SV_EntityReport says what the map declares; this says what happened to it.
  The two numbers that matter are on the first line: outputs wired against
  inputs delivered.  Wired but nothing delivered is a map whose logic never
  started; delivered climbing while nobody moves is a timer driving something.

  The depth high-water mark is here to turn VBSP_IO_MAXDEPTH from a guess into
  a measured margin.  32 was chosen with no evidence behind it -- if the
  deepest legitimate chain across the library turns out to be 5, the constant
  can be justified rather than defended; if some map legitimately reaches 30,
  the fuse is about to start truncating real map logic and reporting it as a
  cycle, which is the exact failure the census exists to prevent.  Read it on
  the densest maps before trusting the number.
===========================================================================
*/
void() SV_IOReport =
{
	print(sprintf("entity I/O: %g output(s) wired, %g input(s) delivered\n",
	              vbsp_io_n, vbsp_io_fired));

	if (!vbsp_io_on)
		print("  vbsp_entity_io is 0 -- the layer is switched off on this map\n");

	print(sprintf("  fire depth: %g now, %g peak (ceiling %g)\n",
	              vbsp_io_depth, vbsp_io_depth_max, VBSP_IO_MAXDEPTH));

	// Both in red, because both mean map wiring that did not run.
	if (vbsp_io_depth_hit)
		print(sprintf("^1  %g fire(s) REFUSED by the cycle fuse^7\n", vbsp_io_depth_hit));
	if (vbsp_io_over_ent)
		print(sprintf("^1  %g output(s) REFUSED -- one entity over %g^7\n",
		              vbsp_io_over_ent, VBSP_IO_MAXRAW));
	if (vbsp_io_over_map)
		print(sprintf("^1  %g output(s) REFUSED -- map over %g^7\n",
		              vbsp_io_over_map, VBSP_IO_MAXOUT));

	if (!vbsp_io_depth_hit && !vbsp_io_over_ent && !vbsp_io_over_map && vbsp_io_n)
		print("  no refusals\n");
};

void(float defsolid) SV_SpawnProp =
{
	local float srcsolid, sc;

	// A prop with no model is nothing to draw and nothing to hit.  A prop
	// carrying a BRUSH model ('*N') is a mapper error -- studio props do not
	// have submodels -- and setmodel would bind world geometry to it.
	if (self.model == "" || substring(self.model, 0, 1) == "*")
	{
		vbsp_prop_dropped_n = vbsp_prop_dropped_n + 1;
		remove(self);
		return;
	}

	/*
	  THE NAME COLLISION, and it is a trap.

	  Source's prop key is spelled "solid", which is exactly the name of
	  QuakeC's .solid field, so VBSP's value lands directly in it.  By the time
	  this function runs .solid already holds 0, 2 or 6 in SOURCE's meaning --
	  and 6 is not a SOLID_ constant at all.  Left alone, every VPhysics prop
	  in the game would be solidity 6, which is SOLID_CORPSE's neighbour and
	  means nothing here.  Read it out first, then overwrite.

	  430 props in a 300-map sample write it as "Solid" instead, which lands in
	  .Solid and never reached this at all -- see THE OTHER SPELLING above.
	*/
	srcsolid = SV_Key2(self.solid, self.Solid);
	if (srcsolid == SRCSOLID_NONE)
		srcsolid = defsolid;

	precache_model(self.model);
	setmodel(self, self.model);

	/*
	  modelscale -> .scale.  86.6% of props write one and it is very often not
	  1 (2, 1.5, 4, 3, 5, 8, 10 all appear in quantity), so ignoring it would
	  put a lot of props at the wrong size -- and, because the trace path reads
	  the same field, at the wrong COLLISION size too (world.c:1399 for the
	  hull path, :1414 for the per-triangle one).

	  SSQC quantises .scale to 1/16 and saturates just under 16
	  (sv_defs.qc:401), so clamp rather than let it wrap.
	*/
	sc = self.modelscale;
	if (sc <= 0)
		sc = 1;
	if (sc > 15.9)
		sc = 15.9;
	self.scale = sc;

	/*
	  Build 34: this used to be guarded by `if (sc != 1)`, which was the wrong
	  shape twice over.  setmodel only fills .mins/.maxs at all because
	  worldspawn now sets sv_gameplayfix_setmodelsize_qw (see the essay there);
	  before that this line multiplied '0 0 0' by the scale, and at sc == 1 it
	  did not run, so an UNSCALED prop was never sized either.  Unconditional now
	  -- a no-op at sc == 1, and it documents that the bounds are expected to be
	  real by this point.

	  setmodel takes the bounds from the model unscaled, so the link box would be
	  the wrong size for anything scaled.  The trace itself is scale-aware; this
	  is just so World_LinkEdict puts it in the right areanodes.
	*/
	setsize(self, self.mins * sc, self.maxs * sc);

	// The one number that says whether the bounds actually arrived.  A prop that
	// reaches here with no size is one the player will walk straight through,
	// and it is otherwise completely silent.
	if (self.size == '0 0 0')
		vbsp_prop_nobox_n = vbsp_prop_nobox_n + 1;

	self.movetype = MOVETYPE_NONE;

	if (srcsolid == SRCSOLID_BBOX)
		self.solid = SOLID_BBOX;
	else if (srcsolid == SRCSOLID_VPHYSICS)
		self.solid = SOLID_PHYSICS_TRIMESH;
	else
		self.solid = SOLID_NOT;

	/*
	  Build 34: relink, because .solid changed AFTER the last link.

	  setmodel and setsize above both link the entity, and at that point .solid
	  still held Source's own value -- 6 for a VPhysics prop, read out of the
	  "solid" key into QuakeC's identically-named .solid field (see THE NAME
	  COLLISION above).  World_LinkEdict expands absmin/absmax for ROTATION only
	  when it sees SOLID_BSP/BSPTRIGGER/PHYSICS_BOX/PHYSICS_TRIMESH
	  (world.c:556-557), so it never expanded any of them: a rotated prop's link
	  box was its unrotated one, and the broadphase dropped the player's move
	  before any trace ran near its corners.

	  That was already true for server-side traceline/tracebox against rotated
	  props; it matters more now that Patch 229 makes the player's own move
	  consult them.  setorigin is the cheapest forced relink in QuakeC.
	*/
	setorigin(self, self.origin);

	// "Don't Render".  Rare (9 instances library-wide) but free to honour, and
	// a prop the mapper hid is usually hiding something.
	if (self.rendermode == RENDERMODE_NONE)
		self.effects = self.effects | EF_NODRAW;

	vbsp_prop_n = vbsp_prop_n + 1;
	if (self.solid != SOLID_NOT)
		vbsp_prop_solid_n = vbsp_prop_solid_n + 1;
	if (sc != 1)
		vbsp_prop_scaled_n = vbsp_prop_scaled_n + 1;
};

// prop_dynamic is an animated prop in Source.  Here it is a static one: the
// user's call, and the right one for a surf map, where a prop is scenery or
// it is geometry and in neither case should it be simulating.
void() prop_dynamic              = { SV_SpawnProp(SRCSOLID_NONE); };
void() prop_dynamic_override     = { SV_SpawnProp(SRCSOLID_NONE); };
void() prop_dynamic_glow         = { SV_SpawnProp(SRCSOLID_NONE); };
void() prop_dynamic_ornament     = { SV_SpawnProp(SRCSOLID_NONE); };
void() prop_physics              = { SV_SpawnProp(SRCSOLID_VPHYSICS); };
void() prop_physics_multiplayer  = { SV_SpawnProp(SRCSOLID_VPHYSICS); };
void() prop_physics_override     = { SV_SpawnProp(SRCSOLID_VPHYSICS); };
void() prop_door_rotating        = { SV_SpawnProp(SRCSOLID_VPHYSICS); };

// A ragdoll with no physics is a corpse lying where the mapper left it.  Not
// solid: a ragdoll in Source is never something you stand on, and making 51
// of them solid could only ever block someone.
void() prop_ragdoll              = { SV_SpawnProp(SRCSOLID_NONE); };

/*
  THE ALIASES, and what they are worth: nothing, today.

  A census of all 1310 maps in the library finds ZERO instances of every
  classname below.  They exist so that a map which does use one spawns a prop
  instead of landing in ent_census as an open question for someone to
  re-derive -- and so the FGD's list and this file's list finally agree.

  They go AFTER the functions they call, because QuakeC resolves a call
  against what is already defined above it.

  prop_hallucination is Source's "visible to a subset of players" prop.  There
  is no per-client visibility here, so it becomes plain scenery, and it must
  never be solid: a prop that half the server cannot see is a prop half the
  server would be blocked by for no visible reason.

  simple_physics_brush is deliberately NOT here.  It is a @SolidClass, so its
  model is a '*N' brush, and the catch-all already keeps unrecognised brush
  entities as SOLID_BSP -- which is what it should be.  Naming it here would
  hand a brush model to SV_SpawnProp, which drops '*N' models on sight
  (:517), and the map would lose the brush entirely.
*/
void() prop_physics_ragdoll      = { prop_ragdoll(); };
void() prop_physics_respawnable  = { prop_physics(); };
void() simple_physics_prop       = { prop_physics(); };
void() prop_sphere               = { prop_physics(); };
void() prop_hallucination        = { SV_SpawnProp(SRCSOLID_NONE); };

/*
===========================================================================
  Water.

  func_water_analog is a moving water brush (358 instances, 5.8% of maps);
  func_water is its older sibling (14 instances).  Both were reaching the
  catch-all, which makes any unrecognised brush entity SOLID_BSP -- so every
  one of them was a solid, invisible-to-reason BLOCK OF WATER you could not
  swim into and could stand on.

  The movement is not modelled (no entity I/O to drive it, and the water sits
  at "startposition" forever), which is the same trade the static-brush note
  below describes.  What matters is that it is water.
===========================================================================
*/
void() SV_SpawnWater =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	// Visible, unlike the triggers: a water surface is something you look at.
	setmodel(self, self.model);
	self.movetype = MOVETYPE_NONE;
	self.solid = SOLID_BSP;
	self.skin = CONTENT_WATER;
	vbsp_water_n = vbsp_water_n + 1;
};

void() func_water        = { SV_SpawnWater(); };
void() func_water_analog = { SV_SpawnWater(); };

/*
===========================================================================
  trigger_teleport -- stage/bonus teleports, and the "you fell off" resets
  that every surf map is built around.
===========================================================================
*/
void() trigger_teleport;        // trigger_momentum_teleport is it, see below

/*
  BUILD 13 -- +jump while noclipping flies straight through a teleport.

  A surf map's teleports are its scaffolding: 351 of them on surf_666, most of
  them the "you fell off" resets that carpet the floor of every stage.  Noclip
  is how you go and look at something, and any route to it crosses several of
  those, so you get snatched back to the stage start before you arrive.

  +jump is the key to hold because noclip no longer uses it for anything.  The
  engine synthesises upmove from it for swimming (cl_input.c:2667), which is why
  space used to drift you upward; PMSrc_NoClipMove now drops that, leaving the
  button free and leaving WASD+mouse to do the flying.

  Deliberately requires BOTH: noclip alone still teleports, because walking a
  route and being reset by it is the map working correctly, and silently
  disabling that whenever noclip was on would hide real behaviour.
*/
float(entity e) SV_TeleportBypassed =
{
	if (e.movetype != MOVETYPE_NOCLIP)
		return FALSE;
	return e.button2 != 0;
};

void() trigger_teleport_touch =
{
	local entity dest, mark;
	local vector newpos;
	local float  vmode, uselm, snapv, snapang;

	if (other.classname != "player")
		return;
	if (other.health <= 0)
		return;
	if (SV_TeleportBypassed(other))
		return;

	// spawnflags bit 1 is "Clients/Players", which the FGD has ON by default
	// (momentum.fgd:10568) -- so Hammer writes it and VBSP keeps it.  A key of
	// exactly 0 means the map never wrote spawnflags at all, which is the
	// common case for older CS:S maps; treat that as the default rather than
	// as "players excluded", or half the surf library loses its resets.
	if (self.spawnflags && !(self.spawnflags & SF_TELEPORT_CLIENTS))
		return;

	/*
	  BUILD 37 -- the two gates this handler never had.

	  StartDisabled was already honoured by trigger_teleport_relative_touch
	  (:984) and not here, which was simply an omission; now that Enable and
	  Disable exist it is also reversible, so a disabled teleport is a state
	  rather than a permanent deletion.

	  The FILTER is the whole of bhop_futile.  35 of its 98 teleports carry a
	  filtername and every one of them fired on first touch, so landing on the
	  first platform sent you straight back to the start -- which is the map
	  reading as "the bhop platforms don't work".  See SV_PassesFilter for why
	  an unresolvable or unimplemented filter deliberately passes.
	*/
	if (SV_Key2(self.StartDisabled, self.startdisabled))
		return;
	if (!SV_PassesFilter(self, other))
		return;

	/*
	  A teleport is a CBaseTrigger too, and 37 of surf_kitsune's carry outputs
	  -- stage renames on OnStartTouch and a secret counter on OnEndTouch.
	  Free on a teleport with no outputs, which is nearly all of them.

	  Before the destination lookup, because Source fires StartTouch before it
	  moves you, and an output that renames the activator must land while the
	  activator is still where the map thinks it is.
	*/
	SV_TriggerIOTouch(self, other);

	dest = find(world, targetname, self.target);
	if (!dest)
	{
		dprint(sprintf("trigger_teleport: no destination '%s'\n", self.target));
		return;
	}

	mark = world;
	if (self.landmark != "")
		mark = find(world, targetname, self.landmark);

	/*
	  WHETHER TO SNAP THE ANGLES.  This was wrong in both directions.

	  It used to be `dest.angles != '0 0 0' || (spawnflags & 32)`, and Source's
	  CTriggerTeleport::Touch is the exact opposite of both halves: it snaps to
	  the destination's angles UNLESS SF_TELEPORT_PRESERVE_ANGLES is set, and it
	  does not care whether those angles happen to be zero.

	  The zero half was the expensive one.  6,635 of the library's 17,188
	  info_teleport_destination entities point at yaw 0 -- deliberately, since
	  north is a direction -- and we ignored every one of them, including all six
	  of surf_666's stage returns.  That is the whole of "the teleports disregard
	  angles and leave me facing wherever I was".  The flag half was nearly
	  harmless by luck: only 7 teleports in the entire library set bit 32.

	  Then Momentum's own key on top, which is not optional -- 16,829 teleports
	  write it.  It applies in both modes (only 1,189 teleports even have a
	  landmark), and in landmark mode it is the thing that turns the FGD's
	  "angles are left alone" into "reoriented to the destination if enabled".
	  Absent means the FGD default, and the FGD default differs by mode: without
	  a landmark, snap; with one, leave alone.  See SV_KeyTri.
	*/
	uselm  = SV_KeyTri(self.UseLandmarkAngles, self.uselandmarkangles);
	snapv  = SV_KeyTri(self.snapvelocitytodestangles, "");

	if (mark)
	{
		// Landmark mode: the player keeps their offset from the landmark.  This
		// is what makes a stage-to-stage teleport preserve a run.
		newpos = dest.origin + (other.origin - mark.origin);
		snapang = (uselm > 0);
	}
	else
	{
		// Source lifts the destination by one unit after aligning it to the hull
		// (CTriggerTeleport::Touch: tmp.z -= WorldAlignMins().z; tmp.z++).  Our
		// hull is already Source's with the origin at the feet, so the alignment
		// term is zero and the lift is all that was missing -- and it is what
		// keeps a destination sitting exactly on the floor from arriving solid.
		newpos  = dest.origin + '0 0 1';
		snapang = (uselm != 0) && !(self.spawnflags & SF_TELEPORT_PRESERVE_ANGLES);
	}

	setorigin(other, newpos);

	/*
	  "I did not travel here, I was put here."  Build 20, and it was missing.

	  This handler has never told the timer anything -- not this, not a void, not
	  a practice mark.  So run_t_lastorg stayed at the departure point and the next
	  tick's SWEPT zone test ran a segment from there to the arrival, firing every
	  stage, checkpoint and END zone on the line between them.  On a map that
	  teleports you backwards past the finish, that SILENTLY FINISHES THE RUN --
	  worse than the missing grey clock this build was asked for.

	  SV_ZoneMove has solved this since build 10, three lines after its own
	  setorigin, with an essay.  The map's own teleports never got the same call.

	  SV_TimerWarped also empties the pre-start padding ring, which is right here
	  for the reason its own comment gives: the ring is the APPROACH, and you did
	  not approach.  It deliberately does NOT void or taint -- plenty of surf maps
	  teleport you legitimately mid-route, and a teleport that lands you in a start
	  zone is caught one tick later by SV_TimerTryArm instead.
	*/
	if (cvar("run_teleport_warp"))
		SV_TimerWarped(other);

	// A teleport into a fall must not spend its first tick believing it is
	// standing; Source clears the ground entity before moving you.
	other.flags = other.flags - (other.flags & FL_ONGROUND);

	if (snapang)
	{
		other.angles   = dest.angles;
		other.angles_x = 0;         // destinations are yaw markers; pitch and
		other.angles_z = 0;         // roll on one are authoring noise

		/*
		  BUILD 13 -- .v_angle, which is why none of this was visible.

		  The logic above has been right since build 7 and the snap still never
		  happened: 291 of surf_666's 351 teleports point at a destination with
		  yaw 0 and you kept whatever angle you arrived with.

		  .angles on a PLAYER is the model's orientation -- what other clients
		  see, with the pitch scaled to a third.  The view is .v_angle, and the
		  engine DERIVES .angles from it at the top of every usercmd
		  (pr_cmds.c:10582), so a touch function that writes .angles is writing
		  a value that is recomputed from a v_angle we never touched.

		  It also decides whether the client is told anything at all.  SV_RunCmd
		  latches startangle = v_angle before physics and, at the bottom
		  (pr_cmds.c:10601-10608), sends a PEXT2_SETANGLEDELTA only when v_angle
		  has MOVED across the tick.  Change .angles alone and that delta is
		  zero: a predicting client is informed of nothing and keeps aiming
		  wherever it already was, which is the report.

		  SV_ZoneGotoAng (sv_zones.qc:513-515) writes BOTH, and that is the path
		  that has always worked -- `!s` and `zone_goto` aim correctly today.
		  The two teleporters differed by exactly this line.
		*/
		other.v_angle  = other.angles;
		other.fixangle = TRUE;

		/*
		  "Snap Velocity To Destination Angles" -- keep the speed, point it the
		  way the destination faces.  Gated on the angle snap, as the FGD gates
		  it, and on the key being present: 98 teleports write it and 81 want it.
		  Vertical velocity is deliberately untouched, which is what makes this
		  survive being used mid-fall.
		*/
		if (snapv > 0)
		{
			local float hs;
			hs = vlen([other.velocity_x, other.velocity_y, 0]);
			makevectors(other.angles);
			other.velocity = v_forward * hs + '0 0 1' * other.velocity_z;
		}
	}

	// Landmark mode is a seam in the level, not a reset: velocity is carried
	// through untouched and VelocityMode does not apply.
	if (mark)
		return;

	// VelocityMode is Momentum's extension (momentum.fgd:10590); a plain CS:S
	// map has no such key, so it reads 0 == keep velocity.  That is deliberate:
	// zeroing on every teleport would kill a staged run.  Both spellings, as
	// everywhere else -- 65 maps write `velocitymode` and 467 write `setspeed`.
	vmode = SV_Key2(self.VelocityMode, self.velocitymode);

	if (vmode == 1)
		other.velocity = '0 0 0';
	else if (vmode == 2)
		other.velocity = [0, 0, min(other.velocity_z, 0)];
	else if (vmode == 3)
	{
		local float spd;
		spd = SV_Key2(self.SetSpeed, self.setspeed);
		if (spd <= 0)
			spd = vlen(other.velocity);
		makevectors(dest.angles);
		other.velocity = v_forward * spd;
	}
};

/*
  trigger_momentum_teleport -- 589 instances across 12 maps, and every one of
  them has been dead.

  The FGD makes the relationship explicit:

      @SolidClass base(trigger_teleport) = trigger_momentum_teleport
          [ ProgressTeleport(boolean) ... TeleportDelay(float) ... ]

  It IS trigger_teleport, plus two keys we do not implement yet.  Without a
  spawn function it hit the `trigger_` prefix arm of SV_OnEntityNoSpawnFunction,
  which strips the model and sets SOLID_NOT -- correct for an unknown trigger,
  and here it meant surf_colin_blaster_69000's 161 fall-off resets (three
  quarters of that map's 217 teleport volumes) silently did nothing.

  ProgressTeleport wants trigger_momentum_progress checkpoints, which is build
  8's work; ignoring it makes those teleports send you to `target` instead,
  which is the same place for every instance in the shipped library.
*/
void() trigger_momentum_teleport = { trigger_teleport(); };

/*
  Bind a brush entity's submodel WITHOUT drawing it.

  The old form here was setmodel() then `self.modelindex = 0`, which is the
  usual Quake idiom for an invisible trigger.  It costs more than it looks:
  clearing modelindex drops the collision model, so SOLID_BSPTRIGGER's hull
  test has nothing to test (world.c:1259 needs mdlidx) and World_LinkEdict
  stops rotating the box (world.c:557 reads the model bounds).  A trigger
  brush built at an angle -- most of a surf map's -- then fires across its
  whole axis-aligned bounding box.

  EF_NODRAW hides it instead, which is the same result visually and keeps
  everything the collision path needs.
*/
void() SV_BindInvisibleBrush =
{
	setmodel(self, self.model);
	self.effects = self.effects | EF_NODRAW;
};

void() trigger_teleport =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	SV_BindInvisibleBrush();
	self.movetype = MOVETYPE_NONE;
	self.solid = SOLID_BSPTRIGGER;
	self.touch = trigger_teleport_touch;

	// Build 37: remembered so Enable restores a TRIGGER rather than a wall,
	// and counted so a map full of disabled teleports says so at load.
	self.vbsp_io_solid = SOLID_BSPTRIGGER;
	if (SV_Key2(self.StartDisabled, self.startdisabled))
		vbsp_tele_disabled_n = vbsp_tele_disabled_n + 1;
};

/*
===========================================================================
  trigger_teleport_relative -- 276 instances across 44 maps.

  The simplest teleport there is: no destination entity, no landmark, just a
  "teleportoffset" vector added to wherever you happen to be (every one of the
  276 writes that key).  Source's CTriggerTeleportRelative::Touch is one line,
  and so is this.  Angles and velocity are untouched by design -- a relative
  teleport is a seam in the level, not a reset.
===========================================================================
*/
void() trigger_teleport_relative_touch =
{
	if (other.classname != "player")
		return;
	if (SV_TeleportBypassed(other))
		return;
	if (other.health <= 0)
		return;
	if (self.spawnflags && !(self.spawnflags & SF_TELEPORT_CLIENTS))
		return;
	/*
	  BUILD 39: SV_Key2, not the raw field.  trigger_teleport_relative's own
	  spawn function reads the key this way and so does every other entity in
	  this file -- the FGD spells it "StartDisabled" while Source's compiled maps
	  write "startdisabled", so a raw `self.StartDisabled` sees only half of the
	  276 instances.
	*/
	if (SV_Key2(self.StartDisabled, self.startdisabled))
		return;

	setorigin(other, other.origin + self.teleportoffset);

	/*
	  BUILD 39 -- AND THE GROUND FLAG, WHICH BOTH SIBLINGS CLEAR AND THIS ONE
	  DID NOT.

	  trigger_teleport_touch clears it (with an essay), SV_BhopTeleport clears
	  it, SV_SaveLocLoad now clears it, and this was the last placement in the
	  codebase still claiming you were standing on a floor you were moved onto.

	  WHAT IT DOES NOT DO, so it does not get credited with the wrong fix later:
	  it does not stop a double jump, and neither does the sibling it is being
	  made to match.  PMSrc_Tick runs CategorizePosition (pm_source.c:2732)
	  BEFORE FullWalkMove, so the flag sv_user.c:7944 loads out of here is
	  overwritten by a fresh 2-unit trace before CheckJumpButton ever reads it.
	  The jump is Patch 241's problem and Patch 241 is where it is solved.

	  What this flag really drives is the QC's own picture of the world --
	  STAT_FS_FLAGS, the HUD's ground regime, Board_Frame's segment kind, the
	  bhop dwell timer -- none of which get a trace of their own, plus a usercmd
	  that runs zero ticks and so reaches no CategorizePosition at all.

	  "Angles and velocity are untouched by design" above is still true and is a
	  different statement.  Keeping your velocity is the whole point of a
	  relative teleport; asserting ground contact you never made is not.
	*/
	other.flags = other.flags - (other.flags & FL_ONGROUND);

	// Same as trigger_teleport_touch above, and for the same reason -- a relative
	// teleport moves you just as far, it just spells the destination differently.
	if (cvar("run_teleport_warp"))
		SV_TimerWarped(other);
};

void() trigger_teleport_relative =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	SV_BindInvisibleBrush();
	self.movetype = MOVETYPE_NONE;
	self.solid = SOLID_BSPTRIGGER;
	self.touch = trigger_teleport_relative_touch;
	vbsp_reltele_n = vbsp_reltele_n + 1;
};

/*
===========================================================================
  Patch 205 -- linked_portal_door, seamless.  Patch 194's header follows this
  one and is kept because its census and its reasoning are still true; what
  changed is the mechanism, and why.

  PATCH 194 PUT YOU IN THE WALL, and not by a little.  Its transform was
  right; its trigger was not.  A touch fires when your BOX reaches the volume,
  so with a 16-deep trigger and a +-16 player it first fires about 32 units in
  FRONT of the entry plane.  The mirror sends +32 to -32 -- 32 units BEHIND
  the exit plane, inside the wall the exit is set into -- and the anti-
  ping-pong guard then made it permanent, because a wedged player keeps
  touching the door they arrived at and keeps refreshing the suppression.
  Patch 194's own verification table recorded both outcomes and read the wrong
  one as the pass: the arrival it logged as "unchanged" was a player embedded
  in solid.

  No number fixes that.  A crossing has to be measured AT the plane, and the
  only thing that knows where the plane was crossed is the mover.

  So the door becomes SOLID_PORTAL, which is a contract with the engine rather
  than a shape: PM_PortalCSG carves the world behind the aperture out of every
  trace (so you can walk through a wall that is still there for everything
  else), PM_PlayerTracePortals follows the crossing and re-traces from the far
  side, and both call back into shared/sh_portal.qc through .camera_transform.
  Patch 203 is the engine half -- until it, a modelless SOLID_PORTAL got
  garbage bounds and the CSG window could not reach a player standing on the
  floor.

  WHAT IS GONE, deliberately:

    * linked_portal_door_touch, and .vbsp_lpd_from/.vbsp_lpd_until with it.  The
      guard existed only because a touch-trigger crossing bounces; a plane
      crossing does not, so there is nothing to suppress.
    * the SV_TimerWarped call.  A seamless portal is not a warp -- it is a
      route through geometry that the map intends you to take, and the timer
      should no more flag it than it flags a doorway.
    * the per-player SV_TeleportBypassed gate.  A portal is geometry now;
      there is no touch to refuse.  startactive 0 (and StartDisabled) is
      handled by simply not creating the portal.

  WHY A THINK.  Spawn order is map order, and a door's partner is as likely to
  come after it as before -- surf_kitsune has both.  A door with no resolved
  partner must stay SOLID_NOT, because a SOLID_PORTAL whose camera_transform
  is 0 faults PR_ExecuteProgram the first time anyone traces near it.
===========================================================================
*/
/*
  Patch 207.  One deferred line, after every door's link think has run, and it
  exists to be COMPARED: the client prints "portals: N with apertures, M
  name-only" from its own independent pass over the same entity lump, and the
  two numbers agreeing is the only cheap evidence that the two sides see the
  same set of portals.  A client that renders an aperture the server will not
  open, or a server that opens one the client draws as a wall, is otherwise
  invisible until somebody walks into it at speed.

  A count that is exactly HALF the door count is the pairing bug Patch 205
  shipped with; short by two or three is a one-way destination.
*/
.float lpd_lastn;	// Patch 207: the reporter is the only user, see below
void() linked_portal_door_report =
{
	/*
	  RE-ARM UNTIL THE COUNT STOPS MOVING.  The first version waited a flat 0.2s
	  and reported "portal doors: 1 linked" on a map with eighteen, because during
	  a map load `time` can jump far enough that every pending think fires in ONE
	  frame, in entity order -- and this reporter, spawned by the first door, has
	  a lower entity number than the seventeen doors whose links it was waiting
	  on.  A longer delay cannot fix an ordering problem; waiting for the number
	  to stop changing can.
	*/
	if (self.lpd_lastn != vbsp_lpd_n + vbsp_lpd_unpaired)
	{
		self.lpd_lastn = vbsp_lpd_n + vbsp_lpd_unpaired;
		self.nextthink = time + 0.25;
		return;
	}

	print(sprintf("portal doors: %g linked%s\n", vbsp_lpd_n,
	              vbsp_lpd_unpaired ? sprintf(", %g with no partner", vbsp_lpd_unpaired) : ""));
	remove(self);
};

void() linked_portal_door_link =
{
	local entity dst;
	local vector ext;

	dst = find(world, targetname, self.partnername);
	if (!dst || !FS_PortalSetup(self, dst))
	{
		dprint(sprintf("linked_portal_door: no partner '%s'\n", self.partnername));
		vbsp_lpd_unpaired = vbsp_lpd_unpaired + 1;
		return;
	}

	/*
	  DO NOT HALVE THESE -- `width` and `height` are already half-extents.
	  momentum.fgd:5366-5372 uses the `orientedwidthheighthalf` helper and names
	  the keys "Half-Width (G)" and "Half-Height (B)", default 128.  The long
	  version of this, with the measurements that caught it, is at the matching
	  site in cl_portal.qc; the two MUST agree, because this one is the teleport
	  acceptance band and that one is what gets drawn.  Halved, the aperture you
	  can see and the aperture you can enter were both a quarter of their real
	  area -- which is why the far view never reached the edges of the doorway.
	*/
	self.lpd_hw = self.width;
	self.lpd_hh = self.height;
	if (self.lpd_hw <= 0) self.lpd_hw = 128;
	if (self.lpd_hh <= 0) self.lpd_hh = 128;

	ext = FS_PortalExtent(self.lpd_fa, self.lpd_ra, self.lpd_ua,
	                      self.lpd_hw, self.lpd_hh);

	// camera_transform BEFORE the entity becomes a portal: setsize links it,
	// and from that moment any trace in the area can reach the transform.
	self.camera_transform = FS_PortalTransform;
	self.movetype = MOVETYPE_NONE;
	self.solid    = SOLID_PORTAL;
	setsize(self, '0 0 0' - ext, ext);
	setorigin(self, self.origin);

	vbsp_lpd_n = vbsp_lpd_n + 1;
};

/*
===========================================================================
  Patch 194 -- linked_portal_door.  443 instances across 18 maps, and without
  it surf_kitsune cannot be finished.

  Patch 191 fixed kitsune's trigger_teleports, and the map still could not be
  completed, because its route does not run on teleports: eighteen
  linked_portal_doors carry it, they had no spawn function, and so they reached
  the catch-all and became SOLID_BSP -- an invisible wall exactly where the way
  through was meant to be.  Counted over the library: surf_tripportals 116,
  bhop_tripportals 54, bhop_flything 50, noneuclidean 43, surf_kitsune2 30,
  bhop_parallel and surf_4plar 20 each, surf_kitsune 18.

  WHAT THE ENTITY IS.  A point entity, not a brush: an `origin`, `angles`, and a
  `width` x `height` rectangle standing in the plane those angles face.  It
  names its opposite number with `partnername`, and the pairing is symmetric --
  A.partnername == B.targetname and B.partnername == A.targetname -- so there is
  nothing to infer.  All 443 write width/height/angles/targetname/startactive;
  440 write partnername.  Yaws are mostly axis aligned (0/90/180/270 on 427 of
  them) but not all: 45, 135, 198.5, 225, 315 and 338.5 all occur, so the
  geometry below is written for an arbitrary orientation rather than for the
  common case.

  THE TRANSFORM is the ordinary portal one: express the player's offset from the
  entry door in that door's own basis, turn it half a revolution about the up
  axis, and read it back out in the exit door's basis.  You leave B travelling
  the way B faces, which is what makes a portal a portal rather than a teleport.
  Velocity and view angles go through the same rotation with the translation
  dropped, so speed is preserved in magnitude and turned in direction -- on a
  surf map that is the whole point, and a teleport that reset either would break
  every route through these maps.

  WHAT THIS WAS NOT, and Patch 205 above is the correction: it was not
  seamless.  You did not see through the doorway, and the crossing happened
  when you touched the volume rather than when you crossed the plane -- which
  is not a missing polish item but the actual bug, because a touch fires
  roughly 32 units early and the mirror turns that into 32 units inside the
  far wall.  The paragraph that used to stand here said seamless "is a bigger
  patch"; it was, and it is Patches 203 and 205.
===========================================================================
*/
void() linked_portal_door =
{
	// SOLID_NOT until the link resolves, and permanently if it does not.  It is
	// also what the entity must be while the rest of the map spawns: anything
	// solid here is an invisible wall standing exactly where the way through is.
	self.movetype = MOVETYPE_NONE;
	self.solid    = SOLID_NOT;
	setorigin(self, self.origin);

	// Patch 207: one reporter for the map, armed by whichever door spawns
	// first and firing after every link think.  See linked_portal_door_report.
	if (!vbsp_lpd_reporter)
	{
		vbsp_lpd_reporter = spawn();
		vbsp_lpd_reporter.classname = "vbsp_lpd_reporter";
		vbsp_lpd_reporter.think     = linked_portal_door_report;
		vbsp_lpd_reporter.nextthink = time + 0.2;
	}

	/*
	  A door with no partnername is a DESTINATION, not a mistake.

	  Three of the library's 443 omit the key, and removing them was wrong: on
	  bhop_aberrant `p2` names `p1` as its partner and `p1` names nobody, so
	  deleting `p1` left `p2` pointing at an entity that no longer existed and
	  broke the pair in the one map that has only one. Source's pairing is
	  one-directional per door, and the second direction is simply absent.

	  So it stays, findable by targetname, with no portal of its own: you can
	  arrive there, you just cannot leave through it.  Counted separately because
	  "this door is one-way" is worth knowing when a route stops working.
	*/
	if (self.partnername == "")
	{
		vbsp_lpd_unpaired = vbsp_lpd_unpaired + 1;
		return;
	}

	/*
	  startactive 0 means the door exists but does nothing.  Patch 194 reused
	  StartDisabled for this because its touch already tested that flag; there is
	  no touch any more, so the honest expression is simply not to build the
	  portal.  Either spelling disables it -- 443 of 443 write startactive, and
	  StartDisabled is the Source key a mapper would reach for.
	*/
	if (self.startactive == 0 || self.StartDisabled)
		return;

	// Resolved next frame: spawn order is map order and the partner is as likely
	// to come after this door as before it.  See linked_portal_door_link.
	self.think     = linked_portal_door_link;
	self.nextthink = time + 0.1;
};

/*
===========================================================================
  trigger_push -- boosters and launchers.  4940 instances, 46.9% of maps.

  Source keys: "pushdir" (a set of ANGLES, converted with AngleVectors),
  "speed" (default 100).  94.1% carry spawnflags 1, which is just
  "Clients" -- the once-flag is 128 and is rare.

  WHAT WAS WRONG.  Both arms used to ASSIGN velocity outright.  Neither of
  Source's two modes does that:

    once (SF_TRIG_PUSH_ONCE)  ApplyAbsVelocityImpulse -- an ADD.  Assigning
                              instead throws away whatever speed you arrived
                              with, so a booster meant to top you up could
                              instead slow you down.  On a surf map, where you
                              may enter a booster at 2000 u/s and its speed is
                              800, that is the difference between a launch and
                              a brake.

    continuous                SetBaseVelocity -- a carrier velocity that rides
                              ON TOP of your own and is recomputed, not
                              accumulated, every tick.  Your own velocity is
                              untouched, so you keep full control inside the
                              volume.  Assigning pinned you to exactly the push
                              vector and took away strafing entirely.

  THIS PARAGRAPH USED TO SAY we could not reproduce the second one, because
  "FTE's Source pmove has no basevelocity concept at all (not one reference in
  pm_source.c)".  THAT WAS WRONG.  There are eleven references: the Z half-step
  in PMSrc_StartGravity, and the add/subtract sandwiches around PMSrc_WalkMove
  and PMSrc_AirMove.  What did not exist was a WRITER -- the only one in the
  engine was Half-Life-specific -- so the field sat permanently at zero and the
  reads were dead code, which is what the grep looked like from here.

  Engine Patch 240 adds the writer: the engine reads .run_basevelocity into
  pmove.basevelocity at the top of the next command and zeroes the field as it
  reads it.  So `continuous` below is now Source's actual SetBaseVelocity, and
  the raise-the-along-component approximation that stood in for it is gone.

  Two things to know about it.  It is a ONE-COMMAND carrier that cannot latch:
  touch re-arms it every command you are inside, and the engine destroys it as
  it consumes it, so nothing has to remember to switch it off.  And it is NOT
  PREDICTED -- basevelocity is not networked, so the client replays unacked
  commands without the push and rubber-bands on entry and exit by roughly
  (speed * unacked time).  Bounded, not cumulative.

  PATCH 249 ADDS THE HALF THIS PARAGRAPH STILL DID NOT HAVE.  Everything above
  is about riding the carrier; none of it is about KEEPING anything.  In Source
  a push volume's horizontal speed becomes real velocity on the way OUT, in
  CheckMovingGround, and until Patch 249 that cash-out did not exist here at
  all -- so a 2000 u/s booster moved you while you were inside it and left you
  with nothing.  See the essay at .run_basevel.
===========================================================================
*/
.vector pushdir;
.float  speed;

/*
  ApplyAbsVelocityImpulse's clamp, which a PUSH_ONCE goes through and the
  continuous branch does not (baseentity_shared.cpp:1121-1142).  Above
  k_flMaxEntitySpeed (4000 = k_flMaxVelocity 2000 * 2) the whole vector is
  rescaled to length 4000; at or above 400000 the impulse is DISCARDED.

  Not theoretical on this library: trigger_push `speed` runs to 999999999999,
  and 247 distinct speeds are in use.  Without this a single one-shot pad on
  one map is an instant out-of-world.
*/
#define PUSH_MAXSPEED    4000
#define PUSH_DISCARD   400000

vector(vector v) SV_ClampImpulse =
{
	local float l;

	l = vlen(v);
	if (l >= PUSH_DISCARD)
	{
		if (SV_CensusAdd("trigger_push impulse discarded"))
			dprint(sprintf("^3trigger_push: impulse %g u/s is over Source's "
			               "%g discard threshold; dropped\n", l, PUSH_DISCARD));
		return '0 0 0';
	}
	if (l > PUSH_MAXSPEED)
		return v * (PUSH_MAXSPEED / l);
	return v;
};

/*
  THE CLASS GATE, which was missing entirely.

  CBaseTrigger::PassesTriggerFilters (triggers.cpp:340-377) tests the touching
  entity's class against the spawnflags BEFORE the filtername is ever consulted,
  and a player needs bit 1 (SF_TRIGGER_ALLOW_CLIENTS) or bit 64
  (SF_TRIGGER_ALLOW_ALL).  100 trigger_push in 39 maps set neither -- they are
  spawnflags 0, 8 (physics only), 12, 1032 or 1036 -- and every one of them has
  been pushing the player here while pushing nothing at all in Source.

  Bit 4096 rejects fake clients; there are none here, so it is named and not
  tested.  Bit 256 ("Affects Ladders") is dead in Momentum -- the whole branch
  is `#if defined( HL2_DLL )` (triggers.cpp:2234-2245) and the mod defines only
  SDK_DLL, so a player on a ladder IS pushed regardless of the flag.
*/
#define SF_TRIGGER_ALLOW_CLIENTS 1
#define SF_TRIGGER_ALLOW_ALL     64

float(entity trig) SV_TriggerTakesPlayers =
{
	return (trig.spawnflags & SF_TRIGGER_ALLOW_CLIENTS) ||
	       (trig.spawnflags & SF_TRIGGER_ALLOW_ALL);
};

void() trigger_push_touch =
{
	local vector dir, push;
	local float  spd;

	if (other.classname != "player")
		return;
	// MOVETYPE_NOCLIP falls into Source's do-nothing arm of the movetype
	// switch (triggers.cpp:2215-2218), so a noclipping player is not pushed.
	if (other.movetype == MOVETYPE_NOCLIP)
		return;
	if (!SV_TriggerTakesPlayers(self))
		return;

	// Build 37.  No push on either bhop map is filtered, so this changes
	// nothing today; it is here because a filter is a property of the TRIGGER
	// base class in Source, and applying it to one subclass and not another is
	// how the next map's boosters end up firing for the wrong player.
	if (!SV_PassesFilter(self, other))
		return;

	SV_TriggerIOTouch(self, other);

	makevectors(self.pushdir);
	dir = v_forward;                    // unit; `speed` is applied below

	/*
	  THE OTHER SPELLING, and this one was live.  885 trigger_push entities
	  write "Speed" with a capital S against 4608 that write "speed", and this
	  function read `self.speed` bare -- so about 16% of every push in the
	  library silently fell back to the default of 100 and did essentially
	  nothing.  `.Speed` was declared at :137 and read NOWHERE.  That is exactly
	  the failure the SV_Key2 essay at :96 exists to prevent, in the one place
	  that never used it.
	*/
	spd = SV_Key2(self.speed, self.Speed);
	if (!spd)
		spd = 100;

	if (self.spawnflags & SF_PUSH_ONCE)
	{
		/*
		  ApplyAbsVelocityImpulse: a genuine one-shot ADD to your own velocity,
		  deliberately not basevelocity -- this one is meant to stay with you
		  after the trigger is gone.

		  Source tests the UNIT direction's Z here, not the scaled push, and it
		  does NOT do the one-unit lift the continuous branch does
		  (triggers.cpp:2201-2211).  Both asymmetries are deliberate in the
		  original and both are copied.
		*/
		if (dir_z > 0)
			other.flags = other.flags - (other.flags & FL_ONGROUND);

		other.velocity = other.velocity + SV_ClampImpulse(dir * spd);
		self.touch = SUB_Null;
		self.solid = SOLID_NOT;
		return;
	}

	/*
	  SetBaseVelocity, and now with the flag that makes it mean something.

	  A carrier that rides on top of your own velocity: the engine adds it
	  before the move and subtracts it after, so your own velocity is untouched
	  and you keep full strafe control inside the volume.  What Patch 240 left
	  out is that the horizontal part is not spent by being ridden -- it is
	  CASHED OUT into real velocity on the first command after you stop being
	  re-armed, i.e. on the way out.  See the essay at .run_basevel.

	  THE ACCUMULATE IS WITHIN ONE COMMAND, NOT ACROSS THEM.  Source folds the
	  existing carrier in only when FL_BASEVELOCITY is already set
	  (triggers.cpp:2248-2251), and the flag is cleared at the top of every
	  command -- so two OVERLAPPING push volumes sum in the tick they both
	  touch, and one volume touching for a hundred commands does not compound.
	  Getting that backwards is a rocket.
	*/
	push = dir * spd;
	if (other.run_basevel_armed)
		push = push + other.run_basevel;

	// Tested AFTER the accumulate, on the net push, and it does two things:
	// clears the ground flag and lifts you one unit.  Without the lift the
	// ground check re-grounds you on the very command the push is applied.
	if (push_z > 0 && (other.flags & FL_ONGROUND))
	{
		other.flags = other.flags - FL_ONGROUND;
		setorigin(other, other.origin + '0 0 1');
	}

	other.run_basevel = push;
	other.run_basevel_armed = TRUE;
};

void() trigger_push =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	/*
	  The default is applied IN THE TOUCH, not here, and that is not a style
	  choice.  This used to read `if (!self.speed) self.speed = 100;`, which
	  writes 100 into `.speed` for every entity that spelled the key `Speed`
	  instead -- and SV_Key2(self.speed, self.Speed) would then find a non-zero
	  `.speed` and return the default, permanently shadowing the 885 entities
	  the capital spelling was added to rescue.

	  100 is right, incidentally, and the FGD's suggested 40 is not: Source's
	  CTriggerPush::Spawn applies 100 when the key is absent, and an already
	  compiled map that omitted the key is asking for the code default.
	*/
	SV_BindInvisibleBrush();
	self.movetype = MOVETYPE_NONE;
	self.solid = SOLID_BSPTRIGGER;
	self.touch = trigger_push_touch;

	/*
	  FTESurf Patch 256.  StartDisabled, which this class never read.

	  trigger_teleport has honoured it since Build 37 and trigger_push did not,
	  which is the asymmetry that makes a map behave differently depending on
	  which kind of volume the mapper reached for.  176 pushes across 63 maps
	  set it, and every one of them has been pushing from the first frame while
	  Source waits for an Enable.

	  vbsp_io_solid is what lets SV_IOEnable put it BACK as a trigger rather
	  than flattening it to SOLID_BSP, which would turn a booster into a wall.
	*/
	self.vbsp_io_solid = SOLID_BSPTRIGGER;
	if (SV_Key2(self.StartDisabled, self.startdisabled))
		self.solid = SOLID_NOT;
};

/*
===========================================================================
  FTESurf Patch 256 -- trigger_setspeed.  372 instances across 94 maps, and
  until now every one of them spawned inert.

  It has no spawn function, so it took the `trigger_` prefix arm of
  SV_OnEntityNoSpawnFunction, lost its model and returned -- WITHOUT the
  "unknown and owns brushes" warning, because that arm returns before the
  dprint.  That silence is why it survived this long: surf_bossfight's start
  pads, surf_prosurf's and 92 other maps' just did nothing, and nothing said so.

  TWO DIALECTS ARE LIVE IN THE LIBRARY and a build that handles one of them
  gets most of the maps wrong.  Censused across all 1310:

    mode dialect      HorizontalSpeedMode / VerticalSpeedMode / HorizontalSpeed
                      / VerticalSpeed / HorizontalSpeedAngle / StrictMode
                      205 entities, 83 maps           <- the shipped FGD
    boolean dialect   keephorizontalspeed / keepverticalspeed /
                      horizontalspeedamount / verticalspeedamount / direction
                      / onthink / interval / everytick
                      167 lowercase (9 maps) + 7 capitalised (3 maps)

  The old one is this engine tree's own momentum.fgd; the new one is the FGD
  shipped with the playtest build.  They are the same entity, so the old keys
  are mapped onto the new modes below rather than given a second code path.

  MODES, from the shipped FGD (momentum/momentum.fgd, trigger_setspeed):
    HorizontalSpeedMode  0 set exact speed AND direction (yaw of the angle key)
                         1 set exact speed, keep current direction
                         2 increase only      3 decrease only      4 ignore
    VerticalSpeedMode    1 set exact          2 increase only
                         3 decrease only      4 ignore   (this one defaults to 4)
  Vertical increase/decrease are SIGNED, not magnitudes -- the FGD spells it
  out: "Decrease only with a speed of -500 will ensure an entity is moving at
  least 500 units/sec downward".  So they are max() and min() on the signed z,
  while the horizontal pair work on the SPEED, which is a length.

  THE DEFAULTS ARE THE TRAP.  A mode key that is absent reads as 0, and 0 is a
  valid HORIZONTAL mode ("set exact speed and direction") but not a valid
  VERTICAL one -- vertical starts at 4, Ignore.  So an old-dialect entity, which
  writes no mode keys at all, would silently be read as "set horizontal to 0"
  and stop the player dead.  The dialect has to be decided before the modes are.

  This is SetAbsVelocity, not a carrier: it is written straight to .velocity and
  deliberately NOT routed through .run_basevel.  A basevelocity carrier is
  cashed out and can be ridden; this is the map saying what your speed IS.

  NOT IMPLEMENTED, and censused rather than dropped: StrictMode (155 entities,
  113 of them on), which in Source additionally requires you to enter grounded
  and un-teleported, snaps you to the trigger edge and blocks ducking inside.
===========================================================================
*/
.float  HorizontalSpeedMode;
.float  HorizontalSpeed;
.vector HorizontalSpeedAngle;
.float  VerticalSpeedMode;
.float  VerticalSpeed;
.float  StrictMode;

.float  keephorizontalspeed;    .float KeepHorizontalSpeed;
.float  keepverticalspeed;      .float KeepVerticalSpeed;
.float  horizontalspeedamount;  .float HorizontalSpeedAmount;
.float  verticalspeedamount;    .float VerticalSpeedAmount;
.vector direction;              .vector Direction;
.float  onthink;                .float OnThink;
.float  interval;               .float Interval;
.float  everytick;              .float EveryTick;

.float  vbsp_ss_stamp;          // last touch, for the enter edge
.float  vbsp_ss_applied;        // last time the speed was actually written

#define SSH_SETDIR   0
#define SSH_SETSPEED 1
#define SSV_SET      1
#define SS_INCREASE  2
#define SS_DECREASE  3
#define SS_IGNORE    4

void() trigger_setspeed_touch =
{
	local float  hmode, vmode, hspeed, vspeed, cur, iv, old;
	local vector ang, dir, vel;

	if (other.classname != "player")
		return;
	if (other.movetype == MOVETYPE_NOCLIP)
		return;
	if (!SV_TriggerTakesPlayers(self))
		return;
	if (!SV_PassesFilter(self, other))
		return;

	SV_TriggerIOTouch(self, other);

	/*
	  WHEN it applies.  Momentum's default is the ENTER edge only; OnThink
	  re-applies every Interval while you are inside, and EveryTick re-applies
	  every frame.  A QC .touch runs every frame you overlap, so without this
	  the default case would pin the player at the pad's speed for as long as
	  they were in the volume -- which on bossfight's 5000 u/s start pads is
	  the difference between a launch and a rail.

	  0.05 is the same staleness window SV_TriggerEndThink uses to synthesise
	  an end-touch, for the same reason: it is comfortably longer than a frame
	  and comfortably shorter than a re-entry.
	*/
	old = self.vbsp_ss_stamp;
	self.vbsp_ss_stamp = time;
	iv = SV_Key2(self.Interval, self.interval);
	if (iv <= 0)
		iv = 1;

	if (time - old <= 0.05)						// not the enter edge
	{
		if (!SV_Key2(self.EveryTick, self.everytick))
		{
			if (!SV_Key2(self.OnThink, self.onthink))
				return;							// enter-only: nothing more to do
			if (time - self.vbsp_ss_applied < iv)
				return;							// OnThink, but not due yet
		}
	}
	self.vbsp_ss_applied = time;

	if (self.StrictMode)
		if (SV_CensusAdd("trigger_setspeed StrictMode"))
			dprint("^3trigger_setspeed: StrictMode is not implemented -- the pad "
			       "fires without Source's grounded/edge-snap/no-duck conditions\n");

	/*
	  DIALECT.  The old one always writes interval and onthink and everytick
	  (167 of 167 lowercase, 7 of 7 capitalised) and the new one writes none of
	  them, so Interval is a reliable discriminator; the amount and keep keys
	  back it up for anything that somehow omitted it.
	*/
	if (SV_Key2(self.Interval, self.interval)      != 0 ||
	    SV_Key2(self.HorizontalSpeedAmount, self.horizontalspeedamount) != 0 ||
	    SV_Key2(self.VerticalSpeedAmount, self.verticalspeedamount)     != 0 ||
	    SV_Key2(self.KeepHorizontalSpeed, self.keephorizontalspeed)     != 0 ||
	    SV_Key2(self.KeepVerticalSpeed, self.keepverticalspeed)         != 0)
	{
		hspeed = SV_Key2(self.HorizontalSpeedAmount, self.horizontalspeedamount);
		vspeed = SV_Key2(self.VerticalSpeedAmount, self.verticalspeedamount);
		ang    = self.Direction + self.direction;   // one of the two is zero
		hmode  = SV_Key2(self.KeepHorizontalSpeed, self.keephorizontalspeed) ? SS_IGNORE : SSH_SETDIR;
		vmode  = SV_Key2(self.KeepVerticalSpeed, self.keepverticalspeed)     ? SS_IGNORE : SSV_SET;
	}
	else
	{
		hspeed = self.HorizontalSpeed;
		vspeed = self.VerticalSpeed;
		ang    = self.HorizontalSpeedAngle;
		hmode  = self.HorizontalSpeedMode;
		// 0 is not a vertical mode; an absent key means the FGD default, Ignore.
		vmode  = self.VerticalSpeedMode;
		if (vmode == 0)
			vmode = SS_IGNORE;
	}

	vel = other.velocity;
	cur = vlen([vel_x, vel_y, 0]);

	if (hmode != SS_IGNORE)
	{
		/*
		  Direction.  Mode 0 takes it from the angle key -- YAW ONLY, the FGD is
		  explicit, because pitch would fight the vertical half.  The others keep
		  the direction you arrived with, and fall back to the player's own
		  facing when you arrived with no horizontal speed at all (also the FGD:
		  "if the entity has no horizontal speed, its rotation is used").
		*/
		if (hmode == SSH_SETDIR)
		{
			makevectors([0, ang_y, 0]);
			dir = v_forward;
		}
		else if (cur > 0)
			dir = normalize([vel_x, vel_y, 0]);
		else
		{
			makevectors([0, other.angles_y, 0]);
			dir = v_forward;
		}

		if (hmode == SS_INCREASE)      { if (cur < hspeed) cur = hspeed; }
		else if (hmode == SS_DECREASE) { if (cur > hspeed) cur = hspeed; }
		else                             cur = hspeed;

		vel_x = dir_x * cur;
		vel_y = dir_y * cur;
	}

	// Signed, not magnitude -- see the essay.
	if (vmode == SSV_SET)           vel_z = vspeed;
	else if (vmode == SS_INCREASE)  { if (vel_z < vspeed) vel_z = vspeed; }
	else if (vmode == SS_DECREASE)  { if (vel_z > vspeed) vel_z = vspeed; }

	other.velocity = vel;
};

void() trigger_setspeed =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	/*
	  0 must reproduce the PREVIOUS build exactly, and "previous" is the
	  `trigger_` arm of SV_OnEntityNoSpawnFunction -- which strips the model and
	  modelindex, goes SOLID_NOT and RETURNS, keeping the edict.  It does not
	  remove.  Removing here instead would move ent_census on 94 maps and drop
	  any outputs hanging off the trigger, so the switch would not be a
	  bisection switch.
	*/
	if (!cvar("run_setspeed"))
	{
		self.model = "";
		self.modelindex = 0;
		self.solid = SOLID_NOT;
		self.movetype = MOVETYPE_NONE;
		return;
	}
	SV_BindInvisibleBrush();
	self.movetype = MOVETYPE_NONE;
	self.solid = SOLID_BSPTRIGGER;
	self.touch = trigger_setspeed_touch;

	// bossfight's b_booster is a one-shot: it fires `!self,Disable` at itself
	// 0.01s after the start touch.  Without vbsp_io_solid the Enable that some
	// other map pairs with that would bring it back as SOLID_BSP -- a wall.
	self.vbsp_io_solid = SOLID_BSPTRIGGER;
	if (SV_Key2(self.StartDisabled, self.startdisabled))
		self.solid = SOLID_NOT;
};

// Same entity under Momentum's own prefix.
void() trigger_momentum_setspeed = { trigger_setspeed(); };

/*
===========================================================================
  Ladders -- and why there is no spawn function here any more.

  There were three separate surprises, and together they move this out of
  entity code entirely.

  1. func_ladder DOES NOT EXIST in a compiled map.  A census of all 1308 maps
     found ZERO instances.  VBSP consumes it at compile time: the brushes go
     into the world with Source's CONTENTS_LADDER bit set, and all that is
     left behind is an info_ladder bbox marker (556 of those, in 132 maps).
     The spawn function that used to be here could never once have been
     called.

  2. The contents ALREADY ARRIVE CORRECTLY.  The hl2 plugin's default
     contents table maps Source bit 29 straight through -- the entry commented
     "ladder" in hl2_contents_remap resolves to LADDER (mod_vbsp.c:4780) -- so
     those brushes already report FTECONTENTS_LADDER to every trace.  Nothing
     in QC needs to mark them, and info_ladder is a marker for AI navigation
     that we have no use for.

  3. And yet ladders still do not work, because FTE's Source movement code
     never looks: pm_source.c contains no reference to LADDER of any kind.
     Q1 pmove has ladder handling; PMSrc does not.

  So a working ladder is a pmove patch, not an entity -- and pmove is the one
  file where a mistake costs every player every tick, in BOTH games sharing
  this engine tree.  It is deliberately not bundled with an entity build.
  Deferred, written down, and cheap when it happens: the contents are already
  in the trace results waiting to be read.
===========================================================================
*/

/*
===========================================================================
  Static brush entities.

  Spawn state only, by design: solidity / StartDisabled / spawnflags are read
  once and then frozen.  Source's entity I/O (an Enable input arriving from a
  logic_relay four hops away) is not modelled, so anything that would have
  toggled at runtime keeps whatever it started as.  On a surf map that is the
  right trade: the geometry you are surfing on is placed at spawn, and the
  things that move are decoration.
===========================================================================
*/

// func_wall -- "Legacy support for Half-Life" (momentum.fgd:4742), and still
// the most common solid brush in older surf maps.  Always solid, never moves.
void() func_wall =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	setmodel(self, self.model);
	self.movetype = MOVETYPE_PUSH;
	self.solid = SOLID_BSP;
};

/*
  func_brush -- the modern one (momentum.fgd:8615).

    solidity 0  "Toggle with Enable/Disable"  -> follow StartDisabled
    solidity 1  "Never Solid"
    solidity 2  "Always Solid"

  StartDisabled on a func_brush means BOTH invisible and non-solid, not just
  non-solid: a disabled brush is not drawn.  Getting that wrong leaves ghost
  walls you can see and walk through, which reads as a renderer bug.
*/
void() func_brush =
{
	local float solid_now, sol, dis;

	if (!self.model)
	{
		remove(self);
		return;
	}
	setmodel(self, self.model);
	self.movetype = MOVETYPE_PUSH;

	// Both spellings -- see THE OTHER SPELLING above.  SOLIDITY_TOGGLE is 0,
	// which is also what an absent key reads as, so the pick loses nothing.
	sol  = SV_Key2(self.Solidity, self.solidity);
	dis  = SV_Key2(self.StartDisabled, self.startdisabled);

	if (sol == SOLIDITY_NEVER)
		solid_now = FALSE;
	else if (sol == SOLIDITY_ALWAYS)
		solid_now = TRUE;
	else
		solid_now = !dis;

	self.solid = solid_now ? SOLID_BSP : SOLID_NOT;

	if (dis)
		self.effects = self.effects | EF_NODRAW;

	// Build 37.  "Toggle with Enable/Disable" is what solidity 0 has always
	// SAID, and until entity I/O existed there was nothing that could toggle
	// it -- a func_brush with StartDisabled was gone for the whole map.
	self.vbsp_io_solid = SOLID_BSP;
};

/*
===========================================================================
  FTESurf Patch 256 -- func_rotating, the biggest surviving repeat of the
  func_dustmotes bug, and it needed a spawnflag test rather than a list entry.

  The "unknown and owns brushes -- made SOLID" line has been printing on
  func_rotating for the whole life of that diagnostic, and the advice it gives
  ("it belongs in the non-solid list") is WRONG.  Source's CFuncRotating::Spawn
  (bmodels.cpp:618-632) is:

      SetSolid( SOLID_VPHYSICS );
      if ( HasSpawnFlags(SF_ROTATING_NOT_SOLID) )
          AddSolidFlags( FSOLID_NOT_SOLID );
      SetMoveType( MOVETYPE_PUSH );

  -- solid by default, non-solid only on spawnflag 64, whose own comment names
  the case: "some special rotating objects are not solid" / fake volumetric
  lights (bmodels.cpp:21, :620-621).  A blanket list entry would have unwalled
  1614 brushes correctly and turned 1323 real walls into holes.

  CENSUS, all 1310 maps: 2937 func_rotating own a `*` model across 372 maps.
  1614 of them, across 262 maps, carry bit 64 and have been invisible walls
  here.  A separate brush walk over 258 of those 262 maps found 1532 of 1582
  models (96.8%) carrying player-blocking contents, so this is not a paper
  count -- they really do stop you.

  KEEP THE MODEL IN BOTH BRANCHES.  Source's non-solid rotator is still drawn;
  that is the entire point of the fake-volumetric-light case.  Putting it in
  the non-solid list would have made it invisible as well, which is the second
  reason the list was the wrong place.

  NOT ROTATING IT.  Frozen at spawn is the same trade SV_SpawnDoor documents,
  and a rotating SOLID_BSP under FTE's pusher is a separate question about
  whether it carries a standing player.  2803 of the 2937 also write
  `solidbsp 0`, which in Source leaves SOLID_VPHYSICS rather than SOLID_BSP --
  still solid, so it changes nothing for us, but the key is there and a future
  reader will find it and wonder.
===========================================================================
*/
#define SF_ROTATING_NOT_SOLID 64        // bmodels.cpp:21

void() func_rotating =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	setmodel(self, self.model);
	self.movetype = MOVETYPE_PUSH;          // bmodels.cpp:626/631, both branches
	self.solid = (self.spawnflags & SF_ROTATING_NOT_SOLID) ? SOLID_NOT : SOLID_BSP;
	self.vbsp_io_solid = self.solid;
};

/*
  func_clip_vphysics -- the one outright bug on the unknown-brush list, and it
  is the opposite of a missing wall.

  bmodels.cpp:1337-1346:  SetSolid( SOLID_VPHYSICS ); AddSolidFlags(
  FSOLID_NOT_SOLID ); SetModel(...); AddEffects( EF_NODRAW );  -- and it only
  ever collides things that pass EntityPassesFilter (:1366-1379), which is
  MOVETYPE_VPHYSICS movable objects.  A player walks straight through it and
  cannot see it.  Here it has been a VISIBLE SOLID WALL: 55 brushes on 8 maps.
*/
void() func_clip_vphysics =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	setmodel(self, self.model);
	self.movetype = MOVETYPE_NONE;
	self.solid = SOLID_NOT;
	self.effects = self.effects | EF_NODRAW;
};

/*
  Three that are literally subclasses of things already implemented, so the
  alias IS the port rather than an approximation of it:

    class CFuncReflectiveGlass : public CFuncBrush   (func_reflective_glass.cpp:13)
    class CFuncMonitor          : public CFuncBrush   (hl2/Func_Monitor.cpp)

  They inherit func_brush's Solidity/StartDisabled ladder verbatim, and 29 of
  148 func_reflective_glass plus 7 of 24 func_monitor write `Solidity 1` =
  Never Solid.  Those 36 are walk-through mirrors and screens in Source and
  have been solid walls here.
*/
void() func_reflective_glass  = { func_brush(); };
void() func_monitor           = { func_brush(); };

/*
  func_conveyor -- `class CFuncConveyor : public CFuncWall` (bmodels.cpp:190),
  so solid by default, non-solid only under SF_CONVEYOR_NOTSOLID
  (bmodels.cpp:188, tested at :251).  355 instances / 89 maps.

  The SOLIDITY is all this does.  Source also sets FL_CONVEYOR (bmodels.cpp:248)
  and gives the player the belt's ground velocity, which is a MOVEMENT feature
  and not a spawn one -- it belongs with the pmove work, not here.  Naming it
  rather than leaving it in the catch-all is the point: the "unknown and owns
  brushes" warning is only useful while it means "nobody has looked at this",
  and a class we have looked at and deliberately half-implemented should not be
  in it.
*/
#define SF_CONVEYOR_NOTSOLID 2          // bmodels.cpp:188

void() func_conveyor =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	setmodel(self, self.model);
	self.movetype = MOVETYPE_PUSH;
	self.solid = (self.spawnflags & SF_CONVEYOR_NOTSOLID) ? SOLID_NOT : SOLID_BSP;
	self.vbsp_io_solid = self.solid;
};

/*
  The rest of the brush movers, named and frozen.

  Every one of these is verified solid in its own game and already ended up
  SOLID_BSP by way of the catch-all, so these change NO behaviour -- they only
  take 4,500-odd entities out of a warning whose whole value is that it lists
  things nobody has checked.  func_lod is the loudest at 1960 instances across
  52 maps, and it is `SetModel(...); SetSolid( SOLID_BSP ); CreateVPhysics()`
  at func_lod.cpp:73-79, i.e. correct as it stood.

  Frozen at spawn is the same trade SV_SpawnDoor documents: what moves on a surf
  map is decoration, and the geometry you surf on is placed at spawn.
*/
/*
===========================================================================
  FTESurf Patch 257 -- the movers Source lets you fly through, and the same
  shape of bug Patch 256 fixed for func_rotating.

  These seven all aliased func_wall(), which is unconditional SOLID_BSP, so
  none of them read a spawnflag.  Four of them have a "not solid" bit and it
  is the same bit in all four:

      func_movelinear   SF_MOVELINEAR_NOTSOLID 8   func_movelinear.cpp:22
      func_train        SF_TRACKTRAIN_PASSABLE 8   trains.h:26, CFuncTrain::Spawn
                                                   trains.cpp:1039,1061
      func_tracktrain   SF_TRACKTRAIN_PASSABLE 8   trains.cpp:2693
      func_tanktrain    SF_TRACKTRAIN_PASSABLE 8   CFuncTankTrain : CFuncTrackTrain,
                                                   tanktrain.cpp:40,71 -- its Spawn
                                                   is BaseClass::Spawn()

  Each does SetSolid(...) then SetModel(...) then AddSolidFlags(FSOLID_NOT_SOLID)
  on the bit.  KEEP THE MODEL IN BOTH BRANCHES, for the reason Patch 256 gives:
  Source's non-solid mover is still drawn, and dropping it would trade a wall
  you cannot walk through for a wall you cannot see.

  CENSUS, all 1310 maps, brush-owning instances / of those, bit 8 set:

      func_movelinear   1563 / 507 across 63 maps
      func_tracktrain    547 / 353 across 38 maps
      func_tanktrain     249 /  65 across 15 maps
      func_train           3 /   2 across  1 map

  927 brush entities that Source walks through and this game has been stopping
  you on.  surf_garden's "frogy" (*234, spawnflags 8) is one of them.

  func_lod is left alone deliberately: all 1960 in the library write
  spawnflags 0, so there is nothing to read.  momentary_rot_button and
  button_target are buttons, not movers, and keep func_wall's behaviour.
===========================================================================
*/
#define SF_MOVELINEAR_NOTSOLID  8       // func_movelinear.cpp:22
#define SF_TRACKTRAIN_PASSABLE  8       // trains.h:26

void(float notsolidbit) SV_SpawnPassableBrush =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	setmodel(self, self.model);
	self.movetype = MOVETYPE_PUSH;
	self.solid = (self.spawnflags & notsolidbit) ? SOLID_NOT : SOLID_BSP;
	// As func_rotating and func_brush do: remember what solid we chose, so a
	// later Enable input restores THIS and not SOLID_NOT-by-default.
	self.vbsp_io_solid = self.solid;
};

void() func_lod              = { func_wall(); };
void() func_movelinear       = { SV_SpawnPassableBrush(SF_MOVELINEAR_NOTSOLID); };
void() func_tracktrain       = { SV_SpawnPassableBrush(SF_TRACKTRAIN_PASSABLE); };
void() func_tanktrain        = { SV_SpawnPassableBrush(SF_TRACKTRAIN_PASSABLE); };
void() func_train            = { SV_SpawnPassableBrush(SF_TRACKTRAIN_PASSABLE); };
void() momentary_rot_button  = { func_wall(); };
void() button_target         = { func_wall(); };
//func_physbox_multiplayer lives beside func_physbox below -- QC needs the
//callee defined first, and func_physbox is defined after this point.

/*
  func_slide -- 702 instances across 17 library maps (decompressed-lump census,
  Patch 280; the earlier "514 on four maps" here was a raw-lump undercount, the
  trap the vbsp-lumps-are-compressed note describes).  bhop_aberrant alone is
  484 of them and is nothing but slides; then rj_tattarrattat 58,
  bhop_retrowave 31, bhop_everfast 21, bhop_ithyphallophobia 19,
  bhop_mom_training_beta 19, surf_mom_training 16, bhop_frigpx 12,
  bhop_2shiny2shuckle 7, bhop_arcane 7, bhop_tripportals 7, surf_skatelife 7,
  surf_skatelife1 7, surf_tripportals 3, surf_huecomundo 2, bhop_bowling 1,
  surf_4plar 1.

  The shipped FGD (momentum.fgd:10041 in the Steam install; it is NOT in the
  public game-develop tree, whose slide is the trigger_momentum_slide volume):
  "a brush entity the player will slide on like a surf ramp, even at shallow
  angles.  Ducking and unducking while sliding work the same as when on normal
  ground."  Three keys, every one written lowercase and lowercase only
  (case-preserving check across all 702):

      stayonslide      251 written (35 are 1)     absent on the other 451
      allowjump        702 written (21 are 1)     FGD default 1 -- see below
      disablegravity   251 written ( 2 are 1)

  SPAWNING: base(func_brush), so the same Solidity / StartDisabled handling.
  All 702 spawn solid: startdisabled is written 251 times, always 0; 48 say
  solidity 2 and 200 say 0.  One is named, so I/O can still disable it, which
  is why SV_IOEnable handles the tag.

  SLIDING: the engine's Source mover reads the tag (pm_source.c, Patch 280,
  behind pm_slide).  A ground probe that lands on a slide brush never grounds,
  so there is no friction and no WalkMove -- gravity is clipped along the face
  each tick exactly as on a ramp steeper than 45 degrees.  allowjump lets a
  +jump ground for the one tick it needs; stayonslide snaps you back onto a
  face that curves away; disablegravity skips both gravity half-steps while
  in contact.

  allowjump is read as a STRING so an absent key can take the FGD's default of
  1 rather than 0 -- the SV_KeyTri reasoning above.  No shipped map leaves it
  absent, so today this changes nothing; it is there so the next map cannot be
  wrong.
*/
.float  stayonslide;
.string allowjump;
.float  disablegravity;

void() func_slide =
{
	local float f;

	if (!self.model)
	{
		remove(self);
		return;
	}
	func_brush();

	f = 0;
	if (self.stayonslide)
		f = f | SLIDE_STAYON;
	if (self.allowjump == "" || stof(self.allowjump) != 0)
		f = f | SLIDE_ALLOWJUMP;
	if (self.disablegravity)
		f = f | SLIDE_NOGRAVITY;

	self.vbsp_slide_skin = SKIN_SLIDE_BASE + f;
	if (self.solid != SOLID_NOT)
		self.skin = self.vbsp_slide_skin;
};

/*
  Doors.

  3485 func_door + 461 func_door_rotating, across 14.4% and 6.8% of maps.
  They reached the catch-all before this and came out SOLID_BSP, frozen at
  their spawn position -- which is very nearly right, and wrong in one
  specific way that matters.

  Source has two spawnflags that make a door NOT COLLIDE WITH THE PLAYER at
  all: bit 4 "Non-solid to Player" (287 doors) and bit 8 "Passable" (213).
  Roughly 500 doors in the library are meant to be walked straight through,
  and every one of them was a solid wall.  That is the sort of bug that reads
  as a blocked route rather than as a door.

  WHAT IS STILL NOT DONE, deliberately: opening.  58.2% carry bit 1024,
  "Touch Opens", and could in principle be driven from a touch function --
  movedir, lip, speed and wait are all present on essentially every door.  It
  is not in this build because a door frozen SHUT is visually and physically
  the state Source shows before you touch it, so nothing looks wrong, whereas
  a door that moves can crush a player, strand one inside it, or open into the
  route.  Weighed against that: doors that START open are 6 instances in 3946,
  and spawnpos 1 is another 18 -- so the frozen position is correct for 99.4%
  of them.  Movement belongs with the entity I/O work, not bolted on here.
*/
#define SF_DOOR_NONSOLID_TO_PLAYER  4
#define SF_DOOR_PASSABLE            8

/*
===========================================================================
  BUILD 63, TIER 2 -- BUTTON AND DOOR STATE.  STILL NOTHING MOVES.

  The rule is stated in full beside the vbsp_mv_* field block: fire what is
  true of the state machine, never what is a claim about geometry.  So a button
  presses, latches, waits and returns, firing OnPressed / OnIn / OnOut; a door
  locks, unlocks and is told to open, firing OnLockedUse / OnOpen / OnClose;
  and neither ever claims to have ARRIVED anywhere, because neither has moved.

  WHY THE TIMING USES .ltime AND NOT time, which is the trap in this whole
  section and would otherwise be found the hard way.

  sv_defs.qc:302 states the contract: on MOVETYPE_PUSH, .nextthink is relative
  to .ltime, not to time.  Every existing think in this project is written
  `nextthink = time + x` and every one of those is on a POINT entity, where
  that is correct.  A button is MOVETYPE_PUSH.

  Worse, .ltime on these entities is frozen at 0 and always has been.
  WPhys_Physics_Pusher (sv_phys.c:1211-1222) clips this frame's movetime to
  nextthink - ltime, and with nextthink 0 -- which is every brush entity in
  every FTESurf map today -- movetime clamps to 0, PushMove is skipped, and
  ltime never advances.  So `nextthink = time + dt` on a button would schedule
  a think for when the SERVER'S UPTIME reaches dt: never, on any map loaded
  more than dt seconds into the process.  Silent, and it would look like the
  button simply not working.

  Tier 2 uses ltime even though nothing moves, so that the scheduling is
  already proven if geometry is ever added.

  THE ONE EXCEPTION is the OnUseLocked debounce, which is wall-clock: it
  rate-limits a PLAYER ACTION, not a mover.
===========================================================================
*/
void(entity t, void() fn, float dt) SV_MoverArm =
{
	t.think = fn;
	t.nextthink = t.ltime + dt;		// ltime.  NEVER time.  See above.
};

/*
  Lock / Unlock -- 1,292 and 752 fires at func_button/func_rot_button across
  116 and 14 maps, plus ~130 at doors.

  m_bLocked is SEEDED by SF_DOOR_LOCKED at spawn (doors.cpp:290-292,
  buttons.cpp:414-417) and is not the same thing as the spawnflag: InputUnlock
  clears the flag, the spawnflag stays set forever.  Reading the spawnflag
  where Source reads m_bLocked is precisely the bug this fixes in SV_UseFrame.
*/
void(entity t, float on) SV_MoverLock =
{
	if (!t.vbsp_mv_kind)
		return;						// not a button or a door; say nothing
	t.vbsp_mv_locked = on ? TRUE : FALSE;
};

/*
  OnUseLocked, with Source's own 0.5s refire guard (buttons.cpp:484-496).

  On `time` rather than ltime, deliberately -- see the ltime essay above.  This
  bounds how often a player holding +use against a locked button can make the
  map talk, which is a question about the player's hand, not about a mover.
*/
void(entity t, entity act) SV_MoverOnUseLocked =
{
	if (time <= t.vbsp_mv_uselocked)
		return;
	t.vbsp_mv_uselocked = time + 0.5;
	SV_FireOutput(t, "OnUseLocked", act);
};

// Forward-declared so ButtonAtTop can arm ButtonReturn and ButtonReturn can
// arm ButtonHome; QC resolves names in file order, and these are a cycle.
void() SV_ButtonReturn;

void() SV_ButtonAtTop =
{
	// TriggerAndWait, buttons.cpp:693-732.  Re-tests the lock, because a Lock
	// can arrive while the button is on its way in.
	if (self.vbsp_mv_locked)
		return;

	self.vbsp_mv_state = TS_AT_TOP;
	self.nextthink = 0;

	// A "stay pushed" button (wait -1) or a toggle button never comes back on
	// its own, so nothing is armed and OnOut will only follow another press.
	if (!self.vbsp_mv_stay)
	if (!(self.spawnflags & SF_BUTTON_TOGGLE))
		SV_MoverArm(self, SV_ButtonReturn, self.vbsp_mv_wait);

	// After the re-arm, as Source does.  392 OnIn outputs across 38 maps.
	SV_FireOutput(self, "OnIn", self.vbsp_mv_act);
};

void() SV_ButtonHome =
{
	// ButtonBackHome, buttons.cpp:757-783.
	self.vbsp_mv_state = TS_AT_BOTTOM;
	self.nextthink = 0;
	SV_FireOutput(self, "OnOut", self.vbsp_mv_act);
};

void() SV_ButtonReturn =
{
	self.vbsp_mv_state = TS_GOING_DOWN;
	SV_MoverArm(self, SV_ButtonHome, self.vbsp_mv_travel);
};

void() SV_ButtonActivate =
{
	self.vbsp_mv_state = TS_GOING_UP;
	SV_MoverArm(self, SV_ButtonAtTop, self.vbsp_mv_travel);
};

/*
  self-swapping wrappers, because the two above are used BOTH as .think targets
  (which must be void() and read self) and as calls against an arbitrary entity
  from the input ladder.  QuakeC has no other way to say "run this think body on
  that entity", and forgetting to restore self is a classic way to corrupt the
  caller -- SV_ApplyInput is often reached from inside a touch.
*/
void(entity t) SV_ButtonActivate1 =
{
	local entity o;
	o = self; self = t; SV_ButtonActivate(); self = o;
};

void(entity t) SV_ButtonReturn1 =
{
	local entity o;
	o = self; self = t; SV_ButtonReturn(); self = o;
};

/*
  CBaseButton::Press, buttons.cpp:199-252.

  The three guard clauses at :201-214 are not interchangeable and collapsing
  them would be wrong in a way nobody would notice for a year: BUTTON_PRESS
  toggles, BUTTON_ACTIVATE only ever goes in, BUTTON_RETURN only ever comes out.

  LOCKED IS SILENT HERE, and that asymmetry is Source's.  Press() plays a lock
  sound and returns (:217-222) firing NOTHING; m_OnUseLocked is fired only from
  OnUseLocked(), which only ButtonUse reaches (:484-496, called at :515).  So a
  Press input at a locked button says nothing and a +use at one does.  Getting
  that backwards reads exactly like a typo, which is why it is spelled out.
*/
void(entity t, entity act, float code) SV_ButtonPress =
{
	if (t.vbsp_mv_kind != MVK_BUTTON)
		return;

	if (code == BUTTON_PRESS)
	if (t.vbsp_mv_state == TS_GOING_UP || t.vbsp_mv_state == TS_GOING_DOWN)
		return;
	if (code == BUTTON_ACTIVATE)
	if (t.vbsp_mv_state == TS_GOING_UP || t.vbsp_mv_state == TS_AT_TOP)
		return;
	if (code == BUTTON_RETURN)
	if (t.vbsp_mv_state == TS_GOING_DOWN || t.vbsp_mv_state == TS_AT_BOTTOM)
		return;

	if (t.vbsp_mv_locked)
		return;						// silent, on purpose -- see above

	t.vbsp_mv_act = act;

	if (code == BUTTON_RETURN)
		{ SV_ButtonReturn1(t); return; }
	if (code == BUTTON_PRESS && t.vbsp_mv_state == TS_AT_TOP)
		{ SV_ButtonReturn1(t); return; }
	SV_ButtonActivate1(t);
};

/*
  CBaseButton::ButtonUse, buttons.cpp:506-551 -- what +use does, as opposed to
  what the Press input does.
*/
void(entity t, entity act) SV_ButtonUse =
{
	if (t.vbsp_mv_state == TS_GOING_UP || t.vbsp_mv_state == TS_GOING_DOWN)
		return;						// :510-511, ignore while in motion

	if (t.vbsp_mv_locked)
	{
		SV_MoverOnUseLocked(t, act);
		return;
	}

	t.vbsp_mv_act = act;

	if (t.vbsp_mv_state == TS_AT_TOP)
	{
		// Already in.  Only a toggle button comes back out on a second press.
		if (!(t.spawnflags & SF_BUTTON_TOGGLE))
			return;
		SV_FireOutput(t, "OnPressed", act);
		SV_ButtonReturn1(t);
		return;
	}

	SV_FireOutput(t, "OnPressed", act);
	SV_ButtonActivate1(t);
};

/*
  CBaseDoor's Open / Close, doors.cpp:1008 and :1091.

  OnOpen and OnClose fire at the START of the move and mean "this door has been
  told to open", which is true of a frozen door -- so they fire.  OnFullyOpen
  and OnFullyClosed are statements about where the brush IS, so they do not.
  194 OnOpen outputs across 17 maps.
*/
void(entity t, entity act) SV_DoorOpen =
{
	if (t.vbsp_mv_kind != MVK_DOOR)
		return;
	if (t.vbsp_mv_locked)
		return;
	if (t.vbsp_mv_state == TS_AT_TOP || t.vbsp_mv_state == TS_GOING_UP)
		return;
	t.vbsp_mv_state = TS_GOING_UP;
	t.vbsp_mv_act   = act;
	SV_FireOutput(t, "OnOpen", act);
};

void(entity t, entity act) SV_DoorClose =
{
	if (t.vbsp_mv_kind != MVK_DOOR)
		return;
	if (t.vbsp_mv_state == TS_AT_BOTTOM || t.vbsp_mv_state == TS_GOING_DOWN)
		return;
	t.vbsp_mv_state = TS_GOING_DOWN;
	t.vbsp_mv_act   = act;
	SV_FireOutput(t, "OnClose", act);
};

/*
  CBaseDoor::Use, doors.cpp:723-769.

  THE SF_DOOR_PUSE GATE (bit 256, "Use Opens") is at :731-735 and refuses a
  player activator outright before bAllowUse is even computed -- so without it
  we fire at doors Source would not have looked at.  Its FGD default is OFF,
  which made honouring it look risky, so it was censused first: of the 20 doors
  in the library that declare OnLockedUse, NINETEEN already set bit 256.
  Honouring it silences exactly one door, on one map.
*/
void(entity t, entity act) SV_DoorUse =
{
	if (!(t.spawnflags & SF_DOOR_PUSE))
		return;
	if (t.vbsp_mv_locked)
	{
		SV_FireOutput(t, "OnLockedUse", act);
		return;
	}
	if (t.vbsp_mv_state == TS_AT_TOP || t.vbsp_mv_state == TS_GOING_UP)
		SV_DoorClose(t, act);
	else
		SV_DoorOpen(t, act);
};

/*
  Shared spawn-time setup.  Resolves the two default sets and caches the travel
  time so that Tier 2's scheduling and any later mover agree by construction.

  THE FGD DEFAULTS AND THE CODE DEFAULTS DISAGREE, and the code wins because
  the code is what shipped (buttons.cpp:380-395, doors.cpp:297-300):

      button lip    FGD 0   code 4
      button speed  FGD 5   code 40
      button wait   FGD 3   code 1
      door   speed  FGD 100 code 100

  Hammer writes the FGD default into the VMF, so a map that took the default
  writes `speed 5` and keeps it; only a map that explicitly wrote 0 gets 40.

  The travel DISTANCE is not computed here.  Source's is
  DotProductAbs(movedir, OBBSize - '2 2 2') - lip, where the -2 compensates for
  its engine expanding bboxes by one unit each way; FTE's setmodel does not do
  that expansion, so the expression is not portable as written and would need
  measuring against a real brush.  Nothing in Tier 2 moves, so the travel TIME
  is all that is needed, and a fixed nominal is honest: it is the wait before
  OnIn, not a distance.  A real mover must replace this with the measured form.
*/
void() SV_MoverSetup =
{
	local float spd;

	self.vbsp_mv_state = TS_AT_BOTTOM;
	self.vbsp_mv_stay  = (self.wait == -1);		// m_fStayPushed, buttons.cpp:411

	// Both spellings: the census in the SV_Key2 essay counts 'speed' 4608
	// against 'Speed' 885, so reading only the lowercase one would miss 16%.
	spd = SV_Key2(self.speed, self.Speed);
	if (spd <= 0)
		spd = (self.vbsp_mv_kind == MVK_DOOR) ? 100 : 40;

	self.vbsp_mv_wait = self.wait;
	if (self.vbsp_mv_wait == 0)
		self.vbsp_mv_wait = 1;			// buttons.cpp:387-390

	// A nominal travel: 4 units of lip at `spd` units/sec, floored so a very
	// fast button still takes a tick rather than firing OnIn inside the press.
	self.vbsp_mv_travel = 4 / spd;
	if (self.vbsp_mv_travel < 0.05)
		self.vbsp_mv_travel = 0.05;
};

void() SV_SpawnDoor =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	setmodel(self, self.model);
	self.movetype = MOVETYPE_PUSH;

	if (self.spawnflags & (SF_DOOR_NONSOLID_TO_PLAYER | SF_DOOR_PASSABLE))
		self.solid = SOLID_NOT;     // still drawn -- you walk through it
	else
		self.solid = SOLID_BSP;

	// Build 63, Tier 2.  State only -- the door still does not move, and
	// deliberately never claims to have arrived anywhere (see the vbsp_mv_*
	// field block for the rule that decides which outputs may fire).
	self.vbsp_mv_kind   = MVK_DOOR;
	self.vbsp_mv_locked = (self.spawnflags & SF_DOOR_LOCKED) ? TRUE : FALSE;
	SV_MoverSetup();
};

void() func_door          = { SV_SpawnDoor(); };
void() func_door_rotating = { SV_SpawnDoor(); };

// func_wall_toggle -- func_wall plus one spawnflag (momentum.fgd:8996).
// Bit 1 "Starts Invisible" means non-solid AND not drawn; with no entity I/O
// to turn it back on, that is where it stays.
void() func_wall_toggle =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	setmodel(self, self.model);
	self.movetype = MOVETYPE_PUSH;

	if (self.spawnflags & SF_WALLTOGGLE_START_OFF)
	{
		self.solid = SOLID_NOT;
		self.effects = self.effects | EF_NODRAW;
	}
	else
		self.solid = SOLID_BSP;
};

/*
===========================================================================
  Buttons and breakables.

  2795 func_button and 1439 func_breakable across the library.  Both reached
  the catch-all before this and came out SOLID_BSP, frozen -- which is right,
  and is what they stay.  A button you cannot press is a wall with a texture
  on it, and Source's unbroken breakable IS a solid wall, so the visible and
  physical state is already correct for both.

  So why spawn functions at all?  Because the catch-all's `dprint` -- "%s is
  unknown and owns brushes, made SOLID" -- is the mechanism that found
  func_dustmotes, and every classname we know about but leave to the catch-all
  makes that warning noisier and therefore less likely to be read.  Naming
  them here is what keeps the warning meaning "nobody has looked at this yet".

  THIS COMMENT USED TO CLAIM func_button READ Source's "Don't move" family.  It
  never did: the body below reads no spawnflags at all, and SF_BUTTON_DONTMOVE
  was defined and never referenced.  Harmless, because a button that does not
  move is what this build makes every button anyway -- but a comment that
  describes code that is not there is worse than no comment, because the next
  person reads it instead of the function.

  601 of 2795 carry bit 2048, which used to delete them outright -- that part
  was and is true; see the CheckSpawn note below.

  BUILD 37 gives the button the half that was actually missing: it can be
  PRESSED.  +use traces 80 units from the eye and fires OnPressed (SV_UseFrame),
  which is what makes surf_kitsune's secret teleporter reachable now that its
  StartDisabled is honoured.  It still does not MOVE, and that stays deliberate
  for the reason SV_SpawnDoor gives at length: a moving brush can crush a
  player, strand one inside it, or open into the route.
*/
void() func_button =
{
	if (!self.model)
	{
		remove(self);
		return;
	}
	setmodel(self, self.model);
	self.movetype = MOVETYPE_PUSH;
	self.solid = SOLID_BSP;
	self.vbsp_io_solid = SOLID_BSP;

	// Build 63, Tier 2.  m_bLocked is SEEDED by the spawnflag and is not the
	// same thing as it -- Unlock clears the flag, the spawnflag stays set.
	self.vbsp_mv_kind   = MVK_BUTTON;
	self.vbsp_mv_locked = (self.spawnflags & SF_DOOR_LOCKED) ? TRUE : FALSE;
	SV_MoverSetup();
};

// func_rot_button is the same thing on a hinge (225 instances).  Same trade.
// CRotButton::Spawn uses m_vecAngle1/2 rather than m_vecPosition1/2, so this
// would diverge the moment anything actually rotated -- but Tier 2 moves
// nothing, and the state machine is identical, so the alias still holds.
void() func_rot_button = { func_button(); };

/*
  func_breakable / func_breakable_surf.  Solid until broken, and nothing here
  breaks it, so solid is the whole of its behaviour.  func_physbox (750) is a
  breakable that would also fall; frozen where it spawned is the same choice
  the doors get, and for the same reason -- a moving brush can crush or strand
  a player, a static one cannot.
*/
/*
  BUILD 63: THE ALIAS NOW HAS A CONSEQUENCE, so it is broken deliberately.

  These four have aliased func_button() since build 37 purely to get "solid
  brush, named rather than left to the catch-all", and that was free while
  func_button did nothing but set .solid.  It is no longer free: func_button
  now stamps vbsp_mv_kind = MVK_BUTTON, and a breakable carrying that would
  answer Press / PressIn / PressOut / Lock and run a button's press-latch-wait
  state machine.  A crate is not a button.

  So: still func_button() for the geometry, then the kind is cleared.  Clearing
  it rather than duplicating the body keeps the one definition of "how a solid
  brush entity spawns" in one place, which is what the alias was for.

  Their real output, OnBreak (276 in the library), is not fired by anything and
  cannot be -- see the OnDamaged note in SV_UseFrame.  It stays censused.
*/
void() SV_SpawnBreakable =
{
	func_button();
	self.vbsp_mv_kind = 0;
};

void() func_breakable      = { SV_SpawnBreakable(); };
void() func_breakable_surf = { SV_SpawnBreakable(); };
void() func_physbox        = { SV_SpawnBreakable(); };
//FTESurf Patch 256: `class CPhysBoxMultiplayer : public CPhysBox` -- the
//multiplayer subclass differs only in its VPhysics shadow, which we have none
//of, so it is the same entity here.  111 instances / 19 maps.
void() func_physbox_multiplayer = { func_physbox(); };

/*
===========================================================================
  Areaportals -- and roughly six hundred maps that have been drawing less than
  they should.

  VBSP splits a map into AREAS joined by areaportals, and the engine will not
  draw a leaf whose area is not connected to the one the camera is in
  (VBSP_RecursiveWorldNode tests refdef->areabits and returns; the prop and
  displacement loops apply the same test).  The plugin memsets every portal
  CLOSED at load unless map_autoopenportals is set, and says in its own header
  that the gamecode is then expected to open them.

  Nothing ever did.  There was no func_areaportal spawn function, so on every
  map with more than one area, everything outside the camera's area was
  unconditionally invisible.  Counted over all 1308 installed maps: 593
  func_areaportal entities, and surf_666, surf_null, surf_anubis and
  surf_utopia each have three areas and two portals.

  Source's own steady state is OPEN: a func_areaportal closes only when the
  door it is tied to closes, and we do not simulate doors (see SV_SpawnDoor).
  So every portal is opened here, which is both what the map looks like in
  Source and what map_autoopenportals 1 does -- except per-entity, and without
  needing a cvar set before the map loads.

  THE BUILTIN READS .style, NOT .portalnumber.  openportal() is a Quake 2-ism
  (pr_cmds.c:7868, "read the func_areaportal's style field") and VBSP spells
  the key `portalnumber`, so the copy below is the whole adaptation.  The
  builtin then calls the model's SetAreaPortalState directly AND sends
  svc_setportalstate to every connected client.

  ONE ORDERING TRAP, and it is why SV_OpenAllPortals exists.  Entities spawn
  before any client connects, so the reliable write at spawn reaches nobody.
  In a listen game it works anyway -- sv.world.worldmodel and cl.worldmodel are
  the same pointer, so the direct call has already fixed the renderer -- but a
  client that connects later would get the map with a third of it missing.
  Re-issuing them from ClientConnect costs nothing and removes the question.
===========================================================================
*/
.float portalnumber;
.float StartOpen;

// vbsp_portal_n / vbsp_portal_first are declared with the other counters at the top
// of this file; vbsp_portal_first is a singly-linked list through .chain.
void() SV_OpenAllPortals =
{
	local entity e;
	for (e = vbsp_portal_first; e; e = e.chain)
		openportal(e, TRUE);
};

void() func_areaportal =
{
	self.style = self.portalnumber;

	// Point entity: VBSP consumes the brushes and leaves a marker carrying the
	// portal number.  Nothing to draw, nothing to touch.
	self.solid = SOLID_NOT;
	self.movetype = MOVETYPE_NONE;

	openportal(self, TRUE);

	self.chain = vbsp_portal_first;
	vbsp_portal_first = self;
	vbsp_portal_n = vbsp_portal_n + 1;
};

/*
  func_areaportalwindow -- 70 instances.  A pane you see and shoot through that
  additionally stops drawing what is beyond it past a distance.  The distance
  fade needs per-frame work we have no hook for; the part that matters is that
  it must not be a wall and must not seal an area, which is the same treatment
  plus keeping the brush visible.
*/
void() func_areaportalwindow =
{
	self.style = self.portalnumber;

	if (self.model && substring(self.model, 0, 1) == "*")
	{
		setmodel(self, self.model);
		self.solid = SOLID_NOT;         // still drawn -- it is glass
		self.movetype = MOVETYPE_NONE;
	}

	openportal(self, TRUE);

	self.chain = vbsp_portal_first;
	vbsp_portal_first = self;
	vbsp_portal_n = vbsp_portal_n + 1;
};

/*
  func_occluder -- 25 instances, in the whole library.

  Source's runtime occlusion volume: a plane the engine tests against to skip
  geometry behind it.  We have no occlusion system, and 25 instances across
  1308 maps does not begin to justify writing one.  What matters is that it is
  NOT a wall -- it reached the catch-all before this and became SOLID_BSP,
  which is 25 invisible blocks in exactly the places a mapper put a big flat
  brush across a sightline.
*/
void() func_occluder =
{
	if (self.model && substring(self.model, 0, 1) == "*")
		SV_BindInvisibleBrush();
	self.solid = SOLID_NOT;
	self.movetype = MOVETYPE_NONE;
};

/*
  func_viscluster needs no spawn function and never will: it is a VIS hint that
  VVIS consumes at compile time, and a census of all 1308 installed maps finds
  ZERO instances.  Same story as func_detail below.

  point_teleport -- 34 instances -- is a different kind of nothing.  It is real
  and it compiles into the map, but it only ever does anything when a
  logic_relay or a trigger fires its Teleport input, and we model no entity I/O
  at all.  Removed silently rather than left to the catch-all, so it stops
  showing up in ent_census as an open question: implementing it without inputs
  would be implementing a teleport that can never fire.
*/
void() point_teleport = { remove(self); };

/*
===========================================================================
  trigger_multiple.

  Before this it had no spawn function at all and fell into the catch-all's
  inert-trigger arm, which is still exactly what happens to one with nothing
  wired to it.  See SV_TriggerIOTouch for the end-touch machinery, which is
  shared with every other trigger class.
===========================================================================
*/
void() trigger_multiple_touch =
{
	local int bit;

	if (other.classname != "player")
		return;
	if (other.health <= 0)
		return;
	if (SV_Key2(self.StartDisabled, self.startdisabled))
		return;
	if (!SV_PassesFilter(self, other))
		return;

	/*
	  PATCH 270, STAGE 2 -- a trigger_once this player has already used.
	  Everything below is skipped, which is what "the entity was removed" looks
	  like from inside one player's session.  See the wait < 0 arm at the foot
	  of this function for how the bit gets set and why the entity survives.
	*/
	bit = SV_TouchBit(other);
	if (bit)
	if (self.vbsp_once_done & bit)
		return;

	SV_TriggerIOTouch(self, other);

	/*
	  OnTrigger is the one output `wait` gates -- Source's ActivateMultiTrigger.
	  StartTouch and EndTouch are CBaseTrigger's and are not gated, which is
	  what lets futile rename you on every crossing despite `wait 1`.

	  PATCH 270, STAGE 2: one shared window, spent once per player, so one
	  player's crossing does not swallow another's OnTrigger for `wait`
	  seconds.  See vbsp_io_gate_seen -- including what the first version of
	  this did instead, and why it fired 200 outputs a second.
	*/
	if (vbsp_mp && bit)
	{
		/*
		  THE MASK IS CLEARED ON EXPIRY; THE TIMER IS PUSHED ON EVERY FIRE.
		  Both halves are needed and an earlier version had only the first.

		  With the timer pushed only when the window restarted, the window ended
		  a fixed `wait` after the FIRST fire in it -- so a player who entered
		  late spent the window at 0.9 s and then spent the next one at 1.0 s,
		  firing twice a tenth of a second apart against `wait 1`.  Source's own
		  rule (ActivateMultiTrigger sets m_flNextTrigger = curtime + m_flWait on
		  every activation) does not allow that, and Source is a multiplayer
		  engine -- the per-player relaxation here is a deliberate divergence for
		  lobby fairness, so it must not also diverge in the direction of firing
		  a map's logic MORE often than authored.

		  Pushing on every fire does not compound the way it looks like it
		  might: the mask lets each player through at most once, so the window
		  ends `wait` after the LAST NEW player fired, not `wait` x 32.  With one
		  player it collapses to exactly build 51 -- fire, push, blocked until
		  the push expires.
		*/
		if (time >= self.vbsp_io_next_ok)
			self.vbsp_io_gate_seen = 0;

		if (self.vbsp_io_gate_seen & bit)
			return;                     // already spent this window
		self.vbsp_io_gate_seen = self.vbsp_io_gate_seen | bit;
	}
	else
	{
		// vbsp_mp 0, or a client above the 32nd slot.  Build 51 exactly.
		if (time < self.vbsp_io_next_ok)
			return;
	}

	self.vbsp_io_next_ok = time + ((self.wait > 0) ? self.wait : 0.2);
	SV_FireOutput(self, "OnTrigger", other);

	/*
	  FTESurf Patch 257: and if it only fires once, retire it here.

	  trigger_once IS trigger_multiple -- CTriggerOnce::Spawn is
	  BaseClass::Spawn() plus `m_flWait = -1` (triggers.cpp:940-955) -- and the
	  wait is what ActivateMultiTrigger branches on: >0 re-arms after the delay,
	  anything else drops the touch and removes the entity (:913-925).  So the
	  same touch function serves both and the authored `wait` decides, exactly
	  as it does in Source.

	  Removed on a think rather than inline, for the reason Source states at
	  :920 -- "we can't just remove (self) here, because this is a touch
	  function called while C code is looping through area links".  SOLID_NOT
	  and the null touch make it inert immediately either way.
	*/
	if (self.wait < 0)
	{
		/*
		  PATCH 270, STAGE 2 -- retire it for THIS PLAYER, in a lobby.

		  A trigger_once that is genuinely removed is removed for all 32
		  people, so the first player through a map's start gate consumes the
		  event for everyone who has not reached it yet.  On the 841 library
		  trigger_onces that wire an output, that is the map's progression
		  logic disappearing for whoever is slower.

		  Only when vbsp_retrigger is set (lobby_enable && lobby_retrigger), so
		  offline this is bit-for-bit build 51: the entity really is removed and
		  a map that counts on it being gone still gets that.

		  The two mask clears are what makes it look like a removal rather than
		  a mute.  Without them the player stays in vbsp_touch_in, the next
		  sweep sees them absent -- this function returns before
		  SV_TriggerIOTouch now -- and fires an OnEndTouch at them from an
		  entity that is supposed to have ceased to exist.  On the seven maps
		  where end-touch IS the progression logic that would be a real misfire.
		*/
		if (vbsp_retrigger && bit)
		{
			self.vbsp_once_done  = self.vbsp_once_done | bit;
			self.vbsp_touch_in   = self.vbsp_touch_in   & ~bit;
			self.vbsp_touch_seen = self.vbsp_touch_seen & ~bit;
			self.vbsp_touch_out  = self.vbsp_touch_out  & ~bit;
			return;
		}

		self.touch = SUB_Null;
		self.solid = SOLID_NOT;
		self.think = SUB_Remove;
		self.nextthink = time + 0.1;
	}
};

void() trigger_multiple =
{
	if (!self.model)
	{
		remove(self);
		return;
	}

	/*
	  A trigger with nothing wired to it stays exactly as inert as it was
	  before this build, and that is the point: the library is 1,308 maps and
	  only a handful wire anything, so this is what keeps the change to the two
	  that need it.

	  It is also the answer to the catch-all's own objection -- "keeping the
	  submodel would put every unhandled trigger on the wire as a networked
	  entity, which on a busy map is real packet cost for something that can
	  never be seen or touched".  Still true, and still avoided, for every
	  trigger that has no outputs.

	  .vbsp_io_raw is complete by now: ED_ParseEdict reads ALL of an entity's
	  keyvalues before ED_LoadFromFile calls its spawn function.
	*/
	if (self.vbsp_io_raw == "")
	{
		self.model = "";
		self.modelindex = 0;
		self.solid = SOLID_NOT;
		self.movetype = MOVETYPE_NONE;
		return;
	}

	SV_BindInvisibleBrush();
	self.movetype = MOVETYPE_NONE;
	self.solid = SOLID_BSPTRIGGER;
	self.vbsp_io_solid = SOLID_BSPTRIGGER;
	self.touch = trigger_multiple_touch;

	if (SV_Key2(self.StartDisabled, self.startdisabled))
		self.solid = SOLID_NOT;
};

/*
  FTESurf Patch 257 -- trigger_once, which has been inert.

  With no spawn function it took the catch-all's `trigger_` arm
  (SV_OnEntityNoSpawnFunction), which strips the model and sets SOLID_NOT so it
  can never be touched -- correct for an unknown trigger, and wrong for this
  one, whose whole job is to fire an output the first time you cross it.

  CTriggerOnce::Spawn is BaseClass::Spawn() plus `m_flWait = -1`
  (triggers.cpp:950-955), and that is all this is.  The -1 is written AFTER the
  base spawn in Source, so an authored `wait` is overridden rather than
  respected; same here.

  CENSUS, all 1310 maps: 845 trigger_once own a brush model, across 176 maps,
  and 841 of those wire at least one output -- so unlike trigger_multiple,
  where the wireless majority is the reason the inert path stays, essentially
  every trigger_once in the library exists to fire something.

  surf_garden's *244 is the local case: OnStartTouch -> fountainaudiosource,
  PlaySound.
*/
void() trigger_once =
{
	trigger_multiple();
	// Only if it actually armed one.  trigger_multiple removes a modelless
	// trigger outright and leaves a trigger with no outputs inert without a
	// touch function; in both cases there is nothing here to make fire once.
	if (self.touch == trigger_multiple_touch)
		self.wait = -1;             // CTriggerOnce::Spawn, triggers.cpp:954
};

/*
===========================================================================
  func_bhop -- 1122 of them on bhop_arcane, every one a hole in the floor.

  THIS ENTRY WAS IN THE NON-SOLID LIST, and the justification written beside it
  was wrong in both halves.

  It said `func_bhop  94 / 2 maps  base(trigger_momentum_bhop)`.

    1. THE COUNT WAS OUT BY AN ORDER OF MAGNITUDE.  bhop_arcane alone has 1122.
       The list's own zone_timer_* note explains why: the offline census behind
       these numbers read raw entity lumps, and the Momentum library stores
       most of them LZMA-compressed.  arcane's is compressed -- and so, it turns
       out, is bhop_futile's, which is a plain VBSP v20 map.  Compression is not
       the "newer maps" special case the note implies.

    2. THE BASE CLASS WAS READ AS EVIDENCE OF A TRIGGER.  momentum.fgd:10736 is
       `@SolidClass base(trigger_momentum_bhop) = func_bhop`, and @SolidClass
       means a solid brush that ALSO has trigger behaviour.  The base class
       supplies LandingLimit and TimeLimit, and its own text says "Only full
       groundings count toward this, not just touching from above" -- you land
       on it.  arcane's brushes agree: all 1122 write solid 6, solidity 0
       (Toggle, i.e. follow StartDisabled) and startdisabled 0.

  WHY IT LOOKED LIKE A TELEPORT RATHER THAN A FALL, which is what made the
  report confusing.  Under the save-lock left on arcane, `func_bhop *30`
  occupies z 14272..14400 and `trigger_teleport *135` occupies z 14272..14336 --
  INSIDE the block's own lower half, both aimed at `stage1a`.  Solid, you stand
  on the top at 14400 and can never reach the trigger.  Non-solid, you drop
  through it into the trigger and are reset.  Every block on the map is built
  this way, so "the platform isn't solid" and "it teleports me" are the same
  bug seen from two sides.

  The blocks were always DRAWN (the catch-all calls setmodel before it reaches
  the non-solid list), which is why this reads as a collision bug rather than a
  missing platform.
===========================================================================
*/
.float  TimeLimit;
.float  LandingLimit;
.float  ProgressTeleport;
.float  ResetVelocityOnTeleport;

// Tri-state for the reason SV_KeyTri exists: the FGD default is 1, so "the
// mapper wrote 0" and "the mapper wrote nothing" mean opposite things and a
// .float cannot tell them apart.  All 1122 of arcane's write 1.
.string UseDestinationAngles;

// Source's landing-counter reset flags.  Both of arcane's are set and both are
// inert there, because LandingLimit 0 means unlimited on all 1122 -- the time
// limit is the only rule that fires on that map.
#define SF_BHOP_RESET_ON_FIRE   1
#define SF_BHOP_RESET_ON_OTHER  2
#define SF_BHOP_RESET_ON_ANY    4

void(entity b, entity pl) SV_BhopTeleport =
{
	local entity dest;
	local float  snap, hs;

	/*
	  `target` OVERRIDES the progress teleport, and the FGD says so in as many
	  words ("overrides progress teleport setting").  All 1122 of arcane's set
	  both, so reading them the other way round would send every block to a
	  trigger_momentum_progress the map does not contain -- arcane has none.
	*/
	dest = SV_FindByName(b.target, world);
	if (!dest)
	{
		if (b.ProgressTeleport)
			if (SV_CensusAdd("trigger_momentum_progress"))
				dprint("^3func_bhop: ProgressTeleport is not implemented and "
				       "this one has no `target` -- it will not teleport\n");
		return;
	}

	setorigin(pl, dest.origin + '0 0 1');

	// A teleport into a fall must not spend its first tick believing it is
	// standing -- the same rule trigger_teleport_touch follows, and here it is
	// also what stops the dwell timer re-arming against the block we just left.
	pl.flags = pl.flags - (pl.flags & FL_ONGROUND);

	snap = SV_KeyTri(b.UseDestinationAngles, "");
	if (snap != 0)						// -1 is absent, and the FGD default is 1
	{
		pl.angles   = dest.angles;
		pl.angles_x = 0;
		pl.angles_z = 0;
		pl.v_angle  = pl.angles;		// the view, not the model -- see build 13
		pl.fixangle = TRUE;

		// "Snap the player's angles AND VELOCITY DIRECTION", per the FGD.
		if (!b.ResetVelocityOnTeleport)
		{
			hs = vlen([pl.velocity_x, pl.velocity_y, 0]);
			makevectors(pl.angles);
			pl.velocity = v_forward * hs + '0 0 1' * pl.velocity_z;
		}
	}

	if (b.ResetVelocityOnTeleport)
		pl.velocity = '0 0 0';

	// "I did not travel here, I was put here" -- same call, same reason, as
	// trigger_teleport_touch makes.  Without it the next tick's swept zone test
	// runs a segment from the block to the destination and fires every zone on
	// the line between them.
	if (cvar("run_teleport_warp"))
		SV_TimerWarped(pl);

	if (b.spawnflags & SF_BHOP_RESET_ON_FIRE)
	{
		b.count = 0;
		// Patch 270, Stage 2: and the per-player copy, or under vbsp_retrigger
		// the reset spawnflag is inert -- the block fires once and its landing
		// limit never re-arms for that player.  Both counters or neither.
		if (pl.vbsp_bhop_cntblk == b)
			pl.vbsp_bhop_cnt = 0;
	}

	pl.vbsp_bhop_on = world;
	pl.vbsp_bhop_since = 0;
	vbsp_bhop_tele_n = vbsp_bhop_tele_n + 1;

	SV_FireOutput(b, "OnActivate", pl);
};

/*
  The dwell and landing check, called once per usercmd from PlayerPostThink.

  NOT a .touch: a SOLID_BSP brush does not receive touches from a player
  STANDING on it, which is the only state this rule is about.  The player's
  .groundentity is what points at it (sv_user.c:8165), and it is written only
  when pmove reports onground -- so it goes STALE the moment you leave, and the
  FL_ONGROUND test below is load-bearing rather than belt-and-braces.
*/
void(entity pl) SV_BhopFrame =
{
	local entity b;
	local float  lim;

	b = world;
	if (pl.flags & FL_ONGROUND)
		b = pl.groundentity;

	if (b.classname != "func_bhop" || b.solid == SOLID_NOT)
	{
		// Landed on something that is not a func_bhop.  Source's spawnflag 2
		// resets the landing counter here; flag 4 resets it on landing on
		// anything at all, which is the same thing from this side.
		if ((pl.flags & FL_ONGROUND) && pl.vbsp_bhop_on)
			if (pl.vbsp_bhop_on.spawnflags & (SF_BHOP_RESET_ON_OTHER | SF_BHOP_RESET_ON_ANY))
			{
				pl.vbsp_bhop_on.count = 0;
				pl.vbsp_bhop_cnt      = 0;
				pl.vbsp_bhop_cntblk   = world;
			}

		pl.vbsp_bhop_on = world;
		pl.vbsp_bhop_since = 0;
		return;
	}

	if (pl.vbsp_bhop_on != b)
	{
		// A new full grounding.  The FGD is explicit that only these count,
		// "not just touching from above".
		pl.vbsp_bhop_on = b;
		pl.vbsp_bhop_since = time;
		b.count = b.count + 1;

		/*
		  PATCH 270, STAGE 2 -- the same count, kept on the player.

		  b.count is one counter shared by everybody standing on the block, so
		  32 players hopping a LandingLimit block exhaust it 32x faster than one
		  player does and the block starts teleporting people who have landed on
		  it once.  The per-player copy counts CONSECUTIVE landings on the same
		  block, which is what b.count means for one player: a different block
		  restarts it, and the spawnflag reset above clears it.

		  b.count is still maintained.  It is what the entity-I/O layer exposes
		  to a map's own AddOutput/counter logic, and silently making that
		  per-player would be a different change with a different blast radius.
		  Only the LandingLimit comparison moves.

		  INVISIBLE ON THE WHOLE LIBRARY AS IT STANDS: LandingLimit is 0
		  (unlimited) on every func_bhop in all 1310 maps, which is why the arm
		  below is described as correct-by-construction rather than tested.  This
		  is a latent bug being closed before 32 players can find it, not an
		  observed one.
		*/
		if (pl.vbsp_bhop_cntblk == b)
			pl.vbsp_bhop_cnt = pl.vbsp_bhop_cnt + 1;
		else
		{
			pl.vbsp_bhop_cntblk = b;
			pl.vbsp_bhop_cnt    = 1;
		}
	}

	/*
	  TimeLimit 0 means "use sv_bhop_time_limit", and an ABSENT key reads 0 too
	  -- which here is the same answer rather than a collapsed distinction,
	  because the FGD's own default for the key is the cvar's default value.
	  arcane writes no TimeLimit at all on any of its 1122 blocks, so this cvar
	  is what the entire map runs on.
	*/
	lim = b.TimeLimit;
	if (lim <= 0)
		lim = cvar("sv_bhop_time_limit");
	if (lim <= 0)
		lim = 0.1;						// the FGD's number, if nothing set it

	if (time - pl.vbsp_bhop_since >= lim)
	{
		SV_BhopTeleport(b, pl);
		return;
	}

	// LandingLimit 0 is unlimited, which is every block on both maps here, so
	// this arm is correct-by-construction rather than tested against a map.
	// -1 is per-gamemode func_door emulation and is deliberately not done.
	//
	/*
	  Patch 270, Stage 2: compared against the PLAYER's count IN A LOBBY.

	  Gated on vbsp_retrigger rather than vbsp_mp, and that is a correction to
	  the first version of this patch.  The two counters do not mean the same
	  thing: b.count is cumulative per block across visits (only the reset
	  spawnflags clear it), while the per-player copy counts CONSECUTIVE
	  landings and restarts when you land on a different block.  For one player
	  alternating between two blocks those diverge, so hanging it on vbsp_mp --
	  which is on everywhere -- would have changed offline behaviour while
	  claiming to be a no-op.  In a lobby the per-player count is an
	  approximation replacing something that is simply wrong at 32 players; on
	  a listen server it is a change with no upside, so it is not made.
	*/
	if (b.LandingLimit > 0 && (vbsp_retrigger ? pl.vbsp_bhop_cnt : b.count) > b.LandingLimit)
	{
		SV_FireOutput(b, "OnLandingLimitReached", pl);
		SV_BhopTeleport(b, pl);
	}
	else if (b.LandingLimit < 0)
	{
		if (SV_CensusAdd("func_bhop LandingLimit -1"))
			dprint("^3func_bhop: LandingLimit -1 (func_door emulation) is not "
			       "implemented; treated as unlimited\n");
	}
};

void() func_bhop =
{
	local float sol, dis;

	if (!self.model)
	{
		remove(self);
		return;
	}

	// Drawn, unlike the triggers: a bhop block is the thing you are aiming at.
	setmodel(self, self.model);
	self.movetype = MOVETYPE_PUSH;

	// Both spellings, and arcane needs both -- 1117 of its blocks write
	// lowercase `solidity` and the other 5 write `Solidity`, in one map.
	sol = SV_Key2(self.Solidity, self.solidity);
	dis = SV_Key2(self.StartDisabled, self.startdisabled);

	if (sol == SOLIDITY_NEVER)
		self.solid = SOLID_NOT;
	else if (sol == SOLIDITY_ALWAYS)
		self.solid = SOLID_BSP;
	else
		self.solid = dis ? SOLID_NOT : SOLID_BSP;

	self.vbsp_io_solid = SOLID_BSP;
	if (dis)
		self.effects = self.effects | EF_NODRAW;

	if (self.solid != SOLID_NOT)
		vbsp_bhop_n = vbsp_bhop_n + 1;
};

// The point-entity half of the same class, for maps that use the trigger form
// rather than the brush one.  It is the base class, so it is the same rules;
// what differs in Source is that it fires on touch-from-inside rather than on
// standing, which the ground test above already covers for both.
void() trigger_momentum_bhop = { func_bhop(); };

/*
===========================================================================
  The I/O endpoints -- entities that exist only to be fired at.

  Every one of these is a POINT entity, so without a spawn function the
  catch-all deletes it (":Point entity with no geometry -- nothing to
  preserve"), and it would be deleted BEFORE SV_EntityIOBuild ever ran.  That
  is the whole reason these stubs exist: an output aimed at a removed entity
  resolves to nothing and is silently dropped.
===========================================================================
*/
void() SV_SpawnIOPoint =
{
	self.solid = SOLID_NOT;
	self.movetype = MOVETYPE_NONE;
};

// Fires OnMapSpawn once, from SV_EntityIOBuild.
void() logic_auto      = { SV_SpawnIOPoint(); };

/*
  Counts, and fires OnHitMax / OnHitMin.  `min` and `max` arrive via
  ED_ParseUnknownEpair, because neither `.float min;` nor `.float max;` compiles
  -- both are builtins (#94 and #95).

  CMathCounter::Spawn, logicentities.cpp:1488-1513.  Both keys are already
  parsed by the time a spawn function runs -- ED_ParseEdict reads every pair
  before it dispatches -- so the swap and the clamp can happen here.
*/
void() math_counter =
{
	local float f;

	SV_SpawnIOPoint();

	if (self.vbsp_io_min > self.vbsp_io_max)
	{
		f = self.vbsp_io_max;
		self.vbsp_io_max = self.vbsp_io_min;
		self.vbsp_io_min = f;
	}

	self.count = SV_Key2(self.startvalue, self.StartValue);
	if (self.vbsp_io_min != 0 || self.vbsp_io_max != 0)
		self.count = bound(self.vbsp_io_min, self.count, self.vbsp_io_max);
};

// ModifySpeed's target.  The multiplier lands on the PLAYER, not on this.
void() player_speedmod = { SV_SpawnIOPoint(); };

/*
  logic_relay is a pass-through: whatever fires its Trigger input makes it fire
  OnTrigger.

  Build 37 left this a bare stub, whose only job was to keep the catch-all from
  deleting the entity so a map's outputs still resolved the name.  Build 63
  wires it: the behaviour is in SV_IORelayTrigger / SV_IOCancelPending beside
  SV_ApplyInput (they have to be up there, since the input ladder calls them),
  the OnSpawn fire is at the tail of SV_EntityIOBuild, and the disabled state is
  StartDisabled, which SV_IOEnable already maintains.

  Nothing to do at spawn but exist, so the stub body is unchanged.
*/
void() logic_relay     = { SV_SpawnIOPoint(); };

/*
  logic_case -- Build 63.  6,258 OnCase01..16 outputs across 112 maps, every one
  of them dead until now, because without a spawn function the catch-all removed
  the entity (":Point entity with no geometry") before SV_EntityIOBuild ran.

  Like every class in this block it needs nothing at spawn but to survive: the
  Case01..16 values are already in vbsp_case_raw by the time this runs (the hook
  fires during the parse, ahead of the spawn function), the wired-case set is
  read off the output chain at fire time, and the shuffle state starts zeroed.
*/
void() logic_case      = { SV_SpawnIOPoint(); };

/*
  logic_branch and logic_compare -- Build 63.  Same story as logic_case: no
  spawn function meant the catch-all deleted them, so OnTrue/OnFalse and the
  four comparison outputs never resolved.

  Both read their starting state here rather than lazily, because "absent" and
  "zero" mean the same thing for all three keys and SV_Key2 is enough.
*/
void() logic_branch =
{
	SV_SpawnIOPoint();
	self.vbsp_branch_val = SV_Key2(self.InitialValue, self.initialvalue) ? TRUE : FALSE;
};

void() logic_compare =
{
	SV_SpawnIOPoint();
	self.vbsp_cmp_in  = SV_Key2(self.InitialValue, self.initialvalue);
	self.vbsp_cmp_cmp = SV_Key2(self.CompareValue, self.comparevalue);
};

/*
===========================================================================
  FTESurf Patch 256 -- logic_timer, and it is the single largest dead output
  source in the library.

  2224 OnTimer outputs across 220 of the 1310 maps, and not one of them could
  ever have fired: logic_timer is a point entity with no spawn function, so the
  catch-all removed it before SV_EntityIOBuild ran, and every output aimed at it
  or hanging off it resolved to nothing.  That is a bigger number than
  OnEndTouchAll, OnLockedUse and OnPass put together.

  Source (logicentities.cpp, CTimerEntity):
    - RefireTime is the interval.  A `UseRandomTime` timer picks uniformly in
      [LowerRandomBound, UpperRandomBound] each shot instead.
    - StartDisabled holds it off until Enable.
    - Inputs: Enable, Disable, Toggle, FireTimer, ResetTimer, RefireTime.
    - It fires OnTimer, and re-arms itself.

  WHAT THIS DOES NOT DO, said plainly: the OnTimer will now fire, but what it
  fires INTO is a separate question.  A large share of these aim at inputs this
  file still does not implement (Trigger, Open, Close, RunScriptCode), so the
  visible result on many maps will be a fresh crop of "input X is not
  implemented" census lines rather than behaviour.  That is the right failure --
  it is loud, it is counted, and it names the next piece of work -- but the
  2224 should not be read as 2224 things that now happen.

  A zero or absent RefireTime would be a per-frame think on a point entity that
  nothing can switch off, so it is clamped rather than trusted; Source's own
  default is 1 second.
===========================================================================
*/
// Fields and prototypes are up beside SV_FireOutput -- SV_IOEnable and
// SV_ApplyInput both need them and both are compiled first.
float(entity t) SV_TimerInterval =
{
	local float lo, hi;

	if (t.UseRandomTime)
	{
		lo = t.LowerRandomBound;
		hi = t.UpperRandomBound;
		if (hi <= lo)
			hi = lo;
		if (lo > 0)
			return lo + random() * (hi - lo);
	}
	if (t.RefireTime > 0)
		return t.RefireTime;
	return 1;								// CTimerEntity's own default
};

void() SV_TimerThink =
{
	// SV_IOEnable's disabled marker is StartDisabled/startdisabled -- it writes
	// BOTH spellings precisely so a later read through SV_Key2 sees it.  Stop
	// dead rather than polling; SV_IOEnable re-arms us.
	if (SV_Key2(self.StartDisabled, self.startdisabled))
	{
		self.nextthink = 0;
		return;
	}
	SV_TimerFire(self);
	self.nextthink = time + SV_TimerInterval(self);
};

/*
  Build 63.  WHICH output a timer fires, in one place.

  CTimerEntity::FireTimer, logicentities.cpp:366-390.  An "Oscillator" timer --
  SF_TIMER_UPDOWN, spawnflag 1 (:195) -- alternates OnTimerHigh and OnTimerLow
  and does not fire OnTimer at all.  11 and 12 outputs respectively across the
  library: small, but they are the only reason those two names exist in it, and
  a map that set the flag fired NOTHING before this, because SV_TimerThink knew
  only OnTimer.

  Source fires the oscillator pair at (this, this); OnTimer has been fired here
  with world as the activator since Patch 256 and that is left alone.
*/
void(entity t) SV_TimerFire =
{
	if (t.spawnflags & SF_TIMER_UPDOWN)
	{
		if (t.vbsp_timer_updown)
			SV_FireOutput(t, "OnTimerHigh", t);
		else
			SV_FireOutput(t, "OnTimerLow", t);
		t.vbsp_timer_updown = !t.vbsp_timer_updown;
		return;
	}
	SV_FireOutput(t, "OnTimer", world);
};

void() logic_timer =
{
	SV_SpawnIOPoint();
	self.think = SV_TimerThink;
	if (SV_Key2(self.StartDisabled, self.startdisabled))
		self.nextthink = 0;
	else
		self.nextthink = time + SV_TimerInterval(self);
};

/*
  func_detail needs no spawn function and never will.

  VBSP merges detail brushes into the world model at compile time, so there is
  no func_detail entity in any compiled Source BSP -- it exists only in the VMF
  and is absent from momentum.fgd entirely.  The geometry is already there, as
  world.  A stub here would never be called; this note is so the next person
  looking for one stops looking.
*/

/*
===========================================================================
  The catch-all.

  The engine calls this for every classname with no spawn function
  (pr_cmds.c:1851) instead of printing "Couldn't find spawn function" and
  freeing the edict.  That default would DELETE brush entities -- and a surf
  map's func_brush/func_illusionary/func_wall pieces are real geometry, so
  losing them means losing walls and ramps.

  So: point entities are dropped silently, brush entities are kept.
  A brush entity is identifiable by its model name starting with '*'.
===========================================================================
*/
float(string cn, string pfx) SV_ClassPrefix =
{
	return substring(cn, 0, strlen(pfx)) == pfx;
};

/*
===========================================================================
  CheckSpawn -- and the 828 entities that were vanishing before this.

  FTE inherits Quake's difficulty/deathmatch entity filter: an entity whose
  spawnflags match `killonspawnflags` is freed before its spawn function is
  ever consulted (pr_cmds.c:1789-1796).  In deathmatch -- which worldspawn
  turns on, because we do not want single-player level progression -- that
  mask is SPAWNFLAG_NOT_DEATHMATCH, bit 2048.

  Bit 2048 means nothing of the sort in Source.  It is an ordinary flag whose
  meaning depends on the class, and plenty of surf-map entities set it.
  Counted across all 1308 maps, the collision silently deleted:

        601 of 2795  func_button          (21.5%)
         78 of 3485  func_door
         53 of  750  func_physbox
         27 of  225  func_rot_button
         24 of  461  func_door_rotating
         18 of 1439  func_breakable
        ... 828 entities in total

  Those are BRUSH entities.  Every one that vanished took its geometry with
  it -- a hole where a button, a door or a breakable wall should have been --
  and nothing was printed, because from the engine's point of view this is
  correct Quake behaviour.

  The engine offers exactly one way out, and says so in its own comment: "we
  skip this check if the mod has the CheckSpawn function defined. Such mods
  can do their own filtering easily enough."  Defining it hands us the spawn
  dispatch, and the filter is bypassed.

  Note that `spawnfunc` is never 0 in practice: the engine falls back to
  SV_OnEntityNoSpawnFunction before it gets here (pr_cmds.c:1850), so the
  catch-all below still runs for unrecognised classnames exactly as it did.
  The zero branch is for the case where that fallback does not exist.
===========================================================================
*/
void(void() spawnfunc) CheckSpawn =
{
	if (spawnfunc)
		spawnfunc();
	else
		remove(self);
};

void() SV_OnEntityNoSpawnFunction =
{
	local string cn;
	local string mdl;
	local float  firstseen;

	cn = self.classname;
	mdl = self.model;

	firstseen = SV_CensusAdd(cn);

	// Point entity with no geometry -- nothing to preserve.
	if (!mdl || substring(mdl, 0, 1) != "*")
	{
		remove(self);
		return;
	}

	setmodel(self, mdl);

	// Unimplemented triggers: keep the edict (something may find() it) but
	// make it inert and invisible so it can never block the player.
	//
	// This one DOES drop the model, unlike the implemented triggers above.
	// Nothing here collides or touches, so the submodel would buy nothing --
	// and keeping it would put every unhandled trigger on the wire as a
	// networked entity, which on a busy map is real packet cost for something
	// that can never be seen or touched.
	if (SV_ClassPrefix(cn, "trigger_"))
	{
		self.model = "";
		self.modelindex = 0;
		self.solid = SOLID_NOT;
		self.movetype = MOVETYPE_NONE;
		return;
	}

	/*
	  Decorative and rules brushwork -- walk straight through.

	  This list is why surf_666 has "invisible blocks blocking the path while you
	  surf".  func_dustmotes was missing from it: 903 instances across 77 maps,
	  22 of them on surf_666, every one textured TOOLS/TOOLSTRIGGER with
	  CONTENTS_SOLID brushes behind it.  Five
	  of surf_666's form a hollow shell -- floor, ceiling, three walls -- around
	  the spawn room, and fourteen more stand inside the two trigger_teleport
	  plates that serve the stage-1 restart.

	  The rest are the same class of thing, found by censusing every brush
	  classname in 220 shipped maps against what Source actually makes solid:

	      func_dustmotes    903 / 77 maps    dust particle volume
	      env_bubbles        91 /  8         particle volume
	      env_embers         53 / 10         particle volume
	      func_nogrenades    47 /  3         CS rules volume
	      func_regenerate    37 /  3         rules volume
	      func_precipitation 26 / 12         rain and snow
	      func_simpleladder   5 /  2         climb volume
	      zone_timer_*      189 / 15         Momentum zone volumes

	  zone_timer_* deserves its own note.  sh_zones.qc says those classnames
	  "appear in exactly zero shipped maps"; they appear in fifteen, as 189
	  invisible walls, including a 576 x 2176 x 256 slab lying across
	  surf_utopia's start line.  That comment was wrong because the offline scan
	  behind it read raw entity lumps and 728 of the 1,308 Momentum maps store
	  theirs LZMA-compressed.

	  BUILD 37 REMOVED func_bhop FROM THIS LIST, and it was the same mistake a
	  second time: the entry read `func_bhop 94 / 2 maps`, and bhop_arcane alone
	  has 1122 -- undercounted by the same compressed-lump scan this paragraph
	  already warns about.  A func_bhop is a @SolidClass and it is the floor of
	  a bhop map; see its spawn function above.  The compression is also not a
	  newer-map special case: bhop_futile is a plain VBSP v20 and its lump is
	  compressed too, so any future census that reads lumps raw will be wrong
	  in the same direction again.
	*/
	/*
	  FTESurf Patch 256 adds the second block.  These are rules and effect
	  volumes -- CRuleBrushEntity descendants (maprules.cpp:110), TF2/CS mode
	  volumes, and Momentum's own timer-adjacent markers -- every one of which
	  is a trigger or a non-solid in its own game and a wall here.  They are in
	  the LIST rather than given spawn functions because none of them tests a
	  spawnflag: they are unconditionally non-solid, which is exactly what this
	  list expresses.  func_rotating is the counter-example and got a spawn
	  function instead; see the essay there.

	    color_correction_volume  SetSolidFlags(FSOLID_TRIGGER|FSOLID_NOT_SOLID)
	                             colorcorrectionvolume.cpp:147
	    game_zone_player         CGamePlayerZone : CRuleBrushEntity, maprules.cpp:416
	    fog_volume, func_nobuild, func_bomb_target, func_capturezone,
	    func_respawnroomvisualizer, dispenser_touch_trigger, func_portal_bumper
	                             mode volumes with no solid in their own game
	    func_stoptimer, func_starttimer, func_setcoursenames, func_overbounce
	                             Momentum markers -- the zone_ family by another
	                             name, and zone_ is already prefixed above
	    func_static              a propper artefact; it is geometry, not a wall
	*/
	/*
	  THIS LIST DOES NOT MAKE ANYTHING INVISIBLE, and a claim that it did used
	  to sit in the paragraph above ("every one textured TOOLS/TOOLSTRIGGER, so
	  build 5's VMT work makes them invisible").  That was wrong and it is why
	  the func_dustmotes slab on surf_boreas went unnoticed for four builds:
	  VBSP flags a trigger face SURF_TRIGGER (0x40), not SURF_NODRAW (0x80), and
	  the plugin's hidetools test read only 0x80.  Fixed in the plugin, where
	  visibility belongs -- Patch 265, mod_vbsp.c.

	  It must stay that way here.  func_illusionary, func_detail_illusionary and
	  func_static are on this list and are DECORATIVE GEOMETRY: they are meant
	  to be seen and walked through, so dropping the model for the whole list
	  would delete real scenery.  Non-solid is a class property; not-drawn is a
	  material property.  Keep them separate.
	*/
	if (cn == "func_illusionary" || cn == "func_detail_illusionary" ||
	    cn == "func_dustcloud"   || cn == "func_smokevolume"        ||
	    cn == "func_dustmotes"   || cn == "func_precipitation"      ||
	    cn == "env_bubbles"      || cn == "env_embers"              ||
	    cn == "func_nogrenades"  || cn == "func_regenerate"         ||
	    cn == "func_buyzone"     || cn == "func_respawnroom"        ||
	    cn == "func_simpleladder"||
	    cn == "color_correction_volume" || cn == "game_zone_player" ||
	    cn == "fog_volume"       || cn == "func_nobuild"            ||
	    cn == "func_bomb_target" || cn == "func_capturezone"        ||
	    cn == "func_respawnroomvisualizer" || cn == "func_portal_bumper" ||
	    cn == "dispenser_touch_trigger"    || cn == "func_static"   ||
	    cn == "func_stoptimer"   || cn == "func_starttimer"         ||
	    cn == "func_setcoursenames" || cn == "func_overbounce"      ||
	    SV_ClassPrefix(cn, "zone_"))
	{
		self.solid = SOLID_NOT;
		self.movetype = MOVETYPE_NONE;
		return;
	}

	/*
	  Everything else that owns brushes is solid world: func_door,
	  func_breakable, func_movelinear, func_tracktrain...  func_brush,
	  func_wall and func_wall_toggle have real spawn functions above and
	  never reach here.  These are frozen where they spawned -- see the
	  static-brush note above for why that is the right trade here.

	  SAY SO at developer 1.  Every entry in the list above cost a play session
	  and a bug report to find, because a brush entity we have never heard of
	  becomes a wall in complete silence.  One line per unrecognised classname
	  (the census dedupes, so it is one line even for 903 of them) turns the next
	  one into a console message.
	*/
	if (firstseen)
		dprint(sprintf("^3entity: %s is unknown and owns brushes -- made SOLID. "
		               "If Source does not block the player with it, it belongs "
		               "in the non-solid list in sv_entities.qc\n", cn));

	self.movetype = MOVETYPE_PUSH;
	self.solid = SOLID_BSP;
};
