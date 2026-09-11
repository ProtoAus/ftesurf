#!/usr/bin/env python3
"""
pcf.py -- bake a Source .pcf particle library into an FTE `r_part` config.

WHY THIS IS OFFLINE.  QuakeC cannot read a binary file and the engine has no
PCF loader, so the translation has to happen before the game runs.  That is the
same shape as the two tools beside this one: mapdeps.py bakes data/mapdeps.txt
and mapmeta.py bakes data/mapmeta.txt.  This bakes particles/<map>.cfg plus a
line in data/mapparticles.txt.

WHAT GOES WHERE, and the split is forced rather than chosen.  cl_emit.qc's
header explains it: pointparticles(effect, org, dir, count) has exactly three
degrees of freedom.

    particles/<map>.cfg   the LOOK -- texture, blend, colour, alpha, scale,
                          lifetime, gravity, friction, and the spawn BOX (an
                          r_part block can express `spawnorg`, so the box does
                          not have to come back through QC)
    data/mapparticles.txt the three things QC still has to supply -- the base
                          velocity to pass as `dir`, the emission rate, and the
                          particle ceiling that caps it
                          -- plus, since build 53, the box centre, a world-frame
                          velocity, the isotropic jitter (random_speed, and the
                          random-walk RMS of a random force) and the parent link
                          for child systems (eighteen columns)

`veladd 1` in every block, so the vector QC passes as `dir` IS the velocity in
units/sec (p_script.c:5230-5235).  Same contract as ftesurf.cfg; changing it
silently rescales every emitter.

THE EMISSION RATE IS NOT emission_rate.  A Source system with
emission_rate 800 and max_particles 1500 over a 10s lifetime cannot sustain 800
-- it saturates at max_particles/lifetime = 150/s and Source simply stops
emitting.  Baking the nominal 800 would ask the engine for 8000 live particles
where the author asked for 1500, so the rate written out is the MINIMUM of the
two.  This is the single most important number in the file: it is what stops a
faithful translation from being five times heavier than the thing it copies.

REFUSE, DO NOT GUESS.  Every operator the translator does not understand is
counted and reported, and --strict makes an unknown one an error.  A partial
translation of a particle system does not look broken, it looks like a different
effect, which is exactly the failure this project keeps writing essays about.

"UNDERSTOOD" IS NOT THE SAME AS "TRANSLATED", and v1 of this tool blurred the
two.  It reported "every operator understood" for surf_tensor2 while writing
`scale 0` for all three portal systems, because being in the KNOWN set only
means the operator's NAME was recognised.  Reported as "the particles near the
portals are very tiny and white and very inactive"; five separate things were
wrong at once and each is written up where it is fixed:

  * TWO `Radius Scale` operators, and only the first was read.  Its
    radius_start_scale is 0, so every particle was born at zero size, and the
    growth was declined too because the ratio it wanted to take was 0.5/0.0.
  * `scalefactor` in FTE selects DISTANCE scaling, not growth.  Every block
    written without one has been drawing at a constant SCREEN size rather than
    a constant world size, which is not what Source does.  Growth belongs in
    `scaledelta`; `scalefactor 1` is now written on every block.
  * `scale` is not a diameter.  The renderer draws a diamond of half-diagonal
    scale*0.25, so a Source radius r needs 4r, not 2r.
  * `Position Within Sphere Random` carries the OUTWARD SPEED beside the radius
    and it was being dropped, so the portal clouds never moved.  FTE's
    `spawnmode ball` gives position and velocity the same random direction,
    which is the same construction, so this maps exactly.
  * `Color Random` was averaged to one flat colour, and its `tint_perc` was
    ignored.  rgbrand + rgbrandsync 1 is FTE's own spelling of the same lerp.

THREE OPERATORS THAT ARE NOT VELOCITIES, and v2 folded two of them into one.
v2 collapsed both Velocity Noise and random force into a single randomvel
scalar -- 20.25 on the portals, which is a persistent 20 u/s per-particle
velocity that neither operator describes.  Velocity Noise is a time-varying
velocity with a per-axis mean, in the control point's LOCAL frame when its
flag says so, and it now goes out as the local velocity column (rotated by the
entity's angles in cl_emit.qc) with its half-range in the local spread.
random force is a per-frame random ACCELERATION re-drawn every frame: a random
walk with zero mean whose velocity after time T has RMS a_rms*sqrt(dt*T), which
is about 3 u/s on the portals rather than 20, and it goes out through the
index's jit column (the same channel random_speed uses).  Alpha Fade In Random
is read and reported but not translated: FTE has one linear alphadelta.  All
three are counted in the report, because a partial translation must say so.
"""
import argparse, collections, io, math, os, re, struct, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx


# --------------------------------------------------------------- BSP pakfile
def bsp_pak(path):
    """The map's embedded pakfile (lump 40), as a ZipFile."""
    with open(path, "rb") as f:
        f.seek(8)
        hdr = f.read(16 * 64)
        off, ln, _ver, _fcc = struct.unpack_from("<4i", hdr, 16 * 40)
        if ln <= 0:
            return None
        f.seek(off)
        return zipfile.ZipFile(io.BytesIO(f.read(ln)))


def pcfs_in_map(bsp):
    z = bsp_pak(bsp)
    if not z:
        return []
    return [n for n in z.namelist() if n.lower().endswith(".pcf")], z


# ------------------------------------------------------------- the translator
# Operators this understands.  Anything absent is reported, never assumed.
KNOWN = {
    "emit_continuously", "emit_instantaneously",
    "Lifetime Random", "Radius Random", "Alpha Random", "Color Random",
    "Rotation Random", "Rotation Spin Roll", "Radius Scale",
    "Velocity Random", "Velocity Noise", "random force",
    "Position Within Box Random", "Position Within Sphere Random",
    "Position Modify Offset Random",
    "Movement Basic", "Movement Max Velocity", "Lifespan Decay",
    "Alpha Fade Out Random", "Alpha Fade In Random", "Alpha Fade and Decay",
    "Collision via traces",
    "render_sprite_trail", "render_animated_sprites", "render_rope",
}

