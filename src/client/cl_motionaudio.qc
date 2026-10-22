/* Optional local instrument: altitude sine, A kick, D snare. No input/body writes. */
#define MA_RATE 16000i
#define MA_BLOCK 256i

float(int hz, int channels, int format, int *data, int frames) MA_Queue = #0:queueaudio;
float() MA_Queued = #0:getqueuedaudiotime;

int *ma_pcm;
int ma_noise;
float ma_supported, ma_active, ma_valid, ma_toneprev, ma_lastvol;
float ma_aheld, ma_dheld, ma_kick, ma_snare, ma_kphase, ma_phase, ma_tonelevel;
float ma_anchor, ma_height, ma_pitch, ma_target, ma_peak, ma_qmax;
float ma_blocks, ma_hits_a, ma_hits_d, ma_errors;
vector ma_pos;

void() MA_Reset =
{
	ma_active = ma_valid = ma_toneprev = FALSE;
	ma_aheld = ma_dheld = ma_kick = ma_snare = ma_tonelevel = 0;
	ma_phase = ma_kphase = 0;
	ma_noise = 12345i;
};

void() MA_Register =
{
	registercvar("cl_surf_tone", "0", CVAR_ARCHIVE);
	registercvar("cl_surf_drums", "0", CVAR_ARCHIVE);
	registercvar("cl_surf_audio_volume", "0.15", CVAR_ARCHIVE);
	registercvar("cl_surf_tone_base", "220", CVAR_ARCHIVE);
	registercvar("cl_surf_tone_octave", "1024", CVAR_ARCHIVE);
	registercommand("motionaudio_info");
	ma_supported = FALSE;
	if (checkbuiltin(MA_Queue))
	if (checkbuiltin(MA_Queued)) ma_supported = TRUE;
	MA_Reset();
};

int(float tone, float volume) MA_Sample =
{
	local float value, noise;

	ma_pitch = ma_pitch + (ma_target - ma_pitch) * 0.002;
	ma_phase = ma_phase + ma_pitch / 16000;
	ma_phase = ma_phase - floor(ma_phase);
	ma_tonelevel = ma_tonelevel + (tone - ma_tonelevel) * 0.004;
	value = sin(ma_phase * 6.28318530718) * 0.18 * ma_tonelevel;
	if (ma_kick > 0.0005)
	{
		ma_kphase = ma_kphase + (70 + 100 * ma_kick) / 16000;
		ma_kphase = ma_kphase - floor(ma_kphase);
		value = value + sin(ma_kphase * 6.28318530718) * 0.65 * ma_kick * ma_kick;
		ma_kick = ma_kick * 0.9975;
	}
	else ma_kick = 0;
	if (ma_snare > 0.0005)
	{
		// Full-period 16-bit LCG; its product stays below signed-int overflow.
		// Do not consume the game's global random() stream for cosmetic noise.
		ma_noise = (ma_noise * 25173i + 13849i) & 65535i;
		noise = (float)ma_noise / 32768 - 1;
		value = value + noise * 0.5 * ma_snare;
		ma_snare = ma_snare * 0.998;
	}
	else ma_snare = 0;
	value = bound(-0.9, value * volume, 0.9);
	ma_peak = max(ma_peak, fabs(value));
	return (int)(value * 32767);
};

void(float tone, float volume, float fade) MA_Fill =
{
	local int i, a, b;
	local float gain, result, queued;

	for (i = 0i; i < MA_BLOCK; i = i + 2i)
	{
		gain = volume;
		if (fade) gain = volume * (1 - (float)i / 255);
		a = MA_Sample(tone, gain);
		gain = volume;
		if (fade) gain = volume * (1 - (float)(i + 1i) / 255);
		b = MA_Sample(tone, gain);
		// Shipped Windows/ARM targets are little-endian: two S16 samples/cell.
		ma_pcm[i >> 1i] = (a & 65535i) | ((b & 65535i) << 16i);
	}
	result = MA_Queue(MA_RATE, 1i, -16i, ma_pcm, MA_BLOCK);
	if (result <= 0)
	{
		ma_errors = ma_errors + 1;
		ma_supported = ma_active = FALSE;
		print("^3motion audio:^7 native signed16 queue unavailable; disabled\n");
		return;
	}
	ma_blocks = ma_blocks + 1;
	queued = MA_Queued();
	ma_qmax = max(ma_qmax, queued);
};

