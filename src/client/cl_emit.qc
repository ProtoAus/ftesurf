/*
===========================================================================
  cl_emit.qc -- Source's volumetric and emissive entities, drawn as particles.

  Eight classes, 22802 instances across roughly 650 of the 1310 shipped maps,
  and not one of them had ever drawn a pixel.  Measured over the whole library:

      func_dustmotes         4999   464 maps   brush volume
      env_fire              13633   211 maps   point
      func_dustcloud          529    93 maps   brush volume
      env_embers              344    76 maps   brush volume, angles meaningful
      env_spark               452    67 maps   point, angles on 100%
      env_smokestack         2443    52 maps   point jet          (build 51)
      func_smokevolume        166    45 maps   brush volume, opt-in
      env_bubbles             236    25 maps   brush volume, water columns

  For the top two these are usually the ONLY effect in the map: only 130 maps
  carry an info_particle_system at all, so nothing else was drawing anything.

  env_smokestack ARRIVED LATE AND SHOULD NOT HAVE.  Build 49 censused the eight
  classes it was handed and implemented seven; nothing prompted it to ask what
  ELSE in the library draws a flame.  The gap surfaced as a bug report -- "some
  of the fire in surf_anubis doesn't spawn" -- and the answer was that 498 of
  that map's 659 flame entities are env_smokestack, one per torch, while its
  161 env_fire are the brazier bowls and were all drawing correctly.  A census
  that only counts the classes it was asked about cannot tell you that.

  THREE CLASSES ON THE ORIGINAL LIST ARE DELIBERATELY ABSENT, by measurement:

      obb_volumefog             0 maps   it is in NONE of the 1310
      fog_volume                1 map    bhop_frigpx, and it needs cl_fog.qc
      env_dustpuff              2 maps   both triggered, so both invisible here
      env_splash                4 maps
      env_firesource           21 maps   HAS NO VISUAL KEYS.  fireradius and
                                         firedamage only -- it is a heat source
                                         that ignites nearby env_fires, and
                                         Source draws nothing for it either.

  env_fog_controller is not here because cl_fog.qc already does it, on 188 maps.

  WHY PARTICLES AND NOT POLYGONS, which is what cl_sprites.qc chose for the
  same lump.  A sprite is one static quad and the worst map holds 863 of them.
  These are not static: surf_shade's 339 dustmotes at the median SpawnRate of
  40/sec and a 3-5s lifetime implies about 54,000 live particles.  Simulating
  and drawing that from QC would be a second renderer; the engine's particle
  system carries 65536 (r_part_maxparticles) as a matter of routine.

  WHAT THIS FILE CONTROLS AND WHAT particles/ftesurf.cfg CONTROLS.
  pointparticles(effect, org, dir, count) has exactly three degrees of freedom,
  so the split is forced rather than chosen:

      here        the spawn POINT (picked inside the entity's own brush AABB,
                  or inside a box derived from firesize), the velocity, and
                  how many
      the cfg     colour, scale, alpha, lifetime, blend, texture, gravity

  `dir` carries speed as well as direction -- p_script.c:5230-5235 is the live
  branch and does `veladd *= VectorLength(dir)` with the velocity applied along
  normalize(dir).  Every block in the cfg sets `veladd 1`, so the vector passed
  here IS the velocity in units/sec.  That is what makes per-entity SpeedMax,
  firesize and Magnitude free, and it is why only colour had to be bucketed.

  THE ONE ENGINE TRAP.  pcount is `count * ptype->count` and the spawn loop is
  `for (i = 0; i < pcount; i++)` -- which ceils.  pointparticles(h, o, d, 0.01)
  spawns ONE particle, not zero.  So passing rate*frametime straight through
  would emit one particle per emitter per FRAME: 339 emitters at 300fps is
  101,700/sec on surf_shade alone.  Everything below goes through an
  accumulator that only ever passes a whole number >= 1.

  COST IS BOUNDED BY A BUDGET, NOT BY THE MAP.  A distance cull alone cannot do
  it -- nothing stops a map putting 200 emitters in one room -- so Emit_Frame
  runs two passes: sum the demand of everything that survives the cull, then
  scale every emitter's rate by budget/demand.  Scaling density rather than
  dropping emitters is what stops it popping as you walk.
===========================================================================
*/

#define EM_MAX        768       // emitters per map.  Worst single class measured
                                // is surf_stonework4's 531 env_fire; a map may
                                // hold more than one class, hence the headroom.
#define EM_FX_N        35       // effect handles.  See Emit_FxName.
#define EM_BUCKETS      6       // colour buckets.  See the cfg's header essay.

#define EM_BURST_MAX   24       // per-emitter per-frame ceiling, so a loading
                                // hitch cannot cash the accumulator out as one
                                // enormous burst on the frame the map appears.
#define EM_RATE_MAX   200       // per-emitter ceiling at LOAD time, and the
                                // default of vbsp_emit_ratemax.  SpawnRate
                                // reaches 900000 in the library, which is an
                                // authoring accident, not an intent -- but
                                // surf_boreas's one func_dustmotes writes 333
                                // and Source runs it at 333, so 200 there is
                                // 60% of Source's live count.

// Effect handle indices.  The six-wide runs are colour buckets.
#define FX_DUSTMOTE     0
#define FX_DUSTCLOUD    6
#define FX_EMBER       12
#define FX_BUBBLE      18
#define FX_FIRE        19
#define FX_FIRELIGHT   20
#define FX_SPARK       21
#define FX_SMOKE       22

/*
  BUILD 51: env_smokestack, and why it needs TWO families of six.

  2443 instances across 52 maps -- more instances than env_embers (344) and
  env_bubbles (236) put together, and it was missed in build 49's census because
  it was not on the list I was given.  surf_anubis carries 498 of them and they
  are its TORCHES: the map's 161 env_fire are the brazier bowls, and every torch
  flame on the map is an env_smokestack.  "Some of the fire doesn't spawn" was
  three quarters of the map's flames belonging to an unimplemented class.

  The class is a JET, not a volume: particles leave the origin along `angles` at
  Speed, spreading by SpreadSpeed, growing or shrinking from StartSize to
  EndSize over JetLength.  Which is why one family will not do -- StartSize and
  EndSize are baked into the effect block, and the library uses the class for two
  visually opposite things:

      StartSize 9 -> EndSize 4    x1488   SHRINKING.  A flame or a steam jet.
      StartSize 20..60 -> 30..80   ~700   GROWING.    Actual smoke.

  So the QC picks the family from the sign of (EndSize - StartSize) and the
  bucket from rendercolor, exactly as the dust and ember classes already pick a
  bucket.  Both families are six-wide because the colours are genuinely spread:
  248 175 78 x1488 (torch orange), 250 200 133 x374, 42 42 42 x134 (smoke grey),
  255 255 255 x127, 209 209 209 x80, 105 198 242 x75 (a cold blue steam).
*/
#define FX_STACKJET    23       // shrinking: flames, steam
#define FX_STACKPUFF   29       // growing: smoke columns

// Emitter kinds, used only for the counters and the report.
#define EK_DUST         0
#define EK_CLOUD        1
#define EK_EMBER        2
#define EK_BUBBLE       3
#define EK_FIRE         4
#define EK_SPARK        5
#define EK_SMOKE        6
#define EK_STACK        7
/*
  BUILD 52: info_particle_system, and it is the odd one out in this file.

  The other eight classes carry their whole appearance in their own entity keys,
  so cl_emit.qc can read a SpawnRate and a Color and pick one of the 35 baked
  effects.  This one carries only a NAME -- `effect_name "spawn_rain01"` -- and
  the thing it names lives in a .pcf, a binary particle library in the map's own
  pakfile.  tensor2's is 41 KB and defines 20 systems.

  So the effect is not chosen from a fixed table here; it is BAKED PER MAP by
  tools/pcf.py into particles/<map>.cfg, and em_eff carries the resolved handle
  itself rather than an index into em_fx.  What stays QC's job is the same three
  things pointparticles takes: where, how fast, how many -- and those come from
  data/mapparticles.txt, which the same tool writes.
*/
#define EK_PSYS         8
#define EK_N            9

#define PS_MAX         64       // baked systems per map.  tensor2 has 20.

float  em_fx[EM_FX_N];          // particleeffectnum handles, taken once at init

// ------------------------------------------------------------------ emitters
// EM_MAX each, in memalloc'd memory (Emit_Alloc): as global arrays these were
// 11,520 of csprogs' 131,072 definitions, which sat 516 from the limit.
vector *em_mins;                // the spawn box, world space
vector *em_size;                // maxs - mins
vector *em_mid;                 // its centre, for the cull
vector *em_vel;                 // base velocity, passed as pointparticles' dir
float  *em_jit;                 // extra omnidirectional speed, per particle
float  *em_rad;                 // cull radius, precomputed
float  *em_dist;                // the entity's own DistMax
float  *em_rate;                // EMISSIONS per second (not particles)
float  *em_burst;               // particles per emission -- 1 except for sparks
float  *em_eff;                 // index into em_fx; EK_PSYS: the handle itself;
                                // a sheet fire: its size class (see em_flfx)
float  *em_kind;
float  *em_acc;                 // fractional emission accumulator
float  *em_want;                // this frame's demand; 0 means culled
float  *em_lit;                 // fire only: may carry a dlight
float  *em_ltacc;
float  *em_drop;                // fire only: 1 = Source lights it on what is under it
float  em_n;

void() Emit_Alloc =
{
	if (em_mins)
		return;
	em_mins  = memalloc(sizeof(vector) * EM_MAX);
	em_size  = memalloc(sizeof(vector) * EM_MAX);
	em_mid   = memalloc(sizeof(vector) * EM_MAX);
	em_vel   = memalloc(sizeof(vector) * EM_MAX);
	em_jit   = memalloc(sizeof(float) * EM_MAX);
	em_rad   = memalloc(sizeof(float) * EM_MAX);
	em_dist  = memalloc(sizeof(float) * EM_MAX);
	em_rate  = memalloc(sizeof(float) * EM_MAX);
	em_burst = memalloc(sizeof(float) * EM_MAX);
	em_eff   = memalloc(sizeof(float) * EM_MAX);
	em_kind  = memalloc(sizeof(float) * EM_MAX);
	em_acc   = memalloc(sizeof(float) * EM_MAX);
	em_want  = memalloc(sizeof(float) * EM_MAX);
	em_lit   = memalloc(sizeof(float) * EM_MAX);
	em_ltacc = memalloc(sizeof(float) * EM_MAX);
	em_drop  = memalloc(sizeof(float) * EM_MAX);
};
void() Emit_AllocLife;

// ------------------------------------------------------------------ counters
float  em_seen[EK_N];           // found in the lump
float  em_live[EK_N];           // actually emitting
float  em_off[EK_N];            // skipped: start-off, disabled or invisible
float  em_norate[EK_N];         // skipped: rate <= 0 reached Emit_Add.  Source
                                // draws ONE particle for such an entity, ever
                                // (see the note in the dust branch), so this
                                // is a named skip rather than a fallback.
float  em_frozen;               // skipped: Frozen 1
float  em_clamped;              // SpawnRate clamped to em_ratemax
float  em_ratemax;              // vbsp_emit_ratemax as read at map load; the
                                // ceiling Emit_Add applies and emit_list prints
float  em_over;                 // skipped: hit EM_MAX
float  em_child;                // baked .pcf children started with their parent
                                // (EK_PSYS only; they are in em_live too, so
                                // Emit_List adds this back to the residual)
float  em_reload;               // times the effect set was found missing and
                                // re-exec'd.  0 on an engine with Patch 272;
                                // 1 per map on one without; a number that
                                // keeps climbing means something is unloading
                                // the set behind us -- see the essay in
                                // Emit_Frame
float  em_reload_t;             // next second at which we are allowed to check
float  em_drawn;                // 0 from Emit_LoadForMap until Emit_Frame has
                                // run once since: that first frame arms
                                // em_reload_t from its own `time` instead of
                                // checking (see Emit_Frame)
float  em_any;                 // total seen, whatever became of them.  Read by
                                // cl_gfx.qc to grey its row out, so it counts
                                // what the MAP holds, not what we chose to draw
                                // -- a row that greys out because you turned the
                                // feature off would be nonsense.

string vbsp_em_map;             // lazy-reload latch, as cl_sprites.qc:115 uses.
                                // Written at the END of Emit_LoadForMap and
                                // only if the entity lump opened -- see there.
float  em_throttle;             // last frame's budget scale, for the report
float  em_demand;               // last frame's unthrottled demand
float  em_fpsn, em_fpst;        // frames since, and the time of, the last emit_list

void() Emit_LoadForMap;

/*
===========================================================================
  Registration
===========================================================================
*/

/*
  The effect names.  NO DOT, AND THAT IS THE WHOLE POINT.

  BUILD 51 CHANGED THIS AFTER THE FEATURE WAS FOUND NEVER TO HAVE DRAWN.
  Builds 49 and 50 asked for "ftesurf.dustmote_0" and relied on the engine's
  implicit namespace auto-load: PScript_FindParticleType splits on the dot,
  misses, and calls P_LoadParticleSet("ftesurf") at p_script.c:674-675, which
  reads particles/ftesurf.cfg and feeds it to the command buffer.

  That mechanism has a failure mode with no recovery and no message.
  P_LoadParticleSet writes the config name into its `loadedconfigs` list at
  p_script.c:3709-3712 -- BEFORE it reaches FS_LoadFile at :3746 -- and the
  dedupe check at :3702-3707 makes every later call return false immediately.
  So if the very first attempt does not find the file, for any reason, the name
  is permanently marked as loaded, the load is never retried for the rest of the
  session, and the only diagnostic is a single Con_Printf nobody was watching
  for.  Every emitter then silently emits through an unresolved handle, which is
  a safe no-op -- so the subsystem reports itself healthy while drawing nothing.
  That is exactly what was measured: `0 particles, 65536 free` with 33 emitters
  inside their cull, and particleeffectquery returning "" for dustmote_0.

  So the dependency is gone rather than debugged.  The names carry a `ftesurf_`
  PREFIX instead of a `ftesurf.` NAMESPACE, and PScript_FindParticleType's
  `if (*cfg) P_LoadParticleSet(...)` arm is never taken because there is no dot
  to split on.  One mechanism, at a time we choose.

  BUILD 51b MOVED WHERE THAT TIME IS, AND THAT -- NOT THE ABOVE -- IS WHAT WAS
  ACTUALLY KILLING IT.  51 exec'd the file from cfg/default.cfg at boot, which
  is before the particle system exists, and FTE discards an r_part block handed
  to it in that window without printing anything at all (p_script.c:1141-1170,
  and r_part.c:684 says it is deliberate).  The load now happens from CSQC at
  map load, in Emit_LoadForMap, where the psys bake has always loaded from and
  demonstrably works.  The full chain, the citations and the two log lines that
  date it are in the essay there; this note exists so that a reader who starts
  at the top is not left believing the auto-load trap was the whole story.  It
  was real, and it was not the bug.

  AND 51b's OWN FIX WAS UNDONE BY THE ENGINE, A FEW MILLISECONDS LATER, ON
  EVERY MAP LOAD.  cl_parse.c forces the r_particledesc callback once the world
  model is loaded (to pick up per-map sets), and that callback opens with
  R_Particles_KillAllEffects.  It fires AFTER CSQC_WorldLoaded.  Found with a
  per-frame census in the engine, not by reading -- the four call sites use
  the cvar's alias r_particlesdesc, which a grep for r_particledesc does not
  match.  Engine Patch 272 makes the kill spare explicitly-loaded effects
  (r_part_keepuser); the essay in Emit_LoadForMap has the log lines.

  Nothing here writes r_particledesc.  On the old engine that called
  R_Particles_KillAllEffects and then did NOT reload while connected
  (p_script.c:3821-3852); three arms were tried -- the saved config's
  "classic", "" and "high" -- and all drew nothing, which is unsurprising in
  hindsight: the callback only loads sets when cls.state != ca_connected
  (p_script.c:3823), so setting it in a map killed the table and reloaded none
  of it.  With Patch 272 our effects survive it, but it is still a footgun on
  a CVAR_SEMICHEAT cvar and the right answer is still to leave it alone.
*/
string(float i) Emit_FxName =
{
	if (i < FX_DUSTCLOUD)  return strcat("ftesurf_dustmote_",  ftos(i - FX_DUSTMOTE));
	if (i < FX_EMBER)      return strcat("ftesurf_dustcloud_", ftos(i - FX_DUSTCLOUD));
	if (i < FX_BUBBLE)     return strcat("ftesurf_ember_",     ftos(i - FX_EMBER));
	if (i == FX_BUBBLE)    return "ftesurf_bubble";
	if (i == FX_FIRE)      return "ftesurf_fire";
	if (i == FX_FIRELIGHT) return "ftesurf_fire_light";
	if (i == FX_SPARK)     return "ftesurf_spark";
	if (i == FX_SMOKE)     return "ftesurf_smokevol";
	if (i < FX_STACKPUFF)  return strcat("ftesurf_stackjet_",  ftos(i - FX_STACKJET));
	return strcat("ftesurf_stackpuff_", ftos(i - FX_STACKPUFF));
};

// Up here rather than beside the report that mostly uses it, because
// Emit_LoadForMap names the classes too and QC wants the callee first.
string(float k) Emit_KindName =
{
	if (k == EK_DUST)   return "func_dustmotes";
	if (k == EK_CLOUD)  return "func_dustcloud";
	if (k == EK_EMBER)  return "env_embers";
	if (k == EK_BUBBLE) return "env_bubbles";
	if (k == EK_FIRE)   return "env_fire";
	if (k == EK_SPARK)  return "env_spark";
	if (k == EK_SMOKE)  return "func_smokevolume";
	if (k == EK_STACK)  return "env_smokestack";
	return "info_particle_system";
};

