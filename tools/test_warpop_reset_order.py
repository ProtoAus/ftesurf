"""CPU QC controls for ordered reset/hold cancellation. No network/UpdateView claim.
Runs production Frame/InputFrame/ACK and server WOP dispatch in a dedicated QC VM.
Engine/stat/preview and server zone/hold services are explicit test doubles.
--control uses the inspected pre-fix source for an acting red control.
"""
from pathlib import Path
import argparse, hashlib, json, re, shutil, socket, struct, subprocess
p=argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True)
p.add_argument('--control', action='store_true')
p.add_argument('--no-reset-backstop', action='store_true', help='acting negative: omit reset terminal handling')
p.add_argument('--rewind-only', action='store_true', help='targeted production rewind handoff controls')
p.add_argument('--no-rewind-handoff', action='store_true', help='acting negative: omit adoption cancellation')
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
OUT=a.out.resolve(); assert not OUT.exists(); (OUT/'src').mkdir(parents=True); (OUT/'ftesurf/maps').mkdir(parents=True)
def source(path):
    if a.control:
        return subprocess.check_output(['git','-C',str(root),'show','02e58218:'+path]).decode()
    return (root/path).read_text()
def function(text,name):
    m=re.search(r'(?ms)^(?:void|float)\([^\n]*\) '+name+r' =(?:\n\{.*?^\};| \{[^\n]*\};)', text)
    assert m,name
    return m.group()
w=source('src/client/cl_warpop.qc'); s=source('src/client/cl_saveloc.qc')
rw=source('src/client/cl_rewind.qc')
if a.no_rewind_handoff:
    assert a.rewind_only and not a.control
    anchor='\tWarpOp_HoldAdopt(); // the accepted go owns its hold/countdown (or TAS pause)'
    assert rw.count(anchor)==1
    rw=rw.replace(anchor,'\t// TEST MUTANT: omit accepted-go adoption')
if a.no_reset_backstop:
    assert not a.control
    assert w.count('	WarpOp_ResetReleaseFrame();') == 1
    w=w.replace('	WarpOp_ResetReleaseFrame();','	// TEST MUTANT: omit reset terminal handling')
