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
  exactly like your avatar: the belt overlay off your two colours
  (Patch 457) and glowmod off your fx mask.  It stands beside the panel with no
  backdrop and no frame -- renderscene does not clear, so the rect shows the
  main view behind the body; that is the look Lex asked for.

  IT CANNOT SHOW THE TRAIL OR THE MOTES, and this paragraph used to claim it
  did -- "it oscillates so the trail is a ribbon and not a dot".  P_DrawParticles
  is inside `if (!(r_refdef.flags & RDF_NOWORLDMODEL))` (r_surf.c:4014) and
  VF_DRAWWORLD 0 sets exactly that flag, so the two effects made of particles
  are the two this preview is structurally unable to draw.  The oscillation was
  animating a ribbon nothing was drawing.  The trail STRIP lower down the panel
  is the answer: a 2D representation of colour and length, labelled as one.

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
/*
  PATCH 457: bit 8 was "long trail" and is unassigned now -- the trail's LENGTH
  is `setinfo lobbylen <0..3>`, its own key beside `lobbytrail`'s colour, because
  one bit can only ever offer two lengths.  Four stops, and they all cost the
  same: tools/mkavatarfx.py scales `step` with `die`, so live particles per
  player is mean(die)/step x speed and depends on the ratio, not on either alone.
*/
#define AV_TRAILN 4

#define AV_COLOURS 12

// Panel placement, fractions of the screen (panel CENTRE), archived so a
// dragged position survives a restart the way every other hud_*_x/y does.
float av_mx;                    // last absolute mouse position, for the drag
float av_my;
float av_drag;                  // title bar held
vector av_dragofs;
float av_namefocus;
float av_saidsz;                // the type-scale line is said once per open
string av_tbsent;               // last topcolor/bottomcolor pushed; see Av_PushHalves
float av_half;                  // which part the sliders edit: 0 belt, 1 body
string av_name_text;
float av_name_caret;
float av_mote_acc;                // mote rate integrator, see Av_Dress
vector av_rgb;                    // PATCH 341: the RGB sliders' 0..255 state

entity av_prev;                 // the preview body
vector av_prev_org;             // its origin last frame (trail segment)
vector av_gh_prev;              // ghost body's feet last frame, same job
float  av_emit_t;               // last mote emit, for a rate
float  av_gh_emit_t;            // the ghost body's own; see Av_GhostDress

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
  PATCH 457 REMOVED Av_ColourMod AND Av_ColourModRGB, and the note is worth more
  than the code was.  They divided the wanted colour by the green skin so that
  .colormod -- a MULTIPLY -- cancelled the texture and left the body the colour
  you asked for.  That is exactly one colour per entity and so could never carry
  two halves, and the shirt/pants overlay is added BEFORE colormod in the shader
  (defaultskin.glsl:317-323, then :398), so a colormod left behind would have
  multiplied the new colours by the old trick.  models/player.tga is a dark grey
  floor now and every body sets colormod to the identity sentinel.
  Av_GlowModRGB below survives untouched: glowmod tints the luma belt, which is
  still a multiply and still one colour.
*/

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

vector(vector rgb) Av_GlowModRGB =
{
	local vector v;

	v = rgb;
	if (v_x < 0.032 && v_y < 0.032 && v_z < 0.032)
		v_x = 0.032;
	return v;
};

