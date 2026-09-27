"""Grade cfg/test/p460lock.cfg -- prop collision is on and not client-switchable.

Requirement: "Maps must have prop collision for this surf game to work ... ensure
its defaulted to on, and can't be turned off client side", unless sv_cheats is on.

READ THIS BEFORE CHANGING THE PARSER.  A latched cheat cvar still reports the
value the user ASKED for:

    variable hl2_propcollision is a cheat variable - latched
    "hl2_propcollision" is "0"
    Effective value is "1"

The cvar's string is "0" and the engine uses 1.  A grader keyed on `is "0"` would
conclude the set succeeded and pass a build where prop collision could be switched
off -- the readback line is the request, and `Effective value` is the answer.  So
the PASS condition is the presence of `Effective value is "<enforced>"`, and its
ABSENCE is what proves L5's cheat-enabled set landed.

The enforced values are the plugin's REGISTRATION defaults, because that is what
cvar.c:1159-1166 force-sets to (var->enginevalue), and a `set` in default.cfg does
not change a default -- CVAR_CONFIGDEFAULT is defined and nothing assigns it.

  L1/L2  hl2_propcollision       -> 1 (VPhysics) for requests 0, 2 and 3
  L3     hl2_dispcollision       -> 1
  L4     hl2_propcollision_nophy -> 0
  L5     with sv_cheats 1 the set lands: no Effective line
  L6     CONTROL hl2_propdist is not a cheat cvar and still sets

L6 is not decoration: without it, an engine that froze every plugin cvar would
pass L1-L4.

Usage: python tools/p460lock.py [ftesurf/logs/p460lock.log]
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TS = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ')
SECTION = re.compile(r'^={4} (L\d) ')
VALUE = re.compile(r'^"([A-Za-z0-9_]+)" is "([^"]*)"')
EFFECTIVE = re.compile(r'^Effective value is "([^"]*)"')
LATCHED = re.compile(r'^variable (\S+) is a cheat variable - latched')

rc = 0


def verdict(name, state, detail):
    global rc
    print("%s  %-30s %s" % ({'PASS': '  PASS', 'FAIL': '  FAIL', 'ND': '  ----'}[state],
                            name, detail))
    if state == 'FAIL':
        rc = 1


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(HERE), 'ftesurf', 'logs', 'p460lock.log')
    if not os.path.exists(path):
        print("no log at %s" % path)
        return 2

    # Per section: the (cvar, requested, effective-or-None, latched?) tuples in order.
    sect = {}
    order = []
    cur = None
    last = None
    for ln in open(path, encoding='utf-8', errors='replace'):
        ln = TS.sub('', ln.strip())
        m = SECTION.match(ln)
        if m:
            cur = m.group(1)
            sect.setdefault(cur, [])
            if cur not in order:
                order.append(cur)
            last = None
            continue
        if cur is None:
            continue
        m = LATCHED.match(ln)
        if m:
            sect[cur].append(['latch', m.group(1)])
            continue
        m = VALUE.match(ln)
        if m:
            last = [m.group(1), m.group(2), None]
            sect[cur].append(['read'] + last)
            continue
        m = EFFECTIVE.match(ln)
        if m and sect[cur]:
            for row in reversed(sect[cur]):
                if row[0] == 'read':
                    row[3] = m.group(1)
                    break
            continue

    if not order:
        print("no `==== L<n>` markers -- did the cfg run?")
        return 2

    def reads(s):
        return [r for r in sect.get(s, []) if r[0] == 'read']

    print("p460lock -- prop collision on, and not the client's to switch off")
    print("            (%s)" % path)
    print()

    # L1-L4: every request must be overridden to the enforced value.
    want = {'L1': ('hl2_propcollision', '1'),
            'L2': ('hl2_propcollision', '1'),
            'L3': ('hl2_dispcollision', '1'),
            'L4': ('hl2_propcollision_nophy', '0')}
    for s in ('L1', 'L2', 'L3', 'L4'):
        rs = reads(s)
        if not rs:
            verdict("%s %s" % (s, want[s][0]), 'ND', "no readback -- section did not run")
            continue
        cv, enforced = want[s]
        bad = [r for r in rs if r[1] != cv or r[3] != enforced]
        latched = sum(1 for r in sect.get(s, []) if r[0] == 'latch')
        verdict("%s %s locked" % (s, cv), 'PASS' if not bad and latched else 'FAIL',
                "%d request(s), %d latch message(s), effective %s%s"
                % (len(rs), latched,
                   "/".join(r[3] if r[3] is not None else "APPLIED" for r in rs),
                   "" if not bad else "  <-- wanted %s" % enforced))

    # L5: with cheats on, the set must LAND -- no effective-value override.
    rs = reads('L5')
    if not rs:
        verdict("L5 sv_cheats lets it through", 'ND', "no readback")
    else:
        r = rs[-1]
        ok = (r[1] == 'hl2_propcollision' and r[2] == '0' and r[3] is None)
        verdict("L5 sv_cheats lets it through", 'PASS' if ok else 'FAIL',
                "reads %s, effective %s -- %s"
                % (r[2], r[3] if r[3] is not None else "(none: applied)",
                   "the latch is conditional, not a constant" if ok
                   else "the set did NOT land, so L1-L4 may be a hard block"))

    # L6: the control.  A non-cheat cvar in the same family must still set.
    rs = reads('L6')
    if not rs:
        verdict("L6 CONTROL propdist sets", 'ND', "no readback")
    else:
        r = rs[-1]
        ok = (r[1] == 'hl2_propdist' and r[2] == '8000' and r[3] is None)
        verdict("L6 CONTROL propdist sets", 'PASS' if ok else 'FAIL',
                "reads %s, effective %s -- %s"
                % (r[2], r[3] if r[3] is not None else "(none: applied)",
                   "the lock is specific" if ok
                   else "a non-cheat plugin cvar is also frozen: the mask is too wide"))

    print()
    print("PASS -- prop collision cannot be turned off client side without sv_cheats."
          if rc == 0 else "FAIL -- see above.")
    return rc


if __name__ == '__main__':
    sys.exit(main())
