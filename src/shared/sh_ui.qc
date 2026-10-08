/* Shared SUI chrome. Existing controls/IDs and the gameplay HUD stay unchanged. */
#define SUI_THEME_PANEL '0.07 0.09 0.12'
#define SUI_THEME_LINE '0.35 0.70 1.00'
#define SUI_THEME_FOCUS '1.00 0.80 0.35'
#define SUI_THEME_MUTED '0.45 0.48 0.55'
#define SUI_THEME_TEXT '0.88 0.92 0.98'
#define SUI_THEME_DIM '0.55 0.60 0.68'
#define SUI_THEME_CHIP '0.12 0.13 0.16'
#define SUI_THEME_SELECTED '0.16 0.30 0.44'
#define SUI_THEME_HOVER '0.18 0.23 0.30'
#define SUI_THEME_PRESSED '0.22 0.28 0.36'
#define SUI_TIP_LINES 24

float sui_style_modern;
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
	registercvar("ui_style", "0", 32);
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

void(float width, float height) sui_style_begin =
{
	local vector pixels;
	pixels = getproperty(VF_SCREENPSIZE);
	if (pixels_x <= 0 || pixels_y <= 0) pixels = [width, height, 0];
	sui_style_pixel_ratio = [max(1, pixels_x) / max(1, width), max(1, pixels_y) / max(1, height), 0];
	sui_style_text_calls = 0;
	sui_style_frames += 1;
	sui_style_modern = (cvar("ui_style") > 0);
	sui_style_screen = [width, height, 0];
	sui_tip_candidate_id = "";
	sui_tip_candidate_text = "";
	sui_tip_visible = FALSE;
	sui_round_calls = 0;
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
	size = sui_native_text_size(want);
	sui_transform_box(pos, size);
	pos = _sui_pixel_align(pos);
	drawstring(pos, text, size, color, alpha, 0);
	sui_style_text_calls += 1;
};

// Raw screen coordinates; the public wrapper transforms exactly once.
void(vector pos, vector size, float radius, vector color, float alpha) _sui_round_draw =
{
	local float x, y, dx, dy, dw, dh, u, v, uw, vh, r;
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
	// 32x32 mask, radius 8: edges/centre stay opaque and only corners scale.
	for (y = 0; y < 3; y += 1)
	for (x = 0; x < 3; x += 1)
	{
		dx = r; dw = size_x - 2 * r; u = 0.25; uw = 0.5;
		dy = r; dh = size_y - 2 * r; v = 0.25; vh = 0.5;
		if (x == 0) { dx = 0; dw = r; u = 0; uw = 0.25; }
		if (x == 2) { dx = size_x - r; dw = r; u = 0.75; uw = 0.25; }
		if (y == 0) { dy = 0; dh = r; v = 0; vh = 0.25; }
		if (y == 2) { dy = size_y - r; dh = r; v = 0.75; vh = 0.25; }
		if (dw > 0)
		if (dh > 0)
		{
			sui_style_quads += 1;
			drawsubpic(pos + [dx, dy, 0], [dw, dh, 0], "gfx/ui/roundmask.png",
				[u, v, 0], [uw, vh, 0], color, alpha, 0);
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
	if (!sui_style_modern)
	{
		sui_fill(pos, size, fill, alpha, 0);
		sui_border_box(pos, size, 1, border, alpha, 0);
		return;
	}
	sui_transform_box(pos, size);
	_sui_round_draw(pos, size, radius, border, alpha);
	_sui_round_draw(pos + '1 1 0', size - '2 2 0', max(0, radius - 1), fill, alpha);
};

void(string id, string text, float scale) sui_tooltip_for =
{
	if (!sui_style_modern) return;
	if (_holding_click) return;
	if (strcmp(text, "") == 0) return;
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

void() sui_tooltip_finish =
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
	if (!sui_style_modern || _holding_click || strcmp(sui_tip_candidate_id, "") == 0)
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
	_sui_round_draw(pos, size, 4 * sc, SUI_THEME_LINE, 0.96);
	_sui_round_draw(pos + '1 1 0', size - '2 2 0', max(0, 4 * sc - 1), SUI_THEME_PANEL, 0.98);
	for (i = 0; i < sui_tip_count; i += 1)
		drawstring(_sui_pixel_align(pos + [6 * sc, 5 * sc + i * (fs + 3 * sc), 0]),
			sui_tip_lines[i], glyph, SUI_THEME_TEXT, 1, 0);
	if (wasclip) drawsetcliparea(clipmin_x, clipmin_y, clipmax_x - clipmin_x, clipmax_y - clipmin_y);
	sui_tip_visible = TRUE;
	sui_tip_pos = pos;
	sui_tip_size = size;
};
