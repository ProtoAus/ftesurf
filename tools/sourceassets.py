"""Explicit, ordered Source asset sources for offline particle planning.

No Steam discovery or fallback mounting. Sources are highest-priority first;
BSP pak precedes caller-supplied content. A malformed selected file is an error,
not permission to fall through to another pack. Reads bind payload SHA256/CRC.
"""
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import re
import struct
import zipfile
import zlib

MAX_FILE = 256 * 1024 * 1024


class ResourceError(ValueError):
    pass


def asset_path(value):
    if not isinstance(value, str):
        raise ResourceError('asset path must be a string')
    value = value.replace('\\', '/').lower()
    if not value or any(p in ('', '.', '..') for p in value.split('/')):
        raise ResourceError('invalid relative asset path: ' + repr(value))
    if ':' in value or any(ord(c) < 32 for c in value):
        raise ResourceError('invalid asset path: ' + repr(value))
    return value


def material_path(value, suffix='.vmt'):
    value = asset_path(value)
    if not value.startswith('materials/'):
        value = 'materials/' + value
    if value.endswith(('.vmt', '.vtf')):
        value = value[:-4]
    return value + suffix


@dataclass(frozen=True)
class Asset:
    path: str
    source: str
    data: bytes

    def provenance(self):
        return dict(path=self.path, source=self.source, bytes=len(self.data),
                    sha256=hashlib.sha256(self.data).hexdigest())


class VpkSource:
    def __init__(self, path):
        self.path = Path(path)
        self.entries = {}
        with self.path.open('rb') as stream:
            head = stream.read(28)
            if len(head) < 12:
                raise ResourceError('truncated VPK header')
            sig, version, size = struct.unpack_from('<III', head)
            if sig != 0x55AA1234 or version not in (1, 2):
                raise ResourceError('unsupported VPK header')
            header = 12 if version == 1 else 28
            if len(head) < header or size > MAX_FILE:
                raise ResourceError('invalid VPK tree size/header')
            self.database = header + size
            if version == 2:
                self.inline_size = struct.unpack_from('<I', head, 12)[0]
            else:
                self.inline_size = self.path.stat().st_size - self.database
            if self.inline_size < 0 or self.database + self.inline_size > self.path.stat().st_size:
                raise ResourceError('truncated VPK inline payload')
            stream.seek(header)
            tree = stream.read(size)
        if len(tree) != size:
            raise ResourceError('truncated VPK tree')
        pos = 0

        def cstr():
            nonlocal pos
            end = tree.find(b'\0', pos)
            if end < 0:
                raise ResourceError('unterminated VPK tree string')
            text = tree[pos:end].decode('latin-1')
            pos = end + 1
            return text

        while True:
            ext = cstr()
            if not ext:
                break
            while True:
                folder = cstr()
                if not folder:
                    break
                while True:
                    name = cstr()
                    if not name:
                        break
                    if pos + 18 > size:
                        raise ResourceError('truncated VPK entry')
                    crc, preload, archive, offset, length, term = struct.unpack_from('<IHHIIH', tree, pos)
                    pos += 18
                    if term != 0xffff or pos + preload > size or length + preload > MAX_FILE:
                        raise ResourceError('invalid VPK entry/preload')
                    pre = tree[pos:pos + preload]
                    pos += preload
                    key = asset_path((name if folder == ' ' else folder + '/' + name) + '.' + ext)
                    if key in self.entries:
                        raise ResourceError('duplicate VPK path: ' + key)
                    if archive == 0x7fff and offset + length > self.inline_size:
                        raise ResourceError('VPK entry crosses inline payload bounds')
                    self.entries[key] = crc, archive, offset, length, pre
        if pos != size:
            raise ResourceError('unconsumed VPK tree bytes')

    def read(self, key):
        crc, archive, offset, length, pre = self.entries[key]
        if archive == 0x7fff:
            path, base = self.path, self.database
        else:
            if not self.path.name.lower().endswith('_dir.vpk'):
                raise ResourceError('split VPK requires _dir.vpk name')
            path = self.path.with_name(self.path.name[:-8] + '_%03d.vpk' % archive)
            base = 0
        data = pre
        if length:
            with path.open('rb') as stream:
                stream.seek(base + offset)
                data += stream.read(length)
        if len(data) != length + len(pre) or zlib.crc32(data) != crc:
            raise ResourceError('VPK length/CRC mismatch: ' + key)
        return Asset(key, str(self.path), data)


class DirectorySource:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_dir():
            raise ResourceError('not a content directory: ' + str(path))
        self.entries = {}
        for sub in ('particles', 'materials'):
            for file in sorted((self.path / sub).rglob('*')):
                if not file.is_file():
                    continue
                if not file.resolve().is_relative_to(self.path.resolve()):
                    raise ResourceError('content symlink escapes root: ' + str(file))
                key = asset_path(file.relative_to(self.path).as_posix())
                if key in self.entries:
                    raise ResourceError('case-colliding loose path: ' + key)
                self.entries[key] = file
        self.vpks = [VpkSource(file) for file in sorted(self.path.glob('*_dir.vpk'))]
        self._paths = set(self.entries).union(*(set(v.entries) for v in self.vpks))

    def paths(self):
        return self._paths

    def read(self, key):
        if key in self.entries:
            file = self.entries[key]
            if file.stat().st_size > MAX_FILE:
                raise ResourceError('asset exceeds size limit: ' + key)
            return Asset(key, str(file), file.read_bytes())
        hits = [v for v in self.vpks if key in v.entries]
        if len(hits) != 1:
            raise ResourceError('ambiguous VPK path within content root: ' + key)
        return hits[0].read(key)


