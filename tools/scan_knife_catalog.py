#!/usr/bin/env python3
"""Generate viewmodel metadata, NOT game assets, from an installed Legacy VPK.

Run with --vpk <pak01_dir.vpk> --output src/client/cl_knife_catalog_data.qc.
World models, animation libraries and inventory icons are deliberately not choices.
The generated paths still require the player's own mounted installation at runtime.
"""
import argparse
import json
from pathlib import Path
import posixpath
import re
import struct

from sourceassets import VpkSource, Content, ResourceError, resolve_vmt, material_path

KNIFE_NAMES = {
    'knife': 'Original CS:GO knife', 'bayonet': 'Bayonet', 'butterfly': 'Butterfly',
    'canis': 'Survival knife', 'cord': 'Paracord knife', 'css': 'Classic knife',
    'default_ct': 'Default CT knife', 'default_t': 'Default T knife',
    'falchion_advanced': 'Falchion', 'flip': 'Flip knife', 'gg': 'Golden knife',
    'ghost': 'Spectral Shiv', 'gut': 'Gut knife', 'gypsy_jackknife': 'Navaja',
    'karam': 'Karambit', 'm9_bay': 'M9 Bayonet', 'outdoor': 'Nomad knife',
    'push': 'Shadow Daggers', 'skeleton': 'Skeleton knife', 'stiletto': 'Stiletto',
    'survival_bowie': 'Bowie knife', 'tactical': 'Huntsman knife', 'ursus': 'Ursus',
    'widowmaker': 'Talon knife',
}


class Mdl:
    def __init__(self, source, path):
        self.source, self.path = source, path
        self.data = source.read(path).data
        if len(self.data) < 408 or self.data[:4] != b'IDST' or self.u32(4) != 49:
            raise ResourceError('not a complete v49 viewmodel: ' + path)
        if not 0 < self.u32(156) <= 256:
            raise ResourceError('viewmodel bone limit: ' + path)

    def span(self, start, count, stride):
        if start < 0 or count < 0 or stride < 0 or start + count * stride > len(self.data):
            raise ResourceError('MDL span outside file: ' + self.path)
        return start

    def u32(self, offset):
        self.span(offset, 1, 4)
        return struct.unpack_from('<I', self.data, offset)[0]

    def text(self, offset, limit=256):
        self.span(offset, 1, 1)
        end = self.data.find(b'\0', offset, min(len(self.data), offset + limit))
        if end < 0:
            raise ResourceError('unterminated MDL name: ' + self.path)
        return self.data[offset:end].decode('ascii')

    def materials(self):
        count, offset = self.u32(204), self.u32(208)
        ndirs, dirs = self.u32(212), self.u32(216)
        if count > 256 or ndirs > 64:
            raise ResourceError('MDL material limits: ' + self.path)
        self.span(offset, count, 64); self.span(dirs, ndirs, 4)
        directories = [self.text(self.u32(dirs + i * 4)) for i in range(ndirs)]
        result = []
        self.material_overrides = set()
        for i in range(count):
            base = offset + i * 64
            name = self.text(base + self.u32(base))
            candidates = [('materials/' + d + name + '.vmt').replace('\\', '/').lower() for d in directories]
            found = None
            for candidate in candidates:
                normalized = posixpath.normpath(candidate)
                if not normalized.startswith('materials/') or ':' in normalized:
                    raise ResourceError('material reference escapes asset root: ' + self.path)
                if normalized in self.source.entries:
                    found = normalized
                    if normalized != candidate:
                        self.material_overrides.add(normalized)
                    break
            if found is None:
                raise ResourceError('unresolved model material: ' + self.path + ':' + name)
            result.append(found)
        return result

    def meshes(self):
        """Mirror the loader's body:model:lLOD:mMesh surface names and skin0 slots."""
        materials = self.materials()
        skinrefs, skins, skinofs = self.u32(220), self.u32(224), self.u32(228)
        if not 0 < skinrefs <= 256 or not 0 < skins <= 256:
            raise ResourceError('MDL skin limits: ' + self.path)
        self.span(skinofs, skinrefs * skins, 2)
        slots = struct.unpack_from('<%dH' % skinrefs, self.data, skinofs)
        vtx = self.source.read(self.path[:-4] + '.dx90.vtx').data
        if len(vtx) < 36 or struct.unpack_from('<I', vtx)[0] != 7:
            raise ResourceError('unsupported viewmodel VTX: ' + self.path)
        lods = struct.unpack_from('<I', vtx, 20)[0]
        if not 0 < lods <= 8:
            raise ResourceError('viewmodel LOD limit: ' + self.path)
        count, offset = self.u32(232), self.u32(236)
        if not 0 < count <= 128:
            raise ResourceError('MDL bodypart limit: ' + self.path)
        self.span(offset, count, 16)
        result = []
        for b in range(count):
            body = offset + b * 16
            bodyname = self.text(body + self.u32(body))
            models, modelofs = self.u32(body + 4), body + self.u32(body + 12)
            if models > 128:
                raise ResourceError('MDL submodel limit: ' + self.path)
            self.span(modelofs, models, 148)
            for m in range(models):
                model = modelofs + m * 148
                name = self.text(model, 64)
                nmesh, meshofs = self.u32(model + 72), model + self.u32(model + 76)
                if nmesh > 128:
                    raise ResourceError('MDL mesh limit: ' + self.path)
                self.span(meshofs, nmesh, 116)
                for mesh in range(nmesh):
                    slot = self.u32(meshofs + mesh * 116)
                    if slot >= len(slots) or slots[slot] >= len(materials):
                        raise ResourceError('MDL mesh material index: ' + self.path)
                    for lod in range(lods):
                        result.append((f'{bodyname}:{name}:l{lod}:m{mesh}', materials[slots[slot]]))
        return result

    def animations(self):
        model = self
        if not self.u32(180) and self.u32(336):
            if self.u32(336) != 1:
                raise ResourceError('unsupported nested/multiple animation includes: ' + self.path)
            inc = self.u32(340); self.span(inc, 1, 8)
            path = self.text(inc + self.u32(inc + 4)).replace('\\', '/').lower()
            if not re.fullmatch(r'models/weapons/v_knife_[a-z0-9_]+\.mdl', path) and path not in (
                    'models/weapons/v_ct_knife_anim.mdl', 'models/weapons/v_t_knife_anim.mdl'):
                raise ResourceError('unexpected weapon include path: ' + self.path)
            model = Mdl(self.source, path)
        n, offset = model.u32(180), model.u32(184)
        if n > 128:
            raise ResourceError('animation table limit: ' + self.path)
        model.span(offset, n, 100)
        return [model.text(offset + i * 100 + model.u32(offset + i * 100 + 4)) for i in range(n)
                if not model.u32(offset + i * 100 + 12) & 4]


