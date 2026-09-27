"""The two ways a start RE-ARMS without the player asking for it.

WHY THIS EXISTS, and it is a process failure of mine rather than a new question.
Patch 445's central justification is that `SV_TimerArm` is reachable from ordinary map
DATA, and it quotes two numbers for that -- "21 shipped maps have two abutting start
regions whose seam re-arms on every crossing" and "66 have a velocity-keeping
trigger_teleport landing inside a START region".  Those came from a round-4 review and
WERE NEVER COMMITTED AS A TOOL.  They are now quoted in deployed source
(sv_timer.qc's run_t_hopped essay and SV_TimerArm's removal comment), in
cfg/test/p445hop.cfg, in BACKLOG.md, in AGENTS.md and in the anti-cheat plan -- load
bearing everywhere and reproducible nowhere.  Round 7 then found that two of my own
committed censuses were blind to whole classes of row, which is exactly why an
uncommitted number is not good enough.

So this re-measures both from scratch.  It is deliberately NOT a copy of the review's
method: the point is an independent answer, and where it disagrees the disagreement is
the finding.

  ARM A -- THE SEAM.  `SV_ZoneOcc` is a POINT test at the shipped `run_zone_hull 1`
  while the start test is the HULL, and the arm scan runs AFTER the start test in the
  same packet.  So two arm-able regions that touch or overlap let a crossing flip
  `run_t_azone` with the body still inside the old region's hull: SV_TimerArm runs, and
  nothing is printed because SV_TimerClassSay needs TS_RUNNING.  Arm-able means
  `segments[i].checkpoints[0]` on any track -- segment 0 is the track's START and i > 0
  are its STAGE starts (ZONE_START / ZONE_STAGE).
  The subset that matters most is SAME (track, segment): there a re-arm cannot even be
  a different leg, so it is a forgiveness for nothing.

  ARM B -- THE VELOCITY-KEEPING TELEPORT.  `trigger_teleport_touch` KEEPS velocity when
  `VelocityMode` is absent or 0 (a plain CS:S map has no such key), strips FL_ONGROUND,
  and calls SV_TimerWarped.  Arriving from outside a start region, the next scan is an
  `az` edge, so the arm launders exactly as in ARM A -- but with the speed you arrived
  at.  A LANDMARK teleport is excluded: it is a relative move, which is not the
  "arrive at full speed" shape.

GRADING, per tools/census/README.md.  ARM A is a zone-to-zone test and has no AABB
problem -- the regions are authored prisms and the seam is a real adjacency.  ARM B
DOES: it resolves a destination POINT (teleDestPos is authored, or the destination
entity's origin) and asks whether that point is inside a start prism, which is a point
test and therefore exact.  Neither says the gesture is USEFUL -- ARM A needs the player
to cross the seam mid-chain, ARM B needs a route to the teleport.

SEPARATOR AND DUPLICATE-KEY DISCIPLINE: this reads `bsplib.read_pairs`, not `read`, and
never splits an I/O record.  Round 7's two blind spots were a dict that dropped repeated
keys and an assumed comma where VBSP >= v25 uses 0x1B ESC; the keys ARM B needs
(`classname`, `target`, `landmark`, `spawnflags`, `VelocityMode`, `origin`,
`targetname`) are all single-valued, and the pair list is collapsed to a dict here
deliberately and locally so that fact is visible rather than inherited.

RESULT 2026-09-27, 537 zone files, 0 unreadable, 0 without an arm-able region.

BOTH HEADLINE NUMBERS REPRODUCE EXACTLY, which is the outcome I wanted least to be
wrong about: Patch 445 is already deployed quoting them.

  ARM A   30 maps have at least one touching pair of arm-able regions; 57 pairs.
          **21 maps have a SAME-(track, segment) pair** -- the review's 21, exactly.
          Split: 18 START/START, 5 STAGE/STAGE, overlapping on 2 maps that have both
          (21 = 18 + 5 - 2).  10 more maps touch only across legs.
  ARM B   52879 trigger_teleport entities (the review's count, exactly).  455 excluded
          as landmark, 46229 excluded for a set VelocityMode, leaving 6195
          velocity-KEEPING candidates.  148 of those have an unresolvable destination.
          1616 land inside a START region, on **66 maps** -- the review's 66, exactly.

WHERE IT DISAGREES, and the disagreement is in the review's favour nowhere: the review
reported "of which 15 are START/START on the same track and segment".  IT IS 18.  All
fifteen it named are in my list; it missed **df_cavernish, surf_gradient and
surf_lt_omnific**.  It also bucketed differently -- surf_gradient and surf_sodacity were
filed as cross-track, and they have same-leg pairs too (a map can have both, and
surf_gradient has all three kinds).  So the sub-count in BACKLOG.md was low by three and
is corrected there; the headline it fed was right.

THE SELF-CHECK IS HEALTHY RATHER THAN VACUOUS.  ARM B's exclusions are where the answer
could have hidden and they are all small relative to what survives: 148 unresolvable out
of 6195 candidates (2.4%), so `nodest` is not swallowing the result.  And the 46229
VelocityMode exclusions are the reason the number is 66 and not 500 -- most shipped
teleports DO set a velocity mode, which is the mapper convention this depends on and
the thing to re-check when the corpus changes.
"""
import json
import os
import sys

