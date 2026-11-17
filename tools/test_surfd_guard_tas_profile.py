#!/usr/bin/env python3
"""Focused tas86-v1 manifest/hash controls (P1600); NEW owned output, no application imports."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys


def check(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def suite(out, preimage, parser_only):
    guard_path = Path(__file__).with_name("surfd_transition_guard.py")
    tas_path = guard_path.parent.parent / "surfd" / "tascontent.py"
    inputs = {"preimage.py": preimage, "fixed.py": guard_path,
              "test.py": Path(__file__), "tascontent.py": tas_path}
    binding = {}
    for name, path in inputs.items():
        data = path.read_bytes()
        (out / name).write_bytes(data)
        binding[name] = sha(data)
    (out / "inputs.json").write_text(json.dumps(binding, indent=2) + "\n")
    fixed = runpy.run_path(str(out / "fixed.py"))
    old = runpy.run_path(str(out / "preimage.py"))
    files85 = old["CURRENT_FAMILY_FILES"] | {"inventory.py", "playstats.py", "momprofile.py", "fetchq.py"}
    check(len(files85) == 85, "preimage must have exact fetch85 set")
    files86 = files85 | {"tascontent.py"}
    check(len(files86) == 86, "tascontent must add exactly one member")
    home = out / "source"
    home.mkdir()
    for name in sorted(files86):
        path = home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = tas_path.read_bytes() if name == "tascontent.py" else b"# synthetic: never imported\n"
        path.write_bytes(data)
    converters = out / "converters"
    converters.mkdir()
    external = {}
    for name in ("momimport", "momreimport", "momreplay"):
        path = converters / (name + ".py")
        path.write_bytes(b"raise RuntimeError('converter must never be imported')\n")
        path.chmod(0o600)
        external[name] = {"origin": str(path), "sha256": sha(path.read_bytes())}
    manifest = {"generation": "1" * 40, "source_home": str(home),
                "target_schema": 26, "runtime_profile": "tas86-v1",
                "hashes": {name: sha((home / name).read_bytes()) for name in sorted(files86)},
                "external_python": external,
                "routes": {"server": [str(Path(sys.executable).resolve()), "surfd.py"]}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    results = []

    def case(name, fn, value, refusal=None):
        try:
            fn(value)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            actual = str(exc)
            passed = refusal is not None and refusal in actual
        else:
            actual = "accepted"
            passed = refusal is None
        results.append({"case": name, "passed": passed, "actual": actual})
        (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        check(passed, name + ": " + actual)
        print("PASS " + name + ": " + actual)

    case("preimage-rejects-exact86", old["manifest_check"], manifest, "unsupported runtime_profile")
    case("fixed-accepts-exact86", fixed["manifest_check"], manifest)
    legacy = copy.deepcopy(manifest)
    legacy["runtime_profile"] = "fetch85-v1"
    legacy["hashes"].pop("tascontent.py")
    for label, guard in (("preimage", old), ("fixed", fixed)):
        case(label + "-accepts-exact85", guard["manifest_check"], legacy)
        added = copy.deepcopy(manifest)
        added["runtime_profile"] = "fetch85-v1"
        case(label + "-85-rejects-tascontent", guard["manifest_check"], added, "raw hash set required")
    short = copy.deepcopy(legacy)
    short["runtime_profile"] = "tas86-v1"
    case("tas86-rejects-exact85", fixed["manifest_check"], short, "raw hash set required")
    for label, change in (("missing-tascontent", lambda m: m["hashes"].pop("tascontent.py")),
                          ("extra-member", lambda m: m["hashes"].update({"extra.py": "0" * 64}))):
        m = copy.deepcopy(manifest)
        change(m)
        case(label, fixed["manifest_check"], m, "raw hash set required")
    for value in (19, 20, 22, 23, 24, 25, 27, True, False, 26.0, "26", None):
        m = copy.deepcopy(manifest)
        m["target_schema"] = value
        case("wrong-schema-" + repr(value), fixed["manifest_check"], m, "schema")
    m = copy.deepcopy(manifest)
    m.pop("target_schema")
    case("missing-schema", fixed["manifest_check"], m, "explicit schema26")
    for label, closure, message in (
            ("missing-external", None, "three-converter"),
            ("empty-external", {}, "three-converter"),
            ("extra-external", dict(external, extra={}), "three-converter"),
            ("malformed-external", dict(external, momimport={}), "external source shape"),
            ("bad-external-hash", dict(external, momimport=dict(external["momimport"], sha256="bad")), "external source hash"),
            ("wrong-external-origin", dict(external, momimport=external["momreplay"]), "external source origin")):
        m = copy.deepcopy(manifest)
        if closure is None:
            m.pop("external_python")
        else:
            m["external_python"] = closure
        case(label, fixed["manifest_check"], m, message)
    if parser_only:
        print("PARSER ONLY: POSIX hash/admission runtime NOT QUALIFIED")
        return
    case("exact86-and-external3-hashes", fixed["verify_hashes"], manifest)
    tas = home / "tascontent.py"
    original = tas.read_bytes()
    tas.unlink()
    case("missing-actual-tascontent-bytes", fixed["verify_hashes"], manifest, "tascontent.py")
    tas.write_bytes(original + b"\n# changed\n")
    case("tampered-actual-tascontent-bytes", fixed["verify_hashes"], manifest, "raw hash mismatch: tascontent.py")
    tas.write_bytes(original)
    for name, item in external.items():
        path = Path(item["origin"])
        original = path.read_bytes()
        path.write_bytes(original + b"# changed\n")
        case("changed-converter-" + name, fixed["verify_hashes"], manifest, "external source raw hash mismatch: " + name)
        path.write_bytes(original)
    case("restored86-and-external3-hashes", fixed["verify_hashes"], manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--preimage", required=True, type=Path)
    parser.add_argument("--parser-only", action="store_true")
    args = parser.parse_args()
    check(os.name == "posix" or args.parser_only,
          "UNSUPPORTED: POSIX hash runtime required; Windows supports only --parser-only")
    out = args.out
    check(out.is_absolute() and out == out.resolve() and not out.exists(), "NEW canonical absolute --out required")
    check(all(not p.is_symlink() for p in (out, *out.parents)), "symlink output refused")
    check(any((p / "OWNER.md").is_file() for p in out.parents), "OWNER.md ancestor required")
    out.mkdir(mode=0o700)
    suite(out, args.preimage, args.parser_only)


if __name__ == "__main__":
    main()
