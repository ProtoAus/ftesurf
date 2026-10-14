/*
  Original KSF CSS/66t v2/v3 files -> an in-memory imported .rec buffer.
  No generated file, Python install or native evidence fields. The caller MUST
  bind map/course/style: the binary has no trustworthy map or player identity.
  Layout and clock match tools/ksfconvert.py; limits bound a synchronous VM load.
*/
#define KSF_BYTES 16777216
#define KSF_FRAMES 40000

float(float x) KSF_Finite =
{
	// Also rejects NaN (both ordered comparisons fail).
	return (x > -10000000 && x < 10000000);
};

int(int *name) KSF_TargetClass =
{
	local int a, b, c, n;
	// Exact seven-byte 5939xxx namespace, NUL-terminated. Unknown is zero;
	// recognized non-bonus is 999, starts positive N, finishes negative N.
	if (name[0] != 0x39333935i || (name[1] & 0xff000000i)) return 0i;
	a = (name[1] & 255i) - 48i;
	b = ((name[1] >> 8i) & 255i) - 48i;
	c = ((name[1] >> 16i) & 255i) - 48i;
	if (a < 0i || a > 9i || b < 0i || b > 9i || c < 0i || c > 9i) return 0i;
	n = a * 100i + b * 10i + c;
	if (n < 101i || n > 199i) return 999i;
	if (n & 1i) return (n - 99i) / 2i;
	return -(n - 99i) / 2i;
};

