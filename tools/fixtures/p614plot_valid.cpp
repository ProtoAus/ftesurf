// Patch 614: the engine's shared grammar for NativeUIPlot/1 (plugins/ui_model.h), which the
// host runs on its copy of QC's rows and the provider runs again. Each case is one field of a
// valid revision or view made wrong; the verdict wanted is beside it. Built and run by
// tools/test_p614plot_unit.py against the real headers of the engine tree it is given.
#include "backend.h"
#include <cstdio>
#include <cstring>
#include <cmath>
#ifndef P614_GRAMMAR            // --header: a mutated copy, to show the table can fail
#define P614_GRAMMAR "../ui_model.h"
#endif
#include P614_GRAMMAR

//Room for the cases that must be refused for their SIZE alone: one row past a series' limit,
//and one past a revision's.
#define ROWS (PLUGUI_PLOT_MAX_TOTAL+8u)
static float xs[ROWS], as[ROWS], bs[ROWS];
static unsigned char brks[ROWS];
static pluguiplot_t Good()
{
	static const float x0[6] = {0, 0.5f, 1, 0, 0.25f, 0.25f}; // two series; the second restarts
	pluguiplot_t p;
	std::memset(&p, 0, sizeof(p));
	std::memset(xs, 0, sizeof(xs)); std::memset(as, 0, sizeof(as)); std::memset(bs, 0, sizeof(bs)); std::memset(brks, 0, sizeof(brks));
	for (int i = 0; i < 6; i++) { xs[i] = x0[i]; as[i] = 300+i; bs[i] = -i; brks[i] = (i == 4); }
	p.structsize = sizeof(p); p.revision = 7; p.count = 2; p.points = 6;
	p.series[0].flags = PLUGUI_PLOT_HAS_B | PLUGUI_PLOT_MARKED; p.series[0].first = 0; p.series[0].count = 3;
	p.series[1].flags = 0; p.series[1].first = 3; p.series[1].count = 3;
	for (int s = 0; s < 2; s++)
	{
		p.series[s].gap = 0.25f;
		p.series[s].rgb[0] = 0.5f; p.series[s].rgb[1] = 1; p.series[s].rgb[2] = 0;
	}
	p.x = xs; p.a = as; p.b = bs; p.brk = brks;
	return p;
}
static pluguiplotview_t GoodView()
{
	pluguiplotview_t v;
	std::memset(&v, 0, sizeof(v));
	v.structsize = sizeof(v); v.hidden = 0xffff; v.emphasis = 1; v.marked = 1; v.mark = 12.5f;
	v.textpx = 13; v.rangeserial = 3; v.x0 = 2; v.x1 = 9;
	return v;
}
static int failures;
static void Want(const char *name, int got, int want)
{
	std::printf("%s %s: valid %d, wanted %d\n", got == want ? "PASS" : "FAIL", name, got, want);
	if (got != want) failures++;
}
#define PLOT(name, want, ...) { pluguiplot_t p = Good(); __VA_ARGS__; Want(name, PlugUI_PlotValid(&p), want); }
#define VIEW(name, want, ...) { pluguiplotview_t v = GoodView(); __VA_ARGS__; Want(name, PlugUI_PlotViewValid(&v), want); }

