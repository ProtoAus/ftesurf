/* Shared SUI chrome. Existing controls/IDs and the gameplay HUD stay unchanged. */

/*
  The palette (Patch 606): one dark slate ramp and seven pastel accents, read by
  every restyled panel in both VMs. The ImGui scoreboard provider carries the
  same values (plugins/ui_imgui/scores.inc, `Dusk`); change them together.
  Surfaces darkest to lightest: WELL, PANEL, CHIP, HOVER, PRESSED.
  Patch 607 removed the look this replaced and its `ui_style` switch; it is in
  git at 562a6c9 and earlier.
*/
#define SUI_THEME_WELL     '0.075 0.078 0.110'
#define SUI_THEME_PANEL    '0.102 0.110 0.149'
#define SUI_THEME_CHIP     '0.141 0.153 0.208'
#define SUI_THEME_HOVER    '0.184 0.200 0.275'
#define SUI_THEME_PRESSED  '0.231 0.251 0.345'
#define SUI_THEME_SELECTED '0.200 0.262 0.361'   // CHIP tinted with ACCENT
#define SUI_THEME_EDGE     '0.204 0.220 0.286'   // hairlines
#define SUI_THEME_EDGE_HI  '0.314 0.337 0.435'
#define SUI_THEME_TEXT     '0.882 0.894 0.949'
#define SUI_THEME_DIM      '0.651 0.671 0.761'
#define SUI_THEME_MUTED    '0.435 0.459 0.565'
#define SUI_THEME_ACCENT   '0.549 0.769 0.973'   // sky
#define SUI_THEME_ACCENT2  '0.737 0.667 0.961'   // lilac
#define SUI_THEME_GOOD     '0.608 0.890 0.710'   // mint
#define SUI_THEME_WARN     '0.961 0.867 0.588'   // butter
#define SUI_THEME_FOCUS    '0.973 0.749 0.596'   // peach
#define SUI_THEME_BAD      '0.961 0.624 0.690'   // rose
#define SUI_THEME_INFO     '0.561 0.863 0.839'   // aqua
#define SUI_THEME_GOOD_BG  '0.225 0.286 0.298'   // CHIP tinted with GOOD
#define SUI_THEME_BAD_BG   '0.321 0.257 0.314'   // CHIP tinted with BAD
#define SUI_THEME_LINE     SUI_THEME_ACCENT

// Inline colour escapes for text that mixes colours in one string.
#define SUI_ESC_GOOD  "^x9eb"
#define SUI_ESC_BAD   "^xf9b"
#define SUI_ESC_WARN  "^xfd9"
#define SUI_ESC_MUTED "^x79a"
#define SUI_TIP_LINES 24

float sui_style_focused, sui_style_mouse_focus, sui_style_key_focus;
float sui_round_checked, sui_round_available;
float sui_round_calls;
float sui_style_frames, sui_style_quads;
vector sui_style_screen, sui_style_pixel_ratio;
float sui_style_text_calls;
vector sui_tip_glyph_size;
float sui_tip_native_pixels;
string sui_tip_candidate_id, sui_tip_candidate_text;
float sui_tip_candidate_scale;
string sui_tip_id, sui_tip_text;
string sui_tip_lines[SUI_TIP_LINES];
float sui_tip_count, sui_tip_since;
float sui_tip_scale, sui_tip_font, sui_tip_width, sui_tip_maxlines, sui_tip_wraps;
float sui_tip_visible;
vector sui_tip_pos, sui_tip_size;

void() sui_style_init =
{
	sui_style_focused = TRUE;
	sui_style_mouse_focus = TRUE;
	sui_style_key_focus = TRUE;
	// DP archive=1<<5, in both VMs (MENU has no CVAR_ARCHIVE macro).
	registercvar("ui_tooltip_delay", "0.35", 32);
};

void() sui_tooltip_reset =
{
	local float i;
	for (i = 0; i < sui_tip_count; i += 1)
	{
		strunzone(sui_tip_lines[i]);
		sui_tip_lines[i] = "";
	}
	if (strcmp(sui_tip_id, "") != 0) strunzone(sui_tip_id);
	if (strcmp(sui_tip_text, "") != 0) strunzone(sui_tip_text);
	sui_tip_id = "";
	sui_tip_text = "";
	sui_tip_count = 0;
	sui_tip_visible = FALSE;
	sui_tip_candidate_id = "";
	sui_tip_candidate_text = "";
};

void(float width, float height) _sui_style_metrics =
{
	local vector pixels;
	pixels = getproperty(VF_SCREENPSIZE);
	if (pixels_x <= 0 || pixels_y <= 0) pixels = [width, height, 0];
	sui_style_pixel_ratio = [max(1, pixels_x) / max(1, width), max(1, pixels_y) / max(1, height), 0];
	sui_style_screen = [width, height, 0];
};

