@echo off
setlocal
cd /d "%~dp0"
python scripts/build_pyinstaller.py --name AxisPyEngine --entrypoint main.py
endlocal
