#!/usr/bin/env python3
"""Patch 637's grader: the HUD editor's defaults are the owner's layout of 11 Oct.

python tools/test_p637defaults.py <runlines_smoke.log of cfg/test/p637defaults.cfg> [--tree <checkout>]

    python tools/runlines_smoke.py ftesurf/cfg/test/p637defaults.cfg --mount --content C:/FTESurf \
        --output-dir <owned dir> --timeout 240

From the client's own prints in a FRESH overlay (no saved config, so a value read at boot is the
default): the settings the patch moved, every other setting the editor owns, the editor's
rectangles before and after the owner's whole saved layout is set by hand, the same settings put
back on their old defaults (the rectangles must move), and everything after "reset all".  From the
tree (--tree, default this checkout): that the game code, both default configs and the editor's
own list agree on each moved setting.  The tables are tools/p637_tables.py.

What it cannot see: an install with a saved config (a name saved there keeps its value whatever
the default becomes), and a real panel's size where the editor draws a stand-in box for one that
is not up.

Three verdicts: passed (exit 0), failed (1), or a step the checks need is not in the log (2).
"""
import pathlib
import re
import sys

from p637_tables import BEFORE, CHANGED, OLD

ROOT = pathlib.Path(__file__).resolve().parent.parent
STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)
ELEMENTS = ('timer', 'splits', 'seq', 'strafe', 'trainer', 'board', 'boarding', 'speed', 'banner',
            'graph', 'mouse', 'keys', 'debug', 'saveloc', 'gfx', 'vote', 'mapinfo', 'specby', 'net',
            'results')
# Two outlines are not where the panel draws, so the on-screen check leaves them out and says what
# their boxes do: the results card is centred on its setting and clamped (cl_results.qc) while the
# editor lists it from its corner; the trainer's drawer lifts the panel to fit (cl_trainer.qc) and
# the editor's box is not lifted.  At the owner's place the trainer's box runs past the bottom of a
# 900-line screen (BACKLOG, "The owner's layout as the defaults").
NOT_ITS_PLACE = ('results', 'trainer')


