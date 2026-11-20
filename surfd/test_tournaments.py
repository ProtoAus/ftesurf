#!/usr/bin/env python3
"""Owned synthetic SQLite/Flask fixtures; no HTTP, credentials or player corpus."""
import copy
import importlib
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

HOME = Path(tempfile.mkdtemp(prefix='surfd-tournaments-'))
(HOME / 'surfd.env').write_text('SURFD_KEY=testkey\n')
for name in ('maps', 'zones', 'local', 'runs', 'tools', 'game'):
    (HOME / name).mkdir()
MAPS = ['surf_Alpha', 'surf_b', 'surf_c', 'surf_d', 'surf_e', 'surf_f', 'surf_g', 'surf_h', 'surf_i']
for name in MAPS:
    (HOME / 'maps' / (name + '.bsp')).write_bytes(b'fixture ' + name.encode())
    (HOME / 'zones' / (name + '.json')).write_text('{}')
os.environ.update(SURFD_HOME=str(HOME), SURFD_DB=str(HOME / 'test.db'),
                  SURFD_ENV=str(HOME / 'surfd.env'), SURFD_MAPS=str(HOME / 'maps'),
                  SURFD_ZONES=str(HOME / 'zones'), SURFD_ZONES_LOCAL=str(HOME / 'local'),
                  SURFD_RUNS=str(HOME / 'runs'), SURFD_GAME=str(HOME / 'game'),
                  SURFD_TOOLS=str(HOME / 'tools'), SURFD_TOURNAMENTS='1',
                  SURFD_PUBLIC_HOST='',
                  SURFD_TOURNAMENT_QUALIFICATIONS=str(HOME / 'qualifications.json'),
                  SURFD_MOMTRACKS=str(HOME / 'momtracks.tsv'))
import surfd as S
import accounts
import social
import tournaments as T
import tournament_rules as R


# All approvals and observations below are deliberately synthetic, not native proofs.
def pin_for(name):
    st = (HOME / 'maps' / (name + '.bsp')).stat()
    return dict(mapcrc='12345678', zonepin='b'*64, gamemode='surf', sha256='c'*64,
                map_stamp=[st.st_size, st.st_mtime_ns, st.st_ctime_ns])


def seed_catalogue():
    listed = Path(S.mapmanifest.LIST_PATH)
    listed.parent.mkdir(parents=True, exist_ok=True)
    listed.write_text('FTESURF-MAPDL 1\n' + ''.join('dl %s surf m 1 1 2026-01-01 0 1 0\n' % n for n in MAPS))
    (HOME / 'momtracks.tsv').write_text(''.join(n.lower()+'\t0\t1\n' for n in MAPS))
    (HOME / 'qualifications.json').write_text(json.dumps(dict(v=1, maps={n: {'default': dict(approved=1, **pin_for(n))} for n in MAPS})))
    S._mt.update(at=0, tier=None)


seed_catalogue()
POOL = {n: dict(name=n, kind='surf', tier=1, pin=pin_for(n)) for n in MAPS}


def observation(m):
    return dict(current_map=m['current_map'], generation=m['generation'], round=m['round_index'],
                ruleset=m['ruleset_id'], movement=R.PROFILES[m['settings']['profile']]['movement'],
                tick_us=m['settings']['tick_us'], clock_us=m['settings']['tick_us'],
                gamemode=m['settings']['kind'], mapcrc='12345678', zonepin='b'*64, zonegen=1)


def tearDownModule():
    logging.shutdown()
    keeper = S._KEEPER.get('conn')
    if keeper:
        keeper.close()
    shutil.rmtree(HOME)


