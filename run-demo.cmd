@echo off
rem Double-click to start the whole KORA site (database + backend + frontend).
powershell -ExecutionPolicy Bypass -File "%~dp0run-demo.ps1" %*
pause