/*
===========================================================================
  The baked .pcf index -- data/mapparticles.txt, written by tools/pcf.py.

      psys <map> <name> <rate> <lx> <ly> <lz> <maxp> <die> <maxdist>
           [<ox> <oy> <oz> <wx> <wy> <wz> <jit> <parent|->]

  BUILD 53: EIGHTEEN COLUMNS, AND THE FIRST TEN MEAN WHAT THEY DID.  Columns
  4-6 are the .pcf's LOCAL-frame velocity and are rotated by the entity's
  angles (Emit_PsysVel); ox oy oz is the spawn box's centre, world space, added
  to the entity origin; wx wy wz is a world-frame velocity (wind, and the
  terminal speed a Movement Max Velocity cap produces) added unrotated; jit is
  the .pcf's isotropic random_speed, handed to em_jit; and a line whose last
  column names a parent is an extra emitter started with that parent (the
  EK_PSYS arm of Emit_LoadForMap).  A ten-column line from an older bake reads
  as local-only with no offset, no jitter and no children, which for an entity
  at angles 0 0 0 is exactly what build 52 did.

  Only three of those reach the engine from here: the rate, the base velocity
  (pointparticles' `dir`, and |dir| IS the speed), and the draw distance.
  Everything else about the effect -- texture, colour, alpha, lifetime, gravity,
  and the spawn BOX -- is in the r_part block, because an r_part block can say
  `spawnorg` and QC would only be duplicating it.

  THE RATE IN THAT FILE IS NOT THE PCF'S emission_rate.  A system with
  emission_rate 800 and max_particles 1500 over a 10s lifetime saturates at
  150/s and Source simply stops emitting; the tool writes the minimum of the
  two.  Taking the nominal figure would ask for five times the particles the
  map's author asked for.
===========================================================================
*/
string ps_name[PS_MAX];
float  ps_rate[PS_MAX];
vector ps_vel[PS_MAX];          // LOCAL frame: rotated by the entity's angles
vector ps_ofs[PS_MAX];          // box centre, world, added to the entity origin
vector ps_wvel[PS_MAX];         // WORLD frame: wind and terminal speed, unrotated
float  ps_jit[PS_MAX];          // isotropic random_speed, for em_jit
string ps_parent[PS_MAX];       // "" on a stand-alone line; the parent's name on a child link
float  ps_dist[PS_MAX];
float  ps_n;
float  ps_links;                // how many of ps_n are child links
float  ps_zoned;                // ps_name[]/ps_parent[] hold strzone handles to give back

void() Emit_PsysFree =
{
	local float i;
	if (ps_zoned)
		for (i = 0; i < ps_n; i = i + 1)
		{
			strunzone(ps_name[i]);
			strunzone(ps_parent[i]);
		}
	ps_zoned = FALSE;
	ps_n = 0;
	ps_links = 0;
};

// `mname`, not `mapname`: there is a global of that name and shadowing it is
// the same trap the mins/maxs note in Emit_LoadForMap records.
void(string mname) Emit_PsysLoad =
{
	local float fh, i, n;
	local string l;

	Emit_PsysFree();

	fh = fopen("data/mapparticles.txt", FILE_READ);
	if (fh < 0)
		return;                 // no baked particles anywhere; not an error

	// Bounded rather than while(1): a truncated or garbage file must not be
	// able to spin the client, and the library's worst map is nowhere near this.
	for (i = 0; i < 4096; i = i + 1)
	{
		l = fgets(fh);
		if (!l)
			break;
		n = tokenize(l);
		if (n < 10)
			continue;
		if (argv(0) != "psys" || argv(1) != mname)
			continue;
		if (ps_n >= PS_MAX)
			break;
		ps_name[ps_n] = strzone(argv(2));
		ps_rate[ps_n] = stof(argv(3));
		ps_vel[ps_n]  = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
		ps_dist[ps_n] = stof(argv(9));
		// The build-53 columns.  Absent on an older bake: no offset, nothing
		// in the world frame, no jitter, no parent -- what build 52 read.
		ps_ofs[ps_n]  = '0 0 0';
		ps_wvel[ps_n] = '0 0 0';
		ps_jit[ps_n]  = 0;
		if (n >= 18)
		{
			ps_ofs[ps_n]  = [stof(argv(10)), stof(argv(11)), stof(argv(12))];
			ps_wvel[ps_n] = [stof(argv(13)), stof(argv(14)), stof(argv(15))];
			ps_jit[ps_n]  = stof(argv(16));
		}
		if (n >= 18 && argv(17) != "-")
		{
			ps_parent[ps_n] = strzone(argv(17));
			ps_links = ps_links + 1;
		}
		else
			ps_parent[ps_n] = strzone("");
		ps_n = ps_n + 1;
	}
	fclose(fh);
	ps_zoned = TRUE;

	/*
	  EXEC THE BAKED FILE OURSELVES rather than letting a dotted effect name
	  auto-load it.  particles/<map>.cfg used to be reached by asking for
	  "<map>.<system>", which makes PScript_FindParticleType split on the dot and
	  call P_LoadParticleSet -- and that function records the config name
	  (p_script.c:3709) BEFORE it tries FS_LoadFile (:3746), then refuses every
	  retry (:3702-3707).  One early miss is therefore permanent for the whole
	  session, silent, and unrecoverable, while emitting through the unresolved
	  handle stays a safe no-op -- so every counter reports perfect health into a
	  dead pool.  particles/ftesurf.cfg was in exactly that state from build 49
	  until 2026-09-08 and nobody could see it.

	  Only when the map actually has a bake: 1180 of the 1310 carry no
	  info_particle_system, and an exec of a file that is not there is an error
	  message rather than a no-op.  Which is the point -- when it IS supposed to
	  be there and is not, that error is the thing that says so.

	  THE EXEC LINE ITSELF LIVES IN Emit_LoadForMap, behind its opened guard,
	  since build 53.  This function only fills the table.  If it exec'd here,
	  the per-frame retry that guard exists to allow (a map whose entity lump
	  was not yet readable) would exec the file once per frame until it was.
	*/
};

// -1 when the map ships no bake for that effect_name, which is the common case
// and is why an unbaked map costs one linear scan of an empty table.
float(string nm) Emit_PsysFind =
{
	local float i;
	for (i = 0; i < ps_n; i = i + 1)
		if (ps_name[i] == nm)
			return i;
	return -1;
};

/*
  The velocity to hand pointparticles for baked system i, at an entity whose
  makevectors(angles) is current (Emit_LoadForMap calls it before this).

  THE .pcf's VELOCITY IS IN THE ENTITY'S FRAME.  Source's Velocity Random
  key is literally speed_in_local_coordinate_system, and control point 0 of
  an info_particle_system follows the entity's origin AND angles:
  particle_property.cpp:644-645 takes GetVectors from the entity under
  PATTACH_ABSORIGIN_FOLLOW (which c_particle_system.cpp:134 uses) and :669
  hands them to SetControlPointOrientation.  surf_boreas' snow is the proof
  and the victim: tendies_snow01 is local X -256..-512 on an entity pitched
  -90, so forward is UP (FTE's AngleVectors: forward_z = -sin(pitch), the
  same formula Source inherited) and the snow FALLS at 384; its sibling
  pre-fill box runs 6000 units DOWN in world Z, 16 s of that fall.  Passing
  the column unrotated, as build 52 did, sends it along world -X forever.

  x -> forward is proved by that geometry.  y -> left (minus v_right) is
  Source's Y convention and is NOT verified against the closed particle lib;
  no baked system on either map has a local Y component, so nothing rests on
  the sign yet.  The world column (wind; the terminal speed a Movement Max
  Velocity cap becomes) is added as it is.  surf_tensor2 is untouched by this
  for a narrower reason than 'its entities are unrotated' -- 27 of its 44 carry
  a yaw of 90, 180 or 270 -- every tensor2 local velocity is pure Z and no
  tensor2 entity has pitch or roll, and a yaw leaves v_up alone, so this is
  the identity there and build 52's numbers.
*/
vector(float i) Emit_PsysVel =
{
	local vector l;
	l = ps_vel[i];
	return v_forward * l_x - v_right * l_y + v_up * l_z + ps_wvel[i];
};

/*
===========================================================================
  env_fire the way Source draws it (Patch 643).

  C_FireSmoke::Start (c_fire_smoke.cpp:165-190) picks ONE particle system by
  floor(firesize / 36): env_fire_tiny, _small, _medium or _large, all four in
  particles/fire_01.pcf.  Each is two layers of animated sprites cut from one
  atlas (the system and its _b child) plus a few embers.  The numbers below are
  those systems' own, read out of the .pcf with tools/pcf_resources.py.

  NOTHING HERE IS A FILE.  The effects and the shader are text this progs hands
  the engine, because a lobby gives a player csprogs.dat but not particles/ or
  glsl/ (cl_playerfade.qc has the same reason).  The atlas is Valve's and is
  never shipped: it is drawn from whichever mounted game carries it, and with
  none mounted env_fire stays on the ftesurf_fire orbs.

  SMOKE (Patch 656).  Unless spawnflags 2, Start asks for env_fire_<size>_smoke
  instead (c_fire_smoke.cpp:173-186), which is the same flame as its child under
  a column of smoke: Emit_SmokeSpec.  39% of the library's fires.

  NOT DRAWN: env_fire_random_puff, and the blend between two frames.
===========================================================================
*/
#define FL_SLOTS       17       // per size class: 6 + 6 flame effects, 1 embers, 2 + 2 smoke
#define FL_ATLAS       "materials/particle/fire_burning_character/fire_burning_character.vtf"
#define FL_SMOKE1      "materials/particle/smoke1/smoke1.vtf"
#define FL_VISTA       "materials/particle/vistasmokev1/vistasmokev1.vtf"
#define FL_REACH       10000    // a fire emits to here: Source has no limit but PVS (the
                                // systems say 100000), env_fire_large_smoke and _smoke_b
                                // alone say 10000
#define FL_NEAR        2000     // and past here it thins, as 1 / distance
#define FL_DROPSOLIDS  2048     // brush entities stood up for Emit_DropFires' traces

float *em_flfx;                 // [4 * FL_SLOTS] handles, filled as classes are defined
float  em_flwant;               // size classes this map's fires use, a bit each
float  em_flmask;               // those of them defined so far (Emit_FlameStep)
string em_flwhy;                // "" = this map's env_fire use the sheet; else why not
string em_smwhy;                // "" = and their smoke is drawn; else why not
float  em_smwant;               // size classes with a fire that smokes, a bit each
float  em_flsmoke;              // sheet fires with smoke
float  em_flglow;               // fires without spawnflags 32, No glow
.float em_dropsolid;            // a brush entity stood up for the drop traces
float  em_fldropwant;           // fires without spawnflags 16
float  em_fldrop, em_fldropsum, em_fldropmax;   // of them, moved, and how far
float  em_flnofloor;            // with no floor within 1024, left where they are
float  em_flinside;             // whose entity is inside something solid, left too
float  em_fldropover;           // brush entities past FL_DROPSOLIDS, not stood up
float  em_flin, em_flthin;      // last frame: sheet fires in reach, and those thinned

// The system (layer 0, sequences 3-5) and its _b child (layer 1, sequences 0-2):
//   radius min max | alpha min max | grey min max | rotation +- | spawn disc |
//   lift of the centre in radii | rise | rise jitter xy z | acceleration up | fps
string(float cls, float layer) Emit_FlameSpec =
{
	if (!layer)
	{
		if (cls == 0) return "16 20  80 180  155 189   8   7  0.25  10    16 6     70  20";
		if (cls == 1) return "16 24  80 180  155 189   8  10  0.25  11.5  16 7.5   80  20";
		if (cls == 2) return "16 32  80 180  177 222   8  19  0.3   22    16 10   115  27";
		return               "24 32  80 180  161 222   8  20  0.3   20.5  24 8    100  20";
	}
	if (cls == 0) return "8 24   100 180  146 189  24   6  0.5    8     0 4     80  15";
	if (cls == 1) return "24 32  100 180  146 189  24  12  0.475  38.5  0 14.5  70  15";
	if (cls == 2) return "32 48  100 180  158 189  24  18  0.5    36    0 12   120  15";
	return               "32 48  120 180  156 194  24  18  0.45   72    0 24    90  14";
};

// Particles a second: the system, its _b child, its embers.
vector(float cls) Emit_FlameRates =
{
	if (cls == 0) return '8 8 3';
	if (cls == 1) return '9 8 3';
	if (cls == 2) return '17 7 8';
	return '17 12 8';
};

/*
  One layer, one sequence, one way round.  "lifetime from sequence" makes the
  life the sequence's length at the layer's frame rate, so `die` is fixed and
  the vertex alpha (1 falling to 0 at death) is the fraction of life left.

  THE COLOUR CHANNELS ARE NOT A COLOUR.  pointparticles carries nothing per
  particle, so the block randomises them and the shader reads them: red is the
  particle's alpha ("Alpha Random"), green its grey tint ("Color Random"), blue
  the layer's mean radius in units (for $startfadesize).

  A sprite's half-side is 0.2652 * scale at scalefactor 1 and rotation 45
  (particles/ftesurf.cfg, UNITS), so scale is the radius times 3.771.
*/
string(float cls, float layer, float seq, float flip, string nm) Emit_FlameBlock =
{
	local float rmin, rmax, rmid, die, fps;
	local string s;

	tokenize(Emit_FlameSpec(cls, layer));
	rmin = stof(argv(0));
	rmax = stof(argv(1));
	rmid = (rmin + rmax) * 0.5;
	fps  = stof(argv(13));
	die  = Emit_FlameFrames(seq) / fps;

	s = sprintf("r_part %s\n{\ntexture ftesurf_flame\ntype normal\nblend blendalpha\nscalefactor 1\nscale %g %g\nrotation %g %g\n",
	            nm, rmin * 3.771, rmax * 3.771, 45 - stof(argv(6)), 45 + stof(argv(6)));
	s = strcat(s, sprintf("rgb %g %g %g\nrgbrand %g %g 0\nalpha 1\nalphadelta %g\ndie %g\ncount 1\n",
	            stof(argv(2)), stof(argv(4)), rmid,
	            stof(argv(3)) - stof(argv(2)), stof(argv(5)) - stof(argv(4)), -1 / die, die));
	// veladd 0: the direction pointparticles is handed carries nothing here.
	s = strcat(s, sprintf("spawnmode ball\nspawnorg %g 0\norgbias 0 0 %g\nveladd 0\nvelbias 0 0 %g\nvelwrand %g %g %g\ngravity %g\n",
	            stof(argv(7)), stof(argv(8)) * rmid, stof(argv(9)),
	            stof(argv(10)), stof(argv(10)), stof(argv(11)), -stof(argv(12))));
	return strcat(s, sprintf("texanim clamp %g\n", fps), Emit_FlameRows(seq, flip), "}\n");
};

// env_embers_tiny/_small/_medium/_large: glowing specks thrown up off the flame.
//   life min max | spawn ball | height | rise | acceleration up
// Radius 1-3 in Source, of particle/particle_glow_05, whose glow is down to half
// at 0.12 of the sprite; ftesurf_dot is at 0.37 (both measured), so a third of
// the size draws the same speck.  At full size they were the old orbs again.
string(float cls, string nm) Emit_EmberBlock =
{
	local string s;

	if (cls == 0)      s = "0.5 1   8  32  35  10";
	else if (cls == 1) s = "0.5 2   8  44  35  20";
	else if (cls == 2) s = "0.5 2  24  40  25  30";
	else               s = "0.5 2  48  48  25  40";
	tokenize(s);
	// No alphadelta: the engine then fades it to nothing over its own life.
	s = sprintf("r_part %s\n{\ntexture ftesurf_dot\nblend adda\nscalefactor 1\nscale 1.25 3.75\nrgb 169 16 16\nrgbrand 69 188 2\nrgbrandsync 1\nalpha 1\ndie %g %g\ncount 1\n",
	            nm, stof(argv(0)), stof(argv(1)));
	return strcat(s, sprintf("spawnmode ball\nspawnorg %g %g\norgbias 0 0 %g\nveladd 0\nvelbias 0 0 %g\nvelwrand 15 15 13\ngravity %g\nflurry 20\n}\n",
	            stof(argv(2)) * 0.5, stof(argv(2)), stof(argv(3)), stof(argv(4)), -stof(argv(5))));
};

/*
  The end of a fragment shader for a sprite Source alpha-blends, given c (its
  colour in linear light times its alpha) and a: the straight line
  Emit_MoteShader's comment explains.  No fog: SpriteCard draws without it
  (spritecard_ps20b.fxc:184, PIXEL_FOG_TYPE_NONE).
*/
#define EM_BLEND_LINE \
	" float ml = dot(c, vec3(0.3, 0.59, 0.11));\n" \
	" float g = (1.0 - a) * 0.0474;\n" \
	" float k = (pow(ml + 1.0 - a, 0.4545) - pow(ml + g, 0.4545)) / 0.75;\n" \
	" gl_FragColor = vec4(max(pow(c + g, vec3(0.4545)) - 0.25 * k, 0.0), 1.0 - k);\n"

/*
  env_fire_tiny_smoke, _small_smoke, _medium_smoke, _large_smoke and (layer 1)
  env_fire_large_smoke_b, out of particles/fire_01.pcf:
    sheet (0 smoke1, 1 vistasmokev1) | radius min max | scale at the end of its
    life | alpha min max, of 255 | life min max | where the fade out starts |
    colour 1 | colour 2 | the colour it fades to | that fade's start and end |
    centre up | spawn disc across, up | rise | rise jitter xy, z | acceleration
    up | frames a second | $startfadesize $endfadesize (the .vmt's: smoke1's
    as Half-Life 2 and Momentum have it; Counter-Strike: Source's says .9 1.3)
  The lifts and rises are the systems' several position and velocity terms
  summed ("Position Within Sphere", "Position Modify Offset", "Velocity Noise").
*/
string(float cls, float layer) Emit_SmokeSpec =
{
	if (layer)
		return "1  18 24  5  120 140  3 4  0.5   255 131 9  255 120 0   52 50 50  0.2 0.6  60  24 12  48.5  12 11.5  45  20    1 1.4";
	if (cls == 0) return "0  12 19  7   40 60   2 3  0.5   255 131 9  194 108 32  28 24 21  0.1 0.7  25   4 7   25    0 3     35  0     0.7 1.1";
	if (cls == 1) return "0  12 19  7   40 60   3 4  0.5   255 131 9  194 108 32  28 24 21  0.1 0.7  28   4 4   25    0 3     35  0     0.7 1.1";
	if (cls == 2) return "1  12 19  7   60 70   3 4  0.65  255 131 9  194 108 32  98 98 98  0.1 0.5  40  24 16  25    0 3     75  20    1 1.4";
	return               "1  18 24  5   90 100  3 4  0.5   255 131 9  194 108 32  59 58 56  0.1 0.8  80  48 32  56.5  12 9.5   75  12.8  1 1.4";
};

