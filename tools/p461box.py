"""Grade cfg/test/p461box.cfg -- a `solid 2` prop's collision must survive the wire.

A SOLID_BBOX entity's bounds reach the client through COM_EncodeSize /
COM_DecodeSize (common/common.c:1340-1385), which truncates every extent to a whole
unit AND forces the box symmetric in x/y (it takes -mins[0] for both half-widths),
while the server's own pmove uses the raw mins/maxs.  So the two sides collided
against different shapes.

SV_SpawnProp promotes such a prop to SOLID_PHYSICS_TRIMESH when its model ships a
.phy: that crosses as ES_SOLID_BSP with no bounds at all, so both sides run the same
narrowphase on the same model and nothing is quantised.

THREE GRADES, and the third is a NOT-DEMONSTRATED by construction:

  B1  the promotion count per map, against this script's own count of solid-2 props
      read out of the BSP entity lump -- and NO `box re-cut` clause, because every
      promoted prop must leave the box path unused.
  B2  the re-cut branch.  146 solid-2 props exist in the library, all 146 promote,
      so this branch has never run on a shipped map.  Reported as NOT DEMONSTRATED,
      never as PASS: an arm whose condition never occurred proves nothing.  If a
      `propbox` line ever does appear, it is graded -- integer extents, symmetric in
      x/y, and containing the old box.
  B3  CONTROL: a map with props and no solid-2 among them must print neither clause.

Usage: python tools/p461box.py [ftesurf/logs/p461box.log]
"""
import contextlib, io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'census'))
_argv = sys.argv
sys.argv = ['pushcensus']
with contextlib.redirect_stdout(io.StringIO()):
    import pushcensus as pc
import bsplib
sys.argv = _argv

DEFNONE = {'prop_dynamic', 'prop_dynamic_override', 'prop_dynamic_glow',
           'prop_dynamic_ornament', 'prop_ragdoll', 'prop_hallucination'}
DEFMESH = {'prop_physics', 'prop_physics_multiplayer', 'prop_physics_override',
           'prop_door_rotating', 'prop_physics_ragdoll',
           'prop_physics_respawnable', 'simple_physics_prop', 'prop_sphere'}
PROPS = DEFNONE | DEFMESH

TS = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ')
SECTION = re.compile(r'^={4} (B\w+) (\S+) ')
PROPSLINE = re.compile(r'^props: (\d+) spawned \(')
PROMOTED = re.compile(r'(\d+) bbox->phy')
RECUT = re.compile(r'(\d+) box re-cut')
PROPBOX = re.compile(r"^propbox '([^']*)' -> '([^']*)' (.*)$")

rc = 0


def verdict(name, state, detail):
    global rc
    print("%s  %-28s %s" % ({'PASS': '  PASS', 'FAIL': '  FAIL', 'ND': '  ----'}[state],
                            name, detail))
    if state == 'FAIL':
        rc = 1


def solid2(mapname):
    """Solid-2 props the spawn will make, from whichever BSP the server loaded."""
    for d, tag in ((os.path.join(ROOT, 'ftesurf', 'maps'), 'gamedir'), (pc.MAPS, 'momentum')):
        p = os.path.join(d, mapname + '.bsp')
        if os.path.exists(p):
            break
    else:
        return None, None
    ents, _ = bsplib.read(p)
    n = 0
    for e in ents:
        if (e.get('classname') or '').lower() not in PROPS:
            continue
        mdl = e.get('model') or ''
        if mdl == '' or mdl.startswith('*'):
            continue
        raw = e.get('solid', e.get('Solid'))
        try:
            s = int(float(raw)) if raw is not None else -1
        except ValueError:
            s = -1
        if s == 2:
            n += 1
    return n, tag


def vec(s):
    return [float(x) for x in s.split()]


def main():
    path = _argv[1] if len(_argv) > 1 else os.path.join(ROOT, 'ftesurf', 'logs', 'p461box.log')
    if not os.path.exists(path):
        print("no log at %s" % path)
        return 2

    sect, order, cur = {}, [], None
    for ln in open(path, encoding='utf-8', errors='replace'):
        ln = TS.sub('', ln.strip())
        m = SECTION.match(ln)
        if m:
            cur = (m.group(1), m.group(2))
            sect[cur] = {'props': None, 'promoted': 0, 'recut': 0, 'boxes': []}
            order.append(cur)
            continue
        if cur is None:
            continue
        d = sect[cur]
        if PROPSLINE.match(ln) and d['props'] is None:
            d['props'] = int(PROPSLINE.match(ln).group(1))
            mp = PROMOTED.search(ln)
            mr = RECUT.search(ln)
            d['promoted'] = int(mp.group(1)) if mp else 0
            d['recut'] = int(mr.group(1)) if mr else 0
            continue
        m = PROPBOX.match(ln)
        if m:
            d['boxes'].append((vec(m.group(1)), vec(m.group(2)), m.group(3)))

    if not order:
        print("no `==== B<n> <map>` markers -- did the cfg run?")
        return 2

    print("p461box -- solid-2 prop collision crosses the wire exactly")
    print("           (%s)" % path)
    print()

    totpromoted = totrecut = 0
    for key in order:
        tag, mapname = key
        d = sect[key]
        want, src = solid2(mapname)
        if d['props'] is None:
            verdict("%s %s" % (tag, mapname), 'ND', "no props: line -- map did not load")
            continue
        if want is None:
            verdict("%s %s" % (tag, mapname), 'ND', "map not installed")
            continue
        totpromoted += d['promoted']
        totrecut += d['recut']
        ok = (d['promoted'] == want and d['recut'] == 0)
        note = "  [control: both clauses silent]" if want == 0 else ""
        verdict("%s %s" % (tag, mapname),
                'PASS' if ok else 'FAIL',
                "solid-2 %d/%d promoted (%s bsp), %d re-cut%s"
                % (d['promoted'], want, src, d['recut'], note))

    # B2: the re-cut branch, graded only if it ever ran.
    boxes = [b for k in order for b in sect[k]['boxes']]
    if not boxes:
        verdict("B2 re-cut branch", 'ND',
                "0 of %d solid-2 props reached it -- every one promotes, so this "
                "path has never run on a shipped map" % totpromoted)
    else:
        bad = []
        for old, new, mdl in boxes:
            integral = all(abs(v - round(v)) < 1e-6 for v in new)
            symmetric = (abs(new[0] - new[1]) < 1e-6)
            contains = (-new[0] >= -old[0] - 1e-6 and -new[1] >= -old[1] - 1e-6
                        and -new[2] >= -old[2] - 1e-6)
            if not (integral and symmetric and contains):
                bad.append((old, new, mdl, integral, symmetric, contains))
        verdict("B2 re-cut branch", 'PASS' if not bad else 'FAIL',
                "%d box(es), %d wrong%s" % (len(boxes), len(bad),
                                            "" if not bad else "; first %s" % (bad[0],)))

    print()
    if rc == 0:
        print("PASS -- %d solid-2 prop(s) now cross the wire as a model rather than a"
              "\n        quantised box, so both sides trace the same shape." % totpromoted)
    else:
        print("FAIL -- see above.")
    return rc


if __name__ == '__main__':
    sys.exit(main())
