/*
===========================================================================
  cl_sprites.qc -- Source's sprite entities, drawn as world polygons.

  Five classes, 34909 instances across 551 of the 1310 shipped maps, and not one
  of them has ever drawn a pixel: they are point entities, so SSQC's catch-all
  removes them as "nothing to preserve", and nothing on the client ever looked
  for them.  They are the light glows on every lamp, the god-rays from every
  ceiling fixture, the fires, the halos and the flat billboard trees.

  WHAT IS DRAWN, measured over the whole library:

      point_spotlight       23666   413 maps   a light shaft
      env_sprite            10947   276 maps   a camera-facing billboard
      env_sprite_oriented     284     8 maps   a billboard fixed to its angles
      beam_spotlight           11     2 maps   point_spotlight's newer name
      env_glow                  1     1 map    point_spotlight's OLDER name

  WHAT IS NOT, and why -- both were in the plan and both were removed by
  measurement rather than by running out of time.  See the two essays further
  down, above Sprite_LoadForMap.

      env_spritetrail        2773   132 maps   needs its parent's MOTION
      env_lightglow          3393   137 maps   is a view-space flare, not a sprite

  WHY POLYGONS AND NOT ENTITIES.  A sprite is one quad with no collision and no
  state, so an entity each would be a CopyCSQCEdictToEntity call and a model
  slot for something R_BeginPolygon draws in six calls.  More decisively, the
  forcedshader entity path hardcodes SPR_VP_PARALLEL (gl_alias.c:3003-3009) and
  env_sprite_oriented needs a fixed world orientation, which that cannot
  express.  Polygons also batch: consecutive R_BeginPolygon calls with the same
  shader and flags do not flush (pr_csqc.c:1671), which is what the draw order
  below is arranged to exploit.

  THE COST IS SMALL, and the plan's estimate of it was wrong.  "24k polys" is
  the LIBRARY total, not a map's; the worst single map is bhop_rpg at 863
  drawables, then surf_grotto at 464.  So there is no cap and no LOD here, only
  a distance cull and a kill switch.
===========================================================================
*/

#define SPR_MAX      1024       // billboards.  Worst map (bhop_rpg) is 862.
#define BEAM_MAX      768       // light shafts.  Worst map (surf_grotto) is 464.
#define SPRMAT_MAX     96       // distinct materials.  Worst map is 34.

#define SPRK_BILLBOARD  0       // faces the viewer, stays upright
#define SPRK_ORIENTED   1       // fixed to the entity's own angles

// ---------------------------------------------------------------- materials
/*
  One entry per distinct material, because the SIZE has to be asked for and the
  answer costs a texture load.

  A Source sprite's world size is its texture's size in PIXELS times `scale`:
  spritemodel.cpp:317-330 sets the quad's half-extents to m_width/2 and
  m_height/2 with no other factor, and c_sprite.cpp:102-105 multiplies those by
  scale alone.  So one texel is one unit at scale 1, and a 128x128 glow at the
  library's median scale of 1 is 128 units across.

  There is exactly one builtin that can answer "how big is that texture" --
  drawgetimagesize -- and it blocks until the image has loaded
  (R_GetShaderSizes with blocktillloaded true, gl_shader.c:9442).  That is fine
  once per material at map load and would be unthinkable per sprite per frame,
  which is the whole reason this table exists.

  It resolves through R_RegisterPic and the draw resolves through
  R_RegisterCustom, so the two are separate shader objects keyed on different
  usage flags -- but both reach the same VMT through the same material loaders
  and therefore the same VTF, so the size is the size the drawn quad has.
*/
string sprmat_name[SPRMAT_MAX];         // the STEM, as R_BeginPolygon wants it
float  sprmat_w[SPRMAT_MAX];            // texture size in pixels, 0 = unresolved
float  sprmat_h[SPRMAT_MAX];
float  sprmat_n;
float  sprmat_zoned;                    // names hold strzone handles to give back