class Rules(unittest.TestCase):
    def lobby(self, n=3):
        m = R.create('a'*32, 'node', 'Fixture', '127.0.0.1:27510', 'host', 'Host',
                     dict(capacity=8, round_seconds=60))
        for i in range(1, n):
            who = 'p' + str(i)
            m = R.transition(m, 'enter', who, who, {})
            m = R.transition(m, 'seat', 'host', '', dict(target=who))
        for p in list(m['players']):
            m = R.transition(m, 'accept', p['who'], '', {})
        return m

    def drafted(self, n=3):
        m = R.transition(self.lobby(n), 'lock', 'host', '', {}, POOL)
        while m['phase'] == 'draft':
            card = next(c for c in m['maps'] if c['status'] == 'pool')
            m = R.transition(m, m['turn_kind'], m['turn_who'], '', dict(map=card['name']))
        return m

    def live(self, n=3):
        m = self.drafted(n)
        data = observation(m)
        m = R.transition(m, 'arrive', '', '', data)
        for p in list(R.competitors(m)):
            m = R.transition(m, 'ready', p['who'], '', data)
        m = R.transition(m, 'start', 'host', '', observation(m))
        return R.transition(m, 'go', '', '', dict(observation(m), elapsed_ms=5000, tickrate=1000000/15000))

    def score(self, m, who, ticks, **extra):
        data = dict(observation(m), who=who,
                    ticks=ticks, tickrate=1000000/15000, elapsed_ms=10000, start_elapsed_ms=0,
                    runid=('%016x' % (len(m['_runs'])+1)))
        data.update(extra)
        return R.transition(m, 'score', '', '', data)

    # P1650 helpers: a wider synthetic pool admits 4+ competitors; play() takes a loading round to live.
    def wide(self, n):
        return {('surf_w%02d' % i): dict(name='surf_w%02d' % i, kind='surf', tier=1, pin=pin_for(MAPS[0]))
                for i in range(3 * n)}

    def play(self, m):
        data = observation(m)
        m = R.transition(m, 'arrive', '', '', data)
        for p in list(R.competitors(m)):
            m = R.transition(m, 'ready', p['who'], '', data)
        m = R.transition(m, 'start', 'host', '', observation(m))
        return R.transition(m, 'go', '', '', dict(observation(m), elapsed_ms=5000, tickrate=1000000/15000))

    def settle(self, m, scores=()):
        for who, ticks in scores:
            m = self.score(m, who, ticks)
        return R.transition(m, 'settle', '', '', dict(observation(m), elapsed_ms=60000))

    def roles(self, m):
        return {p['who']: (p['role'], p['place']) for p in m['players']}

    def test_alpha_settings_actions_refuse_without_mutation_or_invented_consent(self):
        m = self.lobby(2)
        for key in ('settings', 'ruleset_id', '_pins', '_zonegen'):
            m.pop(key)
        original = copy.deepcopy(m)
        data = dict(capacity=2, round_seconds=60, kind='surf', tiers='7', profile='default', pool='-')
        for op in ('configure', 'lock', 'start'):
            with self.assertRaisesRegex(R.Refusal, 'Pre-Beta.*cancel'):
                R.transition(m, op, 'host', '', data, POOL)
            self.assertEqual(m, original)
        self.assertEqual(R.transition(m, 'cancel', 'host', '', {})['phase'], 'cancelled')

    def test_spectator_and_entrant_caps(self):
        m = self.lobby(2)
        for i in range(64):
            m = R.transition(m, 'enter', 's'+str(i), 'Spectator', {})
        with self.assertRaisesRegex(R.Refusal, 'spectator roster full'):
            R.transition(m, 'enter', 'overflow', '', {})
        with self.assertRaisesRegex(R.Refusal, 'spectator roster full'):
            R.transition(m, 'seat', 'host', '', dict(target='host'))
        # Entering an existing account at the cap is still idempotent.
        self.assertEqual(len(R.transition(m, 'enter', 's0', '', {})['players']), 66)
        full = self.lobby(8)
        full = R.transition(full, 'enter', 'ninth', '', {})
        with self.assertRaisesRegex(R.Refusal, 'seats full'):
            R.transition(full, 'seat', 'host', '', dict(target='ninth'))
        with self.assertRaises(R.Refusal):
            R.create('a'*32, 'n', '', '', 'host', '', dict(capacity=9, round_seconds=60))

    def test_draft_consent_turn_pool_and_no_mutation_on_refusal(self):
        m = self.lobby()
        original = copy.deepcopy(m)
        with self.assertRaisesRegex(R.Refusal, '3N'):
            R.transition(m, 'lock', 'host', '', {}, {n: POOL[n] for n in MAPS[:8]})
        self.assertEqual(m, original)
        m['players'][1]['accepted'] = 0
        with self.assertRaisesRegex(R.Refusal, 'accept'):
            R.transition(m, 'lock', 'host', '', {}, POOL)
        m = R.transition(self.lobby(), 'lock', 'host', '', {}, POOL)
        with self.assertRaisesRegex(R.Refusal, 'turn'):
            R.transition(m, 'ban', 'intruder', '', dict(map=MAPS[0]))
        first = m['turn_who']
        m = R.transition(m, 'ban', first, '', dict(map=MAPS[0]))
        with self.assertRaises(R.Refusal):
            R.transition(m, 'ban', m['turn_who'], '', dict(map=MAPS[0]))
        loaded = self.drafted()
        self.assertEqual((len(loaded['schedule']), loaded['round_total']), (2, 2))
        self.assertNotIn(loaded['reserve'], loaded['schedule'])
        self.assertEqual(len(set(loaded['schedule'] + [loaded['reserve']])), 3)

    def test_seat_p1650_clears_only_the_moved_players_consent_and_pool_is_exactly_3n(self):
        m = self.lobby(2)
        self.assertTrue(all(p['accepted'] for p in R.competitors(m)))
        m = R.transition(m, 'enter', 'new', 'New', {})
        m = R.transition(m, 'seat', 'host', '', dict(target='new'))
        self.assertEqual({p['who']: p['accepted'] for p in m['players']}, dict(host=1, p1=1, new=0))
        m = R.transition(m, 'seat', 'host', '', dict(target='p1'))
        self.assertEqual({p['who']: (p['role'], p['accepted']) for p in m['players']},
                         dict(host=('player', 1), p1=('spectator', 0), new=('player', 0)))
        drafted = R.transition(self.lobby(2), 'lock', 'host', '', {}, POOL)
        self.assertEqual(len(drafted['maps']), 6)

    def test_leave_p1650_before_launch_returns_to_lobby(self):
        m = R.transition(self.lobby(3), 'lock', 'host', '', {}, POOL)
        m = R.transition(m, 'ban', m['turn_who'], '', dict(map=m['maps'][0]['name']))
        left = R.transition(m, 'leave', 'p1', '', {})
        self.assertEqual((left['phase'], [p['who'] for p in left['players']]), ('lobby', ['host', 'p2']))
        self.assertTrue(all(p['accepted'] for p in left['players']))
        for key, empty in (('maps', []), ('schedule', []), ('reserve', ''), ('turn_who', ''), ('turn_kind', ''),
                           ('_order', []), ('_turn', 0), ('round_index', 0), ('generation', 0),
                           ('round_total', 0), ('current_map', '')):
            self.assertEqual(left[key], empty, key)
        self.assertEqual(left['note'], 'p1 left: back to the lobby. The host can start the draft again.')
        # The live server QC holds a match whose ruleset changes outside lobby, so it waits for the next lock.
        self.assertEqual(left['ruleset_id'], m['ruleset_id'])
        self.assertEqual(R.transition(left, 'lock', 'host', '', {}, POOL)['phase'], 'draft')
        # A server-hosted match still loading its first map has not launched either.
        self.assertEqual(R.transition(self.drafted(3), 'leave', 'p2', '', {})['phase'], 'lobby')
        self.assertEqual(R.transition(m, 'leave', 'host', '', {})['phase'], 'cancelled')

    def test_leave_p1650_after_launch_forfeits_and_play_continues(self):
        m = self.drafted(3)
        m['menu_started'] = 1
        m = R.transition(m, 'leave', 'p1', '', {})
        self.assertEqual((m['phase'], self.roles(m)['p1'], m['note']), ('loading', ('eliminated', 3), 'p1 left the tournament.'))
        # The leaver neither readies nor blocks Start.
        m = self.play(m)
        self.assertEqual(m['phase'], 'live')
        m = R.transition(m, 'leave', 'host', '', {})
        self.assertEqual((m['phase'], m['outcome']), ('finished', 'winner'))
        self.assertEqual(self.roles(m), dict(host=('eliminated', 2), p1=('eliminated', 3), p2=('player', 1)))
        self.assertEqual(m['note'], 'Host left the tournament. p2 wins!')
        live = R.transition(self.live(3), 'leave', 'p2', '', {})
        self.assertEqual((live['phase'], self.roles(live)['p2']), ('live', ('eliminated', 3)))
        # A decided winner leaving the results screen keeps the result.
        won = self.settle(self.live(2), [('host', 100), ('p1', 200)])
        self.assertEqual(self.roles(R.transition(won, 'leave', 'host', '', {})), self.roles(won))

    def test_unseat_p1650_in_draft_or_ready_check_returns_to_lobby(self):
        m = R.transition(R.transition(self.lobby(3), 'enter', 'x', 'X', {}), 'lock', 'host', '', {}, POOL)
        out = R.transition(m, 'seat', 'host', '', dict(target='p2'))
        self.assertEqual((out['phase'], out['maps'], self.roles(out)['p2'][0]), ('lobby', [], 'spectator'))
        self.assertEqual({p['who']: p['accepted'] for p in out['players']}, dict(host=1, p1=1, p2=0, x=0))
        self.assertEqual(out['note'], 'p2 was moved to spectators: back to the lobby. The host can start the draft again.')
        for actor, target in (('host', 'x'), ('p1', 'p2')):
            with self.assertRaisesRegex(R.Refusal, 'roster frozen|host only'):
                R.transition(m, 'seat', actor, '', dict(target=target))
        self.assertEqual(R.transition(self.drafted(3), 'seat', 'host', '', dict(target='p1'))['phase'], 'lobby')
        started = self.drafted(3)
        started['menu_started'] = 1
        with self.assertRaisesRegex(R.Refusal, 'roster frozen'):
            R.transition(started, 'seat', 'host', '', dict(target='p1'))
        arrived = R.transition(self.drafted(3), 'arrive', '', '', observation(self.drafted(3)))
        with self.assertRaisesRegex(R.Refusal, 'roster frozen'):
            R.transition(arrived, 'seat', 'host', '', dict(observation(arrived), target='p1'))

    def test_readiness_arrival_generation_and_countdown(self):
        m = self.drafted(2)
        data = observation(m)
        with self.assertRaises(R.Refusal):
            R.transition(m, 'ready', 'host', '', data)
        m = R.transition(m, 'arrive', '', '', data)
        m = R.transition(m, 'ready', 'host', '', data)
        m = R.transition(m, 'arrive', '', '', data)
        self.assertEqual(m['players'][0]['ready'], 1)
        with self.assertRaisesRegex(R.Refusal, 'every'):
            R.transition(m, 'start', 'host', '', observation(m))
        with self.assertRaisesRegex(R.Refusal, 'generation'):
            R.transition(m, 'ready', 'p1', '', dict(observation(m), generation=2))
        m = R.transition(m, 'ready', 'p1', '', data)
        m = R.transition(m, 'start', 'host', '', observation(m))
        with self.assertRaises(R.Refusal):
            R.transition(m, 'go', '', '', dict(observation(m), elapsed_ms=4999, tickrate=1000000/15000))
        m = R.transition(m, 'go', '', '', dict(observation(m), elapsed_ms=5000, tickrate=1000000/15000))
        self.assertEqual(m['phase'], 'live')
        with self.assertRaisesRegex(R.Refusal, 'first GO'):
            R.transition(m, 'cancel', 'host', '', {})

    def test_strict_scores_and_unique_dnf(self):
        m = self.live()
        for extra in (dict(elapsed_ms=60001), dict(start_elapsed_ms=10000),
                      dict(current_map='surf_wrong'), dict(generation=2), dict(tickrate=66),
                      dict(runid='legacy'), dict(ticks=0), dict(ticks=6001),
                      dict(who='stranger'), dict(start_elapsed_ms='-1'),
                      dict(elapsed_ms=1), dict(start_elapsed_ms=9999)):
            with self.assertRaises(R.Refusal, msg=str(extra)):
                self.score(m, 'host', 100, **extra) if 'who' not in extra and 'ticks' not in extra else self.score(
                    m, extra.get('who', 'host'), extra.get('ticks', 100),
                    **{k:v for k,v in extra.items() if k not in ('who', 'ticks')})
        m = self.score(m, 'host', 100, elapsed_ms=60000)
        with self.assertRaisesRegex(R.Refusal, 'already scored'):
            self.score(m, 'host', 90, runid='0000000000000001')
        m = self.score(m, 'p1', 200)
        with self.assertRaises(R.Refusal):
            R.transition(m, 'settle', '', '', dict(observation(m), elapsed_ms=59999))
        result = R.transition(m, 'settle', '', '', dict(observation(m), elapsed_ms=60000))
        self.assertEqual(result['phase'], 'results')
        self.assertEqual((result['players'][2]['role'], result['players'][2]['place']), ('eliminated', 3))
        next_round = R.transition(result, 'advance', '', '', {})
        self.assertEqual((next_round['phase'], next_round['generation']), ('loading', 2))
        self.assertTrue(all(p['best_ticks'] == p['ready'] == 0 for p in next_round['players']))
        self.assertEqual(len(next_round['_runs']), 2)
        # Legacy previous-map event remains globally consumed even across rounds.
        next_round['phase'], next_round['_rate'] = 'live', 1000000/15000
        with self.assertRaisesRegex(R.Refusal, 'already scored'):
            self.score(next_round, 'host', 100, runid='0000000000000001')

    def test_settle_p1650_nobody_finished_everyone_goes_through(self):
        m = self.settle(self.live())
        self.assertEqual((m['phase'], m.get('outcome')), ('results', None))
        self.assertTrue(all(p['role'] == 'player' and p['place'] == 0 for p in m['players']))
        self.assertEqual(m['note'], 'Nobody finished %s: everyone goes through.' % m['current_map'])
        self.assertEqual(next(c for c in m['maps'] if c['name'] == m['current_map'])['status'], 'played')

    def test_settle_p1650_every_non_finisher_is_out(self):
        m = self.settle(self.live(), [('host', 100)])
        self.assertEqual(self.roles(m), dict(host=('player', 1), p1=('eliminated', 2), p2=('eliminated', 2)))
        self.assertEqual((m['phase'], m['outcome']), ('results', 'winner'))
        self.assertEqual(m['note'], 'p1 and p2 did not finish and are out. Host wins!')
        m = self.settle(self.live(), [('host', 100), ('p1', 200)])
        self.assertEqual(self.roles(m)['p2'], ('eliminated', 3))
        self.assertEqual((m['phase'], m['note']), ('results', 'p2 did not finish and is out.'))
        # A DNF goes out even when a finisher was slower than everyone else.
        m = R.transition(self.lobby(4), 'lock', 'host', '', {}, self.wide(4))
        while m['phase'] == 'draft':
            card = next(c for c in m['maps'] if c['status'] == 'pool')
            m = R.transition(m, m['turn_kind'], m['turn_who'], '', dict(map=card['name']))
        m = self.settle(self.play(m), [('host', 100), ('p1', 600)])
        self.assertEqual(self.roles(m), dict(host=('player', 0), p1=('player', 0), p2=('eliminated', 3), p3=('eliminated', 3)))
        self.assertEqual(m['note'], 'p2 and p3 did not finish and are out.')

    def test_settle_p1650_slowest_and_tied_slowest_are_out(self):
        m = self.settle(self.live(), [('host', 100), ('p1', 200), ('p2', 300)])
        self.assertEqual(self.roles(m), dict(host=('player', 0), p1=('player', 0), p2=('eliminated', 3)))
        self.assertEqual(m['note'], 'p2 had the slowest time and is out.')
        m = self.settle(self.live(), [('host', 100), ('p1', 200), ('p2', 200)])
        self.assertEqual(self.roles(m), dict(host=('player', 1), p1=('eliminated', 2), p2=('eliminated', 2)))
        self.assertEqual((m['phase'], m['outcome']), ('results', 'winner'))
        self.assertEqual(m['note'], 'p1 and p2 tied for the slowest time and are out. Host wins!')
        m = self.settle(self.live(), [('host', 100), ('p1', 100), ('p2', 100)])
        self.assertEqual((m['phase'], m['note']), ('results', 'Everyone tied: everyone goes through.'))
        self.assertTrue(all(p['role'] == 'player' for p in m['players']))

    def test_advance_p1650_plays_reserve_then_shares_first(self):
        m = self.settle(self.live())
        reserve = m['reserve']
        m = R.transition(m, 'advance', '', '', {})
        self.assertEqual((m['phase'], m['round_index'], m['round_total']), ('loading', 2, 2))
        m = self.settle(self.play(m))
        m = R.transition(m, 'advance', '', '', {})
        # Scheduled rounds are used up with three survivors: the reserve becomes round 3.
        self.assertEqual((m['phase'], m['round_index'], m['generation'], m['round_total']), ('loading', 3, 3, 3))
        self.assertEqual((m['current_map'], m['schedule'][-1], len(m['schedule'])), (reserve, reserve, 3))
        self.assertEqual(next(c for c in m['maps'] if c['name'] == reserve)['status'], 'picked')
        m = self.settle(self.play(m))
        m = R.transition(m, 'advance', '', '', {})
        self.assertEqual((m['phase'], m['outcome']), ('finished', 'shared'))
        self.assertEqual([p['place'] for p in m['players']], [1, 1, 1])
        self.assertEqual(m['note'], 'Out of maps: Host, p1 and p2 share first place.')

    def test_advance_p1650_one_survivor_finishes_early_and_eighth_round_observes(self):
        # Two DNFs in round one of three scheduled rounds leave a winner: no further round loads.
        m = self.settle(self.live(), [('host', 100)])
        self.assertEqual(R.transition(m, 'advance', '', '', {})['phase'], 'finished')
        m = self.drafted(2)
        m.update(round_index=8, generation=8)
        self.assertEqual(R.observe(m, observation(m), latched=False), 1)

    def test_unique_slowest_winner(self):
        m = self.live(2)
        m = self.score(m, 'host', 100)
        m = self.score(m, 'p1', 200)
        m = R.transition(m, 'settle', '', '', dict(observation(m), elapsed_ms=60000))
        self.assertEqual([p['place'] for p in m['players']], [1,2])
        m = R.transition(m, 'advance', '', '', {})
        self.assertEqual(m['phase'], 'finished')
        with self.assertRaises(R.Refusal):
            R.transition(m, 'release', '', '', {})
        self.assertEqual(R.transition(m, 'release', '', '', dict(restored='1'))['phase'], 'finished')

    def test_abort_p1650_reasons_read_plainly(self):
        m = self.live()
        for reason, text in (
                ('alpha_lobby_timeout', 'the tournament timed out waiting in the lobby or draft'),
                ('loading_timeout', 'players did not get ready in time'),
                ('host_gone', 'the host left the server'),
                ('map_change_failed', 'the server could not load the map'),
                ('unqualified_loaded_table', "the map's zones or rules changed"),
                ('loaded_ruleset_changed', "the map's zones or rules changed"),
                ('interrupted_live_round', 'the server lost contact with the tournament service'),
                ('service_interrupted', 'the server lost contact with the tournament service'),
                ('reservation_race', 'someone else joined the server first'),
                ('competitor_lost_during_countdown', 'the server stopped the match'),
                (None, 'the server stopped the match')):
            out = R.transition(m, 'abort', '', '', {} if reason is None else dict(reason=reason))
            self.assertEqual((out['phase'], out['outcome'], out['note']), ('aborted', 'no-contest', 'No contest: %s.' % text))

    def test_autostart_p1650_vouches_for_present_competitors_host_start_unchanged(self):
        m = self.drafted(2)
        data = observation(m)
        with self.assertRaisesRegex(R.Refusal, 'arrived'):
            R.transition(m, 'autostart', '', '', data)
        m = R.transition(m, 'arrive', '', '', data)
        m = R.transition(m, 'ready', 'host', '', data)
        # Host start still needs every survivor's own ready.
        with self.assertRaisesRegex(R.Refusal, 'every'):
            R.transition(m, 'start', 'host', '', data)
        with self.assertRaisesRegex(R.Refusal, 'zone generation'):
            R.transition(m, 'autostart', '', '', dict(data, zonegen=2))
        # S11: autostart marks every survivor it does not name in `absent` ready.
        for extra in ({}, dict(absent='')):
            out = R.transition(m, 'autostart', '', '', dict(data, **extra))
            self.assertEqual((out['phase'], [p['ready'] for p in out['players']]), ('countdown', [1, 1]))
        m = R.transition(m, 'ready', 'p1', '', data)
        self.assertEqual(R.transition(m, 'start', 'host', '', data)['phase'], 'countdown')
        with self.assertRaisesRegex(R.Refusal, 'host only'):
            R.transition(m, 'start', 'p1', '', data)

    def test_autostart_p1650_absent_competitors_forfeit_first(self):
        m = self.drafted(3)
        data = observation(m)
        m = R.transition(R.transition(m, 'arrive', '', '', data), 'ready', 'host', '', data)
        for absent in ('host', 'stranger', 'p1,p1', 'p1,', ',p1'):
            with self.assertRaisesRegex(R.Refusal, 'absent list invalid', msg=absent):
                R.transition(m, 'autostart', '', '', dict(data, absent=absent))
        # p2 is vouched for (not named), p1 is forfeited.
        out = R.transition(m, 'autostart', '', '', dict(data, absent='p1'))
        self.assertEqual((out['phase'], self.roles(out)['p1'], out['note']), ('countdown', ('eliminated', 3), "p1 didn't arrive and is out."))
        self.assertEqual([p['ready'] for p in R.competitors(out)], [1, 1])
        out = R.transition(m, 'autostart', '', '', dict(data, absent='p1,p2'))
        self.assertEqual((out['phase'], out['outcome']), ('finished', 'winner'))
        self.assertEqual(self.roles(out), dict(host=('player', 1), p1=('eliminated', 2), p2=('eliminated', 2)))
        self.assertEqual(out['note'], "p1 and p2 didn't arrive and are out. Host wins!")
        # Everyone absent: no contest, and nobody is forfeited or placed.
        arrived = R.transition(self.drafted(3), 'arrive', '', '', data)
        nobody = R.transition(arrived, 'autostart', '', '', dict(data, absent='p2,host,p1'))
        self.assertEqual((nobody['phase'], nobody['outcome'], nobody['note']), ('aborted', 'no-contest', 'No contest: nobody arrived.'))
        self.assertEqual(nobody['players'], arrived['players'])
        forfeited = R.transition(m, 'leave', 'p1', '', {})
        with self.assertRaisesRegex(R.Refusal, 'absent list invalid'):
            R.transition(forfeited, 'autostart', '', '', dict(data, absent='p1'))

    def test_launched_p1650_is_sticky_in_later_rounds_of_a_server_match(self):
        m = R.transition(self.settle(self.live(3)), 'advance', '', '', {})
        self.assertEqual((m['phase'], m['round_index'], m['_arrived'], m.get('menu_started')), ('loading', 2, 0, None))
        left = R.transition(m, 'leave', 'p1', '', {})
        self.assertEqual((left['phase'], self.roles(left)['p1']), ('loading', ('eliminated', 3)))
        host = R.transition(m, 'leave', 'host', '', {})
        self.assertEqual((host['phase'], self.roles(host)['host']), ('loading', ('eliminated', 3)))
        with self.assertRaisesRegex(R.Refusal, 'roster frozen'):
            R.transition(m, 'seat', 'host', '', dict(target='p2'))
        # Each latch alone keeps the match launched.
        for latch in (dict(_launched=1), dict(_started=1), dict(round_index=2)):
            bare = dict(self.drafted(3), _launched=0, _started=0)
            bare.update(latch)
            self.assertTrue(R.launched(bare), latch)
            self.assertEqual(R.transition(bare, 'leave', 'p1', '', {})['phase'], 'loading', latch)
        self.assertFalse(R.launched(dict(self.drafted(3))))
        self.assertEqual(R.transition(self.drafted(3), 'arrive', '', '', observation(self.drafted(3)))['_launched'], 1)

    def test_configure_host_freeze_capacity_and_consent_invalidation(self):
        m = self.lobby(3)
        data = dict(kind='surf', tiers='7', profile='default', pool='-', capacity=8, round_seconds=60)
        unchanged = R.transition(m, 'configure', 'host', '', data)
        self.assertTrue(all(p['accepted'] for p in unchanged['players']))
        for actor, change in (('p1', {}), ('host', dict(capacity=2))):
            with self.assertRaises(R.Refusal):
                R.transition(m, 'configure', actor, '', dict(data, **change))
        changed = R.transition(m, 'configure', 'host', '', dict(data, profile='ag-250'))
        self.assertEqual(changed['settings']['tick_us'], 4000)
        self.assertTrue(all(p['accepted'] == p['ready'] == p['menu_ready'] == 0 for p in changed['players']))
        drafted = self.drafted()
        with self.assertRaisesRegex(R.Refusal, 'frozen'):
            R.transition(drafted, 'configure', 'host', '', data)
        self.assertEqual(m['settings']['profile'], 'default')

    def test_default_profile_keeps_each_kind_tick_p1639(self):
        data = dict(kind='bhop', tiers='7', profile='default', pool='-', capacity=8, round_seconds=60)
        bhop = R.transition(self.lobby(3), 'configure', 'host', '', data)
        self.assertEqual(bhop['settings']['tick_us'], 10000)
        surf = R.transition(self.lobby(3), 'configure', 'host', '', dict(data, kind='surf'))
        self.assertEqual(surf['settings']['tick_us'], 15000)
        fixed = R.transition(self.lobby(3), 'configure', 'host', '', dict(data, profile='ag-100', kind='surf'))
        self.assertEqual(fixed['settings']['tick_us'], 10000)
        # A default node between matches may sit at either kind's tick; other profiles only at their own.
        for tick in (10000, 15000):
            row = dict(movement='default', tick_us=tick, clock_us=tick)
            self.assertTrue(T.compatible(row, bhop['settings']) and T.compatible(row, surf['settings']))
        self.assertFalse(T.compatible(dict(movement='default', tick_us=10000, clock_us=15000), bhop['settings']))
        self.assertFalse(T.compatible(dict(movement='ag100-v1', tick_us=15000, clock_us=15000), fixed['settings']))
        # Arrival on a bhop round needs bhop's tick; the surf tick is refused.
        m = self.drafted(2)
        m['settings'] = dict(m['settings'], kind='bhop', tick_us=10000)
        good = dict(observation(m), gamemode='bhop', tick_us=10000, clock_us=10000)
        for key in ('tick_us', 'clock_us'):
            with self.assertRaisesRegex(R.Refusal, 'wrong ' + key):
                R.observe(m, dict(good, **{key: 15000}), latched=False)
        # A room persisted with the pre-P1639 bhop tick is refused rather than locked at 66 tick.
        with self.assertRaisesRegex(R.Refusal, 'Pre-Beta'):
            R.require_current_settings(dict(settings=dict(bhop['settings'], tick_us=15000)))
        R.require_current_settings(bhop)

    def test_auto_candidates_more_than_24_but_only_3_actual_competitors_drafted(self):
        pool = {('surf_fixture%d' % i): dict(name='surf_fixture%d' % i, kind='surf', tier=1, pin=pin_for(MAPS[0])) for i in range(30)}
        m = R.transition(self.lobby(2), 'lock', 'host', '', {}, pool)
        self.assertEqual((len(m['maps']), len(m['_pins'])), (6, 6))
        self.assertRegex(m['ruleset_id'], r'^[0-9a-f]{64}$')
        self.assertNotIn('_pins', R.public(m))
        with self.assertRaisesRegex(R.Refusal, 'records'):
            R.transition(self.lobby(2), 'lock', 'host', '', {}, MAPS)

    def test_actual_observations_and_bindings_all_discriminate(self):
        m = self.drafted(2)
        data = observation(m)
        bads = dict(movement='ag100-v1', tick_us=10000, clock_us=10000, gamemode='bhop',
                    mapcrc='00000000', zonepin='c'*64, ruleset='0'*64, round=2, generation=2,
                    current_map='surf_wrong', zonegen=0)
        for key, value in bads.items():
            with self.assertRaises(R.Refusal, msg=key):
                R.transition(m, 'arrive', '', '', dict(data, **{key:value}))
            missing = dict(data)
            missing.pop(key)
            with self.assertRaises(R.Refusal, msg='missing '+key):
                R.transition(m, 'arrive', '', '', missing)
        m = R.transition(m, 'arrive', '', '', data)
        for p in R.competitors(m):
            m = R.transition(m, 'ready', p['who'], '', data)
        with self.assertRaisesRegex(R.Refusal, 'zone generation'):
            R.transition(m, 'start', 'host', '', dict(data, zonegen=2))
        m = R.transition(m, 'start', 'host', '', data)
        with self.assertRaisesRegex(R.Refusal, 'effective tickrate'):
            R.transition(m, 'go', '', '', dict(data, elapsed_ms=5000, tickrate=100))
        m = R.transition(m, 'go', '', '', dict(data, elapsed_ms=5000, tickrate=1000000/15000))
        with self.assertRaisesRegex(R.Refusal, 'zonepin'):
            R.transition(m, 'score', '', '', dict(data, zonepin='d'*64))
        self.assertEqual(R.transition(m, 'abort', '', '', {})['phase'], 'aborted')
        # Float32 spelling at the AG1000 boundary remains inside the explicit tolerance.
        self.assertEqual(R.rate(dict(tickrate='1000.000061')), 1000.000061)


