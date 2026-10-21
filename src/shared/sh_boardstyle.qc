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
	return strcat(FS_BoardSegmented(style) ? "Segmented " : "", FS_BoardDirectionName(FS_BoardDirection(style)));
};

string(float direction, float segmented) FS_BoardStyle =
{
	if (direction == 1) return segmented ? "segmented_sw" : "sw";
	if (direction == 2) return segmented ? "segmented_hsw" : "hsw";
	if (direction == 3) return segmented ? "segmented_bw" : "bw";
	return segmented ? "segmented" : "clean";
};