// Smoke particles a second: the system's, and env_fire_large_smoke_b's.
vector(float cls) Emit_SmokeRates =
{
	return (cls == 3) ? '2 4 0' : '4 0 0';
};

/*
  One smoke effect.  smoke1 is six still pictures and `tcoords` picks one at
  random; vistasmokev1 is a 16-frame loop, sequence seq.

  As the flames, the colour channels carry what the shader needs: red the life,
  green a random number for "Color Random", blue the alpha, alpha the age.  The
  engine holds a puff to the longest life and the shader ends it at its own.

  THE GROWTH IS A STRAIGHT LINE where Source's "Radius Scale" is a bias curve
  (0.4) on a random radius and a random life: `scaledelta` takes the mean radius
  to its end scale in the mean life.  The mean puff ends right and is a fifth
  too wide half way; the smallest, longest-lived one ends 41% too wide and the
  largest, shortest-lived 26% too narrow.
*/
string(float cls, float layer, float seq, string nm) Emit_SmokeBlock =
{
	local float rmin, rmax, lmin, lmax, vista;
	local string s;

	tokenize(Emit_SmokeSpec(cls, layer));
	vista = stof(argv(0));
	rmin = stof(argv(1));
	rmax = stof(argv(2));
	lmin = stof(argv(6));
	lmax = stof(argv(7));

	s = sprintf("r_part %s\n{\ntexture ftesurf_smoke%g%g\ntype normal\nblend blendalpha\nscalefactor 1\nscale %g %g\nscaledelta %g\n",
	            nm, cls, layer, rmin * 3.771, rmax * 3.771,
	            3.771 * (rmin + rmax) * 0.5 * (stof(argv(3)) - 1) / ((lmin + lmax) * 0.5));
	s = strcat(s, sprintf("rgbf %g 0 %g\nrgbrandf %g 1 %g\nalpha 0\nalphadelta 1\ndie %g\ncount 1\n",
	            lmin, stof(argv(4)) / 255, lmax - lmin, (stof(argv(5)) - stof(argv(4))) / 255, lmax));
	s = strcat(s, sprintf("spawnmode ball\nspawnorg %g %g\norgbias 0 0 %g\nveladd 0\nvelbias 0 0 %g\n",
	            stof(argv(21)), stof(argv(22)), stof(argv(20)), stof(argv(23))));
	s = strcat(s, sprintf("velwrand %g %g %g\ngravity %g\n",
	            stof(argv(24)), stof(argv(24)), stof(argv(25)), -stof(argv(26))));
	if (!vista)
		return strcat(s, "tcoords " SM1_TCOORDS "\n}\n");
	return strcat(s, sprintf("texanim loop %g\n", stof(argv(27))), Emit_VistaRows(seq), "}\n");
};

/*
  SpriteCard, alpha blended (smoke1.vmt, vistasmokev1.vmt): the texture times
  the particle's colour, premultiplied.  The particle's colour is "Color
  Random" fading to the system's grey ("Color Fade"), its alpha "Alpha Random"
  under "Alpha Fade and Decay" (in over the first 0.15 of the life; that
  operator's curve is in the closed particle library, a smoothstep here).

  vistasmokev1.vmt is $dualsequence with $sequence_blend_mode 1: the ALPHA of
  sequences 0-3 over the COLOUR of sequences 4-9, zoomed and slowly animated
  (spritecard_ps20b.fxc, COMBINE_MODE_USE_FIRST_AS_ALPHA_MASK_ON_SECOND).  The
  second picture is drawn as its mean colour, SMV_GREY.

  $startfadesize / $endfadesize as spritecard_vs20.fxc:187-202: radius over
  distance, off the particle's colour as well as its alpha.  The radius is read
  off the quad the engine made, and the distance is this fragment's where
  Source's is the sprite's middle.  The blend is the motes' (Emit_MoteShader).

  `sort banner` is only a bucket drawn before the flame's: Source draws a
  system's children after it, so its flame is over its smoke.  In one bucket the
  order was the engine's run list, and smoke settled on top.

  NOT DRAWN: $depthblend (both materials soften where a puff meets a wall or
  the floor; here a large puff is cut by them in a hard line).
*/
void(float cls, float layer) Emit_SmokeShader =
{
	local string s;
	local float vista;

	tokenize(Emit_SmokeSpec(cls, layer));
	vista = stof(argv(0));
	// float(): %g writes 1 for 1.0, and GLSL 1.10 will not multiply an int by a float.
	s = sprintf("#define FOUT float(%g)\n#define SFS float(%g)\n#define EFS float(%g)\n#define CELL float(%g)\n#define CF0 float(%g)\n#define CF1 float(%g)\n",
	            stof(argv(8)), stof(argv(28)), stof(argv(29)), vista ? SMV_CELL : SM1_CELL, stof(argv(18)), stof(argv(19)));
	s = strcat(s, sprintf("#define C1 vec3(%g, %g, %g)\n#define C2 vec3(%g, %g, %g)\n",
	            stof(argv(9)) / 255, stof(argv(10)) / 255, stof(argv(11)) / 255,
	            stof(argv(12)) / 255, stof(argv(13)) / 255, stof(argv(14)) / 255));
	s = strcat(s, sprintf("#define CE vec3(%g, %g, %g)\n", stof(argv(15)) / 255, stof(argv(16)) / 255, stof(argv(17)) / 255),
	            vista ? "#define TEXRGB vec3(" SMV_GREY ")\n" : "#define TEXRGB t.rgb\n");
	s = strcat("{\nglslprogram\n{\n!!ver 110\n!!samps img=0\n", s,
		"varying vec2 tc;\n"
		"varying vec4 vc;\n"
		"varying vec3 ev;\n"
		"#ifdef VERTEX_SHADER\n"
		"attribute vec2 v_texcoord;\n"
		"attribute vec4 v_colour;\n"
		"uniform mat4 m_modelview;\n"
		"void main()\n{\n"
		" tc = v_texcoord;\n"
		" vc = v_colour;\n"
		" ev = (m_modelview * vec4(v_position, 1.0)).xyz;\n"
		" gl_Position = ftetransform();\n"
		"}\n#endif\n"
		"#ifdef FRAGMENT_SHADER\n"
		"void main()\n{\n"
		" float f = vc.a / vc.r;\n"
		" if (f >= 1.0)\n"
		"  discard;\n"
		" vec4 t = texture2D(s_img, tc);\n"
		" float a = vc.b * smoothstep(0.0, 0.15, f) * (1.0 - smoothstep(FOUT, 1.0, f)) * t.a;\n"
		" float l = length(ev);\n"
		" float rad = 0.5 * CELL / max(length(vec2(dFdx(tc.x), dFdy(tc.x))), 0.000001) * length(vec2(dFdx(ev.x), dFdy(ev.x)));\n"
		" float sf = 1.0 - clamp((rad - SFS * l) / ((EFS - SFS) * l), 0.0, 1.0);\n"
		" a *= sf;\n"
		" vec3 c = pow(mix(mix(C1, C2, vc.g), CE, clamp((f - CF0) / (CF1 - CF0), 0.0, 1.0)) * TEXRGB * sf, vec3(2.2)) * a;\n"
		EM_BLEND_LINE
		"}\n#endif\n"
		"}\nsort banner\ncull disable\n{\nmap ");
	shaderforname(sprintf("ftesurf_smoke%g%g", cls, layer), strcat(s, vista ? FL_VISTA : FL_SMOKE1,
		"\nblendfunc gl_one gl_one_minus_src_alpha\nrgbgen vertex\nalphagen vertex\nnodepth\n}\n"
		"polygonoffset\nsurfaceparm noshadows\nsurfaceparm nodlight\n}\n"));
};

/*
  Source's SpriteCard with $addself (fire_env_fire.vmt: $addself 1,
  $overbrightfactor 2.15, $startfadesize .425, $endfadesize .525), as
  spritecard_ps20b.fxc:139 and :173-178 compute it: the texture premultiplied
  by its alpha and the particle's, then added to itself, drawn ONE /
  ONE_MINUS_SRC_ALPHA, and without fog (:184, PIXEL_FOG_TYPE_NONE).

  SOURCE BLENDS THAT IN LINEAR LIGHT AND THIS FRAMEBUFFER DOES NOT.  Measured:
  with the colour premultiplied in gamma space the same sprites drew a fire that
  was mostly not there, because a quarter-covered layer adds a quarter where
  linear light adds half.  So the colour goes out as the linear sum's own
  encoding, and the destination factor is the one that makes the blend exact on
  black and on a mid-grey of 0.6 (0.325 linear); between and beyond those it is
  close, and a pile of layers levels off instead of burning out.

  Registered again on every map load and every repair: a renderer restart
  forgets a shader made this way.
*/
void() Emit_FlameShader =
{
	shaderforname("ftesurf_flame",
		"{\nglslprogram\n{\n"
		"!!ver 110\n"
		"!!samps img=0\n"
		"varying vec2 tc;\n"
		"varying vec4 vc;\n"
		"varying float dist;\n"
		"#ifdef VERTEX_SHADER\n"
		"attribute vec2 v_texcoord;\n"
		"attribute vec4 v_colour;\n"
		"void main()\n{\n"
		" tc = v_texcoord;\n"
		" vc = v_colour;\n"
		" gl_Position = ftetransform();\n"
		" dist = gl_Position.w;\n"
		"}\n#endif\n"
		"#ifdef FRAGMENT_SHADER\n"
		"void main()\n{\n"
		" vec4 t = texture2D(s_img, tc);\n"
		// "Alpha Fade Out Random": over the last quarter of the life.
		" float a = vc.r * clamp(vc.a * 4.0, 0.0, 1.0);\n"
		// $startfadesize/$endfadesize: a sprite wider than the view fades out.
		" float r = vc.b * 255.0;\n"
		" a *= clamp((dist - r / 0.525) / (r / 0.425 - r / 0.525), 0.0, 1.0);\n"
		" float pa = t.a * a;\n"
		" vec3 c = pow(t.rgb, vec3(2.2)) * (2.15 * pa * (1.0 + 2.15 * a)) * pow(vc.g, 2.2);\n"
		" float m = dot(c, vec3(0.3, 0.59, 0.11));\n"
		" float k = (pow(0.325 * (1.0 - pa) + m, 0.4545) - pow(m, 0.4545)) / 0.6;\n"
		" gl_FragColor = vec4(pow(c, vec3(0.4545)), 1.0 - k);\n"
		"}\n#endif\n"
		"}\nsort additive\ncull disable\n"
		"{\nmap " FL_ATLAS "\nblendfunc gl_one gl_one_minus_src_alpha\nrgbgen vertex\nalphagen vertex\nnodepth\n}\n"
		"polygonoffset\nsurfaceparm noshadows\nsurfaceparm nodlight\n}\n");
};

// Why this client cannot draw the sheet, or "" when it can.  The atlas is
// looked for the way cl_banner.qc looks for a sound: whichpack answers "" for a
// file inside a mounted game's .vpk, found or not (measured on this atlas).
string() Emit_FlameWhy =
{
	local float h, n;

	if (!cvar("vbsp_emit_flame"))
		return "vbsp_emit_flame is 0";
	if (!checkextension("FTE_PART_TEXANIM"))
		return "this engine has no stepped particle sheets (Patch 531)";
	if (!Milk_Supported())
		return "the renderer is not OpenGL";
	// The extension only says the scripted system was compiled in.
	if (cvar_string("r_particlesystem") != "script")
		return "r_particlesystem is not script";
	n = 0;
	h = search_begin(FL_ATLAS, TRUE, TRUE);
	if (h >= 0)
	{
		n = search_getsize(h);
		search_end(h);
	}
	if (n <= 0)
		return "no mounted game carries the fire atlas (Half-Life 2 or Counter-Strike: Source)";
	return "";
};

// Why a sheet fire's smoke is not drawn, or "".  Both sheets or neither: one
// answer for the whole map is what emit_list can say.
string() Emit_SmokeWhy =
{
	local float h, n;

	if (!cvar("vbsp_emit_firesmoke"))
		return "vbsp_emit_firesmoke is 0";
	n = 0;
	h = search_begin(FL_SMOKE1, TRUE, TRUE);
	if (h >= 0)
	{
		n = search_getsize(h);
		search_end(h);
	}
	h = search_begin(FL_VISTA, TRUE, TRUE);
	if (h >= 0)
	{
		n = n * search_getsize(h);
		search_end(h);
	}
	else
		n = 0;
	if (n <= 0)
		return "no mounted game carries the two smoke sheets";
	return "";
};

// Define size class cls's effects.  Slots 0-5 are the system's three sequences
// each way round, 6-11 the _b child's, 12 the embers.  env_fire_tiny's system
// draws sequence 3 alone, so its six slots share two effects.  13 and 14 are
// the smoke (vistasmokev1's two loops, or smoke1 twice), 15 and 16
// env_fire_large_smoke_b's.
void(float cls) Emit_FlameDefine =
{
	local float s, seq, layer;
	local string nm;

	if (!em_flfx)
		em_flfx = memalloc(sizeof(float) * 4 * FL_SLOTS);
	// Only for a class with a fire that smokes: surf_anubis has none.
	if (em_smwant & pow(2, cls))
	{
		for (layer = 0; layer < 2; layer = layer + 1)
		{
			if (layer && cls != 3)
				break;
			Emit_SmokeShader(cls, layer);
			for (seq = 0; seq < 2; seq = seq + 1)
			{
				nm = sprintf("ftesurf_fl%gs%g%g", cls, layer, (cls < 2) ? 0 : seq);
				if (cls >= 2 || !seq)
					localcmd(Emit_SmokeBlock(cls, layer, seq, nm));
				em_flfx[cls * FL_SLOTS + 13 + layer * 2 + seq] = particleeffectnum(nm);
			}
		}
	}
	for (s = 0; s < 12; s = s + 1)
	{
		layer = (s >= 6);
		seq = floor((s - layer * 6) / 2);
		if (!layer)
			seq = (cls == 0) ? 3 : seq + 3;
		nm = sprintf("ftesurf_fl%g%s%g%s", cls, layer ? "b" : "a", seq, (s & 1) ? "f" : "");
		if (cls || layer || s < 2)
			localcmd(Emit_FlameBlock(cls, layer, seq, s & 1, nm));
		em_flfx[cls * FL_SLOTS + s] = particleeffectnum(nm);
	}
	nm = sprintf("ftesurf_fl%ge", cls);
	localcmd(Emit_EmberBlock(cls, nm));
	em_flfx[cls * FL_SLOTS + 12] = particleeffectnum(nm);
	dprint(sprintf("emit: flame class %g defined\n", cls));
};

/*
  ONE CLASS A FRAME, from Emit_Frame.  A class is 14-16 KB of text and the
  command buffer drops, whole and with one console line, whatever does not fit
  under cmd_maxbuffersize (65536; cmd.c, Cbuf_AddText).  surf_classics2 and
  surf_road_to_hell use all four classes, 61 KB: sent in one go at map load it
  fitted (measured, 52 of 52 effects), with 4 KB to spare and nothing else of
  this file's in the buffer.  A fire whose class is not defined yet emits into
  nothing for those few frames, which is harmless.

  The shader goes first, and only here: a map with no env_fire never asks for
  the atlas.  TRUE when it defined something -- the caller then leaves the
  repair's probe alone for a second, because an effect defined this frame does
  not answer particleeffectquery until the engine has drawn one.
*/
float() Emit_FlameStep =
{
	local float cls, bit;

	if (em_flwant == em_flmask)
		return FALSE;
	for (cls = 0; cls < 4; cls = cls + 1)
	{
		bit = pow(2, cls);
		if (em_flwant & bit)
		if (!(em_flmask & bit))
		{
			if (!em_flmask)
				Emit_FlameShader();
			Emit_FlameDefine(cls);
			em_flmask = em_flmask | bit;
			return TRUE;
		}
	}
	return FALSE;
};

// A renderer restart or an unload took the effects: forget them, and
// Emit_FlameStep puts them back.  TRUE when it forgot something.
//
// Asked of the flame's OWN effect, not of ftesurf_dustmote_0: a client with no
// particles/ftesurf.cfg fails that probe every second for ever, and a repair
// hung on it defined 26 blocks again every second (measured: 39 times in one
// run of the arm), each time emptying them of live flames.
float() Emit_FlameRepair =
{
	local float cls;

	if (!em_flmask)
		return FALSE;
	for (cls = 0; cls < 4; cls = cls + 1)
		if (em_flmask & pow(2, cls))
			break;
	if (particleeffectquery(em_flfx[cls * FL_SLOTS], 0) != "")
		return FALSE;
	em_flmask = 0;
	return TRUE;
};

// The effect for the next particle of a sheet fire of size class cls, with or
// without its smoke.
float(float cls, float smoke) Emit_FlameSlot =
{
	local vector v, w;
	local float r, s;

	v = Emit_FlameRates(cls);
	w = smoke ? Emit_SmokeRates(cls) : '0 0 0';
	r = random() * (v_x + v_y + v_z + w_x + w_y);
	if (r < v_x)
		s = floor(random() * 5.999);
	else if (r < v_x + v_y)
		s = 6 + floor(random() * 5.999);
	else if (r < v_x + v_y + v_z)
		s = 12;
	else if (r < v_x + v_y + v_z + w_x)
		s = 13 + floor(random() * 1.999);
	else
		s = 15 + floor(random() * 1.999);
	return em_flfx[cls * FL_SLOTS + s];
};

