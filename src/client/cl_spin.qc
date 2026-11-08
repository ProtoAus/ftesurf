/*
  P1387: Patch 860's decorative movers in a chain that is non-solid throughout -- func_rotating,
  func_movelinear and the props that follow them -- posed here every frame from the clock the server
  sends (ENTWIRE_SPSTATE, sv_entities.qc SV_SpSend), with sh_spin.qc's functions and SV_SpPlace's
  composition (Trk_Ride). Poses are cached per time in trk_w* (sh_trk.qc), as trains are.
*/
.float  spc_kind, spc_par, spc_md, spc_sp;
.vector spc_lorg, spc_lang, spc_axis;
.float  spc_th0, spc_t0, spc_w0, spc_wt, spc_up, spc_dn, spc_stopping, spc_stopat;
.float  spc_pos, spc_ideal, spc_dir, spc_speed;
.entity spc_pent;
.float  spc_drawn;              // placed once: drawn where it was if what it rides goes
float   sp_query;               // Sp_Command: pose at another time, change nothing

entity(entity e) Sp_Parent =
{
	local entity p;

	if (!e.spc_par)
		return world;
	p = e.spc_pent;
	if (!p || wasfreed(p) || p.entnum != e.spc_par)
	{
		p = findfloat(world, entnum, e.spc_par);
		e.spc_pent = p;
	}
	if (p.classname != "sp_mover")
		return world;
	return p;
};

// e's pose at t into e.trk_w*; FALSE while a parent it needs has not arrived.
float(entity e, float t) Sp_Place =
{
	local entity p;
	local vector lo, la;
	local float th, wrap;

	if (e.trk_placet == t && t > 0)
		return TRUE;
	p = Sp_Parent(e);
	if (e.spc_par && !p)
		return FALSE;
	if (p)
	if (!Sp_Place(p, t))
		return FALSE;
	lo = e.spc_lorg;
	la = e.spc_lang;
	if (e.spc_kind == SPK_ROT)
	{
		th = Sp_Theta(e.spc_th0, e.spc_w0, e.spc_wt, e.spc_up, e.spc_dn, e.spc_stopping, e.spc_stopat, t - e.spc_t0);
		if (t - e.spc_t0 > 60 && !sp_query)
		{
			// SV_SpRotAnchor's re-anchor, so float32 keeps the phase all day without a resend.
			wrap = 360 * floor(th / 360);
			e.spc_th0 = th - wrap;
			e.spc_w0 = sp_wnow;
			e.spc_t0 = t;
			if (e.spc_stopping)
			{
				e.spc_stopat = e.spc_stopat - wrap;
				if (!sp_wnow)
				{
					e.spc_stopping = FALSE;
					e.spc_wt = 0;
				}
			}
			th = th - wrap;
		}
		la = la + e.spc_axis * th;
	}
	else if (e.spc_kind == SPK_LIN)
		lo = lo + e.spc_axis * (e.spc_md * (Sp_LinPos(e.spc_pos, e.spc_dir, e.spc_speed, t - e.spc_t0, e.spc_md,
		                                               e.spc_ideal) - e.spc_sp));
	if (p)
		Trk_Ride(p, lo, la);
	else
	{
		trk_o = lo;
		trk_a = la;
		Trk_Basis(la);
	}
	e.trk_placet = t;
	e.trk_wo = trk_o;
	e.trk_wa = trk_a;
	e.trk_wf = trk_bf;
	e.trk_wl = trk_bl;
	e.trk_wu = trk_bu;
	return TRUE;
};

