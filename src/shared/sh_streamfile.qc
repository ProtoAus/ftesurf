// P1568: opt-in loose-disk I/O. FILE_READ still materializes on its first read.
#define FS_FILE_READSTREAM 10
#define FS_FILE_WRITESTREAM 9
#define FS_ARCHIVE_BYTES 1073741823i // signed byte offsets, finite disk bound
#define FS_ARCHIVE_WORK 65536i
string(float fh, int quota) FS_FileSHA256Step = #0:file_sha256_step;
__int64(float fh) FS_StreamSize = #0:fsize64;
float(string path) FS_WritePathStatus = #0:fwritepathstatus;

float() FS_StreamFiles =
{
	if (!checkextension("FTESURF_QC_FILESTREAM_HASH")) return FALSE;
	if (!checkbuiltin(FS_FileSHA256Step)) return FALSE;
	if (!checkbuiltin(FS_StreamSize)) return FALSE;
	if (!checkbuiltin(FS_WritePathStatus)) return FALSE;
	return TRUE;
};

// A decimal wire/sidecar field, never a float32 byte count.
int(string value) FS_ArchiveSize =
{
	local int n;
	n = stoi(value);
	if (n < 1i || n > FS_ARCHIVE_BYTES) return 0i;
	if (strcmp(value, itos(n))) return 0i;
	return n;
};
