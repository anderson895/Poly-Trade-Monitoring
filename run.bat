@echo off
rem PolyTrade Pro launcher - double-click para buksan ang app
cd /d "%~dp0"
start "" venv\Scripts\pythonw.exe -m src.main
