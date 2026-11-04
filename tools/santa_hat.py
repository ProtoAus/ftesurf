#!/usr/bin/env python3
"""Build the original P1304 low-poly Santa hat (no third-party mesh or runtime work)."""
import argparse
import math
from pathlib import Path

from holiday_assets import iqm


def mesh():
    vertices, triangles = [], []

    def face(a, b, c, white=False):
        ab, ac = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        n = (ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0])
        length = math.sqrt(sum(x*x for x in n))
        if not math.isfinite(length) or length < 1e-8:
            raise ValueError('degenerate/nonfinite hat face')
        n = tuple(x / length for x in n)
        start = len(vertices)
        vertices.extend((tuple(p), (0.75 if white else 0.25, 0.5), n) for p in (a, b, c))
        triangles.append((start, start + 1, start + 2))

    def tube(rings, sides, white=False):
        points = [[(x + r*math.cos(i*math.tau/sides), r*math.sin(i*math.tau/sides), z)
                   for i in range(sides)] for x, z, r in rings]
        for lower, upper in zip(points, points[1:]):
            for i in range(sides):
                j = (i + 1) % sides
                face(lower[i], lower[j], upper[j], white)
                face(lower[i], upper[j], upper[i], white)
        for i in range(sides):
            j = (i + 1) % sides
            face((rings[0][0], 0, rings[0][1]), points[0][j], points[0][i], white)
            face((rings[-1][0], 0, rings[-1][1]), points[-1][i], points[-1][j], white)

    tube([(0, 0, 10), (0, 2, 10.6), (0, 4, 10.6), (0, 5, 9.4)], 12, True)
    tube([(0, 4, 9.8), (0.5, 9, 8.2), (2, 14, 5.4), (6, 18, 2.9),
          (11.5, 17, 1.1), (13.5, 15, 0.3)], 12)
    tube([(14, 14 - math.sqrt(4.5), math.sqrt(4.5)), (14, 14, 3),
          (14, 14 + math.sqrt(4.5), math.sqrt(4.5))], 8, True)
    assert len(triangles) <= 300
    return vertices, triangles


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'ftesurf/models/christmas')
    out = ap.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    v, t = mesh()
    data = iqm('santa', v, t, 'models/christmas/santa')
    (out / 'santa.iqm').write_bytes(data)
    from PIL import Image
    palette = Image.new('RGB', (8, 4), (210, 24, 34))
    palette.paste((248, 248, 244), (4, 0, 8, 4))
    palette.save(out / 'santa.png')
    print(f'Santa: {len(v)} vertices, {len(t)} triangles, {len(data)} IQM bytes; original mesh')


if __name__ == '__main__':
    main()
