// milk_cone.h -- the coarse pass (#CONE) of a world's scene (milk_sys.qc, the
// menu's "Coarse pass"): included after the world's map().  One ray per 4x4
// block of the full pass's pixels, marched as a cone wide enough to hold all
// sixteen: it stops where anything could be inside the cone -- or within
// `near`, where the world's own march gathers glow -- and the full pass starts
// each of those rays there (milk_conestart).  Exact for a map() that never
// overestimates.

// k: the cone's radius per unit of distance.  The coarse target is a quarter
// of the scene's height, so this pass's pixel is four of the full pass's; the
// farthest full pixel centre is two of its pixels from a block's centre, 2.83
// with the diagonal -- 3, for margin.
float milk_conek(vec2 t) { return 3.0 * 2.0 * M_CAMPOS.w * abs(dFdy(t.y)) / 4.0; }

float coneMarch(vec3 ro, vec3 rd, float k, float tmax, float near, int steps)
{
	float t = 0.02;
	for (int i = min(int(M_TIME.w), 0); i < 256; i++)
	{
		if (i >= steps)
			break;
		float d = map(ro + rd * t).x;
		float r = max(k * t, near);
		if (d < r)
			break;
		// Far enough that the ball the distance promises still holds the whole
		// cone at the new t -- and 15% short of it, for the worlds whose map()
		// is not quite a distance (their own marches under-step too).
		t += 0.85 * (d - k * t) / (1.0 + k);
		if (t > tmax)
			break;
	}
	return min(t, tmax);
}
