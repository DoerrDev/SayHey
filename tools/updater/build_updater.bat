@echo off
cd /d %~dp0
python -m nuitka ^
  --standalone --onefile ^
  --windows-console-mode=disable ^
  --output-filename=updater_app.exe ^
  --output-dir=build_out ^
  updater.py
if errorlevel 1 exit /b 1
