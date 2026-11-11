/*
  P1425: the server takes a point_template's members out of the map at its first frame
  (sv_template.qc SV_TplBuild) and makes copies on ForceSpawn. A walker that reads the lump itself
  -- trigger prediction (cl_triggers.qc), drawn effects -- skips the same members, or it predicts or
  draws what is not there: surf_globalchaos' teleporter_07 triggers wait for a button. Kept, as on the
  server: members of a template with spawnflag 1, and parented ones (the server keeps those too).
  A solid member also stays on the server; the walkers here only take triggers and effects.
  P1432: Tpl_ClCopied also answers for a keeping template's names -- drawn from the lump AND copied.

  Tpl_ClLoad resets getentitytoken: call it BEFORE a walk, never inside one.
*/
string tpl_cl_map;
string tpl_cl_names;            // "\n" + lower-case member names + "\n"
string tpl_cl_wild;             // members named with a trailing '*', "\n"-separated
string tpl_cl_knames, tpl_cl_kwild;   // P1432: the same for templates with spawnflag 1 (kept, copied)

void(float force) Tpl_ClLoad =
{
	local string tok, key, cn, names, wild, knames, kwild, nm, keep;
	local float sf, p0, pn, opened;

	if (!force && tpl_cl_map != "" && tpl_cl_map == CL_LumpMapName())	// P1489
		return;
	names = knames = "\n";
	wild = kwild = "";
	opened = FALSE;
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		opened = TRUE;
		cn = keep = "";
		sf = 0;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if (key == "classname")
				cn = tok;
			else if (key == "spawnflags")
				sf = stof(tok);
			else if (substring(key, 0, 8) == "template" && stof(substring(key, 8, -1)) >= 1)
				keep = strcat(keep, tok, "\n");
		}
		if (cn != "point_template")
			continue;
		p0 = 0;
		while ((pn = strstrofs(keep, "\n", p0)) >= 0)
		{
			nm = strtolower(substring(keep, p0, pn - p0));
			p0 = pn + 1;
			if (strstrofs(nm, "*", 0) >= 0)
			{
				nm = strcat(substring(nm, 0, strstrofs(nm, "*", 0)), "\n");
				if (sf & 1)
					kwild = strcat(kwild, nm);
				else
					wild = strcat(wild, nm);
			}
			else if (sf & 1)
				knames = strcat(knames, nm, "\n");
			else
				names = strcat(names, nm, "\n");
		}
	}
	if (tpl_cl_map != "") strunzone(tpl_cl_map);
	if (tpl_cl_names != "") strunzone(tpl_cl_names);
	if (tpl_cl_wild != "") strunzone(tpl_cl_wild);
	if (tpl_cl_knames != "") strunzone(tpl_cl_knames);
	if (tpl_cl_kwild != "") strunzone(tpl_cl_kwild);
	// Not latched when the lump was unreadable (Patch 335: it can be at CSQC_WorldLoaded): the next walk asks again.
	tpl_cl_map = opened ? strzone(CL_LumpMapName()) : "";
	tpl_cl_names = strzone(names);
	tpl_cl_wild = (wild != "") ? strzone(wild) : "";
	tpl_cl_knames = strzone(knames);
	tpl_cl_kwild = (kwild != "") ? strzone(kwild) : "";
};

float(string tname, string names, string wild) Tpl_ClIn =
{
	local float p0, pn;
	local string pre;

	if (strstrofs(names, strcat("\n", tname, "\n"), 0) >= 0)
		return TRUE;
	p0 = 0;
	while ((pn = strstrofs(wild, "\n", p0)) >= 0)
	{
		pre = substring(wild, p0, pn - p0);
		p0 = pn + 1;
		if (substring(tname, 0, strlen(pre)) == pre)
			return TRUE;
	}
	return FALSE;
};

float(string tname, string parent) Tpl_ClMember =
{
	if (tname == "" || parent != "")
		return FALSE;
	return Tpl_ClIn(strtolower(tname), tpl_cl_names, tpl_cl_wild);
};

// P1432: the server copies it on ForceSpawn (a member, or named by a template with spawnflag 1).
float(string tname, string parent) Tpl_ClCopied =
{
	if (tname == "" || parent != "")
		return FALSE;
	tname = strtolower(tname);
	return Tpl_ClIn(tname, tpl_cl_names, tpl_cl_wild) || Tpl_ClIn(tname, tpl_cl_knames, tpl_cl_kwild);
};
