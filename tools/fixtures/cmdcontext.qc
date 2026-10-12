// Test-only SSQC. Append to a copied sv_progs.src in an owned build.
// Insert cmdcontext_begin.qc BEFORE sv_player.qc, preserving fixed system defs.
#undef PlayerPreThink
#undef StartFrame
float input_cmd_kind;
float input_cmd_sequence_lo;
float input_cmd_sequence_hi;
float input_cmd_msec;
float input_cmd_piece_msec;
float input_cmd_offset_msec;
float ccf_precount;
float ccf_framecount;

void() PlayerPreThink =
{
	if (cvar("test_cmdcontext"))
	{
		if (ccf_precount < 600)
			bprint(2, sprintf("CMDCONTEXT PRE kind=%g lo=%g hi=%g total=%g piece=%g off=%g\n",
				input_cmd_kind, input_cmd_sequence_lo, input_cmd_sequence_hi,
				input_cmd_msec, input_cmd_piece_msec, input_cmd_offset_msec));
		ccf_precount += 1;
	}
	P675_OriginalPreThink();
};

void() StartFrame =
{
	P675_OriginalStartFrame();
	if (cvar("test_cmdcontext"))
	{
		if ((input_cmd_kind != 0) || (input_cmd_sequence_lo != 0) || (input_cmd_sequence_hi != 0)
			|| (input_cmd_msec != 0) || (input_cmd_piece_msec != 0) || (input_cmd_offset_msec != 0))
			bprint(2, "CMDCONTEXT STALE\n");
		if ((ccf_precount > 10) && (ccf_framecount < 3))
		{
			bprint(2, "CMDCONTEXT FRAME CLEARED original-hooks-acted\n");
			ccf_framecount += 1;
		}
	}
};
