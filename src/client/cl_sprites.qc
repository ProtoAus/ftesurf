/*
===========================================================================
  cl_sprites.qc -- Source's sprite entities, drawn as world polygons.

  Five classes, 34909 instances across 551 of the 1310 shipped maps, and not one
  of them has ever drawn a pixel: they are point entities, so SSQC's catch-all
  removes them as "nothing to preserve", and nothing on the client ever looked
  for them.  They are the light glows on every lamp, the god-rays from every
  ceiling fixture, the fires, the halos and the flat billboard trees.

  WHAT IS DRAWN, measured over the whole library:

      point_spotlight       23666   413 maps   a light shaft
      env_sprite            10947   276 maps   a camera-facing billboard
      env_sprite_oriented     284     8 maps   a billboard fixed to its angles
      beam_spotlight           11     2 maps   point_spotlight's newer name
      env_glow                  1     1 map    point_spotlight's OLDER name

  WHAT IS NOT, and why -- both were in the plan and both were removed by
  measurement rather than by running out of time.  See the two essays further
  down, above Sprite_LoadForMap.

      env_spritetrail        2773   132 maps   needs its parent's MOTION
      env_lightglow          3393   137 maps   is a view-space flare, not a sprite

  WHY POLYGONS AND NOT ENTITIES.  A sprite is one quad with no collision and no
  state, so an entity each would be a CopyCSQCEdictToEntity call and a model
  slot for something R_BeginPolygon draws in six calls.  More decisively, the
  forcedshader entity path hardcodes SPR_VP_PARALLEL (gl_alias.c:3003-3009) and
  env_sprite_oriented needs a fixed world orientation, which that cannot
  express.  Polygons also batch: consecutive R_BeginPolygon calls with the same
  shader and flags do not flush (pr_csqc.c:1671), which is what the draw order
  below is arranged to exploit.

  THE COST IS SMALL, and the plan's estimate of it was wrong.  "24k polys" is
  the LIBRARY total, not a map's; the worst single map is bhop_rpg at 863
  drawables, then surf_grotto at 464.  So there is no cap and no LOD here, only
  a distance cull and a kill switch.
===========================================================================
*/

#define SPR_MAX      1024       // billboards.  Worst map (bhop_rpg) is 862.
#define BEAM_MAX      768       // light shafts.  Worst map (surf_grotto) is 464.
#define SPRMAT_MAX     96       // distinct materials.  Worst map is 34.
/*
  Occluders.  238,420 brush entities across the 1310 shipped maps, 182 a map on
  average and 1398 on the worst (bhop_arcane) -- but 64% of those are triggers,
  which are declined below, so the number actually instantiated is far smaller.
  The cap is a backstop against a map nobody has measured, not a working limit.
*/
#define OCC_MAX       768

#define SPRK_BILLBOARD  0       // faces the viewer, stays upright
#define SPRK_ORIENTED   1       // fixed to the entity's own angles
/*
  BUILD 54 -- env_lightglow.  A VIEW-SPACE flare, not a world billboard: the
  quad is placed at a fixed 100 units in front of the eye along the direction to
  the glow (glow_overlay.cpp:330-343), so it holds a constant angular size at
  any range, and its two half-extents come from the entity's own keys rather
  than from the texture.  See Glow_Add.
*/
#define SPRK_GLOW       2

// ---------------------------------------------------------------- materials
/*
  One entry per distinct material, because the SIZE has to be asked for and the
  answer costs a texture load.

  A Source sprite's world size is its texture's size in PIXELS times `scale`:
  spritemodel.cpp:317-330 sets the quad's half-extents to m_width/2 and
  m_height/2 with no other factor, and c_sprite.cpp:102-105 multiplies those by
  scale alone.  So one texel is one unit at scale 1, and a 128x128 glow at the
  library's median scale of 1 is 128 units across.

  There is exactly one builtin that can answer "how big is that texture" --
  drawgetimagesize -- and it blocks until the image has loaded
  (R_GetShaderSizes with blocktillloaded true, gl_shader.c:9442).  That is fine
  once per material at map load and would be unthinkable per sprite per frame,
  which is the whole reason this table exists.

  It resolves through R_RegisterPic and the draw resolves through
  R_RegisterCustom, so the two are separate shader objects keyed on different
  usage flags -- but both reach the same VMT through the same material loaders
  and therefore the same VTF, so the size is the size the drawn quad has.
*/
string sprmat_name[SPRMAT_MAX];         // the STEM, as R_BeginPolygon wants it
float  sprmat_w[SPRMAT_MAX];            // texture size in pixels, 0 = unresolved
float  sprmat_h[SPRMAT_MAX];
float  sprmat_orient[SPRMAT_MAX];       // BUILD 55: SPRO_*, read from the .vmt
float  sprmat_n;
float  sprmat_zoned;                    // names hold strzone handles to give back

/*
  BUILD 55 -- WHICH WAY A SPRITE FACES IS A PROPERTY OF ITS MATERIAL.

  Reported as: "the light sprites don't always face the camera, they stay
  'locked' from underneath and stand upright in the Z.  I believe this is wrong."

  It was wrong.  Every non-oriented sprite was drawn as SPR_VP_PARALLEL_UPRIGHT
  -- world +Z for up, right from the view's yaw only -- on the strength of
  spritemodel.cpp:311, which really does default to that.  But it defaults to it
  only when the material is SILENT, and almost none of them are:

      m_orientation = orientationVar ? orientationVar->GetIntValue()
                                     : SPR_VP_PARALLEL_UPRIGHT;

  sprites/light_glow03.vmt -- the material surf_tensor2's 263 env_sprites
  actually use -- says "$spriteorientation" "vp_parallel", which is the FULL
  billboard: the view's own right and up (c_sprite.cpp:278-290).  Across the 213
  Sprite-shader materials in the mounted VPKs: 177 vp_parallel, 17
  parallel_upright, 4 vp_parallel_oriented, 3 oriented.  The old behaviour
  implemented the 17.

  The two that are counted and declined are not guesses either:
    facing_upright       right is perpendicular to the direction to the SPRITE
                         rather than to the view (c_sprite.cpp:245-275), so it
                         needs a per-sprite basis; drawn as upright, which is
                         what it degenerates to when you are level with it.
    vp_parallel_oriented parallel plus a roll about the view axis taken from the
                         entity's roll (:327+); drawn as parallel, i.e. correct
                         except for the roll.
  7 of 213 materials, and both are visible in the census rather than silent.
*/
#define SPRO_PARALLEL   0       // vp_parallel -- the view's right and up
#define SPRO_UPRIGHT    1       // parallel_upright -- world +Z, right from yaw
#define SPRO_FACING     2       // facing_upright -- declined, drawn as upright
#define SPRO_VPORIENT   3       // vp_parallel_oriented -- declined, as parallel
#define SPRO_ENTANGLES  4       // oriented -- the entity's own angles

/*
  BUILD 58 -- WHICH ADDITIVE KIND, packed into spr_add rather than beside it.

  spr_add held a boolean and every reader asks `if (spr_add[i])`, so widening it
  to a small enum costs nothing and keeps all of them working: every value below
  except NONE is truthy. A second SPR_MAX array would have cost about eight times
  its data in progs -- the measurement this file already cites for the glow
  parameter table -- to carry one number per sprite that takes five values.

  THE DISTINCTION IS SOURCE'S, NOT OURS. kRenderGlow (3) and kRenderWorldGlow (9)
  are the only two rendermodes routed through GlowBlend (c_sprite.cpp:411-414),
  and therefore the only two that get renderamt applied a SECOND time and an
  inverse-square distance fade. kRenderTransAdd (5) is additive and gets neither.
  The two renderfx that change that arithmetic ride along here for the same
  reason: they are per-sprite, they take two values on any real map, and a third
  array for them would be absurd.
*/
#define SPRA_NONE       0       // not additive; the material's own blendfunc
#define SPRA_ADD        1       // kRenderTransAdd -- additive, ONE renderamt
#define SPRA_GLOW       2       // kRenderGlow/kRenderWorldGlow -- the dimmed pair
#define SPRA_NODISS     3       // ...plus kRenderFxNoDissipation (14): no distance fade
#define SPRA_PULSE      4       // ...plus kRenderFxPulseSlowWide (3): renderamt pulses

float sprmat_orient_read;               // materials whose .vmt answered
float sprmat_orient_guess;              // materials that had to take the default
float sprmat_orient_decl;               // facing_upright + vp_parallel_oriented

// ---------------------------------------------------------------- billboards
vector spr_org[SPR_MAX];
vector spr_col[SPR_MAX];                // 0..1
vector spr_right[SPR_MAX];              // unit basis, SPRK_ORIENTED only
vector spr_up[SPR_MAX];
float  spr_alpha[SPR_MAX];
float  spr_hw[SPR_MAX];                 // half-extents, world units
float  spr_hh[SPR_MAX];
float  spr_rad[SPR_MAX];                // cull radius, precomputed
float  spr_mat[SPR_MAX];                // index into the table above
float  spr_kind[SPR_MAX];
float  spr_add[SPR_MAX];                // SPRA_*, and every value but NONE is truthy
float  spr_n;
/*
  BUILD 58.  How many sprites the Source dimming was applied to, and it is a
  GLOBAL holding LAST frame's count rather than a local, because the census that
  prints it runs at the top of Sprite_Draw -- upstream of the loop that does the
  work.  As a local it printed 0 in every arm of the first A/B, which is exactly
  the shape of a liveness check that cannot fail informatively: a switch that is
  working and a switch that never ran both read zero.
*/
float  spr_dim_n;

/*
  BUILD 52 -- THE GLARE STATE.  See Sprite_Glare, below Sprite_Draw.

  spr_gvis is the last answer the occlusion trace gave for this sprite: 1 clear,
  0 blocked.  spr_glare is that answer RAMPED over time, which is what actually
  multiplies the alpha.  They are separate because the trace is amortised -- only
  a few sprites are traced per frame -- and the ramp is what makes the staleness
  invisible.  Source does the same thing for the same reason.

  BUILD 60 -- spr_gtraced IS NOW A VISIT COUNT, and the one thing that reads it
  still reads it as a boolean.  0 means "never traced, so spr_gvis is not an
  answer yet" -- the ramp below turns that into a target of 0 so nothing flashes
  on the first frame.  Anything >= 1 means "spr_gvis is a real answer", which is
  all that reader wants.  The VALUE is how many times Sprite_Glare's round-robin
  has visited this glare, and it only ever increments.

  WHY A RUNNING COUNT AND NOT A RESETTING ONE, because the first version of this
  was the latter and it did not work.  The adaptive path has to force a full
  five-ray re-check occasionally; version one counted cheap confirmations and
  reset to 1 on each full answer.  That cannot keep the re-checks SPREAD OUT:
  every glare given a full answer in the same sweep then shares a phase forever,
  so one sweep in nine cost five rays for everything and took as long as build
  59's did -- measured, 9/50/14 frames per sweep on three consecutive frames.
  Seeding the first period per glare fixed the load case and nothing else: one
  sweep with the shortcut off -- vbsp_glare_adaptive 0, vbsp_glare_rays 1 or
  vbsp_sprite_source 0, which is EVERY documented A/B arm -- set every glare to
  the same value and re-synchronised the map permanently.  Three of four review
  lenses found that independently and all three were right.

  A count that never resets has no such state to lose.  A glare owes a full
  re-check when its visit count is congruent to its own INDEX modulo adapt+1:
  the period is exactly adapt+1 visits for every glare, the phase is a property
  of the index rather than of history, and no toggle, reload or visibility change
  can collapse two glares into one phase.  It also de-phases at adapt 1, which
  `i mod adapt` could not (i mod 1 is identically 0).

  A count rather than a fifth SPR_MAX array because this project has measured
  fteqcc's array overhead at about 8x the data (see the glow parameter sets
  below).  Precision: it rises about once per sweep, so 2^24 is days of play,
  and it is read modulo adapt+1 anyway -- a wrap changes a phase, not a
  behaviour.
*/
float  spr_gvis[SPR_MAX];               // last trace: 1 = centre point visible
float  spr_glare[SPR_MAX];              // 0..1, ramped toward spr_gvis
float  spr_gtraced[SPR_MAX];            // 0 = never traced; else the visit count
float  spr_gnext;                       // round-robin cursor for the trace budget

/*
===========================================================================
  BUILD 54 -- THE GLOW PARAMETER SETS, and why they are a table.

  Four numbers belong to a glow rather than to its material: the three distances
  of env_lightglow's fade ramp, and GlowProxySize, which is how far the
  occlusion trace stops short of the glow.  Four more SPR_MAX float arrays would
  cost roughly four times SPR_MAX*4 bytes times EIGHT in progs -- this project
  has measured fteqcc's array overhead at about 8x the data -- for numbers that
  in practice take a handful of distinct values per map.

  surf_tensor2 is the case that decided it: 263 env_sprite carry GlowProxySize
  2.0 (203 of them), 3 (56) and 6 (4), and all 166 env_lightglow carry the same
  MinDist 500 / MaxDist 2500 / OuterMaxDist 7500.  Four distinct sets on a map
  with 429 glows.  So one float per sprite indexes a small shared table, exactly
  the indirection sprmat_* already uses and for the same reason.
===========================================================================
*/
#define GLOWP_MAX      64
float  glowp_min[GLOWP_MAX];            // env_lightglow MinDist (0 for a sprite)
float  glowp_max[GLOWP_MAX];            // ...MaxDist
float  glowp_outer[GLOWP_MAX];          // ...OuterMaxDist, 0 = no outer ramp
float  glowp_backoff[GLOWP_MAX];        // how far short of the glow the trace stops
float  glowp_n;
float  glowp_over;                      // distinct sets that did not fit

float  spr_pset[SPR_MAX];               // index into the four arrays above

/*
  BUILD 54 -- THE CONTAINING OCCLUDER, which is the fix for "some of them are
  placed inside of the portal and now don't render".

  A glow is placed AT the thing it lights, and on this library that thing is
  routinely a brush entity the glow sits INSIDE.  Build 53 gave the trace those
  brush entities to hit, so every such glow started reporting blocked from every
  angle and vanished.  Measured on surf_tensor2: 38 additive sprites have their
  origin inside a kept occluder, 21 of them at exactly 4.0 units of depth -- the
  size of the trace's own back-off -- and 9 at 0.0, dead on a face.  The spawn
  portal is the clean case: func_brush *19 is a 96 x 8 x 128 plate and the glow
  is at its exact centre, so the half-thickness in Y is 4 and the back-off is 4.

  Source does not hit this because its world-glow path never traces at all: it
  rasterises a proxy pulled GlowProxySize toward the camera and counts surviving
  pixels (c_pixel_visibility.cpp:75-91).  The FGD says so in as many words --
  "if this glow is inside geometry (like a light bulb), set this value to be
  bigger than the bulb's radius".

  So the trace ignores the brush the glow lives in.  traceline's fourth argument
  is the entity to skip, which makes this free per frame: the containing brush
  is resolved once at load (Sprite_ResolveSkips) and world -- today's value --
  stays the default for every glow that is not embedded.
*/
entity spr_gskip[SPR_MAX];              // occluder to ignore, world = none
float  spr_gskip_n;                     // glows that resolved one
float  spr_gskip_multi;                 // glows inside more than one brush

/*
  QuakeC allows at most eight parameters and Sprite_Add already uses all eight,
  so the parameter-set index crosses the call boundary in a global.  Set it
  immediately before the call; the parser already accumulates into locals, and
  splitting one logical call into two would read worse than this does.
*/
float  spra_pset;

/*
  BUILD 53 -- THE BRUSH-ENTITY OCCLUDERS.  See Sprite_LoadOccluders.

  Reported as: "brush entities do not block the sprites from rendering when they
  should."  Correct, and build 52 said so in its own limitation note: a CSQC
  traceline runs against `csqc_world` (pr_csqc.c:50), which is the world model
  plus ONLY the entities the CSQC itself instantiated.  The server's func_* brush
  entities are in the SERVER's world and the client's trace has never been able
  to see them.

  So the client instantiates its own.  The map's entity lump is already walked at
  load (getentitytoken, the same walk that finds the sprites), every brush entity
  in it names a submodel as `model "*N"`, and setmodel on a CSQC entity resolves
  that against the world model exactly as it does server-side
  (CS_FindModel -> Mod_FixName, pr_csqc.c:695).  Zone_LoadFromBsp already proves
  the mechanism in this codebase.  Give the copy SOLID_BSP and the glare trace --
  and the spotlight trace, which had the same hole -- sees it.

  The copies are never drawn: the server's own entities draw the geometry, and a
  second visible copy would z-fight with it.  They exist only to be hit.

  MARKED WITH A FIELD RATHER THAN HELD IN AN ARRAY.  An entity array of any
  useful size is expensive in progs -- measured on this project at roughly 8x the
  data size -- and the only thing the list is ever used for is "remove them all
  at the next map load", which findfloat does without storing anything.
*/
.float spr_occluder;                    // 1 on our own brush-model copies

