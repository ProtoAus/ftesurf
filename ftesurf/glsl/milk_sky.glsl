!!ver 130 150
!!permu FOG
!!samps milk=0 palette=1
!!cvardf r_skyfog=0.5

#include "sys/defs.h"
#include "sys/fog.h"
#include "glsl/milk_common.h"

varying vec3 pos;

#ifdef VERTEX_SHADER
void main(void)
{
	pos = v_position.xyz;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
// Positive exit from a sphere containing the eye: constant work, no raymarch.
vec3 skyHit(vec3 eye, vec3 ray, float radius)
{
	float b = dot(eye, ray);
	float t = -b + sqrt(max(0.0, b * b + radius * radius - dot(eye, eye)));
	return (eye + ray * t) / radius;
}

vec3 skyTone(vec2 a, vec2 b)
{
	vec3 c = (texture2D(s_palette, a).rgb + texture2D(s_palette, b).rgb) * 0.5;
	// Normalize each region independently: mixed thumbnails keep distinct hues.
	// Dark or grey photographs remain quiet/neutral, not an invented hue.
	return clamp(c / max(lum(c), 0.18), 0.2, 2.5);
}

float skyBand(vec3 p, vec3 axis, float latitude, float width)
{
	return 1.0 - smoothstep(width, width * 2.0, abs(dot(p, axis) - latitude));
}

void main(void)
{
	vec3 d = normalize(pos - e_eyepos);
	vec3 eye = (M_SKYEYE.xyz - M_SKYBOUNDS.xyz) / max(M_SKYBOUNDS.w, 4096.0);
	// Normally inside 0.5 map diagonals; bound remote spectator/teleport views.
	eye *= min(1.0, 1.5 / max(length(eye), 0.001)) * M_SKYEYE.w;
	vec3 nearp = skyHit(eye, d, 3.0);
	vec3 midp = skyHit(eye, d, 6.0);
	vec3 farp = skyHit(eye, d, 12.0);

	vec2 uv = 0.5 + 0.44 * farp.xy / (1.0 + abs(farp.z));
	vec3 emission = texture2D(s_milk, uv).rgb;
	float pulse = 1.0 + 0.12 * M_AUDIOATT.x * M_FOCUS.w;
	float nearband = skyBand(nearp, normalize(vec3(0.16, -0.23, 1.0)), 0.28, 0.006);
	float midband = skyBand(midp, normalize(vec3(-0.32, 0.78, 0.53)), -0.18, 0.008);
	float farband = skyBand(farp, normalize(vec3(0.72, 0.24, 0.65)), 0.0, 0.014);
	// Distinct-depth landmarks wrap continuously around the level in all directions.
	float ribs = pow(0.5 + 0.5 * cos(atan(nearp.y, nearp.x) * 12.0), 64.0)
	           * (1.0 - smoothstep(0.65, 0.9, abs(nearp.z)));
	float clouds = 0.5 + 0.5 * sin(farp.x * 8.0 + farp.y * 5.0 + farp.z * 7.0);
	vec3 house = vec3(0.55, 0.72, 1.0);
	vec3 nearTone = mix(house, skyTone(vec2(0.25, 0.25), vec2(0.25, 0.65)), M_SKYPALETTE.x);
	vec3 midTone = mix(house, skyTone(vec2(0.75, 0.25), vec2(0.75, 0.65)), M_SKYPALETTE.x);
	vec3 farTone = mix(house, skyTone(vec2(0.4, 0.85), vec2(0.6, 0.85)), M_SKYPALETTE.x);
	vec3 c = farTone * (0.045 + 0.035 * clouds + pulse * farband * 0.08)
	       + nearTone * pulse * (nearband * 0.20 + ribs * 0.025)
	       + midTone * pulse * midband * 0.13
	       + mix(nearTone, midTone, clouds) * lum(emission) * 0.22;
	// Palette-off retains the feedback's hue as well as the house landmark colour.
	c += emission * (1.0 - M_SKYPALETTE.x) * 0.22;
	c = aces(c * 1.7);
#ifdef FOG
	c = mix(c, w_fogcolour, float(r_skyfog) * w_fogalpha);
#endif
	gl_FragColor = vec4(c, 1.0);
}
#endif
