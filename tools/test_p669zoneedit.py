#!/usr/bin/env python3
"""Patch 669's grader: the zone editor on a hosted game, and on somebody else's server.

python tools/test_p669zoneedit.py <runlines_smoke.log>

    python tools/runlines_smoke.py ftesurf/cfg/test/p669zoneedit.cfg --mount --content C:/FTESurf \
        --output-dir <owned dir> --timeout 300
    python tools/runlines_smoke.py ftesurf/cfg/test/p669remote.cfg --mount --content C:/FTESurf \
        --dedicated --map surf_voyager --output-dir <owned dir> --timeout 200

THE HOSTED RUN (p669zoneedit.cfg)
  a save keeps the table   the map's own zones, saved by the editor and read back: every
                           `zone_edit: zone` line the same (type, track, segment, checkpoint,
                           box, where it sends you) and the same crc.  The crc alone would
                           not do: it does not cover a zone's destination.  An unchanged
                           table is refused a plain save first (`force` writes it)
  the panel's buttons      pressed by name (`zone_edit press <id>` runs the panel's own branch
                           for that element; sui's hit test is not what is tested): a track, a
                           row and the grid, + checkpoint into placing and back, delete,
                           reload, close, each read back from the status
  placed with the aim      three clicks while aiming make one start zone on bonus 9: a box
                           with a width and a depth, its floor and height on the 16-unit
                           grid and not above the floor that was hit, its spawn in its middle
                           on that floor.  NOT MEASURED where the aim met nothing solid
  an empty table           after every zone is deleted a save is refused in words
  a course by command      start, TWO stages, a checkpoint in the second, end, a checkpoint
                           in the start's segment, a bonus: saved and read back in course
                           order.  The first cut put the second stage's checkpoint in stage 1
  a stage deleted          the first stage goes: the second is stage 1 and keeps its checkpoint
  the host reads it        after the map is loaded again the server's and the client's own
                           lines state that table's crc
  the way back             `zone_edit forget`: the map's own zones and their crc again

THE REMOTE RUN (p669remote.cfg, --dedicated)
  no file by command       connected over a socket, every way of writing or removing a file
                           by command is refused in words and the table stays unsaved.  A
                           server can type a console command for a player

Three verdicts: passed (exit 0), failed (1), not measured (2).
"""
import pathlib
import re
import sys

STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)


def block(text, start, end):
    m = re.search(r'^%s\s*\n(.*?)^%s' % (re.escape(start), re.escape(end)), text, re.S | re.M)
    return m.group(1) if m else None


def zones(body):
    return re.findall(r'^zone_edit: zone \d+ (.*)$', body or '', re.M)


def head(body):
    m = re.search(r'^zone_edit: state (\d+) map (\S+) zones (\d+) points (\d+) dirty (\d+) crc (\S+)', body or '', re.M)
    return m.groups() if m else None


def shape(body):
    """type, track, segment and checkpoint of each zone line."""
    return [' '.join(z.split()[:7]) for z in zones(body)]


