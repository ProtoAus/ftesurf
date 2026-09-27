"""Which props can DISAGREE between the client's prediction and the server's move.

Both sides build a physent_t for every solid prop and then run the same
common/pmovetst.c on it, so they agree only as far as the inputs agree.  Two
inputs are known not to survive the wire intact, and this counts the props that
actually carry the values that expose each one.

  SCALE.  sv_ents.c:3950-3953 sends `bound(1, scale*16, 255)` as a BYTE, and
  cl_ents.c divides the received byte by 16 -- so the client's scale is
  trunc(scale*16)/16.  The server's own pmove (sv_user.c AddEntityToPmove) does
  `bound(1, scale*16, 255)/16.0` with NO truncation.  A modelscale whose x16 is
  not a whole number therefore gives the two sides different collision sizes.
  Exposed count: props with a modelscale where frac(scale*16) != 0.

  BOUNDS.  A `solid 2` prop becomes SOLID_BBOX, whose box reaches the client
  through COM_EncodeSize/COM_DecodeSize (common/common.c:1340-1385).  That
  encoding truncates to whole units AND forces the box symmetric in x/y, taking
  -mins[0] for both half-widths.  The server's pmove uses the raw mins/maxs.
  A prop whose model bounds are asymmetric in x/y is a different SHAPE on the
  two sides.  The model bounds are not in the BSP, so this script counts the
  POPULATION (`solid 2` props) and leaves the per-model asymmetry to a reader
  that can open the .mdl.

Read-only sweep, same idiom as the rest of this directory.  See the README's
"READ THIS BEFORE QUOTING A NUMBER": these are entity-lump KEYS, which is a
fact about what the map asks for, not proof the prop is reachable.
"""
import contextlib, io, os, sys
from collections import Counter

sys.argv = ['pushcensus']
with contextlib.redirect_stdout(io.StringIO()):
    import pushcensus as pc
import bsplib

# SV_SpawnProp's callers, sv_entities.qc:4983-5023.  The defsolid each class
# passes is what applies when the map writes NO solid key -- and QC cannot tell
# an absent key from an explicit "0", which is why the default is per-class.
DEFNONE = {'prop_dynamic', 'prop_dynamic_override', 'prop_dynamic_glow',
           'prop_dynamic_ornament', 'prop_ragdoll', 'prop_hallucination'}
DEFMESH = {'prop_physics', 'prop_physics_multiplayer', 'prop_physics_override',
           'prop_door_rotating', 'prop_physics_ragdoll',
           'prop_physics_respawnable', 'simple_physics_prop', 'prop_sphere'}
PROPS = DEFNONE | DEFMESH

maps = sorted(f for f in os.listdir(pc.MAPS) if f.lower().endswith('.bsp'))

cls = Counter()
solidkey = Counter()
scale_sub = 0            # below 1/16, unrepresentable on the wire
scale_bad = 0            # frac(scale*16) != 0 -- the wire truncates, pmove does not
scale_bad_vals = Counter()
scale_any = 0
bbox_n = 0               # solid 2 -> SOLID_BBOX -> COM_EncodeSize path
mesh_n = 0               # solid 6 (or physics default) -> SOLID_PHYSICS_TRIMESH
none_n = 0
scale_bad_maps, bbox_maps = set(), set()
total = 0
nmaps = 0

for f in maps:
    try:
        ents, _ = bsplib.read(os.path.join(pc.MAPS, f))
    except Exception:
        continue
    nmaps += 1
    for e in ents:
        cn = (e.get('classname') or '').lower()
        if cn not in PROPS:
            continue
        total += 1
        cls[cn] += 1

        # SV_Key2(self.solid, self.Solid): the capitalised spelling lands in a
        # different field and 430 props in a 300-map sample use it.
        raw = e.get('solid', e.get('Solid'))
        solidkey[raw if raw is not None else '<absent>'] += 1
        try:
            s = int(float(raw)) if raw is not None else 0
        except ValueError:
            s = 0
        if s == 0:
            s = 2 if False else (6 if cn in DEFMESH else 0)
        if s == 0:
            none_n += 1
        elif s == 2:
            bbox_n += 1
            bbox_maps.add(f)
        else:
            mesh_n += 1

        ms = e.get('modelscale')
        if ms is None:
            continue
        try:
            v = float(ms)
        except ValueError:
            continue
        if v <= 0:
            v = 1.0
        if v > 15.9:
            v = 15.9          # SV_SpawnProp's clamp, sv_entities.qc:4916-4917
        scale_any += 1
        if v < 1 / 16.0:
            # The wire's bound(1, scale*16, 255) floors at 1/16, so anything
            # below it cannot be represented at all.  Counted because a QC-side
            # quantisation must mirror that floor, not floor() alone -- flooring
            # 0.01 to 0 makes the engine read !scale and substitute 1.
            scale_sub += 1
        q = v * 16.0
        if abs(q - round(q)) > 1e-9:
            scale_bad += 1
            # Keyed on the CLAMPED value: modelscale 16 and 20 both become 15.9,
            # whose x16 is 254.4, so they are genuinely affected -- an earlier cut
            # of this script printed the raw key beside a delta of 0.0000 and read
            # as though they were not.
            scale_bad_vals[round(v, 6)] += 1
            scale_bad_maps.add(f)

print("maps read              %d" % nmaps)
print("prop entities          %d" % total)
print()
print("by collision shape the SERVER gives them (SV_SpawnProp):")
print("  SOLID_NOT             %6d   not in either side's physent list" % none_n)
print("  SOLID_BBOX  (solid 2) %6d   box crosses the wire via COM_EncodeSize" % bbox_n)
print("  SOLID_PHYSICS_TRIMESH %6d   model mesh, both sides trace it locally" % mesh_n)
print()
print("SCALE -- the wire truncates to 1/16, the server's pmove does not:")
print("  props with a modelscale         %6d" % scale_any)
print("  ...whose x16 is NOT whole       %6d   <-- client and server differ" % scale_bad)
print("  ...below 1/16 (unrepresentable) %6d   a QC-side fix must floor at 1/16" % scale_sub)
if scale_bad:
    print("  across %d map(s); commonest values:" % len(scale_bad_maps))
    for v, n in scale_bad_vals.most_common(12):
        q = v * 16.0
        print("    scale %-8.4g %5d  client %.4f  server pmove %.4f  (delta %.4f)"
              % (v, n, int(q) / 16.0, v, v - int(q) / 16.0))
print()
print("BOUNDS -- solid 2 props, whose box is quantised AND symmetrised in x/y:")
print("  population                      %6d across %d map(s)" % (bbox_n, len(bbox_maps)))
print()
print("solid key as written (top 12):")
for k, n in solidkey.most_common(12):
    print("  %-10s %6d" % (k, n))
print()
print("classnames:")
for k, n in cls.most_common():
    print("  %-28s %6d" % (k, n))