// ---------------------------------------------------------------- billboards
vector spr_org[SPR_MAX];
vector spr_col[SPR_MAX];                // 0..1
vector spr_right[SPR_MAX];              // unit basis, SPRK_ORIENTED only
vector spr_up[SPR_MAX];
float  spr_alpha[SPR_MAX];
float  spr_hw[SPR_MAX];                 // half-extents, world units
float  spr_hh[SPR_MAX];
float  spr_rad[SPR_MAX];                // cull radius, precomputed
float  spr_mat[SPR_MAX];                // index into the table above
float  spr_kind[SPR_MAX];
float  spr_add[SPR_MAX];                // TRUE = additive rendermode
float  spr_n;

// ------------------------------------------------------------------- beams
vector beam_org[BEAM_MAX];
vector beam_end[BEAM_MAX];
vector beam_col[BEAM_MAX];
float  beam_w0[BEAM_MAX];               // full width at the source
float  beam_w1[BEAM_MAX];               // ...and at the far end
float  beam_rad[BEAM_MAX];
float  beam_n;

// ------------------------------------------------------------------ counters
string vbsp_spr_map;                      // lazy-reload latch, as the decals use
float  vbsp_spr_seen;                     // sprite entities found, drawn or not
float  vbsp_spr_off;                      // skipped: named and not "start on"
float  vbsp_spr_nomat;                    // skipped: the material did not resolve
float  vbsp_spr_over;                     // skipped: hit SPR_MAX / BEAM_MAX
float  vbsp_beam_seen;
float  vbsp_beam_off;                     // skipped: the spotlight starts off
float  vbsp_trail_seen;                   // env_spritetrail, counted and declined
float  vbsp_glow_seen;                    // env_lightglow, counted and declined

/*
  The two materials Source hardcodes for a spotlight, named here for the same
  reason the classnames are: point_spotlight.cpp:135-136 precaches exactly these
  and the entity has no key to change them.
*/
#define BEAM_MATERIAL   "sprites/glow_test02"

/*
  A beam's alpha is FIXED at 64/255, and that is not an approximation.
  point_spotlight.cpp:372 calls SetBrightness(64) unconditionally after setting
  the colour, so `renderamt` -- which 91.6% of these entities write, 98.5% of
  them as 255 -- never reaches the beam at all.  Wiring renderamt in would make
  every light shaft in the library four times too bright.
*/
#define BEAM_BRIGHTNESS (64 / 255)

/*
===========================================================================
  Material names

  Three transformations, each of which Source itself performs, and all three
  are load-bearing on real maps:

    lowercase + backslashes         "materials\Sprites\Glow.vmt"
    strip a leading "materials/"    37 of 847 distinct names carry it, and
                                    VMT_ReadVMT adds its own (mat_vmt.c:2189)
    strip the extension             122 of 847 name a ".spr" -- the HL1 sprite
                                    container -- and Source resolves those by
                                    stem too (spritemodel.cpp:252,
                                    Q_StripExtension before the material lookup)

  That last one is what makes the .spr names work rather than fail: of 11232
  sprite instances only THREE name a .spr with no matching .vmt beside it.  Had
  the extension been kept, "sprites/glow01.spr" would have asked for
  materials/sprites/glow01.spr.vmt, and the single most common sprite material
  in the library -- 2132 instances, 19.5% of all of them -- would have drawn
  nothing.
===========================================================================
*/
string(string raw) Sprite_MatStem =
{
	local string s;
	local float  i, dot, n;

	s = strtolower(strreplace("\\", "/", raw));

	if (substring(s, 0, 10) == "materials/")
		s = substring(s, 10, -1);

	// The extension is the last '.' AFTER the last '/', so a directory with a
	// dot in it -- "_hl2/sprites/blueflare1" has none, but map-packed content
	// is not required to be tidy -- cannot eat the name.
	n = strlen(s);
	dot = -1;
	for (i = n - 1; i >= 0; i = i - 1)
	{
		if (substring(s, i, 1) == "/")
			break;
		if (substring(s, i, 1) == "." && dot < 0)
			dot = i;
	}
	if (dot > 0)
		s = substring(s, 0, dot);

	return s;
};

