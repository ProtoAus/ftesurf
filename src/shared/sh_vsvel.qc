// P1205: VScript velocity writes on the activator, parsed the same way by the server
// (sv_entities.qc SV_ScriptCode) and the client's trigger mirror (cl_triggers.qc). 2204-map
// census (lexlist4-20261102/artifacts/velcensus.py): ~2,250 outputs on ~40 maps, mostly
// trigger_teleport OnStartTouch !activator. The grammar they use:
//   [local flVelocity = self.GetAbsVelocity();] self.Set[Abs]Velocity( Vector(c c c) | Vector() ) [;]
// c: a number; the same axis read back (self.GetAbsVelocity().z, self.GetVelocity().z,
// flVelocity.z); or `that > N ? M : that`. Commas between parts are optional, as in
// Squirrel's call arguments. Anything else (a 4-part Vector, a missing paren, a part read
// from another axis) errors in Source or is not this grammar: FALSE, and nothing runs.

vector vsv_op, vsv_a, vsv_b;    // FS_VsVelParse's answer, per axis: op 0 keep, 1 set a, 2 (v > a) ? b : v

float(string s) FS_VsNum =
{
	local float i, c, digits, dot;
	digits = dot = FALSE;
	if (s == "") return FALSE;
	for (i = 0; i < strlen(s); i = i + 1)
	{
		c = str2chr(s, i);
		if (c == 45 && i == 0) continue;                    // '-'
		if (c == 46 && !dot) { dot = TRUE; continue; }      // '.'
		if (c < 48 || c > 57) return FALSE;
		digits = TRUE;
	}
	return digits;
};

// s is spaceless and lowercase.
float(string s, string ax, float al) FS_VsRead =
{
	return (s == strcat("self.getabsvelocity().", ax) || s == strcat("self.getvelocity().", ax)
	        || (al && s == strcat("flvelocity.", ax)));
};

// One part for axis ax ("x"/"y"/"z"): its op, with vsc_a/vsc_b; -1 if not the grammar.
float vsc_a, vsc_b;
float(string s, string ax, float al) FS_VsPart =
{
	local float q, c, g;
	s = strreplace(" ", "", s);
	if (FS_VsNum(s)) { vsc_a = stof(s); return 1; }
	if (FS_VsRead(s, ax, al)) return 0;
	q = strstrofs(s, "?", 0);
	c = strstrofs(s, ":", 0);
	g = strstrofs(s, ">", 0);
	if (g > 0 && q > g && c > q)
	if (FS_VsRead(substring(s, 0, g), ax, al) && FS_VsRead(substring(s, c + 1, -1), ax, al))
	if (FS_VsNum(substring(s, g + 1, q - g - 1)) && FS_VsNum(substring(s, q + 1, c - q - 1)))
	{
		vsc_a = stof(substring(s, g + 1, q - g - 1));
		vsc_b = stof(substring(s, q + 1, c - q - 1));
		return 2;
	}
	return -1;
};

float(string s, float i) FS_VsBlank =
{
	local float c;
	c = str2chr(s, i);
	return (c == 32 || c == 9);
};

string(string s) FS_VsTrim =
{
	while (s != "" && FS_VsBlank(s, 0))
		s = substring(s, 1, -1);
	while (s != "" && (FS_VsBlank(s, strlen(s) - 1) || str2chr(s, strlen(s) - 1) == 59))   // ';'
		s = substring(s, 0, strlen(s) - 1);
	return s;
};

// The first and last characters are ( and ): what is between, trimmed; else "!".
string(string s) FS_VsParens =
{
	if (strlen(s) < 2 || str2chr(s, 0) != 40 || str2chr(s, strlen(s) - 1) != 41)
		return "!";
	return FS_VsTrim(substring(s, 1, strlen(s) - 2));
};

float(string code) FS_VsVelParse =
{
	local float al, n, i, k, op;
	local string s, p, ax;

	s = FS_VsTrim(strtolower(strreplace("`", "", code)));
	al = FALSE;
	if (substring(s, 0, 16) == "local flvelocity")
	{
		k = strstrofs(s, ";", 0);
		if (k < 0 || strreplace(" ", "", substring(s, 0, k)) != "localflvelocity=self.getabsvelocity()")
			return FALSE;
		al = TRUE;
		s = FS_VsTrim(substring(s, k + 1, -1));
	}
	if (substring(s, 0, 19) == "self.setabsvelocity") s = FS_VsTrim(substring(s, 19, -1));
	else if (substring(s, 0, 16) == "self.setvelocity") s = FS_VsTrim(substring(s, 16, -1));
	else return FALSE;
	s = FS_VsParens(s);
	if (substring(s, 0, 6) != "vector") return FALSE;
	s = FS_VsParens(FS_VsTrim(substring(s, 6, -1)));
	if (s == "!") return FALSE;
	vsv_op = vsv_a = vsv_b = '0 0 0';
	if (s == "")
	{
		vsv_op = '1 1 1';              // Vector(): zero
		return TRUE;
	}
	n = tokenizebyseparator(s, (strstrofs(s, ",", 0) >= 0) ? "," : " ");
	k = 0;
	for (i = 0; i < n; i = i + 1)
	{
		p = argv(i);
		if (FS_VsTrim(p) == "") continue;   // runs of spaces
		if (k >= 3) return FALSE;
		ax = (k == 0) ? "x" : ((k == 1) ? "y" : "z");
		op = FS_VsPart(p, ax, al);
		if (op < 0) return FALSE;
		if (k == 0) { vsv_op_x = op; vsv_a_x = vsc_a; vsv_b_x = vsc_b; }
		if (k == 1) { vsv_op_y = op; vsv_a_y = vsc_a; vsv_b_y = vsc_b; }
		if (k == 2) { vsv_op_z = op; vsv_a_z = vsc_a; vsv_b_z = vsc_b; }
		k = k + 1;
	}
	return k == 3;
};

float(float v, float op, float a, float b) FS_VsAxis =
{
	if (op == 1) return a;
	if (op == 2) return (v > a) ? b : v;
	return v;
};

vector(vector v, vector op, vector a, vector b) FS_VsVelApply =
{
	return [FS_VsAxis(v_x, op_x, a_x, b_x), FS_VsAxis(v_y, op_y, a_y, b_y), FS_VsAxis(v_z, op_z, a_z, b_z)];
};

// Source matches "!activator" and friends case-insensitively (FStrEq); surf_fairy writes "!Activator".
float(string t) FS_IsActivator =
{
	t = strtolower(t);
	return (t == "!activator" || t == "!player" || t == "!caller");
};