// `sp_dump <t>`, sent by the server's `cmd spdump` (sv_cheats): every pose and train clock at that server
// time, to be compared with the server's own lines (sv_entities.qc SV_SpDump).
float() Sp_Command =
{
	local entity e;
	local float t;

	if (argv(0) != "sp_dump")
		return FALSE;
	t = stof(argv(1));
	sp_query = TRUE;                    // review 3: a dump re-anchored the client's own clocks
	for (e = find(world, classname, "sp_mover"); e; e = find(e, classname, "sp_mover"))
	{
		e.trk_placet = 0;
		if (Sp_Place(e, t))
		{
			print(sprintf("sp_dump #%g o %.3f %.3f %.3f", e.entnum, e.trk_wo_x, e.trk_wo_y, e.trk_wo_z));
			print(sprintf(" f %.4f %.4f %.4f", e.trk_wf_x, e.trk_wf_y, e.trk_wf_z));
			print(sprintf(" l %.4f %.4f %.4f\n", e.trk_wl_x, e.trk_wl_y, e.trk_wl_z));
		}
		else
			print(sprintf("sp_dump #%g unplaced\n", e.entnum));
		e.trk_placet = 0;
	}
	for (e = find(world, classname, "trk_train"); e; e = find(e, classname, "trk_train"))
		print(sprintf("sp_dump trk #%g s %.3f v %.3f m %g\n", e.entnum, Trk_S(e, t), trk_vnow, e.trk_vmode));
	sp_query = FALSE;
	print(sprintf("sp_dump end %.3f\n", t));
	return TRUE;
};

float() Sp_Predraw =
{
	// Drawn even where Patch 860 left it unwritten as tools-only ("draws nothing"): the engine drew those
	// at their spawn pose before; a toolsblack one now turns as in Source.
	if (gfx_movers_off || (self.effects & EF_NODRAW))
		return PREDRAW_NEXT;
	if (!Sp_Place(self, time))          // its parent has not arrived, or went without a Kill (review 3)
		return self.spc_drawn ? PREDRAW_AUTOADD : PREDRAW_NEXT;
	self.spc_drawn = TRUE;
	self.origin = self.trk_wo;
	self.angles = self.trk_wa;
	if (self.spc_kind == SPK_FOLLOW)
		self.frame1time = time;
	Trk_Relink(self);
	return PREDRAW_AUTOADD;
};

void(entity e) Sp_NetState =
{
	local float sf, r;

	sf = readbyte();
	if (sf & 1)
	{
		e.spc_kind = readbyte();
		setmodelindex(e, readshort());
		e.spc_par = readentitynum();
		e.spc_lorg_x = readfloat();
		e.spc_lorg_y = readfloat();
		e.spc_lorg_z = readfloat();
		e.spc_lang_x = readfloat();
		e.spc_lang_y = readfloat();
		e.spc_lang_z = readfloat();
		e.spc_axis_x = readfloat();
		e.spc_axis_y = readfloat();
		e.spc_axis_z = readfloat();
		e.spc_md = readfloat();
		e.spc_sp = readfloat();
		e.skin = readbyte();
		e.scale = readfloat();
		e.frame = readshort();
		e.alpha = readfloat();
		e.effects = readfloat();
		e.colormod_x = readfloat();
		e.colormod_y = readfloat();
		e.colormod_z = readfloat();
		// Linked by a box any turn stays inside (SV_SpWrite's reason), and on its first frame even near
		// the origin (Trk_Relink links on a move of 64).
		r = max(vlen(e.mins), vlen(e.maxs));
		setsize(e, '-1 -1 -1' * r, '1 1 1' * r);
		e.trkc_linko = '1000000 0 0';
		e.classname = "sp_mover";
		e.spc_pent = world;
		e.drawmask = MASK_ENGINE;
		e.predraw = Sp_Predraw;
	}
	if (sf & 2)
	{
		if (e.spc_kind == SPK_ROT)
		{
			e.spc_th0 = readfloat();
			e.spc_t0 = readfloat();
			e.spc_w0 = readfloat();
			e.spc_wt = readfloat();
			e.spc_up = readfloat();
			e.spc_dn = readfloat();
			e.spc_stopping = readbyte();
			e.spc_stopat = readfloat();
		}
		else if (e.spc_kind == SPK_LIN)
		{
			e.spc_pos = readfloat();
			e.spc_ideal = readfloat();
			e.spc_dir = readchar();
			e.spc_speed = readfloat();
			e.spc_t0 = readfloat();
		}
	}
	e.trk_placet = 0;                   // a new identity or clock: pose it again even if time is paused
};
