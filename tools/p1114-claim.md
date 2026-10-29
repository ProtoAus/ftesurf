# P1114 claim -- ftesurf-aa (Claude Code), 2026-10-29T08:37Z

Engine, Lex 29 Oct: the engine's own map / file downloads (cl_parse.c HTTP_CL_Get) resolve and connect on
the main thread; move them to the download threads. Files: engine/client/cl_parse.c, engine/http/httpclient.c.
