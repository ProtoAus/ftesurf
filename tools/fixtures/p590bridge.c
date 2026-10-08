//Disposable service fixture. No Tick/Sbar/Menu drawing callbacks are exported.
#include <stdio.h>
#include <stdarg.h>
#include "quakedef.h"
#include "plugin.h"
#undef vsnprintf
#undef snprintf
static plugcorefuncs_t *core;
static plugmeshfuncs_t *mesh;
static plug2dfuncs_t *legacy;
static plugcmdfuncs_t *cmd;
static plugcvarfuncs_t *cvar;
static struct { pluguiowner_t owner; plugmeshtex_t tex; unsigned int draws; } contexts[2];
static unsigned int opens, draws, closes, destroys, reasons[6];
static int abi;
static void Print(const char *fmt, ...)
{
	char text[512]; va_list ap;
	va_start(ap,fmt); vsnprintf(text,sizeof(text),fmt,ap); va_end(ap);
	core->Print(text);
}
static int Failure(void)
{
	char value[32]; cvar->GetString("p590_failure",value,sizeof(value));
	return atoi(value);
}
static qboolean QDECL Open(const pluguiowner_t *o)
{
	static const unsigned char white[4] = {255,255,255,255};
	unsigned int i = o->vm-1;
	if (i >= 2 || contexts[i].tex) return false;
	contexts[i].owner = *o;
	contexts[i].tex = mesh->CreateTextureRGBA(1,1,white,4);
	opens++;
	Print("P590 OPEN vm=%u owner=%u handle=%u allocated=%d fail=%d\n",o->vm,o->owner,o->generation,!!contexts[i].tex,Failure());
	return contexts[i].tex && Failure() != 1;
}
static qboolean QDECL Draw(const pluguiframe_t *f)
{
	unsigned int i = f->owner.vm-1;
	float sx = f->pixelwidth/320, sy = f->pixelheight/240;
	plugmeshvertex_t v[4] = {
		{{80*sx,50*sy},{0,0},{0,255,0,255}}, {{200*sx,50*sy},{1,0},{0,255,0,255}},
		{{200*sx,150*sy},{1,1},{0,255,0,255}}, {{80*sx,150*sy},{0,1},{0,255,0,255}}
	};
	unsigned int ix[6] = {0,1,2,0,2,3};
	plugmeshcommand_t c = {0};
	plugmeshbatch_t b = {sizeof(b),v,ix,&c,4,6,1};
	qboolean ok;
	if (i >= 2 || f->structsize != sizeof(*f) || contexts[i].owner.generation != f->owner.generation)
		return false;
	contexts[i].draws++; draws++;
	if (Failure() == 2) return false;
	c.texture = contexts[i].tex; c.indexcount = 6;
	c.clip[2] = f->pixelwidth; c.clip[3] = f->pixelheight; //deliberately wider than caller
	ok = mesh->Submit(&b);
	legacy->Colour4f(1,0,1,0.25f); //host must restore caller's colour
	if (contexts[i].draws == 1)
		Print("P590 DRAW vm=%u handle=%u frame=%u ok=%d virtual=%.0fx%.0f pixel=%.0fx%.0f clip=%.0f,%.0f,%.0f,%.0f\n",i+1,f->owner.generation,f->frame,ok,f->virtualwidth,f->virtualheight,f->pixelwidth,f->pixelheight,f->clip[0],f->clip[1],f->clip[2],f->clip[3]);
	return ok;
}
static void QDECL Close(const pluguiowner_t *o, unsigned int reason)
{
	unsigned int i = o->vm-1;
	int destroyed = 0;
	if (i < 2 && contexts[i].owner.generation == o->generation)
	{
		if (contexts[i].tex) destroyed = mesh->DestroyTexture(contexts[i].tex);
		memset(&contexts[i],0,sizeof(contexts[i]));
	}
	closes++; destroys += destroyed;
	if (reason < 6) reasons[reason]++;
	Print("P590 CLOSE vm=%u handle=%u reason=%u destroyed=%d\n",o->vm,o->generation,reason,destroyed);
}
static void QDECL Status(void)
{
	Print("P590 STATUS abi=%d opens=%u draws=%u closes=%u destroys=%u live=%d explicit=%u vm=%u plugin=%u renderer=%u failed=%u\n",abi,opens,draws,closes,destroys,!!contexts[0].tex+!!contexts[1].tex,reasons[1],reasons[2],reasons[3],reasons[4],reasons[5]);
}
static void QDECL Shutdown(void) { Status(); }
#ifdef _WIN32
__declspec(dllexport)
#endif
qboolean QDECL FTEPlug_Init(plugcorefuncs_t *c)
{
	pluguiservice_t service = {sizeof(service),PLUGUI_VERSION,PLUGUI_CAP_INDEXED2D,Open,Draw,Close};
	pluguiservice_t bad = service;
	core = c;
	mesh = core->GetEngineInterface(plugmeshfuncs_name,sizeof(*mesh));
	legacy = core->GetEngineInterface(plug2dfuncs_name,sizeof(*legacy));
	cmd = core->GetEngineInterface(plugcmdfuncs_name,sizeof(*cmd));
	cvar = core->GetEngineInterface(plugcvarfuncs_name,sizeof(*cvar));
	if (!mesh || !legacy || !cmd || !cvar) return false;
	abi += !core->ExportInterface(pluguiservice_name,&service,sizeof(service)-1);
	abi += !core->ExportInterface(pluguiservice_name,&service,sizeof(service)+1);
	bad.structsize--; abi += !core->ExportInterface(pluguiservice_name,&bad,sizeof(bad));
	bad = service; bad.version++; abi += !core->ExportInterface(pluguiservice_name,&bad,sizeof(bad));
	bad = service; bad.capabilities = 0; abi += !core->ExportInterface(pluguiservice_name,&bad,sizeof(bad));
	bad = service; bad.Draw = NULL; abi += !core->ExportInterface(pluguiservice_name,&bad,sizeof(bad));
	if (!core->ExportInterface(pluguiservice_name,&service,sizeof(service))) return false;
	abi += !core->ExportInterface(pluguiservice_name,&service,sizeof(service));
	service.Open = NULL; //accepted table must have been copied
	cmd->AddCommand("p590_status",Status,"Report disposable native UI fixture state");
	core->ExportFunction("Shutdown",Shutdown);
	Print("P590 ABI rejected=%d service=1\n",abi);
	return true;
}
