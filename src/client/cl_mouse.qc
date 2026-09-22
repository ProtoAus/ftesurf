/*
===========================================================================
  cl_mouse.qc -- the mouse pad.  Patch 390.

  A 16:10 box left of the key block (or at hud_mouse_x/y).  The dot moves by
  the degrees of turn the mouse is worth and wraps at the edges; its trail
  fades on the HUD clock: blue while +moveleft steers, orange while +moveright
  does, and the later press wins the colour the way it wins the move.  Live
  it is the hand: raw IE_MOUSEDELTA x sensitivity x |m_yaw| (|m_pitch| down),
  in_xflip undone, m_accel and m_filter not modelled.  In a replay or while spectating it is the view: per-frame angle
  deltas of the recorded or watched player.

  MPad_Track only observes: CL_InputChain calls it and ignores it, so the
  engine's input path and the .hid evidence are untouched.

      mousepad          status          mousepad reset    centre, clear
===========================================================================
*/

#define MPS_LIVE    1           // 0 = never set, so the first frame resets
#define MPS_REPLAY  2
#define MPS_SPEC    3
#define MPWIN     128           // sampled trail/(MPWIN-2) apart: the ring outlasts the trail
#define MPC_TURN  '0.45 0.70 1.00'  // the trail: the +left/+right bars' blue,
#define MPC_STRAFE '1.00 0.55 0.15' // orange while +moveright steers (Patch 404)

float  ui_mp_rx, ui_mp_ry;      // IE_MOUSEDELTA since the last frame, virtual px
float  ui_mp_nev;               // deltas seen (a harness counts its own against it)
float  ui_mp_src, ui_mp_key, ui_mp_key2;
vector ui_mp_lang;              // replay/spectate: last frame's angles
float  ui_mp_lt, ui_mp_lreal;   // board_now and cltime of the last update
vector ui_mp_pos;               // the dot, [0,1) both axes, y down
vector ui_mp_acc;               // unwrapped move since the last sample, panel units
vector ui_mp_last;              // last frame's move, degrees
float  ui_mp_wx, ui_mp_wy;      // net wraps, + = off right / bottom
float  ui_mp_brk, ui_mp_resets, ui_mp_snaps;
vector ui_mp_sp[MPWIN];         // u, v, board_now
vector ui_mp_sd[MPWIN];         // the unwrapped move into that sample; z = +moveright steering
float  ui_mp_st;                // this frame's colour: 1 = +moveright steers (Patch 404)
float  ui_mp_pa, ui_mp_pd;      // last frame's A/D, for the rising edges
float  ui_mp_newer;             // -1 = A pressed later, +1 = D, 0 = neither
float  ui_mp_head, ui_mp_len, ui_mp_lastt;
vector ui_mp_bpos, ui_mp_bsize; // the box, whole pixels
vector ui_mp_px;                // one physical pixel, virtual units

void() MPad_RegisterCvars =
{
	registercvar("hud_mouse",       "1",   CVAR_ARCHIVE);
	registercvar("hud_mouse_x",     "-1",  CVAR_ARCHIVE);   // -1: attached left of the keys
	registercvar("hud_mouse_y",     "-1",  CVAR_ARCHIVE);
	registercvar("hud_mouse_span",  "90",  CVAR_ARCHIVE);   // degrees edge to edge; height 10/16
	registercvar("hud_mouse_trail", "0.5", CVAR_ARCHIVE);   // seconds, 0 = dot only
	registercommand("mousepad");    // free: grepped the engine, plugins and src
};

void(float ev, float dx, float dy) MPad_Track =
{
	if (ev != IE_MOUSEDELTA)
		return;
	ui_mp_rx = ui_mp_rx + dx;       // every device's, summed
	ui_mp_ry = ui_mp_ry + dy;
	ui_mp_nev = ui_mp_nev + 1;
};

float() MPad_Span = { local float s; s = cvar("hud_mouse_span"); if (s < 5) s = 90; return s; };
float() MPad_Life = { return bound(0, cvar("hud_mouse_trail"), 2); };

void() MPad_Reset =
{
	ui_mp_pos  = '0.5 0.5 0';
	ui_mp_acc  = '0 0 0';
	ui_mp_head = 0;
	ui_mp_len  = 0;
	ui_mp_resets = ui_mp_resets + 1;
};

