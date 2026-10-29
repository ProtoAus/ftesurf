"""Sparse KSF demo discovery: consume the existing paced crawler's file fields.

Original bytes and row provenance are retained, normalized text gets kind=ksf,
and ONLY an exact current KSF PB is linked. Never probe a filename or submit a
native result. Called under ksfimport's shared lock in unattended --watch --go.
No network from HTTP handlers. A tick scans <=32 board files and downloads <=6
(ksfimport.DEMO_MAX) advertised CSS/66t files, sequentially, after the board crawler's last request.
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

# Bound the advertised ASCII leaf before parsing numeric fields or making a URL.
FILE = re.compile(r'(?=.{1,255}\Z)replay_css_[0-9]+_([0-3])_([0-9]+)_([0-9]+)\.rec\Z')
BOARD = re.compile(r'([a-z0-9_]{1,64})/z([0-9]+)(?:m([1-3]))?\.json\Z')
MAX_BYTES = 16 << 20
PARK = '.refused-demos'    # P1117: downloads' own park, beside the crawler's .refused
MAX_QUEUE = 256
MAX_RECOVER = 2
MAX_FAILED = 2048
MAX_PROVENANCE = 16 << 10
FILESTREAK = 3             # Patch 896: this many file-level failures in a day, in a row, are the host's
FLOOR = 15 << 30           # Patch 896: no download or install below this much free disk
SCAN = 32
BINDING = ('map', 'track', 'leg', 'style', 'player', 'runid', 'millis', 'when', 'file')
STYLES = {0: 'FW', 1: 'SW', 2: 'HSW', 3: 'BW'}


def stages_of(cache, mp):
    """A staged map's stage count from the crawler's cached map row, else 0. Never asks."""
    try:
        info = K.map_info(mp, cache, K.Pacer(0, 0))
    except K.OverBudget:
        return 0
    n = info.get('cp_count') if info and info.get('isLinear') is False else 0
    return n if type(n) is int and 0 < n <= K.KSF_STAGES else 0


def candidate(mp, zone, mode, raw, stages=0):
    """Patch 891: a stage zone is a candidate on a map of `stages` stages. KSF records
    each stage in its own file, so nothing is cut from a longer run."""
    if not isinstance(raw, dict) or S.clean_map(mp) != mp or mode not in STYLES:
        return None
    if zone != 0 and not 31 <= zone <= 99 and not 1 <= zone <= stages:
        return None
    file = raw.get('file')
    m = FILE.fullmatch(file) if isinstance(file, str) else None
    r = K.rec_row(mp, zone, mode, raw)
    if not m or not r or not r['runid']:
        return None
    if (int(m[1]) != mode or int(m[2]) != raw.get('playerID')
            or int(m[3]) != r['when']):
        return None
    j = dict(r, file=file, seconds=raw['time'], bonus=r['track'],
             mode=mode, record_id=raw['record_id'])
    if r['leg']:
        j['last'] = zone == stages
    return j


def valid_job(job):
    try:
        return (isinstance(job, dict) and re.fullmatch(r'[a-z0-9_]{1,64}', job['map'])
                and type(job['track']) is int and 0 <= job['track'] <= 69
                and type(job['leg']) is int
                and ((job['leg'] == 0 and job['bonus'] == job['track'] and 'last' not in job)
                     or (job['track'] == 0 and job['bonus'] == 0 and 1 <= job['leg'] <= K.KSF_STAGES
                         and type(job.get('last')) is bool))
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
        'SELECT runid, millis, submitted FROM runs WHERE map=? AND track=? AND leg=?'
        ' AND style=? AND player=? AND tier=?'
        ' AND NOT EXISTS (SELECT 1 FROM ksf_unbound u WHERE u.map=runs.map'
        ' AND u.track=runs.track AND u.leg=runs.leg AND u.style=runs.style'
        ' AND u.player=runs.player)',
        (job['map'], job['track'], job['leg'], job['style'], job['player'],
         S.TIER_KSF)).fetchone()
    return bool(row and row['runid'] == job['runid'] and row['millis'] == job['millis']
                and row['submitted'] == job['when'])


def ready(conn, job):
    """Exactly linked AND readable; warm files must not occupy pending slots."""
    if not valid_job(job):
        return False
    row = conn.execute(
        'SELECT p.* FROM runs r JOIN replays p ON p.id=r.replay_id'
        ' WHERE r.tier=? AND r.map=? AND r.track=? AND r.leg=? AND r.style=?'
        ' AND r.player=? AND r.runid=? AND r.millis=? AND r.submitted=?',
        (S.TIER_KSF, job['map'], job['track'], job['leg'], job['style'], job['player'],
         job['runid'], job['millis'], job['when'])).fetchone()
    return readable_replay(row)


def readable_replay(row):
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


def pending_deferral(conn, key):
    """Reconcile bounded nonterminal history without discarding live strikes."""
    try:
        mp, zone, mode, runid = key.split('|', 3)
        if (not re.fullmatch(r'[a-z0-9_]{1,64}', mp)
                or not re.fullmatch(r'[0-9]{1,2}', zone)
                or mode not in ('0', '1', '2', '3') or not runid):
            return False
        zone = int(zone)
        track, leg = K.zone_track_leg(zone)
        row = conn.execute(
            'SELECT p.* FROM runs r LEFT JOIN replays p ON p.id=r.replay_id'
            ' WHERE r.tier=? AND r.map=? AND r.track=? AND r.leg=? AND r.style=? AND r.runid=?',
            (S.TIER_KSF, mp, track, leg, K.KSF_MODES[int(mode)], runid)).fetchone()
        return bool(row and not readable_replay(row))
    except (TypeError, ValueError):
        return False


def fresh(conn, state, jobs, mp, zone, mode, raw, now, stages=0):
    """(key, job, deferral) for an exact current PB not yet linked or queued."""
    j = candidate(mp, zone, mode, raw, stages)
    if not j:
        return None
    # Backfill pre-P704 identity only from the same official timestamp
    # and millis. Never let an old cached PB replace a newer one.
    conn.execute('UPDATE runs SET runid=? WHERE tier=? AND map=? AND track=?'
                 ' AND leg=? AND style=? AND player=? AND millis=?'
                 " AND submitted=? AND runid='' AND replay_id=0"
                 " AND NOT EXISTS (SELECT 1 FROM ksf_unbound u WHERE u.map=runs.map"
                 " AND u.track=runs.track AND u.leg=runs.leg AND u.style=runs.style"
                 " AND u.player=runs.player)",
                 (j['runid'], S.TIER_KSF, j['map'], j['track'], j['leg'], j['style'],
                  j['player'], j['millis'], j['when']))
    if not current(conn, j) or ready(conn, j):
        return None
    key = '%s|%d|%d|%s' % (mp, zone, mode, j['runid'])
    deferred = state.get('failed', {}).get(key, 0)
    retry = deferred.get('retry', 0) if isinstance(deferred, dict) else deferred
    if retry > now or key in jobs:
        return None
    return key, j, deferred


def queue(state, jobs, key, j, deferred):
    jobs[key] = dict(j, status='queued', retry=0)
    if isinstance(deferred, dict):
        jobs[key].update(deferred)
        state['failed'].pop(key, None)


def discover_wanted(cache, state, conn, prio):
    """Boards of maps viewed lately (mapwant), SCAN a tick on their own cursor,
    before the rotation. A full queue gives up one cold unwanted job per row."""
    folder = Path(cache) / 'boards'
    names = []
    for mp in sorted(prio):
        if BOARD.fullmatch(mp + '/z0.json') and not (folder / mp).is_symlink():
            names += sorted('%s/%s' % (mp, p.name) for p in (folder / mp).glob('*.json'))
    after = state.get('wanted_cursor', '')
    names = [n for n in names if n > after] + [n for n in names if n <= after]
    jobs = state.setdefault('jobs', {})
    state.setdefault('failed', {})
    now = int(time.time())
    for name in names[:SCAN]:
        state['wanted_cursor'] = name
        m = BOARD.fullmatch(name)
        p = folder / name
        if not m or p.is_symlink() or p.stat().st_size > 8 << 20:
            continue
        mp, zone, mode = m[1], int(m[2]), int(m[3] or 0)
        stages = stages_of(cache, mp) if 1 <= zone <= K.KSF_STAGES else 0
        for raw in K.board_load(cache, mp, zone, mode)['rows']:
            got = fresh(conn, state, jobs, mp, zone, mode, raw, now, stages)
            if not got:
                continue
            if len(jobs) >= MAX_QUEUE:
                cold = next((k for k, held in jobs.items() if held.get('map') not in prio
                             and not held.get('strikes') and not held.get('retry')
                             and not provenance(held).is_file()), None)
                if cold is None:
                    continue
                jobs.pop(cold)
            queue(state, jobs, *got)
    conn.commit()


def discover(cache, state, conn, prio=()):
    """Fair bounded rotation over cached boards; state lives under crawler lock."""
    folder = Path(cache) / 'boards'
    names = sorted(p.relative_to(folder).as_posix() for p in folder.glob('*/*.json'))
    resume = state.get('overflow_board', '')
    overflow_cursor = state.get('overflow_cursor', '') if resume in names else ''
    if resume in names:
        # Resume within the last attempted board before advancing the scan.
        names = [n for n in names if n >= resume] + [n for n in names if n < resume]
    else:
        after = state.get('cursor', '')
        names = [n for n in names if n > after] + [n for n in names if n <= after]
    jobs = state.setdefault('jobs', {})
    state.setdefault('failed', {})
    retained_admitted = 0
    overflow = []
    now = int(time.time())
    for index, name in enumerate(names[:SCAN]):
        state['cursor'] = name
        m = BOARD.fullmatch(name)
        p = folder / name
        if not m or p.is_symlink() or p.parent.is_symlink() or p.stat().st_size > 8 << 20:
            continue
        mp, zone, mode = m[1], int(m[2]), int(m[3] or 0)
        stages = stages_of(cache, mp) if 1 <= zone <= K.KSF_STAGES else 0
        doc = K.board_load(cache, mp, zone, mode)
        for raw in doc['rows']:
            got = fresh(conn, state, jobs, mp, zone, mode, raw, now, stages)
            if not got:
                continue
            key, j, deferred = got
            if len(jobs) >= MAX_QUEUE:
                # Cold requests cannot monopolize admission while the host is
                # parked. Presence is priority only; tick still validates the
                # exact provenance, digest and PB before any original can act.
                if retained_admitted >= MAX_RECOVER or not provenance(j).is_file():
                    continue
                cold = next((k for k, held in jobs.items() if held.get('map') not in prio
                             and not held.get('strikes') and not held.get('retry')
                             and not provenance(held).is_file()), None)
                if cold is None:
                    # No protected eviction: at most two local-only overflow
                    # attempts, with exact-key rotation and durable deferrals.
                    if key not in state['failed'] and len(state['failed']) >= MAX_FAILED:
                        continue
                    if name == resume and key <= overflow_cursor:
                        continue
                    overflow.append((index, key, j, name))
                    overflow.sort(key=lambda item: (item[0], item[1]))
                    del overflow[MAX_RECOVER:]
                    continue
                jobs.pop(cold)
                retained_admitted += 1
            queue(state, jobs, key, j, deferred)
    conn.commit()
    if not overflow:
        # No candidate in this window: normal board rotation must keep moving.
        state.pop('overflow_board', None)
        state.pop('overflow_cursor', None)
    return [(key, job, name) for _, key, job, name in overflow]


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
        try:
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
        except TimeoutError:
            raise                       # a trickle is the host's
        except (OSError, http.client.HTTPException) as exc:
            raise BodyBroken('%s after the headers' % type(exc).__name__) from exc
    return b''.join(parts)


class BodyBroken(OSError):
    """Patch 891: the host answered for this file and its body broke after the headers."""


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


def provenance(job):
    """Direct exact-job lookup; never scan an ever-growing original archive."""
    identity = {k: job[k] for k in BINDING}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return Path(S.KSF_DIR) / '.originals' / ('job-' + key + '.json')


def retained_digest(job):
    """Only exact bounded provenance can authorize reuse of original bytes."""
    path = provenance(job)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError('KSF provenance is a link')
    try:
        with path.open('rb') as f:
            data = f.read(MAX_PROVENANCE + 1)
    except FileNotFoundError:
        return None
    if len(data) > MAX_PROVENANCE:
        raise ValueError('KSF provenance exceeds byte cap')
    try:
        doc = json.loads(data)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError('invalid KSF provenance') from exc
    if (not isinstance(doc, dict) or any(doc.get(k) != job[k] for k in BINDING)
            or doc.get('game') != 'css66' or not isinstance(doc.get('sha256'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', doc['sha256'])):
        raise ValueError('KSF provenance binding differs')
    return doc['sha256']


def retained_bytes(digest):
    path = Path(S.KSF_DIR) / '.originals' / (digest + '.rec')
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError('KSF original is a link')
    try:
        with path.open('rb') as f:
            data = f.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return None
    if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('KSF original digest differs')
    return data


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
                           job['name'], job['seconds'], stage=job['leg'],
                           last=job.get('last', False))
    ticks = info['stop'] - info['start']
    # Archive naming grammar, source hash distinguishes styles/equal-time runs.
    sid = hashlib.sha256(job['player'].encode()).hexdigest()[:8]
    body = text.encode('utf-8')
    digest = hashlib.sha256(body).hexdigest()
    leaf = '%07d_ksf%s-%s_run.rec' % (ticks, digest[:9], sid)
    directory = root / job['map'] / S.leg_dir(job['track'], job['leg'])
    original = root / '.originals' / (info['sha256'] + '.rec')
    # Same containment contract as serving; never write through an archive link.
    target = directory / leaf
    if not os.path.realpath(target).startswith(os.path.realpath(root) + os.sep):
        raise ValueError('KSF archive path escapes root')
    if directory.is_symlink() or (root / job['map']).is_symlink() or original.parent.is_symlink():
        raise ValueError('KSF archive directory is a link')
    # Intent first: any completed original must have a direct exact-job lookup,
    # even if normalized publication is interrupted. Missing bytes retry safely.
    atomic(provenance(job), json.dumps(
        dict(job, sha256=info['sha256'], game='css66',
             upstream=K.KSF_BASE + '/api/replays/' + job['file'] + '?game=66t'),
        sort_keys=True).encode('utf-8'))
    atomic(original, data)
    atomic(directory / leaf, body)
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
            (job['map'], leaf, len(body), digest, job['map'], job['track'], job['leg'],
             # Patch 757: the row's time, which the converter bound; the frame count
             # can differ by more than a tick (tools/p757ksfconvert.md). ticks stays the file's.
             job['player'], ticks, 1 / K.KSF_TICK, job['millis'],
             int(time.time()), 'ksf-' + info['sha256'][:20], job['when'],
             S.TIER_KSF, job['style'], job['name']))
        indexed = conn.execute('SELECT id,kind,runid FROM replays WHERE map=? AND track=?'
                               ' AND leg=? AND leaf=?',
                               (job['map'], job['track'], job['leg'], leaf)).fetchone()
        if indexed['kind'] != 'ksf' or indexed['runid'] != 'ksf-' + info['sha256'][:20]:
            raise ValueError('archive leaf belongs to another recording kind')
        rid = indexed['id']
        conn.execute('UPDATE runs SET replay_id=? WHERE tier=? AND map=? AND track=?'
                     ' AND leg=? AND style=? AND player=? AND runid=? AND millis=? AND submitted=?',
                     (rid, S.TIER_KSF, job['map'], job['track'], job['leg'], job['style'],
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
                       if (type(t) is int and t > now) or
                       (isinstance(t, dict) and type(t.get('retry')) is int
                        and type(t.get('strikes')) is int and 0 < t['strikes'] < 3)}
    state.pop('filefail', None)         # P891's ledger, superseded by P896's rule
    if len(state['failed']) > MAX_FAILED:
        # Older writers appended terminal failures after their initial truncation.
        # Preserve that input verbatim; normal expiry can unblock a later tick.
        print('KSF demos parked locally: deferral ledger exceeds %d; no work or state save' % MAX_FAILED)
        return 0, 0
    jobs = state['jobs']
    conn = S.connect()
    made = linked = recovered = 0
    try:
        state['failed'] = {k: t for k, t in state['failed'].items()
                           if not isinstance(t, dict) or pending_deferral(conn, k)}
        # Retain only queued/retryable current jobs; completed links rediscover
        # locally if lost. A saturated obsolete queue must not starve new maps.
        jobs = state['jobs'] = {k: j for k, j in jobs.items()
                              if isinstance(j, dict) and current(conn, j) and not ready(conn, j)}
        prio = K.wanted_maps(now)
        discover_wanted(cache, state, conn, prio)
        overflow = discover(cache, state, conn, prio)
        K._save(sf, state)
        # P1117: the crawler's park stops downloads too; a download's own failure parks
        # only PARK, so the boards and profile walks keep going.
        park = K._load(os.path.join(cache, '.refused')) or {}
        dpark = K._load(os.path.join(cache, PARK)) or {}
        until = max(int(park.get('until') or 0), int(dpark.get('until') or 0))
        # Give each lane one original slot when both have eligible work; viewed maps first.
        queued = sorted(jobs.items(), key=lambda kj: kj[1].get('map') not in prio)
        work = overflow[:1] + [(k, j, None) for k, j in queued] + overflow[1:]
        # Patch 896: all of KSF's advertised recordings are ~46 GB (21 Oct), more than the
        # Pi can spare beside its lobbies; install()'s 256 MiB reserve is the last ditch only.
        probe = Path(S.KSF_DIR)
        while not probe.exists():
            probe = probe.parent
        if shutil.disk_usage(probe).free < FLOOR:
            print('KSF demos paused: under %d GiB free beside the archive' % (FLOOR >> 30))
            work = []
        for key, job, board in work:
            local_only = board is not None
            if local_only:
                if recovered >= MAX_RECOVER:
                    continue
                state['overflow_board'] = board
                state['overflow_cursor'] = key
                deferred = state['failed'].get(key, {})
                if isinstance(deferred, dict):
                    job.update(deferred)
                if key not in state['failed'] and len(state['failed']) >= MAX_FAILED:
                    continue
            if job.get('retry', 0) > now:
                continue
            if job.get('terminal'):
                jobs.pop(key, None)
                continue
            if ready(conn, job):
                jobs.pop(key, None)
                continue
            if not current(conn, job):
                jobs.pop(key, None)
                continue
            try:
                data = None
                asked = False
                if local_only:
                    recovered += 1
                digest = retained_digest(job)
                if digest:
                    if not local_only:
                        if recovered >= MAX_RECOVER:
                            continue
                        recovered += 1  # Bound original reads, including corrupt/missing bytes.
                    if not local_only:
                        jobs[key] = jobs.pop(key)  # Persist fairness even for parked cache misses.
                    data = retained_bytes(digest)
                if data is None:
                    if local_only:
                        continue
                    if made >= min(K.DEMO_MAX, max(0, maximum)) or now < until:
                        continue
                    # Sleep before FIRST request: the board crawler just acted.
                    time.sleep(max(3.0, delay))
                    made += 1
                    asked = True
                    data = transport(download, job['file'])
                if asked:
                    state['filestreak'] = {}    # the host just served a whole file
                    if dpark:           # an answer lifts the downloads' park
                        try:
                            os.remove(os.path.join(cache, PARK))
                        except FileNotFoundError:
                            pass
                        dpark = {}
                rid = install(conn, job, data)
                if rid:
                    linked += 1
                    state['failed'].pop(key, None)
                    jobs.pop(key, None)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                # Refusal belongs to the HOST, not whichever demo happened to be asked: every
                # non-2xx, redirect or network failure stops this tick, and parks downloads --
                # except (Patch 896) a failure only a file can have: 404/500, or a body broken
                # after the headers. surf_ab's and then surf_kultur's replays break mid-body on
                # every ask (21 Oct), and parking for each such file stalled every map's demos
                # for days. That file is set aside 7 days; FILESTREAK of them in a row is the host.
                code = getattr(e, 'code', 0)
                own = code in (404, 500) or isinstance(getattr(e, 'reason', None), BodyBroken)
                run = state.get('filestreak') if isinstance(state.get('filestreak'), dict) else {}
                at = run.get('at') if type(run.get('at')) is int else 0
                held = [k for k in (run.get('keys') if isinstance(run.get('keys'), list) else [])
                        if isinstance(k, str)] if 0 <= now - at <= 86400 else []
                if own and len(held) + 1 < FILESTREAK:
                    if key in state['failed'] or len(state['failed']) < MAX_FAILED:
                        state['failed'][key] = now + 7 * 86400
                        jobs.pop(key, None)
                    else:
                        job.update(retry=now + 7 * 86400, terminal=True)
                    state['filestreak'] = dict(at=now, keys=held + [key])
                    print('KSF demo set aside: network %d on its own file (%d in a row)'
                          % (code, len(held) + 1))
                    break
                # The host's -- and so was a run of file-looking failures that reached
                # FILESTREAK, so the files it set aside go back to the queue.
                if own:
                    for k in held:
                        state['failed'].pop(k, None)
                state['filestreak'] = {}
                n = int(dpark.get('n') or 0) + 1
                base = K.QUIET_COOLDOWN if code == 0 and not own else K.COOLDOWN
                wait = min(base * 2 ** min(n - 1, 8), K.COOLDOWN_MAX)
                K._save(os.path.join(cache, PARK),
                        dict(at=now, until=now + wait, n=n, why='demo network %d' % code))
                job['retry'] = now + wait
                print('KSF demos refused: network %d; demos parked %d min' % (code, wait // 60))
                break
            except (OSError, ValueError) as e:
                job['retry'] = now + 86400
                job['why'] = type(e).__name__
                job['strikes'] = job.get('strikes', 0) + 1
                print('KSF demo deferred: %s: %s' % (type(e).__name__, ' '.join(str(e).split())[:120]))
                if job['strikes'] >= 3:
                    # Bounded durable tombstone frees the queue for later maps.
                    if key in state['failed'] or len(state['failed']) < MAX_FAILED:
                        state['failed'][key] = now + 7 * 86400
                        jobs.pop(key, None)
                    else:
                        job.update(retry=now + 7 * 86400, terminal=True)
                elif local_only:
                    state['failed'][key] = dict(retry=job['retry'], strikes=job['strikes'])
            finally:
                K._save(sf, state)
        # Also persist local-only removals/empty ticks, not just fetch attempts.
        K._save(sf, state)
        print('KSF demos: %d request(s), %d linked, %d pending' % (made, linked, len(jobs)))
        return made, linked
    finally:
        conn.close()