# render_sprite_trail draws a stretched streak; PT_TEXTUREDSPARK is FTE's.
# render_animated_sprites is an ordinary camera-facing billboard.
RENDERER_TYPE = {
    "render_sprite_trail": "texturedspark",
    "render_animated_sprites": None,          # PT_NORMAL, the default
    "render_rope": None,
}


def ops(d, e, key):
    return [d.elements[i] for i in (e.get(key) or [])]


def find(d, e, key, fn):
    for o in ops(d, e, key):
        if o.get("functionName") == fn:
            return o
    return None


class Untranslated(Exception):
    pass


def translate(d, e, unknown, mapname):
    """One DmeParticleSystemDefinition -> (cfg block text, runtime fields)."""
    name = e.name

    for key in ("emitters", "initializers", "operators", "renderers",
                "forces", "constraints"):
        for o in ops(d, e, key):
            fn = o.get("functionName")
            if fn not in KNOWN:
                unknown[fn] += 1

    # ---- lifetime
    lt = find(d, e, "initializers", "Lifetime Random")
    die_lo = float(lt.get("lifetime_min", 1.0)) if lt else 1.0
    die_hi = float(lt.get("lifetime_max", die_lo)) if lt else 1.0
    if die_hi < die_lo:
        die_lo, die_hi = die_hi, die_lo
    if die_hi <= 0:
        raise Untranslated("lifetime is zero")

    # ---- size.
    # `Radius Random` carries ABSOLUTE radii in world units -- verified across
    # this library: rain is 1..1 and water_splash01 is 50..60, which are a
    # raindrop and a splash at face value.  The definition's own `radius` field
    # is only the fallback for a system that has no such initializer
    # (water_splash02, radius 10).  Multiplying the two double-counts and made
    # rain 10 units wide; they are alternatives, not factors.
    rr = find(d, e, "initializers", "Radius Random")
    if rr:
        r_lo = float(rr.get("radius_min", 1.0))
        r_hi = float(rr.get("radius_max", r_lo))
    else:
        r_lo = r_hi = float(e.get("radius", 5.0))
    if r_hi < r_lo:
        r_lo, r_hi = r_hi, r_lo

    # ---- `Radius Scale`, and a system may carry MORE THAN ONE.
    #
    # THIS IS THE BUG THAT MADE surf_tensor2'S PORTALS INVISIBLE.  The old code
    # took find()'s FIRST match and read its radius_start_scale as the size at
    # birth.  portal_blue has two:
    #
    #     op1  t 0.0 -> 0.2   scale 0.0 -> 0.5
    #     op2  t 0.2 -> 1.0   scale 0.5 -> 2.0
    #
    # so it read start_scale 0.0, multiplied every radius by it, and wrote
    # `scale 0`.  The `if s0 > 0` guard below it then declined to carry any
    # growth either, because 0.5/0.0 is not a number -- so the particles were
    # born at zero size and stayed there for their whole 0.9s life.  That is
    # exactly the report: "very tiny and white and very inactive".
    #
    # The two operators are laid END TO END, which is how the Hammer UI presents
    # them and the only reading under which writing two of them means anything:
    # each governs the slice of the lifetime between its own start_time and
    # end_time, and a later one that actually covers t wins over an earlier one
    # that is merely clamped there.
    #
    # HONEST ABOUT THE UNCERTAINTY: Valve's own C_OP_RadiusScale is in
    # src/particles/, which is NOT in the public tree this project cites, so
    # this composition is inferred from the data rather than read from the
    # source.  The alternative reading -- every operator SETS radius from the
    # initial radius each frame, so the last one wins at every t -- gives 0.5 at
    # birth instead of 0.0 and the same 2.0 at death.  Both readings agree that
    # the size GROWS and that it is never zero for the whole life, which is the
    # part that was broken; they differ only in the first 20% of one system.
    rs_ops = [o for o in ops(d, e, "operators")
              if o.get("functionName") == "Radius Scale"]

    def radius_scale_at(t):
        v, covered = 1.0, False
        for o in rs_ops:
            t0 = float(o.get("start_time", 0.0))
            t1 = float(o.get("end_time", 1.0))
            s0 = float(o.get("radius_start_scale", 1.0))
            s1 = float(o.get("radius_end_scale", 1.0))
            if t1 <= t0:
                continue                      # degenerate window; nothing to ramp
            if t0 <= t <= t1:
                v = s0 + (s1 - s0) * (t - t0) / (t1 - t0)
                covered = True
            elif not covered:
                v = s0 if t < t0 else s1      # clamped, and only as a fallback
        return v

    s_birth = radius_scale_at(0.0)
    s_death = radius_scale_at(1.0)

    # THE CONVERSION IS 4*sqrt(2), AND THE sqrt(2) IS THE WHOLE POINT.
    #
    # Reported as "they are slightly to small".  They were, by exactly 1.414.
    #
    # FTE builds the quad from four points at distance `scale` from the centre,
    # each 90 degrees apart (p_script.c:7030-7053 -- the rotated arm uses
    # x=sin(a)*scale, y=cos(a)*scale so every vertex is sqrt(x^2+y^2) = scale
    # out, and the unrotated arm is the same four points at a fixed angle).
    # That is a SQUARE with circumradius `scale`, not a shape of width `scale`.
    #
    # The texcoords are the texture's four CORNERS, so the texture's corners land
    # on those vertices -- which means the texture's own half-width, the thing a
    # viewer actually measures, is scale/sqrt(2), not scale.  Source draws a quad
    # of half-width = radius with the texture filling it, so matching texture to
    # texture:
    #
    #     p->scale * 0.25 / sqrt(2) = r   ->   p->scale = 4*sqrt(2)*r = 5.657r
    #
    # (0.25 because `scalefactor 1`, emitted unconditionally below, selects
    # p_script.c:6326's `scale = p->scale*0.25`.)
    #
    # THE OLD 4x WAS RIGHT ABOUT THE DIAMOND AND WRONG ABOUT WHAT IS DRAWN IN IT.
    # Its comment reasoned from the diamond's vertex-to-vertex span, which is the
    # texture's DIAGONAL; the sprite you see is bounded by the texture's edges.
    # Every particle in the library has been 1/sqrt(2) = 71% of its Source size.
    # The correction is texture-space to texture-space, so it holds whatever the
    # texture contains -- a soft radial blob and a hard-edged square are scaled
    # by the same factor.
    QUAD = 4.0 * math.sqrt(2.0)
    scale_lo = r_lo * s_birth * QUAD
    scale_hi = r_hi * s_birth * QUAD
    r_mid_birth = (r_lo + r_hi) * 0.5 * s_birth
    r_mid_death = (r_lo + r_hi) * 0.5 * s_death
    # scaledelta is FTE's real growth control: p->scale += frametime*scaledelta
    # (p_script.c:7619), i.e. units per second, applied to every particle alike.
    # Source scales each particle's OWN radius, so this is the mean curve rather
    # than a per-particle one -- the difference is invisible unless radius_min
    # and radius_max are far apart.  Same QUAD, because it is the same conversion
    # per second -- using the old 4.0 here would make particles that grow drift
    # away from their own birth size.
    scaledelta = (r_mid_death - r_mid_birth) * QUAD / max(die_hi, 0.01)

    if scale_hi <= 0.001 and scaledelta <= 0.001:
        raise Untranslated("radius is zero for the whole lifetime")

    # ---- colour and alpha
    #
    # `Color Random` picks a per-particle colour between color1 and color2, and
    # FTE has the same idea spelled differently: rgbrand is the RANGE and
    # rgbrandsync is how CORRELATED the three channels are, 1 meaning all three
    # take the same random number (p_script.c:4769-4774).  So
    #
    #     rgb c1 ; rgbrand (c2-c1) ; rgbrandsync 1
    #
    # is a synchronised lerp along the line c1..c2, which is the same thing.
    # FTE's own colour-range helper writes exactly this pair (p_script.c:
    # 3234-3235), so it is the engine's idiom and not a trick.  Negative
    # components are fine: the byte form is parsed as (c2-c1)/255 with no clamp.
    #
    # AVERAGING THEM, WHICH IS WHAT THIS USED TO DO, throws the whole effect
    # away on the systems that care.  portal_blue ramps [51 51 80] to
    # [0 96 255] -- dark navy to saturated blue -- and the mean of those is one
    # flat mid-blue for every particle.  That is a large part of "they are white
    # and inactive": a cloud with no colour variance reads as a single tone.
    col = e.get("color", [255, 255, 255, 255])
    cr = find(d, e, "initializers", "Color Random")
    rgbrand = None
    if cr:
        c1 = [int(x) for x in cr.get("color1", col)[:3]]
        c2 = [int(x) for x in cr.get("color2", col)[:3]]
        # `tint_perc` IS DELIBERATELY IGNORED, and this note is here because the
        # first version of this file did not ignore it and was wrong.
        #
        # The report said the portals are "blue, and expanding to white colour",
        # so tint_perc 0.4 -- present on all three portal systems -- looked like
        # the missing white: blend the picked colour 40% toward the tint control
        # point, and an unset control point is white.  That was INFERRED, not
        # read; Valve's C_INIT_RandomColor lives in src/particles/, which this
        # tree does not have.  It shipped, and the next thing reported was
        # "they don't have a cool blue hue like in source" -- which is what 40%
        # toward white does to a colour that ramps from [51 51 80] to
        # [0 96 255]: it lifts the dark end to a light grey and desaturates the
        # bright end to a pale blue, so the whole cloud reads as white.
        #
        # So the inference is dropped rather than tuned.  The `tint clamp min`
        # [108 108 108] / `max` [76 76 76 125] pair beside it has min ABOVE max
        # on every one of these systems, which is not a range and not something
        # to guess a second time.  The authored colours go through untouched and
        # the material's own white core supplies whatever white there is.
        col = list(c1) + list(col[3:4])
        if c1 != c2:
            rgbrand = [b - a for a, b in zip(c1, c2)]
    rgb = [max(0, min(255, int(c))) for c in col[:3]]

    ar = find(d, e, "initializers", "Alpha Random")
    if ar:
        a_lo = float(ar.get("alpha_min", 255)) / 255.0
        a_hi = float(ar.get("alpha_max", 255)) / 255.0
    else:
        a_lo = a_hi = (float(col[3]) / 255.0 if len(col) > 3 else 1.0)
    alpha = (a_lo + a_hi) * 0.5
    alpharand = abs(a_hi - a_lo) * 0.5

    alphadelta = 0.0
    if find(d, e, "operators", "Alpha Fade Out Random") or \
       find(d, e, "operators", "Alpha Fade and Decay"):
        alphadelta = -alpha / max(die_hi, 0.05)

    # Alpha Fade In Random ramps each particle's alpha from 0 to its own value
    # over a per-particle random time ("fade in time min"/"max", a fraction of
    # the lifetime when "proportional 0/1" is set).  The keys are read so a
    # malformed operator is at least seen, but the output is NOT changed: FTE
    # has exactly one alphadelta, a signed linear rate applied for the whole
    # life, and the portals (and every Alpha Fade Out system) already spend it
    # on the fade-out.  A fade-in cannot be expressed on the same particle, and
    # the previous version's silence about that is why it is counted here.
    afi = find(d, e, "operators", "Alpha Fade In Random")
    if afi:
        fi_lo = float(afi.get("fade in time min", 0.0) or 0.0)
        fi_hi = float(afi.get("fade in time max", fi_lo) or 0.0)
        fi_prop = bool(afi.get("proportional 0/1", True))
        if fi_hi > 0 or fi_lo > 0:
            unknown["(Alpha Fade In Random: unrepresented; FTE has one linear "
                    "alphadelta and its lerp ramp discards the size spread)"] += 1

    # ---- movement
    mv = find(d, e, "operators", "Movement Basic")
    grav = 0.0
    drag = 0.0
    if mv:
        g = mv.get("gravity", [0, 0, 0])
        # FTE gravity is a scalar down the world Z.  Source's is a vector; the
        # horizontal part is wind and is folded into the base velocity below.
        grav = -float(g[2])
        drag = float(mv.get("drag", 0.0) or 0.0)

    # ---- base velocity and the random spread.
    #
    # TWO FRAMES, AND THEY ARE WRITTEN TO TWO DIFFERENT COLUMNS.  'Velocity
    # Random' is in the CONTROL POINT's local frame -- the name of its key says
    # so -- and control point 0 of an info_particle_system carries the entity's
    # angles (particle_property.cpp:644-645 GetVectors, :669
    # SetControlPointOrientation, under PATTACH_ABSORIGIN_FOLLOW from
    # c_particle_system.cpp:134).  surf_boreas' tendies_snow01 is the proof:
    # local X is -256..-512 and the entity is pitched -90, so forward is UP and
    # the snow FALLS; its sibling tendies_snowinst01 pre-fills a column 6000
    # units below the same point, which is 16s of fall at 384 -- the box is
    # world-space, the velocity is local.  Handing (-384, 0, 0) to the engine
    # unrotated, as the old single column did, blows the snow sideways along
    # world -X forever.  cl_emit.qc rotates this column by the entity's angles;
    # the wind and the terminal velocity below are world-space and go in the
    # second column, which it adds unrotated.  surf_tensor2 is unaffected for a
    # narrower reason than 'its entities are unrotated' -- 27 of its 44 carry
    # a yaw of 90, 180 or 270 -- every one of its local velocities is pure Z
    # and none of its entities has pitch or roll, and a yaw leaves 'up' alone.
    vr = find(d, e, "initializers", "Velocity Random")
    vmin = vr.get("speed_in_local_coordinate_system_min", [0, 0, 0]) if vr else [0, 0, 0]
    vmax_ = vr.get("speed_in_local_coordinate_system_max", [0, 0, 0]) if vr else [0, 0, 0]
    basevel = [(float(a) + float(b)) * 0.5 for a, b in zip(vmin, vmax_)]
    spread = [abs(float(b) - float(a)) * 0.5 for a, b in zip(vmin, vmax_)]
    worldvel = [0.0, 0.0, 0.0]

    # random_speed_min/max is a SECOND, ISOTROPIC term: a random speed in a
    # random direction, added on top of the local vector.  The initializer
    # itself is in the closed particle lib, so that sum is Valve's own
    # documentation of the key rather than code read here, and the sign is
    # meaningless (a negative speed along a random direction is the same set of
    # directions).  Only boreas' snow carries one in this library (-256..-512
    # beside local X -256..-512): a swirl of 256-512 u/s on top of the fall,
    # which is what makes it a blizzard rather than a laminar curtain.  It goes
    # out as a per-axis jitter for cl_emit.qc's em_jit (Emit_RandDir is a
    # cube, not a shell) and is counted below so the report says so; it used
    # to be dropped without a word.
    rs_lo = abs(float(vr.get("random_speed_min", 0.0) or 0.0)) if vr else 0.0
    rs_hi = abs(float(vr.get("random_speed_max", 0.0) or 0.0)) if vr else 0.0
    jit = (rs_lo + rs_hi) * 0.5
    if jit > 0.5:
        unknown["(random_speed: isotropic term approximated as per-axis jitter %g)" % jit] += 1

    # Velocity Noise is a velocity that varies with time and position between
    # its two output vectors -- an initializer, so it is the particle's birth
    # velocity as sampled from a noise field.  What FTE can carry is its MEAN
    # per axis (the half-range goes in the spread), and the frame it is in is
    # the flag's to say: "Apply Velocity in Local Space" true means the control
    # point's frame, i.e. the same frame as Velocity Random and the same index
    # column, the one cl_emit.qc rotates by the entity's angles (Emit_PsysVel).
    # THIS IS WHAT MOVES THE PORTALS TOWARD THE SPAWN.  All three portal systems
    # carry [5 0 0]..[2 0 0] local: 3.5 u/s along the entity's forward, and the
    # info_particle_system entities on surf_tensor2 point their forward at the
    # spawn.  v2 read only the largest magnitude (5) and wrote it as a
    # direction-less randomvel, which is a different effect.  A false flag is
    # world space and goes in the world column, unrotated.
    vn = find(d, e, "initializers", "Velocity Noise")
    if vn:
        n_lo = [float(x) for x in vn.get("output minimum", [0, 0, 0])]
        n_hi = [float(x) for x in vn.get("output maximum", [0, 0, 0])]
        n_local = bool(vn.get("Apply Velocity in Local Space (0/1)", True))
        for i in range(3):
            mean_i = (n_lo[i] + n_hi[i]) * 0.5
            if n_local:
                basevel[i] += mean_i
                spread[i] += abs(n_hi[i] - n_lo[i]) * 0.5
            else:
                worldvel[i] += mean_i
        if any(abs(a) > 0.01 or abs(b) > 0.01 for a, b in zip(n_lo, n_hi)):
            unknown["(Velocity Noise: time-varying term approximated by its mean)"] += 1

    # ---- spawn volume, and for a SPHERE also the outward speed
    #
    # THE OUTWARD SPEED WAS BEING DROPPED ENTIRELY, and it is the other half of
    # "very inactive".  `Position Within Sphere Random` carries speed_min and
    # speed_max beside distance_max, and in Source they are the speed the
    # particle is given ALONG THE RADIUS -- that is the whole "drifting away
    # from the centre point" the portals do.  The old translator read
    # distance_max, called it a box, and never looked at the two speeds, so
    # every portal particle was born motionless in a 64-unit cube and stayed
    # where it was put.
    #
    # FTE expresses this natively and the mapping is exact rather than
    # approximate.  `spawnmode ball` picks a random unit vector, scales it by
    # frandom() to fill the ball, and then uses THAT SAME VECTOR for both the
    # position offset and the velocity (p_script.c:4554-4578):
    #
    #     arsvec = ofsvec * spawnorg      <- where it appears
    #     ovel  += ofsvec * spawnvel      <- which way it goes
    #
    # so spawnvel IS a radial speed.  One difference worth writing down: FTE
    # scales the velocity by the same frandom() that placed the particle, so a
    # particle born near the centre also moves slower, where Source draws its
    # speed independently of its position.  The cloud looks the same; a single
    # particle's path does not.
    #
    # THE BOX: half-extents AND the centre.
    #
    # ABS, because Hammer's particle editor lets the author type min > max and
    # this library does: tendies_snow01 is min (512, 4096, 0) max (-512, -4096,
    # 0), and tensor2's stage6_rain, stage9_rain01, bonus4_rain and bonus3_rain
    # are the same way round.  The old subtraction made every half-extent
    # negative, the '> 0.5' test below then failed, and all five were baked as
    # POINT emitters -- 'spawnorg 0' -- for volumes up to 4880 x 18096 units.
    # The centre is kept too: stage7_rain01 is a sheet 1000 above its entity
    # and tendies_endparticle04 sits 456 below its; both used to collapse onto
    # the control point.  FTE has no world-space offset in an r_part block, so
    # the centre goes out through the index for QC to add to the origin.
    box = [0.0, 0.0, 0.0]
    ofs = [0.0, 0.0, 0.0]
    ball = False
    radial = 0.0
    pb = find(d, e, "initializers", "Position Within Box Random")
    if pb:
        mn = pb.get("min", [0, 0, 0])
        mx = pb.get("max", [0, 0, 0])
        box = [abs(float(b) - float(a)) * 0.5 for a, b in zip(mn, mx)]
        ofs = [(float(a) + float(b)) * 0.5 for a, b in zip(mn, mx)]
    else:
        ps = find(d, e, "initializers", "Position Within Sphere Random")
        if ps:
            r = float(ps.get("distance_max", 0.0))
            box = [r, r, r]
            ball = True
            radial = (float(ps.get("speed_min", 0.0)) +
                      float(ps.get("speed_max", 0.0))) * 0.5

    # ---- horizontal acceleration becomes an initial velocity, because FTE's
    # `gravity` is a scalar down world Z and cannot express wind.
    #
    # THE EFFECTIVE TIME IS NOT THE LIFETIME, and using the lifetime is wrong by
    # an order of magnitude.  spawn_rain01 declares die 10 but kills on
    # collision, and falling at ~2000 u/s through a 1040-unit box it lives about
    # half a second -- so folding 400 u/s^2 of wind over 10s gave a 2000 u/s
    # sideways drift where the map asks for about 100.  Bound it by the time to
    # fall through the emitter's own box instead, which is the only physical
    # quantity available here.  This is the one place the translation is an
    # approximation rather than a transcription.
    t_eff = die_hi
    if abs(basevel[2]) > 1.0 and box[2] > 1.0:
        t_eff = min(t_eff, (box[2] * 2.0) / abs(basevel[2]))
    t_eff = min(t_eff, 2.0)

    # random force is a per-frame random ACCELERATION: every simulation frame
    # each particle draws a fresh force uniformly between min and max and is
    # accelerated by it for that frame.  It is NOT a persistent velocity, which
    # is what v2 made of it -- it folded the +/-45 spread of the portals into
    # randomvel 20.25, a 20 u/s random velocity fixed at birth, and that is
    # what scattered the portal clouds instead of making them shimmer.
    #
    # Two parts.  The MEAN, non-zero only for an asymmetric force (rain_heavy's
    # [5 -5 0]..[35 -45 0] is the one case here), is a steady acceleration and
    # is integrated over the effective time as before, into the world column.
    # The SPREAD is a random walk with zero mean: a per-frame kick of a*dt with
    # a uniform on [-h, h] has RMS h/sqrt(3), and after T/dt independent kicks
    # the velocity's RMS is a_rms*dt*sqrt(T/dt) = a_rms*sqrt(dt*T), with dt the
    # Source tick (1/66) and T bounded by t_eff.  For the portals that is
    # 45/sqrt(3)*sqrt(0.9/66), about 3 u/s, an order of magnitude below v2's
    # 20.  FTE cannot re-draw an acceleration per frame, so the walk is
    # approximated by a fixed per-particle velocity of that RMS, handed out as
    # jit -- cl_emit.qc's em_jit, the same isotropic channel random_speed
    # feeds -- and NOT as randomvel.  An approximation, counted as one.
    rf = find(d, e, "forces", "random force")
    if rf:
        fmin = [float(x) for x in rf.get("min force", [0, 0, 0])]
        fmax = [float(x) for x in rf.get("max force", [0, 0, 0])]
        for i in range(3):
            worldvel[i] += (fmin[i] + fmax[i]) * 0.5 * t_eff * 0.5
        a_rms = sum(abs(b - a) / (2.0 * 3.0 ** 0.5) for a, b in zip(fmin, fmax)) / 3.0
        walk = a_rms * (t_eff / 66.0) ** 0.5
        if walk > 0.01:
            jit += walk
            unknown["(random force: random walk approximated by a fixed "
                    "per-particle velocity of %.3g u/s)" % walk] += 1

    # 'Movement Max Velocity' clamps |vel| every tick.  Nine of boreas' fourteen
    # systems pair it with a gravity of 999 or 99999 UP and a cap of 4..512:
    # in Source the particle hits the cap within a few milliseconds and then
    # RISES AT THE CAP for the rest of its life.  FTE has no clamp, so baking
    # the gravity alone turns a 64 u/s puff into a 6000 u/s rocket over its 6s
    # lifetime.  When the cap is reached inside the lifetime the honest
    # translation is a constant world velocity of 'cap' along the gravity
    # vector and no gravity at all; when it is not, the gravity stands and the
    # cap only bounds the initial speed.
    mxv = find(d, e, "operators", "Movement Max Velocity")
    cap = float(mxv.get("Maximum Velocity", 0.0) or 0.0) if mxv else 0.0
    terminal = False
    if mv and cap > 0:
        g = [float(x) for x in mv.get("gravity", [0, 0, 0])]
        gmag = (g[0] ** 2 + g[1] ** 2 + g[2] ** 2) ** 0.5
        if gmag > 0 and gmag * die_hi > cap:
            for i in range(3):
                worldvel[i] += g[i] / gmag * cap
            grav = 0.0
            terminal = True
    if cap > 0:
        bmag = (basevel[0] ** 2 + basevel[1] ** 2 + basevel[2] ** 2) ** 0.5
        if bmag > cap:
            basevel = [v * cap / bmag for v in basevel]
    if mv and not terminal:
        g = mv.get("gravity", [0, 0, 0])
        for i in (0, 1):
            worldvel[i] += float(g[i]) * t_eff * 0.5

    # ---- rate, capped by the particle ceiling (see the header)
    em = find(d, e, "emitters", "emit_continuously")
    nominal = float(em.get("emission_rate", 0.0)) if em else 0.0
    maxp = float(e.get("max_particles", 0) or 0)
    ceiling = maxp / die_hi if maxp > 0 else nominal
    rate = min(nominal, ceiling) if nominal > 0 else 0.0
    if rate <= 0:
        raise Untranslated("not a continuous emitter (rate 0)")

    # ---- look
    mat = (e.get("material") or "").replace("\\", "/")
    mat = re.sub(r"\.vmt$", "", mat, flags=re.I)
    if not mat:
        raise Untranslated("no material")

    rend = ops(d, e, "renderers")
    rtype = RENDERER_TYPE.get(rend[0].get("functionName")) if rend else None

    coll = find(d, e, "constraints", "Collision via traces")
    kill = bool(coll and coll.get("kill particle on collision", False))

    maxdist = float(e.get("maximum draw distance", 0.0) or 0.0)

    # A PREFIX, NOT A NAMESPACE, and that is the whole reason this reads
    # `<map>_<effect>`.  Asking for "surf_tensor2.spawn_rain01" makes
    # PScript_FindParticleType split on the dot and auto-load
    # particles/surf_tensor2.cfg -- and P_LoadParticleSet records the config
    # name at p_script.c:3709 BEFORE it tries FS_LoadFile at :3746, then refuses
    # every retry at :3702-3707.  One early miss is permanent for the session,
    # silent, and unrecoverable; emitting through the unresolved handle is a
    # safe no-op, so everything downstream reports perfect health into a dead
    # pool.  That is exactly how particles/ftesurf.cfg drew nothing from build
    # 49 to 2026-09-08 without anyone noticing.
    #
    # With no dot there is no namespace to auto-load: the effect is found by
    # plain name (p_script.c:649-660) out of whatever has been exec'd, and
    # cl_emit.qc execs this file itself at map load.  A missing file is then a
    # visible exec error rather than silence.
    L = ["r_part %s_%s" % (mapname, name), "{"]
    L.append('\ttexture "%s"' % mat)
    if rtype:
        L.append("\ttype %s" % rtype)
    L.append("\tblend blendalpha")
    if abs(scale_hi - scale_lo) > 0.01:
        L.append("\tscale %.3g %.3g" % (scale_lo, scale_hi))
    else:
        L.append("\tscale %.3g" % scale_lo)
    # ALWAYS, AND IT IS NOT WHAT THE NAME SUGGESTS.  FTE's `scalefactor` is not
    # a growth factor at all -- it selects how a particle's size relates to its
    # DISTANCE from the viewer (p_script.c:6325-6336):
    #
    #     scalefactor 1  ->  scale = p->scale*0.25              constant in the world
    #     otherwise      ->  scale = viewdist*p->scale*(1-sf) + p->scale*sf*250
    #                        clamped, then 0.25 + scale*0.001   constant on the SCREEN
    #
    # and the default when the key is absent is 0 (P_ResetToDefaults memsets),
    # i.e. the screen-space arm.  So every block this tool has ever written
    # without a scalefactor line -- which is all but three of them -- has been
    # drawing particles whose world size grows with distance.  Source's are
    # constant in the world, so `scalefactor 1` is the right answer for every
    # one of them and the growth goes in scaledelta below, which is the key that
    # really does mean growth.
    #
    # The old code emitted `scalefactor <end/start ratio>` on three blocks, and
    # a value >1 does not even survive the parser: FinishParticleType folds it
    # into scale and resets it to 1 (p_script.c:2856-2862), so `scalefactor 2`
    # silently meant "twice as big", never "grows to twice the size".
    L.append("\tscalefactor 1")
    if scaledelta > 0.001 or scaledelta < -0.001:
        L.append("\tscaledelta %.4g" % scaledelta)
    L.append("\trgb %d %d %d" % tuple(rgb))
    if rgbrand:
        # rgbrandsync 1 = all three channels take the SAME random number, which
        # is what makes this a lerp along c1..c2 instead of an independent
        # per-channel jitter.  See the essay above.
        L.append("\trgbrand %d %d %d" % tuple(rgbrand))
        L.append("\trgbrandsync 1")
    L.append("\talpha %.3g" % alpha)
    if alpharand > 0.005:
        L.append("\talpharand %.3g" % alpharand)
    if alphadelta < -0.001:
        L.append("\talphadelta %.3g" % alphadelta)
    if abs(die_hi - die_lo) > 0.01:
        L.append("\tdie %.3g %.3g" % (die_lo, die_hi))
    else:
        L.append("\tdie %.3g" % die_hi)
    L.append("\tcount 1\t\t\t// QC passes a whole number; pcount = count*this")
    if any(b > 0.5 for b in box):
        # `spawnorg` TAKES TWO VALUES, NOT THREE (p_script.c:2113-2119):
        # horizontal spread then vertical, and a third argument is silently
        # ignored.  Writing the box as x y z therefore set the Y half-extent as
        # the HEIGHT and dropped the real height entirely.
        # Source's box is anisotropic in X and Y and FTE's cannot be, so the
        # horizontal figure is the AREA-PRESERVING mean sqrt(x*y): it keeps the
        # apparent density the author chose, where taking the max would rain
        # outside the volume and the min would leave gaps at its edges.
        horiz = (box[0] * box[1]) ** 0.5 if box[0] > 0 and box[1] > 0 else max(box[0], box[1])
        L.append("\tspawnmode %s" % ("ball" if ball else "box"))
        L.append("\tspawnorg %.6g %.6g" % (horiz, box[2]))
    else:
        L.append("\tspawnorg 0")
    # spawnvel is the same two-value shape, but ITS FRAME IS THE EMIT DIRECTION,
    # not the world: pointparticles builds axis[2] from normalize(dir) and the
    # "vertical" spread rides along it (p_script.c:4849-4857, :5336-5338).  So
    # the spread component along the mean velocity is the second number and the
    # two perpendicular components are the first.  For rain (spread on local Z,
    # falling along -Z) that is what the old code produced by accident; for the
    # snow (spread on local X, falling along -X) it is the difference between a
    # 128 u/s scatter in fall speed and a 128 u/s sideways jitter.  Only an
    # axis-aligned mean is handled; anything oblique keeps the old mapping and
    # says so.
    spawnvel = list(spread)
    bmag = (basevel[0] ** 2 + basevel[1] ** 2 + basevel[2] ** 2) ** 0.5
    if bmag > 1.0:
        n = [abs(v) / bmag for v in basevel]
        ax = max(range(3), key=lambda i: n[i])
        if n[ax] > 0.99:
            perp = [spread[i] for i in range(3) if i != ax]
            spawnvel = [perp[0], perp[1], spread[ax]]
        elif any(s > 0.5 for s in spread):
            unknown["(oblique Velocity Random spread; old horizontal/vertical mapping kept)"] += 1
    # A sphere's own radial speed wins the spawnvel slot, because with
    # `spawnmode ball` that slot IS the radial speed and a Velocity Random
    # spread would be describing something else in the same two numbers.
    if ball and radial > 0.01:
        L.append("\tspawnvel %.6g %.6g" % (radial, radial))
    elif any(v > 0.5 for v in spawnvel):
        svh = (spawnvel[0] * spawnvel[1]) ** 0.5 if spawnvel[0] > 0 and spawnvel[1] > 0 \
            else max(spawnvel[0], spawnvel[1])
        L.append("\tspawnvel %.6g %.6g" % (svh, spawnvel[2]))
    # No randomvel line.  v2 wrote one for random force and Velocity Noise; both
    # now go out through the index (jit and the local velocity) -- see above.
    L.append("\tveladd 1\t\t\t// |dir| IS the speed -- see the header")
    if abs(grav) > 0.01:
        L.append("\tgravity %.6g" % grav)
    if drag > 0.001:
        L.append("\tfriction %.3g" % drag)
    if kill:
        L.append("\tclipbounce -1\t\t// Source: kill particle on collision")
    L.append("}")

    # CHILDREN.  A DmeParticleSystemDefinition's 'children' are systems Source
    # starts at the same control points the moment the parent starts
    # (particles.h:1550-1554 forwards the orientation to every child, and the
    # emission is per-collection).  On boreas the visible end-zone effect IS the
    # children -- tendies_endparticle01 is six near-invisible sparks whose four
    # children are the 1600-unit glow and the 3000-unit laser -- and every alch
    # system carries its sprite-trail sibling as a child; tensor2's
    # water_splash01 carries water_splash02.  Ignoring them drew the parent and
    # dropped the effect.  They go out as extra index lines tagged with the
    # parent's name, and cl_emit.qc adds one emitter per tag at the entity.
    children = []
    for c in ops(d, e, "children"):
        ci = c.get("child", -1)
        if ci is not None and ci >= 0:
            children.append(d.elements[ci].name)
            if float(c.get("delay", 0) or 0) > 0:
                unknown["(child delay > 0; started immediately)"] += 1

    rt = dict(name=name, rate=rate, vel=basevel, wvel=worldvel, ofs=ofs,
              jit=jit, maxp=int(maxp), die=die_hi, maxdist=maxdist,
              nominal=nominal, children=children)
    return "\n".join(L), rt