int main()
{
	const float nan = std::nanf(""), inf = HUGE_VALF;
	//The controls: without these every refusal below could be the baseline's.
	PLOT("plot baseline", 1, (void)0)
	PLOT("plot equal-x", 1, xs[1] = 0)
	PLOT("plot second-series-restarts", 1, xs[3] = 0)
	{
		pluguiplot_t p; std::memset(&p, 0, sizeof(p)); p.structsize = sizeof(p); p.revision = 1;
		Want("plot empty", PlugUI_PlotValid(&p), 1);
	}
	Want("plot null", PlugUI_PlotValid(nullptr), 0);
	PLOT("plot structsize", 0, p.structsize--)
	PLOT("plot revision-zero", 0, p.revision = 0)
	PLOT("plot revision-past-id", 0, p.revision = PLUGUI_MODEL_MAX_ID+1)
	//(Seventeen series cannot be laid out in a sixteen-entry table: the count rule is what
	//keeps the reader inside it, and nothing else can be shown to refuse this.)
	PLOT("plot seventeen-series", 0, p.count = PLUGUI_PLOT_MAX_SERIES+1)
	{	//Nine full series and one row more, every other rule satisfied: ten series.
		pluguiplot_t p = Good(); p.count = 10; p.points = PLUGUI_PLOT_MAX_TOTAL+1;
		for (unsigned s = 0; s < 10; s++)
		{
			p.series[s] = p.series[1]; p.series[s].first = s*PLUGUI_PLOT_MAX_POINTS;
			p.series[s].count = s < 9 ? PLUGUI_PLOT_MAX_POINTS : 1;
		}
		std::memset(xs, 0, sizeof(xs));
		Want("plot too-many-points", PlugUI_PlotValid(&p), 0);
		p.count = 9; p.points = PLUGUI_PLOT_MAX_TOTAL;
		Want("plot the-whole-allowance", PlugUI_PlotValid(&p), 1);
	}
	PLOT("plot null-x", 0, p.x = nullptr)
	PLOT("plot null-a", 0, p.a = nullptr)
	PLOT("plot null-b", 0, p.b = nullptr)
	PLOT("plot null-brk", 0, p.brk = nullptr)
	PLOT("plot unknown-flag", 0, p.series[1].flags = PLUGUI_PLOT_FLAGS+1)
	//An empty series whose neighbours still tile the rows: only the emptiness is wrong.
	PLOT("plot series-empty", 0, p.series[0].count = 0; p.series[1].first = 0; p.series[1].count = 6; xs[3] = xs[4] = xs[5] = 1)
	{	//One series a row past its limit, in a revision that large.
		pluguiplot_t p = Good(); p.count = 1; p.points = p.series[0].count = PLUGUI_PLOT_MAX_POINTS+1;
		std::memset(xs, 0, sizeof(xs));
		Want("plot series-too-long", PlugUI_PlotValid(&p), 0);
		p.points = p.series[0].count = PLUGUI_PLOT_MAX_POINTS;
		Want("plot series-at-its-limit", PlugUI_PlotValid(&p), 1);
	}
	PLOT("plot series-gap-in-rows", 0, p.series[1].first = 4)
	PLOT("plot series-overlaps", 0, p.series[1].first = 2)
	//(A series running past the revision's rows is refused before its rows are read, and
	//again when the totals are compared: two rules, by design. The arrays here are long
	//enough that neither reads outside them.)
	PLOT("plot series-past-points", 0, p.series[1].count = 4)
	PLOT("plot points-unclaimed", 0, p.points = 7)
	PLOT("plot gap-zero", 0, p.series[0].gap = 0)
	PLOT("plot gap-negative", 0, p.series[0].gap = -1)
	PLOT("plot gap-nan", 0, p.series[0].gap = nan)
	PLOT("plot gap-inf", 0, p.series[0].gap = inf)
	PLOT("plot colour-negative", 0, p.series[1].rgb[2] = -0.01f)
	PLOT("plot colour-over-one", 0, p.series[1].rgb[0] = 1.01f)
	PLOT("plot colour-nan", 0, p.series[1].rgb[1] = nan)
	PLOT("plot x-nan", 0, xs[2] = nan)
	PLOT("plot x-inf", 0, xs[5] = inf)
	PLOT("plot a-inf", 0, as[0] = -inf)
	PLOT("plot b-nan", 0, bs[4] = nan)
	PLOT("plot brk-two", 0, brks[1] = 2)
	PLOT("plot x-at-the-limit", 1, xs[2] = PLUGUI_PLOT_MAX_VALUE; as[0] = -PLUGUI_PLOT_MAX_VALUE; bs[5] = PLUGUI_PLOT_MAX_VALUE; p.series[1].gap = PLUGUI_PLOT_MAX_VALUE)
	PLOT("plot x-past-the-limit", 0, xs[2] = 2e9f)
	PLOT("plot x-far-below-the-limit", 0, xs[0] = -2e9f)
	PLOT("plot a-past-the-limit", 0, as[3] = -1.5e9f)
	PLOT("plot b-past-the-limit", 0, bs[1] = 3e30f)
	PLOT("plot gap-past-the-limit", 0, p.series[0].gap = 2e9f)
	PLOT("plot time-backwards", 0, xs[2] = 0.25f)
	PLOT("plot time-backwards-in-second", 0, xs[5] = 0.2f)
	PLOT("plot time-backwards-at-the-start", 0, xs[0] = 0.75f)          //a series' first pair
	PLOT("plot time-backwards-at-second-start", 0, xs[3] = 0.3f)

	VIEW("view baseline", 1, (void)0)
	VIEW("view nothing-asked", 1, v.hidden = v.emphasis = v.marked = v.rangeserial = 0; v.x0 = v.x1 = 0)
	Want("view null", PlugUI_PlotViewValid(nullptr), 0);
	VIEW("view structsize", 0, v.structsize++)
	VIEW("view hidden-too-wide", 0, v.hidden = 1u << PLUGUI_PLOT_MAX_SERIES)
	VIEW("view emphasis-too-wide", 0, v.emphasis = 1u << PLUGUI_PLOT_MAX_SERIES)
	VIEW("view marked-two", 0, v.marked = 2)
	VIEW("view mark-nan", 0, v.mark = nan)
	VIEW("view caption-zero", 0, v.textpx = 0)
	VIEW("view caption-huge", 0, v.textpx = 257)
	VIEW("view caption-nan", 0, v.textpx = nan)
	VIEW("view serial-past-id", 0, v.rangeserial = PLUGUI_MODEL_MAX_ID+1)
	VIEW("view at-the-limit", 1, v.mark = -PLUGUI_PLOT_MAX_VALUE; v.x0 = -PLUGUI_PLOT_MAX_VALUE; v.x1 = PLUGUI_PLOT_MAX_VALUE)
	VIEW("view mark-past-the-limit", 0, v.mark = 2e9f)
	VIEW("view range-past-the-limit", 0, v.x0 = -2e9f)
	VIEW("view range-end-past-the-limit", 0, v.x1 = 1e30f)
	VIEW("view range-inf", 0, v.x1 = inf)
	VIEW("view range-nan", 0, v.x0 = nan)

	//The other grammar in the header is the model's and has its own tools; name it used.
	(void)PlugUI_ModelValid; (void)PlugUI_Model2Valid;
	std::printf("P614 PLOT GRAMMAR failed=%d\n", failures);
	return failures != 0;
}
