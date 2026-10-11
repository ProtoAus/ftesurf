#!/usr/bin/env python3
"""Patch 645's grader: the engine draws the run lines, and the picture is the one QC drew.

python tools/test_p645lines.py <runlines_smoke.log of cfg/test/p645lines.cfg>

    python tools/runlines_smoke.py ftesurf/cfg/test/p645lines.cfg --mount --content C:/FTESurf \
        --client <ftesurf64.exe with Patch 645> --output-dir <owned dir> --timeout 360

Each view is shot the QC way (qc), the engine's way (nat) and the QC way again (qc2).

  the view holds still   qc and qc2, taken either side of nat, are the same picture; else the
                         view is NOT MEASURED (something in it moves by itself)
  the lines are in it    a single-line view differs from the same camera with everything
                         switched off in at least SEEN pixels; else NOT MEASURED (two empty
                         pictures agree and say nothing)
  the same picture       nat is qc: on the paused replay every pixel, exactly.  The live view
                         is surf_dune, whose light flickers (thousands of pixels move by 1
                         of 255 between frames, a few by more), so there the three frames
                         are compared on the line's own pixels, grown by two, within 3 of
                         255; what differs elsewhere is printed
  demo0                  the line stops at the playhead, which is where the camera is: eight
                         segments, nearly all off the top of the screen.  It is judged on
                         its counts as much as its picture
  the same work          `scores lines` and `lines native` report the same segments, points,
                         clipped and wild counts and the same screen box both ways
  who drew               `lines native`: the engine's passes ran in nat and not in qc, and it
                         refused none (a refused pass falls back to QC and would compare QC
                         with itself)

`wide` is the view that takes one polygon batch past 32768 vertices (8 lines x 413 segments
x 10): the unfixed engine dies there drawing the QC way.

Three verdicts: passed (exit 0), failed (1), not measured (2).
"""
import pathlib
import re
import sys

from PIL import Image, ImageChops, ImageFilter

PAUSED = ('window', 'whole', 'wide', 'later', 'demo', 'demo0', 'slot5')
VIEWS = PAUSED + ('live',)
# single-line views: the shot of the same camera with nothing drawn, and how much must differ
# (measured: 86,529 with eight lines, marks and graph; about 2,490 for one line; 467 live)
OFF = {'later': ('p645_later_off', 2000), 'demo': ('p645_later_off', 300),
       'slot5': ('p645_later_off', 300), 'live': ('p645_live_off', 100)}
STRAY = 64                              # live: pixels off the line the engine's frame may differ in
STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)


def over(a, b, tol):
    """An image: 255 where any channel of a and b is more than tol apart; and the largest difference."""
    d = ImageChops.difference(Image.open(a).convert('RGB'), Image.open(b).convert('RGB'))
    worst = max(hi for _, hi in d.getextrema())
    r, g, bl = d.split()
    return ImageChops.lighter(ImageChops.lighter(r, g), bl).point(lambda v: 255 if v > tol else 0), worst


def count(img, mask=None):
    if mask is not None:
        img = ImageChops.multiply(img, mask)
    return sum(1 for v in img.tobytes() if v)


