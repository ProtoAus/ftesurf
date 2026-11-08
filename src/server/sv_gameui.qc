/*
  P1428: trigger_look and game_ui (Source server/triggers.cpp CTriggerLook, game_ui.cpp CGameUI), and the
  small inputs the census found unhandled on classes that exist here: SetHealth / AddHealth /
  RemoveHealth on func_breakable (func_break.cpp UpdateHealth) and Skin on props.
*/

#define SF_TRIGGERLOOK_FIREONCE     128
#define SF_TRIGGERLOOK_USEVELOCITY  256
#define SF_GAMEUI_USE_DEACTIVATES   128
#define SF_GAMEUI_JUMP_DEACTIVATES  256

.float  vbsp_look_tot;          // seconds looked (-1: not looking now), Source's m_flLookTimeTotal
.float  vbsp_look_last, vbsp_look_seen, vbsp_look_tout, vbsp_look_toutdone;
.entity vbsp_look_tgt;

// One player's visit ends when its touches stop (Source's EndTouch): a gap of more than this.
#define LOOK_VISIT_GAP  0.1

void(entity pl, int bit) SV_LookOnce =
{
	if (!(self.spawnflags & SF_TRIGGERLOOK_FIREONCE))
		return;
	// Patch 270's trigger_once rule: in a lobby the trigger is spent for this player, not removed.
	if (bit)
		self.vbsp_once_done = self.vbsp_once_done | bit;
	else
		remove(self);
};

void() trigger_look_touch =
{
	local vector dir, to;
	local int bit;

	if (other.classname != "player" || other.health <= 0)
		return;
	if (SV_Key2(self.StartDisabled, self.startdisabled))
		return;
	if (!SV_TouchFilter(self, other))
		return;
	bit = SV_TouchBit(other);
	if (bit)
	if (self.vbsp_once_done & bit)
		return;
	SV_TriggerIOTouch(self, other);
	if (time - self.vbsp_look_seen > LOOK_VISIT_GAP)
	{
		// StartTouch: the timeout runs from here; a new visit forgets the look time.
		self.vbsp_look_tot = -1;
		self.vbsp_look_toutdone = FALSE;
		self.vbsp_look_tout = (self.Timeout > 0) ? time + self.Timeout : 0;
	}
	self.vbsp_look_seen = time;
	if (self.vbsp_look_toutdone)
		return;
	if (self.vbsp_look_tout && time >= self.vbsp_look_tout)
	{
		self.vbsp_look_toutdone = TRUE;
		SV_FireOutput(self, "OnTimeout", other);
		SV_LookOnce(other, bit);
		return;
	}
	if (!self.vbsp_look_tgt || wasfreed(self.vbsp_look_tgt))
		self.vbsp_look_tgt = SV_FindByName(self.target, world);
	if (!self.vbsp_look_tgt)
		return;
	if (self.spawnflags & SF_TRIGGERLOOK_USEVELOCITY)
		dir = normalize(other.velocity);
	else
	{
		makevectors(other.v_angle);
		dir = v_forward;
	}
	to = normalize(self.vbsp_look_tgt.origin - (other.origin + other.view_ofs));
	if (dir * to <= self.FieldOfView)
	{
		self.vbsp_look_tot = -1;
		return;
	}
	if (self.vbsp_look_tot < 0)
		self.vbsp_look_tot = 0;
	else
		self.vbsp_look_tot = self.vbsp_look_tot + (time - self.vbsp_look_last);
	self.vbsp_look_last = time;
	if (self.vbsp_look_tot < self.LookTime)
		return;
	self.vbsp_look_tot = -1;
	self.vbsp_look_tout = 0;            // Trigger's SetThink(NULL): no timeout after it fired
	SV_FireOutput(self, "OnTrigger", other);
	SV_LookOnce(other, bit);
};

// trigger_multiple's set-up (a look trigger with nothing wired stays inert, as one does), its own touch.
void() trigger_look =
{
	trigger_multiple();
	if (wasfreed(self) || self.touch != trigger_multiple_touch)
		return;
	self.touch = trigger_look_touch;
	self.vbsp_look_tot = -1;
};

/*
  game_ui: while a player holds it, his keys fire outputs -- Pressed / Unpressed per key and the four axes
  as values (-1, 0, 1) when they change. Spawnflag 32 (freeze the player, FL_ATCONTROLS) is NOT done:
  the movement code has no predicted "commands ignored" state, and the run system's pin
  (MOVETYPE_NONE) means a held save or a replay. 24 of the library's 26 set it.
*/
.entity gui_pl;
.float  gui_last;               // keys at the last think (GUI_* bits)
.float  gui_x, gui_y, gui_a, gui_a2;

#define GUI_LEFT    1
#define GUI_RIGHT   2
#define GUI_FWD     4
#define GUI_BACK    8
#define GUI_ATTACK  16
#define GUI_ATTACK2 32

// In a usercmd the move keys are signs of .movement; +attack is button0, +attack2 button3 (see SV_TrigShoot).
float(entity pl) SV_GuiKeys =
{
	local float b;

	b = 0;
	if (pl.movement_y < 0) b = b | GUI_LEFT;
	if (pl.movement_y > 0) b = b | GUI_RIGHT;
	if (pl.movement_x > 0) b = b | GUI_FWD;
	if (pl.movement_x < 0) b = b | GUI_BACK;
	if (pl.button0) b = b | GUI_ATTACK;
	if (pl.button3) b = b | GUI_ATTACK2;
	return b;
};

void(entity g, string out, float v, entity pl) SV_GuiValue =
{
	vbsp_io_value = ftos(v);
	SV_FireOutput(g, out, pl);
};

