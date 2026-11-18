// P1568: opt-in loose-disk I/O. FILE_READ still materializes on its first read.
#define FS_FILE_READSTREAM 10
#define FS_FILE_WRITESTREAM 9
#define FS_ARCHIVE_BYTES 1073741823i // signed byte offsets, finite disk bound
#define FS_ARCHIVE_WORK 65536i
string(float fh, int quota) FS_FileSHA256Step = #0:file_sha256_step;
__int64(float fh) FS_StreamSize = #0:fsize64;
float(string path) FS_WritePathStatus = #0:fwritepathstatus;

// P1617: asked once -- the archive stream calls this every frame and checkextension prints at developer 1
// (pr_cmds.c:7676), 99% of every lobby log. The declared local keeps fteqcc's frame for this function off
// the state global, which a temporaries-only frame covered and the VM reset on return: tools/qcframes.py.
float fs_streamfiles_state;     // 0 not asked yet, 1 yes, -1 no
float() FS_StreamFiles =
{
	local float ok;
	if (!fs_streamfiles_state)
	{
		ok = checkextension("FTESURF_QC_FILESTREAM_HASH");
		if (ok) ok = checkbuiltin(FS_FileSHA256Step);
		if (ok) ok = checkbuiltin(FS_StreamSize);
		if (ok) ok = checkbuiltin(FS_WritePathStatus);
		fs_streamfiles_state = ok ? 1 : -1;
	}
	return fs_streamfiles_state > 0;
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
