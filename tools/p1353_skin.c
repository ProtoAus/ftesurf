/* P1353: native Q1 skin conversion control, compile/run on Windows and AArch64.
 * Mirrors SV_Snapshot_BuildStateQ1's one assignment; expected bits are independent.
 * gcc -O3 -Wall -Wextra p1353_skin.c -o p1353_skin && ./p1353_skin
 */
#include <stdio.h>
#include <stdint.h>

static unsigned direct(float skin) { return skin; }
static unsigned fixed(float skin)
{
	return skin < 0 ? (unsigned)(int)skin : (unsigned)skin;
}

int main(void)
{
	volatile float inputs[] = {-1, -3, -6, -7, -1000, 0, 1, 255, 65535, 2147483648.0f};
	const uint32_t expected[] = {0xffffffffu, 0xfffffffdu, 0xfffffffau, 0xfffffff9u,
		0xfffffc18u, 0, 1, 255, 65535, 0x80000000u};
	unsigned i, faults = 0, acted = 0;
	if (sizeof(unsigned) != 4) return 2;
	for (i = 0; i < sizeof(inputs)/sizeof(inputs[0]); ++i)
	{
		float skin = inputs[i];
		unsigned before = direct(skin), after = fixed(skin);
		printf("skin %.0f direct %u fixed %u expected %u\n", skin, before, after, expected[i]);
		faults += after != expected[i];
		acted += before != after;
		if (skin >= 0) faults += before != after;
	}
#if defined(__aarch64__)
	faults += acted != 5; /* The original ARM producer must actually lose all five tags. */
#endif
	printf("fixed_faults %u direct_differences %u\n", faults, acted);
	return faults != 0;
}