/*
  Resolve a material to a table index, loading its size the first time.

  Returns -1 if the texture will not resolve, and the caller DROPS the sprite
  rather than guessing a size.  That is deliberate: R_BeginPolygon falls back to
  Shader_PolygonShader for an unknown name, which is an untextured coloured
  quad -- so a guessed size would put a solid 64-unit square where a soft glow
  belongs, which is worse than the nothing that is there today.  4.7% of the
  library's sprite instances land here, almost all of them "sprites/glow.vmt",
  a name no mounted pack has ever contained.
*/
float(string raw) Sprite_Material =
{
	local string stem;
	local vector sz;
	local float  i;

	stem = Sprite_MatStem(raw);
	if (stem == "")
		return -1;

	for (i = 0; i < sprmat_n; i = i + 1)
		if (sprmat_name[i] == stem)
			return (sprmat_w[i] > 0) ? i : -1;

	if (sprmat_n >= SPRMAT_MAX)
		return -1;

	sz = drawgetimagesize(stem);

	i = sprmat_n;
	sprmat_name[i] = strzone(stem);
	sprmat_w[i] = sz_x;
	sprmat_h[i] = sz_y;
	sprmat_n = sprmat_n + 1;
	sprmat_zoned = TRUE;

	if (sz_x <= 0 || sz_y <= 0)
	{
		// Named, because "some sprites are missing" is not actionable and
		// "sprites/glow.vmt is missing" is.  Same contract as the plugin's
		// hl2_unresolved list.
		dprint(sprintf("sprites: no material for \"%s\"\n", stem));
		return -1;
	}
	return i;
};

void() Sprite_FreeMaterials =
{
	local float i;
	if (!sprmat_zoned)
	{
		sprmat_n = 0;
		return;
	}
	for (i = 0; i < sprmat_n; i = i + 1)
		if (sprmat_name[i] != "")
			strunzone(sprmat_name[i]);
	sprmat_n = 0;
	sprmat_zoned = FALSE;
};

/*
===========================================================================
  Building the two lists
===========================================================================
*/

// "255 128 0" and "255 128 0 200" both occur -- 2.3% of env_spritetrail's
// colours carry a fourth component.  Source's rendercolor is three; the fourth
// is ignored there and is ignored here.
vector(string s) Sprite_ParseColor =
{
	local vector c;
	local float  n;
	n = tokenize(s);
	if (n < 3)
		return '1 1 1';
	c = [stof(argv(0)), stof(argv(1)), stof(argv(2))];
	return c * (1 / 255);
};

vector(string s) Sprite_ParseVec =
{
	local float n;
	n = tokenize(s);
	if (n < 3)
		return '0 0 0';
	return [stof(argv(0)), stof(argv(1)), stof(argv(2))];
};

/*
  Add one billboard.

  `ang` is only read for SPRK_ORIENTED, and the basis it produces is Source's:
  c_sprite.cpp:319-323 hands the entity's angles straight to AngleVectors and
  uses the resulting right/up as the quad's axes.

  THE ANGLES OF AN ORIENTED SPRITE ARE NOT THE ANGLES IN THE LUMP, and this is
  the single easiest thing in this file to get wrong.  Sprite.cpp:855-863:

      CSpriteOriented::Spawn saves the authored angles, calls CSprite::Spawn --
      which swaps yaw into roll whenever yaw is non-zero and roll is zero
      (Sprite.cpp:219-227, commented "Worldcraft only sets y rotation") -- and
      then puts the SAVED angles back with 180 degrees added to the yaw.

  So the swap is undone and the flip is not, because "ORIENTED sprites forward
  vector points in the players view direction, not the direction out from the
  sprite (gah)" -- Valve's comment, not mine.  Net: authored angles, yaw + 180.
  Get either half wrong and bhop_murder's 208 trees and wall lamps face into
  the walls they are mounted on.
*/
void(vector org, vector ang, float kind, float mat, float scale,
     vector col, float alpha, float additive) Sprite_Add =
{
	local float i, hw, hh;

	if (spr_n >= SPR_MAX)
	{
		vbsp_spr_over = vbsp_spr_over + 1;
		return;
	}

	if (scale <= 0)
		scale = 1;              // DrawSpriteModel's own default, c_sprite.cpp:53-56

	hw = sprmat_w[mat] * scale * 0.5;
	hh = sprmat_h[mat] * scale * 0.5;
	if (hw <= 0 || hh <= 0)
		return;

	i = spr_n;
	spr_org[i]   = org;
	spr_col[i]   = col;
	spr_alpha[i] = alpha;
	spr_hw[i]    = hw;
	spr_hh[i]    = hh;
	spr_rad[i]   = sqrt(hw * hw + hh * hh);
	spr_mat[i]   = mat;
	spr_kind[i]  = kind;
	spr_add[i]   = additive;

	if (kind == SPRK_ORIENTED)
	{
		makevectors([ang_x, anglemod(ang_y + 180), ang_z]);
		spr_right[i] = v_right;
		spr_up[i]    = v_up;
	}
	else
	{
		spr_right[i] = '0 0 0';
		spr_up[i]    = '0 0 0';
	}

	spr_n = spr_n + 1;
};

