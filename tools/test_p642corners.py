#!/usr/bin/env python3
"""Patch 642's grader: a rounded corner is as sharp at 176 px as at 6.

python tools/test_p642corners.py <runlines_smoke.log of cfg/test/p642corners.cfg>

    python tools/runlines_smoke.py ftesurf/cfg/test/p642corners.cfg --mount --content C:/FTESurf \
        --output-dir <owned dir> --timeout 300

The cfg draws one white box (60,60)-(440,440) on black at each corner radius, twice: the way
before the patch (the 8 px mask stretched, `round png`) and from a mask made at that radius
(`round mask`).  This reads the screenshots (beside the log's folder) and compares the four
corner squares with the box's exact coverage, 0..1:

  edge   the mean difference from the exact coverage over the pixels within 1.5 px of the
         exact edge.  It does not thin out as the radius grows; a mean over the whole corner
         square did, and passed a mask with no antialiasing from 32 px up (the review's model).
  soft   pixels that are neither black nor white (0.05..0.95), over the exact count

Modelled (the mask as QC makes it, bilinear sampling): an honest corner on a radius the
ladder holds reads edge 0.000 and soft 1.00; no antialiasing 0.06..0.08 and 0; a premultiply
mismatch 0.05; one pixel out of place 0.21; the old stretched mask 0.18 at 20 px to 0.37 at
190.  A radius between two steps of the ladder (45, 100 here) is drawn from the next mask up,
shrunk by under a pixel, and reads up to 0.04: it has a looser bar and says so.

Three verdicts: passed (exit 0), failed (1), or a shot or status line is missing (2).
"""
import pathlib
import re
import sys

from PIL import Image

ON = (6, 12, 20, 32, 64, 96, 176)      # radii the ladder holds: one texel to a pixel
OFF = (45, 100)                        # between steps: from 46 and 104
RADII = tuple(sorted(ON + OFF))
X0, Y0, SIZE = 60, 60, 380
EDGE_ON = 0.020
EDGE_OFF = 0.060
EDGE_PNG = 0.100                       # the stretched mask from 20 px up
SOFT_LO, SOFT_HI = 0.5, 1.5            # on the ladder
STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)


def exact(r):
    """Each pixel of the corner squares: {(x, y): (coverage 0..1, distance to the edge)}."""
    cx = cy = X0 + SIZE / 2.0
    half = SIZE / 2.0
    out = {}
    m = 2
    for oy in (Y0 - m, Y0 + SIZE - r):
        for ox in (X0 - m, X0 + SIZE - r):
            for y in range(int(oy), int(oy + r + m)):
                for x in range(int(ox), int(ox + r + m)):
                    qx = abs(x + 0.5 - cx) - (half - r)
                    qy = abs(y + 0.5 - cy) - (half - r)
                    d = (max(qx, 0) ** 2 + max(qy, 0) ** 2) ** 0.5 + min(max(qx, qy), 0) - r
                    out[(x, y)] = (min(1.0, max(0.0, 0.5 - d)), d)
    return out


def measure(png, r):
    im = Image.open(png).convert('L')
    edge = band = soft = soft_want = 0
    for (x, y), (w, d) in exact(r).items():
        v = im.getpixel((x, y)) / 255.0
        if abs(d) <= 1.5:
            edge += abs(v - w)
            band += 1
        soft += 0.05 < v < 0.95
        soft_want += 0.05 < w < 0.95
    inside = im.getpixel((X0 + SIZE // 2, Y0 + SIZE // 2)) / 255.0
    outside = im.getpixel((X0 - 10, Y0 - 10)) / 255.0
    return edge / band, soft / max(1, soft_want), inside, outside


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    log = pathlib.Path(sys.argv[1])
    text = STAMP.sub('', log.read_text(encoding='utf-8', errors='replace'))
    shots = {p.stem: p for p in log.parent.parent.rglob('p642_*.png')}
    results = []

    def check(name, ok, detail):
        results.append((name, ok, detail))

    rows = {}
    for way in ('png', 'mask'):
        for r in RADII:
            p = shots.get('p642_%s_r%d' % (way, r))
            rows[(way, r)] = measure(p, r) if p else None
    print('%-6s  %-30s %-30s' % ('radius', 'before (8 px mask stretched)', 'after (mask at its size)'))
    for r in RADII:
        cells = []
        for way in ('png', 'mask'):
            m = rows[(way, r)]
            cells.append('no shot' if m is None else 'edge %.3f  soft x%.2f' % (m[0], m[1]))
        print('%-6d  %-30s %-30s' % (r, cells[0], cells[1]))

    missing = [k for k, v in rows.items() if v is None]
    if missing:
        check('the shots', None, 'missing: %s' % missing)
    else:
        drew = [k for k, v in rows.items() if v[2] < 0.95 or v[3] > 0.05]
        check('every shot holds the white box on black', not drew,
              ('not drawn: %s' % drew) if drew else '%d shots' % len(rows))
        bad = ['%d px: %.3f' % (r, rows[('mask', r)][0]) for r in ON if rows[('mask', r)][0] > EDGE_ON]
        check('on the ladder, a corner matches the exact shape along its edge', not bad,
              ('over %.3f: %s' % (EDGE_ON, '; '.join(bad))) if bad
              else 'edge %.3f to %.3f, bar %.3f' % (min(rows[('mask', r)][0] for r in ON),
                                                    max(rows[('mask', r)][0] for r in ON), EDGE_ON))
        bad = ['%d px: x%.2f' % (r, rows[('mask', r)][1]) for r in ON
               if not SOFT_LO <= rows[('mask', r)][1] <= SOFT_HI]
        check('... with an antialiased edge one pixel wide', not bad,
              ('outside %.1f..%.1f: %s' % (SOFT_LO, SOFT_HI, '; '.join(bad))) if bad
              else 'soft x%.2f to x%.2f of the exact count' % (min(rows[('mask', r)][1] for r in ON),
                                                             max(rows[('mask', r)][1] for r in ON)))
        bad = ['%d px: %.3f' % (r, rows[('mask', r)][0]) for r in OFF if rows[('mask', r)][0] > EDGE_OFF]
        check('between two steps (the next mask up, shrunk) it stays close', not bad,
              ', '.join('%d px: %.3f' % (r, rows[('mask', r)][0]) for r in OFF) + ' (bar %.3f)' % EDGE_OFF)
        big = [r for r in RADII if r >= 20]
        seen = [r for r in big if rows[('png', r)][0] >= EDGE_PNG]
        check('the measure sees the old fault: the stretched mask is off from 20 px up', seen == big,
              ', '.join('%d px: %.3f' % (r, rows[('png', r)][0]) for r in big) + ' (bar %.3f)' % EDGE_PNG)

    p = shots.get('p642_mask_r32_restarted')
    st = re.findall(r'sui_masks made (\S+) off (\S+) last (\S+) gen (\S+)', text)
    if not p or len(st) < 2:
        check('after a video restart', None, 'shot %s, status lines %d' % (bool(p), len(st)))
    else:
        m = measure(p, 32)
        check('after a video restart the masks are made again under the next number',
              m[0] <= EDGE_ON and m[2] > 0.95 and float(st[1][3]) > float(st[0][3]) and st[1][1] == '0'
              and float(st[1][0]) > float(st[0][0]),
              'edge %.3f; made %s then %s; number %s then %s; fallback %s'
              % (m[0], st[0][0], st[1][0], st[0][3], st[1][3], st[1][1]))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P642: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


if __name__ == '__main__':
    raise SystemExit(main())
