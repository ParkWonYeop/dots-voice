@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist ".tts-venv\Scripts\python.exe" (
  echo Run install-windows.cmd first.
  pause
  exit /b 1
)
".tts-venv\Scripts\python.exe" -X utf8 src/voice_launcher.py --stop
set result=%errorlevel%
pause
exit /b %result%