float  spr_occ_n;                       // brush entities instantiated
float  spr_occ_seen;                    // brush entities in the lump
float  spr_occ_over;                    // skipped: hit OCC_MAX
float  spr_gbrush;                      // traces stopped by one, since the last report
/*
  BUILD 59: what the frustum cull actually saved, per frame, so the claim is a
  number and not an argument.  Both are needed: "culled 380" on its own cannot
  distinguish a cull that is working from a cull that has thrown away everything
  including what is on screen, and `spr_gtraced_n` is the half that would go to
  zero if it had.
*/
float  spr_gcull;                       // glares skipped by the view test this frame
float  spr_gtraced_n;                   // glares actually traced this frame
/*
  BUILD 60 -- THE DENOMINATOR, and adding it corrects a number I have been
  reporting since build 59.

  The round-robin cursor advances once per VISIT, so the time for a full pass
  over the map is spr_n / visits-per-frame.  The build 59 census divided by
  glares TRACED per frame instead, which treats a culled glare as if the cursor
  never passed it -- and a culled glare is precisely a visit that costs no rays
  and still advances the cursor.  It made the cull look like it moved the sweep
  from 54 frames to 50 when the visit count says it moved it several-fold, and
  I told Lex the cull "bought almost nothing" on the strength of it.

  A derived figure with a wrong denominator is worse than no figure, because it
  reads like a measurement.  This is the measured quantity.
*/
float  spr_gvisits;                     // loop iterations this frame = cursor advance
/*
  BUILD 60: and then stop deriving it at all.  A sweep is one wrap of the
  round-robin cursor, so counting frames between wraps MEASURES the latency Lex
  reported instead of computing it from a per-frame sample that the ray budget
  makes unrepresentative.  spr_gsweep is the last complete pass, in frames.
*/
float  spr_gsweep;                      // frames the last full sweep took (measured)
float  spr_gsweep_f;                    // frames since the cursor last wrapped
/*
  BUILD 61 -- THE BUDGET WAS THE WRONG UNIT, and build 60's own measurement is
  what shows it.

  vbsp_glare_traces is a fixed number of rays PER FRAME, so the thing it
  actually controls -- how stale a glare's occlusion answer may be -- comes out
  different on every map and at every framerate.  Measured on surf_tensor2 at
  429 glares and 40 rays: a full sweep is 3.7 frames, which at 397 fps is 9.3
  ms.  On a map with a dozen glares the same 40 rays wrap the cursor three
  times in ONE frame: two of those passes re-answer questions that cannot have
  changed since the last one, and they cost the full 27.1 us a ray either way.
  Same cvar, same value, 30x apart in what it buys.

  So the honest knob is the interval itself.  vbsp_glare_interval is in
  SECONDS, and it is the age bound: every glare is re-answered at least that
  often, whatever the map holds and whatever the framerate is.  The per-frame
  visit quota is spr_n * frametime / interval, which is the definition
  rearranged and nothing cleverer.

  vbsp_glare_traces DOES NOT GO AWAY -- it becomes the ceiling rather than the
  target.  A quota is a promise about latency and a ceiling is a promise about
  the frame; a map dense enough that the quota cannot be met inside the ceiling
  should miss its interval rather than drop a frame, and the census says which
  of the two stopped the loop so that case is legible instead of mysterious.

  THE FRACTION HAS TO BE CARRIED.  At 400 fps a 12-glare map wants 12 * 0.0025
  / 0.05 = 0.6 visits per frame; floor() alone would make that 0 forever and
  the glares would never be traced at all.  spr_gvacc accumulates the fractional
  quota across frames, which is the same trick the decay ramp uses on frametime.

  MEASURED (b61int / b61fps / b61curve, surf_tensor2 at Lex's vantage).  The
  staleness column comes from the census's own counters, not from show_fps:
  frametime = quota * interval / spr_n, staleness = sweep * frametime.

      interval   rays/frame   staleness   fps
        0 (off)    40-44         9.5 ms   354.6
        0.015      20           15.9 ms   489.4
        0.025       7-12        26.8 ms   574.9
        0.05         1.5        42.6 ms   586.5
        0.10         2         110   ms   674.8

  Deadline met within 15% on every arm, ray ceiling never reached, and eight of
  nine settled arms byte-identical in the centre region.  The fps gain SATURATES
  past ~0.025 because by 7 rays a frame almost all of the ray cost is already
  gone -- which is the argument for 0.025 over 0.05: it buys back the latency
  for almost nothing.

  A WORD ON THE fps COLUMN, since it cost a run to learn.  show_fps drifted
  426.9 -> 369.7 monotonically over 90 seconds of b61int on a warm machine, and
  a one-shot arm order cannot separate that from the setting.  Every figure
  above is paired against an interval-0 control adjacent in time.  The quota is
  the better probe -- it is frametime read backwards out of the frame that fired
  the rays, with no averaging window and no screenshot hitch in it -- but it
  only exists while the interval is on, so show_fps still has to carry the
  comparison against interval 0.
*/
float  spr_gvacc;                       // fractional visit quota carried between frames
float  spr_gquota;                      // this frame's visit quota; 0 = uncapped
float  spr_glimit;                      // what stopped the loop: 1 rays, 2 visits, 0 neither
/*
  BUILD 60: the adaptive-ray split, and it needs THREE numbers, not one.

  `spr_gcheap` is how many of this frame's traced glares took the centre-only
  path and `spr_grays` is the rays actually fired.  Either alone can mislead: a
  large cheap count with the ray count unchanged would mean the accounting is
  wrong somewhere, and the ray count alone cannot show WHY it fell.
  `spr_gforce` is the third, and it is the one that proves the shortcut is not
  sticky -- it counts the forced full re-checks, so if it is ever 0 on a map
  with hidden glares then a glare that became visible behind a thin edge could
  stay dark forever.  See the essay in Sprite_Glare.
*/
float  spr_gcheap;                      // traced glares that fired 1 ray, this frame
float  spr_gforce;                      // cheap streaks broken by a forced full re-check
float  spr_grays;                       // rays actually fired this frame

// ------------------------------------------------------------------- beams
vector beam_org[BEAM_MAX];
vector beam_end[BEAM_MAX];
vector beam_col[BEAM_MAX];
float  beam_w0[BEAM_MAX];               // full width at the source
float  beam_w1[BEAM_MAX];               // ...and at the far end
float  beam_rad[BEAM_MAX];
float  beam_n;

// ------------------------------------------------------------------ counters
string vbsp_spr_map;                      // lazy-reload latch, as the decals use
float  vbsp_spr_seen;                     // sprite entities found, drawn or not
float  vbsp_spr_off;                      // skipped: named and not "start on"
float  vbsp_spr_nomat;                    // skipped: the material did not resolve
float  vbsp_spr_over;                     // skipped: hit SPR_MAX / BEAM_MAX
float  vbsp_beam_seen;
float  vbsp_beam_off;                     // skipped: the spotlight starts off
float  vbsp_trail_seen;                   // env_spritetrail, counted and declined
float  vbsp_glow_seen;                    // env_lightglow found
float  vbsp_glow_off;                     // ...skipped: vbsp_lightglow 0, or no size
float  vbsp_glow_n;                       // ...instantiated (BUILD 54)

/*
  BUILD 54.  Source's own material for a light glow, and it is hardcoded there
  too: glow_overlay.cpp:397 draws every CGlowOverlay sprite with this and the
  entity has no key to change it.  The "_noz" is not decoration -- the material
  is UnlitGeneric with $additive, $vertexcolor and $ignorez, which is exactly
  the combination the draw below forces with DRAWFLAG_ADD|DRAWFLAG_NODEPTHTEST.
*/
#define GLOW_MATERIAL   "sprites/light_glow02_add_noz"

/*
  The fixed distance CalcBasis places the quad at (glow_overlay.cpp:330).  It is
  what makes HorizontalGlowSize and VerticalGlowSize behave as an ANGULAR size:
  the quad is always this far from the eye, so its two half-extents are world
  units at 100 units and its size on screen never changes with range.
*/
#define GLOW_OVERLAYDIST 100

/*
  The two materials Source hardcodes for a spotlight, named here for the same
  reason the classnames are: point_spotlight.cpp:135-136 precaches exactly these
  and the entity has no key to change them.
*/
#define BEAM_MATERIAL   "sprites/glow_test02"

/*
  A beam's alpha is FIXED at 64/255, and that is not an approximation.
  point_spotlight.cpp:372 calls SetBrightness(64) unconditionally after setting
  the colour, so `renderamt` -- which 91.6% of these entities write, 98.5% of
  them as 255 -- never reaches the beam at all.  Wiring renderamt in would make
  every light shaft in the library four times too bright.
*/
#define BEAM_BRIGHTNESS (64 / 255)

/*
===========================================================================
  Material names

  Three transformations, each of which Source itself performs, and all three
  are load-bearing on real maps:

    lowercase + backslashes         "materials\Sprites\Glow.vmt"
    strip a leading "materials/"    37 of 847 distinct names carry it, and
                                    VMT_ReadVMT adds its own (mat_vmt.c:2189)
    strip the extension             122 of 847 name a ".spr" -- the HL1 sprite
                                    container -- and Source resolves those by
                                    stem too (spritemodel.cpp:252,
                                    Q_StripExtension before the material lookup)

  That last one is what makes the .spr names work rather than fail: of 11232
  sprite instances only THREE name a .spr with no matching .vmt beside it.  Had
  the extension been kept, "sprites/glow01.spr" would have asked for
  materials/sprites/glow01.spr.vmt, and the single most common sprite material
  in the library -- 2132 instances, 19.5% of all of them -- would have drawn
  nothing.
===========================================================================
*/
string(string raw) Sprite_MatStem =
{
	local string s;
	local float  i, dot, n;

	s = strtolower(strreplace("\\", "/", raw));

	if (substring(s, 0, 10) == "materials/")
		s = substring(s, 10, -1);

	// The extension is the last '.' AFTER the last '/', so a directory with a
	// dot in it -- "_hl2/sprites/blueflare1" has none, but map-packed content
	// is not required to be tidy -- cannot eat the name.
	n = strlen(s);
	dot = -1;
	for (i = n - 1; i >= 0; i = i - 1)
	{
		if (substring(s, i, 1) == "/")
			break;
		if (substring(s, i, 1) == "." && dot < 0)
			dot = i;
	}
	if (dot > 0)
		s = substring(s, 0, dot);

	return s;
};

/*
  Resolve a material to a table index, loading its size the first time.

  Returns -1 if the texture will not resolve, and the caller DROPS the sprite
  rather than guessing a size.  That is deliberate: R_BeginPolygon falls back to
  Shader_PolygonShader for an unknown name, which is an untextured coloured
  quad -- so a guessed size would put a solid 64-unit square where a soft glow
  belongs, which is worse than the nothing that is there today.  4.7% of the
  library's sprite instances land here, almost all of them "sprites/glow.vmt",
  a name no mounted pack has ever contained.
*/
/*
  BUILD 55 -- read $spriteorientation out of the material.

  A .vmt is plain text and FTE's filesystem has the mounted VPKs in it, so this
  is one fopen per DISTINCT material at map load -- two on surf_tensor2, and the
  library's worst map has 34.  Nothing per sprite and nothing per frame.

  THE LOOP DOES NOT BREAK ON AN EMPTY LINE, and that is not tidiness.  fgets
  returns the null string at EOF and a blank line is indistinguishable from it in
  QuakeC, so `if (!ln) break;` would stop at the first paragraph break --
  sprites/light_glow02_add_noz.vmt has one, three lines from the top, right above
  the keys worth reading.  A fixed line budget costs a few wasted iterations
  after EOF and cannot be fooled.

  Longest-first on the string tests, because the names nest: every
  "vp_parallel_oriented" contains "vp_parallel" and also contains "oriented", so
  testing either of the short ones first would mislabel it.

  Returns -1 when the file cannot be opened or says nothing -- a patch/include
  material, or content that is simply not there -- and the caller counts that
  separately from a material that answered.
*/
float(string stem) Sprite_ReadOrient =
{
	local float  fh, i, got;
	local string ln;

	fh = fopen(strcat("materials/", stem, ".vmt"), FILE_READ);
	if (fh < 0)
		return -1;

	got = -1;
	for (i = 0; i < 64; i = i + 1)
	{
		ln = fgets(fh);
		if (ln == "")
			continue;               // blank line OR eof -- see above
		ln = strtolower(ln);
		if (strstrofs(ln, "$spriteorientation") < 0)
			continue;

		if      (strstrofs(ln, "vp_parallel_oriented") >= 0) got = SPRO_VPORIENT;
		else if (strstrofs(ln, "parallel_upright")     >= 0) got = SPRO_UPRIGHT;
		else if (strstrofs(ln, "facing_upright")       >= 0) got = SPRO_FACING;
		else if (strstrofs(ln, "vp_parallel")          >= 0) got = SPRO_PARALLEL;
		else if (strstrofs(ln, "oriented")             >= 0) got = SPRO_ENTANGLES;
		break;
	}

	fclose(fh);
	return got;
};

float(string raw) Sprite_Material =
{
	local string stem;
	local vector sz;
	local float  i, o;

	stem = Sprite_MatStem(raw);
	if (stem == "")
		return -1;

	for (i = 0; i < sprmat_n; i = i + 1)
		if (sprmat_name[i] == stem)
			return (sprmat_w[i] > 0) ? i : -1;

	if (sprmat_n >= SPRMAT_MAX)
		return -1;

	sz = drawgetimagesize(stem);

	/*
	  THE MATERIAL IS ALWAYS READ, and vbsp_sprite_orient overrides at DRAW time
	  rather than here.  Caching the override would make the A/B need a map
	  reload, and an A/B that needs a reload is one where the two pictures differ
	  by a map load as well as by the thing under test -- which is exactly the
	  trap vbsp_lightglow is still in (it is load-time, so toggling it in the
	  console is a null test that looks like the feature not working).

	  THE DEFAULT WHEN THE MATERIAL WILL NOT ANSWER IS PARALLEL, not Source's
	  own parallel_upright fallback, and that is a deliberate disagreement.  A
	  material we cannot read is one whose content is missing or is a patch/
	  include we do not follow; guessing the 8% case for it reproduces exactly
	  the bug being fixed, and 177 of the library's 213 sprite materials are
	  parallel.  The guess is counted, so a map full of them says so.
	*/
	o = Sprite_ReadOrient(stem);
	if (o < 0)
	{
		o = SPRO_PARALLEL;
		sprmat_orient_guess = sprmat_orient_guess + 1;
	}
	else
	{
		sprmat_orient_read = sprmat_orient_read + 1;
		if (o == SPRO_FACING || o == SPRO_VPORIENT)
			sprmat_orient_decl = sprmat_orient_decl + 1;
	}

	i = sprmat_n;
	sprmat_name[i] = strzone(stem);
	sprmat_w[i] = sz_x;
	sprmat_h[i] = sz_y;
	sprmat_orient[i] = o;
	sprmat_n = sprmat_n + 1;
	sprmat_zoned = TRUE;

	if (sz_x <= 0 || sz_y <= 0)
	{
		// Named, because "some sprites are missing" is not actionable and
		// "sprites/glow.vmt is missing" is.  Same contract as the plugin's
		// hl2_unresolved list.
		dprint(sprintf("sprites: no material for \"%s\"\n", stem));
		return -1;
	}
	return i;
};

void() Sprite_FreeMaterials =
{
	local float i;
	// BUILD 55: reset here rather than in Sprite_LoadForMap, so the counts can
	// never outlive the table they describe.
	sprmat_orient_read = sprmat_orient_guess = sprmat_orient_decl = 0;
	if (!sprmat_zoned)
	{
		sprmat_n = 0;
		return;
	}
	for (i = 0; i < sprmat_n; i = i + 1)
		if (sprmat_name[i] != "")
			strunzone(sprmat_name[i]);
	sprmat_n = 0;
	sprmat_zoned = FALSE;
};

/*
===========================================================================
  Building the two lists
===========================================================================
*/

// "255 128 0" and "255 128 0 200" both occur -- 2.3% of env_spritetrail's
// colours carry a fourth component.  Source's rendercolor is three; the fourth
// is ignored there and is ignored here.
vector(string s) Sprite_ParseColor =
{
	local vector c;
	local float  n;
	n = tokenize(s);
	if (n < 3)
		return '1 1 1';
	c = [stof(argv(0)), stof(argv(1)), stof(argv(2))];
	return c * (1 / 255);
};

vector(string s) Sprite_ParseVec =
{
	local float n;
	n = tokenize(s);
	if (n < 3)
		return '0 0 0';
	return [stof(argv(0)), stof(argv(1)), stof(argv(2))];
};

