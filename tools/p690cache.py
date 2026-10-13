"""Asset-free BSP29 cache controls and strict offline grading (no game/file staging).

Python -O is supported: evidence gates use explicit errors, never assert. Native
capture is a separate operator-controlled operation; see p690cache.md. No Source
cache support, performance or default2 promotion is certified here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

KINDS = ("opaque", "alpha")
ARMS = ("p688", "merged", "probe", "p688-return")
PHASES = ("initial", "cached", "return")
FILES = ("fteqw64.exe", "fteqwsv64.exe", "fteplug_hl2_x64.dll",
         "fteplug_cod_x64.dll", "fteplug_box3d_x64.dll", "fteplug_ode_x64.dll",
         "fteplug_ui_imgui_x64.dll")
STAMPS = {"p688": "git-688-73322dff5b6898511d62ed775286b23a91b8aad0",
          "p688-return": "git-688-73322dff5b6898511d62ed775286b23a91b8aad0",
          "merged": "git-690-a8e705787fad1b60661da5e8dd43c9138cc69b1b",
          "probe": "git-690-a8e705787fad1b60661da5e8dd43c9138cc69b1b-mv11-cacheprobe"}
CACHE = {"initial": 0, "cached": 1, "return": 0}
# These are retained native output hashes, not rebuilt or inferred from version pins.
P688_HASHES = dict(zip(FILES, (
    "714c625b6414e8ca80d4f75f4326fa56a0b4f743859da319b8f2e5c091df06f4",
    "e76794e6ddcbbb8f1e8802801f751c10d42cc92f704633ecdad057d6c3808456",
    "d446c5454c70820c8468e8790f0d1cde0c937332383ee740cac0ed533f3d623a",
    "57ae977233293c721a7ad47b654797b4cb559142192672e253861ada946bafe7",
    "37d497dac464928d3cbe2835a8cd37f24e548bb36750a16d8466fcf866792202",
    "21cf85a47873299f0b3e476f90ac7c413e1df307d4e730ccb6a95a4170f3f921",
    "871c87ec9ef377fd56e6a95b3da986f48fc1bdc4cb6f7ef1fb7d053b106957b1")))
MERGED_HASHES = dict(zip(FILES, (
    "aa1d9e1bc2f167520538bb24423c6e690081b943026186de79269d90b7944668",
    "5807ff1858ac0eca3796baf459dcc463f412f39c95aabd91647735da9b1eed3e",
    "30857eb260b135c4b47a8b12dd22deb0e6f3513acb4246762b0a6a47e16bc1d9",
    "c1b6c146923e7ea58bb8bb79666cced1677b7fab8dda701344cf850eef4475c3",
    "845f113db7770a968f6823944a5e159e805c0ba80a1de5f398699e2d332e25ee",
    "7f0de2b9aa68a0c2141e361995774cd7647c491d3d145ebe2aa5e740c69f46f9",
    "b1c99a18fc58699f662ca106b6cd1452a637948785a44dc99de77651148dd841")))
PROBE_HASHES = dict(MERGED_HASHES, **{
    "fteqw64.exe": "e6c8b0fbf6fbfc54defc9298169c0f878603ca2adfe538e2547bd678cb3344bb"})
HASHES = {"p688": P688_HASHES, "p688-return": P688_HASHES,
          "merged": MERGED_HASHES, "probe": PROBE_HASHES}


class GateError(ValueError):
    """An acceptance condition failed (including incomplete evidence)."""


def require(condition, message):
    if not condition:
        raise GateError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture_bytes(kind):
    """Unvised BSP29: far black wall, near red strip, nearer blue sloped quad.

    Both node children are one empty leaf; this deliberately tests rendering,
    not collisions/PVS. At the pinned FTESurf eye near(0,0,64), angle(0,0,0),
    overlap blue is nearer. Opaque red extends beyond blue as a loss sentinel.
    """
    require(kind in KINDS, f"unknown fixture {kind}")
    pack = struct.pack
    quads = (((600, -2048, -2048), (600, -2048, 2048), (600, 2048, 2048), (600, 2048, -2048)),
             ((256, -320 if kind == "opaque" else -32, 0),
              (256, -320 if kind == "opaque" else -32, 128), (256, 32, 128), (256, 32, 0)),
             ((64, -64, 0), (64, -64, 128), (512, 384, 128), (512, 384, 0)))
    normals = ((-1., 0., 0.), (-1., 0., 0.), (-2 ** -.5, 2 ** -.5, 0.))
    distances = (-600., -256., -128. * 2 ** -.5)
    planes = b"".join(pack("<4fi", *n, d, 3) for n, d in zip(normals, distances))
    planes += pack("<4fi", 1, 0, 0, 0, 0)
    verts = b"".join(pack("<3f", *v) for q in quads for v in q)
    edges = pack("<2H", 0, 0) + b"".join(pack("<2H", q * 4 + i, q * 4 + (i + 1) % 4)
                                                    for q in range(3) for i in range(4))
    surfedges = b"".join(pack("<i", i) for i in range(1, 13))
    names = [f"mv12_{kind}_{c}" for c in ("black", "red", "blue")]
    mips = [pack("<16s6I", n.encode(), 16, 16, 40, 296, 360, 376) + bytes([224]) * 340 for n in names]
    textures = pack("<4i", 3, 16, 16 + len(mips[0]), 16 + len(mips[0]) + len(mips[1])) + b"".join(mips)
    texinfo = b"".join(pack("<8f2i", 0, 1, 0, 0, 0, 0, 1, 0, i, 0) for i in range(3))
    faces = b"".join(pack("<Hhihh4Bi", i, 0, i * 4, 4, i, 255, 255, 255, 255, -1) for i in range(3))
    nodes = pack("<i2h6h2H", 3, -2, -2, -4096, -4096, -4096, 4096, 4096, 4096, 0, 3)
    clipnodes = pack("<i2h", 3, -1, -1)
    def leaf(contents, count):
        return pack("<ii6h2H4B", contents, -1, -4096, -4096, -4096, 4096, 4096, 4096, 0, count, 0, 0, 0, 0)
    leaves = leaf(-2, 0) + leaf(-1, 3)
    marks = pack("<3H", 0, 1, 2)
    model = pack("<9f7i", -4096, -4096, -4096, 4096, 4096, 4096, 0, 0, 0, 0, 0, 0, 0, 1, 0, 3)
    entities = ('{\n"classname" "worldspawn"\n"message" "mv12 supported cache control"\n}\n'
                '{\n"classname" "info_player_start"\n"origin" "0 0 0"\n"angle" "0"\n}\n').encode() + b"\0"
    lumps = (entities, planes, textures, verts, b"", nodes, texinfo, faces, b"", clipnodes,
             leaves, marks, edges, surfedges, model)
    offset = 4 + 15 * 8
    directory = []
    for data in lumps:
        directory.append(pack("<2i", offset, len(data)))
        offset += len(data)
    return pack("<i", 29) + b"".join(directory) + b"".join(lumps)


def fixture_payloads():
    shader = []
    for kind in KINDS:
        for colour, rgb in (("black", "0 0 0"), ("red", "1 0 0"), ("blue", "0 0 1")):
            alpha = ("  alphaGen const 0.5\n  blendFunc src_alpha one_minus_src_alpha\n"
                     if kind == "alpha" and colour != "black" else "")
            shader.append(f"mv12_{kind}_{colour}\n{{\n cull disable\n {{\n  map $whiteimage\n"
                          f"  rgbGen const ( {rgb} )\n{alpha} }}\n}}\n")
    return {**{f"mv12_cache_{k}.bsp": fixture_bytes(k) for k in KINDS},
            "mv12-cache.shader": "".join(shader).encode()}


def create_fixtures(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name, data in fixture_payloads().items():
        (output / name).write_bytes(data)
    manifest = {n: sha(output / n) for n in fixture_payloads()}
    (output / "fixtures.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def parse_actor(text):
    m = re.search(r"MV11_CACHE ticket=(\d+) ordinary=(\d+) cached=(\d+) world=(\S+) "
                  r"fromgame=(\d+) flags=(\S+) cache=(\d+) inuse=(\d+)", text)
    v = re.search(r"MV11_VIEW eye=(\S+) angles=(\S+) mode=(\d+)", text)
    require(m is not None and v is not None, "missing diagnostic postdraw actor/view")
    g = m.groups()
    return dict(ticket=int(g[0]), ordinary=int(g[1]), cached=int(g[2]), world=g[3],
                fromgame=int(g[4]), flags=g[5], requested=int(g[6]), inuse=int(g[7]),
                eye=v[1], angles=v[2], mode=int(v[3]))


def read_image(path):
    # Offline fixture generation and actor parsing do not require these packages.
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        require(im.format == "PNG" and im.mode == "RGB", f"not RGB PNG: {path}")
        a = np.asarray(im).copy()
    require(a.shape == (720, 960, 3), f"wrong image size: {path}")
    return a


def grade(evidence):
    import numpy as np
    evidence = Path(evidence)
    data = json.loads((evidence / "capture.json").read_text())
    require(data["schema"] == 1, "unsupported evidence schema")
    require(data["restored"] is True, "native fixture restoration not verified")
    require(data["fixtures"] == {n: hashlib.sha256(b).hexdigest() for n, b in fixture_payloads().items()},
            "wrong/unbound fixture bytes")
    bundles = data["bundles"]
    require(set(bundles) == set(ARMS), "incomplete bundle inputs")
    for arm, b in bundles.items():
        require(b["stamp"] == STAMPS[arm], f"wrong runtime stamp: {arm}")
        require(set(b["hashes"]) == set(FILES), f"incomplete bundle: {arm}")
        require(all(re.fullmatch(r"[0-9a-f]{64}", h) for h in b["hashes"].values()), f"bad hashes: {arm}")
        require(b["staged"] == b["hashes"] == HASHES[arm], f"wrong/unstaged exact bundle: {arm}")
        require(set(re.findall(r"git-\d+-[0-9a-f]{40}(?:-[A-Za-z0-9-]+)?", b["version"]))
                == {STAMPS[arm]}, f"runtime version not observed: {arm}")
    require(bundles["p688"]["hashes"] == bundles["p688-return"]["hashes"], "A/A return binary changed")
    require(bundles["probe"]["hashes"]["fteqw64.exe"] != bundles["merged"]["hashes"]["fteqw64.exe"],
            "diagnostic must be separate, not labelled production")
    for name in FILES[1:]:
        require(bundles["probe"]["hashes"][name] == bundles["merged"]["hashes"][name],
                f"diagnostic changes non-client input: {name}")
    expected = {(a, k, m, p, r) for a in ARMS for k in KINDS for m in (1, 2)
                for p in PHASES for r in ("a", "b")}
    images, rows = {}, {}
    for row in data["shots"]:
        key = (row["arm"], row["kind"], row["mode"], row["phase"], row["rep"])
        require(key in expected and key not in rows, f"unexpected/duplicate shot: {key}")
        require(row["cache"] == CACHE[row["phase"]], f"wrong phase/cache: {key}")
        require(row["stamp"] == STAMPS[row["arm"]], f"wrong shot runtime: {key}")
        require(row["world"] == f"maps/mv12_cache_{row['kind']}.bsp", f"wrong shot world: {key}")
        require(row["body"] == "0,0,0" and row["aim"] == "0,0,0" and row["velocity"] == "0,0,0",
                f"camera/body/velocity moved: {key}")
        relative = Path(row["path"])
        require(not relative.is_absolute() and ".." not in relative.parts,
                f"screenshot must be relative to evidence: {key}")
        path = evidence / relative
        require(path.resolve().is_relative_to(evidence.resolve()), f"screenshot escapes evidence: {key}")
        require(sha(path) == row["sha256"], f"changed screenshot: {key}")
        images[key] = read_image(path)
        rows[key] = row
    require(set(rows) == expected, "missing evidence rows")
    pairs = []
    def compare(a, b, equal=True):
        n = int(np.any(images[a] != images[b], axis=2).sum())
        pairs.append(dict(a=a, b=b, changed_pixels=n, required="equal" if equal else "observe"))
        if equal:
            require(n == 0, f"pixel mismatch {a} vs {b}: {n}")
        return n
    for a, k, m, p, r in sorted(expected):
        if r == "a":
            compare((a, k, m, p, "a"), (a, k, m, p, "b"))
    # Diagnostic settled interval: actually drew this supported main-view world.
    actors = []
    for k in KINDS:
        for m in (1, 2):
            for p in PHASES:
                a = rows["probe", k, m, p, "a"]["actor"]
                b = rows["probe", k, m, p, "b"]["actor"]
                for x in (a, b):
                    require(x["world"] == f"maps/mv12_cache_{k}.bsp" and x["fromgame"] == 0,
                            f"not supported Q1 world: {k}/{m}/{p}")
                    require(x["requested"] == x["inuse"] == CACHE[p] and x["mode"] == m,
                            f"actor settings did not act: {k}/{m}/{p}")
                    require(tuple(map(float, x["eye"].split(","))) == (0.062, 0.062, 64.062)
                            and tuple(map(float, x["angles"].split(","))) == (0., 0., 0.),
                            "wrong rendered camera")
                require(b["ticket"] > a["ticket"], "actor ticket did not advance")
                ordinary, cached = b["ordinary"] - a["ordinary"], b["cached"] - a["cached"]
                wanted, other = (cached, ordinary) if CACHE[p] else (ordinary, cached)
                require(wanted > 100 and other == 0, f"cache branch NOT REACHED/exclusive: {k}/{m}/{p}")
                actors.append(dict(kind=k, mode=m, phase=p, ordinary=ordinary, cached=cached))
    # No masks: all opaque pixels, both modes, both cache paths, all exact builds.
    reference = ("p688", "opaque", 1, "initial", "a")
    opaque = images[reference]
    red = np.all(opaque == (255, 0, 0), axis=2)
    blue = np.all(opaque == (0, 0, 255), axis=2)
    require(int(red.sum()) > 1000 and int(blue.sum()) > 1000, "opaque fixture has no authored colours")
    require(opaque[360, 480].tolist() == [0, 0, 255], "opaque nearest-depth witness lost")
    for key in sorted(expected):
        if key[1] == "opaque":
            compare(reference, key)
    alpha = []
    legacy_unstable = []
    for m in (1, 2):
        for p in PHASES:
            baseline = ("p688", "alpha", m, p, "a")
            merged = ("merged", "alpha", m, p, "a")
            probe = ("probe", "alpha", m, p, "a")
            back = ("p688-return", "alpha", m, p, "a")
            nreturn = compare(baseline, back, False)
            if m == 1 and nreturn:
                legacy_unstable.append(dict(phase=p, changed_pixels=nreturn))
                # Observe, do not certify parity or bind a diagnostic image to production.
                compare(baseline, merged, False)
                compare(merged, probe, False)
                alpha.append(dict(mode=m, phase=p, status="UNSTABLE_LEGACY_NOT_ACCEPTED"))
                continue
            compare(baseline, back)
            compare(merged, probe)
            if m == 1 or p == "cached":
                compare(baseline, merged)
            else:
                changed = compare(baseline, merged, False)
                require(changed > 1000, f"ordinary alpha mode2 did not act: {p}")
                require(images[baseline][360, 480].tolist() == [127, 0, 64], "baseline alpha order witness")
                require(images[merged][360, 480].tolist() == [64, 0, 127], "merged alpha order witness")
            alpha.append(dict(mode=m, phase=p, status="PASS"))
    for arm in ARMS:
        for mode in (1, 2):
            compare((arm, "alpha", mode, "initial", "a"), (arm, "alpha", mode, "return", "a"))
    return dict(schema=1, verdict="INCOMPLETE alpha legacy parity" if legacy_unstable else "PASS bounded matrix",
                opaque="PASS bounded fullframe supported-Q1 preservation",
                alpha=alpha, legacy_unstable=legacy_unstable, actors=actors, pixel_pairs=pairs,
                limits=["two asset-free BSP29 maps, one camera, one GPU",
                        "diagnostic actors are bound to production only by exact image/input parity",
                        "not Source temporal-cache support, broad-map certification or ordinary performance",
                        "default1 retained; unstable legacy arms are not accepted"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    f = commands.add_parser("fixtures", help="create three files in a fresh owned directory; does not install")
    f.add_argument("--output", type=Path, required=True)
    g = commands.add_parser("grade", help="fail closed on incomplete native capture.json evidence")
    g.add_argument("--evidence", type=Path, required=True)
    g.add_argument("--result", type=Path, required=True, help="new report file, never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.command == "fixtures":
            print(json.dumps(create_fixtures(args.output), indent=2))
        else:
            require(not args.result.exists(), "result path already exists")
            result = grade(args.evidence)
            with args.result.open("x") as out:
                out.write(json.dumps(result, indent=2) + "\n")
            print(result["opaque"])
            print("Alpha phases:", ", ".join(x["status"] for x in result["alpha"]))
            if result["legacy_unstable"]:
                parser.exit(1, "INCOMPLETE: opaque passes; unstable alpha legacy arms are NOT accepted\n")
    except (GateError, OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
