@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
".venv\Scripts\pythonw.exe" -m ups_label_cropper.__main__ --watch