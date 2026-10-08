// Existing 2D API falsifier, not an ImGui/QC bridge. Owned disposable rig only.
#include "quakedef.h"
#include "plugin.h"
#include <limits.h>
#undef vsnprintf

static plugcorefuncs_t *core;
static plug2dfuncs_t *draw;
static pluginputfuncs_t *input;
static plugcmdfuncs_t *cmd;
static qhandle_t atlas, lookup, disk, extra;
static int phase, frames, uploads, videoevents, subject;
static unsigned char tga[34];

static void Print(const char *format, ...)
{
	char buffer[1024];
	va_list args;
	va_start(args, format);
	vsnprintf(buffer, sizeof(buffer), format, args);
	va_end(args);
	core->Print(buffer);
}

static void Encode(int replaced)
{
	static const unsigned char pixels[2][16] = {
		{0,0,255,255, 0,255,0,255, 255,0,0,128, 255,255,255,128},
		{255,0,0,128, 255,255,255,128, 0,0,255,255, 0,255,0,255}
	};
	memset(tga, 0, sizeof(tga));
	tga[2] = 2;
	tga[12] = tga[14] = 2;
	tga[16] = 32;
	tga[17] = 0x28;
	memcpy(tga + 18, pixels[!!replaced], 16);
}

static void Upload(void)
{
	qhandle_t next;
	Encode(phase);
	next = draw->LoadImageData("p577/atlas", "image/tga", tga, sizeof(tga));
	if (atlas > 0)
		draw->UnloadImage(atlas); // Release the old reference, not the new one.
	atlas = next;
	if (!lookup)
		lookup = draw->LoadImage("p577/atlas");
	if (disk > 0)
		draw->UnloadImage(disk);
	disk = draw->LoadImage(phase ? "textures/p577_b.tga" : "textures/p577_a.tga");
	uploads++;
	Print("P577 UPLOAD phase=%d atlas=%ld lookup=%ld disk=%ld uploads=%d\n",
		phase, (long)atlas, (long)lookup, (long)disk, uploads);
}

static void QDECL Status(void)
{
	float w = 0, h = 0, virtualsize[2] = {0,0};
	unsigned int pixelsize[2] = {0,0};
	int sized = draw->ImageSize(atlas, &w, &h);
	int video = draw->GetVideoSize(virtualsize, pixelsize);
	Print("P577 STATUS phase=%d frames=%d videoevents=%d uploads=%d atlas=%ld size=%d w=%.0f h=%.0f video=%d vw=%.0f vh=%.0f pw=%u ph=%u\n",
		phase, frames, videoevents, uploads, (long)atlas, sized, w, h, video,
		virtualsize[0], virtualsize[1], pixelsize[0], pixelsize[1]);
}

static void QDECL Open(void)
{
	char arg[32];
	cmd->Argv(1, arg, sizeof(arg));
	subject = atoi(arg);
	phase = 0;
	Upload();
	Print("P577 OPEN subject=%d focus=%d\n", subject,
		input->SetMenuFocus(true, "", 0, 0, 1));
}

static void QDECL Replace(void)
{
	phase = 1;
	Upload();
	Print("P577 REPLACE reached=1\n");
}

static void QDECL Invalid(void)
{
	unsigned char bad[34] = {0};
	vec2_t points[4] = {{0,0},{1,0},{1,1},{0,1}};
	vec2_t uv[4] = {{0,0},{1,0},{1,1},{0,1}};
	vec4_t colours[4] = {{1,1,1,1},{1,1,1,1},{1,1,1,1},{1,1,1,1}};
	qhandle_t handles[4] = {0, -1, INT_MIN, INT_MAX};
	int rejected = 0, ids = 0, i;
	float w, h;
	if (!subject)
	{
		Print("P577 INVALID control_skipped=1\n");
		return;
	}
	Print("P577 INVALID begin=1\n");
	rejected += draw->LoadImageData("p577/atlas", "image/tga", NULL, sizeof(tga)) == 0;
	rejected += draw->LoadImageData("p577/atlas", "image/tga", tga, 0) == 0;
	rejected += draw->LoadImageData("p577/atlas", "image/tga", tga, 1) == 0;
	rejected += draw->LoadImageData("p577/atlas", "image/tga", bad, sizeof(bad)) == 0;
	rejected += draw->LoadImageData(NULL, "image/tga", tga, sizeof(tga)) == 0;
	rejected += draw->LoadImageData("", "image/tga", tga, sizeof(tga)) == 0;
	rejected += draw->LoadImageData("p577/atlas", "image/tga", tga, (size_t)INT_MAX + 1) == 0;
	for (i = 0; i < 4; i++)
	{
		w = h = -99;
		ids += draw->ImageSize(handles[i], &w, &h) == -1;
		ids += draw->Image(0, 0, 1, 1, 0, 0, 1, 1, handles[i]) == 0;
		ids += draw->Image2dQuad(points, uv, colours, handles[i]) == 0;
		draw->UnloadImage(handles[i]);
	}
	Print("P577 INVALID end=1 rejected=%d ids=%d unloads=4\n", rejected, ids);
}

