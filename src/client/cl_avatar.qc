/*
===========================================================================
  cl_avatar.qc -- the player customizer, `hud_player`.  Patch 340.

  UIC_AVATAR was reserved in cl_hud.qc's cursor register for "cl_avatar.qc --
  customizer (not built yet)".  This is that file.

  WHAT IT EDITS IS THE SERVER'S EXISTING CHANNELS, not new ones: the avatar
  system (sv_lobby.qc, Patch 278) already resolves `setinfo lobbycolor`,
  `lobbyfx` and -- since 340 -- `lobbytrail`, once a second, for everybody.
  So every control here is a setinfo and the truth of what you got is what
  the server publishes back: `lc` (forceinfokey, your resolved palette index)
  and cl_pcolour (stuffcmd, your resolved colour as a cvar -- read with
  cvar(), a FLOAT read: cvar_string would return the Cvar_LockFromServer
  LATCH, see Lobby_ClientConnect).  The panel marks the GRANTED colour, not
  the asked one, because a taken colour falls through to the random pick and
  a UI that showed the ask would lie.

  THE PALETTE is mirrored from Lobby_PaletteRGB (sv_lobby.qc) -- the third
  copy is mkavatarfx.py's generated particle cfg, which is GENERATED from the
  QC precisely so copies cannot drift.  This one cannot be generated (it is
  compiled into csprogs), so it carries the same table and the same warning:
  edit Lobby_PaletteRGB, edit this, re-run mkavatarfx.py --check.

  THE PLAYER HASH.  *phash is forceinfokey'd once per connection by
  Lobby_ClientConnect: FS_GuidId(guid), the same 8 hex chars the run
  filenames carry.  It survives renames -- records follow the hash, not the
  name -- and it is the handle a per-hash effect table would key on.
  Displayed, per the ask; consumed by nothing yet.  The name field here
  writes the engine's `name` cvar through the console command, which is the
  one channel that updates userinfo mid-connection.

  THE PREVIEW.  A second renderscene into a viewport rect beside the panel
  (VF_VIEWPORT + VF_DRAWWORLD 0, which also fullbrights it -- the stage sits
  at z 65536 where no map has light).  The body is a CSQC entity dressed
  exactly like your avatar -- colormod off the palette, glowmod, trail and
  motes off your fx mask -- and it oscillates so the trail is a ribbon and
  not a dot.  It renders AFTER the panel's 2D fill and BEFORE its border, so
  the frame sits over the scene's edge.  The main view never sees the stage:
  it is above every frustum the game camera has, and the particles it emits
  are born after this frame's main renderscene already ran.

  GHOST MODE dresses the replay stand-in (cl_ghost.qc's rec_gh_body) through
  Av_GhostDress, called from Ghost_DrawBody: the same colormod/glowmod and
  the same trail/mote emitters, so the changes you make are visible on your
  own body the moment you look at it from outside.
===========================================================================
*/

float av_open;                  // the customizer is up

#define AV_FX_TRAIL    1
#define AV_FX_MOTES    2
#define AV_FX_GLOW     4
#define AV_FX_TRAILONG 8

#define AV_COLOURS 12

// Panel placement, fractions of the screen (panel CENTRE), archived so a
// dragged position survives a restart the way every other hud_*_x/y does.
float av_mx;                    // last absolute mouse position, for the drag
float av_my;
float av_drag;                  // title bar held
vector av_dragofs;
float av_namefocus;
string av_name_text;
float av_name_caret;
float av_mote_acc;                // mote rate integrator, see Av_Dress
vector av_rgb;                    // PATCH 341: the RGB sliders' 0..255 state

entity av_prev;                 // the preview body
vector av_prev_org;             // its origin last frame (trail segment)
vector av_gh_prev;              // ghost body's feet last frame, same job
float  av_emit_t;               // last mote emit, for a rate

// The stage the preview body lives on: above every map, below no frustum
// the game camera owns.
#define AV_STAGE '0 0 65536'

// Prototypes: the slider callbacks below land before these definitions.
float(string key) Av_MyInfo;
void(string key, float v) Av_SetInfo;

/*
  The palette mirror.  Keep in lockstep with Lobby_PaletteRGB in
  server/sv_lobby.qc -- see the header.  An if-ladder for the reason that
  file gives (fteqcc array cost), and the same plain hue order.
*/
vector(float i) Av_PaletteRGB =
{
	if (i == 1)  return '1.00 0.00 0.00';    // red
	if (i == 2)  return '0.92 0.51 0.09';    // orange
	if (i == 3)  return '1.00 1.00 0.00';    // yellow
	if (i == 4)  return '0.51 0.92 0.09';    // chartreuse
	if (i == 5)  return '0.00 1.00 0.00';    // green
	if (i == 6)  return '0.09 0.92 0.51';    // spring green
	if (i == 7)  return '0.00 1.00 1.00';    // cyan
	if (i == 8)  return '0.09 0.51 0.92';    // azure
	if (i == 9)  return '0.00 0.00 1.00';    // blue
	if (i == 10) return '0.51 0.09 0.92';    // violet
	if (i == 11) return '1.00 0.00 1.00';    // magenta
	if (i == 12) return '0.92 0.09 0.51';    // rose
	return '1 1 1';
};