/*
  The nearest palette entry to an arbitrary triple: the client half of
  Lobby_NearestColour (sv_lobby.qc:479), the same squared distance over the same
  twelve hues.  A custom colour wears itself exactly on the model and has to name
  one of the twelve for its particles, which are generated per entry and cannot
  be tinted per entity.
*/
/*
  PATCH 457: THE TWO HALVES, CLIENT SIDE.

  `lobbymark` paints the plus-cross and `lobbybody` paints everything else, each
  falling back one step -- mark to body, body to the worn colour -- so a player
  who never touches them wears one colour and no visible cross at all.

  THE MIRROR INTO topcolor/bottomcolor IS DONE HERE AND NOT ONLY BY THE SERVER,
  because the server's 1 Hz resolve runs only on a lobby.  Off one -- a listen
  server, every offline session, every headless arm -- nothing would publish
  them and the renderer would fall back to an UNSET topcolor, which is palette
  range 0 and reads as near-white over the dark skin.  Pushed on change only,
  against a latch, because this is reached from a per-frame draw.
*/
string(float v) Av_Hex2 =
{
	local string d;

	d = "0123456789abcdef";
	v = bound(0, floor(v + 0.5), 255);
	return strcat(substring(d, floor(v / 16), 1), substring(d, v & 15, 1));
};

string(vector rgb) Av_HexRGB =
{
	return strcat("0x", Av_Hex2(rgb_x * 255), Av_Hex2(rgb_y * 255),
	              Av_Hex2(rgb_z * 255));
};

// Everything that is not the cross.  Falls back to the worn body colour.
vector() Av_MyBody =
{
	local vector v;

	v = Av_Parse255(getplayerkeyvalue(player_localnum, "lobbybody"));
	if (v_x >= 0)
		return v / 255;
	return Av_MyRGB();
};

/*
  The cross, and it falls back to the BODY rather than the other way round: with
  lobbymark unset the cross is painted the colour of the body it sits on and is
  therefore invisible, which is what makes "never opened the customizer" mean
  one plain colour instead of a pattern nobody chose.
*/
vector() Av_MyMark =
{
	local vector v;

	v = Av_Parse255(getplayerkeyvalue(player_localnum, "lobbymark"));
	if (v_x >= 0)
		return v / 255;
	return Av_MyBody();
};

void() Av_PushHalves =
{
	local string s, t, b;

	t = Av_HexRGB(Av_MyMark());
	b = Av_HexRGB(Av_MyBody());
	s = strcat(t, " ", b);
	if (s == av_tbsent)
		return;
	if (av_tbsent)
		strunzone(av_tbsent);
	av_tbsent = strzone(s);
	localcmd(strcat("setinfo topcolor ", t, "\n"));
	localcmd(strcat("setinfo bottomcolor ", b, "\n"));
};

