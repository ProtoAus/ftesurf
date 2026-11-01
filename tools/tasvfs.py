"""Strict reader for native TAS VFS COMPONENT exports, not canonical approval.

A complete authority witness additionally needs the enforced policy/image identity,
pre-start source transaction, complete discovery/backing census, parsed-map/finish
controls and private-view equality. Never promote a profile from this object alone.
Paths/provenance are private operator data and must not enter public DTOs.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import PurePosixPath
import re
import stat

MAX_MANIFEST = 160 * 1024 * 1024
MAX_RECORDS = 262144
MAX_NAMES = 64 * 1024 * 1024
MAX_FILES = 8000
MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
PREP_MAX_FILES = 131072
PREP_MAX_TOTAL = 8 * 1024 * 1024 * 1024
ASSETS = ('models/', 'materials/', 'textures/', 'sound/', 'gfx/', 'particles/',
          'glsl/', 'scripts/', 'progs/', 'sprites/')
BASE_QUERIES = ('qwprogs.dat', 'csprogs.dat', 'menu.dat', 'progs.dat', 'csqcprogs.dat',
                'default.cfg', 'quake.rc', 'autoexec.cfg', 'server.cfg', 'cfg/default.cfg',
                'cfg/lobby/mode_surf.cfg', 'cfg/lobby/mode_bhop.cfg', 'data/mapmeta.txt',
                'mapmeta.txt', 'data/mapdeps.txt', 'mapdeps.txt')
SIDECARS = ('.bsp', '.phy', '.phs', '.ent', '.edo', '.entities', '.lit', '.vis', '.rtlights',
            '.bspx', '.lux', '.loc')
LEGACY_ZONES = ('data/maps/zones', 'data/maps/zones/curated', 'data/maps/zones/local',
                'maps/zones', 'maps/zones/curated', 'maps/zones/local')
ZONES = LEGACY_ZONES + ('data/maps/zones/online', 'maps/zones/online',
                        'data/maps/zones/dl', 'maps/zones/dl')
WORLD_DATA_QUERIES = ('maplist.txt', 'common.default.po', 'qwprogs.dat.default.po',
                      'csprogs.dat.default.po', 'menu.dat.default.po', 'progs.dat.default.po',
                      'csqcprogs.dat.default.po', 'fteadd.dat.default.po',
                      'q2bsp.dat.default.po', 'q3bsp.dat.default.po',
                      'doombsp.dat.default.po', 'hlbsp.dat.default.po')
MAP_PROBES = ('%s', 'maps/%s', 'maps/%s.d3dbsp', 'maps/mp/%s.bsp', 'maps/mp/%s.d3dbsp',
              'maps/%s.cm', 'maps/%s.hmp', 'maps/%s.bsp.gz', 'maps/%s.bsp.xz')
DECIMAL = re.compile(r'0|[1-9][0-9]*')
SIGNED = re.compile(r'0|-?[1-9][0-9]*')
SHA = re.compile(r'[0-9a-f]{64}')
HEX = re.compile(r'(?:[0-9a-f]{2})+')


class Invalid(ValueError):
    """Fail closed without echoing an input path, source record or private bytes."""


@dataclass(frozen=True)
class Root:
    kind: int
    path: str


@dataclass(frozen=True)
class Provider:
    id: int
    flags: int
    kind: int
    private: bool
    origin: int
    parent: int
    name: str
    root: str
    logical: str
    purepath: str


@dataclass(frozen=True)
class Entry:
    source: int
    directory: bool
    size: int
    name: str


@dataclass(frozen=True)
class Resolved:
    source: int  # Zero means an explicit native negative query, never a file.
    size: int
    sha256: str
    name: str


@dataclass(frozen=True)
class Input:
    kind: int
    device: int
    inode: int
    links: int
    size: int
    mtime_ns: int
    ctime_ns: int
    path: str


@dataclass(frozen=True)
class Component:
    manifest_sha256: str
    manifest_size: int
    version: int
    world: str
    epoch: int
    puremode: int
    cache: int
    mapmaterials: int
    roots: tuple
    providers: tuple
    pureorder: tuple
    absent_directories: tuple
    entries: tuple
    resolved: tuple
    inputs: tuple
    preparation: bool = False


def _require(value, reason):
    if not value:
        raise Invalid(reason)


def _number(token, bits=64, signed=False):
    _require(len(token) <= 20 and (SIGNED if signed else DECIMAL).fullmatch(token) is not None, 'NUMBER')
    n = int(token)
    _require(-(1 << (bits - 1)) <= n < (1 << (bits - 1)) if signed else 0 <= n < (1 << bits), 'NUMBER_BOUND')
    return n


def _text(token, empty=False):
    if token == '-' and empty:
        return ''
    _require(HEX.fullmatch(token) is not None and len(token) < 2048, 'HEX')
    try:
        value = bytes.fromhex(token).decode('utf-8', 'strict')
    except UnicodeError:
        raise Invalid('ENCODING') from None
    _require(all(ord(c) >= 32 and ord(c) != 127 for c in value), 'TEXT_CONTROL')
    return value


def _absolute(value):
    _require(value.startswith('/') and str(PurePosixPath(value)) == value and
             '..' not in PurePosixPath(value).parts and '\\' not in value, 'ABSOLUTE_PATH')
    return value


def _logical(value, directory=False):
    name = value[:-1] if directory else value
    _require(bool(name) and (not directory or value.endswith('/')) and len(value.encode()) < 1024 and
             name.isascii() and not name.startswith('/') and '\\' not in name and ':' not in name and
             all(p not in ('', '.', '..') for p in name.split('/')), 'LOGICAL_NAME')
    return value


def map_probes(world):
    _logical(world)
    _require(world.startswith('maps/') and world.endswith('.bsp') and world.count('/') == 1 and bool(world[5:-4]), 'WORLD')
    return tuple(pattern % world[5:-4] for pattern in MAP_PROBES)


def negative_probes(world, version=10):
    _require(version in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 'VERSION')
    return (() if version == 1 else map_probes(world)) + (('qwprogs.so',) if version >= 4 else ())


def queries(world, version=10):
    probes = map_probes(world)
    _require(version in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 'VERSION')
    leaf = world[5:-4]
    sidecars = SIDECARS if version >= 2 else tuple(s for s in SIDECARS if s != '.phs')
    zones = ZONES if version >= 3 else LEGACY_ZONES
    base = BASE_QUERIES + (('data/mapdeps.net.txt', 'mapdeps.net.txt', 'qwprogs.qvm',
                            'vm/qagame.qvm', 'vm/cgame.qvm', 'vm/ui.qvm') if version >= 3 else ())
    result = (base + tuple(world[:-4] + suffix for suffix in sidecars) +
              tuple(path + '/' + leaf + '.json' for path in zones) +
              ('cfg/maps/map_' + leaf + '.cfg', 'cfg/maps/entfix_' + leaf + '.cfg'))
    if version >= 3:
        result += ('data/maps/settings/local/' + leaf + '.cfg', 'maps/settings/local/' + leaf + '.cfg')
    if version >= 4:
        result += ('qwprogs.so',)
    if version >= 5:
        result += ('maplist.txt', 'data/maps/tiers.txt', 'maps/tiers.txt',
                   'qwprogs.lno', 'csprogs.lno', 'menu.lno', 'progs.lno', 'csqcprogs.lno')
    if version >= 6:
        result += WORLD_DATA_QUERIES[1:7]
    if version >= 7:
        result += ('fte_bimap.txt',)
    if version >= 8:
        result += ('mod.gam', 'fteadd.dat', 'q2bsp.dat', 'q3bsp.dat', 'doombsp.dat',
                   'hlbsp.dat', 'fteadd.lno', 'q2bsp.lno', 'q3bsp.lno',
                   'doombsp.lno', 'hlbsp.lno') + WORLD_DATA_QUERIES[7:]
    if version >= 9:
        result += ('gibfiltr.cfg',)
    if version >= 10:
        result += ('impfiltr.cfg',)
    return result + probes if version >= 2 else result


def control_queries(world, version=10):
    """Finite Class1 contract, NOT source discovery or winner selection."""
    sidecars = {world[:-4] + suffix for suffix in SIDECARS}
    excluded = sidecars | set(negative_probes(world, version)) | set(WORLD_DATA_QUERIES)
    return tuple(name for name in queries(world, version) if name not in excluded)


def relevant(name, mandatory, directory=False):
    """Native domain, including case variants that must not disappear from census."""
    lower = name.lower()
    return (any(lower.startswith(p) or (directory and p.startswith(lower)) for p in ASSETS) or
            any(q.lower().startswith(lower) if directory else q.lower() == lower for q in mandatory))


def _aliases(entries):
    spellings, files, directories, members = {}, set(), set(), set()
    for item in entries:
        name = item.name.rstrip('/')
        parts = name.split('/')
        for i in range(1, len(parts) + 1):
            path = '/'.join(parts[:i])
            folded = path.lower()
            _require(spellings.setdefault(folded, path) == path, 'CASE_ALIAS')
            if i < len(parts) or item.directory:
                directories.add(folded)
        if not item.directory:
            files.add(name.lower())
        key = (item.source, item.name)
        _require(key not in members, 'DUPLICATE_MEMBER')
        members.add(key)
    _require(not files.intersection(directories), 'FILE_DIRECTORY_ALIAS')


def parse_component(raw, expected_sha256, world):
    """Read exactly one complete frame; its SHA must come from the owned actor ACK.

    This is structural/materialisation data, NOT a fresh source-universe witness.
    Legacy schemas1/2/3/4/5/6/7/8/9 are accepted for archived components only; an authority
    builder must require schema10 AND the full witness, never version alone.
    Epoch is volatile diagnostic state, not a qualification identity.
    """
    return _parse_materialisation(raw, expected_sha256, world, preparation=False)


def parse_preparation(raw, expected_sha256, world):
    """Operator-only static profile data, never a replay component or authority.

    A proven source-reader lease/census must span preparation and validation.
    This role does not supply that transaction or permit registry admission.
    """
    return _parse_materialisation(raw, expected_sha256, world, preparation=True)


def _parse_materialisation(raw, expected_sha256, world, *, preparation):
    purpose = 'profileprep' if preparation else 'component'
    max_files = PREP_MAX_FILES if preparation else MAX_FILES
    max_total = PREP_MAX_TOTAL if preparation else MAX_TOTAL
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_MANIFEST and raw.endswith(b'\n'), 'MANIFEST_BOUND')
    _require(type(expected_sha256) is str and SHA.fullmatch(expected_sha256) is not None and
             hashlib.sha256(raw).hexdigest() == expected_sha256, 'MANIFEST_SHA')
    _require(b'\r' not in raw and b'\0' not in raw, 'MANIFEST_ENCODING')
    def row_iterator():
        offset = 0
        while offset < len(raw):
            end = raw.find(b'\n', offset)
            _require(end >= offset and end - offset + 1 < 16384, 'ROW_BOUND')
            try:
                row = raw[offset:end].decode('ascii', 'strict').split(' ')
            except UnicodeError:
                raise Invalid('MANIFEST_ENCODING') from None
            _require(all(row), 'MANIFEST_GRAMMAR')
            offset = end + 1
            yield row

    rows = iter(row_iterator())
    current = next(rows, None)

    def take(tag, count):
        nonlocal current
        _require(current is not None and current[0] == tag and len(current) == count, 'ROW_' + tag)
        row, current = current, next(rows, None)
        return row

    def next_is(tag):
        return current is not None and current[0] == tag

    h = take('TASVFSEXPORT', 9)
    _require(h[1] in (('10',) if preparation else ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10')) and
             h[2] == purpose and _text(h[8]) == world, 'HEADER')
    version = int(h[1])
    epoch, pathcount = _number(h[3], 32), _number(h[4], 32)
    _require(0 < pathcount <= 128, 'PROVIDER_BOUND')
    settings = tuple(_number(v, 32, signed=True) for v in h[5:8])
    mandatory = queries(world, version)
    roots = []
    while next_is('ROOT'):
        r = take('ROOT', 4)
        _require(_number(r[1], 32) == len(roots) + 1 and len(roots) < 64, 'ROOT_ORDER')
        kind = _number(r[2], 32)
        _require(kind in (1, 2, 3), 'ROOT_KIND')
        roots.append(Root(kind, _absolute(_text(r[3]))))
    _require(bool(roots) and len({r.path for r in roots}) == len(roots), 'ROOT_SET')
    providers = []
    origins = set()
    for source in range(1, pathcount + 1):
        r = take('SOURCE', 10)
        pid, flags, kind, bound, private = (_number(v, 32) for v in r[1:6])
        origin, parent = (_number(v) for v in r[6:8])
        _require(pid == source and kind in (1, 2, 3, 4) and bound == 1 and private in (0, 1) and
                 origin != 0 and origin not in origins and origin != parent, 'PROVIDER')
        origins.add(origin)
        name, root = _text(r[8], True), _text(r[9], True)
        _require(bool(name) and (kind != 1 or bool(root)), 'PROVENANCE')
        if root:
            _absolute(root)
        logical = take('PATH', 3)
        purepath = take('PUREPATH', 3)
        _require(_number(logical[1], 32) == source and _number(purepath[1], 32) == source, 'PROVIDER_PATH')
        providers.append(Provider(pid, flags, kind, bool(private), origin, parent, name, root,
                                  _text(logical[2], True), _text(purepath[2], True)))
    # Active parents may be absent only if a future full witness independently
    # binds the retired constructor chain. Do not silently accept an orphan here.
    _require(all(p.parent == 0 or p.parent in origins for p in providers), 'ORIGIN_PARENT')
    pureorder = []
    while next_is('PUREORDER'):
        r = take('PUREORDER', 3)
        sequence, source = (_number(v, 32) for v in r[1:])
        _require(sequence == len(pureorder) + 1 and 1 <= source <= pathcount and source not in pureorder, 'PURE_ORDER')
        pureorder.append(source)
    absent = []
    while next_is('DIRECTORY_ABSENT'):
        source = _number(take('DIRECTORY_ABSENT', 2)[1], 32)
        _require(1 <= source <= pathcount and providers[source - 1].kind == 1 and source not in absent, 'DIRECTORY_ABSENT')
        absent.append(source)
    entries, resolved, seen_names, namebytes = [], [], set(), 0
    previous = None
    while next_is('ENTRY'):
        r = take('ENTRY', 5)
        source, directory, size = _number(r[1], 32), _number(r[2], 32), _number(r[3])
        _require(source <= pathcount and directory in (0, 1) and source not in absent, 'ENTRY')
        name = _logical(_text(r[4]), bool(directory))
        _require(relevant(name, mandatory, bool(directory)), 'ENTRY_DOMAIN')
        if source == 0:
            _require(not directory and size == 0 and name in mandatory, 'QUERY_ENTRY')
        # Native Q_strcasecmp folds ASCII to UPPER, including punctuation order.
        key = (name.upper(), name, source)
        _require(previous is None or previous < key, 'ENTRY_ORDER')
        previous = key
        namebytes += len(name) + 1
        _require(len(entries) < MAX_RECORDS and namebytes <= MAX_NAMES, 'NAMESPACE_BOUND')
        entries.append(Entry(source, bool(directory), size, name))
        if directory or name in seen_names:
            continue
        seen_names.add(name)
        if next_is('MISSING'):
            result = take('MISSING', 2)
            _require(_text(result[1]) == name and name in mandatory, 'MISSING')
            resolved.append(Resolved(0, 0, '', name))
        else:
            result = take('FILE', 5)
            selected, length = _number(result[1], 32), _number(result[2])
            _require(1 <= selected <= pathcount and selected not in absent and length <= MAX_FILE and
                     SHA.fullmatch(result[3]) is not None and _text(result[4]) == name, 'FILE')
            resolved.append(Resolved(selected, length, result[3], name))
    _aliases(entries)
    _require({e.name for e in entries if e.source == 0} == set(mandatory), 'QUERY_SET')
    positive_entries = {(e.source, e.name) for e in entries if e.source and not e.directory}
    present_names = {name for _, name in positive_entries}
    for result in resolved:
        _require((result.source, result.name) in positive_entries if result.source else result.name not in present_names,
                 'RESOLUTION_COVERAGE')
    if version >= 2:
        probes = set(negative_probes(world, version))
        _require(all(not r.source for r in resolved if r.name in probes), 'PROBE_PRESENT')
    inputs, input_paths = [], set()
    while next_is('INPUT'):
        r = take('INPUT', 12)
        sequence, kind = _number(r[1], 32), _number(r[2], 32)
        device, inode, links, size = (_number(v) for v in r[3:7])
        mt, mn, ct, cn = _number(r[7], signed=True), _number(r[8], 32), _number(r[9], signed=True), _number(r[10], 32)
        path = _absolute(_text(r[11]))
        _require(sequence == len(inputs) + 1 and len(inputs) < 4096 and kind in (1, 2, 3) and
                 links == 1 and mn < 1000000000 and cn < 1000000000 and path not in input_paths, 'INPUT')
        input_paths.add(path)
        inputs.append(Input(kind, device, inode, links, size, mt * 1000000000 + mn, ct * 1000000000 + cn, path))
    end = take('END', 6)
    _require(end[1] == purpose and current is None, 'END')
    files, missing, records, total = (_number(v) for v in end[2:])
    positives = [r for r in resolved if r.source]
    _require(0 < files == len(positives) <= max_files and missing == len(resolved) - files and
             records == len(entries) and total == sum(r.size for r in positives) <= max_total and bool(inputs), 'COUNTS')
    return Component(expected_sha256, len(raw), version, world, epoch, *settings, tuple(roots), tuple(providers),
                     tuple(pureorder), tuple(absent), tuple(entries), tuple(resolved), tuple(inputs), preparation=preparation)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def validate_flat(component, root):
    """Exact flat output bytes/types under caller-held custody/source transaction.

    POSIX-only no-follow opens. This does not substitute for a backing census or
    make the canonical source snapshot atomic; the caller supplies that lifetime.
    """
    _require(isinstance(component, Component), 'COMPONENT')
    _require(os.name == 'posix' and all(hasattr(os, x) for x in ('O_NOFOLLOW', 'O_NONBLOCK', 'O_DIRECTORY')), 'PLATFORM')
    path = os.fspath(root)
    _absolute(path)
    _require(os.path.realpath(path) == path, 'FLAT_ROOT')
    files = {r.name: (r.size, r.sha256) for r in component.resolved if r.source}
    files['index.txt'] = (component.manifest_size, component.manifest_sha256)
    directories = set()
    for name in files:
        parts = name.split('/')
        directories.update('/'.join(parts[:i]) for i in range(1, len(parts)))
    seen = set()

    def walk(fd, relative, depth):
        _require(depth <= 64, 'FLAT_DEPTH')
        before = os.fstat(fd)
        for leaf in sorted(os.listdir(fd)):
            name = relative + leaf
            info = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                _require(name in directories, 'FLAT_DIRECTORY_SET')
                child = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY, dir_fd=fd)
                try:
                    _require(_identity(os.fstat(child)) == _identity(info), 'FLAT_CHANGED')
                    walk(child, name + '/', depth + 1)
                finally:
                    os.close(child)
            else:
                _require(name in files and stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'FLAT_FILE_SET')
                size, digest = files[name]
                _require(info.st_size == size, 'FLAT_SIZE')
                child = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    _require(_identity(os.fstat(child)) == _identity(info), 'FLAT_CHANGED')
                    hash_state, count = hashlib.sha256(), 0
                    while True:
                        data = os.read(child, min(65536, size + 1 - count))
                        if not data:
                            break
                        hash_state.update(data)
                        count += len(data)
                        _require(count <= size, 'FLAT_LENGTH')
                    _require(count == size and hash_state.hexdigest() == digest and
                             _identity(os.fstat(child)) == _identity(info), 'FLAT_BYTES')
                finally:
                    os.close(child)
                seen.add(name)
        _require(_identity(os.fstat(fd)) == _identity(before), 'FLAT_CHANGED')

    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
    try:
        walk(fd, '', 0)
    finally:
        os.close(fd)
    _require(seen == set(files), 'FLAT_EXACT_SET')