def report(results):
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P669: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    text = STAMP.sub('', pathlib.Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace'))
    results = []

    def check(name, ok, detail):
        results.append((name, ok, detail))

    if '==== P669 REMOTE ====' in text:
        made, after = block(text, 'P669 REMOTE made', 'P669 REMOTE after'), block(text, 'P669 REMOTE after', 'P669 REMOTE end')
        hm, ha = head(made), head(after)
        if not (hm and ha):
            check('no file by command on somebody else\'s server', None, 'no status')
        else:
            refused = len(re.findall(r'zone_edit\S*: on someone else\'s server', made))
            wrote = len(re.findall(r'zone_edit\S*: (saved \d+ zones|this machine\'s own file is gone)', made))
            check('no file by command on somebody else\'s server',
                  hm[4] == '1' and ha[4] == '1' and refused >= 5 and wrote == 0,
                  'a zone made by command (unsaved %s); %d of 5 asks refused in words; %d written or removed; still unsaved %s'
                  % (hm[4] == '1', refused, wrote, ha[4] == '1'))
        return report(results)

    before, after = block(text, 'P669 RT before', 'P669 RT after'), block(text, 'P669 RT after', 'P669 RT end')
    hb, ha = head(before), head(after)
    if not (hb and ha) or int(hb[2]) < 1:
        check('a save keeps the table', None, 'no status, or the map had no zones (%s %s)' % (hb, ha))
    else:
        zb, za = zones(before), zones(after)
        diff = sum(1 for a, b in zip(zb, za) if a != b) + abs(len(zb) - len(za))
        plain = block(text, 'P669 RT before', 'P669 RT forced') or ''
        said = re.search(r'zone_edit\S*: saved (\d+) zones to (\S+) \(crc (\w+)\)', before)
        check('a save keeps the table',
              diff == 0 and hb[5] == ha[5] and bool(said) and 'nothing has changed' in plain and 'saved' not in plain.split('nothing has changed')[0],
              '%d zones before, %d after, %d lines differ; crc %s then %s; unchanged table refused first %s; %s'
              % (len(zb), len(za), diff, hb[5], ha[5], 'nothing has changed' in plain,
                 ('written to ' + said.group(2)) if said else 'no saved line'))

    # The panel's buttons, pressed by name: each status is what that button should have left.
    def panel(start, end):
        body = block(text, 'P669 PANEL ' + start, 'P669 PANEL ' + end)
        m = re.search(r'^zone_edit: track (\S+) sel (\S+) grid (\S+) snap (\S+)', body or '', re.M)
        pl = re.search(r'^zone_edit: placing type (\S+) seg (\S+)', body or '', re.M)
        return (head(body), m.groups() if m else None, pl.groups() if pl else None)

    steps = [panel('track', 'sel'), panel('sel', 'placing'), panel('placing', 'deleted'),
             panel('deleted', 'reloaded'), panel('reloaded', 'closed'), panel('closed', 'end')]
    if not all(s[0] and s[1] for s in steps) or not hb:
        check('the panel\'s buttons do what they say', None, 'a status is missing')
    else:
        n0 = int(hb[2])
        want = [('a track', steps[0][1][0] == '1'),
                ('a row, the grid', steps[1][1][:4] == ('0', '0', '32', '1')),
                ('+ checkpoint into placing, on the surface', steps[2][0][0] == '2' and steps[2][1][3] == '0'
                 and steps[2][2] == ('3', '0')),
                ('delete', steps[3][0][0] == '1' and int(steps[3][0][2]) == n0 - 1 and steps[3][0][4] == '1'
                 and steps[3][1][1:4] == ('-1', '16', '1')),
                ('reload', int(steps[4][0][2]) == n0 and steps[4][0][4] == '0'),
                ('close', steps[5][0][0] == '0')]
        bad = [name for name, ok in want if not ok]
        check('the panel\'s buttons do what they say', not bad,
              '%d of %d pressed and answered%s' % (len(want) - len(bad), len(want), ('; wrong: ' + ', '.join(bad)) if bad else ''))

    pulled, done = block(text, 'P669 AIM h', 'P669 AIM done'), block(text, 'P669 AIM done', 'P669 AIM end')
    hp, hd = head(pulled), head(done)
    aimed = re.search(r'^zone_edit: placing .*? ok (\d+)', block(text, 'P669 AIM a', 'P669 AIM b') or '', re.M)
    if not (hp and hd) or hp[0] != '4':
        check('placed with the aim', None, 'the third click was never reached: state %s, aim ok %s'
              % (hp[0] if hp else '-', aimed.group(1) if aimed else '-'))
    else:
        new = [z for z in zones(done) if z.startswith('start track 9 ')]
        m = new and re.match(r'start track 9 seg 0 cp 0 pts 4 z (\S+) (\S+) box (\S+) (\S+) (\S+) (\S+) td (\d) (\S+) (\S+) (\S+)', new[0])
        if not m:
            check('placed with the aim', False, 'no start zone on bonus 9 after the clicks: %s' % new[:1])
        else:
            b, t, x0, y0, x1, y1 = (float(v) for v in m.groups()[:6])
            kind, tx, ty, tz = int(m.group(7)), float(m.group(8)), float(m.group(9)), float(m.group(10))
            grid = all(v == round(v / 16) * 16 for v in (b, t, x0, y0, x1, y1))
            mid = abs(tx - (x0 + x1) / 2) < 0.01 and abs(ty - (y0 + y1) / 2) < 0.01
            # The spawn stands on the floor that was hit (a unit over it), and the zone's bottom is
            # at that floor or less than a grid step under it: never above.
            floor_ok = b <= tz - 1 < b + 16
            check('placed with the aim', hd[0] == '1' and x1 > x0 and y1 > y0 and t - b >= 16 and grid and kind == 1 and mid and floor_ok,
                  'a box %g x %g, bottom %g, %g tall, on the grid %s; spawn kind %d in its middle %s at z %g (the floor hit + 1: bottom not above it %s); back in the panel %s'
                  % (x1 - x0, y1 - y0, b, t - b, grid, kind, mid, tz, floor_ok, hd[0] == '1'))

    empty = block(text, 'P669 EMPTY status', 'P669 EMPTY end')
    he = head(empty)
    if not he:
        check('an empty table is not saved', None, 'no status')
    else:
        check('an empty table is not saved', he[2] == '0' and 'nothing to save' in empty,
              '%s zones left; refused in words %s' % (he[2], 'nothing to save' in empty))

    made, saved = block(text, 'P669 BUILD made', 'P669 BUILD saved'), block(text, 'P669 BUILD saved', 'P669 BUILD end')
    hm, hs = head(made), head(saved)
    want = ['start track 0 seg 0 cp 0', 'checkpoint track 0 seg 0 cp 1', 'stage track 0 seg 1 cp 0',
            'stage track 0 seg 2 cp 0', 'checkpoint track 0 seg 2 cp 2', 'end track 0 seg 3 cp 0',
            'start track 1 seg 0 cp 0', 'end track 1 seg 1 cp 0']
    if not (hm and hs):
        check('a course made by command', None, 'no status')
    else:
        got = shape(saved)
        spawn = [z for z in zones(saved) if z.startswith(('start', 'stage')) and ' td 1 ' not in z]
        check('a course made by command', got == want and shape(made) == want and hm[5] == hs[5] and hs[4] == '0' and not spawn,
              'read back as %s; crc %s made, %s saved; starts and stages without a spawn: %d'
              % ('the eight in course order, the checkpoint in stage 2' if got == want else got, hm[5], hs[5], len(spawn)))

    dmade, dsaved = block(text, 'P669 DELETE made', 'P669 DELETE saved'), block(text, 'P669 DELETE saved', 'P669 DELETE end')
    hdm, hds = head(dmade), head(dsaved)
    dwant = ['start track 0 seg 0 cp 0', 'checkpoint track 0 seg 0 cp 1', 'stage track 0 seg 1 cp 0',
             'checkpoint track 0 seg 1 cp 2', 'end track 0 seg 2 cp 0', 'start track 1 seg 0 cp 0',
             'end track 1 seg 1 cp 0']
    if not (hdm and hds):
        check('a stage deleted', None, 'no status')
    else:
        got = shape(dsaved)
        check('a stage deleted', got == dwant and shape(dmade) == dwant and hdm[5] == hds[5] and hds[4] == '0',
              'read back as %s; crc %s made, %s saved'
              % ('seven: the second stage is stage 1 and has its checkpoint' if got == dwant else got, hdm[5], hds[5]))

    host = block(text, '==== P669 HOST ====', 'P669 HOST end')
    sv = re.search(r'zones\(sv\): (\d+) on (\S+) \((.*?)\) crc (\w+)', host or '')
    cl = re.search(r'^zones: (\d+) on (\S+) \((.*?)\) crc (\w+)', host or '', re.M)
    if not (host and hds):
        check('the hosted game reads the saved file', None, 'no HOST block or no saved table')
    elif not (sv and cl):
        check('the hosted game reads the saved file', None, 'server line %s, client line %s' % (bool(sv), bool(cl)))
    else:
        check('the hosted game reads the saved file',
              sv.group(4) == hds[5] and cl.group(4) == hds[5] and sv.group(1) == '7' and 'local' in sv.group(3).lower(),
              'saved crc %s; the server says %s zones (%s) crc %s, the client %s (%s) crc %s'
              % (hds[5], sv.group(1), sv.group(3), sv.group(4), cl.group(1), cl.group(3), cl.group(4)))

    gone = block(text, '==== P669 FORGET ====', 'P669 FORGET end')
    hf = head(block(text, 'P669 FORGET after', 'P669 FORGET end'))
    if not (hf and hb):
        check('the way back', None, 'no status')
    else:
        check('the way back', hf[2] == hb[2] and hf[5] == hb[5] and "this machine's own file is gone" in (gone or ''),
              '%s zones crc %s after forget; the map had %s crc %s; said so %s'
              % (hf[2], hf[5], hb[2], hb[5], "this machine's own file is gone" in (gone or '')))

    return report(results)


if __name__ == '__main__':
    raise SystemExit(main())
