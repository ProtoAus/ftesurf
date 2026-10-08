#define main PassiveControls
#include "p590bridge_host.c"
#undef main
static unsigned int inputs, polls;
static int inputfail, actionmode;
static float InputCall(pubprogfuncs_t *vm, float handle, float type, float a, float b)
{
	globals.value[OFS_PARM1]=type; globals.value[OFS_PARM2]=a; globals.value[OFS_PARM3]=b;
	return Call(PF_ui_native_input,vm,handle);
}
static qboolean QDECL Input(const pluguiowner_t *o, const pluguiinputevent_t *e)
{
	float clip[4]={0,0,640,480};
	inputs++; CHECK(o->generation && e->structsize==sizeof(*e));
	CHECK(currentplug==plugui_service && !Plug_NativeUI_Ready() && !Plug_NativeUI_Clip(clip));
	CHECK(!Call(PF_ui_native_input_status,&menu,0));
	CHECK(!InputCall(&menu,o->generation,PLUGUI_INPUT_RESET,0,0));
	return !inputfail;
}
static qboolean QDECL Poll(const pluguiowner_t *o, pluguiaction_t *a)
{
	float clip[4]={0,0,640,480};
	polls++; CHECK(currentplug==plugui_service && !Plug_NativeUI_Clip(clip));
	CHECK(!Call(PF_ui_native_poll,&menu,o->generation));
	if (!actionmode) return false;
	a->id=7; a->generation=o->generation; a->value=42;
	if (actionmode==2) a->generation++;
	if (actionmode==3) a->id=0;
	if (actionmode==4) a->id=PLUGUI_MAXID+1;
	if (actionmode==5) a->value=NAN;
	if (actionmode==6) a->value=INFINITY;
	if (actionmode==7) a->value=1000001;
	return true;
}
int main(void)
{
	pluguiinputservice_t extension={sizeof(extension),PLUGUI_INPUT_VERSION,PLUGUI_INPUT_CAP_EVENTS,Input,Poll}, bad;
	pluguiservice_t service={sizeof(service),PLUGUI_VERSION,PLUGUI_CAP_INDEXED2D,Open,Draw,Close};
	float m,c,old;
	unsigned int start, before, close_before, n;
	const float invalid[][3]={{1,NAN,0},{1,0,INFINITY},{1,32769,0},{2,-1,0},{2,5,0},{2,.5f,1},
		{2,0,2},{3,11,0},{4,0,1},{4,PLUGUI_KEY_MAX+1,1},{4,1,.5f},
		{5,0,0},{5,55296,0},{5,57343,0},{5,1114112,0},{5,65.5f,0},{5,65,1},{6,1,0},{7,0,0},{1.5f,0,0}};
	if (PassiveControls()) return 1;
	start=checks; Plug_NativeUI_PluginClose(plugui_service); memset(plugui_vms,0,sizeof(plugui_vms));
	plugui_serial=0; host_framecount++; currentplug=&plugins[0];
	CHECK(!Plug_NativeUI_InputRegister(&extension,sizeof(extension)));
	CHECK(Plug_NativeUI_Register(&service,sizeof(service)));
	CHECK(!Call(PF_ui_native_input_status,&menu,0));
	CHECK(!Plug_NativeUI_InputRegister(&extension,sizeof(extension)-1));
	CHECK(!Plug_NativeUI_InputRegister(&extension,sizeof(extension)+1));
	bad=extension; bad.structsize--; CHECK(!Plug_NativeUI_InputRegister(&bad,sizeof(bad)));
	bad=extension; bad.version++; CHECK(!Plug_NativeUI_InputRegister(&bad,sizeof(bad)));
	bad=extension; bad.capabilities=0; CHECK(!Plug_NativeUI_InputRegister(&bad,sizeof(bad)));
	bad=extension; bad.capabilities=3; CHECK(!Plug_NativeUI_InputRegister(&bad,sizeof(bad)));
	bad=extension; bad.Input=NULL; CHECK(!Plug_NativeUI_InputRegister(&bad,sizeof(bad)));
	bad=extension; bad.Poll=NULL; CHECK(!Plug_NativeUI_InputRegister(&bad,sizeof(bad)));
	currentplug=&plugins[1]; CHECK(!Plug_NativeUI_InputRegister(&extension,sizeof(extension)));
	currentplug=&plugins[0]; CHECK(Plug_NativeUI_InputRegister(&extension,sizeof(extension)));
	CHECK(!Plug_NativeUI_InputRegister(&extension,sizeof(extension)));
	extension.Input=NULL; //host copied callbacks, not borrowed caller storage
	CHECK(Call(PF_ui_native_input_status,&menu,0)==1);
	Plug_NativeUI_Begin(&menu,1); m=Call(PF_ui_native_open,&menu,103); CHECK(m>0);
	CHECK(!Call(PF_ui_native_poll,&menu,m) && !polls);
	before=inputs;
	for (n=0;n<countof(invalid);n++) CHECK(!InputCall(&menu,m,invalid[n][0],invalid[n][1],invalid[n][2]));
	CHECK(!InputCall(&foreign,m,1,10,10) && !InputCall(&client,m,1,10,10));
	CHECK(!InputCall(&menu,m+.5f,1,10,10) && !InputCall(&menu,NAN,1,10,10));
	CHECK(inputs==before); before=flushes;
	CHECK(InputCall(&menu,m,1,10,10)==1 && flushes==before);
	CHECK(currentplug==&plugins[0]);
	Plug_NativeUI_End(&menu);
	CHECK(InputCall(&menu,m,2,0,1)==1); //explicit caller handle, outside draw input callback
	CHECK(!Call(PF_ui_native_poll,&menu,m) && !polls);
	Plug_NativeUI_Begin(&menu,1); CHECK(Call(PF_ui_native_draw,&menu,m));
	CHECK(!Call(PF_ui_native_poll,&menu,m) && polls==1);
	actionmode=1; CHECK(Call(PF_ui_native_poll,&menu,m)==7);
	CHECK(globals.value[1]==m && globals.value[2]==42);
	CHECK(!Call(PF_ui_native_poll,&foreign,m) && !Call(PF_ui_native_poll,&client,m));
	for (n=2;n<PLUGUI_INPUT_MAX_ACTIONS;n++) CHECK(Call(PF_ui_native_poll,&menu,m)==7);
	before=polls; CHECK(!Call(PF_ui_native_poll,&menu,m) && polls==before);
	Plug_NativeUI_End(&menu); CHECK(!Call(PF_ui_native_poll,&menu,m));
	host_framecount++; Plug_NativeUI_Begin(&menu,1); CHECK(!Call(PF_ui_native_poll,&menu,m));
	CHECK(Call(PF_ui_native_draw,&menu,m)); CHECK(Call(PF_ui_native_poll,&menu,m)==7);
	//Malformed plugin results invalidate once, no partial vector values.
	for (actionmode=2;actionmode<=7;actionmode++)
	{
		host_framecount++; m=Call(PF_ui_native_open,&menu,103); CHECK(Call(PF_ui_native_draw,&menu,m));
		close_before=closes; CHECK(!Call(PF_ui_native_poll,&menu,m));
		CHECK(!globals.value[1] && !globals.value[2] && closes==close_before+1);
		CHECK(!Call(PF_ui_native_close,&menu,m));
	}
	actionmode=1; host_framecount++; m=Call(PF_ui_native_open,&menu,103); inputfail=1; close_before=closes;
	CHECK(!InputCall(&menu,m,1,0,0) && closes==close_before+1); inputfail=0;
	old=m; m=Call(PF_ui_native_open,&menu,103); CHECK(m>old && !InputCall(&menu,old,1,0,0));
	host_framecount++;
	for (n=0;n<PLUGUI_INPUT_MAX_EVENTS;n++) CHECK(InputCall(&menu,m,1,(float)n,0));
	CHECK(InputCall(&menu,m,PLUGUI_INPUT_RESET,0,0)); //reset cannot be starved by flood
	before=inputs; close_before=closes;
	CHECK(!InputCall(&menu,m,1,0,0) && inputs==before && closes==close_before+1);
	m=Call(PF_ui_native_open,&menu,103); close_before=closes;
	CHECK(!InputCall(&menu,m,1,0,0) && inputs==before && closes==close_before+1); //reopen does not bypass host budget
	host_framecount++; m=Call(PF_ui_native_open,&menu,103); CHECK(InputCall(&menu,m,1,0,0));
	Plug_NativeUI_End(&menu); Plug_NativeUI_Begin(&client,2); c=Call(PF_ui_native_open,&client,204);
	CHECK(c>m && InputCall(&client,c,1,5,5));
	CHECK(!InputCall(&client,m,1,5,5) && !InputCall(&menu,c,1,5,5));
	Plug_NativeUI_Release(&menu); CHECK(!InputCall(&menu,m,1,0,0));
	CHECK(InputCall(&client,c,1,5,5));
	Plug_NativeUI_RendererShutdown(); CHECK(!InputCall(&client,c,1,5,5));
	Plug_NativeUI_PluginClose(&plugins[0]); CHECK(!Call(PF_ui_native_input_status,&client,0));
	currentplug=&plugins[1]; CHECK(Plug_NativeUI_Register(&service,sizeof(service)));
	CHECK(!Call(PF_ui_native_input_status,&client,0));
	Plug_NativeUI_PluginClose(&plugins[1]); CHECK(opens==closes);
	printf("P599 bridge: %u checks, %u failed, input callbacks=%u polls=%u\n",checks-start,errors,inputs,polls);
	return errors ? 1 : 0;
}
