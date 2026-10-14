#!/usr/bin/env python3
"""Real headless Chrome style/top-up controls against an owned fixture DB."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
(async()=>{
 const pause=()=>new Promise(r=>setTimeout(r,50));
 const wait=async(test)=>{for(let i=0;i<160;i++){if(test())return;await pause()}throw Error('wait expired')};
 const assert=(x,s)=>{if(!x)throw Error(s)};
 const click=(id,s)=>{let b=[...document.querySelectorAll('#'+id+' button')].find(b=>b.textContent.startsWith(s));assert(b,'missing '+s);b.click()};
 try {
  await wait(()=>document.querySelector('#rows').textContent.includes('ForwardFixture'));
  assert(!document.querySelector('#rows').textContent.includes('SidewaysFixture'),'style leaked into Forward');
  click('styles','Sideways (SW)');
  await wait(()=>document.querySelector('#rows').textContent.includes('SidewaysFixture'));
  assert(!document.querySelector('#rows').textContent.includes('ForwardFixture'),'Forward leaked into SW');
  click('ksftopup','Fetch +100');
  await wait(()=>document.querySelector('#ksftopup').textContent.includes('Queued for'));
  click('styles','Backwards (BW)');
  await wait(()=>document.querySelector('#rows').textContent.includes('BackwardFixture'));
  click('srcs','FTESurf');
  await wait(()=>location.hash.includes('s=clean') && location.hash.includes('tier=ranked') &&
    [...document.querySelectorAll('#srcs button')].some(b=>b.textContent.startsWith('FTESurf') && b.getAttribute('aria-pressed')==='true'));
  click('srcs','KSF');
  await wait(()=>document.querySelector('#rows').textContent.includes('ForwardFixture'));
  click('styles','Half-Sideways (HSW)');
  await wait(()=>document.querySelector('#rows').textContent.includes('HalfSideFixture'));
  click('ksftopup','Fetch +100');
  await wait(()=>document.querySelector('#ksftopup').textContent.includes('Queued for'));
  let p=document.createElement('pre');p.id='browser-results';p.textContent='BROWSER PASS: Forward/SW/HSW/BW isolated; source reset; real POST queue on SW and HSW';document.body.prepend(p);document.title='BROWSER PASS';
 } catch(e) {let p=document.createElement('pre');p.id='browser-results';p.textContent='BROWSER FAIL '+e.stack;document.body.prepend(p);document.title='BROWSER FAIL';}
})();
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--chrome',type=Path,default=Path('C:/Program Files/Google/Chrome/Application/chrome.exe'))
    a = ap.parse_args(); out = a.output_dir.resolve()
    if not any((p/'OWNER.md').is_file() for p in (out,*out.parents)):
        raise ValueError('output-dir requires an owned task root')
    out.mkdir(exist_ok=False,parents=True)
    os.environ.update(SURFD_HOME=str(out),SURFD_DB=str(out/'fixture.db'),SURFD_BOARD_URL='',
                      SURFD_ENV=str(out/'no-secrets.env'),SURFD_ADMIN_HASH='',SURFD_RANKED_LINKED='0',
                      SURFD_MAPS=str(out/'maps'),SURFD_ZONES=str(out/'zones'))
    sys.path.insert(0,str(ROOT/'surfd'))
    import surfd as S
    from werkzeug.serving import make_server
    from flask import request, Response
    db=S.connect()
    with db:
        for i,(style,name,ms) in enumerate([('clean','ForwardFixture',1500),('sw','SidewaysFixture',500),
                                             ('hsw','HalfSideFixture',600),('bw','BackwardFixture',700)]):
            db.execute("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,"
                       "node,runid,submitted,replay_id) VALUES('surf_topup',0,0,'ksf',?,?,?,?,100,?,0,'ksf','',1,0)",
                       (style,str(76561197960265729+i),name,ms//10,ms))
    db.close(); hits=[]
    @S.app.get('/board/fixture.js')
    def fixture(): return Response(SCRIPT,content_type='application/javascript')
    @S.app.after_request
    def inject(resp):
        hits.append([request.method,request.path,dict(request.args),resp.status_code])
        if request.path=='/board/':
            resp.set_data(resp.get_data(as_text=True).replace('</body>','<script src="fixture.js"></script></body>'))
        return resp
    server=make_server('127.0.0.1',0,S.app,threaded=True)
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:
        driver=out/'driver.js'
        driver.write_text(r'''
const fs=require('fs'), path=require('path');
(async()=>{
 const ws=new WebSocket(process.argv[2]), out=process.argv[3];
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 let seq=0, pending=new Map();
 ws.onmessage=e=>{let m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p[1](m.error):p[0](m.result)}};
 const call=(method,params={})=>new Promise((r,j)=>{let id=++seq;pending.set(id,[r,j]);ws.send(JSON.stringify({id,method,params}))});
 const evaluate=async expression=>(await call('Runtime.evaluate',{expression,returnByValue:true})).result.value;
 try {
  let answer='NO RESULTS';
  for(let i=0;i<250;i++){
   let x=await evaluate("document.querySelector('#browser-results')?.textContent");
   if(x){answer=x;break} await new Promise(r=>setTimeout(r,100));
  }
  fs.writeFileSync(path.join(out,'dom.html'),await evaluate('document.documentElement.outerHTML'));
  let shot=await call('Page.captureScreenshot',{format:'png'});
  fs.writeFileSync(path.join(out,'board.png'),Buffer.from(shot.data,'base64'));
  console.log(answer);if(!answer.startsWith('BROWSER PASS'))process.exitCode=1;
 } finally {await call('Browser.close').catch(()=>{});ws.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
''')
        with (out/'chrome.log').open('wb') as log:
            chrome=subprocess.Popen([str(a.chrome),'--headless','--disable-gpu','--no-first-run',
                '--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+str(out/'profile'),
                '--window-size=1440,1100',f'http://127.0.0.1:{server.server_port}/board/#m=surf_topup&t=0&l=0&s=clean&tier=ksf'],
                stdout=log,stderr=log)
            try:
                active=out/'profile/DevToolsActivePort'
                for _ in range(100):
                    if active.exists(): break
                    if chrome.poll() is not None: raise RuntimeError('Chrome exited')
                    time.sleep(0.1)
                port=active.read_text().splitlines()[0]
                pages=json.load(urllib.request.urlopen('http://127.0.0.1:'+port+'/json'))
                page=next(p for p in pages if p['type']=='page')
                result=subprocess.run(['node',str(driver),page['webSocketDebuggerUrl'],str(out)],
                                      capture_output=True,text=True,timeout=40)
                (out/'driver.log').write_text(result.stdout+result.stderr)
                print(result.stdout.strip()); assert result.returncode==0,result.stderr
                chrome.wait(timeout=10)
            finally:
                if chrome.poll() is None:
                    chrome.terminate();chrome.wait(timeout=10)
        posts={q['style'] for method,path,q,code in hits if method=='POST' and code==202}
        assert posts=={'sw','hsw'},posts
    finally:
        server.shutdown();t.join();server.server_close()
        (out/'http.json').write_text(json.dumps(hits,indent=2))


if __name__=='__main__': main()
