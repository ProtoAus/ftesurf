#!/usr/bin/env python3
"""Patch 649's grader: sixty-four board lines, and a new slot draws what an old one does.

python tools/test_p649lines.py <runlines_smoke.log of cfg/test/p649lines.cfg>

    python tools/runlines_smoke.py ftesurf/cfg/test/p649lines.cfg --mount --content C:/FTESurf \
        --output-dir <owned dir> --timeout 480          (an engine with Patch 645)

The same run is loaded into every slot under one camera, which rides a replay of that run.

  eight, then sixty-four   `scores lines` says 8 drawn and then 64 drawn, each line with the same
                           point count, and sixty-four draw exactly eight times the segments
                           of eight
  marks on the first eight `lines native` counts the same marks with sixty-four lines as with
                           eight, and more than none
  a moved viewer           half a second after `replay seek` 25 s on, every one of the
                           sixty-four cursors (`lines order`) is within T_NEAR seconds of the
                           playhead and D_NEAR units of the eye.  A line's own look at
                           itself comes every two seconds at this count, so without the
                           look a moved viewer asks for, three in four would still be behind
  a moving viewer          the same after three seconds of the replay playing
  a new slot alone         line 40 and line 64 alone are line 5 alone, every pixel, with the
                           same counts, marks and screen box; and line 5 alone differs from no
                           line at all in at least SEEN pixels (two empty pictures agree and
                           say nothing)
  past the end             `scores lineat 65` and `0` answer with the usage line and load nothing
  a live run               eight lines ticked on another map and a short walk off the start:
                           the live line is built three times or more (else NOT MEASURED) and
                           the eight are not repainted for it.  Before, every build of the
                           live line repainted every ticked line from its first sample
  no refusals              `lines native` counts no refused pass; NOT MEASURED where the
                           engine's path is not the one in use

It also prints what the two crowds cost (QC time a frame); that is not graded.

AN OLDER ENGINE (Patch 654).  Run with `--client <an exe before Patch 645>` the log says
`native builtins 0`, and three other checks are made instead: the client reaches the end of
the cfg, sixty-four asks leave eight lines drawn, and a ninth is refused in words.  Without
654 the first fails: that engine dies as the fortieth line is added.

Three verdicts: passed (exit 0), failed (1), not measured (2).
"""
import pathlib
import re
import sys

from PIL import Image, ImageChops

SEEN = 300
T_NEAR = 0.5
D_NEAR = 200
STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)


def differ(a, b):
    d = ImageChops.difference(Image.open(a).convert('RGB'), Image.open(b).convert('RGB'))
    r, g, bl = d.split()
    over = ImageChops.lighter(ImageChops.lighter(r, g), bl)
    return sum(1 for v in over.tobytes() if v), max(hi for _, hi in d.getextrema())


def block(text, start, end=None):
    stop = re.escape(end) if end else r'P649 |==== |PERF SAMPLE '
    m = re.search(r'^%s\s*\n(.*?)(?=^(?:%s))' % (re.escape(start), stop), text, re.S | re.M)
    return m.group(1) if m else None


def facts(body):
    """What a status block says: lines drawn, segments, points a line, the engine's counters, marks."""
    if body is None:
        return None
    seg = re.search(r'lines: (\d+) drawn, (\d+) segments', body)
    pts = set(re.findall(r'^\s*line \d+ drawn\s+\S+\s+(\d+) pts', body, re.M))
    nat = re.search(r'lines: native builtins (\d+) in use (\d+) passes (\d+) refused (\d+)', body)
    last = re.search(r'lines: last points (\S+) segments (\S+) wild (\S+) clipped (\S+)\s*\n\s*lines: last box (\S+) (\S+) (\S+) (\S+)', body)
    marks = re.search(r'lines: last marks (\d+) of the first (\d+) lines', body)
    if not (seg and nat and last and marks):
        return None
    return {'drawn': int(seg.group(1)), 'seg': int(seg.group(2)), 'pts': pts, 'inuse': nat.group(2),
            'refused': int(nat.group(4)), 'last': last.groups(), 'marks': int(marks.group(1)),
            'marked': int(marks.group(2))}


