/*
===========================================================================
  cl_mapmsg.qc -- the map's own messages and screen effects (Patch 870).

  game_text (six channels), env_hudhint, env_fade and env_shake, sent by the
  server as MM_EV_* events (sv_entities.qc SV_MapMsg*).  Text uses the Dusk
  UI font at the map's position and colour; the hint is a Dusk panel.  The
  fade is drawn under the HUD so the clock stays readable; the shake moves the
  camera only (Source's view punch), never the body.  hud_mapmsg 0 hides the
  text and hint; hud_mapfx 0 stops fades and shakes.
===========================================================================
*/

#define MM_CHANNELS 8       // game_text's channel mod 8 (Source keeps 16; the library writes 0-6)

float  mm_t0[MM_CHANNELS];          // cltime the message arrived; 0 = empty
string mm_msg[MM_CHANNELS];
vector mm_pos[MM_CHANNELS];         // x, y as game_text writes them (-1 centres)
vector mm_col[MM_CHANNELS], mm_col2[MM_CHANNELS];
float  mm_fx[MM_CHANNELS], mm_in[MM_CHANNELS], mm_out[MM_CHANNELS];
float  mm_hold[MM_CHANNELS], mm_fxt[MM_CHANNELS];

string mm_hint;
float  mm_hint_t0, mm_hint_t1;      // shown at, hidden from (fade out)

float  mm_fade_t0, mm_fade_dur, mm_fade_hold, mm_fade_fl;
vector mm_fade_rgb;
float  mm_fade_a;

float  mm_sh_t0, mm_sh_dur, mm_sh_amp, mm_sh_freq;
float  mm_cv_msg, mm_cv_fx;

void() MapMsg_Init =
{
	registercvar("hud_mapmsg", "1");
	registercvar("hud_mapfx", "1");
};

void() MapMsg_Reset =
{
	local float i;
	for (i = 0; i < MM_CHANNELS; i = i + 1)
		mm_t0[i] = 0;
	mm_hint_t0 = mm_hint_t1 = 0;
	mm_fade_t0 = 0;
	mm_sh_t0 = 0;
};

vector() MapMsg_ReadRGB =
{
	local vector c;
	c_x = readbyte() / 255;
	c_y = readbyte() / 255;
	c_z = readbyte() / 255;
	return c;
};

void(float t) MapMsg_Event =
{
	local float ch;
	local string s;

	if (t == MM_EV_TEXT)
	{
		ch = readbyte() % MM_CHANNELS;
		mm_pos[ch] = [readfloat(), readfloat(), 0];
		mm_fx[ch] = readbyte();
		mm_col[ch] = MapMsg_ReadRGB();
		mm_col2[ch] = MapMsg_ReadRGB();
		mm_in[ch] = readfloat();
		mm_out[ch] = readfloat();
		mm_hold[ch] = readfloat();
		mm_fxt[ch] = readfloat();
		s = readstring();
		if (mm_msg[ch] != "")
			strunzone(mm_msg[ch]);
		mm_msg[ch] = strzone(s);
		mm_t0[ch] = cltime;
		return;
	}
	if (t == MM_EV_HINT)
	{
		ch = readbyte();
		s = readstring();
		if (ch && s == mm_hint && cltime < mm_hint_t1)
			mm_hint_t1 = cltime + 6;    // the same hint again holds it, as Source's does
		else if (ch)
		{
			if (mm_hint != "")
				strunzone(mm_hint);
			mm_hint = strzone(s);
			mm_hint_t0 = cltime;
			mm_hint_t1 = cltime + 6;
		}
		else if (mm_hint_t1 > cltime + 0.3)
			mm_hint_t1 = cltime + 0.3;
		return;
	}
	if (t == MM_EV_FADE)
	{
		mm_fade_fl = readbyte();
		mm_fade_rgb = MapMsg_ReadRGB();
		mm_fade_a = readbyte() / 255;
		mm_fade_dur = max(0.001, readfloat());
		mm_fade_hold = readfloat();
		mm_fade_t0 = cltime;
		return;
	}
	if (t == MM_EV_SHAKE)
	{
		mm_sh_amp = readfloat();
		mm_sh_freq = readfloat();
		mm_sh_dur = readfloat();
		mm_sh_t0 = (mm_sh_amp > 0) ? cltime : 0;
		return;
	}
};