constants='\n'.join(l for l in (root/'src/shared/sh_defs.qc').read_text().splitlines() if re.match(r'#define (WOP|STAT_FS_(?:SLACK|HOLD|SAVECOUNT|SAVEINDEX|TSRETURN|TASREWIND|WOPACK|WOPR|WOPM))',l))
constants+='\n'+re.search(r'^#define SL_HOLD_DEADMAN .+$',s,re.M).group()
prefix=r'''
#define VF_CL_VIEWANGLES 0
#define WOP_RING 64
#define WOPP_MOVE 2
#define WOPP_LIST 1
#define WOPP_BLINDLOAD 3
#define WOPP_HOLDROW 4
#define WOPP_STEP 5
#define WOPP_RESET 6
#define WOPB_REFUSED 2
#pragma noref 1
#define WOPB_BLIND 1
#define getstatf TestStat
#define cvar TestCvar
#define serverkey TestServerKey
#define serverkeyfloat TestServerKeyFloat
#define setproperty TestProperty
#define localcmd TestLocalCmd
float cltime, servercommandframe, clientcommandframe, input_impulse, predinput_held, wop_inputt;
float numclientseats, rw_on;
#define RW_LOST 5
#define SLOP_LOADED 2
#define SLOP_SAVED 1
float rw_ack, rw_cd, rw_dir, rw_leave, rw_seq, rw_goi, rw_i, rw_sentat;
float rw_reqtick, rw_reqticks, rw_go_practice, rw_nativeok, rw_go_ticket, rw_tas;
float rw_nativeticks, rw_nativetick, rw_resi, rw_resgen, rw_resn, rw_gosl;
float tr_practice, tr_tick, tr_cur_t, rec_rp_golines, rec_rp_lines, tr_saveack, tr_cur_on, tr_gen, tr_nsamp;
float rec_sl_holdt0, test_eventseq, test_eventop, test_eventpending;
vector tr_cur_p, rw_gop;
string test_request;
float *rec_sl_id;
float *rec_sl_seq;
.float rec_wt_hold, rw_pin, rec_wt_pin, rec_sl_slop, rw_goid, rw_goseq;
void() WarpOp_HoldAdopt;
float() Rewind_Waiting;
void() Rewind_Abandon;
float wop_resetq, wop_resetseq, wop_resetat, wop_resetheld;
float wop_loadlast, wop_rellast, wop_c_ok, wop_c_ack, wop_x_ok, wop_x_held, wop_heldmode;
vector input_angles;
float *wop_seq; float *wop_op; float *wop_q; float *wop_duck; float *wop_qt; float *wop_blind;
vector *wop_org; vector *wop_vel; vector *wop_ang; vector *wop_legorg; vector *wop_legang;
float wop_qn, wop_slot, wop_relseq, wop_relat;
float wop_loadpred, wop_loadsteps, wop_tok, wop_loadseq, wop_loadackat;
vector wop_loadvel, wop_tgorg, wop_tgvel, wop_tgang, rec_sl_holdang;
string wop_why;
float rec_sl_holding, rec_sl_holdkey, rec_sl_holdrep, rec_sl_holdseen;
float rec_sl_refkey, rec_sl_refseen, rec_sl_holdang_ok, rec_sl_wophold, rec_sl_pv_on, rec_sl_upwait, rec_sl_pred;
float rec_sl_leadans, rec_sl_leadhad, rec_sl_holdack, rec_sl_holdackat, rec_sl_sent;
float test_busy, test_ack, test_clear, checks, failures, test_loadkeys, test_hold;
float test_serverhold, test_holdoffs, test_localcmds, test_refuse, test_return;
.float wop_hi, wop_lo, wop_ack, run_inserver, rec_sl_requesttag, rec_sl_auto, rec_sl_index;
float input_cmd_kind, input_cmd_sequence_hi, input_cmd_sequence_lo, wop_live;
float(string name) TestCvar = { return 1; };
string(string name) TestServerKey = { return "1"; };
void(float p, vector v) TestProperty = {};
void(string cmd) TestLocalCmd = { test_localcmds+=1; };
void(string msg) PE_Expect = {};
void(string msg) PE_Note = {};
float() LT_StatsAreMine = { return 1; };
void() Trail_RequestReset = {};
void() WarpOp_Legs = {};
void() WarpOp_Cur = {}; // snapshot delivery is explicit in Publish
float() WarpOp_Idx = { return 1; };
float() WarpOp_Cnt = { return 1; };
float() SV_DevOn = { return 0; };
float(entity e) SV_SaveLocRate = { return 1; };
void(entity e, float held) SV_SaveLocHold = { test_serverhold=held; };
void(entity e, float idx) SV_SaveLocLoad = { e.rec_sl_slop=SLOP_LOADED; };
float(float op) FS_SlopOp = { return op; };
float(entity e) SL_Blk = { return 0; };
float(float blk) SL_Base = { return 0; };
float(entity e) SV_RewindAlone = { return 0; };
void(entity e) SV_WatchRelease = { e.rec_wt_hold=0; };
void(entity e, float held) SV_WatchHold = { e.rec_wt_hold=held; };
float() SaveEvent_Seq = { return test_eventseq; };
float() SaveEvent_Slop = { return test_eventop; };
float() SaveEvent_Pending = { return test_eventpending; };
float() SaveEvent_Tag = { return 0; };
float() SaveEvent_Ticks = { return 0; };
float(string name) TestServerKeyFloat = { return 0.015; };
void() Trail_ReplayClear = {};
string() SaveLoc_SaveCommand = { return "sl_saveview 1 2 3 0 0 0 0 0 0"; };
string() Rewind_At = { return "1 2 3 4"; };
void() Rewind_Close = { rw_on=0; };
void(entity e, float delta) SV_SaveLocStep = {};
void(entity e) SV_SaveLocFirst = {};
void(entity e) SV_SaveLocLast = {};
void(string word, float n) SV_ZoneChatCommand = { if (!test_refuse) SV_SaveLocHold(self,FALSE); };
void(entity e, vector was) SV_RewindWarped = {};
float() WarpOp_Able = { return 1; };
float() Trail_RequestBusy = { return test_busy; };
void() SaveLoc_Resync = {};
void() SaveLead_Clear = { test_clear += 1; };
float(float st) TestStat = { if(st == STAT_FS_SLACK) return test_ack; if(st == STAT_FS_WOPACK) return self.wop_ack; if(st == STAT_FS_TSRETURN) return test_return; if(st == STAT_FS_HOLD) return test_hold; if(st == STAT_FS_WOPRANG+2 || st == STAT_FS_WOPMANG+2) return WOPD_ANG; return 100; };
float(float op) WarpOp_Row = { wop_tgorg='20 0 0'; wop_tgang='0 0 0'; wop_tgvel='0 0 0'; return 1; };
float() WarpOp_Charge = { return 1; };
float() SaveLoc_RunLocked = { return 0; };
void(float key) SaveLoc_Refuse = {};
void(float key) SaveLoc_LoadKey = { test_loadkeys+=1; };
void() SaveLoc_KeyUp = {};
void(string c) SaveLoc_Cmd = { rec_sl_sent+=1; test_request=c; if(c == "sl_holdoff") { test_holdoffs+=1; SV_SaveLocHold(self,FALSE); } };
void() SaveLoc_Release = {};
'''
helpers='\n'.join(function(w,n) for n in ('WarpOp_Ack','WarpOp_Unanswered','WarpOp_Slot','WarpOp_Queue','WarpOp_Pending'))
if 'void() SaveLoc_ResetHold =' in s: helpers+='\n'+function(s,'SaveLoc_ResetHold')
if 'void() WarpOp_HoldAdopt =' in w: helpers+='\n'+function(w,'WarpOp_HoldAdopt')
helpers+='\n'+function(rw,'Rewind_Waiting')
helpers+='\n'+function(w,'WarpOp_ResetTry')+'\n'+function(w,'WarpOp_Load')
if 'void() WarpOp_ResetReleaseFrame =' in w: helpers+='\n'+function(w,'WarpOp_ResetReleaseFrame')
helpers+='\n'+function(w,'WarpOp_PracticeReturnCancel')+'\n'+function(w,'WarpOp_Frame')+'\n'+function(w,'WarpOp_InputFrame')
helpers+='\n'+function(source('src/server/sv_warpop.qc'),'SV_WarpOpCommand')
if a.rewind_only:
    helpers+='\n'+function(rw,'Rewind_Go')+'\n'+function(rw,'Rewind_Answer')+'\n'+function(rw,'Rewind_Abandon')
    helpers+='\n'+function(source('src/server/sv_player.qc'),'SV_SaveLocGo')
