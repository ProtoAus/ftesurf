// Test-only x64 Windows debugger: actual staged removal, never linked/shipped.
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
static void path_at(uintptr_t address, const wchar_t *expected)
{
	wchar_t path[1024];
	char narrow[1024];
	size_t i;
	for (i = 0; i < 1024; i++)
	{
		memory(address + i, &narrow[i], 1, FALSE);
		if (!narrow[i]) break;
	}
	check(i < 1024, "bounded native staged path");
	check(MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, narrow, -1, path, 1024), "native UTF8 path");
	for (i = 0; path[i]; i++) if (path[i] == L'\\') path[i] = L'/';
	check(!_wcsicmp(path, expected), "exact signed staged leaf");
}
static BOOL absent(const wchar_t *path)
{
	DWORD attr = GetFileAttributesW(path);
	DWORD error = GetLastError();
	return attr == INVALID_FILE_ATTRIBUTES && (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND);
}
int wmain(int argc, wchar_t **argv)
{
	STARTUPINFOW si = {0};
	PROCESS_INFORMATION pi = {0};
	DEBUG_EVENT ev;
	uintptr_t base = 0, pre = 0, post = 0;
	BYTE originals[2], trap = 0xcc;
	DWORD hits = 0, writer = 0, code = 90;
	BOOL loader = FALSE, exited = FALSE, killed = FALSE;
	const wchar_t *engine = _wgetenv(L"OWNED_JOURNAL_ENGINE");
	wchar_t *command = _wgetenv(L"OWNED_JOURNAL_COMMAND");
	const wchar_t *hash = _wgetenv(L"OWNED_RETIRE_HASH");
	wchar_t staged[1024], journal[1024];
	ULONGLONG deadline = GetTickCount64() + 60000;
	// Same guarded runner ABI: pre/post RVAs, bytes, ingame dir, receipt, mode, fs, reserved.
	if (argc != 10 || !engine || !command || !hash || wcslen(hash) != 64) return 91;
	for (size_t i = 0; i < 64; i++) check((hash[i] >= L'0' && hash[i] <= L'9') || (hash[i] >= L'a' && hash[i] <= L'f'), "bounded hash");
	check(!wcscmp(argv[7], L"crash-before") || !wcscmp(argv[7], L"crash-after"), "known mode");
	check(!wcscmp(argv[8], L"fs"), "FS_Remove ABI");
	events = _wfopen(argv[6], L"wx");
	check(events != NULL, "fresh events");
	check(swprintf(staged, 1024, L"%ls/staged/%ls", argv[5], hash) > 0, "stage path");
	check(swprintf(journal, 1024, L"%ls/journal.json", argv[5]) > 0, "journal path");
	for (size_t i = 0; staged[i]; i++) if (staged[i] == L'\\') staged[i] = L'/';
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
			base = (uintptr_t)ev.u.CreateProcessInfo.lpBaseOfImage;
			pre = base + wcstoull(argv[1], NULL, 16);
			post = base + wcstoull(argv[2], NULL, 16);
			memory(pre, &originals[0], 1, FALSE);
			memory(post, &originals[1], 1, FALSE);
			check(originals[0] == wcstoul(argv[3], NULL, 16) && originals[1] == wcstoul(argv[4], NULL, 16) && originals[0] != trap && originals[1] != trap, "source-bound call bytes");
			memory(pre, &trap, 1, TRUE);
			if (ev.u.CreateProcessInfo.hFile) check(CloseHandle(ev.u.CreateProcessInfo.hFile), "close image file");
		}
		else if (ev.dwDebugEventCode == LOAD_DLL_DEBUG_EVENT && ev.u.LoadDll.hFile)
			check(CloseHandle(ev.u.LoadDll.hFile), "close dll file");
		else if (ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT)
		{
			code = ev.u.ExitProcess.dwExitCode;
			fprintf(events, "{\"event\":\"exit\",\"pid\":%lu,\"code\":%lu,\"hits\":%lu}\n", pi.dwProcessId, code, hits);
			exited = TRUE;
		}
		else if (ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT)
		{
			DWORD ex = ev.u.Exception.ExceptionRecord.ExceptionCode;
			uintptr_t at = (uintptr_t)ev.u.Exception.ExceptionRecord.ExceptionAddress;
			if (ex == EXCEPTION_BREAKPOINT && ((hits == 0 && at == pre) || (hits == 1 && at == post)) && !killed)
			{
				HANDLE thread = OpenThread(THREAD_GET_CONTEXT|THREAD_SET_CONTEXT, FALSE, ev.dwThreadId);
				CONTEXT ctx = {0};
				check(thread != NULL, "open stopped thread");
				ctx.ContextFlags = CONTEXT_CONTROL|CONTEXT_INTEGER;
				check(GetThreadContext(thread, &ctx), "get stopped context");
				check(!writer || writer == ev.dwThreadId, "same removal thread");
				writer = ev.dwThreadId;
				memory(at, &originals[hits], 1, TRUE);
				ctx.Rip = at;
				check(GetFileAttributesW(journal) != INVALID_FILE_ATTRIBUTES, "authority survives removal seam");
				if (hits == 0)
				{
					path_at(ctx.Rcx, staged);
					check(ctx.Rdx == 3u && !absent(staged), "FS_SYSTEM root and present staged leaf");
					fprintf(events, "{\"event\":\"before\",\"rva\":%llu,\"thread\":%lu,\"paths_verified\":true}\n", (unsigned long long)(at-base), writer);
					if (!wcscmp(argv[7], L"crash-after")) memory(post, &trap, 1, TRUE);
				}
				else
				{
					check((DWORD)ctx.Rax != 0 && absent(staged), "real removal succeeded and leaf OS-confirmed absent");
					fprintf(events, "{\"event\":\"after\",\"rva\":%llu,\"thread\":%lu,\"native_result\":%lu,\"leaf_absent\":true,\"journal_present\":true}\n", (unsigned long long)(at-base), writer, (DWORD)ctx.Rax);
				}
				hits++;
				check(SetThreadContext(thread, &ctx), "restore exact call/return context");
				check(CloseHandle(thread), "close stopped thread");
				if ((!wcscmp(argv[7], L"crash-before") && hits == 1) || (!wcscmp(argv[7], L"crash-after") && hits == 2))
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
	check(CloseHandle(pi.hThread), "close primary thread");
	check(CloseHandle(child), "close child");
	child = NULL;
	check(fclose(events) == 0, "close receipt");
	return killed && code == 86 ? 0 : 92;
}
