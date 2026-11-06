// P1339: per-map replay-baked geometry + content-addressed atlas, on request.
// Same multiply overlay/close lift as P1335; downloading never enables marks/dirt.
// Download caches live in data/gfx/rampwear/, inside the QC write sandbox.
// ASCII transport + existing binary builtins avoids global HTTP-picture limits.
#define RW_BASE "https://play.proto.bar/ftesurf/media/rampwear/"

float() Online_NextReq;
void() RampWear_Load;
string rw_map, rw_shader, rw_texture;
float rw_n, rw_ntri, rw_lift, rw_alloc, rw_imgw, rw_imgh;
vector *rw_cen;
vector *rw_pos;
vector *rw_st;
vector *rw_nrm;
float *rw_rad;
float *rw_first;
float *rw_cnt;
float rw_req, rw_at;
string rw_reqmap, rw_tried;
float rw_getatlas, rw_decoding;
string rw_hash, rw_encodedhash;
int *rw_encoded;
int *rw_decoded;
int rw_encodedlen, rw_decodedlen, rw_offset, rw_bytepos, rw_width, rw_height;
string(string digest, void *data, int length) rw_digest_ptr = #0:digest_ptr;

float(string name) RampWear_MapOK =
{
	local float i, ch;
	if (strlen(name) < 1 || strlen(name) > 64) return FALSE;
	for (i = 0; i < strlen(name); i = i + 1)
	{
		ch = str2chr(name, i);
		if (!((ch >= 97 && ch <= 122) || (ch >= 48 && ch <= 57) || ch == 95 || ch == 45))
			return FALSE;
	}
	return TRUE;
};

float(string text) RampWear_HashOK =
{
	local float i, ch;
	if (strlen(text) != 64) return FALSE;
	for (i = 0; i < 64; i = i + 1)
	{
		ch = str2chr(text, i);
		if (!((ch >= 48 && ch <= 57) || (ch >= 97 && ch <= 102))) return FALSE;
	}
	return TRUE;
};

float() RampWear_Allowed; // consent state is declared later, beside cl_online

float(string path) RampWear_Exists =
{
	local float fh;
	fh = fopen(path, FILE_READ);
	if (fh < 0) return FALSE;
	fclose(fh);
	return TRUE;
};

// Validate bounds/counts BEFORE allocation or replacing a previously valid cache.
float(string path, string mname) RampWear_Valid =
{
	local float fh, k, ns, nt, s, t, left, j, v, bad;
	local string line;
	local vector normal;
	fh = fopen(path, FILE_READ);
	if (fh < 0) return FALSE;
	k = tokenize(fgets(fh));
	bad = (strcmp(argv(0), "rampwear") || strcmp(argv(2), mname));
	if (!((k == 5 && !strcmp(argv(1), "1")) || (k == 9 && !strcmp(argv(1), "2")))) bad = TRUE;
	if (k == 9)
	{
		if (!RampWear_HashOK(argv(5)) || !RampWear_HashOK(argv(6))) bad = TRUE;
		v = stof(argv(7)); if (!(v >= 1 && v <= 4096 && v == floor(v))) bad = TRUE;
		v = stof(argv(8)); if (!(v >= 1 && v <= 4096 && v == floor(v))) bad = TRUE;
	}
	ns = stof(argv(3)); nt = stof(argv(4));
	if (!(ns >= 1 && ns <= 32768 && ns == floor(ns) && nt >= 1 && nt <= 131072 && nt == floor(nt))) bad = TRUE;
	if (bad) { fclose(fh); return FALSE; }
	s = t = left = 0;
	while ((line = fgets(fh)))
	{
		k = tokenize(line);
		if (!strcmp(argv(0), "c"))
		{
			if (k != 6 || left != 0 || s >= ns) bad = TRUE;
			left = stof(argv(5));
			if (!(left >= 1 && left <= nt && left == floor(left))) bad = TRUE;
			for (j = 1; j <= 4; j = j + 1)
				if (!(fabs(stof(argv(j))) <= 10000000)) bad = TRUE;
			if (!(stof(argv(4)) > 0)) bad = TRUE;
			s = s + 1;
		}
		else if (!strcmp(argv(0), "t"))
		{
			if (k != 19 || left <= 0 || t >= nt) bad = TRUE;
			for (j = 0; j < 3; j = j + 1)
			{
				if (!(fabs(stof(argv(1 + j * 5))) <= 10000000 && fabs(stof(argv(2 + j * 5))) <= 10000000 && fabs(stof(argv(3 + j * 5))) <= 10000000)) bad = TRUE;
				v = stof(argv(4 + j * 5)); if (!(v >= 0 && v <= 1)) bad = TRUE;
				v = stof(argv(5 + j * 5)); if (!(v >= 0 && v <= 1)) bad = TRUE;
			}
			normal = [stof(argv(16)), stof(argv(17)), stof(argv(18))];
			if (!(vlen(normal) >= 0.9 && vlen(normal) <= 1.1)) bad = TRUE;
			left = left - 1; t = t + 1;
		}
		else bad = TRUE;
		if (bad) break;
	}
	fclose(fh);
	return (!bad && s == ns && t == nt && left == 0);
};