void() MA_Stop =
{
	if (ma_active)
	if (ma_supported)
	if (ma_pcm) MA_Fill(ma_toneprev, ma_lastvol, TRUE);
	MA_Reset();
};

void() MA_Shutdown =
{
	if (ma_pcm) memfree(ma_pcm);
	ma_pcm = 0;
	MA_Reset();
};

void(float evtype, float key) MA_Release =
{
	if (evtype != IE_KEYUP) return;
	if (key == 97) ma_aheld = FALSE;
	if (key == 100) ma_dheld = FALSE;
};

// Called only AFTER the existing UI/input consumers declined this event.
void(float evtype, float key) MA_Key =
{
	if (evtype != IE_KEYDOWN || !ma_active || !(cvar("cl_surf_drums") > 0)) return;
	if (key == 97 && !ma_aheld)
	{
		ma_aheld = TRUE;
		ma_kick = 1;
		ma_kphase = 0;
		ma_hits_a = ma_hits_a + 1;
	}
	if (key == 100 && !ma_dheld)
	{
		ma_dheld = TRUE;
		ma_snare = 1;
		ma_hits_d = ma_hits_d + 1;
	}
};

void(float visible) MA_Frame =
{
	local float tone, drums, volume, base, octave, queued, burst;
	local vector pos;

	if (!ma_supported) return;
	tone = (cvar("cl_surf_tone") > 0);
	drums = (cvar("cl_surf_drums") > 0);
	volume = cvar("cl_surf_audio_volume");
	if (!(tone || drums) || !(volume > 0)) { MA_Stop(); return; }
	if (!visible || chat_typing || UI_CursorHeld() || !LT_StatsAreMine() ||
	    rec_gh_on || rec_wt_on || getstatf(STAT_FS_SPEC) || rw_on ||
	    getstatf(STAT_FS_MOVETYPE) != MOVETYPE_WALK)
	{
		MA_Stop();
		return;
	}
	pos = pmove_org;                         // native body, never camera bob
	if (pos_z != pos_z || fabs(pos_z) > 1048576) { MA_Stop(); return; }
	volume = min(volume, 1);
	base = cvar("cl_surf_tone_base");
	if (!(base >= 55 && base <= 1000)) base = 220;
	octave = cvar("cl_surf_tone_octave");
	if (!(octave >= 128 && octave <= 8192)) octave = 1024;
	if (!ma_valid || vlen(pos - ma_pos) > 256 || (tone && !ma_toneprev))
	{
		ma_anchor = pos_z;
		ma_pitch = base;
		ma_valid = TRUE;
	}
	ma_pos = pos;
	ma_height = pos_z;
	ma_target = bound(55, base * pow(2, bound(-4, (pos_z - ma_anchor) / octave, 4)), 2000);
	ma_toneprev = tone;
	ma_lastvol = volume;
	if (!ma_pcm) ma_pcm = memalloc(MA_BLOCK * 2i);
	if (!ma_pcm) { MA_Reset(); return; }
	ma_active = TRUE;
	queued = max(0, MA_Queued());
	// Only a small lookahead; never synthesize an unbounded catch-up after a hitch.
	for (burst = 0; burst < 3; burst = burst + 1)
	{
		if (queued >= 0.04) break;
		MA_Fill(tone, volume, FALSE);
		if (!ma_supported) break;
		queued = queued + 0.016;
	}
};

float() MA_Command =
{
	local float queued;

	if (strcmp(argv(0), "motionaudio_info")) return FALSE;
	if (argv(1) == "recenter") ma_valid = FALSE;
	queued = 0;
	if (ma_supported) queued = MA_Queued();
	print(sprintf("motionaudio: supported %g active %g blocks %g hits A %g D %g errors %g\n",
		ma_supported, ma_active, ma_blocks, ma_hits_a, ma_hits_d, ma_errors));
	print(sprintf("motionaudio: body %.3f anchor %.3f target %.3f pitch %.3f peak %.5f queued %.5f maxqueue %.5f\n",
		ma_height, ma_anchor, ma_target, ma_pitch, ma_peak, queued, ma_qmax));
	print("motionaudio: cl_surf_tone 1 / cl_surf_drums 1; cl_surf_audio_volume 0.15; recenter: motionaudio_info recenter\n");
	return TRUE;
};