/*
  Add one light shaft.

  Source builds this as a CBeam from the entity to a traced endpoint, and every
  number below is read off point_spotlight.cpp rather than chosen:

    :341-347  the endpoint is a trace of length 2*spotlightlength, or the full
              2x distance when IgnoreSolid is set.  The DOUBLE is not a typo --
              SpotlightCurrentPos traces "2 * m_flSpotlightMaxLength" so a beam
              that misses its intended surface still lands somewhere.
    :363      BeamInit(name, goalwidth) sets START width to spotlightwidth...
    :210-212  ...and the END width to goalwidth * (reached / intended), so a
              beam that stops short CONVERGES rather than staying parallel.
              Valve's comment there says "keep beam width constant", which
              describes the intent at full length, not the short case.
    :371      FBEAM_SHADEOUT with fade length equal to the reach, which
              beamdraw.cpp:359 turns into brightness = 1 - fraction: full at
              the source, zero at the far end.

  The trace is CSQC's, so it sees the world and not brush entities, where
  Source uses MASK_SOLID_BRUSHONLY and sees both.  A spotlight aimed at a door
  or a moving platform therefore reaches past it to the wall behind.  It is one
  traceline per spotlight at map load and none afterwards.
*/
void(vector org, vector ang, float len, float wid, float ignoresolid, vector col) Beam_Add =
{
	local float  i, curlen;
	local vector dir, endp;

	if (beam_n >= BEAM_MAX)
	{
		vbsp_spr_over = vbsp_spr_over + 1;
		return;
	}

	// Source's own repair of a nonsense key, point_spotlight.cpp:213-221.
	if (len <= 0)
		len = 500;
	if (wid <= 0)
		wid = 10;

	makevectors(ang);
	dir = v_forward;

	endp = org + dir * (2 * len);
	if (!ignoresolid)
	{
		traceline(org, endp, MOVE_NOMONSTERS, world);
		if (trace_fraction < 1)
			endp = trace_endpos;
	}

	curlen = vlen(endp - org);
	if (curlen < 1)
		return;

	i = beam_n;
	beam_org[i] = org;
	beam_end[i] = endp;
	beam_col[i] = col;
	beam_w0[i]  = wid;
	beam_w1[i]  = wid * (curlen / len);
	beam_rad[i] = curlen * 0.5 + wid;
	beam_n = beam_n + 1;
};

