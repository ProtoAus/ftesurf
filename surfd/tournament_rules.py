"""Pure, bounded free-alpha tournament transitions. No wall-clock progression."""
import copy
import hashlib
import json
import math
import random
import re

SERVER_OPS = frozenset(('arrive', 'go', 'score', 'settle', 'advance', 'abort', 'release', 'autostart'))
TERMINAL = frozenset(('finished', 'cancelled', 'aborted'))
RUNID = re.compile(r'[0-9a-f]{16,64}\Z')
# sv_tournament.qc abort reasons, as players read them.
ABORT_REASONS = {
    'alpha_lobby_timeout': 'the tournament timed out waiting',  # also sent for a host who left
    'loading_timeout': 'players did not get ready in time',
    'host_gone': 'the host left the server',
    'map_change_failed': 'the server could not load the map',
    'unqualified_loaded_table': "the map's zones or rules changed",
    'loaded_ruleset_changed': "the map's zones or rules changed",
    'interrupted_live_round': 'the server lost contact with the tournament service',
    'service_interrupted': 'the server lost contact with the tournament service',
    'reservation_race': 'someone else joined the server first',
    'competitor_lost_during_countdown': 'a player dropped during the countdown',
}
# The game server sends the note URL-escaped inside one client line capped at 1024 characters.
NOTE_BYTES = 160
NAME_BYTES = 20  # per name inside a note, so two names, a count and the winner fit NOTE_BYTES

TIER_MASK = 1023 | 1 << 20
MAP_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
HEX8 = re.compile(r'[0-9a-f]{8}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
PROFILES = {
    'default': dict(movement='default', tick_us=15000, label='Default / map tick', unranked=0),
    'hl2-pre': dict(movement='hl2-pre-v1', tick_us=15000, label='HL2 pre', unranked=1),
    'hl2-post': dict(movement='hl2-post-v1', tick_us=15000, label='HL2 post', unranked=1),
    'ag-100': dict(movement='ag100-v1', tick_us=10000, label='AG 100', unranked=1),
    'ag-250': dict(movement='ag250-v1', tick_us=4000, label='AG 250', unranked=1),
    'ag-1000': dict(movement='ag1000-v1', tick_us=1000, label='AG 1000', unranked=1),
    'cs16': dict(movement='cs16-v1', tick_us=10000, label='CS 1.6', unranked=1),
}
# The default profile keeps each map kind's own tick (P1639): surf 66.7 Hz, bhop 100 Hz (mode_bhop.cfg). A node running
# the default profile reports either between matches and reaches the round's tick when it loads the drafted map.
KIND_TICK = {'surf': 15000, 'bhop': 10000}


def tick_for(profile, kind):
    return KIND_TICK[kind] if profile == 'default' else PROFILES[profile]['tick_us']


def node_ticks(profile):
    return tuple(sorted(set(KIND_TICK.values()))) if profile == 'default' else (PROFILES[profile]['tick_us'],)


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
                tick_us=tick_for(data['profile'], data['kind']), pool=pool)


def observe(match, data, latched=True):
    require(data.get('current_map') == match['current_map'], 'wrong map')
    # Up to 7 scheduled rounds plus the reserve.
    require(integer(data, 'generation', 1, 8) == match['generation'], 'wrong generation')
    require(integer(data, 'round', 1, 8) == match['round_index'], 'wrong round')
    require(data.get('ruleset') == match.get('ruleset_id') and bool(match.get('ruleset_id')), 'wrong ruleset')
    require(match.get('settings', {}).get('profile') in PROFILES and isinstance(match.get('_pins'), dict),
            'missing frozen settings')
    profile = PROFILES[match['settings']['profile']]
    require(data.get('movement') == profile['movement'], 'wrong movement')
    for key in ('tick_us', 'clock_us'):
        require(integer(data, key, 1000, 15000) == match['settings'].get('tick_us'), 'wrong ' + key)
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


