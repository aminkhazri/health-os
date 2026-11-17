@echo off
rem Health OS model builder. Runs Blender without a window each time a file named go.txt appears in this folder.
rem It only ever runs: blender.exe -b -P run.py   (run.py runs build_body.py and writes log.txt). Close this window to stop it.
title Health OS model builder
cd /d "C:\Health Os"
set BL="C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
echo Waiting for build requests. Leave this window open; close it to stop.
:loop
if exist go.txt (
  del go.txt
  if exist done.txt del done.txt
  echo [%time%] building...
  %BL% -b --factory-startup -P run.py > blender_out.txt 2>&1
  echo finished > done.txt
  echo [%time%] finished
)
timeout /t 2 /nobreak > nul
goto loop
