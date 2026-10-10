#define P601_MAIN Model1Controls
#include "p601model_host.c"
static pluguimodel2_t copied2;
static unsigned int densemodels, densepolls;
static qboolean QDECL DenseSet(const pluguiowner_t *o,const pluguimodel2_t *m)
{
	densemodels++; CHECK(PlugUI_Model2Valid(m) && o->generation);
	CHECK(!Plug_NativeUI_ModelReady() && !Call(PF_ui_native_model_limit,&menu,0));
	CHECK(!Call(PF_ui_native_model_commit,&menu,o->generation));
	copied2=*m; return !modelfail;
}
static qboolean QDECL DensePoll(const pluguiowner_t *o,pluguimodelaction_t *a)
{
	densepolls++; CHECK(!Plug_NativeUI_ModelReady());
	if (!modelaction) return false;
	*a=(pluguimodelaction_t){256,256,o->generation,copied2.revision,1};
	if (modelaction==2) a->revision--;
	return true;
}
int main(void)
{
	pluguiservice_t service={sizeof(service),PLUGUI_VERSION,PLUGUI_CAP_INDEXED2D,Open,Draw,Close};
	pluguiinputservice_t input={sizeof(input),PLUGUI_INPUT_VERSION,PLUGUI_INPUT_CAP_EVENTS,Input,Poll};
	pluguimodelservice_t prior={sizeof(prior),PLUGUI_MODEL_VERSION,PLUGUI_MODEL_CAP_WIDGETS,ModelSet,ModelPoll};
	pluguimodelservice2_t dense={sizeof(dense),PLUGUI_MODEL2_VERSION,PLUGUI_MODEL_CAP_WIDGETS,DenseSet,DensePoll},bad;
	unsigned int start,n,before; float h;
	if (Model1Controls()) return 1;
	start=checks; currentplug=&plugins[0]; memset(plugui_vms,0,sizeof(plugui_vms));
	CHECK(!Call(PF_ui_native_model_limit,&menu,0));
	CHECK(!Plug_NativeUI_ModelRegister2(&dense,sizeof(dense)));
	CHECK(Plug_NativeUI_Register(&service,sizeof(service)));
	CHECK(Plug_NativeUI_InputRegister(&input,sizeof(input)));
	CHECK(!Plug_NativeUI_ModelRegister2(&dense,sizeof(dense)));
	CHECK(Plug_NativeUI_ModelRegister(&prior,sizeof(prior)));
	CHECK(Call(PF_ui_native_model_limit,&menu,0)==64);
	CHECK(!Plug_NativeUI_ModelRegister2(NULL,sizeof(dense)));
	CHECK(!Plug_NativeUI_ModelRegister2(&dense,sizeof(dense)-1));
	CHECK(!Plug_NativeUI_ModelRegister2(&dense,sizeof(dense)+1));
	bad=dense; bad.structsize--; CHECK(!Plug_NativeUI_ModelRegister2(&bad,sizeof(bad)));
	bad=dense; bad.version=1; CHECK(!Plug_NativeUI_ModelRegister2(&bad,sizeof(bad)));
	bad=dense; bad.capabilities=0; CHECK(!Plug_NativeUI_ModelRegister2(&bad,sizeof(bad)));
	bad=dense; bad.capabilities=3; CHECK(!Plug_NativeUI_ModelRegister2(&bad,sizeof(bad)));
	bad=dense; bad.SetModel=NULL; CHECK(!Plug_NativeUI_ModelRegister2(&bad,sizeof(bad)));
	bad=dense; bad.PollModel=NULL; CHECK(!Plug_NativeUI_ModelRegister2(&bad,sizeof(bad)));
	currentplug=&plugins[1]; CHECK(!Plug_NativeUI_ModelRegister2(&dense,sizeof(dense)));
	currentplug=&plugins[0]; CHECK(Plug_NativeUI_ModelRegister2(&dense,sizeof(dense)));
	CHECK(!Plug_NativeUI_ModelRegister2(&dense,sizeof(dense)));
	dense.SetModel=NULL; CHECK(Call(PF_ui_native_model_limit,&menu,0)==256);
	Plug_NativeUI_Begin(&menu,1); host_framecount++;
	h=Call(PF_ui_native_open,&menu,103); CHECK(h>0);
	CHECK(!Begin(&menu,h,1,257) && !Begin(&menu,h,1,NAN) && !Begin(&menu,h,1,255.5f));
	CHECK(Begin(&menu,h,1,256));
	for (n=0;n<256;n++) CHECK(Widget(h,n,n+1,n+1,2,0,"bounded UTF-8 \xc3\xa9"));
	CHECK(Call(PF_ui_native_model_commit,&menu,h) && densemodels==1 && copied2.count==256 && models==15);
	CHECK(!ModelPollCall(&menu,h,1) && !densepolls);
	CHECK(Call(PF_ui_native_draw,&menu,h)); modelaction=1;
	CHECK(ModelPollCall(&menu,h,1)==256 && globals.value[1]==256 && globals.value[2]==1 && densepolls==1);
	CHECK(Begin(&menu,h,2,256)); CHECK(Widget(h,0,1,1,2,0,"incomplete"));
	CHECK(!Call(PF_ui_native_model_commit,&menu,h) && densemodels==1 && plugui_vms[0].model.revision==1);
	CHECK(Begin(&menu,h,2,2)); CHECK(Widget(h,0,1,1,2,0,"duplicate"));
	CHECK(!Widget(h,1,1,2,2,0,"duplicate") && !Call(PF_ui_native_model_commit,&menu,h));
	CHECK(Begin(&menu,h,2,1)); CHECK(!Widget(h,0,1,1,2,0,"\xed\xa0\x80"));
	CHECK(!Call(PF_ui_native_model_commit,&menu,h) && plugui_vms[0].model.count==256);
	CHECK(Begin(&menu,h,2,0)); CHECK(Call(PF_ui_native_model_commit,&menu,h));
	before=densepolls; CHECK(!ModelPollCall(&menu,h,1) && densepolls==before);
	CHECK(Begin(&menu,h,3,256));
	for (n=0;n<256;n++) CHECK(Widget(h,n,n+1,n+1,2,0,"restored"));
	CHECK(Call(PF_ui_native_model_commit,&menu,h)); host_framecount++;
	CHECK(Call(PF_ui_native_draw,&menu,h)); modelaction=2; before=closes;
	CHECK(!ModelPollCall(&menu,h,3) && closes==before+1);
	modelaction=0; h=Call(PF_ui_native_open,&menu,103); modelfail=1;
	CHECK(Begin(&menu,h,1,0)); before=closes;
	CHECK(!Call(PF_ui_native_model_commit,&menu,h) && closes==before+1); modelfail=0;
	//Open attempts are budgeted per VM per frame; asking again for the live owner is free.
	host_framecount++; before=opens;
	for (n=0;n<PLUGUI_MAX_OPENS;n++) { h=Call(PF_ui_native_open,&menu,103); CHECK(h>0); CHECK(Call(PF_ui_native_close,&menu,h)); }
	CHECK(!Call(PF_ui_native_open,&menu,103) && opens==before+PLUGUI_MAX_OPENS);
	host_framecount++; h=Call(PF_ui_native_open,&menu,103); CHECK(h>0 && opens==before+PLUGUI_MAX_OPENS+1);
	CHECK(Call(PF_ui_native_open,&menu,103)==h && opens==before+PLUGUI_MAX_OPENS+1);
	CHECK(Call(PF_ui_native_close,&menu,h));
	Plug_NativeUI_PluginClose(&plugins[0]); CHECK(!Call(PF_ui_native_model_limit,&menu,0));
	CHECK(!plugui_model2.SetModel && opens==closes);
	printf("P603 DENSE BUDGET model1=%zu model2=%zu widget=%zu vm_snapshots=%zu\n",
		sizeof(pluguimodel_t),sizeof(pluguimodel2_t),sizeof(pluguiwidget_t),
		2*(sizeof(plugui_vms)/sizeof(plugui_vms[0]))*sizeof(pluguimodel2_t));
	printf("P603 DENSE BRIDGE checks=%u failed=%u publishes=%u polls=%u\n",checks-start,errors,densemodels,densepolls);
	return errors ? 1 : 0;
}
