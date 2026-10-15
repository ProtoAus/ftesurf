/* Viewer-local overhead names/Steam pictures from the existing body stream.
   PVS is only coarse admission: a solid-world/brush trace proves visibility.
   Geometry is cheap each frame; visibility rescans at most twice per second
   per body (so occlusion can take up to 0.5s). Never draw a hidden/self/stale
   body, a label outside the view, or a remembered position after a teleport. */
.float tag_next, tag_visible;
.vector tag_lasthead;
.float tag_initialized;
float tag_drawn, tag_traces, tag_lasttraces, tag_has_pvs;
float tag_bodies, tag_fresh, tag_inview, tag_blocked;
vector tag_eye0, tag_forward0;
float tag_alpha, tag_offset, tag_icon, tag_dist, tag_los, tag_camera_seen;
vector tag_previous_eye;

void() PlayerLabels_Register =
{
	registercvar("hud_playerlabels", "1", CVAR_ARCHIVE);
	registercvar("hud_playerlabels_far", "3000", CVAR_ARCHIVE);
	registercommand("playerlabels_status");
	tag_has_pvs = checkextension("FTE_QC_CHECKPVS");
};

void(vector scr) PlayerLabels_Draw =
{
	local entity b;
	local vector eye, head, v, forward, screen;
	local float slot, dist, far, a, icon, tsz, nw, x, visible, camera_jump;
	local string nm, who;

	tag_drawn = 0;
	tag_lasttraces = 0;
	tag_bodies = tag_fresh = tag_inview = tag_blocked = 0;
	if (!cvar("hud_playerlabels")) return;
	if (rec_sb_open || av_open) return; // opaque modals own their picture budget
	eye = getproperty(VF_ORIGIN);
	camera_jump = (tag_camera_seen && vlen(eye - tag_previous_eye) > 512);
	tag_previous_eye = eye;
	tag_camera_seen = TRUE;
	makevectors(getproperty(VF_ANGLES));
	forward = v_forward;
	tag_eye0 = eye;
	tag_forward0 = forward;
	far = bound(0, cvar("hud_playerlabels_far"), 6000);
	Font_Set(ui_font_ui);
	tsz = max(8, Font_Px(6 * max(1, ui_cv_scale)));
	icon = tsz * 1.6;
	for (b = pb_list; b; b = b.pb_nextbody)
	{
		tag_bodies = tag_bodies + 1;
		slot = b.pb_slot - 1;
		if (!b.pb_n || slot < 0 || slot == player_localnum || b.pb_slot == spc_hideslot) continue;
		if (cltime - b.pb_rxt > 1 || getplayerkeyvalue(slot, "name") == "") continue;
		tag_fresh = tag_fresh + 1;
		head = b.pb_rorg + [0, 0, b.pb_reye + 16];
		// Compare consecutive frames, not total travel since the half-second
		// scan. Otherwise a fast surfer's labels blink most of every bucket.
		if (camera_jump || (b.tag_initialized && vlen(head - b.tag_lasthead) > 512)) b.tag_visible = FALSE;
		b.tag_lasthead = head;
		b.tag_initialized = TRUE;
		v = head - eye;
		dist = vlen(v);
		if (dist < 24 || dist > far || v * forward <= 8) continue;
		screen = project(head);
		// project() depth is renderer/projection-dependent (including reverse-Z).
		// The forward dot above, not the depth sign, proves front/near admission.
		if (screen_x < icon || screen_x > scr_x - icon || screen_y < icon || screen_y > scr_y - icon) continue;
		tag_inview = tag_inview + 1;
		if (cltime >= b.tag_next)
		{
			b.tag_next = cltime + 0.5;
			visible = TRUE;
			if (tag_has_pvs) visible = checkpvs(eye, b);
			if (visible)
			{
				traceline(eye, b.pb_rorg + [0, 0, b.pb_reye], MOVE_NOMONSTERS, world);
				tag_lasttraces = tag_lasttraces + 1;
				tag_los = trace_fraction;
				visible = (trace_fraction == 1 && !trace_startsolid);
			}
			b.tag_visible = visible;
		}
		if (!b.tag_visible) { tag_blocked = tag_blocked + 1; continue; }
		a = bound(0, (1024 - dist) / 768, 1);
		nw = 0;
		nm = "";
		if (a > 0)
		{
			nm = Chat_Fit(getplayerkeyvalue(slot, "name"), tsz * 24, tsz);
			nw = stringwidth(nm, TRUE, [tsz, tsz]);
		}
		x = screen_x - (icon + a * (nw + tsz * 0.5)) * 0.5;
		tag_alpha = a;
		tag_offset = x - screen_x;
		tag_icon = icon;
		tag_dist = dist;
		who = getplayerkeyvalue(slot, "*ahash");
		if (who == "") who = getplayerkeyvalue(slot, "*phash");
		if (!SteamPic_Draw([x, screen_y - icon * 0.5], icon, who, 1))
			sui_roundbox([x, screen_y - icon * 0.5], [icon, icon], icon * 0.25, Av_WornRGB(slot), 1);
		if (a > 0)
		{
			drawstring([x + icon + tsz * 0.5 + 1, screen_y - tsz * 0.5 + 1], nm, [tsz, tsz], '0 0 0', a, 0);
			drawstring([x + icon + tsz * 0.5, screen_y - tsz * 0.5], nm, [tsz, tsz], '1 1 1', a, 0);
		}
		tag_drawn = tag_drawn + 1;
	}
	tag_traces = tag_traces + tag_lasttraces;
	Font_Reset();
};

void(float detail) PlayerLabels_Status =
{
	local entity b;
	local vector v, screen;
	print(sprintf("playerlabels: drawn %g frame traces %g total traces %g\n", tag_drawn, tag_lasttraces, tag_traces));
	print(sprintf("playerlabels: bodies %g fresh %g inview %g blocked %g pvs %g\n",
	              tag_bodies, tag_fresh, tag_inview, tag_blocked, tag_has_pvs));
	print(sprintf("playerlabels: name alpha %.3f picture offset %.3f width %.3f distance %.1f los %.5f\n",
	              tag_alpha, tag_offset, tag_icon, tag_dist, tag_los));
	if (!detail) return;
	print(sprintf("label camera %.1f %.1f %.1f forward %.3f %.3f %.3f\n",
	              tag_eye0_x, tag_eye0_y, tag_eye0_z, tag_forward0_x, tag_forward0_y, tag_forward0_z));
	for (b = pb_list; b; b = b.pb_nextbody)
	{
		v = b.pb_rorg + [0, 0, b.pb_reye + 16];
		screen = project(v);
		v = v - tag_eye0;
		print(sprintf("label slot %g dist %.1f dot %.1f projected %.1f %.1f depth %.5f\n",
		              b.pb_slot - 1, vlen(v), v * tag_forward0, screen_x, screen_y, screen_z));
	}
};
