#!/usr/bin/env python3
"""
Generate the ghost body models -- ftesurf/models/player.iqm and player_duck.iqm.

WHY THIS EXISTS
---------------
The player.iqm that was in the tree before build 30 is a 32 x 32 x **48** box
with a nose.  The player hull is 32 x 32 x **72** standing and 32 x 32 x **54**
ducked (PM_HULL_MAXS / PM_DUCK_MAXS, src/shared/sh_defs.qc:21-24), so the model
stood two thirds the height of the body it was drawing.  Ghost mode draws it at
your own feet while you fly away from it, which is exactly the situation where
"what I collide with" and "what I see" disagreeing is worst.

Rather than hand-edit a binary, the shape is described once here and both
heights fall out of the same code -- so the ducked model cannot drift from the
standing one, and either can be re-cut if the hull ever changes.

THE SHAPE is the original's, verified by parsing it: a vertical prism over the
pentagon

        (-16,-16)  (16,-16)  (23.255, 0)  (16, 16)  (-16, 16)

from z = 0 to z = HEIGHT.  Origin at the FEET (Source convention, which is what
PutClientInServer's setsize uses), and the nose on **+X**, which is FTE's
forward -- so drawing it wants `angles = [0, yaw, 0]` and no fixup of any kind.

    5 bottom verts + 5 top verts + 5 side quads x 4 = 30 vertices
    3 + 3 + 5 x 2                                   = 16 triangles

16 triangles is what the original had, which is the check that the pentagon
reading of it is right and not merely plausible.

VERTICES ARE PER-FACE, so every face gets a true flat normal.  The original had
34 for the same 16 triangles (Blender splits differently); the count is not a
thing to match, the geometry is.

USAGE
    python tools/mkplayermodel.py            # report what it would write
    python tools/mkplayermodel.py --apply    # write them
    python tools/mkplayermodel.py --selftest # prove the writer against the
                                             # original file, writing nothing

--selftest is the one that matters before trusting the output: it re-cuts the
shape at the ORIGINAL's height of 48, parses both files back with the same
reader, and compares the geometry that the engine will actually draw.  A writer
that emits a well-formed file describing the wrong solid passes every other
check there is.
"""

import argparse
import os
import re
import shutil
import struct
import sys

# ---------------------------------------------------------------------------
# The shape.  Half-widths and the nose come from the original file; the heights
# come from sh_defs.qc.  Keep them named rather than inline -- the whole point
# of this file is that the numbers are legible and in one place.
# ---------------------------------------------------------------------------
HALF_X = 16.0
HALF_Y = 16.0
NOSE_X = 23.255          # the prow apex, at y = 0

# THESE TWO ARE CHECKED AGAINST sh_defs.qc BY THE SELFTEST.  Do not edit one
# without the other -- see hull_from_sh_defs() and the essay above its call.
#
# They were 72.0 and 54.0 from build 30 to build 51, carrying a comment that
# claimed sh_defs.qc as the source while sh_defs.qc said 62 and 45.  72/54 is
# CS:S's pair; this game uses Momentum's, and sh_defs.qc:34-35 says so in as
# many words.  The hull moved in build 41 and nothing brought the model with
# it, so every drawn body was 10 units taller than the box it collides with,
# standing, and 9 taller ducked, for eleven builds.
HEIGHT_STAND = 62.0      # PM_HULL_MAXS '16 16 62'  (sh_defs.qc:37)
HEIGHT_DUCK  = 45.0      # PM_DUCK_MAXS '16 16 45'  (sh_defs.qc:39)
HEIGHT_ORIG  = 48.0      # what the pre-build-30 file was, for --selftest