/*
===========================================================================
  Reading the entity lump

  WHY env_spritetrail IS COUNTED AND NOT DRAWN.  It is the third largest class
  in this family -- 2773 instances across 132 maps -- and it is not a sprite at
  a place, it is a RIBBON THROUGH A PATH.  95.1% of them carry a `parentname`,
  and the parents are named `spritetrial_rotate_end2`, `knife_spin`,
  `doorrottimer`, `rotating3`: brush entities that turn.  The trail is the
  streak the sprite leaves as its parent swings it around, and a trail whose
  points all coincide draws nothing in Source either.  So the honest options
  were a stationary blob where a moving streak belongs, or this line in the
  status print.  Drawing it would need server-side parenting and the parent's
  motion replicated to the client, which is a different feature.

  WHY env_lightglow IS COUNTED AND NOT DRAWN.  This one is not in the plan at
  all -- the plan's census listed nine classes and this was not among them,
  which was an omission, because at 3393 instances across 137 maps it is bigger
  than env_spritetrail.  It is declined for a better reason than size:
  glow_overlay.cpp:330-331 places it at a FIXED 100 units in front of the
  camera along the direction to the glow, scales it by 70x to 150x depending on
  the view dot product (:288-308), and gates it on an occlusion query
  (:313 UpdateGlowObstruction).  Its apparent size does not change with
  distance.  That is a lens-flare renderer, not a world billboard, and half of
  it -- a world quad at HorizontalGlowSize units -- would be a small dull
  square where a large soft flare belongs.  The keys are all there
  (HorizontalGlowSize, VerticalGlowSize, MinDist, MaxDist, OuterMaxDist on
  98.9% of them), so it is buildable; it is simply a second renderer.
===========================================================================
*/
void() Sprite_LoadForMap =
{
	local string tok, key, cn, map, model, srendercolor;
	local vector org, ang, col;
	local float  scale, renderamt, rendermode, spawnflags, framerate;
	local float  splen, spwid, ignoresolid;
	local float  opened, wantspr, wantbeam, mat, alpha, additive, named;

	map = serverkey("map");
	if (map == "")
		return;

	wantspr  = cvar("vbsp_sprites");
	wantbeam = cvar("vbsp_spotlights");

	Sprite_FreeMaterials();
	spr_n = beam_n = 0;
	vbsp_spr_seen = vbsp_spr_off = vbsp_spr_nomat = vbsp_spr_over = 0;
	vbsp_beam_seen = vbsp_beam_off = 0;
	vbsp_trail_seen = vbsp_glow_seen = 0;
	opened = FALSE;

	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		opened = TRUE;

		cn = model = srendercolor = "";
		org = ang = '0 0 0';
		scale = framerate = 0;
		renderamt = 255;
		rendermode = 0;
		spawnflags = 0;
		splen = spwid = ignoresolid = 0;
		named = FALSE;

		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if      (key == "classname")   cn = tok;
			else if (key == "model")       model = tok;
			else if (key == "origin")      org = Sprite_ParseVec(tok);
			else if (key == "angles")      ang = Sprite_ParseVec(tok);
			else if (key == "scale")       scale = stof(tok);
			else if (key == "renderamt")   renderamt = stof(tok);
			else if (key == "rendermode")  rendermode = stof(tok);
			else if (key == "rendercolor") srendercolor = tok;
			else if (key == "spawnflags")  spawnflags = stof(tok);
			else if (key == "framerate")   framerate = stof(tok);
			else if (key == "targetname")  named = (tok != "");
			// The library writes both spellings of each of these three, so both
			// are read: 1.9% of point_spotlights write "hdrcolorscale" and 0.5%
			// write "ignoresolid" against the FGD's capitalised forms.
			else if (key == "spotlightlength" || key == "SpotlightLength") splen = stof(tok);
			else if (key == "spotlightwidth"  || key == "SpotlightWidth")  spwid = stof(tok);
			else if (key == "IgnoreSolid"     || key == "ignoresolid")     ignoresolid = stof(tok);
		}

		col = Sprite_ParseColor(srendercolor);
		if (srendercolor == "")
			col = '1 1 1';

		if (cn == "env_sprite" || cn == "env_sprite_oriented" || cn == "env_glow")
		{
			vbsp_spr_seen = vbsp_spr_seen + 1;
			if (!wantspr)
				continue;

			/*
			  The start-on gate, and it is NOT "spawnflags & 1".

			  Sprite.cpp:208-216 turns a sprite off only if it has a targetname
			  AND lacks the flag -- an UNNAMED sprite is on whatever its
			  spawnflags say.  That distinction decides thousands of sprites:
			  49.2% of the library writes spawnflags 1 and 50.8% writes 0, so
			  reading the flag alone would blank half of every map; only 8.7%
			  carry a targetname, so the real number turned off is small.
			*/
			if (named && !(spawnflags & 1))
			{
				vbsp_spr_off = vbsp_spr_off + 1;
				continue;
			}

			// kRenderNone.  Source draws nothing; neither do we.
			if (rendermode == 10)
			{
				vbsp_spr_off = vbsp_spr_off + 1;
				continue;
			}

			if (model == "")
				continue;
			mat = Sprite_Material(model);
			if (mat < 0)
			{
				vbsp_spr_nomat = vbsp_spr_nomat + 1;
				continue;
			}

			alpha = renderamt * (1 / 255);
			if (alpha <= 0)
				alpha = 1;              // no renderamt means opaque, not invisible
			if (alpha > 1)
				alpha = 1;

			/*
			  Which rendermodes are additive: 3 kRenderGlow, 5 kRenderTransAdd,
			  9 kRenderWorldGlow.  Together they are 82.5% of the library's
			  sprites, which is what a light glow is.  Everything else keeps the
			  VMT's own blendfunc, because Source picks a per-rendermode MATERIAL
			  VARIANT (c_sprite.cpp:65) and there is no equivalent here -- the
			  material's own opinion is the closest available answer.
			*/
			additive = (rendermode == 3 || rendermode == 5 || rendermode == 9);

			Sprite_Add(org, ang,
			           (cn == "env_sprite_oriented") ? SPRK_ORIENTED : SPRK_BILLBOARD,
			           mat, scale, col, alpha, additive);
		}
		else if (cn == "point_spotlight" || cn == "beam_spotlight")
		{
			vbsp_beam_seen = vbsp_beam_seen + 1;
			if (!wantbeam)
				continue;

			/*
			  SF_SPOTLIGHT_START_LIGHT_ON.  Unlike env_sprite above this one IS
			  a plain flag test: point_spotlight.cpp:182 sets m_bSpotlightOn from
			  the flag alone, and Activate (:262) only builds the beam if it is
			  set.  3.3% of the library -- spawnflags 0 and 2 -- starts dark.
			*/
			if (!(spawnflags & 1))
			{
				vbsp_beam_off = vbsp_beam_off + 1;
				continue;
			}

			Beam_Add(org, ang, splen, spwid, ignoresolid, col);
		}
		else if (cn == "env_spritetrail")
			vbsp_trail_seen = vbsp_trail_seen + 1;
		else if (cn == "env_lightglow")
			vbsp_glow_seen = vbsp_glow_seen + 1;
	}

	// Same guard the decals use: serverkey("map") can lead the entity data by a
	// frame, and latching before the lump was readable means never looking again.
	if (!opened)
		return;
	vbsp_spr_map = map;

	/*
	  One line per family, and every skipped entity is accounted for by name.

	  The four sprite numbers are made to sum to the total for the same reason
	  the overlay line's do: the misses are unrelated things with unrelated
	  fixes -- one we decline because Source declines it too, one is missing
	  content, one is a cap that would need raising -- and a bare "N of M" would
	  hide which.
	*/
	if (vbsp_spr_seen)
	{
		if (!wantspr)
			print(sprintf("sprites: %g found, none drawn (vbsp_sprites 0)\n", vbsp_spr_seen));
		else if (vbsp_spr_off + vbsp_spr_nomat + vbsp_spr_over)
			print(sprintf("sprites: %g of %g drawn (%g off, %g no material, %g over cap)\n",
			              spr_n, vbsp_spr_seen, vbsp_spr_off, vbsp_spr_nomat, vbsp_spr_over));
		else
			print(sprintf("sprites: %g of %g drawn\n", spr_n, vbsp_spr_seen));
	}

	if (vbsp_beam_seen)
	{
		if (!wantbeam)
			print(sprintf("spotlights: %g found, none drawn (vbsp_spotlights 0)\n", vbsp_beam_seen));
		else if (vbsp_beam_off)
			print(sprintf("spotlights: %g of %g drawn (%g start off)\n",
			              beam_n, vbsp_beam_seen, vbsp_beam_off));
		else
			print(sprintf("spotlights: %g of %g drawn\n", beam_n, vbsp_beam_seen));
	}

	// Declined, not forgotten.  See the essay above this function for why each
	// is a different renderer rather than a missing branch.
	if (vbsp_trail_seen || vbsp_glow_seen)
		dprint(sprintf("sprites: declined %g env_spritetrail (needs parent motion), %g env_lightglow (view-space flare)\n",
		               vbsp_trail_seen, vbsp_glow_seen));
};

