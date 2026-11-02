#!/usr/bin/env python3
"""P1210 data step: re-convert surfd's served KSF .rec with the converter that infers DUCKED.

plan (default): read-only on surfd.db. For each kind='ksf' replays row, find its job record
  (.originals/job-*.json) by runid, map, track, leg and player; re-run the OLD converter (this
  root's rollback-runtime, = the generation that wrote the archive) and require the row's exact
  sha and leaf -- the proof that the job and its inputs are the ones ksfgrab used -- then write
  the NEW conversion (runtime/, = live 833c8c58) beside the old leaf, under the name ksfgrab gives
  it. Old files, originals and job records are never touched. Writes reconvert/plan.json.
commit: one BEGIN IMMEDIATE transaction switching each planned row's (leaf, bytes, sha), guarded
  on the row still naming the old leaf and sha. Writes reconvert/commit-result.json.
rollback: the same switch back, from the plan.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import struct
import sys
import time

ROOT = Path('/srv/nvme/agent-work/ksfduck-1210-37d486c9')
KSF = Path('/srv/nvme/surfd/data/ksfruns')
DB = '/srv/nvme/surfd/data/surfd.db'
OUT = ROOT / 'reconvert'
STYLES = {0: 'FW', 1: 'SW', 2: 'HSW', 3: 'BW'}        # ksfgrab.STYLES (833c8c58 and 470ab7c9)
assert '37d486c9' in (ROOT / 'OWNER.md').read_text()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def sha(b):
    return hashlib.sha256(b).hexdigest()


def leaf_of(info, body, player):
    # ksfgrab.install's archive grammar.
    return '%07d_ksf%s-%s_run.rec' % (info['stop'] - info['start'], sha(body)[:9],
                                      sha(player.encode())[:8])


def convert(mod, data, job):
    text, info = mod.convert(data, job['map'], job['bonus'], STYLES[job['mode']], job['name'],
                             job['seconds'], stage=job['leg'], last=job.get('last', False))
    return text.encode('utf-8'), info


def plan():
    load('ksfreplay_info', ROOT / 'runtime/tools/ksfreplay_info.py')
    new = load('ksfconvert_new', ROOT / 'runtime/tools/ksfconvert.py')
    old = load('ksfconvert_old', ROOT / 'rollback-runtime/tools/ksfconvert.py')
    assert hasattr(new, 'infer_ducked') and not hasattr(old, 'infer_ducked')
    OUT.mkdir(mode=0o700, exist_ok=False)
    jobs = {}
    for f in (KSF / '.originals').glob('job-*.json'):
        doc = json.loads(f.read_bytes())
        key = ('ksf-' + doc['sha256'][:20], doc['map'], doc['track'], doc['leg'], doc['player'])
        jobs.setdefault(key, []).append(doc)
    files = {}
    for p in KSF.glob('*/*/*_run.rec'):
        if p.parts[-3].startswith('.'):
            continue
        files[(p.parts[-3], p.name)] = p
    db = sqlite3.connect('file:' + DB + '?mode=ro', uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT id, map, map_dir, track, leg, leaf, bytes, sha, runid, player"
                      " FROM replays WHERE kind='ksf' ORDER BY id").fetchall()
    taken = {(r['map'], r['track'], r['leg'], r['leaf']) for r in db.execute(
        'SELECT map, track, leg, leaf FROM replays')}
    db.close()
    out, why, t0 = [], {}, time.time()
    log = (OUT / 'plan.log').open('w')
    for n, r in enumerate(rows):
        if n % 250 == 0:
            print('%d/%d %.0fs %s' % (n, len(rows), time.time() - t0, json.dumps(why)), file=log, flush=True)
        path = files.get((r['map_dir'], r['leaf']))
        if not path:
            why['no file'] = why.get('no file', 0) + 1
            continue
        match = None
        for job in jobs.get((r['runid'], r['map'], r['track'], r['leg'], r['player']), []):
            data = (KSF / '.originals' / (job['sha256'] + '.rec')).read_bytes()
            try:
                body, info = convert(old, data, job)
            except (ValueError, KeyError, struct.error):
                continue
            if sha(body) == r['sha'] and len(body) == r['bytes'] and leaf_of(info, body, job['player']) == r['leaf']:
                match = (job, data)
                break
        if not match:
            why['old converter does not reproduce'] = why.get('old converter does not reproduce', 0) + 1
            continue
        job, data = match
        body, info = convert(new, data, job)
        leaf = leaf_of(info, body, job['player'])
        if leaf == r['leaf']:
            why['unchanged'] = why.get('unchanged', 0) + 1
            continue
        if (r['map'], r['track'], r['leg'], leaf) in taken:
            why['new leaf taken'] = why.get('new leaf taken', 0) + 1
            continue
        target = path.with_name(leaf)
        if target.exists():
            if target.read_bytes() != body:
                why['target differs'] = why.get('target differs', 0) + 1
                continue
        else:
            part = target.with_name(target.name + '.part')
            fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(body)
                f.flush()
                os.fsync(f.fileno())
            os.replace(part, target)
        taken.add((r['map'], r['track'], r['leg'], leaf))
        out.append(dict(id=r['id'], map=r['map'], track=r['track'], leg=r['leg'],
                        old_leaf=r['leaf'], old_sha=r['sha'], old_bytes=r['bytes'],
                        new_leaf=leaf, new_sha=sha(body), new_bytes=len(body),
                        old_path=str(path), new_path=str(target),
                        holds=info['duck_holds'], ducked=info['ducked_frames']))
        why['planned'] = why.get('planned', 0) + 1
    print('done %d rows %.0fs %s' % (len(rows), time.time() - t0, json.dumps(why)), file=log, flush=True)
    with (OUT / 'plan.json').open('x') as f:
        json.dump(dict(rows=len(rows), why=why, entries=out), f)
    print(json.dumps(dict(rows=len(rows), why=why, holds=sum(e['holds'] for e in out))))


def switch(back):
    doc = json.loads((OUT / 'plan.json').read_bytes())
    a, b = ('old', 'new') if back else ('new', 'old')
    for e in doc['entries']:                    # every target file is there before any row moves
        assert os.path.getsize(e[a + '_path']) == e[a + '_bytes'], e[a + '_path']
    db = sqlite3.connect(DB, timeout=60)
    db.execute('PRAGMA busy_timeout=60000')
    db.execute('BEGIN IMMEDIATE')
    moved, clash = 0, []
    for e in doc['entries']:
        # A row the live ksfgrab wrote at the target leaf since the plan: this UPDATE alone
        # aborts (SQLite's default ABORT undoes the statement, not the transaction); skip it.
        try:
            cur = db.execute("UPDATE replays SET leaf=?, bytes=?, sha=? WHERE id=? AND kind='ksf'"
                             " AND leaf=? AND sha=?",
                             (e[a + '_leaf'], e[a + '_bytes'], e[a + '_sha'], e['id'],
                              e[b + '_leaf'], e[b + '_sha']))
            moved += cur.rowcount
        except sqlite3.IntegrityError:
            clash.append(e['id'])
    db.commit()
    db.close()
    name = 'rollback-result.json' if back else 'commit-result.json'
    res = dict(planned=len(doc['entries']), moved=moved, clashed=clash,
               utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    with (OUT / name).open('x') as f:
        json.dump(res, f)
    print(json.dumps(res))


if __name__ == '__main__':
    os.umask(0o077)
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'plan'
    if cmd == 'plan':
        plan()
    elif cmd in ('commit', 'rollback'):
        switch(cmd == 'rollback')
    else:
        sys.exit('usage: p1210_reconvert.py [plan|commit|rollback]')