float(string path, float buf, string boundmap, float bonus, string style) KSF_BufLoad =
{
	local float sh, fh, size, ok, dt, flags, keys, fw, side, up;
	local int *h;
	local int *marks;
	local int *frame;
	local float *f;
	local int version, cells, ext, count, offset, frames, i, j;
	local int tick, touch, zone, startzone, start, stop, si, ni, exits, ends, last;
	local int buttons, classified;
	local string row, moves;

	if (boundmap == "" || strcmp(boundmap, serverkey("map")))
	{
		print("replay: KSF explicit map binding differs from the loaded map -- refused\n");
		return FALSE;
	}
	if (bonus < 0 || bonus > 69 || bonus != floor(bonus)) return FALSE;
	if (strcmp(style, "FW") && strcmp(style, "SW") && strcmp(style, "HSW") && strcmp(style, "BW"))
		return FALSE;
	// fsize/fread load the whole file in this engine. Bound it BEFORE opening.
	sh = search_begin(path, TRUE, TRUE);
	if (sh < 0) return FALSE;
	size = 0;
	if (search_getsize(sh) == 1) size = search_getfilesize(sh, 0);
	search_end(sh);
	if (size < 16 || size > KSF_BYTES) return FALSE;
	fh = fopen(path, FILE_READ);
	if (fh < 0) return FALSE;
	h = memalloc(24);
	marks = __NULL__;
	frame = __NULL__;
	ok = FALSE;
	while (1)
	{
		if (fsize(fh) != size) break;
		if (fread(fh, h, 16i) != 16i) break;
		version = h[0];
		count = h[3];
		cells = 10i;
		ext = 0i;
		offset = 16i;
		if (version != 2i && version != 3i) break;
		if (count < 0i || count > 4096i) break;
		if (version == 3i)
		{
			if (fread(fh, h + 4i, 8i) != 8i) break;
			cells = h[4];
			ext = h[5];
			offset = 24i;
		}
		if (cells < 10i || cells > 1024i || ext < 0i || ext > 4096i) break;
		offset = offset + ext * 4i + count * 524i;
		frames = ((int)size - offset) / (cells * 4i);
		if (frames < 2i || frames > KSF_FRAMES || offset > (int)size) break;
		if (offset + frames * cells * 4i != (int)size) break;
		marks = memalloc(count * 524i + 4i);
		fseek(fh, offset - count * 524i);
		if (fread(fh, marks, count * 524i) != count * 524i) break;
		startzone = bonus == 0 ? 1i : 30i + (int)bonus;
		start = stop = si = ni = -1i;
		exits = ends = 0i;
		last = -1i;
		for (i = 0i; i < count; i = i + 1i)
		{
			j = i * 131i;
			tick = marks[j]; touch = marks[j + 1i]; zone = marks[j + 2i];
			if (tick < last || tick < 0i || tick >= frames || touch < 1i || touch > 3i)
				break;
			last = tick;
			if (zone == startzone && touch == 3i)
			{
				classified = KSF_TargetClass(marks + j + 3i);
				if (bonus > 0 && classified != 0i && classified != (int)bonus) continue;
				exits = exits + 1i; start = tick; si = i;
			}
		}
		if (i != count || exits != 1i) break;
		for (i = 0i; i < count; i = i + 1i)
		{
			j = i * 131i;
			tick = marks[j]; touch = marks[j + 1i]; zone = marks[j + 2i];
			if (tick <= start && zone == startzone && touch == 2i)
				ni = i;
			if (tick <= start || touch != 2i) continue;
			if (bonus == 0 && zone == 99i)
			{
				ends = ends + 1i; stop = tick;
			}
			if (bonus > 0 && zone == startzone)
			{
				classified = KSF_TargetClass(marks + j + 3i);
				if (classified == 0i || classified == -(int)bonus)
				{
					ends = ends + 1i; stop = tick;
				}
			}
		}
		if (ni < 0i || ends != 1i || stop <= start) break;
		frame = memalloc(cells * 4i);
		f = (float *)frame;
		moves = "buttons 1";
		if (version == 3i && cells == 18i) moves = "recorded";
		bufstr_add(buf, "FTESURF-REC 5", TRUE);
		bufstr_add(buf, "foreign ksf original-binary css66", TRUE);
		bufstr_add(buf, sprintf("map %s", boundmap), TRUE);
		bufstr_add(buf, "mapbuild unknown", TRUE);
		bufstr_add(buf, "clock sampled", TRUE);
		bufstr_add(buf, "tickrate 0.015", TRUE);
		bufstr_add(buf, "owner KSF", TRUE);
		bufstr_add(buf, sprintf("track %g", bonus), TRUE);
		bufstr_add(buf, "startseg 0", TRUE);
		bufstr_add(buf, "leg 0", TRUE);
		bufstr_add(buf, "flags 0", TRUE);
		bufstr_add(buf, sprintf("ksfdemo %i %i %i %s", version, start, stop, style), TRUE);
		bufstr_add(buf, sprintf("ksfground %g", (float)(version == 3i && cells >= 11i)), TRUE);
		bufstr_add(buf, sprintf("ksfmoves %g", (float)(version == 3i && cells == 18i)), TRUE);
		if (version == 3i && cells >= 11i) bufstr_add(buf, "demodata 1", TRUE);
		bufstr_add(buf, sprintf("moves %s", moves), TRUE);
		bufstr_add(buf, "begin", TRUE);
		for (i = 0i; i <= stop; i = i + 1i)
		{
			if (fread(fh, frame, cells * 4i) != cells * 4i) break;
			for (j = 1i; j < 10i; j = j + 1i)
				if (!KSF_Finite(f[j])) break;
			if (j != 10i) break;
			buttons = frame[0];
			flags = keys = 0;
			if (version == 3i && cells >= 11i) if (frame[10] & 1i) flags = 1;
			if (buttons & 2i) { flags = flags | 4; keys = keys | 16; }
			if (buttons & 1i) { flags = flags | 8; keys = keys | 256; }
			if (buttons & 4i) keys = keys | 32;
			if (buttons & 128i) keys = keys | 64;
			if (buttons & 256i) keys = keys | 128;
			fw = side = up = 0;
			if (buttons & 8i) fw = fw + 1;
			if (buttons & 16i) fw = fw - 1;
			if (buttons & 1024i) side = side + 1;
			if (buttons & 512i) side = side - 1;
			if (version == 3i && cells == 18i)
			{
				if (!KSF_Finite(f[13]) || !KSF_Finite(f[14]) || !KSF_Finite(f[17])) break;
				fw = stof(sprintf("%.6f", f[13]));
				side = stof(sprintf("%.6f", f[14]));
				up = stof(sprintf("%.6f", f[17]));
			}
			if (fw > 0) keys = keys | 1;
			if (fw < 0) keys = keys | 2;
			if (side > 0) keys = keys | 8;
			if (side < 0) keys = keys | 4;
			dt = ((float)i - (float)start) * 0.015;
			row = sprintf("%.6f %.6f %.6f %.6f %.6f %.6f %.6f", dt, f[1], f[2], f[3], f[7], f[8], f[9]);
			row = strcat(row, sprintf(" %.6f %.6f %g %g %.6f %.6f %.6f", f[4], f[5], flags, keys, fw, side, up));
			bufstr_add(buf, sprintf("ksfbuttons %i %i", i, buttons), TRUE);
			bufstr_add(buf, strcat(row, " 0 0 0"), TRUE);
		}
		if (i != stop + 1i) break;
		bufstr_add(buf, sprintf("end %i %i %i 0", stop - start, stop + 1i, start), TRUE);
		ok = TRUE;
		break;
	}
	if (frame) memfree(frame);
	if (marks) memfree(marks);
	memfree(h);
	fclose(fh);
	if (!ok) print("replay: unsupported, malformed or ambiguous KSF CSS/66t demo -- refused\n");
	return ok;
};
