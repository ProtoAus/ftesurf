//Compile the real bridge implementation against deterministic host stubs.
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#define QDECL
#define QCBUILTIN
#define F(type,name,args) type (*name)args
#define true 1
#define false 0
typedef int qboolean;
typedef float vec4_t[4];
typedef struct pubprogfuncs_s { int id; } pubprogfuncs_t;
struct globalvars_s { float value[15]; };
#define G_FLOAT(ofs) (pr_globals->value[ofs])
#define G_VECTOR(ofs) (pr_globals->value+(ofs))
#define OFS_RETURN 0
#define OFS_PARM0 3
#define OFS_PARM1 6
#define OFS_PARM2 9
#define OFS_PARM3 12
#define OFS_PARM4 15
#define countof(a) (sizeof(a)/sizeof((a)[0]))
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
static int HostNonFinite(float f)
{
	uint32_t bits;
	memcpy(&bits,&f,sizeof(bits));
	return (bits & (255u<<23)) == (255u<<23); //same NaN/Inf bit predicate as FTE
}
#define IS_NAN(f) HostNonFinite(f)
#define Vector4Copy(a,b) memcpy((b),(a),sizeof(float)*4)
#include "ui_abi.h"
static const char *qclabel = "host label";
static const char *PR_GetStringOfs(pubprogfuncs_t *vm, unsigned int offset)
{ (void)vm; (void)offset; return qclabel; }
typedef struct plugin_s { pluguiservice_t nativeui; } plugin_t;
static plugin_t plugins[2], *currentplug;
static struct { int width,height,pixelwidth,pixelheight; } vid = {320,240,640,480};
static struct { struct { char texname[16]; } rt_destcolour[1]; } r_refdef;
static int qrenderer = 1, host_framecount;
#define QR_NONE 0
static void *BE_DrawMesh_Single = (void *)1;
typedef struct { float x,y,width,height,dmin,dmax; } srect_t;
static float imagecolour[4];
unsigned int r2d_be_flags;
static srect_t backendclip;
static qboolean backclipped;
static unsigned int flushes;
static void Flush(void) { flushes++; }
static void (*R2D_Flush)(void) = Flush;
static void R2D_GetImageColours(float *rgba) { Vector4Copy(imagecolour,rgba); }
static void R2D_ImageColours(float r,float g,float b,float a)
{ imagecolour[0]=r; imagecolour[1]=g; imagecolour[2]=b; imagecolour[3]=a; }
static void BE_Scissor(const srect_t *r) { backclipped = !!r; if(r) backendclip=*r; }
#include "cl_plugin_ui.inc"