/*
  Add one billboard.

  `ang` is only read for SPRK_ORIENTED, and the basis it produces is Source's:
  c_sprite.cpp:319-323 hands the entity's angles straight to AngleVectors and
  uses the resulting right/up as the quad's axes.

  THE ANGLES OF AN ORIENTED SPRITE ARE NOT THE ANGLES IN THE LUMP, and this is
  the single easiest thing in this file to get wrong.  Sprite.cpp:855-863:

      CSpriteOriented::Spawn saves the authored angles, calls CSprite::Spawn --
      which swaps yaw into roll whenever yaw is non-zero and roll is zero
      (Sprite.cpp:219-227, commented "Worldcraft only sets y rotation") -- and
      then puts the SAVED angles back with 180 degrees added to the yaw.

  So the swap is undone and the flip is not, because "ORIENTED sprites forward
  vector points in the players view direction, not the direction out from the
  sprite (gah)" -- Valve's comment, not mine.  Net: authored angles, yaw + 180.
  Get either half wrong and bhop_murder's 208 trees and wall lamps face into
  the walls they are mounted on.
*/
/*
  Intern one (MinDist, MaxDist, OuterMaxDist, backoff) tuple and return its
  index.  Linear, because glowp_n is a handful on every map measured and a map
  that somehow produced 64 distinct sets would spend 64 float compares per
  entity at load and nothing per frame.

  THE BACK-OFF IS CLAMPED UP, NEVER DOWN.  4 units is Source's own constant in
  the software fallback (c_pixel_visibility.cpp:790-791, "trace 4in from
  destination in case the glow is inside some parent object") and GlowProxySize
  defaults to 2, so honouring the key alone would make the trace stricter than
  it is today for two thirds of this library's sprites.  max() of the two keeps
  build 53's behaviour as the floor and lets a map ask for more.
*/
float(float mn, float mx, float outer, float proxy) Glow_ParamSet =
{
	local float i, back;

	back = (proxy > 4) ? proxy : 4;

	for (i = 0; i < glowp_n; i = i + 1)
		if (glowp_min[i] == mn && glowp_max[i] == mx &&
		    glowp_outer[i] == outer && glowp_backoff[i] == back)
			return i;

	if (glowp_n >= GLOWP_MAX)
	{
		glowp_over = glowp_over + 1;
		return 0;               // set 0 is always the plain 4-unit default
	}

	i = glowp_n;
	glowp_min[i]     = mn;
	glowp_max[i]     = mx;
	glowp_outer[i]   = outer;
	glowp_backoff[i] = back;
	glowp_n = glowp_n + 1;
	return i;
};

void(vector org, vector ang, float kind, float mat, float scale,
     vector col, float alpha, float additive) Sprite_Add =
{
	local float i, hw, hh;

	if (spr_n >= SPR_MAX)
	{
		vbsp_spr_over = vbsp_spr_over + 1;
		return;
	}

	if (scale <= 0)
		scale = 1;              // DrawSpriteModel's own default, c_sprite.cpp:53-56

	hw = sprmat_w[mat] * scale * 0.5;
	hh = sprmat_h[mat] * scale * 0.5;
	if (hw <= 0 || hh <= 0)
		return;

	i = spr_n;
	spr_org[i]   = org;
	spr_col[i]   = col;
	spr_alpha[i] = alpha;
	spr_hw[i]    = hw;
	spr_hh[i]    = hh;
	spr_rad[i]   = sqrt(hw * hw + hh * hh);
	spr_mat[i]   = mat;
	spr_kind[i]  = kind;
	spr_add[i]   = additive;
	spr_pset[i]  = spra_pset;
	spr_gskip[i] = world;           // resolved after both walks, Sprite_ResolveSkips

	if (kind == SPRK_ORIENTED)
	{
		makevectors([ang_x, anglemod(ang_y + 180), ang_z]);
		spr_right[i] = v_right;
		spr_up[i]    = v_up;
	}
	else
	{
		spr_right[i] = '0 0 0';
		spr_up[i]    = '0 0 0';
	}

	spr_n = spr_n + 1;
};

/*
===========================================================================
  BUILD 54 -- add one env_lightglow.

  Reported as: "some of the light glow sprites on the flat white brush models
  acting as light are actually horizontally stretched in Source, looks like a
  lens flare almost, can you find that value?"  It is HorizontalGlowSize and
  VerticalGlowSize, and this class is where they live.  surf_tensor2 carries 166
  env_lightglow and 165 of them read 65 wide by 35 tall -- a 1.857:1 stretch,
  which is the lens-flare look exactly.  Until now every one of them was counted
  and thrown away.

  THE SIZES ARE THE RAW KEYS.  C_LightGlowOverlay::CalcSpriteColorAndSize
  (c_lightglow.cpp:19-22) overrides the base class and assigns
  m_flHorzSize/m_flVertSize straight through -- no view-dot multiplier, no
  distance term.  The 70x/150x constants in glow_overlay.cpp:289-315 belong to
  the SUN and this class never reaches them.  (Build 52's essay above
  Sprite_LoadForMap got that right after getting it wrong once; this is the same
  correction, now acted on.)

  ONE-SIDED, and every one of these 166 is.  c_lightglow.cpp:27-34:

      viewDir = normalize(eye - origin)          // FROM the glow TO the eye
      if (m_bOneSided && dot(viewDir, forward) < 0)  -> colour is black

  and m_vecDirection is AngleVectors(angles).forward with no adjustment
  (:189-192) -- NOT the yaw+180 dance CSpriteOriented needs, which is a trap
  worth naming because the sibling case three functions up does need it.  A port
  that skips the test draws all 166 of them through the ceilings they are
  mounted in.

  Stored in the sprite arrays, so Sprite_Glare's round-robin trace, its 50 ms
  ramp and the trace budget all cover glows with no extra machinery.  spr_mat is
  -1 because a glow is not drawn by the material-major loop: they all share one
  hardcoded material and are drawn in one batch of their own, the way the beams
  are.  A material index of -1 can never equal a loop counter that starts at 0,
  so the exclusion needs no test.
===========================================================================
*/
void(vector org, vector ang, float hw, float hh, vector col, float alpha,
     float pset, float onesided) Glow_Add =
{
	local float i;

	if (spr_n >= SPR_MAX)
	{
		vbsp_spr_over = vbsp_spr_over + 1;
		return;
	}

	// A glow with no size is not a glow.  The FGD defaults both to 30, but the
	// key is optional and 1.1% of the library omits it.
	if (hw <= 0 || hh <= 0)
	{
		vbsp_glow_off = vbsp_glow_off + 1;
		return;
	}

	i = spr_n;
	spr_org[i]   = org;
	spr_col[i]   = col;
	spr_alpha[i] = alpha;
	spr_hw[i]    = hw;
	spr_hh[i]    = hh;
	/*
	  Cull radius ZERO, and deliberately.  The quad is drawn 100 units from the
	  eye, not at spr_org, so its world extent there says nothing about what it
	  covers on screen; spr_org is only the point whose distance and visibility
	  are being asked about.  A radius here would widen the behind-camera test
	  into keeping glows that are genuinely behind the viewer.
	*/
	spr_rad[i]   = 0;
	spr_mat[i]   = -1;              // see the note above: never matched by the loop
	spr_kind[i]  = SPRK_GLOW;
	/*
	  SPRA_ADD, not SPRA_GLOW, and the difference is the whole of build 58 for
	  this class: an env_lightglow has no renderamt to apply twice and Source
	  gives it no inverse-square fade (c_lightglow.cpp:19-48 overrides
	  CalcSpriteColorAndSize and never calls GlowBlend). Its only missing term
	  was the occlusion FRACTION, which lives in spr_gvis and needs nothing here.
	*/
	spr_add[i]   = SPRA_ADD;
	spr_pset[i]  = pset;
	spr_gskip[i] = world;

	/*
	  The forward vector doubles as the one-sided flag: makevectors can never
	  return a zero forward, so '0 0 0' unambiguously means "not one-sided" and
	  no second array is needed.
	*/
	if (onesided)
	{
		makevectors(ang);
		spr_right[i] = v_forward;
	}
	else
		spr_right[i] = '0 0 0';
	spr_up[i] = '0 0 0';

	spr_n = spr_n + 1;
	vbsp_glow_n = vbsp_glow_n + 1;
};

/*
  Add one light shaft.

  Source builds this as a CBeam from the entity to a traced endpoint, and every
  number below is read off point_spotlight.cpp rather than chosen:

    :341-347  the endpoint is a trace of length 2*spotlightlength, or the full
              2x distance when IgnoreSolid is set.  The DOUBLE is not a typo --
              SpotlightCurrentPos traces "2 * m_flSpotlightMaxLength" so a beam
              that misses its intended surface still lands somewhere.
    :363      BeamInit(name, goalwidth) sets START width to spotlightwidth...
    :210-212  ...and the END width to goalwidth * (reached / intended), so a
              beam that stops short CONVERGES rather than staying parallel.
              Valve's comment there says "keep beam width constant", which
              describes the intent at full length, not the short case.
    :371      FBEAM_SHADEOUT with fade length equal to the reach, which
              beamdraw.cpp:359 turns into brightness = 1 - fraction: full at
              the source, zero at the far end.

  BUILD 53: this trace now sees brush entities too.  It used to say "the trace
  is CSQC's, so it sees the world and not brush entities, where Source uses
  MASK_SOLID_BRUSHONLY and sees both -- a spotlight aimed at a door or a moving
  platform therefore reaches past it to the wall behind".  The client's own
  copies (Sprite_AddOccluder) close that, and this call gets the fix for free
  because it was always the same csqc_world trace.

  ORDERING IS WHY THE OCCLUDERS GET THEIR OWN WALK.  A spotlight is traced ONCE,
  as it is read, so it can only be traced against brush entities that already
  exist -- and a func_brush declared later in the lump would not.  That is the
  whole reason Sprite_LoadOccluders is a separate pass over the lump instead of
  a branch inside the main one: a second getentitytoken walk costs one pass over
  ~2000 entities at map load, and buying a complete occluder set for that is not
  a close call.
*/
void(vector org, vector ang, float len, float wid, float ignoresolid, vector col) Beam_Add =
{
	local float  i, curlen;
	local vector dir, endp;

	if (beam_n >= BEAM_MAX)
	{
		vbsp_spr_over = vbsp_spr_over + 1;
		return;
	}

	// Source's own repair of a nonsense key, point_spotlight.cpp:213-221.
	if (len <= 0)
		len = 500;
	if (wid <= 0)
		wid = 10;

	makevectors(ang);
	dir = v_forward;

	endp = org + dir * (2 * len);
	if (!ignoresolid)
	{
		traceline(org, endp, MOVE_NOMONSTERS, world);
		if (trace_fraction < 1)
			endp = trace_endpos;
	}

	curlen = vlen(endp - org);
	if (curlen < 1)
		return;

	i = beam_n;
	beam_org[i] = org;
	beam_end[i] = endp;
	beam_col[i] = col;
	beam_w0[i]  = wid;
	beam_w1[i]  = wid * (curlen / len);
	beam_rad[i] = curlen * 0.5 + wid;
	beam_n = beam_n + 1;
};

/*
===========================================================================
  BUILD 53 -- the client's own copies of the map's brush entities, so that a
  trace can hit them.

  WHICH BRUSH ENTITIES OCCLUDE, and this is a measured list rather than a taste
  judgement.  Every `model "*N"` entity in all 1310 shipped maps, by class:

      trigger_teleport   115891    func_brush        35258    func_illusionary 21231
      trigger_multiple    26359    func_door          3485    func_dustmotes    4999
      trigger_push         4891    func_rotating      2937    func_lod          1960
      trigger_hurt         1446    func_button        2762    func_movelinear   1563
      ... 152k triggers in all   ... plus breakable, wall, physbox, tracktrain,
                                     conveyor, door_rotating, wall_toggle, ...

  So 64% of the population is triggers, which are invisible volumes and must
  never occlude anything.  The rule below is therefore a DENYLIST with a solid
  catch-all, which is the same shape sv_entities.qc:2624 settled on server-side:
  an unrecognised brush entity is geometry until something says otherwise.

  Three tiers, because "solid" and "opaque" are not the same question:

    0  never occludes -- triggers, effect volumes (dustmotes, embers, smoke,
       precipitation, bubbles), area portals, ladders, gameplay volumes, and
       INVISIBLE CLIP BRUSHES.  func_clip_vphysics is the interesting one: it is
       genuinely solid and would pass any solidity test, and it is also
       completely invisible, so letting it occlude would hide glows behind
       nothing at all.
    1  solid geometry.  This is Source's own rule for the glow it TRACES:
       glow_overlay.cpp:236-237 traces with CONTENTS_SOLID.
    2  drawn but not solid -- func_illusionary (21,231 of them), and every
       func_brush declaring "solidity 1".  THE DEFAULT, and the map that
       prompted this is why: 145 of surf_tensor2's 160 func_brush are
       solidity 1, so mode 1 keeps 16 of 622 brush entities and measurably
       changed nothing (232 of 240 hidden either way).  Source's CONTENTS_SOLID
       trace does not hit these, but that trace is only used for the SUN; a
       world glow is occluded by a hardware pixel query (glow_overlay.cpp:
       247-250), which sees anything that draws.  So 2 is the closer answer as
       well as the useful one.

  WHAT THIS DOES NOT DO.  The copies are frozen at their spawn position, the
  same trade sv_entities.qc's brush entities already make ("Spawn state only, by
  design" at :3772).  A door that opens still occludes where it was closed.  On
  a surf map the things that move are decoration and the things you surf are
  placed at spawn, so this is the right way round; it is stated rather than
  hidden because a glow behind a moving platform is exactly the case that will
  look wrong to whoever finds it.
===========================================================================
*/
float(string cn) Sprite_OccluderTier =
{
	// Triggers: 152,000 of the library's 238,420 brush entities, and not one of
	// them is drawn.  Prefix-tested rather than listed because the family keeps
	// growing -- Momentum alone adds nine trigger_momentum_* classes.
	if (substring(cn, 0, 8) == "trigger_")
		return 0;
	// Momentum's zone brushes are triggers under another name (zone_timer_start,
	// zone_allowbhop, ...): 184 across 26 maps.
	if (substring(cn, 0, 5) == "zone_")
		return 0;

	// Effect volumes.  Drawn, in the sense that they emit particles, but they
	// are not surfaces and nothing about them stops light.
	if (cn == "func_dustmotes"  || cn == "func_dustcloud" ||
	    cn == "func_smokevolume" || cn == "func_precipitation" ||
	    cn == "env_embers"      || cn == "env_bubbles" ||
	    cn == "color_correction_volume")
		return 0;

	// Invisible by construction: clips, area portals, occluder hints, ladders,
	// and the gameplay volumes that are brushes only because they need a shape.
	if (cn == "func_clip_vphysics" || cn == "func_occluder" ||
	    cn == "func_areaportal"    || cn == "func_areaportalwindow" ||
	    cn == "func_ladder"        || cn == "func_simpleladder" ||
	    cn == "func_buyzone"       || cn == "func_bomb_target" ||
	    cn == "func_respawnroom"   || cn == "func_respawnroomvisualizer" ||
	    cn == "func_nobuild"       || cn == "func_nogrenades" ||
	    cn == "func_regenerate"    || cn == "func_bhop" ||
	    cn == "func_slide"         || cn == "func_portal_bumper")
		return 0;

	// Water is a volume you can see through; a glow under it is dimmed, not hidden.
	if (cn == "func_water" || cn == "func_water_analog")
		return 0;

	// Drawn, never solid.  Source's CONTENTS_SOLID trace misses these; its pixel
	// query does not.  See the three-tier note above.
	if (cn == "func_illusionary")
		return 2;

	return 1;
};

/*
  Drop last map's copies.  Held by a field rather than an array, so the list
  costs nothing when it is empty -- which it is on the 759 maps with no brush
  entity worth instantiating.

  The NEXT one is found before the current one is removed: findfloat walks the
  edict table from `start`, and handing it an edict that has just been freed is
  how you get a walk that stops early and leaves half the copies behind.
*/
void() Sprite_FreeOccluders =
{
	local entity e, nxt;

	e = findfloat(world, spr_occluder, TRUE);
	while (e)
	{
		nxt = findfloat(e, spr_occluder, TRUE);
		remove(e);
		e = nxt;
	}
	spr_occ_n = 0;
};

/*
  One brush entity.  `mdl` is "*N"; `org` is the entity's own origin key, which
  is almost always zero because VBSP bakes brush geometry in world coordinates
  and only subtracts an origin for the things that rotate.

  SOLID BEFORE SETMODEL, because setmodel links the entity and World_LinkEdict
  reads .solid to decide which of the areagrid's lists it belongs in -- the same
  ordering constraint sv_entities.qc:2546 documents for the server's copies.
*/
void(string mdl, vector org) Sprite_AddOccluder =
{
	local entity e;

	if (spr_occ_n >= OCC_MAX)
	{
		spr_occ_over = spr_occ_over + 1;
		return;
	}

	e = spawn();
	e.spr_occluder = TRUE;
	e.solid        = SOLID_BSP;
	e.movetype     = MOVETYPE_NONE;
	setmodel(e, mdl);
	setorigin(e, org);

	/*
	  Never drawn.  The server already draws this geometry; a second copy would
	  z-fight with it everywhere.  Clearing modelindex would take the collision
	  hull away with it (the mistake sv_entities.qc:2915 records), so the entity
	  keeps its model and is hidden by the drawmask instead -- CSQC entities are
	  only drawn by an explicit addentities/addentity call, and nothing here
	  makes one.
	*/
	e.drawmask = 0;

	spr_occ_n = spr_occ_n + 1;
};

