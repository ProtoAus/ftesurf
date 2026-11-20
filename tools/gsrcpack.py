#!/usr/bin/env python3
"""gsrcpack.py -- one package per GoldSrc (BSP 30) map, for <gamedir>/downloads/goldsrc/.

    python3 -I tools/gsrcpack.py plan  <ag_downloads> <out> --stock <Half-Life dir>
    python3 -I tools/gsrcpack.py build <ag_downloads> <out> --stock <Half-Life dir> [--only name,...] [--jobs N]

`plan` reads every maps/*.bsp and writes <out>/plan.json; nothing else. `build` also writes, per kept map,
<out>/pk3/<id>.pk3 (a STORED zip, fixed timestamps: the same input gives the same bytes) and
<out>/xz/<id>.pk3.xz, then <out>/catalog.txt. tools/r2mirror.py (group goldsrc) publishes xz/ as
objects/goldsrc/<sha256 of the .xz>.xz, which is the address the game builds from the row.

A map's id is its lower-case name + "_gs": Momentum publishes Source ports under the original names
(agtricks, kz_cellblock ...), and zones, saves and boards are keyed by map name.

What goes in a package: maps/<id>.bsp, and every model, sprite, sound and sky face the BSP's entities name
that the archive has and Half-Life does not. Custom WADs are cut down to the textures that map takes from
them and keep their own name, so the BSP is shipped unmodified. Valve's files (valve/, cstrike/, czero/)
are never packed: the game mounts them from Steam, and the row's `needs` says which.

Every map whose BSP parses and whose name is usable ships (P1669; until then only complete bhop/kz maps did).
What it names and nobody has is left out of the package and flagged, so the menu can warn; only an unreadable
BSP or an unusable name gets a `gx` row with the reason.

catalog.txt:
    FTESURF-GOLDSRC 1
    # stamp YYYYMMDDhhmmss
    gs <id> <kind> <xz bytes> <pk3 bytes> <pk3 sha256> <needs> <flags> <xz sha256>
    gx <id> <kind> <reason> <count>
    # end <rows>
kind: bhop | kz | other.  needs: 1 Half-Life, 2 Counter-Strike, 4 Condition Zero (sum).
flags: 1 KZ timer buttons, 2 ladders, 4 water; P1669 missing: 8 sky, 16 textures in no WAD, 32 models, 64 sounds (sum).
reason (gx only): bsp (unreadable) | name (unusable id).
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
import zipfile

SUFFIX = '_gs'
GAMES = (('valve', 1), ('cstrike', 2), ('czero', 4))   # mount order; bit in `needs`
NAME_OK = re.compile(r'^[a-z0-9_-]{1,60}$')
FILE_OK = re.compile(r'^[a-z0-9_!.+{}()\[\]~#@$%^&=, /-]+$')
REF_EXT = ('.mdl', '.spr', '.wav', '.mp3', '.ogg', '.tga', '.bmp')
SND_EXT = ('.wav', '.mp3', '.ogg')
ENT_KV = re.compile(rb'"([^"\n]*)"\s+"([^"\n]*)"')
SKY_SIDES = ('rt', 'bk', 'lf', 'ft', 'up', 'dn')
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def index_tree(root):
    """lower-case relative path -> (absolute path, size)."""
    idx = {}
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, root).replace(os.sep, '/').lower()
            try:
                idx[rel] = (full, os.path.getsize(full))
            except OSError:
                pass
    return idx


def archive_index(root):
    idx = index_tree(root)
    # The archive files its sound/ tree under sprites/sound/.
    for rel in [r for r in idx if r.startswith('sprites/sound/')]:
        idx.setdefault(rel[len('sprites/'):], idx[rel])
    return idx


def stock_index(dirs):
    """lower-case relative path -> bit of the first game (GAMES order) that has it."""
    out = {}
    for d in dirs:
        for game, bit in GAMES:
            p = os.path.join(d, game)
            if os.path.isdir(p):
                for rel in index_tree(p):
                    out.setdefault(rel, bit)
    return out


def wad_dir(path):
    """[(name, filepos, disksize, entry bytes)] for a WAD3/WAD2, or None."""
    try:
        with open(path, 'rb') as f:
            head = f.read(12)
            if len(head) < 12 or head[:4] not in (b'WAD3', b'WAD2'):
                return None
            n, off = struct.unpack('<ii', head[4:12])
            if n < 0 or n > 200000:
                return None
            f.seek(off)
            raw = f.read(32 * n)
    except OSError:
        return None
    out = []
    for i in range(len(raw) // 32):
        e = raw[i * 32:(i + 1) * 32]
        pos, disksize = struct.unpack('<ii', e[:8])
        name = e[16:32].split(b'\0', 1)[0].decode('latin-1').lower()
        out.append((name, pos, disksize, e))
    return out


def cut_wad(path, names):
    """A WAD3 holding only `names` (lower case) from the WAD at path, lumps copied as stored."""
    want = set(names)
    keep = []
    with open(path, 'rb') as f:
        for name, pos, disksize, e in wad_dir(path):
            if name in want:
                want.discard(name)   # first lump of a name wins, as the engine's lookup does
                f.seek(pos)
                keep.append((e, f.read(disksize)))
    body = b''
    table = b''
    off = 12
    for e, data in keep:
        table += struct.pack('<i', off) + e[4:]
        body += data
        off += len(data)
    return b'WAD3' + struct.pack('<ii', len(keep), 12 + len(body)) + body + table


def clean_ref(v):
    """A file reference as GoldSrc would open it: lower case, forward slashes, no ./ or //.
    Returns (path, game) where game is 'valve'/'cstrike'/'czero' for a ../<game>/ reference."""
    v = v.strip().lower().replace('\\', '/')
    parts = [p for p in v.split('/') if p not in ('', '.')]
    game = None
    while '..' in parts:
        i = parts.index('..')
        nxt = parts[i + 1] if i + 1 < len(parts) else ''
        if nxt in ('valve', 'cstrike', 'czero'):
            game = nxt
            parts = parts[i + 2:]
        else:
            del parts[max(i - 1, 0):i + 1]
    return '/'.join(parts), game


def parse_bsp(path):
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < 124 or struct.unpack('<i', data[:4])[0] != 30:
        return None
    lumps = [struct.unpack('<ii', data[4 + i * 8:12 + i * 8]) for i in range(15)]
    eoff, elen = lumps[0]
    toff, tlen = lumps[2]
    ext = []
    if tlen >= 4:
        n = struct.unpack('<i', data[toff:toff + 4])[0]
        if 0 <= n <= 65536 and 4 + 4 * n <= tlen:
            for o in struct.unpack('<%di' % n, data[toff + 4:toff + 4 + 4 * n]):
                m = data[toff + o:toff + o + 40] if o >= 0 else b''
                if len(m) == 40 and struct.unpack('<I', m[24:28])[0] == 0:
                    ext.append(m[:16].split(b'\0', 1)[0].decode('latin-1').lower())
    info = {'bytes': len(data), 'tex_external': sorted(set(ext)), 'wads': [], 'sky': '', 'refs': [],
            'flags': 0, 'classes': {}}
    refs = set()
    first = True
    ents = data[eoff:eoff + elen]
    low = ents.lower()
    if b'"counter_start"' in low and b'"counter_off"' in low:
        info['flags'] |= 1
    for block in re.findall(rb'\{[^{}]*\}', ents):
        kv = {}
        for k, v in ENT_KV.findall(block):
            kv[k.decode('latin-1').lower()] = v.decode('latin-1')
        cn = kv.get('classname', '').lower()
        info['classes'][cn] = info['classes'].get(cn, 0) + 1
        if first or cn == 'worldspawn':
            first = False
            if 'wad' in kv:
                info['wads'] = [os.path.basename(w.replace('\\', '/')).lower() for w in kv['wad'].split(';') if w.strip()]
            info['sky'] = kv.get('skyname', info['sky']).strip().lower()
        for k, v in kv.items():
            vl = v.strip().lower()
            if k == 'wad' or not vl.endswith(REF_EXT) or vl.startswith('!'):
                continue
            ref, game = clean_ref(vl.lstrip('*'))
            if ref.endswith(SND_EXT) and not ref.startswith(('sound/', 'media/')):
                ref = 'sound/' + ref
            if ref:
                refs.add((ref, game))
    if 'func_ladder' in info['classes']:
        info['flags'] |= 2
    if 'func_water' in info['classes']:
        info['flags'] |= 4
    info['refs'] = sorted(refs, key=lambda r: r[0])
    return info


def kind_of(name, flags=0):
    """bhop | kz | other. A community jump map carries the KZ timer buttons whatever it is called."""
    n = name.lower()
    head = re.split(r'[_\-0-9]', n)[0]
    if 'kz' in head:
        return 'kz'
    if 'bhop' in n or 'bunnyhop' in n or re.search(r'hops?(_|\d|$)', n):
        return 'bhop'
    if 'kz' in n or (flags & 1):
        return 'kz'
    return 'other'


def plan_map(name, bsp_path, arch, stock, wadcache):
    info = parse_bsp(bsp_path)
    row = {'name': name, 'id': name.lower() + SUFFIX, 'kind': kind_of(name), 'bsp': bsp_path}
    if info is None:
        row.update(reason='bsp', count=1)
        return row
    row['flags'] = info['flags']
    row['kind'] = kind_of(name, info['flags'])
    needs = 0
    files = {}        # path in the package -> absolute source path
    cut = {}          # wad name -> [texture names]
    missing = {'tex': [], 'model': [], 'sound': [], 'sky': []}

    def wad(w):
        if w not in wadcache:
            if w in stock:
                wadcache[w] = ('stock', stock[w], None)
            elif w in arch:
                d = wad_dir(arch[w][0])
                wadcache[w] = ('arch', arch[w][0], {n for n, _p, _s, _e in d} if d else set())
            else:
                wadcache[w] = (None, None, None)
        return wadcache[w]

    need_tex = list(info['tex_external'])
    stock_wads = []
    for w in info['wads']:
        where, src, names = wad(w)
        if where == 'stock':
            stock_wads.append((w, src))
        elif where == 'arch' and need_tex:
            hit = [t for t in need_tex if t in names]
            if hit:
                cut[w] = hit
                need_tex = [t for t in need_tex if t not in names]
    if need_tex:
        # Whatever the custom WADs do not hold must come from a listed Valve WAD; which one is checked
        # against the stock files when they are installed here.
        left = list(need_tex)
        for w, bit in stock_wads:
            d = wadcache.setdefault('#' + w, None)
            if d is None:
                d = wadcache['#' + w] = stock_wad_names(w)
            hit = [t for t in left if t in d]
            if hit:
                needs |= bit
                left = [t for t in left if t not in d]
        missing['tex'] = left

    def want(ref, game, kind):
        nonlocal needs
        if not FILE_OK.match(ref):
            missing[kind].append(ref)
            return
        if ref in stock:
            needs |= stock[ref]
        elif game is not None:
            missing[kind].append(ref)     # named ../<game>/x, and that game does not have it
        elif ref in arch:
            files[ref] = arch[ref][0]
            if ref.endswith('.mdl'):      # a GoldSrc model's texture and sequence-group files
                base = ref[:-4]
                for extra in [base + 't.mdl'] + [base + '%02d.mdl' % i for i in range(1, 33)]:
                    if extra in arch and extra not in stock:
                        files[extra] = arch[extra][0]
        else:
            missing[kind].append(ref)

    for ref, game in info['refs']:
        if ref.endswith(SND_EXT):
            want(ref, game, 'sound')
        elif ref.startswith('gfx/env/'):
            want(ref, game, 'sky')
        else:
            want(ref, game, 'model')
    if info['sky']:
        for side in SKY_SIDES:
            tga = 'gfx/env/%s%s.tga' % (info['sky'], side)
            bmp = tga[:-4] + '.bmp'
            pick = next((p for p in (tga, bmp) if p in stock or p in arch), None)
            if pick is None:
                missing['sky'].append(tga)
            else:
                want(pick, None, 'sky')
    row['needs'] = needs
    row['files'] = files
    row['cut'] = cut
    row['missing'] = {k: v for k, v in missing.items() if v}
    for k, bit in (('sky', 8), ('tex', 16), ('model', 32), ('sound', 64)):   # P1669: ships, flagged
        if missing[k]:
            row['flags'] |= bit
    return row


STOCK_DIRS = []


def stock_wad_names(w):
    for d in STOCK_DIRS:
        for game, _bit in GAMES:
            p = os.path.join(d, game)
            if os.path.isdir(p):
                for f in os.listdir(p):
                    if f.lower() == w:
                        dd = wad_dir(os.path.join(p, f))
                        return {n for n, _p, _s, _e in dd} if dd else set()
    return set()


def make_plan(tree, stock_dirs):
    arch = archive_index(tree)
    stock = stock_index(stock_dirs)
    wadcache = {}
    rows = []
    for rel in sorted(arch):
        if not (rel.startswith('maps/') and rel.endswith('.bsp') and rel.count('/') == 1):
            continue
        name = os.path.basename(arch[rel][0])[:-4]
        if not NAME_OK.match(name.lower() + SUFFIX):
            rows.append({'name': name, 'id': name.lower() + SUFFIX, 'kind': kind_of(name), 'reason': 'name', 'count': 1})
            continue
        rows.append(plan_map(name, arch[rel][0], arch, stock, wadcache))
    return rows, arch


def build_pk3(row, arch, out):
    members = {'maps/%s.bsp' % row['id']: ('file', row['bsp'])}
    for ref, src in row['files'].items():
        members[ref] = ('file', src)
    for w, names in row['cut'].items():
        members[w] = ('bytes', cut_wad(arch[w][0], names))
    path = os.path.join(out, 'pk3', row['id'] + '.pk3')
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_STORED) as z:
        for name in sorted(members):
            kind, v = members[name]
            if kind == 'file':
                with open(v, 'rb') as f:
                    v = f.read()
            zi = zipfile.ZipInfo(name, ZIP_TIME)
            zi.external_attr = 0o644 << 16
            zi.compress_type = zipfile.ZIP_STORED
            z.writestr(zi, v)
    os.replace(tmp, path)
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    size = os.path.getsize(path)
    sha = h.hexdigest()
    xz = os.path.join(out, 'xz', row['id'] + '.pk3.xz')
    note = xz + '.of'      # the pk3 sha this .xz was made from, so a rebuild recompresses only what changed
    made = ''
    if os.path.exists(xz) and os.path.exists(note):
        with open(note) as f:
            made = f.read().strip()
    if made != sha:
        # The engine's decoder allocates the dictionary the stream declares (limit 128 MiB) and checks
        # CRC32 only; a dictionary just over the file is as small as it gets for the same output.
        d = 1 << 20
        while d < size and d < (64 << 20):
            d <<= 1
        with open(xz + '.tmp', 'wb') as o:
            subprocess.run(['xz', '-c', '-T1', '--check=crc32', '--lzma2=preset=9e,dict=%d' % d, path],
                           stdout=o, check=True)
        os.replace(xz + '.tmp', xz)
        with open(note, 'w') as f:
            f.write(sha + '\n')
    h = hashlib.sha256()
    with open(xz, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return row['id'], sha, size, os.path.getsize(xz), h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('plan', 'build'))
    ap.add_argument('tree')
    ap.add_argument('out')
    ap.add_argument('--stock', action='append', default=[])
    ap.add_argument('--only', default='')
    ap.add_argument('--jobs', type=int, default=6)
    a = ap.parse_args()
    STOCK_DIRS.extend(a.stock)
    os.makedirs(a.out, exist_ok=True)
    rows, arch = make_plan(a.tree, a.stock)
    with open(os.path.join(a.out, 'plan.json'), 'w') as f:
        json.dump(rows, f, indent=1, sort_keys=True)
    keep = [r for r in rows if 'reason' not in r]
    drop = [r for r in rows if 'reason' in r]
    print('maps %d  keep %d  drop %d' % (len(rows), len(keep), len(drop)))
    by = {}
    for r in drop:
        by[(r['kind'], r['reason'])] = by.get((r['kind'], r['reason']), 0) + 1
    for k in sorted(by):
        print('  drop %-5s %-6s %d' % (k[0], k[1], by[k]))
    print('  missing', {k: sum(1 for r in keep if r['flags'] & bit) for k, bit in (('sky', 8), ('tex', 16), ('model', 32), ('sound', 64))})
    print('  keep by kind', {k: sum(1 for r in keep if r['kind'] == k) for k in ('bhop', 'kz', 'other')},
          'needs', {n: sum(1 for r in keep if r['needs'] == n) for n in sorted({r['needs'] for r in keep})})
    if a.cmd == 'plan':
        return 0
    only = {x.strip().lower() for x in a.only.split(',') if x.strip()}
    if only:
        keep = [r for r in keep if r['name'].lower() in only or r['id'] in only]
    os.makedirs(os.path.join(a.out, 'pk3'), exist_ok=True)
    os.makedirs(os.path.join(a.out, 'xz'), exist_ok=True)
    built = {}
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        for i, (mid, sha, size, xzsize, xzsha) in enumerate(ex.map(lambda r: build_pk3(r, arch, a.out), keep)):
            built[mid] = (sha, size, xzsize, xzsha)
            if i % 100 == 0:
                print('..', i, len(keep), file=sys.stderr)
    lines = ['FTESURF-GOLDSRC 1', '# stamp ' + time.strftime('%Y%m%d%H%M%S', time.gmtime())]
    n = 0
    for r in sorted(rows, key=lambda r: r['id']):
        if r['id'] in built:
            sha, size, xzsize, xzsha = built[r['id']]
            lines.append('gs %s %s %d %d %s %d %d %s' % (r['id'], r['kind'], xzsize, size, sha, r['needs'], r['flags'], xzsha))
            n += 1
        elif 'reason' in r and not only:
            lines.append('gx %s %s %s %d' % (r['id'], r['kind'], r['reason'], r['count']))
            n += 1
    lines.append('# end %d' % n)
    with open(os.path.join(a.out, 'catalog.txt'), 'w', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print('built %d  pk3 %.2f GB  xz %.2f GB' % (len(built), sum(v[1] for v in built.values()) / 1e9,
                                                  sum(v[2] for v in built.values()) / 1e9))
    return 0


if __name__ == '__main__':
    sys.exit(main())