// game_text's alpha at time `e` since arrival: fade in, hold, fade out.
float(float ch, float e) MapMsg_Alpha =
{
	local float a, tot;
	tot = mm_in[ch] + mm_hold[ch] + mm_out[ch];
	if (e >= tot)
		return -1;
	a = 1;
	if (mm_in[ch] > 0 && e < mm_in[ch])
		a = e / mm_in[ch];
	else if (mm_out[ch] > 0 && e > mm_in[ch] + mm_hold[ch])
		a = 1 - (e - mm_in[ch] - mm_hold[ch]) / mm_out[ch];
	return bound(0, a, 1);
};

// message.cpp XPosition/YPosition: -1 centres, another negative counts from the far
// edge, else a fraction of the screen; then held on screen.
float(float f, float w, float tot) MapMsg_Pos =
{
	local float v;
	if (f == -1)
		v = (tot - w) * 0.5;
	else if (f < 0)
		v = (1 + f) * tot - w;
	else
		v = f * tot;
	return bound(0, v, max(0, tot - w));
};

void(vector scr) MapMsg_DrawText =
{
	local float ch, e, a, sz, w, n, shown, settled, i, j, base, vis, sv, fin, fxt, ft, t;
	local vector p, c, mp;
	local string s, line;

	sz = Font_Px(13 * ui_cv_scale);
	p = '0 0 0';
	Font_Set(ui_font_ui);
	for (ch = 0; ch < MM_CHANNELS; ch = ch + 1)
	{
		if (!mm_t0[ch])
			continue;
		e = cltime - mm_t0[ch];
		s = mm_msg[ch];
		c = mm_col[ch];
		shown = settled = strlen(s);
		a = 1;
		fin = mm_in[ch];
		fxt = mm_fxt[ch];
		if (mm_fx[ch] == 2)
		{
			// Scan-out (message.cpp:348-372, 438-445): a character every fadein,
			// each flashing color2 and settling to color over fxtime; the hold
			// ends at fadein * length + holdtime, then fadeout.
			ft = fin * strlen(s) + mm_hold[ch];
			if (e >= ft + mm_out[ch])
			{
				mm_t0[ch] = 0;
				continue;
			}
			a = (e > ft && mm_out[ch] > 0) ? 1 - (e - ft) / mm_out[ch] : 1;
			if (fin > 0 && e <= ft)
			{
				shown = floor(e / fin);
				settled = (fxt > 0) ? floor((e - fxt) / fin) : shown;
			}
		}
		else
		{
			// Effect 1 draws as 0: Source 2013's flicker is compiled out (message.cpp:385).
			a = MapMsg_Alpha(ch, e);
			if (a < 0)
			{
				mm_t0[ch] = 0;
				continue;
			}
		}
		// Lines are "\n"-separated, as Source splits them; untyped characters
		// keep their place, so a centred line does not grow from the middle.
		n = tokenizebyseparator(s, "\n");
		base = 0;
		for (i = 0; i < n; i = i + 1)
		{
			line = argv(i);
			w = stringwidth(line, TRUE, [sz, sz]);
			mp = mm_pos[ch];
			p_x = MapMsg_Pos(mp_x, w, scr_x);
			p_y = MapMsg_Pos(mp_y, n * sz * 1.2, scr_y) + i * sz * 1.2;
			vis = bound(0, shown - base, strlen(line));
			sv = bound(0, settled - base, vis);
			if (sv > 0)
				HUD_TextDraw(p, substring(line, 0, sv), sz, c, a);
			for (j = sv; j < vis; j = j + 1)
			{
				t = bound(0, (e - (base + j + 1) * fin) / max(0.001, fxt), 1);
				HUD_TextDraw(p + [stringwidth(substring(line, 0, j), TRUE, [sz, sz]), 0, 0],
				             substring(line, j, 1), sz, mm_col2[ch] * (1 - t) + c * t, a);
			}
			base = base + strlen(line);
		}
	}
	Font_Reset();
};

