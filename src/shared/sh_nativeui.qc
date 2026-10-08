//Optional explicit draw-site bridge. No automatic panel/input/preference changes.
//One owner per VM. Handles are VM-local and invalid after any native/VM reset.
float() ui_native_status = #0;
float(float owner) ui_native_open = #0;
float(float handle) ui_native_draw = #0;
float(float handle) ui_native_close = #0;

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
