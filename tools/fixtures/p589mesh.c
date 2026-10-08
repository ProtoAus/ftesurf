//Owned disposable native indexed-2D fixture; no production UI/input ownership.
#include "quakedef.h"
#include "plugin.h"
#include <limits.h>
#undef vsnprintf
#undef snprintf

static plugcorefuncs_t *core;
static plug2dfuncs_t *draw;
static plugmeshfuncs_t *mesh;
static plugcmdfuncs_t *cmd;
static plugcvarfuncs_t *cvar;
static pluginputfuncs_t *input;
static plugmeshtex_t atlas, white;
static int frames, submitted, restarts, invalidcount, stale, uploads;
static unsigned char pixels[16] = {255,0,0,255, 0,255,0,255, 0,0,255,128, 255,255,255,128};
static unsigned char opaque[4] = {255,255,255,255};

static void Print(const char *fmt, ...)
{
	char buffer[1024];
	va_list args;
	va_start(args, fmt);
	vsnprintf(buffer, sizeof(buffer), fmt, args);
	va_end(args);
	core->Print(buffer);
}
static void Vertex(plugmeshvertex_t *v, float x, float y, float u, float t, unsigned int r, unsigned int g, unsigned int b, unsigned int a)
{
	v->xy[0]=x; v->xy[1]=y; v->uv[0]=u; v->uv[1]=t;
	v->rgba[0]=r; v->rgba[1]=g; v->rgba[2]=b; v->rgba[3]=a;
}
static void Upload(void)
{
	char token[64];
	if (!mesh) return;
	if (!uploads)
	{
		plugmeshtex_t previous;
		cvar->GetString("p589_token",token,sizeof(token));
		previous=(plugmeshtex_t)strtoull(token,NULL,10);
		Print("P589 RELOAD previous=%llu rejected=%d\n",(unsigned long long)previous,previous ? !mesh->DestroyTexture(previous) : 0);
	}
	atlas = mesh->CreateTextureRGBA(2,2,pixels,sizeof(pixels));
	white = mesh->CreateTextureRGBA(1,1,opaque,sizeof(opaque));
	snprintf(token,sizeof(token),"%llu",(unsigned long long)atlas);
	cvar->SetString("p589_token",token);
	uploads++;
	Print("P589 UPLOAD atlas=%llu white=%llu uploads=%d\n",(unsigned long long)atlas,(unsigned long long)white,uploads);
}
static void QDECL Open(void)
{
	Upload();
	Print("P589 OPEN focus=%d available=%d\n",input->SetMenuFocus(true,"",0,0,1),mesh!=NULL);
}
static void QDECL Status(void)
{
	float v[2]={0,0}; unsigned int p[2]={0,0};
	int video=draw->GetVideoSize(v,p);
	Print("P589 STATUS frames=%d submitted=%d video=%d vw=%.0f vh=%.0f pw=%u ph=%u uploads=%d restarts=%d invalid=%d stale=%d\n",
		frames,submitted,video,v[0],v[1],p[0],p[1],uploads,restarts,invalidcount,stale);
}
static void QDECL Invalid(void)
{
	plugmeshvertex_t v[3]; unsigned int ix[3]={0,1,2};
	plugmeshcommand_t c[2]={{0,{0,0,640,480},0,3,0},{0,{0,0,640,480},0,3,0}};
	plugmeshbatch_t b={sizeof(b),v,ix,c,3,3,1};
	plugmeshtex_t t, tokens[PLUGMESH_MAX_TEXTURES];
	unsigned int i; int bad=0, life=0, budget=0;
	if (!mesh) return;
	Print("P589 INVALID begin=1\n");
	for(i=0;i<3;i++) Vertex(&v[i],4+i,4,0,0,255,0,0,255);
	c[0].texture=c[1].texture=white;
	bad += !mesh->CreateTextureRGBA(0,1,opaque,4);
	bad += !mesh->CreateTextureRGBA(4097,1,opaque,4);
	bad += !mesh->CreateTextureRGBA(UINT_MAX,UINT_MAX,opaque,4);
	bad += !mesh->CreateTextureRGBA(1,1,NULL,4);
	bad += !mesh->CreateTextureRGBA(1,1,opaque,3);
	bad += !mesh->CreateTextureRGBA(1,1,opaque,(size_t)-1);
	bad += !mesh->DestroyTexture(0);
	bad += !mesh->DestroyTexture(~(plugmeshtex_t)0);
	bad += !mesh->Submit(NULL);
	b.structsize--; bad += !mesh->Submit(&b); b.structsize++;
	b.vertices=NULL; bad += !mesh->Submit(&b); b.vertices=v;
	b.indices=NULL; bad += !mesh->Submit(&b); b.indices=ix;
	b.commands=NULL; bad += !mesh->Submit(&b); b.commands=c;
	b.numvertices=PLUGMESH_MAX_VERTICES+1; bad += !mesh->Submit(&b); b.numvertices=3;
	b.numindices=PLUGMESH_MAX_INDICES+1; bad += !mesh->Submit(&b); b.numindices=3;
	b.numcommands=PLUGMESH_MAX_COMMANDS+1; bad += !mesh->Submit(&b); b.numcommands=1;
	c[0].firstindex=UINT_MAX; bad += !mesh->Submit(&b); c[0].firstindex=0;
	c[0].indexcount=UINT_MAX; bad += !mesh->Submit(&b); c[0].indexcount=3;
	c[0].vertexoffset=UINT_MAX; bad += !mesh->Submit(&b); c[0].vertexoffset=0;
	ix[2]=3; bad += !mesh->Submit(&b); ix[2]=2;
	c[0].indexcount=2; bad += !mesh->Submit(&b); c[0].indexcount=3;
	v[0].xy[0]=NAN; bad += !mesh->Submit(&b); v[0].xy[0]=4;
	v[0].uv[0]=INFINITY; bad += !mesh->Submit(&b); v[0].uv[0]=0;
	c[0].clip[2]=NAN; bad += !mesh->Submit(&b); c[0].clip[2]=640;
	c[1].texture=~(plugmeshtex_t)0; b.numcommands=2; bad += !mesh->Submit(&b); b.numcommands=1;
	t=mesh->CreateTextureRGBA(1,1,opaque,4); life += t!=0;
	life += mesh->DestroyTexture(t);
	life += !mesh->DestroyTexture(t);
	c[0].texture=t; life += !mesh->Submit(&b);
	tokens[0]=mesh->CreateTextureRGBA(1,1,opaque,4); life += tokens[0]!=0 && tokens[0]!=t;
	life += !mesh->DestroyTexture(t);
	life += mesh->DestroyTexture(tokens[0]);
	for(i=0;i<PLUGMESH_MAX_TEXTURES-2;i++) tokens[i]=mesh->CreateTextureRGBA(1,1,opaque,4);
	for(i=0;i<PLUGMESH_MAX_TEXTURES-2;i++) budget += tokens[i]!=0;
	budget += !mesh->CreateTextureRGBA(1,1,opaque,4);
	for(i=0;i<PLUGMESH_MAX_TEXTURES-2;i++) budget += mesh->DestroyTexture(tokens[i]);
	invalidcount=bad;
	Print("P589 INVALID end=1 rejected=%d life=%d budget=%d\n",bad,life,budget);
}
static void QDECL Foreign(void)
{
	char token[64]; plugmeshtex_t t;
	plugmeshvertex_t v[3]; unsigned int ix[3]={0,1,2};
	plugmeshcommand_t c={0,{0,0,640,480},0,3,0};
	plugmeshbatch_t b={sizeof(b),v,ix,&c,3,3,1};
	unsigned int i;
	if(!mesh) return;
	for(i=0;i<3;i++) Vertex(&v[i],4+i,4,0,0,255,0,0,255);
	cvar->GetString("p589_token",token,sizeof(token));
	c.texture=t=(plugmeshtex_t)strtoull(token,NULL,10);
	Print("P589 FOREIGN token=%llu rejected=%d\n",(unsigned long long)t,!mesh->DestroyTexture(t)+!mesh->Submit(&b));
}
static void QDECL Leak(void)
{
	unsigned int i; int count=0;
	if(!mesh) return;
	for(i=0;i<PLUGMESH_MAX_TEXTURES;i++) count += mesh->CreateTextureRGBA(1,1,opaque,4)!=0;
	Print("P589 LEAK created=%d\n",count); //No Shutdown export: host must reclaim all.
}
static void QDECL Video(int w,int h,qboolean restarted)
{
	(void)w; (void)h;
	if(mesh && restarted && uploads)
	{
		stale += !mesh->DestroyTexture(atlas);
		stale += !mesh->DestroyTexture(white);
		restarts++;
		Upload();
		Print("P589 VIDEO restart=1 stale=%d\n",stale);
	}
}
static qboolean QDECL Menu(int event,int key,int unicode,float mx,float my,float w,float h)
{
	float vsize[2]; unsigned int psize[2];
	plugmeshvertex_t v[14], many[600]; unsigned int ix[15]={UINT_MAX,UINT_MAX,UINT_MAX,0,1,2,0,2,3,0,1,2,0,1,2}, mix[600];
	plugmeshcommand_t c[3]={{0,{80,80,176,176},3,6,1},{0,{432,96,512,160},9,3,5},{0,{0,0,640,480},12,3,8}};
	plugmeshbatch_t b={sizeof(b),v,ix,c,14,15,3};
	plugmeshcommand_t mc={0,{0,0,640,480},0,600,0};
	plugmeshbatch_t mb={sizeof(mb),many,mix,&mc,600,600,1};
	unsigned int i;
	(void)key; (void)unicode; (void)mx; (void)my;
	if(event!=0) return true;
	frames++;
	draw->GetVideoSize(vsize,psize);
	//Legacy colours use virtual coordinates; mesh coordinates stay physical.
	draw->Colour4f(0,0,0,1); draw->Fill(0,0,w,h);
	draw->Colour4f(1,0,1,1); draw->Fill(16*vsize[0]/psize[0],16*vsize[1]/psize[1],24*vsize[0]/psize[0],24*vsize[1]/psize[1]);
	draw->Colour4f(1,0,0,1); draw->Fill(400*vsize[0]/psize[0],64*vsize[1]/psize[1],128*vsize[0]/psize[0],128*vsize[1]/psize[1]);
	draw->Colour4f(0,1,0,1); //Must survive mesh submission.
	if(mesh)
	{
		for(i=0;i<14;i++) Vertex(&v[i],0,0,0,0,255,255,255,255);
		Vertex(&v[1],64,64,0,0,255,255,255,255); Vertex(&v[2],192,64,1,0,255,255,255,255);
		Vertex(&v[3],192,192,1,1,255,255,255,255); Vertex(&v[4],64,192,0,1,255,255,255,255);
		Vertex(&v[5],400,64,0,0,0,0,255,128); Vertex(&v[6],528,64,0,0,0,0,255,128); Vertex(&v[7],400,192,0,0,0,0,255,128);
		Vertex(&v[8],400,240,0,0,0,255,0,255); Vertex(&v[9],528,368,0,0,0,255,0,255); Vertex(&v[10],528,240,0,0,0,255,0,255);
		c[0].texture=atlas; c[1].texture=c[2].texture=white;
		submitted += mesh->Submit(&b);
		//Force multiple internal mesh chunks with visible cyan result.
		for(i=0;i<600;i++)
		{
			static const float xy[3][2]={{64,256},{192,256},{64,384}};
			Vertex(&many[i],xy[i%3][0],xy[i%3][1],0,0,0,255,255,255); mix[i]=i;
		}
		mc.texture=white; submitted += mesh->Submit(&mb);
		//Empty clip is successful but must not draw a white triangle at origin.
		mc.clip[2]=mc.clip[0]; submitted += mesh->Submit(&mb);
		//Invalid second command must not submit the valid first command at origin.
		c[0].clip[0]=c[0].clip[1]=0; c[0].clip[2]=c[0].clip[3]=640;
		c[0].vertexoffset=0; c[0].firstindex=9; c[0].indexcount=3;
		Vertex(&v[0],240,64,0,0,255,255,255,255); Vertex(&v[1],368,64,0,0,255,255,255,255); Vertex(&v[2],240,192,0,0,255,255,255,255);
		c[1].texture=~(plugmeshtex_t)0; b.numcommands=2;
		mesh->Submit(&b);
	}
	draw->Fill(256*vsize[0]/psize[0],256*vsize[1]/psize[1],32*vsize[0]/psize[0],32*vsize[1]/psize[1]);
	return true;
}
static void None(void)
{
	const char *path=getenv("P589_NONE_MARKER"); FILE *f=path?fopen(path,"w"):NULL;
	if(f)
	{
		fprintf(f,"P589 NONE video=%d texture=%llu submit=%d\n",draw->GetVideoSize(NULL,NULL),
			(unsigned long long)mesh->CreateTextureRGBA(1,1,opaque,4),mesh->Submit(NULL));
		fclose(f);
	}
}
__declspec(dllexport) qboolean QDECL FTEPlug_Init(plugcorefuncs_t *funcs)
{
	core=funcs;
	draw=core->GetEngineInterface(plug2dfuncs_name,sizeof(*draw));
	mesh=core->GetEngineInterface(plugmeshfuncs_name,sizeof(*mesh));
	cmd=core->GetEngineInterface(plugcmdfuncs_name,sizeof(*cmd));
	cvar=core->GetEngineInterface(plugcvarfuncs_name,sizeof(*cvar));
	input=core->GetEngineInterface(pluginputfuncs_name,sizeof(*input));
	if(!draw||!cmd||!cvar||!input) return false;
	Print("P589 INIT available=%d short=%d long=%d version=%d\n",mesh!=NULL,
		core->GetEngineInterface(plugmeshfuncs_name,sizeof(*mesh)-1)==NULL,
		core->GetEngineInterface(plugmeshfuncs_name,sizeof(*mesh)+1)==NULL,
		core->GetEngineInterface("2DMesh/2",sizeof(*mesh))==NULL);
#ifdef FOREIGN
	(void)Open; (void)Status; (void)Invalid; (void)Menu; (void)Video; (void)None;
	return cmd->AddCommand("p589_foreign",Foreign,"Foreign token control") && cmd->AddCommand("p589_leak",Leak,"Automatic cleanup control");
#else
	(void)Foreign; (void)Leak;
	if(mesh && !draw->GetVideoSize(NULL,NULL)) None();
	if(!core->ExportFunction("MenuEvent",Menu)||!core->ExportFunction("UpdateVideo",Video)) return false;
	return cmd->AddCommand("p589_open",Open,"Owned mesh fixture") && cmd->AddCommand("p589_status",Status,"Mesh status") && cmd->AddCommand("p589_invalid",Invalid,"Invalid mesh probes");
#endif
}
