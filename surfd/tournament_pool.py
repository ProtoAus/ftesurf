"""Exact held-build catalogue and explicitly approved native qualification records."""
import json
import os
from pathlib import Path
import stat
import mapmanifest
import tournament_rules as rules

MAX_BYTES = 1 << 20
PIN_FIELDS = ('mapcrc', 'zonepin', 'gamemode', 'sha256', 'map_stamp')


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate registry key')
        out[key] = value
    return out


def registry(path):
    if not path or not Path(path).exists():
        return {}
    try:
        with open(path, 'rb') as fh:
            raw = fh.read(MAX_BYTES + 1)
        rules.require(len(raw) <= MAX_BYTES, 'qualification registry too large')
        data = json.loads(raw, object_pairs_hook=unique_object)
        rules.require(type(data) is dict and set(data) == {'v', 'maps'} and
                      type(data['v']) is int and data['v'] == 1 and type(data['maps']) is dict,
                      'bad qualification registry')
        rules.require(len(data['maps']) <= 8192, 'qualification registry too large')
        for name, profiles in data['maps'].items():
            rules.require(bool(rules.MAP_NAME.fullmatch(name)) and type(profiles) is dict,
                          'bad qualification map')
            for profile, pin in profiles.items():
                rules.require(profile in rules.PROFILES and type(pin) is dict and
                              set(pin) == {'approved', *PIN_FIELDS}, 'bad qualification profile')
                rules.require(type(pin['approved']) is int and pin['approved'] in (0, 1), 'bad approval')
                rules.require(isinstance(pin['mapcrc'], str) and
                              bool(rules.HEX8.fullmatch(pin['mapcrc'])) and pin['mapcrc'] != '00000000',
                              'bad native checksum')
                rules.require(all(isinstance(pin[k], str) and rules.HEX64.fullmatch(pin[k])
                                  for k in ('zonepin', 'sha256')), 'bad qualification pin')
                rules.require(pin['gamemode'] in ('surf', 'bhop'), 'bad qualification mode')
                stamp = pin['map_stamp']
                rules.require(type(stamp) is list and len(stamp) == 3 and
                              all(type(n) is int and n >= 0 for n in stamp) and stamp[0] > 0,
                              'bad qualification stamp')
        return data['maps']
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        raise rules.Refusal('qualification registry unavailable or invalid') from exc


def catalogue(db, d, settings):
    """No hashing on reads. Stat binds trusted provenance to the exact held file."""
    tiers = d.map_tiers()
    rules.require(tiers is not None, 'difficulty catalogue unavailable')
    try:
        # The ordinary map provider deliberately collapses an unreadable library
        # into an empty index. Tournament configuration must distinguish those
        # states; preserve that provider's behavior for ordinary joining.
        with os.scandir(d.maps_root) as entries:
            next(entries, None)
        listed = mapmanifest.read_list(mapmanifest.LIST_PATH)
        bsp, timed = d.map_index()
    except (OSError, ValueError, TypeError) as exc:
        raise rules.Refusal('map catalogue unavailable') from exc
    rules.require(bsp is not None and timed is not None, 'map catalogue unavailable')
    metadata = {r['map']: r for r in listed}
    disabled = mapmanifest.disabled(db, bsp, d.zone_file_index())
    records = registry(d.setting('SURFD_TOURNAMENT_QUALIFICATIONS', ''))
    qualified, unqualified = {}, 0
    for key, name in sorted(bsp.items(), key=lambda item: item[1]):
        row = metadata.get(key, {})
        kind = mapmanifest.map_mode(key)
        tier = tiers.get(key, 0)
        tier = tier if type(tier) is int and 1 <= tier <= 20 else 0
        bit = 1 << (tier - 1) if tier else 1 << 20
        if kind != settings['kind'] or not settings['tiers'] & bit:
            continue
        if key in disabled or key not in timed:
            continue
        pin = records.get(name, {}).get(settings['profile'])
        valid = bool(rules.MAP_NAME.fullmatch(name)) and pin and pin['approved'] == 1 and pin['gamemode'] == kind
        if valid:
            try:
                st = (Path(d.maps_root) / (name + '.bsp')).stat()
                valid = stat.S_ISREG(st.st_mode) and pin['map_stamp'] == [st.st_size, st.st_mtime_ns, st.st_ctime_ns]
            except OSError:
                valid = False
        if valid:
            qualified[name] = dict(name=name, kind=kind, tier=tier, mt=row.get('mt', 0),
                                   kt=row.get('kt', 0), pin={k: pin[k] for k in PIN_FIELDS})
        else:
            unqualified += 1
    # Lex 21 Nov: one build per map, the Momentum one when it qualifies here. Families are mapwatch's `of`
    # (surfd.variant_base: a build listed there was byte-compared with KSF's archive); dropped builds are not
    # "unqualified". Runs after the kind/tier filter: a base and its variant can sit in different tiers.
    base_of = getattr(d, 'variant_base', None)
    if base_of is not None:
        keep = {}
        for name in qualified:
            family = base_of(name) or name
            have = keep.get(family)
            if have is None or (have != family and (name == family or name < have)):
                keep[family] = name
        qualified = {n: qualified[n] for n in sorted(keep.values())}
    rules.require(len(qualified) <= 8192, 'candidate pool exceeds 8192 maps')
    return qualified, unqualified


def selected(db, d, settings):
    qualified, _ = catalogue(db, d, settings)
    if settings['pool'] is not None:
        rules.require(all(n in qualified for n in settings['pool']), 'selected map unavailable or unqualified')
        return {n: qualified[n] for n in settings['pool']}
    return qualified


def revalidate(db, d, match):
    # Added unselected maps cannot invalidate an already frozen event.
    rules.require(isinstance(match.get('settings'), dict) and isinstance(match.get('_pins'), dict),
                  'missing frozen qualification')
    qualified, _ = catalogue(db, d, match['settings'])
    for name in match['schedule'] + [match['reserve']]:
        rules.require(name in qualified and qualified[name]['pin'] == match['_pins'].get(name),
                      'drafted qualification changed or unavailable')
