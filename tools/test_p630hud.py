#!/usr/bin/env python3
"""Grade cfg/test/p630hud.cfg's log (Patch 630: hud_edit sizes and modes).

python tools/runlines_smoke.py ftesurf/cfg/test/p630hud.cfg --output-dir <dir>
python tools/test_p630hud.py <rig>/ftesurf/logs/runlines_smoke.log

Three verdicts: every check passed (exit 0), a check failed (1), or a section the
cfg should have printed is not in the log, so nothing was measured there (2).
The numbers are the client's own: `hud_edit status` rects, `hud_edit ui` hit
rects, the engine's cvar read after each click.  The cfg pins hud_scale 2.
"""
import pathlib
import re
import sys

STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)


def sections(text):
    """marker -> the log between `P630 <marker>` and the next marker or banner."""
    text = STAMP.sub('', text)
    out = {}
    parts = re.split(r'^(?:P630 (.+?)|====.*)\s*$', text, flags=re.M)
    # parts: [before, name-or-None, body, name-or-None, body, ...]
    for i in range(1, len(parts) - 1, 2):
        if parts[i] is not None:
            out[parts[i].strip()] = parts[i + 1]
    return out


def rect(body, ident):
    m = re.search(r'^\s*%s\s+\S+\s+x\s+\S+\s+y\s+\S+\s+drawn (\S+)x(\S+) at (\S+),(\S+)' % re.escape(ident),
                  body, re.M)
    return tuple(float(v) for v in (m.group(3), m.group(4), m.group(1), m.group(2))) if m else None


def elements(body):
    return {m.group(1): tuple(float(v) for v in m.group(2).split())
            for m in re.finditer(r'sui_element \[([^\]]+)\] (\S+ \S+ \S+ \S+)', body)}


def read(body, cv):
    m = re.search(r'"%s" is "([^"]*)"' % re.escape(cv), body)
    return m.group(1) if m else None


