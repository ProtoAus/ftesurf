//Same acting /1/font controls; one subject acceptance check, no downstream
//draw after a rejected snapshot. A six-row source freeze must fail exactly it.
#define P603_SCORES_MAIN ScoreControls
#include "p603scores_host.cpp"
int main()
{
	if (ScoreControls()) return 2;
	scoreowner.generation++; Check(service.Open(&scoreowner),"capacity control owner acts");
	pluguimodel_t old=FontSnapshot("13"); pluguimodel2_t m={};
	m.structsize=sizeof(m); m.revision=old.revision; m.count=6+24*9;
	std::memcpy(m.widgets,old.widgets,6*sizeof(m.widgets[0]));
	for (unsigned row=0;row<24;row++) for (unsigned col=0;col<9;col++)
	{
		pluguiwidget_t &w=m.widgets[6+row*9+col]; w=old.widgets[6+col];
		w.row=100+row; w.id=w.row*16+col+1;
	}
	Check(PlugUI_Model2Valid(&m),"capacity control valid counted222-widget input acts");
	Check(modelservice2.SetModel(&scoreowner,&m),"24-row acceptance falsifies six-row ceiling");
	service.Close(&scoreowner,PLUGUI_CLOSE_EXPLICIT); Shutdown();
	std::printf("P603 DENSE CONTROL indexbits=%zu failed=%u\n",sizeof(ImDrawIdx)*8,faults);
	return faults ? 1 : 0;
}
