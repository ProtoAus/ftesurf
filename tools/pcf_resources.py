#!/usr/bin/env python3
"""Read-only PCF graph/material/sheet planner for a future native bake.

    python tools/pcf_resources.py --bsp MAP.bsp --content GAME_OR_DIR_VPK \
        --effect dune_fire_medium_03 --json plan.json

Repeat --content in highest-priority-first order. BSP pak always wins by path;
no implicit installed games are searched. All visible PCF libraries are indexed,
not just the first embedded library. Duplicate definition names are reported
and named lookup refuses ambiguity. Explicit local child references retain their
identity; named empty stubs may resolve across libraries. Missing/corrupt inputs
make the report incomplete (exit 2). A resolved plan is NOT a fidelity, native
translation, material compilation, animation, budget or deployment pass.
"""
import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import struct

import dmx
import pcf
from sourceassets import (Asset, BspSource, Content, ResourceError, content_source,
                          material_path, resolve_vmt)
from vtfsheet import read_sheet

GROUPS = ('emitters', 'initializers', 'operators', 'renderers', 'forces', 'constraints')


def element(doc, index, expected=None):
    if type(index) is not int or not 0 <= index < len(doc.elements):
        raise ResourceError('invalid DMX element reference: ' + repr(index))
    result = doc.elements[index]
    if expected and result.type != expected:
        raise ResourceError('expected %s, got %s' % (expected, result.type))
    return result


def refs(doc, owner, group):
    values = owner.get(group, [])
    if not isinstance(values, list):
        raise ResourceError('expected element array: ' + group)
    return [(i, element(doc, i)) for i in values]