string(float i) Av_ColourName =
{
	if (i == 1)  return "red";
	if (i == 2)  return "orange";
	if (i == 3)  return "yellow";
	if (i == 4)  return "chartreuse";
	if (i == 5)  return "green";
	if (i == 6)  return "spring";
	if (i == 7)  return "cyan";
	if (i == 8)  return "azure";
	if (i == 9)  return "blue";
	if (i == 10) return "violet";
	if (i == 11) return "magenta";
	if (i == 12) return "rose";
	return "plain";
};

/*
  The palette as colormod wants it: divided by the green skin, clamped to the
  wire range (sv_ents.c packs byte = qc * 32, so 7.96875 is the ceiling), and
  floored off the all-zero identity sentinel -- the same three moves
  Lobby_ColourMod makes, mirrored because a CSQC entity's colormod is set
  here and not by the server.
*/
vector(float i) Av_ColourMod =
{
	local vector v;

	v = Av_PaletteRGB(i);
	v_x = v_x / 0.50980;
	v_y = v_y / 0.92549;
	v_z = v_z / 0.32549;
	if (v_x > 7.96) v_x = 7.96;
	if (v_y > 7.96) v_y = 7.96;
	if (v_z > 7.96) v_z = 7.96;
	if (v_x < 0.032 && v_y < 0.032 && v_z < 0.032)
		v_x = 0.032;
	return v;
};

/*
  PATCH 341: THE RGB HALF OF THE COLOUR STORY.

  `setinfo lobbyrgb "r g b"` (0..255) wears an exact body colour: colormod and
  glowmod are multiplies and take any triple, so the server resolves it in
  sv_lobby.qc's 1 Hz loop and publishes the exact worn triple back as `lrgb`,
  with `lc` demoted to the NEAREST palette entry -- the one the pre-generated
  trail and mote particles and the console chat colour come from, because
  those cannot be tinted per entity.  These mirror Lobby_ColourModRGB /
  Lobby_GlowModRGB / Lobby_ParseRGB over there; the palette table above is
  already the third copy of the same twelve hues.

  Own-player reads prefer the local `lobbyrgb` userinfo (setinfo is immediate)
  over the server's `lrgb` echo (up to a second old), so a dragged slider moves
  the preview the frame it moves; other slots only ever have `lrgb`.
*/
vector(string s) Av_Parse255 =
{
	local vector v;
	local float i, sp, val;
	local string t;

	v = '-1 -1 -1';
	for (i = 0; i < 3; i = i + 1)
	{
		s = strtrim(s);
		if (s == "")
			return '-1 -1 -1';
		sp = strstrofs(s, " ", 0);
		if (sp < 0)
		{
			t = s;
			s = "";
		}
		else
		{
			t = substring(s, 0, sp);
			s = substring(s, sp + 1, -1);
		}
		val = stof(t);
		if (val < 0 || val > 255)
			return '-1 -1 -1';
		if (i == 0) v_x = val;
		else if (i == 1) v_y = val;
		else v_z = val;
	}
	return v;
};

vector() Av_MyRGB =
{
	local vector v;

	v = Av_Parse255(getplayerkeyvalue(player_localnum, "lobbyrgb"));
	if (v_x >= 0)
		return v / 255;
	v = Av_Parse255(getplayerkeyvalue(player_localnum, "lrgb"));
	if (v_x >= 0)
		return v / 255;
	return Av_PaletteRGB(cvar("cl_pcolour"));
};

// What ANOTHER slot is wearing: the server's exact echo, else its palette.
vector(float slot) Av_WornRGB =
{
	local vector v;

	v = Av_Parse255(getplayerkeyvalue(slot, "lrgb"));
	if (v_x >= 0)
		return v / 255;
	return Av_PaletteRGB(stof(getplayerkeyvalue(slot, "lc")));
};

vector(vector rgb) Av_ColourModRGB =
{
	local vector v;

	v = rgb;
	v_x = v_x / 0.50980;
	v_y = v_y / 0.92549;
	v_z = v_z / 0.32549;
	if (v_x > 7.96) v_x = 7.96;
	if (v_y > 7.96) v_y = 7.96;
	if (v_z > 7.96) v_z = 7.96;
	if (v_x < 0.032 && v_y < 0.032 && v_z < 0.032)
		v_x = 0.032;
	return v;
};

vector(vector rgb) Av_GlowModRGB =
{
	local vector v;

	v = rgb;
	if (v_x < 0.032 && v_y < 0.032 && v_z < 0.032)
		v_x = 0.032;
	return v;
};