/*
  The occluder pass.  Its own walk of the entity lump, ahead of the sprite walk,
  so that Beam_Add's one-shot traces see every brush entity and not merely the
  ones declared above them -- see the ordering note on Beam_Add.
*/
void() Sprite_LoadOccluders =
{
	local string tok, key, cn, model;
	local vector org;
	local float  want, tier, solidity, startdisabled, hassolidity;

	Sprite_FreeOccluders();
	spr_occ_seen = spr_occ_over = 0;

	// 0 off, 1 solid geometry only (Source's own trace rule), 2 also the
	// drawn-but-not-solid ones.  Read once, not once per entity.
	want = cvar("vbsp_glare_brush");
	if (!want)
		return;

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
			// Both spellings of each, the way sv_entities.qc's SV_Key2 reads
			// them: the library writes "Solidity"/"solidity" and
			// "StartDisabled"/"startdisabled" interchangeably, and reading only
			// one of each drops half the maps.
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

		// Counted whether or not it is instantiated, so the status line can say
		// how many were DECLINED rather than only how many were kept.
		spr_occ_seen = spr_occ_seen + 1;

		tier = Sprite_OccluderTier(cn);
		if (tier == 0 || tier > want)
			continue;

		/*
		  func_brush is 35,258 of the library's brush entities -- 15% of all of
		  them, and by far the largest class that is not a trigger -- and it is
		  the one class whose solidity is a KEYVALUE rather than a property of
		  the classname:

		      solidity 0  toggle with Enable/Disable -> follow StartDisabled
		      solidity 1  never solid
		      solidity 2  always solid

		  Read exactly as sv_entities.qc's func_brush reads it (:3820-3830),
		  because the two disagreeing would be worse than either being wrong:
		  the player would walk into something the glow says is not there, or
		  the reverse.  StartDisabled also means INVISIBLE and not merely
		  intangible (:3802-3804), so a disabled brush is skipped at both tiers.
		*/
		if (cn == "func_brush")
		{
			/*
			  StartDisabled means INVISIBLE as well as intangible
			  (:3802-3804), so a disabled brush is not an occluder at any
			  tier and is dropped before the tier test.
			*/
			if ((!hassolidity || solidity == 0) && startdisabled)
				continue;

			/*
			  MEASURED ON THE MAP THAT PROMPTED THIS, and it moved the
			  default.  surf_tensor2 has 160 func_brush and 145 of them
			  declare `solidity 1` -- never solid.  They are not junk: they
			  are the decorative geometry you can walk through and cannot see
			  through, and the spawn portals are among them (the combine
			  shield at -11776 -10816 13744 is func_brush *19, solidity 1).

			  So "solid" alone would have kept 16 of 622 brush entities on
			  this map and changed nothing on screen, which is what the first
			  run measured: 232 of 240 glares hidden with the occluders in,
			  and 232 of 240 with them out.  A non-solid-but-drawn func_brush
			  is the func_illusionary case wearing a different classname, and
			  it belongs in the same tier.
			*/
			if (hassolidity && solidity == 1 && want < 2)
				continue;
		}

		Sprite_AddOccluder(model, org);
	}
};

/*
===========================================================================
  BUILD 54 -- which occluder is each glow buried in.

  Runs after BOTH walks, because it needs the occluders to exist and the sprites
  to have been read.  The answer is a load-time constant: neither a brush entity
  nor a sprite moves.

  OCCLUDERS IN THE OUTER LOOP, and that is not a stylistic choice.  findfloat
  scans the edict table on every call, so sprites-outer would call it spr_n
  times and cost spr_n * edicts * occluders -- on the library's worst map (862
  sprites, 768 occluders) that is hundreds of millions of operations at load.
  Occluders-outer calls findfloat once per occluder and leaves an inner loop of
  plain float compares.

  THE SMALLEST CONTAINER WINS.  A glow can sit inside a small light fitting that
  is itself inside a large decorative shell, and the thing it belongs to is the
  tight one; skipping the shell as well would punch a hole in the occlusion the
  player can see.  spr_gskip_multi counts the overlaps so a map where one skip
  is not enough says so rather than quietly under-fixing.

  Only additive sprites are considered, because only they are ever traced
  (Sprite_Glare gates on spr_add).  A non-additive billboard is depth-tested
  world geometry and has no occlusion trace to exempt.
===========================================================================
*/
void() Sprite_ResolveSkips =
{
	local entity e, p;
	local float  i, v, best;
	local vector mn, mx, o;

	spr_gskip_n = spr_gskip_multi = 0;

	for (i = 0; i < spr_n; i = i + 1)
		spr_gskip[i] = world;

	if (!spr_occ_n || !spr_n)
		return;

	e = findfloat(world, spr_occluder, TRUE);
	while (e)
	{
		mn = e.absmin;
		mx = e.absmax;
		v  = (mx_x - mn_x) * (mx_y - mn_y) * (mx_z - mn_z);

		for (i = 0; i < spr_n; i = i + 1)
		{
			if (!spr_add[i])
				continue;

			o = spr_org[i];
			if (o_x < mn_x || o_x > mx_x) continue;
			if (o_y < mn_y || o_y > mx_y) continue;
			if (o_z < mn_z || o_z > mx_z) continue;

			/*
			  The incumbent's volume is recomputed rather than cached in a
			  parallel SPR_MAX array: it costs three subtractions on the rare
			  overlap and saves 8x SPR_MAX*4 bytes of progs for a number that is
			  zero on almost every sprite.
			*/
			p = spr_gskip[i];
			if (p != world)
			{
				spr_gskip_multi = spr_gskip_multi + 1;
				best = (p.absmax_x - p.absmin_x) *
				       (p.absmax_y - p.absmin_y) *
				       (p.absmax_z - p.absmin_z);
				if (v >= best)
					continue;               // the one we already have is tighter
			}
			else
				spr_gskip_n = spr_gskip_n + 1;

			spr_gskip[i] = e;
		}

		e = findfloat(e, spr_occluder, TRUE);
	}
};

/*
===========================================================================
  Reading the entity lump

  WHY env_spritetrail IS COUNTED AND NOT DRAWN.  It is the third largest class
  in this family -- 2773 instances across 132 maps -- and it is not a sprite at
  a place, it is a RIBBON THROUGH A PATH.  95.1% of them carry a `parentname`,
  and the parents are named `spritetrial_rotate_end2`, `knife_spin`,
  `doorrottimer`, `rotating3`: brush entities that turn.  The trail is the
  streak the sprite leaves as its parent swings it around, and a trail whose
  points all coincide draws nothing in Source either.  So the honest options
  were a stationary blob where a moving streak belongs, or this line in the
  status print.  Drawing it would need server-side parenting and the parent's
  motion replicated to the client, which is a different feature.

  WHY env_lightglow IS COUNTED AND NOT DRAWN.  This one is not in the plan at
  all -- the plan's census listed nine classes and this was not among them,
  which was an omission, because at 3393 instances across 137 maps it is bigger
  than env_spritetrail.  It is declined for a better reason than size:
  glow_overlay.cpp:330-343 (CalcBasis) places it at a FIXED 100 units in front
  of the camera along the direction to the glow, so its apparent size does not
  change with distance, and it is gated on an occlusion query rather than on the
  depth buffer (:205-252).  That is a lens-flare renderer, not a world
  billboard.  The keys are all there (HorizontalGlowSize, VerticalGlowSize,
  MinDist, MaxDist, OuterMaxDist on 98.9% of them), so it is buildable; it is
  simply a second renderer.  Sprite_Glare below is that renderer.

  CORRECTION, BUILD 52.  This paragraph used to add "scales it by 70x to 150x
  depending on the view dot product (:288-308)", and that is WRONG -- it belongs
  to the SUN.  Those constants live in the base CGlowOverlay::CalcSpriteColorAndSize
  (glow_overlay.cpp:289-315), and C_LightGlowOverlay OVERRIDES that method:
  c_lightglow.cpp:19-22 sets the size straight from m_flHorzSize/m_flVertSize and
  never touches flDot at all.  Only CalcBasis' 100-unit placement is inherited.
  The claim was checked against the real source rather than assumed, and the
  practical effect is that a glare is EASIER than this note implied: the sizes
  are the raw keys, not the keys times a view-dependent factor.
===========================================================================
*/
void() Sprite_LoadForMap =
{
	local string tok, key, cn, map, model, srendercolor;
	local vector org, ang, col;
	local float  scale, renderamt, rendermode, spawnflags, framerate, renderfx;
	local float  splen, spwid, ignoresolid;
	local float  opened, wantspr, wantbeam, mat, alpha, additive, named;
	local float  glowh, glowv, gmin, gmax, gouter, gproxy, wantglow;

	map = serverkey("map");
	if (map == "")
		return;

	wantspr  = cvar("vbsp_sprites");
	wantbeam = cvar("vbsp_spotlights");
	wantglow = cvar("vbsp_lightglow");

	Sprite_FreeMaterials();
	/*
	  BUILD 53.  FIRST, and its own walk of the lump.  Beam_Add traces each
	  spotlight once as it is read, so every brush entity has to exist before
	  the sprite walk starts or a beam will shoot through a door that is merely
	  declared further down the file.
	*/
	Sprite_LoadOccluders();
	spr_n = beam_n = 0;

	/*
	  BUILD 53: forget the last map's glare answers.

	  Build 52 left spr_gvis/spr_glare/spr_gtraced untouched across a load, and
	  the arrays are indexed by POSITION -- so for the first frames of a new map
	  sprite 7 wore whatever sprite 7 of the previous map had decided, including
	  spr_gtraced TRUE, which is the flag that says "this answer is real".  The
	  round-robin corrects it within a few frames and the ramp hides most of it,
	  which is exactly why it survived: it is a wrong first frame, not a
	  persistent artefact.  It stops being invisible with vbsp_sprite_debug 2,
	  which reloads in place and would otherwise carry every stale answer
	  straight into the arm that is meant to be measuring the new one.
	*/
	for (mat = 0; mat < SPR_MAX; mat = mat + 1)
	{
		spr_gvis[mat] = 0;
		spr_glare[mat] = 0;
		spr_gtraced[mat] = FALSE;
		/*
		  BUILD 54.  Cleared here and not merely in Sprite_ResolveSkips, because
		  Sprite_LoadOccluders has already removed the previous map's occluders a
		  few lines above and spawn() recycles edicts: a stale handle would name
		  a real entity that happens to be the wrong one.  Nothing traces between
		  those two points, so this is belt and braces -- which is what it should
		  be, since the failure would be a glow silently ignoring a wall.
		*/
		spr_gskip[mat] = world;
	}
	spr_gnext = 0;
	/*
	  BUILD 61.  The carried fraction is per-map: spr_n has just changed, so a
	  remainder accumulated against the old map's glare count would spend the
	  new map's first frames at the wrong rate.  Cleared here rather than left
	  to decay because this also runs on vbsp_sprite_debug 2, and an A/B arm
	  must not inherit the previous arm's debt.
	*/
	spr_gvacc = 0;
	glowp_n = glowp_over = 0;
	vbsp_spr_seen = vbsp_spr_off = vbsp_spr_nomat = vbsp_spr_over = 0;
	vbsp_beam_seen = vbsp_beam_off = 0;
	vbsp_trail_seen = 0;
	vbsp_glow_seen = vbsp_glow_off = vbsp_glow_n = 0;
	opened = FALSE;

	/*
	  Set 0 is reserved as the plain default -- no fade ramp, Source's own 4-unit
	  back-off -- so that Glow_ParamSet's overflow return of 0 is a sane answer
	  rather than whichever set happened to be interned first.
	*/
	Glow_ParamSet(0, 0, 0, 0);

	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		opened = TRUE;

		cn = model = srendercolor = "";
		org = ang = '0 0 0';
		scale = framerate = 0;
		renderamt = 255;
		rendermode = 0;
		renderfx = 0;
		spawnflags = 0;
		splen = spwid = ignoresolid = 0;
		named = FALSE;
		// BUILD 54.  The FGD's own defaults for env_lightglow (base.fgd:1198),
		// so a map that omits a key gets what Hammer showed its author.
		glowh = glowv = 30;
		gmin  = 500;
		gmax  = 2000;
		gouter = 0;
		gproxy = 2;

		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if      (key == "classname")   cn = tok;
			else if (key == "model")       model = tok;
			else if (key == "origin")      org = Sprite_ParseVec(tok);
			else if (key == "angles")      ang = Sprite_ParseVec(tok);
			else if (key == "scale")       scale = stof(tok);
			else if (key == "renderamt")   renderamt = stof(tok);
			else if (key == "rendermode")  rendermode = stof(tok);
			// BUILD 58.  Only two values change the arithmetic and only for the
			// two glow rendermodes; see SPRA_* and the draw.  Note 26 is NOT a
			// valid RenderFx_t -- kRenderFxMax is 25 -- and 166 of surf_tensor2's
			// 263 sprites carry it.  Source falls to `default:` there
			// (c_baseentity.cpp:3502-3509), so 26 behaves exactly as 0 and must
			// not be "fixed" into meaning something.
			else if (key == "renderfx")    renderfx = stof(tok);
			else if (key == "rendercolor") srendercolor = tok;
			else if (key == "spawnflags")  spawnflags = stof(tok);
			else if (key == "framerate")   framerate = stof(tok);
			else if (key == "targetname")  named = (tok != "");
			// The library writes both spellings of each of these three, so both
			// are read: 1.9% of point_spotlights write "hdrcolorscale" and 0.5%
			// write "ignoresolid" against the FGD's capitalised forms.
			else if (key == "spotlightlength" || key == "SpotlightLength") splen = stof(tok);
			else if (key == "spotlightwidth"  || key == "SpotlightWidth")  spwid = stof(tok);
			else if (key == "IgnoreSolid"     || key == "ignoresolid")     ignoresolid = stof(tok);
			/*
			  BUILD 54.  Both spellings again, for the reason the three above
			  give: the library is inconsistent and reading one form silently
			  drops the maps that wrote the other.  GlowProxySize is on 263 of
			  263 env_sprite on surf_tensor2 as well as on every env_lightglow,
			  which is why it is read outside the class test.
			*/
			else if (key == "GlowProxySize"      || key == "glowproxysize")      gproxy = stof(tok);
			else if (key == "HorizontalGlowSize" || key == "horizontalglowsize") glowh  = stof(tok);
			else if (key == "VerticalGlowSize"   || key == "verticalglowsize")   glowv  = stof(tok);
			else if (key == "MinDist"            || key == "mindist")            gmin   = stof(tok);
			else if (key == "MaxDist"            || key == "maxdist")            gmax   = stof(tok);
			else if (key == "OuterMaxDist"       || key == "outermaxdist")       gouter = stof(tok);
		}

		col = Sprite_ParseColor(srendercolor);
		if (srendercolor == "")
			col = '1 1 1';

		if (cn == "env_sprite" || cn == "env_sprite_oriented" || cn == "env_glow")
		{
			vbsp_spr_seen = vbsp_spr_seen + 1;
			if (!wantspr)
				continue;

			/*
			  The start-on gate, and it is NOT "spawnflags & 1".

			  Sprite.cpp:208-216 turns a sprite off only if it has a targetname
			  AND lacks the flag -- an UNNAMED sprite is on whatever its
			  spawnflags say.  That distinction decides thousands of sprites:
			  49.2% of the library writes spawnflags 1 and 50.8% writes 0, so
			  reading the flag alone would blank half of every map; only 8.7%
			  carry a targetname, so the real number turned off is small.
			*/
			if (named && !(spawnflags & 1))
			{
				vbsp_spr_off = vbsp_spr_off + 1;
				continue;
			}

			// kRenderNone.  Source draws nothing; neither do we.
			if (rendermode == 10)
			{
				vbsp_spr_off = vbsp_spr_off + 1;
				continue;
			}

			if (model == "")
				continue;
			mat = Sprite_Material(model);
			if (mat < 0)
			{
				vbsp_spr_nomat = vbsp_spr_nomat + 1;
				continue;
			}

			alpha = renderamt * (1 / 255);
			if (alpha <= 0)
				alpha = 1;              // no renderamt means opaque, not invisible
			if (alpha > 1)
				alpha = 1;

			/*
			  Which rendermodes are additive: 3 kRenderGlow, 5 kRenderTransAdd,
			  9 kRenderWorldGlow.  Together they are 82.5% of the library's
			  sprites, which is what a light glow is.  Everything else keeps the
			  VMT's own blendfunc, because Source picks a per-rendermode MATERIAL
			  VARIANT (c_sprite.cpp:65) and there is no equivalent here -- the
			  material's own opinion is the closest available answer.
			*/
			additive = SPRA_NONE;
			if (rendermode == 3 || rendermode == 9)
			{
				// The two that go through GlowBlend, hence the two Source dims
				// twice.  BUILD 58; before it all three were one boolean.
				additive = SPRA_GLOW;
				if (renderfx == 14)
					additive = SPRA_NODISS;         // kRenderFxNoDissipation
				else if (renderfx == 3)
					additive = SPRA_PULSE;          // kRenderFxPulseSlowWide
			}
			else if (rendermode == 5)
				additive = SPRA_ADD;                // kRenderTransAdd

			// BUILD 54.  A sprite has no fade ramp, so only the back-off half of
			// the set is meaningful; the three zeros keep it one table.
			spra_pset = Glow_ParamSet(0, 0, 0, gproxy);

			Sprite_Add(org, ang,
			           (cn == "env_sprite_oriented") ? SPRK_ORIENTED : SPRK_BILLBOARD,
			           mat, scale, col, alpha, additive);
		}
		else if (cn == "point_spotlight" || cn == "beam_spotlight")
		{
			vbsp_beam_seen = vbsp_beam_seen + 1;
			if (!wantbeam)
				continue;

			/*
			  SF_SPOTLIGHT_START_LIGHT_ON.  Unlike env_sprite above this one IS
			  a plain flag test: point_spotlight.cpp:182 sets m_bSpotlightOn from
			  the flag alone, and Activate (:262) only builds the beam if it is
			  set.  3.3% of the library -- spawnflags 0 and 2 -- starts dark.
			*/
			if (!(spawnflags & 1))
			{
				vbsp_beam_off = vbsp_beam_off + 1;
				continue;
			}

			Beam_Add(org, ang, splen, spwid, ignoresolid, col);
		}
		else if (cn == "env_spritetrail")
			vbsp_trail_seen = vbsp_trail_seen + 1;
		/*
		  BUILD 54.  env_lightglow, drawn at last.  3393 instances across 137
		  maps that have never put a pixel on the screen.

		  NO start-on gate and no rendermode: the class has neither.  Its
		  datadesc (lightglow.cpp:67-78) is the six sizes and distances, a colour
		  input, and one spawnflag -- there is no targetname gate of the kind
		  env_sprite needs, and CLightGlow has no render mode at all.  Its only
		  runtime gate is a PVS poll every one to three seconds
		  (c_lightglow.cpp:202-215), which the occlusion trace here subsumes.

		  Alpha is 1 because Source draws the quad at a fixed alpha and puts the
		  whole fade in the COLOUR (vColor * fade * obstruction, :48; the mesh
		  builder writes Color4f(..., 1) at glow_overlay.cpp:420).  Under this
		  engine's additive blend -- SRC_ALPHA, ONE (gl_backend.c:3264-3266) --
		  scaling the colour and scaling the alpha are the same operation, so the
		  fade is applied through spr_alpha in the draw where the existing
		  obstruction ramp already lives, and the two agree.
		*/
		else if (cn == "env_lightglow")
		{
			vbsp_glow_seen = vbsp_glow_seen + 1;
			if (!wantglow)
			{
				vbsp_glow_off = vbsp_glow_off + 1;
				continue;
			}
			Glow_Add(org, ang, glowh, glowv, col, 1,
			         Glow_ParamSet(gmin, gmax, gouter, gproxy),
			         spawnflags & 1);        // SF_LIGHTGLOW_DIRECTIONAL
		}
	}

	// Same guard the decals use: serverkey("map") can lead the entity data by a
	// frame, and latching before the lump was readable means never looking again.
	if (!opened)
		return;
	vbsp_spr_map = map;

	// BUILD 54.  Needs both walks finished: the occluders exist and the sprites
	// have been read.  Neither ever moves, so the answer is a load-time constant.
	Sprite_ResolveSkips();

	/*
	  One line per family, and every skipped entity is accounted for by name.

	  The four sprite numbers are made to sum to the total for the same reason
	  the overlay line's do: the misses are unrelated things with unrelated
	  fixes -- one we decline because Source declines it too, one is missing
	  content, one is a cap that would need raising -- and a bare "N of M" would
	  hide which.
	*/
	/*
	  BUILD 54.  spr_n IS NOT THE SPRITE COUNT ANY MORE -- env_lightglow shares
	  these arrays, so it counts sprites AND glows.  Printing it against
	  vbsp_spr_seen produced "sprites: 429 of 263 drawn" on surf_tensor2, a line
	  that reads as a bug in the parser and is really 263 sprites plus 166 glows.
	  The glows have their own line below; subtract them here.
	*/
	if (vbsp_spr_seen)
	{
		if (!wantspr)
			print(sprintf("sprites: %g found, none drawn (vbsp_sprites 0)\n", vbsp_spr_seen));
		else if (vbsp_spr_off + vbsp_spr_nomat + vbsp_spr_over)
			print(sprintf("sprites: %g of %g drawn (%g off, %g no material, %g over cap)\n",
			              spr_n - vbsp_glow_n, vbsp_spr_seen, vbsp_spr_off, vbsp_spr_nomat, vbsp_spr_over));
		else
			print(sprintf("sprites: %g of %g drawn\n", spr_n - vbsp_glow_n, vbsp_spr_seen));
	}

	if (vbsp_beam_seen)
	{
		if (!wantbeam)
			print(sprintf("spotlights: %g found, none drawn (vbsp_spotlights 0)\n", vbsp_beam_seen));
		else if (vbsp_beam_off)
			print(sprintf("spotlights: %g of %g drawn (%g start off)\n",
			              beam_n, vbsp_beam_seen, vbsp_beam_off));
		else
			print(sprintf("spotlights: %g of %g drawn\n", beam_n, vbsp_beam_seen));
	}

	/*
	  BUILD 53.  dprint, not print: this is a diagnostic about how a trace will
	  behave and not a fact about the map, and the two lines above are already
	  the ones a player reads.  The DECLINED count is printed beside the kept
	  one because the interesting failure is "the wall you expected is in the
	  declined pile", and a bare "161 occluders" cannot show that.
	*/
	if (spr_occ_seen)
		dprint(sprintf("sprite occluders: %g of %g brush entities (%g declined, %g over cap, mode %g)\n",
		               spr_occ_n, spr_occ_seen, spr_occ_seen - spr_occ_n - spr_occ_over,
		               spr_occ_over, cvar("vbsp_glare_brush")));

	/*
	  BUILD 54.  How many glows are buried in the brush they light, which is the
	  number the "some of them are placed inside of the portal and now don't
	  render" report is about.  Printed even when it is zero on a map with
	  occluders, because zero is itself the interesting answer there: it means
	  either the map does not do this or the containment test is not finding it,
	  and those want opposite responses.
	*/
	if (spr_occ_n)
		dprint(sprintf("sprite glare skips: %g glows inside an occluder (%g of them inside more than one)\n",
		               spr_gskip_n, spr_gskip_multi));

	if (vbsp_glow_seen)
	{
		if (!wantglow)
			print(sprintf("lightglows: %g found, none drawn (vbsp_lightglow 0)\n", vbsp_glow_seen));
		else if (vbsp_glow_off)
			print(sprintf("lightglows: %g of %g drawn (%g skipped)\n",
			              vbsp_glow_n, vbsp_glow_seen, vbsp_glow_off));
		else
			print(sprintf("lightglows: %g of %g drawn\n", vbsp_glow_n, vbsp_glow_seen));
	}

	if (glowp_over)
		dprint(sprintf("sprites: %g glow parameter sets over GLOWP_MAX -- some fades will be wrong\n",
		               glowp_over));

	// Declined, not forgotten.  env_lightglow is off this list as of build 54;
	// env_spritetrail stays, and the essay above says why it is a different
	// renderer rather than a missing branch.
	if (vbsp_trail_seen)
		dprint(sprintf("sprites: declined %g env_spritetrail (needs parent motion)\n",
		               vbsp_trail_seen));
};