void() MPad_Push =
{
	if (fabs(ui_mp_acc_x) >= 1 || fabs(ui_mp_acc_y) >= 1)
		ui_mp_brk = ui_mp_brk + 1;      // MPad_Seg leaves it undrawn
	ui_mp_sp[ui_mp_head] = [ui_mp_pos_x, ui_mp_pos_y, board_now];
	ui_mp_sd[ui_mp_head] = [ui_mp_acc_x, ui_mp_acc_y, ui_mp_st];
	ui_mp_head = ui_mp_head + 1;
	if (ui_mp_head >= MPWIN)
		ui_mp_head = 0;
	if (ui_mp_len < MPWIN)
		ui_mp_len = ui_mp_len + 1;
	ui_mp_lastt = board_now;
	ui_mp_acc = '0 0 0';
};

// A replay teleport (Watch's snap table, keyed by the interval's start) in the
// recording time this frame covered.  cfit alone misses one a frame skipped.
float(float t0, float t1) MPad_ReplaySnap =
{
	local float i;

	for (i = 0; i < rec_wt_snn; i = i + 1)
		if (rec_wt_snt[i] > t0 - 0.05)
		if (rec_wt_snt[i] <= t1)
			return TRUE;
	return FALSE;
};

// After HUD_Draw has set board_now.  d is degrees: x right, y down.
void() MPad_Frame =
{
	local float src, key, key2, rdt, span, spanv, s, u, v, w, iv, t0;
	local float ka, kd, ra, rd;     // Patch 404
	local vector ang, d, ps, vs;

	src = MPS_LIVE;  key = 0;  key2 = 0;  ang = '0 0 0';
	if (rec_wt_on)
	{
		src = MPS_REPLAY;  key = rec_wt_rec;  key2 = rec_wt_t1;
		ang = [rec_wt_pitch, rec_wt_yaw, 0];
	}
	else if (spc_hud)
	{
		src = MPS_SPEC;  key = spc_stat;
		ang = spc_tang;                 // the watched body, every camera mode
	}

	rdt = cltime - ui_mp_lreal;
	ui_mp_lreal = cltime;
	if (rdt < 0 || rdt > 0.5)
		rdt = 0.5;
	d = [ui_mp_rx, ui_mp_ry, 0];
	ui_mp_rx = 0;
	ui_mp_ry = 0;

	/*
	  Patch 404: which of A/D is STEERING, not merely which is held -- blue for
	  +moveleft, orange for +moveright.  cl_iDrive (default 1) lets the later
	  press win and suppresses the earlier key until it is let go, so the colour
	  follows the same rule the mover does.  Patch 399 asked only "is either
	  held", which could not tell the two apart at all.

	  ITS OWN LATCH rather than HUD_DrawKeys' ui_kb_newer, which is the same six
	  lines: that one is updated inside HUD_DrawKeys, and the block is drawn only
	  `if (ui_cv_keys)` (cl_hud.qc:5650), so sharing it would freeze the pad's
	  colour for anyone who turns the key display off.
	*/
	if (src == MPS_REPLAY)
	{
		ka = (rec_wt_keys & FSI_LEFT)  ? TRUE : FALSE;
		kd = (rec_wt_keys & FSI_RIGHT) ? TRUE : FALSE;
	}
	else if (src == MPS_SPEC)
	{
		ka = (spc_hkeys & FSI_LEFT)  ? TRUE : FALSE;
		kd = (spc_hkeys & FSI_RIGHT) ? TRUE : FALSE;
	}
	else
	{
		ka = Keys_Held(FSK_LEFT);
		kd = Keys_Held(FSK_RIGHT);
	}

	ra = (ka && !ui_mp_pa);        // parenthesised: see AGENTS.md on `x = a && b`
	rd = (kd && !ui_mp_pd);
	if (ra != rd)
		ui_mp_newer = ra ? -1 : 1;
	else if (ra || (!ka && !kd))
		ui_mp_newer = 0;            // both in one frame, or neither held
	ui_mp_pa = ka;
	ui_mp_pd = kd;

	// With one key down IT steers, whatever the latch remembers of the press
	// before it -- the latch only turns on a rising edge, so a released D would
	// otherwise keep the colour while A is still held.
	if (ka && kd)
		s = (ui_mp_newer > 0);
	else
		s = kd;
	iv = ui_mp_st;
	ui_mp_st = s ? 1 : 0;

	// A new source, target or file, the clock going back, or a replay jumping
	// ahead (a seek): start clean.
	if (src != ui_mp_src || key != ui_mp_key || key2 != ui_mp_key2
	 || board_now < ui_mp_lt
	 || (src == MPS_REPLAY && board_now - ui_mp_lt > 0.1 + 2 * rdt * rec_wt_rate))
	{
		MPad_Reset();
		ui_mp_src = src;  ui_mp_key = key;  ui_mp_key2 = key2;
		ui_mp_lang = ang;
		ui_mp_lt = board_now;
		return;
	}
	t0 = ui_mp_lt;
	ui_mp_lt = board_now;
	span  = MPad_Span();
	spanv = span * 10 / 16;

	if (src == MPS_LIVE)
	{
		// Virtual px back to counts (pr_csqc.c:9359), as Spec_Look does.  The
		// hand, not the view: in_xflip undone, m_yaw/m_pitch signs dropped.
		ps = getproperty(VF_SCREENPSIZE);
		vs = getproperty(VF_SCREENVSIZE);
		if (vs_x > 0)
		if (vs_y > 0)
		{
			d_x = d_x * ps_x / vs_x;
			d_y = d_y * ps_y / vs_y;
		}
		if (cvar("in_xflip"))
			d_x = -d_x;
		s = cvar("sensitivity");
		d_x = d_x * s * fabs(cvar("m_yaw"));
		d_y = d_y * s * fabs(cvar("m_pitch"));
	}
	else
	{
		// Yaw grows turning left; pitch grows looking down.
		d_x = -Interp_Arc(ui_mp_lang_y, ang_y);
		d_y =  Interp_Arc(ui_mp_lang_x, ang_x);
		ui_mp_lang = ang;
		// A teleport, not a hand: move nothing, keep the trail.
		if (fabs(d_x) > WT_ASNAP || fabs(d_y) > WT_ASNAP
		 || (src == MPS_REPLAY && (rec_wt_cfit == INTERP_SNAP || MPad_ReplaySnap(t0, board_now)))
		 || (src == MPS_SPEC && (spc_tbp & BP_SNAP)))
		{
			ui_mp_snaps = ui_mp_snaps + 1;
			return;
		}
	}
	ui_mp_last = d;

	// QC's mod truncates toward zero; floor does not.
	u = ui_mp_pos_x + d_x / span;
	w = floor(u);
	ui_mp_wx = ui_mp_wx + w;
	u = u - w;
	if (u >= 1)
	{
		u = 0;                          // float32: -1e-9 - floor(-1e-9) rounds to 1
		ui_mp_wx = ui_mp_wx + 1;
	}
	v = ui_mp_pos_y + d_y / spanv;
	w = floor(v);
	ui_mp_wy = ui_mp_wy + w;
	v = v - w;
	if (v >= 1)
	{
		v = 0;
		ui_mp_wy = ui_mp_wy + 1;
	}
	ui_mp_pos = [u, v, 0];
	ui_mp_acc = ui_mp_acc + [d_x / span, d_y / spanv, 0];

	// A strafe key going down or up starts a sample, so the colour turns there.
	if (ui_mp_acc_x || ui_mp_acc_y)
	if (!ui_mp_len || iv != ui_mp_st || board_now - ui_mp_lastt >= max(0.004, MPad_Life() / (MPWIN - 2)))
		MPad_Push();
};