/*
  PATCH 341: THE SLIDER.  sui_slidercontrol draws nothing (sui_sys.qc:1152 is
  sui_action_element plus the drag maths), so this is the cl_watch knob look:
  a track, a filled share, a knob, a label at the left and the state at the
  right.  `vtxt` is the caller's naming of the stop -- a slider over three
  named states reads better than three numbers nobody memorises.
*/
void(string id, vector pos, vector sz, float maxv, float val, string label,
     string vtxt, void(float v) cb, float divs) Av_Slider =
{
	local float lw, vw, tw, kw, lab;

	lab = Font_Px(5 * ui_cv_scale);
	lw  = ceil(lab * 5.5);
	vw  = ceil(lab * 5.5);
	tw  = sz_x - lw - vw;
	kw  = ceil(sz_y * 0.5);

	sui_text([pos_x, pos_y + (sz_y - lab) * 0.5], [lab, lab], label,
	         '0.65 0.65 0.7', 1, 0);
	sui_fill([pos_x + lw, pos_y + sz_y * 0.5 - ceil(sz_y * 0.18)],
	         [tw, ceil(sz_y * 0.36)], '0.12 0.14 0.18', 1, 0);
	if (val > 0)
		sui_fill([pos_x + lw, pos_y + sz_y * 0.5 - ceil(sz_y * 0.18)],
		         [tw * (val / maxv), ceil(sz_y * 0.36)], '0.30 0.45 0.62', 1, 0);
	sui_fill([pos_x + lw + (tw - kw) * (val / maxv), pos_y], [kw, sz_y],
	         '0.90 0.93 0.98', 1, 0);
	sui_text([pos_x + lw + tw + 4, pos_y + (sz_y - lab) * 0.5], [lab, lab],
	         vtxt, '0.55 0.55 0.58', 1, 0);
	sui_slidercontrol(id, [pos_x + lw, pos_y], [tw, sz_y], [0, maxv, divs],
	                  val, cb);
};

void() Av_SendRGB =
{
	localcmd(sprintf("setinfo lobbyrgb \"%g %g %g\"\n",
	                 floor(av_rgb_x + 0.5), floor(av_rgb_y + 0.5),
	                 floor(av_rgb_z + 0.5)));
};

// A palette pick is a palette pick: the custom triple goes away with it.
void() Av_ClearRGB =
{
	localcmd("setinfo lobbyrgb \"\"\n");
	av_rgb = Av_MyRGB() * 255;
};

void(float v) Av_SetR = { av_rgb_x = v; Av_SendRGB(); };
void(float v) Av_SetG = { av_rgb_y = v; Av_SendRGB(); };
void(float v) Av_SetB = { av_rgb_z = v; Av_SendRGB(); };

void(float v) Av_FxTrail =
{
	local float fx;

	fx = Av_MyInfo("lobbyfx");
	fx = fx - (fx & (AV_FX_TRAIL | AV_FX_TRAILONG));
	if (v >= 1)
		fx = fx + AV_FX_TRAIL;
	if (v >= 2)
		fx = fx + AV_FX_TRAILONG;
	Av_SetInfo("lobbyfx", fx);
};

void(float v) Av_FxMotes =
{
	local float fx;

	fx = Av_MyInfo("lobbyfx");
	fx = fx - (fx & AV_FX_MOTES);
	if (v >= 1)
		fx = fx + AV_FX_MOTES;
	Av_SetInfo("lobbyfx", fx);
};

void(float v) Av_FxGlow =
{
	local float fx;

	fx = Av_MyInfo("lobbyfx");
	fx = fx - (fx & AV_FX_GLOW);
	if (v >= 1)
		fx = fx + AV_FX_GLOW;
	Av_SetInfo("lobbyfx", fx);
};

/*
  Greedy wrap to a width, for the panel's prose: every line in here is fitted
  or wrapped, because a fixed-size panel with variable-length sentences is a
  panel that leaks text over its own border, which is exactly what the first
  cut did with "your times follow the hash" and the footer.
*/
float(float x, float y, float w, float fsz, string s, vector col) Av_Wrap =
{
	local string piece;
	local float k, cut;

	k = 0;
	while (k < strlen(s))
	{
		piece = "";
		cut = k;
		while (cut < strlen(s))
		{
			piece = strcat(piece, substring(s, cut, 1));
			if (stringwidth(piece, TRUE, [fsz, fsz]) > w)
				break;
			cut = cut + 1;
		}
		if (cut == k)
			cut = k + 1;
		sui_text([x, y], [fsz, fsz], substring(s, k, cut - k), col, 1, 0);
		y = y + fsz + 2;
		k = cut;
	}
	return y;
};

void() Av_Close =
{
	if (!av_open)
		return;
	av_open = FALSE;
	av_drag = FALSE;
	av_namefocus = FALSE;
	UI_CursorRelease(UIC_AVATAR);
};

