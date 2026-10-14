#!/usr/bin/env python3
"""P693 acted UI checks using the existing isolated socket/content rig.

Supply three progs with --progs, an inspected --client/--server and an owned
--output-dir. No install files or player data are changed. Synthetic identities
and rows only. --baseline keeps expected failures as evidence; it is not a pass.
The visual screenshots must also be inspected: submitting faces is not drawing.
--precision-control additionally grades the PREINTEGER collision's acted witness.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time
import uuid
import test_ui_maps_runtime as rig

PLAYER = 'p692-selected-synthetic'
HANDLE = hashlib.sha256(PLAYER.encode()).hexdigest()[:12]
# Use full profile handles; the compact board's eight-character marks are tested too.
rig.WHO = (HANDLE, hashlib.sha256(b'p692-other-synthetic').hexdigest()[:12])
BASE_FIXTURE, BASE_RUNTIME, BASE_OVERLAY = rig.Fixture, rig.Runtime, rig.overlay
GROUPS = ('focused profile', 'focus validation', 'integer focus precision',
          'zone wheel and Mouse2', 'teleport and clips')
PLUGINS = tuple('fteplug_' + p + '_x64.dll' for p in ('hl2', 'cod', 'box3d', 'ode', 'ui_imgui'))


def plain_path(path):
    path = Path(os.path.abspath(path))
    for node in (path, *path.parents):
        try:
            info = node.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('refusing linked/reparse path: ' + str(node))
    return path


def owned_output(path):
    path = plain_path(path).resolve()
    for parent in (path, *path.parents):
        marker = plain_path(parent / 'OWNER.md')
        if marker.is_file():
            return path
    raise ValueError('--output-dir must be beneath an owned task root')


def focus_ranks(status):
    found = re.search(r'profile requested #(\d+), selected #(\d+)', status)
    return (int(found[1]), int(found[2])) if found else None


def precision_subject_acted(observations):
    cases = [('full', 16777217, 16777216), ('full', 16777217, 16777217),
             ('full', 2147483647, 2147483646), ('full', 2147483647, 2147483647),
             ('compact', 16777217, 16777216), ('compact', 16777217, 16777217)]
    if not isinstance(observations, list) or len(observations) != len(cases):
        return False
    for observed, (source, picked, held) in zip(observations, cases):
        if not isinstance(observed, dict):
            return False
        rank, offset = (1500, 1494) if source == 'full' else (1, 0)
        expected = dict(source=source, picked_ms=picked, held_ms=held,
                        profile_json_ms=picked, board_json_ms=held, requested=rank,
                        selected=rank if picked == held else 0, offset=offset)
        if not all(type(observed.get(k)) is type(v) and observed.get(k) == v for k, v in expected.items()):
            return False
    return True


def precision_control_acted(results, observations):
    """A retained baseline failure is not necessarily an acted counterfactual."""
    if [r.get('name') for r in results] != list(GROUPS):
        return False
    groups = {r['name']: r for r in results}
    if any(groups[name].get('passed') is not True for name in
           ('focused profile', 'zone wheel and Mouse2', 'teleport and clips')):
        return False
    failure = groups['integer focus precision']
    if failure.get('passed') is not False or not failure.get('error', '').startswith(
            'full profile integer focus mismatch 16777217/16777216:'):
        return False
    if not observations:
        return False
    first = observations[0]
    return all(first.get(k) == v for k, v in dict(
        source='full', picked_ms=16777217, held_ms=16777216,
        profile_json_ms=16777217, board_json_ms=16777216,
        requested=1500, selected=1500, offset=1494).items())


def input_hashes(a):
    files = [a.progs / name for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')]
    files += [a.client, a.server]
    for parent in {a.client.parent, a.server.parent}:
        files += [parent / name for name in PLUGINS]
    return {str(plain_path(path).resolve()): hashlib.sha256(plain_path(path).read_bytes()).hexdigest()
            for path in files}


def overlay(a, progs, label, junctions):
    path, gd = BASE_OVERLAY(a, progs, label, junctions)
    defs = (rig.ROOT / 'src/shared/sh_defs.qc').read_text(encoding='utf-8')
    version = re.search(r'^#define FS_TERMS_ONLINE (\d+)', defs, re.M).group(1)
    (gd / 'data/consent.txt').write_text('FTESURF-CONSENT 1\nversion ' + version + '\naccepted 20261013-000000\n')
    shutil.copyfile(rig.ROOT / 'ftesurf/fs_addons.default.txt', gd / 'fs_addons.txt')
    return path, gd


class Fixture(BASE_FIXTURE):
    def __init__(self, replay=b'fixture replay'):
        super().__init__(replay)
        self.neighbors = [dict(r=i + 1, player='p692-neighbor-%d' % i, name='Same display name',
                               ms=19501 + i, date=1000, tr='momentum', s='segmented', rep=0)
                          for i in range(2000)]
        self.neighbors[1499].update(player=PLAYER, ms=21000)
        self.neighbors[1498]['ms'] = 21000  # same name/time, different identity
        self.neighbors[20].update(player=PLAYER, ms=19521)  # same identity, different time
        self.profile_ms = 21000
        self.on_ms = 30015

    def answer(self, path):
        u = rig.urlsplit(path)
        q = {k: v[-1] for k, v in rig.parse_qs(u.query, keep_blank_values=True).items()}
        if u.path == '/api/board' and q.get('player') in (HANDLE, HANDLE[:8]) and not any(k in q for k in ('ct', 'on')):
            body = dict(who=HANDLE, name='Same display name', av=0, src='momentum', n=1, maps=1,
                        wr=0, top10=0, total=1,
                        rows=[dict(map='surf_result', track=1, leg=2, tr='momentum', ms=self.profile_ms,
                                   when=1000, r=1500, of=2000, style='segmented')])
        elif u.path == '/api/board' and q.get('player') and q.get('on'):
            full = next((hashlib.sha256(s.encode()).hexdigest()[:12] for s in rig.SID
                         if hashlib.sha256(s.encode()).hexdigest().startswith(q['player'])), q['player'])
            body = dict(who=full, name='Same display name', av=0, src='ranked', on=q['on'],
                        rows=[dict(track=0, leg=0, tr='ranked', ms=self.on_ms, when=1, r=1, of=330, style='clean')])
        elif u.path == '/api/board' and q.get('map') == 'surf_result':
            off, limit = int(q.get('offset', '0')), int(q.get('limit', '100'))
            body = dict(ok=True, map='surf_result', track=int(q.get('track', '0')),
                        leg=int(q.get('leg', '0')), tier=q.get('tier', 'momentum'),
                        style=q.get('style', 'segmented'), offset=off,
                        counts=dict(ksf=0, momentum=2000, ranked=0),
                        rows=self.neighbors[off:off + limit], more=off + limit < len(self.neighbors))
        else:
            return super().answer(path)
        with self.lock:
            self.events.append(dict(path=u.path, query=q, status=200, body=rig.copy.deepcopy(body), delay=0))
        return 200, body, 0


class Runtime(BASE_RUNTIME):
    baseline = False

    def checks(self):
        self.results = []
        self.precision_observations = []
        for name, fn in zip(GROUPS, (self.focus, self.validation, self.precision, self.zone, self.faces)):
            try:
                fn()
                self.results.append(dict(name=name, passed=True))
            except (AssertionError, TimeoutError, RuntimeError) as exc:
                self.results.append(dict(name=name, passed=False, error=str(exc)))
                print('FAIL', name, str(exc))
        (self.out / 'p692-results.json').write_text(json.dumps(self.results, indent=2), encoding='utf-8')
        (self.out / 'precision-observations.json').write_text(
            json.dumps(self.precision_observations, indent=2), encoding='utf-8')
        self.send('echo NAV-RUNTIME-DONE', 0.1)
        print(json.dumps(self.results, indent=2))
        if not self.baseline and not all(r['passed'] for r in self.results):
            raise AssertionError('P693 checks failed; retained arm contains results/log/screenshots')
        return self.results

    run = checks

    def focused_status(self):
        return self.section('ui_board_test', 0.3)

    def menu_click(self, target):
        state = self.section('ui_cursor')
        matches = re.findall(r'ui_element \d+ \[' + re.escape(target) + r'\] ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)', state)
        self.require(bool(matches), 'menu hit target not drawn: ' + target)
        x, y, w, h = map(float, matches[-1])
        self.send('ui_click %g %g' % (x + w / 2, y + h / 2), 0.7)

    def focus(self):
        self.send('ui_close', 0.1)
        self.send('hud_player find ""', 0.1)
        self.send('hud_player view ' + HANDLE, 0.9)
        end = time.monotonic() + 8
        while 'rows 1/1' not in self.section('hud_player status', 0.15):
            if time.monotonic() >= end:
                raise AssertionError('profile request/row load control did not act')
        at = len(self.fixture.events)
        self.click('pf_map0')
        state = self.focused_status()
        asks = self.fixture.since(at, '/api/board')
        self.require(any(e['query'].get('offset') == '1494' for e in asks),
                     'profile click did not fetch distant rank neighborhood: ' + repr([e['query'] for e in asks]))
        self.require('profile requested #1500, selected #1500' in state,
                     'exact identity/time did not focus at rank 1500: ' + state)
        self.send('screenshot p692_profile', 0.3)
        self.send('ui_board_test scroll 105', 0.8)
        asks = self.fixture.since(at, '/api/board')
        self.require(any(e['query'].get('offset') == '1594' for e in asks), 'next page lost the base offset')
        self.send('ui_board_test scroll 0', 0.1)
        self.menu_click('mlb_earlier')
        self.require(any(e['query'].get('offset') == '1394' for e in self.fixture.since(at, '/api/board')),
                     'earlier button did not act')
        self.menu_click('mlb_top')
        self.require(any(e['query'].get('offset') == '0' for e in self.fixture.since(at, '/api/board')),
                     'top button did not act')
        self.send('ui_board_test close', 0.1)
        self.send('ui_close', 0.1)
        self.send('scores open', 0.1)
        self.send('scores tab online', 0.7)
        # Documented twin of picking a player in the board search dropdown.
        self.send('scores on ' + hashlib.sha256(rig.SID[0].encode()).hexdigest()[:8], 0.8)
        at = len(self.fixture.events)
        self.click('pf_on0')
        self.require('profile requested #1, selected #1' in self.focused_status(),
                     'compact profile time did not focus its exact board row')
        self.require(any(e['query'].get('map') == 'surf_voyager' and e['query'].get('tier') == 'ranked'
                         and e['query'].get('style') == 'clean' for e in self.fixture.since(at, '/api/board')),
                     'compact profile time lost its tier/style scope')

    def validation(self):
        self.send('ui_board_test close', 0.1)
        before = len(self.fixture.events)
        log_at = len(self.log.text())
        tails = ['0 ' + HANDLE + ' 21000', '1500 badhandle 21000',
                 '1500 ' + HANDLE + ' 0', '1500 ' + HANDLE + ' 21000 extra',
                 '1500 ' + HANDLE + ' 2147483648', '1500 ' + HANDLE + ' 4294967297',
                 '10000001 ' + HANDLE + ' 21000']
        for tail in tails:
            self.send('set ui_board_request "surf_result momentum 1 2 segmented ' + tail + '"', 0.3)
        self.require(self.log.text()[log_at:].count('rejected browse request') == len(tails),
                     'focused payload bounds/token validation did not reject all inputs')
        self.require(not self.fixture.since(before, '/api/board'), 'malformed focus dispatched a request')
        self.send('set ui_board_request "surf_result momentum 1 2 segmented 1500 ' +
                  rig.WHO[1] + ' 21000"', 0.7)
        self.require('selected #0' in self.focused_status(), 'duplicate display name/time selected wrong identity')
        self.send('set ui_board_request "surf_result momentum 1 2 segmented 1500 ' + HANDLE[:8] + ' 21000"', 0.7)
        self.require('selected #1500' in self.focused_status(), 'compact eight-character mark did not focus')
        self.send('set ui_board_request "surf_result momentum 1 2 segmented"', 0.7)
        self.require('offset 0' in self.focused_status(), 'legacy five-field browse retained offset')
        self.send('ui_close', 0.1)

    def precision(self):
        # Actual profile JSON -> CSQC table -> decimal mailbox -> MenuQC JSON.
        # First case is the reviewer's acted float32 collision, not a model test.
        for idx, (picked, held) in enumerate([(16777217, 16777216), (16777217, 16777217),
                                              (2147483647, 2147483646), (2147483647, 2147483647)]):
            self.fixture.profile_ms = picked
            self.fixture.neighbors[1499]['ms'] = held
            self.send('ui_board_test close', 0.1)
            self.send('ui_close', 0.1)
            at = len(self.fixture.events)
            self.send('hud_player view ' + (HANDLE[:8] if idx % 2 == 0 else HANDLE), 0.9)
            end = time.monotonic() + 8
            while not self.fixture.since(at, '/api/board') or 'rows 1/1' not in self.section('hud_player status', 0.15):
                if time.monotonic() >= end:
                    raise AssertionError('integer profile row request did not act')
            profile = self.fixture.since(at, '/api/board')[-1]['body']
            click_at = len(self.fixture.events)
            log_at = len(self.log.text())
            self.click('pf_map0')
            state = self.focused_status()
            pages = [e for e in self.fixture.since(click_at, '/api/board')
                     if e['query'].get('map') == 'surf_result' and e['query'].get('offset') == '1494']
            self.require(bool(pages), 'integer profile click did not request rank neighborhood')
            observed = re.search(r'profile requested #(\d+), selected #(\d+)', state)
            self.require(bool(observed), 'integer focus status did not act: ' + state)
            page = pages[-1]['body']
            row = next((r for r in page['rows'] if r['r'] == 1500), {})
            self.precision_observations.append(dict(source='full', picked_ms=picked, held_ms=held,
                profile_json_ms=profile['rows'][0]['ms'], board_json_ms=row.get('ms'),
                requested=int(observed[1]), selected=int(observed[2]), offset=page['offset']))
            selected = 1500 if picked == held else 0
            self.require((int(observed[1]), int(observed[2])) == (1500, selected),
                         'full profile integer focus mismatch %d/%d: %s' % (picked, held, state))
            if selected:
                self.require('(%d ms)' % picked in self.log.text()[log_at:],
                             'integer handoff rounded its milliseconds')
        for picked, held in [(16777217, 16777216), (16777217, 16777217)]:
            self.fixture.on_ms = picked
            self.fixture.rows[0]['ms'] = held
            self.send('ui_board_test close', 0.1)
            self.send('ui_close', 0.1)
            self.send('scores open', 0.1)
            self.send('scores tab online', 0.6)
            at = len(self.fixture.events)
            self.send('scores on ' + hashlib.sha256(rig.SID[0].encode()).hexdigest()[:8], 0.8)
            profiles = [e for e in self.fixture.since(at, '/api/board') if e['query'].get('on') == rig.MAP]
            self.require(bool(profiles), 'compact integer profile request did not act')
            click_at = len(self.fixture.events)
            log_at = len(self.log.text())
            self.click('pf_on0')
            state = self.focused_status()
            pages = [e for e in self.fixture.since(click_at, '/api/board')
                     if e['query'].get('map') == rig.MAP and e['query'].get('tier') == 'ranked'
                     and e['query'].get('style') == 'clean' and e['query'].get('offset') == '0']
            self.require(bool(pages), 'compact integer click did not request scoped board')
            observed = re.search(r'profile requested #(\d+), selected #(\d+)', state)
            self.require(bool(observed), 'compact integer focus status did not act: ' + state)
            row = next((r for r in pages[-1]['body']['rows'] if r['r'] == 1), {})
            self.precision_observations.append(dict(source='compact', picked_ms=picked, held_ms=held,
                profile_json_ms=profiles[-1]['body']['rows'][0]['ms'], board_json_ms=row.get('ms'),
                requested=int(observed[1]), selected=int(observed[2]), offset=pages[-1]['body']['offset']))
            selected = 1 if picked == held else 0
            self.require((int(observed[1]), int(observed[2])) == (1, selected),
                         'compact profile integer focus mismatch %d/%d' % (picked, held))
            if selected:
                self.require('(%d ms)' % picked in self.log.text()[log_at:],
                             'compact integer handoff rounded its milliseconds')
        # Decimal leading zeros must not invoke stoi's octal interpretation.
        self.send('set ui_board_request "surf_result momentum 1 2 segmented 0000001500 ' +
                  HANDLE + ' 2147483647"', 0.7)
        self.require(focus_ranks(self.focused_status()) == (1500, 1500), 'decimal leading-zero rank lost focus')
        self.fixture.neighbors[1499]['ms'] = 21000
        self.send('set ui_board_request "surf_result momentum 1 2 segmented 1500 ' +
                  HANDLE + ' 0000021000"', 0.7)
        self.require(focus_ranks(self.focused_status()) == (1500, 1500), 'decimal leading-zero time parsed as octal')
        self.send('ui_close', 0.1)

    def key(self, number):
        self.send('vote key %d 1' % number, 0.08)
        self.send('vote key %d 0' % number, 0.2)

    def zone(self):
        self.send('scores close', 0.1)
        self.send('ui_close', 0.1)
        self.send('disconnect', 0.1)
        self.send('map surf_tensor2', 10)
        self.send('sv_cheats 1', 0.1)
        self.send('menu_restart', 0.3)
        self.send('ui_close', 0.1)
        self.send('zone_edit', 0.3)
        self.send('bind MWHEELDOWN +jump', 0.1)
        self.send('bind MWHEELUP +jump', 0.1)
        self.send('bind SPACE +jump', 0.1)
        status = self.section('zone_edit status')
        if 'cursor 0' in status:
            self.send('zone_edit mouse', 0.2)
        position = re.search(r'window ([\d.-]+) ([\d.-]+)', status)
        self.require(bool(position), 'editor panel geometry control did not act')
        x, y = map(float, position.groups())
        self.send('zone_edit pointer %g %g' % (x + 24, y + 200), 0.2)
        self.key(516)
        status = self.section('zone_edit status')
        self.require('cursor 1' in status and 'first list row 2' in status,
                     '+jump-bound wheel did not scroll without toggling: ' + status[:800])
        self.key(515)
        self.require('first list row 0' in self.section('zone_edit status'), 'wheel up did not reverse scroll')
        self.key(32)
        self.require('cursor 1' in self.section('zone_edit status'), 'space jump switched mouse')
        self.key(513)
        self.require('cursor 0' in self.section('zone_edit status'), 'Mouse2 did not switch to look')
        self.key(513)
        self.require('cursor 1' in self.section('zone_edit status'), 'Mouse2 did not switch back to window')
        self.send('zone_edit place stage', 0.2)
        self.key(513)
        self.require('state 1' in self.section('zone_edit status'), 'Mouse2 placement back did not cancel')
        self.send('screenshot p692_zone', 0.2)
        self.send('zone_edit close', 0.1)

    def faces(self):
        # Reset unsaved client-only editor fixtures. Use this installed map's real
        # intro spawn/view, not coordinates from an older revision of its BSP.
        # No saving through the shared read-only maps content junction.
        self.send('zone_edit close', 0.1)
        self.send('map surf_tensor2', 10)
        self.send('sv_cheats 1', 0.1)
        self.require('setpos ' in self.section('cmd viewpos'), 'body/spawn observation did not act')
        self.send('r_showbrushes 0', 0.1)
        self.send('ent_view_dist 8192', 0.1)
        self.send('ent_view_labels 0', 0.1)
        self.send('ent_view_clips 0', 0.1)
        self.send('ent_view', 0.8)
        tp = self.section('ent_view_teleports')
        self.send('screenshot p692_teleport', 0.4)
        if not self.baseline:
            self.require(re.search(r'ent_view_teleports.*"[1-9]', tp), 'teleport class/model publication did not act: ' + tp)
            poses = self.section('ent_view_poses')
            wire = re.search(r'"ent_view_poses" is "([^"]+)"', poses)
            self.require(bool(wire), 'map entity poses did not publish')
            fields = wire.group(1).split()
            self.require(len(fields) % 7 == 0, 'pose record shape is not seven fields')
            table = {int(fields[i]): tuple(map(float, fields[i + 1:i + 4]))
                     for i in range(0, len(fields), 7)}
            hover = re.findall(r'entview hover: \*(\d+) teleport 1, [1-9]\d* brush\(es\), [1-9]\d* face\(s\), origin ([\d.e+-]+) ([\d.e+-]+) ([\d.e+-]+)', self.log.text())
            self.require(bool(hover), 'hovered teleport did not submit actual red faces')
            model, *position = hover[-1]
            origin = tuple(map(float, position))
            self.require(int(model) in table and all(abs(a - b) < .05 for a, b in zip(origin, table[int(model)]))
                         and any(abs(v) > 1000 for v in origin), 'native hull origin did not match the map entity publication')
        at = len(self.log.text())
        self.send('ent_view_dist 8192', 0.1)
        self.send('ent_view_clips 1', 0.8)
        auto_clips = bool(re.search(r'r_showbrushes 0: [1-9]\d* brush\(es\), [1-9]\d* face\(s\).*mask 0x30000', self.log.text()[at:]))
        self.send('screenshot p692_clips', 0.4)
        self.send('ent_view_clips 0', 0.4)
        self.send('screenshot p692_no_clips', 0.4)
        self.send('ent_view', 0.3)
        active = self.section('ent_view_active')
        self.send('screenshot p692_off', 0.3)
        self.require(auto_clips, 'automatic clip hull census did not act')
        self.require('"0"' in active, 'closing overlay left clip publication active')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--progs', type=Path, required=True)
    p.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    p.add_argument('--client', type=Path, required=True)
    p.add_argument('--server', type=Path, required=True)
    p.add_argument('--port', type=int, default=27588)
    p.add_argument('--budget', type=int, default=300,
                   help='runtime deadline in seconds (1..300; excludes setup/cleanup)')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--baseline', action='store_true')
    mode.add_argument('--precision-control', action='store_true')
    a = p.parse_args()
    try:
        rig.launch_options(a)
    except ValueError as exc:
        p.error(str(exc))
    try:
        a.output = owned_output(a.output_dir)
        receipt_path = plain_path(a.output / 'runtime-report.json')
        a.output.mkdir(parents=True, exist_ok=True)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    receipt = dict(mode='precision-control' if a.precision_control else ('baseline' if a.baseline else 'subject'),
                   state='not_started', runtime_verified=False, images_verified=False,
                   requested_port=a.port, requested_budget_seconds=a.budget)
    def save(initial=False):
        owned_output(a.output)
        plain_path(receipt_path)
        target = receipt_path if initial else receipt_path.with_name(receipt_path.name + '.' + uuid.uuid4().hex + '.tmp')
        with target.open('x', encoding='utf-8') as out:
            out.write(json.dumps(receipt, indent=2) + '\n')
            out.flush()
            os.fsync(out.fileno())
        if not initial:
            plain_path(receipt_path)
            target.replace(receipt_path)
    try:
        save(initial=True)
    except (ValueError, OSError) as exc:
        p.error('cannot exclusively create fresh owned report: ' + str(exc))
    try:
        rig.process_gate()
        receipt['inputs_sha256'] = input_hashes(a)
        rig.Fixture, rig.Runtime, rig.overlay = Fixture, Runtime, overlay
        Runtime.baseline = a.baseline or a.precision_control
        report = rig.arm(a, a.progs, 'baseline' if Runtime.baseline else 'subject')
        receipt.update(report, requested_port=a.port)
        if (any(type(report.get(key)) is not int for key in
                ('requested_port', 'port', 'runtime_budget_seconds'))
                or (report['requested_port'], report['port'], report['runtime_budget_seconds'])
                != (a.port, a.port, a.budget)):
            raise RuntimeError('effective launch port/budget differs from requested options')
        if input_hashes(a) != receipt['inputs_sha256']:
            raise RuntimeError('input artifacts changed during the arm')
        observations = json.loads((Path(report['rig']) / 'precision-observations.json').read_text())
        receipt['precision_observations'] = observations
        if a.precision_control:
            if not precision_control_acted(report['results'], observations):
                raise AssertionError('precision control did not prove the expected acted collision/regressions')
            receipt['state'] = 'control_verified'
        elif a.baseline:
            receipt['state'] = 'evidence_only'
        else:
            if [r.get('name') for r in report['results']] != list(GROUPS) or not all(
                    r.get('passed') is True for r in report['results']):
                raise AssertionError('subject requires all five groups')
            if not precision_subject_acted(observations):
                raise AssertionError('subject requires all six exact precision witnesses')
            receipt.update(state='runtime_verified', runtime_verified=True)
        save()
        print('Retained arm:', report['rig'])
        print('Requests:', Path(report['rig']) / 'requests.json')
        return 0
    except rig.Blocked as exc:
        receipt.update(state='blocked', error=str(exc))
        save()
        print('BLOCKED:', exc)
        return 2
    except (AssertionError, RuntimeError, OSError, ValueError) as exc:
        receipt.update(state='failed', error=str(exc))
        save()
        print('FAILED:', exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
