#define main PassiveControls
#include "p590bridge_host.c"
#undef main
static qboolean QDECL Input(const pluguiowner_t *o, const pluguiinputevent_t *e)
{ (void)o; (void)e; return true; }
static qboolean QDECL Poll(const pluguiowner_t *o, pluguiaction_t *a)
{ (void)o; (void)a; return false; }
static unsigned int models, modelpolls;
static int modelfail, modelaction;
static pluguimodel_t copied;
static qboolean QDECL ModelSet(const pluguiowner_t *o, const pluguimodel_t *m)
{
	models++; CHECK(o->generation && PlugUI_ModelValid(m));
	CHECK(currentplug==plugui_service && !Plug_NativeUI_ModelReady());
	CHECK(!Call(PF_ui_native_model_commit,&menu,o->generation));
	if (modelfail) return false;
	copied=*m; return true;
}
static qboolean QDECL ModelPoll(const pluguiowner_t *o, pluguimodelaction_t *a)
{
	modelpolls++; CHECK(currentplug==plugui_service && !Plug_NativeUI_ModelReady());
	if (!modelaction) return false;
	*a=(pluguimodelaction_t){11,91,o->generation,copied.revision,1};
	if (modelaction==2) a->generation++;
	if (modelaction==3) a->revision++;
	if (modelaction==4) a->row++;
	if (modelaction==5) a->id=999;
	if (modelaction==6) a->value=NAN;
	if (modelaction==7) a->value=INFINITY;
	if (modelaction==8) a->value=2;
	if (modelaction==9) a->id=12; //text widget must never produce action
	return true;
}
static float Begin(pubprogfuncs_t *vm,float h,float revision,float count)
{
	globals.value[OFS_PARM1]=revision; globals.value[OFS_PARM2]=count;
	return Call(PF_ui_native_model_begin,vm,h);
}
static float Widget(float h,float index,float id,float row,float type,float value,const char *label)
{
	globals.value[OFS_PARM1]=index;
	globals.value[OFS_PARM2]=id; globals.value[OFS_PARM2+1]=row; globals.value[OFS_PARM2+2]=type;
	globals.value[OFS_PARM3]=value; qclabel=label;
	return Call(PF_ui_native_model_widget,&menu,h);
}
static float ModelPollCall(pubprogfuncs_t *vm,float h,float revision)
{
	globals.value[OFS_PARM1]=revision;
	return Call(PF_ui_native_model_poll,vm,h);
}
static void Publish(float h,float revision)
{
	CHECK(Begin(&menu,h,revision,2));
	CHECK(Widget(h,0,11,91,2,0,"row button"));
	CHECK(Widget(h,1,12,91,1,0,"plain text"));
	CHECK(Call(PF_ui_native_model_commit,&menu,h));
}
#ifndef P601_MAIN
#define P601_MAIN main
#endif
int P601_MAIN(void)
{
	pluguiservice_t service={sizeof(service),PLUGUI_VERSION,PLUGUI_CAP_INDEXED2D,Open,Draw,Close};
	pluguiinputservice_t input={sizeof(input),PLUGUI_INPUT_VERSION,PLUGUI_INPUT_CAP_EVENTS,Input,Poll};
	pluguimodelservice_t extension={sizeof(extension),PLUGUI_MODEL_VERSION,PLUGUI_MODEL_CAP_WIDGETS,ModelSet,ModelPoll},bad;
	float h,old,c; unsigned int start,before,n,close_before;
	char label[97];
	const float invalidcount[]={-1,.5f,65,NAN,INFINITY};
	const float invalidid[]={0,-1,.5f,16777216,NAN,INFINITY};
	const char *invalidlabel[]={"\xc0\xaf","\xed\xa0\x80","\xf4\x90\x80\x80","\xe2\x82","\x80","bad\nlabel"};
	if (PassiveControls()) return 1;
	Plug_NativeUI_PluginClose(plugui_service); memset(plugui_vms,0,sizeof(plugui_vms));
	start=checks; plugui_serial=0; host_framecount++; currentplug=&plugins[0];
	CHECK(!Plug_NativeUI_ModelRegister(&extension,sizeof(extension)));
	CHECK(Plug_NativeUI_Register(&service,sizeof(service)));
	CHECK(!Plug_NativeUI_ModelRegister(&extension,sizeof(extension)));
	CHECK(Plug_NativeUI_InputRegister(&input,sizeof(input)));
	CHECK(!Plug_NativeUI_ModelRegister(NULL,sizeof(extension)));
	CHECK(!Plug_NativeUI_ModelRegister(&extension,sizeof(extension)-1));
	CHECK(!Plug_NativeUI_ModelRegister(&extension,sizeof(extension)+1));
	bad=extension; bad.structsize--; CHECK(!Plug_NativeUI_ModelRegister(&bad,sizeof(bad)));
	bad=extension; bad.version++; CHECK(!Plug_NativeUI_ModelRegister(&bad,sizeof(bad)));
	bad=extension; bad.capabilities=0; CHECK(!Plug_NativeUI_ModelRegister(&bad,sizeof(bad)));
	bad=extension; bad.capabilities=3; CHECK(!Plug_NativeUI_ModelRegister(&bad,sizeof(bad)));
	bad=extension; bad.SetModel=NULL; CHECK(!Plug_NativeUI_ModelRegister(&bad,sizeof(bad)));
	bad=extension; bad.PollModel=NULL; CHECK(!Plug_NativeUI_ModelRegister(&bad,sizeof(bad)));
	currentplug=&plugins[1]; CHECK(!Plug_NativeUI_ModelRegister(&extension,sizeof(extension)));
	currentplug=&plugins[0]; CHECK(Plug_NativeUI_ModelRegister(&extension,sizeof(extension)));
	CHECK(!Plug_NativeUI_ModelRegister(&extension,sizeof(extension)));
	extension.SetModel=NULL; CHECK(Call(PF_ui_native_model_status,&menu,0));
	Plug_NativeUI_Begin(&menu,1); h=Call(PF_ui_native_open,&menu,103); CHECK(h>0);
	Plug_NativeUI_End(&menu); CHECK(!Begin(&menu,h,1,1));
	Plug_NativeUI_Begin(&menu,1); CHECK(!Begin(&foreign,h,1,1) && !Begin(&client,h,1,1));
	CHECK(!Begin(&menu,h+.5f,1,1) && !Begin(&menu,NAN,1,1));
	for (n=0;n<countof(invalidcount);n++) CHECK(!Begin(&menu,h,1,invalidcount[n]));
	for (n=0;n<countof(invalidid);n++) CHECK(!Begin(&menu,h,invalidid[n],1));
	CHECK(Begin(&menu,h,1,2)); CHECK(Widget(h,0,11,91,2,0,"button"));
	CHECK(!Call(PF_ui_native_model_commit,&menu,h) && !models); //incomplete never publishes
	CHECK(Begin(&menu,h,1,1)); CHECK(!Widget(h,1,11,91,2,0,"out of order"));
	CHECK(!Widget(h,0,11,91,2,0,"poisoned")); CHECK(!Call(PF_ui_native_model_commit,&menu,h));
	CHECK(Begin(&menu,h,1,2)); CHECK(Widget(h,0,11,91,2,0,"button"));
	CHECK(!Widget(h,1,11,92,2,0,"duplicate")); CHECK(!Call(PF_ui_native_model_commit,&menu,h));
	for (n=0;n<countof(invalidid);n++)
	{
		CHECK(Begin(&menu,h,1,1)); CHECK(!Widget(h,0,invalidid[n],91,2,0,"bad id"));
		CHECK(!Call(PF_ui_native_model_commit,&menu,h));
		CHECK(Begin(&menu,h,1,1)); CHECK(!Widget(h,0,11,invalidid[n],2,0,"bad row"));
	}
	for (n=0;n<countof(invalidlabel);n++)
	{
		CHECK(Begin(&menu,h,1,1)); CHECK(!Widget(h,0,11,91,2,0,invalidlabel[n]));
		CHECK(!Call(PF_ui_native_model_commit,&menu,h));
	}
	memset(label,'x',sizeof(label)); label[96]=0;
	CHECK(Begin(&menu,h,1,1)); CHECK(!Widget(h,0,11,91,2,0,label));
	label[95]=0; CHECK(Begin(&menu,h,1,1)); CHECK(Widget(h,0,11,91,2,0,label));
	label[0]='z'; CHECK(Call(PF_ui_native_model_commit,&menu,h));
	CHECK(copied.widgets[0].label[0]=='x' && copied.revision==1 && models==1);
	CHECK(!Begin(&menu,h,1,1)); CHECK(!Begin(&menu,h,0,1));
	CHECK(Begin(&menu,h,2,1)); CHECK(!Widget(h,0,11,91,4,0,"type"));
	CHECK(Begin(&menu,h,2,1)); CHECK(!Widget(h,0,11,91,2,1,"value"));
	CHECK(Begin(&menu,h,2,1)); CHECK(!Widget(h,0,11,91,3,NAN,"value"));
	Publish(h,2); CHECK(!ModelPollCall(&menu,h,2) && !modelpolls);
	CHECK(Call(PF_ui_native_draw,&menu,h)); modelaction=1;
	before=modelpolls; CHECK(!ModelPollCall(&menu,h,1) && modelpolls==before);
	CHECK(!ModelPollCall(&client,h,2) && !ModelPollCall(&foreign,h,2));
	CHECK(ModelPollCall(&menu,h,2)==11 && globals.value[1]==91 && globals.value[2]==1);
	Publish(h,3); before=modelpolls;
	CHECK(!ModelPollCall(&menu,h,3) && modelpolls==before); //publish revokes draw authority
	host_framecount++; CHECK(Call(PF_ui_native_draw,&menu,h));
	for (n=0;n<PLUGUI_INPUT_MAX_ACTIONS;n++) CHECK(ModelPollCall(&menu,h,3)==11);
	before=modelpolls; CHECK(!ModelPollCall(&menu,h,3) && modelpolls==before);
	for (modelaction=2;modelaction<=9;modelaction++)
	{
		host_framecount++; h=Call(PF_ui_native_open,&menu,103);
		if (plugui_vms[0].model.revision==3) Publish(h,4); else Publish(h,1);
		CHECK(Call(PF_ui_native_draw,&menu,h)); close_before=closes;
		CHECK(!ModelPollCall(&menu,h,copied.revision) && !globals.value[1] && !globals.value[2]);
		CHECK(closes==close_before+1 && !Call(PF_ui_native_close,&menu,h));
	}
	modelaction=0; host_framecount++; h=Call(PF_ui_native_open,&menu,103);
	CHECK(Begin(&menu,h,1,PLUGUI_MODEL_MAX_WIDGETS));
	for (n=0;n<PLUGUI_MODEL_MAX_WIDGETS;n++) CHECK(Widget(h,n,n+1,n+1,1,0,"bounded"));
	CHECK(Call(PF_ui_native_model_commit,&menu,h) && copied.count==64);
	CHECK(Begin(&menu,h,2,0)); CHECK(Call(PF_ui_native_model_commit,&menu,h) && !copied.count);
	modelfail=1; CHECK(Begin(&menu,h,3,0)); close_before=closes;
	CHECK(!Call(PF_ui_native_model_commit,&menu,h) && closes==close_before+1); modelfail=0;
	old=h; h=Call(PF_ui_native_open,&menu,103); CHECK(h>old && !Begin(&menu,old,1,0));
	Plug_NativeUI_Begin(&client,2); c=Call(PF_ui_native_open,&client,204);
	CHECK(!Begin(&client,h,1,0) && Begin(&client,c,1,0));
	CHECK(Call(PF_ui_native_model_commit,&client,c));
	Plug_NativeUI_Release(&menu); CHECK(!Begin(&menu,h,1,0));
	Plug_NativeUI_PluginClose(&plugins[0]); CHECK(!Call(PF_ui_native_model_status,&client,0));
	CHECK(opens==closes);
	printf("P601 model bridge: %u checks, %u failed, published=%u polls=%u\n",checks-start,errors,models,modelpolls);
	return errors ? 1 : 0;
}
