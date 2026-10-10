#!/usr/bin/env python3
"""Read-only dense-reader positive/counterfactual controls over an acted rig."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch
from PIL import Image
from p603dense import grade_dense, captures


def run(rig):
    report=json.loads((rig/'report.json').read_text())
    required={'native1','native2','oldplugin','oldengine','legacy','absent'}
    if set(report['arms']) != required: raise RuntimeError('complete six-arm rig required')
    paths=[rig/'report.json']+list(rig.rglob('scores*.log'))+list(rig.rglob('http.jsonl'))+list(rig.rglob('dense*.png'))
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    original_read=Path.read_text; original_glob=Path.glob; original_image=Image.open
    logs={arm:next((rig/arm/'ftesurf/logs').glob('scores*.log')) for arm in required}
    text={arm:logs[arm].read_text() for arm in required}
    checks=0; failures=[]
    def check(name, condition):
        nonlocal checks
        checks+=1
        if not condition: failures.append(name); print('FAIL',name)
    check('positive complete acting rig',not grade_dense(rig,report))
    for name,key,value in [('disabled-density','dense',False),('no-online-plan','dense_http',False),
                           ('wrong-fixture-hash','csprogs_sha256','0'*64),('no-provider-hash','plugin_sha256',None),
                           ('renderer-fallback-is-not-parity','renderer','vk'),
                           ('missing-arm','planned_arms',['native1']),('no-arms','arms',{})]:
        changed=deepcopy(report); changed[key]=value
        check(name,bool(grade_dense(rig,changed)))
    for key,value in [('returncode',1),('returncode',True),('port',27698),('server_sha256',None),
                      ('csprogs_sha256','0'*64),('plugin_sha256','0'*64)]:
        changed=deepcopy(report);changed['arms']['native1'][key]=value
        check('provenance-'+key+'-'+str(value),bool(grade_dense(rig,changed)))
    for arm in ('oldplugin','absent'):
        changed=deepcopy(report);changed['arms'][arm]['plugin_sha256']=report['plugin_sha256']
        check(arm+' wrong provider',bool(grade_dense(rig,changed)))
    changes=[
        ('STATE','dense_page0','painted',0),('STATE','dense_page0','h',0),('STATE','dense_page0','failed',1),
        ('DENSE','dense_page0','limit',64),('DENSE','dense_page0','pagesize',25),('DENSE','dense_page0','rows',25),
        ('DENSE','dense_page0','count',257),('DENSERANK','dense_page0','first',2),('DENSERANK','dense_page0','last',25),
        ('ACTIVE','dense_passive','watch',1),('OWNER','dense_page0','pin',0),('LINE','dense_line','ready',0),
        ('LINE','dense_line','samples',0),('ACTIVE','dense_lineoff','lines',1),
        ('ACTIVE','dense_watch8','watch',0),('ACTIVE','dense_watch8','samples',19),
        ('DENSE','dense_next','page',6),('DENSE','dense_follow','selected',30),('ACTIVE','dense_stale','watch',1),
        ('STATE','dense_quiet_end','revision',99),('ACTIVE','dense_tailwatch','watch',0),
        ('ACTIVE','dense_fontstale','watch',1),('STATE','dense_font20','painted',0),
        ('STATE','dense_closed2','h',99),('ACTIVE','dense_closed2','watch',1),
        ('DENSE','dense_online_follow','selected',7),('DENSE','dense_online_short','count',77),
        ('ACTIVE','dense_online_identical','watch',1),('ACTIVE','dense_online_reordered','watch',1),
        ('ACTIVE','dense_online_shortwatch','samples',0)]
    def modified_log(name, changed):
        def read(path,*args,**kwargs): return changed if path==logs['native1'] else original_read(path,*args,**kwargs)
        with patch.object(Path,'read_text',read): check(name,bool(grade_dense(rig,report)))
    for kind,label,field,value in changes:
        pattern=r'(P603 '+kind+' '+label+r' [^\r\n]*?\b'+field+r'=)[^\s]+'
        changed,n=re.subn(pattern,lambda m:m[1]+str(value),text['native1'])
        if n!=1: raise RuntimeError('unique mutation required '+label+'/'+field)
        modified_log(kind+'/'+label+'/'+field,changed)
    for name,old,new in [
        ('wrong-watch-identity','0000108_p6038_pb.rec','0000109_p6039_pb.rec'),
        ('wrong-replay-identity','996041.rec','996042.rec'),('missing-completion','P603 FINISHED','P603 NOTFINISHED'),
        ('nonfinite-count','count=221','count=nan'),('fractional-count','count=221','count=221.5'),
        ('runtime-error','P603 FINISHED','QC runtime error\nP603 FINISHED'),
        ('quiet-resource-leak','live=0','live=1'),('wrong-phash', 'P603 PHASH dense_online_ready:', 'P603 PHASH dense_online_ready: wrong'),
        ('wrong-own-row','rows=32 mine=31','rows=32 mine=7')]:
        if old not in text['native1']: raise RuntimeError('mutation did not act '+name)
        modified_log(name,text['native1'].replace(old,new))
    line=re.search(r'P603 DENSE dense_page0 [^\r\n]+',text['native1'])[0]
    modified_log('duplicate-counted-witness',text['native1']+'\n'+line+'\n')
    modified_log('unknown-counted-field',text['native1'].replace(line,line+' borrowed=1'))
    modified_log('missing-counted-witness',text['native1'].replace(line,''))
    for field in ('epoch','revision'):
        b=re.search(r'P603 HTTP dense_online_page0 [^\r\n]+',text['native1'])[0]
        old=int(re.search(field+r'=(\d+)',b)[1])
        pattern=r'(P603 HTTP dense_online_identical [^\r\n]*?\b'+field+r'=)\d+'
        changed,n=re.subn(pattern,lambda m:m[1]+str(old),text['native1'])
        if n!=1: raise RuntimeError('replacement mutation did not act')
        modified_log('identical-response-stale-'+field,changed)
    exchanges=rig/'native1/http.jsonl'
    records=[json.loads(l) for l in exchanges.read_text().splitlines()]
    for key,value in [('sha256','0'*64),('bytes',0),('code',404),('method','POST')]:
        changed=deepcopy(records); item=next(r for r in changed if '/normal/api/board?' in r['path']);item[key]=value
        body='\n'.join(json.dumps(r) for r in changed)+'\n'
        def read(path,*args,**kwargs): return body if path==exchanges else original_read(path,*args,**kwargs)
        with patch.object(Path,'read_text',read): check('actual-response-'+key,bool(grade_dense(rig,report)))
    target=rig/'native1/ftesurf/screenshots/dense_page0.png'
    def glob(path,pattern): return iter(p for p in original_glob(path,pattern) if p!=target)
    with patch.object(Path,'glob',glob): check('missing-screenshot',bool(grade_dense(rig,report)))
    def image(path,*args,**kwargs):
        if Path(path)==target: return Image.new('RGB',(1920,1080),(0,0,0))
        return original_image(path,*args,**kwargs)
    with patch.object(Image,'open',image): check('blank-rank-ink',bool(grade_dense(rig,report)))
    #A single changed glyph pixel must falsify the physical-scale ink equality,
    #even with plenty of rank groups and all acting log witnesses still present.
    def image(path,*args,**kwargs):
        im=original_image(path,*args,**kwargs)
        if Path(path)==target:
            result=im.convert('RGB');im.close();result.putpixel((568,279),(255,255,255));return result
        return im
    with patch.object(Image,'open',image): check('wrong-physical-ink',bool(grade_dense(rig,report)))
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    check('reader controls left source evidence byte-identical',before==after)
    check('positive after counterfactuals',not grade_dense(rig,report))
    print(f'P603 DENSE READER checks={checks} failed={len(failures)}')
    return bool(failures)


if __name__=='__main__':
    raise SystemExit(run(Path(sys.argv[1]).resolve()))
