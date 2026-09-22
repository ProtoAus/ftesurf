#!/usr/bin/env python3
"""
onlinecache.py -- the downloaded-replay cache (data/online/) and the stage
window a board click opens, modelled outside the game.  Patch 395.

    python tools/onlinecache.py names DIR
        every cached .rec under DIR (flat <id>.rec or <...>_r<id>.rec): its id,
        where it is, where Online_RecName files it
    python tools/onlinecache.py manifest DIR
        `id md5 expected-path` for every cached .rec under DIR (take it BEFORE a
        migration run; `verify` checks the run against it)
    python tools/onlinecache.py verify MANIFEST ONLINEDIR
        after a migration: no flat <id>.rec left, every manifest path present
        once with its md5, no .part.  Exit 0 when all hold
    python tools/onlinecache.py windows FILE [SEG ...]
        per stage: seg leg a b a_s b_s how, then the exact `replay: stage ...
        window` line Watch_StageWindow prints (SEG 0-based; all when omitted)
    python tools/onlinecache.py selftest DIR
        names and windows against the values pinned below
    python tools/onlinecache.py fixture SRC OUTDIR IDA IDB IDC
        three files cut from SRC mid-run: IDA.rec with the evidence trailer
        (`abandon`), IDB.rec with no trailer, IDC.rec the trailer minus `abandon`
    python tools/onlinecache.py serve PORT DIR
        a stub surfd for p395stub.cfg: STUB_BOARDS' stage rows carry `run`, and
        /api/replay/<id> serves DIR/<id>.rec

WRITTEN FROM THE GRAMMAR BLOCK over SV_RecOpen (src/server/sv_timer.qc), not
from cl_online.qc: header keys in any order up to `begin`, `owner` to the end
of the line, `movetickrate` preferred for seconds; `stagepost <seg> <dur>`
closes at the next `stage`/`end` tick; `abandon` means the run was not
finished.  Where the QC decides a number in float32, so does this (f32).
Stdlib only.
"""

import hashlib
import math
import os
import re
import struct
import sys

PM_TICK = 0.015
OR_TAIL = 16384         # cl_online.qc: bytes of the tail scanned for `end`/`abandon`
OR_HEADMAX = 64         # header lines read before giving up on `begin`
OR_WORDMAX = 48         # map directory cap (MAX_QPATH 128 over the whole name)
FS_WHO_NAMEMAX = 12     # sh_defs.qc
WT_STGMAX = 24          # cl_watch.qc (sv_timer.qc FS_MAXSPLITS)
WT_EVMAX = 64

LEAF_RE = re.compile(r'_r([0-9]+)\.rec$')
FLAT_RE = re.compile(r'^([0-9]+)\.rec$')


def f32(x):
    return struct.unpack('f', struct.pack('f', x))[0]


def lines_of(data):
    """fgets: split on \\n, every \\r dropped, 4095 chars at most."""
    out = []
    for raw in data.split(b'\n'):
        out.append(raw.replace(b'\r', b'').decode('latin-1')[:4095])
    if out and out[-1] == '':
        out.pop()
    return out


def is_sample(s):
    """FS_IsSample: '-' or a digit first."""
    return bool(s) and (s[0] == '-' or '0' <= s[0] <= '9')


def decolor(s):
    """strdecolorize, for the markup a netname carries: ^digit, ^xRGB, ^&FB, ^^."""
    s = re.sub(r'\^x[0-9A-Fa-f]{3}', '', s)
    s = re.sub(r'\^&[0-9A-Fa-f-]{2}', '', s)
    s = re.sub(r'\^[0-9abdhmrs]', '', s)
    return s.replace('^^', '^')


def name_slug(s):
    """FS_NameSlug: lowercased, [a-z0-9] only, FS_WHO_NAMEMAX kept."""
    out = ''
    for ch in decolor(s).lower():
        if len(out) >= FS_WHO_NAMEMAX:
            break
        if 'a' <= ch <= 'z' or '0' <= ch <= '9':
            out += ch
    return out


def leg_dir(track, leg):
    """FS_LegDir."""
    if track <= 0:
        return 'main' if leg <= 0 else 'stage_%g' % leg
    if leg <= 0:
        return 'bonus_%g' % track
    return 'bonus_%g_stage_%g' % (track, leg)


def dir_word(s):
    """Online_DirWord: the map, lowercased, or `unknown` when unsafe as a folder."""
    s = s.lower()
    if not s or len(s) > OR_WORDMAX or s[0] == '.' or '..' in s:
        return 'unknown'
    if re.search(r'[^a-z0-9_.+-]', s):
        return 'unknown'
    return s