/*
===========================================================================
  Drawing

  Runs beside Zone_Draw, before renderscene, for the same reason: R_BeginPolygon
  queues into the scene rather than over it, so a sprite behind a wall is
  correctly hidden by the wall.
===========================================================================
*/
/*
  a b c d are top-left, top-right, bottom-right, bottom-left.

  T RUNS DOWNWARD, and getting that backwards is invisible on exactly the
  materials you would test with.  Source's own quad (c_sprite.cpp:110-131) pairs
  the TOP two corners with flMinV and the bottom two with flMaxV, so v=0 is the
  top of the image -- the ordinary top-left texture origin.  Nearly every sprite
  in the library is a radially symmetric glow, which looks identical either way;
  kz_anubis's timer digits and bhop_murder's trees do not.
*/
void(vector a, vector b, vector c, vector d, string mat, float flags,
     vector col, float alpha) Sprite_Quad =
{
	R_BeginPolygon(mat, flags);
	R_PolygonVertex(a, '0 0 0', col, alpha);
	R_PolygonVertex(b, '1 0 0', col, alpha);
	R_PolygonVertex(c, '1 1 0', col, alpha);
	R_PolygonVertex(d, '0 1 0', col, alpha);
	R_EndPolygon();
};

/*
===========================================================================
  Sprite_Glare -- the light glows, drawn the way Source draws them.
  BUILD 52.  Reported as: "the light sprites simply rotate towards the camera
  and get cut by the world geometry."  Both halves of that are true and both are
  wrong, and they are the same bug: a glare is a LENS effect, not a surface.

  WHAT SOURCE ACTUALLY DOES (read, not assumed --
  game/client/glow_overlay.cpp and c_lightglow.cpp in the public Momentum tree):

    - the quad is drawn with sprites/light_glow02_add_noz (:397).  The _noz is
      the point: NO DEPTH TEST.  It is never clipped by the world.
    - visibility is a TRACE to the glow's centre, not the depth buffer
      (:236-250), backed off 4 units toward the camera so the trace does not
      hit the lamp the glow is sitting inside (c_pixel_visibility.cpp:787-802).
    - the result does not switch, it RAMPS:
          scale +/-= frametime / cl_sun_decay_rate,  clamped 0..1
      with cl_sun_decay_rate 0.05 (:59, :262, :274) -- a 50ms fade either way,
      framerate-independent.  Drawing is skipped outright at 0 (:365).
    - final colour is spriteColour * distanceFade * obstructionScale
      (c_lightglow.cpp:48).

  WHY THE RAMP IS LOAD-BEARING HERE AND NOT JUST PRETTY.  One traceline per glow
  per frame is not free at 263 sprites on surf_tensor2.  So only a few are traced
  each frame, round-robin, and every glow's fade is advanced every frame from
  whatever its last answer was.  The 50ms ramp is longer than the time it takes
  the cursor to come back round, so the staleness never reaches the screen.  Cut
  the ramp and the amortisation becomes visible as popping; that is the trade,
  and it is the same one Source makes.

  ONLY ADDITIVE BILLBOARDS.  spr_add is the discriminator, and it has to be:
  this same array holds bhop_murder's 208 billboard TREES and kz_anubis' timer
  digits, and drawing those with no depth test would put them through walls on
  maps that work today.  Source's glow materials are additive by construction; a
  tree is not.  SPRK_ORIENTED is excluded too -- it has a fixed world normal and
  is a surface decoration, never a flare.

  THE LIMIT BUILD 52 STATED HERE IS FIXED IN BUILD 53, and it was reported
  before it was noticed: "brush entities do not block the sprites from rendering
  when they should."  This note used to read "a CSQC traceline runs against
  csqc_world ... not the server's func_* brush entities, so a glow occluded by a
  moving door or a func_brush will not fade for it".  All of that was true, and
  writing it down did not make it acceptable.  The client now instantiates its
  own copies of the map's brush entities so that the trace has something to hit
  -- see Sprite_OccluderTier and Sprite_AddOccluder above, and vbsp_glare_brush.

  WHAT IS STILL NOT MODELLED, so the next reader does not have to rediscover it:
  the copies are frozen at their spawn position, static props are hit only
  because the VBSP plugin builds them into the world BIH rather than because
  anything here asks for them, and a transparent brush (glass, a monitor)
  occludes as though it were opaque, because a traceline has no notion of
  opacity.  Source has none of these problems in the world-glow case because it
  does not trace at all -- it asks the GPU how many of the glow's pixels
  survived the depth test (glow_overlay.cpp:247-250).
===========================================================================
*/
void() Sprite_Glare =
{
	local float  i, n, budget, decay, target, step, back;
	local vector eye, d;
	// BUILD 58: the proxy rays.
	local float  rays, hits, off;
	local vector pr, pu, aim;
	// BUILD 59: the view cull.
	local float  visits, docull, tanx, fovx, fovy, zc, xc, rad, maxdist;
	local vector fwd;
	// BUILD 60: the adaptive rays, and the measured sweep.
	local float  adapt, docorners, had, m, wrapped;
	// BUILD 61: the interval-targeted budget.
	local float  interval, vmax, ft;

	eye = getproperty(VF_ORIGIN);

	decay = cvar("vbsp_glare_decay");
	if (decay <= 0)
		decay = 0.05;               // Source's cl_sun_decay_rate
	step = frametime / decay;

	budget = cvar("vbsp_glare_traces");
	if (budget < 0)
		budget = 0;

	/*
	  BUILD 58 -- A FRACTION, NOT A YES/NO, and why the budget now counts RAYS.

	  Source runs a hardware occlusion query on a small proxy quad at the glow --
	  radius GlowProxySize, pulled GlowProxySize units toward the eye -- and
	  multiplies the glow's colour by pixels/pixelsPossible
	  (c_pixel_visibility.cpp:333-358). That is a FRACTION. Ours was
	  `trace_fraction >= 1`, so a glare Source draws at 0.2 we drew at full or
	  not at all, and on surf_tensor2 that was most of the reported wash: the
	  flares alone lifted Lex's own vantage by +17.30 mean luma against a zero
	  noise floor, with the sprites adding +10.26.

	  Five rays reproduce its shape: the centre, plus the four corners of
	  Source's own proxy, whose half-extent is GlowProxySize * sqrt(2)/2 in the
	  VIEW's right and up (c_pixel_visibility.cpp:83-91). spr_gvis then holds
	  hits/5 and NOTHING downstream changes -- it is already a float, the ramp
	  below already interpolates toward it, and both draws already multiply by
	  it. Source snaps >= 0.95 to 1.0 (:356); with five rays the nearest value
	  below 1 is 0.8, so 5 of 5 is the only thing that can mean fully visible and
	  no snap is needed.

	  THE BUDGET COUNTS RAYS, so the per-frame traceline cost is exactly what it
	  was: vbsp_glare_traces 8 was 8 tracelines and still is. What changes is
	  that 8 rays cover 1.6 glares instead of 8, so the round-robin comes round
	  5x slower and the 50 ms ramp does more of the hiding -- which is what it is
	  for. If glares lag when you spin, raise the budget rather than lowering the
	  rays. vbsp_glare_rays 1 restores builds 52-57 exactly.

	  CORRECTED IN BUILD 60: this used to end "`n` still rises by 1 for every
	  sprite VISITED, before the gate below, or a map with no additive sprites
	  would spin here forever."  That stopped being true in build 59, which gave
	  the loop a second bound -- `visits` -- precisely so a skipped or culled
	  glare would cost no rays.  `n` now counts only rays actually fired and
	  `visits` is what stops the spin.  See the two-limits note at the loop.
	*/
	rays = cvar("vbsp_glare_rays");
	rays = (rays > 1) ? 5 : 1;      // only the two shapes; anything else is 1 or 5
	if (!cvar("vbsp_sprite_source"))
		rays = 1;                   // the A/B switch reaches this half too

	/*
	  BUILD 60: how many consecutive centre-only confirmations a hidden glare may
	  take before it owes a full five-ray re-check.  Read here rather than in the
	  loop so all 429 visits see one consistent value, and so the A/B toggle
	  lands on a frame boundary.  The essay is at the shortcut itself.
	*/
	adapt = floor(cvar("vbsp_glare_adaptive"));
	if (adapt < 0)
		adapt = 0;              // floored, so anything under 1 means OFF and not
	m = adapt + 1;              // a fractional period.  m is the congruence modulus.

	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	pr = v_right;
	pu = v_up;

	/*
	  BUILD 59 -- DO NOT SPEND RAYS ON GLARES THAT CANNOT PRODUCE A PIXEL.

	  Reported as a framerate cost once the budget was raised: 555-600fps at
	  vbsp_glare_traces 8, 360-420 at 40, 200-220 at 120.  Those three points fit
	  a straight line at 27.1us PER RAY (predicting 385fps at 40 against 360-420
	  measured), so the budget is almost entirely traceline cost and the way to
	  buy latency is to stop wasting rays rather than to buy more of them.

	  THE WASTE IS THE ROUND-ROBIN ITSELF.  It walked all 429 of surf_tensor2's
	  glares in order, including the ~380 behind the player, because nothing in
	  this loop had ever looked at where the camera was pointing.  Lex asked the
	  right question -- "only dealing with the ones in the scene or something?
	  are we doing it silly?" -- and the answer was yes.

	  WHY CULLING THE TRACE IS SAFE WHERE CULLING THE DRAW WOULD NOT BE.  A glare
	  outside the viewport contributes no pixels whatever spr_glare says, so a
	  stale answer there is invisible by construction.  Verified: cull on vs off
	  at the reported vantage is 0.007% of pixels, i.e. the same picture.

	  IT BUYS NO FRAMERATE AT ALL, AND THAT IS CORRECT RATHER THAN DISAPPOINTING.
	  The budget is in RAYS and it is saturated either way, so the cost per frame
	  cannot move: measured 383.4 fps with the cull off against 399.0 and 412.5
	  on two cull-on arms, i.e. if anything faster, and inside its own spread.
	  What the cull buys is LATENCY, and a great deal of it.

	  I REPORTED THAT WRONG FOR A WHOLE BUILD, off a census line of my own.  The
	  build 59 line divided by glares TRACED per frame, which quietly assumes a
	  culled glare does not advance the round-robin cursor -- it does, for free,
	  which is the entire point.  So it read "sweep 54 -> 50 frames" and I told
	  Lex the cull bought almost nothing, while the same line was printing 30
	  culled and 8 traced: 38 visits, and a sweep five times shorter than it
	  claimed.

	  THEN I STOPPED DERIVING IT AND COUNTED FRAMES BETWEEN CURSOR WRAPS, which
	  is the sweep itself with no denominator and no assumption.  Measured at
	  Lex's vantage, six samples an arm, and repeated at a second vantage when he
	  moved the mouse mid-run:

	      cull off (b58)        53.6 frames per sweep  (429/8, the one case
	                                                    the old formula got right)
	      cull on  (b59)        11.2 and 10.8 frames   -> 4.8x
	      + adaptive (b60)      3.7, 3.8 and 3.4       -> a further 3.0x, 14.5x on b58
	      + adaptive at 12 rays 9.8 frames             -> better than b59 at 30%
	                                                      of the ray budget

	  A DERIVED FIGURE WITH THE WRONG DENOMINATOR IS WORSE THAN NO FIGURE,
	  because it reads like a measurement and it survived three runs and a report
	  to the user before anyone divided 429 by 38 by hand.  Note that even the
	  CORRECTED derivation (spr_n/visits) was only accidentally close: it gave
	  10.5 against a measured 11.2 here, but visits-per-frame swings 20-200 with
	  the cursor's position because the loop stops on the ray budget, so a
	  sampled mean of it is not the sweep.  Count the wraps.

	  I ALSO HAD THE STRUCTURE WRONG.  "~50 glares on screen" confused DRAWN with
	  IN VIEW.  The census reads `glare 302 in frame, 296 hidden by the trace`
	  and `6 of 429 passed the cull`: 302 of the 429 are genuinely inside the
	  frustum and are invisible because they are OCCLUDED, which is precisely the
	  thing only a trace can determine.  The cull still pays, but it pays on the
	  ~30-160 behind the eye rather than on any of those 302.

	  WHICH POINTS AT THE ACTUAL LEVER: 296 of the 302 traced glares are FULLY
	  hidden, and each spends 5 rays to establish what the centre ray alone
	  already said.  That is the adaptive path below, added in build 60.

	  THE CONE IS DELIBERATELY TOO WIDE.  It is built from the horizontal fov
	  with a SQUARE aspect -- i.e. as if the screen were as tall as it is wide.
	  Every real widescreen is shorter than that, so the cone circumscribes the
	  true frustum and cannot cull something on screen.  Reading the real aspect
	  would be tighter and would also make this depend on vid_conwidth/conheight,
	  which are not reliably set here; a cone that is too generous costs a few
	  wasted rays, a cone that is too tight costs correctness.

	  vbsp_glare_cull is the margin ITSELF, not a boolean: 0 disables the cull
	  entirely (the build-58 behaviour, and the A/B), 1.0 is the exact
	  circumscribed cone, 1.25 is the default and gives 25% slack on the tangent
	  for turning.  One cvar rather than two because a boolean plus a margin
	  would have two ways to spell "off".
	*/
	docull = cvar("vbsp_glare_cull");
	maxdist = cvar("vbsp_sprite_dist");
	tanx = 0;
	if (docull > 0)
	{
		fovx = cvar("fov");
		if (fovx <= 0 || fovx >= 180)
			fovx = 90;
		fovy = fovx * 0.5 * 0.0174532925;       // half-fov in radians
		// tan = sin/cos; sqrt(2) promotes the horizontal half-angle to the
		// diagonal of a SQUARE frustum, which is the conservative choice above.
		tanx = (sin(fovy) / cos(fovy)) * 1.41421356 * docull;
	}

	// ---- the amortised trace: `budget` RAYS per frame, round-robin ----------
	/*
	  BUILD 59: two limits now, and they bound different things.

	  `n` bounds RAYS, because rays are the 27us each.  `visits` bounds LOOP
	  ITERATIONS, because a culled glare costs one dot product and must NOT eat
	  the ray budget -- if it did, culling would make the sweep slower rather
	  than faster (429 cheap visits would exhaust a budget of 40 long before
	  finding the 50 glares worth tracing).  Capping visits at spr_n also means
	  at most one full pass per frame, which is what stops an all-culled map
	  from spinning here forever.

	  BUILD 61 MOVED THAT CAP but did not weaken it: the bound is now `vmax`,
	  which is spr_n unless the interval asks for less, and the interval branch
	  clamps its accumulator to spr_n before flooring it.  So vmax <= spr_n
	  always and the one-pass guarantee above is unchanged.  Said here because
	  the code no longer literally reads `visits < spr_n` and a reader checking
	  the anti-spin argument would otherwise have to re-derive it.
	*/
	/*
	  BUILD 61: and a third limit, which is the one with a unit anybody cares
	  about.  `vmax` is spr_n -- one full pass, the build 60 behaviour -- unless
	  vbsp_glare_interval asks for a staleness bound, in which case it is this
	  frame's share of a sweep that must complete in `interval` seconds.

	  frametime IS CLAMPED, and the direction matters.  A 250 ms hitch (a map
	  load finishing, an alt-tab, a shader compile) would otherwise compute a
	  quota of several whole sweeps and fire the entire ray ceiling on the frame
	  immediately after the hitch -- i.e. spend the budget precisely when the
	  frame is already late.  Clamping at 100 ms means a hitch loses a little
	  freshness instead of making the stall worse, which is the trade I want.
	  It cannot deadlock: the quota keeps accruing every frame afterwards.

	  ONE SWEEP OF DEBT IS THE MOST THE ACCUMULATOR MAY HOLD.  Without the clamp
	  a long pause banks arbitrary credit and pays it out in one frame; with it,
	  the worst case after any stall is a single full pass, which is exactly the
	  build 60 worst case and already measured.
	*/
	interval = cvar("vbsp_glare_interval");
	vmax = spr_n;
	spr_gquota = 0;                 // 0 in the census reads as "uncapped"
	if (interval > 0 && spr_n > 0)
	{
		ft = frametime;
		if (ft <= 0)
			ft = 0.001;
		else if (ft > 0.1)
			ft = 0.1;
		spr_gvacc = spr_gvacc + spr_n * ft / interval;
		if (spr_gvacc > spr_n)
			spr_gvacc = spr_n;
		vmax = floor(spr_gvacc);
		spr_gvacc = spr_gvacc - vmax;   // carry the fraction; see the decl
		spr_gquota = vmax;
	}

	n = 0;
	visits = 0;
	wrapped = FALSE;
	spr_gcull = 0;
	spr_gtraced_n = 0;
	spr_gcheap = 0;
	spr_gforce = 0;
	spr_grays = 0;
	while (n < budget && visits < vmax && spr_n > 0)
	{
		i = spr_gnext;
		spr_gnext = spr_gnext + 1;
		if (spr_gnext >= spr_n)
		{
			spr_gnext = 0;
			wrapped = TRUE;         // a sweep completed in this frame; see below
		}
		visits = visits + 1;

		// BUILD 54: env_lightglow joins this, and it is the same question for the
		// same reason.  Everything additive except an ORIENTED sprite, which has
		// a fixed world normal and is a tree or a sign rather than a flare.
		if (!spr_add[i] || spr_kind[i] == SPRK_ORIENTED)
			continue;               // not a glare; see the essay

		d = spr_org[i] - eye;

		/*
		  BUILD 59: the view test.  The first two conditions are the DRAW loop's
		  own cull (:2091-2093) copied deliberately rather than reinvented -- if
		  these two ever disagree about what is on screen, the disagreement is a
		  glare that draws with an answer nothing is refreshing, which is the
		  exact bug this is meant to cure.  The third is the cone, and it has no
		  counterpart in the draw loop because the rasteriser does that clipping
		  for free; here it has to be explicit.
		*/
		if (docull > 0)
		{
			rad = spr_rad[i];
			zc = fwd * d;
			if (zc < -rad)
			{                       // behind the eye
				spr_gcull = spr_gcull + 1;
				continue;
			}
			if (maxdist > 0 && vlen(d) - rad > maxdist)
			{                       // past the draw distance, so it is not drawn
				spr_gcull = spr_gcull + 1;
				continue;
			}
			// Outside the cone.  Only meaningful in front of the eye; a glare
			// straddling the eye plane (-rad <= zc <= 0) is kept, because its
			// distance from the axis says nothing useful there.
			if (zc > 0)
			{
				xc = vlen(d - fwd * zc);        // distance from the view axis
				if (xc - rad > zc * tanx)
				{
					spr_gcull = spr_gcull + 1;
					continue;
				}
			}
		}

		/*
		  The back-off, and it is not cosmetic.  A glow is placed AT the lamp, so
		  a trace to its exact centre lands on the lamp's own brush and reports
		  "blocked" from every angle -- the glow would never appear at all.
		  Source hits this and solves it the same way
		  (c_pixel_visibility.cpp:790-791: "trace 4in from destination in case
		  the glow is inside some parent object").

		  BUILD 54: the distance is now the map's own GlowProxySize, floored at
		  Source's 4.  See Glow_ParamSet for why the floor is a max and not a
		  replacement.
		*/
		back = glowp_backoff[spr_pset[i]];
		if (vlen(d) > back)
			aim = spr_org[i] - normalize(d) * back;
		else
			aim = spr_org[i];

		/*
		  BUILD 59: the full ray cost, not rays-1.  Before the cull, every VISIT
		  cost 1 from this budget and a traced glare paid the remaining rays-1;
		  now a visit costs nothing (it is bounded by `visits` instead) so the
		  whole cost belongs here.

		  BUILD 60: the centre ray is charged HERE and the four corners are
		  charged where they are fired, because whether they fire is now a
		  decision.  The budget therefore still counts rays exactly -- getting
		  this wrong in either direction silently rescales every measurement
		  taken with it, in the direction that flatters the change.
		*/
		n = n + 1;
		spr_grays = spr_grays + 1;
		spr_gtraced_n = spr_gtraced_n + 1;

		hits = 0;
		traceline(eye, aim, MOVE_NOMONSTERS, spr_gskip[i]);
		if (trace_fraction >= 1)
			hits = hits + 1;

		/*
		  BUILD 53 -- WAS IT A BRUSH ENTITY THAT STOPPED IT?

		  This counter exists because the obvious A/B does not work.  Flipping
		  vbsp_glare_brush and comparing the `hidden` count only detects a brush
		  entity that is the ONLY thing between the eye and the glow, and on a
		  real map almost every blocked glow is blocked by worldspawn as well --
		  so the totals can be identical whether or not the feature works.  The
		  first run of this measured exactly that: 232 of 240 hidden with the
		  occluders in, 232 of 240 with them out, which proves nothing in either
		  direction.

		  trace_ent names what the trace actually hit, so counting the hits that
		  landed on something other than the world answers the question directly
		  and needs no lucky vantage.
		*/
		if (trace_fraction < 1 && trace_ent != world)
			spr_gbrush = spr_gbrush + 1;

		/*
		  ===================================================================
		  BUILD 60 -- SPEND FOUR MORE RAYS ONLY WHERE THEY CAN CHANGE THE ANSWER
		  ===================================================================

		  Build 59 measured 27.1us per ray and then found the frustum cull could
		  only remove 7% of them.  The census said where the rest go: at Lex's
		  vantage 302 of surf_tensor2's 429 glares are inside the frustum, 296 of
		  those are FULLY hidden, and each of the 296 fires five rays to establish
		  what its first ray already said.

		  THE SHORTCUT.  If the last full answer was 0 -- every one of the five
		  rays blocked -- and the centre ray is blocked AGAIN this visit, take 0
		  and stop.  That is one ray instead of five on 98% of the traced set.

		  WHY IT IS NEARLY EXACT, and this is a fact about the geometry rather
		  than a hope.  `off` is GlowProxySize*sqrt(2)/2, but each corner is
		  displaced along (pr +- pu), whose length is sqrt(2) -- so the corner
		  sits off * sqrt(2) = GlowProxySize from the aim point, i.e. 4.0 UNITS
		  to the side of a ray that just hit something, on the glows here.
		  (An earlier version of this paragraph said 2.8 and had dropped that
		  sqrt(2); a review lens caught it.  The bound is 4.0.)  For the cheap
		  answer to be wrong, an occluder's silhouette edge has to pass within
		  those 4 units.  When it does, the true answer is 1/5 or 2/5 -- a glare
		  Source would draw at 20-40% -- so the error is bounded by a dim glare
		  reading as dark, never by a bright one vanishing.  A glare going the
		  other way (hidden -> visible) cannot be missed at all: the centre ray
		  comes back clear, the shortcut declines, and the full five fire.

		  THE BOUND IS LOOSER WHERE GlowProxySize IS BIG, and it is the map's
		  number: glowp_backoff is max(GlowProxySize, 4), so a map authored with
		  a 64-unit proxy puts its corners 64 units out and the cheap answer is
		  correspondingly coarser.  Not gated on, because a large proxy is also a
		  large soft glow where a 1/5 error is least visible -- but stated, so a
		  map that looks wrong here has somewhere to start.

		  AND WHY IT IS NOT STICKY, which is the failure this could have had.  A
		  glare parked exactly behind a thin edge would keep confirming 0 forever
		  and could never discover its corners had opened up.  So every glare owes
		  a full five-ray re-check once every adapt+1 VISITS, whatever the centre
		  ray says.  vbsp_glare_adaptive IS that period rather than a boolean:
		  0 disables the shortcut and restores build 59 exactly, 8 is the default
		  and costs (8*1 + 5)/9 = 1.44 rays per hidden glare instead of 5.  One
		  cvar, because a boolean plus a period would have two ways to spell
		  "off".  It is floored to an integer above, so 0.5 means off rather than
		  meaning a 1.5-visit period.

		  HOW THE RE-CHECKS ARE KEPT SPREAD OUT, which took two attempts.  Version
		  one counted cheap confirmations and reset on each full answer; measured,
		  that put every glare in the same phase and one sweep in nine cost the
		  full five rays for everything -- 9/50/14 frames per sweep on three
		  consecutive frames, i.e. a good mean with build 59's worst case intact,
		  and the worst case is what Lex reported as "up to 1 sec".  Version two
		  seeded the first period per glare, which fixed the load case and nothing
		  else: one sweep with the shortcut off re-synchronised the whole map
		  permanently, and three of four review lenses found that before it had
		  run twice.

		  So the due test is a CONGRUENCE on a counter that never resets: glare i
		  is due when its visit count and its index agree modulo adapt+1.  The
		  period is exactly adapt+1 for every glare, the phase is a property of
		  the index, and there is no history for a toggle to destroy.  See
		  spr_gtraced's declaration.

		  WHAT IT DOES NOT TOUCH: rays, hits and spr_gvis keep their build-58
		  meanings, the ramp below is unchanged, and both draw loops still just
		  multiply by spr_glare.  A glare whose answer is anything other than 0
		  is traced exactly as it was.
		*/
		had = spr_gtraced[i];                   // 0 = this is its first ever answer
		spr_gtraced[i] = had + 1;               // one visit; never reset, see the decl

		docorners = (rays > 1);
		if (docorners && !hits && adapt > 0 && had >= 1 && spr_gvis[i] <= 0)
		{
			// due when count == index (mod adapt+1).  `m` is set once per frame.
			if ((spr_gtraced[i] - floor(spr_gtraced[i] / m) * m)
			    == (i - floor(i / m) * m))
				spr_gforce = spr_gforce + 1;    // owed a re-check: fall through to five
			else
			{
				docorners = FALSE;              // centre blocked, and it was blocked before
				spr_gcheap = spr_gcheap + 1;
			}
		}

		/*
		  The four proxy corners. Taken in the VIEW basis rather than around the
		  eye-to-glow direction because that is where Source puts them -- the
		  proxy is a screen-facing quad, so at a grazing angle its corners spread
		  across the lamp's face and that is exactly when a fraction differs most
		  from a centre sample.
		*/
		if (docorners)
		{
			off = back * 0.70710678;    // GlowProxySize * sqrt(2)/2

			n = n + 4;
			spr_grays = spr_grays + 4;

			traceline(eye, aim + (pr + pu) * off, MOVE_NOMONSTERS, spr_gskip[i]);
			if (trace_fraction >= 1)
				hits = hits + 1;
			traceline(eye, aim + (pr - pu) * off, MOVE_NOMONSTERS, spr_gskip[i]);
			if (trace_fraction >= 1)
				hits = hits + 1;
			traceline(eye, aim - (pr - pu) * off, MOVE_NOMONSTERS, spr_gskip[i]);
			if (trace_fraction >= 1)
				hits = hits + 1;
			traceline(eye, aim - (pr + pu) * off, MOVE_NOMONSTERS, spr_gskip[i]);
			if (trace_fraction >= 1)
				hits = hits + 1;

			spr_gvis[i] = hits * 0.2;
		}
		else if (rays == 1)
			spr_gvis[i] = hits;        // no corners exist to skip; always a full answer
		// else: the cheap path took 0 and left spr_gvis alone, which already IS 0.
		//
		// spr_gtraced was incremented once, above, on every one of these paths --
		// it counts VISITS, not answers, so nothing is written back here.  The
		// earlier version wrote it per path and that is what lost the phase.
	}
	spr_gvisits = visits;               // the cursor advance, for the census
	/*
	  BUILD 61 -- RECORD WHICH LIMIT BIT, because with two live limits "40 rays
	  fired" and "40 rays allowed" are the same number for two opposite reasons
	  and the census cannot tell them apart from the counters alone.  This is the
	  same lesson as the sweep denominator: a figure that needs the reader to
	  guess which term dominated is a figure that will be read wrong.

	  Rays win a tie deliberately.  If both are exhausted on the same iteration
	  the interval is not being met, and saying "the ray ceiling" points at the
	  cvar that would fix it.
	*/
	spr_glimit = 0;
	if (n >= budget)
		spr_glimit = 1;
	else if (visits >= vmax)
		spr_glimit = 2;

	/*
	  BUILD 60 -- MEASURE THE SWEEP, DO NOT DERIVE IT.

	  The build 59 census computed frames-per-sweep from the per-frame counters
	  and got it wrong (see the census block in Sprite_Draw), and the corrected
	  formula spr_n/visits is still a derivation resting on "the cursor advances
	  once per visit" plus an assumption that this frame's visit count is typical
	  of the sweep.  It is not: the loop stops when the ray budget runs out, so a
	  frame crossing a stretch of culled glares reports 160 visits and one
	  crossing visible lamps reports 20.  Sampling that at 400ms gave a mean that
	  disagreed with the map-wide cull fraction by 4x, and rather than argue the
	  statistics, count the thing itself.

	  A sweep IS one wrap of the cursor.  So count frames, and when the cursor
	  wraps, latch the count.  spr_gsweep is then the measured number of frames
	  the last complete pass over every glare actually took -- no denominator, no
	  assumption, and it is the exact quantity Lex reported as "up to 1 sec".
	*/
	spr_gsweep_f = spr_gsweep_f + 1;
	if (wrapped)
	{
		spr_gsweep = spr_gsweep_f;
		spr_gsweep_f = 0;
	}

	// ---- and every glare's fade advances every frame, traced or not ---------
	/*
	  BUILD 54, FIXED AFTER MEASUREMENT.  This gate MUST be the same gate the
	  trace loop above uses, and for one build it was not: it read
	  `spr_kind[i] != SPRK_BILLBOARD`, which is true for every SPRK_GLOW, so all
	  166 of surf_tensor2's env_lightglows were traced, answered correctly, and
	  then had their ramp skipped -- spr_glare stayed at its initial 0 forever
	  and the draw loop's `if (glare <= 0) continue` threw every one of them
	  away.

	  IT LOOKED EXACTLY LIKE THE FEATURE NOT EXISTING.  The load-time census said
	  "lightglows: 166 of 166 drawn" because that counts what was ADDED, and
	  toggling vbsp_lightglow moved 0.160% of the frame against a same-setting
	  control of 0.192% at the same vantage -- i.e. below its own noise floor.
	  Only the control made that readable as "nothing is drawing" rather than as
	  "the flares are subtle".

	  Written as the trace loop's gate rather than as `== BILLBOARD || == GLOW`
	  so the two cannot drift apart again: an ORIENTED sprite has a fixed world
	  normal and is a sign or a tree, and everything else additive is a glare.
	*/
	for (i = 0; i < spr_n; i = i + 1)
	{
		if (!spr_add[i] || spr_kind[i] == SPRK_ORIENTED)
			continue;

		/*
		  Never traced yet: start HIDDEN and let it fade up.  Starting visible
		  would flash every glow on the map for one ramp on the first frame,
		  including the ones behind walls -- which is exactly the artefact this
		  whole function exists to remove.
		*/
		target = spr_gtraced[i] ? spr_gvis[i] : 0;

		if (spr_glare[i] < target)
		{
			spr_glare[i] = spr_glare[i] + step;
			if (spr_glare[i] > target) spr_glare[i] = target;
		}
		else if (spr_glare[i] > target)
		{
			spr_glare[i] = spr_glare[i] - step;
			if (spr_glare[i] < target) spr_glare[i] = target;
		}
	}
};