/*
===========================================================================
  Drawing

  Runs beside Zone_Draw, before renderscene, for the same reason: R_BeginPolygon
  queues into the scene rather than over it, so a sprite behind a wall is
  correctly hidden by the wall.
===========================================================================
*/
/*
  a b c d are top-left, top-right, bottom-right, bottom-left.

  T RUNS DOWNWARD, and getting that backwards is invisible on exactly the
  materials you would test with.  Source's own quad (c_sprite.cpp:110-131) pairs
  the TOP two corners with flMinV and the bottom two with flMaxV, so v=0 is the
  top of the image -- the ordinary top-left texture origin.  Nearly every sprite
  in the library is a radially symmetric glow, which looks identical either way;
  kz_anubis's timer digits and bhop_murder's trees do not.
*/
void(vector a, vector b, vector c, vector d, string mat, float flags,
     vector col, float alpha) Sprite_Quad =
{
	R_BeginPolygon(mat, flags);
	R_PolygonVertex(a, '0 0 0', col, alpha);
	R_PolygonVertex(b, '1 0 0', col, alpha);
	R_PolygonVertex(c, '1 1 0', col, alpha);
	R_PolygonVertex(d, '0 1 0', col, alpha);
	R_EndPolygon();
};

void() Sprite_Draw =
{
	local float  i, m, maxdist, drawn, dbg;
	local vector eye, fwd, vright, r, u, dd;
	local vector a, b, c, d, side, mid;
	local float  flags;

	if (serverkey("map") != vbsp_spr_map)
		Sprite_LoadForMap();

	if (!spr_n && !beam_n)
		return;

	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;

	maxdist = cvar("vbsp_sprite_dist");
	drawn = 0;

	dbg = cvar("vbsp_sprite_debug");
	if (dbg)
	{
		cvar_set("vbsp_sprite_debug", "0");
		print(sprintf("vbsp_sprite_debug: %g sprites, %g beams, %g materials, maxdist %g\n",
		              spr_n, beam_n, sprmat_n, maxdist));
		for (m = 0; m < sprmat_n; m = m + 1)
			print(sprintf("  %2g %-40s %gx%g\n", m, sprmat_name[m], sprmat_w[m], sprmat_h[m]));
	}

	/*
	  SPR_VP_PARALLEL_UPRIGHT, which is Source's default for any sprite whose
	  material does not say otherwise (spritemodel.cpp:311).  It is NOT a
	  full billboard: up stays world +Z and only the right vector turns, so a
	  tall glow does not tip over as you look up at it.

	  c_sprite.cpp:305-309 derives right from the VIEW direction rather than
	  from the direction to each sprite, which is why this is computed once here
	  and not per sprite.  Its degenerate case is looking almost straight up or
	  down; Source declines to draw within one degree of vertical (:301-303) and
	  so does the guard below.
	*/
	vright = normalize([fwd_y, -fwd_x, 0]);
	if (fwd_z > 0.999848 || fwd_z < -0.999848)
		vright = '0 1 0';   // looking straight up: any horizontal axis will do

	/*
	  Materials in the OUTER loop.  Consecutive polygons sharing a shader and
	  flags do not flush the batch (pr_csqc.c:1671), so walking the sprites in
	  material order turns bhop_rpg's 862 quads into roughly 30 draw calls
	  instead of 862.  The cost is sprmat_n passes over the array -- at most 96
	  times 1024 tests of one float, once per frame, and no work at all for the
	  ones that do not match.
	*/
	for (m = 0; m < sprmat_n; m = m + 1)
	{
		if (sprmat_w[m] <= 0)
			continue;

		for (i = 0; i < spr_n; i = i + 1)
		{
			if (spr_mat[i] != m)
				continue;

			dd = spr_org[i] - eye;

			// Distance and behind-camera, off the precomputed radius.  Same two
			// tests Zone_Draw uses, and for the same reason: CSQC polygons get
			// no PVS and no frustum cull from the engine.
			if (maxdist > 0 && vlen(dd) - spr_rad[i] > maxdist)
				continue;
			if (fwd * dd < -spr_rad[i])
				continue;

			if (spr_kind[i] == SPRK_ORIENTED)
			{
				r = spr_right[i] * spr_hw[i];
				u = spr_up[i]    * spr_hh[i];
				// An oriented quad has a fixed normal and the player can walk
				// behind it -- 208 of bhop_murder's are trees you can circle.
				// Without this the far side is culled away (pr_csqc.c:1666).
				flags = DRAWFLAG_TWOSIDED;
			}
			else
			{
				r = vright  * spr_hw[i];
				u = '0 0 1' * spr_hh[i];
				flags = 0;
			}
			if (spr_add[i])
				flags = flags | DRAWFLAG_ADD;

			a = spr_org[i] - r + u;
			b = spr_org[i] + r + u;
			c = spr_org[i] + r - u;
			d = spr_org[i] - r - u;

			Sprite_Quad(a, b, c, d, sprmat_name[m], flags, spr_col[i], spr_alpha[i]);
			drawn = drawn + 1;
		}
	}

	/*
	  The light shafts, all one material, so the whole set is one batch.

	  The quad is camera-facing about the beam's own axis -- the same
	  construction Zone_Quad uses for a thick line -- with the two widths and
	  the SHADEOUT alpha ramp applied at the two ends.
	*/
	for (i = 0; i < beam_n; i = i + 1)
	{
		mid = (beam_org[i] + beam_end[i]) * 0.5;
		dd = mid - eye;

		if (maxdist > 0 && vlen(dd) - beam_rad[i] > maxdist)
			continue;
		if (fwd * dd < -beam_rad[i])
			continue;

		side = crossproduct(normalize(beam_end[i] - beam_org[i]), normalize(dd));
		if (side == '0 0 0')
			continue;               // looking straight down the beam
		side = normalize(side);

		a = beam_org[i] - side * (beam_w0[i] * 0.5);
		b = beam_org[i] + side * (beam_w0[i] * 0.5);
		c = beam_end[i] + side * (beam_w1[i] * 0.5);
		d = beam_end[i] - side * (beam_w1[i] * 0.5);

		// Alpha at the source, zero at the far end: FBEAM_SHADEOUT with a fade
		// length equal to the reach, beamdraw.cpp:359-361.
		// s runs across the width, t along the length from the source outward.
		R_BeginPolygon(BEAM_MATERIAL, DRAWFLAG_ADD);
		R_PolygonVertex(a, '0 0 0', beam_col[i], BEAM_BRIGHTNESS);
		R_PolygonVertex(b, '1 0 0', beam_col[i], BEAM_BRIGHTNESS);
		R_PolygonVertex(c, '1 1 0', beam_col[i], 0);
		R_PolygonVertex(d, '0 1 0', beam_col[i], 0);
		R_EndPolygon();
		drawn = drawn + 1;
	}

	if (dbg)
		print(sprintf("vbsp_sprite_debug: %g of %g passed the cull\n",
		              drawn, spr_n + beam_n));
};

/*
  Called from CSQC_WorldLoaded, which is where reading the entity lump belongs.

  The lazy serverkey("map") compare in Sprite_Draw stays as the safety net for
  the paths that never reach that hook -- demo playback among them -- exactly as
  Portal_Poll does.  Once this has run the compare matches and costs one string
  test a frame.
*/
void() Sprite_LoadFromWorld =
{
	Sprite_LoadForMap();
};
