//Optional explicit draw-site bridge. No automatic panel/input/preference changes.
//One owner per VM. Handles are VM-local and invalid after any native/VM reset.
float() ui_native_status = #0;
float(float owner) ui_native_open = #0;
float(float handle) ui_native_draw = #0;
float(float handle) ui_native_close = #0;
float() ui_native_input_status = #0;
float(float handle, float type, float a, float b) ui_native_input = #0;
vector(float handle) ui_native_poll = #0;

float() NUI_Available =
{
	//QC does not short-circuit; never call an optional builtin in an && arm.
	if (!checkbuiltin(ui_native_status))
		return FALSE;
	if (!checkbuiltin(ui_native_open))
		return FALSE;
	if (!checkbuiltin(ui_native_draw))
		return FALSE;
	if (!checkbuiltin(ui_native_close))
		return FALSE;
	return ui_native_status();
};

//Optional scalar events; caller owns cursor/focus/input routing. Coordinates are
//physical pixels, not QC virtual units. Never forward engine binds/scancodes.
float() NUI_InputAvailable =
{
	if (!NUI_Available())
		return FALSE;
	if (!checkbuiltin(ui_native_input_status))
		return FALSE;
	if (!checkbuiltin(ui_native_input))
		return FALSE;
	if (!checkbuiltin(ui_native_poll))
		return FALSE;
	return ui_native_input_status();
};

float(float handle, float type, float a, float b) NUI_Input =
{
	if (handle <= 0)
		return FALSE;
	if (!NUI_InputAvailable())
		return FALSE;
	return ui_native_input(handle,type,a,b);
};

//id / owner generation / scalar value; zero means empty/unavailable.
//Poll only after successful Draw, before leaving that VM's draw callback.
vector(float handle) NUI_Poll =
{
	if (handle <= 0)
		return '0 0 0';
	if (!NUI_InputAvailable())
		return '0 0 0';
	return ui_native_poll(handle);
};

//Open and Draw are authorized only during the engine's MQC/CSQC draw callback.
//A zero return means the caller should draw its usable legacy panel instead.
float(float owner) NUI_Open =
{
	if (!NUI_Available())
		return 0;
	return ui_native_open(owner);
};

float(float handle) NUI_Draw =
{
	if (handle <= 0)
		return FALSE;
	if (!NUI_Available())
		return FALSE;
	return ui_native_draw(handle);
};

void(float handle) NUI_Close =
{
	if (handle <= 0)
		return;
	if (checkbuiltin(ui_native_close))
		ui_native_close(handle);
};
