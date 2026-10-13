// Test-only x64 Windows debugger. Never link or ship into a product.
// Break before the inspected journal rename and at its unchanged return PC.
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
	uintptr_t base = 0, pre = 0, post = 0, caller;
	BYTE originals[2], trap = 0xcc;
	DWORD hits = 0, writer = 0, code = 90;
	BOOL loader = FALSE, exited = FALSE, killed = FALSE;
	const wchar_t *engine = _wgetenv(L"OWNED_JOURNAL_ENGINE");
	wchar_t *command = _wgetenv(L"OWNED_JOURNAL_COMMAND");
	wchar_t source[1024], dest[1024];
	ULONGLONG deadline = GetTickCount64() + 60000;
	// pre/post RVAs, original bytes, ingame dir, receipt, mode, ABI, cold caller RVA
	if (argc != 10 || !engine || !command) return 91;
	check(!wcscmp(argv[7], L"none") || !wcscmp(argv[7], L"crash-before") || !wcscmp(argv[7], L"crash-after"), "known mode");
	check(!wcscmp(argv[8], L"wide") || !wcscmp(argv[8], L"fs"), "known ABI");
	events = _wfopen(argv[6], L"wx");
	check(events != NULL, "fresh events");
	check(swprintf(source, 1024, L"%ls/journal.tmp", argv[5]) > 0, "source path");
	check(swprintf(dest, 1024, L"%ls/journal.json", argv[5]) > 0, "destination path");
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
			base = (uintptr_t)ev.u.CreateProcessInfo.lpBaseOfImage;
			pre = base + wcstoull(argv[1], NULL, 16);
			post = base + wcstoull(argv[2], NULL, 16);
			memory(pre, &originals[0], 1, FALSE);
			memory(post, &originals[1], 1, FALSE);
			check(originals[0] == wcstoul(argv[3], NULL, 16) && originals[1] == wcstoul(argv[4], NULL, 16) && originals[0] != trap && originals[1] != trap, "source-bound call bytes");
			memory(pre, &trap, 1, TRUE);
			if (ev.u.CreateProcessInfo.hFile) check(CloseHandle(ev.u.CreateProcessInfo.hFile), "close image file");
		}
		// Debug-event process/thread handles are auto-closed at EXIT events.
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
				check(!writer || writer == ev.dwThreadId, "same rename thread");
				writer = ev.dwThreadId;
				memory(at, &originals[hits], 1, TRUE);
				ctx.Rip = at;
				if (hits == 0)
				{
					BOOL wide = !wcscmp(argv[8], L"wide");
					path_at(ctx.Rcx, wide, source);
					path_at(ctx.Rdx, wide, dest);
					check(ctx.R8 == (wide ? 1u : 3u), "rename flags/root");
					if (wide)
					{
						// Binding verifies this exact part.0 prologue and wrapper tail jump.
						memory(ctx.Rsp + 0x1848, &caller, sizeof(caller), FALSE);
						check(caller == base + wcstoull(argv[9], NULL, 16), "inspected cold caller");
					}
					fprintf(events, "{\"event\":\"before\",\"rva\":%llu,\"thread\":%lu,\"paths_verified\":true}\n", (unsigned long long)(at-base), writer);
					if (wcscmp(argv[7], L"crash-before")) memory(post, &trap, 1, TRUE);
				}
				else
				{
					check((DWORD)ctx.Rax != 0, "real native rename succeeded");
					fprintf(events, "{\"event\":\"after\",\"rva\":%llu,\"thread\":%lu,\"native_result\":%lu}\n", (unsigned long long)(at-base), writer, (DWORD)ctx.Rax);
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
	return killed ? (code == 86 ? 0 : 92) : (hits == 2 && code != 0 ? 0 : 92);
}