def read_header(lines):
    """Header keys until `begin`; returns (dict, index after begin) or (None, 0)."""
    hdr = {}
    for i, l in enumerate(lines[:OR_HEADMAX]):
        tok = l.split()
        if not tok:
            continue
        if tok[0] == 'begin':
            return hdr, i + 1
        if len(tok) < 2:
            continue
        if tok[0] == 'owner':
            hdr['owner'] = l[6:]
        else:
            hdr[tok[0]] = tok[1]
    return None, 0


def rec_meta(path):
    """What Online_RecName reads: header, then the trailer from the last OR_TAIL bytes."""
    with open(path, 'rb') as fh:
        data = fh.read()
    lines = lines_of(data)
    hdr, body = read_header(lines)
    if hdr is None:
        return None
    if len(data) > OR_TAIL:
        # fseek(sz - OR_TAIL) then one fgets dropped: resume after the next \n
        nl = data.find(b'\n', len(data) - OR_TAIL)
        tail = lines_of(data[nl + 1:]) if nl >= 0 else []
    else:
        tail = lines[body:]
    ticks, lastt, dnf = -1.0, 0.0, False
    for l in tail:
        if l == '':
            break               # QC's `if (!l) break` stops on an empty line
        if is_sample(l):
            m = re.match(r'-?[0-9.]+', l)
            lastt = f32(float(m.group(0))) if m else 0.0
        elif l.startswith('end '):
            ticks = f32(float(l.split()[1]))
        elif l.startswith('abandon '):
            dnf = True
    return {'hdr': hdr, 'ticks': ticks, 'lastt': lastt, 'dnf': dnf, 'size': len(data)}


def num(hdr, key, dflt):
    try:
        return f32(float(hdr[key]))
    except (KeyError, ValueError):
        return dflt


def rec_name(path, rep):
    """Online_RecName: data/online/<map>/<legdir>/<MMmSS.mmms>_<slug>[_dnf]_r<id>.rec.

    Returns (name, exact_name): the second computed without float32, so a
    disagreement (a time on a rounding edge) is visible."""
    m = rec_meta(path)
    if m is None:
        return None, None
    h = m['hdr']
    ver = num(h, 'FTESURF-REC', 0)
    if ver < 1:
        return None, None
    track = num(h, 'track', 0)
    sseg = num(h, 'startseg', 0)
    leg = num(h, 'leg', -1)
    if leg < 0:
        leg = sseg + 1 if sseg > 0 else 0          # FS_LegOf(sseg, sseg > 0)
    rkey = 'movetickrate' if num(h, 'movetickrate', 0) > 0 else 'tickrate'
    rate = num(h, rkey, 0)
    if rate <= 0:
        rkey, rate = None, f32(PM_TICK)
    exrate = float(h[rkey]) if rkey else PM_TICK
    ticks, dnf = m['ticks'], m['dnf']
    if ticks < 0:
        ticks = f32(math.floor(f32(m['lastt'] / rate) + 0.5))     # rint, t >= 0
        dnf = True
    slug = name_slug(h.get('owner', '')) or 'anon'
    base = 'data/online/%s/%s/' % (dir_word(h.get('map', '')), leg_dir(track, leg))

    def spell(ms):
        mm = math.floor(ms / 60000)
        ms -= mm * 60000
        ss = math.floor(ms / 1000)
        ms -= ss * 1000
        return '%s%02dm%02d.%03ds_%s%s_r%d.rec' % (base, mm, ss, ms, slug,
                                                   '_dnf' if dnf else '', rep)

    ms32 = math.floor(f32(f32(f32(ticks * rate) * 1000) + 0.5))
    exact = math.floor(float(ticks) * exrate * 1000 + 0.5)
    return spell(ms32), spell(exact)


def cached(d):
    """(id, path) for every cached .rec under d: flat <id>.rec or *_r<id>.rec."""
    out = []
    for root, _dirs, files in os.walk(d):
        for f in files:
            m = FLAT_RE.match(f) if root == d else None
            m = m or LEAF_RE.search(f)
            if m and f.endswith('.rec'):
                out.append((int(m.group(1)), os.path.join(root, f)))
    return sorted(out)


def md5(path):
    with open(path, 'rb') as fh:
        return hashlib.md5(fh.read()).hexdigest()