# ------------------------------------------------------------------ driver
def bake(pcf_bytes, mapname, unknown):
    d = dmx.parse(pcf_bytes)
    if d.format != "pcf":
        raise dmx.DmxError("format is %r, not pcf" % d.format)
    root = d.root
    ids = root.get("particleSystemDefinitions") or []
    blocks, runtime, skipped = [], [], []
    for i in ids:
        e = d.elements[i]
        try:
            b, rt = translate(d, e, unknown, mapname)
        except Untranslated as ex:
            skipped.append((e.name, str(ex)))
            continue
        blocks.append(b)
        runtime.append(rt)
    return blocks, runtime, skipped


HEADER = """\
// %(map)s -- BAKED BY tools/pcf.py FROM THE MAP'S OWN %(src)s
//
// Do not hand-edit: re-run `python tools/pcf.py --map %(map)s` instead.
// %(n)d of %(total)d particle systems translated.
//
// EXEC'd, NOT AUTO-LOADED.  cl_emit.qc runs `exec particles/%(map)s.cfg` at map
// load, and every block is named `%(map)s_<system>` with an underscore rather
// than living in a `%(map)s.` namespace.  That is deliberate: a dotted name
// makes PScript_FindParticleType auto-load the config, and P_LoadParticleSet
// records the name at p_script.c:3709 BEFORE attempting FS_LoadFile at :3746
// and then refuses every retry at :3702-3707 -- so a single early miss is
// permanent for the session and completely silent, which is how
// particles/ftesurf.cfg drew nothing at all from build 49 until 2026-09-08.
// A missing file is now a visible exec error instead.
//
// Never set r_particledesc -- it is CVAR_SEMICHEAT and writing it while
// connected kills every effect without reloading.
//
// `veladd 1` everywhere: the vector cl_emit.qc passes as `dir` is the velocity
// in units/sec.  The spawn BOX is baked here as `spawnorg`; the RATE and the
// base velocity are in data/mapparticles.txt because they are QC's to pass.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", help="map name; reads the .pcf out of its BSP pakfile")
    ap.add_argument("--pcf", help="a .pcf file directly")
    ap.add_argument("--mapsdir", default=r"C:\Program Files (x86)\Steam\steamapps"
                                        r"\common\Momentum Mod Playtest\momentum\maps")
    ap.add_argument("--gamedir", default=r"C:\FTESurf\ftesurf")
    ap.add_argument("--strict", action="store_true",
                    help="fail if any operator is not understood")
    ap.add_argument("--dry", action="store_true", help="print, do not write")
    a = ap.parse_args()

    unknown = collections.Counter()

    if a.pcf:
        data = open(a.pcf, "rb").read()
        mapname = a.map or os.path.splitext(os.path.basename(a.pcf))[0]
        srcname = os.path.basename(a.pcf)
    elif a.map:
        bsp = os.path.join(a.mapsdir, a.map + ".bsp")
        if not os.path.exists(bsp):
            sys.exit("no such map: %s" % bsp)
        names, z = pcfs_in_map(bsp)
        if not names:
            sys.exit("%s ships no .pcf -- nothing to bake" % a.map)
        if len(names) > 1:
            print("note: %d pcfs, using %s" % (len(names), names[0]))
        data = z.read(names[0])
        mapname = a.map
        srcname = os.path.basename(names[0])
    else:
        sys.exit("need --map or --pcf")

    try:
        blocks, runtime, skipped = bake(data, mapname, unknown)
    except dmx.DmxError as ex:
        sys.exit("REFUSED: %s" % ex)

    total = len(blocks) + len(skipped)
    body = HEADER % dict(map=mapname, src=srcname,
                         n=len(blocks), total=total) + "\n" + "\n\n".join(blocks) + "\n"

    # psys <map> <name> <rate> <lx> <ly> <lz> <maxp> <die> <maxdist>
    #      <ox> <oy> <oz> <wx> <wy> <wz> <jit> <parent|->
    # Eighteen columns.  The first ten are what build 52 read; the local
    # velocity is rotated by the entity's angles in QC, the centre offset is
    # added to the origin, the world velocity is added unrotated, jit is the
    # isotropic random_speed plus the random-force walk handed to em_jit, and a
    # line whose last column
    # names a parent is an extra emitter started with that parent.
    # Stand-alone lines first, so Emit_PsysFind (first match by name) lands on
    # one with no parent tag.
    def psline(rt, parent):
        return "psys %s %s %.4g %.6g %.6g %.6g %d %.4g %.6g %.6g %.6g %.6g %.6g %.6g %.6g %.6g %s" % (
            mapname, rt["name"], rt["rate"],
            rt["vel"][0], rt["vel"][1], rt["vel"][2],
            rt["maxp"], rt["die"], rt["maxdist"],
            rt["ofs"][0], rt["ofs"][1], rt["ofs"][2],
            rt["wvel"][0], rt["wvel"][1], rt["wvel"][2], rt["jit"], parent)

    byname = dict((rt["name"], rt) for rt in runtime)
    edges = []
    for rt in runtime:
        for c in rt["children"]:
            if c in byname:
                edges.append((rt["name"], byname[c]))
            else:
                skipped.append((c, "child of %s was not translated; dropped" % rt["name"]))
    idx = ["particles %s %d" % (mapname, len(runtime) + len(edges))]
    for rt in runtime:
        idx.append(psline(rt, "-"))
    for parent, rt in edges:
        idx.append(psline(rt, parent))

    print("%s: %d systems translated, %d skipped, %d child links" % (
        mapname, len(blocks), len(skipped), len(edges)))
    for n, why in skipped:
        print("   skipped %-24s %s" % (n, why))
    for parent, rt in edges:
        print("   child   %-24s of %s" % (rt["name"], parent))
    if unknown:
        print("   operators NOT understood (effects will differ):")
        for k, v in unknown.most_common():
            print("      %3d  %s" % (v, k))
        if a.strict:
            sys.exit("--strict: refusing to write a partial translation")
    else:
        print("   every operator understood")

    if a.dry:
        print("\n" + body)
        print("\n".join(idx))
        return

    cfg = os.path.join(a.gamedir, "particles", mapname + ".cfg")
    os.makedirs(os.path.dirname(cfg), exist_ok=True)
    with open(cfg, "w", newline="\n") as f:
        f.write(body)
    print("   wrote %s" % cfg)

    mp = os.path.join(a.gamedir, "data", "mapparticles.txt")
    keep = []
    if os.path.exists(mp):
        for line in open(mp, encoding="latin-1"):
            t = line.split()
            if len(t) >= 2 and t[1] == mapname:
                continue
            if line.strip():
                keep.append(line.rstrip("\n"))
    with open(mp, "w", newline="\n") as f:
        if keep:
            f.write("\n".join(keep) + "\n")
        f.write("\n".join(idx) + "\n")
    print("   updated %s" % mp)


if __name__ == "__main__":
    main()
