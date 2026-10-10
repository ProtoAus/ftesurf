//Patch 614: the real provider (ui_imgui.cpp with plots.inc, pinned ImGui and ImPlot) and owner
//206 under acting fake host endpoints. What reaches the host's mesh is counted; the view, the
//cursor and the kept strips are read back through the actions QC polls; and the strips
//themselves are measured against the rows they were cut from.
#define main PassiveControls
#include "p598imgui_host.cpp"
#undef main
#include <cmath>

static pluguiowner_t plotowner = {PLUGUI_VM_CLIENT,PlotsClient,700};
static pluguiframe_t plotframe = {sizeof(plotframe),plotowner,1,1920,1080,1920,1080,{432,356,1488,792}};
static unsigned plotrevision;
static std::vector<float> xs, as, bs;
static std::vector<unsigned char> ks;
static float report[8];
static bool reported[8];
static bool Frame()
{
	plotframe.owner = plotowner; plotframe.frame++; ResetInk();
	if (!service.Draw(&plotframe)) return false;
	pluguiaction_t a;
	for (bool &r : reported) r = false;
	for (unsigned n = 0; inputservice.Poll(&plotowner,&a); n++)
	{
		Check(a.generation == plotowner.generation && a.id >= 1 && a.id < 8 && n < 8,"plot report is this owner's");
		if (a.id < 8) { report[a.id] = a.value; reported[a.id] = true; }
	}
	return true;
}
static void Event(unsigned type, float a = 0, float b = 0)
{
	pluguiinputevent_t e = {sizeof(e),type,a,b};
	Check(inputservice.Input(&plotowner,&e),"plot input accepted");
}
//kind 0: a run (speed climbing with a strafe wobble, energy stepping down); 1: white noise.
static pluguiplot_t Plot(unsigned series, unsigned rows, int kind)
{
	pluguiplot_t p = {};
	xs.assign(size_t(series)*rows,0); as = xs; bs = xs; ks.assign(xs.size(),0);
	unsigned seed = 12345;
	for (unsigned s = 0; s < series; s++)
		for (unsigned k = 0; k < rows; k++)
		{
			const size_t at = size_t(s)*rows+k;
			const float t = k*0.015f;
			seed = seed*1664525u+1013904223u;
			const float noise = float(seed >> 8)/16777216.0f;
			xs[at] = t;
			as[at] = kind ? noise*2000 : 300+25*t+40*s+3*std::sin(13*t+s);
			bs[at] = kind ? noise*900-450 : 14*t-float(int(t/6))*90-30*s;
		}
	p.structsize = sizeof(p); p.revision = ++plotrevision; p.count = series; p.points = series*rows;
	for (unsigned s = 0; s < series; s++)
	{
		pluguiplotseries_t &h = p.series[s];
		h.flags = PLUGUI_PLOT_HAS_B | (s == 0 ? PLUGUI_PLOT_MARKED : 0);
		h.first = s*rows; h.count = rows; h.gap = 0.25f;
		h.rgb[0] = 0.2f+0.25f*(s%4); h.rgb[1] = 0.9f-0.2f*(s%3); h.rgb[2] = 0.3f+0.1f*(s%5);
	}
	p.x = xs.data(); p.a = as.data(); p.b = bs.data(); p.brk = ks.data();
	return p;
}
static pluguiplotview_t View()
{
	pluguiplotview_t v = {};
	v.structsize = sizeof(v); v.textpx = 13;
	return v;
}
static PlotStore &Store() { return *contexts[1]->plots; }
//The furthest any row in view stands, vertically, from the strip that replaced it.
static float Deviation(int plot, unsigned series, unsigned rows)
{
	const PlotPool &pool = Store().pool[plot];
	const float *x = xs.data()+size_t(series)*rows, *y = (plot ? bs : as).data()+size_t(series)*rows;
	float worst = 0;
	unsigned covered = 0, inview = 0;
	for (unsigned k = 0; k < rows; k++)
	{
		if (x[k] < pool.x0 || x[k] > pool.x1) continue;
		inview++;
		const float px = float(pool.pos.x+(x[k]-pool.x0)/(pool.x1-pool.x0)*pool.size.x);
		const float py = float(pool.pos.y+pool.size.y-(y[k]-pool.y0)/(pool.y1-pool.y0)*pool.size.y);
		float best = 1e9f;
		for (unsigned n = 0; n < pool.nstrips; n++)
		{
			const PlotStrip &strip = pool.strips[n];
			if (strip.series != series) continue;
			const ImVec2 *p = pool.pts+strip.first;
			for (unsigned j = 0; j+1 < strip.count; j++)
			{
				if (px < p[j].x-0.02f || px > p[j+1].x+0.02f) continue;
				const float dx = p[j+1].x-p[j].x;
				const float at = dx > 0.02f ? p[j].y+(p[j+1].y-p[j].y)*std::min(std::max((px-p[j].x)/dx,0.0f),1.0f) : py;
				//On a vertical step the row lies on the step if it is between its ends.
				const float miss = dx > 0.02f ? std::fabs(at-py) :
					std::max(0.0f,std::max(std::min(p[j].y,p[j+1].y)-py,py-std::max(p[j].y,p[j+1].y)));
				best = std::min(best,miss);
			}
		}
		if (best < 1e8f) { covered++; worst = std::max(worst,best); }
	}
	Check(inview > 100 && covered == inview,"every row in view lies under a strip");
	return worst;
}
//The swing filter on its own, in pixels: for every point fed, the strips it wrote pass within
//the tolerance, vertically. Random walks, steps, and the one sequence a cone that starts too wide
//gets wrong (a 0.45 px spike straight after a vertex, then a flat run).
static float SwingWorst(const std::vector<ImVec2> &in, PlotPool &pool)
{
	pool.npts = pool.nstrips = 0;
	PlotSwing swing(pool,0);
	for (const ImVec2 &p : in) swing.Add(p);
	swing.End();
	Check(!swing.full && pool.nstrips == 1 && pool.strips[0].count >= 2,"one strip from one run of points");
	const ImVec2 *out = pool.pts+pool.strips[0].first;
	const unsigned n = pool.strips[0].count;
	Check(out[0].x == in.front().x && out[0].y == in.front().y && out[n-1].x == in.back().x && out[n-1].y == in.back().y,"both ends kept");
	float worst = 0;
	for (const ImVec2 &p : in)
	{
		//Every segment over this x: on a vertical step the point may lie on the step itself.
		float best = 1e9f;
		for (unsigned j = 0; j+1 < n; j++)
		{
			if (p.x < out[j].x-0.001f || p.x > out[j+1].x+0.001f) continue;
			const float dx = out[j+1].x-out[j].x;
			const float at = dx > 0.001f ? out[j].y+(out[j+1].y-out[j].y)*std::min(std::max((p.x-out[j].x)/dx,0.0f),1.0f) : p.y;
			best = std::min(best,dx > 0.001f ? std::fabs(at-p.y) :
				std::max(0.0f,std::max(std::min(out[j].y,out[j+1].y)-p.y,p.y-std::max(out[j].y,out[j+1].y))));
		}
		worst = std::max(worst,best);
	}
	return worst;
}
static void SwingControls()
{
	PlotPool *pool = new PlotPool;
	std::vector<ImVec2> in = {ImVec2(0,0),ImVec2(1,0.45f)};
	for (int x = 2; x <= 60; x++) in.push_back(ImVec2(float(x),0));
	float worst = SwingWorst(in,*pool);
	Check(worst <= PlotsTolerance+0.01f && pool->npts >= 3,"a spike straight after a vertex is kept");
	unsigned seed = 99, fewer = 0;
	for (int run = 0; run < 300; run++)
	{
		in.clear();
		float x = 100, y = 300;
		const int kind = run%3;
		for (int k = 0; k < 600; k++)
		{
			seed = seed*1664525u+1013904223u;
			const float r = float(seed >> 8)/16777216.0f-0.5f;
			x += kind == 2 ? 0.0f+float((seed >> 3)&1)*0.7f : 0.3f+float(seed&3)*0.2f; //kind 2 stands still half the time
			y += kind == 0 ? r*0.6f : kind == 1 ? r*9 : (k%97 ? r*0.2f : 40*r);
			in.push_back(ImVec2(x,y));
		}
		worst = std::max(worst,SwingWorst(in,*pool));
		fewer += pool->npts < in.size();
	}
	std::printf("P614 PLOTS swing filter: worst %.3f px over 301 runs, %u of 300 cut down\n",worst,fewer);
	Check(worst <= PlotsTolerance+0.01f,"the filter holds its tolerance on every run");
	Check(fewer >= 100,"and it does cut gentle runs down");
	delete pool;
}
static unsigned Settle() //the y axis is fitted a frame late: draw until nothing is cut afresh
{
	unsigned frames = 0;
	do { Check(Frame(),"plot frame draws"); frames++; } while (report[PlotsReportRebuilt] != 0 && frames < 8);
	return frames;
}
int main()
{
	if (PassiveControls()) return 1;
	const unsigned start = checks, faultsbefore = faults;
	SwingControls();
	plugcorefuncs_t coreapi = {};
	coreapi.GetEngineInterface = GetInterface; coreapi.ExportInterface = ExportInterface;
	coreapi.ExportFunction = ExportFunction; coreapi.Print = Print; cmdapi.AddCommand = AddCommand;

	//A host from before the patch refuses the table: the owner then refuses to open.
	plotavailable = false;
	Check(FTEPlug_Init(&coreapi),"older host still loads the provider");
	Check(!service.Open(&plotowner),"no plot service: owner 206 refuses"); service.Close(&plotowner,5);
	Check(!contexts[1],"refused open left nothing behind");
	plotavailable = true; Check(FTEPlug_Init(&coreapi),"plot-capable host loads");
	plotowner.generation++;
	Check(service.Open(&plotowner) && contexts[1] && contexts[1]->implot,"owner 206 opens with an ImPlot context");
	Check(!Frame(),"no revision yet: nothing to draw");
	pluguiplot_t p = Plot(3,3533,0);
	pluguiplotview_t v = View();
	Check(!plotservice.SetView(&plotowner,&v),"a view needs a plot");
	pluguiowner_t stranger = plotowner; stranger.generation++;
	Check(!plotservice.SetPlot(&stranger,&p),"another generation's plot is refused");
	stranger = {PLUGUI_VM_CLIENT,ScoresClient,plotowner.generation};
	Check(!plotservice.SetPlot(&stranger,&p),"another owner's plot is refused");
	Check(plotservice.SetPlot(&plotowner,&p) && plotservice.SetView(&plotowner,&v),"a revision and a view are taken");
	xs[5] = 1e9f; //the provider kept a copy, not the lender's pointer
	Check(Store().x[5] == 5*0.015f && Store().x != p.x,"rows are copied at SetPlot");
	xs[5] = 5*0.015f;

	//Three runs, whole view: drawn, bounded, and kept once the y axis has settled.
	unsigned frames = Settle();
	Check(frames >= 2 && frames <= 4 && report[PlotsReportRebuilt] == 0,"strips are kept once the axes settle");
	const float points = report[PlotsReportPoints];
	Check(reported[PlotsReportX0] && reported[PlotsReportX1] && !reported[PlotsReportHover],"view reported, no cursor");
	Check(std::fabs(report[PlotsReportX0]) < 0.01f && std::fabs(report[PlotsReportX1]-3532*0.015f) < 0.01f,"whole run in view");
	Check(points >= 12 && points <= 2*PlotsPoolPoints && Store().pool[0].nstrips == 3 && Store().pool[1].nstrips >= 3,"curves within the pool");
	Check(!ink.empty() && ink.size() < 200000,"bounded host vertices");
	const size_t steady = ink.size();
	Check(Frame() && report[PlotsReportRebuilt] == 0 && report[PlotsReportPoints] == points && ink.size() == steady,"a still view redraws the same strips");
	float worst = 0;
	for (unsigned s = 0; s < 3; s++) for (int plot = 0; plot < 2; plot++) worst = std::max(worst,Deviation(plot,s,3533));
	std::printf("P614 PLOTS deviation %.3f px over %g points (tolerance %.2f)\n",worst,points,PlotsTolerance);
	Check(worst <= PlotsTolerance+0.03f,"no row stands further than the tolerance from its strip");
	Check(points < 3*3533,"and the strips are fewer than the rows");

	//A range asked for once; the same serial again is not a second request.
	v.rangeserial = 1; v.x0 = 18; v.x1 = 30;
	Check(plotservice.SetView(&plotowner,&v),"range request taken"); Settle();
	Check(std::fabs(report[PlotsReportX0]-18) < 0.01f && std::fabs(report[PlotsReportX1]-30) < 0.01f,"asked range shown");
	worst = 0;
	for (unsigned s = 0; s < 3; s++) worst = std::max(worst,Deviation(0,s,3533));
	Check(worst <= PlotsTolerance+0.03f,"zoomed strips within tolerance");
	v.x0 = 2; v.x1 = 4; Check(plotservice.SetView(&plotowner,&v),"same serial"); Settle();
	Check(std::fabs(report[PlotsReportX0]-18) < 0.01f,"a serial is honoured once");

	//The cursor: inside a plot it reports a time in view; the wheel zooms about it.
	const PlotPool &speed = Store().pool[0];
	const float mx = speed.pos.x+speed.size.x*0.5f, my = speed.pos.y+speed.size.y*0.5f;
	Event(PLUGUI_INPUT_MOUSEPOS,mx,my); Check(Frame() && Frame(),"hover frames");
	Check(reported[PlotsReportHover] && std::fabs(report[PlotsReportHover]-24) < 0.05f,"cursor's time is the middle of 18..30");
	const float hovered = report[PlotsReportHover];
	Event(PLUGUI_INPUT_WHEEL,0,1); Settle();
	Check(std::fabs((report[PlotsReportX1]-report[PlotsReportX0])/12-1.25f/1.5f) < 0.01f,"a notch in is x0.833");
	Check(reported[PlotsReportHover] && std::fabs(report[PlotsReportHover]-hovered) < 0.03f,"about the cursor");
	//The right button without a drag: everything again.
	//(The release is seen in one frame and acted on in the next.)
	Event(PLUGUI_INPUT_BUTTON,1,1); Check(Frame(),"press"); Event(PLUGUI_INPUT_BUTTON,1,0); Check(Frame(),"release"); Settle();
	Check(std::fabs(report[PlotsReportX0]) < 0.01f && std::fabs(report[PlotsReportX1]-3532*0.015f) < 0.01f,"right button shows the whole run");
	Event(PLUGUI_INPUT_RESET); Check(Frame() && !reported[PlotsReportHover],"reset takes the cursor away");

	//Hidden and emphasised series are the view's, not a new revision.
	v.rangeserial = 1; v.hidden = 2; Check(plotservice.SetView(&plotowner,&v),"hide the second"); Settle();
	bool second = false; for (unsigned n = 0; n < Store().pool[0].nstrips; n++) second |= Store().pool[0].strips[n].series == 1;
	Check(!second && report[PlotsReportPoints] < points,"a hidden series has no strip");
	v.hidden = 0; v.emphasis = 1; Check(plotservice.SetView(&plotowner,&v),"pick out the first"); Settle();
	unsigned dim = 0; for (const auto &vert : ink) dim += vert.rgba[3] == 76 || vert.rgba[3] == 77;
	Check(dim > 100 && report[PlotsReportPoints] == points,"the others are drawn at 0.30, from the same strips");
	v.emphasis = 0; v.marked = 1; v.mark = 20; Check(plotservice.SetView(&plotowner,&v),"marker"); Check(Frame(),"marker frame");
	Check(ink.size() > steady,"the marker adds ink");
	v.marked = 0; Check(plotservice.SetView(&plotowner,&v),"marker off");

	//Refusals: none changes what is drawn.
	pluguiplot_t q = Plot(3,3533,0);
	q.revision = Store().revision; Check(!plotservice.SetPlot(&plotowner,&q),"a revision that does not rise");
	q.revision = Store().revision+1; xs[10] = xs[9]-1; Check(!plotservice.SetPlot(&plotowner,&q),"time running backwards");
	q = Plot(3,3533,0); as[7] = std::nanf(""); Check(!plotservice.SetPlot(&plotowner,&q),"a NaN value");
	q = Plot(3,3533,0); q.structsize--; Check(!plotservice.SetPlot(&plotowner,&q),"a struct of another size");
	Check(!plotservice.SetPlot(&plotowner,nullptr),"no plot at all");
	pluguiplotview_t w = v; w.hidden = 1u << PLUGUI_PLOT_MAX_SERIES; Check(!plotservice.SetView(&plotowner,&w),"a mask too wide");
	w = v; w.textpx = 0; Check(!plotservice.SetView(&plotowner,&w),"no caption size");
	w = v; w.mark = std::nanf(""); Check(!plotservice.SetView(&plotowner,&w),"a NaN marker");
	Settle(); Check(report[PlotsReportPoints] == points,"the plot is as it was");

	//A revision of another length is shown whole when the whole run was in view, and
	//leaves a view the player had zoomed alone (a loading line sends several a second).
	q = Plot(3,4000,0);
	Check(plotservice.SetPlot(&plotowner,&q),"a longer revision"); Settle();
	Check(std::fabs(report[PlotsReportX0]) < 0.01f && std::fabs(report[PlotsReportX1]-3999*0.015f) < 0.01f,"the whole view grows with the run");
	v.rangeserial = 2; v.x0 = 18; v.x1 = 30; Check(plotservice.SetView(&plotowner,&v),"zoom in"); Settle();
	q = Plot(3,3000,0);
	Check(plotservice.SetPlot(&plotowner,&q),"a shorter revision"); Settle();
	Check(std::fabs(report[PlotsReportX0]-18) < 0.01f && std::fabs(report[PlotsReportX1]-30) < 0.01f,"a zoomed view outlives a revision");
	v.rangeserial = 3; v.x0 = v.x1 = 0; Check(plotservice.SetView(&plotowner,&v),"everything again"); Settle();
	Check(std::fabs(report[PlotsReportX1]-2999*0.015f) < 0.01f,"and the whole run is the new one");

	//A view moved in x alone: two levels, so the fitted y axis is the same wherever the view
	//stands, and only the time range tells the kept strips they are stale.
	q = Plot(1,3000,0);
	for (unsigned k = 0; k < 3000; k++) { as[k] = (k/200)%2 ? 900.0f : 300.0f; bs[k] = (k/150)%2 ? 50.0f : -50.0f; }
	Check(plotservice.SetPlot(&plotowner,&q),"a square wave"); Settle();
	Check(Deviation(0,0,3000) <= PlotsTolerance+0.03f,"square wave drawn, whole");
	const double y0 = Store().pool[0].y0, y1 = Store().pool[0].y1;
	v.rangeserial = 4; v.x0 = 12; v.x1 = 33; Check(plotservice.SetView(&plotowner,&v),"pan and zoom in x"); Settle();
	Check(Store().pool[0].y0 == y0 && Store().pool[0].y1 == y1,"the y axis did not move (or this case shows nothing)");
	Check(std::fabs(Store().pool[0].x0-12) < 0.01 && Deviation(0,0,3000) <= PlotsTolerance+0.03f,"strips follow a view that moved in x alone");
	v.rangeserial = 5; v.x0 = v.x1 = 0; Check(plotservice.SetView(&plotowner,&v),"whole"); Settle();

	//Breaks and gaps cut a curve; nothing is drawn across them.
	q = Plot(1,2000,0); ks[700] = 1; for (unsigned k = 1200; k < 2000; k++) xs[k] += 3;
	Check(plotservice.SetPlot(&plotowner,&q),"a run with a break and a gap"); Settle();
	{
		const PlotPool &pool = Store().pool[0]; //a new revision is a new store: fetched again
		auto px = [&](float t) { return float(pool.pos.x+(t-pool.x0)/(pool.x1-pool.x0)*pool.size.x); };
		auto first = [&](unsigned n) { return pool.pts[pool.strips[n].first]; };
		auto last = [&](unsigned n) { return pool.pts[pool.strips[n].first+pool.strips[n].count-1]; };
		Check(pool.nstrips == 3 && Store().pool[1].nstrips >= 3,"three strips: before the break, between, after the gap");
		if (pool.nstrips == 3)
		{
			Check(std::fabs(last(0).x-px(699*0.015f)) < 0.05f && std::fabs(first(1).x-px(700*0.015f)) < 0.05f,"cut at the break, not across it");
			Check(std::fabs(last(1).x-px(1199*0.015f)) < 0.05f && std::fabs(first(2).x-px(1200*0.015f+3)) < 0.05f,"cut at the gap, not across it");
		}
	}

	//The worst a hostile caller can hand over: nine full series of noise. Bounded, and drawn.
	q = Plot(9,PLUGUI_PLOT_MAX_POINTS,1);
	Check(plotservice.SetPlot(&plotowner,&q),"nine full series are taken"); frames = Settle();
	Check(report[PlotsReportPoints] <= 2*PlotsPoolPoints && report[PlotsReportPoints] > 1000,"noise is cut to the pool");
	for (int plot = 0; plot < 2; plot++)
	{
		std::set<unsigned> drawn; //the pool is shared out: no series may take another's place
		for (unsigned n = 0; n < Store().pool[plot].nstrips; n++) drawn.insert(Store().pool[plot].strips[n].series);
		Check(drawn.size() == 9,"every one of the nine is drawn");
	}
	Check(ink.size() <= 18u*2*PlotsPoolPoints+60000 && Store().pool[0].npts <= PlotsPoolPoints && Store().pool[1].npts <= PlotsPoolPoints,"within the renderer's frame");
	std::printf("P614 PLOTS noise: %g points, %zu host vertices, %u frames to settle\n",report[PlotsReportPoints],ink.size(),frames);

	//A range that is not in the run: what is shown and reported stays inside it. (A report
	//past a million makes the host drop the owner; ImPlot alone left such a request
	//a quarter of the way back for a frame.)
	q = Plot(2,3533,0);
	Check(plotservice.SetPlot(&plotowner,&q),"two runs again"); Settle();
	v.rangeserial = 6; v.x0 = 5e6f; v.x1 = 6e6f; Check(plotservice.SetView(&plotowner,&v),"a range a million seconds out");
	for (int k = 0; k < 4; k++)
	{
		Check(Frame(),"far range frame");
		Check(report[PlotsReportX0] >= -0.01f && report[PlotsReportX1] <= 3532*0.015f+0.01f,"every frame's report is inside the run");
	}
	v.rangeserial = 7; v.x0 = -9e6f; v.x1 = 20; Check(plotservice.SetView(&plotowner,&v),"a range starting before the run");
	for (int k = 0; k < 4; k++)
	{
		Check(Frame(),"early range frame");
		Check(report[PlotsReportX0] >= -0.01f && report[PlotsReportX1] <= 20.01f,"every frame's report starts inside the run");
	}
	Check(std::fabs(report[PlotsReportX0]) < 0.01f && std::fabs(report[PlotsReportX1]-20) < 0.01f,"is cut to its start");
	v.rangeserial = 8; v.x0 = v.x1 = 0; Check(plotservice.SetView(&plotowner,&v),"whole"); Settle();

	//Numbers no plot can do arithmetic on are refused whole; the largest that are allowed
	//(a billion either way, rows five million seconds apart) must still be a frame the
	//backend takes and a report the host takes.
	q = Plot(1,200,0);
	for (unsigned k = 0; k < 200; k++) { xs[k] = k*1e28f; as[k] = (k&1) ? 1e30f : -1e30f; }
	Check(!plotservice.SetPlot(&plotowner,&q),"rows of absurd size are refused");
	q = Plot(1,200,0);
	for (unsigned k = 0; k < 200; k++) { xs[k] = k*5e6f; as[k] = (k&1) ? 1e9f : -1e9f; bs[k] = k*5e6f; }
	q.series[0].gap = 1e9f;
	Check(plotservice.SetPlot(&plotowner,&q),"rows at the bound are a valid revision");
	for (int k = 0; k < 4; k++) Check(Frame(),"and are drawn");
	bool sane = true; for (const auto &vert : ink) sane = sane && std::fabs(vert.xy[0]) <= 1.1e6f && std::fabs(vert.xy[1]) <= 1.1e6f;
	Check(sane && !ink.empty(),"no vertex past a million pixels");
	Check(std::fabs(report[PlotsReportX0]) <= 1e6f && std::fabs(report[PlotsReportX1]) <= 1e6f,"no report past a million");
	//Zoomed to the first quarter second, the next row is five million s outside the view: the
	//segment towards it must not carry a vertex out to where it would map.
	v.rangeserial = 9; v.x0 = 0; v.x1 = 0.25f; Check(plotservice.SetView(&plotowner,&v),"zoom to the first row");
	for (int k = 0; k < 4; k++) Check(Frame(),"drawn with its neighbour far outside");
	sane = !ink.empty(); for (const auto &vert : ink) sane = sane && std::fabs(vert.xy[0]) <= 1.1e6f && std::fabs(vert.xy[1]) <= 1.1e6f;
	Check(sane && report[PlotsReportPoints] >= 2,"the far row is drawn towards, and bounded");
	//A marker at the far end of that run is a billion seconds from this view: not drawn.
	v.marked = 1; v.mark = 9.95e8f; Check(plotservice.SetView(&plotowner,&v),"a marker far outside the view");
	Check(Frame() && Frame(),"is a frame the backend takes");
	sane = !ink.empty(); for (const auto &vert : ink) sane = sane && std::fabs(vert.xy[0]) <= 1.1e6f && std::fabs(vert.xy[1]) <= 1.1e6f;
	Check(sane,"with no vertex out where it would map");
	v.marked = 0; Check(plotservice.SetView(&plotowner,&v),"marker off again");
	{	//The clock under the plots. ImPlot hands it tick values: any double must come out text.
		PlotStore &st = Store(); const double keep = st.span; char text[64];
		st.span = 300; PlotsClock(125,text,sizeof(text),&st); Check(!std::strcmp(text,"2:05"),"a clock in minutes and seconds");
		st.span = 5; PlotsClock(125.26,text,sizeof(text),&st); Check(!std::strcmp(text,"2:05.3"),"to the tenth inside twenty seconds");
		st.span = 1; PlotsClock(-0.5,text,sizeof(text),&st); Check(!std::strcmp(text,"-0:00.50"),"to the hundredth inside two, and signed");
		st.span = 300; PlotsClock(1e30,text,sizeof(text),&st); Check(!std::strcmp(text,"1666666666:40"),"and bounded where the minutes are an int");
		st.span = keep;
	}
	const float mxh = Store().pool[0].pos.x+Store().pool[0].size.x*0.5f, myh = Store().pool[0].pos.y+Store().pool[0].size.y*0.5f;
	Event(PLUGUI_INPUT_MOUSEPOS,mxh,myh); Check(Frame() && Frame(),"hover over it");
	Check(!reported[PlotsReportHover] || std::fabs(report[PlotsReportHover]) <= 1e6f,"nor a cursor time past a million");
	Event(PLUGUI_INPUT_RESET); Check(Frame(),"reset");

	//An ImGui or ImPlot usage error is the frame's failure, not the process's.
	Check(!contexts[1]->imgui->IO.ConfigErrorRecoveryEnableAssert && contexts[1]->imgui->ErrorCallback == PlotsError,"usage errors go to the callback");
	PlotsError(nullptr,contexts[1],"injected"); Check(!Frame(),"and fail the frame"); contexts[1]->plotserror = false;
	Check(Frame(),"which is this owner's flag alone");

	//A rectangle too small to plot in fails the draw (QC then draws its own).
	plotframe.clip[2] = plotframe.clip[0]+120; Check(!Frame(),"a 120 px wide clip is refused");
	plotframe.clip[2] = 1488;
	service.Close(&plotowner,1);
	Check(!contexts[1] && live.empty(),"close frees the context and its atlas");
	Check(!plotservice.SetPlot(&plotowner,&q) && !plotservice.SetView(&plotowner,&v),"a closed owner takes nothing");
	std::printf("P614 PLOTS indexbits=%zu checks=%u failed=%u\n",sizeof(ImDrawIdx)*8,checks-start,faults-faultsbefore);
	return faults ? 1 : 0;
}
