#!/usr/bin/env python
"""
mkavatarfx.py -- generate ftesurf/particles/ftesurf_avatar.cfg.

Patch 278.  Two engine-driven particle effects per palette colour, for the
lobby avatars:

    ftesurf_avtrail_<n>   .traileffectnum -- a ribbon behind a moving player
    ftesurf_avmote_<n>    .emiteffectnum  -- slow motes rising around them

WHY THIS IS GENERATED AND NOT HAND-WRITTEN
------------------------------------------
Particles cannot be tinted per entity.  .colormod recolours a MODEL; there is
no equivalent for a particle effect, because an effect is a shared template and
the colour lives in the template.  So "the trail matches your colour" means one
effect per colour, and twelve colours means twenty-four near-identical blocks.

Hand-maintaining twenty-four copies of two blocks, whose colours must agree with
a table in a completely different language in a completely different file, is
exactly the drift that mkplayermodel.py's heights were.  So THE PALETTE IS NOT
DEFINED HERE.  It is read out of Lobby_PaletteRGB in src/server/sv_lobby.qc,
which is the only place it exists.  Edit the QC, re-run this, and the two cannot
disagree.  `--check` proves they do not, without writing anything.

WHERE THE FILE IS LOADED
------------------------
A NEW file rather than an append to particles/ftesurf.cfg, and the exec is its
own line in CSQC_WorldLoaded beside Emit_LoadFromWorld's.  Patch 272's rules
still apply and are the reason for all three of these:

  * loaded by a CSQC localcmd at map load, NOT exec'd from cfg/default.cfg --
    an r_part block parsed before Renderer_Start is discarded in silence
    (p_script.c:1155-1159), which cost three shipped builds;
  * named ftesurf_avtrail_N with UNDERSCORES and never a dot -- a dotted name
    reaches the auto-load arm in PScript_FindParticleType, and P_LoadParticleSet
    records the config name in loadedconfigs BEFORE it tries to open the file,
    so one early miss is permanent for the session;
  * re-exec'd on every map load rather than latched, because the engine forces
    the r_particledesc callback on every map load (through the cvar's ALIAS
    r_particlesdesc, which is why no grep found it) and vid_restart frees the
    whole table.  r_part_keepuser 1 is what makes our blocks survive that.

Usage:
    python mkavatarfx.py            # dry run: parse, report, write nothing
    python mkavatarfx.py --check    # is the cfg on disk still in step with the QC?
    python mkavatarfx.py --apply    # write it
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
QC   = os.path.join(HERE, os.pardir, "src", "server", "sv_lobby.qc")
CFG  = os.path.join(HERE, os.pardir, "ftesurf", "particles", "ftesurf_avatar.cfg")

# One particle per this many units of travel.
#
# `step` is the trail control and it is NOT a rate: p_script.c:1418-1425 sets
# countspacing = n and count = 1/n, so this is one particle every n units of
# DISTANCE.  That is the entire reason a trail on 32 players is affordable -- a
# standing player emits nothing at all, and the cost scales with speed rather
# than with the clock.
#
# At 16 and a 0.45 s life: a player at 2000 ups makes 125/sec and holds about 56
# alive.  Twelve moving players is ~675, thirty-two is ~1800, against
# r_part_maxparticles 65536 shared with vbsp_emit_budget's 2000.  Comfortable.
TRAIL_STEP = 16

# Motes are the opposite: a flat rate per second, alive or not moving.
# 6/sec at a ~2.1 s mean life is about 13 alive per player, 420 at 32 players.
MOTE_RATE  = 6

# `die` IS A MIN AND A MAX, not a base and a spread.  The house blocks say so
# (ftesurf_fire is `die 0.7 1.1`) and the engine's own export confirms it: a
# first draft wrote `die 1.8 0.8` meaning "1.8 plus up to 0.8", and
# r_exportalleffects read it back as `die 1.8 2.8` -- the engine had taken the
# absolute difference and produced a lifetime range nobody intended.  Writing
# the pair as an explicit min and max makes the file and the engine agree.


def palette_from_qc(path=QC):
    """Pull Lobby_PaletteRGB's table out of the QC.  Returns [(i,(r,g,b)),...]
    with r/g/b in 0..1, or None if it could not be found."""
    try:
        with open(path, "r") as f:
            text = f.read()
    except IOError:
        return None

    m = re.search(r"vector\s*\(\s*float\s+i\s*\)\s*Lobby_PaletteRGB\s*=\s*\{(.*?)\n\};",
                  text, re.S)
    if not m:
        return None

    out = []
    for line in m.group(1).splitlines():
        e = re.search(r"if\s*\(\s*i\s*==\s*(\d+)\s*\)\s*return\s*'\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*'",
                      line)
        if e:
            out.append((int(e.group(1)),
                        tuple(float(e.group(k)) for k in (2, 3, 4))))
    if not out:
        return None

    out.sort()
    if [i for i, _ in out] != list(range(1, len(out) + 1)):
        return None            # gap or duplicate: refuse rather than guess
    return out


# scalefactor 1 ON BOTH, AND IT IS NOT A GROWTH FACTOR.
#
# It selects how a particle's drawn size relates to DISTANCE, not to time:
# p_script.c:6325-6336 takes the `type->scalefactor == 1` branch as a plain
# `scale = p->scale*0.25` -- constant WORLD size -- and otherwise blends in a
# term proportional to the distance from the eye, weighted by
# invscalefactor = 1 - scalefactor.  A value ABOVE 1 does not survive the parser
# at all: FinishParticleType (:2855-2862) folds it into `scale` and resets the
# factor to 1, so `scalefactor 2` has always meant "twice as big" and never
# "grows to twice the size".
#
# The default when the key is ABSENT is 0, i.e. constant SCREEN size -- so an
# r_part block that says nothing draws particles whose world size grows with
# distance.  Growth over LIFE is `scaledelta` (:7619), which is a different key
# and is what the trail's -7 is doing.
#
# These were 0.8 and 0.9, written as if the number were a growth rate.  Both are
# now 1: a trail on somebody else's body is a distance cue, and a mark that
# shrinks as it recedes is the cue.  Found by ftesurf-4b, in the baker for the
# map emitters; the same mistake is in most of the hand-written blocks in
# particles/ftesurf.cfg, which is a separate judgement and not this file's.
def block_trail(i, rgb):
    r, g, b = (int(round(c * 255)) for c in rgb)
    return """r_part ftesurf_avtrail_%d
{
\ttexture "ftesurf_dot"
\tblend adda
\tstep %d
\tscale 5 3
\tscalefactor 1
\tscaledelta -7
\trgb %d %d %d
\talpha 0.5
\talphadelta -1.1
\tdie 0.45 0.70
\tspawnmode box
\tspawnorg 2
\tspawnvel 5 4
\tfriction 1.4
\tgravity 0
}
""" % (i, TRAIL_STEP, r, g, b)


def block_mote(i, rgb):
    r, g, b = (int(round(c * 255)) for c in rgb)
    return """r_part ftesurf_avmote_%d
{
\ttexture "ftesurf_dot"
\tblend adda
\tcount %d
\tscale 3 2
\tscalefactor 1
\trgb %d %d %d
\talpha 0.45
\talphadelta -0.25
\tdie 1.6 2.6
\tspawnmode box
\tspawnorg 18 22
\tspawnvel 3 2
\tfriction 0.5
\tgravity -14
}
""" % (i, MOTE_RATE, r, g, b)


HEADER = """// ftesurf/particles/ftesurf_avatar.cfg
//
// GENERATED BY tools/mkavatarfx.py -- DO NOT EDIT BY HAND.
// The colours come from Lobby_PaletteRGB in src/server/sv_lobby.qc, which is
// the only place the palette is defined.  Change it there and re-run:
//     python tools/mkavatarfx.py --apply
// `--check` fails if this file and the QC have drifted apart.
//
// Per-player effects for the lobby avatars (Patch 278).  Two per palette
// colour, because a particle effect carries its colour in the template and
// there is no per-entity tint for particles the way .colormod is for models.
//
// These are ENGINE-DRIVEN, which makes their contract different from every
// other block in particles/ftesurf.cfg:
//
//   ftesurf_avtrail_N  goes in .traileffectnum.  The engine runs it between the
//                      entity's last and current origin once per RENDERED frame
//                      (cl_ents.c:5929-5944).  `step` is units of distance per
//                      particle, so a stationary player costs nothing.  Note
//                      the engine's own 128-unit-per-frame guard: a segment
//                      longer than that is dropped, so at extreme speed and low
//                      framerate the trail goes sparse rather than wrong.
//
//   ftesurf_avmote_N   goes in .emiteffectnum.  P_EmitEffect passes frametime
//                      as the count (r_part.c:1036-1055), so `count` here is a
//                      RATE PER SECOND.  It emits from the entity ORIGIN, which
//                      on this model is the FEET -- spawnorg's vertical spread
//                      is what lifts them onto the body, and some will start
//                      below the floor and rise through it.  That is expected;
//                      they are not clipped and they die in under two seconds.
//
// NO `veladd 1` ON EITHER, unlike every QC-driven block in ftesurf.cfg.  That
// line is there because pointparticles is handed a velocity vector and veladd
// scales by its length; here the engine supplies a direction of its own (the
// trail segment, or the entity's forward axis) and there is no speed to
// recover.  Setting it would make the particles chase the player.