# THE MATERIAL IS PATH-QUALIFIED, AND IT HAS TO BE.
#
# The obvious name is "player", which is what the hand-made model this replaces
# carried.  It is also the name of QUAKE'S OWN PLAYER SKIN, and FTE has a shader
# for it -- so a bare "player" resolves to that instead of to this model's own
# texture, and the console fills with
#
#     texture "player_norm"  did not resolve from any wad or replacement
#     texture "player_pants" did not resolve from any wad or replacement
#     texture "player_shirt" did not resolve from any wad or replacement
#
# (those are player.mdl's skin-group layers), and the model draws as flat
# no_texture green.  Measured, first time it was drawn.
#
# A name containing '/' is taken verbatim by R_RegisterSkin rather than being
# resolved against the shader scripts and the wads first, so "models/player"
# finds models/player.tga -- the file that is actually sitting next to the
# model -- and finds it without a search across the 86,000 indexed files that a
# bare name has to be checked against.  That search is also the best available
# explanation for the map-load hang the first precache attempt hit; see the
# note in cl_ghost.qc.
MATERIAL = "models/player"

# Counter-clockwise seen from +Z, so that the outward normal of each side quad
# comes out pointing away from the solid.
FOOTPRINT = [
    (-HALF_X, -HALF_Y),
    ( HALF_X, -HALF_Y),
    ( NOSE_X,     0.0),
    ( HALF_X,  HALF_Y),
    (-HALF_X,  HALF_Y),
]

IQM_MAGIC = b"INTERQUAKEMODEL\0"
IQM_VERSION = 2

IQM_POSITION = 0
IQM_TEXCOORD = 1
IQM_NORMAL   = 2
IQM_TANGENT  = 3
IQM_FLOAT    = 7