// Attached (either cvar < 0): the keys' height, 16:10, one gap left, tops aligned.
void(vector scr) MPad_Geom =
{
	local vector ps, vs, p, sz;

	ps = getproperty(VF_SCREENPSIZE);
	vs = getproperty(VF_SCREENVSIZE);
	ui_mp_px = '1 1 0';
	if (ps_x > 0)
	if (ps_y > 0)
		ui_mp_px = [vs_x / ps_x, vs_y / ps_y, 0];

	HUD_KeysGeom(scr);
	sz = [ui_kb_size_y * 1.6, ui_kb_size_y, 0];
	if (cvar("hud_mouse_x") < 0 || cvar("hud_mouse_y") < 0)
	{
		p = [ui_kb_pos_x - ui_kb_gap - sz_x, ui_kb_pos_y, 0];
		if (p_x < 0)                    // keys dragged to the left edge: their right
			p_x = ui_kb_pos_x + ui_kb_size_x + ui_kb_gap;
	}
	else
		p = [scr_x * cvar("hud_mouse_x"), scr_y * cvar("hud_mouse_y"), 0];

	// Whole pixels, so the 1 px edge is one column.
	ui_mp_bpos  = [floor(p_x / ui_mp_px_x + 0.5) * ui_mp_px_x,
	               floor(p_y / ui_mp_px_y + 0.5) * ui_mp_px_y, 0];
	ui_mp_bsize = [floor(sz_x / ui_mp_px_x + 0.5) * ui_mp_px_x,
	               floor(sz_y / ui_mp_px_y + 0.5) * ui_mp_px_y, 0];
};

