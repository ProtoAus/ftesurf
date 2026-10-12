#!/usr/bin/env python3
"""Hermetic Source 1 layout tests; compile the actual engine resolver function.

python tools/test_source_mounts.py --engine <fte checkout> --scratch-root <owned root>
The scratch root must already have OWNER.md; no fixtures touch installed games.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import mapdeps

OLD = "Counter-Strike Global Offensive/csgo"
LEGACY = "csgo legacy/csgo"

HARNESS = r'''
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
#include <sys/stat.h>
typedef bool qboolean;
#define Q_strcasecmp _stricmp
#define FTESURF_STEAMLIBS 1
#define Q_strncpyz(dst,src,len) snprintf(dst,len,"%s",src)
struct sys_findgamedata_ctx_s { char *basepath; int basepathlen; qboolean found; };
static const char *normalroot, *extraroot;
static void Sys_FoundGameData(void *vctx, const char *path)
{
    struct sys_findgamedata_ctx_s *ctx = vctx;
    if (ctx->found || strlen(path) >= (size_t)ctx->basepathlen) return;
    ctx->found = true;
    Q_strncpyz(ctx->basepath, path, ctx->basepathlen);
}
static qboolean probe(const char *root, char *game, char *fname,
    void (*callback)(void *, const char *), void *ctx)
{
    char dir[4096], path[4096];
    struct stat st;
    FILE *file;
    if (!*root) return false;
    snprintf(dir, sizeof(dir), "%s/%s", root, game);
    if (*fname)
    {
        snprintf(path, sizeof(path), "%s/%s", dir, fname);
        file = fopen(path, "rb");
        if (!file) return false;
        fclose(file);
    }
    else if (stat(dir, &st) || !(st.st_mode & S_IFDIR)) return false;
    callback(ctx, dir);
    return true;
}
static qboolean Sys_SteamExtraRoots(void (*callback)(void *, const char *),
    void *ctx, char *game, char *fname)
{
    return probe(extraroot, game, fname, callback, ctx);
}
static qboolean Sys_SteamDirsWithFile(char *game, char *fname,
    void (*callback)(void *, const char *), void *ctx)
{
    return Sys_SteamExtraRoots(callback, ctx, game, fname) ||
        probe(normalroot, game, fname, callback, ctx);
}
'''
MAIN = r'''
int main(int argc, char **argv)
{
    char path[4096];
    if (argc != 5) return 2;
    normalroot = argv[1]; extraroot = argv[2];
    if (!Sys_SteamHasFile(path, sizeof(path), argv[3], argv[4]))
    { puts("MISSING"); return 1; }
    puts(path); return 0;
}
'''


class SourceMountTests(unittest.TestCase):
    def setUp(self):
        self.case = WORK / self._testMethodName
        self.normal = self.case / "normal"
        self.extra = self.case / "extra"
        self.normal.mkdir(parents=True)
        self.extra.mkdir()

    def pack(self, root, game):
        path = root / game / "pak01_dir.vpk"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture: layout selection only")
        return path.parent

    def engine(self, spec, expected, fname=""):
        result = subprocess.run([str(EXE), self.normal.as_posix(), self.extra.as_posix(), spec, fname],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1 if expected is None else 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "MISSING" if expected is None else expected.as_posix())

    def test_beta_layout(self):
        path = self.pack(self.normal, OLD)
        self.engine(OLD, path)
        self.engine(LEGACY, path)
        self.assertEqual(Path(mapdeps.source_csgo_root(self.normal)), path)

    def test_standalone_layout(self):
        path = self.pack(self.normal, LEGACY)
        self.engine(OLD, path)
        self.engine(LEGACY, path)
        self.assertEqual(Path(mapdeps.source_csgo_root(self.normal)), path)

    def test_modern_cs2_only(self):
        self.pack(self.normal, "Counter-Strike Global Offensive/game/csgo")
        (self.normal / OLD).mkdir()
        self.engine(OLD, None)
        self.engine(LEGACY, None)
        self.assertFalse((Path(mapdeps.source_csgo_root(self.normal)) / "pak01_dir.vpk").exists())

    def test_empty_old_directory_does_not_mask_legacy(self):
        (self.normal / OLD).mkdir(parents=True)
        path = self.pack(self.normal, LEGACY)
        self.engine(OLD, path)
        self.assertEqual(Path(mapdeps.source_csgo_root(self.normal)), path)

    def test_explicit_alias_precedes_registry_layout(self):
        self.pack(self.normal, OLD)
        path = self.pack(self.extra, LEGACY)
        self.engine(OLD, path)

    def test_explicit_beta_precedes_registry_legacy(self):
        self.pack(self.normal, LEGACY)
        path = self.pack(self.extra, OLD)
        self.engine(LEGACY, path)

    def test_both_layouts_prefer_requested_name(self):
        old = self.pack(self.normal, OLD)
        legacy = self.pack(self.normal, LEGACY)
        self.engine(OLD, old)
        self.engine(LEGACY, legacy)
        self.assertEqual(Path(mapdeps.source_csgo_root(self.normal)), old)

    def test_unrelated_game_unchanged(self):
        path = self.normal / "Other Game/data"
        path.mkdir(parents=True)
        self.engine("Other Game/data", path)
        self.engine("Other Game/missing", None)

    def test_nonempty_filename_keeps_original_semantics(self):
        old = self.pack(self.normal, OLD)
        self.pack(self.extra, LEGACY)
        self.engine(OLD, old, "pak01_dir.vpk")

    def test_base_pack_is_not_optional_dependency(self):
        self.assertIn("mount", [p[0] for p in mapdeps.MOUNTED])
        self.assertNotIn("mount", [p[0] for p in mapdeps.ADDONS])


def main():
    global WORK, EXE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--cc", default="C:/msys64/ucrt64/bin/gcc.exe")
    args = parser.parse_args()
    if not (args.scratch_root / "OWNER.md").is_file():
        parser.error("--scratch-root must be an existing owned task root")
    source = (args.engine / "engine/common/fs.c").read_text(encoding="utf-8")
    start = source.index("static qboolean Sys_SteamHasFile(char *steambasedir,size_t steambasedirsize, char *steamdir, char *fname)\n{")
    end = source.index("\nstatic void FS_FreePaths", start)
    with tempfile.TemporaryDirectory(prefix="resolver-tests-", dir=args.scratch_root) as work:
        WORK = Path(work)
        EXE = WORK / "resolver.exe"
        c = WORK / "resolver.c"
        c.write_text(HARNESS + source[start:end] + MAIN, encoding="utf-8")
        env = os.environ.copy()
        env["PATH"] = str(Path(args.cc).parent) + os.pathsep + env["PATH"]
        subprocess.run([args.cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-format-truncation",
                        str(c), "-o", str(EXE)], env=env, check=True)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SourceMountTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
