"""Library census: entity classes, outputs and inputs the maps use that the game code does not handle.

    python -B tools/census/entgap.py --qc . --out <dir> [--engine <engine tree>]

Static, so it is a list of CANDIDATES to confirm with the server's own `ent_census`:
- a class counts as handled when SSQC has a function of that name (the engine's spawn dispatch), or the
  client names it in a string literal compared with a classname / key (cl_*.qc lump walks), or the
  catch-all lists it as walk-through brushwork;
- an input counts as handled when any server file compares a folded input with that name;
- an output counts as handled when SV_IOOutputKnown (or a class helper) names it.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--qc', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--engine', type=Path, default=Path('C:/msys64/home/Lex/fteqw'), help='engine tree (plugins/hl2 literals)')
ap.add_argument('--lib', type=Path,
                default=Path('C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps'))
a = ap.parse_args()
sys.path.insert(0, str(a.qc / 'tools/census'))
import bsplib  # noqa: E402

src = a.qc / 'src'
sv = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in sorted((src / 'server').glob('*.qc')))
sv += ''.join(p.read_text(encoding='utf-8', errors='replace') for p in sorted((src / 'shared').glob('*.qc')))
cl = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in sorted((src / 'client').glob('*.qc')))

spawnfuncs = set(re.findall(r'^void\(\)\s+([a-z][a-z0-9_]*)\s*=', sv, re.M))
# client: any lowercase class-like literal it compares (cn == "x", classname == "x", strcmp(x, "y"))
cl_lits = set(re.findall(r'[!=]=\s*"([a-z][a-z0-9_]*)"', cl)) | set(re.findall(r'strcmp\(\w+,\s*"([a-z][a-z0-9_]*)"\)', cl))
plug = ''.join(q.read_text(encoding='utf-8', errors='replace') for q in (a.engine / 'plugins/hl2').glob('*.c'))
plug_lits = set(re.findall(r'"([a-z]+_[a-z0-9_]+)"', plug))
sv_lits = set(re.findall(r'[!=]=\s*"([a-z][a-z0-9_]*)"', sv)) | set(re.findall(r'strcmp\([\w.]+,\s*"([a-z][a-z0-9_]*)"\)', sv))
walk = set(re.findall(r'"(func_[a-z_]+|env_[a-z_]+|zone_timer_[a-z_]*)"', sv[sv.find('SV_OnEntityNoSpawnFunction'):][:20000]))
inputs_ok = set(re.findall(r'\bin\s*==\s*"([a-z0-9_]+)"', sv)) | set(re.findall(r'strcmp\(in,\s*"([a-z0-9_]+)"\)', sv))
okb = sv.find('float(string lk) SV_IOOutputKnown')
outputs_ok = set(re.findall(r'"(on[a-z0-9_]+)"', sv[okb:okb + 12000])) | set(re.findall(r'lk\s*==\s*"(on[a-z0-9_]+)"', sv))

cls_ents = collections.Counter()
cls_maps = collections.defaultdict(set)
cls_brush = collections.Counter()
out_maps = collections.defaultdict(set)
out_n = collections.Counter()
inp_maps = collections.defaultdict(set)
inp_n = collections.Counter()
inp_cls = collections.defaultdict(collections.Counter)
nmaps = 0
bad = []
for p in sorted(a.lib.glob('*.bsp')):
    try:
        ents, _ = bsplib.read_pairs(p)
    except Exception as e:  # a map the reader cannot open is reported, not skipped silently
        bad.append((p.stem, str(e)[:80]))
        continue
    if not ents:
        bad.append((p.stem, 'no entity lump'))
        continue
    nmaps += 1
    names = {}
    for kv in ents:
        d = dict(kv)
        if d.get('targetname'):
            names.setdefault(d['targetname'].lower(), d.get('classname', '').lower())
    for kv in ents:
        d = dict(kv)
        cn = d.get('classname', '').lower()
        cls_ents[cn] += 1
        cls_maps[cn].add(p.stem)
        if d.get('model', '').startswith('*'):
            cls_brush[cn] += 1
        for k, v in kv:
            if not k.startswith('on'):
                continue
            parts = re.split('[,\x1b]', v)
            if len(parts) < 2:
                continue
            out_maps[k].add(p.stem)
            out_n[k] += 1
            inp = parts[1].strip().lower()
            if not inp:
                continue
            inp_maps[inp].add(p.stem)
            inp_n[inp] += 1
            tgt = parts[0].strip().lower()
            inp_cls[inp][names.get(tgt, '!' + tgt if tgt.startswith('!') else '?')] += 1


def handled_cls(cn):
    if cn in spawnfuncs:
        return 'server'
    if cn in cl_lits:
        return 'client'
    if cn in walk or cn.startswith('zone_timer_'):
        return 'walk-through'
    if cn in plug_lits:
        return 'plugin'
    return ''


rows_c = [{'class': c, 'maps': len(cls_maps[c]), 'ents': cls_ents[c], 'brush': cls_brush[c],
           'sv_literal': c in sv_lits, 'examples': sorted(cls_maps[c])[:4]}
          for c in cls_ents if c and not handled_cls(c)]
rows_c.sort(key=lambda r: (-r['maps'], -r['ents']))
case_ok = {'oncase%02d' % i for i in range(1, 17)}
rows_o = [{'output': o, 'maps': len(out_maps[o]), 'n': out_n[o]} for o in out_n if o not in outputs_ok and o not in case_ok]
rows_o.sort(key=lambda r: (-r['maps'], -r['n']))
rows_i = [{'input': i, 'maps': len(inp_maps[i]), 'n': inp_n[i], 'targets': inp_cls[i].most_common(4),
           'examples': sorted(inp_maps[i])[:4]} for i in inp_n if i not in inputs_ok]
rows_i.sort(key=lambda r: (-r['maps'], -r['n']))
a.out.mkdir(parents=True, exist_ok=True)
rep = {'maps': nmaps, 'unreadable': bad, 'spawnfuncs': len(spawnfuncs), 'inputs_handled': len(inputs_ok),
       'outputs_handled': len(outputs_ok), 'classes': rows_c, 'outputs': rows_o, 'inputs': rows_i}
(a.out / 'entgap.json').write_text(json.dumps(rep, indent=1))
print(f'{nmaps} maps read, {len(bad)} unreadable; {len(spawnfuncs)} spawn functions, {len(inputs_ok)} inputs, '
      f'{len(outputs_ok)} outputs handled')
print('\nCLASSES with no handler (maps, ents, brush):')
for r in rows_c[:45]:
    print(f"  {r['maps']:5d} {r['ents']:6d} {r['brush']:5d}  {r['class']}{'  (sv literal)' if r['sv_literal'] else ''}")
print('\nOUTPUTS nothing fires (maps, n):')
for r in rows_o[:25]:
    print(f"  {r['maps']:5d} {r['n']:6d}  {r['output']}")
print('\nINPUTS not dispatched (maps, n, top targets):')
for r in rows_i[:45]:
    print(f"  {r['maps']:5d} {r['n']:6d}  {r['input']:28s} {r['targets'][:3]}")
