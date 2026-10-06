#!/usr/bin/env python3
"""Generate clangd's local database from FTE's Windows Makefile, without building.

FTE's DO_LD starts with '+' and would link even under make -n. Override that
recipe before the dry run. This database describes m-rel (client + server),
not the Pi's dedicated target or plugin C++; regenerate after flag/header changes.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess


def native_path(value, msys):
    value = value.replace("\\", "/")
    match = re.match(r"^/([a-zA-Z])/(.*)$", value)
    if match:
        return match[1].upper() + ":/" + match[2]
    if value.startswith("/"):
        return msys.as_posix() + value
    return value


def parse_commands(text, engine, msys, compiler):
    entries = {}
    for line in text.splitlines():
        if not re.match(r"^\s*(?:cc|gcc|g\+\+)\s", line):
            continue
        if not re.search(r"\s-c\s", line) or re.search(r"\s-MM\s", line):
            continue
        args = shlex.split(line)
        source = native_path(args[args.index("-c") + 1], msys)
        if Path(source).suffix.lower() not in (".c", ".cc", ".cpp", ".cxx"):
            continue
        converted = [compiler.as_posix()]
        for arg in args[1:]:
            if arg.startswith("-I") and len(arg) > 2:
                converted.append("-I" + native_path(arg[2:], msys))
            else:
                converted.append(native_path(arg, msys))
        entries[source] = {"directory": engine.as_posix(), "file": source,
                           "arguments": converted}
    if not entries:
        raise ValueError("No C/C++ compile commands found; refusing an empty database")
    return list(entries.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=Path("C:/msys64/home/Lex/fteqw"))
    parser.add_argument("--msys", type=Path, default=Path("C:/msys64"))
    parser.add_argument("--compiler", type=Path, help="GCC used by the Windows build")
    parser.add_argument("--log", type=Path, help="Parse an existing make log instead of running make")
    args = parser.parse_args()
    root = args.engine.resolve()
    engine = root / "engine"
    msys = args.msys.resolve()
    compiler = args.compiler
    if compiler is None:
        compiler = next((msys / flavor / "bin/gcc.exe" for flavor in ("ucrt64", "mingw64")
                         if (msys / flavor / "bin/gcc.exe").is_file()), None)
    if compiler is None or not compiler.is_file():
        parser.error("GCC not found; supply --compiler")
    compiler = compiler.resolve()
    if not (engine / "Makefile").is_file():
        parser.error("--engine must name the FTE checkout containing engine/Makefile")
    if args.log:
        text = args.log.read_text(encoding="utf-8", errors="replace")
    else:
        env = os.environ.copy()
        env["PATH"] = os.pathsep.join((str(compiler.parent), str(msys / "usr/bin"), env["PATH"]))
        env["TMP"] = env["TEMP"] = str(msys / "tmp")
        command = [str(msys / "usr/bin/make.exe"), "-n", "-B", "-C", engine.as_posix(),
                   "m-rel", "FTE_TARGET=win64", "DO_LD=echo", "CC=cc"]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("Make dry run failed; database not replaced:\n" + result.stderr)
        text = result.stdout
    entries = parse_commands(text, engine, msys, compiler)
    # Files and definitions must come from this checkout, not a different log.
    files = {Path(entry["file"]).resolve() for entry in entries}
    required = {engine / "common/pm_source.c", engine / "server/sv_user.c",
                engine / "client/in_generic.c"}
    if not required.issubset(files) or not all(path.is_file() and path.is_relative_to(root) for path in files):
        raise ValueError("Database does not cover this engine's mover, server and input sources")
    output = root / "compile_commands.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"Wrote {output}: {len(entries)} translation units (m-rel; no build/deploy)")
    print(f"Allow only this driver in clangd --query-driver: {compiler.as_posix()}")


if __name__ == "__main__":
    main()
