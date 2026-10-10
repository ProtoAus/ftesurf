#define main PassiveControls
#include "p598imgui_host.cpp"
#undef main

static pluguiowner_t scoreowner = {PLUGUI_VM_CLIENT,ScoresClient,600};
static pluguiframe_t scoreframe = {sizeof(scoreframe),scoreowner,1,640,360,1280,720,{80,120,1100,620}};
static unsigned revision = 0;
static bool Frame()
{
	scoreframe.owner=scoreowner; scoreframe.frame++; ResetInk();
	return service.Draw(&scoreframe) != 0;
}
static void Event(unsigned type,float a=0,float b=0)
{
	pluguiinputevent_t e={sizeof(e),type,a,b};
	Check(inputservice.Input(&scoreowner,&e),"scores input accepted");
}
static pluguimodel_t Snapshot(bool active,unsigned token=20)
{
	pluguimodel_t m={}; m.structsize=sizeof(m); m.revision=++revision; m.count=23;
	for (unsigned i=0;i<4;i++)
	{
		pluguiwidget_t &w=m.widgets[i]; w.id=i+1; w.row=1;
		w.type=i==0 ? PLUGUI_WIDGET_CHECKBOX : i>1 ? PLUGUI_WIDGET_BUTTON : PLUGUI_WIDGET_TEXT;
		std::snprintf(w.label,sizeof(w.label),"%s",i==0 ? "pinned" : i==1 ? "runs 1-2 of 20" : i==2 ? "Previous" : "Next");
	}
	m.widgets[0].value=active ? 1 : 0;
	m.widgets[4].id=5; m.widgets[4].row=1; m.widgets[4].type=PLUGUI_WIDGET_CHECKBOX;
	for (unsigned row=0;row<2;row++)
		for (unsigned col=0;col<9;col++)
		{
			pluguiwidget_t &w=m.widgets[5+row*9+col]; w.row=token+row; w.id=w.row*16+col+1;
			w.type=col==3 ? PLUGUI_WIDGET_BUTTON : col==8 ? PLUGUI_WIDGET_CHECKBOX : PLUGUI_WIDGET_TEXT;
			std::snprintf(w.label,sizeof(w.label),"%s",col==3 ? (row ? "second UTF-8 \xc3\xa9" : "Literal ## / ### player") : col==8 ? "off" : "plain");
		}
	return m;
}
static ImVec2 Cell(unsigned col,unsigned row=0)
{
	ImGuiContext *previous=ImGui::GetCurrentContext();
	ImGui::SetCurrentContext(contexts[1]->imgui);
	ImGuiWindow *window=ImGui::FindWindowByName("Scores table");
	Check(window != nullptr,"real scores window exists");
	ImGuiTable *table=ImGui::GetCurrentContext()->Tables.GetByKey(window->GetID("runs"));
	Check(table != nullptr,"real scores table exists");
	float height=table->RowPosY2-table->RowPosY1;
	ImVec2 p(table->Columns[col].WorkMinX+8,table->RowPosY1-height*(1-row)+height*0.5f);
	ImGui::SetCurrentContext(previous);
	return p;
}
static void ReplayFits(const char *label)
{
	ImGuiContext *previous=ImGui::GetCurrentContext();
	ImGui::SetCurrentContext(contexts[1]->imgui);
	ImGuiWindow *window=ImGui::FindWindowByName("Scores table");
	ImGuiTable *table=ImGui::GetCurrentContext()->Tables.GetByKey(window->GetID("runs"));
	Check(table->Columns[4].WorkMaxX-table->Columns[4].WorkMinX >= ImGui::CalcTextSize(label).x,
		"complete replay claim fits actual column");
	ImGui::SetCurrentContext(previous);
}
static void Click(ImVec2 p)
{
	Event(PLUGUI_INPUT_MOUSEPOS,p.x,p.y); Check(Frame(),"scores hover renders");
	Event(PLUGUI_INPUT_BUTTON,0,1); Check(Frame(),"scores press renders");
	Event(PLUGUI_INPUT_BUTTON,0,0); Check(Frame(),"scores release renders");
}
static bool ScorePoll(pluguimodelaction_t &a) { return modelservice.PollModel(&scoreowner,&a) != 0; }
static void NarrowControls()
{
	pluguimodelaction_t a={};
	for (float width : {150.0f,190.0f,260.0f,400.0f})
	{
		service.Close(&scoreowner,PLUGUI_CLOSE_EXPLICIT); scoreowner.generation++;
		Check(service.Open(&scoreowner),"fresh narrow owner opens");
		scoreframe.clip[2]=scoreframe.clip[0]+width;
		scoreframe.clip[3]=scoreframe.clip[1]+300;
		pluguimodel_t m=Snapshot(true,60);
		std::snprintf(m.widgets[4].label,sizeof(m.widgets[4].label),"Your standing #99  0:03.150  Literal ## / ### player");
		Check(modelservice.SetModel(&scoreowner,&m),"narrow standing snapshot");
		Check(Frame(),"narrow table draws"); Check(Frame(),"narrow table settles");
		//Footer hit positions must remain inside the inherited viewport.
		bool stacked=width-16 < 188;
		ImVec2 previous(scoreframe.clip[0]+50,scoreframe.clip[3]-18-(stacked ? 23 : 0));
		ImVec2 next(scoreframe.clip[0]+(stacked ? 50 : 148),scoreframe.clip[3]-18);
		Click(next); Check(ScorePoll(a) && a.id==4 && a.row==1,"narrow Next acts inside viewport");
		Click(previous); Check(ScorePoll(a) && a.id==3 && a.row==1,"narrow Previous acts inside viewport");
		ImGuiContext *saved=ImGui::GetCurrentContext(); ImGui::SetCurrentContext(contexts[1]->imgui);
		ImGuiWindow *window=ImGui::FindWindowByName("Scores table");
		ImGuiTable *table=ImGui::GetCurrentContext()->Tables.GetByKey(window->GetID("runs"));
		ImRect bar=ImGui::GetWindowScrollbarRect(table->InnerWindow,ImGuiAxis_X);
		Check(table->InnerWindow->ScrollMax.x>0,"narrow horizontal overflow exists");
		Check(bar.Min.y>scoreframe.clip[1] && bar.Max.y<previous.y-9,"wrapped standing/footer does not cover scrollbar");
		ImGui::SetCurrentContext(saved);
		//The actual mouse-only scrollbar is reachable from the QC input contract.
		ImVec2 start(bar.Min.x+10,bar.GetCenter().y), end(bar.Max.x-10,bar.GetCenter().y);
		Event(PLUGUI_INPUT_MOUSEPOS,start.x,start.y); Check(Frame(),"scrollbar hover");
		Event(PLUGUI_INPUT_BUTTON,0,1); Check(Frame(),"scrollbar press");
		Event(PLUGUI_INPUT_MOUSEPOS,end.x,end.y); Check(Frame(),"scrollbar drag");
		Event(PLUGUI_INPUT_BUTTON,0,0); Check(Frame(),"scrollbar release"); Check(Frame(),"scrollbar settles");
		ImVec2 line=Cell(8);
		ImGui::SetCurrentContext(contexts[1]->imgui);
		std::printf("P603 NARROW width=%.0f scroll=%.1f max=%.1f bar=%.1f..%.1f line=%.1f\n",width,table->InnerWindow->Scroll.x,table->InnerWindow->ScrollMax.x,bar.Min.x,bar.Max.x,line.x);
		ImGui::SetCurrentContext(saved);
		Check(line.x>=scoreframe.clip[0] && line.x<scoreframe.clip[2],"scrollbar exposes line cell");
		Click(line); Check(ScorePoll(a) && a.id==60*16+9 && a.row==60,"narrow scrolled line acts");
		Check(!ScorePoll(a),"narrow actions once only");
	}
	scoreframe.clip[3]=scoreframe.clip[1]+80;
	Check(!Frame(),"too-short standing/table viewport requests legacy cover");
	scoreframe.clip[2]=1100; scoreframe.clip[3]=620;
	pluguimodel_t m=Snapshot(true,60); Check(modelservice.SetModel(&scoreowner,&m),"wide layout restored");
	Check(Frame(),"wide layout after narrow draws"); Check(Frame(),"wide layout after narrow settles");
}
static pluguimodel_t FontSnapshot(const char *size)
{
	pluguimodel_t m=Snapshot(true,60);
	for (unsigned i=m.count;i>5;i--) m.widgets[i]=m.widgets[i-1];
	m.count++;
	m.widgets[5]={}; m.widgets[5].id=6; m.widgets[5].row=1; m.widgets[5].type=PLUGUI_WIDGET_TEXT;
	std::snprintf(m.widgets[5].label,sizeof(m.widgets[5].label),"%s",size);
	std::snprintf(m.widgets[4].label,sizeof(m.widgets[4].label),"Your standing #99  0:03.150  Literal ## / ### player");
	return m;
}
static void FontControls()
{
	unsigned uploads=stats.uploads, created=creates;
	ImVec2 oldwatch=Cell(3);
	Event(PLUGUI_INPUT_MOUSEPOS,oldwatch.x,oldwatch.y); Check(Frame(),"font-change hover");
	Event(PLUGUI_INPUT_BUTTON,0,1); Check(Frame(),"font-change held press");
	pluguimodel_t m=FontSnapshot("20"); Check(modelservice.SetModel(&scoreowner,&m),"font-change snapshot");
	Event(PLUGUI_INPUT_BUTTON,0,0); Check(Frame(),"font-change old release");
	pluguimodelaction_t a={}; Check(!ScorePoll(a),"font change abandons old held authority");
	scoreframe.clip[2]=scoreframe.clip[0]+1600; scoreframe.clip[3]=scoreframe.clip[1]+640;
	scoreframe.pixelwidth=1920; scoreframe.pixelheight=1080;
	for (const char *size : {"13","16","20","24","13","24","16"})
	{
		m=FontSnapshot(size); Check(modelservice.SetModel(&scoreowner,&m),"physical-font metadata accepted");
		Check(Frame(),"font selection draws"); Check(Frame(),"font selection settles");
		ImGuiContext *previous=ImGui::GetCurrentContext(); ImGui::SetCurrentContext(contexts[1]->imgui);
		ImGuiIO &io=ImGui::GetIO(); ImFont *font=io.FontDefault;
		Check(io.Fonts->Fonts.Size==4,"bounded four-bake scoreboard atlas");
		Check(font && font->FontSize==std::atoi(size) && ImGui::GetFontSize()==font->FontSize,"selected actual physical bake");
		Check(font->Sources && font->Sources->SizePixels==font->FontSize,"selected rasterizer physical size");
		Check(io.FontGlobalScale==1 && io.DisplayFramebufferScale.x==1 && io.DisplayFramebufferScale.y==1,
			"no font or framebuffer bitmap scaling");
		const ImFontGlyph *glyph=font->FindGlyphNoFallback('A');
		Check(glyph && glyph->Visible && glyph->X1>glyph->X0 && glyph->Y1>glyph->Y0,"real baked glyph coverage");
		std::printf("P603 FONT size=%s bake=%.0f glyph=%.0fx%.0f atlas=%dx%d uploads=%u\n",size,font->FontSize,
			glyph ? glyph->X1-glyph->X0 : 0,glyph ? glyph->Y1-glyph->Y0 : 0,io.Fonts->TexWidth,io.Fonts->TexHeight,stats.uploads-uploads);
		ImGui::SetCurrentContext(previous);
		Click(Cell(3)); Check(ScorePoll(a) && a.row==60 && a.id==60*16+4,"font-size watch acts");
		Click(Cell(8)); Check(ScorePoll(a) && a.row==60 && a.id==60*16+9,"font-size line acts");
		Check(!ScorePoll(a),"font-size actions exactly once");
		//Both virtual axes vary independently; native physical geometry stays identical.
		Event(PLUGUI_INPUT_MOUSEPOS,-100,-100); Check(Frame(),"font pixel control hover cleared"); Check(Frame(),"font pixel control settles");
		scoreframe.virtualwidth=1920; scoreframe.virtualheight=1080; Check(Frame(),"font pixel scale1");
		auto control=ink;
		scoreframe.virtualwidth=960; scoreframe.virtualheight=720; Check(Frame(),"font pixel anisotropic scale2");
		Check(control.size()==ink.size() && !control.empty() && !std::memcmp(control.data(),ink.data(),control.size()*sizeof(control[0])),
			"virtual-scale-invariant actual font geometry");
		Check(stats.uploads==uploads && creates==created,"size changes and steady draws do not upload or recreate atlas");
		ReplayFits("plain");
	}
	for (const char *size : {"","17","13.0","20 commands","nan","24##bad"})
	{
		m=FontSnapshot(size); Check(PlugUI_ModelValid(&m),"bad font metadata passes generic model grammar");
		unsigned kept=contexts[1]->model.revision;
		Check(!modelservice.SetModel(&scoreowner,&m) && contexts[1]->model.revision==kept,"unsupported font metadata rejects atomically");
	}
	m=FontSnapshot("20"); m.widgets[5].row=2;
	Check(!modelservice.SetModel(&scoreowner,&m),"font metadata cannot carry row authority");
	m=FontSnapshot("20"); m.widgets[5].type=PLUGUI_WIDGET_BUTTON;
	Check(!modelservice.SetModel(&scoreowner,&m),"font metadata cannot become an action");
	//At large fonts, a narrow viewport must reserve both wrapped text and stacked buttons.
	for (const char *size : {"16","20","24"})
	{
		m=FontSnapshot(size); Check(modelservice.SetModel(&scoreowner,&m),"narrow large-font snapshot");
		scoreframe.clip[2]=scoreframe.clip[0]+260; Check(Frame(),"narrow large font draws"); Check(Frame(),"narrow large font settles");
		ImGuiContext *saved=ImGui::GetCurrentContext(); ImGui::SetCurrentContext(contexts[1]->imgui);
		ImGuiWindow *window=ImGui::FindWindowByName("Scores table");
		ImGuiTable *table=ImGui::GetCurrentContext()->Tables.GetByKey(window->GetID("runs"));
		ImRect bar=ImGui::GetWindowScrollbarRect(table->InnerWindow,ImGuiAxis_X);
		float button=ImGui::GetFrameHeightWithSpacing(), pad=ImGui::GetStyle().WindowPadding.y;
		ImVec2 next(scoreframe.clip[0]+50,scoreframe.clip[3]-pad-button*0.5f);
		ImVec2 back(next.x,next.y-(size[0]=='1' ? 0 : button));
		bool stacked=260-2*ImGui::GetStyle().WindowPadding.x < 180*ImGui::GetFontSize()/13+ImGui::GetStyle().ItemSpacing.x;
		if (stacked) back.y=next.y-button; else { back=next; next.x+=90*ImGui::GetFontSize()/13+ImGui::GetStyle().ItemSpacing.x; }
		Check(bar.Max.y<back.y-button*0.5f,"large-font wrapped standing leaves scrollbar reachable");
		ImGui::SetCurrentContext(saved);
		Click(next); Check(ScorePoll(a) && a.id==4,"large-font narrow Next acts");
		Click(back); Check(ScorePoll(a) && a.id==3,"large-font narrow Previous acts");
		//Scroll position deliberately survives size changes. Reset through actual
		//horizontal wheel input before grabbing the now-leftmost thumb.
		Event(PLUGUI_INPUT_MOUSEPOS,bar.Min.x+50,bar.Min.y-40); Check(Frame(),"large-font wheel hover");
		for (unsigned wheel=0;wheel<5;wheel++) { Event(PLUGUI_INPUT_WHEEL,10,0); Check(Frame(),"large-font wheel left"); }
		Check(table->InnerWindow->Scroll.x==0,"large-font wheel reaches left edge");
		Event(PLUGUI_INPUT_MOUSEPOS,bar.Min.x+4,(bar.Min.y+bar.Max.y)/2); Check(Frame(),"large-font scrollbar hover");
		Event(PLUGUI_INPUT_BUTTON,0,1); Check(Frame(),"large-font scrollbar press");
		Event(PLUGUI_INPUT_MOUSEPOS,bar.Max.x-3,(bar.Min.y+bar.Max.y)/2); Check(Frame(),"large-font scrollbar drag");
		Event(PLUGUI_INPUT_BUTTON,0,0); Check(Frame(),"large-font scrollbar release");
		Check(table->InnerWindow->Scroll.x>0,"large-font scrollbar drag acts");
		ImVec2 linepoint=Cell(8);
		std::printf("P603 SCROLL FONT size=%s point=%.1f,%.1f scroll=%.1f column=%.1f..%.1f clip=%.1f..%.1f\n",size,
			linepoint.x,linepoint.y,table->InnerWindow->Scroll.x,table->Columns[8].MinX,table->Columns[8].MaxX,
			table->Columns[8].ClipRect.Min.x,table->Columns[8].ClipRect.Max.x);
		Click(linepoint); bool acted=ScorePoll(a);
		std::printf("P603 SCROLL ACTION size=%s acted=%d id=%u row=%u\n",size,int(acted),a.id,a.row);
		Check(acted && a.id==60*16+9,"large-font scrolled line acts");
	}
	scoreframe.clip[2]=1100; scoreframe.clip[3]=620; scoreframe.pixelwidth=1280; scoreframe.pixelheight=720;
	scoreframe.virtualwidth=640; scoreframe.virtualheight=360;
	m=Snapshot(true,60); Check(modelservice.SetModel(&scoreowner,&m),"old schema restored without reopen"); Check(Frame(),"default-font old schema draws");
	ImGuiContext *previous=ImGui::GetCurrentContext(); ImGui::SetCurrentContext(contexts[1]->imgui);
	Check(ImGui::GetFontSize()==13,"five-metadata schema selects default physical bake"); ImGui::SetCurrentContext(previous);
}
#ifndef P603_SCORES_MAIN
#define P603_SCORES_MAIN main
#endif
int P603_SCORES_MAIN()
{
	if (PassiveControls()) return 1;
	unsigned start=checks;
	Check(service.Open(&scoreowner),"real CSQC scores owner opens");
	pluguimodel_t m=Snapshot(false); Check(modelservice.SetModel(&scoreowner,&m),"passive score snapshot");
	Check(Frame(),"passive actual rows render"); Check(Frame(),"passive stable frame");
	ImVec2 watch=Cell(3), line=Cell(8);
	pluguimodelaction_t a={};
	Click(watch); Check(!ScorePoll(a),"passive table cannot join mouse capture");
	m=Snapshot(true); Check(modelservice.SetModel(&scoreowner,&m),"pinned score snapshot");
	Check(Frame(),"pinned render"); Check(Frame(),"pinned stable frame");
	watch=Cell(3); line=Cell(8);
	Click(watch); Check(ScorePoll(a) && a.revision==m.revision && a.id==20*16+4 && a.row==20 && a.value==1,"acting watch stable row identity");
	Check(!ScorePoll(a),"watch once only");
	Click(line); Check(ScorePoll(a) && a.id==20*16+9 && a.row==20 && a.value==1,"acting line stable row identity");
	Check(!ScorePoll(a),"line once only");
	//Acting controls above are required before cancellation subjects.
	Event(PLUGUI_INPUT_MOUSEPOS,watch.x,watch.y); Check(Frame(),"stale hover");
	Event(PLUGUI_INPUT_BUTTON,0,1); Check(Frame(),"stale old-row press");
	m=Snapshot(true,40); Check(modelservice.SetModel(&scoreowner,&m),"replace rows atomically");
	Event(PLUGUI_INPUT_BUTTON,0,0); Check(Frame(),"release over replacement");
	Check(!ScorePoll(a),"held old click cannot retarget new row");
	Check(Frame(),"replacement stable frame"); watch=Cell(3); Click(watch);
	Check(ScorePoll(a) && a.row==40 && a.id==40*16+4,"replacement control acts");
	Click(watch); Check(contexts[1]->actions==1,"acting unpolled action control");
	m=Snapshot(true,60); Check(modelservice.SetModel(&scoreowner,&m),"queued-action replacement");
	Check(Frame(),"queued replacement frame"); Check(!ScorePoll(a),"unpolled old action is discarded");
	Check(Frame(),"focus control stable"); watch=Cell(3);
	Event(PLUGUI_INPUT_MOUSEPOS,watch.x,watch.y); Check(Frame(),"focus hover");
	Event(PLUGUI_INPUT_BUTTON,0,1); Check(Frame(),"focus press");
	Event(PLUGUI_INPUT_RESET); Event(PLUGUI_INPUT_BUTTON,0,0); Check(Frame(),"focus release");
	Check(!ScorePoll(a),"interruption cannot activate held row");
	//Display-only metadata highlights a real token; an outside standing is not a row.
	m=Snapshot(true,60); m.widgets[4].row=61; m.widgets[4].value=1;
	std::snprintf(m.widgets[4].label,sizeof(m.widgets[4].label),"Your standing #99  0:03.150  Literal ## / ### player");
	Check(modelservice.SetModel(&scoreowner,&m),"highlight/standing snapshot accepted");
	Check(Frame(),"highlight and standing draw"); Check(Frame(),"highlight stable");
	Click(Cell(3,1)); Check(ScorePoll(a) && a.row==61,"highlighted real row still acts");
	Check(!ScorePoll(a),"standing emits no action");
	for (const char *label : {"watch (verified)","Get demo (verified)","queued (verified)","retry (verified)",
		"A bounded but unusually long replay verification claim"})
	{
		m=Snapshot(true,60); std::snprintf(m.widgets[9].label,sizeof(m.widgets[9].label),"%s",label);
		Check(modelservice.SetModel(&scoreowner,&m),"replay claim snapshot accepted");
		Check(Frame(),"replay claim draws"); Check(Frame(),"replay claim settles"); ReplayFits(label);
	}
	m=Snapshot(true,60); Check(modelservice.SetModel(&scoreowner,&m),"restore action layout");
	Check(Frame(),"restored action layout draws"); Check(Frame(),"restored action layout settles");
	Click(Cell(8)); Check(ScorePoll(a) && a.row==60 && a.id==60*16+9,"line acts after replay width changes");
	pluguimodel_t bad=Snapshot(true); bad.widgets[4].row=999; bad.widgets[4].value=1;
	Check(PlugUI_ModelValid(&bad),"orphan highlight passes generic grammar");
	Check(!modelservice.SetModel(&scoreowner,&bad),"orphan highlight rejected");
	bad=Snapshot(true); bad.widgets[6].id=9999;
	Check(PlugUI_ModelValid(&bad),"cell-role subject passes generic model grammar");
	Check(!modelservice.SetModel(&scoreowner,&bad),"invalid scoreboard cell role rejected");
	Check(Frame(),"bad snapshot retains previous complete table");
	Check(ink.size()>0 && !commands.empty(),"real native indexed mesh acts");
	for (const plugmeshcommand_t &cmd:commands)
		Check(cmd.clip[0]>=80 && cmd.clip[1]>=120 && cmd.clip[2]<=1100 && cmd.clip[3]<=620,"physical inherited table clip");
	NarrowControls();
	FontControls();
	service.Close(&scoreowner,PLUGUI_CLOSE_EXPLICIT);
	pluguiinputevent_t reset={sizeof(reset),PLUGUI_INPUT_RESET,0,0};
	Check(!inputservice.Input(&scoreowner,&reset),"closed owner rejects input");
	Shutdown(); Check(live.empty(),"scores close/stop releases resources");
	std::printf("P603 SCORES indexbits=%zu checks=%u failed=%u\n",sizeof(ImDrawIdx)*8,checks-start,faults);
	return faults ? 1 : 0;
}