void(vector scr) MapMsg_DrawHint =
{
	local float sz, w, a, pad;
	local vector p;
	local string s;

	if (!mm_hint_t0 || cltime >= mm_hint_t1)
		return;
	a = bound(0, (cltime - mm_hint_t0) / 0.2, 1) * bound(0, (mm_hint_t1 - cltime) / 0.3, 1);
	Font_Set(ui_font_ui);
	sz = Font_Px(9 * ui_cv_scale);
	pad = 8 * ui_cv_scale;
	s = Chat_Fit(mm_hint, scr_x * 0.6, sz);
	w = stringwidth(s, TRUE, [sz, sz]) + pad * 2;
	p = [(scr_x - w) * 0.5, scr_y * 0.72, 0];
	_sui_round_draw(p, [w, sz + pad * 1.6, 0], 5 * ui_cv_scale, SUI_THEME_PANEL, 0.85 * a);
	HUD_TextDraw(p + [pad, pad * 0.8, 0], s, sz, SUI_THEME_TEXT, a);
	Font_Reset();
};

/*
  env_fade, under the HUD.  Flags: 1 fade IN from the colour (Source's
  SF_FADE_IN), 2 modulate, 8 stay out (hold until the next fade).
*/
void(vector scr) MapMsg_DrawFade =
{
	local float e, k;

	if (!mm_fade_t0 || !mm_cv_fx)
		return;
	e = cltime - mm_fade_t0;
	if (mm_fade_fl & 1)
	{
		// From the colour back to the scene: hold first, then clear.
		if (e < mm_fade_hold)
			k = 1;
		else
			k = 1 - (e - mm_fade_hold) / mm_fade_dur;
	}
	else
	{
		k = e / mm_fade_dur;
		if (e > mm_fade_dur + mm_fade_hold && !(mm_fade_fl & 8))
			k = 0;
	}
	k = bound(0, k, 1);
	if (k <= 0 && e > mm_fade_dur + mm_fade_hold)
	{
		mm_fade_t0 = 0;
		return;
	}
	if (mm_fade_fl & 2)
		drawfill('0 0 0', scr, mm_fade_rgb, k * mm_fade_a, DRAWFLAG_MODULATE);
	else
		drawfill('0 0 0', scr, mm_fade_rgb, k * mm_fade_a, 0);
};

// The camera offset this frame: Source's shake is a damped random offset at
// `frequency`, amplitude falling linearly over `duration`.
vector() MapMsg_ShakeOffset =
{
	local float e, amp, ph;

	if (!mm_sh_t0 || !mm_cv_fx)
		return '0 0 0';
	e = cltime - mm_sh_t0;
	if (e >= mm_sh_dur)
	{
		mm_sh_t0 = 0;
		return '0 0 0';
	}
	amp = mm_sh_amp * (1 - e / mm_sh_dur);
	ph = e * max(1, mm_sh_freq) * 6.2832;
	return [sin(ph * 1.13), sin(ph * 0.87 + 1.7), sin(ph + 0.6) * 0.5] * amp * 0.25;
};

void(vector scr) MapMsg_Draw =
{
	mm_cv_msg = cvar("hud_mapmsg");
	mm_cv_fx = cvar("hud_mapfx");
	if (!mm_cv_msg)
		return;
	MapMsg_DrawText(scr);
	MapMsg_DrawHint(scr);
};
