/*
  Patch 871: hud_fps -- the HUD's pure panels drawn into a render target at a capped rate and
  pasted every frame. 0 (the default) draws them every frame as before; N redraws N times a
  second; -1 once an input frame (clientcommandframe), the trainer's own sampling rate.

  Only panels that do nothing but draw are inside a layer (the Patch 871 audit: the trainer, the
  net panel and the boarding window in layer 0, the key strip and the missing-graphics note in
  layer 1). Everything between and around them still draws every frame in its old place, so the
  stacking is unchanged. Panels that keep state as they draw (speed's gain, the strafe bar's
  smoothing, the keys' and input display's latches, the timer's edge machine, chat) stay out.

  The engine's FTESURF_2D_COVERAGE makes a 2D target keep coverage in its alpha, so one target
  composites with blendfunc gl_one gl_one_minus_src_alpha to what drawing directly gives (up to
  8-bit rounding). Without it -- every released engine, Vulkan, D3D -- the layers draw directly.
  So do they while the HUD editor, a menu or the chat cursor is up, when 2D units are not the
  screen's pixels, and while the frame itself goes to an engine target (screenshot_mega, a capture):
  switching back from a layer's target returns to the screen, not to that target.
*/
#define VF_RT_COVERAGE  226     // engine Patch 871; not in fteqcc's table
#define HC_FMT          1       // RGBA8 (milk_sys.qc's MILK_FMT_RGBA8), negated for nearest

float hc_have;                  // 1 the engine can, -1 it cannot, 0 not asked yet
float hc_gen;                   // renderer generation: a restart drops targets and materials
float hc_matgen;                // the generation the materials were made for, plus one
float hc_mode;                  // this frame: 0 direct, 1 redraw then paste, 2 paste
float hc_why;                   // why direct: 1 off, 2 engine, 3 not 1:1, 4 editor or cursor, 5 engine target
float hc_valid;                 // bit per layer: its target holds this size's picture
float hc_next, hc_lastcf;       // the next timed redraw (at -1, the 10/s floor); clientcommandframe at the last
float hc_redraws, hc_pastes;    // for `hudcache`
vector hc_size;

void() HC_Register =
{
	registercvar("hud_fps", "-1", CVAR_ARCHIVE);
	registercommand("hudcache");
};

// CSQC_RendererRestarted: the targets and their materials are gone.
void() HC_Lost =
{
	hc_gen = hc_gen + 1;
	hc_valid = 0;
	hc_have = 0;                    // a restart can be a renderer switch: ask again
};

string(float l) HC_RT  = { return sprintf("hc_rt%g_%g", l, hc_gen); };
string(float l) HC_Mat = { return sprintf("hc_mat%g_%g", l, hc_gen); };

// fteqcc's own table has no VF_RT_COVERAGE, so it warns on the id (F333) in the next three.
#pragma warning disable F333

// Once a frame, before layer 0: direct, redraw or paste.
void() HC_Frame =
{
	local float r, l;
	local vector vs, ps;

	r = cvar("hud_fps");
	hc_mode = 0;
	hc_why = 1;
	if (!r)
	{
		hc_valid = 0;
		return;
	}
	if (r > 0 && r < 1)
		r = 1;
	if (!hc_have)
		hc_have = (checkextension("FTESURF_2D_COVERAGE") && Milk_Supported()) ? 1 : -1;
	vs = getproperty(VF_SCREENVSIZE);
	ps = getproperty(VF_SCREENPSIZE);
	if (hc_have < 0)
		hc_why = 2;
	else if (vs_x != ps_x || vs_y != ps_y || ps_x < 1 || ps_y < 1)
		hc_why = 3;
	else if (ui_he_open || UI_CursorHeld())
		hc_why = 4;
	else if (getproperty(VF_RT_COVERAGE) < 0 || (isdemo() && cvar("capturedemowidth") && cvar("capturedemoheight")))
		hc_why = 5;
	else
		hc_why = 0;
	if (hc_why)
	{
		hc_valid = 0;
		return;
	}
	if (hc_matgen != hc_gen + 1)
	{
		// Named per generation: a name drawn after a restart is a missing file for good (r_2d.c).
		for (l = 0; l < 2; l = l + 1)
			shaderforname(HC_Mat(l), sprintf("{\naffine\nnomipmaps\nprogram default2d\n{\nmap $rt:%s\nblendfunc gl_one gl_one_minus_src_alpha\nrgbgen vertex\nalphagen vertex\n}\n}\n",
			              HC_RT(l)));
		shaderforname(sprintf("hc_clr%g", hc_gen),
		              "{\nprogram default2d\n{\nmap $whiteimage\nblendfunc gl_zero gl_zero\nrgbgen vertex\nalphagen vertex\n}\n}\n");
		hc_matgen = hc_gen + 1;
	}
	if (ps != hc_size)
	{
		hc_size = ps;
		hc_valid = 0;
	}
	hc_mode = 2;
	if (hc_valid != 3)
		hc_mode = 1;
	else if (r < 0 && clientcommandframe != hc_lastcf)
		hc_mode = 1;
	else if (cltime >= hc_next || hc_next > cltime + 1)
		hc_mode = 1;                    // due, or the clock went back (a map change)
	if (hc_mode != 1)
		return;
	hc_lastcf = clientcommandframe;
	if (r < 0)
		hc_next = cltime + 0.1;          // a demo or a pause sends no input frames
	else
	{
		// Phase kept, so N a second is N on average at any frame rate; not after a hitch.
		hc_next = hc_next + 1 / r;
		if (hc_next < cltime || hc_next > cltime + 1)
			hc_next = cltime + 1 / r;
	}
	hc_redraws = hc_redraws + 1;
};

// TRUE when the caller should draw the layer's panels this frame (direct, or into the target).
float(float l) HC_Begin =
{
	if (hc_mode != 1)
		return hc_mode == 0;
	setproperty(VF_RT_COVERAGE, 0);         // flushes the screen's queued 2D first
	setproperty(VF_RT_DESTCOLOUR, HC_RT(l), 0 - HC_FMT, hc_size);
	setproperty(VF_RT_COVERAGE, 1);
	drawsubpic('0 0 0', hc_size, sprintf("hc_clr%g", hc_gen), '0 0 0', '1 1 0', '0 0 0', 0, 0);
	return TRUE;
};

// After the layer's panels: back to the screen, and paste the target.
void(float l) HC_End =
{
	if (!hc_mode)
		return;
	if (hc_mode == 1)
	{
		setproperty(VF_RT_COVERAGE, 0);
		setproperty(VF_RT_DESTCOLOUR, "");
		hc_valid = hc_valid | (l + 1);
	}
	drawsubpic('0 0 0', hc_size, HC_Mat(l), '0 0 0', '1 1 0', '1 1 1', 1, 0);
	hc_pastes = hc_pastes + 1;
};

#pragma warning enable F333

float(string cmd) HC_Command =
{
	tokenize(cmd);
	if (argv(0) != "hudcache")
		return FALSE;
	print(sprintf("hudcache: hud_fps %s engine %g mode %g why %g valid %g", cvar_string("hud_fps"),
	              hc_have, hc_mode, hc_why, hc_valid));
	print(sprintf(" size %v redraws %g pastes %g\n", hc_size, hc_redraws, hc_pastes));
	return TRUE;
};
