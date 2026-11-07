/*
  P1378: passable func_tracktrains and the props riding them, drawn here every frame from the clock the
  server sends (ENTWIRE_TRKSTATE / ENTWIRE_TRKPROP, sv_entities.qc SV_TrkSend). The path comes from this
  map's own path_tracks, walked as the server walks them (sh_trk.qc), so nothing moves on the wire.
  csqc `time` is the server's clock.
*/
string trk_clmap;               // the map the path table was read for
.string trkc_tgt;               // a train's first path_track (zoned; the entity goes with the map)
.float  trkp_par;               // a rider's train, as a server entity number
.entity trkp_pent;              // ...found
.vector trkp_lo, trkp_la;       // its pose in the train's spawn frame
.float  trkp_drawn;

// The lump's path_tracks, once per map (and again if a walk finds nothing: Portal_Poll's reason --
// a map change can still show the previous lump for a moment).
void() Trk_ClLoad =
{
	local string tok, key, cn, nm, tgt, sorg, sfl;

	Trk_TableReset();
	if (trk_clmap)
		strunzone(trk_clmap);
	trk_clmap = strzone(serverkey("map"));
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = nm = tgt = sorg = sfl = "";
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")  cn = tok;
			else if (key == "targetname") nm = tok;
			else if (key == "target")     tgt = tok;
			else if (key == "origin")     sorg = tok;
			else if (key == "spawnflags") sfl = tok;
		}
		if (cn == "path_track")
			Trk_TableAdd(nm, tgt, stov(sorg), stof(sfl));
	}
	Trk_TableLink();
};

// The lump again (a walk found nothing), and every train's path from it: the reload freed the pool.
void() Trk_ClReload =
{
	local entity t;

	Trk_ClLoad();
	for (t = find(world, classname, "trk_train"); t; t = find(t, classname, "trk_train"))
		if (Trk_Walk(t, t.trkc_tgt))
		if (!t.trk_faced)
			Trk_FaceStart(t);
};

float() Trk_TrainPredraw =
{
	if (!self.trk_n || (self.effects & EF_NODRAW))
		return PREDRAW_NEXT;
	Trk_Place(self, time);
	setorigin(self, trk_o);
	self.angles = trk_a;
	return PREDRAW_AUTOADD;
};

void(entity e) Trk_NetTrain =
{
	local float sf, mi, s0, t0, spd, dir;
	local vector o0, a0;
	local string tgt;

	sf = readbyte();
	if (sf & TRK_SF_ID)
	{
		mi = readshort();
		o0_x = readfloat();
		o0_y = readfloat();
		o0_z = readfloat();
		a0_x = readfloat();
		a0_y = readfloat();
		a0_z = readfloat();
		tgt = readstring();
		e.trk_height = readfloat();
		e.trk_wheels = readfloat();
		e.trk_orient = readbyte();
		e.trk_sflags = readfloat();
		e.effects = readfloat();
		e.alpha = readfloat();
		e.colormod_x = readfloat();
		e.colormod_y = readfloat();
		e.colormod_z = readfloat();
		if (e.classname != "trk_train")     // the server may send an identity again: walk once
		{
			if (strcmp(trk_clmap, serverkey("map")))
				Trk_ClReload();
			e.classname = "trk_train";
			e.trkc_tgt = strzone(tgt);
			e.trk_o0 = o0;
			e.trk_a0 = a0;
			e.trk_alast = a0;
			e.trk_faced = FALSE;
			setmodelindex(e, mi);
			e.drawmask = MASK_ENGINE;
			e.predraw = Trk_TrainPredraw;
			if (!Trk_Walk(e, tgt))
				Trk_ClReload();
			if (e.trk_n)
				Trk_FaceStart(e);
			if (cvar("developer"))
				print(sprintf("trk(cl): %s rides %g path_tracks from %s, %g units%s\n", e.model, e.trk_n, tgt,
					e.trk_len, (e.trk_k >= 0) ? " round" : ""));
		}
	}
	if (sf & TRK_SF_CLOCK)
	{
		s0 = readfloat();
		t0 = readfloat();
		spd = readfloat();
		dir = readchar();
		e.trk_s0 = s0;
		e.trk_t0 = t0;
		e.trk_spd = spd;
		e.trk_dir = dir;
	}
};

float() Trk_PropPredraw =
{
	local entity p;

	if (self.effects & EF_NODRAW)
		return PREDRAW_NEXT;
	p = self.trkp_pent;
	if (!p || wasfreed(p) || p.entnum != self.trkp_par)
	{
		p = findfloat(world, entnum, self.trkp_par);
		self.trkp_pent = p;
	}
	if (!p || p.classname != "trk_train" || !p.trk_n)
		return self.trkp_drawn ? PREDRAW_AUTOADD : PREDRAW_NEXT;    // a killed train leaves it where it was
	Trk_Place(p, time);
	Trk_Ride(p, self.trkp_lo, self.trkp_la);
	setorigin(self, trk_o);
	self.angles = trk_a;
	self.frame1time = time;
	self.trkp_drawn = TRUE;
	return PREDRAW_AUTOADD;
};

void(entity e) Trk_NetProp =
{
	readbyte();                     // flags: one send, the identity
	e.trkp_par = readentitynum();
	e.trkp_lo_x = readfloat();
	e.trkp_lo_y = readfloat();
	e.trkp_lo_z = readfloat();
	e.trkp_la_x = readfloat();
	e.trkp_la_y = readfloat();
	e.trkp_la_z = readfloat();
	setmodelindex(e, readshort());
	e.skin = readbyte();
	e.scale = readfloat();
	e.frame = readshort();
	e.alpha = readfloat();
	e.effects = readfloat();
	e.colormod_x = readfloat();
	e.colormod_y = readfloat();
	e.colormod_z = readfloat();
	e.classname = "trk_prop";
	e.trkp_pent = world;
	e.drawmask = MASK_ENGINE;
	e.predraw = Trk_PropPredraw;
};