void(float width, float height) sui_style_begin =
{
	_sui_style_metrics(width, height);
	sui_style_text_calls = 0;
	sui_style_frames += 1;
	sui_tip_candidate_id = "";
	sui_tip_candidate_text = "";
	sui_tip_visible = FALSE;
	sui_round_calls = 0;
};

// For a panel drawn in the HUD stack, outside any sui bracket: the pixel ratio
// only. No frame, action or tooltip state is touched.
void(vector scr) sui_style_hud =
{
	_sui_style_metrics(scr_x, scr_y);
};

// Snap the PHYSICAL glyph height to the selected face's baked ladder, then
// convert back to virtual units. Geometry can scale; glyphs are not stretched.
vector(float want) sui_native_text_size =
{
	local float pixels;
	pixels = Font_Px(want * sui_style_pixel_ratio_y);
	if (!drawfont) pixels = 8; // native bitmap fallback, not a scaled bitmap
	return [pixels / sui_style_pixel_ratio_x, pixels / sui_style_pixel_ratio_y, 0];
};

vector(vector pos) _sui_pixel_align =
{
	return [floor(pos_x * sui_style_pixel_ratio_x + 0.5) / sui_style_pixel_ratio_x,
		floor(pos_y * sui_style_pixel_ratio_y + 0.5) / sui_style_pixel_ratio_y, 0];
};

void(vector pos, string text, float want, vector color, float alpha) sui_native_text =
{
	local vector size;
	local float legacyfont;
	legacyfont = drawfont;
	drawfont = Font_NativeSlot(legacyfont);
	size = sui_native_text_size(want);
	sui_transform_box(pos, size);
	pos = _sui_pixel_align(pos);
	drawstring(pos, text, size, color, alpha, 0);
	drawfont = legacyfont;
	sui_style_text_calls += 1;
};

// Raw screen coordinates; the public wrapper transforms exactly once.
void(vector pos, vector size, float radius, vector color, float alpha) _sui_round_draw =
{
	local float dw, dh, r;
	if (size_x <= 0 || size_y <= 0) return;
	r = max(0, min(radius, min(size_x, size_y) * 0.5));
	if (!sui_round_checked)
	{
		sui_round_checked = TRUE;
		sui_round_available = (strcmp(precache_pic("gfx/ui/roundmask.png", 512), "") != 0);
	}
	if (!sui_round_available || r <= 0)
	{
		drawfill(pos, size, color, alpha, 0);
		return;
	}
	sui_round_calls += 1;
	/*
	  32x32 mask, radius 8: the corners scale, the edges and the centre stay
	  opaque. Written out cell by cell (Patch 610): the 3x3 loop this replaces
	  spent 450 ops a box deciding which of nine cells it was in, and the
	  trainer and the run graphs draw a score of boxes a frame during play.
	*/
	dw = size_x - 2 * r;
	dh = size_y - 2 * r;
	drawsubpic(pos, [r, r, 0], "gfx/ui/roundmask.png", '0 0 0', '0.25 0.25 0', color, alpha, 0);
	drawsubpic(pos + [size_x - r, 0, 0], [r, r, 0], "gfx/ui/roundmask.png", '0.75 0 0', '0.25 0.25 0', color, alpha, 0);
	drawsubpic(pos + [0, size_y - r, 0], [r, r, 0], "gfx/ui/roundmask.png", '0 0.75 0', '0.25 0.25 0', color, alpha, 0);
	drawsubpic(pos + [size_x - r, size_y - r, 0], [r, r, 0], "gfx/ui/roundmask.png", '0.75 0.75 0', '0.25 0.25 0', color, alpha, 0);
	sui_style_quads += 4;
	if (dw > 0)
	{
		drawsubpic(pos + [r, 0, 0], [dw, r, 0], "gfx/ui/roundmask.png", '0.25 0 0', '0.5 0.25 0', color, alpha, 0);
		drawsubpic(pos + [r, size_y - r, 0], [dw, r, 0], "gfx/ui/roundmask.png", '0.25 0.75 0', '0.5 0.25 0', color, alpha, 0);
		sui_style_quads += 2;
	}
	if (dh > 0)
	{
		drawsubpic(pos + [0, r, 0], [r, dh, 0], "gfx/ui/roundmask.png", '0 0.25 0', '0.25 0.5 0', color, alpha, 0);
		drawsubpic(pos + [size_x - r, r, 0], [r, dh, 0], "gfx/ui/roundmask.png", '0.75 0.25 0', '0.25 0.5 0', color, alpha, 0);
		sui_style_quads += 2;
		if (dw > 0)
		{
			drawsubpic(pos + [r, r, 0], [dw, dh, 0], "gfx/ui/roundmask.png", '0.25 0.25 0', '0.5 0.5 0', color, alpha, 0);
			sui_style_quads += 1;
		}
	}
};

