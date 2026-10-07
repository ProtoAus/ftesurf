#!/usr/bin/env python3
"""Make an extruded Impact ERROR MD3/OBJ from a locally licensed font.

Generator-only dependencies: fonttools, shapely, mapbox-earcut, numpy. The game
needs none of them, and the font file itself is never copied/embedded. Example:
    python tools/make_error_model.py --font C:/Windows/Fonts/impact.ttf \
        --out ftesurf/models/missing_error.md3 \
        --palette ftesurf/gfx/env/missing_error_palette.png --obj /private/preview.obj

Front is +X, text reads left-to-right along +Y, baseline Z=0. Default 24-unit
cap height, 4-unit depth. Four small additive outline rings provide a red halo
without post-process bloom; matching materials are scripts/missing_assets.shader.
This creates a MODEL ASSET, not an engine missing-model/collision replacement.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

import mapbox_earcut
import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from shapely import affinity
from shapely.geometry import Polygon
from shapely.ops import unary_union


class OutlinePen(BasePen):
    def __init__(self, glyphs, tolerance):
        super().__init__(glyphs)
        self.tolerance = tolerance
        self.contours, self.points = [], []

    def _moveTo(self, p):
        self.points = [p]

    def _lineTo(self, p):
        self.points.append(p)

    def _curveToOne(self, a, b, end):
        start = self._getCurrentPoint()
        # Sample a cubic with a bounded subdivision count from control length.
        length = sum(math.dist(p, q) for p, q in [(start, a), (a, b), (b, end)])
        n = min(128, max(4, math.ceil(length / self.tolerance)))
        for i in range(1, n + 1):
            t, u = i / n, 1 - i / n
            self.points.append(tuple(u**3*start[j] + 3*u*u*t*a[j] + 3*u*t*t*b[j] + t**3*end[j] for j in (0, 1)))

    def _qCurveToOne(self, control, end):
        start = self._getCurrentPoint()
        n = min(128, max(4, math.ceil((math.dist(start, control) + math.dist(control, end)) / self.tolerance)))
        for i in range(1, n + 1):
            t, u = i / n, 1 - i / n
            self.points.append(tuple(u*u*start[j] + 2*u*t*control[j] + t*t*end[j] for j in (0, 1)))

    def _closePath(self):
        if len(self.points) > 2:
            if self.points[-1] == self.points[0]:
                self.points.pop()
            self.contours.append(self.points)
        self.points = []

    def _endPath(self):
        self._closePath()


def polygons(shape):
    if shape.is_empty:
        return []
    if shape.geom_type == 'Polygon':
        return [shape]
    if shape.geom_type == 'MultiPolygon':
        return list(shape.geoms)
    raise ValueError('unexpected outline geometry: ' + shape.geom_type)


def text_shape(font, height):
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    contours, x = [], 0
    for letter in 'ERROR':
        name = cmap[ord(letter)]
        pen = OutlinePen(glyphs, font['head'].unitsPerEm / 80)
        glyphs[name].draw(pen)
        contours += [Polygon([(px + x, py) for px, py in c]) for c in pen.contours]
        x += font['hmtx'][name][0]
    if not contours or any(not p.is_valid or p.area <= 0 for p in contours):
        raise ValueError('invalid font contours')
    # Font contours are non-overlapping except nesting. Containment parity
    # retains the counters in R/O rather than filling them with cap triangles.
    shells = []
    for contour in contours:
        parents = [p for p in contours if p != contour and p.contains(contour)]
        if len(parents) % 2:
            continue
        holes = [p.exterior.coords for p in contours if contour.contains(p)
                 and sum(q.contains(p) for q in contours if q != p) == len(parents) + 1]
        shells.append(Polygon(contour.exterior.coords, holes))
    shape = unary_union(shells)
    lo_x, lo_y, hi_x, hi_y = shape.bounds
    shape = affinity.translate(shape, xoff=-(lo_x + hi_x) / 2, yoff=-lo_y)
    shape = affinity.scale(shape, xfact=height/(hi_y-lo_y), yfact=height/(hi_y-lo_y), origin=(0, 0))
    shape = shape.simplify(.025, preserve_topology=True)
    if not shape.is_valid:
        raise ValueError('invalid combined text outline')
    return shape


class Surface:
    def __init__(self, name, shader):
        self.name, self.shader = name, shader
        self.vertices, self.normals, self.triangles = [], [], []
        self.quantized_degenerates_pruned = 0

    def triangle(self, points):
        # Per-triangle vertices keep cap/side normals independent.
        a, b, c = (np.array(p, dtype=float) for p in points)
        normal = np.cross(b-a, c-a)
        magnitude = np.linalg.norm(normal)
        if magnitude < 1e-8:
            raise ValueError('degenerate geometry triangle')
        normal /= magnitude
        base = len(self.vertices)
        self.vertices.extend(points)
        self.normals.extend([tuple(normal)]*3)
        self.triangles.append((base, base+1, base+2))

    def compact(self):
        unique, vertices, normals, remap = {}, [], [], []
        for vertex, normal in zip(self.vertices, self.normals):
            key = tuple(round(x, 7) for x in vertex + normal)
            if key not in unique:
                unique[key] = len(vertices)
                vertices.append(vertex)
                normals.append(normal)
            remap.append(unique[key])
        self.vertices, self.normals = vertices, normals
        self.triangles = [tuple(remap[i] for i in t) for t in self.triangles]
        quantized = [np.array([round(x*64) for x in v], dtype=np.int64) for v in vertices]
        valid = [t for t in self.triangles if np.any(np.cross(quantized[t[1]]-quantized[t[0]],
                                                             quantized[t[2]]-quantized[t[0]]))]
        self.quantized_degenerates_pruned = len(self.triangles)-len(valid)
        self.triangles = valid


def caps(surface, shape, plane, reverse=False):
    for polygon in polygons(shape):
        rings = [list(polygon.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in polygon.interiors]
        points = np.array([p for ring in rings for p in ring], dtype=np.float64)
        ends = np.cumsum([len(r) for r in rings], dtype=np.uint32)
        triangles = mapbox_earcut.triangulate_float64(points, ends).reshape(-1, 3)
        # Falsifier: triangulation must cover exactly the polygon incl. holes.
        area = sum(Polygon(points[t]).area for t in triangles)
        if not math.isclose(area, polygon.area, rel_tol=1e-7, abs_tol=1e-7):
            raise ValueError('cap triangulation loses/fills outline area')
        for indices in triangles:
            pts = [(plane, points[i][0], points[i][1]) for i in indices]
            cross = np.cross(np.array(pts[1])-pts[0], np.array(pts[2])-pts[0])[0]
            if (cross > 0) == reverse:
                pts.reverse()
            surface.triangle(pts)


def model(shape, depth):
    front = Surface('letters', 'missing_error_face')
    sides = Surface('extrusion', 'missing_error_side')
    caps(front, shape, depth/2)
    caps(front, shape, -depth/2, reverse=True)
    for polygon in polygons(shape):
        for ring in [polygon.exterior] + list(polygon.interiors):
            points = list(ring.coords)
            for a, b in zip(points, points[1:]):
                quad = [(depth/2, a[0], a[1]), (-depth/2, a[0], a[1]),
                        (-depth/2, b[0], b[1]), (depth/2, b[0], b[1])]
                sides.triangle([quad[0], quad[1], quad[2]])
                sides.triangle([quad[0], quad[2], quad[3]])
    surfaces = [front, sides]
    previous = shape
    for i, radius in enumerate((.25, .5, .8, 1.2)):
        expanded = shape.buffer(radius, quad_segs=3)
        ring = expanded.difference(previous).simplify(.01, preserve_topology=True)
        halo = Surface('halo%d' % i, 'missing_error_halo')
        caps(halo, ring, depth/2+.125)
        caps(halo, ring, -depth/2-.125, reverse=True)
        surfaces.append(halo)
        previous = expanded
    for surface in surfaces:
        surface.compact()
        if len(surface.vertices) > 4096 or len(surface.triangles) > 8192:
            raise ValueError('MD3 surface limit exceeded: ' + surface.name)
    return surfaces


def cstr(value, size):
    data = value.encode('ascii')
    if len(data) >= size:
        raise ValueError('MD3 string too long')
    return data.ljust(size, b'\0')


def write_md3(path, surfaces):
    chunks = []
    vertices = [v for s in surfaces for v in s.vertices]
    mins = [min(v[i] for v in vertices) for i in range(3)]
    maxs = [max(v[i] for v in vertices) for i in range(3)]
    radius = max(math.sqrt(sum(x*x for x in v)) for v in vertices)
    frame = struct.pack('<10f16s', *mins, *maxs, 0, 0, 0, radius, cstr('ERROR', 16))
    for surface in surfaces:
        triangles = b''.join(struct.pack('<3i', *t) for t in surface.triangles)
        shader = struct.pack('<64si', cstr(surface.shader, 64), 0)
        # Solid palette texels keep alias GPU vertex-color handling irrelevant.
        # Halos share one shader/texture, so there is no per-ring material cost.
        palette_index = {'letters': 0, 'extrusion': 1}.get(surface.name)
        if palette_index is None:
            palette_index = 2 + int(surface.name[4:])
        st = struct.pack('<2f', (palette_index+.5)/8, .5) * len(surface.vertices)
        xyz = bytearray()
        for vertex, normal in zip(surface.vertices, surface.normals):
            point = [round(x*64) for x in vertex]
            if any(not -32768 <= x <= 32767 for x in point):
                raise ValueError('MD3 coordinate overflow')
            lat = round(math.atan2(normal[1], normal[0]) * 255/(2*math.pi)) & 255
            lng = round(math.acos(max(-1, min(1, normal[2]))) * 255/(2*math.pi)) & 255
            xyz += struct.pack('<3hH', *point, (lat << 8) | lng)
        ot, osh, ost, ox = 108, 108+len(triangles), 108+len(triangles)+len(shader), 108+len(triangles)+len(shader)+len(st)
        end = ox+len(xyz)
        head = struct.pack('<4s64s10i', b'IDP3', cstr(surface.name, 64), 0, 1, 1,
                           len(surface.vertices), len(surface.triangles), ot, osh, ost, ox, end)
        chunks.append(head+triangles+shader+st+xyz)
    end = 108+len(frame)+sum(map(len, chunks))
    header = struct.pack('<4si64s9i', b'IDP3', 15, cstr('missing_error', 64), 0, 1, 0,
                         len(surfaces), 0, 108, 108+len(frame), 108+len(frame), end)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header+frame+b''.join(chunks))
    return dict(bytes=end, surfaces=len(surfaces), vertices=sum(len(s.vertices) for s in surfaces),
                triangles=sum(len(s.triangles) for s in surfaces), mins=mins, maxs=maxs,
                quantized_degenerates_pruned=sum(s.quantized_degenerates_pruned for s in surfaces),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def write_obj(path, surfaces):
    lines = ['# Impact ERROR mesh; same axes/scale as missing_error.md3']
    offset = 1
    for surface in surfaces:
        lines += ['g ' + surface.name, 'usemtl ' + surface.shader]
        lines += ['v %.7g %.7g %.7g' % v for v in surface.vertices]
        lines += ['f %d %d %d' % tuple(i+offset for i in t) for t in surface.triangles]
        offset += len(surface.vertices)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines)+'\n')


def write_palette(path):
    colors = [(255, 3, 2), (97, 0, 0), (82, 0, 0), (41, 0, 0),
              (20, 0, 0), (9, 0, 0), (0, 0, 0), (0, 0, 0)]

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag+data))

    data = b'\x89PNG\r\n\x1a\n'
    data += chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 1, 8, 2, 0, 0, 0))
    data += chunk(b'IDAT', zlib.compress(b'\0'+bytes(v for c in colors for v in c)))
    data += chunk(b'IEND', b'')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--font', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--obj', type=Path)
    parser.add_argument('--palette', type=Path, required=True)
    parser.add_argument('--height', type=float, default=24)
    parser.add_argument('--depth', type=float, default=4)
    args = parser.parse_args()
    if not (0 < args.height <= 64 and 0 < args.depth <= 32):
        parser.error('height must be (0,64], depth (0,32]')
    with TTFont(args.font) as font:
        if not any(n.toUnicode().lower() == 'impact' for n in font['name'].names if n.nameID == 1):
            parser.error('expected the locally licensed Impact font')
        surfaces = model(text_shape(font, args.height), args.depth)
    report = write_md3(args.out, surfaces)
    write_palette(args.palette)
    if args.obj:
        write_obj(args.obj, surfaces)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
