// Test-only x64 debugger: initial/deferred live publication, not power loss.
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

static HANDLE child;
static FILE *events;
static void check(BOOL ok, const char *what)
{
	if (ok) return;
	fprintf(stderr, "%s: Win32 error %lu\n", what, GetLastError());
	if (child) TerminateProcess(child, 90);
	exit(90);
}
static void memory(uintptr_t address, void *data, SIZE_T size, BOOL write)
{
	SIZE_T done;
	DWORD old;
	if (write)
	{
		check(VirtualProtectEx(child, (void *)address, size, PAGE_EXECUTE_READWRITE, &old), "protect");
		check(WriteProcessMemory(child, (void *)address, data, size, &done) && done == size, "write");
		check(VirtualProtectEx(child, (void *)address, size, old, &old), "restore protection");
		check(FlushInstructionCache(child, (void *)address, size), "flush instructions");
	}
	else check(ReadProcessMemory(child, (void *)address, data, size, &done) && done == size, "read");
}
static void path_at(uintptr_t address, BOOL wide, const wchar_t *expected)
{
	wchar_t path[1024];
	char narrow[1024];
	size_t i;
	for (i = 0; i < 1024; i++)
	{
		if (wide)
		{
			memory(address + i*sizeof(wchar_t), &path[i], sizeof(wchar_t), FALSE);
			if (!path[i]) break;
		}
		else
		{
			memory(address + i, &narrow[i], 1, FALSE);
			if (!narrow[i]) break;
		}
	}
	check(i < 1024, "bounded native path");
	if (!wide) check(MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, narrow, -1, path, 1024), "native UTF8 path");
	for (i = 0; path[i]; i++) if (path[i] == L'\\') path[i] = L'/';
	check(!_wcsicmp(path, expected), "exact journal rename path");
}
int wmain(int argc, wchar_t **argv)
{
	STARTUPINFOW si = {0};
	PROCESS_INFORMATION pi = {0};
	DEBUG_EVENT ev;
	uintptr_t base = 0, entry = 0, pre = 0, post = 0, caller;
	BYTE originals[3], trap = 0xcc;
	DWORD hits = 0, writer = 0, code = 90, calls = 0, stepping = 0;
	BOOL loader = FALSE, exited = FALSE, killed = FALSE, deferred;
	DWORD saved_flags = 0;
	HANDLE lock = NULL;
	const wchar_t *engine = _wgetenv(L"OWNED_JOURNAL_ENGINE");
	wchar_t *command = _wgetenv(L"OWNED_JOURNAL_COMMAND");
	wchar_t source[1024], dest[1024], probe[1024];
	ULONGLONG deadline = GetTickCount64() + 120000;
	// Default initial ABI; optional deferred caller + initial-authority snapshot.
	if ((argc != 14 && argc != 16) || !engine || !command) return 91;
	deferred = argc == 16;
	check(!wcscmp(argv[13], L"none") || !wcscmp(argv[13], L"source-lock") || !wcscmp(argv[13], L"crash-before") || !wcscmp(argv[13], L"crash-after"), "known mode");
	check(!wcscmp(argv[9], L"wide") || !wcscmp(argv[9], L"fs"), "known ABI");
	events = _wfopen(argv[11], L"wx");
	check(events != NULL, "fresh events");
	check(swprintf(source, 1024, L"%ls/journal.tmp", argv[10]) > 0, "source path");
	check(swprintf(dest, 1024, L"%ls/journal.json", argv[10]) > 0, "destination path");
	check(swprintf(probe, 1024, L"%ls/journal.probe", argv[10]) > 0, "probe path");
	for (size_t i = 0; source[i]; i++) if (source[i] == L'\\') source[i] = L'/';
	for (size_t i = 0; dest[i]; i++) if (dest[i] == L'\\') dest[i] = L'/';
	si.cb = sizeof(si);
	si.dwFlags = STARTF_USESTDHANDLES;
	si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
	si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
	si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
	check(CreateProcessW(engine, command, NULL, NULL, TRUE, DEBUG_ONLY_THIS_PROCESS, NULL, NULL, &si, &pi), "owned debug child");
	child = pi.hProcess;
	fprintf(events, "{\"event\":\"child\",\"pid\":%lu}\n", pi.dwProcessId);
	fflush(events);
	while (!exited)
	{
		DWORD disposition = DBG_CONTINUE;
		check(GetTickCount64() < deadline, "debug deadline");
		if (!WaitForDebugEvent(&ev, 1000))
		{
			check(GetLastError() == ERROR_SEM_TIMEOUT, "debug wait");
			continue;
		}
		check(ev.dwProcessId == pi.dwProcessId, "foreign process");
		if (ev.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT)
		{
			uintptr_t addresses[3];
			base = (uintptr_t)ev.u.CreateProcessInfo.lpBaseOfImage;
			entry = base + wcstoull(argv[1], NULL, 16);
			pre = base + wcstoull(argv[2], NULL, 16);
			post = base + wcstoull(argv[3], NULL, 16);
			addresses[0] = entry; addresses[1] = pre; addresses[2] = post;
			for (size_t i = 0; i < 3; i++)
			{
				memory(addresses[i], &originals[i], 1, FALSE);
				check(originals[i] == wcstoul(argv[4+i], NULL, 16) && originals[i] != trap, "source-bound bytes");
			}
			memory(entry, &trap, 1, TRUE);
			if (ev.u.CreateProcessInfo.hFile) check(CloseHandle(ev.u.CreateProcessInfo.hFile), "close image file");
		}
		// Debug-event process/thread handles are auto-closed at EXIT events.
		else if (ev.dwDebugEventCode == LOAD_DLL_DEBUG_EVENT && ev.u.LoadDll.hFile)
			check(CloseHandle(ev.u.LoadDll.hFile), "close dll file");
		else if (ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT)
		{
			code = ev.u.ExitProcess.dwExitCode;
			fprintf(events, "{\"event\":\"exit\",\"pid\":%lu,\"code\":%lu,\"hits\":%lu,\"calls\":%lu}\n", pi.dwProcessId, code, hits, calls);
			exited = TRUE;
		}
		else if (ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT)
		{
			DWORD ex = ev.u.Exception.ExceptionRecord.ExceptionCode;
			uintptr_t at = (uintptr_t)ev.u.Exception.ExceptionRecord.ExceptionAddress;
			if (ex == EXCEPTION_SINGLE_STEP && stepping == ev.dwThreadId)
			{
				HANDLE thread = OpenThread(THREAD_GET_CONTEXT|THREAD_SET_CONTEXT, FALSE, ev.dwThreadId);
				CONTEXT ctx = {0};
				check(thread != NULL, "open stepping thread");
				ctx.ContextFlags = CONTEXT_CONTROL;
				check(GetThreadContext(thread, &ctx), "get step context");
				ctx.EFlags = (ctx.EFlags & ~0x100u) | (saved_flags & 0x100u);
				memory(entry, &trap, 1, TRUE);
				check(SetThreadContext(thread, &ctx), "restore trap flag");
				check(CloseHandle(thread), "close stepping thread");
				stepping = 0;
			}
			else if (ex == EXCEPTION_BREAKPOINT && !killed && !stepping && ((hits == 0 && at == entry) || (hits == 1 && at == pre) || (hits == 2 && at == post)))
			{
				HANDLE thread = OpenThread(THREAD_GET_CONTEXT|THREAD_SET_CONTEXT, FALSE, ev.dwThreadId);
				CONTEXT ctx = {0};
				check(thread != NULL, "open stopped thread");
				ctx.ContextFlags = CONTEXT_CONTROL|CONTEXT_INTEGER;
				check(GetThreadContext(thread, &ctx), "get stopped context");
				check(!writer || writer == ev.dwThreadId, "same live writer thread");
				writer = ev.dwThreadId;
				memory(at, &originals[hits], 1, TRUE);
				ctx.Rip = at;
				if (hits == 0)
				{
					calls++;
					check(calls <= (deferred ? 2u : 1u), "live writer ordinal");
					memory(ctx.Rsp, &caller, sizeof(caller), FALSE);
					check(caller == base + wcstoull(argv[calls == 1 ? 7 : 14], NULL, 16), "inspected live caller");
					fprintf(events, "{\"event\":\"writer\",\"ordinal\":%lu,\"rva\":%llu,\"thread\":%lu,\"caller_rva\":%llu}\n", calls, (unsigned long long)(at-base), writer, (unsigned long long)(caller-base));
					if (deferred && calls == 1)
					{
						saved_flags = ctx.EFlags;
						check(!(saved_flags & 0x100u), "untraced first writer");
						ctx.EFlags |= 0x100u;
						stepping = ev.dwThreadId;
					}
					else
					{
						if (deferred)
						{
							check(CopyFileW(dest, argv[15], TRUE), "snapshot full prior authority");
							check(GetFileAttributesW(source) == INVALID_FILE_ATTRIBUTES && GetLastError() == ERROR_FILE_NOT_FOUND, "first temp consumed");
						}
						memory(pre, &trap, 1, TRUE);
					}
				}
				else if (hits == 1)
				{
					BOOL wide = !wcscmp(argv[9], L"wide");
					path_at(ctx.Rcx, wide, source);
					path_at(ctx.Rdx, wide, dest);
					check(ctx.R8 == (wide ? 1u : 3u), "rename flags/root");
					if (wide)
					{
						memory(ctx.Rsp + 0x1848, &caller, sizeof(caller), FALSE);
						check(caller == base + wcstoull(argv[8], NULL, 16), "inspected live commit caller");
					}
					if (deferred && wide)
						check(GetFileAttributesW(dest) != INVALID_FILE_ATTRIBUTES, "prior authority retained before replace");
					else
						check(GetFileAttributesW(dest) == INVALID_FILE_ATTRIBUTES && GetLastError() == ERROR_FILE_NOT_FOUND, "authority absent before rename");
					check(CopyFileW(source, argv[12], TRUE), "snapshot complete native temp");
					fprintf(events, "{\"event\":\"before\",\"rva\":%llu,\"thread\":%lu,\"paths_verified\":true,\"authority_absent\":%s}\n", (unsigned long long)(at-base), writer, deferred && wide ? "false" : "true");
					if (!wcscmp(argv[13], L"source-lock"))
					{
						HANDLE writable;
						lock = CreateFileW(source, GENERIC_READ, FILE_SHARE_READ|FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
						check(lock != INVALID_HANDLE_VALUE, "complete source share lock");
						writable = CreateFileW(source, GENERIC_WRITE, FILE_SHARE_READ|FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
						check(writable != INVALID_HANDLE_VALUE, "source remains writable");
						check(CloseHandle(writable), "close allowed writer");
						check(GetFileAttributesW(probe) == INVALID_FILE_ATTRIBUTES && GetLastError() == ERROR_FILE_NOT_FOUND, "fresh probe destination");
						check(!MoveFileExW(source, probe, MOVEFILE_REPLACE_EXISTING) && GetLastError() == ERROR_SHARING_VIOLATION, "source rename must fail32");
						fprintf(events, "{\"event\":\"source-lock\",\"rename_error\":32,\"write_allowed\":true}\n");
					}
					if (wcscmp(argv[13], L"crash-before")) memory(post, &trap, 1, TRUE);
				}
				else
				{
					BOOL failed = !wcscmp(argv[13], L"source-lock");
					check(((DWORD)ctx.Rax == 0) == failed, "actual native publication result");
					fprintf(events, "{\"event\":\"after\",\"rva\":%llu,\"thread\":%lu,\"native_result\":%lu}\n", (unsigned long long)(at-base), writer, (DWORD)ctx.Rax);
					if (lock) { check(CloseHandle(lock), "release source lock after actual failure"); lock = NULL; }
				}
				if (!stepping) hits++;
				check(SetThreadContext(thread, &ctx), "restore native context");
				check(CloseHandle(thread), "close stopped thread");
				if ((!wcscmp(argv[13], L"crash-before") && hits == 2) || (!wcscmp(argv[13], L"crash-after") && hits == 3))
				{
					fflush(events);
					check(TerminateProcess(child, 86), "interrupt only owned child");
					killed = TRUE;
					fprintf(events, "{\"event\":\"interrupt\",\"code\":86,\"hits\":%lu}\n", hits);
				}
			}
			else if (ex == EXCEPTION_BREAKPOINT && !loader && hits == 0) loader = TRUE;
			else disposition = DBG_EXCEPTION_NOT_HANDLED;
		}
		fflush(events);
		check(ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, disposition), "continue native execution");
	}
	if (lock) check(CloseHandle(lock), "close remaining source lock");
	check(CloseHandle(pi.hThread), "close primary thread");
	check(CloseHandle(child), "close child");
	child = NULL;
	check(fclose(events) == 0, "close receipt");
	return calls == (deferred ? 2u : 1u) && !stepping && hits == (wcscmp(argv[13], L"crash-before") ? 3u : 2u) &&
		(killed ? code == 86 : code == 0) ? 0 : 92;
}
