/*
  Patch 610: what the strafe trainer and the run graphs are drawn with, so the
  HUD's instruments are one look. The panel is the key menus' (cl_saveloc.qc):
  SUI_THEME_PANEL at 0.90, a 5-unit radius, a header band over a hairline. `u`
  is a panel's unit: its text size / 8, which is hud_scale until that element's
  size knob is set.

  Curves are cl_lines.qc's anti-aliased strip. `drawline` is not usable for
  them: the engine ignores its width (pr_menu.c:1089) and draws one aliased
  hardware line per call, a draw call each.

  ORDER: fills and text, then every curve, then a fill, then text. A drawstring
  issued between two polygon batches does not appear (the note over ln_lab_p).
*/

// cl_lines.qc compiles after this file.
void(float w) Line_Width;
void() Line_PxFrame;
void(vector a, vector sa, vector ca, float la, vector b, vector sb, vector cb, float lb) Line_Emit;

#define PLOT_BAND 15            // the header band, units

/*
  A unit is a whole or a half pixel count (the UI face's ladder steps by 4, so
  u is n/2): EVEN multiples of u are whole pixels and the layouts advance by
  those. What is left over, a centred string or an odd offset, goes through
  these: text that starts on a half pixel is resampled and blurs, and the
  owner runs the trainer at 20 px, where u is 2.5.
*/
void(vector pos, string s, float sz, vector rgb, float a) Plot_Text =
{
	HUD_Text(_sui_pixel_align(pos), s, sz, rgb, a);
};

void(vector pos, string s, float sz, vector rgb, float a) Plot_TextR =
{
	sz = Font_Px(sz);
	pos_x = pos_x - stringwidth(s, TRUE, [sz, sz]);
	HUD_Text(_sui_pixel_align(pos), s, sz, rgb, a);
};

void(vector pos, string s, float sz, vector rgb, float a) Plot_TextC =
{
	sz = Font_Px(sz);
	pos_x = pos_x - stringwidth(s, TRUE, [sz, sz]) * 0.5;
	HUD_Text(_sui_pixel_align(pos), s, sz, rgb, a);
};

void(vector p, vector size, float u) Plot_Panel =
{
	_sui_round_draw(p, size, 5 * u, SUI_THEME_PANEL, 0.90);
};

// The header band: the panel's name, what it is reading, a hairline. Returns
// the height it took.
float(vector p, float w, float u, float sz, string title, string right, vector rc) Plot_Header =
{
	local float y;

	y = p_y + 3 * u + (PLOT_BAND * u - 2 * u - sz) * 0.5;
	Plot_Text([p_x + 6 * u, y], title, sz, SUI_THEME_TEXT, 1);
	if (right != "")
		Plot_TextR([p_x + w - 6 * u, y], right, sz, rc, 1);
	drawfill([p_x + 4 * u, p_y + 16 * u], [w - 8 * u, 1], SUI_THEME_EDGE_HI, 0.7, 0);
	return 3 * u + PLOT_BAND * u;
};

// A run's colour, by run-line slot: 0 is the open replay, 1..8 the board's.
vector(float s) Plot_Series =
{
	if (s == 0) return SUI_THEME_TEXT;
	if (s == 1) return SUI_THEME_ACCENT;
	if (s == 2) return SUI_THEME_FOCUS;
	if (s == 3) return SUI_THEME_GOOD;
	if (s == 4) return SUI_THEME_ACCENT2;
	if (s == 5) return SUI_THEME_BAD;
	if (s == 6) return SUI_THEME_INFO;
	if (s == 7) return SUI_THEME_WARN;
	return '0.780 0.890 0.600';
};

// HUD_QualityColor's five bands, in the panel palette.
vector(float q) Plot_Quality =
{
	if (q < 0)    return SUI_THEME_MUTED;       // no answer
	if (q > 0.96) return SUI_THEME_GOOD;
	if (q > 0.85) return '0.780 0.890 0.600';
	if (q > 0.65) return SUI_THEME_WARN;
	if (q > 0.40) return SUI_THEME_FOCUS;
	return SUI_THEME_BAD;
};

