@echo off
setlocal
title PUE Solver UI Server
cd /d "%~dp0pue-solver-main"
echo.
echo PUE Solver UI server
echo --------------------
echo Serving folder:
echo %CD%
echo.
echo Open this address in your browser:
echo http://127.0.0.1:8000/index.html
echo.
echo Keep this window open while using the page.
echo Press Ctrl+C to stop the server.
echo.
"%LOCALAPPDATA%\Python\bin\python.exe" -m http.server 8000 --bind 127.0.0.1
pause