def main():
    text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace')
    sec = sections(text)
    results = []            # (name, verdict, detail): verdict True, False or None (not measured)

    def check(name, ok, detail):
        results.append((name, ok, detail))

    def need(marker):
        if marker not in sec:
            check(marker, None, 'section not in the log')
            return None
        return sec[marker]

    # --- what the speedometer draws -------------------------------------------------
    S, E = 48.0, 32.0       # 24 and 16 hud_scale units at hud_scale 2
    for marker, want in (('mode both', S + E), ('mode speed', S), ('mode energy', E),
                         ('mode energy-legacy', E), ('mode both-legacy', S)):
        body = need(marker)
        if body is None:
            continue
        r = rect(body, 'speed')
        if r is None:
            check(marker, None, 'no drawn rect for speed')
        else:
            check(marker, r[3] == want, 'speed box height %g, want %g' % (r[3], want))

    # --- a pane's boxes ---------------------------------------------------------------
    def boxes(marker, cv, sizes, twin, twinsizes):
        body = need(marker)
        if body is None:
            return
        el = elements(body)
        if not el:
            check(marker, None, 'no sui_element lines')
            return
        ids = ['he_o_%s%s' % (cv, s) for s in sizes]
        missing = [i for i in ids if i not in el]
        check('%s: %s boxes' % (marker, cv), not missing,
              'missing %s' % missing if missing else '%d boxes: %s' % (len(ids), ' '.join(sizes)))
        if missing or twin is None:
            return
        tids = ['he_sz_%s%s' % (twin, s) for s in twinsizes]
        if any(t not in el for t in tids):
            check('%s: same boxes as the size row' % marker, None, 'size row %s not listed' % tids)
            return
        same = all(el[a][0] == el[b][0] and el[a][2:] == el[b][2:] for a, b in zip(ids, tids))
        check('%s: same boxes as the size row' % marker, same,
              'x w h of %s against %s: %s / %s' % (ids[0], tids[0], el[ids[0]], el[tids[0]]))

    boxes('pane speed', 'hud_energy_size', ['40', '48', '64', '80'], 'speed', ['40', '48', '64', '80'])
    body = sec.get('pane speed')
    if body is not None:
        el = elements(body)
        for i in ('he_o_hud_speed_show', 'he_o_hud_energy', 'he_o_hud_energy_ref'):
            check('pane speed: %s' % i, i in el, 'listed' if i in el else 'not listed')
    boxes('pane timer', 'hud_timer_sub_size', ['12', '16', '20', '24'], 'timer', ['32', '48', '64', '80'])
    boxes('pane mouse', 'hud_keys_size', ['1', '1.25', '1.5', '2'], None, None)

    for marker, ident in (('pane trainer', 'trainer'), ('pane graph', 'graph')):
        body = need(marker)
        if body is None:
            continue
        el = elements(body)
        got = sorted(int(k[len('he_sz_' + ident):]) for k in el if k.startswith('he_sz_' + ident))
        check('%s: size rungs' % marker, got == [16, 20, 24, 28], 'offered %s, want [16, 20, 24, 28]' % got)

    # --- what each click wrote -----------------------------------------------------------
    # 'migrated': hud_energy 0 was set before the map (a config saved with the line off)
    for marker, cv, want in (('read migrated energy', 'hud_energy', 1), ('read migrated show', 'hud_speed_show', 0),
                             ('read energy64', 'hud_energy_size', 64), ('read energyauto', 'hud_energy_size', 0),
                             ('read show2', 'hud_speed_show', 2), ('read show0', 'hud_speed_show', 0),
                             ('read show1', 'hud_speed_show', 1), ('read unit2', 'hud_energy', 2),
                             ('read unit1', 'hud_energy', 1), ('read sub20', 'hud_timer_sub_size', 20),
                             ('read subauto', 'hud_timer_sub_size', 0), ('read keys2', 'hud_keys_size', 2),
                             ('read keys2again', 'hud_keys_size', 2), ('read keys125', 'hud_keys_size', 1.25),
                             ('read keys1', 'hud_keys_size', 1)):
        body = need(marker)
        if body is None:
            continue
        v = read(body, cv)
        if v is None:
            check(marker, None, 'no read of %s' % cv)
        else:
            check(marker, float(v) == want, '%s is "%s", want %g' % (cv, v, want))

    # --- the key block and the mouse pad at each size ----------------------------------
    geo = {}
    for marker in ('size S', 'size XL', 'size M', 'size S2'):
        body = need(marker)
        if body is None:
            continue
        k, m = rect(body, 'keys'), rect(body, 'mouse')
        if k is None or m is None:
            check(marker, None, 'keys %s mouse %s' % (k, m))
        else:
            geo[marker] = (k, m)
    if 'size S' in geo:
        ks, ms = geo['size S']
        for marker, mul in (('size XL', 2.0), ('size M', 1.25)):
            if marker not in geo:
                continue
            k, m = geo[marker]
            check('%s: key block %gx' % (marker, mul), k[2] == ks[2] * mul and k[3] == ks[3] * mul,
                  '%gx%g against %gx%g' % (k[2], k[3], ks[2], ks[3]))
            check('%s: same right and bottom gap' % marker,
                  abs((k[0] + k[2]) - (ks[0] + ks[2])) < 0.01 and abs((k[1] + k[3]) - (ks[1] + ks[3])) < 0.01,
                  'right %g bottom %g against %g %g' % (k[0] + k[2], k[1] + k[3], ks[0] + ks[2], ks[1] + ks[3]))
            gap = 4 * mul           # 2 hud_scale units at hud_scale 2
            # the pad is on whole pixels, so half a pixel is the tolerance: with 1 the
            # build before the patch passed this at M (its gap is 4, M's is 5)
            check('%s: pad beside it' % marker,
                  abs(m[3] - k[3]) <= 0.51 and abs(m[1] - k[1]) <= 0.51
                  and abs((m[0] + m[2]) - (k[0] - gap)) <= 0.51 and abs(m[2] - 1.6 * k[3]) <= 0.51,
                  'pad %s keys %s gap %g' % (m, k, gap))
        if 'size S2' in geo:
            check('size S2: back where it was', geo['size S2'] == geo['size S'],
                  '%s against %s' % (geo['size S2'], geo['size S']))

    # --- hud_scale 3: the size-S block has no floor gap in a 900-line window ----------
    scr = re.findall(r'sui_work frames \S+ quads \S+ screen (\S+) (\S+)', text)
    s3 = {m: rect(sec[m], 'keys') for m in ('scale3 S', 'scale3 XL') if m in sec}
    if len(s3) < 2 or None in s3.values() or not scr:
        check('scale 3', None, 'rects %s, screen %s' % (s3, scr[-1:] if scr else 'not printed'))
    else:
        ks, kx, bottom = s3['scale3 S'], s3['scale3 XL'], float(scr[-1][1])
        check('scale 3: the size-S block has no floor gap', ks[1] + ks[3] >= bottom,
              'S ends at %g of %g' % (ks[1] + ks[3], bottom))
        check('scale 3: XL is twice S', kx[2] == 2 * ks[2] and kx[3] == 2 * ks[3],
              '%gx%g against %gx%g' % (kx[2], kx[3], ks[2], ks[3]))
        check('scale 3: XL stands on the bottom edge', abs((kx[1] + kx[3]) - bottom) < 0.01,
              'XL ends at %g of %g' % (kx[1] + kx[3], bottom))

    bad = [w for w in ('sui_probe: no control', 'Unknown command') if w in text]
    check('no refused probe or unknown command', not bad, 'found %s' % bad if bad else 'none in the log')

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P630: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


if __name__ == '__main__':
    raise SystemExit(main())