/*
===========================================================================
  func_dustmotes the way Source draws it (Patch 648).

  c_func_dust.cpp is the whole of it.  A mote is a square of particle/sparkles
  whose half-side is rand(SizeMin, SizeMax) / 10000 of its DEPTH (:73, :234),
  so it is the same few pixels at any distance: 1.4 to 2.9 across at 1080p for
  the usual 10 and 20.  It is the entity's Color at Alpha, times a sine through
  its life (:58-59), times a fall to nothing at DistMax (:68).  It lives
  rand(LifetimeMin, LifetimeMax) seconds (:231) and leaves at
  RandomVector(-SpeedMax, SpeedMax) less FallSpeed down (:227-228).

  The ftesurf_dustmote_N blocks draw one median mote for the whole library, in
  six colours, several units wide.  Every number above is the ENTITY'S, and
  pointparticles carries none of them, so:

  EACH LOOK ON THE MAP IS ITS OWN r_part BLOCK, written at map load (the library's
  worst map has 27), and what differs per particle rides the colour channels
  to ONE shader that draws the sprite itself:
      red        the mote's size as a fraction of its depth
      green      its life, seconds
      blue       the entity's Color, r + 256 g + 65536 b
      alpha      its age, seconds (alpha 0, alphadelta 1)
      texcoord   whole part of s: DistMax; of t: Alpha, + 256 when Frozen
  The engine's quad only has to contain the sprite.

  "CORRECT AT ANY SIZE" IS THE SHADER, NOT A TEXTURE.  A two-pixel sprite cut
  from a 32-pixel texture is whatever four texels the pixel centres land on, and
  twinkles as it drifts.  particle/sparkles is a plain shape -- solid out to a
  quarter of the half-side, falling in a straight line to nothing at 1.17, cut
  off square (measured off the .vtf) -- so it is computed per pixel from four
  taps, and a mote thinner than the grid can hold (0.6 px) is held at that and
  dimmed by the area it lost.

  THE VELOCITY IS NOT SOURCE'S CURVE, IT IS ITS DISPLACEMENT.  Source pulls x
  and y towards the wind at 50 u/s^2 (:108-126, and there is no wind here), so a
  13 u/s mote stops sideways inside 0.26 s and then only rises or sinks.  With a
  life over 3.6 s its alpha is still under 5% by then; at surf_dune's 1 to 3 s
  it is 16 to 53%, and Source's early dash is not drawn.  The engine has no such
  pull, so each axis gets the constant speed that covers the same ground in the
  mean life.

  NOT DRAWN: env_wind, and the brush's own shape (a point is taken in its box).
  func_dustcloud is not touched: Source never scales it with depth.
===========================================================================
*/
#define DM_MAX         48
#define DM_FROZEN_LIFE 12       // Source's Frozen motes never die; these are replaced
#define DM_POOL        2048     // MAX_TOTAL_PARTICLES, particle_iterators.h:20: every
                                // old-style particle in the world shares it, and a
                                // spawn into a full pool is dropped (particlemgr.cpp:1150)
#define DM_REACH       2        // a volume emits to this many DistMax: Source fades a
                                // mote by its view DEPTH (:63-68), and at the corner of
                                // a 16:9 screen at fov 90 that is 1.83 times nearer than
                                // the mote is

string dm_look[DM_MAX];         // "r g b alpha smin smax lmin lmax dist frozen", strzoned
float *dm_fx;                   // [DM_MAX] handles
float  dm_n;
float  dm_over;                 // emitters whose look found the table full
float  dm_alive;                // last frame: motes the volumes in range would keep alive
float  dm_thr;                  // and the scale that holds them to DM_POOL
float  dm_fresh;                // Emit_MoteLook made a look in this call
string dm_why;                  // "" = Source's motes; else why the orbs draw
float *em_life;                 // [EM_MAX] a Source mote's mean life; 0 for anything else

/*
  Two things about the blend.  It is ONE / ONE_MINUS_SRC_ALPHA with both factors
  computed, because Source blends in linear light and this framebuffer does not
  (see Emit_FlameShader).  What linear light gives is a curve over the wall's
  brightness and this blend is a straight line, so it is made exact at two
  walls: a 0.25 grey, per channel, and white, for a grey of the mote's
  brightness -- so a pale mote can never darken a bright wall.  The first cut
  was exact on black instead, and a white mote at alpha 0.087 measured 0.108 too
  bright on a 0.37 wall; this is 0.023 over there and 0.10 under on a 0.04 one
  (the arm's row W).  A black mote is exact on any wall, which is what the rest
  of the ruler uses.

  `sort additive`, not the bucket a blendalpha particle gets by default: the
  engine draws that one (unlitdecal) twice a frame, and a mote meant to cover
  0.85 measured 0.975.  BACKLOG, "blended particles are drawn twice".
*/
void() Emit_MoteShader =
{
	shaderforname("ftesurf_mote",
		"{\nglslprogram\n{\n"
		"!!ver 110\n"
		"varying vec2 q;\n"         // across the engine's quad, -1..1, in its own frame
		"varying vec3 ev;\n"        // eye space
		"varying vec3 mote;\n"      // size / depth, life, age
		"varying vec4 look;\n"      // Color and Alpha
		"varying vec2 lim;\n"       // DistMax, Frozen
		"#ifdef VERTEX_SHADER\n"
		"attribute vec2 v_texcoord;\n"
		"attribute vec4 v_colour;\n"
		"uniform mat4 m_modelview;\n"
		"void main()\n{\n"
		// Unpacked HERE: an integer this size does not survive being interpolated.
		" vec2 k = floor(v_texcoord * 0.5);\n"
		" q = (v_texcoord - 2.0 * k) * 2.0 - 1.0;\n"
		" float fz = floor(k.y / 256.0);\n"
		" lim = vec2(k.x, fz);\n"
		" float cb = floor(v_colour.b / 65536.0);\n"
		" float cg = floor((v_colour.b - cb * 65536.0) / 256.0);\n"
		" look = vec4(v_colour.b - cb * 65536.0 - cg * 256.0, cg, cb, k.y - fz * 256.0) / 255.0;\n"
		" mote = v_colour.rga;\n"
		" ev = (m_modelview * vec4(v_position, 1.0)).xyz;\n"
		" gl_Position = ftetransform();\n"
		"}\n#endif\n"
		"#ifdef FRAGMENT_SHADER\n"
		// particle/sparkles at t pixels from the centre of a mote of half-side h.
		"float tap(vec2 t, float h)\n{\n"
		" t = abs(t);\n"
		" return step(max(t.x, t.y), h) * clamp((1.17 - length(t) / h) / 0.92, 0.0, 1.0);\n"
		"}\n"
		"void main()\n{\n"
		" float depth = -ev.z;\n"
		" float f = mote.z / mote.y;\n"
		" if (f >= 1.0 || depth >= lim.x || depth <= 0.0)\n"
		"  discard;\n"
		// c_func_dust.cpp:58-59, or a Frozen mote's constant, eased at both ends; :68
		" float a = look.a * mix(0.5 - 0.5 * cos(6.2831853 * f), clamp(min(mote.z, mote.y - mote.z) * 2.0, 0.0, 1.0), lim.y);\n"
		" a *= 1.0 - depth / lim.x;\n"
		// Pixels: world units and quad units per pixel, from the hardware's own slopes.
		" float wpp = length(vec2(dFdx(ev.x), dFdy(ev.x)));\n"
		" float qpp = length(vec2(dFdx(q.x), dFdy(q.x)));\n"
		" float h = mote.x * depth / wpp;\n"
		" float he = max(h, 0.6);\n"
		" a *= (h * h) / (he * he);\n"
		// The quad is a diamond on screen (the block's `rotation 0`; left alone the
		// engine turns each particle at random); turn its frame square to the pixels.
		" vec2 d = q / qpp;\n"
		" vec2 p = vec2(d.x - d.y, d.x + d.y) * 0.7071;\n"
		" a *= 0.25 * (tap(p + vec2(0.125, 0.375), he) + tap(p + vec2(-0.375, 0.125), he)\n"
		"  + tap(p + vec2(-0.125, -0.375), he) + tap(p + vec2(0.375, -0.125), he));\n"
		// 0.0474 is 0.25 ^ 2.2: the darker of the two walls the line is exact on.
		" vec3 c = pow(look.rgb, vec3(2.2)) * a;\n"
		" float ml = dot(c, vec3(0.3, 0.59, 0.11));\n"
		" float g = (1.0 - a) * 0.0474;\n"
		" float k = (pow(ml + 1.0 - a, 0.4545) - pow(ml + g, 0.4545)) / 0.75;\n"
		" gl_FragColor = vec4(max(pow(c + g, vec3(0.4545)) - 0.25 * k, 0.0), 1.0 - k);\n"
		"}\n#endif\n"
		"}\nsort additive\ncull disable\n"
		"{\nmap $whiteimage\nblendfunc gl_one gl_one_minus_src_alpha\nrgbgen vertex\nalphagen vertex\nnodepth\n}\n"
		"polygonoffset\nsurfaceparm noshadows\nsurfaceparm nodlight\n}\n");
};

// Why this client draws the orbs instead, or "".
string() Emit_MoteWhy =
{
	if (!cvar("vbsp_emit_motes"))
		return "vbsp_emit_motes is 0";
	if (!Milk_Supported())
		return "the renderer is not OpenGL";
	if (cvar_string("r_particlesystem") != "script")
		return "r_particlesystem is not script";
	return "";
};

/*
  Write look i's block from dm_look[i].

  The quad: its half-width across the flats is 1.06 * (0.25 + 0.001 * depth *
  scale) at scalefactor 0 (particles/ftesurf.cfg, UNITS).  The sprite's square
  sits turned 45 degrees inside it, so it needs 1.414 of the sprite's half-side
  plus a pixel of edge: scale 1333 * (SizeMax / 10000 + 0.0015), and no less
  than 4.7, which is one pixel at a focal length of 300.

  `die` is LifetimeMax for every particle: the shader ends a mote at its own
  life (green) and the engine carries it, undrawn, to the longest.  So
  r_partinfo counts rate * LifetimeMax where Source has rate * the mean alive.
  (`die min max` would not do it: the engine starts such a particle already
  aged, alpha and colour alike -- p_script.c:5233-5282.)
*/
void(float i) Emit_MoteDefine =
{
	local float smin, smax, lmin, lmax, sc, k;
	local string s, nm;

	tokenize(dm_look[i]);
	smin = stof(argv(4)) / 10000;
	smax = stof(argv(5)) / 10000;
	lmin = stof(argv(6));
	lmax = stof(argv(7));
	sc = 1333 * (max(smin, smax) + 0.0015);
	if (sc < 4.7)
		sc = 4.7;
	k = stof(argv(3)) + stof(argv(9)) * 256;
	nm = sprintf("ftesurf_dm%g", i);

	// ftos, not %g: these are whole numbers past six digits.
	s = sprintf("r_part %s\n{\ntexture ftesurf_mote\ntype normal\nblend blendalpha\nscalefactor 0\nscale %g\nrotation 0\nrgbf %g %g %s\nrgbrandf %g %g 0\n",
	            nm, sc, smin, lmin,
	            ftos(stof(argv(0)) + stof(argv(1)) * 256 + stof(argv(2)) * 65536),
	            smax - smin, lmax - lmin);
	s = strcat(s, sprintf("alpha 0\nalphadelta 1\ndie %g\ncount 1\nspawnmode box\nspawnorg 0\nveladd %g\n",
	            lmax, stof(argv(9)) ? 0 : 1));
	s = strcat(s, sprintf("tcoords %s %s %s %s\n}\n",
	            ftos(stof(argv(8)) * 2), ftos(k * 2), ftos(stof(argv(8)) * 2 + 1), ftos(k * 2 + 1)));
	localcmd(s);
	dm_fx[i] = particleeffectnum(nm);
};

// The look's index, made on first sight; -1 when the table is full.
float(string look) Emit_MoteLook =
{
	local float i;

	for (i = 0; i < dm_n; i = i + 1)
		if (!strcmp(dm_look[i], look))
			return i;
	if (dm_n >= DM_MAX)
		return -1;
	if (!dm_fx)
		dm_fx = memalloc(sizeof(float) * DM_MAX);
	if (!dm_n)
		Emit_MoteShader();
	dm_look[dm_n] = strzone(look);
	dm_fresh = TRUE;
	Emit_MoteDefine(dm_n);
	dprint(sprintf("emit: mote look %g = %s\n", dm_n, look));
	dm_n = dm_n + 1;
	return dm_n - 1;
};

void() Emit_MoteFree =
{
	local float i;

	for (i = 0; i < dm_n; i = i + 1)
		strunzone(dm_look[i]);
	dm_n = 0;
	dm_over = 0;
};

// As Emit_FlameRepair: asked of look 0's own effect.
float() Emit_MoteRepair =
{
	local float i;

	if (!dm_n)
		return FALSE;
	if (particleeffectquery(dm_fx[0], 0) != "")
		return FALSE;
	Emit_MoteShader();
	for (i = 0; i < dm_n; i = i + 1)
		Emit_MoteDefine(i);
	return TRUE;
};

void() Emit_AllocLife =
{
	if (!em_life)
		em_life = memalloc(sizeof(float) * EM_MAX);
};

// One axis of a mote's sideways speed: the constant speed that ends where
// Source's does, which loses 50 u/s every second (see the section's note).
float(float v0, float life) Emit_MoteDrift =
{
	local float a;

	a = fabs(v0);
	if (a < 50 * life)
		a = a * a / (100 * life);
	else
		a = a - 25 * life;
	return (v0 < 0) ? -a : a;
};

/*
  Taken ONCE, at init, and never again -- including across map changes.

  particleeffectnum returns a stable handle even when the lookup fails, because
  the guard at pr_csqc.c:3859 is commented out: it allocates a slot, remembers
  the NAME, and hands back a negative index.  P_LoadParticleSet queues the file
  through Cbuf_AddText (p_script.c:3748-3755), so on the frame we ask, the
  effect does not exist yet.  When the buffer drains and the r_part blocks
  parse, r_plooksdirty is set, and the per-frame particle draw calls
  CL_RegisterParticles (p_script.c:7005-7038), which re-resolves every stored
  handle by name.  Emitting through an unresolved handle returns early and is a
  safe no-op, so the only cost of being early is a frame or two of nothing.

  Doing this at init rather than per map is what stops the FIRST map being
  particle-free while the command buffer catches up.
*/
void() Emit_Precache =
{
	local float i;
	i = 0;
	while (i < EM_FX_N)
	{
		em_fx[i] = particleeffectnum(Emit_FxName(i));
		i = i + 1;
	}
};

void() Emit_RegisterCvars =
{
	registercvar("vbsp_emit",         "1", CVAR_ARCHIVE);
	registercvar("vbsp_emit_dust",    "1", CVAR_ARCHIVE);
	// func_dustmotes as Source draws them (Emit_MoteWhy); 0 keeps the
	// ftesurf_dustmote orbs.  Read at map load.
	registercvar("vbsp_emit_motes",   "1", CVAR_ARCHIVE);
	registercvar("vbsp_emit_embers",  "1", CVAR_ARCHIVE);
	registercvar("vbsp_emit_bubbles", "1", CVAR_ARCHIVE);
	registercvar("vbsp_emit_fire",    "1", CVAR_ARCHIVE);
	// env_fire from Source's own flame sheet where the client can draw it
	// (Emit_FlameWhy); 0 keeps the ftesurf_fire orbs.  Read at map load.
	registercvar("vbsp_emit_flame",   "1", CVAR_ARCHIVE);
	// The smoke Source puts over a fire that is not Smokeless.  Read at map load.
	registercvar("vbsp_emit_firesmoke", "1", CVAR_ARCHIVE);
	registercvar("vbsp_emit_spark",   "1", CVAR_ARCHIVE);
	// Off by default: a churning approximation of a static haze, on 45 maps.
	registercvar("vbsp_emit_smoke",   "0", CVAR_ARCHIVE);
	// ON by default, unlike its similarly-named neighbour: env_smokestack is
	// 2443 real jets across 52 maps and is most maps' only torch flame.
	registercvar("vbsp_emit_stack",   "1", CVAR_ARCHIVE);
	// info_particle_system: the map's OWN .pcf, baked to particles/<map>.cfg by
	// tools/pcf.py.  On by default -- it is the rain on surf_tensor2, and 130
	// maps in the library carry one.  A map with no bake draws nothing and says
	// so in emit_list.  Two bakes ship as of build 53: surf_tensor2 (rain and
	// portals) and surf_boreas (data/mapparticles.txt carries 13 systems plus
	// 7 child links for it), so surf_boreas's snow -- tendies_snow01, 16
	// flakes/s falling at 384 -- IS drawn through this path, on top of the
	// map's one func_dustmotes.  Before the boreas bake landed this comment
	// said tensor2 was the only one, and before that it claimed the opposite.
	registercvar("vbsp_emit_psys",    "1", CVAR_ARCHIVE);

	registercvar("vbsp_emit_dist",    "1", 0);
	registercvar("vbsp_emit_budget",  "2000", 0);
	// The per-emitter SpawnRate ceiling Emit_Add applies at LOAD time.  200 is
	// EM_RATE_MAX -- build 49's behaviour exactly.  It exists because the
	// clamp is one of the two measured reasons surf_boreas's snow was thinner
	// than Source's (SpawnRate 333, so 60% of Source's live count at 200; the
	// other reason was that its tendies_snow01 had no bake -- the boreas bake
	// ships as of build 53, and its psys line is 16/s, nowhere near this
	// clamp).  Read once per map load, so a change needs a map change.  0 or
	// less means EM_RATE_MAX.
	registercvar("vbsp_emit_ratemax", "200", 0);
	registercvar("vbsp_emit_lights",  "0", 0);
	// The self-healing reload in Emit_Frame.  0 is build 51b exactly: one exec
	// at map load and no repair, which is how you make the unload REPRODUCIBLE
	// instead of papered over -- cfg/test/b51e.cfg needs it off to timestamp
	// the kill.  Bisection cvar, not archived: nobody should keep it off.
	registercvar("vbsp_emit_heal",    "1", 0);
	// Child systems of a baked .pcf parent (build 53).  0 is build 52 exactly:
	// the parent alone, and the default, because it is not a pure correctness
	// fix -- surf_tensor2 already runs at throttle 0.456 (logs/t2rain.log,
	// demand 4390/sec) and its 12 water_splash02 children add 480/sec to every
	// emitter's cut.  On surf_boreas the end-zone glow and laser ARE the
	// children, so flip this once cfg/test/psboreas.cfg arms C/D have shown
	// them.  Read once per map load in Emit_LoadForMap; not archived.
	registercvar("vbsp_emit_psys_children", "0", 0);

	registercommand("emit_list");
	registercommand("emit_test");
	registercommand("emit_mote");

	Emit_Precache();
};

