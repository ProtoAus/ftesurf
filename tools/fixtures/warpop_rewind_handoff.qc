void() RewindTests = {
 local float practice;
 for(practice=0;practice<2;practice+=1) {
  BeginHeldReset(); clientcommandframe=101; WarpOp_InputFrame(); Dispatch(1); Publish();
  servercommandframe=102; WarpOp_Frame(); cltime+=0.1;
  rw_on=1; tr_practice=practice; Rewind_Go();
  Check(rw_ack && wop_resetq,"production rewind request retains recovery until adoption");
  Check(strstrofs(test_request,practice?"sl_goview":"sl_saveat ",0)==0,"production rewind selects native or practice go request");
  SV_SaveLocGo(self); Publish();
  Check(test_serverhold,"production server go creates newer hold");
  cltime+=0.5; WarpOp_Frame();
  Check(test_serverhold && !test_holdoffs && wop_resetq,"pending go fences old reset after new server hold");
  test_ack=rw_ack; test_eventpending=1; Rewind_Answer(); cltime+=0.5; WarpOp_Frame();
  Check(rw_ack && test_serverhold && !test_holdoffs,"ACK with pending split event cannot release new hold");
  test_eventseq=2; test_eventop=SLOP_LOADED; test_eventpending=0; Rewind_Answer();
  Check(!rw_ack && rw_cd>cltime && rec_sl_holding && !wop_resetq,"production rewind answer adopts countdown and retires reset obligation");
  WarpOp_Frame(); cltime+=0.5; WarpOp_Frame();
  Check(test_serverhold && !test_holdoffs,"old reset cannot release adopted rewind countdown");
 }
 BeginHeldReset(); clientcommandframe=101; WarpOp_InputFrame(); test_refuse=1; Dispatch(1); Publish();
 servercommandframe=102; WarpOp_Frame(); rw_on=1; Rewind_Go();
 cltime+=0.5; WarpOp_Frame();
 Check(wop_resetq && !test_holdoffs,"refused-go outcome not assumed while request pending");
 test_ack=rw_ack; Rewind_Answer();
 Check(!rw_ack && wop_resetq,"refused rewind answer retains prior reset recovery");
 WarpOp_Frame(); cltime+=0.31; WarpOp_Frame();
 Check(!test_serverhold && test_holdoffs==1,"refused rewind cannot strand prior hold");
 BeginHeldReset(); clientcommandframe=101; WarpOp_InputFrame(); test_refuse=1; Dispatch(1); Publish();
 servercommandframe=102; rw_on=1; Rewind_Go();
 cltime+=RW_LOST+0.1; Rewind_Answer();
 Check(!rw_ack && !rw_on && !test_serverhold && test_holdoffs==1,"production unanswered-go abandon releases prior hold");
 Publish(); WarpOp_Frame(); cltime+=0.31; WarpOp_Frame();
 Check(!wop_resetq && test_holdoffs==1,"timeout recovery retires old obligation without duplicate holdoff");
 BeginHeldReset(); clientcommandframe=101; WarpOp_InputFrame(); test_refuse=1; Dispatch(1); Publish();
 servercommandframe=102; test_busy=1; Rewind_Go();
 Check(!rw_ack && wop_resetq,"busy rewind admission leaves recovery armed");
 WarpOp_Frame(); cltime+=0.31; WarpOp_Frame();
 Check(!test_serverhold && test_holdoffs==1,"busy rewind cannot strand prior hold");
};