float(vector rgb) Av_NearestColour =
{
	local float i, best, bi, d;
	local vector c;

	best = -1;
	bi   = 1;
	for (i = 1; i <= AV_COLOURS; i = i + 1)
	{
		c = Av_PaletteRGB(i) - rgb;
		d = c_x * c_x + c_y * c_y + c_z * c_z;
		if (best < 0 || d < best)
		{
			best = d;
			bi   = i;
		}
	}
	return bi;
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

	// 6, not 5: 5 * hud_scale 2 is 10, which ties between rungs 8 and 12 and
	// Font_Px breaks ties downward -- so every slider label and value used to
	// come out at 8 while the panel around them was 12.  See Av_Draw.
	lab = Font_Px(6 * ui_cv_scale);
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

// PATCH 457: the sliders move ONE HALF of the body, whichever av_half selects.
void() Av_SendRGB =
{
	localcmd(sprintf("setinfo %s \"%g %g %g\"\n",
	                 av_half ? "lobbybody" : "lobbymark",
	                 floor(av_rgb_x + 0.5), floor(av_rgb_y + 0.5),
	                 floor(av_rgb_z + 0.5)));
};

// A palette pick is a palette pick: the custom triple goes away with it, and so
// do both halves, so the whole body follows the swatch that was just clicked.
void() Av_ClearRGB =
{
	localcmd("setinfo lobbyrgb \"\"\n");
	localcmd("setinfo lobbymark \"\"\n");
	localcmd("setinfo lobbybody \"\"\n");
	av_rgb = Av_MyRGB() * 255;
};

void(float v) Av_SetR = { av_rgb_x = v; Av_SendRGB(); };
void(float v) Av_SetG = { av_rgb_y = v; Av_SendRGB(); };
void(float v) Av_SetB = { av_rgb_z = v; Av_SendRGB(); };

// The stop's name, matching tools/mkavatarfx.py's TRAIL_STOPS so the panel and
// the generated blocks call the same ribbon the same thing.
string(float n) Av_TrailLenName =
{
	if (n <= 0) return "short";
	if (n == 1) return "medium";
	if (n == 2) return "long";
	return "longest";
};

// What the trail length is set to, clamped.  Unset is 0, the ribbon this game
// drew before there was a choice.
float() Av_TrailLen =
{
	local float n;

	n = Av_MyInfo("lobbylen");
	if (n < 0 || n > AV_TRAILN - 1)
		n = 0;
	return n;
};

/*
  One slider for the trail: 0 is off, 1..AV_TRAILN are the length stops.  The
  length is written only when the trail is ON, so switching it off and back on
  returns the ribbon you had rather than the shortest one.
*/
void(float v) Av_FxTrail =
{
	local float fx;

	fx = Av_MyInfo("lobbyfx");
	fx = fx - (fx & AV_FX_TRAIL);
	if (v >= 1)
	{
		fx = fx + AV_FX_TRAIL;
		Av_SetInfo("lobbylen", v - 1);
	}
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
	av_saidsz = FALSE;              // say the type scale again for this open
	// Seed the name field from the live name so the field is never a lie.
	av_name_text = getplayerkeyvalue(player_localnum, "name");
	av_name_caret = strlen(av_name_text);
	// ...and the sliders from what is actually worn, custom or palette.
	av_rgb = Av_MyMark() * 255;
	av_half = 0;
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

	rgb = Av_MyRGB();
	/*
	  PATCH 457: the colour is the shirt/pants overlay, which the renderer
	  fetches from this player's own topcolor/bottomcolor through .colormap.
	  colormod is left at the identity sentinel because the shader applies it
	  AFTER adding the overlay (defaultskin.glsl:317, :398) and would otherwise
	  multiply the chosen colours by it.
	*/
	g.colormod = '0 0 0';
	g.colormap = player_localnum + 1;
	Av_PushHalves();

	m = Av_MyInfo("lobbyfx");

	if (m & AV_FX_GLOW)
		g.glowmod = Av_GlowModRGB(rgb);
	else
		g.glowmod = '0.032 0.032 0.032';   // off, and expressible: see sv_lobby

	/*
	  cl_pcolour is the LOBBY's resolved index and it is 0 off one -- a listen
	  server, or any time before the first 1 Hz pass.  This function used to
	  RETURN there, so the body stayed undressed with nothing saying why, which
	  is every offline session and every headless arm.  The worn colour never
	  needed the server (lobbyrgb is local userinfo); only the particles need an
	  index, so only they fall back.
	*/
	c = cvar("cl_pcolour");
	if (c < 1 || c > AV_COLOURS)
		c = Av_NearestColour(rgb);

	tc = Av_MyInfo("lobbytrail");
	if (tc < 1 || tc > AV_COLOURS)
		tc = c;

	if (m & AV_FX_TRAIL)
	{
		slot = particleeffectnum(sprintf("ftesurf_avtrail%g_%g",
		                                 Av_TrailLen() + 1, tc));
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
		/*
		  dt IS CLAMPED, because it is "since this body last emitted" and a
		  caller can hand over a stale stamp: Av_GhostDress wrote none at all, so
		  the first ghost frame after the panel had been shut for five minutes
		  asked for 6 * 300 motes in one call, and again on the next frame.
		*/
		if (dt > 0.1)
			dt = 0.1;
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

	/*
	  ITS OWN STAMP.  This read av_emit_t, which only Av_Preview ever writes, and
	  wrote nothing back -- so dt was "seconds since the panel was last open" and
	  grew by a frame every frame.  Av_Dress clamps too; both are wanted, because
	  the clamp bounds the burst and this makes the rate right.
	*/
	dt = time - av_gh_emit_t;
	if (dt < 0)
		dt = 0;
	av_gh_emit_t = time;
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
	/*
	  THE PITCH IS NEGATED, AND THAT IS WHY THE BODY SAT LOW IN THE FRAME.

	  vectoangles returns "+x=UP" -- the engine's own builtin description says so
	  (pr_cmds.c:11490) -- and VF_ANGLES takes view angles, where positive pitch
	  is DOWN.  So this aimed the camera 4.05 degrees UP when it meant 4.05 down,
	  an 8.1 degree error, and the body hung below the middle of its viewport.
	  Measured before the fix: 64 px low in a 364 px rect.  Predicted from the
	  geometry: 170 units of camera distance x tan(8.1 deg) = 24.2 world units,
	  at the 2.73 px per unit the body was drawn at = 66 px.  The two agreeing is
	  what says this is the cause and not merely a cure.

	  This is the only vectoangles in the client, so there was nothing to compare
	  it against -- cl_watch builds its pitch and yaw directly.
	*/
	look = vectoangles(org + '0 0 31' - cam);
	look_x = -look_x;

	clearscene();
	setproperty(VF_VIEWPORT, rpos, rsz);
	setproperty(VF_DRAWWORLD, 0);
	setproperty(VF_ORIGIN, cam);
	setproperty(VF_ANGLES, look);
	/*
	  VF_AFOV, NOT VF_FOV, AND THAT IS THE STRETCH FIX.  VF_FOV sets fovx and
	  fovy outright, and this passed [50, 50] -- equal angles into a viewport
	  nearly twice as tall as it is wide, so a unit of world height covered the
	  same angle as a unit of width while spanning far more pixels, and the body
	  came out stretched vertically.  AFOV hands the engine ONE angle and it
	  derives both from the viewport rect (V_CalcAFov, view.c:1344).
	  cl_defs.qc:714 says as much on VF_FOV's own declaration: "consider using
	  afov instead".
	*/
	setproperty(VF_AFOV, 50);
	addentity(av_prev);
	renderscene();
};

void(vector scr) Av_Draw =
{
	local vector p, sz;
	local float i, x, y, sw, fx, want, got, eff, askt, pad, tsz, ttl, hint;
	local float barh, fw, fh, pvw, pvx, pvy, pvh, slh, stop;
	local float segs, lit, stripw, striph;      // the trail strip, below
	local vector tv, bv;                        // the two halves, as 0..255
	local float rqttl, rqtsz, rqhnt;            // the sizes ASKED for, pre-snap
	local string nm, hash, s, rgbstr, markstr;

	// The board is the older modal and draws over this; see Av_Open.
	if (!av_open || rec_sb_open)
		return;

	sui_begin(scr_x, scr_y);

	/*
	  ONE TYPE SCALE, snapped to the font's baked ladder the way every other
	  panel does (Font_Px, cl_hud.qc's essay): raw pixel sizes resample off
	  the nearest bake and read soft, which is exactly the complaint the
	  first cut of this panel earned.

	  Font_Set FIRST, AND THAT IS THE FIX: this panel shipped with the closing
	  Font_Reset (below) and no opener, so it drew in whatever face the previous
	  drawer left -- FONT_DEFAULT, the 8 px bitmap, because every other panel ends
	  by resetting.  Font_Px then matched no ladder and handed the request straight
	  back (sh_font.qc:184), so the sizes were raw as well and the snap this
	  comment describes never ran.  cl_hud.qc:2741 is the same bug in the sequence
	  block, with the same one-line fix.
	*/
	/*
	  THE THREE ASKS ARE RUNGS OF THE UI LADDER AT hud_scale 2, ON PURPOSE:
	  20 / 16 / 12 against "8 12 16 20 24 28 32".  They used to be 16/12/10, and
	  the 10 was the problem -- it is EXACTLY equidistant from 8 and 12, and
	  Font_Px breaks the tie with a strict `<` that keeps the first rung it saw,
	  so the hint text and every slider label silently came out at 8.  Nobody
	  chose 8; a tie did.  12 is the floor now and nothing here asks for a size
	  the ladder has to move.
	*/
	Font_Set(ui_font_ui);
	rqttl = 10 * ui_cv_scale;
	rqtsz =  8 * ui_cv_scale;
	rqhnt =  6 * ui_cv_scale;
	ttl  = Font_Px(rqttl);
	tsz  = Font_Px(rqtsz);
	hint = Font_Px(rqhnt);

	/*
	  ONCE PER OPEN, so the fix above is answerable from a LOG and not only from
	  pixels -- this tree has shipped a panel whose every reported number was its
	  own and correct while nothing was on screen at all.  The face slot proves
	  the .ttf loaded (0 is the bitmap fallback) and the three sizes prove the
	  snap ran: at hud_scale 2 a working snap reads 16/12/8, and the unsnapped
	  request this panel used to draw at read 16/12/10.
	  AT hud_scale 1 ALL THREE COLLAPSE TO 8, because the UI ladder's lowest rung
	  is 8 and it steps in fours -- the type hierarchy here exists at scale 2 and
	  up.  That is a property of the ladder, not of these constants, and it was
	  hidden for as long as Font_Px was returning the request unchanged.
	*/
	if (!av_saidsz)
	{
		av_saidsz = TRUE;
		dprint(sprintf("hud_player: face %g, snapped %g/%g/%g at hud_scale %g\n",
		               ui_font_ui, ttl, tsz, hint, ui_cv_scale));
		/*
		  AND SAY SO WHEN A SIZE HAD TO MOVE.  Font_Px snapping is invisible --
		  it returns a number and nothing records that the number is not the one
		  asked for -- so an off-ladder constant added later reads as a soft
		  block with no cause.  A second print rather than more arguments:
		  fteqcc drops the ninth parameter of a varargs call silently, which is
		  a bug this same patch fixed one file over.
		*/
		if (ttl != rqttl || tsz != rqtsz || hint != rqhnt)
			dprint(sprintf("hud_player: asked %g/%g/%g -- OFF THE LADDER, so at "
			               "least one block is a resample\n",
			               rqttl, rqtsz, rqhnt));
	}

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
	/*
	  sui_is_HELD, not sui_is_released, and that is why the panel could not be
	  dragged at all.  Release fires on the frame the button goes UP
	  (sui_sys.qc:345), so the old form armed the drag as the grab ENDED and the
	  sui_click_held test below cleared it again on the same frame.  The hold list
	  is latched at mouse-down and never rebuilt from hover (sui_sys.qc:433), so
	  this stays true when the cursor outruns the bar.
	*/
	if (sui_is_held("av_drag"))
	{
		if (!av_drag)
		{
			av_drag = TRUE;
			av_dragofs = [av_mx - p_x, av_my - p_y, 0];
		}
	}
	else
		av_drag = FALSE;

	if (av_drag)
	{
		cvar_set("hud_player_x", ftos((av_mx - av_dragofs_x + sz_x * 0.5) / scr_x));
		cvar_set("hud_player_y", ftos((av_my - av_dragofs_y + sz_y * 0.5) / scr_y));
		p = [cvar("hud_player_x") * scr_x - sz_x * 0.5,
		     cvar("hud_player_y") * scr_y - sz_y * 0.5];
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
	/*
	  ...and the index the PARTICLES will really use, which off a lobby is not the
	  server's answer at all: Av_Dress falls back to the nearest entry, so a panel
	  reporting `got` said "particles: plain" while the trail came out rose.  The
	  swatch marks stay on `got`, because an unlit swatch is honest about there
	  being no server pick to show.
	*/
	eff  = got;
	if (eff < 1 || eff > AV_COLOURS)
		eff = Av_NearestColour(Av_MyRGB());
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
	  PATCH 457: WHICH PART THE SLIDERS EDIT.

	  The body wears a plus-cross and the two are coloured independently (the
	  engine's shirt and pants overlay, driven by topcolor/bottomcolor through
	  .colormap), so the three sliders below need to say which part they are
	  moving.  "plain" clears the MARK, which makes the cross take the body's own
	  colour and vanish -- that is the fallback chain in Av_MyMark, and it is what
	  "one colour" means here.

	  The SWATCHES above stay whole-body: a palette pick clears both parts as
	  well as lobbyrgb, because a quick colour pick meaning "the cross only"
	  would surprise everybody.
	*/
	markstr = getplayerkeyvalue(player_localnum, "lobbymark");
	x = sz_x - pad * 2;
	if (Av_Chip("av_hmark", [p_x + pad, y], [x * 0.34, tsz * 1.6], "belt",
	            av_half == 0))
	{
		av_half = 0;
		av_rgb = Av_MyMark() * 255;
	}
	if (Av_Chip("av_hbody", [p_x + pad + x * 0.35, y], [x * 0.34, tsz * 1.6],
	            "body", av_half == 1))
	{
		av_half = 1;
		av_rgb = Av_MyBody() * 255;
	}
	/*
	  "plain" clears the MARK, not the body: an unset mark takes the body's own
	  colour and the cross disappears, which is the one-colour look.  Clearing
	  the body instead would have left the cross standing on a default.
	*/
	if (Av_Chip("av_hplain", [p_x + pad + x * 0.70, y], [x * 0.30, tsz * 1.6],
	            "plain", markstr == ""))
	{
		localcmd("setinfo lobbymark \"\"\n");
		av_half = 1;
		av_rgb = Av_MyBody() * 255;
	}
	y = y + tsz * 1.6 + 4;

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

	/*
	  PATCH 457: the line describes the BODY, which is two halves now, and names
	  the particle colour separately because that one is still a palette entry --
	  the trail and mote blocks are generated per colour and cannot be tinted.
	*/
	tv = Av_MyMark() * 255;
	bv = Av_MyBody() * 255;
	if (markstr != "")
		s = sprintf("belt %g %g %g / body %g %g %g -- particles: %s",
		            floor(tv_x + 0.5), floor(tv_y + 0.5), floor(tv_z + 0.5),
		            floor(bv_x + 0.5), floor(bv_y + 0.5), floor(bv_z + 0.5),
		            Av_ColourName(eff));
	else if (rgbstr != "" || getplayerkeyvalue(player_localnum, "lobbybody") != "")
		s = sprintf("body %g %g %g -- particles: %s",
		            floor(tv_x + 0.5), floor(tv_y + 0.5), floor(tv_z + 0.5),
		            Av_ColourName(eff));
	else if (got >= 1 && got <= AV_COLOURS)
		s = sprintf("body %s  (%g/12 taken)", Av_ColourName(got), got);
	else
		s = "body: server's pick";
	sui_text([p_x + pad, y], [hint, hint], Chat_Fit(s, sz_x - pad * 2, hint),
	         '0.55 0.55 0.58', 1, 0);
	y = y + hint + pad;

	// ---- effects: three sliders, off through full -----------------------
	sui_text([p_x + pad, y], [tsz, tsz], "effects", '0.65 0.65 0.7', 1, 0);
	y = y + tsz + 4;

	fx = Av_MyInfo("lobbyfx");
	stop = (fx & AV_FX_TRAIL) ? Av_TrailLen() + 1 : 0;
	Av_Slider("av_fx1", [p_x + pad, y], [sz_x - pad * 2, slh], AV_TRAILN, stop,
	          "trail", stop == 0 ? "off" : Av_TrailLenName(stop - 1),
	          Av_FxTrail, AV_TRAILN);
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
		              askt == i || (askt == 0 && eff == i), askt == i))
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
	  THE TRAIL STRIP, AND IT EXISTS BECAUSE THE 3D PREVIEW CANNOT SHOW ONE.
	  P_DrawParticles is inside `if (!(r_refdef.flags & RDF_NOWORLDMODEL))`
	  (r_surf.c:4014) and the stage renders with VF_DRAWWORLD 0, which sets
	  exactly that flag -- so the panel built to preview your effects could never
	  draw the two that are made of particles, and the body oscillates to animate
	  a ribbon nothing was drawing.  Measured, not inferred: p457av's shots have
	  lobbyfx 3 set and no particle anywhere in the viewport.

	  A REPRESENTATION, NOT A RENDER, and the panel says "to scale" rather than
	  pretending otherwise: the colour is the one the blocks are generated in and
	  the drawn length is the stop's share of the longest, which is the pair you
	  are actually choosing between.  Bright at the left, where the body would
	  be, fading out along the tail the way the real alphadelta does.
	*/
	striph = ceil(tsz * 0.6);
	if (fx & AV_FX_TRAIL)
	{
		// One segment per ~4 px of panel rather than a fixed 30: at 30 the
		// blocks were wide enough for the alpha steps to read as banding.
		segs = ceil((sz_x - pad * 2) / 4);
		stripw = (sz_x - pad * 2) / segs;
		lit = segs * (Av_TrailLen() + 1) / AV_TRAILN;
		for (i = 0; i < lit; i = i + 1)
			sui_fill([p_x + pad + i * stripw, y], [stripw + 1, striph],
			         Av_PaletteRGB(askt >= 1 ? askt : eff),
			         (1 - i / lit) * 0.85, 0);
	}
	else
		sui_fill([p_x + pad, y + striph * 0.5], [sz_x - pad * 2, 1],
		         '0.18 0.18 0.22', 1, 0);
	y = y + striph + 4;

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
	  THE VIEWPORT'S HEIGHT COMES FROM ITS OWN WIDTH, not from the panel's.

	  It was 72% of the panel height, which was tolerable while the panel was
	  480 units tall and became "weirdly tall" at 640 -- a 248-wide frame 460
	  tall, nearly 1:2.  A portrait frame half again as tall as it is wide holds
	  a standing body with margin and stops tracking a number it has nothing to
	  do with.  Still clamped to the screen below, which is what Patch 341 added
	  it for: a panel dragged low used to push the model's feet off the display.
	*/
	pvh = ceil(pvw * 1.5);
	if (pvh > sz_y)
		pvh = sz_y;
	if (pvh < tsz * 6)
		pvh = tsz * 6;
	/*
	  CENTRED ON THE PANEL, not anchored to its top.  While the rect had a frame
	  around it the anchor was the thing that read as deliberate; with the frame
	  gone it just left the body floating up by the panel's first few rows, a
	  third of the way down a 640-unit panel.  Clamped to the screen afterwards,
	  which is what Patch 341 put the clamp here for -- a panel dragged low must
	  not push the model's feet off the display.
	*/
	pvy = p_y + ceil((sz_y - pvh) * 0.5);
	if (pvy < 4)
		pvy = 4;
	if (pvy + pvh > scr_y - 4)
		pvy = scr_y - 4 - pvh;
	/*
	  NO BACKDROP AND NO FRAME: the body stands beside the panel, not in a box.

	  Both existed and both are deliberately gone.  VF_DRAWWORLD 0 draws the body
	  and nothing else and renderscene does not clear the colour buffer, so this
	  rect shows whatever the MAIN view already drew there -- which is why a fill
	  was added in the first place.  Lex's call after seeing it framed: "remove
	  the window behind the player display".  So the trade is stated rather than
	  hidden: the body now reads against live map geometry, which is busier than
	  a flat fill, and the rect is invisible so nothing marks where it clips.
	  Put the two lines back if it ever reads badly on a bright map.
	*/
	Av_Preview([pvx, pvy], [pvw, pvh]);

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
