"""32-row dense counterpart of the existing loopback HTTP gate, not a service."""
import hashlib
import json
import re
from urllib.parse import parse_qs, urlparse
from p603http import board, PLAYER, PHASH, REP, replay


def board32(query, mode):
    result = json.loads(board(query, 'normal'))
    rows = result['rows']
    rows[7]['player'] = 'http-peer-7'
    for i in range(8,32):
        rows.append({'r': i+1, 'name': f'HTTP Row{i}', 'player': PLAYER if i == 31 else f'http-peer-{i}',
                     'ticks': 100+i, 'rate': (100+i)*1000/(1500+i*100), 'ms': 1500+i*100, 'flags': 0, 'when': 1000, 'rep': 0, 'ver': 0})
    if mode == 'reorder': rows[0], rows[1] = rows[1], rows[0]
    if mode == 'short': rows = rows[:4]
    result['rows'] = rows
    result['counts'] = {'ranked': len(rows), 'imported': len(rows)}
    return json.dumps(result,separators=(',',':')).encode()


def extend(cfg, arm, port):
    if arm not in ('native1','native2','oldplugin','oldengine'): return cfg
    marker = '-showscores\nreplay off\nwaitms 500\np603dense probe dense_closed1'
    if cfg.count(marker) != 1: raise ValueError('unique closed marker required')
    def probe(label):
        return [f'p603dense probe {label}', f'p603 probe {label}', f'p603http probe {label}', 'waitms 200']
    def click(row=0, target='watch'):
        return [f'p603dense move {target} {row}','waitms 150','p603 down','waitms 150','p603 up','waitms 700']
    def fetch(mode):
        return [f'set lobby_dir "http://127.0.0.1:{port}/{mode}"','board_fetch 0 0 ranked clean','waitms 1000']
    reset = ['-showscores','replay off','p603dense forget','set ui_native_scores_font 13',
             'scores tab online','+showscores','waitms 300','p603 pin','p603 unpin','waitms 500']
    #The /1 counterpart follows to page30, not24; return through all five
    #real Previous actions rather than labeling page24 as the first page.
    back = []
    for _ in range(31//(24 if arm.startswith('native') else 6)):
        back += click(target='previous')
    lines = [*reset, 'set rec_terms 4', *fetch('normal'), *probe('dense_online_ready'),
             'p603dense finish 31','waitms 700',*probe('dense_online_follow'),'screenshot dense_online_follow',
             *back,*probe('dense_online_page0'),
             'p603dense move watch 0','waitms 150','p603 down','waitms 150',*fetch('normal'),
             'p603 up','waitms 400',*probe('dense_online_identical'),'screenshot dense_online_identical',
             *click(),*probe('dense_online_coldwatch'),*reset,*fetch('normal'),*probe('dense_online_reorder_before'),
             'p603dense move watch 0','waitms 150','p603 down','waitms 150',*fetch('reorder'),
             'p603 up','waitms 400',*probe('dense_online_reordered'),'screenshot dense_online_reordered',
             *click(row=1),*probe('dense_online_reorderwatch'),*reset,*fetch('normal'),*probe('dense_online_short_before'),
             'p603dense move watch 0','waitms 150','p603 down','waitms 150',*fetch('short'),
             'p603 up','waitms 400',*probe('dense_online_short'),'screenshot dense_online_short',
             *click(),*probe('dense_online_shortwatch')]
    return cfg.replace(marker,'\n'.join(lines)+'\n'+marker)


def grade(rig, arm, text, values):
    errors=[]
    def need(ok, message):
        if not ok: errors.append(arm+': dense online '+message)
    fields={'state','rows','mine','epoch','revision','page'}
    http={}; cells={}
    try:
        for label,body in re.findall(r'P603 HTTP (dense_online_\w+) ([^\r\n]+)',text):
            pairs=re.findall(r'(\w+)=([^\s]+)',body)
            if label in http or len(pairs)!=len(fields) or {k for k,_ in pairs}!=fields: raise ValueError('duplicate/incomplete HTTP '+label)
            http[label]={k:int(v) for k,v in pairs}
        for label,idx,body in re.findall(r'P603 CELL (dense_online_\w+) (\d+): ([^\r\n]*)',text):
            key=label,int(idx)
            if key in cells: raise ValueError('duplicate CELL')
            cells[key]=body
    except ValueError as e: return [arm+': dense online '+str(e)]
    def get(label,field): return http.get(label,{}).get(field,-999)
    def val(kind,label,field): return values.get((kind,label),{}).get(field,-999)
    page=24 if arm.startswith('native') else 6
    labels=('ready','follow','page0','identical','reorder_before','reordered','short_before','short')
    for label in labels:
        name='dense_online_'+label; small=label=='short'; n=4 if small else 32
        firstpage=(31//page)*page if label=='follow' else 0
        need(get(name,'state')==2 and get(name,'rows')==n and get(name,'mine')==(-1 if small else 31), 'actual parser/FindMine '+label)
        need(val('STATE',name,'painted')==1 and val('STATE',name,'failed')==0 and
             val('DENSE',name,'page')==firstpage and val('DENSE',name,'count')==5+min(page,n-firstpage)*9,
             'wrong counted route '+label)
        phashes=re.findall(r'P603 PHASH '+name+r': ([^\r\n]+)',text)
        need(phashes==[PHASH],'authoritative synthetic identity '+label)
    need(val('DENSE','dense_online_follow','selected')==31,'follow did not select real own row31')
    own = 5 + (31 % page)*9
    need(cells.get(('dense_online_follow',own+1))=='0:04.600' and
         cells.get(('dense_online_follow',own+2))=='+0:03.100' and
         cells.get(('dense_online_follow',own+3))=='HTTP Row31 (you)',
         'own row31 time/ms delta/identity label did not ACT')
    for before,after in (('page0','identical'),('reorder_before','reordered'),('short_before','short')):
        b='dense_online_'+before; a='dense_online_'+after
        need(get(a,'epoch')>get(b,'epoch') and get(a,'revision')>get(b,'revision'),'replacement did not ACT '+after)
        need(val('ACTIVE',a,'watch')==0,'held old click retargeted '+after)
    need(cells.get(('dense_online_page0',8))=='HTTP Row0' and
         cells.get(('dense_online_reordered',8))=='HTTP Row1' and
         cells.get(('dense_online_reordered',17))=='HTTP Row0','actual reordered row labels')
    need(cells.get(('dense_online_short',8))=='HTTP Row0','short page wrong current key')
    for label in ('coldwatch','reorderwatch','shortwatch'):
        name='dense_online_'+label
        need(val('ACTIVE',name,'watch')==1 and val('ACTIVE',name,'samples')==20,'fresh replay did not ACT '+label)
        paths=re.findall(r'P603 DENSEPATH '+name+r' ([^\r\n]+)',text)
        need(len(paths)==1 and re.fullmatch(r'data/online/[^\s]*'+str(REP)+r'\.rec',paths[0]) is not None,'wrong replay path '+label)
    try:
        exchanges=[json.loads(l) for l in (rig/arm/'http.jsonl').read_text().splitlines()]
        for mode,minimum in (('normal',4),('reorder',1),('short',1)):
            rows=[r for r in exchanges if r.get('path','').startswith('/'+mode+'/api/board?')]
            need(len(rows)>=minimum,'missing actual GET '+mode)
            for record in rows:
                query={k:v[0] for k,v in parse_qs(urlparse(record['path']).query).items()}
                payload=board32(query,mode)
                need(record.get('method')=='GET' and record.get('code')==200 and record.get('bytes')==len(payload) and
                     record.get('sha256')==hashlib.sha256(payload).hexdigest(),'wrong response body '+mode)
        downloads=[r for r in exchanges if r.get('path','').endswith('/api/replay/'+str(REP))]
        payload=replay()
        need(len(downloads)==1 and downloads[0].get('code')==200 and downloads[0].get('bytes')==len(payload) and
             downloads[0].get('sha256')==hashlib.sha256(payload).hexdigest(),'cold replay bytes not delivered exactly once')
    except (OSError,ValueError,KeyError) as e: need(False,'exchange evidence '+str(e))
    for shot in ('follow','identical','reordered','short'):
        need(len(list((rig/arm/'ftesurf/screenshots').glob('dense_online_'+shot+'.*')))==1,'missing screenshot '+shot)
    return errors