void() Sprite_Draw =
{
	local float  i, m, maxdist, drawn, dbg, mo;
	local vector eye, fwd, vright, vpright, vpup, r, u, dd;
	local vector a, b, c, d, side, mid;
	local float  flags, glare, useglare, useglare_on;
	local float  g_total, g_hidden, g_fading;
	// BUILD 58.  srcmode gates the Source dimming terms; the count they were
	// applied to lives in the global spr_dim_n, for the reason given there.
	local float  srcmode, amt, gfx, glowscale;
	local vector gcol;
	/*
	  BUILD 54.  GLOW-ONLY COUNTERS, because the shared ones cannot answer the
	  question that matters.

	  g_total/g_hidden are incremented by BOTH the billboard loop and the glow
	  loop, so "glare 349 in frame, 338 hidden by the trace" says nothing about
	  whether any of the 166 env_lightglows reached the draw.  Eight vantages,
	  each 1500 units along one glow's own forward, produced a lightglow on/off
	  difference of exactly 0.000% at seven of them against a control that was
	  also exactly 0.000% -- a perfectly still scene, so that is not a subtle
	  effect being missed, it is nothing being drawn.  These five numbers say
	  which gate is eating them.
	*/
	local float  gl_seen, gl_side, gl_hid, gl_fade, gl_drawn;
	local float  dist, fade, pset, gmn, gmx, gout;
	local vector toglow, base;

	if (serverkey("map") != vbsp_spr_map)
		Sprite_LoadForMap();

	/*
	  BUILD 58 -- THE RELOAD HOOK MOVED ABOVE THE EARLY RETURN, because below it
	  the hook was unreachable in exactly the state it exists for.

	  vbsp_sprite_debug 2 reloads the table in place; that is build 53's remedy
	  for cvars that are only read at map load. But `vbsp_sprites 0` empties the
	  table, and an empty table returns here -- before the debug block ever runs.
	  So once the feature was switched off it could not be switched back on
	  without changing map, and an A/B arm that tried produced two screenshots
	  byte-identical to the sprites-off frame and looked like a result. It cost
	  two arms of the build 58 measurement run before a diff against the control
	  caught it.
	*/
	if (cvar("vbsp_sprite_debug") == 2)
	{
		cvar_set("vbsp_sprite_debug", "1");
		Sprite_LoadForMap();
	}

	if (!spr_n && !beam_n)
		return;

	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	/*
	  BUILD 55.  SPR_VP_PARALLEL is literally the view's own basis --
	  c_sprite.cpp:283-288 copies CurrentViewUp/Right/Forward element by element
	  and does nothing else.  Taken here rather than per sprite because it is the
	  same for every sprite on screen, exactly like vright below.  Roll comes
	  along for free, which is correct: Source rolls parallel sprites with the
	  view (:238-241 promotes them to VP_PARALLEL_ORIENTED when the entity has
	  roll of its own, and the view's roll is already in these vectors).
	*/
	vpright = v_right;
	vpup    = v_up;

	maxdist = cvar("vbsp_sprite_dist");
	drawn = 0;
	// QuakeC locals are not zeroed; fteqcc warns F302 if you forget.
	g_total = 0;
	g_hidden = 0;
	g_fading = 0;
	srcmode = cvar("vbsp_sprite_source");
	// Negative would invert an additive blend into nothing and read as "the
	// flares stopped working"; 0 is a legitimate way to mute them entirely.
	glowscale = cvar("vbsp_lightglow_scale");
	if (glowscale < 0)
		glowscale = 0;
	gl_seen = gl_side = gl_hid = gl_fade = gl_drawn = 0;

	// BUILD 52.  One read per frame, not one per sprite; and the trace/ramp pass
	// runs before the draw so this frame's alphas are this frame's answers.
	useglare_on = cvar("vbsp_glare");
	if (useglare_on)
		Sprite_Glare();

	dbg = cvar("vbsp_sprite_debug");
	if (dbg)
	{
		cvar_set("vbsp_sprite_debug", "0");
		/*
		  BUILD 53: 2 also RELOADS, and the reason is that vbsp_glare_brush is
		  read once at map load.

		  The occluders are built in the load walk, so setting the cvar in the
		  console does nothing until the next map -- and "map <samename>" does
		  not reload in this engine, which is a trap already written down in this
		  project's notes.  Without this, the only way to A/B the feature is to
		  load a different map in between, and an A/B that needs a detour
		  through a third map is one nobody runs twice.

		  Deliberately on the DEBUG cvar rather than as its own command: it is a
		  test hook, it costs one entity-lump walk, and it clears itself the same
		  way the rest of this block does.
		*/
		if (dbg == 2)
			Sprite_LoadForMap();
		print(sprintf("vbsp_sprite_debug: %g sprites, %g beams, %g materials, maxdist %g\n",
		              spr_n, beam_n, sprmat_n, maxdist));
		print(sprintf("  occluders: %g of %g brush entities, mode %g (%g over cap), %g traces stopped by one\n",
		              spr_occ_n, spr_occ_seen, cvar("vbsp_glare_brush"), spr_occ_over,
		              spr_gbrush));
		spr_gbrush = 0;
		/*
		  BUILD 54.  Its own line because fteqcc caps a varargs call at eight
		  parameters INCLUDING the format string, and the line above already
		  spends seven.
		*/
		print(sprintf("  glows: %g env_lightglow drawn, %g parameter sets; %g glares skip their own brush (%g in more than one)\n",
		              vbsp_glow_n, glowp_n, spr_gskip_n, spr_gskip_multi));
		// BUILD 55.  "we could not read the material and guessed" has to be
		// visible: a map whose sprite content is missing looks identical to one
		// whose materials all say vp_parallel, and only this number tells them
		// apart.
		print(sprintf("  orientation: %g material(s) read from the .vmt, %g guessed (mode %g), %g declined\n",
		              sprmat_orient_read, sprmat_orient_guess,
		              cvar("vbsp_sprite_orient"), sprmat_orient_decl));
		// BUILD 58.  Liveness, not decoration: a stale frame cannot fake a
		// counter, so this is what says the dimming actually ran rather than
		// the picture happening to look the same.
		print(sprintf("  source dimming: %s, %g sprite(s) dimmed last frame; glare rays %g\n",
		              srcmode ? "on" : "OFF", spr_dim_n, cvar("vbsp_glare_rays")));
		for (m = 0; m < sprmat_n; m = m + 1)
			print(sprintf("  %2g %-40s %gx%g  orient %g\n",
			              m, sprmat_name[m], sprmat_w[m], sprmat_h[m], sprmat_orient[m]));
	}

	/*
	  SPR_VP_PARALLEL_UPRIGHT.  It is NOT a full billboard: up stays world +Z and
	  only the right vector turns, so a tall glow does not tip over as you look
	  up at it -- which is right for the 17 library materials that ask for it and
	  wrong for the 177 that do not.  BUILD 55 picks per material; see
	  Sprite_ReadOrient.  This is still computed once rather than per sprite
	  because c_sprite.cpp:305-309 derives right from the VIEW direction and not
	  from the direction to each sprite.

	  Its degenerate case is looking almost straight up or down; Source declines
	  to draw within one degree of vertical (:301-303) and so does the guard
	  below.
	*/
	vright = normalize([fwd_y, -fwd_x, 0]);
	if (fwd_z > 0.999848 || fwd_z < -0.999848)
		vright = '0 1 0';   // looking straight up: any horizontal axis will do

	/*
	  Materials in the OUTER loop.  Consecutive polygons sharing a shader and
	  flags do not flush the batch (pr_csqc.c:1671), so walking the sprites in
	  material order turns bhop_rpg's 862 quads into roughly 30 draw calls
	  instead of 862.  The cost is sprmat_n passes over the array -- at most 96
	  times 1024 tests of one float, once per frame, and no work at all for the
	  ones that do not match.
	*/
	// Reset HERE rather than at the top of the function: the census above has
	// already printed it, so what it printed is last frame's finished total.
	spr_dim_n = 0;

	for (m = 0; m < sprmat_n; m = m + 1)
	{
		if (sprmat_w[m] <= 0)
			continue;

		/*
		  BUILD 55: once per material, not per sprite -- the loop is already
		  material-major, so the cvar lookup costs at most 34 hash probes a frame
		  on the library's worst map and buys a live A/B with no reload.
		  2 (or anything else) = what the material said.
		*/
		mo = sprmat_orient[m];
		if (cvar("vbsp_sprite_orient") == 0)
			mo = SPRO_UPRIGHT;
		else if (cvar("vbsp_sprite_orient") == 1)
			mo = SPRO_PARALLEL;

		for (i = 0; i < spr_n; i = i + 1)
		{
			if (spr_mat[i] != m)
				continue;

			dd = spr_org[i] - eye;

			// Distance and behind-camera, off the precomputed radius.  Same two
			// tests Zone_Draw uses, and for the same reason: CSQC polygons get
			// no PVS and no frustum cull from the engine.
			if (maxdist > 0 && vlen(dd) - spr_rad[i] > maxdist)
				continue;
			if (fwd * dd < -spr_rad[i])
				continue;

			if (spr_kind[i] == SPRK_ORIENTED)
			{
				r = spr_right[i] * spr_hw[i];
				u = spr_up[i]    * spr_hh[i];
				// An oriented quad has a fixed normal and the player can walk
				// behind it -- 208 of bhop_murder's are trees you can circle.
				// Without this the far side is culled away (pr_csqc.c:1666).
				flags = DRAWFLAG_TWOSIDED;
			}
			else if (mo == SPRO_UPRIGHT || mo == SPRO_FACING)
			{
				// parallel_upright, and facing_upright drawn as it (declined)
				r = vright  * spr_hw[i];
				u = '0 0 1' * spr_hh[i];
				flags = 0;
			}
			else
			{
				// vp_parallel, and vp_parallel_oriented drawn as it (declined
				// -- it differs only by the entity's own roll about the view
				// axis).  This is the case for 177 of the library's 213 sprite
				// materials, including every one surf_tensor2 uses.
				r = vpright * spr_hw[i];
				u = vpup    * spr_hh[i];
				flags = 0;
			}
			if (spr_add[i])
				flags = flags | DRAWFLAG_ADD;

			/*
			  BUILD 52.  An additive billboard is a light glare, so it is drawn
			  OVER the world and its visibility comes from Sprite_Glare's trace
			  instead of from the depth buffer.  Everything else keeps exactly
			  the behaviour it had -- see the essay above Sprite_Glare for why
			  that distinction is not optional.
			*/
			useglare = (useglare_on && spr_add[i] && spr_kind[i] == SPRK_BILLBOARD);
			if (useglare)
			{
				g_total = g_total + 1;
				glare = spr_glare[i];
				if (glare <= 0)
				{
					g_hidden = g_hidden + 1;
					continue;           // fully occluded: draw nothing at all
				}
				if (glare < 1)
					g_fading = g_fading + 1;
				flags = flags | DRAWFLAG_NODEPTHTEST;
			}
			else
				glare = 1;

			a = spr_org[i] - r + u;
			b = spr_org[i] + r + u;
			c = spr_org[i] + r - u;
			d = spr_org[i] - r - u;

			/*
			  BUILD 58 -- THE TWO TERMS SOURCE DIMS A GLOW SPRITE BY.

			  1. RENDERAMT IS APPLIED TWICE. The leaf system folds it into RGB
			     (viewrender.cpp:4085 -> c_sprite.cpp:409, then r,g,b *= blend at
			     :417-419) and it is ALSO the vertex alpha that the additive
			     blend multiplies (Sprite.cpp:806 -> c_sprite.cpp:83, with
			     SHADER_BLEND_SRC_ALPHA). So the output scales as
			     (renderamt/255)^2. We applied it once: 1.46x too bright at the
			     175 that 166 of surf_tensor2's sprites carry.
			  2. AN INVERSE-SQUARE DISTANCE FADE, c_sprite.cpp:168-170:
			     clamp((1200/dist)^2, 0, 1). It sits OUTSIDE the
			     `rendermode != kRenderWorldGlow` guard at :172, so mode 9 gets
			     it; only the screen-space *scale* fix-up is skipped. We had
			     nothing: 3.7x too bright at 2300 units, 11x at 4000.

			  No sqrt: dd is the eye-to-sprite vector and dd*dd is its length
			  squared, which is the only form the fade needs.

			  Folding both into the COLOUR rather than the alpha is exact under
			  GL_SRC_ALPHA/GL_ONE (they are one product either way) and keeps the
			  alpha meaning what the glare ramp means, so nothing downstream has
			  to know this happened.
			*/
			gcol = spr_col[i];
			if (srcmode && spr_add[i] >= SPRA_GLOW)
			{
				amt = spr_alpha[i];
				if (spr_add[i] == SPRA_PULSE)
				{
					// c_baseentity.cpp:3342-3344: renderamt +/- 0x40 at 2 rad/s,
					// de-synced per entity. Source offsets by the entity index;
					// the sprite index serves the same purpose and is what we
					// have. It modulates the COLOUR term only -- the vertex
					// alpha stays GetRenderBrightness(), i.e. unpulsed
					// (Sprite.cpp:806 reads m_nBrightness, not m_nFXBlend).
					amt = amt + 0.25098 * sin(time * 2 + i * 363);
					if (amt < 0) amt = 0;
					if (amt > 1) amt = 1;
				}

				gfx = 1;
				if (spr_add[i] != SPRA_NODISS && (dd * dd) > 0.01)
				{
					gfx = (1200 * 1200) / (dd * dd);
					if (gfx > 1)
						gfx = 1;
				}

				gcol = gcol * (amt * gfx);
				spr_dim_n = spr_dim_n + 1;

				// The same term-by-term dump as the glows below, for the same
				// reason: which factor is carrying the brightness.
				if (dbg)
					print(sprintf("  sprite %g: dist %g renderamt %.3f fadeout %.3f  half %g  glare %.3f\n",
					              i, vlen(dd), amt, gfx, spr_hw[i], glare));
			}

			Sprite_Quad(a, b, c, d, sprmat_name[m], flags, gcol, spr_alpha[i] * glare);
			drawn = drawn + 1;
		}
	}

	/*
	===========================================================================
	  BUILD 54 -- env_lightglow, in one batch of its own.

	  Its own loop rather than a branch inside the material-major one above,
	  because a glow is not a world quad: it is placed in VIEW space, it shares
	  one hardcoded material with every other glow on the map, and its size comes
	  from the entity rather than from a texture.  All 166 of surf_tensor2's are
	  therefore one batch, the same way the beams below are.

	  THE BASIS IS SOURCE'S, transcribed from CalcBasis (glow_overlay.cpp:322-343):

	      vBasePt = eye + vToGlow * 100
	      vRight  = normalize(cross(vToGlow, (0,0,1))) * flHorzSize
	      vUp     = normalize(cross(vRight,  vToGlow)) * flVertSize

	  The fixed 100 units is what makes HorizontalGlowSize and VerticalGlowSize
	  read as an ANGULAR size: the quad is always the same distance from the eye,
	  so 65 by 35 is 65 by 35 on screen whether the lamp is 200 units away or
	  6000.  Getting that wrong -- putting the quad at the glow -- would make
	  every flare on the map shrink with distance and the effect would read as
	  "the lens flares are tiny", which is not a bug anyone would connect back to
	  this line.
	===========================================================================
	*/
	for (i = 0; i < spr_n; i = i + 1)
	{
		if (spr_kind[i] != SPRK_GLOW)
			continue;

		dd = spr_org[i] - eye;
		dist = vlen(dd);
		if (dist < 0.01)
			continue;               // standing inside it; no direction to face
		toglow = dd * (1 / dist);

		/*
		  One-sided, c_lightglow.cpp:27-34.  Source tests the vector FROM the
		  glow TO the eye against the glow's forward and blacks it out when the
		  dot is negative; toglow points the other way, so the sign flips.
		  spr_right is '0 0 0' on a glow that is not one-sided -- makevectors
		  cannot produce that, so the test needs no separate flag.
		*/
		gl_seen = gl_seen + 1;
		if (spr_right[i] != '0 0 0' && (toglow * spr_right[i]) > 0)
		{
			gl_side = gl_side + 1;
			g_total = g_total + 1;  // in frame, and hidden -- see below
			g_hidden = g_hidden + 1;
			continue;
		}

		g_total = g_total + 1;

		// The occlusion ramp, shared with every other glare.
		glare = useglare_on ? spr_glare[i] : 1;
		if (glare <= 0)
		{
			g_hidden = g_hidden + 1;
			gl_hid = gl_hid + 1;
			continue;
		}
		if (glare < 1)
			g_fading = g_fading + 1;

		/*
		  The distance ramp, c_lightglow.cpp:36-47.  This is the half of the
		  behaviour that makes a flare appear as you approach rather than being
		  on from across the map.  RemapValClamped with equal endpoints returns
		  the far value at or above them and the near value below
		  (mathlib RemapValClamped), which is what the degenerate branches here
		  reproduce -- a map that writes MinDist == MaxDist means "on beyond
		  this point", not "divide by zero".
		*/
		pset = spr_pset[i];
		gmn  = glowp_min[pset];
		gmx  = glowp_max[pset];
		gout = glowp_outer[pset];

		if (gout > gmx && dist > gmx)
			fade = 1 - (dist - gmx) / (gout - gmx);
		else if (gmx > gmn)
			fade = (dist - gmn) / (gmx - gmn);
		else
			fade = (dist >= gmx) ? 1 : 0;

		if (fade <= 0)
		{
			g_hidden = g_hidden + 1;
			gl_fade = gl_fade + 1;
			continue;
		}
		if (fade > 1)
			fade = 1;

		base = eye + toglow * GLOW_OVERLAYDIST;

		r = crossproduct(toglow, '0 0 1');
		if (r == '0 0 0')
		{
			// Dead overhead: no horizontal axis exists.  Counted as trace-hidden
			// rather than as nothing, because BUILD 55 relies on the four
			// outcomes summing to gl_seen -- a glow that leaves the loop without
			// incrementing any of them makes the line lie by omission, and a
			// debug line that does not add up is worse than no line.
			gl_hid = gl_hid + 1;
			continue;
		}
		r = normalize(r);
		u = normalize(crossproduct(r, toglow));

		r = r * spr_hw[i];
		u = u * spr_hh[i];

		a = base - r + u;
		b = base + r + u;
		c = base + r - u;
		d = base - r - u;

		/*
		  BUILD 58 -- TERM BY TERM, for the handful that actually reach the draw.

		  Two read-derived explanations for the flares' brightness have now died
		  (the arithmetic matches Source per channel; making the occlusion
		  fractional moved 0.00 luma because the ones that draw are fully
		  visible), and the project's own rule is that the third attempt is an
		  instrument, not another hypothesis. At Lex's vantage exactly 2 of 166
		  reach here, so this prints two lines and answers which factor is
		  carrying the +17.30.
		*/
		if (dbg)
		{
			/*
			  TWO prints, and that is not style: fteqcc caps a varargs call at
			  EIGHT parameters INCLUDING the format string, and silently drops
			  the rest. The first version of this passed eleven and printed the
			  colour as "0.00 0.00 0.00" -- which reads as a real and alarming
			  finding (an additive black quad contributes nothing, so the flares
			  could not be what was on screen) rather than as a broken print.
			  The cap is already documented forty lines up, in this same file.

			  Through a temporary because `spr_col[i]_x` is not a component
			  selector fteqcc accepts on an array element.
			*/
			print(sprintf("  glow %g: dist %g fade %.3f glare %.3f  half %gx%g\n",
			              i, dist, fade, glare, spr_hw[i], spr_hh[i]));
			gcol = spr_col[i];
			print(sprintf("           col %.3f %.3f %.3f  alpha %.3f -> %.3f\n",
			              gcol_x, gcol_y, gcol_z, spr_alpha[i], spr_alpha[i] * glare * fade));
		}

		/*
		  BUILD 58.  Into the COLOUR, because that is where Source carries a
		  glow's brightness -- glow_overlay.cpp:418 hard-wires the vertex alpha
		  to 1 and puts fade and obstruction in the RGB, precisely because the
		  blend is additive.  Under GL_SRC_ALPHA/GL_ONE the two are one product
		  anyway, so this is a scale on the result either way.
		*/
		gcol = spr_col[i] * glowscale;

		Sprite_Quad(a, b, c, d, GLOW_MATERIAL,
		            DRAWFLAG_ADD | DRAWFLAG_NODEPTHTEST,
		            gcol, spr_alpha[i] * glare * fade);
		drawn = drawn + 1;
		gl_drawn = gl_drawn + 1;
	}

	/*
	  The light shafts, all one material, so the whole set is one batch.

	  The quad is camera-facing about the beam's own axis -- the same
	  construction Zone_Quad uses for a thick line -- with the two widths and
	  the SHADEOUT alpha ramp applied at the two ends.
	*/
	for (i = 0; i < beam_n; i = i + 1)
	{
		mid = (beam_org[i] + beam_end[i]) * 0.5;
		dd = mid - eye;

		if (maxdist > 0 && vlen(dd) - beam_rad[i] > maxdist)
			continue;
		if (fwd * dd < -beam_rad[i])
			continue;

		side = crossproduct(normalize(beam_end[i] - beam_org[i]), normalize(dd));
		if (side == '0 0 0')
			continue;               // looking straight down the beam
		side = normalize(side);

		a = beam_org[i] - side * (beam_w0[i] * 0.5);
		b = beam_org[i] + side * (beam_w0[i] * 0.5);
		c = beam_end[i] + side * (beam_w1[i] * 0.5);
		d = beam_end[i] - side * (beam_w1[i] * 0.5);

		// Alpha at the source, zero at the far end: FBEAM_SHADEOUT with a fade
		// length equal to the reach, beamdraw.cpp:359-361.
		// s runs across the width, t along the length from the source outward.
		R_BeginPolygon(BEAM_MATERIAL, DRAWFLAG_ADD);
		R_PolygonVertex(a, '0 0 0', beam_col[i], BEAM_BRIGHTNESS);
		R_PolygonVertex(b, '1 0 0', beam_col[i], BEAM_BRIGHTNESS);
		R_PolygonVertex(c, '1 1 0', beam_col[i], 0);
		R_PolygonVertex(d, '0 1 0', beam_col[i], 0);
		R_EndPolygon();
		drawn = drawn + 1;
	}

	if (dbg)
	{
		print(sprintf("vbsp_sprite_debug: %g of %g passed the cull\n",
		              drawn, spr_n + beam_n));
		/*
		  BUILD 52.  COUNT WHAT THE GATE IS FILTERING, not just whether it ran.
		  `hidden` is the number the occlusion trace suppressed this frame; if it
		  is 0 from a vantage where glows are plainly behind walls, the trace is
		  not gating anything and the glares are drawing through the world --
		  which is the failure mode this feature can have, and it is invisible in
		  a screenshot taken facing the glows.
		*/
		if (useglare_on)
			print(sprintf("vbsp_sprite_debug: glare %g in frame, %g hidden by the trace, %g mid-fade\n",
			              g_total, g_hidden, g_fading));
		/*
		  BUILD 59, DENOMINATOR CORRECTED IN BUILD 60.  What the last frame of
		  Sprite_Glare actually did.

		  Every number here is counted, and the only derived one divides by the
		  quantity that actually sets the latency: the cursor advances once per
		  VISIT, so a full pass over spr_n sprites takes spr_n/visits frames.
		  Build 59 divided by glares TRACED, which silently assumed a culled
		  glare does not advance the cursor -- it does, for free, which is the
		  entire point of the cull.  That error made the cull look inert.

		  `culled` and `traced` are both printed against `visited` rather than
		  against the map total, because they are counted over the glares this
		  frame's budget actually reached, not over the map.  Reading them as
		  map-wide figures is the mistake that produced the wrong sweep.

		  The "no cull" comparison divides by traced, which is what visits would
		  collapse to if nothing were culled.  It ignores the non-glare sprites
		  that also cost a free visit, so it flatters the cull slightly less than
		  the truth -- the honest direction for a number that argues for my own
		  change.
		*/
		if (useglare_on)
			print(sprintf("vbsp_sprite_debug: glare sweep %g FRAMES measured (last full pass);"
			              " this frame %g of %g visited (%g culled, %g traced)\n",
			              spr_gsweep, spr_gvisits, spr_n, spr_gcull, spr_gtraced_n));
		/*
		  BUILD 60.  The adaptive rays, and the LAST number is the measurement:
		  rays/glare is what the 27.1us is multiplied by, so it is the only figure
		  here that can be compared against a cost.  `cheap` and `forced` are
		  there to show the mechanism is running AND that it is not sticky -- a
		  frame with cheap > 0 and forced == 0 forever would mean a glare can
		  never escape a stale 0, which is the one way this optimisation can be
		  wrong.  (forced is legitimately 0 on most frames; it is 1 in every
		  `adapt`+1 visits to a given glare, so read it over several frames.)

		  THE BASELINE IS READ, NOT ASSUMED.  It used to print a literal
		  "(5.00 unadapted)", which is false on any arm where vbsp_glare_rays 1
		  or vbsp_sprite_source 0 has already forced one ray per glare -- there
		  the line reported "1.00 rays/glare (5.00 unadapted)" and credited this
		  change with a 5x it had nothing to do with.  Three review lenses filed
		  it separately.  The line now prints the ray shape actually in force,
		  and says so when the shortcut cannot be running at all.

		  A NOTE ON `rays` EXCEEDING THE BUDGET BY UP TO 4: the loop test passes
		  at n == budget-1 and the glare it admits may then fire five, so 43 rays
		  against a budget of 40 is expected and is not a leak.  Build 59 had the
		  same +4, invisibly; only this line makes it legible.
		*/
		if (useglare_on && cvar("vbsp_glare_adaptive") >= 1)
		{
			// `raybase`, not `base`: Sprite_Draw already has a `vector base`.
			local float raybase;
			raybase = (cvar("vbsp_glare_rays") > 1 && cvar("vbsp_sprite_source")) ? 5 : 1;
			print(sprintf("vbsp_sprite_debug: glare adaptive %g cheap, %g forced full, %g rays"
			              " for %g traced -> %.2f rays/glare (%.2f unadapted%s)\n",
			              spr_gcheap, spr_gforce, spr_grays, spr_gtraced_n,
			              (spr_gtraced_n > 0) ? spr_grays / spr_gtraced_n : 0,
			              raybase, (raybase > 1) ? "" : ", so the shortcut is inert here"));
		}
		/*
		  BUILD 61.  The interval budget, and the point of the line is the LAST
		  field.  Everything else here is an input; "stopped by" is the only
		  thing that says whether the interval is actually being honoured:

		    the interval quota   the promise is being kept, and the ray ceiling
		                         has headroom -- this is the healthy state
		    THE RAY CEILING      the map wants more rays than vbsp_glare_traces
		                         allows, so the real staleness is WORSE than the
		                         interval asks.  Read the measured sweep line
		                         above for what it actually is; do not trust the
		                         interval on this frame.
		    running out of map   the whole map was visited inside the quota, so
		                         the interval is finer than it needs to be here
		                         and rays are being spent on re-answers.

		  Printed only when the interval is in use; with vbsp_glare_interval 0
		  the sweep line above is the whole story and this would just be noise.
		*/
		if (useglare_on && cvar("vbsp_glare_interval") > 0)
		{
			local string glimtxt;
			if (spr_glimit == 1)
				glimtxt = "THE RAY CEILING (interval not met)";
			else if (spr_glimit == 2)
				glimtxt = "the interval quota";
			else
				glimtxt = "running out of map (interval finer than needed)";
			print(sprintf("vbsp_sprite_debug: glare interval %gs -> quota %g visits,"
			              " used %g, %g rays of %g allowed, stopped by %s\n",
			              cvar("vbsp_glare_interval"), spr_gquota, spr_gvisits,
			              spr_grays, cvar("vbsp_glare_traces"), glimtxt));
		}
		/*
		  BUILD 54.  The env_lightglow half on its own, because the line above
		  mixes it with the billboards and cannot say which gate is eating them.
		  Read left to right: how many glows the loop reached, then each way out
		  of it in the order they are tested, then how many quads were emitted.
		  Every one of the 166 has to appear in exactly one of the last four
		  numbers, so a total that does not add up is itself the answer.
		*/
		print(sprintf("vbsp_sprite_debug: glows %g reached, %g one-sided away, %g trace-hidden, %g out of fade range, %g drawn\n",
		              gl_seen, gl_side, gl_hid, gl_fade, gl_drawn));
	}
};

/*
  Called from CSQC_WorldLoaded, which is where reading the entity lump belongs.

  The lazy serverkey("map") compare in Sprite_Draw stays as the safety net for
  the paths that never reach that hook -- demo playback among them -- exactly as
  Portal_Poll does.  Once this has run the compare matches and costs one string
  test a frame.
*/
void() Sprite_LoadFromWorld =
{
	Sprite_LoadForMap();
};
