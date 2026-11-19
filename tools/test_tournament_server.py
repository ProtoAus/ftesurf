#!/usr/bin/env python3
"""Load actual tournament QC in an owned, renderer-free FTE server fixture.

This tests native VM guards and wire construction, NOT Steam verification,
real-player finish eligibility, renderer readiness or three-client acceptance.
No real maps, player data, credentials, home directory or service is used.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

HELPER = r'''
float tq_test_done, tq_test_fail;
void(float condition, string label) TQ_Test =
{
    if (condition) print(strcat("TQ_TEST_PASS ", label, "\n"));
    else { print(strcat("TQ_TEST_FAIL ", label, "\n")); tq_test_fail = tq_test_fail + 1; }
};
void() TQ_TestFrame =
{
    local entity e;
    local int root;
    local string envelope, text;
    local float queued;
    if (tq_test_done || !zone_entsready || time < 0.2) return;
    tq_test_done = TRUE;
    TQ_Test(!Tour_Owns(), "mode off owns no reservation");
    TQ_Test(Tour_Occupants() == 0, "native empty slot occupancy");
    TQ_Test(Tour_Slots() >= 2, "native slot scan");
    TQ_Test(!Lobby_MapNameOK("x;quit") && Lobby_MapNameOK("surf_TQ+1"), "map command validation");
    envelope = "{\"v\":1,\"ok\":1,\"status\":\"ok\",\"match\":{\"id\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"revision\":1,\"phase\":\"loading\",\"host\":\"bbbbbbbbbbbb\",\"round_index\":1,\"round_total\":2,\"round_seconds\":60,\"current_map\":\"surf_tourney_fixture\",\"reserve\":\"surf_reserve\",\"players\":[{\"who\":\"bbbbbbbbbbbb\",\"name\":\"Fixture One\",\"role\":\"player\",\"ready\":0,\"accepted\":1,\"best_ticks\":0,\"tickrate\":0,\"place\":0}],\"maps\":[{\"name\":\"surf_tourney_fixture\",\"status\":\"picked\",\"by\":\"bbbbbbbbbbbb\"}]}}";
    root = json_parse(envelope);
    Tour_Adopt(json_find_object_child(root, "match"), envelope);
    json_free(root);
    TQ_Test(tq_id == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" && tq_revision == 1 && tq_round == 1, "JSON snapshot adoption");
    TQ_Test(tq_wirecount == 2, "bounded player and card rows");
    text = bufstr_get(tq_wire, 0);
    TQ_Test(strstrofs(text, "Fixture%20One", 0) >= 0, "player names percent encoded");
    e = spawn(); e.acct_who = "bbbbbbbbbbbb"; e.acct_state = ACCT_LINKED;
    e.social_token = "fixture-capability-not-a-credential";
    e.tq_streambuf = buf_create(); e.tq_stream = 5; e.tq_streamrev = tq_revision;
    Tour_RefreshRole(e);
    TQ_Test(e.tq_role == 1, "verified account owns competing seat");
    TQ_Test(!e.tq_stream && !e.tq_streambuf && !e.tq_seenrev, "identity change restarts partial snapshot");
    e.tq_streambuf = buf_create(); e.tq_stream = 5; e.tq_streamrev = tq_revision;
    e.acct_state = ACCT_UNKNOWN;
    Tour_RefreshRole(e);
    TQ_Test(e.tq_role == 0, "claimed name or handle alone grants no seat");
    TQ_Test(!e.tq_stream && !e.tq_streambuf && !e.tq_seenrev, "revoked identity restarts partial snapshot");
    e.acct_state = ACCT_LINKED; Tour_RefreshRole(e);
    tq_owned = TRUE; tq_live = TRUE; tq_goat = time - 1;
    Tour_RunStart(e);
    TQ_Test(e.tq_runround == 0, "warmup attempt cannot score");
    strunzone(tq_phase); tq_phase = strzone("live");
    Tour_RunStart(e);
    TQ_Test(e.tq_runround == 1 && e.tq_runstart > 0, "actual live start captured");
    tq_goat = time - 2;
    e.run_t_finleg = 1; e.run_t_finflags = 0; e.run_t_finticks = 50;
    e.run_movetickrate = run_t_tick;
    Tour_Finished(e);
    TQ_Test(tq_qwrite == 1, "eligible in-window main finish enqueued");
    text = bufstr_get(tq_queue, 1);
    TQ_Test(strstrofs(text, "who=bbbbbbbbbbbb", 0) >= 0 && strstrofs(text, "start_elapsed_ms=", 0) >= 0,
        "score carries account and owned window");
    TQ_Test(strstrofs(text, "runid=", 0) >= 0 && strstrofs(text, "request=", 0) >= 0,
        "score and request idempotency identifiers");
    queued = tq_qwrite;
    e.run_t_finticks = 60; Tour_Finished(e);
    TQ_Test(tq_qwrite == queued, "non-improving completion ignored");
    e.run_t_finticks = 40; e.run_t_finleg = 2; Tour_Finished(e);
    TQ_Test(tq_qwrite == queued, "non-main-course completion ignored");
    e.run_t_finleg = 1; e.run_t_finflags = TF_PRACTICE; Tour_Finished(e);
    TQ_Test(tq_qwrite == queued, "ineligible completion ignored");
    e.run_t_finflags = 0; tq_goat = time - 61; Tour_Finished(e);
    TQ_Test(tq_qwrite == queued, "late finish ignored");
    tq_goat = time - 2; e.tq_runround = 0; Tour_Finished(e);
    TQ_Test(tq_qwrite == queued, "stale or warmup start ignored");
    Tour_Hold(e); TQ_Test(e.run_pmhold && e.tq_hold, "countdown owns native movement hold");
    Tour_Unhold(e); TQ_Test(!e.run_pmhold && !e.tq_hold, "GO releases owned movement hold");
    Tour_Disconnected(e); remove(e);
    Tour_Clear();
    TQ_Test(!Tour_Owns() && !strlen(cvar_string("tournament_reserved")), "explicit restore clears reservation");
    TQ_Test(!tq_revision && !tq_round && !tq_arrived && !tq_goat, "release clears match CAS and clock state");
    text = Tour_Form("create", "&capacity=3&round_seconds=60", "fixture");
    TQ_Test(strstrofs(text, "&revision=0&", 0) >= 0 && strstrofs(text, "&generation=0&", 0) >= 0,
        "second create outgoing CAS starts at zero");
    envelope = strreplace("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "cccccccccccccccccccccccccccccccc", envelope);
    root = json_parse(envelope);
    Tour_Adopt(json_find_object_child(root, "match"), envelope); json_free(root);
    TQ_Test(tq_revision == 1 && tq_id == "cccccccccccccccccccccccccccccccc", "new match revision one accepted after release");
    envelope = strreplace("\"phase\":\"loading\"", "\"phase\":\"live\"", envelope);
    envelope = strreplace("\"status\":\"ok\"", "\"status\":\"disabled\"", envelope);
    strunzone(tq_phase); tq_phase = strzone("live"); tq_live = TRUE;
    tq_goat = time; tq_request = 987; tq_pendingop = strzone("state");
    queued = tq_qwrite;
    Tour_Reply(987, 0, envelope);
    TQ_Test(tq_broken && tq_qwrite == queued + 1 && bufstr_get(tq_queue, queued * 4) == "abort",
        "disabled live owner queues durable abort");
    tq_request = 988; tq_pendingop = strzone("state");
    Tour_Reply(988, 0, envelope);
    TQ_Test(tq_qwrite == queued + 1, "disabled polls cannot duplicate abort");
    Tour_Clear();
    if (tq_test_fail) print(sprintf("TQ_TEST_RESULT FAIL %g\n", tq_test_fail));
    else print("TQ_TEST_RESULT PASS\n");
    localcmd("quit\n");
};
'''


def fixture_bsp(path):
    """Reuse the tracked original synthetic brush fixture, never a user map.

    A zero-face Q1 model is interpreted as Hexen2 by FTE, so the original empty
    model fixture was not a valid load control. Keep that failure evidence and
    use the repository's complete textured BSP29 generator instead.
    """
    spec = importlib.util.spec_from_file_location('tq_bsp_fixture', ROOT / 'tools/p690brushfixture.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path.write_bytes(module.bsp_bytes(0))


def run_fixture(args, helper=HELPER, extra_maps=(), extra_args=(),
                result_marker='TQ_TEST_RESULT PASS', timeout=30):
    for binary in (args.compiler, args.server):
        if not binary.is_file():
            raise ValueError('missing executable: ' + str(binary))
    parent = args.work_root.resolve(strict=True)
    if not parent.is_dir():
        raise ValueError('work-root must be an existing owned directory')
    rig = Path(tempfile.mkdtemp(prefix='tournament-native-', dir=parent))
    (rig / 'OWNER.md').write_text('Owned tournament native fixture. No real account, content, player data or services.\n')
    game = rig / 'ftesurf'
    (game / 'maps').mkdir(parents=True)
    (game / 'cfg').mkdir()
    fixture_bsp(game / 'maps/surf_tourney_fixture.bsp')
    for name in extra_maps:
        if '/' in name or '\\' in name or not name.startswith('surf_'):
            raise ValueError('invalid fixture map name')
        fixture_bsp(game / ('maps/' + name + '.bsp'))
    # Read-only asset references are to THIS source checkout, never a player install.
    for name in ('models', 'gfx', 'sound', 'textures', 'glsl', 'scripts'):
        source = ROOT / 'ftesurf' / name
        if source.is_dir():
            (game / name).symlink_to(source, target_is_directory=True)
    (rig / 'default.fmf').write_text('FTEMANIFEST 1\nGAME "Tournament Fixture"\nNAME "Tournament Fixture"\n'
                                    'BASEGAME "ftesurf"\nDISABLEHOMEDIR 1\n')
    (rig / 'fixture.qc').write_text(helper)
    main_source = (ROOT / 'src/server/sv_main.qc').read_text()
    marker = '\tTour_Frame();'
    if main_source.count(marker) != 1:
        raise RuntimeError('StartFrame integration marker must be unique')
    (rig / 'main.qc').write_text(main_source.replace(marker, marker + '\n\tTQ_TestFrame();'))
    manifest = (ROOT / 'src/sv_progs.src').read_text().splitlines()
    lines = [str(game / 'qwprogs.dat')]
    for line in manifest[1:]:
        filename = line.split('//', 1)[0].strip()
        if not filename:
            continue
        if filename == 'server/sv_main.qc':
            lines += [str(rig / 'fixture.qc'), str(rig / 'main.qc')]
        elif filename == 'server/sv_tournament.qc' and args.mutant_no_score:
            text = (ROOT / 'src' / filename).read_text()
            hook = 'void(entity e) Tour_Finished =\n{'
            if text.count(hook) != 1:
                raise RuntimeError('finish consumer marker must be unique')
            (rig / 'mutant.qc').write_text(text.replace(hook, hook + '\n\treturn;'))
            lines.append(str(rig / 'mutant.qc'))
        else:
            lines.append(str(ROOT / 'src' / filename))
    (rig / 'fixture.src').write_text('\n'.join(lines) + '\n')
    compiled = subprocess.run([str(args.compiler), '-O2', '-Wall', '-v', '-srcfile', str(rig / 'fixture.src')],
                              cwd=ROOT / 'src', capture_output=True, timeout=120)
    (rig / 'compile.log').write_bytes(compiled.stdout + compiled.stderr)
    if compiled.returncode or not (game / 'qwprogs.dat').is_file():
        raise RuntimeError('fixture compile failed: ' + str(rig / 'compile.log'))
    # Reserve only a fresh loopback UDP endpoint; never address an existing game.
    port = getattr(args, 'port', None)
    if port is None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
    command = [str(args.server), '-nohome', '-nobrowse', '-basedir', str(rig),
               '-manifest', str(rig / 'default.fmf'), '+set', 'sv_public', '0',
               '+set', 'sv_listen_qw', '127.0.0.1:' + str(port), '+set', 'sv_port', str(port),
               '+set', 'cfg_save_auto', '0', '+set', 'lobby_enable', '0',
               '+set', 'tournament_enable', '0', '+set', 'sv_mintic', '0.015',
               '+set', 'sv_maxtic', '0.015', *extra_args, '+map', 'surf_tourney_fixture']
    env = dict(os.environ, HOME=str(rig), XDG_CONFIG_HOME=str(rig / 'config'),
               XDG_DATA_HOME=str(rig / 'data'), XDG_CACHE_HOME=str(rig / 'cache'))
    try:
        result = subprocess.run(command, cwd=rig, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=timeout)
        log = result.stdout + result.stderr
    except subprocess.TimeoutExpired as exc:
        (rig / 'runtime.log').write_bytes((exc.stdout or b'') + (exc.stderr or b''))
        raise RuntimeError('owned native fixture timed out: ' + str(rig / 'runtime.log')) from exc
    (rig / 'runtime.log').write_bytes(log)
    text = log.decode(errors='replace')
    passed = result_marker in text and 'TQ_TEST_FAIL ' not in text
    report = dict(ok=passed, mutant=args.mutant_no_score, rig=str(rig),
                  compiler_sha256=hashlib.sha256(args.compiler.read_bytes()).hexdigest(),
                  server_sha256=hashlib.sha256(args.server.read_bytes()).hexdigest(),
                  checks=text.count('TQ_TEST_PASS '), native_returncode=result.returncode,
                  limitations='Native VM/guard fixture, not live Steam/player/renderer acceptance')
    (rig / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not passed:
        print('\n'.join(line for line in text.splitlines() if 'TQ_TEST_' in line))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--mutant-no-score', action='store_true', help='negative control: bypass consumer')
    return run_fixture(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
