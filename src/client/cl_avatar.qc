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

  THE PLAYER HASH.  *phash is forceinfokey'd by the server (sv_account.qc,
  Account_Mark): FS_GuidId(guid), the same 8 hex chars the run filenames
  carry, or since Patch 629 surfd's digest of the linked account while the
  board is by account (empty for a player with none, and it changes when a
  link is made).  It survives renames -- records follow the hash, not the
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

  It does not show the trail: a body swaying in place has no path to draw.
  The trail STRIP lower down the panel is a 2D representation of colour and
  length, labelled as one.  Patch 772 made the trail a line (cl_ptrail.qc)
  and took the motes out.

  GHOST MODE dresses the replay stand-in (cl_ghost.qc's rec_gh_body) through
  Av_GhostDress, called from Ghost_DrawBody, so the changes you make are
  visible on your own body the moment you look at it from outside; its trail
  is your own (Av_SelfTrail), drawn at the same feet.
===========================================================================
*/

float av_open;                  // the customizer is up

#define AV_FX_TRAIL    1
#define AV_FX_GLOW     4
#define AV_FX_MOTES    2        // drawn by nothing since Patch 772; cleared, see Av_ClearMotes
/*
  PATCH 457: bit 8 was "long trail" and is unassigned now -- the trail's LENGTH
  is `setinfo lobbylen <0..3>`, its own key beside `lobbytrail`'s colour, because
  one bit can only ever offer two lengths.  The stops' lives: PTrail_Life.
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
// Patch 663: the panel is a profile.  Its two pages, whose breakdown is up
// ("" the player's own), and what the page last drew at.
#define AV_TAB_LOOK  0
#define AV_TAB_STATS 1
#define AV_TAB_FRIENDS 2
float  av_tab;
string av_other;
float  av_hint;                 // the small label size, for Av_Slider
float  av_rowh;                 // a results row, for the wheel
float  av_saidtab;              // the page said once what it is showing
vector av_dbg;                  // the first trail swatch as last drawn, for `hud_player status`
string av_tbsent;               // last topcolor/bottomcolor pushed; see Av_PushHalves
float av_half;                  // which part the sliders edit: 0 belt, 1 body
string av_name_text;
float av_name_caret;
vector av_rgb;                    // PATCH 341: the RGB sliders' 0..255 state
string av_seen;                   // Patch 773: the half and its worn colour the sliders last took

entity av_prev;                 // the preview body
vector av_self_prev;            // Av_SelfTrail's last feet, for the teleport cut
float  av_self_t;

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
	// Patch 773: solo nothing resolves the ask, and an unresolved 0 is white.
	if (cvar("cl_pcolour") < 1)
		return Av_PaletteRGB(stof(getplayerkeyvalue(player_localnum, "lobbycolor")));
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
	lab = av_hint;
	lw  = ceil(lab * 4.5);
	vw  = ceil(lab * 4.5);
	tw  = sz_x - lw - vw;
	kw  = ceil(sz_y * 0.8);

	sui_text([pos_x, pos_y + (sz_y - lab) * 0.5], [lab, lab], label, SUI_THEME_DIM, 1, 0);
	sui_roundbox([pos_x + lw, pos_y + sz_y * 0.5 - ceil(sz_y * 0.14)],
	             [tw, ceil(sz_y * 0.28)], sz_y * 0.14, SUI_THEME_WELL, 1);
	if (val > 0)
		sui_roundbox([pos_x + lw, pos_y + sz_y * 0.5 - ceil(sz_y * 0.14)],
		             [max(ceil(sz_y * 0.28), tw * (val / maxv)), ceil(sz_y * 0.28)], sz_y * 0.14,
		             SUI_THEME_ACCENT, 0.7);
	sui_roundbox([pos_x + lw + (tw - kw) * (val / maxv), pos_y + (sz_y - kw) * 0.5], [kw, kw],
	             kw * 0.5, (sui_is_hovered(id) || sui_is_held(id)) ? '1 1 1' : SUI_THEME_TEXT, 1);
	sui_text([pos_x + lw + tw + lab * 0.6, pos_y + (sz_y - lab) * 0.5], [lab, lab],
	         vtxt, SUI_THEME_MUTED, 1, 0);
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

/*
  Patch 773: a palette swatch sets the half the sliders edit.  The body's pick is
  the palette ask a lobby resolves for everyone (a colour another player holds is
  not granted), so body, trail and chat stay one colour; solo nothing resolves it
  and Av_MyRGB wears the ask.  The belt takes the colour exactly.
*/
void(float i) Av_PickPalette =
{
	av_rgb = Av_PaletteRGB(i) * 255;
	if (av_half)
	{
		localcmd(sprintf("setinfo lobbycolor \"%g\"\n", i));
		localcmd("setinfo lobbyrgb \"\"\n");
		localcmd("setinfo lobbybody \"\"\n");
	}
	else
		Av_SendRGB();
};

void(float v) Av_SetR = { av_rgb_x = v; Av_SendRGB(); };
void(float v) Av_SetG = { av_rgb_y = v; Av_SendRGB(); };
void(float v) Av_SetB = { av_rgb_z = v; Av_SendRGB(); };

/*
  Which of the twelve the trail is drawn in: the asked colour when it is in
  range, else your body's palette entry -- what the server resolves for the
  others (Lobby_ApplyFX), so your line matches theirs.  Av_SelfTrail and the
  panel's strip both read it.
*/
float() Av_TrailColour =
{
	local float tc, c;

	tc = Av_MyInfo("lobbytrail");
	if (tc >= 1 && tc <= AV_COLOURS)
		return tc;
	c = cvar("cl_pcolour");
	if (c < 1 || c > AV_COLOURS)
		c = Av_NearestColour(Av_MyRGB());
	return c;
};

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
// The server still emits motes for a client without CSQC, and the chip that
// switched them off is gone: any write of the mask takes the bit out.
void() Av_ClearMotes =
{
	local float fx;

	fx = Av_MyInfo("lobbyfx");
	if (fx & AV_FX_MOTES)
		Av_SetInfo("lobbyfx", fx - AV_FX_MOTES);
};

void(float v) Av_FxTrail =
{
	local float fx;

	fx = Av_MyInfo("lobbyfx");
	fx = fx - (fx & (AV_FX_TRAIL | AV_FX_MOTES));
	if (v >= 1)
	{
		fx = fx + AV_FX_TRAIL;
		Av_SetInfo("lobbylen", v - 1);
	}
	Av_SetInfo("lobbyfx", fx);
};

// A LOCAL view preference, so it writes a cvar and not a setinfo -- nothing
// about how anybody else sees you changes with it.
void(float v) Av_FxSelf =
{
	cvar_set("cl_trailself", v >= 1 ? "1" : "0");
};

void(float v) Av_FxGlow =
{
	local float fx;

	fx = Av_MyInfo("lobbyfx");
	fx = fx - (fx & (AV_FX_GLOW | AV_FX_MOTES));
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
	Profile_Reset();
	sui_keys_forget();
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
	if (rec_sb_open || ui_he_open)
	{
		print("hud_player: close the leaderboard / editor first\n");
		return;
	}
	if (av_open)
		return;
	av_open = TRUE;
	av_saidtab = FALSE;
	Av_ClearMotes();
	av_other = "";
	av_name_text = getplayerkeyvalue(player_localnum, "name");
	av_name_caret = strlen(av_name_text);
	// Patch 773: one colour (no belt of its own) opens on the body, so a swatch colours you.
	av_half = (getplayerkeyvalue(player_localnum, "lobbymark") == "");
	av_rgb = (av_half ? Av_MyBody() : Av_MyMark()) * 255;
	av_namefocus = FALSE;
	Profile_Reset();
	Profile_Stale(60);
	Profile_TierShow(-2);           // Patch 666: the card opens on the results
	sui_keys_forget();
	UI_CursorClaim(UIC_AVATAR);
};

// Open on somebody's breakdown: a search row's handle or a board row's mark.
void(string who) Av_OpenAt =
{
	Av_Open();
	if (!av_open)
		return;
	av_other = who;
	av_tab = AV_TAB_STATS;
	av_namefocus = FALSE;
	av_saidtab = FALSE;
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
  resolved look: the colour overlay and the glow.  The trail is Av_SelfTrail's.
*/
void(entity g) Av_Dress =
{
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

	if (Av_MyInfo("lobbyfx") & AV_FX_GLOW)
		g.glowmod = Av_GlowModRGB(Av_MyRGB());
	else
		g.glowmod = '0.032 0.032 0.032';   // off, and expressible: see sv_lobby
};

/*
  PATCH 457, A LINE SINCE 769: YOUR OWN TRAIL, DRAWN LOCALLY.

  Nobody streams your own body back to you (lobby_av_self 0), so this is the
  only trail of yours you see; the others draw theirs from your LOOK block
  (cl_body.qc) in the same colour and length.  rec_gh_bodyfeet is the body's
  feet whether or not you are ghosting (cl_ghost.qc), so the stand-in's trail
  is this one, shown while ghosting even with cl_trailself 0.

  A move further than twice this frame's travel plus 128 units is a teleport,
  a load or a respawn, and cuts the line rather than drawing one across the map.
*/
void() Av_SelfTrail =
{
	local vector feet;
	local float cut, dt;

	if (!(Av_MyInfo("lobbyfx") & AV_FX_TRAIL))
	{
		PTrail_Cut(PT_SELF);
		return;
	}
	feet = rec_gh_bodyfeet;
	dt = max(0, cltime - av_self_t);
	cut = (vlen(feet - av_self_prev) > 128 + vlen(pmove_vel) * dt * 2);
	PTrail_Feed(PT_SELF, feet, cut, Av_PaletteRGB(Av_TrailColour()), PTrail_Life(Av_TrailLen()),
	            (cvar("cl_trailself") || rec_gh_on));
	av_self_prev = feet;
	av_self_t = cltime;
};

/*
  cl_ghost.qc calls this on the replay stand-in every frame it draws one --
  the forward declaration is over there, beside the colormod it overrides.
  This is the answer to "I go ghost mode and see none of my changes": the
  stand-in used to be dressed in identity white, and now it wears you.
*/
void(entity g) Av_GhostDress =
{
	Av_Dress(g);
};

/*
  One swatch.  Returns TRUE on the frame it is clicked.  `on` marks the
  server-resolved pick; `want` marks the ask when it differs (a taken colour
  is asked-but-not-granted for up to a second, and a swatch that showed
  neither state would look dead).
*/
float(string id, vector pos, float sz, float idx, float on, float want) Av_Swatch =
{
	sui_action_element(pos, [sz, sz], id, sui_noop);
	if (on || sui_is_hovered(id))
		sui_roundbox(pos - '2 2 0', [sz + 4, sz + 4], sz * 0.3 + 2, on ? SUI_THEME_TEXT : SUI_THEME_EDGE_HI, 1);
	sui_roundbox(pos, [sz, sz], sz * 0.3, Av_PaletteRGB(idx), on ? 1 : (want ? 0.85 : 0.6));
	return sui_is_released(id);
};

// A section's small heading.  -> the y under it.
float(vector pos, string s) Av_Head =
{
	sui_text(pos, [av_hint, av_hint], s, SUI_THEME_MUTED, 1, 0);
	return pos_y + av_hint + ceil(av_hint * 0.6);
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

	if (!av_prev)
	{
		av_prev = spawn();
		setmodel(av_prev, "models/player.iqm");
		av_prev.solid = SOLID_NOT;
		av_prev.effects = EF_NOSHADOW;
	}

	// Oscillate: sway on x, bob on z, yaw back and forth, so the colour catches the eye.
	org = AV_STAGE + [sin(time * 1.3) * 16, 0, sin(time * 2.2) * 2];
	setorigin(av_prev, org);
	av_prev.angles = [0, sin(time * 0.7) * 40, 0];

	Av_Dress(av_prev);

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
	setproperty(VF_AFOV, 36);       // Patch 663: the body fills the card's column
	addentity(av_prev);
	renderscene();
};

// Patch 772: cl_paint.qc compiles after this file.
void() Paint_Clear;
float() Paint_Count;
float() Paint_Size;
void(string name) Paint_Save;       // Patch 777
void(string name, float quiet) Paint_Load;
float() Paint_LayoutCount;

string(vector rgb) Av_255 =
{
	return sprintf("%g %g %g", rint(rgb_x * 255), rint(rgb_y * 255), rint(rgb_z * 255));
};

void(float v) Av_PaintSize = { cvar_set("paint_size", ftos((rint(v) + 1) * 4)); };
void(float v) Av_PaintAlpha = { cvar_set("paint_alpha", ftos((rint(v) + 1) / 10)); };

#define AV_PRATES "2 4 6 8 10 15 20 30 40 60 0"     // discs a second; 0 every frame
void(float v) Av_PaintRate = { cvar_set("paint_rate", Gfx_Field(AV_PRATES, rint(v), " ")); };

// The stop nearest paint_rate; 0 (every frame) is the top one.
float() Av_PaintRateStop =
{
	local float i, r, d, best, bi;

	r = cvar("paint_rate");
	if (r <= 0)
		return 10;
	best = -1;
	bi = 0;
	for (i = 0; i < 10; i = i + 1)
	{
		d = fabs(stof(Gfx_Field(AV_PRATES, i, " ")) - r);
		if (best < 0 || d < best)
		{
			best = d;
			bi = i;
		}
	}
	return bi;
};

/*
  The paint controls: a palette swatch or the body's colour, size, opacity, rate,
  this map's layout (Patch 777) and the keys.  Local cvars, not setinfo: others
  see your paint only through `share`.
*/
void(vector pos, float w, float psw, float slh) Av_PaintPanel =
{
	local float i, chw, sz, al, rs, ln;
	local vector v;
	local string k, s, sk;

	chw = ceil(av_hint * 5.5);
	if (Profile_Chip("av_pclr", [pos_x + w - chw, pos_y - 3], [chw, ceil(av_hint * 1.8)],
	                 sprintf("Clear %g", Paint_Count()), av_hint, FALSE))
		Paint_Clear();
	if (Profile_Chip("av_pbody", [pos_x + w - chw - ceil(av_hint * 4.5) - 6, pos_y - 3],
	                 [ceil(av_hint * 4.5), ceil(av_hint * 1.8)], "Body", av_hint, cvar_string("paint_color") == ""))
		cvar_set("paint_color", "");
	if (Profile_Chip("av_prnd", [pos_x + w - chw * 2 - ceil(av_hint * 4.5) - 12, pos_y - 3], [chw, ceil(av_hint * 1.8)],
	                 "Random", av_hint, !strcmp(cvar_string("paint_color"), "random")))
		cvar_set("paint_color", "random");
	pos_y = Av_Head(pos, "PAINT") + 3;
	v = Av_Parse255(cvar_string("paint_color"));
	for (i = 1; i <= AV_COLOURS; i = i + 1)
	{
		if (Av_Swatch(sprintf("av_ps%g", i), [pos_x + (i - 1) * (psw + 4), pos_y], psw, i,
		              !strcmp(Av_255(v * (1 / 255)), Av_255(Av_PaletteRGB(i))), FALSE))
			cvar_set("paint_color", Av_255(Av_PaletteRGB(i)));
	}
	pos_y = pos_y + psw + 6;
	sz = Paint_Size();
	Av_Slider("av_psz", pos, [w, slh], 15, bound(0, sz / 4 - 1, 15), "Size", sprintf("%gu", sz),
	          Av_PaintSize, 15);
	pos_y = pos_y + slh + 2;
	al = bound(0.1, cvar("paint_alpha"), 1);
	Av_Slider("av_pal", pos, [w, slh], 9, al * 10 - 1, "Opacity", sprintf("%g%%", rint(al * 100)),
	          Av_PaintAlpha, 9);
	pos_y = pos_y + slh + 2;
	rs = Av_PaintRateStop();
	Av_Slider("av_prt", pos, [w, slh], 10, rs, "Rate",
	          rs >= 10 ? "max" : sprintf("%g/s", stof(Gfx_Field(AV_PRATES, rs, " "))), Av_PaintRate, 10);
	pos_y = pos_y + slh + 2;
	// Patch 777: this map's layout, data/paint/<map>.txt.
	ln = Paint_LayoutCount();
	chw = floor((w - 12) / 3);
	if (Profile_Chip("av_psave", pos, [chw, ceil(av_hint * 1.8)], "Save layout", av_hint, FALSE))
		Paint_Save("");
	if (Profile_Chip("av_pload", [pos_x + chw + 6, pos_y], [chw, ceil(av_hint * 1.8)],
	                 ln >= 0 ? sprintf("Load (%g)", ln) : "Load (none)", av_hint, FALSE))
		Paint_Load("", FALSE);
	if (Profile_Chip("av_pauto", [pos_x + chw * 2 + 12, pos_y], [chw, ceil(av_hint * 1.8)], "Auto-load",
	                 av_hint, cvar("paint_autoload") != 0))
		cvar_set("paint_autoload", cvar("paint_autoload") ? "0" : "1");
	pos_y = pos_y + ceil(av_hint * 1.8) + 4;
	k = "";
	sk = "";
	if (checkbuiltin(findkeysforcommandex))
	{
		k = Gfx_Field(findkeysforcommandex("+paint"), 0, " ");
		if (k == "")
			k = Gfx_Field(findkeysforcommandex("paint"), 0, " ");
		sk = Gfx_Field(findkeysforcommandex("share"), 0, " ");
	}
	if (k == "")
		s = "Bind Paint (K) to spray";
	else
		s = sprintf("Hold %s to spray", strtoupper(k));
	s = (sk != "") ? sprintf("%s, %s at a player to share.", s, strtoupper(sk)) : strcat(s, ".");
	sui_text(pos, [av_hint, av_hint], Chat_Fit(s, w, av_hint), SUI_THEME_MUTED, 1, 0);
};

/*
  Patch 663: THE PROFILE.  One card in the UI's look: who you are (the name and
  picture a linked account plays under), a search for any player, and two
  pages: the customizer, and a breakdown like the site's player page
  (cl_profile.qc).  Picking a player from the search shows theirs.

  The title strip is the handle, and it is registered FIRST: of the elements
  under the cursor sui answers for the last, so the field and the chips on the
  strip win.  The type steps down until the card fits the window.
*/
void(vector scr) Av_Draw =
{
	local vector p, sz, tv, bv;
	local float i, x, y, y0, sw, fx, want, got, eff, askt, pad, tsz, ttl, hint, sc, me;
	local float hh, pic, fw, fh, lw, slh, stop, segw, tabh, segs, lit, stripw, striph, chw, link, fr_slot;
	local float pw, px, psw, ph;
	local string nm, mark, s, rgbstr, markstr, fr_target, profilemark;

	// The board is the older modal and draws over this; see Av_Open.
	if (!av_open || rec_sb_open)
		return;

	Profile_Frame();
	sui_begin(scr_x, scr_y);
	Font_Set(ui_font_ui);
	sc = ui_cv_scale;
	if (sc < 1)
		sc = 1;
	while (sc > 1 && (Font_Px(8 * sc) * 46 > scr_x - 8 || Font_Px(8 * sc) * 38 > scr_y - 8))
		sc = sc - 0.5;
	ttl  = Font_Px(10 * sc);
	tsz  = Font_Px(8 * sc);
	hint = Font_Px(6 * sc);
	av_hint = hint;
	av_rowh = ceil(tsz * 1.75);
	pad = tsz;
	pic = tsz * 3;
	hh  = pad * 2 + pic;
	fw  = tsz * 14;
	fh  = ceil(tsz * 1.9);
	link = FALSE;

	sz = [min(scr_x - 8, tsz * 46), min(scr_y - 8, tsz * 38)];
	p  = [cvar("hud_player_x") * scr_x - sz_x * 0.5, cvar("hud_player_y") * scr_y - sz_y * 0.5];
	// The handle is where the card will be drawn: clamped as it is, below.
	if (p_x + sz_x > scr_x - 4) p_x = scr_x - 4 - sz_x;
	if (p_y + sz_y > scr_y - 4) p_y = scr_y - 4 - sz_y;
	if (p_x < 4) p_x = 4;
	if (p_y < 4) p_y = 4;
	sui_action_element(p, [sz_x, hh], "av_drag", sui_noop);
	// sui_is_HELD: release fires as the grab ends (the first cut could not be dragged).
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
		p = [cvar("hud_player_x") * scr_x - sz_x * 0.5, cvar("hud_player_y") * scr_y - sz_y * 0.5];
	}
	if (p_x + sz_x > scr_x - 4) p_x = scr_x - 4 - sz_x;
	if (p_y + sz_y > scr_y - 4) p_y = scr_y - 4 - sz_y;
	if (p_x < 4) p_x = 4;
	if (p_y < 4) p_y = 4;
	p = [floor(p_x), floor(p_y)];
	sui_style_panel(p, sz, ceil(pad * 0.75), 0.98);

	// ---- who
	me = (av_other == "");
	// The lobby's mark for this player: an account's while the board is by account.
	mark = getplayerkeyvalue(player_localnum, "*ahash");
	if (mark == "") mark = getplayerkeyvalue(player_localnum, "*phash");
	if (!me)
		Profile_Show(av_other);
	else if (av_tab == AV_TAB_STATS && mark != "")
	{
		profilemark = getplayerkeyvalue(player_localnum, "*phash");
		Profile_Show(profilemark != "" ? profilemark : mark); // preserve GUID-board stats on legacy lobbies
	}
	fr_slot = Friends_ProfileSlot(av_other);
	fr_target = me ? "" : Friends_ProfileTarget(av_other);
	if (me)
	{
		nm = getplayerkeyvalue(player_localnum, "name");
		Profile_Face([p_x + pad, p_y + pad], pic, mark, mark != "", nm);
	}
	else if (fr_slot >= 0 && pf_state != PFS_OK)
	{
		nm = getplayerkeyvalue(fr_slot, "name");
		Profile_Face([p_x + pad, p_y + pad], pic, getplayerkeyvalue(fr_slot, "*ahash"), TRUE, nm);
	}
	else
	{
		nm = (pf_state == PFS_OK) ? pf_name : "";
		Profile_Face([p_x + pad, p_y + pad], pic, substring(pf_handle, 0, 8),
		             pf_state == PFS_OK && pf_av, nm);
	}
	x = p_x + pad * 2 + pic;
	sui_text([x, p_y + pad + 2], [ttl, ttl],
	         Chat_Fit(UI_NameShow(nm, 0), sz_x - pad * 4 - pic - fw, ttl), SUI_THEME_TEXT, 1, 0);
	y = p_y + pad + ttl + ceil(hint * 0.9);
	chw = ceil(hint * 8);
	if (me)
	{
		// What the lobby last said of this install (acct_is, cl_account.qc): words only.
		s = "This server keeps no accounts";
		tv = SUI_THEME_MUTED;
		if (acct_cl_is == 2) { s = "Steam account linked"; tv = SUI_THEME_GOOD; }
		else if (acct_cl_is == 3) { s = "This Steam account is banned here"; tv = SUI_THEME_BAD; }
		else if (acct_cl_is == 1) s = "Not linked to Steam";
		sui_text([x, y + 2], [hint, hint], s, tv, 1, 0);
		if (acct_cl_is == 1)
		if (Profile_Chip("av_link", [x + stringwidth(s, TRUE, [hint, hint]) + hint, y - 2],
		                 [chw, ceil(hint * 1.9)], "Link Steam", hint, FALSE))
			link = TRUE;
	}
	else
	{
		s = "";
		if (pf_state == PFS_OK)
		{
			s = Profile_TierTag(pf_src);
			if (Profile_Age(pf_last) != "")
				s = strcat(s, "   last time ", Profile_Age(pf_last), (Profile_Age(pf_last) == "today") ? "" : " ago");
		}
		sui_text([x, y + 2], [hint, hint], s, SUI_THEME_MUTED, 1, 0);
		if (Profile_Chip("av_back", [x + stringwidth(s, TRUE, [hint, hint]) + hint, y - 2],
		                 [chw, ceil(hint * 1.9)], "Back to me", hint, FALSE))
		{
			av_other = "";
			av_saidtab = FALSE;
		}
	}
	Profile_Field("pf_qa", [p_x + sz_x - pad - fw, p_y + pad], [fw, fh], tsz);
	sui_fill([p_x + pad, p_y + hh], [sz_x - pad * 2, 1], SUI_THEME_EDGE, 1, 0);

	// ---- the two pages
	y = p_y + hh + ceil(pad * 0.75);
	tabh = ceil(tsz * 1.9);
	segw = tsz * 7;
	if (me)
	{
		sui_roundbox([p_x + pad, y], [segw * 3, tabh], tabh * 0.5, SUI_THEME_WELL, 1);
		// NOT av_t0 and av_t1: the trail's swatches are av_t1 to av_t12, and a
		// press on the red one turned the page instead (663's review).
		if (Profile_Seg("av_pg0", [p_x + pad, y], [segw, tabh], "Customize", tsz, av_tab == AV_TAB_LOOK))
			av_tab = AV_TAB_LOOK;
		if (Profile_Seg("av_pg1", [p_x + pad + segw, y], [segw, tabh], "Stats", tsz, av_tab == AV_TAB_STATS))
		{
			av_tab = AV_TAB_STATS;
			av_namefocus = FALSE;
		}
		if (Profile_Seg("av_pg2", [p_x + pad + segw * 2, y], [segw, tabh], "Friends", tsz, av_tab == AV_TAB_FRIENDS))
		{
			av_tab = AV_TAB_FRIENDS;
			av_namefocus = FALSE;
		}
	}
	else
	{
		sui_text([p_x + pad, y + (tabh - hint) * 0.5], [hint, hint], "STATS", SUI_THEME_MUTED, 1, 0);
		if (fr_target != "" && getplayerkeyvalue(player_localnum, "*ahash") != "")
		if (Profile_Chip("av_friend", [p_x + sz_x - pad - segw * 1.5, y], [segw * 1.5, tabh],
		                 Friends_AddLabel(fr_target), tsz, FALSE))
			Friends_Add(fr_target);
	}
	y0 = y + tabh + ceil(pad * 0.75);
	if (!av_saidtab)
	{
		av_saidtab = TRUE;
		dprint(sprintf("hud_player: page %g of %s, card %gx%g at %g,%g, rows of %g\n",
		               me ? av_tab : AV_TAB_STATS, me ? "me" : av_other, sz_x, sz_y, p_x, p_y, tsz));
	}

	if (me && av_tab == AV_TAB_FRIENDS)
		Friends_Draw([p_x + pad, y0], [sz_x - pad * 2, p_y + sz_y - pad - y0], tsz, hint);
	else if (!me || av_tab == AV_TAB_STATS)
	{
		if (me && mark == "")
		{
			sui_text([p_x + pad, y0 + hint], [tsz, tsz],
			         (acct_cl_is == 1) ? "Link your Steam account to have a profile here"
			                           : "This server keeps no profile for you",
			         SUI_THEME_DIM, 1, 0);
			if (acct_cl_is == 1)
			if (Profile_Chip("av_link2", [p_x + pad, y0 + hint + tsz * 2], [tsz * 7, tabh], "Link Steam", tsz, FALSE))
				link = TRUE;
		}
		else
			Profile_DrawStats([p_x + pad, y0], [sz_x - pad * 2, p_y + sz_y - pad - y0], ttl, tsz, hint);
	}
	else
	{
		lw = floor((sz_x - pad * 3) * 0.6);
		x  = p_x + pad;
		y  = y0;
		sw = floor((lw - 11 * 6) / 12);
		if (sw > tsz * 2)
			sw = tsz * 2;
		slh = ceil(tsz * 1.25);

		// ---- name: Enter commits through the engine's `name` command, the one
		// channel that updates userinfo mid-connection.
		y = Av_Head([x, y], "NAME");
		sui_text_metrics(ceil(tsz * 0.7), [tsz, tsz]);
		sui_text_input("av_name", [x, y], [lw, fh], av_name_text, av_name_caret);
		if (sui_is_held("av_name") || sui_is_clicked("av_name"))
		{
			if (!av_namefocus)
				Profile_TookNone();
			av_namefocus = TRUE;
		}
		Profile_FieldLook("av_name", [x, y], [lw, fh], tsz, av_name_text, av_name_caret, "your name",
		                  av_namefocus, ceil(tsz * 0.5), ceil(tsz * 0.7));
		y = y + fh + ceil(hint * 0.5);
		y = Av_Wrap(x, y, lw, hint, "Enter to set. Linked accounts use their Steam name.",
		            SUI_THEME_MUTED);
		y = y + ceil(pad * 0.6);

		// ---- colour
		got  = cvar("cl_pcolour");          // the server's answer (float read)
		// ...and the index the TRAIL really uses: off a lobby it falls back to
		// the nearest entry. The swatch marks stay on `got`.
		eff  = got;
		if (eff < 1 || eff > AV_COLOURS)
			eff = Av_NearestColour(Av_MyRGB());
		want = Av_MyInfo("lobbycolor");     // your ask (0 = auto)
		rgbstr = getplayerkeyvalue(player_localnum, "lobbyrgb");
		chw = ceil(hint * 6.5);
		if (Profile_Chip("av_cauto", [x + lw - chw, y - 3], [chw, ceil(hint * 1.8)], "Random", hint,
		                 want == 0 && rgbstr == "" && getplayerkeyvalue(player_localnum, "lobbybody") == ""))
		{
			Av_SetInfo("lobbycolor", 0);
			Av_ClearRGB();
		}
		/*
		  Patch 773: the sliders follow what the half wears when that CHANGES: a lobby
		  echoes a setinfo a round trip later, and reading it every frame snapped a
		  knob back and let the next drag send the stale channels.
		*/
		s = sprintf("%g %s", av_half, Av_255(av_half ? Av_MyBody() : Av_MyMark()));
		if (strcmp(s, av_seen))
		{
			if (!sui_is_held("av_r") && !sui_is_held("av_g") && !sui_is_held("av_b"))
				av_rgb = (av_half ? Av_MyBody() : Av_MyMark()) * 255;
			if (av_seen)
				strunzone(av_seen);
			av_seen = strzone(s);
		}
		y = Av_Head([x, y], "COLOUR");
		y = y + 3;
		for (i = 1; i <= AV_COLOURS; i = i + 1)
		{
			if (Av_Swatch(sprintf("av_c%g", i), [x + (i - 1) * (sw + 6), y], sw, i,
			              !strcmp(Av_255(av_rgb * (1 / 255)), Av_255(Av_PaletteRGB(i))), FALSE))
				Av_PickPalette(i);
		}
		y = y + sw + ceil(pad * 0.6);

		// ---- which part the sliders edit (Patch 457: the body wears a cross)
		markstr = getplayerkeyvalue(player_localnum, "lobbymark");
		chw = ceil(hint * 5.5);
		if (Profile_Chip("av_hmark", [x, y], [chw, ceil(hint * 1.9)], "Belt", hint, av_half == 0))
		{
			av_half = 0;
			av_rgb = Av_MyMark() * 255;
		}
		if (Profile_Chip("av_hbody", [x + chw + 6, y], [chw, ceil(hint * 1.9)], "Body", hint, av_half == 1))
		{
			av_half = 1;
			av_rgb = Av_MyBody() * 255;
		}
		// "One colour" clears the MARK: the cross takes the body's colour and is gone.
		if (Profile_Chip("av_hplain", [x + lw - chw * 1.7, y], [chw * 1.7, ceil(hint * 1.9)], "One colour",
		                 hint, markstr == ""))
		{
			localcmd("setinfo lobbymark \"\"\n");
			av_half = 1;
			av_rgb = Av_MyBody() * 255;
		}
		y = y + ceil(hint * 1.9) + 6;
		// The third figure of a slider is a DIVISION COUNT (Patch 341bis).
		Av_Slider("av_r", [x, y], [lw, slh], 255, av_rgb_x, "Red", ftos(floor(av_rgb_x + 0.5)), Av_SetR, 255);
		y = y + slh + 2;
		Av_Slider("av_g", [x, y], [lw, slh], 255, av_rgb_y, "Green", ftos(floor(av_rgb_y + 0.5)), Av_SetG, 255);
		y = y + slh + 2;
		Av_Slider("av_b", [x, y], [lw, slh], 255, av_rgb_z, "Blue", ftos(floor(av_rgb_z + 0.5)), Av_SetB, 255);
		y = y + slh + 4;
		// The body is two parts; the trail is still a palette entry.
		tv = Av_MyMark() * 255;
		bv = Av_MyBody() * 255;
		if (markstr != "")
			s = sprintf("belt %g %g %g, body %g %g %g, trail %s",
			            floor(tv_x + 0.5), floor(tv_y + 0.5), floor(tv_z + 0.5),
			            floor(bv_x + 0.5), floor(bv_y + 0.5), floor(bv_z + 0.5), Av_ColourName(eff));
		else if (rgbstr != "" || getplayerkeyvalue(player_localnum, "lobbybody") != "")
			s = sprintf("body %g %g %g, trail %s",
			            floor(tv_x + 0.5), floor(tv_y + 0.5), floor(tv_z + 0.5), Av_ColourName(eff));
		else if (got >= 1 && got <= AV_COLOURS)
			s = sprintf("body %s", Av_ColourName(got));
		else if (want >= 1 && want <= AV_COLOURS)      // solo: nothing resolves the ask
			s = sprintf("body %s", Av_ColourName(want));
		else
			s = "body: the server's pick";
		sui_text([x, y], [hint, hint], Chat_Fit(s, lw, hint), SUI_THEME_MUTED, 1, 0);
		y = y + hint + ceil(pad * 0.7);

		// ---- effects
		y = Av_Head([x, y], "EFFECTS");
		fx = Av_MyInfo("lobbyfx");
		stop = (fx & AV_FX_TRAIL) ? Av_TrailLen() + 1 : 0;
		Av_Slider("av_fx1", [x, y], [lw, slh], AV_TRAILN, stop, "Trail",
		          stop == 0 ? "off" : Av_TrailLenName(stop - 1), Av_FxTrail, AV_TRAILN);
		y = y + slh + 6;
		chw = floor((lw - 6) / 2);
		if (Profile_Chip("av_fx3", [x, y], [chw, ceil(hint * 1.9)], "Glow", hint, (fx & AV_FX_GLOW) != 0))
			Av_FxGlow((fx & AV_FX_GLOW) ? 0 : 1);
		// The odd one out: a cvar that changes only what YOU see.
		if (Profile_Chip("av_fx4", [x + chw + 6, y], [chw, ceil(hint * 1.9)], "See my own", hint,
		                 cvar("cl_trailself") != 0))
			Av_FxSelf(cvar("cl_trailself") ? 0 : 1);
		y = y + ceil(hint * 1.9) + ceil(pad * 0.7);

		// ---- trail colour
		askt = Av_MyInfo("lobbytrail");
		chw = ceil(hint * 8);
		if (Profile_Chip("av_tauto", [x + lw - chw, y - 3], [chw, ceil(hint * 1.8)], "Match body", hint, askt == 0))
			Av_SetInfo("lobbytrail", 0);
		y = Av_Head([x, y], "TRAIL COLOUR");
		y = y + 3;
		sw = floor(sw * 0.7);
		for (i = 1; i <= AV_COLOURS; i = i + 1)
		{
			if (i == 1)
				av_dbg = [x, y, sw];
			if (Av_Swatch(sprintf("av_t%g", i), [x + (i - 1) * (sw + 6), y], sw, i,
			              askt == i || (askt == 0 && eff == i), askt == i))
				Av_SetInfo("lobbytrail", i);
		}
		y = y + sw + 8;
		// A REPRESENTATION of the trail, to scale: the preview body sways in
		// place and has no path to draw.
		striph = ceil(hint * 0.5);
		if (fx & AV_FX_TRAIL)
		{
			segs = ceil(lw / 4);
			stripw = lw / segs;
			lit = segs * (Av_TrailLen() + 1) / AV_TRAILN;
			for (i = 0; i < lit; i = i + 1)
				sui_fill([x + i * stripw, y], [stripw + 1, striph],
				         Av_PaletteRGB(askt >= 1 ? askt : eff), (1 - i / lit) * 0.85, 0);
		}
		else
			sui_fill([x, y + striph * 0.5], [lw, 1], SUI_THEME_EDGE, 1, 0);

		sui_text([x, p_y + sz_y - pad - hint], [hint, hint], "This is how other players see you.",
		         SUI_THEME_MUTED, 1, 0);

		// ---- Patch 772: paint, under the body in its column
		pw  = sz_x - pad * 3 - lw;
		px  = p_x + pad * 2 + lw;
		psw = min(floor((pw - 11 * 4) / 12), ceil(tsz * 1.4));
		ph  = ceil(hint * 1.6) + 3 + psw + 6 + (slh + 2) * 3 + ceil(hint * 1.8) + 4 + hint;
		Av_PaintPanel([px, p_y + sz_y - pad - ph], pw, psw, slh);

		// ---- the body, standing on the card beside its controls
		Av_Preview([px, y0], [pw, p_y + sz_y - pad * 2 - ph - y0]);
	}

	// The search's list, LAST: over everything, and the element sui answers for.
	Profile_Drop([p_x + sz_x - pad - max(fw, tsz * 18), p_y + pad + fh + 4], max(fw, tsz * 18), tsz, hint);
	Font_Reset();
	sui_end();

	if (Profile_BoardNavigate()) { Av_Close(); return; }
	s = Profile_TakePick();
	if (s != "")
	{
		av_other = s;
		av_namefocus = FALSE;
		av_saidtab = FALSE;
	}
	if (link)
	{
		// The link box asks for its own Enter: only a real key starts a link.
		Av_Close();
		localcmd("link\n");
	}
};

/*
  The panel's input.  The mouse is sui's; the absolute position is also STORED
  (the drag reads it a frame later).  A field that has the keyboard gets every
  key as it comes (sui_text_event): the search first, then the name.
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
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP)
		return FALSE;

	// Other-player ESC wins even when the profile search owns text focus.
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE && av_other != "")
	{
		Av_Close();
		return TRUE;
	}
	if (Profile_FieldEvent(evtype, scanx, chary))
		return TRUE;
	if (Friends_Wheel(evtype, scanx))
		return TRUE;
	if (Profile_Wheel(evtype, scanx, av_rowh))
		return TRUE;
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN)
		if (scanx == K_MOUSE1)
			_sui_mouse_move(_cursor_position, FALSE);
		sui_input_event(evtype, scanx, chary, devid);
		// A press is also how the name field loses the keyboard: its own draw
		// gives it back when the press was on it.
		if (evtype == IE_KEYDOWN)
			av_namefocus = FALSE;
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE)
	{
		if (av_namefocus)
		{
			av_namefocus = FALSE;           // first ESC leaves the field
			Profile_TookNone();
		}
		else
			Av_Close();
		return TRUE;
	}
	if (!av_namefocus)
		return FALSE;
	// Only the releases of keys the field took the press of (Profile_Took).
	if (evtype == IE_KEYUP)
	{
		sui_text_event(evtype, scanx, chary, "av_name", av_name_text, av_name_caret);
		return Profile_TookUp(scanx);
	}
	Profile_Took(scanx);
	if (scanx == K_ENTER || scanx == K_KP_ENTER)
	{
		// Through the quoted-cvar route the chat draft uses, so a name with
		// spaces or a semicolon arrives as exactly what was typed.
		if (strtrim(av_name_text) != "")
			Chat_RunSafe("name", strtrim(av_name_text));
		av_namefocus = FALSE;
		return TRUE;
	}
	sui_text_event(evtype, scanx, chary, "av_name", av_name_text, av_name_caret);
	return TRUE;
};

// Patch 667: one pasted character, into the name.  -> the field had the keyboard.
float(float c) Av_Paste =
{
	if (!av_open || !av_namefocus)
		return FALSE;
	sui_text_event(IE_KEYDOWN, 0, c, "av_name", av_name_text, av_name_caret);
	return TRUE;
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
	else if (argv(1) == "stats")            // Patch 663: the breakdown page, the player's own
	{
		Av_OpenAt("");
		av_tab = AV_TAB_STATS;
	}
	else if (argv(1) == "friends")
	{
		Av_OpenAt("");
		av_tab = AV_TAB_FRIENDS;
	}
	else if (argv(1) == "view")             // ...somebody's, by handle or mark
		Av_OpenAt(argv(2));
	else if (argv(1) == "find")             // ...and the search, as if typed
	{
		Av_Open();
		if (av_open)
			Profile_Type(argv(2));
	}
	else if (argv(1) == "scroll")           // ...and the results (or the tier's maps), by rows
	{
		if (pf_ct != "")
			pf_ct_scroll_y = max(0, stof(argv(2)) * av_rowh);
		else
			pf_scroll_y = max(0, stof(argv(2)) * av_rowh);
	}
	else if (argv(1) == "tier")             // Patch 666: a tier's bar; `u` the unrated, `off` the results
	{
		if (!av_open)
			return TRUE;                    // no card, no ask: a console line is not a reason for one
		if (argv(2) == "u")
			Profile_TierShow(-1);
		else if (argv(2) == "off" || argv(2) == "")
			Profile_TierShow(-2);
		else
			Profile_TierShow(stof(argv(2)));
	}
	else if (argv(1) == "kind")             // P853: the bars' kind of map, `all`, `surf` or `bhop`
		Profile_ModeShow((argv(2) == "surf") ? 1 : ((argv(2) == "bhop") ? 2 : 0));
	else if (argv(1) == "status")
		print(strcat(sprintf("hud_player: open %g page %g view \"%s\" breakdown %g of \"%s\" rows %g/%g",
		                     av_open, av_tab, av_other, pf_state, pf_who, pf_rn, pf_total),
		             sprintf("  search %g of \"%s\" found %g  lobby says %g", pf_s_state, pf_q_for, pf_s_n,
		                     acct_cl_is),
		             sprintf("  field %g,%g %gx%g on %gx%g keys %g", pf_f_p_x, pf_f_p_y, pf_f_sz_x, pf_f_sz_y,
		                     pf_f_scr_x, pf_f_scr_y, pf_q_focus),
		             sprintf("  board %g  trail %s at %g,%g %g", rec_sb_open,
		                     getplayerkeyvalue(player_localnum, "lobbytrail"), av_dbg_x, av_dbg_y, av_dbg_z),
		             // Patch 666, at the end: an older arm reads the line up to here.
		             sprintf("  tier \"%s\" %g maps %g/%g done %g", pf_ct, pf_ct_state, pf_ct_n, pf_ct_total,
		                     pf_ct_done),
		             sprintf("  bar %g,%g %gx%g", pf_bar_p_x, pf_bar_p_y, pf_bar_sz_x, pf_bar_sz_y),
		             sprintf("  kind %g split %g\n", pf_cm, pf_c_modes)));
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
	/*
	  PATCH 457: draw your OWN trail as well as everybody else's.  A CLIENT
	  cvar and not a userinfo key, because it changes nothing about how you
	  look to anyone -- it is a local view preference, like a crosshair.
	  Archived, and on by default: a trail you cannot see is one nobody tunes.
	*/
	registercvar("cl_trailself", "1", CVAR_ARCHIVE);

	registercvar("hud_player_x", "0.5", CVAR_ARCHIVE);
	registercvar("hud_player_y", "0.5", CVAR_ARCHIVE);
};
