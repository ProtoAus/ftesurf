"""Bounded account viewmodel setup, never inventory, paths or run evidence.

Catalog-v1 row IDs are append-only. The matching pure QC codec is
src/shared/sh_viewmodel.qc. Authority is social.session's proven lobby capability;
no client-supplied account/GUID chooses the row. Migration is additive.
"""
import math
import re

VERSION = 1
FIELDS = 21
MAX_BYTES = 256
NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?\Z", re.ASCII)
SQL = """
CREATE TABLE IF NOT EXISTS account_viewmodels (
 steamid TEXT PRIMARY KEY, setup TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision BETWEEN 1 AND 16777215),
 updated INTEGER NOT NULL);
"""


def limits(field):
    if field == 0:
        return 1, 1, True
    if field == 2:
        return 0, 24, True
    if field == 3:
        return 32, 49, True
    if field == 4:
        return 64, 117, True
    if field == 6:
        return 0, 3, True
    if field == 7:
        return 0, 1000, True
    if field == 8:
        return .25, 4, False
    if field == 9:
        return 0, 360, False
    if field in (15, 16):
        return 0, 179, False
    return 0, 1, field not in (10, 11, 13, 14, 18, 19, 20)


def normalize(packed):
    if not isinstance(packed, str) or len(packed) > MAX_BYTES:
        return None
    parts = packed.split(',')
    if len(parts) != FIELDS:
        return None
    out = []
    for field, text in enumerate(parts):
        if not 1 <= len(text) <= 12 or not NUMBER.fullmatch(text):
            return None
        value = float(text)
        lo, hi, integer = limits(field)
        if not math.isfinite(value) or not lo <= value <= hi:
            return None
        if integer and value != int(value):
            return None
        number = format(value, '.4f').rstrip('0').rstrip('.')
        out.append('0' if number == '-0' else number)
    return ','.join(out)


def load(db, steamid):
    row = db.execute('SELECT setup,revision FROM account_viewmodels WHERE steamid=?',
                     (steamid,)).fetchone()
    if row is None:
        return {'setup': '', 'revision': 0}
    # Preserve an unknown/corrupt row; never reinterpret it as empty and erase it.
    packed = normalize(row['setup'])
    if (packed is None or packed != row['setup'] or type(row['revision']) is not int
            or not 1 <= row['revision'] <= 16777215):
        raise ValueError('Stored viewmodel setup is unavailable')
    return {'setup': packed, 'revision': row['revision']}


def save(db, steamid, packed, revision, now):
    """Caller owns BEGIN IMMEDIATE; compare revision before changing one row."""
    canonical = normalize(packed)
    if canonical is None or type(revision) is not int or not 0 <= revision < 16777215:
        raise ValueError('Invalid viewmodel setup')
    current = load(db, steamid)
    if current['revision'] != revision:
        return None
    next_revision = revision + 1
    if not revision:
        db.execute('INSERT INTO account_viewmodels(steamid,setup,revision,updated) VALUES(?,?,?,?)',
                   (steamid, canonical, next_revision, now))
    else:
        db.execute('UPDATE account_viewmodels SET setup=?,revision=?,updated=?'
                   ' WHERE steamid=? AND revision=?',
                   (canonical, next_revision, now, steamid, revision))
    return {'setup': canonical, 'revision': next_revision}
