// Test-only x64 Windows debugger; never link or ship into the engine.
// Stop the source-bound second live writer, then let its real rename fail.
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

int wmain(int argc, wchar_t **argv)
{
	STARTUPINFOW si = {0};
	PROCESS_INFORMATION pi = {0};
	DEBUG_EVENT ev;
	uintptr_t address = 0, base = 0, caller;
	DWORD stepping = 0, writer = 0, calls = 0, code = 90;
	BYTE original, trap = 0xcc;
	BOOL loader = FALSE, armed = FALSE, exited = FALSE;
	HANDLE lock = NULL;
	wchar_t journal[32768], tmp[32768], probe[32768];
	const wchar_t *engine = _wgetenv(L"OWNED_JOURNAL_ENGINE");
	wchar_t *command = _wgetenv(L"OWNED_JOURNAL_COMMAND");
	ULONGLONG deadline = GetTickCount64() + 120000;
	if (argc != 7 || !engine || !command) return 91;
	si.cb = sizeof(si);
	si.dwFlags = STARTF_USESTDHANDLES;
	si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
	si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
	si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
	events = _wfopen(argv[4], L"wx");
	check(events != NULL, "fresh events file");
	check(swprintf(journal, 32768, L"%ls/journal.json", argv[3]) > 0, "journal path");
	check(swprintf(tmp, 32768, L"%ls/journal.tmp", argv[3]) > 0, "temp path");
	check(swprintf(probe, 32768, L"%ls/journal.probe", argv[3]) > 0, "probe path");
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
		check(ev.dwProcessId == pi.dwProcessId, "foreign debug process");
		if (ev.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT)
		{
			base = (uintptr_t)ev.u.CreateProcessInfo.lpBaseOfImage;
			address = base + wcstoull(argv[1], NULL, 16);
			memory(address, &original, 1, FALSE);
			check(original == wcstoul(argv[2], NULL, 16) && original != trap, "source-bound prologue");
			memory(address, &trap, 1, TRUE);
			armed = TRUE;
			if (ev.u.CreateProcessInfo.hFile) check(CloseHandle(ev.u.CreateProcessInfo.hFile), "close image file");
		}
		// Debug-event process/thread handles belong to the debugger lifecycle:
		// ContinueDebugEvent(EXIT_THREAD/PROCESS) closes them automatically.
		// Closing early allows reuse, then an automatic close of an unrelated lock.
		else if (ev.dwDebugEventCode == LOAD_DLL_DEBUG_EVENT && ev.u.LoadDll.hFile)
			check(CloseHandle(ev.u.LoadDll.hFile), "close dll file");
		else if (ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT)
		{
			code = ev.u.ExitProcess.dwExitCode;
			fprintf(events, "{\"event\":\"exit\",\"pid\":%lu,\"code\":%lu,\"calls\":%lu}\n", pi.dwProcessId, code, calls);
			exited = TRUE;
		}
		else if (ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT)
		{
			DWORD ex = ev.u.Exception.ExceptionRecord.ExceptionCode;
			uintptr_t at = (uintptr_t)ev.u.Exception.ExceptionRecord.ExceptionAddress;
			if ((ex == EXCEPTION_BREAKPOINT && armed && at == address) ||
				(ex == EXCEPTION_SINGLE_STEP && stepping == ev.dwThreadId))
			{
				HANDLE thread = OpenThread(THREAD_GET_CONTEXT|THREAD_SET_CONTEXT, FALSE, ev.dwThreadId);
				CONTEXT ctx = {0};
				check(thread != NULL, "open stopped thread");
				ctx.ContextFlags = CONTEXT_CONTROL;
				check(GetThreadContext(thread, &ctx), "get stopped context");
				if (ex == EXCEPTION_SINGLE_STEP)
				{
					ctx.EFlags &= ~0x100u;
					stepping = 0;
					memory(address, &trap, 1, TRUE);
					armed = TRUE;
				}
				else
				{
					calls++;
					check(calls <= 2 && (!writer || writer == ev.dwThreadId), "writer ordinal/thread");
					writer = ev.dwThreadId;
					memory((uintptr_t)ctx.Rsp, &caller, sizeof(caller), FALSE);
					fprintf(events, "{\"event\":\"writer\",\"ordinal\":%lu,\"thread\":%lu,\"rva\":%llu,\"caller_rva\":%llu}\n", calls, writer, (unsigned long long)(address-base), (unsigned long long)(caller-base));
					memory(address, &original, 1, TRUE);
					armed = FALSE;
					ctx.Rip = address;
					if (calls == 1)
					{
						ctx.EFlags |= 0x100u;
						stepping = ev.dwThreadId;
					}
					else
					{
						// First write returned and partial install acted. Save authority BEFORE fault.
						check(CopyFileW(journal, argv[5], TRUE), "save initial full authority");
						check(GetFileAttributesW(tmp) == INVALID_FILE_ATTRIBUTES && GetLastError() == ERROR_FILE_NOT_FOUND, "first temp consumed");
						if (!wcscmp(argv[6], L"source-lock"))
						{
							DWORD wrote;
							const char bytes[] = "owned second-writer source-lock probe\n";
							HANDLE out = CreateFileW(tmp, GENERIC_WRITE, FILE_SHARE_READ|FILE_SHARE_WRITE, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
							check(out != INVALID_HANDLE_VALUE, "create only second temp");
							check(WriteFile(out, bytes, sizeof(bytes)-1, &wrote, NULL) && wrote == sizeof(bytes)-1, "write probe");
							check(CloseHandle(out), "close probe writer");
							lock = CreateFileW(tmp, GENERIC_READ, FILE_SHARE_READ|FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
							check(lock != INVALID_HANDLE_VALUE, "second source share lock");
							out = CreateFileW(tmp, GENERIC_WRITE, FILE_SHARE_READ|FILE_SHARE_WRITE, NULL, TRUNCATE_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
							check(out != INVALID_HANDLE_VALUE, "write/truncate while locked");
							check(CloseHandle(out), "close allowed writer");
							check(GetFileAttributesW(probe) == INVALID_FILE_ATTRIBUTES && GetLastError() == ERROR_FILE_NOT_FOUND, "fresh probe destination");
							check(!MoveFileExW(tmp, probe, MOVEFILE_REPLACE_EXISTING) && GetLastError() == ERROR_SHARING_VIOLATION, "real source rename must fail32");
							fprintf(events, "{\"event\":\"source-lock\",\"ordinal\":2,\"rename_error\":32,\"write_allowed\":true}\n");
						}
						else check(!wcscmp(argv[6], L"none"), "known fault mode");
					}
				}
				check(SetThreadContext(thread, &ctx), "restore stopped context");
				check(CloseHandle(thread), "close stopped thread");
			}
			else if (ex == EXCEPTION_BREAKPOINT && !loader && calls == 0) loader = TRUE;
			else disposition = DBG_EXCEPTION_NOT_HANDLED;
		}
		fflush(events);
		check(ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, disposition), "continue native execution");
	}
	if (lock) check(CloseHandle(lock), "release source lock");
	check(CloseHandle(pi.hThread), "close primary thread");
	check(CloseHandle(child), "close child process");
	child = NULL;
	check(fclose(events) == 0, "close event receipt");
	return code == 0 && calls == 2 && !armed && !stepping ? 0 : 92;
}