def finite_values(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ResourceError('nonfinite PCF attribute')
    if isinstance(value, dict):
        for v in value.values():
            finite_values(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            finite_values(v)


@dataclass
class System:
    asset: Asset
    doc: dmx.Dmx
    index: int

    @property
    def entry(self):
        return self.doc.elements[self.index]

    @property
    def key(self):
        return self.asset.path + '#' + str(self.index)


class Libraries:
    def __init__(self, content):
        self.content = content
        self.byname = defaultdict(list)
        self.assets, self.errors = [], []
        for path in content.paths():
            if not path.endswith('.pcf'):
                continue
            try:
                asset = content.read(path)
                self.add(asset, dmx.parse(asset.data))
            except (dmx.DmxError, ValueError, OSError, struct.error, IndexError) as error:
                self.errors.append(dict(path=path, error=str(error)))

    def add(self, asset, doc):
        if doc.format != 'pcf' or doc.root is None:
            raise ResourceError('not a nonempty PCF document')
        definitions = refs(doc, doc.root, 'particleSystemDefinitions')
        if len({i for i, _ in definitions}) != len(definitions):
            raise ResourceError('duplicate root definition reference')
        for entry in doc.elements:
            finite_values(entry.attr)
        systems = []
        for i, entry in definitions:
            element(doc, i, 'DmeParticleSystemDefinition')
            for group in GROUPS + ('children',):
                refs(doc, entry, group)
            systems.append(System(asset, doc, i))
        # Publish only after validating the complete library.
        self.assets.append(dict(asset.provenance(), definitions=len(systems),
                                unnamed_definitions=sum(not s.entry.name for s in systems)))
        for system in systems:
            if system.entry.name and not system.entry.get('preventNameBasedLookup', False):
                self.byname[system.entry.name].append(system)

    def find(self, name):
        hits = self.byname.get(name, [])
        if not hits:
            raise ResourceError('missing particle definition: ' + name)
        if len(hits) != 1:
            raise ResourceError('ambiguous particle definition %s: %s' %
                                (name, ', '.join(s.key for s in hits)))
        return hits[0]

    def child(self, parent, wrapper):
        index = wrapper.get('child')
        target = element(parent.doc, index, 'DmeParticleSystemDefinition')
        if target.attr:
            return System(parent.asset, parent.doc, index)
        return self.find(target.name)

    def graph(self, names):
        systems, edges, errors, visiting = {}, [], [], set()

        def visit(system):
            if len(visiting) >= 64 or len(systems) + len(visiting) >= 4096:
                raise ResourceError('particle graph depth/count limit')
            if system.key in visiting:
                raise ResourceError('cyclic particle graph: ' + system.key)
            if system.key in systems:
                return
            visiting.add(system.key)
            for group in GROUPS:
                refs(system.doc, system.entry, group)
            for _i, wrapper in refs(system.doc, system.entry, 'children'):
                if wrapper.type != 'DmeParticleChild':
                    raise ResourceError('invalid particle child wrapper')
                child = self.child(system, wrapper)
                delay = wrapper.get('delay', 0.0)
                if not isinstance(delay, (int, float)) or not math.isfinite(delay) or delay < 0:
                    raise ResourceError('invalid child delay')
                edges.append(dict(parent=system.key, child=child.key, delay=delay))
                visit(child)
            visiting.remove(system.key)
            systems[system.key] = system

        roots = []
        for name in names:
            # One failed root cannot leave a partially successful graph behind.
            saved_systems, saved_edges = dict(systems), list(edges)
            try:
                root = self.find(name)
                visit(root)
                roots.append(dict(name=name, system=root.key))
            except ResourceError as error:
                systems, edges = saved_systems, saved_edges
                visiting.clear()
                errors.append(dict(effect=name, error=str(error)))
        return roots, systems, edges, errors


def material_report(content, name):
    shader, params, vmts = resolve_vmt(content, name)
    textures = {}
    for key in pcf_texture_keys():
        value = params.get('$' + key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ResourceError('non-scalar texture parameter: ' + key)
        if value.lower() == 'env_cubemap' or value.lower().startswith('_rt_'):
            textures[key] = dict(runtime_target=value)
            continue
        asset = content.read(material_path(value, '.vtf'))
        textures[key] = asset.provenance()
        # Sheet parsing is scoped to the base sprite texture, not bumpmaps.
        if key == 'basetexture':
            textures[key]['sheet'] = read_sheet(asset.data)
    if 'basetexture' not in textures:
        raise ResourceError('particle material has no base texture: ' + name)
    return dict(shader=shader, params=params, vmts=vmts, textures=textures,
                fidelity='unverified; shader behavior is not translated')


def pcf_texture_keys():
    # Reuse the plugin dependency key list, not the regex dependency walker.
    from mapdeps import TEXKEYS
    return TEXKEYS


def system_report(content, system):
    entry = system.entry
    groups = {group: [dict(e.attr) for _, e in refs(system.doc, entry, group)]
              for group in GROUPS}
    row = dict(name=entry.name, system=system.key, library=system.asset.provenance(),
               attrs={k: v for k, v in entry.attr.items() if k not in GROUPS + ('children',)},
               groups=groups, material=None,
               legacy_translator_unrecognized=sorted({str(e.get('functionName'))
                   for group in GROUPS for _, e in refs(system.doc, entry, group)
                   if e.get('functionName') not in pcf.KNOWN}))
    name = entry.get('material', '')
    if name:
        row['material'] = material_report(content, name)
        sheet = row['material']['textures']['basetexture'].get('sheet')
        selections = [e for e in groups['initializers'] if e.get('functionName') == 'Sequence Random']
        if len(selections) > 1:
            raise ResourceError('multiple primary Sequence Random initializers')
        if selections:
            lo = selections[0].get('sequence_min', 0)
            hi = selections[0].get('sequence_max', 0)
        else:
            lo = hi = entry.get('sequence_number', 0)
        if type(lo) is not int or type(hi) is not int or not 0 <= lo <= hi < 64:
            raise ResourceError('invalid primary sequence range')
        row['primary_sequences'] = list(range(lo, hi + 1))
        if sheet and any(i not in sheet['sequences'] for i in row['primary_sequences']):
            raise ResourceError('primary sequence absent from base texture sheet')
        row['native_limits'] = ['no translation attempted', 'single-channel native stepping only',
                                'frame blending/material/forces/children require bake policy']
    return row


def plan(content, names):
    libraries = Libraries(content)
    roots, systems, edges, errors = libraries.graph(names)
    rows = []
    errors = list(libraries.errors) + errors
    for key in sorted(systems):
        try:
            rows.append(system_report(content, systems[key]))
        except (ValueError, OSError, struct.error) as error:
            errors.append(dict(system=key, error=str(error)))
            rows.append(dict(name=systems[key].entry.name, system=key, unresolved=True))
    return dict(schema=1, status='incomplete' if errors else 'resolved',
                scope='resource resolution only; no bake/render/fidelity acceptance',
                libraries=libraries.assets, archive_diagnostics=content.issues,
                ambiguous_names={name: [s.key for s in hits]
                                 for name, hits in sorted(libraries.byname.items()) if len(hits) > 1},
                roots=roots, systems=rows, edges=edges, errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bsp', type=Path)
    parser.add_argument('--content', type=Path, action='append', default=[])
    parser.add_argument('--effect', action='append', required=True)
    parser.add_argument('--json', type=Path, required=True, help='report destination, never a generated particle cfg')
    args = parser.parse_args()
    pak = None
    try:
        pak = BspSource(args.bsp) if args.bsp else None
        sources = ([pak] if pak else []) + [content_source(p) for p in args.content]
        report = plan(Content(sources), args.effect)
    except (ValueError, OSError, struct.error) as error:
        report = dict(schema=1, status='incomplete', errors=[dict(error=str(error))])
    finally:
        if pak:
            pak.close()
    args.json.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('%s: %d libraries, %d graph systems, %d child edges, %d errors' %
          (report['status'], len(report.get('libraries', [])), len(report.get('systems', [])),
           len(report.get('edges', [])), len(report['errors'])))
    for error in report['errors']:
        print('INCOMPLETE:', json.dumps(error))
    return 2 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
