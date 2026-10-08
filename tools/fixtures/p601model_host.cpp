#define main PassiveControls
#include "p598imgui_host.cpp"
#undef main
static pluguiowner_t modelowner = {1,InteractiveMenu,100};
static pluguiframe_t modelframe = {sizeof(modelframe),modelowner,1,320,240,640,480,{0,0,640,480}};
static void Event(unsigned type,float a=0,float b=0)
{
	pluguiinputevent_t e = {sizeof(e),type,a,b};
	Check(inputservice.Input(&modelowner,&e),"explicit model input accepted");
}
static void DrawModel()
{
	modelframe.owner=modelowner; modelframe.frame++; ResetInk();
	Check(service.Draw(&modelframe),"actual model draw/mesh acts");
	Check(calls && !ink.empty(),"model produced native ink");
}
static pluguimodel_t Snapshot(unsigned revision,bool reordered=false)
{
	pluguimodel_t m = {}; m.structsize=sizeof(m); m.revision=revision; m.count=3;
	m.widgets[0]={10,90,PLUGUI_WIDGET_TEXT,0,"Plain ## label"};
	m.widgets[1]={11,91,PLUGUI_WIDGET_BUTTON,0,"Button ### literal"};
	m.widgets[2]={12,92,PLUGUI_WIDGET_CHECKBOX,0,"Checkbox"};
	if (reordered) std::swap(m.widgets[1],m.widgets[2]);
	return m;
}
static pluguimodelaction_t Click(float x,float y)
{
	Event(PLUGUI_INPUT_MOUSEPOS,x,y); Event(PLUGUI_INPUT_BUTTON,0,1); DrawModel();
	Event(PLUGUI_INPUT_BUTTON,0,0); DrawModel();
	pluguimodelaction_t a = {}; Check(modelservice.PollModel(&modelowner,&a),"real widget click emitted action");
	pluguimodelaction_t empty = {}; Check(!modelservice.PollModel(&modelowner,&empty),"model action once only");
	Check(a.generation==modelowner.generation,"generation attached to action");
	return a;
}
int main()
{
	if (PassiveControls()) return 1;
	unsigned start=checks;
	Check(modelservice.SetModel && modelservice.PollModel,"model service exported");
	Check(service.Open(&modelowner),"interactive diagnostic owner opens");
	pluguimodel_t m=Snapshot(1),bad=m; pluguimodelaction_t a = {};
	pluguiowner_t wrong=modelowner; wrong.vm=2;
	Check(!modelservice.SetModel(&wrong,&m),"VM isolation"); wrong=modelowner; wrong.generation++;
	Check(!modelservice.SetModel(&wrong,&m),"stale generation isolation"); wrong=modelowner; wrong.owner++;
	Check(!modelservice.SetModel(&wrong,&m),"owner isolation");
	bad.structsize--; Check(!modelservice.SetModel(&modelowner,&bad),"exact snapshot size");
	bad=m; bad.count=65; Check(!modelservice.SetModel(&modelowner,&bad),"bounded count");
	bad=m; bad.revision=0; Check(!modelservice.SetModel(&modelowner,&bad),"positive revision");
	bad=m; bad.revision=16777216; Check(!modelservice.SetModel(&modelowner,&bad),"exact QC revision");
	bad=m; bad.widgets[1].id=10; Check(!modelservice.SetModel(&modelowner,&bad),"duplicate widget identity");
	bad=m; bad.widgets[1].row=0; Check(!modelservice.SetModel(&modelowner,&bad),"nonzero row identity");
	bad=m; bad.widgets[1].value=NAN; Check(!modelservice.SetModel(&modelowner,&bad),"nonfinite value");
	bad=m; bad.widgets[1].value=1; Check(!modelservice.SetModel(&modelowner,&bad),"typed immutable value");
	bad=m; std::memset(bad.widgets[0].label,'x',sizeof(bad.widgets[0].label));
	Check(!modelservice.SetModel(&modelowner,&bad),"missing label terminator");
	for (const char *text : {"\xc0\xaf","\xed\xa0\x80","\xf4\x90\x80\x80","\xe2\x82","bad\nlabel"})
	{
		bad=m; std::strcpy(bad.widgets[0].label,text);
		Check(!modelservice.SetModel(&modelowner,&bad),"malformed UTF-8 rejected");
	}
	Check(modelservice.SetModel(&modelowner,&m),"atomic snapshot accepted");
	m.widgets[1].id=666; m.widgets[1].label[0]='X';
	Check(contexts[0]->model.widgets[1].id==11 && contexts[0]->model.widgets[1].label[0]=='B',"native deep copy");
	bad=Snapshot(1); Check(!modelservice.SetModel(&modelowner,&bad),"same/older revisions rejected");
	DrawModel(); DrawModel(); a=Click(110,122);
	Check(a.id==11 && a.row==91 && a.revision==1 && a.value==1,"actual button stable identity");
	a=Click(85,145); Check(a.id==12 && a.row==92 && a.revision==1 && a.value==1,"actual checkbox typed identity");
	Check(contexts[0]->model.widgets[2].value==0,"snapshot remains immutable until QC replacement");
	//Queued press never reaches replacement, and labels/reorder never define identity.
	Event(PLUGUI_INPUT_MOUSEPOS,110,122); Event(PLUGUI_INPUT_BUTTON,0,1);
	m=Snapshot(2,true); std::strcpy(m.widgets[2].label,"Renamed button");
	Check(modelservice.SetModel(&modelowner,&m),"reordered/renamed model accepted");
	Event(PLUGUI_INPUT_BUTTON,0,0); DrawModel();
	Check(!modelservice.PollModel(&modelowner,&a),"queued old press cannot hit replacement");
	a=Click(110,145); Check(a.id==11 && a.row==91 && a.revision==2,"reordered/renamed button retains identity");
	//Held press and unpolled completed click are reset by replacement.
	Event(PLUGUI_INPUT_MOUSEPOS,110,145); Event(PLUGUI_INPUT_BUTTON,0,1); DrawModel();
	m=Snapshot(3); m.widgets[1].id=21; m.widgets[1].row=191;
	Check(modelservice.SetModel(&modelowner,&m),"deleted row replacement accepted");
	Event(PLUGUI_INPUT_BUTTON,0,0); DrawModel();
	Check(!modelservice.PollModel(&modelowner,&a),"held old press cannot select replacement row");
	a=Click(110,122); Check(a.id==21 && a.row==191 && a.revision==3,"new row actually clickable");
	Event(PLUGUI_INPUT_MOUSEPOS,110,122); Event(PLUGUI_INPUT_BUTTON,0,1); DrawModel();
	Event(PLUGUI_INPUT_BUTTON,0,0); DrawModel(); Check(contexts[0]->actions==1,"acting unpolled action control");
	m=Snapshot(4); Check(modelservice.SetModel(&modelowner,&m),"pending action replacement");
	Check(!modelservice.PollModel(&modelowner,&a),"old unpolled action discarded immediately");
	DrawModel(); Check(!modelservice.PollModel(&modelowner,&a),"old unpolled action stays discarded");
	//Exact label limit and non-ASCII labels; max and empty counts act.
	m={}; m.structsize=sizeof(m); m.revision=5; m.count=64;
	for (unsigned i=0;i<m.count;i++) m.widgets[i]={i+1,i+1,PLUGUI_WIDGET_TEXT,0,"ASCII \xc3\xa9 \xe2\x82\xac \xf0\x9f\x98\x80"};
	std::memset(m.widgets[0].label,'x',95); m.widgets[0].label[95]=0;
	Check(modelservice.SetModel(&modelowner,&m),"max count/label/scalar UTF-8 accepted"); DrawModel();
	m.revision=6; m.count=0; Check(modelservice.SetModel(&modelowner,&m),"empty clears model"); DrawModel();
	Check(!modelservice.PollModel(&modelowner,&a),"empty model emits no actions");
	m=Snapshot(7); Check(modelservice.SetModel(&modelowner,&m),"recover after empty"); DrawModel();
	Context &c=*contexts[0];
	for (unsigned i=0;i<=PLUGUI_INPUT_MAX_ACTIONS;i++) ModelAction(c,m.widgets[1],1);
	Check(c.actionoverflow && c.actions==PLUGUI_INPUT_MAX_ACTIONS,"bounded model queue overflow acts");
	Event(PLUGUI_INPUT_RESET); Check(!modelservice.PollModel(&modelowner,&a),"explicit reset discards model actions");
	service.Close(&modelowner,PLUGUI_CLOSE_EXPLICIT); service.Close(&modelowner,PLUGUI_CLOSE_EXPLICIT);
	Check(!modelservice.PollModel(&modelowner,&a) && live.empty(),"close releases once/no stale model action");
	wrong=modelowner; modelowner.generation++; Check(service.Open(&modelowner),"fresh owner reopens");
	m=Snapshot(1); Check(modelservice.SetModel(&modelowner,&m),"revision lifetime scoped to generation");
	Check(!modelservice.PollModel(&wrong,&a) && !modelservice.SetModel(&wrong,&m),"old generation never aliases reopened owner");
	DrawModel(); service.Close(&modelowner,PLUGUI_CLOSE_PLUGIN); Check(live.empty(),"unload resources reclaimed");
	std::printf("P601 MODEL indexbits=%zu checks=%u failed=%u\n",sizeof(ImDrawIdx)*8,checks-start,faults);
	return faults ? 1 : 0;
}
