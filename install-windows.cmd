@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
py -3.11 -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
if not errorlevel 1 goto launcher
python -c "import sys; assert sys.version_info[:2] == (3,11) and sys.maxsize > 2**32" >nul 2>&1
if not errorlevel 1 goto python
echo Install Python 3.11 x64, then run this file again.
echo Or ask a local AI agent to follow AGENTS.md in this folder.
pause
exit /b 1
:launcher
py -3.11 -X utf8 src/setup_windows.py %*
goto finished
:python
python -X utf8 src/setup_windows.py %*
:finished
set result=%errorlevel%
pause
exit /b %result%