// A round step giving about `n` divisions of `span`: 1, 2 or 5 times a power of ten.
float(float span, float n) Plot_Step =
{
	local float raw, mag, i;

	if (span <= 0 || n < 1)
		return 1;
	raw = span / n;
	mag = 1;
	for (i = 0; i < 40 && raw >= 10; i = i + 1) { raw = raw / 10; mag = mag * 10; }
	for (i = 0; i < 40 && raw < 1;   i = i + 1) { raw = raw * 10; mag = mag / 10; }
	if (raw > 5) return 10 * mag;
	if (raw > 2) return 5 * mag;
	if (raw > 1) return 2 * mag;
	return mag;
};

// The same for a time axis, in seconds: steps a clock is read in.
float(float span, float n) Plot_TimeStep =
{
	local float raw;

	raw = span / max(1, n);
	if (raw <= 1)
		return Plot_Step(span, n);
	if (raw <= 2)   return 2;
	if (raw <= 5)   return 5;
	if (raw <= 10)  return 10;
	if (raw <= 15)  return 15;
	if (raw <= 30)  return 30;
	if (raw <= 60)  return 60;
	if (raw <= 120) return 120;
	if (raw <= 300) return 300;
	return 600;
};

// m:ss, with tenths when the axis steps by less than a second and hundredths
// under a tenth (a 0.25 s view steps by 0.05 or 0.02, and tenths repeated).
string(float t, float step) Plot_Clock =
{
	local float m, s;

	if (t < 0)
		return strcat("-", Plot_Clock(0 - t, step));
	if (step < 0.1)
	{
		t = floor(t * 100 + 0.5) / 100;
		m = floor(t / 60);
		s = t - m * 60;
		return sprintf("%g:%s%.2f", m, (s < 10) ? "0" : "", s);
	}
	if (step >= 1)
	{
		t = floor(t + 0.5);
		m = floor(t / 60);
		return sprintf("%g:%02g", m, t - m * 60);
	}
	t = floor(t * 10 + 0.5) / 10;
	m = floor(t / 60);
	s = t - m * 60;
	return sprintf("%g:%s%.1f", m, (s < 10) ? "0" : "", s);
};

// ---- the strip: Line_Q's mitre (cl_lines.qc), without the world line's counters

float  plot_rn, plot_a, plot_px;
vector plot_q0, plot_q1, plot_s0, plot_n1, plot_c;

// A strip `wpx` physical pixels wide. Sets cl_lines.qc's width state.
void(float wpx, vector col, float alpha) Plot_Strip =
{
	local vector ps, vs;

	ps = getproperty(VF_SCREENPSIZE);
	vs = getproperty(VF_SCREENVSIZE);
	plot_px = (ps_x > 0) ? (vs_x / ps_x) : 1;
	Line_PxFrame();
	Line_Width(wpx);
	plot_rn = 0;
	plot_c = col;
	plot_a = alpha;
};

void() Plot_StripEnd =
{
	if (plot_rn >= 2)
		Line_Emit(plot_q0, plot_s0, plot_c, plot_a, plot_q1, plot_n1, plot_c, plot_a);
	plot_rn = 0;
};

void(vector q) Plot_Q =
{
	local vector d, n, m;
	local float l, k;

	if (plot_rn == 0)
	{
		plot_rn = 1;
		plot_q1 = q;
		return;
	}
	d = q - plot_q1;
	d_z = 0;
	l = vlen(d);
	if (l < 0.25 * plot_px)
		return;
	n = [d_y, 0 - d_x, 0] * (1 / l);
	if (plot_rn == 1)
		plot_s0 = n;
	else
	{
		m = plot_n1 + n;
		l = vlen(m);
		if (l < 0.1)
			m = n;                  // doubled back: no mitre to take
		else
		{
			m = m * (1 / l);
			k = m * n;
			m = m * (1 / ((k > 0.5) ? k : 0.5));
		}
		Line_Emit(plot_q0, plot_s0, plot_c, plot_a, plot_q1, m, plot_c, plot_a);
		plot_s0 = m;
	}
	plot_q0 = plot_q1;
	plot_q1 = q;
	plot_n1 = n;
	plot_rn = 2;
};
