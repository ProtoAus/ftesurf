// P1178: mapmeta column 12 (tools/mapmeta.py author_token) as display text, for the
// Maps list (menu) and the HUD's Map info (CSQC). Letters and digits stand, '_' is a
// space, '.hh' is one byte of the UTF-8; "" for unknown ("-") or a malformed token.
// Bytes come back raw (utf8_enable 0), the same bytes json_get_string gives a name.

float(float c) MapAuthor_Hex =
{
	if (c >= 48 && c <= 57) return c - 48;
	if (c >= 97 && c <= 102) return c - 87;
	if (c >= 65 && c <= 70) return c - 55;
	return -1;
};

string(string tok) MapAuthor_Text =
{
	local float i, n, c, hi, lo;
	local string out;
	n = strlen(tok);
	if (n < 1 || n > 64 || tok == "-")
		return "";
	out = "";
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(tok, i);
		if (c == 95)
		{
			out = strcat(out, " ");
			continue;
		}
		if (c != 46)
		{
			if (c < 33 || c > 126 || c == 94)
				return "";
			out = strcat(out, chr2str(c));
			continue;
		}
		if (i + 2 >= n)
			return "";
		hi = MapAuthor_Hex(str2chr(tok, i + 1));
		lo = MapAuthor_Hex(str2chr(tok, i + 2));
		if (hi < 0 || lo < 0)
			return "";
		c = hi * 16 + lo;
		if (c >= 32 && c != 94 && c != 127)     // no control bytes, no '^' colour codes
			out = strcat(out, chr2str(c));
		i = i + 2;
	}
	return out;
};