def windows(path):
    """Watch_Scan's pass one (the tables Watch_StageWindow reads), float32."""
    with open(path, 'rb') as fh:
        lines = lines_of(fh.read())
    hdr, body = read_header(lines)
    if hdr is None:
        return None
    rate = num(hdr, 'tickrate', 0)      # the viewer reads `tickrate` (rec_wt_tickrate)
    if rate <= 0:
        rate = f32(PM_TICK)
    pw0, pw1 = [-1.0] * WT_STGMAX, [-1.0] * WT_STGMAX
    ev, endticks, abandon, wpseg, wpdur = [], 0.0, False, -1, 0.0
    t0 = t1 = None
    for l in lines[body:]:
        if is_sample(l):
            t = f32(float(l.split()[0]))
            t0 = t if t0 is None else t0
            t1 = t
            continue
        tok = l.split()
        if len(tok) < 2:
            continue
        if tok[0] == 'stagepost':
            wpseg = -1
            if len(tok) >= 3:
                wpseg, wpdur = int(float(tok[1])), f32(float(tok[2]))
            continue
        if tok[0] == 'abandon':
            abandon = True
            continue
        if wpseg >= 0:
            wpend = -1.0
            if tok[0] == 'end':
                wpend = f32(float(tok[1]))
            elif tok[0] == 'stage' and len(tok) >= 3:
                wpend = f32(float(tok[2]))
            if wpend >= 0:
                if wpseg < WT_STGMAX:
                    pw0[wpseg], pw1[wpseg] = f32(wpend - wpdur), wpend
                wpseg = -1
        if tok[0] == 'end':
            endticks = f32(float(tok[1]))
            continue
        if len(ev) >= WT_EVMAX:
            continue
        if tok[0] in ('stage', 'cp') and len(tok) >= 3:
            ev.append((tok[0], int(float(tok[1])), f32(float(tok[2]))))
    return {'rate': rate, 'pw0': pw0, 'pw1': pw1, 'ev': ev, 'end': endticks,
            'abandon': abandon, 't0': t0 or 0.0, 't1': t1 or 0.0}


def stage_window(w, seg):
    """Watch_StageWindow(seg): (a, b, how, wint0, wint1, from) or None."""
    if seg < 0 or seg >= WT_STGMAX:
        return None
    a, b, how = w['pw0'][seg], w['pw1'][seg], 'stagepost'
    if a < 0:
        how, a, b = 'stage records', (-1.0 if seg > 0 else 0.0), w['end']
        for kind, s, tick in w['ev']:
            if kind != 'stage':
                continue
            if s == seg:
                a = tick
            if s == seg + 1:
                b = tick
                break
    if a < 0 or b <= a:
        return None
    rate = w['rate']
    wint0 = f32(a * rate)
    wint1 = min(f32(b * rate), w['t1'])
    frm = max(w['t0'], f32(wint0 - 1))
    frm = min(max(frm, w['t0']), w['t1'])      # Watch_Seek's clamp
    return a, b, how, wint0, wint1, frm


def window_line(seg, win):
    if win is None:
        return 'replay: no window for stage %g in this file' % (seg + 1)
    a, b, how, wint0, wint1, frm = win
    return ('replay: stage %g window %.4f..%.4f s from %.4f (ticks %g..%g, %s)'
            % (seg + 1, wint0, wint1, frm, a, b, how))


# The design's pins (Patch 395 design report, section 2i and the pNNNwin arms).
PINNED_NAMES = {
    2: 'surf_lux/main/00m50.400s_player_r2',
    3: 'surf_aesthetic/main/01m01.515s_player_r3',
    4: 'surf_aesthetic/main/01m13.620s_player_r4',
    5: 'surf_utopia/main/01m03.360s_proto_r5',
    6: 'surf_utopia/main/01m02.520s_boro_r6',
    8: 'surf_tensor2/stage_2/00m12.570s_proto_r8',
    10: 'bhop_eazy/main/00m49.845s_1proto_r10',
    16: 'bhop_eazy/main/00m49.030s_kap_r16',
    18: 'surf_aura/main/04m08.325s_kap_r18',
    19: 'surf_aweles/main/02m03.525s_kap_r19',
    34: 'surf_deathstar/main/00m40.005s_boro_r34',
    38: 'surf_ace/main/00m57.990s_borobongo_r38',
    42: 'surf_beginner/main/00m56.940s_proto_r42',
}
PINNED_WINDOWS = [   # (id, 0-based seg, the line)
    (18, 1, 'replay: stage 2 window 7.8750..17.2350 s from 6.8750 (ticks 525..1149, stagepost)'),
    (18, 0, 'replay: stage 1 window 0.0000..6.6300 s from -1.0000 (ticks 0..442, stagepost)'),
    (16, 2, 'replay: stage 3 window 23.7800..36.8600 s from 22.7800 (ticks 2378..3686, stagepost)'),
    (3, 1, 'replay: stage 2 window 8.5350..20.5500 s from 7.5350 (ticks 569..1370, stage records)'),
    (18, 8, 'replay: no window for stage 9 in this file'),
]