def differ(a, b, tol):
    """Pixels where any channel is more than tol apart, and the largest difference."""
    img, worst = over(a, b, tol)
    return count(img), worst


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    log = pathlib.Path(sys.argv[1])
    text = STAMP.sub('', log.read_text(encoding='utf-8', errors='replace'))
    shots = {p.stem: p for p in log.parent.parent.rglob('p645_*.png')}
    results = []

    def check(name, ok, detail):
        results.append((name, ok, detail))

    status = {}
    for m in re.finditer(r'^P645 (\w+) (qc2?|nat)\s*\n(.*?)(?=^P645 |^==== )', text, re.S | re.M):
        body = m.group(3)
        seg = re.search(r'lines: (\d+) drawn, (\d+) segments', body)
        nat = re.search(r'lines: native builtins (\d+) in use (\d+) passes (\d+) refused (\d+)', body)
        last = re.search(r'lines: last points (\S+) segments (\S+) wild (\S+) clipped (\S+)', body)
        box = re.search(r'lines: last box (\S+) (\S+) (\S+) (\S+)', body)
        status[(m.group(1), m.group(2))] = {
            'seg': seg.groups() if seg else None, 'nat': nat.groups() if nat else None,
            'last': (last.groups() + box.groups()) if last and box else None}

    for v in VIEWS:
        qc, nat, qc2 = (shots.get('p645_%s_%s' % (v, k)) for k in ('qc', 'nat', 'qc2'))
        sq, sn = status.get((v, 'qc')), status.get((v, 'nat'))
        if not (qc and qc2 and nat and sq and sn and sq['nat'] and sn['nat']):
            check('%s: shots and status' % v, None, 'shots %s %s %s, status %s %s'
                  % (bool(qc), bool(nat), bool(qc2), bool(sq and sq['nat']), bool(sn and sn['nat'])))
            continue
        if sn['nat'][0] != '1':
            check('%s: the engine has the builtins' % v, None, 'lines native says builtins %s' % sn['nat'][0])
            continue
        if v in OFF:
            name, bar = OFF[v]
            off = shots.get(name)
            ink = over(qc, off, 3)[0] if off else None
            seen = count(ink) if off else -1
            if seen < bar:
                check('%s: lines are in the picture compared' % v, None,
                      '%d pixels differ from the same camera with them switched off (bar %d)' % (seen, bar))
                continue
            check('%s: lines are in the picture compared' % v, True,
                  '%d pixels differ from the same camera with them switched off (bar %d)' % (seen, bar))
        if v in PAUSED:
            still, _ = differ(qc, qc2, 0)
            if still:
                check('%s: the view holds still' % v, None,
                      '%d pixels differ between the QC frames either side of the engine\'s' % still)
                continue
            same, worst = differ(qc, nat, 0)
            check('%s: the engine\'s picture is QC\'s, every pixel' % v, same == 0,
                  '%d pixels differ, largest difference %d of 255' % (same, worst))
        else:
            # the line's own pixels, grown by two; the rest of the frame is the map's
            mask = ink.filter(ImageFilter.MaxFilter(5))
            hold, moved = over(qc, qc2, 3)[0], over(qc, nat, 3)[0]
            if count(hold, mask):
                check('%s: the line holds still' % v, None,
                      '%d of its pixels differ between the QC frames either side of the engine\'s'
                      % count(hold, mask))
                continue
            away = ImageChops.invert(mask)
            check('%s: the engine\'s line is QC\'s' % v, count(moved, mask) == 0 and count(moved, away) <= STRAY,
                  '%d of the line\'s %d pixels differ by more than 3; elsewhere %d do (bar %d), and %d between '
                  'the two QC frames (the map\'s own flicker)'
                  % (count(moved, mask), count(mask), count(moved, away), STRAY, count(hold, away)))
        passes_qc, passes_nat = int(sq['nat'][2]), int(sn['nat'][2])
        check('%s: the engine drew it, QC drew the other, and no pass was refused' % v,
              sq['nat'][1] == '0' and sn['nat'][1] == '1' and passes_nat > passes_qc and sn['nat'][3] == '0',
              'in use %s then %s; passes %d then %d; refused %s'
              % (sq['nat'][1], sn['nat'][1], passes_qc, passes_nat, sn['nat'][3]))
        ok = (sq['seg'] is not None and sq['seg'] == sn['seg'] and int(sq['seg'][1]) > 0
              and sq['last'] is not None and sq['last'] == sn['last'])
        check('%s: the same counts and screen box both ways' % v, ok,
              'segments QC %s engine %s; points, segments, wild, clipped, box QC %s engine %s'
              % (sq['seg'], sn['seg'], sq['last'], sn['last']))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P645: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


if __name__ == '__main__':
    raise SystemExit(main())