float(string mname) RampWear_Request =
{
	if (!RampWear_MapOK(mname)) { print("rampwear: invalid map name\n"); return FALSE; }
	if (!RampWear_Allowed()) { print("rampwear: accept the online terms before downloading\n"); return FALSE; }
	if (rw_req || rw_decoding) { print("rampwear: another map request is pending\n"); return FALSE; }
	if (!checkbuiltin(rw_digest_ptr)) { print("rampwear: this engine lacks binary asset hashing\n"); return FALSE; }
	if (!checkbuiltin(fwrite)) { print("rampwear: this engine lacks binary asset caching\n"); return FALSE; }
	if (rw_reqmap != "") strunzone(rw_reqmap);
	if (rw_tried != "") strunzone(rw_tried);
	rw_reqmap = strzone(mname); rw_tried = strzone(mname);
	rw_getatlas = FALSE;
	rw_req = Online_NextReq(); rw_at = gettime(0);
	if (!uri_get(strcat(RW_BASE, mname, ".txt"), rw_req))
	{
		rw_req = 0; print("rampwear: geometry request could not start\n"); return FALSE;
	}
	print(sprintf("rampwear: requesting %s atlas/geometry (marks stay at your setting)\n", mname));
	return TRUE;
};

void() RampWear_DecodeFree =
{
	if (rw_decoding) { memfree(rw_encoded); memfree(rw_decoded); }
	rw_decoding = FALSE;
};

int(int ch) RampWear_B64 =
{
	if (ch >= 65i && ch <= 90i) return ch - 65i;
	if (ch >= 97i && ch <= 122i) return ch - 71i;
	if (ch >= 48i && ch <= 57i) return ch + 4i;
	if (ch == 43i) return 62i;
	if (ch == 47i) return 63i;
	if (ch == 61i) return 0i;
	return -1i;
};

