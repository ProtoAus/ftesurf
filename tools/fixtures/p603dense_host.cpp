#define P603_SCORES_MAIN ScoreControls
#include "p603scores_host.cpp"

static pluguimodel2_t DenseSnapshot(unsigned rows=24,unsigned token=160,const char *font="13")
{
	pluguimodel_t prior=FontSnapshot(font);
	pluguimodel2_t m={}; m.structsize=sizeof(m); m.revision=prior.revision; m.count=6+rows*9;
	std::memcpy(m.widgets,prior.widgets,6*sizeof(m.widgets[0]));
	std::snprintf(m.widgets[1].label,sizeof(m.widgets[1].label),"runs 1-%u of 40",rows);
	for (unsigned row=0;row<rows;row++)
		for (unsigned col=0;col<9;col++)
		{
			pluguiwidget_t &w=m.widgets[6+row*9+col]; w.row=token+row; w.id=w.row*16+col+1;
			w.type=col==3 ? PLUGUI_WIDGET_BUTTON : col==8 ? PLUGUI_WIDGET_CHECKBOX : PLUGUI_WIDGET_TEXT;
			std::snprintf(w.label,sizeof(w.label),col==3 ? "Player %u ## literal" : col==8 ? "off%u" : "%u",row);
		}
	return m;
}
static ImGuiTable *DenseTable()
{
	ImGuiWindow *w=ImGui::FindWindowByName("Scores table");
	return ImGui::GetCurrentContext()->Tables.GetByKey(w->GetID("runs"));
}
static ImVec2 DenseCell(unsigned col,unsigned row)
{
	ImGuiContext *saved=ImGui::GetCurrentContext(); ImGui::SetCurrentContext(contexts[1]->imgui);
	//Clipper's final seek stretches RowPosY2 over omitted rows. Use the
	//actual button/cell metrics, not that synthetic end-of-page rectangle.
	ImGuiTable *t=DenseTable(); float height=ImGui::GetFrameHeight()+2*t->RowCellPaddingY;
	ImVec2 p(t->Columns[col].WorkMinX+8,t->InnerWindow->DC.CursorStartPos.y+
		ImGui::GetTextLineHeight()+2*t->RowCellPaddingY+row*height+height*0.5f);
	std::printf("P603 DENSE CELL col=%u row=%u font=%.0f point=%.1f,%.1f height=%.1f origin=%.1f scroll=%.1f visible=%.1f..%.1f\n",
		col,row,ImGui::GetFontSize(),p.x,p.y,height,t->InnerWindow->DC.CursorStartPos.y,t->InnerWindow->Scroll.y,
		t->InnerWindow->ClipRect.Min.y,t->InnerWindow->ClipRect.Max.y);
	Check(p.y>=t->InnerWindow->ClipRect.Min.y && p.y<t->InnerWindow->ClipRect.Max.y,"requested actual dense cell is visible");
	ImGui::SetCurrentContext(saved); return p;
}
int main()
{
	if (ScoreControls()) return 1;
	unsigned start=checks; scoreowner.generation++;
	Check(service.Open(&scoreowner),"dense scoreboard opens");
	scoreframe.clip[2]=1680; scoreframe.clip[3]=620; scoreframe.pixelwidth=1920; scoreframe.pixelheight=1080;
	pluguimodel2_t m=DenseSnapshot(); Check(modelservice2.SetModel && modelservice2.PollModel,"dense service exported");
	Check(modelservice2.SetModel(&scoreowner,&m),"24-row counted page accepts atomically");
	Check(Frame(),"dense actual rows draw"); Check(Frame(),"dense rows settle");
	unsigned uploads=stats.uploads,created=creates;
	ImGuiContext *saved=ImGui::GetCurrentContext(); ImGui::SetCurrentContext(contexts[1]->imgui);
	ImGuiTable *t=DenseTable();
	Check(t->CurrentRow>6 && t->InnerWindow->ScrollMax.y>0,"real viewport draws more than six rows and has bounded vertical overflow");
	std::printf("P603 DENSE VIEW row=%d y=%.1f..%.1f scrollmax=%.1f\n",t->CurrentRow,t->RowPosY1,t->RowPosY2,t->InnerWindow->ScrollMax.y);
	ImGui::SetCurrentContext(saved);
	pluguimodelaction_t a={}; Click(DenseCell(3,8));
	Check(ScorePoll(a) && a.row==168 && a.id==168*16+4,"visible ninth-row watch acts");
	Click(DenseCell(8,8)); Check(ScorePoll(a) && a.row==168 && a.id==168*16+9,"visible ninth-row line acts");
	Check(!ScorePoll(a),"dense actions once only");
	//Real mouse-wheel input and the actual scrollbar must each reveal the tail.
	ImVec2 at=DenseCell(3,8); Event(PLUGUI_INPUT_MOUSEPOS,at.x,at.y); Check(Frame(),"dense wheel hover");
	for (unsigned n=0;n<5;n++) { Event(PLUGUI_INPUT_WHEEL,0,-10); Check(Frame(),"dense wheel down"); }
	Check(Frame(),"dense tail settles"); Click(DenseCell(3,23));
	Check(ScorePoll(a) && a.row==183 && a.id==183*16+4,"wheel-revealed last-row watch acts");
	Click(DenseCell(8,23)); Check(ScorePoll(a) && a.row==183 && a.id==183*16+9,"wheel-revealed last-row line acts");
	for (unsigned n=0;n<5;n++) { Event(PLUGUI_INPUT_WHEEL,0,10); Check(Frame(),"dense wheel up"); }
	ImGui::SetCurrentContext(contexts[1]->imgui); t=DenseTable();
	Check(t->InnerWindow->Scroll.y==0,"dense wheel reaches first row");
	ImRect bar=ImGui::GetWindowScrollbarRect(t->InnerWindow,ImGuiAxis_Y); ImGui::SetCurrentContext(saved);
	Event(PLUGUI_INPUT_MOUSEPOS,bar.GetCenter().x,bar.Min.y+5); Check(Frame(),"dense vertical scrollbar hover");
	Event(PLUGUI_INPUT_BUTTON,0,1); Check(Frame(),"dense vertical scrollbar press");
	Event(PLUGUI_INPUT_MOUSEPOS,bar.GetCenter().x,bar.Max.y-5); Check(Frame(),"dense vertical scrollbar drag");
	Event(PLUGUI_INPUT_BUTTON,0,0); Check(Frame(),"dense vertical scrollbar release"); Check(Frame(),"dense scrollbar settles");
	Click(DenseCell(8,23)); Check(ScorePoll(a) && a.row==183,"vertical scrollbar tail line acts");
	ImVec2 tail=DenseCell(3,23); Event(PLUGUI_INPUT_MOUSEPOS,tail.x,tail.y); Check(Frame(),"dense stale hover");
	Event(PLUGUI_INPUT_BUTTON,0,1); Check(Frame(),"dense stale held press");
	m=DenseSnapshot(24,240); Check(modelservice2.SetModel(&scoreowner,&m),"equal-sized next page replaces dense rows");
	Event(PLUGUI_INPUT_BUTTON,0,0); Check(Frame(),"old tail release after page replacement"); Check(!ScorePoll(a),"held tail cannot retarget replacement page");
	//Fresh first-row control after equal-sized paging: old vertical offset
	//must not hide the next page start (short pages clamp implicitly).
	Check(Frame(),"replacement page settles"); Click(DenseCell(3,0));
	Check(ScorePoll(a) && a.row==240,"equal-sized page first-row fresh watch acts");
	Click(DenseCell(3,0)); Check(contexts[1]->actions==1,"dense queued action control acts");
	m=DenseSnapshot(24,300); Check(modelservice2.SetModel(&scoreowner,&m),"unpolled dense action replacement");
	Check(!ScorePoll(a),"old unpolled dense action discarded"); Check(Frame(),"dense replacement draws");
	for (const char *font : {"13","16","20","24"})
	{
		m=DenseSnapshot(24,300,font); Check(modelservice2.SetModel(&scoreowner,&m),"dense physical font snapshot");
		Check(Frame(),"dense font draws"); Check(Frame(),"dense font settles");
		Click(DenseCell(3,0)); Check(ScorePoll(a) && a.row==300,"dense font fresh first-row watch acts");
		Check(stats.uploads==uploads && creates==created,"dense pages/font changes keep immutable atlas");
	}
	unsigned kept=contexts[1]->model.revision;
	for (unsigned fault=0;fault<5;fault++)
	{
		m=DenseSnapshot();
		if (fault==0) m.structsize--;
		if (fault==1) m.count=257;
		if (fault==2) m.widgets[80].id=m.widgets[79].id;
		if (fault==3) std::memcpy(m.widgets[80].label,"\xed\xa0\x80",4);
		if (fault==4) m.widgets[80].row++;
		Check(!modelservice2.SetModel(&scoreowner,&m) && contexts[1]->model.revision==kept,"bad dense page rejects atomically");
	}
	m=DenseSnapshot(25); Check(PlugUI_Model2Valid(&m),"25 rows fit generic 256-widget budget");
	Check(!modelservice2.SetModel(&scoreowner,&m),"scoreboard-specific 24-row cap rejects25");
	pluguimodel_t old=Snapshot(true); old.count=65; Check(!modelservice.SetModel(&scoreowner,&old),"exact /1 ABI still rejects65");
	service.Close(&scoreowner,PLUGUI_CLOSE_EXPLICIT);
	//General diagnostics use all256 widgets, but never257 or the /1 size.
	pluguiowner_t menu={PLUGUI_VM_MENU,InteractiveMenu,999}; Check(service.Open(&menu),"generic dense owner opens");
	m={}; m.structsize=sizeof(m); m.revision=1; m.count=256;
	for (unsigned n=0;n<256;n++) { m.widgets[n].id=n+1; m.widgets[n].row=n+1; m.widgets[n].type=PLUGUI_WIDGET_TEXT; }
	Check(modelservice2.SetModel(&menu,&m),"generic full256 accepts"); m.revision++; m.count=257;
	Check(!modelservice2.SetModel(&menu,&m),"generic257 rejects");
	service.Close(&menu,PLUGUI_CLOSE_EXPLICIT); Shutdown(); Check(live.empty(),"dense resources fully released");
	std::printf("P603 DENSE indexbits=%zu checks=%u failed=%u\n",sizeof(ImDrawIdx)*8,checks-start,faults);
	return faults ? 1 : 0;
}