void(vector pos, vector size, float radius, vector color, float alpha) sui_roundbox =
{
	sui_transform_box(pos, size);
	_sui_round_draw(pos, size, radius, color, alpha);
};

void(vector pos, vector size, float radius, vector fill, vector border, float alpha) sui_style_box =
{
	sui_transform_box(pos, size);
	_sui_round_draw(pos, size, radius, border, alpha);
	_sui_round_draw(pos + '1 1 0', size - '2 2 0', max(0, radius - 1), fill, alpha);
};

// A modal panel: a stepped drop shadow, a hairline and the fill. The mask has
// hard straight edges, so the shadow is three widening translucent boxes.
void(vector pos, vector size, float radius, float alpha) sui_style_panel =
{
	sui_transform_box(pos, size);
	_sui_round_draw(pos + '-7 -4 0', size + '14 16 0', radius + 7, '0 0 0', 0.07 * alpha);
	_sui_round_draw(pos + '-4 -2 0', size + '8 9 0', radius + 4, '0 0 0', 0.12 * alpha);
	_sui_round_draw(pos + '-2 -1 0', size + '4 4 0', radius + 2, '0 0 0', 0.18 * alpha);
	_sui_round_draw(pos, size, radius, SUI_THEME_EDGE, alpha);
	_sui_round_draw(pos + '1 1 0', size - '2 2 0', max(0, radius - 1), SUI_THEME_PANEL, alpha);
};

// The scroll thumb: half the gutter, rounded, with a three-line grip where it is
// long enough to carry one (Patch 610; sui_scrollbar keeps it long enough to hold).
void(vector pos, vector size, float hot) sui_style_thumb =
{
	local float w, x, y, i;
	sui_transform_box(pos, size);
	w = max(3, floor(size_x * 0.5));
	x = pos_x + size_x - w - 1;
	_sui_round_draw([x, pos_y + 1, 0], [w, max(w, size_y - 2), 0], w * 0.5,
		hot ? SUI_THEME_ACCENT : SUI_THEME_EDGE_HI, 1);
	if (size_y < w * 4)
		return;
	y = floor(pos_y + size_y * 0.5) - 3;
	for (i = 0; i < 3; i += 1)
		drawfill([x + 1, y + i * 3, 0], [w - 2, 1, 0], SUI_THEME_WELL, 0.7, 0);
};

void(string id, string text, float scale) sui_tooltip_for =
{
	if (_holding_click) return;
	if (strcmp(text, "") == 0) return;
	// A mouse's hover only: the keyboard cursor rests on a control from the moment
	// a menu opens, and a tip nobody asked for covers its neighbours.
	if (!_cursor_is_mouse_active) return;
	if (!sui_is_hovered(id)) return;
	// Last matching control wins, like SUI's hit list. These are frame-local.
	sui_tip_candidate_id = id;
	sui_tip_candidate_text = text;
	sui_tip_candidate_scale = max(0.5, scale);
};

// Cached only when text, face, scale or wrap width changes. Substring/strlen
// follow the VM's character encoding; no tokenizer state is changed here.
void(float width, vector fontsize, float maxlines) _sui_tooltip_wrap =
{
	local float i, start, at, fit, space, n;
	local string line, ch;
	for (i = 0; i < sui_tip_count; i += 1) strunzone(sui_tip_lines[i]);
	sui_tip_count = 0;
	sui_tip_wraps += 1;
	n = strlen(sui_tip_text);
	start = 0;
	while (start < n && sui_tip_count < maxlines)
	{
		fit = 0; space = 0;
		at = start;
		while (at < n)
		{
			ch = substring(sui_tip_text, at, 1);
			if (strcmp(ch, "\n") == 0) break;
			line = substring(sui_tip_text, start, at - start + 1);
			if (stringwidth(line, TRUE, fontsize) > width) break;
			fit = at - start + 1;
			if (strcmp(ch, " ") == 0) space = fit;
			at += 1;
		}
		if (at < n)
		if (strcmp(substring(sui_tip_text, at, 1), "\n") != 0)
		if (space > 0) fit = space;
		if (fit < 1) fit = 1;
		line = substring(sui_tip_text, start, fit);
		if (sui_tip_count == maxlines - 1)
		if (start + fit < n)
		{
			while (fit > 1 && stringwidth(strcat(line, "..."), TRUE, fontsize) > width)
			{
				fit -= 1;
				line = substring(line, 0, fit);
			}
			line = strcat(line, "...");
		}
		sui_tip_lines[sui_tip_count] = strzone(line);
		sui_tip_count += 1;
		start += max(1, fit);
		while (start < n && strcmp(substring(sui_tip_text, start, 1), " ") == 0) start += 1;
		if (strcmp(substring(sui_tip_text, start, 1), "\n") == 0) start += 1;
	}
};

