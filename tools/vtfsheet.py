"""Bounded VTF particle-sheet metadata reader; does not decode image pixels.

VTF resource 0x10 holds a length-prefixed sheet, not VTF image frames. Versions
0/1 contain one/four UV rectangles per sample. Flags remain raw: interpreting
loop/clamp and selecting a channel belongs to the consumer, not the decoder.
"""
import math
import struct


class SheetError(ValueError):
    pass


def read_sheet(data):
    """Return sheet metadata or None for a valid header without a sheet."""
    if len(data) < 64 or data[:4] != b'VTF\0':
        raise SheetError('not a complete VTF header')
    major, minor, header = struct.unpack_from('<III', data, 4)
    if major != 7 or not 0 <= minor <= 6:
        raise SheetError('unsupported VTF version')
    minimum = 80 if minor >= 3 else (80 if minor == 2 else 64)
    if not minimum <= header <= len(data):
        raise SheetError('invalid VTF header size')
    if minor < 3:
        return None
    count = struct.unpack_from('<I', data, 68)[0]
    if count > 32 or 80 + count * 8 > header:
        raise SheetError('invalid resource directory size')
    entries = [struct.unpack_from('<3sBI', data, 80 + i * 8) for i in range(count)]
    if len({e[0] for e in entries}) != count:
        raise SheetError('duplicate resource tag')
    external = []
    for tag, flags, offset in entries:
        if flags & ~2:
            raise SheetError('unsupported resource flags')
        if not flags & 2:
            if not header <= offset < len(data):
                raise SheetError('resource offset outside payload')
            external.append(offset)
    if len(set(external)) != len(external):
        raise SheetError('overlapping resource offsets')
    sheets = [e for e in entries if e[0] == b'\x10\0\0']
    if not sheets:
        return None
    _, flags, offset = sheets[0]
    if flags or offset + 4 > len(data):
        raise SheetError('invalid external sheet resource')
    size = struct.unpack_from('<I', data, offset)[0]
    end = offset + 4 + size
    following = min((o for o in external if o > offset), default=len(data))
    if size < 8 or end > following:
        raise SheetError('sheet length crosses resource bounds')
    sheet = memoryview(data)[offset + 4:end]
    version, nseq = struct.unpack_from('<II', sheet)
    if version not in (0, 1) or not 1 <= nseq <= 64:
        raise SheetError('unsupported/empty sheet')
    pos, sequences = 8, {}
    for _ in range(nseq):
        if pos + 16 > len(sheet):
            raise SheetError('truncated sequence header')
        index, flags, count, total = struct.unpack_from('<IIIf', sheet, pos)
        pos += 16
        if index >= 64 or index in sequences or not 1 <= count <= 4096:
            raise SheetError('invalid sequence index/count')
        if not math.isfinite(total) or not 0 < total <= 1e6:
            raise SheetError('invalid total duration')
        channels = 1 if version == 0 else 4
        stride = 4 + channels * 16
        if pos + count * stride > len(sheet):
            raise SheetError('truncated frame table')
        frames = []
        for _ in range(count):
            duration = struct.unpack_from('<f', sheet, pos)[0]
            if not math.isfinite(duration) or duration <= 0:
                raise SheetError('invalid frame duration')
            uv = [list(struct.unpack_from('<4f', sheet, pos + 4 + j * 16))
                  for j in range(channels)]
            for left, top, right, bottom in uv:
                if not all(math.isfinite(x) for x in (left, top, right, bottom)):
                    raise SheetError('nonfinite frame UV')
                if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
                    raise SheetError('invalid frame UV rectangle')
            if version == 0:
                uv = [list(uv[0]) for _ in range(4)]
            frames.append(dict(duration=duration, uv=uv))
            pos += stride
        if not math.isclose(math.fsum(f['duration'] for f in frames), total,
                            rel_tol=1e-5, abs_tol=1e-5):
            raise SheetError('duration sum mismatch')
        sequences[index] = dict(flags_raw=flags, duration=total, frames=frames)
    if pos != len(sheet):
        raise SheetError('unconsumed sheet bytes')
    return dict(version=version, sequences=sequences)
