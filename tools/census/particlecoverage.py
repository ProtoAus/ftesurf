#!/usr/bin/env python3
"""Read-only Source particle coverage audit; never bakes/installs effects.

python tools/census/particlecoverage.py --json <report.json>

Distinguishes map entities, embedded PCFs, registered bakes and translator
support. A translatable system is NOT a runtime/fidelity pass. Missing embedded
PCFs may live in mounted game packs. Decode errors remain counted maps, not
silently omitted successes. Exit 2 means an incomplete census; consult errors.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import sys

# Load the census reader before adding tools/: tools/bsplib.py is a different
# parser. The seek-based census reader avoids reading the entire BSP here.
if __package__:
    from . import bsplib
else:
    import bsplib
TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import dmx
import pcf


def baked_index(path):
    """Parent names only; child links do not cover an entity's effect_name."""
    result = collections.defaultdict(set)
    for line in path.read_text().splitlines():
        fields = line.split()
        if not fields or fields[0].startswith('#'):
            continue
        if len(fields) == 3 and fields[0] == 'particles':
            int(fields[2])  # map-level line count, not an effect definition
            continue
        if len(fields) != 18 or fields[0] != 'psys':
            raise ValueError('expected current 18-column psys index: ' + line)
        if fields[17] == '-':
            result[fields[1]].add(fields[2])
    return result


def audit_map(path, baked, cfgdir):
    with path.open('rb') as stream:
        table = bsplib.lumps(stream)
        if table is None:
            raise ValueError('not a VBSP')
        entities = bsplib.parse_ents(bsplib.lump(stream, table, 0))
    entities = [e for e in entities if e.get('classname') == 'info_particle_system']
    if not entities:
        return None
    effects = collections.Counter(e.get('effect_name', '') for e in entities)
    row = dict(map=path.stem, entities=len(entities),
               start_active=sum(e.get('start_active', '0') == '1' for e in entities),
               effects=dict(effects), baked_effects=sorted(baked),
               unbaked_effects=sorted(set(effects) - baked),
               pcfs=[], defined_effects=[], translatable_effects=[],
               referenced_translatable_effects=[], skipped=[],
               unsupported_operators={}, cfg_matches_current_translator=None,
               errors=[])
    packed = pcf.pcfs_in_map(path)
    if not packed:
        return row
    names, pak = packed
    row['pcfs'] = names
    defined, translated = set(), set()
    unknown = collections.Counter()
    try:
        for name in names:
            try:
                data = pak.read(name)
                doc = dmx.parse(data)
                if doc.format != 'pcf':
                    raise ValueError('DMX format is not pcf: ' + doc.format)
                defined.update(doc.elements[i].name for i in
                               (doc.root.get('particleSystemDefinitions') or []))
                blocks, runtime, skipped = pcf.bake(data, path.stem, unknown)
                translated.update(r['name'] for r in runtime)
                row['skipped'].extend(skipped)
                # The existing writer overwrites per PCF. Do not pretend a
                # multi-library bake can be compared to one generated cfg.
                cfg = cfgdir / (path.stem + '.cfg')
                if len(names) == 1 and baked and cfg.exists():
                    header = pcf.HEADER % dict(map=path.stem, src=Path(name).name,
                                              n=len(blocks), total=len(blocks)+len(skipped))
                    body = header + '\n' + '\n\n'.join(blocks) + '\n'
                    row['cfg_matches_current_translator'] = cfg.read_text() == body
            except Exception as error:
                row['errors'].append(dict(pcf=name, error=str(error)))
    finally:
        pak.close()
    row['defined_effects'] = sorted(defined)
    row['translatable_effects'] = sorted(translated)
    row['referenced_translatable_effects'] = sorted(set(effects) & translated)
    row['unsupported_operators'] = dict(unknown)
    return row


def census(mapsdir, index, cfgdir):
    paths = sorted(mapsdir.glob('*.bsp'))
    if not paths:
        raise ValueError('no BSPs in ' + str(mapsdir))
    baked = baked_index(index)
    rows, errors = [], []
    for path in paths:
        try:
            row = audit_map(path, baked[path.stem], cfgdir)
            if row is not None:
                rows.append(row)
                errors.extend(dict(map=path.stem, **e) for e in row['errors'])
        except Exception as error:
            errors.append(dict(map=path.stem, error=str(error)))
    summary = dict(maps_scanned=len(paths), maps_with_particle_entities=len(rows),
                   particle_entities=sum(r['entities'] for r in rows),
                   maps_with_bakes=sum(bool(r['baked_effects']) for r in rows),
                   maps_with_embedded_pcfs=sum(bool(r['pcfs']) for r in rows),
                   unbaked_maps_with_embedded_pcfs=sum(bool(r['pcfs']) and
                       not r['baked_effects'] for r in rows),
                   maps_with_multiple_pcfs=sum(len(r['pcfs']) > 1 for r in rows),
                   errors=len(errors))
    return dict(summary=summary, maps=rows, errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mapsdir = Path(os.environ.get('MOMENTUM_DIR',
        'C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum'))/'maps'
    parser.add_argument('--mapsdir', type=Path, default=mapsdir)
    parser.add_argument('--index', type=Path, default=TOOLS.parent/'ftesurf/data/mapparticles.txt')
    parser.add_argument('--cfgdir', type=Path, default=TOOLS.parent/'ftesurf/particles')
    parser.add_argument('--json', type=Path, help='write the detailed report here')
    args = parser.parse_args()
    report = census(args.mapsdir, args.index, args.cfgdir)
    print(json.dumps(report['summary'], indent=2))
    for row in report['maps']:
        match = row['cfg_matches_current_translator']
        if match is not None:
            print('%s cfg matches current translator: %s' % (row['map'], match))
    for error in report['errors']:
        print('INCOMPLETE:', json.dumps(error))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + '\n')
    return 2 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