/*
===========================================================================
  Parsing
===========================================================================
*/

vector(string s) Emit_ParseVec =
{
	local float n;
	n = tokenize(s);
	if (n < 3)
		return '0 0 0';
	return [stof(argv(0)), stof(argv(1)), stof(argv(2))];
};

// "255 128 0" and the odd "255 128 0 200"; the fourth component is ignored in
// Source and ignored here, exactly as Sprite_ParseColor does.
vector(string s) Emit_ParseColor =
{
	local float n;
	if (s == "")
		return '1 1 1';
	n = tokenize(s);
	if (n < 3)
		return '1 1 1';
	return [stof(argv(0)), stof(argv(1)), stof(argv(2))] * (1 / 255);
};

/*
  Nearest of the six baked colours, by direction rather than by distance.

  Direction, because the effect's own `alpha` already carries brightness: a
  dim grey and a bright white are the same bucket and should be, while orange
  and red are different buckets at the same brightness.  Normalising first is
  what makes "128 128 128" and "255 255 255" both land on white.
*/
float(vector col) Emit_Bucket =
{
	local vector c;
	local float  l, best, bestdot, d;

	l = vlen(col);
	if (l < 0.001)
		return 0;                       // black is not a colour anyone authored
	c = col * (1 / l);

	best = 0;
	bestdot = -2;

	d = c * normalize('1 1 1');         if (d > bestdot) { bestdot = d; best = 0; }
	d = c * normalize('1 0.78 0.5');    if (d > bestdot) { bestdot = d; best = 1; }
	d = c * normalize('1 0.5 0.15');    if (d > bestdot) { bestdot = d; best = 2; }
	d = c * normalize('1 0.2 0.12');    if (d > bestdot) { bestdot = d; best = 3; }
	d = c * normalize('0.45 1 0.45');   if (d > bestdot) { bestdot = d; best = 4; }
	d = c * normalize('0.4 0.55 1');    if (d > bestdot) { bestdot = d; best = 5; }

	return best;
};

/*
  Add one emitter.

  `rate` is EMISSIONS per second and `burst` is particles per emission; for
  everything except env_spark burst is 1 and the two are the same number.  The
  split exists because a spark is a burst of Magnitude particles every MaxDelay
  seconds, and folding that into a rate would lose the burstiness that is the
  entire visual.
*/
// Returns the emitter's index, or -1 when it was not added.
float(vector bmin, vector bmax, vector vel, float jit, float rate, float burst,
     float dist, float eff, float kind) Emit_Add =
{
	local float i;
	local vector sz;

	if (em_n >= EM_MAX)
	{
		em_over = em_over + 1;
		return -1;
	}
	if (rate <= 0 || burst <= 0)
	{
		// Counted by kind, not dropped: this used to return in silence and
		// the entity surfaced in emit_list only as an "unaccounted" residual.
		em_norate[kind] = em_norate[kind] + 1;
		return -1;
	}

	if (rate > em_ratemax)
	{
		rate = em_ratemax;
		em_clamped = em_clamped + 1;
	}

	sz = bmax - bmin;
	if (sz_x < 0) sz_x = 0;
	if (sz_y < 0) sz_y = 0;
	if (sz_z < 0) sz_z = 0;

	i = em_n;
	em_mins[i]  = bmin;
	em_size[i]  = sz;
	em_mid[i]   = bmin + sz * 0.5;
	em_rad[i]   = vlen(sz) * 0.5;
	em_vel[i]   = vel;
	em_jit[i]   = jit;
	em_rate[i]  = rate;
	em_burst[i] = burst;
	em_dist[i]  = dist;
	em_eff[i]   = eff;
	em_kind[i]  = kind;
	em_acc[i]   = random();         // stagger, so 339 emitters do not all fire
	em_want[i]  = 0;                // on the same frame
	em_lit[i]   = 0;
	em_life[i]  = 0;
	em_ltacc[i] = random();
	em_drop[i]  = 0;

	em_n = em_n + 1;
	em_live[kind] = em_live[kind] + 1;
	return i;
};

/*
  WHERE A FIRE BURNS (Patch 656).  Unless spawnflags 16, "Don't drop", a fire
  that starts on is lit where a line 1024 down from its entity ends
  (fire.cpp:701-709, from Activate): 4,309 of the library's fires, on 85 maps,
  hang above their bowl or floor.

  THE LINE MUST MEET WHAT SOURCE'S MEETS, which is the world, its static props
  and the brush entities that are solid when the map starts.  This VM's world
  has the first two.  cl_sprites.qc's occluder copies are the wrong set twice
  over -- absent at vbsp_glare_brush 0, and at its default they include what is
  drawn and not solid (func_illusionary; surf_delight's 349 fires stopped on
  those) -- so they are stood down for the pass and this file stands up its
  own: Sprite_OccluderTier's tier 1 with func_brush's Solidity read the same
  way.  surf_lost2's 178 fires land on func_brush pedestals 24 units under them.

  Source's line ends 1024 below when it meets nothing.  Such a fire is left
  where it is and counted, as is one whose entity is inside something solid.
  Not stood up: prop_dynamic, and a brush as it is after the map has moved it.
*/
void() Emit_DropFires =
{
	local entity e, nxt;
	local string tok, key, cn, model;
	local vector org;
	local float i, k, n, solidity, hassolidity, startdisabled;

	if (!em_fldropwant)
		return;

	// .solid alone is not seen until the entity is linked again.
	for (e = findfloat(world, spr_occluder, TRUE); e; e = findfloat(e, spr_occluder, TRUE))
	{
		e.solid = SOLID_NOT;
		setorigin(e, e.origin);
	}

	n = 0;
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = model = "";
		org = '0 0 0';
		solidity = startdisabled = 0;
		hassolidity = FALSE;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if      (key == "classname") cn = tok;
			else if (key == "model")     model = tok;
			else if (key == "origin")    org = Sprite_ParseVec(tok);
			else if (key == "solidity"      || key == "Solidity")
			{
				solidity = stof(tok);
				hassolidity = TRUE;
			}
			else if (key == "startdisabled" || key == "StartDisabled")
				startdisabled = stof(tok);
		}
		if (substring(model, 0, 1) != "*")
			continue;
		if (Sprite_OccluderTier(cn) != 1)
			continue;
		if (cn == "func_brush")
		{
			if ((!hassolidity || solidity == 0) && startdisabled)
				continue;
			if (hassolidity && solidity == 1)
				continue;
		}
		if (n >= FL_DROPSOLIDS)
		{
			em_fldropover = em_fldropover + 1;
			continue;
		}
		// Solid before setmodel, which is what links it (Sprite_AddOccluder).
		e = spawn();
		e.em_dropsolid = TRUE;
		e.solid = SOLID_BSP;
		e.movetype = MOVETYPE_NONE;
		setmodel(e, model);
		setorigin(e, org);
		e.drawmask = 0;
		n = n + 1;
	}

	for (i = 0; i < em_n; i = i + 1)
	{
		if (!em_drop[i])
			continue;
		org = em_mid[i];
		traceline(org, org - '0 0 1024', TRUE, world);
		if (trace_startsolid)
			em_flinside = em_flinside + 1;
		else if (trace_fraction >= 1)
			em_flnofloor = em_flnofloor + 1;
		else
		{
			k = org_z - trace_endpos_z;
			if (k > 256)
				dprint(sprintf("emit: env_fire at %v is lit %g below it\n", org, k));
			em_fldrop = em_fldrop + 1;
			em_fldropsum = em_fldropsum + k;
			if (k > em_fldropmax)
				em_fldropmax = k;
			org = em_mins[i];
			org_z = org_z - k;
			em_mins[i] = org;
			org = em_mid[i];
			org_z = org_z - k;
			em_mid[i] = org;
		}
	}

	// The next one is found before this one goes: Sprite_FreeOccluders.
	e = findfloat(world, em_dropsolid, TRUE);
	while (e)
	{
		nxt = findfloat(e, em_dropsolid, TRUE);
		remove(e);
		e = nxt;
	}
	for (e = findfloat(world, spr_occluder, TRUE); e; e = findfloat(e, spr_occluder, TRUE))
	{
		e.solid = SOLID_BSP;
		setorigin(e, e.origin);
	}
	dprint(sprintf("emit: %g brush entities stood up for %g fires' drop\n", n, em_fldropwant));
};