def cursors(body):
    """(playhead t, [(slot, cursor t, units from the eye)]) of a `replay status` + `lines order` block."""
    if body is None:
        return None
    t = re.search(r'^\s*t (-?\d+\.\d+)\s+span ', body, re.M)
    rows = [(int(s), float(ct), float(d)) for s, ct, d in
            re.findall(r'lines: order slot (\d+) cursor \S+ t (-?\d+\.\d+) at (-?\d+\.\d+) u', body)]
    return (float(t.group(1)), rows) if t else None


def report(results):
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P649: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    log = pathlib.Path(sys.argv[1])
    text = STAMP.sub('', log.read_text(encoding='utf-8', errors='replace'))
    shots = {p.stem: p for p in log.parent.parent.rglob('p649_*.png')}
    results = []

    def check(name, ok, detail):
        results.append((name, ok, detail))

    n8, n64 = facts(block(text, 'P649 CROWD n8')), facts(block(text, 'P649 CROWD n64'))
    if 'lines: native builtins 0 ' in text and 'lines: native builtins 1 ' not in text:
        # Patch 654: an engine before Patch 645.  It has no line builtins and dies when one
        # polygon batch reaches 32768 vertices, which the fortieth line did; it keeps eight.
        said = len(re.findall(r'^scores lineat <1\.\.8> <path> \[leg\]', text, re.M))
        last = [l for l in text.splitlines() if l.strip()][-1][:70]
        check('an older engine: the client reaches the end', 'P649 end' in text, 'last line: %s' % last)
        if not (n8 and n64):
            check('an older engine: eight lines, asked for sixty-four', None,
                  'status blocks: %s %s' % (bool(n8), bool(n64)))
        else:
            check('an older engine: eight lines, asked for sixty-four',
                  n8['drawn'] == 8 and n64['drawn'] == 8 and n64['seg'] == n8['seg'],
                  '%d drawn (%d segments), then %d drawn (%d segments)'
                  % (n8['drawn'], n8['seg'], n64['drawn'], n64['seg']))
        check('an older engine: a ninth line is refused in words', said >= 56,
              '%d usage lines naming 1..8 (fifty-six asks past the eighth, and more after)' % said)
        return report(results)
    if not (n8 and n64):
        check('eight, then sixty-four', None, 'status blocks: %s %s' % (bool(n8), bool(n64)))
    else:
        check('eight lines draw', n8['drawn'] == 8 and n8['seg'] > 0 and len(n8['pts']) == 1,
              '%d drawn, %d segments, points a line %s' % (n8['drawn'], n8['seg'], sorted(n8['pts'])))
        check('sixty-four draw, each what one of the eight does',
              n64['drawn'] == 64 and n64['seg'] == 8 * n8['seg'] and n64['pts'] == n8['pts'],
              '%d drawn, %d segments against 8 x %d = %d, points a line %s'
              % (n64['drawn'], n64['seg'], n8['seg'], 8 * n8['seg'], sorted(n64['pts'])))
        check('marks on the first eight only', n8['marks'] > 0 and n64['marks'] == n8['marks'] and n64['marked'] == 8,
              '%d marks with eight lines, %d with sixty-four (hud_lines_marked %d)'
              % (n8['marks'], n64['marks'], n64['marked']))
        if n64['inuse'] != '1':
            check('no pass refused', None, 'the engine\'s path is not in use here (in use %s)' % n64['inuse'])
        else:
            check('no pass refused', n8['refused'] == 0 and n64['refused'] == 0,
                  'refused %d then %d' % (n8['refused'], n64['refused']))

    for name, label in (('MOVED', 'a moved viewer: every cursor is with it half a second on'),
                        ('PLAYING', 'a moving viewer: every cursor stays with it')):
        c = cursors(block(text, 'P649 %s' % name, 'P649 %s END' % name))
        if not c or len(c[1]) != 64:
            check(label, None, 'playhead %s, cursor rows %s' % (bool(c), len(c[1]) if c else 0))
            continue
        t, rows = c
        late = [(s, ct, d) for s, ct, d in rows if abs(ct - t) > T_NEAR or d > D_NEAR]
        check(label, not late,
              'playhead %.2f s; cursors %.2f..%.2f s, %.0f..%.0f u from the eye; %d of 64 astray%s'
              % (t, min(r[1] for r in rows), max(r[1] for r in rows), min(r[2] for r in rows),
                 max(r[2] for r in rows), len(late),
                 (' (slot %d at %.2f s, %.0f u)' % late[0]) if late else ''))

    one = {n: facts(block(text, 'P649 ALONE %d' % n)) for n in (5, 40, 64)}
    pics = {n: shots.get('p649_alone%d' % n) for n in (5, 40, 64)}
    off = shots.get('p649_off')
    if not (all(one.values()) and all(pics.values()) and off):
        check('a new slot alone', None, 'status %s, shots %s, off %s'
              % ({n: bool(v) for n, v in one.items()}, {n: bool(v) for n, v in pics.items()}, bool(off)))
    else:
        seen, _ = differ(pics[5], off)
        if seen < SEEN or one[5]['drawn'] != 1:
            check('line 5 alone is in its picture', None, '%d pixels differ from no line (bar %d); %d drawn'
                  % (seen, SEEN, one[5]['drawn']))
        else:
            check('line 5 alone is in its picture', one[5]['marks'] > 0,
                  '%d pixels differ from no line (bar %d); %d marks on it' % (seen, SEEN, one[5]['marks']))
            for n in (40, 64):
                same, worst = differ(pics[5], pics[n])
                check('line %d alone is line 5 alone' % n,
                      same == 0 and one[n]['drawn'] == 1 and one[n]['seg'] == one[5]['seg']
                      and one[n]['last'] == one[5]['last'] and one[n]['pts'] == one[5]['pts']
                      and one[n]['marks'] == one[5]['marks'],
                      '%d pixels differ (largest %d of 255); segments %d and %d; marks %d and %d; counts and box %s and %s'
                      % (same, worst, one[n]['seg'], one[5]['seg'], one[n]['marks'], one[5]['marks'],
                         one[n]['last'], one[5]['last']))

    past = block(text, '==== P649 PAST THE END ====')
    usage = len(re.findall(r'scores lineat <1\.\.64> <path> \[leg\]', past or ''))
    queued = len(re.findall(r'scores: line \d+ queued', past or ''))
    check('a 65th line and a 0th are refused in words', None if past is None else (usage == 2 and queued == 0),
          'usage lines %d, lines queued %d' % (usage, queued))

    live0 = block(text, 'P649 LIVE before', 'P649 LIVE after')
    live1 = block(text, 'P649 LIVE after', 'P649 LIVE end')
    p0 = re.search(r'lines: repainted (\d+) times', live0 or '')
    p1 = re.search(r'lines: repainted (\d+) times.*?tables made in (\S+) ms', live1 or '')
    built = re.search(r'trail: run (\d+) samples, (\d+) Line_End passes', live1 or '')
    if not (p0 and p1 and built) or int(built.group(2)) < 3:
        # fewer than three builds of the live line: the thing that used to repaint the others did not happen
        check('a live run does not repaint the ticked lines', None, 'repaint counts %s %s; live line %s'
              % (bool(p0), bool(p1), ('%s samples, %s builds' % built.groups()) if built else 'no trail line'))
    else:
        more = int(p1.group(1)) - int(p0.group(1))
        check('a live run does not repaint the ticked lines', more <= 1,
              '%d repaints of the eight during a walk that built the live line %s times (it was eight a build); '
              'the tables took %s ms to make' % (more, built.group(2), p1.group(2)))

    cost = {}
    for name in ('n8', 'n64'):
        v = [float(x) for x in re.findall(r'PERF SAMPLE %s \d+\s*\n.*?^\s*(\d+\.\d+)\s+QC UpdateView' % name, text, re.S | re.M)]
        if v:
            cost[name] = sum(v) / len(v)
    if cost:
        print('QC time a frame (not graded): ' + ', '.join('%s %.2f ms' % (k, v / 1000) for k, v in cost.items()))

    return report(results)


if __name__ == '__main__':
    raise SystemExit(main())
