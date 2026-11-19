// Board filters: direction and segmentation are independent axes. Wire names
// retain the existing Normal clean/segmented boards; no run is reclassified.
string(float direction) FS_BoardDirectionName =
{
	if (direction == 1) return "Sideways";
	if (direction == 2) return "Half-Sideways";
	if (direction == 3) return "Backwards";
	return "Normal";
};

float(string style) FS_BoardDirection =
{
	if (!strcmp(style, "sw") || !strcmp(style, "segmented_sw")) return 1;
	if (!strcmp(style, "hsw") || !strcmp(style, "segmented_hsw")) return 2;
	if (!strcmp(style, "bw") || !strcmp(style, "segmented_bw")) return 3;
	return 0;
};

float(string style) FS_BoardSegmented =
{
	return !strcmp(substring(style, 0, 9), "segmented");
};

string(string style) FS_BoardStyleName =
{
	if (!strcmp(style, "tas")) return "TAS";
	return strcat(FS_BoardSegmented(style) ? "Segmented " : "", FS_BoardDirectionName(FS_BoardDirection(style)));
};

string(float direction, float segmented) FS_BoardStyle =
{
	if (direction == 1) return segmented ? "segmented_sw" : "sw";
	if (direction == 2) return segmented ? "segmented_hsw" : "hsw";
	if (direction == 3) return segmented ? "segmented_bw" : "bw";
	return segmented ? "segmented" : "clean";
};

// P1590: the boards' one mode row (Lex, 16 Nov): exactly one of these is shown, and
// each is its own board on every leg. 0-3 are the directions; the row lists
// Segmented and TAS first. Segmented directions (segmented_sw...) are no longer offered.
#define FS_MODE_SEG  4
#define FS_MODE_TAS  5
#define FS_MODES     6
float(float i) FS_ModeAt = { if (i == 0) return FS_MODE_SEG; if (i == 1) return FS_MODE_TAS; return i - 2; };
string(float m) FS_ModeName =
{
	if (m == FS_MODE_SEG) return "Segmented";
	if (m == FS_MODE_TAS) return "TAS";
	return FS_BoardDirectionName(m);
};
string(float m) FS_ModeStyle =
{
	if (m == FS_MODE_SEG) return "segmented";
	if (m == FS_MODE_TAS) return "tas";
	return FS_BoardStyle(m, FALSE);
};
// x < 0: the theme's own colours.
vector(float m) FS_ModeColour =
{
	if (m == FS_MODE_SEG) return '0.38 0.64 1';
	if (m == FS_MODE_TAS) return '0.72 0.5 1';
	return '-1 0 0';
};

// Normal has no selected chip; clicking the active mode clears it.
float(float current, float picked) FS_ModeToggle =
{
	return (current == picked) ? 0 : picked;
};

// P1590: surfd's groups (game_groups): 0 Top 10, 1-6 G1-G6, 7 ungrouped.
string(float g) FS_GroupName =
{
	if (g == 0) return "T10";
	if (g >= 1 && g <= 6) return strcat("G", ftos(g));
	return "No group";
};
vector(float g) FS_GroupColour =
{
	if (g == 0) return '1 0.45 0.82';
	if (g == 1) return '1 0.3 0.3';
	if (g == 2) return '1 0.53 0.22';
	if (g == 3) return '1 0.74 0.24';
	if (g == 4) return '0.97 0.94 0.36';
	if (g == 5) return '0.45 0.9 0.45';
	if (g == 6) return '0.4 0.72 1';
	return '0.55 0.55 0.6';
};
