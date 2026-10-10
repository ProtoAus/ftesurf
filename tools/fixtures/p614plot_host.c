//Patch 614: the engine's real NativeUIPlot/1 bridge (cl_plugin_ui_plot.inc) against a small VM
//and a provider that checks what it is handed. Every refusal is preceded by the same call
//succeeding, so none can pass for the wrong reason. tools/test_p614plot_unit.py builds and runs it.
#define main PassiveControls
#include "p590bridge_host.c"
#undef main
static qboolean QDECL Input(const pluguiowner_t *o, const pluguiinputevent_t *e)
{ (void)o; (void)e; return true; }
static qboolean QDECL Poll(const pluguiowner_t *o, pluguiaction_t *a)
{ (void)o; (void)a; return false; }

#define XS 1000u        //float index of the VM's time rows
#define AS 67000u       //...and of its value rows; both hold PLUGUI_PLOT_MAX_POINTS
#define KS 133000u      //break flags: one set, 7000 floats of room
#define QC(i) ((int)((i)*4u))
static unsigned int plots, views;
static int plotfail, viewfail;
static pluguiplot_t got;            //the last revision's header
static float gx[8], ga[8], gb[8], glastx;
static unsigned char gk[8];
static pluguiplotview_t gotview;
static int Lent(const void *p) //host memory, not the VM's
{ return (const unsigned char *)p < vmmem.b || (const unsigned char *)p >= vmmem.b+sizeof(vmmem); }
static qboolean QDECL PlotSet(const pluguiowner_t *o, const pluguiplot_t *p)
{
	unsigned int i, n;
	plots++;
	CHECK(o->generation && PlugUI_PlotValid(p));
	CHECK(currentplug==plugui_service && !Plug_NativeUI_PlotReady());
	CHECK(!Call(PF_ui_native_plot_commit,&client,o->generation)); //no nested staging
	CHECK(!p->points || (Lent(p->x) && Lent(p->a) && Lent(p->b) && Lent(p->brk)));
	if (plotfail) return false;
	got=*p; got.x=got.a=got.b=NULL; got.brk=NULL;
	n=min(p->points,8u);
	for (i=0;i<n;i++) { gx[i]=p->x[i]; ga[i]=p->a[i]; gb[i]=p->b[i]; gk[i]=p->brk[i]; }
	glastx=p->points ? p->x[p->points-1] : -1;
	return true;
}
static qboolean QDECL ViewSet(const pluguiowner_t *o, const pluguiplotview_t *v)
{
	views++;
	CHECK(o->generation && PlugUI_PlotViewValid(v));
	CHECK(currentplug==plugui_service && !Plug_NativeUI_PlotReady());
	if (viewfail) return false;
	gotview=*v;
	return true;
}
static void SetInt(int ofs,int v) { memcpy(&globals.value[ofs],&v,sizeof(v)); }
static float PBegin(pubprogfuncs_t *vm,float h,float revision,float count)
{
	globals.value[OFS_PARM1]=revision; globals.value[OFS_PARM2]=count;
	return Call(PF_ui_native_plot_begin,vm,h);
}
static float rgb[3]={0.5f,1,0};
static float PSeries(float h,float index,float flags,float gap)
{
	globals.value[OFS_PARM1]=index;
	globals.value[OFS_PARM2]=flags; globals.value[OFS_PARM2+1]=gap; globals.value[OFS_PARM2+2]=0;
	memcpy(&globals.value[OFS_PARM3],rgb,sizeof(rgb));
	return Call(PF_ui_native_plot_series,&client,h);
}
static float PRows(float h,float index,int x,int a,int b,int brk,float count,float xoffset)
{
	globals.value[OFS_PARM1]=index;
	SetInt(OFS_PARM2,x); SetInt(OFS_PARM3,a); SetInt(OFS_PARM4,b); SetInt(OFS_PARM5,brk);
	globals.value[OFS_PARM6]=count; globals.value[OFS_PARM7]=xoffset;
	return Call(PF_ui_native_plot_rows,&client,h);
}
static float mark[3]={12.5f,1,13}, masks[3]={0,0,0}, range[3]={0,0,0};
static float PView(float h)
{
	memcpy(&globals.value[OFS_PARM1],mark,sizeof(mark));
	memcpy(&globals.value[OFS_PARM2],masks,sizeof(masks));
	memcpy(&globals.value[OFS_PARM3],range,sizeof(range));
	return Call(PF_ui_native_plot_view,&client,h);
}
//A series header that is accepted, on a fresh transaction in a fresh frame: what each
//rows refusal below is measured against.
static float revision;
static void Fresh(float h,float flags)
{
	host_framecount++;
	CHECK(PBegin(&client,h,++revision,1));
	CHECK(PSeries(h,0,flags,0.25f));
}
static void Rows(void) //x ascending from 5 s, a rising, a break at row 3
{
	unsigned int i;
	memset(&vmmem,0,sizeof(vmmem));
	for (i=0;i<PLUGUI_PLOT_MAX_POINTS;i++) { vmmem.f[XS+i]=5+i*0.015f; vmmem.f[AS+i]=300+(i&1023); }
	vmmem.f[KS+3]=7; //any nonzero is a break
}
int main(void)
{
	pluguiservice_t service={sizeof(service),PLUGUI_VERSION,PLUGUI_CAP_INDEXED2D,Open,Draw,Close};
	pluguiinputservice_t input={sizeof(input),PLUGUI_INPUT_VERSION,PLUGUI_INPUT_CAP_EVENTS,Input,Poll};
	pluguiplotservice_t ext={sizeof(ext),PLUGUI_PLOT_VERSION,PLUGUI_PLOT_CAP_SERIES,PlotSet,ViewSet},bad;
	float h,old,m; unsigned int start,before,i,closed;
	const float notcount[]={-1,.5f,17,NAN,INFINITY};
	const float notrevision[]={0,-1,.5f,16777216,NAN,INFINITY};
	const float notgap[]={0,-1,NAN,INFINITY};
	const float notcolour[]={-0.01f,1.01f,NAN,INFINITY};
	const float notrows[]={0,-1,.5f,65537,NAN,INFINITY};
	if (PassiveControls()) return 1;
	Plug_NativeUI_PluginClose(plugui_service); memset(plugui_vms,0,sizeof(plugui_vms));
	start=checks; plugui_serial=0; host_framecount++; currentplug=&plugins[0];

	//Registration: after the drawing and input services of the same provider, exact, once.
	CHECK(!Plug_NativeUI_PlotRegister(&ext,sizeof(ext)));
	CHECK(Plug_NativeUI_Register(&service,sizeof(service)));
	CHECK(!Plug_NativeUI_PlotRegister(&ext,sizeof(ext)));
	CHECK(Plug_NativeUI_InputRegister(&input,sizeof(input)));
	CHECK(!Call(PF_ui_native_plot_status,&client,0));
	CHECK(!Plug_NativeUI_PlotRegister(NULL,sizeof(ext)));
	CHECK(!Plug_NativeUI_PlotRegister(&ext,sizeof(ext)-1));
	CHECK(!Plug_NativeUI_PlotRegister(&ext,sizeof(ext)+1));
	bad=ext; bad.structsize--; CHECK(!Plug_NativeUI_PlotRegister(&bad,sizeof(bad)));
	bad=ext; bad.version++; CHECK(!Plug_NativeUI_PlotRegister(&bad,sizeof(bad)));
	bad=ext; bad.capabilities=0; CHECK(!Plug_NativeUI_PlotRegister(&bad,sizeof(bad)));
	bad=ext; bad.SetPlot=NULL; CHECK(!Plug_NativeUI_PlotRegister(&bad,sizeof(bad)));
	bad=ext; bad.SetView=NULL; CHECK(!Plug_NativeUI_PlotRegister(&bad,sizeof(bad)));
	currentplug=&plugins[1]; CHECK(!Plug_NativeUI_PlotRegister(&ext,sizeof(ext))); currentplug=&plugins[0];
	CHECK(Plug_NativeUI_PlotRegister(&ext,sizeof(ext)));
	CHECK(!Plug_NativeUI_PlotRegister(&ext,sizeof(ext)));
	CHECK(Call(PF_ui_native_plot_status,&client,0)==1);

	//Staging belongs to a live owner inside its VM's draw bracket.
	Rows();
	Plug_NativeUI_Begin(&client,2); h=Call(PF_ui_native_open,&client,206); CHECK(h>0);
	CHECK(!PView(h));                                           //nothing published yet
	Plug_NativeUI_End(&client); CHECK(!PBegin(&client,h,1,1));
	Plug_NativeUI_Begin(&client,2);
	CHECK(!PBegin(&menu,h,1,1) && !PBegin(&client,h+1,1,1) && !PBegin(&client,0,1,1));

	//The good revision: a series with a second value, breaks and the marker; one without.
	CHECK(PBegin(&client,h,1,2));
	CHECK(PSeries(h,0,PLUGUI_PLOT_HAS_B|PLUGUI_PLOT_MARKED,0.25f));
	CHECK(PRows(h,0,QC(XS),QC(AS),QC(AS+100),QC(KS),5,5));
	CHECK(PSeries(h,1,0,0.5f));
	CHECK(PRows(h,1,QC(XS+10),QC(AS+10),0,0,3,0));
	before=plots; CHECK(Call(PF_ui_native_plot_commit,&client,h)==1 && plots==before+1);
	CHECK(got.revision==1 && got.count==2 && got.points==8);
	CHECK(got.series[0].first==0 && got.series[0].count==5 && got.series[0].flags==3 && got.series[0].gap==0.25f);
	CHECK(got.series[1].first==5 && got.series[1].count==3 && got.series[1].flags==0 && got.series[1].rgb[1]==1);
	CHECK(gx[0]==0 && gx[4]==vmmem.f[XS+4]-5 && ga[2]==302 && gb[2]==vmmem.f[AS+102]); //x less its offset
	CHECK(gk[0]==0 && gk[3]==1 && gk[4]==0);                    //any nonzero flag is 1
	CHECK(gx[5]==vmmem.f[XS+10] && gb[5]==0 && gb[7]==0 && gk[5]==0 && glastx==vmmem.f[XS+12]); //no b, no breaks: zeros
	CHECK(!Call(PF_ui_native_plot_commit,&client,h) && plots==before+1); //a transaction commits once
	revision=1;

	//The view: accepted with a plot, every field through.
	masks[0]=5; masks[1]=2; range[0]=9; range[1]=18; range[2]=30;
	before=views; CHECK(PView(h)==1 && views==before+1);
	CHECK(gotview.hidden==5 && gotview.emphasis==2 && gotview.marked==1 && gotview.mark==12.5f);
	CHECK(gotview.textpx==13 && gotview.rangeserial==9 && gotview.x0==18 && gotview.x1==30);
	before=views;
	mark[1]=2; CHECK(!PView(h)); mark[1]=.5f; CHECK(!PView(h)); mark[1]=1;
	mark[0]=NAN; CHECK(!PView(h)); mark[0]=INFINITY; CHECK(!PView(h)); mark[0]=12.5f;
	mark[2]=0; CHECK(!PView(h)); mark[2]=257; CHECK(!PView(h)); mark[2]=NAN; CHECK(!PView(h)); mark[2]=13;
	masks[0]=65536; CHECK(!PView(h)); masks[0]=-1; CHECK(!PView(h)); masks[0]=1.5f; CHECK(!PView(h)); masks[0]=5;
	masks[1]=65536; CHECK(!PView(h)); masks[1]=NAN; CHECK(!PView(h)); masks[1]=2;
	range[0]=-1; CHECK(!PView(h)); range[0]=16777216; CHECK(!PView(h)); range[0]=.5f; CHECK(!PView(h)); range[0]=9;
	range[1]=NAN; CHECK(!PView(h)); range[1]=18; range[2]=INFINITY; CHECK(!PView(h)); range[2]=30;
	mark[0]=2e9f; CHECK(!PView(h)); mark[0]=12.5f; range[1]=-2e9f; CHECK(!PView(h)); range[1]=18;
	range[2]=1e30f; CHECK(!PView(h)); range[2]=30;
	CHECK(views==before && PView(h)==1);                        //none reached the provider; the owner lives

	//begin: revisions only rise, counts are whole and bounded, two transactions a frame.
	for (i=0;i<countof(notrevision);i++) { host_framecount++; CHECK(!PBegin(&client,h,notrevision[i],1)); }
	host_framecount++; CHECK(!PBegin(&client,h,1,1));           //not above the published one
	for (i=0;i<countof(notcount);i++) { host_framecount++; CHECK(!PBegin(&client,h,2,notcount[i])); }
	host_framecount++;
	CHECK(PBegin(&client,h,2,1) && PBegin(&client,h,2,16) && !PBegin(&client,h,2,1)); //the third is over budget
	host_framecount++; CHECK(PBegin(&client,h,2,0));            //an empty plot is a plot
	before=plots; CHECK(Call(PF_ui_native_plot_commit,&client,h)==1 && plots==before+1 && got.count==0 && got.points==0);
	revision=2;

	//series: in order, known flags, a positive finite gap, a colour.
	host_framecount++; CHECK(PBegin(&client,h,++revision,2));
	CHECK(!PSeries(h,1,0,0.25f));                               //out of order...
	CHECK(!PSeries(h,0,0,0.25f) && !Call(PF_ui_native_plot_commit,&client,h)); //...and the transaction is spent
	host_framecount++; CHECK(PBegin(&client,h,++revision,1));
	CHECK(!PSeries(h,0,4,0.25f));
	host_framecount++; CHECK(PBegin(&client,h,++revision,1)); CHECK(!PSeries(h,0,.5f,0.25f));
	for (i=0;i<countof(notgap);i++)
	{ host_framecount++; CHECK(PBegin(&client,h,++revision,1)); CHECK(!PSeries(h,0,0,notgap[i])); }
	for (i=0;i<countof(notcolour);i++)
	{
		host_framecount++; CHECK(PBegin(&client,h,++revision,1));
		rgb[i%3]=notcolour[i]; CHECK(!PSeries(h,0,0,0.25f)); rgb[0]=0.5f; rgb[1]=1; rgb[2]=0;
	}
	host_framecount++; CHECK(PBegin(&client,h,++revision,2)); CHECK(PSeries(h,0,0,0.25f));
	CHECK(!PSeries(h,1,0,0.25f));                               //the first has no rows yet
	host_framecount++; CHECK(PBegin(&client,h,++revision,1)); CHECK(PSeries(h,0,0,0.25f));
	CHECK(PRows(h,0,QC(XS),QC(AS),0,0,2,0)); CHECK(!PSeries(h,1,0,0.25f)); //more than declared

	//rows: counts, pointers, order and finiteness. Fresh() proves the header was fine.
	for (i=0;i<countof(notrows);i++) { Fresh(h,0); CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,notrows[i],0)); }
	Fresh(h,0); CHECK(!PRows(h,1,QC(XS),QC(AS),0,0,2,0));       //not this series
	Fresh(h,0); CHECK(!PRows(h,0,0,QC(AS),0,0,2,0));            //null x
	Fresh(h,0); CHECK(!PRows(h,0,QC(XS),0,0,0,2,0));            //null a
	Fresh(h,0); CHECK(!PRows(h,0,-4,QC(AS),0,0,2,0));           //before the VM
	Fresh(h,0); CHECK(!PRows(h,0,(int)sizeof(vmmem)-8,QC(AS),0,0,2,0)); //its last byte is one past the rule
	Fresh(h,0); CHECK(PRows(h,0,(int)sizeof(vmmem)-9,QC(AS),0,0,2,0));  //the last address the VM allows, unaligned
	Fresh(h,0); CHECK(!PRows(h,0,QC(XS),(int)sizeof(vmmem)-4,0,0,2,0)); //a's second row is outside
	Fresh(h,0); CHECK(!PRows(h,0,0x7ffffff0,QC(AS),0,0,2,0));
	Fresh(h,0); CHECK(!PRows(h,0,QC(XS),QC(AS),0,(int)sizeof(vmmem)-4,2,0)); //breaks outside
	Fresh(h,0); memset(&vmmem,0,sizeof(vmmem));
	CHECK(PRows(h,0,QC(XS)+1,QC(AS)+3,0,0,2,0)); Rows();        //unaligned is read bytewise, never faulted on
	Fresh(h,0); CHECK(!PRows(h,0,QC(XS),QC(AS),QC(AS),0,2,0));  //a second value nobody declared
	Fresh(h,PLUGUI_PLOT_HAS_B); CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,2,0)); //and one declared and missing
	Fresh(h,PLUGUI_PLOT_HAS_B); CHECK(!PRows(h,0,QC(XS),QC(AS),(int)sizeof(vmmem)-4,0,2,0));
	Fresh(h,0); CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,2,NAN));
	Fresh(h,0); vmmem.f[XS+1]=4.9f; CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,3,0)); Rows(); //time runs backwards
	Fresh(h,0); vmmem.f[XS+1]=vmmem.f[XS]; CHECK(PRows(h,0,QC(XS),QC(AS),0,0,3,0)); Rows(); //standing still is allowed
	Fresh(h,0); vmmem.f[XS+2]=NAN; CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,3,0)); Rows();
	Fresh(h,0); vmmem.f[XS+2]=3e38f; CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,3,-3e38f)); Rows(); //the offset overflows it
	Fresh(h,0); vmmem.f[AS+1]=INFINITY; CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,3,0)); Rows();
	//A number is plotted, so it is bounded: a billion either way, x counted less its offset.
	Fresh(h,0); vmmem.f[AS+1]=1e9f; vmmem.f[AS+2]=-1e9f; CHECK(PRows(h,0,QC(XS),QC(AS),0,0,3,0)); Rows();
	Fresh(h,0); vmmem.f[AS+1]=1.5e9f; CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,3,0)); Rows();
	Fresh(h,0); vmmem.f[AS+2]=-3e30f; CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,3,0)); Rows();
	Fresh(h,PLUGUI_PLOT_HAS_B); vmmem.f[AS+101]=2e9f; CHECK(!PRows(h,0,QC(XS),QC(AS),QC(AS+100),0,3,0)); Rows();
	Fresh(h,0); CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,3,-2e9f));  //x itself small, its offset not
	Fresh(h,0); vmmem.f[XS]=3e9f; vmmem.f[XS+1]=3e9f; vmmem.f[XS+2]=3e9f+512; CHECK(PRows(h,0,QC(XS),QC(AS),0,0,3,3e9f)); Rows(); //a late clock, a short run
	host_framecount++; CHECK(PBegin(&client,h,++revision,1)); CHECK(!PSeries(h,0,0,2e9f));
	Fresh(h,PLUGUI_PLOT_HAS_B); vmmem.f[AS+101]=NAN; CHECK(!PRows(h,0,QC(XS),QC(AS),QC(AS+100),0,3,0)); Rows();
	Fresh(h,0); vmmem.f[KS+1]=NAN; CHECK(!PRows(h,0,QC(XS),QC(AS),0,QC(KS),3,0)); Rows();
	Fresh(h,0); CHECK(PRows(h,0,QC(XS),QC(AS),0,0,2,0)); CHECK(!PRows(h,0,QC(XS),QC(AS),0,0,2,0)); //rows once
	CHECK(!Call(PF_ui_native_plot_commit,&client,h));           //and that spent it
	host_framecount++; CHECK(PBegin(&client,h,++revision,2)); CHECK(PSeries(h,0,0,0.25f));
	CHECK(PRows(h,0,QC(XS),QC(AS),0,0,2,0)); CHECK(!Call(PF_ui_native_plot_commit,&client,h)); //a series short
	Fresh(h,0); CHECK(!Call(PF_ui_native_plot_commit,&client,h)); //a series with no rows
	CHECK(plots==2);                                            //none of it reached the provider

	//Memory that will not come: refused, nothing lost, and the next one is whole.
	Plug_NativeUI_Release(&client); Plug_NativeUI_Begin(&client,2); host_framecount++;
	h=Call(PF_ui_native_open,&client,206); revision=0;
	for (i=1;i<=4;i++)
	{
		Fresh(h,PLUGUI_PLOT_HAS_B); allocfail=i;
		CHECK(!PRows(h,0,QC(XS),QC(AS),QC(AS),0,5000,0) && !allocfail);
	}
	Fresh(h,PLUGUI_PLOT_HAS_B); CHECK(PRows(h,0,QC(XS),QC(AS),QC(AS),QC(KS),5000,5));
	before=plots; CHECK(Call(PF_ui_native_plot_commit,&client,h)==1 && plots==before+1);
	CHECK(got.points==5000 && gx[0]==0 && ga[1]==301 && gb[1]==301 && gk[3]==1);

	//The whole allowance: nine full series, and not a row more.
	host_framecount++; CHECK(PBegin(&client,h,++revision,10));
	for (i=0;i<9;i++)
	{
		CHECK(PSeries(h,i,0,0.25f));
		CHECK(PRows(h,i,QC(XS),QC(AS),0,0,PLUGUI_PLOT_MAX_POINTS,0));
	}
	CHECK(PSeries(h,9,0,0.25f)); CHECK(!PRows(h,9,QC(XS),QC(AS),0,0,1,0));
	host_framecount++; CHECK(PBegin(&client,h,++revision,9));
	for (i=0;i<9;i++)
	{
		CHECK(PSeries(h,i,0,0.25f));
		CHECK(PRows(h,i,QC(XS),QC(AS),0,0,PLUGUI_PLOT_MAX_POINTS,0));
	}
	before=plots; CHECK(Call(PF_ui_native_plot_commit,&client,h)==1 && plots==before+1);
	CHECK(got.points==PLUGUI_PLOT_MAX_TOTAL && got.series[8].first==8u*PLUGUI_PLOT_MAX_POINTS);
	CHECK(glastx==vmmem.f[XS+PLUGUI_PLOT_MAX_POINTS-1]);

	//A provider that refuses a revision or a view loses the owner, once; a new owner starts over.
	Fresh(h,0); CHECK(PRows(h,0,QC(XS),QC(AS),0,0,2,0));
	plotfail=1; closed=closes; CHECK(!Call(PF_ui_native_plot_commit,&client,h) && closes==closed+1); plotfail=0;
	CHECK(!PView(h) && !PBegin(&client,h,99,1));
	host_framecount++; old=h; h=Call(PF_ui_native_open,&client,206); CHECK(h>old);
	CHECK(!PView(h));                                           //the new owner has no plot
	revision=0; Fresh(h,0); CHECK(PRows(h,0,QC(XS),QC(AS),0,0,2,0));
	CHECK(Call(PF_ui_native_plot_commit,&client,h)==1 && got.revision==1); //revisions restart with it
	viewfail=1; closed=closes; CHECK(!PView(h) && closes==closed+1); viewfail=0;
	CHECK(!PView(h));

	//The other VM's owner is its own; a VM torn down mid-transaction takes its rows with it.
	host_framecount++; h=Call(PF_ui_native_open,&client,206); revision=0;
	Plug_NativeUI_Begin(&menu,1); m=Call(PF_ui_native_open,&menu,103);
	CHECK(!PBegin(&menu,h,1,1) && PBegin(&menu,m,1,0) && Call(PF_ui_native_plot_commit,&menu,m)==1);
	Fresh(h,0); CHECK(PRows(h,0,QC(XS),QC(AS),0,0,PLUGUI_PLOT_MAX_POINTS,0));
	Plug_NativeUI_Release(&client); CHECK(!plugui_vms[1].plotx && !plugui_vms[1].plotcap);
	CHECK(!Call(PF_ui_native_plot_commit,&client,h));
	Plug_NativeUI_PluginClose(&plugins[0]); CHECK(!Call(PF_ui_native_plot_status,&menu,0));
	CHECK(!plugui_vms[0].plotx && opens==closes);
	printf("P614 plot bridge: %u checks, %u failed, published=%u views=%u\n",checks-start,errors,plots,views);
	return errors ? 1 : 0;
}
