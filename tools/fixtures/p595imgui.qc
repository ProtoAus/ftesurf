float probe_handle;
float probe_phase;
#ifdef MENU
string probe_vm = "menu";
float probe_owner = 101;
#else
string probe_vm = "client";
float probe_owner = 202;
#endif
void() Probe_Init =
{
	probe_phase = -1;
	registercommand(strcat("p595_",probe_vm));
	print(sprintf("P595 INIT vm=%s available=%g\n",probe_vm,NUI_Available()));
};
float(string text) Probe_Command =
{
	tokenize(text);
	if (strcmp(argv(0),strcat("p595_",probe_vm))) return FALSE;
	if (!strcmp(argv(1),"close")) { NUI_Close(probe_handle); probe_handle = 0; }
#ifdef MENU
	if (!strcmp(argv(1),"show")) { cvar_set("p595_menudraw","1"); setkeydest(2); }
	if (!strcmp(argv(1),"hide")) { cvar_set("p595_menudraw","0"); setkeydest(0); }
#endif
	return TRUE;
};
vector(vector p, vector scale) Probe_Scale = { p_x *= scale_x; p_y *= scale_y; return p; };
void(vector screen) Probe_Draw =
{
	local vector scale;
	local float native, phase;
#ifdef MENU
	if (!cvar("p595_menudraw")) return;
#endif
	if (!cvar("p595_act")) return;
	scale = '1 1 0'; scale_x = screen_x/320; scale_y = screen_y/240;
	drawresetcliparea();
	drawfill('0 0 0',screen,'0 0 0',1);
	drawfill(Probe_Scale('10 10 0',scale),Probe_Scale('300 215 0',scale),'1 0 0',1);
	drawsetcliparea(30*scale_x,30*scale_y,255*scale_x,180*scale_y);
	probe_handle = NUI_Open(probe_owner);
	native = NUI_Draw(probe_handle);
	if (!native)
	{
		NUI_Close(probe_handle); probe_handle = 0;
		drawfill(Probe_Scale('20 20 0',scale),Probe_Scale('270 180 0',scale),'1 1 0',1);
	}
	drawfill(Probe_Scale('100 70 0',scale),Probe_Scale('30 40 0',scale),'0 0 1',1);
	drawresetcliparea();
	drawfill(Probe_Scale('295 45 0',scale),Probe_Scale('10 20 0',scale),'1 1 1',1);
	phase = cvar("p595_phase");
	if (phase != probe_phase)
	{
		probe_phase = phase;
		print(sprintf("P595 DRAW vm=%s phase=%g native=%g handle=%g before=1 after=1 legacy=%g\n",probe_vm,phase,native,probe_handle,!native));
	}
};
#ifdef MENU
void() m_init = { Probe_Init(); };
void(vector size) m_draw = { Probe_Draw(size); };
void(float mode) m_toggle = { setkeydest(mode ? 2 : 0); };
float(string text) m_consolecommand = { return Probe_Command(text); };
float(float type, float key, float unicode, float devid) m_inputevent = { return FALSE; };
void() m_shutdown = {};
#else
void(float level, string name, float version) CSQC_Init = { Probe_Init(); };
void() CSQC_Input_Frame = {};
void(float width, float height, float notmenu) CSQC_UpdateView =
{
	local vector screen;
	screen = '0 0 0'; screen_x = width; screen_y = height;
	Probe_Draw(screen);
};
float(string text) CSQC_ConsoleCommand = { return Probe_Command(text); };
void() CSQC_Shutdown = {};
#endif
