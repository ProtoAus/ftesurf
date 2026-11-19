#!/usr/bin/env python3
"""Actual FTE -> loopback Flask protocol, map reload and release fixture.

Only synthetic fixture accounts/maps are used. Round-one scoring is explicitly
injected via the pure rule kernel in one DB transaction, NOT represented as a
real player finish or a synchronized multiplayer-start acceptance test.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import queue
import secrets
import socket
import sys
import threading
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'surfd'))

TRANSPORT_QC = r'''
float tq_transport_seen, tq_transport_printed;
void() TQ_TestFrame =
{
    if (!zone_entsready) return;
    // Fast-forward only the zero-client result screen, never a LIVE clock.
    if (tq_phase == "aborted") tq_resultsat = time - 31;
    if (strlen(tq_id))
    {
        tq_transport_seen = TRUE;
        if (mapname == tq_map && !tq_transport_printed)
        {
            tq_transport_printed = TRUE;
            if (cvar_string("tournament_reserved") != tq_id)
            {
                print("TQ_TEST_FAIL reservation missing after map reload\n");
                localcmd("quit\n");
            }
            print(sprintf("TQ_TRANSPORT_MAP %s round=%g revision=%g\n", mapname, tq_round, tq_revision));
        }
    }
    if (tq_transport_seen && !Tour_Owns())
    {
        print("TQ_TRANSPORT_RESULT PASS\n");
        localcmd("quit\n");
    }
};
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--server', type=Path, required=True)
    args = parser.parse_args()
    work = args.work_root.resolve(strict=True)
    os.environ['TMPDIR'] = str(work)
    # This helper creates its entire SURFD_HOME/maps/data under this owned TMPDIR.
    import tempfile
    tempfile.tempdir = None
    import test_tournaments as fixture
    from flask import request
    from werkzeug.serving import make_server
    import test_tournament_server as native
    S, R = fixture.S, fixture.R
    case = fixture.API()
    events = queue.Queue()
    requests = []
    failures = []
    phases = []
    expected = {}
    event_path = work / ('native-events-' + secrets.token_hex(8) + '.jsonl')
    print('Native event evidence: ' + str(event_path), flush=True)

    @S.app.after_request
    def observe(response):
        if request.path == '/api/tournaments/game':
            form = request.form
            payload = response.get_json(silent=True) or {}
            record = {k: form.get(k, '') for k in
                      ('op', 'id', 'revision', 'epoch', 'generation', 'current_map', 'enabled', 'request')}
            record.update(ok=payload.get('ok'), status=payload.get('status'), error=payload.get('error'))
            requests.append(record)
            with event_path.open('a') as stream:
                stream.write(json.dumps(record) + '\n')
            if payload.get('ok') and form.get('op') in ('arrive', 'release'):
                events.put((form['op'], payload.get('match')))
        return response

    case.setUp()
    try:
        created = case.post('create', case.tokens[0], revision=0, capacity=3,
                            round_seconds=60, occupants=1)
        if not created['ok']:
            raise RuntimeError('synthetic create failed: ' + str(created))
        match = created['match']
        for i in (1, 2):
            match = case.action(match, 'enter', i)['match']
        for who in case.whos[1:]:
            match = case.action(match, 'seat', 0, target=who)['match']
        for i in range(3):
            match = case.action(match, 'accept', i)['match']
        match = case.action(match, 'lock', 0)['match']
        while match['phase'] == 'draft':
            actor = case.whos.index(match['turn_who'])
            name = next(c['name'] for c in match['maps'] if c['status'] == 'pool')
            match = case.action(match, match['turn_kind'], actor, map=name)['match']
        # Fleet identity is p<sv_port>, not a configurable lobby_node. Rebind
        # ONLY this synthetic fixture's records before launching its native owner.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        node = 'p' + str(port)
        match['node'] = node
        match['addr'] = '127.0.0.1:' + str(port)
        with case.db:
            for table in ('lobbies', 'tournament_nodes', 'tournament_reservations', 'social_sessions'):
                case.db.execute('UPDATE ' + table + ' SET node=? WHERE node=?', (node, 'n1'))
            state = json.loads(case.db.execute('SELECT state FROM tournament_matches WHERE id=?', (match['id'],)).fetchone()[0])
            state.update(node=node, addr=match['addr'])
            case.db.execute('UPDATE tournament_matches SET node=?,state=? WHERE id=?',
                            (node, json.dumps(state), match['id']))
        expected.update(id=match['id'], maps=match['schedule'], loser=case.whos[2])

        def controller():
            try:
                for round_index in (1, 2):
                    op, arrived = events.get(timeout=35)
                    if op != 'arrive' or arrived['round_index'] != round_index:
                        raise AssertionError(('unexpected arrival', op, arrived))
                    if arrived['current_map'] != expected['maps'][round_index-1]:
                        raise AssertionError('wrong native map arrival')
                    phases.append({'native_arrival': round_index, 'map': arrived['current_map'],
                                   'revision': arrived['revision']})
                    with closing(S.connect()) as db:
                        with db:
                            db.execute('BEGIN IMMEDIATE')
                            state = json.loads(db.execute('SELECT state FROM tournament_matches WHERE id=?',
                                                          (expected['id'],)).fetchone()[0])
                            if state['revision'] != arrived['revision'] or not state['_arrived']:
                                raise AssertionError('arrival not durably acknowledged')
                            if round_index == 1:
                                for who in case.whos:
                                    state = R.transition(state, 'ready', who, '', dict(
                                        current_map=state['current_map'], generation=state['generation']))
                                state = R.transition(state, 'start', state['host'], '', {})
                                state = R.transition(state, 'go', '', '', dict(elapsed_ms=5000, tickrate=100))
                                for i, who in enumerate(case.whos):
                                    state = R.transition(state, 'score', '', '', dict(
                                        who=who, ticks=(i+1)*100, tickrate=100, elapsed_ms=10000,
                                        start_elapsed_ms=0, runid=secrets.token_hex(16),
                                        current_map=state['current_map'], generation=state['generation']))
                                state = R.transition(state, 'settle', '', '', dict(elapsed_ms=60000))
                                state = R.transition(state, 'advance', '', '', {})
                            else:
                                loser = next(p for p in state['players'] if p['who'] == expected['loser'])
                                if loser['role'] != 'eliminated' or loser['place'] != 3:
                                    raise AssertionError('elimination lost across native QC reload')
                                state = R.transition(state, 'abort', '', '', {})
                            db.execute('UPDATE tournament_matches SET state=? WHERE id=?',
                                       (json.dumps(state), state['id']))
                op, released = events.get(timeout=45)
                if op != 'release' or released['phase'] != 'aborted':
                    raise AssertionError('expected explicit restoration/release')
                phases.append({'native_release': True, 'revision': released['revision']})
            except Exception:
                failures.append(traceback.format_exc())
                with event_path.open('a') as stream:
                    stream.write(json.dumps({'controller_failure': failures[-1]}) + '\n')

        server = make_server('127.0.0.1', 0, S.app)
        http_thread = threading.Thread(target=server.serve_forever, daemon=True)
        control_thread = threading.Thread(target=controller, daemon=True)
        http_thread.start()
        control_thread.start()
        url = 'http://127.0.0.1:' + str(server.server_port)
        try:
            rc = native.run_fixture(SimpleNamespace(work_root=work, compiler=args.compiler,
                                    server=args.server, mutant_no_score=False, port=port), helper=TRANSPORT_QC,
                                    extra_maps=fixture.MAPS,
                                    extra_args=['+set', 'lobby_master', url, '+set', 'lobby_master_key', 'testkey',
                                                '+set', 'lobby_enable', '1',
                                                '+set', 'lobby_cycle', '0', '+set', 'tournament_enable', '1'],
                                    result_marker='TQ_TRANSPORT_RESULT PASS', timeout=90)
            control_thread.join(timeout=2)
        finally:
            server.shutdown()
            http_thread.join(timeout=3)
        if control_thread.is_alive():
            failures.append('controller did not finish')
        if case.db.execute('SELECT 1 FROM tournament_reservations').fetchone():
            failures.append('reservation not released')
        accepted = [r for r in requests if r['ok'] and r['op'] == 'arrive']
        if len(accepted) != 2 or {r['generation'] for r in accepted} != {'1', '2'}:
            failures.append('native did not produce both expected arrival generations')
        report = dict(ok=not failures and rc == 0, phases=phases, failures=failures,
                      scope='Real keyed native HTTP + two map loads + QC restore + explicit release; synthetic scoring and fast-forwarded result screen',
                      requests=requests)
        (work / 'transport-result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 0 if report['ok'] else 1
    finally:
        case.tearDown()


if __name__ == '__main__':
    raise SystemExit(main())
