"""Grade cfg/test/p458prop.cfg -- prop scale parity.

The defect: `.scale` is a plain QC float and nothing clamps it on write, so one
number reached four readers three ways -- the wire and the renderer at
trunc(scale*16)/16, the server's pmove at the same expression WITHOUT the
truncation, and World_Move at the raw float.  `modelscale 1.4` predicted as
1.3750 on the client and moved the player against 1.4000 on the server.

SV_SpawnProp now floors the field to the 1/16 the wire carries.  A multiple of
1/16 is exact in float32, so once the field is on that grid every reader computes
the same number and there is nothing left to round.

WHAT IS GRADED, and the two grades answer different questions:

  P1  the COUNT.  `props: N spawned (... ) , M requantised` against this script's
      own reading of the BSP entity lump -- independent of the QC, written from
      the map format.  Two readers, one number, per map.  Also asserts the two
      CONTROLS print no clause at all: ahop_coast has 284 props and none needing
      the floor, bhop_eazy has no props.  A counter that always fires proves
      nothing, so the silent maps are the arm, not the noise.

  P2  the ARITHMETIC.  Every `propscale <raw> -> <scale>` line must satisfy
      scale == floor(raw*16)/16 and scale*16 must be a whole number.  This is the
      grade that proves the floor RAN: the count at P1 is derived from the raw
      value, so deleting the floor leaves P1 identical and only P2 moves.

  P3  COVERAGE.  The number of propscale lines must equal the reported count, per
      map.  Without it a floor that ran on one prop and was skipped on 224 would
      pass P2 on its single line.

Three verdicts.  NOT DEMONSTRATED is for a map that did not load or a build whose
spawn predates the counter -- an arm that goes red on a build that cannot answer
teaches nobody anything.

Usage: python tools/p458prop.py [ftesurf/logs/p458prop.log]
"""
import contextlib, io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
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
SECTION = re.compile(r'^={4} (M\d) (\S+) ')
PROPSLINE = re.compile(r'^props: (\d+) spawned \((\d+) solid, (\d+) scaled\)(.*)$')
REQUANT = re.compile(r'(\d+) requantised')
PSCALE = re.compile(r'^propscale (-?[\d.]+) -> (-?[\d.]+) (.*)$')

rc = 0
def verdict(name, state, detail):
    global rc
    tag = {'PASS': '  PASS', 'FAIL': '  FAIL', 'ND': '  ----'}[state]
    print("%s  %-34s %s" % (tag, name, detail))
    if state == 'FAIL':
        rc = 1


GAMEMAPS = os.path.join(os.path.dirname(HERE), 'ftesurf', 'maps')


def bsppath(mapname):
    """THE FILE THE SERVER ACTUALLY LOADED, and this is not a detail.

    The census scripts in tools/census read the Momentum install; the game loads
    ftesurf/maps.  For surf_dune those are DIFFERENT BUILDS -- 344 props in one
    and 176 in the other -- so the first cut of this grader marked a correct
    server wrong, having graded it against a map it never opened.  This
    codebase's own `mapcrc` note says it: a map name is not a map.  The gamedir
    wins, and the path is printed so a future mismatch names its own cause.
    """
    p = os.path.join(GAMEMAPS, mapname + '.bsp')
    if os.path.exists(p):
        return p, 'gamedir'
    p = os.path.join(pc.MAPS, mapname + '.bsp')
    if os.path.exists(p):
        return p, 'momentum'
    return None, None


def census(mapname):
    """What the BSP says: props the spawn will make, and how many need the floor.

    Mirrors SV_SpawnProp's order exactly -- a prop with no model or a '*N' brush
    model is dropped BEFORE the scale block, so it counts in neither number.
    """
    path, src = bsppath(mapname)
    if path is None:
        return None
    ents, _ = bsplib.read(path)
    n = req = 0
    for e in ents:
        if (e.get('classname') or '').lower() not in PROPS:
            continue
        mdl = e.get('model') or ''
        if mdl == '' or mdl.startswith('*'):
            continue
        n += 1
        ms = e.get('modelscale')
        if ms is None:
            continue
        try:
            v = float(ms)
        except ValueError:
            continue
        if v <= 0:
            v = 1.0
        if v > 15.9:
            v = 15.9
        # raw != floor(raw*16)/16, which is the QC's own test.  Covers both a
        # fractional sixteenth and a scale below 1/16 that the floor raises.
        if abs(v * 16.0 - int(v * 16.0 + 1e-9)) > 1e-9 or v < 1 / 16.0:
            req += 1
    return n, req, src