void() Av_Open =
{
	/*
	  Refuses the modal neighbours rather than drawing under them.  sui has ONE
	  hit-test list and sui_begin empties it, so two sui brackets in a frame
	  means the second one's buttons are dead -- cl_main.qc's Ev_Panel comment
	  is the long version.  The board wins because it is the older modal; the
	  customizer says so instead of drawing a panel that cannot be clicked.
	*/
	if (rec_sb_open || ui_he_open || rec_wt_open)
	{
		print("hud_player: close the leaderboard / editor / replay first\n");
		return;
	}
	if (av_open)
		return;
	av_open = TRUE;
	// Seed the name field from the live name so the field is never a lie.
	av_name_text = getplayerkeyvalue(player_localnum, "name");
	av_name_caret = strlen(av_name_text);
	// ...and the sliders from what is actually worn, custom or palette.
	av_rgb = Av_MyRGB() * 255;
	UI_CursorClaim(UIC_AVATAR);
};

void() Av_Toggle =
{
	if (av_open)
		Av_Close();
	else
		Av_Open();
};

// What the player ASKED for; the server's grant is read separately.
float(string key) Av_MyInfo =
{
	return stof(getplayerkeyvalue(player_localnum, key));
};

void(string key, float v) Av_SetInfo =
{
	localcmd(sprintf("setinfo %s \"%g\"\n", key, v));
};

/*
  Dress a body -- the preview's or the ghost stand-in's -- in this player's
  resolved look.  colormod and glowmod are fields; the trail and motes are
  EMITTED, because the engine-driven .traileffectnum wants a SERVER-side
  particle slot and CSQC's particleeffectnum hands back a client-only one
  (sv_lobby.qc's effects essay is the long version).  trailparticles and
  pointparticles are the client-side end of the same table, so they take it.
*/
void(entity g, vector feet, vector prevfeet, float dt) Av_Dress =
{
	local float c, m, tc, slot, n;
	local vector rgb;

	c = cvar("cl_pcolour");
	if (c < 1 || c > AV_COLOURS)
		return;                       // unresolved: leave the body as it was

	rgb = Av_MyRGB();
	g.colormod = Av_ColourModRGB(rgb);

	m = Av_MyInfo("lobbyfx");

	if (m & AV_FX_GLOW)
		g.glowmod = Av_GlowModRGB(rgb);
	else
		g.glowmod = '0.032 0.032 0.032';   // off, and expressible: see sv_lobby

	tc = Av_MyInfo("lobbytrail");
	if (tc < 1 || tc > AV_COLOURS)
		tc = c;

	if (m & AV_FX_TRAIL)
	{
		if (m & AV_FX_TRAILONG)
			slot = particleeffectnum(sprintf("ftesurf_avtrailL_%g", tc));
		else
			slot = particleeffectnum(sprintf("ftesurf_avtrail_%g", tc));
		if (prevfeet != '0 0 0')
			trailparticles(slot, g, prevfeet, feet);
	}
	if (m & AV_FX_MOTES)
	{
		/*
		  pointparticles' count is a NUMBER of particles, not a rate -- the
		  engine-driven emitter passes frametime and multiplies by the block's
		  `count` itself, a manual call does not.  So the 6/sec rate is
		  integrated here and spent in whole particles, or at 100 fps every
		  call would ask for 0.06 of one and get nothing at all.
		*/
		av_mote_acc = av_mote_acc + 6 * dt;
		n = floor(av_mote_acc);
		if (n >= 1)
		{
			av_mote_acc = av_mote_acc - n;
			pointparticles(particleeffectnum(sprintf("ftesurf_avmote_%g", c)),
			               feet + '0 0 32', '0 0 0', n);
		}
	}
};

/*
  cl_ghost.qc calls this on the replay stand-in every frame it draws one --
  the forward declaration is over there, beside the colormod it overrides.
  This is the answer to "I go ghost mode and see none of my changes": the
  stand-in used to be dressed in identity white, and now it wears you.
*/
void(entity g) Av_GhostDress =
{
	local float dt;

	dt = time - av_emit_t;
	if (dt < 0)
		dt = 0;
	Av_Dress(g, g.origin, av_gh_prev, dt);
	av_gh_prev = g.origin;
};

/*
  One swatch.  Returns TRUE on the frame it is clicked.  `on` marks the
  server-resolved pick; `want` marks the ask when it differs (a taken colour
  is asked-but-not-granted for up to a second, and a swatch that showed
  neither state would look dead).
*/
float(string id, vector pos, float sz, float idx, float on, float want) Av_Swatch =
{
	local vector c;

	sui_action_element(pos, [sz, sz], id, sui_noop);
	c = Av_PaletteRGB(idx);
	sui_fill(pos, [sz, sz], c, on ? 1 : (want ? 0.8 : 0.4), 0);
	sui_border_box(pos, [sz, sz], on ? 2 : 1,
	               (on || sui_is_hovered(id)) ? '1 1 1' : '0.2 0.2 0.24',
	               1, 0);
	return sui_is_released(id);
};

