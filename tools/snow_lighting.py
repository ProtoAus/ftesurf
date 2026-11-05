"""Offline Source face-light sampling for static snow; no runtime traces/readbacks.
Follow native Strata/legacy layouts and RGBExp32 first-style samples. The IQM
stores linear normalized RGB; missing samples use restrained ambient, not white.
"""
import struct
import numpy as np


class FaceLights:
    def __init__(self, bsp):
        self.wide = bsp.version >= 25
        hdr = bsp.lump(53)[0]
        self.data = hdr or bsp.lump(8)[0]
        self.faces = (bsp.lump(58)[0] if hdr else bsp.lump(7)[0])
        self.texinfo = bsp.lump(6)[0]
        self.stride = 72 if self.wide else 56
        if not self.data or len(self.faces) % self.stride:
            raise ValueError('snow lighting requires complete actual face/light data')
        self.cache = {}
        self.sampled = self.ambient = 0
        self.source = 'HDR RGBExp32' if hdr else 'LDR RGBExp32'

    def face(self, index):
        if index in self.cache:
            return self.cache[index]
        at = index * self.stride
        if not 0 <= at <= len(self.faces) - self.stride:
            raise ValueError('snow light face outside lump')
        ti = struct.unpack_from('<i' if self.wide else '<h', self.faces, at + (16 if self.wide else 10))[0]
        offset = struct.unpack_from('<i', self.faces, at + (32 if self.wide else 20))[0]
        mins = np.asarray(struct.unpack_from('<2i', self.faces, at + (40 if self.wide else 28)))
        size = np.asarray(struct.unpack_from('<2i', self.faces, at + (48 if self.wide else 36))) + 1
        styles = self.faces[at + (28 if self.wide else 16):at + (32 if self.wide else 20)]
        if offset < 0 or styles[0] == 255:
            result = None
        else:
            if ti < 0 or (ti + 1) * 72 > len(self.texinfo) or np.any(size <= 0) or np.any(size > 4096):
                raise ValueError('invalid snow lightmap dimensions/texinfo')
            length = int(size.prod()) * 4
            if offset + length > len(self.data):
                raise ValueError('snow lightmap outside actual light data')
            raw = np.frombuffer(self.data, np.uint8, count=length, offset=offset).reshape(int(size[1]), int(size[0]), 4)
            exponent = raw[:, :, 3].astype(np.int8).astype(float)
            pixels = raw[:, :, :3].astype(float) * np.exp2(exponent[:, :, None]) / 255.0
            vec = np.asarray(struct.unpack_from('<8f', self.texinfo, ti * 72 + 32)).reshape(2, 4)
            if not np.isfinite(vec).all():
                raise ValueError('nonfinite snow light vectors')
            result = (pixels, vec, mins, size)
        self.cache[index] = result
        return result

    def sample(self, index, point):
        data = self.face(index)
        if data is None:
            self.ambient += 1
            return np.full(3, .28)
        pixels, vec, mins, size = data
        xy = np.clip(vec[:, :3] @ np.asarray(point) + vec[:, 3] - mins, 0, size - 1)
        lo = np.floor(xy).astype(int); hi = np.minimum(lo + 1, size - 1); mix = xy - lo
        a = pixels[lo[1], lo[0]] * (1 - mix[0]) + pixels[lo[1], hi[0]] * mix[0]
        b = pixels[hi[1], lo[0]] * (1 - mix[0]) + pixels[hi[1], hi[0]] * mix[0]
        self.sampled += 1
        return np.clip(a * (1 - mix[1]) + b * mix[1], .035, 1)
