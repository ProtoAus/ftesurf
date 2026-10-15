#!/usr/bin/env python3
"""Audit/fetch surf+bhop XL originals and regenerate bounded menu backdrops.

Local Momentum MSML caches (including public testing) are unioned with the LIVE
approved API catalogue. Testing API requires a Momentum login: cached testing
rows are explicitly labelled as cached, never reported as a current live census.
Only public thumbnail IDs/metadata are saved. No credentials are read or exported.
Use --offline for reproducible regeneration. Publishing is a separate operation;
never rclone sync/delete. See mapmedia.md.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import time
import urllib.request
from PIL import Image, ImageOps, ImageFilter
import mapmeta

API = 'https://api.momentum-mod.org/v1/maps'
CDN = 'https://cdn.momentum-mod.org/img/'
UUID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
NAME = re.compile(r'[a-z0-9_-]{1,64}', re.I)
MAX_ORIGINAL = 16 * 1024 * 1024
UA = 'FTESurf-mapmedia/1 (public map thumbnail preservation)'


def fetch(url, limit):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        b = r.read(limit + 1)
    if len(b) > limit:
        raise ValueError('response exceeds bound')
    return b


def live_maps():
    """Fail closed on short pages, changed totals or repeated IDs."""
    rows = []
    for mode in (1, 2):
        skip, total, seen = 0, None, set()
        while total is None or skip < total:
            data = json.loads(fetch(API + '?gamemode=%d&take=100&skip=%d&expand=thumbnail,images' %
                                    (mode, skip), 8 * 1024 * 1024))
            n = data.get('totalCount')
            page = data.get('data')
            if not isinstance(n, int) or n < 1 or n > 20000 or not isinstance(page, list):
                raise ValueError('invalid approved catalogue')
            if total is not None and total != n:
                raise ValueError('catalogue changed during pagination; retry')
            total = n
            if not page or len(page) > 100 or skip + len(page) > total:
                raise ValueError('incomplete approved catalogue')
            for row in page:
                ident = row.get('id')
                if not isinstance(ident, int) or ident in seen:
                    raise ValueError('duplicate approved catalogue row')
                seen.add(ident)
                rows.append(row)
            skip += len(page)
            time.sleep(0.35)
    return rows


def catalogue(momentum, online, prior=()):
    rows = {}
    for old in prior:
        if NAME.fullmatch(str(old.get('name', ''))):
            rows[old['name']] = (dict(id=old.get('id'), name=old['name'], status=old.get('status'),
                thumbnail=dict(id=old.get('uuid')), images=[dict(id=u) for u in old.get('alternatives', [])]), 'retained-catalogue')
    for path in sorted((Path(momentum) / '_cache').glob('*.dat')):
        for m in mapmeta.read_msml(str(path)):
            name = m.get('name', '')
            native = mapmeta.pick_gamemode(m, m.get('leaderboards') or [], name)
            if NAME.fullmatch(name) and (name.lower().startswith(('surf_', 'bhop_')) or native in (1,2)):
                rows[name.lower()] = (m, 'momentum-cache')
    for m in online:
        if NAME.fullmatch(m.get('name', '')):
            rows[m['name'].lower()] = (m, 'live-approved')
    if not rows:
        raise ValueError('no surf/bhop catalogue; refusing empty success')
    result = []
    for name, (m, source) in sorted(rows.items()):
        thumb = m.get('thumbnail') or {}
        uuid = str(thumb.get('id') or '').lower()
        if not UUID.fullmatch(uuid):
            uuid = next((str(t.get('id', '')).lower() for t in (m.get('images') or [])
                         if UUID.fullmatch(str(t.get('id', '')).lower())), '')
        result.append(dict(name=name, id=m.get('id'), status=m.get('status'),
                           source=source, uuid=uuid if UUID.fullmatch(uuid) else None,
                           alternatives=[t['id'].lower() for t in (m.get('images') or [])
                                         if UUID.fullmatch(str(t.get('id', '')).lower()) and t['id'].lower() != uuid]))
    return result


def jpeg(body):
    with Image.open(io.BytesIO(body)) as im:
        if im.format != 'JPEG' or im.width < 16 or im.height < 16 or max(im.size) > 16384:
            raise ValueError('not a bounded JPEG')
        im.load()
        return im.convert('RGB')


def backdrop(body, width, maxbytes):
    im = ImageOps.fit(jpeg(body), (width, round(width * 9 / 16)), method=Image.Resampling.LANCZOS)
    # Stay within the engine's default r_image_downloadsizelimit. The original
    # remains lossless-as-downloaded and can generate larger derivatives later.
    for radius in (0, 0.5, 1, 2, 4):
        candidate = im.filter(ImageFilter.GaussianBlur(radius)) if radius else im
        for quality in range(90, 24, -5):
            b = io.BytesIO()
            candidate.save(b, format='JPEG', quality=quality, optimize=True, progressive=True)
            if len(b.getvalue()) < maxbytes:
                return b.getvalue()
    raise ValueError('image cannot meet requested byte bound')


def atomic(path, body):
    part = path.with_suffix(path.suffix + '.part')
    part.write_bytes(body)
    part.replace(path)


def process(uuid, output, seed, width, maxbytes, download, alternatives=()):
    original = output / (uuid + '-xl.jpg')
    try:
        if original.exists():
            body = original.read_bytes()
            jpeg(body)
        elif seed and (seed / original.name).is_file():
            body = (seed / original.name).read_bytes()
            jpeg(body)
            atomic(original, body)
        elif download:
            body = fetch(CDN + original.name, MAX_ORIGINAL)
            jpeg(body)
            atomic(original, body)
        else:
            return dict(uuid=uuid, state='missing-xl')
        target = output / (uuid + '-bg.jpg')
        b = target.read_bytes() if target.exists() else b''
        if not b or len(b) >= maxbytes or jpeg(b).size != (width, round(width * 9 / 16)):
            b = backdrop(body, width, maxbytes)
            atomic(target, b)
        return dict(uuid=uuid, state='ok', original_bytes=len(body),
                    original_sha256=hashlib.sha256(body).hexdigest(),
                    backdrop_bytes=len(b), backdrop_sha256=hashlib.sha256(b).hexdigest())
    except Exception as exc:
        # A map can retain a deleted thumbnail but still have other XL images.
        # Preserve the real CDN identity; only derivatives get compatibility aliases.
        for other in alternatives:
            result = process(other, output, seed, width, maxbytes, download)
            if result['state'] == 'ok':
                result.update(requested_uuid=uuid, primary_error=type(exc).__name__)
                return result
        # Safe diagnostics: never emit arbitrary transport URLs or credentials.
        return dict(uuid=uuid, state='failed', error=type(exc).__name__)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--momentum', type=Path, default=Path(mapmeta.MOMENTUM))
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--seed', type=Path)
    ap.add_argument('--catalogue', type=Path, help='saved catalogue for offline regeneration')
    ap.add_argument('--offline', action='store_true', help='use saved catalogue, no API')
    ap.add_argument('--fetch', action='store_true', help='fetch missing XL originals')
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--max-bytes', type=int, default=131072)
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    if not 256 <= a.width <= 8192 or not 8192 <= a.max_bytes <= 16 * 1024 * 1024 or not 1 <= a.workers <= 8:
        ap.error('width, byte bound or concurrency outside safe range')
    a.output.mkdir(parents=True, exist_ok=True)
    catfile = a.output / 'catalogue.json'
    if a.offline:
        rows = json.loads((a.catalogue or catfile).read_text())['maps']
    else:
        prior = json.loads(catfile.read_text())['maps'] if catfile.exists() else []
        rows = catalogue(a.momentum, live_maps(), prior)
        atomic(catfile, (json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
            testing_coverage='cached only; authenticated upstream census unavailable', maps=rows), indent=2) + '\n').encode())
    if not isinstance(rows, list) or not rows:
        raise ValueError('empty/invalid saved catalogue')
    for row in rows:
        if not isinstance(row, dict) or not NAME.fullmatch(str(row.get('name', ''))):
            raise ValueError('invalid saved map name')
        if row.get('uuid') is not None and not UUID.fullmatch(str(row['uuid'])):
            raise ValueError('invalid saved thumbnail ID')
        if any(not UUID.fullmatch(str(u)) for u in row.get('alternatives', [])):
            raise ValueError('invalid saved image alternative')
    ids = sorted({m['uuid'] for m in rows if m['uuid']})
    alternatives = {m['uuid']: m.get('alternatives', []) for m in rows if m['uuid']}
    images = []
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for i, result in enumerate(pool.map(lambda u: process(u, a.output, a.seed, a.width, a.max_bytes, a.fetch, alternatives[u]), ids), 1):
            images.append(result)
            if i % 25 == 0 or i == len(ids):
                print('%d/%d images; %d not ok' % (i, len(ids), sum(x['state'] != 'ok' for x in images)), flush=True)
    # Name aliases let newly discovered maps work before the next bundled
    # mapmeta/atlas rebuild. UUID originals remain available independently.
    good = {x.get('requested_uuid', x['uuid']): x['uuid'] for x in images if x['state'] == 'ok'}
    for requested, resolved in good.items():
        b = (a.output / (resolved + '-bg.jpg')).read_bytes()
        if requested != resolved:
            atomic(a.output / (requested + '-bg.jpg'), b)
        # The atlas builder still consumes medium images. Derive them from XL,
        # including a recorded fallback when Momentum deleted the chosen thumbnail.
        atomic(a.output / (requested + '-medium.jpg'), backdrop(
            (a.output / (resolved + '-xl.jpg')).read_bytes(), 256, 131072))
    for row in rows:
        if row['uuid'] in good and NAME.fullmatch(row['name']):
            atomic(a.output / (row['name'] + '.jpg'), (a.output / (row['uuid'] + '-bg.jpg')).read_bytes())
    report = dict(maps=len(rows), no_thumbnail=[m['name'] for m in rows if not m['uuid']],
                  unique_images=len(ids), width=a.width, max_bytes=a.max_bytes, images=images)
    atomic(a.output / 'coverage.json', (json.dumps(report, indent=2) + '\n').encode())
    print('maps=%d; no upstream thumbnail=%d; images=%d; failed/missing=%d' %
          (len(rows), len(report['no_thumbnail']), len(ids), sum(x['state'] != 'ok' for x in images)))
    return int(any(x['state'] != 'ok' for x in images))


if __name__ == '__main__':
    raise SystemExit(main())