"""


def generate(pal):
    parts = [HEADER]
    for i, rgb in pal:
        parts.append(block_trail(i, rgb))
        parts.append("\n")
    for i, rgb in pal:
        parts.append(block_mote(i, rgb))
        parts.append("\n")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the cfg")
    ap.add_argument("--check", action="store_true",
                    help="verify the cfg on disk matches the QC palette; write nothing")
    args = ap.parse_args()

    pal = palette_from_qc()
    if pal is None:
        print("could not read Lobby_PaletteRGB from %s" % os.path.abspath(QC))
        print("that function is the only definition of the palette -- if it has")
        print("moved or changed shape, fix this parser rather than duplicating it.")
        return 1

    print("palette: %d colours from %s" % (len(pal), os.path.relpath(QC, HERE)))
    for i, (r, g, b) in pal:
        print("    %2d  rgb %3d %3d %3d" % (i, round(r * 255), round(g * 255), round(b * 255)))

    want = generate(pal)
    print()
    print("%d effects (%d trail + %d mote), %d bytes"
          % (2 * len(pal), len(pal), len(pal), len(want)))

    if args.check:
        try:
            with open(CFG, "r") as f:
                have = f.read()
        except IOError:
            print("CHECK FAILED: %s does not exist" % os.path.abspath(CFG))
            return 1
        if have != want:
            print("CHECK FAILED: %s is out of step with the QC palette."
                  % os.path.relpath(CFG, HERE))
            print("run:  python tools/mkavatarfx.py --apply")
            return 1
        print("CHECK PASSED: the cfg on disk matches the QC palette exactly.")
        return 0

    if not args.apply:
        print()
        print("would write (use --apply):")
        print("    %s" % os.path.abspath(CFG))
        return 0

    d = os.path.dirname(os.path.abspath(CFG))
    if not os.path.isdir(d):
        print("no such directory: %s" % d)
        return 1
    with open(CFG, "w") as f:
        f.write(want)
    print()
    print("wrote %s" % os.path.abspath(CFG))
    return 0


if __name__ == "__main__":
    sys.exit(main())
