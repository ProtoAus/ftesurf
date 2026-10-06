"""Independent convex-world-brush oracle for hl2_lightprobe occlusion arms.

Usage: python tools/p509brushoracle.py <map.bsp> <probe.log>
Rejects disagreement with a brush blocker. Displacements may explain additional
runtime blockers (reported separately, never silently counted as an oracle pass).
Only VBSP v20 worldlight records are supported here. No Source runtime parity.
"""
import argparse
import math
from pathlib import Path
import struct

from vbsp_lightmap import Bsp
from p509lighting import parse_probes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('bsp', type=Path)
    ap.add_argument('log', type=Path)
    args = ap.parse_args()
    b = Bsp(args.bsp)
    assert b.lumps[54][2] == 0
    lights = [r for r in struct.iter_unpack('<9f3i7f3i', b.lump(54))
              if r[10] in (0,1,2) and r[11] == 0 and not r[19]&1 and r[9] >= 0]
    planes = list(struct.iter_unpack('<4fi', b.lump(1)))
    brushes = list(struct.iter_unpack('<3i', b.lump(18)))
    sides = list(struct.iter_unpack('<Hhhh', b.lump(19)))
    nodes = list(struct.iter_unpack('<iii6hHHhh', b.lump(5)))
    leaves = b.lump(10)
    leafstride = 56 if b.lumps[10][2] == 0 else 32
    leafbrushes = list(struct.unpack('<'+'H'*(len(b.lump(17))//2), b.lump(17)))
    # World headnode, not inline brush models. Derive the actual world brush set.
    head = struct.unpack_from('<i', b.lump(14),36)[0]
    stack, seen, world = [head], set(), set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        if node >= 0:
            stack.extend(nodes[node][1:3])
        else:
            first,count=struct.unpack_from('<HH',leaves,(-1-node)*leafstride+24)
            world.update(leafbrushes[first:first+count])
    opaque = [(i,brushes[i]) for i in sorted(world) if brushes[i][2] & (1|128|16384)]

    def blocker(start,end):
        for ident,(first,count,contents) in opaque:
            enter,leave=0.,1.
            for side in sides[first:first+count]:
                plane=planes[side[0]]
                a=sum(start[c]*plane[c] for c in range(3))-plane[3]
                z=sum(end[c]*plane[c] for c in range(3))-plane[3]
                if a>0 and z>0:
                    break
                if a<=0 and z<=0:
                    continue
                t=a/(a-z)
                if a>z:
                    enter=max(enter,t)
                else:
                    leave=min(leave,t)
                if enter>leave:
                    break
            else:
                if enter<=leave and leave>1e-6 and enter<1-1e-6:
                    return ident
        return None

    compared=blocked=clear=extra=0
    for p in parse_probes(args.log):
        if not p['occlusion']:
            continue
        for ident,(status,rgb,direction) in p['lights'].items():
            r=lights[ident]
            end=list(r[:3])
            if r[10] == 0:
                end=[end[c]+.125*r[6+c] for c in range(3)]
            # Prove the light-index mapping before making an occlusion assertion.
            delta=[r[c]-p['point'][c] for c in range(3)]
            dist=math.sqrt(sum(x*x for x in delta))
            assert all(abs(delta[c]/dist-direction[c])<2e-6 for c in range(3)), (p['point'],ident)
            hit=blocker(p['point'],end)
            compared+=1
            if hit is not None:
                assert status=='blocked', (p['point'],ident,hit,'brush leak')
                blocked+=1
            elif status=='visible':
                clear+=1
            else:
                extra+=1
                print('UNEXPLAINED BY BRUSH-ONLY ORACLE:',p['point'],ident)
    assert blocked>0 and clear>0, 'both occluded and visible subjects must act'
    print(f'Brush oracle: {compared} rays; {blocked} blocked and {clear} clear agree; {extra} additional blockers')
    assert extra==0, 'investigate displacement/trace-epsilon differences before calling this a pass'
    print('PASS independent world-brush oracle, 0 disagreements')


if __name__ == '__main__':
    main()