// One trail stroke a -> b in screen units, colour/alpha ca/la at a and cb/lb at
// b, at the width MPad_Draw set (Line_Width).  Patch 432: anti-aliased, edges
// fading over a pixel (cl_lines.qc).  Queued 2D polygons: MPad_Draw's
// drawresetcliparea flushes them under the clip.
void(vector a, vector b, float t, vector ca, float la, vector cb, float lb) MPad_Stroke =
{
	Line_Seg2D(a, b, ca, la, cb, lb);
};

vector(float st) MPad_Colour = { return st ? MPC_STRAFE : MPC_TURN; };

// a -> b in panel units, b inside [0,1), |b-a| < 1.  The copy shifted back
// across the edge a lies past draws what the wrap carried over; the clip trims.
void(vector a, vector b, vector o, vector wh, float t, vector ca, float la, vector cb, float lb) MPad_Seg =
{
	local float sx, sy, i, j;

	if (a_x == b_x)
	if (a_y == b_y)
		return;
	if (fabs(b_x - a_x) >= 1 || fabs(b_y - a_y) >= 1)
		return;                         // a panel or more: no honest line
	sx = 0;  sy = 0;
	if (a_x < 0) sx = 1;  else if (a_x >= 1) sx = -1;
	if (a_y < 0) sy = 1;  else if (a_y >= 1) sy = -1;
	for (i = 0; i < 2; i = i + 1)
	{
		for (j = 0; j < 2; j = j + 1)
		{
			MPad_Stroke([o_x + (a_x + i * sx) * wh_x, o_y + (a_y + j * sy) * wh_y, 0],
			            [o_x + (b_x + i * sx) * wh_x, o_y + (b_y + j * sy) * wh_y, 0],
			            t, ca, la, cb, lb);
			if (!sy)
				break;
		}
		if (!sx)
			break;
	}
};

void(vector scr) MPad_Draw =
{
	local vector o, wh, p, d, q, dq;
	local float px, py, i, slot, os, age, oage, life, ds, sx, sy, t, ost;

	MPad_Frame();                   // hidden too: switching on shows now
	if (!cvar("hud_mouse"))
		return;
	MPad_Geom(scr);
	o = ui_mp_bpos;  wh = ui_mp_bsize;  px = ui_mp_px_x;  py = ui_mp_px_y;

	// HUD_Key's unlit ground; the edge is 1 px whatever hud_scale says.
	drawfill(o + [px, py], wh - [2 * px, 2 * py], '0 0 0', 0.35, 0);
	drawfill(o, [wh_x, py], '0.75 0.75 0.75', 0.5, 0);
	drawfill(o + [0, wh_y - py], [wh_x, py], '0.75 0.75 0.75', 0.5, 0);
	drawfill(o + [0, py], [px, wh_y - 2 * py], '0.75 0.75 0.75', 0.5, 0);
	drawfill(o + [wh_x - px, py], [px, wh_y - 2 * py], '0.75 0.75 0.75', 0.5, 0);

	drawsetcliparea(o_x + px, o_y + py, wh_x - 2 * px, wh_y - 2 * py);
	life = MPad_Life();
	t = max(px, ui_cv_scale);
	Line_PxFrame();
	Line_Width(t / px);
	if (life > 0)
	{
		// Not yet sampled: from the newest sample's colour to this frame's.
		ost = ui_mp_st;
		if (ui_mp_len)
		{
			slot = ui_mp_head - 1;
			if (slot < 0)
				slot = slot + MPWIN;
			dq = ui_mp_sd[slot];
			ost = dq_z;
		}
		MPad_Seg(ui_mp_pos - ui_mp_acc, ui_mp_pos, o, wh, t,
		         MPad_Colour(ost), 0.85, MPad_Colour(ui_mp_st), 0.85);
		for (i = 0; i < ui_mp_len; i = i + 1)
		{
			slot = ui_mp_head - 1 - i;
			if (slot < 0)
				slot = slot + MPWIN;
			p = ui_mp_sp[slot];
			age = board_now - p_z;
			if (age >= life)
				break;
			// The stroke starts at the older sample, faded to that sample's age.
			d = ui_mp_sd[slot];
			oage = life;
			ost = d_z;
			if (i + 1 < ui_mp_len)
			{
				os = slot - 1;
				if (os < 0)
					os = os + MPWIN;
				q = ui_mp_sp[os];
				oage = min(life, board_now - q_z);
				dq = ui_mp_sd[os];
				ost = dq_z;
			}
			MPad_Seg([p_x - d_x, p_y - d_y, 0], [p_x, p_y, 0], o, wh, t,
			         MPad_Colour(ost), 0.85 * (1 - oage / life),
			         MPad_Colour(d_z), 0.85 * (1 - age / life));
		}
	}

	// The dot, with a copy across any edge it straddles.
	ds = max(2 * px, floor(3 * ui_cv_scale / px + 0.5) * px);
	q = [o_x + ui_mp_pos_x * wh_x - ds * 0.5, o_y + ui_mp_pos_y * wh_y - ds * 0.5, 0];
	sx = 0;  sy = 0;
	if (q_x < o_x) sx = wh_x;  else if (q_x + ds > o_x + wh_x) sx = -wh_x;
	if (q_y < o_y) sy = wh_y;  else if (q_y + ds > o_y + wh_y) sy = -wh_y;
	drawfill(q, [ds, ds], '1 1 1', 0.95, 0);
	if (sx)
		drawfill(q + [sx, 0], [ds, ds], '1 1 1', 0.95, 0);
	if (sy)
		drawfill(q + [0, sy], [ds, ds], '1 1 1', 0.95, 0);
	if (sx)
	if (sy)
		drawfill(q + [sx, sy], [ds, ds], '1 1 1', 0.95, 0);
	drawresetcliparea();

	HUD_Rect("mouse", o, wh, o);     // anchor = top-left, what hud_mouse_x/y encode
};