console=function(s,'SaveLoc_Console')
start=console.index('\tif (c == "+sl_hold")')
end=console.index('\n\tif (c == "sl_load"',start)
helpers+='\nfloat(string c) HoldConsole = { local float k;\n'+console[start:end]+'\nreturn FALSE;\n};'
tests=r'''
void(float ok, string label) Check = { checks+=1; if(!ok) { failures+=1; bprint(2,strcat("RESET FAIL: ",label,"\n")); } };
void() Setup = {
local float i;
for(i=0;i<WOP_RING;i+=1) wop_seq[i]=0;
wop_qn=0; test_busy=test_ack=rec_sl_sent=0;
rec_sl_holding=rec_sl_holdkey=rec_sl_refkey=test_hold=test_loadkeys=0;
rec_sl_pv_on=rec_sl_holdang_ok=rec_sl_leadans=0;
cltime=10; servercommandframe=0; clientcommandframe=0; test_clear=0;
wop_resetq=wop_resetseq=wop_resetat=wop_relseq=wop_relat=0;
wop_c_ok=wop_c_ack=wop_x_ok=wop_x_held=0;
test_holdoffs=test_localcmds=test_serverhold=test_refuse=test_return=0;
wop_loadlast=wop_rellast=0;
self.wop_ack=self.wop_hi=self.wop_lo=0;
self.classname="player"; self.run_inserver=1; wop_live=1; numclientseats=1;
rw_ack=rw_cd=rw_on=rw_tas=rw_leave=0;
test_eventseq=1; test_eventop=SLOP_SAVED; test_eventpending=0;
tr_practice=0; tr_tick=0.015; tr_cur_t=0.3; tr_cur_p='1 2 3';
tr_saveack=0; tr_gen=1; tr_nsamp=10;
};
void() worldspawn = {
local float i, ok;
self=spawn();
wop_seq=memalloc(4*WOP_RING); wop_op=memalloc(4*WOP_RING); wop_q=memalloc(4*WOP_RING); wop_duck=memalloc(4*WOP_RING); wop_qt=memalloc(4*WOP_RING); wop_blind=memalloc(4*WOP_RING);
wop_org=memalloc(12*WOP_RING); wop_vel=memalloc(12*WOP_RING); wop_ang=memalloc(12*WOP_RING);
Setup();
Check(WarpOp_ResetTry(WOP_RESET),"stationary reset admitted");
Check(wop_op[0]==WOP_RESET && !wop_blind[0],"stationary destination still predicted");
Setup();
Check(WarpOp_Queue(WOP_LOAD,'10 0 0','0 0 0','0 0 0',0),"earlier load admitted");
// Simulate an in-flight command at 300ms; ACK has not reached it.
wop_seq[0]=100; cltime+=0.3;
rec_sl_holding=rec_sl_pv_on=rec_sl_holdang_ok=rec_sl_leadans=1; rec_sl_holdkey=50;
wop_relseq=99; wop_relat=10;
ok=WarpOp_ResetTry(WOP_RESET);
Check(ok,"held reset stays on ordered command stream");
Check(wop_seq[0]==100 && wop_op[0]==WOP_LOAD,"earlier admitted load retained");
Check(wop_seq[1]==-1 && wop_op[1]==WOP_RESET && wop_blind[1],"reset queued blind behind load");
Check(!rec_sl_holding && !rec_sl_pv_on && !rec_sl_holdang_ok && !rec_sl_leadans && test_clear==1,"terminal local ownership cancelled");
Check(rec_sl_refkey==50 && rec_sl_refseen==cltime,"held physical key transferred to repeat suppression");
// No release fallback may reach a later load.
Check(!wop_relseq && !wop_relat,"old holdoff backstop cancelled");
test_hold=1;
Check(WarpOp_Load(),"next production load admitted despite stale server hold");
Check(wop_op[0]==WOP_LOAD && wop_op[1]==WOP_RESET && wop_op[2]==WOP_LOAD && wop_q[0]<wop_q[1] && wop_q[1]<wop_q[2],"load reset next-load queue order");
tokenize("+sl_hold 50"); HoldConsole("+sl_hold");
Check(test_loadkeys==0,"cancelled key repeat suppressed");
tokenize("-sl_hold 50"); HoldConsole("-sl_hold");
Check(!rec_sl_refkey,"cancelled key release clears suppression");
tokenize("+sl_hold 50"); HoldConsole("+sl_hold");
Check(test_loadkeys==1,"fresh key press can load");
Setup(); test_busy=1; rec_sl_holding=1;
Check(!WarpOp_ResetTry(WOP_RESET) && rec_sl_holding && !test_clear,"busy trail unchanged");
Setup(); rec_sl_sent=1; rec_sl_holding=1;
Check(!WarpOp_ResetTry(WOP_RESET) && rec_sl_holding && !test_clear,"in-flight reliable save unchanged");
Setup(); for(i=0;i<WOP_RING;i+=1) wop_seq[i]=-1;
rec_sl_holding=1;
Check(!WarpOp_ResetTry(WOP_RESET) && rec_sl_holding && !test_clear,"full queue retains hold");
bprint(2,sprintf("RESET RESULT checks=%g failures=%g\n",checks,failures));
};
void() main={}; void() StartFrame={}; void() SetNewParms={}; void() SetChangeParms={};
void() ClientConnect={}; void() PutClientInServer={}; void() ClientDisconnect={}; void() ClientKill={};
void() PlayerPreThink={}; void() PlayerPostThink={}; void() SpectatorConnect={}; void() SpectatorThink={}; void() SpectatorDisconnect={};
'''
outcomes=r'''void() Publish = {
 test_hold=test_serverhold; wop_x_held=test_serverhold; wop_x_ok=1;
 wop_c_ok=1; wop_c_ack=self.wop_ack;
};
void(float kind) Dispatch = {
 input_cmd_kind=kind; input_cmd_sequence_hi=0; input_cmd_sequence_lo=clientcommandframe;
 SV_WarpOpCommand();
};
void() BeginHeldReset = {
 Setup();
 WarpOp_Queue(WOP_LOAD,'10 0 0','0 0 0','0 0 0',0);
 clientcommandframe=100; WarpOp_InputFrame(); Dispatch(1); Publish();
 Check(test_serverhold && WarpOp_Ack()==100,"production load dispatch establishes hold and ACK");
 rec_sl_holding=1; rec_sl_holdkey=50;
 Check(WarpOp_ResetTry(WOP_RESET) && !rec_sl_holding && wop_resetq,"reset retains release obligation after camera cancel");
 WarpOp_Frame();
 Check(wop_resetseq==-1 && !test_holdoffs,"queued reset cannot release early");
};
void() OutcomeTests = {
 local float mode, oldq;
 for(mode=0;mode<4;mode+=1) {
  BeginHeldReset();
  clientcommandframe=101; WarpOp_InputFrame();
  Check(input_impulse==WOP_RESET && wop_resetseq==101,"production InputFrame binds reset command");
  test_refuse=(mode==2);
  if(mode==1) Dispatch(0); // nondecoded: dispatch must not ACK
  if(mode>=2) Dispatch(1); // refused and successful decoded dispatch both ACK
  Publish();
  Check(WarpOp_Ack()==((mode<2)?100:101),"real ACK distinguishes lost/nondecoded from dispatched");
  Check(test_serverhold==(mode!=3),"reset service refused or acted as configured");
  servercommandframe=101; WarpOp_Frame(); cltime+=0.4; WarpOp_Frame();
  Check(!test_holdoffs && wop_resetq,"ACK or reaching reset command alone cannot release or discharge");
  servercommandframe=102; WarpOp_Frame();
  Check(!test_holdoffs && wop_resetq,"progress starts hold settle window without immediate holdoff");
  cltime+=0.31; WarpOp_Frame();
  Check(!wop_resetq && !test_serverhold && test_holdoffs==((mode<3)?1:0),"terminal lost nondecoded refused or successful reset resolved");
  cltime+=0.4; WarpOp_Frame();
  Check(test_holdoffs==((mode<3)?1:0),"terminal reset sends at most one delayed holdoff");
 }
 BeginHeldReset(); clientcommandframe=101; WarpOp_InputFrame(); test_refuse=1; Dispatch(1); Publish();
 servercommandframe=102; test_hold=0; WarpOp_Frame(); cltime+=0.5; WarpOp_Frame();
 Check(wop_resetq && !test_holdoffs,"split numeric and coherent hold cannot discharge obligation");
 test_hold=1; WarpOp_Frame(); cltime+=0.2; WarpOp_Frame();
 Check(wop_resetq && !test_holdoffs,"coherent hold starts a fresh settle interval");
 cltime+=0.11; WarpOp_Frame();
 Check(!wop_resetq && test_holdoffs==1,"coherent held outcome eventually releases");
 BeginHeldReset(); clientcommandframe=101; WarpOp_InputFrame(); test_refuse=1; Dispatch(1); Publish();
 servercommandframe=102; WarpOp_Frame(); cltime+=0.2;
 test_hold=wop_x_held=0; WarpOp_Frame(); cltime+=0.2; WarpOp_Frame();
 Check(wop_resetq,"coherent held-to-free change restarts settle window");
 cltime+=0.11; WarpOp_Frame();
 Check(!wop_resetq && !test_holdoffs,"settled free state discharges without redundant holdoff");
 BeginHeldReset(); clientcommandframe=101; WarpOp_InputFrame();
 // Deliberately do not deliver the reset. Both visible hold sources are still
 // an old free snapshot even though the prior server load already holds.
 test_hold=wop_x_held=0; servercommandframe=102; WarpOp_Frame();
 Check(wop_resetq && !test_holdoffs,"stale coherent free snapshot cannot discharge before settle");
 cltime+=0.31; WarpOp_Frame();
 Check(test_holdoffs==1 && !test_serverhold,"no reset ACK means delayed holdoff even under stale free stats");
 BeginHeldReset(); test_return=1; WarpOp_Frame();
 Check(!wop_resetq && !wop_resetseq && !test_holdoffs,"production practice return cancels reset obligation without fallback");
 for(mode=0;mode<3;mode+=1) {
  BeginHeldReset(); oldq=wop_resetq;
  if(mode>0) { clientcommandframe=101; WarpOp_InputFrame(); }
  if(mode==2) { servercommandframe=102; WarpOp_Frame(); cltime+=0.2; }
  Check(WarpOp_Load() && !wop_resetq,"new production load cancels queued sent or settling reset obligation");
  // If the reset was still queued, production InputFrame must carry it first,
  // without re-arming an obligation now owned by the newer load.
  clientcommandframe=103; WarpOp_InputFrame();
  if(input_impulse==WOP_RESET) { Dispatch(1); clientcommandframe=104; WarpOp_InputFrame(); }
  Check(input_impulse==WOP_LOAD && !wop_resetq,"older reset InputFrame cannot rearm after newer load");
  Dispatch(1); Publish(); servercommandframe=105; WarpOp_Frame(); cltime+=0.5; WarpOp_Frame();
  Check(test_serverhold && !test_holdoffs,"old reset backstop cannot release newer server hold");
 }
 BeginHeldReset(); cltime+=0.26; WarpOp_Frame();
 Check(test_localcmds==1 && wop_resetseq==100 && !test_holdoffs,"uncarried reset fallback retains delayed release obligation");
 servercommandframe=101; Publish(); WarpOp_Frame(); cltime+=0.31; WarpOp_Frame();
 Check(test_holdoffs==1 && !wop_resetq,"uncarried refused fallback eventually releases old hold");
};
'''
if not a.control:
    tests=tests.replace('void() worldspawn = {',outcomes+'\nvoid() worldspawn = {')
    tests=tests.replace('bprint(2,sprintf("RESET RESULT', 'OutcomeTests();\nbprint(2,sprintf("RESET RESULT')