HEADER_FMT = "<16s27I"
HEADER_SIZE = struct.calcsize(HEADER_FMT)      # 124


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(v):
    length = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
    if length < 1e-9:
        return (0.0, 0.0, 1.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _face_normal(poly):
    """Newell's method -- correct for a non-planar or degenerate-edged polygon,
    where a single cross product of two edges is not."""
    nx = ny = nz = 0.0
    n = len(poly)
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return _norm((nx, ny, nz))


def _tangent(normal):
    """Any unit vector perpendicular to `normal`, chosen deterministically.

    The models carry no bumpmap, so the tangent frame is never used for
    lighting -- it is emitted because the original file had the array and a
    loader that reads it should find something well formed rather than absent.
    """
    axis = (0.0, 0.0, 1.0) if abs(normal[2]) < 0.9 else (1.0, 0.0, 0.0)
    return _norm(_cross(axis, normal))


def build_faces(height):
    """The solid, as a list of (polygon, uvs).  Polygons are CCW seen from
    outside, so a front-facing winding falls out of the fan below."""
    n = len(FOOTPRINT)
    bottom = [(x, y, 0.0) for (x, y) in FOOTPRINT]
    top    = [(x, y, height) for (x, y) in FOOTPRINT]

    faces = []

    # Bottom: reversed, because CCW-from-above is CW-from-below.
    faces.append((list(reversed(bottom)),
                  [((x / (2 * NOSE_X)) + 0.5, (y / (2 * HALF_Y)) + 0.5)
                   for (x, y, _) in reversed(bottom)]))

    faces.append((top,
                  [((x / (2 * NOSE_X)) + 0.5, (y / (2 * HALF_Y)) + 0.5)
                   for (x, y, _) in top]))

    # The five sides, each a quad from the bottom edge up to the top edge.  u
    # runs along the perimeter so the skin wraps rather than repeating per face;
    # v is height, 0 at the feet.
    perim = 0.0
    lengths = []
    for i in range(n):
        a = FOOTPRINT[i]
        b = FOOTPRINT[(i + 1) % n]
        seg = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        lengths.append(seg)
        perim += seg

    run = 0.0
    for i in range(n):
        j = (i + 1) % n
        u0 = run / perim
        run += lengths[i]
        u1 = run / perim
        quad = [bottom[i], bottom[j], top[j], top[i]]
        uvs  = [(u0, 1.0), (u1, 1.0), (u1, 0.0), (u0, 0.0)]
        faces.append((quad, uvs))

    return faces


def build_mesh(height):
    """Flatten the faces into per-face vertices and a triangle fan each."""
    positions, texcoords, normals, tangents, triangles = [], [], [], [], []

    for poly, uvs in build_faces(height):
        base = len(positions)
        nrm = _face_normal(poly)
        tan = _tangent(nrm)
        for k, p in enumerate(poly):
            positions.append(p)
            texcoords.append(uvs[k])
            normals.append(nrm)
            # w = 1: handedness.  Unused here, but the field is not optional.
            tangents.append((tan[0], tan[1], tan[2], 1.0))
        # WOUND CW, BECAUSE FTE'S FRONT FACE IS CW AND THE MODEL WAS INSIDE OUT.
        #
        # build_faces produces polygons CCW seen from outside, which is the
        # normal maths convention and is what makes _face_normal point outward.
        # Fanning them in that order produced CCW triangles -- and FTE culls
        # those.  GL_CullFace (gl_backend.c:1086-1089) maps SHADER_CULL_FRONT to
        # `qglCullFace(GL_FRONT)`, and qglFrontFace is loaded but NEVER CALLED
        # anywhere in the engine, so the winding stays at GL's default of
        # GL_CCW = front.  Culling the front therefore culls the CCW triangles,
        # and the visible ones are the CW ones.
        #
        # So every outward face of the player model was being discarded and what
        # you saw was the inside of the far side of the box.  It is subtle on a
        # convex solid -- the silhouette is identical and only the shading and
        # the depth order give it away -- which is why it survived being drawn
        # as a ghost body and in three lobby screenshots before somebody looked
        # at another player and said the faces were on the inside.
        #
        # k+1 and k swapped, and ONLY here: the polygon order feeds
        # _face_normal, so reversing the polygon itself would flip the normals
        # inward and break the lighting instead.  Normals stay outward; only the
        # index order changes.
        for k in range(1, len(poly) - 1):
            triangles.append((base, base + k + 1, base + k))

    return positions, texcoords, normals, tangents, triangles


# ---------------------------------------------------------------------------
# the IQM writer
# ---------------------------------------------------------------------------

def write_iqm(height):
    positions, texcoords, normals, tangents, triangles = build_mesh(height)

    # text blob: index 0 must be the empty string, which is what a zero name
    # offset means.  Both the mesh name and its material are "player".
    text = b"\0" + MATERIAL.encode("ascii") + b"\0"
    ofs_material = 1

    arrays = [
        (IQM_POSITION, 3, b"".join(struct.pack("<3f", *v) for v in positions)),
        (IQM_TEXCOORD, 2, b"".join(struct.pack("<2f", *v) for v in texcoords)),
        (IQM_NORMAL,   3, b"".join(struct.pack("<3f", *v) for v in normals)),
        (IQM_TANGENT,  4, b"".join(struct.pack("<4f", *v) for v in tangents)),
    ]

    # Layout: header, text, vertex data, vertexarray table, triangles, mesh.
    # Order is free -- everything is reached by offset -- so this is simply the
    # order that makes the offsets easy to check by eye in a hex dump.
    ofs = HEADER_SIZE
    ofs_text = ofs
    ofs += len(text)

    blobs = []
    descs = []
    for kind, size, blob in arrays:
        descs.append((kind, 0, IQM_FLOAT, size, ofs))
        blobs.append(blob)
        ofs += len(blob)

    ofs_vertexarrays = ofs
    ofs += 20 * len(arrays)

    ofs_triangles = ofs
    tri_blob = b"".join(struct.pack("<3I", *t) for t in triangles)
    ofs += len(tri_blob)

    ofs_meshes = ofs
    mesh_blob = struct.pack("<6I", ofs_material, ofs_material,
                            0, len(positions), 0, len(triangles))
    ofs += len(mesh_blob)

    filesize = ofs

    header = struct.pack(
        HEADER_FMT, IQM_MAGIC,
        IQM_VERSION, filesize, 0,
        len(text), ofs_text,
        1, ofs_meshes,
        len(arrays), len(positions), ofs_vertexarrays,
        len(triangles), ofs_triangles, 0,      # ofs_adjacency 0 = none
        0, 0,                                   # joints
        0, 0,                                   # poses
        0, 0,                                   # anims
        0, 0, 0, 0,                             # frames, framechannels, frames, bounds
        0, 0,                                   # comment
        0, 0,                                   # extensions
    )

    out = bytearray(header)
    out += text
    for blob in blobs:
        out += blob
    for d in descs:
        out += struct.pack("<5I", *d)
    out += tri_blob
    out += mesh_blob

    assert len(out) == filesize, (len(out), filesize)
    return bytes(out)


# ---------------------------------------------------------------------------
# the reader, used only to check our own work and the original
# ---------------------------------------------------------------------------

def read_iqm(data):
    if data[:16] != IQM_MAGIC:
        raise ValueError("not an IQM (bad magic)")
    h = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
    (_, version, filesize, _flags,
     num_text, ofs_text,
     num_meshes, ofs_meshes,
     num_va, num_vt, ofs_va,
     num_tri, ofs_tri, _ofs_adj,
     num_joints, _oj, num_poses, _op, num_anims, _oa,
     num_frames, _nfc, _of, _ob, _nc, _oc, _ne, _oe) = h

    if version != IQM_VERSION:
        raise ValueError("IQM version %d, expected 2" % version)
    if filesize != len(data):
        raise ValueError("header filesize %d, actual %d" % (filesize, len(data)))

    info = {
        "version": version, "filesize": filesize,
        "num_meshes": num_meshes, "num_vertexes": num_vt,
        "num_triangles": num_tri, "num_joints": num_joints,
        "num_poses": num_poses, "num_anims": num_anims,
        "num_frames": num_frames,
        "arrays": {},
    }

    for i in range(num_va):
        kind, _f, fmt, size, off = struct.unpack(
            "<5I", data[ofs_va + i * 20: ofs_va + i * 20 + 20])
        info["arrays"][kind] = (fmt, size, off)

    if IQM_POSITION not in info["arrays"]:
        raise ValueError("no POSITION array")
    fmt, size, off = info["arrays"][IQM_POSITION]
    if fmt != IQM_FLOAT or size != 3:
        raise ValueError("POSITION is not 3 floats")
    pos = [struct.unpack("<3f", data[off + j * 12: off + j * 12 + 12])
           for j in range(num_vt)]
    info["positions"] = pos

    tris = [struct.unpack("<3I", data[ofs_tri + j * 12: ofs_tri + j * 12 + 12])
            for j in range(num_tri)]
    for t in tris:
        for v in t:
            if v >= num_vt:
                raise ValueError("triangle indexes vertex %d of %d" % (v, num_vt))
    info["triangles"] = tris

    names = data[ofs_text:ofs_text + num_text]
    mats = set()
    for i in range(num_meshes):
        _n, mat, fv, nv, ft, nt = struct.unpack(
            "<6I", data[ofs_meshes + i * 24: ofs_meshes + i * 24 + 24])
        if fv + nv > num_vt or ft + nt > num_tri:
            raise ValueError("mesh %d runs past the arrays" % i)
        end = names.find(b"\0", mat)
        mats.add(names[mat:end].decode("ascii", "replace"))
    info["materials"] = sorted(mats)

    return info


def geometry(info):
    """The facts the engine actually draws with, in a comparable form."""
    pts = {tuple(round(c, 3) for c in p) for p in info["positions"]}
    zs = [p[2] for p in info["positions"]]
    xs = [p[0] for p in info["positions"]]
    ys = [p[1] for p in info["positions"]]
    return {
        "unique_positions": sorted(pts),
        "num_triangles": info["num_triangles"],
        "bbox": (round(min(xs), 3), round(min(ys), 3), round(min(zs), 3),
                 round(max(xs), 3), round(max(ys), 3), round(max(zs), 3)),
        "materials": info["materials"],
        "rigid": (info["num_joints"], info["num_anims"], info["num_frames"]),
    }


# ---------------------------------------------------------------------------

def write_luma_tga(width=256, height=256, lo=0.42, hi=0.58):
    """A fullbright mask for models/player: black, with one white band.

    Dropping models/player_luma.tga beside models/player.tga is all it takes to
    enable the fullbright pass -- R_BuildLegacyTexnums probes "%s_luma:%s_glow"
    (gl_shader.c:7046-7048) and the permutation turns on when that texture
    loads (gl_backend.c:4373-4374).  .glowmod then tints it per player.

    WHY A BAND AND NOT FULL COVERAGE.  The skin is flat, so a fully white luma
    would make the entire body self-lit -- which throws the lighting away and
    turns every player into a flat silhouette.  A band is a belt around the
    model that stays readable in a dark leaf, where colormod's lit term goes to
    zero and a colour-only body goes black.

    WHY THE BAND IS CENTRED ON v = 0.5.  build_faces lays u along the perimeter
    and v as height, but v runs 1 at the FEET and 0 at the crown -- the
    inversion noted beside the texcoord code.  A band placed off-centre would
    therefore land at the ankles if that reading is wrong by a flip, and this
    has not been checked against a rendered frame.  Centring it makes the
    placement independent of the orientation: waist height either way.  Move it
    once someone has actually looked at it.
    """
    band = bytearray()
    for y in range(height):
        v = (y + 0.5) / height
        on = (lo <= v <= hi)
        c = 255 if on else 0
        band += bytes((c, c, c)) * width          # TGA is BGR; grey is symmetric

    hdr = struct.pack("<BBBHHBHHHHBB",
                      0,      # no image id
                      0,      # no colour map
                      2,      # uncompressed true-colour
                      0, 0, 0,
                      0, 0,   # x/y origin
                      width, height,
                      24,     # bits per pixel
                      0)      # descriptor: bottom-left origin
    return bytes(hdr) + bytes(band) + b"\x00"*8 + b"TRUEVISION-XFILE.\x00"


def hull_from_sh_defs(path=None):
    """Read the real hull out of sh_defs.qc.  Returns (mins_z, stand_z, duck_z)
    or None if the file could not be read or did not contain what we need.

    THE AUTHORITY IS NOT THIS FILE.  src/shared/sh_defs.qc holds the hull, the
    engine asserts the same numbers in its own selftests (pm_source.c:4111-4112)
    and cfg/default.cfg sets them as pm_standheight / pm_duckheight.  This
    script only ever gets to AGREE with them.
    """
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, os.pardir, "src", "shared", "sh_defs.qc")
    path = os.path.abspath(path)

    try:
        with open(path, "r") as f:
            text = f.read()
    except IOError:
        return None

    def vec(name):
        m = re.search(r"#define\s+%s\s+'\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*'"
                      % re.escape(name), text)
        return tuple(float(g) for g in m.groups()) if m else None

    hull_min, hull_max = vec("PM_HULL_MINS"), vec("PM_HULL_MAXS")
    duck_min, duck_max = vec("PM_DUCK_MINS"), vec("PM_DUCK_MAXS")
    if not (hull_min and hull_max and duck_min and duck_max):
        return None
    # Both hulls sit on the floor; the model is cut from z=0 up, so if these
    # ever stop being 0 the whole feet-at-origin convention has moved and the
    # heights are the least of it.
    if hull_min[2] != duck_min[2]:
        return None
    return (hull_min[2], hull_max[2], duck_max[2])