def cmd_names(d):
    for rep, p in cached(d):
        n, ex = rec_name(p, rep)
        rel = os.path.relpath(p, os.path.dirname(os.path.dirname(os.path.normpath(d))))
        rel = rel.replace(os.sep, '/')
        flag = '' if n == ex else '   (exact: %s)' % ex
        state = 'in place' if n == rel else 'moves'
        print('%4d  %-12s %s\n      -> %s%s' % (rep, state, rel, n, flag))


def cmd_manifest(d):
    for rep, p in cached(d):
        n, _ = rec_name(p, rep)
        print('%d %s %s' % (rep, md5(p), n))


def cmd_verify(manifest, d):
    ok = True
    want = {}
    with open(manifest) as fh:
        for l in fh:
            tok = l.split()
            if len(tok) == 3:
                want[int(tok[0])] = (tok[1], tok[2])
    flat = [f for f in os.listdir(d) if FLAT_RE.match(f)]
    parts = [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.endswith('.part')]
    have = {}
    for rep, p in cached(d):
        have.setdefault(rep, []).append(p)
    print('flat <id>.rec left: %d %s' % (len(flat), ' '.join(flat)))
    print('.part files: %d %s' % (len(parts), ' '.join(parts)))
    ok = ok and not flat and not parts
    for rep in sorted(want):
        md, exp = want[rep]
        p = os.path.join(d, exp[len('data/online/'):].replace('/', os.sep))
        ps = have.get(rep, [])
        good = os.path.isfile(p) and md5(p) == md and len(ps) == 1
        ok = ok and good
        print('%s r%d %s%s' % ('PASS' if good else 'FAIL', rep, exp,
                               '' if len(ps) == 1 else '  (%d copies)' % len(ps)))
    print('VERIFY %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def cmd_windows(path, segs):
    w = windows(path)
    if w is None:
        print('no header')
        return 1
    print('rate %.9g  t0 %.4f  t1 %.4f  end %g  abandon %d' % (w['rate'], w['t0'], w['t1'],
                                                              w['end'], w['abandon']))
    for seg in (segs or range(WT_STGMAX)):
        win = stage_window(w, seg)
        if win is None and not segs:
            continue
        if win:
            a, b, how, _, _, _ = win
            print('seg %d leg %d a %g b %g a_s %.4f b_s %.4f %s' % (seg, seg + 1, a, b,
                  f32(a * w['rate']), f32(b * w['rate']), how))
        print('  ' + window_line(seg, win))
        if win:
            print('  replay: stage %g window end %.4f -- paused' % (seg + 1, win[4]))
    return 0


def cmd_selftest(d):
    bad = 0
    byid = dict(cached(d))
    for rep, pin in sorted(PINNED_NAMES.items()):
        if rep not in byid:
            print('SKIP r%d not under %s' % (rep, d))
            continue
        n, ex = rec_name(byid[rep], rep)
        good = n == 'data/online/%s.rec' % pin and n == ex
        bad += not good
        print('%s r%d %s%s' % ('PASS' if good else 'FAIL', rep, n,
                               '' if n == ex else ' (exact %s)' % ex))
    for rep, seg, line in PINNED_WINDOWS:
        if rep not in byid:
            print('SKIP window r%d' % rep)
            continue
        got = window_line(seg, stage_window(windows(byid[rep]), seg))
        good = got == line
        bad += not good
        print('%s r%d seg %d: %s' % ('PASS' if good else 'FAIL', rep, seg, got))
    print('SELFTEST %s (%d failed)' % ('PASS' if not bad else 'FAIL', bad))
    return 1 if bad else 0


def cmd_fixture(src, outdir, rep_a, rep_b, rep_c):
    """Three files cut from SRC at its middle sample: <rep_a>.rec with the
    evidence trailer (`abandon T`, `inend`, `end T`, as SV_RecKeepEvidence writes
    it), <rep_b>.rec cut dead with no trailer (a torn file), and <rep_c>.rec with
    the same trailer minus `abandon` (the control: it reads as finished at T)."""
    with open(src, 'rb') as fh:
        lines = fh.read().decode('latin-1').split('\n')
    _hdr, body = read_header(lines)
    samples = [i for i in range(body, len(lines)) if is_sample(lines[i])]
    cut = samples[len(samples) // 2]
    rate = float(_hdr.get('tickrate', PM_TICK))
    t = float(lines[cut].split()[0])
    ticks = int(math.floor(t / rate + 0.5))
    keep = lines[:cut + 1]
    pad = sum(1 for i in samples if i <= cut and lines[i].startswith('-'))
    trailer = ['abandon %d' % ticks, 'inend %d 0' % ticks,
               'end %d %d %d 0 0 0 0 0 0 0' % (ticks, samples.index(cut) + 1, pad)]
    os.makedirs(outdir, exist_ok=True)
    for rep, body_lines in ((rep_a, keep + trailer), (rep_b, keep), (rep_c, keep + trailer[1:])):
        with open(os.path.join(outdir, '%d.rec' % rep), 'wb') as fh:
            fh.write(('\n'.join(body_lines) + '\n').encode('latin-1'))
    print('cut at line %d, t %.4f, ticks %d -> %d.rec (abandon), %d.rec (no trailer), '
          '%d.rec (no abandon)' % (cut + 1, t, ticks, rep_a, rep_b, rep_c))
    return 0


# p395stub's boards: (map, leg) -> rows.  `run` without `rep` is a stage row set
# inside a main run (surfd schema 6); ids resolve to DIR/<id>.rec.
STUB_BOARDS = {
    ('surf_aura', 2): [(1, 'Kap', 624, 0, 18), (2, 'Nobody', 700, 0, 0)],
    ('surf_aura', 3): [(1, 'Proto', 804, 0, 990044)],
    ('surf_beginner', 5): [(1, 'Proto', 259, 0, 990042)],
    # p433line: stage 4 of a run the cache does not hold (a copy of 18).
    ('surf_aura', 4): [(1, 'Kap', 800, 0, 990018)],
}


def cmd_serve(port, d):
    """A stub surfd on 127.0.0.1:PORT: /api/board from STUB_BOARDS, /api/replay/<id>
    from D/<id>.rec.  One line per request on stdout."""
    import http.server
    import json
    import time
    from urllib.parse import urlparse, parse_qs

    class H(http.server.BaseHTTPRequestHandler):
        def reply(self, code, body, ctype):
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            print('%s %d %d bytes' % (self.path, code, len(body)), flush=True)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == '/api/board':
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                mp, leg = q.get('map', '').lower(), int(float(q.get('leg', 0)))
                rows = [{'r': r, 'name': n, 'player': n.lower(), 'ticks': t,
                         'ms': round(t * 15), 'rate': 66.6667, 'flags': 0,
                         'when': int(time.time()) - 600, 'rep': rep, 'run': run,
                         'ver': 0} for r, n, t, rep, run in STUB_BOARDS.get((mp, leg), [])]
                body = {'map': mp, 'track': int(float(q.get('track', 0))), 'leg': leg,
                        'tier': q.get('tier', 'ranked'), 'style': q.get('style', 'clean'),
                        't': int(time.time()),
                        'counts': {'ranked': len(rows), 'community': 0}, 'rows': rows}
                return self.reply(200, json.dumps(body).encode(), 'application/json')
            m = re.match(r'^/api/replay/([0-9]+)$', u.path)
            p = os.path.join(d, '%s.rec' % m.group(1)) if m else ''
            if p and os.path.isfile(p):
                with open(p, 'rb') as fh:
                    return self.reply(200, fh.read(), 'text/plain')
            return self.reply(404, b'{"error":"not found"}', 'application/json')

        def log_message(self, *a):
            pass

    print('serving %s on 127.0.0.1:%d' % (d, port), flush=True)
    http.server.ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()


def main(argv):
    if len(argv) >= 4 and argv[1] == 'serve':
        return cmd_serve(int(argv[2]), argv[3])
    if len(argv) >= 7 and argv[1] == 'fixture':
        return cmd_fixture(argv[2], argv[3], int(argv[4]), int(argv[5]), int(argv[6]))
    if len(argv) >= 3 and argv[1] == 'names':
        cmd_names(argv[2])
        return 0
    if len(argv) >= 3 and argv[1] == 'manifest':
        cmd_manifest(argv[2])
        return 0
    if len(argv) >= 4 and argv[1] == 'verify':
        return cmd_verify(argv[2], argv[3])
    if len(argv) >= 3 and argv[1] == 'windows':
        return cmd_windows(argv[2], [int(x) for x in argv[3:]])
    if len(argv) >= 3 and argv[1] == 'selftest':
        return cmd_selftest(argv[2])
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