/*
  The walk.

  A FOURTH independent pass over the same entity lump -- cl_decals.qc,
  cl_sprites.qc and cl_fog.qc are the other three, and none of the four reads
  another.  One probe entity is reused for every brush volume and removed at
  the end, exactly as Zone_LoadFromBsp does (cl_zones.qc:241-269).

  KEYS ARE COMPARED IN LOWERCASE, which is a departure from cl_sprites.qc:487
  and deliberate.  That file lists both spellings of each key, which is fine for
  three; this one reads twenty-odd, and the library writes CamelCase and
  lowercase for nearly all of them -- SpawnRate/spawnrate, Color/color,
  Frozen/frozen, Density/density -- with 2-8% of instances on the lowercase
  form.  One strtolower per key is cheaper than forty comparisons and cannot be
  half-forgotten for one key the way a paired list can.
*/
void() Emit_LoadForMap =
{
	local string tok, key, cn, mdl, scol, mname;
	local entity probe;
	// NOT `mins`/`maxs`: a local of that name shadows the entity FIELD of the
	// same name, and `probe.mins` then fails to compile as "mins is not a
	// field".  cl_zones.qc never hits this because it passes probe.mins
	// straight into Zone_AddBox without a local in between.
	local vector org, ang, bmin, bmax, col, vel;
	/*
	  Only the keys that reach a decision are read.  ParticleDrawWidth is set
	  on essentially every instance and deliberately absent: it is baked into
	  the effect blocks and cannot be passed through pointparticles.  SizeMin,
	  SizeMax and Lifetime* were absent for the same reason until Patch 648,
	  which reads them for func_dustmotes (a block per look; see its section).
	  The header essay is where the full key inventory lives.
	*/
	local float  rate, alpha, dist, spd, frozen;
	local float  smin, smax, lmin, lmax, fall, look;
	local float  spawnflags, disabled, density, freq, current;
	local float  firesize, maxdelay, magnitude, traillen, mspeed;
	local float  ssize, esize, jetlen, spread, initst;
	local float  i, k, bucket, eff, kind, jit, burst;
	local string effname;
	local float  ps, j, pchild, opened, fcls;

	Emit_Alloc();
	Emit_AllocLife();

	// NOT written to vbsp_em_map here.  The latch is taken at the end of the
	// walk, and only if the entity lump actually opened -- see the note there.
	mname = serverkey("map");
	pchild = cvar("vbsp_emit_psys_children");

	em_ratemax = cvar("vbsp_emit_ratemax");
	if (em_ratemax <= 0)
		em_ratemax = EM_RATE_MAX;

	em_n = 0;
	em_any = 0;
	em_frozen = em_clamped = em_over = em_child = 0;
	em_flwant = em_flmask = 0;
	em_flwhy = Emit_FlameWhy();
	em_smwhy = Emit_SmokeWhy();
	em_smwant = em_flsmoke = em_flglow = 0;
	em_fldropwant = em_fldrop = em_fldropsum = em_fldropmax = em_flnofloor = em_flinside = em_fldropover = 0;
	Emit_MoteFree();
	dm_why = Emit_MoteWhy();
	i = 0;
	while (i < EK_N)
	{
		em_seen[i] = em_live[i] = em_off[i] = em_norate[i] = 0;
		i = i + 1;
	}

	if (mname == "")
	{
		Emit_PsysFree();
		vbsp_em_map = mname;    // "" == "" so Emit_Frame does not spin on it
		return;
	}

	/*
	  THE SHARED EFFECT SET, LOADED HERE AND NOT FROM default.cfg.  Build 51b.

	  cfg/default.cfg used to carry `exec particles/ftesurf.cfg` and it never
	  created a single effect, because a config exec'd at boot is handed to the
	  particle system before that system exists:

	      pe_script_enabled is a zero-initialised static (p_script.c:86) and the
	      ONLY assignment to true is inside PScript_InitParticles (p_script.c:3513).
	      P_ParticleEffect_f -- the r_part handler -- tests it at p_script.c:1141,
	      sets ptype = NULL, and at :1150-1170 counts braces to the end of the
	      block and returns.  No Con_Printf, no Con_DPrintf, no warning of any
	      kind.  r_part is registered unconditionally and the engine says why in
	      as many words at r_part.c:684: "always registered to suck up stray
	      r_part commands even when the scripted system is not active."
	      CL_ExecInitialConfigs queues `exec cfg/default.cfg` (cl_main.c:8097)
	      and drains the buffer ITSELF at :8127, and only its caller then reaches
	      Renderer_Start at cl_main.c:8236.

	  So all 35 blocks were parsed, swallowed and discarded in silence, every
	  pointparticles returned at p_script.c:4707 on typenum < 0, and the pool sat
	  at `0 particles, 65536 free` for three builds.

	  logs/t2final.log dates it to the second, in a run of that exact mechanism:
	      15:04:30  couldn't exec config.cfg   <- queued after default.cfg and
	                                              drained in the same pass, so
	                                              default.cfg is already finished
	      15:04:32  Setting windowed mode 1280*720 OpenGL   <- Renderer_Start
	  and the same file holds the control, 36 seconds later, from the line below:
	      15:05:06  execing particles/surf_tensor2.cfg
	      15:05:06  [vmt] watersource/particles/water_splash_02: ...
	  Same command, same session; the blocks parse and pull their textures in the
	  same tick.  Nothing named ftesurf_dot appears anywhere in that log.

	  THIS LINE ALONE IS NOT ENOUGH, AND THAT WAS MEASURED, NOT ASSUMED.  With
	  only this, b51b still reported "EFFECT DOES NOT EXIST".  Three runs pinned
	  down why:

	    b51c  the SAME file exec'd from the console at RESTRICT_LOCAL, mid-map,
	          gives `query ".ftesurf_dustmote_0"  effect exists` and 1811
	          particles.  So the file, the names and the engine are all fine.
	    b51d  r_exportalleffects with only this line having run dumps all 35
	          types with the right names and EMPTY BODIES -- which is what
	          PScript_Query writes for a type whose loaded flag is 0
	          (p_script.c:2372-2373).

	  Created, parsed, and then UNLOADED.  FOUND, by counting instead of
	  reading: engine Patch 272 puts a per-frame census of loaded types in the
	  log, and logs/b51e.log (the 16:29 pass, abridged by one server-side
	  line) shows the whole thing:
	      loaded types 0 -> 35 of 35, at frame            <- this exec
	      r_particledesc callback: "classic" -> "classic" (cls.state 3)
	      R_Particles_KillAllEffects: unloading 35 types
	      Sending stringcmd prespawn 1 0 0
	      loaded types 35 -> 0 of 35, at frame
	  (p_script.c line numbers in this file predate Patch 272, which inserted
	  about ninety lines of census and prints above R_ParticleDesc_Callback;
	  search by symbol.)
	  CL_RequestNextDownload forces the r_particledesc callback once the world
	  model is loaded so that per-map sets get picked up (cl_parse.c, just
	  before it sends prespawn), and that callback opens by unloading every
	  effect.  CSQC_WorldLoaded -- and so this line -- runs a few milliseconds
	  BEFORE it.  An unchanged value, so Cvar_SetCore never did this; the four
	  sites call Cvar_ForceCallback by the cvar's ALIAS, r_particlesdesc, and
	  no grep for r_particledesc matches that.  It also explains the psys
	  configs reading 0 particles on surf_tensor2: same exec point, same kill.

	  Patch 272 makes that kill spare explicitly-loaded effects (r_part_keepuser,
	  default 1; 0 is the old engine), so this line is sufficient on its own and
	  em_reload reads 0.  The net in Emit_Frame stays for what the engine still
	  unloads -- a vid_restart, r_part_keepuser 0, or an engine without the patch.

	  NOT latched to run once.  A vid_restart calls PScript_Shutdown
	  (p_script.c:3554-3610), which frees the whole part_type table; re-execing
	  per map load is what survives one.  Re-parsing an effect that already
	  exists is idempotent -- P_ResetToDefaults runs first, p_script.c:1225.

	  And it is quieter than the boot exec was: localcmd from CSQC runs at
	  RESTRICT_INSECURE, so P_SetModified returns early (p_script.c:693-694) and
	  f_modified_particles stays clear.  At RESTRICT_LOCAL it would have been set
	  on every launch, which the eventual leaderboard client would have had to
	  learn to ignore.

	  THE EXEC LINE ITSELF IS AT THE END OF THIS FUNCTION since build 53,
	  behind the opened guard, together with the psys bake's.  The cbuf drains
	  after this callback returns whichever line issues the localcmd, so
	  nothing about the ordering discussed above changes; what changes is that
	  a frame on which the entity lump could not be read no longer execs the
	  file, and so the per-frame retry that frame now triggers cannot exec it
	  once per frame.
	*/

	/*
	  And hold the net in Emit_Frame off until a frame has been drawn.  Its
	  probe reads cl.particle_csprecache[], which the engine re-resolves inside
	  its own draw (the r_plooksdirty block at the top of
	  PScript_DrawParticleTypes), and Emit_Frame runs BEFORE renderscene() --
	  so a check on the very first frame after this exec would read the slot
	  stale and re-exec for nothing.  Whether the engine's map-load pass
	  re-resolves it in time depends on whether this exec drains before that
	  pass, and b51b.log shows both orders on different loads.

	  NOT `em_reload_t = time + 1` here, which is what the first version did:
	  `time` inside CSQC_WorldLoaded is whatever the last frame or the init
	  left in it, the engine writes no time global for this callback, and a map
	  load takes longer than a second -- so that deadline could already have
	  passed on the first drawn frame and the check would have run stale after
	  all (the review of engine Patch 272 caught it).  A frame latch instead:
	  clear em_drawn, and the first Emit_Frame arms the one-second deadline
	  from its own fresh `time` and skips the check.  Then em_reload means what
	  it says: 0 on a patched engine.
	*/
	em_drawn = 0;

	// Before the walk: the entity loop looks each effect_name up in this.
	Emit_PsysLoad(mname);

	probe = spawn();
	opened = FALSE;

	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		opened = TRUE;

		cn = mdl = scol = effname = "";
		org = ang = '0 0 0';
		rate = dist = spd = frozen = 0;
		smin = smax = lmin = lmax = fall = 0;
		look = -1;
		alpha = 255;
		spawnflags = disabled = 0;
		density = freq = current = 0;
		firesize = maxdelay = magnitude = traillen = mspeed = 0;
		ssize = esize = jetlen = spread = 0;
		initst = 1;             // env_smokestack's default is ON; 2378 of 2443
		                        // write it explicitly and 10 write 0

		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);

			if      (key == "classname")     cn  = tok;
			else if (key == "model")         mdl = tok;
			else if (key == "origin")        org = Emit_ParseVec(tok);
			else if (key == "angles")        ang = Emit_ParseVec(tok);
			else if (key == "spawnflags")    spawnflags = stof(tok);
			else if (key == "startdisabled") disabled = stof(tok);

			// info_particle_system.  `start_active` is its own on/off key and
			// does NOT reuse StartDisabled -- 44 of 44 on tensor2 write the
			// former and none the latter, so folding them would read every
			// system as enabled by accident rather than by rule.
			else if (key == "effect_name")   effname = tok;
			else if (key == "start_active")  disabled = !stof(tok);

			else if (key == "spawnrate")     rate = stof(tok);
			else if (key == "alpha")         alpha = stof(tok);
			else if (key == "distmax")       dist = stof(tok);
			else if (key == "speedmax")      spd  = stof(tok);
			else if (key == "frozen")        frozen = stof(tok);
			else if (key == "sizemin")       smin = stof(tok);
			else if (key == "sizemax")       smax = stof(tok);
			else if (key == "lifetimemin")   lmin = stof(tok);
			else if (key == "lifetimemax")   lmax = stof(tok);
			else if (key == "fallspeed")     fall = stof(tok);

			else if (key == "color")         scol = tok;
			else if (key == "color1")        scol = tok;
			else if (key == "rendercolor")   scol = tok;

			else if (key == "speed")         spd = stof(tok);
			else if (key == "density")       density = stof(tok);
			else if (key == "frequency")     freq = stof(tok);
			else if (key == "current")       current = stof(tok);

			else if (key == "firesize")      firesize = stof(tok);
			else if (key == "maxdelay")      maxdelay = stof(tok);
			else if (key == "magnitude")     magnitude = stof(tok);
			else if (key == "traillength")   traillen = stof(tok);
			else if (key == "movementspeed") mspeed = stof(tok);

			/*
			  env_smokestack.  `rate` is shared with SpawnRate above and that is
			  correct rather than lucky -- both mean "particles per second" and no
			  class in this file carries both keys.  Everything else needs its own
			  local because the meanings genuinely differ: Speed here is the jet's
			  launch speed and already lands in `spd` via the shared "speed" case.
			*/
			else if (key == "rate")          rate = stof(tok);
			else if (key == "startsize")     ssize  = stof(tok);
			else if (key == "endsize")       esize  = stof(tok);
			else if (key == "jetlength")     jetlen = stof(tok);
			else if (key == "spreadspeed")   spread = stof(tok);
			else if (key == "initialstate")  initst = stof(tok);
		}

		if (cn == "")
			continue;

		// ---- which class, and is it wanted at all
		kind = -1;
		if      (cn == "func_dustmotes")   kind = EK_DUST;
		else if (cn == "func_dustcloud")   kind = EK_CLOUD;
		else if (cn == "env_embers")       kind = EK_EMBER;
		else if (cn == "env_bubbles")      kind = EK_BUBBLE;
		else if (cn == "env_fire")         kind = EK_FIRE;
		else if (cn == "env_spark")        kind = EK_SPARK;
		else if (cn == "func_smokevolume") kind = EK_SMOKE;
		else if (cn == "env_smokestack")   kind = EK_STACK;
		else if (cn == "info_particle_system") kind = EK_PSYS;
		if (kind < 0)
			continue;

		em_seen[kind] = em_seen[kind] + 1;
		em_any = em_any + 1;

		/*
		  The per-class cvars are NOT consulted here, deliberately.  Filtering
		  at load would mean vbsp_emit_fire only took effect on the next map
		  load, which is exactly the "row does nothing" complaint the gfx menu
		  marks map-latched rows with a `*` to avoid.  Emit_Frame tests them
		  instead, off em_kind, so every switch here is instant.
		*/
		// A Frozen volume's motes are made when it is, whatever StartDisabled
		// says (c_func_dust.cpp:167-173): one volume in the library.
		if (disabled)
		if (!(frozen && kind == EK_DUST && dm_why == ""))
		{
			em_off[kind] = em_off[kind] + 1;
			continue;
		}

		col = Emit_ParseColor(scol);
		bucket = Emit_Bucket(col);
		makevectors(ang);

		// ---- the brush classes: the volume IS the entity's submodel
		bmin = bmax = '0 0 0';
		if (kind != EK_FIRE && kind != EK_SPARK && kind != EK_STACK &&
		    kind != EK_PSYS)
		{
			if (mdl == "" || substring(mdl, 0, 1) != "*")
				continue;
			setmodel(probe, mdl);
			bmin = probe.mins;
			bmax = probe.maxs;
		}

		vel = '0 0 0';
		jit = 0;
		burst = 1;
		eff = 0;

		if (kind == EK_DUST || kind == EK_CLOUD)
		{
			if (alpha <= 0)
			{
				em_off[kind] = em_off[kind] + 1;
				continue;
			}
			if (dist <= 0)
				dist = (kind == EK_DUST) ? 2000 : 3000;

			/*
			  NO SpawnRate FALLBACK, AND THAT IS SOURCE'S BEHAVIOUR, NOT AN
			  OMISSION.  Entity memory is zeroed on allocation (baseentity.cpp
			  :3331, "All fields in the object are all initialized to 0"), so an
			  absent key leaves m_SpawnRate at 0.  C_Func_Dust::OnDataChanged
			  then calls m_Spawner.Init(0) (c_func_dust.cpp:176); TimedEvent::Init
			  makes the period 1/0 = inf (timedevent.h:32) and NextEvent fires
			  exactly once, because m_fNextEvent starts at 0, then never again
			  (timedevent.h:46-52).  ONE particle, ever.  The FGD's 40
			  (momentum.fgd:1965) is Hammer's editor default, and Hammer writes
			  it: all 4999 func_dustmotes and all 529 func_dustcloud in the
			  library carry the key and none is <= 0 (entity-lump census,
			  2026-09-08).  So a 0 falls through to Emit_Add, which counts it in
			  em_norate so emit_list names the skip instead of burying it in the
			  residual.  A 40 here would draw what Source does not.
			*/

			/*
			  BUILD 51: FROZEN IS NOW DRAWN, ALMOST STILL, RATHER THAN SKIPPED.

			  Build 49 skipped the 79 + 30 Frozen instances and counted them,
			  on the reasoning that "motionless" wants veladd 0 and therefore a
			  second effect for every colour bucket.  That reasoning was about
			  what EXACT would cost, and it silently chose invisible over
			  approximate -- which is the wrong way round for a visual feature.
			  Source draws a frozen mote; it just does not move it.

			  1 u/s is not 0 but it is indistinguishable from it: over the 3-5s
			  lifetime a particle drifts 3-5 units, inside a volume whose median
			  diagonal is 589 and which on surf_boreas is 2048x2048x832.  The
			  block's own `spawnvel 3 2` already adds more drift than this does.

			  NOT ZERO, deliberately: `dir` is normalised before use
			  (p_script.c:5230-5235), so a zero vector would be a division by
			  zero in the engine rather than a still particle in the game.

			  surf_boreas is why this changed.  Its snow reads as thin, and one
			  of the two reasons is its func_dustcloud (2048x2048x832,
			  SizeMin 100 SizeMax 200) carrying Frozen 1 and therefore never
			  being emitted at all.
			*/
			if (frozen)
			{
				em_frozen = em_frozen + 1;
				vel = '0 0 1';
				jit = 1;
			}
			else
			{
				jit = spd;
				if (jit <= 0)
					jit = 13;       // the library's own median SpawnRate pair
			}
			eff = ((kind == EK_DUST) ? FX_DUSTMOTE : FX_DUSTCLOUD) + bucket;

			/*
			  Source's own mote.  The keys are read as the CLIENT receives them:
			  func_dust.cpp sends SpawnRate and SpeedMax in 12 bits, DistMax in
			  16, the two lifetimes in 4 (:87-93) -- a LifetimeMax of 20 arrives
			  as 4 -- and they are integers before that (:107-113).  Alpha is a
			  byte (:166).  RemapVal takes the pair either way round (:231, :234).
			*/
			if (kind == EK_DUST)
			if (dm_why == "")
			{
				lmin = floor(lmin) & 15;
				lmax = floor(lmax) & 15;
				if (lmin > lmax)
				{
					k = lmin;
					lmin = lmax;
					lmax = k;
				}
				if (frozen)
					lmin = lmax = DM_FROZEN_LIFE;
				if (lmax <= 0)
				{
					// Dead the frame it is born: Source draws nothing either.
					em_off[kind] = em_off[kind] + 1;
					continue;
				}
				if (lmin < 0.1)
					lmin = 0.1;
				dist = floor(dist) & 65535;
				// Emit_ParseColor's 0..1, back to the bytes Source keeps.
				scol = sprintf("%g %g %g %g %g", rint(col_x * 255), rint(col_y * 255), rint(col_z * 255),
				               floor(alpha) & 255, smin);
				scol = strcat(scol, sprintf(" %g %g %g %g %g", smax, lmin, lmax, dist, frozen ? 1 : 0));
				look = Emit_MoteLook(scol);
				if (look < 0)
					dm_over = dm_over + 1;
			}
			if (look >= 0)
			{
				eff = look;
				dist = dist * DM_REACH;
				rate = floor(rate) & 4095;
				spd = floor(spd) & 4095;
				vel = [0, 0, -fall];
				jit = spd;
				if (frozen)
				{
					// SpawnRate motes, standing: that many alive, replaced as they go.
					rate = rate / DM_FROZEN_LIFE;
					vel = '0 0 1';
					jit = 0;
				}
			}
		}
		else if (kind == EK_EMBER)
		{
			// bit 1 is Start On, and only 56% set it -- so 44% are meant to be
			// off until triggered.  An ember fountain that should not be running
			// is a visible authoring error; a missing one is invisible.
			if (!(spawnflags & 1))
			{
				em_off[kind] = em_off[kind] + 1;
				continue;
			}
			if (spd <= 0) spd = 32;
			if (density <= 0) density = 80;
			rate = density * 0.15;
			dist = 3000;
			vel = v_forward * spd;
			jit = spd * 0.2;
			eff = FX_EMBER + bucket;
		}
		else if (kind == EK_BUBBLE)
		{
			// bit 1 is Start OFF here, not Start On.  Only 12% set it.
			if (spawnflags & 1)
			{
				em_off[kind] = em_off[kind] + 1;
				continue;
			}
			if (density <= 0) density = 6;
			if (freq <= 0) freq = 4;
			rate = density * freq * 0.25;
			dist = 2000;
			vel = '0 0 1' * 22 + v_forward * current;
			jit = 6;
			eff = FX_BUBBLE;
		}
		else if (kind == EK_SMOKE)
		{
			if (density <= 0) density = 0.6;
			rate = density * 3;
			dist = 3000;
			if (mspeed <= 0) mspeed = 10;
			vel = '0 0 1' * mspeed * 0.3;
			jit = mspeed * 0.5;
			eff = FX_SMOKE;
		}
		else if (kind == EK_FIRE)
		{
			/*
			  BUILD 51: THIS TESTED THE WRONG BIT.

			  It read bit 1 and called it "Start On".  Bit 1 is INFINITE
			  DURATION; Start On is bit 4.  The FGD is the authority
			  (momentum.fgd env_fire: 1 Infinite Duration, 2 Smokeless,
			  4 Start On, 8 Start Full, 16 Don't drop light, 32 No glow).

			  The two bits agree on 98.7% of the library, which is why this
			  survived build 49 and why the old comment's "98%" looked right --
			  it was the bit-1 count wearing bit 4's name.  Censused over all
			  13633 env_fire: bit 1 on 13490 (99.0%), bit 4 on 13380 (98.1%),
			  and they disagree on 246 instances -- 178 we were lighting that
			  Source leaves dark, and 68 we were skipping that Source burns.
			*/
			if (!(spawnflags & 4))
			{
				em_off[kind] = em_off[kind] + 1;
				continue;
			}
			// Source's choice of system, from the size as written.
			fcls = floor(firesize / 36);
			if (fcls < 0) fcls = 0;
			if (fcls > 3) fcls = 3;
			if (firesize <= 0) firesize = 64;
			if (firesize > 512) firesize = 512;     // 2782 occurs; it is not a flame

			/*
			  firesize is not baked into the effect -- there is one `fire` block
			  for the whole library.  Instead the spawn box widens with the fire
			  and the rise speed scales with it, so a 16-unit candle and a
			  256-unit bonfire come out of the same three cfg lines.
			*/
			k = firesize * 0.22;
			bmin = org - [k, k, 0];
			bmax = org + [k, k, firesize * 0.1];
			rate = 8 + firesize * 0.12;
			/*
			  BUILD 51: 1800 -> 4000, AND 1800 WAS DRAWING NOTHING AT ALL.

			  Measured over all 65 info_player_start positions on surf_anubis,
			  counting env_fire within the cull:

			      cull 1800   median  0 in range (max 0)      demand      0/s
			      cull 2200   median  2                       demand     31/s
			      cull 3000   median  8                       demand    125/s
			      cull 3500   median 13                       demand    204/s
			      cull 4000   median 22 (max 24)              demand    345/s
			      cull 5000   median 55                       demand    862/s

			  MEDIAN ZERO, MAX ZERO.  Not one of surf_anubis' 161 braziers was
			  within the cull from ANY spawn on the map, so the class that build
			  49 shipped as working drew literally nothing there.  That is half
			  of "some of the flame fire effect doesn't spawn" -- the other half
			  was the torches being env_smokestack.

			  4000 rather than more, from the same census: the worst map in the
			  library for this class, surf_stonework4 (531 fires), only reaches
			  10 in range at 4000 for 157/s, and anubis' 22 cost 345/s -- both
			  far inside vbsp_emit_budget 2000.  5000+ starts to matter and buys
			  little, since beyond that a 64-unit flame is under a pixel.

			  No env_fire in the library carries a DistMax key, so there is no
			  per-entity number to honour here and this constant is the whole
			  policy.  Source itself culls these only by PVS.
			*/
			dist = 4000;
			vel = '0 0 1' * (firesize * 0.55);
			jit = firesize * 0.18;
			eff = FX_FIRE;
			if (em_flwhy == "")
			{
				// The sheet: every particle starts from the entity's origin and
				// the effect spreads it.  eff is the size class, as -1 - class.
				em_flwant = em_flwant | pow(2, fcls);
				bmin = bmax = org;
				col = Emit_FlameRates(fcls);
				rate = col_x + col_y + col_z;
				eff = -1 - fcls;
				// With its smoke, classes -5 to -8: spawnflags 2 is Smokeless.
				if (!(spawnflags & 2))
				if (em_smwhy == "")
				{
					col = Emit_SmokeRates(fcls);
					rate = rate + col_x + col_y;
					eff = eff - 4;
					em_flsmoke = em_flsmoke + 1;
					em_smwant = em_smwant | pow(2, fcls);
				}
				dist = FL_REACH;
			}
		}
		else if (kind == EK_SPARK)
		{
			// bit 64 is Start ON.  271 of 452 set it; the rest wait for a
			// trigger that this client can never hear about (see the essay in
			// Emit_Frame about there being no entity channel).
			if (!(spawnflags & 64))
			{
				em_off[kind] = em_off[kind] + 1;
				continue;
			}
			if (magnitude <= 0) magnitude = 1;
			if (traillen <= 0) traillen = 1;
			if (maxdelay <= 0) maxdelay = 3;

			bmin = bmax = org;
			rate = 1 / maxdelay;                    // bursts per second
			burst = 4 + magnitude * 3;
			dist = 1500;
			// TrailLength (1..3) stretches the streak in Source; here it can
			// only reach the streak through speed, since the particle's own
			// lifetime is baked into the effect.
			vel = v_forward * ((60 + magnitude * 45) * (0.6 + traillen * 0.4));
			jit = 40 + magnitude * 30;
			eff = FX_SPARK;
		}
		else if (kind == EK_STACK)
		{
			/*
			  env_smokestack.  A point jet -- see the FX_STACKJET essay.

			  InitialState, not spawnflags: momentum.fgd gives this class no
			  spawnflags block at all, and only 25 instances in the library even
			  write the key (all of them 0).  10 of 2443 set InitialState 0.
			*/
			if (!initst)
			{
				em_off[kind] = em_off[kind] + 1;
				continue;
			}

			if (rate   <= 0) rate   = 15;   // library median, x1871 of 2443
			if (spd    <= 0) spd    = 30;   // x1750
			if (spread <= 0) spread = 8;    // x1489
			if (ssize  <= 0) ssize  = 9;    // x1488
			if (jetlen <= 0) jetlen = 24;   // x1488

			/*
			  UP, not FORWARD, and this is an inference worth flagging rather
			  than burying.  1992 of 2443 instances carry `angles 0 0 0`, and
			  they are torches, chimneys and steam vents -- all of which must
			  rise.  makevectors('0 0 0') puts v_forward down +X, which would
			  lay every one of them on its side; v_up is '0 0 1', which is what
			  a smokestack with no angles obviously means.  The 75 instances at
			  `-90 0 0` then come out horizontal, which is what a pitched vent
			  should do.  If a map ever turns up with jets pointing the wrong
			  way, this is the line.
			*/
			bmin = bmax = org;
			vel  = v_up * spd;
			jit  = spread;
			/*
			  4000, for the reason recorded on env_fire's cull above and from the
			  same census.  On surf_anubis the NEAREST torch to the first spawn is
			  2839 units away, so a 2200 cull put zero of its 498 on screen from
			  that vantage; across all 65 spawns the median in range is 27 at
			  2200 against 60 at 4000, for 900 emissions/sec against a 2000
			  budget.  6000 would reach 134 and 2010/sec, which is the whole
			  budget for one class on one map.
			*/
			dist = 4000;

			/*
			  Which family: the sign of the size change.  A jet that narrows is
			  a flame or a steam plume; one that widens is smoke.  StartSize and
			  EndSize are baked into the block, so this is the only place the
			  distinction can be made.  Ties and unwritten keys go to JET, which
			  is both the majority (1488) and the one the user is missing.
			*/
			if (esize > ssize)
				eff = FX_STACKPUFF + bucket;
			else
				eff = FX_STACKJET + bucket;
		}

		/*
		  info_particle_system.  Everything about the LOOK, including the spawn
		  box, is already in the baked r_part block, so the entity contributes
		  only its origin -- bmin == bmax == org, and Emit_PointIn then returns
		  that origin exactly, which is the control point the .pcf's
		  "Position Within Box Random" is relative to.

		  eff carries the particleeffectnum HANDLE rather than an index into
		  em_fx, and the emit site branches on the kind to tell them apart.  A
		  handle for an effect whose cfg has not parsed yet is safe: asking for
		  "<map>.<name>" is what QUEUES particles/<map>.cfg in the first place
		  (p_script.c:674-675), the handle is re-resolved by name every frame by
		  CL_RegisterParticles, and emitting through an unresolved one returns
		  early. See the essay above Emit_FxName.

		  A map with no bake finds nothing and is skipped, counted as `off`, so
		  the report says "found N, drew 0" rather than staying silent -- the
		  distinction between "this map has no rain" and "we cannot draw its
		  rain" is the whole point of having the counter.
		*/
		if (kind == EK_PSYS)
		{
			ps = (effname == "") ? -1 : Emit_PsysFind(effname);
			if (ps < 0)
			{
				em_off[kind] = em_off[kind] + 1;
				continue;
			}
			// BUILD 53: the box centre moves the origin (a rain sheet 1000
			// above its entity on tensor2, a glow 456 below its on boreas),
			// the entity's angles rotate the velocity -- see Emit_PsysVel --
			// and the .pcf's isotropic random_speed rides em_jit.
			// makevectors(ang) ran above, before the class branches.
			bmin = bmax = org + ps_ofs[ps];
			vel  = Emit_PsysVel(ps);
			jit  = ps_jit[ps];
			burst = 1;
			rate = ps_rate[ps];
			dist = ps_dist[ps];
			// UNDERSCORE, NOT A DOT.  A dot would send this back through the
			// auto-load path Emit_PsysLoad exists to avoid; with no dot the
			// effect is found by plain name out of what we exec'd
			// (p_script.c:649-660).  tools/pcf.py names the blocks to match.
			eff  = particleeffectnum(strcat(mname, "_", effname));
			// The one number that separates "we never looked it up" from "the
			// cfg did not parse": an unresolved handle emits nothing and is
			// otherwise completely silent.  The velocity is printed because it
			// is the rotation's only headless witness: boreas' snow must read
			// '0 0 -384' jit 384, not '-384 0 0'.
			dprint(sprintf("emit: psys %s_%s -> handle %g rate %g dist %g vel %v jit %g\n",
			               mname, effname, eff, rate, dist, vel, jit));

			/*
			  CHILDREN.  A .pcf system's children start with it, at the same
			  control point (particles.h:1550-1554 hands every child the same
			  orientation).  tools/pcf.py writes one extra index line per
			  parent->child link, tagged with the parent's name in the last
			  column, and each becomes its own emitter here at the same entity.
			  Counted in em_child so Emit_List's residual can add them back --
			  they are created without ever being "seen".
			*/
			if (pchild)
			for (j = 0; j < ps_n; j = j + 1)
			{
				if (ps_parent[j] != effname)
					continue;
				Emit_Add(org + ps_ofs[j], org + ps_ofs[j], Emit_PsysVel(j), ps_jit[j],
				         ps_rate[j], 1, ps_dist[j],
				         particleeffectnum(strcat(mname, "_", ps_name[j])), kind);
				em_child = em_child + 1;
				dprint(sprintf("emit: psys %s_%s child of %s rate %g\n",
				               mname, ps_name[j], effname, ps_rate[j]));
			}
		}

		j = Emit_Add(bmin, bmax, vel, jit, rate, burst, dist, eff, kind);
		if (j >= 0)
		{
			if (look >= 0)
				em_life[j] = (lmin + lmax) * 0.5;
			if (kind == EK_FIRE)
			{
				// 32 is No glow (fire.cpp:785).  This read 16, which is Don't
				// drop: Emit_DropFires.
				if (!(spawnflags & 32))
				{
					em_lit[j] = 1;
					em_flglow = em_flglow + 1;
				}
				if (!(spawnflags & 16))
				{
					em_drop[j] = 1;
					em_fldropwant = em_fldropwant + 1;
				}
			}
		}
	}

	remove(probe);
	Emit_DropFires();

	/*
	  THE LATCH, AFTER THE WALK AND ONLY IF THE LUMP OPENED.  It used to be the
	  first line of this function, and that made one bad frame permanent:
	  serverkey("map") can lead the entity data by a frame (cl_sprites.qc
	  :602-606 records it, from the decals before that), so a walk that saw no
	  "{" at all had already written vbsp_em_map, Emit_Frame's compare then
	  matched every frame, and the map stayed emitter-free for the session
	  with emit_list reporting 0 emitters and no reason.  cl_sprites.qc
	  :474-481 sets an opened flag on the first "{" and returns before its
	  latch; this does the same and goes one step further by writing "" rather
	  than leaving the previous map's name in place, because a restart of the
	  SAME map would otherwise compare equal and never retry.  The two execs
	  below are behind this guard so that the retry cannot exec a config on
	  every frame the lump stays unreadable.
	*/
	if (!opened)
	{
		Emit_PsysFree();
		vbsp_em_map = "";
		dprint(sprintf("emit: entity lump not readable yet for %s, will retry\n", mname));
		return;
	}
	vbsp_em_map = mname;

	// The shared effect set.  The build 51b essay above says why it is exec'd
	// from here and not from cfg/default.cfg.
	localcmd("exec particles/ftesurf.cfg\n");
	// The map's own baked systems, if Emit_PsysLoad found any.  See its essay.
	if (ps_n)
		localcmd(sprintf("exec particles/%s.cfg\n", mname));

	/*
	  SILENT when there is nothing.  Roughly half the library carries none of
	  these classes, so this is the common case and must not print -- the same
	  contract Zone_LoadForMap keeps at cl_zones.qc:297-304.
	*/
	if (em_n)
	{
		// Built by walking the kinds rather than as one nine-argument sprintf,
		// which fteqcc warns about past eight -- and this way a map only ever
		// reads out the classes it actually has.
		scol = "";
		k = 0;
		while (k < EK_N)
		{
			if (em_live[k])
				scol = strcat(scol, sprintf(" %g %s", em_live[k], Emit_KindName(k)));
			k = k + 1;
		}
		print(sprintf("^3emit:^7 %g emitters on %s:%s\n", em_n, mname, scol));
	}
	else
		dprint(sprintf("emit: none for %s\n", mname));
};

