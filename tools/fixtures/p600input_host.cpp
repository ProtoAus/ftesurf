//Includes the existing acting passive/mesh controls and actual plugin sources.
#define main PassiveControls
#include "p598imgui_host.cpp"
#undef main
static pluguiowner_t owner = {1,InteractiveMenu,100};
static pluguiframe_t frame = {sizeof(frame),owner,1,320,240,640,480,{0,0,640,480}};
static bool Event(unsigned type, float a = 0, float b = 0)
{
	pluguiinputevent_t e = {sizeof(e),type,a,b};
	return inputservice.Input(&owner,&e) != qfalse;
}
static void DrawFrame()
{
	frame.owner = owner; frame.frame++; ResetInk();
	Check(service.Draw(&frame),"interactive native frame submits");
	Check(calls && !ink.empty(),"interactive glyph/widget ink acts");
}
static void Expect(unsigned id, float value)
{
	pluguiaction_t action = {};
	Check(inputservice.Poll(&owner,&action) && action.id == id && action.generation == owner.generation && action.value == value,
		"real widget action exactly identified");
	Check(!inputservice.Poll(&owner,&action),"action consumed only once");
}
static void Click(float x, float y)
{
	Check(Event(PLUGUI_INPUT_MOUSEPOS,x,y),"mouse position accepted"); DrawFrame();
	Check(Event(PLUGUI_INPUT_BUTTON,0,1),"press accepted"); DrawFrame();
	Check(Event(PLUGUI_INPUT_BUTTON,0,0),"release accepted"); DrawFrame();
}
int main()
{
	int passive = PassiveControls(); if (passive) return passive;
	unsigned initial = checks;
	plugcorefuncs_t coreapi = {};
	coreapi.GetEngineInterface = GetInterface; coreapi.ExportInterface = ExportInterface;
	coreapi.ExportFunction = ExportFunction; coreapi.Print = Print; cmdapi.AddCommand = AddCommand;
	inputavailable = false;
	Check(FTEPlug_Init(&coreapi),"old host still loads passive service");
	Check(!service.Open(&owner),"old host refuses interactive owner");
	pluguiowner_t oldowner = {1,GalleryMenu,99};
	Check(service.Open(&oldowner),"old host passive open acts"); service.Close(&oldowner,1);
	inputavailable = true; Check(FTEPlug_Init(&coreapi),"input-capable host loads");
	ImGuiContext *outside = ImGui::CreateContext();
	Check(service.Open(&owner),"interactive opens");
	pluguiowner_t other = {2,InteractiveClient,101};
	Check(service.Open(&other),"second VM interactive opens independently");
	Context *c = contexts[0]; DrawFrame(); DrawFrame();
	Click(100,110); Expect(1,1);
	Check(c->clicks == 1 && !contexts[1]->clicks,"acting button isolated by VM");
	Click(242,110); Expect(2,1); Check(c->enabled,"acting checkbox toggles");
	Click(100,136);
	Check(Event(PLUGUI_INPUT_TEXT,'A') && Event(PLUGUI_INPUT_TEXT,'B'),"queued text accepted");
	DrawFrame(); Expect(3,2); Check(!std::strcmp(c->text,"AB"),"real text field edited");
	Check(Event(PLUGUI_INPUT_KEY,PLUGUI_KEY_BACKSPACE,1),"navigation key accepted");
	DrawFrame(); Expect(3,1); Check(!std::strcmp(c->text,"A"),"real backspace acts");
	Check(Event(PLUGUI_INPUT_KEY,PLUGUI_KEY_BACKSPACE,0),"key release accepted"); DrawFrame();
	static_assert(sizeof(ImWchar)==4,"Unicode scalar storage must not truncate supplementary text");
	Check(Event(PLUGUI_INPUT_TEXT,0x1f642),"supplementary Unicode scalar accepted"); DrawFrame(); Expect(3,5);
	Check(!std::strcmp(c->text,"A\xf0\x9f\x99\x82"),"supplementary scalar preserves exact UTF-8 bytes");
	Event(PLUGUI_INPUT_KEY,PLUGUI_KEY_BACKSPACE,1); DrawFrame(); Expect(3,1);
	Event(PLUGUI_INPUT_KEY,PLUGUI_KEY_BACKSPACE,0); DrawFrame();
	Check(!std::strcmp(c->text,"A"),"backspace deletes whole supplementary scalar");
	ImGui::SetCurrentContext(c->imgui);
	Check(!ImGui::GetPlatformIO().Platform_GetClipboardTextFn && !ImGui::GetPlatformIO().Platform_SetClipboardTextFn &&
		!ImGui::GetPlatformIO().Platform_SetImeDataFn,"no OS clipboard/IME side channel");
	ImGui::SetCurrentContext(outside);
	//Both an already held press and a not-yet-consumed queued press must be abandoned.
	for (int held = 0; held < 2; held++)
	{
		Event(PLUGUI_INPUT_MOUSEPOS,100,110); DrawFrame(); Event(PLUGUI_INPUT_BUTTON,0,1);
		if (held) DrawFrame();
		Check(Event(PLUGUI_INPUT_RESET),"reset accepted");
		Event(PLUGUI_INPUT_BUTTON,0,0); DrawFrame();
		pluguiaction_t a = {}; Check(!inputservice.Poll(&owner,&a) && c->clicks == 1,"reset prevents latent click");
	}
	Event(PLUGUI_INPUT_KEY,PLUGUI_KEY_CTRL,1); Event(PLUGUI_INPUT_TEXT,'Z');
	Check(Event(PLUGUI_INPUT_RESET),"reset clears queued key/text"); DrawFrame();
	Check(!std::strcmp(c->text,"A"),"reset queued text never edits");
	ImGui::SetCurrentContext(c->imgui);
	Check(!ImGui::GetIO().KeyCtrl && !ImGui::GetIO().MouseDown[0],"reset no held modifier/button");
	ImGui::SetCurrentContext(outside);
	Click(100,110); DrawFrame();
	pluguiaction_t a = {}; Check(!inputservice.Poll(&owner,&a),"unread previous-frame action expires");
	Check(c->clicks == 2,"unread action control actually clicked");
	const pluguiinputevent_t invalid[] = {
		{0,1,0,0},{sizeof(pluguiinputevent_t),99,0,0},
		{sizeof(pluguiinputevent_t),1,std::numeric_limits<float>::quiet_NaN(),0},
		{sizeof(pluguiinputevent_t),1,0,std::numeric_limits<float>::infinity()},
		{sizeof(pluguiinputevent_t),1,32769,0},{sizeof(pluguiinputevent_t),2,5,0},
		{sizeof(pluguiinputevent_t),2,.5f,1},{sizeof(pluguiinputevent_t),2,0,2},
		{sizeof(pluguiinputevent_t),3,11,0},{sizeof(pluguiinputevent_t),4,0,1},
		{sizeof(pluguiinputevent_t),4,PLUGUI_KEY_MAX+1,1},{sizeof(pluguiinputevent_t),4,1,.5f},
		{sizeof(pluguiinputevent_t),5,0,0},{sizeof(pluguiinputevent_t),5,55296,0},
		{sizeof(pluguiinputevent_t),5,57343,0},{sizeof(pluguiinputevent_t),5,1114112,0},
		{sizeof(pluguiinputevent_t),5,65,1},{sizeof(pluguiinputevent_t),6,1,0}};
	for (const auto &e : invalid) Check(!inputservice.Input(&owner,&e),"malformed direct C event rejects");
	Check(!c->events,"invalid events do not enter queue");
	pluguiinputevent_t valid = {sizeof(valid),PLUGUI_INPUT_TEXT,'Q',0};
	pluguiowner_t stale = owner; stale.generation++;
	Check(!inputservice.Input(&stale,&valid) && !inputservice.Poll(&stale,&a),"stale generation denied");
	stale = owner; stale.owner++;
	Check(!inputservice.Input(&stale,&valid),"foreign owner denied");
	for (unsigned n = 0; n < PLUGUI_INPUT_MAX_EVENTS; n++) Check(Event(PLUGUI_INPUT_MOUSEPOS,float(n),0),"bounded queue fills with actual events");
	Check(!Event(PLUGUI_INPUT_TEXT,'X') && c->events == PLUGUI_INPUT_MAX_EVENTS,"queue overflow refuses without allocation growth");
	Check(Event(PLUGUI_INPUT_RESET) && !c->events,"reset works even at queue limit");
	Check(Event(PLUGUI_INPUT_WHEEL,0,1),"wheel transport accepts finite bound"); DrawFrame();
	//Trickled edges survive NewFrame. Bound the actual queue, not only per-frame counts.
	Check(Event(PLUGUI_INPUT_RESET),"reset before trickled backlog control");
	for (unsigned n = 0; n < PLUGUI_INPUT_MAX_EVENTS; n++)
		Check(Event(PLUGUI_INPUT_KEY,PLUGUI_KEY_SUPER,float(n&1)),"alternating key edges really enqueue");
	DrawFrame(); Check(c->imgui->InputEventsQueue.Size > 0,"trickled backlog control acted");
	for (int f = 0; f < 4; f++)
	{
		unsigned accepted = 0;
		while (accepted < PLUGUI_INPUT_MAX_EVENTS && Event(PLUGUI_INPUT_KEY,PLUGUI_KEY_SUPER,float(accepted&1))) accepted++;
		Check(c->imgui->InputEventsQueue.Size <= int(PLUGUI_INPUT_MAX_EVENTS),"cross-frame actual queue bounded");
		Check(accepted < PLUGUI_INPUT_MAX_EVENTS,"backlog prevents another whole frame burst");
		DrawFrame();
	}
	Check(Event(PLUGUI_INPUT_RESET) && !c->imgui->InputEventsQueue.Size,"reset reclaims trickled backlog");
	Check(ImGui::GetCurrentContext() == outside,"input/draw/reset restore external context");
	service.Close(&owner,1); Check(!inputservice.Input(&owner,&valid) && !inputservice.Poll(&owner,&a),"closed owner cannot input/poll");
	owner.generation++; Check(service.Open(&owner),"interactive reopen");
	Check(!contexts[0]->clicks && !contexts[0]->enabled && !contexts[0]->text[0] && !contexts[0]->events && !contexts[0]->actions,
		"reopen no widget/held/action state");
	Check(contexts[1] && contexts[1]->owner.generation == other.generation,"close preserves other VM");
	DrawFrame(); DrawFrame(); Click(100,136);
	for (unsigned n = 0; n < PLUGUI_INPUT_MAX_EVENTS; n++) Check(Event(PLUGUI_INPUT_TEXT,'X'),"bounded text arm actually types");
	DrawFrame(); Expect(3,127);
	Check(std::strlen(contexts[0]->text)==127 && !contexts[0]->text[127],"text edit cannot exceed fixed UTF-8 buffer");
	Check(Event(PLUGUI_INPUT_TEXT,'Y'),"full text buffer still accepts bounded transport"); DrawFrame();
	Check(!inputservice.Poll(&owner,&a) && std::strlen(contexts[0]->text)==127,"full text refuses growth/no false change action");
	Shutdown(); Check(live.empty() && stats.opens == stats.closes,"all passive/interactive atlases balance");
	ImGui::DestroyContext(outside);
	std::printf("P599 INPUT indexbits=%zu checks=%u failed=%u\n",sizeof(ImDrawIdx)*8,checks-initial,faults);
	return faults ? 1 : 0;
}
