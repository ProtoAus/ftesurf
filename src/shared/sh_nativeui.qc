//Optional explicit draw-site bridge. No automatic panel/input/preference changes.
//One owner per VM. Handles are VM-local and invalid after any native/VM reset.
float() ui_native_status = #0;
float() ui_native_gamefocus = #0;

float() NUI_GameFocus =
{
	if (!checkbuiltin(ui_native_gamefocus)) return FALSE;
	return ui_native_gamefocus();
};
float(float owner) ui_native_open = #0;
float(float handle) ui_native_draw = #0;
float(float handle) ui_native_close = #0;
float() ui_native_input_status = #0;
float(float handle, float type, float a, float b) ui_native_input = #0;
vector(float handle) ui_native_poll = #0;
float() ui_native_model_status = #0;
float() ui_native_model_limit = #0;
float(float handle, float revision, float count) ui_native_model_begin = #0;
float(float handle, float index, vector identity, float value, string label) ui_native_model_widget = #0;
float(float handle) ui_native_model_commit = #0;
vector(float handle, float revision) ui_native_model_poll = #0;
float() ui_native_plot_status = #0;
float(float handle, float revision, float series) ui_native_plot_begin = #0;
float(float handle, float index, vector spec, vector rgb) ui_native_plot_series = #0;
float(float handle, float index, float *x, float *a, float *b, float *brk, float count, float xoffset) ui_native_plot_rows = #0;
float(float handle) ui_native_plot_commit = #0;
float(float handle, vector mark, vector masks, vector range) ui_native_plot_view = #0;

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

//Immutable counted models: widget/row/revision IDs are stable positive integers.
//Stage ordered indices 0..count-1, then commit before draw. Never poll old revisions.
float() NUI_ModelAvailable =
{
	if (!NUI_InputAvailable()) return FALSE;
	if (!checkbuiltin(ui_native_model_status)) return FALSE;
	if (!checkbuiltin(ui_native_model_begin)) return FALSE;
	if (!checkbuiltin(ui_native_model_widget)) return FALSE;
	if (!checkbuiltin(ui_native_model_commit)) return FALSE;
	if (!checkbuiltin(ui_native_model_poll)) return FALSE;
	return ui_native_model_status();
};
float() NUI_ModelLimit =
{
	//Old engines know only the exact-size /1 ABI; no optimistic oversized send.
	if (checkbuiltin(ui_native_model_limit)) return ui_native_model_limit();
	return 64;
};

float(float handle, float revision, float count) NUI_ModelBegin =
{
	if (!handle) return FALSE;
	if (!NUI_ModelAvailable()) return FALSE;
	return ui_native_model_begin(handle,revision,count);
};
float(float handle, float index, vector identity, float value, string label) NUI_ModelWidget =
{
	if (!handle) return FALSE;
	if (!NUI_ModelAvailable()) return FALSE;
	return ui_native_model_widget(handle,index,identity,value,label);
};
float(float handle) NUI_ModelCommit =
{
	if (!handle) return FALSE;
	if (!NUI_ModelAvailable()) return FALSE;
	return ui_native_model_commit(handle);
};
vector(float handle, float revision) NUI_ModelPoll =
{
	if (!handle) return '0 0 0';
	if (!NUI_ModelAvailable()) return '0 0 0';
	return ui_native_model_poll(handle,revision); //widget ID, row ID, typed value
};

//Counted sample series for a plot owner (Patch 614). Stage inside the VM's draw
//callback: begin(handle,revision,series), then per series its header
//(spec = [flags, gap, 0]: 1 = has a second value, 2 = carries the marker) and its
//rows by pointer, then commit. The engine bounds-checks the pointers against VM
//memory, copies and validates; view() carries what moves between revisions
//(mark = [x, shown, caption px], masks = [hidden, emphasis, 0] by series bit,
//range = [serial, x0, x1]). After this says yes the six are called bare.
float() NUI_PlotAvailable =
{
	if (!NUI_InputAvailable()) return FALSE;
	if (!checkbuiltin(ui_native_plot_status)) return FALSE;
	if (!checkbuiltin(ui_native_plot_begin)) return FALSE;
	if (!checkbuiltin(ui_native_plot_series)) return FALSE;
	if (!checkbuiltin(ui_native_plot_rows)) return FALSE;
	if (!checkbuiltin(ui_native_plot_commit)) return FALSE;
	if (!checkbuiltin(ui_native_plot_view)) return FALSE;
	return ui_native_plot_status();
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