def short(note, limit=NOTE_BYTES):
    """Caps text at `limit` bytes of UTF-8, cutting on a character boundary."""
    raw = note.encode()
    return note if len(raw) <= limit else raw[:limit - 3].decode(errors='ignore') + '...'


def nick(player):
    return short(player['name'], NAME_BYTES)


def listed(players):
    names = [nick(p) for p in players]
    if len(names) > 2:
        extra = len(names) - 2
        return '%s, %s and %d other%s' % (names[0], names[1], extra, '' if extra == 1 else 's')
    return ' and '.join(names)


def crown(match, note):
    """Declares a lone survivor the winner; returns the note with the win appended."""
    left = competitors(match)
    if len(left) != 1:
        return note
    left[0]['place'] = 1
    match['outcome'] = 'winner'
    return note + ' %s wins!' % nick(left[0])


def launched(match):
    # Sticky: party Start (menu_started), first arrival (_launched) or GO; loading() clears _arrived every round.
    return (bool(match.get('menu_started') or match.get('_launched') or match.get('_arrived') or
                 match.get('_started')) or match.get('round_index', 0) > 1 or
            match['phase'] not in ('lobby', 'draft', 'loading'))


def to_lobby(match, note):
    """Pre-launch roster change: the draft is cleared, remaining accepts stay."""
    # ruleset_id/_pins stay until the next lock: sv_tournament.qc holds a match whose ruleset changes outside lobby.
    match.update(phase='lobby', maps=[], schedule=[], reserve='', turn_who='', turn_kind='',
                 round_index=0, generation=0, round_total=0, current_map='', note=note,
                 _order=[], _turn=0, _arrived=0, _zonegen=0, _rate=0)
    for p in match['players']:
        p.update(ready=0, best_ticks=0, tickrate=0)
        if 'menu_ready' in p:
            p['menu_ready'] = 0