float(string id, vector pos, vector sz, string label, float on) Av_Chip =
{
	sui_action_element(pos, sz, id, sui_noop);
	sui_fill(pos, sz, on ? '0.22 0.34 0.48' : (sui_is_hovered(id) ? '0.14 0.14 0.18' : '0.09 0.09 0.12'), 1, 0);
	sui_border_box(pos, sz, 1, on ? '0.5 0.8 1' : '0.28 0.30 0.36', 1, 0);
	sui_text([pos_x + 8, pos_y + (sz_y - Font_Px(6 * ui_cv_scale)) * 0.5],
	         [Font_Px(6 * ui_cv_scale), Font_Px(6 * ui_cv_scale)], label,
	         on ? '1 1 1' : '0.65 0.65 0.7', 1, 0);
	return sui_is_released(id);
};

/*
  The preview scene: a second renderscene into its own viewport rect, AFTER
  the panel's fill and BEFORE its border.  VF_DRAWWORLD 0 skips the world --
  there is none at the stage -- and fullbrights what is left, so the body
  reads as its colour rather than as whatever light a void has.
*/
void(vector rpos, vector rsz) Av_Preview =
{
	local vector cam, look, org;
	local float dt;

	if (!av_prev)
	{
		av_prev = spawn();
		setmodel(av_prev, "models/player.iqm");
		av_prev.solid = SOLID_NOT;
		av_prev.effects = EF_NOSHADOW;
		av_prev_org = '0 0 0';
	}

	// Oscillate: sway on x, bob on z, yaw back and forth -- enough motion for
	// the trail to be a ribbon and for the colour to catch the eye.
	org = AV_STAGE + [sin(time * 1.3) * 16, 0, sin(time * 2.2) * 2];
	setorigin(av_prev, org);
	av_prev.angles = [0, sin(time * 0.7) * 40, 0];

	dt = time - av_emit_t;
	if (dt < 0)
		dt = 0;
	av_emit_t = time;

	Av_Dress(av_prev, org, av_prev_org, dt);
	av_prev_org = org;

	cam  = org + [120, -120, 44];
	look = vectoangles(org + '0 0 32' - cam);

	clearscene();
	setproperty(VF_VIEWPORT, rpos, rsz);
	setproperty(VF_DRAWWORLD, 0);
	setproperty(VF_ORIGIN, cam);
	setproperty(VF_ANGLES, look);
	setproperty(VF_FOV, [50, 50, 0]);
	addentity(av_prev);
	renderscene();
};

