// milk_common.h -- shared by ftesurf/glsl/milk_*.glsl (Patch 467).
//
// w_user[] is written by src/milk_sys.qc (Milk_Pack) through VF_USERDATA.
// The slot table here and the MU_* defines there are one contract.

#define M_TIME      w_user[0]   // x sim time  y tick dt  z aspect (w/h)  w tick count
#define M_AUDIO     w_user[1]   // x bass  y mid  z treb  w vol  (1 = typical for this audio, 0 = silent)
#define M_AUDIOATT  w_user[2]   // x bass_att  y mid_att  z treb_att  w beat pulse
#define M_CAMPOS    w_user[3]   // xyz camera  w tan(fov/2)
#define M_CAMFWD    w_user[4]   // xyz forward  w travel (0 settled .. 1 mid-flight)
#define M_CAMRIGHT  w_user[5]   // xyz right
#define M_CAMUP     w_user[6]   // xyz up
#define M_WARP      w_user[7]   // x zoom/tick  y rot/tick  z decay/tick  w wobble
#define M_LOOK      w_user[8]   // x hue  y trails  z bloom  w exposure
#define M_EVENT     w_user[9]   // x flash  y liquid  z speed 0..1  w beat_bass pulse
#define M_FOCUS     w_user[10]  // xy zoom centre (uv)  z highlight  w reactivity
#define M_EXTRA     w_user[11]  // xy present offset (uv)  z quality  w spare

// Station anchors -- mirrored by MS_* in src/menu/m_milk.qc.
#define ST_CUBE     vec3(0.0, 3.4, 0.0)
#define ST_TOWERS   vec3(64.0, 0.0, 0.0)
#define ST_TUNNEL   vec3(0.0, 3.0, 64.0)
#define ST_POOL     vec3(-64.0, 0.0, 0.0)

#define PI  3.14159265
#define TAU 6.28318531

// Dave Hoskins' sine-free hashes: stable across drivers, unlike fract(sin()).
float hash11(float p) { p = fract(p * 0.1031); p *= p + 33.33; p *= p + p; return fract(p); }
float hash12(vec2 p)  { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash13(vec3 p3) { p3 = fract(p3 * 0.1031); p3 += dot(p3, p3.zyx + 31.32); return fract((p3.x + p3.y) * p3.z); }
vec3  hash33(vec3 p3) { p3 = fract(p3 * vec3(0.1031, 0.1030, 0.0973)); p3 += dot(p3, p3.yxz + 33.33); return fract((p3.xxy + p3.yxx) * p3.zyx); }

float vnoise(vec3 p)
{
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash13(i),                   hash13(i + vec3(1.0, 0.0, 0.0)), f.x),
	               mix(hash13(i + vec3(0.0, 1.0, 0.0)), hash13(i + vec3(1.0, 1.0, 0.0)), f.x), f.y),
	           mix(mix(hash13(i + vec3(0.0, 0.0, 1.0)), hash13(i + vec3(1.0, 0.0, 1.0)), f.x),
	               mix(hash13(i + vec3(0.0, 1.0, 1.0)), hash13(i + vec3(1.0, 1.0, 1.0)), f.x), f.y), f.z);
}

mat2 rot2(float a) { float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }
float lum(vec3 c)  { return dot(c, vec3(0.299, 0.587, 0.114)); }

// The house palette: indigo -> cyan -> violet, with a warm accent at the top.
// t is a phase; M_LOOK.x rotates it per station.
vec3 milk_pal(float t)
{
	return vec3(0.50, 0.46, 0.62) + vec3(0.45, 0.42, 0.40) * cos(TAU * (vec3(1.0, 1.0, 1.0) * t + vec3(0.62, 0.40, 0.18)));
}

// ACES fitted (Narkowicz).  The feedback targets are half-float, so the
// composite is where HDR comes back down to display range.
vec3 aces(vec3 x)
{
	return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
