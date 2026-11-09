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
	// Patch 270's trigger_once rule: spent for this player, not removed -- and out of the touch masks, or the
	// next sweep fires an OnEndTouch at a player still inside (trigger_multiple_touch's once arm).
	if (bit)
	{
		self.vbsp_once_done  = self.vbsp_once_done | bit;
		self.vbsp_touch_in   = self.vbsp_touch_in   & ~bit;
		self.vbsp_touch_seen = self.vbsp_touch_seen & ~bit;
		self.vbsp_touch_out  = self.vbsp_touch_out  & ~bit;
	}
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
	if (cvar("developer"))
		dprint(sprintf("trigger_look %s: OnTrigger after %g s looking\n", self.model, self.LookTime));
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

// The subject says what it fired (developer 1; tools/p1428-gameplay.md grades on it).
void(entity g, string out, entity pl) SV_GuiFire =
{
	if (cvar("developer"))
		dprint(sprintf("game_ui %s: %s %s\n", g.targetname, out, vbsp_io_value));
	SV_FireOutput(g, out, pl);
};

void(entity g, string out, float v, entity pl) SV_GuiValue =
{
	vbsp_io_value = ftos(v);
	SV_GuiFire(g, out, pl);
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
	SV_GuiFire(g, "PlayerOff", pl);
	SV_GuiValue(g, "XAxis", 0, pl);
	SV_GuiValue(g, "YAxis", 0, pl);
	SV_GuiValue(g, "AttackAxis", 0, pl);
	SV_GuiValue(g, "Attack2Axis", 0, pl);
	g.gui_x = g.gui_y = g.gui_a = g.gui_a2 = 0;
};

// TRUE when the fire let go of the game_ui (the think stops there).
float(entity g, float was, float now, float bit, string down, string up, entity pl) SV_GuiEdge =
{
	if (!((was ^ now) & bit))
		return FALSE;
	SV_GuiFire(g, (now & bit) ? down : up, pl);
	return g.gui_pl != pl;
};

// CGameUI::Think, every frame while a player holds it.
void() SV_GuiThink =
{
	local entity pl;
	local float now, was, v;
	local vector to;

	pl = self.gui_pl;
	if (!pl || wasfreed(pl) || pl.classname != "player" || pl.health <= 0 || clienttype(pl) == CLIENTTYPE_DISCONNECTED)
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
	// The new keys first: an output fired below may let go of this game_ui (de_nam's napalm_ui wires
	// PressedAttack to its own Deactivate), and then nothing after it fires.
	self.gui_last = now | (pl.button5 ? 64 : 0) | (pl.button2 ? 128 : 0);
	if (SV_GuiEdge(self, was, now, GUI_RIGHT, "PressedMoveRight", "UnpressedMoveRight", pl)) return;
	if (SV_GuiEdge(self, was, now, GUI_LEFT, "PressedMoveLeft", "UnpressedMoveLeft", pl)) return;
	if (SV_GuiEdge(self, was, now, GUI_FWD, "PressedForward", "UnpressedForward", pl)) return;
	if (SV_GuiEdge(self, was, now, GUI_BACK, "PressedBack", "UnpressedBack", pl)) return;
	if (SV_GuiEdge(self, was, now, GUI_ATTACK, "PressedAttack", "UnpressedAttack", pl)) return;
	if (SV_GuiEdge(self, was, now, GUI_ATTACK2, "PressedAttack2", "UnpressedAttack2", pl)) return;
	// The axes: right/forward win over left/back, as m_nButtons is tested in that order.
	v = (now & GUI_RIGHT) ? 1 : ((now & GUI_LEFT) ? -1 : 0);
	if (v != self.gui_x) { self.gui_x = v; SV_GuiValue(self, "XAxis", v, pl); if (self.gui_pl != pl) return; }
	v = (now & GUI_FWD) ? 1 : ((now & GUI_BACK) ? -1 : 0);
	if (v != self.gui_y) { self.gui_y = v; SV_GuiValue(self, "YAxis", v, pl); if (self.gui_pl != pl) return; }
	v = (now & GUI_ATTACK) ? 1 : 0;
	if (v != self.gui_a) { self.gui_a = v; SV_GuiValue(self, "AttackAxis", v, pl); if (self.gui_pl != pl) return; }
	v = (now & GUI_ATTACK2) ? 1 : 0;
	if (v != self.gui_a2) { self.gui_a2 = v; SV_GuiValue(self, "Attack2Axis", v, pl); }
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
	SV_GuiFire(t, "PlayerOn", pl);
	// m_bForceUpdate: the keys held now are the baseline, not presses.
	t.gui_last = SV_GuiKeys(pl) | (pl.button5 ? 64 : 0) | (pl.button2 ? 128 : 0);
	t.nextthink = time;
	return TRUE;
};

// The census's small ones (tools/census/entgap-20261108.md): health on breakables, skins on props.
float(entity t, string in, string pm, entity act) SV_SmallInput =
{
	local float v;

	if (t.classname == "func_breakable")
	if (in == "sethealth" || in == "addhealth" || in == "removehealth")
	{
		v = stof(pm);
		v = (v < 0) ? ceil(v) : floor(v);   // FIELD_INTEGER
		if (in == "addhealth")
			v = t.health + v;
		else if (in == "removehealth")
			v = t.health - v;
		// func_break.cpp UpdateHealth: nothing unless it changes; OnHealthChanged; at or below zero it breaks.
		if (v == t.health)
			return TRUE;
		t.health = v;
		SV_FireOutput(t, "OnHealthChanged", act);
		if (!wasfreed(t) && t.health <= 0)
			SV_BreakableBreak(t, act);
		return TRUE;
	}
	if (in == "skin" && substring(t.classname, 0, 5) == "prop_")
	{
		t.skin = stof(pm);
		return TRUE;                    // csprogs riders resend on any input (SV_ApplyInput's head)
	}
	// P1440: the packed body takes the value (with one bodypart, base 1, that is its choice -- every library
	// prop that receives it). The wire carries 0-255 (sv_ents.c), csprogs riders and movers too (SV_TrkPropSend,
	// SV_SpSend).
	if (in == "setbodygroup" && substring(t.classname, 0, 5) == "prop_")
	{
		t.body = max(0, floor(stof(pm)));
		return TRUE;
	}
	return FALSE;
};