def same(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return a == b


def sections(text):
    text = STAMP.sub('', text)
    out = {}
    parts = re.split(r'^(?:P637 (.+?)|====.*)\s*$', text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        if parts[i] is not None:
            out[parts[i].strip()] = parts[i + 1]
    return out


def reads(body):
    """name -> (value, printed as the default)."""
    return {m.group(1): (m.group(2), m.group(3) is not None)
            for m in re.finditer(r'^"([A-Za-z0-9_]+)" is "([^"]*)"( \(default\))?', body, re.M)}


def rects(body):
    got = {m.group(1): tuple(float(v) for v in m.groups()[1:])
           for m in re.finditer(r'sui_element \[([^\]]+)\] (\S+) (\S+) (\S+) (\S+)', body or '')}
    return {k: v for k, v in got.items() if k in ELEMENTS}


def screen(body):
    m = re.search(r'sui_work .*? screen (\S+) (\S+)', body or '')
    return (float(m.group(1)), float(m.group(2))) if m else None


def differ(a, b):
    return [e for e in ELEMENTS if e in a and e in b and any(abs(x - y) > 0.51 for x, y in zip(a[e], b[e]))]


def static(tree):
    """Each moved setting, wherever the tree states its default: (place, value) pairs."""
    src = tree / 'src/client'
    qc = {f.name: f.read_text(encoding='utf-8', errors='replace') for f in sorted(src.glob('*.qc'))}
    cfgs = {n: (tree / 'ftesurf/cfg' / n).read_text(encoding='utf-8', errors='replace')
            for n in ('default.cfg', 'defaultuser.cfg')}
    he = qc['cl_hudedit.qc']
    lits = he[he.index('HE_Default ='):he.index('HE_ResetCvar =')]
    found = {}
    for name in CHANGED:
        places = []
        for fname, text in qc.items():
            for m in re.finditer(r'registercvar\("%s",\s*"([^"]*)"' % re.escape(name), text):
                places.append((fname, m.group(1)))
        for cname, text in cfgs.items():
            for m in re.finditer(r'(?m)^set[ \t]+%s[ \t]+(\S+)' % re.escape(name), text):
                places.append((cname, m.group(1).strip('"')))
        for m in re.finditer(r'seta %s (-?[0-9.]+)' % re.escape(name), lits):
            places.append(('HE_Default', m.group(1)))
        found[name] = places
    return found


def grade(text, tree):
    sec = sections(text)
    results = []

    def check(name, ok, detail):
        results.append((name, ok, detail))

    boot = reads(sec['boot']) if 'boot' in sec else None
    if not boot:
        check('boot', None, 'no settings read at boot')
    else:
        missing = [n for n in list(CHANGED) + list(BEFORE) if n not in boot]
        wrong = ['%s %s (want %s)' % (n, boot[n][0], v) for n, v in CHANGED.items()
                 if n in boot and not same(boot[n][0], v)]
        check('a fresh game starts on the owner\'s value for each setting the patch moved',
              not wrong and not any(n in missing for n in CHANGED),
              '%d of %d%s' % (len(CHANGED) - len(wrong) - sum(1 for n in CHANGED if n in missing), len(CHANGED),
                              ('; wrong: %s' % '; '.join(wrong[:8])) if wrong else ''))
        drift = ['%s %s (was %s)' % (n, boot[n][0], v) for n, v in BEFORE.items()
                 if n in boot and not same(boot[n][0], v)]
        check('... and every other setting the editor owns on the default it had',
              not drift and not any(n in missing for n in BEFORE),
              '%d of %d%s' % (len(BEFORE) - len(drift) - sum(1 for n in BEFORE if n in missing), len(BEFORE),
                              ('; moved: %s' % '; '.join(drift[:8])) if drift else ''))
        notdef = [n for n, (_v, d) in boot.items() if not d]
        check('each value read at boot is printed as the default (nothing set it)',
              not notdef and not missing,
              '%d read, %d not marked default%s%s' % (len(boot), len(notdef),
                                                      (': %s' % notdef[:6]) if notdef else '',
                                                      ('; not read: %s' % missing[:6]) if missing else ''))

    a, b = rects(sec.get('rects')), rects(sec.get('rects again'))
    size = screen(sec.get('rects'))
    if not a or not b or not size:
        check('layout', None, 'the editor\'s rectangles were not listed twice, or no screen size (%s, %s, %s)'
              % (bool(a), bool(b), size))
    else:
        lost = [e for e in ELEMENTS if e not in a or e not in b]
        moved = ['%s %s -> %s' % (e, a[e], b[e]) for e in differ(a, b)]
        check('setting the owner\'s whole saved layout by hand moves no element: the defaults are it',
              not moved and not lost, '%d elements compared%s%s' % (
                  len(ELEMENTS) - len(lost), ('; moved: %s' % '; '.join(moved[:6])) if moved else '',
                  ('; not listed: %s' % lost) if lost else ''))
        off = ['%s %s' % (e, a[e]) for e in ELEMENTS if e in a and e not in NOT_ITS_PLACE and
               (a[e][0] < -0.5 or a[e][1] < -0.5 or a[e][0] + a[e][2] > size[0] + 0.5
                or a[e][1] + a[e][3] > size[1] + 0.5)]
        past = ['%s by %.0f px' % (e, max(a[e][0] + a[e][2] - size[0], a[e][1] + a[e][3] - size[1]))
                for e in NOT_ITS_PLACE if e in a and
                (a[e][0] + a[e][2] > size[0] + 0.5 or a[e][1] + a[e][3] > size[1] + 0.5)]
        check('every element\'s rectangle is on the %gx%g screen' % size, not off,
              ('off screen: %s' % '; '.join(off)) if off
              else '%d on screen; left out, their drawers clamp them: %s%s'
              % (len(a) - len(NOT_ITS_PLACE), ', '.join(NOT_ITS_PLACE),
                 (' (box past the edge: %s)' % ', '.join(past)) if past else ''))

    mv = reads(sec['moved']) if 'moved' in sec else None
    c = rects(sec.get('rects moved'))
    if not mv or not a or not c:
        check('moved', None, 'the old defaults were not read back, or no rectangles in that state')
    else:
        bad = ['%s %s' % (n, mv[n][0] if n in mv else 'not read') for n, v in OLD.items()
               if n not in mv or not same(mv[n][0], v)]
        check('every moved setting put back on its old default, so the reset has work to do', not bad,
              '%d of %d read their old value%s' % (len(OLD) - len(bad), len(OLD),
                                                   ('; not: %s' % '; '.join(bad[:6])) if bad else ''))
        there = differ(a, c)
        check('... and the old defaults are another layout', len(there) >= 8,
              '%d of %d rectangles differ from the fresh game\'s: %s' % (len(there), len(ELEMENTS), ' '.join(there)))
    rs = reads(sec['reset']) if 'reset' in sec else None
    if not rs or not boot:
        check('reset', None, 'no settings read after the reset')
    else:
        diff = ['%s %s (boot %s)' % (n, rs[n][0], boot[n][0]) for n in boot if n in rs and not same(rs[n][0], boot[n][0])]
        gone = [n for n in boot if n not in rs]
        # the button's own line (the console's `hud_edit reset` words it differently)
        said = 'back to its shipped settings' in sec.get('click reset all', '')
        check('"reset all" puts every setting back on the value a fresh game has',
              not diff and not gone and said,
              '%d of %d%s%s; the editor said so: %s' % (len(boot) - len(diff) - len(gone), len(boot),
                                                        ('; differ: %s' % '; '.join(diff[:8])) if diff else '',
                                                        ('; not read: %s' % gone[:6]) if gone else '', said))
    d = rects(sec.get('rects reset'))
    if not a or not d:
        check('layout after the reset', None, 'rectangles not listed')
    else:
        moved = ['%s %s -> %s' % (e, a[e], d[e]) for e in differ(a, d)]
        check('... and every element back where a fresh game draws it', not moved,
              ('moved: %s' % '; '.join(moved[:6])) if moved else '%d elements' % len(d))

    found = static(tree)
    none = [n for n, p in found.items() if not any(f.endswith('.qc') for f, _ in p)]
    split = ['%s: %s' % (n, ', '.join('%s %s' % fv for fv in p)) for n, p in found.items()
             if any(not same(v, CHANGED[n]) for _f, v in p)]
    places = sum(len(p) for p in found.values())
    check('the tree agrees with itself: game code, both default configs and the editor\'s list',
          not split and not none, '%d places for %d settings%s%s' % (
              places, len(found), ('; disagree: %s' % '; '.join(split[:6])) if split else '',
              ('; not registered: %s' % none[:6]) if none else ''))

    bad = [w for w in ('sui_probe: no control', 'Unknown command') if w in text]
    check('no refused probe or unknown command', not bad, ('found %s' % bad) if bad else 'none in the log')

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P637: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


def main():
    args = list(sys.argv[1:])
    tree = ROOT
    if '--tree' in args:
        i = args.index('--tree')
        tree = pathlib.Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit(__doc__)
    text = pathlib.Path(args[0]).read_text(encoding='utf-8', errors='replace')
    return grade(text, tree)


if __name__ == '__main__':
    raise SystemExit(main())