if a.rewind_only:
    fixture=(root/'tools/fixtures/warpop_rewind_handoff.qc').read_text()
    start=tests.index('void() worldspawn = {')
    end=tests.index('bprint(2,sprintf("RESET RESULT',start)
    allocation=tests[tests.index('self=spawn();',start):tests.index('Setup();',start)]
    tests=tests[:start]+fixture+'\nvoid() worldspawn = {\n'+allocation+'RewindTests();\n'+tests[end:]
shutil.copy2(root/'src/defs/sv_defs.qc',OUT/'src/defs.qc')
(OUT/'src/test.qc').write_text(constants+'\n'+prefix+helpers+tests)
(OUT/'src/progs.src').write_text('../ftesurf/qwprogs.dat\ndefs.qc\ntest.qc\n')
r=subprocess.run([str(root/'src/fteqcc64.exe'),'-srcfile','progs.src'],cwd=OUT/'src',capture_output=True)
(OUT/'compile.log').write_bytes(r.stdout+r.stderr)
assert r.returncode==0,(r.returncode,r.stdout,r.stderr)
assert not [l for l in (r.stdout+r.stderr).splitlines() if b'warning' in l.lower() and b'Done. 0 warnings' not in l]
with Path('C:/FTESurf/id1/pak0.pak').open('rb') as pak:
    magic,offset,size=struct.unpack('<4sii',pak.read(12)); pak.seek(offset); directory=pak.read(size)
    entry=next(struct.unpack('<56sii',directory[i:i+64]) for i in range(0,size,64) if directory[i:i+56].split(b'\0',1)[0]==b'maps/start.bsp')
    pak.seek(entry[1]); body=pak.read(entry[2])