// Chunked CPU work, not str2chr on a multi-megabyte UTF-8 string per byte.
// memcpy's validated string-temp pointer is supported by the existing VM ABI.
void() RampWear_DecodeFrame =
{
	local int stop, word, a, b, c, d, value, i, bytevalue, fh, w, h;
	local string path, digest;
	if (!rw_decoding) return;
	if (!RampWear_Allowed()) { RampWear_DecodeFree(); return; }
	stop = min(rw_encodedlen, rw_offset + 8192i);
	while (rw_offset < stop)
	{
		word = rw_encoded[rw_offset >> 2i];
		a = RampWear_B64(word & 255i); b = RampWear_B64((word >> 8i) & 255i);
		c = RampWear_B64((word >> 16i) & 255i); d = RampWear_B64((word >> 24i) & 255i);
		if (a < 0i || b < 0i || c < 0i || d < 0i) { RampWear_DecodeFree(); print("rampwear: invalid atlas encoding\n"); return; }
		value = (a << 18i) | (b << 12i) | (c << 6i) | d;
		for (i = 0i; i < 3i; i = i + 1i)
		{
			if (rw_bytepos >= rw_decodedlen) break;
			bytevalue = (value >> ((2i - i) * 8i)) & 255i;
			rw_decoded[rw_bytepos >> 2i] |= bytevalue << ((rw_bytepos & 3i) * 8i);
			rw_bytepos = rw_bytepos + 1i;
		}
		rw_offset = rw_offset + 4i;
	}
	if (rw_offset < rw_encodedlen) return;
	if (rw_bytepos != rw_decodedlen) { RampWear_DecodeFree(); print("rampwear: short atlas\n"); return; }
	digest = rw_digest_ptr("SHA256", rw_decoded, rw_decodedlen);
	if (strcmp(digest, rw_hash)) { RampWear_DecodeFree(); print("rampwear: atlas hash mismatch; cache kept\n"); return; }
	w = rw_decoded[4i]; h = rw_decoded[5i];
	w = ((w & 255i) << 24i) | (((w >> 8i) & 255i) << 16i) | (((w >> 16i) & 255i) << 8i) | ((w >> 24i) & 255i);
	h = ((h & 255i) << 24i) | (((h >> 8i) & 255i) << 16i) | (((h >> 16i) & 255i) << 8i) | ((h >> 24i) & 255i);
	if (rw_decoded[0i] != 0x474e5089i || rw_decoded[1i] != 0x0a1a0a0di || w != rw_width || h != rw_height)
	{
		RampWear_DecodeFree(); print("rampwear: invalid atlas PNG/dimensions\n"); return;
	}
	path = sprintf("data/gfx/rampwear/%s.%s.png", rw_reqmap, rw_hash);
	fh = fopen(path, FILE_WRITE);
	if (fh < 0i) { RampWear_DecodeFree(); print("rampwear: cannot cache atlas\n"); return; }
	value = fwrite(fh, rw_decoded, rw_decodedlen); fclose(fh);
	if (value != rw_decodedlen) { RampWear_DecodeFree(); print("rampwear: short atlas cache write\n"); return; }
	RampWear_DecodeFree();
	print(sprintf("rampwear: %s atlas cached and SHA256 verified\n", rw_reqmap));
	if (!strcmp(serverkey("map"), rw_reqmap)) RampWear_Load();
};

float(float reqid, float responsecode, string body) RampWear_Reply =
{
	local float fh;
	local int n, length;
	local string pending, destination;
	if (!rw_req) return FALSE;
	if (reqid != rw_req) return FALSE;
	rw_req = 0;
	if (!RampWear_Allowed()) return TRUE;
	if (responsecode || strlen(body) < 10 || strlen(body) > 22369624)
	{
		print(sprintf("rampwear: %s not available (HTTP %g); existing data kept\n", rw_reqmap, responsecode));
		return TRUE;
	}
	if (rw_getatlas)
	{
		n = strlen(body);
		if (n & 3i) { print("rampwear: short atlas transport\n"); return TRUE; }
		length = (n / 4i) * 3i;
		if (str2chr(body, n - 1i) == 61) length = length - 1i;
		if (str2chr(body, n - 2i) == 61) length = length - 1i;
		if (length < 24i || length > 16777216i) { print("rampwear: atlas size refused\n"); return TRUE; }
		rw_encoded = memalloc(n + 4i); rw_decoded = memalloc(length + 4i); rw_decoding = TRUE;
		memcpy(rw_encoded, (void *)body, n);
		if (strcmp(rw_digest_ptr("SHA256", rw_encoded, n), rw_encodedhash))
		{
			RampWear_DecodeFree(); print("rampwear: atlas transport hash mismatch\n"); return TRUE;
		}
		rw_encodedlen = n; rw_decodedlen = length; rw_offset = rw_bytepos = 0i;
		return TRUE;
	}
	pending = sprintf("data/gfx/rampwear/%s.pending.txt", rw_reqmap);
	fh = fopen(pending, FILE_WRITE);
	if (fh < 0) { print("rampwear: cannot write download cache\n"); return TRUE; }
	fputs(fh, body); fclose(fh);
	if (!RampWear_Valid(pending, rw_reqmap))
	{
		print("rampwear: invalid/truncated geometry; existing data kept\n"); return TRUE;
	}
	fh = fopen(pending, FILE_READ); tokenize(fgets(fh)); fclose(fh);
	if (strcmp(argv(1), "2")) { print("rampwear: download needs a content-addressed v2 atlas\n"); return TRUE; }
	if (rw_hash != "") strunzone(rw_hash);
	if (rw_encodedhash != "") strunzone(rw_encodedhash);
	rw_hash = strzone(argv(5)); rw_encodedhash = strzone(argv(6));
	rw_width = stof(argv(7)); rw_height = stof(argv(8));
	destination = sprintf("data/gfx/rampwear/%s.net.txt", rw_reqmap);
	fh = fopen(destination, FILE_WRITE);
	if (fh < 0) { print("rampwear: cannot install geometry cache\n"); return TRUE; }
	fputs(fh, body); fclose(fh);
	rw_getatlas = TRUE; rw_req = Online_NextReq(); rw_at = gettime(0);
	if (!uri_get(strcat(RW_BASE, rw_reqmap, ".", rw_hash, ".png.b64"), rw_req))
	{
		rw_req = 0; print("rampwear: atlas request could not start\n");
	}
	else print(sprintf("rampwear: %s geometry cached; atlas requested\n", rw_reqmap));
	return TRUE;
};