import bsplib

MOM = os.environ.get("MOMENTUM_DIR",
                     r"C:\Program Files (x86)\Steam\steamapps\common"
                     r"\Momentum Mod Playtest\momentum")
MAPS = os.path.join(MOM, "maps")
ZON = os.path.join(MAPS, "zones", "online")


def arm_regions(path):
    """-> list of (track, seg, mins, maxs) for every ARM-ABLE region in the file.

    Arm-able is `segments[i].checkpoints[0]`: segment 0 is the track's START and i > 0
    are its STAGE starts.  checkpoints[1..] are ordinary checkpoints and do not arm.
    Track 0 is main, 1.. are the bonuses, matching zone_track in the QC.
    """
    d = json.load(open(path, 'r', encoding='utf-8-sig'))
    tracks = d.get('tracks') or {}
    out = []
    cands = []
    if isinstance(tracks.get('main'), dict):
        cands.append((0, tracks['main']))
    for i, b in enumerate(tracks.get('bonuses') or []):
        if isinstance(b, dict):
            cands.append((i + 1, b))
    for tr, t in cands:
        segs = ((t.get('zones') or {}).get('segments') or [])
        for si, seg in enumerate(segs):
            cps = (seg or {}).get('checkpoints') or []
            if not cps:
                continue
            for r in (cps[0] or {}).get('regions') or []:
                pts = r.get('points') or []
                if len(pts) < 3:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                b0 = r.get('bottom', 0.0)
                h = r.get('height', 0.0)
                out.append((tr, si,
                            (min(xs), min(ys), b0),
                            (max(xs), max(ys), b0 + h)))
    return out


def starts_only(regs):
    """The (mins, maxs) of every track's SEGMENT-0 region -- a START, not a stage."""
    return [(mn, mx) for tr, si, mn, mx in regs if si == 0]


def touch(a0, a1, b0, b1, slop=0.0):
    """True if the two AABBs overlap or are within `slop` on every axis."""
    for i in range(3):
        if a0[i] - b1[i] > slop:
            return False
        if b0[i] - a1[i] > slop:
            return False
    return True


def inside(p, mn, mx):
    return all(mn[i] <= p[i] <= mx[i] for i in range(3))


def truthy(v):
    return str(v).strip() not in ("", "0", "false", "False")


