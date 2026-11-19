"""Pure, bounded free-alpha tournament transitions. No wall-clock progression."""
import copy
import hashlib
import json
import math
import random
import re

SERVER_OPS = frozenset(('arrive', 'go', 'score', 'settle', 'advance', 'abort', 'release'))
TERMINAL = frozenset(('finished', 'cancelled', 'aborted'))
RUNID = re.compile(r'[0-9a-f]{16,64}\Z')

TIER_MASK = 1023 | 1 << 20
MAP_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
HEX8 = re.compile(r'[0-9a-f]{8}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
PROFILES = {
    'default': dict(movement='default', tick_us=15000, label='Default / 66 tick', unranked=0),
    'hl2-pre': dict(movement='hl2-pre-v1', tick_us=15000, label='HL2 pre', unranked=1),
    'hl2-post': dict(movement='hl2-post-v1', tick_us=15000, label='HL2 post', unranked=1),
    'ag-100': dict(movement='ag100-v1', tick_us=10000, label='AG 100', unranked=1),
    'ag-250': dict(movement='ag250-v1', tick_us=4000, label='AG 250', unranked=1),
    'ag-1000': dict(movement='ag1000-v1', tick_us=1000, label='AG 1000', unranked=1),
    'cs16': dict(movement='cs16-v1', tick_us=10000, label='CS 1.6', unranked=1),
}


def settings(data, legacy=False):
    defaults = dict(kind='surf', tiers='7', profile='default', pool='-')
    if legacy:
        data = dict(defaults, **data)
    require(all(k in data for k in defaults), 'all settings required')
    require(isinstance(data['kind'], str) and data['kind'] in ('surf', 'bhop'), 'bad kind')
    require(bool(re.fullmatch(r'[1-9][0-9]{0,6}', str(data['tiers']))), 'bad tiers')
    tiers = int(data['tiers'])
    require(1 <= tiers <= 2097151, 'bad tiers')
    # Ten tiers exist (bits 0-9) plus unrated (bit 20).
    require(not tiers & ~TIER_MASK, 'bad tiers')
    require(isinstance(data['profile'], str) and data['profile'] in PROFILES, 'bad profile')
    raw = data['pool']
    require(isinstance(raw, str), 'bad pool')
    pool = None if raw == '-' else [] if raw == '_' else raw.split(',')
    if pool is not None:
        require(len(pool) <= 24 and len(set(pool)) == len(pool) and
                all(MAP_NAME.fullmatch(n) for n in pool), 'bad pool')
        pool = sorted(pool)
    return dict(kind=data['kind'], tiers=tiers, profile=data['profile'],
                tick_us=PROFILES[data['profile']]['tick_us'], pool=pool)


def observe(match, data, latched=True):
    require(data.get('current_map') == match['current_map'], 'wrong map')
    require(integer(data, 'generation', 1, 7) == match['generation'], 'wrong generation')
    require(integer(data, 'round', 1, 7) == match['round_index'], 'wrong round')
    require(data.get('ruleset') == match.get('ruleset_id') and bool(match.get('ruleset_id')), 'wrong ruleset')
    require(match.get('settings', {}).get('profile') in PROFILES and isinstance(match.get('_pins'), dict),
            'missing frozen settings')
    profile = PROFILES[match['settings']['profile']]
    require(data.get('movement') == profile['movement'], 'wrong movement')
    for key in ('tick_us', 'clock_us'):
        require(integer(data, key, 1000, 15000) == profile['tick_us'], 'wrong ' + key)
    pin = match['_pins'].get(match['current_map'])
    require(pin is not None, 'missing frozen qualification')
    for key in ('mapcrc', 'zonepin', 'gamemode'):
        require(data.get(key) == pin[key], 'wrong ' + key)
    zonegen = integer(data, 'zonegen', 1, 2147483647)
    if latched:
        require(zonegen == match['_zonegen'], 'zone generation changed')
    return zonegen


class Refusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def integer(data, key, low, high):
    raw = str(data.get(key, ''))
    require(bool(re.fullmatch(r'[0-9]{1,12}', raw)), 'bad ' + key)
    value = int(raw)
    require(low <= value <= high, 'bad ' + key)
    return value


def rate(data):
    try:
        value = float(data.get('tickrate', ''))
    except (TypeError, ValueError):
        raise Refusal('bad tickrate')
    require(math.isfinite(value) and 1 <= value <= 1000.0001, 'bad tickrate')
    return value


def player(who, name, role='spectator'):
    return dict(who=who, name=name[:64], role=role, accepted=0, ready=0,
                best_ticks=0, tickrate=0, place=0)


def create(ident, node, name, addr, who, display, data):
    return dict(id=ident, epoch=ident, revision=1, node=node, name=name[:64], addr=addr,
                phase='lobby', host=who, capacity=integer(data, 'capacity', 2, 8),
                round_seconds=integer(data, 'round_seconds', 60, 900),
                settings=settings(data, legacy=True), ruleset_id='', _pins={}, _zonegen=0,
                round_index=0, generation=0, round_total=0, current_map='', reserve='',
                turn_who='', turn_kind='', note='Free Beta: manual readiness; no payments.',
                players=[player(who, display, 'player')], maps=[], schedule=[],
                _seed=ident, _order=[], _turn=0, _arrived=0, _started=0,
                _runs=[], _rate=0, _accounts={})


def public(match):
    return {k: copy.deepcopy(v) for k, v in match.items() if not k.startswith('_')}


def competitors(match):
    return [p for p in match['players'] if p['role'] == 'player']


def require_current_settings(match):
    # Do not invent settings, pins or renewed consent for persisted Alpha state.
    # State/leave/cancel/abort/restoration-gated release stay available.
    configured = match.get('settings')
    require(type(configured) is dict and
            set(configured) == {'kind', 'tiers', 'profile', 'tick_us', 'pool'},
            'Pre-Beta tournament: cancel and create a new tournament.')


def loading(match):
    match['phase'] = 'loading'
    match['generation'] = match['round_index']
    match['current_map'] = match['schedule'][match['round_index'] - 1]
    match['_arrived'] = 0
    match['_zonegen'] = 0
    match['_rate'] = 0
    for p in match['players']:
        p.update(ready=0, best_ticks=0, tickrate=0)


def transition(original, op, actor, display, data, pool=()):
    """Returns a new state; any refusal leaves the input byte-for-byte unchanged."""
    m = copy.deepcopy(original)
    phase = m['phase']
    me = next((p for p in m['players'] if p['who'] == actor), None)
    if op not in SERVER_OPS:
        require(bool(actor), 'linked account required')
    if op in ('configure', 'seat', 'lock', 'start', 'next', 'cancel'):
        require(actor == m['host'], 'host only')
    if op in ('configure', 'lock', 'start'):
        require_current_settings(m)
    if m.get('_arrived') and phase in ('loading', 'countdown', 'live') and op not in ('abort', 'release', 'cancel', 'leave'):
        observe(m, data)
    if op == 'configure':
        require(phase == 'lobby', 'settings frozen')
        capacity = integer(data, 'capacity', 2, 8)
        seconds = integer(data, 'round_seconds', 60, 900)
        configured = settings(data)
        require(len(competitors(m)) <= capacity, 'capacity below roster')
        if (capacity, seconds, configured) != (m['capacity'], m['round_seconds'], m['settings']):
            m.update(capacity=capacity, round_seconds=seconds, settings=configured)
            for p in m['players']:
                p.update(accepted=0, ready=0, menu_ready=0)
    elif op == 'enter':
        require(phase not in TERMINAL, 'match is closed')
        if me is None:
            require(len(m['players']) < 72 and
                    sum(p['role'] == 'spectator' for p in m['players']) < 64,
                    'spectator roster full')
            m['players'].append(player(actor, display))
    elif op == 'seat':
        require(phase == 'lobby', 'roster frozen')
        target = next((p for p in m['players'] if p['who'] == data.get('target')), None)
        require(target is not None, 'target must enter first')
        if target['role'] != 'player':
            require(len(competitors(m)) < m['capacity'], 'seats full')
            target['role'] = 'player'
        else:
            require(sum(p['role'] == 'spectator' for p in m['players']) < 64,
                    'spectator roster full')
            target['role'] = 'spectator'
        for p in competitors(m):
            p['accepted'] = 0
        target['accepted'] = 0
    elif op == 'accept':
        require(phase == 'lobby' and me is not None and me['role'] == 'player', 'no open seat')
        me['accepted'] = 1
    elif op == 'lock':
        require(phase == 'lobby', 'not in lobby')
        roster = competitors(m)
        require(2 <= len(roster) <= m['capacity'], 'need at least two competitors')
        require(all(p['accepted'] for p in roster), 'every competitor must accept')
        require(isinstance(pool, dict), 'qualified pool records required')
        require(len(pool) >= 3 * len(roster), 'need at least 3N qualified maps')
        require(len(pool) <= 8192, 'candidate pool exceeds 8192 maps')
        for name, card in pool.items():
            require(isinstance(name, str) and bool(MAP_NAME.fullmatch(name)) and
                    isinstance(card, dict) and card.get('name') == name and
                    card.get('kind') == m['settings']['kind'] and type(card.get('tier')) is int,
                    'qualified pool records required')
            pin = card.get('pin')
            require(isinstance(pin, dict) and set(pin) == {'mapcrc', 'zonepin', 'gamemode', 'sha256', 'map_stamp'},
                    'qualified identity required')
            require(isinstance(pin['mapcrc'], str) and bool(HEX8.fullmatch(pin['mapcrc'])) and
                    pin['mapcrc'] != '00000000' and pin['gamemode'] == m['settings']['kind'] and
                    all(isinstance(pin[k], str) and HEX64.fullmatch(pin[k]) for k in ('zonepin', 'sha256')),
                    'qualified identity required')
            stamp = pin['map_stamp']
            require(type(stamp) is list and len(stamp) == 3 and
                    all(type(n) is int and n >= 0 for n in stamp) and stamp[0] > 0, 'qualified stamp required')
        if m['settings']['pool'] is not None:
            require(set(pool) == set(m['settings']['pool']), 'manual pool mismatch')
        order = [p['who'] for p in roster]
        random.Random(m['_seed']).shuffle(order)
        candidates = list(pool)
        random.Random(m['_seed'] + ':pool').shuffle(candidates)
        candidates = candidates[:3 * len(roster)]
        m['_pins'] = {n: copy.deepcopy(pool[n]['pin']) for n in candidates}
        # Event settings/build binding only, not a full game or anti-cheat rules proof.
        identity = dict(settings=m['settings'], maps=candidates, pins=m['_pins'])
        m['ruleset_id'] = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        m.update(phase='draft', maps=[dict(name=n, kind=pool[n]['kind'], tier=pool[n]['tier'], status='pool', by='') for n in candidates],
                 _order=order, _turn=0, turn_who=order[0], turn_kind='ban',
                 round_total=len(roster)-1)
    elif op in ('ban', 'pick'):
        require(phase == 'draft' and m['turn_kind'] == op and m['turn_who'] == actor,
                'not your draft turn')
        card = next((c for c in m['maps'] if c['name'] == data.get('map')), None)
        require(card is not None and card['status'] == 'pool', 'map is not available')
        card.update(status='banned' if op == 'ban' else 'picked', by=actor)
        m['_turn'] += 1
        n = len(m['_order'])
        if m['_turn'] == 2*n:
            selected = [c['name'] for c in m['maps'] if c['status'] == 'picked']
            random.Random(m['_seed'] + ':maps').shuffle(selected)
            m.update(schedule=selected[:-1], reserve=selected[-1], round_index=1,
                     turn_who='', turn_kind='')
            for c in m['maps']:
                if c['name'] == m['reserve']:
                    c['status'] = 'reserve'
            loading(m)
        else:
            order = m['_order'] if m['_turn'] < n else list(reversed(m['_order']))
            m['turn_who'] = order[m['_turn'] % n]
            m['turn_kind'] = 'ban' if m['_turn'] < n else 'pick'
    elif op in ('arrive', 'ready'):
        require(phase == 'loading', 'not loading')
        zonegen = observe(m, data, latched=bool(m['_arrived']))
        if op == 'arrive':
            m['_zonegen'] = zonegen
            if not m['_arrived']:
                for p in competitors(m):
                    p['ready'] = 0
                m['_arrived'] = 1
        else:
            require(m['_arrived'] and me is not None and me['role'] == 'player', 'map has not arrived or no seat')
            me['ready'] = 1
    elif op == 'start':
        require(phase == 'loading' and m['_arrived'], 'map has not arrived')
        require(all(p['ready'] for p in competitors(m)), 'every surviving competitor must ready')
        m['phase'] = 'countdown'
    elif op == 'go':
        require(phase == 'countdown', 'not counting down')
        integer(data, 'elapsed_ms', 5000, 3600000)
        tickrate = rate(data)
        require(abs(tickrate - 1000000 / m['settings']['tick_us']) <= 1e-4, 'wrong effective tickrate')
        m.update(phase='live', _started=1, _rate=tickrate)
    elif op == 'score':
        require(phase == 'live', 'round is not live')
        require(data.get('current_map') == m['current_map'], 'wrong map')
        require(integer(data, 'generation', 1, 7) == m['generation'], 'wrong generation')
        target = next((p for p in competitors(m) if p['who'] == data.get('who')), None)
        require(target is not None, 'not a surviving competitor')
        tickrate = rate(data)
        require(tickrate == m['_rate'], 'round tickrate changed')
        ticks = integer(data, 'ticks', 1, int(m['round_seconds'] * tickrate))
        finish = integer(data, 'elapsed_ms', 1, m['round_seconds']*1000)
        start = integer(data, 'start_elapsed_ms', 0, m['round_seconds']*1000)
        require(start < finish, 'run must start and finish inside live round')
        require(ticks * 1000 / tickrate <= finish - start + 1000 / tickrate + 1,
                'run duration exceeds live elapsed time')
        runid = data.get('runid', '')
        require(bool(RUNID.fullmatch(runid)), 'runid must be 16..64 lowercase hex')
        require(runid not in m['_runs'], 'run already scored')
        require(len(m['_runs']) < 8192, 'score event limit reached; abort or settle')
        m['_runs'].append(runid)
        if not target['best_ticks'] or ticks < target['best_ticks']:
            target.update(best_ticks=ticks, tickrate=tickrate)
    elif op == 'settle':
        require(phase == 'live', 'round is not live')
        integer(data, 'elapsed_ms', m['round_seconds']*1000, 3600000)
        roster = competitors(m)
        dnfs = [p for p in roster if not p['best_ticks']]
        if len(dnfs) == 1:
            losers, note = dnfs, 'Unique DNF eliminated.'
        elif dnfs:
            losers, note = [], 'No contest: multiple/all DNF; alpha tiebreak unavailable.'
        else:
            worst = max(p['best_ticks'] for p in roster)
            losers = [p for p in roster if p['best_ticks'] == worst]
            note = 'Slowest round best eliminated.'
        if len(losers) != 1:
            m.update(phase='aborted', outcome='no-contest', note=note if dnfs else
                     'No contest: tied slowest best; alpha tiebreak unavailable.')
        else:
            losers[0].update(role='eliminated', place=len(roster))
            m.update(phase='results', note=note)
            for c in m['maps']:
                if c['name'] == m['current_map']:
                    c['status'] = 'played'
            if len(roster) == 2:
                competitors(m)[0]['place'] = 1
                m['outcome'] = 'winner'
    elif op in ('advance', 'next'):
        require(phase == 'results', 'results required')
        if m['round_index'] == m['round_total']:
            m['phase'] = 'finished'
        else:
            m['round_index'] += 1
            loading(m)
    elif op == 'leave':
        require(me is not None, 'not entered')
        if phase == 'lobby' or me['role'] == 'spectator':
            m['players'].remove(me)
            if actor == m['host'] and phase == 'lobby':
                m.update(phase='cancelled', note='Host left the lobby.')
        elif me['role'] == 'player' and phase not in TERMINAL:
            m.update(phase='aborted', outcome='no-contest',
                     note='No contest: competitor withdrawal after lock; alpha withdrawal replay unavailable.')
    elif op == 'cancel':
        require(not m['_started'] and phase not in TERMINAL, 'cannot cancel after first GO')
        m.update(phase='cancelled', note='Host cancelled before first GO.')
    elif op == 'abort':
        require(phase not in TERMINAL, 'match is closed')
        m.update(phase='aborted', outcome='no-contest', note='No contest: server aborted match.')
    elif op == 'release':
        require(phase in TERMINAL, 'finish, cancel or abort before release')
        require(data.get('restored') == '1', 'public-mode restoration ACK required')
    else:
        raise Refusal('unknown operation')
    m['revision'] += 1
    return m
