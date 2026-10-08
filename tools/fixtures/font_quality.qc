// Disposable MQC gallery, never part of the shipped menu.
float fq_loaded, fq_frames, fq_probe;
vector fq_ratio, fq_screen;

vector(vector physical) FQ_Virtual =
{
	return [physical_x / fq_ratio_x, physical_y / fq_ratio_y, 0];
};

void(vector position, vector size, vector colour) FQ_Fill =
{
	drawfill(FQ_Virtual(position), FQ_Virtual(size), colour, 1, 0);
};

void(vector position, string text, float pixels, vector colour, float alpha) FQ_Text =
{
	local float legacyfont;
	legacyfont = drawfont;
	drawfont = Font_NativeSlot(legacyfont);
	drawstring(FQ_Virtual(position), text, FQ_Virtual([pixels, pixels, 0]), colour, alpha, 0);
	drawfont = legacyfont;
};

void() m_init =
{
	registercvar("fq_mode", "0", 0);
	registercommand("fq_probe");
	registercommand("fq_open");
};
void() m_shutdown = {};
void(float mode) m_toggle =
{
	setkeydest(mode ? 2 : 0);
};
float(string command) m_consolecommand =
{
	tokenize(command);
	if (!strcmp(argv(0), "fq_open"))
	{
		setkeydest(2);
		return TRUE;
	}
	if (strcmp(argv(0), "fq_probe"))
		return FALSE;
	fq_probe = 1;
	return TRUE;
};

void(vector screensize) m_draw =
{
	local vector virtual, colour;
	local float side, face, rung, pixels, x, y, slot, calls, mode;
	local string name;

	fq_screen = getviewprop(VF_SCREENPSIZE);
	virtual = getviewprop(VF_SCREENVSIZE);
	if (fq_screen_x < 1280 || fq_screen_y < 720 || virtual_x <= 0 || virtual_y <= 0)
		return;
	fq_ratio = [fq_screen_x / virtual_x, fq_screen_y / virtual_y, 0];
	if (!fq_loaded)
	{
		Font_Init();
		fq_loaded = 1;
	}
	fq_frames = fq_frames + 1;
	mode = cvar("fq_mode");
	calls = 0;
	drawfontscale = '1 1 0';
	FQ_Fill('0 0 0', fq_screen, '0.08 0.08 0.08');
	FQ_Fill('16 16 0', '608 688 0', '0 0 0');
	FQ_Fill('656 16 0', '608 688 0', '1 1 1');
	// Fixed colour/geometry control; no text or changing phase label inside it.
	FQ_Fill('628 16 0', '24 24 0', '1 0 1');
	FQ_Fill('628 48 0', '24 24 0', '0 1 0');
	for (side = 0; side < 2; side = side + 1)
	{
		x = 32 + side * 640;
		colour = side ? '0 0 0' : '1 1 1';
		Font_Set(ui_font_ui);
		FQ_Text([x, 28, 0], "Native physical bakes | font / pixels / sample", 16, colour, 1);
		for (face = 0; face < 3; face = face + 1)
		{
			if (face == 0) { slot = ui_font_ui; name = "Roboto"; }
			else if (face == 1) { slot = ui_font_mono; name = "Google Sans Code Medium"; }
			else { slot = ui_font_dispsm; name = "Bebas Neue"; }
			for (rung = 0; rung < 4; rung = rung + 1)
			{
				pixels = 8 + rung * 4;
				if (rung == 3) pixels = 24;
				if (face == 2) pixels = 12 + rung * 4;
				y = 60 + face * 192 + rung * 48;
				Font_Set(ui_font_ui);
				FQ_Text([x, y, 0], sprintf("%s | %g px", name, pixels), 8, colour, 1);
				Font_Set(slot);
				if (mode == 1) pixels = pixels + 0.75; // Intentional resampling control.
				FQ_Text([x, y + 12, 0], "Hamburgefonts 0123 Il1 O0 /.,:;!?", pixels, colour, 1);
				calls = calls + 1;
				if (fq_probe)
					print(sprintf("fq_row %g %g %g slot %.0f physical %.6f %.6f",
						side, face, rung, Font_NativeSlot(slot), pixels, pixels),
						sprintf(" origin %g %g\n", x, y + 12));
			}
		}
		Font_Set(ui_font_ui);
		// QC takes straight RGB; the renderer premultiplies it, exactly once.
		FQ_Text([x, 650, 0], "Half alpha 0.5: Aa 09 !?", 16, colour, 0.5);
		FQ_Text([x, 678, 0], "No shadow, outline, blur or postprocess", 12, colour, 1);
	}
	Font_Reset();
	if (fq_probe)
	{
		print(sprintf("fq_state mode %g frames %g loads %g ready %g calls %g\n",
			mode, fq_frames, ui_font_tries, ui_font_ready, calls));
		print(sprintf("fq_native tries %g %g %g %g\n", ui_font_native_tries[0],
			ui_font_native_tries[1], ui_font_native_tries[2], ui_font_native_tries[3]));
		print(sprintf("fq_screen physical %g %g virtual %.6f %.6f ratio %.6f %.6f\n",
			fq_screen_x, fq_screen_y, virtual_x, virtual_y, fq_ratio_x, fq_ratio_y));
		print(sprintf("fq_settings linear %g mono %g outline %g smaller %g gamma %g contrast %g srgb %g\n",
			cvar("r_font_linear"), cvar("r_font_postprocess_mono"), cvar("r_font_postprocess_outline"),
			cvar("dpcompat_smallerfonts"), cvar("v_gamma"), cvar("v_contrast"), cvar("vid_srgb")));
		fq_probe = 0;
	}
};
