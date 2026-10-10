#!/usr/bin/env python3
"""Finite parsed-board / finish-follow gate. Not HTTP/download/identity acceptance."""
import json
from pathlib import Path
import re


def seed_boards(game):
    folder = game / 'cfg/test'
    folder.mkdir(parents=True, exist_ok=True)
    rows = [{'r': i + 1, 'name': f'P603 Online{i}', 'ticks': 100 + i,
             'ms': 1500 + i * 15, 'rate': 1 / .015, 'flags': 0, 'when': 1,
             'rep': 0, 'player': '', 'tr': 'ranked'} for i in range(8)]
    board = {'map': 'p603scores.map', 'track': 0, 'leg': 0, 'tier': 'ranked',
             'style': 'clean', 't': 2, 'counts': {'ranked': 8}, 'rows': rows}
    for name, changes in [('board', {}), ('empty', {'rows': []}),
                          ('wrongleg', {'leg': 1}), ('wrongstyle', {'style': 'stitched'})]:
        (folder / f'p603{name}.json').write_text(json.dumps(dict(board, **changes)))


def extend_config(cfg, arm):
    lines = []

    def probe(name, shot=False):
        lines.extend(['waitms 400', 'p603follow probe ' + name])
        if shot: lines.append('screenshot follow_' + name)

    def click(target):
        lines.extend(['p603 move ' + target, 'waitms 150', 'p603 down',
                      'waitms 150', 'p603 up', 'waitms 300'])

    lines += ['scores tab local', '+showscores', 'scores open', 'waitms 500']
    probe('local_control', True)
    lines += ['scores note 0 0 107 0']
    probe('local_seek', True)
    if arm.startswith('native'):
        click('previous')
        probe('local_once')
        #Acting watch/line controls were required in the main local suite.
        lines += ['p603 move watch', 'waitms 150', 'p603 down', 'waitms 150',
                  'scores note 0 0 107 0', 'waitms 400', 'p603 up']
        probe('local_held_finish')
    lines += ['p603follow wrongleg']
    probe('wrongleg')
    lines += ['p603follow rightleg']
    probe('rightleg')
    lines += ['-showscores', 'scores note 0 0 107 0']
    probe('closed_seek')
    lines += ['+showscores', 'scores open']
    probe('reopen_seek')
    #Parsed finite bodies, with explicitly synthetic own-index after parser.
    lines += ['scores tab online', 'scores note 0 0 107 0', 'p603follow wait',
              'p603follow board mine']
    probe('online_wait', True)
    lines += ['p603follow answer', 'p603follow board stale']
    probe('online_stale')
    lines += ['p603follow board mine']
    probe('online_seek', True)
    lines += ['p603follow board outside']
    probe('outside', True)
    lines += ['p603follow wrongleg']
    probe('outside_wrongleg', True)
    lines += ['p603follow rightleg', 'p603follow wrongstyle']
    probe('outside_wrongstyle', True)
    lines += ['p603follow rightstyle', 'p603follow board wrongleg']
    probe('body_wrongleg', True)
    lines += ['p603follow board wrongstyle']
    probe('body_wrongstyle', True)
    lines += ['p603follow board empty']
    probe('empty', True)
    lines += ['-showscores', 'replay off', 'waitms 500']
    if arm != 'absent': lines += ['ui_imgui_status', 'waitms 400', 'ui_imgui_status']
    lines += ['echo P603 FOLLOW FINISHED', 'echo P603 FINISHED', 'quit']
    return cfg.replace('echo P603 FINISHED\nquit\n', '\n'.join(lines) + '\n')


