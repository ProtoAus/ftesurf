// P1084: what client/cl_profile.qc reads from CSQC, supplied from the menu's own
// pieces so hud_player's Stats page compiles here unchanged.
// cltime is declared in m_main.qc and set each frame in m_draw.
float ui_consent_ver;           // CSQC's consent.txt copy; Profile_Gate also reads rec_terms
string(int value) itos = #0:itos;

float(vector pos, float px, string mark, float a) SteamPic_Draw =
{
	return MP_Draw(pos, px, mark, a);
};

string(string s, float maxw, float sz) Chat_Fit =
{
	return ui_fit_text(s, maxw, [sz, sz]);
};

// The menu's fields read their keys inside sui_text_input (sui_sys.qc), so the
// page's Profile_FieldEvent is never called here and this is never reached.
void(float evtype, float scanx, float chary, string id, __inout string text, __inout float cursor) sui_text_event =
{
};