float(string cmd) MPad_ConsoleCommand =
{
	local float i, slot, n, life;
	local vector p;

	if (argv(0) != "mousepad")
		return FALSE;
	if (argv(1) == "reset")
	{
		MPad_Reset();
		ui_mp_wx = 0;  ui_mp_wy = 0;  ui_mp_brk = 0;  ui_mp_snaps = 0;
		return TRUE;
	}
	MPad_Geom(getproperty(VF_SCREENVSIZE));
	life = MPad_Life();
	n = 0;
	for (i = 0; i < ui_mp_len; i = i + 1)
	{
		slot = ui_mp_head - 1 - i;
		if (slot < 0)
			slot = slot + MPWIN;
		p = ui_mp_sp[slot];
		if (board_now - p_z >= life)
			break;
		n = n + 1;
	}
	print(sprintf("mousepad: on %g src %g pos %.4f %.4f\n",
	              cvar("hud_mouse"), ui_mp_src, ui_mp_pos_x, ui_mp_pos_y));
	print(sprintf("  box %g %g %g %g px %g\n", ui_mp_bpos_x, ui_mp_bpos_y,
	              ui_mp_bsize_x, ui_mp_bsize_y, ui_mp_px_x));
	print(sprintf("  span %g trail %g samples %g live %g breaks %g\n",
	              MPad_Span(), life, ui_mp_len, n, ui_mp_brk));
	// Patch 404: held A/D, the rising-edge latch, and the colour it resolves to.
	print(sprintf("  keys a%g d%g  newer %s  colour %s\n",
	              ui_mp_pa, ui_mp_pd,
	              ui_mp_newer > 0 ? "d" : (ui_mp_newer < 0 ? "a" : "-"),
	              ui_mp_st ? "orange (+moveright)" : "blue (+moveleft/none)"));
	print(sprintf("  wraps %g %g resets %g snaps %g events %g\n",
	              ui_mp_wx, ui_mp_wy, ui_mp_resets, ui_mp_snaps, ui_mp_nev));
	print(sprintf("  last %.4f %.4f deg  lang %.3f %.3f\n",
	              ui_mp_last_x, ui_mp_last_y, ui_mp_lang_x, ui_mp_lang_y));
	// The key block's own latch, for comparison with the pad's above.  STALE when
	// hud_keys is off: HUD_DrawKeys is called only `if (ui_cv_keys)` and nothing
	// else updates it -- which is why Patch 404 keeps its own rather than share.
	print(sprintf("  keys a %g d %g newer %g cl_iDrive %g\n",
	              ui_kb_pa, ui_kb_pd, ui_kb_newer, cvar("cl_iDrive")));
	if (cvar("cl_threadedphysics"))
		print("  cl_threadedphysics: the engine sends no mouse deltas\n");
	return TRUE;
};