void() RampWear_Init =
{
	registercvar("r_rampwear", "0", 0);
	registercvar("r_rampwear_dirt", "0", 0);
	registercvar("r_rampwear_scratch", "1.5", 0);
	registercvar("r_rampwear_distance", "12000", CVAR_ARCHIVE);
	registercvar("r_rampwear_shine", "0.15", CVAR_ARCHIVE);
	registercvar("r_rampwear_lift", "0.03125", CVAR_ARCHIVE);
	registercvar("r_rampwear_debug", "0", 0);
	registercommand("rampwear_download");
	registercommand("rampwear_status");
};

float(float cmdargc) RampWear_Command =
{
	local string command, mname;
	local vector size;
	command = argv(0);
	if (!strcmp(command, "rampwear_download"))
	{
		mname = cmdargc > 1 ? argv(1) : serverkey("map");
		RampWear_Request(mname); return TRUE;
	}
	if (!strcmp(command, "rampwear_status"))
	{
		print(sprintf("rampwear: map %s surfaces %g triangles %g pending %g\n", rw_map, rw_n, rw_ntri, rw_req != 0));
		size = '0 0 0';
		if (rw_shader != "") size = drawgetimagesize(rw_shader);
		print(sprintf("rampwear: atlas pixels %g %g texture %s\n", size_x, size_y, rw_texture));
		return TRUE;
	}
	return FALSE;
};

void() RampWear_Free =
{
	if (rw_alloc)
	{
		memfree(rw_cen); memfree(rw_rad); memfree(rw_first); memfree(rw_cnt);
		memfree(rw_pos); memfree(rw_st); memfree(rw_nrm);
	}
	if (rw_shader != "") strunzone(rw_shader);
	if (rw_texture != "") strunzone(rw_texture);
	rw_alloc = FALSE; rw_n = rw_ntri = 0;
	rw_shader = rw_texture = "";
};

