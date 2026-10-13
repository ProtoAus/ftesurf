#!/usr/bin/env python3
"""Acted startup-wrapper controls with tiny native actors and the real bootstrap.

Use an owned fresh evidence root. POSIX runtime fixtures use ext4 temporary dirs;
no player install, private key, public feed or GUI engine is used by this test.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ACTOR = r'''
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <direct.h>
#define getcwd _getcwd
#else
#include <unistd.h>
#endif
static void hex(FILE *f, const char *s) {
    while (*s) fprintf(f, "%02x", (unsigned char)*s++);
    fputc('\n', f);
}
int main(int argc, char **argv) {
    char cwd[8192];
    FILE *f = fopen(getenv("FTESURF_WRAPPER_ACTOR_LOG"), "a");
    if (!f || !getcwd(cwd, sizeof(cwd))) return 90;
    fputs("cwd ", f); hex(f, cwd);
    for (int i = 0; i < argc; i++) { fputs("arg ", f); hex(f, argv[i]); }
    fputs("end\n", f);
    if (fclose(f)) return 91;
    puts("WRAPPER_ACTOR_ACTED");
    fputs("WRAPPER_ACTOR_STDERR\n", stderr);
    const char *code = getenv("FTESURF_WRAPPER_ACTOR_EXIT");
    return code ? atoi(code) : 0;
}
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(path):
    result, item = [], {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        if line == 'end':
            result.append(item)
            item = {}
        else:
            key, value = line.split(' ', 1)
            value = bytes.fromhex(value).decode()
            if key == 'cwd':
                item['cwd'] = value
            else:
                item.setdefault('argv', []).append(value)
    assert not item, 'incomplete native actor record'
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tree', type=Path, required=True)
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--cc', default='C:/msys64/ucrt64/bin/gcc.exe' if os.name == 'nt' else 'cc')
    ap.add_argument('--expect-before', action='store_true')
    ap.add_argument('--regression-control', choices=['desktop', 'dangling'])
    a = ap.parse_args()
    assert not (a.expect_before and a.regression_control)
    tree, launcher = a.tree.resolve(), a.launcher.resolve()
    evidence = a.work_root.resolve()
    assert not evidence.exists(), f'fresh evidence root required: {evidence}'
    assert tree.is_dir() and launcher.is_file()
    evidence.mkdir(parents=True)
    (evidence / 'OWNER.md').write_text('Owned tiny wrapper actors and captured evidence; no player data.\n')
    win = os.name == 'nt'
    suffix = '.exe' if win else ''
    wrapper_name = 'ftesurf.bat' if win else 'ftesurf.sh'
    summary = {'platform': os.name, 'wrapper_sha256': digest(tree / wrapper_name),
               'launcher_sha256': digest(launcher), 'cases': [], 'verdict': 'FAIL'}
    context = tempfile.TemporaryDirectory(prefix='ftesurf-wrappers-', dir=evidence if win else None)
    runtime = Path(context.name)
    summary['runtime_root'] = str(runtime)
    try:
        source = runtime / 'actor.c'
        source.write_text(ACTOR)
        actor = runtime / ('actor' + suffix)
        build_env = os.environ.copy()
        if win:
            build_env['PATH'] = str(Path(a.cc).resolve().parent) + os.pathsep + build_env['PATH']
        build = subprocess.run([a.cc, '-std=c99', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(actor)],
                               env=build_env, capture_output=True, text=True, timeout=60)
        (evidence / 'actor-build.txt').write_text(build.stdout + build.stderr)
        assert build.returncode == 0, build
        if not win:
            actor.chmod(0o755)
        caller = runtime / 'unrelated cwd'
        caller.mkdir()
        dialogs = runtime / 'bin'
        dialogs.mkdir()
        if not win:
            zenity = dialogs / 'zenity'
            zenity.write_text('#!/bin/sh\necho WRAPPER_DIALOG_ACTED\nexit 0\n')
            zenity.chmod(0o755)

        def run(name, args, expected_args, *, bootstrap=True, code=0, real=False,
                engine=True, nonexec=False, dangling=False, linked=False, fresh=False,
                expect_refusal=False, expect_dangling_before=False, terminal=False,
                linked_consent=False):
            install = runtime / (name + ' install with spaces')
            install.mkdir()
            shutil.copy2(tree / wrapper_name, install / wrapper_name)
            game = install / 'ftesurf'
            game.mkdir()
            (game / 'fs_addons.default.txt').write_text('portable mount sentinel\n')
            (install / 'default.fmf').write_text('fixture manifest sentinel\n')
            engine_path = install / ('ftesurf64' + suffix)
            bootstrap_path = install / ('ftesurf-launcher' + suffix)
            if engine:
                shutil.copy2(actor, engine_path)
            if bootstrap:
                if dangling or linked:
                    assert not win
                    bootstrap_path.symlink_to(actor if linked else 'missing-bootstrap-target')
                else:
                    shutil.copy2(launcher if real else actor, bootstrap_path)
                    if not win:
                        bootstrap_path.chmod(0o644 if nonexec else 0o755)
            consent = install / '.ftesurf-updater/consent'
            if not fresh:
                consent.parent.mkdir()
                consent.write_bytes(b'0\n')
            if linked_consent:
                assert fresh and real and not win
                consent.parent.mkdir()
                consent.symlink_to('missing-consent-target')
            actor_log = evidence / (name + '-actor.txt')
            env = os.environ.copy()
            env.update(FTESURF_WRAPPER_ACTOR_LOG=str(actor_log), FTESURF_WRAPPER_ACTOR_EXIT=str(code))
            env['PATH'] = str(dialogs) + os.pathsep + env['PATH']
            if win:
                # Pass the /c payload raw: list2cmdline on the whole payload adds
                # C-runtime quote escaping that cmd.exe itself does not understand.
                payload = f'""{install / wrapper_name}" {subprocess.list2cmdline(args)}"'
                cmd = f'cmd.exe /d /s /c {payload}'
            else:
                cmd = ['sh', str(install / wrapper_name), *args]
            if terminal and win:
                assert not real, 'Windows real interactive prompt needs a console-input harness'
                info = subprocess.STARTUPINFO()
                info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                info.wShowWindow = 0
                result = subprocess.run(cmd, cwd=caller, env=env, timeout=30,
                                        creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=info)
            elif terminal:
                import pty
                master, slave = pty.openpty()
                try:
                    os.write(master, b'n\n')
                    result = subprocess.run(cmd, cwd=caller, env=env, stdin=slave,
                                            capture_output=True, text=True, timeout=30)
                finally:
                    os.close(slave)
                    os.close(master)
            else:
                result = subprocess.run(cmd, cwd=caller, env=env, stdin=subprocess.DEVNULL,
                                        capture_output=True, text=True, timeout=30)
            (evidence / (name + '-stdout.txt')).write_text(result.stdout or '')
            (evidence / (name + '-stderr.txt')).write_text(result.stderr or '')
            stderr_log = install / 'stderr.log'
            if stderr_log.exists():
                shutil.copy2(stderr_log, evidence / (name + '-startup.txt'))
            acted = records(actor_log)
            row = {'name': name, 'args': args, 'returncode': result.returncode, 'actors': acted,
                   'consent_after': consent.read_text() if consent.exists() else None,
                   'terminal': terminal}
            summary['cases'].append(row)
            if linked_consent:
                assert result.returncode == 1 and not acted and consent.is_symlink(), row
                assert 'linked install path:' in stderr_log.read_text(), row
                assert 'WRAPPER_DIALOG_ACTED' in result.stdout, row
                return
            if expect_refusal:
                assert result.returncode == 1 and not acted and not consent.exists(), row
                diagnostic = result.stderr if win else stderr_log.read_text()
                assert 'first launch needs consent' in diagnostic, diagnostic
                if not win:
                    assert 'WRAPPER_DIALOG_ACTED' in result.stdout, row
                return
            if nonexec or linked or (dangling and not expect_dangling_before):
                assert result.returncode != 0 and not acted, row
                assert 'not executable' in result.stderr, result.stderr
                assert 'WRAPPER_DIALOG_ACTED' in result.stdout, row
                return
            expected_actor = engine_path if real or not bootstrap or expect_dangling_before else bootstrap_path
            assert len(acted) == 1, row
            assert Path(acted[0]['argv'][0]).name == expected_actor.name, row
            assert Path(acted[0]['cwd']).resolve() == install.resolve(), row
            if real:
                prefix = ['-manifest', 'default.fmf']
            elif bootstrap and not expect_dangling_before:
                prefix = ['--offline', '--'] if fresh and not terminal else ['--']
            else:
                prefix = []
            assert acted[0]['argv'][1:] == prefix + expected_args, row
            assert result.returncode == code, row
            if not (win and terminal):
                assert 'WRAPPER_ACTOR_ACTED' in result.stdout, row
            if not win:
                assert 'WRAPPER_ACTOR_STDERR' in stderr_log.read_text(), row
            if real:
                assert (game / 'fs_addons.txt').read_bytes() == (game / 'fs_addons.default.txt').read_bytes()
                if fresh and not terminal:
                    assert not consent.exists(), row
                else:
                    assert consent.read_bytes() == b'0\n', row
                if terminal:
                    assert 'Enable automatic updates? [Y/n]' in result.stdout, row
                assert digest(bootstrap_path) == summary['launcher_sha256']

        if a.regression_control:
            if a.regression_control == 'desktop':
                run('fresh-desktop', [], [], fresh=True, real=True, expect_refusal=True)
            else:
                assert not win
                run('dangling-bootstrap', [], [], dangling=True, expect_dangling_before=True)
            summary['verdict'] = 'EXPECTED PRE-FIX ' + a.regression_control.upper() + ' FAILURE'
            print(summary['verdict'])
            return

        # This deliberately has both executables; an engine-only old wrapper
        # cannot pass by silence, a missing file, or an unacted bootstrap fixture.
        try:
            run('normal', [], [])
        except AssertionError:
            if not a.expect_before:
                raise
            row = summary['cases'][-1]
            assert row['returncode'] == 0 and len(row['actors']) == 1, row
            assert Path(row['actors'][0]['argv'][0]).name == 'ftesurf64' + suffix, row
            summary['verdict'] = 'EXPECTED PRE-FIX ROUTING FAILURE'
        else:
            assert not a.expect_before, 'pre-fix control unexpectedly selected bootstrap'
            quoted = ['-window', '+set', 'fixture.value', 'spaces "quote" back\\slash & ! %']
            run('quoted-options', quoted, quoted)
            mapargs = ['surf map with spaces', '-window', '+set', 'fixture.value', 'a value']
            normalized = ['+map', *mapargs] if win else [*mapargs[1:], '+map', mapargs[0]]
            run('map', mapargs, normalized)
            run('missing-bootstrap', quoted, quoted, bootstrap=False)
            run('bootstrap-refusal', quoted, quoted, code=23)
            run('engine-absent-bootstrap-present', [], [], engine=False)
            run('real-bootstrap', quoted, quoted, real=True)
            run('real-bootstrap-map', mapargs, normalized, real=True)
            run('fresh-nonterminal-route', quoted, quoted, fresh=True)
            run('real-fresh-nonterminal', quoted, quoted, fresh=True, real=True)
            run('fresh-terminal-route', [], [], fresh=True, terminal=True)
            if not win:
                run('real-fresh-terminal', quoted, quoted, fresh=True, real=True, terminal=True)
                run('dangling-bootstrap', [], [], dangling=True)
                run('linked-bootstrap', [], [], linked=True)
                run('linked-consent', [], [], fresh=True, real=True, linked_consent=True)
                run('debug', ['--debug', *mapargs],
                    ['-condebug', '+set', 'log_dir', 'logs', '+set', 'developer', '1', *normalized])
                run('nonexec-bootstrap', [], [], nonexec=True)
            summary['verdict'] = 'PASS'
    finally:
        context.cleanup()
        summary['runtime_retired'] = not runtime.exists()
        if not summary['runtime_retired']:
            summary['verdict'] = 'FAIL: runtime retirement'
        (evidence / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    assert summary['runtime_retired']
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