void(vector scr) Av_Draw =
{
	local vector p, sz;
	local float i, x, y, sw, fx, want, got, askt, pad, tsz, ttl, hint;
	local float barh, fw, fh, pvw, pvx, pvh, slh, stop;
	local string nm, hash, s, rgbstr;

	// The board is the older modal and draws over this; see Av_Open.
	if (!av_open || rec_sb_open)
		return;

	sui_begin(scr_x, scr_y);

	/*
	  ONE TYPE SCALE, snapped to the font's baked ladder the way every other
	  panel does (Font_Px, cl_hud.qc's essay): raw pixel sizes resample off
	  the nearest bake and read soft, which is exactly the complaint the
	  first cut of this panel earned.
	*/
	ttl  = Font_Px(8 * ui_cv_scale);
	tsz  = Font_Px(6 * ui_cv_scale);
	hint = Font_Px(5 * ui_cv_scale);

	pad = ceil(tsz * 1.0);
	sw  = ceil(tsz * 2.2);
	// PATCH 341: taller -- the RGB sliders and the effect sliders are rows the
	// chip grid never had, and the footer wraps instead of leaking.
	sz  = [ceil(tsz * 25), ceil(tsz * 40)];
	pvw = ceil(sz_x * 0.62);              // the preview viewport's width
	p   = [cvar("hud_player_x") * scr_x - sz_x * 0.5,
	       cvar("hud_player_y") * scr_y - sz_y * 0.5];
	// Clamped with the PREVIEW's footprint counted: the panel plus its
	// viewport beside it is the thing that has to fit, not the panel alone.
	if (p_x < 4) p_x = 4;
	if (p_y < 4) p_y = 4;
	if (p_x + sz_x + 6 + pvw > scr_x - 4)
		p_x = scr_x - 4 - pvw - 6 - sz_x;
	if (p_x < 4) p_x = 4;
	if (p_y + sz_y > scr_y - 4) p_y = scr_y - 4 - sz_y;
	pvx = p_x + sz_x + 6;

	sui_fill(p, sz, '0.05 0.05 0.07', 0.94, 0);

	/*
	  THE TITLE BAR IS THE HANDLE.  sui_is_held on it plus the mouse position
	  Av_InputEvent stores is the whole drag: grab offsets once on the press,
	  then every absolute move rewrites the two placement cvars.  cvar_set
	  rather than a QC global so the position is archived like every other
	  hud_*_x/y and survives a restart.
	*/
	barh = ttl + pad * 2;
	sui_action_element([p_x, p_y], [sz_x, barh], "av_drag", sui_noop);
	if (sui_is_released("av_drag"))
	{
		av_drag = TRUE;
		av_dragofs = [av_mx - p_x, av_my - p_y, 0];
	}
	if (av_drag)
	{
		if (sui_click_held())
		{
			cvar_set("hud_player_x", ftos((av_mx - av_dragofs_x + sz_x * 0.5) / scr_x));
			cvar_set("hud_player_y", ftos((av_my - av_dragofs_y + sz_y * 0.5) / scr_y));
			p = [cvar("hud_player_x") * scr_x - sz_x * 0.5,
			     cvar("hud_player_y") * scr_y - sz_y * 0.5];
		}
		else
			av_drag = FALSE;
	}

	// ---- who am I ------------------------------------------------------
	nm   = getplayerkeyvalue(player_localnum, "name");
	/*
	  The hash, off the star infokey Lobby_ClientConnect forceinfokeys -- the
	  *wrank channel (cl_results.qc), because a stuffed `set` latches and
	  cvar_string reads the latch.  "" is a server without sv_guidkey (a
	  listen server, or a lobby that cannot rank): the runs are then filed by
	  name-and-slot and saying "no id" beats an empty box that looks like a
	  rendering bug.
	*/
	hash = getplayerkeyvalue(player_localnum, "*phash");

	sui_text([p_x + pad, p_y + pad], [ttl, ttl], "player", '0.35 0.75 1', 1, 0);

	y = p_y + pad * 2 + ttl;

	// The name field: sui's own text input, fed by Av_InputEvent while it has
	// focus.  Enter commits through the engine's `name` command -- the one
	// channel that updates userinfo mid-connection.
	fw = sz_x - pad * 2;
	fh = ceil(tsz * 1.8);
	sui_text_input("av_name", [p_x + pad, y], [fw, fh], av_name_text, av_name_caret);
	if (sui_is_last_clicked("av_name"))
		av_namefocus = TRUE;
	sui_fill([p_x + pad, y], [fw, fh], '0.09 0.09 0.12', 1, 0);
	sui_border_box([p_x + pad, y], [fw, fh], 1,
	               av_namefocus ? '0.5 0.8 1' : '0.28 0.30 0.36', 1, 0);
	sui_text([p_x + pad + 6, y + (fh - tsz) * 0.5], [tsz, tsz],
	         av_name_text == "" ? "your name" : av_name_text,
	         av_name_text == "" ? '0.4 0.4 0.44' : '1 1 1', 1, 0);
	y = y + fh + 4;

	if (hash == "")
		sui_text([p_x + pad, y], [hint, hint],
		         "hash: none -- this server has no player ids",
		         '0.55 0.55 0.58', 1, 0);
	else
		sui_text([p_x + pad, y], [hint, hint],
		         strcat("hash: ", hash), '0.55 0.55 0.58', 1, 0);
	y = y + hint + 2;
	y = Av_Wrap(p_x + pad, y, sz_x - pad * 2, hint,
	            "your times follow the hash, not the name",
	            '0.4 0.4 0.44');
	y = y + pad - 2;

	// ---- colour ---------------------------------------------------------
	got  = cvar("cl_pcolour");          // the server's answer (float read)
	want = Av_MyInfo("lobbycolor");     // your ask (0 = auto)
	rgbstr = getplayerkeyvalue(player_localnum, "lobbyrgb");

	sui_text([p_x + pad, y], [tsz, tsz], "colour", '0.65 0.65 0.7', 1, 0);
	y = y + tsz + 4;
	x = p_x + pad;
	for (i = 1; i <= AV_COLOURS; i = i + 1)
	{
		if (Av_Swatch(sprintf("av_c%g", i), [x, y], sw, i, got == i,
		              want == i && rgbstr == ""))
		{
			Av_SetInfo("lobbycolor", i);
			Av_ClearRGB();
		}
		x = x + sw + 4;
		if (i == 6)
		{
			x = p_x + pad;
			y = y + sw + 4;
		}
	}
	if (Av_Chip("av_cauto", [p_x + sz_x - pad - sw * 3, y - sw - 4 + 3],
	            [sw * 3, tsz * 1.6], "random", want == 0 && rgbstr == ""))
	{
		Av_SetInfo("lobbycolor", 0);
		Av_ClearRGB();
	}
	y = y + sw + 4;                 // row 2's bottom, before the sliders

	/*
	  PATCH 341: THE RGB SLIDERS, under the swatches rather than instead of
	  them.  The swatches are the twelve hues the particles exist in; the
	  sliders are the exact body colour, which colormod carries fine and the
	  pre-generated trail and motes cannot -- so a custom triple wears itself
	  on the model and the nearest palette entry in its particles, its chat
	  name and everybody's swatch, and the wearing line says so out loud.
	  Picking a swatch clears lobbyrgb: a palette pick is a palette pick.
	*/
	slh = ceil(tsz * 1.5);
	/*
	  PATCH 341bis: THE THIRD COMPONENT IS A DIVISION COUNT, not a step size
	  (sui_sys.qc:1166: rint(ratio * steps) / steps).  [0, 255, 1] quantised
	  every drag to 0 or 255 -- "the sliders only give 0 or 255" -- because one
	  division IS the whole range.  255 divisions for the colour bytes, 2 for
	  the three-stop trail, 1 for the binaries.
	*/
	Av_Slider("av_r", [p_x + pad, y], [sz_x - pad * 2, slh], 255, av_rgb_x,
	          "r", ftos(floor(av_rgb_x + 0.5)), Av_SetR, 255);
	y = y + slh + 2;
	Av_Slider("av_g", [p_x + pad, y], [sz_x - pad * 2, slh], 255, av_rgb_y,
	          "g", ftos(floor(av_rgb_y + 0.5)), Av_SetG, 255);
	y = y + slh + 2;
	Av_Slider("av_b", [p_x + pad, y], [sz_x - pad * 2, slh], 255, av_rgb_z,
	          "b", ftos(floor(av_rgb_z + 0.5)), Av_SetB, 255);
	y = y + slh + 4;

	if (rgbstr != "")
		s = sprintf("wearing: %g %g %g custom -- particles: %s",
		            floor(av_rgb_x + 0.5), floor(av_rgb_y + 0.5),
		            floor(av_rgb_z + 0.5), Av_ColourName(got));
	else if (got >= 1 && got <= AV_COLOURS)
		s = sprintf("wearing: %s  (%g/12 taken)", Av_ColourName(got), got);
	else
		s = "wearing: server's pick";
	sui_text([p_x + pad, y], [hint, hint], Chat_Fit(s, sz_x - pad * 2, hint),
	         '0.55 0.55 0.58', 1, 0);
	y = y + hint + pad;

	// ---- effects: three sliders, off through full -----------------------
	sui_text([p_x + pad, y], [tsz, tsz], "effects", '0.65 0.65 0.7', 1, 0);
	y = y + tsz + 4;

	fx = Av_MyInfo("lobbyfx");
	stop = (fx & AV_FX_TRAIL) ? ((fx & AV_FX_TRAILONG) ? 2 : 1) : 0;
	Av_Slider("av_fx1", [p_x + pad, y], [sz_x - pad * 2, slh], 2, stop,
	          "trail", stop == 0 ? "off" : (stop == 1 ? "trail" : "long"),
	          Av_FxTrail, 2);
	y = y + slh + 2;
	Av_Slider("av_fx2", [p_x + pad, y], [sz_x - pad * 2, slh], 1,
	          (fx & AV_FX_MOTES) ? 1 : 0, "motes",
	          (fx & AV_FX_MOTES) ? "on" : "off", Av_FxMotes, 1);
	y = y + slh + 2;
	Av_Slider("av_fx3", [p_x + pad, y], [sz_x - pad * 2, slh], 1,
	          (fx & AV_FX_GLOW) ? 1 : 0, "glow",
	          (fx & AV_FX_GLOW) ? "on" : "off", Av_FxGlow, 1);
	y = y + slh + pad;

	// ---- trail colour ------------------------------------------------------
	sui_text([p_x + pad, y], [tsz, tsz], "trail colour", '0.65 0.65 0.7', 1, 0);
	y = y + tsz + 4;
	askt = Av_MyInfo("lobbytrail");
	x = p_x + pad;
	for (i = 1; i <= AV_COLOURS; i = i + 1)
	{
		if (Av_Swatch(sprintf("av_t%g", i), [x, y], sw * 0.7, i,
		              askt == i || (askt == 0 && got == i), askt == i))
			Av_SetInfo("lobbytrail", i);
		x = x + sw * 0.7 + 4;
		if (i == 6)
		{
			x = p_x + pad;
			y = y + sw * 0.7 + 4;
		}
	}
	if (Av_Chip("av_tauto", [p_x + pad + 7 * (sw * 0.7 + 4), y - sw * 0.7 - 4 + 1],
	            [sw * 3, tsz * 1.6], "match", askt == 0))
		Av_SetInfo("lobbytrail", 0);
	y = y + sw * 0.7 + 4;

	/*
	  PATCH 341: THE FOOTER WRAPS.  It used to be two fixed lines written for a
	  wider panel than this one, and the first of them ran straight out over
	  the border -- the panel is a fixed width and the sentence is not, so the
	  sentence yields.
	*/
	Av_Wrap(p_x + pad, p_y + sz_y - hint * 3 - 8, sz_x - pad * 2, hint,
	        "how you look to OTHERS -- drag the title bar to move this, esc closes",
	        '0.4 0.4 0.44');

	// ---- the preview, in its own viewport beside the panel ---------------
	/*
	  PATCH 341: THE VIEWPORT IS CLAMPED TO THE SCREEN.  It is anchored to the
	  panel's top and takes 72% of the panel's (now taller) height, so a panel
	  dragged low -- or a short window -- used to push the model's feet under
	  the bottom of the display, which is exactly what "the player model is off
	  the bottom of the window" reported.  The camera also sits further back
	  and wider (fov 50 at ~170 units) so the body floats inside the frame
	  with margin instead of touching all four edges.
	*/
	pvh = ceil(sz_y * 0.72);
	if (pvh > scr_y - 8 - p_y)
		pvh = scr_y - 8 - p_y;
	if (pvh < tsz * 6)
		pvh = tsz * 6;
	Av_Preview([pvx, p_y], [pvw, pvh]);
	sui_border_box([pvx, p_y], [pvw, pvh], 1,
	               '0.28 0.30 0.36', 0.9, 0);

	sui_border_box(p, sz, 1, '0.28 0.30 0.36', 1, 0);
	Font_Reset();
	sui_end();
};

