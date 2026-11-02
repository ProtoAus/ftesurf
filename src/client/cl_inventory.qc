/* Account inventory and procedural cosmetics. Only the lobby publishes *kit.
   Depth-tested soft ice halo: no world depth capture / wallhack.
   Hat geometry and both shaders travel in CSQC; no external model required. */
float inv_ready, inv_revision, inv_roles, inv_own1, inv_own2, inv_colour, inv_eq1, inv_eq2, inv_wait;
string inv_who;
entity inv_shell;
float inv_shader;

vector(float colour) Inv_Colour = { return sui_inventory_colour(colour); };

void() Inv_Init =
{
	registercommand("inventory");
	registercommand("inventory_clear");
	registercommand("inventory_state");
};

void() Inv_Clear =
{
	inv_ready = inv_roles = inv_own1 = inv_own2 = inv_eq1 = inv_eq2 = inv_wait = 0;
	if (inv_who != "") strunzone(inv_who);
	inv_who = "";
};

// Non-secret presentation only. Server keys never authorize a grant on backend.
vector(float slot) Inv_Public =
{
	local string packed;
	local vector result;
	packed = getplayerkeyvalue(slot, "*kit");
	result = [stof(Gfx_Field(packed, 0, " ")), stof(Gfx_Field(packed, 1, " ")), stof(Gfx_Field(packed, 2, " "))];
	if (result_x < 0 || result_x > 7 || result_x != floor(result_x)) return '0 0 0';
	if ((result_y != 0 && result_y != 1) || result_z < 0 || result_z > 12 || result_z != floor(result_z)) return '0 0 0';
	return result;
};

float() Inv_Valid =
{
	return inv_ready && inv_who != "" && !strcmp(inv_who, getplayerkeyvalue(player_localnum, "*ahash"));
};

float(float count) Inv_ConsoleCommand =
{
	local string command, who;
	local float revision, roles, own1, own2, colour, eq1, eq2;
	command = argv(0);
	if (!strcmp(command, "inventory_clear")) { Inv_Clear(); return TRUE; }
	if (!strcmp(command, "inventory_state"))
	{
		if (count != 9) return TRUE;
		who = argv(1); revision = stof(argv(2)); roles = stof(argv(3));
		own1 = stof(argv(4)); own2 = stof(argv(5)); colour = stof(argv(6)); eq1 = stof(argv(7)); eq2 = stof(argv(8));
		if (strcmp(who, getplayerkeyvalue(player_localnum, "*ahash")) || strlen(who) != 8) return TRUE;
		if (revision < 0 || revision > 16777215 || revision != floor(revision)) return TRUE;
		if (Inv_Valid() && revision < inv_revision) return TRUE;
		if (roles < 1 || roles > 7 || roles != floor(roles)) return TRUE;
		if ((own1 != 0 && own1 != 1) || (own2 != 0 && own2 != 1)) return TRUE;
		if ((eq1 != 0 && eq1 != 1) || (eq2 != 0 && eq2 != 1) || eq1 > own1 || eq2 > own2) return TRUE;
		if (colour < 0 || colour > 11 || colour != floor(colour)) return TRUE;
		if (inv_who != "") strunzone(inv_who);
		inv_who = strzone(who);
		inv_revision = revision; inv_roles = roles; inv_own1 = own1; inv_own2 = own2;
		inv_colour = colour; inv_eq1 = eq1; inv_eq2 = eq2; inv_ready = TRUE; inv_wait = 0;
		return TRUE;
	}
	if (strcmp(command, "inventory")) return FALSE;
	print(sprintf("Inventory: ready %g revision %.0f owned %g/%g equipped %g/%g hat colour %g\n",
	              Inv_Valid(), inv_revision, inv_own1, inv_own2, inv_eq1, inv_eq2, inv_colour));
	return TRUE;
};

float(float roles, float textsize) Inv_BadgeWidth =
{
	local float w;
	w = 0;
	if (roles & 4) w = w + stringwidth("Developer", TRUE, [textsize, textsize]) + textsize * 1.4;
	if (roles & 2) w = w + stringwidth("Zoner", TRUE, [textsize, textsize]) + textsize * 1.4;
	if (roles & 1) w = w + stringwidth("Tester", TRUE, [textsize, textsize]) + textsize * 1.4;
	return w;
};