class API(unittest.TestCase):
    def setUp(self):
        seed_catalogue()
        self.now = 2000000000
        self.clock = patch.object(S.time, 'time', lambda: self.now)
        self.clock.start()
        self.client = S.app.test_client()
        self.db = S.connect()
        for table in ('tournament_requests', 'tournament_reservations', 'tournament_matches',
                      'tournament_nodes', 'lobby_handoffs', 'assignments', 'lobbies', 'social_sessions', 'keylinks', 'accounts', 'map_pool'):
            self.db.execute('DELETE FROM ' + table)
        self.tokens = []
        self.whos = []
        for i in range(3):
            sid, pub = str(76561198000000001+i), str(i+1)*64
            self.db.execute('INSERT INTO accounts(steamid,name,created_at) VALUES(?,?,?)', (sid, 'Fixture '+str(i), self.now))
            self.db.execute('INSERT INTO keylinks(pub,steamid,linked_at) VALUES(?,?,?)', (pub, sid, self.now))
            self.tokens.append(social.issue(self.db, pub, sid, 'n1', self.now)['social'])
            self.whos.append(accounts.who_of(sid))
        self.db.commit()
        S._rate.clear()
        self.serial = 0
        self.heartbeat()
        self.post('state', enabled=1, occupants=0)

    def tearDown(self):
        self.db.close()
        self.clock.stop()

    def heartbeat(self, node='n1', mapname='surf_Alpha', players=0):
        res = self.client.post('/api/heartbeat', data=dict(key='testkey', node=node, map=mapname,
                               players=players, max=16, port=27510, name='Fixture'))
        self.assertEqual(res.status_code, 200)
        return res

    def post(self, op, token=None, **fields):
        self.serial += 1
        data = dict(key='testkey', node='n1', op=op, request=('%x' % self.serial),
                    movement='default', tick_us=15000, clock_us=15000)
        if token is not None:
            data['token'] = token
        data.update(fields)
        return self.client.post('/api/tournaments/game', data=data).get_json()

    def create(self):
        res = self.post('create', self.tokens[0], revision=0, capacity=3, round_seconds=60, occupants=1)
        self.assertEqual(res['ok'], 1, res)
        return res['match']

    def action(self, m, op, i=None, **data):
        fields = dict(observation(m), id=m['id'], revision=m['revision'], epoch=m['epoch'])
        fields.update(data)
        return self.post(op, self.tokens[i] if i is not None else None, **fields)

    def test_off_default_and_bad_key_semantics(self):
        with patch.dict(os.environ, SURFD_TOURNAMENTS='0'):
            self.assertEqual(self.client.get('/api/tournaments').get_json(), dict(v=1, enabled=0, rows=[], slots=[]))
            self.assertEqual(self.post('create', self.tokens[0], revision=0, capacity=2,
                                       round_seconds=60, occupants=1)['ok'], 0)
        bad = self.client.post('/api/tournaments/game', data=dict(key='wrong', op='create'))
        self.assertEqual(bad.status_code, 403)
        good = self.client.post('/api/tournaments/game', data=dict(key='testkey', op='create', node='n1'))
        self.assertEqual((good.status_code, good.get_json()['ok']), (200, 0))
        self.assertEqual(self.db.execute('PRAGMA user_version').fetchone()[0], S.SCHEMA_VERSION)

    def test_native_spectator_occupancy_excludes_empty_slot_and_old_capability(self):
        self.assertEqual(len(self.client.get('/api/tournaments').get_json()['slots']), 1)
        self.assertEqual(self.post('state', enabled=1, occupants=1)['ok'], 1)
        self.assertEqual(self.client.get('/api/tournaments').get_json()['slots'], [])
        self.assertEqual(self.post('state', enabled=1, occupants=2)['ok'], 1)
        self.assertEqual(self.post('create', self.tokens[0], revision=0, capacity=3,
                                   round_seconds=60, occupants=1)['ok'], 0)
        self.db.execute('UPDATE tournament_nodes SET native_occupants=-1')
        self.db.commit()
        self.assertEqual(self.client.get('/api/tournaments').get_json()['slots'], [])
        self.assertEqual(self.post('state', enabled=1, occupants=0)['ok'], 1)
        self.assertEqual(len(self.client.get('/api/tournaments').get_json()['slots']), 1)

    def test_create_permissions_slots_collision_and_allocator_all_paths(self):
        self.assertEqual(len(self.client.get('/api/tournaments').get_json()['slots']), 1)
        self.assertEqual(self.post('create', '0'*64, revision=0, occupants=1)['ok'], 0)
        m = self.create()
        self.assertEqual(len(self.client.get('/api/tournaments').get_json()['slots']), 0)
        self.assertEqual(self.post('create', self.tokens[1], revision=0, occupants=1)['ok'], 0)
        # Same-map reuse, pending-claim reuse, idle allocation and busy fallback all exclude n1.
        for name in ('surf_alpha', 'surf_b'):
            self.db.execute('INSERT OR REPLACE INTO assignments VALUES(?,?,?,?,?)', ('n1',name,name,self.now,'fixture'))
            self.db.commit()
            res = self.client.get('/api/join?map='+name)
            self.assertEqual(res.status_code, 503, res.get_data(as_text=True))
            self.assertEqual(res.get_json()['lobbies'], [])
        self.assertEqual(self.heartbeat().get_data(as_text=True), 'ok')
        self.assertEqual(self.client.get('/lobbies.json').get_json()['lobbies'], [])
        self.assertEqual(self.action(m, 'enter', 1)['ok'], 1)
        body = json.dumps(self.client.get('/api/tournaments').get_json())
        self.assertNotIn(self.tokens[0], body)
        self.assertNotIn('76561198', body)
        self.assertNotIn('_accounts', body)

    def test_hold_p1650_capable_idle_node_skips_ordinary_joins_but_stays_listed(self):
        # setUp advertised n1 with an enabled=1 state poll.
        for name in ('surf_b', 'surf_alpha'):
            self.assertEqual(self.client.get('/api/join?map=' + name).status_code, 503, name)
        self.assertEqual(len(self.client.get('/lobbies.json').get_json()['lobbies']), 1)
        self.heartbeat(node='n2', mapname='surf_c')
        self.assertEqual(self.client.get('/api/join?map=surf_b').status_code, 200)
        self.assertEqual([r[0] for r in self.db.execute('SELECT node FROM assignments')], ['n2'])
        self.db.execute('DELETE FROM assignments')
        self.db.execute("DELETE FROM lobbies WHERE node='n2'")
        self.db.commit()
        for env in (dict(SURFD_TOURNAMENT_HOLD='0'), dict(SURFD_TOURNAMENTS='0')):
            with patch.dict(os.environ, env):
                self.assertEqual(self.client.get('/api/join?map=surf_alpha').get_json()['why'], 'already running', env)
        # A capability poll older than CAP_TTL no longer holds the node.
        self.now += T.CAP_TTL + 1
        self.heartbeat()
        self.assertEqual(self.client.get('/api/join?map=surf_alpha').status_code, 200)

    def test_auth_ban_unlink_wrong_node_and_host_permissions(self):
        m = self.create()
        self.assertEqual(self.action(m, 'cancel', 1)['ok'], 0)
        self.assertEqual(self.post('enter', self.tokens[1], node='other', id=m['id'], revision=m['revision'])['ok'], 0)
        self.db.execute('UPDATE accounts SET banned_at=1 WHERE steamid=?', (str(76561198000000002),))
        self.db.commit()
        self.assertEqual(self.action(m, 'enter', 1)['ok'], 0)
        self.db.execute('UPDATE accounts SET banned_at=0')
        self.db.execute('DELETE FROM keylinks WHERE steamid=?', (str(76561198000000002),))
        self.db.commit()
        self.assertEqual(self.action(m, 'enter', 1)['ok'], 0)
        self.assertEqual(self.action(m, 'abort', epoch='b'*32)['ok'], 0)

    def test_idempotency_cas_and_explicit_release(self):
        fields = dict(revision=0, capacity=3, round_seconds=60, occupants=1, request='abcd')
        one = self.post('create', self.tokens[0], **fields)
        two = self.post('create', self.tokens[0], **fields)
        self.assertEqual(one, two)
        fields['capacity'] = 2
        self.assertEqual(self.post('create', self.tokens[0], **fields)['ok'], 0)
        m = one['match']
        entered = self.action(m, 'enter', 1)['match']
        self.assertEqual(self.action(m, 'enter', 2)['ok'], 0)
        self.assertEqual(self.action(entered, 'release', restored=1)['ok'], 0)
        cancelled = self.action(entered, 'cancel', 0)['match']
        with patch.dict(os.environ, SURFD_TOURNAMENTS='0'):
            self.assertTrue(T.reserved(self.db, 'n1'))
            released = self.action(cancelled, 'release', restored=1)
        self.assertEqual(released['status'], 'released')
        self.assertFalse(T.reserved(self.db, 'n1'))

    def test_fresh_occupied_and_pending_assignment_create_refusal(self):
        self.heartbeat(players=2)
        self.assertEqual(self.post('create', self.tokens[0], revision=0, occupants=1)['ok'], 0)
        self.heartbeat(players=0)
        self.db.execute('INSERT INTO assignments VALUES(?,?,?,?,?)', ('n1','surf_b','surf_b',self.now,'fixture'))
        self.db.commit()
        self.assertEqual(self.post('create', self.tokens[0], revision=0, occupants=1)['ok'], 0)
        self.db.execute('DELETE FROM assignments')
        self.db.commit()
        self.now += T.CAP_TTL + 1
        self.assertEqual(self.client.get('/api/tournaments').get_json()['slots'], [])
        self.assertEqual(self.post('create', self.tokens[0], revision=0, occupants=1)['ok'], 0)

    def test_flask_draft_ready_scoring_restore_and_finish(self):
        m = self.create()
        def act(op, i=None, **fields):
            nonlocal m
            res = self.action(m, op, i, **fields)
            self.assertEqual(res['ok'], 1, res)
            m = res['match']
        act('enter', 1)
        act('seat', 0, target=self.whos[1])
        act('accept', 0)
        act('accept', 1)
        act('lock', 0)
        while m['phase'] == 'draft':
            i = self.whos.index(m['turn_who'])
            act(m['turn_kind'], i, map=next(c['name'] for c in m['maps'] if c['status']=='pool'))
        expected = copy.deepcopy(m)
        self.now += S.LOBBY_TTL + 100
        # Real backend module reload; no heartbeat timeout can free the active node.
        importlib.reload(S)
        self.client = S.app.test_client()
        self.assertEqual(self.post('state')['match'], expected)
        self.assertTrue(T.reserved(self.db, 'n1'))
        self.heartbeat(mapname=m['current_map'], players=2)
        self.assertEqual(self.post('state')['match'], expected)
        data = observation(m)
        act('arrive', **data)
        act('ready', 0, **data)
        act('arrive', **data)
        self.assertEqual(m['players'][0]['ready'], 1)
        act('ready', 1, **data)
        act('start', 0)
        act('go', elapsed_ms=5000, tickrate=1000000/15000)
        act('score', who=self.whos[0], ticks=60, tickrate=1000000/15000, elapsed_ms=1000,
            start_elapsed_ms=0, runid='a'*32, **data)
        act('settle', elapsed_ms=60000)
        self.assertEqual([p['place'] for p in m['players']], [1,2])
        act('advance')
        self.assertEqual(m['phase'], 'finished')
        act('release', restored=1)
        self.assertFalse(T.reserved(self.db, 'n1'))

    def test_leave_p1650_after_arrival_forfeits_through_game_endpoint(self):
        m = self.create()
        for op, i, fields in (('enter',1,{}), ('seat',0,dict(target=self.whos[1])), ('accept',0,{}), ('accept',1,{}), ('lock',0,{})):
            m = self.action(m, op, i, **fields)['match']
        while m['phase'] == 'draft':
            m = self.action(m, m['turn_kind'], self.whos.index(m['turn_who']), map=next(c['name'] for c in m['maps'] if c['status']=='pool'))['match']
        m = self.action(m, 'arrive')['match']
        out = self.action(m, 'leave', 1)
        self.assertEqual(out['ok'], 1, out)
        self.assertEqual((out['match']['phase'], out['match']['outcome']), ('finished', 'winner'))
        self.assertEqual([(p['role'], p['place']) for p in out['match']['players']], [('player', 1), ('eliminated', 2)])
        self.assertTrue(T.reserved(self.db, 'n1'))

    def arrived_ready(self, ready=(0, 1)):
        m = self.create()
        for op, i, fields in (('enter',1,{}), ('seat',0,dict(target=self.whos[1])), ('accept',0,{}), ('accept',1,{}), ('lock',0,{})):
            m = self.action(m, op, i, **fields)['match']
        while m['phase'] == 'draft':
            m = self.action(m, m['turn_kind'], self.whos.index(m['turn_who']), map=next(c['name'] for c in m['maps'] if c['status']=='pool'))['match']
        m = self.action(m, 'arrive')['match']
        for i in ready:
            m = self.action(m, 'ready', i)['match']
        return m

    def test_autostart_p1650_absent_list_through_game_endpoint_and_journal(self):
        m = self.arrived_ready(ready=(0,))
        fields = dict(observation(m), id=m['id'], revision=m['revision'], epoch=m['epoch'], request='b6b6')
        self.assertEqual(self.post('autostart', **dict(fields, absent=self.whos[0]))['error'], 'absent list invalid')
        first = self.post('autostart', **dict(fields, absent=self.whos[1]))
        self.assertEqual((first['ok'], first['match']['phase'], first['match']['outcome']), (1, 'finished', 'winner'), first)
        self.assertEqual([(p['role'], p['place']) for p in first['match']['players']], [('player', 1), ('eliminated', 2)])
        self.assertEqual(self.post('autostart', **dict(fields, absent=self.whos[1])), first)
        self.assertIn('reused', self.post('autostart', **dict(fields, absent=''))['error'])

    def test_autostart_p1650_is_a_keyed_server_op_with_journal(self):
        m = self.arrived_ready()
        fields = dict(observation(m), id=m['id'], revision=m['revision'], epoch=m['epoch'], request='a5a5')
        self.assertEqual(self.post('autostart', **dict(fields, epoch='b'*32))['ok'], 0)
        with patch.dict(os.environ, SURFD_TOURNAMENT_ACCESS='paid'):
            self.assertEqual(self.post('autostart', **fields)['ok'], 0)
        first = self.post('autostart', **fields)
        self.assertEqual((first['ok'], first['match']['phase']), (1, 'countdown'), first)
        self.assertEqual(self.post('autostart', **fields), first)
        self.assertEqual(self.post('autostart', **dict(fields, revision=first['match']['revision'], request='a5a6'))['ok'], 0)

    def test_abort_p1650_reason_from_game_server_and_drift_note(self):
        m = self.arrived_ready()
        out = self.action(m, 'abort', reason='host_gone')
        self.assertEqual((out['ok'], out['match']['note']), (1, 'No contest: the host left the server.'))
        self.action(out['match'], 'release', restored=1)
        m = self.arrived_ready()
        bad = self.post('state', **dict(observation(m), zonegen=2))['match']
        self.assertEqual((bad['phase'], bad['note']), ('aborted', "No contest: the map's zones or rules changed."))

    def test_disable_live_abort_restore_release_and_second_creation(self):
        m = self.create()
        def act(op, i=None, **fields):
            nonlocal m
            res = self.action(m, op, i, **fields)
            self.assertEqual(res['ok'], 1, res)
            m = res['match']
        act('enter', 1)
        act('seat', 0, target=self.whos[1])
        act('accept', 0)
        act('accept', 1)
        act('lock', 0)
        while m['phase'] == 'draft':
            act(m['turn_kind'], self.whos.index(m['turn_who']),
                map=next(c['name'] for c in m['maps'] if c['status'] == 'pool'))
        data = observation(m)
        act('arrive', **data)
        act('ready', 0, **data)
        act('ready', 1, **data)
        act('start', 0)
        act('go', elapsed_ms=5000, tickrate=1000000/15000)
        first_id = m['id']
        with patch.dict(os.environ, SURFD_TOURNAMENTS='0'):
            held = self.post('state', **observation(m))
            self.assertEqual((held['ok'], held['status'], held['match']['phase']), (1, 'disabled', 'live'))
            self.assertEqual(self.action(m, 'settle', elapsed_ms=60000)['ok'], 0)
            act('abort')
            self.assertEqual((m['phase'], m['outcome']), ('aborted', 'no-contest'))
            self.assertTrue(T.reserved(self.db, 'n1'))
            act('release', restored=1)
            self.assertFalse(T.reserved(self.db, 'n1'))
        second = self.create()
        self.assertNotEqual(first_id, second['id'])
        self.assertEqual(second['revision'], 1)

    def test_qualified_pool_spelling_and_disabled_maps(self):
        m = self.post('create', self.tokens[0], revision=0, capacity=3, round_seconds=60, occupants=1, pool=','.join(MAPS[:6]))['match']
        for op, i, fields in (('enter',1,{}), ('seat',0,dict(target=self.whos[1])),
                              ('accept',0,{}), ('accept',1,{})):
            m = self.action(m, op, i, **fields)['match']
        self.db.execute('INSERT INTO map_pool VALUES(?,?,?)', ('surf_f',0,self.now))
        self.db.commit()
        denied = self.action(m, 'lock', 0)
        self.assertEqual(denied['ok'], 0)
        self.assertIn('selected map', denied['error'])
        self.db.execute('DELETE FROM map_pool')
        self.db.commit()
        locked = self.action(m, 'lock', 0)
        self.assertEqual(locked['ok'], 1, locked)
        self.assertIn('surf_Alpha', [c['name'] for c in locked['match']['maps']])

    def test_missing_default_env_file_enable_and_unreserved_control(self):
        with patch.dict(os.environ):
            os.environ.pop('SURFD_TOURNAMENTS', None)
            self.assertEqual(self.client.get('/api/tournaments').get_json()['enabled'], 0)
            (HOME / 'surfd.env').write_text('SURFD_KEY=testkey\nSURFD_TOURNAMENTS=1\n')
            try:
                self.assertEqual(self.client.get('/api/tournaments').get_json()['enabled'], 1)
            finally:
                (HOME / 'surfd.env').write_text('SURFD_KEY=testkey\n')
        m = self.create()
        self.heartbeat(node='n2', mapname='surf_Alpha', players=2)
        res = self.client.get('/api/join?map=surf_alpha')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['players'], 2)
        self.assertEqual(res.get_json()['why'], 'already running')
        self.assertTrue(T.reserved(self.db, m['node']))

    def test_duplicate_action_and_replay_still_requires_valid_actor(self):
        m = self.create()
        data = dict(id=m['id'], revision=m['revision'], request='ffee')
        first = self.post('enter', self.tokens[1], **data)
        self.assertEqual(self.post('enter', self.tokens[1], **data), first)
        self.assertEqual(first['match']['revision'], 2)
        self.db.execute('UPDATE accounts SET banned_at=1 WHERE steamid=?', ('76561198000000002',))
        self.db.commit()
        self.assertEqual(self.post('enter', self.tokens[1], **data)['ok'], 0)

    def test_concurrent_create_cannot_overwrite_reservation(self):
        def create(i):
            with S.app.test_client() as client:
                return client.post('/api/tournaments/game', data=dict(key='testkey', node='n1',
                    op='create', token=self.tokens[i], request=('%x' % (100+i)),
                    revision=0, occupants=1, capacity=2, round_seconds=60)).get_json()['ok']
        with ThreadPoolExecutor(max_workers=2) as executor:
            result = list(executor.map(create, (0,1)))
        self.assertEqual(sorted(result), [0,1])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 1)

    def test_journal_full_preserves_abort_and_release_recovery(self):
        m = self.create()
        with patch.object(T, 'REQUEST_LIMIT', 1):
            self.assertEqual(self.action(m, 'enter', 1)['ok'], 0)
            aborted = self.action(m, 'abort')
            self.assertEqual(aborted['ok'], 1, aborted)
            self.assertTrue(T.reserved(self.db, 'n1'))
            released = self.action(aborted['match'], 'release', restored=1)
            self.assertEqual(released['ok'], 1, released)
            self.assertFalse(T.reserved(self.db, 'n1'))

    def test_concurrent_cas_one_commit(self):
        m = self.create()
        def enter(i):
            with S.app.test_client() as client:
                return client.post('/api/tournaments/game', data=dict(key='testkey', node='n1',
                    op='enter', token=self.tokens[i], request=('%x' % (100+i)),
                    id=m['id'], revision=m['revision'])).get_json()['ok']
        with ThreadPoolExecutor(max_workers=2) as executor:
            result = list(executor.map(enter, (1,2)))
        self.assertEqual(sorted(result), [0,1])
        self.assertEqual(self.post('state')['match']['revision'], 2)

    def test_actual_missing_library_is_unavailable_but_empty_library_is_success(self):
        self.assertEqual(self.client.get('/api/tournament-map-pool').get_json()['total'], 9)
        maps, held = HOME / 'maps', HOME / 'held-maps'
        maps.rename(held)
        try:
            # Real ordinary provider deliberately reports emptiness, not None.
            self.assertEqual(S._scan_maps(), ({}, frozenset()))
            response = self.client.get('/api/tournament-map-pool')
            self.assertEqual((response.status_code, response.get_json()['error']),
                             (400, 'map catalogue unavailable'))
            self.assertEqual(self.post('create', self.tokens[0], revision=0, occupants=1,
                                      capacity=2, round_seconds=60)['error'], 'map catalogue unavailable')
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 0)
            maps.mkdir()
            response = self.client.get('/api/tournament-map-pool')
            self.assertEqual((response.status_code, response.get_json()['ok'], response.get_json()['total']), (200,1,0))
        finally:
            if maps.exists():
                maps.rmdir()
            held.rename(maps)

    def test_persisted_alpha_settings_refusal_state_cancel_and_release(self):
        self.create()  # Successful current-protocol control before removing Beta fields.
        m = json.loads(self.db.execute('SELECT state FROM tournament_matches').fetchone()[0])
        for key in ('settings', 'ruleset_id', '_pins', '_zonegen'):
            m.pop(key)
        saved = S.game_json(m)
        self.db.execute('UPDATE tournament_matches SET state=? WHERE id=?', (saved,m['id']))
        self.db.commit()
        fields = dict(id=m['id'], revision=m['revision'], epoch=m['epoch'], capacity=3,
                      round_seconds=60, kind='surf', tiers='7', profile='default', pool='-')
        for op in ('configure', 'lock', 'start'):
            out = self.post(op, self.tokens[0], **fields)
            self.assertEqual((out['ok'], out['status']), (0,'refused'))
            self.assertIn('Pre-Beta', out['error'])
            self.assertEqual(self.db.execute('SELECT state FROM tournament_matches').fetchone()[0], saved)
            self.assertTrue(T.reserved(self.db, 'n1'))
        state = self.post('state')
        self.assertEqual(state['ok'], 1)
        self.assertNotIn('settings', state['match'])
        cancelled = self.post('cancel', self.tokens[0], **fields)['match']
        self.assertEqual(cancelled['phase'], 'cancelled')
        out = self.post('release', id=cancelled['id'], revision=cancelled['revision'],
                        epoch=cancelled['epoch'], restored=1, occupants=0)
        self.assertEqual((out['ok'], out['status']), (1,'released'))
        self.assertFalse(T.reserved(self.db, 'n1'))

    def test_pool_read_contract_public_policy_and_unavailable(self):
        response = self.client.get('/api/tournament-map-pool')
        out = response.get_json()
        self.assertEqual((out['ok'], out['enabled'], out['hosting'], out['policy'], out['total'], len(out['rows'])), (1,1,1,'free_beta',9,8))
        self.assertEqual((out['tick_us'], out['filters']), (15000, dict(kind='surf',tiers=7,profile='default')))
        self.assertEqual(set(out['rows'][0]), {'name','kind','tier','mt','kt'})
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)
        self.assertNotIn('map_stamp', json.dumps(out))
        for query in ('limit=17', 'offset=-1', 'kind=surf&kind=bhop', 'profile=unknown', 'tiers=07', 'pool=-'):
            self.assertEqual(self.client.get('/api/tournament-map-pool?'+query).status_code, 400)
        with patch.dict(os.environ, SURFD_TOURNAMENT_QUALIFICATIONS=''):
            out = self.client.get('/api/tournament-map-pool').get_json()
            self.assertEqual((out['rows'], out['unqualified']), ([],9))
        with patch.dict(os.environ, SURFD_TOURNAMENT_ACCESS='paid'):
            self.assertEqual(self.client.get('/api/tournament-map-pool').get_json()['hosting'], 0)
            self.assertEqual(self.post('create', self.tokens[0], revision=0, occupants=1, capacity=2, round_seconds=60)['ok'], 0)
        with patch.dict(os.environ, SURFD_TOURNAMENTS='0'):
            self.assertEqual(self.client.get('/api/tournament-map-pool').get_json(), dict(ok=1,v=1,enabled=0,rows=[]))
        with patch.object(S, '_mt', dict(at=S.time.monotonic(), tier=None)):
            self.assertEqual(self.client.get('/api/tournament-map-pool').get_json()['error'], 'difficulty catalogue unavailable')

    def test_observed_state_drift_durably_aborts_without_freeing_reservation(self):
        m = self.create()
        for op, i, fields in (('enter',1,{}), ('seat',0,dict(target=self.whos[1])), ('accept',0,{}), ('accept',1,{}), ('lock',0,{})):
            m = self.action(m, op, i, **fields)['match']
        while m['phase'] == 'draft':
            m = self.action(m, m['turn_kind'], self.whos.index(m['turn_who']), map=next(c['name'] for c in m['maps'] if c['status']=='pool'))['match']
        m = self.action(m, 'arrive')['match']
        healthy = self.post('state', **observation(m))['match']
        self.assertEqual(healthy['phase'], 'loading')
        bad = self.post('state', **dict(observation(m), zonegen=2))['match']
        self.assertEqual(bad['phase'], 'aborted')
        self.assertTrue(T.reserved(self.db, 'n1'))
        self.assertEqual(json.loads(self.db.execute('SELECT state FROM tournament_matches').fetchone()[0])['phase'], 'aborted')
        self.assertEqual(self.action(bad, 'release', restored=1, movement='bad')['ok'], 1)

    def test_native_capability_migration_and_missing_observation_fail_closed(self):
        import sqlite3
        db = sqlite3.connect(':memory:')
        try:
            db.execute('CREATE TABLE tournament_nodes(node TEXT PRIMARY KEY, seen INTEGER NOT NULL)')
            db.execute("INSERT INTO tournament_nodes VALUES('old',1)")
            T.schema(db)
            self.assertEqual(db.execute('SELECT movement,tick_us,clock_us,native_occupants FROM tournament_nodes').fetchone(), ('',0,0,-1))
        finally:
            db.close()
        for fields in (dict(movement=''), dict(tick_us=''), dict(clock_us=''), dict(movement='ag100-v1'), dict(tick_us=10000), dict(clock_us=10000)):
            self.post('state', enabled=1, occupants=0, **fields)
            failed = self.post('create', self.tokens[0], revision=0, occupants=1, capacity=2, round_seconds=60)
            self.assertEqual(failed['ok'], 0, fields)
            for table in ('tournament_matches','tournament_reservations'):
                self.assertEqual(self.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM social_sessions').fetchone()[0], 3)
        self.post('state', enabled=1, occupants=0)
        self.assertTrue(self.create()['id'])


if __name__ == '__main__':
    unittest.main()