def preferred(names, choices, contains=''):
    return next((n for n in choices if n in names),
                next((n for n in names if contains and contains in n.lower()), ''))


def friendly(path):
    name = Path(path).stem.removeprefix('v_').replace('_', ' ')
    name = re.sub(r'variant([a-z])\b', r'variant \1', name)
    name = name.title()
    for word in ('Fbi', 'Gign', 'Gsg9', 'Idf', 'Sas', 'St6', 'Swat', 'Ctm'):
        name = name.replace(word, word.upper())
    return name


def generate(vpk):
    source, content = VpkSource(vpk), None
    content = Content([source])
    roots = sorted(p for p in source.entries if re.fullmatch(r'models/weapons/v_knife(?:_[a-z0-9_]+)?\.mdl', p)
                   and not p.endswith(('_anim.mdl', '_inspect.mdl')))
    first = ['models/weapons/v_knife_butterfly.mdl', 'models/weapons/v_knife_m9_bay.mdl']
    knives = first + [p for p in roots if p not in first]
    # An obsolete root can be installed without its external animation file.
    # Never advertise it or substitute another knife's animation/bind pose.
    complete, excluded = [], []
    for path in knives:
        model = Mdl(source, path)
        if model.u32(180) and model.u32(352):
            ani = model.text(model.u32(348)).replace(chr(92), '/').lower()
            if ani not in source.entries:
                excluded.append({'path': path, 'reason': 'missing external animation file'})
                continue
        complete.append(path)
    knives = complete
    pieces = sorted(p for p in source.entries if p.startswith('models/weapons/v_models/arms/')
                    and p.endswith('.mdl') and not p.endswith('_icon.mdl'))
    hands, layers = [], []
    for path in pieces:
        name = Path(path).stem
        if name.startswith(('v_glove_', 'v_bare_', 'v_ghost_')):
            hands.append(path)
        elif name.startswith('v_sleeve_') or 'watch' in name:
            layers.append(path)
        else:
            raise ResourceError('unclassified first-person arm piece: ' + path)
    hands = ['models/weapons/ct_arms.mdl', 'models/weapons/t_arms.mdl'] + hands
    if len(knives) + 1 > 32 or len(hands) > 32 or len(layers) + 2 > 64:
        raise ResourceError('catalog exceeds runtime table bounds')
    lines = ['/* Generated by tools/scan_knife_catalog.py from installed Legacy content.',
             ' * Metadata only: no game assets, local install paths or inventory data. */',
             'void() KCAT_Data =', '{',
             f'\tkcat_knives = {len(knives) + 1}; kcat_hands = {len(hands)}; kcat_layers = {len(layers) + 2};',
             '\tKCAT_Row(0i, "Counter-Strike: Source", "models/weapons/v_knife_t.mdl");',
             '\tKCAT_Row(64i, "Automatic sleeves", "");', '\tKCAT_Row(65i, "No sleeves / watch", "");']
    records = []
    quote = lambda value: json.dumps(value, ensure_ascii=True)
    groups = [(i + 1, p, 'knife') for i, p in enumerate(knives)]
    groups += [(32 + i, p, 'hands') for i, p in enumerate(hands)]
    groups += [(66 + i, p, 'layer') for i, p in enumerate(layers)]
    for row, path, kind in groups:
        model = Mdl(source, path)
        meshes = model.meshes()
        stem = Path(path).stem
        label = KNIFE_NAMES.get(stem.removeprefix('v_knife_') if stem != 'v_knife' else 'knife', friendly(path)) if kind == 'knife' else friendly(path)
        if path.endswith('/ct_arms.mdl'): label = 'Counter-Terrorist (complete)'
        if path.endswith('/t_arms.mdl'): label = 'Terrorist (complete)'
        paint, hide, skin, neutral = [], [], [], []
        base, mask = '', ''
        if kind == 'knife':
            for surface, material in meshes:
                if '/arms/' in material or '/hand/' in material or '/hands/' in material:
                    hide.append(surface)
                else:
                    shader, params, _ = resolve_vmt(content, material)
                    diffuse = params.get('$basetexture', '')
                    if not isinstance(diffuse, str) or not diffuse:
                        raise ResourceError('missing knife diffuse: ' + material)
                    candidate = material_path(diffuse, '.vtf')
                    # Only surfaces sharing this diffuse may share the preview shader.
                    if not base: base = candidate
                    if candidate == base:
                        paint.append(surface)
                    elif stem in ('v_knife', 'v_knife_gg'):
                        # These roots contain both T/CT knife bodygroup variants.
                        # Select the first, not two overlapping knives at once.
                        hide.append(surface)
                        continue
                    matstem = Path(material).stem
                    for candidate_mask in [f'materials/models/weapons/customization/{matstem}/{matstem}_masks.vtf',
                                           f'materials/models/weapons/customization/{matstem}_masks.vtf']:
                        if candidate_mask in source.entries: mask = candidate_mask
        for surface, material in meshes:
            if material.endswith('/v_model_base_arms.vmt'): skin.append(surface)
            if kind == 'hands':
                _, params, _ = resolve_vmt(content, material)
                diffuse = material_path(params.get('$basetexture', ''), '.vtf')
                if diffuse not in source.entries:
                    # Inventory gloves are paint-system templates, not baked skins.
                    # A local neutral AO preview is honest; a missing-texture check is not.
                    family = Path(material).parent.name
                    choices = [f'materials/models/weapons/customization/{family}/ao.vtf',
                               f'materials/models/weapons/customization/{family}/{family}_ao.vtf']
                    ao = next((p for p in choices if p in source.entries), None)
                    if ao is None:
                        raise ResourceError('no neutral glove preview texture: ' + material)
                    neutral.extend((surface, ao))
        if neutral: label += ' (neutral preview)'
        lines.append(f'\tKCAT_Row({row}i, {quote(label)}, {quote(path)});')
        if neutral: lines.append(f'\tKCAT_Set({row}i, KCAT_NEUTRAL, {quote("|".join(neutral))});')
        rules = ''.join('replace "%s" "%s"\n' % (surface, material.removeprefix('materials/'))
                        for surface, material in meshes if material in model.material_overrides
                        and not material.endswith('/v_model_base_arms.vmt'))
        lines.append('\tKCAT_Mesh(%di, %s, %s, %s, %s, %s, %s);' %
                     (row, quote(base), quote(mask), quote('|'.join(paint)), quote('|'.join(hide)), quote('|'.join(skin)), quote(rules)))
        names = model.animations() if kind == 'knife' else []
        if kind == 'knife':
            clips = [preferred(names, ['draw', 'draw01', 'draw1'], 'draw'),
                     preferred(names, ['idle1', 'idle01', 'idle', 'idle2'], 'idle'),
                     preferred(names, ['lookat01', 'lookat1', 'inspect'], 'lookat'),
                     preferred(names, ['light_miss1', 'midslash1', 'slash1', 'slash'], 'light_miss'),
                     preferred(names, ['heavy_miss1', 'stab_miss', 'stab'], 'heavy_miss'),
                     preferred(names, ['light_hit1', 'midslash1', 'slash1'], 'light_hit'),
                     preferred(names, ['heavy_hit1', 'stab_hit', 'stab'], 'heavy_hit')]
            if not clips[0] or not clips[1]:
                raise ResourceError('no usable draw/idle in ' + path + ': ' + repr(names))
            lines.append('\tKCAT_Clips(%di, %s);' % (row, ', '.join(map(quote, clips))))
            family = '1' if row == 1 else ('2' if row == 2 else '3')
            lines.append(f'\tKCAT_Set({row}i, 15i, "{family}");')
        records.append(dict(row=row, kind=kind, label=label, path=path, meshes=len(meshes), base=base, mask=mask, animations=names))
    lines += ['};', '']
    return '\n'.join(lines), records, excluded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vpk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    text, rows, excluded = generate(args.vpk)
    args.output.write_text(text, encoding='utf-8')
    if args.report:
        args.report.write_text(json.dumps({'rows': rows, 'excluded': excluded}, indent=2) + '\n', encoding='utf-8')
    print('Catalog metadata:', sum(x['kind'] == 'knife' for x in rows), 'Legacy knives,',
          sum(x['kind'] == 'hands' for x in rows), 'hand/arm sets,',
          sum(x['kind'] == 'layer' for x in rows), f'sleeve/watch pieces; plus CSS and automatic/none. {len(excluded)} incomplete roots excluded.')


if __name__ == '__main__':
    main()