void() Emit_LoadFromWorld =
{
	Emit_LoadForMap();
};

/*
===========================================================================
  Emitting
===========================================================================
*/

// A random vector in the unit cube, biased to the centre by construction.
// Cheap on purpose: this runs once per particle.
vector() Emit_RandDir =
{
	return [random() * 2 - 1, random() * 2 - 1, random() * 2 - 1];
};

vector(float i) Emit_PointIn =
{
	local vector s;
	s = em_size[i];
	return em_mins[i] + [random() * s_x, random() * s_y, random() * s_z];
};

/*
  Two passes, and the second one is why.

  Pass 1 culls by distance and sums the demand of everything that survived.
  Pass 2 scales every surviving emitter by budget/demand and spends its
  accumulator.  A distance cull ALONE cannot bound the cost -- surf_shade holds
  339 dustmotes and nothing stops a map putting two hundred of them in one
  room -- so the budget is what actually makes the worst case safe, and
  scaling density rather than dropping whole emitters is what stops it popping.

  NO FRUSTUM OR BEHIND-CAMERA CULL, which is the opposite of what Sprite_Draw
  does two files up, and deliberately.  A sprite is drawn, so culling it costs
  nothing the moment it is off screen.  These particles LIVE for three to five
  seconds: an emitter culled because it is behind you produces an empty volume,
  and turning around shows it visibly refilling.  Distance only.

  TRIGGERED EMITTERS ARE OUT OF SCOPE and the counters say so.  44% of
  env_embers and 40% of env_spark wait for a Source I/O input.  There is no
  CSQC entity channel in this project -- clientstat is the only server-to-client
  path and it carries a fixed set of scalars, not "entity #713 turned on" -- so
  honouring those would be a different feature with a different wire format.
*/
void() Emit_Frame =
{
	local float i, n, ft, thr, budget, dscale, d, lights, lit, k, mdem;
	local float wdust, wember, wbubble, wfire, wspark, wsmoke, wstack, wpsys;
	local vector eye, v;

	em_fpsn = em_fpsn + 1;
	if (!cvar("vbsp_emit"))
		return;

	/*
	  The same lazy-reload latch cl_sprites.qc and cl_zones.qc use: one string
	  compare a frame, real work only when the map actually changed.

	  BEFORE the em_n test, not after.  CSQC_WorldLoaded is what normally
	  reloads this, and the latch is only the safety net for the ordering that
	  Patch 207 records as not always holding -- but a net that is skipped
	  whenever em_n is 0 would never catch the one case that matters, which is
	  arriving on a map WITH emitters from one without any.
	*/
	if (serverkey("map") != vbsp_em_map)
	{
		Emit_LoadForMap();
		return;
	}

	if (!em_n)
		return;

	/*
	  THE LOAD IS DRIVEN BY A MEASUREMENT, NOT BY A GUESSED MOMENT.

	  Three builds shipped an effect set that was never loaded, and each fix
	  moved the `exec` to a moment that looked right and was not:

	    49/50  implicit auto-load on a dotted name -- P_LoadParticleSet records
	           the config in loadedconfigs (p_script.c:3709) BEFORE FS_LoadFile
	           (:3746) and refuses every retry (:3702-3707).
	    51     exec from cfg/default.cfg -- runs before Renderer_Start, and
	           P_ParticleEffect_f discards a block in silence while
	           pe_script_enabled is false (p_script.c:1141-1170).
	    51b    localcmd exec at CSQC_WorldLoaded -- the blocks parse (the
	           ftesurf_dot shader gets built) and then something unloads all 35
	           again: r_exportalleffects dumps them with the right names and
	           EMPTY BODIES, which is what PScript_Query writes for a type whose
	           loaded flag is 0 (p_script.c:2372-2373).

	  Guessing a fourth moment would be the same mistake a fourth time.  The
	  engine hands us an exact probe and an idempotent loader, so use them:
	  particleeffectquery reads cl.particle_csprecache[] -- the same table
	  pointparticles reads -- so "" means this emitter is about to call into
	  nothing, whatever the reason.  Re-exec when that is true and only then.

	  This is robust against every cause at once: a vid_restart
	  (R_ApplyRenderer_Load fires Cvar_ForceCallback(&r_particlesystem),
	  renderer.c:2267, and PScript_Shutdown frees the whole part_type table,
	  and only r_particledesc's list is reloaded -- ours is not in it), a write
	  to r_particledesc on an engine with r_part_keepuser 0, or an engine
	  without Patch 272 at all, where every map load's forced r_particledesc
	  callback unloads the set (the cause, found after this net was written --
	  see Emit_LoadForMap).  Worst case the effects are absent for under a
	  second instead of for the entire session.

	  Costs one string compare per second.  em_reload counts the repairs and
	  emit_list prints it.  On a patched engine it reads 0; a count that keeps
	  climbing means something is unloading the set repeatedly and is a bug in
	  its own right, which is exactly the signal that was missing for three
	  builds.  ONE KNOWN FALSE POSITIVE, AND WHY IT CANNOT FIRE AT MAP LOAD: the
	  probe reads cl.particle_csprecache, which is re-resolved inside the
	  engine's draw (the r_plooksdirty block at the top of
	  PScript_DrawParticleTypes, which calls CL_RegisterParticles), and
	  Emit_Frame runs before renderscene() -- so a check on the first frame
	  after a parse reads the slot stale and would re-exec once for nothing.
	  Emit_LoadForMap therefore clears em_drawn, and the first Emit_Frame after
	  a load arms the deadline one second ahead from its OWN `time` (the one
	  CSQC_WorldLoaded sees can be a whole map load stale) and does not check,
	  so the first check always follows a drawn frame.  A console re-exec
	  mid-map can still trip it once; harmless.
	*/
	if (!em_drawn)
	{
		em_drawn = 1;
		em_reload_t = time + 1;
	}
	if (Emit_FlameStep())
		em_reload_t = time + 1;
	// Off the scripted particle system nothing of ours can answer, and a repair
	// would send every block again each second for good.
	if (time > em_reload_t && cvar("vbsp_emit_heal"))
	if (cvar_string("r_particlesystem") == "script")
	{
		em_reload_t = time + 1;
		k = Emit_FlameRepair();
		if (Emit_MoteRepair())
			k = TRUE;
		if (particleeffectquery(em_fx[FX_DUSTMOTE], 0) == "")
		{
			localcmd("exec particles/ftesurf.cfg\n");
			k = TRUE;
		}
		if (k)
		{
			em_reload = em_reload + 1;
			return;                 // the cbuf has not drained yet
		}
	}

	ft = frametime;
	if (ft <= 0)
		return;
	if (ft > 0.25)
		ft = 0.25;                      // a hitch is not a licence to emit

	eye = getproperty(VF_ORIGIN);
	dscale = cvar("vbsp_emit_dist");
	budget = cvar("vbsp_emit_budget");
	lights = cvar("vbsp_emit_lights");

	// Read once a frame, not once per emitter: surf_stonework4 would otherwise
	// be 531 cvar lookups a frame to answer the same six questions.
	wdust   = cvar("vbsp_emit_dust");
	wember  = cvar("vbsp_emit_embers");
	wbubble = cvar("vbsp_emit_bubbles");
	wfire   = cvar("vbsp_emit_fire");
	wspark  = cvar("vbsp_emit_spark");
	wsmoke  = cvar("vbsp_emit_smoke");
	wstack  = cvar("vbsp_emit_stack");
	wpsys   = cvar("vbsp_emit_psys");

	// ---- pass 1: cull, and total the demand
	em_demand = 0;
	dm_alive = 0;
	mdem = 0;
	em_flin = em_flthin = 0;
	i = 0;
	while (i < em_n)
	{
		em_want[i] = 0;

		k = em_kind[i];
		if      (k == EK_DUST || k == EK_CLOUD) d = wdust;
		else if (k == EK_EMBER)                 d = wember;
		else if (k == EK_BUBBLE)                d = wbubble;
		else if (k == EK_FIRE)                  d = wfire;
		else if (k == EK_SPARK)                 d = wspark;
		else if (k == EK_SMOKE)                 d = wsmoke;
		// Named rather than left to the else, and the distinction is load-bearing:
		// vbsp_emit_smoke defaults to 0, so an env_smokestack falling through to
		// it would be registered, parsed, counted and then silently never drawn.
		else if (k == EK_STACK)                 d = wstack;
		else if (k == EK_PSYS)                  d = wpsys;
		/*
		  NOTHING falls through here any more, and that is the point.  This arm
		  used to be `d = wsmoke` and it silently swallowed EK_STACK when that
		  was added: env_smokestack was registered, parsed, counted and then
		  never drawn, because vbsp_emit_smoke defaults to 0.  EK_PSYS then
		  inherited the same unnamed slot.  Every kind is now named, so the next
		  one added gets 0 -- invisible immediately and everywhere, which is a
		  bug you find in one map load instead of one that hides behind whatever
		  default the last-named class happened to have.
		*/
		else                                    d = 0;
		if (!d)
		{
			i = i + 1;
			continue;
		}

		if (dscale > 0)
		{
			// centre minus radius, so a 1024-unit dustcloud is not culled by
			// its own middle while its near face is at your feet.
			d = vlen(em_mid[i] - eye) - em_rad[i];
			if (d > em_dist[i] * dscale)
			{
				i = i + 1;
				continue;
			}
		}
		em_want[i] = em_rate[i];
		// A sheet fire reaches as far as Source's and thins on the way, so the
		// hundred in range on surf_anubis do not cost the near ones their flame.
		if (k == EK_FIRE)
		if (em_eff[i] < 0)
		{
			em_flin = em_flin + 1;
			d = vlen(em_mid[i] - eye);
			if (d > FL_NEAR)
			{
				em_want[i] = em_rate[i] * FL_NEAR / d;
				em_flthin = em_flthin + 1;
			}
		}
		if (em_life[i])
		{
			mdem = mdem + em_rate[i] * em_burst[i];
			dm_alive = dm_alive + em_rate[i] * em_life[i];
		}
		else
			em_demand = em_demand + em_want[i] * em_burst[i];
		i = i + 1;
	}

	// Source's pool, as a scale on every mote volume: a full pool refuses each
	// volume's spawns alike.  surf_psychedelia asks for 144,000 alive.  Before
	// the budget, so the other classes are not charged for motes never made.
	dm_thr = 1;
	if (dm_alive > DM_POOL)
		dm_thr = DM_POOL / dm_alive;
	em_demand = em_demand + mdem * dm_thr;

	thr = 1;
	if (budget > 0 && em_demand > budget)
		thr = budget / em_demand;
	em_throttle = thr;

	// ---- pass 2: spend
	lit = 0;
	i = 0;
	while (i < em_n)
	{
		if (!em_want[i])
		{
			i = i + 1;
			continue;
		}

		em_acc[i] = em_acc[i] + em_want[i] * thr * (em_life[i] ? dm_thr : 1) * ft;
		if (em_acc[i] > EM_BURST_MAX)
			em_acc[i] = EM_BURST_MAX;

		n = floor(em_acc[i]);
		if (n >= 1)
		{
			em_acc[i] = em_acc[i] - n;
			// Emissions, not particles -- and a spark emission is up to 28 of
			// them, so the accumulator's own EM_BURST_MAX is not a particle
			// bound on its own.  Four emissions is already more than anything
			// in the library asks for in one frame.
			if (n > 4)
				n = 4;
			n = n * em_burst[i];
			while (n > 0)
			{
				v = em_vel[i] + Emit_RandDir() * em_jit[i];
				// A zero dir would zero veladd along with it (veladd *=
				// VectorLength(dir), p_script.c:5232), so a still emitter must
				// still hand over something.
				if (vlen(v) < 0.01)
					v = '0 0 1';
				// EK_PSYS carries the handle itself, and its spawn volume is
				// the r_part block's own `spawnorg` -- so the point handed over
				// is the entity origin, which is the control point the .pcf's
				// box is measured from.  Everything else indexes em_fx and
				// picks a point inside the entity's brush.
				if (em_kind[i] == EK_PSYS)
					pointparticles(em_eff[i], em_mid[i], v, 1);
				else if (em_eff[i] < 0)
				{
					// -1 to -4 are the size classes, -5 to -8 the same with smoke.
					k = -1 - em_eff[i];
					pointparticles(Emit_FlameSlot(k & 3, k >= 4), em_mid[i], '0 0 1', 1);
				}
				else if (em_life[i])
				{
					// A Source mote: RandomVector(-SpeedMax, SpeedMax), FallSpeed
					// off z, and x and y as the ground Source's pull lets them cover.
					v_x = Emit_MoteDrift(v_x, em_life[i]);
					v_y = Emit_MoteDrift(v_y, em_life[i]);
					if (vlen(v) < 0.01)
						v = '0 0 1';
					pointparticles(dm_fx[em_eff[i]], Emit_PointIn(i), v, 1);
				}
				else
					pointparticles(em_fx[em_eff[i]], Emit_PointIn(i), v, 1);
				n = n - 1;
			}
		}

		/*
		  The dlight, for a few fires only and off by default.

		  CL_AllocDlight with key 0 takes the free-slot path and never reuses a
		  slot (cl_ents.c:242-278), and the non-real-time pool is at most 64.
		  A lightradius on the main `fire` block would therefore exhaust it in
		  a single frame on surf_stonework4's 531 fires.  This emits a separate
		  count-0 effect -- no particles, one light -- at roughly 10Hz.

		  THE FIRST N IN LUMP ORDER, not the nearest N, and the distinction is
		  visible: they are already inside the distance cull, so they are all
		  nearby, but which of them get the light is arbitrary and changes as
		  you move.  Sorting would cost a pass over every fire every frame to
		  choose between lights that are individually barely perceptible.  If
		  this ever looks wrong, that is the reason and the sort is the fix.
		*/
		if (em_lit[i])
		if (lights > 0)
		if (lit < lights)
		{
			em_ltacc[i] = em_ltacc[i] + ft * 10;
			if (em_ltacc[i] >= 1)
			{
				em_ltacc[i] = em_ltacc[i] - floor(em_ltacc[i]);
				pointparticles(em_fx[FX_FIRELIGHT], em_mid[i], '0 0 1', 1);
				lit = lit + 1;
			}
		}

		i = i + 1;
	}
};

