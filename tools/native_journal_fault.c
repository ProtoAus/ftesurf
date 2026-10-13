// Harness-only POSIX rename interposer. Never linked into or shipped with the engine.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int ends(const char *path, const char *tail)
{
	size_t n = strlen(path), t = strlen(tail);
	return n >= t && !strcmp(path+n-t, tail);
}

int rename(const char *oldpath, const char *newpath)
{
	int (*realrename)(const char *, const char *) = dlsym(RTLD_NEXT, "rename");
	const char *mode = getenv("NATIVE_JOURNAL_FAULT"), *log = getenv("NATIVE_JOURNAL_FAULT_LOG");
	int fd, result;
	char line[128];
	if (!realrename) _exit(92);
	if (!mode || !log || !ends(oldpath, "/.ftesurf-updater/ingame/journal.tmp") ||
		!ends(newpath, "/.ftesurf-updater/ingame/journal.json"))
		return realrename(oldpath, newpath);
	fd = open(log, O_WRONLY|O_CREAT|O_APPEND|O_NOFOLLOW, 0600);
	if (fd < 0) _exit(93);
	result = snprintf(line, sizeof(line), "journal-rename pid=%ld mode=%s\n", (long)getpid(), mode);
	if (result <= 0 || result >= (int)sizeof(line) || write(fd, line, result) != result) _exit(94);
	if (!strcmp(mode, "fail")) { close(fd); errno = EACCES; return -1; }
	if (!strcmp(mode, "crash-before")) { close(fd); _exit(86); }
	if (strcmp(mode, "crash-after")) _exit(95);
	result = realrename(oldpath, newpath);
	if (result) _exit(96);
	if (write(fd, "journal-rename committed\n", 25) != 25) _exit(97);
	close(fd);
	_exit(86);
}