void(entity g) SV_GuiOff =
{
	local entity pl;

	pl = g.gui_pl;
	if (!pl)
		return;
	g.gui_pl = world;
	g.gui_last = 0;
	g.nextthink = 0;
	SV_FireOutput(g, "PlayerOff", pl);
	SV_GuiValue(g, "XAxis", 0, pl);
	SV_GuiValue(g, "YAxis", 0, pl);
	SV_GuiValue(g, "AttackAxis", 0, pl);
	SV_GuiValue(g, "Attack2Axis", 0, pl);
	g.gui_x = g.gui_y = g.gui_a = g.gui_a2 = 0;
};

void(entity g, float was, float now, float bit, string down, string up, entity pl) SV_GuiEdge =
{
	if (!((was ^ now) & bit))
		return;
	SV_FireOutput(g, (now & bit) ? down : up, pl);
};

// CGameUI::Think, every frame while a player holds it.
void() SV_GuiThink =
{
	local entity pl;
	local float now, was, v;
	local vector to;

	pl = self.gui_pl;
	if (!pl || wasfreed(pl) || pl.classname != "player" || pl.health <= 0)
	{
		SV_GuiOff(self);
		return;
	}
	if (self.FieldOfView > -1)
	{
		makevectors(pl.v_angle);
		to = normalize(self.origin - (pl.origin + (pl.mins + pl.maxs) * 0.5));
		if (v_forward * to < self.FieldOfView)
		{
			SV_GuiOff(self);
			return;
		}
	}
	self.nextthink = time;
	if (((self.spawnflags & SF_GAMEUI_USE_DEACTIVATES) && pl.button5 && !(self.gui_last & 64)) ||
	    ((self.spawnflags & SF_GAMEUI_JUMP_DEACTIVATES) && pl.button2 && !(self.gui_last & 128)))
	{
		SV_GuiOff(self);
		return;
	}
	now = SV_GuiKeys(pl);
	was = self.gui_last & 63;
	SV_GuiEdge(self, was, now, GUI_RIGHT, "PressedMoveRight", "UnpressedMoveRight", pl);
	SV_GuiEdge(self, was, now, GUI_LEFT, "PressedMoveLeft", "UnpressedMoveLeft", pl);
	SV_GuiEdge(self, was, now, GUI_FWD, "PressedForward", "UnpressedForward", pl);
	SV_GuiEdge(self, was, now, GUI_BACK, "PressedBack", "UnpressedBack", pl);
	SV_GuiEdge(self, was, now, GUI_ATTACK, "PressedAttack", "UnpressedAttack", pl);
	SV_GuiEdge(self, was, now, GUI_ATTACK2, "PressedAttack2", "UnpressedAttack2", pl);
	// The axes: right/forward win over left/back, as m_nButtons is tested in that order.
	v = (now & GUI_RIGHT) ? 1 : ((now & GUI_LEFT) ? -1 : 0);
	if (v != self.gui_x) { self.gui_x = v; SV_GuiValue(self, "XAxis", v, pl); }
	v = (now & GUI_FWD) ? 1 : ((now & GUI_BACK) ? -1 : 0);
	if (v != self.gui_y) { self.gui_y = v; SV_GuiValue(self, "YAxis", v, pl); }
	v = (now & GUI_ATTACK) ? 1 : 0;
	if (v != self.gui_a) { self.gui_a = v; SV_GuiValue(self, "AttackAxis", v, pl); }
	v = (now & GUI_ATTACK2) ? 1 : 0;
	if (v != self.gui_a2) { self.gui_a2 = v; SV_GuiValue(self, "Attack2Axis", v, pl); }
	// +use / +jump held at activation must be released first, as Source's m_afButtonPressed is an edge.
	self.gui_last = now | (pl.button5 ? 64 : 0) | (pl.button2 ? 128 : 0);
};

void() game_ui =
{
	self.solid = SOLID_NOT;
	self.movetype = MOVETYPE_NONE;
	setorigin(self, self.origin);
	self.think = SV_GuiThink;
};

float(entity t, string in, string pm, entity act) SV_GuiInput =
{
	local entity pl;

	if (in == "deactivate")
	{
		SV_GuiOff(t);
		return TRUE;
	}
	if (in != "activate")
		return FALSE;
	pl = act;
	if (pm != "")
		pl = (pm == "!activator") ? act : SV_FindByName(pm, world);
	if (!pl || pl.classname != "player")
		return TRUE;
	if (t.gui_pl && t.gui_pl != pl)
		return TRUE;                    // another player holds it
	t.gui_pl = pl;
	SV_FireOutput(t, "PlayerOn", pl);
	// m_bForceUpdate: the keys held now are the baseline, not presses.
	t.gui_last = SV_GuiKeys(pl) | (pl.button5 ? 64 : 0) | (pl.button2 ? 128 : 0);
	t.nextthink = time;
	return TRUE;
};

// The census's small ones (tools/census/entgap-20261108.md): health on breakables, skins on props.
float(entity t, string in, string pm, entity act) SV_SmallInput =
{
	if (t.classname == "func_breakable")
	if (in == "sethealth" || in == "addhealth" || in == "removehealth")
	{
		if (in == "sethealth")
			t.health = stof(pm);
		else if (in == "addhealth")
			t.health = t.health + fabs(stof(pm));
		else
			t.health = t.health - fabs(stof(pm));
		if (t.health <= 0)
			SV_BreakableBreak(t, act);  // UpdateHealth: at or below zero it breaks
		return TRUE;
	}
	if (in == "skin" && substring(t.classname, 0, 5) == "prop_")
	{
		t.skin = stof(pm);
		return TRUE;                    // csprogs riders resend on any input (SV_ApplyInput's head)
	}
	return FALSE;
};
