@echo off
rem ===========================================================================
rem  cluster_test.cmd -- mapcluster on THIS fork, with output captured.
rem
rem  RUN 1 RESULT (2026-09-13): the cluster WORKED and then the node died.
rem  The gateway accepted the client, forked node 17, and that node loaded
rem  surf_ace completely -- VBSP lumps, 1147 clusters, 473 worldlights, all 109
rem  static props -- and then printed "Player's node crashed out (surf_ace)",
rem  which is MSV_ServerCrashed (sv_cluster.c:167) noticing the child's pipe hit
rem  EOF.  The client then looped on challenge/print because it was being
rem  redirected to a node that kept dying.
rem
rem  So this is NOT a startup failure and NOT a missing feature.  Something
rem  kills the leaf AFTER SpawnServer returns, and the gateway's relayed stdout
rem  does not say what.
rem
rem  WHAT CHANGED IN THIS VERSION, and why each thing:
rem
rem  1. THE GATEWAY'S CONSOLE IS REDIRECTED TO A FILE.  Sys_ForkServer gives the
rem     child a PIPE for stdout (relayed by the gateway, prefixed "17(map):")
rem     but hands it the PARENT'S OWN stderr handle (sys_win_threads.c:532), so
rem     a dying leaf's last words go to the gateway's console and nowhere else.
rem     Scrollback is not evidence; a file is.
rem
rem  2. +set sv_serverip 127.0.0.1 on the gateway.  specs/mapcluster.txt lists
rem     this under "random useful commands" and SSV_UpdateAddresses
rem     (sv_cluster.c:1624) uses it to decide which address a leaf reports back.
rem     Without it the leaf enumerates every interface and may hand the client
rem     one it cannot reach.  That would not explain a CRASH, but it would
rem     explain a reconnect loop, and both are in play here.
rem
rem  3. +set developer 1 on both, so the leaf's own load path is verbose.
rem
rem  Logs land in tools\clusterlog\.  Send me gateway.log -- that is the one
rem  with the leaf's death in it.
rem ===========================================================================
setlocal
cd /d "%~dp0.."
if not exist "tools\clusterlog" mkdir "tools\clusterlog"

echo.
echo === FTESurf mapcluster test (run 2, with capture) ====================
echo Gateway  : 127.0.0.1:27600, console -^> tools\clusterlog\gateway.log
echo Leaf     : forked on connect, should run surf_ace
echo.
echo Run 1 got as far as the leaf loading the whole map, then it died.
echo This run captures why.
echo =====================================================================
echo.

rem cmd /c with redirection, so the gateway's stdout AND stderr reach the file.
rem `start` alone cannot redirect, which is why this is wrapped.
start "FTESurf CLUSTER GATEWAY" cmd /c ^
  ftesurf64.exe -dedicated ^
  +set sv_port 27600 +set sv_public 0 +set developer 1 ^
  +set sv_serverip 127.0.0.1 ^
  +mapcluster surf_ace ^
  ^> tools\clusterlog\gateway.log 2^>^&1

echo Gateway starting -- waiting 10s...
timeout /t 10 /nobreak >nul

start "FTESurf CLUSTER CLIENT" ftesurf64.exe ^
  +set vid_fullscreen 0 +set developer 1 ^
  +set log_enable 1 +set log_dir logs +set log_name clusterclient ^
  +connect 127.0.0.1:27600

echo.
echo Both launched.  Give it ~30s, then close both windows.
echo Then send me:  tools\clusterlog\gateway.log
echo.
endlocal
