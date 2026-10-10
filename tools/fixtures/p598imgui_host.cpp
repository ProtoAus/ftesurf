//Real plugin/adapter/ImGui source with acting fake C-ABI endpoints; no renderer mocks in runtime gallery.
#include "ui_imgui.cpp"
#include "vendor/imgui_internal.h"
#include <vector>
#include <set>
#include <limits>
#include <cstring>
using namespace FteImGui;
static unsigned checks, faults, calls, creates, destroys;
static bool failcreate, failsubmit;
static pluguiservice_t service;
static pluguiinputservice_t inputservice;
static pluguimodelservice_t modelservice;
#ifdef PLUGUI_MODEL2_VERSION
static pluguimodelservice2_t modelservice2;
static bool model2available = true;
#endif
#ifdef PLUGUI_PLOT_VERSION
static pluguiplotservice_t plotservice;
static bool plotavailable = true;
#endif
static bool modelavailable = true;
static bool inputavailable = true;
static std::set<plugmeshtex_t> live;
static std::vector<plugmeshvertex_t> ink;
static std::vector<plugmeshcommand_t> commands;
static plugmeshtex_t serial = 100;
static void Check(bool ok, const char *label)
{
	checks++; if (!ok) { faults++; std::printf("FAIL %s\n",label); }
}
static qboolean QDECL Submit(const plugmeshbatch_t *b)
{
	calls++;
	Check(b->numvertices <= PLUGMESH_MAX_VERTICES && b->numindices <= PLUGMESH_MAX_INDICES &&
		b->numcommands <= PLUGMESH_MAX_COMMANDS,"bounded host batch");
	for (unsigned n = 0; n < b->numcommands; n++)
	{
		const auto &c = b->commands[n];
		Check(c.indexcount % 3 == 0 && c.firstindex+c.indexcount <= b->numindices && !c.vertexoffset,"valid host command");
		for (unsigned k = 0; k < c.indexcount; k++)
			if (b->indices[c.firstindex+k] >= b->numvertices) { Check(false,"host index bound"); break; }
	}
	if (failsubmit) return qfalse;
	ink.insert(ink.end(),b->vertices,b->vertices+b->numvertices);
	commands.insert(commands.end(),b->commands,b->commands+b->numcommands);
	return qtrue;
}
static plugmeshtex_t QDECL Create(unsigned w, unsigned h, const qbyte *rgba, size_t bytes)
{
	creates++; Check(w && h && rgba && bytes == size_t(w)*h*4,"actual atlas bytes");
	if (failcreate) return 0;
	live.insert(++serial); return serial;
}
static qboolean QDECL Destroy(plugmeshtex_t t)
{
	destroys++; Check(live.erase(t) == 1,"destroy live token exactly once"); return qtrue;
}
static plugmeshfuncs_t api = {nullptr,Create,Destroy,Submit};
static plugcmdfuncs_t cmdapi = {};
static void *QDECL GetInterface(const char *name, size_t size)
{
	if (!std::strcmp(name,plugmeshfuncs_name) && size == sizeof(api)) return &api;
	if (!std::strcmp(name,plugcmdfuncs_name) && size == sizeof(cmdapi)) return &cmdapi;
	return nullptr;
}
static qboolean QDECL ExportInterface(const char *name, void *p, size_t size)
{
	if (!std::strcmp(name,pluguiinputservice_name))
	{
		Check(size == sizeof(inputservice),"exact additive input service");
		if (!inputavailable) return qfalse;
		std::memcpy(&inputservice,p,sizeof(inputservice)); return qtrue;
	}
	if (!std::strcmp(name,pluguimodelservice_name))
	{
		Check(size == sizeof(modelservice),"exact additive model service");
		if (!modelavailable) return qfalse;
		std::memcpy(&modelservice,p,sizeof(modelservice)); return qtrue;
	}
#ifdef PLUGUI_MODEL2_VERSION
	if (!std::strcmp(name,pluguimodelservice2_name))
	{
		Check(size == sizeof(modelservice2),"exact additive dense model service");
		if (!model2available) return qfalse;
		std::memcpy(&modelservice2,p,sizeof(modelservice2)); return qtrue;
	}
#endif
#ifdef PLUGUI_PLOT_VERSION
	if (!std::strcmp(name,pluguiplotservice_name))
	{
		Check(size == sizeof(plotservice),"exact additive plot service");
		if (!plotavailable) return qfalse;
		std::memcpy(&plotservice,p,sizeof(plotservice)); return qtrue;
	}
#endif
	//Anything else is the drawing service, or a name this host does not know: an older
	//host refuses those, and filing one here once overwrote the service table.
	Check(!std::strcmp(name,pluguiservice_name) && size == sizeof(service),"exact exported service");
	if (std::strcmp(name,pluguiservice_name)) return qfalse;
	std::memcpy(&service,p,sizeof(service)); return qtrue;
}
static qboolean QDECL ExportFunction(const char *name, funcptr_t p)
{
	Check(!std::strcmp(name,"Shutdown") && p,"only shutdown callback exported"); return qtrue;
}
static qboolean QDECL AddCommand(const char *name, void (*p)(), const char *)
{
	Check(!std::strcmp(name,"ui_imgui_status") && p,"explicit diagnostic command"); return qtrue;
}
static void QDECL Print(const char *s) { std::printf("%s",s); }
static void Callback(const ImDrawList *, const ImDrawCmd *) { Check(false,"unknown callback never executes"); }
static void ResetInk() { calls = 0; ink.clear(); commands.clear(); }
int main()
{
	plugcorefuncs_t coreapi = {};
	coreapi.GetEngineInterface = GetInterface; coreapi.ExportInterface = ExportInterface;
	coreapi.ExportFunction = ExportFunction; coreapi.Print = Print; cmdapi.AddCommand = AddCommand;
	Check(FTEPlug_Init(&coreapi) == qtrue,"plugin registered");
	Check(!stats.frames && !stats.uploads && !calls,"closed init zero work");
	pluguiowner_t menu = {1,GalleryMenu,1}, client = {2,GalleryClient,2}, bad = {1,999,3};
	Check(!service.Open(&bad),"unsupported owner refuses"); bad = {0,GalleryMenu,3};
	Check(!service.Open(&bad),"invalid VM refuses");
	ImGuiContext *outside = ImGui::CreateContext();
	ImGui::GetIO().IniFilename = nullptr; //The control context must not write imgui.ini into the cwd.
	Check(service.Open(&menu),"menu opens");
	Check(ImGui::GetCurrentContext() == outside,"open context restored");
	Check(service.Open(&client),"client opens separately");
	Check(contexts[0]->imgui != contexts[1]->imgui && contexts[0]->atlas != contexts[1]->atlas,"VM context/token isolation");
	Check(!service.Open(&menu),"duplicate open refuses");
	pluguiframe_t f = {sizeof(f),menu,1,320,240,640,480,{40,40,560,400}};
	for (auto *c : contexts)
	{
		ImGui::SetCurrentContext(c->imgui);
		Check(!ImGui::GetIO().IniFilename && !ImGui::GetIO().LogFilename,"implicit files disabled");
	}
	ImGui::SetCurrentContext(outside);
	Check(service.Draw(&f),"real ImGui gallery draws");
	Check(ImGui::GetCurrentContext() == outside,"draw context restored");
	Check(calls && !ink.empty() && stats.frames == 1,"real native ink reached host");
	f.owner = client; Check(service.Draw(&f),"client real gallery draws");
	failsubmit = true; Check(!service.Draw(&f),"draw submit failure propagates"); failsubmit = false;
	f.owner.generation++; Check(!service.Draw(&f),"wrong generation refuses"); f.owner = menu;
	service.Close(&menu,1); service.Close(&menu,1);
	Check(destroys == 1 && !contexts[0] && contexts[1],"idempotent close preserves other VM");
	service.Close(&client,4); Check(live.empty(),"renderer closes both atlases");
	unsigned frames = stats.frames, uploads = stats.uploads, submits = stats.submissions;
	for (int k = 0; k < 100; k++) Status();
	Check(stats.frames == frames && stats.uploads == uploads && stats.submissions == submits,"closed zero recurring native work");
	failcreate = true; menu.generation = 4;
	Check(!service.Open(&menu),"failed atlas/open acts");
	service.Close(&menu,5); failcreate = false;
	Check(!contexts[0] && live.empty(),"failed partial context reclaimed");
	Check(service.Open(&menu),"reopen after atlas failure");
	service.Close(&menu,3); Shutdown(); Check(live.empty(),"unload idempotent cleanup");

	ImGui::SetCurrentContext(outside);
	ImDrawList list(ImGui::GetDrawListSharedData());
	list.VtxBuffer.resize(6); list.IdxBuffer.resize(9); list.CmdBuffer.resize(1);
	for (int k = 0; k < 6; k++) list.VtxBuffer[k] = {ImVec2(10+k,20+k),ImVec2(.25f,.75f),IM_COL32(11,22,33,44)};
	for (int k = 0; k < 9; k++) list.IdxBuffer[k] = ImDrawIdx(k%3);
	ImDrawCmd c; c.TextureId = 77; c.ElemCount = 6; c.IdxOffset = 3; c.VtxOffset = 3; c.ClipRect = ImVec4(10,20,100,100);
	list.CmdBuffer[0] = c;
	ImDrawData d; d.Valid = true; d.CmdListsCount = 1; d.CmdLists.push_back(&list);
	d.TotalVtxCount = 6; d.TotalIdxCount = 9; d.DisplayPos = ImVec2(10,20);
	d.DisplaySize = ImVec2(320,240); d.FramebufferScale = ImVec2(2,2);
	f.clip[0] = 0; f.clip[1] = 0; f.clip[2] = 640; f.clip[3] = 480;
	Renderer *r = new Renderer; Counters count;
	ResetInk(); Check(r->Submit(d,77,f,api,count),"offset/scale crafted draw");
	Check(ink.size() == 6 && ink[0].xy[0] == 6 && ink[0].xy[1] == 6,"DisplayPos framebuffer scale and offsets");
	Check(ink[0].rgba[0] == 11 && ink[0].rgba[1] == 22 && ink[0].rgba[2] == 33 && ink[0].rgba[3] == 44,"RGBA packing");
	Check(ink[0].uv[0] == .25f && ink[0].uv[1] == .75f && commands[0].clip[2] == 180,"UV and clip conversion");
	list.CmdBuffer.push_back(c); list.CmdBuffer[1].UserCallback = ImDrawCallback_ResetRenderState;
	ResetInk(); Check(r->Submit(d,77,f,api,count) && calls == 1,"reset callback no external execution");
	list.CmdBuffer[1].UserCallback = Callback;
	ResetInk(); Check(!r->Submit(d,77,f,api,count) && !calls,"unknown later callback no partial submission");
	list.CmdBuffer.resize(1);
	for (int which = 0; which < 18; which++)
	{
		list.CmdBuffer.push_back(c); auto &badc = list.CmdBuffer[1];
		float saved = list.VtxBuffer[0].pos.x;
		switch (which) {
		case 0: badc.TextureId++; break;
		case 1: badc.IdxOffset = 999; break;
		case 2: badc.VtxOffset = 999; break;
		case 3: badc.ElemCount = 999; break;
		case 4: badc.ElemCount = 4; break;
		case 5: badc.ClipRect.x = std::numeric_limits<float>::infinity(); break;
		case 6: badc.ClipRect.y = std::numeric_limits<float>::quiet_NaN(); break;
		case 7: badc.ClipRect.z = std::numeric_limits<float>::max(); break;
		case 8: list.VtxBuffer[0].pos.x = std::numeric_limits<float>::quiet_NaN(); break;
		case 9: list.IdxBuffer[3] = 99; break;
		case 10: d.TotalVtxCount++; break;
		case 11: d.FramebufferScale.x = -1; break;
		case 12: list.VtxBuffer[0].uv.x = std::numeric_limits<float>::infinity(); break;
		case 13: d.DisplayPos.x = std::numeric_limits<float>::quiet_NaN(); break;
		case 14: d.DisplaySize.x = std::numeric_limits<float>::infinity(); break;
		case 15: f.clip[0] = std::numeric_limits<float>::quiet_NaN(); break;
		case 16: f.pixelwidth = std::numeric_limits<float>::infinity(); break;
		case 17: d.TotalIdxCount++; break;
		}
		ResetInk(); Check(!r->Submit(d,77,f,api,count) && !calls,"malformed data zero partial submission");
		list.VtxBuffer[0].pos.x = saved; list.IdxBuffer[3] = 0; d.TotalVtxCount = 6; d.FramebufferScale.x = 2;
		list.VtxBuffer[0].uv.x = .25f; d.DisplayPos.x = 10; d.DisplaySize.x = 320;
		f.clip[0] = 0; f.pixelwidth = 640; d.TotalIdxCount = 9;
		list.CmdBuffer.resize(1);
	}
	list.CmdBuffer[0].ClipRect = ImVec4(100,100,90,90);
	ResetInk(); Check(r->Submit(d,77,f,api,count) && !calls,"empty clip zero ink"); list.CmdBuffer[0] = c;
	list.VtxBuffer.resize(MaxVertices+1); d.TotalVtxCount = MaxVertices+1;
	ResetInk(); Check(!r->Submit(d,77,f,api,count) && !calls,"vertex budget rejection");
	list.VtxBuffer.resize(6); d.TotalVtxCount = 6;
	list.CmdBuffer.resize(MaxCommands+1);
	ResetInk(); Check(!r->Submit(d,77,f,api,count) && !calls,"command budget rejection"); list.CmdBuffer.resize(1);
	d.CmdListsCount = MaxLists+1;
	ResetInk(); Check(!r->Submit(d,77,f,api,count) && !calls,"list budget rejection"); d.CmdListsCount = 1;
	list.IdxBuffer.resize(MaxIndices+1); d.TotalIdxCount = MaxIndices+1;
	ResetInk(); Check(!r->Submit(d,77,f,api,count) && !calls,"stored index budget rejection");
	list.IdxBuffer.resize(MaxIndices/2); d.TotalIdxCount = MaxIndices/2;
	for (auto &idx : list.IdxBuffer) idx = 0;
	list.CmdBuffer.resize(3);
	for (auto &dc : list.CmdBuffer) { dc = c; dc.IdxOffset = dc.VtxOffset = 0; dc.ElemCount = MaxIndices/2; }
	ResetInk(); Check(!r->Submit(d,77,f,api,count) && !calls,"aliased consumed index budget rejection");

	ImGuiIO &io = ImGui::GetIO(); io.DisplaySize = ImVec2(640,480); io.DeltaTime = .01f;
	io.BackendFlags |= ImGuiBackendFlags_RendererHasVtxOffset;
	unsigned char *rgba; int w,h; io.Fonts->GetTexDataAsRGBA32(&rgba,&w,&h); io.Fonts->SetTexID(77);
	ImGui::NewFrame();
	ImDrawList *large = ImGui::GetForegroundDrawList();
	for (int k = 0; k < 20000; k++) large->AddRectFilled(ImVec2(10,10),ImVec2(20,20),IM_COL32(255,255,255,255));
	ImGui::Render();
	const ImDrawData &generated = *ImGui::GetDrawData();
	Check(generated.TotalVtxCount > 65535 && generated.TotalIdxCount == 120000,"large real draw data acts");
	ResetInk(); Check(r->Submit(generated,77,f,api,count) && calls > 1 && ink.size() == 120000,"bounded >64K generated draw data");
	bool offset = false; for (auto *dl : generated.CmdLists) for (const auto &dc : dl->CmdBuffer) offset |= dc.VtxOffset != 0;
	Check(sizeof(ImDrawIdx) == 4 || offset,"16-bit rollover VtxOffset acts");
	delete r; ImGui::DestroyContext(outside);
	std::printf("P595 HOST indexbits=%zu checks=%u failed=%u creates=%u destroys=%u\n",sizeof(ImDrawIdx)*8,checks,faults,creates,destroys);
	return faults ? 1 : 0;
}