/*
===========================================================================
  Diagnostic
===========================================================================
*/

/*
  Every class, and every skip accounted for.

  The same contract cl_sprites.qc's report keeps: a class that quietly draws
  nothing has to say which rule silenced it rather than just being absent from
  the list.  The residual is COMPUTED rather than enumerated -- seen, minus
  emitting, minus each named reason -- so a skip path added later that forgets
  to bump a counter shows up here as an unexplained number instead of
  disappearing.  A tally of the reasons I remembered to count would only ever
  agree with itself.
*/
void() Emit_List =
{
	local float k, tot, sm;

	print(sprintf("^3emit:^7 map %s, %g emitters, %g effect handles\n",
	              vbsp_em_map, em_n, EM_FX_N));

	tot = 0;
	k = 0;
	while (k < EK_N)
	{
		if (em_seen[k])
		{
			// "created", not "emitting".  em_live is incremented at LOAD time,
			// so it counts emitters that survived parsing -- NOT emitters inside
			// their cull this frame.  The old wording cost another session a
			// wrong conclusion: it read "emitting 161" beside an empty
			// r_partinfo and inferred the particle system was dead, when in
			// fact all 161 were out of range from where it was standing.
			print(sprintf("  %-18s seen %4g  created %4g  off %4g\n",
			              Emit_KindName(k), em_seen[k], em_live[k], em_off[k]));
			// Named, not folded into the residual below: Source draws one
			// particle for such an entity and then nothing (see the note in
			// Emit_LoadForMap's dust branch), so this is a skip with a reason.
			if (em_norate[k])
				print(sprintf("  %-18s   %4g with a rate <= 0, skipped (Source: one particle, ever)\n",
				              "", em_norate[k]));
		}
		tot = tot + em_seen[k] - em_live[k] - em_off[k] - em_norate[k];
		k = k + 1;
	}
	// Children are created without being seen, so without this they would
	// read as a negative residual below.
	tot = tot + em_child;
	if (em_child)
		print(sprintf("  %g child system(s) started with their baked parent\n", em_child));
	if (!em_any)
		print("  none of the eight classes on this map\n");

	// Frozen is no longer a skip -- build 51 emits them at 1 u/s instead of
	// dropping them -- so it is reported as a note and NOT subtracted below.
	// It used to be both, and leaving the subtraction in would have hidden one
	// real unaccounted emitter for every frozen one on the map.
	if (em_frozen)  print(sprintf("  %g Frozen, drawn nearly still\n", em_frozen));
	if (em_clamped) print(sprintf("  clamped %g SpawnRate to %g (vbsp_emit_ratemax)\n", em_clamped, em_ratemax));
	if (em_over)    print(sprintf("  ^1dropped %g past EM_MAX %g^7\n", em_over, EM_MAX));

	/*
	  What is left over after every named reason.  Expected to be the brush
	  entities whose "model" key was missing or not a "*N" submodel, which is
	  the one silent drop in the walk and should be zero or near it.  A large
	  number here means a class is being read and then thrown away somewhere
	  that forgot to say so.
	*/
	if (tot)
		print(sprintf("  %g unaccounted (no submodel, or an uncounted skip)\n", tot));

	print(sprintf("  demand %g/sec, budget %g, throttle %.3f\n",
	              em_demand, cvar("vbsp_emit_budget"), em_throttle));

	// env_fire: the sheet or the orbs, and which rule chose.  A class counts as
	// answering only once one of its effects answers the engine's own query.
	if (em_seen[EK_FIRE])
	{
		if (em_flwhy != "")
			print(sprintf("  env_fire: orbs, because %s\n", em_flwhy));
		else
		{
			// Slots 0-12 of a class are its flame and embers, 13-16 its smoke.
			tot = sm = 0;
			for (k = 0; k < 4 * FL_SLOTS; k = k + 1)
				if (em_flmask & pow(2, floor(k / FL_SLOTS)))
				if (particleeffectquery(em_flfx[k], 0) != "")
				{
					if (k - floor(k / FL_SLOTS) * FL_SLOTS < 13)
						tot = tot + 1;
					else
						sm = sm + 1;
				}
			print(sprintf("  env_fire: flame sheet, size classes %g (1 tiny 2 small 4 medium 8 large), %g of their %g effects answering\n",
			              em_flwant, tot, 13 * ((em_flwant & 1) + (em_flwant & 2) / 2 + (em_flwant & 4) / 4 + (em_flwant & 8) / 8)));
			if (em_smwhy != "")
				print(sprintf("  env_fire: no smoke, because %s\n", em_smwhy));
			else if (!em_flsmoke)
				print("  env_fire: no smoke, because every fire here is Smokeless\n");
			else
				print(sprintf("  env_fire: smoke over %g fires, %g of %g smoke effects answering\n", em_flsmoke, sm,
				              2 * ((em_smwant & 1) + (em_smwant & 2) / 2 + (em_smwant & 4) / 4) + (em_smwant & 8) / 2));
			print(sprintf("  env_fire: %g in reach (%g units), %g of them past %g and thinned\n",
			              em_flin, FL_REACH, em_flthin, FL_NEAR));
		}
		print(sprintf("  env_fire: %g may carry a light (no spawnflags 32)\n", em_flglow));
		print(sprintf("  env_fire: %g without Don't drop: %g lit on what is under them (mean %g, most %g units), %g with nothing within 1024, %g inside something\n",
		              em_fldropwant, em_fldrop, em_fldrop ? rint(em_fldropsum / em_fldrop) : 0, rint(em_fldropmax), em_flnofloor, em_flinside));
		if (em_fldropover)
			print(sprintf("  ^1%g brush entities past %g were not stood up for the drop^7\n", em_fldropover, FL_DROPSOLIDS));
	}

	if (em_seen[EK_DUST])
	{
		if (dm_why != "")
			print(sprintf("  func_dustmotes: orbs, because %s\n", dm_why));
		else
		{
			tot = 0;
			for (k = 0; k < dm_n; k = k + 1)
				if (particleeffectquery(dm_fx[k], 0) != "")
					tot = tot + 1;
			print(sprintf("  func_dustmotes: Source's motes, %g looks asked, %g answering\n", dm_n, tot));
			print(sprintf("  motes in range would keep %g alive; Source's pool is %g, so %.3f of them spawn\n",
			              rint(dm_alive), DM_POOL, dm_thr));
			if (dm_over)
				print(sprintf("  %g func_dustmotes past %g looks, drawn as orbs\n", dm_over, DM_MAX));
		}
	}

	// What a class costs, as an A/B: cl_maxfps 0, emit_list, wait, emit_list.
	k = gettime(0);
	if (em_fpst && k > em_fpst)
		print(sprintf("  %g frames in %.2f s since the last emit_list, %.1f a second\n",
		              em_fpsn, k - em_fpst, em_fpsn / (k - em_fpst)));
	em_fpst = k;
	em_fpsn = 0;

	/*
	  The handles -- AND THEY CANNOT TELL YOU WHETHER THE EFFECT RESOLVED.
	  This comment used to claim they could, and the b49 test procedure told
	  Lex to read them as the primary diagnostic.  Both were wrong.

	  particleeffectnum returns `-i` at pr_csqc.c:3863, the CSQC precache slot,
	  whether or not the name ever matched an r_part block -- which is the same
	  property this file's own Emit_Precache essay relies on for taking handles
	  before the cfg has loaded.  A negative handle is therefore the NORMAL and
	  expected value and says nothing either way.  Printed only so a handle of
	  exactly 0 stands out, which would mean the precache table was full.

	  Printed only so a handle of exactly 0 stands out, which would mean the
	  precache table was full.
	*/
	print(sprintf("  handles: dustmote_0 %g  fire %g  spark %g\n",
	              em_fx[FX_DUSTMOTE], em_fx[FX_FIRE], em_fx[FX_SPARK]));

	/*
	  particleeffectquery IS a valid probe, and a note here previously said --
	  twice, in two essays that contradicted each other three lines apart --
	  that it was not.  That claim came from grepping the engine for
	  `ParticleQuery` and finding only the call site (pr_csqc.c:3877): the
	  vtable slot is filled POSITIONALLY, so pe_script's initialiser assigns
	  PScript_Query to it without the identifier ever appearing next to the
	  member name (p_script.c:7886, against particles.h:245-246).  A grep for a
	  member name cannot see a positional initialiser -- check the field ORDER.

	  It also translates the handle first (pr_csqc.c:3875), which matters
	  because our handles are negative and PScript_Query rejects typenum < 0.

	  So its answer counts: an empty string here really does say the effect does
	  not exist in the engine.  On 2026-09-08 it said exactly that, corroborated
	  independently by r_partinfo reporting `0 particles, 65536 free` while 33
	  env_smokestack sat inside the cull.

	  THE NAME IS TAKEN FROM Emit_FxName, not written out here.  It used to be
	  the literal "ftesurf.dustmote_0", which survived the rename to the dotless
	  spelling and then reported a name this file no longer asks the engine for
	  -- a diagnostic lying about its own subject, in the one line someone reads
	  when they are already lost.
	*/
	print(sprintf("  resolves: %s '%s'   reloads %g\n", Emit_FxName(FX_DUSTMOTE),
	              particleeffectquery(em_fx[FX_DUSTMOTE], 0), em_reload));
	if (ps_n)
	{
		print(sprintf("  psys: %g baked system(s) + %g child link(s) for %s, first %s\n",
		              ps_n - ps_links, ps_links, vbsp_em_map, ps_name[0]));
	}
};

/*
===========================================================================
  emit_test -- THE TWENTY LINES THAT SHOULD HAVE BEEN WRITTEN FIRST.

  The build 49 plan opened with "prove the generation route in twenty lines,
  before building anything on it": one effect, one pointparticles, at the
  player's feet, behind a temporary command.  That step was skipped because the
  engine source appeared to settle every question, and ~700 lines were then
  built on an unproven route.  It has since emerged that no emitter has ever
  spawned a particle, so this is that step, arriving two builds late.

  IT BYPASSES EVERYTHING IN THIS FILE.  No lump walk, no emitter array, no
  distance cull, no budget, no accumulator, no per-class cvar -- just a handle
  and a spawn at your own origin.  So it splits the fault cleanly in two:

      particles appear  ->  the effects and the engine are FINE, and the bug is
                            in this file's emitter logic (the cull, the budget,
                            the accumulator, or Emit_Frame not running)
      nothing appears   ->  the effect system itself is not spawning, and
                            nothing in this file can fix it

  It also prints what the engine says about the handle, using the only two
  probes that are actually valid:
    particleeffectnum  -- the negative CSQC precache slot.  It is returned
                          whether or not the name ever resolved
                          (pr_csqc.c:3863), so it is ONLY useful for spotting 0.
    particleeffectquery -- a real probe, contrary to an earlier note in this
                          file.  PScript_Query is the second slot of pe_script,
                          filled positionally (p_script.c:7886), and the builtin
                          translates the CSQC handle before querying
                          (pr_csqc.c:3875).  It returns "config.name" for a type
                          that exists and "" for one that does not.

  usage:  emit_test              the default dustmote
          emit_test fire         any suffix; "ftesurf_" is prepended
          emit_test <name> 200   how many to spawn
===========================================================================
*/
void() Emit_Test =
{
	local string nm, q;
	local float h, n;
	local vector o;

	nm = (argv(1) != "") ? strcat("ftesurf_", argv(1)) : "ftesurf_dustmote_0";
	n  = (argv(2) != "") ? stof(argv(2)) : 60;

	h = particleeffectnum(nm);
	q = particleeffectquery(h, 0);

	o = getproperty(VF_ORIGIN);

	print(sprintf("^3emit_test:^7 %s\n", nm));
	print(sprintf("  handle %g   %s\n", h,
	              (h == 0) ? "^1ZERO -- the precache table is full^7" : "(negative is normal)"));
	print(sprintf("  query  \"%s\"  %s\n", q,
	              (q == "") ? "^1EFFECT DOES NOT EXIST^7"
	                        : "^2effect exists^7"));
	print(sprintf("  spawning %g at %v\n", n, o));

	// Straight at the eye, and slightly below it so they are not inside the
	// near clip plane.  A small upward dir so |dir| is non-zero -- a zero
	// vector would zero veladd with it (p_script.c:5232).
	pointparticles(h, o - '0 0 24', '0 0 20', n);

	print("  if nothing appears at your feet, the fault is below this file\n");
};

/*
  emit_mote <depth> <rise> <count> <r g b alpha sizemin sizemax lifemin lifemax distmax frozen> [right]

  A ROW OF SOURCE MOTES AT A KNOWN DEPTH, standing still: `count` of one look,
  `depth` units in front of the eye, `rise` of that depth above the line of
  sight and `right` of it to the side, 0.06 of it apart.  It is the ruler
  cfg/test/p648motes.cfg reads a mote's size and fade off -- a volume's motes
  are at depths nobody knows.
*/
void() Emit_MoteRow =
{
	local float depth, n, i, look;
	local vector o;
	local string l;

	if (dm_why != "")
	{
		print(sprintf("emit_mote: orbs, because %s\n", dm_why));
		return;
	}
	if (argv(13) == "")
	{
		print("emit_mote <depth> <rise> <count> <r g b alpha sizemin sizemax lifemin lifemax distmax frozen> [right]\n");
		return;
	}
	depth = stof(argv(1));
	n = stof(argv(3));
	o = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	o = o + v_forward * depth + v_up * (depth * stof(argv(2))) + v_right * (depth * stof(argv(14)));
	// The look is argv's own text, so take the eye's vectors first: Emit_MoteLook tokenizes.
	l = sprintf("%s %s %s %s %s", argv(4), argv(5), argv(6), argv(7), argv(8));
	l = strcat(l, sprintf(" %s %s %s %s %s", argv(9), argv(10), argv(11), argv(12), argv(13)));
	dm_fresh = FALSE;
	look = Emit_MoteLook(l);
	if (look < 0)
	{
		print(sprintf("emit_mote: all %g looks are taken\n", DM_MAX));
		return;
	}
	// A look made by this very call is text the engine has not read yet, and
	// a particle sent to it now is dropped without a word.  dm_fresh, not the
	// query alone: on a second map the last map's block of that name answers.
	if (dm_fresh || particleeffectquery(dm_fx[look], 0) == "")
	{
		print(sprintf("emit_mote: look %g is new; say it again to place the row\n", look));
		return;
	}
	for (i = 0; i < n; i = i + 1)
		pointparticles(dm_fx[look], o + v_right * ((i - (n - 1) * 0.5) * depth * 0.06), '0 0 0.0001', 1);
	print(sprintf("emit_mote: %g of look %g (%s) at depth %g, row centre %v\n", n, look, l, depth, o));
};

float(string cmd) Emit_ConsoleCommand =
{
	if (argv(0) == "emit_mote")
	{
		Emit_MoteRow();
		return TRUE;
	}
	if (argv(0) == "emit_list")
	{
		Emit_List();
		return TRUE;
	}
	if (argv(0) == "emit_test")
	{
		Emit_Test();
		return TRUE;
	}
	return FALSE;
};
