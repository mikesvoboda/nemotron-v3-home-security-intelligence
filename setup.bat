@echo off
REM setup.bat - Windows wrapper for setup.py
REM Usage: setup.bat [--guided]

python "%~dp0setup.py" %*
