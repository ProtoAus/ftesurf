#!/usr/bin/env python3
"""Native MQC waiting-room parser/control tests in an owned headless profile.

Captures the transport and final connect command: NO real service, account proof,
server connection, visual/font-quality claim, production profile or deployment.
The separate two-native-client playtest exercises real signatures and handoff.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from tournament_playtest import ORIGINS, owned_root

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(value):
    return json.dumps(json.dumps(value, separators=(',', ':'), ensure_ascii=False), ensure_ascii=False)


def fixture():
    ident, host, peer = 'a'*32, '11111111', '22222222'
    players = [dict(who=w, name=n, role='player', accepted=1, menu_ready=1, menu_online=1)
               for w, n in ((host, 'Host'), (peer, 'Partner'))]
    party = dict(id=ident, host=host, phase='lobby', revision=7, capacity=3,
                 round_seconds=300, players=players,
                 maps=[dict(map='surf_fixture_'+str(i), status='pool', by='') for i in range(6)], turn=None)
    launch = dict(id=ident, epoch=ident, addr='127.0.0.1:27510', map='surf_fixture_0')
    statements = []

    def check(expression, label):
        statements.append('TQ_Check('+expression+','+json.dumps(label)+');')

    def snapshot(value):
        return 'TQ_Snapshot('+literal(value)+')'

    check(snapshot(party), 'valid capacity-three actual-two snapshot')
    check('mt_np==2 && mt_nm==6 && mt_capacity==3 && mt_revision==7', 'roster is not advertised capacity')
    check('MT_Player(0,1)=="Host"', 'adopted name')
    bad = []
    for key, value in (('id', 'bad'), ('phase', 'mystery'), ('host', '33333333'),
                       ('players', {}), ('maps', {}), ('players', [])):
        p = copy.deepcopy(party); p[key] = value; bad.append((key+' '+str(value), p))
    for name in ('surf_bad;quit', '../escape', 'surf_'+'x'*102):
        p = copy.deepcopy(party); p['maps'][0]['map'] = name; bad.append(('unsafe map', p))
    p = copy.deepcopy(party); p['players'][0]['role'] = 'admin'; bad.append(('invalid role', p))
    p = copy.deepcopy(party); p['players'] *= 37; bad.append(('roster over 72', p))
    p = copy.deepcopy(party); p['maps'] *= 5; bad.append(('maps over 24', p))
    for label, p in bad:
        check('!'+snapshot(p), label+' refused')
    check('mt_id=="'+ident+'" && mt_np==2 && mt_nm==6 && mt_revision==7', 'invalid snapshot retains last valid state')
    check('MT_Text("aé漢😀z",2)=="a"', 'byte limit before two-byte character')
    check('MT_Text("aé漢😀z",5)=="aé"', 'byte limit before three-byte character')
    check('MT_Text("aé漢😀z",9)=="aé漢"', 'byte limit before four-byte character')
    check('MT_Text("x^1",64)=="x^^1"', 'persona colour markup stays literal')
    statements += ['mt_fresh=1; MT_Fail("fixture stale revision");']
    check('mt_fresh==0 && mt_req==0', 'refusal disables stale controls until resync')

    statements += ['MT_Set("'+host+'",mt_me); cvar_set("lobby_hosts","127.0.0.1"); ms_consent=3;',
                   'mt_directory=buf_create(); mt_nd=1;',
                   'bufstr_set(mt_directory,0,"'+ident+'"); bufstr_set(mt_directory,5,"7");',
                   'tq_connect=""; tq_connects=0; tq_calls=0; mt_req=mt_wire=0;', 'MT_Connect(0);']
    check('tq_calls==1 && mt_req>0 && mt_op=="join" && tq_connects==0', 'joining waiting room requests proof but never connects')
    statements += ['MT_Action("leave",mt_id,"-","-",0);']
    check('tq_calls==1', 'one in-flight wire prevents overlap')
    statements += ['mt_req=mt_wire=0; MT_Action("ready",mt_id,"-","-",(MT_Player(0,1)!=MT_Player(1,1)));']
    check('strstrofs(mt_payload,"&value=1",0)>=0', 'native nonunit string truth encoded canonically')
    statements += ['mt_req=mt_wire=0;']
    for key, value in (('id', 'b'*32), ('epoch', 'g'*32), ('addr', 'evil.invalid:27510'),
                       ('addr', '127.0.0.1:70000'), ('map', 'surf_bad;quit')):
        p = copy.deepcopy(launch); p[key] = value
        statements += ['MT_Set("",mt_launched); tq_connects=0; TQ_Launch('+literal(p)+');']
        check('tq_connects==0', 'unsafe/unbound '+key+' cannot connect')
    statements += ['MT_Set("33333333",mt_me); TQ_Launch('+literal(launch)+');']
    check('tq_connects==0', 'nonmember cannot use a launch')
    statements += ['MT_Set("'+host+'",mt_me); MT_Set("",mt_launched); TQ_Launch('+literal(launch)+');']
    check('tq_connects==1 && tq_connect=="connect 127.0.0.1:27510\\n"', 'member final launch emits one bounded connect')
    statements += ['TQ_Launch('+literal(launch)+');']
    check('tq_connects==1', 'same launch epoch is not emitted twice')
    reply = dict(ok=1, me=host, party=party, launch=launch)
    statements += ['MT_Set("",mt_launched); tq_connects=0; mt_wire=mt_req=91; mt_phase_wire=2; ms_consent=0;',
                   'MT_Reply(91,0,'+literal(reply)+');']
    check('tq_connects==0 && mt_fresh==0', 'consent revoked before callback refuses launch')
    statements += ['ms_consent=3; mt_wire=92; mt_req=0;', 'MT_Reply(92,0,'+literal(reply)+');']
    check('tq_connects==0 && mt_wire==0', 'late timed-out callback only drains its wire')
    # Exercise actual button conditionals with drawing sinks. This catches QC's
    # unusual ?: precedence (the renderer otherwise receives float -> red vector).
    statements += ['sui_begin(800,600);', 'MT_Button("probe-regular",\'20 20 0\',\'140 36 0\',"Native");']
    check('tq_fill==SUI_THEME_CHIP && tq_ink==SUI_THEME_TEXT', 'cold button uses theme vectors, not logical floats')
    statements += ['MT_Button("probe-selected",\'20 80 0\',\'140 36 0\',"Native",FALSE,TRUE,TRUE);']
    check('tq_fill==SUI_THEME_SELECTED && tq_ink==SUI_THEME_ACCENT', 'selected button uses native accent vector')
    statements += ['MT_Button("probe-primary",\'20 140 0\',\'140 36 0\',"Native",TRUE);']
    check('tq_fill==SUI_THEME_GOOD_BG && tq_ink==SUI_THEME_GOOD', 'cold primary uses theme vectors')
    return r'''
float tq_checks,tq_failed,tq_calls,tq_connects;
string tq_connect;
vector tq_fill,tq_ink;
float(string url,float req,string mime="",string form="") TQ_URI = { tq_calls+=1; return TRUE; };
void(string cmd) TQ_Connect = { tq_connect=cmd; tq_connects+=1; };
void(vector pos,vector size,float radius,vector fill,vector edge,float alpha) TQ_Box = { tq_fill=fill; };
void(vector pos,string text,float want,vector colour,float alpha) TQ_Ink = { tq_ink=colour; };
void(float good,string label) TQ_Check = {
    tq_checks+=1;
    if (!good) { tq_failed+=1; print(strcat("TQ_MENU_FAIL ",label,"\n")); }
};
float(string body) TQ_Snapshot = {
    local int root;
    local float good;
    root=json_parse(body); good=MT_Snapshot(root); json_free(root); return good;
};
void(string body) TQ_Launch = {
    local int root;
    root=json_parse(body); MT_Launch(root); json_free(root);
};
void() TQ_MenuFixture = {
'''+'\n'.join(statements)+r'''
    if (!tq_failed) print(sprintf("TQ_MENU_RESULT PASS %g/%g\n",tq_checks,tq_checks));
    else print(sprintf("TQ_MENU_RESULT FAIL %g/%g\n",tq_failed,tq_checks));
    localcmd("quit\n");
};
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--compiler', type=Path, required=True)
    ap.add_argument('--client', type=Path, required=True)
    a = ap.parse_args()
    work = owned_root(a.work_root)
    rig = Path(tempfile.mkdtemp(prefix='menu-v2-', dir=work))
    (rig/'OWNER.md').write_text('Owned headless tournament-menu parser fixture. Transport/render/connect sinks.\n')
    src = rig/'src'; shutil.copytree(ROOT/'src', src)
    hashes = {}
    for path in src.rglob('*.qc'):
        hashes[str(path.relative_to(src))] = sha(path)
        text = path.read_text()
        for origin in ORIGINS:
            text = text.replace(origin, 'http://127.0.0.1:1')
        path.write_text(text)
    browser = src/'menu/m_tournament.qc'
    text = browser.read_text()
    marker = 'localcmd(sprintf("connect %s\\n", addr));'
    if text.count(marker) != 1:
        raise RuntimeError('final connect fixture hook must be unique')
    text = text.replace(marker, 'TQ_Connect(sprintf("connect %s\\n", addr));')
    for original, sink in (('uri_get(', 'TQ_URI('), ('sui_style_box(', 'TQ_Box('), ('sui_native_text(', 'TQ_Ink(')):
        text = text.replace(original, sink)
    browser.write_text('float(string url,float req,string mime="",string form="") TQ_URI;\n'
                       'void(string cmd) TQ_Connect;\n'
                       'void(vector pos,vector size,float radius,vector fill,vector edge,float alpha) TQ_Box;\n'
                       'void(vector pos,string text,float want,vector colour,float alpha) TQ_Ink;\n'+text)
    mainfile = src/'menu/m_main.qc'; text = mainfile.read_text()
    if text.count('Lob_Init();') != 1:
        raise RuntimeError('menu init fixture hook must be unique')
    mainfile.write_text('void() TQ_MenuFixture;\n'+text.replace('Lob_Init();', 'Lob_Init();\n\tTQ_MenuFixture();'))
    (src/'fixture.qc').write_text(fixture())
    manifest = src/'m_progs.src'; manifest.write_text(manifest.read_text()+'\nfixture.qc\n')
    game = rig/'ftesurf'; game.mkdir()
    (rig/'default.fmf').write_text('FTEManifestVer 1\nGAME wos\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\n')
    (game/'default.cfg').write_text('set utf8_enable 0\nset menu_font_flags 0\n')
    with (rig/'compile.log').open('w') as log:
        result = subprocess.run([str(a.compiler.resolve()),'-O2','-Wall','-max_strings','4194304','-srcfile','m_progs.src'],
                                cwd=src,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    if result.returncode or not (game/'menu.dat').is_file():
        raise RuntimeError('native menu fixture compile failed: '+str(rig/'compile.log'))
    command = [str(a.client.resolve()),'-basedir',str(rig),'-game','ftesurf','-nohome','-nostdout',
               '+set','renderer','headless','+set','sv_public','0','+set','cl_nofake','1','+set','utf8_enable','0']
    try:
        result = subprocess.run(command,cwd=rig,env={**os.environ,'XDG_DATA_HOME':str(rig/'xdg')},
                                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=40)
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or b''
        (rig/'runtime.log').write_text(output.decode(errors='replace') if isinstance(output,bytes) else output)
        (rig/'result.json').write_text(json.dumps(dict(ok=False,failure='native timeout',rig=str(rig)))+'\n')
        raise RuntimeError('native menu fixture timeout; logs retained: '+str(rig)) from exc
    (rig/'runtime.log').write_text(result.stdout)
    passed = result.returncode==0 and 'TQ_MENU_RESULT PASS ' in result.stdout and 'TQ_MENU_FAIL ' not in result.stdout
    report = dict(ok=passed, source_sha256=hashes, compiler_sha256=sha(a.compiler), client_sha256=sha(a.client),
                  scope=__doc__, rig=str(rig))
    (rig/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(rig)
    for line in result.stdout.splitlines():
        if 'TQ_MENU_' in line: print(line)
    if not passed: raise SystemExit('native MQC parser/control fixture failed; logs retained')


if __name__ == '__main__':
    main()