class BspSource:
    def __init__(self, path):
        self.path = Path(path)
        self.entries, self.zip, self.issues = {}, None, []
        with self.path.open('rb') as stream:
            head = stream.read(8 + 64 * 16)
            if len(head) != 8 + 64 * 16 or head[:4] != b'VBSP':
                raise ResourceError('not a complete VBSP header')
            offset, size, _version, compressed = struct.unpack_from('<4i', head, 8 + 40 * 16)
            if size == 0:
                return
            if compressed or size < 0 or offset < len(head) or size > MAX_FILE:
                raise ResourceError('invalid/unsupported BSP pak lump')
            stream.seek(offset)
            raw = stream.read(size)
        if len(raw) != size:
            raise ResourceError('truncated BSP pak lump')
        try:
            self.zip = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as error:
            raise ResourceError('invalid BSP pak ZIP: ' + str(error)) from error
        for entry in self.zip.infolist():
            if entry.is_dir():
                continue
            try:
                key = asset_path(entry.filename)
            except ResourceError as error:
                if entry.filename.lower().endswith('.pcf'):
                    raise ResourceError('unsafe PCF archive path: ' + entry.filename) from error
                self.issues.append(dict(source=str(self.path), error=str(error), selected=False))
                continue
            if key in self.entries:
                self.issues.append(dict(source=str(self.path), path=key,
                                        error='duplicate BSP pak path; lookup will refuse ambiguity'))
            self.entries.setdefault(key, []).append(entry)

    def read(self, key):
        entries = self.entries[key]
        if len(entries) != 1:
            raise ResourceError('duplicate BSP pak path: ' + key)
        entry = entries[0]
        if entry.file_size > MAX_FILE:
            raise ResourceError('BSP asset exceeds size limit: ' + key)
        try:
            return Asset(key, str(self.path) + ':pak', self.zip.read(entry))
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
            raise ResourceError('unreadable BSP pak member %s: %s' % (key, error)) from error

    def close(self):
        if self.zip:
            self.zip.close()


class Content:
    def __init__(self, sources):
        self.sources = sources
        self.issues = [issue for source in sources for issue in getattr(source, 'issues', [])]

    def paths(self):
        return sorted(set().union(*(s.paths() if isinstance(s, DirectorySource)
                                   else set(s.entries) for s in self.sources)))

    def read(self, path):
        key = asset_path(path)
        for source in self.sources:
            keys = source.paths() if isinstance(source, DirectorySource) else source.entries
            if key in keys:
                return source.read(key)
        raise ResourceError('missing asset: ' + key)


def content_source(path):
    return DirectorySource(path) if Path(path).is_dir() else VpkSource(path)


_TOKEN = re.compile(r'\s+|//[^\r\n]*|"([^"\r\n]*)"|([{}])|([^\s{}"]+)')


def keyvalues(data):
    """Strict subset: blocks, quoted/bare tokens, // comments; no conditionals."""
    text = data.decode('utf-8-sig') if data.startswith(b'\xef\xbb\xbf') else data.decode('latin-1')
    tokens, pos = [], 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match:
            raise ResourceError('invalid VMT token at %d' % pos)
        pos = match.end()
        if match[1] is not None or match[2] or match[3]:
            value = match[1] if match[1] is not None else (match[2] or match[3])
            if '[' in value or ']' in value:
                raise ResourceError('conditional VMT syntax unsupported')
            tokens.append(value)
    cursor = 0

    def block(depth):
        nonlocal cursor
        if depth > 16:
            raise ResourceError('VMT nesting limit')
        result = {}
        while cursor < len(tokens) and tokens[cursor] != '}':
            key = tokens[cursor].lower()
            cursor += 1
            if key == '{' or cursor >= len(tokens) or key in result:
                raise ResourceError('invalid/duplicate VMT key: ' + key)
            value = tokens[cursor]
            cursor += 1
            if value == '{':
                value = block(depth + 1)
            elif value == '}':
                raise ResourceError('missing VMT value')
            result[key] = value
        if cursor >= len(tokens):
            raise ResourceError('unclosed VMT block')
        cursor += 1
        return result

    if len(tokens) < 3 or tokens[1] != '{':
        raise ResourceError('missing VMT shader/block')
    shader, cursor = tokens[0].lower(), 2
    params = block(0)
    if cursor != len(tokens):
        raise ResourceError('unconsumed VMT tokens')
    return shader, params


def resolve_vmt(content, path, stack=()):
    path = material_path(path)
    if path in stack or len(stack) >= 16:
        raise ResourceError('VMT include cycle/depth: ' + path)
    asset = content.read(path)
    shader, params = keyvalues(asset.data)
    origins = [asset.provenance()]
    if shader != 'patch':
        if 'include' in params:
            raise ResourceError('include outside Patch unsupported: ' + path)
        return shader, params, origins
    if not isinstance(params.get('include'), str) or set(params) - {'include', 'insert', 'replace'}:
        raise ResourceError('unsupported VMT Patch structure: ' + path)
    shader, inherited, parents = resolve_vmt(content, params['include'], stack + (path,))
    effective = dict(inherited)
    for operation in ('insert', 'replace'):
        changes = params.get(operation, {})
        if not isinstance(changes, dict) or any(isinstance(v, dict) for v in changes.values()):
            raise ResourceError('nested VMT Patch changes unsupported: ' + path)
        for key, value in changes.items():
            # SDK materialpatch.cpp: insert overwrites unconditionally;
            # replace sets only existing keys (despite the surprising names).
            if operation == 'insert' or key in effective:
                effective[key] = value
    return shader, effective, origins + parents
