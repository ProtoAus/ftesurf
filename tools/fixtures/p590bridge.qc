float probe_handle;
float probe_phase;
#ifdef MENU
string probe_vm = "menu";
string probe_own = "p590_menu_handle";
string probe_other = "p590_client_handle";
float probe_owner = 101;
#else
string probe_vm = "client";
string probe_own = "p590_client_handle";
string probe_other = "p590_menu_handle";
float probe_owner = 202;
#endif

void() Probe_Init =
{
	local float early;
	probe_phase = -1;
	early = NUI_Open(probe_owner);
	registercommand(strcat("p590_", probe_vm));
	print(sprintf("P590 QC INIT vm=%s available=%g outside_open=%g builtin=%g\n", probe_vm, NUI_Available(), early, checkbuiltin(ui_native_status)));
};

float(string text) Probe_Command =
{
	local float result, stale;
	tokenize(text);
	if (strcmp(argv(0), strcat("p590_", probe_vm)))
		return FALSE;
	result = 0;
	stale = 0;
#ifdef MENU
	if (!strcmp(argv(1), "hide")) { cvar_set("p590_menudraw", "0"); setkeydest(0); }
	if (!strcmp(argv(1), "show")) { cvar_set("p590_menudraw", "1"); setkeydest(2); }
#endif
	if (!strcmp(argv(1), "outside"))
		result = NUI_Draw(probe_handle);
	if (!strcmp(argv(1), "close"))
	{
		if (checkbuiltin(ui_native_close))
		{
			result = ui_native_close(probe_handle);
			stale = ui_native_draw(probe_handle);
		}
		probe_handle = 0;
	}
	print(sprintf("P590 QC COMMAND vm=%s command=%s handle=%g result=%g stale=%g\n", probe_vm, argv(1), probe_handle, result, stale));
	return TRUE;
};

vector(vector point, vector scale) Probe_Scale =
{
	point_x *= scale_x;
	point_y *= scale_y;
	return point;
};

void(vector screen) Probe_Draw =
{
	local vector scale;
	local float native, rejects, phase, foreign;
#ifdef MENU
	if (!cvar("p590_menudraw"))
		return;
#endif
	scale = '1 1 0';
	scale_x = screen_x / 320;
	scale_y = screen_y / 240;
	drawresetcliparea();
	drawfill('0 0 0', screen, '0 0 0', 1);
	drawfill(Probe_Scale('40 40 0', scale), Probe_Scale('160 120 0', scale), '1 0 0', 1); //QC before
	drawsetcliparea(60 * scale_x, 60 * scale_y, 90 * scale_x, 60 * scale_y);
	probe_handle = NUI_Open(probe_owner); //idempotent, reacquire after native resets
	native = 0;
	rejects = 0;
	if (NUI_Available())
	{
		if (!ui_native_open(0)) rejects += 1;
		if (!ui_native_open(0.5)) rejects += 1;
		if (probe_handle)
		{
			if (!ui_native_open(probe_owner + 1)) rejects += 1;
			if (!ui_native_draw(probe_handle + 0.5)) rejects += 1;
			foreign = cvar(probe_other);
			if (foreign)
				if (!ui_native_draw(foreign)) rejects += 1;
		}
	}
	if (probe_handle)
		native = NUI_Draw(probe_handle);
	if (native)
	{
		if (!NUI_Draw(probe_handle)) rejects += 1; //no second native draw this frame
	}
	else
	{
		NUI_Close(probe_handle);
		probe_handle = 0;
		drawfill(Probe_Scale('80 50 0', scale), Probe_Scale('120 100 0', scale), '1 1 0', 1); //acting legacy
	}
	drawfill(Probe_Scale('100 70 0', scale), Probe_Scale('30 40 0', scale), '0 0 1', 1); //QC after
	drawresetcliparea();
	drawfill(Probe_Scale('230 70 0', scale), Probe_Scale('30 40 0', scale), '1 1 1', 1); //restored state
	cvar_set(probe_own, ftos(probe_handle));
	phase = cvar("p590_phase");
	if (phase != probe_phase)
	{
		probe_phase = phase;
		print(sprintf("P590 QC DRAW vm=%s phase=%g available=%g handle=%g native=%g rejects=%g before=1 after=1 legacy=%g\n", probe_vm, phase, NUI_Available(), probe_handle, native, rejects, !native));
	}
};

#ifdef MENU
void() m_init = { Probe_Init(); };
void(vector size) m_draw = { Probe_Draw(size); };
void(float mode) m_toggle = { cvar_set("p590_menudraw", ftos(mode != 0)); setkeydest(mode ? 2 : 0); };
float(string text) m_consolecommand = { return Probe_Command(text); };
float(float type, float key, float unicode, float devid) m_inputevent = { return FALSE; };
void() m_shutdown = { print("P590 QC SHUTDOWN vm=menu\n"); };
#else
void(float level, string name, float version) CSQC_Init = { Probe_Init(); };
void() CSQC_Input_Frame = {};
#ifdef FULLVIEW
void(float width, float height, float notmenu) CSQC_UpdateView =
{
	local vector screen;
	screen = '0 0 0'; screen_x = width; screen_y = height;
	Probe_Draw(screen);
};
#else
void(vector size, float showscores) CSQC_DrawHud = { Probe_Draw(size); };
#endif
float(string text) CSQC_ConsoleCommand = { return Probe_Command(text); };
void() CSQC_Shutdown = { print("P590 QC SHUTDOWN vm=client\n"); };
#endif