static unsigned int checks, errors, opens, draws, closes, reasons[6];
static int failopen, faildraw;
static pubprogfuncs_t menu = {1}, client = {2}, foreign = {3};
static struct globalvars_s globals;
static pluguiframe_t captured;
#define CHECK(x) do { checks++; if (!(x)) { errors++; fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); } } while(0)
static float Call(void (*fn)(pubprogfuncs_t *,struct globalvars_s *),pubprogfuncs_t *vm,float arg)
{ globals.value[0]=-999; globals.value[OFS_PARM0]=arg; fn(vm,&globals); return globals.value[0]; }
static qboolean QDECL Open(const pluguiowner_t *o)
{
	opens++;
	CHECK(o->generation && o->owner && (o->vm==1 || o->vm==2));
	CHECK(!Plug_NativeUI_Ready());
	return !failopen;
}
static qboolean QDECL Draw(const pluguiframe_t *f)
{
	float clip[4] = {0,0,640,480};
	srect_t wrong = {0,0,1,1,0,1};
	draws++; captured=*f;
	CHECK(f->structsize==sizeof(*f));
	CHECK(currentplug==plugui_service);
	CHECK(Plug_NativeUI_Clip(clip));
	CHECK(clip[0]==f->clip[0] && clip[1]==f->clip[1] && clip[2]==f->clip[2] && clip[3]==f->clip[3]);
	CHECK(!Call(PF_ui_native_open,&menu,101));
	CHECK(!Call(PF_ui_native_draw,&menu,f->owner.generation));
	CHECK(!Call(PF_ui_native_close,&menu,f->owner.generation));
	CHECK(!Call(PF_ui_native_status,&menu,0));
	//A nested draw bracket must not overwrite the caller's active clip/authority.
	Plug_NativeUI_Begin(&menu,1); Plug_NativeUI_SetClip(&menu,NULL); Plug_NativeUI_End(&menu);
	R2D_ImageColours(0,0,0,0); r2d_be_flags=999; BE_Scissor(&wrong);
	return !faildraw;
}
static void QDECL Close(const pluguiowner_t *o,unsigned int reason)
{
	closes++;
	CHECK(o->generation && reason>=1 && reason<=5);
	CHECK(!Plug_NativeUI_Ready());
	reasons[reason]++;
}
int main(void)
{
	pluguiservice_t service = {sizeof(service),PLUGUI_VERSION,PLUGUI_CAP_INDEXED2D,Open,Draw,Close}, bad;
	srect_t clip = {0.1875f,0.5f,0.28125f,0.25f,-99999,99999};
	float m,c,old,box[4]={0,0,640,480};
	unsigned int before, native_before, flush_before;
	float invalidclip[3] = {NAN,INFINITY,3.4e38f};
	unsigned int j;
	currentplug=&plugins[0];
	CHECK(!Plug_NativeUI_InputRegister(NULL,0));
	CHECK(!Plug_NativeUI_ModelRegister(NULL,0));
	CHECK(!Plug_NativeUI_Register(NULL,sizeof(service)));
	CHECK(!Plug_NativeUI_Register(&service,sizeof(service)-1));
	CHECK(!Plug_NativeUI_Register(&service,sizeof(service)+1));
	bad=service; bad.structsize--; CHECK(!Plug_NativeUI_Register(&bad,sizeof(bad)));
	bad=service; bad.version++; CHECK(!Plug_NativeUI_Register(&bad,sizeof(bad)));
	bad=service; bad.capabilities=0; CHECK(!Plug_NativeUI_Register(&bad,sizeof(bad)));
	bad=service; bad.capabilities=3; CHECK(!Plug_NativeUI_Register(&bad,sizeof(bad)));
	bad=service; bad.Open=NULL; CHECK(!Plug_NativeUI_Register(&bad,sizeof(bad)));
	bad=service; bad.Draw=NULL; CHECK(!Plug_NativeUI_Register(&bad,sizeof(bad)));
	bad=service; bad.Close=NULL; CHECK(!Plug_NativeUI_Register(&bad,sizeof(bad)));
	CHECK(Plug_NativeUI_Register(&service,sizeof(service)));
	CHECK(!Plug_NativeUI_Register(&service,sizeof(service)));
	CHECK(Call(PF_ui_native_status,&menu,0)==1);
	CHECK(!Call(PF_ui_native_open,&menu,101));
	CHECK(!Call(PF_ui_native_draw,&menu,1));
	CHECK(!Plug_NativeUI_Clip(box));
	Plug_NativeUI_Begin(&menu,1);
	CHECK(opens==0 && draws==0); //entry never automatically renders
	service.Open=NULL; //copied table, not borrowed caller storage
	CHECK(!Call(PF_ui_native_open,&menu,0));
	CHECK(!Call(PF_ui_native_open,&menu,-1));
	CHECK(!Call(PF_ui_native_open,&menu,0.5f));
	CHECK(!Call(PF_ui_native_open,&menu,NAN));
	CHECK(!Call(PF_ui_native_open,&menu,INFINITY));
	CHECK(!Call(PF_ui_native_open,&menu,16777216.0f));
	m=Call(PF_ui_native_open,&menu,101); CHECK(m>0 && opens==1);
	CHECK(Call(PF_ui_native_open,&menu,101)==m && opens==1);
	CHECK(!Call(PF_ui_native_open,&menu,102));
	CHECK(!Call(PF_ui_native_draw,&menu,m+0.5f));
	CHECK(!Call(PF_ui_native_close,&menu,m+0.5f));
	CHECK(!Call(PF_ui_native_draw,&foreign,m));
	Plug_NativeUI_SetClip(&menu,&clip); BE_Scissor(&clip);
	R2D_ImageColours(1,0.5f,0.25f,0.75f); r2d_be_flags=17;
	before=flushes;
	CHECK(Call(PF_ui_native_draw,&menu,m)==1);
	CHECK(flushes==before+2 && currentplug==&plugins[0]);
	CHECK(imagecolour[0]==1 && imagecolour[1]==0.5f && imagecolour[2]==0.25f && imagecolour[3]==0.75f);
	CHECK(r2d_be_flags==17 && backclipped && !memcmp(&backendclip,&clip,sizeof(clip)));
	CHECK(captured.owner.vm==1 && captured.owner.owner==101 && captured.owner.generation==(unsigned int)m);
	CHECK(captured.virtualwidth==320 && captured.virtualheight==240 && captured.pixelwidth==640 && captured.pixelheight==480);
	CHECK(captured.clip[0]==120 && captured.clip[1]==120 && captured.clip[2]==300 && captured.clip[3]==240);
	CHECK(!Call(PF_ui_native_draw,&menu,m) && draws==1);
	Plug_NativeUI_End(&menu); host_framecount++;
	CHECK(!Call(PF_ui_native_draw,&menu,m) && draws==1);
	Plug_NativeUI_Begin(&client,2); c=Call(PF_ui_native_open,&client,101);
	CHECK(c>m && c!=m); CHECK(!Call(PF_ui_native_draw,&client,m));
	CHECK(!Call(PF_ui_native_close,&client,m));
	CHECK(Call(PF_ui_native_draw,&client,c)==1);
	CHECK(captured.owner.vm==2 && captured.clip[0]==0 && captured.clip[1]==0 && captured.clip[2]==640 && captured.clip[3]==480);
	CHECK(!backclipped); Plug_NativeUI_End(&client);
	CHECK(Call(PF_ui_native_close,&menu,m)==1); CHECK(!Call(PF_ui_native_close,&menu,m));
	Plug_NativeUI_Begin(&menu,1); old=m; m=Call(PF_ui_native_open,&menu,101);
	CHECK(m>old && !Call(PF_ui_native_draw,&menu,old));
	Plug_NativeUI_Release(&menu); CHECK(reasons[PLUGUI_CLOSE_VM]==1);
	CHECK(!Call(PF_ui_native_draw,&menu,m));
	Plug_NativeUI_RendererShutdown(); CHECK(reasons[PLUGUI_CLOSE_RENDERER]==1);
	qrenderer=QR_NONE; CHECK(!Call(PF_ui_native_status,&menu,0));
	qrenderer=1; BE_DrawMesh_Single=NULL; CHECK(!Call(PF_ui_native_status,&menu,0));
	BE_DrawMesh_Single=(void *)1; vid.pixelwidth=0; CHECK(!Call(PF_ui_native_status,&menu,0));
	vid.pixelwidth=640; Plug_NativeUI_Begin(&menu,1); failopen=1; before=closes;
	CHECK(!Call(PF_ui_native_open,&menu,101)); CHECK(closes==before+1 && reasons[5]==1);
	failopen=0; m=Call(PF_ui_native_open,&menu,101); faildraw=1; host_framecount++;
	CHECK(!Call(PF_ui_native_draw,&menu,m)); CHECK(reasons[5]==2 && !Call(PF_ui_native_close,&menu,m));
	faildraw=0; m=Call(PF_ui_native_open,&menu,101); strcpy(r_refdef.rt_destcolour[0].texname,"target"); host_framecount++;
	before=draws; CHECK(!Call(PF_ui_native_draw,&menu,m) && draws==before && reasons[5]==3);
	r_refdef.rt_destcolour[0].texname[0]=0; m=Call(PF_ui_native_open,&menu,101);
	Plug_NativeUI_PluginClose(&plugins[1]); CHECK(Plug_NativeUI_Ready());
	Plug_NativeUI_PluginClose(&plugins[0]); CHECK(reasons[3]==1 && !Plug_NativeUI_Ready());
	CHECK(!Call(PF_ui_native_close,&menu,m));
	currentplug=&plugins[1]; service.Open=Open; CHECK(Plug_NativeUI_Register(&service,sizeof(service)));
	old=m; m=Call(PF_ui_native_open,&menu,101); CHECK(m>old);
	CHECK(Call(PF_ui_native_close,&menu,m)==1);
	//Inherited non-finite clips (including finite -> physical overflow) fail
	//before any native callback/flush, and release the partially-open owner once.
	for (j=0;j<countof(invalidclip);j++)
	{
		m=Call(PF_ui_native_open,&menu,101);
		clip.x=invalidclip[j]; Plug_NativeUI_SetClip(&menu,&clip);
		host_framecount++; native_before=draws; before=closes; flush_before=flushes;
		CHECK(!Call(PF_ui_native_draw,&menu,m) && draws==native_before);
		CHECK(closes==before+1 && flushes==flush_before);
		CHECK(!Call(PF_ui_native_close,&menu,m));
	}
	clip.x=0.1875f; Plug_NativeUI_SetClip(&menu,NULL);
	//Close/reopen in one host frame cannot authorize another draw in that frame.
	host_framecount++; m=Call(PF_ui_native_open,&menu,101); CHECK(Call(PF_ui_native_draw,&menu,m)==1);
	CHECK(Call(PF_ui_native_close,&menu,m)==1); m=Call(PF_ui_native_open,&menu,101);
	CHECK(!Call(PF_ui_native_draw,&menu,m)); CHECK(Call(PF_ui_native_close,&menu,m)==1);
	plugui_serial=PLUGUI_MAXID-1; m=Call(PF_ui_native_open,&menu,101); CHECK(m==PLUGUI_MAXID);
	CHECK(Call(PF_ui_native_close,&menu,m)==1); before=opens;
	CHECK(!Call(PF_ui_native_open,&menu,101) && opens==before);
	CHECK(!Call(PF_ui_native_close,&menu,1));
	CHECK(opens==closes);
	printf("P590 host: %u checks, %u failed\n",checks,errors);
	return errors ? 1 : 0;
}