static void QDECL Lifetime(void)
{
	qhandle_t temp, reload;
	float w = 0, h = 0;
	int size, image, quad, reloaded;
	vec2_t points[4] = {{0,0},{1,0},{1,1},{0,1}};
	vec2_t uv[4] = {{0,0},{1,0},{1,1},{0,1}};
	vec4_t colours[4] = {{1,1,1,1},{1,1,1,1},{1,1,1,1},{1,1,1,1}};
	if (!subject)
	{
		Print("P577 LIFETIME control_skipped=1\n");
		return;
	}
	temp = draw->LoadImageData("p577/temp", "image/tga", tga, sizeof(tga));
	size = draw->ImageSize(temp, &w, &h);
	Print("P577 LIFETIME begin=1 temp=%ld size=%d w=%.0f h=%.0f\n", (long)temp, size, w, h);
	draw->UnloadImage(temp);
	size = draw->ImageSize(temp, &w, &h);
	image = draw->Image(0, 0, 1, 1, 0, 0, 1, 1, temp);
	quad = draw->Image2dQuad(points, uv, colours, temp);
	draw->UnloadImage(temp); // Non-live slot: must not double-free.
	reload = draw->LoadImageData("p577/temp", "image/tga", tga, sizeof(tga));
	reloaded = draw->ImageSize(reload, &w, &h);
	Print("P577 LIFETIME end=1 released_size=%d released_image=%d released_quad=%d reload=%ld size=%d w=%.0f h=%.0f\n",
		size, image, quad, (long)reload, reloaded, w, h);
	if (extra > 0)
		draw->UnloadImage(extra);
	extra = reload; // Keep one reference so the next frame proves reload pixels.
}

static void QDECL None(void)
{
	float v[2] = {0,0};
	unsigned int p[2] = {0,0};
	qhandle_t loaded;
	const char *path = getenv("P577_NONE_MARKER");
	FILE *marker = path ? fopen(path, "w") : NULL;
	int video = draw->GetVideoSize(v, p);
	Encode(0);
	Print("P577 NONE begin=1 video=%d\n", video);
	if (marker)
	{
		fprintf(marker, "P577 NONE begin=1 video=%d\n", video);
		fflush(marker); // Startup autoload precedes the engine's log setup.
	}
	loaded = draw->LoadImageData("p577/none", "image/tga", tga, sizeof(tga));
	Print("P577 NONE end=1 loaded=%ld\n", (long)loaded);
	if (marker)
	{
		fprintf(marker, "P577 NONE end=1 loaded=%ld\n", (long)loaded);
		fclose(marker);
	}
}

static void QDECL Video(int width, int height, qboolean restarted)
{
	(void)width;
	(void)height;
	videoevents++;
	if (restarted && uploads)
	{
		atlas = lookup = disk = extra = 0; // Old shader-table IDs are not persistent.
		Upload();
		Print("P577 VIDEO restart=1\n");
	}
}

static qboolean QDECL Menu(int event, int key, int unicode, float mousex, float mousey, float width, float height)
{
	(void)key; (void)unicode; (void)mousex; (void)mousey;
	if (event == 0)
	{
		frames++;
		draw->Colour4f(0, 0, 0, 1);
		draw->Fill(0, 0, width, height);
		draw->Colour4f(1, 0, 1, 1);
		draw->Fill(16, 16, 24, 24);
		draw->Colour4f(1, 1, 1, 1);
		draw->Image(64, 64, 128, 128, 0, 0, 1, 1, atlas);
		draw->Image(256, 64, 128, 128, 0, 0, 1, 1, disk);
		draw->Image(448, 64, 128, 128, 0, 0, 1, 1, lookup);
		if (extra > 0)
			draw->Image(64, 256, 128, 128, 0, 0, 1, 1, extra);
	}
	return true;
}

static void QDECL Shutdown(void)
{
	if (atlas > 0) draw->UnloadImage(atlas);
	if (lookup > 0) draw->UnloadImage(lookup);
	if (disk > 0) draw->UnloadImage(disk);
	if (extra > 0) draw->UnloadImage(extra);
	atlas = lookup = disk = extra = 0;
}

__declspec(dllexport) qboolean QDECL FTEPlug_Init(plugcorefuncs_t *funcs)
{
	core = funcs;
	draw = core->GetEngineInterface(plug2dfuncs_name, sizeof(*draw));
	input = core->GetEngineInterface(pluginputfuncs_name, sizeof(*input));
	cmd = core->GetEngineInterface(plugcmdfuncs_name, sizeof(*cmd));
	if (!draw || !input || !cmd)
		return false;
	Print("P577 INIT wrong_size_rejected=%d\n",
		core->GetEngineInterface(plug2dfuncs_name, sizeof(*draw) - sizeof(void *)) == NULL);
	if (!core->ExportFunction("MenuEvent", Menu) || !core->ExportFunction("UpdateVideo", Video)
		|| !core->ExportFunction("Shutdown", Shutdown))
		return false;
	if (!draw->GetVideoSize(NULL, NULL))
		None(); // Root autoload runs before normal client renderer initialization.
	return cmd->AddCommand("p577_open", Open, "Owned atlas fixture") &&
		cmd->AddCommand("p577_status", Status, "Atlas status") &&
		cmd->AddCommand("p577_replace", Replace, "Replace atlas") &&
		cmd->AddCommand("p577_invalid", Invalid, "Invalid input/handle probes") &&
		cmd->AddCommand("p577_lifetime", Lifetime, "Unload/reload atlas") &&
		cmd->AddCommand("p577_none", None, "No-renderer probe");
}