def selftest(original_path, hull_check=True):
    print("--- selftest: re-cut the shape at the ORIGINAL's height and compare")

    if not os.path.exists(original_path):
        print("    SKIP: %s is not there to compare against" % original_path)
        print("    (the writer's round trip is still checked below)")
        orig_geo = None
    else:
        with open(original_path, "rb") as f:
            orig = read_iqm(f.read())
        orig_geo = geometry(orig)
        print("    original : %d verts, %d tris, bbox %s"
              % (orig["num_vertexes"], orig_geo["num_triangles"], orig_geo["bbox"]))

    mine = read_iqm(write_iqm(HEIGHT_ORIG))
    mine_geo = geometry(mine)
    print("    re-cut   : %d verts, %d tris, bbox %s"
          % (mine["num_vertexes"], mine_geo["num_triangles"], mine_geo["bbox"]))

    ok = True
    if orig_geo is not None:
        for key in ("unique_positions", "num_triangles", "bbox"):
            if orig_geo[key] != mine_geo[key]:
                ok = False
                print("    MISMATCH %s:" % key)
                print("      original: %r" % (orig_geo[key],))
                print("      re-cut  : %r" % (mine_geo[key],))
        if orig_geo["rigid"] != mine_geo["rigid"]:
            ok = False
            print("    MISMATCH rigid (joints, anims, frames): %r vs %r"
                  % (orig_geo["rigid"], mine_geo["rigid"]))
        if orig["materials"] != mine["materials"]:
            print("    note: materials %r vs %r (skin name, not geometry)"
                  % (orig["materials"], mine["materials"]))

    # WINDING, which this selftest did not check and which is what broke.
    #
    # The first version compared unique_positions, num_triangles, bbox and
    # rigidity against the preserved original -- everything except the order the
    # indices are in.  So when the re-cut came out CCW where the hand-made
    # player_48.iqm was CW, the selftest passed, and the model shipped inside
    # out: FTE culls CCW (GL_CullFace maps SHADER_CULL_FRONT to
    # glCullFace(GL_FRONT), and glFrontFace is never called, so GL's CCW=front
    # default stands).  Every outward face was discarded and players saw the
    # inside of each other's far side.  It survived three lobby screenshots and
    # was found by a person looking at another player.
    #
    # The solid is convex, so the test needs no stored normals: a correctly
    # wound triangle's right-hand normal points AWAY from the centroid, and CW
    # is the one that must be true here.
    def _winding(info):
        pos, tris = info["positions"], info["triangles"]
        n = len(pos)
        cen = tuple(sum(p[i] for p in pos) / n for i in range(3))
        ccw = cw = 0
        for (a, b, c) in tris:
            u = tuple(pos[b][i] - pos[a][i] for i in range(3))
            v = tuple(pos[c][i] - pos[a][i] for i in range(3))
            gn = (u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2], u[0]*v[1] - u[1]*v[0])
            mid = tuple((pos[a][i] + pos[b][i] + pos[c][i]) / 3.0 for i in range(3))
            d = sum(gn[i] * (mid[i] - cen[i]) for i in range(3))
            if d > 0: ccw += 1
            elif d < 0: cw += 1
        return ccw, cw

    if orig is not None:
        o_ccw, o_cw = _winding(orig)
        print("    original winding : %d CCW, %d CW" % (o_ccw, o_cw))

    # And the two real outputs must parse, stand the right height, and be CW.
    for name, height in (("player.iqm", HEIGHT_STAND),
                         ("player_duck.iqm", HEIGHT_DUCK)):
        info = read_iqm(write_iqm(height))
        geo = geometry(info)
        top = geo["bbox"][5]
        ccw, cw = _winding(info)
        status = "ok" if abs(top - height) < 1e-3 else "WRONG HEIGHT"
        if ccw:
            status = "INSIDE OUT (%d CCW tris)" % ccw
        if status != "ok":
            ok = False
        print("    %-16s %d verts, %d tris, z 0..%g, %d CW  [%s]"
              % (name, info["num_vertexes"], geo["num_triangles"], top, cw, status))

    # THE HEIGHTS AGAINST THE HULL, which is the check that was missing and is
    # the reason this file shipped a 72-unit model against a 62-unit hull for
    # eleven builds.
    #
    # Everything above compares the writer against player_48.iqm, and then
    # checks each output came out at the height THIS SCRIPT ASKED FOR.  That
    # second test cannot fail: it compares HEIGHT_STAND to itself.  So the
    # constants were free to say 72 while sh_defs.qc said 62, the comment beside
    # them cited sh_defs.qc as the source, and the selftest passed the whole
    # time and read as coverage.
    #
    # Same shape as the winding bug directly above: a round trip that compares
    # every property except the one that broke.  The fix in both cases is to
    # compare against something that is NOT this script -- there, the preserved
    # original's index order; here, the hull the game actually collides with.
    hull = hull_from_sh_defs() if hull_check else None
    if not hull_check:
        print("    hull     : CHECK SKIPPED (--no-hull-check).  The heights in this")
        print("      script are unverified against sh_defs.qc.")
    elif hull is None:
        # Loudly, and as a FAILURE of the check rather than a silent pass.  A
        # check that evaporates when its input moves is worse than no check,
        # because the "PASSED" line still says everything was verified.
        ok = False
        print("    HULL CHECK UNAVAILABLE: could not read PM_HULL_MINS/MAXS and")
        print("      PM_DUCK_MINS/MAXS from src/shared/sh_defs.qc.")
        print("      Pass --no-hull-check if the file has genuinely moved, and")
        print("      then go and fix this path.")
    else:
        floor_z, stand_z, duck_z = hull
        for what, mine, theirs in (("HEIGHT_STAND", HEIGHT_STAND, stand_z),
                                   ("HEIGHT_DUCK",  HEIGHT_DUCK,  duck_z)):
            if abs(mine - theirs) >= 1e-6:
                ok = False
                print("    MISMATCH %s: this script says %g, sh_defs.qc says %g"
                      % (what, mine, theirs))
        if floor_z != 0.0:
            ok = False
            print("    MISMATCH hull floor: sh_defs.qc mins.z is %g, not 0 -- the"
                  % floor_z)
            print("      model is cut from z=0 up, so feet-at-origin has moved.")
        if ok:
            print("    hull     : sh_defs.qc says floor %g, stand %g, duck %g  [agrees]"
                  % (floor_z, stand_z, duck_z))

    print("--- selftest %s" % ("PASSED" if ok else "FAILED"))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually write the files")
    ap.add_argument("--selftest", action="store_true",
                    help="check the writer against the original; write nothing")
    ap.add_argument("--models", default=None,
                    help="the models directory (default: ../ftesurf/models "
                         "relative to this script)")
    ap.add_argument("--no-hull-check", action="store_true",
                    help="skip checking HEIGHT_STAND/HEIGHT_DUCK against "
                         "src/shared/sh_defs.qc.  Only for when that file has "
                         "genuinely moved -- the check is what stops this "
                         "script drifting away from the hull again.")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    models = args.models or os.path.join(here, os.pardir, "ftesurf", "models")
    models = os.path.abspath(models)

    stand = os.path.join(models, "player.iqm")
    duck  = os.path.join(models, "player_duck.iqm")
    backup = os.path.join(models, "player_48.iqm")

    # COMPARE AGAINST THE PRESERVED ORIGINAL, NOT AGAINST player.iqm.
    #
    # Once --apply has run once, player.iqm IS this script's output, so checking
    # the re-cut against it compares 48 to 72 and "fails" -- and, worse, on the
    # run before that it would have compared the writer against itself and
    # passed for the wrong reason.  player_48.iqm is the untouched hand-made
    # model kept by the first --apply, so it stays a real reference forever.
    reference = backup if os.path.exists(backup) else stand

    hull_check = not args.no_hull_check

    if args.selftest:
        return 0 if selftest(reference, hull_check) else 1

    if not selftest(reference, hull_check):
        print("refusing to write: the selftest failed")
        return 1

    plan = [(stand, HEIGHT_STAND), (duck, HEIGHT_DUCK)]

    if not args.apply:
        print()
        print("would write (use --apply):")
        for path, height in plan:
            print("    %s   z 0..%g" % (path, height))
        if os.path.exists(stand) and not os.path.exists(backup):
            print("    %s   <- the existing 48-unit model, kept" % backup)
        return 0

    print()
    if os.path.exists(stand) and not os.path.exists(backup):
        shutil.copyfile(stand, backup)
        print("kept the old model as %s" % backup)

    for path, height in plan:
        data = write_iqm(height)
        with open(path, "wb") as f:
            f.write(data)
        print("wrote %s (%d bytes, z 0..%g)" % (path, len(data), height))

    # The fullbright mask, written here so it cannot drift away from the model
    # whose UVs it is cut against.  Patch 278.
    luma = os.path.join(models, "player_luma.tga")
    data = write_luma_tga()
    with open(luma, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes, waist band for .glowmod)" % (luma, len(data)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
