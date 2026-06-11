@echo off
setlocal
title PUE Solver EPW API Server
cd /d "%~dp0"
echo.
echo EPW API Server
echo --------------------
echo EPW API Server running at:
echo http://127.0.0.1:8011
echo.
echo Keep this window open while using online EPW fetch.
echo Press Ctrl+C to stop the server.
echo.
"%LOCALAPPDATA%\Python\bin\python.exe" tools\epw_api_server.py --host 127.0.0.1 --port 8011
pause