/*
  The panel's input, shaped like Scores_InputEvent with two additions: the
  absolute mouse position is STORED (the drag reads it a frame later), and
  while the name field has focus every key goes to sui's text input first so
  the field actually types.
*/
float(float evtype, float scanx, float chary, float devid) Av_InputEvent =
{
	if (!av_open || rec_sb_open)
		return FALSE;

	if (evtype == IE_MOUSEABS)
	{
		av_mx = scanx;
		av_my = chary;
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}

	if (evtype == IE_KEYDOWN || evtype == IE_KEYUP)
	{
		if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
		{
			sui_input_event(evtype, scanx, chary, devid);
			// A click is also how the name field gains and loses focus:
			// whichever element sui saw clicked last is the answer.
			if (evtype == IE_KEYDOWN)
				av_namefocus = sui_is_last_clicked("av_name");
			return TRUE;
		}
		if (evtype == IE_KEYDOWN)
		{
			if (scanx == K_ESCAPE)
			{
				if (av_namefocus)
				{
					av_namefocus = FALSE;   // first ESC leaves the field
					return TRUE;
				}
				Av_Close();
				return TRUE;
			}
			if (av_namefocus)
			{
				if (scanx == K_ENTER)
				{
					// Commit through the engine's name command -- the one
					// channel that updates userinfo mid-connection -- via the
					// same quoted-cvar route the chat draft uses, so a name with
					// spaces or a semicolon arrives as exactly what was typed.
					if (strtrim(av_name_text) != "")
						Chat_RunSafe("name", strtrim(av_name_text));
					av_namefocus = FALSE;
					return TRUE;
				}
				sui_input_event(evtype, scanx, chary, devid);
				return TRUE;
			}
		}
		else if (av_namefocus)
		{
			sui_input_event(evtype, scanx, chary, devid);
			return TRUE;
		}
	}
	return FALSE;
};