def grade_follow(rig: Path, report):
    errors = []
    names = ['local_control', 'local_seek', 'wrongleg', 'rightleg', 'closed_seek',
             'reopen_seek', 'online_wait', 'online_stale', 'online_seek', 'outside',
             'outside_wrongleg', 'outside_wrongstyle', 'body_wrongleg', 'body_wrongstyle', 'empty']
    fields = {'FOLLOW': {'seek', 'wait', 'finished', 'outside', 'mine', 'online'},
              'META': {'page', 'selected', 'first', 'last', 'count', 'painted'},
              'SCROLL': {'local', 'online', 'watch'}}
    for arm in report['planned_arms']:
        native = arm.startswith('native')
        planned = names + (['local_once', 'local_held_finish'] if native else [])
        text = '\n'.join(p.read_text(errors='replace') for p in (rig / arm / 'ftesurf/logs').glob('scores*.log'))

        def need(condition, why):
            if not condition: errors.append(arm + ': follow ' + why)

        need('P603 FOLLOW FINISHED' in text, 'missing completion')
        need('P603 FOLLOW ERROR' not in text, 'fixture error')
        captures, labels = {}, {}
        for kind, name, tail in re.findall(r'P603 (FOLLOW|META|SCROLL) (\w+) ([^\r\n]+)', text):
            if name not in planned: continue
            key = kind, name
            need(key not in captures, 'duplicate ' + kind + ' ' + name)
            pairs = re.findall(r'(\w+)=(-?[0-9]+(?:\.[0-9]+)?)', tail)
            need(len(pairs) == len(fields[kind]) and {k for k, v in pairs} == fields[kind],
                 'field set ' + kind + ' ' + name)
            captures[key] = {k: float(v) for k, v in pairs}
        for name, label in re.findall(r'P603 STANDING (\w+): ?([^\r\n]*)', text):
            if name not in planned: continue
            need(name not in labels, 'duplicate label ' + name)
            labels[name] = label
        for name in planned:
            need(name in labels, 'missing label ' + name)
            for kind in fields: need((kind, name) in captures, 'missing ' + kind + ' ' + name)
        if any((kind, name) not in captures or set(captures[kind, name]) != fields[kind]
               for name in planned for kind in fields) or any(n not in labels for n in planned):
            continue

        def get(kind, name, field): return captures[kind, name][field]
        for name in planned:
            need(get('SCROLL', name, 'watch') == 0, 'unexpected watch ' + name)
            want_native = native and name not in ('closed_seek', 'body_wrongleg', 'body_wrongstyle')
            need(get('META', name, 'painted') == int(want_native), 'route ' + name)
        for name in ('local_seek', 'rightleg', 'reopen_seek', 'online_seek'):
            need(get('FOLLOW', name, 'seek') == 0, 'seek unconsumed ' + name)
        for name in ('wrongleg', 'closed_seek', 'online_wait', 'online_stale'):
            need(get('FOLLOW', name, 'seek') == 1, 'premature seek ' + name)
        need(get('FOLLOW', 'online_wait', 'wait') == 1, 'pending answer subject inert')
        need(get('FOLLOW', 'online_stale', 'wait') == 0, 'answer control did not act')
        for name in ('online_wait', 'online_stale', 'online_seek', 'outside'):
            need(get('FOLLOW', name, 'online') == 8, 'parser rows ' + name)
        need(get('FOLLOW', 'online_seek', 'mine') == 7, 'own-row seam')
        need(get('FOLLOW', 'outside', 'outside') == 1, 'outside standing control')
        for name in ('outside_wrongleg', 'outside_wrongstyle', 'empty'):
            need(get('FOLLOW', name, 'outside') == 0, 'outside guard ' + name)
        for name in planned:
            expected = 'Your standing #99  0:03.150  P603Fixture' if native and name == 'outside' else ''
            need(labels[name] == expected, 'displayed standing ' + name)
        if native:
            for name in ('local_seek', 'rightleg', 'reopen_seek', 'online_seek'):
                need(get('META', name, 'page') == 6 and get('META', name, 'selected') == 7 and
                     get('META', name, 'first') == 7 and get('META', name, 'last') == 8 and
                     get('META', name, 'count') == 23, 'actual revealed/highlighted cells ' + name)
            need(get('META', 'local_once', 'page') == 0 and get('FOLLOW', 'local_once', 'seek') == 0,
                 'one-shot follow overrode acting previous-page control')
            need(get('META', 'local_held_finish', 'page') == 6, 'held-click finish never changed page')
            for name in ('body_wrongleg', 'body_wrongstyle', 'empty'):
                want_count = 5 if name == 'empty' else 0
                need(get('META', name, 'count') == want_count and get('META', name, 'selected') == -1,
                     'old/synthetic row under unavailable board ' + name)
            for name in ('outside', 'outside_wrongleg', 'outside_wrongstyle'):
                need(get('META', name, 'count') == 23 and get('META', name, 'selected') == -1,
                     'outside standing manufactured a row/action ' + name)
        for name in ('local_control', 'local_seek', 'online_wait', 'online_seek', 'outside',
                     'outside_wrongleg', 'outside_wrongstyle', 'body_wrongleg', 'body_wrongstyle', 'empty'):
            need(any((rig / arm / 'ftesurf/screenshots').glob('follow_' + name + '.*')),
                 'missing screenshot ' + name)
    return errors
