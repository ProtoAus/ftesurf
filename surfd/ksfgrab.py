"""Sparse KSF demo discovery: consume the existing paced crawler's file fields.

Original bytes and row provenance are retained, normalized text gets kind=ksf,
and ONLY an exact current KSF PB is linked. Never probe a filename or submit a
native result. Called under ksfimport's shared lock in unattended --watch --go.
No network from HTTP handlers. A tick scans <=32 board files and downloads <=2
advertised CSS/66t files, sequentially, after the board crawler's last request.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

import ksfimport as K
import surfd as S

# Pi installs surfd beside its codec tools; checkout layout keeps tools at root.
TOOLS = Path(__file__).resolve().parent / 'tools'
if not (TOOLS / 'ksfconvert.py').is_file():
    TOOLS = Path(__file__).resolve().parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))
import ksfconvert as C

FILE = re.compile(r'replay_css_[0-9]+_([0-3])_([0-9]+)_([0-9]+)\.rec\Z')
BOARD = re.compile(r'([a-z0-9_]{1,64})/z([0-9]+)(?:m([1-3]))?\.json\Z')
MAX_BYTES = 16 << 20
MAX_QUEUE = 256
SCAN = 32
STYLES = {0: 'FW', 1: 'SW', 2: 'HSW', 3: 'BW'}


def candidate(mp, zone, mode, raw):
    if not isinstance(raw, dict) or S.clean_map(mp) != mp or mode not in STYLES:
        return None
    if zone != 0 and not 31 <= zone <= 99:  # no fabricated stage cut
        return None
    file = raw.get('file')
    m = FILE.fullmatch(file) if isinstance(file, str) else None
    r = K.rec_row(mp, zone, mode, raw)
    if not m or not r or not r['runid']:
        return None
    if (int(m[1]) != mode or int(m[2]) != raw.get('playerID')
            or int(m[3]) != r['when']):
        return None
    return dict(r, file=file, seconds=raw['time'], bonus=r['track'],
                mode=mode, record_id=raw['record_id'])


def valid_job(job):
    try:
        return (isinstance(job, dict) and re.fullmatch(r'[a-z0-9_]{1,64}', job['map'])
                and type(job['track']) is int and 0 <= job['track'] <= 69
                and job['bonus'] == job['track'] and job['leg'] == 0
                and job['mode'] in STYLES and job['style'] == K.KSF_MODES[job['mode']]
                and isinstance(job['file'], str) and FILE.fullmatch(job['file'])
                and re.fullmatch(r'[0-9]{17}', job['player'])
                and job['millis'] == round(job['seconds'] * 1000)
                and job['runid'] == K.record_key(dict(record_id=job['record_id'],
                       date=job['when'], time=job['seconds'], file=job['file'])))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def current(conn, job):
    if not valid_job(job):
        return False
    row = conn.execute(
        'SELECT runid, millis, submitted FROM runs WHERE map=? AND track=? AND leg=0'
        ' AND style=? AND player=? AND tier=?',
        (job['map'], job['track'], job['style'], job['player'], S.TIER_KSF)).fetchone()
    return bool(row and row['runid'] == job['runid'] and row['millis'] == job['millis']
                and row['submitted'] == job['when'])


def ready(conn, job):
    """Exactly linked AND readable; warm files must not occupy pending slots."""
    if not valid_job(job):
        return False
    row = conn.execute(
        'SELECT p.* FROM runs r JOIN replays p ON p.id=r.replay_id'
        ' WHERE r.tier=? AND r.map=? AND r.track=? AND r.leg=0 AND r.style=?'
        ' AND r.player=? AND r.runid=? AND r.millis=? AND r.submitted=?',
        (S.TIER_KSF, job['map'], job['track'], job['style'], job['player'],
         job['runid'], job['millis'], job['when'])).fetchone()
    if not row or row['kind'] != 'ksf':
        return False
    path, _ = S.replay_file(row)
    if not path:
        return False
    try:
        with open(path, 'rb') as f:
            return (os.fstat(f.fileno()).st_size == row['bytes']
                    and f.read(16).startswith(b'FTESURF-REC '))
    except OSError:
        return False


def discover(cache, state, conn):
    """Fair bounded rotation over cached boards; state lives under crawler lock."""
    folder = Path(cache) / 'boards'
    names = sorted(p.relative_to(folder).as_posix() for p in folder.glob('*/*.json'))
    after = state.get('cursor', '')
    names = [n for n in names if n > after] + [n for n in names if n <= after]
    jobs = state.setdefault('jobs', {})
    for name in names[:SCAN]:
        state['cursor'] = name
        m = BOARD.fullmatch(name)
        p = folder / name
        if not m or p.is_symlink() or p.parent.is_symlink() or p.stat().st_size > 8 << 20:
            continue
        mp, zone, mode = m[1], int(m[2]), int(m[3] or 0)
        doc = K.board_load(cache, mp, zone, mode)
        for raw in doc['rows']:
            j = candidate(mp, zone, mode, raw)
            if not j:
                continue
            # Backfill pre-P704 identity only from the same official timestamp
            # and millis. Never let an old cached PB replace a newer one.
            conn.execute('UPDATE runs SET runid=? WHERE tier=? AND map=? AND track=?'
                         ' AND leg=0 AND style=? AND player=? AND millis=?'
                         " AND submitted=? AND runid='' AND replay_id=0",
                         (j['runid'], S.TIER_KSF, j['map'], j['track'], j['style'],
                          j['player'], j['millis'], j['when']))
            if not current(conn, j) or ready(conn, j):
                continue
            key = '%s|%d|%d|%s' % (mp, zone, mode, j['runid'])
            if state.get('failed', {}).get(key, 0) > int(time.time()):
                continue
            if key not in jobs and len(jobs) < MAX_QUEUE:
                jobs[key] = dict(j, status='queued', retry=0)
    conn.commit()


def fetch(file):
    """Only validated advertised leaves on the fixed upstream, no redirects."""
    if not FILE.fullmatch(file):
        raise ValueError('invalid replay filename')

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None

    req = urllib.request.Request(K.KSF_BASE + '/api/replays/' + file + '?game=66t',
                                 headers={'User-Agent': K.UA})
    with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as r:
        claimed = getattr(r, 'headers', {}).get('Content-Length')
        expected = None
        if claimed is not None:
            try:
                expected = int(claimed)
            except ValueError as exc:
                raise http.client.HTTPException('invalid replay length') from exc
            if expected < 0:
                raise http.client.HTTPException('negative replay length')
            if expected > MAX_BYTES:
                raise ValueError('replay exceeds byte cap')
        deadline = time.monotonic() + 30
        parts = []
        size = 0
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('replay body deadline')
            # read1 makes ONE buffered/socket read, rather than waiting forever
            # to fill a large read() from a peer trickling bytes under timeout.
            chunk = r.read1(min(64 << 10, MAX_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError('replay exceeds byte cap')
            parts.append(chunk)
        if expected is not None and size != expected:
            raise http.client.IncompleteRead(b'', expected - size)
    return b''.join(parts)


def transport(download, file):
    """Keep socket/header/body failures separate from LOCAL archive errors."""
    try:
        return download(file)
    except urllib.error.HTTPError:
        raise
    except (OSError, http.client.HTTPException) as exc:
        raise urllib.error.URLError(exc) from exc


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.part')
    with tmp.open('wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def install(conn, job, data):
    """File immutable original/provenance first, then atomically link exact PB."""
    if not current(conn, job):
        return None
    if len(data) > MAX_BYTES:
        raise ValueError('replay exceeds byte cap')
    root = Path(S.KSF_DIR)
    parent = root
    while not parent.exists():
        parent = parent.parent
    if shutil.disk_usage(parent).free < (256 << 20):
        raise OSError('KSF archive reserve below 256 MiB')
    text, info = C.convert(data, job['map'], job['bonus'], STYLES[job['mode']],
                           job['name'], job['seconds'])
    ticks = info['stop'] - info['start']
    # Archive naming grammar, source hash distinguishes styles/equal-time runs.
    sid = hashlib.sha256(job['player'].encode()).hexdigest()[:8]
    body = text.encode('utf-8')
    digest = hashlib.sha256(body).hexdigest()
    leaf = '%07d_ksf%s-%s_run.rec' % (ticks, digest[:9], sid)
    directory = root / job['map'] / S.leg_dir(job['track'], 0)
    original = root / '.originals' / (info['sha256'] + '.rec')
    # Same containment contract as serving; never write through an archive link.
    target = directory / leaf
    if not os.path.realpath(target).startswith(os.path.realpath(root) + os.sep):
        raise ValueError('KSF archive path escapes root')
    if directory.is_symlink() or (root / job['map']).is_symlink() or original.parent.is_symlink():
        raise ValueError('KSF archive directory is a link')
    atomic(original, data)
    atomic(directory / leaf, body)
    provenance = original.with_name(info['sha256'] + '-' + hashlib.sha256(
        job['runid'].encode()).hexdigest()[:16] + '.json')
    atomic(provenance, json.dumps(
        dict(job, sha256=info['sha256'], game='css66',
             upstream=K.KSF_BASE + '/api/replays/' + job['file'] + '?game=66t'),
        sort_keys=True).encode('utf-8'))
    with conn:
        # Re-check inside the write transaction; an import could have won.
        conn.execute('BEGIN IMMEDIATE')
        if not current(conn, job):
            return None
        digest = hashlib.sha256(body).hexdigest()
        conn.execute(
            'INSERT INTO replays (node,map_dir,leaf,bytes,sha,map,track,leg,player,ticks,'
            ' tickrate,millis,kind,seen,runid,bound,submitted,tier,style,name,flags)'
            " VALUES ('ksf',?,?,?,?,?,?,?,?,?,?,?,'ksf',?,?,1,?,?,?,?,0)"
            ' ON CONFLICT(map,track,leg,leaf) DO UPDATE SET bytes=excluded.bytes,'
            ' sha=excluded.sha,seen=excluded.seen'
            " WHERE replays.kind='ksf' AND replays.runid=excluded.runid",
            (job['map'], leaf, len(body), digest, job['map'], job['track'], 0,
             job['player'], ticks, 1 / K.KSF_TICK, int(round(info['seconds'] * 1000)),
             int(time.time()), 'ksf-' + info['sha256'][:20], job['when'],
             S.TIER_KSF, job['style'], job['name']))
        indexed = conn.execute('SELECT id,kind,runid FROM replays WHERE map=? AND track=?'
                               ' AND leg=0 AND leaf=?', (job['map'], job['track'], leaf)).fetchone()
        if indexed['kind'] != 'ksf' or indexed['runid'] != 'ksf-' + info['sha256'][:20]:
            raise ValueError('archive leaf belongs to another recording kind')
        rid = indexed['id']
        conn.execute('UPDATE runs SET replay_id=? WHERE tier=? AND map=? AND track=?'
                     ' AND leg=0 AND style=? AND player=? AND runid=? AND millis=? AND submitted=?',
                     (rid, S.TIER_KSF, job['map'], job['track'], job['style'],
                      job['player'], job['runid'], job['millis'], job['when']))
    return rid


def tick(cache, maximum=2, delay=3.0, download=fetch):
    """Caller holds ksfimport lock. Durable intent survives interruption."""
    sf = os.path.join(cache, 'demos.json')
    state = K._load(sf)
    state = state if isinstance(state, dict) else {}
    state['version'] = 1
    if not isinstance(state.get('jobs'), dict):
        state['jobs'] = {}
    if not isinstance(state.get('failed'), dict):
        state['failed'] = {}
    now = int(time.time())
    state['failed'] = {k: t for k, t in state['failed'].items()
                       if type(t) is int and t > now}
    state['failed'] = dict(sorted(state['failed'].items(), key=lambda x: x[1])[-2048:])
    jobs = state['jobs']
    conn = S.connect()
    made = linked = 0
    try:
        # Retain only queued/retryable current jobs; completed links rediscover
        # locally if lost. A saturated obsolete queue must not starve new maps.
        jobs = state['jobs'] = {k: j for k, j in jobs.items()
                              if isinstance(j, dict) and current(conn, j) and not ready(conn, j)}
        discover(cache, state, conn)
        K._save(sf, state)
        park = K._load(os.path.join(cache, '.refused')) or {}
        for key, job in list(jobs.items()):
            if made >= min(2, max(0, maximum)):
                break
            if now < int(park.get('until') or 0) or job.get('retry', 0) > now:
                continue
            if ready(conn, job):
                jobs.pop(key, None)
                continue
            if not current(conn, job):
                jobs.pop(key, None)
                continue
            # Sleep before FIRST request as well: the board crawler just acted.
            time.sleep(max(3.0, delay))
            made += 1
            try:
                data = transport(download, job['file'])
                rid = install(conn, job, data)
                if rid:
                    linked += 1
                    jobs.pop(key, None)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                # Refusal belongs to the HOST, not whichever demo happened to
                # be asked. All non-2xx/redirects/network failures stop this tick.
                n = int(park.get('n') or 0) + 1
                wait = min(K.COOLDOWN * 2 ** min(n - 1, 8), K.COOLDOWN_MAX)
                code = getattr(e, 'code', 0)
                K._save(os.path.join(cache, '.refused'),
                        dict(at=now, until=now + wait, n=n, why='demo network %d' % code))
                job['retry'] = now + wait
                print('KSF demos refused: network %d; shared crawler parked' % code)
                break
            except (OSError, ValueError) as e:
                job['retry'] = now + 86400
                job['why'] = type(e).__name__
                job['strikes'] = job.get('strikes', 0) + 1
                print('KSF demo deferred: %s' % type(e).__name__)
                if job['strikes'] >= 3:
                    # Bounded durable tombstone frees the queue for later maps.
                    state['failed'][key] = now + 7 * 86400
                    jobs.pop(key, None)
            finally:
                K._save(sf, state)
        # Also persist local-only removals/empty ticks, not just fetch attempts.
        K._save(sf, state)
        print('KSF demos: %d request(s), %d linked, %d pending' % (made, linked, len(jobs)))
        return made, linked
    finally:
        conn.close()