void() _sui_tooltip_finish =
{
	local float now, sc, fs, width, maxlines, i, wasclip;
	local vector pos, size, clipmin, clipmax, glyph;
	local string text, id;
	now = gettime();
#ifdef MENU
	if (getkeydest() != 2) sui_tip_candidate_id = "";
#else
	if (!sui_style_focused) sui_tip_candidate_id = "";
#endif
	if (_holding_click || strcmp(sui_tip_candidate_id, "") == 0)
	{
		sui_tooltip_reset();
		return;
	}
	sc = sui_tip_candidate_scale;
	glyph = sui_native_text_size(8 * sc);
	fs = glyph_y;
	width = min(320 * sc, sui_style_screen_x - 16 * sc);
	maxlines = min(SUI_TIP_LINES, floor((sui_style_screen_y - 16 * sc) / (fs + 3 * sc)));
	if (width < fs || maxlines < 1) { sui_tooltip_reset(); return; }
	text = substring(sui_tip_candidate_text, 0, 2048);
	id = sui_tip_candidate_id;
	if (strcmp(sui_tip_id, id) != 0
		|| strcmp(sui_tip_text, text) != 0 || sui_tip_scale != sc
		|| sui_tip_font != drawfont || sui_tip_width != width || sui_tip_maxlines != maxlines
		|| sui_tip_glyph_size != glyph)
	{
		sui_tooltip_reset();
		sui_tip_id = strzone(id);
		sui_tip_text = strzone(text);
		sui_tip_scale = sc;
		sui_tip_font = drawfont;
		sui_tip_width = width;
		sui_tip_maxlines = maxlines;
		sui_tip_glyph_size = glyph;
		sui_tip_native_pixels = fs * sui_style_pixel_ratio_y;
		sui_tip_since = now;
		_sui_tooltip_wrap(width - 12 * sc, glyph, maxlines);
	}
	if (now - sui_tip_since < bound(0, cvar("ui_tooltip_delay"), 2)) return;

	size = [12 * sc, sui_tip_count * (fs + 3 * sc) + 9 * sc, 0];
	for (i = 0; i < sui_tip_count; i += 1)
		size_x = max(size_x, stringwidth(sui_tip_lines[i], TRUE, glyph) + 12 * sc);
	pos = _cursor_position + [14 * sc, 18 * sc, 0];
	if (pos_y + size_y > sui_style_screen_y) pos_y = _cursor_position_y - size_y - 6 * sc;
	pos_x = bound(0, pos_x, max(0, sui_style_screen_x - size_x));
	pos_y = bound(0, pos_y, max(0, sui_style_screen_y - size_y));
	wasclip = _sui_is_clipping;
	clipmin = _sui_clip_area_mins;
	clipmax = _sui_clip_area_maxs;
	drawresetcliparea();
	_sui_round_draw(pos + '-2 -1 0', size + '4 4 0', 4 * sc + 2, '0 0 0', 0.22);
	_sui_round_draw(pos, size, 4 * sc, SUI_THEME_EDGE_HI, 1);
	_sui_round_draw(pos + '1 1 0', size - '2 2 0', max(0, 4 * sc - 1), SUI_THEME_CHIP, 1);
	for (i = 0; i < sui_tip_count; i += 1)
		drawstring(_sui_pixel_align(pos + [6 * sc, 5 * sc + i * (fs + 3 * sc), 0]),
			sui_tip_lines[i], glyph, SUI_THEME_TEXT, 1, 0);
	if (wasclip) drawsetcliparea(clipmin_x, clipmin_y, clipmax_x - clipmin_x, clipmax_y - clipmin_y);
	sui_tip_visible = TRUE;
	sui_tip_pos = pos;
	sui_tip_size = size;
};

// m_draw resets the font before its sui_end, and a tip measured and drawn in
// the 8 px bitmap is unreadable: a tip is UI text wherever the bracket ends.
void() sui_tooltip_finish =
{
	local float font, cur;
	font = drawfont;
	cur = ui_font_cur;
	if (!drawfont) Font_Set(ui_font_ui);
	_sui_tooltip_finish();
	drawfont = font;
	ui_font_cur = cur;
};