def main():
    path = _argv[1] if len(_argv) > 1 else os.path.join(
        os.path.dirname(HERE), 'ftesurf', 'logs', 'p458prop.log')
    if not os.path.exists(path):
        print("no log at %s" % path)
        return 2
    lines = open(path, encoding='utf-8', errors='replace').read().splitlines()

    # Split by section marker; a map's props line and propscale lines follow it.
    cur = None
    seen = {}
    order = []
    for ln in lines:
        ln = TS.sub('', ln.strip())
        m = SECTION.match(ln)
        if m:
            cur = (m.group(1), m.group(2))
            seen[cur] = {'props': None, 'requant': 0, 'clause': False, 'scales': []}
            order.append(cur)
            continue
        if cur is None:
            continue
        d = seen[cur]
        m = PROPSLINE.match(ln)
        if m and d['props'] is None:
            d['props'] = int(m.group(1))
            d['scaled'] = int(m.group(3))
            r = REQUANT.search(m.group(4))
            if r:
                d['requant'] = int(r.group(1))
                d['clause'] = True
            continue
        m = PSCALE.match(ln)
        if m:
            d['scales'].append((float(m.group(1)), float(m.group(2)), m.group(3)))

    if not order:
        print("no `==== M<n> <map>` markers in the log -- did the cfg run?")
        return 2

    print("p458prop -- prop scale parity  (%s)" % path)
    print()

    anymeasured = False
    for key in order:
        sec, mapname = key
        d = seen[key]
        exp = census(mapname)
        if d['props'] is None:
            verdict("P1 %s %s" % (sec, mapname), 'ND',
                    "no `props:` line -- map did not load, or this build has no counter")
            continue
        if exp is None:
            verdict("P1 %s %s" % (sec, mapname), 'ND',
                    "map not installed, nothing to grade the count against")
            continue
        anymeasured = True
        n, req, src = exp
        ok = (d['props'] == n and d['requant'] == req)
        # The controls: zero requantised MUST mean no clause printed at all.
        if req == 0 and d['clause']:
            verdict("P1 %s %s" % (sec, mapname), 'FAIL',
                    "BSP says 0 requantised but the clause printed %d -- the "
                    "condition fires when it should not" % d['requant'])
        else:
            verdict("P1 %s %s" % (sec, mapname), 'PASS' if ok else 'FAIL',
                    "props %d/%d, requantised %d/%d (server/%s bsp)%s"
                    % (d['props'], n, d['requant'], req, src,
                       "" if req else "  [control: clause silent]"))

        # P2: the arithmetic on every line the server printed.
        bad = []
        for raw, got, mdl in d['scales']:
            want = int(raw * 16.0 + 1e-6) / 16.0
            if want < 1 / 16.0:
                want = 1 / 16.0
            if abs(got - want) > 1e-6 or abs(got * 16.0 - round(got * 16.0)) > 1e-6:
                bad.append((raw, got, want, mdl))
        if not d['scales']:
            verdict("P2 %s arithmetic" % sec, 'ND' if req else 'PASS',
                    "no propscale lines" + ("" if req else " and none expected"))
        else:
            verdict("P2 %s arithmetic" % sec, 'PASS' if not bad else 'FAIL',
                    "%d line(s) checked, %d wrong%s"
                    % (len(d['scales']), len(bad),
                       "" if not bad else "; first %s -> %s want %s (%s)"
                       % (bad[0][0], bad[0][1], bad[0][2], bad[0][3])))

        # P3: every counted prop printed a line.
        if req:
            verdict("P3 %s coverage" % sec,
                    'PASS' if len(d['scales']) == d['requant'] else 'FAIL',
                    "%d propscale line(s) for %d counted"
                    % (len(d['scales']), d['requant']))

    print()
    if not anymeasured:
        print("NOT DEMONSTRATED -- nothing in this log could be graded.")
        return 2
    print("PASS -- prop scale is on the 1/16 grid the wire carries, so the client's"
          "\n        prediction and the server's move use one number."
          if rc == 0 else
          "FAIL -- see the lines above.")
    return rc


if __name__ == '__main__':
    sys.exit(main())