(OUT/'ftesurf/maps/start.bsp').write_bytes(body)
(OUT/'default.fmf').write_text('FTEMANIFEST 1\nGAME ResetUnit\nNAME "Reset CPU unit"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG unused\n')
(OUT/'ftesurf/unit.cfg').write_text('cfg_save_auto 0\nlog_enable 1\nlog_name reset-unit\nsv_public 0\nsv_progs qwprogs.dat\nmap start\nquit\n')
with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe: probe.bind(('127.0.0.1',27601))
command=['C:/FTEQuake/fteqwsv64.exe','-manifest',str(OUT/'default.fmf'),'-basedir',str(OUT),'-port','27601','+exec','unit.cfg']
with (OUT/'process.log').open('wb') as log:
    proc=subprocess.Popen(command,cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
    (OUT/'owned-pid.json').write_text(json.dumps({'pid':proc.pid}))
    try: code=proc.wait(timeout=30)
    except subprocess.TimeoutExpired: proc.terminate(); proc.wait(timeout=10); raise
logs=b'\n'.join(f.read_bytes() for f in (OUT/'ftesurf').rglob('*.log'))+(OUT/'process.log').read_bytes()
(OUT/'combined.log').write_bytes(logs)
results=re.findall(rb'RESET RESULT checks=(\d+) failures=(\d+)',logs)
assert code==0 and results, (code,logs)
if a.rewind_only:
    expected=4 if a.no_rewind_handoff else 0
    assert all(int(n)==36 and int(f)==expected for n,f in results),results
    if a.no_rewind_handoff:
        assert set(re.findall(rb'RESET FAIL: ([^\r\n]+)',logs))=={
            b'production rewind answer adopts countdown and retires reset obligation',
            b'old reset cannot release adopted rewind countdown',
        }
elif a.control: assert all(int(n)==17 and int(f)==8 for n,f in results),results
elif a.no_reset_backstop:
    assert all(int(n)==100 and int(f)==11 for n,f in results),results
    labels=set(re.findall(rb'RESET FAIL: ([^\r\n]+)',logs))
    assert labels=={
        b'terminal lost nondecoded refused or successful reset resolved',
        b'terminal reset sends at most one delayed holdoff',
        b'coherent held outcome eventually releases',
        b'settled free state discharges without redundant holdoff',
        b'no reset ACK means delayed holdoff even under stale free stats',
        b'uncarried refused fallback eventually releases old hold',
    }, labels
else: assert all(int(n)==100 and int(f)==0 for n,f in results),results
(OUT/'inputs.json').write_text(json.dumps({'control':a.control,'no_reset_backstop':a.no_reset_backstop,'rewind_only':a.rewind_only,'no_rewind_handoff':a.no_rewind_handoff,'helper_sha256':hashlib.sha256(helpers.encode()).hexdigest(),'result':str(results)},indent=2))
print('Acting QC checks/failures:',results[0],'; synthetic300ms ACK delay, NOT network or camera acceptance')
