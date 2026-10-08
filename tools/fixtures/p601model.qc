float probe_handle, probe_phase, probe_revision, probe_requested;
float probe_enabled, probe_shape;
#ifdef MENU
string probe_vm = "menu";
float probe_owner = 103;
#else
string probe_vm = "client";
float probe_owner = 204;
#endif
float(float x, float y, float w, float h, vector rgb) Ink =
{
	return drawfill([x,y,0],[w,h,0],rgb,1,0);
};
float() Publish =
{
	float ok;
	ok = NUI_ModelBegin(probe_handle,probe_requested,3);
	if (!ok) return FALSE;
	ok = NUI_ModelWidget(probe_handle,0,'10 90 1',0,"Plain ## label");
	if (!ok) return FALSE;
	if (!probe_shape)
	{
		ok = NUI_ModelWidget(probe_handle,1,'11 91 2',0,"Button ### literal");
		if (!ok) return FALSE;
		ok = NUI_ModelWidget(probe_handle,2,'12 92 3',probe_enabled,"Checkbox");
	}
	else
	{
		ok = NUI_ModelWidget(probe_handle,1,'12 92 3',probe_enabled,"Checkbox");
		if (!ok) return FALSE;
		if (probe_shape == 1) ok = NUI_ModelWidget(probe_handle,2,'11 91 2',0,"Renamed button");
		else ok = NUI_ModelWidget(probe_handle,2,'21 191 2',0,"Replacement row");
	}
	if (!ok) return FALSE;
	ok = NUI_ModelCommit(probe_handle);
	if (ok) probe_revision = probe_requested;
	print(sprintf("P601 MODEL vm=%s revision=%g count=3 committed=%g shape=%g\n",probe_vm,probe_requested,ok,probe_shape));
	return ok;
};
void(vector screen) DrawProbe =
{
	float sx, sy, native, before, after, legacy, phase, i;
	vector action;
	native = 0; legacy = 0;
	sx = screen_x/640; sy = screen_y/480;
	drawresetcliparea(); drawfill('0 0 0',screen,'0 0 0',1);
	before = Ink(40*sx,40*sy,550*sx,390*sy,'1 0 0');
	drawsetcliparea(62*sx,62*sy,508*sx,346*sy);
	if (NUI_ModelAvailable())
	{
		if (!probe_handle) probe_handle = NUI_Open(probe_owner);
		if (probe_handle)
		{
			if (probe_revision != probe_requested) Publish();
			native = NUI_Draw(probe_handle);
			if (!native) { probe_handle = 0; probe_revision = 0; }
		}
	}
	if (native)
		for (i = 0; i < 16; i++)
		{
			action = NUI_ModelPoll(probe_handle,probe_revision);
			if (action_x)
			{
				print(sprintf("P601 ACTION vm=%s id=%g row=%g value=%g revision=%g\n",probe_vm,action_x,action_y,action_z,probe_revision));
				if (action_x == 12) { probe_enabled = action_z; probe_requested += 1; }
			}
		}
	if (!native) legacy = Ink(40*sx,40*sy,550*sx,390*sy,'1 1 0');
	drawresetcliparea();
	after = Ink(218*sx,168*sy,24*sx,24*sy,'0 0 1');
	Ink(592*sx,102*sy,18*sx,18*sy,'1 1 1');
	phase = cvar("p601_phase");
	if (phase != probe_phase)
	{
		probe_phase = phase;
		print(sprintf("P601 DRAW vm=%s phase=%g available=%g native=%g before=%g after=%g legacy=%g\n",probe_vm,phase,NUI_ModelAvailable(),native,before,after,legacy));
	}
};
void() InitProbe =
{
	probe_phase = -1; probe_requested = 1;
	registercommand(strcat("p601_",probe_vm));
	print(sprintf("P601 INIT vm=%s available=%g\n",probe_vm,NUI_ModelAvailable()));
};
float(string command) CommandProbe =
{
	float ok;
	tokenize(command);
	if (strcmp(argv(0),strcat("p601_",probe_vm))) return FALSE;
#ifdef MENU
	if (!strcmp(argv(1),"show")) { cvar_set("p601_menu_act","1"); setkeydest(2); }
	if (!strcmp(argv(1),"hide")) { cvar_set("p601_menu_act","0"); setkeydest(0); }
#endif
	if (!strcmp(argv(1),"stop"))
	{
		cvar_set(sprintf("p601_%s_act",probe_vm),"0");
		NUI_Close(probe_handle); probe_handle = 0;
	}
	if (!strcmp(argv(1),"close"))
	{
		NUI_Close(probe_handle); probe_handle = 0; probe_revision = 0;
	}
	if (!strcmp(argv(1),"reorder")) { probe_shape = 1; probe_requested += 1; }
	if (!strcmp(argv(1),"delete")) { probe_shape = 2; probe_requested += 1; }
	if (!strcmp(argv(1),"event"))
	{
		ok = NUI_Input(probe_handle,stof(argv(2)),stof(argv(3)),stof(argv(4)));
		print(sprintf("P601 INPUT vm=%s type=%s a=%s b=%s accepted=%g\n",probe_vm,argv(2),argv(3),argv(4),ok));
	}
	return TRUE;
};
#ifdef MENU
void() m_init = { InitProbe(); };
void(vector size) m_draw = { if (cvar("p601_menu_act")) DrawProbe(size); };
void(float mode) m_toggle = { setkeydest(mode ? 2 : 0); };
float(float type, float key, float unicode, float devid) m_inputevent = { return FALSE; };
float(string command) m_consolecommand = { return CommandProbe(command); };
#else
void(float level, string name, float version) CSQC_Init = { InitProbe(); };
void() CSQC_Input_Frame = {};
void(float width, float height, float showscores) CSQC_UpdateView =
{
	vector screen;
	screen = '0 0 0'; screen_x = width; screen_y = height;
	if (cvar("p601_client_act")) DrawProbe(screen);
};
float(string command) CSQC_ConsoleCommand = { return CommandProbe(command); };
#endif