def require_current_settings(match):
    # Do not invent settings, pins or renewed consent for persisted Alpha state.
    # State/leave/cancel/abort/restoration-gated release stay available.
    configured = match.get('settings')
    require(type(configured) is dict and
            set(configured) == {'kind', 'tiers', 'profile', 'tick_us', 'pool'} and
            configured.get('profile') in PROFILES and configured.get('kind') in KIND_TICK and
            configured.get('tick_us') == tick_for(configured['profile'], configured['kind']),
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
    if op in ('configure', 'lock', 'start', 'autostart'):
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
        # Before launch the host may still unseat a competitor; the draft then starts over.
        require(phase == 'lobby' or (phase in ('draft', 'loading') and not launched(m)), 'roster frozen')
        target = next((p for p in m['players'] if p['who'] == data.get('target')), None)
        require(target is not None, 'target must enter first')
        require(phase == 'lobby' or target['role'] == 'player', 'roster frozen')
        if target['role'] != 'player':
            require(len(competitors(m)) < m['capacity'], 'seats full')
            target['role'] = 'player'
        else:
            require(sum(p['role'] == 'spectator' for p in m['players']) < 64,
                    'spectator roster full')
            target['role'] = 'spectator'
        # Only the moved player's consent is cleared; the others accepted their own seats.
        target['accepted'] = 0
        if phase != 'lobby':
            to_lobby(m, '%s was moved to spectators: back to the lobby. The host can start the draft again.'
                     % nick(target))
    elif op == 'accept':
        require(phase == 'lobby' and me is not None and me['role'] == 'player', 'no open seat')
        if me['accepted']:
            return m  # a repeat changes nothing, not even the revision
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
                m['_arrived'] = m['_launched'] = 1
        else:
            require(m['_arrived'] and me is not None and me['role'] == 'player', 'map has not arrived or no seat')
            if me['ready']:
                return m  # a repeat changes nothing, not even the revision
            me['ready'] = 1
    elif op in ('start', 'autostart'):
        require(phase == 'loading' and m['_arrived'], 'map has not arrived')
        if op == 'autostart':
            # The game server vouches for every survivor it does not name in `absent`; it names a player
            # 120 s after arrival at the earliest, after 60 s of continuous absence (up to 300 s while
            # someone is still connecting). Named players are forfeited first.
            roster = competitors(m)
            raw = data.get('absent') or ''
            require(isinstance(raw, str), 'absent list invalid')
            absent = raw.split(',') if raw else []
            unready = {p['who']: p for p in roster if not p['ready']}
            require(len(set(absent)) == len(absent) and all(who in unready for who in absent), 'absent list invalid')
            if absent and len(absent) == len(roster) and (m['round_index'] > 1 or m.get('_started')):
                # Places earned in earlier rounds stand; the survivors share first, nobody forfeits.
                for p in roster:
                    p['place'] = 1
                m.update(phase='finished', outcome='shared',
                         note='Nobody arrived for round %d: %s share first place.' % (m['round_index'], listed(roster)))
            elif absent and len(absent) == len(roster):
                m.update(phase='aborted', outcome='no-contest', note='No contest: nobody arrived.')
            else:
                gone = [unready[who] for who in absent]
                for p in roster:
                    if p['who'] in absent:
                        p.update(role='eliminated', place=len(roster) - len(gone) + 1)
                    else:
                        p['ready'] = 1
                if gone:
                    m['note'] = crown(m, "%s didn't arrive and %s out." % (listed(gone), 'is' if len(gone) == 1 else 'are'))
                    if len(competitors(m)) == 1:
                        m['phase'] = 'finished'
        if m['phase'] == 'loading':
            require(all(p['ready'] for p in competitors(m)), 'every surviving competitor must ready')
            m['phase'] = 'countdown'
    elif op == 'go':
        require(phase == 'countdown', 'not counting down')
        integer(data, 'elapsed_ms', 5000, 3600000)
        tickrate = rate(data)
        require(abs(tickrate - 1000000 / m['settings']['tick_us']) <= 1e-4, 'wrong effective tickrate')
        m.update(phase='live', _started=1, _launched=1, _rate=tickrate)
    elif op == 'score':
        require(phase == 'live', 'round is not live')
        require(data.get('current_map') == m['current_map'], 'wrong map')
        require(integer(data, 'generation', 1, 8) == m['generation'], 'wrong generation')
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
        if len(dnfs) == len(roster):
            losers, note = [], 'Nobody finished %s: everyone goes through.' % m['current_map']
        elif dnfs:
            losers = dnfs
            note = '%s did not finish and %s out.' % (listed(dnfs), 'is' if len(dnfs) == 1 else 'are')
        else:
            worst = max(p['best_ticks'] for p in roster)
            losers = [p for p in roster if p['best_ticks'] == worst]
            note = ('%s had the slowest time and is out.' if len(losers) == 1 else
                    '%s tied for the slowest time and are out.') % listed(losers)
            if len(losers) == len(roster):
                losers, note = [], 'Everyone tied: everyone goes through.'
        for p in losers:
            p.update(role='eliminated', place=len(roster) - len(losers) + 1)
        for c in m['maps']:
            if c['name'] == m['current_map']:
                c['status'] = 'played'
        m.update(phase='results', note=crown(m, note))
    elif op in ('advance', 'next'):
        require(phase == 'results', 'results required')
        survivors = competitors(m)
        spare = next((c for c in m['maps'] if c['name'] == m['reserve'] and c['status'] == 'reserve'), None)
        if len(survivors) <= 1:
            m['phase'] = 'finished'
        elif m['round_index'] < m['round_total']:
            m['round_index'] += 1
            loading(m)
        elif spare is not None:
            # The reserve is played once; 'picked' is the status the menu and HUD already show.
            spare['status'] = 'picked'
            m['schedule'].append(spare['name'])
            m['round_total'] += 1
            m['round_index'] += 1
            m['note'] = 'Extra round on the reserve map %s.' % spare['name']
            loading(m)
        else:
            for p in survivors:
                p['place'] = 1
            m.update(phase='finished', outcome='shared',
                     note='Out of maps: %s share first place.' % listed(survivors))
    elif op == 'leave':
        require(me is not None, 'not entered')
        if phase == 'lobby' or me['role'] == 'spectator':
            m['players'].remove(me)
            if actor == m['host'] and phase == 'lobby':
                m.update(phase='cancelled', note='Host left the lobby.')
        elif me['role'] == 'player' and phase not in TERMINAL:
            if not launched(m):
                m['players'].remove(me)
                if actor == m['host']:
                    m.update(phase='cancelled', note='Host left the lobby.')
                else:
                    to_lobby(m, '%s left: back to the lobby. The host can start the draft again.' % nick(me))
            elif len(competitors(m)) > 1:
                # Forfeit, host included: last place among those still in (autostart replaces host Start).
                me.update(role='eliminated', place=len(competitors(m)))
                m['note'] = crown(m, '%s left the tournament.' % nick(me))
                if len(competitors(m)) == 1:
                    m['phase'] = 'finished'
    elif op == 'cancel':
        require(not m['_started'] and phase not in TERMINAL, 'cannot cancel after first GO')
        m.update(phase='cancelled', note='Host cancelled before first GO.')
    elif op == 'abort':
        require(phase not in TERMINAL, 'match is closed')
        reason = ABORT_REASONS.get(data.get('reason'), 'the server stopped the match')
        m.update(phase='aborted', outcome='no-contest', note='No contest: %s.' % reason)
    elif op == 'release':
        require(phase in TERMINAL, 'finish, cancel or abort before release')
        require(data.get('restored') == '1', 'public-mode restoration ACK required')
    else:
        raise Refusal('unknown operation')
    if isinstance(m.get('note'), str):
        m['note'] = short(m['note'])
    m['revision'] += 1
    return m


RATING_START, RATING_K = 1000.0, 32.0


def standings(matches):
    """Tournament stats (Lex 21 Nov) from finished matches' final places, oldest first. Rating is Elo over every pair
    in a match (a better place wins the pair, an equal place draws), K / (n - 1) per pair so one match moves a rating
    by at most K; all of a match's changes use the ratings from before it. Shared first place counts as `shared`."""
    table = {}
    for m in matches:
        if not isinstance(m, dict) or m.get('phase') != 'finished':
            continue
        seen, ranked = set(), []
        for p in m.get('players') or ():
            who, place = (p.get('who'), p.get('place')) if isinstance(p, dict) else (None, None)
            if isinstance(who, str) and who and who not in seen and type(place) is int and place > 0:
                seen.add(who)
                ranked.append(p)
        if len(ranked) < 2:
            continue
        before = {p['who']: table.get(p['who'], {}).get('rating', RATING_START) for p in ranked}
        n, firsts = len(ranked), sum(1 for p in ranked if p['place'] == 1)
        for a in ranked:
            change = 0.0
            for b in ranked:
                if b is not a:
                    score = 1.0 if a['place'] < b['place'] else 0.5 if a['place'] == b['place'] else 0.0
                    expect = 1.0 / (1.0 + 10 ** ((before[b['who']] - before[a['who']]) / 400.0))
                    change += RATING_K * (score - expect) / (n - 1)
            row = table.setdefault(a['who'], dict(who=a['who'], name='', rating=RATING_START, played=0, wins=0,
                                                  shared=0, best=0))
            row['rating'] = before[a['who']] + change
            row['played'] += 1
            if isinstance(a.get('name'), str) and a['name']:
                row['name'] = short(a['name'], NAME_BYTES)
            if a['place'] == 1:
                row['wins' if firsts == 1 else 'shared'] += 1
            row['best'] = min(row['best'] or a['place'], a['place'])
    rows = sorted(table.values(), key=lambda r: (-r['rating'], -r['wins'], -r['played'], r['who']))
    for r in rows:
        r['rating'] = int(round(r['rating']))
    return rows