void() RampWear_Load =
{
	local string mname, path, line, hash, texture;
	local float fh, ns, nt, s, t, j, modern;
	RampWear_Free();
	if (rw_map != "") strunzone(rw_map);
	mname = serverkey("map"); rw_map = strzone(mname);
	if (!RampWear_MapOK(mname)) return;
	path = sprintf("data/gfx/rampwear/%s.net.txt", mname);
	if (!RampWear_Valid(path, mname)) path = sprintf("gfx/rampwear/%s.txt", mname);
	if (!RampWear_Valid(path, mname)) return;
	fh = fopen(path, FILE_READ); tokenize(fgets(fh));
	ns = stof(argv(3)); nt = stof(argv(4));
	rw_imgw = rw_imgh = 0;
	if (!strcmp(argv(1), "2")) { rw_imgw = stof(argv(7)); rw_imgh = stof(argv(8)); }
	hash = strzone(!strcmp(argv(1), "2") ? argv(5) : "legacy");
	texture = !strcmp(hash, "legacy") ? sprintf("gfx/rampwear/%s.png", mname) : sprintf("data/gfx/rampwear/%s.%s.png", mname, hash);
	if (strcmp(hash, "legacy"))
	if (!RampWear_Exists(texture)) texture = sprintf("gfx/rampwear/%s.%s.png", mname, hash);
	if (!RampWear_Exists(texture)) { fclose(fh); strunzone(hash); return; }
	rw_texture = strzone(texture);
	rw_lift = bound(0, cvar("r_rampwear_lift"), 0.125);
	rw_cen = memalloc(sizeof(vector) * ns); rw_rad = memalloc(sizeof(float) * ns);
	rw_first = memalloc(sizeof(float) * ns); rw_cnt = memalloc(sizeof(float) * ns);
	rw_pos = memalloc(sizeof(vector) * nt * 3); rw_st = memalloc(sizeof(vector) * nt * 3);
	rw_nrm = memalloc(sizeof(vector) * nt); rw_alloc = TRUE;
	s = t = 0;
	while ((line = fgets(fh)))
	{
		tokenize(line);
		if (!strcmp(argv(0), "c"))
		{
			rw_cen[s] = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
			rw_rad[s] = stof(argv(4)) + rw_lift; rw_first[s] = t; rw_cnt[s] = 0; s = s + 1;
		}
		else
		{
			for (j = 0; j < 3; j = j + 1)
			{
				rw_pos[t * 3 + j] = [stof(argv(1 + j * 5)), stof(argv(2 + j * 5)), stof(argv(3 + j * 5))];
				rw_st[t * 3 + j] = [stof(argv(4 + j * 5)), stof(argv(5 + j * 5)), 0];
			}
			rw_nrm[t] = [stof(argv(16)), stof(argv(17)), stof(argv(18))];
			for (j = 0; j < 3; j = j + 1) rw_pos[t * 3 + j] = rw_pos[t * 3 + j] + normalize(rw_nrm[t]) * rw_lift;
			rw_cnt[s - 1] = rw_cnt[s - 1] + 1; t = t + 1;
		}
	}
	fclose(fh); rw_n = s; rw_ntri = t;
	fh = fopen("glsl/ftesurf_rampwear_v2.glsl", FILE_READ); modern = (fh >= 0); if (modern) fclose(fh);
	rw_shader = strzone(sprintf("ftesurf_rampwear_%s/%s/%s", modern ? "v2_close" : "legacy_close", mname, substring(hash, 0, 16)));
	strunzone(hash);
	shaderforname(rw_shader, sprintf("{\npolygonoffset 1\nnomipmaps\nnopicmip\nsort decal\n{\nprogram %s\nblendfunc %s\nclampmap $nosrgb:%s\nrgbgen exactvertex\nalphagen vertex\n}\n}\n",
	              modern ? "ftesurf_rampwear_v2" : "ftesurf_rampwear",
	              modern ? "gl_dst_color gl_src_color" : "gl_dst_color gl_zero", rw_texture));
	print(sprintf("rampwear: %s, %g surfaces, %g triangles, real lift %.3f units\n", mname, rw_n, rw_ntri, rw_lift));
};

void() RampWear_Frame =
{
	local float i, t, e, j, reach;
	local vector eye, fwd, d, col, image_size;
	if (rw_req)
	if (gettime(0) - rw_at > 30) { rw_req = 0; print("rampwear: request timed out; use rampwear_download to retry\n"); }
	RampWear_DecodeFrame();
	if (!cvar("r_rampwear")) return;
	if (strcmp(serverkey("map"), rw_map) || (rw_alloc && bound(0, cvar("r_rampwear_lift"), 0.125) != rw_lift)) RampWear_Load();
	if (strcmp(rw_tried, rw_map))
	if (!rw_req)
	if (RampWear_Allowed()) RampWear_Request(rw_map);
	if (!rw_n) return;
	// RESTYPE_TEXTURE queries flags=0 and cannot find this no-sRGB/clamped
	// texture. Query the actual custom material instead; do not deadlock its
	// first draw on an unrelated unflagged texture-cache entry.
	image_size = drawgetimagesize(rw_shader);
	if (!(image_size_x > 0 && image_size_y > 0)) return;
	if (rw_imgw > 0)
	if (image_size_x != rw_imgw || image_size_y != rw_imgh) return;
	eye = getproperty(VF_ORIGIN); reach = bound(1024, cvar("r_rampwear_distance"), 24000);
	makevectors(getproperty(VF_ANGLES)); fwd = v_forward;
	R_BeginPolygon(rw_shader, 0, FALSE);
	for (i = 0; i < rw_n; i = i + 1)
	{
		d = rw_cen[i] - eye;
		if (vlen(d) - rw_rad[i] > reach || d * fwd < -rw_rad[i]) continue;
		e = rw_first[i] + rw_cnt[i];
		for (t = rw_first[i]; t < e; t = t + 1)
		{
			col = rw_nrm[t] * 0.5 + '0.5 0.5 0.5';
			for (j = 0; j < 3; j = j + 1) R_PolygonVertex(rw_pos[t * 3 + j], rw_st[t * 3 + j], col, 1);
			R_EndPolygon();
		}
	}
};