float(vector p, float roles, float textsize, float width) Inv_Badges =
{
	local float bit, w, x;
	local string label;
	local vector colour;
	x = p_x;
	for (bit = 4; bit >= 1; bit = bit / 2)
	{
		if (!(roles & bit)) continue;
		label = bit == 4 ? "Developer" : (bit == 2 ? "Zoner" : "Tester");
		colour = bit == 4 ? '0.86 0.55 1' : (bit == 2 ? '1 0.76 0.3' : '0.4 0.83 1');
		w = stringwidth(label, TRUE, [textsize, textsize]) + textsize;
		if (x + w > p_x + width) break;
		sui_roundbox([x, p_y], [w, textsize * 1.7], textsize * 0.5, colour * 0.19, 1);
		sui_text([x + textsize * 0.5, p_y + textsize * 0.3], [textsize, textsize], label, colour, 1, 0);
		x = x + w + textsize * 0.4;
	}
	return x - p_x;
};

// P1221: an item cell's ON / OWNED tag, a pill in its bottom-left corner (m_stats.qc draws the same).
void(vector at, float cell, float bsz, float on) Inv_Badge =
{
	local string s;
	local float bh;
	s = on ? "ON" : "OWNED";
	bh = ceil(bsz * 1.5);
	at = at + [3, cell - bh - 3];
	sui_roundbox(at, [stringwidth(s, TRUE, [bsz, bsz]) + bsz, bh], bh * 0.5, on ? SUI_THEME_GOOD_BG : SUI_THEME_CHIP, 0.92);
	sui_text(at + [bsz * 0.5, (bh - bsz) * 0.5 + bsz * FONT_CAPDROP], [bsz, bsz], s, on ? SUI_THEME_GOOD : SUI_THEME_DIM, 1, 0);
};

void(vector p, float width, float textsize, float editable, vector publickit, vector publicitems, float publicknown) Inv_Panel =
{
	local float cell, gap, i, j, x, owned, on, item, ready;
	local vector at, colour;
	local string id, label, note;
	gap = max(3, floor(textsize * 0.35));
	cell = floor((width - gap * 5) / 4);
	sui_style_panel(p, [width, cell * 4 + gap * 5 + textsize * 6], textsize * 0.75, 0.98);
	sui_text(p + [gap, gap], [textsize, textsize], "INVENTORY", SUI_THEME_TEXT, 1, 0);
	ready = Inv_Valid();
	for (i = 0; i < 16; i = i + 1)
	{
		at = p + [gap + (i % 4) * (cell + gap), textsize * 2 + gap + floor(i / 4) * (cell + gap)];
		item = i + 1;
		owned = editable ? (ready && (i == 0 ? inv_own1 : (i == 1 ? inv_own2 : 0))) : (publicknown ? (i == 0 ? publicitems_x : (i == 1 ? publicitems_y : 0)) : (i == 0 ? publickit_y : (i == 1 ? publickit_z : 0)));
		on = editable ? (i == 0 ? inv_eq1 : inv_eq2) : (i == 0 ? publickit_y : (i == 1 ? publickit_z : 0));
		id = sprintf("inv_slot%g", i);
		if (owned) sui_action_element(at, [cell, cell], id, sui_noop);
		sui_roundbox(at, [cell, cell], max(3, textsize * 0.4), (owned && on) ? SUI_THEME_SELECTED : SUI_THEME_WELL, 1);
		if (!owned) continue;
		colour = i == 0 ? '0.4 0.83 1' : Inv_Colour(editable ? inv_colour : (publicknown ? publicitems_z : publickit_z - 1));
		if (i == 0)
		{
			sui_roundbox(at + [cell * 0.28, cell * 0.18], [cell * 0.44, cell * 0.55], cell * 0.18, colour, 0.85);
			sui_roundbox(at + [cell * 0.34, cell * 0.24], [cell * 0.32, cell * 0.43], cell * 0.12, SUI_THEME_WELL, 1);
		}
		else
		{
			sui_roundbox(at + [cell * 0.18, cell * 0.46], [cell * 0.64, cell * 0.28], 0, colour * 0.85, 1);
			for (j = 0; j < 3; j = j + 1)
			{
				x = 0.28 + j * 0.22;
				R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
				R_PolygonVertex(at + [cell * (x - 0.1), cell * 0.5], '0 0 0', colour * 0.85, 1);
				R_PolygonVertex(at + [cell * x, cell * 0.18], '0 0 0', colour, 1);
				R_PolygonVertex(at + [cell * (x + 0.1), cell * 0.5], '0 0 0', colour * 0.85, 1);
				R_EndPolygon();
			}
		}
		Inv_Badge(at, cell, Font_Px(textsize * 0.8), on);
		label = i == 0 ? "Ice aura" : "Paper party crown";
		sui_tooltip_for(id, strcat(label, editable ? (on ? ": click to unequip" : ": click to equip") : (on ? ": equipped (read-only)" : ": owned (read-only)")), 2);
		if (editable && owned && sui_is_released(id) && cltime >= inv_wait)
		{
			localcmd(sprintf("cmd inventory_equip %g %g %.0f\n", item, !on, inv_revision));
			inv_wait = cltime + 1;
		}
	}
	note = editable ? (ready ? "Click an item to equip / remove" :
	       (getplayerkeyvalue(player_localnum, "*ahash") != "" ? "Waiting for lobby inventory service" : "Link Steam on a lobby to load items")) : (publicknown ? "Their owned items (read-only)" : "Inventory unavailable; equipped items only");
	sui_text(p + [gap, cell * 4 + gap * 5 + textsize * 2.1], [textsize, textsize],
	         Chat_Fit(note, width - gap * 2, textsize), SUI_THEME_MUTED, 1, 0);
};