/*
  The console half: `hud_player` toggles the panel, and open/close exist for
  the same reason `scores open` does -- a panel no config can reach is a panel
  no headless test can check.
*/
float(string cmd) Av_ConsoleCommand =
{
	if (argv(0) != "hud_player")
		return FALSE;

	if (argv(1) == "open")
		Av_Open();
	else if (argv(1) == "close")
		Av_Close();
	else
		Av_Toggle();
	return TRUE;
};

void() Av_RegisterCvars =
{
	/*
	  THE NAME IS THE ASK'S: `hud_player`.  registercommand silently no-ops on
	  a name the engine owns (pr_csqc.c:5497) -- `hud_player` was checked
	  against the engine's command list and is free.  Not a cvar: the panel is
	  a toggle like `scores`, and a cvar would archive a panel left open.
	*/
	registercommand("hud_player");

	/*
	  The server's colour mirror, registered beside its read (the rule this
	  tree has lost features to).  cl_pcolour is the resolved palette index
	  Lobby_Frame stuffcmds on change; read with cvar() (a FLOAT read, which
	  is the effective value) and NOT cvar_string -- a server-stuffed set is
	  Cvar_LockFromServer, and cvar_string returns the LATCHED pre-override
	  string to QC (pr_bgcmd.c:1975).  The hash rides a star infokey instead
	  for exactly that reason; see Lobby_ClientConnect.  Not CVAR_ARCHIVE:
	  an archived mirror would outlive the connection it describes.
	*/
	registercvar("cl_pcolour", "0");

	// Panel placement, archived: the drag writes these through cvar_set.
	registercvar("hud_player_x", "0.5", CVAR_ARCHIVE);
	registercvar("hud_player_y", "0.5", CVAR_ARCHIVE);
};