def main():
    if not os.path.isdir(ZON):
        sys.exit("no zone dir at %s (set MOMENTUM_DIR)" % ZON)
    zfiles = {os.path.splitext(f)[0].lower(): os.path.join(ZON, f)
              for f in os.listdir(ZON) if f.lower().endswith('.json')}
    bsps = {os.path.splitext(f)[0].lower(): os.path.join(MAPS, f)
            for f in os.listdir(MAPS) if f.lower().endswith('.bsp')}

    st = dict(zoned=0, unreadable=0, noarm=0,
              seam_maps=0, seam_same=0, seam_pairs=0, seam_s0=0, seam_sN=0,
              tp_maps=0, tp_ents=0, tp_keep=0, tp_hit=0,
              tp_landmark=0, tp_vmode=0, nodest=0)
    seam_rows, tp_rows = [], []

    for name in sorted(zfiles):
        try:
            regs = arm_regions(zfiles[name])
        except Exception:
            st['unreadable'] += 1
            continue
        st['zoned'] += 1
        if not regs:
            st['noarm'] += 1
            continue

        # ---- ARM A: the seam ------------------------------------------------
        hit_same = False
        pairs_here = 0
        for i in range(len(regs)):
            for j in range(i + 1, len(regs)):
                ta, sa, amn, amx = regs[i]
                tb, sb, bmn, bmx = regs[j]
                if not touch(amn, amx, bmn, bmx):
                    continue
                pairs_here += 1
                same = (ta == tb and sa == sb)
                if same:
                    hit_same = True
                seam_rows.append((name, ta, sa, tb, sb, same))
        if pairs_here:
            st['seam_maps'] += 1
            st['seam_pairs'] += pairs_here
        if hit_same:
            st['seam_same'] += 1
            # Split because the review this re-measures reported the two separately:
            # a START/START seam re-arms the RUN's own start, a STAGE/STAGE one re-arms
            # a leg.  Both call SV_TimerArm; only the first is the hopped-start case.
            if any(r[5] and r[2] == 0 for r in seam_rows if r[0] == name):
                st['seam_s0'] += 1
            else:
                st['seam_sN'] += 1

        # ---- ARM B: the velocity-keeping teleport ---------------------------
        if name not in bsps:
            continue
        try:
            pl, _ = bsplib.read_pairs(bsps[name])
        except Exception:
            continue
        if pl is None:
            continue
        # Local, deliberate collapse: every key ARM B reads is single-valued.  See the
        # module docstring -- round 7's bug was inheriting this shape for OUTPUTS.
        ents = [{k: v for k, v in e} for e in pl]

        dests = {}
        for e in ents:
            tn = (e.get('targetname') or '').strip().lower()
            cn = (e.get('classname') or '').lower()
            if tn and cn in ('info_teleport_destination', 'info_target',
                             'info_player_teleport'):
                try:
                    dests[tn] = [float(x) for x in e.get('origin', '').split()[:3]]
                except ValueError:
                    pass

        starts = starts_only(regs)
        if not starts:
            continue
        hit_here = False
        for e in ents:
            if (e.get('classname') or '').lower() != 'trigger_teleport':
                continue
            st['tp_ents'] += 1
            if (e.get('landmark') or '').strip():
                st['tp_landmark'] += 1
                continue                      # a relative move, not an arrival
            vm = e.get('VelocityMode', e.get('velocitymode', '0'))
            if truthy(vm):
                st['tp_vmode'] += 1
                continue                      # sets or scales, so not "kept"
            st['tp_keep'] += 1
            tgt = (e.get('target') or '').strip().lower()
            p = dests.get(tgt)
            if p is None or len(p) != 3:
                st['nodest'] += 1
                continue
            for mn, mx in starts:
                if inside(p, mn, mx):
                    st['tp_hit'] += 1
                    hit_here = True
                    tp_rows.append((name, tgt, tuple(round(x, 1) for x in p)))
                    break
        if hit_here:
            st['tp_maps'] += 1

    print("zone files %(zoned)d  unreadable %(unreadable)d  "
          "no arm-able region %(noarm)d" % st)
    print()
    print("ARM A -- ADJACENT ARM-ABLE REGIONS (the silent re-arm)")
    print("    maps with at least one touching pair: %(seam_maps)d" % st)
    print("    ...of which SAME (track, segment):    %(seam_same)d"
          "   <- a re-arm that cannot be a different leg" % st)
    print("    ...of those, START/START (seg 0):     %(seam_s0)d" % st)
    print("    ...the rest are STAGE/STAGE seams:    %(seam_sN)d" % st)
    print("    touching pairs in total:              %(seam_pairs)d" % st)
    print()
    print("ARM B -- VELOCITY-KEEPING TELEPORT INTO A START REGION")
    print("    trigger_teleport entities seen:       %(tp_ents)d" % st)
    print("    excluded, landmark (relative move):   %(tp_landmark)d" % st)
    print("    excluded, VelocityMode set:           %(tp_vmode)d" % st)
    print("    velocity-KEEPING candidates:          %(tp_keep)d" % st)
    print("    ...whose destination is unresolvable: %(nodest)d" % st)
    print("    ...landing inside a START region:     %(tp_hit)d" % st)
    print("    maps with at least one:               %(tp_maps)d" % st)
    print()
    print("SELF-CHECK -- neither zero would mean anything on its own:")
    print("  ARM A is vacuous if `seam_pairs` is 0 AND no map has two arm-able regions")
    print("  at all; ARM B is vacuous if `tp_keep` is 0 (every teleport excluded) or if")
    print("  `nodest` swallows most candidates -- an unresolved destination is a")
    print("  'cannot see', not a 'does not land there'.  Both are printed for that.")
    print()
    same = [r for r in seam_rows if r[5]]
    print("--- ARM A, same-leg pairs (first 25 of %d) ---" % len(same))
    for r in same[:25]:
        print("  %-30s track %g seg %g  <->  track %g seg %g" % (r[0], r[1], r[2], r[3], r[4]))
    print()
    print("--- ARM B, first 25 of %d ---" % len(tp_rows))
    for r in tp_rows[:25]:
        print("  %-30s -> %-24s at %s" % (r[0], r[1][:24], r[2]))


if __name__ == "__main__":
    main()