void(entity body, float outline, float hat, float duck) Inv_Draw =
{
	local vector base, tip, a, b, colour;
	local float i, t, u;
	if (outline)
	{
		if (!inv_shader)
			inv_shader = shaderforname("ftesurf/ice_aura", "{\n cull back\n sort additive\n glslprogram\n{\n"
				"!!ver 110\n!!permu FRAMEBLEND\n!!permu SKELETAL\n"
				"#include \"sys/defs.h\"\n"
				"#ifdef VERTEX_SHADER\n#include \"sys/skeletal.h\"\n"
				"void main() {\n vec3 w,n,s,t;\n skeletaltransform_wnst(w,n,s,t);\n"
				" w+=normalize(n)*e_colourident.r;\n"
				" gl_Position=m_modelviewprojection*vec4(w,1.0);\n}\n#endif\n"
				"#ifdef FRAGMENT_SHADER\nvoid main() {\n"
				" gl_FragColor=vec4(0.3,0.75,1.0,e_colourident.a);\n}\n#endif\n"
				"}\n {\n map $whiteimage\n blendfunc GL_SRC_ALPHA GL_ONE\n }\n}\n");
		if (!inv_shell) { inv_shell = spawn(); inv_shell.effects = EF_NOSHADOW; }
		setmodel(inv_shell, body.model);
		setorigin(inv_shell, body.origin);
		inv_shell.angles = body.angles;
		inv_shell.frame = body.frame;
		inv_shell.frame2 = body.frame2;
		inv_shell.lerpfrac = body.lerpfrac;
		inv_shell.forceshader = inv_shader;
		inv_shell.scale = 1;
		// Integrated shell weights approximate a squared fade, not bright rings.
		// Radius travels in colour.r; the program emits a fixed ice-blue colour.
		for (i = 0; i < 16; i = i + 1)
		{
			t = i / 16;
			u = (i + 1) / 16;
			inv_shell.colormod = [u * 8, 1, 1];
			inv_shell.alpha = 0.65 * ((1 - t) * (1 - t) - (1 - u) * (1 - u));
			addentity(inv_shell);
		}
	}
	if (hat < 1 || hat > 12) return;
	base = body.origin + [0, 0, duck ? 45 : 62];
	colour = Inv_Colour(hat - 1);
	for (i = 0; i < 16; i = i + 1)
	{
		t = (i / 16) * 6.2831853 + body.angles_y * (3.14159265 / 180);
		u = ((i + 1) / 16) * 6.2831853 + body.angles_y * (3.14159265 / 180);
		a = base + [cos(t) * 11, sin(t) * 11, 0];
		b = base + [cos(u) * 11, sin(u) * 11, 0];
		R_BeginPolygon("", DRAWFLAG_TWOSIDED);
		R_PolygonVertex(a, '0 0 0', colour * (0.8 + 0.2 * cos(t)), 1);
		R_PolygonVertex(b, '0 0 0', colour * (0.8 + 0.2 * cos(u)), 1);
		R_PolygonVertex(b + '0 0 6', '0 0 0', colour * (0.8 + 0.2 * cos(u)), 1);
		R_PolygonVertex(a + '0 0 6', '0 0 0', colour * (0.8 + 0.2 * cos(t)), 1);
		R_EndPolygon();
		if (i % 2) continue;
		// Eight paper points around an open cylindrical band, not one cone tip.
		a = a + '0 0 6';
		b = base + [cos(t + 0.78539816) * 11, sin(t + 0.78539816) * 11, 6];
		tip = base + [cos(u) * 11, sin(u) * 11, 14];
		R_BeginPolygon("", DRAWFLAG_TWOSIDED);
		R_PolygonVertex(a, '0 0 0', colour * (0.8 + 0.2 * cos(t)), 1);
		R_PolygonVertex(b, '0 0 0', colour * (0.8 + 0.2 * cos(t + 0.78539816)), 1);
		R_PolygonVertex(tip, '0 0 0', colour, 1);
		R_EndPolygon();
	}
};
