"""Of the trigger_push volumes that OVERLAP a start zone, which ones push UPWARD?

Only an upward net push takes FL_ONGROUND (sv_entities.qc:5657-5663:
`if (push_z > 0 && (other.flags & FL_ONGROUND))`), and only that clear can
poison the next command's run_wasground stamp (sv_player.qc:420) and so switch
Patch 409's gate off.  QC derives the direction as makevectors(self.pushdir)
-> v_forward, so v_forward_z = -sin(pitch): pitch < 0 pushes up.
"""
import json, math, os, sys
import bsplib
import pushcensus as pc

MAPS = pc.MAPS
ZON = pc.ZON


def fwd_z(pushdir):
    try:
        p = [float(t) for t in str(pushdir).split()[:3]]
    except ValueError:
        return 0.0
    if len(p) < 1:
        return 0.0
    return -math.sin(math.radians(p[0]))


def starts_for(name, ents, models):
    jp = os.path.join(ZON, name + ".json")
    if os.path.exists(jp):
        try:
            b = pc.json_starts(jp)
            if b:
                return b
        except Exception:
            pass
    out = []
    for e in ents:
        if e.get('classname') == 'trigger_momentum_timer_start':
            bx = pc.ent_box(e, models)
            if bx:
                out.append(bx)
    return out


def main(names):
    rows = []
    for name in names:
        bsp = os.path.join(MAPS, name + ".bsp")
        if not os.path.exists(bsp):
            print("MISSING %s" % name)
            continue
        ents, models = bsplib.read(bsp)
        starts = starts_for(name, ents, models)
        if not starts:
            print("NOSTART %s" % name)
            continue
        for e in ents:
            if e.get('classname') != 'trigger_push':
                continue
            bx = pc.ent_box(e, models)
            if not bx:
                continue
            if not any(pc.gap(bx, s) == 0.0 for s in starts):
                continue
            pd = e.get('pushdir', '0 0 0')
            spd = e.get('speed') or e.get('Speed') or '100'
            try:
                spd = float(spd)
            except ValueError:
                spd = 100.0
            try:
                sf = int(float(e.get('spawnflags', '0')))
            except ValueError:
                sf = 0
            fz = fwd_z(pd)
            rows.append(dict(map=name, pushdir=pd, speed=spd, spawnflags=sf,
                             fwd_z=round(fz, 4), push_z=round(spd * fz, 1),
                             once=bool(sf & 128), up=(spd * fz) > 0.0))
    up = [r for r in rows if r['up'] and not r['once']]
    print(json.dumps(dict(
        overlapping_pushes=len(rows),
        upward_continuous=len(up),
        upward_maps=sorted({r['map'] for r in up}),
    ), indent=1))
    print("\n-- every overlapping trigger_push --")
    for r in sorted(rows, key=lambda r: (-r['push_z'], r['map'])):
        print("  %-28s pushdir %-14s speed %8.1f  push_z %+9.1f %s%s" % (
            r['map'], r['pushdir'], r['speed'], r['push_z'],
            "UP" if r['up'] else "  ", "  (ONCE)" if r['once'] else ""))


if __name__ == '__main__':
    main([l.strip() for l in open(sys.argv[1], encoding='utf-8') if l.strip()])
