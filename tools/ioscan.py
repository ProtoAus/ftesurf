# IO census for the trigger mirror (patch 338/339): scans BSP entity lumps
# and reports which outputs gate movement-class triggers, grouped by source
# class -- the measurement that decides whether extending the client mirror
# (relays, timers, delayed outputs) has an actionable set.  Usage:
#   python tools/ioscan.py maps...   (or edit SCANLIST)
# 2026-09 result over the 82-map lobby roster: ZERO zero-delay relay/timer
# gates; all relay gating is delayed 0.05-200 s (song/hint/ending sequences;
# the only MOVE-class rows are surf_lt_unicorn's ending viewholder swap).
import struct, lzma, re, sys, os
from collections import Counter

def ents(path):
    d = open(path, 'rb').read()
    o, l, v, f = struct.unpack('<iiii', d[8:8+16])
    raw = d[o:o+l]
    if raw[:4] == b'LZMA':
        actual, lsize = struct.unpack('<II', raw[4:12])
        props = raw[12:17]
        flt = [{"id": lzma.FILTER_LZMA1, "lc": props[0] % 9, "lp": (props[0]//9) % 5,
                "pb": props[0]//45, "dict_size": struct.unpack('<I', props[1:5])[0]}]
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=flt)
        try: out = dec.decompress(raw[17:17+lsize])
        except lzma.LZMAError: out = b''
    else:
        out = raw
    es = []
    for block in re.findall(rb'\{(.*?)\}', out, re.S):
        kv = re.findall(rb'"([^"]+)"\s*"([^"]*)"', block)
        if kv: es.append([(k.decode('latin1'), v.decode('latin1')) for k, v in kv])
    return es

def get(e, k, d=''):
    for kk, vv in e:
        if kk.lower() == k.lower(): return vv
    return d

CLS = ('trigger_teleport','trigger_momentum_teleport','trigger_push',
       'trigger_setspeed','trigger_momentum_setspeed')
EVCLS = ('trigger_multiple','trigger_once')
gain = Counter()
total = 0
for p in sys.argv[1:]:
    if not os.path.exists(p):
        print('missing', p); continue
    total += 1
    es = ents(p)
    tnames = {get(e,'targetname'): get(e,'classname') for e in es if get(e,'targetname')}
    for e in es:
        cn = get(e,'classname')
        for k,v in e:
            if not k.startswith('On'): continue
            sep = chr(27) if chr(27) in v else ','
            parts=[x.strip() for x in v.split(sep)]
            if len(parts)<2: continue
            tgt,inp = parts[0], parts[1].lower()
            delay = float(parts[3]) if len(parts)>3 and parts[3] else 0
            tcls = tnames.get(tgt,'')
            if inp not in ('enable','disable','toggle','kill'): continue
            if tcls not in CLS and tcls not in EVCLS: continue
            kind = 'MOVE' if tcls in CLS else 'EVENT'
            mirror = ((cn in CLS+EVCLS and k in ('OnStartTouch','OnEndTouch')) or
                      (cn=='logic_auto' and k=='OnMapSpawn'))
            gain[f"{'MIRRORED' if mirror and delay==0 else cn}({k}) d={delay:g} {kind}"] += 1
print('maps scanned:', total)
for k,c in gain.most_common(30): print(f'  {c:4d}  {k}')
